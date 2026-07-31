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
    score_cicd_posture,
    summarize_artifact,
)
from endor_agent_kit.workflow_output_contracts.cicd_posture import (
    compute_cicd_posture_scores,
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


def _fake_endorctl(
    path: Path,
    *,
    exit_code: int = 0,
    objects: list[dict[str, object]] | None = None,
) -> Path:
    executable = path / "endorctl"
    payload = json.dumps(
        {
            "list": {
                "objects": objects
                if objects is not None
                else [{"uuid": "finding-1"}, {"uuid": "finding-2"}]
            }
        },
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


def _ai_sast_objects() -> list[dict[str, object]]:
    return [
        {
            "uuid": "finding-z",
            "context": {"type": "CONTEXT_TYPE_MAIN"},
            "spec": {
                "project_uuid": "project-1",
                "method": "SYSTEM_EVALUATION_METHOD_DEFINITION_AI_SAST",
                "level": "FINDING_LEVEL_CRITICAL",
                "source_code_version": {"sha": "abc123", "ref": "main"},
            },
        },
        {
            "uuid": "finding-a",
            "context": {"type": "CONTEXT_TYPE_MAIN"},
            "spec": {
                "project_uuid": "project-1",
                "method": "SYSTEM_EVALUATION_METHOD_DEFINITION_AI_SAST",
                "level": "FINDING_LEVEL_CRITICAL",
                "source_code_version": {"sha": "abc123", "ref": "main"},
            },
        },
        {
            "uuid": "finding-high",
            "context": {"type": "CONTEXT_TYPE_MAIN"},
            "spec": {
                "project_uuid": "project-1",
                "method": "SYSTEM_EVALUATION_METHOD_DEFINITION_AI_SAST",
                "level": "FINDING_LEVEL_HIGH",
                "source_code_version": {"sha": "abc123", "ref": "main"},
            },
        },
    ]


def _ai_sast_capture_command(executable: Path) -> list[str]:
    return [
        str(executable),
        "agent",
        "api",
        "--agent-id",
        "ai-sast-remediation",
        "list",
        "-r",
        "Finding",
        "-n",
        "example",
        "--filter",
        (
            'context.type==CONTEXT_TYPE_MAIN and spec.project_uuid=="project-1" '
            'and spec.method=="SYSTEM_EVALUATION_METHOD_DEFINITION_AI_SAST"'
        ),
        "--field-mask",
        "uuid,context.type,spec.project_uuid,spec.method,spec.level,spec.source_code_version",
        "--list-all",
        "-o",
        "json",
    ]


def test_ai_sast_projection_selects_highest_severity_with_stable_uuid_tie_break(
    tmp_path: Path,
):
    first_artifact = tmp_path / "findings-first.json"
    second_artifact = tmp_path / "findings-second.json"
    objects = _ai_sast_objects()
    _write_artifact(first_artifact, objects)
    _write_artifact(second_artifact, list(reversed(objects)))

    first = summarize_artifact(first_artifact, projection="ai-sast-selection")
    second = summarize_artifact(second_artifact, projection="ai-sast-selection")

    assert first["selection_summary"] == second["selection_summary"] == {
        "all_artifact_rows_evaluated": True,
        "project_uuid": "project-1",
        "selected_finding_uuid": "finding-a",
        "selected_level": "CRITICAL",
        "selection_rule": "severity_desc_uuid_asc_v1",
        "severity_counts": {
            "CRITICAL": 2,
            "HIGH": 1,
            "INFO": 0,
            "LOW": 0,
            "MEDIUM": 0,
        },
        "tie_count_at_selected_level": 2,
    }
    serialized = json.dumps(first)
    assert "finding-a" in serialized
    assert "finding-z" not in serialized
    assert "finding-high" not in serialized


def test_ai_sast_projection_rejects_unrankable_or_cross_scope_rows(tmp_path: Path):
    invalid_level = tmp_path / "invalid-level.json"
    objects = _ai_sast_objects()
    objects[0]["spec"]["level"] = "FINDING_LEVEL_UNKNOWN"  # type: ignore[index]
    _write_artifact(invalid_level, objects)

    with pytest.raises(ArtifactSummaryError) as unknown:
        summarize_artifact(invalid_level, projection="ai-sast-selection")
    assert unknown.value.code == "invalid_ai_sast_level"

    cross_scope = tmp_path / "cross-scope.json"
    objects = _ai_sast_objects()
    objects[0]["spec"]["project_uuid"] = "project-2"  # type: ignore[index]
    _write_artifact(cross_scope, objects)

    with pytest.raises(ArtifactSummaryError) as mixed:
        summarize_artifact(cross_scope, projection="ai-sast-selection")
    assert mixed.value.code == "mixed_ai_sast_project_scope"


def test_ai_sast_capture_requires_one_complete_compact_project_inventory(tmp_path: Path):
    executable = _fake_endorctl(tmp_path, objects=_ai_sast_objects())
    command = _ai_sast_capture_command(executable)

    summary = capture_and_summarize(
        command,
        artifact_dir=tmp_path / "artifacts",
        projection="ai-sast-selection",
    )

    assert summary["query_completeness"] == "list_all"
    assert summary["selection_summary"]["selected_finding_uuid"] == "finding-a"

    without_list_all = [argument for argument in command if argument != "--list-all"]
    with pytest.raises(ArtifactSummaryError) as incomplete:
        capture_and_summarize(
            without_list_all,
            artifact_dir=tmp_path / "incomplete",
            projection="ai-sast-selection",
        )
    assert incomplete.value.code == "ai_sast_complete_inventory_required"

    bulky = list(command)
    field_mask_index = bulky.index("--field-mask") + 1
    bulky[field_mask_index] += ",spec.finding_metadata"
    with pytest.raises(ArtifactSummaryError) as oversized:
        capture_and_summarize(
            bulky,
            artifact_dir=tmp_path / "bulky",
            projection="ai-sast-selection",
        )
    assert oversized.value.code == "invalid_ai_sast_field_mask"


def _cicd_raw_counts() -> dict[str, int]:
    return {
        "repositories_in_scope": 1,
        "repositories_with_branch_protection": 0,
        "repositories_with_required_reviews": 0,
        "workflows_reviewed": 0,
        "third_party_actions": 0,
        "unpinned_actions": 0,
        "overbroad_permissions": 0,
        "risky_triggers": 0,
        "self_hosted_runners": 0,
        "update_automation_present": 0,
        "endor_critical_findings": 1,
        "endor_high_findings": 3,
        "endor_cicd_findings": 0,
        "endor_scpm_findings": 19,
        "endor_gha_findings": 0,
        "endor_supply_chain_findings": 1,
    }


def test_cicd_score_helper_matches_canonical_contract_formula():
    counts = _cicd_raw_counts()
    helper = score_cicd_posture(
        counts,
        declared_override_types=("endor_critical_finding",),
    )
    canonical = compute_cicd_posture_scores(
        counts,
        declared_override_types=("endor_critical_finding",),
    )

    assert helper["posture_verdict"] == canonical["verdict_band"] == "CRITICAL"
    assert helper["dimension_scores"] == canonical["dimension_scores"]
    assert helper["score_validation"] == {
        "dimension_weights": {key: 1 for key in canonical["dimension_scores"]},
        "formula_version": canonical["formula_version"],
        "overall_score": canonical["overall_score"],
        "recomputed": True,
        "verdict_band": canonical["verdict_band"],
    }
    assert helper["critical_override_required"] is True


def test_cicd_score_cli_emits_one_authoritative_json_record(capsys):
    exit_code = main(
        [
            "score-cicd-posture",
            "--raw-counts-json",
            json.dumps(_cicd_raw_counts(), separators=(",", ":")),
            "--critical-override",
            "endor_critical_finding",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    assert captured.out.count("\n") == 1
    output = json.loads(captured.out)
    assert output["schema_version"] == "endor.cicd-posture-score/v1"
    assert output["score_validation"]["overall_score"] == 45
    assert output["posture_verdict"] == "CRITICAL"


def test_cicd_score_helper_rejects_incomplete_or_impossible_counts():
    counts = _cicd_raw_counts()
    counts.pop("endor_supply_chain_findings")
    with pytest.raises(ArtifactSummaryError) as missing:
        score_cicd_posture(counts)
    assert missing.value.code == "missing_raw_counts"

    counts = _cicd_raw_counts()
    counts["repositories_with_branch_protection"] = 2
    with pytest.raises(ArtifactSummaryError) as impossible:
        score_cicd_posture(counts)
    assert impossible.value.code == "invalid_repository_count"


def test_configuration_scan_projection_keeps_latest_health_and_groups_failures(tmp_path: Path):
    artifact = tmp_path / "scans.json"
    _write_artifact(
        artifact,
        [
            {
                "uuid": "scan-old",
                "meta": {"parent_uuid": "project-1", "create_time": "2026-01-01T00:00:00Z"},
                "spec": {"status": "STATUS_SUCCESS", "refs": ["main"], "stats": {}},
            },
            {
                "uuid": "scan-new",
                "meta": {"parent_uuid": "project-1", "create_time": "2026-02-01T00:00:00Z"},
                "spec": {
                    "status": "STATUS_PARTIAL_SUCCESS",
                    "refs": ["main"],
                    "stats": {"scan_failures": 1, "call_graph_errors": 2},
                },
            },
            {
                "uuid": "scan-healthy",
                "meta": {"parent_uuid": "project-2", "create_time": "2026-02-01T00:00:00Z"},
                "spec": {"status": "STATUS_SUCCESS", "refs": ["main"], "stats": {}},
            },
        ],
    )

    summary = summarize_artifact(artifact, projection="configuration-scans")
    health = summary["configuration_summary"]

    assert health["projects_with_scan_results"] == 2
    assert health["healthy_project_count"] == 1
    assert health["unhealthy_project_count"] == 1
    assert {cohort["signature"] for cohort in health["issue_cohorts"]} == {
        "STATUS_PARTIAL_SUCCESS",
        "scan_failures",
        "call_graph_errors",
    }
    assert health["unhealthy_project_samples"][0]["scan_result_uuid"] == "scan-new"


def test_configuration_selected_projects_projection_builds_safe_batch_filters(tmp_path: Path):
    artifact = tmp_path / "projects.json"
    _write_artifact(
        artifact,
        [
            {
                "uuid": "project-1",
                "meta": {"name": "one", "parent_uuid": "namespace-1"},
                "spec": {"git": {"full_name": "endorlabs/one"}},
            },
            {
                "uuid": "project-2",
                "meta": {"name": "two", "parent_uuid": "namespace-1"},
                "spec": {"git": {"full_name": "endorlabs/two"}},
            },
        ],
    )

    summary = summarize_artifact(
        artifact,
        projection="configuration-selected-projects",
    )["configuration_summary"]

    assert summary["project_count"] == 2
    assert summary["scan_project_filter"] == (
        '(meta.parent_uuid=="project-1" or meta.parent_uuid=="project-2") '
        "and context.type==CONTEXT_TYPE_MAIN"
    )
    assert summary["package_project_filter"] == (
        '(spec.project_uuid=="project-1" or spec.project_uuid=="project-2") '
        "and context.type==CONTEXT_TYPE_MAIN"
    )


def test_configuration_selected_projects_projection_rejects_empty_scope(tmp_path: Path):
    artifact = tmp_path / "projects.json"
    _write_artifact(artifact, [])

    with pytest.raises(ArtifactSummaryError, match="did not resolve any safe project UUIDs"):
        summarize_artifact(
            artifact,
            projection="configuration-selected-projects",
        )


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
