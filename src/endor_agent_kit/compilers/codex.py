"""Codex skill compiler."""

from __future__ import annotations

import shutil
from pathlib import Path
from textwrap import dedent

from endor_agent_kit.compilers.claude_code import (
    _indent,
    _instructions_for_edition,
    _render_action_contracts,
)
from endor_agent_kit.recipe import (
    EndorAgentRecipe,
    load_action_contracts,
    load_recipe,
    read_instructions,
)
from endor_agent_kit.safety_posture import source_recipe_safety_posture
from endor_agent_kit.validator import validate_recipe_file

HOST = "codex"
CODEX_SECTION_EDITION = "enterprise-edition"


def compile_codex(recipe_path: str | Path) -> list[Path]:
    """Compile a recipe to a Codex skill artifact."""

    recipe_file = Path(recipe_path)
    errors = validate_recipe_file(recipe_file)
    if errors:
        raise ValueError("\n".join(errors))

    recipe = load_recipe(recipe_file)
    instructions = read_instructions(recipe_file, recipe)
    actions = load_action_contracts(recipe_file, recipe)
    out_dir = recipe_file.parent / "dist" / HOST / recipe.id
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    skill = out_dir / "SKILL.md"
    skill.write_text(_render_skill(recipe, instructions, actions), encoding="utf-8")
    return [skill]


def _render_skill(recipe: EndorAgentRecipe, instructions: str, actions: tuple = ()) -> str:
    body = _codex_instruction_text(_instructions_for_edition(instructions, CODEX_SECTION_EDITION))
    return (
        "---\n"
        f"name: {recipe.id}\n"
        "description: |\n"
        f"{_indent(recipe.description.strip(), 2)}\n"
        "---\n\n"
        f"{_codex_notice(recipe)}\n\n"
        f"{_codex_host_contract(recipe)}\n\n"
        f"{body.rstrip()}\n"
        f"{_codex_instruction_text(_render_action_contracts(actions))}"
    )


def _codex_notice(recipe: EndorAgentRecipe) -> str:
    return dedent(
        f"""\
        # {recipe.name}

        Generated from Endor Agent Kit recipe `{recipe.id}` v{recipe.version} for Codex.
        Treat this skill as a source-first generated artifact; update the recipe and
        republish instead of hand-editing installed copies.
        """
    ).strip()


def _codex_host_contract(recipe: EndorAgentRecipe) -> str:
    posture = source_recipe_safety_posture(recipe)
    lines = [
        "## Codex Host Contract",
        "",
        "Use Codex terminal and file-editing tools only within the recipe safety contract.",
        "Do not claim that a command, file edit, branch push, PR/MR, comment, approval,",
        "or Endor policy write happened unless Codex performed it and captured evidence.",
        "",
    ]
    if posture.is_mutating:
        lines.extend(
            [
                "- Confirm the target repository, base branch, generated diff, validation plan, and PR/MR body before editing files, pushing branches, or opening change requests.",
                "- Treat file edits, branch pushes, PR/MR creation, PR/MR comments, and Endor policy writes as separate approval gates.",
                "- Never create or update an Endor policy until the policy spec is rendered, required AppSec approval evidence is verified, and the user explicitly confirms the write.",
                "- If credentials, Endor access, source-provider access, package-manager tooling, or repository state are missing, record the blocker in `data_gaps` instead of inventing evidence.",
            ]
        )
    else:
        lines.extend(
            [
                "- Keep the workflow read-only: do not edit files, run mutating package-manager commands, open change requests, post comments, or mutate Endor state.",
                "- If a read-only lookup is unavailable, record the missing signal in `data_gaps` and continue with verified evidence only.",
            ]
        )
    if not posture.can_run_commands:
        lines.append("- Do not run shell commands unless the user separately asks for local setup or installation work.")
    elif not posture.is_mutating:
        lines.append("- Shell commands, when used, must stay read-only and match documented Endor lookup shapes.")
    if not posture.can_write_files:
        lines.append("- Do not write source files as part of this agent workflow.")
    if not posture.can_open_change_requests:
        lines.append("- Do not create branches, commits, pushes, PRs, or MRs as part of this agent workflow.")
    return "\n".join(lines)


def _codex_instruction_text(text: str) -> str:
    """Adapt source host wording for Codex while preserving recipe semantics."""

    return (
        text.replace("Claude Code session", "Codex session")
        .replace("Claude Code artifact", "Codex skill")
        .replace("Claude Code workspace", "Codex workspace")
        .replace("Claude Code", "Codex")
    )
