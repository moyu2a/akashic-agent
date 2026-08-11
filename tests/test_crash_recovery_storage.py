from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from session.store import SessionStore
from agent.recovery.sqlite_uow import AttachedSQLiteUnitOfWork


NOW = datetime(2030, 1, 1, tzinfo=UTC)


def _seed_message(store: SessionStore) -> dict:
    store.upsert_session(
        "cli:s1",
        created_at=NOW.isoformat(),
        updated_at=NOW.isoformat(),
        last_consolidated=0,
        metadata={},
    )
    return store.insert_message(
        "cli:s1",
        role="assistant",
        content="final answer",
        ts=NOW.isoformat(),
        seq=0,
    )


def test_outbox_stores_message_reference_and_claims_once(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    message = _seed_message(store)

    created = store.enqueue_outbox(
        session_key="cli:s1",
        message_id=message["id"],
        channel="cli",
        chat_id="direct",
        now=NOW,
    )

    with sqlite3.connect(store.db_path) as conn:
        conn.row_factory = sqlite3.Row
        columns = {row[1] for row in conn.execute("PRAGMA table_info(outbox)")}
        row = conn.execute(
            "SELECT * FROM outbox WHERE outbox_id = ?",
            (created["outbox_id"],),
        ).fetchone()

    assert "content" not in columns
    assert row is not None
    assert row["message_id"] == message["id"]

    first = store.claim_next_outbox(
        worker_id="worker-1",
        now=NOW,
        lease_seconds=30,
    )
    second = store.claim_next_outbox(
        worker_id="worker-2",
        now=NOW,
        lease_seconds=30,
    )

    assert first is not None
    assert first["outbox_id"] == created["outbox_id"]
    assert first["message"]["content"] == "final answer"
    assert second is None


def test_unknown_outbox_is_reconciled_to_sent_or_requeued(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    message = _seed_message(store)
    created = store.enqueue_outbox(
        session_key="cli:s1",
        message_id=message["id"],
        channel="cli",
        chat_id="direct",
        now=NOW,
    )

    store.mark_outbox_unknown(
        created["outbox_id"],
        remote_message_id="remote-1",
        error="ack lost",
        now=NOW,
    )
    store.reconcile_unknown_outbox(
        created["outbox_id"],
        delivered=True,
        now=NOW + timedelta(seconds=1),
    )

    sent = store.get_outbox(created["outbox_id"])
    assert sent is not None
    assert sent["status"] == "sent"
    assert sent["remote_message_id"] == "remote-1"


def test_generation_abort_preserves_partial_content(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    message = _seed_message(store)
    generation = store.create_message_generation(
        session_key="cli:s1",
        message_id=message["id"],
        generation_id="gen-1",
        now=NOW,
    )
    assert generation["status"] == "streaming"

    store.update_message_generation_progress(
        "gen-1",
        partial_content="已经输出的半截内容",
        last_streamed_offset=9,
        now=NOW + timedelta(seconds=1),
    )
    aborted = store.abort_stale_message_generations(
        now=NOW + timedelta(seconds=2),
        suffix="（内容因网络波动截断，请重新触发）",
    )

    assert [item["generation_id"] for item in aborted] == ["gen-1"]
    generation_after = store.get_message_generation("gen-1")
    message_after = store.get_message(message["id"])
    assert generation_after is not None
    assert generation_after["status"] == "aborted"
    assert message_after is not None
    assert message_after["content"] == "已经输出的半截内容\n\n（内容因网络波动截断，请重新触发）"


def test_attached_transaction_interrupt_rolls_back_and_preserves_recovery_ref(
    tmp_path: Path,
) -> None:
    session_db = tmp_path / "sessions.db"
    task_db = tmp_path / "task_plans.db"

    with sqlite3.connect(task_db) as conn:
        conn.execute("CREATE TABLE task_events (id TEXT PRIMARY KEY, metadata_json TEXT)")
        conn.execute(
            "INSERT INTO task_events (id, metadata_json) VALUES (?, ?)",
            ("started", '{"recovery_ref":"remote-call-1"}'),
        )
        conn.commit()
    with sqlite3.connect(session_db) as conn:
        conn.execute("CREATE TABLE outbox_probe (id TEXT PRIMARY KEY)")
        conn.commit()

    uow = AttachedSQLiteUnitOfWork(
        sessions_db_path=session_db,
        task_plans_db_path=task_db,
        busy_timeout_ms=3000,
    )

    try:
        with uow.transaction() as conn:
            conn.execute(
                "INSERT INTO task_plans.task_events (id, metadata_json) VALUES (?, ?)",
                ("finished", '{"result":"ok"}'),
            )
            conn.execute(
                "INSERT INTO sessions.outbox_probe (id) VALUES (?)",
                ("outbox-1",),
            )
            conn.interrupt()
            conn.execute("SELECT 1")
    except sqlite3.OperationalError:
        pass

    with sqlite3.connect(task_db) as conn:
        rows = conn.execute(
            "SELECT id, metadata_json FROM task_events ORDER BY id"
        ).fetchall()
    with sqlite3.connect(session_db) as conn:
        outbox_rows = conn.execute("SELECT id FROM outbox_probe").fetchall()

    assert rows == [("started", '{"recovery_ref":"remote-call-1"}')]
    assert outbox_rows == []
