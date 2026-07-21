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
inspection or private extractor logic.

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
include private source paths, private code snippets, proprietary registry hashes,
or instructions that require Agent Kit to inspect a private codebase.

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
- `src/endor_agent_kit/structured_output_contracts.py` when the agent needs a
  strict final JSON contract
- `source/endor-knowledge-pack/query-recipes.yaml` when the agent depends on
  repeatable Endor evidence
- one similar `source/agents/*/recipe.yaml`
- one similar `source/agents/*/actions.yaml` when the new agent is mutating or
  adapter-backed
- one similar `source/agents/*/instructions.md`
- one similar `source/endor-knowledge-pack/workflows/*.yaml` when the agent has
  a multi-step Endor evidence workflow
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
- `codex` for Codex skills and bundled custom-agent plugin output
- `gemini` for Gemini CLI skills and subagent output
- `portable` for provider-neutral generated artifacts and manifests
- root `agents/`, `skills/`, `.cursor-plugin/`, and `cursor-sdk/` outputs are
  generated publication surfaces, not separate source agent definitions

Choose capabilities conservatively:

- `read_files: true` only when the agent must inspect local files
- `run_commands: true` only when the recipe supports `endorctl_agent_api`
- `write_files: false` unless the agent is explicitly mutating
- `open_pr: false` unless the agent is explicitly mutating
- `mutations: []` for read-only and dry-run agents
- use `recipe_schema_version: 2` plus `action_contracts_path: actions.yaml`
  when the agent opens change requests, writes comments, requests approvals, or
  depends on an external adapter

Use `supported_transports` this way:

- prefer `endorctl_agent_api` for customer-tenant Endor evidence
- use `mcp` only when the requested public host artifact explicitly needs public
  Endor MCP tools
- do not add undocumented transports

For new customer-facing agents, default to MCP-free `endorctl_agent_api` when tenant
data is needed. If a blueprint mentions MCP, treat it as source material and
remove the MCP dependency unless the agent specifically requires a public MCP
tool that cannot be expressed through a validated
`endorctl agent api --agent-id <agent-id>` command.

Use the canonical source recipe id as `<agent-id>` in every generated command.
All agents are read-only against Endor by default. The only permitted Endor
mutations are AI SAST `Policy` create and `Policy` update after its approval and
confirmation gates; never generate Policy delete or another resource mutation.

Do not introduce a runtime dependency on `endorlabs-sdk` or other private SDK
code while authoring public Agent Kit agents unless the maintainer explicitly
approves that dependency. Use source recipes, documented `endorctl_agent_api`
invocation shapes, Knowledge Pack query recipes, and generated prompt contracts
as the default public surface.

## Create Source Files

Create:

```text
  source/agents/<agent-id>/
  recipe.yaml
  actions.yaml        # schema v2 mutating or explicit adapter-backed workflows
  instructions.md
  evals/cases.yaml
  architecture.svg
```

The exact source files are `source/agents/<agent-id>/recipe.yaml`,
`source/agents/<agent-id>/instructions.md`, and
`source/agents/<agent-id>/evals/cases.yaml`, plus required
`source/agents/<agent-id>/architecture.svg`. Add
`source/agents/<agent-id>/actions.yaml` only when the recipe is schema v2
mutating or explicitly adapter-backed.

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
- `endorctl_agent_api_invocations`
- `instructions_path: instructions.md`
- `evals: evals/cases.yaml`
- `model: sonnet`

If the agent should publish only selected editions, add `host_editions`. When a
host has exactly one selected edition, the generated public layout is flattened
to `claude-code/<agent>/` or `claude-managed-agents/<agent>/`.

For schema v2 mutating agents, create `actions.yaml` with one action per
semantic side effect. For schema v2 adapter-backed read-only or dry-run agents,
create `actions.yaml` only when the runtime needs explicit action and evidence
contracts. Mutating actions must set `confirmation_required: true`. Use
`availability: requires_adapter` when the prompt can describe or request an
action but cannot complete it without a host service, such as Slack approval or
Endor policy writeback.

## Add Knowledge Pack And Output Contracts

For agents that depend on repeatable Endor evidence, add or update public
Knowledge Pack source:

```text
source/endor-knowledge-pack/workflows/<agent-id>.yaml
source/endor-knowledge-pack/query-recipes.yaml
```

Use these files to describe resource kinds, field masks, bounded query shapes,
namespace/traversal rules, completeness limits, and data-gap behavior. Keep the
workflow public and product-safe. Do not include private runtime QA logs,
private tenant details, local checkout paths, or proprietary extractor output.

