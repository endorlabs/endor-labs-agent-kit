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
from .models import (
    DependencyVulnerabilities,
    PackageRisk,
    UpgradeRecommendations,
    VulnerabilityDetail,
)
from .refs import normalize_advisory_id, validate_purl
from .tools import TOOL_SPECS, dispatch_tool

# Un-anchored token scanners (the refs.* validators re-check each match).
_ADVISORY_TOKEN = re.compile(
    r"(CVE-\d{4}-\d{4,}|GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}|BIT-[A-Za-z0-9._-]+)",
    re.IGNORECASE,
)
_PURL_TOKEN = re.compile(r"([a-z][a-z0-9+.-]*://[A-Za-z0-9._:@/+~-]+)")
_RISK_WORDS = re.compile(r"\b(risk|score|health|healthy|safe|trust|quality|maintain)", re.I)
_UPGRADE_WORDS = re.compile(r"\b(upgrade|update|fix|remediat|patch|bump|resolve|safe version)", re.I)


class OssAnswer(BaseModel):
    """The router's structured result — a text answer plus what it looked up."""

    answer: str
    tools_used: list[str] = Field(default_factory=list)
    advisory: VulnerabilityDetail | None = None
    dependency: DependencyVulnerabilities | None = None
    risk: PackageRisk | None = None
    upgrades: UpgradeRecommendations | None = None
    data_gaps: list[str] = Field(default_factory=list)
    # Discoverability (Google/Veer feedback): a greeting/"what can you do" turn is
    # a welcome; answers carry contextual follow-up suggestions. Both render as GE
    # suggestion chips — clicking one re-asks that question through the router.
    is_welcome: bool = False
    suggestions: list[str] = Field(default_factory=list)
    # Two-or-more advisories asked together -> a side-by-side comparison (Google #3,
    # rendered as a table). Each entry is one looked-up advisory.
    comparison: list[VulnerabilityDetail] = Field(default_factory=list)


# Clickable example queries shown on a greeting ("hello", "hello auri", etc.).
_EXAMPLE_QUERIES = [
    "What is CVE-2021-44228?",
    "What are the vulnerabilities in mvn://org.apache.logging.log4j:log4j-core@2.14.1?",
    "What's the Endor risk score for npm://lodash@4.17.20?",
    "Recommend a safe upgrade for mvn://org.apache.logging.log4j:log4j-core@2.14.1",
]

_WELCOME_TEXT = (
    "Hi, I'm Endor AURI for Developers — I answer open-source security questions "
    "from Endor Labs' public intelligence. I can:\n"
    "• Explain a CVE/GHSA — severity, CVSS, EPSS, and the fix\n"
    "• List the known vulnerabilities for a package version\n"
    "• Give an Endor package risk score\n"
    "• Recommend a safe upgrade that fixes the vulnerabilities\n"
    "Pick an example below, or ask about any CVE (e.g. CVE-2021-44228) or package "
    "(e.g. npm://lodash@4.17.20)."
)


def _followups(advisory_id: str | None, purl: str | None, result: "OssAnswer") -> list[str]:
    """Contextual next-step chips — "compare with X", "recommend an upgrade", "risk
    score" — phrased so clicking one is a valid follow-up question (Google feedback #2)."""

    out: list[str] = []
    if purl:
        dep = result.dependency
        has_vulns = bool(dep and dep.found and dep.vulnerabilities)
        if has_vulns and result.upgrades is None:
            out.append(f"Recommend a safe upgrade for {purl}")
        if result.risk is None:
            out.append(f"What's the Endor risk score for {purl}?")
        if result.upgrades is not None:
            out.append(f"Show the Endor risk score for {purl}")
    if advisory_id and not result.comparison:
        out.append(f"Compare {advisory_id} with CVE-2021-45046")
    seen: set[str] = set()
    uniq: list[str] = []
    for s in out:
        if s and s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq[:3]


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

    def _all_advisories(self, text: str) -> list[str]:
        """Every distinct advisory id in the question, in order (for comparisons)."""
        out: list[str] = []
        for m in _ADVISORY_TOKEN.finditer(text):
            try:
                aid = normalize_advisory_id(m.group(1))
            except InvalidParamsError:
                continue
            if aid not in out:
                out.append(aid)
        return out

    def _first_purl(self, text: str) -> str | None:
        for m in _PURL_TOKEN.finditer(text):
            try:
                return validate_purl(m.group(1))
            except InvalidParamsError:
                continue
        return None

    def answer(self, question: str) -> OssAnswer:
        text = question or ""
        advisories = self._all_advisories(text)
        advisory_id = advisories[0] if advisories else None
        purl = self._first_purl(text)

        tools: list[str] = []
        parts: list[str] = []
        result = OssAnswer(answer="")

        if len(advisories) >= 2:
            # Two or more CVEs/GHSAs: compare them side by side (Google #3).
            details = [(a, self._client.vulnerability_details(a)) for a in advisories]
            tools.append("vulnerability_details")
            result.comparison = [d for _, d in details]
            parts.append(_describe_comparison(details))
        elif advisory_id:
            detail = self._client.vulnerability_details(advisory_id)
            tools.append("vulnerability_details")
            result.advisory = detail
            parts.append(_describe_advisory(advisory_id, detail))

        if purl:
            dep = self._client.dependency_vulnerabilities(purl)
            tools.append("dependency_vulnerabilities")
            result.dependency = dep
            parts.append(_describe_dependency(dep))
            if _UPGRADE_WORDS.search(text) and dep.found and dep.vulnerabilities:
                upgrades = self._client.recommend_upgrades(purl)
                tools.append("recommend_upgrades")
                result.upgrades = upgrades
                parts.append(_describe_upgrades(upgrades))
            if _RISK_WORDS.search(text) or not advisory_id:
                risk = self._client.package_risk(purl)
                tools.append("package_risk")
                result.risk = risk
                parts.append(_describe_risk(risk))

        if not advisory_id and not purl:
            # A greeting or an unrecognized question: introduce the agent and offer
            # clickable example queries (Google feedback #1 — discoverability).
            result.data_gaps.append("no_package_or_advisory_identified")
            result.is_welcome = True
            result.answer = _WELCOME_TEXT
            result.suggestions = list(_EXAMPLE_QUERIES)
            return result

        result.tools_used = tools
        result.answer = " ".join(parts)
        result.suggestions = _followups(advisory_id, purl, result)
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
        elif isinstance(out, UpgradeRecommendations):
            result.upgrades = out

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


