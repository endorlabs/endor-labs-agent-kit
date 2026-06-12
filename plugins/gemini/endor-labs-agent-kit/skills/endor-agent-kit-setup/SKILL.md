---
name: endor-agent-kit-setup
description: Use when setting up Endor Labs Agent Kit for Gemini CLI, checking readiness, verifying Endor auth, choosing namespaces, or diagnosing missing endorctl, gh, Gemini CLI, Endor MCP, or workflow prerequisites.
---

# Endor Agent Kit Setup For Gemini CLI

Generated for the Endor Labs Agent Kit Gemini CLI extension.

## Bundled Gemini CLI Workflows

- `Triage AI SAST findings` -> skill `ai-sast-triage`, subagent `@ai-sast-triage`
- `Assess CI/CD and supply chain posture` -> skill `cicd-posture`, subagent `@cicd-posture`
- `Diagnose Endor setup and scan issues` -> skill `endor-troubleshooter`, subagent `@endor-troubleshooter`
- `Browse existing Endor findings` -> skill `findings-browser`, subagent `@findings-browser`
- `Malware Response` -> skill `malware-response`, subagent `@malware-response`
- `Assess GitHub onboarding gaps` -> skill `probe-droid`, subagent `@probe-droid`
- `Find safe SCA remediation paths` -> skill `sca-remediation`, subagent `@sca-remediation`

## Gemini CLI Extension Install Commands

Install from the generated local extension package:

```bash
gemini extensions install /path/to/endor-labs-agent-kit/plugins/gemini/endor-labs-agent-kit
```

Install from the public GitHub repository after a release tag is published:

```bash
git clone --depth 1 --branch <tag> https://github.com/endorlabs/ai-plugins ai-plugins
gemini extensions install ./ai-plugins/plugins/gemini/endor-labs-agent-kit
```

Observed local validation on Gemini CLI 0.44.1: local installs may still
show a folder trust prompt even when `--consent` is supplied. Inspect the
extension package, approve only the expected Agent Kit folder,
then restart Gemini CLI so skills and subagents become visible.
Do not create or install zip archives for Gemini CLI; use the local extension
directory for local testing and clone the tagged GitHub repository before
installing the generated extension directory for release installs.

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
- Inspect Endor MCP support when a selected workflow needs MCP or the user asks
  for MCP setup.
- Offer host-specific Endor MCP configuration only after explaining the exact
  file, command, and validation step.
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
- Configure MCP globally without explicit user approval. MCP remains opt-in per
  recipe/workflow.

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

## Endor MCP

Prefer documented Endor API or `endorctl api` lookups for workflows that support
them. Configure Endor MCP only when a selected MCP-capable workflow needs it or
the user explicitly asks for it.

The distribution may include ready-to-use Endor MCP config snippets such as
root `.mcp.json` or Gemini `mcpServers` metadata. Treat those files as setup
inputs, not permission to start or register MCP without approval.

When MCP setup is requested:

1. Check whether `npx` is available.
2. Check whether `endorctl` is available.
3. Verify the proposed server command is:
   `npx -y endorctl ai-tools mcp-server`.
4. Inspect the host-specific MCP config location or installed plugin metadata.
5. If `endor-cli-tools` is already registered, report it and ask before
   changing anything.
6. If it is missing, show the exact config that would be added and ask for
   approval before writing host config files.
7. After approval and configuration, validate in a fresh host session when the
   host supports tool visibility checks.

Do not claim Endor MCP tools are available to a workflow until the host exposes
them in the current session. If MCP tools are unavailable, continue with
CLI-first workflows when they support `endorctl api`; otherwise record the
missing MCP capability in `data_gaps`.

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

## Gemini-Specific Rules

- Keep Gemini extension installs explicit. Do not install, link, update, or uninstall extensions without user approval.
- Do not add plugin-wide MCP automatically. Only guide MCP setup when a selected workflow needs it and the user approves.
- Do not collect, write, or persist Endor API credential values. Report credential presence by key name only.
- Gemini subagents are preview functionality; if subagent delegation is unavailable, use the matching skill and report the limitation.
- Tell the user to restart Gemini CLI after installing or updating the extension.
