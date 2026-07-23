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
HOOK_PAYLOAD="$payload" ENDOR_ARTIFACT_SUMMARIZER="$artifact_summarizer" ENDOR_PLUGIN_ROOT="$plugin_root" python3 - "$@" <<'PY' || true
import json
import os
from pathlib import Path
import re
import sys


def emit(event_name: str, message: str) -> None:
    if event_name == "PreInvocation":
        steps = [{"ephemeralMessage": message}] if message else []
        print(json.dumps({"injectSteps": steps}, separators=(",", ":")))
        return
    if not message:
        return
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": message,
        }
    }, separators=(",", ":")))


def helper_context(helper: str) -> str:
    return (
        "Installed Endor Agent Kit package metadata: "
        f"`artifact_summarizer_path={helper}`. Use this verified absolute path only when the "
        "selected workflow recipe sets `runtime.large_result_artifact_required=true`; otherwise "
        "ignore it. In that route, invoke `python3 <artifact_summarizer_path> capture -- "
        "<direct endorctl agent api list arguments>` exactly once. Do not preflight or execute "
        "the same Endor query separately, inspect the artifact with another command, or issue a "
        "separate count query. Preserve the returned `artifact_ref`, `sha256`, `format`, `bytes`, "
        "and `row_count` verbatim in the successful evidence ledger row."
    )


def prompt_requests_complete_inventory(prompt_lc: str) -> bool:
    explicitly_bounded = bool(
        re.search(
            r"(?:\bnot (?:a )?complete\b|\bbounded\b.{0,80}\bnot (?:a )?complete\b|"
            r"\b(?:do not|don't|omit|without|no)\b.{0,24}--list-all)",
            prompt_lc,
        )
    )
    if explicitly_bounded:
        return False
    return bool(
        re.search(
            r"(?:--list-all|\blist all\b|\bcomplete\b|\bexhaustive\b|"
            r"\bexact totals?\b|\bfull inventory\b)",
            prompt_lc,
        )
    )


def codex_agent_install_context(prompt_lc: str) -> str:
    plugin_root = Path(os.environ.get("ENDOR_PLUGIN_ROOT", ""))
    if not (plugin_root / ".codex-plugin" / "plugin.json").is_file():
        return ""
    bundled = sorted((plugin_root / "agents").glob("*.toml"))
    if not bundled:
        return ""
    codex_home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
    installed_root = codex_home / "agents"
    missing = [source.name for source in bundled if not (installed_root / source.name).is_file()]
    if not missing:
        return ""
    setup_requested = bool(
        "endor-agent-kit-setup" in prompt_lc
        or re.search(r"\b(install|setup|set up|check)\b", prompt_lc)
    )
    status = (
        "Codex custom-agent installation boundary: "
        f"{len(missing)} of {len(bundled)} bundled Endor custom agents are missing. "
    )
    if setup_requested:
        return (
            status
            + "Use `endor-agent-kit-setup` to perform the approved managed agents-only "
            "installation, then tell the user to start a fresh Codex task."
        )
    return (
        status
        + "Do not execute the requested Endor workflow in the primary agent or through "
        "a workflow skill. Use `endor-agent-kit-setup` to request the managed agents-only "
        "installation, then continue in a fresh Codex task."
    )


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
    helper = os.environ.get("ENDOR_ARTIFACT_SUMMARIZER", "")
    if event == "PreInvocation":
        invocation_num = payload.get("invocationNum")
        message = (
            helper_context(helper)
            if helper and invocation_num in (None, 0, "0")
            else ""
        )
        emit(event, message)
        raise SystemExit(0)
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
    install_context = codex_agent_install_context(prompt_lc)
    if install_context:
        context.append(install_context)
    if routes:
        context.append("Endor Agent Kit advisory routing:\n- " + "\n- ".join(dict.fromkeys(routes)))
    endor_relevant = bool(routes) or bool(
        re.search(r"\b(endor|malware|remediat|triag|upgrade impact|exception policy)\b", prompt_lc)
    )
    if helper and endor_relevant and prompt_requests_complete_inventory(prompt_lc):
        context.append(helper_context(helper))
    if context:
        emit(event, "\n".join(context))
except Exception:
    pass
PY

exit 0
