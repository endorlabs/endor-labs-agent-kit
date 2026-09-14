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

import os

from google.adk.agents import Agent

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


root_agent = Agent(
    name="endor_oss",
    model=_select_model(),
    description=(
        "Endor Labs open-source intelligence: answers questions about open-source "
        "vulnerabilities, package risk, and CVEs. Public data only — no login, no "
        "customer data."
    ),
    instruction=SYSTEM_PROMPT,
    tools=[vulnerability_details, dependency_vulnerabilities, package_risk],
)
