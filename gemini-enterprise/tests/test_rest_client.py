"""Offline contract tests for the direct Endor REST client.

Uses httpx.MockTransport with canned responses shaped exactly like the live
Endor API (verified against a real tenant), so CI needs no network or secrets.
"""

from __future__ import annotations

import httpx
import pytest

from service.a2a.errors import (
    AuthenticationError,
    InvalidParamsError,
    NamespaceNotAuthorizedError,
)
from service.a2a.models import AnalysisRequest, RecommendedAction, Severity
from service.endor_client.auth import EndorCredentials, TokenProvider
from service.endor_client.rest import RestEndorSCAClient

NS = "demo-tenant"
PROJECT_UUID = "0123456789abcdef01234567"  # 24-char hex, format-valid


def _finding(uuid, level, purl, *, proposed=None, patch=None, tags=None, aliases=None, primary=None):
    return {
        "uuid": uuid,
        "spec": {
            "level": level,
            "target_dependency_package_name": purl,
            "finding_tags": tags or [],
            "proposed_version": proposed,
            "fixing_patch": patch,
            "finding_metadata": {
                "vulnerability": {
                    "meta": {"name": primary},
                    "spec": {"aliases": aliases or []},
                }
            },
        },
    }


_FINDINGS = [
    _finding(
        "f1", "FINDING_LEVEL_HIGH", "mvn://org.assertj:assertj-core@3.24.2",
        proposed="3.27.7", tags=["FINDING_TAGS_FIX_AVAILABLE"],
        aliases=["GHSA-rqfh-9r24-8c9r", "CVE-2026-24400"], primary="GHSA-rqfh-9r24-8c9r",
    ),
    _finding(
        "f2", "FINDING_LEVEL_MEDIUM", "mvn://org.springframework:spring-context@6.1.1",
        proposed="6.1.14", tags=["FINDING_TAGS_FIX_AVAILABLE"],
        aliases=["CVE-2024-38820"], primary="GHSA-4gc7-5j7h-4qph",
    ),
    _finding(
        "f3", "FINDING_LEVEL_LOW", "mvn://com.example:low-level@1.0.0",
        aliases=["CVE-2020-0002"], primary="CVE-2020-0002",
    ),
    _finding(
        "f4", "FINDING_LEVEL_INFO", "mvn://com.example:informational@1.0.0",
    ),
    _finding(
        "f5", "FINDING_LEVEL_CRITICAL", "mvn://com.example:patched@1.0.0",
        patch={"uuid": "patch-1"}, aliases=["CVE-2021-1234"], primary="CVE-2021-1234",
    ),
    _finding(
        "f6", "FINDING_LEVEL_HIGH", "mvn://com.example:no-fix@1.0.0",
        aliases=["CVE-2020-0001"], primary="GHSA-aaaa-bbbb-cccc",
    ),
]


def _list(objects):
    return {"list": {"objects": objects, "response": {"next_page_id": ""}}}


class _Handler:
    def __init__(self, *, project_exists=True, findings_status=200):
        self.requests: list[httpx.Request] = []
        self.project_exists = project_exists
        self.findings_status = findings_status

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/v1/auth/api-key":
            return httpx.Response(
                200, json={"token": "fake.jwt.token", "expirationTime": "2999-01-01T00:00:00Z"}
            )
        if path.endswith("/projects"):
            objects = [{"uuid": PROJECT_UUID}] if self.project_exists else []
            return httpx.Response(200, json=_list(objects))
        if path.endswith("/findings"):
            if self.findings_status != 200:
                return httpx.Response(self.findings_status, json={"message": "nope"})
            return httpx.Response(200, json=_list(_FINDINGS))
        return httpx.Response(404, json={"message": f"unexpected {path}"})


def _client(handler: _Handler) -> RestEndorSCAClient:
    http = httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.test")
    creds = EndorCredentials(key="k", secret="s", namespace=NS, base_url="https://api.test")
    return RestEndorSCAClient(
        token_provider=TokenProvider(creds, client=http),
        default_namespace=NS,
        http_client=http,
    )


