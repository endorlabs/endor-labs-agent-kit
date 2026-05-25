"""Claude Code Host Adapter for artifact publication."""

from __future__ import annotations

import shutil
from pathlib import Path

from endor_agent_kit.catalog_schema import CatalogBundle
from endor_agent_kit.compilers.claude_code import (
    EDITIONS,
    HOST,
    compile_claude_code_prepared,
)
from endor_agent_kit.compilers.raw import compile_raw_prepared
from endor_agent_kit.prepared_source_recipe import PreparedSourceRecipe
from endor_agent_kit.recipe import EndorAgentRecipe, editions_for_host
from endor_agent_kit.safety_posture import source_recipe_safety_posture

from .readme import architecture_readme_section
from .records import (
    BundleRecord,
    artifact_bundle_record,
    prepared_actions_source,
    prepared_architecture_source,
)


class ClaudeCodeHostAdapter:
    """Publish Claude Code subagent artifacts."""

    host = HOST

    def publish(
        self,
        prepared: PreparedSourceRecipe,
        destination: Path,
    ) -> BundleRecord:
        """Publish one Claude Code Host Artifact Bundle."""

        compile_raw_prepared(prepared)
        compile_claude_code_prepared(prepared)

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
            artifact = edition_dir / f"{recipe.id}.md"
            source_artifact = recipe_file.parent / "dist" / HOST / edition / f"{recipe.id}.md"
            shutil.copyfile(source_artifact, artifact)
            written.append(artifact)

            readme = edition_dir / "README.md"
            readme.write_text(
                claude_code_edition_readme(
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


def claude_code_edition_readme(
    recipe: EndorAgentRecipe,
    edition: str,
    *,
    has_architecture: bool = False,
    show_edition_name: bool = True,
) -> str:
    """Render the Claude Code Generated Agent README."""

    name = edition_name(edition)
    title = f"{recipe.name} {name}" if show_edition_name else recipe.name
    artifact_label = "edition" if show_edition_name else "agent"
    posture = source_recipe_safety_posture(recipe)
    if posture.is_mutating:
        requirements = [
            "Claude Code with the generated subagent file installed.",
            "Endor tenant access through authenticated `endorctl api` or documented Endor API credentials.",
            "A local workspace checkout for any repository the agent will patch.",
            "Git and source-provider credentials that can push a branch and open the requested pull request or merge request.",
        ]
        if recipe.id == "ai-sast-triage":
            requirements.extend(
                [
                    "GitHub or GitLab credentials that can read PR/MR reviews and comments from the target repository.",
                    "A configured AppSec approver list when the agent is allowed to create Endor exception policies in standalone mode.",
                    "Endor policy-write access for direct exception-policy creation after verified AppSec approval.",
                ]
            )
        workflow_label = {
            "ai-sast-triage": "AI SAST triage",
            "sca-remediation": "SCA remediation",
        }.get(recipe.id, recipe.name)
        notes = [
            f"This {artifact_label} preserves the {workflow_label} workflow capabilities as a mutating agent.",
            "The agent may fetch source context, prepare patches, edit files, run commands, open a change request, verify AppSec approval evidence, and create an Endor exception policy when the workflow requires it.",
            "Confirm repository and branch targets before allowing write or pull-request actions. Confirm the rendered Endor policy spec before allowing exception-policy creation.",
        ]
        if recipe.id == "sca-remediation":
            notes = [
                f"This {artifact_label} preserves the SCA remediation workflow capabilities as a mutating agent.",
                "The agent may query Endor SCA findings and VersionUpgrade/UIA evidence, list separate non-breaking low-risk PR-ready candidates, inspect local manifests, produce a deterministic risk_decision, prepare dependency changes, run validation, open a change request, and post a remediation comment when approved.",
                "Confirm the selected package, UIA evidence, risk_decision, target files, generated diff, validation status, branch, and PR/MR body before allowing mutations.",
            ]
        if recipe.action_contracts_path:
            notes.append(
                "`actions.yaml` lists the semantic side effects and any external adapter requirements."
            )
    elif edition == "developer-edition" or not posture.uses_endorctl_api:
        requirements = [
            "Claude Code with the generated subagent file installed.",
            "Endor MCP access through the subagent's bundled MCP server config.",
            f"No shell access or authenticated endorctl setup is required for this {artifact_label}.",
        ]
        if posture.can_read_files:
            requirements.insert(2, "Read-only access to dependency manifests in the target workspace.")
        notes = [
            (
                f"This {artifact_label} uses Endor MCP tools plus Claude Code read-only file inspection."
                if posture.can_read_files
                else f"This {artifact_label} uses Endor MCP tools only."
            ),
            "It records unavailable non-MCP signals in data_gaps rather than fabricating evidence.",
        ]
    else:
        requirements = [
            "Claude Code with the generated subagent file installed.",
            "Authenticated endorctl for the read-only API lookups documented in endorctl-setup.md.",
        ]
        if posture.uses_mcp:
            requirements.insert(
                1,
                "Endor MCP access through the subagent's bundled MCP server config.",
            )
        notes = [
            (
                f"This {artifact_label} uses MCP first, then read-only endorctl api lookups for richer signals."
                if posture.uses_mcp
                else f"This {artifact_label} uses read-only endorctl api lookups and does not require Endor MCP."
            ),
            "Bash use is limited by prompt to the documented Endor lookup commands.",
        ]
        if recipe.id == "probe-droid":
            requirements.append(
                "Read-only GitHub.com credentials through `gh` or exported GitHub repository inventory JSON."
            )
            notes = [
                f"This {artifact_label} compares GitHub.com repository inventory with Endor project, GitHub App, package, monitored-branch scan, scan profile, toolchain, and package-manager evidence.",
                "It uses read-only Endor and GitHub lookups to produce onboarding lanes, reason codes, evidence queries, and setup prescriptions.",
                "It must not run scans, clone repositories, create scan profiles, update package manager integrations, change GitHub settings, open PRs/MRs, or mutate Endor state.",
            ]

    architecture = architecture_readme_section(recipe) if has_architecture else []
    return "\n".join([
        f"# {title}",
        "",
        recipe.description.strip(),
        "",
        "## Install",
        "",
        f"Copy `{recipe.id}.md` into your target repository's `.claude/agents/` directory,",
        "then restart Claude Code if needed.",
        "",
        "## Requirements",
        "",
        *[f"- {item}" for item in requirements],
        "",
        *claude_code_agent_setup_section(recipe),
        "## Example",
        "",
        "```text",
        example_prompt(recipe, edition),
        "```",
        "",
        *claude_code_example_workflow_section(recipe),
        *claude_code_smoke_test_section(recipe),
        *architecture,
        "## Notes",
        "",
        *[f"- {item}" for item in notes],
        "",
    ])


def claude_code_agent_setup_section(
    recipe: EndorAgentRecipe,
) -> list[str]:
    """Return Claude Code setup README content."""

    if recipe.id == "probe-droid":
        return [
            "## Setup Checklist",
            "",
            "### 1. Install The Subagent",
            "",
            "Run this from the target repository or admin workspace where Claude Code",
            "will perform the read-only inventory:",
            "",
            "```bash",
            "mkdir -p .claude/agents",
            "cp /path/to/endor-labs-agent-kit/claude-code/probe-droid/probe-droid.md \\",
            "  .claude/agents/probe-droid.md",
            "```",
            "",
            "### 2. Verify Read-Only Access",
            "",
            "Run these read-only checks when live GitHub inventory is available:",
            "",
            "```bash",
            "endorctl --version",
            "gh auth status        # GitHub inventory",
            "```",
            "",
            "Probe Droid does not need an Endor MCP server. If Endor access, GitHub",
            "read permissions, scan profile data, package manager integration data, or",
            "repository contents are unavailable, the agent should report the missing",
            "setup in `data_gaps`.",
            "",
            "### 3. Keep The Probe Read-Only",
            "",
            "The agent may list GitHub repositories, fetch specific manifest or CI files,",
            "and query Endor projects, GitHub App evidence, monitored-branch scans, packages,",
            "scan profiles, and package manager integrations. It should not run scans,",
            "clone repositories, edit files, change GitHub settings, create profiles,",
            "update integrations, or open PRs/MRs.",
            "",
        ]
    if recipe.id == "sca-remediation":
        return [
            "## Setup Checklist",
            "",
            "### 1. Install The Subagent",
            "",
            "Run this from the target repository where Claude Code will operate:",
            "",
            "```bash",
            "mkdir -p .claude/agents",
            "cp /path/to/endor-labs-agent-kit/claude-code/sca-remediation/sca-remediation.md \\",
            "  .claude/agents/sca-remediation.md",
            "```",
            "",
            "### 2. Verify Local Access",
            "",
            "Run the checks that match your source provider:",
            "",
            "```bash",
            "git remote -v",
            "endorctl --version",
            "endorctl host-check",
            "gh auth status        # GitHub repositories",
            "glab auth status      # GitLab repositories",
            "```",
            "",
            "Claude Code does not need an Endor MCP server for this agent. If `endorctl`,",
            "direct Endor API credentials, local dependency-manager tooling, or",
            "source-provider credentials are not authenticated, the agent should report",
            "the missing setup in `data_gaps`.",
            "",
            "### 3. Prepare For Approval Gates",
            "",
            "The agent shows UIA evidence, risk_decision, target files, diff,",
            "validation plan, branch, and PR/MR body before mutating. Approve file",
            "edits and PR/MR creation as separate steps.",
            "",
            "Validation commands are selected from the repository's actual package",
            "manager and build metadata. The agent should not assume a Maven, npm,",
            "Python, Go, .NET, Ruby, Rust, or any other ecosystem layout until it",
            "has inspected the local manifests and documented build instructions.",
            "",
        ]
    if recipe.id != "ai-sast-triage":
        return []
    return [
        "## Setup Checklist",
        "",
        "### 1. Install The Subagent",
        "",
        "Run this from the target repository where Claude Code will operate:",
        "",
        "```bash",
        "mkdir -p .claude/agents",
        "cp /path/to/endor-labs-agent-kit/claude-code/ai-sast-triage/ai-sast-triage.md \\",
        "  .claude/agents/ai-sast-triage.md",
        "```",
        "",
        "Or ask an LLM with filesystem access to do it:",
        "",
        "```text",
        "Install the Endor Labs AI SAST Triage agent in this repository.",
        "",
        "Agent Kit root: /path/to/endor-labs-agent-kit",
        "Agent artifact: claude-code/ai-sast-triage/ai-sast-triage.md",
        "Install path: .claude/agents/ai-sast-triage.md",
        "",
        "Preserve the generated agent prompt exactly. After installing it, check",
        "endorctl, git remote, and GitHub/GitLab CLI access, then tell",
        "me the exact prompt to invoke the agent.",
        "```",
        "",
        "### 2. Verify Local Access",
        "",
        "Run the checks that match your source provider:",
        "",
        "```bash",
        "git remote -v",
        "endorctl --version",
        "gh auth status        # GitHub repositories",
        "glab auth status      # GitLab repositories",
        "```",
        "",
        "Claude Code does not need an Endor MCP server for this agent. If `endorctl`,",
        "direct Endor API credentials, or source-provider credentials are not",
        "authenticated, the agent should report the missing setup in `data_gaps`.",
        "",
        "### 3. Understand Finding Evidence",
        "",
        "When Endor AI SAST includes `## Exploit Reproduction`, the agent uses it",
        "for priority, confidence, and safe local validation planning. It must not",
        "run exploit steps against live systems or paste weaponized detail into a",
        "PR/MR body.",
        "",
        "When Endor AI SAST includes `## Remediation Guidance`, the agent uses it as",
        "patch context. It can apply the guidance as-is, adapt it to the codebase,",
        "or reject it with a reason when the pinned source or tests show a safer fix.",
        "",
        "### 4. Match The AURI PR/MR Body",
        "",
        "Remediation PR/MR bodies should follow the AURI AI SAST structure:",
        "",
        "- `## 🛡️ Endor Labs AURI Security Fix: <finding title>`",
        "- hidden `<!-- auri:ai-sast-context ... -->` finding/project metadata",
        "- `### 🔧 What changed`",
        "- `### 🔎 Evidence provided by AURI`",
        "- `### ✅ Review checklist`",
        "- `### 📝 Need an exception instead?` with standalone Agent Kit request prompts",
        "- folded `📎 Finding details` table",
        "",
        "Severity must be visually indicated everywhere it is shown: Critical `🔴`,",
        "High `🟠`, Medium `🟡`, and Low `🟢`.",
        "Default to one remediation PR/MR per AI SAST finding so review, validation,",
        "rollback, and exception handling stay traceable. Group findings only when",
        "one small, cohesive source change fixes the same root cause in the same",
        "repository/component or when the user explicitly asks for grouping.",
        "The PR/MR title should start with the visual indicator and highest severity",
        "represented, such as `🟡 Medium: Fix ...` for one finding or",
        "`🟠 High: Fix 3 AI SAST findings` for a tightly grouped fix. Bracket-only",
        "titles like `[Medium] Fix ...` should be treated as invalid.",
        "",
        "When `endor-agent-kit` is available and temporary file writes are allowed,",
        "use it as the source of truth for generated bodies: validate the normalized",
        "AI SAST JSON, render the PR/MR body, and lint the rendered body before",
        "opening the change request.",
        "",
        "### 5. Configure Optional AppSec Approvers",
        "",
        "The exception workflow is optional. You can use the agent for triage and",
        "remediation PR/MRs without configuring AppSec approvers or Endor policy-write",
        "access. If your team wants PR/MR-driven exceptions, standalone exception",
        "creation requires an approval artifact in the PR/MR. Give the agent the",
        "allowed approvers before it creates an Endor exception policy. Use GitHub",
        "handles, GitLab usernames, or team slugs:",
        "",
        "```text",
        "AppSec approvers: @alice, @bob, @endor-labs/appsec",
        "```",
        "",
        "The developer requesting the exception must not approve their own request.",
        "",
        "### 6. Approval Comment Format",
        "",
        "When the agent requests an exception, an AppSec approver should comment or",
        "review with one of these exact forms:",
        "",
        "```text",
        "APPSEC APPROVED: false positive for finding <finding_uuid> - <why this is not exploitable>",
        "APPSEC APPROVED: accept risk for finding <finding_uuid> until YYYY-MM-DD - <owner, mitigation, and why code will not change now>",
        "```",
        "",
        "The agent verifies the approver, finding UUID, request type, and expiration",
        "before it renders the Endor policy spec. In standalone Agent Kit, PR/MR comments are approval evidence only; they do not automatically trigger a",
        "policy write unless a user or external automation invokes the installed",
        "agent.",
        "",
        "### 7. Optional Policy Creation Gate",
        "",
        "The agent may create a scoped Endor exception policy only after all of these",
        "are true:",
        "",
        "- AppSec approval evidence is verified from the PR/MR.",
        "- Existing Endor policies are checked by generated policy name and finding UUID.",
        "- The policy spec is shown in the Claude Code session.",
        "- The user explicitly confirms policy creation.",
        "- Endor returns a policy UUID.",
        "",
        "If an active matching exception policy already exists for the same finding,",
        "project, and reason, the agent should reuse that policy and should not",
        "create a duplicate. The PR/MR decision comment should show the policy name",
        "first, keep the policy UUID for API traceability, and display a human-readable",
        "Endor project label instead of raw `$uuid=...` selector syntax.",
        "",
    ]


def claude_code_example_workflow_section(recipe: EndorAgentRecipe) -> list[str]:
    """Return Claude Code example workflow README content."""

    if recipe.id == "probe-droid":
        return [
            "## Example Workflow",
            "",
            "Use these copy/paste prompts after the agent is installed.",
            "",
            "```text",
            "@agent-probe-droid probe GitHub org <org> for Endor monitored-branch onboarding gaps. Compare GitHub.com repositories with Endor projects, GitHub App coverage, dependency resolution, reachability, scan profiles, toolchains, and package manager integrations. Do not run scans or mutate anything.",
            "```",
            "",
            "```text",
            "@agent-probe-droid compare these GitHub repositories with Endor and prescribe the scan profiles, toolchains, private package integrations, and call graph setup needed for clean monitored-branch onboarding: <repo-url-1>, <repo-url-2>",
            "```",
            "",
            "The result should prioritize shared setup that unblocks the most repositories",
            "first, while separating not-yet-onboarded repositories from onboarded-but-gapped",
            "repositories and keeping PR scan coverage in future scope.",
            "",
        ]
    if recipe.id == "sca-remediation":
        return [
            "## Example Workflow",
            "",
            "Use these copy/paste prompts after the agent is installed.",
            "",
            "### 1. Rank Without Mutating",
            "",
            "```text",
            "@agent-sca-remediation check this repository for P0 SCA findings I can start remediating. Do not edit files or open a PR/MR. Rank package-level fixes and show the UIA evidence for the best first fix.",
            "```",
            "",
            "### 2. List Other Low-Risk PRs",
            "",
            "```text",
            "@agent-sca-remediation show me the other non-breaking low-risk UIA-backed PRs for this repository. Keep this separate from the P0/exploited queue and the risky solver. Do not edit files, create branches, push, or open a PR/MR.",
            "```",
            "",
            "### 3. Prepare One Patch",
            "",
            "```text",
            "@agent-sca-remediation prepare the top UIA-backed dependency remediation for this repository. Show the selected package, affected manifests, VersionUpgrade/UIA UUID, risk, CIA status, risk_decision, findings fixed, folded advisory/finding list, validation command, branch name, PR/MR title, and body before changing files.",
            "```",
            "",
            "### 4. Open The PR/MR After Approval",
            "",
            "```text",
            "@agent-sca-remediation apply the approved patch, run local validation, and then ask me before pushing a branch or opening the PR/MR. Use the AURI-style PR/MR body with emoji sections, UIA evidence, validation status, and a folded advisory/finding list.",
            "```",
            "",
            "Do not call a high-count finding bucket low risk unless the response shows",
            "the actual VersionUpgrade/UIA evidence. Prefer a package-level fix when one",
            "package upgrade clears findings across multiple manifests. Future PR/MR bodies",
            "should include the folded `Advisories This Upgrade Fixes` section, and should",
            "scope compatibility claims to Endor UIA/CIA plus validation that actually ran.",
            "If CIA is indeterminate or risk is medium/high, the agent should produce a",
            "deterministic `risk_decision` from Endor evidence plus local source usage",
            "instead of recommending a manual release-note skim.",
            "The selection/plan gate is not complete until that `risk_decision` is",
            "present; low UIA risk, zero conflicts, and a simple manifest edit are",
            "inputs to the verdict, not replacements for it.",
            "Keep low-risk non-breaking UIA candidates separate from P0/exploited",
            "findings and from the risky solver. Hidden P0 duplicates should be",
            "reported separately and excluded from `most_findings_in_one_pr`.",
            "Choose validation commands from the repository's actual ecosystem and",
            "manifest layout; do not carry Maven or any other package-manager",
            "commands across runs unless the current repository proves that layout.",
            "Use the branch convention `remediation/sca/<package>-<target-version>`",
            "unless the user explicitly asks for a different branch name.",
            "",
        ]
    if recipe.id != "ai-sast-triage":
        return []
    return [
        "## Example Workflow",
        "",
        "Use these copy/paste prompts after the agent is installed. Replace the",
        "placeholders with the finding UUID, PR/MR URL, date, and AppSec approvers",
        "from your environment.",
        "",
        "### 1. Triage Without Mutating",
        "",
        "```text",
        "@agent-ai-sast-triage triage AI SAST findings for this repository. Do not edit files, open a PR/MR, or create an Endor policy. Show confirmed true positives, likely false positives, inconclusive findings, exploit-driven priority, remediation-guidance usage, and data gaps.",
        "```",
        "",
        "### 2. Open One Remediation PR",
        "",
        "```text",
        "@agent-ai-sast-triage remediate finding <finding_uuid> for this repository. Use Endor Exploit Reproduction and Remediation Guidance as context, but verify the fix against the source. Show me the patch, branch name, PR/MR title, and PR/MR body before pushing. After I approve, open exactly one PR/MR.",
        "```",
        "",
        "Use one PR/MR per finding by default. If a single cohesive source change",
        "fixes several findings with the same root cause, use the highest severity",
        "in the title, for example `🟠 High: Fix 3 AI SAST findings`, and list each",
        "finding separately in the body.",
        "",
        "### 3. Request Optional Exception Approval",
        "",
        "This workflow is optional; use it only when the finding should be excepted",
        "instead of remediated in code.",
        "",
        "```text",
        "@agent-ai-sast-triage request an AppSec exception review for finding <finding_uuid> on PR/MR <pr_or_mr_url>. Request type: accept risk until YYYY-MM-DD. Reason: <owner, mitigation, and why code will not change now>. Allowed AppSec approvers: @alice, @bob. Do not create an Endor policy yet. Post or update a PR/MR comment with the exact approval phrase the approver can use.",
        "```",
        "",
        "### 4. AppSec Approval Comment",
        "",
        "An allowed AppSec approver can use one of these comments or review bodies:",
        "",
        "```text",
        "APPSEC APPROVED: false positive for finding <finding_uuid> - <why this is not exploitable>",
        "APPSEC APPROVED: accept risk for finding <finding_uuid> until YYYY-MM-DD - <owner, mitigation, and why code will not change now>",
        "```",
        "",
        "The requester, PR author, and agent account must not approve their own",
        "exception request.",
        "",
        "### 5. Optional Scoped Endor Exception Policy",
        "",
        "```text",
        "@agent-ai-sast-triage verify AppSec approval on PR/MR <pr_or_mr_url> for finding <finding_uuid>. Allowed AppSec approvers: @alice, @bob. If approval is valid and not self-approval, check for an existing active Endor exception policy for this finding/project/reason, then render the Endor exception policy spec for my confirmation. After I confirm, create or reuse the scoped policy and comment on the PR/MR with the policy name, policy UUID, Endor project, approver, expiration, and evidence URL.",
        "```",
        "",
        "For render-only exception checks, the agent should emit validator-ready",
        "JSON with `approvals[].approved: true`, `approvals[].expiration_time`,",
        "`exception_policies[].policy_name`, `exception_policies[].idempotency_check`,",
        "and `exception_policies[].policy_spec`. A pending policy should fail only",
        "the explicit-confirmation gate until the user approves the Endor write.",
        "",
        "Do not combine remediation and exception approval in normal production use.",
        "If you test both paths for QA, label the exception as temporary validation.",
        "Redact concrete exploit payloads from PR/MR prose and comments.",
        "",
    ]


def claude_code_smoke_test_section(recipe: EndorAgentRecipe) -> list[str]:
    """Return Claude Code smoke test README content."""

    if recipe.id == "sca-remediation":
        return [
            "## QA Smoke Test",
            "",
            "When validating this agent, isolate the run from user-level Claude skills so",
            "the result proves the Agent Kit artifact itself is doing the work.",
            "",
            "```bash",
            "export CLAUDE_CONFIG_DIR=\"$(mktemp -d)\"",
            "claude -p --agent sca-remediation --permission-mode bypassPermissions \\",
            "  \"Check this repository for P0 SCA findings I can start remediating. Do not edit files or open a PR until I approve.\"",
            "```",
            "",
            "The run log should not reference user-level skills or Endor MCP tooling.",
            "If it does, the test is contaminated and should be rerun in a clean",
            "Claude configuration.",
            "",
        ]
    if recipe.id != "ai-sast-triage":
        return []
    return [
        "## QA Smoke Test",
        "",
        "When validating this agent, isolate the run from user-level Claude skills so",
        "the result proves the Agent Kit artifact itself is doing the work.",
        "",
        "```bash",
        "export CLAUDE_CONFIG_DIR=\"$(mktemp -d)\"",
        "claude -p --agent ai-sast-triage --permission-mode bypassPermissions \\",
        "  \"Triage AI SAST findings for this repository. Do not open a PR until I approve the patch.\"",
        "```",
        "",
        "The run log should not reference user-level skills such as",
        "`~/.claude/skills/endor-ai-sast`. If it does, the test is contaminated",
        "and should be rerun in a clean Claude configuration.",
        "",
    ]


def edition_name(edition: str) -> str:
    """Return a human-readable Claude Code edition name."""

    if edition == "developer-edition":
        return "Developer Edition"
    if edition == "enterprise-edition":
        return "Enterprise Edition"
    raise ValueError(f"Unknown edition {edition!r}")


def example_prompt(recipe: EndorAgentRecipe, edition: str = "enterprise-edition") -> str:
    """Return the Claude Code example prompt for one recipe."""

    input_names = {field.name for field in recipe.inputs}
    if recipe.id == "ai-sast-triage":
        return f"@agent-{recipe.id} triage AI SAST findings for this repository. Do not open a PR until I approve the patch."
    if recipe.id == "sca-remediation":
        return f"@agent-{recipe.id} check this repository for P0 SCA findings I can start remediating. Do not edit files or open a PR until I approve."
    if recipe.id == "remediation-planner":
        return f"@agent-{recipe.id} preview remediation options for this repository"
    if recipe.id == "probe-droid":
        return f"@agent-{recipe.id} probe GitHub org <org> for Endor monitored-branch onboarding gaps and setup prescriptions"
    if "vulnerability_id" in input_names:
        return f"@agent-{recipe.id} explain CVE-2021-44228"
    if recipe.id == "upgrade-impact-analysis":
        if edition == "developer-edition":
            return f"@agent-{recipe.id} assess npm lodash from 4.17.20 to 4.17.21"
        return f"@agent-{recipe.id} show the safest upgrade path for repository <owner>/<repo> package lodash, including CIA and manifest files"
    if recipe.id == "package-risk-summary":
        return f"@agent-{recipe.id} summarize npm lodash version 4.17.20"
    if {"ecosystem", "package_name", "version"}.issubset(input_names):
        return f"@agent-{recipe.id} assess npm lodash version 4.17.20"
    return f"@agent-{recipe.id} help"


def _published_edition_dir(agent_root: Path, editions: tuple[str, ...], edition: str) -> Path:
    if len(editions) == 1:
        return agent_root
    return agent_root / edition
