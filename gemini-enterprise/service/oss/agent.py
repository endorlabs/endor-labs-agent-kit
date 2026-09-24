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
from .factory import build_oss_client
from .router import OssAnswer, QuestionRouter
from .ui import A2UI_SELECT_EVENT
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


def _select_context(data: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """If ``data`` (a DataPart body) is the A2UI select_upgrade event, return its
    context. GE delivers it under an ``action`` key (``{"action": {"name",
    "context", ...}}``); also accept ``event`` or a top-level event for safety."""

    for node in (data.get("action"), data.get("event"), data):
        if isinstance(node, Mapping) and node.get("name") == A2UI_SELECT_EVENT:
            ctx = node.get("context")
            return ctx if isinstance(ctx, Mapping) else {}
    return None


def _extract_select_upgrade(message: Mapping[str, Any]) -> tuple[str, str] | None:
    """Detect a clicked upgrade button: the A2UI ``select_upgrade`` event with a
    ``version`` + ``purl`` context (values resolved to literals by the client)."""

    for part in message.get("parts") or []:
        if not isinstance(part, Mapping):
            continue
        data = part.get("data")
        candidates = [data] if isinstance(data, Mapping) else []
        # Some clients deliver the event JSON as text rather than a data part.
        if isinstance(part.get("text"), str) and A2UI_SELECT_EVENT in part["text"]:
            try:
                candidates.append(json.loads(part["text"]))
            except Exception:  # noqa: BLE001
                pass
        for cand in candidates:
            if not isinstance(cand, Mapping):
                continue
            ctx = _select_context(cand)
            if ctx is not None:
                version, purl = ctx.get("version"), ctx.get("purl")
                if isinstance(version, str) and isinstance(purl, str):
                    return version, purl
    return None


def _select_upgrade_answer(version: str, purl: str) -> OssAnswer:
    """Confirm a chosen upgrade with what it fixes and how to apply it (text only,
    so it does not re-render the choice cards)."""

    name = purl.split("://", 1)[-1].split("@", 1)[0]
    fixes: list[str] = []
    try:
        recs = build_oss_client().recommend_upgrades(purl)
        opt = next((o for o in recs.options if o.version == version), None)
        if opt:
            fixes = list(opt.fixes)
    except Exception:  # noqa: BLE001 - the confirmation still works without the detail
        pass
    resolves = f"resolves {', '.join(fixes)}" if fixes else "is the recommended fix"
    return OssAnswer(
        answer=(
            f"Upgrading {name} to {version} {resolves}. Update the dependency to "
            f"version {version} in your build file, then rebuild and re-scan to confirm."
        ),
        tools_used=["recommend_upgrades"],
    )


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

    # A clicked upgrade button comes back as the A2UI select_upgrade event; answer
    # with a confirmation instead of routing it as a new question.
    selection = _extract_select_upgrade(message)
    if selection is not None:
        answer = _select_upgrade_answer(*selection)
    else:
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
