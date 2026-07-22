"""Endor Knowledge Pack loading, validation, and prompt rendering."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shlex
from typing import Any

import yaml

from endor_agent_kit.agent_api import agent_api_command_errors
from endor_agent_kit.endor_api_registry import endor_api_template_errors


PACK_SECTION_HEADING = "## Endor Knowledge Pack"
PACK_SCHEMA_VERSION = 1
SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{2,63}$")
FORBIDDEN_VISIBLE_TERMS = (
    "pip install " + "endorlabs",
    "python " + "package",
    "external client " + "package",
)
APPROVED_GROUP_AGGREGATION_PATHS = {
    "Finding": frozenset(
        {
            "spec.level",
            "spec.target_dependency_package_name",
        }
    ),
}
REQUIRED_PRECEDENCE_MARKERS = (
    "workflow output contracts",
    "source recipe instructions",
    "Endor Knowledge Pack",
)
REQUIRED_GLOBAL_RULE_IDS = (
    "context-first",
    "namespace-provenance",
    "query-efficiency",
    "verified-evidence",
    "data-gaps",
)
REQUIRED_WORKFLOW_FIELDS = (
    "agent_id",
    "title",
    "summary",
    "resources",
    "retrieval_steps",
    "fallbacks",
    "data_gaps",
    "evidence_query_plans",
    "evidence_query_recipes",
)
REQUIRED_TASK_PROFILE_FIELDS = (
    "id",
    "title",
    "summary",
    "when_to_use",
    "minimal_evidence",
    "stop_when",
    "output_focus",
)
REQUIRED_EVIDENCE_QUERY_PLAN_FIELDS = (
    "profile_id",
    "title",
    "objective",
    "query_order",
    "avoid",
    "stop_after",
    "data_gaps",
)
REQUIRED_EVIDENCE_QUERY_RECIPE_FIELDS = (
    "profile_id",
    "id",
    "resource",
    "purpose",
    "template",
    "fields",
    "constraints",
)
REQUIRED_CANONICAL_QUERY_RECIPE_FIELDS = (
    "id",
    "title",
    "resource",
    "purpose",
    "template",
    "fields",
    "constraints",
    "completeness",
)
EVIDENCE_GATE_RULES = (
    "Never use memory, examples, older sessions, or prior repos as namespace, repo, project, finding, or package provenance.",
    "Never dump or `cat` Endor config files; extract only the namespace key.",
    "Never guess repo URLs, project UUIDs, finding counts, package versions, scan state, or VersionUpgrade/UIA/CIA evidence.",
    "Treat local docs and repository files as context until current Endor or user-provided evidence backs them.",
    "Every scoped Endor gate must record `namespace_provenance` from user input, environment, default config, or project metadata.",
    "Every evidence gate must return required JSON with precise `data_gaps` for missing, stale, unavailable, or blocked evidence.",
    "If required user inputs are missing in a noninteractive or final-answer context, return the required JSON shape with `data_gaps` instead of asking a prose-only follow-up.",
    "Final answers must summarize query intent, selectors, and field masks instead of echoing raw `endorctl agent api` command strings.",
)
SCOPE_NORMALIZATION_RULES = (
    "Normalize repository selectors to `owner/repo` or the equivalent source-provider full path before Endor project lookup.",
    "Record branch provenance: GitHub default branch, selected branch, Endor monitored branch, and any mismatch that affects main-context evidence.",
    "When `project_resolution.status` is `resolved`, include project UUID, namespace, namespace provenance, normalized repo identity, branch provenance, and whether `--traverse` was attempted.",
    "If a parent namespace project lookup misses, retry the same selector with traversal before reporting the project missing.",
)
MUTABILITY_GATE_RULES = (
    "Read-only agents must not edit files, create branches, push commits, open PRs, post comments, run scans, or perform Endor/source-provider writes.",
    "When a useful next step is mutating, return a future action contract with owner, reason, expected effect, validation step, and `confirmation_required: true`.",
    "Plan-capable agents must separate local edits, source-provider writes, and Endor writes; each requires explicit approval before action.",
)
COMPACT_EVIDENCE_GATE_RULES = (
    "Never use memory/prior sessions for namespace/repo/project/finding/package provenance.",
    "Never dump or `cat` Endor config files; read only namespace key.",
    "Never guess repo/project/finding/package/scan/VersionUpgrade/UIA/CIA evidence.",
    "Local docs require current Endor/user evidence.",
    "Record `namespace_provenance`, repo, branch, traverse, `data_gaps`.",
    "Missing inputs in noninteractive/final answer: return required JSON with `data_gaps`.",
    "Read-only: no edits/scans/PRs/comments/writes.",
    "No raw commands in final.",
)


@dataclass(frozen=True)
class KnowledgeRule:
    """One compact global rule available to generated agents."""

    id: str
    title: str
    guidance: str


@dataclass(frozen=True)
class KnowledgeResource:
    """One Endor resource and the reason an agent should query it."""

    name: str
    purpose: str
    fields: tuple[str, ...]


@dataclass(frozen=True)
class KnowledgeTaskProfile:
    """One compact operating mode for an agent."""

    id: str
    title: str
    summary: str
    when_to_use: tuple[str, ...]
    minimal_evidence: tuple[str, ...]
    stop_when: tuple[str, ...]
    output_focus: tuple[str, ...]
    included_sections: tuple[str, ...] = ()
    compact: bool = False
    output_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class KnowledgeEvidenceQueryPlan:
    """Ordered evidence lookups for one task profile."""

    profile_id: str
    title: str
    objective: str
    query_order: tuple[str, ...]
    avoid: tuple[str, ...]
    stop_after: tuple[str, ...]
    data_gaps: tuple[str, ...]


@dataclass(frozen=True)
class KnowledgeEvidenceQueryRecipe:
    """One compact query template for a task profile."""

    profile_id: str
    id: str
    canonical_id: str | None
    resource: str
    purpose: str
    template: str
    fields: tuple[str, ...]
    constraints: tuple[str, ...]


@dataclass(frozen=True)
class KnowledgeCanonicalQueryRecipe:
    """One source-of-truth Endor evidence query shape."""

    id: str
    title: str
    resource: str
    purpose: str
    template: str
    fields: tuple[str, ...]
    constraints: tuple[str, ...]
    completeness: str
    forbidden: tuple[str, ...]


@dataclass(frozen=True)
class KnowledgeWorkflow:
    """Per-agent workflow knowledge rendered only for the matching agent."""

    agent_id: str
    title: str
    summary: str
    resources: tuple[KnowledgeResource, ...]
    retrieval_steps: tuple[str, ...]
    fallbacks: tuple[str, ...]
    data_gaps: tuple[str, ...]
    task_profiles: tuple[KnowledgeTaskProfile, ...]
    evidence_query_plans: tuple[KnowledgeEvidenceQueryPlan, ...]
    evidence_query_recipes: tuple[KnowledgeEvidenceQueryRecipe, ...]

    def task_profile_for(self, profile_id: str) -> KnowledgeTaskProfile | None:
        """Return a task profile by id."""

        for profile in self.task_profiles:
            if profile.id == profile_id:
                return profile
        return None

    def evidence_query_plan_for(self, profile_id: str) -> KnowledgeEvidenceQueryPlan | None:
        """Return the evidence query plan for a task profile by id."""

        for plan in self.evidence_query_plans:
            if plan.profile_id == profile_id:
                return plan
        return None

    def evidence_query_recipes_for(self, profile_id: str) -> tuple[KnowledgeEvidenceQueryRecipe, ...]:
        """Return evidence query recipes for a task profile."""

        return tuple(
            recipe
            for recipe in self.evidence_query_recipes
            if recipe.profile_id == profile_id
        )


@dataclass(frozen=True)
class EndorKnowledgePack:
    """Validated Endor Knowledge Pack content."""

    name: str
    version: str
    precedence: tuple[str, ...]
    global_rules: tuple[KnowledgeRule, ...]
    query_recipes: dict[str, KnowledgeCanonicalQueryRecipe]
    workflows: dict[str, KnowledgeWorkflow]

    def workflow_for(self, agent_id: str) -> KnowledgeWorkflow | None:
        """Return the workflow contract for an agent, if one exists."""

        return self.workflows.get(agent_id)


def default_knowledge_pack_root() -> Path:
    """Return the source-controlled Endor Knowledge Pack root."""

    return Path(__file__).resolve().parents[2] / "source" / "endor-knowledge-pack"


def load_knowledge_pack(root: str | Path | None = None) -> EndorKnowledgePack:
    """Load the Endor Knowledge Pack from disk."""

    pack_root = Path(root) if root is not None else default_knowledge_pack_root()
    pack_data = _load_yaml_mapping(pack_root / "pack.yaml")
    query_recipes = {
        recipe.id: recipe
        for recipe in _load_canonical_query_recipes(pack_root)
    }
    workflows = {
        workflow.agent_id: workflow
        for workflow in _load_workflows(pack_root)
    }
    return EndorKnowledgePack(
        name=str(pack_data.get("name", "")),
        version=str(pack_data.get("version", "")),
        precedence=tuple(_strings(pack_data.get("precedence"))),
        global_rules=tuple(_rule(item) for item in _mappings(pack_data.get("global_rules"))),
        query_recipes=query_recipes,
        workflows=workflows,
    )


def validate_knowledge_pack(
    root: str | Path | None = None,
    *,
    agent_ids: set[str] | frozenset[str] | None = None,
) -> list[str]:
    """Validate source-controlled pack data and return all errors."""

    pack_root = Path(root) if root is not None else default_knowledge_pack_root()
    errors: list[str] = []

    pack_path = pack_root / "pack.yaml"
    try:
        pack_data = _load_yaml_mapping(pack_path)
    except Exception as exc:
        return [f"pack.yaml: failed to read YAML: {exc}"]

    if pack_data.get("schema_version") != PACK_SCHEMA_VERSION:
        errors.append(f"pack.yaml: schema_version must be {PACK_SCHEMA_VERSION}")
    if pack_data.get("name") != "Endor Knowledge Pack":
        errors.append("pack.yaml: name must be Endor Knowledge Pack")
    if not isinstance(pack_data.get("version"), str) or not str(pack_data.get("version")).strip():
        errors.append("pack.yaml: version must be a non-empty string")

    precedence = _strings(pack_data.get("precedence"))
    for marker in REQUIRED_PRECEDENCE_MARKERS:
        if not any(marker in item for item in precedence):
            errors.append(f"pack.yaml: precedence must mention {marker!r}")

    global_rules = _mappings(pack_data.get("global_rules"))
    if not global_rules:
        errors.append("pack.yaml: global_rules must be a non-empty list")
    rule_ids: set[str] = set()
    for index, item in enumerate(global_rules):
        prefix = f"pack.yaml global_rules[{index}]"
        rule_id = _required_slug(item, "id", prefix, errors)
        if rule_id:
            if rule_id in rule_ids:
                errors.append(f"{prefix}.id: duplicate rule id {rule_id!r}")
            rule_ids.add(rule_id)
        _required_string(item, "title", prefix, errors)
        _required_string(item, "guidance", prefix, errors)
    for rule_id in REQUIRED_GLOBAL_RULE_IDS:
        if rule_id not in rule_ids:
            errors.append(f"pack.yaml: missing global rule {rule_id!r}")

    _check_forbidden_visible_terms(pack_path, pack_data, errors)
    canonical_query_recipes = _validate_canonical_query_recipes(pack_root, errors)
    _validate_workflows(
        pack_root,
        agent_ids=agent_ids,
        canonical_query_recipes=canonical_query_recipes,
        errors=errors,
    )
    from endor_agent_kit.evidence_plans import compile_evidence_plans

    evidence_plans_root = pack_root / "evidence-plans"
    if evidence_plans_root.exists() and not evidence_plans_root.is_dir():
        errors.append("evidence-plans: must be a directory")
    elif evidence_plans_root.is_dir():
        for path in sorted(evidence_plans_root.glob("*.yaml")):
            if agent_ids is not None and path.stem not in agent_ids:
                continue
            try:
                compile_evidence_plans(path.stem, knowledge_pack_root=pack_root)
            except Exception as exc:
                errors.extend(
                    f"evidence-plans/{path.name}: {line}"
                    for line in str(exc).splitlines()
                )
        if agent_ids is not None:
            for agent_id in sorted(agent_ids):
                if not (pack_root / "workflows" / f"{agent_id}.yaml").is_file():
                    continue
                try:
                    compiled = compile_evidence_plans(
                        agent_id,
                        knowledge_pack_root=pack_root,
                    )
                except Exception:
                    continue
                default_profile = default_task_profile_for_agent(agent_id)
                if not any(
                    plan.profile_id == default_profile for plan in compiled
                ):
                    errors.append(
                        f"evidence-plans/{agent_id}.yaml: missing default "
                        f"Evidence Plan {default_profile!r}"
                    )
    return errors


def render_knowledge_pack_section(
    agent_id: str | None,
    root: str | Path | None = None,
    *,
    compact: bool = False,
    profile_id: str | None = None,
) -> str:
    """Render compact pack guidance for one generated agent."""

    if not agent_id:
        return ""
    pack = load_knowledge_pack(root)
    lines = [
        PACK_SECTION_HEADING,
        "",
        "These notes augment this generated recipe. Workflow output contracts, hard guardrails, and source recipe instructions remain authoritative.",
        "",
        "### Global Rules",
        "",
    ]
    if compact:
        global_titles = "; ".join(rule.title for rule in pack.global_rules)
        lines.append(f"- {global_titles}.")
    else:
        for rule in pack.global_rules:
            lines.append(f"- {rule.title}: {rule.guidance}")
    lines.extend(["", "### Evidence Gate Contract", ""])
    gate_rules = COMPACT_EVIDENCE_GATE_RULES if compact else EVIDENCE_GATE_RULES
    lines.extend(f"- {rule}" for rule in gate_rules)
    if not compact:
        lines.extend(["", "### Scope Normalization Contract", ""])
        lines.extend(f"- {rule}" for rule in SCOPE_NORMALIZATION_RULES)
        lines.extend(["", "### Mutability Gate Contract", ""])
        lines.extend(f"- {rule}" for rule in MUTABILITY_GATE_RULES)

    workflow = pack.workflow_for(agent_id)
    if workflow is not None:
        selected_profile = workflow.task_profile_for(profile_id) if profile_id is not None else None
        if profile_id is not None and selected_profile is None:
            raise ValueError(f"unknown task profile {profile_id!r} for agent {agent_id!r}")
        task_profiles = (selected_profile,) if selected_profile is not None else workflow.task_profiles
        query_plans = (
            tuple(plan for plan in workflow.evidence_query_plans if plan.profile_id == profile_id)
            if profile_id is not None
            else workflow.evidence_query_plans
        )
        query_recipes = (
            tuple(recipe for recipe in workflow.evidence_query_recipes if recipe.profile_id == profile_id)
            if profile_id is not None
            else workflow.evidence_query_recipes
        )
        lines.extend(["", f"### {workflow.title}", "", workflow.summary, ""])
        if task_profiles:
            lines.extend(["### Agent Task Profiles", ""])
            if compact:
                profiles = ", ".join(f"`{profile.id}`" for profile in task_profiles)
                lines.append(
                    f"- Profiles: {profiles}. Profile bounds workflow; obey stop; full only on request."
                )
            else:
                for profile in task_profiles:
                    lines.extend([
                        f"#### `{profile.id}` - {profile.title}",
                        "",
                        profile.summary,
                        "- Use when: " + " ".join(profile.when_to_use),
                        "- Minimal evidence: " + " ".join(profile.minimal_evidence),
                        "- Stop when: " + " ".join(profile.stop_when),
                        "- Output focus: " + " ".join(profile.output_focus),
                        "",
                    ])
        if query_plans:
            lines.extend(["### Evidence Query Plans", ""])
            if compact:
                profiles = ", ".join(f"`{plan.profile_id}`" for plan in query_plans)
                lines.append(
                    f"- Plans: {profiles}. Exact/ranked evidence first; selected detail only; "
                    "skipped lanes -> `data_gaps`."
                )
                if _workflow_uses_sca_upgrade_plan(workflow):
                    lines.append(
                        "- SCA/remediation: VersionUpgrade/UIA before Finding detail; no broad Finding inventory."
                    )
            else:
                for plan in query_plans:
                    lines.extend([
                        f"#### `{plan.profile_id}` - {plan.title}",
                        "",
                        plan.objective,
                        "- Query order: " + " ".join(
                            f"{index}. {step}"
                            for index, step in enumerate(plan.query_order, start=1)
                        ),
                        "- Avoid: " + " ".join(plan.avoid),
                        "- Stop after: " + " ".join(plan.stop_after),
                        "- Data gaps: " + " ".join(plan.data_gaps),
                        "",
                    ])
        if query_recipes:
            lines.extend(["### Evidence Query Recipes", ""])
            if compact:
                compact_recipes = (
                    query_recipes
                    if profile_id is not None
                    else _compact_query_recipes(workflow)
                )
                for recipe in compact_recipes:
                    lines.append(
                        f"- `{recipe.id}`/{recipe.profile_id}: `{recipe.template}`"
                    )
            else:
                for recipe in query_recipes:
                    if recipe.canonical_id:
                        canonical_line = f"- Canonical: `{recipe.canonical_id}`"
                    else:
                        canonical_line = "- Canonical: workflow-local"
                    lines.extend([
                        f"#### `{recipe.id}` ({recipe.profile_id})",
                        "",
                        canonical_line,
                        f"- Resource: `{recipe.resource}`",
                        f"- Purpose: {recipe.purpose}",
                        f"- Template: `{recipe.template}`",
                        "- Fields: " + ", ".join(f"`{field}`" for field in recipe.fields),
                        "- Constraints: " + " ".join(recipe.constraints),
                        "",
                    ])
        if workflow.resources and not compact and profile_id is None:
            resources = ", ".join(f"`{resource.name}`" for resource in workflow.resources)
            lines.append(f"- Preferred evidence resources: {resources}.")
            for resource in workflow.resources:
                fields = ", ".join(f"`{field}`" for field in resource.fields)
                lines.append(f"- `{resource.name}`: {resource.purpose} Fields: {fields}.")
        if not compact and profile_id is None and workflow.retrieval_steps:
            lines.append("- Retrieval order: " + " ".join(
                f"{index}. {step}" for index, step in enumerate(workflow.retrieval_steps, start=1)
            ))
        if not compact and profile_id is None and workflow.fallbacks:
            lines.append("- Fallbacks: " + " ".join(workflow.fallbacks))
        if not compact and profile_id is None and workflow.data_gaps:
            lines.append("- Data gaps: " + " ".join(workflow.data_gaps))

    return "\n".join(lines).rstrip() + "\n"


def default_task_profile_for_agent(agent_id: str) -> str:
    """Return the preferred compact profile for runtime proof of an agent."""

    defaults = {
        "ai-sast-remediation": "evidence-check",
        "cicd-posture": "posture",
        "dependency-reviewer": "repository-review",
        "troubleshooting": "diagnose",
        "findings-browser": "browse",
        "malware-responder": "exposure-check",
        "configuration-automation": "evidence-check",
        "remediation-planning": "selection-plan",
        "sca-remediation": "selection-plan",
        "oss-upgrade-investigator": "evidence-check",
        "vulnerability-explainer": "explain",
    }
    return defaults.get(agent_id, "evidence-check")


def render_task_profile_prompt(
    agent_id: str,
    profile_id: str | None = None,
    root: str | Path | None = None,
    *,
    compact: bool = False,
) -> str:
    """Render one compact task-profile selection prompt for runtime use."""

    selected_profile_id = profile_id or default_task_profile_for_agent(agent_id)
    pack = load_knowledge_pack(root)
    workflow = pack.workflow_for(agent_id)
    if workflow is None:
        return ""
    profile = workflow.task_profile_for(selected_profile_id)
    if profile is None:
        return ""
    plan = workflow.evidence_query_plan_for(selected_profile_id)
    recipes = workflow.evidence_query_recipes_for(selected_profile_id)
    if compact:
        prompt = (
            f"Agent task profile `{profile.id}`: {profile.summary} "
            "Use only that profile's minimal evidence. Treat this profile as the active workflow boundary: "
            "stop with the selected gate or precise `data_gaps`, and do not continue into later workflow "
            "steps unless the user explicitly asks for the full workflow."
        )
        if profile.minimal_evidence:
            prompt += f" Minimal evidence: {_compact_list(profile.minimal_evidence)}."
        if profile.output_focus:
            prompt += f" Required output focus: {_compact_list(profile.output_focus)}."
        if plan is not None:
            prompt += (
                f" Evidence query plan: {_compact_order(plan.query_order)} "
                f"Avoid {_compact_list(plan.avoid)}."
            )
        if recipes:
            rendered_recipes = "; ".join(
                f"{recipe.id}: `{recipe.template}`"
                for recipe in recipes[:4]
            )
            prompt += f" Evidence query recipes: {rendered_recipes}."
        return prompt
    lines = [
        f"Agent task profile: `{profile.id}` ({profile.title}).",
        profile.summary,
        "Use this compact profile instead of running the full workflow unless the user explicitly asks for the full workflow.",
        "Minimal evidence:",
        *[f"- {item}" for item in profile.minimal_evidence],
        "Stop when:",
        *[f"- {item}" for item in profile.stop_when],
        "Output focus:",
        *[f"- {item}" for item in profile.output_focus],
    ]
    if plan is not None:
        lines.extend([
            "Evidence query plan:",
            *[f"{index}. {step}" for index, step in enumerate(plan.query_order, start=1)],
            "Avoid:",
            *[f"- {item}" for item in plan.avoid],
            "Stop after:",
            *[f"- {item}" for item in plan.stop_after],
            "Data gaps:",
            *[f"- {item}" for item in plan.data_gaps],
        ])
    if recipes:
        lines.append("Evidence query recipes:")
        for recipe in recipes:
            canonical = (
                f", canonical `{recipe.canonical_id}`"
                if recipe.canonical_id
                else ""
            )
            lines.extend([
                f"- `{recipe.id}` ({recipe.resource}{canonical}): {recipe.purpose}",
                "  ```bash",
                f"  {recipe.template}",
                "  ```",
            ])
    return "\n".join(lines)


def _validate_workflows(
    pack_root: Path,
    *,
    agent_ids: set[str] | frozenset[str] | None,
    canonical_query_recipes: dict[str, KnowledgeCanonicalQueryRecipe],
    errors: list[str],
) -> None:
    workflows_root = pack_root / "workflows"
    if not workflows_root.exists():
        return
    if not workflows_root.is_dir():
        errors.append("workflows: must be a directory")
        return

    seen: set[str] = set()
    for path in sorted(workflows_root.glob("*.yaml")):
        try:
            data = _load_yaml_mapping(path)
        except Exception as exc:
            errors.append(f"{_rel(pack_root, path)}: failed to read YAML: {exc}")
            continue
        prefix = _rel(pack_root, path)
        for field in REQUIRED_WORKFLOW_FIELDS:
            if field not in data:
                errors.append(f"{prefix}: missing required field {field!r}")
        agent_id = _required_slug(data, "agent_id", prefix, errors)
        if agent_id:
            if path.stem != agent_id:
                errors.append(f"{prefix}: filename must match agent_id {agent_id!r}")
            if agent_id in seen:
                errors.append(f"{prefix}: duplicate workflow for agent {agent_id!r}")
            seen.add(agent_id)
            if agent_ids is not None and agent_id not in agent_ids:
                errors.append(f"{prefix}: references unknown agent {agent_id!r}")

        _required_string(data, "title", prefix, errors)
        _required_string(data, "summary", prefix, errors)
        resources = _mappings(data.get("resources"))
        if not resources:
            errors.append(f"{prefix}.resources: must be a non-empty list")
        for index, resource in enumerate(resources):
            resource_prefix = f"{prefix}.resources[{index}]"
            _required_string(resource, "name", resource_prefix, errors)
            _required_string(resource, "purpose", resource_prefix, errors)
            if not _strings(resource.get("fields")):
                errors.append(f"{resource_prefix}.fields: must be a non-empty list")
        for field in ("retrieval_steps", "fallbacks", "data_gaps"):
            if not _strings(data.get(field)):
                errors.append(f"{prefix}.{field}: must be a non-empty list")
        task_profiles = _mappings(data.get("task_profiles"))
        if not task_profiles:
            errors.append(f"{prefix}.task_profiles: must be a non-empty list")
        profile_ids: set[str] = set()
        for index, profile in enumerate(task_profiles):
            profile_prefix = f"{prefix}.task_profiles[{index}]"
            for field in REQUIRED_TASK_PROFILE_FIELDS:
                if field not in profile:
                    errors.append(f"{profile_prefix}: missing required field {field!r}")
            profile_id = _required_slug(profile, "id", profile_prefix, errors)
            if profile_id:
                if profile_id in profile_ids:
                    errors.append(f"{profile_prefix}.id: duplicate task profile id {profile_id!r}")
                profile_ids.add(profile_id)
            _required_string(profile, "title", profile_prefix, errors)
            _required_string(profile, "summary", profile_prefix, errors)
            for field in ("when_to_use", "minimal_evidence", "stop_when", "output_focus"):
                if not _strings(profile.get(field)):
                    errors.append(f"{profile_prefix}.{field}: must be a non-empty list")
            if "included_sections" in profile:
                included_sections = _strings(profile.get("included_sections"))
                raw_included_sections = profile.get("included_sections")
                if not isinstance(raw_included_sections, list) or len(included_sections) != len(raw_included_sections):
                    errors.append(f"{profile_prefix}.included_sections: must be an array of strings")
                if len(set(included_sections)) != len(included_sections):
                    errors.append(f"{profile_prefix}.included_sections: duplicate section id")
                for section_id in included_sections:
                    if not SLUG_RE.fullmatch(section_id):
                        errors.append(f"{profile_prefix}.included_sections: invalid section id {section_id!r}")
            if "compact" in profile and not isinstance(profile.get("compact"), bool):
                errors.append(f"{profile_prefix}.compact: must be a boolean")
            if "output_fields" in profile:
                output_fields = _strings(profile.get("output_fields"))
                raw_output_fields = profile.get("output_fields")
                if not isinstance(raw_output_fields, list) or len(output_fields) != len(raw_output_fields):
                    errors.append(f"{profile_prefix}.output_fields: must be an array of strings")
                if len(set(output_fields)) != len(output_fields):
                    errors.append(f"{profile_prefix}.output_fields: duplicate output field")
            profile_text = _visible_text(profile).lower()
            if "data_gaps" not in profile_text:
                errors.append(f"{profile_prefix}: task profile guidance must mention data_gaps")
        evidence_query_plans = _mappings(data.get("evidence_query_plans"))
        if not evidence_query_plans:
            errors.append(f"{prefix}.evidence_query_plans: must be a non-empty list")
        plan_profile_ids: set[str] = set()
        for index, plan in enumerate(evidence_query_plans):
            plan_prefix = f"{prefix}.evidence_query_plans[{index}]"
            for field in REQUIRED_EVIDENCE_QUERY_PLAN_FIELDS:
                if field not in plan:
                    errors.append(f"{plan_prefix}: missing required field {field!r}")
            profile_id = _required_slug(plan, "profile_id", plan_prefix, errors)
            if profile_id:
                if profile_id in plan_profile_ids:
                    errors.append(f"{plan_prefix}.profile_id: duplicate evidence query plan for profile {profile_id!r}")
                plan_profile_ids.add(profile_id)
                if profile_ids and profile_id not in profile_ids:
                    errors.append(f"{plan_prefix}.profile_id: references unknown task profile {profile_id!r}")
            _required_string(plan, "title", plan_prefix, errors)
            _required_string(plan, "objective", plan_prefix, errors)
            for field in ("query_order", "avoid", "stop_after", "data_gaps"):
                if not _strings(plan.get(field)):
                    errors.append(f"{plan_prefix}.{field}: must be a non-empty list")
            plan_text = _visible_text(plan).lower()
            if "data_gaps" not in plan_text:
                errors.append(f"{plan_prefix}: evidence query plan must mention data_gaps")
        for profile_id in sorted(profile_ids - plan_profile_ids):
            errors.append(f"{prefix}.evidence_query_plans: missing plan for task profile {profile_id!r}")
        if agent_id in {"sca-remediation", "remediation-planning"}:
            _validate_sca_query_order(prefix, evidence_query_plans, errors)
        evidence_query_recipes = _mappings(data.get("evidence_query_recipes"))
        if not evidence_query_recipes:
            errors.append(f"{prefix}.evidence_query_recipes: must be a non-empty list")
        recipe_profile_ids: set[str] = set()
        recipe_keys: set[tuple[str, str]] = set()
        for index, recipe in enumerate(evidence_query_recipes):
            recipe_prefix = f"{prefix}.evidence_query_recipes[{index}]"
            for field in REQUIRED_EVIDENCE_QUERY_RECIPE_FIELDS:
                if field not in recipe:
                    errors.append(f"{recipe_prefix}: missing required field {field!r}")
            profile_id = _required_slug(recipe, "profile_id", recipe_prefix, errors)
            if profile_id:
                recipe_profile_ids.add(profile_id)
                if profile_ids and profile_id not in profile_ids:
                    errors.append(f"{recipe_prefix}.profile_id: references unknown task profile {profile_id!r}")
            recipe_id = _required_slug(recipe, "id", recipe_prefix, errors)
            if profile_id and recipe_id:
                recipe_key = (profile_id, recipe_id)
                if recipe_key in recipe_keys:
                    errors.append(
                        f"{recipe_prefix}.id: duplicate evidence query recipe id {recipe_id!r} for profile {profile_id!r}"
                    )
                recipe_keys.add(recipe_key)
            _required_string(recipe, "resource", recipe_prefix, errors)
            _required_string(recipe, "purpose", recipe_prefix, errors)
            template = _required_string(recipe, "template", recipe_prefix, errors)
            for field in ("fields", "constraints"):
                if not _strings(recipe.get(field)):
                    errors.append(f"{recipe_prefix}.{field}: must be a non-empty list")
            _validate_query_recipe_template(recipe_prefix, template, errors)
            _validate_canonical_query_recipe_reference(
                recipe_prefix,
                recipe,
                canonical_query_recipes,
                errors,
            )
        for profile_id in sorted(profile_ids - recipe_profile_ids):
            errors.append(f"{prefix}.evidence_query_recipes: missing recipe for task profile {profile_id!r}")
        visible = _visible_text(data)
        if "namespace" not in visible.lower():
            errors.append(f"{prefix}: workflow guidance must mention namespace handling")
        if "data_gaps" not in visible:
            errors.append(f"{prefix}: workflow guidance must mention data_gaps")
        _check_forbidden_visible_terms(path, data, errors, root=pack_root)


def _load_workflows(pack_root: Path) -> tuple[KnowledgeWorkflow, ...]:
    workflows_root = pack_root / "workflows"
    if not workflows_root.is_dir():
        return ()
    return tuple(_workflow(_load_yaml_mapping(path)) for path in sorted(workflows_root.glob("*.yaml")))


def _load_canonical_query_recipes(pack_root: Path) -> tuple[KnowledgeCanonicalQueryRecipe, ...]:
    catalog_path = pack_root / "query-recipes.yaml"
    if not catalog_path.exists():
        return ()
    catalog = _load_yaml_mapping(catalog_path)
    return tuple(
        _canonical_query_recipe(item)
        for item in _mappings(catalog.get("recipes"))
    )


def _workflow(data: dict[str, Any]) -> KnowledgeWorkflow:
    return KnowledgeWorkflow(
        agent_id=str(data.get("agent_id", "")),
        title=str(data.get("title", "")),
        summary=str(data.get("summary", "")),
        resources=tuple(_resource(item) for item in _mappings(data.get("resources"))),
        retrieval_steps=tuple(_strings(data.get("retrieval_steps"))),
        fallbacks=tuple(_strings(data.get("fallbacks"))),
        data_gaps=tuple(_strings(data.get("data_gaps"))),
        task_profiles=tuple(_task_profile(item) for item in _mappings(data.get("task_profiles"))),
        evidence_query_plans=tuple(
            _evidence_query_plan(item)
            for item in _mappings(data.get("evidence_query_plans"))
        ),
        evidence_query_recipes=tuple(
            _evidence_query_recipe(item)
            for item in _mappings(data.get("evidence_query_recipes"))
        ),
    )


def _resource(data: dict[str, Any]) -> KnowledgeResource:
    return KnowledgeResource(
        name=str(data.get("name", "")),
        purpose=str(data.get("purpose", "")),
        fields=tuple(_strings(data.get("fields"))),
    )


def _task_profile(data: dict[str, Any]) -> KnowledgeTaskProfile:
    return KnowledgeTaskProfile(
        id=str(data.get("id", "")),
        title=str(data.get("title", "")),
        summary=str(data.get("summary", "")),
        when_to_use=tuple(_strings(data.get("when_to_use"))),
        minimal_evidence=tuple(_strings(data.get("minimal_evidence"))),
        stop_when=tuple(_strings(data.get("stop_when"))),
        output_focus=tuple(_strings(data.get("output_focus"))),
        included_sections=tuple(_strings(data.get("included_sections"))),
        compact=bool(data.get("compact", False)),
        output_fields=tuple(_strings(data.get("output_fields"))),
    )


def _evidence_query_plan(data: dict[str, Any]) -> KnowledgeEvidenceQueryPlan:
    return KnowledgeEvidenceQueryPlan(
        profile_id=str(data.get("profile_id", "")),
        title=str(data.get("title", "")),
        objective=str(data.get("objective", "")),
        query_order=tuple(_strings(data.get("query_order"))),
        avoid=tuple(_strings(data.get("avoid"))),
        stop_after=tuple(_strings(data.get("stop_after"))),
        data_gaps=tuple(_strings(data.get("data_gaps"))),
    )


def _evidence_query_recipe(data: dict[str, Any]) -> KnowledgeEvidenceQueryRecipe:
    return KnowledgeEvidenceQueryRecipe(
        profile_id=str(data.get("profile_id", "")),
        id=str(data.get("id", "")),
        canonical_id=_optional_slug_value(data.get("canonical_id")),
        resource=str(data.get("resource", "")),
        purpose=str(data.get("purpose", "")),
        template=str(data.get("template", "")),
        fields=tuple(_strings(data.get("fields"))),
        constraints=tuple(_strings(data.get("constraints"))),
    )


def _canonical_query_recipe(data: dict[str, Any]) -> KnowledgeCanonicalQueryRecipe:
    return KnowledgeCanonicalQueryRecipe(
        id=str(data.get("id", "")),
        title=str(data.get("title", "")),
        resource=str(data.get("resource", "")),
        purpose=str(data.get("purpose", "")),
        template=str(data.get("template", "")),
        fields=tuple(_strings(data.get("fields"))),
        constraints=tuple(_strings(data.get("constraints"))),
        completeness=str(data.get("completeness", "")),
        forbidden=tuple(_strings(data.get("forbidden"))),
    )


def _rule(data: dict[str, Any]) -> KnowledgeRule:
    return KnowledgeRule(
        id=str(data.get("id", "")),
        title=str(data.get("title", "")),
        guidance=str(data.get("guidance", "")),
    )


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"expected YAML mapping, got {type(data).__name__}")
    return data


def _mappings(value: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, dict))


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if isinstance(item, str) and item.strip())


def _required_slug(
    data: dict[str, Any],
    field: str,
    prefix: str,
    errors: list[str],
) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not SLUG_RE.match(value):
        errors.append(f"{prefix}.{field}: must match ^[a-z][a-z0-9-]{{2,63}}$")
        return ""
    return value


def _required_string(
    data: dict[str, Any],
    field: str,
    prefix: str,
    errors: list[str],
) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{prefix}.{field}: must be a non-empty string")
        return ""
    return value


def _optional_slug_value(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    return value


def _check_forbidden_visible_terms(
    path: Path,
    data: dict[str, Any],
    errors: list[str],
    *,
    root: Path | None = None,
) -> None:
    visible = _visible_text(data).lower()
    label = _rel(root, path) if root is not None else path.name
    for term in FORBIDDEN_VISIBLE_TERMS:
        if term in visible:
            errors.append(f"{label}: forbidden public wording {term!r}")


def _visible_text(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(_visible_text(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_visible_text(item) for item in value)
    if isinstance(value, str):
        return value
    return ""


def _rel(root: Path | None, path: Path) -> str:
    if root is None:
        return path.name
    return path.relative_to(root).as_posix()


def _compact_order(items: tuple[str, ...]) -> str:
    if not items:
        return "none."
    return " ".join(f"{index}. {item}" for index, item in enumerate(items, start=1))


def _compact_list(items: tuple[str, ...]) -> str:
    if not items:
        return "nothing extra"
    return "; ".join(items)


def _workflow_uses_sca_upgrade_plan(workflow: KnowledgeWorkflow) -> bool:
    resource_names = {resource.name.lower() for resource in workflow.resources}
    return "finding" in resource_names and "versionupgrade" in resource_names


def _compact_query_recipes(workflow: KnowledgeWorkflow) -> tuple[KnowledgeEvidenceQueryRecipe, ...]:
    selected: list[KnowledgeEvidenceQueryRecipe] = []
    seen: set[str] = set()
    preferred_profiles = (
        default_task_profile_for_agent(workflow.agent_id),
        "selection-plan",
        "evidence-check",
        "resolve-scope",
        "explain",
        "diagnose",
    )
    for profile_id in preferred_profiles:
        for recipe in workflow.evidence_query_recipes_for(profile_id):
            if recipe.id in seen:
                continue
            selected.append(recipe)
            seen.add(recipe.id)
            if len(selected) >= 4:
                return tuple(selected)
    for recipe in workflow.evidence_query_recipes:
        if recipe.id in seen:
            continue
        selected.append(recipe)
        seen.add(recipe.id)
        if len(selected) >= 4:
            break
    return tuple(selected)


def _validate_query_recipe_template(
    prefix: str,
    template: str,
    errors: list[str],
) -> None:
    if not template:
        return
    lower = template.lower()
    for error in agent_api_command_errors(
        template,
        agent_id="<agent-id>",
        allow_template_identity=True,
    ):
        errors.append(f"{prefix}.template: {error}")
    if "endorctl agent api" in lower and " get " in lower and (" --filter " in lower or " -f " in lower):
        errors.append(f"{prefix}.template: endorctl agent api get must not use filters")
    if "endorctl agent api" in lower and " -n " not in lower and " --namespace " not in lower:
        errors.append(f"{prefix}.template: endorctl agent api commands must include explicit namespace")
    count_only = bool(re.search(r"(?:^|\s)--count(?:\s|$)", lower))
    grouped = "--group-aggregation-paths" in lower
    group_paths = _group_aggregation_paths(template) if grouped else ()
    if (
        "endorctl agent api" in lower
        and " list " in lower
        and not count_only
        and not grouped
        and " --field-mask " not in lower
    ):
        errors.append(f"{prefix}.template: endorctl agent api list commands must include --field-mask")
    if count_only and "endorctl agent api" in lower and " list " in lower and "--list-all" in lower:
        errors.append(f"{prefix}.template: count-only list commands must not include --list-all")
    if grouped and not group_paths:
        errors.append(f"{prefix}.template: group aggregation requires at least one path")
    if grouped and "--list-all" in lower:
        errors.append(f"{prefix}.template: grouped list commands must not include --list-all")
    if grouped and group_paths:
        resource = _query_resource(template)
        approved_paths = APPROVED_GROUP_AGGREGATION_PATHS.get(resource, frozenset())
        for path in group_paths:
            if path not in approved_paths:
                errors.append(
                    f"{prefix}.template: group aggregation path {path!r} is not approved for {resource or 'unknown resource'}"
                )
    field_mask_paths = _field_mask_paths(template)
    if _has_field_mask_path_collision(field_mask_paths):
        errors.append(f"{prefix}.template: field-mask must not include both a parent path and child path")
    if "endorctl agent api" in lower and " list " in lower and "finding" in lower and "--list-all" in lower:
        if not _is_scoped_finding_list_all_query(lower):
            errors.append(f"{prefix}.template: broad Finding --list-all templates are not allowed")
    if "cat ~/.endorctl/config.yaml" in lower or "cat $home/.endorctl/config.yaml" in lower:
        errors.append(f"{prefix}.template: must not cat Endor config files")
    errors.extend(endor_api_template_errors(prefix, template))


def _field_mask_paths(template: str) -> tuple[str, ...]:
    match = re.search(r"--field-mask\s+([\"'])(?P<mask>.+?)\1", template)
    if not match:
        return ()
    return tuple(
        path.strip()
        for path in match.group("mask").split(",")
        if path.strip()
    )


def _group_aggregation_paths(template: str) -> tuple[str, ...]:
    try:
        tokens = shlex.split(template)
    except ValueError:
        return ()
    values: list[str] = []
    for index, token in enumerate(tokens):
        if token == "--group-aggregation-paths":
            if index + 1 < len(tokens) and not tokens[index + 1].startswith("-"):
                values.append(tokens[index + 1])
        elif token.startswith("--group-aggregation-paths="):
            values.append(token.split("=", 1)[1])
    return tuple(
        path.strip()
        for value in values
        for path in value.split(",")
        if path.strip()
    )


def _query_resource(template: str) -> str:
    try:
        tokens = shlex.split(template)
    except ValueError:
        return ""
    for index, token in enumerate(tokens):
        if token in {"-r", "--resource"}:
            if index + 1 < len(tokens) and not tokens[index + 1].startswith("-"):
                return tokens[index + 1]
        elif token.startswith("--resource="):
            return token.split("=", 1)[1]
    return ""


def _has_field_mask_path_collision(paths: tuple[str, ...]) -> bool:
    for index, path in enumerate(paths):
        prefix = path + "."
        for other_index, other_path in enumerate(paths):
            if index != other_index and other_path.startswith(prefix):
                return True
    return False


def _validate_canonical_query_recipes(
    pack_root: Path,
    errors: list[str],
) -> dict[str, KnowledgeCanonicalQueryRecipe]:
    catalog_path = pack_root / "query-recipes.yaml"
    if not catalog_path.exists():
        return {}
    try:
        catalog = _load_yaml_mapping(catalog_path)
    except Exception as exc:
        errors.append(f"query-recipes.yaml: failed to read YAML: {exc}")
        return {}

    if catalog.get("schema_version") != PACK_SCHEMA_VERSION:
        errors.append(f"query-recipes.yaml: schema_version must be {PACK_SCHEMA_VERSION}")

    recipes = _mappings(catalog.get("recipes"))
    if not recipes:
        errors.append("query-recipes.yaml.recipes: must be a non-empty list")

    seen: set[str] = set()
    canonical_recipes: dict[str, KnowledgeCanonicalQueryRecipe] = {}
    for index, recipe in enumerate(recipes):
        prefix = f"query-recipes.yaml recipes[{index}]"
        for field in REQUIRED_CANONICAL_QUERY_RECIPE_FIELDS:
            if field not in recipe:
                errors.append(f"{prefix}: missing required field {field!r}")
        recipe_id = _required_slug(recipe, "id", prefix, errors)
        if recipe_id:
            if recipe_id in seen:
                errors.append(f"{prefix}.id: duplicate canonical query recipe id {recipe_id!r}")
            seen.add(recipe_id)
        _required_string(recipe, "title", prefix, errors)
        _required_string(recipe, "resource", prefix, errors)
        _required_string(recipe, "purpose", prefix, errors)
        template = _required_string(recipe, "template", prefix, errors)
        if not _strings(recipe.get("fields")):
            errors.append(f"{prefix}.fields: must be a non-empty list")
        if not _strings(recipe.get("constraints")):
            errors.append(f"{prefix}.constraints: must be a non-empty list")
        _required_string(recipe, "completeness", prefix, errors)
        _validate_query_recipe_template(prefix, template, errors)
        if recipe_id:
            canonical_recipes[recipe_id] = _canonical_query_recipe(recipe)
    _check_forbidden_visible_terms(catalog_path, catalog, errors, root=pack_root)
    return canonical_recipes


def _validate_canonical_query_recipe_reference(
    prefix: str,
    recipe: dict[str, Any],
    canonical_query_recipes: dict[str, KnowledgeCanonicalQueryRecipe],
    errors: list[str],
) -> None:
    raw_canonical_id = recipe.get("canonical_id")
    if raw_canonical_id is None:
        return
    if not isinstance(raw_canonical_id, str) or not SLUG_RE.match(raw_canonical_id):
        errors.append(f"{prefix}.canonical_id: must match ^[a-z][a-z0-9-]{{2,63}}$")
        return
    canonical = canonical_query_recipes.get(raw_canonical_id)
    if canonical is None:
        errors.append(f"{prefix}.canonical_id: references unknown canonical query recipe {raw_canonical_id!r}")
        return

    resource = str(recipe.get("resource", ""))
    if resource != canonical.resource:
        errors.append(
            f"{prefix}.canonical_id: resource {resource!r} does not match canonical {raw_canonical_id!r} resource {canonical.resource!r}"
        )

    fields = _strings(recipe.get("fields"))
    if fields != canonical.fields:
        errors.append(
            f"{prefix}.canonical_id: fields do not match canonical query recipe {raw_canonical_id!r}"
        )

    template = str(recipe.get("template", ""))
    if _normalize_query_template(template) != _normalize_query_template(canonical.template):
        errors.append(
            f"{prefix}.canonical_id: template does not match canonical query recipe {raw_canonical_id!r}"
        )


def _normalize_query_template(template: str) -> str:
    return " ".join(template.split())


def _is_scoped_finding_list_all_query(lower_template: str) -> bool:
    if (
        "context.type==context_type_main" in lower_template
        and "spec.project_uuid" in lower_template
        and "system_evaluation_method_definition_ai_sast" in lower_template
    ):
        return True
    if (
        "<scope_filter>" in lower_template
        and "spec.dismiss==false" in lower_template
        and "spec.level in" in lower_template
        and "spec.finding_categories" in lower_template
        and 'field-mask "uuid,spec.level,spec.finding_categories"' in lower_template
    ):
        return True
    return (
        "uuid==" in lower_template
        or "spec.target" in lower_template
        or "target_dependency" in lower_template
    )


def _validate_sca_query_order(
    prefix: str,
    plans: tuple[dict[str, Any], ...],
    errors: list[str],
) -> None:
    for index, plan in enumerate(plans):
        if plan.get("profile_id") != "selection-plan":
            continue
        order = " ".join(_strings(plan.get("query_order"))).lower()
        version_index = order.find("versionupgrade")
        finding_index = order.find("finding")
        if version_index == -1:
            errors.append(
                f"{prefix}.evidence_query_plans[{index}].query_order: selection-plan must query VersionUpgrade/UIA evidence"
            )
        if finding_index != -1 and version_index != -1 and finding_index < version_index:
            errors.append(
                f"{prefix}.evidence_query_plans[{index}].query_order: selection-plan must narrow with VersionUpgrade before Finding detail expansion"
            )
