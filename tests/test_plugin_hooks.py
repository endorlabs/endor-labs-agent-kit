from __future__ import annotations

import json
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
