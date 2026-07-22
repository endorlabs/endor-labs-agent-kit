from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat
import sys

import pytest

from endor_agent_kit.artifact_summary import (
    ArtifactSummaryError,
    capture_and_summarize,
    main,
    summarize_artifact,
)


def _write_artifact(path: Path, objects: list[dict[str, object]]) -> bytes:
    payload = json.dumps({"list": {"objects": objects}}, separators=(",", ":")).encode()
    path.write_bytes(payload)
    return payload


def test_summarize_artifact_returns_compact_integrity_metadata(tmp_path: Path):
    artifact = tmp_path / "findings.json"
    payload = _write_artifact(
        artifact,
        [
            {"uuid": "finding-1", "spec": {"level": "FINDING_LEVEL_HIGH"}},
            {"uuid": "finding-2", "spec": {"level": "FINDING_LEVEL_LOW"}},
        ],
    )

    summary = summarize_artifact(artifact)

    assert summary == {
        "artifact_ref": str(artifact.absolute()),
        "bytes": len(payload),
        "collection_path": "list.objects",
        "duplicate_count": 0,
        "format": "json",
        "missing_unique_count": 0,
        "row_count": 2,
        "schema_version": "endor.agent-artifact-summary/v1",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "status": "valid",
        "unique_count": 2,
        "unique_field": "uuid",
    }
    assert "finding-1" not in json.dumps(summary)
    assert "FINDING_LEVEL_HIGH" not in json.dumps(summary)


def test_summarize_artifact_rejects_duplicate_ids_without_leaking_them(
    tmp_path: Path,
    capsys,
):
    artifact = tmp_path / "duplicate.json"
    _write_artifact(artifact, [{"uuid": "secret-id"}, {"uuid": "secret-id"}])

    exit_code = main([str(artifact)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "duplicate_unique_values" in captured.err
    assert "secret-id" not in captured.err


def test_summarize_artifact_rejects_missing_agent_api_envelope(
    tmp_path: Path,
    capsys,
):
    artifact = tmp_path / "wrong-shape.json"
    artifact.write_text('{"objects":[]}', encoding="utf-8")

    exit_code = main([str(artifact)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "missing_collection_path" in captured.err
    assert artifact.read_text(encoding="utf-8") not in captured.err


def test_summarize_artifact_cli_emits_one_compact_json_record(
    tmp_path: Path,
    capsys,
):
    artifact = tmp_path / "packages.json"
    _write_artifact(artifact, [{"uuid": "package-1"}])

    exit_code = main([str(artifact)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert captured.out.count("\n") == 1
    assert json.loads(captured.out)["row_count"] == 1
    assert "package-1" not in captured.out


def test_summarize_artifact_enforces_size_limit_before_parsing(
    tmp_path: Path,
    capsys,
):
    artifact = tmp_path / "too-large.json"
    _write_artifact(artifact, [{"uuid": "finding-1"}])

    exit_code = main([str(artifact), "--max-bytes", "10"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "artifact_too_large" in captured.err


def _fake_endorctl(path: Path, *, exit_code: int = 0) -> Path:
    executable = path / "endorctl"
    payload = json.dumps(
        {"list": {"objects": [{"uuid": "finding-1"}, {"uuid": "finding-2"}]}},
        separators=(",", ":"),
    )
    executable.write_text(
        "\n".join(
            [
                f"#!{sys.executable}",
                "import sys",
                f"sys.stdout.write({payload!r})",
                f"raise SystemExit({exit_code})",
                "",
            ]
        ),
        encoding="utf-8",
    )
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    return executable


def _capture_command(executable: Path) -> list[str]:
    return [
        str(executable),
        "agent",
        "api",
        "--agent-id",
        "findings-browser",
        "list",
        "-r",
        "Finding",
        "-n",
        "example",
        "--field-mask",
        "uuid,spec.level",
        "--list-all",
        "-o",
        "json",
    ]


def test_capture_and_summarize_executes_one_direct_agent_api_list(tmp_path: Path):
    executable = _fake_endorctl(tmp_path)
    artifact_dir = tmp_path / "artifacts"

    summary = capture_and_summarize(
        _capture_command(executable),
        artifact_dir=artifact_dir,
    )

    assert summary["status"] == "valid"
    assert summary["row_count"] == 2
    assert summary["unique_count"] == 2
    assert Path(summary["artifact_ref"]).parent == artifact_dir
    assert stat.S_IMODE(Path(summary["artifact_ref"]).stat().st_mode) == 0o600
    assert "finding-1" not in json.dumps(summary)


def test_capture_cli_emits_only_summary_json(tmp_path: Path, capsys):
    executable = _fake_endorctl(tmp_path)

    exit_code = main(
        [
            "capture",
            "--artifact-dir",
            str(tmp_path / "artifacts"),
            "--",
            *_capture_command(executable),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert json.loads(captured.out)["row_count"] == 2
    assert "finding-1" not in captured.out


def test_capture_rejects_non_endorctl_commands_without_executing_them(tmp_path: Path):
    marker = tmp_path / "executed"

    with pytest.raises(ArtifactSummaryError, match="direct endorctl"):
        capture_and_summarize(
            [sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"],
            artifact_dir=tmp_path / "artifacts",
        )

    assert not marker.exists()


def test_failed_capture_removes_partial_artifact(tmp_path: Path):
    executable = _fake_endorctl(tmp_path, exit_code=7)
    artifact_dir = tmp_path / "artifacts"

    with pytest.raises(ArtifactSummaryError, match="status 7"):
        capture_and_summarize(
            _capture_command(executable),
            artifact_dir=artifact_dir,
        )

    assert list(artifact_dir.iterdir()) == []
