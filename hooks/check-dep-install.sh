#!/usr/bin/env bash
# endor_agent_kit_managed=true

if ! command -v python3 >/dev/null 2>&1; then
  exit 0
fi

payload="$(cat)"
HOOK_PAYLOAD="$payload" python3 - "$@" <<'PY' || true
import json
import os
import re
import sys


INSTALL_RE = re.compile(
    r"(^|\s)(npm\s+(install|i|add)|pnpm\s+(add|install)|yarn\s+add|bun\s+add|"
    r"pip(x)?\s+install|poetry\s+add|uv\s+(add|pip\s+install)|bundle\s+add|"
    r"gem\s+install|go\s+get|cargo\s+add|mvn\s+dependency:get|gradle\s+dependencies)\b",
    re.IGNORECASE,
)


def emit(event_name: str, message: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": message,
        }
    }, separators=(",", ":")))


try:
    raw = os.environ.get("HOOK_PAYLOAD", "")
    payload = json.loads(raw or "{}")
    if not isinstance(payload, dict):
        raise ValueError("hook payload must be an object")
    default_event = sys.argv[1] if len(sys.argv) > 1 else "PostToolUse"
    event = str(
        payload.get("hook_event_name")
        or payload.get("hookEventName")
        or payload.get("event")
        or default_event
    )
    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    nested_args = tool_input.get("args") if isinstance(tool_input.get("args"), dict) else {}
    nested_params = tool_input.get("params") if isinstance(tool_input.get("params"), dict) else {}
    command = str(
        tool_input.get("command")
        or tool_input.get("cmd")
        or nested_args.get("command")
        or nested_params.get("command")
        or payload.get("command")
        or ""
    )
    if not INSTALL_RE.search(command):
        raise SystemExit(0)
    emit(
        event,
        "Endor Agent Kit dependency advisory: this command looks like a dependency install or add. "
        "Before relying on the package, route through `dependency-decision-helper` for new dependency approval "
        "or `package-risk-summary` for package-version risk. Keep the workflow read-only unless the user has "
        "already approved the install."
    )
except Exception:
    pass
PY

exit 0
