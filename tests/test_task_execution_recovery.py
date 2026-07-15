from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from agent.config_models import TaskExecutionConfig
from agent.task_plan.execution_service import (
    TaskExecutionConflictError,
    TaskExecutionService,
)
from agent.task_plan.recovery import TaskExecutionRecoveryService
from agent.task_plan.service import TaskPlanService
from agent.task_plan.store import TaskPlanStore


@dataclass
class RecoveryFixture:
    store: TaskPlanStore
    plan_service: TaskPlanService
    execution_service: TaskExecutionService
    recovery: TaskExecutionRecoveryService
    task_id: str
    attempt_id: str


@pytest.fixture
def recovery_fixture(tmp_path: Path):
    def build(
        *,
        status: str,
        owner: str,
        lease_expires_at: str = "2026-07-15T00:30:00+00:00",
        now: str = "2026-07-15T00:00:00+00:00",
    ) -> RecoveryFixture:
        current_time = datetime.fromisoformat(now)
        store = TaskPlanStore(tmp_path / f"{status}-{owner}.db")
        plan_service = TaskPlanService(store)
        plan = plan_service.create_task_plan(
            session_key="cli:s1",
            title="Recover execution",
            steps=["Read README"],
        )
        claim = store.claim_execution_attempt(
            task_id=plan.task_id,
            step_id=plan.steps[0].step_id,
            session_key="cli:s1",
            request_id="req-recovery",
            idempotency_key=f"recovery-{status}-{owner}",
            owner_instance_id=owner,
            lease_expires_at=lease_expires_at,
        )
        if status == "running":
            store.start_execution_attempt(
                attempt_id=claim.attempt.attempt_id,
                owner_instance_id=owner,
                now=datetime(2026, 7, 14, 23, 59, tzinfo=UTC),
            )
        elif status == "waiting_authorization":
            store.defer_execution_attempt(
                attempt_id=claim.attempt.attempt_id,
                owner_instance_id=owner,
                now=datetime(2026, 7, 14, 23, 59, tzinfo=UTC),
                terminal_reason="authorization required",
            )
        execution_service = TaskExecutionService(
            store=store,
            plan_service=plan_service,
            runtime_instance_id="runtime-current",
            config=TaskExecutionConfig(lease_seconds=60),
            clock=lambda: current_time,
        )
        return RecoveryFixture(
            store=store,
            plan_service=plan_service,
            execution_service=execution_service,
            recovery=TaskExecutionRecoveryService(
                service=execution_service,
                clock=lambda: current_time,
            ),
            task_id=plan.task_id,
            attempt_id=claim.attempt.attempt_id,
        )

    return build


def test_old_runtime_running_attempt_blocks_without_retry(recovery_fixture) -> None:
    fixture = recovery_fixture(status="running", owner="runtime-old")

    results = fixture.recovery.reconcile_session("cli:s1")

    snapshot = fixture.execution_service.inspect(
        session_key="cli:s1",
        attempt_id=fixture.attempt_id,
    )
    plan = fixture.plan_service.get_active_task_plan(session_key="cli:s1")
    assert results[0].reason == "runtime_restarted_outcome_unknown"
    assert results[0].step_reset is True
    assert snapshot.attempt is not None
    assert snapshot.attempt.status == "blocked"
    assert plan is not None
    assert plan.steps[0].status == "pending"
    assert len(fixture.store.list_execution_attempts(fixture.task_id)) == 1


def test_waiting_authorization_survives_restart(recovery_fixture) -> None:
    fixture = recovery_fixture(status="waiting_authorization", owner="runtime-old")

    assert fixture.recovery.reconcile_session("cli:s1") == ()

    snapshot = fixture.execution_service.inspect(
        session_key="cli:s1",
        attempt_id=fixture.attempt_id,
    )
    assert snapshot.attempt is not None
    assert snapshot.attempt.status == "waiting_authorization"


def test_expired_current_runtime_lease_blocks_as_unknown(recovery_fixture) -> None:
    fixture = recovery_fixture(
        status="running",
        owner="runtime-current",
        lease_expires_at="2026-07-15T00:00:00+00:00",
        now="2026-07-15T00:01:00+00:00",
    )

    results = fixture.recovery.reconcile_session("cli:s1")

    snapshot = fixture.execution_service.inspect(
        session_key="cli:s1",
        attempt_id=fixture.attempt_id,
    )
    assert results[0].reason == "lease_expired_outcome_unknown"
    assert snapshot.attempt is not None
    assert snapshot.attempt.status == "blocked"


def test_recovered_blocked_step_requires_explicit_retry(recovery_fixture) -> None:
    fixture = recovery_fixture(status="running", owner="runtime-old")
    fixture.recovery.reconcile_session("cli:s1")
    before = fixture.store.list_execution_attempts(fixture.task_id)

    with pytest.raises(TaskExecutionConflictError, match="explicit_retry"):
        fixture.execution_service.begin_next_step(
            session_key="cli:s1",
            request_id="req-ordinary-continue",
        )

    after = fixture.store.list_execution_attempts(fixture.task_id)
    assert [item.attempt_id for item in after] == [item.attempt_id for item in before]


def test_recovered_blocked_step_can_be_explicitly_retried(recovery_fixture) -> None:
    fixture = recovery_fixture(status="running", owner="runtime-old")
    fixture.recovery.reconcile_session("cli:s1")
    plan = fixture.plan_service.get_active_task_plan(session_key="cli:s1")
    assert plan is not None

    retry = fixture.execution_service.retry_step(
        session_key="cli:s1",
        step_id=plan.steps[0].step_id,
        request_id="req-explicit-retry",
    )

    assert retry.attempt.attempt_no == 2
    assert retry.attempt.status == "pending"
