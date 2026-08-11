from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from agent.turns.outbound import (
    OutboundDispatch,
    PersistentOutboxReconciler,
    PersistentOutboundPort,
)
from session.manager import SessionManager


class _Delegate:
    def __init__(self, *, result: bool = True, error: Exception | None = None) -> None:
        self.calls: list[OutboundDispatch] = []
        self._result = result
        self._error = error

    async def dispatch(self, outbound: OutboundDispatch) -> bool:
        self.calls.append(outbound)
        if self._error is not None:
            raise self._error
        return self._result


@pytest.mark.asyncio
async def test_persistent_outbound_port_marks_sent_after_delegate_accepts(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.get_or_create("telegram:123")
    await manager.append_messages(session, [{"role": "assistant", "content": "hello"}])

    delegate = _Delegate()
    port = PersistentOutboundPort(manager, delegate)

    sent = await port.dispatch(
        OutboundDispatch(channel="telegram", chat_id="123", content="hello")
    )

    assert sent is True
    assert delegate.calls[0].content == "hello"
    with sqlite3.connect(manager.db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM outbox").fetchone()
    assert row is not None
    assert row["status"] == "sent"
    assert row["message_id"] == session.messages[-1]["id"]
    assert row["remote_message_id"] == session.messages[-1]["id"]


@pytest.mark.asyncio
async def test_persistent_outbound_port_marks_unknown_when_delegate_raises(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.get_or_create("telegram:123")
    await manager.append_messages(session, [{"role": "assistant", "content": "hello"}])

    delegate = _Delegate(error=RuntimeError("send failed"))
    port = PersistentOutboundPort(manager, delegate)

    sent = await port.dispatch(
        OutboundDispatch(channel="telegram", chat_id="123", content="hello")
    )

    assert sent is False
    with sqlite3.connect(manager.db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM outbox").fetchone()
    assert row is not None
    assert row["status"] == "unknown"
    assert "send failed" in str(row["last_error"])


@pytest.mark.asyncio
async def test_persistent_outbox_reconciler_flushes_pending_rows(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.get_or_create("telegram:123")
    session.add_message("assistant", "hello")
    await manager.save_async(session)
    store = manager._store
    store.enqueue_outbox(
        session_key="telegram:123",
        message_id=session.messages[-1]["id"],
        channel="telegram",
        chat_id="123",
    )

    delegate = _Delegate()
    reconciler = PersistentOutboxReconciler(manager, delegate)

    flushed = await reconciler.flush_pending(worker_id="worker-1")

    assert flushed == 1
    assert delegate.calls[0].content == "hello"
    rows = store.list_outbox(session_key="telegram:123")
    assert rows[0]["status"] == "sent"


@pytest.mark.asyncio
async def test_persistent_outbox_reconciler_resolves_unknown_rows(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.get_or_create("telegram:123")
    session.add_message("assistant", "hello")
    await manager.save_async(session)
    store = manager._store
    created = store.enqueue_outbox(
        session_key="telegram:123",
        message_id=session.messages[-1]["id"],
        channel="telegram",
        chat_id="123",
    )
    store.mark_outbox_unknown(
        created["outbox_id"],
        remote_message_id=session.messages[-1]["id"],
        error="ack lost",
    )

    delegate = _Delegate()
    reconciler = PersistentOutboxReconciler(manager, delegate)

    changed = await reconciler.reconcile_unknown(lambda _row: True)

    assert changed == 1
    rows = store.list_outbox(session_key="telegram:123", status="sent")
    assert rows[0]["status"] == "sent"
