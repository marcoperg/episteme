from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


INFRA = Path(__file__).resolve().parents[1]
ROOT = INFRA.parent


@unittest.skipUnless(shutil.which("ciao-shell"), "Ciao is not installed")
class AgentTodoCliTests(unittest.TestCase):
    def test_list_reads_an_untracked_todo_from_the_live_worktree(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agent-todo-test-", dir=ROOT) as name:
            directory = Path(name)
            relative_path = directory.relative_to(ROOT) / "note.org"
            body = "Review café [cite:@draftKey p. 4]."
            (directory / "note.org").write_text(
                "#+title: Test\n* Scope\n:AGENT_TODO:\n"
                f"{body}\n:END:\n",
                encoding="utf-8",
            )
            value = "\0".join((relative_path.as_posix(), "Scope", body))
            fingerprint = hashlib.sha256(value.encode("utf-8")).hexdigest()

            result = subprocess.run(
                [str(INFRA / "bin" / "agent-todos"), "list"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            )

        self.assertIn(fingerprint, result.stdout)
        self.assertIn(relative_path.as_posix(), result.stdout)
        self.assertIn("['Scope']", result.stdout)

    def test_complete_removes_the_selected_live_drawer(self) -> None:
        with tempfile.TemporaryDirectory(prefix="agent-todo-complete-", dir=ROOT) as name:
            directory = Path(name)
            path = directory / "note.org"
            relative_path = path.relative_to(ROOT)
            body = "Completed test task."
            path.write_text(
                f"#+title: Test\n:AGENT_TODO:\n{body}\n:END:\nDurable result.\n",
                encoding="utf-8",
            )
            value = "\0".join((relative_path.as_posix(), body))
            fingerprint = hashlib.sha256(value.encode("utf-8")).hexdigest()

            subprocess.run(
                [str(INFRA / "bin" / "agent-todos"), "complete", fingerprint],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            )

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "#+title: Test\nDurable result.\n",
            )

    def test_policy_exposes_risk_and_completion_boundaries(self) -> None:
        result = subprocess.run(
            [str(INFRA / "bin" / "agent-todos"), "policy"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        self.assertIn("action\tedit_note\tautonomous", result.stdout)
        self.assertIn("action\timport_source\thuman_approval", result.stdout)
        self.assertIn("completion\trepository_validation_passes", result.stdout)


if __name__ == "__main__":
    unittest.main()
