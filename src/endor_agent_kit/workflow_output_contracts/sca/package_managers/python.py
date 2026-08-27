"""pip, Poetry, Pipenv, and uv dependency-graph audit profiles.

Endor treats Python as one PyPI registry family: pip, Poetry, Pipenv, and uv
all install from PyPI, share `pyproject.toml`, and share `pypi://`
coordinates. The duplicate-inventory ecosystem token is therefore the
registry-level `pypi` for every Python manager, while manager identity comes
from manager-specific lockfiles (`poetry.lock`, `Pipfile`/`Pipfile.lock`,
`uv.lock`/`uv.toml`) and is carried in the audit's `package_manager`.

pip is the family baseline: it has no lockfile, and every pip-format file
(`requirements.txt`, `requirements.in`, `constraints.txt`) is legitimately
produced or consumed by Poetry exports and uv's pip interface, so pip claims
no manager-specific manifests. pip identity comes from the audit's declared
manager over family-shared signals.

Manipulations are mechanism-driven like Gradle and Node: `type` stays null,
the namespaced `mechanism` token carries the construct, and `semantic_effect`
is required. No Python construct removes or aliases a resolved-graph node the
way a JVM exclusion or an npm alias redirect does — pip famously has no
exclusion mechanism, and a fork swap is a manifest edit of the declaration
itself — so the removal and substitution buckets are empty for all four
profiles. Hand-edited lockfiles are overrides with `lockfile_override`
semantics; VCS/URL/path/editable installs and `[tool.uv.sources]` redirects
are overrides with `source_override` semantics.
"""

from __future__ import annotations

import re
from types import MappingProxyType

from endor_agent_kit.workflow_output_contracts.sca.package_managers._base import (
    PackageManagerAuditProfile,
)

# Exact PyPI package coordinate: name==version with a full, immutable PEP 440
# release (optionally with pre/post/dev segments). Ranges (>=, ~=, wildcards)
# and extras are mutable or ambiguous and defeat the graph-safety pin.
PYTHON_REPLACEMENT_RE = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?"
    r"==\d+(?:\.\d+)*(?:(?:a|b|rc)\d+)?(?:\.post\d+)?(?:\.dev\d+)?",
    # ASCII-only so \d cannot admit fullwidth lookalike digits.
    re.ASCII,
)

_SHARED_ECOSYSTEM_ALIASES = frozenset(
    {"pypi", "python", "py", "python3", "python-3"}
)
_SHARED_MANIFEST_BASENAMES = frozenset(
    {
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "requirements.in",
        "constraints.txt",
    }
)
_PYTHON_COORDINATE_PREFIXES = ("pypi://",)

PIP_PROFILE = PackageManagerAuditProfile(
    name="pip",
    display_name="pip",
    # "pip" as an ecosystem token unambiguously names the manager (pypi is
    # the registry token), so it stays a manager-specific alias even though
    # it is non-canonical for the duplicate-inventory key.
    ecosystem_aliases=frozenset({"pip"}),
    # No lockfile and no pip-unique manifest: see module docstring.
    manifest_basenames=frozenset(),
    manifest_suffixes=(),
    coordinate_prefixes=_PYTHON_COORDINATE_PREFIXES,
    native_types=frozenset(),
    override_types=frozenset(),
    removal_types=frozenset(),
    type_driven=False,
    semantic_effect_required=True,
    mechanisms=MappingProxyType(
        {
            "pip.manifest_range": "native",
            "pip.constraints_pin": "override",
            "pip.direct_dependency_override": "override",
            "pip.source_specifier": "override",
        }
    ),
    canonical_ecosystem="pypi",
    shared_ecosystem_aliases=_SHARED_ECOSYSTEM_ALIASES,
    shared_manifest_basenames=_SHARED_MANIFEST_BASENAMES,
    mechanism_semantic_effects=MappingProxyType(
        {
            "pip.source_specifier": frozenset({"source_override"}),
        }
    ),
    replacement_pattern=PYTHON_REPLACEMENT_RE,
    replacement_format="name==version",
)

