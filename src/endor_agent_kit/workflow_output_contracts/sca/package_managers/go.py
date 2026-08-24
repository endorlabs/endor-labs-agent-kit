"""Go modules dependency-graph audit profile.

Go is a single-manager family: go.mod declares requirements, go.sum carries
integrity checksums, and MVS resolves versions deterministically — there is
no registry-family split, so the canonical inventory ecosystem is `go` and
the profile claims no shared weak signals.

Manipulations are mechanism-driven (`type` null, namespaced `mechanism`,
required `semantic_effect`). The `replace` directive splits into three
mechanisms because its shapes have different semantics: a same-path version
redirect is forced version mediation; a filesystem path (or go.work /
drifted vendor) redirect is an override with `source_override`; a
different-module-path redirect is a substitution requiring an exact
`module@version` replacement. `exclude` removes a VERSION from the MVS
candidate set, never the module node — it mediates version selection, so it
is an override construct, and `dependency_removal` is never claimable
through Go mechanisms. A hand-edited go.sum is an override with
`lockfile_override` semantics (checksum swaps defeat integrity, the Go
analog of a hand-edited lockfile).
"""

from __future__ import annotations

import re
from types import MappingProxyType

from endor_agent_kit.workflow_output_contracts.sca.package_managers._base import (
    PackageManagerAuditProfile,
)

# Exact Go module coordinate: module/path@vX.Y.Z with a full semver version,
# optionally a prerelease segment (which also covers pseudo-versions like
# v0.0.0-20260819120000-abcdef123456) and the +incompatible marker. Queries
# (@latest, @master, @v3) are mutable and defeat the graph-safety pin; no
# go:// or other scheme prefix.
GO_REPLACEMENT_RE = re.compile(
    r"[a-z0-9][A-Za-z0-9.-]*(?:/[A-Za-z0-9._~-]+)*"
    r"@v\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+incompatible)?",
    # ASCII-only so \d cannot admit fullwidth lookalike digits.
    re.ASCII,
)

GO_PROFILE = PackageManagerAuditProfile(
    name="go",
    display_name="Go",
    ecosystem_aliases=frozenset({"go", "golang", "gomod", "go-mod", "go-modules"}),
    manifest_basenames=frozenset({"go.mod", "go.sum", "go.work", "go.work.sum"}),
    manifest_suffixes=(),
    coordinate_prefixes=("go://",),
    native_types=frozenset(),
    override_types=frozenset(),
    removal_types=frozenset(),
    type_driven=False,
    semantic_effect_required=True,
    mechanisms=MappingProxyType(
        {
            "go.require_directive": "native",
            "go.replace_version": "override",
            "go.exclude_directive": "override",
            "go.sum_edit": "override",
            "go.replace_path": "override",
            "go.work_replace": "override",
            "go.vendor_override": "override",
            "go.replace_module": "substitution",
        }
    ),
    mechanism_semantic_effects=MappingProxyType(
        {
            "go.sum_edit": frozenset({"lockfile_override"}),
            "go.replace_path": frozenset({"source_override"}),
            "go.work_replace": frozenset({"source_override"}),
            "go.vendor_override": frozenset({"source_override"}),
        }
    ),
    replacement_pattern=GO_REPLACEMENT_RE,
    replacement_format="module@version",
)
