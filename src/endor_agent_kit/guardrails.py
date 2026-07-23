"""Guardrail conformance checks for generated Agent Kit catalogs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from endor_agent_kit.agent_api import agent_api_command_errors
from endor_agent_kit.portable_runtime_conformance import (
    UNTRUSTED_CONTENT_BOUNDARY_PREFIX,
    assert_portable_text,
    portable_manifest_conformance_errors,
)
from endor_agent_kit.publication.mcp_support import (
    ENDOR_MCP_SERVER_ARGS,
    ENDOR_MCP_SERVER_COMMAND,
    ENDOR_MCP_SERVER_NAME,
)
from endor_agent_kit.recipe import load_recipe, load_yaml_file
from endor_agent_kit.safety_posture import (
    SourceRecipeSafetyPosture,
    source_recipe_safety_posture,
)
from endor_agent_kit.dlp_scan import scan_catalog_credential_findings
from endor_agent_kit.knowledge_pack import PACK_SECTION_HEADING, validate_knowledge_pack
from endor_agent_kit.provenance import verify_catalog_provenance
from endor_agent_kit.publication.plugin_package_common import package_version
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

NAMESPACE_PREFLIGHT_REQUIRED_TEXT = (
    "## Endor Namespace Preflight",
    "`ENDOR_NAMESPACE` and `ENDOR_API_CREDENTIALS_*` are supported inputs",
    "`ENDOR_NAMESPACE` from the default `~/.endorctl/config.yaml` only",
    "surface both values with provenance and stop for user confirmation",
    "`endorctl agent api --agent-id",
    "tenant-specific",
    "customer-specific",
    "production, backup",
    "non-default Endor config",
)

NAMESPACE_SETUP_REQUIRED_TEXT = (
    "`ENDOR_NAMESPACE`",
    "`ENDOR_API_CREDENTIALS_*`",
    "`~/.endorctl/config.yaml`",
    "tenant-specific",
    "customer-specific",
    "production, backup",
    "non-default Endor config",
    "surface both values",
    "`-n <namespace>` or `--namespace <namespace>`",
)

KNOWLEDGE_PACK_REQUIRED_TEXT = (
    PACK_SECTION_HEADING,
    "Workflow output contracts, hard guardrails, and source recipe instructions remain authoritative",
    "Context first",
    "namespace_provenance",
    "data_gaps",
)

PRIMARY_CLAUDE_PLUGIN_HOOKS = (
    "suggest-endor-tools.sh",
    "check-dep-install.sh",
    "check-manifest-edit.sh",
)

CLAUDE_PLUGIN_HOOK_EVENTS = frozenset({"UserPromptSubmit", "PostToolUse"})
CODEX_PLUGIN_HOOK_EVENTS = frozenset({"UserPromptSubmit", "PostToolUse"})
CURSOR_PLUGIN_HOOK_EVENTS = frozenset({
    "beforeSubmitPrompt",
    "beforeShellExecution",
    "afterFileEdit",
})
GEMINI_PLUGIN_HOOK_EVENTS = frozenset({"BeforeAgent", "BeforeTool", "AfterTool"})
ANTIGRAVITY_PLUGIN_HOOK_EVENTS = frozenset({
    "PreInvocation",
    "PreToolUse",
    "PostToolUse",
})

CLAUDE_PLUGIN_HOOK_FORBIDDEN_TOKENS = (
    "curl ",
    "wget ",
    "nc ",
    "ssh ",
    "sudo ",
    "endorctl scan",
    "endorctl host-check",
    "rm -rf",
)


def check_catalog_guardrails(catalog_root: str | Path = ".") -> list[str]:
    """Return guardrail conformance errors for a generated catalog root."""

    root = Path(catalog_root)
    errors: list[str] = []

    _check_manifest(root, errors)
    _check_docs(root, errors)
    _check_source_recipes(root, errors)
    _check_knowledge_pack_source(root, errors)
    _check_claude_code(root, errors)
    _check_managed_agents(root, errors)
    _check_codex(root, errors)
    _check_gemini(root, errors)
    _check_root_mcp_support(root, errors)
    _check_plugins(root, errors)
    _check_portable(root, errors)
    _check_generated_agent_api_contracts(root, errors)
    _check_credentials(root, errors)
    _check_provenance(root, errors)
    return errors


def _check_generated_agent_api_contracts(root: Path, errors: list[str]) -> None:
    """Bind every generated Endor API command to its canonical recipe identity."""

    agent_ids = _source_agent_ids(root) | {"endor-agent-kit-setup"}
    generated_roots = (
        "agents",
        "claude-code",
        "claude-managed-agents",
        "codex",
        "cursor-sdk",
        "gemini",
        "plugins",
        "portable",
        "skills",
    )
    text_suffixes = {".json", ".md", ".toml", ".yaml", ".yml"}
    for generated_root in generated_roots:
        base = root / generated_root
        if not base.exists():
            continue
        for path in sorted(item for item in base.rglob("*") if item.is_file()):
            if path.suffix.lower() not in text_suffixes:
                continue
            relative = _rel(root, path)
            matching_ids = [agent_id for agent_id in agent_ids if agent_id in relative]
            if not matching_ids:
                continue
            agent_id = max(matching_ids, key=len)
            content = path.read_text(encoding="utf-8")
            for error in agent_api_command_errors(content, agent_id=agent_id):
                errors.append(f"{relative}: {error}")


def _check_credentials(root: Path, errors: list[str]) -> None:
    errors.extend(scan_catalog_credential_findings(root))


def _check_provenance(root: Path, errors: list[str]) -> None:
    if not (root / "manifest.json").is_file():
        return
    errors.extend(verify_catalog_provenance(root))


def _check_namespace_preflight(root: Path, path: Path, content: str, errors: list[str]) -> None:
    for required in NAMESPACE_PREFLIGHT_REQUIRED_TEXT:
        if required not in content:
            errors.append(f"{_rel(root, path)}: missing namespace preflight text {required!r}")


def _check_namespace_setup_guidance(root: Path, path: Path, content: str, errors: list[str]) -> None:
    for required in NAMESPACE_SETUP_REQUIRED_TEXT:
        if required not in content:
            errors.append(f"{_rel(root, path)}: missing namespace setup text {required!r}")


def _check_knowledge_pack_section(root: Path, path: Path, content: str, errors: list[str]) -> None:
    for required in KNOWLEDGE_PACK_REQUIRED_TEXT:
        if required not in content:
            errors.append(f"{_rel(root, path)}: missing Endor Knowledge Pack text {required!r}")
    if content.count(PACK_SECTION_HEADING) != 1:
        errors.append(f"{_rel(root, path)}: Endor Knowledge Pack section must appear exactly once")


def _check_knowledge_pack_source(root: Path, errors: list[str]) -> None:
    pack_root = root / "source" / "endor-knowledge-pack"
    if not pack_root.exists():
        return
    for error in validate_knowledge_pack(pack_root, agent_ids=_source_agent_ids(root)):
            errors.append(f"source/endor-knowledge-pack: {error}")


def _check_root_mcp_support(root: Path, errors: list[str]) -> None:
    root_files = (
        root / ".mcp.json",
        root / "GEMINI.md",
    )
    if (root / "gemini-extension.json").exists():
        errors.append(
            "gemini-extension.json: root Gemini extension manifest must not be generated; "
            "install plugins/gemini/endor-labs-agent-kit instead"
        )

    if not any(path.exists() for path in root_files):
        return

    for path in root_files:
        if not path.is_file():
            errors.append(f"{_rel(root, path)}: missing root MCP support file")

    expected_mcp_server = {
        "args": ENDOR_MCP_SERVER_ARGS,
        "command": ENDOR_MCP_SERVER_COMMAND,
        "type": "stdio",
    }
    mcp_config = _load_json_mapping(root, root / ".mcp.json", errors)
    if mcp_config and _dict(mcp_config.get("mcpServers")).get(ENDOR_MCP_SERVER_NAME) != expected_mcp_server:
        errors.append(f".mcp.json: must declare {ENDOR_MCP_SERVER_NAME} stdio server")

    gemini_context = root / "GEMINI.md"
    if gemini_context.is_file():
        text = gemini_context.read_text(encoding="utf-8")
        for required in (
            "Do not install the repository root as a",
            "Install Gemini CLI from `plugins/gemini/endor-labs-agent-kit/`",
            "Do not load the root Cursor skills as Gemini",
            "Prefer `endorctl agent api --agent-id <canonical-recipe-id>` lookups",
            "Use Endor MCP only when a selected MCP-capable",
            "use the `endor-agent-kit-setup` skill",
            "configure Endor MCP without explicit user approval",
        ):
            if required not in text:
                errors.append(f"GEMINI.md: missing root MCP support text {required!r}")


def _source_agent_ids(root: Path) -> set[str]:
    agent_ids: set[str] = set()
    for recipe_file in sorted((root / "source" / "agents").glob("*/recipe.yaml")):
        try:
            data = load_yaml_file(recipe_file)
        except Exception:
            continue
        recipe_id = data.get("id")
        if isinstance(recipe_id, str):
            agent_ids.add(recipe_id)
    return agent_ids


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
            "Namespace provenance and conflict surfacing",
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
        recipe_id = recipe.get("id")
        transports = recipe.get("supported_transports", [])
        if "endorctl_agent_api" not in transports:
            errors.append(
                f"{_rel(root, recipe_file)}: every agent must support endorctl_agent_api"
            )
        instructions_path = recipe_file.parent / str(
            recipe.get("instructions_path", "instructions.md")
        )
        if isinstance(recipe_id, str) and instructions_path.is_file():
            instructions = instructions_path.read_text(encoding="utf-8")
            for error in agent_api_command_errors(
                instructions,
                agent_id=recipe_id,
                allow_template_identity=True,
            ):
                errors.append(f"{_rel(root, instructions_path)}: {error}")
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
        if recipe.get("id") in {"sca-remediation", "ai-sast-remediation"}:
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
        direct_prompt = agent_dir / f"{agent_dir.name}.md"
        bundle_dirs = [agent_dir] if direct_prompt.is_file() else [
            item
            for item in sorted(agent_dir.iterdir())
            if item.is_dir() and (item / f"{agent_dir.name}.md").is_file()
        ]
        if not bundle_dirs:
            errors.append(f"{_rel(root, direct_prompt)}: missing Claude Code prompt")
            continue
        for bundle_dir in bundle_dirs:
            prompt = bundle_dir / f"{agent_dir.name}.md"
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
            _check_namespace_preflight(root, prompt, content, errors)
            _check_knowledge_pack_section(root, prompt, content, errors)
            setup = bundle_dir / "endorctl-setup.md"
            if setup.is_file():
                _check_namespace_setup_guidance(root, setup, setup.read_text(encoding="utf-8"), errors)


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
        system = str(agent.get("system", ""))
        if UNTRUSTED_CONTENT_BOUNDARY_PREFIX not in system:
            errors.append(f"{_rel(root, agent_file)}: missing untrusted-content boundary")
        _check_namespace_preflight(root, agent_file, system, errors)
        _check_knowledge_pack_section(root, agent_file, system, errors)
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
        setup = agent_dir / "endorctl-setup.md"
        if setup.is_file():
            _check_namespace_setup_guidance(root, setup, setup.read_text(encoding="utf-8"), errors)


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
        _check_namespace_preflight(root, skill, content, errors)
        _check_knowledge_pack_section(root, skill, content, errors)
        setup = agent_dir / "endorctl-setup.md"
        if setup.is_file():
            _check_namespace_setup_guidance(root, setup, setup.read_text(encoding="utf-8"), errors)


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
            _check_namespace_preflight(root, skill, skill_text, errors)
            _check_knowledge_pack_section(root, skill, skill_text, errors)
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
        if frontmatter.get("model") != "gemini-3.5-flash":
            errors.append(
                f"{_rel(root, agent)}: Gemini subagent model must be gemini-3.5-flash"
            )
        for forbidden in ("mcpServers", "hooks"):
            if forbidden in frontmatter:
                errors.append(f"{_rel(root, agent)}: Gemini subagent must not declare {forbidden}")
        _check_namespace_preflight(root, agent, agent_text, errors)
        _check_knowledge_pack_section(root, agent, agent_text, errors)
        setup = agent_dir / "endorctl-setup.md"
        if setup.is_file():
            _check_namespace_setup_guidance(root, setup, setup.read_text(encoding="utf-8"), errors)


def _check_plugins(root: Path, errors: list[str]) -> None:
    plugins_root = root / "plugins"
    expected_package_version = package_version()
    if (root / ".cursor-plugin").is_dir():
        _check_cursor_plugin_package(root, errors)
    if (root / "cursor-sdk").is_dir():
        _check_cursor_sdk_package(root, errors)
    if not plugins_root.is_dir():
        return

    codex_package = plugins_root / "codex" / "endor-labs-agent-kit"
    if codex_package.is_dir():
        _check_codex_plugin_package(root, plugins_root, codex_package, errors)

    claude_root = plugins_root / "claude"
    claude_package = claude_root / "endor-labs-agent-kit"
    legacy_claude_package = claude_root / "ai-plugins"
    if claude_package.is_dir() or legacy_claude_package.is_dir() or (claude_root / ".claude-plugin").is_dir():
        if not claude_package.is_dir():
            errors.append("plugins/claude/endor-labs-agent-kit: missing primary Claude plugin package")
        else:
            _check_claude_plugin_package(
                root,
                claude_package,
                expected_name="endor-labs-agent-kit",
                expected_version=expected_package_version,
                errors=errors,
            )
        if not legacy_claude_package.is_dir():
            errors.append("plugins/claude/ai-plugins: missing legacy Claude plugin package")
        else:
            _check_claude_plugin_package(
                root,
                legacy_claude_package,
                expected_name="ai-plugins",
                expected_version="1.2.0",
                errors=errors,
            )
        _check_claude_marketplace(
            root,
            root / ".claude-plugin" / "marketplace.json",
            {
                "endor-labs-agent-kit": "./plugins/claude/endor-labs-agent-kit",
                "ai-plugins": "./plugins/claude/ai-plugins",
            },
            {
                "endor-labs-agent-kit": expected_package_version,
                "ai-plugins": "1.2.0",
            },
            errors,
        )
        _check_claude_marketplace(
            root,
            plugins_root / "claude" / ".claude-plugin" / "marketplace.json",
            {
                "endor-labs-agent-kit": "./endor-labs-agent-kit",
                "ai-plugins": "./ai-plugins",
            },
            {
                "endor-labs-agent-kit": expected_package_version,
                "ai-plugins": "1.2.0",
            },
            errors,
        )

    gemini_package = plugins_root / "gemini" / "endor-labs-agent-kit"
    if gemini_package.is_dir():
        _check_gemini_plugin_package(root, gemini_package, errors)

    antigravity_package = plugins_root / "antigravity" / "endor-labs-agent-kit"
    if antigravity_package.is_dir():
        _check_antigravity_plugin_package(root, antigravity_package, errors)

    _check_unexpected_plugin_hooks(root, plugins_root, errors)


def _check_unexpected_plugin_hooks(root: Path, plugins_root: Path, errors: list[str]) -> None:
    allowed = {
        root / "plugins" / "claude" / "endor-labs-agent-kit" / "hooks",
        root / "plugins" / "codex" / "endor-labs-agent-kit" / "hooks",
        root / "plugins" / "gemini" / "endor-labs-agent-kit" / "hooks",
        root / "plugins" / "antigravity" / "endor-labs-agent-kit" / "hooks",
    }
    for hooks_dir in sorted(plugins_root.rglob("hooks")):
        if hooks_dir in allowed:
            continue
        if hooks_dir.is_dir():
            errors.append(f"{_rel(root, hooks_dir)}: unexpected plugin hook directory")


def _check_cursor_plugin_package(root: Path, errors: list[str]) -> None:
    expected_package_version = package_version()
    manifest_path = root / ".cursor-plugin" / "plugin.json"
    manifest = _load_json_mapping(root, manifest_path, errors)
    if manifest:
        if manifest.get("name") != "endorlabs":
            errors.append(".cursor-plugin/plugin.json: name must be endorlabs")
        if manifest.get("displayName") != "Endor Labs Agent Kit":
            errors.append(".cursor-plugin/plugin.json: displayName must be Endor Labs Agent Kit")
        if manifest.get("version") != expected_package_version:
            errors.append(f".cursor-plugin/plugin.json: version must be {expected_package_version}")
        if manifest.get("logo") != "assets/logo.png":
            errors.append(".cursor-plugin/plugin.json: logo must be assets/logo.png")
        if manifest.get("agents") != "./agents/":
            errors.append(".cursor-plugin/plugin.json: agents must point at ./agents/")
        if manifest.get("skills") != "./skills/":
            errors.append(".cursor-plugin/plugin.json: skills must point at ./skills/")
        if manifest.get("hooks") != "./hooks/hooks.json":
            errors.append(".cursor-plugin/plugin.json: hooks must point at ./hooks/hooks.json")
        for forbidden in ("mcpServers", "settings", "gemini-extension.json"):
            if forbidden in manifest:
                errors.append(f".cursor-plugin/plugin.json: must not declare {forbidden}")

    marketplace_path = root / ".cursor-plugin" / "marketplace.json"
    marketplace = _load_json_mapping(root, marketplace_path, errors)
    if marketplace:
        if marketplace.get("name") != "endorlabs":
            errors.append(".cursor-plugin/marketplace.json: name must be endorlabs")
        entries = _list(marketplace.get("plugins"))
        entry = next(
            (
                _dict(item)
                for item in entries
                if _dict(item).get("name") == "endorlabs"
            ),
            {},
        )
        if not entry:
            errors.append(".cursor-plugin/marketplace.json: missing endorlabs plugin entry")
        elif entry.get("source") != "./":
            errors.append(".cursor-plugin/marketplace.json: Cursor package source must be './'")

    setup = root / "skills" / "endor-agent-kit-setup" / "SKILL.md"
    if not setup.is_file():
        errors.append(f"{_rel(root, setup)}: missing Cursor setup skill")
    else:
        setup_text = setup.read_text(encoding="utf-8")
        for required in (
            "Run `endorctl scan`",
            "Run `endorctl host-check`",
            "separate from the Gemini CLI extension",
            "Do not add plugin-wide MCP automatically",
        ):
            if required not in setup_text:
                errors.append(f"{_rel(root, setup)}: missing required setup text {required!r}")
        _check_namespace_setup_guidance(root, setup, setup_text, errors)

    expected_skills = (
        "ai-sast-remediation",
        "cicd-posture",
        "troubleshooting",
        "findings-browser",
        "configuration-automation",
        "sca-remediation",
    )
    for skill_id in expected_skills:
        skill = root / "skills" / skill_id / "SKILL.md"
        if not skill.is_file():
            errors.append(f"{_rel(root, skill)}: missing Cursor workflow skill")
            continue
        text = skill.read_text(encoding="utf-8")
        for required in ("## Cursor Host Contract", "data_gaps"):
            if required not in text:
                errors.append(f"{_rel(root, skill)}: missing required Cursor skill text {required!r}")
        if "Gemini CLI Host Contract" in text:
            errors.append(f"{_rel(root, skill)}: Cursor skill must not use Gemini host contract")
        _check_namespace_preflight(root, skill, text, errors)
        _check_knowledge_pack_section(root, skill, text, errors)
        architecture = skill.parent / "architecture.svg"
        if not architecture.is_file():
            errors.append(f"{_rel(root, architecture)}: missing Cursor architecture diagram")

    expected_agents = {
        "ai-sast-remediation": "endor-ai-sast-remediation-agent",
        "cicd-posture": "endor-cicd-posture-agent",
        "troubleshooting": "endor-troubleshooting-agent",
        "findings-browser": "endor-findings-browser-agent",
        "configuration-automation": "endor-configuration-automation-agent",
        "sca-remediation": "endor-sca-remediation-agent",
    }
    mutating_agents = {"ai-sast-remediation", "sca-remediation"}
    for skill_id, agent_name in expected_agents.items():
        agent = root / "agents" / f"{agent_name}.md"
        if not agent.is_file():
            errors.append(f"{_rel(root, agent)}: missing Cursor workflow agent")
            continue
        text = agent.read_text(encoding="utf-8")
        frontmatter = text.split("---", 2)[1] if text.startswith("---") else ""
        for required in (
            f"name: {agent_name}",
            "model: composer-2.5[fast=false]",
            "## Cursor Host Contract",
            "data_gaps",
            "host=cursor",
        ):
            if required not in text:
                errors.append(f"{_rel(root, agent)}: missing required Cursor agent text {required!r}")
        if skill_id in mutating_agents:
            if "readonly: false" not in frontmatter:
                errors.append(f"{_rel(root, agent)}: mutating Cursor agent must set readonly: false")
        elif "readonly: true" not in frontmatter:
            errors.append(f"{_rel(root, agent)}: read-only Cursor agent must set readonly: true")
        if "Gemini CLI Host Contract" in text:
            errors.append(f"{_rel(root, agent)}: Cursor agent must not use Gemini host contract")
        _check_namespace_preflight(root, agent, text, errors)
        _check_knowledge_pack_section(root, agent, text, errors)

    setup_agent = root / "agents" / "endor-agent-kit-setup-agent.md"
    if not setup_agent.is_file():
        errors.append(f"{_rel(root, setup_agent)}: missing Cursor setup agent")
    else:
        setup_agent_text = setup_agent.read_text(encoding="utf-8")
        for required in (
            "Endor Agent Kit Setup Agent For Cursor",
            "model: composer-2.5[fast=false]",
            "agents/",
            "skills/",
            "separate from the Gemini CLI extension",
            "Do not add plugin-wide MCP automatically",
        ):
            if required not in setup_agent_text:
                errors.append(f"{_rel(root, setup_agent)}: missing required setup agent text {required!r}")
        _check_namespace_setup_guidance(root, setup_agent, setup_agent_text, errors)

    _check_advisory_plugin_hooks(
        root,
        hooks_json_path=root / "hooks" / "hooks.json",
        hooks_dir=root / "hooks",
        expected_events=CURSOR_PLUGIN_HOOK_EVENTS,
        command_prefix='bash ./hooks/',
        errors=errors,
        host_label="Cursor",
    )


def _check_cursor_sdk_package(root: Path, errors: list[str]) -> None:
    sdk_root = root / "cursor-sdk"
    readme = sdk_root / "README.md"
    if not readme.is_file():
        errors.append("cursor-sdk/README.md: missing Cursor SDK README")
    else:
        readme_text = readme.read_text(encoding="utf-8")
        for required in (
            "uv pip install -r requirements.txt",
            "run_cursor_agent.py",
            "Cursor Python SDK",
            "Filter > Source > SDK",
            "must not run `endorctl scan` or `endorctl host-check`",
        ):
            if required not in readme_text:
                errors.append(f"cursor-sdk/README.md: missing required SDK text {required!r}")

    requirements = sdk_root / "requirements.txt"
    if not requirements.is_file():
        errors.append("cursor-sdk/requirements.txt: missing Cursor SDK requirements")
    elif "cursor-sdk" not in requirements.read_text(encoding="utf-8"):
        errors.append("cursor-sdk/requirements.txt: must depend on cursor-sdk")

    runner = sdk_root / "run_cursor_agent.py"
    if not runner.is_file():
        errors.append("cursor-sdk/run_cursor_agent.py: missing Cursor SDK runner")
    else:
        runner_text = runner.read_text(encoding="utf-8")
        for required in (
            "from cursor_sdk import (",
            "CURSOR_API_KEY",
            "Agent.create",
            "agent_definitions.json",
            "CloudAgentOptions",
            "LocalAgentOptions",
            "ModelParameterValue",
            "ModelSelection",
            'ModelParameterValue(id="fast", value="false")',
        ):
            if required not in runner_text:
                errors.append(f"cursor-sdk/run_cursor_agent.py: missing required SDK runner text {required!r}")

    definitions = _load_json_mapping(root, sdk_root / "agent_definitions.json", errors)
    expected_agents = {
        "endor-agent-kit-setup": "endor-agent-kit-setup-agent",
        "ai-sast-remediation": "endor-ai-sast-remediation-agent",
        "cicd-posture": "endor-cicd-posture-agent",
        "troubleshooting": "endor-troubleshooting-agent",
        "findings-browser": "endor-findings-browser-agent",
        "configuration-automation": "endor-configuration-automation-agent",
        "sca-remediation": "endor-sca-remediation-agent",
    }
    if definitions:
        if definitions.get("sdk") != "cursor-python":
            errors.append("cursor-sdk/agent_definitions.json: sdk must be cursor-python")
        if definitions.get("default_model") != "composer-2.5":
            errors.append("cursor-sdk/agent_definitions.json: default_model must be composer-2.5")
        agents = _list(definitions.get("agents"))
        by_id = {
            str(_dict(agent).get("id")): _dict(agent)
            for agent in agents
        }
        for agent_id, agent_name in expected_agents.items():
            definition = by_id.get(agent_id)
            if not definition:
                errors.append(f"cursor-sdk/agent_definitions.json: missing {agent_id}")
                continue
            if definition.get("agent_name") != agent_name:
                errors.append(f"cursor-sdk/agent_definitions.json: {agent_id} has wrong agent_name")
            prompt_file = definition.get("prompt_file")
            if not isinstance(prompt_file, str) or not (sdk_root / prompt_file).is_file():
                errors.append(f"cursor-sdk/agent_definitions.json: {agent_id} prompt_file is missing")
            readonly = definition.get("readonly")
            expected_readonly = agent_id not in {"ai-sast-remediation", "sca-remediation"}
            if readonly is not expected_readonly:
                errors.append(f"cursor-sdk/agent_definitions.json: {agent_id} readonly must be {expected_readonly}")

    expected_prompt_files = {
        "endor-agent-kit-setup-agent": "Endor Agent Kit Setup Agent For Cursor SDK",
        "endor-ai-sast-remediation-agent": "## Cursor SDK Host Contract",
        "endor-findings-browser-agent": "## Cursor SDK Host Contract",
        "endor-cicd-posture-agent": "## Cursor SDK Host Contract",
        "endor-troubleshooting-agent": "## Cursor SDK Host Contract",
        "endor-configuration-automation-agent": "## Cursor SDK Host Contract",
        "endor-sca-remediation-agent": "## Cursor SDK Host Contract",
    }
    for agent_name, required_heading in expected_prompt_files.items():
        prompt = sdk_root / "agents" / f"{agent_name}.md"
        if not prompt.is_file():
            errors.append(f"{_rel(root, prompt)}: missing Cursor SDK prompt")
            continue
        text = prompt.read_text(encoding="utf-8")
        for required in (
            required_heading,
            "host=cursor-sdk",
            "data_gaps",
        ):
            if required not in text:
                errors.append(f"{_rel(root, prompt)}: missing required Cursor SDK prompt text {required!r}")
        if "Gemini CLI Host Contract" in text:
            errors.append(f"{_rel(root, prompt)}: Cursor SDK prompt must not use Gemini host contract")
        if agent_name == "endor-agent-kit-setup-agent":
            _check_namespace_setup_guidance(root, prompt, text, errors)
        else:
            _check_namespace_preflight(root, prompt, text, errors)
            _check_knowledge_pack_section(root, prompt, text, errors)


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
    manifest_version = ""
    if manifest:
        manifest_version = str(manifest.get("version") or "")
        if manifest.get("name") != "endor-labs-agent-kit":
            errors.append("plugins/codex/endor-labs-agent-kit/.codex-plugin/plugin.json: name must be endor-labs-agent-kit")
        if "agents" in manifest:
            errors.append("plugins/codex/endor-labs-agent-kit/.codex-plugin/plugin.json: Codex plugin manifest must not declare unsupported agents field")
        if manifest.get("skills") != "./skills/":
            errors.append("plugins/codex/endor-labs-agent-kit/.codex-plugin/plugin.json: skills must point at ./skills/")
        if manifest.get("hooks") != "./hooks/hooks.json":
            errors.append("plugins/codex/endor-labs-agent-kit/.codex-plugin/plugin.json: hooks must point at ./hooks/hooks.json")
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

    _check_advisory_plugin_hooks(
        root,
        hooks_json_path=codex_package / "hooks" / "hooks.json",
        hooks_dir=codex_package / "hooks",
        expected_events=CODEX_PLUGIN_HOOK_EVENTS,
        # Codex-native variable; CLAUDE_PLUGIN_ROOT is only a compat alias
        # (https://developers.openai.com/codex/plugins/build).
        command_prefix='bash "${PLUGIN_ROOT}/hooks/',
        command_uses_quoted_script=True,
        errors=errors,
        host_label="Codex",
    )

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
        _check_namespace_setup_guidance(root, setup, setup_text, errors)

    installer = codex_package / "scripts" / "install_codex_agents.py"
    if not installer.is_file():
        errors.append(f"{_rel(root, installer)}: missing Codex custom-agent installer")
    else:
        installer_text = installer.read_text(encoding="utf-8")
        if manifest_version != "0.1.0":
            for required in (
                "--agents-only",
                "--skills-only",
                "MANAGED_SKILL_MARKERS",
                "shutil.copytree",
                "bundled agents and skills",
            ):
                if required not in installer_text:
                    errors.append(f"{_rel(root, installer)}: missing required installer text {required!r}")

    for skill in sorted((codex_package / "skills").glob("*/SKILL.md")):
        if skill.parent.name == "endor-agent-kit-setup":
            continue
        text = skill.read_text(encoding="utf-8")
        _check_namespace_preflight(root, skill, text, errors)
        _check_knowledge_pack_section(root, skill, text, errors)

    for agent in sorted((codex_package / "agents").glob("*.toml")):
        text = agent.read_text(encoding="utf-8")
        if agent.stem == "endor-agent-kit-setup-agent":
            for required in (
                "# endor_agent_kit_managed = true",
                'model = "gpt-5.6-luna"',
                'model_reasoning_effort = "medium"',
                "developer_instructions = ",
                "Codex Host Contract",
                "Do not run",
                "endorctl host-check",
            ):
                if required not in text:
                    errors.append(f"{_rel(root, agent)}: missing required setup custom-agent text {required!r}")
            continue
        for required in (
            "# endor_agent_kit_managed = true",
            'model = "gpt-5.6-luna"',
            "model_reasoning_effort = ",
            "developer_instructions = ",
            "Codex Host Contract",
        ):
            if required not in text:
                errors.append(f"{_rel(root, agent)}: missing required custom-agent text {required!r}")
        if "_" in agent.stem:
            errors.append(f"{_rel(root, agent)}: Codex custom-agent names must use hyphens, not underscores")
        if not agent.stem.startswith("endor-") or not agent.stem.endswith("-agent"):
            errors.append(f"{_rel(root, agent)}: Codex custom-agent name must use endor-...-agent")
        _check_namespace_preflight(root, agent, text, errors)
        _check_knowledge_pack_section(root, agent, text, errors)

    forbidden_names = {"recipe.yaml", "cases.yaml"}
    for path in codex_package.rglob("*"):
        if path.is_file() and path.name in forbidden_names:
            errors.append(f"{_rel(root, path)}: source-only file leaked into plugin package")


def _check_claude_plugin_package(
    root: Path,
    claude_package: Path,
    *,
    expected_name: str,
    expected_version: str,
    errors: list[str],
) -> None:
    manifest_path = claude_package / ".claude-plugin" / "plugin.json"
    manifest = _load_json_mapping(root, manifest_path, errors)
    manifest_rel = _rel(root, manifest_path)
    if manifest:
        if manifest.get("name") != expected_name:
            errors.append(f"{manifest_rel}: name must be {expected_name}")
        if manifest.get("version") != expected_version:
            errors.append(f"{manifest_rel}: version must be {expected_version}")
        if "agents" in manifest:
            errors.append(f"{manifest_rel}: must not declare default agents path; Claude auto-discovers agents/")
        if "skills" in manifest:
            errors.append(f"{manifest_rel}: must not declare default skills path; Claude auto-discovers skills/")
        if "license" in manifest:
            errors.append(f"{manifest_rel}: license must be omitted until release metadata is final")
        if "mcpServers" in manifest:
            errors.append(f"{manifest_rel}: must not declare plugin-wide MCP")

    _check_claude_plugin_hooks(root, claude_package, expected_name=expected_name, errors=errors)

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
        if expected_name == "ai-plugins":
            for required in (
                "retained for existing Claude Code users and pinned installs",
                "Do not enable both Claude plugin ids in the same profile",
                "does not auto-disable, uninstall, or edit Claude settings",
            ):
                if required not in setup_text:
                    errors.append(f"{_rel(root, setup)}: missing legacy compatibility text {required!r}")
        else:
            for required in (
                "preferred Claude Code plugin id for new installs",
                "Existing `ai-plugins@endorlabs` users can keep using",
                "does not auto-disable, uninstall, or edit Claude settings",
            ):
                if required not in setup_text:
                    errors.append(f"{_rel(root, setup)}: missing Claude compatibility text {required!r}")
        _check_namespace_setup_guidance(root, setup, setup_text, errors)

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
        _check_namespace_preflight(root, agent, text, errors)
        _check_knowledge_pack_section(root, agent, text, errors)

    forbidden_names = {"recipe.yaml", "cases.yaml"}
    for path in claude_package.rglob("*"):
        if path.is_file() and path.name in forbidden_names:
            errors.append(f"{_rel(root, path)}: source-only file leaked into plugin package")


def _check_claude_plugin_hooks(
    root: Path,
    claude_package: Path,
    *,
    expected_name: str,
    errors: list[str],
) -> None:
    hooks_dir = claude_package / "hooks"
    if expected_name == "ai-plugins":
        if hooks_dir.exists():
            errors.append(f"{_rel(root, hooks_dir)}: legacy Claude compatibility package must not include hooks")
        return

    hooks_json_path = hooks_dir / "hooks.json"
    hooks = _load_json_mapping(root, hooks_json_path, errors)
    if not hooks:
        return

    hook_events = _dict(hooks.get("hooks"))
    if set(hook_events) != CLAUDE_PLUGIN_HOOK_EVENTS:
        errors.append(
            f"{_rel(root, hooks_json_path)}: hook events must be {sorted(CLAUDE_PLUGIN_HOOK_EVENTS)}"
        )

    referenced_scripts: set[str] = set()
    for event_name, entries in hook_events.items():
        if event_name not in CLAUDE_PLUGIN_HOOK_EVENTS:
            continue
        for entry_index, entry in enumerate(_list(entries)):
            entry_map = _dict(entry)
            commands = _list(entry_map.get("hooks"))
            if not commands:
                errors.append(
                    f"{_rel(root, hooks_json_path)}: {event_name}[{entry_index}] must declare hook commands"
                )
                continue
            for command_index, command_data in enumerate(commands):
                command_map = _dict(command_data)
                if command_map.get("type") != "command":
                    errors.append(
                        f"{_rel(root, hooks_json_path)}: {event_name}[{entry_index}].hooks[{command_index}] must be a command hook"
                    )
                command = str(command_map.get("command") or "")
                script = _claude_hook_script_from_command(command)
                if script is None:
                    errors.append(
                        f"{_rel(root, hooks_json_path)}: hook command must use bash \"${{CLAUDE_PLUGIN_ROOT}}/hooks/<script>.sh\""
                    )
                    continue
                referenced_scripts.add(script)
                if command_map.get("timeout") != 10:
                    errors.append(
                        f"{_rel(root, hooks_json_path)}: {script} timeout must be 10"
                    )

    expected_scripts = set(PRIMARY_CLAUDE_PLUGIN_HOOKS)
    if referenced_scripts != expected_scripts:
        errors.append(
            f"{_rel(root, hooks_json_path)}: referenced hook scripts must be {sorted(expected_scripts)}"
        )

    for script in PRIMARY_CLAUDE_PLUGIN_HOOKS:
        path = hooks_dir / script
        if not path.is_file():
            errors.append(f"{_rel(root, path)}: missing Claude advisory hook script")
            continue
        text = path.read_text(encoding="utf-8")
        if not text.startswith("#!/usr/bin/env bash"):
            errors.append(f"{_rel(root, path)}: hook script must start with bash shebang")
        if "endor_agent_kit_managed=true" not in text:
            errors.append(f"{_rel(root, path)}: hook script must include managed marker")
        if "exit 0" not in text:
            errors.append(f"{_rel(root, path)}: hook script must fail open with exit 0")
        if "hookSpecificOutput" not in text or "additionalContext" not in text:
            errors.append(f"{_rel(root, path)}: hook script must return Claude hook JSON context")
        if "json.dumps" not in text:
            errors.append(f"{_rel(root, path)}: hook script must use structured JSON output")
        if not (path.stat().st_mode & 0o111):
            errors.append(f"{_rel(root, path)}: hook script must be executable")
        lowered = text.lower()
        for token in CLAUDE_PLUGIN_HOOK_FORBIDDEN_TOKENS:
            if token in lowered:
                errors.append(f"{_rel(root, path)}: hook script must not contain {token!r}")


def _check_advisory_plugin_hooks(
    root: Path,
    *,
    hooks_json_path: Path,
    hooks_dir: Path,
    expected_events: frozenset[str],
    command_prefix: str,
    errors: list[str],
    host_label: str,
    command_uses_quoted_script: bool = False,
    hook_namespace: str | None = None,
) -> None:
    hooks = _load_json_mapping(root, hooks_json_path, errors)
    if not hooks:
        return

    if hook_namespace is not None and set(hooks) != {hook_namespace}:
        errors.append(
            f"{_rel(root, hooks_json_path)}: {host_label} hooks must be nested under {hook_namespace!r}"
        )
    hook_events = _dict(hooks.get(hook_namespace or "hooks"))
    if set(hook_events) != expected_events:
        errors.append(
            f"{_rel(root, hooks_json_path)}: {host_label} hook events must be {sorted(expected_events)}"
        )

    referenced_scripts: set[str] = set()
    for event_name, entries in hook_events.items():
        if event_name not in expected_events:
            continue
        for entry_index, entry in enumerate(_list(entries)):
            entry_map = _dict(entry)
            commands = _advisory_hook_command_maps(entry_map)
            if not commands:
                errors.append(
                    f"{_rel(root, hooks_json_path)}: {event_name}[{entry_index}] must declare hook commands"
                )
                continue
            for command_index, command_map in enumerate(commands):
                if command_map.get("type") != "command":
                    errors.append(
                        f"{_rel(root, hooks_json_path)}: {event_name}[{entry_index}].hooks[{command_index}] must be a command hook"
                    )
                command = str(command_map.get("command") or "")
                script = _advisory_hook_script_from_command(
                    command,
                    event_name,
                    command_prefix=command_prefix,
                    command_uses_quoted_script=command_uses_quoted_script,
                )
                if script is None:
                    errors.append(
                        f"{_rel(root, hooks_json_path)}: {event_name} command must use {command_prefix}<script>.sh {event_name}"
                    )
                    continue
                referenced_scripts.add(script)
                if command_map.get("timeout") != 10:
                    errors.append(
                        f"{_rel(root, hooks_json_path)}: {script} timeout must be 10"
                    )

    expected_scripts = set(PRIMARY_CLAUDE_PLUGIN_HOOKS)
    if referenced_scripts != expected_scripts:
        errors.append(
            f"{_rel(root, hooks_json_path)}: referenced hook scripts must be {sorted(expected_scripts)}"
        )

    _check_advisory_hook_scripts(root, hooks_dir, errors, host_label=host_label)


def _advisory_hook_command_maps(entry_map: dict[str, Any]) -> list[dict[str, Any]]:
    if "command" in entry_map:
        return [entry_map]
    return [_dict(item) for item in _list(entry_map.get("hooks"))]


def _advisory_hook_script_from_command(
    command: str,
    event_name: str,
    *,
    command_prefix: str,
    command_uses_quoted_script: bool,
) -> str | None:
    suffix = f'" {event_name}' if command_uses_quoted_script else f" {event_name}"
    if command.startswith(command_prefix) and command.endswith(suffix):
        script = command[len(command_prefix):-len(suffix)]
        if script in PRIMARY_CLAUDE_PLUGIN_HOOKS:
            return script
    return None


def _check_advisory_hook_scripts(
    root: Path,
    hooks_dir: Path,
    errors: list[str],
    *,
    host_label: str,
) -> None:
    for script in PRIMARY_CLAUDE_PLUGIN_HOOKS:
        path = hooks_dir / script
        if not path.is_file():
            errors.append(f"{_rel(root, path)}: missing {host_label} advisory hook script")
            continue
        text = path.read_text(encoding="utf-8")
        if not text.startswith("#!/usr/bin/env bash"):
            errors.append(f"{_rel(root, path)}: hook script must start with bash shebang")
        if "endor_agent_kit_managed=true" not in text:
            errors.append(f"{_rel(root, path)}: hook script must include managed marker")
        if "exit 0" not in text:
            errors.append(f"{_rel(root, path)}: hook script must fail open with exit 0")
        if "hookSpecificOutput" not in text or "additionalContext" not in text:
            errors.append(f"{_rel(root, path)}: hook script must return advisory hook JSON context")
        if "json.dumps" not in text:
            errors.append(f"{_rel(root, path)}: hook script must use structured JSON output")
        if not (path.stat().st_mode & 0o111):
            errors.append(f"{_rel(root, path)}: hook script must be executable")
        lowered = text.lower()
        for token in CLAUDE_PLUGIN_HOOK_FORBIDDEN_TOKENS:
            if token in lowered:
                errors.append(f"{_rel(root, path)}: hook script must not contain {token!r}")


def _claude_hook_script_from_command(command: str) -> str | None:
    prefix = 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/'
    suffix = '"'
    if command.startswith(prefix) and command.endswith(suffix):
        script = command[len(prefix):-len(suffix)]
        if script in PRIMARY_CLAUDE_PLUGIN_HOOKS:
            return script
    return None


def _check_claude_marketplace(
    root: Path,
    path: Path,
    expected_sources: dict[str, str],
    expected_versions: dict[str, str],
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
    expected_terms = {
        "agentic remediation",
        "SAST remediation",
        "agentic AppSec",
        "AppSec",
        "OSS Upgrade Investigator",
    }
    for plugin_name, expected_source in expected_sources.items():
        entry = next(
            (
                _dict(item)
                for item in entries
                if _dict(item).get("name") == plugin_name
            ),
            {},
        )
        if not entry:
            errors.append(f"{_rel(root, path)}: missing {plugin_name} plugin entry")
            continue
        if entry.get("source") != expected_source:
            errors.append(f"{_rel(root, path)}: {plugin_name} source must be {expected_source!r}")
        source = entry.get("source")
        if not isinstance(source, str) or not source.startswith("./") or "/../" in source or source.startswith("../"):
            errors.append(f"{_rel(root, path)}: {plugin_name} source must be a marketplace-root relative path starting with ./")
        expected_version = expected_versions[plugin_name]
        if entry.get("version") != expected_version:
            errors.append(f"{_rel(root, path)}: {plugin_name} entry version must match package version {expected_version}")
        tags = set(str(item) for item in _list(entry.get("tags")))
        keywords = set(str(item) for item in _list(entry.get("keywords")))
        if not expected_terms <= tags:
            missing = sorted(expected_terms - tags)
            errors.append(f"{_rel(root, path)}: {plugin_name} entry tags missing discovery terms {missing}")
        if not expected_terms <= keywords:
            missing = sorted(expected_terms - keywords)
            errors.append(f"{_rel(root, path)}: {plugin_name} entry keywords missing discovery terms {missing}")


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
        _check_namespace_setup_guidance(root, setup, setup_text, errors)

    for skill in sorted((gemini_package / "skills").glob("*/SKILL.md")):
        if skill.parent.name == "endor-agent-kit-setup":
            continue
        text = skill.read_text(encoding="utf-8")
        for required in ("## Gemini CLI Host Contract", "data_gaps"):
            if required not in text:
                errors.append(f"{_rel(root, skill)}: missing required Gemini plugin skill text {required!r}")
        _check_namespace_preflight(root, skill, text, errors)
        _check_knowledge_pack_section(root, skill, text, errors)

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
        if frontmatter.get("model") != "gemini-3.5-flash":
            errors.append(f"{_rel(root, agent)}: Gemini subagent model must be gemini-3.5-flash")
        for forbidden in ("mcpServers", "hooks"):
            if forbidden in frontmatter:
                errors.append(f"{_rel(root, agent)}: Gemini plugin subagent must not declare {forbidden}")
        _check_namespace_preflight(root, agent, text, errors)
        _check_knowledge_pack_section(root, agent, text, errors)

    forbidden_names = {"recipe.yaml", "cases.yaml"}
    for path in gemini_package.rglob("*"):
        if path.is_file() and path.name in forbidden_names:
            errors.append(f"{_rel(root, path)}: source-only file leaked into plugin package")

    _check_advisory_plugin_hooks(
        root,
        hooks_json_path=gemini_package / "hooks" / "hooks.json",
        hooks_dir=gemini_package / "hooks",
        expected_events=GEMINI_PLUGIN_HOOK_EVENTS,
        command_prefix='bash ./hooks/',
        errors=errors,
        host_label="Gemini",
    )

    archive_path = root / "plugins" / "gemini" / "endor-labs-agent-kit.zip"
    if archive_path.exists():
        errors.append(f"{_rel(root, archive_path)}: Gemini plugin packaging must not generate a zip archive")


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
        _check_namespace_setup_guidance(root, setup, setup_text, errors)

    for skill in sorted((antigravity_package / "skills").glob("*/SKILL.md")):
        if skill.parent.name == "endor-agent-kit-setup":
            continue
        text = skill.read_text(encoding="utf-8")
        for required in ("## Antigravity CLI Host Contract", "data_gaps"):
            if required not in text:
                errors.append(f"{_rel(root, skill)}: missing required Antigravity plugin skill text {required!r}")
        _check_namespace_preflight(root, skill, text, errors)
        _check_knowledge_pack_section(root, skill, text, errors)

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
        if frontmatter.get("model") != "inherit":
            errors.append(
                f"{_rel(root, agent)}: Antigravity plugin cannot pin a per-agent model; host-pinned agents must retain model: inherit"
            )
        for forbidden in ("mcpServers", "hooks"):
            if forbidden in frontmatter:
                errors.append(f"{_rel(root, agent)}: Antigravity plugin subagent must not declare {forbidden}")
        _check_namespace_preflight(root, agent, text, errors)
        _check_knowledge_pack_section(root, agent, text, errors)

    forbidden_names = {"recipe.yaml", "cases.yaml"}
    for path in antigravity_package.rglob("*"):
        if path.is_file() and path.name in forbidden_names:
            errors.append(f"{_rel(root, path)}: source-only file leaked into plugin package")

    _check_advisory_plugin_hooks(
        root,
        hooks_json_path=antigravity_package / "hooks.json",
        hooks_dir=antigravity_package / "hooks",
        expected_events=ANTIGRAVITY_PLUGIN_HOOK_EVENTS,
        command_prefix='bash ./hooks/',
        errors=errors,
        host_label="Antigravity",
        hook_namespace="endor-labs-agent-kit",
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
            if path.name == "endorctl-setup.md":
                _check_namespace_setup_guidance(root, path, content, errors)
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
        _check_namespace_preflight(root, agent, agent_text, errors)
        _check_knowledge_pack_section(root, agent, agent_text, errors)

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
