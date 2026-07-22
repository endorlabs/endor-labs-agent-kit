"""Source-owned model recommendations and generated customer documentation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


MODEL_RECOMMENDATION_SCHEMA_VERSION = 1
RECOMMENDATION_DATE = "2026-07-22"
AGENT_MODEL_TIERS = {
    "ai-sast-remediation": "complex_remediation",
    "cicd-posture": "standard",
    "configuration-automation": "standard",
    "dependency-reviewer": "standard",
    "findings-browser": "standard",
    "malware-responder": "standard",
    "oss-upgrade-investigator": "standard",
    "remediation-planning": "standard",
    "sca-remediation": "complex_remediation",
    "troubleshooting": "standard",
    "vulnerability-explainer": "standard",
}
COMPLEX_REMEDIATION_AGENT_IDS = frozenset(
    agent_id
    for agent_id, tier in AGENT_MODEL_TIERS.items()
    if tier == "complex_remediation"
)
ALLOWED_SELECTION_MODES = frozenset({
    "host_pinned",
    "pinned",
    "runtime_selected",
})


@dataclass(frozen=True)
class HostModelRecommendation:
    """One non-blocking model recommendation for a supported host."""

    host: str
    label: str
    recommended_model: str
    selection_mode: str
    standard_effort: str
    complex_remediation_effort: str
    generated_artifact_behavior: str
    customer_override: str
    provider_guidance_url: str = ""


HOST_MODEL_RECOMMENDATIONS = (
    HostModelRecommendation(
        host="claude-code",
        label="Claude Code",
        recommended_model="sonnet",
        selection_mode="pinned",
        standard_effort="host default",
        complex_remediation_effort="host default",
        generated_artifact_behavior="agent frontmatter defaults to sonnet",
        customer_override="Claude environment or per-invocation subagent override wins",
        provider_guidance_url="https://code.claude.com/docs/en/sub-agents",
    ),
    HostModelRecommendation(
        host="claude-managed-agents",
        label="Claude Managed Agents",
        recommended_model="sonnet",
        selection_mode="pinned",
        standard_effort="host default",
        complex_remediation_effort="host default",
        generated_artifact_behavior="recipe sonnet alias compiles to claude-sonnet-4-6",
        customer_override="managed host configuration remains authoritative",
        provider_guidance_url="https://code.claude.com/docs/en/sub-agents",
    ),
    HostModelRecommendation(
        host="codex",
        label="Codex",
        recommended_model="gpt-5.6-luna",
        selection_mode="pinned",
        standard_effort="medium",
        complex_remediation_effort="high",
        generated_artifact_behavior="custom-agent TOML pins gpt-5.6-luna and tier-specific reasoning effort",
        customer_override="explicit Codex model and reasoning settings win",
        provider_guidance_url="https://developers.openai.com/codex/subagents",
    ),
    HostModelRecommendation(
        host="gemini",
        label="Gemini CLI",
        recommended_model="gemini-3.5-flash",
        selection_mode="pinned",
        standard_effort="host managed",
        complex_remediation_effort="host managed",
        generated_artifact_behavior="subagent frontmatter pins model: gemini-3.5-flash",
        customer_override="explicit subagent definition or host subagent configuration wins",
        provider_guidance_url="https://geminicli.com/docs/core/subagents/",
    ),
    HostModelRecommendation(
        host="antigravity",
        label="Antigravity CLI",
        recommended_model="Gemini 3.6 Flash (Low)",
        selection_mode="host_pinned",
        standard_effort="low",
        complex_remediation_effort="low",
        generated_artifact_behavior="pin Gemini 3.6 Flash (Low) in Antigravity Model Usage; plugins cannot set a per-agent model",
        customer_override="customer may explicitly select another available Antigravity model",
        provider_guidance_url="https://antigravity.google/docs/models",
    ),
    HostModelRecommendation(
        host="cursor",
        label="Cursor IDE",
        recommended_model="composer-2.5",
        selection_mode="pinned",
        standard_effort="host managed",
        complex_remediation_effort="host managed",
        generated_artifact_behavior="plugin-agent frontmatter pins composer-2.5 standard with fast=false",
        customer_override="Cursor model selection remains authoritative",
        provider_guidance_url="https://cursor.com/composer",
    ),
    HostModelRecommendation(
        host="cursor-sdk",
        label="Cursor SDK",
        recommended_model="composer-2.5",
        selection_mode="pinned",
        standard_effort="host managed",
        complex_remediation_effort="host managed",
        generated_artifact_behavior="SDK runner pins composer-2.5 standard with fast=false",
        customer_override="--model or CURSOR_MODEL wins",
        provider_guidance_url="https://cursor.com/composer",
    ),
    HostModelRecommendation(
        host="portable",
        label="Portable runtime",
        recommended_model="runtime-selected compatible agentic model",
        selection_mode="runtime_selected",
        standard_effort="runtime managed",
        complex_remediation_effort="runtime managed",
        generated_artifact_behavior="portable bundles do not select a provider model",
        customer_override="runtime operator owns model selection",
    ),
)

_RECOMMENDATIONS_BY_HOST = {
    recommendation.host: recommendation
    for recommendation in HOST_MODEL_RECOMMENDATIONS
}


def recommendation_for_host(host: str) -> HostModelRecommendation:
    """Return the model recommendation for one generated host."""

    try:
        return _RECOMMENDATIONS_BY_HOST[host]
    except KeyError as exc:
        raise ValueError(f"No model recommendation is declared for host {host!r}") from exc


def model_recommendation_lines(
    host: str,
    *,
    agent_id: str | None = None,
    heading_level: int = 2,
) -> list[str]:
    """Render one host recommendation for a generated README."""

    recommendation = recommendation_for_host(host)
    tier = AGENT_MODEL_TIERS.get(agent_id, "unclassified")
    if tier == "complex_remediation":
        effort = recommendation.complex_remediation_effort
    elif tier == "standard" or agent_id is None:
        effort = recommendation.standard_effort
    else:
        effort = "host default pending tier validation"
    heading = "#" * heading_level
    lines = [
        f"{heading} Recommended Model",
        "",
        "This is a release-QA target, not a requirement or model allowlist.",
        "Agent Kit does not block compatible customer-selected host models.",
        "",
        f"- Recommended model: `{recommendation.recommended_model}`.",
        f"- Selection mode: `{recommendation.selection_mode}`.",
        f"- Recommended reasoning/effort: `{effort}`.",
        f"- Generated behavior: {recommendation.generated_artifact_behavior}.",
        f"- Override behavior: {recommendation.customer_override}.",
    ]
    if recommendation.provider_guidance_url:
        lines.append(
            f"- Provider guidance: <{recommendation.provider_guidance_url}>."
        )
    lines.append("")
    return lines


def model_requirements_lines(
    agent_ids: Iterable[str],
    *,
    heading_level: int = 2,
) -> list[str]:
    """Render the Steam-style supported and recommended model matrix."""

    normalized_agent_ids = tuple(sorted(set(agent_ids)))
    complex_agents = tuple(
        agent_id
        for agent_id in normalized_agent_ids
        if AGENT_MODEL_TIERS.get(agent_id) == "complex_remediation"
    )
    standard_agents = tuple(
        agent_id
        for agent_id in normalized_agent_ids
        if AGENT_MODEL_TIERS.get(agent_id) == "standard"
    )
    unclassified_agents = tuple(
        agent_id
        for agent_id in normalized_agent_ids
        if agent_id not in AGENT_MODEL_TIERS
    )
    heading = "#" * heading_level
    subheading = "#" * (heading_level + 1)
    rows = [
        (
            f"| {item.label} | `{item.recommended_model}` | "
            f"`{item.standard_effort}` | `{item.complex_remediation_effort}` | "
            f"`{item.selection_mode}` | {item.generated_artifact_behavior} |"
        )
        for item in HOST_MODEL_RECOMMENDATIONS
    ]
    return [
        f"{heading} Recommended Model Configurations",
        "",
        "These configurations are the Agent Kit targets recommended for release QA.",
        "They are not installation requirements and never restrict a customer's model picker.",
        "Record the actual resolved model and effort in runtime QA because provider aliases can move.",
        "Until an accepted source SHA and benchmark digest are recorded, they are recommendations rather than release-tested claims.",
        "This generated documentation is checked for source drift but is not part of the signed catalog or manifest schema.",
        "",
        f"{subheading} Supported",
        "",
        "- Agent Kit enforces no model allowlist; compatibility still depends on the host's required tools, context, and structured output.",
        "- Explicit customer model and reasoning selections take precedence over Agent Kit recommendations.",
        "- An untested model may produce different quality or latency, but Agent Kit does not block it.",
        "",
        f"{subheading} Recommended",
        "",
        "| Host | Model | Standard effort | Complex remediation effort | Selection mode | Generated behavior |",
        "| --- | --- | --- | --- | --- | --- |",
        *rows,
        "",
        f"Standard agent tier: `{', '.join(standard_agents)}`.",
        "",
        f"Complex remediation agent tier: `{', '.join(complex_agents)}`.",
        "",
        f"Unclassified agents requiring benchmark review: `{', '.join(unclassified_agents) or 'none'}`.",
        "",
        f"Recommendation date: `{RECOMMENDATION_DATE}`. Promote or change a default only after the quality and latency benchmark gate passes for that host and workflow profile.",
        "",
    ]


def model_recommendations_payload(agent_ids: Iterable[str]) -> dict[str, object]:
    """Return the machine-readable non-blocking model recommendation contract."""

    normalized_agent_ids = tuple(sorted(set(agent_ids)))
    unclassified_agent_ids = [
        agent_id
        for agent_id in normalized_agent_ids
        if agent_id not in AGENT_MODEL_TIERS
    ]
    return {
        "schema_version": MODEL_RECOMMENDATION_SCHEMA_VERSION,
        "recommendation_date": RECOMMENDATION_DATE,
        "policy": "recommendation_only",
        "acceptance": {
            "status": "target_for_release_qa",
            "source_commit": None,
            "acceptance_digest": None,
        },
        "customer_override_precedence": [
            "explicit_customer_override",
            "host_or_session_selection",
            "agent_kit_recommendation",
            "host_fallback",
        ],
        "hosts": [asdict(item) for item in HOST_MODEL_RECOMMENDATIONS],
        "agent_tiers": {
            "standard": {
                "agent_ids": [
                    agent_id
                    for agent_id in normalized_agent_ids
                    if AGENT_MODEL_TIERS.get(agent_id) == "standard"
                ],
            },
            "complex_remediation": {
                "agent_ids": [
                    agent_id
                    for agent_id in normalized_agent_ids
                    if AGENT_MODEL_TIERS.get(agent_id) == "complex_remediation"
                ],
            },
            "unclassified": {
                "agent_ids": unclassified_agent_ids,
                "recommendation": "host default pending tier validation",
            },
        },
    }


def write_model_recommendation_artifacts(
    destination: Path,
    agent_ids: Iterable[str],
) -> tuple[Path, Path]:
    """Write the generated JSON contract and human model requirements."""

    normalized_agent_ids = tuple(sorted(set(agent_ids)))
    contract = destination / "model-recommendations.json"
    contract.write_text(
        json.dumps(
            model_recommendations_payload(normalized_agent_ids),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    documentation = destination / "docs" / "model-recommendations.md"
    documentation.parent.mkdir(parents=True, exist_ok=True)
    documentation.write_text(
        "\n".join([
            "# Model Requirements",
            "",
            "<!-- Generated by Endor Labs Agent Kit. Do not hand-edit. -->",
            "",
            *model_requirements_lines(normalized_agent_ids),
        ]),
        encoding="utf-8",
    )
    return contract, documentation
