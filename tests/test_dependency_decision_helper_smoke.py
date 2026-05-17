from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from endor_agent_kit.compilers import compile_claude_code

from conftest import repo_root


def _copy_agent(tmp_path: Path) -> Path:
    src = repo_root() / "agents" / "dependency-decision-helper"
    dst = tmp_path / "dependency-decision-helper"
    shutil.copytree(src, dst)
    return dst / "recipe.yaml"


def test_dependency_decision_helper_compiled_artifacts_carry_load_bearing_rules(tmp_path):
    recipe = _copy_agent(tmp_path)
    compile_claude_code(recipe)

    developer = (
        recipe.parent / "dist" / "claude-code" / "developer-edition" / "dependency-decision-helper.md"
    ).read_text()
    enterprise = (
        recipe.parent / "dist" / "claude-code" / "enterprise-edition" / "dependency-decision-helper.md"
    ).read_text()

    for body in (developer, enterprise):
        assert "Dependency Decision Helper" in body
        assert "mcpServers:" in body
        assert "endor-cli-tools:" in body
        assert "alwaysLoad: true" in body
        assert "check_dependency_for_risks" in body
        assert "check_dependency_for_vulnerabilities" in body
        assert "get_endor_vulnerability" in body
        assert "Never fabricate" in body
        assert "data_gaps" in body
        assert "https://app.endorlabs.com" in body
        assert "Malware detected" in body
        assert "CISA KEV" in body

    assert "PackageVersion UUID Lookup" in enterprise
    assert "QuerySimilarPackages" in enterprise


def test_eval_cases_cover_v0_outcomes():
    evals = yaml.safe_load((repo_root() / "agents" / "dependency-decision-helper" / "evals" / "cases.yaml").read_text())

    case_ids = {case["id"] for case in evals["cases"]}
    assert case_ids == {
        "safe-package",
        "vulnerable-usable",
        "critical-or-malware-blocked",
        "critical-not-recommended",
        "degraded-unknown-package",
    }
    verdicts = {case["expected"]["verdict"] for case in evals["cases"]}
    assert verdicts == {"SAFE", "SAFE_WITH_CONDITIONS", "NOT_RECOMMENDED", "BLOCKED"}
