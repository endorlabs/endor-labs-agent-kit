"""Claude Code subagent compiler."""

from __future__ import annotations

import shutil
from pathlib import Path
from textwrap import dedent

from endor_agent_kit.recipe import (
    ActionContract,
    EndorAgentRecipe,
    editions_for_host,
    load_action_contracts,
    load_recipe,
    read_instructions,
)
from endor_agent_kit.validator import validate_recipe_file

EDITIONS = ("developer-edition", "enterprise-edition")
HOST = "claude-code"
LEGACY_EDITION_ALIASES = {
    "standard": "developer-edition",
    "extended": "enterprise-edition",
}
LEGACY_SECTION_NAMES = {
    "developer-edition": "standard",
    "enterprise-edition": "extended",
}
LEGACY_OUTPUT_DIRS = tuple(LEGACY_EDITION_ALIASES)
EDITION_CHOICES = EDITIONS + tuple(LEGACY_EDITION_ALIASES)
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

    recipe_file = Path(recipe_path)
    errors = validate_recipe_file(recipe_file)
    if errors:
        raise ValueError("\n".join(errors))

    recipe = load_recipe(recipe_file)
    instructions = read_instructions(recipe_file, recipe)
    actions = load_action_contracts(recipe_file, recipe)
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
        out_path.write_text(_render_subagent(recipe, instructions, actions, edition=item), encoding="utf-8")
        outputs.append(out_path)
    return outputs


def _normalize_edition(value: str) -> str:
    edition = LEGACY_EDITION_ALIASES.get(value, value)
    if edition not in EDITIONS:
        raise ValueError(f"Unknown Claude Code edition {value!r}; allowed: {', '.join(EDITIONS)}")
    return edition


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
    if edition == "developer-edition" or not recipe.host_capabilities_required.run_commands:
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
    if not _uses_mcp(recipe):
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
    if recipe.safety_class == "mutating":
        label = "This artifact" if single_edition else "Enterprise Edition"
        transport = (
            f"{label} may run commands, edit files, open change requests, and call "
            "authenticated Endor API/endorctl workflows when explicitly required."
        )
    elif edition == "developer-edition":
        if _uses_mcp(recipe):
            label = "This artifact" if single_edition else "Developer Edition"
            transport = f"{label} is MCP-only; do not use Bash or endorctl in this artifact."
        else:
            label = "This artifact" if single_edition else "Developer Edition"
            transport = f"{label} must not use Bash or authenticated endorctl."
    elif not _allows_read_only_endorctl(recipe):
        if _uses_mcp(recipe):
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


def _allows_read_only_endorctl(recipe: EndorAgentRecipe) -> bool:
    return "endorctl_api" in recipe.supported_transports and bool(recipe.endorctl_api_invocations)


def _uses_mcp(recipe: EndorAgentRecipe) -> bool:
    return (
        "mcp" in recipe.supported_transports
        or bool(recipe.required_endor_mcp_tools)
        or bool(recipe.requires_endor_mcp)
    )


def _disallowed_tools(recipe: EndorAgentRecipe) -> tuple[str, ...]:
    """Map abstract recipe capabilities to Claude Code tool restrictions."""

    if recipe.host_capabilities_required.write_files or recipe.host_capabilities_required.open_pr:
        allowed = READ_ONLY_FILE_TOOLS | {"Write", "Edit", "MultiEdit"}
    elif recipe.host_capabilities_required.read_files:
        allowed = READ_ONLY_FILE_TOOLS
    else:
        allowed = frozenset()
    if allowed:
        return tuple(tool for tool in READ_OR_WRITE_TOOLS if tool not in allowed)
    return READ_OR_WRITE_TOOLS


def _instructions_for_edition(instructions: str, edition: str) -> str:
    edition = _normalize_edition(edition)
    shared = _section(instructions, "shared")
    mode = _edition_section(instructions, edition)
    return f"{shared.rstrip()}\n\n{mode.rstrip()}\n"


def _instructions_for_variant(instructions: str, variant: str) -> str:
    """Compatibility wrapper for raw compiler/tests using old variant names."""

    return _instructions_for_edition(instructions, variant)


def _render_action_contracts(actions: tuple[ActionContract, ...]) -> str:
    if not actions:
        return ""
    lines = [
        "",
        "## Action Contracts",
        "",
        "These are the semantic side effects this agent may discuss or request.",
        "Do not claim an action completed unless the host performed it and returned evidence.",
        "",
    ]
    for action in actions:
        lines.extend([
            f"### {action.id}",
            "",
            f"- kind: `{action.kind}`",
            f"- safety_class: `{action.safety_class}`",
            f"- confirmation_required: `{str(action.confirmation_required).lower()}`",
            f"- availability: `{action.availability}`",
        ])
        if action.providers:
            lines.append(f"- providers: {', '.join(f'`{provider}`' for provider in action.providers)}")
        if action.required_host_capabilities:
            lines.append(
                "- required_host_capabilities: "
                + ", ".join(f"`{capability}`" for capability in action.required_host_capabilities)
            )
        if action.inputs:
            lines.append(f"- inputs: {', '.join(f'`{item}`' for item in action.inputs)}")
        if action.outputs:
            lines.append(f"- outputs: {', '.join(f'`{item}`' for item in action.outputs)}")
        if action.notes:
            lines.append(f"- notes: {action.notes}")
        lines.append("")
    return "\n".join(lines)


def _edition_section(text: str, edition: str) -> str:
    try:
        return _section(text, edition)
    except ValueError:
        legacy_name = LEGACY_SECTION_NAMES.get(edition)
        if legacy_name is not None:
            return _section(text, legacy_name)
        raise


def _section(text: str, name: str) -> str:
    start = f"<!-- {name}:start -->"
    end = f"<!-- {name}:end -->"
    try:
        after_start = text.split(start, 1)[1]
        return after_start.split(end, 1)[0].strip()
    except IndexError as exc:
        raise ValueError(f"instructions.md missing section markers for {name!r}") from exc


def _indent(text: str, spaces: int) -> str:
    pad = " " * spaces
    return "\n".join(f"{pad}{line}" if line else pad for line in text.splitlines())
