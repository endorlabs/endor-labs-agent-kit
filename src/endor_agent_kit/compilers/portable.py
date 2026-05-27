"""Portable runtime-neutral agent compiler."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from textwrap import dedent
from typing import Any

from endor_agent_kit.compilers.rendering import (
    instructions_for_edition,
)
from endor_agent_kit.prepared_source_recipe import PreparedSourceRecipe, prepare_source_recipe
from endor_agent_kit.recipe import ActionContract, EndorAgentRecipe, RecipeField
from endor_agent_kit.safety_posture import source_recipe_safety_posture

HOST = "portable"
PORTABLE_SCHEMA_VERSION = 1
PORTABLE_SECTION_EDITION = "enterprise-edition"

FORBIDDEN_PORTABLE_TOKENS = (
    "Claude Code",
    "Codex",
    "Claude Managed Agents",
    "Managed Agents",
    "subagent",
    "SKILL.md",
    "mcpServers:",
    "disallowedTools",
)

RUNTIME_ACTION_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "kind": "endor.query",
        "description": "Run read-only Endor evidence lookups through an approved Endor transport.",
        "provider_examples": ["endor-api", "endorctl-api", "approved-endor-mcp-adapter"],
    },
    {
        "kind": "repository.read",
        "description": "Read repository files, manifests, lockfiles, or pinned source context.",
        "provider_examples": ["repository-service", "source-index", "local-checkout"],
    },
    {
        "kind": "repository.patch.prepare",
        "description": "Prepare or apply a repository patch after explicit approval.",
        "provider_examples": ["patch-service", "dependency-update-service", "local-checkout"],
    },
    {
        "kind": "source.change_request.lookup",
        "description": "Look up existing branches, pull requests, merge requests, or internal change records.",
        "provider_examples": ["github", "gitlab", "bitbucket", "internal-change-service"],
    },
    {
        "kind": "source.change_request.create",
        "description": "Create or update a source-provider change request after explicit approval.",
        "provider_examples": ["github", "gitlab", "bitbucket", "internal-change-service"],
    },
    {
        "kind": "source.comment.create",
        "description": "Post or update a source-provider comment after explicit approval.",
        "provider_examples": ["github", "gitlab", "bitbucket", "internal-change-service"],
    },
    {
        "kind": "approval.request",
        "description": "Request approval through the runtime's approved review workflow.",
        "provider_examples": ["appsec-review-service", "source-review-api", "internal-approval-service"],
    },
    {
        "kind": "approval.verify",
        "description": "Verify approval evidence before a gated action proceeds.",
        "provider_examples": ["appsec-review-service", "source-review-api", "internal-approval-service"],
    },
    {
        "kind": "endor.policy.write",
        "description": "Create or reuse an Endor policy only after required approval and confirmation.",
        "provider_examples": ["endor-api", "endorctl-api"],
    },
    {
        "kind": "ticket.create",
        "description": "Create a ticket from final agent output through a runtime wrapper or declared action.",
        "provider_examples": ["jira", "servicenow", "linear", "internal-ticketing"],
    },
)


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
        _assert_portable_text(path.name, content)
        path.write_text(content, encoding="utf-8")
        outputs.append(path)
    return outputs


def _render_agent(
    recipe: EndorAgentRecipe,
    instructions: str,
    actions: tuple[ActionContract, ...],
) -> str:
    body = _portable_text(instructions_for_edition(instructions, PORTABLE_SECTION_EDITION))
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
                f"- portable_kind: `{_portable_kind(action)}`",
                f"- safety_class: `{action.safety_class}`",
                f"- confirmation_required: `{str(action.confirmation_required).lower()}`",
                f"- availability: `{action.availability}`",
            ]
        )
        if action.providers:
            lines.append(
                "- source_provider_examples: "
                + ", ".join(f"`{provider}`" for provider in action.providers)
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
        "declared_actions": declared_actions,
        "action_contracts_path": "actions.yaml" if actions else None,
        "runtime_action_vocabulary": _runtime_action_vocabulary(
            declared_actions,
            required_capabilities,
        ),
        "runtime_wrappers": [
            {
                "kind": "ticket.create",
                "status": "wrapper_available",
                "declared_by_recipe": _has_declared_kind(declared_actions, "ticket.create"),
                "confirmation_required": True,
                "provider_examples": ["jira", "servicenow", "linear", "internal-ticketing"],
            }
        ],
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
        "degradation": {
            "supports_plan_only": True,
            "missing_capability_behavior": "record_data_gap",
            "mutation_without_adapter": "forbidden",
        },
        "data_gap_policy": "Record unavailable transport, credential, adapter, runtime, or evidence signals in data_gaps instead of fabricating evidence.",
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
        "## Adapter Contracts",
        "",
    ]
    if actions:
        for action in actions:
            lines.extend(
                [
                    f"### {action.id}",
                    "",
                    f"- portable_kind: `{_portable_kind(action)}`",
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
        "portable_kind": _portable_kind(action),
        "safety_class": action.safety_class,
        "confirmation_required": action.confirmation_required,
        "availability": action.availability,
        "source_provider_examples": list(action.providers),
        "inputs": list(action.inputs),
        "outputs": list(action.outputs),
    }


def _portable_kind(action: ActionContract) -> str:
    by_id = {
        "fetch-pinned-source": "repository.read",
        "read-local-manifests": "repository.read",
        "resolve-upgrade-risk": "repository.read",
        "prepare-remediation-diff": "repository.patch.prepare",
        "open-change-request": "source.change_request.create",
        "post-decision-comment": "source.comment.create",
        "post-remediation-comment": "source.comment.create",
        "request-exception-review": "approval.request",
        "verify-appsec-approval": "approval.verify",
        "write-exception-policy": "endor.policy.write",
    }
    if action.id in by_id:
        return by_id[action.id]
    by_kind = {
        "endor.query": "endor.query",
        "scm.source_read": "repository.read",
        "scm.change_request": "source.change_request.create",
        "scm.comment": "source.comment.create",
        "approval.request": "approval.request",
        "approval.verify": "approval.verify",
        "endor.policy_write": "endor.policy.write",
        "ticket.create": "ticket.create",
    }
    return by_kind.get(action.kind, action.kind)


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
    return tuple(capabilities)


def _runtime_action_vocabulary(
    declared_actions: list[dict[str, Any]],
    required_capabilities: list[str],
) -> list[dict[str, Any]]:
    declared_by_kind: dict[str, list[dict[str, Any]]] = {}
    for action in declared_actions:
        declared_by_kind.setdefault(str(action["portable_kind"]), []).append(action)
    required = set(required_capabilities)

    vocabulary = []
    for definition in RUNTIME_ACTION_DEFINITIONS:
        kind = str(definition["kind"])
        declared = declared_by_kind.get(kind, [])
        if declared:
            status = "declared"
            confirmation_required = any(bool(action["confirmation_required"]) for action in declared)
            declared_by_recipe = True
        elif kind in required:
            status = "declared"
            confirmation_required = False
            declared_by_recipe = True
        elif kind == "ticket.create":
            status = "wrapper_available"
            confirmation_required = True
            declared_by_recipe = False
        else:
            status = "unavailable"
            confirmation_required = None
            declared_by_recipe = False
        vocabulary.append(
            {
                "kind": kind,
                "status": status,
                "declared_by_recipe": declared_by_recipe,
                "confirmation_required": confirmation_required,
                "description": definition["description"],
                "provider_examples": definition["provider_examples"],
            }
        )
    return vocabulary


def _has_declared_kind(declared_actions: list[dict[str, Any]], kind: str) -> bool:
    return any(action.get("portable_kind") == kind for action in declared_actions)


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
        ("MCP-free Claude Code artifact", "MCP-free portable agent bundle"),
        ("Claude Code session", "runtime session"),
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
        ("local git, read-only file tools, package-manager commands, and source-provider credentials", "runtime-provided repository, dependency, and source-provider adapters"),
        ("local source-provider credentials, git, and the target workspace", "runtime-provided repository and source-provider adapters"),
        ("source-provider tooling", "source-provider adapter"),
        ("source-provider credentials", "source-provider adapter credentials"),
        ("GitHub/GitLab", "source-provider"),
        ("GitHub or GitLab", "source-provider"),
        ("GitHub/GitLab review or comment", "source-provider review or comment"),
        ("GitHub/GitLab comments", "source-provider comments"),
        ("GitHub handles, GitLab usernames, or team slugs", "source-provider handles, usernames, or team slugs"),
        ("gh-cli", "source-provider adapter"),
        ("glab-cli", "source-provider adapter"),
        ("`git apply --check`", "the runtime patch-application check"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)

    text = re.sub(
        r"For GitHub this can be `gh pr list.*?Emit `change_requests\[\]\.existing_change_request_check`",
        "Use the runtime `source.change_request.lookup` adapter to check the proposed branch, finding UUID, and remote branch. Emit `change_requests[].existing_change_request_check`",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"use available source-provider tooling, such as `gh pr view --json reviews,comments` or equivalent GitLab commands/API calls,",
        "use the runtime `approval.verify` adapter",
        text,
    )
    text = text.replace("`gh pr list --head <branch> --state all`", "`source.change_request.lookup`")
    text = text.replace("`gh pr list --search <finding_uuid> --state all --json ...`", "`source.change_request.lookup`")
    text = text.replace("`git ls-remote --heads origin <branch>`", "`source.change_request.lookup`")
    text = text.replace("git, and the target workspace", "repository and source-provider adapters")
    text = text.replace("git and source-provider", "repository and source-provider")
    text = text.replace("local git", "runtime repository adapter")
    return text


def _assert_portable_text(name: str, content: str) -> None:
    for token in FORBIDDEN_PORTABLE_TOKENS:
        if token in content:
            raise ValueError(f"{HOST} {name}: forbidden host-specific token {token!r}")
