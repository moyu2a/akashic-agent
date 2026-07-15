from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

from agent.config_models import TaskExecutionConfig
from agent.task_plan.execution_models import (
    RuntimeToolEvent,
    TaskExecutionAttempt,
    TaskExecutionEvent,
    TaskExecutionSnapshot,
)
from agent.task_plan.execution_redaction import (
    bounded_execution_preview,
    hash_execution_arguments,
    redact_execution_arguments,
)
from agent.task_plan.execution_store import ReconciledExecutionAttempt
from agent.task_plan.models import TaskPlan, TaskStep
from agent.task_plan.request_identity import derive_task_execution_idempotency_key
from agent.task_plan.service import (
    TaskPlanAccessDeniedError,
    TaskPlanConflictError,
    TaskPlanService,
)
from agent.task_plan.store import (
    ExecutionAttemptConflictError,
    TaskExecutionAttemptNotFoundError,
    TaskPlanStore,
)


_RETRYABLE_BLOCK_REASONS = frozenset(
    {
        "dispatch_interrupted",
        "lease_expired_outcome_unknown",
        "runtime_restarted_outcome_unknown",
        "turn_interrupted_outcome_unknown",
    }
)


@dataclass(frozen=True)
class BeginExecutionResult:
    attempt: TaskExecutionAttempt
    step: TaskStep
    replayed: bool


class TaskExecutionError(RuntimeError):
    pass


class TaskExecutionConflictError(TaskExecutionError):
    pass


class TaskExecutionAccessDeniedError(TaskExecutionError):
    pass


