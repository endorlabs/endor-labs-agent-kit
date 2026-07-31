#!/usr/bin/env python3
"""Reject tracked cache, scratch, and unsafe runtime residue."""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath
import re
import subprocess


FORBIDDEN_DIRECTORIES = frozenset(
    {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
)
FORBIDDEN_NAMES = frozenset({".DS_Store", "HANDOFF.md"})
FORBIDDEN_SUFFIXES = frozenset({".pyc", ".pyo", ".log", ".tmp", ".bak", ".swp"})
QA_RAW_RUNTIME_NAMES = frozenset(
    {"stdout.txt", "stderr.txt", "prompt.txt", "command.txt", "summary.txt", "schema.txt"}
)
NUMBERED_COPY = re.compile(r" \([0-9]+\)(?:\.[^/]+)?$")
VALIDATION_REQUEST = re.compile(r"(?:^|/)(?:validation[-_]request|validation-requests)(?:[./_-]|$)")


def hygiene_problem(path: str, *, qa_artifacts: bool = False) -> str | None:
    """Return a reason when a tracked path is repository residue."""

    parsed = PurePosixPath(path)
    if FORBIDDEN_DIRECTORIES.intersection(parsed.parts):
        return "cache directory"
    if parsed.name in FORBIDDEN_NAMES:
        return "local handoff or operating-system file"
    if parsed.suffix.lower() in FORBIDDEN_SUFFIXES:
        return "cache, log, or temporary file"
    if NUMBERED_COPY.search(path):
        return "numbered duplicate"
    if VALIDATION_REQUEST.search(path):
        return "local validation-request artifact"
    if qa_artifacts and parsed.name in QA_RAW_RUNTIME_NAMES:
        return "raw runtime capture; retain only bounded redacted proof sidecars"
    return None


def tracked_paths(root: Path) -> tuple[str, ...]:
    completed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return tuple(
        item.decode("utf-8")
        for item in completed.stdout.split(b"\0")
        if item
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--qa-artifacts",
        action="store_true",
        help="also reject unredacted runtime capture basenames",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    problems = [
        (path, reason)
        for path in tracked_paths(root)
        if (reason := hygiene_problem(path, qa_artifacts=args.qa_artifacts))
    ]
    if problems:
        for path, reason in problems:
            print(f"ERROR: {path}: {reason}")
        return 1
    print(f"OK: tracked repository hygiene ({root})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
