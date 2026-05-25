"""Codex Host Adapter for artifact publication."""

from __future__ import annotations

import shutil
from pathlib import Path

from endor_agent_kit.compilers.codex import HOST, compile_codex_prepared
from endor_agent_kit.compilers.raw import compile_raw_prepared
from endor_agent_kit.prepared_source_recipe import PreparedSourceRecipe
from endor_agent_kit.recipe import EndorAgentRecipe
from endor_agent_kit.safety_posture import source_recipe_safety_posture

from .readme import architecture_readme_section
from .records import (
    BundleRecord,
    artifact_bundle_record,
    prepared_actions_source,
    prepared_architecture_source,
)


class CodexHostAdapter:
    """Publish Codex skill artifacts."""

    host = HOST

    def publish(
        self,
        prepared: PreparedSourceRecipe,
        destination: Path,
    ) -> BundleRecord:
        """Publish one Codex Host Artifact Bundle."""

        compile_raw_prepared(prepared)
        compile_codex_prepared(prepared)

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

        architecture = prepared_architecture_source(prepared)
        has_architecture = architecture.is_file()

        readme = agent_root / "README.md"
        readme.write_text(codex_readme(recipe, has_architecture=has_architecture), encoding="utf-8")
        written.append(readme)

        if has_architecture:
            published_architecture = agent_root / "architecture.svg"
            published_architecture.write_text(
                codex_text(architecture.read_text(encoding="utf-8")),
                encoding="utf-8",
            )
            written.append(published_architecture)

        actions = prepared_actions_source(prepared)
        if actions.is_file():
            published_actions = agent_root / "actions.yaml"
            published_actions.write_text(
                codex_text(actions.read_text(encoding="utf-8")),
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
                    "codex-skill",
                    "Codex Skill",
                    agent_root,
                    requires_endorctl=recipe.requires_endorctl
                    if _needs_endorctl_setup(recipe)
                    else "",
                ),
            ),
        )


def codex_readme(recipe: EndorAgentRecipe, *, has_architecture: bool = False) -> str:
    """Render the Codex Generated Agent README."""

    posture = source_recipe_safety_posture(recipe)
    if posture.is_mutating:
        requirements = [
            "Codex with filesystem and terminal access to the target repository.",
            "Endor tenant access through authenticated `endorctl api` or documented Endor API credentials.",
            "Git and source-provider credentials for approved branch, PR/MR, review, or comment workflows.",
        ]
        if recipe.id == "ai-sast-triage":
            requirements.extend(
                [
                    "A configured AppSec approver list before standalone exception-policy creation.",
                    "Endor policy-write access only after verified AppSec approval and explicit user confirmation.",
                ]
            )
    else:
        requirements = [
            "Codex with access to the current workspace.",
            "The Endor access path declared by the recipe.",
            "No mutating repository, source-provider, or Endor writes for this skill.",
        ]
    return "\n".join(
        [
            f"# {recipe.name} Codex Skill",
            "",
            recipe.description.strip(),
            "",
            "## Install",
            "",
            "Copy this generated skill directory into your Codex skills directory:",
            "",
            "```bash",
            "mkdir -p \"${CODEX_HOME:-$HOME/.codex}/skills\"",
            f"cp -R /path/to/endor-labs-agent-kit/codex/{recipe.id} \\",
            f"  \"${{CODEX_HOME:-$HOME/.codex}}/skills/{recipe.id}\"",
            "```",
            "",
            "Start a new Codex session after installing or replacing the skill.",
            "",
            "## Requirements",
            "",
            *[f"- {item}" for item in requirements],
            "",
            "## Example",
            "",
            "```text",
            codex_example_prompt(recipe),
            "```",
            "",
            *codex_example_workflow_section(recipe),
            *codex_smoke_test_section(recipe),
            *(codex_architecture_readme_section(recipe) if has_architecture else []),
            "## Notes",
            "",
            "- `SKILL.md` is generated from the source recipe and should not be hand-edited in installed copies.",
            "- `actions.yaml` records semantic side-effect contracts when the recipe declares mutating actions.",
            "- Keep host-specific approval gates intact: local edits, branch pushes, PR/MR creation, PR/MR comments, and Endor policy writes are separate decisions.",
            "",
        ]
    )


