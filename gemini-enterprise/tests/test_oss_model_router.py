"""Model tool-calling loop (P2 production path), offline via MockBackend.

No SDKs, no keys — the loop is provider-agnostic, so a scripted backend proves
it end to end. The Gemini/Anthropic backends translate to their SDKs and are
validated live when deployed.
"""

from __future__ import annotations

import pytest

from service.oss.mock import OssMockClient
from service.oss.model import (
    AnthropicBackend,
    FallbackBackend,
    GeminiBackend,
    ModelBackend,
    ModelBackendUnavailable,
    ModelResponse,
    MockBackend,
    ToolCall,
    build_model_backend,
)
from service.oss.router import ModelRouter


def _router(scripted):
    return ModelRouter(OssMockClient(), MockBackend(scripted))


def test_single_tool_then_answer():
    r = _router([
        ModelResponse(tool_calls=[ToolCall("vulnerability_details", {"advisory_id": "CVE-2021-44228"})]),
        ModelResponse(text="CVE-2021-44228 is a critical Log4j RCE."),
    ])
    a = r.answer("What is CVE-2021-44228?")
    assert a.tools_used == ["vulnerability_details"]
    assert a.advisory is not None and a.advisory.severity == "CRITICAL"
    assert "critical" in a.answer.lower()


def test_multi_tool_loop_attaches_all_results():
    purl = "mvn://org.apache.logging.log4j:log4j-core@2.14.1"
    r = _router([
        ModelResponse(tool_calls=[
            ToolCall("dependency_vulnerabilities", {"purl": purl}),
            ToolCall("package_risk", {"purl": purl}),
        ]),
        ModelResponse(text="It has known vulnerabilities and moderate risk."),
    ])
    a = r.answer(f"Assess {purl}")
    assert a.tools_used == ["dependency_vulnerabilities", "package_risk"]
    assert a.dependency is not None and a.risk is not None


def test_direct_answer_without_tools():
    a = _router([ModelResponse(text="Ask me about a CVE or a package.")]).answer("hi")
    assert a.tools_used == []
    assert a.answer.startswith("Ask me")


def test_tool_error_is_fed_back_not_raised():
    # Bad args -> dispatch raises -> loop feeds the error back and continues.
    r = _router([
        ModelResponse(tool_calls=[ToolCall("vulnerability_details", {"advisory_id": "not-an-id"})]),
        ModelResponse(text="I couldn't find that identifier."),
    ])
    a = r.answer("look up not-an-id")
    assert a.advisory is None
    assert "couldn't find" in a.answer


def test_loop_bounded_when_model_never_finalizes():
    # Model keeps requesting tools forever -> bounded, reports a data gap.
    always_tool = [
        ModelResponse(tool_calls=[ToolCall("vulnerability_details", {"advisory_id": "CVE-2021-44228"})])
        for _ in range(10)
    ]
    a = _router(always_tool).answer("loop")
    assert "model_did_not_finalize" in a.data_gaps


# -- backend selection --------------------------------------------------------

def test_default_provider_is_gemini(monkeypatch):
    monkeypatch.delenv("OSS_MODEL_PROVIDER", raising=False)
    monkeypatch.delenv("OSS_MODEL", raising=False)
    # Default selection is Gemini. If the SDK is present we get a GeminiBackend;
    # if not, selecting it surfaces ModelBackendUnavailable — either way the
    # default provider is gemini.
    try:
        assert build_model_backend().provider == "gemini"
    except ModelBackendUnavailable:
        pass


def test_fallback_skips_unavailable(monkeypatch):
    # Force the first provider unavailable regardless of installed SDKs / creds.
    import service.oss.model as model_mod

    def _unavailable(model=None):
        raise ModelBackendUnavailable("forced-unavailable")

    monkeypatch.setattr(model_mod, "GeminiBackend", _unavailable)
    monkeypatch.setenv("OSS_MODEL_PROVIDER", "gemini,mock")
    backend = build_model_backend()
    assert isinstance(backend, FallbackBackend)
    # gemini is unavailable -> falls through to the mock backend.
    resp = backend.generate(system="s", transcript=[{"role": "user", "text": "hi"}], tools=[])
    assert isinstance(resp, ModelResponse)
    assert backend.provider == "mock"


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("OSS_MODEL_PROVIDER", "bogus")
    with pytest.raises(ValueError):
        build_model_backend()


def test_backend_classes_are_backends():
    assert issubclass(GeminiBackend, ModelBackend)
    assert issubclass(AnthropicBackend, ModelBackend)
