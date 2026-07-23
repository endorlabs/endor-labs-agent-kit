"""Codex public-directory skills-only package publication."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import shutil

from endor_agent_kit.catalog_schema import CatalogPluginPackage
from endor_agent_kit.compilers.codex import HOST as CODEX_HOST, render_codex_skill
from endor_agent_kit.prepared_source_recipe import PreparedSourceRecipe
from endor_agent_kit.publication.plugin_package_common import (
    PLUGIN_DISPLAY_NAME,
    PLUGIN_NAME,
    package_version,
    write_logo,
)
from endor_agent_kit.publication.runtime_support import (
    ARTIFACT_SUMMARIZER_NAME,
    write_artifact_summarizer_file,
)


CODEX_DIRECTORY_CHANNEL = "official-directory"
CODEX_DIRECTORY_PACKAGE_ROOT = Path("plugins") / "codex-directory" / PLUGIN_NAME
CODEX_DIRECTORY_SKILL_IDS = (
    "ai-sast-remediation",
    "cicd-posture",
    "configuration-automation",
    "dependency-reviewer",
    "findings-browser",
    "malware-responder",
    "oss-upgrade-investigator",
    "remediation-planning",
    "sca-remediation",
    "troubleshooting",
    "vulnerability-explainer",
)
CODEX_DIRECTORY_SUMMARIZER_COMMAND = (
    'python3 "$SKILL_DIR/scripts/summarize_endor_artifact.py"'
)
CODEX_DIRECTORY_SUMMARIZER_GUIDANCE = (
    "For large-result capture, take the active skill path disclosed by Codex, set "
    "`SKILL_DIR` to the absolute parent directory of this `SKILL.md`, and invoke "
    "the skill-local helper from `$SKILL_DIR/scripts/summarize_endor_artifact.py`; "
    "never resolve it from the current working directory."
)


@dataclass(frozen=True)
class CodexDirectoryPluginPublication:
    """Result of publishing the Codex public-directory package."""

    package_record: CatalogPluginPackage
    written: tuple[Path, ...]


def publish_codex_directory_plugin_package(
    prepared_recipes: tuple[PreparedSourceRecipe, ...] | list[PreparedSourceRecipe],
    destination: Path,
) -> CodexDirectoryPluginPublication | None:
    """Publish the exact canonical skills-only package, preserving it for partial runs."""

    codex_recipes = [
        prepared
        for prepared in prepared_recipes
        if CODEX_HOST in prepared.recipe.compatible_hosts
    ]
    if not codex_recipes:
        return None

    recipe_ids = [prepared.recipe.id for prepared in codex_recipes]
    duplicate_ids = sorted({agent_id for agent_id in recipe_ids if recipe_ids.count(agent_id) > 1})
    unexpected_ids = sorted(set(recipe_ids) - set(CODEX_DIRECTORY_SKILL_IDS))
    if duplicate_ids or unexpected_ids:
        details = []
        if duplicate_ids:
            details.append(f"duplicate ids: {', '.join(duplicate_ids)}")
        if unexpected_ids:
            details.append(f"unexpected ids: {', '.join(unexpected_ids)}")
        raise ValueError(
            "Codex official-directory publication requires the canonical workflow set ("
            + "; ".join(details)
            + ")"
        )
    if set(recipe_ids) < set(CODEX_DIRECTORY_SKILL_IDS):
        return None
    missing_ids = sorted(set(CODEX_DIRECTORY_SKILL_IDS) - set(recipe_ids))
    if missing_ids:
        raise ValueError(
            "Codex official-directory publication is missing canonical ids: "
            + ", ".join(missing_ids)
        )

    package_dir = destination / CODEX_DIRECTORY_PACKAGE_ROOT
    if package_dir.exists():
        shutil.rmtree(package_dir)
    (package_dir / ".codex-plugin").mkdir(parents=True)
    (package_dir / "skills").mkdir()
    (package_dir / "assets").mkdir()

    version = package_version()
    sorted_recipes = sorted(codex_recipes, key=lambda prepared: prepared.recipe.id)
    written: list[Path] = []
    for prepared in sorted_recipes:
        skill_dir = package_dir / "skills" / prepared.recipe.id
        (skill_dir / "agents").mkdir(parents=True)
        (skill_dir / "scripts").mkdir()

        skill = skill_dir / "SKILL.md"
        skill.write_text(
            render_codex_skill(
                prepared,
                generated_context="Endor Labs Agent Kit Codex public-directory plugin",
                compact_plugin=True,
                package_name=PLUGIN_NAME,
                package_version=version,
                artifact_summarizer_command=CODEX_DIRECTORY_SUMMARIZER_COMMAND,
                artifact_summarizer_guidance=CODEX_DIRECTORY_SUMMARIZER_GUIDANCE,
            ),
            encoding="utf-8",
        )
        written.append(skill)

        openai_yaml = skill_dir / "agents" / "openai.yaml"
        openai_yaml.write_text(_render_openai_yaml(prepared), encoding="utf-8")
        written.append(openai_yaml)

        helper = write_artifact_summarizer_file(
            skill_dir / "scripts" / ARTIFACT_SUMMARIZER_NAME
        )
        written.append(helper)

    logo = write_logo(package_dir / "assets")
    written.append(logo)
    composer_icon = package_dir / "assets" / "composer-icon.png"
    shutil.copy2(logo, composer_icon)
    written.append(composer_icon)

    manifest = package_dir / ".codex-plugin" / "plugin.json"
    manifest.write_text(
        json.dumps(_codex_directory_manifest(version), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    written.append(manifest)

    package_record = CatalogPluginPackage.from_published_package(
        destination,
        host=CODEX_HOST,
        name=PLUGIN_NAME,
        display_name=PLUGIN_DISPLAY_NAME,
        version=version,
        package_dir=package_dir,
        included_agents=tuple(prepared.recipe.id for prepared in sorted_recipes),
        distribution_channel=CODEX_DIRECTORY_CHANNEL,
    )
    return CodexDirectoryPluginPublication(
        package_record=package_record,
        written=tuple(written),
    )


def _render_openai_yaml(prepared: PreparedSourceRecipe) -> str:
    recipe = prepared.recipe
    description = _truncate(_single_line(recipe.short_description or recipe.description), 100)
    default_prompt = f"Use ${recipe.id} for this Endor Labs workflow."
    # JSON is a strict YAML subset. Using it here keeps the metadata portable to
    # the stdlib-only immutable-mirror validator while remaining valid openai.yaml.
    return json.dumps(
        {
            "interface": {
                "display_name": recipe.name,
                "short_description": description,
                "default_prompt": default_prompt,
            },
            "policy": {"allow_implicit_invocation": True},
        },
        indent=2,
        sort_keys=True,
    ) + "\n"


def _codex_directory_manifest(version: str) -> dict[str, object]:
    return {
        "name": PLUGIN_NAME,
        "version": version,
        "description": "Endor Labs security workflows for Codex.",
        "author": {
            "name": "Endor Labs",
            "url": "https://www.endorlabs.com/",
        },
        "homepage": "https://github.com/endorlabs/ai-plugins",
        "repository": "https://github.com/endorlabs/ai-plugins",
        "license": "MIT",
        "keywords": ["endor-labs", "security", "sca", "sast", "codex"],
        "skills": "./skills/",
        "interface": {
            "displayName": PLUGIN_DISPLAY_NAME,
            "shortDescription": "Endor security workflows",
            "longDescription": (
                "Use eleven source-generated Endor Labs workflows to investigate, "
                "triage, plan, and remediate application security and software "
                "supply-chain risks from Codex."
            ),
            "developerName": "Endor Labs",
            "category": "Developer Tools",
            "capabilities": ["Security", "Investigation", "Remediation"],
            "websiteURL": "https://www.endorlabs.com/",
            "defaultPrompt": [
                "Browse and summarize my active Endor findings.",
                "Investigate an Endor vulnerability and explain its impact.",
                "Plan a safe dependency remediation using Endor evidence.",
            ],
            "brandColor": "#4F46E5",
            "composerIcon": "./assets/composer-icon.png",
            "logo": "./assets/logo.png",
        },
    }


def _single_line(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"
