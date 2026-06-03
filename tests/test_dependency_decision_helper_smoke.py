from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from endor_agent_kit.compilers import compile_claude_code

from conftest import repo_root


def _copy_agent(tmp_path: Path) -> Path:
    src = repo_root() / "source" / "agents" / "dependency-decision-helper"
    dst = tmp_path / "dependency-decision-helper"
    shutil.copytree(src, dst)
    return dst / "recipe.yaml"


def test_dependency_decision_helper_compiled_artifacts_carry_load_bearing_rules(tmp_path):
    recipe = _copy_agent(tmp_path)
    compile_claude_code(recipe)

    enterprise = (
        recipe.parent / "dist" / "claude-code" / "enterprise-edition" / "dependency-decision-helper.md"
    ).read_text()

    assert not (recipe.parent / "dist" / "claude-code" / "developer-edition").exists()
    assert "Dependency Decision Helper" in enterprise
    assert "mcpServers:" in enterprise
    assert "endor-cli-tools:" in enterprise
    assert "alwaysLoad: true" in enterprise
    assert "check_dependency_for_risks" in enterprise
    assert "check_dependency_for_vulnerabilities" in enterprise
    assert "get_endor_vulnerability" in enterprise
    assert "Never fabricate" in enterprise
    assert "data_gaps" in enterprise
    assert "https://app.endorlabs.com" in enterprise
    assert "Malware detected" in enterprise
    assert "CISA KEV" in enterprise
    assert "Default Endor Context Scope" in enterprise
    assert "package-level `oss` lookups" in enterprise
    assert "context.type==CONTEXT_TYPE_MAIN" in enterprise
    assert "Keep non-main counts separate" in enterprise
    assert "retry the project lookup with `--traverse`" in enterprise
    assert "PackageVersion UUID Lookup" in enterprise
    assert "QuerySimilarPackages" in enterprise


def test_eval_cases_cover_v0_outcomes():
    evals = yaml.safe_load((repo_root() / "source" / "agents" / "dependency-decision-helper" / "evals" / "cases.yaml").read_text())

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
