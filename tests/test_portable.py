from __future__ import annotations

import json
import shutil
from pathlib import Path

from endor_agent_kit.cli import main
from endor_agent_kit.compilers.portable import compile_portable
from endor_agent_kit.portable_runtime_conformance import assert_portable_text
from endor_agent_kit.publisher import publish_recipes
from endor_agent_kit.recipe import load_recipe
from endor_agent_kit.safety_posture import source_recipe_safety_posture

from conftest import repo_root


def test_portable_compiler_emits_runtime_neutral_bundle(tmp_path):
    recipe = _copy_agent(tmp_path, "sca-remediation")

    outputs = compile_portable(recipe)

    assert [path.name for path in outputs] == [
        "agent.md",
        "agent.manifest.json",
        "output-contract.md",
    ]
    out_dir = recipe.parent / "dist" / "portable" / "sca-remediation"
    agent = (out_dir / "agent.md").read_text(encoding="utf-8")
    manifest = json.loads((out_dir / "agent.manifest.json").read_text(encoding="utf-8"))
    contract = (out_dir / "output-contract.md").read_text(encoding="utf-8")

    assert "## Portable Runtime Contract" in agent
    assert "runtime adapter performed it and returned evidence" in agent
    assert "Present workflow target choices at the mutation gate" in agent
    assert "## Action Contracts" in agent
    assert manifest["portable_schema_version"] == 1
    assert manifest["id"] == "sca-remediation"
    assert "source.change_request.create" in manifest["required_capabilities"]
    assert "ticket.create" in manifest["required_capabilities"]
    assert manifest["degradation"]["supports_plan_only"] is True
    ticket = _vocabulary_item(manifest, "ticket.create")
    assert ticket["status"] == "declared"
    assert ticket["confirmation_required"] is True
    assert "source-provider-adapter" in json.dumps(manifest)
    assert "gh-cli" not in json.dumps(manifest)
    assert "selection-plan" in contract
    assert "endor-agent-kit validate-sca-output" in contract
    _assert_portable_text_files(out_dir)


def test_portable_cli_compile_target(tmp_path, capsys):
    recipe = _copy_agent(tmp_path, "vulnerability-explainer")

    status = main(["compile", str(recipe), "--target", "portable"])
    output = capsys.readouterr().out

    assert status == 0
    assert "portable/vulnerability-explainer/agent.md" in output
    assert "agent.manifest.json" in output


def test_publish_recipes_writes_portable_bundles_for_all_current_agents(tmp_path):
    source_recipes = sorted((repo_root() / "source" / "agents").glob("*/recipe.yaml"))
    dest = tmp_path / "endor-labs-agent-kit"

    publish_recipes(source_recipes, dest, prune=True)

    manifest = json.loads((dest / "manifest.json").read_text(encoding="utf-8"))
    portable_agents = [
        agent
        for agent in manifest["agents"]
        if agent["host"] == "portable"
    ]
    assert {agent["id"] for agent in portable_agents} == {
        path.parent.name for path in source_recipes
    }
    assert "Portable" in (dest / "README.md").read_text(encoding="utf-8")
    assert "Already Have Your Own Tech Stack Or Workflows Wired?" in (
        dest / "README.md"
    ).read_text(encoding="utf-8")

    for recipe_path in source_recipes:
        recipe = load_recipe(recipe_path)
        bundle = dest / "portable" / recipe.id
        expected = {"README.md", "agent.md", "agent.manifest.json", "output-contract.md"}
        if recipe.action_contracts_path:
            expected.add("actions.yaml")
        if (recipe_path.parent / "architecture.svg").is_file():
            expected.add("architecture.svg")
        if source_recipe_safety_posture(recipe).requires_endorctl_setup:
            expected.add("endorctl-setup.md")
        assert {path.name for path in bundle.iterdir() if path.is_file()} == expected
        _assert_portable_text_files(bundle)


def test_portable_manifest_distinguishes_declared_actions_and_wrappers(tmp_path):
    recipe = _copy_agent(tmp_path, "ai-sast-triage")
    compile_portable(recipe)
    manifest = json.loads(
        (
            recipe.parent
            / "dist"
            / "portable"
            / "ai-sast-triage"
            / "agent.manifest.json"
        ).read_text(encoding="utf-8")
    )

    declared = {action["portable_kind"] for action in manifest["declared_actions"]}
    assert "source.change_request.create" in declared
    assert "endor.policy.write" in declared
    assert "ticket.create" in declared
    assert _vocabulary_item(manifest, "ticket.create")["status"] == "declared"
    assert manifest["runtime_wrappers"] == []


def test_portable_manifest_keeps_ticket_wrapper_for_non_declared_ticket_agents(tmp_path):
    recipe = _copy_agent(tmp_path, "vulnerability-explainer")
    compile_portable(recipe)
    manifest = json.loads(
        (
            recipe.parent
            / "dist"
            / "portable"
            / "vulnerability-explainer"
            / "agent.manifest.json"
        ).read_text(encoding="utf-8")
    )

    declared = {action["portable_kind"] for action in manifest["declared_actions"]}
    assert "ticket.create" not in declared
    assert _vocabulary_item(manifest, "ticket.create")["status"] == "wrapper_available"
    assert manifest["runtime_wrappers"][0]["kind"] == "ticket.create"
    assert manifest["runtime_wrappers"][0]["declared_by_recipe"] is False


def _copy_agent(tmp_path: Path, agent_id: str) -> Path:
    src = repo_root() / "source" / "agents" / agent_id
    dst = tmp_path / agent_id
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("dist"))
    return dst / "recipe.yaml"


def _vocabulary_item(manifest: dict, kind: str) -> dict:
    return next(
        item
        for item in manifest["runtime_action_vocabulary"]
        if item["kind"] == kind
    )


def _assert_portable_text_files(bundle: Path) -> None:
    for filename in (
        "agent.md",
        "agent.manifest.json",
        "output-contract.md",
        "README.md",
        "actions.yaml",
        "architecture.svg",
        "endorctl-setup.md",
    ):
        path = bundle / filename
        if not path.exists():
            continue
        assert_portable_text(path.name, path.read_text(encoding="utf-8"))
