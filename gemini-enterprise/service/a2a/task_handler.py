"""Orchestrate one A2A task: parse -> query Endor -> shape the result.

This layer is transport-agnostic. It takes the A2A ``message`` params object,
runs the read-only SCA analysis, and returns an A2A ``Task`` result dict. The
JSON-RPC transport (``app.py``) turns :class:`AgentError`s into JSON-RPC error
responses.
"""

from __future__ import annotations

import uuid
from typing import Any, Mapping

from ..endor_client.base import EndorSCAClient
from .context import CallerContext
from .errors import InvalidParamsError, TaskNotFoundError
from .models import AnalysisStatus, ScaAnalysisResult
from .request_parser import parse_task_message
from .result_formatter import build_analysis_result, human_summary
from .task_store import TaskStore

# A2A task states we emit. ``needs_more_info`` maps to input-required; a
# ``data_gap`` still completes with partial results (§10).
_STATE_BY_STATUS = {
    AnalysisStatus.COMPLETED: "completed",
    AnalysisStatus.DATA_GAP: "completed",
    AnalysisStatus.NEEDS_MORE_INFO: "input-required",
}


def _new_id() -> str:
    return uuid.uuid4().hex


def _task_result(
    analysis: ScaAnalysisResult,
    *,
    context_id: str,
    task_id: str,
) -> dict[str, Any]:
    """Build a minimal A2A Task object carrying the structured analysis."""

    return {
        "kind": "task",
        "id": task_id,
        "contextId": context_id,
        "status": {"state": _STATE_BY_STATUS[analysis.status]},
        "artifacts": [
            {
                "artifactId": "sca-remediation-analysis",
                "name": "SCA Remediation Analysis",
                "parts": [
                    {"kind": "data", "data": analysis.model_dump(mode="json")},
                    {"kind": "text", "text": human_summary(analysis)},
                ],
            }
        ],
    }


def handle_message_send(
    params: Mapping[str, Any],
    *,
    client: EndorSCAClient,
    caller_context: CallerContext | None = None,
    task_store: TaskStore | None = None,
) -> dict[str, Any]:
    """Handle an A2A ``message/send`` request and return a Task result dict.

    ``caller_context`` carries the resolved tenant (namespace/identity) for the
    request; the effective namespace is the request's explicit override, else
    the caller's tenant. Raises :class:`~service.a2a.errors.AgentError`
    subclasses for auth, authorization, ambiguous-target, and invalid-params
    conditions so the transport can emit clean JSON-RPC errors.
    """

    caller_context = caller_context or CallerContext()

    if not isinstance(params, Mapping):
        raise InvalidParamsError("`params` must be an object")

    message = params.get("message")
    if not isinstance(message, Mapping):
        raise InvalidParamsError("`params.message` is required")

    context_id = message.get("contextId")
    context_id = context_id if isinstance(context_id, str) and context_id else _new_id()
    task_id = _new_id()

    request = parse_task_message(message)
    # Effective namespace: an explicit request namespace (a sub-scope the caller
    # asked for) wins; otherwise fall back to the caller's authenticated tenant.
    if not request.namespace and caller_context.namespace:
        request = request.model_copy(update={"namespace": caller_context.namespace})

    endor_result = client.get_sca_analysis(request)
    analysis = build_analysis_result(endor_result)

    task = _task_result(analysis, context_id=context_id, task_id=task_id)
    if task_store is not None:
        task_store.put(task)
    return task


def handle_tasks_get(
    params: Mapping[str, Any],
    *,
    task_store: TaskStore,
) -> dict[str, Any]:
    """Handle an A2A ``tasks/get`` request.

    The service completes tasks synchronously, so ``message/send`` already
    returns the full task. This supports clients that still poll by id; an
    unknown id maps to a proper A2A ``TaskNotFound`` error.
    """

    if not isinstance(params, Mapping):
        raise InvalidParamsError("`params` must be an object")
    task_id = params.get("id")
    if not isinstance(task_id, str) or not task_id:
        raise InvalidParamsError("`params.id` is required")

    task = task_store.get(task_id)
    if task is None:
        raise TaskNotFoundError(f"Task {task_id!r} not found.")
    return task
