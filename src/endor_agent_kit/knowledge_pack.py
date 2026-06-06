"""Endor Knowledge Pack loading, validation, and prompt rendering."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import yaml


PACK_SECTION_HEADING = "## Endor Knowledge Pack"
PACK_SCHEMA_VERSION = 1
SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{2,63}$")
FORBIDDEN_VISIBLE_TERMS = (
    "pip install " + "endorlabs",
    "python " + "package",
    "external client " + "package",
)
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
EVIDENCE_GATE_RULES = (
    "Never use memory, older sessions, examples, or prior repos as namespace, repo, project, finding, or package provenance.",
    "Never dump or `cat` Endor config files; extract only the namespace key with a field-specific command or parser.",
    "Never guess repo URLs, project UUIDs, finding counts, package versions, scan state, or VersionUpgrade/UIA/CIA evidence.",
    "Treat local docs and repository files as context only until backed by current Endor or user-provided evidence.",
    "Every scoped Endor gate must record `namespace_provenance` from user input, environment, default config key extraction, or project metadata.",
    "Every evidence gate must return required JSON with precise `data_gaps` for missing, stale, unavailable, or host-blocked evidence.",
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

    def task_profile_for(self, profile_id: str) -> KnowledgeTaskProfile | None:
        """Return a task profile by id."""

        for profile in self.task_profiles:
            if profile.id == profile_id:
                return profile
        return None


@dataclass(frozen=True)
class EndorKnowledgePack:
    """Validated Endor Knowledge Pack content."""

    name: str
    version: str
    precedence: tuple[str, ...]
    global_rules: tuple[KnowledgeRule, ...]
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
    workflows = {
        workflow.agent_id: workflow
        for workflow in _load_workflows(pack_root)
    }
    return EndorKnowledgePack(
        name=str(pack_data.get("name", "")),
        version=str(pack_data.get("version", "")),
        precedence=tuple(_strings(pack_data.get("precedence"))),
        global_rules=tuple(_rule(item) for item in _mappings(pack_data.get("global_rules"))),
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
    _validate_workflows(pack_root, agent_ids=agent_ids, errors=errors)
    return errors


def render_knowledge_pack_section(
    agent_id: str | None,
    root: str | Path | None = None,
    *,
    compact: bool = False,
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
    lines.extend(f"- {rule}" for rule in EVIDENCE_GATE_RULES)

    workflow = pack.workflow_for(agent_id)
    if workflow is not None:
        lines.extend(["", f"### {workflow.title}", "", workflow.summary, ""])
        if workflow.task_profiles:
            lines.extend(["### Agent Task Profiles", ""])
            if compact:
                profiles = ", ".join(f"`{profile.id}`" for profile in workflow.task_profiles)
                lines.append(
                    f"- Profiles: {profiles}. Start narrow; stop with `data_gaps`; full only on request."
                )
            else:
                for profile in workflow.task_profiles:
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
        if workflow.resources:
            resources = ", ".join(f"`{resource.name}`" for resource in workflow.resources)
            lines.append(f"- Preferred evidence resources: {resources}.")
            if not compact:
                for resource in workflow.resources:
                    fields = ", ".join(f"`{field}`" for field in resource.fields)
                    lines.append(f"- `{resource.name}`: {resource.purpose} Fields: {fields}.")
        if compact:
            if workflow.retrieval_steps:
                lines.append("- Retrieval: " + " ".join(workflow.retrieval_steps[:2]))
            if workflow.data_gaps:
                lines.append("- Data gaps: " + " ".join(workflow.data_gaps[:1]))
        elif workflow.retrieval_steps:
            lines.append("- Retrieval order: " + " ".join(
                f"{index}. {step}" for index, step in enumerate(workflow.retrieval_steps, start=1)
            ))
        if not compact and workflow.fallbacks:
            lines.append("- Fallbacks: " + " ".join(workflow.fallbacks))
        if not compact and workflow.data_gaps:
            lines.append("- Data gaps: " + " ".join(workflow.data_gaps))

    return "\n".join(lines).rstrip() + "\n"


def default_task_profile_for_agent(agent_id: str) -> str:
    """Return the preferred compact profile for runtime proof of an agent."""

    defaults = {
        "ai-sast-triage": "evidence-check",
        "dependency-decision-helper": "explain",
        "endor-troubleshooter": "diagnose",
        "package-risk-summary": "explain",
        "probe-droid": "evidence-check",
        "remediation-planner": "selection-plan",
        "repository-dependency-reviewer": "evidence-check",
        "sca-remediation": "selection-plan",
        "upgrade-impact-analysis": "evidence-check",
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
    if compact:
        return (
            f"Agent task profile `{profile.id}`: {profile.summary} "
            "Use only that profile's minimal evidence; stop with the selected gate or precise `data_gaps`."
        )
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
    return "\n".join(lines)


def _validate_workflows(
    pack_root: Path,
    *,
    agent_ids: set[str] | frozenset[str] | None,
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
            profile_text = _visible_text(profile).lower()
            if "data_gaps" not in profile_text:
                errors.append(f"{profile_prefix}: task profile guidance must mention data_gaps")
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
