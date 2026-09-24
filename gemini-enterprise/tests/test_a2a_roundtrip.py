"""Build-order step 2 DoD (§12): a local JSON-RPC round-trip returns a
well-formed result matching the §10 contract from mocked findings.
"""

from __future__ import annotations

import itertools

import pytest
from fastapi.testclient import TestClient

from service.a2a import errors
from service.app import app

client = TestClient(app)

_ids = itertools.count(1)


def _send(text: str, *, metadata: dict | None = None) -> dict:
    message: dict = {"role": "user", "parts": [{"kind": "text", "text": text}]}
    if metadata is not None:
        message["metadata"] = metadata
    body = {
        "jsonrpc": "2.0",
        "id": next(_ids),
        "method": "message/send",
        "params": {"message": message},
    }
    response = client.post("/", json=body)
    assert response.status_code == 200
    return response.json()


def _data_part(result: dict) -> dict:
    task = result["result"]
    artifact = task["artifacts"][0]
    for part in artifact["parts"]:
        if part["kind"] == "data":
            return part["data"]
    raise AssertionError("no data part in artifact")


def test_agent_card_served():
    response = client.get("/.well-known/agent-card.json")
    assert response.status_code == 200
    card = response.json()
    assert card["name"] == "Endor Labs SCA Remediation"
    assert card["skills"][0]["id"] == "sca_remediation_readonly"


def test_healthz():
    assert client.get("/healthz").json() == {"status": "ok"}


def test_full_analysis_round_trip():
    result = _send("Find open source vulnerabilities in acme/service-api")
    task = result["result"]

    assert "error" not in result
    assert task["kind"] == "task"
    assert task["status"]["state"] == "completed"

    data = _data_part(result)
    assert data["status"] == "completed"
    assert data["namespace"] == "acme/service-api"
    assert data["findings_summary"] == {"p0_count": 2, "p1_count": 5}
    assert len(data["findings"]) == 7
    assert data["data_gaps"] == []

    # Every finding conforms to the §10 finding shape.
    for finding in data["findings"]:
        assert set(finding) >= {
            "package",
            "current_version",
            "vulnerability_ids",
            "severity",
            "recommended_action",
            "target_version",
            "breaking_change_risk",
            "patch_available",
        }
        assert finding["severity"] in {"P0", "P1"}


def test_p0_only_filter():
    result = _send("Check acme/service-api for P0 SCA findings I can remediate")
    data = _data_part(result)
    assert data["findings_summary"] == {"p0_count": 2, "p1_count": 0}
    assert all(f["severity"] == "P0" for f in data["findings"])


def test_repo_url_and_metadata_namespace():
    result = _send(
        "What's the safest upgrade path for https://github.com/acme/service-api ?",
        metadata={"namespace": "acme-corp.prod"},
    )
    data = _data_part(result)
    # Explicit namespace metadata wins over the derived repo full name.
    assert data["namespace"] == "acme-corp.prod"


def test_ambiguous_request_is_rpc_error():
    result = _send("Please look for some vulnerabilities for me")
    assert "result" not in result
    assert result["error"]["code"] == errors.AMBIGUOUS_TARGET


def test_auth_failure_is_rpc_error():
    result = _send("Check acme/needs-auth for P0 findings")
    assert result["error"]["code"] == errors.AUTH_FAILED


def test_namespace_not_authorized_is_rpc_error():
    result = _send("Check acme/forbidden-namespace for findings")
    assert result["error"]["code"] == errors.NAMESPACE_NOT_AUTHORIZED


def test_empty_but_resolved_completes():
    result = _send("Check acme/empty for findings")
    data = _data_part(result)
    assert data["status"] == "completed"
    assert data["findings_summary"] == {"p0_count": 0, "p1_count": 0}
    assert data["findings"] == []


def test_partial_evidence_reports_data_gap():
    result = _send("Check acme/partial for findings")
    task = result["result"]
    data = _data_part(result)
    assert data["status"] == "data_gap"
    assert data["data_gaps"]
    # A data gap still returns partial results and completes the task.
    assert task["status"]["state"] == "completed"


def test_unknown_method_is_rpc_error():
    body = {"jsonrpc": "2.0", "id": 99, "method": "tasks/cancel", "params": {}}
    result = client.post("/", json=body).json()
    assert result["error"]["code"] == errors.METHOD_NOT_FOUND


def test_non_jsonrpc_payload_rejected():
    result = client.post("/", json={"hello": "world"}).json()
    assert result["error"]["code"] == errors.INVALID_REQUEST


@pytest.mark.parametrize("bad", ["not json at all", "{"])
def test_malformed_body_is_parse_error(bad: str):
    result = client.post(
        "/", content=bad, headers={"content-type": "application/json"}
    ).json()
    assert result["error"]["code"] == errors.PARSE_ERROR


def test_type_discriminator_part_is_parsed():
    # Some A2A clients/versions send parts keyed by `type` instead of `kind`.
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": "Find vulns in acme/service-api"}],
            }
        },
    }
    result = client.post("/", json=body).json()
    assert "result" in result
    assert _data_part(result)["namespace"] == "acme/service-api"


def test_tasks_get_returns_completed_task_and_misses_cleanly():
    sent = _send("Find vulns in acme/service-api")
    task_id = sent["result"]["id"]

    got = client.post(
        "/",
        json={"jsonrpc": "2.0", "id": 1, "method": "tasks/get", "params": {"id": task_id}},
    ).json()
    assert got["result"]["id"] == task_id

    miss = client.post(
        "/",
        json={"jsonrpc": "2.0", "id": 2, "method": "tasks/get", "params": {"id": "nope"}},
    ).json()
    assert miss["error"]["code"] == errors.TASK_NOT_FOUND
