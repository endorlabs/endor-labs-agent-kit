"""Coordinator for host artifact publication."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Protocol

from endor_agent_kit.catalog_schema import (
    GENERATOR_NAME,
    MANIFEST_PATH,
    CatalogAgent,
    CatalogBundle,
    catalog_agent_sort_key,
    catalog_agents_from_manifest_payload,
    catalog_manifest_payload,
)
from endor_agent_kit.prepared_source_recipe import PreparedSourceRecipe

from .records import BundleRecord, PublicationRecord


class HostAdapter(Protocol):
    """Host-specific publication adapter."""

    host: str

    def publish(
        self,
        prepared: PreparedSourceRecipe,
        destination: Path,
    ) -> BundleRecord:
        """Publish one host artifact bundle."""


class HostArtifactPublication:
    """Coordinate publication through host adapters."""

    def __init__(
        self,
        adapters: dict[str, HostAdapter],
        *,
        manifest_path: str = MANIFEST_PATH,
        generator_name: str = GENERATOR_NAME,
    ):
        self._adapters = adapters
        self._manifest_path = manifest_path
        self._generator_name = generator_name

    def publish(
        self,
        host: str,
        prepared: PreparedSourceRecipe,
        destination: Path,
    ) -> PublicationRecord:
        """Publish one host artifact bundle."""

        try:
            adapter = self._adapters[host]
        except KeyError as exc:
            raise ValueError(f"Unsupported publication host {host!r}") from exc
        bundle = adapter.publish(prepared, destination)
        catalog_manifest = self._write_manifest(
            destination,
            prepared,
            host,
            bundle.manifest_records,
        )
        return PublicationRecord(bundle=bundle, catalog_manifest=catalog_manifest)

    def prune_stale_agents(
        self,
        destination: Path,
        active_host_agents: set[tuple[str, str]],
    ) -> Path | None:
        """Remove stale published agents and update the Catalog Manifest."""

        path = self.catalog_manifest_path(destination)
        if not path.exists():
            return None

        agents = self._existing_agents(path)
        kept_agents = [
            agent
            for agent in agents
            if (agent.host, agent.id) in active_host_agents
        ]
        stale_agents = [
            agent
            for agent in agents
            if (agent.host, agent.id) not in active_host_agents
        ]
        if not stale_agents:
            return None

        for agent in stale_agents:
            if agent.host not in self._adapters or not agent.id:
                continue
            shutil.rmtree(destination / agent.host / agent.id, ignore_errors=True)

        kept_agents.sort(key=catalog_agent_sort_key)
        return self._write_agents(destination, kept_agents)

    def catalog_agents(self, destination: Path) -> list[dict[str, Any]]:
        """Return agents currently recorded in the Catalog Manifest."""

        return [
            agent.to_manifest_record()
            for agent in self._existing_agents(self.catalog_manifest_path(destination))
        ]

    def catalog_manifest_path(self, destination: Path) -> Path:
        """Return the Catalog Manifest path for a destination."""

        return destination / self._manifest_path

    def _write_manifest(
        self,
        destination: Path,
        prepared: PreparedSourceRecipe,
        host: str,
        edition_records: tuple[CatalogBundle, ...],
    ) -> Path:
        path = self.catalog_manifest_path(destination)
        recipe = prepared.recipe
        agents = self._existing_agents(path)
        agents = [
            agent
            for agent in agents
            if not (agent.id == recipe.id and agent.host == host)
        ]
        agents.append(CatalogAgent.from_recipe(recipe, host, edition_records))
        agents.sort(key=catalog_agent_sort_key)
        return self._write_agents(destination, agents)

    def _write_agents(self, destination: Path, agents: list[CatalogAgent]) -> Path:
        path = self.catalog_manifest_path(destination)
        payload = catalog_manifest_payload(tuple(agents), generator_name=self._generator_name)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def _existing_agents(self, path: Path) -> list[CatalogAgent]:
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        return list(catalog_agents_from_manifest_payload(data, manifest_path=self._manifest_path))
