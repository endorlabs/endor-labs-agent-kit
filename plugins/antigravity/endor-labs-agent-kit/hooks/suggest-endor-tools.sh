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


def emit(event_name: str, message: str) -> None:
    if not message:
        return
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
    default_event = sys.argv[1] if len(sys.argv) > 1 else "UserPromptSubmit"
    event = str(
        payload.get("hook_event_name")
        or payload.get("hookEventName")
        or payload.get("event")
        or default_event
    )
    prompt = str(
        payload.get("prompt")
        or payload.get("user_prompt")
        or payload.get("message")
        or payload.get("transcript")
        or ""
    )
    prompt_lc = prompt.lower()
    if not prompt_lc or "endor_agent_kit_managed" in prompt_lc:
        raise SystemExit(0)

    routes = []
    if re.search(r"\b(cve-\d{4}-\d+|ghsa-[a-z0-9-]+|vulnerab|advisory)\b", prompt_lc):
        routes.append("Use `vulnerability-explainer` for CVE/GHSA explanation or `package-risk-summary` when package-version posture matters.")
    if re.search(r"\b(package|dependency|library|module)\b", prompt_lc) and re.search(r"\b(safe|risk|install|add|upgrade|version)\b", prompt_lc):
        routes.append("Use `dependency-decision-helper` before adding a new dependency, or `package-risk-summary` for a known package version.")
    if re.search(r"\b(endorctl|scan|host-check|mcp|namespace|auth|token|setup|onboard|error|failed|failure)\b", prompt_lc):
        routes.append("Use `endor-troubleshooter` for Endor errors and setup failures; use `probe-droid` for GitHub onboarding coverage.")
    if re.search(r"\b(findings?|finding uuid|severity|filter|dismissed|reachable|epss|kev)\b", prompt_lc):
        routes.append("Use `findings-browser` to browse or filter existing Endor findings without starting a new scan.")
    if re.search(r"\b(ci/cd|cicd|github actions?|workflow|branch protection|ruleset|runner|supply chain|posture)\b", prompt_lc):
        routes.append("For CI/CD posture questions, keep evidence read-only. Use `findings-browser` for existing CI/CD or GitHub Actions findings and `probe-droid` for GitHub onboarding evidence until a dedicated posture workflow is available.")

    if routes:
        emit(event, "Endor Agent Kit advisory routing:\n- " + "\n- ".join(dict.fromkeys(routes)))
except Exception:
    pass
PY

exit 0
