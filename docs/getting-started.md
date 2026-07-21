# Getting Started

Use this guide when you want to install and run Endor Labs Agent Kit workflows.
If you are changing agent behavior or publishing the public distribution mirror,
use `docs/maintainer-guide.md` or `docs/distribution-sync.md` instead.

## Pick A Host

| Host | Start Here | Good Fit |
| --- | --- | --- |
| Claude Code | `plugins/claude/endor-labs-agent-kit/README.md` | Plugin install with Claude Code agents and setup skill. |
| Codex | `plugins/codex/endor-labs-agent-kit/README.md` | Plugin install with Codex skills plus optional managed custom-agent TOML files. |
| Gemini CLI | `plugins/gemini/endor-labs-agent-kit/README.md` | Gemini extension install with skills and preview subagents. |
| Antigravity CLI | `plugins/antigravity/endor-labs-agent-kit/README.md` | Antigravity plugin install with skills and subagents. |
| Cursor | `.cursor-plugin/`, root `agents/`, root `skills/`, root `hooks/`, and `assets/logo.png` | Cursor plugin metadata with generated workflow agents, support skills, and advisory hooks. |
| Cursor SDK | `cursor-sdk/README.md` | Python SDK automation for local workspaces, CI, orchestration, backend services, or Cursor cloud agents. |
| Manual single-agent install | `<host>/<agent>/README.md` | One workflow in one host without the full plugin package. |
| Runtime-neutral integration | `portable/<agent>/README.md` | Internal runtime with its own adapters, approvals, audit, and credentials. |

The public distribution repo is `endorlabs/ai-plugins`. This source repo owns
recipes, generation, tests, and guardrails.

Google documents Antigravity CLI as the consumer transition path for Gemini
CLI. Use the Gemini package for supported Gemini CLI environments and
compatibility checks; use the Antigravity package for affected Gemini CLI
consumer accounts.

## Install A Plugin

Claude Code public install for new users:

```text
/plugin marketplace add endorlabs/ai-plugins --sparse .claude-plugin plugins/claude
/plugin install endor-labs-agent-kit@endorlabs
/reload-plugins
/agents
```

Existing Claude Code users pinned to the historical id can keep using:

```text
/plugin marketplace add endorlabs/ai-plugins --sparse .claude-plugin plugins/claude
/plugin install ai-plugins@endorlabs
```

Do not enable `endor-labs-agent-kit@endorlabs` and `ai-plugins@endorlabs` in
the same Claude profile for normal use. They expose the same setup skill and
agents.

For Codex, Gemini CLI, Antigravity CLI, and Cursor, use the host package README
or package metadata because their public install commands depend on the pushed
tag and host-specific marketplace behavior. Cursor IDE uses `.cursor-plugin/`,
root `agents/`, root `skills/`, root advisory `hooks/`, and `assets/logo.png`;
Cursor SDK automation uses `cursor-sdk/`; Gemini uses
`plugins/gemini/endor-labs-agent-kit/`.

## Run Cursor SDK Automation

Use the SDK lane when the workflow should be launched from Python code instead
of installed into the Cursor IDE.

```bash
python3 -m pip install -r cursor-sdk/requirements.txt
export CURSOR_API_KEY="crsr_..."
python cursor-sdk/run_cursor_agent.py endor-configuration-automation-agent \
  --workspace /path/to/repo \
  "Explain what evidence you need to assess GitHub onboarding gaps. Keep it read-only."
```

For Cursor cloud agents:

```bash
python cursor-sdk/run_cursor_agent.py endor-sca-remediation-agent \
  --mode cloud \
  --repo-url https://github.com/your-org/your-repo \
  --ref main \
  "Prepare a remediation plan only. Do not edit files or open a PR."
```

## Run Setup First

After installing a plugin, ask the host to run the setup skill:

```text
Use the endor-agent-kit-setup skill to check Endor Agent Kit readiness.
```

Setup is readiness guidance. It can report missing `endorctl`, `gh`, namespace,
auth, MCP, or toolchain prerequisites. It must not run scans, run
`endorctl host-check`, edit shell profiles, install language runtimes, install
package managers, or write credentials.

## Choose A Workflow

| Job | Workflow |
| --- | --- |
| Triage Endor AI SAST findings | `ai-sast-remediation` |
| Assess CI/CD and supply chain posture | `cicd-posture` |
| Diagnose Endor setup, scan, auth, policy, or integration issues | `troubleshooting` |
| Browse, filter, and summarize existing Endor findings | `findings-browser` |
| Correlate supply-chain malware intelligence against tenant inventory | `malware-responder` |
| Probe GitHub onboarding and monitored-branch coverage gaps | `configuration-automation` |
| Find safe dependency remediation paths with Endor SCA evidence | `sca-remediation` |
| Compare package risk, make a dependency decision, or review repository dependencies | `dependency-reviewer` with the `package-risk`, `package-decision`, or `repository-review` profile |
| Preview remediation options without making changes | `remediation-planning` |
| Analyze upgrade impact or explain vulnerabilities | `oss-upgrade-investigator`, `vulnerability-explainer` |

Each workflow above is generated for the supported host packages. Use the
selected host README for exact invocation names and install paths.

## First Prompts

```text
Use the ai-sast-remediation skill to triage AI SAST findings for this repository. Do not edit files, open a PR/MR, or create an Endor policy unless I approve the specific gate.
```

```text
Use the sca-remediation skill to check this repository for P0 SCA findings I can start remediating. Do not edit files or open a PR/MR until I approve.
```

```text
Use the configuration-automation skill to probe GitHub org <org> for Endor monitored-branch onboarding gaps and setup prescriptions. Keep the workflow read-only.
```

```text
Use the troubleshooting skill to diagnose this Endor issue from redacted error text and read-only tenant evidence. Keep the workflow read-only.
```

```text
Use the cicd-posture skill to assess CI/CD and supply chain posture for namespace <namespace>. Keep it read-only and validate the deterministic score.
```

```text
Use the findings-browser skill to show the critical and high reachable findings for namespace <namespace>. Keep it read-only.
```

## Safety Expectations

- Setup and read-only workflows must not mutate Endor, source providers, package managers, or repositories.
- Mutating workflows split file edits, branch pushes, PR/MR creation, PR/MR comments, tickets, approval verification, and Endor policy writes into separate approval gates.
- Agents must report unavailable evidence in `data_gaps` instead of inventing facts.
- Secret values must never be printed, persisted, copied into prompts, or written into generated artifacts.

## More Detail

- Agent and host catalog: `README.md`
- Renamed and consolidated agent identifiers: `docs/agent-identity-migration.md`
- Agent-facing operating rules: `docs/for-agents.md`
- Maintainer workflow: `docs/maintainer-guide.md`
- Public mirror sync: `docs/distribution-sync.md`
- Runtime-neutral adapter requirements: `docs/portable-runtime-conformance.md`
