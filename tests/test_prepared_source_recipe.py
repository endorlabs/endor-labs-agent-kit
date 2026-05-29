from __future__ import annotations

from endor_agent_kit.prepared_source_recipe import prepare_source_recipe

from conftest import repo_root


def test_prepare_source_recipe_loads_validated_recipe_render_inputs():
    recipe_file = repo_root() / "source" / "agents" / "sca-remediation" / "recipe.yaml"

    prepared = prepare_source_recipe(recipe_file)

    assert prepared.path == recipe_file
    assert prepared.recipe.id == "sca-remediation"
    assert "# SCA Remediation" in prepared.instructions
    assert [action.id for action in prepared.actions] == [
        "resolve-endor-project",
        "query-sca-findings",
        "query-uia-evidence",
        "list-low-risk-uia-prs",
        "read-local-manifests",
        "resolve-upgrade-risk",
        "prepare-remediation-diff",
        "open-change-request",
        "post-remediation-comment",
        "create-remediation-ticket",
    ]
    assert prepared.action_contracts_path == recipe_file.parent / "actions.yaml"
    assert prepared.architecture_path == recipe_file.parent / "architecture.svg"


def test_prepare_source_recipe_uses_absent_action_path_for_recipes_without_actions():
    recipe_file = repo_root() / "source" / "agents" / "vulnerability-explainer" / "recipe.yaml"

    prepared = prepare_source_recipe(recipe_file)

    assert prepared.actions == ()
    assert prepared.action_contracts_path.name == "__no_actions_yaml__"
