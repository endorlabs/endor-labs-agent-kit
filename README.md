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

| Agent | Use it when you want to... | Claude Code | Claude Managed Agents |
| --- | --- | --- | --- |
| AI SAST Triage | Triage Endor AI SAST findings, generate grounded patches, and open requested change requests | `claude-code/ai-sast-triage/` | - |
| Dependency Decision Helper | Decide whether to add, upgrade to, or keep a specific package version | `claude-code/dependency-decision-helper/` | `claude-managed-agents/dependency-decision-helper/` |
| Endor Labs Package Risk Summary | Summarize the risk profile of a specific package version | `claude-code/package-risk-summary/` | `claude-managed-agents/package-risk-summary/` |
| Endor Labs Repository Dependency Reviewer | Review local dependency manifests with read-only file inspection and Endor evidence | `claude-code/repository-dependency-reviewer/` | - |
| Endor Labs Upgrade Impact Analysis | Analyze AURI-style upgrade impact with VersionUpgrade, CIA, findings, and manifest context | `claude-code/upgrade-impact-analysis/` | `claude-managed-agents/upgrade-impact-analysis/` |
| Endor Labs Vulnerability Explainer | Understand a specific CVE, GHSA, or Endor vulnerability and what to do next | `claude-code/vulnerability-explainer/` | `claude-managed-agents/vulnerability-explainer/` |
| Remediation Planner | Preview safe dependency remediation options without opening PRs | `claude-code/remediation-planner/` | - |

## Which Directory Do I Use?

| Goal | Start Here | You Do Not Need |
| --- | --- | --- |
| Install a Claude Code agent | `claude-code/<agent>/<edition>/README.md` | `source/`, `src/`, `tests/` |
| Install a Claude Managed Agent | `claude-managed-agents/<agent>/<edition>/README.md` | `source/`, `src/`, `tests/` |
| Modify or contribute an agent | `source/agents/<agent>/recipe.yaml` and `instructions.md` | Generated catalog files as the first edit |
| Work on the kit builder itself | `src/endor_agent_kit/` and `tests/` | Host install directories unless compiler output changes |

The `source/agents/` tree is for maintainers and contributors. It is not
copied into Claude Code or Managed Agents. Installable artifacts
are the generated host directories listed in the catalog.

## Supported Hosts

| Host | Generated path | Typical install target |
| --- | --- | --- |
| Claude Code | `claude-code/<agent>/<edition>/` | `.claude/agents/` in the target repository |
| Claude Managed Agents | `claude-managed-agents/<agent>/<edition>/` | Anthropic Console or `ant` CLI agent and environment creation |

## Editions

Each agent is published in one or more editions. If an edition does not apply
to a host, the catalog omits that host/edition directory.

| Edition | Best for | Signals | Shell access |
| --- | --- | --- | --- |
| Developer Edition | Fast, low-friction checks | Endor Model Context Protocol (MCP) tools | Not allowed |
| Enterprise Edition | Richer Endor context when the agent supports it | Endor MCP tools, documented Endor API lookups, and declared host capabilities | Agent-specific; see the recipe safety class |

Use **Developer Edition** when you want the safest default with no Bash
access.

Use **Enterprise Edition** when you have authenticated Endor setup and want
the highest-fidelity signals available for that agent. Some Enterprise
Edition agents are still MCP-only; their generated host configuration leaves
Bash access disabled when no read-only `endorctl api` lookups
or mutating workflow capabilities are required.

## Install An Agent

Pick an agent from the catalog, then choose the host and edition directory
that matches your environment.

### Ask An LLM To Install It

If you are using an assistant that can edit files or run commands in your
target repository, copy and paste this prompt:

```text
Install this Endor Labs Agent Kit agent in the current repository.

Agent Kit root: /path/to/endor-labs-agent-kit
Host: claude-code
Agent id: dependency-decision-helper
Edition: developer-edition

Please:
1. Read the install README at <Agent Kit root>/<Host>/<Agent id>/<Edition>/README.md.
2. Install the generated agent artifact from that directory into this repository.
3. Preserve the generated agent prompt exactly; do not rewrite or summarize it.
4. Tell me any Endor MCP, endorctl, repository, or credential setup still required.
5. Show me the command or prompt I should use to invoke the agent.
```

Replace the host, agent id, and edition with the directory you selected from
the catalog.

### Claude Code

Copy the generated subagent into your target repository and restart Claude
Code if needed.

```bash
mkdir -p .claude/agents
cp /path/to/endor-labs-agent-kit/claude-code/dependency-decision-helper/developer-edition/dependency-decision-helper.md \
  .claude/agents/dependency-decision-helper.md
```

Then invoke it from Claude Code:

```text
@agent-dependency-decision-helper assess npm lodash version 4.17.20
```

### Claude Managed Agents

Update the MCP server URL and vault references in the generated YAML
templates, then create the agent and environment with the Anthropic CLI or
Console.

```bash
cd /path/to/endor-labs-agent-kit/claude-managed-agents/dependency-decision-helper/developer-edition
ant beta:agents create < agent.yaml
ant beta:environments create < environment.yaml
```

Use `session-template.yaml` as the starting point when creating sessions.

## Configure Endor Access

| Access path | Used by | Notes |
| --- | --- | --- |
| Endor MCP | Developer Edition and Enterprise Edition agents | Required for every published agent. Configure it through the target host's MCP mechanism. |
| Read-only `endorctl api` | Enterprise Edition agents that need tenant or project data beyond public MCP tools | The generated prompts constrain commands to documented read-only lookups. Per-edition README files link to `endorctl-setup.md` when needed. |
| Git and source-provider credentials | Mutating Claude Code agents such as AI SAST Triage | Required only when the agent is expected to apply patches and open change requests. |

