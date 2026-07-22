from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

HookEvent = Literal["pre_tool_use", "post_tool_use", "post_tool_error"]
ToolSource = Literal["passive", "proactive", "subagent"]
ToolExecStatus = Literal["success", "denied", "deferred", "error"]
HookDecision = Literal["pass", "deny"]


@dataclass
class ToolExecutionRequest:
    call_id: str
    tool_name: str
    arguments: dict[str, Any]
    source: ToolSource
    session_key: str = ""
    channel: str = ""
    chat_id: str = ""
    request_text: str = ""
    tool_batch: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    tool_batch_index: int = 0
    registered: bool = True
    registry_risk: str = "unknown"
    registry_capabilities: frozenset[str] = field(default_factory=frozenset)
    task_execution_active: bool = False
    task_execution_phase: str = ""


@dataclass
class HookContext:
    event: HookEvent
    request: ToolExecutionRequest
    current_arguments: dict[str, Any]
    result: Any = ""
    error: str = ""


@dataclass
class HookOutcome:
    decision: HookDecision = "pass"
    updated_input: dict[str, Any] | None = None
    extra_message: str = ""
    reason: str = ""


@dataclass
class HookTraceItem:
    hook_name: str
    event: HookEvent
    matched: bool
    decision: HookDecision = "pass"
    reason: str = ""
    extra_message: str = ""


def _empty_str_list() -> list[str]:
    return []


def _empty_pre_trace() -> list[HookTraceItem]:
    return []


def _empty_post_trace() -> list[HookTraceItem]:
    return []


@dataclass
class ToolExecutionResult:
    status: ToolExecStatus
    output: Any
    final_arguments: dict[str, Any]
    invoker_reached: bool = False
    invoker_succeeded: bool = False
    extra_messages: list[str] = field(default_factory=_empty_str_list)
    pre_hook_trace: list[HookTraceItem] = field(default_factory=_empty_pre_trace)
    post_hook_trace: list[HookTraceItem] = field(default_factory=_empty_post_trace)
    policy_trace: dict[str, object] = field(default_factory=dict)
