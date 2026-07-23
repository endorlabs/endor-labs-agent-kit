"""Coordinator for host artifact publication."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Protocol

from endor_agent_kit.catalog_schema import (
    GENERATOR_NAME,
    MANIFEST_PATH,
    CatalogAgent,
    CatalogPluginPackage,
    catalog_agent_sort_key,
    catalog_agents_from_manifest_payload,
    catalog_manifest_payload,
    catalog_plugin_package_sort_key,
    catalog_plugin_packages_from_manifest_payload,
)
from endor_agent_kit.compilers.raw import compile_raw_prepared
from endor_agent_kit.prepared_source_recipe import PreparedSourceRecipe

from .records import (
    BundleRecord,
    PublicationBatchRecord,
    PublicationRecord,
    with_evidence_plan_artifacts,
)


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

        if host not in self._adapters:
            raise ValueError(f"Unsupported publication host {host!r}")
        compile_raw_prepared(prepared)
        bundle = self._publish_bundle(host, prepared, destination)
        agent = CatalogAgent.from_recipe(
            prepared.recipe,
            host,
            bundle.manifest_records,
        )
        catalog_manifest = self.finalize_manifest(
            destination,
            generated_agents=(agent,),
        )
        if catalog_manifest is None:  # pragma: no cover - generated_agents always writes
            raise AssertionError("publishing a host bundle must finalize the Catalog Manifest")
        return PublicationRecord(bundle=bundle, catalog_manifest=catalog_manifest)

    def publish_bundles(
        self,
        prepared_recipes: tuple[PreparedSourceRecipe, ...],
        destination: Path,
    ) -> PublicationBatchRecord:
        """Publish prepared recipes without incrementally writing catalog aggregates."""

        bundles: list[BundleRecord] = []
        agents: list[CatalogAgent] = []
        destination.mkdir(parents=True, exist_ok=True)
        for prepared in prepared_recipes:
            hosts = tuple(
                host
                for host in self._adapters
                if host in prepared.recipe.compatible_hosts
            )
            if not hosts:
                continue
            compile_raw_prepared(prepared)
            for host in hosts:
                bundle = self._publish_bundle(host, prepared, destination)
                bundles.append(bundle)
                agents.append(
                    CatalogAgent.from_recipe(
                        prepared.recipe,
                        host,
                        bundle.manifest_records,
                    )
                )
        return PublicationBatchRecord(
            bundles=tuple(bundles),
            agents=tuple(agents),
        )

    def finalize_manifest(
        self,
        destination: Path,
        *,
        generated_agents: tuple[CatalogAgent, ...] = (),
        plugin_packages: tuple[CatalogPluginPackage, ...] = (),
        replace_plugin_groups: set[tuple[str, str]] | None = None,
        prune_active_host_agents: set[tuple[str, str]] | None = None,
    ) -> Path | None:
        """Finalize generated agents, pruning, and plugin packages in one manifest write."""

        path = self.catalog_manifest_path(destination)
        existing_agents, existing_packages = self._existing_catalog(path)
        agents_by_key = {
            (agent.host, agent.id): agent
            for agent in existing_agents
        }
        for agent in generated_agents:
            agents_by_key[(agent.host, agent.id)] = agent

        stale_agents: list[CatalogAgent] = []
        if prune_active_host_agents is not None:
            stale_agents = [
                agent
                for key, agent in agents_by_key.items()
                if key not in prune_active_host_agents
            ]
            for agent in stale_agents:
                agents_by_key.pop((agent.host, agent.id), None)
                if agent.host in self._adapters and agent.id:
                    shutil.rmtree(
                        destination / agent.host / agent.id,
                        ignore_errors=True,
                    )

        replace_groups = replace_plugin_groups or set()
        merged_packages = [
            package
            for package in existing_packages
            if (package.host, package.distribution_channel) not in replace_groups
        ]
        merged_packages.extend(plugin_packages)

        changed = bool(
            generated_agents
            or plugin_packages
            or stale_agents
            or any(
                (package.host, package.distribution_channel) in replace_groups
                for package in existing_packages
            )
        )
        if not changed:
            return None

        agents = sorted(agents_by_key.values(), key=catalog_agent_sort_key)
        merged_packages.sort(key=catalog_plugin_package_sort_key)
        return self._write_manifest_payload(destination, agents, merged_packages)

    def _publish_bundle(
        self,
        host: str,
        prepared: PreparedSourceRecipe,
        destination: Path,
    ) -> BundleRecord:
        adapter = self._adapters[host]
        return with_evidence_plan_artifacts(
            adapter.publish(prepared, destination),
            destination,
            prepared,
        )

    def prune_stale_agents(
        self,
        destination: Path,
        active_host_agents: set[tuple[str, str]],
    ) -> Path | None:
        """Remove stale published agents and update the Catalog Manifest."""

        return self.finalize_manifest(
            destination,
            prune_active_host_agents=active_host_agents,
        )

    def catalog_agents(self, destination: Path) -> list[CatalogAgent]:
        """Return agents currently recorded in the Catalog Manifest."""

        return self._existing_agents(self.catalog_manifest_path(destination))

    def catalog_plugin_packages(self, destination: Path) -> list[CatalogPluginPackage]:
        """Return plugin packages currently recorded in the Catalog Manifest."""

        return self._existing_plugin_packages(self.catalog_manifest_path(destination))

    def write_plugin_packages(
        self,
        destination: Path,
        packages: tuple[CatalogPluginPackage, ...],
        *,
        replace_groups: set[tuple[str, str]],
    ) -> Path:
        """Write plugin package records while preserving unrelated host channels."""

        path = self.finalize_manifest(
            destination,
            plugin_packages=packages,
            replace_plugin_groups=replace_groups,
        )
        if path is None:  # pragma: no cover - packages always writes
            raise AssertionError("writing plugin packages must finalize the Catalog Manifest")
        return path

    def catalog_manifest_path(self, destination: Path) -> Path:
        """Return the Catalog Manifest path for a destination."""

        return destination / self._manifest_path

    def _write_manifest_payload(
        self,
        destination: Path,
        agents: list[CatalogAgent],
        plugin_packages: list[CatalogPluginPackage],
    ) -> Path:
        path = self.catalog_manifest_path(destination)
        payload = catalog_manifest_payload(
            tuple(agents),
            plugin_packages=tuple(plugin_packages),
            generator_name=self._generator_name,
        )
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def _existing_agents(self, path: Path) -> list[CatalogAgent]:
        agents, _ = self._existing_catalog(path)
        return agents

    def _existing_plugin_packages(self, path: Path) -> list[CatalogPluginPackage]:
        _, packages = self._existing_catalog(path)
        return packages

    def _existing_catalog(
        self,
        path: Path,
    ) -> tuple[list[CatalogAgent], list[CatalogPluginPackage]]:
        if not path.exists():
            return [], []
        data = json.loads(path.read_text(encoding="utf-8"))
        return (
            list(catalog_agents_from_manifest_payload(data, manifest_path=self._manifest_path)),
            list(
                catalog_plugin_packages_from_manifest_payload(
                    data,
                    manifest_path=self._manifest_path,
                )
            ),
        )
