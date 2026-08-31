from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("ciao-shell"), "Ciao is not installed")
class RelationCliTests(unittest.TestCase):
    def test_runtime_distinguishes_incoming_traversal_from_semantic_inverse(self) -> None:
        subprocess.run(
            ["ciao-shell", str(ROOT / "tests" / "check_relation_semantics.pl")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

    def test_reference_query_returns_all_informed_architecture_notes(self) -> None:
        result = subprocess.run(
            [
                str(ROOT / "bin" / "query-relations"),
                "references",
                "muller&vogelMullerVogelAtlas1995",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        self.assertEqual(
            set(result.stdout.splitlines()),
            {
                "informed_by\tarquitectura/Elementos constructivos/Bovedas.org\t7\t1\t",
                "informed_by\tarquitectura/Elementos constructivos/Escaleras.org\t7\t1\t",
                "informed_by\tarquitectura/Elementos constructivos/Soportes.org\t7\t1\t",
            },
        )

    def test_reference_query_preserves_individual_citation_locations(self) -> None:
        result = subprocess.run(
            [
                str(ROOT / "bin" / "query-relations"),
                "references",
                "inestaOptimalEntanglementDistribution2023",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        self.assertEqual(
            set(result.stdout.splitlines()),
            {
                "cites\tGIICC/Entanglement Management System.org\t12\t184\t",
                "cites\tGIICC/Preguntas QIA.org\t7\t17\t",
            },
        )


if __name__ == "__main__":
    unittest.main()
