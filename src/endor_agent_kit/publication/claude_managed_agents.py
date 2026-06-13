"""Claude Managed Agents Host Adapter for artifact publication."""

from __future__ import annotations

import shutil
from pathlib import Path

from endor_agent_kit.catalog_schema import CatalogBundle
from endor_agent_kit.compilers.rendering import EDITIONS
from endor_agent_kit.compilers.claude_managed_agents import HOST, compile_claude_managed_agents_prepared
from endor_agent_kit.compilers.raw import compile_raw_prepared
from endor_agent_kit.prepared_source_recipe import PreparedSourceRecipe
from endor_agent_kit.recipe import EndorAgentRecipe, editions_for_host
from endor_agent_kit.safety_posture import (
    GITHUB_EVIDENCE_AGENT_IDS,
    source_recipe_safety_posture,
)

from .readme import agent_readme_start_here, architecture_readme_section
from .records import (
    BundleRecord,
    artifact_bundle_record,
    prepared_actions_source,
    prepared_architecture_source,
)


class ClaudeManagedAgentsHostAdapter:
    """Publish Claude Managed Agents artifacts."""

    host = HOST

    def publish(
        self,
        prepared: PreparedSourceRecipe,
        destination: Path,
    ) -> BundleRecord:
        """Publish one Claude Managed Agents Host Artifact Bundle."""

        compile_raw_prepared(prepared)
        compile_claude_managed_agents_prepared(prepared)

        recipe_file = prepared.path
        recipe = prepared.recipe
        agent_root = destination / HOST / recipe.id
        if agent_root.exists():
            shutil.rmtree(agent_root)

        written: list[Path] = []
        manifest_records: list[CatalogBundle] = []
        architecture = prepared_architecture_source(prepared)
        has_architecture = architecture.is_file()
        editions = editions_for_host(recipe, HOST, EDITIONS)
        flat_layout = len(editions) == 1
        posture = source_recipe_safety_posture(recipe)
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

            actions = prepared_actions_source(prepared)
            if actions.is_file():
                published_actions = edition_dir / "actions.yaml"
                shutil.copyfile(actions, published_actions)
                written.append(published_actions)

            if edition == "enterprise-edition" and posture.uses_endorctl_api:
                setup = edition_dir / "endorctl-setup.md"
                shutil.copyfile(recipe_file.parent / "dist" / "raw" / "endorctl-setup.md", setup)
                written.append(setup)

            manifest_records.append(
                artifact_bundle_record(
                    destination,
                    recipe,
                    HOST,
                    edition,
                    edition_name(edition),
                    edition_dir,
                    requires_endorctl=recipe.requires_endorctl
                    if edition == "enterprise-edition" and posture.uses_endorctl_api
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
    posture = source_recipe_safety_posture(recipe)
    if edition == "developer-edition" or not posture.uses_endorctl_api:
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
        if posture.uses_mcp:
            requirements[1:1] = [
                "A remote Endor MCP server URL configured in agent.yaml.",
                "An Anthropic credential vault referenced from session-template.yaml when MCP auth is required.",
            ]
        notes = [
            (
                f"This {artifact_label} uses MCP first, then read-only endorctl api lookups for richer signals."
                if posture.uses_mcp
                else f"This {artifact_label} uses read-only endorctl api lookups and does not require Endor MCP."
            ),
            "The generated `agent.yaml` enables only the Managed Agents Bash tool from the pre-built toolset, with confirmation required.",
            "Bash use remains limited by prompt to the documented Endor lookup commands.",
        ]
        if _uses_github_evidence(recipe):
            requirements.append(
                "Read-only GitHub.com credentials available to the managed session, or exported GitHub inventory JSON supplied in the prompt."
            )
            if recipe.id == "cicd-posture":
                notes = [
                    f"This {artifact_label} assesses CI/CD and supply chain posture from existing Endor findings plus read-only GitHub repository configuration evidence.",
                    "It uses read-only Endor and GitHub lookups to produce dimension scores, critical overrides, evidence queries, recommended actions, and data gaps.",
                    "The generated environment allows api.endorlabs.com plus GitHub.com/API hosts for read-only evidence. It still must not run scans, clone repositories, dispatch workflows, change branch protection or repository settings, open PRs/MRs, or mutate Endor state.",
                ]
            else:
                notes = [
                    f"This {artifact_label} compares GitHub.com repository inventory with Endor project, GitHub App, package, monitored-branch scan, scan profile, toolchain, and package-manager evidence.",
                    "It uses read-only Endor and GitHub lookups to produce onboarding lanes, reason codes, evidence queries, and setup prescriptions.",
                    "The generated environment allows api.endorlabs.com plus GitHub.com/API hosts for read-only inventory. It still must not run scans, clone repositories, create profiles, update package manager integrations, change GitHub settings, open PRs/MRs, or mutate Endor state.",
                ]
        elif recipe.id == "endor-troubleshooter":
            notes = [
                f"This {artifact_label} diagnoses Endor Labs errors, warnings, missing integrations, scan failures, slow scans, and unhealthy configuration from user-provided issue text plus read-only Endor evidence.",
                "It returns a troubleshooting verdict, issue lanes, evidence queries, root-cause hypotheses, low-friction repair guidance, validation steps, and gated future action contracts.",
                "The generated environment allows api.endorlabs.com for read-only Endor lookups. It still must not run scans, create scan log requests, change credentials, edit scan profiles, update integrations, post comments, open PRs/MRs, or mutate Endor state.",
            ]

    architecture = architecture_readme_section(recipe) if has_architecture else []
    start_here = agent_readme_start_here(
        recipe,
        host_label="Claude Managed Agents",
        artifact_label=artifact_label,
        install_summary="Update generated YAML placeholders, then create the managed agent and environment.",
        run_summary=managed_example_prompt(recipe, edition),
        has_architecture=has_architecture,
    )
    return "\n".join([
        f"# {title}",
        "",
        recipe.description.strip(),
        "",
        *start_here,
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
    if recipe.id == "probe-droid":
        return "Probe GitHub org <org> for Endor monitored-branch onboarding gaps and setup prescriptions. Keep the workflow read-only."
    if recipe.id == "cicd-posture":
        return "Assess CI/CD and supply chain posture for namespace <namespace>. Keep the workflow read-only."
    if recipe.id == "endor-troubleshooter":
        return "Diagnose this Endor scan failure from redacted error text and read-only tenant evidence. Keep the workflow read-only."
    if {"ecosystem", "package_name", "version"}.issubset(input_names):
        return "Assess npm lodash version 4.17.20."
    return "Help me use this Endor Labs agent."


def _published_edition_dir(agent_root: Path, editions: tuple[str, ...], edition: str) -> Path:
    if len(editions) == 1:
        return agent_root
    return agent_root / edition


def _uses_github_evidence(recipe: EndorAgentRecipe) -> bool:
    return recipe.id in GITHUB_EVIDENCE_AGENT_IDS
