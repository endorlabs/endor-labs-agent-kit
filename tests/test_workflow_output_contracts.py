from __future__ import annotations

from endor_agent_kit import ai_sast_triage, cli, sca_remediation
from endor_agent_kit.workflow_output_contracts import ai_sast, sca


def test_ai_sast_contracts_are_exposed_through_gate_modules():
    assert set(ai_sast.AI_SAST_GATES) == {"triage", "remediation", "pr", "exception"}
    assert ai_sast.AI_SAST_GATES["triage"].__class__.__module__.endswith(".triage_gate")
    assert ai_sast.AI_SAST_GATES["remediation"].__class__.__module__.endswith(".remediation_gate")
    assert ai_sast.AI_SAST_GATES["pr"].__class__.__module__.endswith(".remediation_gate")
    assert ai_sast.AI_SAST_GATES["exception"].__class__.__module__.endswith(".exception_gate")


def test_ai_sast_compatibility_shell_and_cli_use_gate_contract_interface():
    assert ai_sast_triage.validate_ai_sast_gate_payload is ai_sast.validate_ai_sast_gate_payload
    assert ai_sast_triage.render_ai_sast_pr_body is ai_sast.render_ai_sast_pr_body
    assert cli.validate_ai_sast_gate_payload is ai_sast.validate_ai_sast_gate_payload


def test_ai_sast_exception_gate_owns_exception_specific_requirements():
    errors = ai_sast.validate_ai_sast_gate_payload({}, gate="exception")

    assert "approvals: required before exception policy creation" in errors
    assert "exception_policies: required for exception gate" in errors


def test_sca_contracts_are_exposed_through_gate_modules():
    assert set(sca.SCA_GATES) == {"selection-plan", "apply", "validate", "pr"}
    assert sca.SCA_GATES["selection-plan"].__class__.__module__.endswith(".selection_gate")
    assert sca.SCA_GATES["apply"].__class__.__module__.endswith(".apply_gate")
    assert sca.SCA_GATES["validate"].__class__.__module__.endswith(".validation_gate")
    assert sca.SCA_GATES["pr"].__class__.__module__.endswith(".pr_gate")


def test_sca_compatibility_shell_and_cli_use_gate_contract_interface():
    assert sca_remediation.validate_sca_gate_payload is sca.validate_sca_gate_payload
    assert sca_remediation.render_sca_pr_body is sca.render_sca_pr_body
    assert cli.validate_sca_gate_payload is sca.validate_sca_gate_payload


def test_sca_pr_gate_owns_pr_body_requirement():
    errors = sca.validate_sca_gate_payload({}, gate="pr")

    assert "pr_body: required for PR gate validation" in errors

