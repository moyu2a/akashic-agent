from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from agent.task_plan.execution_models import TaskExecutionAttempt, TaskExecutionSnapshot
from agent.task_plan.execution_service import (
    TaskExecutionConflictError,
    TaskExecutionService,
)


ExecutionOrchestrationAction = Literal["claimed", "replayed", "inspect", "conflict"]


@dataclass(frozen=True)
class ExecutionOrchestrationDecision:
    action: ExecutionOrchestrationAction
    reason: str
    snapshot: TaskExecutionSnapshot


class TaskExecutionOrchestrator:
    def __init__(self, service: TaskExecutionService) -> None:
        self._service = service

    def decide_continue(
        self,
        *,
        session_key: str,
        request_id: str,
        source_turn_id: int | None = None,
    ) -> ExecutionOrchestrationDecision:
        try:
            result = self._service.begin_next_step(
                session_key=session_key,
                request_id=request_id,
                source_turn_id=source_turn_id,
            )
        except TaskExecutionConflictError as exc:
            return ExecutionOrchestrationDecision(
                action="conflict",
                reason=str(exc),
                snapshot=self._service.inspect(session_key=session_key),
            )
        return self._decision(result.replayed, result.attempt, retry=False)

    def decide_retry(
        self,
        *,
        session_key: str,
        step_id: str,
        request_id: str,
        source_turn_id: int | None = None,
    ) -> ExecutionOrchestrationDecision:
        try:
            result = self._service.retry_step(
                session_key=session_key,
                step_id=step_id,
                request_id=request_id,
                source_turn_id=source_turn_id,
            )
        except TaskExecutionConflictError as exc:
            return ExecutionOrchestrationDecision(
                action="conflict",
                reason=str(exc),
                snapshot=self._service.inspect(session_key=session_key),
            )
        return self._decision(result.replayed, result.attempt, retry=True)

    @staticmethod
    def _decision(
        replayed: bool,
        attempt: TaskExecutionAttempt,
        *,
        retry: bool,
    ) -> ExecutionOrchestrationDecision:
        if replayed:
            return ExecutionOrchestrationDecision(
                action="replayed",
                reason="task_execution_request_replayed",
                snapshot=TaskExecutionSnapshot(attempt=attempt),
            )
        return ExecutionOrchestrationDecision(
            action="claimed",
            reason=(
                "task_execution_step_retry_claimed"
                if retry
                else "task_execution_step_claimed"
            ),
            snapshot=TaskExecutionSnapshot(attempt=attempt),
        )
