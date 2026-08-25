"""The Endor SCA client interface the rest of the service depends on."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..a2a.models import AnalysisRequest, ScaFinding


@dataclass
class EndorSCAResult:
    """Normalized result of an Endor SCA analysis for one resolved target.

    ``namespace`` is the resolved Endor namespace/project the findings belong
    to (echoed back to the caller). ``data_gaps`` records missing or
    unreachable evidence so the task can return partial results instead of
    failing (recipe convention, §10).
    """

    namespace: str
    findings: list[ScaFinding] = field(default_factory=list)
    data_gaps: list[str] = field(default_factory=list)


class EndorSCAClient(ABC):
    """Read-only access to Endor SCA findings and remediation guidance.

    Implementations resolve the request's repo/project reference to an Endor
    project, then return ranked P0/P1 findings with remediation guidance. They
    must never mutate customer source, Endor state, or CI (v1 is read-only).
    """

    @abstractmethod
    def get_sca_analysis(self, request: AnalysisRequest) -> EndorSCAResult:
        """Return SCA findings + remediation guidance for the request target.

        Should raise :class:`~service.a2a.errors.AuthenticationError` on auth
        failure and
        :class:`~service.a2a.errors.NamespaceNotAuthorizedError` when the
        caller is not entitled to the requested namespace, rather than
        returning empty results.
        """
        raise NotImplementedError
