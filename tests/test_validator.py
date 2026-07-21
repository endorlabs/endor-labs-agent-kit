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


def test_accepts_agent_attributed_endor_api_transport():
    data = _data()
    data["supported_transports"] = ["mcp", "endorctl_agent_api"]
    data["endorctl_api_invocations"] = []
    data["endorctl_agent_api_invocations"] = ["lookup_package_version_uuid"]

    assert _errors(data) == []


def test_agent_attributed_endor_api_transport_requires_invocations():
    data = _data()
    data["supported_transports"] = ["mcp", "endorctl_agent_api"]
    data["endorctl_api_invocations"] = []
    data["endorctl_agent_api_invocations"] = []

    assert any("endorctl_agent_api_invocations" in error for error in _errors(data))


def test_rejects_missing_instructions_file():
    data = _data()
    data["instructions_path"] = "missing.md"

    assert any("instructions_path" in error for error in _errors(data))


def test_rejects_missing_audience():
    data = _data()
    data.pop("audience", None)

    assert any("audience:" in error for error in _errors(data))


def test_rejects_invalid_audience():
    data = _data()
    data["audience"] = "platform"

    assert any("audience:" in error for error in _errors(data))


def test_accepts_both_audiences():
    data = _data()
    for audience in ("appsec", "developer"):
        data["audience"] = audience
        assert not [error for error in _errors(data) if "audience:" in error]


def test_rejects_missing_short_description():
    data = _data()
    data.pop("short_description", None)

    assert any("short_description:" in error for error in _errors(data))


def test_rejects_blank_short_description():
    data = _data()
    data["short_description"] = "   "

    assert any("short_description:" in error for error in _errors(data))


def test_rejects_missing_authors():
    data = _data()
    data.pop("authors", None)

    assert any("authors:" in error for error in _errors(data))


def test_rejects_empty_authors_list():
    data = _data()
    data["authors"] = []

    assert any("authors:" in error for error in _errors(data))


def test_rejects_author_email():
    data = _data()
    data["authors"] = ["contributor@example.com"]

    assert any("PII" in error for error in _errors(data))


def test_rejects_author_handle():
    data = _data()
    data["authors"] = ["@some-handle"]

    assert any("PII" in error for error in _errors(data))


def test_rejects_author_url():
    data = _data()
    data["authors"] = ["https://example.com/me"]

    assert any("PII" in error for error in _errors(data))


def test_accepts_display_name_authors():
    data = _data()
    data["authors"] = ["Endor Labs", "Matt Brown"]

    assert not [error for error in _errors(data) if "authors:" in error]


def test_rejects_missing_requires_endorctl():
    data = _data()
    data.pop("requires_endorctl", None)

    assert any("requires_endorctl:" in error for error in _errors(data))


def test_rejects_requires_endorctl_without_operator():
    data = _data()
    data["requires_endorctl"] = "1.0.0"

    assert any("requires_endorctl:" in error for error in _errors(data))


def test_rejects_requires_endorctl_partial_semver():
    data = _data()
    data["requires_endorctl"] = ">=1.0"

    assert any("requires_endorctl:" in error for error in _errors(data))


def test_accepts_requires_endorctl_constraints():
    data = _data()
    for value in (">=1.0.0", ">1.2.3", ">=1.32.0", ">=2.0.0-rc.1"):
        data["requires_endorctl"] = value
        assert not [error for error in _errors(data) if "requires_endorctl:" in error]


def _copy_recipe_fixture(tmp_path):
    src = recipe_path().parent
    dst = tmp_path / "dependency-decision-helper"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("dist"))
    return dst / "recipe.yaml"
