"""Guardrail conformance checks for generated Agent Kit catalogs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import zipfile

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
from endor_agent_kit.dlp_scan import scan_catalog_credential_findings
from endor_agent_kit.provenance import verify_catalog_provenance
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
    _check_gemini(root, errors)
    _check_plugins(root, errors)
    _check_portable(root, errors)
    _check_credentials(root, errors)
    _check_provenance(root, errors)
    return errors


def _check_credentials(root: Path, errors: list[str]) -> None:
    errors.extend(scan_catalog_credential_findings(root))


def _check_provenance(root: Path, errors: list[str]) -> None:
    if not (root / "manifest.json").is_file():
        return
    errors.extend(verify_catalog_provenance(root))


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
    plugin_packages = data.get("plugin_packages", [])
    if plugin_packages and not isinstance(plugin_packages, list):
        errors.append(f"{_rel(root, manifest_path)}: plugin_packages must be a list")


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


def _check_gemini(root: Path, errors: list[str]) -> None:
    host_root = root / "gemini"
    if not host_root.is_dir():
        return
    for agent_dir in sorted(item for item in host_root.iterdir() if item.is_dir()):
        skill = agent_dir / "SKILL.md"
        if not skill.is_file():
            errors.append(f"{_rel(root, skill)}: missing Gemini skill")
        else:
            skill_text = skill.read_text(encoding="utf-8")
            for required in (
                "## Gemini CLI Host Contract",
                "unless Gemini CLI performed it and captured evidence",
                "data_gaps",
                UNTRUSTED_CONTENT_BOUNDARY_PREFIX,
            ):
                if required not in skill_text:
                    errors.append(f"{_rel(root, skill)}: missing required guardrail text {required!r}")
        agent = agent_dir / f"{agent_dir.name}.md"
        if not agent.is_file():
            errors.append(f"{_rel(root, agent)}: missing Gemini subagent")
            continue
        agent_text = agent.read_text(encoding="utf-8")
        for required in (
            "endor_agent_kit_managed=true",
            "## Gemini CLI Host Contract",
            "data_gaps",
            UNTRUSTED_CONTENT_BOUNDARY_PREFIX,
        ):
            if required not in agent_text:
                errors.append(f"{_rel(root, agent)}: missing required guardrail text {required!r}")
        frontmatter = _frontmatter_mapping(root, agent, agent_text, errors)
        for forbidden in ("mcpServers", "hooks"):
            if forbidden in frontmatter:
                errors.append(f"{_rel(root, agent)}: Gemini subagent must not declare {forbidden}")


def _check_plugins(root: Path, errors: list[str]) -> None:
    plugins_root = root / "plugins"
    if not plugins_root.is_dir():
        return

    codex_package = plugins_root / "codex" / "endor-labs-agent-kit"
    if codex_package.is_dir():
        _check_codex_plugin_package(root, plugins_root, codex_package, errors)

    claude_package = plugins_root / "claude" / "endor-labs-agent-kit"
    if claude_package.is_dir():
        _check_claude_plugin_package(root, plugins_root, claude_package, errors)

    gemini_package = plugins_root / "gemini" / "endor-labs-agent-kit"
    if gemini_package.is_dir():
        _check_gemini_plugin_package(root, gemini_package, errors)

    antigravity_package = plugins_root / "antigravity" / "endor-labs-agent-kit"
    if antigravity_package.is_dir():
        _check_antigravity_plugin_package(root, antigravity_package, errors)


def _check_codex_plugin_package(
    root: Path,
    plugins_root: Path,
    codex_package: Path,
    errors: list[str],
) -> None:
    manifest = _load_json_mapping(
        root,
        codex_package / ".codex-plugin" / "plugin.json",
        errors,
    )
    if manifest:
        if manifest.get("name") != "endor-labs-agent-kit":
            errors.append("plugins/codex/endor-labs-agent-kit/.codex-plugin/plugin.json: name must be endor-labs-agent-kit")
        if "agents" in manifest:
            errors.append("plugins/codex/endor-labs-agent-kit/.codex-plugin/plugin.json: Codex plugin manifest must not declare unsupported agents field")
        if manifest.get("skills") != "./skills/":
            errors.append("plugins/codex/endor-labs-agent-kit/.codex-plugin/plugin.json: skills must point at ./skills/")
        interface = _dict(manifest.get("interface"))
        prompts = _list(interface.get("defaultPrompt"))
        if len(prompts) > 3:
            errors.append("plugins/codex/endor-labs-agent-kit/.codex-plugin/plugin.json: defaultPrompt must include at most 3 prompts")
        logo = interface.get("logo")
        if isinstance(logo, str) and logo:
            if not (codex_package / logo.removeprefix("./")).is_file():
                errors.append(f"plugins/codex/endor-labs-agent-kit/.codex-plugin/plugin.json: logo path {logo!r} is missing")

    marketplace = _load_json_mapping(
        root,
        plugins_root / "codex" / ".agents" / "plugins" / "marketplace.json",
        errors,
    )
    if marketplace:
        if marketplace.get("name") != "endor-labs-agent-kit":
            errors.append("plugins/codex/.agents/plugins/marketplace.json: name must be endor-labs-agent-kit")
        entries = _list(marketplace.get("plugins"))
        if not any(_dict(entry).get("name") == "endor-labs-agent-kit" for entry in entries):
            errors.append("plugins/codex/.agents/plugins/marketplace.json: missing endor-labs-agent-kit plugin entry")

    public_marketplace = _load_json_mapping(
        root,
        root / ".agents" / "plugins" / "marketplace.json",
        errors,
    )
    if public_marketplace:
        if public_marketplace.get("name") != "endor-labs-agent-kit":
            errors.append(".agents/plugins/marketplace.json: name must be endor-labs-agent-kit")
        entries = _list(public_marketplace.get("plugins"))
        entry = next(
            (
                _dict(item)
                for item in entries
                if _dict(item).get("name") == "endor-labs-agent-kit"
            ),
            {},
        )
        if not entry:
            errors.append(".agents/plugins/marketplace.json: missing endor-labs-agent-kit plugin entry")
        elif _dict(entry.get("source")).get("path") != "./plugins/codex/endor-labs-agent-kit":
            errors.append(".agents/plugins/marketplace.json: plugin source path must be './plugins/codex/endor-labs-agent-kit'")

    setup = codex_package / "skills" / "endor-agent-kit-setup" / "SKILL.md"
    if not setup.is_file():
        errors.append(f"{_rel(root, setup)}: missing Codex setup skill")
    else:
        setup_text = setup.read_text(encoding="utf-8")
        for required in (
            "must not:",
            "Run `endorctl scan`",
            "Run `endorctl host-check`",
            "Install Codex custom agents globally by default",
            "provenance-gated updates",
        ):
            if required not in setup_text:
                errors.append(f"{_rel(root, setup)}: missing required setup text {required!r}")

    installer = codex_package / "scripts" / "install_codex_agents.py"
    if not installer.is_file():
        errors.append(f"{_rel(root, installer)}: missing Codex custom-agent installer")

    for agent in sorted((codex_package / "agents").glob("*.toml")):
        text = agent.read_text(encoding="utf-8")
        for required in (
            "# endor_agent_kit_managed = true",
            "developer_instructions = ",
            "Codex Host Contract",
        ):
            if required not in text:
                errors.append(f"{_rel(root, agent)}: missing required custom-agent text {required!r}")
        if "_" in agent.stem:
            errors.append(f"{_rel(root, agent)}: Codex custom-agent names must use hyphens, not underscores")
        if not agent.stem.startswith("endor-") or not agent.stem.endswith("-agent"):
            errors.append(f"{_rel(root, agent)}: Codex custom-agent name must use endor-...-agent")

    forbidden_names = {"recipe.yaml", "cases.yaml"}
    for path in codex_package.rglob("*"):
        if path.is_file() and path.name in forbidden_names:
            errors.append(f"{_rel(root, path)}: source-only file leaked into plugin package")


def _check_claude_plugin_package(
    root: Path,
    plugins_root: Path,
    claude_package: Path,
    errors: list[str],
) -> None:
    manifest_path = claude_package / ".claude-plugin" / "plugin.json"
    manifest = _load_json_mapping(root, manifest_path, errors)
    if manifest:
        if manifest.get("name") != "endor-labs-agent-kit":
            errors.append("plugins/claude/endor-labs-agent-kit/.claude-plugin/plugin.json: name must be endor-labs-agent-kit")
        if "agents" in manifest:
            errors.append("plugins/claude/endor-labs-agent-kit/.claude-plugin/plugin.json: must not declare default agents path; Claude auto-discovers agents/")
        if "skills" in manifest:
            errors.append("plugins/claude/endor-labs-agent-kit/.claude-plugin/plugin.json: must not declare default skills path; Claude auto-discovers skills/")
        if "license" in manifest:
            errors.append("plugins/claude/endor-labs-agent-kit/.claude-plugin/plugin.json: license must be omitted until release metadata is final")
        if "mcpServers" in manifest:
            errors.append("plugins/claude/endor-labs-agent-kit/.claude-plugin/plugin.json: must not declare plugin-wide MCP")

    _check_claude_marketplace(
        root,
        root / ".claude-plugin" / "marketplace.json",
        "./plugins/claude/endor-labs-agent-kit",
        errors,
    )
    _check_claude_marketplace(
        root,
        plugins_root / "claude" / ".claude-plugin" / "marketplace.json",
        "./endor-labs-agent-kit",
        errors,
    )

    setup = claude_package / "skills" / "endor-agent-kit-setup" / "SKILL.md"
    if not setup.is_file():
        errors.append(f"{_rel(root, setup)}: missing Claude setup skill")
    else:
        setup_text = setup.read_text(encoding="utf-8")
        for required in (
            "must not:",
            "Run `endorctl scan`",
            "Run `endorctl host-check`",
            "Do not add plugin-wide MCP automatically",
            "plugin-shipped agents cannot declare `mcpServers`",
        ):
            if required not in setup_text:
                errors.append(f"{_rel(root, setup)}: missing required setup text {required!r}")

    for agent in sorted((claude_package / "agents").glob("*.md")):
        text = agent.read_text(encoding="utf-8")
        for required in (
            "endor_agent_kit_managed=true",
            "Claude Code Plugin Setup Note",
            "data_gaps",
        ):
            if required not in text:
                errors.append(f"{_rel(root, agent)}: missing required Claude plugin agent text {required!r}")
        frontmatter = _frontmatter_mapping(root, agent, text, errors)
        for forbidden in ("mcpServers", "permissionMode", "hooks"):
            if forbidden in frontmatter:
                errors.append(f"{_rel(root, agent)}: Claude plugin agent must not declare {forbidden}")
        disallowed = _claude_code_disallowed_tools(text)
        if disallowed is None:
            errors.append(f"{_rel(root, agent)}: missing disallowedTools frontmatter")
            continue
        posture = _recipe_posture(root, agent.stem)
        if posture is not None:
            expected_denied = _claude_code_expected_denied(posture)
            if not expected_denied <= disallowed:
                missing = sorted(expected_denied - disallowed)
                errors.append(f"{_rel(root, agent)}: disallowedTools missing {missing}")

    forbidden_names = {"recipe.yaml", "cases.yaml"}
    for path in claude_package.rglob("*"):
        if path.is_file() and path.name in forbidden_names:
            errors.append(f"{_rel(root, path)}: source-only file leaked into plugin package")


def _check_claude_marketplace(
    root: Path,
    path: Path,
    expected_source: str,
    errors: list[str],
) -> None:
    marketplace = _load_json_mapping(root, path, errors)
    if not marketplace:
        return
    if marketplace.get("name") != "endorlabs":
        errors.append(f"{_rel(root, path)}: name must be endorlabs")
    owner = _dict(marketplace.get("owner"))
    if owner.get("name") != "Endor Labs":
        errors.append(f"{_rel(root, path)}: owner.name must be Endor Labs")
    entries = _list(marketplace.get("plugins"))
    entry = next(
        (
            _dict(item)
            for item in entries
            if _dict(item).get("name") == "endor-labs-agent-kit"
        ),
        {},
    )
    if not entry:
        errors.append(f"{_rel(root, path)}: missing endor-labs-agent-kit plugin entry")
        return
    if entry.get("source") != expected_source:
        errors.append(f"{_rel(root, path)}: plugin source must be {expected_source!r}")
    source = entry.get("source")
    if not isinstance(source, str) or not source.startswith("./") or "/../" in source or source.startswith("../"):
        errors.append(f"{_rel(root, path)}: plugin source must be a marketplace-root relative path starting with ./")
    if entry.get("version") != "0.1.0":
        errors.append(f"{_rel(root, path)}: plugin entry version must match package version 0.1.0")
    expected_terms = {
        "agentic remediation",
        "SAST remediation",
        "agentic AppSec",
        "AppSec",
        "Upgrade Impact Analysis",
    }
    tags = set(str(item) for item in _list(entry.get("tags")))
    keywords = set(str(item) for item in _list(entry.get("keywords")))
    if not expected_terms <= tags:
        missing = sorted(expected_terms - tags)
        errors.append(f"{_rel(root, path)}: plugin entry tags missing discovery terms {missing}")
    if not expected_terms <= keywords:
        missing = sorted(expected_terms - keywords)
        errors.append(f"{_rel(root, path)}: plugin entry keywords missing discovery terms {missing}")


def _check_gemini_plugin_package(
    root: Path,
    gemini_package: Path,
    errors: list[str],
) -> None:
    manifest_path = gemini_package / "gemini-extension.json"
    manifest = _load_json_mapping(root, manifest_path, errors)
    if manifest:
        if manifest.get("name") != "endor-labs-agent-kit":
            errors.append("plugins/gemini/endor-labs-agent-kit/gemini-extension.json: name must be endor-labs-agent-kit")
        if manifest.get("contextFileName") != "GEMINI.md":
            errors.append("plugins/gemini/endor-labs-agent-kit/gemini-extension.json: contextFileName must be GEMINI.md")
        for forbidden in ("mcpServers", "settings", "license"):
            if forbidden in manifest:
                errors.append(f"plugins/gemini/endor-labs-agent-kit/gemini-extension.json: must not declare {forbidden}")

    setup = gemini_package / "skills" / "endor-agent-kit-setup" / "SKILL.md"
    if not setup.is_file():
        errors.append(f"{_rel(root, setup)}: missing Gemini setup skill")
    else:
        setup_text = setup.read_text(encoding="utf-8")
        for required in (
            "Run `endorctl scan`",
            "Run `endorctl host-check`",
            "folder trust prompt",
            "Do not add plugin-wide MCP automatically",
            "Gemini subagents are preview functionality",
        ):
            if required not in setup_text:
                errors.append(f"{_rel(root, setup)}: missing required setup text {required!r}")

    for skill in sorted((gemini_package / "skills").glob("*/SKILL.md")):
        if skill.parent.name == "endor-agent-kit-setup":
            continue
        text = skill.read_text(encoding="utf-8")
        for required in ("## Gemini CLI Host Contract", "data_gaps"):
            if required not in text:
                errors.append(f"{_rel(root, skill)}: missing required Gemini plugin skill text {required!r}")

    for agent in sorted((gemini_package / "agents").glob("*.md")):
        text = agent.read_text(encoding="utf-8")
        for required in (
            "endor_agent_kit_managed=true",
            "## Gemini CLI Host Contract",
            "data_gaps",
        ):
            if required not in text:
                errors.append(f"{_rel(root, agent)}: missing required Gemini plugin subagent text {required!r}")
        frontmatter = _frontmatter_mapping(root, agent, text, errors)
        if frontmatter.get("kind") != "local":
            errors.append(f"{_rel(root, agent)}: Gemini subagent kind must be local")
        for forbidden in ("mcpServers", "hooks"):
            if forbidden in frontmatter:
                errors.append(f"{_rel(root, agent)}: Gemini plugin subagent must not declare {forbidden}")

    forbidden_names = {"recipe.yaml", "cases.yaml"}
    for path in gemini_package.rglob("*"):
        if path.is_file() and path.name in forbidden_names:
            errors.append(f"{_rel(root, path)}: source-only file leaked into plugin package")

    archive_path = root / "plugins" / "gemini" / "endor-labs-agent-kit.zip"
    if not archive_path.is_file():
        errors.append(f"{_rel(root, archive_path)}: missing Gemini release archive")
        return
    try:
        with zipfile.ZipFile(archive_path) as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile as exc:
        errors.append(f"{_rel(root, archive_path)}: invalid zip archive: {exc}")
        return
    if "gemini-extension.json" not in names:
        errors.append(f"{_rel(root, archive_path)}: gemini-extension.json must be at archive root")
    if "skills/endor-agent-kit-setup/SKILL.md" not in names:
        errors.append(f"{_rel(root, archive_path)}: missing setup skill in release archive")
    if any(name.startswith("endor-labs-agent-kit/") for name in names):
        errors.append(f"{_rel(root, archive_path)}: archive must not include an extra endor-labs-agent-kit root directory")
    if any(Path(name).name in forbidden_names for name in names):
        errors.append(f"{_rel(root, archive_path)}: source-only file leaked into release archive")


def _check_antigravity_plugin_package(
    root: Path,
    antigravity_package: Path,
    errors: list[str],
) -> None:
    manifest_path = antigravity_package / "plugin.json"
    manifest = _load_json_mapping(root, manifest_path, errors)
    if manifest:
        if manifest.get("name") != "endor-labs-agent-kit":
            errors.append("plugins/antigravity/endor-labs-agent-kit/plugin.json: name must be endor-labs-agent-kit")
        for forbidden in ("mcpServers", "settings", "license", "hooks"):
            if forbidden in manifest:
                errors.append(f"plugins/antigravity/endor-labs-agent-kit/plugin.json: must not declare {forbidden}")

    setup = antigravity_package / "skills" / "endor-agent-kit-setup" / "SKILL.md"
    if not setup.is_file():
        errors.append(f"{_rel(root, setup)}: missing Antigravity setup skill")
    else:
        setup_text = setup.read_text(encoding="utf-8")
        for required in (
            "Run `endorctl scan`",
            "Run `endorctl host-check`",
            "antigravity plugin validate",
            "Do not add plugin-wide MCP automatically",
            "Antigravity subagents are host-managed",
        ):
            if required not in setup_text:
                errors.append(f"{_rel(root, setup)}: missing required setup text {required!r}")

    for skill in sorted((antigravity_package / "skills").glob("*/SKILL.md")):
        if skill.parent.name == "endor-agent-kit-setup":
            continue
        text = skill.read_text(encoding="utf-8")
        for required in ("## Antigravity CLI Host Contract", "data_gaps"):
            if required not in text:
                errors.append(f"{_rel(root, skill)}: missing required Antigravity plugin skill text {required!r}")

    for agent in sorted((antigravity_package / "agents").glob("*.md")):
        text = agent.read_text(encoding="utf-8")
        for required in (
            "endor_agent_kit_managed=true",
            "## Antigravity CLI Host Contract",
            "data_gaps",
        ):
            if required not in text:
                errors.append(f"{_rel(root, agent)}: missing required Antigravity plugin subagent text {required!r}")
        frontmatter = _frontmatter_mapping(root, agent, text, errors)
        if frontmatter.get("kind") != "local":
            errors.append(f"{_rel(root, agent)}: Antigravity subagent kind must be local")
        for forbidden in ("mcpServers", "hooks"):
            if forbidden in frontmatter:
                errors.append(f"{_rel(root, agent)}: Antigravity plugin subagent must not declare {forbidden}")

    forbidden_names = {"recipe.yaml", "cases.yaml"}
    for path in antigravity_package.rglob("*"):
        if path.is_file() and path.name in forbidden_names:
            errors.append(f"{_rel(root, path)}: source-only file leaked into plugin package")


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


def _frontmatter_mapping(
    root: Path,
    path: Path,
    content: str,
    errors: list[str],
) -> dict[str, Any]:
    parts = content.split("---", 2)
    if len(parts) < 3 or parts[0].strip():
        errors.append(f"{_rel(root, path)}: missing YAML frontmatter")
        return {}
    try:
        data = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        errors.append(f"{_rel(root, path)}: invalid YAML frontmatter: {exc}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"{_rel(root, path)}: YAML frontmatter must be a mapping")
        return {}
    return data


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
