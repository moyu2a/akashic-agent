from __future__ import annotations

from typing import Any

from agent.prompting import PromptSectionRender
from agent.task_plan.models import TaskPlan, TaskStep
from agent.task_plan.execution_models import TaskExecutionSnapshot
from agent.task_plan.execution_service import TaskExecutionService
from agent.task_plan.service import TaskPlanService


class TaskPlanPromptRenderModule:
    slot = "task_plan.prompt_context"
    requires = ("prompt_render.emit", "prompt:ctx")
    produces = ("prompt:section_bottom:task_plan",)

    def __init__(
        self,
        service: TaskPlanService,
        execution_service: TaskExecutionService | None = None,
        max_chars: int = 1200,
        max_execution_chars: int = 400,
    ) -> None:
        self._service = service
        self._execution_service = execution_service
        self._max_chars = max_chars
        self._max_execution_chars = max_execution_chars

    async def run(self, frame: Any) -> Any:
        ctx = frame.slots.get("prompt:ctx")
        session_key = str(getattr(ctx, "session_key", "") or "")
        if not session_key:
            return frame
        plan = self._service.get_active_task_plan(session_key=session_key)
        if plan is None:
            return frame
        execution = (
            self._execution_service.inspect(session_key=session_key)
            if self._execution_service is not None
            else None
        )
        content = render_task_plan_context(
            plan,
            max_chars=self._max_chars,
            execution=execution,
            max_execution_chars=self._max_execution_chars,
        )
        if not content.strip():
            return frame
        frame.slots["prompt:section_bottom:task_plan"] = PromptSectionRender(
            name="task_plan",
            content=content,
            is_static=False,
        )
        return frame


def render_task_plan_context(
    plan: TaskPlan,
    max_chars: int = 1200,
    *,
    execution: TaskExecutionSnapshot | None = None,
    max_execution_chars: int = 400,
) -> str:
    ordered = sorted(plan.steps, key=lambda step: step.index)
    current = _current_step(ordered)
    next_step = _next_pending_step(ordered, current)
    recent_result = _recent_result(ordered)
    lines = [
        "当前任务计划：",
        f"- task_id: {plan.task_id}",
        f"- title: {_truncate(plan.title, 180)}",
        f"- status: {plan.status}",
    ]
    if current is not None:
        lines.append(f"- current_step: {_format_step(current)}")
    if next_step is not None:
        lines.append(f"- next_step: {_format_step(next_step)}")
    if recent_result:
        lines.append(f"- recent_result: {_truncate(recent_result, 240)}")
    lines.extend(
        [
            "",
            "规则：",
            "- 当前任务计划来自 TaskPlan，不等同于后台 spawn job。",
            "- 如果用户询问当前任务、任务进度或下一步，优先基于此 TaskPlan 回答。",
            "- 如果本轮只是创建、查看或更新计划状态，完成后不要继续调用工具。",
            "- 不要因为存在 TaskPlan 就自动执行步骤；不要自动启动后台任务。",
            "- 如果本轮推进了某个步骤，完成后更新对应 step 状态。",
            "- 不要跳过 pending 步骤，除非用户明确要求。",
        ]
    )
    content = _truncate("\n".join(lines), max_chars)
    execution_content = render_task_execution_context(
        execution, max_chars=max_execution_chars
    )
    return f"{content}\n\n{execution_content}" if execution_content else content


def render_task_execution_context(
    snapshot: TaskExecutionSnapshot | None,
    *,
    max_chars: int = 400,
) -> str:
    if snapshot is None or snapshot.attempt is None:
        return ""
    attempt = snapshot.attempt
    lines = [
        "Execution:",
        f"- attempt_id: {attempt.attempt_id}",
        f"- status: {attempt.status}",
        f"- step_id: {attempt.step_id}",
    ]
    if attempt.error_code:
        lines.append(f"- error_code: {_truncate(attempt.error_code, 120)}")
    if attempt.terminal_reason:
        lines.append(f"- reason: {_truncate(attempt.terminal_reason, 160)}")
    return _truncate("\n".join(lines), max_chars)


def _current_step(steps: list[TaskStep]) -> TaskStep | None:
    for step in steps:
        if step.status == "in_progress":
            return step
    for step in steps:
        if step.status == "pending":
            return step
    return steps[-1] if steps else None


def _next_pending_step(
    steps: list[TaskStep],
    current: TaskStep | None,
) -> TaskStep | None:
    if current is None:
        return None
    for step in steps:
        if step.index > current.index and step.status == "pending":
            return step
    return None


def _recent_result(steps: list[TaskStep]) -> str:
    for step in reversed(steps):
        if step.result_summary.strip():
            return step.result_summary.strip()
    return ""


def _format_step(step: TaskStep) -> str:
    return (
        f"[{step.status}] #{step.index} {step.step_id} " f"{_truncate(step.title, 180)}"
    )


def _truncate(text: str, limit: int) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 3)].rstrip() + "..."
