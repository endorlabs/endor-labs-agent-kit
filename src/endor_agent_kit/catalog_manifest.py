"""Read-side access to the Catalog Manifest."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

MANIFEST_PATH = "manifest.json"


@dataclass(frozen=True)
class CatalogArtifact:
    """One artifact file recorded in the Catalog Manifest."""

    path: str
    sha256: str
    bytes: int | None = None

    @property
    def name(self) -> str:
        return Path(self.path).name


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

    def artifact_named(self, name: str) -> CatalogArtifact | None:
        """Return the first artifact in this bundle with the given filename."""

        for artifact in self.artifacts:
            if artifact.name == name:
                return artifact
        return None


@dataclass(frozen=True)
class CatalogManifest:
    """Loaded Catalog Manifest records."""

    path: Path
    bundles: tuple[CatalogBundle, ...]

    @classmethod
    def load(
        cls,
        catalog_root: str | Path,
        *,
        manifest_path: str = MANIFEST_PATH,
    ) -> "CatalogManifest":
        """Load the Catalog Manifest from a catalog root."""

        path = Path(catalog_root) / manifest_path
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{manifest_path}: expected a JSON object")

        agents = data.get("agents", [])
        if not isinstance(agents, list) or not all(isinstance(agent, dict) for agent in agents):
            raise ValueError(f"{manifest_path}: expected agents to be a list of objects")

        bundles: list[CatalogBundle] = []
        for agent in agents:
            bundles.extend(_bundles_for_agent(agent))
        return cls(path=path, bundles=tuple(bundles))

    def find_bundles(self, agent_id: str, host: str) -> tuple[CatalogBundle, ...]:
        """Return the Host Artifact Bundles for one agent and Host."""

        return tuple(
            bundle
            for bundle in self.bundles
            if bundle.agent_id == agent_id and bundle.host == host
        )

    def primary_artifact(
        self,
        agent_id: str,
        host: str,
        artifact_name: str,
    ) -> CatalogArtifact | None:
        """Return the preferred primary artifact for one agent and Host."""

        bundles = sorted(
            self.find_bundles(agent_id, host),
            key=_primary_bundle_priority,
        )
        for bundle in bundles:
            artifact = bundle.artifact_named(artifact_name)
            if artifact is not None:
                return artifact
        return None


def _bundles_for_agent(agent: dict[str, Any]) -> list[CatalogBundle]:
    editions = agent.get("editions", [])
    if not isinstance(editions, list):
        raise ValueError("manifest.json: expected agent editions to be a list")

    bundles: list[CatalogBundle] = []
    for edition in editions:
        if not isinstance(edition, dict):
            raise ValueError("manifest.json: expected edition records to be objects")
        artifacts = edition.get("artifacts", [])
        if not isinstance(artifacts, list):
            raise ValueError("manifest.json: expected edition artifacts to be a list")
        bundles.append(
            CatalogBundle(
                agent_id=str(agent.get("id") or ""),
                agent_name=str(agent.get("name") or ""),
                agent_version=str(agent.get("version") or ""),
                host=str(agent.get("host") or ""),
                bundle_id=str(edition.get("id") or ""),
                bundle_name=str(edition.get("name") or ""),
                path=str(edition.get("path") or ""),
                artifacts=tuple(_artifact_record(artifact) for artifact in artifacts),
                requires_endorctl=str(edition.get("requires_endorctl") or ""),
            )
        )
    return bundles


def _artifact_record(record: Any) -> CatalogArtifact:
    if not isinstance(record, dict):
        raise ValueError("manifest.json: expected artifact records to be objects")
    return CatalogArtifact(
        path=str(record.get("path") or ""),
        sha256=str(record.get("sha256") or ""),
        bytes=_optional_int(record.get("bytes")),
    )


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    raise ValueError("manifest.json: expected artifact bytes to be an integer")


def _primary_bundle_priority(bundle: CatalogBundle) -> tuple[int, str]:
    priority = {
        "enterprise-edition": 0,
        "developer-edition": 1,
    }.get(bundle.bundle_id, 2)
    return (priority, bundle.path)
