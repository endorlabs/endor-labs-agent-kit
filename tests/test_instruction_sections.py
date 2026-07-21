from __future__ import annotations

from endor_agent_kit.instruction_sections import parse_instruction_sections


def test_instruction_scanner_preserves_interleaved_region_order_and_full_body() -> None:
    instructions = """\
<!-- shared:start -->
Shared lead.
<!-- section:invariants:start -->
Invariant block.
<!-- section:invariants:end -->
Shared middle.
<!-- profile:evidence-check:start -->
Evidence-only block.
<!-- profile:evidence-check:end -->
<!-- profile:selection-plan:start -->
Selection-only block.
<!-- profile:selection-plan:end -->
Shared tail.
<!-- shared:end -->

<!-- developer-edition:start -->
Developer only.
<!-- developer-edition:end -->

<!-- enterprise-edition:start -->
Enterprise only.
<!-- enterprise-edition:end -->
"""

    sections = parse_instruction_sections(instructions)

    assert [region.kind for region in sections.shared_regions] == [
        "unmarked",
        "section",
        "unmarked",
        "profile",
        "unmarked",
        "profile",
        "unmarked",
    ]
    assert sections.sections["invariants"].body.strip() == "Invariant block."
    assert sections.profiles["evidence-check"].body.strip() == "Evidence-only block."
    assert sections.shared.index("Shared lead.") < sections.shared.index("Invariant block.")
    assert sections.shared.index("Invariant block.") < sections.shared.index("Evidence-only block.")
    scoped = sections.scoped_shared(profile_id="evidence-check", included_sections=("invariants",))
    assert "Shared lead." in scoped
    assert "Invariant block." in scoped
    assert "Evidence-only block." in scoped
    assert "Selection-only block." not in scoped
    assert sections.for_edition("developer-edition") == "Developer only."
    assert "Developer only." not in sections.for_edition("enterprise-edition")


def test_instruction_scanner_rejects_overlapping_markers() -> None:
    instructions = """\
<!-- shared:start -->
<!-- section:invariants:start -->
<!-- profile:evidence-check:start -->
Invalid nesting.
<!-- profile:evidence-check:end -->
<!-- section:invariants:end -->
<!-- shared:end -->
<!-- developer-edition:start -->Developer<!-- developer-edition:end -->
<!-- enterprise-edition:start -->Enterprise<!-- enterprise-edition:end -->
"""

    try:
        parse_instruction_sections(instructions)
    except ValueError as exc:
        assert "cannot overlap or nest" in str(exc)
    else:
        raise AssertionError("overlapping markers must fail")


def test_instruction_scanner_rejects_addressable_marker_outside_top_level_body() -> None:
    instructions = """\
<!-- profile:evidence-check:start -->outside<!-- profile:evidence-check:end -->
<!-- shared:start -->Shared<!-- shared:end -->
<!-- developer-edition:start -->Developer<!-- developer-edition:end -->
<!-- enterprise-edition:start -->Enterprise<!-- enterprise-edition:end -->
"""

    try:
        parse_instruction_sections(instructions)
    except ValueError as exc:
        assert "inside a top-level instruction body" in str(exc)
    else:
        raise AssertionError("addressable markers outside top-level bodies must fail")
