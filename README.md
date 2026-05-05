# Endor Labs Agent Kit

Ready-to-use Endor Labs agents for AI coding assistants.

This repository contains customer-facing agent artifacts that you can install in
supported coding assistants. The agents bring Endor Labs dependency risk
intelligence into the place where engineering decisions happen: the development
workflow.

## Available Agents

| Agent | Use it when you want to... | Claude Code | Claude Managed Agents | GitHub Copilot / AgentHQ plugin |
| --- | --- | --- | --- | --- |
| Dependency Decision Helper | Decide whether to add, upgrade to, or keep a specific package version | `claude-code/dependency-decision-helper/` | `claude-managed-agents/dependency-decision-helper/` | `github-copilot-plugin/dependency-decision-helper/` |
| Endor Labs Package Risk Summary | Summarize the risk profile of a specific package version | `claude-code/package-risk-summary/` | `claude-managed-agents/package-risk-summary/` | `github-copilot-plugin/package-risk-summary/` |
| Endor Labs Upgrade Impact Analysis | Analyze AURI-style upgrade impact with VersionUpgrade, CIA, findings, and manifest context | `claude-code/upgrade-impact-analysis/` | `claude-managed-agents/upgrade-impact-analysis/` | `github-copilot-plugin/upgrade-impact-analysis/` |
| Endor Labs Vulnerability Explainer | Understand a specific CVE, GHSA, or Endor vulnerability and what to do next | `claude-code/vulnerability-explainer/` | `claude-managed-agents/vulnerability-explainer/` | `github-copilot-plugin/vulnerability-explainer/` |

Currently supported hosts:

- Claude Code subagents
- Claude Managed Agents
- GitHub Copilot / AgentHQ plugin packages

## Quick Start

### Claude Code

Choose an agent and edition, copy the generated subagent into your target
repository, and restart Claude Code if needed.

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

Choose an agent and edition, update the MCP server URL and vault references
in the generated YAML templates, then create the agent and environment with
the Anthropic CLI or Console.

```bash
cd /path/to/endor-labs-agent-kit/claude-managed-agents/dependency-decision-helper/developer-edition
ant beta:agents create < agent.yaml
ant beta:environments create < environment.yaml
```

Use `session-template.yaml` as the starting point when creating sessions.

### GitHub Copilot / AgentHQ

Choose an agent and edition, then install the generated plugin package with
GitHub Copilot CLI from the package directory.

```bash
cd /path/to/endor-labs-agent-kit/github-copilot-plugin/vulnerability-explainer/developer-edition
copilot plugin install .
```

For AgentHQ, use the generated plugin package as the public plugin repository
contents for the corresponding Agentic App and edition.

## Editions

Each agent is published in one or more editions.

| Edition | Best for | Signals | Shell/execute access |
| --- | --- | --- | --- |
| Developer Edition | Fast, low-friction checks | Endor Model Context Protocol (MCP) tools | Not allowed |
| Enterprise Edition | Richer Endor context when the agent supports it | Endor MCP tools, plus documented read-only `endorctl api` lookups for agents that need them | Agent-specific; always read-only |

Use **Developer Edition** when you want the safest default with no Bash access.

Use **Enterprise Edition** when you have authenticated Endor setup and want the
highest-fidelity signals available for that agent. Some Enterprise Edition
agents are still MCP-only; their generated host configuration leaves shell
or `execute` access disabled when no read-only `endorctl api` lookups are
required.

## Example Prompts

Dependency Decision Helper:

```text
@agent-dependency-decision-helper assess npm lodash version 4.17.20
```

Endor Labs Package Risk Summary:

```text
@agent-package-risk-summary summarize npm lodash version 4.17.20
```

Endor Labs Upgrade Impact Analysis:

```text
@agent-upgrade-impact-analysis show the safest upgrade path for project <project_uuid> package lodash
```

Endor Labs Vulnerability Explainer:

```text
@agent-vulnerability-explainer explain CVE-2021-44228
```

## Output

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
Claude Managed Agents artifacts omit the pre-built agent toolset unless an
agent needs read-only Bash, and then enable only Bash with confirmation.
GitHub Copilot plugins enable `execute` only for Enterprise Edition agents
that require the documented read-only Endor lookups.

## Repository Layout

```text
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

`manifest.json` lists published artifacts and their SHA-256 checksums.

## Source And Releases

This repository is the distribution catalog. It contains ready-to-use artifacts
and setup docs.

The source recipes, validation tests, compilers, and promotion automation are
maintained separately by Endor Labs. Published artifacts are generated from that
source of truth and promoted into this distribution catalog.

## License

License information will be added before public release.
