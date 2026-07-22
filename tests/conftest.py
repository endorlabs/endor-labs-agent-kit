from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

from endor_agent_kit.publisher import publish_recipes


@dataclass(frozen=True)
class GeneratedCatalog:
    """Immutable session catalog shared by read-only publication assertions."""

    root: Path
    recipes: tuple[Path, ...]


CATALOG_AGGREGATE_PATHS = {
    "README.md",
    "catalog.json",
    "docs/model-recommendations.md",
    "manifest.json",
    "model-recommendations.json",
}
CATALOG_ROOT_NAMES = {
    "README.md",
    "catalog.json",
    "claude-code",
    "claude-managed-agents",
    "codex",
    "docs",
    "gemini",
    "manifest.json",
    "model-recommendations.json",
    "portable",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def recipe_path() -> Path:
    return repo_root() / "source" / "agents" / "dependency-reviewer" / "recipe.yaml"


@pytest.fixture(scope="session")
def generated_catalog(tmp_path_factory: pytest.TempPathFactory) -> GeneratedCatalog:
    """Build the canonical all-provider catalog once for read-only tests."""

    workspace = tmp_path_factory.mktemp("generated-catalog")
    source_root = workspace / "source-agents"
    recipes: list[Path] = []
    for source in sorted((repo_root() / "source" / "agents").iterdir()):
        if not source.is_dir() or not (source / "recipe.yaml").is_file():
            continue
        copied = source_root / source.name
        shutil.copytree(source, copied, ignore=shutil.ignore_patterns("dist"))
        recipes.append(copied / "recipe.yaml")

    catalog_root = workspace / "catalog"
    publish_recipes(
        recipes,
        catalog_root,
        prune=True,
        include_plugins=True,
    )
    return GeneratedCatalog(root=catalog_root, recipes=tuple(recipes))
