"""Compile source-owned Evidence Plans into deterministic Host artifacts."""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import re
import shlex
from typing import Any

import yaml

from endor_agent_kit.knowledge_pack import (
    EndorKnowledgePack,
    default_knowledge_pack_root,
    load_knowledge_pack,
)
from endor_agent_kit.profile_contracts import compile_profile_contract
from endor_agent_kit.recipe import load_recipe


EVIDENCE_PLAN_SCHEMA_VERSION = "1"
_SAFE_OPERATIONS = frozenset({"get", "list", "local_read"})
_EXECUTION_MODES = frozenset({"prompt_fallback", "host_adapter"})
_PLACEHOLDER_RE = re.compile(r"<([^>]+)>")


@dataclass(frozen=True)
class EvidenceInputBinding:
    """One typed value supplied to a canonical query placeholder."""

    name: str
    placeholder: str
    source: str
    value_type: str
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "placeholder": self.placeholder,
            "source": self.source,
            "type": self.value_type,
            "required": self.required,
        }


@dataclass(frozen=True)
class EvidenceOutputBinding:
    """One normalized value emitted by an evidence step."""

    name: str
    path: str
    value_type: str
    required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "type": self.value_type,
            "required": self.required,
        }


@dataclass(frozen=True)
class EvidenceRetryPolicy:
    """Bounded retry/fallback policy for one step."""

    eligible: bool = False
    max_attempts: int = 1
    when: str = "never"
    append_args: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "max_attempts": self.max_attempts,
            "when": self.when,
            "append_args": list(self.append_args),
        }


@dataclass(frozen=True)
class EvidenceRoute:
    """One mutually exclusive execution route through a plan."""

    id: str
    condition: str
    exclusive_group: str
    expected_calls: int
    max_calls: int
    required_outputs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "condition": self.condition,
            "exclusive_group": self.exclusive_group,
            "expected_calls": self.expected_calls,
            "max_calls": self.max_calls,
            "required_outputs": list(self.required_outputs),
        }


@dataclass(frozen=True)
class EvidenceStep:
    """One typed canonical evidence operation in a plan DAG."""

    id: str
    recipe_id: str
    canonical_recipe_id: str
    resource: str
    operation: str
    template: str
    fields: tuple[str, ...]
    inputs: tuple[EvidenceInputBinding, ...]
    outputs: tuple[EvidenceOutputBinding, ...]
    depends_on: tuple[str, ...]
    route_id: str
    condition: str
    concurrency_group: str
    retry: EvidenceRetryPolicy
    max_calls: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "recipe_id": self.recipe_id,
            "canonical_recipe_id": self.canonical_recipe_id,
            "resource": self.resource,
            "operation": self.operation,
            "template": self.template,
            "fields": list(self.fields),
            "inputs": [binding.to_dict() for binding in self.inputs],
            "outputs": [binding.to_dict() for binding in self.outputs],
            "depends_on": list(self.depends_on),
            "route_id": self.route_id,
            "condition": self.condition,
            "concurrency_group": self.concurrency_group,
            "retry": self.retry.to_dict(),
            "max_calls": self.max_calls,
        }


