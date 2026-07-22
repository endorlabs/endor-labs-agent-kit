"""Gemini CLI extension package publication."""

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
    package_version,
    plugin_readme_start_here,
    plugin_packages_readme,
    write_logo,
)
from endor_agent_kit.safety_posture import source_recipe_safety_posture
from endor_agent_kit.publication.runtime_support import write_artifact_summarizer

GEMINI_PLUGIN_PACKAGE_ROOT = Path("plugins") / "gemini" / PLUGIN_NAME
GEMINI_SETUP_SKILL = "endor-agent-kit-setup"
PUBLIC_GEMINI_DISTRIBUTION_REPOSITORY = "https://github.com/endorlabs/ai-plugins"
GEMINI_HOOK_SOURCE_DIR = Path("source") / "plugin-support" / "hooks" / "claude"
GEMINI_HOOK_FILENAMES = (
    "suggest-endor-tools.sh",
    "check-dep-install.sh",
    "check-manifest-edit.sh",
)


def _public_gemini_install_lines(ref: str) -> list[str]:
    return [
        f"git clone --depth 1 --branch {ref} {PUBLIC_GEMINI_DISTRIBUTION_REPOSITORY} ai-plugins",
        "gemini extensions install ./ai-plugins/plugins/gemini/endor-labs-agent-kit",
    ]


@dataclass(frozen=True)
class PluginPackagePublication:
    """Result of publishing one generated plugin package."""

    package_record: CatalogPluginPackage
    written: tuple[Path, ...]


