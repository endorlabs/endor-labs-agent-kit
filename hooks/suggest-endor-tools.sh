#!/usr/bin/env bash
# endor_agent_kit_managed=true

if ! command -v python3 >/dev/null 2>&1; then
  exit 0
fi

payload="$(cat)"
hook_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)" || exit 0
plugin_root="$(dirname -- "$hook_dir")"
artifact_summarizer="$plugin_root/runtime/summarize_endor_artifact.py"
if [[ ! -f "$artifact_summarizer" ]]; then
  artifact_summarizer=""
fi
HOOK_PAYLOAD="$payload" ENDOR_ARTIFACT_SUMMARIZER="$artifact_summarizer" python3 - "$@" <<'PY' || true
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
        routes.append("Use `vulnerability-explainer` for CVE/GHSA explanation or `dependency-reviewer` with `package-risk` when package-version posture matters.")
    if re.search(r"\b(package|dependency|library|module)\b", prompt_lc) and re.search(r"\b(safe|risk|install|add|upgrade|version)\b", prompt_lc):
        routes.append("Use `dependency-reviewer` with `package-decision` before adding a dependency, or `package-risk` for a known package version.")
    if re.search(r"\b(endorctl|scan|host-check|mcp|namespace|auth|token|setup|onboard|error|failed|failure)\b", prompt_lc):
        routes.append("Use `troubleshooting` for Endor errors and setup failures; use `configuration-automation` for GitHub onboarding coverage.")
    if re.search(r"\b(findings?|finding uuid|severity|filter|dismissed|reachable|epss|kev)\b", prompt_lc):
        routes.append("Use `findings-browser` to browse or filter existing Endor findings without starting a new scan.")
    if re.search(r"\b(ci/cd|cicd|github actions?|workflow|branch protection|ruleset|runner|supply chain|posture)\b", prompt_lc):
        routes.append("For CI/CD posture questions, keep evidence read-only. Use `findings-browser` for existing CI/CD or GitHub Actions findings and `configuration-automation` for GitHub onboarding evidence until a dedicated posture workflow is available.")

    context = []
    if routes:
        context.append("Endor Agent Kit advisory routing:\n- " + "\n- ".join(dict.fromkeys(routes)))
    helper = os.environ.get("ENDOR_ARTIFACT_SUMMARIZER", "")
    endor_relevant = bool(routes) or bool(
        re.search(r"\b(endor|malware|remediat|triag|upgrade impact|exception policy)\b", prompt_lc)
    )
    if helper and endor_relevant:
        context.append(
            "Endor Agent Kit runtime helper: for `runtime.large_result_artifact_required`, "
            f"invoke `python3 {helper} capture -- <direct endorctl agent api list arguments>` exactly "
            "once. This hook already verified the helper path, and capture reports executable "
            "errors safely. Run capture immediately: do not test paths or tools, search, "
            "preflight, execute endorctl separately, inspect the artifact with another command, "
            "or issue a separate count query."
        )
    if context:
        emit(event, "\n".join(context))
except Exception:
    pass
PY

exit 0
