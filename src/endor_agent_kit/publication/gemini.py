"""Gemini CLI Host Adapter for artifact publication."""

from __future__ import annotations

import shutil
from pathlib import Path

from endor_agent_kit.compilers.gemini import HOST, compile_gemini_prepared
from endor_agent_kit.prepared_source_recipe import PreparedSourceRecipe
from endor_agent_kit.recipe import EndorAgentRecipe
from endor_agent_kit.safety_posture import source_recipe_safety_posture

from .readme import agent_readme_start_here, architecture_readme_section
from .records import (
    BundleRecord,
    artifact_bundle_record,
    prepared_actions_source,
    prepared_architecture_source,
)


class GeminiHostAdapter:
    """Publish Gemini CLI skill and subagent artifacts."""

    host = HOST

    def publish(
        self,
        prepared: PreparedSourceRecipe,
        destination: Path,
    ) -> BundleRecord:
        """Publish one Gemini CLI Host Artifact Bundle."""

        compile_gemini_prepared(prepared)

        recipe_file = prepared.path
        recipe = prepared.recipe
        agent_root = destination / HOST / recipe.id
        if agent_root.exists():
            shutil.rmtree(agent_root)
        agent_root.mkdir(parents=True, exist_ok=True)

        written: list[Path] = []
        source_dir = recipe_file.parent / "dist" / HOST / recipe.id
        skill = agent_root / "SKILL.md"
        shutil.copyfile(source_dir / "SKILL.md", skill)
        written.append(skill)

        agent = agent_root / f"{recipe.id}.md"
        shutil.copyfile(source_dir / f"{recipe.id}.md", agent)
        written.append(agent)

        architecture = prepared_architecture_source(prepared)
        has_architecture = architecture.is_file()

        readme = agent_root / "README.md"
        readme.write_text(gemini_readme(recipe, has_architecture=has_architecture), encoding="utf-8")
        written.append(readme)

        if has_architecture:
            published_architecture = agent_root / "architecture.svg"
            published_architecture.write_text(
                gemini_text(architecture.read_text(encoding="utf-8")),
                encoding="utf-8",
            )
            written.append(published_architecture)

        actions = prepared_actions_source(prepared)
        if actions.is_file():
            published_actions = agent_root / "actions.yaml"
            published_actions.write_text(
                gemini_text(actions.read_text(encoding="utf-8")),
                encoding="utf-8",
            )
            written.append(published_actions)

        if _needs_endorctl_setup(recipe):
            setup = agent_root / "endorctl-setup.md"
            shutil.copyfile(recipe_file.parent / "dist" / "raw" / "endorctl-setup.md", setup)
            written.append(setup)

        return BundleRecord(
            host=HOST,
            written=tuple(written),
            manifest_records=(
                artifact_bundle_record(
                    destination,
                    recipe,
                    HOST,
                    "gemini-cli",
                    "Gemini CLI Skill And Subagent",
                    agent_root,
                    requires_endorctl=recipe.requires_endorctl
                    if _needs_endorctl_setup(recipe)
                    else "",
                ),
            ),
        )


def gemini_readme(recipe: EndorAgentRecipe, *, has_architecture: bool = False) -> str:
    """Render the Gemini CLI generated agent README."""

    posture = source_recipe_safety_posture(recipe)
    if posture.is_mutating:
        requirements = [
            "Gemini CLI with filesystem and terminal access to the target repository.",
            f"Endor tenant access through authenticated `endorctl agent api --agent-id {recipe.id}`.",
            "Git and source-provider credentials for approved branch, PR/MR, review, or comment workflows.",
        ]
        if recipe.id == "ai-sast-remediation":
            requirements.extend([
                "A configured AppSec approver list before standalone exception-policy creation.",
                "Endor policy-write access only after verified AppSec approval and explicit user confirmation.",
            ])
    else:
        requirements = [
            "Gemini CLI with access to the current workspace.",
            "The Endor access path declared by the recipe.",
            "No mutating repository, source-provider, or Endor writes for this workflow.",
        ]
    notes = [
        "- `SKILL.md` and the subagent markdown are generated from the source recipe and should not be hand-edited in installed copies.",
        "- The plugin package installs the skill under `skills/<agent>/` and the subagent under `agents/<agent>.md`.",
        "- Keep host-specific approval gates intact: local edits, branch pushes, PR/MR creation, PR/MR comments, and Endor policy writes are separate decisions.",
    ]
    if posture.is_mutating:
        notes.append(
            "- `actions.yaml` records semantic side-effect contracts when the recipe declares mutating actions."
        )
    else:
        notes.append("- This read-only workflow must report unavailable signals in `data_gaps`.")
    start_here = agent_readme_start_here(
        recipe,
        host_id=HOST,
        host_label="Gemini CLI",
        artifact_label="skill and subagent bundle",
        install_summary="Prefer the generated Gemini extension under `plugins/gemini/endor-labs-agent-kit`, then restart Gemini CLI.",
        run_summary=gemini_example_prompt(recipe),
        has_architecture=has_architecture,
    )
    return "\n".join([
        f"# {recipe.name} Gemini CLI Bundle",
        "",
        recipe.description.strip(),
        "",
        *start_here,
        "## Install Through The Generated Extension",
        "",
        "Prefer the generated extension package under `plugins/gemini/endor-labs-agent-kit`.",
        "",
        "```bash",
        "gemini extensions install /path/to/endor-labs-agent-kit/plugins/gemini/endor-labs-agent-kit",
        "```",
        "",
        "Restart Gemini CLI after installing or updating the extension.",
        "",
        "## Manual Fallback",
        "",
        "Copy this bundle into a custom Gemini extension or install the skill and",
        "subagent manually under your Gemini configuration.",
        "",
        "## Requirements",
        "",
        *[f"- {item}" for item in requirements],
        "",
        "## Example",
        "",
        "```text",
        gemini_example_prompt(recipe),
        "```",
        "",
        *gemini_example_workflow_section(recipe),
        *(gemini_architecture_readme_section(recipe) if has_architecture else []),
        "## Notes",
        "",
        *notes,
        "",
    ])


