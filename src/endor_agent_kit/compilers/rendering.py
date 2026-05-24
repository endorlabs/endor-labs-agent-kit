"""Shared Source Recipe prompt rendering helpers for Host compilers."""

from __future__ import annotations

from endor_agent_kit.recipe import ActionContract

EDITIONS = ("developer-edition", "enterprise-edition")
LEGACY_EDITION_ALIASES = {
    "standard": "developer-edition",
    "extended": "enterprise-edition",
}
LEGACY_SECTION_NAMES = {
    "developer-edition": "standard",
    "enterprise-edition": "extended",
}
EDITION_CHOICES = EDITIONS + tuple(LEGACY_EDITION_ALIASES)


def normalize_edition(value: str) -> str:
    """Normalize a public or legacy edition name."""

    edition = LEGACY_EDITION_ALIASES.get(value, value)
    if edition not in EDITIONS:
        raise ValueError(f"Unknown Claude Code edition {value!r}; allowed: {', '.join(EDITIONS)}")
    return edition


def instructions_for_edition(instructions: str, edition: str) -> str:
    """Render the shared and edition-specific instruction sections."""

    edition = normalize_edition(edition)
    shared = _section(instructions, "shared")
    mode = _edition_section(instructions, edition)
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


def _edition_section(text: str, edition: str) -> str:
    try:
        return _section(text, edition)
    except ValueError:
        legacy_name = LEGACY_SECTION_NAMES.get(edition)
        if legacy_name is not None:
            return _section(text, legacy_name)
        raise


def _section(text: str, name: str) -> str:
    start = f"<!-- {name}:start -->"
    end = f"<!-- {name}:end -->"
    try:
        after_start = text.split(start, 1)[1]
        return after_start.split(end, 1)[0].strip()
    except IndexError as exc:
        raise ValueError(f"instructions.md missing section markers for {name!r}") from exc

