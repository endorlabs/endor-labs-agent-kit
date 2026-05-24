"""Claude Code subagent compiler."""

from __future__ import annotations

import shutil
from pathlib import Path
from textwrap import dedent

from endor_agent_kit.compilers.rendering import (
    EDITIONS,
    EDITION_CHOICES,
    LEGACY_EDITION_ALIASES,
    indent as _indent,
    instructions_for_edition as _instructions_for_edition,
    instructions_for_variant as _instructions_for_variant,
    normalize_edition as _normalize_edition,
    render_action_contracts as _render_action_contracts,
)
from endor_agent_kit.recipe import (
    ActionContract,
    EndorAgentRecipe,
    editions_for_host,
)
from endor_agent_kit.safety_posture import source_recipe_safety_posture
from endor_agent_kit.prepared_source_recipe import PreparedSourceRecipe, prepare_source_recipe

HOST = "claude-code"
LEGACY_OUTPUT_DIRS = tuple(LEGACY_EDITION_ALIASES)
READ_OR_WRITE_TOOLS = (
    "Task",
    "Agent",
    "Read",
    "Write",
    "Edit",
    "MultiEdit",
    "Glob",
    "Grep",
    "LS",
    "NotebookRead",
    "NotebookEdit",
    "WebFetch",
    "WebSearch",
    "TodoWrite",
)
READ_ONLY_FILE_TOOLS = frozenset({"Read", "Glob", "Grep", "LS"})


def compile_claude_code(
    recipe_path: str | Path,
    *,
    edition: str | None = None,
    variant: str | None = None,
) -> list[Path]:
    """Compile a recipe to Claude Code subagent markdown.

    If ``edition`` is omitted, both v0 editions are generated.

    ``variant`` is kept as a compatibility alias for pre-edition callers.
    """

    if edition is not None and variant is not None:
        raise ValueError("Use only one of edition or variant")

    return compile_claude_code_prepared(
        prepare_source_recipe(recipe_path),
        edition=edition,
        variant=variant,
    )


def compile_claude_code_prepared(
    prepared: PreparedSourceRecipe,
    *,
    edition: str | None = None,
    variant: str | None = None,
) -> list[Path]:
    """Compile a prepared Source Recipe to Claude Code subagent markdown."""

    if edition is not None and variant is not None:
        raise ValueError("Use only one of edition or variant")

    recipe_file = prepared.path
    recipe = prepared.recipe
    selected_edition = edition if edition is not None else variant
    editions = (
        editions_for_host(recipe, HOST, EDITIONS)
        if selected_edition is None
        else (_normalize_edition(selected_edition),)
    )
    outputs: list[Path] = []
    _remove_legacy_output_dirs(recipe_file.parent / "dist" / "claude-code")
    for item in EDITIONS:
        if item not in editions:
            shutil.rmtree(recipe_file.parent / "dist" / HOST / item, ignore_errors=True)
    for item in editions:
        out_dir = recipe_file.parent / "dist" / HOST / item
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{recipe.id}.md"
        out_path.write_text(
            _render_subagent(recipe, prepared.instructions, prepared.actions, edition=item),
            encoding="utf-8",
        )
        outputs.append(out_path)
    return outputs


def _remove_legacy_output_dirs(out_dir: Path) -> None:
    for name in LEGACY_OUTPUT_DIRS:
        path = out_dir / name
        if path.is_dir():
            shutil.rmtree(path)


def _render_subagent(
    recipe: EndorAgentRecipe,
    instructions: str,
    actions: tuple[ActionContract, ...] = (),
    *,
    edition: str,
) -> str:
    body = _instructions_for_edition(instructions, edition)
    action_contracts = _render_action_contracts(actions)
    disallowed_tools = _disallowed_tools(recipe)
    posture = source_recipe_safety_posture(recipe)
    if edition == "developer-edition" or not posture.can_run_commands:
        disallowed_tools = ("Bash",) + disallowed_tools

    return (
        "---\n"
        f"name: {recipe.id}\n"
        "description: |\n"
        f"{_indent(recipe.description.strip(), 2)}\n"
        f"{_mcp_server_frontmatter(recipe)}"
        f"disallowedTools: {', '.join(disallowed_tools)}\n"
        f"model: {recipe.model}\n"
        "---\n\n"
        f"{_compiler_notice(recipe, edition)}\n\n"
        f"{body.rstrip()}\n"
        f"{action_contracts}"
    )


def _mcp_server_frontmatter(recipe: EndorAgentRecipe) -> str:
    posture = source_recipe_safety_posture(recipe)
    if not posture.uses_mcp:
        return ""
    return (
        "mcpServers:\n"
        "  - endor-cli-tools:\n"
        "      type: stdio\n"
        "      command: npx\n"
        '      args: ["-y", "endorctl", "ai-tools", "mcp-server"]\n'
        "      alwaysLoad: true\n"
    )


def _compiler_notice(recipe: EndorAgentRecipe, edition: str) -> str:
    single_edition = len(editions_for_host(recipe, HOST, EDITIONS)) == 1
    posture = source_recipe_safety_posture(recipe)
    if posture.is_mutating:
        label = "This artifact" if single_edition else "Enterprise Edition"
        transport = (
            f"{label} may run commands, edit files, open change requests, and call "
            "authenticated Endor API/endorctl workflows when explicitly required."
        )
    elif edition == "developer-edition":
        if posture.uses_mcp:
            label = "This artifact" if single_edition else "Developer Edition"
            transport = f"{label} is MCP-only; do not use Bash or endorctl in this artifact."
        else:
            label = "This artifact" if single_edition else "Developer Edition"
            transport = f"{label} must not use Bash or authenticated endorctl."
    elif not posture.uses_endorctl_api:
        if posture.uses_mcp:
            label = "This artifact" if single_edition else "Enterprise Edition"
            transport = f"{label} is MCP-only; it does not require Bash or endorctl."
        else:
            label = "This artifact" if single_edition else "Enterprise Edition"
            transport = f"{label} does not require Bash or endorctl."
    else:
        label = "This artifact" if single_edition else "Enterprise Edition"
        transport = (
            f"{label} allows Bash only for read-only Endor lookups "
            "through `endorctl api`."
        )
    return dedent(
        f"""\
        > Generated from Endor Agent Kit recipe `{recipe.id}` v{recipe.version}.
        > {transport}
        """
    ).strip()


def _disallowed_tools(recipe: EndorAgentRecipe) -> tuple[str, ...]:
    """Map abstract recipe capabilities to Claude Code tool restrictions."""

    posture = source_recipe_safety_posture(recipe)
    if posture.can_write_files or posture.can_open_change_requests:
        allowed = READ_ONLY_FILE_TOOLS | {"Write", "Edit", "MultiEdit"}
    elif posture.can_read_files:
        allowed = READ_ONLY_FILE_TOOLS
    else:
        allowed = frozenset()
    if allowed:
        return tuple(tool for tool in READ_OR_WRITE_TOOLS if tool not in allowed)
    return READ_OR_WRITE_TOOLS
