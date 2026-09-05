from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


INFRA = Path(__file__).resolve().parents[1]
ROOT = INFRA.parent
sys.path.insert(0, str(INFRA / "python"))

from episteme_org import completion as complete_agent_todo
from episteme_org import integrity as check_integrity


class CompleteAgentTodoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write(self, content: str) -> Path:
        path = self.root / "note.org"
        path.write_text(content, encoding="utf-8")
        return path

    def test_removes_only_the_matching_drawer_atomically(self) -> None:
        path = self.write(
            "#+title: Note\n* Scope\n:AGENT_TODO:\nReview café.\n:END:\nText.\n"
        )
        documents, _ = check_integrity.parse_repository(self.root)
        fingerprint = documents[0].todos[0].fingerprint

        completed_path = complete_agent_todo.complete_todo(self.root, fingerprint)

        self.assertEqual(completed_path, Path("note.org"))
        self.assertEqual(path.read_text(encoding="utf-8"), "#+title: Note\n* Scope\nText.\n")
        refreshed, issues = check_integrity.parse_repository(self.root)
        self.assertEqual(issues, [])
        self.assertEqual(refreshed[0].todos, [])

    def test_rejects_a_stale_fingerprint_without_editing(self) -> None:
        original = ":AGENT_TODO:\nOriginal task.\n:END:\n"
        path = self.write(original)
        documents, _ = check_integrity.parse_repository(self.root)
        fingerprint = documents[0].todos[0].fingerprint
        changed = original.replace("Original", "Changed")
        path.write_text(changed, encoding="utf-8")

        with self.assertRaisesRegex(RuntimeError, "unknown or changed"):
            complete_agent_todo.complete_todo(self.root, fingerprint)

        self.assertEqual(path.read_text(encoding="utf-8"), changed)

    def test_rejects_completion_while_repository_has_integrity_errors(self) -> None:
        self.write(":AGENT_TODO:\nTask.\n:END:\n[[file:missing.org]]\n")
        documents, _ = check_integrity.parse_repository(self.root)
        fingerprint = documents[0].todos[0].fingerprint

        with self.assertRaisesRegex(RuntimeError, "integrity errors"):
            complete_agent_todo.complete_todo(self.root, fingerprint)
