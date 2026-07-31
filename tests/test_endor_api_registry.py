from __future__ import annotations

from conftest import repo_root
from endor_agent_kit.endor_api_registry import (
    ENDOR_API_RESOURCES,
    ENDOR_ENUM_VALUES,
    endor_api_template_errors,
    known_enum_families,
)
from endor_agent_kit.knowledge_pack import validate_knowledge_pack
from endor_agent_kit.recipe import load_yaml_file


def test_registry_contains_the_resources_used_by_the_pack():
    assert {
        "Project",
        "Finding",
        "PackageVersion",
        "VersionUpgrade",
        "ScanResult",
    } <= ENDOR_API_RESOURCES


def test_registry_contains_the_enums_used_by_the_pack():
    assert "FINDING_CATEGORY_VULNERABILITY" in ENDOR_ENUM_VALUES["FINDING_CATEGORY"]
    assert "FINDING_CATEGORY_SUPPLY_CHAIN" in ENDOR_ENUM_VALUES["FINDING_CATEGORY"]
    assert "CONTEXT_TYPE_MAIN" in ENDOR_ENUM_VALUES["CONTEXT_TYPE"]
    assert (
        "SYSTEM_EVALUATION_METHOD_DEFINITION_AI_SAST"
        in ENDOR_ENUM_VALUES["SYSTEM_EVALUATION_METHOD"]
    )
    assert known_enum_families() == (
        "CONTEXT_TYPE",
        "ECOSYSTEM",
        "ERROR_CATEGORY",
        "FINDING_CATEGORY",
        "FINDING_LEVEL",
        "FINDING_TAGS",
        "POLICY_TYPE",
        "SYSTEM_EVALUATION_METHOD",
    )


def test_enum_families_match_authoritative_openapi_sets():
    # The full member sets are projected from the Endor OpenAPI. Lock in the
    # corrected breadth (the first draft hand-typed sets were far too narrow).
    assert len(ENDOR_ENUM_VALUES["FINDING_CATEGORY"]) == 17
    assert len(ENDOR_ENUM_VALUES["CONTEXT_TYPE"]) == 6
    assert len(ENDOR_ENUM_VALUES["SYSTEM_EVALUATION_METHOD"]) == 10
    # Previously-missing-but-valid categories must be accepted, not rejected.
    for value in (
        "FINDING_CATEGORY_SCA",
        "FINDING_CATEGORY_SECRETS",
        "FINDING_CATEGORY_MALWARE",
        "FINDING_CATEGORY_LICENSE_RISK",
        "FINDING_CATEGORY_SAST",
    ):
        assert value in ENDOR_ENUM_VALUES["FINDING_CATEGORY"]
    for value in ("CONTEXT_TYPE_REF", "CONTEXT_TYPE_SBOM", "CONTEXT_TYPE_EXTERNAL"):
        assert value in ENDOR_ENUM_VALUES["CONTEXT_TYPE"]


def test_previously_valid_category_is_no_longer_falsely_rejected():
    # FINDING_CATEGORY_SCA is a real API category; the narrow first-draft set
    # would have wrongly flagged it. It must now pass.
    template = (
        "endorctl api list -r Finding -n x --filter "
        "'spec.finding_categories contains FINDING_CATEGORY_SCA' --field-mask uuid -o json"
    )
    assert endor_api_template_errors("recipe", template) == []


def test_integration_pseudo_resource_removed():
    # 'Integration' is not a real Endor API resource kind (absent from spec +
    # docs) and no agent queries it via -r/--resource.
    assert "Integration" not in ENDOR_API_RESOURCES


def test_valid_ai_sast_template_has_no_errors():
    template = (
        "endorctl api list -r Finding -n <namespace> --filter "
        '\'context.type==CONTEXT_TYPE_MAIN and spec.project_uuid=="<PROJECT_UUID>" '
        'and spec.method=="SYSTEM_EVALUATION_METHOD_DEFINITION_AI_SAST"\' '
        '--field-mask "uuid,context.type" --list-all -o json'
    )
    assert endor_api_template_errors("recipe", template) == []


def test_valid_cicd_posture_category_set_has_no_errors():
    template = (
        "endorctl api list -r Finding -n <namespace> --filter "
        "'spec.finding_categories in [FINDING_CATEGORY_SCPM,FINDING_CATEGORY_CICD,"
        "FINDING_CATEGORY_GHACTIONS,FINDING_CATEGORY_SUPPLY_CHAIN]' "
        '--field-mask "uuid" -o json'
    )
    assert endor_api_template_errors("recipe", template) == []


def test_unknown_resource_is_flagged():
    errors = endor_api_template_errors(
        "recipe",
        "endorctl api list -r Frobnicate -n x --field-mask a -o json",
    )
    assert len(errors) == 1
    assert "Frobnicate" in errors[0]
    assert "resource" in errors[0]


def test_agent_attributed_unknown_resource_is_flagged():
    errors = endor_api_template_errors(
        "recipe",
        "endorctl agent api --agent-id findings-browser list -r Frobnicate "
        "-n x --field-mask a -o json",
    )

    assert any("Frobnicate" in error and "resource" in error for error in errors)


def test_long_resource_flag_is_policed():
    # Agents query diagnostic lanes via the long --resource flag, not -r.
    errors = endor_api_template_errors(
        "recipe",
        "endorctl api list --resource Frobnicate --namespace x --field-mask a -o json",
    )
    assert any("Frobnicate" in error and "resource" in error for error in errors)


def test_long_resource_flag_known_resource_is_accepted():
    template = (
        "endorctl api list --resource DependencyMetadata --namespace x "
        '--field-mask "uuid,meta.name" --list-all -o json'
    )
    assert endor_api_template_errors("recipe", template) == []


