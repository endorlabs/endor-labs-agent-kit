#!/usr/bin/env bash
# endor_agent_kit_managed=true

if ! command -v python3 >/dev/null 2>&1; then
  exit 0
fi

payload="$(cat)"
HOOK_PAYLOAD="$payload" python3 - "$@" <<'PY' || true
import json
import os
from pathlib import Path
import re
import shlex
import sys


LEGACY_MESSAGE = (
    "Endor Agent Kit transport enforcement: direct `endorctl api` is not attributed. "
    "Retry the same read as `endorctl agent api --agent-id <canonical-agent-id>` using "
    "the active workflow's canonical agent ID; never append `-agent`."
)
MISSING_AGENT_ID_MESSAGE = (
    "Endor Agent Kit attribution enforcement: `endorctl agent api` requires a non-empty "
    "`--agent-id <canonical-agent-id>`. Retry the same request using the active workflow's "
    "canonical agent ID; never append `-agent`."
)


def command_from(payload: dict[str, object]) -> str:
    tool_input = payload.get("tool_input") or payload.get("toolInput") or payload.get("toolCall") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    nested_args = tool_input.get("args") if isinstance(tool_input.get("args"), dict) else {}
    nested_params = tool_input.get("params") if isinstance(tool_input.get("params"), dict) else {}
    return str(
        tool_input.get("command")
        or tool_input.get("cmd")
        or tool_input.get("CommandLine")
        or nested_args.get("command")
        or nested_args.get("CommandLine")
        or nested_params.get("command")
        or payload.get("command")
        or ""
    )


def has_nonempty_agent_id(tokens: list[str]) -> bool:
    found = False
    for index, token in enumerate(tokens):
        if token == "--agent-id":
            if index + 1 >= len(tokens) or not tokens[index + 1] or tokens[index + 1].startswith("-"):
                return False
            found = True
        elif token.startswith("--agent-id="):
            if not token.partition("=")[2]:
                return False
            found = True
    return found


def agent_api_violation(command: str):
    for segment in re.split(r"(?:&&|\|\||[;|\n])", command):
        try:
            tokens = shlex.split(segment, posix=True)
        except ValueError:
            continue
        index = 0
        while index < len(tokens) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[index]):
            index += 1
        if index < len(tokens) and tokens[index] == "env":
            index += 1
            while index < len(tokens) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[index]):
                index += 1
        if index < len(tokens) and tokens[index] in {"command", "exec"}:
            index += 1
        if index < len(tokens) and Path(tokens[index]).name in {"bunx", "npx", "pnpx"}:
            index += 1
            while index < len(tokens) and tokens[index].startswith("-"):
                index += 1
        if index + 1 >= len(tokens) or Path(tokens[index]).name != "endorctl":
            continue
        if tokens[index + 1] == "api":
            return LEGACY_MESSAGE
        if (
            index + 2 < len(tokens)
            and tokens[index + 1] == "agent"
            and tokens[index + 2] == "api"
            and not has_nonempty_agent_id(tokens[index + 3 :])
        ):
            return MISSING_AGENT_ID_MESSAGE
    return None


def deny(event: str, message: str) -> None:
    if event == "beforeShellExecution":
        print(json.dumps({
            "permission": "deny",
            "user_message": message,
            "agent_message": message,
        }, separators=(",", ":")))
        return
    if event == "BeforeTool":
        print(json.dumps({"decision": "deny", "reason": message}, separators=(",", ":")))
        return
    if event == "PreToolUse" and os.environ.get("CLAUDE_PLUGIN_ROOT"):
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": message,
                "additionalContext": message,
            }
        }, separators=(",", ":")))
        return
    print(json.dumps({"decision": "deny", "reason": message}, separators=(",", ":")))


try:
    raw = os.environ.get("HOOK_PAYLOAD", "")
    parsed = json.loads(raw or "{}")
    if not isinstance(parsed, dict):
        raise ValueError("hook payload must be an object")
    default_event = sys.argv[1] if len(sys.argv) > 1 else "PreToolUse"
    event = str(
        parsed.get("hook_event_name")
        or parsed.get("hookEventName")
        or parsed.get("event")
        or default_event
    )
    command = command_from(parsed)
    violation = agent_api_violation(command)
    if violation:
        deny(event, violation)
except Exception:
    pass
PY

exit 0
