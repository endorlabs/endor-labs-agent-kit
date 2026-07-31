from __future__ import annotations

import json

import pytest

from conftest import repo_root
from endor_agent_kit.cli import main
from endor_agent_kit.policy_pack import (
    evaluate_policy_pack,
    evaluate_policy_pack_file,
    load_policy_pack,
    policy_fact_preflight_errors,
    policy_output_errors,
    policy_pack_sha256,
    validate_policy_pack_data,
    validate_policy_pack_file,
)


def _policy_path(name: str):
    return repo_root() / "policy-packs" / name


def _policy(**updates):
    policy = {
        "id": "warn",
        "title": "Warn",
        "effect": "warn",
        "message": "Review this proposal.",
    }
    policy.update(updates)
    return policy


def _pack(*policies, **updates):
    data = {
        "policy_pack_version": 1,
        "id": "test-pack",
        "version": "1",
        "policies": list(policies),
    }
    data.update(updates)
    return data


def test_policy_pack_examples_validate():
    assert validate_policy_pack_file(_policy_path("policy-pack.template.yaml")) == []
    assert validate_policy_pack_file(_policy_path("examples/was-traditional-java8.yaml")) == []
    assert validate_policy_pack_file(_policy_path("examples/liberty-java-fixpack.yaml")) == []


def test_policy_pack_schema_encodes_strict_condition_shapes():
    schema = json.loads(_policy_path("policy-pack.schema.json").read_text(encoding="utf-8"))

    assert schema["additionalProperties"] is False
    assert schema["$defs"]["policy"]["additionalProperties"] is False
    assert schema["$defs"]["predicateCondition"]["additionalProperties"] is False
    assert len(schema["$defs"]["predicateCondition"]["oneOf"]) == 13
    assert "version_lt" in schema["$defs"]["predicateCondition"]["properties"]
    assert schema["$defs"]["allCondition"]["properties"]["all"]["minItems"] == 1
    assert schema["$defs"]["anyCondition"]["properties"]["any"]["minItems"] == 1


def test_policy_pack_schema_rejects_whitespace_text_and_empty_scope_arrays():
    schema = json.loads(_policy_path("policy-pack.schema.json").read_text(encoding="utf-8"))

    assert schema["properties"]["id"]["pattern"] == r".*\S.*"
    policy = schema["$defs"]["policy"]["properties"]
    assert policy["id"]["pattern"] == r".*\S.*"
    assert policy["message"]["pattern"] == r".*\S.*"
    applies_to = policy["applies_to"]["properties"]
    assert applies_to["agents"]["minItems"] == 1
    assert applies_to["ecosystems"]["minItems"] == 1


def test_policy_pack_validation_rejects_bad_policy_shapes():
    data = {
        "policy_pack_version": 1,
        "id": "bad",
        "version": "1",
        "policies": [
            {
                "id": "duplicate",
                "title": "No message",
                "effect": "deny",
                "deny_if": {"fact": "x", "matches": "unsupported"},
            },
            {
                "id": "duplicate",
                "title": "Bad effect",
                "effect": "block",
                "message": "bad",
            },
        ],
    }

    errors = validate_policy_pack_data(data)

    assert "policies[0].message: required for every policy" in errors
    assert "policies[0].deny_if: must contain exactly one supported operator" in errors
    assert "policies[1].id: duplicate policy id 'duplicate'" in errors
    assert any("policies[1].effect" in error for error in errors)


def test_policy_pack_validation_rejects_unknown_top_level_fields():
    assert validate_policy_pack_data(_pack(unexpected=True)) == [
        "policy_pack: unsupported fields ['unexpected']"
    ]


def test_policy_pack_validation_rejects_boolean_schema_version():
    assert validate_policy_pack_data(_pack(policy_pack_version=True)) == [
        "policy_pack_version: must be 1"
    ]


def test_policy_pack_validation_rejects_unknown_policy_fields():
    assert validate_policy_pack_data(
        _pack(_policy(warn_when={"fact": "risk", "equals": "high"}))
    ) == [
        "policies[0]: unsupported fields ['warn_when']"
    ]


