from __future__ import annotations

import json

import pytest

from conftest import repo_root
from endor_agent_kit.cli import main
from endor_agent_kit.portable_runtime_conformance import (
    DATA_GAP_POLICY,
    DEGRADATION_POLICY,
    adapter_response_conformance_errors,
    assert_portable_text,
    portable_kind,
    portable_manifest_conformance_errors,
    portable_provider_examples,
    required_runtime_control_ids,
    required_runtime_controls,
    runtime_action_vocabulary,
    runtime_wrappers,
)


def test_runtime_controls_are_exposed_through_one_interface():
    controls = required_runtime_controls()

    assert required_runtime_control_ids() == {
        "adapter_authorization",
        "least_privilege_adapters",
        "explicit_confirmation",
        "adapter_evidence",
        "fail_closed_degradation",
        "untrusted_content_boundary",
        "audit_log",
        "secret_redaction",
        "idempotency_check",
    }
    assert {control["id"] for control in controls} == required_runtime_control_ids()
    assert all(control["description"] for control in controls)


def test_action_vocabulary_distinguishes_declared_capabilities_and_wrappers():
    declared_actions = [
        {"portable_kind": "ticket.create", "confirmation_required": True},
    ]

    vocabulary = {
        item["kind"]: item
        for item in runtime_action_vocabulary(
            declared_actions,
            required_capabilities=["repository.read"],
        )
    }

    assert vocabulary["ticket.create"]["status"] == "declared"
    assert vocabulary["ticket.create"]["confirmation_required"] is True
    assert vocabulary["repository.read"]["status"] == "declared"
    assert vocabulary["repository.read"]["confirmation_required"] is False
    assert runtime_wrappers(declared_actions) == []


def test_ticket_create_wrapper_is_available_when_not_declared():
    vocabulary = {
        item["kind"]: item
        for item in runtime_action_vocabulary([], required_capabilities=[])
    }
    wrappers = runtime_wrappers([])

    assert vocabulary["ticket.create"]["status"] == "wrapper_available"
    assert wrappers == [
        {
            "kind": "ticket.create",
            "status": "wrapper_available",
            "declared_by_recipe": False,
            "confirmation_required": True,
            "provider_examples": ["jira", "servicenow", "linear", "internal-ticketing"],
        }
    ]


def test_portable_manifest_conformance_errors_capture_runtime_policy_drift():
    manifest = {
        "declared_actions": [],
        "runtime_action_vocabulary": [{"kind": "ticket.create", "status": "unavailable"}],
        "runtime_wrappers": [],
        "required_runtime_controls": [],
        "degradation": {"mutation_without_adapter": "allowed"},
        "data_gap_policy": "",
    }

    errors = portable_manifest_conformance_errors(manifest)

    assert any("missing runtime controls" in error for error in errors)
    assert "mutation_without_adapter must be forbidden" in errors
    assert "missing data_gap_policy" in errors
    assert "undeclared ticket.create must remain wrapper_available" in errors
    assert "missing ticket.create runtime wrapper" in errors


def test_valid_portable_manifest_conformance_passes():
    manifest = {
        "declared_actions": [],
        "runtime_action_vocabulary": runtime_action_vocabulary([], []),
        "runtime_wrappers": runtime_wrappers([]),
        "required_runtime_controls": required_runtime_controls(),
        "degradation": dict(DEGRADATION_POLICY),
        "data_gap_policy": DATA_GAP_POLICY,
    }

    assert portable_manifest_conformance_errors(manifest) == []


def test_portable_kind_and_provider_examples_are_runtime_neutral():
    assert (
        portable_kind("open-change-request", "scm.change_request")
        == "source.change_request.create"
    )
    assert portable_kind("custom", "ticket.create") == "ticket.create"
    assert portable_provider_examples(("gh-cli", "github-api", "gh-cli")) == (
        "source-provider-adapter",
        "source-provider-api",
    )


def test_assert_portable_text_rejects_host_specific_text():
    with pytest.raises(ValueError, match="forbidden host-specific token"):
        assert_portable_text("agent.md", "Use Claude Code for this workflow.")


