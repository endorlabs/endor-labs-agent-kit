from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def recipe_path() -> Path:
    return repo_root() / "agents" / "dependency-decision-helper" / "recipe.yaml"

