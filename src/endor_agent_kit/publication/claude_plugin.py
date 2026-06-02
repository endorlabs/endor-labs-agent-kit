"""Claude Code plugin package publication."""

from __future__ import annotations

from dataclasses import dataclass
import json
import shutil
from pathlib import Path
from textwrap import dedent

import yaml

from endor_agent_kit.catalog_schema import CatalogPluginPackage
from endor_agent_kit.compilers.claude_code import EDITIONS, HOST as CLAUDE_CODE_HOST
from endor_agent_kit.prepared_source_recipe import PreparedSourceRecipe
from endor_agent_kit.publication.plugin_package_common import (
    PLUGIN_DISPLAY_NAME,
    PLUGIN_NAME,
    logo_svg,
    package_version,
    plugin_packages_readme,
)
from endor_agent_kit.recipe import editions_for_host
from endor_agent_kit.safety_posture import source_recipe_safety_posture

CLAUDE_PLUGIN_PACKAGE_ROOT = Path("plugins") / "claude" / PLUGIN_NAME
CLAUDE_MARKETPLACE_PATH = Path(".claude-plugin") / "marketplace.json"
CLAUDE_LOCAL_MARKETPLACE_PATH = Path("plugins") / "claude" / ".claude-plugin" / "marketplace.json"
CLAUDE_SETUP_SKILL = "endor-agent-kit-setup"
CLAUDE_UNSUPPORTED_AGENT_FRONTMATTER = frozenset({
    "hooks",
    "mcpServers",
    "permissionMode",
})
CLAUDE_SUPPORTED_AGENT_FRONTMATTER = frozenset({
    "background",
    "description",
    "disallowedTools",
    "effort",
    "isolation",
    "maxTurns",
    "memory",
    "model",
    "name",
    "skills",
    "tools",
})


@dataclass(frozen=True)
class PluginPackagePublication:
    """Result of publishing one generated plugin package."""

    package_record: CatalogPluginPackage
    written: tuple[Path, ...]


