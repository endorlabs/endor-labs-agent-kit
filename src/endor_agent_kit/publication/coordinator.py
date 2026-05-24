"""Coordinator for host artifact publication."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Protocol

from endor_agent_kit.recipe import EndorAgentRecipe

from .records import BundleRecord, PublicationRecord

MANIFEST_PATH = "manifest.json"
GENERATOR_NAME = "endor-agent-kit"


class HostAdapter(Protocol):
    """Host-specific publication adapter."""

    host: str

    def publish(
        self,
        recipe_file: Path,
        recipe: EndorAgentRecipe,
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
        recipe_file: Path,
        recipe: EndorAgentRecipe,
        destination: Path,
    ) -> PublicationRecord:
        """Publish one host artifact bundle."""

        try:
            adapter = self._adapters[host]
        except KeyError as exc:
            raise ValueError(f"Unsupported publication host {host!r}") from exc
        bundle = adapter.publish(recipe_file, recipe, destination)
        catalog_manifest = self._write_manifest(
            destination,
            recipe,
            host,
            list(bundle.manifest_records),
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

        agents = self.catalog_agents(destination)
        kept_agents = [
            agent
            for agent in agents
            if (str(agent.get("host", "")), str(agent.get("id", ""))) in active_host_agents
        ]
        stale_agents = [
            agent
            for agent in agents
            if (str(agent.get("host", "")), str(agent.get("id", ""))) not in active_host_agents
        ]
        if not stale_agents:
            return None

        for agent in stale_agents:
            host = str(agent.get("host", ""))
            agent_id = str(agent.get("id", ""))
            if host not in self._adapters or not agent_id:
                continue
            shutil.rmtree(destination / host / agent_id, ignore_errors=True)

        kept_agents.sort(key=lambda agent: (str(agent.get("host", "")), str(agent.get("id", ""))))
        return self._write_agents(destination, kept_agents)

    def catalog_agents(self, destination: Path) -> list[dict[str, Any]]:
        """Return agents currently recorded in the Catalog Manifest."""

        return self._existing_agents(self.catalog_manifest_path(destination))

    def catalog_manifest_path(self, destination: Path) -> Path:
        """Return the Catalog Manifest path for a destination."""

        return destination / self._manifest_path

    def _write_manifest(
        self,
        destination: Path,
        recipe: EndorAgentRecipe,
        host: str,
        edition_records: list[dict[str, Any]],
    ) -> Path:
        path = self.catalog_manifest_path(destination)
        agents = self._existing_agents(path)
        agents = [
            agent
            for agent in agents
            if not (agent.get("id") == recipe.id and agent.get("host") == host)
        ]
        agents.append({
            "id": recipe.id,
            "name": recipe.name,
            "version": recipe.version,
            "host": host,
            "source": {
                "recipe_schema_version": recipe.recipe_schema_version,
                "builder_recipe": f"source/agents/{recipe.id}/recipe.yaml",
            },
            "editions": edition_records,
        })
        agents.sort(key=lambda agent: (str(agent.get("host", "")), str(agent.get("id", ""))))
        return self._write_agents(destination, agents)

    def _write_agents(self, destination: Path, agents: list[dict[str, Any]]) -> Path:
        path = self.catalog_manifest_path(destination)
        payload = {
            "schema_version": 1,
            "generated_by": self._generator_name,
            "agents": agents,
        }
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def _existing_agents(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"{self._manifest_path}: expected a JSON object")
        agents = data.get("agents", [])
        if not isinstance(agents, list) or not all(isinstance(agent, dict) for agent in agents):
            raise ValueError(f"{self._manifest_path}: expected agents to be a list of objects")
        return agents
