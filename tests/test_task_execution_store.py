from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier

import pytest

from agent.task_plan.store import (
    ActiveTaskExistsError,
    ExecutionAttemptConflictError,
    TaskPlanStore,
)


LEASE_EXPIRES_AT = "2030-07-15T01:00:00+00:00"
NOW = datetime(2030, 7, 15, tzinfo=UTC)


def _create_claimed_attempt(tmp_path: Path) -> tuple[TaskPlanStore, str, str, str]:
    store = TaskPlanStore(tmp_path / "task.db")
    plan = store.create_plan(
        session_key="cli:s1",
        title="Read project",
        step_titles=["Read README"],
    )
    result = store.claim_execution_attempt(
        task_id=plan.task_id,
        step_id=plan.steps[0].step_id,
        session_key="cli:s1",
        request_id="req-1",
        idempotency_key="idem-1",
        owner_instance_id="runtime-1",
        lease_expires_at=LEASE_EXPIRES_AT,
    )
    return store, plan.task_id, plan.steps[0].step_id, result.attempt.attempt_id


def test_schema_migrates_execution_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "task.db"
    _seed_base_task_plan_schema(db_path)

    store = TaskPlanStore(db_path)
    active = store.get_active_plan("cli:legacy")

    with sqlite3.connect(db_path) as conn:
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        indexes = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }
    assert active is not None
    assert active.task_id == "task_legacy"
    assert active.status == "active"
    assert [(step.step_id, step.status) for step in active.steps] == [
        ("step_legacy", "pending")
    ]
    assert {"task_execution_attempts", "task_execution_events"} <= names
    assert {
        "ux_task_plans_one_active_per_session",
        "ux_task_execution_one_active_per_step",
        "ux_task_execution_one_active_per_task",
        "ix_task_execution_events_attempt_sequence",
    } <= indexes
    with pytest.raises(ActiveTaskExistsError):
        store.create_plan(
            session_key="cli:legacy", title="Second task", step_titles=["Step"]
        )


def test_claim_replays_same_request(tmp_path: Path) -> None:
    store = TaskPlanStore(tmp_path / "task.db")
    plan = store.create_plan(
        session_key="cli:s1",
        title="Read project",
        step_titles=["Read README", "Summarize tests"],
    )
    first = store.claim_execution_attempt(
        task_id=plan.task_id,
        step_id=plan.steps[0].step_id,
        session_key="cli:s1",
        request_id="req-1",
        idempotency_key="idem-1",
        owner_instance_id="runtime-1",
        lease_expires_at=LEASE_EXPIRES_AT,
    )
    second = store.claim_execution_attempt(
        task_id=plan.task_id,
        step_id=plan.steps[0].step_id,
        session_key="cli:s1",
        request_id="req-1",
        idempotency_key="idem-1",
        owner_instance_id="runtime-1",
        lease_expires_at=LEASE_EXPIRES_AT,
    )
    assert first.attempt.attempt_id == second.attempt.attempt_id
    assert first.disposition == "created"
    assert second.disposition == "request_replay"


def test_concurrent_claim_has_one_active_attempt(tmp_path: Path) -> None:
    db_path = tmp_path / "task.db"
    setup_store = TaskPlanStore(db_path)
    plan = setup_store.create_plan(
        session_key="cli:s1",
        title="Read project",
        step_titles=["Read README"],
    )

    barrier = Barrier(2)

    def claim(index: int) -> tuple[str, str]:
        store = TaskPlanStore(db_path)
        barrier.wait()
        result = store.claim_execution_attempt(
            task_id=plan.task_id,
            step_id=plan.steps[0].step_id,
            session_key="cli:s1",
            request_id=f"req-{index}",
            idempotency_key=f"idem-{index}",
            owner_instance_id="runtime-1",
            lease_expires_at=LEASE_EXPIRES_AT,
        )
        return result.attempt.attempt_id, result.disposition

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, [1, 2]))
    assert len({attempt_id for attempt_id, _ in results}) == 1
    assert {disposition for _, disposition in results} == {
        "created",
        "active_conflict",
    }


