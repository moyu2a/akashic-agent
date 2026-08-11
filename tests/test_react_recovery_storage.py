from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from session.store import SessionStore


NOW = datetime(2031, 1, 1, tzinfo=UTC)


def test_react_recovery_schema_stores_references_only(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.db")

    with sqlite3.connect(store.db_path) as conn:
        turn_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(turn_runs)")
        }
        step_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(react_steps)")
        }
        attempt_columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(tool_invocation_attempts)")
        }

    assert {"turn_run_id", "lease_owner", "lease_expires_at", "lease_version"} <= turn_columns
    assert {"step_id", "turn_run_id", "assistant_tool_call_json"} <= step_columns
    assert {"attempt_id", "turn_run_id", "tool_call_id", "result_message_id"} <= attempt_columns
    assert "content" not in turn_columns
    assert "content" not in attempt_columns


def test_turn_run_claim_allows_only_one_worker_and_reclaims_expired_lease(
    tmp_path: Path,
) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    store.create_turn_run(
        turn_run_id="turn-1",
        session_key="cli:s1",
        user_message_id=None,
        now=NOW,
    )

    first = store.claim_turn_run_for_recovery(
        turn_run_id="turn-1",
        worker_id="worker-1",
        lease_expires_at=NOW + timedelta(seconds=30),
        now=NOW,
    )
    second = store.claim_turn_run_for_recovery(
        turn_run_id="turn-1",
        worker_id="worker-2",
        lease_expires_at=NOW + timedelta(seconds=30),
        now=NOW,
    )
    reclaimed = store.claim_turn_run_for_recovery(
        turn_run_id="turn-1",
        worker_id="worker-2",
        lease_expires_at=NOW + timedelta(seconds=90),
        now=NOW + timedelta(seconds=31),
    )

    assert first is True
    assert second is False
    assert reclaimed is True
    turn = store.get_turn_run("turn-1")
    assert turn is not None
    assert turn["lease_owner"] == "worker-2"
    assert turn["lease_version"] == 2


def test_terminal_turn_run_cannot_be_claimed(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    store.create_turn_run(
        turn_run_id="turn-1",
        session_key="cli:s1",
        user_message_id=None,
        now=NOW,
    )
    store.mark_turn_run_completed(turn_run_id="turn-1", now=NOW)

    claimed = store.claim_turn_run_for_recovery(
        turn_run_id="turn-1",
        worker_id="worker-1",
        lease_expires_at=NOW + timedelta(seconds=30),
        now=NOW + timedelta(seconds=31),
    )

    assert claimed is False


def test_tool_claim_requires_matching_turn_lease(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    store.create_turn_run(
        turn_run_id="turn-1",
        session_key="cli:s1",
        user_message_id=None,
        now=NOW,
    )
    step = store.create_react_step(
        step_id="step-1",
        turn_run_id="turn-1",
        step_no=0,
        model_input_json="[]",
        now=NOW,
    )
    attempt = store.persist_react_tool_call(
        turn_run_id="turn-1",
        step_id=step["step_id"],
        tool_call_id="call-1",
        tool_name="read_file",
        arguments_json='{"path":"README.md"}',
        arguments_hash="hash-1",
        recovery_ref="call-1",
        pollable=False,
        idempotent=True,
        side_effect=False,
        now=NOW,
    )

    without_turn_lease = store.claim_tool_invocation(
        attempt_id=attempt["attempt_id"],
        turn_run_id="turn-1",
        worker_id="worker-1",
        lease_expires_at=NOW + timedelta(seconds=30),
        now=NOW,
    )
    store.claim_turn_run_for_recovery(
        turn_run_id="turn-1",
        worker_id="worker-1",
        lease_expires_at=NOW + timedelta(seconds=30),
        now=NOW,
    )
    first = store.claim_tool_invocation(
        attempt_id=attempt["attempt_id"],
        turn_run_id="turn-1",
        worker_id="worker-1",
        lease_expires_at=NOW + timedelta(seconds=30),
        now=NOW,
    )
    second = store.claim_tool_invocation(
        attempt_id=attempt["attempt_id"],
        turn_run_id="turn-1",
        worker_id="worker-2",
        lease_expires_at=NOW + timedelta(seconds=30),
        now=NOW,
    )

    assert without_turn_lease is False
    assert first is True
    assert second is False


def test_recoverable_turn_runs_excludes_terminal_rows(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    store.create_turn_run(
        turn_run_id="running",
        session_key="cli:s1",
        user_message_id=None,
        now=NOW,
    )
    store.create_turn_run(
        turn_run_id="completed",
        session_key="cli:s1",
        user_message_id=None,
        now=NOW,
    )
    store.mark_turn_run_completed(turn_run_id="completed", now=NOW)

    rows = store.list_recoverable_turn_runs(now=NOW + timedelta(seconds=1))

    assert [row["turn_run_id"] for row in rows] == ["running"]
