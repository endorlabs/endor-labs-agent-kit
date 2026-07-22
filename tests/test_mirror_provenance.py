from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_mirror_provenance import validate_mirror_provenance


def _write_mirror(root: Path, *, checksum: str = "a" * 64) -> None:
    ids = [f"agent-{index}" for index in range(11)]
    (root / "agents").mkdir(parents=True)
    for agent_id in ids:
        (root / "agents" / f"endor-{agent_id}-agent.md").write_text("agent\n", encoding="utf-8")
    (root / "agents/endor-agent-kit-setup-agent.md").write_text("setup\n", encoding="utf-8")
    (root / "provenance").mkdir()
    statement = {
        "subject": [{"name": "manifest.json", "digest": {"sha256": checksum}}],
        "predicate": {"catalog": [{"id": agent_id} for agent_id in ids]},
    }
    (root / "provenance/agent-kit-catalog.intoto.json").write_text(
        json.dumps(statement), encoding="utf-8"
    )
    (root / "provenance/manifest.sha256").write_text(
        f"{checksum}  manifest.json\n", encoding="utf-8"
    )


def test_mirror_provenance_matches_canonical_root_agents(tmp_path: Path) -> None:
    _write_mirror(tmp_path)

    assert validate_mirror_provenance(tmp_path) == []


def test_mirror_provenance_rejects_checksum_or_identity_drift(tmp_path: Path) -> None:
    _write_mirror(tmp_path)
    (tmp_path / "provenance/manifest.sha256").write_text(
        f"{'b' * 64}  manifest.json\n", encoding="utf-8"
    )
    (tmp_path / "agents/endor-agent-0-agent.md").unlink()

    errors = validate_mirror_provenance(tmp_path)

    assert "manifest checksum does not match provenance subject" in errors
    assert "mirror canonical agent ids do not match provenance" in errors
