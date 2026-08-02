from __future__ import annotations

import asyncio
from typing import Any

from agent.policies.tool_invocation_policy import ToolInvocationDecision
from agent.tool_hooks.base import ToolHook
from agent.tool_hooks.executor import ToolExecutor
from agent.tool_hooks.types import HookContext, HookOutcome, ToolExecutionRequest
from agent.tools.base import Tool
from agent.tools.execution_context import ToolExecutionContext
from agent.tools.registry import ToolRegistry


class _SpyHook(ToolHook):
    def __init__(
        self,
        *,
        name: str,
        event: str,
        matched: bool = True,
        outcome: HookOutcome | None = None,
    ) -> None:
        self.name = name
        self.event = event
        self._matched = matched
        self._outcome = outcome or HookOutcome()
        self.calls: list[HookContext] = []
        self._match_error: Exception | None = None
        self._run_error: Exception | None = None

    def matches(self, ctx: HookContext) -> bool:
        if self._match_error is not None:
            raise self._match_error
        return self._matched

    async def run(self, ctx: HookContext) -> HookOutcome:
        if self._run_error is not None:
            raise self._run_error
        self.calls.append(ctx)
        return self._outcome


async def _invoke(tool_name: str, arguments: dict[str, Any]) -> Any:
    return {"tool": tool_name, "arguments": dict(arguments)}


class _RecordingLedger:
    def __init__(self) -> None:
        self.events: list[Any] = []
        self.raise_on_record = False

    def record_event(self, event: Any) -> Any:
        if self.raise_on_record:
            raise RuntimeError("ledger down")
        self.events.append(event)
        return event


class _FixedPolicy:
    def __init__(
        self, action: str, reason: str = "test_policy", risk: str = "write"
    ) -> None:
        self.action = action
        self.reason = reason
        self.risk = risk

    def evaluate(self, _context: Any) -> ToolInvocationDecision:
        return ToolInvocationDecision(
            action=self.action,
            reason=self.reason,
            risk=self.risk,
            metadata={"resource_type": "workspace", "resource_decision": self.action},
        )


class _ThrowingTool(Tool):
    name = "throwing"
    description = "throws during execution"
    parameters = {"type": "object", "properties": {}}

    async def execute(self, **_: Any) -> str:
        raise RuntimeError("boom")


def test_tool_executor_pre_hook_can_update_arguments() -> None:
    hook = _SpyHook(
        name="rewrite",
        event="pre_tool_use",
        outcome=HookOutcome(updated_input={"x": 2}),
    )
    executor = ToolExecutor([hook])

    result = asyncio.run(
        executor.execute(
            ToolExecutionRequest(
                call_id="c1",
                tool_name="dummy",
                arguments={"x": 1},
                source="passive",
                registry_risk="read-only",
            ),
            _invoke,
        )
    )

    assert result.status == "success"
    assert result.final_arguments == {"x": 2}
    assert result.output == {"tool": "dummy", "arguments": {"x": 2}}
    assert hook.calls[0].request.arguments == {"x": 1}


def test_tool_executor_denied_is_not_error() -> None:
    hook = _SpyHook(
        name="deny",
        event="pre_tool_use",
        outcome=HookOutcome(decision="deny", reason="blocked"),
    )
    executor = ToolExecutor([hook])

    result = asyncio.run(
        executor.execute(
            ToolExecutionRequest(
                call_id="c1",
                tool_name="dummy",
                arguments={"x": 1},
                source="passive",
                registry_risk="read-only",
            ),
            _invoke,
        )
    )

    assert result.status == "denied"
    assert result.output == "blocked"
    assert result.invoker_reached is False
    assert result.invoker_succeeded is False


def test_tool_executor_post_hook_only_adds_extra_message() -> None:
    hook = _SpyHook(
        name="post",
        event="post_tool_use",
        outcome=HookOutcome(extra_message="hint"),
    )
    executor = ToolExecutor([hook])

    result = asyncio.run(
        executor.execute(
            ToolExecutionRequest(
                call_id="c1",
                tool_name="dummy",
                arguments={"x": 1},
                source="passive",
                registry_risk="read-only",
            ),
            _invoke,
        )
    )

    assert result.status == "success"
    assert result.output == {"tool": "dummy", "arguments": {"x": 1}}
    assert result.extra_messages == ["hint"]


def test_tool_executor_post_error_hook_cannot_swallow_error() -> None:
    hook = _SpyHook(
        name="post_error",
        event="post_tool_error",
        outcome=HookOutcome(extra_message="logged"),
    )
    executor = ToolExecutor([hook])

    async def _broken(_tool_name: str, _arguments: dict[str, Any]) -> Any:
        raise RuntimeError("boom")

    result = asyncio.run(
        executor.execute(
            ToolExecutionRequest(
                call_id="c1",
                tool_name="dummy",
                arguments={},
                source="passive",
                registry_risk="read-only",
            ),
            _broken,
        )
    )

    assert result.status == "error"
    assert result.output == "工具执行出错: boom"
    assert result.extra_messages == ["logged"]
    assert result.invoker_reached is True
    assert result.invoker_succeeded is False


def test_execution_context_propagates_registry_tool_error_to_executor() -> None:
    registry = ToolRegistry()
    registry.register(_ThrowingTool(), risk="read-only")
    executor = ToolExecutor()

    result = asyncio.run(
        executor.execute(
            ToolExecutionRequest(
                call_id="c1",
                tool_name="throwing",
                arguments={},
                source="passive",
                registry_risk="read-only",
            ),
            lambda name, arguments: registry.execute(
                name,
                arguments,
                execution_context=ToolExecutionContext(
                    protected={}, propagate_tool_errors=True
                ),
            ),
        )
    )

    assert result.status == "error"
    assert result.invoker_reached is True
    assert result.invoker_succeeded is False


