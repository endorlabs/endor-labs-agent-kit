from __future__ import annotations

import json
import subprocess

from endor_agent_kit.publication.antigravity_plugin import (
    _antigravity_hooks_config,
    _hook_source,
    antigravity_text,
)


def test_antigravity_hooks_use_named_hook_schema_and_direct_invocation_handlers():
    config = _antigravity_hooks_config()

    assert set(config) == {"endor-labs-agent-kit"}
    hook = config["endor-labs-agent-kit"]
    assert set(hook) == {"PreInvocation", "PreToolUse", "PostToolUse"}
    assert hook["PreInvocation"] == [
        {
            "type": "command",
            "command": "bash ./hooks/suggest-endor-tools.sh PreInvocation",
            "timeout": 10,
        }
    ]
    assert hook["PreToolUse"][0]["matcher"] == "run_command"
    assert hook["PreToolUse"][0]["hooks"][0]["type"] == "command"
    assert (
        hook["PostToolUse"][0]["matcher"]
        == "write_to_file|replace_file_content|multi_replace_file_content"
    )


def test_antigravity_hook_scripts_emit_native_event_responses():
    hooks = _hook_source()

    pre_invocation = _run_hook(
        hooks / "suggest-endor-tools.sh",
        "PreInvocation",
        {"invocationNum": 0, "initialNumSteps": 0},
    )
    assert pre_invocation == {"injectSteps": []}

    pre_tool = _run_hook(
        hooks / "check-dep-install.sh",
        "PreToolUse",
        {
            "toolCall": {
                "name": "run_command",
                "args": {"CommandLine": "npm install left-pad"},
            }
        },
    )
    assert pre_tool["decision"] == "allow"
    assert "dependency install" in pre_tool["reason"]

    post_tool = _run_hook(
        hooks / "check-manifest-edit.sh",
        "PostToolUse",
        {
            "toolCall": {
                "name": "write_to_file",
                "args": {"TargetFile": "/workspace/package.json"},
            }
        },
    )
    assert post_tool == {}


def test_antigravity_text_uses_installed_plugin_artifact_helper():
    rendered = antigravity_text(
        "Run `python3 runtime/summarize_endor_artifact.py capture -- <argv>` once."
    )

    assert (
        '`python3 "$HOME/.gemini/config/plugins/endor-labs-agent-kit/'
        'runtime/summarize_endor_artifact.py" capture -- <argv>`'
        in rendered
    )
    assert "python3 runtime/summarize_endor_artifact.py" not in rendered


def _run_hook(path, event: str, payload: dict[str, object]) -> dict[str, object]:
    completed = subprocess.run(
        ["bash", str(path), event],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)
