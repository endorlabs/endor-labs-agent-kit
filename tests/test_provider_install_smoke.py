from __future__ import annotations

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
