"""npm, Yarn, and pnpm dependency-graph audit profiles.

Endor treats JavaScript/TypeScript as one npm-registry family: npm, Yarn, and
pnpm all install from the npm registry, share `package.json`, and share
`npm://` coordinates. The duplicate-inventory ecosystem token is therefore the
registry-level `npm` for every Node manager, while manager identity comes from
manager-specific lockfiles and config files and is carried in the audit's
`package_manager`. Manipulations are mechanism-driven like Gradle: `type`
stays null, the namespaced `mechanism` token carries the construct, and
`semantic_effect` is required.

No Node construct removes a resolved-graph node the way a JVM exclusion does,
so the removal bucket is empty for all three profiles: hand-edited lockfiles
are overrides with `lockfile_override` semantics, and git/file/link/portal
redirections are overrides with `source_override` semantics.
"""

from __future__ import annotations

import re
from types import MappingProxyType

from endor_agent_kit.workflow_output_contracts.sca.package_managers._base import (
    PackageManagerAuditProfile,
)

# Exact npm package coordinate: name@version or @scope/name@version, with no
# npm:// or other scheme prefix. The version must be a full, immutable semver
# (optionally with prerelease/build metadata) — dist-tags (latest, next) and
# x-ranges (1, 1.x, 1.2.x) are mutable and defeat the graph-safety pin.
NODE_REPLACEMENT_RE = re.compile(
    r"(?:@[A-Za-z0-9._-]+/)?[A-Za-z0-9._-]+"
    r"@\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?"
)

_SHARED_ECOSYSTEM_ALIASES = frozenset(
    {"npm", "node", "nodejs", "node-js", "javascript", "typescript", "js"}
)
_SHARED_MANIFEST_BASENAMES = frozenset({"package.json"})
_NODE_COORDINATE_PREFIXES = ("npm://",)

NPM_PROFILE = PackageManagerAuditProfile(
    name="npm",
    display_name="npm",
    # npm-the-manager cannot be told apart from npm-the-registry by ecosystem
    # token alone, so it claims no manager-specific ecosystem aliases.
    ecosystem_aliases=frozenset(),
    manifest_basenames=frozenset({"package-lock.json", "npm-shrinkwrap.json"}),
    manifest_suffixes=(),
    coordinate_prefixes=_NODE_COORDINATE_PREFIXES,
    native_types=frozenset(),
    override_types=frozenset(),
    removal_types=frozenset(),
    type_driven=False,
    semantic_effect_required=True,
    mechanisms=MappingProxyType(
        {
            "npm.manifest_range": "native",
            "npm.overrides": "override",
            "npm.lockfile_edit": "override",
            "npm.source_specifier": "override",
            "npm.alias_redirect": "substitution",
        }
    ),
    canonical_ecosystem="npm",
    shared_ecosystem_aliases=_SHARED_ECOSYSTEM_ALIASES,
    shared_manifest_basenames=_SHARED_MANIFEST_BASENAMES,
    mechanism_semantic_effects=MappingProxyType(
        {
            "npm.lockfile_edit": frozenset({"lockfile_override"}),
            "npm.source_specifier": frozenset({"source_override"}),
        }
    ),
    replacement_pattern=NODE_REPLACEMENT_RE,
    replacement_format="name@version",
)

YARN_PROFILE = PackageManagerAuditProfile(
    name="yarn",
    display_name="Yarn",
    ecosystem_aliases=frozenset({"yarn", "yarn-classic", "yarn-berry"}),
    manifest_basenames=frozenset({"yarn.lock", ".yarnrc.yml", ".yarnrc"}),
    manifest_suffixes=(),
    coordinate_prefixes=_NODE_COORDINATE_PREFIXES,
    native_types=frozenset(),
    override_types=frozenset(),
    removal_types=frozenset(),
    type_driven=False,
    semantic_effect_required=True,
    mechanisms=MappingProxyType(
        {
            "yarn.manifest_range": "native",
            "yarn.resolutions": "override",
            "yarn.lockfile_edit": "override",
            "yarn.patch_protocol": "override",
            "yarn.source_protocol": "override",
            "yarn.alias_redirect": "substitution",
        }
    ),
    canonical_ecosystem="npm",
    shared_ecosystem_aliases=_SHARED_ECOSYSTEM_ALIASES,
    shared_manifest_basenames=_SHARED_MANIFEST_BASENAMES,
    mechanism_semantic_effects=MappingProxyType(
        {
            "yarn.lockfile_edit": frozenset({"lockfile_override"}),
            "yarn.patch_protocol": frozenset({"source_override"}),
            "yarn.source_protocol": frozenset({"source_override"}),
        }
    ),
    replacement_pattern=NODE_REPLACEMENT_RE,
    replacement_format="name@version",
)

PNPM_PROFILE = PackageManagerAuditProfile(
    name="pnpm",
    display_name="pnpm",
    ecosystem_aliases=frozenset({"pnpm"}),
    manifest_basenames=frozenset(
        {"pnpm-lock.yaml", "pnpm-workspace.yaml", ".pnpmfile.cjs"}
    ),
    manifest_suffixes=(),
    coordinate_prefixes=_NODE_COORDINATE_PREFIXES,
    native_types=frozenset(),
    override_types=frozenset(),
    removal_types=frozenset(),
    type_driven=False,
    semantic_effect_required=True,
    mechanisms=MappingProxyType(
        {
            "pnpm.manifest_range": "native",
            "pnpm.overrides": "override",
            "pnpm.lockfile_edit": "override",
            "pnpm.source_specifier": "override",
            "pnpm.pnpmfile_hook": "override",
            "pnpm.alias_redirect": "substitution",
        }
    ),
    canonical_ecosystem="npm",
    shared_ecosystem_aliases=_SHARED_ECOSYSTEM_ALIASES,
    shared_manifest_basenames=_SHARED_MANIFEST_BASENAMES,
    mechanism_semantic_effects=MappingProxyType(
        {
            "pnpm.lockfile_edit": frozenset({"lockfile_override"}),
            "pnpm.source_specifier": frozenset({"source_override"}),
        }
    ),
    replacement_pattern=NODE_REPLACEMENT_RE,
    replacement_format="name@version",
)
