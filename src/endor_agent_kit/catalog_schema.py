"""Shared Catalog Manifest schema records."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
from typing import Any, Mapping

from endor_agent_kit.evidence_plans import compile_evidence_plans
from endor_agent_kit.knowledge_pack import default_knowledge_pack_root
from endor_agent_kit.profile_contracts import compile_profile_contract
from endor_agent_kit.recipe import EndorAgentRecipe

MANIFEST_PATH = "manifest.json"
GENERATOR_NAME = "endor-agent-kit"


@dataclass(frozen=True)
class CatalogArtifact:
    """One artifact file recorded in the Catalog Manifest."""

    path: str
    sha256: str
    bytes: int | None = None
    profile_id: str | None = None
    extra_fields: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_manifest_record(cls, record: Any) -> "CatalogArtifact":
        """Parse one artifact record from Catalog Manifest JSON."""

        if not isinstance(record, dict):
            raise ValueError("manifest.json: expected artifact records to be objects")
        extra_fields = _extra_fields(record, {"path", "sha256", "bytes", "profile_id"})
        return cls(
            path=str(record.get("path") or ""),
            sha256=str(record.get("sha256") or ""),
            bytes=_optional_int(record.get("bytes"), "artifact bytes"),
            profile_id=_optional_str(record.get("profile_id"), "artifact profile_id"),
            extra_fields=extra_fields,
        )

    @classmethod
    def from_published_file(
        cls,
        destination: Path,
        path: Path,
        *,
        profile_id: str | None = None,
        extra_fields: Mapping[str, Any] | None = None,
    ) -> "CatalogArtifact":
        """Return manifest metadata for one published artifact file."""

        data = path.read_bytes()
        return cls(
            path=path.relative_to(destination).as_posix(),
            sha256=hashlib.sha256(data).hexdigest(),
            bytes=len(data),
            profile_id=profile_id,
            extra_fields=dict(extra_fields or {}),
        )

    @property
    def name(self) -> str:
        return Path(self.path).name

    def to_manifest_record(self) -> dict[str, Any]:
        """Serialize this artifact to Catalog Manifest JSON shape."""

        record = dict(self.extra_fields)
        record["path"] = self.path
        record["sha256"] = self.sha256
        if self.bytes is not None:
            record["bytes"] = self.bytes
        if self.profile_id is not None:
            record["profile_id"] = self.profile_id
        return record


@dataclass(frozen=True)
class CatalogBundle:
    """One Host Artifact Bundle recorded in the Catalog Manifest."""

    agent_id: str
    agent_name: str
    agent_version: str
    host: str
    bundle_id: str
    bundle_name: str
    path: str
    artifacts: tuple[CatalogArtifact, ...]
    requires_endorctl: str = ""
    include_requires_endorctl: bool = True
    extra_fields: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_manifest_records(
        cls,
        agent: dict[str, Any],
        edition: Any,
    ) -> "CatalogBundle":
        """Parse one edition entry plus its parent agent into a bundle record."""

        if not isinstance(edition, dict):
            raise ValueError("manifest.json: expected edition records to be objects")
        artifacts = edition.get("artifacts", [])
        if not isinstance(artifacts, list):
            raise ValueError("manifest.json: expected edition artifacts to be a list")
        extra_fields = _extra_fields(
            edition,
            {"id", "name", "path", "artifacts", "requires_endorctl"},
        )
        return cls(
            agent_id=str(agent.get("id") or ""),
            agent_name=str(agent.get("name") or ""),
            agent_version=str(agent.get("version") or ""),
            host=str(agent.get("host") or ""),
            bundle_id=str(edition.get("id") or ""),
            bundle_name=str(edition.get("name") or ""),
            path=str(edition.get("path") or ""),
            artifacts=tuple(CatalogArtifact.from_manifest_record(artifact) for artifact in artifacts),
            requires_endorctl=str(edition.get("requires_endorctl") or ""),
            include_requires_endorctl="requires_endorctl" in edition,
            extra_fields=extra_fields,
        )

    @classmethod
    def from_published_bundle(
        cls,
        destination: Path,
        recipe: EndorAgentRecipe,
        host: str,
        bundle_id: str,
        bundle_name: str,
        bundle_dir: Path,
        *,
        requires_endorctl: str = "",
        artifact_profiles: Mapping[str, str] | None = None,
    ) -> "CatalogBundle":
        """Return manifest metadata for one published artifact bundle."""

        files = sorted(path for path in bundle_dir.rglob("*") if path.is_file())
        profiles = artifact_profiles or {}
        profile_metadata: dict[str, dict[str, Any]] = {}
        evidence_plan_metadata: dict[str, dict[str, Any]] = {}
        source_recipe = (
            default_knowledge_pack_root().parent / "agents" / recipe.id / "recipe.yaml"
        )
        if source_recipe.is_file():
            for profile_id in sorted(set(profiles.values())):
                contract = compile_profile_contract(recipe.id, profile_id)
                profile_metadata[profile_id] = {
                    "profile_contract_digest": contract.contract_digest,
                    "profile_gate_validator": {
                        "id": contract.gate_validator_id,
                        "version": contract.gate_validator_version,
                    },
                }
            for plan in compile_evidence_plans(recipe.id):
                evidence_plan_metadata[plan.profile_id] = {
                    "evidence_plan_schema_version": plan.schema_version,
                    "evidence_plan_digest": plan.plan_digest,
                    "evidence_execution_mode": plan.execution_mode,
                    "evidence_plan_executable": plan.execution_mode == "host_adapter",
                }
        return cls(
            agent_id=recipe.id,
            agent_name=recipe.name,
            agent_version=recipe.version,
            host=host,
            bundle_id=bundle_id,
            bundle_name=bundle_name,
            path=bundle_dir.relative_to(destination).as_posix(),
            artifacts=tuple(
                CatalogArtifact.from_published_file(
                    destination,
                    path,
                    profile_id=(profile_id := profiles.get(path.relative_to(destination).as_posix())),
                    extra_fields={
                        **profile_metadata.get(profile_id, {}),
                        **(
                            evidence_plan_metadata.get(profile_id, {})
                            if path.parent.name == "evidence-plans"
                            else {}
                        ),
                    },
                )
                for path in files
            ),
            requires_endorctl=requires_endorctl,
            include_requires_endorctl=True,
        )

    def artifact_named(self, name: str) -> CatalogArtifact | None:
        """Return the first artifact in this bundle with the given filename."""

        for artifact in self.artifacts:
            if artifact.name == name:
                return artifact
        return None

    def to_manifest_edition_record(self) -> dict[str, Any]:
        """Serialize this bundle to its edition entry in Catalog Manifest JSON."""

        record = dict(self.extra_fields)
        record["id"] = self.bundle_id
        record["name"] = self.bundle_name
        record["path"] = self.path
        record["artifacts"] = [artifact.to_manifest_record() for artifact in self.artifacts]
        if self.include_requires_endorctl or self.requires_endorctl:
            record["requires_endorctl"] = self.requires_endorctl
        return record


@dataclass(frozen=True)
class CatalogSource:
    """Source Recipe pointer recorded for one Catalog Manifest agent."""

    recipe_schema_version: int | None = None
    builder_recipe: str = ""
    extra_fields: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_recipe(cls, recipe: EndorAgentRecipe) -> "CatalogSource":
        """Return the manifest source pointer for one Source Recipe."""

        return cls(
            recipe_schema_version=recipe.recipe_schema_version,
            builder_recipe=f"source/agents/{recipe.id}/recipe.yaml",
        )

    @classmethod
    def from_manifest_record(cls, record: Any) -> "CatalogSource | None":
        """Parse the optional source record from Catalog Manifest JSON."""

        if record is None:
            return None
        if not isinstance(record, dict):
            raise ValueError("manifest.json: expected source records to be objects")
        extra_fields = _extra_fields(record, {"recipe_schema_version", "builder_recipe"})
        return cls(
            recipe_schema_version=_optional_int(
                record.get("recipe_schema_version"),
                "source recipe_schema_version",
            ),
            builder_recipe=str(record.get("builder_recipe") or ""),
            extra_fields=extra_fields,
        )

    def to_manifest_record(self) -> dict[str, Any]:
        """Serialize this source pointer to Catalog Manifest JSON shape."""

        record = dict(self.extra_fields)
        if self.recipe_schema_version is not None:
            record["recipe_schema_version"] = self.recipe_schema_version
        if self.builder_recipe:
            record["builder_recipe"] = self.builder_recipe
        return record


@dataclass(frozen=True)
class CatalogAgent:
    """One agent/host entry in the Catalog Manifest."""

    id: str
    host: str
    editions: tuple[CatalogBundle, ...]
    name: str = ""
    version: str = ""
    audience: str = ""
    short_description: str = ""
    description: str = ""
    authors: tuple[str, ...] = ()
    requires_endorctl: str = ""
    source: CatalogSource | None = None
    extra_fields: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_recipe(
        cls,
        recipe: EndorAgentRecipe,
        host: str,
        bundles: tuple[CatalogBundle, ...],
    ) -> "CatalogAgent":
        """Create one agent/host manifest entry from published bundle records."""

        return cls(
            id=recipe.id,
            name=recipe.name,
            version=recipe.version,
            audience=recipe.audience,
            short_description=recipe.short_description,
            description=recipe.description,
            authors=tuple(recipe.authors),
            requires_endorctl=recipe.requires_endorctl,
            host=host,
            source=CatalogSource.from_recipe(recipe),
            editions=bundles,
        )

    @classmethod
    def from_manifest_record(cls, record: Any) -> "CatalogAgent":
        """Parse one agent entry from Catalog Manifest JSON."""

        if not isinstance(record, dict):
            raise ValueError("manifest.json: expected agents to be a list of objects")
        editions = record.get("editions", [])
        if not isinstance(editions, list):
            raise ValueError("manifest.json: expected agent editions to be a list")
        extra_fields = _extra_fields(
            record,
            {
                "id",
                "name",
                "version",
                "audience",
                "short_description",
                "description",
                "authors",
                "requires_endorctl",
                "host",
                "source",
                "editions",
            },
        )
        authors = record.get("authors", [])
        if not isinstance(authors, list):
            raise ValueError("manifest.json: expected agent authors to be a list")
        return cls(
            id=str(record.get("id") or ""),
            name=str(record.get("name") or ""),
            version=str(record.get("version") or ""),
            audience=str(record.get("audience") or ""),
            short_description=str(record.get("short_description") or ""),
            description=str(record.get("description") or ""),
            authors=tuple(str(author) for author in authors),
            requires_endorctl=str(record.get("requires_endorctl") or ""),
            host=str(record.get("host") or ""),
            source=CatalogSource.from_manifest_record(record.get("source")),
            editions=tuple(CatalogBundle.from_manifest_records(record, edition) for edition in editions),
            extra_fields=extra_fields,
        )

    def to_manifest_record(self) -> dict[str, Any]:
        """Serialize this agent to Catalog Manifest JSON shape."""

        record = dict(self.extra_fields)
        record["id"] = self.id
        if self.name:
            record["name"] = self.name
        if self.version:
            record["version"] = self.version
        if self.audience:
            record["audience"] = self.audience
        if self.short_description:
            record["short_description"] = self.short_description
        if self.description:
            record["description"] = self.description
        if self.authors:
            record["authors"] = list(self.authors)
        if self.requires_endorctl:
            record["requires_endorctl"] = self.requires_endorctl
        record["host"] = self.host
        if self.source is not None:
            record["source"] = self.source.to_manifest_record()
        record["editions"] = [bundle.to_manifest_edition_record() for bundle in self.editions]
        return record


def catalog_agents_from_manifest_payload(
    data: Any,
    *,
    manifest_path: str = MANIFEST_PATH,
) -> tuple[CatalogAgent, ...]:
    """Parse Catalog Manifest agent records from loaded JSON."""

    if not isinstance(data, dict):
        raise ValueError(f"{manifest_path}: expected a JSON object")
    agents = data.get("agents", [])
    if not isinstance(agents, list) or not all(isinstance(agent, dict) for agent in agents):
        raise ValueError(f"{manifest_path}: expected agents to be a list of objects")
    return tuple(CatalogAgent.from_manifest_record(agent) for agent in agents)


@dataclass(frozen=True)
class CatalogPluginPackage:
    """One generated plugin package recorded in the Catalog Manifest."""

    host: str
    name: str
    version: str
    path: str
    included_agents: tuple[str, ...]
    artifacts: tuple[CatalogArtifact, ...]
    display_name: str = ""
    marketplace_path: str = ""
    extra_fields: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_manifest_record(cls, record: Any) -> "CatalogPluginPackage":
        """Parse one plugin package record from Catalog Manifest JSON."""

        if not isinstance(record, dict):
            raise ValueError("manifest.json: expected plugin package records to be objects")
        artifacts = record.get("artifacts", [])
        if not isinstance(artifacts, list):
            raise ValueError("manifest.json: expected plugin package artifacts to be a list")
        included_agents = record.get("included_agents", [])
        if not isinstance(included_agents, list):
            raise ValueError("manifest.json: expected plugin package included_agents to be a list")
        extra_fields = _extra_fields(
            record,
            {
                "host",
                "name",
                "display_name",
                "version",
                "path",
                "marketplace_path",
                "included_agents",
                "artifacts",
            },
        )
        return cls(
            host=str(record.get("host") or ""),
            name=str(record.get("name") or ""),
            display_name=str(record.get("display_name") or ""),
            version=str(record.get("version") or ""),
            path=str(record.get("path") or ""),
            marketplace_path=str(record.get("marketplace_path") or ""),
            included_agents=tuple(str(item) for item in included_agents),
            artifacts=tuple(CatalogArtifact.from_manifest_record(artifact) for artifact in artifacts),
            extra_fields=extra_fields,
        )

    @classmethod
    def from_published_package(
        cls,
        destination: Path,
        *,
        host: str,
        name: str,
        display_name: str,
        version: str,
        package_dir: Path,
        included_agents: tuple[str, ...],
        marketplace_path: str = "",
        extra_artifacts: tuple[Path, ...] = (),
    ) -> "CatalogPluginPackage":
        """Return manifest metadata for one generated plugin package."""

        files = sorted(path for path in package_dir.rglob("*") if path.is_file())
        files.extend(path for path in extra_artifacts if path.is_file())
        return cls(
            host=host,
            name=name,
            display_name=display_name,
            version=version,
            path=package_dir.relative_to(destination).as_posix(),
            marketplace_path=marketplace_path,
            included_agents=tuple(sorted(included_agents)),
            artifacts=tuple(CatalogArtifact.from_published_file(destination, path) for path in files),
        )

    def to_manifest_record(self) -> dict[str, Any]:
        """Serialize this plugin package to Catalog Manifest JSON shape."""

        record = dict(self.extra_fields)
        record["host"] = self.host
        record["name"] = self.name
        if self.display_name:
            record["display_name"] = self.display_name
        record["version"] = self.version
        record["path"] = self.path
        if self.marketplace_path:
            record["marketplace_path"] = self.marketplace_path
        record["included_agents"] = list(self.included_agents)
        record["artifacts"] = [artifact.to_manifest_record() for artifact in self.artifacts]
        return record


def catalog_plugin_packages_from_manifest_payload(
    data: Any,
    *,
    manifest_path: str = MANIFEST_PATH,
) -> tuple[CatalogPluginPackage, ...]:
    """Parse Catalog Manifest plugin package records from loaded JSON."""

    if not isinstance(data, dict):
        raise ValueError(f"{manifest_path}: expected a JSON object")
    packages = data.get("plugin_packages", [])
    if not isinstance(packages, list) or not all(isinstance(package, dict) for package in packages):
        raise ValueError(f"{manifest_path}: expected plugin_packages to be a list of objects")
    return tuple(CatalogPluginPackage.from_manifest_record(package) for package in packages)


def catalog_manifest_payload(
    agents: tuple[CatalogAgent, ...],
    *,
    plugin_packages: tuple[CatalogPluginPackage, ...] = (),
    generator_name: str = GENERATOR_NAME,
) -> dict[str, Any]:
    """Return the JSON payload for a Catalog Manifest."""

    payload = {
        "schema_version": 1,
        "generated_by": generator_name,
        "agents": [agent.to_manifest_record() for agent in agents],
    }
    if plugin_packages:
        payload["plugin_packages"] = [
            package.to_manifest_record()
            for package in sorted(plugin_packages, key=catalog_plugin_package_sort_key)
        ]
    return payload


def catalog_agent_sort_key(agent: CatalogAgent) -> tuple[str, str]:
    """Return the stable Catalog Manifest sort key for one agent."""

    return (agent.host, agent.id)


def catalog_plugin_package_sort_key(package: CatalogPluginPackage) -> tuple[str, str]:
    """Return the stable Catalog Manifest sort key for one plugin package."""

    return (package.host, package.name)


def _extra_fields(record: dict[str, Any], known: set[str]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in known}


def _optional_int(value: Any, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    raise ValueError(f"manifest.json: expected {field_name} to be an integer")


def _optional_str(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise ValueError(f"manifest.json: expected {field_name} to be a string")
