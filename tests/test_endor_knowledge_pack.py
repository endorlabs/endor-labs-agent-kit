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
    assert sorted(pack.query_recipes) == [
        "ai-sast-list",
        "cicd-posture-findings",
        "current-malware-intelligence",
        "exposure-guidance-source",
        "finding-browser-filtered",
        "finding-by-uuid",
        "github-branch-protection",
        "github-workflow-files",
        "local-git-state",
        "local-manifest-inventory",
        "mcp-finding-by-uuid-check",
        "mcp-finding-by-uuid-full",
        "mcp-vulnerability-by-id-check",
        "mcp-vulnerability-by-id-full",
        "package-version-exact",
        "project-branch-coverage",
        "project-by-git",
        "sca-finding-availability",
        "scan-result-by-uuid",
        "selected-source-usage",
        "tenant-package-inventory",
        "tenant-package-version-exact",
        "version-upgrade-by-package",
        "version-upgrade-detail",
        "version-upgrade-summary",
    ]
    assert set(pack.workflows) == {
        "ai-sast-triage",
        "cicd-posture",
        "dependency-decision-helper",
        "endor-troubleshooter",
        "findings-browser",
        "malware-response",
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
        "evidence-ledger",
        "data-gaps",
    ]
    assert [profile.id for profile in pack.workflow_for("sca-remediation").task_profiles] == [
        "resolve-scope",
        "evidence-check",
        "selection-plan",
    ]
    assert [plan.profile_id for plan in pack.workflow_for("sca-remediation").evidence_query_plans] == [
        "resolve-scope",
        "evidence-check",
        "selection-plan",
    ]
    assert [
        recipe.id
        for recipe in pack.workflow_for("sca-remediation").evidence_query_recipes_for("selection-plan")
    ] == [
        "version-upgrade-summary",
        "version-upgrade-detail",
        "selected-source-usage",
        "selected-finding-detail",
    ]
    query_efficiency = next(rule for rule in pack.global_rules if rule.id == "query-efficiency")
    assert "--list-all" in query_efficiency.guidance
    assert "complete scoped inventory or count" in query_efficiency.guidance
    ai_sast_recipe = next(
        recipe
        for recipe in pack.workflow_for("ai-sast-triage").evidence_query_recipes
        if recipe.id == "ai-sast-list"
    )
    assert ai_sast_recipe.canonical_id == "ai-sast-list"
    assert "SYSTEM_EVALUATION_METHOD_DEFINITION_AI_SAST" in ai_sast_recipe.template
    assert 'finding_tags contains "AI_SAST"' not in ai_sast_recipe.template
    assert "--list-all" in ai_sast_recipe.template
    assert "spec.explanation" not in ai_sast_recipe.template
    assert "spec.explanation" not in ai_sast_recipe.fields
    assert all(
        recipe.canonical_id in pack.query_recipes
        for workflow in pack.workflows.values()
        for recipe in workflow.evidence_query_recipes
    )


def test_runtime_task_profile_prompts_carry_gemini_contract_guards():
    troubleshooter = render_task_profile_prompt("endor-troubleshooter", "diagnose", compact=True)
    probe = render_task_profile_prompt("probe-droid", "evidence-check", compact=True)

    assert "every nested issue_lanes.next_step, validation, action, why, reasoning" in troubleshooter
    assert "free of raw tool names or command-shaped" in troubleshooter
    assert "run a baseline scan" in troubleshooter
    assert "Every future_action_contracts row must include" in troubleshooter
    assert "confirmation_required true" in troubleshooter
    assert "github_app_coverage must be a non-empty" in probe
    assert "Every repository lane row, including ambiguous_matches" in probe
    assert "not github_repository alone" in probe
    assert "Onboarded" in probe
    assert "project_uuid and endor_monitored_branch" in probe
    assert "not onboarded_healthy_repositories" in probe