def test_policy_pack_validation_rejects_condition_for_a_different_effect():
    assert validate_policy_pack_data(
        _pack(
            _policy(
                effect="deny",
                warn_if={"fact": "risk", "equals": "high"},
            )
        )
    ) == [
        "policies[0].warn_if: does not match effect 'deny'; use deny_if"
    ]


def test_policy_pack_validation_rejects_unknown_applies_to_fields():
    assert validate_policy_pack_data(
        _pack(_policy(applies_to={"repositories": ["example/repo"]}))
    ) == [
        "policies[0].applies_to: unsupported fields ['repositories']"
    ]


def test_policy_pack_validation_rejects_null_applies_to():
    assert validate_policy_pack_data(_pack(_policy(applies_to=None))) == [
        "policies[0].applies_to: must be a mapping"
    ]


def test_policy_pack_validation_rejects_empty_scope_arrays():
    assert validate_policy_pack_data(
        _pack(_policy(applies_to={"agents": [], "ecosystems": []}))
    ) == [
        "policies[0].applies_to.agents: must be a non-empty list of non-blank strings",
        "policies[0].applies_to.ecosystems: must be a non-empty list of non-blank strings",
    ]


def test_policy_pack_validation_requires_messages_for_nonblocking_policies():
    policy = _policy()
    policy.pop("message")

    assert "policies[0].message: required for every policy" in validate_policy_pack_data(
        _pack(policy)
    )


def test_policy_pack_validation_rejects_empty_missing_facts_policy():
    assert validate_policy_pack_data(_pack(_policy(on_missing_facts=""))) == [
        "policies[0].on_missing_facts: must be one of allow, deny, unavailable, warn"
    ]


def test_policy_pack_validation_rejects_extra_compound_condition_fields():
    condition = {
        "all": [{"fact": "risk", "equals": "high"}],
        "unexpected": True,
    }

    assert validate_policy_pack_data(_pack(_policy(effect="deny", when=condition))) == [
        "policies[0].when: unsupported fields ['unexpected']"
    ]


def test_policy_pack_validation_requires_boolean_exists_operator():
    assert validate_policy_pack_data(
        _pack(_policy(effect="deny", deny_if={"fact": "risk", "exists": "false"}))
    ) == [
        "policies[0].deny_if.exists: must be boolean"
    ]


def test_policy_pack_validation_requires_array_in_operator():
    assert validate_policy_pack_data(
        _pack(_policy(warn_if={"fact": "risk", "in": "high"}))
    ) == [
        "policies[0].warn_if.in: must be a list"
    ]


def test_policy_pack_validation_rejects_ambiguous_version_literals():
    assert validate_policy_pack_data(
        _pack(
            _policy(
                warn_if={"fact": "runtime.version", "version_lt": "2.0-ifix"},
            )
        )
    ) == [
        "policies[0].warn_if.version_lt: must be a numeric dotted version"
    ]


def test_policy_pack_validation_rejects_collection_equality_literals():
    assert validate_policy_pack_data(
        _pack(_policy(warn_if={"fact": "runtime.tags", "equals": ["legacy"]}))
    ) == [
        "policies[0].warn_if.equals: must be a scalar value"
    ]


def test_policy_pack_validation_rejects_non_numeric_ordered_literal():
    assert validate_policy_pack_data(
        _pack(_policy(warn_if={"fact": "runtime.java.major", "gte": "17"}))
    ) == [
        "policies[0].warn_if.gte: must be a number"
    ]


def test_collection_equality_fails_closed_when_runtime_validation_is_bypassed():
    evaluations = evaluate_policy_pack(
        _pack(
            _policy(
                effect="deny",
                deny_if={"fact": "runtime.tags", "equals": ["legacy"]},
                on_missing_facts="unavailable",
            )
        ),
        {"runtime": {"tags": ["legacy"]}},
    )

    assert evaluations[0]["decision"] == "unavailable"
    assert evaluations[0]["invalid_facts"] == ["runtime.tags"]


