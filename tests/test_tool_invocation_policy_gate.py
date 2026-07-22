from __future__ import annotations

import asyncio
import json
from typing import Any

from agent.policies.tool_invocation_policy import (
    ToolInvocationContext,
    ToolInvocationDecision,
)
from agent.tool_hooks import ToolExecutionRequest, ToolExecutor
from agent.tool_hooks.base import ToolHook
from agent.tool_hooks.types import HookContext, HookOutcome
from agent.tools.base import Tool
from agent.tools.registry import ToolRegistry


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _raising_invoker(tool_name: str, arguments: dict[str, Any]) -> object:
    raise AssertionError(f"invoker reached for {tool_name}: {arguments}")


async def _recording_invoker(tool_name: str, arguments: dict[str, Any]) -> object:
    return {"tool": tool_name, "arguments": dict(arguments)}


async def _echo_invoker(tool_name: str, arguments: dict[str, Any]) -> object:
    return {"tool": tool_name, "arguments": dict(arguments)}


def test_policy_gate_denies_destructive_tool_before_invoker() -> None:
    result = _run(
        ToolExecutor().execute(
            ToolExecutionRequest(
                call_id="call-1",
                tool_name="delete_workspace",
                arguments={"path": "."},
                source="passive",
                registered=True,
                registry_risk="destructive",
            ),
            _raising_invoker,
        )
    )

    assert result.status == "denied"
    assert result.invoker_reached is False
    assert result.invoker_succeeded is False
    assert result.final_arguments == {"path": "."}
    assert result.policy_trace["action"] == "deny"
    assert result.policy_trace["reason"] == "tool_invocation_destructive_denied"


def test_policy_gate_defers_task_execution_work_shell_before_invoker() -> None:
    result = _run(
        ToolExecutor().execute(
            ToolExecutionRequest(
                call_id="call-2",
                tool_name="shell",
                arguments={"command": "pwd"},
                source="passive",
                registered=True,
                registry_risk="read-only",
                registry_capabilities=frozenset({"shell.execute"}),
                task_execution_active=True,
                task_execution_phase="work",
            ),
            _raising_invoker,
        )
    )

    assert result.status == "deferred"
    assert result.invoker_reached is False
    assert result.invoker_succeeded is False
    assert result.policy_trace["action"] == "defer"
    assert result.policy_trace["metadata"]["durable_transition"] == (
        "waiting_authorization"
    )
    assert isinstance(result.output, str)
    assert '"deferred": true' in result.output


def test_policy_gate_allows_task_execution_control_tool_before_invoker() -> None:
    result = _run(
        ToolExecutor().execute(
            ToolExecutionRequest(
                call_id="call-control",
                tool_name="finish_task_step_execution",
                arguments={"success": True, "result_summary": "done"},
                source="passive",
                registered=True,
                registry_risk="write",
                registry_capabilities=frozenset({"task_execution.finish"}),
                task_execution_active=True,
                task_execution_phase="work",
            ),
            _recording_invoker,
        )
    )

    assert result.status == "success"
    assert result.invoker_reached is True
    assert result.policy_trace["action"] == "allow"
    assert result.policy_trace["reason"] == (
        "tool_invocation_task_execution_control_allowed"
    )


class RewritePathHook(ToolHook):
    name = "rewrite_path"
    event = "pre_tool_use"

    def matches(self, ctx: HookContext) -> bool:
        return ctx.request.tool_name == "read_file"

    async def run(self, ctx: HookContext) -> HookOutcome:
        updated = dict(ctx.current_arguments)
        updated["path"] = "safe.md"
        return HookOutcome(decision="pass", updated_input=updated)


class CapturingPolicyEngine:
    policy_name = "CapturingPolicyEngine"

    def __init__(self) -> None:
        self.contexts: list[ToolInvocationContext] = []

    def evaluate(self, context: ToolInvocationContext) -> ToolInvocationDecision:
        self.contexts.append(context)
        return ToolInvocationDecision(
            action="allow",
            reason="captured",
            risk=context.registry_risk,
            policy_name=self.policy_name,
        )


def test_policy_runs_after_pre_hook_argument_rewrite() -> None:
    policy = CapturingPolicyEngine()
    result = _run(
        ToolExecutor([RewritePathHook()], policy_engine=policy).execute(
            ToolExecutionRequest(
                call_id="call-3",
                tool_name="read_file",
                arguments={"path": "unsafe.md"},
                source="passive",
                registered=True,
                registry_risk="read-only",
            ),
            _echo_invoker,
        )
    )

    assert result.status == "success"
    assert result.invoker_reached is True
    assert result.final_arguments == {"path": "safe.md"}
    assert result.policy_trace["action"] == "allow"
    assert dict(policy.contexts[0].arguments) == {"path": "safe.md"}


def test_passive_registered_write_remains_default_allowed() -> None:
    result = _run(
        ToolExecutor().execute(
            ToolExecutionRequest(
                call_id="call-4",
                tool_name="write_file",
                arguments={"path": "note.md", "content": "hello"},
                source="passive",
                registered=True,
                registry_risk="write",
            ),
            _echo_invoker,
        )
    )

    assert result.status == "success"
    assert result.invoker_reached is True
    assert result.invoker_succeeded is True
    assert result.policy_trace["reason"] == "tool_invocation_default_allow"


class DummyTool(Tool):
    name = "dummy"
    description = "dummy tool"
    parameters = {"type": "object", "properties": {}}
    capabilities = frozenset({"dummy.read"})

    async def execute(self, **kwargs: Any) -> str:
        return "ok"


def test_registry_returns_invocation_metadata_for_registered_tool() -> None:
    registry = ToolRegistry()
    registry.register(DummyTool(), risk="read-only")

    metadata = registry.get_invocation_metadata("dummy")

    assert metadata == {
        "registered": True,
        "registry_risk": "read-only",
        "registry_capabilities": frozenset({"dummy.read"}),
    }


def test_registry_returns_closed_metadata_for_missing_tool() -> None:
    registry = ToolRegistry()

    metadata = registry.get_invocation_metadata("missing")

    assert metadata == {
        "registered": False,
        "registry_risk": "unknown",
        "registry_capabilities": frozenset(),
    }


def test_executor_deferred_result_payload_is_json_string() -> None:
    result = _run(
        ToolExecutor().execute(
            ToolExecutionRequest(
                call_id="call-5",
                tool_name="send_webhook",
                arguments={"url": "https://example.invalid"},
                source="passive",
                registered=True,
                registry_risk="external-side-effect",
                task_execution_active=True,
                task_execution_phase="work",
            ),
            _raising_invoker,
        )
    )

    assert result.status == "deferred"
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert payload["blocked"] is True
    assert payload["deferred"] is True
    assert payload["invoker_reached"] is False
    assert payload["policy"]["action"] == "defer"
    assert payload["policy"]["metadata"]["durable_transition"] == (
        "waiting_authorization"
    )
