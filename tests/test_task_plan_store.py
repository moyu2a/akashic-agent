from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from agent.task_plan.store import ActiveTaskExistsError, TaskPlanStore


def test_create_and_get_active_plan(tmp_path: Path) -> None:
    store = TaskPlanStore(tmp_path / "task_plans.db")

    plan = store.create_plan(
        session_key="cli:s1",
        title="Fix RAG",
        step_titles=["Read logs", "Update docs"],
    )

    active = store.get_active_plan("cli:s1")
    assert active is not None
    assert active.task_id == plan.task_id
    assert [step.title for step in active.steps] == ["Read logs", "Update docs"]


def test_one_active_task_per_session_enforced(tmp_path: Path) -> None:
    store = TaskPlanStore(tmp_path / "task_plans.db")
    store.create_plan(session_key="cli:s1", title="One", step_titles=["A"])

    with pytest.raises(ActiveTaskExistsError):
        store.create_plan(session_key="cli:s1", title="Two", step_titles=["B"])


def test_replace_active_cancels_old_plan_atomically(tmp_path: Path) -> None:
    store = TaskPlanStore(tmp_path / "task_plans.db")
    old = store.create_plan(session_key="cli:s1", title="One", step_titles=["A"])

    new = store.create_plan(
        session_key="cli:s1",
        title="Two",
        step_titles=["B"],
        replace_active=True,
    )

    old_plan = store.get_plan(old.task_id)
    active = store.get_active_plan("cli:s1")
    assert old_plan is not None
    assert active is not None
    assert old_plan.status == "cancelled"
    assert active.task_id == new.task_id


def test_different_sessions_can_each_have_active_plan(tmp_path: Path) -> None:
    store = TaskPlanStore(tmp_path / "task_plans.db")

    one = store.create_plan(session_key="cli:s1", title="One", step_titles=["A"])
    two = store.create_plan(session_key="cli:s2", title="Two", step_titles=["B"])

    active_one = store.get_active_plan("cli:s1")
    active_two = store.get_active_plan("cli:s2")
    assert active_one is not None
    assert active_two is not None
    assert active_one.task_id == one.task_id
    assert active_two.task_id == two.task_id


def test_concurrent_create_active_allows_only_one_winner(tmp_path: Path) -> None:
    store = TaskPlanStore(tmp_path / "task_plans.db")

    def _create(index: int) -> bool:
        try:
            store.create_plan(
                session_key="cli:s1",
                title=f"Task {index}",
                step_titles=["A"],
            )
            return True
        except ActiveTaskExistsError:
            return False

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(_create, range(4)))

    assert results.count(True) == 1
    assert results.count(False) == 3


def test_update_step_by_index_orders_steps(tmp_path: Path) -> None:
    store = TaskPlanStore(tmp_path / "task_plans.db")
    plan = store.create_plan(
        session_key="cli:s1",
        title="Fix RAG",
        step_titles=["Read logs", "Update docs"],
    )

    updated = store.update_step(
        task_id=plan.task_id,
        step_index=1,
        status="completed",
        result_summary="Logs reviewed",
        tool_names=["inspect_turn_trace"],
    )

    assert updated.steps[0].status == "completed"
    assert updated.steps[0].result_summary == "Logs reviewed"
    assert updated.steps[0].tool_names == ["inspect_turn_trace"]


def test_set_task_status_marks_terminal_reason(tmp_path: Path) -> None:
    store = TaskPlanStore(tmp_path / "task_plans.db")
    plan = store.create_plan(session_key="cli:s1", title="Fix RAG", step_titles=["A"])

    updated = store.set_task_status(
        task_id=plan.task_id,
        status="cancelled",
        terminal_reason="replaced",
    )

    assert updated.status == "cancelled"
    assert updated.terminal_reason == "replaced"
    assert updated.completed_at is not None
