"""Tool specifications the model routes questions to (Option A).

These are the three OSS tools the Copilot plugin uses, described in a
model-agnostic shape (name, description, JSON input schema). The P2 router
adapts these to whatever model runtime is chosen (Vertex/Gemini, etc.); the
handler dispatches a chosen tool call to :class:`OssIntelClient`.
"""

from __future__ import annotations

from typing import Any

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "vulnerability_details",
        "description": "Get details for a specific open-source vulnerability by CVE or GHSA id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "advisory_id": {"type": "string", "description": "e.g. CVE-2021-44228 or GHSA-…"}
            },
            "required": ["advisory_id"],
        },
    },
    {
        "name": "dependency_vulnerabilities",
        "description": "List known vulnerabilities for an open-source package version.",
        "input_schema": {
            "type": "object",
            "properties": {
                "purl": {"type": "string", "description": "e.g. mvn://group:artifact@1.2.3 or npm://name@1.2.3"}
            },
            "required": ["purl"],
        },
    },
    {
        "name": "package_risk",
        "description": "Get Endor risk scores for an open-source package version.",
        "input_schema": {
            "type": "object",
            "properties": {
                "purl": {"type": "string", "description": "e.g. mvn://group:artifact@1.2.3 or npm://name@1.2.3"}
            },
            "required": ["purl"],
        },
    },
]

TOOL_NAMES = frozenset(spec["name"] for spec in TOOL_SPECS)


def dispatch_tool(client: "OssIntelClient", name: str, args: dict[str, Any]) -> Any:
    """Execute one tool call against the OSS client. Returns a result model."""

    if name == "vulnerability_details":
        return client.vulnerability_details(args["advisory_id"])
    if name == "dependency_vulnerabilities":
        return client.dependency_vulnerabilities(args["purl"])
    if name == "package_risk":
        return client.package_risk(args["purl"])
    raise ValueError(f"Unknown OSS tool: {name!r}")


# Imported at end to avoid a cycle at module load.
from .client import OssIntelClient  # noqa: E402
