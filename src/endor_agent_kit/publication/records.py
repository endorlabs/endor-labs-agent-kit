"""Shared publication records and artifact metadata helpers."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any

from endor_agent_kit.recipe import EndorAgentRecipe


@dataclass(frozen=True)
class BundleRecord:
    """Internal result of publishing one host artifact bundle."""

    host: str
    written: tuple[Path, ...]
    manifest_records: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class PublicationRecord:
    """Internal result of publishing one bundle into the Catalog Manifest."""

    bundle: BundleRecord
    catalog_manifest: Path


def artifact_bundle_record(
    destination: Path,
    recipe: EndorAgentRecipe,
    bundle_id: str,
    bundle_name: str,
    bundle_dir: Path,
    *,
    requires_endorctl: str = "",
) -> dict[str, Any]:
    """Return manifest metadata for one published artifact bundle."""

    files = sorted(path for path in bundle_dir.rglob("*") if path.is_file())
    return {
        "id": bundle_id,
        "name": bundle_name,
        "path": bundle_dir.relative_to(destination).as_posix(),
        "artifacts": [artifact_record(destination, path) for path in files],
        "requires_endorctl": requires_endorctl,
    }


def artifact_record(destination: Path, path: Path) -> dict[str, Any]:
    """Return manifest metadata for one published artifact file."""

    data = path.read_bytes()
    return {
        "path": path.relative_to(destination).as_posix(),
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
    }


def architecture_source(recipe_file: Path) -> Path:
    """Return the optional source architecture diagram path."""

    return recipe_file.parent / "architecture.svg"


def actions_source(recipe_file: Path, recipe: EndorAgentRecipe) -> Path:
    """Return the optional source action contract path."""

    if not recipe.action_contracts_path:
        return recipe_file.parent / "__no_actions_yaml__"
    return recipe_file.parent / recipe.action_contracts_path
