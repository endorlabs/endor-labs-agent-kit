from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from conftest import repo_root


pytestmark = pytest.mark.release

BASELINE_COMMIT = "92d24a749dc3bd9ec168db7bb1362282e3e7f9ec"


def _git(*args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo_root()), *args],
        check=True,
        capture_output=True,
    ).stdout


def _is_preexisting_prompt(path: str) -> bool:
    parts = Path(path).parts
    if path == "catalog.json":
        return True
    if len(parts) >= 3 and parts[0] == "claude-code" and path.endswith(".md"):
        return Path(path).name != "README.md"
    if len(parts) >= 3 and parts[0] == "claude-managed-agents":
        return Path(path).name in {"agent.yaml", "environment.yaml", "session-template.yaml"}
    if len(parts) >= 3 and parts[0] == "codex" and Path(path).name == "SKILL.md":
        return True
    if len(parts) >= 3 and parts[0] == "gemini":
        return Path(path).name == "SKILL.md" or (
            path.endswith(".md") and Path(path).name != "README.md"
        )
    if len(parts) >= 3 and parts[0] == "portable" and Path(path).name == "agent.md":
        return True
    if parts[:2] == ("plugins", "claude"):
        return "/agents/" in path and path.endswith(".md") or path.endswith("/SKILL.md")
    if parts[:2] == ("plugins", "codex"):
        return path.endswith("/SKILL.md") or path.endswith(".toml")
    if parts[:2] in {("plugins", "gemini"), ("plugins", "antigravity")}:
        return path.endswith("/SKILL.md") or "/agents/" in path and path.endswith(".md")
    if parts and parts[0] == "agents" and path.endswith(".md"):
        return True
    if parts and parts[0] == "skills" and Path(path).name == "SKILL.md":
        return True
    return parts[:2] == ("cursor-sdk", "agents") and path.endswith(".md")


def test_preexisting_prompt_and_backend_catalog_bytes_match_frozen_baseline():
    try:
        paths = _git("ls-tree", "-r", "--name-only", BASELINE_COMMIT).decode().splitlines()
    except subprocess.CalledProcessError:
        pytest.skip(f"baseline commit {BASELINE_COMMIT} is unavailable")

    selected = sorted(path for path in paths if _is_preexisting_prompt(path))
    assert "catalog.json" in selected
    assert len(selected) >= 100
    drift = []
    for relative in selected:
        current = repo_root() / relative
        if not current.is_file() or current.read_bytes() != _git(
            "show",
            f"{BASELINE_COMMIT}:{relative}",
        ):
            drift.append(relative)
    assert drift == []