def test_in_operator_does_not_treat_boolean_as_integer():
    evaluations = evaluate_policy_pack(
        _pack(
            _policy(
                effect="deny",
                deny_if={"fact": "runtime.flag", "in": [1, 2]},
                on_missing_facts="unavailable",
            )
        ),
        {"runtime": {"flag": True}},
    )

    assert evaluations[0]["decision"] == "unavailable"
    assert evaluations[0]["invalid_facts"] == ["runtime.flag"]


def test_was_traditional_policy_blocks_java_above_8():
    evaluations = evaluate_policy_pack_file(
        _policy_path("examples/was-traditional-java8.yaml"),
        {
            "agent": {"id": "sca-remediation"},
            "ecosystem": "maven",
            "platform": {"websphere": {"family": "traditional", "present": True}},
            "proposed": {"runtime": {"java": {"major": 17}}},
        },
    )

    assert evaluations[0]["policy_id"] == "was-traditional-java-max-8"
    assert evaluations[0]["decision"] == "blocked"


def test_policy_fact_preflight_requires_applicability_facts_only():
    pack = _pack(
        _policy(
            effect="deny",
            applies_to={"agents": ["sca-remediation"], "ecosystems": ["maven"]},
            when={"fact": "platform.websphere.family", "equals": "traditional"},
            deny_if={"fact": "proposed.runtime.java.major", "gt": 8},
            on_missing_facts="unavailable",
        )
    )

    missing_applicability = policy_fact_preflight_errors(
        pack,
        {"agent": {"id": "sca-remediation"}, "ecosystem": "maven"},
    )
    missing_decision = policy_fact_preflight_errors(
        pack,
        {
            "agent": {"id": "sca-remediation"},
            "ecosystem": "maven",
            "platform": {"websphere": {"family": "traditional"}},
        },
    )

    assert missing_applicability == [
        "policy 'warn' applicability: missing trusted facts "
        "['platform.websphere.family']"
    ]
    assert missing_decision == []


def test_was_traditional_policy_allows_java_8():
    evaluations = evaluate_policy_pack_file(
        _policy_path("examples/was-traditional-java8.yaml"),
        {
            "agent": {"id": "oss-upgrade-investigator"},
            "ecosystem": "maven",
            "platform": {"websphere": {"family": "traditional", "present": True}},
            "proposed": {"runtime": {"java": {"major": 8}}},
        },
    )

    assert evaluations[0]["decision"] == "passed"


def test_was_traditional_policy_marks_missing_java_fact_unavailable():
    evaluations = evaluate_policy_pack_file(
        _policy_path("examples/was-traditional-java8.yaml"),
        {
            "agent": {"id": "sca-remediation"},
            "ecosystem": "maven",
            "platform": {"websphere": {"family": "traditional", "present": True}},
        },
    )

    assert evaluations[0]["decision"] == "unavailable"
    assert "proposed.runtime.java.major" in evaluations[0]["missing_facts"]


def test_cross_type_equals_reports_invalid_fact_and_fails_closed():
    evaluations = evaluate_policy_pack(
        _pack(
            _policy(
                effect="deny",
                when={"fact": "platform.websphere.present", "equals": True},
                on_missing_facts="unavailable",
            )
        ),
        {"platform": {"websphere": {"present": "true"}}},
    )

    assert evaluations[0]["decision"] == "unavailable"
    assert evaluations[0]["missing_facts"] == []
    assert evaluations[0]["invalid_facts"] == ["platform.websphere.present"]


def test_cross_type_not_equals_reports_invalid_fact_and_fails_closed():
    evaluations = evaluate_policy_pack(
        _pack(
            _policy(
                effect="deny",
                deny_if={"fact": "proposed.runtime.java.major", "not_equals": 8},
                on_missing_facts="unavailable",
            )
        ),
        {"proposed": {"runtime": {"java": {"major": "8"}}}},
    )

    assert evaluations[0]["decision"] == "unavailable"
    assert evaluations[0]["invalid_facts"] == ["proposed.runtime.java.major"]


