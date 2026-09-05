from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


INFRA = Path(__file__).resolve().parents[1]
ROOT = INFRA.parent
sys.path.insert(0, str(INFRA / "python"))

from episteme_org import integrity as check_integrity


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

    def test_informed_by_relation_resolves_against_bibliography(self) -> None:
        self.write(
            "note.org",
            """:PROPERTIES:
:ID: note-id
:END:
#+title: Note
:RELATIONS:
- informed-by :: [cite:@sourceKey]
:END:
""",
        )
        self.write("library.bib", "@book{sourceKey,\n  title = {Source}\n}\n")

        self.assertEqual(
            check_integrity.check_repository(self.root, self.root / "library.bib"),
            [],
        )

    def test_informed_by_relation_does_not_require_sibling_bibliography(self) -> None:
        self.write(
            "note.org",
            """:PROPERTIES:
:ID: note-id
:END:
#+title: Note
:RELATIONS:
- informed-by :: [cite:@sourceKey]
:END:
""",
        )

        self.assertEqual(check_integrity.check_repository(self.root), [])

    def test_direct_citations_are_collected_outside_relations_and_examples(self) -> None:
        self.write(
            "note.org",
            """#+title: Note
:RELATIONS:
- informed-by :: [cite:@sourceKey]
:END:
Text [cite:@firstKey p. 3; @secondKey].
[cite/t:@thirdKey]
#+begin_src org
[cite:@exampleKey]
#+end_src
""",
        )

        documents, issues = check_integrity.parse_repository(self.root)

        self.assertEqual(issues, [])
        self.assertEqual(
            [
                (citation.key, citation.locator, citation.line, citation.column)
                for citation in documents[0].citations
            ],
            [
                ("firstKey", "p. 3", 5, 12),
                ("secondKey", None, 5, 28),
                ("thirdKey", None, 6, 9),
            ],
        )

    def test_citations_inside_comment_blocks_are_not_collected(self) -> None:
        self.write(
            "note.org",
            """#+title: Note
#+begin_comment
[cite:@commentedKey p. 2]
#+end_comment
Text [cite:@liveKey p. 3].
""",
        )

        documents, issues = check_integrity.parse_repository(self.root)

        self.assertEqual(issues, [])
        self.assertEqual(
            [(citation.key, citation.locator) for citation in documents[0].citations],
            [("liveKey", "p. 3")],
        )

    def test_non_org_citations_are_not_collected(self) -> None:
        self.write(
            "note.org",
            """#+title: Note
:PROPERTIES:
:CUSTOM: [cite:@propertyKey]
:END:
:LOGBOOK:
[cite:@drawerKey]
:END:
: [cite:@fixedWidthKey]
* TODO COMMENT Disabled
[cite:@commentSubtreeKey]
** Child
[cite:@commentChildKey]
* Live
[cite:@liveKey]
""",
        )

        documents, issues = check_integrity.parse_repository(self.root)

        self.assertEqual(issues, [])
        self.assertEqual(
            [citation.key for citation in documents[0].citations],
            ["liveKey"],
        )

    def test_agent_todo_preserves_body_scope_and_provisional_citations(self) -> None:
        content = """:PROPERTIES:
:ID: note-id
:END:
#+title: Note
* Parent
** Niño
:AGENT_TODO:
Keep  spacing and café [cite:@draftKey pp. 2-3].
:END:
Durable [cite:@liveKey p. 9].
:LOGBOOK:
[cite:@hiddenKey]
:END:
"""
        self.write("inbox/note.org", content)

        documents, issues = check_integrity.parse_repository(self.root)

        self.assertEqual(issues, [])
        todo = documents[0].todos[0]
        self.assertEqual(todo.path, Path("inbox/note.org"))
        self.assertEqual(todo.heading_path, ("Parent", "Niño"))
        self.assertEqual(todo.start_line, 7)
        self.assertEqual(todo.end_line, 9)
        self.assertEqual(
            todo.body,
            "Keep  spacing and café [cite:@draftKey pp. 2-3].",
        )
        self.assertEqual(
            [(citation.key, citation.locator) for citation in todo.citation_hints],
            [("draftKey", "pp. 2-3")],
        )
        self.assertEqual(
            [citation.key for citation in documents[0].citations], ["liveKey"]
        )

        fingerprint = todo.fingerprint
        self.write("inbox/note.org", "\n\n" + content)
        shifted_documents, _ = check_integrity.parse_repository(self.root)
        self.assertEqual(shifted_documents[0].todos[0].fingerprint, fingerprint)
        self.assertEqual(shifted_documents[0].todos[0].start_line, 9)

    def test_only_exact_live_agent_todo_drawers_are_exposed(self) -> None:
        self.write(
            "note.org",
            """#+title: Note
:AGENT_TODO_ARCHIVE:
[cite:@archiveKey]
:END:
* COMMENT Hidden
:AGENT_TODO:
[cite:@commentKey]
:END:
* Live
:agent_todo:
task
:END:
""",
        )

        documents, issues = check_integrity.parse_repository(self.root)

        self.assertEqual(
            [issue.message for issue in issues],
            ["agent task drawer must use exact uppercase :AGENT_TODO:"],
        )
        self.assertEqual(documents[0].todos, [])
        self.assertEqual(documents[0].citations, [])

    def test_agent_todo_structure_is_validated(self) -> None:
        self.write(
            "note.org",
            """#+title: Note
:AGENT_TODO:
:END:
* Scope
:AGENT_TODO:
** Nested heading
#+begin_src org
example
#+end_src
:LOGBOOK:
:END:
:AGENT_TODO:
duplicate
:END:
""",
        )

        _, issues = check_integrity.parse_repository(self.root)
        messages = [issue.message for issue in issues]

        self.assertIn("empty AGENT_TODO drawer", messages)
        self.assertIn("AGENT_TODO drawer must not contain Org headings", messages)
        self.assertIn("AGENT_TODO drawer must not contain literal blocks", messages)
        self.assertIn("AGENT_TODO drawer must not contain nested drawers", messages)
        self.assertTrue(any(message.startswith("duplicate AGENT_TODO") for message in messages))

    def test_parse_repository_includes_filesystem_todos(self) -> None:
        self.write("new/untracked.org", ":AGENT_TODO:\nnew task\n:END:\n")

        documents, issues = check_integrity.parse_repository(self.root)

        self.assertEqual(issues, [])
        self.assertEqual(
            [(document.relative_path.as_posix(), len(document.todos)) for document in documents],
            [("new/untracked.org", 1)],
        )

    def test_parse_repository_excludes_infra_and_git_but_scans_hidden_paths(self) -> None:
        self.write("infra/ignored.org", "[[file:missing.org]]\n")
        self.write(".git/ignored.org", "[[file:missing.org]]\n")
        self.write(".hidden/included.org", "#+title: Hidden\n")

        documents, issues = check_integrity.parse_repository(self.root)

        self.assertEqual(issues, [])
        self.assertEqual(
            [document.relative_path.as_posix() for document in documents],
            [".hidden/included.org"],
        )

    def test_unclosed_generic_drawer_is_an_error(self) -> None:
        self.write("note.org", "#+title: Note\n:LOGBOOK:\n[cite:@hiddenKey]\n")

        messages = [
            issue.message for issue in check_integrity.check_repository(self.root)
        ]

        self.assertIn("unclosed Org drawer", messages)

    def test_direct_citation_key_resolves_against_bibliography(self) -> None:
        self.write(
            "note.org",
            ":PROPERTIES:\n:ID: note-id\n:END:\n"
            "#+title: Note\nText [cite:@missingKey p. 3].\n",
        )
        self.write("library.bib", "@book{otherKey,\n  title = {Other}\n}\n")

        messages = [
            issue.message
            for issue in check_integrity.check_repository(
                self.root, self.root / "library.bib"
            )
        ]

        self.assertIn("unresolved citation key: missingKey", messages)

    def test_relation_errors(self) -> None:
        self.write(
            "note.org",
            """:PROPERTIES:
:ID: note-id
:END:
#+title: Note
:RELATIONS:
- related-to :: [cite:@sourceKey]
- informed-by :: [cite:@missingKey]
- informed-by :: [cite:@sourceKey; @secondKey]
not a relation
:END:
""",
        )
        self.write("library.bib", "@book{sourceKey,\n  title = {Source}\n}\n")

        messages = [
            issue.message
            for issue in check_integrity.check_repository(self.root, self.root / "library.bib")
        ]

        self.assertIn("unknown relation predicate: related-to", messages)
        self.assertIn("unresolved informed-by citation key: missingKey", messages)
        self.assertTrue(any("must be exactly one Org citation" in message for message in messages))
        self.assertTrue(any("malformed relation" in message for message in messages))

    def test_graph_notes_require_a_file_level_id(self) -> None:
        self.write("note.org", "#+title: Note\nText [cite:@sourceKey].\n")

        messages = [
            issue.message for issue in check_integrity.check_repository(self.root)
        ]

        self.assertIn(
            "notes with relations or citations require a file-level :ID:",
            messages,
        )

    def test_file_has_only_one_file_level_id(self) -> None:
        self.write(
            "note.org",
            """:PROPERTIES:
:ID: first
:ID: second
:END:
#+title: Note
[cite:@sourceKey]
""",
        )

        messages = [
            issue.message for issue in check_integrity.check_repository(self.root)
        ]

        self.assertIn("file must have exactly one file-level :ID:", messages)

    def test_separate_file_property_drawers_do_not_select_an_id(self) -> None:
        self.write(
            "note.org",
            """:PROPERTIES:
:ID: first
:END:
#+title: Note
:PROPERTIES:
:ID: second
:END:
[cite:@sourceKey]
""",
        )

        documents, parse_issues = check_integrity.parse_repository(self.root)

        self.assertIn(
            "file must have exactly one file-level :ID:",
            [issue.message for issue in parse_issues],
        )
        self.assertIsNone(documents[0].file_id)

    def test_empty_file_id_is_not_selected(self) -> None:
        self.write(
            "note.org",
            ":PROPERTIES:\n:ID:\n:END:\n#+title: Note\n[cite:@sourceKey]\n",
        )

        documents, _ = check_integrity.parse_repository(self.root)

        self.assertIsNone(documents[0].file_id)

    def test_unclosed_relations_drawer(self) -> None:
        self.write(
            "note.org",
            """#+title: Note
:RELATIONS:
- informed-by :: [cite:@sourceKey]
""",
        )

        messages = [issue.message for issue in check_integrity.check_repository(self.root)]

        self.assertIn("unclosed relations drawer", messages)

    def test_relations_drawer_must_be_file_level(self) -> None:
        self.write(
            "note.org",
            """#+title: Note
* Section
:RELATIONS:
- informed-by :: [cite:@sourceKey]
:END:
""",
        )

        messages = [issue.message for issue in check_integrity.check_repository(self.root)]

        self.assertIn("relations drawer must be file-level", messages)


if __name__ == "__main__":
    unittest.main()
