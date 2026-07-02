"""Recipe schema and YAML serde for portable Endor agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class RecipeField:
    """One declared input or output field."""

    name: str
    kind: str
    required: bool = False
    description: str = ""


@dataclass(frozen=True)
class HostCapabilities:
    """Abstract host capabilities; compilers map these to host-specific tools."""

    run_commands: bool = False
    read_files: bool = False
    write_files: bool = False
    open_pr: bool = False


@dataclass(frozen=True)
class ActionContract:
    """One semantic runtime action declared by a recipe."""

    id: str
    kind: str
    safety_class: str
    confirmation_required: bool = False
    providers: tuple[str, ...] = ()
    required_host_capabilities: tuple[str, ...] = ()
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()
    availability: str = "available"
    notes: str = ""


@dataclass(frozen=True)
class EndorAgentRecipe:
    """Canonical v0 agent recipe.

    This is intentionally smaller than runtime AgentSpec. It describes a
    workflow prompt, required Endor transports, host capabilities, and IO
    contracts; it does not model graph topology.
    """

    recipe_schema_version: int
    id: str
    name: str
    version: str
    description: str
    safety_class: str
    supported_transports: tuple[str, ...]
    host_capabilities_required: HostCapabilities
    inputs: tuple[RecipeField, ...]
    outputs: tuple[RecipeField, ...]
    evals: str
    compatible_hosts: tuple[str, ...]
    host_editions: dict[str, tuple[str, ...]] = field(default_factory=dict)
    action_contracts_path: str = ""
    mutations: tuple[str, ...] = ()
    required_endor_mcp_tools: tuple[str, ...] = ()
    endorctl_api_invocations: tuple[str, ...] = ()
    endor_tier_minimum: str = "free"
    instructions_path: str = "instructions.md"
    model: str = ""
    requires_endor_mcp: str = ""
    requires_endorctl: str = ""
    audience: str = ""
    short_description: str = ""
    authors: tuple[str, ...] = ()
    policy_pack_support: bool = False


def load_yaml_file(path: str | Path) -> dict[str, Any]:
    """Load a YAML mapping from disk."""

    recipe_path = Path(path)
    with recipe_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Recipe must be a YAML mapping; got {type(data).__name__}")
    return data


def load_recipe(path: str | Path) -> EndorAgentRecipe:
    """Load and parse a recipe from YAML."""

    return recipe_from_dict(load_yaml_file(path))


def recipe_from_dict(data: dict[str, Any]) -> EndorAgentRecipe:
    """Parse a recipe mapping.

    Validation lives in :mod:`endor_agent_kit.validator`; this parser assumes
    the happy path and raises naturally when required fields are missing.
    """

    capabilities = data.get("host_capabilities_required") or {}
    if not isinstance(capabilities, dict):
        capabilities = {}

    return EndorAgentRecipe(
        recipe_schema_version=int(data["recipe_schema_version"]),
        id=str(data["id"]),
        name=str(data["name"]),
        version=str(data["version"]),
        description=str(data["description"]),
        safety_class=str(data["safety_class"]),
        supported_transports=tuple(str(v) for v in data.get("supported_transports", ())),
        host_capabilities_required=HostCapabilities(
            run_commands=bool(capabilities.get("run_commands", False)),
            read_files=bool(capabilities.get("read_files", False)),
            write_files=bool(capabilities.get("write_files", False)),
            open_pr=bool(capabilities.get("open_pr", False)),
        ),
        inputs=_fields_from_list(data.get("inputs", ())),
        outputs=_fields_from_list(data.get("outputs", ())),
        evals=str(data.get("evals", "")),
        compatible_hosts=tuple(str(v) for v in data.get("compatible_hosts", ())),
        host_editions=_host_editions_from_mapping(data.get("host_editions", {})),
        action_contracts_path=str(data.get("action_contracts_path", "")),
        mutations=tuple(str(v) for v in data.get("mutations", ())),
        required_endor_mcp_tools=tuple(str(v) for v in data.get("required_endor_mcp_tools", ())),
        endorctl_api_invocations=tuple(str(v) for v in data.get("endorctl_api_invocations", ())),
        endor_tier_minimum=str(data.get("endor_tier_minimum", "free")),
        instructions_path=str(data.get("instructions_path", "instructions.md")),
        model=str(data.get("model", "")),
        requires_endor_mcp=str(data.get("requires_endor_mcp", "")),
        requires_endorctl=str(data.get("requires_endorctl", "")),
        audience=str(data.get("audience", "")),
        short_description=str(data.get("short_description", "")),
        authors=tuple(str(author) for author in data.get("authors", ())),
        policy_pack_support=bool(data.get("policy_pack_support", False)),
    )


def recipe_to_dict(recipe: EndorAgentRecipe) -> dict[str, Any]:
    """Convert a recipe back to a JSON/YAML-friendly mapping."""

    return {
        "recipe_schema_version": recipe.recipe_schema_version,
        "id": recipe.id,
        "name": recipe.name,
        "version": recipe.version,
        "description": recipe.description,
        "safety_class": recipe.safety_class,
        "supported_transports": list(recipe.supported_transports),
        "host_capabilities_required": {
            "run_commands": recipe.host_capabilities_required.run_commands,
            "read_files": recipe.host_capabilities_required.read_files,
            "write_files": recipe.host_capabilities_required.write_files,
            "open_pr": recipe.host_capabilities_required.open_pr,
        },
        "inputs": [_field_to_dict(field) for field in recipe.inputs],
        "outputs": [_field_to_dict(field) for field in recipe.outputs],
        "evals": recipe.evals,
        "compatible_hosts": list(recipe.compatible_hosts),
        "host_editions": {
            host: list(editions)
            for host, editions in recipe.host_editions.items()
        },
        "action_contracts_path": recipe.action_contracts_path,
        "mutations": list(recipe.mutations),
        "required_endor_mcp_tools": list(recipe.required_endor_mcp_tools),
        "endorctl_api_invocations": list(recipe.endorctl_api_invocations),
        "endor_tier_minimum": recipe.endor_tier_minimum,
        "instructions_path": recipe.instructions_path,
        "model": recipe.model,
        "requires_endor_mcp": recipe.requires_endor_mcp,
        "requires_endorctl": recipe.requires_endorctl,
        "audience": recipe.audience,
        "short_description": recipe.short_description,
        "authors": list(recipe.authors),
        "policy_pack_support": recipe.policy_pack_support,
    }


def read_instructions(recipe_path: str | Path, recipe: EndorAgentRecipe) -> str:
    """Read the recipe's instruction file relative to the recipe path."""

    path = Path(recipe_path)
    instructions = path.parent / recipe.instructions_path
    return instructions.read_text(encoding="utf-8")


