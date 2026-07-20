"""Declarative customer policy packs for Endor Agent Kit workflows."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

POLICY_PACK_SCHEMA_VERSION = 1
POLICY_EFFECTS = frozenset({"allow", "warn", "require_review", "deny"})
POLICY_DECISIONS = frozenset(
    {"passed", "warned", "requires_review", "blocked", "not_applicable", "unavailable"}
)
MISSING_FACT_POLICIES = frozenset({"deny", "warn", "allow", "unavailable"})
CONDITION_OPERATORS = frozenset(
    {
        "exists",
        "equals",
        "not_equals",
        "in",
        "contains",
        "gt",
        "gte",
        "lt",
        "lte",
        "version_gt",
        "version_gte",
        "version_lt",
        "version_lte",
    }
)
CONDITION_FIELDS = ("when", "deny_if", "warn_if", "require_review_if", "allow_if")
BLOCKING_DECISIONS = frozenset({"blocked", "requires_review", "unavailable"})
POLICY_PACK_FIELDS = frozenset({"policy_pack_version", "id", "version", "policies"})
POLICY_FIELDS = frozenset(
    {
        "id",
        "title",
        "effect",
        "message",
        "applies_to",
        "when",
        "allow_if",
        "warn_if",
        "require_review_if",
        "deny_if",
        "on_missing_facts",
    }
)
APPLIES_TO_FIELDS = frozenset({"agents", "ecosystems"})


class PolicyPackLoadError(ValueError):
    """Raised when a policy pack cannot be parsed as YAML."""


@dataclass(frozen=True)
class ConditionResult:
    """Tri-state condition result plus evaluation metadata."""

    matched: bool | None
    facts_used: frozenset[str]
    missing_facts: frozenset[str]
    invalid_facts: frozenset[str] = frozenset()


def load_policy_pack(path: str | Path) -> dict[str, Any]:
    """Load one policy pack YAML file as a mapping."""

    policy_path = Path(path)
    try:
        data = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise PolicyPackLoadError(f"invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("policy pack must be a YAML mapping")
    return data


def policy_pack_sha256(path: str | Path) -> str:
    """Return the SHA-256 digest for one policy pack file."""

    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_policy_pack_file(path: str | Path) -> list[str]:
    """Validate one policy pack YAML file."""

    try:
        data = load_policy_pack(path)
    except PolicyPackLoadError as exc:
        return [f"policy_pack: {exc}"]
    except (OSError, ValueError) as exc:
        return [f"policy pack: failed to read YAML: {exc}"]
    return validate_policy_pack_data(data)


def validate_policy_pack_data(data: dict[str, Any]) -> list[str]:
    """Return all validation errors for one policy pack mapping."""

    errors = _unsupported_field_errors(data, POLICY_PACK_FIELDS, "policy_pack")
    if (
        type(data.get("policy_pack_version")) is not int
        or data["policy_pack_version"] != POLICY_PACK_SCHEMA_VERSION
    ):
        errors.append("policy_pack_version: must be 1")
    for field in ("id", "version"):
        if not _text(data.get(field)):
            errors.append(f"{field}: must be a non-empty string")

    policies = data.get("policies")
    if not isinstance(policies, list):
        errors.append("policies: must be a list")
        return errors

    seen: set[str] = set()
    for index, policy in enumerate(policies):
        prefix = f"policies[{index}]"
        if not isinstance(policy, dict):
            errors.append(f"{prefix}: must be a mapping")
            continue
        errors.extend(_unsupported_field_errors(policy, POLICY_FIELDS, prefix))
        policy_id = _text(policy.get("id"))
        if not policy_id:
            errors.append(f"{prefix}.id: must be a non-empty string")
        elif policy_id in seen:
            errors.append(f"{prefix}.id: duplicate policy id {policy_id!r}")
        else:
            seen.add(policy_id)
        if not _text(policy.get("title")):
            errors.append(f"{prefix}.title: must be a non-empty string")
        effect = _text(policy.get("effect"))
        if effect not in POLICY_EFFECTS:
            errors.append(f"{prefix}.effect: must be one of {', '.join(sorted(POLICY_EFFECTS))}")
        else:
            expected_condition = f"{effect}_if"
            for field in CONDITION_FIELDS:
                if field not in {"when", expected_condition} and field in policy:
                    errors.append(
                        f"{prefix}.{field}: does not match effect {effect!r}; "
                        f"use {expected_condition}"
                    )
        missing = (
            _text(policy["on_missing_facts"])
            if "on_missing_facts" in policy
            else "deny"
        )
        if missing not in MISSING_FACT_POLICIES:
            errors.append(
                f"{prefix}.on_missing_facts: must be one of "
                + ", ".join(sorted(MISSING_FACT_POLICIES))
            )
        if not _text(policy.get("message")):
            errors.append(f"{prefix}.message: required for every policy")
        if "applies_to" in policy:
            errors.extend(_validate_applies_to(policy["applies_to"], prefix))
        for field in CONDITION_FIELDS:
            if field in policy:
                errors.extend(_validate_condition(policy[field], f"{prefix}.{field}"))
    return errors


def evaluate_policy_pack_file(
    path: str | Path,
    facts: dict[str, Any],
    *,
    agent_id: str = "",
    ecosystem: str = "",
) -> list[dict[str, Any]]:
    """Load and evaluate one policy pack file."""

    data = load_policy_pack(path)
    errors = validate_policy_pack_data(data)
    if errors:
        raise ValueError("\n".join(errors))
    return evaluate_policy_pack(data, facts, agent_id=agent_id, ecosystem=ecosystem)


def evaluate_policy_pack(
    data: dict[str, Any],
    facts: dict[str, Any],
    *,
    agent_id: str = "",
    ecosystem: str = "",
) -> list[dict[str, Any]]:
    """Evaluate all policies in a valid policy pack against a fact bag."""

    resolved_agent = agent_id or _fact_text(facts, "agent.id") or _fact_text(facts, "agent_id")
    resolved_ecosystem = (
        ecosystem
        or _fact_text(facts, "ecosystem")
        or _fact_text(facts, "package.ecosystem")
        or _fact_text(facts, "proposed.ecosystem")
    )
    evaluations: list[dict[str, Any]] = []
    for policy in data.get("policies", []):
        if not isinstance(policy, dict):
            continue
        evaluations.append(
            _evaluate_policy(
                policy,
                facts,
                agent_id=resolved_agent,
                ecosystem=resolved_ecosystem,
            )
        )
    return evaluations


def policy_fact_preflight_errors(
    data: dict[str, Any],
    facts: dict[str, Any],
    *,
    agent_id: str = "",
    ecosystem: str = "",
) -> list[str]:
    """Return missing or invalid facts needed to decide policy applicability.

    Scope and ``when`` conditions decide whether a policy applies, so a trusted
    runtime must resolve them before activation. Effect-condition facts remain
    governed by each policy's ``on_missing_facts`` behavior.
    """

    resolved_agent = agent_id or _fact_text(facts, "agent.id") or _fact_text(
        facts, "agent_id"
    )
    resolved_ecosystem = (
        ecosystem
        or _fact_text(facts, "ecosystem")
        or _fact_text(facts, "package.ecosystem")
        or _fact_text(facts, "proposed.ecosystem")
    )
    errors: list[str] = []
    for policy in data.get("policies", []):
        if not isinstance(policy, dict):
            continue
        policy_id = _text(policy.get("id")) or "<unknown>"
        scope = _applies_to(
            policy.get("applies_to"),
            agent_id=resolved_agent,
            ecosystem=resolved_ecosystem,
        )
        if scope.matched is False:
            continue
        if scope.matched is None:
            if scope.missing_facts:
                errors.append(
                    f"policy {policy_id!r} applicability: missing trusted facts "
                    f"{sorted(scope.missing_facts)!r}"
                )
            continue
        if "when" not in policy:
            continue
        applicability = _eval_condition(policy["when"], facts)
        if applicability.matched is not None:
            continue
        if applicability.missing_facts:
            errors.append(
                f"policy {policy_id!r} applicability: missing trusted facts "
                f"{sorted(applicability.missing_facts)!r}"
            )
        if applicability.invalid_facts:
            errors.append(
                f"policy {policy_id!r} applicability: invalid trusted facts "
                f"{sorted(applicability.invalid_facts)!r}"
            )
    return errors


def policy_output_errors(
    payload: dict[str, Any],
    *,
    policy_pack: dict[str, Any] | None = None,
    policy_sha256: str = "",
    mutation_gate: bool = False,
    trusted_evaluations: list[dict[str, Any]] | None = None,
) -> list[str]:
    """Validate policy context/evaluation fields in an agent output payload."""

    errors: list[str] = []
    context = payload.get("policy_context")
    evaluations = payload.get("policy_evaluations")
    if context is None and evaluations is None and policy_pack is None:
        return errors
    if not isinstance(context, dict):
        errors.append("policy_context: required object when policy support is enabled")
        context = {}
    if not isinstance(evaluations, list):
        errors.append("policy_evaluations: required array when policy support is enabled")
        evaluations = []

    status = _text(context.get("status"))
    if policy_pack is not None:
        if status != "loaded":
            errors.append("policy_context.status: must be loaded when --policy-pack is supplied")
        if context.get("pack_id") != policy_pack.get("id"):
            errors.append("policy_context.pack_id: does not match supplied policy pack")
        if context.get("pack_version") != policy_pack.get("version"):
            errors.append("policy_context.pack_version: does not match supplied policy pack")
        if policy_sha256 and context.get("sha256") != policy_sha256:
            errors.append("policy_context.sha256: does not match supplied policy pack")
        if not evaluations and policy_pack.get("policies"):
            errors.append("policy_evaluations: required when --policy-pack declares policies")
        if trusted_evaluations is None:
            errors.append("policy_evaluations: trusted policy evaluation is required")
    elif status not in {"", "not_configured", "loaded", "unavailable"}:
        errors.append("policy_context.status: must be not_configured, loaded, or unavailable")

    for index, evaluation in enumerate(evaluations):
        if not isinstance(evaluation, dict):
            errors.append(f"policy_evaluations[{index}]: must be an object")
            continue
        decision = _text(evaluation.get("decision"))
        if decision not in POLICY_DECISIONS:
            errors.append(
                f"policy_evaluations[{index}].decision: must be one of "
                + ", ".join(sorted(POLICY_DECISIONS))
            )
        if mutation_gate and decision in BLOCKING_DECISIONS:
            errors.append(
                f"policy_evaluations[{index}].decision: {decision} blocks mutation gate"
            )
    if trusted_evaluations is not None:
        errors.extend(_trusted_evaluation_errors(evaluations, trusted_evaluations))
    return errors


def _trusted_evaluation_errors(
    evaluations: list[Any],
    trusted_evaluations: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    trusted_ids = {evaluation["policy_id"] for evaluation in trusted_evaluations}
    for index, evaluation in enumerate(evaluations):
        if isinstance(evaluation, dict) and evaluation.get("policy_id") not in trusted_ids:
            errors.append(
                f"policy_evaluations[{index}].policy_id: not present in trusted policy evaluations"
            )
    for expected in trusted_evaluations:
        policy_id = expected["policy_id"]
        matches = [
            (index, evaluation)
            for index, evaluation in enumerate(evaluations)
            if isinstance(evaluation, dict) and evaluation.get("policy_id") == policy_id
        ]
        if len(matches) != 1:
            errors.append(
                f"policy_evaluations: must contain exactly one trusted evaluation for {policy_id!r}"
            )
            continue
        index, evaluation = matches[0]
        for field in (
            "effect",
            "decision",
            "message",
            "facts_used",
            "missing_facts",
            "invalid_facts",
        ):
            if evaluation.get(field) != expected.get(field):
                errors.append(
                    f"policy_evaluations[{index}].{field}: must match trusted policy "
                    f"evaluation {expected.get(field)!r}"
                )
    return errors


def policy_evaluations_have_blocking_decision(payload: dict[str, Any]) -> bool:
    """Return true when payload policy evaluations contain a blocking decision."""

    evaluations = payload.get("policy_evaluations")
    if not isinstance(evaluations, list):
        return False
    for evaluation in evaluations:
        if isinstance(evaluation, dict) and _text(evaluation.get("decision")) in BLOCKING_DECISIONS:
            return True
    return False


def _evaluate_policy(
    policy: dict[str, Any],
    facts: dict[str, Any],
    *,
    agent_id: str,
    ecosystem: str,
) -> dict[str, Any]:
    effect = _text(policy.get("effect"))
    base = {
        "policy_id": _text(policy.get("id")),
        "effect": effect,
        "decision": "not_applicable",
        "message": _text(policy.get("message")),
        "facts_used": [],
        "missing_facts": [],
        "invalid_facts": [],
    }
    scope = _applies_to(policy.get("applies_to"), agent_id=agent_id, ecosystem=ecosystem)
    if scope.matched is False:
        return base
    if scope.matched is None:
        return _evaluation_record(base, _missing_decision(policy), scope)

    when = _eval_condition(policy["when"], facts) if "when" in policy else _always()
    if when.matched is False:
        return _evaluation_record(base, "not_applicable", when)
    if when.matched is None:
        return _evaluation_record(base, _missing_decision(policy), when)

    condition = policy.get(f"{effect}_if")
    result = _eval_condition(condition, facts) if condition is not None else _always()
    combined = ConditionResult(
        result.matched,
        frozenset(when.facts_used | result.facts_used),
        frozenset(when.missing_facts | result.missing_facts),
        frozenset(when.invalid_facts | result.invalid_facts),
    )
    if result.matched is None:
        return _evaluation_record(base, _missing_decision(policy), combined)
    if not result.matched:
        return _evaluation_record(base, "passed", combined)
    return _evaluation_record(base, _decision_for_effect(effect), combined)


def _evaluation_record(
    base: dict[str, Any],
    decision: str,
    result: ConditionResult,
) -> dict[str, Any]:
    record = dict(base)
    record["decision"] = decision
    record["facts_used"] = sorted(result.facts_used)
    record["missing_facts"] = sorted(result.missing_facts)
    record["invalid_facts"] = sorted(result.invalid_facts)
    return record


def _decision_for_effect(effect: str) -> str:
    if effect == "deny":
        return "blocked"
    if effect == "require_review":
        return "requires_review"
    if effect == "warn":
        return "warned"
    return "passed"


def _missing_decision(policy: dict[str, Any]) -> str:
    missing_policy = _text(policy.get("on_missing_facts") or "deny")
    effect = _text(policy.get("effect"))
    if missing_policy == "allow":
        return "passed"
    if missing_policy == "warn":
        return "warned"
    if missing_policy == "unavailable":
        return "unavailable"
    if effect == "require_review":
        return "requires_review"
    return "blocked"


def _eval_condition(condition: Any, facts: dict[str, Any]) -> ConditionResult:
    if not isinstance(condition, dict):
        return ConditionResult(None, frozenset(), frozenset())
    if "all" in condition:
        return _eval_all(condition.get("all"), facts)
    if "any" in condition:
        return _eval_any(condition.get("any"), facts)
    if "not" in condition:
        inner = _eval_condition(condition.get("not"), facts)
        if inner.matched is None:
            return inner
        return ConditionResult(
            not inner.matched,
            inner.facts_used,
            inner.missing_facts,
            inner.invalid_facts,
        )
    fact_path = _text(condition.get("fact"))
    if not fact_path:
        return ConditionResult(None, frozenset(), frozenset())
    present, actual = _resolve_fact(facts, fact_path)
    facts_used = frozenset({fact_path})
    if "exists" in condition:
        expected = bool(condition.get("exists"))
        return ConditionResult(present is expected, facts_used, frozenset())
    if not present:
        return ConditionResult(None, facts_used, frozenset({fact_path}))
    operator = next((op for op in CONDITION_OPERATORS if op in condition and op != "exists"), "")
    if not operator:
        return ConditionResult(None, facts_used, frozenset())
    expected = condition[operator]
    matched = _compare(operator, actual, expected)
    return ConditionResult(
        matched,
        facts_used,
        frozenset(),
        frozenset({fact_path}) if matched is None else frozenset(),
    )


def _always() -> ConditionResult:
    return ConditionResult(True, frozenset(), frozenset())


def _eval_all(conditions: Any, facts: dict[str, Any]) -> ConditionResult:
    if not isinstance(conditions, list):
        return ConditionResult(None, frozenset(), frozenset())
    facts_used: set[str] = set()
    missing: set[str] = set()
    invalid: set[str] = set()
    unknown = False
    for condition in conditions:
        result = _eval_condition(condition, facts)
        facts_used.update(result.facts_used)
        missing.update(result.missing_facts)
        invalid.update(result.invalid_facts)
        if result.matched is False:
            return ConditionResult(
                False,
                frozenset(facts_used),
                frozenset(missing),
                frozenset(invalid),
            )
        if result.matched is None:
            unknown = True
    return ConditionResult(
        None if unknown else True,
        frozenset(facts_used),
        frozenset(missing),
        frozenset(invalid),
    )


def _eval_any(conditions: Any, facts: dict[str, Any]) -> ConditionResult:
    if not isinstance(conditions, list):
        return ConditionResult(None, frozenset(), frozenset())
    facts_used: set[str] = set()
    missing: set[str] = set()
    invalid: set[str] = set()
    unknown = False
    for condition in conditions:
        result = _eval_condition(condition, facts)
        facts_used.update(result.facts_used)
        missing.update(result.missing_facts)
        invalid.update(result.invalid_facts)
        if result.matched is True:
            return ConditionResult(
                True,
                frozenset(facts_used),
                frozenset(missing),
                frozenset(invalid),
            )
        if result.matched is None:
            unknown = True
    return ConditionResult(
        None if unknown else False,
        frozenset(facts_used),
        frozenset(missing),
        frozenset(invalid),
    )


def _compare(operator: str, actual: Any, expected: Any) -> bool | None:
    if operator == "equals":
        if not _equality_types_compatible(actual, expected):
            return None
        return actual == expected
    if operator == "not_equals":
        if not _equality_types_compatible(actual, expected):
            return None
        return actual != expected
    if operator == "in":
        if not isinstance(expected, list):
            return None
        compatible = [item for item in expected if _equality_types_compatible(actual, item)]
        if expected and not compatible:
            return None
        return any(actual == item for item in compatible)
    if operator == "contains":
        if isinstance(actual, list):
            compatible = [item for item in actual if _equality_types_compatible(item, expected)]
            if actual and not compatible:
                return None
            return any(item == expected for item in compatible)
        if isinstance(actual, str):
            return expected in actual if isinstance(expected, str) else None
        if isinstance(actual, dict):
            compatible = [key for key in actual if _equality_types_compatible(key, expected)]
            if actual and not compatible:
                return None
            return any(key == expected for key in compatible)
        return None
    if operator in {"gt", "gte", "lt", "lte"}:
        if not (_is_number(actual) and _is_number(expected)):
            return None
        if operator == "gt":
            return actual > expected
        if operator == "gte":
            return actual >= expected
        if operator == "lt":
            return actual < expected
        return actual <= expected
    if operator in {"version_gt", "version_gte", "version_lt", "version_lte"}:
        left = _version_parts(actual)
        right = _version_parts(expected)
        if left is None or right is None:
            return None
        if operator == "version_gt":
            return left > right
        if operator == "version_gte":
            return left >= right
        if operator == "version_lt":
            return left < right
        return left <= right
    return False


def _equality_types_compatible(actual: Any, expected: Any) -> bool:
    """Return whether exact equality has meaningful operand types."""

    if not (_is_scalar(actual) and _is_scalar(expected)):
        return False
    if isinstance(actual, bool) or isinstance(expected, bool):
        return type(actual) is type(expected)
    if _is_number(actual) and _is_number(expected):
        return True
    return type(actual) is type(expected)


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, str | int | float | bool)


def _version_parts(value: Any) -> tuple[int, ...] | None:
    if not isinstance(value, str) or not _is_dotted_number(value):
        return None
    parts = [int(part) for part in value.split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def _is_dotted_number(value: str) -> bool:
    parts = value.split(".")
    return len(parts) > 1 and all(part.isdigit() for part in parts)


def _resolve_fact(facts: dict[str, Any], fact_path: str) -> tuple[bool, Any]:
    current: Any = facts
    for part in fact_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _fact_text(facts: dict[str, Any], fact_path: str) -> str:
    present, value = _resolve_fact(facts, fact_path)
    return str(value) if present and value is not None else ""


def _applies_to(value: Any, *, agent_id: str, ecosystem: str) -> ConditionResult:
    if not isinstance(value, dict):
        return _always()
    facts_used: set[str] = set()
    missing: set[str] = set()
    agents = value.get("agents")
    if isinstance(agents, list) and agents:
        facts_used.add("agent.id")
        if not agent_id:
            missing.add("agent.id")
        elif agent_id not in agents:
            return ConditionResult(False, frozenset(facts_used), frozenset(missing))
    ecosystems = value.get("ecosystems")
    if isinstance(ecosystems, list) and ecosystems:
        facts_used.add("ecosystem")
        if not ecosystem:
            missing.add("ecosystem")
        elif ecosystem not in ecosystems:
            return ConditionResult(False, frozenset(facts_used), frozenset(missing))
    return ConditionResult(
        None if missing else True,
        frozenset(facts_used),
        frozenset(missing),
    )


def _validate_applies_to(value: Any, prefix: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{prefix}.applies_to: must be a mapping"]
    errors = _unsupported_field_errors(value, APPLIES_TO_FIELDS, f"{prefix}.applies_to")
    for field in ("agents", "ecosystems"):
        if field in value and not _is_string_list(value[field]):
            errors.append(
                f"{prefix}.applies_to.{field}: "
                "must be a non-empty list of non-blank strings"
            )
    return errors


def _validate_condition(condition: Any, prefix: str) -> list[str]:
    if not isinstance(condition, dict):
        return [f"{prefix}: must be a mapping"]
    compound = [field for field in ("all", "any", "not") if field in condition]
    if compound:
        if len(compound) > 1 or "fact" in condition:
            return [f"{prefix}: must contain only one compound operator"]
        field = compound[0]
        unsupported = _unsupported_field_errors(condition, frozenset({field}), prefix)
        if unsupported:
            return unsupported
        if field in {"all", "any"}:
            value = condition[field]
            if not isinstance(value, list) or not value:
                return [f"{prefix}.{field}: must be a non-empty list"]
            errors: list[str] = []
            for index, item in enumerate(value):
                errors.extend(_validate_condition(item, f"{prefix}.{field}[{index}]"))
            return errors
        return _validate_condition(condition[field], f"{prefix}.not")

    if not _text(condition.get("fact")):
        return [f"{prefix}.fact: must be a non-empty string"]
    operators = [field for field in CONDITION_OPERATORS if field in condition]
    if len(operators) != 1:
        return [f"{prefix}: must contain exactly one supported operator"]
    unknown = set(condition) - {"fact"} - CONDITION_OPERATORS
    if unknown:
        return [f"{prefix}: unsupported fields {sorted(unknown)}"]
    if operators[0] == "exists" and not isinstance(condition["exists"], bool):
        return [f"{prefix}.exists: must be boolean"]
    if operators[0] == "in" and not isinstance(condition["in"], list):
        return [f"{prefix}.in: must be a list"]
    if operators[0] in {"equals", "not_equals"} and not _is_scalar(
        condition[operators[0]]
    ):
        return [f"{prefix}.{operators[0]}: must be a scalar value"]
    if operators[0] in {"gt", "gte", "lt", "lte"} and not _is_number(
        condition[operators[0]]
    ):
        return [f"{prefix}.{operators[0]}: must be a number"]
    if operators[0] == "contains" and not _is_scalar(condition["contains"]):
        return [f"{prefix}.contains: must be a scalar value"]
    if operators[0] == "in" and isinstance(condition["in"], list) and not all(
        _is_scalar(item) for item in condition["in"]
    ):
        return [f"{prefix}.in: must contain only scalar values"]
    if operators[0].startswith("version_") and (
        not isinstance(condition[operators[0]], str)
        or not _is_dotted_number(condition[operators[0]])
    ):
        return [f"{prefix}.{operators[0]}: must be a numeric dotted version"]
    return []


def _is_string_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(bool(_text(item)) for item in value)
    )


def _unsupported_field_errors(
    value: dict[Any, Any],
    allowed: frozenset[str],
    prefix: str,
) -> list[str]:
    unsupported = sorted((field for field in value if field not in allowed), key=str)
    return [f"{prefix}: unsupported fields {unsupported}"] if unsupported else []


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def evaluations_to_json(evaluations: list[dict[str, Any]]) -> str:
    """Render policy evaluations as stable JSON for CLI output."""

    return json.dumps({"policy_evaluations": evaluations}, indent=2, sort_keys=True) + "\n"
