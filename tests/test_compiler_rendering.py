from __future__ import annotations

from pathlib import Path

import pytest

from conftest import repo_root
from endor_agent_kit.compilers import claude_code
from endor_agent_kit.compilers.rendering import (
    ENDOR_NAMESPACE_PREFLIGHT,
    STRUCTURED_OUTPUT_HEADING,
    indent,
    instructions_for_edition,
    normalize_edition,
    render_action_contracts,
    render_structured_output_contract,
)
from endor_agent_kit.knowledge_pack import PACK_SECTION_HEADING
from endor_agent_kit.recipe import ActionContract, EndorAgentRecipe, HostCapabilities, RecipeField


INSTRUCTIONS = """\
<!-- shared:start -->
Shared rules.
<!-- shared:end -->

<!-- developer-edition:start -->
Developer rules.
<!-- developer-edition:end -->

<!-- enterprise-edition:start -->
Enterprise rules.
<!-- enterprise-edition:end -->
"""


def test_shared_compiler_rendering_extracts_instruction_sections():
    assert instructions_for_edition(INSTRUCTIONS, "enterprise-edition") == (
        f"Shared rules.\n\n{ENDOR_NAMESPACE_PREFLIGHT.rstrip()}\n\nEnterprise rules.\n"
    )
    assert instructions_for_edition(INSTRUCTIONS, "standard") == (
        f"Shared rules.\n\n{ENDOR_NAMESPACE_PREFLIGHT.rstrip()}\n\nDeveloper rules.\n"
    )


def test_shared_compiler_rendering_injects_namespace_preflight():
    rendered = instructions_for_edition(INSTRUCTIONS, "enterprise-edition")

    assert "## Endor Namespace Preflight" in rendered
    assert "`ENDOR_NAMESPACE` and `ENDOR_API_CREDENTIALS_*` are supported inputs" in rendered
    assert "tenant-specific, customer-specific, production, backup" in rendered
    assert "non-default Endor config directories" in rendered


def test_shared_compiler_rendering_injects_knowledge_pack_after_namespace_preflight():
    rendered = instructions_for_edition(
        INSTRUCTIONS,
        "enterprise-edition",
        recipe_id="sca-remediation",
    )

    assert rendered.count(PACK_SECTION_HEADING) == 1
    assert rendered.index("## Endor Namespace Preflight") < rendered.index(PACK_SECTION_HEADING)
    assert rendered.index(PACK_SECTION_HEADING) < rendered.index("Enterprise rules.")
    assert "source recipe instructions remain authoritative" in rendered
    assert "Context first" in rendered
    assert "Agent Task Profiles" in rendered
    assert "`selection-plan` - Selection Plan" in rendered
    assert "Evidence Query Plans" in rendered
    assert "`selection-plan` - Selection Plan Query Plan" in rendered
    assert "Evidence Query Recipes" in rendered
    assert "endorctl api list -r VersionUpgrade -n <namespace>" in rendered


def test_shared_compiler_rendering_injects_structured_contract_before_workflow_steps():
    rendered = instructions_for_edition(
        INSTRUCTIONS,
        "enterprise-edition",
        recipe_id="sca-remediation",
        structured_output_recipe=_recipe_with_outputs(
            RecipeField("summary", "string", required=True),
            RecipeField("data_gaps", "list[string]", required=True),
        ),
    )

    assert rendered.count(STRUCTURED_OUTPUT_HEADING) == 1
    assert rendered.index("## Endor Namespace Preflight") < rendered.index(PACK_SECTION_HEADING)
    assert rendered.index(PACK_SECTION_HEADING) < rendered.index(STRUCTURED_OUTPUT_HEADING)
    assert rendered.index(STRUCTURED_OUTPUT_HEADING) < rendered.index("Enterprise rules.")


