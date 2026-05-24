"""Coordinator for host artifact publication."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from endor_agent_kit.recipe import EndorAgentRecipe

from .records import BundleRecord


class HostAdapter(Protocol):
    """Host-specific publication adapter."""

    host: str

    def publish(
        self,
        recipe_file: Path,
        recipe: EndorAgentRecipe,
        destination: Path,
    ) -> BundleRecord:
        """Publish one host artifact bundle."""


class HostArtifactPublication:
    """Coordinate publication through host adapters."""

    def __init__(self, adapters: dict[str, HostAdapter]):
        self._adapters = adapters

    def publish(
        self,
        host: str,
        recipe_file: Path,
        recipe: EndorAgentRecipe,
        destination: Path,
    ) -> BundleRecord:
        """Publish one host artifact bundle."""

        try:
            adapter = self._adapters[host]
        except KeyError as exc:
            raise ValueError(f"Unsupported publication host {host!r}") from exc
        return adapter.publish(recipe_file, recipe, destination)
