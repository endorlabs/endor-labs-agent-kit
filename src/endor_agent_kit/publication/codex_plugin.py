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
CODEX_AGENT_SUFFIX = "-agent"
CODEX_SECTION_EDITION = "enterprise-edition"


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
            ),
            encoding="utf-8",
        )
        written.append(skill)

        agent = package_dir / "agents" / f"{_codex_agent_name(prepared.recipe.id)}.toml"
        agent.write_text(_render_codex_agent_toml(prepared), encoding="utf-8")
        written.append(agent)

    setup_skill_dir = package_dir / "skills" / CODEX_SETUP_SKILL
    setup_skill_dir.mkdir(parents=True)
    setup_skill = setup_skill_dir / "SKILL.md"
    setup_skill.write_text(_render_setup_skill(sorted_recipes), encoding="utf-8")
    written.append(setup_skill)

    installer = package_dir / "scripts" / "install_codex_agents.py"
    installer.write_text(_codex_agent_installer_script(), encoding="utf-8")
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


def _render_codex_agent_toml(prepared: PreparedSourceRecipe) -> str:
    recipe = prepared.recipe
    posture = source_recipe_safety_posture(recipe)
    skill_text = render_codex_skill(
        prepared,
        generated_context="Endor Labs Agent Kit Codex custom agent",
    )
    body = _strip_frontmatter(skill_text)
    body += dedent(
        f"""

        ## Codex Custom Agent Setup Note

        This custom agent is installed from the Endor Labs Agent Kit Codex plugin.
        If `endorctl`, `gh`, Endor authentication, namespace selection, or
        workflow-specific tooling is missing, ask the user to run the
        `{CODEX_SETUP_SKILL}` skill before continuing live Endor work.
        """
    )
    lines = [
        "# Generated by Endor Labs Agent Kit. Do not hand-edit installed copies.",
        "# endor_agent_kit_managed = true",
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


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _strip_frontmatter(markdown: str) -> str:
    parts = markdown.split("---", 2)
    if len(parts) == 3 and not parts[0].strip():
        return parts[2].lstrip()
    return markdown


def _single_line(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _render_setup_skill(prepared_recipes: list[PreparedSourceRecipe]) -> str:
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
        "# Endor Agent Kit Setup For Codex",
        "",
        "Generated for the Endor Labs Agent Kit Codex plugin.",
        "",
        "## Bundled Codex Custom Agents",
        "",
        *workflow_lines,
        "",
        "## Codex Agent Install Commands",
        "",
        "Check installed Endor Codex agents:",
        "",
        "```bash",
        "python scripts/install_codex_agents.py --status",
        "```",
        "",
        "Install or update all bundled Endor Codex agents after user approval:",
        "",
        "```bash",
        "python scripts/install_codex_agents.py --install --yes",
        "```",
        "",
        "Uninstall only Endor Agent Kit-managed Codex agents after user approval:",
        "",
        "```bash",
        "python scripts/install_codex_agents.py --uninstall --yes",
        "```",
        "",
        setup_source.rstrip(),
        "",
        "## Codex-Specific Rules",
        "",
        "- Install Codex custom agents globally by default under `${CODEX_HOME:-~/.codex}/agents`.",
        "- Do not write project-local `.codex/agents/` files unless the user explicitly requests that advanced option.",
        "- Use provenance-gated updates: missing files may be installed; managed stale files may be updated after approval; unknown files must not be overwritten.",
        "- Tell the user to start a new Codex thread after installing or updating custom agents.",
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
        "- Custom agents: `agents/endor-*-agent.toml`, installed by the setup skill only after approval.",
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
        "",
        "## Set Up This Machine",
        "",
        "Ask Codex:",
        "",
        "```text",
        "Use the endor-agent-kit-setup skill to check readiness and install the bundled Codex custom agents.",
        "```",
        "",
        "The setup skill can install or update managed Endor Codex custom agents",
        "under `${CODEX_HOME:-~/.codex}/agents` after explicit approval. It does",
        "not run scans, run `endorctl host-check`, edit shell profiles, install",
        "`gh`, or install language runtimes and package managers.",
        "",
        "## Capabilities And Skills",
        "",
        "| Job | Codex skill | Codex custom agent | Safety |",
        "| --- | --- | --- | --- |",
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
        "`${CODEX_HOME:-~/.codex}/skills/<agent>`.",
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


def _codex_agent_installer_script() -> str:
    return dedent(
        r'''
        #!/usr/bin/env python3
        """Install, update, inspect, or uninstall Endor Agent Kit Codex agents."""

        from __future__ import annotations

        import argparse
        import hashlib
        import os
        from pathlib import Path
        import shutil
        import sys
        from datetime import datetime, timezone

        MANAGED_MARKER = "# endor_agent_kit_managed = true"


        def sha256(path: Path) -> str:
            digest = hashlib.sha256()
            digest.update(path.read_bytes())
            return digest.hexdigest()


        def codex_home(value: str | None) -> Path:
            if value:
                return Path(value).expanduser()
            return Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()


        def bundled_agents(plugin_root: Path) -> list[Path]:
            return sorted((plugin_root / "agents").glob("*.toml"))


        def is_managed(path: Path) -> bool:
            if not path.is_file():
                return False
            try:
                return MANAGED_MARKER in path.read_text(encoding="utf-8").splitlines()[:12]
            except UnicodeDecodeError:
                return False


        def status(source: Path, target: Path) -> str:
            if not target.exists():
                return "missing"
            if not target.is_file():
                return "blocked-non-file"
            if sha256(source) == sha256(target):
                return "current"
            if is_managed(target):
                return "managed-stale-or-edited"
            return "blocked-unmanaged"


        def backup(path: Path) -> Path:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup_path = path.with_suffix(path.suffix + f".bak-{stamp}")
            shutil.copy2(path, backup_path)
            return backup_path


        def run(args: argparse.Namespace) -> int:
            plugin_root = Path(__file__).resolve().parents[1]
            target_root = codex_home(args.codex_home) / "agents"
            sources = bundled_agents(plugin_root)
            if not sources:
                print("ERROR: no bundled agents found")
                return 1

            exit_code = 0
            for source in sources:
                target = target_root / source.name
                item_status = status(source, target)
                print(f"{source.name}: {item_status}")

                if args.status:
                    continue

                if args.uninstall:
                    if item_status == "missing":
                        continue
                    if not is_managed(target):
                        print(f"  refusing to remove unmanaged file: {target}")
                        exit_code = 1
                        continue
                    if args.yes:
                        target.unlink()
                        print(f"  removed {target}")
                    else:
                        print(f"  would remove {target}; rerun with --yes after approval")
                    continue

                if args.install:
                    if item_status == "current":
                        continue
                    if item_status == "blocked-non-file":
                        print(f"  refusing to replace non-file path: {target}")
                        exit_code = 1
                        continue
                    if item_status == "blocked-unmanaged":
                        print(f"  refusing to overwrite unmanaged file: {target}")
                        exit_code = 1
                        continue
                    if args.yes:
                        target_root.mkdir(parents=True, exist_ok=True)
                        if target.exists():
                            backup_path = backup(target)
                            print(f"  backed up existing managed file to {backup_path}")
                        shutil.copy2(source, target)
                        print(f"  installed {target}")
                    else:
                        print(f"  would install/update {target}; rerun with --yes after approval")
            return exit_code


        def main(argv: list[str] | None = None) -> int:
            parser = argparse.ArgumentParser(prog="install_codex_agents.py")
            action = parser.add_mutually_exclusive_group()
            action.add_argument("--status", action="store_true", help="Report installed agent status")
            action.add_argument("--install", action="store_true", help="Install or update bundled agents")
            action.add_argument("--uninstall", action="store_true", help="Remove managed installed agents")
            parser.add_argument("--codex-home", help="Override CODEX_HOME")
            parser.add_argument("--yes", action="store_true", help="Apply install/update/uninstall actions")
            args = parser.parse_args(argv)
            if not (args.status or args.install or args.uninstall):
                args.status = True
            return run(args)


        if __name__ == "__main__":
            raise SystemExit(main())
        '''
    ).lstrip()
