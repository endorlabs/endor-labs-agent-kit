"""Publish compiled agent artifacts into a customer-facing catalog."""

from __future__ import annotations

from pathlib import Path

from endor_agent_kit.compilers.claude_code import HOST as CLAUDE_CODE_HOST
from endor_agent_kit.compilers.claude_managed_agents import HOST as CLAUDE_MANAGED_AGENTS_HOST
from endor_agent_kit.compilers.codex import HOST as CODEX_HOST
from endor_agent_kit.publication import (
    ClaudeCodeHostAdapter,
    ClaudeManagedAgentsHostAdapter,
    CodexHostAdapter,
    HostArtifactPublication,
    RootCatalogAggregate,
)
from endor_agent_kit.recipe import load_recipe
from endor_agent_kit.validator import validate_recipe_file

_HOST_ARTIFACT_PUBLICATION = HostArtifactPublication({
    CLAUDE_CODE_HOST: ClaudeCodeHostAdapter(),
    CLAUDE_MANAGED_AGENTS_HOST: ClaudeManagedAgentsHostAdapter(),
    CODEX_HOST: CodexHostAdapter(),
})
_ROOT_CATALOG_AGGREGATE = RootCatalogAggregate()


def publish_recipe(recipe_path: str | Path, dest: str | Path) -> list[Path]:
    """Publish one recipe's customer-facing artifacts into ``dest``."""

    recipe_file = Path(recipe_path)
    errors = validate_recipe_file(recipe_file)
    if errors:
        raise ValueError("\n".join(errors))

    recipe = load_recipe(recipe_file)
    destination = Path(dest)
    destination.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    manifest: Path | None = None

    if CLAUDE_CODE_HOST in recipe.compatible_hosts:
        publication = _HOST_ARTIFACT_PUBLICATION.publish(CLAUDE_CODE_HOST, recipe_file, recipe, destination)
        written.extend(publication.bundle.written)
        manifest = publication.catalog_manifest

    if CLAUDE_MANAGED_AGENTS_HOST in recipe.compatible_hosts:
        publication = _HOST_ARTIFACT_PUBLICATION.publish(CLAUDE_MANAGED_AGENTS_HOST, recipe_file, recipe, destination)
        written.extend(publication.bundle.written)
        manifest = publication.catalog_manifest

    if CODEX_HOST in recipe.compatible_hosts:
        publication = _HOST_ARTIFACT_PUBLICATION.publish(CODEX_HOST, recipe_file, recipe, destination)
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
    recipe_files = [Path(recipe_path) for recipe_path in recipe_paths]
    active_host_agents: set[tuple[str, str]] = set()
    for recipe_file in recipe_files:
        errors = validate_recipe_file(recipe_file)
        if errors:
            raise ValueError("\n".join(errors))
        recipe = load_recipe(recipe_file)
        for host in recipe.compatible_hosts:
            active_host_agents.add((host, recipe.id))

    written: list[Path] = []
    for recipe_file in recipe_files:
        written.extend(publish_recipe(recipe_file, destination))

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