def test_knowledge_pack_renders_global_section_for_known_agent():
    section = render_knowledge_pack_section("sca-remediation")

    assert section.startswith(PACK_SECTION_HEADING)
    assert "Context first" in section
    assert "Evidence Gate Contract" in section
    assert "Scope Normalization Contract" in section
    assert "normalized repo identity" in section
    assert "Mutability Gate Contract" in section
    assert "future action contract" in section
    assert "Agent Task Profiles" in section
    assert "`selection-plan` - Selection Plan" in section
    assert "Evidence Query Plans" in section
    assert "`selection-plan` - Selection Plan Query Plan" in section
    assert "Evidence Query Recipes" in section
    assert "`version-upgrade-summary` (selection-plan)" in section
    assert "Canonical: `version-upgrade-summary`" in section
    assert "endorctl api list -r VersionUpgrade -n <namespace>" in section
    assert "narrowing through VersionUpgrade before detailed Finding expansion" in section
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
    assert "Stop when:" in prompt
    assert "Minimal evidence:" in prompt
    assert "VersionUpgrade/UIA evidence" in prompt
    assert "Evidence query plan:" in prompt
    assert "Query VersionUpgrade/UIA candidate summaries" in prompt
    assert "Do not enumerate broad Finding inventories" in prompt
    assert "Evidence query recipes:" in prompt
    assert "version-upgrade-summary" in prompt
    assert "canonical `version-upgrade-summary`" in prompt
    assert "--field-mask" in prompt
    assert "Output focus:" in prompt
    assert default_task_profile_for_agent("sca-remediation") == "selection-plan"

    compact = render_task_profile_prompt("sca-remediation", "selection-plan", compact=True)

    assert "Minimal evidence:" in compact
    assert "Required output focus:" in compact
    assert "resource is `Finding`" in compact
    assert "selected_remediation.branch_name" in compact
    assert "change_requests[].proposed_branch" in compact
    assert "never use selection labels such as `selected`" in compact


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
                "evidence_query_plans": [
                    {
                        "profile_id": "evidence-check",
                        "title": "Evidence Check Query Plan",
                        "objective": "Check namespace evidence and record data_gaps.",
                        "query_order": ["Resolve namespace evidence."],
                        "avoid": ["Do not guess missing namespace evidence."],
                        "stop_after": ["Stop after evidence exists or data_gaps are recorded."],
                        "data_gaps": ["Record missing namespace evidence in data_gaps."],
                    }
                ],
                "evidence_query_recipes": [
                    {
                        "profile_id": "evidence-check",
                        "id": "project-by-git",
                        "resource": "Project",
                        "purpose": "Resolve namespace evidence.",
                        "template": "endorctl api list -r Project -n <namespace> --field-mask \"uuid,meta.name\" -o json",
                        "fields": ["uuid", "meta.name"],
                        "constraints": ["Record missing namespace evidence in data_gaps."],
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


def test_knowledge_pack_validator_rejects_query_plan_for_unknown_profile(tmp_path):
    _write_minimal_pack(tmp_path)
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    workflow = _minimal_workflow()
    workflow["evidence_query_plans"][0]["profile_id"] = "unknown-profile"
    (workflows / "sca-remediation.yaml").write_text(
        yaml.safe_dump(workflow, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_knowledge_pack(tmp_path, agent_ids={"sca-remediation"})

    assert any("references unknown task profile 'unknown-profile'" in error for error in errors)
    assert any("missing plan for task profile 'evidence-check'" in error for error in errors)


def test_knowledge_pack_validator_rejects_sca_selection_plan_finding_first(tmp_path):
    _write_minimal_pack(tmp_path)
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    workflow = _minimal_workflow()
    workflow["task_profiles"].append(
        {
            "id": "selection-plan",
            "title": "Selection Plan",
            "summary": "Select one candidate and report data_gaps.",
            "when_to_use": ["Use when selecting a remediation."],
            "minimal_evidence": ["VersionUpgrade and Finding evidence or data_gaps."],
            "stop_when": ["Stop with data_gaps when evidence is missing."],
            "output_focus": ["Return selected_remediation and data_gaps."],
        }
    )
    workflow["evidence_query_plans"].append(
        {
            "profile_id": "selection-plan",
            "title": "Selection Plan Query Plan",
            "objective": "Select one candidate and record data_gaps.",
            "query_order": [
                "Query Finding evidence first.",
                "Query VersionUpgrade evidence second.",
            ],
            "avoid": ["Do not guess missing data_gaps."],
            "stop_after": ["Stop after selection or data_gaps."],
            "data_gaps": ["Record missing evidence in data_gaps."],
        }
    )
    (workflows / "sca-remediation.yaml").write_text(
        yaml.safe_dump(workflow, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_knowledge_pack(tmp_path, agent_ids={"sca-remediation"})

    assert any("selection-plan must narrow with VersionUpgrade before Finding detail expansion" in error for error in errors)


def test_knowledge_pack_validator_rejects_unsafe_query_recipe_template(tmp_path):
    _write_minimal_pack(tmp_path)
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    workflow = _minimal_workflow()
    workflow["evidence_query_recipes"][0]["template"] = "endorctl api list -r Finding --list-all -o json"
    (workflows / "sca-remediation.yaml").write_text(
        yaml.safe_dump(workflow, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_knowledge_pack(tmp_path, agent_ids={"sca-remediation"})

    assert any("must include explicit namespace" in error for error in errors)
    assert any("must include --field-mask" in error for error in errors)
    assert any("broad Finding --list-all templates are not allowed" in error for error in errors)


def test_knowledge_pack_validator_rejects_unknown_canonical_query_recipe_ref(tmp_path):
    _write_minimal_pack(tmp_path)
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    workflow = _minimal_workflow()
    workflow["evidence_query_recipes"][0]["canonical_id"] = "missing-query"
    (workflows / "sca-remediation.yaml").write_text(
        yaml.safe_dump(workflow, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_knowledge_pack(tmp_path, agent_ids={"sca-remediation"})

    assert any(
        "references unknown canonical query recipe 'missing-query'" in error
        for error in errors
    )


def test_knowledge_pack_validator_rejects_canonical_query_recipe_template_drift(tmp_path):
    _write_minimal_pack(tmp_path)
    _write_minimal_query_catalog(tmp_path)
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    workflow = _minimal_workflow()
    workflow["evidence_query_recipes"][0]["canonical_id"] = "project-by-git"
    workflow["evidence_query_recipes"][0]["template"] = (
        'endorctl api list -r Project -n <namespace> --field-mask "uuid" -o json'
    )
    (workflows / "sca-remediation.yaml").write_text(
        yaml.safe_dump(workflow, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_knowledge_pack(tmp_path, agent_ids={"sca-remediation"})

    assert any(
        "template does not match canonical query recipe 'project-by-git'" in error
        for error in errors
    )


def test_knowledge_pack_validator_rejects_unsafe_canonical_query_recipe_template(tmp_path):
    _write_minimal_pack(tmp_path)
    _write_minimal_query_catalog(
        tmp_path,
        template="endorctl api list -r Finding --list-all -o json",
    )

    errors = validate_knowledge_pack(tmp_path)

    assert any("query-recipes.yaml recipes[0].template: endorctl api commands must include explicit namespace" in error for error in errors)
    assert any("query-recipes.yaml recipes[0].template: endorctl api list commands must include --field-mask" in error for error in errors)
    assert any("query-recipes.yaml recipes[0].template: broad Finding --list-all templates are not allowed" in error for error in errors)


def test_knowledge_pack_validator_rejects_field_mask_parent_child_collisions(tmp_path):
    _write_minimal_pack(tmp_path)
    _write_minimal_query_catalog(
        tmp_path,
        template=(
            'endorctl api list -r VersionUpgrade -n <namespace> '
            '--field-mask "uuid,spec.upgrade_info,spec.upgrade_info.cia_results" -o json'
        ),
    )

    errors = validate_knowledge_pack(tmp_path)

    assert any("field-mask must not include both a parent path and child path" in error for error in errors)


def test_knowledge_pack_validator_accepts_scoped_ai_sast_list_all_query(tmp_path):
    _write_minimal_pack(tmp_path)
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    workflow = _minimal_workflow()
    workflow["evidence_query_recipes"][0]["template"] = (
        'endorctl api list -r Finding -n <namespace> --filter '
        '\'context.type==CONTEXT_TYPE_MAIN and spec.project_uuid=="<PROJECT_UUID>" '
        'and spec.method=="SYSTEM_EVALUATION_METHOD_DEFINITION_AI_SAST"\' '
        '--field-mask "uuid,context.type,spec.project_uuid,spec.method" --list-all -o json'
    )
    (workflows / "sca-remediation.yaml").write_text(
        yaml.safe_dump(workflow, sort_keys=False),
        encoding="utf-8",
    )

    errors = validate_knowledge_pack(tmp_path, agent_ids={"sca-remediation"})

    assert "workflows/sca-remediation.yaml evidence_query_recipes[0].template: broad Finding --list-all templates are not allowed" not in errors


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


def _write_minimal_query_catalog(
    root: Path,
    *,
    template: str = 'endorctl api list -r Project -n <namespace> --field-mask "uuid,meta.name" -o json',
) -> None:
    (root / "query-recipes.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "recipes": [
                    {
                        "id": "project-by-git",
                        "title": "Project By Git",
                        "resource": "Project",
                        "purpose": "Resolve project evidence.",
                        "template": template,
                        "fields": ["uuid", "meta.name"],
                        "constraints": ["Use explicit namespace."],
                        "completeness": "Complete for one selected namespace.",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _minimal_workflow() -> dict:
    return {
        "agent_id": "sca-remediation",
        "title": "SCA Remediation Evidence Contract",
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
        "evidence_query_plans": [
            {
                "profile_id": "evidence-check",
                "title": "Evidence Check Query Plan",
                "objective": "Check namespace evidence and record data_gaps.",
                "query_order": ["Resolve namespace evidence."],
                "avoid": ["Do not guess missing namespace evidence."],
                "stop_after": ["Stop after evidence exists or data_gaps are recorded."],
                "data_gaps": ["Record missing namespace evidence in data_gaps."],
            }
        ],
        "evidence_query_recipes": [
            {
                "profile_id": "evidence-check",
                "id": "project-by-git",
                "resource": "Project",
                "purpose": "Resolve namespace evidence.",
                "template": "endorctl api list -r Project -n <namespace> --field-mask \"uuid,meta.name\" -o json",
                "fields": ["uuid", "meta.name"],
                "constraints": ["Record missing namespace evidence in data_gaps."],
            }
        ],
    }