def test_diagnostic_and_onboarding_resources_are_registered():
    # Every resource any agent emits via -r/--resource (kit-wide grep) must be
    # registered, so extending the validator to scan instructions.md stays green.
    required = {
        "Project",
        "Finding",
        "PackageVersion",
        "VersionUpgrade",
        "ScanResult",
        "Metric",
        "QuerySimilarPackages",
        "Vulnerability",
        "Policy",
        "UpgradeImpactAnalysis",
        "DependencyMetadata",
        "CallGraphData",
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
    }
    missing = required - ENDOR_API_RESOURCES
    assert missing == set(), f"registry missing agent-used resources: {sorted(missing)}"


def test_long_flag_does_not_false_match_other_flags():
    # --recursive / --list-all / --field-mask must not be read as resources.
    template = (
        "endorctl api list -r Finding -n x --field-mask uuid --list-all -o json"
    )
    assert endor_api_template_errors("recipe", template) == []


def test_unknown_finding_category_is_flagged():
    errors = endor_api_template_errors(
        "recipe",
        "endorctl api list -r Finding -n x --filter "
        "'spec.finding_categories contains FINDING_CATEGORY_MADE_UP' --field-mask a -o json",
    )
    assert any("FINDING_CATEGORY_MADE_UP" in error for error in errors)


def test_unknown_context_type_is_flagged():
    errors = endor_api_template_errors(
        "recipe",
        "endorctl api list -r Finding -n x --filter "
        "'context.type==CONTEXT_TYPE_BOGUS' --field-mask a -o json",
    )
    assert any("CONTEXT_TYPE_BOGUS" in error for error in errors)


def test_placeholder_category_is_not_flagged():
    template = (
        "endorctl api list -r Finding -n x --filter "
        "'spec.finding_categories contains <FINDING_CATEGORY>' --field-mask a -o json"
    )
    assert endor_api_template_errors("recipe", template) == []


def test_enum_shaped_placeholders_are_not_flagged():
    # A <...> placeholder must never be read as a literal enum value, even when it
    # is shaped like one (e.g. <ECOSYSTEM_ENUM>, <FINDING_CATEGORY_X>).
    template = (
        "endorctl api list -r Finding -n <namespace> --filter "
        "'spec.ecosystem==<ECOSYSTEM> and spec.finding_categories contains <FINDING_CATEGORY_X>' "
        '--field-mask "uuid" -o json'
    )
    assert endor_api_template_errors("recipe", template) == []


def test_uuid_placeholders_and_prose_tokens_are_not_flagged():
    template = "endorctl api get -r ScanResult -n x --uuid <SCAN_RESULT_UUID> -o json"
    assert endor_api_template_errors("recipe", template) == []


def test_non_endorctl_templates_skip_resource_check():
    assert (
        endor_api_template_errors(
            "recipe",
            "GitHub REST GET /repos/<owner>/<repo>/branches/<default_branch>/protection",
        )
        == []
    )
    assert (
        endor_api_template_errors(
            "recipe",
            "get_endor_vulnerability(vulnerability_id=<CVE_OR_GHSA>, namespace=<namespace>)",
        )
        == []
    )


def test_each_unknown_token_is_reported_once():
    template = (
        "endorctl api list -r Frobnicate -n x --filter "
        "'context.type==CONTEXT_TYPE_BOGUS and other==CONTEXT_TYPE_BOGUS' "
        "-r Frobnicate --field-mask a -o json"
    )
    errors = endor_api_template_errors("recipe", template)
    assert sum("Frobnicate" in error for error in errors) == 1
    assert sum("CONTEXT_TYPE_BOGUS" in error for error in errors) == 1


def test_registry_covers_every_resource_emitted_by_any_agent_source():
    """Kit-wide guard: every Endor resource an agent actually queries via
    ``-r``/``--resource`` (in query-recipes, workflows, or instructions.md) must
    be registered. If a new agent adds a resource, this fails until it is added.
    """

    import re

    root = repo_root()
    scanned = [
        root / "source" / "endor-knowledge-pack" / "query-recipes.yaml",
        *(root / "source" / "endor-knowledge-pack" / "workflows").glob("*.yaml"),
        *(root / "source" / "agents").glob("*/instructions.md"),
    ]
    # Long form is unambiguous (only endorctl uses --resource); short -r is only
    # trusted on lines that mention endorctl/api to avoid shell `grep -r` etc.
    long_re = re.compile(r"--resource[=\s]+([A-Z][A-Za-z0-9]*)")
    short_re = re.compile(r"(?<![\w-])-r[=\s]+([A-Z][A-Za-z0-9]*)")

    used: set[str] = set()
    for path in scanned:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            used.update(long_re.findall(line))
            if "endorctl" in line or "api list" in line or "api get" in line or "api create" in line:
                used.update(short_re.findall(line))

    assert used, "expected to find endorctl resources in source"
    unregistered = used - ENDOR_API_RESOURCES
    assert unregistered == set(), (
        f"agent source references unregistered Endor resources: {sorted(unregistered)} "
        "(add them to endor_api_registry.ENDOR_API_RESOURCES after verifying against the pinned OpenAPI)"
    )


def test_committed_knowledge_pack_uses_only_registered_resources_and_enums():
    """The committed query-recipes.yaml must reference only registered API
    surface, so wiring the registry into validate_knowledge_pack stays green."""

    agent_ids = {
        str(load_yaml_file(path)["id"])
        for path in (repo_root() / "source" / "agents").glob("*/recipe.yaml")
    }
    errors = validate_knowledge_pack(agent_ids=agent_ids)
    registry_errors = [error for error in errors if "endor_api_registry" in error]
    assert registry_errors == []
    assert errors == []
