"""Endor Open Source Intelligence — Google ADK agent (customer-hosted MVP).

This is the customer-hosted shape (AD-1): a Google ADK agent whose managed
runtime (Vertex AI Agent Engine) provides sessions, resume, and per-customer
isolation — so we do not build those ourselves. It reuses the exact same OSS
tools as the A2A app; only the shell differs.

Run locally (chat UI with managed sessions):

    pip install google-adk
    cd gemini-enterprise/adk && adk web            # or: adk run endor_oss

Use real Endor OSS data instead of the offline mock:

    OSS_CLIENT=rest ENDOR_ALLOW_ENDORCTL_CONFIG=1 adk web

Model / Vertex config comes from the environment (GOOGLE_GENAI_USE_VERTEXAI,
GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION — or GOOGLE_API_KEY for AI Studio).
The class/import path may vary slightly across google-adk versions.
"""

from __future__ import annotations

import logging
import os

from google.adk.agents import Agent

logger = logging.getLogger(__name__)

from service.oss.adk_tools import (
    dependency_vulnerabilities,
    package_risk,
    vulnerability_details,
)
from service.oss.model import SYSTEM_PROMPT


def _select_model():
    """Pick the model provider from env — Gemini by default, or Anthropic.

    Set ADK_MODEL_PROVIDER=anthropic (or just have ANTHROPIC_API_KEY set) to run
    on Claude via LiteLLM — no Google/Vertex needed. Override the exact model id
    with ADK_MODEL. Otherwise default to Gemini (OSS_MODEL, gemini-3.6-flash).
    """

    provider = os.environ.get("ADK_MODEL_PROVIDER", "").strip().lower()
    use_anthropic = provider == "anthropic" or (
        not provider and os.environ.get("ANTHROPIC_API_KEY")
    )
    if use_anthropic:
        from google.adk.models.lite_llm import LiteLlm  # needs: pip install litellm

        return LiteLlm(model=os.environ.get("ADK_MODEL", "anthropic/claude-sonnet-5"))
    return os.environ.get("OSS_MODEL", "gemini-3.6-flash")


_MODEL = _select_model()


def describe_model() -> dict[str, str]:
    """The provider/model this ADK agent actually resolved to (what adk web runs).

    Inspects the resolved model object, so it reflects reality, not just env.
    """

    if isinstance(_MODEL, str):
        vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").strip().lower() in (
            "1", "true", "yes",
        )
        return {"provider": "gemini", "model": _MODEL,
                "transport": "vertex" if vertex else "ai_studio"}
    return {"provider": "anthropic", "model": getattr(_MODEL, "model", str(_MODEL))}


def agent_info() -> dict[str, object]:
    """Report which model/provider this agent runs on, and what it can do.

    Use this to answer meta questions such as "what model are you running?",
    "which provider is this?", or "what can you do?".
    """

    return {
        "agent": "Endor Open Source Intelligence",
        "model": describe_model(),
        "tools": [
            "vulnerability_details",
            "dependency_vulnerabilities",
            "package_risk",
        ],
        "data_scope": "public open-source data only; no customer data, no login",
    }


root_agent = Agent(
    name="endor_oss",
    model=_MODEL,
    description=(
        "Endor Labs open-source intelligence: answers questions about open-source "
        "vulnerabilities, package risk, and CVEs. Public data only — no login, no "
        "customer data."
    ),
    instruction=SYSTEM_PROMPT,
    tools=[
        vulnerability_details,
        dependency_vulnerabilities,
        package_risk,
        agent_info,
    ],
)

# Printed to the adk web / adk run console at startup.
logger.info("endor_oss active model: %s", describe_model())
