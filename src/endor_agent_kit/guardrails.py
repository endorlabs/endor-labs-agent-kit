"""Guardrail conformance checks for generated Agent Kit catalogs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from endor_agent_kit.portable_runtime_conformance import (
    UNTRUSTED_CONTENT_BOUNDARY_PREFIX,
    assert_portable_text,
    portable_manifest_conformance_errors,
)
from endor_agent_kit.recipe import load_recipe, load_yaml_file
from endor_agent_kit.safety_posture import (
    SourceRecipeSafetyPosture,
    source_recipe_safety_posture,
)
from endor_agent_kit.validator import validate_recipe_file

CLAUDE_CODE_ALWAYS_DENIED = frozenset(
    {
        "Task",
        "Agent",
        "NotebookRead",
        "NotebookEdit",
        "WebFetch",
        "WebSearch",
        "TodoWrite",
    }
)

CLAUDE_CODE_READ_TOOLS = frozenset({"Read", "Glob", "Grep", "LS"})

CLAUDE_CODE_WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit"})

PORTABLE_FAIL_CLOSED_README_GUIDANCE = "Fail closed to plan-only output or `data_gaps`"

MANAGED_ALLOWED_HOSTS = frozenset(
    {
        "https://api.endorlabs.com",
        "https://api.github.com",
        "https://github.com",
    }
)


def check_catalog_guardrails(catalog_root: str | Path = ".") -> list[str]:
    """Return guardrail conformance errors for a generated catalog root."""

    root = Path(catalog_root)
    errors: list[str] = []

    _check_manifest(root, errors)
    _check_docs(root, errors)
    _check_source_recipes(root, errors)
    _check_claude_code(root, errors)
    _check_managed_agents(root, errors)
    _check_codex(root, errors)
    _check_portable(root, errors)
    return errors


def _check_manifest(root: Path, errors: list[str]) -> None:
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        errors.append(f"{_rel(root, manifest_path)}: missing catalog manifest")
        return
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{_rel(root, manifest_path)}: invalid JSON: {exc}")
        return
    agents = data.get("agents")
    if not isinstance(agents, list) or not agents:
        errors.append(f"{_rel(root, manifest_path)}: agents must be a non-empty list")


def _check_docs(root: Path, errors: list[str]) -> None:
    if not (root / "source" / "agents").is_dir() and not (root / "docs").exists():
        return
    expected = {
        "docs/guardrails.md": (
            "Agent Kit is an artifact and workflow-contract system",
            "Runtime audit and authorization | Delegated",
            "Untrusted Content Boundary",
            "Remaining Gaps",
        ),
        "docs/portable-runtime-conformance.md": (
            "Required Runtime Controls",
            "Adapter Response Contract",
            "fail closed",
        ),
    }
    for relative, required_text in expected.items():
        path = root / relative
        if not path.is_file():
            errors.append(f"{relative}: missing guardrail documentation")
            continue
        content = path.read_text(encoding="utf-8")
        for text in required_text:
            if text not in content:
                errors.append(f"{relative}: missing required guardrail text {text!r}")


def _check_source_recipes(root: Path, errors: list[str]) -> None:
    recipe_root = root / "source" / "agents"
    if not recipe_root.is_dir():
        return
    for recipe_file in sorted(recipe_root.glob("*/recipe.yaml")):
        for error in validate_recipe_file(recipe_file):
            errors.append(f"{_rel(root, recipe_file)}: {error}")
        try:
            recipe = load_yaml_file(recipe_file)
        except Exception as exc:
            errors.append(f"{_rel(root, recipe_file)}: failed to read YAML: {exc}")
            continue
        if recipe.get("safety_class") != "mutating":
            if recipe.get("mutations") not in (None, []):
                errors.append(f"{_rel(root, recipe_file)}: read-only recipe declares mutations")
            continue
        actions = _load_recipe_actions(root, recipe_file, recipe, errors)
        mutating_actions = [
            action
            for action in actions
            if isinstance(action, dict) and action.get("safety_class") == "mutating"
        ]
        if not mutating_actions:
            errors.append(f"{_rel(root, recipe_file)}: mutating recipe has no mutating actions")
        for action in mutating_actions:
            if action.get("confirmation_required") is not True:
                errors.append(
                    f"{_rel(root, recipe_file)}: mutating action "
                    f"{action.get('id', '<unknown>')!r} must require confirmation"
                )
        if recipe.get("id") in {"sca-remediation", "ai-sast-triage"}:
            if not any(action.get("kind") == "ticket.create" for action in mutating_actions):
                errors.append(f"{_rel(root, recipe_file)}: remediation recipe must declare ticket.create")


def _load_recipe_actions(
    root: Path,
    recipe_file: Path,
    recipe: dict[str, Any],
    errors: list[str],
) -> list[dict[str, Any]]:
    action_path = recipe.get("action_contracts_path")
    if not action_path:
        return []
    actions_file = recipe_file.parent / str(action_path)
    if not actions_file.is_file():
        errors.append(f"{_rel(root, actions_file)}: missing action contracts")
        return []
    try:
        data = load_yaml_file(actions_file)
    except Exception as exc:
        errors.append(f"{_rel(root, actions_file)}: failed to read YAML: {exc}")
        return []
    actions = data.get("actions")
    if not isinstance(actions, list):
        errors.append(f"{_rel(root, actions_file)}: actions must be a list")
        return []
    return [action for action in actions if isinstance(action, dict)]


def _check_claude_code(root: Path, errors: list[str]) -> None:
    host_root = root / "claude-code"
    if not host_root.is_dir():
        return
    for agent_dir in sorted(item for item in host_root.iterdir() if item.is_dir()):
        prompt = agent_dir / f"{agent_dir.name}.md"
        if not prompt.is_file():
            errors.append(f"{_rel(root, prompt)}: missing Claude Code prompt")
            continue
        content = prompt.read_text(encoding="utf-8")
        disallowed = _claude_code_disallowed_tools(content)
        if disallowed is None:
            errors.append(f"{_rel(root, prompt)}: missing disallowedTools frontmatter")
        else:
            expected_denied = _claude_code_expected_denied(_recipe_posture(root, agent_dir.name))
            if not expected_denied <= disallowed:
                missing = sorted(expected_denied - disallowed)
                errors.append(f"{_rel(root, prompt)}: disallowedTools missing {missing}")
        if UNTRUSTED_CONTENT_BOUNDARY_PREFIX not in content:
            errors.append(f"{_rel(root, prompt)}: missing untrusted-content boundary")


def _claude_code_expected_denied(posture: SourceRecipeSafetyPosture | None) -> set[str]:
    """Return the tools a Claude Code artifact must deny given recipe posture."""

    expected = set(CLAUDE_CODE_ALWAYS_DENIED)
    if posture is None:
        return expected
    if not posture.can_run_commands:
        expected.add("Bash")
    if not posture.can_read_files:
        expected |= CLAUDE_CODE_READ_TOOLS
    if not posture.can_write_files:
        expected |= CLAUDE_CODE_WRITE_TOOLS
    return expected


def _check_managed_agents(root: Path, errors: list[str]) -> None:
    host_root = root / "claude-managed-agents"
    if not host_root.is_dir():
        return
    for agent_dir in sorted(item for item in host_root.iterdir() if item.is_dir()):
        agent_file = agent_dir / "agent.yaml"
        environment_file = agent_dir / "environment.yaml"
        agent = _load_yaml_mapping(root, agent_file, errors)
        environment = _load_yaml_mapping(root, environment_file, errors)
        if not agent or not environment:
            continue
        if UNTRUSTED_CONTENT_BOUNDARY_PREFIX not in str(agent.get("system", "")):
            errors.append(f"{_rel(root, agent_file)}: missing untrusted-content boundary")
        for index, tool in enumerate(_list(agent.get("tools"))):
            policy = _dict(_dict(tool).get("default_config")).get("permission_policy", {})
            if _dict(policy).get("type") != "always_ask":
                errors.append(f"{_rel(root, agent_file)}: tools[{index}] must use always_ask")
            for config_index, config in enumerate(_list(_dict(tool).get("configs"))):
                config_policy = _dict(config).get("permission_policy", {})
                if _dict(config_policy).get("type") != "always_ask":
                    errors.append(
                        f"{_rel(root, agent_file)}: tools[{index}].configs[{config_index}] "
                        "must use always_ask"
                    )
        config = _dict(environment.get("config"))
        networking = _dict(config.get("networking"))
        if networking.get("type") != "limited":
            errors.append(f"{_rel(root, environment_file)}: networking.type must be limited")
        allowed_hosts = set(_list(networking.get("allowed_hosts")))
        if not allowed_hosts <= MANAGED_ALLOWED_HOSTS:
            errors.append(f"{_rel(root, environment_file)}: unexpected allowed_hosts {sorted(allowed_hosts)}")
        packages = _dict(config.get("packages"))
        if packages:
            if packages != {"npm": ["endorctl"]}:
                errors.append(f"{_rel(root, environment_file)}: packages must only install endorctl")
            if networking.get("allow_package_managers") is not True:
                errors.append(
                    f"{_rel(root, environment_file)}: allow_package_managers must be true when packages are installed"
                )
        elif networking.get("allow_package_managers") is not False:
            errors.append(f"{_rel(root, environment_file)}: allow_package_managers must be false")


def _check_codex(root: Path, errors: list[str]) -> None:
    host_root = root / "codex"
    if not host_root.is_dir():
        return
    for agent_dir in sorted(item for item in host_root.iterdir() if item.is_dir()):
        skill = agent_dir / "SKILL.md"
        if not skill.is_file():
            errors.append(f"{_rel(root, skill)}: missing Codex skill")
            continue
        content = skill.read_text(encoding="utf-8")
        for required in (
            "## Codex Host Contract",
            "unless Codex performed it and captured evidence",
            "data_gaps",
            UNTRUSTED_CONTENT_BOUNDARY_PREFIX,
        ):
            if required not in content:
                errors.append(f"{_rel(root, skill)}: missing required guardrail text {required!r}")
        posture = _recipe_posture(root, agent_dir.name)
        if posture is not None:
            posture_text = (
                "separate approval gates"
                if posture.is_mutating
                else "Keep the workflow read-only"
            )
            if posture_text not in content:
                errors.append(
                    f"{_rel(root, skill)}: missing required guardrail text {posture_text!r}"
                )


def _check_portable(root: Path, errors: list[str]) -> None:
    host_root = root / "portable"
    if not host_root.is_dir():
        return
    for bundle in sorted(item for item in host_root.iterdir() if item.is_dir()):
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
            content = path.read_text(encoding="utf-8")
            try:
                assert_portable_text(path.name, content)
            except ValueError as exc:
                errors.append(str(exc))
        agent = bundle / "agent.md"
        if not agent.is_file():
            errors.append(f"{_rel(root, agent)}: missing portable agent instructions")
            continue
        agent_text = agent.read_text(encoding="utf-8")
        for required in (
            "## Portable Runtime Contract",
            "runtime adapter performed it and returned evidence",
            UNTRUSTED_CONTENT_BOUNDARY_PREFIX,
        ):
            if required not in agent_text:
                errors.append(f"{_rel(root, agent)}: missing required guardrail text {required!r}")

        manifest_path = bundle / "agent.manifest.json"
        manifest = _load_json_mapping(root, manifest_path, errors)
        if manifest:
            _check_portable_manifest(root, manifest_path, manifest, errors)

        output_contract = bundle / "output-contract.md"
        if not output_contract.is_file():
            errors.append(f"{_rel(root, output_contract)}: missing output contract")
        elif "## Runtime Control Requirements" not in output_contract.read_text(encoding="utf-8"):
            errors.append(f"{_rel(root, output_contract)}: missing runtime control requirements")

        readme = bundle / "README.md"
        if readme.is_file():
            readme_text = readme.read_text(encoding="utf-8")
            if "docs/portable-runtime-conformance.md" not in readme_text:
                errors.append(f"{_rel(root, readme)}: missing portable conformance doc link")
            if PORTABLE_FAIL_CLOSED_README_GUIDANCE not in readme_text:
                errors.append(f"{_rel(root, readme)}: missing fail-closed README guidance")


def _check_portable_manifest(
    root: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    errors: list[str],
) -> None:
    for error in portable_manifest_conformance_errors(manifest):
        errors.append(f"{_rel(root, manifest_path)}: {error}")


def _recipe_posture(root: Path, agent_id: str) -> SourceRecipeSafetyPosture | None:
    """Return the Source Recipe Safety Posture for an agent, if source is present.

    Posture-derived host checks are best-effort: a catalog shipped without its
    ``source/agents`` tree still validates the host-independent guardrails, but a
    full catalog (as in CI) gets the same posture enforcement as the test suite.
    """

    recipe_file = root / "source" / "agents" / agent_id / "recipe.yaml"
    if not recipe_file.is_file():
        return None
    if validate_recipe_file(recipe_file):
        return None
    try:
        recipe = load_recipe(recipe_file)
    except Exception:
        return None
    return source_recipe_safety_posture(recipe)


def _claude_code_disallowed_tools(content: str) -> set[str] | None:
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None
    for line in parts[1].splitlines():
        if line.startswith("disallowedTools:"):
            values = line.split(":", 1)[1].strip()
            return {item.strip() for item in values.split(",") if item.strip()}
    return None


def _load_yaml_mapping(root: Path, path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.is_file():
        errors.append(f"{_rel(root, path)}: missing YAML file")
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        errors.append(f"{_rel(root, path)}: invalid YAML: {exc}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"{_rel(root, path)}: YAML must be a mapping")
        return {}
    return data


def _load_json_mapping(root: Path, path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.is_file():
        errors.append(f"{_rel(root, path)}: missing JSON file")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{_rel(root, path)}: invalid JSON: {exc}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"{_rel(root, path)}: JSON must be an object")
        return {}
    return data


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
