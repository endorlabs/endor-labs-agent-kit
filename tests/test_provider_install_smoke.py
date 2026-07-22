from __future__ import annotations

from pathlib import Path

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


def test_claude_disposable_install_runs_host_plugin_validation(tmp_path: Path) -> None:
    claude_command = tmp_path / "claude"
    claude_command.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "test \"$1\" = plugin\n"
        "test \"$2\" = validate\n"
        "test -f \"$3/hooks/hooks.json\"\n",
        encoding="utf-8",
    )
    claude_command.chmod(0o755)

    result = smoke_test(repo_root(), claude_command=str(claude_command))

    assert result["providers"]["claude"]["cli_validation"] == "passed"


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
