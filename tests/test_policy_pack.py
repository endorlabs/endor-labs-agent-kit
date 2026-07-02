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


def test_policy_pack_examples_validate():
    assert validate_policy_pack_file(_policy_path("policy-pack.template.yaml")) == []
    assert validate_policy_pack_file(_policy_path("examples/was-traditional-java8.yaml")) == []
    assert validate_policy_pack_file(_policy_path("examples/liberty-java-fixpack.yaml")) == []


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

    assert "policies[0].message: required for blocking policies" in errors
    assert "policies[0].deny_if: must contain exactly one supported operator" in errors
    assert "policies[1].id: duplicate policy id 'duplicate'" in errors
    assert any("policies[1].effect" in error for error in errors)


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
    payload = {
        "policy_context": {
            "status": "loaded",
            "pack_id": pack["id"],
            "pack_version": pack["version"],
            "sha256": policy_pack_sha256(path),
            "source": "runtime",
        },
        "policy_evaluations": [
            {
                "policy_id": "was-traditional-java-max-8",
                "effect": "deny",
                "decision": "passed",
                "message": "ok",
                "facts_used": [],
                "missing_facts": [],
            }
        ],
    }

    assert policy_output_errors(payload, policy_pack=pack, policy_sha256=policy_pack_sha256(path)) == []


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
