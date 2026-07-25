from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

from conftest import repo_root


def test_prompt_hook_injects_exact_packaged_artifact_summarizer_path(tmp_path: Path):
    package = tmp_path / "endor-labs-agent-kit"
    hooks = package / "hooks"
    runtime = package / "runtime"
    hooks.mkdir(parents=True)
    runtime.mkdir()
    hook = hooks / "suggest-endor-tools.sh"
    shutil.copy2(
        repo_root() / "source" / "plugin-support" / "hooks" / "claude" / hook.name,
        hook,
    )
    helper = runtime / "summarize_endor_artifact.py"
    helper.write_text("# packaged helper\n", encoding="utf-8")

    completed = subprocess.run(
        ["bash", str(hook), "UserPromptSubmit"],
        input=json.dumps({"prompt": "Browse complete Endor findings across the namespace."}),
        text=True,
        capture_output=True,
        check=True,
    )

    output = json.loads(completed.stdout)
    context = output["hookSpecificOutput"]["additionalContext"]
    assert str(helper) in context
    assert f"artifact_summarizer_path={helper}" in context
    assert "python3 <artifact_summarizer_path> capture --" in context
    assert "exactly once" in context
    assert "verified absolute path only when" in context
    assert "otherwise ignore it" in context
    assert "Run capture immediately" not in context
    assert "execute the same Endor query separately" in context
    assert "inspect the artifact" in context
    assert "separate count query" in context


def test_prompt_hook_omits_runtime_helper_for_bounded_endor_prompt(tmp_path: Path):
    package = tmp_path / "endor-labs-agent-kit"
    hooks = package / "hooks"
    runtime = package / "runtime"
    hooks.mkdir(parents=True)
    runtime.mkdir()
    hook = hooks / "suggest-endor-tools.sh"
    shutil.copy2(
        repo_root() / "source" / "plugin-support" / "hooks" / "claude" / hook.name,
        hook,
    )
    helper = runtime / "summarize_endor_artifact.py"
    helper.write_text("# packaged helper\n", encoding="utf-8")

    completed = subprocess.run(
        ["bash", str(hook), "UserPromptSubmit"],
        input=json.dumps(
            {
                "prompt": (
                    "Browse at most three Endor findings. This is a bounded sample, "
                    "not a complete inventory."
                )
            }
        ),
        text=True,
        capture_output=True,
        check=True,
    )

    context = json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "findings-browser" in context
    assert "artifact_summarizer_path" not in context


def test_antigravity_pre_invocation_injects_helper_without_prompt_fields(
    tmp_path: Path,
):
    package = tmp_path / "endor-labs-agent-kit"
    hooks = package / "hooks"
    runtime = package / "runtime"
    hooks.mkdir(parents=True)
    runtime.mkdir()
    hook = hooks / "suggest-endor-tools.sh"
    shutil.copy2(
        repo_root() / "source" / "plugin-support" / "hooks" / "claude" / hook.name,
        hook,
    )
    helper = runtime / "summarize_endor_artifact.py"
    helper.write_text("# packaged helper\n", encoding="utf-8")

    first = subprocess.run(
        ["bash", str(hook), "PreInvocation"],
        input=json.dumps(
            {
                "invocationNum": 0,
                "initialNumSteps": 0,
                "workspacePaths": [str(tmp_path)],
            }
        ),
        text=True,
        capture_output=True,
        check=True,
    )
    later = subprocess.run(
        ["bash", str(hook), "PreInvocation"],
        input=json.dumps({"invocationNum": 1, "initialNumSteps": 3}),
        text=True,
        capture_output=True,
        check=True,
    )

    first_output = json.loads(first.stdout)
    assert len(first_output["injectSteps"]) == 1
    assert str(helper) in first_output["injectSteps"][0]["ephemeralMessage"]
    assert json.loads(later.stdout) == {"injectSteps": []}


