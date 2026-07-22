from __future__ import annotations

import json

from scripts.validate_release_evidence import validate_release_evidence

from conftest import repo_root


def test_release_evidence_binds_qa_backend_aliases_and_audit_log_to_catalog() -> None:
    source_commit = "a" * 40
    catalog = json.loads((repo_root() / "catalog.json").read_text(encoding="utf-8"))
    canonical = [item["id"] for item in catalog["agents"]]
    aliases = {
        alias: item["id"]
        for item in catalog["agents"]
        for alias in item.get("legacy_ids", [])
    }
    qa = {
        "status": "pass",
        "publish_ready": True,
        "coordinates": {"source_commits": {"treatment": source_commit}},
    }
    backend = {
        "schema_version": "1",
        "status": "pass",
        "catalog_schema_version": 2,
        "agent_api_transport": "endorctl agent api",
        "canonical_agent_ids": canonical,
        "legacy_aliases": aliases,
        "audit_log_correlation": {
            "status": "pass",
            "observed_fields": [
                "request_id",
                "actor_type",
                "canonical_agent_id",
                "on_behalf_of",
            ],
            "canonical_agent_samples": 11,
        },
    }

    assert validate_release_evidence(
        source_commit=source_commit,
        qa=qa,
        backend=backend,
        catalog=catalog,
    ) == []

    backend["legacy_aliases"] = {}
    assert "backend legacy alias resolution must exactly match catalog aliases" in validate_release_evidence(
        source_commit=source_commit,
        qa=qa,
        backend=backend,
        catalog=catalog,
    )


def test_release_evidence_requires_exact_full_source_commit() -> None:
    catalog = json.loads((repo_root() / "catalog.json").read_text(encoding="utf-8"))
    qa = {
        "status": "pass",
        "publish_ready": True,
        "coordinates": {"source_commits": {"treatment": "a" * 39}},
    }

    errors = validate_release_evidence(
        source_commit="a" * 40,
        qa=qa,
        backend={},
        catalog=catalog,
    )

    assert "QA treatment and publishing source commits must be full immutable Git SHAs" in errors
