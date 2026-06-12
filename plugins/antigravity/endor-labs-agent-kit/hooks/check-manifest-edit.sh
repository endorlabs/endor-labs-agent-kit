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


MANIFEST_RE = re.compile(
    r"(^|/)(package\.json|package-lock\.json|npm-shrinkwrap\.json|pnpm-lock\.yaml|"
    r"yarn\.lock|pyproject\.toml|poetry\.lock|requirements.*\.txt|Pipfile|Pipfile\.lock|"
    r"go\.mod|go\.sum|Cargo\.toml|Cargo\.lock|pom\.xml|build\.gradle|build\.gradle\.kts|"
    r"Gemfile|Gemfile\.lock|composer\.json|composer\.lock)$",
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
    modified_files = payload.get("modified_files") or payload.get("modifiedFiles") or []
    if not isinstance(modified_files, list):
        modified_files = []
    candidate_paths = [
        tool_input.get("file_path"),
        tool_input.get("path"),
        nested_args.get("file_path"),
        nested_args.get("path"),
        nested_params.get("file_path"),
        nested_params.get("path"),
        payload.get("file_path"),
        payload.get("path"),
        *modified_files,
    ]
    path = next((str(item) for item in candidate_paths if item), "")
    if not path or not MANIFEST_RE.search(path):
        raise SystemExit(0)
    emit(
        event,
        "Endor Agent Kit manifest advisory: this edit touches a dependency manifest or lockfile. "
        "Use `dependency-decision-helper` for new dependency approval, `package-risk-summary` for known "
        "package-version risk, or `repository-dependency-reviewer` for a repository-level manifest review. "
        "Do not run a scan or mutate Endor state from this hook context."
    )
except Exception:
    pass
PY

exit 0
