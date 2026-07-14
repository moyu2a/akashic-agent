from __future__ import annotations

import json
from typing import Any

from agent.task_plan.service import (
    TaskPlanAccessDeniedError,
    TaskPlanConflictError,
    TaskPlanService,
)
from agent.tools.base import Tool


class CreateTaskPlanTool(Tool):
    name = "create_task_plan"
    capabilities = frozenset({"task_plan.create"})
    description = (
        "为当前 session 创建一个 TaskPlan 任务计划状态，适用于制定多步骤工作"
        "计划、记录开发任务步骤和后续进度追踪。只创建计划，不执行步骤，不读取"
        "文件，不检索文档，不启动后台任务。创建成功后应直接向用户确认计划。"
        "如果用户要求三步计划，steps 应为 3 项。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "任务标题",
                "minLength": 1,
            },
            "steps": {
                "type": "array",
                "description": "任务步骤标题列表；数量应遵循用户明确要求",
                "items": {"type": "string", "minLength": 1},
                "minItems": 1,
            },
            "replace_active": {
                "type": "boolean",
                "description": "是否取消当前 active task 并创建新任务",
                "default": False,
            },
        },
        "required": ["title", "steps"],
    }

    def __init__(self, service: TaskPlanService) -> None:
        self._service = service

    async def execute(
        self,
        title: str,
        steps: list[str],
        replace_active: bool = False,
        _session_key: str | None = None,
        **_: Any,
    ) -> str:
        session_key = _clean_session(_session_key)
        if not session_key:
            return _error(
                "missing_session_context",
                "create_task_plan requires protected current-session context.",
            )
        try:
            plan = self._service.create_task_plan(
                session_key=session_key,
                title=title,
                steps=steps,
                replace_active=bool(replace_active),
            )
        except Exception as exc:
            return _service_error(exc)
        return _ok(plan)


class UpdateTaskStepTool(Tool):
    name = "update_task_step"
    capabilities = frozenset({"task_plan.update"})
    description = (
        "更新当前 session 中某个 TaskPlan 步骤的状态、结果摘要和相关工具名。"
        "只用于显式任务进度追踪，不用于执行任务本身，不启动后台任务。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "任务 id",
                "minLength": 1,
            },
            "step_id": {
                "type": "string",
                "description": "步骤 id；可与 step_index 二选一",
                "minLength": 1,
            },
            "step_index": {
                "type": "integer",
                "description": "步骤序号，从 1 开始；可与 step_id 二选一",
                "minimum": 1,
            },
            "status": {
                "type": "string",
                "enum": ["pending", "in_progress", "completed", "failed", "skipped"],
                "description": "步骤状态",
            },
            "result_summary": {
                "type": "string",
                "description": "步骤结果摘要",
            },
            "tool_names": {
                "type": "array",
                "description": "本步骤相关工具名",
                "items": {"type": "string"},
            },
        },
        "required": ["task_id", "status"],
    }

    def __init__(self, service: TaskPlanService) -> None:
        self._service = service

    async def execute(
        self,
        task_id: str,
        status: str,
        step_id: str | None = None,
        step_index: int | None = None,
        result_summary: str = "",
        tool_names: list[str] | None = None,
        _session_key: str | None = None,
        **_: Any,
    ) -> str:
        session_key = _clean_session(_session_key)
        if not session_key:
            return _error(
                "missing_session_context",
                "update_task_step requires protected current-session context.",
            )
        try:
            plan = self._service.update_step_status(
                session_key=session_key,
                task_id=task_id,
                step_id=step_id,
                step_index=step_index,
                status=status,
                result_summary=result_summary,
                tool_names=tool_names,
            )
        except Exception as exc:
            return _service_error(exc)
        return _ok(plan)


class InspectTaskPlanTool(Tool):
    name = "inspect_task_plan"
    capabilities = frozenset({"task_plan.inspect"})
    description = (
        "查看当前 session 的 TaskPlan active task plan，或查看指定 task_id 的当前 "
        "session 任务计划。用于回答当前任务、步骤、进度、下一步。"
        "当用户说当前任务、进度、做到哪一步或下一步时，默认优先使用本工具。"
        "只有用户明确说后台任务、job、subagent、spawn、后台输出或后台任务输出"
        "时，才考虑 spawn_manage 或 task_output。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "可选任务 id；未传时返回当前 active task",
                "minLength": 1,
            },
        },
        "required": [],
    }

    def __init__(self, service: TaskPlanService) -> None:
        self._service = service

    async def execute(
        self,
        task_id: str | None = None,
        _session_key: str | None = None,
        **_: Any,
    ) -> str:
        session_key = _clean_session(_session_key)
        if not session_key:
            return _error(
                "missing_session_context",
                "inspect_task_plan requires protected current-session context.",
            )
        try:
            if task_id:
                plan = self._service.get_task_plan(
                    session_key=session_key,
                    task_id=task_id,
                )
            else:
                plan = self._service.get_active_task_plan(session_key=session_key)
        except Exception as exc:
            return _service_error(exc)
        if plan is None:
            return _error("task_not_found", "No task plan found for current session.")
        return _ok(plan)


def _ok(plan) -> str:
    return _json_dump({"ok": True, "error_code": "", "task": plan.to_dict()})


def _service_error(exc: Exception) -> str:
    if isinstance(exc, TaskPlanConflictError):
        return _error("active_task_exists", str(exc))
    if isinstance(exc, TaskPlanAccessDeniedError):
        return _error("task_not_found", str(exc))
    if isinstance(exc, ValueError):
        return _error("invalid_request", str(exc))
    return _error("task_plan_error", str(exc))


def _error(code: str, message: str) -> str:
    return _json_dump({"ok": False, "error_code": code, "message": message})


def _json_dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _clean_session(session_key: str | None) -> str:
    return str(session_key or "").strip()
