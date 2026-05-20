from __future__ import annotations

from copy import deepcopy
import shutil

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
    recipe_paths = sorted((repo_root() / "source" / "agents").glob("*/recipe.yaml"))

    assert recipe_paths
    for path in recipe_paths:
        assert validate_recipe_file(path) == []


def test_rejects_bad_schema_version():
    data = _data()
    data["recipe_schema_version"] = 3

    assert any("recipe_schema_version" in error for error in _errors(data))


def test_schema_v2_mutating_recipe_requires_actions(tmp_path):
    recipe_file = _copy_recipe_fixture(tmp_path)
    data = load_yaml_file(recipe_file)
    data["recipe_schema_version"] = 2
    data["safety_class"] = "mutating"
    data["mutations"] = ["open_pr"]
    data["host_capabilities_required"]["write_files"] = True
    data["host_capabilities_required"]["open_pr"] = True

    errors = validate_recipe_data(data, recipe_path=recipe_file)

    assert any("action_contracts_path" in error for error in errors)


def test_schema_v2_accepts_valid_mutating_actions(tmp_path):
    recipe_file = _copy_recipe_fixture(tmp_path)
    (recipe_file.parent / "actions.yaml").write_text(
        """
actions:
  - id: open-change-request
    kind: scm.change_request
    safety_class: mutating
    confirmation_required: true
    providers: ["github"]
    required_host_capabilities: ["run_commands", "write_files", "open_pr"]
    inputs: ["patch_diff"]
    outputs: ["url"]
  - id: verify-appsec-approval
    kind: approval.verify
    safety_class: read_only
    confirmation_required: false
    providers: ["github"]
    required_host_capabilities: ["run_commands"]
    inputs: ["pr_url"]
    outputs: ["approval_evidence_url"]
""",
        encoding="utf-8",
    )
    data = load_yaml_file(recipe_file)
    data["recipe_schema_version"] = 2
    data["safety_class"] = "mutating"
    data["mutations"] = ["write_files", "open_pr"]
    data["action_contracts_path"] = "actions.yaml"
    data["host_capabilities_required"]["write_files"] = True
    data["host_capabilities_required"]["open_pr"] = True

    assert validate_recipe_data(data, recipe_path=recipe_file) == []


def test_schema_v2_rejects_mutating_action_without_confirmation(tmp_path):
    recipe_file = _copy_recipe_fixture(tmp_path)
    (recipe_file.parent / "actions.yaml").write_text(
        """
actions:
  - id: open-change-request
    kind: scm.change_request
    safety_class: mutating
    confirmation_required: false
    required_host_capabilities: ["run_commands", "write_files", "open_pr"]
""",
        encoding="utf-8",
    )
    data = load_yaml_file(recipe_file)
    data["recipe_schema_version"] = 2
    data["safety_class"] = "mutating"
    data["mutations"] = ["write_files", "open_pr"]
    data["action_contracts_path"] = "actions.yaml"
    data["host_capabilities_required"]["write_files"] = True
    data["host_capabilities_required"]["open_pr"] = True

    assert any("confirmation_required" in error for error in validate_recipe_data(data, recipe_path=recipe_file))


def test_rejects_bad_slug():
    data = _data()
    data["id"] = "Dependency Decision"

    assert any("id:" in error for error in _errors(data))


def test_accepts_mutating_recipe_with_matching_host_capabilities():
    data = _data()
    data["safety_class"] = "mutating"
    data["mutations"] = ["write_files", "open_pr"]
    data["host_capabilities_required"]["run_commands"] = True
    data["host_capabilities_required"]["read_files"] = True
    data["host_capabilities_required"]["write_files"] = True
    data["host_capabilities_required"]["open_pr"] = True

    assert _errors(data) == []


def test_rejects_non_empty_mutations_for_read_only_recipe():
    data = _data()
    data["mutations"] = ["open_pr"]

    assert any("read_only recipes" in error for error in _errors(data))


def test_rejects_mutating_recipe_without_matching_host_capabilities():
    data = _data()
    data["safety_class"] = "mutating"
    data["mutations"] = ["open_pr"]

    assert any("open_pr" in error for error in _errors(data))


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
    data["host_editions"] = {"claude-code": ["preview-edition"]}

    assert any("unsupported edition" in error for error in _errors(data))


def test_endorctl_transport_requires_run_commands():
    data = deepcopy(_data())
    data["host_capabilities_required"]["run_commands"] = False

    assert any("run_commands" in error for error in _errors(data))


def test_rejects_missing_instructions_file():
    data = _data()
    data["instructions_path"] = "missing.md"

    assert any("instructions_path" in error for error in _errors(data))


def _copy_recipe_fixture(tmp_path):
    src = recipe_path().parent
    dst = tmp_path / "dependency-decision-helper"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("dist"))
    return dst / "recipe.yaml"
