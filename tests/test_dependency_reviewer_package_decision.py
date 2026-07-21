from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from endor_agent_kit.compilers import compile_claude_code

from conftest import repo_root


def _copy_agent(tmp_path: Path) -> Path:
    src = repo_root() / "source" / "agents" / "dependency-reviewer"
    dst = tmp_path / "dependency-reviewer"
    shutil.copytree(src, dst)
    return dst / "recipe.yaml"


def test_dependency_reviewer_package_decision_compiled_artifacts_carry_load_bearing_rules(tmp_path):
    recipe = _copy_agent(tmp_path)
    compile_claude_code(recipe)

    enterprise = (
        recipe.parent / "dist" / "claude-code" / "enterprise-edition" / "dependency-reviewer-package-decision.md"
    ).read_text()

    assert (recipe.parent / "dist" / "claude-code" / "developer-edition").is_dir()
    assert "Dependency Reviewer" in enterprise
    assert "mcpServers:" in enterprise
    assert "endor-cli-tools:" in enterprise
    assert "alwaysLoad: true" in enterprise
    assert "check_dependency_for_risks" in enterprise
    assert "check_dependency_for_vulnerabilities" in enterprise
    assert "get_endor_vulnerability" in enterprise
    assert "Never fabricate" in enterprise
    assert "data_gaps" in enterprise
    assert "malware or a tenant firewall malware block" in enterprise
    assert "CISA KEV" in enterprise
    assert "`profile`, `verdict`, `conditions`, `alternatives`" in enterprise
    assert "Keep tenant/project lookups out of scope unless the request needs them" in enterprise
    assert "retry that lookup\nwith `--traverse`" in enterprise
    assert "## Repository Inspection Rules" not in enterprise
    assert "## Risk Postures" not in enterprise


def test_eval_cases_cover_v0_outcomes():
    evals = yaml.safe_load((repo_root() / "source" / "agents" / "dependency-reviewer" / "evals" / "cases.yaml").read_text())

    cases = [case for case in evals["cases"] if case["input"]["task_profile"] == "package-decision"]
    assert {case["id"] for case in cases} == {"package-decision-safe", "package-decision-blocked"}
    assert {case["expected"]["verdict"] for case in cases} == {"SAFE", "BLOCKED"}
