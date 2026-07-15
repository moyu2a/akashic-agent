from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from agent.task_plan.execution_models import AttemptStatus
from agent.task_plan.execution_service import TaskExecutionService


@dataclass(frozen=True)
class RecoveryResult:
    attempt_id: str
    previous_status: AttemptStatus
    current_status: AttemptStatus
    reason: str
    step_reset: bool


class TaskExecutionRecoveryService:
    def __init__(
        self,
        *,
        service: TaskExecutionService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._service = service
        self._clock = clock or (lambda: datetime.now(UTC))

    def reconcile_startup(self) -> tuple[RecoveryResult, ...]:
        return self._reconcile(session_key=None)

    def reconcile_session(self, session_key: str) -> tuple[RecoveryResult, ...]:
        return self._reconcile(session_key=session_key)

    def _reconcile(self, *, session_key: str | None) -> tuple[RecoveryResult, ...]:
        reconciled = self._service.reconcile_attempts(
            now=self._clock(),
            session_key=session_key,
        )
        return tuple(
            RecoveryResult(
                attempt_id=item.attempt.attempt_id,
                previous_status=item.previous_status,
                current_status=item.attempt.status,
                reason=item.reason,
                step_reset=item.step_reset,
            )
            for item in reconciled
        )