def gemini_example_prompt(recipe: EndorAgentRecipe) -> str:
    """Return the Gemini CLI example prompt for one recipe."""

    if recipe.id == "ai-sast-remediation":
        return "Use @ai-sast-remediation to triage AI SAST findings for this repository. Do not edit files, open a PR/MR, or create an Endor policy unless I approve the specific gate."
    if recipe.id == "cicd-posture":
        return "Use @cicd-posture to assess CI/CD and supply chain posture for namespace <namespace>. Keep it read-only and validate the deterministic score."
    if recipe.id == "configuration-automation":
        return "Use @configuration-automation to probe GitHub org <org> for Endor monitored-branch onboarding gaps and setup prescriptions. Keep the workflow read-only."
    if recipe.id == "troubleshooting":
        return "Use @troubleshooting to diagnose this Endor issue from redacted error text and read-only tenant evidence. Keep the workflow read-only."
    if recipe.id == "sca-remediation":
        return "Use @sca-remediation to check this repository for P0 SCA findings I can start remediating. Do not edit files or open a PR/MR until I approve."
    return f"Use @{recipe.id} to help with this Endor Labs workflow."


def gemini_text(text: str) -> str:
    """Adapt generated text for Gemini CLI wording."""

    return (
        text.replace("Claude Code session", "Gemini CLI session")
        .replace("Claude Code artifact", "Gemini CLI artifact")
        .replace("Claude Code agent", "Gemini CLI subagent")
        .replace("Claude Code runs", "Gemini CLI runs")
        .replace("Claude Code", "Gemini CLI")
        .replace("Codex session", "Gemini CLI session")
        .replace("Codex skill", "Gemini CLI skill")
        .replace("Codex", "Gemini CLI")
    )


def gemini_architecture_readme_section(recipe: EndorAgentRecipe) -> list[str]:
    """Return the Gemini architecture README section."""

    return [gemini_text(line) for line in architecture_readme_section(recipe)]


def gemini_example_workflow_section(recipe: EndorAgentRecipe) -> list[str]:
    """Return Gemini CLI example workflow README content."""

    if recipe.id == "sca-remediation":
        return [
            "## Example Workflow",
            "",
            "```text",
            "Use @sca-remediation to show me the other non-breaking low-risk UIA-backed PRs for this repository. Keep this separate from the P0/exploited queue and risky solver. Do not edit files, create branches, push, or open a PR/MR.",
            "```",
            "",
            "```text",
            "Use @sca-remediation to prepare the top UIA-backed dependency remediation for this repository. Show the selected package, affected manifests, VersionUpgrade/UIA UUID, risk, CIA status, risk_decision, findings fixed, folded advisory/finding list, validation command, branch name, PR/MR title, and body before changing files.",
            "```",
            "",
        ]
    if recipe.id == "configuration-automation":
        return [
            "## Example Workflow",
            "",
            "```text",
            "Use @configuration-automation to probe GitHub org <org> for Endor monitored-branch onboarding gaps and setup prescriptions. Keep the workflow read-only, do not run scans, do not clone repositories, and separate not-onboarded repositories from already-onboarded repositories with dependency resolution or reachability gaps.",
            "```",
            "",
        ]
    if recipe.id == "cicd-posture":
        return [
            "## Example Workflow",
            "",
            "```text",
            "Use @cicd-posture to assess CI/CD and supply chain posture for Endor namespace <namespace> and GitHub org <org>. Include Endor SCPM, CICD, GHACTIONS, and SUPPLY_CHAIN findings, branch protection, CODEOWNERS, action pinning, permissions, risky triggers, self-hosted runners, update automation, deterministic scores, critical overrides, evidence_queries, and data_gaps. Do not run scans or mutate anything.",
            "```",
            "",
            "```text",
            "Use @cicd-posture for these repositories only: <owner/repo>, <owner/repo>. Compute raw_counts, dimension_scores, score_validation, and recommended human actions without editing workflows or branch protection.",
            "```",
            "",
        ]
    if recipe.id == "troubleshooting":
        return [
            "## Example Workflow",
            "",
            "```text",
            "Use @troubleshooting to diagnose this Endor scan failure. Namespace: <namespace>. Project: <project>. Error: <redacted error text>. Keep the workflow read-only and tell me the lowest-friction fix.",
            "```",
            "",
        ]
    if recipe.id != "ai-sast-remediation":
        return []
    return [
        "## Example Workflow",
        "",
        "```text",
        "Use @ai-sast-remediation to triage AI SAST findings for this repository. Do not edit files, open a PR/MR, or create an Endor policy. Show confirmed true positives, likely false positives, inconclusive findings, exploit-driven priority, remediation-guidance usage, and data gaps.",
        "```",
        "",
    ]


def _needs_endorctl_setup(recipe: EndorAgentRecipe) -> bool:
    posture = source_recipe_safety_posture(recipe)
    return bool(recipe.requires_endorctl and posture.uses_endor_api_transport)
