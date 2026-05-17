"""Claude Managed Agents compiler."""

from __future__ import annotations

import shutil
from pathlib import Path
from textwrap import dedent

import yaml

from endor_agent_kit.compilers.claude_code import (
    EDITIONS,
    _allows_read_only_endorctl,
    _instructions_for_edition,
    _normalize_edition,
)
from endor_agent_kit.recipe import EndorAgentRecipe, editions_for_host, load_recipe, read_instructions
from endor_agent_kit.validator import validate_recipe_file

HOST = "claude-managed-agents"
ENDOR_MCP_SERVER_NAME = "endor"
ENDOR_MCP_SERVER_URL_PLACEHOLDER = "https://YOUR-ENDOR-MCP-SERVER.example.com/mcp"
MODEL_ALIASES = {
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-7",
}


class LiteralString(str):
    """String that PyYAML should emit with block-literal style."""


def _literal_representer(dumper: yaml.SafeDumper, data: LiteralString) -> yaml.nodes.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


yaml.SafeDumper.add_representer(LiteralString, _literal_representer)


def compile_claude_managed_agents(
    recipe_path: str | Path,
    *,
    edition: str | None = None,
    variant: str | None = None,
) -> list[Path]:
    """Compile a recipe to Claude Managed Agents configuration templates."""

    if edition is not None and variant is not None:
        raise ValueError("Use only one of edition or variant")

    recipe_file = Path(recipe_path)
    errors = validate_recipe_file(recipe_file)
    if errors:
        raise ValueError("\n".join(errors))

    recipe = load_recipe(recipe_file)
    instructions = read_instructions(recipe_file, recipe)
    selected_edition = edition if edition is not None else variant
    editions = (
        editions_for_host(recipe, HOST, EDITIONS)
        if selected_edition is None
        else (_normalize_edition(selected_edition),)
    )

    out_root = recipe_file.parent / "dist" / HOST
    if out_root.exists() and selected_edition is None:
        shutil.rmtree(out_root)

    outputs: list[Path] = []
    for item in editions:
        out_dir = out_root / item
        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        agent = out_dir / "agent.yaml"
        agent.write_text(_yaml(_agent_config(recipe, instructions, item)), encoding="utf-8")
        outputs.append(agent)

        environment = out_dir / "environment.yaml"
        environment.write_text(_yaml(_environment_config(recipe, item)), encoding="utf-8")
        outputs.append(environment)

        session = out_dir / "session-template.yaml"
        session.write_text(_yaml(_session_template(recipe)), encoding="utf-8")
        outputs.append(session)

    return outputs


def _agent_config(recipe: EndorAgentRecipe, instructions: str, edition: str) -> dict:
    config = {
        "name": f"{recipe.name} {_edition_name(edition)}",
        "description": LiteralString(recipe.description.strip() + "\n"),
        "model": _managed_model(recipe.model),
        "system": LiteralString(_managed_system(recipe, instructions, edition)),
        "mcp_servers": _mcp_servers(recipe),
        "tools": _tools(recipe, edition),
        "skills": [],
        "metadata": {
            "endor_agent_kit_recipe_id": recipe.id,
            "endor_agent_kit_recipe_version": recipe.version,
            "endor_agent_kit_host": HOST,
            "endor_agent_kit_edition": edition,
        },
    }
    return config


def _managed_model(model: str) -> str:
    return MODEL_ALIASES.get(model, model)


def _managed_system(recipe: EndorAgentRecipe, instructions: str, edition: str) -> str:
    body = _instructions_for_edition(instructions, edition)
    if edition == "developer-edition":
        transport = (
            "Managed Agents Developer Edition. Use Endor MCP tools only. "
            "Do not use Bash, filesystem, web, or mutating tools."
        )
    elif not _allows_read_only_endorctl(recipe):
        transport = (
            "Managed Agents Enterprise Edition. This agent is MCP-only for this recipe. "
            "Do not use Bash, filesystem, web, or mutating tools."
        )
    else:
        transport = (
            "Managed Agents Enterprise Edition. Use Endor MCP first. Bash is available "
            "only for the documented read-only `endorctl api` lookups in these instructions."
        )
    intro = dedent(
        f"""\
        Generated from Endor Agent Kit recipe `{recipe.id}` v{recipe.version}.
        {transport}

        The Managed Agents host runs in an Anthropic-managed environment. MCP
        servers must be remote URL servers declared in `mcp_servers`; credentials
        must be supplied at session creation through an Anthropic credential vault.
        If an expected MCP server, vault, credential, account tier, or command is
        unavailable, record the missing signal in `data_gaps` instead of inventing
        evidence.
        """
    ).strip()
    return f"{intro}\n\n{body.rstrip()}\n"


def _mcp_servers(recipe: EndorAgentRecipe) -> list[dict]:
    if "mcp" not in recipe.supported_transports:
        return []
    return [
        {
            "type": "url",
            "name": ENDOR_MCP_SERVER_NAME,
            "url": ENDOR_MCP_SERVER_URL_PLACEHOLDER,
        }
    ]


def _tools(recipe: EndorAgentRecipe, edition: str) -> list[dict]:
    tools: list[dict] = []
    if "mcp" in recipe.supported_transports:
        tools.append({
            "type": "mcp_toolset",
            "mcp_server_name": ENDOR_MCP_SERVER_NAME,
            "default_config": {
                "permission_policy": {
                    "type": "always_ask",
                }
            },
        })

    if edition == "enterprise-edition" and _allows_read_only_endorctl(recipe):
        tools.append({
            "type": "agent_toolset_20260401",
            "default_config": {
                "enabled": False,
                "permission_policy": {
                    "type": "always_ask",
                },
            },
            "configs": [
                {
                    "name": "bash",
                    "enabled": True,
                    "permission_policy": {
                        "type": "always_ask",
                    },
                }
            ],
        })
    return tools


def _environment_config(recipe: EndorAgentRecipe, edition: str) -> dict:
    config = {
        "name": f"endor-{recipe.id}-{edition}",
        "config": {
            "type": "cloud",
            "networking": {
                "type": "limited",
                "allowed_hosts": ["https://api.endorlabs.com"],
                "allow_mcp_servers": True,
                "allow_package_managers": False,
            },
        },
    }
    if edition == "enterprise-edition" and _allows_read_only_endorctl(recipe):
        config["config"]["packages"] = {"npm": ["endorctl"]}
        config["config"]["networking"]["allow_package_managers"] = True
    return config


def _session_template(recipe: EndorAgentRecipe) -> dict:
    template: dict = {
        "agent": "<AGENT_ID>",
        "environment_id": "<ENVIRONMENT_ID>",
    }
    if "mcp" in recipe.supported_transports:
        template["vault_ids"] = ["<ENDOR_MCP_VAULT_ID>"]
    return template


def _edition_name(edition: str) -> str:
    return {
        "developer-edition": "Developer Edition",
        "enterprise-edition": "Enterprise Edition",
    }[edition]


def _yaml(payload: dict) -> str:
    return yaml.safe_dump(payload, sort_keys=False, default_flow_style=False, allow_unicode=False)
