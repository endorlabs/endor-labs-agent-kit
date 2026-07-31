from __future__ import annotations

from endor_agent_kit.recipe import EndorAgentRecipe, HostCapabilities
from endor_agent_kit.safety_posture import source_recipe_safety_posture


def _recipe(
    *,
    safety_class: str = "read_only",
    transports: tuple[str, ...] = (),
    capabilities: HostCapabilities | None = None,
    mcp_tools: tuple[str, ...] = (),
    mcp_requirement: str = "",
    endorctl_invocations: tuple[str, ...] = (),
    agent_api_invocations: tuple[str, ...] = (),
) -> EndorAgentRecipe:
    return EndorAgentRecipe(
        recipe_schema_version=1,
        id="posture-fixture",
        name="Posture Fixture",
        version="1.0.0",
        description="Fixture",
        safety_class=safety_class,
        supported_transports=transports,
        host_capabilities_required=capabilities or HostCapabilities(),
        inputs=(),
        outputs=(),
        evals="evals/cases.yaml",
        compatible_hosts=("claude-code",),
        required_endor_mcp_tools=mcp_tools,
        endorctl_api_invocations=endorctl_invocations,
        endorctl_agent_api_invocations=agent_api_invocations,
        instructions_path="instructions.md",
        model="sonnet",
        requires_endor_mcp=mcp_requirement,
    )


def test_source_recipe_safety_posture_detects_mcp_from_any_recipe_signal():
    assert source_recipe_safety_posture(_recipe(transports=("mcp",))).uses_mcp
    assert source_recipe_safety_posture(_recipe(mcp_tools=("get_resource",))).uses_mcp
    assert source_recipe_safety_posture(_recipe(mcp_requirement="enterprise")).uses_mcp
    assert not source_recipe_safety_posture(_recipe()).uses_mcp


def test_source_recipe_safety_posture_requires_transport_and_invocations_for_endorctl_api():
    assert source_recipe_safety_posture(
        _recipe(
            transports=("endorctl_api",),
            endorctl_invocations=("lookup_package_version_uuid",),
        )
    ).uses_endorctl_api
    assert not source_recipe_safety_posture(
        _recipe(transports=("endorctl_api",))
    ).uses_endorctl_api
    assert not source_recipe_safety_posture(
        _recipe(endorctl_invocations=("lookup_package_version_uuid",))
    ).uses_endorctl_api


def test_source_recipe_safety_posture_requires_endorctl_setup_for_api_or_mutating_recipes():
    assert source_recipe_safety_posture(
        _recipe(
            transports=("endorctl_api",),
            endorctl_invocations=("lookup_package_version_uuid",),
        )
    ).requires_endorctl_setup
    assert source_recipe_safety_posture(
        _recipe(
            safety_class="mutating",
            capabilities=HostCapabilities(run_commands=True, write_files=True),
        )
    ).requires_endorctl_setup
    assert not source_recipe_safety_posture(_recipe()).requires_endorctl_setup


def test_source_recipe_safety_posture_detects_agent_attributed_endor_api():
    posture = source_recipe_safety_posture(
        _recipe(
            transports=("endorctl_agent_api",),
            agent_api_invocations=("lookup_package_version_uuid",),
        )
    )

    assert posture.uses_endorctl_agent_api
    assert posture.uses_endor_api_transport
    assert posture.requires_endorctl_setup


def test_source_recipe_safety_posture_exposes_host_capability_contract():
    posture = source_recipe_safety_posture(
        _recipe(
            safety_class="mutating",
            capabilities=HostCapabilities(
                run_commands=True,
                read_files=True,
                write_files=True,
                open_pr=True,
            ),
        )
    )

    assert posture.is_mutating
    assert posture.can_run_commands
    assert posture.can_read_files
    assert posture.can_write_files
    assert posture.can_open_change_requests
