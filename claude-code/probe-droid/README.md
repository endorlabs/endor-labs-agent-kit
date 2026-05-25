# Probe Droid

Use this agent when the user wants to assess GitHub repository onboarding
gaps for Endor Labs monitored-branch coverage. Probe Droid compares
github.com organization or repository inventory with Endor project, GitHub
App, package, scan, scan profile, package manager integration, dependency
resolution, and reachability evidence, then returns human-readable setup
actions without mutating source, GitHub, or Endor state.

## Install

Copy `probe-droid.md` into your target repository's `.claude/agents/` directory,
then restart Claude Code if needed.

## Requirements

- Claude Code with the generated subagent file installed.
- Authenticated endorctl for the read-only API lookups documented in endorctl-setup.md.
- Read-only GitHub.com credentials through `gh` or exported GitHub repository inventory JSON.

## Setup Checklist

### 1. Install The Subagent

Run this from the target repository or admin workspace where Claude Code
will perform the read-only inventory:

```bash
mkdir -p .claude/agents
cp /path/to/endor-labs-agent-kit/claude-code/probe-droid/probe-droid.md \
  .claude/agents/probe-droid.md
```

### 2. Verify Read-Only Access

Run these read-only checks when live GitHub inventory is available:

```bash
endorctl --version
gh auth status        # GitHub inventory
```

Probe Droid does not need an Endor MCP server. If Endor access, GitHub
read permissions, scan profile data, package manager integration data, or
repository contents are unavailable, the agent should report the missing
setup in `data_gaps`.

### 3. Keep The Probe Read-Only

The agent may list GitHub repositories, fetch specific manifest or CI files,
and query Endor projects, GitHub App evidence, monitored-branch scans, packages,
scan profiles, and package manager integrations. It should not run scans,
clone repositories, edit files, change GitHub settings, create profiles,
update integrations, or open PRs/MRs.

## Example

```text
@agent-probe-droid probe GitHub org <org> for Endor monitored-branch onboarding gaps and setup prescriptions
```

## Example Workflow

Use these copy/paste prompts after the agent is installed.

```text
@agent-probe-droid probe GitHub org <org> for Endor monitored-branch onboarding gaps. Compare GitHub.com repositories with Endor projects, GitHub App coverage, dependency resolution, reachability, scan profiles, toolchains, and package manager integrations. Do not run scans or mutate anything.
```

```text
@agent-probe-droid compare these GitHub repositories with Endor and prescribe the scan profiles, toolchains, private package integrations, and call graph setup needed for clean monitored-branch onboarding: <repo-url-1>, <repo-url-2>
```

The result should prioritize shared setup that unblocks the most repositories
first, while separating not-yet-onboarded repositories from onboarded-but-gapped
repositories and keeping PR scan coverage in future scope.

## Architecture

![Probe Droid architecture](architecture.svg)

This read-only agent compares GitHub.com repository inventory with Endor project, GitHub App, monitored-branch scan, package, scan profile, toolchain, and package-manager evidence. It returns onboarding lanes, reason codes, evidence queries, and setup prescriptions, but does not run scans, create profiles, edit repositories, change GitHub settings, or mutate Endor state.

## Notes

- This agent compares GitHub.com repository inventory with Endor project, GitHub App, package, monitored-branch scan, scan profile, toolchain, and package-manager evidence.
- It uses read-only Endor and GitHub lookups to produce onboarding lanes, reason codes, evidence queries, and setup prescriptions.
- It must not run scans, clone repositories, create scan profiles, update package manager integrations, change GitHub settings, open PRs/MRs, or mutate Endor state.
