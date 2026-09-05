"""Export the parsed Episteme Org graph and agent tasks as deterministic JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from . import integrity

ROOT = Path(__file__).resolve().parents[3]


def _relation_identifier(
    note_id: str, line: int, predicate: str, target_kind: str, target: str
) -> str:
    value = f"{note_id}\0{line}\0{predicate}\0{target_kind}\0{target}"
    return "relation_" + hashlib.sha256(value.encode()).hexdigest()[:16]


def _citation_identifier(
    note_id: str, line: int, column: int, key: str, locator: str | None
) -> str:
    value = f"{note_id}\0{line}\0{column}\0{key}\0{locator or ''}"
    return "citation_" + hashlib.sha256(value.encode()).hexdigest()[:16]


def build_snapshot(root: Path, bibliography: Path | None = None) -> dict[str, object]:
    """Return schema version 1 using the integrity checker's single Org parser."""
    root = root.expanduser().resolve()
    parsed = integrity.parse_repository(root)
    documents, _ = parsed
    issues = integrity.check_repository(root, bibliography, parsed)
    exported_documents = []
    for document in documents:
        if not document.relations and not document.citations and not document.todos:
            continue
        note_id = document.file_id.value if document.file_id is not None else None
        relations = []
        for relation in document.relations:
            predicate = relation.predicate.replace("-", "_")
            relations.append(
                {
                    "id": (
                        _relation_identifier(
                            note_id, relation.line, predicate, "source", relation.target
                        )
                        if note_id is not None
                        else None
                    ),
                    "line": relation.line,
                    "predicate": predicate,
                    "target": relation.target,
                    "target_kind": "source",
                }
            )
        citations = []
        for citation in document.citations:
            citations.append(
                {
                    "column": citation.column,
                    "id": (
                        _citation_identifier(
                            note_id,
                            citation.line,
                            citation.column,
                            citation.key,
                            citation.locator,
                        )
                        if note_id is not None
                        else None
                    ),
                    "key": citation.key,
                    "line": citation.line,
                    "locator": citation.locator,
                    "relation_id": (
                        _relation_identifier(
                            note_id, citation.line, "cites", "source", citation.key
                        )
                        if note_id is not None
                        else None
                    ),
                }
            )
        todos = [
            {
                "body": todo.body,
                "citation_hints": [
                    {
                        "column": citation.column,
                        "key": citation.key,
                        "line": citation.line,
                        "locator": citation.locator,
                    }
                    for citation in todo.citation_hints
                ],
                "end_line": todo.end_line,
                "fingerprint": todo.fingerprint,
                "heading_path": list(todo.heading_path),
                "path": todo.path.as_posix(),
                "start_line": todo.start_line,
            }
            for todo in document.todos
        ]
        exported_documents.append(
            {
                "citations": citations,
                "context": document.relative_path.parent.as_posix(),
                "file_id": note_id,
                "path": document.relative_path.as_posix(),
                "relations": relations,
                "todos": todos,
            }
        )
    return {
        "documents": exported_documents,
        "issues": [
            {
                "line": issue.line,
                "message": issue.message,
                "path": issue.path.as_posix(),
                "severity": issue.severity,
            }
            for issue in issues
        ],
        "schema_version": 1,
    }


def render_snapshot(snapshot: dict[str, object]) -> str:
    return json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Episteme repository root")
    parser.add_argument("--bibliography", type=Path, help="BibTeX file used to resolve citations")
    args = parser.parse_args(argv)
    if not args.root.expanduser().is_dir():
        parser.error(f"repository root does not exist: {args.root}")
    if args.bibliography is not None and not args.bibliography.expanduser().is_file():
        parser.error(f"bibliography does not exist: {args.bibliography}")

    snapshot = build_snapshot(args.root, args.bibliography)
    print(render_snapshot(snapshot))
    return 1 if any(
        issue["severity"] == "ERROR" for issue in snapshot["issues"]
    ) else 0


if __name__ == "__main__":
    sys.exit(main())
