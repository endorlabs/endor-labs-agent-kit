from __future__ import annotations

import json
from pathlib import Path
import subprocess

from scripts.smoke_test_provider_installations import smoke_test

from conftest import repo_root


def test_all_provider_packages_install_in_disposable_roots() -> None:
    result = smoke_test(repo_root())

    assert result["canonical_agent_count"] == 11
    assert set(result["providers"]) == {
        "claude",
        "codex",
        "cursor",
        "gemini",
        "antigravity",
    }
    assert all(item["status"] == "passed" for item in result["providers"].values())


def test_claude_disposable_install_enforces_host_specific_package_boundary() -> None:
    result = smoke_test(repo_root())

    claude = result["providers"]["claude"]
    assert claude["marketplace_source"] == "./plugins/claude/endor-labs-agent-kit"
    assert claude["skills"] == ["endor-agent-kit-setup"]
    assert claude["hook_events"] == ["PostToolUse", "UserPromptSubmit"]
    assert claude["plugin_wide_mcp"] is False


def test_codex_disposable_install_requires_setup_then_installs_custom_agents_only() -> None:
    result = smoke_test(repo_root())

    codex = result["providers"]["codex"]
    assert codex["plugin_skills"] == ["endor-agent-kit-setup"]
    assert codex["installed_custom_agents"] == 12
    assert codex["workflow_skills_installed"] is False


def test_claude_disposable_install_runs_host_plugin_validation(tmp_path: Path) -> None:
    claude_command = tmp_path / "claude"
    claude_command.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "test \"$1\" = plugin\n"
        "test \"$2\" = validate\n"
        "test -f \"$3/hooks/hooks.json\" || "
        "test -f \"$3/.claude-plugin/root-package-guard-hooks.json\"\n",
        encoding="utf-8",
    )
    claude_command.chmod(0o755)

    result = smoke_test(repo_root(), claude_command=str(claude_command))

    assert result["providers"]["claude"]["cli_validation"] == "passed"
    assert result["providers"]["claude"]["root_guard_cli_validation"] == "passed"


def test_claude_plugin_documents_the_host_specific_development_root() -> None:
    readme = (
        repo_root()
        / "plugins"
        / "claude"
        / "endor-labs-agent-kit"
        / "README.md"
    ).read_text(encoding="utf-8")

    assert "claude --plugin-dir plugins/claude/endor-labs-agent-kit" in readme
    assert "Do not run `claude --plugin-dir .`" in readme


def test_claude_repository_root_guard_redirects_agents_and_blocks_prompts() -> None:
    root = repo_root()
    manifest = json.loads(
        (root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    expected_agents = {
        f"./{path.relative_to(root).as_posix()}"
        for path in (
            root / "plugins" / "claude" / "endor-labs-agent-kit" / "agents"
        ).glob("*.md")
    }
    assert set(manifest["agents"]) == expected_agents
    assert manifest["hooks"] == "./.claude-plugin/root-package-guard-hooks.json"

    guard = root / ".claude-plugin" / "reject-repository-root.sh"
    session = subprocess.run(
        ["bash", str(guard), "SessionStart"],
        input="{}",
        text=True,
        capture_output=True,
        check=True,
    )
    session_output = json.loads(session.stdout)
    assert "repository root is the Cursor package" in (
        session_output["hookSpecificOutput"]["additionalContext"]
    )

    prompt = subprocess.run(
        ["bash", str(guard), "UserPromptSubmit"],
        input='{"prompt":"Triage AI SAST findings"}',
        text=True,
        capture_output=True,
        check=False,
    )
    assert prompt.returncode == 2
    assert "plugins/claude/endor-labs-agent-kit" in prompt.stderr
