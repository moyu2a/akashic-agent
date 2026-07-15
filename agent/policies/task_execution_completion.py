from __future__ import annotations

from collections.abc import Mapping

from agent.policies.task_execution_contract import TaskExecutionTurnContract
from agent.policies.tool_ledger import ToolCallLedger
from agent.policies.turn_completion_types import TurnCompletionDecision
from agent.task_plan.execution_models import TaskExecutionEvent, TaskExecutionSnapshot

_TRANSITION_EVENT_BY_STATUS = {
    "succeeded": "attempt_succeeded",
    "failed": "attempt_failed",
    "blocked": "attempt_blocked",
    "cancelled": "attempt_cancelled",
    "waiting_authorization": "authorization_deferred",
}


class TaskExecutionCompletionPolicy:
    """Complete only from durable attempt and event facts, never boundary output."""

    def evaluate(
        self,
        *,
        contract: TaskExecutionTurnContract | None,
        snapshot: TaskExecutionSnapshot | None,
        ledger: ToolCallLedger,
        tool_capabilities: Mapping[str, frozenset[str]],
    ) -> TurnCompletionDecision | None:
        del ledger
        if contract is None or not contract.active or snapshot is None:
            return None
        attempt = snapshot.attempt
        if attempt is None:
            return None
        if attempt.attempt_id != contract.attempt_id:
            return None
        if (
            contract.target_step_id is not None
            and attempt.step_id != contract.target_step_id
        ):
            return None
        transition_event = _TRANSITION_EVENT_BY_STATUS.get(attempt.status)
        if transition_event is None or not _has_event(
            snapshot.events, attempt.attempt_id, transition_event
        ):
            return None

        if attempt.status == "succeeded":
            if not _has_finish_provider(tool_capabilities):
                return None
            if not _has_eligible_work_event(snapshot.events, attempt.attempt_id):
                return None
            reason = "task_execution_attempt_succeeded"
        elif attempt.status == "waiting_authorization":
            reason = "task_execution_waiting_authorization"
        else:
            reason = f"task_execution_attempt_{attempt.status}"

        return TurnCompletionDecision(
            action="final_only",
            reason=reason,
            model_hint=(
                "Task execution has reached a durable state. Do not call more "
                "tools for this attempt."
            ),
            metadata={
                "attempt": {
                    "attempt_id": attempt.attempt_id,
                    "status": attempt.status,
                    "error_code": attempt.error_code[:128],
                    "terminal_reason": attempt.terminal_reason[:128],
                },
                "durable_transition": transition_event,
            },
        )


def _has_event(
    events: tuple[TaskExecutionEvent, ...], attempt_id: str, event_type: str
) -> bool:
    return any(
        event.attempt_id == attempt_id and event.event_type == event_type
        for event in events
    )


def _has_finish_provider(tool_capabilities: Mapping[str, frozenset[str]]) -> bool:
    return any(
        "task_execution.finish" in capabilities
        for capabilities in tool_capabilities.values()
    )


def _has_eligible_work_event(
    events: tuple[TaskExecutionEvent, ...], attempt_id: str
) -> bool:
    return any(
        event.attempt_id == attempt_id
        and event.event_type == "tool_finished"
        and event.counts_as_work
        and event.tool_risk == "read-only"
        and event.invoker_reached
        and event.invoker_succeeded
        and event.execution_status == "success"
        and event.result_ok is True
        and not event.error_code
        for event in events
    )
