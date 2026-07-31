"""Source Recipe authoring checks for public Agent Kit agents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from endor_agent_kit.adversarial_evals import adversarial_eval_errors
from endor_agent_kit.instruction_sections import parse_instruction_sections
from endor_agent_kit.recipe import load_action_contracts, load_recipe, load_yaml_file
from endor_agent_kit.validator import validate_recipe_file

NEW_AGENT_MIN_EVAL_CASES = 4


@dataclass(frozen=True)
class SourceAuthoringIssue:
    """One Source Recipe authoring issue."""

    code: str
    message: str
    path: Path | None = None


@dataclass(frozen=True)
class SourceRecipeAuthoringReport:
    """Authoring check result for one Source Recipe."""

    recipe_path: Path
    agent_id: str
    source_dir: Path
    errors: tuple[SourceAuthoringIssue, ...]
    warnings: tuple[SourceAuthoringIssue, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors


def check_source_recipe_authoring(
    recipe_path: str | Path,
    *,
    new_agent: bool = False,
) -> SourceRecipeAuthoringReport:
    """Check repeatable Source Recipe authoring invariants."""

    path = Path(recipe_path)
    errors: list[SourceAuthoringIssue] = []
    warnings: list[SourceAuthoringIssue] = []

    for message in validate_recipe_file(path):
        errors.append(SourceAuthoringIssue("recipe.validation", message, path))

    try:
        data = load_yaml_file(path)
    except Exception:
        return SourceRecipeAuthoringReport(
            recipe_path=path,
            agent_id="",
            source_dir=path.parent,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )

    agent_id = str(data.get("id") or "")
    _check_source_layout(path, agent_id, new_agent=new_agent, errors=errors)
    _check_instructions(path.parent, data, errors=errors)
    _check_eval_cases(path.parent, data, new_agent=new_agent, errors=errors)
    _check_architecture(path.parent, new_agent=new_agent, errors=errors)
    _check_transport_authoring(path.parent, data, errors=errors)
    _check_mutating_authoring(path, data, errors=errors)

    return SourceRecipeAuthoringReport(
        recipe_path=path,
        agent_id=agent_id,
        source_dir=path.parent,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def _check_source_layout(
    recipe_path: Path,
    agent_id: str,
    *,
    new_agent: bool,
    errors: list[SourceAuthoringIssue],
) -> None:
    if recipe_path.name != "recipe.yaml":
        errors.append(
            SourceAuthoringIssue(
                "layout.recipe_filename",
                "Source Recipe file must be named recipe.yaml",
                recipe_path,
            )
        )
    if agent_id and recipe_path.parent.name != agent_id:
        errors.append(
            SourceAuthoringIssue(
                "layout.agent_directory",
                "Source Recipe directory name must match recipe id",
                recipe_path.parent,
            )
        )
    if new_agent and not _is_source_agents_layout(recipe_path, agent_id):
        errors.append(
            SourceAuthoringIssue(
                "layout.source_agents",
                "New agents must live at source/agents/<agent-id>/recipe.yaml",
                recipe_path,
            )
        )


def _is_source_agents_layout(recipe_path: Path, agent_id: str) -> bool:
    if not agent_id:
        return False
    return (
        recipe_path.name == "recipe.yaml"
        and recipe_path.parent.name == agent_id
        and recipe_path.parent.parent.name == "agents"
        and recipe_path.parent.parent.parent.name == "source"
    )


def _check_instructions(
    source_dir: Path,
    data: dict[str, Any],
    *,
    errors: list[SourceAuthoringIssue],
) -> None:
    instructions_path = source_dir / str(data.get("instructions_path") or "instructions.md")
    if not instructions_path.is_file():
        return
    instructions = instructions_path.read_text(encoding="utf-8")
    try:
        parse_instruction_sections(instructions)
    except ValueError as exc:
        errors.append(
            SourceAuthoringIssue(
                "instructions.section",
                str(exc),
                instructions_path,
            )
        )


def _check_eval_cases(
    source_dir: Path,
    data: dict[str, Any],
    *,
    new_agent: bool,
    errors: list[SourceAuthoringIssue],
) -> None:
    evals_path = source_dir / str(data.get("evals") or "evals/cases.yaml")
    if not evals_path.is_file():
        return
    try:
        evals_data = load_yaml_file(evals_path)
    except Exception as exc:
        errors.append(
            SourceAuthoringIssue(
                "evals.yaml",
                f"eval cases must be readable YAML: {exc}",
                evals_path,
            )
        )
        return
    cases = evals_data.get("cases")
    if not isinstance(cases, list) or not cases:
        errors.append(
            SourceAuthoringIssue(
                "evals.cases",
                "evals/cases.yaml must contain a non-empty cases list",
                evals_path,
            )
        )
        return
    if new_agent and len(cases) < NEW_AGENT_MIN_EVAL_CASES:
        errors.append(
            SourceAuthoringIssue(
                "evals.minimum_cases",
                f"new agents must include at least {NEW_AGENT_MIN_EVAL_CASES} eval cases",
                evals_path,
            )
        )
    seen_ids: set[str] = set()
    for index, case in enumerate(cases):
        prefix = f"cases[{index}]"
        if not isinstance(case, dict):
            errors.append(
                SourceAuthoringIssue("evals.case", f"{prefix}: must be a mapping", evals_path)
            )
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            errors.append(
                SourceAuthoringIssue(
                    "evals.case_id",
                    f"{prefix}.id: must be a non-empty string",
                    evals_path,
                )
            )
        elif case_id in seen_ids:
            errors.append(
                SourceAuthoringIssue(
                    "evals.case_id",
                    f"{prefix}.id: duplicate case id {case_id!r}",
                    evals_path,
                )
            )
        else:
            seen_ids.add(case_id)
        expected = case.get("expected")
        if not isinstance(expected, dict) or not expected:
            errors.append(
                SourceAuthoringIssue(
                    "evals.expected",
                    f"{prefix}.expected: must be a non-empty mapping",
                    evals_path,
                )
            )
            continue
        if new_agent:
            required_evidence = expected.get("required_evidence")
            if not isinstance(required_evidence, list) or not required_evidence:
                errors.append(
                    SourceAuthoringIssue(
                        "evals.required_evidence",
                        f"{prefix}.expected.required_evidence: must be a non-empty list",
                        evals_path,
                    )
                )
            if not isinstance(expected.get("data_gaps_allowed"), bool):
                errors.append(
                    SourceAuthoringIssue(
                        "evals.data_gaps_allowed",
                        f"{prefix}.expected.data_gaps_allowed: must be boolean",
                        evals_path,
                    )
                )

    for message in adversarial_eval_errors(cases):
        errors.append(SourceAuthoringIssue("evals.adversarial", message, evals_path))


def _check_architecture(
    source_dir: Path,
    *,
    new_agent: bool,
    errors: list[SourceAuthoringIssue],
) -> None:
    architecture_path = source_dir / "architecture.svg"
    if not architecture_path.is_file():
        if new_agent:
            errors.append(
                SourceAuthoringIssue(
                    "architecture.required",
                    "new agents must include architecture.svg",
                    architecture_path,
                )
            )
        return

    architecture = architecture_path.read_text(encoding="utf-8")
    required_tokens = ("<svg", 'viewBox="0 0 1280 ', "radialGradient", "cardGlass")
    for token in required_tokens:
        if token not in architecture:
            errors.append(
                SourceAuthoringIssue(
                    "architecture.format",
                    f"architecture.svg must use the Agent Kit visual format token {token!r}",
                    architecture_path,
                )
            )
    if new_agent and "CONTRACT" not in architecture:
        errors.append(
            SourceAuthoringIssue(
                "architecture.contract_band",
                "new agent architecture.svg must include a bottom contract band",
                architecture_path,
            )
        )


def _check_transport_authoring(
    source_dir: Path,
    data: dict[str, Any],
    *,
    errors: list[SourceAuthoringIssue],
) -> None:
    transports = _strings(data.get("supported_transports"))
    mcp_tools = _strings(data.get("required_endor_mcp_tools"))
    recipe_path = source_dir / "recipe.yaml"
    if "mcp" not in transports and mcp_tools:
        errors.append(
            SourceAuthoringIssue(
                "transport.mcp_tools_without_mcp",
                "required_endor_mcp_tools must be empty unless supported_transports includes mcp",
                recipe_path,
            )
        )
    if "endorctl_agent_api" not in transports or "mcp" in transports:
        return
    if str(data.get("requires_endor_mcp") or ""):
        errors.append(
            SourceAuthoringIssue(
                "transport.mcp_free_requires_mcp",
                "MCP-free endorctl_agent_api agents must leave requires_endor_mcp empty",
                recipe_path,
            )
        )
    instructions_path = source_dir / str(data.get("instructions_path") or "instructions.md")
    if not instructions_path.is_file():
        return
    instructions = instructions_path.read_text(encoding="utf-8")
    if "Endor MCP server" not in instructions:
        errors.append(
            SourceAuthoringIssue(
                "transport.mcp_free_instruction",
                "MCP-free endorctl_agent_api agents must explicitly say not to require "
                "an Endor MCP server",
                instructions_path,
            )
        )


def _check_mutating_authoring(
    recipe_path: Path,
    data: dict[str, Any],
    *,
    errors: list[SourceAuthoringIssue],
) -> None:
    if data.get("safety_class") != "mutating":
        return
    has_actions_file = (
        data.get("recipe_schema_version") == 2
        and data.get("action_contracts_path") == "actions.yaml"
    )
    if not has_actions_file:
        errors.append(
            SourceAuthoringIssue(
                "actions.required_for_mutating",
                "mutating agents must use recipe_schema_version 2 with "
                "action_contracts_path: actions.yaml",
                recipe_path,
            )
        )
        return
    try:
        recipe = load_recipe(recipe_path)
        actions = load_action_contracts(recipe_path, recipe)
    except Exception:
        return
    if not any(action.safety_class == "mutating" for action in actions):
        errors.append(
            SourceAuthoringIssue(
                "actions.mutating_action",
                "mutating agents must declare at least one mutating action contract",
                recipe_path.parent / "actions.yaml",
            )
        )


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))
