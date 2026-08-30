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
HEADING_RE = re.compile(r"^\*+\s")
BEGIN_LITERAL_BLOCK_RE = re.compile(r"^#\+begin_(?:src|example|export|verbatim)\b", re.IGNORECASE)
END_LITERAL_BLOCK_RE = re.compile(r"^#\+end_(?:src|example|export|verbatim)\b", re.IGNORECASE)
INLINE_VERBATIM_RE = re.compile(r"(?<!\w)([=~]).*?\1")


@dataclass(frozen=True)
class LocatedValue:
    value: str
    line: int


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
    has_file_id: bool


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
        has_file_id=False,
    )
    issues: list[Issue] = []
    drawer_start: int | None = None
    drawer_ids: list[LocatedValue] = []
    drawer_aliases: list[LocatedValue] = []
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
        if HEADING_RE.match(line):
            seen_heading = True

        if stripped == ":PROPERTIES:":
            if drawer_start is not None:
                issues.append(_issue("ERROR", document, line_number, "nested property drawer"))
            drawer_start = line_number
            drawer_ids = []
            drawer_aliases = []
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
                document.has_file_id = True
            drawer_start = None
            drawer_ids = []
            drawer_aliases = []
        else:
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

        content_line = INLINE_VERBATIM_RE.sub("", line)
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

    if drawer_start is not None:
        issues.append(_issue("ERROR", document, drawer_start, "unclosed property drawer"))
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


def check_repository(root: Path) -> list[Issue]:
    root = root.expanduser().resolve()
    documents: list[OrgDocument] = []
    issues: list[Issue] = []
    for path in sorted(root.rglob("*.org")):
        if ".git" in path.parts:
            continue
        document, parse_issues = _parse_document(path, root)
        documents.append(document)
        issues.extend(parse_issues)

    ids: dict[str, list[tuple[OrgDocument, LocatedValue]]] = {}
    for document in documents:
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
    args = parser.parse_args(argv)

    if not args.root.is_dir():
        parser.error(f"repository root does not exist: {args.root}")
    issues = check_repository(args.root)
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
