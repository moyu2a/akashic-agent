from __future__ import annotations

from typing import Any

from agent.task_plan.execution_models import TaskExecutionSnapshot
from agent.task_plan.execution_service import (
    TaskExecutionAccessDeniedError,
    TaskExecutionConflictError,
    TaskExecutionError,
    TaskExecutionService,
)
from agent.task_plan.orchestrator import (
    ExecutionOrchestrationDecision,
    TaskExecutionOrchestrator,
)
from agent.tools.base import Tool, ToolResult


class _ExecutionTool(Tool):
    def __init__(self, service: TaskExecutionService) -> None:
        self._service = service


class BeginTaskStepExecutionTool(Tool):
    name = "begin_task_step_execution"
    description = (
        "Claim exactly one current TaskPlan step for controlled execution. "
        "This does not authorize write, shell, or external side effects."
    )
    capabilities = frozenset({"task_execution.begin"})
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def __init__(self, orchestrator: TaskExecutionOrchestrator) -> None:
        self._orchestrator = orchestrator

    async def execute(
        self,
        *,
        _session_key: str = "",
        _task_execution_request_id: str = "",
        _task_execution_action: str = "",
        _task_execution_target_step_id: str = "",
        _tool_execution_context_active: bool = False,
        **_: Any,
    ) -> ToolResult:
        if not _tool_execution_context_active:
            return _error(
                "missing_execution_context", "Missing per-call execution context."
            )
        session_key = str(_session_key or "").strip()
        request_id = str(_task_execution_request_id or "").strip()
        action = str(_task_execution_action or "").strip()
        if not session_key:
            return _error(
                "missing_session_context", "Missing protected session context."
            )
        if not request_id:
            return _error(
                "missing_execution_request", "Missing protected execution request."
            )
        if action not in {"continue", "retry"}:
            return _error(
                "missing_execution_action", "Missing protected execution action."
            )
        if action == "retry" and not str(_task_execution_target_step_id or "").strip():
            return _error(
                "missing_retry_target", "Retry requires a protected target step."
            )
        try:
            if action == "retry":
                decision = self._orchestrator.decide_retry(
                    session_key=session_key,
                    request_id=request_id,
                    step_id=str(_task_execution_target_step_id),
                )
            else:
                decision = self._orchestrator.decide_continue(
                    session_key=session_key,
                    request_id=request_id,
                )
        except Exception as exc:
            return _service_error(exc)
        return _result(decision=decision)


class FinishTaskStepExecutionTool(_ExecutionTool):
    name = "finish_task_step_execution"
    description = "Finish the protected current execution attempt after verified work."
    capabilities = frozenset({"task_execution.finish"})
    parameters = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "result_summary": {"type": "string"},
            "error_code": {"type": "string"},
        },
        "required": ["success", "result_summary"],
    }

    async def execute(
        self,
        *,
        success: bool,
        result_summary: str,
        error_code: str = "",
        _session_key: str = "",
        _task_execution_attempt_id: str = "",
        _tool_execution_context_active: bool = False,
        **_: Any,
    ) -> ToolResult:
        context = _attempt_context(
            _session_key,
            _task_execution_attempt_id,
            active=_tool_execution_context_active,
        )
        if isinstance(context, ToolResult):
            return context
        try:
            snapshot = self._service.finish_attempt(
                session_key=context[0],
                attempt_id=context[1],
                success=success,
                result_summary=result_summary,
                error_code=error_code,
            )
        except Exception as exc:
            return _service_error(exc)
        return _result(snapshot=snapshot)


class RequestTaskStepAuthorizationTool(_ExecutionTool):
    name = "request_task_step_authorization"
    description = (
        "Defer the protected attempt until requested side effects are authorized."
    )
    capabilities = frozenset({"task_execution.defer"})
    parameters = {
        "type": "object",
        "properties": {
            "tool_name": {"type": "string"},
            "requested_arguments": {"type": "object"},
            "requested_capabilities": {"type": "array", "items": {"type": "string"}},
            "reason": {"type": "string"},
        },
        "required": [
            "tool_name",
            "requested_arguments",
            "requested_capabilities",
            "reason",
        ],
    }

    async def execute(
        self,
        *,
        tool_name: str,
        requested_arguments: dict[str, object],
        requested_capabilities: list[str],
        reason: str,
        _session_key: str = "",
        _task_execution_attempt_id: str = "",
        _tool_execution_context_active: bool = False,
        **_: Any,
    ) -> ToolResult:
        context = _attempt_context(
            _session_key,
            _task_execution_attempt_id,
            active=_tool_execution_context_active,
        )
        if isinstance(context, ToolResult):
            return context
        try:
            snapshot = self._service.defer_attempt(
                session_key=context[0],
                attempt_id=context[1],
                tool_name=tool_name,
                requested_arguments=requested_arguments,
                requested_capabilities=tuple(requested_capabilities),
                reason=reason,
            )
        except Exception as exc:
            return _service_error(exc)
        return _result(snapshot=snapshot)


