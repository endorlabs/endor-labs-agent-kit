"""Model backends for the OSS agent's tool-calling loop (P2, production path).

Provider-agnostic seam so the agent defaults to **Gemini** but can switch:

* ``GeminiBackend`` (default) — Vertex AI / Google GenAI function calling.
* ``AnthropicBackend`` — the switchable alternative.
* ``MockBackend`` — scripted, for tests (no network, no keys).
* ``FallbackBackend`` — try providers in order; if one is unavailable
  (SDK/config missing), fall through to the next.

Provider SDKs are imported lazily, so importing this module — and the whole test
suite — needs neither ``google-genai`` nor ``anthropic`` installed. Selection is
via env (see ``build_model_backend``). The Gemini/Anthropic backends are the
real production path but are exercised live only when deployed with credentials;
the tool-calling loop itself is covered offline through ``MockBackend``.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

SYSTEM_PROMPT = (
    "You are Endor Labs' open-source intelligence assistant. Answer questions "
    "about open-source vulnerabilities, package risk, and CVEs using ONLY the "
    "provided tools. Cite CVE/GHSA ids and severities. If the tools return no "
    "data, say so plainly; never invent findings. You have no access to any "
    "customer's private projects or findings — open-source data only. Keep "
    "answers concise."
)

# Provider-default model ids (overridable via OSS_MODEL). These are release-QA
# targets, not hard requirements; confirm the exact id available in your project.
_DEFAULT_MODELS = {
    # gemini-3.6-flash verified live on Vertex (v1beta1/global) and AI Studio.
    # gemini-2.5-flash is retired for new accounts, so don't default to it.
    "gemini": "gemini-3.6-flash",
    "anthropic": "claude-sonnet-5",
}
_MAX_TURNS = 4


class ModelBackendUnavailable(RuntimeError):
    """The backend's SDK or configuration is not available; try another."""


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]


@dataclass
class ModelResponse:
    """One model turn: either it wants tool calls, or it has a final answer."""

    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)


class ModelBackend(ABC):
    provider: str = "unknown"
    model: str = ""

    @abstractmethod
    def generate(
        self, *, system: str, transcript: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ModelResponse:
        """One model call over a normalized transcript; return the next turn.

        Transcript entries are one of:
        ``{"role": "user", "text": str}``,
        ``{"role": "assistant", "tool_calls": [ToolCall, ...]}``,
        ``{"role": "tool", "name": str, "content": <json>}``.
        """


class MockBackend(ModelBackend):
    """Return scripted responses in order — deterministic loop testing."""

    provider = "mock"

    def __init__(self, scripted: list[ModelResponse], *, model: str = "mock") -> None:
        self._scripted = list(scripted)
        self.model = model
        self.calls = 0

    def generate(self, *, system, transcript, tools) -> ModelResponse:
        self.calls += 1
        if not self._scripted:
            return ModelResponse(text="(no scripted response)")
        return self._scripted.pop(0)


class FallbackBackend(ModelBackend):
    """Try each backend factory in order until one is available."""

    provider = "fallback"

    def __init__(self, factories: list) -> None:
        self._factories = factories
        self._active: ModelBackend | None = None

    def _backend(self) -> ModelBackend:
        if self._active is not None:
            return self._active
        errors = []
        for make in self._factories:
            try:
                self._active = make()
                self.provider = self._active.provider
                self.model = self._active.model
                return self._active
            except ModelBackendUnavailable as exc:  # noqa: PERF203
                errors.append(str(exc))
        raise ModelBackendUnavailable(
            "No model backend available. Tried: " + "; ".join(errors)
        )

    def generate(self, *, system, transcript, tools) -> ModelResponse:
        return self._backend().generate(system=system, transcript=transcript, tools=tools)


class GeminiBackend(ModelBackend):
    """Google Gemini (Vertex AI or GenAI) function calling — the default.

    Lazy-imports ``google-genai``. Configure Vertex with GOOGLE_GENAI_USE_VERTEXAI=1
    + GOOGLE_CLOUD_PROJECT/LOCATION, or set GEMINI_API_KEY for GenAI. Unverified
    in the test sandbox; validated when deployed with credentials.
    """

    provider = "gemini"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or _DEFAULT_MODELS["gemini"]
        try:
            from google import genai
        except Exception as exc:  # noqa: BLE001
            raise ModelBackendUnavailable(
                "google-genai not installed (pip install google-genai) for the "
                "Gemini backend."
            ) from exc
        try:
            # Reads Vertex/GenAI config from the environment; fails fast if the
            # backend is unconfigured, so a FallbackBackend can move on.
            self._client = genai.Client()
        except Exception as exc:  # noqa: BLE001
            raise ModelBackendUnavailable(
                "Gemini backend is not configured: set GOOGLE_GENAI_USE_VERTEXAI "
                "+ GOOGLE_CLOUD_PROJECT/LOCATION, or GOOGLE_API_KEY."
            ) from exc

    def generate(self, *, system, transcript, tools) -> ModelResponse:
        from google.genai import types

        client = self._client
        declarations = [
            types.FunctionDeclaration(
                name=t["name"], description=t["description"], parameters=t["input_schema"]
            )
            for t in tools
        ]
        contents = _to_gemini_contents(transcript, types)
        resp = client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system,
                tools=[types.Tool(function_declarations=declarations)],
            ),
        )
        calls: list[ToolCall] = []
        text_parts: list[str] = []
        for part in (resp.candidates[0].content.parts if resp.candidates else []):
            fn = getattr(part, "function_call", None)
            if fn is not None:
                calls.append(ToolCall(name=fn.name, args=dict(fn.args or {})))
            elif getattr(part, "text", None):
                text_parts.append(part.text)
        if calls:
            return ModelResponse(tool_calls=calls)
        return ModelResponse(text="".join(text_parts).strip() or None)


