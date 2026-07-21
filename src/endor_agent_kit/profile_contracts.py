"""Compiled, source-bound task-profile contracts for runtime Hosts."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from endor_agent_kit.knowledge_pack import default_knowledge_pack_root, load_knowledge_pack
from endor_agent_kit.recipe import load_recipe
from endor_agent_kit.structured_output_contracts import (
    json_schema_for_agent,
    validate_structured_output_payload,
)


PROFILE_CONTRACT_SCHEMA_VERSION = "1"
PROFILE_GATE_VALIDATOR_VERSION = "1"


@dataclass(frozen=True)
class CompiledProfileContract:
    """One immutable profile contract shared by compiler and Host consumers."""

    agent_id: str
    profile_id: str
    projection_applied: bool
    output_fields: tuple[str, ...]
    required_fields: tuple[str, ...]
    gate_validator_id: str
    gate_validator_version: str
    policy_pack_support: bool
    policy_pack_fields: tuple[str, ...]
    source_digest: str
    recipe_digest: str
    knowledge_pack_digest: str
    provider_neutral_schema_json: str
    contract_digest: str
    schema_version: str = PROFILE_CONTRACT_SCHEMA_VERSION

    @property
    def provider_neutral_schema(self) -> dict[str, Any]:
        """Return a fresh provider-neutral schema mapping."""

        return json.loads(self.provider_neutral_schema_json)

    def to_dict(self) -> dict[str, Any]:
        """Return the deterministic portable representation."""

        return {
            "schema_version": self.schema_version,
            "agent_id": self.agent_id,
            "profile_id": self.profile_id,
            "projection_applied": self.projection_applied,
            "output_fields": list(self.output_fields),
            "required_fields": list(self.required_fields),
            "gate_validator": {
                "id": self.gate_validator_id,
                "version": self.gate_validator_version,
            },
            "policy_pack": {
                "supported": self.policy_pack_support,
                "fields": list(self.policy_pack_fields),
            },
            "source_digest": self.source_digest,
            "recipe_digest": self.recipe_digest,
            "knowledge_pack_digest": self.knowledge_pack_digest,
            "provider_neutral_schema": self.provider_neutral_schema,
            "contract_digest": self.contract_digest,
        }


def compile_profile_contract(
    agent_id: str,
    profile_id: str,
    *,
    knowledge_pack_root: str | Path | None = None,
) -> CompiledProfileContract:
    """Compile one task profile from canonical Agent Kit source."""

    pack_root = (
        Path(knowledge_pack_root)
        if knowledge_pack_root is not None
        else default_knowledge_pack_root()
    )
    source_root = pack_root.parent
    recipe_path = source_root / "agents" / agent_id / "recipe.yaml"
    if not recipe_path.is_file():
        raise ValueError(f"unknown source-backed agent {agent_id!r}")
    recipe = load_recipe(recipe_path)
    workflow = load_knowledge_pack(pack_root).workflow_for(agent_id)
    profile = workflow.task_profile_for(profile_id) if workflow is not None else None
    if profile is None:
        raise ValueError(f"unknown task profile {profile_id!r} for agent {agent_id!r}")

    projected_fields = profile.output_fields or None
    schema = json_schema_for_agent(agent_id, projected_fields)
    output_fields = tuple(schema["properties"])
    required_fields = tuple(schema["required"])
    schema_json = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
    instructions_path = recipe_path.parent / recipe.instructions_path
    workflow_path = pack_root / "workflows" / f"{agent_id}.yaml"
    source_digest = _digest_files((recipe_path, instructions_path), relative_to=source_root)
    recipe_digest = _digest_files((recipe_path,), relative_to=source_root)
    knowledge_pack_digest = _digest_files(
        (pack_root / "pack.yaml", pack_root / "query-recipes.yaml", workflow_path),
        relative_to=source_root,
    )
    gate_validator_id = _gate_validator_id(agent_id, profile_id)
    policy_fields = tuple(
        field for field in ("policy_context", "policy_evaluations") if field in output_fields
    )
    digest_payload = {
        "schema_version": PROFILE_CONTRACT_SCHEMA_VERSION,
        "agent_id": agent_id,
        "profile_id": profile_id,
        "projection_applied": bool(projected_fields),
        "output_fields": output_fields,
        "required_fields": required_fields,
        "gate_validator_id": gate_validator_id,
        "gate_validator_version": PROFILE_GATE_VALIDATOR_VERSION,
        "policy_pack_support": recipe.policy_pack_support,
        "policy_pack_fields": policy_fields,
        "source_digest": source_digest,
        "recipe_digest": recipe_digest,
        "knowledge_pack_digest": knowledge_pack_digest,
        "provider_neutral_schema": schema,
    }
    contract_digest = hashlib.sha256(
        json.dumps(digest_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return CompiledProfileContract(
        agent_id=agent_id,
        profile_id=profile_id,
        projection_applied=bool(projected_fields),
        output_fields=output_fields,
        required_fields=required_fields,
        gate_validator_id=gate_validator_id,
        gate_validator_version=PROFILE_GATE_VALIDATOR_VERSION,
        policy_pack_support=recipe.policy_pack_support,
        policy_pack_fields=policy_fields,
        source_digest=source_digest,
        recipe_digest=recipe_digest,
        knowledge_pack_digest=knowledge_pack_digest,
        provider_neutral_schema_json=schema_json,
        contract_digest=contract_digest,
    )


def validate_profile_output_payload(
    agent_id: str,
    profile_id: str,
    payload: dict[str, Any],
) -> list[str]:
    """Validate output against one compiled task-profile boundary."""

    contract = compile_profile_contract(agent_id, profile_id)
    errors = validate_structured_output_payload(agent_id, payload, contract.output_fields)
    allowed = set(contract.output_fields)
    errors.extend(
        f"{field}: not allowed by task profile {profile_id}"
        for field in sorted(set(payload) - allowed)
    )
    return errors


def _gate_validator_id(agent_id: str, profile_id: str) -> str:
    if profile_id in {"resolve-scope", "evidence-check"} and agent_id in {
        "sca-remediation",
        "ai-sast-triage",
    }:
        return f"{agent_id}.read-only-profile"
    return f"{agent_id}.structured-output"


def _digest_files(paths: tuple[Path, ...], *, relative_to: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        if not path.is_file():
            raise ValueError(f"profile contract source file is missing: {path}")
        digest.update(path.relative_to(relative_to).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
