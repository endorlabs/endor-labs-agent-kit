"""Shared Generated Agent README fragments."""

from __future__ import annotations

from endor_agent_kit.recipe import EndorAgentRecipe


def architecture_readme_section(recipe: EndorAgentRecipe) -> list[str]:
    """Return the shared architecture section for Generated Agent READMEs."""

    body = {
        "ai-sast-triage": (
            "In Agent Kit, PR/MR creation is host-mediated. Claude Code runs in the target "
            "checkout, gathers Endor evidence including exploit reproduction and remediation "
            "guidance when present, applies the confirmed diff locally, creates and pushes a "
            "branch, then opens the change request with configured source-provider credentials. "
            "If the host cannot perform one of those steps, the agent must stop and report the "
            "missing capability in `data_gaps`."
        ),
        "upgrade-impact-analysis": (
            "This read-only agent resolves a human project selector to the Endor project used "
            "for VersionUpgrade queries. Claude Managed Agents do not inspect local git by "
            "default, so sessions should provide a repository URL, owner/repo, or Endor "
            "project name instead of requiring a project UUID."
        ),
        "remediation-planner": (
            "This dry-run workflow resolves project or finding context, gathers Endor "
            "remediation evidence, and returns a plan only. It does not edit files, push "
            "branches, or open PRs/MRs."
        ),
        "sca-remediation": (
            "This mutating Claude Code agent resolves repository context, queries Endor "
            "SCA findings, requires VersionUpgrade/UIA evidence before recommending a "
            "best first fix, keeps non-breaking low-risk UIA PR candidates separate "
            "from the P0/exploited queue and risky solver, resolves risky or "
            "CIA-indeterminate upgrades into a deterministic risk_decision, prepares "
            "local dependency changes, runs ecosystem-appropriate validation when "
            "possible, and opens a PR/MR only after explicit approval. "
            "It does not use or require an Endor MCP server."
        ),
    }.get(
        recipe.id,
        "This diagram shows the generated agent contract, host responsibilities, and external systems required at runtime.",
    )
    return [
        "## Architecture",
        "",
        f"![{recipe.name} architecture](architecture.svg)",
        "",
        body,
        "",
    ]
