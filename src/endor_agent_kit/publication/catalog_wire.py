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

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

from endor_agent_kit.catalog_schema import CatalogAgent, CatalogPluginPackage
from endor_agent_kit.publication.claude_plugin import (
    CLAUDE_MARKETPLACE_NAME,
    PUBLIC_CLAUDE_DISTRIBUTION_REPOSITORY,
)
from endor_agent_kit.publication.plugin_package_common import PLUGIN_NAME

CATALOG_PATH = "catalog.json"
CATALOG_SCHEMA_VERSION = "v2"
AUDIENCES = frozenset({"appsec", "developer"})

_ENDORCTL_OPERATOR_RE = re.compile(r"^(?:>=|>)")
_PACKAGE_VERSION_RE = re.compile(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?")
_SETUP_SKILL_PATH = PurePosixPath("skills/endor-agent-kit-setup/SKILL.md")


@dataclass(frozen=True)
class _InstallPackageSpec:
    package_host: str
    wire_host: str
    package_name: str
    distribution_channel: str


# Package authority -> wire host, in catalog install order. Claude Managed,
# Gemini, portable, and Cursor SDK artifacts remain generated but are not public
# install surfaces. Cursor and Antigravity are monolithic packages, so they do
# not need duplicate per-agent compiler records to appear in the catalog.
_WIRE_INSTALL_PACKAGES = (
    _InstallPackageSpec("claude-code", "claude-code", PLUGIN_NAME, "repository"),
    _InstallPackageSpec("codex", "codex", PLUGIN_NAME, "official-directory"),
    _InstallPackageSpec("cursor", "cursor", "endorlabs", "repository"),
    _InstallPackageSpec("antigravity", "antigravity", PLUGIN_NAME, "repository"),
)


def catalog_wire_payload(
    agents: list[CatalogAgent],
    plugin_packages: list[CatalogPluginPackage],
    *,
    catalog_version: str | None = None,
) -> dict[str, Any]:
    """Return the catalog wire payload for finalized manifest records."""

    by_id: dict[str, list[CatalogAgent]] = {}
    for agent in agents:
        by_id.setdefault(agent.id, []).append(agent)

    _validate_legacy_id_claims(by_id)
    install_packages = _eligible_install_packages(by_id, plugin_packages)

    records = []
    for _, group in sorted(by_id.items()):
        record = _endor_agent_record(group, install_packages)
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
    plugin_packages: list[CatalogPluginPackage],
    *,
    catalog_version: str | None = None,
) -> Path:
    """Write ``catalog.json`` into ``destination`` and return its path."""

    path = Path(destination) / CATALOG_PATH
    payload = catalog_wire_payload(
        agents,
        plugin_packages,
        catalog_version=catalog_version,
    )
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def stamp_catalog_version(catalog_path: str | Path, catalog_version: str) -> Path:
    """Inject ``catalog_version`` (the release tag) into an existing catalog.json.

    The committed catalog.json carries no ``catalog_version`` because no tag
    exists at commit time. Provider install commands are production package
    instructions and remain unchanged when the Agent Kit catalog tag is stamped.
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


def _endor_agent_record(
    group: list[CatalogAgent],
    install_packages: dict[str, CatalogPluginPackage],
) -> dict[str, Any] | None:
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
    if not representative.category or representative.category != representative.category.strip():
        raise ValueError(
            f"{representative.id}: category must be a non-empty string without surrounding whitespace"
        )

    install: list[dict[str, str]] = []
    for spec in _WIRE_INSTALL_PACKAGES:
        package = install_packages.get(spec.package_host)
        if package is None or representative.id not in package.included_agents:
            continue
        install.append(
            {
                "host": spec.wire_host,
                "command": _install_command(spec.package_host, package),
            }
        )
    if not install:
        return None

    record = {
        "id": representative.id,
        "name": representative.name,
        "audience": representative.audience,
        "category": representative.category,
        "short_description": representative.short_description,
        "description": representative.description,
        "endorctl_min_version": _strip_operator(representative.requires_endorctl),
        "version": representative.version,
        "authors": list(representative.authors),
        "install": install,
    }
    if representative.legacy_ids:
        record["legacy_ids"] = sorted(representative.legacy_ids)
    return record


def _eligible_install_packages(
    by_id: dict[str, list[CatalogAgent]],
    plugin_packages: list[CatalogPluginPackage],
) -> dict[str, CatalogPluginPackage]:
    """Select complete package records that can install the emitted catalog."""

    published_agent_ids = {
        agent_id
        for agent_id, group in by_id.items()
        if any(agent.editions for agent in group)
    }
    selected: dict[str, CatalogPluginPackage] = {}
    for spec in _WIRE_INSTALL_PACKAGES:
        matches = [
            package
            for package in plugin_packages
            if package.host == spec.package_host
            and package.name == spec.package_name
            and package.distribution_channel == spec.distribution_channel
        ]
        if len(matches) > 1:
            raise ValueError(
                f"manifest.json: multiple {spec.distribution_channel} packages for "
                f"{spec.package_host}/{spec.package_name}"
            )
        if not matches:
            continue
        package = matches[0]
        if not _PACKAGE_VERSION_RE.fullmatch(package.version):
            continue
        if not published_agent_ids.issubset(package.included_agents):
            continue
        if not _package_contains_setup_skill(package):
            continue
        selected[spec.package_host] = package
    return selected


def _package_contains_setup_skill(package: CatalogPluginPackage) -> bool:
    package_root = PurePosixPath(package.path)
    if package.path in ("", "."):
        expected = _SETUP_SKILL_PATH.as_posix()
    else:
        expected = (package_root / _SETUP_SKILL_PATH).as_posix()
    return any(artifact.path == expected for artifact in package.artifacts)


def _validate_legacy_id_claims(by_id: dict[str, list[CatalogAgent]]) -> None:
    """Reject ambiguous aliases before signing the catalog wire artifact."""

    active_ids = set(by_id)
    owners: dict[str, str] = {}
    for agent_id, group in by_id.items():
        declarations = {tuple(sorted(agent.legacy_ids)) for agent in group}
        if len(declarations) > 1:
            raise ValueError(f"{agent_id}: legacy_ids differ across published hosts")
        legacy_ids = next(iter(declarations), ())
        for legacy_id in legacy_ids:
            if legacy_id in active_ids:
                raise ValueError(
                    f"{agent_id}: legacy id {legacy_id!r} is still an active agent id"
                )
            owner = owners.setdefault(legacy_id, agent_id)
            if owner != agent_id:
                raise ValueError(
                    f"legacy id {legacy_id!r} is claimed by multiple agents: "
                    f"{owner!r} and {agent_id!r}"
                )


def _install_command(repo_host: str, package: CatalogPluginPackage) -> str:
    # Each command installs the whole package, so it is identical for every agent
    # on that host.
    if repo_host == "claude-code":
        return (
            f"/plugin marketplace add {PUBLIC_CLAUDE_DISTRIBUTION_REPOSITORY}\n"
            f"/plugin install {PLUGIN_NAME}@{CLAUDE_MARKETPLACE_NAME}\n"
            "/reload-plugins"
        )
    if repo_host == "codex":
        return (
            "Use /plugins to find and install Endor Labs Agent Kit from the "
            "public Codex Plugins Directory."
        )
    if repo_host == "cursor":
        return "/add-plugin endorlabs"
    if repo_host == "antigravity":
        clone_dir = f"endor-ai-plugins-{package.version}"
        plugin_path = f"./{clone_dir}/plugins/antigravity/{PLUGIN_NAME}"
        return (
            f"git clone --branch {package.version} "
            f"https://github.com/{PUBLIC_CLAUDE_DISTRIBUTION_REPOSITORY}.git {clone_dir}\n"
            f"agy plugin validate {plugin_path}\n"
            f"agy plugin install {plugin_path}"
        )
    raise ValueError(f"unsupported install host {repo_host!r}")


def _strip_operator(constraint: str) -> str:
    return _ENDORCTL_OPERATOR_RE.sub("", constraint or "")
