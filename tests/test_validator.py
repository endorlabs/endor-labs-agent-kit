from __future__ import annotations

from copy import deepcopy

from endor_agent_kit.recipe import load_yaml_file
from endor_agent_kit.validator import validate_recipe_data, validate_recipe_file

from conftest import recipe_path, repo_root


def _data():
    return load_yaml_file(recipe_path())


def _errors(data):
    return validate_recipe_data(data, recipe_path=recipe_path())


def test_canonical_recipe_validates():
    assert validate_recipe_file(recipe_path()) == []


def test_all_agent_recipes_validate():
    recipe_paths = sorted((repo_root() / "agents").glob("*/recipe.yaml"))

    assert recipe_paths
    for path in recipe_paths:
        assert validate_recipe_file(path) == []


def test_rejects_bad_schema_version():
    data = _data()
    data["recipe_schema_version"] = 2

    assert any("recipe_schema_version" in error for error in _errors(data))


def test_rejects_bad_slug():
    data = _data()
    data["id"] = "Dependency Decision"

    assert any("id:" in error for error in _errors(data))


def test_rejects_mutating_safety_in_v0():
    data = _data()
    data["safety_class"] = "mutating"

    assert any("read_only" in error for error in _errors(data))


def test_rejects_non_empty_mutations_in_v0():
    data = _data()
    data["mutations"] = ["open_pr"]

    assert any("mutations" in error for error in _errors(data))


def test_rejects_unknown_mcp_tool():
    data = _data()
    data["required_endor_mcp_tools"] = ["not_a_real_tool"]

    assert any("unknown public Endor MCP tool" in error for error in _errors(data))


def test_rejects_forbidden_topology_fields():
    data = _data()
    data["nodes"] = []

    assert any("graph topology" in error for error in _errors(data))


def test_rejects_bad_host_edition_override():
    data = _data()
    data["host_editions"] = {"github-copilot-plugin": ["preview-edition"]}

    assert any("unsupported edition" in error for error in _errors(data))


def test_endorctl_transport_requires_run_commands():
    data = deepcopy(_data())
    data["host_capabilities_required"]["run_commands"] = False

    assert any("run_commands" in error for error in _errors(data))


def test_rejects_missing_instructions_file():
    data = _data()
    data["instructions_path"] = "missing.md"

    assert any("instructions_path" in error for error in _errors(data))
