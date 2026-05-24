from __future__ import annotations

from pathlib import Path

import pytest

from conftest import repo_root
from endor_agent_kit.compilers import claude_code
from endor_agent_kit.compilers.rendering import (
    indent,
    instructions_for_edition,
    normalize_edition,
    render_action_contracts,
)
from endor_agent_kit.recipe import ActionContract


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
        "Shared rules.\n\nEnterprise rules.\n"
    )
    assert instructions_for_edition(INSTRUCTIONS, "standard") == (
        "Shared rules.\n\nDeveloper rules.\n"
    )


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
