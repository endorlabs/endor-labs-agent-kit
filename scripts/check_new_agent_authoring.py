#!/usr/bin/env python3
"""Run strict authoring checks for newly added Source Recipes."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def new_agent_recipes(base_ref: str, head_ref: str = "HEAD") -> list[Path]:
    """Return newly added source recipe paths between two git refs."""

    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-status",
            f"{base_ref}...{head_ref}",
            "--",
            "source/agents/*/recipe.yaml",
        ],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    recipes: list[Path] = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        status, path, *_ = line.split("\t")
        if status == "A":
            recipes.append(Path(path))
    return recipes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", required=True, help="Base git ref to compare against")
    parser.add_argument("--head-ref", default="HEAD", help="Head git ref to compare")
    parser.add_argument(
        "--command",
        default="endor-agent-kit",
        help="Agent Kit command to run; use 'python -m endor_agent_kit.cli' in source mode",
    )
    args = parser.parse_args(argv)

    recipes = new_agent_recipes(args.base_ref, args.head_ref)
    if not recipes:
        print("OK: no newly added source agent recipes")
        return 0

    command = args.command.split()
    for recipe in recipes:
        print(f"Strict new-agent authoring check: {recipe}")
        subprocess.run(
            [*command, "authoring-check", str(recipe), "--new-agent"],
            check=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
