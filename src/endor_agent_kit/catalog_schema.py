"""Shared Catalog Manifest schema records."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
from typing import Any

from endor_agent_kit.recipe import EndorAgentRecipe

MANIFEST_PATH = "manifest.json"
GENERATOR_NAME = "endor-agent-kit"


@dataclass(frozen=True)
class CatalogArtifact:
    """One artifact file recorded in the Catalog Manifest."""

    path: str
    sha256: str
    bytes: int | None = None
    extra_fields: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_manifest_record(cls, record: Any) -> "CatalogArtifact":
        """Parse one artifact record from Catalog Manifest JSON."""

        if not isinstance(record, dict):
            raise ValueError("manifest.json: expected artifact records to be objects")
        extra_fields = _extra_fields(record, {"path", "sha256", "bytes"})
        return cls(
            path=str(record.get("path") or ""),
            sha256=str(record.get("sha256") or ""),
            bytes=_optional_int(record.get("bytes"), "artifact bytes"),
            extra_fields=extra_fields,
        )

    @classmethod
    def from_published_file(cls, destination: Path, path: Path) -> "CatalogArtifact":
        """Return manifest metadata for one published artifact file."""

        data = path.read_bytes()
        return cls(
            path=path.relative_to(destination).as_posix(),
            sha256=hashlib.sha256(data).hexdigest(),
            bytes=len(data),
        )

    @property
    def name(self) -> str:
        return Path(self.path).name

    def to_manifest_record(self) -> dict[str, Any]:
        """Serialize this artifact to Catalog Manifest JSON shape."""

        record = dict(self.extra_fields)
        record["path"] = self.path
        record["sha256"] = self.sha256
        if self.bytes is not None:
            record["bytes"] = self.bytes
        return record


@dataclass(frozen=True)
class CatalogBundle:
    """One Host Artifact Bundle recorded in the Catalog Manifest."""

    agent_id: str
    agent_name: str
    agent_version: str
    host: str
    bundle_id: str
    bundle_name: str
    path: str
    artifacts: tuple[CatalogArtifact, ...]
    requires_endorctl: str = ""
    include_requires_endorctl: bool = True
    extra_fields: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_manifest_records(
        cls,
        agent: dict[str, Any],
        edition: Any,
    ) -> "CatalogBundle":
        """Parse one edition entry plus its parent agent into a bundle record."""

        if not isinstance(edition, dict):
            raise ValueError("manifest.json: expected edition records to be objects")
        artifacts = edition.get("artifacts", [])
        if not isinstance(artifacts, list):
            raise ValueError("manifest.json: expected edition artifacts to be a list")
        extra_fields = _extra_fields(
            edition,
            {"id", "name", "path", "artifacts", "requires_endorctl"},
        )
        return cls(
            agent_id=str(agent.get("id") or ""),
            agent_name=str(agent.get("name") or ""),
            agent_version=str(agent.get("version") or ""),
            host=str(agent.get("host") or ""),
            bundle_id=str(edition.get("id") or ""),
            bundle_name=str(edition.get("name") or ""),
            path=str(edition.get("path") or ""),
            artifacts=tuple(CatalogArtifact.from_manifest_record(artifact) for artifact in artifacts),
            requires_endorctl=str(edition.get("requires_endorctl") or ""),
            include_requires_endorctl="requires_endorctl" in edition,
            extra_fields=extra_fields,
        )

    @classmethod
    def from_published_bundle(
        cls,
        destination: Path,
        recipe: EndorAgentRecipe,
        host: str,
        bundle_id: str,
        bundle_name: str,
        bundle_dir: Path,
        *,
        requires_endorctl: str = "",
    ) -> "CatalogBundle":
        """Return manifest metadata for one published artifact bundle."""

        files = sorted(path for path in bundle_dir.rglob("*") if path.is_file())
        return cls(
            agent_id=recipe.id,
            agent_name=recipe.name,
            agent_version=recipe.version,
            host=host,
            bundle_id=bundle_id,
            bundle_name=bundle_name,
            path=bundle_dir.relative_to(destination).as_posix(),
            artifacts=tuple(CatalogArtifact.from_published_file(destination, path) for path in files),
            requires_endorctl=requires_endorctl,
            include_requires_endorctl=True,
        )

    def artifact_named(self, name: str) -> CatalogArtifact | None:
        """Return the first artifact in this bundle with the given filename."""

        for artifact in self.artifacts:
            if artifact.name == name:
                return artifact
        return None

    def to_manifest_edition_record(self) -> dict[str, Any]:
        """Serialize this bundle to its edition entry in Catalog Manifest JSON."""

        record = dict(self.extra_fields)
        record["id"] = self.bundle_id
        record["name"] = self.bundle_name
        record["path"] = self.path
        record["artifacts"] = [artifact.to_manifest_record() for artifact in self.artifacts]
        if self.include_requires_endorctl or self.requires_endorctl:
            record["requires_endorctl"] = self.requires_endorctl
        return record


@dataclass(frozen=True)
class CatalogSource:
    """Source Recipe pointer recorded for one Catalog Manifest agent."""

    recipe_schema_version: int | None = None
    builder_recipe: str = ""
    extra_fields: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_recipe(cls, recipe: EndorAgentRecipe) -> "CatalogSource":
        """Return the manifest source pointer for one Source Recipe."""

        return cls(
            recipe_schema_version=recipe.recipe_schema_version,
            builder_recipe=f"source/agents/{recipe.id}/recipe.yaml",
        )

    @classmethod
    def from_manifest_record(cls, record: Any) -> "CatalogSource | None":
        """Parse the optional source record from Catalog Manifest JSON."""

        if record is None:
            return None
        if not isinstance(record, dict):
            raise ValueError("manifest.json: expected source records to be objects")
        extra_fields = _extra_fields(record, {"recipe_schema_version", "builder_recipe"})
        return cls(
            recipe_schema_version=_optional_int(
                record.get("recipe_schema_version"),
                "source recipe_schema_version",
            ),
            builder_recipe=str(record.get("builder_recipe") or ""),
            extra_fields=extra_fields,
        )

    def to_manifest_record(self) -> dict[str, Any]:
        """Serialize this source pointer to Catalog Manifest JSON shape."""

        record = dict(self.extra_fields)
        if self.recipe_schema_version is not None:
            record["recipe_schema_version"] = self.recipe_schema_version
        if self.builder_recipe:
            record["builder_recipe"] = self.builder_recipe
        return record


@dataclass(frozen=True)
class CatalogAgent:
    """One agent/host entry in the Catalog Manifest."""

    id: str
    host: str
    editions: tuple[CatalogBundle, ...]
    name: str = ""
    version: str = ""
    source: CatalogSource | None = None
    extra_fields: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_recipe(
        cls,
        recipe: EndorAgentRecipe,
        host: str,
        bundles: tuple[CatalogBundle, ...],
    ) -> "CatalogAgent":
        """Create one agent/host manifest entry from published bundle records."""

        return cls(
            id=recipe.id,
            name=recipe.name,
            version=recipe.version,
            host=host,
            source=CatalogSource.from_recipe(recipe),
            editions=bundles,
        )

    @classmethod
    def from_manifest_record(cls, record: Any) -> "CatalogAgent":
        """Parse one agent entry from Catalog Manifest JSON."""

        if not isinstance(record, dict):
            raise ValueError("manifest.json: expected agents to be a list of objects")
        editions = record.get("editions", [])
        if not isinstance(editions, list):
            raise ValueError("manifest.json: expected agent editions to be a list")
        extra_fields = _extra_fields(
            record,
            {"id", "name", "version", "host", "source", "editions"},
        )
        return cls(
            id=str(record.get("id") or ""),
            name=str(record.get("name") or ""),
            version=str(record.get("version") or ""),
            host=str(record.get("host") or ""),
            source=CatalogSource.from_manifest_record(record.get("source")),
            editions=tuple(CatalogBundle.from_manifest_records(record, edition) for edition in editions),
            extra_fields=extra_fields,
        )

    def to_manifest_record(self) -> dict[str, Any]:
        """Serialize this agent to Catalog Manifest JSON shape."""

        record = dict(self.extra_fields)
        record["id"] = self.id
        if self.name:
            record["name"] = self.name
        if self.version:
            record["version"] = self.version
        record["host"] = self.host
        if self.source is not None:
            record["source"] = self.source.to_manifest_record()
        record["editions"] = [bundle.to_manifest_edition_record() for bundle in self.editions]
        return record


def catalog_agents_from_manifest_payload(
    data: Any,
    *,
    manifest_path: str = MANIFEST_PATH,
) -> tuple[CatalogAgent, ...]:
    """Parse Catalog Manifest agent records from loaded JSON."""

    if not isinstance(data, dict):
        raise ValueError(f"{manifest_path}: expected a JSON object")
    agents = data.get("agents", [])
    if not isinstance(agents, list) or not all(isinstance(agent, dict) for agent in agents):
        raise ValueError(f"{manifest_path}: expected agents to be a list of objects")
    return tuple(CatalogAgent.from_manifest_record(agent) for agent in agents)


def catalog_manifest_payload(
    agents: tuple[CatalogAgent, ...],
    *,
    generator_name: str = GENERATOR_NAME,
) -> dict[str, Any]:
    """Return the JSON payload for a Catalog Manifest."""

    return {
        "schema_version": 1,
        "generated_by": generator_name,
        "agents": [agent.to_manifest_record() for agent in agents],
    }


def catalog_agent_sort_key(agent: CatalogAgent) -> tuple[str, str]:
    """Return the stable Catalog Manifest sort key for one agent."""

    return (agent.host, agent.id)


def _extra_fields(record: dict[str, Any], known: set[str]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in known}


def _optional_int(value: Any, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    raise ValueError(f"manifest.json: expected {field_name} to be an integer")
