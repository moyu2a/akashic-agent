from __future__ import annotations

from pathlib import Path

import pytest

from agent.task_plan.service import (
    TaskPlanAccessDeniedError,
    TaskPlanConflictError,
    TaskPlanService,
)
from agent.task_plan.store import TaskPlanStore


def _service(tmp_path: Path) -> TaskPlanService:
    return TaskPlanService(TaskPlanStore(tmp_path / "task_plans.db"))


def test_create_conflict_is_service_error(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.create_task_plan(
        session_key="cli:s1",
        title="One",
        steps=["A"],
    )

    with pytest.raises(TaskPlanConflictError):
        service.create_task_plan(
            session_key="cli:s1",
            title="Two",
            steps=["B"],
        )


def test_update_step_requires_task_session_owner(tmp_path: Path) -> None:
    service = _service(tmp_path)
    plan = service.create_task_plan(
        session_key="cli:s1",
        title="One",
        steps=["A"],
    )

    with pytest.raises(TaskPlanAccessDeniedError):
        service.update_step_status(
            session_key="cli:s2",
            task_id=plan.task_id,
            step_index=1,
            status="completed",
        )


def test_auto_completes_when_all_steps_terminal_success(tmp_path: Path) -> None:
    service = _service(tmp_path)
    plan = service.create_task_plan(
        session_key="cli:s1",
        title="One",
        steps=["A", "B"],
    )

    plan = service.update_step_status(
        session_key="cli:s1",
        task_id=plan.task_id,
        step_index=1,
        status="completed",
    )
    assert plan.status == "active"

    plan = service.update_step_status(
        session_key="cli:s1",
        task_id=plan.task_id,
        step_index=2,
        status="skipped",
    )
    assert plan.status == "completed"
    assert service.get_active_task_plan(session_key="cli:s1") is None


def test_failed_step_does_not_fail_task(tmp_path: Path) -> None:
    service = _service(tmp_path)
    plan = service.create_task_plan(
        session_key="cli:s1",
        title="One",
        steps=["A"],
    )

    plan = service.update_step_status(
        session_key="cli:s1",
        task_id=plan.task_id,
        step_index=1,
        status="failed",
        result_summary="Needs retry",
    )

    assert plan.status == "active"
    assert plan.steps[0].status == "failed"


def test_complete_and_cancel_store_terminal_reason(tmp_path: Path) -> None:
    service = _service(tmp_path)
    first = service.create_task_plan(
        session_key="cli:s1",
        title="One",
        steps=["A"],
    )
    completed = service.complete_task_plan(
        session_key="cli:s1",
        task_id=first.task_id,
        terminal_reason="done",
    )
    assert completed.status == "completed"
    assert completed.terminal_reason == "done"

    second = service.create_task_plan(
        session_key="cli:s1",
        title="Two",
        steps=["B"],
    )
    cancelled = service.cancel_task_plan(
        session_key="cli:s1",
        task_id=second.task_id,
        terminal_reason="replaced",
    )
    assert cancelled.status == "cancelled"
    assert cancelled.terminal_reason == "replaced"


def test_update_requires_step_selector(tmp_path: Path) -> None:
    service = _service(tmp_path)
    plan = service.create_task_plan(session_key="cli:s1", title="One", steps=["A"])

    with pytest.raises(ValueError, match="step_id or step_index"):
        service.update_step_status(
            session_key="cli:s1",
            task_id=plan.task_id,
            status="completed",
        )


def test_step_id_and_index_must_match(tmp_path: Path) -> None:
    service = _service(tmp_path)
    plan = service.create_task_plan(session_key="cli:s1", title="One", steps=["A", "B"])

    with pytest.raises(ValueError, match="same step"):
        service.update_step_status(
            session_key="cli:s1",
            task_id=plan.task_id,
            step_id=plan.steps[0].step_id,
            step_index=2,
            status="completed",
        )


def test_terminal_task_rejects_step_update(tmp_path: Path) -> None:
    service = _service(tmp_path)
    plan = service.create_task_plan(session_key="cli:s1", title="One", steps=["A"])
    service.complete_task_plan(session_key="cli:s1", task_id=plan.task_id)

    with pytest.raises(TaskPlanConflictError, match="terminal"):
        service.update_step_status(
            session_key="cli:s1",
            task_id=plan.task_id,
            step_index=1,
            status="completed",
        )


def test_complete_and_cancel_are_idempotent_for_same_terminal_state(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    first = service.create_task_plan(session_key="cli:s1", title="One", steps=["A"])
    service.complete_task_plan(session_key="cli:s1", task_id=first.task_id)
    completed = service.complete_task_plan(session_key="cli:s1", task_id=first.task_id)
    assert completed.status == "completed"

    second = service.create_task_plan(session_key="cli:s1", title="Two", steps=["B"])
    service.cancel_task_plan(session_key="cli:s1", task_id=second.task_id)
    cancelled = service.cancel_task_plan(session_key="cli:s1", task_id=second.task_id)
    assert cancelled.status == "cancelled"
