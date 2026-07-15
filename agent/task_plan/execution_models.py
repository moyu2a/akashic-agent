from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Literal, cast
from uuid import uuid4

from agent.task_plan.models import utc_now_iso

AttemptStatus = Literal[
    "pending",
    "running",
    "waiting_authorization",
    "succeeded",
    "failed",
    "blocked",
    "cancelled",
]
ExecutionMode = Literal["read_only_auto", "authorization_required"]
AttemptClaimDisposition = Literal[
    "created",
    "request_replay",
    "active_conflict",
]
ExecutionEventType = Literal[
    "attempt_claimed",
    "attempt_started",
    "tool_started",
    "tool_finished",
    "authorization_deferred",
    "attempt_succeeded",
    "attempt_failed",
    "attempt_blocked",
    "attempt_cancelled",
    "recovery_reconciled",
]

ACTIVE_ATTEMPT_STATUSES = frozenset({"pending", "running", "waiting_authorization"})
TERMINAL_ATTEMPT_STATUSES = frozenset({"succeeded", "failed", "blocked", "cancelled"})
_TRANSITIONS = {
    "pending": frozenset({"running", "waiting_authorization", "blocked", "cancelled"}),
    "running": frozenset(
        {
            "waiting_authorization",
            "succeeded",
            "failed",
            "blocked",
            "cancelled",
        }
    ),
    "waiting_authorization": frozenset({"cancelled"}),
    "succeeded": frozenset(),
    "failed": frozenset(),
    "blocked": frozenset(),
    "cancelled": frozenset(),
}


def new_attempt_id() -> str:
    return f"attempt_{uuid4().hex}"


def validate_attempt_status(value: str) -> AttemptStatus:
    if value not in _TRANSITIONS:
        raise ValueError(f"invalid attempt status: {value}")
    return cast(AttemptStatus, value)


def validate_attempt_transition(current: str, target: str) -> AttemptStatus:
    source = validate_attempt_status(current)
    destination = validate_attempt_status(target)
    if source in TERMINAL_ATTEMPT_STATUSES:
        raise ValueError("terminal attempt cannot transition")
    if destination not in _TRANSITIONS[source]:
        raise ValueError(f"invalid attempt transition: {source} -> {destination}")
    return destination


@dataclass(frozen=True)
class TaskExecutionAttempt:
    attempt_id: str
    task_id: str
    step_id: str
    session_key: str
    request_id: str
    idempotency_key: str
    attempt_no: int
    status: AttemptStatus
    execution_mode: ExecutionMode
    owner_instance_id: str
    lease_expires_at: str
    source_turn_id: int | None
    requested_tool_name: str
    requested_arguments: dict[str, Any]
    requested_capabilities: tuple[str, ...]
    result_summary: str
    error_code: str
    terminal_reason: str
    created_at: str
    started_at: str | None
    updated_at: str
    finished_at: str | None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new(
        cls,
        *,
        task_id: str,
        step_id: str,
        session_key: str,
        request_id: str,
        idempotency_key: str,
        attempt_no: int,
        owner_instance_id: str,
        lease_expires_at: str,
        source_turn_id: int | None = None,
    ) -> TaskExecutionAttempt:
        now = utc_now_iso()
        return cls(
            attempt_id=new_attempt_id(),
            task_id=task_id,
            step_id=step_id,
            session_key=session_key,
            request_id=request_id,
            idempotency_key=idempotency_key,
            attempt_no=attempt_no,
            status="pending",
            execution_mode="read_only_auto",
            owner_instance_id=owner_instance_id,
            lease_expires_at=lease_expires_at,
            source_turn_id=source_turn_id,
            requested_tool_name="",
            requested_arguments={},
            requested_capabilities=(),
            result_summary="",
            error_code="",
            terminal_reason="",
            created_at=now,
            started_at=None,
            updated_at=now,
            finished_at=None,
            metadata={},
        )

    def to_dict(self) -> dict[str, Any]:
        payload = deepcopy(self.__dict__)
        payload["requested_capabilities"] = list(self.requested_capabilities)
        return payload


@dataclass(frozen=True)
class TaskExecutionEvent:
    event_id: str
    attempt_id: str
    sequence_no: int
    event_type: ExecutionEventType
    tool_name: str
    tool_call_id: str
    source_turn_id: int | None
    tool_risk: str
    tool_capabilities: tuple[str, ...]
    counts_as_work: bool
    invoker_reached: bool
    invoker_succeeded: bool
    execution_status: str
    result_ok: bool | None
    error_code: str
    arguments_hash: str
    result_preview: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeToolEvent:
    event_type: Literal["tool_started", "tool_finished"]
    tool_name: str
    tool_call_id: str
    source_turn_id: int | None
    tool_risk: str
    tool_capabilities: tuple[str, ...]
    counts_as_work: bool
    invoker_reached: bool
    invoker_succeeded: bool
    execution_status: str
    result_ok: bool | None
    error_code: str
    arguments_hash: str
    result_preview: str


@dataclass(frozen=True)
class TaskExecutionSnapshot:
    attempt: TaskExecutionAttempt | None
    events: tuple[TaskExecutionEvent, ...] = ()


@dataclass(frozen=True)
class AttemptClaimResult:
    attempt: TaskExecutionAttempt
    disposition: AttemptClaimDisposition
