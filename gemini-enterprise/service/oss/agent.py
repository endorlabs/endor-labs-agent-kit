"""A2A message handling for the Option-A OSS agent (P2).

Reuses the A2A Task shape from the SCA path but is self-contained: it takes an
A2A ``message``, runs the question through a :class:`QuestionRouter`, and returns
an A2A ``Task`` carrying the answer. No customer tenant, no per-user identity.
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from typing import Any, Mapping, Sequence

from ..a2a.errors import InvalidParamsError, TaskNotFoundError
from ..a2a.task_store import TaskStore
from .router import QuestionRouter
from .ui import (
    GE_SUGGESTIONS_MIME,
    build_upgrade_element,
    to_a2a_parts,
    to_a2ui_parts,
    to_ag_ui_events,
    to_ge_suggestions_payload,
    ui_protocol,
)


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
    parts: list[dict[str, Any]] = [
        {"kind": "data", "data": answer.model_dump(mode="json")},
        {"kind": "text", "text": answer.answer},
    ]
    metadata: dict[str, Any] = {}

    # If the answer offers upgrade choices, emit the interactive "pick an
    # upgrade" element in the configured wire protocol (OSS_UI_PROTOCOL): A2A
    # structured parts (default), AG-UI events (task metadata), or both. One
    # canonical element, adapters per protocol — see service/oss/ui.py.
    element = build_upgrade_element(answer.upgrades) if answer.upgrades else None
    if element is not None:
        protocol = ui_protocol()
        if protocol in ("a2a", "both"):
            parts.extend(to_a2a_parts(element))
        if protocol == "a2ui":
            # Gemini Enterprise's GA interactive-UI protocol: emit the A2UI surface
            # as application/json+a2ui DataParts (GE renders the ChoicePicker cards).
            parts.extend(to_a2ui_parts(element))
        if protocol in ("ag_ui", "both"):
            metadata["endor/ag_ui_events"] = to_ag_ui_events(
                element, thread_id=context_id, run_id=task_id
            )
        # Experiment: also emit the choices as Gemini Enterprise native suggestion
        # chips (the one interactive widget GE is confirmed to render). Gated by
        # OSS_GE_SUGGESTIONS; we emit both a mimeType-tagged `file` part and a
        # `data` part so whichever mapping GE uses for A2A -> typed content hits.
        if os.environ.get("OSS_GE_SUGGESTIONS", "").strip().lower() in ("1", "true", "yes"):
            payload = to_ge_suggestions_payload(element)
            parts.append({
                "kind": "file",
                "file": {
                    "mimeType": GE_SUGGESTIONS_MIME,
                    "bytes": base64.b64encode(
                        json.dumps(payload).encode("utf-8")
                    ).decode("ascii"),
                },
            })
            parts.append({
                "kind": "data",
                "data": payload,
                "metadata": {"mimeType": GE_SUGGESTIONS_MIME},
            })

    artifact: dict[str, Any] = {
        "artifactId": "oss-intelligence-answer",
        "name": "Open Source Intelligence",
        "parts": parts,
    }
    if metadata:
        artifact["metadata"] = metadata

    return {
        "kind": "task",
        "id": task_id,
        "contextId": context_id,
        "status": {"state": "completed"},
        "artifacts": [artifact],
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
