from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from conftest import repo_root
from endor_agent_kit.cli import main
from endor_agent_kit.compilers import compile_claude_code, compile_claude_managed_agents, compile_raw
from endor_agent_kit.publisher import publish_recipe
from endor_agent_kit.source_authoring import check_source_recipe_authoring
from endor_agent_kit.validator import validate_recipe_file
from host_artifact_bundle_contract import (
    assert_codex_skill_bundle,
    assert_host_bundle_files,
    assert_mcp_free_generated_artifact,
    assert_no_nested_edition_dirs,
)


def _copy_agent(tmp_path: Path) -> Path:
    src = repo_root() / "source" / "agents" / "cicd-posture"
    dst = tmp_path / "source" / "agents" / "cicd-posture"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("dist"))
    return dst / "recipe.yaml"


def test_cicd_posture_recipe_is_read_only_mcp_free_and_new_agent_ready(tmp_path, capsys):
    recipe = _copy_agent(tmp_path)
    data = yaml.safe_load(recipe.read_text(encoding="utf-8"))

    report = check_source_recipe_authoring(recipe, new_agent=True)
    authoring_status = main(["authoring-check", str(recipe), "--new-agent"])
    doctor_status = main(["doctor-new-agent", str(recipe)])
    output = capsys.readouterr().out

    assert validate_recipe_file(recipe) == []
    assert report.ok
    assert authoring_status == 0
    assert doctor_status == 0
    assert "OK: strict new-agent authoring" in output
    assert data["id"] == "cicd-posture"
    assert data["safety_class"] == "read_only"
    assert data["endor_tier_minimum"] == "enterprise"
    assert data["supported_transports"] == ["endorctl_api"]
    assert data["required_endor_mcp_tools"] == []
    assert data["requires_endor_mcp"] == ""
    assert data["mutations"] == []
    assert data["compatible_hosts"] == ["claude-code", "claude-managed-agents", "codex", "gemini", "portable"]
    assert data["host_editions"] == {
        "claude-code": ["enterprise-edition"],
        "claude-managed-agents": ["enterprise-edition"],
        "gemini": ["enterprise-edition"],
    }
    assert data["host_capabilities_required"] == {
        "run_commands": True,
        "read_files": True,
        "write_files": False,
        "open_pr": False,
    }
    input_names = {item["name"] for item in data["inputs"]}
    assert {
        "namespace",
        "github_org",
        "repository_urls",
        "endor_project_selector",
        "github_inventory_json",
        "include_local_ci_files",
        "sampling_mode",
        "sample_size",
        "sample_seed",
        "report_mode",
    } == input_names
    output_names = {item["name"] for item in data["outputs"]}
    assert {
        "posture_verdict",
        "summary",
        "scope",
        "raw_counts",
        "dimension_scores",
        "score_validation",
        "critical_overrides",
        "endor_findings",
        "github_evidence",
        "local_ci_evidence",
        "recommended_actions",
        "evidence_queries",
        "data_gaps",
    } == output_names


def test_cicd_posture_compiled_artifact_carries_posture_contract(tmp_path):
    recipe = _copy_agent(tmp_path)

    compile_claude_code(recipe)

    artifact = (
        recipe.parent
        / "dist"
        / "claude-code"
        / "enterprise-edition"
        / "cicd-posture.md"
    ).read_text(encoding="utf-8")
    header = artifact.split("---", 2)[1]

    assert "CI/CD And Supply Chain Posture" in artifact
    assert "## Endor Knowledge Pack" in artifact
    assert "CI/CD Posture Evidence Contract" in artifact
    assert "cicd-posture-findings" in artifact
    assert "github-branch-protection" in artifact
    assert "github-workflow-files" in artifact
    assert "FINDING_CATEGORY_SCPM" in artifact
    assert "FINDING_CATEGORY_CICD" in artifact
    assert "FINDING_CATEGORY_GHACTIONS" in artifact
    assert "FINDING_CATEGORY_SUPPLY_CHAIN" in artifact
    assert "branch protection" in artifact
    assert "CODEOWNERS" in artifact
    assert "action pinning" in artifact
    assert "self_hosted_runners" in artifact
    assert "posture_verdict" in artifact
    assert "raw_counts" in artifact
    assert "dimension_scores" in artifact
    assert "score_validation" in artifact
    assert "critical_overrides" in artifact
    assert "endor-agent-kit validate-cicd-posture-output --gate posture" in artifact
    assert "Never run `endorctl scan`" in artifact
    assert "workflow dispatches" in artifact
    assert "Never mutate" in artifact
    assert "Endor state" in artifact
    assert "`--traverse` before reporting the project as missing" in artifact
    assert "Do not substitute example,\n  remembered, cached, or prior-session repositories" in artifact
    assert "`OWASP/NodejsGoat`" in artifact
    assert "`hkhcoder/vprofile-repo`" in artifact
    assert "return `INSUFFICIENT_DATA` with a `data_gaps` entry" in artifact
    assert "`github_evidence` and `local_ci_evidence` must always be JSON arrays" in artifact
    assert "Never return either field as an object\nor map" in artifact
    assert "must use `filter_summary` and `field_mask_summary`" in artifact
    assert "do not emit raw\n`filter`, `field_mask`, `command`, or `output` fields" in artifact
    assert "disallowedTools: Bash" not in header
    assert_mcp_free_generated_artifact(artifact)