class InspectTaskExecutionTool(_ExecutionTool):
    name = "inspect_task_execution"
    description = "Inspect the protected current TaskPlan execution attempt."
    capabilities = frozenset({"task_execution.inspect"})
    parameters = {"type": "object", "properties": {}, "required": []}

    async def execute(
        self,
        *,
        _session_key: str = "",
        _task_execution_attempt_id: str = "",
        _tool_execution_context_active: bool = False,
        **_: Any,
    ) -> ToolResult:
        if not _tool_execution_context_active:
            return _error(
                "missing_execution_context", "Missing per-call execution context."
            )
        try:
            snapshot = self._service.inspect(
                session_key=str(_session_key or ""),
                attempt_id=str(_task_execution_attempt_id or "") or None,
            )
        except Exception as exc:
            return _service_error(exc)
        return _result(snapshot=snapshot)


class AbortTaskStepExecutionTool(_ExecutionTool):
    name = "abort_task_step_execution"
    description = "Abort the protected current execution attempt."
    capabilities = frozenset({"task_execution.abort"})
    parameters = {
        "type": "object",
        "properties": {"reason": {"type": "string"}},
        "required": ["reason"],
    }

    async def execute(
        self,
        *,
        reason: str,
        _session_key: str = "",
        _task_execution_attempt_id: str = "",
        _tool_execution_context_active: bool = False,
        **_: Any,
    ) -> ToolResult:
        context = _attempt_context(
            _session_key,
            _task_execution_attempt_id,
            active=_tool_execution_context_active,
        )
        if isinstance(context, ToolResult):
            return context
        try:
            snapshot = self._service.abort_attempt(
                session_key=context[0], attempt_id=context[1], reason=reason
            )
        except Exception as exc:
            return _service_error(exc)
        return _result(snapshot=snapshot)


def _attempt_context(
    session_key: str, attempt_id: str, *, active: bool
) -> tuple[str, str] | ToolResult:
    if not active:
        return _error(
            "missing_execution_context", "Missing per-call execution context."
        )
    clean_session = str(session_key or "").strip()
    clean_attempt = str(attempt_id or "").strip()
    if not clean_session:
        return _error("missing_session_context", "Missing protected session context.")
    if not clean_attempt:
        return _error(
            "missing_execution_attempt", "Missing protected execution attempt."
        )
    return clean_session, clean_attempt


def _result(
    *,
    snapshot: TaskExecutionSnapshot | None = None,
    decision: ExecutionOrchestrationDecision | None = None,
) -> ToolResult:
    effective_snapshot = snapshot or (
        decision.snapshot if decision is not None else None
    )
    attempt = (
        effective_snapshot.attempt.to_dict()
        if effective_snapshot and effective_snapshot.attempt
        else None
    )
    events = (
        [_event_to_dict(event) for event in effective_snapshot.events]
        if effective_snapshot
        else []
    )
    payload: dict[str, object] = {
        "ok": True,
        "error_code": "",
        "attempt": attempt,
        "events": events,
        "decision": (
            {
                "action": decision.action,
                "reason": decision.reason,
            }
            if decision is not None
            else None
        ),
    }
    return ToolResult(ok=True, error_code="", text=_json(payload))


def _event_to_dict(event: object) -> dict[str, object]:
    values = getattr(event, "__dict__", {})
    return {str(key): value for key, value in values.items()}


def _service_error(exc: Exception) -> ToolResult:
    if isinstance(exc, TaskExecutionAccessDeniedError):
        return _error("execution_access_denied", str(exc))
    if isinstance(exc, TaskExecutionConflictError):
        return _error("execution_conflict", str(exc))
    if isinstance(exc, ValueError):
        return _error("invalid_request", str(exc))
    if isinstance(exc, TaskExecutionError):
        return _error("task_execution_error", str(exc))
    return _error("task_execution_error", str(exc))


def _error(error_code: str, message: str) -> ToolResult:
    return ToolResult(
        ok=False,
        error_code=error_code,
        text=_json(
            {
                "ok": False,
                "error_code": error_code,
                "attempt": None,
                "events": [],
                "decision": None,
                "message": message,
            }
        ),
    )


def _json(payload: dict[str, object]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, default=str)
