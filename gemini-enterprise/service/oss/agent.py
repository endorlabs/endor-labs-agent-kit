"""A2A message handling for the Option-A OSS agent (P2).

Reuses the A2A Task shape from the SCA path but is self-contained: it takes an
A2A ``message``, runs the question through a :class:`QuestionRouter`, and returns
an A2A ``Task`` carrying the answer. No customer tenant, no per-user identity.
"""

from __future__ import annotations

import uuid
from typing import Any, Mapping, Sequence

from ..a2a.errors import InvalidParamsError, TaskNotFoundError
from ..a2a.task_store import TaskStore
from .router import QuestionRouter


def _new_id() -> str:
    return uuid.uuid4().hex


def _message_text(message: Mapping[str, Any]) -> str:
    parts = message.get("parts")
    if not isinstance(parts, Sequence):
        return ""
    chunks: list[str] = []
    for part in parts:
        if isinstance(part, Mapping) and (part.get("kind") or part.get("type")) == "text":
            if isinstance(part.get("text"), str):
                chunks.append(part["text"])
    return "\n".join(chunks).strip()


def _task_result(answer, *, context_id: str, task_id: str) -> dict[str, Any]:
    return {
        "kind": "task",
        "id": task_id,
        "contextId": context_id,
        "status": {"state": "completed"},
        "artifacts": [
            {
                "artifactId": "oss-intelligence-answer",
                "name": "Open Source Intelligence",
                "parts": [
                    {"kind": "data", "data": answer.model_dump(mode="json")},
                    {"kind": "text", "text": answer.answer},
                ],
            }
        ],
    }


def handle_oss_message(
    params: Mapping[str, Any],
    *,
    router: QuestionRouter,
    task_store: TaskStore | None = None,
) -> dict[str, Any]:
    if not isinstance(params, Mapping):
        raise InvalidParamsError("`params` must be an object")
    message = params.get("message")
    if not isinstance(message, Mapping):
        raise InvalidParamsError("`params.message` is required")

    context_id = message.get("contextId")
    context_id = context_id if isinstance(context_id, str) and context_id else _new_id()
    task_id = _new_id()

    answer = router.answer(_message_text(message))
    task = _task_result(answer, context_id=context_id, task_id=task_id)
    if task_store is not None:
        task_store.put(task)
    return task


def handle_tasks_get(params: Mapping[str, Any], *, task_store: TaskStore) -> dict[str, Any]:
    if not isinstance(params, Mapping):
        raise InvalidParamsError("`params` must be an object")
    task_id = params.get("id")
    if not isinstance(task_id, str) or not task_id:
        raise InvalidParamsError("`params.id` is required")
    task = task_store.get(task_id)
    if task is None:
        raise TaskNotFoundError(f"Task {task_id!r} not found.")
    return task