class TaskExecutionService:
    def __init__(
        self,
        store: TaskPlanStore,
        plan_service: TaskPlanService,
        *,
        runtime_instance_id: str,
        config: TaskExecutionConfig,
        clock: Callable[[], datetime],
    ) -> None:
        self.plan_service = plan_service
        self._store = store
        self._runtime_instance_id = runtime_instance_id
        self._config = config
        self._now = clock

    @property
    def store(self) -> TaskPlanStore:
        return self._store

    def replay_request(
        self, *, session_key: str, request_id: str
    ) -> BeginExecutionResult | None:
        attempt = self._store.get_execution_attempt_by_request(
            session_key=session_key, request_id=request_id
        )
        if attempt is None:
            return None
        plan = self._require_owned_plan(session_key=session_key, task_id=attempt.task_id)
        return BeginExecutionResult(
            attempt=attempt,
            step=self._find_step(plan, attempt.step_id),
            replayed=True,
        )

    def begin_next_step(
        self,
        *,
        session_key: str,
        request_id: str,
        source_turn_id: int | None = None,
    ) -> BeginExecutionResult:
        replay = self.replay_request(session_key=session_key, request_id=request_id)
        if replay is not None:
            return replay
        plan = self._require_active_owned_plan(session_key=session_key)
        active = self._store.get_active_execution_attempt(plan.task_id)
        if active is not None:
            raise TaskExecutionConflictError("attempt_already_active")
        if any(step.status == "failed" for step in plan.steps):
            raise TaskExecutionConflictError(
                "failed_step_requires_explicit_retry: explicit retry required"
            )

        blocked_pending = False
        for step in sorted(plan.steps, key=lambda item: item.index):
            if step.status != "pending":
                continue
            latest = self._store.get_latest_execution_attempt_for_step(step.step_id)
            if latest is not None and self._is_retryable_block(latest):
                blocked_pending = True
                continue
            return self._claim_step(
                plan=plan,
                step=step,
                session_key=session_key,
                request_id=request_id,
                source_turn_id=source_turn_id,
                action="continue",
            )
        if blocked_pending:
            raise TaskExecutionConflictError("blocked_step_requires_explicit_retry")
        raise TaskExecutionConflictError("no_pending_task_step")

    def retry_step(
        self,
        *,
        session_key: str,
        step_id: str,
        request_id: str,
        source_turn_id: int | None = None,
    ) -> BeginExecutionResult:
        replay = self.replay_request(session_key=session_key, request_id=request_id)
        if replay is not None:
            return replay
        plan = self._require_active_owned_plan(session_key=session_key)
        step = self._find_step(plan, step_id)
        active = self._store.get_active_execution_attempt(plan.task_id)
        if active is not None:
            raise TaskExecutionConflictError("attempt_already_active")
        latest = self._store.get_latest_execution_attempt_for_step(step.step_id)
        if latest is None or not self._is_retryable_attempt(latest):
            raise TaskExecutionConflictError("step_requires_failed_or_blocked_attempt")
        if step.status == "failed":
            try:
                self.plan_service.update_step_status(
                    session_key=session_key,
                    task_id=plan.task_id,
                    step_id=step.step_id,
                    status="pending",
                    source_turn_id=source_turn_id,
                )
            except TaskPlanConflictError as exc:
                raise TaskExecutionConflictError(str(exc)) from exc
            plan = self._require_active_owned_plan(session_key=session_key)
            step = self._find_step(plan, step_id)
        if step.status != "pending":
            raise TaskExecutionConflictError("retry_step_is_not_pending")
        return self._claim_step(
            plan=plan,
            step=step,
            session_key=session_key,
            request_id=request_id,
            source_turn_id=source_turn_id,
            action="retry",
        )

    def find_retryable_step(self, *, session_key: str) -> TaskStep | None:
        plan = self._require_active_owned_plan(session_key=session_key)
        for step in sorted(plan.steps, key=lambda item: item.index):
            latest = self._store.get_latest_execution_attempt_for_step(step.step_id)
            if latest is None or not self._is_retryable_attempt(latest):
                continue
            if step.status in {"failed", "pending"}:
                return step
        return None

    def start_attempt(
        self, *, session_key: str, attempt_id: str
    ) -> TaskExecutionSnapshot:
        self._require_owned_attempt(session_key=session_key, attempt_id=attempt_id)
        try:
            attempt = self._store.start_execution_attempt(
                attempt_id=attempt_id,
                owner_instance_id=self._runtime_instance_id,
                now=self._now(),
            )
        except (ExecutionAttemptConflictError, TaskExecutionAttemptNotFoundError) as exc:
            raise TaskExecutionConflictError(str(exc)) from exc
        return self._snapshot(attempt)

    def record_tool_event(
        self,
        *,
        session_key: str,
        attempt_id: str,
        event: RuntimeToolEvent,
    ) -> TaskExecutionEvent:
        if not isinstance(event, RuntimeToolEvent):
            raise TypeError("event must be a RuntimeToolEvent")
        self._require_owned_attempt(session_key=session_key, attempt_id=attempt_id)
        try:
            return self._store.append_execution_event(
                attempt_id=attempt_id,
                owner_instance_id=self._runtime_instance_id,
                now=self._now(),
                event_type=event.event_type,
                tool_name=bounded_execution_preview(event.tool_name, max_chars=128),
                tool_call_id=bounded_execution_preview(event.tool_call_id, max_chars=128),
                source_turn_id=event.source_turn_id,
                tool_risk=event.tool_risk,
                tool_capabilities=event.tool_capabilities,
                counts_as_work=event.counts_as_work,
                invoker_reached=event.invoker_reached,
                invoker_succeeded=event.invoker_succeeded,
                execution_status=event.execution_status,
                result_ok=event.result_ok,
                error_code=bounded_execution_preview(event.error_code, max_chars=128),
                arguments_hash=bounded_execution_preview(
                    event.arguments_hash, max_chars=128
                ),
                result_preview=bounded_execution_preview(event.result_preview),
            )
        except (ExecutionAttemptConflictError, TaskExecutionAttemptNotFoundError) as exc:
            raise TaskExecutionConflictError(str(exc)) from exc

    def finish_attempt(
        self,
        *,
        session_key: str,
        attempt_id: str,
        success: bool,
        result_summary: str,
        error_code: str = "",
    ) -> TaskExecutionSnapshot:
        self._require_owned_attempt(session_key=session_key, attempt_id=attempt_id)
        if success and not self._has_successful_work_event(attempt_id):
            raise TaskExecutionConflictError("successful finish requires work event")
        try:
            attempt = self._store.finalize_execution_attempt(
                attempt_id=attempt_id,
                owner_instance_id=self._runtime_instance_id,
                now=self._now(),
                success=success,
                result_summary=bounded_execution_preview(result_summary),
                error_code=bounded_execution_preview(error_code, max_chars=128),
                terminal_reason=(
                    "read_only_work_succeeded" if success else "read_only_work_failed"
                ),
            )
        except (ExecutionAttemptConflictError, TaskExecutionAttemptNotFoundError) as exc:
            raise TaskExecutionConflictError(str(exc)) from exc
        return self._snapshot(attempt)

    def block_attempt(
        self,
        *,
        session_key: str,
        attempt_id: str,
        terminal_reason: str,
        error_code: str = "",
    ) -> TaskExecutionSnapshot:
        attempt = self._require_owned_attempt(session_key=session_key, attempt_id=attempt_id)
        if attempt.status in {"succeeded", "failed", "blocked", "cancelled"}:
            return self._snapshot(attempt)
        reason = bounded_execution_preview(terminal_reason)
        bounded_error_code = bounded_execution_preview(error_code, max_chars=128)
        try:
            blocked = self._store.block_execution_attempt(
                attempt_id=attempt_id,
                owner_instance_id=self._runtime_instance_id,
                now=self._now(),
                terminal_reason=reason,
                error_code=bounded_error_code,
            )
        except (ExecutionAttemptConflictError, TaskExecutionAttemptNotFoundError) as exc:
            raise TaskExecutionConflictError(str(exc)) from exc
        return self._snapshot(blocked)

    def defer_attempt(
        self,
        *,
        session_key: str,
        attempt_id: str,
        tool_name: str,
        requested_arguments: dict[str, object],
        requested_capabilities: tuple[str, ...],
        reason: str,
    ) -> TaskExecutionSnapshot:
        self._require_owned_attempt(session_key=session_key, attempt_id=attempt_id)
        redacted_arguments = redact_execution_arguments(requested_arguments)
        arguments_hash = hash_execution_arguments(redacted_arguments)
        capability_preview = ",".join(
            bounded_execution_preview(capability, max_chars=96)
            for capability in requested_capabilities
        )
        terminal_reason = bounded_execution_preview(reason)
        terminal_reason = (
            f"{terminal_reason}; tool={bounded_execution_preview(tool_name, max_chars=128)}; "
            f"arguments_hash={arguments_hash}; capabilities={capability_preview}"
        )
        try:
            deferred = self._store.defer_execution_attempt(
                attempt_id=attempt_id,
                owner_instance_id=self._runtime_instance_id,
                now=self._now(),
                terminal_reason=bounded_execution_preview(terminal_reason),
            )
        except (ExecutionAttemptConflictError, TaskExecutionAttemptNotFoundError) as exc:
            raise TaskExecutionConflictError(str(exc)) from exc
        return self._snapshot(deferred)

    def abort_attempt(
        self, *, session_key: str, attempt_id: str, reason: str
    ) -> TaskExecutionSnapshot:
        self._require_owned_attempt(session_key=session_key, attempt_id=attempt_id)
        try:
            aborted = self._store.abort_execution_attempt(
                attempt_id=attempt_id,
                terminal_reason=bounded_execution_preview(reason),
            )
        except (ExecutionAttemptConflictError, TaskExecutionAttemptNotFoundError) as exc:
            raise TaskExecutionConflictError(str(exc)) from exc
        return self._snapshot(aborted)

    def inspect(
        self, *, session_key: str, attempt_id: str | None = None
    ) -> TaskExecutionSnapshot:
        if attempt_id is None:
            plan = self.plan_service.get_active_task_plan(session_key=session_key)
            if plan is None:
                return TaskExecutionSnapshot(attempt=None)
            attempt = self._store.get_active_execution_attempt(plan.task_id)
            return TaskExecutionSnapshot(attempt=attempt) if attempt is None else self._snapshot(attempt)
        attempt = self._require_owned_attempt(session_key=session_key, attempt_id=attempt_id)
        return self._snapshot(attempt)

    def reconcile_attempts(
        self,
        *,
        now: datetime,
        session_key: str | None = None,
    ) -> list[ReconciledExecutionAttempt]:
        return self._store.reconcile_execution_attempts(
            now=now,
            runtime_instance_id=self._runtime_instance_id,
            session_key=session_key,
        )

    def _claim_step(
        self,
        *,
        plan: TaskPlan,
        step: TaskStep,
        session_key: str,
        request_id: str,
        source_turn_id: int | None,
        action: str,
    ) -> BeginExecutionResult:
        try:
            claim = self._store.claim_execution_attempt(
                task_id=plan.task_id,
                step_id=step.step_id,
                session_key=session_key,
                request_id=request_id,
                idempotency_key=derive_task_execution_idempotency_key(
                    session_key=session_key,
                    request_id=request_id,
                    task_id=plan.task_id,
                    step_id=step.step_id,
                    action=action,
                ),
                owner_instance_id=self._runtime_instance_id,
                lease_expires_at=(
                    self._now() + timedelta(seconds=self._config.lease_seconds)
                ).isoformat(),
                source_turn_id=source_turn_id,
            )
        except ExecutionAttemptConflictError as exc:
            raise TaskExecutionConflictError(str(exc)) from exc
        if claim.disposition == "active_conflict":
            raise TaskExecutionConflictError("attempt_already_active")
        claimed_plan = self._require_owned_plan(
            session_key=session_key, task_id=claim.attempt.task_id
        )
        return BeginExecutionResult(
            attempt=claim.attempt,
            step=self._find_step(claimed_plan, claim.attempt.step_id),
            replayed=claim.disposition == "request_replay",
        )

    def _snapshot(self, attempt: TaskExecutionAttempt) -> TaskExecutionSnapshot:
        return TaskExecutionSnapshot(
            attempt=attempt,
            events=tuple(self._store.list_execution_events(attempt.attempt_id)),
        )

    def _require_active_owned_plan(self, *, session_key: str) -> TaskPlan:
        plan = self.plan_service.get_active_task_plan(session_key=session_key)
        if plan is None:
            raise TaskExecutionConflictError("no_active_task_plan")
        return self._require_owned_plan(session_key=session_key, task_id=plan.task_id)

    def _require_owned_plan(self, *, session_key: str, task_id: str) -> TaskPlan:
        try:
            return self.plan_service.require_owned_task_plan(
                session_key=session_key, task_id=task_id
            )
        except TaskPlanAccessDeniedError as exc:
            raise TaskExecutionAccessDeniedError(str(exc)) from exc

    def _require_owned_attempt(
        self, *, session_key: str, attempt_id: str
    ) -> TaskExecutionAttempt:
        attempt = self._store.get_execution_attempt(attempt_id)
        if attempt is None:
            raise TaskExecutionConflictError("execution attempt not found")
        if attempt.session_key != session_key:
            raise TaskExecutionAccessDeniedError(
                "execution attempt does not belong to current session"
            )
        self._require_owned_plan(session_key=session_key, task_id=attempt.task_id)
        return attempt

    @staticmethod
    def _find_step(plan: TaskPlan, step_id: str) -> TaskStep:
        for step in plan.steps:
            if step.step_id == step_id:
                return step
        raise TaskExecutionConflictError("execution attempt step is not in task plan")

    @staticmethod
    def _is_retryable_block(attempt: TaskExecutionAttempt) -> bool:
        return (
            attempt.status == "blocked"
            and attempt.terminal_reason in _RETRYABLE_BLOCK_REASONS
        )

    @classmethod
    def _is_retryable_attempt(cls, attempt: TaskExecutionAttempt) -> bool:
        return attempt.status == "failed" or cls._is_retryable_block(attempt)

    def _has_successful_work_event(self, attempt_id: str) -> bool:
        return any(
            event.event_type == "tool_finished"
            and event.counts_as_work
            and event.tool_risk == "read-only"
            and event.invoker_reached
            and event.invoker_succeeded
            and event.execution_status == "success"
            and event.result_ok is True
            and not event.error_code
            for event in self._store.list_execution_events(attempt_id)
        )
