"""Portable runtime-neutral agent compiler."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from textwrap import dedent
from typing import Any

import yaml

from endor_agent_kit.compilers.rendering import (
    instructions_for_edition,
)
from endor_agent_kit.prepared_source_recipe import PreparedSourceRecipe, prepare_source_recipe
from endor_agent_kit.portable_runtime_conformance import (
    DATA_GAP_POLICY,
    DEGRADATION_POLICY,
    PORTABLE_SCHEMA_VERSION,
    PORTABLE_UNTRUSTED_CONTENT_RULE,
    assert_portable_text,
    portable_kind,
    portable_provider_examples,
    required_runtime_control_lines,
    required_runtime_controls,
    runtime_action_vocabulary,
    runtime_wrappers,
)
from endor_agent_kit.recipe import ActionContract, EndorAgentRecipe, RecipeField
from endor_agent_kit.safety_posture import source_recipe_safety_posture

HOST = "portable"
PORTABLE_SECTION_EDITION = "enterprise-edition"


def compile_portable(recipe_path: str | Path) -> list[Path]:
    """Compile a recipe to a portable runtime-neutral bundle."""

    return compile_portable_prepared(prepare_source_recipe(recipe_path))


def compile_portable_prepared(prepared: PreparedSourceRecipe) -> list[Path]:
    """Compile a prepared Source Recipe to portable artifacts."""

    recipe_file = prepared.path
    recipe = prepared.recipe
    out_dir = recipe_file.parent / "dist" / HOST / recipe.id
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    artifacts = {
        out_dir / "agent.md": _render_agent(recipe, prepared.instructions, prepared.actions),
        out_dir / "agent.manifest.json": _render_manifest(
            recipe,
            prepared.actions,
            has_architecture=prepared.architecture_path.is_file(),
        ),
        out_dir / "output-contract.md": _render_output_contract(recipe, prepared.actions),
    }
    outputs: list[Path] = []
    for path, content in artifacts.items():
        assert_portable_text(path.name, content)
        path.write_text(content, encoding="utf-8")
        outputs.append(path)
    return outputs


def portable_text(text: str) -> str:
    """Rewrite host-specific text into portable runtime-neutral wording."""

    return _portable_text(text)


def render_portable_actions_yaml(actions: tuple[ActionContract, ...]) -> str:
    """Render action contracts for portable adapter implementers."""

    content = yaml.safe_dump(
        {"actions": [_portable_action_record(action) for action in actions]},
        sort_keys=False,
        allow_unicode=False,
    )
    assert_portable_text("actions.yaml", content)
    return content


def _render_agent(
    recipe: EndorAgentRecipe,
    instructions: str,
    actions: tuple[ActionContract, ...],
) -> str:
    body = _portable_text(
        instructions_for_edition(
            instructions,
            PORTABLE_SECTION_EDITION,
            recipe_id=recipe.id,
            structured_output_recipe=recipe,
        )
    )
    return (
        f"# {recipe.name}\n\n"
        f"{_portable_notice(recipe)}\n\n"
        f"{_portable_runtime_contract(recipe)}\n\n"
        f"{body.rstrip()}\n"
        f"{_render_runtime_action_contracts(actions)}"
    ).rstrip() + "\n"


def _portable_notice(recipe: EndorAgentRecipe) -> str:
    return dedent(
        f"""\
        Generated from Endor Agent Kit recipe `{recipe.id}` v{recipe.version} for portable runtimes.
        Treat this file as generated. Configure runtime adapters and wrapper policy outside this bundle.
        """
    ).strip()


def _portable_runtime_contract(recipe: EndorAgentRecipe) -> str:
    posture = source_recipe_safety_posture(recipe)
    lines = [
        "## Portable Runtime Contract",
        "",
        "Use this agent in a customer-managed runtime that provides the adapters declared in `agent.manifest.json`.",
        "The runtime owns authentication, authorization, logging, audit, adapter execution, and evidence capture.",
        "The agent owns reasoning, workflow sequencing, structured output, data-gap reporting, and approval-gate discipline.",
        "",
        "- Do not claim an action completed unless the runtime adapter performed it and returned evidence.",
        "- If a transport, credential, adapter, or permission is unavailable, record the missing signal in `data_gaps`.",
        "- Treat `ticket.create` as a runtime wrapper unless the Source Recipe declares a ticket action.",
        f"- {PORTABLE_UNTRUSTED_CONTENT_RULE}",
        "- Fail closed to plan-only output or `data_gaps` when approvals, permissions, or adapter evidence are missing.",
    ]
    if posture.is_mutating:
        lines.extend(
            [
                "- Ask for explicit approval before repository changes, source-provider mutations, ticket creation, comments, or Endor writes.",
                "- Present workflow target choices at the mutation gate, including plan-only output, source change request, ticket creation, or both when the runtime supports them.",
            ]
        )
    else:
        lines.append("- Keep the agent workflow read-only unless the runtime applies an approved wrapper action after final output.")
    if recipe.policy_pack_support:
        lines.append(
            "- Evaluate trusted organization policy packs before recommendations and before any mutation gate."
        )
    return "\n".join(lines)


def _render_runtime_action_contracts(actions: tuple[ActionContract, ...]) -> str:
    if not actions:
        return "\n\n## Action Contracts\n\nThis Source Recipe declares no agent-owned side-effect actions.\n"
    lines = [
        "",
        "## Action Contracts",
        "",
        "These are the semantic side effects this agent may discuss or request.",
        "Do not claim an action completed unless the runtime adapter performed it and returned evidence.",
        "",
    ]
    for action in actions:
        lines.extend(
            [
                f"### {action.id}",
                "",
                f"- kind: `{action.kind}`",
                f"- portable_kind: `{portable_kind(action.id, action.kind)}`",
                f"- safety_class: `{action.safety_class}`",
                f"- confirmation_required: `{str(action.confirmation_required).lower()}`",
                f"- availability: `{action.availability}`",
            ]
        )
        providers = portable_provider_examples(action.providers)
        if providers:
            lines.append(
                "- source_provider_examples: "
                + ", ".join(f"`{provider}`" for provider in providers)
            )
        if action.inputs:
            lines.append(f"- inputs: {', '.join(f'`{item}`' for item in action.inputs)}")
        if action.outputs:
            lines.append(f"- outputs: {', '.join(f'`{item}`' for item in action.outputs)}")
        if action.notes:
            lines.append(f"- notes: {_portable_text(action.notes)}")
        lines.append("")
    return "\n".join(lines)


def _render_manifest(
    recipe: EndorAgentRecipe,
    actions: tuple[ActionContract, ...],
    *,
    has_architecture: bool,
) -> str:
    posture = source_recipe_safety_posture(recipe)
    declared_actions = [_manifest_action(action) for action in actions]
    required_capabilities = sorted(
        set(_derived_capabilities(recipe)) | {item["portable_kind"] for item in declared_actions}
    )
    payload = {
        "portable_schema_version": PORTABLE_SCHEMA_VERSION,
        "recipe_schema_version": recipe.recipe_schema_version,
        "id": recipe.id,
        "name": recipe.name,
        "version": recipe.version,
        "description": _portable_text(recipe.description),
        "safety_class": recipe.safety_class,
        "required_transports": list(recipe.supported_transports),
        "requires_endorctl": recipe.requires_endorctl,
        "requires_endor_mcp": recipe.requires_endor_mcp,
        "required_endor_mcp_tools": list(recipe.required_endor_mcp_tools),
        "endorctl_api_invocations": list(recipe.endorctl_api_invocations),
        "required_capabilities": required_capabilities,
        "required_runtime_controls": required_runtime_controls(),
        "declared_actions": declared_actions,
        "action_contracts_path": "actions.yaml" if actions else None,
        "runtime_action_vocabulary": runtime_action_vocabulary(
            declared_actions,
            required_capabilities,
        ),
        "runtime_wrappers": runtime_wrappers(declared_actions),
        "inputs": [_field_record(field) for field in recipe.inputs],
        "outputs": [_field_record(field) for field in recipe.outputs],
        "artifacts": {
            "agent": "agent.md",
            "runtime_contract": "agent.manifest.json",
            "output_contract": "output-contract.md",
            "actions": "actions.yaml" if actions else None,
            "runtime_setup": "endorctl-setup.md" if posture.requires_endorctl_setup else None,
            "architecture": "architecture.svg" if has_architecture else None,
        },
        "degradation": dict(DEGRADATION_POLICY),
        "data_gap_policy": DATA_GAP_POLICY,
        "generated_files_are_editable": False,
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _render_output_contract(recipe: EndorAgentRecipe, actions: tuple[ActionContract, ...]) -> str:
    lines = [
        f"# {recipe.name} Output Contract",
        "",
        "This contract summarizes the structured inputs, outputs, runtime adapters, and optional mechanical gates for the portable bundle.",
        "",
        "## Safety And Transports",
        "",
        f"- safety_class: `{recipe.safety_class}`",
        f"- required_transports: {_inline_code_list(recipe.supported_transports)}",
        f"- endorctl_api_invocations: {_inline_code_list(recipe.endorctl_api_invocations)}",
        f"- required_endor_mcp_tools: {_inline_code_list(recipe.required_endor_mcp_tools)}",
        "",
        "## Inputs",
        "",
        *_field_lines(recipe.inputs),
        "",
        "## Outputs",
        "",
        *_field_lines(recipe.outputs),
        "",
        "## Data Gaps",
        "",
        "If an expected signal is unavailable because of credentials, account tier, runtime capabilities, source access, transport setup, or adapter failure, record that in `data_gaps` and continue only with verified evidence.",
        "",
        "## Runtime Control Requirements",
        "",
        *required_runtime_control_lines(),
        "",
        "## Adapter Contracts",
        "",
    ]
    if actions:
        for action in actions:
            lines.extend(
                [
                    f"### {action.id}",
                    "",
                    f"- portable_kind: `{portable_kind(action.id, action.kind)}`",
                    f"- confirmation_required: `{str(action.confirmation_required).lower()}`",
                    f"- inputs: {_inline_code_list(action.inputs)}",
                    f"- runtime_returns: {_inline_code_list(action.outputs)}",
                    "",
                ]
            )
    else:
        lines.extend(
            [
                "This Source Recipe declares no agent-owned side-effect actions.",
                "Runtime wrappers such as `ticket.create` may operate on final output after separate approval.",
                "",
            ]
        )
    lines.extend(_gate_contract_section(recipe.id))
    return "\n".join(lines).rstrip() + "\n"


def _gate_contract_section(agent_id: str) -> list[str]:
    if agent_id == "sca-remediation":
        return [
            "## Mechanical Workflow Gates",
            "",
            "- `selection-plan`",
            "- `apply`",
            "- `validate`",
            "- `pr`",
            "",
            "Validation helpers:",
            "",
            "- `endor-agent-kit validate-sca-output <payload.json> --gate selection-plan`",
            "- `endor-agent-kit render-sca-pr-body <payload.json>`",
            "- `endor-agent-kit lint-sca-pr-body <body.md>`",
            "",
        ]
    if agent_id == "ai-sast-triage":
        return [
            "## Mechanical Workflow Gates",
            "",
            "- `triage`",
            "- `remediation`",
            "- `pr`",
            "- `exception`",
            "",
            "Validation helpers:",
            "",
            "- `endor-agent-kit validate-ai-sast-output <payload.json> --gate remediation`",
            "- `endor-agent-kit render-ai-sast-pr-body <payload.json>`",
            "- `endor-agent-kit lint-ai-sast-pr-body <body.md>`",
            "- `endor-agent-kit render-ai-sast-approval-comment <payload.json>`",
            "- `endor-agent-kit lint-ai-sast-approval-comment <comment.md>`",
            "- `endor-agent-kit render-ai-sast-exception-policy-comment <payload.json>`",
            "- `endor-agent-kit lint-ai-sast-exception-policy-comment <comment.md>`",
            "",
        ]
    return []


def _manifest_action(action: ActionContract) -> dict[str, Any]:
    return {
        "id": action.id,
        "kind": action.kind,
        "portable_kind": portable_kind(action.id, action.kind),
        "safety_class": action.safety_class,
        "confirmation_required": action.confirmation_required,
        "availability": action.availability,
        "source_provider_examples": list(portable_provider_examples(action.providers)),
        "inputs": list(action.inputs),
        "outputs": list(action.outputs),
    }


def _portable_action_record(action: ActionContract) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": action.id,
        "kind": action.kind,
        "portable_kind": portable_kind(action.id, action.kind),
        "safety_class": action.safety_class,
        "confirmation_required": action.confirmation_required,
        "providers": list(portable_provider_examples(action.providers)),
        "required_runtime_capabilities": list(action.required_host_capabilities),
        "inputs": list(action.inputs),
        "outputs": list(action.outputs),
        "availability": action.availability,
    }
    if action.notes:
        record["notes"] = _portable_text(action.notes)
    return record


def _derived_capabilities(recipe: EndorAgentRecipe) -> tuple[str, ...]:
    capabilities: list[str] = []
    posture = source_recipe_safety_posture(recipe)
    if recipe.supported_transports or recipe.endorctl_api_invocations or recipe.required_endor_mcp_tools:
        capabilities.append("endor.query")
    if posture.can_read_files:
        capabilities.append("repository.read")
    if posture.can_write_files:
        capabilities.append("repository.patch.prepare")
    if posture.can_open_change_requests:
        capabilities.extend(["source.change_request.lookup", "source.change_request.create"])
    if recipe.policy_pack_support:
        capabilities.append("organization.policy.evaluate")
    return tuple(capabilities)


def _field_record(field: RecipeField) -> dict[str, Any]:
    return {
        "name": field.name,
        "kind": field.kind,
        "required": field.required,
        "description": _portable_text(field.description),
    }


def _field_lines(fields: tuple[RecipeField, ...]) -> list[str]:
    if not fields:
        return ["- none declared"]
    return [
        (
            f"- `{field.name}` ({field.kind}, "
            f"{'required' if field.required else 'optional'}): {_portable_text(field.description)}"
        )
        for field in fields
    ]


def _inline_code_list(values: tuple[str, ...]) -> str:
    if not values:
        return "`none`"
    return ", ".join(f"`{value}`" for value in values)


def _portable_text(text: str) -> str:
    """Rewrite host-specific text into portable runtime-neutral wording."""

    replacements = [
        (
            "Do not delegate this workflow to another subagent or Task/Agent tool.",
            "Do not delegate this workflow to another reasoning agent unless the runtime has an explicit orchestration contract that preserves required inputs, outputs, approval gates, and evidence records.",
        ),
        (
            "Use only Claude Code read-only file tools: `Glob`, `Grep`, `LS`, and `Read`.",
            "Use only runtime-provided read-only repository inspection adapters.",
        ),
        (
            "Use only Endor MCP tools and Claude Code read-only file tools.",
            "Use only Endor MCP tools and runtime-provided read-only repository inspection adapters.",
        ),
        (
            "Use `Glob`, `Grep`, `LS`, and `Read` to find and inspect supported manifest",
            "Use runtime-provided read-only repository inspection adapters to find and inspect supported manifest",
        ),
        (
            "Claude Code can use local repository context. Claude Managed Agents need the session or user message to provide repository URL, owner/repo, or Endor project name.",
            "Portable runtimes can provide repository context directly or accept a repository URL, owner/repo, or Endor project name from the session.",
        ),
        ("MCP-free Claude Code artifact", "MCP-free portable agent bundle"),
        ("Claude Code session", "runtime session"),
        ("Claude Code Workspace", "Runtime Workspace"),
        ("Claude Code artifact", "portable agent bundle"),
        ("Claude Code workspace", "runtime workspace"),
        ("Claude Code runs", "the runtime runs"),
        ("Claude Code", "the runtime"),
        ("Codex session", "runtime session"),
        ("Codex skill", "portable agent bundle"),
        ("Codex workspace", "runtime workspace"),
        ("Codex", "the runtime"),
        ("Claude Managed Agents", "customer-managed runtime"),
        ("Managed Agents", "customer-managed runtime"),
        ("subagent", "agent"),
        ("SKILL.md", "agent.md"),
        ("Task/Agent tool", "reasoning-agent tool"),
        ("host evidence", "runtime evidence"),
        ("host has Endor Agent Kit installed", "runtime has Endor Agent Kit installed"),
        ("host cannot infer it from a local checkout or session context", "runtime cannot infer it from repository context or session context"),
        ("host cannot infer it from a runtime-provided checkout or session context", "runtime cannot infer it from repository context or session context"),
        ("host signals", "runtime signals"),
        ("host tooling", "source-provider adapter"),
        ("host returns", "runtime returns"),
        ("installed host skill", "installed portable agent"),
        ("host shell's", "runtime shell's"),
        ("host-allowed scratch path", "runtime-approved scratch path"),
        ("host blocks", "runtime blocks"),
        ("source-host credential path from the local environment", "source-provider credential path from the runtime environment"),
        ("through the host", "through the runtime"),
        ("If a host cannot", "If the runtime cannot"),
        ("HOST RESPONSIBILITY", "RUNTIME RESPONSIBILITY"),
        ("local repository checkout", "runtime repository checkout"),
        ("read/write file tools and bash", "repository patch and command adapters"),
        ("git plus source-provider credentials", "repository plus source-provider adapters"),
        ("git plus source-provider adapter credentials", "repository plus source-provider adapters"),
        ("source-provider CLIs such as `gh` or `glab`", "source-provider adapters"),
        ("Use Bash only for documented read-only GitHub inventory/file calls", "Use runtime command execution only for documented read-only source-provider inventory/file calls"),
        ("Use Bash only for the documented read-only `endorctl api` lookups", "Use runtime command execution only for the documented read-only `endorctl api` lookups"),
        ("Use Bash only for read-only `endorctl api` lookups", "Use runtime command execution only for read-only `endorctl api` lookups"),
        ("Bash is allowed only for the read-only Endor lookups", "Runtime command execution is allowed only for the read-only Endor lookups"),
        ("Bash, authenticated `endorctl`", "runtime command execution, authenticated `endorctl`"),
        ("Do not use Bash or `endorctl`", "Do not use shell command execution or `endorctl`"),
        ("Do not use Bash", "Do not run shell commands"),
        ("even when Bash is available", "even when command execution is available"),
        ("Read-Only gh Or JSON", "Read-Only API Or JSON"),
        ("bounded read-only GitHub API or `gh` CLI calls", "bounded read-only source-provider API calls"),
        ("`gh` CLI", "source-provider CLI/API"),
        ("Use authenticated source-provider CLI/API first.", "Use an authenticated source-provider inventory adapter first."),
        ("Use authenticated `gh` CLI first.", "Use an authenticated source-provider inventory adapter first."),
        ("Run `gh auth status` when using live GitHub inventory.", "Use the runtime source-provider auth check when using live source-provider inventory."),
        ("Verify `gh auth status` and `endorctl --version`.", "Verify source-provider adapter authentication and `endorctl --version`."),
        ("List GitHub repositories once with `gh repo list <org> --limit 1000 --json ...`.", "List GitHub repositories once with the source-provider repository-list adapter."),
        ("Do not print the full `gh repo list` JSON array", "Do not print the full repository-list JSON array"),
        ("gh auth status", "source-provider.auth_check"),
        ("gh repo list <org> --limit 1000 --json nameWithOwner,url,defaultBranchRef,isArchived,isPrivate,primaryLanguage,pushedAt,updatedAt,isFork,visibility", "source-provider.repository_list <org>"),
        ("gh repo view <owner>/<repo> --json nameWithOwner,url,defaultBranchRef,isArchived,isPrivate,primaryLanguage,pushedAt,updatedAt,isFork,visibility", "source-provider.repository_get <owner>/<repo>"),
        ("gh api repos/<owner>/<repo>/git/trees/<tree_sha>", "source-provider.repository_tree <owner>/<repo> <tree_sha>"),
        ("`gh repo list`", "the source-provider repository-list adapter"),
        ("`gh repo view`", "the source-provider repository-detail adapter"),
        ("`gh api` commands", "source-provider API calls"),
        ("`gh api`", "the source-provider file/tree adapter"),
        ("live `gh` inventory", "live source-provider inventory"),
        ("`gh` inventory", "source-provider inventory"),
        ("`gh` commands", "source-provider API calls"),
        ("`gh` is unavailable", "the source-provider inventory adapter is unavailable"),
        ("`gh` may be unavailable", "the source-provider inventory adapter may be unavailable"),
        ("from `gh` or exported JSON", "from live source-provider inventory or exported JSON"),
        ("when `gh` is not", "when live source-provider inventory is not"),
        ("`gh`", "source-provider inventory adapter"),
        ("gh CLI live inventory", "live source-provider inventory"),
        ("managed session", "runtime session"),
        ("local git, read-only file tools, package-manager commands, and source-provider credentials", "runtime-provided repository, dependency, and source-provider adapters"),
        ("local source-provider credentials, git, and the target workspace", "runtime-provided repository and source-provider adapters"),
        ("local source-provider credentials", "runtime-provided source-provider adapter credentials"),
        ("local file writes", "runtime-approved file writes"),
        ("local checkout", "runtime-provided checkout"),
        ("local source repository", "runtime-provided source repository"),
        ("local source/validation", "runtime-provided source/validation"),
        ("local source usage", "runtime-provided source usage"),
        ("local source before deciding", "runtime-provided source before deciding"),
        ("source-provider tooling", "source-provider adapter"),
        ("source-provider credentials", "source-provider adapter credentials"),
        ("GitHub/GitLab review or comment", "source-provider review or comment"),
        ("GitHub/GitLab comments", "source-provider comments"),
        ("GitHub/GitLab", "source-provider"),
        ("GitHub or GitLab", "source-provider"),
        ("GitHub handles, GitLab usernames, or team slugs", "source-provider handles, usernames, or team slugs"),
        ("gh-cli", "source-provider adapter"),
        ("glab-cli", "source-provider adapter"),
        ("`git apply --check`", "the runtime patch-application check"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)

    text = re.sub(
        r"For (?:GitHub|source-provider) this can be `gh pr list.*?Emit `change_requests\[\]\.existing_change_request_check`",
        "Use the runtime `source.change_request.lookup` adapter to check the proposed branch, finding UUID, and remote branch. Emit `change_requests[].existing_change_request_check`",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"use available source-provider (?:tooling|adapter), such as `gh pr view --json reviews,comments` or equivalent GitLab commands/API calls,",
        "use the runtime `approval.verify` adapter",
        text,
    )
    text = re.sub(r"current Claude\s+Code workspace", "current runtime workspace", text)
    text = re.sub(r"Claude\s+Code session", "runtime session", text)
    text = re.sub(r"Claude\s+Code workspace", "runtime workspace", text)
    text = re.sub(r"Claude\s+Code", "the runtime", text)
    text = re.sub(r"Claude\s+Managed\s+Agents", "customer-managed runtime", text)
    text = re.sub(
        r"Bash\s+is allowed only for the read-only Endor\s+lookups",
        "Runtime command execution is allowed only for the read-only Endor lookups",
        text,
    )
    text = re.sub(
        r"In the runtime,\s+use the current repository and `origin` remote when available\. If the host\s+cannot inspect local git,",
        "When runtime repository context is available, use the current repository and `origin` remote. If a repository adapter is unavailable,",
        text,
    )
    text = text.replace(
        "the runtime can use local repository context. customer-managed runtime need the session or user message to provide repository URL, owner/repo, or Endor project name.",
        "Portable runtimes can provide repository context directly or accept a repository URL, owner/repo, or Endor project name from the session.",
    )
    text = text.replace(
        "In the runtime, first use the current repository context when it is available:",
        "When runtime repository context is available, use it first:",
    )
    text = text.replace(
        "In customer-managed runtime, do not assume runtime repository adapter is available;",
        "If a repository adapter is unavailable,",
    )
    text = text.replace(
        "In customer-managed runtime, do not assume local git is available;",
        "If a repository adapter is unavailable,",
    )
    text = text.replace("`gh pr list --head <branch> --state all`", "`source.change_request.lookup`")
    text = text.replace("`gh pr list --search <finding_uuid> --state all --json ...`", "`source.change_request.lookup`")
    text = text.replace("`git ls-remote --heads origin <branch>`", "`source.change_request.lookup`")
    text = text.replace("git, and the target workspace", "repository and source-provider adapters")
    text = text.replace("git and source-provider", "repository and source-provider")
    text = text.replace("local git", "runtime repository adapter")
    return text