def test_cicd_posture_managed_agents_artifacts_carry_github_boundary(tmp_path):
    recipe = _copy_agent(tmp_path)

    compile_claude_managed_agents(recipe)

    out_dir = recipe.parent / "dist" / "claude-managed-agents" / "enterprise-edition"
    assert_host_bundle_files(out_dir, {"agent.yaml", "environment.yaml", "session-template.yaml"})
    managed = yaml.safe_load((out_dir / "agent.yaml").read_text(encoding="utf-8"))
    environment = yaml.safe_load((out_dir / "environment.yaml").read_text(encoding="utf-8"))
    session = yaml.safe_load((out_dir / "session-template.yaml").read_text(encoding="utf-8"))

    assert not (recipe.parent / "dist" / "claude-managed-agents" / "developer-edition").exists()
    assert managed["name"] == "CI/CD And Supply Chain Posture"
    assert managed["metadata"]["endor_agent_kit_recipe_id"] == "cicd-posture"
    assert managed["mcp_servers"] == []
    assert "vault_ids" not in session
    assert environment["name"] == "endor-cicd-posture"
    assert environment["config"]["networking"]["allowed_hosts"] == [
        "https://api.endorlabs.com",
        "https://api.github.com",
        "https://github.com",
    ]
    assert environment["config"]["networking"]["allow_mcp_servers"] is False
    assert "GitHub.com inventory/file lookups" in managed["system"]
    assert "Do not require Endor MCP" in managed["system"]
    assert "branch protection" in managed["system"]
    assert "score_validation" in managed["system"]


