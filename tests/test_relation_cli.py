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
                "informed_by\tarquitectura/Elementos constructivos/Bovedas.org\t4",
                "informed_by\tarquitectura/Elementos constructivos/Escaleras.org\t4",
                "informed_by\tarquitectura/Elementos constructivos/Soportes.org\t4",
            },
        )


if __name__ == "__main__":
    unittest.main()
