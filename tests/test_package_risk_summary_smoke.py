from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from endor_agent_kit.compilers import compile_claude_code, compile_raw

from conftest import repo_root


def _copy_agent(tmp_path: Path) -> Path:
    src = repo_root() / "source" / "agents" / "package-risk-summary"
    dst = tmp_path / "package-risk-summary"
    shutil.copytree(src, dst)
    return dst / "recipe.yaml"


def test_package_risk_summary_compiled_artifacts_carry_expected_rules(tmp_path):
    recipe = _copy_agent(tmp_path)
    compile_claude_code(recipe)

    enterprise = (
        recipe.parent / "dist" / "claude-code" / "enterprise-edition" / "package-risk-summary.md"
    ).read_text()

    assert not (recipe.parent / "dist" / "claude-code" / "developer-edition").exists()
    assert "Endor Labs Package Risk Summary" in enterprise
    assert "mcpServers:" in enterprise
    assert "endor-cli-tools:" in enterprise
    assert "alwaysLoad: true" in enterprise
    assert "check_dependency_for_risks" in enterprise
    assert "check_dependency_for_vulnerabilities" in enterprise
    assert "get_endor_vulnerability" in enterprise
    assert "Never fabricate" in enterprise
    assert "data_gaps" in enterprise
    assert "LOW | MODERATE | HIGH | CRITICAL | UNKNOWN" in enterprise
    assert "Default Endor Context Scope" in enterprise
    assert "package-level `oss` lookups" in enterprise
    assert "context.type==CONTEXT_TYPE_MAIN" in enterprise
    assert "Keep non-main counts separate" in enterprise
    assert "retry the project lookup with `--traverse`" in enterprise
    assert "disallowedTools: Bash" not in enterprise.split("---", 2)[1]
    assert "PackageVersion UUID Lookup" in enterprise
    assert "QuerySimilarPackages" in enterprise
    assert "endorctl api create" in enterprise


def test_package_risk_summary_eval_cases_cover_v0_postures():
    evals = yaml.safe_load((repo_root() / "source" / "agents" / "package-risk-summary" / "evals" / "cases.yaml").read_text())

    case_ids = {case["id"] for case in evals["cases"]}
    assert case_ids == {
        "low-risk-package",
        "vulnerable-package",
        "critical-package",
        "unknown-package",
    }
    postures = {case["expected"]["risk_posture"] for case in evals["cases"]}
    assert postures == {"LOW", "MODERATE", "CRITICAL", "UNKNOWN"}


def test_package_risk_summary_setup_doc_uses_agent_name(tmp_path):
    recipe = _copy_agent(tmp_path)

    compile_raw(recipe)

    setup = (recipe.parent / "dist" / "raw" / "endorctl-setup.md").read_text()
    assert "The Endor Labs Package Risk Summary artifact uses" in setup
    assert "Dependency Decision Helper uses" not in setup
