---
name: endor-agent-kit-setup
description: |
  Use when setting up Endor Labs Agent Kit for Codex, checking readiness,
  installing or updating bundled Codex custom agents, verifying Endor auth,
  or diagnosing missing endorctl, gh, namespace, or toolchain prerequisites.
---

# Endor Agent Kit Setup For Codex

Generated for the Endor Labs Agent Kit Codex plugin.

## Bundled Codex Custom Agents

- `ai-sast-triage` -> `endor-ai-sast-triage-agent`
- `endor-troubleshooter` -> `endor-troubleshooter-agent`
- `probe-droid` -> `endor-probe-droid-agent`
- `sca-remediation` -> `endor-sca-remediation-agent`

## Codex Agent Install Commands

Check installed Endor Codex agents:

```bash
python scripts/install_codex_agents.py --status
```

Install or update all bundled Endor Codex agents after user approval:

```bash
python scripts/install_codex_agents.py --install --yes
```

Uninstall only Endor Agent Kit-managed Codex agents after user approval:

```bash
python scripts/install_codex_agents.py --uninstall --yes
```

# Endor Agent Kit Setup

Use this setup workflow when the user asks to install, check, update, or remove
Endor Labs Agent Kit plugin support files, or when an Endor Agent Kit workflow
is blocked by missing `endorctl`, GitHub CLI, authentication, namespace, or
local toolchain readiness.

## Setup Contract

Be proactive about checking the environment, but do not make persistent changes
without explicit user approval. Report evidence for each check. Never print
secret values.

Setup may:

- Inspect command availability and versions for `endorctl`, `gh`, `git`, and
  workflow-relevant language tooling.
- Safely parse `~/.endorctl/config.yaml` for non-secret fields such as
  `ENDOR_API` and `ENDOR_NAMESPACE`.
- Report the presence of credential fields by key name only.
- Run lightweight read-only Endor auth verification when config or credentials
  are present.
- Offer re-authentication when verification fails.
- Check `gh` authentication and point to official installation guidance.
- Install, update, or uninstall host-specific Agent Kit support files only after
  explicit approval.

Setup must not:

- Run `endorctl scan`.
- Run `endorctl host-check`.
- Print `~/.endorctl/config.yaml` or secret values.
- Ask the user to paste API keys, API secrets, tokens, or passwords into chat.
- Write `ENDOR_API_CREDENTIALS_KEY` or `ENDOR_API_CREDENTIALS_SECRET`.
- Edit shell profile files such as `.zshrc`, `.bashrc`, or PowerShell profile.
- Install `gh`, package managers, language runtimes, Docker, JDKs, or build
  tooling.
- Configure MCP globally. MCP remains opt-in per recipe/workflow.

## Readiness Report

Start with a concise readiness report. Separate configured state from verified
state.

Include these sections when relevant:

- Ready
- Needs action
- Optional checks
- Available fixes

For Endor auth, report sanitized fields only:

```text
Endor config: found
API endpoint: https://api.endorlabs.com
Namespace: auri
Auth: API credential fields present
Endor auth: verified for namespace auri
Secret values: hidden
```

If a namespace is missing, say that a namespace is required before live Endor
lookups. If a namespace is detected, let the user use it or override it for the
current workflow.

## Endor Tooling

If `endorctl` is missing, offer documented install options in this order:

1. Package manager route when available, such as Homebrew or npm.
2. Direct binary download with checksum verification.

Only install `endorctl` after explicit approval. If installing to `~/bin`, tell
the user how to update `PATH` for the current shell. Do not edit shell profiles.

If API credential fields are present, do not run browser auth unless the user
explicitly asks to switch or re-authenticate. If API credential setup is needed,
tell the user to set `ENDOR_API_CREDENTIALS_KEY` and
`ENDOR_API_CREDENTIALS_SECRET` through their preferred secure environment
mechanism.

When browser or SSO authentication is requested, confirm the namespace first.
Use non-interactive flags where supported. If multi-tenant selection appears,
summarize the available tenant choices and ask the user before retrying.

## GitHub CLI

Check `gh auth status` when workflows need GitHub evidence, repository
inventory, pull requests, or comments. If `gh` is missing, provide current
official installation guidance instead of installing it automatically.

Do not manage GitHub token scopes or create personal access tokens in v1. Verify
only the specific read or write capability needed for the selected workflow.

## Language Tooling

Detect and report workflow-relevant package managers, language runtimes, and
build tools. Do not install them.

When tooling is missing, report the affected validation step and ask the user to
install it through their team-standard toolchain.

## Workflow Safety

Setup never performs remediation, creates branches, opens PRs/MRs, posts
comments, writes Endor policies, or runs scans. Mutating workflows such as SCA
Remediation and AI SAST Triage keep those actions behind their generated agent
approval gates.

## Codex-Specific Rules

- Install Codex custom agents globally by default under `${CODEX_HOME:-~/.codex}/agents`.
- Do not write project-local `.codex/agents/` files unless the user explicitly requests that advanced option.
- Use provenance-gated updates: missing files may be installed; managed stale files may be updated after approval; unknown files must not be overwritten.
- Tell the user to start a new Codex thread after installing or updating custom agents.