def test_tool_executor_hook_exception_becomes_controlled_error() -> None:
    hook = _SpyHook(name="boom_hook", event="pre_tool_use")
    hook._run_error = RuntimeError("hook boom")
    executor = ToolExecutor([hook])

    result = asyncio.run(
        executor.execute(
            ToolExecutionRequest(
                call_id="c1",
                tool_name="dummy",
                arguments={"x": 1},
                source="passive",
                registry_risk="read-only",
            ),
            _invoke,
        )
    )

    assert result.status == "error"
    assert "boom_hook" in result.output
    assert "hook boom" in result.output


def test_tool_executor_post_tool_use_hook_failure_does_not_pollute_success() -> None:
    hook = _SpyHook(name="boom_hook", event="post_tool_use")
    hook._run_error = RuntimeError("post hook boom")
    executor = ToolExecutor([hook])

    result = asyncio.run(
        executor.execute(
            ToolExecutionRequest(
                call_id="c1",
                tool_name="dummy",
                arguments={"x": 1},
                source="passive",
                registry_risk="read-only",
            ),
            _invoke,
        )
    )

    assert result.status == "success"
    assert result.output == {"tool": "dummy", "arguments": {"x": 1}}
    assert result.post_hook_trace[-1].reason == "hook failed: post hook boom"


def test_tool_executor_records_allow_policy_decision_to_ledger() -> None:
    ledger = _RecordingLedger()
    executor = ToolExecutor(audit_ledger_store=ledger)
    result = asyncio.run(
        executor.execute(
            ToolExecutionRequest(
                call_id="call-allow",
                tool_name="dummy",
                arguments={"x": 1},
                source="passive",
                registry_risk="read-only",
                session_key="cli:s",
                channel="cli",
            ),
            _invoke,
        )
    )
    assert result.status == "success"
    assert len(ledger.events) == 1
    event = ledger.events[0]
    assert event.event_type == "tool_invocation_policy_decision"
    assert event.request_id == "call-allow"
    assert event.policy_action == "allow"
    assert event.invoker_reached is True
    assert event.invoker_succeeded is True


def test_tool_executor_records_deny_policy_decision_to_ledger() -> None:
    ledger = _RecordingLedger()
    result = asyncio.run(
        ToolExecutor(
            policy_engine=_FixedPolicy("deny"), audit_ledger_store=ledger
        ).execute(
            ToolExecutionRequest(
                call_id="call-deny",
                tool_name="dummy",
                arguments={"x": 1},
                source="passive",
                registry_risk="write",
            ),
            _invoke,
        )
    )
    assert result.status == "denied"
    assert ledger.events[0].policy_action == "deny"
    assert ledger.events[0].invoker_reached is False


def test_tool_executor_records_defer_policy_decision_to_ledger() -> None:
    ledger = _RecordingLedger()
    result = asyncio.run(
        ToolExecutor(
            policy_engine=_FixedPolicy("defer"), audit_ledger_store=ledger
        ).execute(
            ToolExecutionRequest(
                call_id="call-defer",
                tool_name="dummy",
                arguments={"x": 1},
                source="passive",
                registry_risk="write",
            ),
            _invoke,
        )
    )
    assert result.status == "deferred"
    assert ledger.events[0].policy_action == "defer"
    assert ledger.events[0].invoker_reached is False


def test_tool_executor_records_invoker_error_to_ledger() -> None:
    ledger = _RecordingLedger()

    async def _broken(_tool_name: str, _arguments: dict[str, Any]) -> Any:
        raise RuntimeError("boom")

    result = asyncio.run(
        ToolExecutor(audit_ledger_store=ledger).execute(
            ToolExecutionRequest(
                call_id="call-error",
                tool_name="dummy",
                arguments={"x": 1},
                source="passive",
                registry_risk="read-only",
            ),
            _broken,
        )
    )
    assert result.status == "error"
    assert ledger.events[0].policy_action == "allow"
    assert ledger.events[0].invoker_reached is True
    assert ledger.events[0].invoker_succeeded is False


def test_tool_executor_records_post_hook_error_after_invoker_to_ledger() -> None:
    ledger = _RecordingLedger()
    hook = _SpyHook(name="boom_hook", event="post_tool_use")
    hook._match_error = RuntimeError("post match boom")
    result = asyncio.run(
        ToolExecutor([hook], audit_ledger_store=ledger).execute(
            ToolExecutionRequest(
                call_id="call-post-error",
                tool_name="dummy",
                arguments={"x": 1},
                source="passive",
                registry_risk="read-only",
            ),
            _invoke,
        )
    )
    assert result.status == "success"
    assert ledger.events[0].invoker_reached is True
    assert ledger.events[0].invoker_succeeded is True


def test_tool_executor_ledger_failure_does_not_change_result() -> None:
    ledger = _RecordingLedger()
    ledger.raise_on_record = True
    result = asyncio.run(
        ToolExecutor(audit_ledger_store=ledger).execute(
            ToolExecutionRequest(
                call_id="call-allow",
                tool_name="dummy",
                arguments={"x": 1},
                source="passive",
                registry_risk="read-only",
            ),
            _invoke,
        )
    )
    assert result.status == "success"
    assert result.invoker_reached is True
    assert result.invoker_succeeded is True
