"""NuGet (.NET) dependency-graph audit profile.

NuGet is a single-manager family: MSBuild project files (.csproj/.fsproj/
.vbproj), props/targets layers, and the NuGet lock and config files are all
unambiguously .NET, so the canonical inventory ecosystem is `nuget` and the
profile claims no shared weak signals.

Manipulations are mechanism-driven (`type` null, namespaced `mechanism`,
required `semantic_effect`). NuGet resolution is direct-wins over
transitives, and MSBuild layers version authority across files the project
file never shows — the parent-POM analog: a direct PackageReference added
only to pin a transitive, a centrally pinned transitive
(CentralPackageTransitivePinningEnabled), a VersionOverride defeating the
central pin, and a `PackageReference Update` or version property in
Directory.Build.props/.targets are all forced version mediation. A
hand-edited packages.lock.json is an override with `lockfile_override`
semantics (integrity only holds under RestoreLockedMode), and a
nuget.config source redirect (packageSources, package source mapping, local
feed) is an override with `source_override` semantics.

NuGet has a removal bucket, split by what actually leaves the graph: an
MSBuild `<PackageReference Remove>` drops the reference item — true
`dependency_removal` — while ExcludeAssets/PrivateAssets suppresses asset
flow but never removes the node (the package stays resolved and listed in
packages.lock.json), so it is `asset_or_feature_suppression`. There is no
substitution bucket: NuGet has no module-path redirect, and swapping to a
different package ID is a manifest edit, not a resolution-graph construct —
`dependency_substitution` is never claimable through NuGet mechanisms.
"""

from __future__ import annotations

import re
from types import MappingProxyType

from endor_agent_kit.workflow_output_contracts.sca.package_managers._base import (
    PackageManagerAuditProfile,
)

# Exact NuGet package coordinate: PackageId@version with an explicit
# three-or-four-part numeric version, optionally a prerelease segment and
# build metadata. Floating versions (2.*), ranges ([2.3.1,3.0.0)), and
# two-part shorthands are mutable or ambiguous and defeat the graph-safety
# pin; no nuget:// or other scheme prefix. ASCII-only so \d cannot admit
# fullwidth lookalike digits into the version.
NUGET_REPLACEMENT_RE = re.compile(
    r"[A-Za-z0-9_][A-Za-z0-9_.-]*"
    r"@\d+\.\d+\.\d+(?:\.\d+)?(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?",
    re.ASCII,
)

NUGET_PROFILE = PackageManagerAuditProfile(
    name="nuget",
    display_name="NuGet",
    ecosystem_aliases=frozenset({"nuget", "dotnet", "dot-net", ".net"}),
    manifest_basenames=frozenset(
        {"packages.lock.json", "packages.config", "nuget.config"}
    ),
    manifest_suffixes=(".csproj", ".fsproj", ".vbproj", ".props", ".targets"),
    coordinate_prefixes=("nuget://",),
    native_types=frozenset(),
    override_types=frozenset(),
    removal_types=frozenset(),
    type_driven=False,
    semantic_effect_required=True,
    mechanisms=MappingProxyType(
        {
            "nuget.package_reference": "native",
            "nuget.central_package_version": "native",
            "nuget.transitive_pin": "override",
            "nuget.central_transitive_pin": "override",
            "nuget.version_override": "override",
            "nuget.build_props_layer": "override",
            "nuget.lockfile_edit": "override",
            "nuget.restore_source": "override",
            "nuget.exclude_assets": "removal",
            "nuget.package_remove": "removal",
        }
    ),
    mechanism_semantic_effects=MappingProxyType(
        {
            "nuget.lockfile_edit": frozenset({"lockfile_override"}),
            "nuget.restore_source": frozenset({"source_override"}),
            "nuget.exclude_assets": frozenset({"asset_or_feature_suppression"}),
            "nuget.package_remove": frozenset({"dependency_removal"}),
        }
    ),
    replacement_pattern=NUGET_REPLACEMENT_RE,
    replacement_format="package@version",
)