def test_compound_conditions_preserve_invalid_fact_provenance():
    evaluations = evaluate_policy_pack(
        _pack(
            _policy(
                effect="deny",
                when={
                    "all": [
                        {"fact": "platform.websphere.family", "equals": "traditional"},
                        {"fact": "platform.websphere.present", "equals": True},
                    ]
                },
                on_missing_facts="unavailable",
            )
        ),
        {
            "platform": {
                "websphere": {"family": "traditional", "present": "true"},
            }
        },
    )

    assert evaluations[0]["decision"] == "unavailable"
    assert evaluations[0]["invalid_facts"] == ["platform.websphere.present"]


def test_ordered_comparison_rejects_numeric_strings():
    evaluations = evaluate_policy_pack(
        _pack(
            _policy(
                effect="deny",
                deny_if={"fact": "proposed.runtime.java.major", "gt": 8},
                on_missing_facts="unavailable",
            )
        ),
        {"proposed": {"runtime": {"java": {"major": "17"}}}},
    )

    assert evaluations[0]["decision"] == "unavailable"
    assert evaluations[0]["invalid_facts"] == ["proposed.runtime.java.major"]


def test_version_comparison_orders_numeric_dotted_versions():
    evaluations = evaluate_policy_pack(
        _pack(
            _policy(
                effect="deny",
                deny_if={
                    "fact": "platform.websphere.liberty.version",
                    "version_lt": "21.0.0.10",
                },
                on_missing_facts="unavailable",
            )
        ),
        {"platform": {"websphere": {"liberty": {"version": "21.0.0.9"}}}},
    )

    assert evaluations[0]["decision"] == "blocked"
    assert evaluations[0]["invalid_facts"] == []


def test_version_comparison_treats_trailing_zero_segments_as_equal():
    evaluations = evaluate_policy_pack(
        _pack(
            _policy(
                effect="deny",
                deny_if={"fact": "runtime.version", "version_lt": "2.0.0"},
                on_missing_facts="unavailable",
            )
        ),
        {"runtime": {"version": "2.0"}},
    )

    assert evaluations[0]["decision"] == "passed"
    assert evaluations[0]["invalid_facts"] == []


def test_version_comparison_rejects_ambiguous_qualifiers():
    evaluations = evaluate_policy_pack(
        _pack(
            _policy(
                effect="deny",
                deny_if={
                    "fact": "platform.websphere.liberty.version",
                    "version_lt": "21.0.0.10",
                },
                on_missing_facts="unavailable",
            )
        ),
        {
            "platform": {
                "websphere": {"liberty": {"version": "21.0.0.9-ifix"}},
            }
        },
    )

    assert evaluations[0]["decision"] == "unavailable"
    assert evaluations[0]["invalid_facts"] == ["platform.websphere.liberty.version"]


def test_contains_checks_dictionary_keys():
    evaluations = evaluate_policy_pack(
        _pack(
            _policy(
                effect="deny",
                deny_if={"fact": "runtime.capabilities", "contains": "legacy-java"},
                on_missing_facts="unavailable",
            )
        ),
        {"runtime": {"capabilities": {"legacy-java": True}}},
    )

    assert evaluations[0]["decision"] == "blocked"
    assert evaluations[0]["invalid_facts"] == []


def test_scoped_policy_is_unavailable_when_scope_facts_are_missing():
    evaluations = evaluate_policy_pack_file(
        _policy_path("examples/was-traditional-java8.yaml"),
        {
            "platform": {"websphere": {"family": "traditional", "present": True}},
            "proposed": {"runtime": {"java": {"major": 17}}},
        },
    )

    assert evaluations[0]["decision"] == "unavailable"
    assert evaluations[0]["missing_facts"] == ["agent.id", "ecosystem"]


def test_scoped_policy_is_not_applicable_for_a_known_scope_mismatch():
    evaluations = evaluate_policy_pack_file(
        _policy_path("examples/was-traditional-java8.yaml"),
        {
            "agent": {"id": "findings-browser"},
            "ecosystem": "maven",
            "platform": {"websphere": {"family": "traditional", "present": True}},
            "proposed": {"runtime": {"java": {"major": 17}}},
        },
    )

    assert evaluations[0]["decision"] == "not_applicable"
    assert evaluations[0]["missing_facts"] == []


