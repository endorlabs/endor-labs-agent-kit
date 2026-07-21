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
from endor_agent_kit.compilers.rendering import (
    instructions_for_edition,
    render_action_contracts,
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
from endor_agent_kit.recipe import editions_for_host
from endor_agent_kit.safety_posture import source_recipe_safety_posture

CLAUDE_PLUGIN_PACKAGE_ROOT = Path("plugins") / "claude" / PLUGIN_NAME
CLAUDE_MARKETPLACE_PATH = Path(".claude-plugin") / "marketplace.json"
CLAUDE_LOCAL_MARKETPLACE_PATH = Path("plugins") / "claude" / ".claude-plugin" / "marketplace.json"
CLAUDE_SETUP_SKILL = "endor-agent-kit-setup"
CLAUDE_HOOK_SOURCE_DIR = Path("source") / "plugin-support" / "hooks" / "claude"
CLAUDE_HOOK_FILENAMES = (
    "suggest-endor-tools.sh",
    "check-dep-install.sh",
    "check-manifest-edit.sh",
)
CLAUDE_MARKETPLACE_NAME = "endorlabs"
CLAUDE_DISCOVERY_TERMS = (
    "agentic remediation",
    "SAST remediation",
    "agentic AppSec",
    "AppSec",
    "OSS Upgrade Investigator",
)
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

    package_records: tuple[CatalogPluginPackage, ...]
    written: tuple[Path, ...]


@dataclass(frozen=True)
class ClaudePluginPackageSpec:
    """One Claude Code plugin package emitted from the same Agent Kit sources."""

    name: str
    display_name: str
    version: str
    package_root: Path
    legacy: bool = False


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

    marketplace_path = destination / CLAUDE_MARKETPLACE_PATH
    local_marketplace_path = destination / CLAUDE_LOCAL_MARKETPLACE_PATH
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    local_marketplace_path.parent.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    version = package_version()
    package_specs = _claude_plugin_package_specs(version)
    sorted_recipes = sorted(claude_recipes, key=lambda item: item.recipe.id)

    for spec in package_specs:
        written.extend(_write_claude_plugin_package(destination, spec, sorted_recipes))

    marketplace_path.write_text(
        json.dumps(
            _claude_marketplace_manifest(
                package_specs,
                source_paths={
                    spec.name: f"./{spec.package_root.as_posix()}"
                    for spec in package_specs
                },
            ),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    written.append(marketplace_path)

    local_marketplace_path.write_text(
        json.dumps(
            _claude_marketplace_manifest(
                package_specs,
                source_paths={
                    spec.name: f"./{spec.name}"
                    for spec in package_specs
                },
            ),
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

    package_records = tuple(
        CatalogPluginPackage.from_published_package(
            destination,
            host=CLAUDE_CODE_HOST,
            name=spec.name,
            display_name=spec.display_name,
            version=spec.version,
            package_dir=destination / spec.package_root,
            marketplace_path=CLAUDE_MARKETPLACE_PATH.as_posix(),
            included_agents=tuple(prepared.recipe.id for prepared in sorted_recipes),
            extra_artifacts=(marketplace_path, local_marketplace_path, plugins_readme),
        )
        for spec in package_specs
    )
    return PluginPackagePublication(package_records=package_records, written=tuple(written))


LEGACY_CLAUDE_PLUGIN_NAME = "ai-plugins"
LEGACY_CLAUDE_PLUGIN_DISPLAY_NAME = "Endor Labs AI Plugins (Legacy)"
LEGACY_CLAUDE_PLUGIN_VERSION = "1.2.0"
PUBLIC_CLAUDE_DISTRIBUTION_REPOSITORY = "endorlabs/ai-plugins"


def _claude_plugin_package_specs(version: str) -> tuple[ClaudePluginPackageSpec, ...]:
    return (
        ClaudePluginPackageSpec(
            name=PLUGIN_NAME,
            display_name=PLUGIN_DISPLAY_NAME,
            version=version,
            package_root=CLAUDE_PLUGIN_PACKAGE_ROOT,
        ),
        ClaudePluginPackageSpec(
            name=LEGACY_CLAUDE_PLUGIN_NAME,
            display_name=LEGACY_CLAUDE_PLUGIN_DISPLAY_NAME,
            version=LEGACY_CLAUDE_PLUGIN_VERSION,
            package_root=Path("plugins") / "claude" / LEGACY_CLAUDE_PLUGIN_NAME,
            legacy=True,
        ),
    )


def _write_claude_plugin_package(
    destination: Path,
    spec: ClaudePluginPackageSpec,
    sorted_recipes: list[PreparedSourceRecipe],
) -> tuple[Path, ...]:
    package_dir = destination / spec.package_root
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True)
    (package_dir / ".claude-plugin").mkdir()
    (package_dir / "agents").mkdir()
    (package_dir / "skills").mkdir()
    (package_dir / "assets").mkdir()

    written: list[Path] = []
    for prepared in sorted_recipes:
        source_agent = _published_claude_agent_path(destination, prepared)
        source_agents = [source_agent, *sorted(source_agent.parent.glob(f"{prepared.recipe.id}-*.md"))]
        for source_variant in source_agents:
            profile_prefix = f"{prepared.recipe.id}-"
            profile_id = (
                source_variant.stem.removeprefix(profile_prefix)
                if source_variant.stem.startswith(profile_prefix)
                else None
            )
            target_agent = package_dir / "agents" / source_variant.name
            target_agent.write_text(
                _render_claude_plugin_agent(
                    prepared,
                    source_variant.read_text(encoding="utf-8"),
                    profile_id=profile_id,
                ),
                encoding="utf-8",
            )
            written.append(target_agent)

    setup_skill_dir = package_dir / "skills" / CLAUDE_SETUP_SKILL
    setup_skill_dir.mkdir(parents=True)
    setup_skill = setup_skill_dir / "SKILL.md"
    setup_skill.write_text(_render_setup_skill(sorted_recipes, spec), encoding="utf-8")
    written.append(setup_skill)

    logo = write_logo(package_dir / "assets")
    written.append(logo)

    if not spec.legacy:
        written.extend(_write_claude_plugin_hooks(spec, package_dir))

    plugin_manifest = package_dir / ".claude-plugin" / "plugin.json"
    plugin_manifest.write_text(
        json.dumps(_claude_plugin_manifest(spec), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    written.append(plugin_manifest)

    readme = package_dir / "README.md"
    readme.write_text(_claude_plugin_readme(sorted_recipes, spec), encoding="utf-8")
    written.append(readme)
    return tuple(written)


def _write_claude_plugin_hooks(
    spec: ClaudePluginPackageSpec,
    package_dir: Path,
) -> tuple[Path, ...]:
    if spec.legacy:
        return ()
    source_dir = _hook_source()
    hooks_dir = package_dir / "hooks"
    hooks_dir.mkdir()
    written: list[Path] = []
    for filename in CLAUDE_HOOK_FILENAMES:
        source = source_dir / filename
        target = hooks_dir / filename
        shutil.copy2(source, target)
        written.append(target)
    hooks_json = hooks_dir / "hooks.json"
    hooks_json.write_text(
        json.dumps(_claude_hooks_config(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    written.append(hooks_json)
    return tuple(written)


def _hook_source() -> Path:
    candidates = [
        Path(__file__).resolve().parents[3] / CLAUDE_HOOK_SOURCE_DIR,
        Path.cwd() / CLAUDE_HOOK_SOURCE_DIR,
    ]
    for candidate in candidates:
        if candidate.is_dir():
            missing = [
                filename
                for filename in CLAUDE_HOOK_FILENAMES
                if not (candidate / filename).is_file()
            ]
            if missing:
                raise FileNotFoundError(
                    f"{candidate}: missing Claude hook source files {missing}"
                )
            return candidate
    raise FileNotFoundError(CLAUDE_HOOK_SOURCE_DIR.as_posix())


def _claude_hooks_config() -> dict[str, object]:
    def command(filename: str) -> dict[str, object]:
        return {
            "type": "command",
            "command": f'bash "${{CLAUDE_PLUGIN_ROOT}}/hooks/{filename}"',
            "timeout": 10,
        }

    return {
        "hooks": {
            "UserPromptSubmit": [
                {
                    "matcher": "",
                    "hooks": [command("suggest-endor-tools.sh")],
                }
            ],
            "PostToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [command("check-dep-install.sh")],
                },
                {
                    "matcher": "Edit|MultiEdit|Write",
                    "hooks": [command("check-manifest-edit.sh")],
                },
            ],
        }
    }


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
    *,
    profile_id: str | None = None,
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
        (
            f"<!-- endor_agent_kit_managed=true agent_id={prepared.recipe.id} "
            f"profile_id={profile_id or 'base'} host=claude-code-plugin -->"
        ),
    ])
    setup_note = dedent(
        f"""\
        ## Claude Code Plugin Setup Note

        Run `{CLAUDE_SETUP_SKILL}` for missing setup, auth, namespace, MCP, or workflow tooling.
        This package does not declare plugin-wide MCP. Plugin agents cannot declare
        `mcpServers`; use `data_gaps` for unavailable tools.
        """
    ).strip()
    return "\n\n".join([
        f"---\n{sanitized_frontmatter.rstrip()}\n---",
        provenance,
        _compact_claude_plugin_body(body, prepared, profile_id=profile_id).rstrip(),
        setup_note,
    ]) + "\n"


def _compact_claude_plugin_body(
    body: str,
    prepared: PreparedSourceRecipe,
    *,
    profile_id: str | None = None,
) -> str:
    notice = body.split("\n\n", 1)[0].rstrip()
    compact_body = instructions_for_edition(
        prepared.instructions,
        _claude_plugin_edition(prepared),
        recipe_id=prepared.recipe.id,
        structured_output_recipe=prepared.recipe,
        compact_plugin=True,
        profile_id=profile_id,
    )
    compact_actions = render_action_contracts(prepared.actions, compact=True)
    return f"{notice}\n\n{compact_body.rstrip()}\n{compact_actions}"


def _claude_plugin_edition(prepared: PreparedSourceRecipe) -> str:
    editions = editions_for_host(prepared.recipe, CLAUDE_CODE_HOST, EDITIONS)
    return "enterprise-edition" if "enterprise-edition" in editions else editions[0]


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


def _claude_plugin_manifest(spec: ClaudePluginPackageSpec) -> dict[str, object]:
    description = "Endor Labs workflow agents and setup for Claude Code."
    if spec.legacy:
        description = "Legacy Claude Code plugin id for Endor Labs Agent Kit workflows."
    return {
        "name": spec.name,
        "displayName": spec.display_name,
        "version": spec.version,
        "description": description,
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
            "claude-code",
            *CLAUDE_DISCOVERY_TERMS,
        ],
    }


def _claude_marketplace_manifest(
    package_specs: tuple[ClaudePluginPackageSpec, ...],
    *,
    source_paths: dict[str, str],
) -> dict[str, object]:
    return {
        "name": CLAUDE_MARKETPLACE_NAME,
        "description": "Endor Labs Agent Kit Claude Code plugin marketplace.",
        "owner": {
            "name": "Endor Labs",
            "email": "support@endor.ai",
        },
        "plugins": [
            _claude_marketplace_entry(spec, source_path=source_paths[spec.name])
            for spec in package_specs
        ],
    }


def _claude_marketplace_entry(
    spec: ClaudePluginPackageSpec,
    *,
    source_path: str,
) -> dict[str, object]:
    description = "Endor Labs workflow agents and setup for Claude Code."
    if spec.legacy:
        description = "Legacy Claude Code plugin id for Endor Labs Agent Kit workflows."
    return {
        "name": spec.name,
        "displayName": spec.display_name,
        "source": source_path,
        "description": description,
        "version": spec.version,
        "author": {
            "name": "Endor Labs",
        },
        "keywords": [
            "endor-labs",
            "security",
            "sca",
            "sast",
            "claude-code",
            *CLAUDE_DISCOVERY_TERMS,
        ],
        "category": "Developer Tools",
        "tags": [
            "endor-labs",
            "security",
            "sca",
            "sast",
            "claude-code",
            *CLAUDE_DISCOVERY_TERMS,
        ],
    }


def _render_setup_skill(
    prepared_recipes: list[PreparedSourceRecipe],
    spec: ClaudePluginPackageSpec,
) -> str:
    setup_source = _setup_source(prepared_recipes)
    workflow_lines = [
        f"- `{_workflow_label(prepared.recipe.id)}` -> Claude Code agent `{prepared.recipe.id}`"
        for prepared in prepared_recipes
    ]
    install_notice = _claude_install_upgrade_notice(spec)
    return "\n".join([
        "---",
        f"name: {CLAUDE_SETUP_SKILL}",
        "description: Use when setting up Endor Labs Agent Kit for Claude Code, checking readiness, verifying Endor auth, choosing namespaces, or diagnosing missing endorctl, gh, Endor MCP, or workflow prerequisites.",
        "---",
        "",
        "# Endor Agent Kit Setup For Claude Code",
        "",
        f"Generated for the {spec.display_name} Claude Code plugin.",
        "",
        "## Claude Install And Upgrade Notice",
        "",
        *install_notice,
        "",
        "## Bundled Claude Code Agents",
        "",
        *workflow_lines,
        "",
        "## Claude Code Plugin Install Commands",
        "",
        "From the public ai-plugins distribution repository:",
        "",
        "```text",
        f"/plugin marketplace add {PUBLIC_CLAUDE_DISTRIBUTION_REPOSITORY} --sparse .claude-plugin plugins/claude",
        f"/plugin install {spec.name}@{CLAUDE_MARKETPLACE_NAME}",
        "```",
        "",
        "From a local checkout of the Agent Kit repository root:",
        "",
        "```text",
        "/plugin marketplace add ./",
        f"/plugin install {spec.name}@{CLAUDE_MARKETPLACE_NAME}",
        "```",
        "",
        "For package-only local validation, add the generated Claude marketplace:",
        "",
        "```text",
        "/plugin marketplace add ./plugins/claude",
        f"/plugin install {spec.name}@{CLAUDE_MARKETPLACE_NAME}",
        "```",
        "",
        setup_source.rstrip(),
        "",
        "## Claude-Specific Rules",
        "",
        "- Prefer the default Claude Code user-scope plugin install unless the user explicitly requests project, local, or managed scope.",
        "- Do not copy plugin-packaged agents into `.claude/agents/` when marketplace installation is available.",
        "- Do not add plugin-wide MCP automatically. Only guide per-workflow MCP setup when the selected workflow needs it and the user approves.",
        "- The primary `endor-labs-agent-kit` plugin also ships advisory hooks for prompt routing, dependency installs, and dependency manifest edits. Hooks are fail-open, read-only, and never run Endor commands.",
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
    spec: ClaudePluginPackageSpec,
) -> str:
    rows = [
        f"| {_workflow_label(prepared.recipe.id)} | `{prepared.recipe.id}` | {_workflow_safety(prepared)} |"
        for prepared in prepared_recipes
    ]
    install_notice = _claude_install_upgrade_notice(spec)
    start_here = plugin_readme_start_here(
        host_label="Claude Code",
        install_summary=f"Install `{spec.name}@{CLAUDE_MARKETPLACE_NAME}` from the public marketplace or a local checkout.",
        setup_summary=f"ask Claude Code to use the `{CLAUDE_SETUP_SKILL}` skill.",
    )
    return "\n".join([
        f"# {spec.display_name} Claude Code Plugin",
        "",
        "<!-- Generated by Endor Labs Agent Kit. Do not hand-edit. -->",
        "",
        f"Version: `{spec.version}`",
        "",
        "This generated Claude Code plugin package includes Endor Labs setup",
        "support and Claude Code agents generated from source recipes in the",
        "Endor Labs Agent Kit repository.",
        "",
        *start_here,
        "## Install And Upgrade Notice",
        "",
        *install_notice,
        "",
        "## Host Metadata",
        "",
        "- Manifest: `.claude-plugin/plugin.json`.",
        "- Agents: `agents/<agent>.md`, auto-discovered from the plugin root with Claude Code plugin-supported frontmatter only.",
        "- Skills: `skills/endor-agent-kit-setup/SKILL.md`, auto-discovered from the plugin root.",
        *(
            ["- Hooks: `hooks/hooks.json` plus fail-open advisory scripts for routing, dependency installs, and manifest edits."]
            if not spec.legacy
            else ["- Hooks: not included in the legacy compatibility package."]
        ),
        "- Model/runtime: packaged agents preserve supported generated agent frontmatter; the plugin does not set a plugin-wide default model.",
        "- MCP: no plugin-wide MCP server is declared by default.",
        "",
        "## Install From The Public Repository",
        "",
        "```text",
        f"/plugin marketplace add {PUBLIC_CLAUDE_DISTRIBUTION_REPOSITORY} --sparse .claude-plugin plugins/claude",
        f"/plugin install {spec.name}@{CLAUDE_MARKETPLACE_NAME}",
        "```",
        "",
        "## Install From A Local Checkout",
        "",
        "From the Agent Kit repository root:",
        "",
        "```text",
        "/plugin marketplace add ./",
        f"/plugin install {spec.name}@{CLAUDE_MARKETPLACE_NAME}",
        "```",
        "",
        "Start a new Claude Code session or run `/reload-plugins` after installing",
        "or reinstalling the plugin.",
        "If Claude Code still shows stale same-version content, uninstall and",
        "reinstall the plugin id, run `/reload-plugins`, and start a new Claude",
        "Code session so host caches reload the generated agents and setup skill.",
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
        "- Never auto-install `gh`, language runtimes, or package managers.",
        "- Never print, persist, or copy Endor API key, secret, token, or full config values.",
        "",
        "## Provider Notes",
        "",
        "Claude Code plugin-shipped agents do not support `mcpServers`,",
        "`permissionMode`, or `hooks` in agent frontmatter. This package removes",
        "agent-local MCP frontmatter from generated Claude Code artifacts and keeps",
        "MCP setup as explicit user-guided configuration. The primary package uses",
        "plugin-level advisory hooks only; they add context and never block or run",
        "Endor commands.",
        "",
        "Before release, verify the current Claude Code plugin and marketplace docs:",
        "",
        "- https://code.claude.com/docs/en/plugins",
        "- https://code.claude.com/docs/en/plugin-marketplaces",
        "- https://code.claude.com/docs/en/plugins-reference",
        "",
    ])


def _claude_install_upgrade_notice(spec: ClaudePluginPackageSpec) -> list[str]:
    if spec.legacy:
        return [
            f"- `{LEGACY_CLAUDE_PLUGIN_NAME}@{CLAUDE_MARKETPLACE_NAME}` is retained for existing Claude Code users and pinned installs.",
            f"- New installs should prefer `{PLUGIN_NAME}@{CLAUDE_MARKETPLACE_NAME}`.",
            "- Existing users do not need an automatic migration; this package will keep working.",
            "- Do not enable both Claude plugin ids in the same profile because they expose the same agents and setup skill.",
            "- The plugin does not auto-disable, uninstall, or edit Claude settings for either id.",
        ]
    return [
        f"- `{PLUGIN_NAME}@{CLAUDE_MARKETPLACE_NAME}` is the preferred Claude Code plugin id for new installs.",
        f"- Existing `{LEGACY_CLAUDE_PLUGIN_NAME}@{CLAUDE_MARKETPLACE_NAME}` users can keep using the legacy compatibility package.",
        "- Do not enable both Claude plugin ids in the same profile because they expose the same agents and setup skill.",
        "- The plugin does not auto-disable, uninstall, or edit Claude settings for either id.",
    ]


def _workflow_label(agent_id: str) -> str:
    labels = {
        "ai-sast-remediation": "Triage AI SAST findings",
        "cicd-posture": "Assess CI/CD and supply chain posture",
        "dependency-reviewer": "Review package decisions, package risk, or repository dependencies",
        "troubleshooting": "Diagnose Endor setup and scan issues",
        "findings-browser": "Browse existing Endor findings",
        "configuration-automation": "Assess GitHub onboarding gaps",
        "remediation-planning": "Plan remediation across findings",
        "sca-remediation": "Find safe SCA remediation paths",
        "oss-upgrade-investigator": "Analyze upgrade impact",
        "vulnerability-explainer": "Explain vulnerability risk and remediation",
    }
    return labels.get(agent_id, agent_id.replace("-", " ").title())


def _workflow_safety(prepared: PreparedSourceRecipe) -> str:
    return "mutating, approval-gated" if source_recipe_safety_posture(prepared.recipe).is_mutating else "read-only"