def test_prompt_hook_omits_runtime_helper_for_unrelated_prompts(tmp_path: Path):
    package = tmp_path / "endor-labs-agent-kit"
    hooks = package / "hooks"
    runtime = package / "runtime"
    hooks.mkdir(parents=True)
    runtime.mkdir()
    hook = hooks / "suggest-endor-tools.sh"
    shutil.copy2(
        repo_root() / "source" / "plugin-support" / "hooks" / "claude" / hook.name,
        hook,
    )
    (runtime / "summarize_endor_artifact.py").write_text("# packaged helper\n", encoding="utf-8")

    completed = subprocess.run(
        ["bash", str(hook), "UserPromptSubmit"],
        input=json.dumps({"prompt": "Explain how Python list comprehensions work."}),
        text=True,
        capture_output=True,
        check=True,
    )

    assert completed.stdout == ""


def test_codex_prompt_hook_routes_missing_custom_agents_to_setup(tmp_path: Path):
    package = tmp_path / "endor-labs-agent-kit"
    hooks = package / "hooks"
    agents = package / "agents"
    manifest = package / ".codex-plugin" / "plugin.json"
    hooks.mkdir(parents=True)
    agents.mkdir()
    manifest.parent.mkdir()
    manifest.write_text('{"name":"endor-labs-agent-kit"}\n', encoding="utf-8")
    hook = hooks / "suggest-endor-tools.sh"
    shutil.copy2(
        repo_root() / "source" / "plugin-support" / "hooks" / "claude" / hook.name,
        hook,
    )
    for name in ("endor-findings-browser-agent.toml", "endor-agent-kit-setup-agent.toml"):
        (agents / name).write_text("# bundled\n", encoding="utf-8")

    codex_home = tmp_path / "codex-home"
    environment = os.environ.copy()
    environment["CODEX_HOME"] = str(codex_home)
    missing = subprocess.run(
        ["bash", str(hook), "UserPromptSubmit"],
        input=json.dumps({"prompt": "Browse Endor findings for this repository."}),
        text=True,
        capture_output=True,
        check=True,
        env=environment,
    )
    missing_context = json.loads(missing.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "2 of 2 bundled Endor custom agents are missing" in missing_context
    assert "Do not execute the requested Endor workflow in the primary agent" in missing_context
    assert "endor-agent-kit-setup" in missing_context

    installed = codex_home / "agents"
    installed.mkdir(parents=True)
    for source in agents.glob("*.toml"):
        shutil.copy2(source, installed / source.name)
    current = subprocess.run(
        ["bash", str(hook), "UserPromptSubmit"],
        input=json.dumps({"prompt": "Browse Endor findings for this repository."}),
        text=True,
        capture_output=True,
        check=True,
        env=environment,
    )
    current_context = json.loads(current.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "custom-agent installation boundary" not in current_context
    assert "MANDATORY ROUTE" in current_context
    assert "invoke the installed Codex custom agent `endor-findings-browser-agent`" in current_context
    assert "--agent-id findings-browser" in current_context
    assert "never append `-agent`" in current_context


def test_codex_prompt_hook_routes_all_workflows_to_one_installed_custom_agent(tmp_path: Path):
    package = tmp_path / "endor-labs-agent-kit"
    hooks = package / "hooks"
    agents = package / "agents"
    manifest = package / ".codex-plugin" / "plugin.json"
    hooks.mkdir(parents=True)
    agents.mkdir()
    manifest.parent.mkdir()
    manifest.write_text('{"name":"endor-labs-agent-kit"}\n', encoding="utf-8")
    hook = hooks / "suggest-endor-tools.sh"
    shutil.copy2(
        repo_root() / "source" / "plugin-support" / "hooks" / "claude" / hook.name,
        hook,
    )

    prompts = {
        "ai-sast-remediation": "Triage the AI SAST results for this repository.",
        "cicd-posture": "Assess GitHub Actions and branch protection supply chain posture.",
        "configuration-automation": "Check monitored branch onboarding and GitHub App selection coverage.",
        "dependency-reviewer": "Is lodash safe to add as a dependency?",
        "findings-browser": "Browse active critical reachable findings for this repository.",
        "malware-responder": "Assess exposure to this compromised package malware campaign.",
        "oss-upgrade-investigator": "Assess upgrading pypi://pydantic-settings from 2.6.1 to 2.14.2, including findings fixed and CIA status.",
        "remediation-planning": "Create a prioritized remediation plan for these issues.",
        "sca-remediation": "Remediate this dependency vulnerability with approval gates.",
        "troubleshooting": "Diagnose this Endor authentication failure.",
        "vulnerability-explainer": "Explain CVE-2021-44228 and its exploitability.",
    }
    codex_home = tmp_path / "codex-home"
    installed = codex_home / "agents"
    installed.mkdir(parents=True)
    for agent_id in prompts:
        name = f"endor-{agent_id}-agent.toml"
        (agents / name).write_text("# bundled\n", encoding="utf-8")
        shutil.copy2(agents / name, installed / name)

    environment = os.environ.copy()
    environment["CODEX_HOME"] = str(codex_home)
    for agent_id, prompt in prompts.items():
        completed = subprocess.run(
            ["bash", str(hook), "UserPromptSubmit"],
            input=json.dumps({"prompt": prompt}),
            text=True,
            capture_output=True,
            check=True,
            env=environment,
        )
        context = json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]
        expected = f"endor-{agent_id}-agent"
        assert f"invoke the installed Codex custom agent `{expected}`" in context
        assert context.count("MANDATORY ROUTE") == 1
        assert f"--agent-id {agent_id}" in context


def test_upgrade_route_preserves_oss_investigator_precedence_without_codex_package(tmp_path: Path):
    package = tmp_path / "endor-labs-agent-kit"
    hooks = package / "hooks"
    hooks.mkdir(parents=True)
    hook = hooks / "suggest-endor-tools.sh"
    shutil.copy2(
        repo_root() / "source" / "plugin-support" / "hooks" / "claude" / hook.name,
        hook,
    )

    completed = subprocess.run(
        ["bash", str(hook), "UserPromptSubmit"],
        input=json.dumps(
            {
                "prompt": (
                    "Assess upgrading pypi://pydantic-settings from 2.6.1 to 2.14.2 "
                    "in Endor namespace matt-staging. Return findings fixed and CIA status."
                )
            }
        ),
        text=True,
        capture_output=True,
        check=True,
    )

    context = json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "Use `oss-upgrade-investigator`" in context
    assert "dependency-reviewer" not in context
    assert "findings-browser" not in context
    assert "troubleshooting" not in context


def test_cursor_prompt_hook_prefers_packaged_agent_over_support_skill(tmp_path: Path):
    package = tmp_path / "endor-labs-agent-kit"
    hooks = package / "hooks"
    agents = package / "agents"
    hooks.mkdir(parents=True)
    agents.mkdir()
    hook = hooks / "suggest-endor-tools.sh"
    shutil.copy2(
        repo_root() / "source" / "plugin-support" / "hooks" / "claude" / hook.name,
        hook,
    )
    (agents / "endor-oss-upgrade-investigator-agent.md").write_text(
        "---\nname: endor-oss-upgrade-investigator-agent\n---\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        ["bash", str(hook), "beforeSubmitPrompt"],
        input=json.dumps(
            {
                "prompt": (
                    "Assess upgrading pypi://pydantic-settings from 2.6.1 to 2.14.2 "
                    "and return CIA status."
                )
            }
        ),
        text=True,
        capture_output=True,
        check=True,
    )

    context = json.loads(completed.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "Invoke the installed Cursor agent `endor-oss-upgrade-investigator-agent`" in context
    assert "Do not substitute its matching support skill" in context