@dataclass(frozen=True)
class CompiledEvidencePlan:
    """A deterministic, source-bound Evidence Plan for a runtime Host."""

    agent_id: str
    profile_id: str
    safety_class: str
    namespace_required: bool
    namespace_provenance_required: bool
    freshness_max_age_seconds: int
    cache_identity: tuple[str, ...]
    attribution_required: bool
    attribution_agent_id: str
    execution_mode: str
    prompt_recipes_exposed: bool
    host_adapter_required: bool
    expected_calls: int
    max_calls: int
    stop_conditions: tuple[str, ...]
    data_gaps_required: bool
    routes: tuple[EvidenceRoute, ...]
    steps: tuple[EvidenceStep, ...]
    source_digest: str
    agent_source_digest: str
    profile_contract_digest: str
    knowledge_pack_digest: str
    plan_digest: str
    schema_version: str = EVIDENCE_PLAN_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Return the deterministic provider-neutral representation."""

        return {
            "schema_version": self.schema_version,
            "agent_id": self.agent_id,
            "profile_id": self.profile_id,
            "safety_class": self.safety_class,
            "scope": {
                "namespace_required": self.namespace_required,
                "namespace_provenance_required": self.namespace_provenance_required,
            },
            "freshness": {"max_age_seconds": self.freshness_max_age_seconds},
            "cache_identity": list(self.cache_identity),
            "attribution": {
                "required": self.attribution_required,
                "agent_id": self.attribution_agent_id,
            },
            "execution": {
                "mode": self.execution_mode,
                "prompt_recipes_exposed": self.prompt_recipes_exposed,
                "host_adapter_required": self.host_adapter_required,
            },
            "gate": {
                "expected_calls": self.expected_calls,
                "max_calls": self.max_calls,
                "stop_conditions": list(self.stop_conditions),
                "data_gaps_required": self.data_gaps_required,
            },
            "routes": [route.to_dict() for route in self.routes],
            "steps": [step.to_dict() for step in self.steps],
            "provenance": {
                "source_digest": self.source_digest,
                "agent_source_digest": self.agent_source_digest,
                "profile_contract_digest": self.profile_contract_digest,
                "knowledge_pack_digest": self.knowledge_pack_digest,
                "plan_digest": self.plan_digest,
            },
        }

    def to_json_bytes(self) -> bytes:
        """Serialize identically for identical source."""

        return (
            json.dumps(
                self.to_dict(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")


def compile_evidence_plan(
    agent_id: str,
    profile_id: str,
    *,
    knowledge_pack_root: str | Path | None = None,
) -> CompiledEvidencePlan:
    """Compile one source-declared Evidence Plan or fail closed."""

    for plan in compile_evidence_plans(agent_id, knowledge_pack_root=knowledge_pack_root):
        if plan.profile_id == profile_id:
            return plan
    raise ValueError(f"unknown Evidence Plan {agent_id!r}/{profile_id!r}")


def compile_evidence_plans(
    agent_id: str,
    *,
    knowledge_pack_root: str | Path | None = None,
) -> tuple[CompiledEvidencePlan, ...]:
    """Compile every source-declared Evidence Plan for one agent."""

    pack_root = (
        Path(knowledge_pack_root)
        if knowledge_pack_root is not None
        else default_knowledge_pack_root()
    )
    source_path = pack_root / "evidence-plans" / f"{agent_id}.yaml"
    if not source_path.is_file():
        return ()
    data = _load_mapping(source_path)
    if str(data.get("schema_version")) != EVIDENCE_PLAN_SCHEMA_VERSION:
        raise ValueError(
            f"{source_path.name}: schema_version must be {EVIDENCE_PLAN_SCHEMA_VERSION}"
        )
    source_agent_id = str(data.get("agent_id", ""))
    if source_agent_id != agent_id:
        raise ValueError(
            f"{source_path.name}: agent_id {source_agent_id!r} does not match {agent_id!r}"
        )

    raw_plans = data.get("plans")
    if not isinstance(raw_plans, list) or not raw_plans:
        raise ValueError(f"{source_path.name}: plans must be a non-empty list")
    pack = load_knowledge_pack(pack_root)
    workflow = pack.workflow_for(agent_id)
    if workflow is None:
        raise ValueError(f"{source_path.name}: unknown Knowledge Pack agent {agent_id!r}")

    source_digest = _digest_files((source_path,), relative_to=pack_root)
    compiled: list[CompiledEvidencePlan] = []
    seen_profiles: set[str] = set()
    for index, raw_plan in enumerate(raw_plans):
        if not isinstance(raw_plan, dict):
            raise ValueError(f"{source_path.name}.plans[{index}]: must be an object")
        plan = _compile_raw_plan(
            raw_plan,
            agent_id=agent_id,
            source_digest=source_digest,
            pack_root=pack_root,
            pack=pack,
        )
        if plan.profile_id in seen_profiles:
            raise ValueError(
                f"{source_path.name}: duplicate profile_id {plan.profile_id!r}"
            )
        seen_profiles.add(plan.profile_id)
        errors = validate_evidence_plan(
            plan,
            expected_agent_id=agent_id,
            knowledge_pack=pack,
        )
        if errors:
            raise ValueError("\n".join(f"{source_path.name}: {error}" for error in errors))
        plan_digest = _plan_digest(plan)
        compiled.append(replace(plan, plan_digest=plan_digest))
    return tuple(compiled)


def validate_evidence_plan(
    plan: CompiledEvidencePlan,
    *,
    expected_agent_id: str | None = None,
    knowledge_pack: EndorKnowledgePack | None = None,
) -> list[str]:
    """Return all structural, safety, provenance, and budget errors."""

    errors: list[str] = []
    expected = expected_agent_id or plan.agent_id
    if plan.agent_id != expected:
        errors.append(
            f"agent_id {plan.agent_id!r} does not match expected agent_id {expected!r}"
        )
    if plan.attribution_agent_id != plan.agent_id:
        errors.append(
            "attribution agent_id must exactly match the plan agent_id"
        )
    if not plan.attribution_required:
        errors.append("agent attribution is required")
    if plan.safety_class != "read_only":
        errors.append("Evidence Plans must use read_only safety_class")
    if not plan.namespace_required:
        errors.append("namespace is required for Endor Evidence Plans")
    if not plan.namespace_provenance_required:
        errors.append("namespace provenance is required for Endor Evidence Plans")
    if plan.freshness_max_age_seconds <= 0:
        errors.append("freshness max_age_seconds must be positive")
    for identity in ("agent_id", "profile_id", "namespace", "source_digest"):
        if identity not in plan.cache_identity:
            errors.append(f"cache_identity must include {identity!r}")
    if plan.execution_mode not in _EXECUTION_MODES:
        errors.append(f"unknown execution mode {plan.execution_mode!r}")
    if plan.execution_mode == "host_adapter" and plan.prompt_recipes_exposed:
        errors.append("prompt recipes must not be exposed with host_adapter execution")
    if plan.execution_mode == "prompt_fallback" and not plan.prompt_recipes_exposed:
        errors.append("prompt_fallback mode must expose prompt recipes")
    if plan.execution_mode == "prompt_fallback" and not plan.host_adapter_required:
        errors.append("prompt_fallback plan must declare that a Host adapter is required")
    if plan.expected_calls < 0 or plan.max_calls < 1 or plan.expected_calls > plan.max_calls:
        errors.append("gate call budget must satisfy 0 <= expected_calls <= max_calls")
    if not plan.stop_conditions:
        errors.append("at least one stop condition is required")
    if not plan.data_gaps_required:
        errors.append("data_gaps behavior is required")
    if plan.plan_digest and plan.plan_digest != _plan_digest(plan):
        errors.append("plan_digest does not match the compiled plan content")
    for name, digest in (
        ("source_digest", plan.source_digest),
        ("agent_source_digest", plan.agent_source_digest),
        ("profile_contract_digest", plan.profile_contract_digest),
        ("knowledge_pack_digest", plan.knowledge_pack_digest),
        ("plan_digest", plan.plan_digest),
    ):
        if digest and not re.fullmatch(r"[0-9a-f]{64}", digest):
            errors.append(f"{name} must be a lowercase SHA-256 digest")

    routes = {route.id: route for route in plan.routes}
    if len(routes) != len(plan.routes):
        errors.append("route ids must be unique")
    steps = {step.id: step for step in plan.steps}
    if len(steps) != len(plan.steps):
        errors.append("step ids must be unique")
    _validate_route_exclusivity(plan.routes, errors)

    for step in plan.steps:
        prefix = f"step {step.id!r}"
        if step.route_id not in routes:
            errors.append(f"{prefix}: references unknown route {step.route_id!r}")
        if step.operation not in _SAFE_OPERATIONS:
            errors.append(f"{prefix}: unsafe operation {step.operation!r}")
        if step.max_calls < (0 if step.operation == "local_read" else 1):
            errors.append(f"{prefix}: max_calls is too small for its operation")
        if step.retry.eligible:
            if step.retry.max_attempts < 2:
                errors.append(f"{prefix}: retry requires bounded max_attempts of at least 2")
            if step.retry.max_attempts > step.max_calls:
                errors.append(f"{prefix}: retry attempts exceed the step call budget")
            if step.retry.when != "parent_namespace_empty_result":
                errors.append(f"{prefix}: retry uses an unsupported eligibility condition")
            if step.retry.append_args != ("--traverse",):
                errors.append(f"{prefix}: retry fallback arguments are not allowlisted")
        elif step.retry.max_attempts != 1:
            errors.append(f"{prefix}: ineligible retry must use max_attempts 1")
        elif step.retry.when != "never" or step.retry.append_args:
            errors.append(f"{prefix}: ineligible retry must not expose fallback behavior")
        for dependency in step.depends_on:
            if dependency not in steps:
                errors.append(f"{prefix}: unknown dependency {dependency!r}")
            elif steps[dependency].route_id != step.route_id:
                errors.append(f"{prefix}: dependency crosses mutually exclusive routes")
        _validate_step_condition(step, steps, errors)
        _validate_bindings(step, steps, errors)
        _validate_endor_step(step, plan, errors)

    if _has_dependency_cycle(plan.steps):
        errors.append("plan contains a dependency cycle")

    for route in plan.routes:
        route_steps = tuple(step for step in plan.steps if step.route_id == route.id)
        if not route_steps:
            errors.append(f"route {route.id!r}: must contain at least one step")
            continue
        route_max = sum(step.max_calls for step in route_steps)
        if route.expected_calls < 0 or route.expected_calls > route.max_calls:
            errors.append(f"route {route.id!r}: invalid call budget")
        if route_max > route.max_calls:
            errors.append(
                f"route {route.id!r}: step call budget {route_max} exceeds route call budget {route.max_calls}"
            )
        if route.max_calls > plan.max_calls:
            errors.append(
                f"route {route.id!r}: call budget {route.max_calls} exceeds gate call budget {plan.max_calls}"
            )
        _validate_required_outputs(route, route_steps, errors)

    pack = knowledge_pack or load_knowledge_pack()
    _validate_canonical_recipes(plan, pack, errors)
    return errors


def _compile_raw_plan(
    raw: dict[str, Any],
    *,
    agent_id: str,
    source_digest: str,
    pack_root: Path,
    pack: EndorKnowledgePack,
) -> CompiledEvidencePlan:
    profile_id = _required_string(raw, "profile_id")
    workflow = pack.workflow_for(agent_id)
    if workflow is None or workflow.task_profile_for(profile_id) is None:
        raise ValueError(f"unknown task profile {profile_id!r} for agent {agent_id!r}")
    profile_contract = compile_profile_contract(
        agent_id,
        profile_id,
        knowledge_pack_root=pack_root,
    )
    execution = _required_mapping(raw, "execution")
    scope = _required_mapping(raw, "scope")
    freshness = _required_mapping(raw, "freshness")
    attribution = _required_mapping(raw, "attribution")
    gate = _required_mapping(raw, "gate")
    routes = tuple(_route(item) for item in _required_mappings(raw, "routes"))
    steps = tuple(
        _step(item, profile_id=profile_id, pack=pack, agent_id=agent_id)
        for item in _required_mappings(raw, "steps")
    )
    recipe_path = pack_root.parent / "agents" / agent_id / "recipe.yaml"
    recipe = load_recipe(recipe_path)
    instructions_path = recipe_path.parent / recipe.instructions_path
    return CompiledEvidencePlan(
        agent_id=agent_id,
        profile_id=profile_id,
        safety_class=_required_string(raw, "safety_class"),
        namespace_required=_required_bool(scope, "namespace_required"),
        namespace_provenance_required=_required_bool(
            scope, "namespace_provenance_required"
        ),
        freshness_max_age_seconds=_required_int(freshness, "max_age_seconds"),
        cache_identity=_required_strings(raw, "cache_identity"),
        attribution_required=_required_bool(attribution, "required"),
        attribution_agent_id=_required_string(attribution, "agent_id").replace(
            "<agent-id>", agent_id
        ),
        execution_mode=_required_string(execution, "mode"),
        prompt_recipes_exposed=_required_bool(execution, "prompt_recipes_exposed"),
        host_adapter_required=_required_bool(execution, "host_adapter_required"),
        expected_calls=_required_int(gate, "expected_calls"),
        max_calls=_required_int(gate, "max_calls"),
        stop_conditions=_required_strings(gate, "stop_conditions"),
        data_gaps_required=_required_bool(gate, "data_gaps_required"),
        routes=routes,
        steps=steps,
        source_digest=source_digest,
        agent_source_digest=_digest_files(
            (recipe_path, instructions_path), relative_to=pack_root.parent
        ),
        profile_contract_digest=profile_contract.contract_digest,
        knowledge_pack_digest=profile_contract.knowledge_pack_digest,
        plan_digest="",
    )


def _step(
    raw: dict[str, Any],
    *,
    profile_id: str,
    pack: EndorKnowledgePack,
    agent_id: str,
) -> EvidenceStep:
    recipe_id = _required_string(raw, "recipe_id")
    canonical_recipe_id = _required_string(raw, "canonical_recipe_id")
    workflow = pack.workflow_for(agent_id)
    query_recipe = next(
        (
            recipe
            for recipe in (workflow.evidence_query_recipes if workflow else ())
            if recipe.profile_id == profile_id and recipe.id == recipe_id
        ),
        None,
    )
    canonical_recipe = pack.query_recipes.get(canonical_recipe_id)
    if query_recipe is None and (
        recipe_id != canonical_recipe_id or canonical_recipe is None
    ):
        raise ValueError(
            f"step {_required_string(raw, 'id')!r}: unknown recipe {recipe_id!r} "
            f"for profile {profile_id!r}"
        )
    retry_raw = raw.get("retry", {})
    if not isinstance(retry_raw, dict):
        raise ValueError(f"step {raw.get('id')!r}: retry must be an object")
    retry = EvidenceRetryPolicy(
        eligible=_optional_bool(retry_raw, "eligible", False),
        max_attempts=_optional_int(retry_raw, "max_attempts", 1),
        when=_optional_string(retry_raw, "when", "never"),
        append_args=_optional_strings(retry_raw, "append_args"),
    )
    return EvidenceStep(
        id=_required_string(raw, "id"),
        recipe_id=recipe_id,
        canonical_recipe_id=canonical_recipe_id,
        resource=(query_recipe.resource if query_recipe else canonical_recipe.resource),
        operation=_required_string(raw, "operation"),
        template=(
            query_recipe.template if query_recipe else canonical_recipe.template
        ).replace("<agent-id>", agent_id),
        fields=(query_recipe.fields if query_recipe else canonical_recipe.fields),
        inputs=tuple(_input_binding(item) for item in _required_mappings(raw, "inputs")),
        outputs=tuple(_output_binding(item) for item in _required_mappings(raw, "outputs")),
        depends_on=_optional_strings(raw, "depends_on"),
        route_id=_required_string(raw, "route_id"),
        condition=_required_string(raw, "condition"),
        concurrency_group=_required_string(raw, "concurrency_group"),
        retry=retry,
        max_calls=_required_int(raw, "max_calls"),
    )


def _route(raw: dict[str, Any]) -> EvidenceRoute:
    return EvidenceRoute(
        id=_required_string(raw, "id"),
        condition=_required_string(raw, "condition"),
        exclusive_group=_required_string(raw, "exclusive_group"),
        expected_calls=_required_int(raw, "expected_calls"),
        max_calls=_required_int(raw, "max_calls"),
        required_outputs=_required_strings(raw, "required_outputs"),
    )


def _input_binding(raw: dict[str, Any]) -> EvidenceInputBinding:
    return EvidenceInputBinding(
        name=_required_string(raw, "name"),
        placeholder=_required_string(raw, "placeholder"),
        source=_required_string(raw, "source"),
        value_type=_required_string(raw, "type"),
        required=_optional_bool(raw, "required", True),
    )


def _output_binding(raw: dict[str, Any]) -> EvidenceOutputBinding:
    return EvidenceOutputBinding(
        name=_required_string(raw, "name"),
        path=_required_string(raw, "path"),
        value_type=_required_string(raw, "type"),
        required=_optional_bool(raw, "required", True),
    )


def _validate_route_exclusivity(routes: tuple[EvidenceRoute, ...], errors: list[str]) -> None:
    groups: dict[str, list[EvidenceRoute]] = {}
    for route in routes:
        groups.setdefault(route.exclusive_group, []).append(route)
    for group, members in groups.items():
        conditions = [member.condition for member in members]
        if len(set(conditions)) != len(conditions):
            errors.append(f"route group {group!r}: conditions must be unique")
        if "always" in conditions and len(members) > 1:
            errors.append(f"route group {group!r}: always route cannot have siblings")
        if len(members) == 1 and conditions != ["always"]:
            errors.append(f"route group {group!r}: a single route must use condition 'always'")
        if len(members) == 2 and "always" not in conditions:
            complements = {
                condition.removesuffix("_present")
                for condition in conditions
                if condition.endswith("_present")
            } & {
                condition.removesuffix("_absent")
                for condition in conditions
                if condition.endswith("_absent")
            }
            if not complements:
                errors.append(
                    f"route group {group!r}: two routes must use complementary present/absent conditions"
                )
            if not all(
                re.fullmatch(r"runtime\.[a-z][a-z0-9_]*_(?:present|absent)", condition)
                for condition in conditions
            ):
                errors.append(f"route group {group!r}: conditions use an unsupported selector")


def _validate_step_condition(
    step: EvidenceStep,
    steps: dict[str, EvidenceStep],
    errors: list[str],
) -> None:
    if step.condition == "always":
        return
    match = re.fullmatch(r"steps\.([a-z][a-z0-9-]*)\.([a-z][a-z0-9_]*)_missing", step.condition)
    if match is None:
        errors.append(f"step {step.id!r}: unknown condition {step.condition!r}")
        return
    source_step_id, output_name = match.groups()
    source_step = steps.get(source_step_id)
    if source_step is None or output_name not in {
        output.name for output in source_step.outputs
    }:
        errors.append(f"step {step.id!r}: condition references unknown output")
    if source_step_id not in _dependency_ancestors(step.id, steps):
        errors.append(f"step {step.id!r}: condition source is not a dependency")


def _validate_bindings(
    step: EvidenceStep,
    steps: dict[str, EvidenceStep],
    errors: list[str],
) -> None:
    prefix = f"step {step.id!r}"
    placeholders = set(_PLACEHOLDER_RE.findall(step.template))
    bound_placeholders = {binding.placeholder for binding in step.inputs}
    missing = sorted(placeholders - bound_placeholders)
    extra = sorted(bound_placeholders - placeholders)
    if missing:
        errors.append(f"{prefix}: missing bindings for placeholders {missing!r}")
    if extra:
        errors.append(f"{prefix}: bindings reference unknown placeholders {extra!r}")
    if len(bound_placeholders) != len(step.inputs):
        errors.append(f"{prefix}: placeholder bindings must be unique")
    input_names = [binding.name for binding in step.inputs]
    if len(set(input_names)) != len(input_names):
        errors.append(f"{prefix}: input binding names must be unique")
    output_names = [output.name for output in step.outputs]
    if len(set(output_names)) != len(output_names):
        errors.append(f"{prefix}: output binding names must be unique")
    for binding in step.inputs:
        if binding.source.startswith("steps."):
            parts = binding.source.split(".", 2)
            if len(parts) != 3 or parts[1] not in steps:
                errors.append(f"{prefix}: binding {binding.name!r} references unknown step")
                continue
            source_step = steps[parts[1]]
            if parts[2] not in {output.name for output in source_step.outputs}:
                errors.append(
                    f"{prefix}: binding {binding.name!r} references unknown output {parts[2]!r}"
                )
            if parts[1] not in _dependency_ancestors(step.id, steps):
                errors.append(
                    f"{prefix}: binding {binding.name!r} source is not a dependency"
                )
        elif not (
            binding.source.startswith("runtime.") or binding.source == "plan.agent_id"
        ):
            errors.append(f"{prefix}: binding {binding.name!r} has unknown source")


def _validate_endor_step(
    step: EvidenceStep,
    plan: CompiledEvidencePlan,
    errors: list[str],
) -> None:
    if step.operation == "local_read":
        return
    prefix = f"step {step.id!r}"
    try:
        tokens = shlex.split(step.template)
    except ValueError:
        errors.append(f"{prefix}: query template cannot be parsed")
        return
    expected_prefix = ["endorctl", "agent", "api", "--agent-id", plan.agent_id]
    if tokens[:5] != expected_prefix:
        errors.append(f"{prefix}: must use attributed endorctl agent api transport")
    if len(tokens) < 6 or tokens[5] != step.operation:
        errors.append(f"{prefix}: operation does not match the canonical query template")
    if not plan.namespace_required or "<namespace>" not in step.template:
        errors.append(f"{prefix}: missing explicit namespace placeholder")
    namespace_bindings = [
        binding
        for binding in step.inputs
        if binding.placeholder == "namespace"
        and binding.source == "runtime.namespace"
        and binding.required
    ]
    if not namespace_bindings:
        errors.append(f"{prefix}: missing required runtime namespace binding")
    if step.operation == "list" and not any(
        flag in tokens for flag in ("--field-mask", "--count", "--group-aggregation-paths")
    ):
        errors.append(f"{prefix}: list operation lacks field-mask, count, or aggregation discipline")
    if any(token in {"create", "update", "delete"} for token in tokens[5:7]):
        errors.append(f"{prefix}: query template contains an unsafe operation")


def _validate_required_outputs(
    route: EvidenceRoute,
    route_steps: tuple[EvidenceStep, ...],
    errors: list[str],
) -> None:
    outputs = {
        f"steps.{step.id}.{output.name}"
        for step in route_steps
        for output in step.outputs
    }
    for required in route.required_outputs:
        if required not in outputs:
            errors.append(
                f"route {route.id!r}: required output {required!r} is not reachable"
            )


def _validate_canonical_recipes(
    plan: CompiledEvidencePlan,
    pack: EndorKnowledgePack,
    errors: list[str],
) -> None:
    workflow = pack.workflow_for(plan.agent_id)
    if workflow is None:
        errors.append(f"unknown Knowledge Pack workflow {plan.agent_id!r}")
        return
    for step in plan.steps:
        prefix = f"step {step.id!r}"
        workflow_recipe = next(
            (
                recipe
                for recipe in workflow.evidence_query_recipes
                if recipe.profile_id == plan.profile_id and recipe.id == step.recipe_id
            ),
            None,
        )
        if workflow_recipe is None:
            if step.recipe_id != step.canonical_recipe_id:
                errors.append(f"{prefix}: workflow recipe is missing")
        elif workflow_recipe.canonical_id != step.canonical_recipe_id:
            errors.append(f"{prefix}: canonical recipe id does not match workflow source")
        canonical = pack.query_recipes.get(step.canonical_recipe_id)
        if canonical is None:
            errors.append(f"{prefix}: canonical recipe is missing")
            continue
        if step.resource != canonical.resource:
            errors.append(f"{prefix}: resource does not equal the canonical recipe")
        if step.fields != canonical.fields:
            errors.append(f"{prefix}: fields do not equal the canonical recipe")
        canonical_template = canonical.template.replace("<agent-id>", plan.agent_id)
        if _normalize(step.template) != _normalize(canonical_template):
            errors.append(f"{prefix}: template does not equal the canonical recipe")


def _has_dependency_cycle(steps: tuple[EvidenceStep, ...]) -> bool:
    graph = {step.id: step.depends_on for step in steps}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(step_id: str) -> bool:
        if step_id in visiting:
            return True
        if step_id in visited or step_id not in graph:
            return False
        visiting.add(step_id)
        if any(visit(dependency) for dependency in graph[step_id]):
            return True
        visiting.remove(step_id)
        visited.add(step_id)
        return False

    return any(visit(step_id) for step_id in graph)


def _dependency_ancestors(step_id: str, steps: dict[str, EvidenceStep]) -> set[str]:
    ancestors: set[str] = set()
    pending = list(steps.get(step_id).depends_on if step_id in steps else ())
    while pending:
        dependency = pending.pop()
        if dependency in ancestors:
            continue
        ancestors.add(dependency)
        if dependency in steps:
            pending.extend(steps[dependency].depends_on)
    return ancestors


def _plan_digest(plan: CompiledEvidencePlan) -> str:
    payload = plan.to_dict()
    payload["provenance"].pop("plan_digest", None)
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _digest_files(paths: tuple[Path, ...], *, relative_to: Path) -> str:
    digest = hashlib.sha256()
    for path in paths:
        if not path.is_file():
            raise ValueError(f"Evidence Plan source file is missing: {path}")
        digest.update(path.relative_to(relative_to).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _load_mapping(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: expected a YAML object")
    return data


def _required_mapping(data: dict[str, Any], field: str) -> dict[str, Any]:
    value = data.get(field)
    if not isinstance(value, dict):
        raise ValueError(f"{field}: must be an object")
    return value


def _required_mappings(data: dict[str, Any], field: str) -> tuple[dict[str, Any], ...]:
    value = data.get(field)
    if not isinstance(value, list) or not value or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"{field}: must be a non-empty list of objects")
    return tuple(value)


def _required_string(data: dict[str, Any], field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}: must be a non-empty string")
    return value.strip()


def _optional_string(data: dict[str, Any], field: str, default: str) -> str:
    value = data.get(field, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field}: must be a non-empty string")
    return value.strip()


def _required_strings(data: dict[str, Any], field: str) -> tuple[str, ...]:
    value = data.get(field)
    if not isinstance(value, list) or not value or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(f"{field}: must be a non-empty list of strings")
    return tuple(item.strip() for item in value)


def _optional_strings(data: dict[str, Any], field: str) -> tuple[str, ...]:
    value = data.get(field, [])
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(f"{field}: must be a list of strings")
    return tuple(item.strip() for item in value)


def _required_int(data: dict[str, Any], field: str) -> int:
    value = data.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field}: must be an integer")
    return value


def _optional_int(data: dict[str, Any], field: str, default: int) -> int:
    value = data.get(field, default)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field}: must be an integer")
    return value


def _required_bool(data: dict[str, Any], field: str) -> bool:
    value = data.get(field)
    if not isinstance(value, bool):
        raise ValueError(f"{field}: must be a boolean")
    return value


def _optional_bool(data: dict[str, Any], field: str, default: bool) -> bool:
    value = data.get(field, default)
    if not isinstance(value, bool):
        raise ValueError(f"{field}: must be a boolean")
    return value


def _normalize(value: str) -> str:
    return " ".join(value.split())