def test_retry_claim_is_atomic_against_ordinary_continue(tmp_path: Path) -> None:
    db_path = tmp_path / "task.db"
    setup_store, task_id, step_id, first_attempt_id = _create_claimed_attempt(tmp_path)
    setup_store.start_execution_attempt(
        attempt_id=first_attempt_id,
        owner_instance_id="runtime-1",
        now=NOW,
    )
    setup_store.finalize_execution_attempt(
        attempt_id=first_attempt_id,
        owner_instance_id="runtime-1",
        now=NOW,
        success=False,
        error_code="read_failed",
    )
    barrier = Barrier(2)

    def claim(action: str) -> str:
        store = TaskPlanStore(db_path)
        barrier.wait()
        try:
            result = store.claim_execution_attempt(
                task_id=task_id,
                step_id=step_id,
                session_key="cli:s1",
                request_id=f"req-{action}",
                idempotency_key=f"idem-{action}",
                owner_instance_id="runtime-1",
                lease_expires_at=LEASE_EXPIRES_AT,
                retry_from_attempt_id=(
                    first_attempt_id if action == "retry" else None
                ),
            )
        except ExecutionAttemptConflictError:
            return "conflict"
        return result.disposition

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(claim, ["retry", "continue"]))

    assert sorted(outcomes) in (
        ["active_conflict", "created"],
        ["conflict", "created"],
    )
    attempts = setup_store.list_execution_attempts(task_id)
    assert len(attempts) == 2
    assert attempts[-1].attempt_no == 2
    assert attempts[-1].request_id == "req-retry"


def test_retry_claim_rolls_back_step_reset_and_attempt_on_failure(tmp_path: Path) -> None:
    store, task_id, step_id, first_attempt_id = _create_claimed_attempt(tmp_path)
    store.start_execution_attempt(
        attempt_id=first_attempt_id,
        owner_instance_id="runtime-1",
        now=NOW,
    )
    store.finalize_execution_attempt(
        attempt_id=first_attempt_id,
        owner_instance_id="runtime-1",
        now=NOW,
        success=False,
        error_code="read_failed",
    )
    store._after_execution_mutation = _raise_at(  # type: ignore[method-assign]
        "retry_after_step_reset"
    )

    with pytest.raises(RuntimeError, match="retry_after_step_reset"):
        store.claim_execution_attempt(
            task_id=task_id,
            step_id=step_id,
            session_key="cli:s1",
            request_id="req-retry",
            idempotency_key="idem-retry",
            owner_instance_id="runtime-1",
            lease_expires_at=LEASE_EXPIRES_AT,
            retry_from_attempt_id=first_attempt_id,
        )

    plan = store.get_plan(task_id)
    assert plan is not None
    assert plan.steps[0].status == "failed"
    assert len(store.list_execution_attempts(task_id)) == 1


def test_claim_persists_initial_event_and_query_helpers(tmp_path: Path) -> None:
    store, task_id, step_id, attempt_id = _create_claimed_attempt(tmp_path)

    attempt = store.get_execution_attempt(attempt_id)
    by_request = store.get_execution_attempt_by_request(
        session_key="cli:s1", request_id="req-1"
    )
    active = store.get_active_execution_attempt(task_id)
    latest = store.get_latest_execution_attempt_for_step(step_id)
    events = store.list_execution_events(attempt_id)

    assert attempt is not None
    assert by_request == attempt
    assert active == attempt
    assert latest == attempt
    assert store.list_execution_attempts(task_id) == [attempt]
    assert store.list_recoverable_execution_attempts("cli:s1") == [attempt]
    assert [(event.sequence_no, event.event_type) for event in events] == [
        (1, "attempt_claimed")
    ]


