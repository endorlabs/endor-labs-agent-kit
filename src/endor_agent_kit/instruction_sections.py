"""Shared parsing for Source Recipe instruction sections."""

from __future__ import annotations

from dataclasses import dataclass
import re


EDITIONS = ("developer-edition", "enterprise-edition")
LEGACY_EDITION_ALIASES = {
    "standard": "developer-edition",
    "extended": "enterprise-edition",
}
LEGACY_SECTION_NAMES = {
    "developer-edition": "standard",
    "enterprise-edition": "extended",
}
_REGION_MARKER_RE = re.compile(
    r"<!--\s*(?P<kind>section|profile):(?P<id>[a-z0-9][a-z0-9-]*):(?P<edge>start|end)\s*-->"
)
_REGION_MARKER_CANDIDATE_RE = re.compile(r"<!--\s*(?:section|profile)\b.*?-->")


@dataclass(frozen=True)
class InstructionRegion:
    """One ordered addressable or unmarked instruction region."""

    kind: str
    id: str | None
    body: str
    source_position: int
    top_level_body: str


@dataclass(frozen=True)
class InstructionSections:
    """Structured instruction sections used by host compiler renderers."""

    shared: str
    developer_edition: str
    enterprise_edition: str
    shared_regions: tuple[InstructionRegion, ...]
    developer_edition_regions: tuple[InstructionRegion, ...]
    enterprise_edition_regions: tuple[InstructionRegion, ...]

    def for_edition(self, edition: str) -> str:
        """Return the section body for a canonical edition name."""

        if edition == "developer-edition":
            return self.developer_edition
        if edition == "enterprise-edition":
            return self.enterprise_edition
        raise ValueError(f"Unknown Claude Code edition {edition!r}; allowed: {', '.join(EDITIONS)}")

    def regions_for_edition(self, edition: str) -> tuple[InstructionRegion, ...]:
        if edition == "developer-edition":
            return self.developer_edition_regions
        if edition == "enterprise-edition":
            return self.enterprise_edition_regions
        raise ValueError(f"Unknown Claude Code edition {edition!r}; allowed: {', '.join(EDITIONS)}")

    @property
    def sections(self) -> dict[str, InstructionRegion]:
        return {
            region.id: region
            for region in self._all_regions()
            if region.kind == "section" and region.id is not None
        }

    @property
    def profiles(self) -> dict[str, InstructionRegion]:
        return {
            region.id: region
            for region in self._all_regions()
            if region.kind == "profile" and region.id is not None
        }

    def scoped_shared(self, *, profile_id: str, included_sections: tuple[str, ...]) -> str:
        return _render_regions(
            _selected_regions(self.shared_regions, profile_id=profile_id, included_sections=included_sections)
        )

    def scoped_for_edition(self, edition: str, *, profile_id: str, included_sections: tuple[str, ...]) -> str:
        return _render_regions(
            _selected_regions(
                self.regions_for_edition(edition),
                profile_id=profile_id,
                included_sections=included_sections,
            )
        )

    def _all_regions(self) -> tuple[InstructionRegion, ...]:
        return self.shared_regions + self.developer_edition_regions + self.enterprise_edition_regions


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
    """Parse top-level edition bodies and their ordered addressable regions."""

    raw_bodies = {
        "shared": _section_from_any(instructions, ("shared",)),
        "developer-edition": _section_from_any(
            instructions,
            _section_names("developer-edition", allow_legacy=allow_legacy),
        ),
        "enterprise-edition": _section_from_any(
            instructions,
            _section_names("enterprise-edition", allow_legacy=allow_legacy),
        ),
    }
    candidate_count = len(_REGION_MARKER_CANDIDATE_RE.findall(instructions))
    contained_candidate_count = sum(
        len(_REGION_MARKER_CANDIDATE_RE.findall(body)) for body in raw_bodies.values()
    )
    if candidate_count != contained_candidate_count:
        raise ValueError("instructions.md section/profile markers must be inside a top-level instruction body")
    seen: set[tuple[str, str]] = set()
    region_bodies = {
        name: _scan_regions(body, top_level_body=name, seen=seen)
        for name, body in raw_bodies.items()
    }
    return InstructionSections(
        shared=_render_regions(region_bodies["shared"]),
        developer_edition=_render_regions(region_bodies["developer-edition"]),
        enterprise_edition=_render_regions(region_bodies["enterprise-edition"]),
        shared_regions=region_bodies["shared"],
        developer_edition_regions=region_bodies["developer-edition"],
        enterprise_edition_regions=region_bodies["enterprise-edition"],
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
    start_count = text.count(start)
    end_count = text.count(end)
    if start_count == 0 and end_count == 0:
        raise ValueError(f"instructions.md missing section markers for {name!r}")
    if start_count == 0:
        raise ValueError(f"instructions.md missing start marker {start}")
    if end_count == 0:
        raise ValueError(f"instructions.md missing end marker {end}")
    if start_count != 1 or end_count != 1:
        raise ValueError(f"instructions.md has duplicate section markers for {name!r}")
    start_position = text.index(start) + len(start)
    end_position = text.index(end, start_position)
    return text[start_position:end_position].strip()


def _scan_regions(
    body: str,
    *,
    top_level_body: str,
    seen: set[tuple[str, str]],
) -> tuple[InstructionRegion, ...]:
    candidates = list(_REGION_MARKER_CANDIDATE_RE.finditer(body))
    matches = list(_REGION_MARKER_RE.finditer(body))
    if [candidate.span() for candidate in candidates] != [match.span() for match in matches]:
        raise ValueError(f"instructions.md has malformed section/profile marker in {top_level_body}")
    regions: list[InstructionRegion] = []
    cursor = 0
    active: tuple[str, str, int, int] | None = None
    for match in matches:
        kind = match.group("kind")
        region_id = match.group("id")
        edge = match.group("edge")
        if edge == "start":
            if active is not None:
                raise ValueError("instructions.md section/profile markers cannot overlap or nest")
            if match.start() > cursor:
                regions.append(
                    InstructionRegion("unmarked", None, body[cursor:match.start()], cursor, top_level_body)
                )
            identity = (kind, region_id)
            if identity in seen:
                raise ValueError(f"instructions.md has duplicate {kind} marker id {region_id!r}")
            seen.add(identity)
            active = (kind, region_id, match.end(), match.start())
            cursor = match.end()
            continue
        if active is None:
            raise ValueError(f"instructions.md has orphaned {kind}:{region_id}:end marker")
        active_kind, active_id, content_start, source_position = active
        if (kind, region_id) != (active_kind, active_id):
            raise ValueError(
                f"instructions.md closes {kind}:{region_id} while {active_kind}:{active_id} is open"
            )
        regions.append(
            InstructionRegion(kind, region_id, body[content_start:match.start()], source_position, top_level_body)
        )
        active = None
        cursor = match.end()
    if active is not None:
        raise ValueError(f"instructions.md missing end marker for {active[0]}:{active[1]}")
    if cursor < len(body):
        regions.append(InstructionRegion("unmarked", None, body[cursor:], cursor, top_level_body))
    if not regions:
        regions.append(InstructionRegion("unmarked", None, body, 0, top_level_body))
    return tuple(region for region in regions if region.body)


def _selected_regions(
    regions: tuple[InstructionRegion, ...],
    *,
    profile_id: str,
    included_sections: tuple[str, ...],
) -> tuple[InstructionRegion, ...]:
    allowed_sections = set(included_sections)
    return tuple(
        region
        for region in regions
        if region.kind == "unmarked"
        or (region.kind == "profile" and region.id == profile_id)
        or (region.kind == "section" and region.id in allowed_sections)
    )


def _render_regions(regions: tuple[InstructionRegion, ...]) -> str:
    return "".join(region.body for region in regions).strip()
