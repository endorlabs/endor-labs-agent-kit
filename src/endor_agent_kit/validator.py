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
SUPPORTED_HOSTS = frozenset({"claude-code", "claude-managed-agents", "github-copilot-plugin", "raw"})
SUPPORTED_EDITIONS = frozenset({"developer-edition", "enterprise-edition"})
SAFETY_CLASSES = frozenset({"read_only", "dry_run", "mutating"})
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
    if schema_version != 1:
        errors.append("recipe_schema_version: only version 1 is supported in v0")

    recipe_id = data.get("id", "")
    if not isinstance(recipe_id, str) or not SLUG_RE.match(recipe_id):
        errors.append("id: must match ^[a-z][a-z0-9-]{2,63}$")

    safety = data.get("safety_class")
    if safety not in SAFETY_CLASSES:
        errors.append("safety_class: must be one of read_only, dry_run, mutating")
    elif safety != "read_only":
        errors.append("safety_class: v0 launch recipes must be read_only; dry_run/mutating land later")

    mutations = data.get("mutations")
    if mutations is None:
        pass
    elif not isinstance(mutations, list):
        errors.append("mutations: must be a list")
    elif mutations:
        errors.append("mutations: v0 recipes must leave this reserved field empty")

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
