#!/usr/bin/env python3
"""Validate QA and backend evidence before publishing generated agents."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
from typing import Mapping


_FULL_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")


def validate_release_evidence(
    *,
    source_commit: str,
    qa: Mapping[str, object],
    backend: Mapping[str, object],
    catalog: Mapping[str, object],
) -> list[str]:
    errors: list[str] = []
    catalog_agents = catalog.get("agents")
    if not isinstance(catalog_agents, list) or not all(
        isinstance(item, Mapping) for item in catalog_agents
    ):
        return ["catalog agents must be an array of objects"]
    canonical = {
        str(item.get("id"))
        for item in catalog_agents
        if isinstance(item.get("id"), str) and item.get("id")
    }
    aliases = {
        str(alias): str(item.get("id"))
        for item in catalog_agents or []
        if isinstance(item, Mapping)
        for alias in item.get("legacy_ids", [])
        if isinstance(alias, str)
    }
    if len(catalog_agents) != 11 or len(canonical) != 11:
        errors.append("catalog must contain exactly 11 canonical agents")
    if qa.get("status") != "pass" or qa.get("publish_ready") is not True:
        errors.append("QA benchmark acceptance must pass")
    coordinates = qa.get("coordinates")
    source_commits = coordinates.get("source_commits") if isinstance(coordinates, Mapping) else None
    treatment_commit = str(source_commits.get("treatment") or "") if isinstance(source_commits, Mapping) else ""
    if not _FULL_GIT_SHA.fullmatch(source_commit) or not _FULL_GIT_SHA.fullmatch(treatment_commit):
        errors.append("QA treatment and publishing source commits must be full immutable Git SHAs")
    elif source_commit != treatment_commit:
        errors.append("QA treatment commit must match the publishing source commit")
    if str(backend.get("schema_version") or "") != "1":
        errors.append("backend acceptance must use schema_version 1")
    if backend.get("status") != "pass":
        errors.append("backend acceptance must pass")
    if backend.get("catalog_schema_version") != 2:
        errors.append("backend must accept catalog schema version 2")
    if backend.get("agent_api_transport") != "endorctl agent api":
        errors.append("backend evidence must cover endorctl agent api")
    if set(backend.get("canonical_agent_ids") or []) != canonical:
        errors.append("backend canonical agent ids must exactly match catalog ids")
    if dict(backend.get("legacy_aliases") or {}) != aliases:
        errors.append("backend legacy alias resolution must exactly match catalog aliases")
    audit = backend.get("audit_log_correlation")
    if not isinstance(audit, Mapping) or audit.get("status") != "pass":
        errors.append("backend audit-log correlation must pass")
    else:
        required = {"request_id", "actor_type", "canonical_agent_id", "on_behalf_of"}
        if not required.issubset(set(audit.get("observed_fields") or [])):
            errors.append("backend audit-log correlation is missing required fields")
        if int(audit.get("canonical_agent_samples") or 0) < len(canonical):
            errors.append("backend audit-log evidence must sample every canonical agent")
    return errors


def _load(path: Path | None, env_name: str | None, label: str) -> dict[str, object]:
    raw = os.environ.get(env_name, "") if env_name else ""
    try:
        value = json.loads(raw) if raw else json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is missing or invalid") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--catalog", type=Path, default=Path("catalog.json"))
    parser.add_argument("--qa-acceptance", type=Path)
    parser.add_argument("--qa-acceptance-env")
    parser.add_argument("--backend-acceptance", type=Path)
    parser.add_argument("--backend-acceptance-env")
    args = parser.parse_args()
    if bool(args.qa_acceptance) == bool(args.qa_acceptance_env):
        parser.error("choose exactly one QA acceptance file or environment variable")
    if bool(args.backend_acceptance) == bool(args.backend_acceptance_env):
        parser.error("choose exactly one backend acceptance file or environment variable")
    try:
        qa = _load(args.qa_acceptance, args.qa_acceptance_env, "QA acceptance")
        backend = _load(args.backend_acceptance, args.backend_acceptance_env, "backend acceptance")
        catalog = _load(args.catalog, None, "catalog")
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1
    errors = validate_release_evidence(
        source_commit=args.source_commit,
        qa=qa,
        backend=backend,
        catalog=catalog,
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("OK: QA and backend release evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
