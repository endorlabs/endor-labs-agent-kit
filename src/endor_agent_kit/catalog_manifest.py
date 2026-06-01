"""Read-side access to the Catalog Manifest."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from endor_agent_kit.catalog_schema import (
    MANIFEST_PATH,
    CatalogAgent,
    CatalogArtifact,
    CatalogBundle,
    CatalogPluginPackage,
    catalog_agents_from_manifest_payload,
    catalog_plugin_packages_from_manifest_payload,
)


@dataclass(frozen=True)
class CatalogManifest:
    """Loaded Catalog Manifest records."""

    path: Path
    agents: tuple[CatalogAgent, ...]
    bundles: tuple[CatalogBundle, ...]
    plugin_packages: tuple[CatalogPluginPackage, ...] = ()

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

        agents = catalog_agents_from_manifest_payload(data, manifest_path=manifest_path)
        plugin_packages = catalog_plugin_packages_from_manifest_payload(
            data,
            manifest_path=manifest_path,
        )
        bundles = tuple(bundle for agent in agents for bundle in agent.editions)
        return cls(path=path, agents=agents, bundles=bundles, plugin_packages=plugin_packages)

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


def _primary_bundle_priority(bundle: CatalogBundle) -> tuple[int, str]:
    priority = {
        "enterprise-edition": 0,
        "developer-edition": 1,
    }.get(bundle.bundle_id, 2)
    return (priority, bundle.path)
