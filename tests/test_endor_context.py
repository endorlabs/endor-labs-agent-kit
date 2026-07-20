from __future__ import annotations

import hashlib
import json
from pathlib import Path

from conftest import repo_root
from endor_agent_kit.cli import main
from endor_agent_kit.endor_context import (
    DEFAULT_CONTEXT_PATH,
    DEFAULT_OPENAPI_SPEC_PATH,
    build_endor_context_payload,
    refresh_endor_context,
    verify_endor_context,
)


def _fetch_bytes(_: str) -> bytes:
    return b'{"swagger":"2.0"}'


def _fetch_json(_: str) -> dict[str, object]:
    return {
        "ClientVersion": "v1.2.3",
        "Service": {
            "Version": "v1.2.3",
            "SHA": "a" * 40,
        },
    }


def _fetch_status(url: str) -> dict[str, object]:
    return {"status": 200, "final_url": url}


def test_committed_endor_context_validates_without_network():
    report = verify_endor_context(repo_root() / DEFAULT_CONTEXT_PATH)

    assert report.errors == ()


def test_verify_endor_context_cli_round_trip(capsys):
    status = main([
        "verify-endor-context",
        "--context-file",
        str(repo_root() / DEFAULT_CONTEXT_PATH),
    ])
    output = capsys.readouterr().out

    assert status == 0
    assert "OK:" in output


def test_build_payload_records_openapi_digest_and_docs():
    payload = build_endor_context_payload(
        checked_at="2026-06-07",
        fetch_bytes=_fetch_bytes,
        fetch_json=_fetch_json,
        fetch_url_status=_fetch_status,
    )

    assert payload["checked_at"] == "2026-06-07"
    assert payload["openapi"]["sha256"] == hashlib.sha256(_fetch_bytes("")).hexdigest()
    assert payload["openapi"]["failure_mode"] == "blocking"
    assert payload["meta_version"]["failure_mode"] == "warning"
    assert payload["docs"]
    assert {doc["status"] for doc in payload["docs"]} == {200}


def test_refresh_endor_context_writes_deterministic_json(tmp_path):
    path = tmp_path / "source" / "endor-context" / "provenance.json"

    payload = refresh_endor_context(
        path,
        checked_at="2026-06-07",
        fetch_bytes=_fetch_bytes,
        fetch_json=_fetch_json,
        fetch_url_status=_fetch_status,
    )

    assert json.loads(path.read_text(encoding="utf-8")) == payload
    assert (path.parent / DEFAULT_OPENAPI_SPEC_PATH.name).read_bytes() == _fetch_bytes("")


def test_verify_endor_context_checks_local_openapi_spec(tmp_path):
    path = _write_payload(tmp_path)
    spec_path = tmp_path / "openapiv2.swagger.json"
    spec_path.write_bytes(b"changed")

    report = verify_endor_context(path, spec_path=spec_path)

    assert any("sha256 does not match provenance" in error for error in report.errors)


def test_upstream_openapi_drift_is_blocking(tmp_path):
    path = _write_payload(tmp_path)

    report = verify_endor_context(
        path,
        upstream=True,
        fetch_bytes=lambda _: b"changed",
        fetch_json=_fetch_json,
        fetch_url_status=_fetch_status,
    )

    assert any("openapi sha256 drift" in error for error in report.errors)


def test_upstream_docs_redirect_is_blocking(tmp_path):
    path = _write_payload(tmp_path)

    def redirected(url: str) -> dict[str, object]:
        return {"status": 200, "final_url": f"{url}/"}

    report = verify_endor_context(
        path,
        upstream=True,
        fetch_bytes=_fetch_bytes,
        fetch_json=_fetch_json,
        fetch_url_status=redirected,
    )

    assert any("docs canonical URL drift" in error for error in report.errors)


def test_upstream_meta_version_drift_is_warning_only(tmp_path):
    path = _write_payload(tmp_path)

    def newer_meta(_: str) -> dict[str, object]:
        return {
            "ClientVersion": "v1.2.4",
            "Service": {
                "Version": "v1.2.4",
                "SHA": "b" * 40,
            },
        }

    report = verify_endor_context(
        path,
        upstream=True,
        fetch_bytes=_fetch_bytes,
        fetch_json=newer_meta,
        fetch_url_status=_fetch_status,
    )

    assert report.errors == ()
    assert any("Endor client version drift" in warning for warning in report.warnings)


def _write_payload(tmp_path: Path) -> Path:
    path = tmp_path / "provenance.json"
    payload = build_endor_context_payload(
        checked_at="2026-06-07",
        fetch_bytes=_fetch_bytes,
        fetch_json=_fetch_json,
        fetch_url_status=_fetch_status,
    )
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
