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
    assert f"python3 {helper} capture -- <direct endorctl agent api list arguments>" in context
    assert "exactly once" in context
    assert "hook already verified the helper path" in context
    assert "do not test paths or tools" in context
    assert "execute endorctl separately" in context
    assert "inspect the artifact" in context
    assert "separate count query" in context


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
