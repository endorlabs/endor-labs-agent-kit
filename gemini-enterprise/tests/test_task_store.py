"""Unit tests for the bounded in-memory task store."""

from __future__ import annotations

from service.a2a.task_store import TaskStore


def _task(task_id: str) -> dict:
    return {"kind": "task", "id": task_id}


def test_get_returns_stored_task():
    store = TaskStore()
    store.put(_task("t1"))
    assert store.get("t1") == _task("t1")


def test_get_miss_returns_none():
    assert TaskStore().get("missing") is None


def test_put_without_id_is_a_noop():
    store = TaskStore()
    store.put({"kind": "task"})
    assert store.get("") is None


def test_capacity_evicts_oldest():
    store = TaskStore(capacity=2)
    store.put(_task("t1"))
    store.put(_task("t2"))
    store.put(_task("t3"))

    assert store.get("t1") is None
    assert store.get("t2") is not None
    assert store.get("t3") is not None


def test_re_put_refreshes_recency():
    store = TaskStore(capacity=2)
    store.put(_task("t1"))
    store.put(_task("t2"))
    store.put(_task("t1"))  # t1 becomes most recent; t2 is now oldest
    store.put(_task("t3"))

    assert store.get("t1") is not None
    assert store.get("t2") is None
    assert store.get("t3") is not None
