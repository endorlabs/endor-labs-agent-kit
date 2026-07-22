#!/usr/bin/env python3
"""Validate that an ai-plugins checkout matches its Agent Kit provenance."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Mapping


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_AGENT_PREFIX = "endor-"
_AGENT_SUFFIX = "-agent.md"
_SETUP_AGENT = "endor-agent-kit-setup-agent.md"


def validate_mirror_provenance(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        statement = json.loads(
            (root / "provenance/agent-kit-catalog.intoto.json").read_text(encoding="utf-8")
        )
        checksum_parts = (root / "provenance/manifest.sha256").read_text(
            encoding="utf-8"
        ).strip().split()
    except (OSError, json.JSONDecodeError) as exc:
        return [f"missing or invalid mirror provenance: {exc}"]

    subjects = statement.get("subject") if isinstance(statement, Mapping) else None
    if not isinstance(subjects, list) or len(subjects) != 1 or not isinstance(subjects[0], Mapping):
        errors.append("provenance must contain exactly one manifest subject")
        subject_digest = ""
    else:
        subject = subjects[0]
        digest = subject.get("digest")
        subject_digest = str(digest.get("sha256") or "") if isinstance(digest, Mapping) else ""
        if subject.get("name") != "manifest.json" or not _SHA256.fullmatch(subject_digest):
            errors.append("provenance subject must be a SHA-256 digest of manifest.json")

    if (
        len(checksum_parts) != 2
        or not _SHA256.fullmatch(checksum_parts[0])
        or checksum_parts[1] != "manifest.json"
    ):
        errors.append("manifest.sha256 must contain one manifest.json checksum")
    elif checksum_parts[0] != subject_digest:
        errors.append("manifest checksum does not match provenance subject")

    predicate = statement.get("predicate") if isinstance(statement, Mapping) else None
    catalog = predicate.get("catalog") if isinstance(predicate, Mapping) else None
    if not isinstance(catalog, list) or not all(isinstance(item, Mapping) for item in catalog):
        errors.append("provenance predicate catalog must be an array of objects")
        provenance_ids: set[str] = set()
    else:
        provenance_ids = {
            str(item.get("id"))
            for item in catalog
            if isinstance(item.get("id"), str) and item.get("id")
        }

    agents_root = root / "agents"
    try:
        filenames = {
            path.name
            for path in agents_root.iterdir()
            if path.is_file() and path.name != _SETUP_AGENT
        }
    except OSError as exc:
        errors.append(f"missing mirror agents directory: {exc}")
        filenames = set()
    invalid_names = sorted(
        name
        for name in filenames
        if not (name.startswith(_AGENT_PREFIX) and name.endswith(_AGENT_SUFFIX))
    )
    if invalid_names:
        errors.append(f"unexpected root agent filenames: {invalid_names}")
    mirror_ids = {
        name[len(_AGENT_PREFIX) : -len(_AGENT_SUFFIX)]
        for name in filenames
        if name.startswith(_AGENT_PREFIX) and name.endswith(_AGENT_SUFFIX)
    }
    if len(provenance_ids) != 11 or len(mirror_ids) != 11:
        errors.append("mirror provenance and root package must each contain exactly 11 canonical agents")
    if provenance_ids != mirror_ids:
        errors.append("mirror canonical agent ids do not match provenance")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    errors = validate_mirror_provenance(args.root.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("OK: mirror provenance matches 11 canonical agents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
