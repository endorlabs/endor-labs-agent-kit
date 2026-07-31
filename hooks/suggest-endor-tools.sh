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
import hashlib
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


def cicd_score_context(helper: str) -> str:
    return (
        "CI/CD Posture deterministic scoring boundary: use the verified packaged helper "
        f"`artifact_summarizer_path={helper}` exactly once after raw_counts and verified "
        "critical override types are known. Invoke `python3 <artifact_summarizer_path> "
        "score-cicd-posture --raw-counts-json '<RAW_COUNTS_JSON>' "
        "[--critical-override <TYPE>]`. Copy posture_verdict, dimension_scores, and "
        "score_validation verbatim. Do not run the helper twice, manually recompute the "
        "scores, run a separate validator cross-check, or search for another helper."
    )


def ai_sast_selection_context(helper: str) -> str:
    return (
        "AI SAST deterministic selection boundary: when the selected profile needs one finding "
        "and the user did not supply a Finding UUID, use the verified packaged helper "
        f"`artifact_summarizer_path={helper}` exactly once as `python3 "
        "<artifact_summarizer_path> capture --projection ai-sast-selection -- "
        "<direct compact endorctl agent api list arguments>`. Copy only artifact metadata, "
        "row_count, severity_counts, selected_level, and selected_finding_uuid into model "
        "context, then fetch detail for that UUID. Do not read the retained artifact, issue a "
        "separate count, repeat the inventory, or write an ad hoc parser. A supplied Finding "
        "UUID and the availability-only evidence-check profile do not use this selection route."
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
    noncurrent = [
        source.name
        for source in bundled
        if _file_digest(source) != _file_digest(installed_root / source.name)
    ]
    if not noncurrent:
        return ""
    setup_requested = bool(
        "endor-agent-kit-setup" in prompt_lc
        or re.search(r"\b(install|setup|set up|check)\b", prompt_lc)
    )
    status = (
        "Codex custom-agent installation boundary: "
        f"{len(noncurrent)} of {len(bundled)} bundled Endor custom agents are missing or stale. "
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


CANONICAL_AGENT_IDS = (
    "ai-sast-remediation",
    "cicd-posture",
    "configuration-automation",
    "dependency-reviewer",
    "findings-browser",
    "malware-responder",
    "oss-upgrade-investigator",
    "remediation-planning",
    "sca-remediation",
    "troubleshooting",
    "vulnerability-explainer",
)


def codex_plugin_root() -> Path | None:
    plugin_root = Path(os.environ.get("ENDOR_PLUGIN_ROOT", ""))
    if (plugin_root / ".codex-plugin" / "plugin.json").is_file():
        return plugin_root
    return None


def codex_custom_agent_name(agent_id: str) -> str:
    return f"endor-{agent_id}-agent"


def _file_digest(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def codex_installed_agent_provenance(agent_id: str) -> tuple[Path, str] | None:
    plugin_root = codex_plugin_root()
    if plugin_root is None:
        return None
    filename = f"{codex_custom_agent_name(agent_id)}.toml"
    bundled = plugin_root / "agents" / filename
    codex_home = Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
    installed = codex_home / "agents" / filename
    bundled_digest = _file_digest(bundled)
    installed_digest = _file_digest(installed)
    if not bundled_digest or installed_digest != bundled_digest:
        return None
    return installed, installed_digest


def cursor_packaged_agent_provenance(agent_id: str) -> tuple[str, Path, str] | None:
    plugin_root = Path(os.environ.get("ENDOR_PLUGIN_ROOT", ""))
    name = codex_custom_agent_name(agent_id)
    path = plugin_root / "agents" / f"{name}.md"
    digest = _file_digest(path)
    if digest:
        return name, path, digest
    return None


def workflow_result_relay() -> str:
    return (
        "Deliver the workflow agent's complete result as a concise human-readable answer "
        "by default. Preserve its verdict or recommendation, supporting evidence, material "
        "data gaps, and next steps. Do not expose internal routing or output-schema "
        "language. If the user explicitly requested JSON, machine-readable output, or the "
        "structured output contract, return the agent's structured JSON without alteration "
        "instead."
    )


def route_instruction(agent_id: str, purpose: str) -> str:
    if codex_plugin_root() is None:
        cursor_provenance = cursor_packaged_agent_provenance(agent_id)
        if cursor_provenance:
            cursor_agent, cursor_path, cursor_digest = cursor_provenance
            return (
                f"Invoke the installed Cursor agent `{cursor_agent}` {purpose}. "
                f"Verified packaged artifact: `path={cursor_path};sha256={cursor_digest}`. "
                "Do not substitute its matching support skill for workflow execution; "
                "the support skill is documentation and reference material. Do not search "
                "the workspace, home directory, or another provider directory for a second "
                "workflow artifact. "
                + workflow_result_relay()
            )
        return f"Use `{agent_id}` {purpose}. " + workflow_result_relay()
    custom_agent = codex_custom_agent_name(agent_id)
    codex_provenance = codex_installed_agent_provenance(agent_id)
    if codex_provenance:
        installed_path, installed_digest = codex_provenance
        return (
            f"MANDATORY ROUTE: before any setup or shell tool call, invoke the installed Codex "
            f"custom agent `{custom_agent}` through subagent delegation {purpose}, passing the "
            f"full user request. Verified installed artifact: `path={installed_path};"
            f"sha256={installed_digest}`. Do not search the workspace, home directory, plugin "
            "caches, or another provider directory for a second workflow artifact. "
            "Do not execute this workflow in the primary agent, open the "
            "setup skill, or substitute a workflow-skill fallback. The Endor API attribution "
            f"value remains `--agent-id {agent_id}`; never append `-agent` or use the host "
            "custom-agent name as the Endor agent ID. "
            + workflow_result_relay()
        )
    return (
        f"The `{agent_id}` workflow requires the bundled Codex custom agent "
        f"`{custom_agent}`, which is not installed. Use `endor-agent-kit-setup` for the "
        "approved managed agents-only installation, then start a fresh Codex task. Do not "
        "fall back to the primary agent or an unrelated workflow skill."
    )


def select_route(prompt_lc: str) -> tuple[str, str] | None:
    # An explicit canonical or installed-agent identity always wins.
    for agent_id in CANONICAL_AGENT_IDS:
        if agent_id in prompt_lc or codex_custom_agent_name(agent_id) in prompt_lc:
            return agent_id, "for the explicitly selected Endor workflow"

    if re.search(r"\b(ai[ -]?sast|exploit reproduction|remediation guidance)\b", prompt_lc):
        return "ai-sast-remediation", "for AI SAST triage or remediation"
    if re.search(r"\b(malware|supply[ -]?chain incident|compromised package|campaign exposure)\b", prompt_lc):
        return "malware-responder", "for read-only malware exposure response"
    if re.search(r"\b(ci/cd|cicd|github actions?|branch protection|ruleset|self-hosted runner|supply chain posture)\b", prompt_lc):
        return "cicd-posture", "for read-only CI/CD and supply-chain posture evidence"
    if re.search(r"\b(onboard(?:ing)?|monitored branch|github app selection|configuration coverage|probe droid)\b", prompt_lc):
        return "configuration-automation", "for read-only onboarding and configuration coverage"

    upgrade_intent = bool(
        re.search(r"\b(versionupgrade|version upgrade|upgrade impact|code impact analysis|cia status|breaking changes?)\b", prompt_lc)
        or (
            re.search(r"\bupgrad\w*\b", prompt_lc)
            and re.search(r"\b(from|current)\b.{0,80}\b(to|target)\b", prompt_lc)
        )
        or (
            re.search(r"\bupgrad\w*\b", prompt_lc)
            and re.search(r"\b(findings? fixed|findings? introduced|worth doing|worth it)\b", prompt_lc)
        )
    )
    if upgrade_intent:
        return "oss-upgrade-investigator", "for project-scoped VersionUpgrade, CIA, and upgrade-risk evidence"

    if re.search(r"\b(remediation plan|remediation queue|prioriti[sz]e remediation|plan fixes|fix plan)\b", prompt_lc):
        return "remediation-planning", "for read-only remediation selection and planning"
    if re.search(r"\b(sca|dependency vulnerabilit\w*|remediat\w* dependency|fix\w* dependency)\b", prompt_lc):
        return "sca-remediation", "for SCA remediation with the required approval gates"
    if re.search(r"\b(findings?|finding uuid|severity|filter|dismissed|reachable|epss|kev)\b", prompt_lc):
        return "findings-browser", "to browse or filter existing Endor findings without starting a scan"
    if re.search(r"\b(cve-\d{4}-\d+|ghsa-[a-z0-9-]+|explain\w* vulnerabilit|what does this vulnerabilit)\b", prompt_lc):
        return "vulnerability-explainer", "for a focused vulnerability explanation"
    if re.search(r"\b(error|failed|failure|not working|diagnos|troubleshoot|auth issue|login issue|setup issue|scan issue)\b", prompt_lc):
        return "troubleshooting", "for read-only diagnosis and repair guidance"
    if re.search(r"\b(package|dependency|library|module)\b", prompt_lc) and re.search(r"\b(safe|risk|install|add|use|review|version)\b", prompt_lc):
        return "dependency-reviewer", "for a package decision, package-risk review, or repository dependency review"
    return None


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

    route = select_route(prompt_lc)
    routes = [route_instruction(*route)] if route else []

    context = []
    install_context = codex_agent_install_context(prompt_lc)
    if install_context:
        context.append(install_context)
    if routes:
        context.append("Endor Agent Kit advisory routing:\n- " + "\n- ".join(dict.fromkeys(routes)))
    if helper and route and route[0] == "cicd-posture":
        context.append(cicd_score_context(helper))
    if helper and route and route[0] == "ai-sast-remediation":
        context.append(ai_sast_selection_context(helper))
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
