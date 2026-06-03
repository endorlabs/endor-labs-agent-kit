"""Shared Source Recipe prompt rendering helpers for Host compilers."""

from __future__ import annotations

from endor_agent_kit.instruction_sections import (
    EDITIONS,
    LEGACY_EDITION_ALIASES,
    normalize_edition,
    parse_instruction_sections,
)
from endor_agent_kit.recipe import ActionContract

EDITION_CHOICES = EDITIONS + tuple(LEGACY_EDITION_ALIASES)

ENDOR_NAMESPACE_PREFLIGHT = """## Endor Namespace Preflight

Before any Endor project-, finding-, package-, version-upgrade-, policy-, or repository-scoped lookup, resolve the namespace deliberately and record provenance. Preserve normal environment-variable auth and namespace selection: `ENDOR_NAMESPACE` and `ENDOR_API_CREDENTIALS_*` are supported inputs, but silent namespace conflicts are not.

Resolve namespace candidates in this order:

1. Explicit namespace supplied by the user in the current request.
2. `ENDOR_NAMESPACE` from the current process environment.
3. `ENDOR_NAMESPACE` from the default `~/.endorctl/config.yaml` only, read with a field-specific command or parser.
4. Namespace from already-resolved Endor project metadata.

If the user supplied a namespace in the current request, use that namespace explicitly with `-n <namespace>` or `--namespace <namespace>` and report any environment/config mismatch as overridden by the request. If `ENDOR_NAMESPACE` and the default config namespace both exist and differ, surface both values with provenance and stop for user confirmation before any scoped Endor or Endor MCP lookup. Do not silently trust either one.

After selecting a namespace, pass it explicitly with `-n <namespace>` or `--namespace <namespace>` for every scoped `endorctl api` lookup; do not rely on bare `endorctl` namespace resolution. If an Endor MCP call cannot be explicitly scoped to the selected namespace, use it only after proving the active process/config namespace matches the selected namespace. Otherwise use explicit `endorctl api -n <namespace>` or report a `data_gaps` entry.

Do not read, cat, source, recurse through, or point `ENDORCTL_CONFIG` or `--config-path` at `~/.endorctl/aigovernance/` or any path whose name contains `aigovernance` or `ai-governance`. Do not dump full Endor config files. Extract only the namespace key and never echo credential keys, secrets, tokens, or full config content.
"""


def instructions_for_edition(instructions: str, edition: str) -> str:
    """Render the shared and edition-specific instruction sections."""

    edition = normalize_edition(edition)
    sections = parse_instruction_sections(instructions)
    shared = sections.shared
    mode = sections.for_edition(edition)
    return f"{shared.rstrip()}\n\n{ENDOR_NAMESPACE_PREFLIGHT.rstrip()}\n\n{mode.rstrip()}\n"


def instructions_for_variant(instructions: str, variant: str) -> str:
    """Compatibility wrapper for old variant names."""

    return instructions_for_edition(instructions, variant)


def render_action_contracts(actions: tuple[ActionContract, ...]) -> str:
    """Render action contracts into the generated prompt body."""

    if not actions:
        return ""
    lines = [
        "",
        "## Action Contracts",
        "",
        "These are the semantic side effects this agent may discuss or request.",
        "Do not claim an action completed unless the host performed it and returned evidence.",
        "",
    ]
    for action in actions:
        lines.extend([
            f"### {action.id}",
            "",
            f"- kind: `{action.kind}`",
            f"- safety_class: `{action.safety_class}`",
            f"- confirmation_required: `{str(action.confirmation_required).lower()}`",
            f"- availability: `{action.availability}`",
        ])
        if action.providers:
            lines.append(f"- providers: {', '.join(f'`{provider}`' for provider in action.providers)}")
        if action.required_host_capabilities:
            lines.append(
                "- required_host_capabilities: "
                + ", ".join(f"`{capability}`" for capability in action.required_host_capabilities)
            )
        if action.inputs:
            lines.append(f"- inputs: {', '.join(f'`{item}`' for item in action.inputs)}")
        if action.outputs:
            lines.append(f"- outputs: {', '.join(f'`{item}`' for item in action.outputs)}")
        if action.notes:
            lines.append(f"- notes: {action.notes}")
        lines.append("")
    return "\n".join(lines)


def indent(text: str, spaces: int) -> str:
    """Indent text for generated frontmatter block scalars."""

    pad = " " * spaces
    return "\n".join(f"{pad}{line}" if line else pad for line in text.splitlines())
