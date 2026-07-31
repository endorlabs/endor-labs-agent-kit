from __future__ import annotations

from endor_agent_kit.endor_api_registry import ENDOR_API_RESOURCES, ENDOR_ENUM_VALUES
from scripts.generate_endor_api_registry import (
    LEGACY_RESOURCES,
    all_enum_members,
    emit_enum_block,
    enum_family_drift,
    enum_members_for_family,
    field_mask_drift,
    field_mask_path_exists,
    namespaced_collections,
    openapi_format_errors,
    registry_drift,
    resource_has_evidence,
    source_field_references,
    source_instruction_templates,
    source_query_templates,
    source_yaml_documents,
    v1_kinds,
)


def _spec_from_registry(*, extra_enums=(), drop_enums=(), drop_resource_evidence=()):
    """Build a fake spec that exactly satisfies the committed registry, then
    perturb it so drift can be asserted deterministically (offline, no network)."""

    enums: set[str] = set()
    for members in ENDOR_ENUM_VALUES.values():
        enums |= set(members)
    enums |= set(extra_enums)
    enums -= set(drop_enums)
    # Give every non-legacy resource a v1<Kind> definition (evidence), except any
    # we deliberately drop. Legacy resources need no evidence.
    defs = {
        f"v1{kind}": {"type": "object"}
        for kind in ENDOR_API_RESOURCES
        if kind not in LEGACY_RESOURCES and kind not in drop_resource_evidence
    }
    return {
        "swagger": "2.0",
        "definitions": defs,
        "paths": {},
        "components": {"enum": sorted(enums)},
    }


# --- pure extractors -------------------------------------------------------- #
def test_all_enum_members_walks_nested_enums():
    spec = {"a": {"b": {"enum": ["X_ONE", "X_TWO"]}}, "c": [{"enum": ["Y_THREE"]}]}
    assert all_enum_members(spec) == {"X_ONE", "X_TWO", "Y_THREE"}


def test_openapi_format_errors_rejects_unsupported_versions():
    assert openapi_format_errors({"swagger": "2.0"}) == []
    assert openapi_format_errors({"openapi": "3.1.0"}) == [
        "unsupported OpenAPI format '3.1.0'; expected Swagger 2.0"
    ]
    assert openapi_format_errors({}) == [
        "missing OpenAPI format marker; expected Swagger 2.0"
    ]


def test_enum_members_for_family_filters_by_prefix():
    spec = {"enum": ["FINDING_CATEGORY_SCA", "FINDING_CATEGORY_MALWARE", "CONTEXT_TYPE_MAIN"]}
    assert enum_members_for_family(spec, "FINDING_CATEGORY") == {
        "FINDING_CATEGORY_SCA",
        "FINDING_CATEGORY_MALWARE",
    }


def test_namespaced_collections_extracted_from_paths():
    spec = {
        "paths": {
            "/v1/namespaces/{namespace}/findings": {},
            "/v1/namespaces/{namespace}/package-versions": {},
            "/v1/meta/version": {},
        }
    }
    assert namespaced_collections(spec) == {"findings", "package-versions"}


def test_v1_kinds_extracts_pascalcase_definitions():
    spec = {"definitions": {"v1Finding": {}, "v1ScanResult": {}, "v1ListFindingsResponse": {}, "Other": {}}}
    kinds = v1_kinds(spec)
    assert "Finding" in kinds and "ScanResult" in kinds
    # ListFindingsResponse is a real v1<Kind> shape too, but the point is no false PascalCase.
    assert "Other" not in kinds


def test_resource_has_evidence_def_collection_legacy_and_fake():
    spec = {
        "definitions": {"v1Finding": {}},
        "paths": {"/v1/namespaces/{namespace}/vulnerabilities": {}, "/v1/namespaces/{namespace}/metrics": {}},
    }
    assert resource_has_evidence("Finding", spec) is True          # v1<Kind> def
    assert resource_has_evidence("Vulnerability", spec) is True     # collection (y -> ies)
    assert resource_has_evidence("Metric", spec) is True           # collection (+s)
    assert resource_has_evidence("UpgradeImpactAnalysis", spec) is True  # known legacy
    assert resource_has_evidence("Frobnicate", spec) is False      # fake