def test_shared_compiler_rendering_compact_plugin_profile_omits_marked_blocks():
    instructions = """\
<!-- shared:start -->
Shared rules.
<!-- compact-plugin:omit-start -->
Reference-only details.
<!-- compact-plugin:omit-end -->
Shared tail.
<!-- shared:end -->

<!-- developer-edition:start -->
Developer rules.
<!-- developer-edition:end -->

<!-- enterprise-edition:start -->
Enterprise rules.
<!-- enterprise-edition:end -->
"""

    full = instructions_for_edition(instructions, "enterprise-edition")
    compact = instructions_for_edition(instructions, "enterprise-edition", compact_plugin=True)

    assert "Reference-only details" in full
    assert "compact-plugin:omit" not in full
    assert "Reference-only details" not in compact
    assert "Shared rules." in compact
    assert "Shared tail." in compact


def test_shared_compiler_rendering_compact_profile_includes_task_profiles():
    compact = instructions_for_edition(
        INSTRUCTIONS,
        "enterprise-edition",
        recipe_id="sca-remediation",
        compact_plugin=True,
    )

    assert "Agent Task Profiles" in compact
    assert "Profiles: `resolve-scope`, `evidence-check`, `selection-plan`" in compact
    assert "Profile bounds workflow" in compact
    assert "full only on request" in compact
    assert "Evidence Query Plans" in compact
    assert "Plans: `resolve-scope`, `evidence-check`, `selection-plan`" in compact
    assert "Exact/ranked evidence first; selected detail only" in compact
    assert "VersionUpgrade/UIA before Finding detail; no broad Finding inventory" in compact
    assert "Evidence Query Recipes" in compact
    assert "version-upgrade-summary" in compact
    assert "endorctl api list -r VersionUpgrade -n <namespace>" in compact
    assert "#### `selection-plan` - Selection Plan" not in compact


def test_shared_compiler_rendering_reports_missing_instruction_sections():
    with pytest.raises(ValueError, match="enterprise-edition"):
        instructions_for_edition(
            """\
<!-- shared:start -->
Shared rules.
<!-- shared:end -->

<!-- developer-edition:start -->
Developer rules.
<!-- developer-edition:end -->
""",
            "enterprise-edition",
        )


def test_shared_compiler_rendering_normalizes_legacy_edition_aliases():
    assert normalize_edition("standard") == "developer-edition"
    assert normalize_edition("extended") == "enterprise-edition"

    with pytest.raises(ValueError, match="Unknown Claude Code edition"):
        normalize_edition("unknown")


def test_shared_compiler_rendering_renders_action_contracts():
    action = ActionContract(
        id="open-change-request",
        kind="source_provider",
        safety_class="mutating",
        confirmation_required=True,
        providers=("github", "gitlab"),
        required_host_capabilities=("open_pr",),
        inputs=("title", "body"),
        outputs=("url",),
        availability="requires_adapter",
        notes="Requires explicit approval.",
    )

    rendered = render_action_contracts((action,))

    assert "## Action Contracts" in rendered
    assert "### open-change-request" in rendered
    assert "- confirmation_required: `true`" in rendered
    assert "- providers: `github`, `gitlab`" in rendered
    assert "- required_host_capabilities: `open_pr`" in rendered
    assert "- inputs: `title`, `body`" in rendered
    assert "- outputs: `url`" in rendered
    assert "- notes: Requires explicit approval." in rendered


def test_shared_compiler_rendering_renders_compact_action_contracts():
    action = ActionContract(
        id="open-change-request",
        kind="source_provider",
        safety_class="mutating",
        confirmation_required=True,
        providers=("github", "gitlab"),
        required_host_capabilities=("open_pr",),
        inputs=("title", "body"),
        outputs=("url",),
        availability="requires_adapter",
        notes="Long reference note omitted from compact plugin prompts.",
    )

    rendered = render_action_contracts((action,), compact=True)

    assert "Compact plugin profile" in rendered
    assert "id=`open-change-request`" in rendered
    assert "outputs=`url`" in rendered
    assert "Long reference note" not in rendered


