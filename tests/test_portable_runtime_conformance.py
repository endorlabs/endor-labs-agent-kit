from __future__ import annotations

import pytest

from endor_agent_kit.portable_runtime_conformance import (
    DATA_GAP_POLICY,
    DEGRADATION_POLICY,
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
