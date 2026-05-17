"""GitHub Copilot / AgentHQ plugin compiler."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from textwrap import dedent
from typing import Any

import yaml

from endor_agent_kit.compilers.claude_code import (
    EDITIONS,
    _allows_read_only_endorctl,
    _instructions_for_edition,
    _normalize_edition,
)
from endor_agent_kit.recipe import EndorAgentRecipe, editions_for_host, load_recipe, read_instructions
from endor_agent_kit.validator import validate_recipe_file

TARGET = "github-copilot-plugin"
MCP_SERVER_NAME = "endor-cli-tools"
EDITION_SLUGS = {
    "developer-edition": "developer",
    "enterprise-edition": "enterprise",
}


def compile_github_copilot_plugin(
    recipe_path: str | Path,
    *,
    edition: str | None = None,
    variant: str | None = None,
) -> list[Path]:
    """Compile a recipe to GitHub Copilot CLI / AgentHQ plugin packages."""

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
        editions_for_host(recipe, TARGET, EDITIONS)
        if selected_edition is None
        else (_normalize_edition(selected_edition),)
    )

    outputs: list[Path] = []
    for item in editions:
        out_dir = recipe_file.parent / "dist" / TARGET / item
        if out_dir.exists():
            shutil.rmtree(out_dir)
        agents_dir = out_dir / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)

        outputs.append(_write_json(out_dir / "plugin.json", _plugin_manifest(recipe, item)))
        agent_path = agents_dir / f"{recipe.id}.agent.md"
        outputs.append(_write_text(agent_path, _render_agent(recipe, instructions, item)))
        outputs.append(_write_text(out_dir / "README.md", _readme(recipe, item)))
    return outputs


def _plugin_manifest(recipe: EndorAgentRecipe, edition: str) -> dict[str, Any]:
    edition_slug = EDITION_SLUGS[edition]
    return {
        "name": f"endor-labs-{recipe.id}-{edition_slug}",
        "description": f"{recipe.name} {_edition_name(edition)} plugin for GitHub Copilot and AgentHQ.",
        "version": recipe.version,
        "author": {
            "name": "Endor Labs",
        },
        "keywords": _keywords(recipe),
        "category": "security",
        "agents": "agents/",
    }


def _render_agent(recipe: EndorAgentRecipe, instructions: str, edition: str) -> str:
    frontmatter = {
        "name": recipe.name,
        "description": _collapse_whitespace(recipe.description),
        "target": "github-copilot",
        "disable-model-invocation": True,
        "user-invocable": True,
        "tools": _tool_allowlist(recipe, edition),
        "mcp-servers": _mcp_servers(recipe, edition),
        "metadata": {
            "endor_agent_id": recipe.id,
            "endor_agent_version": recipe.version,
            "endor_edition": edition,
            "endor_recipe_schema_version": str(recipe.recipe_schema_version),
        },
    }
    header = yaml.safe_dump(frontmatter, sort_keys=False, width=1000).strip()
    body = _instructions_for_edition(instructions, edition).rstrip()
    return "\n".join([
        "---",
        header,
        "---",
        "",
        _compiler_notice(recipe, edition),
        "",
        body,
        "",
    ])


def _tool_allowlist(recipe: EndorAgentRecipe, edition: str) -> list[str]:
    tools = [f"{MCP_SERVER_NAME}/{tool}" for tool in recipe.required_endor_mcp_tools]
    if edition == "enterprise-edition" and _allows_read_only_endorctl(recipe):
        tools.append("execute")
    return tools


def _mcp_servers(recipe: EndorAgentRecipe, edition: str) -> dict[str, Any]:
    server: dict[str, Any] = {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "endorctl", "ai-tools", "mcp-server"],
    }
    if edition == "enterprise-edition":
        server["env"] = {
            "ENDOR_GITHUB_ACTION_TOKEN_ENABLE": "true",
            "ENDOR_NAMESPACE": "$COPILOT_MCP_ENDOR_NAMESPACE",
            "ENDOR_API": "${COPILOT_MCP_ENDOR_API:-https://api.endorlabs.com}",
        }
    server["tools"] = list(recipe.required_endor_mcp_tools) or ["*"]
    return {
        MCP_SERVER_NAME: {
            **server,
        }
    }


def _compiler_notice(recipe: EndorAgentRecipe, edition: str) -> str:
    if edition == "developer-edition":
        transport = "Developer Edition. MCP-only; no shell execution is enabled in this artifact."
    elif not _allows_read_only_endorctl(recipe):
        transport = "Enterprise Edition. MCP-only; this artifact does not enable shell execution."
    else:
        transport = (
            "Enterprise Edition. The `execute` tool is enabled only for the read-only "
            "Endor lookups documented in the prompt."
        )
    return dedent(
        f"""\
        > Generated from Endor Agent Kit recipe `{recipe.id}` v{recipe.version}.
        > {transport}
        """
    ).strip()


def _readme(recipe: EndorAgentRecipe, edition: str) -> str:
    edition_name = _edition_name(edition)
    plugin_name = _plugin_manifest(recipe, edition)["name"]
    shell_note = (
        "This package enables only the Endor MCP tools required by the agent."
        if edition == "developer-edition" or not _allows_read_only_endorctl(recipe)
        else "This package also enables Copilot's `execute` tool for the documented read-only Endor lookups."
    )
    keyless_note = (
        [
            "- The Endor MCP server is configured for GitHub Actions keyless auth. "
            "The target repository still needs the `copilot` environment and setup "
            "workflow described in `github-copilot-plugin/ENDOR_GITHUB_KEYLESS_AUTH.md`.",
        ]
        if edition == "enterprise-edition"
        else []
    )
    return "\n".join([
        f"# {recipe.name} {edition_name}",
        "",
        recipe.description.strip(),
        "",
        "## Install",
        "",
        "From this package directory:",
        "",
        "```bash",
        "copilot plugin install .",
        "```",
        "",
        f"Uninstall with `copilot plugin uninstall {plugin_name}`.",
        "",
        "## Notes",
        "",
        "- The custom agent is in `agents/` and embeds its Endor MCP server configuration.",
        f"- {shell_note}",
        *keyless_note,
        "- AgentHQ app wrapping and any OIDC token exchange endpoints are configured outside this generated package.",
        "",
    ])


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_text(path: Path, content: str) -> Path:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    return path


def _keywords(recipe: EndorAgentRecipe) -> list[str]:
    if recipe.id == "tenant-findings":
        return [
            "endor-labs",
            "security",
            "findings",
            "reachability",
            "github-copilot",
            "agenthq",
        ]
    return [
        "endor-labs",
        "security",
        "dependencies",
        "github-copilot",
        "agenthq",
    ]


def _collapse_whitespace(text: str) -> str:
    return " ".join(text.split())


def _edition_name(edition: str) -> str:
    return "Developer Edition" if edition == "developer-edition" else "Enterprise Edition"
