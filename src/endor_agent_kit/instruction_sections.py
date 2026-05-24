"""Shared parsing for Source Recipe instruction sections."""

from __future__ import annotations

from dataclasses import dataclass

EDITIONS = ("developer-edition", "enterprise-edition")
LEGACY_EDITION_ALIASES = {
    "standard": "developer-edition",
    "extended": "enterprise-edition",
}
LEGACY_SECTION_NAMES = {
    "developer-edition": "standard",
    "enterprise-edition": "extended",
}


@dataclass(frozen=True)
class InstructionSections:
    """Structured instruction sections used by host compiler renderers."""

    shared: str
    developer_edition: str
    enterprise_edition: str

    def for_edition(self, edition: str) -> str:
        """Return the section body for a canonical edition name."""

        if edition == "developer-edition":
            return self.developer_edition
        if edition == "enterprise-edition":
            return self.enterprise_edition
        raise ValueError(f"Unknown Claude Code edition {edition!r}; allowed: {', '.join(EDITIONS)}")


def normalize_edition(value: str) -> str:
    """Normalize a public or legacy edition name."""

    edition = LEGACY_EDITION_ALIASES.get(value, value)
    if edition not in EDITIONS:
        raise ValueError(f"Unknown Claude Code edition {value!r}; allowed: {', '.join(EDITIONS)}")
    return edition


def parse_instruction_sections(
    instructions: str,
    *,
    allow_legacy: bool = True,
) -> InstructionSections:
    """Parse shared and edition-specific instruction sections."""

    return InstructionSections(
        shared=_section_from_any(instructions, ("shared",)),
        developer_edition=_section_from_any(
            instructions,
            _section_names("developer-edition", allow_legacy=allow_legacy),
        ),
        enterprise_edition=_section_from_any(
            instructions,
            _section_names("enterprise-edition", allow_legacy=allow_legacy),
        ),
    )


def _section_names(edition: str, *, allow_legacy: bool) -> tuple[str, ...]:
    if not allow_legacy:
        return (edition,)
    legacy_name = LEGACY_SECTION_NAMES.get(edition)
    if legacy_name is None:
        return (edition,)
    return (edition, legacy_name)


def _section_from_any(text: str, names: tuple[str, ...]) -> str:
    errors: list[str] = []
    for name in names:
        try:
            return _section(text, name)
        except ValueError as exc:
            errors.append(str(exc))
    if len(names) == 1:
        raise ValueError(errors[0])
    raise ValueError(
        "instructions.md missing section markers for "
        + " or ".join(repr(name) for name in names)
    )


def _section(text: str, name: str) -> str:
    start = f"<!-- {name}:start -->"
    end = f"<!-- {name}:end -->"
    if start not in text and end not in text:
        raise ValueError(f"instructions.md missing section markers for {name!r}")
    if start not in text:
        raise ValueError(f"instructions.md missing start marker {start}")
    if end not in text:
        raise ValueError(f"instructions.md missing end marker {end}")
    after_start = text.split(start, 1)[1]
    return after_start.split(end, 1)[0].strip()
