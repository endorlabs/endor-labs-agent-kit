#!/usr/bin/env python3
"""Generate and verify the Endor API registry from the upstream OpenAPI spec.

``src/endor_agent_kit/endor_api_registry.py`` hand-lists the Endor resource kinds
and filter-enum members the catalog is allowed to reference. Those values are an
external contract — they must mirror the Endor OpenAPI, not "what the repo
happens to use today". This script makes the registry a *verified projection* of
the spec instead of a hand-maintained guess:

  * ``--check``  : fetch (or read) the spec and report drift between it and the
                   committed registry. Exit non-zero on drift. Use this after
                   ``endor-agent-kit refresh-endor-context`` and in CI.
  * ``--emit``   : print paste-ready Python literals for ENDOR_ENUM_VALUES so a
                   maintainer never hand-types enum members again.

The core extractors are pure functions over a parsed spec dict, so they are unit
tested offline; only ``main`` touches the network.

Examples:
    python scripts/generate_endor_api_registry.py --check
    python scripts/generate_endor_api_registry.py --check --spec /tmp/openapi.json
    python scripts/generate_endor_api_registry.py --emit --spec /tmp/openapi.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any

# Keep the kit importable when run as a script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from endor_agent_kit.endor_api_registry import (  # noqa: E402
    ENDOR_API_RESOURCES,
    ENDOR_ENUM_VALUES,
)

try:  # Reuse the same URL the provenance gate pins, if available.
    from endor_agent_kit.endor_context import DEFAULT_OPENAPI_URL  # noqa: E402
except Exception:  # pragma: no cover - defensive fallback
    DEFAULT_OPENAPI_URL = "https://api.endorlabs.com/download/openapiv2.swagger.json"

# Resource kinds the API serves through a differently-named definition / service
# rather than a ``v1<Kind>`` message, or that are legacy. Documented here so they
# are exceptions on purpose, not silent gaps.
LEGACY_RESOURCES = frozenset({"UpgradeImpactAnalysis"})


# --------------------------------------------------------------------------- #
# Pure extractors (unit tested offline against an inline fake spec)
# --------------------------------------------------------------------------- #
def all_enum_members(spec: dict[str, Any]) -> set[str]:
    """Return every string member of every ``enum`` array anywhere in the spec."""

    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            enum = node.get("enum")
            if isinstance(enum, list):
                found.update(v for v in enum if isinstance(v, str))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(spec)
    return found


def enum_members_for_family(spec: dict[str, Any], family: str) -> set[str]:
    """Return spec enum members belonging to one family prefix (e.g. FINDING_CATEGORY)."""

    prefix = family + "_"
    return {m for m in all_enum_members(spec) if m.startswith(prefix)}


def namespaced_collections(spec: dict[str, Any]) -> set[str]:
    """Return the namespaced REST collection segments (e.g. ``findings``)."""

    collections: set[str] = set()
    for path in spec.get("paths", {}):
        match = re.search(r"/namespaces/\{[^}]+\}/([a-z0-9-]+)", path)
        if match:
            collections.add(match.group(1))
    return collections


def v1_kinds(spec: dict[str, Any]) -> set[str]:
    """Return PascalCase kinds backed by a ``v1<Kind>`` definition."""

    defs = spec.get("definitions", {})
    return {k[2:] for k in defs if re.fullmatch(r"v1[A-Z][A-Za-z0-9]+", k)}


def _expected_collection(kind: str) -> str:
    """Best-effort PascalCase -> plural kebab collection name (e.g. Vulnerability -> vulnerabilities)."""

    kebab = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", kind).lower()
    if kebab.endswith("y"):
        return kebab[:-1] + "ies"
    if kebab.endswith("s"):
        return kebab + "es"
    return kebab + "s"


def resource_has_evidence(kind: str, spec: dict[str, Any]) -> bool:
    """True if ``kind`` is a real Endor resource per the spec (def or collection) or a known legacy kind."""

    if kind in LEGACY_RESOURCES:
        return True
    if kind in v1_kinds(spec):
        return True
    return _expected_collection(kind) in namespaced_collections(spec)


def enum_family_drift(
    family: str,
    registry_members: set[str],
    spec_members: set[str],
) -> tuple[set[str], set[str]]:
    """Return (in_spec_not_in_registry, in_registry_not_in_spec) for one family."""

    return (spec_members - registry_members, registry_members - spec_members)


# --------------------------------------------------------------------------- #
# Composition against the committed registry
# --------------------------------------------------------------------------- #
def registry_drift(spec: dict[str, Any]) -> list[str]:
    """Compare the committed registry to the spec; return human-readable drift lines."""

    drift: list[str] = []

    for family in sorted(ENDOR_ENUM_VALUES):
        spec_members = enum_members_for_family(spec, family)
        if not spec_members:
            drift.append(
                f"enum family {family}_*: NONE found in spec "
                "(family renamed/removed upstream? re-check the OpenAPI)"
            )
            continue
        missing, extra = enum_family_drift(family, set(ENDOR_ENUM_VALUES[family]), spec_members)
        for value in sorted(missing):
            drift.append(f"enum {value}: present in spec, MISSING from registry {family}")
        for value in sorted(extra):
            drift.append(f"enum {value}: in registry {family}, NOT in current spec")

    for kind in sorted(ENDOR_API_RESOURCES):
        if not resource_has_evidence(kind, spec):
            drift.append(
                f"resource {kind!r}: no v1<Kind> definition or matching collection in spec "
                "(typo / removed kind?)"
            )
    return drift


def emit_enum_block(spec: dict[str, Any]) -> str:
    """Render paste-ready ENDOR_ENUM_VALUES literals for the registry's tracked families."""

    lines = ["ENDOR_ENUM_VALUES: dict[str, frozenset[str]] = {"]
    for family in sorted(ENDOR_ENUM_VALUES):
        members = sorted(enum_members_for_family(spec, family))
        lines.append(f'    "{family}": frozenset(')
        lines.append("        {")
        lines.extend(f'            "{m}",' for m in members)
        lines.append("        }")
        lines.append("    ),")
    lines.append("}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _load_spec(spec_path: str | None, url: str) -> dict[str, Any]:
    if spec_path:
        return json.loads(Path(spec_path).read_text(encoding="utf-8"))
    with urllib.request.urlopen(url) as response:  # noqa: S310 - documented public URL
        return json.loads(response.read().decode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", help="Path to a local OpenAPI JSON (default: fetch --url)")
    parser.add_argument("--url", default=DEFAULT_OPENAPI_URL, help="OpenAPI download URL")
    parser.add_argument("--check", action="store_true", help="Report registry/spec drift; non-zero on drift")
    parser.add_argument("--emit", action="store_true", help="Print paste-ready ENDOR_ENUM_VALUES literals")
    args = parser.parse_args(argv)

    if not args.check and not args.emit:
        parser.error("choose --check and/or --emit")

    try:
        spec = _load_spec(args.spec, args.url)
    except Exception as exc:  # pragma: no cover - network/IO failure path
        print(f"ERROR: could not load OpenAPI spec: {exc}", file=sys.stderr)
        return 2

    status = 0
    if args.check:
        drift = registry_drift(spec)
        if drift:
            print("Endor API registry drift detected:")
            for line in drift:
                print(f"  - {line}")
            print(
                "\nReconcile src/endor_agent_kit/endor_api_registry.py "
                "(use --emit for enum literals) after verifying against the pinned OpenAPI."
            )
            status = 1
        else:
            print("OK: endor_api_registry matches the OpenAPI spec (enums + resources).")
    if args.emit:
        print(emit_enum_block(spec))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
