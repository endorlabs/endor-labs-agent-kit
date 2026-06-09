"""Codex plugin package publication."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
import shutil
from pathlib import Path
from textwrap import dedent

from endor_agent_kit.catalog_schema import CatalogPluginPackage
from endor_agent_kit.compilers.codex import HOST as CODEX_HOST, render_codex_skill
from endor_agent_kit.prepared_source_recipe import PreparedSourceRecipe
from endor_agent_kit.publication.plugin_package_common import (
    PLUGIN_DISPLAY_NAME,
    PLUGIN_NAME,
    logo_svg,
    package_version,
    plugin_readme_start_here,
    plugin_packages_readme,
)
from endor_agent_kit.safety_posture import source_recipe_safety_posture

CODEX_PLUGIN_PACKAGE_ROOT = Path("plugins") / "codex" / PLUGIN_NAME
CODEX_MARKETPLACE_PATH = Path(".agents") / "plugins" / "marketplace.json"
CODEX_LOCAL_MARKETPLACE_PATH = Path("plugins") / "codex" / ".agents" / "plugins" / "marketplace.json"
CODEX_SETUP_SKILL = "endor-agent-kit-setup"
CODEX_SETUP_AGENT = "endor-agent-kit-setup-agent"
CODEX_AGENT_SUFFIX = "-agent"
CODEX_SECTION_EDITION = "enterprise-edition"
CODEX_INSTALLER_REPO_PATH = CODEX_PLUGIN_PACKAGE_ROOT / "scripts" / "install_codex_agents.py"
CODEX_INSTALLER_REPO_COMMAND = f"python {CODEX_INSTALLER_REPO_PATH.as_posix()}"
CODEX_INSTALLER_COMMAND = 'python "$ENDOR_CODEX_INSTALLER"'


@dataclass(frozen=True)
class PluginPackagePublication:
    """Result of publishing one generated plugin package."""

    package_record: CatalogPluginPackage
    written: tuple[Path, ...]


def publish_codex_plugin_package(
    prepared_recipes: list[PreparedSourceRecipe],
    destination: Path,
) -> PluginPackagePublication | None:
    """Publish the generated Codex plugin package for compatible recipes."""

    codex_recipes = [
        prepared
        for prepared in prepared_recipes
        if CODEX_HOST in prepared.recipe.compatible_hosts
    ]
    if not codex_recipes:
        return None

    package_dir = destination / CODEX_PLUGIN_PACKAGE_ROOT
    marketplace_path = destination / CODEX_MARKETPLACE_PATH
    local_marketplace_path = destination / CODEX_LOCAL_MARKETPLACE_PATH
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True)
    (package_dir / ".codex-plugin").mkdir()
    (package_dir / "skills").mkdir()
    (package_dir / "agents").mkdir()
    (package_dir / "scripts").mkdir()
    (package_dir / "assets").mkdir()
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    local_marketplace_path.parent.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    version = package_version()
    sorted_recipes = sorted(codex_recipes, key=lambda item: item.recipe.id)

    for prepared in sorted_recipes:
        skill_dir = package_dir / "skills" / prepared.recipe.id
        skill_dir.mkdir(parents=True)
        skill = skill_dir / "SKILL.md"
        skill.write_text(
            render_codex_skill(
                prepared,
                generated_context="Endor Labs Agent Kit Codex plugin",
                compact_plugin=True,
                package_name=PLUGIN_NAME,
                package_version=version,
            ),
            encoding="utf-8",
        )
        written.append(skill)

        agent = package_dir / "agents" / f"{_codex_agent_name(prepared.recipe.id)}.toml"
        agent.write_text(_render_codex_agent_toml(prepared, version), encoding="utf-8")
        written.append(agent)

    setup_skill_dir = package_dir / "skills" / CODEX_SETUP_SKILL
    setup_skill_dir.mkdir(parents=True)
    setup_skill = setup_skill_dir / "SKILL.md"
    setup_skill.write_text(_render_setup_skill(sorted_recipes, version), encoding="utf-8")
    written.append(setup_skill)

    setup_agent = package_dir / "agents" / f"{CODEX_SETUP_AGENT}.toml"
    setup_agent.write_text(_render_codex_setup_agent_toml(sorted_recipes, version), encoding="utf-8")
    written.append(setup_agent)

    installer = package_dir / "scripts" / "install_codex_agents.py"
    installer.write_text(_codex_agent_installer_script(version), encoding="utf-8")
    written.append(installer)

    logo = package_dir / "assets" / "logo.svg"
    logo.write_text(logo_svg(), encoding="utf-8")
    written.append(logo)

    plugin_manifest = package_dir / ".codex-plugin" / "plugin.json"
    plugin_manifest.write_text(
        json.dumps(_codex_plugin_manifest(version), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    written.append(plugin_manifest)

    readme = package_dir / "README.md"
    readme.write_text(_codex_plugin_readme(sorted_recipes, version), encoding="utf-8")
    written.append(readme)

    marketplace_path.write_text(
        json.dumps(
            _codex_marketplace_manifest(f"./{CODEX_PLUGIN_PACKAGE_ROOT.as_posix()}"),
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    written.append(marketplace_path)

    local_marketplace_path.write_text(
        json.dumps(
            _codex_marketplace_manifest(f"./{PLUGIN_NAME}"),
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )
    written.append(local_marketplace_path)

    plugins_readme = destination / "plugins" / "README.md"
    plugins_readme.write_text(plugin_packages_readme(), encoding="utf-8")
    written.append(plugins_readme)

    package_record = CatalogPluginPackage.from_published_package(
        destination,
        host=CODEX_HOST,
        name=PLUGIN_NAME,
        display_name=PLUGIN_DISPLAY_NAME,
        version=version,
        package_dir=package_dir,
        marketplace_path=CODEX_MARKETPLACE_PATH.as_posix(),
        included_agents=tuple(prepared.recipe.id for prepared in sorted_recipes),
        extra_artifacts=(marketplace_path, local_marketplace_path, plugins_readme),
    )
    return PluginPackagePublication(package_record=package_record, written=tuple(written))


def _codex_agent_name(recipe_id: str) -> str:
    if recipe_id.startswith("endor-"):
        return f"{recipe_id}{CODEX_AGENT_SUFFIX}"
    return f"endor-{recipe_id}{CODEX_AGENT_SUFFIX}"


def _render_codex_agent_toml(prepared: PreparedSourceRecipe, version: str) -> str:
    recipe = prepared.recipe
    posture = source_recipe_safety_posture(recipe)
    skill_text = render_codex_skill(
        prepared,
        generated_context="Endor Labs Agent Kit Codex custom agent",
        compact_plugin=True,
        package_name=PLUGIN_NAME,
        package_version=version,
    )
    body = _strip_frontmatter(skill_text)
    body += f"\n\nSetup gaps: use `{CODEX_SETUP_SKILL}`.\n"
    lines = [
        "# Generated by Endor Labs Agent Kit. Do not hand-edit installed copies.",
        "# endor_agent_kit_managed = true",
        f"# endor_agent_kit_package_name = {_toml_string(PLUGIN_NAME)}",
        f"# endor_agent_kit_package_version = {_toml_string(version)}",
        f"# endor_agent_kit_agent_id = {_toml_string(recipe.id)}",
        f"# endor_agent_kit_agent_name = {_toml_string(_codex_agent_name(recipe.id))}",
        f"# endor_agent_kit_recipe_version = {_toml_string(recipe.version)}",
        f"# endor_agent_kit_source_recipe = {_toml_string(f'source/agents/{recipe.id}/recipe.yaml')}",
        "",
        f"name = {_toml_string(_codex_agent_name(recipe.id))}",
        f"description = {_toml_string(_single_line(recipe.description))}",
    ]
    if not posture.is_mutating:
        lines.append('sandbox_mode = "read-only"')
    lines.extend([
        f"developer_instructions = {_toml_string(body)}",
        "",
    ])
    return "\n".join(lines)


def _render_codex_setup_agent_toml(prepared_recipes: list[PreparedSourceRecipe], version: str) -> str:
    workflow_names = ", ".join(prepared.recipe.id for prepared in prepared_recipes)
    instructions = "\n".join([
        "<!-- Generated by Endor Labs Agent Kit. Do not hand-edit installed copies. -->",
        f"<!-- endor_agent_kit_managed=true agent_id=endor-agent-kit-setup host=codex package={PLUGIN_NAME} version={version} -->",
        "",
        "# Endor Agent Kit Setup Agent For Codex",
        "",
        f"Generated for the Endor Labs Agent Kit Codex plugin package `{PLUGIN_NAME}` v{version}.",
        f"Use `{CODEX_SETUP_SKILL}` as the exhaustive setup skill when Codex exposes skills more reliably than custom agents.",
        "",
        "## Bundled Workflows",
        "",
        f"Workflow agents: {workflow_names}.",
        f"Setup agent: `{CODEX_SETUP_AGENT}`.",
        "",
        "## Installer Commands",
        "",
        "Resolve the bundled installer from either the checkout root or Codex plugin cache:",
        "",
        "```bash",
        f"ENDOR_CODEX_INSTALLER=\"{CODEX_INSTALLER_REPO_PATH.as_posix()}\"",
        'if [ ! -f "$ENDOR_CODEX_INSTALLER" ]; then',
        '  ENDOR_CODEX_INSTALLER="$(find "${CODEX_HOME:-$HOME/.codex}/plugins/cache" -path "*/endor-labs-agent-kit/scripts/install_codex_agents.py" -print -quit)"',
        "fi",
        'test -f "$ENDOR_CODEX_INSTALLER"',
        "```",
        "",
        "After user approval, use only these managed-file commands:",
        "",
        "```bash",
        f"{CODEX_INSTALLER_COMMAND} --status",
        f"{CODEX_INSTALLER_COMMAND} --purge-stale-plugin-cache --yes",
        f"{CODEX_INSTALLER_COMMAND} --install --yes",
        f"{CODEX_INSTALLER_COMMAND} --install --agents-only --yes",
        f"{CODEX_INSTALLER_COMMAND} --install --skills-only --yes",
        f"{CODEX_INSTALLER_COMMAND} --uninstall --yes",
        "```",
        "",
        "## Setup Contract",
        "",
        "Start with a concise readiness report: ready, needs action, optional checks, and available fixes.",
        "Check command availability, versions, namespace provenance, Endor auth presence, and `gh auth status` when a selected workflow needs GitHub evidence.",
        "For Endor namespace provenance, surface both `ENDOR_NAMESPACE` and default `~/.endorctl/config.yaml` namespace when they disagree, then stop for user choice before live Endor lookups.",
        "Report credential presence by key name only. Never print, dump, source, recurse through, or `cat` Endor config files or secrets.",
        "Do not read tenant-specific, customer-specific, production, backup, or non-default Endor config directories unless the user explicitly requests that separate operation.",
        "Use `-n <namespace>` or `--namespace <namespace>` after the user selects a namespace.",
        "",
        "Do not run `endorctl scan` or `endorctl host-check`. Setup must not install tools, edit shell profiles, write Endor credentials, create branches, open PRs/MRs, post comments, write Endor policies, or remediate findings.",
        "MCP remains opt-in: prefer documented Endor API or `endorctl api`; configure Endor MCP only when a selected MCP-capable workflow needs it or the user explicitly asks.",
        "If MCP setup is approved, validate the proposed command is `npx -y endorctl ai-tools mcp-server`, show the exact host config change first, and verify tool visibility in a fresh host session when supported.",
        "",
        "## Codex Host Contract",
        "",
        "This setup custom agent is installed from the Endor Labs Agent Kit Codex plugin. Keep setup read-only unless the user explicitly approves local package installation or managed Agent Kit file installation.",
        f"Use provenance-gated updates. Unknown files or directories must not be overwritten. Use `{CODEX_SETUP_SKILL}` for full setup details.",
        "",
    ])
    lines = [
        "# Generated by Endor Labs Agent Kit. Do not hand-edit installed copies.",
        "# endor_agent_kit_managed = true",
        f"# endor_agent_kit_package_name = {_toml_string(PLUGIN_NAME)}",
        f"# endor_agent_kit_package_version = {_toml_string(version)}",
        '# endor_agent_kit_agent_id = "endor-agent-kit-setup"',
        f"# endor_agent_kit_agent_name = {_toml_string(CODEX_SETUP_AGENT)}",
        '# endor_agent_kit_source = "source/plugin-support/setup/setup.md"',
        "",
        f"name = {_toml_string(CODEX_SETUP_AGENT)}",
        'description = "Set up and validate Endor Labs Agent Kit readiness for Codex."',
        'sandbox_mode = "read-only"',
        f"developer_instructions = {_toml_string(instructions)}",
        "",
    ]
    return "\n".join(lines)


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _strip_frontmatter(markdown: str) -> str:
    parts = markdown.split("---", 2)
    if len(parts) == 3 and not parts[0].strip():
        return parts[2].lstrip()
    return markdown


def _single_line(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _render_setup_skill(prepared_recipes: list[PreparedSourceRecipe], version: str) -> str:
    setup_source = _setup_source(prepared_recipes)
    workflow_lines = [
        f"- `{prepared.recipe.id}` -> `{_codex_agent_name(prepared.recipe.id)}`"
        for prepared in prepared_recipes
    ]
    return "\n".join([
        "---",
        f"name: {CODEX_SETUP_SKILL}",
        "description: |",
        "  Use when setting up Endor Labs Agent Kit for Codex, checking readiness,",
        "  installing or updating bundled Codex custom agents, verifying Endor auth,",
        "  or diagnosing missing endorctl, gh, namespace, or toolchain prerequisites.",
        "---",
        "",
        "<!-- Generated by Endor Labs Agent Kit. Do not hand-edit installed copies. -->",
        f"<!-- endor_agent_kit_managed=true agent_id=endor-agent-kit-setup host=codex package={PLUGIN_NAME} version={version} -->",
        "",
        "# Endor Agent Kit Setup For Codex",
        "",
        f"Generated for the Endor Labs Agent Kit Codex plugin package `{PLUGIN_NAME}` v{version}.",
        "",
        "## Bundled Codex Custom Agents And Skills",
        "",
        *workflow_lines,
        f"- `{CODEX_SETUP_SKILL}` -> `{CODEX_SETUP_AGENT}`",
        "",
        "## Codex Install Commands",
        "",
        "Resolve the bundled installer from either the Agent Kit/`ai-plugins`",
        "checkout root or Codex's plugin cache:",
        "",
        "```bash",
        f"ENDOR_CODEX_INSTALLER=\"{CODEX_INSTALLER_REPO_PATH.as_posix()}\"",
        'if [ ! -f "$ENDOR_CODEX_INSTALLER" ]; then',
        '  ENDOR_CODEX_INSTALLER="$(find "${CODEX_HOME:-$HOME/.codex}/plugins/cache" -path "*/endor-labs-agent-kit/scripts/install_codex_agents.py" -print -quit)"',
        "fi",
        'test -f "$ENDOR_CODEX_INSTALLER"',
        "```",
        "",
        "Check installed Endor Codex agents and skills:",
        "",
        "```bash",
        f"{CODEX_INSTALLER_COMMAND} --status",
        "```",
        "",
        "Move stale Endor Agent Kit plugin-cache copies out of Codex's active cache after user approval:",
        "",
        "```bash",
        f"{CODEX_INSTALLER_COMMAND} --purge-stale-plugin-cache --yes",
        "```",
        "",
        "Install or update all bundled Endor Codex agents and skills after user approval:",
        "",
        "```bash",
        f"{CODEX_INSTALLER_COMMAND} --install --yes",
        "```",
        "",
        "Install only one surface when diagnosing host discovery:",
        "",
        "```bash",
        f"{CODEX_INSTALLER_COMMAND} --install --agents-only --yes",
        f"{CODEX_INSTALLER_COMMAND} --install --skills-only --yes",
        "```",
        "",
        "Uninstall only Endor Agent Kit-managed Codex agents and skills after user approval:",
        "",
        "```bash",
        f"{CODEX_INSTALLER_COMMAND} --uninstall --yes",
        "```",
        "",
        setup_source.rstrip(),
        "",
        "## Codex-Specific Rules",
        "",
        "- Install Codex custom agents globally by default under `${CODEX_HOME:-~/.codex}/agents` and bundled user skills under `$HOME/.agents/skills`.",
        "- Do not write project-local `.codex/agents/` or repo-local `.agents/skills/` files unless the user explicitly requests that advanced option.",
        "- Use provenance-gated updates: missing files may be installed; managed stale files may be updated after approval; unknown files or directories must not be overwritten.",
        "- Treat stale Endor Agent Kit plugin-cache warnings from `--status` as active-host risk; remove or reinstall the stale plugin package and start a fresh Codex thread before judging agent behavior.",
        "- Use `--purge-stale-plugin-cache --yes` only after user approval; it moves stale Endor Agent Kit cache directories to `${CODEX_HOME:-~/.codex}/plugins/cache-backups/`.",
        "- Tell the user to start a new Codex thread after installing or updating custom agents or skills.",
        "",
    ])


def _setup_source(prepared_recipes: list[PreparedSourceRecipe]) -> str:
    first_path = prepared_recipes[0].path
    candidates = [
        first_path.parents[2] / "plugin-support" / "setup" / "setup.md",
        Path.cwd() / "source" / "plugin-support" / "setup" / "setup.md",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    raise FileNotFoundError("source/plugin-support/setup/setup.md")


def _codex_plugin_manifest(version: str) -> dict[str, object]:
    return {
        "name": PLUGIN_NAME,
        "version": version,
        "description": "Endor Labs workflow agents and setup for Codex.",
        "author": {
            "name": "Endor Labs",
            "url": "https://www.endorlabs.com/",
        },
        "homepage": "https://github.com/endorlabs/ai-plugins",
        "repository": "https://github.com/endorlabs/ai-plugins",
        "keywords": [
            "endor-labs",
            "security",
            "sca",
            "sast",
            "codex",
        ],
        "skills": "./skills/",
        "interface": {
            "displayName": PLUGIN_DISPLAY_NAME,
            "shortDescription": "Endor Labs security workflows for Codex.",
            "longDescription": (
                "Install setup guidance, Codex skills, and bundled custom agents for "
                "Endor Labs SCA remediation, AI SAST triage, troubleshooting, and "
                "onboarding analysis workflows."
            ),
            "developerName": "Endor Labs",
            "category": "Developer Tools",
            "capabilities": ["Code", "Security", "Workflow"],
            "websiteURL": "https://www.endorlabs.com/",
            "defaultPrompt": [
                "Set up Endor Agent Kit for this machine.",
                "Triage AI SAST findings for this repository.",
                "Find the safest SCA remediation path.",
            ],
            "brandColor": "#4F46E5",
            "logo": "./assets/logo.svg",
        },
    }


def _codex_marketplace_manifest(plugin_path: str) -> dict[str, object]:
    return {
        "name": PLUGIN_NAME,
        "interface": {
            "displayName": PLUGIN_DISPLAY_NAME,
        },
        "plugins": [
            {
                "name": PLUGIN_NAME,
                "source": {
                    "source": "local",
                    "path": plugin_path,
                },
                "policy": {
                    "installation": "AVAILABLE",
                    "authentication": "ON_INSTALL",
                },
                "category": "Developer Tools",
            }
        ],
    }


def _codex_plugin_readme(
    prepared_recipes: list[PreparedSourceRecipe],
    version: str,
) -> str:
    rows = [
        f"| {_workflow_label(prepared.recipe.id)} | `{prepared.recipe.id}` | `{_codex_agent_name(prepared.recipe.id)}` | {_workflow_safety(prepared)} |"
        for prepared in prepared_recipes
    ]
    start_here = plugin_readme_start_here(
        host_label="Codex",
        install_summary=f"Install `{PLUGIN_NAME}@{PLUGIN_NAME}` from the local or public Codex marketplace metadata.",
        setup_summary=f"ask Codex to use the `{CODEX_SETUP_SKILL}` skill.",
    )
    return "\n".join([
        "# Endor Labs Agent Kit Codex Plugin",
        "",
        "<!-- Generated by Endor Labs Agent Kit. Do not hand-edit. -->",
        "",
        f"Version: `{version}`",
        "",
        "This generated Codex plugin package includes Endor Labs setup support,",
        "Codex skills, and bundled Codex custom-agent TOML files. The plugin is",
        "generated from source recipes in the Endor Labs Agent Kit repository.",
        "",
        *start_here,
        "## Host Metadata",
        "",
        "- Manifest: `.codex-plugin/plugin.json`.",
        "- Skills: `skills/<agent>/SKILL.md`, including `endor-agent-kit-setup`.",
        f"- Custom agents: `agents/endor-*-agent.toml`, including `{CODEX_SETUP_AGENT}.toml`, installed by the setup skill only after approval.",
        "- Model/runtime: custom agents inherit Codex defaults unless the user or host overrides them; read-only custom agents set `sandbox_mode = \"read-only\"`.",
        "- MCP: no plugin-wide MCP server is declared by default.",
        "",
        "## Install Locally",
        "",
        "From the Agent Kit repository root:",
        "",
        "```bash",
        "codex plugin marketplace add ./plugins/codex",
        f"codex plugin add {PLUGIN_NAME}@{PLUGIN_NAME}",
        "```",
        "",
        "After the repository is public and tagged, install from the repository",
        "marketplace metadata at `.agents/plugins/marketplace.json`:",
        "",
        "```bash",
        "codex plugin marketplace add endorlabs/ai-plugins --ref <tag> --sparse .agents --sparse plugins/codex/endor-labs-agent-kit",
        f"codex plugin add {PLUGIN_NAME}@{PLUGIN_NAME}",
        "```",
        "",
        "Start a new Codex thread after installing or reinstalling the plugin.",
        "If Codex still shows stale same-version content, remove and reinstall",
        f"the plugin, rerun `{CODEX_INSTALLER_REPO_COMMAND} --install --yes` from the checkout root,",
        "and start another fresh thread so host caches reload both skills and agents.",
        "",
        "## Set Up This Machine",
        "",
        "Ask Codex:",
        "",
        "```text",
        "Use the endor-agent-kit-setup skill, or the endor-agent-kit-setup-agent custom agent, to check readiness and install the bundled Codex custom agents and skills.",
        "```",
        "",
        "The setup skill can install or update managed Endor Codex custom agents",
        "under `${CODEX_HOME:-~/.codex}/agents` and bundled user skills under `$HOME/.agents/skills` after explicit approval. It does",
        "not run scans, run `endorctl host-check`, edit shell profiles, install",
        "`gh`, or install language runtimes and package managers.",
        "",
        "## Capabilities And Skills",
        "",
        "| Job | Codex skill | Codex custom agent | Safety |",
        "| --- | --- | --- | --- |",
        f"| Set up this machine | `{CODEX_SETUP_SKILL}` | `{CODEX_SETUP_AGENT}` | read-only setup |",
        *rows,
        "",
        "Mutating workflows keep file edits, branch pushes, PR/MR creation,",
        "comments, approval verification, and Endor policy writes behind separate",
        "approval gates. Setup never performs those workflow actions.",
        "",
        "## Boundaries And Rules",
        "",
        "- Always run readiness and namespace checks before live Endor lookups.",
        "- Always keep setup, file edits, branch pushes, PR/MR creation, comments, tickets, and policy writes as separate evidence-backed steps.",
        "- Never run setup scans or `endorctl host-check`.",
        "- Never auto-install `gh`, language runtimes, or package managers in v1.",
        "- Never print, persist, or copy Endor API key, secret, token, or full config values.",
        "",
        "## Manual Fallback",
        "",
        "If plugin installation is unavailable, install individual generated Codex",
        "skills from the repository-level `codex/<agent>/` directories into",
        "`$HOME/.agents/skills/<agent>`.",
        "",
        "## Provider Docs",
        "",
        "Before release, verify the current Codex plugin and custom-agent docs:",
        "",
        "- https://developers.openai.com/codex/plugins/build",
        "- https://developers.openai.com/codex/subagents",
        "",
    ])


def _workflow_label(agent_id: str) -> str:
    labels = {
        "ai-sast-triage": "Triage AI SAST findings",
        "endor-troubleshooter": "Diagnose Endor setup and scan issues",
        "probe-droid": "Assess GitHub onboarding gaps",
        "sca-remediation": "Find safe SCA remediation paths",
    }
    return labels.get(agent_id, agent_id.replace("-", " ").title())


def _workflow_safety(prepared: PreparedSourceRecipe) -> str:
    return "mutating, approval-gated" if source_recipe_safety_posture(prepared.recipe).is_mutating else "read-only"


def _codex_agent_installer_script(version: str) -> str:
    script = dedent(
        r'''
        #!/usr/bin/env python3
        """Install, update, inspect, or uninstall Endor Agent Kit Codex agents and skills."""

        from __future__ import annotations

        import argparse
        import hashlib
        import json
        import os
        from pathlib import Path
        import re
        import shutil
        import sys
        from datetime import datetime, timezone

        CURRENT_PLUGIN_NAME = "__ENDOR_AGENT_KIT_PLUGIN_NAME__"
        CURRENT_PLUGIN_VERSION = "__ENDOR_AGENT_KIT_PLUGIN_VERSION__"
        ENDOR_PLUGIN_CACHE_NAMES = {
            CURRENT_PLUGIN_NAME,
            "endor-agent-kit-security-agents",
        }
        LEGACY_CODEX_PLUGIN_IDS = {
            "endor-agent-kit-security-agents@endor-agent-kit-local",
        }
        PLUGIN_TABLE_RE = re.compile(r'^\[plugins\."(?P<name>[^"]+)"\]\s*$')
        MANAGED_AGENT_MARKER = "# endor_agent_kit_managed = true"
        MANAGED_SKILL_MARKERS = (
            "endor_agent_kit_managed=true",
            "Generated from Endor Agent Kit recipe",
            "Generated for the Endor Labs Agent Kit Codex plugin",
        )


        def file_digest(path: Path) -> str:
            digest = hashlib.sha256()
            digest.update(path.read_bytes())
            return digest.hexdigest()


        def tree_digest(path: Path) -> str:
            digest = hashlib.sha256()
            for child in sorted(item for item in path.rglob("*") if item.is_file()):
                digest.update(child.relative_to(path).as_posix().encode("utf-8"))
                digest.update(b"\0")
                digest.update(child.read_bytes())
                digest.update(b"\0")
            return digest.hexdigest()


        def codex_home(value: str | None) -> Path:
            if value:
                return Path(value).expanduser()
            return Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()


        def codex_skills_home(value: str | None) -> Path:
            if value:
                return Path(value).expanduser()
            return Path("~/.agents/skills").expanduser()


        def bundled_agents(plugin_root: Path) -> list[Path]:
            return sorted((plugin_root / "agents").glob("*.toml"))


        def bundled_skills(plugin_root: Path) -> list[Path]:
            skills_root = plugin_root / "skills"
            if not skills_root.is_dir():
                return []
            return sorted(path for path in skills_root.iterdir() if (path / "SKILL.md").is_file())


        def is_managed_agent(path: Path) -> bool:
            if not path.is_file():
                return False
            try:
                return MANAGED_AGENT_MARKER in path.read_text(encoding="utf-8").splitlines()[:12]
            except UnicodeDecodeError:
                return False


        def is_managed_skill(path: Path) -> bool:
            skill = path / "SKILL.md"
            if not skill.is_file():
                return False
            try:
                text = skill.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                return False
            return any(marker in text for marker in MANAGED_SKILL_MARKERS)


        def item_status(kind: str, source: Path, target: Path) -> str:
            if not target.exists():
                return "missing"
            if kind == "agent":
                if not target.is_file():
                    return "blocked-non-file"
                if file_digest(source) == file_digest(target):
                    return "current"
                if is_managed_agent(target):
                    return "managed-stale-or-edited"
                return "blocked-unmanaged"
            if not target.is_dir():
                return "blocked-non-dir"
            if tree_digest(source) == tree_digest(target):
                return "current"
            if is_managed_skill(target):
                return "managed-stale-or-edited"
            return "blocked-unmanaged"


        def backup_path_for(path: Path) -> Path:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            base = path.with_name(f"{path.name}.bak-{stamp}")
            candidate = base
            counter = 1
            while candidate.exists():
                candidate = path.with_name(f"{path.name}.bak-{stamp}-{counter}")
                counter += 1
            return candidate


        def backup(path: Path) -> Path:
            backup_path = backup_path_for(path)
            if path.is_dir():
                shutil.copytree(path, backup_path)
            elif path.is_file():
                shutil.copy2(path, backup_path)
            else:
                raise RuntimeError(f"cannot back up unsupported path: {path}")
            return backup_path


        def remove_existing(path: Path) -> None:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()


        def copy_item(kind: str, source: Path, target: Path) -> None:
            target.parent.mkdir(parents=True, exist_ok=True)
            if kind == "agent":
                shutil.copy2(source, target)
            else:
                shutil.copytree(source, target)


        def bundled_items(plugin_root: Path, home: Path, skills_home: Path, *, agents_only: bool, skills_only: bool) -> list[tuple[str, Path, Path]]:
            items: list[tuple[str, Path, Path]] = []
            if not skills_only:
                agents_root = home / "agents"
                items.extend(
                    ("agent", source, agents_root / source.name)
                    for source in bundled_agents(plugin_root)
                )
            if not agents_only:
                items.extend(
                    ("skill", source, skills_home / source.name)
                    for source in bundled_skills(plugin_root)
                )
            return items


        def read_json(path: Path) -> dict:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                return {}
            return payload if isinstance(payload, dict) else {}


        def manifest_text(manifest: dict) -> str:
            interface = manifest.get("interface")
            interface = interface if isinstance(interface, dict) else {}
            values = [
                manifest.get("name"),
                manifest.get("description"),
                manifest.get("homepage"),
                manifest.get("repository"),
                interface.get("displayName"),
                interface.get("shortDescription"),
                interface.get("longDescription"),
            ]
            return " ".join(str(value) for value in values if value).lower()


        def is_endor_agent_kit_manifest(manifest: dict) -> bool:
            name = str(manifest.get("name") or "")
            if name in ENDOR_PLUGIN_CACHE_NAMES:
                return True
            text = manifest_text(manifest)
            return "endor" in text and "agent kit" in text


        def relative_display(path: Path, root: Path) -> str:
            try:
                return path.relative_to(root).as_posix()
            except ValueError:
                return str(path)


        def tree_or_file_matches(source: Path, cached: Path) -> bool:
            if source.is_dir():
                return cached.is_dir() and tree_digest(source) == tree_digest(cached)
            if source.is_file():
                return cached.is_file() and file_digest(source) == file_digest(cached)
            return not cached.exists()


        def plugin_cache_status(plugin_root: Path, cache_root: Path, manifest: dict) -> str:
            name = str(manifest.get("name") or "unknown")
            version = str(manifest.get("version") or "unknown")
            if name != CURRENT_PLUGIN_NAME:
                return (
                    f"stale-legacy-cache package={name} version={version} "
                    f"expected={CURRENT_PLUGIN_NAME}@{CURRENT_PLUGIN_VERSION}"
                )
            if version != CURRENT_PLUGIN_VERSION:
                return (
                    f"stale-version-cache package={name} version={version} "
                    f"expected={CURRENT_PLUGIN_VERSION}"
                )

            mismatches = []
            for relative in ("skills", "agents", ".codex-plugin/plugin.json"):
                source = plugin_root / relative
                cached = cache_root / relative
                if not tree_or_file_matches(source, cached):
                    mismatches.append(relative)
            if mismatches:
                return "stale-content-cache mismatched=" + ",".join(mismatches)
            return f"current package={name} version={version}"


        def report_plugin_cache_status(plugin_root: Path, home: Path) -> None:
            records = plugin_cache_records(plugin_root, home)
            reported = False
            for cache_root, status in records:
                print(f"plugin-cache:{relative_display(cache_root, home)}: {status}")
                if status.startswith("stale"):
                    print(
                        "  warning: Codex may load stale Endor Agent Kit instructions from "
                        f"{cache_root}. Remove/reinstall that plugin package or clear the "
                        "host cache, then start a fresh Codex thread. To move this cache "
                        "out of the active cache after approval, rerun this installer with "
                        "`--purge-stale-plugin-cache --yes`."
                    )
                reported = True
            if not reported:
                print("plugin-cache: none")


        def plugin_cache_records(plugin_root: Path, home: Path) -> list[tuple[Path, str]]:
            cache_base = home / "plugins" / "cache"
            records: list[tuple[Path, str]] = []
            for manifest_path in sorted(cache_base.glob("**/.codex-plugin/plugin.json")):
                manifest = read_json(manifest_path)
                if not is_endor_agent_kit_manifest(manifest):
                    continue
                cache_root = manifest_path.parents[1]
                records.append((cache_root, plugin_cache_status(plugin_root, cache_root, manifest)))
            return records


        def plugin_config_sections(config_path: Path) -> list[tuple[str, int, int, str]]:
            try:
                lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
            except (OSError, UnicodeDecodeError):
                return []
            sections: list[tuple[str, int, int, str]] = []
            for index, line in enumerate(lines):
                match = PLUGIN_TABLE_RE.match(line.strip())
                if match is None:
                    continue
                end = len(lines)
                for cursor in range(index + 1, len(lines)):
                    if lines[cursor].lstrip().startswith("["):
                        end = cursor
                        break
                enabled = "unknown"
                for entry in lines[index + 1:end]:
                    stripped = entry.strip()
                    if stripped.startswith("enabled") and "=" in stripped:
                        enabled = stripped.split("=", 1)[1].strip()
                        break
                sections.append((match.group("name"), index, end, enabled))
            return sections


        def stale_plugin_config_records(home: Path) -> list[tuple[Path, str, str]]:
            config_path = home / "config.toml"
            if not config_path.is_file():
                return []
            records: list[tuple[Path, str, str]] = []
            for plugin_id, _start, _end, enabled in plugin_config_sections(config_path):
                if plugin_id in LEGACY_CODEX_PLUGIN_IDS:
                    records.append((
                        config_path,
                        plugin_id,
                        f"stale-legacy-config enabled={enabled}",
                    ))
            return records


        def report_plugin_config_status(home: Path) -> None:
            records = stale_plugin_config_records(home)
            if not records:
                print("plugin-config: none")
                return
            for config_path, plugin_id, status in records:
                print(f"plugin-config:{relative_display(config_path, home)}:{plugin_id}: {status}")
                print(
                    "  warning: Codex may try to load this removed legacy Endor Agent Kit "
                    "plugin on every run. To remove the stale config entry after approval, "
                    "rerun this installer with `--purge-stale-plugin-cache --yes`."
                )


        def purge_stale_plugin_config(home: Path, *, yes: bool) -> None:
            config_path = home / "config.toml"
            sections = [
                (plugin_id, start, end)
                for plugin_id, start, end, _enabled in plugin_config_sections(config_path)
                if plugin_id in LEGACY_CODEX_PLUGIN_IDS
            ]
            if not sections:
                print("plugin-config: no stale Endor Agent Kit config entries")
                return
            plugin_ids = ", ".join(plugin_id for plugin_id, _start, _end in sections)
            if not yes:
                print(
                    f"plugin-config:{relative_display(config_path, home)}: "
                    f"would remove stale legacy entries {plugin_ids}; rerun with --yes after approval"
                )
                return
            backup_path = backup(config_path)
            lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
            keep = [True] * len(lines)
            for _plugin_id, start, end in sections:
                for index in range(start, end):
                    keep[index] = False
            config_path.write_text(
                "".join(line for line, include in zip(lines, keep) if include),
                encoding="utf-8",
            )
            print(f"plugin-config:{relative_display(config_path, home)}: removed stale legacy entries {plugin_ids}")
            print(f"  backed up Codex config to {backup_path}")


        def cache_backup_path(home: Path, cache_root: Path) -> Path:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            try:
                relative = cache_root.relative_to(home / "plugins" / "cache")
            except ValueError:
                relative = Path(cache_root.name)
            name = "-".join(relative.parts) + f".bak-{stamp}"
            base = home / "plugins" / "cache-backups" / name
            candidate = base
            counter = 1
            while candidate.exists():
                candidate = base.with_name(f"{base.name}-{counter}")
                counter += 1
            return candidate


        def purge_stale_plugin_cache(plugin_root: Path, home: Path, *, yes: bool) -> int:
            stale = [
                (cache_root, status)
                for cache_root, status in plugin_cache_records(plugin_root, home)
                if status.startswith("stale")
            ]
            stale_config = stale_plugin_config_records(home)
            if not stale and not stale_config:
                print("plugin-cache: no stale Endor Agent Kit caches")
                print("plugin-config: no stale Endor Agent Kit config entries")
                return 0
            if not stale:
                print("plugin-cache: no stale Endor Agent Kit caches")
            else:
                for cache_root, status in stale:
                    target = cache_backup_path(home, cache_root)
                    print(f"plugin-cache:{relative_display(cache_root, home)}: {status}")
                    if yes:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(cache_root), str(target))
                        print(f"  moved stale plugin cache to {target}")
                    else:
                        print(f"  would move stale plugin cache to {target}; rerun with --yes after approval")
            purge_stale_plugin_config(home, yes=yes)
            return 0


        def describe_block(kind: str, target: Path, status: str) -> str:
            if status == "blocked-non-file":
                return "blocked-non-file"
            if status == "blocked-non-dir":
                return "blocked-non-dir"
            return f"blocked unmanaged {kind}: {target}"


        def run(args: argparse.Namespace) -> int:
            plugin_root = Path(__file__).resolve().parents[1]
            home = codex_home(args.codex_home)
            skills_home = codex_skills_home(args.skills_home)
            if args.purge_stale_plugin_cache:
                return purge_stale_plugin_cache(plugin_root, home, yes=args.yes)
            items = bundled_items(
                plugin_root,
                home,
                skills_home,
                agents_only=args.agents_only,
                skills_only=args.skills_only,
            )
            if not items:
                print("ERROR: no bundled Codex agents or skills found for selected scope")
                return 1

            exit_code = 0
            for kind, source, target in items:
                status = item_status(kind, source, target)
                print(f"{kind}:{source.name}: {status}")

                if args.status:
                    continue

                if args.uninstall:
                    if status == "missing":
                        continue
                    if status.startswith("blocked"):
                        print(f"  refusing to remove {describe_block(kind, target, status)}")
                        exit_code = 1
                        continue
                    if args.yes:
                        backup_path = backup(target)
                        print(f"  backed up existing managed {kind} to {backup_path}")
                        remove_existing(target)
                        print(f"  removed {target}")
                    else:
                        print(f"  would back up and remove {target}; rerun with --yes after approval")
                    continue

                if args.install:
                    if status == "current":
                        continue
                    if status.startswith("blocked"):
                        print(f"  refusing to overwrite {describe_block(kind, target, status)}")
                        exit_code = 1
                        continue
                    if args.yes:
                        if target.exists():
                            backup_path = backup(target)
                            print(f"  backed up existing managed {kind} to {backup_path}")
                            remove_existing(target)
                        copy_item(kind, source, target)
                        print(f"  installed {target}")
                    else:
                        print(f"  would install/update {target}; rerun with --yes after approval")
            if args.status and not args.agents_only and not args.skills_only:
                report_plugin_cache_status(plugin_root, home)
                report_plugin_config_status(home)
            return exit_code


        def main(argv: list[str] | None = None) -> int:
            parser = argparse.ArgumentParser(prog="install_codex_agents.py")
            action = parser.add_mutually_exclusive_group()
            action.add_argument("--status", action="store_true", help="Report installed agent and skill status")
            action.add_argument("--install", action="store_true", help="Install or update bundled agents and skills")
            action.add_argument("--uninstall", action="store_true", help="Remove managed installed agents and skills")
            action.add_argument("--purge-stale-plugin-cache", action="store_true", help="Move stale Endor Agent Kit plugin-cache directories and remove stale plugin config entries")
            scope = parser.add_mutually_exclusive_group()
            scope.add_argument("--agents-only", action="store_true", help="Limit action to bundled Codex custom agents")
            scope.add_argument("--skills-only", action="store_true", help="Limit action to bundled Codex skills")
            parser.add_argument("--codex-home", help="Override CODEX_HOME")
            parser.add_argument("--skills-home", help="Override Codex user skills directory")
            parser.add_argument("--yes", action="store_true", help="Apply install/update/uninstall actions")
            args = parser.parse_args(argv)
            if not (args.status or args.install or args.uninstall or args.purge_stale_plugin_cache):
                args.status = True
            return run(args)


        if __name__ == "__main__":
            raise SystemExit(main())
        '''
    ).lstrip()
    return (
        script
        .replace("__ENDOR_AGENT_KIT_PLUGIN_NAME__", PLUGIN_NAME)
        .replace("__ENDOR_AGENT_KIT_PLUGIN_VERSION__", version)
    )
