from __future__ import annotations

from agent.task_plan.models import StepStatus, TaskPlan, validate_step_status
from agent.task_plan.store import (
    ActiveExecutionAttemptExistsError,
    ActiveTaskExistsError,
    TaskPlanNotFoundError,
    TaskPlanStore,
    TaskStepNotFoundError,
)


class TaskPlanError(RuntimeError):
    pass


class TaskPlanConflictError(TaskPlanError):
    pass


class TaskPlanAccessDeniedError(TaskPlanError):
    pass


class TaskPlanService:
    def __init__(self, store: TaskPlanStore) -> None:
        self._store = store

    @property
    def store(self) -> TaskPlanStore:
        return self._store

    def create_task_plan(
        self,
        *,
        session_key: str,
        title: str,
        steps: list[str],
        source_turn_id: int | None = None,
        replace_active: bool = False,
    ) -> TaskPlan:
        clean_session = _require_text(session_key, "session_key")
        clean_title = _require_text(title, "title")
        clean_steps = [_require_text(step, "step") for step in steps]
        if not clean_steps:
            raise ValueError("steps must not be empty")
        try:
            return self._store.create_plan(
                session_key=clean_session,
                title=clean_title,
                step_titles=clean_steps,
                source_turn_id=source_turn_id,
                replace_active=replace_active,
            )
        except ActiveTaskExistsError as exc:
            raise TaskPlanConflictError("active task already exists") from exc
        except ActiveExecutionAttemptExistsError as exc:
            raise TaskPlanConflictError("active execution attempt exists") from exc

    def get_active_task_plan(self, *, session_key: str) -> TaskPlan | None:
        return self._store.get_active_plan(_require_text(session_key, "session_key"))

    def get_task_plan(self, *, session_key: str, task_id: str) -> TaskPlan | None:
        try:
            return self._require_owned_plan(session_key=session_key, task_id=task_id)
        except TaskPlanAccessDeniedError:
            return None

    def update_step_status(
        self,
        *,
        session_key: str,
        task_id: str,
        status: StepStatus | str,
        step_id: str | None = None,
        step_index: int | None = None,
        result_summary: str = "",
        tool_names: list[str] | None = None,
        source_turn_id: int | None = None,
    ) -> TaskPlan:
        status = validate_step_status(str(status))
        plan = self._require_owned_plan(session_key=session_key, task_id=task_id)
        if plan.status != "active":
            raise TaskPlanConflictError("cannot update terminal task")
        self._resolve_step_selector(plan, step_id=step_id, step_index=step_index)
        try:
            updated = self._store.update_step(
                task_id=plan.task_id,
                step_id=step_id,
                step_index=step_index,
                status=status,
                result_summary=result_summary,
                tool_names=tool_names,
                source_turn_id=source_turn_id,
            )
        except TaskStepNotFoundError as exc:
            raise ValueError("step_id or step_index does not match a task step") from exc
        except ActiveExecutionAttemptExistsError as exc:
            raise TaskPlanConflictError("active execution attempt exists") from exc

        if updated.steps and all(
            step.status in {"completed", "skipped"} for step in updated.steps
        ):
            return self._store.set_task_status(
                task_id=updated.task_id,
                status="completed",
                terminal_reason="all_steps_terminal",
            )
        return updated

    def complete_task_plan(
        self,
        *,
        session_key: str,
        task_id: str,
        terminal_reason: str = "",
    ) -> TaskPlan:
        plan = self._require_owned_plan(session_key=session_key, task_id=task_id)
        if plan.status == "completed":
            return plan
        if plan.status in {"cancelled", "failed"}:
            raise TaskPlanConflictError("task is already terminal")
        try:
            return self._store.set_task_status(
                task_id=plan.task_id,
                status="completed",
                terminal_reason=terminal_reason,
            )
        except ActiveExecutionAttemptExistsError as exc:
            raise TaskPlanConflictError("active execution attempt exists") from exc

    def cancel_task_plan(
        self,
        *,
        session_key: str,
        task_id: str,
        terminal_reason: str = "",
    ) -> TaskPlan:
        plan = self._require_owned_plan(session_key=session_key, task_id=task_id)
        if plan.status == "cancelled":
            return plan
        if plan.status in {"completed", "failed"}:
            raise TaskPlanConflictError("task is already terminal")
        try:
            return self._store.set_task_status(
                task_id=plan.task_id,
                status="cancelled",
                terminal_reason=terminal_reason,
            )
        except ActiveExecutionAttemptExistsError as exc:
            raise TaskPlanConflictError("active execution attempt exists") from exc

    def require_owned_task_plan(self, *, session_key: str, task_id: str) -> TaskPlan:
        return self._require_owned_plan(session_key=session_key, task_id=task_id)

    def _require_owned_plan(self, *, session_key: str, task_id: str) -> TaskPlan:
        clean_session = _require_text(session_key, "session_key")
        clean_task_id = _require_text(task_id, "task_id")
        try:
            plan = self._store.get_plan(clean_task_id)
        except TaskPlanNotFoundError as exc:
            raise TaskPlanAccessDeniedError(
                "task not found for current session"
            ) from exc
        if plan is None:
            raise TaskPlanAccessDeniedError("task not found for current session")
        if plan.session_key != clean_session:
            raise TaskPlanAccessDeniedError("task does not belong to current session")
        return plan

    @staticmethod
    def _resolve_step_selector(
        plan: TaskPlan,
        *,
        step_id: str | None,
        step_index: int | None,
    ) -> None:
        if not step_id and step_index is None:
            raise ValueError("step_id or step_index is required")
        by_id = {step.step_id: step for step in plan.steps}
        by_index = {step.index: step for step in plan.steps}
        selected_by_id = by_id.get(step_id) if step_id else None
        selected_by_index = by_index.get(step_index) if step_index is not None else None
        if step_id and selected_by_id is None:
            raise ValueError("step_id does not match a task step")
        if step_index is not None and selected_by_index is None:
            raise ValueError("step_index does not match a task step")
        if (
            selected_by_id is not None
            and selected_by_index is not None
            and selected_by_id.step_id != selected_by_index.step_id
        ):
            raise ValueError("step_id and step_index must refer to the same step")


def _require_text(value: str, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must not be empty")
    return clean
