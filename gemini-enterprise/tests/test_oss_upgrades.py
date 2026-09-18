"""Unit tests for the pure upgrade-recommendation logic (no network, no SDK)."""

from __future__ import annotations

from service.oss.upgrades import (
    compute_upgrade_options,
    parse_version,
    version_jump,
)


# -- parse_version ------------------------------------------------------------

def test_parse_version_variants():
    assert parse_version("3.27.7") == (3, 27, 7)
    assert parse_version("v0.48.0") == (0, 48, 0)
    assert parse_version("32.0.0-jre") == (32, 0, 0)
    assert parse_version("2.15") == (2, 15)
    assert parse_version("latest") is None
    assert parse_version(None) is None
    assert parse_version("") is None


# -- version_jump -------------------------------------------------------------

def test_version_jump_classification():
    assert version_jump("2.14.1", "2.14.2") == "patch"
    assert version_jump("2.14.1", "2.15.0") == "minor"
    assert version_jump("2.14.1", "3.0.0") == "major"
    assert version_jump("2.15.0", "2.15.0") == "none"
    assert version_jump("2.14.1", "weird") == "unknown"
    assert version_jump(None, "2.15.0") == "unknown"


# -- compute_upgrade_options --------------------------------------------------

def test_picks_smallest_fix_per_advisory_and_recommends_highest():
    vulns = [
        ("CVE-A", ["2.15.0", "3.0.0"]),   # smallest fix above current is 2.15.0
        ("CVE-B", ["2.16.0"]),
        ("CVE-C", ["2.17.1"]),
    ]
    options, gaps = compute_upgrade_options("2.14.1", vulns)
    assert gaps == []
    assert [o.version for o in options] == ["2.15.0", "2.16.0", "2.17.1"]

    lowest = options[0]
    assert lowest.version == "2.15.0"
    assert lowest.fixes == ["CVE-A"] and not lowest.fixes_all
    assert lowest.jump == "minor"

    top = options[-1]
    assert top.version == "2.17.1"
    assert top.recommended and top.fixes_all
    assert top.fixes == ["CVE-A", "CVE-B", "CVE-C"]


def test_single_advisory_recommends_its_fix():
    options, gaps = compute_upgrade_options("2.14.1", [("CVE-A", ["2.15.0"])])
    assert gaps == []
    assert len(options) == 1
    assert options[0].version == "2.15.0"
    assert options[0].recommended and options[0].fixes_all


def test_already_fixed_version_yields_no_options():
    # Current version is at/above every fix boundary -> nothing to upgrade to.
    options, gaps = compute_upgrade_options("2.17.1", [("CVE-A", ["2.15.0"])])
    assert options == []
    assert gaps == ["no_upgrade_fix_known:CVE-A"]


def test_missing_fix_data_is_reported_not_guessed():
    options, gaps = compute_upgrade_options("1.0.0", [("CVE-A", [])])
    assert options == []
    assert gaps == ["no_upgrade_fix_known:CVE-A"]


def test_unparseable_current_version_recorded():
    options, gaps = compute_upgrade_options("nightly", [("CVE-A", ["2.15.0"])])
    # An unparseable current version can't be compared, so no fix is selectable.
    assert "current_version_unparseable:nightly" in gaps
    assert options == []


def test_mixed_known_and_unknown_fixes():
    vulns = [
        ("CVE-A", ["2.15.0"]),
        ("CVE-B", []),  # no known fix
    ]
    options, gaps = compute_upgrade_options("2.14.1", vulns)
    assert [o.version for o in options] == ["2.15.0"]
    assert "no_upgrade_fix_known:CVE-B" in gaps
    # 2.15.0 resolves every *fixable* advisory (CVE-B has no upgrade fix, so it's
    # surfaced in data_gaps rather than counting against fixes_all).
    assert options[0].fixes == ["CVE-A"] and options[0].fixes_all


def test_no_current_version_treats_every_fix_as_upgrade():
    # current_version None -> every fix version is a candidate upgrade.
    options, gaps = compute_upgrade_options(None, [("CVE-A", ["2.15.0"])])
    assert gaps == []
    assert options and options[0].version == "2.15.0"
    assert options[0].jump == "unknown"  # can't classify jump without a current version