def publish_gemini_plugin_package(
    prepared_recipes: list[PreparedSourceRecipe],
    destination: Path,
) -> PluginPackagePublication | None:
    """Publish the generated Gemini CLI extension package."""

    gemini_recipes = [
        prepared
        for prepared in prepared_recipes
        if GEMINI_HOST in prepared.recipe.compatible_hosts
    ]
    if not gemini_recipes:
        return None

    package_dir = destination / GEMINI_PLUGIN_PACKAGE_ROOT
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True)
    (package_dir / "skills").mkdir()
    (package_dir / "agents").mkdir()
    (package_dir / "assets").mkdir()
    (package_dir / "hooks").mkdir()

    written: list[Path] = []
    version = package_version()
    sorted_recipes = sorted(gemini_recipes, key=lambda item: item.recipe.id)

    for prepared in sorted_recipes:
        skill_dir = package_dir / "skills" / prepared.recipe.id
        skill_dir.mkdir(parents=True)
        skill = skill_dir / "SKILL.md"
        skill.write_text(
            render_gemini_skill(
                prepared,
                generated_context="Endor Labs Agent Kit Gemini CLI extension",
                compact_plugin=True,
            ),
            encoding="utf-8",
        )
        written.append(skill)

        agent = package_dir / "agents" / f"{prepared.recipe.id}.md"
        agent.write_text(
            render_gemini_agent(
                prepared,
                generated_context="Endor Labs Agent Kit Gemini CLI extension subagent",
                compact_plugin=True,
            ),
            encoding="utf-8",
        )
        written.append(agent)

    setup_skill_dir = package_dir / "skills" / GEMINI_SETUP_SKILL
    setup_skill_dir.mkdir(parents=True)
    setup_skill = setup_skill_dir / "SKILL.md"
    setup_skill.write_text(_render_setup_skill(sorted_recipes), encoding="utf-8")
    written.append(setup_skill)

    gemini_context = package_dir / "GEMINI.md"
    gemini_context.write_text(_gemini_context(sorted_recipes), encoding="utf-8")
    written.append(gemini_context)

    logo = write_logo(package_dir / "assets")
    written.append(logo)

    written.append(write_artifact_summarizer(package_dir))

    written.extend(_write_gemini_extension_hooks(package_dir))

    manifest = package_dir / "gemini-extension.json"
    manifest.write_text(
        json.dumps(_gemini_extension_manifest(version), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    written.append(manifest)

    readme = package_dir / "README.md"
    readme.write_text(_gemini_plugin_readme(sorted_recipes, version), encoding="utf-8")
    written.append(readme)

    plugins_readme = destination / "plugins" / "README.md"
    plugins_readme.write_text(plugin_packages_readme(), encoding="utf-8")
    written.append(plugins_readme)

    package_record = CatalogPluginPackage.from_published_package(
        destination,
        host=GEMINI_HOST,
        name=PLUGIN_NAME,
        display_name=PLUGIN_DISPLAY_NAME,
        version=version,
        package_dir=package_dir,
        included_agents=tuple(prepared.recipe.id for prepared in sorted_recipes),
        extra_artifacts=(plugins_readme,),
    )
    return PluginPackagePublication(package_record=package_record, written=tuple(written))


def _write_gemini_extension_hooks(package_dir: Path) -> tuple[Path, ...]:
    source_dir = _hook_source()
    hooks_dir = package_dir / "hooks"
    written: list[Path] = []
    for filename in GEMINI_HOOK_FILENAMES:
        source = source_dir / filename
        target = hooks_dir / filename
        shutil.copy2(source, target)
        written.append(target)
    hooks_json = hooks_dir / "hooks.json"
    hooks_json.write_text(
        json.dumps(_gemini_hooks_config(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    written.append(hooks_json)
    return tuple(written)


def _hook_source() -> Path:
    candidates = [
        Path(__file__).resolve().parents[3] / GEMINI_HOOK_SOURCE_DIR,
        Path.cwd() / GEMINI_HOOK_SOURCE_DIR,
    ]
    for candidate in candidates:
        if candidate.is_dir():
            missing = [
                filename
                for filename in GEMINI_HOOK_FILENAMES
                if not (candidate / filename).is_file()
            ]
            if missing:
                raise FileNotFoundError(
                    f"{candidate}: missing Gemini hook source files {missing}"
                )
            return candidate
    raise FileNotFoundError(GEMINI_HOOK_SOURCE_DIR.as_posix())


def _gemini_hooks_config() -> dict[str, object]:
    def command(filename: str, event_name: str, name: str) -> dict[str, object]:
        return {
            "type": "command",
            "command": f"bash ./hooks/{filename} {event_name}",
            "name": name,
            "timeout": 10,
        }

    return {
        "hooks": {
            "BeforeAgent": [
                {
                    "matcher": "",
                    "hooks": [
                        command(
                            "suggest-endor-tools.sh",
                            "BeforeAgent",
                            "endor-agent-kit-route-prompt",
                        )
                    ],
                }
            ],
            "BeforeTool": [
                {
                    "matcher": "run_shell_command",
                    "hooks": [
                        command(
                            "check-dep-install.sh",
                            "BeforeTool",
                            "endor-agent-kit-dependency-install-advisory",
                        )
                    ],
                }
            ],
            "AfterTool": [
                {
                    "matcher": "write_file|replace",
                    "hooks": [
                        command(
                            "check-manifest-edit.sh",
                            "AfterTool",
                            "endor-agent-kit-manifest-edit-advisory",
                        )
                    ],
                }
            ],
        }
    }


def _gemini_extension_manifest(version: str) -> dict[str, object]:
    return {
        "name": PLUGIN_NAME,
        "version": version,
        "description": "Endor Labs workflow skills and subagents for Gemini CLI.",
        "contextFileName": "GEMINI.md",
    }


def _render_setup_skill(prepared_recipes: list[PreparedSourceRecipe]) -> str:
    setup_source = _setup_source(prepared_recipes)
    workflow_lines = [
        f"- `{prepared.recipe.name}` -> skill `{prepared.recipe.id}`, subagent `@{prepared.recipe.id}`"
        for prepared in prepared_recipes
    ]
    return "\n".join([
        "---",
        f"name: {GEMINI_SETUP_SKILL}",
        "description: Use when setting up Endor Labs Agent Kit for Gemini CLI, checking readiness, verifying Endor auth, choosing namespaces, or diagnosing missing endorctl, gh, Gemini CLI, Endor MCP, or workflow prerequisites.",
        "---",
        "",
        "# Endor Agent Kit Setup For Gemini CLI",
        "",
        "Generated for the Endor Labs Agent Kit Gemini CLI extension.",
        "",
        "## Bundled Gemini CLI Workflows",
        "",
        *workflow_lines,
        "",
        "## Gemini CLI Extension Install Commands",
        "",
        "Install from the generated local extension package:",
        "",
        "```bash",
        f"gemini extensions install /path/to/endor-labs-agent-kit/{GEMINI_PLUGIN_PACKAGE_ROOT.as_posix()}",
        "```",
        "",
        "Install from the public GitHub repository after a release tag is published:",
        "",
        "```bash",
        *_public_gemini_install_lines("<tag>"),
        "```",
        "",
        "Observed local validation on Gemini CLI 0.44.1: local installs may still",
        "show a folder trust prompt even when `--consent` is supplied. Inspect the",
        "extension package, approve only the expected Agent Kit folder,",
        "then restart Gemini CLI so skills and subagents become visible.",
        "",
        "Google documents Antigravity CLI as the consumer transition path for",
        "Gemini CLI. If your Gemini CLI account is affected by that transition,",
        "use the Antigravity package instead; keep this Gemini extension for",
        "supported Gemini CLI environments and compatibility checks.",
        "",
        "Do not create or install zip archives for Gemini CLI; use the local extension",
        "directory for local testing and clone the tagged GitHub repository before",
        "installing the generated extension directory for release installs.",
        "",
        setup_source.rstrip(),
        "",
        "## Gemini-Specific Rules",
        "",
        "- Keep Gemini extension installs explicit. Do not install, link, update, or uninstall extensions without user approval.",
        "- Do not add plugin-wide MCP automatically. Only guide MCP setup when a selected workflow needs it and the user approves.",
        "- Do not collect, write, or persist Endor API credential values. Report credential presence by key name only.",
        "- Gemini subagents are preview functionality; if subagent delegation is unavailable, use the matching skill and report the limitation.",
        "- Tell the user to restart Gemini CLI after installing or updating the extension.",
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


def _gemini_context(prepared_recipes: list[PreparedSourceRecipe]) -> str:
    rows = [
        f"- {prepared.recipe.name}: use skill `{prepared.recipe.id}` or subagent `@{prepared.recipe.id}`."
        for prepared in prepared_recipes
    ]
    return "\n".join([
        "# Endor Labs Agent Kit For Gemini CLI",
        "",
        "Use Endor Labs Agent Kit workflows only within their generated safety",
        "contracts. If setup, authentication, namespace, Endor MCP, `endorctl`,",
        "`gh`, or repository tooling is missing, use the `endor-agent-kit-setup`",
        "skill before live Endor work.",
        "",
        "User jobs mapped to installed workflows:",
        "",
        *rows,
        "",
        "Setup must not run scans, run `endorctl host-check`, edit shell profiles,",
        "auto-install `gh`, install language tooling, or collect/write API secrets.",
        "",
    ])


def _gemini_plugin_readme(
    prepared_recipes: list[PreparedSourceRecipe],
    version: str,
) -> str:
    rows = [
        f"| {prepared.recipe.name} | `{prepared.recipe.id}` | `@{prepared.recipe.id}` | {_workflow_safety(prepared)} |"
        for prepared in prepared_recipes
    ]
    start_here = plugin_readme_start_here(
        host_label="Gemini CLI",
        install_summary="Install the generated extension directory locally or the tagged public GitHub repository.",
        setup_summary=f"ask Gemini CLI to use the `{GEMINI_SETUP_SKILL}` skill.",
    )
    return "\n".join([
        "# Endor Labs Agent Kit Gemini CLI Extension",
        "",
        "<!-- Generated by Endor Labs Agent Kit. Do not hand-edit. -->",
        "",
        f"Version: `{version}`",
        "",
        "This generated Gemini CLI extension package includes Endor Labs setup",
        "support, Gemini Agent Skills, and preview Gemini subagents generated from",
        "source recipes in the Endor Labs Agent Kit repository.",
        "",
        *start_here,
        "## Host Metadata",
        "",
        "- Manifest: `gemini-extension.json`.",
        "- Context: `GEMINI.md`, loaded through the manifest `contextFileName` field.",
        "- Skills: `skills/<agent>/SKILL.md`, including `endor-agent-kit-setup`.",
        "- Preview subagents: `agents/<agent>.md`.",
        "- Hooks: `hooks/hooks.json` plus fail-open advisory scripts for prompt routing, dependency installs, and manifest edits.",
        "- Model/runtime: generated skills and subagents inherit Gemini CLI defaults; the extension does not set a plugin-wide default model.",
        "- MCP: no extension-wide MCP server is declared by default.",
        "",
        "## Install From A Local Checkout",
        "",
        "```bash",
        f"gemini extensions install /path/to/endor-labs-agent-kit/{GEMINI_PLUGIN_PACKAGE_ROOT.as_posix()}",
        "```",
        "",
        "Install from the public GitHub repository after a release tag is published:",
        "",
        "```bash",
        *_public_gemini_install_lines("<tag>"),
        "```",
        "",
        "Gemini CLI 0.44.1 local validation showed a folder trust prompt for local",
        "paths even with `--consent`. Inspect the package and approve only the",
        "expected Endor Agent Kit extension source.",
        "",
        "Google documents Antigravity CLI as the consumer transition path for",
        "Gemini CLI. If your Gemini CLI account is affected by that transition,",
        "use the Antigravity package instead; keep this Gemini extension for",
        "supported Gemini CLI environments and compatibility checks.",
        "",
        "Do not create or install zip archives for Gemini CLI; use the local extension",
        "directory for local testing and clone the tagged GitHub repository before",
        "installing the generated extension directory for published installs.",
        "",
        "Restart Gemini CLI after installing or reinstalling the extension.",
        "",
        "## Set Up This Machine",
        "",
        "Ask Gemini CLI:",
        "",
        "```text",
        f"Use the {GEMINI_SETUP_SKILL} skill to check Endor Agent Kit readiness.",
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
        "| Job | Gemini skill | Gemini subagent | Safety |",
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
        "- Never auto-install `gh`, language runtimes, or package managers.",
        "- Never print, persist, or copy Endor API key, secret, token, or full config values.",
        "",
        "## Provider Docs",
        "",
        "- https://geminicli.com/docs/extensions/writing-extensions/",
        "- https://geminicli.com/docs/extensions/reference/",
        "- https://geminicli.com/docs/hooks/",
        "- https://geminicli.com/docs/extensions/releasing/",
        "- https://geminicli.com/docs/core/subagents/",
        "",
    ])

def _workflow_safety(prepared: PreparedSourceRecipe) -> str:
    return "mutating, approval-gated" if source_recipe_safety_posture(prepared.recipe).is_mutating else "read-only"