def codex_example_prompt(recipe: EndorAgentRecipe) -> str:
    """Return the Codex example prompt for one recipe."""

    if recipe.id == "ai-sast-triage":
        return "Use the ai-sast-triage skill to triage AI SAST findings for this repository. Do not edit files, open a PR/MR, or create an Endor policy unless I approve the specific gate."
    if recipe.id == "probe-droid":
        return "Use the probe-droid skill to probe GitHub org <org> for Endor monitored-branch onboarding gaps and setup prescriptions. Keep the workflow read-only."
    if recipe.id == "sca-remediation":
        return "Use the sca-remediation skill to check this repository for P0 SCA findings I can start remediating. Do not edit files or open a PR/MR until I approve."
    return f"Use the {recipe.id} skill to help with this Endor Labs workflow."


def codex_text(text: str) -> str:
    """Adapt Generated Agent README text for Codex wording."""

    return (
        text.replace("Claude Code session", "Codex session")
        .replace("Claude Code artifact", "Codex skill")
        .replace("Claude Code agent", "Codex skill")
        .replace("Claude Code runs", "Codex runs")
        .replace("Claude Code", "Codex")
    )


def codex_architecture_readme_section(recipe: EndorAgentRecipe) -> list[str]:
    """Return the Codex architecture README section."""

    return [codex_text(line) for line in architecture_readme_section(recipe)]


def codex_example_workflow_section(recipe: EndorAgentRecipe) -> list[str]:
    """Return Codex example workflow README content."""

    if recipe.id == "sca-remediation":
        return [
            "## Example Workflow",
            "",
            "```text",
            "Use the sca-remediation skill to show me the other non-breaking low-risk UIA-backed PRs for this repository. Keep this separate from the P0/exploited queue and risky solver. Do not edit files, create branches, push, or open a PR/MR.",
            "```",
            "",
            "```text",
            "Use the sca-remediation skill to prepare the top UIA-backed dependency remediation for this repository. Show the selected package, affected manifests, VersionUpgrade/UIA UUID, risk, CIA status, risk_decision, findings fixed, folded advisory/finding list, validation command, branch name, PR/MR title, and body before changing files.",
            "```",
            "",
        ]
    if recipe.id == "probe-droid":
        return [
            "## Example Workflow",
            "",
            "```text",
            "Use the probe-droid skill to probe GitHub org <org> for Endor monitored-branch onboarding gaps and setup prescriptions. Keep the workflow read-only, do not run scans, do not clone repositories, and separate not-onboarded repositories from already-onboarded repositories with dependency resolution or reachability gaps.",
            "```",
            "",
            "```text",
            "Use the probe-droid skill to compare these GitHub repositories with Endor namespace <namespace>: <owner/repo>, <owner/repo>. Report the top setup actions for missing package manager integrations, scan profile/toolchain gaps, dependency resolution blockers, reachability blockers, and GitHub App selection gaps.",
            "```",
            "",
        ]
    if recipe.id != "ai-sast-triage":
        return []
    return [
        "## Example Workflow",
        "",
        "```text",
        "Use the ai-sast-triage skill to triage AI SAST findings for this repository. Do not edit files, open a PR/MR, or create an Endor policy. Show confirmed true positives, likely false positives, inconclusive findings, exploit-driven priority, remediation-guidance usage, and data gaps.",
        "```",
        "",
        "```text",
        "Use the ai-sast-triage skill to remediate finding <finding_uuid> for this repository. Use Endor Exploit Reproduction and Remediation Guidance as context, but verify the fix against the source. Show me the patch, branch name, PR/MR title, and PR/MR body before pushing. After I approve, open exactly one PR/MR.",
        "```",
        "",
        "Use the exception workflow only when a finding should be excepted instead",
        "of remediated in code.",
        "",
        "```text",
        "Use the ai-sast-triage skill to verify AppSec approval on PR/MR <pr_or_mr_url> for finding <finding_uuid>. Allowed AppSec approvers: @alice, @bob. If approval is valid and not self-approval, check for an existing active Endor exception policy for this finding/project/reason, then render the Endor exception policy spec for my confirmation. After I confirm, create or reuse the scoped policy and comment on the PR/MR with the policy name, policy UUID, Endor project, approver, expiration, and evidence URL.",
        "```",
        "",
    ]


def codex_smoke_test_section(recipe: EndorAgentRecipe) -> list[str]:
    """Return Codex smoke test README content."""

    if recipe.id not in {"ai-sast-triage", "probe-droid", "sca-remediation"}:
        return []
    return [
        "## QA Smoke Test",
        "",
        "Use a fresh Codex session after installing the skill. Run a planning-only",
        "prompt first and verify the response references the Codex skill, preserves",
        "approval gates, and does not claim file edits, PR/MR creation, comments, or",
        "Endor policy writes.",
        "",
    ]


def _needs_endorctl_setup(recipe: EndorAgentRecipe) -> bool:
    posture = source_recipe_safety_posture(recipe)
    return posture.requires_endorctl_setup
