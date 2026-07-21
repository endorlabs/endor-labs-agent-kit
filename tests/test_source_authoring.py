from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from endor_agent_kit.cli import main
from endor_agent_kit.source_authoring import check_source_recipe_authoring

from conftest import repo_root


def _copy_agent_source(tmp_path: Path, agent_id: str) -> Path:
    src = repo_root() / "source" / "agents" / agent_id
    dst = tmp_path / "source" / "agents" / agent_id
    shutil.copytree(src, dst)
    return dst / "recipe.yaml"


def test_source_authoring_check_accepts_existing_agent_recipes():
    for recipe in sorted((repo_root() / "source" / "agents").glob("*/recipe.yaml")):
        report = check_source_recipe_authoring(recipe)

        assert not report.errors


def test_all_source_agents_include_parent_namespace_traverse_fallback():
    for instructions in sorted((repo_root() / "source" / "agents").glob("*/instructions.md")):
        body = instructions.read_text(encoding="utf-8")

        assert "--traverse" in body, instructions
        assert (
            "matching project" in body
            or "matching Endor projects" in body
            or "PROJECT_NOT_FOUND" in body
            or "reporting the project as missing" in body
        ), instructions


def test_source_authoring_check_accepts_strict_new_mutating_agent(tmp_path, capsys):
    recipe = _copy_agent_source(tmp_path, "sca-remediation")

    report = check_source_recipe_authoring(recipe, new_agent=True)
    status = main(["authoring-check", str(recipe), "--new-agent"])
    output = capsys.readouterr().out

    assert report.ok
    assert report.agent_id == "sca-remediation"
    assert status == 0
    assert f"OK: {recipe}" in output


def test_doctor_new_agent_reports_pre_pr_readiness(tmp_path, capsys):
    recipe = _copy_agent_source(tmp_path, "sca-remediation")

    status = main(["doctor-new-agent", str(recipe)])
    output = capsys.readouterr().out

    assert status == 0
    assert f"Doctor New Agent: {recipe}" in output
    assert "OK: recipe validation" in output
    assert "OK: strict new-agent authoring" in output
    assert "- agent id: sca-remediation" in output
    assert "- safety class: mutating" in output
    assert "endor-agent-kit publish source/agents/*/recipe.yaml --dest . --prune --include-plugins" in output
    assert "OK: new agent is ready for an Agent Kit PR" in output


def test_doctor_new_agent_returns_failure_for_incomplete_new_agent(tmp_path, capsys):
    recipe = _copy_agent_source(tmp_path, "vulnerability-explainer")

    status = main(["doctor-new-agent", str(recipe)])
    output = capsys.readouterr().out

    assert status == 1
    assert "OK: recipe validation" in output
    assert "FAIL: strict new-agent authoring" in output
    assert "ERROR: architecture.required" in output
    assert "Next commands:" in output


def test_source_authoring_check_requires_new_agent_architecture(tmp_path):
    recipe = _copy_agent_source(tmp_path, "vulnerability-explainer")

    report = check_source_recipe_authoring(recipe, new_agent=True)

    assert "architecture.required" in {error.code for error in report.errors}


def test_source_authoring_check_requires_new_agent_eval_coverage(tmp_path):
    recipe = _copy_agent_source(tmp_path, "remediation-planning")

    report = check_source_recipe_authoring(recipe, new_agent=True)

    assert "evals.minimum_cases" in {error.code for error in report.errors}


def test_source_authoring_check_uses_shared_instruction_section_parser(tmp_path):
    recipe = _copy_agent_source(tmp_path, "vulnerability-explainer")
    instructions = recipe.parent / "instructions.md"
    instructions.write_text(
        instructions.read_text(encoding="utf-8").replace(
            "<!-- enterprise-edition:end -->",
            "",
        ),
        encoding="utf-8",
    )

    report = check_source_recipe_authoring(recipe)

    assert ("instructions.section", instructions) in {
        (error.code, error.path) for error in report.errors
    }
    assert any("enterprise-edition" in error.message for error in report.errors)


def test_source_authoring_check_validates_adversarial_eval_cases(tmp_path):
    recipe = _copy_agent_source(tmp_path, "sca-remediation")
    cases_path = recipe.parent / "evals" / "cases.yaml"
    data = yaml.safe_load(cases_path.read_text(encoding="utf-8"))
    for case in data["cases"]:
        if case.get("adversarial"):
            case["expected"].pop("must_not", None)
            break
    cases_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    report = check_source_recipe_authoring(recipe)

    assert "evals.adversarial" in {error.code for error in report.errors}
