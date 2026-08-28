from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("check_integrity", ROOT / "bin" / "check-integrity.py")
assert SPEC is not None and SPEC.loader is not None
check_integrity = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = check_integrity
SPEC.loader.exec_module(check_integrity)


class IntegrityCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write(self, relative_path: str, content: str) -> None:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_valid_tree_and_optional_ids(self) -> None:
        self.write("setup.org", "#+LATEX_HEADER: test\n")
        self.write(
            "domain/a.org",
            """:PROPERTIES:
:ID: a
:ROAM_ALIASES: "first note"
:END:
#+title: A
#+SETUPFILE: ../setup.org
[[id:b][B]]
[[file:b.org][B file]]
""",
        )
        self.write(
            "domain/b.org",
            """:PROPERTIES:
:ID: b
:END:
#+title: B
""",
        )
        self.write("course/outline.org", "#+title: Outline\n")

        self.assertEqual(check_integrity.check_repository(self.root), [])

    def test_idless_link_target_is_informational(self) -> None:
        self.write("index.org", "#+title: Index\n[[file:notes/topic.org][Topic]]\n")
        self.write("notes/topic.org", "#+title: Topic\n")

        issues = check_integrity.check_repository(self.root)

        self.assertEqual([issue.severity for issue in issues], ["INFO"])
        self.assertIn("consider promoting", issues[0].message)

    def test_identity_and_alias_errors(self) -> None:
        self.write(
            "a.org",
            """:PROPERTIES:
:ID: duplicate
:END:
#+title: A
aliases: - obsolete
[[id:missing][Missing]]
""",
        )
        self.write(
            "b.org",
            """:PROPERTIES:
:ID: duplicate
:END:
#+title: B
* Heading
:PROPERTIES:
:ROAM_ALIASES: "no identity"
:END:
""",
        )

        messages = [issue.message for issue in check_integrity.check_repository(self.root)]

        self.assertEqual(sum(message.startswith("duplicate ID") for message in messages), 2)
        self.assertTrue(any("Obsidian alias syntax" in message for message in messages))
        self.assertTrue(any("unresolved id link" in message for message in messages))
        self.assertTrue(any("requires an :ID:" in message for message in messages))

    def test_missing_files_and_malformed_file_prefix(self) -> None:
        self.write(
            "note.org",
            """#+title: Note
#+SETUPFILE: missing-setup.org
[[file:missing.org][Missing]]
[[file:file:other.org][Malformed]]
""",
        )

        messages = [issue.message for issue in check_integrity.check_repository(self.root)]

        self.assertTrue(any("missing SETUPFILE" in message for message in messages))
        self.assertTrue(any("missing file target" in message for message in messages))
        self.assertTrue(any("duplicated file: prefix" in message for message in messages))

    def test_file_target_case_must_match_on_case_insensitive_filesystems(self) -> None:
        self.write("Target.org", "#+title: Target\n")
        self.write("note.org", "[[file:target.org][Target]]\n")

        messages = [issue.message for issue in check_integrity.check_repository(self.root)]

        self.assertIn("missing file target: target.org", messages)

    def test_literal_examples_are_not_checked_as_live_links(self) -> None:
        self.write(
            "README.org",
            """#+title: README
=[[file:not-real.org]]= and ~[[id:not-real][example]]~
#+begin_src org
aliases: - example
[[file:also-not-real.org]]
#+end_src
""",
        )

        self.assertEqual(check_integrity.check_repository(self.root), [])

    def test_deferred_legacy_zotero_template_is_excluded(self) -> None:
        self.write(
            ".literature-notes/templates/zotero.org",
            "aliases: - legacy\n[[file:missing.org][Generated placeholder]]\n",
        )

        self.assertEqual(check_integrity.check_repository(self.root), [])


if __name__ == "__main__":
    unittest.main()
