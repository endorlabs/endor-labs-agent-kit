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
from endor_agent_kit.publication.cursor_plugin import publish_cursor_plugin_package
from endor_agent_kit.publication.gemini_plugin import publish_gemini_plugin_package
from endor_agent_kit.prepared_source_recipe import PreparedSourceRecipe, prepare_source_recipe

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


def _publish_prepared_recipe(prepared: PreparedSourceRecipe, dest: str | Path) -> list[Path]:
    """Publish one prepared Source Recipe into ``dest``."""

    recipe = prepared.recipe
    destination = Path(dest)
    destination.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    manifest: Path | None = None

    if CLAUDE_CODE_HOST in recipe.compatible_hosts:
        publication = _HOST_ARTIFACT_PUBLICATION.publish(CLAUDE_CODE_HOST, prepared, destination)
        written.extend(publication.bundle.written)
        manifest = publication.catalog_manifest

    if CLAUDE_MANAGED_AGENTS_HOST in recipe.compatible_hosts:
        publication = _HOST_ARTIFACT_PUBLICATION.publish(CLAUDE_MANAGED_AGENTS_HOST, prepared, destination)
        written.extend(publication.bundle.written)
        manifest = publication.catalog_manifest

    if CODEX_HOST in recipe.compatible_hosts:
        publication = _HOST_ARTIFACT_PUBLICATION.publish(CODEX_HOST, prepared, destination)
        written.extend(publication.bundle.written)
        manifest = publication.catalog_manifest

    if GEMINI_HOST in recipe.compatible_hosts:
        publication = _HOST_ARTIFACT_PUBLICATION.publish(GEMINI_HOST, prepared, destination)
        written.extend(publication.bundle.written)
        manifest = publication.catalog_manifest

    if PORTABLE_HOST in recipe.compatible_hosts:
        publication = _HOST_ARTIFACT_PUBLICATION.publish(PORTABLE_HOST, prepared, destination)
        written.extend(publication.bundle.written)
        manifest = publication.catalog_manifest

    if manifest is not None:
        written.append(manifest)
    root_readme = _write_root_readme(destination)
    written.append(root_readme)
    return written


def publish_recipes(
    recipe_paths: list[str | Path],
    dest: str | Path,
    *,
    prune: bool = False,
    include_plugins: bool = False,
) -> list[Path]:
    """Publish recipes, optionally removing previously published stale agents."""

    destination = Path(dest)
    prepared_recipes = [prepare_source_recipe(recipe_path) for recipe_path in recipe_paths]
    active_host_agents: set[tuple[str, str]] = set()
    for prepared in prepared_recipes:
        recipe = prepared.recipe
        for host in recipe.compatible_hosts:
            active_host_agents.add((host, recipe.id))

    written: list[Path] = []
    for prepared in prepared_recipes:
        written.extend(_publish_prepared_recipe(prepared, destination))

    if prune:
        manifest = _HOST_ARTIFACT_PUBLICATION.prune_stale_agents(destination, active_host_agents)
        if manifest is not None:
            written.append(manifest)
            written.append(_write_root_readme(destination))

    if include_plugins:
        plugin_packages = []
        codex_plugin = publish_codex_plugin_package(prepared_recipes, destination)
        if codex_plugin is not None:
            written.extend(codex_plugin.written)
            plugin_packages.append(codex_plugin.package_record)
        claude_plugin = publish_claude_plugin_package(prepared_recipes, destination)
        if claude_plugin is not None:
            written.extend(claude_plugin.written)
            plugin_packages.extend(claude_plugin.package_records)
        gemini_plugin = publish_gemini_plugin_package(prepared_recipes, destination)
        if gemini_plugin is not None:
            written.extend(gemini_plugin.written)
            plugin_packages.append(gemini_plugin.package_record)
        antigravity_plugin = publish_antigravity_plugin_package(prepared_recipes, destination)
        if antigravity_plugin is not None:
            written.extend(antigravity_plugin.written)
            plugin_packages.append(antigravity_plugin.package_record)
        cursor_plugin = publish_cursor_plugin_package(prepared_recipes, destination)
        if cursor_plugin is not None:
            written.extend(cursor_plugin.written)
            plugin_packages.append(cursor_plugin.package_record)
        if plugin_packages:
            manifest = _HOST_ARTIFACT_PUBLICATION.write_plugin_packages(
                destination,
                tuple(plugin_packages),
                replace_hosts={package.host for package in plugin_packages},
            )
            written.append(manifest)

    return written


def _write_root_readme(destination: Path) -> Path:
    return _ROOT_CATALOG_AGGREGATE.write_readme(
        destination,
        _HOST_ARTIFACT_PUBLICATION.catalog_agents(destination),
    )
