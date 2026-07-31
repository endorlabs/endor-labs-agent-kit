from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validate_release_evidence import _load, main, validate_release_evidence

from conftest import repo_root


SOURCE_COMMIT = "a" * 40


def _catalog() -> dict[str, object]:
    return json.loads((repo_root() / "catalog.json").read_text(encoding="utf-8"))


def _cli_argv(*extra: str) -> list[str]:
    return [
        "validate_release_evidence.py",
        "--source-commit",
        SOURCE_COMMIT,
        "--catalog",
        str(repo_root() / "catalog.json"),
        "--qa-acceptance-env",
        "AGENT_QA_ACCEPTANCE_JSON",
        "--backend-acceptance-env",
        "ENDOR_AGENT_BACKEND_ACCEPTANCE_JSON",
        *extra,
    ]


def _valid_evidence(catalog: dict[str, object]) -> tuple[dict, dict]:
    agents = catalog["agents"]
    qa = {
        "status": "pass",
        "publish_ready": True,
        "coordinates": {"source_commits": {"treatment": SOURCE_COMMIT}},
    }
    backend = {
        "schema_version": "1",
        "status": "pass",
        "catalog_schema_version": 2,
        "agent_api_transport": "endorctl agent api",
        "canonical_agent_ids": [item["id"] for item in agents],
        "legacy_aliases": {
            alias: item["id"]
            for item in agents
            for alias in item.get("legacy_ids", [])
        },
        "audit_log_correlation": {
            "status": "pass",
            "observed_fields": [
                "request_id",
                "actor_type",
                "canonical_agent_id",
                "on_behalf_of",
            ],
            "canonical_agent_samples": len(agents),
        },
    }
    return qa, backend


def test_release_evidence_binds_qa_backend_aliases_and_audit_log_to_catalog() -> None:
    source_commit = "a" * 40
    catalog = json.loads((repo_root() / "catalog.json").read_text(encoding="utf-8"))
    canonical = [item["id"] for item in catalog["agents"]]
    aliases = {
        alias: item["id"]
        for item in catalog["agents"]
        for alias in item.get("legacy_ids", [])
    }
    qa = {
        "status": "pass",
        "publish_ready": True,
        "coordinates": {"source_commits": {"treatment": source_commit}},
    }
    backend = {
        "schema_version": "1",
        "status": "pass",
        "catalog_schema_version": 2,
        "agent_api_transport": "endorctl agent api",
        "canonical_agent_ids": canonical,
        "legacy_aliases": aliases,
        "audit_log_correlation": {
            "status": "pass",
            "observed_fields": [
                "request_id",
                "actor_type",
                "canonical_agent_id",
                "on_behalf_of",
            ],
            "canonical_agent_samples": 11,
        },
    }

    assert validate_release_evidence(
        source_commit=source_commit,
        qa=qa,
        backend=backend,
        catalog=catalog,
    ) == []

    backend["legacy_aliases"] = {}
    assert "backend legacy alias resolution must exactly match catalog aliases" in validate_release_evidence(
        source_commit=source_commit,
        qa=qa,
        backend=backend,
        catalog=catalog,
    )


def test_release_evidence_requires_exact_full_source_commit() -> None:
    catalog = json.loads((repo_root() / "catalog.json").read_text(encoding="utf-8"))
    qa = {
        "status": "pass",
        "publish_ready": True,
        "coordinates": {"source_commits": {"treatment": "a" * 39}},
    }

    errors = validate_release_evidence(
        source_commit="a" * 40,
        qa=qa,
        backend={},
        catalog=catalog,
    )

    assert "QA treatment and publishing source commits must be full immutable Git SHAs" in errors


def test_load_reports_missing_evidence_when_environment_variable_is_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AGENT_QA_ACCEPTANCE_JSON", raising=False)

    # An unset variable must not fall through to a file read; that raised an
    # AttributeError instead of the actionable validation error.
    with pytest.raises(ValueError, match="QA acceptance is missing or invalid"):
        _load(None, "AGENT_QA_ACCEPTANCE_JSON", "QA acceptance")


@pytest.mark.parametrize("raw", ["", "   \n", "not json", "{"])
def test_load_reports_missing_evidence_for_blank_or_unparseable_variables(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv("BACKEND_EVIDENCE", raw)

    with pytest.raises(ValueError, match="backend acceptance is missing or invalid"):
        _load(None, "BACKEND_EVIDENCE", "backend acceptance")


def test_load_rejects_non_object_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BACKEND_EVIDENCE", "[1, 2]")

    with pytest.raises(ValueError, match="backend acceptance must be an object"):
        _load(None, "BACKEND_EVIDENCE", "backend acceptance")


def test_load_ignores_a_populated_file_when_an_environment_variable_is_selected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps({"from": "file"}), encoding="utf-8")
    monkeypatch.setenv("QA_EVIDENCE", json.dumps({"from": "env"}))

    assert _load(path, "QA_EVIDENCE", "QA acceptance") == {"from": "env"}


