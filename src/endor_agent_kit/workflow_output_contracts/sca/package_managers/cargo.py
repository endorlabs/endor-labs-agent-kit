"""Rust Cargo dependency-graph audit profile.

Cargo is the only manager for the crates.io registry: no registry-family
split, no shared weak signals, and the canonical inventory ecosystem is the
manager name `cargo`. `Cargo.toml`/`Cargo.lock` are unambiguous strong
signals. `.cargo/config.toml` carries the source-replacement mechanism but
is deliberately NOT a detection signal — a bare `config.toml` basename is
too generic to identify the family.

Manipulations are mechanism-driven (`type` null, namespaced `mechanism`,
required `semantic_effect`). Cargo unifies semver-compatible requirements
to one resolved version, so an exact `=` requirement added only to
constrain a transitive's unified resolution is forced mediation
(`cargo.transitive_pin`), and a `Cargo.lock` held at a version a fresh
resolution would not pick is an override with `lockfile_override`
semantics (`cargo.lockfile_pin` — the lock is authoritative under
`--locked`/`--frozen`). The `[patch]`/`[replace]` sections split by shape
like Go's replace: a same-crate version redirect is forced mediation
(`cargo.patch_version`), while a git/path redirect keeps the crate's name
and swaps its source (`cargo.patch_source`), as does a
`.cargo/config.toml` source replacement or vendor/mirror redirect
(`cargo.source_replacement`) — both `source_override`.

Cargo is the first single-manager family with BOTH removal and
substitution buckets (among all families only Gradle carries both). Disabling features (`default-features = false`,
trimmed feature lists — `cargo.feature_suppression`) suppresses
feature-gated code paths, and because optional dependencies are
feature-activated it can also drop whole nodes from the resolved graph, so
both `asset_or_feature_suppression` and `dependency_removal` are
legitimate effects, chosen by what actually left the graph. A dependency
alias (`name = { package = "other-crate", ... }` —
`cargo.package_rename`) makes the code depend on one name while resolving
a different crate: a substitution requiring an exact `crate@version`
replacement.
"""

from __future__ import annotations

import re
from types import MappingProxyType

from endor_agent_kit.workflow_output_contracts.sca.package_managers._base import (
    PackageManagerAuditProfile,
)

# Exact crates.io coordinate: crate-name@version with a full semver version,
# optionally a prerelease segment and build metadata. Requirement operators
# (^, ~, =, >=), wildcards, partial versions, and git refs are mutable or
# ambiguous and defeat the graph-safety pin; no cargo:// or other scheme
# prefix. ASCII-only so \d cannot admit fullwidth lookalike digits.
CARGO_REPLACEMENT_RE = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9_-]*"
    r"@\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?",
    re.ASCII,
)

CARGO_PROFILE = PackageManagerAuditProfile(
    name="cargo",
    display_name="Cargo",
    ecosystem_aliases=frozenset({"cargo", "crates", "crates-io", "crates.io", "rust"}),
    manifest_basenames=frozenset({"cargo.toml", "cargo.lock"}),
    manifest_suffixes=(),
    coordinate_prefixes=("cargo://",),
    native_types=frozenset(),
    override_types=frozenset(),
    removal_types=frozenset(),
    type_driven=False,
    semantic_effect_required=True,
    mechanisms=MappingProxyType(
        {
            "cargo.manifest_requirement": "native",
            "cargo.workspace_dependency": "native",
            "cargo.transitive_pin": "override",
            "cargo.lockfile_pin": "override",
            "cargo.patch_version": "override",
            "cargo.patch_source": "override",
            "cargo.source_replacement": "override",
            "cargo.feature_suppression": "removal",
            "cargo.package_rename": "substitution",
        }
    ),
    mechanism_semantic_effects=MappingProxyType(
        {
            "cargo.lockfile_pin": frozenset({"lockfile_override"}),
            "cargo.patch_source": frozenset({"source_override"}),
            "cargo.source_replacement": frozenset({"source_override"}),
            "cargo.feature_suppression": frozenset(
                {"asset_or_feature_suppression", "dependency_removal"}
            ),
        }
    ),
    replacement_pattern=CARGO_REPLACEMENT_RE,
    replacement_format="crate@version",
)
