---
name: create-endor-labs-agent
description: >
  Create or update an Endor Labs Agent Kit agent from source. Use when the user
  asks to make, add, build, author, contribute, or publish a new Endor Labs
  agent for this repository. Produces recipe.yaml, instructions.md, eval cases,
  focused tests, generated catalog artifacts, and validation results.
argument-hint: "[agent idea, target host, and required Endor signals]"
---

# Create Endor Labs Agent

Use this skill to create a production-ready Endor Labs Agent Kit agent in the
current repository.

The repository is source-first:

- contributors edit `source/agents/<agent>/recipe.yaml`
- contributors edit `source/agents/<agent>/instructions.md`
- contributors edit `source/agents/<agent>/evals/cases.yaml`
- generated catalog artifacts stay checked in for users
- CI rejects stale generated artifacts

## Confirm The Target

Before editing, confirm that the current repository contains:

- `pyproject.toml`
- `src/endor_agent_kit/`
- `source/agents/`
- `manifest.json`

If those are missing, ask for the path to `endor-labs-agent-kit`.

Read these files before designing the agent:

- `README.md`
- `src/endor_agent_kit/recipe.py`
- `src/endor_agent_kit/validator.py`
- one similar `source/agents/*/recipe.yaml`
- one similar `source/agents/*/instructions.md`
- one similar `tests/test_*_smoke.py`

## Pick The Agent Shape

Define the agent in one sentence:

```text
Use this agent when the user wants <workflow> using <Endor evidence> in <host>.
```

Choose the smallest safe host set:

- `claude-code` for agents that inspect the local workspace or work well as a
  local developer assistant
- `claude-managed-agents` for Anthropic-hosted agents that do not need local
  repository file access

Choose capabilities conservatively:

- `read_files: true` only when the agent must inspect local files
- `run_commands: true` only when the recipe supports `endorctl_api`
- `write_files: false` unless the agent is explicitly mutating
- `open_pr: false` unless the agent is explicitly mutating
- `mutations: []` for read-only and dry-run agents

Use `supported_transports` this way:

- `mcp` for public Endor MCP tools
- `endorctl_api` only for documented read-only tenant or OSS lookups
- do not add undocumented transports

## Create Source Files

Create:

```text
source/agents/<agent-id>/
  recipe.yaml
  instructions.md
  evals/cases.yaml
```

The exact source files are `source/agents/<agent-id>/recipe.yaml`,
`source/agents/<agent-id>/instructions.md`, and
`source/agents/<agent-id>/evals/cases.yaml`.

Use a lowercase kebab-case `agent-id`.

The recipe must declare:

- identity: `id`, `name`, `version`, `description`
- `safety_class: read_only`
- `endor_tier_minimum`
- `supported_transports`
- `host_capabilities_required`
- concrete `inputs`
- concrete `outputs`
- `compatible_hosts`
- `required_endor_mcp_tools`
- `endorctl_api_invocations`
- `instructions_path: instructions.md`
- `evals: evals/cases.yaml`
- `model: sonnet`

If the agent should publish only selected editions, add `host_editions`.

## Write Instructions

`instructions.md` must have these sections:

```markdown
<!-- shared:start -->
...
<!-- shared:end -->

<!-- developer-edition:start -->
...
<!-- developer-edition:end -->

<!-- enterprise-edition:start -->
...
<!-- enterprise-edition:end -->
```

The shared section must include:

- the agent role
- what question or workflow it answers
- read-only safety rules
- evidence rules
- data gap rules
- decision ladder or summary ladder
- required JSON output shape

Edition sections must say exactly which tools are allowed.

For Claude Code file-reading agents, state that only `Read`, `Glob`, `Grep`, and
`LS` are allowed. Do not allow Bash unless the recipe uses documented read-only
`endorctl api` lookups.

For Enterprise Edition agents with `endorctl_api`, include exact command shapes
and say not to generalize them to mutation commands.

## Write Eval Cases

Create at least four eval cases covering:

- the happy path
- a high-risk or critical path
- a missing-data or unavailable-tool path
- an edge case specific to the workflow

Each case should include:

- `id`
- `input`
- `expected.risk_posture`, `expected.verdict`, `expected.action`, or another
  output enum matching the recipe
- `expected.required_evidence`
- `expected.data_gaps_allowed`

## Add Tests

Add or update focused tests under `tests/`.

For every new agent, test:

- the recipe compiles for intended hosts and editions
- generated artifacts carry load-bearing prompt rules
- generated tool restrictions match declared capabilities
- `publish_recipe` writes the expected catalog surface
- eval case ids and output enum coverage match the intended v1 behavior

Do not rely only on broad publish tests.

## Validate And Regenerate

Run:

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest -q
endor-agent-kit validate source/agents/<agent-id>/recipe.yaml
endor-agent-kit publish source/agents/*/recipe.yaml --dest . --prune
git diff --check
```

Then verify:

```bash
python3 -m pytest -q
for recipe in source/agents/*/recipe.yaml; do endor-agent-kit validate "$recipe"; done
endor-agent-kit publish source/agents/*/recipe.yaml --dest . --prune
git diff --exit-code -- README.md manifest.json claude-code claude-managed-agents
```

If generated files changed, review them and keep them committed with the source
recipe.

## Final Report

Report:

- new or changed agent id
- source files created or changed
- generated catalog paths
- host and edition support
- safety capabilities
- tests and validation commands run
- any remaining data gaps or release blockers

Do not claim the agent works in a host until its generated artifact was inspected
or tested for that host.
