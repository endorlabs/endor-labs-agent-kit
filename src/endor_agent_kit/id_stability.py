"""Agent id immutability gate.

An agent's ``id`` is the telemetry join key the Agents Hub uses to map a catalog
card to its usage data. Renaming or removing an id silently orphans that data, so
once an id reaches ``main`` it must never disappear. This module compares the ids
present on a base ref to the ids on the PR head and reports any that vanished.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
import subprocess

import yaml

IdLoader = Callable[..., set[str]]


def disappeared_ids(base_ids: Iterable[str], head_ids: Iterable[str]) -> set[str]:
    """Return ids present on the base but missing on the head."""

    return set(base_ids) - set(head_ids)


def agent_ids_at_ref(ref: str, *, root: Path | str = ".") -> set[str]:
    """Return the set of recipe ids declared under ``source/agents`` at a git ref."""

    listing = subprocess.run(
        ["git", "-C", str(root), "ls-tree", "-r", "--name-only", ref, "--", "source/agents"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    ids: set[str] = set()
    for path in listing.stdout.splitlines():
        if not path.endswith("/recipe.yaml"):
            continue
        blob = subprocess.run(
            ["git", "-C", str(root), "show", f"{ref}:{path}"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        data = yaml.safe_load(blob.stdout) or {}
        recipe_id = data.get("id") if isinstance(data, dict) else None
        if isinstance(recipe_id, str) and recipe_id:
            ids.add(recipe_id)
    return ids


def legacy_ids_at_ref(ref: str, *, root: Path | str = ".") -> set[str]:
    """Return legacy ids explicitly claimed by recipes at a git ref."""

    listing = subprocess.run(
        ["git", "-C", str(root), "ls-tree", "-r", "--name-only", ref, "--", "source/agents"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    legacy_ids: set[str] = set()
    for path in listing.stdout.splitlines():
        if not path.endswith("/recipe.yaml"):
            continue
        blob = subprocess.run(
            ["git", "-C", str(root), "show", f"{ref}:{path}"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        data = yaml.safe_load(blob.stdout) or {}
        values = data.get("legacy_ids", ()) if isinstance(data, dict) else ()
        if isinstance(values, list):
            legacy_ids.update(value for value in values if isinstance(value, str) and value)
    return legacy_ids


def check_id_stability(
    base_ref: str,
    head_ref: str = "HEAD",
    *,
    root: Path | str = ".",
    loader: IdLoader = agent_ids_at_ref,
    legacy_loader: IdLoader | None = None,
) -> list[str]:
    """Return errors for ids removed without an explicit canonical legacy alias."""

    base_ids = loader(base_ref, root=root)
    head_ids = loader(head_ref, root=root)
    if legacy_loader is not None:
        preserved_legacy_ids = legacy_loader(head_ref, root=root)
    elif loader is agent_ids_at_ref:
        preserved_legacy_ids = legacy_ids_at_ref(head_ref, root=root)
    else:
        preserved_legacy_ids = set()
    return [
        f"id {recipe_id!r} present on {base_ref} is missing on {head_ref}; "
        "agent ids are immutable (telemetry join key) -- restore it or claim it in exactly "
        "one canonical recipe's legacy_ids"
        for recipe_id in sorted(disappeared_ids(base_ids, head_ids | preserved_legacy_ids))
    ]
