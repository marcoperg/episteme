from __future__ import annotations

import contextlib
import importlib.util
import io
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

        facts, issues = build_relations.relation_facts(self.root)
        rendered = build_relations.render_module(facts)

        self.assertEqual(issues, [])
        self.assertEqual(len(facts), 2)
        self.assertIn("informed_by, source('source&Key')", rendered)
        self.assertIn("cites, source('otherKey')", rendered)
        self.assertIn("note('notes/O\\'Brien.org')", rendered)
        self.assertEqual(rendered.count("asserted("), 2)
        self.assertEqual(rendered.count("from_index("), 2)
        self.assertEqual(rendered.count("to_index("), 2)

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


if __name__ == "__main__":
    unittest.main()
