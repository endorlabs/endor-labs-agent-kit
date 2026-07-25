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


MESSAGE = (
    "Endor Agent Kit transport enforcement: direct `endorctl api` is not attributed. "
    "Retry the same read as `endorctl agent api --agent-id <canonical-agent-id>` using "
    "the active workflow's canonical agent ID; never append `-agent`."
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


def invokes_legacy_agent_api(command: str) -> bool:
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
        if index + 1 >= len(tokens):
            continue
        if Path(tokens[index]).name == "endorctl" and tokens[index + 1] == "api":
            return True
    return False


def deny(event: str) -> None:
    if event == "beforeShellExecution":
        print(json.dumps({
            "permission": "deny",
            "user_message": MESSAGE,
            "agent_message": MESSAGE,
        }, separators=(",", ":")))
        return
    if event == "BeforeTool":
        print(json.dumps({"decision": "deny", "reason": MESSAGE}, separators=(",", ":")))
        return
    if event == "PreToolUse" and os.environ.get("CLAUDE_PLUGIN_ROOT"):
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": MESSAGE,
                "additionalContext": MESSAGE,
            }
        }, separators=(",", ":")))
        return
    print(json.dumps({"decision": "deny", "reason": MESSAGE}, separators=(",", ":")))


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
    if invokes_legacy_agent_api(command):
        deny(event)
except Exception:
    pass
PY

exit 0
