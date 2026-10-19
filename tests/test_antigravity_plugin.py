from __future__ import annotations

import json
import subprocess

from endor_agent_kit.publication.antigravity_plugin import (
    _antigravity_hooks_config,
    _antigravity_plugin_manifest,
    _hook_source,
    antigravity_text,
)


def test_antigravity_hooks_use_documented_hooks_schema_and_plugin_root_placeholder():
    config = _antigravity_hooks_config()

    assert set(config) == {"hooks"}
    hook = config["hooks"]
    assert set(hook) == {"PreInvocation", "PreToolUse", "PostToolUse"}
    assert hook["PreInvocation"] == [
        {
            "type": "command",
            "command": 'bash "${PLUGIN_ROOT:-.}/hooks/suggest-endor-tools.sh" PreInvocation',
            "timeout": 10,
        }
    ]
    assert hook["PreToolUse"][0]["matcher"] == "run_command"
    assert hook["PreToolUse"][0]["hooks"][0]["type"] == "command"
    assert (
        hook["PostToolUse"][0]["matcher"]
        == "write_to_file|replace_file_content|multi_replace_file_content"
    )
    commands = [hook["PreInvocation"][0]["command"]]
    for event in ("PreToolUse", "PostToolUse"):
        for entry in hook[event]:
            commands.extend(item["command"] for item in entry["hooks"])
    # agy 1.3.2 runs hooks with cwd at the plugin root and no PLUGIN_ROOT in
    # the environment, so the "." default is what makes the scripts resolve.
    assert all(command.startswith('bash "${PLUGIN_ROOT:-.}/hooks/') for command in commands)
    assert not any('"${PLUGIN_ROOT}/' in command for command in commands)


def test_antigravity_manifest_declares_marketplace_metadata():
    manifest = _antigravity_plugin_manifest("2.2.2")

    assert manifest["$schema"] == "https://antigravity.google/schemas/v1/plugin.json"
    assert manifest["name"] == "endor-labs-agent-kit"
    assert manifest["displayName"] == "Endor Labs Agent Kit"
    assert manifest["version"] == "2.2.2"
    assert manifest["logo"] == "assets/logo.png"
    assert 120 <= len(manifest["description"]) <= 160
    assert len(manifest["suggestedPrompts"]) == 3
    assert all(prompt.strip() for prompt in manifest["suggestedPrompts"])
    assert manifest["category"] == "Security"
    assert manifest["author"] == {
        "name": "Endor Labs",
        "email": "support@endor.ai",
        "url": "https://www.endorlabs.com/",
    }
    assert manifest["license"] == "MIT"
    assert "skills" not in manifest
    assert "mcpServers" not in manifest
    assert "disabled" not in manifest


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

    # agy 1.3.2 does not substitute ${PLUGIN_ROOT} in skill text, so the
    # helper path must carry the installed-plugin fallback.
    assert (
        '`python3 "${PLUGIN_ROOT:-$HOME/.gemini/config/plugins/endor-labs-agent-kit}'
        '/runtime/summarize_endor_artifact.py" capture -- <argv>`'
        in rendered
    )
    assert "python3 runtime/summarize_endor_artifact.py" not in rendered
    assert '"${PLUGIN_ROOT}/' not in rendered


def _run_hook(path, event: str, payload: dict[str, object]) -> dict[str, object]:
    completed = subprocess.run(
        ["bash", str(path), event],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)
