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


def instructions_for_edition(instructions: str, edition: str) -> str:
    """Render the shared and edition-specific instruction sections."""

    edition = normalize_edition(edition)
    sections = parse_instruction_sections(instructions)
    shared = sections.shared
    mode = sections.for_edition(edition)
    return f"{shared.rstrip()}\n\n{mode.rstrip()}\n"


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
