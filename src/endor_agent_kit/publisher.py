"""Publish compiled agent artifacts into a customer-facing catalog."""

from __future__ import annotations

from pathlib import Path

from endor_agent_kit.compilers.claude_code import HOST as CLAUDE_CODE_HOST
from endor_agent_kit.compilers.claude_managed_agents import HOST as CLAUDE_MANAGED_AGENTS_HOST
from endor_agent_kit.compilers.codex import HOST as CODEX_HOST
from endor_agent_kit.compilers.gemini import HOST as GEMINI_HOST
from endor_agent_kit.compilers.portable import HOST as PORTABLE_HOST
from endor_agent_kit.publication import (
    ClaudeCodeHostAdapter,
    ClaudeManagedAgentsHostAdapter,
    CodexHostAdapter,
    GeminiHostAdapter,
    HostArtifactPublication,
    PortableHostAdapter,
    RootCatalogAggregate,
)
from endor_agent_kit.publication.antigravity_plugin import publish_antigravity_plugin_package
from endor_agent_kit.publication.claude_plugin import publish_claude_plugin_package
from endor_agent_kit.publication.codex_plugin import publish_codex_plugin_package
from endor_agent_kit.publication.codex_directory_plugin import (
    publish_codex_directory_plugin_package,
)
from endor_agent_kit.publication.cursor_plugin import publish_cursor_plugin_package
from endor_agent_kit.publication.cursor_sdk import publish_cursor_sdk_package
from endor_agent_kit.publication.gemini_plugin import publish_gemini_plugin_package
from endor_agent_kit.publication.catalog_wire import write_catalog
from endor_agent_kit.publication.mcp_support import publish_root_mcp_support
from endor_agent_kit.publication.model_recommendations import (
    write_model_recommendation_artifacts,
)
from endor_agent_kit.catalog_manifest import CatalogManifest
from endor_agent_kit.prepared_source_recipe import prepare_source_recipe

_HOST_ARTIFACT_PUBLICATION = HostArtifactPublication({
    CLAUDE_CODE_HOST: ClaudeCodeHostAdapter(),
    CLAUDE_MANAGED_AGENTS_HOST: ClaudeManagedAgentsHostAdapter(),
    CODEX_HOST: CodexHostAdapter(),
    GEMINI_HOST: GeminiHostAdapter(),
    PORTABLE_HOST: PortableHostAdapter(),
})
_ROOT_CATALOG_AGGREGATE = RootCatalogAggregate()


def publish_recipe(
    recipe_path: str | Path,
    dest: str | Path,
    *,
    include_plugins: bool = False,
) -> list[Path]:
    """Publish one recipe's customer-facing artifacts into ``dest``."""

    return publish_recipes([recipe_path], dest, include_plugins=include_plugins)


def publish_recipes(
    recipe_paths: list[str | Path],
    dest: str | Path,
    *,
    prune: bool = False,
    include_plugins: bool = False,
) -> list[Path]:
    """Publish recipes, optionally removing previously published stale agents."""

    destination = Path(dest)
    destination.mkdir(parents=True, exist_ok=True)
    prepared_recipes = tuple(
        prepare_source_recipe(recipe_path)
        for recipe_path in recipe_paths
    )
    active_host_agents: set[tuple[str, str]] = set()
    for prepared in prepared_recipes:
        recipe = prepared.recipe
        for host in recipe.compatible_hosts:
            active_host_agents.add((host, recipe.id))

    publication = _HOST_ARTIFACT_PUBLICATION.publish_bundles(
        prepared_recipes,
        destination,
    )
    written = [
        path
        for bundle in publication.bundles
        for path in bundle.written
    ]

    plugin_packages = []
    if include_plugins:
        codex_plugin = publish_codex_plugin_package(prepared_recipes, destination)
        if codex_plugin is not None:
            written.extend(codex_plugin.written)
            plugin_packages.append(codex_plugin.package_record)
        codex_directory_plugin = publish_codex_directory_plugin_package(
            prepared_recipes,
            destination,
        )
        if codex_directory_plugin is not None:
            written.extend(codex_directory_plugin.written)
            plugin_packages.append(codex_directory_plugin.package_record)
        claude_plugin = publish_claude_plugin_package(prepared_recipes, destination)
        if claude_plugin is not None:
            written.extend(claude_plugin.written)
            plugin_packages.extend(claude_plugin.package_records)
        gemini_plugin = publish_gemini_plugin_package(prepared_recipes, destination)
        if gemini_plugin is not None:
            written.extend(gemini_plugin.written)
            plugin_packages.append(gemini_plugin.package_record)
            written.extend(publish_root_mcp_support(prepared_recipes, destination))
        antigravity_plugin = publish_antigravity_plugin_package(prepared_recipes, destination)
        if antigravity_plugin is not None:
            written.extend(antigravity_plugin.written)
            plugin_packages.append(antigravity_plugin.package_record)
        cursor_plugin = publish_cursor_plugin_package(prepared_recipes, destination)
        if cursor_plugin is not None:
            written.extend(cursor_plugin.written)
            plugin_packages.append(cursor_plugin.package_record)
        cursor_sdk = publish_cursor_sdk_package(prepared_recipes, destination)
        if cursor_sdk is not None:
            written.extend(cursor_sdk.written)
            plugin_packages.append(cursor_sdk.package_record)
    manifest = _HOST_ARTIFACT_PUBLICATION.finalize_manifest(
        destination,
        generated_agents=publication.agents,
        plugin_packages=tuple(plugin_packages),
        replace_plugin_groups={
            (package.host, package.distribution_channel)
            for package in plugin_packages
        },
        prune_active_host_agents=active_host_agents if prune else None,
    )
    if manifest is not None:
        written.append(manifest)

    if prepared_recipes or manifest is not None:
        written.append(_write_root_readme(destination))
        catalog_agent_ids = {
            agent.id
            for agent in _HOST_ARTIFACT_PUBLICATION.catalog_agents(destination)
        }
        written.extend(
            write_model_recommendation_artifacts(
                destination,
                catalog_agent_ids or (prepared.recipe.id for prepared in prepared_recipes),
            )
        )

    catalog = _write_catalog_wire(destination)
    if catalog is not None:
        written.append(catalog)

    return written


def _write_catalog_wire(destination: Path) -> Path | None:
    """Project the finalized Catalog Manifest into the signed-release catalog.json."""

    if not (destination / "manifest.json").is_file():
        return None
    manifest = CatalogManifest.load(destination)
    return write_catalog(destination, list(manifest.agents))


def _write_root_readme(destination: Path) -> Path:
    return _ROOT_CATALOG_AGGREGATE.write_readme(
        destination,
        _HOST_ARTIFACT_PUBLICATION.catalog_agents(destination),
    )