def test_enum_family_drift_reports_both_directions():
    in_spec_not_registry, in_registry_not_spec = enum_family_drift(
        "FINDING_CATEGORY",
        registry_members={"A", "B"},
        spec_members={"B", "C"},
    )
    assert in_spec_not_registry == {"C"}
    assert in_registry_not_spec == {"A"}


# --- composition against the committed registry ----------------------------- #
def test_registry_drift_clean_baseline():
    assert registry_drift(_spec_from_registry()) == []


def test_registry_drift_flags_new_spec_enum_member():
    drift = registry_drift(_spec_from_registry(extra_enums=["FINDING_CATEGORY_BRAND_NEW"]))
    assert any("FINDING_CATEGORY_BRAND_NEW" in line and "MISSING from registry" in line for line in drift)


def test_registry_drift_flags_registry_member_absent_from_spec():
    drift = registry_drift(_spec_from_registry(drop_enums=["FINDING_CATEGORY_SCA"]))
    assert any("FINDING_CATEGORY_SCA" in line and "NOT in current spec" in line for line in drift)


def test_registry_drift_flags_resource_without_evidence():
    drift = registry_drift(_spec_from_registry(drop_resource_evidence=["Finding"]))
    assert any(line.startswith("resource 'Finding'") for line in drift)


def test_emit_enum_block_is_paste_ready():
    block = emit_enum_block(_spec_from_registry())
    assert block.startswith("ENDOR_ENUM_VALUES: dict[str, frozenset[str]] = {")
    assert '"FINDING_CATEGORY": frozenset(' in block
    assert '"FINDING_CATEGORY_VULNERABILITY",' in block


def test_field_mask_path_exists_walks_refs_arrays_and_maps():
    spec = {
        "definitions": {
            "v1Finding": {
                "type": "object",
                "properties": {
                    "uuid": {"type": "string"},
                    "spec": {"$ref": "#/definitions/v1FindingSpec"},
                },
            },
            "v1FindingSpec": {
                "type": "object",
                "properties": {
                    "finding_tags": {"type": "array", "items": {"type": "string"}},
                    "finding_metadata": {"additionalProperties": {"type": "string"}},
                },
            },
        }
    }

    assert field_mask_path_exists(spec, "Finding", "uuid")
    assert field_mask_path_exists(spec, "Finding", "spec.finding_tags")
    assert field_mask_path_exists(spec, "Finding", "spec.finding_metadata.any_key")
    assert not field_mask_path_exists(spec, "Finding", "spec.monitored_branch")


def test_field_mask_path_exists_treats_closed_maps_as_closed():
    spec = {
        "definitions": {
            "v1Finding": {
                "type": "object",
                "properties": {
                    "spec": {
                        "type": "object",
                        "properties": {"known": {"type": "string"}},
                        "additionalProperties": False,
                    }
                },
            }
        }
    }

    assert field_mask_path_exists(spec, "Finding", "spec.known")
    assert not field_mask_path_exists(spec, "Finding", "spec.unknown")


def test_field_mask_path_exists_resolves_service_backed_resource_schema():
    spec = {
        "definitions": {
            "endorv1Metric": {
                "type": "object",
                "properties": {
                    "spec": {
                        "type": "object",
                        "properties": {"value": {"type": "number"}},
                        "additionalProperties": False,
                    }
                },
            }
        },
        "paths": {
            "/v1/namespaces/{namespace}/metrics/{uuid}": {
                "get": {
                    "responses": {
                        "200": {"schema": {"$ref": "#/definitions/endorv1Metric"}}
                    }
                }
            }
        },
    }

    assert field_mask_path_exists(spec, "Metric", "spec.value")
    assert not field_mask_path_exists(spec, "Metric", "spec.typo")


