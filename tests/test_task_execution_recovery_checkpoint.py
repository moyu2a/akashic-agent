from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from agent.config_models import TaskExecutionConfig
from agent.task_plan.execution_models import RuntimeToolEvent
from agent.task_plan.execution_service import TaskExecutionService
from agent.task_plan.service import TaskPlanService
from agent.task_plan.store import TaskPlanStore


NOW = datetime(2030, 7, 15, tzinfo=UTC)


def test_recovery_checkpoint_preserves_started_metadata(tmp_path: Path) -> None:
    store = TaskPlanStore(tmp_path / "task.db")
    plan = store.create_plan(
        session_key="cli:s1",
        title="Recover tool",
        step_titles=["Run tool"],
    )
    claim = store.claim_execution_attempt(
        task_id=plan.task_id,
        step_id=plan.steps[0].step_id,
        session_key="cli:s1",
        request_id="req-1",
        idempotency_key="idem-1",
        owner_instance_id="runtime-1",
        lease_expires_at="2030-07-15T01:00:00+00:00",
    )
    store.start_execution_attempt(
        attempt_id=claim.attempt.attempt_id,
        owner_instance_id="runtime-1",
        now=NOW,
    )
    store.append_execution_event(
        attempt_id=claim.attempt.attempt_id,
        owner_instance_id="runtime-1",
        now=NOW,
        event_type="tool_started",
        tool_name="http_call",
        tool_call_id="call-1",
        counts_as_work=True,
        invoker_reached=True,
        invoker_succeeded=False,
        execution_status="running",
        arguments_hash="hash-1",
        metadata={
            "recovery_ref": "remote-call-1",
            "pollable": True,
            "side_effect": False,
        },
    )

    checkpoint = store.get_execution_recovery_checkpoint(claim.attempt.attempt_id)

    assert checkpoint is not None
    assert checkpoint["attempt_id"] == claim.attempt.attempt_id
    assert checkpoint["started"]["metadata"]["recovery_ref"] == "remote-call-1"
    assert checkpoint["started"]["metadata"]["pollable"] is True
    assert checkpoint["finished"] is None


def test_recovery_checkpoint_probe_confirms_completion(tmp_path: Path) -> None:
    store = TaskPlanStore(tmp_path / "task.db")
    plan_service = TaskPlanService(store)
    plan = plan_service.create_task_plan(
        session_key="cli:s1",
        title="Recover tool",
        steps=["Run tool"],
    )
    claim = store.claim_execution_attempt(
        task_id=plan.task_id,
        step_id=plan.steps[0].step_id,
        session_key="cli:s1",
        request_id="req-1",
        idempotency_key="idem-1",
        owner_instance_id="runtime-1",
        lease_expires_at="2030-07-15T01:00:00+00:00",
    )
    store.start_execution_attempt(
        attempt_id=claim.attempt.attempt_id,
        owner_instance_id="runtime-1",
        now=NOW,
    )
    store.append_execution_event(
        attempt_id=claim.attempt.attempt_id,
        owner_instance_id="runtime-1",
        now=NOW,
        event_type="tool_started",
        tool_name="http_call",
        tool_call_id="call-1",
        counts_as_work=True,
        invoker_reached=True,
        invoker_succeeded=False,
        execution_status="running",
        arguments_hash="hash-1",
        metadata={
            "recovery_ref": "remote-call-1",
            "pollable": True,
            "side_effect": False,
        },
    )
    service = TaskExecutionService(
        store=store,
        plan_service=plan_service,
        runtime_instance_id="runtime-1",
        config=TaskExecutionConfig(lease_seconds=60),
        clock=lambda: NOW,
    )

    snapshot = service.resolve_recovery_checkpoint(
        session_key="cli:s1",
        attempt_id=claim.attempt.attempt_id,
        probe=lambda _checkpoint: True,
    )

    assert snapshot.attempt is not None
    assert snapshot.attempt.status == "running"
    assert any(event.event_type == "tool_finished" for event in snapshot.events)


def test_recovery_checkpoint_probe_failure_blocks_attempt(tmp_path: Path) -> None:
    store = TaskPlanStore(tmp_path / "task.db")
    plan_service = TaskPlanService(store)
    plan = plan_service.create_task_plan(
        session_key="cli:s1",
        title="Recover tool",
        steps=["Run tool"],
    )
    claim = store.claim_execution_attempt(
        task_id=plan.task_id,
        step_id=plan.steps[0].step_id,
        session_key="cli:s1",
        request_id="req-1",
        idempotency_key="idem-1",
        owner_instance_id="runtime-1",
        lease_expires_at="2030-07-15T01:00:00+00:00",
    )
    store.start_execution_attempt(
        attempt_id=claim.attempt.attempt_id,
        owner_instance_id="runtime-1",
        now=NOW,
    )
    store.append_execution_event(
        attempt_id=claim.attempt.attempt_id,
        owner_instance_id="runtime-1",
        now=NOW,
        event_type="tool_started",
        tool_name="http_call",
        tool_call_id="call-1",
        counts_as_work=True,
        invoker_reached=True,
        invoker_succeeded=False,
        execution_status="running",
        arguments_hash="hash-1",
        metadata={
            "recovery_ref": "remote-call-1",
            "pollable": True,
            "side_effect": False,
        },
    )
    service = TaskExecutionService(
        store=store,
        plan_service=plan_service,
        runtime_instance_id="runtime-1",
        config=TaskExecutionConfig(lease_seconds=60),
        clock=lambda: NOW,
    )

    snapshot = service.resolve_recovery_checkpoint(
        session_key="cli:s1",
        attempt_id=claim.attempt.attempt_id,
        probe=lambda _checkpoint: False,
    )

    assert snapshot.attempt is not None
    assert snapshot.attempt.status == "blocked"
    assert snapshot.attempt.terminal_reason == "runtime_restarted_outcome_unknown"