## Example Prompts

AI SAST Triage:

```text
@agent-ai-sast-triage triage AI SAST findings for project <project_uuid>
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
@agent-upgrade-impact-analysis show the safest upgrade path for project <project_uuid> package lodash
```

Endor Labs Vulnerability Explainer:

```text
@agent-vulnerability-explainer explain CVE-2021-44228
```

Remediation Planner:

```text
@agent-remediation-planner preview remediation options for project <project_uuid>
```

## Output Contract

Agents return concise prose plus a JSON block. The exact schema depends on the
agent. If a signal is unavailable because of setup, authentication, account
tier, or tooling, agents record that in `data_gaps` instead of inventing
evidence.

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
host capabilities. AI SAST Triage is the current mutating agent: it may
fetch source context, write patch files, run git/source-provider commands,
and open a change request when the user asks for that workflow and the target
repository credentials are available.

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
tests, catalog regeneration, and validation.

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
4. Add or update tests under `tests/`.
5. Validate and regenerate the catalog.

```bash
endor-agent-kit validate source/agents/<agent>/recipe.yaml
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
| `endor-agent-kit compile source/agents/<agent>/recipe.yaml --target <host>` | Compile one recipe into its local `dist/` directory. |
| `endor-agent-kit compile source/agents/<agent>/recipe.yaml --target <host> --edition <edition>` | Compile one edition for one host. |
| `endor-agent-kit publish source/agents/*/recipe.yaml --dest . --prune` | Regenerate the checked-in catalog and remove stale generated agents. |

Supported compile targets are `claude-code`, `claude-managed-agents`,
and `raw`.

## Recipe Reference

Recipes are YAML files with schema version `1`. They describe the agent's
prompt, Endor access paths, host capabilities, inputs, outputs, evals, and
published host editions.

| Field | Purpose |
| --- | --- |
| `id`, `name`, `version`, `description` | Public catalog identity and copy. |
| `safety_class`, `mutations` | Safety contract. Recipes may be `read_only`, `dry_run`, or explicitly `mutating` with matching host capabilities. |
| `supported_transports` | Endor access paths such as `mcp` and `endorctl_api`. |
| `host_capabilities_required` | Abstract host capabilities that compilers map to host-specific tools. |
| `inputs`, `outputs` | User-facing IO contract and expected JSON output shape. |
| `compatible_hosts` | Hosts that should receive generated artifacts. |
| `host_editions` | Optional host-specific edition selection. Omit to publish all default editions for that host. |
| `required_endor_mcp_tools`, `endorctl_api_invocations` | Endor tools and API lookup groups the prompt may use. |
| `instructions_path`, `evals` | Source prompt and eval case files relative to the recipe. |

Generated artifacts must not be edited as the first step. Change the recipe
or instructions source, publish the catalog, then review the generated diff.

## Repository Reference

### Layout

```text
source/
  agents/
    <agent>/
      recipe.yaml
      instructions.md
      evals/cases.yaml
skills/
  create-endor-labs-agent/
    SKILL.md
src/endor_agent_kit/
tests/
claude-code/
  ai-sast-triage/
    enterprise-edition/
      README.md
      ai-sast-triage.md
      endorctl-setup.md
  dependency-decision-helper/
    developer-edition/
      README.md
      dependency-decision-helper.md
    enterprise-edition/
      README.md
      dependency-decision-helper.md
      endorctl-setup.md
  package-risk-summary/
    developer-edition/
      README.md
      package-risk-summary.md
    enterprise-edition/
      README.md
      endorctl-setup.md
      package-risk-summary.md
  remediation-planner/
    enterprise-edition/
      README.md
      remediation-planner.md
  repository-dependency-reviewer/
    developer-edition/
      README.md
      repository-dependency-reviewer.md
    enterprise-edition/
      README.md
      repository-dependency-reviewer.md
  upgrade-impact-analysis/
    developer-edition/
      README.md
      upgrade-impact-analysis.md
    enterprise-edition/
      README.md
      endorctl-setup.md
      upgrade-impact-analysis.md
  vulnerability-explainer/
    developer-edition/
      README.md
      vulnerability-explainer.md
    enterprise-edition/
      README.md
      vulnerability-explainer.md
claude-managed-agents/
  dependency-decision-helper/
    developer-edition/
      README.md
      agent.yaml
      environment.yaml
      session-template.yaml
    enterprise-edition/
      README.md
      agent.yaml
      endorctl-setup.md
      environment.yaml
      session-template.yaml
  package-risk-summary/
    developer-edition/
      README.md
      agent.yaml
      environment.yaml
      session-template.yaml
    enterprise-edition/
      README.md
      agent.yaml
      endorctl-setup.md
      environment.yaml
      session-template.yaml
  upgrade-impact-analysis/
    developer-edition/
      README.md
      agent.yaml
      environment.yaml
      session-template.yaml
    enterprise-edition/
      README.md
      agent.yaml
      endorctl-setup.md
      environment.yaml
      session-template.yaml
  vulnerability-explainer/
    developer-edition/
      README.md
      agent.yaml
      environment.yaml
      session-template.yaml
    enterprise-edition/
      README.md
      agent.yaml
      environment.yaml
      session-template.yaml
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
- `manifest.json`

These paths are customer-facing and should stay stable.

## Release And License

Before publishing a public release, verify that generated artifacts are fresh
and that Endor Labs has selected and added the final open-source license.

License information will be added before public release.
