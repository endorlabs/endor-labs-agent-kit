# Endor Labs Agent Kit

Ready-to-use Endor Labs agents for AI coding assistants, plus the
recipe-first builder used to maintain and publish them.

Use this repository in two ways:

- **Install agents** from the generated catalog directories.
- **Contribute agents** by editing source recipes and regenerating the catalog.

## Table Of Contents

- [Agent Catalog](#agent-catalog)
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
running the builder. Source recipes live under `agents/` and are the
maintainer-facing source of truth.

| Agent | Use it when you want to... | Claude Code | Claude Managed Agents | GitHub Copilot / AgentHQ plugin |
| --- | --- | --- | --- | --- |
| Dependency Decision Helper | Decide whether to add, upgrade to, or keep a specific package version | `claude-code/dependency-decision-helper/` | `claude-managed-agents/dependency-decision-helper/` | `github-copilot-plugin/dependency-decision-helper/` |
| Endor Labs Package Risk Summary | Summarize the risk profile of a specific package version | `claude-code/package-risk-summary/` | `claude-managed-agents/package-risk-summary/` | `github-copilot-plugin/package-risk-summary/` |
| Endor Labs Repository Dependency Reviewer | Review local dependency manifests with read-only file inspection and Endor evidence | `claude-code/repository-dependency-reviewer/` | - | - |
| Endor Labs Tenant Findings | Summarize tenant findings for an imported project, including reachable findings | - | - | `github-copilot-plugin/tenant-findings/` |
| Endor Labs Upgrade Impact Analysis | Analyze AURI-style upgrade impact with VersionUpgrade, CIA, findings, and manifest context | `claude-code/upgrade-impact-analysis/` | `claude-managed-agents/upgrade-impact-analysis/` | `github-copilot-plugin/upgrade-impact-analysis/` |
| Endor Labs Vulnerability Explainer | Understand a specific CVE, GHSA, or Endor vulnerability and what to do next | `claude-code/vulnerability-explainer/` | `claude-managed-agents/vulnerability-explainer/` | `github-copilot-plugin/vulnerability-explainer/` |

## Supported Hosts

| Host | Generated path | Typical install target |
| --- | --- | --- |
| Claude Code | `claude-code/<agent>/<edition>/` | `.claude/agents/` in the target repository |
| Claude Managed Agents | `claude-managed-agents/<agent>/<edition>/` | Anthropic Console or `ant` CLI agent and environment creation |
| GitHub Copilot / AgentHQ plugin | `github-copilot-plugin/<agent>/<edition>/` | Copilot plugin package or AgentHQ app repository contents |

## Editions

Each agent is published in one or more editions. If an edition does not apply
to a host, the catalog omits that host/edition directory.

| Edition | Best for | Signals | Shell/execute access |
| --- | --- | --- | --- |
| Developer Edition | Fast, low-friction checks | Endor Model Context Protocol (MCP) tools | Not allowed |
| Enterprise Edition | Richer Endor context when the agent supports it | Endor MCP tools, plus documented read-only `endorctl api` lookups for agents that need them | Agent-specific; always read-only |

Use **Developer Edition** when you want the safest default with no Bash or
execute access.

Use **Enterprise Edition** when you have authenticated Endor setup and want
the highest-fidelity signals available for that agent. Some Enterprise
Edition agents are still MCP-only; their generated host configuration leaves
shell or `execute` access disabled when no read-only `endorctl api` lookups
are required.

## Install An Agent

Pick an agent from the catalog, then choose the host and edition directory
that matches your environment.

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

### GitHub Copilot / AgentHQ

Install the generated plugin package with GitHub Copilot CLI from the
package directory.

```bash
cd /path/to/endor-labs-agent-kit/github-copilot-plugin/vulnerability-explainer/developer-edition
copilot plugin install .
```

For AgentHQ, use the generated plugin package as the public plugin repository
contents for the corresponding Agentic App and edition.

## Configure Endor Access

| Access path | Used by | Notes |
| --- | --- | --- |
| Endor MCP | Developer Edition and Enterprise Edition agents | Required for every published agent. Configure it through the target host's MCP mechanism. |
| Read-only `endorctl api` | Enterprise Edition agents that need tenant or project data beyond public MCP tools | The generated prompts constrain commands to documented read-only lookups. Per-edition README files link to `endorctl-setup.md` when needed. |
| GitHub Actions keyless auth | Enterprise GitHub Copilot / AgentHQ plugins that need tenant data | Configure the target repository using `github-copilot-plugin/ENDOR_GITHUB_KEYLESS_AUTH.md`. |

## Example Prompts

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

Endor Labs Tenant Findings:

```text
@agent-tenant-findings show reachable findings for project <project_uuid>
```

Endor Labs Upgrade Impact Analysis:

```text
@agent-upgrade-impact-analysis show the safest upgrade path for project <project_uuid> package lodash
```

Endor Labs Vulnerability Explainer:

```text
@agent-vulnerability-explainer explain CVE-2021-44228
```

## Output Contract

Agents return concise prose plus a JSON block. The exact schema depends on the
agent. If a signal is unavailable because of setup, authentication, account
tier, or tooling, agents record that in `data_gaps` instead of inventing
evidence.

## Safety Model

The agents in this kit are read-only.

They do not:

- edit files
- create pull requests
- run scans
- dismiss findings
- create policies
- mutate Endor Labs state

When an agent permits Bash, its prompt limits Bash to documented read-only Endor
lookup commands. Claude Code artifacts deny Bash when it is not needed.
When a recipe declares `host_capabilities_required.read_files: true`,
Claude Code artifacts allow only `Read`, `Glob`, `Grep`, and `LS` for
read-only workspace inspection; file mutation, notebook, web, and todo tools
remain denied.
Claude Managed Agents artifacts omit the pre-built agent toolset unless an
agent needs read-only Bash, and then enable only Bash with confirmation.
GitHub Copilot plugins enable `execute` only for Enterprise Edition agents
that require the documented read-only Endor lookups.

## Contribute An Agent

This repository is both the source of truth and the distribution catalog.
Contributor workflow is recipe-first: edit source files under `agents/`, then
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

1. Edit `agents/<agent>/recipe.yaml`.
2. Edit `agents/<agent>/instructions.md`.
3. Update `agents/<agent>/evals/cases.yaml`.
4. Add or update tests under `tests/`.
5. Validate and regenerate the catalog.

```bash
endor-agent-kit validate agents/<agent>/recipe.yaml
endor-agent-kit publish agents/*/recipe.yaml --dest . --prune
python -m pytest -q
git diff --exit-code -- README.md manifest.json claude-code claude-managed-agents github-copilot-plugin
```

Pull requests should include both source changes and regenerated artifacts.
CI runs the same validation and generated-artifact drift check.

### CLI Reference

| Command | Purpose |
| --- | --- |
| `endor-agent-kit validate agents/<agent>/recipe.yaml` | Validate one recipe. |
| `endor-agent-kit compile agents/<agent>/recipe.yaml --target <host>` | Compile one recipe into its local `dist/` directory. |
| `endor-agent-kit compile agents/<agent>/recipe.yaml --target <host> --edition <edition>` | Compile one edition for one host. |
| `endor-agent-kit publish agents/*/recipe.yaml --dest . --prune` | Regenerate the checked-in catalog and remove stale generated agents. |

Supported compile targets are `claude-code`, `claude-managed-agents`,
`github-copilot-plugin`, and `raw`.

## Recipe Reference

Recipes are YAML files with schema version `1`. They describe the agent's
prompt, Endor access paths, host capabilities, inputs, outputs, evals, and
published host editions.

| Field | Purpose |
| --- | --- |
| `id`, `name`, `version`, `description` | Public catalog identity and copy. |
| `safety_class`, `mutations` | Safety contract. v1 launch recipes are read-only and must not declare mutations. |
| `supported_transports` | Endor access paths such as `mcp` and `endorctl_api`. |
| `host_capabilities_required` | Abstract host capabilities that compilers map to host-specific tools. |
| `inputs`, `outputs` | User-facing IO contract and expected JSON output shape. |
| `compatible_hosts` | Hosts that should receive generated artifacts. |
| `host_editions` | Optional host-specific edition selection. Omit to publish all default editions for that host. |
| `required_endor_mcp_tools`, `endorctl_api_invocations` | Endor tools and read-only API lookups the prompt may use. |
| `instructions_path`, `evals` | Source prompt and eval case files relative to the recipe. |

Generated artifacts must not be edited as the first step. Change the recipe
or instructions source, publish the catalog, then review the generated diff.

## Repository Reference

### Layout

```text
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
github-copilot-plugin/
  dependency-decision-helper/
    developer-edition/
      README.md
      dependency-decision-helper.agent.md
      plugin.json
    enterprise-edition/
      README.md
      dependency-decision-helper.agent.md
      plugin.json
  package-risk-summary/
    developer-edition/
      README.md
      package-risk-summary.agent.md
      plugin.json
    enterprise-edition/
      README.md
      package-risk-summary.agent.md
      plugin.json
  tenant-findings/
    enterprise-edition/
      README.md
      tenant-findings.agent.md
      plugin.json
  upgrade-impact-analysis/
    developer-edition/
      README.md
      upgrade-impact-analysis.agent.md
      plugin.json
    enterprise-edition/
      README.md
      upgrade-impact-analysis.agent.md
      plugin.json
  vulnerability-explainer/
    developer-edition/
      README.md
      vulnerability-explainer.agent.md
      plugin.json
    enterprise-edition/
      README.md
      vulnerability-explainer.agent.md
      plugin.json
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
- `github-copilot-plugin/`
- `manifest.json`

These paths are customer-facing and should stay stable.

## Release And License

Before publishing a public release, verify that generated artifacts are fresh
and that Endor Labs has selected and added the final open-source license.

License information will be added before public release.
