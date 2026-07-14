from __future__ import annotations

import pytest

from agent.task_plan.models import (
    TaskPlan,
    TaskStep,
    new_step_id,
    new_task_id,
    validate_step_status,
    validate_task_status,
)


def test_task_ids_have_task_prefix() -> None:
    assert new_task_id().startswith("task_")


def test_step_ids_have_step_prefix() -> None:
    assert new_step_id().startswith("step_")


def test_status_validation_accepts_known_values() -> None:
    assert validate_task_status("active") == "active"
    assert validate_step_status("completed") == "completed"


def test_status_validation_rejects_unknown_values() -> None:
    with pytest.raises(ValueError, match="invalid task status"):
        validate_task_status("running")
    with pytest.raises(ValueError, match="invalid step status"):
        validate_step_status("done")


def test_task_plan_to_dict_contains_ordered_steps() -> None:
    later = TaskStep(
        step_id="step_2",
        task_id="task_1",
        index=2,
        title="Run tests",
        status="pending",
    )
    earlier = TaskStep(
        step_id="step_1",
        task_id="task_1",
        index=1,
        title="Read logs",
        status="pending",
    )
    plan = TaskPlan(
        task_id="task_1",
        session_key="cli:s1",
        title="Fix bug",
        status="active",
        steps=[later, earlier],
        created_at="2026-07-14T00:00:00+00:00",
        updated_at="2026-07-14T00:00:00+00:00",
    )

    payload = plan.to_dict()

    assert payload["task_id"] == "task_1"
    assert payload["steps"][0]["step_id"] == "step_1"
    assert payload["steps"][0]["index"] == 1