def test_maps_findings_from_repo():
    handler = _Handler()
    client = _client(handler)
    result = client.get_sca_analysis(
        AnalysisRequest(repo_full_name="example-org/demo-service")
    )

    assert result.namespace == NS
    assert result.data_gaps == []
    # v1 high-severity scope: f2 (MEDIUM), f3 (LOW), f4 (INFO) are dropped;
    # f1 (HIGH), f5 (CRITICAL), f6 (HIGH) remain.
    assert len(result.findings) == 3

    by_pkg = {f.package: f for f in result.findings}
    assert "org.springframework:spring-context" not in by_pkg
    assert "com.example:low-level" not in by_pkg
    assert "com.example:informational" not in by_pkg

    assertj = by_pkg["org.assertj:assertj-core"]
    assert assertj.current_version == "3.24.2"
    assert assertj.severity is Severity.P1
    assert assertj.recommended_action is RecommendedAction.UPGRADE
    assert assertj.target_version == "3.27.7"
    # CVE ordered before GHSA.
    assert assertj.vulnerability_ids[0] == "CVE-2026-24400"

    nofix = by_pkg["com.example:no-fix"]
    assert nofix.severity is Severity.P1
    assert nofix.recommended_action is RecommendedAction.NO_FIX_AVAILABLE
    assert nofix.target_version is None
    # Primary GHSA is included even though only the CVE alias was listed.
    assert "GHSA-aaaa-bbbb-cccc" in nofix.vulnerability_ids

    patched = by_pkg["com.example:patched"]
    assert patched.severity is Severity.P0
    assert patched.patch_available is True

    # Most severe first.
    assert result.findings[0].severity is Severity.P0


def test_severity_filter_builds_level_clause():
    handler = _Handler()
    client = _client(handler)
    client.get_sca_analysis(
        AnalysisRequest(repo_full_name="acme/known", severity_filter=[Severity.P0])
    )
    findings_req = next(r for r in handler.requests if r.url.path.endswith("/findings"))
    filt = findings_req.url.params["list_parameters.filter"]
    # P0 means CRITICAL only: a "critical" request must not pull HIGH findings,
    # and vice versa (the parser maps "critical" -> P0 and "high" -> P1).
    assert "FINDING_LEVEL_CRITICAL" in filt
    assert "FINDING_LEVEL_HIGH" not in filt
    assert "FINDING_LEVEL_MEDIUM" not in filt


def test_p1_severity_filter_requests_high_levels():
    handler = _Handler()
    client = _client(handler)
    client.get_sca_analysis(
        AnalysisRequest(repo_full_name="acme/known", severity_filter=[Severity.P1])
    )
    findings_req = next(r for r in handler.requests if r.url.path.endswith("/findings"))
    filt = findings_req.url.params["list_parameters.filter"]
    assert "FINDING_LEVEL_HIGH" in filt
    assert "FINDING_LEVEL_CRITICAL" not in filt
    assert "FINDING_LEVEL_MEDIUM" not in filt and "FINDING_LEVEL_LOW" not in filt


def test_project_not_found_is_data_gap():
    client = _client(_Handler(project_exists=False))
    result = client.get_sca_analysis(AnalysisRequest(repo_full_name="acme/ghost"))
    assert result.findings == []
    assert any("project_not_found" in g for g in result.data_gaps)


def test_project_id_skips_resolution():
    handler = _Handler()
    client = _client(handler)
    client.get_sca_analysis(AnalysisRequest(project_id=PROJECT_UUID))
    # No project lookup needed when a project_id is supplied.
    assert not any(r.url.path.endswith("/projects") for r in handler.requests)
    assert any(r.url.path.endswith("/findings") for r in handler.requests)


def test_findings_401_raises_auth_error():
    client = _client(_Handler(findings_status=401))
    with pytest.raises(AuthenticationError):
        client.get_sca_analysis(AnalysisRequest(project_id=PROJECT_UUID))


def test_findings_403_raises_namespace_error():
    client = _client(_Handler(findings_status=403))
    with pytest.raises(NamespaceNotAuthorizedError):
        client.get_sca_analysis(AnalysisRequest(project_id=PROJECT_UUID))


def test_client_rejects_malicious_namespace_directly():
    # Defense in depth: the client validates even when called directly.
    client = _client(_Handler())
    with pytest.raises(InvalidParamsError):
        client.get_sca_analysis(
            AnalysisRequest(project_id=PROJECT_UUID, namespace="evil/../ns")
        )
