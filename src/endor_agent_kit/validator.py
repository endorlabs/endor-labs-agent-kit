"""Validation for Endor Agent Kit recipes."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from endor_agent_kit.recipe import load_yaml_file

PUBLIC_MCP_TOOLS = frozenset(
    {
        "check_dependency_for_vulnerabilities",
        "check_dependency_for_risks",
        "get_endor_vulnerability",
        "get_resource",
        "scan",
        "security_review",
    }
)

SUPPORTED_TRANSPORTS = frozenset({"mcp", "endorctl_api", "direct_api"})
SUPPORTED_HOSTS = frozenset({"claude-code", "claude-managed-agents", "codex", "portable", "raw"})
SUPPORTED_EDITIONS = frozenset({"developer-edition", "enterprise-edition"})
SAFETY_CLASSES = frozenset({"read_only", "dry_run", "mutating"})
ACTION_KINDS = frozenset(
    {
        "endor.query",
        "scm.source_read",
        "scm.change_request",
        "scm.comment",
        "endor.policy_write",
        "approval.request",
        "approval.verify",
        "ticket.create",
    }
)
ACTION_AVAILABILITY = frozenset({"available", "requires_adapter", "unavailable"})
HOST_CAPABILITY_KEYS = frozenset({"run_commands", "read_files", "write_files", "open_pr"})
FORBIDDEN_V0_FIELDS = frozenset({"graph", "nodes", "edges"})
REQUIRED_FIELDS = (
    "recipe_schema_version",
    "id",
    "name",
    "version",
    "description",
    "safety_class",
    "supported_transports",
    "host_capabilities_required",
    "inputs",
    "outputs",
    "evals",
    "compatible_hosts",
    "mutations",
    "instructions_path",
    "model",
)
SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{2,63}$")


def validate_recipe_file(path: str | Path) -> list[str]:
    """Validate a recipe file and return all errors."""

    recipe_path = Path(path)
    try:
        data = load_yaml_file(recipe_path)
    except Exception as exc:
        return [f"recipe: failed to read YAML: {exc}"]
    return validate_recipe_data(data, recipe_path=recipe_path)


def validate_recipe_data(data: dict[str, Any], *, recipe_path: Path | None = None) -> list[str]:
    """Validate one recipe mapping."""

    errors: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"{field}: required field is missing")

    for field in sorted(FORBIDDEN_V0_FIELDS.intersection(data.keys())):
        errors.append(f"{field}: graph topology lands in a future schema version; v0 recipes are prompt-focused")

    schema_version = data.get("recipe_schema_version")
    if schema_version not in {1, 2}:
        errors.append("recipe_schema_version: must be 1 or 2")

    recipe_id = data.get("id", "")
    if not isinstance(recipe_id, str) or not SLUG_RE.match(recipe_id):
        errors.append("id: must match ^[a-z][a-z0-9-]{2,63}$")

    safety = data.get("safety_class")
    if safety not in SAFETY_CLASSES:
        errors.append("safety_class: must be one of read_only, dry_run, mutating")

    mutations = data.get("mutations")
    if mutations is None:
        mutations = []
    elif not isinstance(mutations, list):
        errors.append("mutations: must be a list")
        mutations = []
    elif safety == "read_only" and mutations:
        errors.append("mutations: read_only recipes must leave this field empty")
    elif safety == "dry_run" and mutations:
        errors.append("mutations: dry_run recipes must leave this field empty")
    elif safety == "mutating" and not mutations:
        errors.append("mutations: mutating recipes must declare their mutation types")

    transports = _list_of_strings(data.get("supported_transports"), "supported_transports", errors)
    for transport in transports:
        if transport not in SUPPORTED_TRANSPORTS:
            errors.append(f"supported_transports: unsupported transport {transport!r}")

    capabilities = data.get("host_capabilities_required")
    if not isinstance(capabilities, dict):
        errors.append("host_capabilities_required: must be a mapping of abstract capabilities to booleans")
        capabilities = {}
    else:
        for key, value in capabilities.items():
            if not isinstance(value, bool):
                errors.append(f"host_capabilities_required.{key}: must be boolean")

    if safety == "mutating":
        if not bool(capabilities.get("write_files", False)) and not bool(capabilities.get("open_pr", False)):
            errors.append("host_capabilities_required: mutating recipes must require write_files or open_pr")
        if "write_files" in mutations and not bool(capabilities.get("write_files", False)):
            errors.append("host_capabilities_required.write_files: required when mutations includes write_files")
        if "open_pr" in mutations and not bool(capabilities.get("open_pr", False)):
            errors.append("host_capabilities_required.open_pr: required when mutations includes open_pr")
        if bool(capabilities.get("open_pr", False)) and not bool(capabilities.get("run_commands", False)):
            errors.append("host_capabilities_required.run_commands: required when opening pull requests")

    if "endorctl_api" in transports and not bool(capabilities.get("run_commands", False)):
        errors.append("host_capabilities_required.run_commands: must be true when supported_transports includes endorctl_api")

    mcp_tools = _list_of_strings(data.get("required_endor_mcp_tools", []), "required_endor_mcp_tools", errors)
    if "mcp" in transports and not mcp_tools:
        errors.append("required_endor_mcp_tools: required when supported_transports includes mcp")
    for tool in mcp_tools:
        if tool not in PUBLIC_MCP_TOOLS:
            errors.append(f"required_endor_mcp_tools: unknown public Endor MCP tool {tool!r}")

    _list_of_strings(data.get("endorctl_api_invocations", []), "endorctl_api_invocations", errors)

    tier = data.get("endor_tier_minimum")
    if tier not in {"free", "enterprise"}:
        errors.append("endor_tier_minimum: must be free or enterprise")

    hosts = _list_of_strings(data.get("compatible_hosts"), "compatible_hosts", errors)
    for host in hosts:
        if host not in SUPPORTED_HOSTS:
            errors.append(f"compatible_hosts: unsupported host {host!r}")
    _validate_host_editions(data.get("host_editions", {}), hosts, errors)
    _validate_action_contracts(
        data,
        capabilities,
        recipe_path=recipe_path,
        errors=errors,
    )

    _validate_fields(data.get("inputs"), "inputs", errors)
    _validate_fields(data.get("outputs"), "outputs", errors)

    for string_field in ("name", "version", "description", "evals", "instructions_path", "model"):
        value = data.get(string_field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{string_field}: must be a non-empty string")

    if recipe_path is not None and isinstance(data.get("instructions_path"), str):
        if not (recipe_path.parent / data["instructions_path"]).is_file():
            errors.append("instructions_path: file does not exist relative to recipe")

    if recipe_path is not None and isinstance(data.get("evals"), str):
        if not (recipe_path.parent / data["evals"]).is_file():
            errors.append("evals: file does not exist relative to recipe")

    return errors


def _validate_action_contracts(
    data: dict[str, Any],
    capabilities: dict[str, Any],
    *,
    recipe_path: Path | None,
    errors: list[str],
) -> None:
    schema_version = data.get("recipe_schema_version")
    action_path = data.get("action_contracts_path", "")
    safety = data.get("safety_class")

    if not action_path:
        if schema_version == 2 and safety == "mutating":
            errors.append("action_contracts_path: required for schema v2 mutating recipes")
        return
    if schema_version != 2:
        errors.append("action_contracts_path: requires recipe_schema_version 2")
        return
    if not isinstance(action_path, str) or not action_path.strip():
        errors.append("action_contracts_path: must be a non-empty string")
        return
    if recipe_path is None:
        return

    actions_file = recipe_path.parent / action_path
    if not actions_file.is_file():
        errors.append("action_contracts_path: file does not exist relative to recipe")
        return

    try:
        action_data = load_yaml_file(actions_file)
    except Exception as exc:
        errors.append(f"action_contracts_path: failed to read YAML: {exc}")
        return

    actions = action_data.get("actions")
    if not isinstance(actions, list) or not actions:
        errors.append("actions.yaml actions: must be a non-empty list")
        return

    seen: set[str] = set()
    for index, action in enumerate(actions):
        prefix = f"actions[{index}]"
        if not isinstance(action, dict):
            errors.append(f"{prefix}: must be a mapping")
            continue
        action_id = action.get("id")
        if not isinstance(action_id, str) or not SLUG_RE.match(action_id):
            errors.append(f"{prefix}.id: must match ^[a-z][a-z0-9-]{{2,63}}$")
        elif action_id in seen:
            errors.append(f"{prefix}.id: duplicate action id {action_id!r}")
        else:
            seen.add(action_id)

        kind = action.get("kind")
        availability = action.get("availability", "available")
        if availability not in ACTION_AVAILABILITY:
            errors.append(f"{prefix}.availability: must be one of available, requires_adapter, unavailable")
        if kind not in ACTION_KINDS and availability != "unavailable":
            errors.append(f"{prefix}.kind: unsupported action kind {kind!r}")

        action_safety = action.get("safety_class")
        if action_safety not in SAFETY_CLASSES:
            errors.append(f"{prefix}.safety_class: must be one of read_only, dry_run, mutating")
        if action_safety == "mutating" and action.get("confirmation_required") is not True:
            errors.append(f"{prefix}.confirmation_required: mutating actions must require confirmation")

        required_capabilities = _list_of_strings(
            action.get("required_host_capabilities", []),
            f"{prefix}.required_host_capabilities",
            errors,
        )
        for capability in required_capabilities:
            if capability not in HOST_CAPABILITY_KEYS:
                errors.append(f"{prefix}.required_host_capabilities: unsupported capability {capability!r}")
            elif action_safety == "mutating" and availability == "available" and not bool(capabilities.get(capability, False)):
                errors.append(
                    f"{prefix}.required_host_capabilities.{capability}: "
                    "must be enabled in host_capabilities_required for available mutating actions"
                )

        for list_field in ("providers", "inputs", "outputs"):
            _list_of_strings(action.get(list_field, []), f"{prefix}.{list_field}", errors)


def _list_of_strings(value: Any, field: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{field}: must be a list of strings")
        return []
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{field}: entries must be non-empty strings")
        else:
            out.append(item)
    return out


def _validate_fields(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{field}: must be a non-empty list")
        return
    names: set[str] = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"{field}[{index}]: must be a mapping")
            continue
        name = item.get("name")
        kind = item.get("kind")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{field}[{index}].name: must be a non-empty string")
        elif name in names:
            errors.append(f"{field}[{index}].name: duplicate field {name!r}")
        else:
            names.add(name)
        if not isinstance(kind, str) or not kind.strip():
            errors.append(f"{field}[{index}].kind: must be a non-empty string")
        if "required" in item and not isinstance(item["required"], bool):
            errors.append(f"{field}[{index}].required: must be boolean")


def _validate_host_editions(value: Any, compatible_hosts: list[str], errors: list[str]) -> None:
    if value in (None, {}):
        return
    if not isinstance(value, dict):
        errors.append("host_editions: must be a mapping of host names to edition lists")
        return
    compatible_host_set = set(compatible_hosts)
    for host, editions in value.items():
        if host not in SUPPORTED_HOSTS:
            errors.append(f"host_editions: unsupported host {host!r}")
        elif host not in compatible_host_set:
            errors.append(f"host_editions.{host}: host must also appear in compatible_hosts")
        selected = _list_of_strings(editions, f"host_editions.{host}", errors)
        if not selected:
            errors.append(f"host_editions.{host}: must list at least one edition")
        for edition in selected:
            if edition not in SUPPORTED_EDITIONS:
                errors.append(f"host_editions.{host}: unsupported edition {edition!r}")
