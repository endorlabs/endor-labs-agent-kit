"""Compiled, source-bound task-profile contracts for runtime Hosts."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
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

    def to_json_bytes(self) -> bytes:
        """Serialize identically for identical source."""

        return (
            json.dumps(
                self.to_dict(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")


def compile_profile_contract(
    agent_id: str,
    profile_id: str,
    *,
    knowledge_pack_root: str | Path | None = None,
) -> CompiledProfileContract:
    """Compile one task profile from canonical Agent Kit source."""

    if knowledge_pack_root is None:
        return _compile_default_profile_contract(agent_id, profile_id)
    return _compile_profile_contract(
        agent_id,
        profile_id,
        Path(knowledge_pack_root),
    )


@lru_cache(maxsize=None)
def _compile_default_profile_contract(
    agent_id: str,
    profile_id: str,
) -> CompiledProfileContract:
    return _compile_profile_contract(
        agent_id,
        profile_id,
        default_knowledge_pack_root(),
    )


def _compile_profile_contract(
    agent_id: str,
    profile_id: str,
    pack_root: Path,
) -> CompiledProfileContract:
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
    schema = json_schema_for_agent(
        agent_id,
        projected_fields,
        profile_id=profile_id,
    )
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


def profile_contract_from_dict(
    payload: dict[str, Any],
    *,
    expected_agent_id: str | None = None,
    expected_profile_id: str | None = None,
) -> CompiledProfileContract:
    """Verify and restore one immutable lifecycle profile contract."""

    if not isinstance(payload, dict):
        raise ValueError("profile contract must be an object")
    schema_version = _serialized_string(payload, "schema_version")
    if schema_version != PROFILE_CONTRACT_SCHEMA_VERSION:
        raise ValueError(
            f"profile contract schema_version must be {PROFILE_CONTRACT_SCHEMA_VERSION}"
        )
    agent_id = _serialized_string(payload, "agent_id")
    profile_id = _serialized_string(payload, "profile_id")
    if expected_agent_id is not None and agent_id != expected_agent_id:
        raise ValueError("profile contract agent_id does not match selected agent")
    if expected_profile_id is not None and profile_id != expected_profile_id:
        raise ValueError("profile contract profile_id does not match selected profile")

    projection_applied = payload.get("projection_applied")
    if not isinstance(projection_applied, bool):
        raise ValueError("profile contract projection_applied must be a boolean")
    output_fields = _serialized_strings(payload, "output_fields")
    required_fields = _serialized_strings(payload, "required_fields")
    gate = _serialized_mapping(payload, "gate_validator")
    policy = _serialized_mapping(payload, "policy_pack")
    gate_validator_id = _serialized_string(gate, "id")
    gate_validator_version = _serialized_string(gate, "version")
    policy_pack_support = policy.get("supported")
    if not isinstance(policy_pack_support, bool):
        raise ValueError("profile contract policy_pack.supported must be a boolean")
    policy_pack_fields = _serialized_strings(policy, "fields")
    schema = _serialized_mapping(payload, "provider_neutral_schema")
    properties = schema.get("properties")
    if not isinstance(properties, dict) or tuple(properties) != output_fields:
        raise ValueError("profile contract output_fields do not match schema properties")
    schema_required = schema.get("required")
    if not isinstance(schema_required, list) or tuple(schema_required) != required_fields:
        raise ValueError("profile contract required_fields do not match schema required")

    source_digest = _serialized_digest(payload, "source_digest")
    recipe_digest = _serialized_digest(payload, "recipe_digest")
    knowledge_pack_digest = _serialized_digest(payload, "knowledge_pack_digest")
    contract_digest = _serialized_digest(payload, "contract_digest")
    digest_payload = {
        "schema_version": schema_version,
        "agent_id": agent_id,
        "profile_id": profile_id,
        "projection_applied": projection_applied,
        "output_fields": output_fields,
        "required_fields": required_fields,
        "gate_validator_id": gate_validator_id,
        "gate_validator_version": gate_validator_version,
        "policy_pack_support": policy_pack_support,
        "policy_pack_fields": policy_pack_fields,
        "source_digest": source_digest,
        "recipe_digest": recipe_digest,
        "knowledge_pack_digest": knowledge_pack_digest,
        "provider_neutral_schema": schema,
    }
    expected_digest = hashlib.sha256(
        json.dumps(
            digest_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if contract_digest != expected_digest:
        raise ValueError("profile contract contract_digest does not match content")

    return CompiledProfileContract(
        agent_id=agent_id,
        profile_id=profile_id,
        projection_applied=projection_applied,
        output_fields=output_fields,
        required_fields=required_fields,
        gate_validator_id=gate_validator_id,
        gate_validator_version=gate_validator_version,
        policy_pack_support=policy_pack_support,
        policy_pack_fields=policy_pack_fields,
        source_digest=source_digest,
        recipe_digest=recipe_digest,
        knowledge_pack_digest=knowledge_pack_digest,
        provider_neutral_schema_json=json.dumps(
            schema,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        contract_digest=contract_digest,
        schema_version=schema_version,
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
        "ai-sast-remediation",
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


def _serialized_mapping(payload: dict[str, Any], field: str) -> dict[str, Any]:
    value = payload.get(field)
    if not isinstance(value, dict):
        raise ValueError(f"profile contract {field} must be an object")
    return value


def _serialized_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"profile contract {field} must be a non-empty string")
    return value


def _serialized_strings(payload: dict[str, Any], field: str) -> tuple[str, ...]:
    value = payload.get(field)
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise ValueError(f"profile contract {field} must be an array of strings")
    if len(set(value)) != len(value):
        raise ValueError(f"profile contract {field} must not contain duplicates")
    return tuple(value)


def _serialized_digest(payload: dict[str, Any], field: str) -> str:
    value = _serialized_string(payload, field)
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(f"profile contract {field} must be a lowercase SHA-256 digest")
    return value
