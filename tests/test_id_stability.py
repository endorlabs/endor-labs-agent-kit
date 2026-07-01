from __future__ import annotations

from endor_agent_kit.id_stability import check_id_stability, disappeared_ids


def test_disappeared_ids_returns_base_minus_head():
    assert disappeared_ids({"a", "b", "c"}, {"a", "c"}) == {"b"}


def test_disappeared_ids_allows_additions():
    assert disappeared_ids({"a"}, {"a", "b", "c"}) == set()


def test_check_id_stability_passes_when_ids_preserved():
    loader = {"base": {"alpha", "beta"}, "HEAD": {"alpha", "beta", "gamma"}}.__getitem__

    errors = check_id_stability("base", "HEAD", loader=lambda ref, **_: loader(ref))

    assert errors == []


def test_check_id_stability_flags_removed_id():
    refs = {"base": {"alpha", "beta"}, "HEAD": {"alpha"}}

    errors = check_id_stability("base", "HEAD", loader=lambda ref, **_: refs[ref])

    assert len(errors) == 1
    assert "beta" in errors[0]
    assert "immutable" in errors[0]


def test_check_id_stability_flags_rename_as_removed_plus_added():
    # A rename = old id removed + new id added; the removal is what we block.
    refs = {"base": {"alpha", "beta"}, "HEAD": {"alpha", "beta-renamed"}}

    errors = check_id_stability("base", "HEAD", loader=lambda ref, **_: refs[ref])

    assert len(errors) == 1
    assert "beta" in errors[0]


def test_check_id_stability_reports_multiple_sorted():
    refs = {"base": {"a", "b", "c"}, "HEAD": set()}

    errors = check_id_stability("base", "HEAD", loader=lambda ref, **_: refs[ref])

    assert [error.split("'")[1] for error in errors] == ["a", "b", "c"]
