from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


INFRA = Path(__file__).resolve().parents[1]
ROOT = INFRA.parent
sys.path.insert(0, str(INFRA / "python"))

from episteme_org import legacy_relations as build_relations
from episteme_org import snapshot as export_snapshot


class OrgSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write(self, relative_path: str, content: str) -> None:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_snapshot_is_deterministic_unicode_and_identifier_compatible(self) -> None:
        self.write(
            "zeta/gráfica.org",
            """:PROPERTIES:
:ID: nōte-id
:END:
#+title: Gráfica
:RELATIONS:
- informed-by :: [cite:@fuenteClave]
:END:
Texto [cite:@otraClave p. 7].
* Acción
:AGENT_TODO:
Revisar [cite:@borradorClave p. 8].
:END:
""",
        )
        self.write("alpha/plain.org", "#+title: Excluded\n")
        self.write(
            "alpha/new.org", ":AGENT_TODO:\nAñadir vídeo\n:END:\n"
        )

        first = export_snapshot.build_snapshot(self.root)
        second = export_snapshot.build_snapshot(self.root)
        rendered = export_snapshot.render_snapshot(first)

        self.assertEqual(first, second)
        self.assertEqual(json.loads(rendered), first)
        self.assertIn("gráfica.org", rendered)
        self.assertIn("Añadir vídeo", rendered)
        self.assertNotIn("\\u", rendered)
        self.assertEqual(first["schema_version"], 1)
        self.assertEqual(
            [document["path"] for document in first["documents"]],
            ["alpha/new.org", "zeta/gráfica.org"],
        )

        graph = first["documents"][1]
        relation = graph["relations"][0]
        citation = graph["citations"][0]
        expected_relation = build_relations.RelationFact(
            "nōte-id", "zeta/gráfica.org", 6, "informed_by", "source", "fuenteClave"
        ).identifier
        expected_citation = build_relations.CitationOccurrence(
            "nōte-id", "zeta/gráfica.org", 8, 13, "otraClave", "p. 7"
        ).identifier
        expected_citation_relation = build_relations.RelationFact(
            "nōte-id", "zeta/gráfica.org", 8, "cites", "source", "otraClave"
        ).identifier
        self.assertEqual(relation["id"], expected_relation)
        self.assertEqual(citation["id"], expected_citation)
        self.assertEqual(citation["relation_id"], expected_citation_relation)
        self.assertEqual(graph["context"], "zeta")
        self.assertEqual(graph["todos"][0]["heading_path"], ["Acción"])
        self.assertEqual(
            [hint["key"] for hint in graph["todos"][0]["citation_hints"]],
            ["borradorClave"],
        )
        self.assertEqual([citation["key"] for citation in graph["citations"]], ["otraClave"])
        self.assertIsNone(first["documents"][0]["file_id"])

    def test_snapshot_includes_integrity_issues(self) -> None:
        self.write("broken.org", "[[file:missing.org][Missing]]\n")

        snapshot = export_snapshot.build_snapshot(self.root)

        self.assertEqual(snapshot["documents"], [])
        self.assertEqual(snapshot["issues"][0]["severity"], "ERROR")
        self.assertIn("missing file target", snapshot["issues"][0]["message"])

    def test_cli_emits_snapshot_and_fails_on_integrity_error(self) -> None:
        self.write("broken.org", "[[file:missing.org][Missing]]\n")

        result = subprocess.run(
            [
                sys.executable,
                str(INFRA / "bin" / "export-org-snapshot"),
                "--root",
                str(self.root),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        snapshot = json.loads(result.stdout)
        self.assertEqual(snapshot["schema_version"], 1)
        self.assertEqual(snapshot["issues"][0]["severity"], "ERROR")


if __name__ == "__main__":
    unittest.main()
