from __future__ import annotations

import contextlib
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_relations", ROOT / "bin" / "build-relations.py"
)
assert SPEC is not None and SPEC.loader is not None
build_relations = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = build_relations
SPEC.loader.exec_module(build_relations)


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

    def test_generates_relation_and_citation_facts_with_two_indexes(self) -> None:
        self.write(
            "notes/O'Brien.org",
            """#+title: Note
:RELATIONS:
- informed-by :: [cite:@source&Key]
:END:
Direct [cite:@otherKey p. 2].
""",
        )

        facts, citations, issues = build_relations.relation_facts(self.root)
        rendered = build_relations.render_module(facts, citations)

        self.assertEqual(issues, [])
        self.assertEqual(len(facts), 2)
        self.assertEqual(len(citations), 1)
        self.assertIn("informed_by, source('source&Key')", rendered)
        self.assertIn("cites, source('otherKey')", rendered)
        self.assertIn("note('notes/O\\'Brien.org')", rendered)
        self.assertEqual(rendered.count("asserted("), 2)
        self.assertEqual(rendered.count("\nfrom_index("), 2)
        self.assertEqual(rendered.count("\nto_index("), 2)
        self.assertIn("locator('p. 2')", rendered)
        self.assertIn("org('notes/O\\'Brien.org', 5, 14)", rendered)
        self.assertEqual(rendered.count("asserted_citation("), 1)
        self.assertEqual(rendered.count("citation_from_index("), 1)
        self.assertEqual(rendered.count("citation_to_index("), 1)

    def test_generation_refuses_malformed_relations_without_replacing_output(self) -> None:
        self.write(
            "note.org",
            """#+title: Note
:RELATIONS:
not a relation
:END:
""",
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
            "#+title: Note\n[cite:@sourceKey p. 2] and [cite:@sourceKey p. 9].\n",
        )

        facts, citations, issues = build_relations.relation_facts(self.root)

        self.assertEqual(issues, [])
        self.assertEqual(len(facts), 1)
        self.assertEqual(
            [(citation.locator, citation.column) for citation in citations],
            [("p. 2", 7), ("p. 9", 34)],
        )

    def test_authored_locator_values_do_not_collide_with_missing_locator(self) -> None:
        self.write(
            "note.org",
            "#+title: Note\n[cite:@first none] [cite:@second -] [cite:@third]\n",
        )

        facts, citations, issues = build_relations.relation_facts(self.root)
        rendered = build_relations.render_module(facts, citations)

        self.assertEqual(issues, [])
        self.assertIn("locator('none')", rendered)
        self.assertIn("locator('-')", rendered)
        self.assertIn("source('third'), no_locator", rendered)

    def test_concurrent_generation_uses_independent_temporary_files(self) -> None:
        self.write("note.org", "#+title: Note\n[cite:@sourceKey p. 2]\n")
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


if __name__ == "__main__":
    unittest.main()