def test_start_append_and_finalize_success_update_all_records(tmp_path: Path) -> None:
    store, task_id, _, attempt_id = _create_claimed_attempt(tmp_path)

    started = store.start_execution_attempt(
        attempt_id=attempt_id,
        owner_instance_id="runtime-1",
        now=NOW,
    )
    event = store.append_execution_event(
        attempt_id=attempt_id,
        owner_instance_id="runtime-1",
        now=NOW,
        event_type="tool_finished",
        tool_name="read_file",
        tool_call_id="call-1",
        source_turn_id=42,
        tool_risk="read-only",
        tool_capabilities=("filesystem:read",),
        counts_as_work=True,
        invoker_reached=True,
        invoker_succeeded=True,
        execution_status="completed",
        result_ok=True,
        result_preview="README contents",
    )
    finished = store.finalize_execution_attempt(
        attempt_id=attempt_id,
        owner_instance_id="runtime-1",
        now=NOW,
        success=True,
        result_summary="README read",
    )
    plan = store.get_plan(task_id)

    assert started.status == "running"
    assert event.sequence_no == 3
    assert event.tool_call_id == "call-1"
    assert event.tool_capabilities == ("filesystem:read",)
    assert event.counts_as_work is True
    assert finished.status == "succeeded"
    assert plan is not None
    assert plan.steps[0].status == "completed"
    assert plan.status == "completed"
    assert [item.event_type for item in store.list_execution_events(attempt_id)] == [
        "attempt_claimed",
        "attempt_started",
        "tool_finished",
        "attempt_succeeded",
    ]


def test_finalize_failure_marks_attempt_and_step_failed(tmp_path: Path) -> None:
    store, task_id, _, attempt_id = _create_claimed_attempt(tmp_path)
    store.start_execution_attempt(
        attempt_id=attempt_id, owner_instance_id="runtime-1", now=NOW
    )

    failed = store.finalize_execution_attempt(
        attempt_id=attempt_id,
        owner_instance_id="runtime-1",
        now=NOW,
        success=False,
        error_code="tool_failed",
        terminal_reason="tool invocation failed",
    )
    plan = store.get_plan(task_id)

    assert failed.status == "failed"
    assert failed.error_code == "tool_failed"
    assert plan is not None
    assert plan.steps[0].status == "failed"
    assert plan.status == "active"
    assert store.list_execution_events(attempt_id)[-1].event_type == "attempt_failed"


def test_block_defer_abort_and_reconcile_preserve_required_step_state(
    tmp_path: Path,
) -> None:
    store, task_id, _, attempt_id = _create_claimed_attempt(tmp_path)
    deferred = store.defer_execution_attempt(
        attempt_id=attempt_id,
        owner_instance_id="runtime-1",
        now=NOW,
        terminal_reason="authorization required",
    )
    assert deferred.status == "waiting_authorization"
    assert store.get_plan(task_id).steps[0].status == "pending"  # type: ignore[union-attr]
    aborted = store.abort_execution_attempt(
        attempt_id=attempt_id,
        terminal_reason="user cancelled",
    )
    assert aborted.status == "cancelled"

    _, task_id, _, attempt_id = _create_claimed_attempt(tmp_path / "stale")
    store = TaskPlanStore(tmp_path / "stale" / "task.db")
    store.start_execution_attempt(
        attempt_id=attempt_id, owner_instance_id="runtime-1", now=NOW
    )
    reconciled = store.reconcile_execution_attempts(
        now=datetime(2030, 7, 15, 2, tzinfo=UTC),
        runtime_instance_id="runtime-1",
    )
    assert [item.attempt.status for item in reconciled] == ["blocked"]
    assert store.get_plan(task_id).steps[0].status == "pending"  # type: ignore[union-attr]


def test_block_requires_current_unexpired_owner_and_resets_step(tmp_path: Path) -> None:
    store, task_id, _, attempt_id = _create_claimed_attempt(tmp_path)

    with pytest.raises(ExecutionAttemptConflictError):
        store.block_execution_attempt(
            attempt_id=attempt_id,
            owner_instance_id="runtime-other",
            now=NOW,
            terminal_reason="interrupted",
        )

    blocked = store.block_execution_attempt(
        attempt_id=attempt_id,
        owner_instance_id="runtime-1",
        now=NOW,
        terminal_reason="interrupted",
        error_code="turn_interrupted",
    )
    assert blocked.status == "blocked"
    assert blocked.error_code == "turn_interrupted"
    assert store.get_plan(task_id).steps[0].status == "pending"  # type: ignore[union-attr]
    assert store.list_execution_events(attempt_id)[-1].error_code == "turn_interrupted"