def publish_claude_plugin_package(
    prepared_recipes: list[PreparedSourceRecipe],
    destination: Path,
) -> PluginPackagePublication | None:
    """Publish the generated Claude Code plugin package for compatible recipes."""

    claude_recipes = [
        prepared
        for prepared in prepared_recipes
        if CLAUDE_CODE_HOST in prepared.recipe.compatible_hosts
    ]
    if not claude_recipes:
        return None

    package_dir = destination / CLAUDE_PLUGIN_PACKAGE_ROOT
    marketplace_path = destination / CLAUDE_MARKETPLACE_PATH
    local_marketplace_path = destination / CLAUDE_LOCAL_MARKETPLACE_PATH
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True)
    (package_dir / ".claude-plugin").mkdir()
    (package_dir / "agents").mkdir()
    (package_dir / "skills").mkdir()
    (package_dir / "assets").mkdir()
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    local_marketplace_path.parent.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    version = package_version()
    sorted_recipes = sorted(claude_recipes, key=lambda item: item.recipe.id)

    for prepared in sorted_recipes:
        source_agent = _published_claude_agent_path(destination, prepared)
        target_agent = package_dir / "agents" / f"{prepared.recipe.id}.md"
        target_agent.write_text(
            _render_claude_plugin_agent(
                prepared,
                source_agent.read_text(encoding="utf-8"),
            ),
            encoding="utf-8",
        )
        written.append(target_agent)

    setup_skill_dir = package_dir / "skills" / CLAUDE_SETUP_SKILL
    setup_skill_dir.mkdir(parents=True)
    setup_skill = setup_skill_dir / "SKILL.md"
    setup_skill.write_text(_render_setup_skill(sorted_recipes), encoding="utf-8")
    written.append(setup_skill)

    logo = package_dir / "assets" / "logo.svg"
    logo.write_text(logo_svg(), encoding="utf-8")
    written.append(logo)

    plugin_manifest = package_dir / ".claude-plugin" / "plugin.json"
    plugin_manifest.write_text(
        json.dumps(_claude_plugin_manifest(version), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    written.append(plugin_manifest)

    readme = package_dir / "README.md"
    readme.write_text(_claude_plugin_readme(sorted_recipes, version), encoding="utf-8")
    written.append(readme)

    marketplace_path.write_text(
        json.dumps(
            _claude_marketplace_manifest(source_path=f"./{CLAUDE_PLUGIN_PACKAGE_ROOT.as_posix()}"),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    written.append(marketplace_path)

    local_marketplace_path.write_text(
        json.dumps(
            _claude_marketplace_manifest(source_path=f"./{PLUGIN_NAME}"),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    written.append(local_marketplace_path)

    plugins_readme = destination / "plugins" / "README.md"
    plugins_readme.write_text(plugin_packages_readme(), encoding="utf-8")
    written.append(plugins_readme)

    package_record = CatalogPluginPackage.from_published_package(
        destination,
        host=CLAUDE_CODE_HOST,
        name=PLUGIN_NAME,
        display_name=PLUGIN_DISPLAY_NAME,
        version=version,
        package_dir=package_dir,
        marketplace_path=CLAUDE_MARKETPLACE_PATH.as_posix(),
        included_agents=tuple(prepared.recipe.id for prepared in sorted_recipes),
        extra_artifacts=(marketplace_path, local_marketplace_path, plugins_readme),
    )
    return PluginPackagePublication(package_record=package_record, written=tuple(written))


def _published_claude_agent_path(destination: Path, prepared: PreparedSourceRecipe) -> Path:
    recipe = prepared.recipe
    editions = editions_for_host(recipe, CLAUDE_CODE_HOST, EDITIONS)
    edition = "enterprise-edition" if "enterprise-edition" in editions else editions[0]
    if len(editions) == 1:
        return destination / CLAUDE_CODE_HOST / recipe.id / f"{recipe.id}.md"
    return destination / CLAUDE_CODE_HOST / recipe.id / edition / f"{recipe.id}.md"


def _render_claude_plugin_agent(
    prepared: PreparedSourceRecipe,
    source_markdown: str,
) -> str:
    frontmatter, body = _split_frontmatter(source_markdown)
    sanitized_frontmatter = _sanitize_agent_frontmatter(frontmatter)
    metadata = yaml.safe_load(sanitized_frontmatter) or {}
    if not isinstance(metadata, dict):
        raise ValueError(f"{prepared.recipe.id}: Claude agent frontmatter must be a mapping")
    unsupported = sorted(set(metadata) - CLAUDE_SUPPORTED_AGENT_FRONTMATTER)
    if unsupported:
        raise ValueError(
            f"{prepared.recipe.id}: unsupported Claude plugin agent frontmatter {unsupported}"
        )

    provenance = "\n".join([
        "<!-- Generated by Endor Labs Agent Kit. Do not hand-edit installed plugin cache copies. -->",
        f"<!-- endor_agent_kit_managed=true agent_id={prepared.recipe.id} host=claude-code-plugin -->",
    ])
    setup_note = dedent(
        f"""\
        ## Claude Code Plugin Setup Note

        This agent is installed from the Endor Labs Agent Kit Claude Code plugin.
        If `endorctl`, `gh`, Endor authentication, namespace selection, Endor MCP,
        or workflow-specific tooling is missing, ask the user to run the
        `{CLAUDE_SETUP_SKILL}` skill before continuing live Endor work.

        Claude Code plugin-shipped agents do not support `mcpServers`,
        `permissionMode`, or `hooks` in agent frontmatter. This package omits
        those fields and does not declare plugin-wide MCP. If an Endor MCP-only
        signal is unavailable, report it in `data_gaps` rather than fabricating
        evidence.
        """
    ).strip()
    return "\n\n".join([
        f"---\n{sanitized_frontmatter.rstrip()}\n---",
        provenance,
        body.rstrip(),
        setup_note,
        "",
    ])


def _split_frontmatter(markdown: str) -> tuple[str, str]:
    parts = markdown.split("---", 2)
    if len(parts) == 3 and not parts[0].strip():
        return parts[1].strip("\n"), parts[2].lstrip()
    raise ValueError("Claude Code agent artifact is missing YAML frontmatter")


def _sanitize_agent_frontmatter(frontmatter: str) -> str:
    kept: list[str] = []
    skip = False
    for line in frontmatter.splitlines():
        is_top_level = bool(line) and not line.startswith((" ", "\t")) and ":" in line
        if is_top_level:
            key = line.split(":", 1)[0].strip()
            skip = key in CLAUDE_UNSUPPORTED_AGENT_FRONTMATTER
        if not skip:
            kept.append(line)
    return "\n".join(kept).rstrip()


def _claude_plugin_manifest(version: str) -> dict[str, object]:
    return {
        "name": PLUGIN_NAME,
        "displayName": PLUGIN_DISPLAY_NAME,
        "version": version,
        "description": "Endor Labs workflow agents and setup for Claude Code.",
        "author": {
            "name": "Endor Labs",
            "url": "https://www.endorlabs.com/",
        },
        "homepage": "https://github.com/endorlabs/endor-labs-agent-kit",
        "repository": "https://github.com/endorlabs/endor-labs-agent-kit",
        "keywords": [
            "endor-labs",
            "security",
            "sca",
            "sast",
            "claude-code",
        ],
        "skills": "./skills/",
        "agents": "./agents/",
    }


def _claude_marketplace_manifest(*, source_path: str) -> dict[str, object]:
    return {
        "name": PLUGIN_NAME,
        "description": "Endor Labs Agent Kit Claude Code plugin marketplace.",
        "owner": {
            "name": "Endor Labs",
            "email": "support@endorlabs.com",
        },
        "plugins": [
            {
                "name": PLUGIN_NAME,
                "displayName": PLUGIN_DISPLAY_NAME,
                "source": source_path,
                "description": "Endor Labs workflow agents and setup for Claude Code.",
                "version": package_version(),
                "author": {
                    "name": "Endor Labs",
                },
                "category": "Developer Tools",
                "tags": [
                    "endor-labs",
                    "security",
                    "sca",
                    "sast",
                    "claude-code",
                ],
            }
        ],
    }


def _render_setup_skill(prepared_recipes: list[PreparedSourceRecipe]) -> str:
    setup_source = _setup_source(prepared_recipes)
    workflow_lines = [
        f"- `{_workflow_label(prepared.recipe.id)}` -> Claude Code agent `{prepared.recipe.id}`"
        for prepared in prepared_recipes
    ]
    return "\n".join([
        "---",
        f"name: {CLAUDE_SETUP_SKILL}",
        "description: Use when setting up Endor Labs Agent Kit for Claude Code, checking readiness, verifying Endor auth, choosing namespaces, or diagnosing missing endorctl, gh, Endor MCP, or workflow prerequisites.",
        "---",
        "",
        "# Endor Agent Kit Setup For Claude Code",
        "",
        "Generated for the Endor Labs Agent Kit Claude Code plugin.",
        "",
        "## Bundled Claude Code Agents",
        "",
        *workflow_lines,
        "",
        "## Claude Code Plugin Install Commands",
        "",
        "From a public checkout of the Agent Kit repository:",
        "",
        "```text",
        "/plugin marketplace add endorlabs/endor-labs-agent-kit",
        f"/plugin install {PLUGIN_NAME}@{PLUGIN_NAME}",
        "```",
        "",
        "From a local checkout of the Agent Kit repository root:",
        "",
        "```text",
        "/plugin marketplace add .",
        f"/plugin install {PLUGIN_NAME}@{PLUGIN_NAME}",
        "```",
        "",
        "For package-only local validation, add the generated Claude marketplace:",
        "",
        "```text",
        "/plugin marketplace add plugins/claude",
        f"/plugin install {PLUGIN_NAME}@{PLUGIN_NAME}",
        "```",
        "",
        setup_source.rstrip(),
        "",
        "## Claude-Specific Rules",
        "",
        "- Prefer the default Claude Code user-scope plugin install unless the user explicitly requests project, local, or managed scope.",
        "- Do not copy plugin-packaged agents into `.claude/agents/` when marketplace installation is available.",
        "- Do not add plugin-wide MCP automatically. Only guide per-workflow MCP setup when the selected workflow needs it and the user approves.",
        "- Claude Code plugin-shipped agents cannot declare `mcpServers`, `permissionMode`, or `hooks` in agent frontmatter; report unavailable MCP-only signals in `data_gaps`.",
        "- Tell the user to restart or reload Claude Code after installing or updating the plugin.",
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


def _claude_plugin_readme(
    prepared_recipes: list[PreparedSourceRecipe],
    version: str,
) -> str:
    rows = [
        f"| {_workflow_label(prepared.recipe.id)} | `{prepared.recipe.id}` | {_workflow_safety(prepared)} |"
        for prepared in prepared_recipes
    ]
    return "\n".join([
        "# Endor Labs Agent Kit Claude Code Plugin",
        "",
        "<!-- Generated by Endor Labs Agent Kit. Do not hand-edit. -->",
        "",
        f"Version: `{version}`",
        "",
        "This generated Claude Code plugin package includes Endor Labs setup",
        "support and Claude Code agents generated from source recipes in the",
        "Endor Labs Agent Kit repository.",
        "",
        "## Host Metadata",
        "",
        "- Manifest: `.claude-plugin/plugin.json`.",
        "- Agents: `agents/<agent>.md` with Claude Code plugin-supported frontmatter only.",
        "- Skills: `skills/endor-agent-kit-setup/SKILL.md`.",
        "- Model/runtime: packaged agents preserve supported generated agent frontmatter; the plugin does not set a plugin-wide default model.",
        "- MCP: no plugin-wide MCP server is declared by default.",
        "",
        "## Install From The Public Repository",
        "",
        "```text",
        "/plugin marketplace add endorlabs/endor-labs-agent-kit",
        f"/plugin install {PLUGIN_NAME}@{PLUGIN_NAME}",
        "```",
        "",
        "## Install From A Local Checkout",
        "",
        "From the Agent Kit repository root:",
        "",
        "```text",
        "/plugin marketplace add .",
        f"/plugin install {PLUGIN_NAME}@{PLUGIN_NAME}",
        "```",
        "",
        "Start a new Claude Code session or run `/reload-plugins` after installing",
        "or reinstalling the plugin.",
        "",
        "## Set Up This Machine",
        "",
        "Ask Claude Code:",
        "",
        "```text",
        f"Use the {CLAUDE_SETUP_SKILL} skill to check Endor Agent Kit readiness.",
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
        "| Job | Claude Code agent | Safety |",
        "| --- | --- | --- |",
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
        "## Provider Notes",
        "",
        "Claude Code plugin-shipped agents do not support `mcpServers`,",
        "`permissionMode`, or `hooks` in agent frontmatter. This package removes",
        "agent-local MCP frontmatter from generated Claude Code artifacts and keeps",
        "MCP setup as explicit user-guided configuration.",
        "",
        "Before release, verify the current Claude Code plugin and marketplace docs:",
        "",
        "- https://code.claude.com/docs/en/plugins",
        "- https://code.claude.com/docs/en/plugin-marketplaces",
        "- https://code.claude.com/docs/en/plugins-reference",
        "",
    ])


def _workflow_label(agent_id: str) -> str:
    labels = {
        "ai-sast-triage": "Triage AI SAST findings",
        "dependency-decision-helper": "Decide whether a dependency is safe to use",
        "endor-troubleshooter": "Diagnose Endor setup and scan issues",
        "package-risk-summary": "Summarize package-version risk",
        "probe-droid": "Assess GitHub onboarding gaps",
        "remediation-planner": "Plan remediation across findings",
        "repository-dependency-reviewer": "Review repository dependency manifests",
        "sca-remediation": "Find safe SCA remediation paths",
        "upgrade-impact-analysis": "Analyze upgrade impact",
        "vulnerability-explainer": "Explain vulnerability risk and remediation",
    }
    return labels.get(agent_id, agent_id.replace("-", " ").title())


def _workflow_safety(prepared: PreparedSourceRecipe) -> str:
    return "mutating, approval-gated" if source_recipe_safety_posture(prepared.recipe).is_mutating else "read-only"