class AnthropicBackend(ModelBackend):
    """Anthropic Claude tool-use — the switchable alternative."""

    provider = "anthropic"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or _DEFAULT_MODELS["anthropic"]
        try:
            import anthropic
        except Exception as exc:  # noqa: BLE001
            raise ModelBackendUnavailable(
                "anthropic not installed (pip install anthropic) for the "
                "Anthropic backend."
            ) from exc
        try:
            self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
        except Exception as exc:  # noqa: BLE001
            raise ModelBackendUnavailable(
                "Anthropic backend is not configured: set ANTHROPIC_API_KEY."
            ) from exc

    def generate(self, *, system, transcript, tools) -> ModelResponse:
        client = self._client
        tool_defs = [
            {"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]}
            for t in tools
        ]
        resp = client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system,
            tools=tool_defs,
            messages=_to_anthropic_messages(transcript),
        )
        calls = [
            ToolCall(name=block.name, args=dict(block.input))
            for block in resp.content
            if getattr(block, "type", None) == "tool_use"
        ]
        if calls:
            return ModelResponse(tool_calls=calls)
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        return ModelResponse(text=text.strip() or None)


def _to_gemini_contents(transcript: list[dict[str, Any]], types) -> list:
    contents = []
    for entry in transcript:
        role = entry["role"]
        if role == "user":
            contents.append(types.Content(role="user", parts=[types.Part(text=entry["text"])]))
        elif role == "assistant":
            parts = [
                types.Part(function_call=types.FunctionCall(name=c.name, args=c.args))
                for c in entry["tool_calls"]
            ]
            contents.append(types.Content(role="model", parts=parts))
        elif role == "tool":
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part(function_response=types.FunctionResponse(
                        name=entry["name"], response={"result": entry["content"]}
                    ))],
                )
            )
    return contents


def _to_anthropic_messages(transcript: list[dict[str, Any]]) -> list[dict[str, Any]]:
    import json

    messages: list[dict[str, Any]] = []
    for entry in transcript:
        role = entry["role"]
        if role == "user":
            messages.append({"role": "user", "content": entry["text"]})
        elif role == "assistant":
            messages.append({
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": f"call_{i}", "name": c.name, "input": c.args}
                    for i, c in enumerate(entry["tool_calls"])
                ],
            })
        elif role == "tool":
            messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": entry.get("tool_use_id", "call_0"),
                    "content": json.dumps(entry["content"]),
                }],
            })
    return messages


def _make_backend(provider: str, model: str | None) -> ModelBackend:
    provider = provider.strip().lower()
    if provider == "mock":
        return MockBackend([])
    if provider == "gemini":
        return GeminiBackend(model)
    if provider == "anthropic":
        return AnthropicBackend(model)
    raise ValueError(f"Unknown model provider: {provider!r}")


def build_model_backend() -> ModelBackend:
    """Build the model backend from env.

    * ``OSS_MODEL_PROVIDER`` — one provider, or a comma list for ordered
      fallback. Default ``gemini``.
    * ``OSS_MODEL`` — override the model id.
    """

    providers = [p for p in os.environ.get("OSS_MODEL_PROVIDER", "gemini").split(",") if p.strip()]
    model = os.environ.get("OSS_MODEL")
    if len(providers) == 1:
        return _make_backend(providers[0], model)
    return FallbackBackend([lambda p=p: _make_backend(p, model) for p in providers])


def max_turns() -> int:
    return _MAX_TURNS


def active_model() -> dict[str, object]:
    """Side-effect-free view of the selected router/provider/model (from env).

    Reads configuration only — never constructs an SDK client or a credential —
    so it is safe to call from a health/info endpoint. Contains no secrets.
    """

    router = os.environ.get("OSS_ROUTER", "rule").strip().lower()
    if router != "model":
        return {"router": router}  # deterministic rule-based router, no model

    providers = [
        p.strip() for p in os.environ.get("OSS_MODEL_PROVIDER", "gemini").split(",") if p.strip()
    ] or ["gemini"]
    primary = providers[0]
    info: dict[str, object] = {
        "router": "model",
        "providers": providers,
        "model": os.environ.get("OSS_MODEL") or _DEFAULT_MODELS.get(primary, ""),
    }
    if primary == "gemini":
        vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").strip().lower() in (
            "1", "true", "yes",
        )
        info["transport"] = "vertex" if vertex else "ai_studio"
    return info
