"""Compute upgrade choices that resolve a package's known vulnerabilities.

Pure, side-effect-free logic (no network, no SDK) so it is fully unit-tested.
Given the current version and, per advisory, the versions that fix it, it produces
ranked :class:`UpgradeOption` choices — the content behind the interactive
"pick an upgrade" UI element.

Version comparison is deliberately lightweight and ecosystem-agnostic: it reads
the leading numeric components (major.minor.patch...), tolerating prefixes/suffixes
like ``v0.48.0`` or ``32.0.0-jre``. When a version can't be parsed, it is recorded
in ``data_gaps`` rather than guessed.
"""

from __future__ import annotations

import re

from .models import UpgradeOption

_NUM = re.compile(r"^\d+")


def parse_version(value: str | None) -> tuple[int, ...] | None:
    """Leading numeric components of a version, or None if unparseable.

    ``"3.27.7"`` -> ``(3, 27, 7)``; ``"v0.48.0"`` -> ``(0, 48, 0)``;
    ``"32.0.0-jre"`` -> ``(32, 0, 0)``; ``"latest"`` -> ``None``.
    """

    if not isinstance(value, str):
        return None
    text = value.strip().lstrip("vV")
    parts: list[int] = []
    for chunk in text.replace("_", ".").replace("-", ".").split("."):
        m = _NUM.match(chunk)
        if not m:
            break
        parts.append(int(m.group()))
    return tuple(parts) or None


def _pad(a: tuple[int, ...], b: tuple[int, ...]) -> tuple[tuple[int, ...], tuple[int, ...]]:
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)), b + (0,) * (n - len(b))


def version_jump(current: str | None, target: str | None) -> str:
    """Classify current->target as patch / minor / major / none / unknown."""

    c, t = parse_version(current), parse_version(target)
    if c is None or t is None:
        return "unknown"
    c, t = _pad(c, t)
    if t == c:
        return "none"
    if t[0] != c[0]:
        return "major"
    if len(t) > 1 and t[1] != c[1]:
        return "minor"
    return "patch"


def _ge(a: str, b: str) -> bool:
    """target a >= boundary b, by parsed version (unparseable -> False)."""

    pa, pb = parse_version(a), parse_version(b)
    if pa is None or pb is None:
        return False
    pa, pb = _pad(pa, pb)
    return pa >= pb


def _gt(a: str, b: str | None) -> bool:
    if b is None:
        return True
    pa, pb = parse_version(a), parse_version(b)
    if pa is None or pb is None:
        return False
    pa, pb = _pad(pa, pb)
    return pa > pb


def compute_upgrade_options(
    current_version: str | None,
    vulns: list[tuple[str, list[str]]],
) -> tuple[list[UpgradeOption], list[str]]:
    """Return ``(options, data_gaps)``.

    ``vulns`` is ``[(advisory_id, [fixed_version, ...]), ...]``. For each advisory
    we pick the smallest fixed version greater than the current one; the set of
    those becomes the candidate targets, and the highest fixes everything fixable
    (marked ``recommended``).
    """

    data_gaps: list[str] = []
    if current_version is not None and parse_version(current_version) is None:
        data_gaps.append(f"current_version_unparseable:{current_version}")

    per_vuln_fix: dict[str, str] = {}
    for advisory_id, fixed_versions in vulns:
        candidates = sorted(
            (f for f in fixed_versions if parse_version(f) is not None and _gt(f, current_version)),
            key=lambda f: parse_version(f) or (),
        )
        if candidates:
            per_vuln_fix[advisory_id] = candidates[0]
        else:
            data_gaps.append(f"no_upgrade_fix_known:{advisory_id}")

    if not per_vuln_fix:
        return [], data_gaps

    fixable = set(per_vuln_fix)
    versions = sorted(set(per_vuln_fix.values()), key=lambda v: parse_version(v) or ())
    recommended = versions[-1]  # highest fix boundary → resolves all fixable advisories

    options: list[UpgradeOption] = []
    for version in versions:
        fixes = sorted(a for a, fx in per_vuln_fix.items() if _ge(version, fx))
        options.append(
            UpgradeOption(
                version=version,
                fixes=fixes,
                fixes_all=set(fixes) == fixable,
                jump=version_jump(current_version, version),
                recommended=(version == recommended),
            )
        )
    return options, data_gaps
