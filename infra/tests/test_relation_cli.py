from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


INFRA = Path(__file__).resolve().parents[1]
ROOT = INFRA.parent


@unittest.skipUnless(shutil.which("ciao-shell"), "Ciao is not installed")
class RelationCliTests(unittest.TestCase):
    def write(self, root: Path, relative_path: str, content: str) -> None:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_reference_query_does_not_rebuild_generated_facts(self) -> None:
        generated = INFRA / "ciao" / "relations" / "generated" / "relation_facts.pl"
        before = generated.stat().st_mtime_ns if generated.exists() else None

        subprocess.run(
            [
                str(INFRA / "bin" / "query-relations"),
                "references",
                "muller&vogelMullerVogelAtlas1995",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        after = generated.stat().st_mtime_ns if generated.exists() else None
        self.assertEqual(after, before)

    def test_runtime_distinguishes_incoming_traversal_from_semantic_inverse(self) -> None:
        subprocess.run(
            ["ciao-shell", str(INFRA / "tests" / "check_relation_semantics.pl")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

    def test_reference_query_returns_all_informed_architecture_notes(self) -> None:
        result = subprocess.run(
            [
                str(INFRA / "bin" / "query-relations"),
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
                str(INFRA / "bin" / "query-relations"),
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

    def test_context_relations_are_inherited_with_authored_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "infra").symlink_to(INFRA, target_is_directory=True)
            self.write(
                root,
                "course/README.org",
                """:PROPERTIES:
:ID: readme-id
:END:
#+title: Course
:RELATIONS:
- informed-by :: [cite:@readmeSource]
:END:
:CONTEXT_RELATIONS:
- informed-by :: [cite:@courseSource]
:END:
""",
            )
            self.write(
                root,
                "course/topic.org",
                ":PROPERTIES:\n:ID: topic-id\n:END:\n#+title: Topic\n",
            )
            self.write(
                root,
                "course/nested/README.org",
                """#+title: Nested
:CONTEXT_RELATIONS:
- informed-by :: [cite:@nestedSource]
:END:
""",
            )
            self.write(
                root,
                "course/nested/topic.org",
                ":PROPERTIES:\n:ID: nested-id\n:END:\n#+title: Nested topic\n",
            )

            subprocess.run(
                [
                    "ciao-shell",
                    str(INFRA / "tests" / "check_inherited_relation_semantics.pl"),
                    str(root),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            result = subprocess.run(
                [
                    str(root / "infra" / "bin" / "query-relations"),
                    "references",
                    "courseSource",
                ],
                cwd=root,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(
                result.stdout.splitlines(),
                ["informed_by\tcourse/README.org\t9\t1\t"],
            )


if __name__ == "__main__":
    unittest.main()
