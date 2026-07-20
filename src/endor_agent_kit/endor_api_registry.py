"""Typed registry of the Endor Labs API surface the knowledge pack may reference.

This mirrors :data:`endor_agent_kit.validator.PUBLIC_MCP_TOOLS` (the allowlist for
Endor MCP tools) but for the ``endorctl api`` *resource kinds* and *filter enum
values* used in the canonical query recipes
(``source/endor-knowledge-pack/query-recipes.yaml``).

Why this exists
---------------
Before this module, Endor resource kinds (``-r Finding``) and filter enums
(``FINDING_CATEGORY_*``, ``CONTEXT_TYPE_*``, the AI SAST evaluation method) lived
only as free text inside query templates. Their correctness against the live
Endor API was asserted by a single hand-written comment in ``query-recipes.yaml``
that pins an OpenAPI sha256 — nothing failed the build if a template referenced
an enum or resource the API does not expose. This registry is the one place
those values are enumerated, so a typo or an unverified new value is caught at
``validate_knowledge_pack`` time (which already runs in CI and the test suite).

It is intentionally a hand-maintained allowlist, not a parse of the OpenAPI: the
spec is pinned by sha256 in ``source/endor-context/provenance.json`` but is not
vendored locally. The allowlist is the cheap, deterministic first line of
defense; a future enhancement can cross-check these sets against the OpenAPI
``FindingCategory`` / ``ContextType`` / ``SystemEvaluationMethod`` enums when
``endor-agent-kit refresh-endor-context`` re-pins the spec.

Keeping it fresh
----------------
These values describe the Endor API surface pinned in
``source/endor-context/provenance.json``. When ``refresh-endor-context`` re-pins
a new OpenAPI sha, reconcile the sets below against the new spec — exactly as the
``FINDING_CATEGORY_*`` provenance comment in ``query-recipes.yaml`` already
instructs for finding categories.

Do NOT hand-edit these sets blind. Regenerate/verify them against the spec:

    python scripts/generate_endor_api_registry.py --check   # report drift, non-zero on drift
    python scripts/generate_endor_api_registry.py --emit    # paste-ready enum literals

The scheduled ``Refresh Endor context`` workflow runs ``--check`` and warns on
drift, so this registry stays a verified projection of the OpenAPI rather than a
hand-maintained guess.
"""

from __future__ import annotations

import re

# endorctl resource kinds (the value after ``-r`` or ``--resource``) the catalog
# may use. The five attested in query-recipes.yaml are the floor; the remainder
# are Endor resources the agent ``instructions.md`` commands query directly,
# mostly via the long ``--resource`` flag (endor-troubleshooter and probe-droid
# diagnostics, package-risk-summary scoring, the legacy SCA agent). This list is
# the complete set actually emitted by any agent today — derived from a kit-wide
# grep of every ``-r``/``--resource`` token across source/ and the generated
# bundles — so it is the single source for the whole catalog.
ENDOR_API_RESOURCES = frozenset(
    {
        # Attested in source/endor-knowledge-pack/query-recipes.yaml templates.
        "Project",
        "Finding",
        "PackageVersion",
        "VersionUpgrade",
        "ScanResult",
        # package-risk-summary / dependency-decision-helper scoring + similarity.
        "Metric",
        "QuerySimilarPackages",
        # remediation / upgrade / dependency family.
        "Vulnerability",
        "Policy",
        "UpgradeImpactAnalysis",
        "DependencyMetadata",
        "CallGraphData",
        # probe-droid onboarding + endor-troubleshooter diagnostic lanes
        # (queried via ``endorctl api list --resource <kind>``).
        "ScanWorkflowResult",
        "ScanWorkflow",
        "ScanProfile",
        "PackageManager",
        "Repository",
        "RepositoryVersion",
        "Installation",
        "SCMCredential",
        "IdentityProvider",
        "PRCommentConfig",
        "NotificationTarget",
        "Exporter",
        # NOTE: Endor malware is queried via Finding + FINDING_CATEGORY_MALWARE.
        # `Malware` / `MalwareDetection*` have v1<Kind> defs in the OpenAPI but are
        # NOT endorctl `-r` resources (live `endorctl api list -r Malware` returns
        # "invalid resource" in auri, 2026-06-30) -- a v1<Kind> def does not imply
        # `-r` is queryable, so they are intentionally excluded here.
        # Endor-ingested repository child resources (cicd-posture repo-evidence
        # upgrade; idiom confirmed live in namespace auri 2026-06-30: payload in
        # ingested_object.raw, parented to Repository via meta.parent_uuid).
        "RepositoryCodeownersFile",
        "RepositoryTagProtection",
    }
)
# Verified 2026-06-30 against the live Endor OpenAPI
# (api.endorlabs.com/download/openapiv2.swagger.json): all but four are present as
# ``v1<Kind>`` message definitions; ``Vulnerability`` and ``Metric`` are
# service-backed resource kinds (resource-kinds docs + live agent usage), and
# ``UpgradeImpactAnalysis`` is a legacy kind NOT in the current spec. The fake
# ``Integration`` placeholder was removed — endor-troubleshooter declares it as a
# resource but never queries it via -r/--resource and the API exposes no such
# kind. Endor's OpenAPI defines many more message kinds (Malware, FindingLog,
# PackageLicense, LinterResult, ...), but a definition does not prove an
# endorctl-queryable resource. This set is intentionally scoped to verified kinds
# that agents emit today and extends only after resource-kind verification.

