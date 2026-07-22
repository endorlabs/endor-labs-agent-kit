from __future__ import annotations

from endor_agent_kit.agent_api import agent_api_command_errors


def test_agent_api_contract_rejects_bare_endorctl_api():
    errors = agent_api_command_errors(
        "endorctl api list -r Finding -n demo",
        agent_id="findings-browser",
    )

    assert errors == ["line 1: agent-facing Endor calls must use `endorctl agent api`"]


def test_agent_api_contract_rejects_package_manager_wrapped_endorctl():
    errors = agent_api_command_errors(
        "npx -y endorctl agent api --agent-id findings-browser "
        "list -r Finding -n demo",
        agent_id="findings-browser",
    )

    assert errors == [
        "line 1: agent-facing Endor calls must invoke installed `endorctl` directly"
    ]


def test_agent_api_contract_requires_canonical_recipe_id():
    missing = agent_api_command_errors(
        "endorctl agent api list -r Finding -n demo",
        agent_id="findings-browser",
    )
    mismatched = agent_api_command_errors(
        "endorctl agent api --agent-id cursor list -r Finding -n demo",
        agent_id="findings-browser",
    )

    assert missing == [
        "line 1: `endorctl agent api` must include `--agent-id findings-browser`"
    ]
    assert mismatched == [
        "line 1: `endorctl agent api` uses agent id 'cursor'; expected 'findings-browser'"
    ]


def test_agent_api_contract_limits_mutations_to_ai_sast_policy_create_or_update():
    assert agent_api_command_errors(
        "endorctl agent api --agent-id findings-browser list -r Finding -n demo",
        agent_id="findings-browser",
    ) == []
    assert agent_api_command_errors(
        "endorctl agent api --agent-id findings-browser create -r Policy -n demo",
        agent_id="findings-browser",
    ) == ["line 1: findings-browser is not allowed to mutate Endor resources"]
    assert agent_api_command_errors(
        "endorctl agent api --agent-id ai-sast-remediation create -r Policy -n demo\n"
        "endorctl agent api --agent-id ai-sast-remediation update -r Policy -n demo",
        agent_id="ai-sast-remediation",
    ) == []
    assert agent_api_command_errors(
        "endorctl agent api --agent-id ai-sast-remediation delete -r Policy -n demo\n"
        "endorctl agent api --agent-id ai-sast-remediation update -r Finding -n demo",
        agent_id="ai-sast-remediation",
    ) == [
        "line 1: ai-sast-remediation may create or update Policy resources only",
        "line 2: ai-sast-remediation may create or update Policy resources only",
    ]


def test_agent_api_contract_accepts_canonical_source_identity_placeholder():
    assert agent_api_command_errors(
        "endorctl agent api --agent-id <agent-id> list -r Finding -n <namespace>",
        agent_id="findings-browser",
        allow_template_identity=True,
    ) == []


def test_agent_api_contract_still_checks_permissions_for_source_identity_placeholder():
    errors = agent_api_command_errors(
        "endorctl agent api --agent-id <agent-id> delete -r Policy -n demo",
        agent_id="ai-sast-remediation",
        allow_template_identity=True,
    )

    assert any("may create or update Policy resources only" in error for error in errors)


def test_agent_api_contract_does_not_treat_prose_after_inline_command_name_as_action():
    assert agent_api_command_errors(
        "Use `endorctl agent api --agent-id <agent-id>` lookups. Do not create policies.",
        agent_id="findings-browser",
        allow_template_identity=True,
    ) == []