def _ticket_creation_response(**overrides):
    response = {
        "action_id": "create-ticket",
        "portable_kind": "ticket.create",
        "status": "succeeded",
        "actor": "runtime-service-account",
        "approved": True,
        "approval_evidence_id": "approval-1",
        "evidence_id": "evidence-1",
        "evidence_summary": "Created tracking ticket from final agent output.",
        "object_id": "TICKET-123",
        "object_url": "https://tickets.example/TICKET-123",
        "idempotency_check": {
            "status": "none_found",
            "lookup_method": "ticket.lookup",
            "evidence_id": "lookup-1",
        },
        "data_gaps": [],
    }
    response.update(overrides)
    return response


def test_successful_ticket_creation_response_is_conformant():
    assert adapter_response_conformance_errors(_ticket_creation_response()) == []


def test_succeeded_response_requires_evidence():
    errors = adapter_response_conformance_errors(_ticket_creation_response(evidence_id=""))

    assert "succeeded adapter response must include evidence_id" in errors


def test_succeeded_state_creating_action_requires_object_and_idempotency():
    response = _ticket_creation_response(object_id="", object_url="")
    del response["idempotency_check"]

    errors = adapter_response_conformance_errors(response)

    assert "succeeded ticket.create must include object_id or object_url" in errors
    assert "succeeded ticket.create must include idempotency_check" in errors


def test_duplicate_state_reuse_is_conformant():
    response = _ticket_creation_response(
        idempotency_check={
            "status": "existing_reused",
            "lookup_method": "ticket.lookup",
            "evidence_id": "lookup-2",
        }
    )

    assert adapter_response_conformance_errors(response) == []


def test_invalid_idempotency_status_is_rejected():
    response = {
        "action_id": "read-manifests",
        "portable_kind": "repository.read",
        "status": "succeeded",
        "evidence_id": "evidence-1",
        "idempotency_check": {"status": "maybe"},
    }

    errors = adapter_response_conformance_errors(response)

    assert any("idempotency_check status must be one of" in error for error in errors)


def test_denied_and_unavailable_responses_must_report_data_gaps():
    for status in ("denied", "unavailable", "failed"):
        blocked = {
            "action_id": "open-change-request",
            "portable_kind": "source.change_request.create",
            "status": status,
            "data_gaps": [],
        }

        errors = adapter_response_conformance_errors(blocked)

        assert f"{status} adapter response must report data_gaps" in errors


def test_authorization_denied_response_with_data_gap_is_conformant():
    denied = {
        "action_id": "open-change-request",
        "portable_kind": "source.change_request.create",
        "status": "denied",
        "evidence_summary": "Authorization denied for actor at repository scope.",
        "data_gaps": ["adapter_authorization denied source.change_request.create"],
    }

    assert adapter_response_conformance_errors(denied) == []


def test_unknown_status_and_kind_are_rejected():
    errors = adapter_response_conformance_errors(
        {"action_id": "x", "portable_kind": "made.up", "status": "pending"}
    )

    assert any("status must be one of" in error for error in errors)
    assert "adapter response has unknown portable_kind 'made.up'" in errors


def _example_responses(category: str):
    example_dir = repo_root() / "examples" / "adapter-responses" / category
    files = sorted(example_dir.glob("*.json"))
    assert files, f"no example responses under {example_dir}"
    return files


def test_conformant_example_responses_pass_the_schema():
    for path in _example_responses("conformant"):
        response = json.loads(path.read_text(encoding="utf-8"))
        assert adapter_response_conformance_errors(response) == [], path.name


def test_nonconformant_example_responses_fail_the_schema():
    for path in _example_responses("nonconformant"):
        response = json.loads(path.read_text(encoding="utf-8"))
        assert adapter_response_conformance_errors(response), path.name


def test_validate_adapter_response_cli_round_trip(capsys):
    conformant = _example_responses("conformant")[0]
    nonconformant = _example_responses("nonconformant")[0]

    assert main(["validate-adapter-response", str(conformant)]) == 0
    assert "OK:" in capsys.readouterr().out

    assert main(["validate-adapter-response", str(nonconformant)]) == 1
    assert "ERROR:" in capsys.readouterr().out
