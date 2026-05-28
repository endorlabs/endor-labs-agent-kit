"""Adversarial eval schema for agent prompt-injection resistance cases.

Agent Kit compiles agents; it does not execute them, so injection resistance is
expressed as declarative eval cases under ``source/agents/<agent>/evals``. This
module gives those adversarial cases a mechanical schema so authoring checks can
enforce them instead of relying on the untrusted-content prose alone.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

ADVERSARIAL_INJECTION_VECTORS = (
    "repository_file",
    "source_comment",
    "dependency_metadata",
    "endor_evidence",
    "adapter_output",
    "fake_evidence",
)


def is_adversarial_case(case: Mapping[str, Any]) -> bool:
    """Return whether an eval case opts in to adversarial schema checks."""

    return bool(case.get("adversarial"))


def adversarial_eval_errors(cases: Iterable[Any]) -> list[str]:
    """Return schema errors for adversarial injection-resistance eval cases.

    Only cases marked ``adversarial: true`` are checked, so agents without
    adversarial coverage are unaffected. Each adversarial case must name a known
    injection vector, carry the untrusted payload it models, and declare the
    resistance outcome the agent must hold to.
    """

    errors: list[str] = []
    for index, case in enumerate(cases):
        if not isinstance(case, Mapping) or not is_adversarial_case(case):
            continue
        label = case.get("id", index)
        prefix = f"adversarial case {label!r}"

        if case.get("injection_vector") not in ADVERSARIAL_INJECTION_VECTORS:
            errors.append(
                f"{prefix}: injection_vector must be one of "
                f"{list(ADVERSARIAL_INJECTION_VECTORS)}"
            )
        if not str(case.get("untrusted_payload") or "").strip():
            errors.append(f"{prefix}: untrusted_payload must be a non-empty string")

        expected = case.get("expected")
        if not isinstance(expected, Mapping):
            errors.append(f"{prefix}: expected must be a mapping")
            continue
        if expected.get("resists_injection") is not True:
            errors.append(f"{prefix}: expected.resists_injection must be true")
        must_not = expected.get("must_not")
        if not isinstance(must_not, list) or not must_not:
            errors.append(f"{prefix}: expected.must_not must be a non-empty list")

    return errors


def declared_adversarial_vectors(cases: Iterable[Any]) -> set[str]:
    """Return the injection vectors covered by valid adversarial cases."""

    vectors: set[str] = set()
    for case in cases:
        if not isinstance(case, Mapping) or not is_adversarial_case(case):
            continue
        vector = case.get("injection_vector")
        if vector in ADVERSARIAL_INJECTION_VECTORS:
            vectors.add(str(vector))
    return vectors


def missing_adversarial_vectors(
    cases: Iterable[Any],
    required: Iterable[str] = ADVERSARIAL_INJECTION_VECTORS,
) -> set[str]:
    """Return required injection vectors not yet covered by adversarial cases."""

    cases = list(cases)
    return set(required) - declared_adversarial_vectors(cases)
