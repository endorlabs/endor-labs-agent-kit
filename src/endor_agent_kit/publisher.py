"""Publish compiled agent artifacts into a customer-facing catalog."""

from __future__ import annotations

from pathlib import Path

from endor_agent_kit.compilers.claude_code import HOST as CLAUDE_CODE_HOST
from endor_agent_kit.compilers.claude_managed_agents import HOST as CLAUDE_MANAGED_AGENTS_HOST
from endor_agent_kit.compilers.codex import HOST as CODEX_HOST
from endor_agent_kit.compilers.portable import HOST as PORTABLE_HOST
from endor_agent_kit.publication import (
    ClaudeCodeHostAdapter,
    ClaudeManagedAgentsHostAdapter,
    CodexHostAdapter,
    HostArtifactPublication,
    PortableHostAdapter,
    RootCatalogAggregate,
)
from endor_agent_kit.prepared_source_recipe import PreparedSourceRecipe, prepare_source_recipe

_HOST_ARTIFACT_PUBLICATION = HostArtifactPublication({
    CLAUDE_CODE_HOST: ClaudeCodeHostAdapter(),
    CLAUDE_MANAGED_AGENTS_HOST: ClaudeManagedAgentsHostAdapter(),
    CODEX_HOST: CodexHostAdapter(),
    PORTABLE_HOST: PortableHostAdapter(),
})
_ROOT_CATALOG_AGGREGATE = RootCatalogAggregate()


def publish_recipe(recipe_path: str | Path, dest: str | Path) -> list[Path]:
    """Publish one recipe's customer-facing artifacts into ``dest``."""

    return _publish_prepared_recipe(prepare_source_recipe(recipe_path), dest)


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

    if PORTABLE_HOST in recipe.compatible_hosts:
        publication = _HOST_ARTIFACT_PUBLICATION.publish(PORTABLE_HOST, prepared, destination)
        written.extend(publication.bundle.written)
        manifest = publication.catalog_manifest

    if manifest is not None:
        written.append(manifest)
    root_readme = _write_root_readme(destination)
    written.append(root_readme)
    return written


def publish_recipes(recipe_paths: list[str | Path], dest: str | Path, *, prune: bool = False) -> list[Path]:
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

    return written


def _write_root_readme(destination: Path) -> Path:
    return _ROOT_CATALOG_AGGREGATE.write_readme(
        destination,
        _HOST_ARTIFACT_PUBLICATION.catalog_agents(destination),
    )
