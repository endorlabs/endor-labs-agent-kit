"""Security: values that reach Endor URL paths / filters must be validated.

Covers path injection (namespace -> URL path) and filter injection
(repo/project -> filter literal) at the parser boundary, plus the validators.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from service.a2a import errors
from service.a2a.errors import InvalidParamsError
from service.a2a.validation import (
    validate_namespace,
    validate_project_id,
    validate_repo_full_name,
)
from service.app import app

client = TestClient(app)


def _send(text: str, metadata: dict | None = None) -> dict:
    message: dict = {"role": "user", "parts": [{"kind": "text", "text": text}]}
    if metadata is not None:
        message["metadata"] = metadata
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "message/send",
        "params": {"message": message},
    }
    return client.post("/", json=body).json()


@pytest.mark.parametrize(
    "namespace",
    [
        "../../etc/passwd",   # path traversal
        "other-tenant/findings",  # cross-namespace path
        "a b",                # whitespace
        'ram"',               # quote
        "ns%2f..",            # encoded slash
        "..",
        ".",
    ],
)
def test_path_injection_namespace_is_rejected(namespace):
    result = _send("scan acme/service-api", {"namespace": namespace})
    assert "result" not in result
    assert result["error"]["code"] == errors.INVALID_PARAMS


@pytest.mark.parametrize(
    "project_id",
    [
        'x" or "1"=="1',              # filter break-out
        "../x",
        "NOTHEXVALUE000000000000",
        "6a84f3b9be4a8c1c15261e0",    # 23 chars (too short)
    ],
)
def test_filter_injection_project_id_is_rejected(project_id):
    result = _send("check my project", {"project_id": project_id})
    assert "result" not in result
    assert result["error"]["code"] == errors.INVALID_PARAMS


def test_quote_in_text_repo_does_not_leak_into_filter():
    # A quote in free text simply isn't captured as part of owner/repo.
    result = _send('scan acme/service-api" or spec.foo=="x')
    assert "result" in result
    data = next(
        p for p in result["result"]["artifacts"][0]["parts"] if p["kind"] == "data"
    )["data"]
    assert data["namespace"] == "acme/service-api"


def test_valid_dotted_namespace_accepted():
    result = _send("scan acme/service-api", {"namespace": "tenant.child-1"})
    assert "result" in result


def test_validators_units():
    for bad in ["a/b", "..", ".", "a b", 'a"b', "a%2fb"]:
        with pytest.raises(InvalidParamsError):
            validate_namespace(bad)
    assert validate_namespace("tenant-a.child_1") == "tenant-a.child_1"

    for bad in ["owner", 'o/r" or 1', "a/../b", "o/r/../x"]:
        with pytest.raises(InvalidParamsError):
            validate_repo_full_name(bad)
    assert validate_repo_full_name("owner/repo.name-1") == "owner/repo.name-1"

    for bad in ["proj-123", "../x", "ABCDEF0123456789ABCDEF01"]:  # non-hex/upper
        with pytest.raises(InvalidParamsError):
            validate_project_id(bad)
    assert validate_project_id("0123456789abcdef01234567") == "0123456789abcdef01234567"
