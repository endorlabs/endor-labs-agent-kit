"""Prepared Source Recipe records used by compilers and publication."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from endor_agent_kit.recipe import (
    ActionContract,
    EndorAgentRecipe,
    load_action_contracts,
    load_recipe,
    read_instructions,
)
from endor_agent_kit.validator import validate_recipe_file


@dataclass(frozen=True)
class PreparedSourceRecipe:
    """Validated Source Recipe plus source files needed for rendering."""

    path: Path
    recipe: EndorAgentRecipe
    instructions: str
    actions: tuple[ActionContract, ...]

    @property
    def source_dir(self) -> Path:
        return self.path.parent

    @property
    def architecture_path(self) -> Path:
        return self.source_dir / "architecture.svg"

    @property
    def action_contracts_path(self) -> Path:
        if not self.recipe.action_contracts_path:
            return self.source_dir / "__no_actions_yaml__"
        return self.source_dir / self.recipe.action_contracts_path


def prepare_source_recipe(recipe_path: str | Path) -> PreparedSourceRecipe:
    """Validate and load one Source Recipe once for downstream rendering."""

    path = Path(recipe_path)
    errors = validate_recipe_file(path)
    if errors:
        raise ValueError("\n".join(errors))

    recipe = load_recipe(path)
    return PreparedSourceRecipe(
        path=path,
        recipe=recipe,
        instructions=read_instructions(path, recipe),
        actions=load_action_contracts(path, recipe),
    )
