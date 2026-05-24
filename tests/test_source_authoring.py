from __future__ import annotations

import shutil
from pathlib import Path

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


def test_source_authoring_check_accepts_strict_new_mutating_agent(tmp_path, capsys):
    recipe = _copy_agent_source(tmp_path, "sca-remediation")

    report = check_source_recipe_authoring(recipe, new_agent=True)
    status = main(["authoring-check", str(recipe), "--new-agent"])
    output = capsys.readouterr().out

    assert report.ok
    assert report.agent_id == "sca-remediation"
    assert status == 0
    assert f"OK: {recipe}" in output


def test_source_authoring_check_requires_new_agent_architecture(tmp_path):
    recipe = _copy_agent_source(tmp_path, "dependency-decision-helper")

    report = check_source_recipe_authoring(recipe, new_agent=True)

    assert "architecture.required" in {error.code for error in report.errors}


def test_source_authoring_check_requires_new_agent_eval_coverage(tmp_path):
    recipe = _copy_agent_source(tmp_path, "remediation-planner")

    report = check_source_recipe_authoring(recipe, new_agent=True)

    assert "evals.minimum_cases" in {error.code for error in report.errors}


def test_source_authoring_check_uses_shared_instruction_section_parser(tmp_path):
    recipe = _copy_agent_source(tmp_path, "dependency-decision-helper")
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
