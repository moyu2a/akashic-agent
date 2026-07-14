from __future__ import annotations

from typing import Any

from agent.prompting import PromptSectionRender
from agent.task_plan.models import TaskPlan, TaskStep
from agent.task_plan.service import TaskPlanService


class TaskPlanPromptRenderModule:
    slot = "task_plan.prompt_context"
    requires = ("prompt_render.emit", "prompt:ctx")
    produces = ("prompt:section_bottom:task_plan",)

    def __init__(self, service: TaskPlanService, max_chars: int = 1200) -> None:
        self._service = service
        self._max_chars = max_chars

    async def run(self, frame: Any) -> Any:
        ctx = frame.slots.get("prompt:ctx")
        session_key = str(getattr(ctx, "session_key", "") or "")
        if not session_key:
            return frame
        plan = self._service.get_active_task_plan(session_key=session_key)
        if plan is None:
            return frame
        content = render_task_plan_context(plan, max_chars=self._max_chars)
        if not content.strip():
            return frame
        frame.slots["prompt:section_bottom:task_plan"] = PromptSectionRender(
            name="task_plan",
            content=content,
            is_static=False,
        )
        return frame


def render_task_plan_context(plan: TaskPlan, max_chars: int = 1200) -> str:
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
    content = "\n".join(lines)
    if len(content) <= max_chars:
        return content
    return content[: max(0, max_chars - 3)].rstrip() + "..."


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
        f"[{step.status}] #{step.index} {step.step_id} "
        f"{_truncate(step.title, 180)}"
    )


def _truncate(text: str, limit: int) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 3)].rstrip() + "..."