def test_field_mask_drift_reports_invalid_query_template_path():
    spec = {
        "definitions": {
            "v1Project": {
                "type": "object",
                "properties": {
                    "uuid": {"type": "string"},
                    "spec": {"$ref": "#/definitions/v1ProjectSpec"},
                },
            },
            "v1ProjectSpec": {
                "type": "object",
                "properties": {"git": {"type": "object"}},
            },
        }
    }
    templates = [
        (
            "workflows/x.yaml.evidence_query_recipes[0].template",
            'endorctl api list -r Project -n x --field-mask "uuid,spec.git,spec.monitored_branch" -o json',
        )
    ]
    drift = field_mask_drift(spec, templates)

    assert drift == [
        "workflows/x.yaml.evidence_query_recipes[0].template: field-mask path "
        "'spec.monitored_branch' is not valid for Endor API resource 'Project'"
    ]


def test_field_mask_drift_reports_multiple_field_masks_and_fields_lists():
    spec = {
        "definitions": {
            "v1Project": {
                "type": "object",
                "properties": {
                    "uuid": {"type": "string"},
                    "spec": {
                        "type": "object",
                        "properties": {"git": {"type": "object"}},
                        "additionalProperties": False,
                    },
                },
            },
        }
    }
    templates = [
        (
            "workflows/x.yaml.step.template",
            'endorctl api list -r Project --field-mask "uuid" && '
            'endorctl api list -r Project --field-mask "spec.monitored_branch"',
        )
    ]
    fields = [
        ("workflows/x.yaml.resources[0].fields[0]", "Project", "spec.git"),
        ("workflows/x.yaml.resources[0].fields[1]", "Project", "spec.monitored_branch"),
        ("workflows/x.yaml.resources[1].fields[0]", "GitHub", "workflow_files"),
    ]

    drift = field_mask_drift(spec, templates, fields)

    assert drift == [
        "workflows/x.yaml.step.template: field-mask path 'spec.monitored_branch' "
        "is not valid for Endor API resource 'Project'",
        "workflows/x.yaml.resources[0].fields[1]: fields path 'spec.monitored_branch' "
        "is not valid for Endor API resource 'Project'",
    ]


def test_field_mask_drift_pairs_each_mask_with_its_command_resource():
    spec = {
        "definitions": {
            "v1Project": {
                "type": "object",
                "properties": {"uuid": {"type": "string"}},
                "additionalProperties": False,
            },
            "v1Finding": {
                "type": "object",
                "properties": {
                    "spec": {
                        "type": "object",
                        "properties": {"level": {"type": "string"}},
                        "additionalProperties": False,
                    }
                },
                "additionalProperties": False,
            },
        }
    }
    templates = [
        (
            "workflows/x.yaml.step.template",
            "endorctl api list -r Project --field-mask uuid && "
            "endorctl api list -r Finding --field-mask spec.level",
        )
    ]

    assert field_mask_drift(spec, templates) == []


def test_field_mask_drift_validates_non_registry_resource_when_schema_exists():
    spec = {
        "definitions": {
            "v1Integration": {
                "type": "object",
                "properties": {
                    "uuid": {"type": "string"},
                    "spec": {
                        "type": "object",
                        "properties": {"name": {"type": "string"}},
                        "additionalProperties": False,
                    },
                },
            },
        }
    }
    fields = [
        ("workflows/x.yaml.resources[0].fields[0]", "Integration", "spec.name"),
        ("workflows/x.yaml.resources[0].fields[1]", "Integration", "spec.missing"),
    ]

    assert "Integration" not in ENDOR_API_RESOURCES
    assert field_mask_drift(spec, [], fields) == [
        "workflows/x.yaml.resources[0].fields[1]: fields path 'spec.missing' "
        "is not valid for Endor API resource 'Integration'",
    ]