# Endor filter enum values, grouped by their enum-family prefix. Only tokens that
# match one of these families are policed, so query placeholders
# (``<FINDING_CATEGORY>``, ``<PROJECT_UUID>``) and verdict/prose tokens
# (``NOT_OBSERVED``, ``EXACT_FINDING_FOUND``) are ignored by construction.
# Authoritative enum members projected verbatim from the Endor OpenAPI enum
# definitions (extracted 2026-06-30 from the live swagger). Each family is the
# COMPLETE member set, so the validator accepts every API-valid value and only
# rejects typos / hallucinations. A too-narrow set is as broken as a too-broad
# one — it would reject valid queries.
# Verify current drift with ``scripts/generate_endor_api_registry.py --check``
# rather than recording snapshot-specific hashes or failure claims here.
ENDOR_ENUM_VALUES: dict[str, frozenset[str]] = {
    "FINDING_CATEGORY": frozenset(
        {
            "FINDING_CATEGORY_AI_MODELS",
            "FINDING_CATEGORY_CICD",
            "FINDING_CATEGORY_CONTAINER",
            "FINDING_CATEGORY_GHACTIONS",
            "FINDING_CATEGORY_LICENSE_RISK",
            "FINDING_CATEGORY_MALWARE",
            "FINDING_CATEGORY_OPERATIONAL",
            "FINDING_CATEGORY_SAST",
            "FINDING_CATEGORY_SCA",
            "FINDING_CATEGORY_SCPM",
            "FINDING_CATEGORY_SECRETS",
            "FINDING_CATEGORY_SECURITY",
            "FINDING_CATEGORY_SECURITY_REVIEW",
            "FINDING_CATEGORY_SUPPLY_CHAIN",
            "FINDING_CATEGORY_TOOLS",
            "FINDING_CATEGORY_UNSPECIFIED",
            "FINDING_CATEGORY_VULNERABILITY",
        }
    ),
    "CONTEXT_TYPE": frozenset(
        {
            "CONTEXT_TYPE_CI_RUN",
            "CONTEXT_TYPE_EXTERNAL",
            "CONTEXT_TYPE_MAIN",
            "CONTEXT_TYPE_REF",
            "CONTEXT_TYPE_SBOM",
            "CONTEXT_TYPE_UNSPECIFIED",
        }
    ),
    "SYSTEM_EVALUATION_METHOD": frozenset(
        {
            "SYSTEM_EVALUATION_METHOD_DEFINITION_AI_SAST",
            "SYSTEM_EVALUATION_METHOD_DEFINITION_CIS",
            "SYSTEM_EVALUATION_METHOD_DEFINITION_CONDITIONS",
            "SYSTEM_EVALUATION_METHOD_DEFINITION_MALWARE",
            "SYSTEM_EVALUATION_METHOD_DEFINITION_POLICIES",
            "SYSTEM_EVALUATION_METHOD_DEFINITION_SCORES",
            "SYSTEM_EVALUATION_METHOD_DEFINITION_SECURITY_REVIEW",
            "SYSTEM_EVALUATION_METHOD_DEFINITION_TYPOSQUATTING",
            "SYSTEM_EVALUATION_METHOD_DEFINITION_UNSPECIFIED",
            "SYSTEM_EVALUATION_METHOD_DEFINITION_VULNERABILITIES",
        }
    ),
    "FINDING_LEVEL": frozenset(
        {
            "FINDING_LEVEL_CRITICAL",
            "FINDING_LEVEL_HIGH",
            "FINDING_LEVEL_LOW",
            "FINDING_LEVEL_MEDIUM",
            "FINDING_LEVEL_UNSPECIFIED",
        }
    ),
    "ERROR_CATEGORY": frozenset(
        {
            "ERROR_CATEGORY_OTHER",
            "ERROR_CATEGORY_PRIVATE_REGISTRY",
            "ERROR_CATEGORY_REPOSITORY",
            "ERROR_CATEGORY_TOOLCHAIN",
            "ERROR_CATEGORY_UNSPECIFIED",
        }
    ),
    "POLICY_TYPE": frozenset(
        {
            "POLICY_TYPE_ADMISSION",
            "POLICY_TYPE_EXCEPTION",
            "POLICY_TYPE_FINDING",
            "POLICY_TYPE_FINDING_CFG",
            "POLICY_TYPE_ML_FINDING",
            "POLICY_TYPE_NOTIFICATION",
            "POLICY_TYPE_REMEDIATION",
            "POLICY_TYPE_SYSTEM_FINDING",
            "POLICY_TYPE_UNSPECIFIED",
            "POLICY_TYPE_USER_FINDING",
        }
    ),
    "ECOSYSTEM": frozenset(
        {
            "ECOSYSTEM_AI_MODEL",
            "ECOSYSTEM_APK",
            "ECOSYSTEM_C",
            "ECOSYSTEM_CARGO",
            "ECOSYSTEM_COCOAPOD",
            "ECOSYSTEM_CONAN",
            "ECOSYSTEM_CONTAINER",
            "ECOSYSTEM_DEBIAN",
            "ECOSYSTEM_GEM",
            "ECOSYSTEM_GIT",
            "ECOSYSTEM_GITHUB_ACTION",
            "ECOSYSTEM_GO",
            "ECOSYSTEM_HUGGING_FACE",
            "ECOSYSTEM_MAVEN",
            "ECOSYSTEM_NPM",
            "ECOSYSTEM_NUGET",
            "ECOSYSTEM_PACKAGIST",
            "ECOSYSTEM_PYPI",
            "ECOSYSTEM_RPM",
            "ECOSYSTEM_SBOM",
            "ECOSYSTEM_SWIFT",
            "ECOSYSTEM_UNSPECIFIED",
            "ECOSYSTEM_VSCODE",
        }
    ),
    "FINDING_TAGS": frozenset(
        {
            "FINDING_TAGS_AI",
            "FINDING_TAGS_CI_BLOCKER",
            "FINDING_TAGS_CI_WARNING",
            "FINDING_TAGS_DIRECT",
            "FINDING_TAGS_DISPUTED",
            "FINDING_TAGS_EXCEPTION",
            "FINDING_TAGS_EXPLOITED",
            "FINDING_TAGS_FALSE_POSITIVE",
            "FINDING_TAGS_FIXABLE",
            "FINDING_TAGS_FIX_AVAILABLE",
            "FINDING_TAGS_IGNORED",
            "FINDING_TAGS_INVALID_SECRET",
            "FINDING_TAGS_MALWARE",
            "FINDING_TAGS_NAMESPACE_INTERNAL",
            "FINDING_TAGS_NORMAL",
            "FINDING_TAGS_NOTIFICATION",
            "FINDING_TAGS_PATH_EXTERNAL",
            "FINDING_TAGS_PHANTOM",
            "FINDING_TAGS_POLICY",
            "FINDING_TAGS_POTENTIALLY_REACHABLE_DEPENDENCY",
            "FINDING_TAGS_POTENTIALLY_REACHABLE_FUNCTION",
            "FINDING_TAGS_PRODUCTION",
            "FINDING_TAGS_PROJECT_INTERNAL",
            "FINDING_TAGS_REACHABLE_DEPENDENCY",
            "FINDING_TAGS_REACHABLE_FUNCTION",
            "FINDING_TAGS_SEGMENT_MATCH",
            "FINDING_TAGS_SELF",
            "FINDING_TAGS_SNOOZED",
            "FINDING_TAGS_TEST",
            "FINDING_TAGS_TRANSITIVE",
            "FINDING_TAGS_TRUE_POSITIVE",
            "FINDING_TAGS_UNDER_REVIEW",
            "FINDING_TAGS_UNFIXABLE",
            "FINDING_TAGS_UNREACHABLE_DEPENDENCY",
            "FINDING_TAGS_UNREACHABLE_FUNCTION",
            "FINDING_TAGS_UNSPECIFIED",
            "FINDING_TAGS_VALID_SECRET",
            "FINDING_TAGS_WITHDRAWN",
        }
    ),
}

