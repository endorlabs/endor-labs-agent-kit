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
current repository. Agent Kit owns the public authoring and publishing path for
new Endor/AURI-style agents. Private extraction tools may generate sanitized
draft inputs, but this repository must not depend on proprietary source
inspection or AURI-specific plucking logic.

The repository is source-first:

- contributors edit `source/agents/<agent>/recipe.yaml`
- contributors add `source/agents/<agent>/actions.yaml` for schema v2 agents
  with semantic side effects
- contributors edit `source/agents/<agent>/instructions.md`
- contributors edit `source/agents/<agent>/evals/cases.yaml`
- contributors add `source/agents/<agent>/architecture.svg`
- generated catalog artifacts stay checked in for users
- CI rejects stale generated artifacts

## Supported Public Inputs

Create agents from either public input shape:

- **Net-new agent brief:** the user describes the workflow, Endor evidence,
  target host, mutations, outputs, and success criteria.
- **Generic agent blueprint:** a sanitized YAML/JSON spec with recipe metadata,
  actions, instruction outline, eval scenarios, and architecture notes.

Blueprints must be generic. They may describe workflow intent, Endor resources,
I/O, safety class, action contracts, eval cases, and architecture. They must not
include AURI source paths, private code snippets, proprietary registry hashes,
or instructions that require Agent Kit to inspect the AURI codebase.

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
- one similar `source/agents/*/actions.yaml` when the new agent is mutating or
  adapter-backed
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
- use `recipe_schema_version: 2` plus `action_contracts_path: actions.yaml`
  when the agent opens change requests, writes comments, requests approvals, or
  depends on an external adapter

Use `supported_transports` this way:

- prefer `endorctl_api` for customer-tenant Endor evidence
- use `mcp` only when the requested public host artifact explicitly needs public
  Endor MCP tools
- do not add undocumented transports

For new customer-facing agents, default to MCP-free `endorctl_api` when tenant
data is needed. If a blueprint mentions MCP, treat it as source material and
remove the MCP dependency unless the agent specifically requires a public MCP
tool that cannot be expressed through documented Endor API or `endorctl api`
commands.

## Create Source Files

Create:

```text
source/agents/<agent-id>/
  recipe.yaml
  actions.yaml
  instructions.md
  evals/cases.yaml
  architecture.svg
```

The exact source files are `source/agents/<agent-id>/recipe.yaml`,
optional `source/agents/<agent-id>/actions.yaml`,
`source/agents/<agent-id>/instructions.md`, and
`source/agents/<agent-id>/evals/cases.yaml`, plus required
`source/agents/<agent-id>/architecture.svg`.

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

If the agent should publish only selected editions, add `host_editions`. When a
host has exactly one selected edition, the generated public layout is flattened
to `claude-code/<agent>/` or `claude-managed-agents/<agent>/`.

For schema v2 mutating agents, create `actions.yaml` with one action per
semantic side effect. Mutating actions must set `confirmation_required: true`.
Use `availability: requires_adapter` when the prompt can describe or request an
action but cannot complete it without a host service, such as Slack approval or
Endor policy writeback.

## Write Architecture

Every new agent must include `architecture.svg` in the same visual format as the
existing source-agent diagrams:

- `viewBox="0 0 1280 700"`
- dark background with radial glows
- horizontal workflow cards across the top half
- lower evidence/safety/host-boundary cards
- a bottom published-contract band

The diagram should describe the public agent contract, not private AURI runtime
internals.

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
- natural-language intake examples that do not require UUID-first payloads
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

For MCP-free agents, explicitly say that the agent must not require, configure,
or start an Endor MCP server. Generated artifacts should not mention
`mcpServers`, `endor-cli-tools`, or `endorctl ai-tools mcp-server`.

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
- `architecture.svg` is published with every generated catalog artifact
- schema v2 action contracts validate when the agent is mutating or adapter-backed
- generated artifacts carry load-bearing prompt rules
- generated tool restrictions match declared capabilities
- MCP-free agents do not emit MCP frontmatter or Endor MCP setup text
- `publish_recipe` writes the expected catalog surface
- eval case ids and output enum coverage match the intended v1 behavior

Do not rely only on broad publish tests.

## Validate And Regenerate

Run:

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest -q
endor-agent-kit validate source/agents/<agent-id>/recipe.yaml
endor-agent-kit authoring-check source/agents/<agent-id>/recipe.yaml --new-agent
endor-agent-kit publish source/agents/*/recipe.yaml --dest . --prune
git diff --check
```

Then verify:

```bash
python3 -m pytest -q
for recipe in source/agents/*/recipe.yaml; do endor-agent-kit validate "$recipe"; done
endor-agent-kit authoring-check source/agents/<agent-id>/recipe.yaml --new-agent
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
- host and edition/layout support
- safety capabilities
- tests and validation commands run
- any remaining data gaps or release blockers

Do not claim the agent works in a host until its generated artifact was inspected
or tested for that host.