def test_field_mask_drift_reports_unvalidated_registry_resource():
    templates = [
        (
            "agents/x/instructions.md",
            "endorctl api list -r UpgradeImpactAnalysis --field-mask spec.typo",
        )
    ]

    assert field_mask_drift({"definitions": {}, "paths": {}}, templates) == [
        "agents/x/instructions.md: field mask for Endor API resource "
        "'UpgradeImpactAnalysis' cannot be validated because no schema was resolved"
    ]

def test_source_field_references_collects_resource_fields(tmp_path):
    pack = tmp_path / "pack"
    (pack / "workflows").mkdir(parents=True)
    (pack / "query-recipes.yaml").write_text("recipes: []\n", encoding="utf-8")
    (pack / "workflows" / "x.yaml").write_text(
        """\
resources:
  - name: Project
    fields:
      - uuid
      - spec.monitored_branch
evidence_query_recipes:
  - resource: Finding
    fields:
      - spec.level
""",
        encoding="utf-8",
    )

    assert source_field_references(pack) == [
        ("workflows/x.yaml.resources[0].fields[0]", "Project", "uuid"),
        ("workflows/x.yaml.resources[0].fields[1]", "Project", "spec.monitored_branch"),
        ("workflows/x.yaml.evidence_query_recipes[0].fields[0]", "Finding", "spec.level"),
    ]


def test_source_field_references_separates_count_and_group_response_envelopes(tmp_path):
    pack = tmp_path / "pack"
    (pack / "workflows").mkdir(parents=True)
    (pack / "query-recipes.yaml").write_text(
        """\
recipes:
  - resource: Finding
    template: endorctl agent api --agent-id fixture list -r Finding -n tenant --count -o json
    fields: [count]
  - resource: Finding
    template: endorctl agent api --agent-id fixture list -r Finding -n tenant --group-aggregation-paths spec.level -o json
    fields:
      - group_response.groups
      - aggregation_count.count
      - spec.level
""",
        encoding="utf-8",
    )

    assert source_field_references(pack) == [
        ("query-recipes.yaml.recipes[1].fields[2]", "Finding", "spec.level")
    ]


def test_source_field_references_ignores_generic_name_and_fields_objects(tmp_path):
    pack = tmp_path / "pack"
    (pack / "workflows").mkdir(parents=True)
    (pack / "query-recipes.yaml").write_text("recipes: []\n", encoding="utf-8")
    (pack / "workflows" / "x.yaml").write_text(
        """\
metadata:
  name: Project
  fields: [uuid]
resources:
  - name: Finding
    fields: [uuid]
""",
        encoding="utf-8",
    )

    assert source_field_references(pack) == [
        ("workflows/x.yaml.resources[0].fields[0]", "Finding", "uuid")
    ]


def test_source_yaml_documents_can_be_reused_for_templates_and_fields(tmp_path):
    pack = tmp_path / "pack"
    (pack / "workflows").mkdir(parents=True)
    (pack / "query-recipes.yaml").write_text("recipes: []\n", encoding="utf-8")
    (pack / "workflows" / "x.yaml").write_text(
        """\
resources:
  - name: Project
    fields: [uuid]
evidence_query_recipes:
  - id: project
    template: endorctl api list -r Project --field-mask uuid
""",
        encoding="utf-8",
    )

    documents = source_yaml_documents(pack)

    assert source_query_templates(pack, documents) == [
        ("workflows/x.yaml.evidence_query_recipes[0].template", "endorctl api list -r Project --field-mask uuid")
    ]
    assert source_field_references(pack, documents) == [
        ("workflows/x.yaml.resources[0].fields[0]", "Project", "uuid")
    ]


def test_source_instruction_templates_collects_agent_markdown_commands(tmp_path):
    agents = tmp_path / "agents"
    (agents / "example").mkdir(parents=True)
    instructions = agents / "example" / "instructions.md"
    instructions.write_text(
        "Run `endorctl api list -r Project --field-mask uuid`.\n",
        encoding="utf-8",
    )

    assert source_instruction_templates(agents) == [
        ("agents/example/instructions.md", instructions.read_text(encoding="utf-8"))
    ]
