"""Agent-attributed Endor API command contracts."""

from __future__ import annotations

import re


_BARE_ENDORCTL_API_RE = re.compile(r"\bendorctl\s+api\b", re.IGNORECASE)
_AGENT_API_RE = re.compile(r"\bendorctl\s+agent\s+api\b", re.IGNORECASE)
_AGENT_ID_RE = re.compile(r"--agent-id(?:=|\s+)([a-z0-9-]+|<agent-id>)", re.IGNORECASE)
_ACTION_RE = re.compile(r"\b(list|get|create|update|delete)\b", re.IGNORECASE)
_RESOURCE_RE = re.compile(r"(?:--resource|(?<![\w-])-r)(?:=|\s+)([A-Za-z0-9]+)")


def agent_api_command_errors(
    text: str,
    *,
    agent_id: str,
    allow_template_identity: bool = False,
) -> list[str]:
    """Return safety errors for agent-facing Endor CLI commands."""

    errors: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if _BARE_ENDORCTL_API_RE.search(line):
            errors.append(
                f"line {line_number}: agent-facing Endor calls must use `endorctl agent api`"
            )
            continue
        marker = _AGENT_API_RE.search(line)
        if marker is None:
            continue
        command = line[marker.end():]
        if line[: marker.start()].count("`") % 2 == 1:
            command = command.split("`", 1)[0]
        action_match = _ACTION_RE.search(command)
        if action_match is None:
            continue
        match = _AGENT_ID_RE.search(command)
        if match is None:
            errors.append(
                f"line {line_number}: `endorctl agent api` must include `--agent-id {agent_id}`"
            )
            continue
        actual = match.group(1)
        placeholder_identity = allow_template_identity and actual == "<agent-id>"
        if not placeholder_identity and actual != agent_id:
            errors.append(
                f"line {line_number}: `endorctl agent api` uses agent id {actual!r}; "
                f"expected {agent_id!r}"
            )
        action = action_match.group(1).lower()
        if action not in {"create", "update", "delete"}:
            continue
        if agent_id != "ai-sast-remediation":
            errors.append(
                f"line {line_number}: {agent_id} is not allowed to mutate Endor resources"
            )
            continue
        resource_match = _RESOURCE_RE.search(command)
        resource = resource_match.group(1) if resource_match is not None else ""
        if action not in {"create", "update"} or resource != "Policy":
            errors.append(
                f"line {line_number}: ai-sast-remediation may create or update Policy resources only"
            )
    return errors
