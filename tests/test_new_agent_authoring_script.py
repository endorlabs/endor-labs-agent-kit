from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.check_new_agent_authoring import new_agent_recipes


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, stdout=subprocess.PIPE)


def _write(repo: Path, path: str, text: str = "content\n") -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def test_new_agent_recipes_returns_added_source_recipes_only(tmp_path, monkeypatch):
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    _write(tmp_path, "source/agents/existing/recipe.yaml")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "initial")
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()

    _write(tmp_path, "source/agents/new-agent/recipe.yaml")
    _write(tmp_path, "source/agents/existing/instructions.md")
    _write(tmp_path, "README.md")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "change")

    monkeypatch.chdir(tmp_path)

    assert new_agent_recipes(base) == [Path("source/agents/new-agent/recipe.yaml")]
