from __future__ import annotations

import shutil
from pathlib import Path

from endor_agent_kit.publisher import publish_recipe

from conftest import repo_root
from host_artifact_bundle_contract import (
    assert_codex_skill_bundle,
    assert_host_bundle_files,
    assert_mcp_free_generated_artifact,
    assert_no_nested_edition_dirs,
)


def _copy_agent(tmp_path: Path) -> Path:
    src = repo_root() / "source" / "agents" / "ai-sast-triage"
    dst = tmp_path / "ai-sast-triage"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("dist"))
    return dst / "recipe.yaml"


def test_ai_sast_triage_does_not_require_project_uuid_for_normal_use(tmp_path):
    recipe = _copy_agent(tmp_path)
    dest = tmp_path / "endor-labs-agent-kit"

    publish_recipe(recipe, dest)

    root_readme = (dest / "README.md").read_text()
    agent_dir = dest / "claude-code" / "ai-sast-triage"
    codex_dir = dest / "codex" / "ai-sast-triage"
    agent_readme = (agent_dir / "README.md").read_text()
    prompt = (agent_dir / "ai-sast-triage.md").read_text()
    architecture = (agent_dir / "architecture.svg").read_text()

    assert "@agent-ai-sast-triage triage AI SAST findings for this repository" in root_readme
    assert "Do not open a PR until I approve the patch" in agent_readme
    assert "<project_uuid>" not in agent_readme
    assert "<project_uuid>" not in prompt
    assert "Do not require the user to know an Endor project UUID" in prompt
    assert_mcp_free_generated_artifact(prompt)
    assert "ai-tools" not in prompt
    assert "Do not require or start an Endor MCP server" in prompt
    assert "read the current repository root and `origin` remote URL" in prompt
    assert "ask the user to choose one" in prompt
    assert "Project scoping is mandatory" in prompt
    assert "Default Endor Context Scope" in prompt
    assert "Default Endor Finding list queries to `context.type==CONTEXT_TYPE_MAIN`" in prompt
    assert 'context.type==CONTEXT_TYPE_MAIN and spec.project_uuid=="<PROJECT_UUID>" and spec.method=="AI_SAST"' in prompt
    assert "inspect and report the returned `context.type` and `spec.source_code_version.ref`" in prompt
    assert "do not merge a CI/PR-run finding into main-context counts" in prompt
    assert "Namespace Provenance" in prompt
    assert "If the user supplied a namespace in the current request" in prompt
    assert "Never print or dump an entire Endor config file" in prompt
    assert "Do not run `cat ~/.config/endorctl/config.yaml`" in prompt
    assert "Never echo credential keys, secrets, tokens, or full config contents" in prompt
    assert "namespace_provenance" in prompt
    assert "project_resolution.repo_full_name" in prompt
    assert "Exploit Reproduction" in prompt
    assert "Remediation Guidance" in prompt
    assert "Use Exploit Reproduction for prioritization and validation planning" in prompt
    assert "Redact concrete exploit strings from PR/MR bodies" in prompt
    assert "Treat Remediation Guidance as advisory evidence, not an authority" in prompt
    assert "remediation_guidance_used" in prompt
    assert "exploit_reproduction_used" in prompt
    assert "safe local validation" in prompt
    assert "Derive validation commands from the actual target repo files" in prompt
    assert "do not guess Maven, npm, Docker, image names, ports, or service names" in prompt
    assert "validate that image/config" in prompt
    assert "<!-- auri:ai-sast-context " in prompt
    assert "<!-- endor-agent-kit:ai-sast-triage -->" in prompt
    assert "Endor Labs AURI Security Fix" in prompt
    assert "### 🔧 What changed" in prompt
    assert "### 🔎 Evidence provided by AURI" in prompt
    assert "Critical `🔴`, High `🟠`, Medium `🟡`, Low `🟢`" in prompt
    assert "Default to one remediation PR/MR per AI SAST finding" in prompt
    assert "Do not group unrelated CWE classes" in prompt
    assert "🟠 High: Fix 3 AI SAST findings" in prompt
    assert "give standalone Agent Kit copy/paste prompts, not AURI bot commands" in prompt
    assert "This section is optional guidance" in prompt
    assert "normal remediation PR/MR use does not require configuring exception approvals" in prompt
    assert "@agent-ai-sast-triage request an AppSec exception review for finding" in prompt
    assert "Do not create an Endor policy yet" in prompt
    assert "Do not embed any literal `APPSEC APPROVED:` approval phrase" in prompt
    assert "do not present `@auri`, `AURI:`, AURI Command Center" in prompt
    assert "Do not invent `file_path`, `source_location`, component names, or source files" in prompt
    assert "remediation/ai-sast/<finding-slug>" in prompt
    assert "endor/fix" in prompt
    assert "existing_change_request_check" in prompt
    assert "gh pr list --head <branch> --state all" in prompt
    assert "git ls-remote --heads origin <branch>" in prompt
    assert 'status: "none_found"' in prompt
    assert '`"lookup_unavailable"` plus a matching `data_gaps` entry' in prompt
    assert 'Do not write "No existing PR/branch discovered"' in prompt
    assert "endor-agent-kit validate-ai-sast-output" in prompt
    assert "endor-agent-kit lint-ai-sast-pr-body" in prompt
    assert "Every `patches[]` object for a generated remediation patch must include" in prompt
    assert "Every `change_requests[]` object for a generated remediation patch must include" in prompt
    assert "source_sha" in prompt
    assert "Use a host-allowed scratch path" in prompt
    assert "run `git apply --check`" in prompt
    assert "leave `change_requests[].body` unset or mark it as renderer-required" in prompt
    assert "inject the lint-clean rendered body into `change_requests[].body`" in prompt
    assert "Do not run a known-incomplete remediation payload through the validator" in prompt
    assert "Do not hand-render these review-facing artifacts" in prompt
    assert "Do not delegate this workflow to another subagent" in prompt
    assert "Never use bracket-only titles" in prompt
    header = prompt.split("---", 2)[1]
    assert "Task" in header
    assert "Agent" in header
    assert "Do not claim that an Endor exception policy was created" in prompt
    assert "## Action Contracts" in prompt
    assert "open-change-request" in prompt
    assert "using finding UUID, source location, context type, source ref" in prompt
    assert "Treat main-context findings as the default and label PR/CI-run context explicitly" in prompt
    assert "write-exception-policy" in prompt
    assert "availability: `available`" in prompt
    assert "checking existing Endor policies by generated policy name and finding UUID" in prompt
    assert "If an active matching policy already exists" in prompt
    assert "policy_name" in prompt
    assert "idempotency_check" in prompt
    assert "Endor project label" in prompt
    assert "do not show `Scope: $uuid=...`" in prompt
    assert "not a webhook listener" in prompt
    assert "`rule` containing the full Rego source" in prompt
    assert "Never use a `rego` field" in prompt
    assert "Do not use `meta.parent_uuid` for project scoping" in prompt
    assert "Exception-gate JSON must still include a minimal `verdicts[]` entry" in prompt
    assert "approvals[].approved: true" in prompt
    assert "Do not use `expiration` as a substitute for `expiration_time`" in prompt
    assert "exception_policies[].policy_spec" in prompt
    assert "render-ai-sast-exception-policy-comment" in prompt
    assert "lint-ai-sast-exception-policy-comment" in prompt
    assert "Do not use `rendered_policy`, `policy`, `policy_json`" in prompt
    assert "local structural validation copy with `user_confirmation` set to `approved`" in prompt
    assert "friendly aliases such as `expiration`, `rendered_policy`, or `finding_title`" in prompt
    assert '`"$uuid=PROJECT_UUID"`' in prompt
    assert "do not guess alternate live write shapes" in prompt
    assert_host_bundle_files(
        agent_dir,
        {"ai-sast-triage.md", "README.md", "actions.yaml", "architecture.svg", "endorctl-setup.md"},
    )
    assert_codex_skill_bundle(
        codex_dir,
        expected_files={"SKILL.md", "README.md", "actions.yaml", "architecture.svg", "endorctl-setup.md"},
        skill_markers=(
            "Treat file edits, branch pushes, PR/MR creation",
            "Never create or update an Endor policy",
            "auri:ai-sast-context",
        ),
    )
    assert_no_nested_edition_dirs(agent_dir)
    assert "![AI SAST Triage architecture](architecture.svg)" in agent_readme
    assert "PR/MR creation is host-mediated" in agent_readme
    assert "Setup Checklist" in agent_readme
    assert "gh auth status" in agent_readme
    assert "does not need an Endor MCP server" in agent_readme
    assert "AppSec approvers: @alice, @bob, @endor-labs/appsec" in agent_readme
    assert "Configure Optional AppSec Approvers" in agent_readme
    assert "The exception workflow is optional" in agent_readme
    assert "without configuring AppSec approvers or Endor policy-write" in agent_readme
    assert "Understand Finding Evidence" in agent_readme
    assert "Match The AURI PR/MR Body" in agent_readme
    assert "standalone Agent Kit request prompts" in agent_readme
    assert "Severity must be visually indicated" in agent_readme
    assert "Default to one remediation PR/MR per AI SAST finding" in agent_readme
    assert "visual indicator and highest severity" in agent_readme
    assert "🟠 High: Fix 3 AI SAST findings" in agent_readme
    assert "🟡 Medium: Fix ..." in agent_readme
    assert "[Medium] Fix ..." in agent_readme
    assert "uses it as" in agent_readme
    assert "APPSEC APPROVED: accept risk" in agent_readme
    assert "Example Workflow" in agent_readme
    assert "Triage Without Mutating" in agent_readme
    assert "Open One Remediation PR" in agent_readme
    assert "Request Optional Exception Approval" in agent_readme
    assert "This workflow is optional" in agent_readme
    assert "Request type: accept risk until YYYY-MM-DD" in agent_readme
    assert "Do not create an Endor policy yet" in agent_readme
    assert "Optional Scoped Endor Exception Policy" in agent_readme
    assert "render the Endor exception policy spec for my confirmation" in agent_readme
    assert "check for an existing active Endor exception policy" in agent_readme
    assert "policy name, policy UUID, Endor project" in agent_readme
    assert "PR/MR comments are approval evidence" in agent_readme
    assert "raw `$uuid=...` selector syntax" in agent_readme
    assert "approvals[].approved: true" in agent_readme
    assert "approvals[].expiration_time" in agent_readme
    assert "exception_policies[].policy_name" in agent_readme
    assert "exception_policies[].idempotency_check" in agent_readme
    assert "exception_policies[].policy_spec" in agent_readme
    assert "fail only" in agent_readme
    assert "The requester, PR author, and agent account must not approve their own" in agent_readme
    assert "exception request" in agent_readme
    assert "Redact concrete exploit payloads" in agent_readme
    assert "QA Smoke Test" in agent_readme
    assert "CLAUDE_CONFIG_DIR" in agent_readme
    assert "AppSec approver list" in agent_readme
    assert "approval.verify" in prompt
    assert "standalone PR/MR approval workflow" in prompt
    assert "Never let the developer requesting an exception self-approve it" in prompt
    assert "GitHub App/GitLab webhook" not in agent_readme
    assert "Optional exception lane" in architecture
    assert "PR/MR comment is evidence, not trigger" in architecture
    assert "Remediation works without the optional exception lane" in architecture
