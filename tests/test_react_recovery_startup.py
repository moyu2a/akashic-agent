from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from agent.recovery.react_recovery import ReactRecoveryService
from session.store import SessionStore


NOW = datetime(2031, 1, 1, tzinfo=UTC)


def _seed_turn_with_step(store: SessionStore, *, status: str = "running") -> None:
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
    with store._conn:  # noqa: SLF001 - white-box recovery fixture.
        store._conn.execute(
            "UPDATE turn_runs SET status = ?, lease_expires_at = ? WHERE turn_run_id = ?",
            (status, (NOW - timedelta(seconds=1)).isoformat(), "turn-1"),
        )


def _seed_tool_attempt(
    store: SessionStore,
    *,
    side_effect: bool,
    idempotent: bool,
    status: str = "running",
) -> None:
    attempt = store.persist_react_tool_call(
        turn_run_id="turn-1",
        step_id="step-1",
        tool_call_id="call-1",
        tool_name="probe",
        arguments_json="{}",
        arguments_hash="hash",
        recovery_ref="call-1",
        pollable=False,
        idempotent=idempotent,
        side_effect=side_effect,
        now=NOW,
    )
    with store._conn:  # noqa: SLF001 - white-box recovery fixture.
        store._conn.execute(
            """
            UPDATE tool_invocation_attempts
            SET status = ?, lease_expires_at = ?
            WHERE attempt_id = ?
            """,
            (status, (NOW - timedelta(seconds=1)).isoformat(), attempt["attempt_id"]),
        )


def test_startup_recovery_claims_turn_once_across_workers(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    _seed_turn_with_step(store, status="model_retry_pending")

    first = ReactRecoveryService(store, worker_id="w1").reconcile_startup(now=NOW)
    second = ReactRecoveryService(store, worker_id="w2").reconcile_startup(now=NOW)

    assert [item.reason for item in first] == ["model_retry_pending"]
    assert second == []


def test_startup_recovery_blocks_unknown_side_effect_tool(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    _seed_turn_with_step(store)
    _seed_tool_attempt(store, side_effect=True, idempotent=False)

    result = ReactRecoveryService(store, worker_id="w1").reconcile_startup(now=NOW)

    assert [item.reason for item in result] == ["blocked_side_effect_unknown"]
    assert store.get_turn_run("turn-1")["status"] == "blocked"


def test_startup_recovery_marks_idempotent_tool_for_retry(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    _seed_turn_with_step(store)
    _seed_tool_attempt(store, side_effect=False, idempotent=True)

    result = ReactRecoveryService(store, worker_id="w1").reconcile_startup(now=NOW)

    assert [item.reason for item in result] == ["tool_retry_pending"]
    assert store.get_tool_invocation_attempt("tool_turn-1_call-1")["status"] == "pending"


def test_tool_succeeded_invokes_resume_callback(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    _seed_turn_with_step(store)
    _seed_tool_attempt(store, side_effect=False, idempotent=True, status="succeeded")
    resumed: list[str] = []

    result = ReactRecoveryService(
        store,
        worker_id="w1",
        resume_turn=lambda turn_run_id: resumed.append(turn_run_id),
    ).reconcile_startup(now=NOW)

    assert [item.reason for item in result] == ["resumed_after_tool_success"]
    assert resumed == ["turn-1"]


def test_final_pending_turn_is_completed(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.db")
    _seed_turn_with_step(store, status="final_pending")

    result = ReactRecoveryService(store, worker_id="w1").reconcile_startup(now=NOW)

    assert [item.reason for item in result] == ["final_completed"]
    assert store.get_turn_run("turn-1")["status"] == "completed"