def test_load_reads_a_file_when_no_environment_variable_is_selected(
    tmp_path: Path,
) -> None:
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps({"from": "file"}), encoding="utf-8")

    assert _load(path, None, "catalog") == {"from": "file"}


def test_load_reports_missing_evidence_for_unreadable_or_absent_sources(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="catalog is missing or invalid"):
        _load(tmp_path / "absent.json", None, "catalog")

    with pytest.raises(ValueError, match="catalog is missing or invalid"):
        _load(None, None, "catalog")


def test_cli_reports_unset_evidence_variable_without_a_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("AGENT_QA_ACCEPTANCE_JSON", raising=False)
    monkeypatch.delenv("ENDOR_AGENT_BACKEND_ACCEPTANCE_JSON", raising=False)
    monkeypatch.setattr("sys.argv", _cli_argv())

    assert main() == 1
    captured = capsys.readouterr()
    assert "ERROR: QA acceptance is missing or invalid" in captured.out
    assert "Traceback" not in captured.out + captured.err


def test_cli_passes_and_fails_on_configured_evidence(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    catalog = _catalog()
    qa, backend = _valid_evidence(catalog)
    monkeypatch.setenv("AGENT_QA_ACCEPTANCE_JSON", json.dumps(qa))
    monkeypatch.setenv("ENDOR_AGENT_BACKEND_ACCEPTANCE_JSON", json.dumps(backend))
    monkeypatch.setattr("sys.argv", _cli_argv())

    assert main() == 0
    assert "OK: QA and backend release evidence" in capsys.readouterr().out

    backend["catalog_schema_version"] = 1
    monkeypatch.setenv("ENDOR_AGENT_BACKEND_ACCEPTANCE_JSON", json.dumps(backend))

    assert main() == 1
    assert "ERROR: backend must accept catalog schema version 2" in capsys.readouterr().out


def test_cli_requires_exactly_one_evidence_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", _cli_argv("--qa-acceptance", "benchmark.json"))

    with pytest.raises(SystemExit) as raised:
        main()

    assert raised.value.code == 2


def test_release_evidence_rejects_a_catalog_without_agent_objects() -> None:
    qa, backend = _valid_evidence(_catalog())

    assert validate_release_evidence(
        source_commit=SOURCE_COMMIT,
        qa=qa,
        backend=backend,
        catalog={"agents": ["dependency-reviewer"]},
    ) == ["catalog agents must be an array of objects"]


def test_release_evidence_requires_the_full_canonical_agent_set() -> None:
    catalog = _catalog()
    qa, backend = _valid_evidence(catalog)
    trimmed = {"agents": catalog["agents"][:-1]}

    errors = validate_release_evidence(
        source_commit=SOURCE_COMMIT,
        qa=qa,
        backend=backend,
        catalog=trimmed,
    )

    assert "catalog must contain exactly 11 canonical agents" in errors
    assert "backend canonical agent ids must exactly match catalog ids" in errors


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda qa, backend: qa.update(status="fail"),
            "QA benchmark acceptance must pass",
        ),
        (
            lambda qa, backend: qa.update(publish_ready=False),
            "QA benchmark acceptance must pass",
        ),
        (
            lambda qa, backend: qa.pop("coordinates"),
            "QA treatment and publishing source commits must be full immutable Git SHAs",
        ),
        (
            lambda qa, backend: qa.update(
                coordinates={"source_commits": {"treatment": "b" * 40}}
            ),
            "QA treatment commit must match the publishing source commit",
        ),
        (
            lambda qa, backend: backend.update(schema_version="2"),
            "backend acceptance must use schema_version 1",
        ),
        (
            lambda qa, backend: backend.update(status="fail"),
            "backend acceptance must pass",
        ),
        (
            lambda qa, backend: backend.update(catalog_schema_version=1),
            "backend must accept catalog schema version 2",
        ),
        (
            lambda qa, backend: backend.update(agent_api_transport="endorctl api"),
            "backend evidence must cover endorctl agent api",
        ),
        (
            lambda qa, backend: backend.update(canonical_agent_ids=["unknown"]),
            "backend canonical agent ids must exactly match catalog ids",
        ),
        (
            lambda qa, backend: backend.update(
                audit_log_correlation={"status": "fail"}
            ),
            "backend audit-log correlation must pass",
        ),
        (
            lambda qa, backend: backend["audit_log_correlation"].update(
                observed_fields=["request_id"]
            ),
            "backend audit-log correlation is missing required fields",
        ),
        (
            lambda qa, backend: backend["audit_log_correlation"].update(
                canonical_agent_samples=1
            ),
            "backend audit-log evidence must sample every canonical agent",
        ),
    ],
)
def test_release_evidence_reports_every_unsatisfied_claim(mutate, expected: str) -> None:
    catalog = _catalog()
    qa, backend = _valid_evidence(catalog)
    mutate(qa, backend)

    errors = validate_release_evidence(
        source_commit=SOURCE_COMMIT,
        qa=qa,
        backend=backend,
        catalog=catalog,
    )

    assert expected in errors
