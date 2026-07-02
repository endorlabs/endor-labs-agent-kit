"""Catalog wire aggregate -- the signed ``catalog.json`` apiserver consumes.

This is a Catalog Aggregate: it projects Catalog Manifest Schema Records into the
``EndorAgent`` wire shape defined by the monorepo proto
(``spec/internal/endor/v1/agent_catalog.proto``). It consumes typed
``CatalogAgent`` records, never raw recipes, so prune/partial publishes stay
consistent with ``manifest.json``.

The producer emits ``schema_version`` + ``agents`` (and ``catalog_version`` only
when the release pipeline stamps the tag). ``fetched_at`` / ``stale`` are
serve-time fields apiserver owns and are intentionally absent here.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from endor_agent_kit.catalog_schema import CatalogAgent, CatalogBundle

CATALOG_PATH = "catalog.json"
CATALOG_SCHEMA_VERSION = "v1"
AUDIENCES = frozenset({"appsec", "developer"})

# repo host -> wire host name, in catalog install order. Only the two V1 install
# hosts appear in the wire shape; cursor/codex are proto-reserved and gemini/
# portable are not in the proto host enum.
_WIRE_INSTALL_HOSTS: tuple[tuple[str, str], ...] = (
    ("claude-code", "claude-code"),
    ("claude-managed-agents", "claude-managed"),
)
_EDITION_PRIORITY = {"enterprise-edition": 0, "developer-edition": 1}
_ENDORCTL_OPERATOR_RE = re.compile(r"^(?:>=|>)")


def catalog_wire_payload(
    agents: list[CatalogAgent],
    *,
    catalog_version: str | None = None,
) -> dict[str, Any]:
    """Return the ``catalog.json`` payload for the given Catalog Manifest agents."""

    by_id: dict[str, list[CatalogAgent]] = {}
    for agent in agents:
        by_id.setdefault(agent.id, []).append(agent)

    records = []
    for _, group in sorted(by_id.items()):
        record = _endor_agent_record(group)
        if record is not None:
            records.append(record)

    payload: dict[str, Any] = {"schema_version": CATALOG_SCHEMA_VERSION}
    if catalog_version:
        payload["catalog_version"] = catalog_version
    payload["agents"] = records
    return payload


def write_catalog(
    destination: str | Path,
    agents: list[CatalogAgent],
    *,
    catalog_version: str | None = None,
) -> Path:
    """Write ``catalog.json`` into ``destination`` and return its path."""

    path = Path(destination) / CATALOG_PATH
    payload = catalog_wire_payload(agents, catalog_version=catalog_version)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def stamp_catalog_version(catalog_path: str | Path, catalog_version: str) -> Path:
    """Inject ``catalog_version`` (the release tag) into an existing catalog.json.

    The committed catalog.json carries no ``catalog_version`` (no tag exists at
    commit time); the release pipeline stamps it just before signing.
    """

    path = Path(catalog_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    stamped: dict[str, Any] = {
        "schema_version": payload.get("schema_version", CATALOG_SCHEMA_VERSION),
        "catalog_version": catalog_version,
    }
    for key, value in payload.items():
        if key not in ("schema_version", "catalog_version"):
            stamped[key] = value
    path.write_text(json.dumps(stamped, indent=2) + "\n", encoding="utf-8")
    return path


def _endor_agent_record(group: list[CatalogAgent]) -> dict[str, Any] | None:
    by_host = {agent.host: agent for agent in group}
    representative = by_host.get("claude-code") or group[0]

    # A manifest entry with no published editions on any host is a stub (e.g. a
    # hand-written {id, host, editions: []}), not a catalog-installable agent -- skip it.
    if not any(agent.editions for agent in group):
        return None

    # A real, published agent MUST carry a valid audience. Fail loud rather than
    # dropping it silently from the signed catalog (the validator enforces this on
    # recipes, but the emitter is the last line before the served artifact).
    if representative.audience not in AUDIENCES:
        raise ValueError(
            f"{representative.id}: audience must be one of {sorted(AUDIENCES)}, got {representative.audience!r}"
        )

    install: list[dict[str, str]] = []
    for repo_host, wire_host in _WIRE_INSTALL_HOSTS:
        host_agent = by_host.get(repo_host)
        if host_agent is None or not host_agent.editions:
            continue
        bundle = _primary_edition(host_agent)
        install.append(
            {"host": wire_host, "command": _install_command(repo_host, host_agent.id, bundle.path)}
        )
    if not install:
        raise ValueError(
            f"{representative.id}: no V1 install host (claude-code/claude-managed); cannot build install[]"
        )

    return {
        "id": representative.id,
        "name": representative.name,
        "audience": representative.audience,
        "short_description": representative.short_description,
        "description": representative.description,
        "endorctl_min_version": _strip_operator(representative.requires_endorctl),
        "version": representative.version,
        "authors": list(representative.authors),
        "install": install,
    }


def _primary_edition(agent: CatalogAgent) -> CatalogBundle:
    editions = sorted(
        agent.editions,
        key=lambda bundle: (_EDITION_PRIORITY.get(bundle.bundle_id, 2), bundle.path),
    )
    if not editions:
        raise ValueError(f"{agent.id}: host {agent.host} has no published editions")
    return editions[0]


def _install_command(repo_host: str, agent_id: str, bundle_path: str) -> str:
    if repo_host == "claude-code":
        return f"cp {bundle_path}/{agent_id}.md .claude/agents/{agent_id}.md"
    if repo_host == "claude-managed-agents":
        return (
            f"cd {bundle_path} && ant beta:agents create < agent.yaml "
            f"&& ant beta:environments create < environment.yaml"
        )
    raise ValueError(f"unsupported install host {repo_host!r}")


def _strip_operator(constraint: str) -> str:
    return _ENDORCTL_OPERATOR_RE.sub("", constraint or "")