def test_lease_cas_never_renews_expired_or_foreign_attempt(tmp_path: Path) -> None:
    store, _, _, attempt_id = _create_claimed_attempt(tmp_path)

    renewed = store.renew_execution_attempt_lease(
        attempt_id=attempt_id,
        owner_instance_id="runtime-1",
        now=NOW,
        lease_expires_at="2030-07-15T02:00:00+00:00",
    )
    assert renewed.lease_expires_at == "2030-07-15T02:00:00+00:00"

    with pytest.raises(ExecutionAttemptConflictError):
        store.renew_execution_attempt_lease(
            attempt_id=attempt_id,
            owner_instance_id="runtime-other",
            now=NOW,
            lease_expires_at="2030-07-15T03:00:00+00:00",
        )
    with pytest.raises(ExecutionAttemptConflictError):
        store.renew_execution_attempt_lease(
            attempt_id=attempt_id,
            owner_instance_id="runtime-1",
            now=datetime(2030, 7, 15, 2, 1, tzinfo=UTC),
            lease_expires_at="2030-07-15T04:00:00+00:00",
        )


def test_lease_cas_rejects_expired_offset_crossing_timestamp(tmp_path: Path) -> None:
    store = TaskPlanStore(tmp_path / "task.db")
    plan = store.create_plan(
        session_key="cli:s1", title="Read project", step_titles=["Read README"]
    )
    claim = store.claim_execution_attempt(
        task_id=plan.task_id,
        step_id=plan.steps[0].step_id,
        session_key="cli:s1",
        request_id="req-offset",
        idempotency_key="idem-offset",
        owner_instance_id="runtime-1",
        lease_expires_at="2030-07-15T09:00:00+08:00",
    )
    assert claim.attempt.lease_expires_at == "2030-07-15T01:00:00+00:00"

    with pytest.raises(ExecutionAttemptConflictError):
        store.renew_execution_attempt_lease(
            attempt_id=claim.attempt.attempt_id,
            owner_instance_id="runtime-1",
            now=datetime(2030, 7, 15, 2, tzinfo=UTC),
            lease_expires_at="2030-07-15T03:00:00+00:00",
        )


def test_schema_normalizes_persisted_legacy_offset_lease(tmp_path: Path) -> None:
    store, _, _, attempt_id = _create_claimed_attempt(tmp_path)
    with sqlite3.connect(tmp_path / "task.db") as conn:
        conn.execute(
            """
            UPDATE task_execution_attempts SET lease_expires_at = ?
            WHERE attempt_id = ?
            """,
            ("2030-07-15T09:00:00+08:00", attempt_id),
        )

    upgraded = TaskPlanStore(tmp_path / "task.db")
    attempt = upgraded.get_execution_attempt(attempt_id)

    assert attempt is not None
    assert attempt.lease_expires_at == "2030-07-15T01:00:00+00:00"


