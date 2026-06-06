from __future__ import annotations

from pathlib import Path

import yaml

from conftest import repo_root
from endor_agent_kit.knowledge_pack import (
    PACK_SECTION_HEADING,
    default_task_profile_for_agent,
    load_knowledge_pack,
    render_knowledge_pack_section,
    render_task_profile_prompt,
    validate_knowledge_pack,
)
from endor_agent_kit.recipe import load_yaml_file


def test_default_knowledge_pack_validates_against_source_agents():
    agent_ids = {
        str(load_yaml_file(path)["id"])
        for path in (repo_root() / "source" / "agents").glob("*/recipe.yaml")
    }

    assert validate_knowledge_pack(agent_ids=agent_ids) == []


def test_knowledge_pack_loader_exposes_precedence_and_global_rules():
    pack = load_knowledge_pack()

    assert pack.name == "Endor Knowledge Pack"
    assert set(pack.workflows) == {
        "ai-sast-triage",
        "dependency-decision-helper",
        "endor-troubleshooter",
        "package-risk-summary",
        "probe-droid",
        "remediation-planner",
        "repository-dependency-reviewer",
        "sca-remediation",
        "upgrade-impact-analysis",
        "vulnerability-explainer",
    }
    assert any("workflow output contracts" in item for item in pack.precedence)
    assert any("source recipe instructions" in item for item in pack.precedence)
    assert [rule.id for rule in pack.global_rules] == [
        "context-first",
        "namespace-provenance",
        "query-efficiency",
        "verified-evidence",
        "data-gaps",
    ]
    assert [profile.id for profile in pack.workflow_for("sca-remediation").task_profiles] == [
        "resolve-scope",
        "evidence-check",
        "selection-plan",
    ]


def test_knowledge_pack_renders_global_section_for_known_agent():
    section = render_knowledge_pack_section("sca-remediation")

    assert section.startswith(PACK_SECTION_HEADING)
    assert "Context first" in section
    assert "Evidence Gate Contract" in section
    assert "Agent Task Profiles" in section
    assert "`selection-plan` - Selection Plan" in section
    assert "Never use memory" in section
    assert "Never dump or `cat` Endor config files" in section
    assert "SCA Remediation Evidence Contract" in section
    assert "Preferred evidence resources: `Project`, `Finding`, `VersionUpgrade`" in section
    assert "namespace_provenance" in section
    assert "data_gaps" in section
    assert "Workflow output contracts" in section


def test_knowledge_pack_renders_task_profile_prompt():
    prompt = render_task_profile_prompt("sca-remediation", "selection-plan")

    assert "Agent task profile: `selection-plan`" in prompt
    assert "Use this compact profile instead of running the full workflow" in prompt
    assert "Minimal evidence:" in prompt
    assert "VersionUpgrade/UIA evidence" in prompt
    assert "Output focus:" in prompt
    assert default_task_profile_for_agent("sca-remediation") == "selection-plan"


def test_knowledge_pack_validator_rejects_unknown_workflow_agent(tmp_path):
    _write_minimal_pack(tmp_path)
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "unknown-agent.yaml").write_text(
        yaml.safe_dump(
            {
                "agent_id": "unknown-agent",
                "title": "Unknown Agent Contract",
                "summary": "Use namespace evidence and report data_gaps.",
                "resources": [
                    {
                        "name": "Project",
                        "purpose": "Resolve namespace-scoped project identity.",
                        "fields": ["uuid", "meta.name"],
                    }
                ],
                "retrieval_steps": ["Resolve namespace and project evidence."],
                "fallbacks": ["Record lookup failures in data_gaps."],
                "data_gaps": ["Record missing namespace access in data_gaps."],
                "task_profiles": [
                    {
                        "id": "evidence-check",
                        "title": "Evidence Check",
                        "summary": "Use namespace evidence and report data_gaps.",
                        "when_to_use": ["Use for read-only evidence checks."],
                        "minimal_evidence": ["Namespace evidence or data_gaps."],
                        "stop_when": ["Evidence is known or data_gaps are recorded."],
                        "output_focus": ["Return evidence_queries and data_gaps."],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    errors = validate_knowledge_pack(tmp_path, agent_ids={"sca-remediation"})

    assert any("references unknown agent 'unknown-agent'" in error for error in errors)


def test_knowledge_pack_validator_rejects_forbidden_public_wording(tmp_path):
    forbidden = "python " + "package"
    _write_minimal_pack(
        tmp_path,
        global_rule_guidance=f"Use a {forbidden} to fetch evidence.",
    )

    errors = validate_knowledge_pack(tmp_path)

    assert any(f"forbidden public wording {forbidden!r}" in error for error in errors)


def _write_minimal_pack(root: Path, *, global_rule_guidance: str = "Record data_gaps.") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pack.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "name": "Endor Knowledge Pack",
                "version": "0.1.0",
                "precedence": [
                    "workflow output contracts and hard guardrails remain authoritative",
                    "source recipe instructions remain authoritative over this pack",
                    "Endor Knowledge Pack guidance augments generated recipes",
                ],
                "global_rules": [
                    {
                        "id": "context-first",
                        "title": "Context first",
                        "guidance": global_rule_guidance,
                    },
                    {
                        "id": "namespace-provenance",
                        "title": "Namespace provenance",
                        "guidance": "Record namespace_provenance.",
                    },
                    {
                        "id": "query-efficiency",
                        "title": "Efficient Endor queries",
                        "guidance": "Use field masks.",
                    },
                    {
                        "id": "verified-evidence",
                        "title": "Verified evidence only",
                        "guidance": "Use verified evidence.",
                    },
                    {
                        "id": "data-gaps",
                        "title": "Data gaps",
                        "guidance": "Record data_gaps.",
                    },
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
