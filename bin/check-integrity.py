#!/usr/bin/env python3
"""Check structural integrity of the Episteme Org repository."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit


ID_LINK_RE = re.compile(r"\[\[id:([^\]\s]+)")
FILE_LINK_RE = re.compile(r"\[\[file:([^\]\n]+)")
SETUPFILE_RE = re.compile(r"^#\+SETUPFILE:\s*(.+?)\s*$", re.IGNORECASE)
PROPERTY_RE = re.compile(r"^\s*:([A-Za-z0-9_]+):\s*(.*?)\s*$")
BROKEN_ALIAS_RE = re.compile(r"^\s*(?:aliases?\s*:|\*+\s+aliases?\s*:)", re.IGNORECASE)
HEADING_CONTENT_RE = re.compile(r"^(?P<stars>\*+)\s+(?P<title>.*)$")
COMMENT_HEADING_RE = re.compile(
    r"^(?:[A-Z][A-Z0-9_-]*\s+)?(?:\[#[A-Z0-9]\]\s+)?COMMENT(?:\s|$)"
)
DRAWER_RE = re.compile(r"^:([A-Za-z][A-Za-z0-9_-]*):$")
FIXED_WIDTH_RE = re.compile(r"^\s*:(?:\s|$)")
BEGIN_LITERAL_BLOCK_RE = re.compile(
    r"^#\+begin_(?:src|example|export|verbatim|comment)\b", re.IGNORECASE
)
END_LITERAL_BLOCK_RE = re.compile(
    r"^#\+end_(?:src|example|export|verbatim|comment)\b", re.IGNORECASE
)
INLINE_VERBATIM_RE = re.compile(r"(?<!\w)([=~]).*?\1")
RELATION_ITEM_RE = re.compile(r"^\s*-\s+([a-z][a-z0-9-]*)\s+::\s+(.+?)\s*$")
CITATION_TARGET_RE = re.compile(r"^\[cite:@([^\]\s;]+)\]$")
ORG_CITATION_RE = re.compile(r"\[cite(?:/[^\]:\]]+)?(?::[^\]]*)?\]")
ORG_CITATION_REFERENCE_RE = re.compile(
    r"@(?P<key>[^\s;,\]\[]+)(?P<locator>[^;@\]]*)"
)
BIBTEX_ENTRY_RE = re.compile(r"^@[A-Za-z]+\s*\{\s*([^,\s]+)\s*,", re.MULTILINE)
RELATION_PREDICATES = {"informed-by"}


@dataclass(frozen=True)
class LocatedValue:
    value: str
    line: int


@dataclass(frozen=True)
class LocatedRelation:
    predicate: str
    target: str
    line: int


@dataclass(frozen=True)
class LocatedCitation:
    key: str
    locator: str | None
    line: int
    column: int


@dataclass(frozen=True)
class Issue:
    severity: str
    path: Path
    line: int
    message: str


@dataclass
class OrgDocument:
    path: Path
    relative_path: Path
    ids: list[LocatedValue]
    id_links: list[LocatedValue]
    file_links: list[LocatedValue]
    setupfiles: list[LocatedValue]
    relations: list[LocatedRelation]
    citations: list[LocatedCitation]
    has_file_id: bool
    file_id: LocatedValue | None


def _issue(severity: str, document: OrgDocument, line: int, message: str) -> Issue:
    return Issue(severity, document.relative_path, line, message)


def _parse_document(path: Path, root: Path) -> tuple[OrgDocument, list[Issue]]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    document = OrgDocument(
        path=path,
        relative_path=path.relative_to(root),
        ids=[],
        id_links=[],
        file_links=[],
        setupfiles=[],
        relations=[],
        citations=[],
        has_file_id=False,
        file_id=None,
    )
    issues: list[Issue] = []
    drawer_start: int | None = None
    drawer_ids: list[LocatedValue] = []
    drawer_aliases: list[LocatedValue] = []
    relations_drawer_start: int | None = None
    other_drawer_start: int | None = None
    comment_subtree_depth: int | None = None
    file_level_id_count = 0
    seen_heading = False
    in_literal_block = False

    for line_number, line in enumerate(lines, 1):
        stripped = line.strip()
        if BEGIN_LITERAL_BLOCK_RE.match(stripped):
            in_literal_block = True
            continue
        if END_LITERAL_BLOCK_RE.match(stripped):
            in_literal_block = False
            continue
        if in_literal_block:
            continue
        heading_match = HEADING_CONTENT_RE.match(line)
        if heading_match:
            seen_heading = True
            heading_depth = len(heading_match.group("stars"))
            if comment_subtree_depth is not None and heading_depth <= comment_subtree_depth:
                comment_subtree_depth = None
            if COMMENT_HEADING_RE.match(heading_match.group("title")):
                comment_subtree_depth = heading_depth
            if comment_subtree_depth is not None:
                continue
        elif comment_subtree_depth is not None:
            continue

        drawer_match = DRAWER_RE.match(stripped)
        if (
            drawer_match
            and drawer_match.group(1).upper() not in {"PROPERTIES", "RELATIONS", "END"}
            and drawer_start is None
            and relations_drawer_start is None
            and other_drawer_start is None
        ):
            other_drawer_start = line_number
        elif stripped == ":END:" and other_drawer_start is not None:
            other_drawer_start = None

        if stripped == ":PROPERTIES:":
            if drawer_start is not None or relations_drawer_start is not None:
                issues.append(_issue("ERROR", document, line_number, "nested property drawer"))
            drawer_start = line_number
            drawer_ids = []
            drawer_aliases = []
        elif stripped == ":RELATIONS:":
            if drawer_start is not None or relations_drawer_start is not None:
                issues.append(_issue("ERROR", document, line_number, "nested relations drawer"))
            if seen_heading:
                issues.append(_issue("ERROR", document, line_number, "relations drawer must be file-level"))
            relations_drawer_start = line_number
        elif stripped == ":END:" and drawer_start is not None:
            if drawer_aliases and not drawer_ids:
                for alias in drawer_aliases:
                    issues.append(
                        _issue(
                            "ERROR",
                            document,
                            alias.line,
                            ":ROAM_ALIASES: requires an :ID: in the same property drawer",
                        )
                    )
            if drawer_ids and not seen_heading:
                file_level_id_count += len(drawer_ids)
                if file_level_id_count > 1:
                    issues.append(
                        _issue(
                            "ERROR",
                            document,
                            drawer_ids[0].line,
                            "file must have exactly one file-level :ID:",
                        )
                    )
                    document.has_file_id = False
                    document.file_id = None
                elif drawer_ids[0].value:
                    document.has_file_id = True
                    document.file_id = drawer_ids[0]
                else:
                    document.has_file_id = False
                    document.file_id = None
            drawer_start = None
            drawer_ids = []
            drawer_aliases = []
        elif stripped == ":END:" and relations_drawer_start is not None:
            relations_drawer_start = None
        else:
            if relations_drawer_start is not None and stripped and not stripped.startswith("#"):
                relation_match = RELATION_ITEM_RE.match(line)
                if not relation_match:
                    issues.append(
                        _issue(
                            "ERROR",
                            document,
                            line_number,
                            "malformed relation; expected '- predicate :: target'",
                        )
                    )
                else:
                    predicate = relation_match.group(1)
                    target = relation_match.group(2)
                    if predicate not in RELATION_PREDICATES:
                        issues.append(
                            _issue("ERROR", document, line_number, f"unknown relation predicate: {predicate}")
                        )
                    elif predicate == "informed-by":
                        citation_match = CITATION_TARGET_RE.match(target)
                        if not citation_match:
                            issues.append(
                                _issue(
                                    "ERROR",
                                    document,
                                    line_number,
                                    "informed-by target must be exactly one Org citation: [cite:@key]",
                                )
                            )
                        else:
                            document.relations.append(
                                LocatedRelation(predicate, citation_match.group(1), line_number)
                            )

            property_match = PROPERTY_RE.match(line)
            if property_match:
                name = property_match.group(1).upper()
                value = property_match.group(2).strip()
                if name == "ID":
                    located = LocatedValue(value, line_number)
                    document.ids.append(located)
                    if drawer_start is None:
                        issues.append(_issue("ERROR", document, line_number, ":ID: is outside a property drawer"))
                    else:
                        drawer_ids.append(located)
                elif name in {"ROAM_ALIAS", "ROAM_ALIASES"}:
                    located = LocatedValue(value, line_number)
                    if not value:
                        issues.append(_issue("ERROR", document, line_number, "empty :ROAM_ALIASES: property"))
                    if drawer_start is None:
                        issues.append(
                            _issue("ERROR", document, line_number, ":ROAM_ALIASES: is outside a property drawer")
                        )
                    else:
                        drawer_aliases.append(located)

        content_line = INLINE_VERBATIM_RE.sub(
            lambda match: " " * len(match.group(0)), line
        )
        if re.match(r"^\s*#(?!\+)", content_line):
            content_line = ""
        if BROKEN_ALIAS_RE.match(content_line):
            issues.append(
                _issue(
                    "ERROR",
                    document,
                    line_number,
                    "Obsidian alias syntax; use :ROAM_ALIASES: in the node property drawer",
                )
            )

        document.id_links.extend(
            LocatedValue(match.group(1), line_number) for match in ID_LINK_RE.finditer(content_line)
        )
        document.file_links.extend(
            LocatedValue(match.group(1), line_number) for match in FILE_LINK_RE.finditer(content_line)
        )
        setup_match = SETUPFILE_RE.match(line)
        if setup_match:
            document.setupfiles.append(LocatedValue(setup_match.group(1), line_number))
        if (
            drawer_start is None
            and relations_drawer_start is None
            and other_drawer_start is None
            and not FIXED_WIDTH_RE.match(content_line)
        ):
            for citation_match in ORG_CITATION_RE.finditer(content_line):
                citation = citation_match.group(0)
                for reference_match in ORG_CITATION_REFERENCE_RE.finditer(citation):
                    locator = " ".join(reference_match.group("locator").split()) or None
                    document.citations.append(
                        LocatedCitation(
                            reference_match.group("key"),
                            locator,
                            line_number,
                            citation_match.start() + reference_match.start() + 1,
                        )
                    )

    if drawer_start is not None:
        issues.append(_issue("ERROR", document, drawer_start, "unclosed property drawer"))
    if relations_drawer_start is not None:
        issues.append(_issue("ERROR", document, relations_drawer_start, "unclosed relations drawer"))
    if other_drawer_start is not None:
        issues.append(_issue("ERROR", document, other_drawer_start, "unclosed Org drawer"))
    return document, issues


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _resolve_file_target(document: OrgDocument, raw_target: str) -> tuple[Path | None, str | None]:
    target = unquote(_strip_quotes(raw_target))
    target = target.split("::", 1)[0]
    target = target.replace(r"\ ", " ")
    if not target:
        return document.path, None
    if target.startswith("file:"):
        return None, "duplicated file: prefix"
    parts = urlsplit(target)
    if parts.scheme and parts.scheme != "file":
        return None, f"URL incorrectly encoded as a file link: {target}"
    path = Path(target).expanduser()
    if not path.is_absolute():
        path = document.path.parent / path
    return path.resolve(strict=False), None


def _exists_with_exact_case(root: Path, target: Path) -> bool:
    try:
        relative = target.relative_to(root)
    except ValueError:
        return target.exists()
    current = root
    for part in relative.parts:
        if not current.is_dir() or part not in {entry.name for entry in current.iterdir()}:
            return False
        current /= part
    return current.exists()


def _bibliography_keys(path: Path) -> set[str]:
    return set(BIBTEX_ENTRY_RE.findall(path.read_text(encoding="utf-8")))


def parse_repository(root: Path) -> tuple[list[OrgDocument], list[Issue]]:
    """Parse all Org documents below ROOT and return syntax issues."""
    root = root.expanduser().resolve()
    documents: list[OrgDocument] = []
    issues: list[Issue] = []
    for path in sorted(root.rglob("*.org")):
        if ".git" in path.parts:
            continue
        document, parse_issues = _parse_document(path, root)
        documents.append(document)
        issues.extend(parse_issues)
    return documents, issues


def check_repository(
    root: Path,
    bibliography: Path | None = None,
    parsed: tuple[list[OrgDocument], list[Issue]] | None = None,
) -> list[Issue]:
    root = root.expanduser().resolve()
    if bibliography is None:
        sibling_bibliography = root.parent / "bibliotheca" / "zotero-library.bib"
        bibliography = sibling_bibliography if sibling_bibliography.is_file() else None
    else:
        bibliography = bibliography.expanduser().resolve()
    citation_keys = _bibliography_keys(bibliography) if bibliography is not None else None
    documents, parsed_issues = parsed if parsed is not None else parse_repository(root)
    issues = list(parsed_issues)

    ids: dict[str, list[tuple[OrgDocument, LocatedValue]]] = {}
    for document in documents:
        if (document.relations or document.citations) and document.file_id is None:
            graph_lines = [
                located.line
                for located in (*document.relations, *document.citations)
            ]
            issues.append(
                _issue(
                    "ERROR",
                    document,
                    min(graph_lines),
                    "notes with relations or citations require a file-level :ID:",
                )
            )
        for identifier in document.ids:
            if not identifier.value:
                issues.append(_issue("ERROR", document, identifier.line, "empty :ID: property"))
                continue
            ids.setdefault(identifier.value, []).append((document, identifier))
    for identifier, definitions in ids.items():
        if len(definitions) > 1:
            locations = ", ".join(
                f"{document.relative_path}:{located.line}" for document, located in definitions
            )
            for document, located in definitions:
                issues.append(
                    _issue("ERROR", document, located.line, f"duplicate ID {identifier!r}; also at {locations}")
                )

    documents_by_path = {document.path.resolve(): document for document in documents}
    incoming_file_links: dict[Path, list[tuple[OrgDocument, LocatedValue]]] = {}
    for document in documents:
        for link in document.id_links:
            if link.value not in ids:
                issues.append(_issue("ERROR", document, link.line, f"unresolved id link: {link.value}"))

        for link in document.file_links:
            target, error = _resolve_file_target(document, link.value)
            if error:
                issues.append(_issue("ERROR", document, link.line, error))
                continue
            assert target is not None
            raw_path = link.value.split("::", 1)[0]
            is_external = Path(unquote(_strip_quotes(raw_path))).expanduser().is_absolute()
            if is_external:
                issues.append(
                    _issue("WARNING", document, link.line, f"external file link is not portable: {raw_path}")
                )
                continue
            if not _exists_with_exact_case(root, target):
                issues.append(_issue("ERROR", document, link.line, f"missing file target: {link.value}"))
                continue
            if target in documents_by_path:
                incoming_file_links.setdefault(target, []).append((document, link))

        for setup in document.setupfiles:
            target, error = _resolve_file_target(document, setup.value)
            if error:
                issues.append(_issue("ERROR", document, setup.line, f"invalid SETUPFILE: {error}"))
            elif target is not None and not _exists_with_exact_case(root, target):
                issues.append(_issue("ERROR", document, setup.line, f"missing SETUPFILE: {setup.value}"))

        if citation_keys is not None:
            for relation in document.relations:
                if relation.target not in citation_keys:
                    issues.append(
                        _issue(
                            "ERROR",
                            document,
                            relation.line,
                            f"unresolved informed-by citation key: {relation.target}",
                        )
                    )
            for citation in document.citations:
                if citation.key not in citation_keys:
                    issues.append(
                        _issue(
                            "ERROR",
                            document,
                            citation.line,
                            f"unresolved citation key: {citation.key}",
                        )
                    )

    for target, incoming in incoming_file_links.items():
        target_document = documents_by_path[target]
        if not target_document.has_file_id:
            sources = ", ".join(
                f"{source.relative_path}:{link.line}" for source, link in incoming[:3]
            )
            issues.append(
                _issue(
                    "INFO",
                    target_document,
                    1,
                    f"ID-less file has incoming file links ({sources}); consider promoting it if links should survive moves",
                )
            )

    severity_order = {"ERROR": 0, "WARNING": 1, "INFO": 2}
    return sorted(issues, key=lambda issue: (severity_order[issue.severity], str(issue.path), issue.line, issue.message))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Episteme repository root (defaults to the parent of this script's bin directory)",
    )
    parser.add_argument("--quiet-info", action="store_true", help="do not print informational findings")
    parser.add_argument(
        "--bibliography",
        type=Path,
        help="BibTeX file used to resolve citations (defaults to the sibling Bibliotheca export)",
    )
    args = parser.parse_args(argv)

    if not args.root.is_dir():
        parser.error(f"repository root does not exist: {args.root}")
    if args.bibliography is not None and not args.bibliography.expanduser().is_file():
        parser.error(f"bibliography does not exist: {args.bibliography}")
    issues = check_repository(args.root, args.bibliography)
    visible = [issue for issue in issues if not args.quiet_info or issue.severity != "INFO"]
    for issue in visible:
        print(f"{issue.severity}: {issue.path}:{issue.line}: {issue.message}")

    counts = {
        severity: sum(issue.severity == severity for issue in issues)
        for severity in ("ERROR", "WARNING", "INFO")
    }
    print(
        "Integrity check: "
        f"{counts['ERROR']} error(s), {counts['WARNING']} warning(s), {counts['INFO']} info message(s)"
    )
    return 1 if counts["ERROR"] else 0


if __name__ == "__main__":
    sys.exit(main())
