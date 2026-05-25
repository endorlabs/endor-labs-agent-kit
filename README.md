# Endor Labs Agent Kit

Ready-to-use Endor Labs agents for AI coding assistants, plus the
recipe-first builder used to maintain and publish them.

Use this repository in two ways:

- **Install agents** from the generated catalog directories.
- **Contribute agents** by editing source recipes and regenerating the catalog.

## Table Of Contents

- [Agent Catalog](#agent-catalog)
- [Which Directory Do I Use?](#which-directory-do-i-use)
- [Supported Hosts](#supported-hosts)
- [MCP Usage](#mcp-usage)
- [Plugin Packaging Route](#plugin-packaging-route)
- [Editions](#editions)
- [Install An Agent](#install-an-agent)
- [Configure Endor Access](#configure-endor-access)
- [Example Prompts](#example-prompts)
- [Output Contract](#output-contract)
- [Safety Model](#safety-model)
- [Contribute An Agent](#contribute-an-agent)
- [Create Agents With The Skill](#create-agents-with-the-skill)
- [Recipe Reference](#recipe-reference)
- [Repository Reference](#repository-reference)
- [Release And License](#release-and-license)

## Agent Catalog

Generated artifacts are checked in so users can copy or install agents without
running the builder. Maintainer source recipes live under `source/agents/` and are the
maintainer-facing source of truth.

If you are installing an agent, start with the generated host directories below.
You only need `source/agents/` when you are changing or contributing an agent.

| Agent | Use it when you want to... | Claude Code | Claude Managed Agents | Codex |
| --- | --- | --- | --- | --- |
| AI SAST Triage | Triage Endor AI SAST findings, use exploit and remediation context, and open requested change requests | `claude-code/ai-sast-triage/` | - | `codex/ai-sast-triage/` |
| Dependency Decision Helper | Decide whether to add, upgrade to, or keep a specific package version | `claude-code/dependency-decision-helper/` | `claude-managed-agents/dependency-decision-helper/` | - |
| Endor Labs Package Risk Summary | Summarize the risk profile of a specific package version | `claude-code/package-risk-summary/` | `claude-managed-agents/package-risk-summary/` | - |
| Endor Labs Repository Dependency Reviewer | Review local dependency manifests with read-only file inspection and Endor evidence | `claude-code/repository-dependency-reviewer/` | - | - |
| Endor Labs Upgrade Impact Analysis | Analyze Endor platform upgrade impact with VersionUpgrade, CIA, findings, and manifest context | `claude-code/upgrade-impact-analysis/` | `claude-managed-agents/upgrade-impact-analysis/` | - |
| Endor Labs Vulnerability Explainer | Understand a specific CVE, GHSA, or Endor vulnerability and what to do next | `claude-code/vulnerability-explainer/` | `claude-managed-agents/vulnerability-explainer/` | - |
| Probe Droid | Probe GitHub.com onboarding gaps and prescribe Endor scan profiles, toolchains, package integrations, and reachability setup | `claude-code/probe-droid/` | - | `codex/probe-droid/` |
| Remediation Planner | Preview safe dependency remediation options without opening PRs | `claude-code/remediation-planner/` | - | - |
| SCA Remediation | Remediate dependency vulnerabilities with Endor SCA findings, UIA evidence, low-risk PR lanes, deterministic risk decisions, validation, and approved PR/MR creation | `claude-code/sca-remediation/` | - | `codex/sca-remediation/` |

## Which Directory Do I Use?

| Goal | Start Here | You Do Not Need |
| --- | --- | --- |
| Install a Claude Code agent | `claude-code/<agent>/README.md` | `source/`, `src/`, `tests/` |
| Install a Claude Managed Agent | `claude-managed-agents/<agent>/README.md` | `source/`, `src/`, `tests/` |
| Install a Codex skill | `codex/<agent>/README.md` | `source/`, `src/`, `tests/` |
| Modify or contribute an agent | `source/agents/<agent>/recipe.yaml` and `instructions.md` | Generated catalog files as the first edit |
| Work on the kit builder itself | `src/endor_agent_kit/` and `tests/` | Host install directories unless compiler output changes |

The `source/agents/` tree is for maintainers and contributors. It is not
copied into Claude Code or Managed Agents. Installable artifacts
are the generated host directories listed in the catalog.

## Supported Hosts

| Host | Generated path | Typical install target |
| --- | --- | --- |
| Claude Code | `claude-code/<agent>/` | `.claude/agents/` in the target repository |
| Claude Managed Agents | `claude-managed-agents/<agent>/` | Anthropic Console or `ant` CLI agent and environment creation |
| Codex | `codex/<agent>/` | `$CODEX_HOME/skills/<agent>/` or `~/.codex/skills/<agent>/` |

## MCP Usage

MCP is not used by the mutating remediation workflows. AI SAST Triage, SCA
Remediation, Remediation Planner, Upgrade Impact Analysis, Probe Droid,
and the Codex skills use documented Endor API or `endorctl api` paths
instead.

MCP remains in the catalog only where the current public recipe still depends
on Endor package/vulnerability lookup tools that do not yet have an
`endorctl api` contract in this kit:

| Agent | MCP use | Non-MCP path in same artifact |
| --- | --- | --- |
| Dependency Decision Helper | Package risk, vulnerability list, and vulnerability enrichment. | `endorctl api` for package scores, license, and similar-package signals. |
| Endor Labs Package Risk Summary | Package risk, vulnerability list, and vulnerability enrichment. | `endorctl api` for package scores, license, and similar-package signals. |
| Endor Labs Repository Dependency Reviewer | Per-dependency risk and vulnerability checks after local read-only manifest inspection. | None in v0. |
| Endor Labs Vulnerability Explainer | Vulnerability detail lookup. | None in v0. |

If MCP is unavailable, those agents must record the missing signal in
`data_gaps` rather than blocking install or fabricating evidence.

## Plugin Packaging Route

Codex support currently publishes generated skills under `codex/<agent>/`.
A future plugin package can wrap those skills for easier installation, but
the plugin route should preserve the same recipe source, generated skill
text, action metadata, and approval gates. See
`docs/plugin-packaging-design.md` for the current blast-radius notes before
adding plugin publishing.

## Editions

Most users should not need to think about editions. The current catalog
publishes one customer-facing artifact per agent and host, directly under
`claude-code/<agent>/`, `claude-managed-agents/<agent>/`, or
`codex/<agent>/`.

The builder still understands internal `developer-edition` and
`enterprise-edition` recipe sections for compatibility and for future
agents that genuinely need multiple artifacts. When a recipe selects one
artifact, the published directory is flat and the generated README omits the
edition label.

Shell access is still controlled by each recipe's host capability contract.
Read-only agents that do not need `endorctl api` deny Bash. Read-only agents
that need `endorctl api` allow Bash only for documented read-only Endor
lookup commands. Mutating agents keep file edits, branch pushes, PR/MR
creation, comments, approval verification, and Endor policy writes behind
separate approval gates.

## Install An Agent

Pick an agent from the catalog, then open that host directory's README. If
the agent has edition subdirectories, choose the one that matches your
environment; otherwise use the agent directory directly.

### Ask An LLM To Install It

If you are using an assistant that can edit files or run commands in your
target repository, copy and paste this prompt:

```text
Install this Endor Labs Agent Kit agent in the current repository.

Agent Kit root: /path/to/endor-labs-agent-kit
Host: claude-code
Agent directory: claude-code/ai-sast-triage

Please:
1. Read the install README at <Agent Kit root>/<Agent directory>/README.md.
2. Install the generated agent artifact from that directory into this repository.
3. Preserve the generated agent prompt exactly; do not rewrite or summarize it.
4. Tell me any Endor MCP if declared, endorctl, repository, or credential setup still required.
5. Show me the command or prompt I should use to invoke the agent.
```

Replace `Agent directory` with the directory you selected from the catalog.

### Claude Code

Copy the generated subagent into your target repository and restart Claude
Code if needed.

```bash
mkdir -p .claude/agents
cp /path/to/endor-labs-agent-kit/claude-code/ai-sast-triage/ai-sast-triage.md \
  .claude/agents/ai-sast-triage.md
```

Then invoke it from Claude Code:

```text
@agent-ai-sast-triage triage AI SAST findings for this repository
```

### Claude Managed Agents

Create the agent and environment with the Anthropic CLI or Console. If the
selected agent declares MCP in its generated `README.md`, update the MCP
server URL and vault references in the generated YAML first.

```bash
cd /path/to/endor-labs-agent-kit/claude-managed-agents/dependency-decision-helper
ant beta:agents create < agent.yaml
ant beta:environments create < environment.yaml
```

Use `session-template.yaml` as the starting point when creating sessions.

### Codex

Copy the generated skill directory into your Codex skills directory, then
start a new Codex session so the skill loader can see it.

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R /path/to/endor-labs-agent-kit/codex/ai-sast-triage \
  "${CODEX_HOME:-$HOME/.codex}/skills/ai-sast-triage"
cp -R /path/to/endor-labs-agent-kit/codex/probe-droid \
  "${CODEX_HOME:-$HOME/.codex}/skills/probe-droid"
cp -R /path/to/endor-labs-agent-kit/codex/sca-remediation \
  "${CODEX_HOME:-$HOME/.codex}/skills/sca-remediation"
```

Then invoke it from Codex:

```text
Use the ai-sast-triage skill to triage AI SAST findings for this repository.
Use the probe-droid skill to probe GitHub org <org> for Endor monitored-branch onboarding gaps and setup prescriptions.
Use the sca-remediation skill to check this repository for P0 SCA findings I can start remediating.
```

## Configure Endor Access

| Access path | Used by | Notes |
| --- | --- | --- |
| Endor MCP | Agents whose generated artifact declares an MCP server | Configure it through the target host's MCP mechanism only when the selected agent requires it. |
| `endorctl api` or direct Endor API | Agents that need tenant, project, finding, or policy data without MCP | The generated prompts constrain commands to documented lookups and writes. Agent or edition README files link to `endorctl-setup.md` when needed. |
| GitHub read-only inventory credentials | Probe Droid | Required when the agent compares GitHub.com repository inventory with Endor projects without cloning or mutating repositories. |
| Git and source-provider credentials | Mutating Claude Code agents such as AI SAST Triage and SCA Remediation | Required when the agent is expected to apply patches, open change requests, read PR/MR approval evidence, or post PR/MR comments. |
| Codex terminal and file-editing tools | Codex skills for mutating agents such as AI SAST Triage and SCA Remediation | The skill keeps file edits, branch pushes, PR/MR creation, PR/MR comments, and Endor policy writes behind separate approval gates. |
| Endor policy-write access | AI SAST Triage standalone exceptions | Required only when a verified AppSec PR/MR approval should create a scoped Endor exception policy. The agent must show the policy spec and ask for confirmation before writing. |

## Example Prompts

AI SAST Triage:

```text
@agent-ai-sast-triage triage AI SAST findings for this repository
```

Dependency Decision Helper:

```text
@agent-dependency-decision-helper assess npm lodash version 4.17.20
```

Endor Labs Package Risk Summary:

```text
@agent-package-risk-summary summarize npm lodash version 4.17.20
```

Endor Labs Repository Dependency Reviewer:

```text
@agent-repository-dependency-reviewer review this repository's dependency manifests
```

Endor Labs Upgrade Impact Analysis:

```text
@agent-upgrade-impact-analysis show the safest upgrade path for repository <owner>/<repo> package lodash
```

Endor Labs Vulnerability Explainer:

```text
@agent-vulnerability-explainer explain CVE-2021-44228
```

Probe Droid:

```text
@agent-probe-droid probe GitHub org <org> for Endor monitored-branch onboarding gaps and setup prescriptions
```

Remediation Planner:

```text
@agent-remediation-planner preview remediation options for this repository
```

SCA Remediation:

```text
@agent-sca-remediation check this repository for P0 SCA findings I can start remediating
```

Other non-breaking low-risk UIA-backed PRs:

```text
@agent-sca-remediation show me the other non-breaking low-risk UIA-backed PRs for this repository. Keep this separate from the P0/exploited queue and the risky solver. Do not edit files, create branches, push, or open a PR/MR.
```

SCA remediation PR plan:

```text
@agent-sca-remediation prepare the top UIA-backed dependency remediation for this repository. Show the selected package, affected manifests, VersionUpgrade/UIA UUID, risk, CIA status, risk_decision, findings fixed, folded advisory/finding list, validation command, branch name, PR/MR title, and body before changing files.
```

## Output Contract

Agents return concise prose plus a JSON block. The exact schema depends on the
agent. If a signal is unavailable because of setup, authentication, account
tier, or tooling, agents record that in `data_gaps` instead of inventing
evidence.

SCA remediation outputs can be checked mechanically before a workflow advances:

```bash
endor-agent-kit validate-sca-output sca-output.json --gate selection-plan
endor-agent-kit render-sca-pr-body sca-output.json > pr-body.md
endor-agent-kit lint-sca-pr-body pr-body.md
endor-agent-kit check-install --agent sca-remediation --repo /path/to/repo
endor-agent-kit check-install --host codex --agent sca-remediation --codex-home ~/.codex
endor-agent-kit validate-ai-sast-output ai-sast-output.json --gate remediation
endor-agent-kit render-ai-sast-pr-body ai-sast-output.json > pr-body.md
endor-agent-kit lint-ai-sast-pr-body pr-body.md
endor-agent-kit render-ai-sast-approval-comment ai-sast-output.json > approval-comment.md
endor-agent-kit lint-ai-sast-approval-comment approval-comment.md
endor-agent-kit render-ai-sast-exception-policy-comment ai-sast-output.json > policy-comment.md
endor-agent-kit lint-ai-sast-exception-policy-comment policy-comment.md
```

`validate-sca-output` rejects Selection / Plan responses that omit
`risk_decision.status`, use nonstandard branch names, or try to advance a
CIA-indeterminate upgrade without source-usage evidence and validation
requirements. `render-sca-pr-body` turns normalized advisory data into the
AURI-style PR/MR body, including the folded advisory list, CVE-visible links
to GHSA URLs, and severity emoji suffixes.
`check-install` catches copied Claude Code primary artifacts and installed
Codex skill bundles that are stale versus the checked-in Agent Kit catalog.

AI SAST triage outputs can be checked before remediation, PR/MR, or
exception-policy gates advance. `validate-ai-sast-output` requires
project and namespace provenance, finding/source-location provenance,
approval evidence before exception policies, and a rendered PR/MR body
when a remediation change request is part of the plan. For exception
policies it also checks accepted-risk expiration, approval reason
matching, approved finding scope, project selector scope, policy names,
idempotency checks, and human-readable decision comments. The AI SAST
PR/MR renderer follows the AURI AI SAST remediation structure with
`auri:ai-sast-context` metadata, severity indicator emojis, sanitized
AURI evidence, a standalone exception-request prompt block, folded finding details,
and standalone Agent Kit policy-write gates that still require independent
AppSec approval before any Endor policy write. Standalone Agent Kit is not
a webhook listener: PR/MR comments are approval evidence, and a user or
external automation must invoke the installed agent before any policy can
be created or reused.

For `sca-remediation`, keep the three remediation lanes distinct:

- P0/exploited remediation candidates: rank reachable or exploited critical/high findings and require UIA evidence before naming a best fix.
- Other non-breaking low-risk UIA-backed PRs: list only low-risk, CIA-clean recommendations with zero introduced findings and enough repo metadata to open a PR/MR.
- Risky or indeterminate upgrades: use `risk_decision` from Endor evidence plus local source usage before applying or opening a change request.

The low-risk lane reports `low_risk_recommendations`, `candidate_prs`,
`ready_to_open`, `most_findings_in_one_pr`, and `p0_duplicates_hidden`.
Validation commands must come from the repository's actual manifest and
package-manager layout; the agent must not assume Java, Maven, npm, Python,
Go, .NET, Ruby, Rust, or any other ecosystem from prior runs.

## Safety Model

Most agents in this kit are read-only. Recipes declare their safety class and
host capabilities explicitly.

Read-only agents do not:

- edit files
- create pull requests
- run scans
- dismiss findings
- create policies
- mutate Endor Labs state

Mutating agents are published only when their recipe declares the required
host capabilities. AI SAST Triage and SCA Remediation may fetch source
context, write patch files, run git/source-provider commands, and open a
change request when the user asks for that workflow and the target repository
credentials are available.

When a read-only agent permits Bash, its prompt limits Bash to documented
read-only Endor lookup commands. Claude Code artifacts deny Bash when it is
not needed.

When a recipe declares `host_capabilities_required.read_files: true`,
Claude Code artifacts allow only `Read`, `Glob`, `Grep`, and `LS` for
read-only workspace inspection; file mutation, notebook, web, and todo tools
remain denied.
Claude Managed Agents artifacts omit the pre-built agent toolset unless an
agent needs read-only Bash, and then enable only Bash with confirmation.

## Contribute An Agent

This repository is both the source of truth and the distribution catalog.
Contributor workflow is recipe-first: edit source files under `source/agents/`, then
regenerate customer-facing artifacts.

### Create Agents With The Skill

Use the Create Endor Labs Agent skill to make your own Endor Labs agent.
The skill lives at `skills/create-endor-labs-agent/SKILL.md` and guides an
assistant through agent design, recipe authoring, prompt sections, evals,
architecture diagrams, tests, catalog regeneration, and validation.

The skill supports two public input styles: a net-new agent brief or a
generic sanitized agent blueprint. Private tools may generate a blueprint,
but Agent Kit should only receive customer-safe recipe, action, instruction,
eval, and architecture source files.

For Claude Code, install it at either the repository or user level:

```bash
# Repository-level install
mkdir -p .claude/skills
cp -R skills/create-endor-labs-agent .claude/skills/

# User-level install
mkdir -p ~/.claude/skills
cp -R skills/create-endor-labs-agent ~/.claude/skills/
```

Then ask your assistant:

```text
Use the create Endor Labs agent skill to make an agent that <does the workflow you want>.
```

You can also point any agent directly at
`skills/create-endor-labs-agent/SKILL.md` if it does not support native
skills.

### Development Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### Authoring Workflow

1. Edit `source/agents/<agent>/recipe.yaml`.
2. Edit `source/agents/<agent>/instructions.md`.
3. Update `source/agents/<agent>/evals/cases.yaml`.
4. Add `source/agents/<agent>/architecture.svg` in the existing diagram format.
5. Add or update tests under `tests/`.
6. Validate and regenerate the catalog.

```bash
endor-agent-kit validate source/agents/<agent>/recipe.yaml
endor-agent-kit authoring-check source/agents/<agent>/recipe.yaml --new-agent
endor-agent-kit publish source/agents/*/recipe.yaml --dest . --prune
python -m pytest -q
git diff --exit-code -- README.md manifest.json claude-code claude-managed-agents
```

Pull requests should include both source changes and regenerated artifacts.
CI runs the same validation and generated-artifact drift check.

### CLI Reference

| Command | Purpose |
| --- | --- |
| `endor-agent-kit validate source/agents/<agent>/recipe.yaml` | Validate one recipe. |
| `endor-agent-kit authoring-check source/agents/<agent>/recipe.yaml --new-agent` | Check source-first authoring rules for a new public agent. |
| `endor-agent-kit compile source/agents/<agent>/recipe.yaml --target <host>` | Compile one recipe into its local `dist/` directory. |
| `endor-agent-kit compile source/agents/<agent>/recipe.yaml --target <host> --edition <edition>` | Compile one edition for one host. |
| `endor-agent-kit publish source/agents/*/recipe.yaml --dest . --prune` | Regenerate the checked-in catalog and remove stale generated agents. |
| `endor-agent-kit validate-sca-output sca-output.json --gate selection-plan` | Validate structured `sca-remediation` output before advancing a workflow gate. |
| `endor-agent-kit render-sca-pr-body sca-output.json > pr-body.md` | Render the AURI-style SCA remediation PR/MR body from normalized JSON. |
| `endor-agent-kit lint-sca-pr-body pr-body.md` | Lint a rendered SCA remediation PR/MR body for required sections, advisory formatting, and severity suffixes. |
| `endor-agent-kit validate-ai-sast-output ai-sast-output.json --gate remediation` | Validate structured `ai-sast-triage` output before remediation, PR/MR, or exception gates advance. |
| `endor-agent-kit render-ai-sast-pr-body ai-sast-output.json > pr-body.md` | Render an AURI-style AI SAST remediation PR/MR body from normalized JSON. |
| `endor-agent-kit lint-ai-sast-pr-body pr-body.md` | Lint an AURI-style AI SAST remediation PR/MR body for required sections, hidden context metadata, and severity indicators. |
| `endor-agent-kit render-ai-sast-approval-comment ai-sast-output.json > approval-comment.md` | Render a standalone AppSec approval request comment. |
| `endor-agent-kit lint-ai-sast-approval-comment approval-comment.md` | Lint the approval request comment and exact approval phrase. |
| `endor-agent-kit render-ai-sast-exception-policy-comment ai-sast-output.json > policy-comment.md` | Render a human-readable Endor exception policy decision comment. |
| `endor-agent-kit lint-ai-sast-exception-policy-comment policy-comment.md` | Lint the policy decision comment for policy name/UUID, project label, evidence, and raw selector leakage. |
| `endor-agent-kit check-install --agent sca-remediation --repo /path/to/repo` | Check whether a copied repo-level Claude Code agent matches the generated catalog artifact. |
| `endor-agent-kit check-install --host codex --agent sca-remediation --codex-home ~/.codex` | Check whether an installed Codex skill directory matches the generated catalog bundle. |

Supported compile targets are `claude-code`, `claude-managed-agents`,
`codex`, and `raw`.

## Recipe Reference

Recipes are YAML files with schema version `1` or `2`. They describe the agent's
prompt, Endor access paths, host capabilities, inputs, outputs, evals, and
published host editions. Schema v2 recipes may also point to `actions.yaml`
for semantic side-effect contracts such as opening change requests or
requesting exception-policy approval.

| Field | Purpose |
| --- | --- |
| `id`, `name`, `version`, `description` | Public catalog identity and copy. |
| `safety_class`, `mutations` | Safety contract. Recipes may be `read_only`, `dry_run`, or explicitly `mutating` with matching host capabilities. |
| `supported_transports` | Endor access paths such as `mcp` and `endorctl_api`. |
| `host_capabilities_required` | Abstract host capabilities that compilers map to host-specific tools. |
| `action_contracts_path` | Optional schema v2 path to `actions.yaml`, which declares semantic side effects and adapter requirements. |
| `inputs`, `outputs` | User-facing IO contract and expected JSON output shape. |
| `compatible_hosts` | Hosts that should receive generated artifacts. |
| `host_editions` | Optional host-specific edition selection. Omit to publish all default editions for that host. |
| `required_endor_mcp_tools`, `endorctl_api_invocations` | Endor tools and API lookup groups the prompt may use. |
| `instructions_path`, `evals` | Source prompt and eval case files relative to the recipe. |
| `architecture.svg` | Required source diagram copied into generated catalog artifacts when present. |

Generated artifacts must not be edited as the first step. Change the recipe
or instructions source, publish the catalog, then review the generated diff.

## Repository Reference

### Layout

```text
source/
  agents/
    <agent>/
      recipe.yaml
      actions.yaml
      instructions.md
      evals/cases.yaml
skills/
  create-endor-labs-agent/
    SKILL.md
docs/
  plugin-packaging-design.md
src/endor_agent_kit/
tests/
claude-code/
  ai-sast-triage/
    README.md
    actions.yaml
    ai-sast-triage.md
    architecture.svg
    endorctl-setup.md
  dependency-decision-helper/
    README.md
    dependency-decision-helper.md
    endorctl-setup.md
  package-risk-summary/
    README.md
    endorctl-setup.md
    package-risk-summary.md
  probe-droid/
    README.md
    architecture.svg
    endorctl-setup.md
    probe-droid.md
  remediation-planner/
    README.md
    architecture.svg
    endorctl-setup.md
    remediation-planner.md
  repository-dependency-reviewer/
    README.md
    repository-dependency-reviewer.md
  sca-remediation/
    README.md
    actions.yaml
    architecture.svg
    endorctl-setup.md
    sca-remediation.md
  upgrade-impact-analysis/
    README.md
    architecture.svg
    endorctl-setup.md
    upgrade-impact-analysis.md
  vulnerability-explainer/
    README.md
    vulnerability-explainer.md
claude-managed-agents/
  dependency-decision-helper/
    README.md
    agent.yaml
    endorctl-setup.md
    environment.yaml
    session-template.yaml
  package-risk-summary/
    README.md
    agent.yaml
    endorctl-setup.md
    environment.yaml
    session-template.yaml
  upgrade-impact-analysis/
    README.md
    agent.yaml
    architecture.svg
    endorctl-setup.md
    environment.yaml
    session-template.yaml
  vulnerability-explainer/
    README.md
    agent.yaml
    environment.yaml
    session-template.yaml
codex/
  ai-sast-triage/
    README.md
    SKILL.md
    actions.yaml
    architecture.svg
    endorctl-setup.md
  probe-droid/
    README.md
    SKILL.md
    architecture.svg
    endorctl-setup.md
  sca-remediation/
    README.md
    SKILL.md
    actions.yaml
    architecture.svg
    endorctl-setup.md
manifest.json
```

### Manifest

`manifest.json` lists published artifacts and their SHA-256 checksums. Each
manifest entry also records `source.builder_recipe`, which points back to the
recipe that generated the artifact set.

### Generated Catalog

The root catalog directories are intentionally checked in:

- `claude-code/`
- `claude-managed-agents/`
- `codex/`
- `manifest.json`

These paths are customer-facing and should stay stable.

## Release And License

Before publishing a public release, verify that generated artifacts are fresh
and that Endor Labs has selected and added the final open-source license.

License information will be added before public release.
