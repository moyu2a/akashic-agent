from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, cast
from uuid import uuid4

TaskStatus = Literal["active", "completed", "cancelled", "failed"]
StepStatus = Literal["pending", "in_progress", "completed", "failed", "skipped"]

TASK_STATUSES: frozenset[str] = frozenset(
    {"active", "completed", "cancelled", "failed"}
)
STEP_STATUSES: frozenset[str] = frozenset(
    {"pending", "in_progress", "completed", "failed", "skipped"}
)


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def new_task_id() -> str:
    return f"task_{uuid4().hex}"


def new_step_id() -> str:
    return f"step_{uuid4().hex}"


def validate_task_status(status: str) -> TaskStatus:
    if status not in TASK_STATUSES:
        raise ValueError(f"invalid task status: {status}")
    return cast(TaskStatus, status)


def validate_step_status(status: str) -> StepStatus:
    if status not in STEP_STATUSES:
        raise ValueError(f"invalid step status: {status}")
    return cast(StepStatus, status)


@dataclass
class TaskStep:
    step_id: str
    task_id: str
    index: int
    title: str
    status: StepStatus
    tool_names: list[str] = field(default_factory=list)
    result_summary: str = ""
    source_turn_id: int | None = None
    started_at: str | None = None
    completed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "task_id": self.task_id,
            "index": self.index,
            "title": self.title,
            "status": self.status,
            "tool_names": list(self.tool_names),
            "result_summary": self.result_summary,
            "source_turn_id": self.source_turn_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": dict(self.metadata),
        }


@dataclass
class TaskPlan:
    task_id: str
    session_key: str
    title: str
    status: TaskStatus
    steps: list[TaskStep]
    created_at: str
    updated_at: str
    completed_at: str | None = None
    source_turn_id: int | None = None
    terminal_reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        ordered_steps = sorted(self.steps, key=lambda step: step.index)
        return {
            "task_id": self.task_id,
            "session_key": self.session_key,
            "title": self.title,
            "status": self.status,
            "steps": [step.to_dict() for step in ordered_steps],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "source_turn_id": self.source_turn_id,
            "terminal_reason": self.terminal_reason,
            "metadata": dict(self.metadata),
        }
