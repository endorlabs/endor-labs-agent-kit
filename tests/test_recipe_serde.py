from __future__ import annotations

from endor_agent_kit.recipe import load_recipe, read_instructions, recipe_from_dict, recipe_to_dict

from conftest import recipe_path


def test_recipe_yaml_round_trips_core_fields():
    recipe = load_recipe(recipe_path())

    assert recipe.id == "dependency-decision-helper"
    assert recipe.recipe_schema_version == 1
    assert recipe.safety_class == "read_only"
    assert recipe.supported_transports == ("mcp", "endorctl_api")
    assert recipe.host_capabilities_required.run_commands is True
    assert recipe.compatible_hosts == ("claude-code", "claude-managed-agents", "codex", "gemini", "portable")
    assert recipe.host_editions == {
        "claude-code": ("enterprise-edition",),
        "claude-managed-agents": ("enterprise-edition",),
    }
    assert [field.name for field in recipe.inputs] == ["ecosystem", "package_name", "version"]
    assert "data_gaps" in [field.name for field in recipe.outputs]

    round_tripped = recipe_from_dict(recipe_to_dict(recipe))
    assert round_tripped == recipe


def test_recipe_reads_instructions_relative_to_recipe():
    recipe = load_recipe(recipe_path())
    body = read_instructions(recipe_path(), recipe)

    assert "Endor Labs Dependency Decision Helper" in body
    assert "<!-- shared:start -->" in body
    assert "<!-- enterprise-edition:start -->" in body


def test_recipe_parses_host_edition_overrides():
    data = recipe_to_dict(load_recipe(recipe_path()))
    data["compatible_hosts"] = ["claude-code"]
    data["host_editions"] = {"claude-code": ["enterprise-edition"]}

    recipe = recipe_from_dict(data)

    assert recipe.compatible_hosts == ("claude-code",)
    assert recipe.host_editions == {"claude-code": ("enterprise-edition",)}
