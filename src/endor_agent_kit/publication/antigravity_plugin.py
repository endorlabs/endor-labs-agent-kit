"""Antigravity CLI plugin package publication."""

from __future__ import annotations

from dataclasses import dataclass
import json
import shutil
from pathlib import Path

from endor_agent_kit.catalog_schema import CatalogPluginPackage
from endor_agent_kit.compilers.gemini import (
    HOST as GEMINI_HOST,
    render_gemini_agent,
    render_gemini_skill,
)
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

ANTIGRAVITY_HOST = "antigravity"
ANTIGRAVITY_PLUGIN_PACKAGE_ROOT = Path("plugins") / ANTIGRAVITY_HOST / PLUGIN_NAME
ANTIGRAVITY_SETUP_SKILL = "endor-agent-kit-setup"


@dataclass(frozen=True)
class PluginPackagePublication:
    """Result of publishing one generated plugin package."""

    package_record: CatalogPluginPackage
    written: tuple[Path, ...]


def publish_antigravity_plugin_package(
    prepared_recipes: list[PreparedSourceRecipe],
    destination: Path,
) -> PluginPackagePublication | None:
    """Publish the generated Antigravity CLI plugin package."""

    antigravity_recipes = [
        prepared
        for prepared in prepared_recipes
        if GEMINI_HOST in prepared.recipe.compatible_hosts
    ]
    if not antigravity_recipes:
        return None

    package_dir = destination / ANTIGRAVITY_PLUGIN_PACKAGE_ROOT
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True)
    (package_dir / "skills").mkdir()
    (package_dir / "agents").mkdir()
    (package_dir / "assets").mkdir()

    written: list[Path] = []
    version = package_version()
    sorted_recipes = sorted(antigravity_recipes, key=lambda item: item.recipe.id)

    for prepared in sorted_recipes:
        skill_dir = package_dir / "skills" / prepared.recipe.id
        skill_dir.mkdir(parents=True)
        skill = skill_dir / "SKILL.md"
        skill.write_text(
            antigravity_text(
                render_gemini_skill(
                    prepared,
                    generated_context="Endor Labs Agent Kit Antigravity CLI plugin",
                    compact_plugin=True,
                )
            ),
            encoding="utf-8",
        )
        written.append(skill)

        agent = package_dir / "agents" / f"{prepared.recipe.id}.md"
        agent.write_text(
            antigravity_text(
                render_gemini_agent(
                    prepared,
                    generated_context="Endor Labs Agent Kit Antigravity CLI plugin subagent",
                    compact_plugin=True,
                )
            ),
            encoding="utf-8",
        )
        written.append(agent)

    setup_skill_dir = package_dir / "skills" / ANTIGRAVITY_SETUP_SKILL
    setup_skill_dir.mkdir(parents=True)
    setup_skill = setup_skill_dir / "SKILL.md"
    setup_skill.write_text(_render_setup_skill(sorted_recipes), encoding="utf-8")
    written.append(setup_skill)

    logo = package_dir / "assets" / "logo.svg"
    logo.write_text(logo_svg(), encoding="utf-8")
    written.append(logo)

    manifest = package_dir / "plugin.json"
    manifest.write_text(
        json.dumps(_antigravity_plugin_manifest(version), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    written.append(manifest)

    readme = package_dir / "README.md"
    readme.write_text(_antigravity_plugin_readme(sorted_recipes, version), encoding="utf-8")
    written.append(readme)

    plugins_readme = destination / "plugins" / "README.md"
    plugins_readme.write_text(plugin_packages_readme(), encoding="utf-8")
    written.append(plugins_readme)

    package_record = CatalogPluginPackage.from_published_package(
        destination,
        host=ANTIGRAVITY_HOST,
        name=PLUGIN_NAME,
        display_name=PLUGIN_DISPLAY_NAME,
        version=version,
        package_dir=package_dir,
        included_agents=tuple(prepared.recipe.id for prepared in sorted_recipes),
        extra_artifacts=(plugins_readme,),
    )
    return PluginPackagePublication(package_record=package_record, written=tuple(written))


def _antigravity_plugin_manifest(version: str) -> dict[str, object]:
    return {
        "name": PLUGIN_NAME,
        "version": version,
        "description": "Endor Labs workflow skills and subagents for Antigravity CLI.",
        "short_description": "Endor Labs security workflows for Antigravity.",
        "long_description": (
            "Setup guidance, workflow skills, and subagents for Endor Labs SCA "
            "remediation, AI SAST triage, troubleshooting, and onboarding analysis."
        ),
        "author": {
            "name": "Endor Labs",
            "url": "https://www.endorlabs.com/",
        },
        "repository": "https://github.com/endorlabs/ai-plugins",
        "homepage": "https://github.com/endorlabs/ai-plugins",
        "keywords": [
            "Endor Labs",
            "AppSec",
            "agentic AppSec",
            "agentic remediation",
            "SAST remediation",
            "Upgrade Impact Analysis",
            "SCA remediation",
            "software composition analysis",
        ],
    }


def _render_setup_skill(prepared_recipes: list[PreparedSourceRecipe]) -> str:
    setup_source = _setup_source(prepared_recipes)
    workflow_lines = [
        f"- `{_workflow_label(prepared.recipe.id)}` -> skill `{prepared.recipe.id}`, subagent `@{prepared.recipe.id}`"
        for prepared in prepared_recipes
    ]
    return "\n".join([
        "---",
        f"name: {ANTIGRAVITY_SETUP_SKILL}",
        "description: Use when setting up Endor Labs Agent Kit for Antigravity CLI, checking readiness, verifying Endor auth, choosing namespaces, or diagnosing missing endorctl, gh, Antigravity CLI, Endor MCP, or workflow prerequisites.",
        "---",
        "",
        "# Endor Agent Kit Setup For Antigravity CLI",
        "",
        "Generated for the Endor Labs Agent Kit Antigravity CLI plugin.",
        "",
        "## Bundled Antigravity CLI Workflows",
        "",
        *workflow_lines,
        "",
        "## Antigravity CLI Plugin Commands",
        "",
        "Validate and install from the generated local plugin package:",
        "",
        "```bash",
        f"antigravity plugin validate /path/to/endor-labs-agent-kit/{ANTIGRAVITY_PLUGIN_PACKAGE_ROOT.as_posix()}",
        f"antigravity plugin install /path/to/endor-labs-agent-kit/{ANTIGRAVITY_PLUGIN_PACKAGE_ROOT.as_posix()}",
        "antigravity plugin list",
        "```",
        "",
        "Remove the plugin only after explicit user approval:",
        "",
        "```bash",
        f"antigravity plugin uninstall {PLUGIN_NAME}",
        "```",
        "",
        "Antigravity CLI is the consumer migration path for Gemini CLI. Keep Gemini",
        "extension installation and Antigravity plugin installation as separate",
        "host-specific choices, and validate the selected package before installing.",
        "",
        setup_source.rstrip(),
        "",
        "## Antigravity-Specific Rules",
        "",
        "- Keep Antigravity plugin installs explicit. Do not install, link, update, enable, disable, or uninstall plugins without user approval.",
        "- Do not add plugin-wide MCP automatically. Only guide MCP setup when a selected workflow needs it and the user approves.",
        "- Do not collect, write, or persist Endor API credential values. Report credential presence by key name only.",
        "- Invoke bundled subagents as `@agent-name` when delegating a workflow; do not invent alternate invocation names.",
        "- Do not narrate tool-planning chatter. Return the requested evidence, decisions, and gaps.",
        "- When required Endor evidence is unavailable, include `evidence_queries` and non-empty `data_gaps` instead of guessing.",
        "- Antigravity subagents are host-managed; if subagent delegation is unavailable, use the matching skill and report the limitation.",
        "- Tell the user to restart Antigravity CLI after installing or updating the plugin if newly installed skills or subagents are not visible.",
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


def _antigravity_plugin_readme(
    prepared_recipes: list[PreparedSourceRecipe],
    version: str,
) -> str:
    rows = [
        f"| {_workflow_label(prepared.recipe.id)} | `{prepared.recipe.id}` | `@{prepared.recipe.id}` | {_workflow_safety(prepared)} |"
        for prepared in prepared_recipes
    ]
    start_here = plugin_readme_start_here(
        host_label="Antigravity CLI",
        install_summary="Validate and install the generated Antigravity plugin directory with `antigravity plugin` commands.",
        setup_summary=f"ask Antigravity CLI to use the `{ANTIGRAVITY_SETUP_SKILL}` skill.",
    )
    return "\n".join([
        "# Endor Labs Agent Kit Antigravity CLI Plugin",
        "",
        "<!-- Generated by Endor Labs Agent Kit. Do not hand-edit. -->",
        "",
        f"Version: `{version}`",
        "",
        "This generated Antigravity CLI plugin package includes Endor Labs setup",
        "support, Antigravity Agent Skills, and Antigravity subagents generated",
        "from source recipes in the Endor Labs Agent Kit repository.",
        "",
        *start_here,
        "## Host Metadata",
        "",
        "- Manifest: `plugin.json`.",
        "- Skills: `skills/<agent>/SKILL.md`, including `endor-agent-kit-setup`.",
        "- Subagents: `agents/<agent>.md`.",
        "- Model/runtime: generated skills and subagents inherit Antigravity CLI defaults; the plugin does not set a plugin-wide default model.",
        "- MCP: no plugin-wide MCP server is declared by default.",
        "",
        "## Install From A Local Checkout",
        "",
        "```bash",
        f"antigravity plugin validate /path/to/endor-labs-agent-kit/{ANTIGRAVITY_PLUGIN_PACKAGE_ROOT.as_posix()}",
        f"antigravity plugin install /path/to/endor-labs-agent-kit/{ANTIGRAVITY_PLUGIN_PACKAGE_ROOT.as_posix()}",
        "antigravity plugin list",
        "```",
        "",
        "Restart Antigravity CLI after installing or reinstalling the plugin if",
        "the newly installed skills or subagents are not visible.",
        "If Antigravity still shows stale same-version content, uninstall and",
        "reinstall the plugin directory, validate the package again, and start a",
        "fresh Antigravity CLI session so host caches reload the generated prompts.",
        "",
        "## Set Up This Machine",
        "",
        "Ask Antigravity CLI:",
        "",
        "```text",
        f"Use the {ANTIGRAVITY_SETUP_SKILL} skill to check Endor Agent Kit readiness.",
        "```",
        "",
        "The setup skill can guide package-manager-first `endorctl` installation,",
        "verify Endor auth and namespace readiness, and report missing `gh` or",
        "toolchain prerequisites. It does not run scans, run `endorctl host-check`,",
        "edit shell profiles, auto-install `gh`, or install language runtimes and",
        "package managers.",
        "",
        "## Capabilities And Skills",
        "",
        "| Job | Antigravity skill | Antigravity subagent | Safety |",
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
        "- Invoke workflow subagents as `@agent-name`, for example `@sca-remediation`.",
        "- Do not narrate tool-planning chatter; return the workflow result, evidence, and precise gaps.",
        "- Include `evidence_queries` and non-empty `data_gaps` whenever required Endor evidence is missing.",
        "- Always keep setup, file edits, branch pushes, PR/MR creation, comments, tickets, and policy writes as separate evidence-backed steps.",
        "- Never run setup scans or `endorctl host-check`.",
        "- Never auto-install `gh`, language runtimes, or package managers in v1.",
        "- Never print, persist, or copy Endor API key, secret, token, or full config values.",
        "",
        "## Provider Docs",
        "",
        "- https://antigravity.google/docs/cli-plugins",
        "- https://antigravity.google/docs/gcli-migration",
        "- https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/",
        "",
    ])


def antigravity_text(text: str) -> str:
    """Adapt Gemini-rendered package text for Antigravity CLI wording."""

    adapted = (
        text.replace("Gemini CLI extension subagent", "Antigravity CLI plugin subagent")
        .replace("Gemini CLI extension", "Antigravity CLI plugin")
        .replace("Gemini CLI Host Contract", "Antigravity CLI Host Contract")
        .replace("Gemini CLI subagent", "Antigravity CLI subagent")
        .replace("Gemini CLI skill", "Antigravity CLI skill")
        .replace("Gemini CLI workspace", "Antigravity CLI workspace")
        .replace("Gemini CLI artifact", "Antigravity CLI artifact")
        .replace("Gemini CLI session", "Antigravity CLI session")
        .replace("Gemini CLI runs", "Antigravity CLI runs")
        .replace("Gemini CLI performed", "Antigravity CLI performed")
        .replace("Gemini CLI file and shell tools", "Antigravity CLI file and shell tools")
        .replace("Gemini subagent", "Antigravity subagent")
        .replace("Gemini-specific", "Antigravity-specific")
        .replace("host=gemini", "host=antigravity")
        .replace("Gemini CLI", "Antigravity CLI")
    )
    host_contract = "Antigravity CLI Host Contract\n"
    if host_contract in adapted and "Invoke workflow subagents as `@agent-name`" not in adapted:
        adapted = adapted.replace(
            host_contract,
            host_contract
            + "\n"
            + "- Invoke workflow subagents as `@agent-name`; do not invent alternate invocation names.\n"
            + "- Do not narrate tool-planning chatter. Return the requested evidence, decisions, and gaps.\n"
            + "- Include `evidence_queries` and non-empty `data_gaps` when required Endor evidence is missing.\n",
            1,
        )
    return adapted


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