def test_shared_compiler_rendering_renders_structured_output_contract():
    recipe = _recipe_with_outputs(
        RecipeField("verdict", "enum", required=True, description="Decision."),
        RecipeField("conditions", "list[string]", required=True, description="Constraints."),
        RecipeField("summary", "string", required=True, description="Operator summary."),
        RecipeField("evidence_queries", "list[object]", required=True, description="Evidence ledger."),
        RecipeField("data_gaps", "list[string]", required=True, description="Missing evidence."),
        RecipeField("optional_signal", "object", required=False, description="Extra evidence."),
    )

    rendered = render_structured_output_contract(recipe)

    assert rendered.count(STRUCTURED_OUTPUT_HEADING) == 1
    assert rendered.index("`verdict`") < rendered.index("`conditions`")
    assert rendered.index("`conditions`") < rendered.index("`summary`")
    assert "Optional top-level fields when verified" in rendered
    assert '"verdict": "string"' in rendered
    assert '"conditions": []' in rendered
    assert '"query_template_id": "knowledge-pack-recipe-id or null"' in rendered
    assert "`evidence_queries`: only name/resource/source/status/query_template_id" in rendered
    assert "no raw commands" in rendered
    assert "put gaps in top-level `data_gaps`" in rendered
    assert "no raw shell, `endorctl api`, `endorctl scan`, `git`, or `gh` command strings" in rendered
    assert "Record every missing evidence source or blocked lookup in `data_gaps`" in rendered


def test_shared_compiler_rendering_renders_compact_structured_output_contract():
    recipe = _recipe_with_outputs(
        RecipeField("verdict", "enum", required=True),
        RecipeField("conditions", "list[string]", required=True),
        RecipeField("evidence_queries", "list[object]", required=True),
        RecipeField("data_gaps", "list[string]", required=True),
        RecipeField("findings_fixed", "integer", required=False),
    )

    rendered = render_structured_output_contract(recipe, compact=True)

    assert "Required top-level fields, in order" in rendered
    assert "`verdict`, `conditions`, `evidence_queries`, `data_gaps`" in rendered
    assert "`evidence_queries`: only name/resource/source/status/query_template_id" in rendered
    assert "`findings_fixed`:integer" in rendered
    assert "missing inputs return JSON" in rendered
    assert "no raw commands" in rendered
    assert "put gaps in top-level `data_gaps`" in rendered
    assert "```json" not in rendered


def test_shared_compiler_rendering_indents_frontmatter_blocks():
    assert indent("one\n\ntwo", 2) == "  one\n  \n  two"


def test_claude_code_keeps_private_helper_aliases_for_compatibility():
    assert claude_code._instructions_for_edition is instructions_for_edition
    assert claude_code._normalize_edition is normalize_edition
    assert claude_code._render_action_contracts is render_action_contracts
    assert claude_code._indent is indent


def test_non_claude_code_compilers_do_not_import_private_claude_code_rendering_helpers():
    compiler_dir = repo_root() / "src" / "endor_agent_kit" / "compilers"
    for path in (
        compiler_dir / "codex.py",
        compiler_dir / "claude_managed_agents.py",
        compiler_dir / "raw.py",
    ):
        content = Path(path).read_text(encoding="utf-8")
        assert "_instructions_for_edition" not in content
        assert "_render_action_contracts" not in content
        assert "_normalize_edition" not in content
        assert "_indent" not in content


def _recipe_with_outputs(*outputs: RecipeField) -> EndorAgentRecipe:
    return EndorAgentRecipe(
        recipe_schema_version=1,
        id="structured-output-fixture",
        name="Structured Output Fixture",
        version="1.0.0",
        description="Fixture",
        safety_class="read_only",
        supported_transports=("endorctl",),
        host_capabilities_required=HostCapabilities(),
        inputs=(),
        outputs=outputs,
        evals="evals/cases.yaml",
        compatible_hosts=("claude-code",),
        instructions_path="instructions.md",
        model="sonnet",
    )