def test_mutation_gate_blocks_when_a_policy_scope_fact_is_missing():
    path = _policy_path("examples/was-traditional-java8.yaml")
    pack = load_policy_pack(path)
    trusted = evaluate_policy_pack_file(
        path,
        {
            "platform": {"websphere": {"family": "traditional", "present": True}},
            "proposed": {"runtime": {"java": {"major": 17}}},
        },
        agent_id="sca-remediation",
    )
    payload = {
        "policy_context": {
            "status": "loaded",
            "pack_id": pack["id"],
            "pack_version": pack["version"],
            "sha256": policy_pack_sha256(path),
        },
        "policy_evaluations": trusted,
    }

    errors = policy_output_errors(
        payload,
        policy_pack=pack,
        policy_sha256=policy_pack_sha256(path),
        mutation_gate=True,
        trusted_evaluations=trusted,
    )

    assert trusted[0]["missing_facts"] == ["ecosystem"]
    assert "policy_evaluations[0].decision: unavailable blocks mutation gate" in errors


def test_liberty_policy_gates_java_versions_by_fixpack():
    policy = _policy_path("examples/liberty-java-fixpack.yaml")
    java17_old = evaluate_policy_pack_file(
        policy,
        {
            "agent": {"id": "sca-remediation"},
            "ecosystem": "maven",
            "platform": {"websphere": {"family": "liberty", "liberty": {"version": "21.0.0.9"}}},
            "proposed": {"runtime": {"java": {"major": 17}}},
        },
    )
    java17_new = evaluate_policy_pack_file(
        policy,
        {
            "agent": {"id": "sca-remediation"},
            "ecosystem": "maven",
            "platform": {"websphere": {"family": "liberty", "liberty": {"version": "21.0.0.10"}}},
            "proposed": {"runtime": {"java": {"major": 17}}},
        },
    )
    java21_old = evaluate_policy_pack_file(
        policy,
        {
            "agent": {"id": "oss-upgrade-investigator"},
            "ecosystem": "maven",
            "platform": {"websphere": {"family": "liberty", "liberty": {"version": "23.0.0.9"}}},
            "proposed": {"runtime": {"java": {"major": 21}}},
        },
    )

    assert java17_old[0]["decision"] == "blocked"
    assert java17_new[0]["decision"] == "passed"
    assert java21_old[1]["decision"] == "blocked"


def test_policy_output_errors_require_loaded_context_when_policy_pack_is_supplied():
    pack = load_policy_pack(_policy_path("examples/was-traditional-java8.yaml"))
    payload = {"policy_context": {"status": "unavailable"}, "policy_evaluations": []}

    errors = policy_output_errors(payload, policy_pack=pack)

    assert "policy_context.status: must be loaded when --policy-pack is supplied" in errors
    assert "policy_evaluations: required when --policy-pack declares policies" in errors


def test_policy_output_errors_accept_exact_loaded_policy_context():
    path = _policy_path("examples/was-traditional-java8.yaml")
    pack = load_policy_pack(path)
    trusted = evaluate_policy_pack_file(
        path,
        {
            "agent": {"id": "sca-remediation"},
            "ecosystem": "maven",
            "platform": {"websphere": {"family": "traditional", "present": True}},
            "proposed": {"runtime": {"java": {"major": 8}}},
        },
    )
    payload = {
        "policy_context": {
            "status": "loaded",
            "pack_id": pack["id"],
            "pack_version": pack["version"],
            "sha256": policy_pack_sha256(path),
            "source": "runtime",
        },
        "policy_evaluations": trusted,
    }

    assert (
        policy_output_errors(
            payload,
            policy_pack=pack,
            policy_sha256=policy_pack_sha256(path),
            trusted_evaluations=trusted,
        )
        == []
    )


