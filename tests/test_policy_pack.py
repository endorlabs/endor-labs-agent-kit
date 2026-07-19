from __future__ import annotations

import json

from conftest import repo_root
from endor_agent_kit.cli import main
from endor_agent_kit.policy_pack import (
    evaluate_policy_pack_file,
    load_policy_pack,
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
    assert len(schema["$defs"]["predicateCondition"]["oneOf"]) == 9
    assert schema["$defs"]["allCondition"]["properties"]["all"]["minItems"] == 1
    assert schema["$defs"]["anyCondition"]["properties"]["any"]["minItems"] == 1


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


def test_was_traditional_policy_allows_java_8():
    evaluations = evaluate_policy_pack_file(
        _policy_path("examples/was-traditional-java8.yaml"),
        {
            "agent": {"id": "upgrade-impact-analysis"},
            "ecosystem": "maven",
            "platform": {"websphere": {"family": "traditional", "present": True}},
            "proposed": {"runtime": {"java": {"major": 8}}},
        },
    )

    assert evaluations[0]["decision"] == "passed"


def test_was_traditional_policy_blocks_missing_java_fact_by_default():
    evaluations = evaluate_policy_pack_file(
        _policy_path("examples/was-traditional-java8.yaml"),
        {
            "agent": {"id": "sca-remediation"},
            "ecosystem": "maven",
            "platform": {"websphere": {"family": "traditional", "present": True}},
        },
    )

    assert evaluations[0]["decision"] == "blocked"
    assert "proposed.runtime.java.major" in evaluations[0]["missing_facts"]


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
            "agent": {"id": "upgrade-impact-analysis"},
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
