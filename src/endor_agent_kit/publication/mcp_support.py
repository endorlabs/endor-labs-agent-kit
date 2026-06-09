"""Root MCP support files for the public distribution mirror."""

from __future__ import annotations

import json
from pathlib import Path

from endor_agent_kit.compilers.gemini import HOST as GEMINI_HOST
from endor_agent_kit.prepared_source_recipe import PreparedSourceRecipe

ENDOR_MCP_SERVER_NAME = "endor-cli-tools"
ENDOR_MCP_SERVER_COMMAND = "npx"
ENDOR_MCP_SERVER_ARGS = ["-y", "endorctl", "ai-tools", "mcp-server"]


def endor_mcp_server_config(*, include_type: bool) -> dict[str, object]:
    """Return the stdio Endor MCP server config used by host manifests."""

    config: dict[str, object] = {
        "command": ENDOR_MCP_SERVER_COMMAND,
        "args": ENDOR_MCP_SERVER_ARGS,
    }
    if include_type:
        config["type"] = "stdio"
    return config


def publish_root_mcp_support(
    prepared_recipes: list[PreparedSourceRecipe],
    destination: Path,
) -> tuple[Path, ...]:
    """Publish root compatibility files that expose optional Endor MCP setup."""

    gemini_recipes = [
        prepared
        for prepared in prepared_recipes
        if GEMINI_HOST in prepared.recipe.compatible_hosts
    ]
    if not gemini_recipes:
        return ()

    written: list[Path] = []

    mcp_config = destination / ".mcp.json"
    mcp_config.write_text(
        json.dumps(
            {
                "mcpServers": {
                    ENDOR_MCP_SERVER_NAME: endor_mcp_server_config(include_type=True),
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    written.append(mcp_config)

    gemini_context = destination / "GEMINI.md"
    gemini_context.write_text(_root_gemini_context(sorted(gemini_recipes, key=lambda item: item.recipe.id)), encoding="utf-8")
    written.append(gemini_context)

    gemini_manifest = destination / "gemini-extension.json"
    gemini_manifest.write_text(
        json.dumps(_root_gemini_extension_manifest(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    written.append(gemini_manifest)

    return tuple(written)


def _root_gemini_extension_manifest() -> dict[str, object]:
    return {
        "contextFileName": "GEMINI.md",
        "description": "Endor Labs Agent Kit setup and security workflow skills.",
        "displayName": "Endor Labs Agent Kit",
        "homepage": "https://www.endorlabs.com",
        "keywords": [
            "endor-labs",
            "security",
            "endorctl",
            "sca",
            "sast",
            "agentic remediation",
            "AppSec",
        ],
        "license": "MIT",
        "mcpServers": {
            ENDOR_MCP_SERVER_NAME: endor_mcp_server_config(include_type=False),
        },
        "name": "endor-labs-agent-kit",
        "publisher": "endorlabs",
        "repository": {
            "type": "git",
            "url": "https://github.com/endorlabs/ai-plugins",
        },
        "skills": {
            "path": "./skills",
        },
        "version": "0.1.0",
    }


def _root_gemini_context(prepared_recipes: list[PreparedSourceRecipe]) -> str:
    rows = [
        f"- {_workflow_label(prepared.recipe.id)}: use skill `{prepared.recipe.id}`."
        for prepared in prepared_recipes
    ]
    return "\n".join([
        "# Endor Labs Agent Kit Root Package",
        "",
        "Use Endor Labs Agent Kit workflows only within their generated safety",
        "contracts. Prefer documented Endor API or `endorctl api` lookups when a",
        "workflow supports them. Use Endor MCP only when a selected MCP-capable",
        "workflow needs it or the user explicitly asks for it.",
        "",
        "If setup, authentication, namespace, Endor MCP, `endorctl`, `gh`, or",
        "repository tooling is missing, use the `endor-agent-kit-setup` skill",
        "before live Endor work.",
        "",
        "User jobs mapped to root skills:",
        "",
        *rows,
        "",
        "Setup must not run scans, run `endorctl host-check`, edit shell profiles,",
        "auto-install `gh`, install language tooling, collect/write API secrets, or",
        "configure Endor MCP without explicit user approval.",
        "",
    ])


def _workflow_label(agent_id: str) -> str:
    labels = {
        "ai-sast-triage": "Triage AI SAST findings",
        "endor-troubleshooter": "Diagnose Endor setup and scan issues",
        "malware-response": "Malware Response",
        "probe-droid": "Assess GitHub onboarding gaps",
        "sca-remediation": "Find safe SCA remediation paths",
    }
    return labels.get(agent_id, agent_id.replace("-", " ").title())