def test_cicd_posture_publish_writes_all_host_surfaces(tmp_path):
    recipe = _copy_agent(tmp_path)
    dest = tmp_path / "endor-labs-agent-kit"

    written = publish_recipe(recipe, dest)

    written_paths = {path.relative_to(dest).as_posix() for path in written}
    assert written_paths == {
        "claude-code/cicd-posture/cicd-posture.md",
        "claude-code/cicd-posture/README.md",
        "claude-code/cicd-posture/architecture.svg",
        "claude-code/cicd-posture/endorctl-setup.md",
        "claude-managed-agents/cicd-posture/agent.yaml",
        "claude-managed-agents/cicd-posture/environment.yaml",
        "claude-managed-agents/cicd-posture/session-template.yaml",
        "claude-managed-agents/cicd-posture/README.md",
        "claude-managed-agents/cicd-posture/architecture.svg",
        "claude-managed-agents/cicd-posture/endorctl-setup.md",
        "codex/cicd-posture/SKILL.md",
        "codex/cicd-posture/README.md",
        "codex/cicd-posture/architecture.svg",
        "codex/cicd-posture/endorctl-setup.md",
        "gemini/cicd-posture/SKILL.md",
        "gemini/cicd-posture/cicd-posture.md",
        "gemini/cicd-posture/README.md",
        "gemini/cicd-posture/architecture.svg",
        "gemini/cicd-posture/endorctl-setup.md",
        "portable/cicd-posture/README.md",
        "portable/cicd-posture/agent.md",
        "portable/cicd-posture/agent.manifest.json",
        "portable/cicd-posture/output-contract.md",
        "portable/cicd-posture/architecture.svg",
        "portable/cicd-posture/endorctl-setup.md",
        "manifest.json",
        "README.md",
    }

    agent_dir = dest / "claude-code" / "cicd-posture"
    managed_dir = dest / "claude-managed-agents" / "cicd-posture"
    codex_dir = dest / "codex" / "cicd-posture"
    gemini_dir = dest / "gemini" / "cicd-posture"
    portable_dir = dest / "portable" / "cicd-posture"
    assert_host_bundle_files(agent_dir, {"cicd-posture.md", "README.md", "architecture.svg", "endorctl-setup.md"})
    assert_host_bundle_files(
        managed_dir,
        {"agent.yaml", "environment.yaml", "session-template.yaml", "README.md", "architecture.svg", "endorctl-setup.md"},
    )
    assert_codex_skill_bundle(
        codex_dir,
        expected_files={"SKILL.md", "README.md", "architecture.svg", "endorctl-setup.md"},
        skill_markers=(
            "Keep the workflow read-only",
            "CI/CD Posture Evidence Contract",
            "validate-cicd-posture-output",
            "FINDING_CATEGORY_SUPPLY_CHAIN",
        ),
    )
    assert_host_bundle_files(
        gemini_dir,
        {"SKILL.md", "cicd-posture.md", "README.md", "architecture.svg", "endorctl-setup.md"},
    )
    assert_host_bundle_files(
        portable_dir,
        {"README.md", "agent.md", "agent.manifest.json", "output-contract.md", "architecture.svg", "endorctl-setup.md"},
    )
    assert_no_nested_edition_dirs(agent_dir)
    assert_no_nested_edition_dirs(managed_dir)
    assert_no_nested_edition_dirs(gemini_dir)

    root_readme = (dest / "README.md").read_text(encoding="utf-8")
    agent_readme = (agent_dir / "README.md").read_text(encoding="utf-8")
    managed_readme = (managed_dir / "README.md").read_text(encoding="utf-8")
    codex_readme = (codex_dir / "README.md").read_text(encoding="utf-8")
    gemini_readme = (gemini_dir / "README.md").read_text(encoding="utf-8")
    setup = (agent_dir / "endorctl-setup.md").read_text(encoding="utf-8")
    architecture = (agent_dir / "architecture.svg").read_text(encoding="utf-8")

    assert "CI/CD And Supply Chain Posture" in root_readme
    assert "claude-code/cicd-posture/" in root_readme
    assert "claude-managed-agents/cicd-posture/" in root_readme
    assert "codex/cicd-posture/" in root_readme
    assert "gemini/cicd-posture/" in root_readme
    assert "portable/cicd-posture/" in root_readme
    assert "Use the cicd-posture skill to assess CI/CD and supply chain posture" in root_readme
    assert "@agent-cicd-posture assess CI/CD and supply chain posture" in root_readme
    assert "CI/CD Posture does not need an Endor MCP server" in agent_readme
    assert "deterministic score" in agent_readme
    assert "Read-only GitHub.com credentials available to the managed session" in managed_readme
    assert "Assess CI/CD and supply chain posture for namespace <namespace>" in managed_readme
    assert "CI/CD And Supply Chain Posture Codex Skill" in codex_readme
    assert "CI/CD And Supply Chain Posture Gemini CLI Bundle" in gemini_readme
    assert "CI/CD And Supply Chain Posture also needs read-only GitHub.com evidence access" in setup
    assert "must not clone repositories" in setup
    assert "mutate GitHub settings" in setup
    assert "Deterministic Band" in architecture
    assert "CONTRACT" in architecture


def test_cicd_posture_raw_setup_documents_github_evidence_boundary(tmp_path):
    recipe = _copy_agent(tmp_path)

    compile_raw(recipe)

    setup = (recipe.parent / "dist" / "raw" / "endorctl-setup.md").read_text(encoding="utf-8")
    assert "CI/CD And Supply Chain Posture also needs read-only GitHub.com evidence access" in setup
    assert "must not clone repositories" in setup
    assert "mutate GitHub settings" in setup


def test_cicd_posture_eval_cases_cover_scope_and_adversarial_inputs():
    cases_path = repo_root() / "source" / "agents" / "cicd-posture" / "evals" / "cases.yaml"
    cases = yaml.safe_load(cases_path.read_text(encoding="utf-8"))["cases"]
    ids = {case["id"] for case in cases}

    assert {
        "namespace-critical-supply-chain-posture",
        "repository-subset-high-risk-unpinned-actions",
        "healthy-repository-with-proven-branch-protection",
        "missing-github-inventory-partial-endor-only",
        "large-namespace-stratified-sampled-posture",
        "no-namespace-insufficient-data",
        "adversarial-workflow-file-injection",
    } == ids
    adversarial = next(case for case in cases if case["id"] == "adversarial-workflow-file-injection")
    assert adversarial["adversarial"] is True
    assert "must_not" in adversarial["expected"]