# Only police resources inside actual endorctl api invocations so GitHub REST,
# Endor MCP, and local-shell recipes are never false-flagged. Match BOTH flag
# forms: the short ``-r Finding`` (used in query-recipes.yaml) and the long
# ``--resource Finding`` / ``--resource=Finding`` (used heavily in agent
# instructions.md). The lookbehind keeps the short ``-r`` branch from matching
# the ``-r`` inside the long ``--resource`` flag -- the only ``--r...`` flag
# endorctl uses here (its namespace recursion flag is ``--traverse``, not
# ``--recursive``).
_ENDORCTL_API_MARKER = "endorctl api"
_RESOURCE_RE = re.compile(r"(?:--resource|(?<![\w-])-r)[=\s]+([A-Z][A-Za-z0-9]*)")
_ENUM_RES = {
    family: re.compile(rf"\b{family}_[A-Z0-9]+(?:_[A-Z0-9]+)*\b")
    for family in ENDOR_ENUM_VALUES
}

_PROVENANCE_HINT = (
    "reconcile against the pinned Endor OpenAPI (source/endor-context/provenance.json) "
    "and add it to endor_api_registry if the live API exposes it"
)


def endor_api_template_errors(prefix: str, template: str) -> list[str]:
    """Return errors for unknown Endor resources / enum values in one query template.

    ``prefix`` is the caller's error-path prefix (e.g.
    ``"query-recipes.yaml recipes[3]"``) so messages match the surrounding
    knowledge-pack validation style. Each unknown resource/enum is reported once.
    """

    if not template:
        return []

    # Ignore <...> placeholders (e.g. <FINDING_CATEGORY>, <ECOSYSTEM>,
    # <PROJECT_UUID>) so a placeholder is never mistaken for a literal enum value.
    template = re.sub(r"<[^>]*>", " ", template)
    errors: list[str] = []

    if _ENDORCTL_API_MARKER in template.lower():
        seen_resources: set[str] = set()
        for resource in _RESOURCE_RE.findall(template):
            if resource in ENDOR_API_RESOURCES or resource in seen_resources:
                continue
            seen_resources.add(resource)
            errors.append(
                f"{prefix}.template: references Endor API resource {resource!r} "
                f"that is not in endor_api_registry.ENDOR_API_RESOURCES; {_PROVENANCE_HINT}"
            )

    for family, pattern in _ENUM_RES.items():
        allowed = ENDOR_ENUM_VALUES[family]
        seen_tokens: set[str] = set()
        for token in pattern.findall(template):
            if token in allowed or token in seen_tokens:
                continue
            seen_tokens.add(token)
            errors.append(
                f"{prefix}.template: references Endor enum {token!r} that is not a "
                f"known {family}_* value in endor_api_registry; {_PROVENANCE_HINT}"
            )

    return errors


def known_enum_families() -> tuple[str, ...]:
    """Return the enum-family prefixes this registry currently policies."""

    return tuple(sorted(ENDOR_ENUM_VALUES))
