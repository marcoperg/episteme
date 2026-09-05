from __future__ import annotations

import contextlib
from concurrent.futures import ThreadPoolExecutor
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest


INFRA = Path(__file__).resolve().parents[1]
ROOT = INFRA.parent
sys.path.insert(0, str(INFRA / "python"))

from episteme_org import legacy_relations as build_relations


class RelationBuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write(self, relative_path: str, content: str) -> None:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def graph_note(self, content: str, identifier: str = "note-id") -> str:
        return (
            ":PROPERTIES:\n"
            f":ID: {identifier}\n"
            ":END:\n"
            f"{content}"
        )

    def test_generates_relation_and_citation_facts_with_two_indexes(self) -> None:
        self.write(
            "notes/O'Brien.org",
            self.graph_note("""#+title: Note
:RELATIONS:
- informed-by :: [cite:@source&Key]
:END:
Direct [cite:@otherKey p. 2].
"""),
        )

        notes, facts, citations, issues = build_relations.relation_facts(self.root)
        rendered = build_relations.render_module(notes, facts, citations)

        self.assertEqual(issues, [])
        self.assertEqual(len(notes), 1)
        self.assertEqual(len(facts), 2)
        self.assertEqual(len(citations), 1)
        self.assertIn("informed_by, source('source&Key')", rendered)
        self.assertIn("cites, source('otherKey')", rendered)
        self.assertIn("note('note-id')", rendered)
        self.assertIn(
            "note_index(note('note-id'), 'notes/O\\'Brien.org', context('notes'))",
            rendered,
        )
        self.assertIn("context_parent_index(context('notes'), context('.'))", rendered)
        self.assertEqual(rendered.count("asserted("), 2)
        self.assertEqual(rendered.count("\nfrom_index("), 2)
        self.assertEqual(rendered.count("\nto_index("), 2)
        self.assertIn("locator('p. 2')", rendered)
        self.assertIn("org('notes/O\\'Brien.org', 8, 14)", rendered)
        self.assertEqual(rendered.count("asserted_citation("), 1)
        self.assertEqual(rendered.count("citation_from_index("), 1)
        self.assertEqual(rendered.count("citation_to_index("), 1)

    def test_generation_refuses_malformed_relations_without_replacing_output(self) -> None:
        self.write(
            "note.org",
            self.graph_note("""#+title: Note
:RELATIONS:
not a relation
:END:
"""),
        )
        output = self.root / "facts.pl"
        output.write_text("existing\n", encoding="utf-8")

        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            result = build_relations.main(
                ["--root", str(self.root), "--output", str(output), "--quiet"]
            )

        self.assertEqual(result, 1)
        self.assertIn("malformed relation", errors.getvalue())
        self.assertEqual(output.read_text(encoding="utf-8"), "existing\n")

    def test_generation_refuses_broken_file_links(self) -> None:
        self.write("note.org", "#+title: Note\n[[file:missing.org][Missing]]\n")
        output = self.root / "facts.pl"

        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            result = build_relations.main(
                ["--root", str(self.root), "--output", str(output), "--quiet"]
            )

        self.assertEqual(result, 1)
        self.assertIn("missing file target", errors.getvalue())
        self.assertFalse(output.exists())

    def test_repeated_citations_keep_distinct_occurrences(self) -> None:
        self.write(
            "note.org",
            self.graph_note(
                "#+title: Note\n[cite:@sourceKey p. 2] and [cite:@sourceKey p. 9].\n"
            ),
        )

        notes, facts, citations, issues = build_relations.relation_facts(self.root)

        self.assertEqual(issues, [])
        self.assertEqual([note.identifier for note in notes], ["note-id"])
        self.assertEqual(len(facts), 1)
        self.assertEqual(
            [(citation.locator, citation.column) for citation in citations],
            [("p. 2", 7), ("p. 9", 34)],
        )

    def test_authored_locator_values_do_not_collide_with_missing_locator(self) -> None:
        self.write(
            "note.org",
            self.graph_note(
                "#+title: Note\n[cite:@first none] [cite:@second -] [cite:@third]\n"
            ),
        )

        notes, facts, citations, issues = build_relations.relation_facts(self.root)
        rendered = build_relations.render_module(notes, facts, citations)

        self.assertEqual(issues, [])
        self.assertIn("locator('none')", rendered)
        self.assertIn("locator('-')", rendered)
        self.assertIn("source('third'), no_locator", rendered)
        self.assertIn(
            "note_index(note('note-id'), 'note.org', context('.'))", rendered
        )

    def test_concurrent_generation_uses_independent_temporary_files(self) -> None:
        self.write(
            "note.org",
            self.graph_note("#+title: Note\n[cite:@sourceKey p. 2]\n"),
        )
        output = self.root / "facts.pl"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    lambda _: build_relations.main(
                        ["--root", str(self.root), "--output", str(output), "--quiet"]
                    ),
                    range(2),
                )
            )

        self.assertEqual(results, [0, 0])
        self.assertIn("asserted_citation(", output.read_text(encoding="utf-8"))
        self.assertEqual(os.stat(output).st_mode & 0o777, 0o644)

    def test_generation_refuses_graph_note_without_file_id(self) -> None:
        self.write("note.org", "#+title: Note\n[cite:@sourceKey]\n")
        output = self.root / "facts.pl"

        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            result = build_relations.main(
                ["--root", str(self.root), "--output", str(output), "--quiet"]
            )

        self.assertEqual(result, 1)
        self.assertIn("require a file-level :ID:", errors.getvalue())
        self.assertFalse(output.exists())

    def test_file_move_changes_context_without_changing_note_identity(self) -> None:
        self.write(
            "first/note.org",
            self.graph_note("#+title: Note\n[cite:@sourceKey p. 2]\n"),
        )
        before_notes, before_facts, before_citations, before_issues = (
            build_relations.relation_facts(self.root)
        )
        (self.root / "second").mkdir()
        (self.root / "first" / "note.org").rename(
            self.root / "second" / "note.org"
        )

        after_notes, after_facts, after_citations, after_issues = (
            build_relations.relation_facts(self.root)
        )

        self.assertEqual(before_issues, [])
        self.assertEqual(after_issues, [])
        self.assertEqual(before_notes[0].identifier, after_notes[0].identifier)
        self.assertEqual((before_notes[0].path, before_notes[0].context),
                         ("first/note.org", "first"))
        self.assertEqual((after_notes[0].path, after_notes[0].context),
                         ("second/note.org", "second"))
        self.assertEqual(before_facts[0].identifier, after_facts[0].identifier)
        self.assertEqual(
            before_citations[0].identifier, after_citations[0].identifier
        )


if __name__ == "__main__":
    unittest.main()
