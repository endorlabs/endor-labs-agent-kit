"""Ruby Bundler dependency-graph audit profile.

Bundler is the only manager for the RubyGems registry, so there is no
registry-family split and no shared weak signals — but unlike Go and NuGet,
the canonical inventory ecosystem is the registry token `gem`, not the
manager name. `Gemfile`/`Gemfile.lock` (and their `gems.rb`/`gems.locked`
spellings) are unambiguous strong signals, as is the `.gemspec` suffix.

Manipulations are mechanism-driven (`type` null, namespaced `mechanism`,
required `semantic_effect`). Bundler resolves the whole graph as one
unified constraint set, so a Gemfile entry added only to force a
transitive's resolved version is forced mediation
(`bundler.transitive_pin`). A hand-edited `Gemfile.lock` is an override
with `lockfile_override` semantics — the lockfile is fully authoritative
under frozen/deployment mode, so a hand-pinned entry silently rules
resolution. A per-gem `git:`/`github:`/`path:` redirect keeps the gem's
name and swaps where its code comes from (`bundler.source_redirect`), and a
`source`-block or mirror swap redirects the registry itself
(`bundler.gem_source`); both are overrides with `source_override`.

The removal bucket is suppression-only: `gem "x", require: false`
(`bundler.require_false`) never removes the gem from the graph — it stays
resolved and pinned in Gemfile.lock while its automatic require at boot is
suppressed, so the effect is `asset_or_feature_suppression` under the same
removal safety rules. Nothing removes a graph node (deleting the gem line
is a manifest edit) and nothing renames a gem (a fork redirect keeps the
name), so `dependency_removal` and `dependency_substitution` are never
claimable through Bundler mechanisms.
"""

from __future__ import annotations

import re
from types import MappingProxyType

from endor_agent_kit.workflow_output_contracts.sca.package_managers._base import (
    PackageManagerAuditProfile,
)

# Exact RubyGems coordinate: gem-name@version with an explicit Gem::Version
# string — at least major.minor, then dot-separated numeric or prerelease
# segments (1.2.3, 7.0.4.3, 1.2.3.rc1). Requirement operators (~>, >=),
# wildcards, and git refs are mutable and defeat the graph-safety pin; no
# gem:// or other scheme prefix. ASCII-only so \d and \w cannot admit
# fullwidth lookalikes.
BUNDLER_REPLACEMENT_RE = re.compile(
    r"[A-Za-z0-9_][A-Za-z0-9_.-]*@\d+\.\d+(?:\.[A-Za-z0-9]+)*",
    re.ASCII,
)

BUNDLER_PROFILE = PackageManagerAuditProfile(
    name="bundler",
    display_name="Bundler",
    ecosystem_aliases=frozenset({"gem", "rubygems", "ruby-gems", "ruby", "bundler"}),
    manifest_basenames=frozenset(
        {"gemfile", "gemfile.lock", "gems.rb", "gems.locked"}
    ),
    manifest_suffixes=(".gemspec",),
    coordinate_prefixes=("gem://",),
    native_types=frozenset(),
    override_types=frozenset(),
    removal_types=frozenset(),
    type_driven=False,
    semantic_effect_required=True,
    canonical_ecosystem="gem",
    mechanisms=MappingProxyType(
        {
            "bundler.gemfile_requirement": "native",
            "bundler.gemspec_requirement": "native",
            "bundler.transitive_pin": "override",
            "bundler.lockfile_edit": "override",
            "bundler.source_redirect": "override",
            "bundler.gem_source": "override",
            "bundler.require_false": "removal",
        }
    ),
    mechanism_semantic_effects=MappingProxyType(
        {
            "bundler.lockfile_edit": frozenset({"lockfile_override"}),
            "bundler.source_redirect": frozenset({"source_override"}),
            "bundler.gem_source": frozenset({"source_override"}),
            "bundler.require_false": frozenset({"asset_or_feature_suppression"}),
        }
    ),
    replacement_pattern=BUNDLER_REPLACEMENT_RE,
    replacement_format="gem@version",
)
