from __future__ import annotations

import gzip
import tarfile
from pathlib import Path

from scripts.build_provenance_bundle import build_bundle


def _write_bundle_inputs(root: Path, *, manifest: str = "{}\n") -> None:
    (root / "manifest.json").write_text(manifest, encoding="utf-8")
    provenance = root / "dist" / "provenance"
    provenance.mkdir(parents=True)
    (provenance / "agent-kit-catalog.intoto.json").write_text("{}\n", encoding="utf-8")
    (provenance / "manifest.sha256").write_text("abc  manifest.json\n", encoding="utf-8")


def test_build_bundle_is_deterministic(tmp_path):
    _write_bundle_inputs(tmp_path)

    first = tmp_path / "first.tgz"
    second = tmp_path / "second.tgz"
    build_bundle(tmp_path, first)
    build_bundle(tmp_path, second)

    assert first.read_bytes() == second.read_bytes()


def test_build_bundle_uses_stable_member_metadata(tmp_path):
    _write_bundle_inputs(tmp_path)

    output = tmp_path / "bundle.tgz"
    build_bundle(tmp_path, output)

    with gzip.GzipFile(output, "rb") as gz:
        with tarfile.open(fileobj=gz, mode="r:") as archive:
            members = archive.getmembers()

    assert [member.name for member in members] == [
        "manifest.json",
        "dist/provenance/agent-kit-catalog.intoto.json",
        "dist/provenance/manifest.sha256",
    ]
    assert all(member.uid == 0 and member.gid == 0 for member in members)
    assert all(member.mtime == 0 for member in members)
