"""Derived safety and transport facts for Source Recipes."""

from __future__ import annotations

from dataclasses import dataclass

from endor_agent_kit.recipe import EndorAgentRecipe


@dataclass(frozen=True)
class SourceRecipeSafetyPosture:
    """Behavior-preserving safety view derived from one Source Recipe."""

    recipe: EndorAgentRecipe

    @property
    def is_mutating(self) -> bool:
        return self.recipe.safety_class == "mutating"

    @property
    def uses_mcp(self) -> bool:
        return (
            "mcp" in self.recipe.supported_transports
            or bool(self.recipe.required_endor_mcp_tools)
            or bool(self.recipe.requires_endor_mcp)
        )

    @property
    def uses_endorctl_api(self) -> bool:
        return "endorctl_api" in self.recipe.supported_transports and bool(
            self.recipe.endorctl_api_invocations
        )

    @property
    def requires_endorctl_setup(self) -> bool:
        return self.uses_endorctl_api or self.is_mutating

    @property
    def can_run_commands(self) -> bool:
        return self.recipe.host_capabilities_required.run_commands

    @property
    def can_read_files(self) -> bool:
        return self.recipe.host_capabilities_required.read_files

    @property
    def can_write_files(self) -> bool:
        return self.recipe.host_capabilities_required.write_files

    @property
    def can_open_change_requests(self) -> bool:
        return self.recipe.host_capabilities_required.open_pr


def source_recipe_safety_posture(recipe: EndorAgentRecipe) -> SourceRecipeSafetyPosture:
    """Return the derived Source Recipe Safety Posture for a recipe."""

    return SourceRecipeSafetyPosture(recipe)
