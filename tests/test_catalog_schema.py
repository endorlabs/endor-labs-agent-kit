from __future__ import annotations

from dataclasses import replace
import hashlib

import pytest

from endor_agent_kit.catalog_schema import (
    CatalogAgent,
    CatalogBundle,
    catalog_manifest_payload,
)
from endor_agent_kit.recipe import EndorAgentRecipe, HostCapabilities


def _recipe() -> EndorAgentRecipe:
    return EndorAgentRecipe(
        recipe_schema_version=2,
        id="schema-fixture",
        name="Schema Fixture",
        version="1.0.0",
        description="Fixture",
        safety_class="read_only",
        supported_transports=("endorctl_api",),
        host_capabilities_required=HostCapabilities(run_commands=True),
        inputs=(),
        outputs=(),
        evals="evals/cases.yaml",
        compatible_hosts=("claude-code",),
        endorctl_api_invocations=("lookup_package_version_uuid",),
        instructions_path="instructions.md",
        model="sonnet",
    )


def test_catalog_schema_round_trips_manifest_agent_records_with_unknown_fields():
    record = {
        "id": "schema-fixture",
        "name": "Schema Fixture",
        "version": "1.0.0",
        "host": "claude-code",
        "source": {
            "recipe_schema_version": 2,
            "builder_recipe": "source/agents/schema-fixture/recipe.yaml",
            "future_source_field": "preserved",
        },
        "editions": [
            {
                "id": "enterprise-edition",
                "name": "Enterprise Edition",
                "path": "claude-code/schema-fixture",
                "artifacts": [
                    {
                        "path": "claude-code/schema-fixture/schema-fixture.md",
                        "sha256": "abc123",
                        "bytes": 42,
                        "profile_id": "evidence-check",
                        "future_artifact_field": "preserved",
                    }
                ],
                "requires_endorctl": "",
                "future_edition_field": "preserved",
            }
        ],
        "future_agent_field": "preserved",
    }

    agent = CatalogAgent.from_manifest_record(record)

    assert agent.editions[0].artifact_named("schema-fixture.md").sha256 == "abc123"
    assert agent.editions[0].artifact_named("schema-fixture.md").profile_id == "evidence-check"
    assert agent.to_manifest_record() == record


def test_catalog_schema_preserves_minimal_existing_manifest_agents():
    record = {
        "id": "other-agent",
        "host": "claude-code",
        "editions": [],
    }

    agent = CatalogAgent.from_manifest_record(record)

    assert agent.to_manifest_record() == record


def test_catalog_schema_builds_manifest_payload_from_published_bundle(tmp_path):
    recipe = _recipe()
    destination = tmp_path / "catalog"
    bundle_dir = destination / "claude-code" / recipe.id
    bundle_dir.mkdir(parents=True)
    artifact = bundle_dir / f"{recipe.id}.md"
    artifact.write_text("current", encoding="utf-8")

    bundle = CatalogBundle.from_published_bundle(
        destination,
        recipe,
        "claude-code",
        "enterprise-edition",
        "Enterprise Edition",
        bundle_dir,
        requires_endorctl=">=1.0",
        artifact_profiles={artifact.relative_to(destination).as_posix(): "evidence-check"},
    )
    agent = CatalogAgent.from_recipe(recipe, "claude-code", (bundle,))

    payload = catalog_manifest_payload((agent,))

    manifest_agent = payload["agents"][0]
    manifest_bundle = manifest_agent["editions"][0]
    manifest_artifact = manifest_bundle["artifacts"][0]
    assert manifest_agent["source"]["builder_recipe"] == "source/agents/schema-fixture/recipe.yaml"
    assert manifest_bundle["requires_endorctl"] == ">=1.0"
    assert manifest_artifact["path"] == "claude-code/schema-fixture/schema-fixture.md"
    assert manifest_artifact["bytes"] == len("current")
    assert manifest_artifact["sha256"] == hashlib.sha256(b"current").hexdigest()
    assert manifest_artifact["profile_id"] == "evidence-check"
    assert "profile_contract_digest" not in manifest_artifact
    assert "profile_gate_validator" not in manifest_artifact


def test_catalog_schema_fails_closed_when_source_backed_profile_contract_is_invalid(
    tmp_path,
    monkeypatch,
):
    recipe = replace(_recipe(), id="sca-remediation")
    destination = tmp_path / "catalog"
    bundle_dir = destination / "claude-code" / recipe.id
    bundle_dir.mkdir(parents=True)
    artifact = bundle_dir / f"{recipe.id}.md"
    artifact.write_text("current", encoding="utf-8")

    def fail_contract_compilation(_agent_id, _profile_id):
        raise ValueError("invalid canonical profile contract")

    monkeypatch.setattr(
        "endor_agent_kit.catalog_schema.compile_profile_contract",
        fail_contract_compilation,
    )

    with pytest.raises(ValueError, match="invalid canonical profile contract"):
        CatalogBundle.from_published_bundle(
            destination,
            recipe,
            "claude-code",
            "enterprise-edition",
            "Enterprise Edition",
            bundle_dir,
            artifact_profiles={artifact.relative_to(destination).as_posix(): "evidence-check"},
        )