def _describe_comparison(details: list[tuple[str, VulnerabilityDetail | None]]) -> str:
    ids = " vs ".join(a for a, _ in details)
    lines = [f"Comparing {ids}:"]
    for aid, d in details:
        lines.append("• " + _describe_advisory(aid, d))
    return "\n".join(lines)


def _describe_dependency(d: DependencyVulnerabilities) -> str:
    if not d.found:
        return f"{d.package_name or d.purl}: not found in Endor's open-source data."
    n = len(d.vulnerabilities)
    if n == 0:
        return f"{d.package_name or d.purl} has no known vulnerabilities in Endor's data."
    ids = ", ".join(f"{v.id} ({v.severity})" for v in d.vulnerabilities[:5])
    more = "" if n <= 5 else f" and {n - 5} more"
    return f"{d.package_name or d.purl} has {n} known vulnerabilit{'y' if n == 1 else 'ies'}: {ids}{more}."


def _describe_upgrades(u: UpgradeRecommendations) -> str:
    if not u.found or not u.options:
        return (
            f"No known upgrade fixes the vulnerabilities in {u.package_name or u.purl}."
        )
    rec = next((o for o in u.options if o.recommended), u.options[-1])
    scope = "all known vulnerabilities" if rec.fixes_all else f"{len(rec.fixes)} of them"
    others = [o.version for o in u.options if o.version != rec.version]
    tail = f" Other options: {', '.join(others)}." if others else ""
    return (
        f"Recommended upgrade: {rec.version} ({rec.jump}), which fixes {scope}.{tail}"
    )


def _risk_summary(scores: dict[str, float]) -> str:
    """Human-readable summary from Endor's metric paths (e.g.
    ``package_version_scorecard.scorecard.score_card.overall_score`` or
    ``...vulnerability_stats.critical_vulnerabilities``). Pull the overall score and
    per-severity vuln counts; never surface the raw metric path names (Google #6)."""

    def find(suffix: str) -> float | None:
        for k, v in scores.items():
            if k.endswith(suffix):
                return v
        return None

    overall = find("overall_score")
    if overall is None:
        for k, v in scores.items():
            if "overall" in k.lower() or k.lower().endswith(".score"):
                overall = v
                break
    counts = [(sev, find(f"{sev}_vulnerabilities")) for sev in ("critical", "high", "medium", "low")]

    bits: list[str] = []
    if overall is not None:
        bits.append(f"overall risk {overall:g}/10")
    present = [(sev, int(n)) for sev, n in counts if n is not None]
    if present:
        bits.append("known vulnerabilities — " + ", ".join(f"{n} {sev}" for sev, n in present))
    if bits:
        return " · ".join(bits)
    # Fallback: cleaned leaf labels for metrics we didn't specifically recognize.
    clean = [(k.split(".")[-1].replace("_", " "), v) for k, v in list(scores.items())[:3]]
    return ", ".join(f"{label} {v:g}" for label, v in clean)


def _describe_risk(r: PackageRisk) -> str:
    if not r.found or not r.scores:
        return ""
    return f"Endor risk for {r.package_name or r.purl}: {_risk_summary(r.scores)}."
