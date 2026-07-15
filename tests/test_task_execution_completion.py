from __future__ import annotations

from agent.policies.task_execution_completion import TaskExecutionCompletionPolicy
from agent.policies.task_execution_contract import TaskExecutionTurnContract
from agent.policies.tool_ledger import ToolCallLedger, ToolCallRecord
from agent.task_plan.execution_models import (
    TaskExecutionAttempt,
    TaskExecutionEvent,
    TaskExecutionSnapshot,
)


def _contract() -> TaskExecutionTurnContract:
    return TaskExecutionTurnContract(
        active=True,
        action="continue",
        phase="work",
        attempt_id="attempt-1",
        target_step_id="step-1",
        required_capabilities=frozenset({"task_execution.finish"}),
        allowed_capabilities=frozenset(
            {
                "task_execution.finish",
                "task_execution.defer",
                "task_execution.abort",
            }
        ),
        allowed_risks=frozenset({"read-only"}),
        work_call_budget=3,
        tool_search_budget=1,
        completion_capability="task_execution.finish",
        reason="attempt_running",
        matched_terms=(),
    )


def _snapshot(
    status: str,
    events: tuple[TaskExecutionEvent, ...],
    *,
    attempt_id: str = "attempt-1",
    step_id: str = "step-1",
) -> TaskExecutionSnapshot:
    attempt = TaskExecutionAttempt(
        attempt_id=attempt_id,
        task_id="task-1",
        step_id=step_id,
        session_key="cli:s1",
        request_id="req-1",
        idempotency_key="key-1",
        attempt_no=1,
        status=status,  # type: ignore[arg-type]
        execution_mode="read_only_auto",
        owner_instance_id="runtime-1",
        lease_expires_at="2030-01-01T00:00:00+00:00",
        source_turn_id=1,
        requested_tool_name="read_file",
        requested_arguments={},
        requested_capabilities=(),
        result_summary="done",
        error_code="",
        terminal_reason="",
        created_at="2030-01-01T00:00:00+00:00",
        started_at="2030-01-01T00:00:00+00:00",
        updated_at="2030-01-01T00:00:00+00:00",
        finished_at="2030-01-01T00:00:00+00:00",
    )
    return TaskExecutionSnapshot(attempt=attempt, events=events)


def _event(
    event_type: str,
    *,
    work: bool = False,
    attempt_id: str = "attempt-1",
) -> TaskExecutionEvent:
    return TaskExecutionEvent(
        event_id=f"event-{event_type}",
        attempt_id=attempt_id,
        sequence_no=1,
        event_type=event_type,  # type: ignore[arg-type]
        tool_name="read_file" if work else "",
        tool_call_id="call-1" if work else "",
        source_turn_id=1,
        tool_risk="read-only" if work else "",
        tool_capabilities=(),
        counts_as_work=work,
        invoker_reached=work,
        invoker_succeeded=work,
        execution_status="success" if work else "",
        result_ok=True if work else None,
        error_code="",
        arguments_hash="hash" if work else "",
        result_preview="README" if work else "",
        created_at="2030-01-01T00:00:00+00:00",
    )


def test_finish_only_completes_after_persisted_work_event_and_success_transition() -> (
    None
):
    policy = TaskExecutionCompletionPolicy()
    tools = {"finish_task_step_execution": frozenset({"task_execution.finish"})}

    no_work = policy.evaluate(
        contract=_contract(),
        snapshot=_snapshot("succeeded", (_event("attempt_succeeded"),)),
        ledger=ToolCallLedger(),
        tool_capabilities=tools,
    )
    completed = policy.evaluate(
        contract=_contract(),
        snapshot=_snapshot(
            "succeeded",
            (_event("tool_finished", work=True), _event("attempt_succeeded")),
        ),
        ledger=ToolCallLedger(),
        tool_capabilities=tools,
    )

    assert no_work is None
    assert completed is not None
    assert completed.action == "final_only"
    assert completed.reason == "task_execution_attempt_succeeded"


def test_boundary_ledger_or_synthetic_result_cannot_complete_running_attempt() -> None:
    ledger = ToolCallLedger(
        records=[
            ToolCallRecord(
                tool_name="read_file",
                tool_class="local_file",
                args_hash="hash",
                args_summary="{}",
                call_index=1,
                visible_before_call=True,
                execution_status="success",
                result_ok=True,
                counts_as_work=True,
                tool_risk="read-only",
                invoker_reached=True,
                invoker_succeeded=True,
            )
        ]
    )

    decision = TaskExecutionCompletionPolicy().evaluate(
        contract=_contract(),
        snapshot=_snapshot("running", ()),
        ledger=ledger,
        tool_capabilities={
            "finish_task_step_execution": frozenset({"task_execution.finish"})
        },
    )

    assert decision is None


def test_waiting_authorization_requires_durable_defer_transition() -> None:
    policy = TaskExecutionCompletionPolicy()
    tools = {"request_task_step_authorization": frozenset({"task_execution.defer"})}

    missing_event = policy.evaluate(
        contract=_contract(),
        snapshot=_snapshot("waiting_authorization", ()),
        ledger=ToolCallLedger(),
        tool_capabilities=tools,
    )
    deferred = policy.evaluate(
        contract=_contract(),
        snapshot=_snapshot(
            "waiting_authorization", (_event("authorization_deferred"),)
        ),
        ledger=ToolCallLedger(),
        tool_capabilities=tools,
    )

    assert missing_event is None
    assert deferred is not None
    assert deferred.reason == "task_execution_waiting_authorization"


def test_completion_rejects_snapshot_for_a_different_attempt() -> None:
    decision = TaskExecutionCompletionPolicy().evaluate(
        contract=_contract(),
        snapshot=_snapshot(
            "succeeded",
            (
                _event("tool_finished", work=True, attempt_id="attempt-2"),
                _event("attempt_succeeded", attempt_id="attempt-2"),
            ),
            attempt_id="attempt-2",
        ),
        ledger=ToolCallLedger(),
        tool_capabilities={
            "finish_task_step_execution": frozenset({"task_execution.finish"})
        },
    )

    assert decision is None


def test_completion_rejects_snapshot_for_a_different_target_step() -> None:
    decision = TaskExecutionCompletionPolicy().evaluate(
        contract=_contract(),
        snapshot=_snapshot(
            "succeeded",
            (_event("tool_finished", work=True), _event("attempt_succeeded")),
            step_id="step-2",
        ),
        ledger=ToolCallLedger(),
        tool_capabilities={
            "finish_task_step_execution": frozenset({"task_execution.finish"})
        },
    )

    assert decision is None
