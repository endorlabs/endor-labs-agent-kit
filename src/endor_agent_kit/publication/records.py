"""Shared publication records and artifact metadata helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from endor_agent_kit.catalog_schema import CatalogBundle
from endor_agent_kit.prepared_source_recipe import PreparedSourceRecipe
from endor_agent_kit.recipe import EndorAgentRecipe


@dataclass(frozen=True)
class BundleRecord:
    """Internal result of publishing one host artifact bundle."""

    host: str
    written: tuple[Path, ...]
    manifest_records: tuple[CatalogBundle, ...]


@dataclass(frozen=True)
class PublicationRecord:
    """Internal result of publishing one bundle into the Catalog Manifest."""

    bundle: BundleRecord
    catalog_manifest: Path


def artifact_bundle_record(
    destination: Path,
    recipe: EndorAgentRecipe,
    host: str,
    bundle_id: str,
    bundle_name: str,
    bundle_dir: Path,
    *,
    requires_endorctl: str = "",
) -> CatalogBundle:
    """Return manifest metadata for one published artifact bundle."""

    return CatalogBundle.from_published_bundle(
        destination,
        recipe,
        host,
        bundle_id,
        bundle_name,
        bundle_dir,
        requires_endorctl=requires_endorctl,
    )


def architecture_source(recipe_file: Path) -> Path:
    """Return the optional source architecture diagram path."""

    return recipe_file.parent / "architecture.svg"


def actions_source(recipe_file: Path, recipe: EndorAgentRecipe) -> Path:
    """Return the optional source action contract path."""

    if not recipe.action_contracts_path:
        return recipe_file.parent / "__no_actions_yaml__"
    return recipe_file.parent / recipe.action_contracts_path


def prepared_architecture_source(prepared: PreparedSourceRecipe) -> Path:
    """Return the optional source architecture diagram path for a prepared recipe."""

    return prepared.architecture_path


def prepared_actions_source(prepared: PreparedSourceRecipe) -> Path:
    """Return the optional source action contract path for a prepared recipe."""

    return prepared.action_contracts_path
