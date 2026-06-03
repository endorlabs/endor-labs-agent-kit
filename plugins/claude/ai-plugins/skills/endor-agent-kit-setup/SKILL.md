---
name: endor-agent-kit-setup
description: Use when setting up Endor Labs Agent Kit for Claude Code, checking readiness, verifying Endor auth, choosing namespaces, or diagnosing missing endorctl, gh, Endor MCP, or workflow prerequisites.
---

# Endor Agent Kit Setup For Claude Code

Generated for the Endor Labs AI Plugins (Legacy) Claude Code plugin.

## Claude Install And Upgrade Notice

- `ai-plugins@endorlabs` is retained for existing Claude Code users and pinned installs.
- New installs should prefer `endor-labs-agent-kit@endorlabs`.
- Existing users do not need an automatic migration; this package will keep working.
- Do not enable both Claude plugin ids in the same profile because they expose the same agents and setup skill.
- The plugin does not auto-disable, uninstall, or edit Claude settings for either id.

## Bundled Claude Code Agents

- `Triage AI SAST findings` -> Claude Code agent `ai-sast-triage`
- `Decide whether a dependency is safe to use` -> Claude Code agent `dependency-decision-helper`
- `Diagnose Endor setup and scan issues` -> Claude Code agent `endor-troubleshooter`
- `Summarize package-version risk` -> Claude Code agent `package-risk-summary`
- `Assess GitHub onboarding gaps` -> Claude Code agent `probe-droid`
- `Plan remediation across findings` -> Claude Code agent `remediation-planner`
- `Review repository dependency manifests` -> Claude Code agent `repository-dependency-reviewer`
- `Find safe SCA remediation paths` -> Claude Code agent `sca-remediation`
- `Analyze upgrade impact` -> Claude Code agent `upgrade-impact-analysis`
- `Explain vulnerability risk and remediation` -> Claude Code agent `vulnerability-explainer`

## Claude Code Plugin Install Commands

From the public ai-plugins distribution repository:

```text
/plugin marketplace add endorlabs/ai-plugins --sparse .claude-plugin plugins/claude
/plugin install ai-plugins@endorlabs
```

From a local checkout of the Agent Kit repository root:

```text
/plugin marketplace add ./
/plugin install ai-plugins@endorlabs
```

For package-only local validation, add the generated Claude marketplace:

```text
/plugin marketplace add ./plugins/claude
/plugin install ai-plugins@endorlabs
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
- Read `ENDOR_NAMESPACE` from the current process environment and report it as
  namespace provenance when present.
- Safely parse `~/.endorctl/config.yaml` for non-secret fields such as
  `ENDOR_API` and `ENDOR_NAMESPACE`.
- Report the presence of credential fields by key name only.
- Report the presence of `ENDOR_API_CREDENTIALS_*` authentication variables by
  key name only.
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
- Read, cat, source, recurse through, or point `ENDORCTL_CONFIG` or
  `--config-path` at tenant-specific, customer-specific, production, backup,
  or other non-default Endor config directories.
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
Namespace candidates:
- ENDOR_NAMESPACE: not set
- ~/.endorctl/config.yaml ENDOR_NAMESPACE: example-namespace
Selected namespace: example-namespace from ~/.endorctl/config.yaml
Auth: API credential fields present
Endor auth: verified for namespace example-namespace
Secret values: hidden
```

If a namespace is missing, say that a namespace is required before live Endor
lookups. If a namespace is detected, let the user use it or override it for the
current workflow.

If `ENDOR_NAMESPACE` from the current process environment and
`~/.endorctl/config.yaml` disagree, surface both values and stop before live
Endor lookups. Ask the user which namespace to use for this workflow. Do not
silently trust either value, and do not unset environment variables or edit
config files unless the user explicitly asks for that separate operational
cleanup.

When the user selects or supplies a namespace, later workflow agents must pass
it explicitly with `-n <namespace>` or `--namespace <namespace>` for scoped
Endor lookups rather than relying on bare `endorctl` namespace resolution.

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

## Claude-Specific Rules

- Prefer the default Claude Code user-scope plugin install unless the user explicitly requests project, local, or managed scope.
- Do not copy plugin-packaged agents into `.claude/agents/` when marketplace installation is available.
- Do not add plugin-wide MCP automatically. Only guide per-workflow MCP setup when the selected workflow needs it and the user approves.
- Claude Code plugin-shipped agents cannot declare `mcpServers`, `permissionMode`, or `hooks` in agent frontmatter; report unavailable MCP-only signals in `data_gaps`.
- Tell the user to restart or reload Claude Code after installing or updating the plugin.
