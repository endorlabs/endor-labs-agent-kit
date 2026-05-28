"""Release provenance for the generated catalog.

Integrity today is per-artifact ``sha256`` recorded in ``manifest.json``. This
module adds the two pieces release provenance needs on top of that:

1. Whole-catalog verification: recompute every recorded artifact digest from disk
   and confirm it matches the manifest, so a downloaded or installed catalog can
   be checked offline and deterministically.
2. A single signable subject + SLSA-style in-toto statement. ``manifest.json`` is
   the subject; because it commits to every artifact's ``sha256``, signing the
   manifest digest anchors the whole catalog. Producing/holding signing keys is a
   release-pipeline concern, so this module emits the attestable statement and
   leaves the signature to CI (e.g. cosign / SLSA generator / gh attestation).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from endor_agent_kit.catalog_schema import (
    GENERATOR_NAME,
    MANIFEST_PATH,
    catalog_agents_from_manifest_payload,
)

PREDICATE_TYPE = "https://endorlabs.com/agent-kit/catalog-provenance/v1"
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
DEFAULT_BUILDER_ID = "https://github.com/endorlabs/endor-labs-agent-kit"


def file_sha256(path: str | Path) -> str:
    """Return the hex sha256 digest of a file's bytes."""

    digest = hashlib.sha256()
    digest.update(Path(path).read_bytes())
    return digest.hexdigest()


def verify_catalog_provenance(catalog_root: str | Path = ".") -> list[str]:
    """Return integrity errors comparing on-disk artifacts to the manifest."""

    root = Path(catalog_root)
    manifest_path = root / MANIFEST_PATH
    if not manifest_path.is_file():
        return [f"{MANIFEST_PATH}: missing catalog manifest"]

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        agents = catalog_agents_from_manifest_payload(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        return [f"{MANIFEST_PATH}: {exc}"]

    errors: list[str] = []
    for agent in agents:
        for bundle in agent.editions:
            for artifact in bundle.artifacts:
                path = root / artifact.path
                if not path.is_file():
                    errors.append(
                        f"{artifact.path}: missing published artifact recorded in manifest"
                    )
                    continue
                actual = file_sha256(path)
                if actual != artifact.sha256:
                    errors.append(
                        f"{artifact.path}: sha256 mismatch "
                        f"(manifest {artifact.sha256[:12]}..., disk {actual[:12]}...)"
                    )
    return errors


def catalog_manifest_subject(catalog_root: str | Path = ".") -> dict[str, object]:
    """Return the in-toto subject for the catalog manifest."""

    manifest_path = Path(catalog_root) / MANIFEST_PATH
    return {
        "name": MANIFEST_PATH,
        "digest": {"sha256": file_sha256(manifest_path)},
    }


def build_provenance_statement(
    catalog_root: str | Path = ".",
    *,
    builder_id: str = DEFAULT_BUILDER_ID,
) -> dict[str, object]:
    """Return a deterministic SLSA-style in-toto statement for the catalog.

    The statement carries no timestamp so it is reproducible from catalog content
    alone; release identity (time, run id, signer) belongs to the CI signature
    wrapped around this statement, not to the attestable subject itself.
    """

    root = Path(catalog_root)
    payload = json.loads((root / MANIFEST_PATH).read_text(encoding="utf-8"))
    agents = catalog_agents_from_manifest_payload(payload)

    catalog = [
        {
            "id": agent.id,
            "host": agent.host,
            "bundles": len(agent.editions),
            "source_recipe": agent.source.builder_recipe if agent.source else "",
        }
        for agent in sorted(agents, key=lambda agent: (agent.host, agent.id))
    ]

    return {
        "_type": STATEMENT_TYPE,
        "subject": [catalog_manifest_subject(root)],
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            "builder": {"id": builder_id},
            "generator": str(payload.get("generated_by", GENERATOR_NAME)),
            "manifest_schema_version": payload.get("schema_version"),
            "catalog": catalog,
        },
    }