def load_action_contracts(recipe_path: str | Path, recipe: EndorAgentRecipe) -> tuple[ActionContract, ...]:
    """Load the recipe's optional action contracts."""

    if not recipe.action_contracts_path:
        return ()
    path = Path(recipe_path)
    data = load_yaml_file(path.parent / recipe.action_contracts_path)
    actions = data.get("actions", [])
    if not isinstance(actions, list):
        return ()
    return tuple(_action_from_mapping(action) for action in actions if isinstance(action, dict))


def editions_for_host(
    recipe: EndorAgentRecipe,
    host: str,
    default_editions: tuple[str, ...],
) -> tuple[str, ...]:
    """Return configured editions for a host, falling back to all host defaults."""

    return recipe.host_editions.get(host, default_editions)


def _fields_from_list(items: Any) -> tuple[RecipeField, ...]:
    if not isinstance(items, list):
        return ()
    fields: list[RecipeField] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        fields.append(
            RecipeField(
                name=str(item.get("name", "")),
                kind=str(item.get("kind", "")),
                required=bool(item.get("required", False)),
                description=str(item.get("description", "")),
            )
        )
    return tuple(fields)


def _host_editions_from_mapping(value: Any) -> dict[str, tuple[str, ...]]:
    if not isinstance(value, dict):
        return {}
    host_editions: dict[str, tuple[str, ...]] = {}
    for host, editions in value.items():
        if not isinstance(editions, list):
            continue
        host_editions[str(host)] = tuple(str(edition) for edition in editions)
    return host_editions


def _action_from_mapping(item: dict[str, Any]) -> ActionContract:
    return ActionContract(
        id=str(item.get("id", "")),
        kind=str(item.get("kind", "")),
        safety_class=str(item.get("safety_class", "")),
        confirmation_required=bool(item.get("confirmation_required", False)),
        providers=_tuple_of_strings(item.get("providers", ())),
        required_host_capabilities=_tuple_of_strings(item.get("required_host_capabilities", ())),
        inputs=_tuple_of_strings(item.get("inputs", ())),
        outputs=_tuple_of_strings(item.get("outputs", ())),
        availability=str(item.get("availability", "available")),
        notes=str(item.get("notes", "")),
    )


def _tuple_of_strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _field_to_dict(field: RecipeField) -> dict[str, Any]:
    return {
        "name": field.name,
        "kind": field.kind,
        "required": field.required,
        "description": field.description,
    }
