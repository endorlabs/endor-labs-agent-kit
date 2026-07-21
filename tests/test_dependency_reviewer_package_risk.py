from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from endor_agent_kit.compilers import compile_claude_code, compile_raw

from conftest import repo_root


def _copy_agent(tmp_path: Path) -> Path:
    src = repo_root() / "source" / "agents" / "dependency-reviewer"
    dst = tmp_path / "dependency-reviewer"
    shutil.copytree(src, dst)
    return dst / "recipe.yaml"


def test_dependency_reviewer_package_risk_compiled_artifacts_carry_expected_rules(tmp_path):
    recipe = _copy_agent(tmp_path)
    compile_claude_code(recipe)

    enterprise = (
        recipe.parent / "dist" / "claude-code" / "enterprise-edition" / "dependency-reviewer-package-risk.md"
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
    assert "`profile`, `risk_posture`, `findings`, `strengths`, `next_checks`" in enterprise
    assert "Keep tenant/project lookups out of scope unless the request needs them" in enterprise
    assert "retry that lookup\nwith `--traverse`" in enterprise
    assert "disallowedTools: Bash" not in enterprise.split("---", 2)[1]
    assert "## Repository Inspection Rules" not in enterprise
    assert "## Package Decision Verdicts" not in enterprise


def test_dependency_reviewer_package_risk_eval_cases_cover_v0_postures():
    evals = yaml.safe_load((repo_root() / "source" / "agents" / "dependency-reviewer" / "evals" / "cases.yaml").read_text())

    cases = [case for case in evals["cases"] if case["input"]["task_profile"] == "package-risk"]
    assert {case["id"] for case in cases} == {
        "package-risk-evidence-limited",
        "package-profile-missing-version",
    }
    assert {case["expected"]["risk_posture"] for case in cases} == {"MODERATE", "UNKNOWN"}


def test_dependency_reviewer_package_risk_setup_doc_uses_agent_name(tmp_path):
    recipe = _copy_agent(tmp_path)

    compile_raw(recipe)

    setup = (recipe.parent / "dist" / "raw" / "endorctl-setup.md").read_text()
    assert "The Enterprise Edition Dependency Reviewer uses" in setup