For agents with structured runtime reports, add or update
`src/endor_agent_kit/structured_output_contracts.py` so generated prompts,
runtime validation, and future private QA consumers can agree on required
fields. The contract should encode the public final-output shape, not private
execution policy.

## Write Architecture

Every new agent must include `architecture.svg` in the same visual format as the
existing source-agent diagrams:

- `viewBox="0 0 1280 700"`
- dark background with radial glows
- horizontal workflow cards across the top half
- lower evidence/safety/host-boundary cards
- a bottom published-contract band

The diagram should describe the public agent contract, not private runtime
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
`endorctl agent api --agent-id <agent-id>` lookups.

For agents with `endorctl_agent_api`, include exact command shapes, require the
`endorctl agent api --help` capability preflight, and fail closed instead of
falling back to the unattributed legacy API command.

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
- Knowledge Pack workflow/query recipe coverage when the agent depends on
  repeatable Endor evidence
- structured output contract coverage when the agent promises a strict final
  JSON shape
- schema v2 action contracts validate when the agent is mutating or explicitly adapter-backed
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
endor-agent-kit doctor-new-agent source/agents/<agent-id>/recipe.yaml
endor-agent-kit authoring-check source/agents/<agent-id>/recipe.yaml --new-agent
endor-agent-kit publish source/agents/*/recipe.yaml --dest . --prune --include-plugins
endor-agent-kit check-guardrails --catalog-root .
endor-agent-kit verify-provenance --catalog-root .
git diff --check
```

Then verify:

```bash
python3 -m pytest -q
for recipe in source/agents/*/recipe.yaml; do endor-agent-kit validate "$recipe"; done
endor-agent-kit doctor-new-agent source/agents/<agent-id>/recipe.yaml
endor-agent-kit authoring-check source/agents/<agent-id>/recipe.yaml --new-agent
python scripts/check_new_agent_authoring.py --base-ref origin/main --command endor-agent-kit
endor-agent-kit publish source/agents/*/recipe.yaml --dest . --prune --include-plugins
endor-agent-kit check-guardrails --catalog-root .
endor-agent-kit verify-provenance --catalog-root .
git diff --exit-code -- README.md manifest.json .agents/plugins .claude-plugin .cursor-plugin agents assets claude-code claude-managed-agents codex cursor-sdk gemini plugins portable skills
```

If generated files changed, review them and keep them committed with the source
recipe.

`doctor-new-agent` is the first contributor-facing stop before opening the
Agent Kit PR. It is read-only and reports missing source layout, eval,
architecture, transport, and action-contract requirements before CI does.

## Prepare Lifecycle Handoff

When a private validation consumer needs to QA the generated agent, create a
public-neutral validation request from Agent Kit:

```bash
endor-agent-kit lifecycle prepare \
  --agent <agent-id> \
  --base-ref origin/main \
  --output /tmp/validation-request.json
```

The request may include source commit, branch, package version, agent ids,
provider targets, task profile ids, structured output contract ids, generated
drift status, warnings, and errors. It must not include absolute local checkout
paths, private runtime QA mechanics, raw logs, credentials, or machine-specific
host policy. Keep publish-readiness reports outside this public repository.

## Final Report

Report:

- new or changed agent id
- source files created or changed
- generated catalog paths
- host and edition/layout support
- Knowledge Pack and structured output contract changes, when present
- safety capabilities
- tests and validation commands run
- validation-request path or status when a lifecycle handoff was prepared
- any remaining data gaps or release blockers

Do not claim the agent works in a host until its generated artifact was inspected
or tested for that host.

## Prepare The Pull Request

After source files, generated artifacts, tests, and validation are complete,
prepare a PR in `endor-labs-agent-kit`, not `ai-plugins`.

The PR should use `.github/PULL_REQUEST_TEMPLATE/agent-source-change.md` and
include:

- source files created or changed
- generated host and plugin artifact paths
- architecture diagram path
- eval coverage summary
- safety class, host capabilities, and approval gates
- validation commands and results
- any known host-install or provider-validation gaps

If the host has GitHub CLI and the user explicitly approves opening the PR, the
assistant may create the branch and PR with `gh`. Otherwise, stop with the exact
branch name, commit message, PR title, PR body, and validation summary for a
maintainer to apply.

Do not open or edit a PR in `ai-plugins`. After an Agent Kit maintainer merges
the source PR, the publication workflow opens the generated `ai-plugins` PR.
