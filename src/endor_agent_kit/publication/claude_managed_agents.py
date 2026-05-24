"""Claude Managed Agents Host Adapter for artifact publication."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from endor_agent_kit.compilers.claude_code import (
    EDITIONS,
    _allows_read_only_endorctl,
    _uses_mcp,
)
from endor_agent_kit.compilers.claude_managed_agents import HOST, compile_claude_managed_agents
from endor_agent_kit.compilers.raw import compile_raw
from endor_agent_kit.recipe import EndorAgentRecipe, editions_for_host

from .readme import architecture_readme_section
from .records import (
    BundleRecord,
    actions_source,
    architecture_source,
    artifact_bundle_record,
)


class ClaudeManagedAgentsHostAdapter:
    """Publish Claude Managed Agents artifacts."""

    host = HOST

    def publish(
        self,
        recipe_file: Path,
        recipe: EndorAgentRecipe,
        destination: Path,
    ) -> BundleRecord:
        """Publish one Claude Managed Agents Host Artifact Bundle."""

        compile_raw(recipe_file)
        compile_claude_managed_agents(recipe_file)

        agent_root = destination / HOST / recipe.id
        if agent_root.exists():
            shutil.rmtree(agent_root)

        written: list[Path] = []
        manifest_records: list[dict[str, Any]] = []
        architecture = architecture_source(recipe_file)
        has_architecture = architecture.is_file()
        editions = editions_for_host(recipe, HOST, EDITIONS)
        flat_layout = len(editions) == 1
        for edition in editions:
            edition_dir = _published_edition_dir(agent_root, editions, edition)
            edition_dir.mkdir(parents=True, exist_ok=True)
            source_dir = recipe_file.parent / "dist" / HOST / edition

            for filename in ("agent.yaml", "environment.yaml", "session-template.yaml"):
                artifact = edition_dir / filename
                shutil.copyfile(source_dir / filename, artifact)
                written.append(artifact)

            readme = edition_dir / "README.md"
            readme.write_text(
                managed_agents_edition_readme(
                    recipe,
                    edition,
                    has_architecture=has_architecture,
                    show_edition_name=not flat_layout,
                ),
                encoding="utf-8",
            )
            written.append(readme)

            if has_architecture:
                published_architecture = edition_dir / "architecture.svg"
                shutil.copyfile(architecture, published_architecture)
                written.append(published_architecture)

            actions = actions_source(recipe_file, recipe)
            if actions.is_file():
                published_actions = edition_dir / "actions.yaml"
                shutil.copyfile(actions, published_actions)
                written.append(published_actions)

            if edition == "enterprise-edition" and _allows_read_only_endorctl(recipe):
                setup = edition_dir / "endorctl-setup.md"
                shutil.copyfile(recipe_file.parent / "dist" / "raw" / "endorctl-setup.md", setup)
                written.append(setup)

            manifest_records.append(
                artifact_bundle_record(
                    destination,
                    recipe,
                    edition,
                    edition_name(edition),
                    edition_dir,
                    requires_endorctl=recipe.requires_endorctl
                    if edition == "enterprise-edition" and _allows_read_only_endorctl(recipe)
                    else "",
                )
            )
        return BundleRecord(
            host=HOST,
            written=tuple(written),
            manifest_records=tuple(manifest_records),
        )


def managed_agents_edition_readme(
    recipe: EndorAgentRecipe,
    edition: str,
    *,
    has_architecture: bool = False,
    show_edition_name: bool = True,
) -> str:
    """Render the Claude Managed Agents Generated Agent README."""

    name = edition_name(edition)
    title = f"{recipe.name} {name}" if show_edition_name else recipe.name
    artifact_label = "edition" if show_edition_name else "agent"
    if edition == "developer-edition" or not _allows_read_only_endorctl(recipe):
        requirements = [
            "Anthropic Console or `ant` CLI access to Claude Managed Agents.",
            "A remote Endor MCP server URL configured in agent.yaml.",
            "An Anthropic credential vault referenced from session-template.yaml when MCP auth is required.",
            f"No pre-built Bash or filesystem tools are enabled for this {artifact_label}.",
        ]
        notes = [
            f"This {artifact_label} uses the Managed Agents MCP connector only.",
            "The generated `agent.yaml` intentionally uses a placeholder MCP URL that must be replaced.",
            "Unavailable MCP, vault, auth, or account-tier signals are reported in data_gaps.",
        ]
    else:
        requirements = [
            "Anthropic Console or `ant` CLI access to Claude Managed Agents.",
            "An environment that can install and authenticate endorctl for the read-only API lookups documented in endorctl-setup.md.",
        ]
        if _uses_mcp(recipe):
            requirements[1:1] = [
                "A remote Endor MCP server URL configured in agent.yaml.",
                "An Anthropic credential vault referenced from session-template.yaml when MCP auth is required.",
            ]
        notes = [
            (
                f"This {artifact_label} uses MCP first, then read-only endorctl api lookups for richer signals."
                if _uses_mcp(recipe)
                else f"This {artifact_label} uses read-only endorctl api lookups and does not require Endor MCP."
            ),
            "The generated `agent.yaml` enables only the Managed Agents Bash tool from the pre-built toolset, with confirmation required.",
            "Bash use remains limited by prompt to the documented Endor lookup commands.",
        ]

    architecture = architecture_readme_section(recipe) if has_architecture else []
    return "\n".join([
        f"# {title}",
        "",
        recipe.description.strip(),
        "",
        "## Install",
        "",
        "Update placeholders in `agent.yaml`, `environment.yaml`, and",
        "`session-template.yaml`, then create the agent and environment in",
        "Claude Managed Agents.",
        "",
        "```bash",
        "ant beta:agents create < agent.yaml",
        "ant beta:environments create < environment.yaml",
        "```",
        "",
        "Use `session-template.yaml` as the starting point for session creation after",
        "you have the created agent ID, environment ID, and any required vault IDs.",
        "",
        "## Requirements",
        "",
        *[f"- {item}" for item in requirements],
        "",
        "## Example User Message",
        "",
        "```text",
        managed_example_prompt(recipe, edition),
        "```",
        "",
        *architecture,
        "## Notes",
        "",
        *[f"- {item}" for item in notes],
        "",
    ])


def edition_name(edition: str) -> str:
    """Return a human-readable Claude Managed Agents edition name."""

    if edition == "developer-edition":
        return "Developer Edition"
    if edition == "enterprise-edition":
        return "Enterprise Edition"
    raise ValueError(f"Unknown edition {edition!r}")


def managed_example_prompt(recipe: EndorAgentRecipe, edition: str = "enterprise-edition") -> str:
    """Return the Claude Managed Agents example prompt for one recipe."""

    input_names = {field.name for field in recipe.inputs}
    if recipe.id == "ai-sast-triage":
        return "Triage AI SAST findings for this repository. Do not open a PR until I approve the patch."
    if recipe.id == "remediation-planner":
        return "Preview remediation options for repository <owner>/<repo>."
    if "vulnerability_id" in input_names:
        return "Explain CVE-2021-44228."
    if recipe.id == "upgrade-impact-analysis":
        if edition == "developer-edition":
            return "Assess upgrading npm lodash from 4.17.20 to 4.17.21."
        return "Show the safest upgrade path for repository <owner>/<repo> package lodash, including CIA, findings fixed, manifest files, and breaking changes."
    if recipe.id == "package-risk-summary":
        return "Summarize npm lodash version 4.17.20."
    if {"ecosystem", "package_name", "version"}.issubset(input_names):
        return "Assess npm lodash version 4.17.20."
    return "Help me use this Endor Labs agent."


def _published_edition_dir(agent_root: Path, editions: tuple[str, ...], edition: str) -> Path:
    if len(editions) == 1:
        return agent_root
    return agent_root / edition
