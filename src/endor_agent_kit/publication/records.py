"""Shared publication records and artifact metadata helpers."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping

from endor_agent_kit.catalog_schema import CatalogBundle
from endor_agent_kit.evidence_plans import compile_evidence_plans
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


def with_evidence_plan_artifacts(
    bundle: BundleRecord,
    destination: Path,
    prepared: PreparedSourceRecipe,
) -> BundleRecord:
    """Add identical inert Evidence Plans to every published Host bundle."""

    plans = compile_evidence_plans(prepared.recipe.id)
    if not plans:
        return bundle

    written = list(bundle.written)
    records: list[CatalogBundle] = []
    for record in bundle.manifest_records:
        bundle_dir = destination / record.path
        plan_dir = bundle_dir / "evidence-plans"
        plan_dir.mkdir(parents=True, exist_ok=True)
        artifact_profiles = {
            artifact.path: artifact.profile_id
            for artifact in record.artifacts
            if artifact.profile_id is not None
        }
        for plan in plans:
            artifact = plan_dir / f"{plan.profile_id}.json"
            artifact.write_bytes(plan.to_json_bytes())
            written.append(artifact)
            artifact_profiles[artifact.relative_to(destination).as_posix()] = plan.profile_id
        rebuilt = CatalogBundle.from_published_bundle(
            destination,
            prepared.recipe,
            record.host,
            record.bundle_id,
            record.bundle_name,
            bundle_dir,
            requires_endorctl=record.requires_endorctl,
            artifact_profiles=artifact_profiles,
        )
        records.append(
            replace(
                rebuilt,
                include_requires_endorctl=record.include_requires_endorctl,
                extra_fields=record.extra_fields,
            )
        )
    return BundleRecord(
        host=bundle.host,
        written=tuple(written),
        manifest_records=tuple(records),
    )


def artifact_bundle_record(
    destination: Path,
    recipe: EndorAgentRecipe,
    host: str,
    bundle_id: str,
    bundle_name: str,
    bundle_dir: Path,
    *,
    requires_endorctl: str = "",
    artifact_profiles: Mapping[str, str] | None = None,
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
        artifact_profiles=artifact_profiles,
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