def _seed_base_task_plan_schema(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE task_plans (
                task_id TEXT PRIMARY KEY,
                session_key TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL CHECK (
                    status IN ('active', 'completed', 'cancelled', 'failed')
                ),
                source_turn_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT,
                terminal_reason TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE UNIQUE INDEX ux_task_plans_one_active_per_session
            ON task_plans(session_key)
            WHERE status = 'active';

            CREATE INDEX ix_task_plans_session_status_updated
            ON task_plans(session_key, status, updated_at);

            CREATE TABLE task_steps (
                step_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL CHECK (
                    status IN (
                        'pending', 'in_progress', 'completed', 'failed', 'skipped'
                    )
                ),
                tool_names_json TEXT NOT NULL DEFAULT '[]',
                result_summary TEXT NOT NULL DEFAULT '',
                source_turn_id INTEGER,
                started_at TEXT,
                completed_at TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY(task_id) REFERENCES task_plans(task_id) ON DELETE CASCADE,
                UNIQUE(task_id, step_index)
            );

            CREATE INDEX ix_task_steps_task_index
            ON task_steps(task_id, step_index);
            """
        )
        conn.execute(
            """
            INSERT INTO task_plans (
                task_id, session_key, title, status, created_at, updated_at,
                metadata_json
            ) VALUES (?, ?, ?, 'active', ?, ?, '{}')
            """,
            (
                "task_legacy",
                "cli:legacy",
                "Existing task",
                "2030-07-15T00:00:00+00:00",
                "2030-07-15T00:00:00+00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO task_steps (step_id, task_id, step_index, title, status)
            VALUES ('step_legacy', 'task_legacy', 1, 'Existing step', 'pending')
            """
        )


@pytest.mark.parametrize("failure_point", ["claim_after_attempt_insert", "claim_after_event_insert"])
def test_claim_rolls_back_when_injected_mutation_fails(
    tmp_path: Path, failure_point: str
) -> None:
    store = TaskPlanStore(tmp_path / "task.db")
    plan = store.create_plan(
        session_key="cli:s1", title="Read project", step_titles=["Read README"]
    )
    store._after_execution_mutation = _raise_at(failure_point)  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match=failure_point):
        store.claim_execution_attempt(
            task_id=plan.task_id,
            step_id=plan.steps[0].step_id,
            session_key="cli:s1",
            request_id="req-1",
            idempotency_key="idem-1",
            owner_instance_id="runtime-1",
            lease_expires_at=LEASE_EXPIRES_AT,
        )
    assert store.list_execution_attempts(plan.task_id) == []


def test_start_rolls_back_when_step_update_fails(tmp_path: Path) -> None:
    store, task_id, _, attempt_id = _create_claimed_attempt(tmp_path)
    store._after_execution_mutation = _raise_at("start_after_step_update")  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="start_after_step_update"):
        store.start_execution_attempt(
            attempt_id=attempt_id, owner_instance_id="runtime-1", now=NOW
        )
    assert store.get_execution_attempt(attempt_id).status == "pending"  # type: ignore[union-attr]
    assert store.get_plan(task_id).steps[0].status == "pending"  # type: ignore[union-attr]


def test_finalize_rolls_back_when_plan_completion_fails(tmp_path: Path) -> None:
    store, task_id, _, attempt_id = _create_claimed_attempt(tmp_path)
    store.start_execution_attempt(
        attempt_id=attempt_id, owner_instance_id="runtime-1", now=NOW
    )
    store._after_execution_mutation = _raise_at("finalize_after_plan_completion")  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="finalize_after_plan_completion"):
        store.finalize_execution_attempt(
            attempt_id=attempt_id,
            owner_instance_id="runtime-1",
            now=NOW,
            success=True,
        )
    assert store.get_execution_attempt(attempt_id).status == "running"  # type: ignore[union-attr]
    assert store.get_plan(task_id).status == "active"  # type: ignore[union-attr]
    assert [item.event_type for item in store.list_execution_events(attempt_id)] == [
        "attempt_claimed",
        "attempt_started",
    ]


def test_block_rolls_back_between_attempt_step_and_event_mutations(tmp_path: Path) -> None:
    store, task_id, _, attempt_id = _create_claimed_attempt(tmp_path)
    store._after_execution_mutation = _raise_at("block_after_step_reset")  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="block_after_step_reset"):
        store.block_execution_attempt(
            attempt_id=attempt_id,
            owner_instance_id="runtime-1",
            now=NOW,
            terminal_reason="interrupted",
        )
    assert store.get_execution_attempt(attempt_id).status == "pending"  # type: ignore[union-attr]
    assert store.get_plan(task_id).steps[0].status == "pending"  # type: ignore[union-attr]
    assert [item.event_type for item in store.list_execution_events(attempt_id)] == [
        "attempt_claimed"
    ]


def _raise_at(expected_point: str):
    def inject(point: str) -> None:
        if point == expected_point:
            raise RuntimeError(point)

    return inject
