from __future__ import annotations

import asyncio
import threading
from inspect import signature
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from anyio import create_task_group, sleep

from django_fastapi import aclose_db_connections, database_sync_to_async, django_db
from django_fastapi import database as db


@pytest.mark.parametrize("obsolete_only", [False, True])
def test_cleanup_respects_transactions_and_connection_lifetime(
    monkeypatch, obsolete_only
):
    connections = [
        SimpleNamespace(
            in_atomic_block=atomic,
            settings_dict={"CONN_MAX_AGE": age},
            close=Mock(),
            close_if_unusable_or_obsolete=Mock(),
        )
        for atomic, age in [(True, 0), (False, 0), (False, 60), (False, None)]
    ]
    all_connections = Mock(return_value=connections)
    monkeypatch.setattr(db.connections, "all", all_connections)
    db.close_db_connections(obsolete_only=obsolete_only)
    all_connections.assert_called_once_with(initialized_only=True)
    for index, connection in enumerate(connections):
        assert connection.close.call_count == int(index == 1 and not obsolete_only)
        assert connection.close_if_unusable_or_obsolete.call_count == int(
            index > 0 and (obsolete_only or index > 1)
        )


@pytest.mark.parametrize("failure", [False, True])
@pytest.mark.parametrize("use_async", [False, True])
def test_db_unit_cleans_up_in_its_own_thread(monkeypatch, failure, use_async):
    calls = []

    def cleanup(*, obsolete_only=False):
        calls.append((threading.get_ident(), obsolete_only))

    monkeypatch.setattr(db, "close_db_connections", cleanup)

    def operation(value: int) -> int:
        calls.append((threading.get_ident(), "operation"))
        if failure:
            raise RuntimeError("operation failed")
        return value

    wrapped = django_db(operation)
    assert signature(wrapped) == signature(operation, eval_str=True)
    assert wrapped.__django_db__

    def execute():
        if use_async:
            return asyncio.run(database_sync_to_async(operation)(7))
        return wrapped(7)

    if failure:
        with pytest.raises(RuntimeError, match="operation failed"):
            execute()
    else:
        assert execute() == 7
    assert len({thread for thread, _ in calls}) == 1
    assert [step for _, step in calls] == [True, "operation", False]


def test_cleanup_finishes_inside_cancelled_anyio_scope(monkeypatch):
    closed = threading.Event()
    monkeypatch.setattr(db, "close_db_connections", closed.set)

    async def run():
        async with create_task_group() as group:
            group.cancel_scope.cancel()
            await aclose_db_connections()
            assert closed.is_set()

    asyncio.run(run())


def test_cleanup_waits_for_thread_after_task_cancellation(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    closed = threading.Event()

    def cleanup():
        started.set()
        assert release.wait(5)
        closed.set()

    monkeypatch.setattr(db, "close_db_connections", cleanup)

    async def run():
        task = asyncio.create_task(aclose_db_connections())
        while not started.is_set():
            await sleep(0.001)
        task.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert closed.is_set()

    try:
        asyncio.run(run())
    finally:
        release.set()