POETRY_PROFILE = PackageManagerAuditProfile(
    name="poetry",
    display_name="Poetry",
    ecosystem_aliases=frozenset({"poetry"}),
    manifest_basenames=frozenset({"poetry.lock"}),
    manifest_suffixes=(),
    coordinate_prefixes=_PYTHON_COORDINATE_PREFIXES,
    native_types=frozenset(),
    override_types=frozenset(),
    removal_types=frozenset(),
    type_driven=False,
    semantic_effect_required=True,
    mechanisms=MappingProxyType(
        {
            "poetry.manifest_range": "native",
            "poetry.direct_dependency_override": "override",
            "poetry.lockfile_edit": "override",
            "poetry.source_specifier": "override",
        }
    ),
    canonical_ecosystem="pypi",
    shared_ecosystem_aliases=_SHARED_ECOSYSTEM_ALIASES,
    shared_manifest_basenames=_SHARED_MANIFEST_BASENAMES,
    mechanism_semantic_effects=MappingProxyType(
        {
            "poetry.lockfile_edit": frozenset({"lockfile_override"}),
            "poetry.source_specifier": frozenset({"source_override"}),
        }
    ),
    replacement_pattern=PYTHON_REPLACEMENT_RE,
    replacement_format="name==version",
)

PIPENV_PROFILE = PackageManagerAuditProfile(
    name="pipenv",
    display_name="Pipenv",
    ecosystem_aliases=frozenset({"pipenv"}),
    manifest_basenames=frozenset({"pipfile", "pipfile.lock"}),
    manifest_suffixes=(),
    coordinate_prefixes=_PYTHON_COORDINATE_PREFIXES,
    native_types=frozenset(),
    override_types=frozenset(),
    removal_types=frozenset(),
    type_driven=False,
    semantic_effect_required=True,
    mechanisms=MappingProxyType(
        {
            "pipenv.manifest_range": "native",
            "pipenv.direct_dependency_override": "override",
            "pipenv.lockfile_edit": "override",
            "pipenv.source_specifier": "override",
        }
    ),
    canonical_ecosystem="pypi",
    shared_ecosystem_aliases=_SHARED_ECOSYSTEM_ALIASES,
    shared_manifest_basenames=_SHARED_MANIFEST_BASENAMES,
    mechanism_semantic_effects=MappingProxyType(
        {
            "pipenv.lockfile_edit": frozenset({"lockfile_override"}),
            "pipenv.source_specifier": frozenset({"source_override"}),
        }
    ),
    replacement_pattern=PYTHON_REPLACEMENT_RE,
    replacement_format="name==version",
)

UV_PROFILE = PackageManagerAuditProfile(
    name="uv",
    display_name="uv",
    ecosystem_aliases=frozenset({"uv"}),
    manifest_basenames=frozenset({"uv.lock", "uv.toml"}),
    manifest_suffixes=(),
    coordinate_prefixes=_PYTHON_COORDINATE_PREFIXES,
    native_types=frozenset(),
    override_types=frozenset(),
    removal_types=frozenset(),
    type_driven=False,
    semantic_effect_required=True,
    mechanisms=MappingProxyType(
        {
            "uv.manifest_range": "native",
            "uv.override_dependencies": "override",
            "uv.constraint_dependencies": "override",
            "uv.direct_dependency_override": "override",
            "uv.lockfile_edit": "override",
            "uv.source_specifier": "override",
            "uv.sources_redirect": "override",
        }
    ),
    canonical_ecosystem="pypi",
    shared_ecosystem_aliases=_SHARED_ECOSYSTEM_ALIASES,
    shared_manifest_basenames=_SHARED_MANIFEST_BASENAMES,
    mechanism_semantic_effects=MappingProxyType(
        {
            "uv.lockfile_edit": frozenset({"lockfile_override"}),
            "uv.source_specifier": frozenset({"source_override"}),
            "uv.sources_redirect": frozenset({"source_override"}),
        }
    ),
    replacement_pattern=PYTHON_REPLACEMENT_RE,
    replacement_format="name==version",
)