def test_policy_output_errors_reject_tampered_invalid_facts():
    path = _policy_path("examples/was-traditional-java8.yaml")
    pack = load_policy_pack(path)
    trusted = evaluate_policy_pack_file(
        path,
        {
            "agent": {"id": "sca-remediation"},
            "ecosystem": "maven",
            "platform": {"websphere": {"family": "traditional", "present": True}},
            "proposed": {"runtime": {"java": {"major": 8}}},
        },
    )
    tampered = [dict(trusted[0], invalid_facts=["fabricated.fact"])]
    payload = {
        "policy_context": {
            "status": "loaded",
            "pack_id": pack["id"],
            "pack_version": pack["version"],
            "sha256": policy_pack_sha256(path),
        },
        "policy_evaluations": tampered,
    }

    errors = policy_output_errors(
        payload,
        policy_pack=pack,
        policy_sha256=policy_pack_sha256(path),
        trusted_evaluations=trusted,
    )

    assert (
        "policy_evaluations[0].invalid_facts: must match trusted policy evaluation []"
        in errors
    )


@pytest.mark.parametrize(
    ("field", "tampered_value"),
    [
        ("message", "fabricated message"),
        ("facts_used", ["fabricated.fact"]),
        ("missing_facts", ["fabricated.fact"]),
    ],
)
def test_policy_output_errors_reject_tampered_trusted_fields(field, tampered_value):
    path = _policy_path("examples/was-traditional-java8.yaml")
    pack = load_policy_pack(path)
    trusted = evaluate_policy_pack_file(
        path,
        {
            "agent": {"id": "sca-remediation"},
            "ecosystem": "maven",
            "platform": {"websphere": {"family": "traditional", "present": True}},
            "proposed": {"runtime": {"java": {"major": 8}}},
        },
    )
    payload_evaluation = dict(trusted[0])
    payload_evaluation[field] = tampered_value
    payload = {
        "policy_context": {
            "status": "loaded",
            "pack_id": pack["id"],
            "pack_version": pack["version"],
            "sha256": policy_pack_sha256(path),
        },
        "policy_evaluations": [payload_evaluation],
    }

    errors = policy_output_errors(
        payload,
        policy_pack=pack,
        policy_sha256=policy_pack_sha256(path),
        trusted_evaluations=trusted,
    )

    assert any(f"policy_evaluations[0].{field}: must match" in error for error in errors)


def test_policy_output_errors_reject_duplicate_trusted_evaluation():
    path = _policy_path("examples/liberty-java-fixpack.yaml")
    pack = load_policy_pack(path)
    trusted = evaluate_policy_pack_file(
        path,
        {
            "agent": {"id": "sca-remediation"},
            "ecosystem": "maven",
            "platform": {
                "websphere": {"family": "liberty", "liberty": {"version": "23.0.0.10"}},
            },
            "proposed": {"runtime": {"java": {"major": 17}}},
        },
    )
    payload = {
        "policy_context": {
            "status": "loaded",
            "pack_id": pack["id"],
            "pack_version": pack["version"],
            "sha256": policy_pack_sha256(path),
        },
        "policy_evaluations": trusted + [dict(trusted[0])],
    }

    errors = policy_output_errors(
        payload,
        policy_pack=pack,
        policy_sha256=policy_pack_sha256(path),
        trusted_evaluations=trusted,
    )

    assert any("must contain exactly one trusted evaluation" in error for error in errors)


def test_policy_output_errors_reject_omitted_trusted_evaluation():
    path = _policy_path("examples/liberty-java-fixpack.yaml")
    pack = load_policy_pack(path)
    trusted = evaluate_policy_pack_file(
        path,
        {
            "agent": {"id": "sca-remediation"},
            "ecosystem": "maven",
            "platform": {
                "websphere": {"family": "liberty", "liberty": {"version": "23.0.0.10"}},
            },
            "proposed": {"runtime": {"java": {"major": 17}}},
        },
    )
    payload = {
        "policy_context": {
            "status": "loaded",
            "pack_id": pack["id"],
            "pack_version": pack["version"],
            "sha256": policy_pack_sha256(path),
        },
        "policy_evaluations": trusted[:1],
    }

    errors = policy_output_errors(
        payload,
        policy_pack=pack,
        policy_sha256=policy_pack_sha256(path),
        trusted_evaluations=trusted,
    )

    assert any("must contain exactly one trusted evaluation" in error for error in errors)


