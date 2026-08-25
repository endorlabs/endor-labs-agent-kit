"""A tiny bounded in-memory task store for ``tasks/get`` lookups.

The service completes tasks synchronously and returns the full ``Task`` in the
``message/send`` response, so polling is not required. This store lets a client
that *does* poll (`tasks/get`) retrieve a recently completed task.

Caveat: it is per-process. On Cloud Run with more than one instance a poll may
land on an instance that never saw the task. That is acceptable for the
synchronous v1 model; a shared store (e.g. Firestore) would be needed only if we
move to long-running async tasks.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any


class TaskStore:
    def __init__(self, capacity: int = 256) -> None:
        self._capacity = capacity
        self._tasks: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    def put(self, task: dict[str, Any]) -> None:
        task_id = task.get("id")
        if not task_id:
            return
        self._tasks[task_id] = task
        self._tasks.move_to_end(task_id)
        while len(self._tasks) > self._capacity:
            self._tasks.popitem(last=False)

    def get(self, task_id: str) -> dict[str, Any] | None:
        return self._tasks.get(task_id)
