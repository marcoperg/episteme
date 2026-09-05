"""Atomically remove one validated AGENT_TODO drawer by fingerprint."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import sys
import tempfile

from . import integrity

ROOT = Path(__file__).resolve().parents[3]


def complete_todo(root: Path, fingerprint: str) -> Path:
    """Remove exactly one unchanged drawer from an otherwise valid repository."""
    root = root.expanduser().resolve()
    parsed = integrity.parse_repository(root)
    issues = integrity.check_repository(root, parsed=parsed)
    errors = [issue for issue in issues if issue.severity == "ERROR"]
    if errors:
        raise RuntimeError("repository integrity errors prevent task completion")

    matches = [
        (document, todo)
        for document in parsed[0]
        for todo in document.todos
        if todo.fingerprint == fingerprint
    ]
    if not matches:
        raise RuntimeError(f"unknown or changed AGENT_TODO fingerprint: {fingerprint}")
    if len(matches) != 1:
        raise RuntimeError(f"ambiguous AGENT_TODO fingerprint: {fingerprint}")

    document, todo = matches[0]
    if document.path.is_symlink():
        raise RuntimeError("refusing to replace a symlinked Org note")
    original_stat = document.path.stat()
    original_bytes = document.path.read_bytes()
    if hashlib.sha256(original_bytes).hexdigest() != document.source_digest:
        raise RuntimeError("Org note changed during completion")
    after_read_stat = document.path.stat()
    version = (
        original_stat.st_dev,
        original_stat.st_ino,
        original_stat.st_size,
        original_stat.st_mtime_ns,
    )
    after_read_version = (
        after_read_stat.st_dev,
        after_read_stat.st_ino,
        after_read_stat.st_size,
        after_read_stat.st_mtime_ns,
    )
    if after_read_version != version:
        raise RuntimeError("Org note changed during completion")
    lines = original_bytes.decode("utf-8").splitlines(keepends=True)
    if lines[todo.start_line - 1].strip() != ":AGENT_TODO:":
        raise RuntimeError("task opening marker changed during completion")
    if lines[todo.end_line - 1].strip() != ":END:":
        raise RuntimeError("task closing marker changed during completion")
    updated = lines[: todo.start_line - 1] + lines[todo.end_line :]

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{document.path.name}.", suffix=".tmp", dir=document.path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.writelines(updated)
        shutil.copystat(document.path, temporary, follow_symlinks=False)
        os.chown(temporary, original_stat.st_uid, original_stat.st_gid)
        os.utime(temporary, None)
        current_stat = document.path.stat()
        current_version = (
            current_stat.st_dev,
            current_stat.st_ino,
            current_stat.st_size,
            current_stat.st_mtime_ns,
        )
        if current_version != version or document.path.read_bytes() != original_bytes:
            raise RuntimeError("Org note changed during completion")
        temporary.replace(document.path)
    finally:
        temporary.unlink(missing_ok=True)
    return document.relative_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fingerprint", help="fingerprint returned by bin/agent-todos")
    parser.add_argument("--root", type=Path, default=ROOT, help="Episteme repository root")
    args = parser.parse_args(argv)
    if not args.root.expanduser().is_dir():
        parser.error(f"repository root does not exist: {args.root}")

    try:
        path = complete_todo(args.root, args.fingerprint)
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(path.as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
