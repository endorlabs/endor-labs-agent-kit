"""Raw bundle compiler."""

from __future__ import annotations

import json
from pathlib import Path

from endor_agent_kit.compilers.claude_code import (
    EDITIONS,
    HOST as CLAUDE_CODE_HOST,
    _instructions_for_edition,
    _render_action_contracts,
    _uses_mcp,
)
from endor_agent_kit.recipe import (
    EndorAgentRecipe,
    editions_for_host,
    load_action_contracts,
    load_recipe,
    read_instructions,
)
from endor_agent_kit.validator import validate_recipe_file

LEGACY_RAW_PROMPTS = ("system-prompt-standard.md", "system-prompt-extended.md")


def compile_raw(recipe_path: str | Path) -> list[Path]:
    """Compile a recipe to raw prompt/setup artifacts."""

    recipe_file = Path(recipe_path)
    errors = validate_recipe_file(recipe_file)
    if errors:
        raise ValueError("\n".join(errors))

    recipe = load_recipe(recipe_file)
    instructions = read_instructions(recipe_file, recipe)
    actions = load_action_contracts(recipe_file, recipe)
    out_dir = recipe_file.parent / "dist" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    _remove_legacy_raw_prompts(out_dir)

    for edition in EDITIONS:
        stale = out_dir / f"system-prompt-{edition}.md"
        if stale.exists():
            stale.unlink()

    outputs = [
        _write(
            out_dir / f"system-prompt-{edition}.md",
            _instructions_for_edition(instructions, edition) + _render_action_contracts(actions),
        )
        for edition in editions_for_host(recipe, CLAUDE_CODE_HOST, EDITIONS)
    ]
    outputs.extend([
        _write(out_dir / "mcp-config.json", _mcp_config(recipe)),
        _write(out_dir / "endorctl-setup.md", _endorctl_setup(recipe)),
    ])
    return outputs


def _remove_legacy_raw_prompts(out_dir: Path) -> None:
    for name in LEGACY_RAW_PROMPTS:
        path = out_dir / name
        if path.exists():
            path.unlink()


def _write(path: Path, content: str) -> Path:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    return path


def _mcp_config(recipe: EndorAgentRecipe) -> str:
    if not _uses_mcp(recipe):
        return json.dumps(
            {
                "mcpServers": {},
                "required_tools": [],
                "requires_endor_mcp": "",
                "note": "This recipe does not require Endor MCP. Use the documented Endor API or endorctl paths instead.",
            },
            indent=2,
            sort_keys=True,
        )
    payload = {
        "mcpServers": {
            "endor-cli-tools": {
                "command": "npx",
                "args": ["-y", "endorctl", "ai-tools", "mcp-server"],
                "note": "Use an authenticated Enterprise configuration when enabling Enterprise-only tools.",
            }
        },
        "required_tools": list(recipe.required_endor_mcp_tools),
        "requires_endor_mcp": recipe.requires_endor_mcp,
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def _endorctl_setup(recipe: EndorAgentRecipe) -> str:
    invocations = "\n".join(f"- `{name}`" for name in recipe.endorctl_api_invocations) or "- none"
    if recipe.safety_class == "mutating":
        agent_label = recipe.name if recipe.name.lower().endswith("agent") else f"{recipe.name} agent"
        subject = (
            f"The {agent_label}"
            if len(editions_for_host(recipe, CLAUDE_CODE_HOST, EDITIONS)) == 1
            else f"The Enterprise Edition {recipe.name}"
        )
        lines = [
            "# Runtime Setup",
            "",
            f"{subject} preserves a mutating workflow.",
            "Use an authenticated Endor tenant plus local source-provider credentials",
            "before allowing patch or change-request steps.",
            "",
            f"Required endorctl version: `{recipe.requires_endorctl or 'latest recommended'}`",
            "",
            "The recipe documents these Endor lookup groups:",
            "",
            invocations,
            "",
            "The agent may also use git and source-provider CLIs such as `gh` or `glab`",
            "when the user asks it to apply patches, open a PR/MR, verify AppSec",
            "approval evidence, or post PR/MR comments. Confirm the target repository,",
            "base branch, generated diff, and change-request body before allowing",
            "those mutations.",
            "",
        ]
        if recipe.id == "ai-sast-triage":
            lines.extend([
                "For standalone exception policies, the agent must verify a GitHub/GitLab",
                "approval artifact from a configured AppSec approver, render the Endor",
                "policy spec, and get explicit confirmation before calling Endor API or",
                "`endorctl api` to create the policy.",
            ])
        elif recipe.id == "sca-remediation":
            lines.extend([
                "For SCA remediation, the agent must surface VersionUpgrade/UIA evidence",
                "before recommending a best first fix and must get separate confirmation",
                "before local file edits and before branch push or PR/MR creation.",
            ])
        return "\n".join(lines)
    if "endorctl_api" not in recipe.supported_transports or not recipe.endorctl_api_invocations:
        return "\n".join([
            "# endorctl Setup",
            "",
            f"The {recipe.name} artifacts do not require read-only `endorctl api` lookups.",
            "Use the generated Claude Code subagent with Endor MCP access.",
            "",
            "If a future edition adds tenant-aware Endor lookups, this file will document",
            "the exact read-only commands that are allowed.",
        ])
    return "\n".join([
        "# endorctl Setup",
        "",
        f"The Enterprise Edition {recipe.name} uses read-only Endor lookups",
        "through `endorctl api` for package scores, license classification, and",
        "similar-package signals. Install and authenticate `endorctl` before",
        "using the Enterprise Edition artifact.",
        "",
        f"Required version: `{recipe.requires_endorctl or 'latest recommended'}`",
        "",
        "The recipe documents these read-only API invocation groups:",
        "",
        invocations,
        "",
        "The only allowed `endorctl api create` call is the documented",
        "QuerySimilarPackages query-service lookup; every other v0 command must",
        "be a read-only list/get/query operation. If `endorctl` is missing,",
        "unauthenticated, or lacks access to a resource, the agent must record the",
        "affected signal in `data_gaps` and continue with the evidence it already",
        "gathered.",
    ])
