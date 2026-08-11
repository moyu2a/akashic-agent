from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from agent.recovery.react_recovery import ReactRecoveryService
from session.store import SessionStore


NOW = datetime(2031, 1, 1, tzinfo=UTC)


def _turn(store: SessionStore, *, turn_status: str = "running") -> None:
    store.create_turn_run(
        turn_run_id="turn-1",
        session_key="cli:s1",
        user_message_id=None,
        now=NOW,
    )
    store.create_react_step(
        step_id="step-1",
        turn_run_id="turn-1",
        step_no=0,
        model_input_json="[]",
        now=NOW,
    )
    with store._conn:  # noqa: SLF001 - white-box crash fixture.
        store._conn.execute(
            """
            UPDATE turn_runs
            SET status = ?, lease_expires_at = ?
            WHERE turn_run_id = 'turn-1'
            """,
            (turn_status, (NOW - timedelta(seconds=1)).isoformat()),
        )


def _attempt(
    store: SessionStore,
    *,
    status: str,
    side_effect: bool = False,
    idempotent: bool = True,
) -> str:
    attempt = store.persist_react_tool_call(
        turn_run_id="turn-1",
        step_id="step-1",
        tool_call_id="call-1",
        tool_name="read_file",
        arguments_json='{"path":"README.md"}',
        arguments_hash="hash",
        recovery_ref="call-1",
        pollable=False,
        idempotent=idempotent,
        side_effect=side_effect,
        now=NOW,
    )
    with store._conn:  # noqa: SLF001 - white-box crash fixture.
        store._conn.execute(
            """
            UPDATE tool_invocation_attempts
            SET status = ?, lease_expires_at = ?
            WHERE attempt_id = ?
            """,
            (status, (NOW - timedelta(seconds=1)).isoformat(), attempt["attempt_id"]),
        )
    return str(attempt["attempt_id"])


def test_crash_after_model_running_commit_becomes_model_retry_pending(
    tmp_path: Path,
) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    _turn(store, turn_status="running")
    store.mark_react_step_model_running(
        step_id="step-1",
        runtime_instance_id="old-worker",
        lease_expires_at=NOW - timedelta(seconds=1),
        now=NOW - timedelta(seconds=2),
    )

    result = ReactRecoveryService(store, worker_id="new-worker").reconcile_startup(
        now=NOW
    )

    assert [item.reason for item in result] == ["model_retry_pending"]


def test_crash_after_tool_running_commit_retries_read_only_tool(
    tmp_path: Path,
) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    _turn(store)
    attempt_id = _attempt(store, status="running", side_effect=False, idempotent=True)

    result = ReactRecoveryService(store, worker_id="new-worker").reconcile_startup(
        now=NOW
    )

    assert [item.reason for item in result] == ["tool_retry_pending"]
    assert store.get_tool_invocation_attempt(attempt_id)["status"] == "pending"


def test_crash_after_tool_running_commit_blocks_unknown_side_effect(
    tmp_path: Path,
) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    _turn(store)
    attempt_id = _attempt(store, status="running", side_effect=True, idempotent=False)

    result = ReactRecoveryService(store, worker_id="new-worker").reconcile_startup(
        now=NOW
    )

    assert [item.reason for item in result] == ["blocked_side_effect_unknown"]
    assert store.get_tool_invocation_attempt(attempt_id)["status"] == "blocked"
    assert store.get_turn_run("turn-1")["status"] == "blocked"


def test_crash_after_tool_succeeded_invokes_resume_once(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    _turn(store)
    _attempt(store, status="succeeded")
    resumed: list[str] = []

    first = ReactRecoveryService(
        store,
        worker_id="new-worker",
        resume_turn=lambda turn_run_id: resumed.append(turn_run_id),
    ).reconcile_startup(now=NOW)
    second = ReactRecoveryService(
        store,
        worker_id="other-worker",
        resume_turn=lambda turn_run_id: resumed.append(turn_run_id),
    ).reconcile_startup(now=NOW)

    assert [item.reason for item in first] == ["resumed_after_tool_success"]
    assert second == []
    assert resumed == ["turn-1"]


def test_crash_after_final_pending_completes_turn(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    _turn(store, turn_status="final_pending")

    result = ReactRecoveryService(store, worker_id="new-worker").reconcile_startup(
        now=NOW
    )

    assert [item.reason for item in result] == ["final_completed"]
    assert store.get_turn_run("turn-1")["status"] == "completed"