def test_policy_output_errors_require_trusted_evaluations_for_a_supplied_pack():
    path = _policy_path("examples/was-traditional-java8.yaml")
    pack = load_policy_pack(path)
    payload = {
        "policy_context": {
            "status": "loaded",
            "pack_id": pack["id"],
            "pack_version": pack["version"],
            "sha256": policy_pack_sha256(path),
        },
        "policy_evaluations": [
            {
                "policy_id": "was-traditional-java-max-8",
                "effect": "deny",
                "decision": "passed",
            }
        ],
    }

    errors = policy_output_errors(
        payload,
        policy_pack=pack,
        policy_sha256=policy_pack_sha256(path),
    )

    assert "policy_evaluations: trusted policy evaluation is required" in errors


def test_policy_output_errors_reject_untrusted_extra_evaluations():
    path = _policy_path("examples/was-traditional-java8.yaml")
    pack = load_policy_pack(path)
    trusted = evaluate_policy_pack_file(
        path,
        {
            "agent": {"id": "sca-remediation"},
            "ecosystem": "maven",
            "platform": {"websphere": {"family": "traditional", "present": True}},
            "proposed": {"runtime": {"java": {"major": 8}}},
        },
    )
    payload = {
        "policy_context": {
            "status": "loaded",
            "pack_id": pack["id"],
            "pack_version": pack["version"],
            "sha256": policy_pack_sha256(path),
        },
        "policy_evaluations": trusted
        + [
            {
                "policy_id": "not-declared-by-pack",
                "effect": "allow",
                "decision": "passed",
                "message": "fabricated",
                "facts_used": [],
                "missing_facts": [],
            }
        ],
    }

    errors = policy_output_errors(
        payload,
        policy_pack=pack,
        policy_sha256=policy_pack_sha256(path),
        mutation_gate=True,
        trusted_evaluations=trusted,
    )

    assert "policy_evaluations[1].policy_id: not present in trusted policy evaluations" in errors


def test_policy_pack_cli_validate_and_evaluate(tmp_path, capsys):
    facts = tmp_path / "facts.json"
    facts.write_text(
        json.dumps(
            {
                "agent": {"id": "sca-remediation"},
                "ecosystem": "maven",
                "platform": {"websphere": {"family": "traditional", "present": True}},
                "proposed": {"runtime": {"java": {"major": 21}}},
            }
        ),
        encoding="utf-8",
    )

    assert main(["validate-policy-pack", str(_policy_path("examples/was-traditional-java8.yaml"))]) == 0
    assert main(
        [
            "evaluate-policy-pack",
            str(_policy_path("examples/was-traditional-java8.yaml")),
            "--facts",
            str(facts),
        ]
    ) == 0
    output = capsys.readouterr().out

    assert '"decision": "blocked"' in output


def test_policy_pack_cli_preflight_rejects_missing_applicability_facts(tmp_path, capsys):
    facts = tmp_path / "facts.json"
    facts.write_text(
        json.dumps(
            {
                "agent": {"id": "sca-remediation"},
                "ecosystem": "maven",
                "proposed": {"runtime": {"java": {"major": 17}}},
            }
        ),
        encoding="utf-8",
    )

    status = main(
        [
            "evaluate-policy-pack",
            str(_policy_path("examples/was-traditional-java8.yaml")),
            "--facts",
            str(facts),
            "--preflight",
        ]
    )

    assert status == 1
    assert "applicability: missing trusted facts" in capsys.readouterr().out


def test_policy_pack_cli_reports_malformed_yaml_without_traceback(tmp_path, capsys):
    policy = tmp_path / "bad-policy.yaml"
    policy.write_text("policies: [", encoding="utf-8")
    facts = tmp_path / "facts.json"
    facts.write_text("{}", encoding="utf-8")

    status = main(
        [
            "evaluate-policy-pack",
            str(policy),
            "--facts",
            str(facts),
        ]
    )

    assert status == 1
    assert "ERROR: policy_pack: invalid YAML:" in capsys.readouterr().out
