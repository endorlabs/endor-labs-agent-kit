"""Turn a natural-language question into OSS tool calls and an answer (P2).

`QuestionRouter` is the model seam. Two implementations:

* `RuleBasedRouter` — deterministic, **no model**: it extracts a CVE/GHSA/BIT id
  or a package URL from the question, calls the matching OSS tool(s), and
  synthesizes a short answer. This makes the whole "ask -> answer" flow runnable
  and testable locally with no API key.
* `ModelRouter` — the production path: an LLM does tool-calling over the same
  `TOOL_SPECS` / `OssIntelClient`. The runtime (Vertex/Gemini, Anthropic, or an
  Endor-hosted model) is a product + cost decision ("Endor pays the model cost
  per question"), so it is intentionally a stub until that is chosen.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from ..a2a.errors import InvalidParamsError
from .client import OssIntelClient
from .model import SYSTEM_PROMPT, ModelBackend, max_turns
from .models import DependencyVulnerabilities, PackageRisk, VulnerabilityDetail
from .refs import normalize_advisory_id, validate_purl
from .tools import TOOL_SPECS, dispatch_tool

# Un-anchored token scanners (the refs.* validators re-check each match).
_ADVISORY_TOKEN = re.compile(
    r"(CVE-\d{4}-\d{4,}|GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}|BIT-[A-Za-z0-9._-]+)",
    re.IGNORECASE,
)
_PURL_TOKEN = re.compile(r"([a-z][a-z0-9+.-]*://[A-Za-z0-9._:@/+~-]+)")
_RISK_WORDS = re.compile(r"\b(risk|score|health|healthy|safe|trust|quality|maintain)", re.I)


class OssAnswer(BaseModel):
    """The router's structured result — a text answer plus what it looked up."""

    answer: str
    tools_used: list[str] = Field(default_factory=list)
    advisory: VulnerabilityDetail | None = None
    dependency: DependencyVulnerabilities | None = None
    risk: PackageRisk | None = None
    data_gaps: list[str] = Field(default_factory=list)


class QuestionRouter(ABC):
    @abstractmethod
    def answer(self, question: str) -> OssAnswer:
        """Answer one open-source question using the OSS tools."""


class RuleBasedRouter(QuestionRouter):
    """Deterministic router — extract identifiers, call tools, template a reply."""

    def __init__(self, client: OssIntelClient) -> None:
        self._client = client

    def _first_advisory(self, text: str) -> str | None:
        for m in _ADVISORY_TOKEN.finditer(text):
            try:
                return normalize_advisory_id(m.group(1))
            except InvalidParamsError:
                continue
        return None

    def _first_purl(self, text: str) -> str | None:
        for m in _PURL_TOKEN.finditer(text):
            try:
                return validate_purl(m.group(1))
            except InvalidParamsError:
                continue
        return None

    def answer(self, question: str) -> OssAnswer:
        text = question or ""
        advisory_id = self._first_advisory(text)
        purl = self._first_purl(text)

        tools: list[str] = []
        parts: list[str] = []
        result = OssAnswer(answer="")

        if advisory_id:
            detail = self._client.vulnerability_details(advisory_id)
            tools.append("vulnerability_details")
            result.advisory = detail
            parts.append(_describe_advisory(advisory_id, detail))

        if purl:
            dep = self._client.dependency_vulnerabilities(purl)
            tools.append("dependency_vulnerabilities")
            result.dependency = dep
            parts.append(_describe_dependency(dep))
            if _RISK_WORDS.search(text) or not advisory_id:
                risk = self._client.package_risk(purl)
                tools.append("package_risk")
                result.risk = risk
                parts.append(_describe_risk(risk))

        if not advisory_id and not purl:
            result.data_gaps.append("no_package_or_advisory_identified")
            result.answer = (
                "I can answer open-source questions about a specific vulnerability "
                "(e.g. CVE-2021-44228) or a package version "
                "(e.g. mvn://org.apache.logging.log4j:log4j-core@2.14.1). "
                "Please include one of those."
            )
            return result

        result.tools_used = tools
        result.answer = " ".join(parts)
        return result


class ModelRouter(QuestionRouter):
    """LLM tool-calling router — defaults to Gemini, provider-pluggable.

    Runs a bounded agentic loop: the model sees the question + the OSS tool
    specs, requests tool calls, we execute them against the same
    :class:`OssIntelClient`, feed the results back, and return the model's final
    synthesized answer. The model backend is injected, so the provider (Gemini,
    Anthropic, ...) is a config choice, not a code change.
    """

    def __init__(self, client: OssIntelClient, backend: ModelBackend) -> None:
        self._client = client
        self._backend = backend

    def _attach(self, result: OssAnswer, out: object) -> None:
        if isinstance(out, VulnerabilityDetail):
            result.advisory = out
        elif isinstance(out, DependencyVulnerabilities):
            result.dependency = out
        elif isinstance(out, PackageRisk):
            result.risk = out

    def answer(self, question: str) -> OssAnswer:
        transcript: list[dict] = [{"role": "user", "text": question or ""}]
        result = OssAnswer(answer="")
        tools_used: list[str] = []

        for _ in range(max_turns()):
            resp = self._backend.generate(
                system=SYSTEM_PROMPT, transcript=transcript, tools=TOOL_SPECS
            )
            if not resp.tool_calls:
                result.answer = (resp.text or "").strip()
                result.tools_used = tools_used
                return result

            transcript.append({"role": "assistant", "tool_calls": resp.tool_calls})
            for call in resp.tool_calls:
                tools_used.append(call.name)
                try:
                    out = dispatch_tool(self._client, call.name, call.args)
                except Exception as exc:  # noqa: BLE001 - feed the error back to the model
                    transcript.append(
                        {"role": "tool", "name": call.name, "content": {"error": str(exc)}}
                    )
                    continue
                self._attach(result, out)
                transcript.append(
                    {"role": "tool", "name": call.name, "content": out.model_dump(mode="json")}
                )

        # Ran out of turns without a final answer.
        result.tools_used = tools_used
        result.data_gaps.append("model_did_not_finalize")
        if not result.answer:
            result.answer = "I couldn't complete an answer for that question."
        return result


def _describe_advisory(advisory_id: str, d: VulnerabilityDetail | None) -> str:
    if d is None or not d.found:
        return f"{advisory_id}: no details found in Endor's open-source data."
    bits = [advisory_id]
    if d.severity:
        bits.append(str(d.severity))
    if d.cvss_score is not None:
        bits.append(f"CVSS {d.cvss_score}")
    if d.epss_score is not None:
        bits.append(f"EPSS {d.epss_score}")
    head = " — ".join([bits[0], ", ".join(bits[1:])]) if len(bits) > 1 else bits[0]
    return f"{head}. {d.summary or ''}".strip()


def _describe_dependency(d: DependencyVulnerabilities) -> str:
    if not d.found:
        return f"{d.package_name or d.purl}: not found in Endor's open-source data."
    n = len(d.vulnerabilities)
    if n == 0:
        return f"{d.package_name or d.purl} has no known vulnerabilities in Endor's data."
    ids = ", ".join(f"{v.id} ({v.severity})" for v in d.vulnerabilities[:5])
    more = "" if n <= 5 else f" and {n - 5} more"
    return f"{d.package_name or d.purl} has {n} known vulnerabilit{'y' if n == 1 else 'ies'}: {ids}{more}."


def _describe_risk(r: PackageRisk) -> str:
    if not r.found or not r.scores:
        return ""
    top = ", ".join(f"{k}={v}" for k, v in list(r.scores.items())[:4])
    return f"Endor risk scores for {r.package_name or r.purl}: {top}."
