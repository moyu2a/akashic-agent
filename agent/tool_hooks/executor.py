from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any, Awaitable, Callable, Protocol

from agent.policies.tool_approval import build_approval_payload
from agent.policies.tool_approval_decision import ToolApprovalDecision
from agent.policies.tool_approval_runtime import ToolApprovalRuntime
from agent.policies.tool_audit import build_tool_audit_event
from agent.policies.tool_invocation_policy import (
    ToolInvocationContext,
    ToolInvocationDecision,
    ToolInvocationPolicyEngine,
    ToolInvocationSource,
    ToolInvocationTaskExecutionPhase,
)
from agent.tool_hooks.base import ToolHook
from agent.tool_hooks.types import (
    HookContext,
    HookTraceItem,
    ToolExecutionRequest,
    ToolExecutionResult,
)

ToolInvoker = Callable[[str, dict[str, Any]], Awaitable[Any]]


class ToolInvocationPolicy(Protocol):
    def evaluate(self, context: ToolInvocationContext) -> ToolInvocationDecision: ...


class HookExecutionError(RuntimeError):
    def __init__(self, hook_name: str, event: str, cause: Exception) -> None:
        self.hook_name = hook_name
        self.event = event
        self.cause = cause
        super().__init__(f"hook {hook_name} ({event}) failed: {cause}")


class ToolExecutor:
    def __init__(
        self,
        hooks: Sequence[ToolHook] | None = None,
        policy_engine: ToolInvocationPolicy | None = None,
        approval_runtime: ToolApprovalRuntime | None = None,
    ) -> None:
        self._hooks = list(hooks or [])
        self._policy_engine = policy_engine or ToolInvocationPolicyEngine()
        self._approval_runtime = approval_runtime

    def add_hooks(self, hooks: Sequence[ToolHook]) -> None:
        self._hooks.extend(hooks)

    def set_approval_runtime(
        self, approval_runtime: ToolApprovalRuntime | None
    ) -> None:
        self._approval_runtime = approval_runtime

    async def execute(
        self,
        request: ToolExecutionRequest,
        invoker: ToolInvoker,
    ) -> ToolExecutionResult:
        """执行单次工具调用。

        request 描述“这次想调用什么工具、带什么参数”；
        invoker 是真实执行入口（通常是 ToolRegistry.execute）。

        固定流程：
        1. pre hooks：匹配、改参、必要时拒绝
        2. core invocation policy：最终参数进入真实 invoker 前的硬 gate
        3. invoker：用最终参数执行真实工具
        4. post hooks：记录成功或错误后的附加信息与 trace
        """
        current_arguments = dict(request.arguments)
        extra_messages: list[str] = []
        pre_trace: list[HookTraceItem] = []
        post_trace: list[HookTraceItem] = []

        try:
            # pre_hook 是唯一允许改输入/直接 deny 的阶段。
            denied_reason, current_arguments = await self._run_pre_hooks(
                request=request,
                current_arguments=current_arguments,
                extra_messages=extra_messages,
                traces=pre_trace,
            )
        except HookExecutionError as exc:
            return ToolExecutionResult(
                status="error",
                output=f"工具执行出错: {exc}",
                final_arguments=dict(current_arguments),
                invoker_reached=False,
                invoker_succeeded=False,
                extra_messages=extra_messages,
                pre_hook_trace=pre_trace,
                post_hook_trace=post_trace,
            )
        final_arguments = dict(current_arguments)
        if denied_reason:
            return ToolExecutionResult(
                status="denied",
                output=denied_reason,
                final_arguments=final_arguments,
                invoker_reached=False,
                invoker_succeeded=False,
                extra_messages=extra_messages,
                pre_hook_trace=pre_trace,
                post_hook_trace=post_trace,
            )

        policy_decision = self._policy_engine.evaluate(
            _build_policy_context(request, final_arguments)
        )
        policy_trace = policy_decision.to_trace_metadata()
        if policy_decision.action == "deny":
            return ToolExecutionResult(
                status="denied",
                output=_policy_block_output(policy_decision),
                final_arguments=final_arguments,
                invoker_reached=False,
                invoker_succeeded=False,
                extra_messages=extra_messages,
                pre_hook_trace=pre_trace,
                post_hook_trace=post_trace,
                policy_trace=policy_trace,
                audit_trace=_audit_trace(
                    request,
                    final_arguments,
                    policy_decision,
                    invoker_reached=False,
                    invoker_succeeded=False,
                ),
            )
        if policy_decision.action == "defer":
            approval_scope = _approval_scope_from_trace(policy_trace)
            approval_decision: ToolApprovalDecision | None = None
            if self._approval_runtime is not None:
                approval_decision = self._approval_runtime.consume_for_execution(
                    trusted_context=request.trusted_approval_context,
                    request_id=request.call_id,
                    session_key=request.session_key,
                    tool_name=request.tool_name,
                    approval_scope=approval_scope,
                    arguments=final_arguments,
                )
                if approval_decision.allows_invoker:
                    return await self._execute_invoker(
                        request=request,
                        invoker=invoker,
                        final_arguments=final_arguments,
                        extra_messages=extra_messages,
                        pre_trace=pre_trace,
                        post_trace=post_trace,
                        policy_decision=policy_decision,
                        policy_trace=policy_trace,
                        approval_request_id=approval_decision.approval_request_id,
                        approval_scope=approval_scope,
                    )
            approval_request_id = ""
            expires_at = ""
            if (
                self._approval_runtime is not None
                and approval_decision is not None
                and approval_decision.action == "not_applicable"
            ):
                record = self._approval_runtime.record_defer_request(
                    request_id=request.call_id,
                    session_key=request.session_key,
                    channel=request.channel,
                    chat_id=request.chat_id,
                    source=_policy_source(request),
                    tool_name=request.tool_name,
                    risk=policy_decision.risk,
                    approval_scope=approval_scope,
                    policy_reason=policy_decision.reason,
                    arguments=final_arguments,
                )
                approval_request_id = record.approval_request_id
                expires_at = record.expires_at
            return ToolExecutionResult(
                status="deferred",
                output=_policy_defer_output(
                    policy_decision,
                    tool_name=request.tool_name,
                    arguments=final_arguments,
                    approval_request_id=approval_request_id,
                    expires_at=expires_at,
                ),
                final_arguments=final_arguments,
                invoker_reached=False,
                invoker_succeeded=False,
                extra_messages=extra_messages,
                pre_hook_trace=pre_trace,
                post_hook_trace=post_trace,
                policy_trace=policy_trace,
                audit_trace=_audit_trace(
                    request,
                    final_arguments,
                    policy_decision,
                    invoker_reached=False,
                    invoker_succeeded=False,
                ),
            )

        return await self._execute_invoker(
            request=request,
            invoker=invoker,
            final_arguments=final_arguments,
            extra_messages=extra_messages,
            pre_trace=pre_trace,
            post_trace=post_trace,
            policy_decision=policy_decision,
            policy_trace=policy_trace,
        )

    async def _execute_invoker(
        self,
        *,
        request: ToolExecutionRequest,
        invoker: ToolInvoker,
        final_arguments: dict[str, Any],
        extra_messages: list[str],
        pre_trace: list[HookTraceItem],
        post_trace: list[HookTraceItem],
        policy_decision: ToolInvocationDecision,
        policy_trace: dict[str, object],
        approval_request_id: str = "",
        approval_scope: str = "tool_call",
    ) -> ToolExecutionResult:
        try:
            # 这里才进入真实工具执行；hook 本身不直接替代工具实现。
            output = await invoker(request.tool_name, final_arguments)
        except Exception as exc:
            error_text = str(exc)
            self._finalize_approval_execution(
                approval_request_id=approval_request_id,
                request=request,
                final_arguments=final_arguments,
                approval_scope=approval_scope,
                execution_status="execution_failed",
            )
            try:
                # 工具自身报错后，允许 post_tool_error 做记录型处理。
                await self._run_post_hooks(
                    HookContext(
                        event="post_tool_error",
                        request=request,
                        current_arguments=final_arguments,
                        error=error_text,
                    ),
                    extra_messages=extra_messages,
                    traces=post_trace,
                )
            except HookExecutionError as hook_exc:
                return ToolExecutionResult(
                    status="error",
                    output=f"工具执行出错: {hook_exc}",
                    final_arguments=final_arguments,
                    invoker_reached=True,
                    invoker_succeeded=False,
                    extra_messages=extra_messages,
                    pre_hook_trace=pre_trace,
                    post_hook_trace=post_trace,
                    policy_trace=policy_trace,
                    audit_trace=_audit_trace(
                        request,
                        final_arguments,
                        policy_decision,
                        invoker_reached=True,
                        invoker_succeeded=False,
                    ),
                )
            return ToolExecutionResult(
                status="error",
                output=f"工具执行出错: {error_text}",
                final_arguments=final_arguments,
                invoker_reached=True,
                invoker_succeeded=False,
                extra_messages=extra_messages,
                pre_hook_trace=pre_trace,
                post_hook_trace=post_trace,
                policy_trace=policy_trace,
                audit_trace=_audit_trace(
                    request,
                    final_arguments,
                    policy_decision,
                    invoker_reached=True,
                    invoker_succeeded=False,
                ),
            )

        self._finalize_approval_execution(
            approval_request_id=approval_request_id,
            request=request,
            final_arguments=final_arguments,
            approval_scope=approval_scope,
            execution_status="executed",
        )
        try:
            # post_tool_use 只做观察和补充信息，不回写执行参数。
            await self._run_post_hooks(
                HookContext(
                    event="post_tool_use",
                    request=request,
                    current_arguments=final_arguments,
                    result=output,
                ),
                extra_messages=extra_messages,
                traces=post_trace,
                fail_open=True,
            )
        except HookExecutionError as exc:
            return ToolExecutionResult(
                status="error",
                output=f"工具执行出错: {exc}",
                final_arguments=final_arguments,
                invoker_reached=True,
                invoker_succeeded=True,
                extra_messages=extra_messages,
                pre_hook_trace=pre_trace,
                post_hook_trace=post_trace,
                policy_trace=policy_trace,
                audit_trace=_audit_trace(
                    request,
                    final_arguments,
                    policy_decision,
                    invoker_reached=True,
                    invoker_succeeded=True,
                ),
            )
        return ToolExecutionResult(
            status="success",
            output=output,
            final_arguments=final_arguments,
            invoker_reached=True,
            invoker_succeeded=True,
            extra_messages=extra_messages,
            pre_hook_trace=pre_trace,
            post_hook_trace=post_trace,
            policy_trace=policy_trace,
            audit_trace=_audit_trace(
                request,
                final_arguments,
                policy_decision,
                invoker_reached=True,
                invoker_succeeded=True,
            ),
        )

    def _finalize_approval_execution(
        self,
        *,
        approval_request_id: str,
        request: ToolExecutionRequest,
        final_arguments: dict[str, Any],
        approval_scope: str,
        execution_status: str,
    ) -> None:
        if self._approval_runtime is None or not approval_request_id:
            return
        self._approval_runtime.finalize_execution(
            approval_request_id=approval_request_id,
            request_id=request.call_id,
            session_key=request.session_key,
            tool_name=request.tool_name,
            approval_scope=approval_scope,
            arguments=final_arguments,
            execution_status=execution_status,
        )

    async def preflight(
        self,
        request: ToolExecutionRequest,
    ) -> ToolExecutionResult:
        current_arguments = dict(request.arguments)
        extra_messages: list[str] = []
        pre_trace: list[HookTraceItem] = []
        try:
            denied_reason, current_arguments = await self._run_pre_hooks(
                request=request,
                current_arguments=current_arguments,
                extra_messages=extra_messages,
                traces=pre_trace,
            )
        except HookExecutionError as exc:
            return ToolExecutionResult(
                status="error",
                output=f"工具执行出错: {exc}",
                final_arguments=dict(current_arguments),
                invoker_reached=False,
                invoker_succeeded=False,
                extra_messages=extra_messages,
                pre_hook_trace=pre_trace,
            )
        if denied_reason:
            return ToolExecutionResult(
                status="denied",
                output=denied_reason,
                final_arguments=dict(current_arguments),
                invoker_reached=False,
                invoker_succeeded=False,
                extra_messages=extra_messages,
                pre_hook_trace=pre_trace,
            )
        return ToolExecutionResult(
            status="success",
            output="",
            final_arguments=dict(current_arguments),
            invoker_reached=False,
            invoker_succeeded=False,
            extra_messages=extra_messages,
            pre_hook_trace=pre_trace,
        )

    async def _run_pre_hooks(
        self,
        *,
        request: ToolExecutionRequest,
        current_arguments: dict[str, Any],
        extra_messages: list[str],
        traces: list[HookTraceItem],
    ) -> tuple[str, dict[str, Any]]:
        for hook in self._hooks:
            if hook.event != "pre_tool_use":
                continue
            ctx = HookContext(
                event="pre_tool_use",
                request=request,
                current_arguments=dict(current_arguments),
            )
            try:
                matched = hook.matches(ctx)
            except Exception as exc:
                raise HookExecutionError(hook.name, hook.event, exc) from exc
            if not matched:
                traces.append(
                    HookTraceItem(
                        hook_name=hook.name,
                        event=hook.event,
                        matched=False,
                    )
                )
                continue
            try:
                outcome = await hook.run(ctx)
            except Exception as exc:
                raise HookExecutionError(hook.name, hook.event, exc) from exc
            if outcome.updated_input is not None:
                current_arguments = dict(outcome.updated_input)
            if outcome.extra_message:
                extra_messages.append(outcome.extra_message)
            traces.append(
                HookTraceItem(
                    hook_name=hook.name,
                    event=hook.event,
                    matched=True,
                    decision=outcome.decision,
                    reason=outcome.reason,
                    extra_message=outcome.extra_message,
                )
            )
            if outcome.decision == "deny":
                reason = outcome.reason.strip() or "工具调用被拦截"
                return reason, current_arguments
        return "", current_arguments

    async def _run_post_hooks(
        self,
        ctx: HookContext,
        *,
        extra_messages: list[str],
        traces: list[HookTraceItem],
        fail_open: bool = False,
    ) -> None:
        for hook in self._hooks:
            if hook.event != ctx.event:
                continue
            try:
                matched = hook.matches(ctx)
            except Exception as exc:
                if fail_open:
                    traces.append(
                        HookTraceItem(
                            hook_name=hook.name,
                            event=hook.event,
                            matched=False,
                            reason=f"hook failed: {exc}",
                        )
                    )
                    continue
                raise HookExecutionError(hook.name, hook.event, exc) from exc
            if not matched:
                traces.append(
                    HookTraceItem(
                        hook_name=hook.name,
                        event=hook.event,
                        matched=False,
                    )
                )
                continue
            try:
                outcome = await hook.run(ctx)
            except Exception as exc:
                if fail_open:
                    traces.append(
                        HookTraceItem(
                            hook_name=hook.name,
                            event=hook.event,
                            matched=True,
                            reason=f"hook failed: {exc}",
                        )
                    )
                    continue
                raise HookExecutionError(hook.name, hook.event, exc) from exc
            if outcome.extra_message:
                extra_messages.append(outcome.extra_message)
            traces.append(
                HookTraceItem(
                    hook_name=hook.name,
                    event=hook.event,
                    matched=True,
                    decision=outcome.decision,
                    reason=outcome.reason,
                    extra_message=outcome.extra_message,
                )
            )


def _policy_source(request: ToolExecutionRequest) -> ToolInvocationSource:
    if request.task_execution_active:
        return "task_execution"
    if request.source in {"passive", "proactive", "subagent"}:
        return request.source
    return "passive"


def _policy_task_execution_phase(value: str) -> ToolInvocationTaskExecutionPhase:
    phases: dict[str, ToolInvocationTaskExecutionPhase] = {
        "": "",
        "inactive": "inactive",
        "claim": "claim",
        "work": "work",
        "waiting_authorization": "waiting_authorization",
        "finish": "finish",
        "terminal": "terminal",
    }
    return phases.get(value, "")


def _build_policy_context(
    request: ToolExecutionRequest,
    arguments: dict[str, Any],
) -> ToolInvocationContext:
    return ToolInvocationContext(
        tool_name=request.tool_name,
        arguments=arguments,
        registered=request.registered,
        registry_risk=request.registry_risk,
        capabilities=request.registry_capabilities,
        source=_policy_source(request),
        session_key=request.session_key,
        request_id=request.call_id,
        user_text=request.request_text,
        task_execution_active=request.task_execution_active,
        task_execution_phase=_policy_task_execution_phase(request.task_execution_phase),
        metadata={
            "channel": request.channel,
            "chat_id": request.chat_id,
            "tool_batch_index": request.tool_batch_index,
            "resource_roots": tuple(request.resource_roots),
        },
    )


def _audit_trace(
    request: ToolExecutionRequest,
    arguments: dict[str, Any],
    decision: ToolInvocationDecision,
    *,
    invoker_reached: bool,
    invoker_succeeded: bool,
) -> dict[str, object]:
    return build_tool_audit_event(
        request_id=request.call_id,
        session_key=request.session_key,
        channel=request.channel,
        chat_id=request.chat_id,
        tool_name=request.tool_name,
        source=_policy_source(request),
        risk=decision.risk,
        policy_action=decision.action,
        policy_reason=decision.reason,
        arguments=arguments,
        invoker_reached=invoker_reached,
        invoker_succeeded=invoker_succeeded,
    ).to_trace_metadata()


def _policy_block_output(decision: ToolInvocationDecision) -> str:
    trace = decision.to_trace_metadata()
    return json.dumps(
        {
            "ok": False,
            "blocked": True,
            "error_code": trace["reason"],
            "message": "工具调用被调用级安全策略拒绝。",
            "policy": trace,
            "invoker_reached": False,
        },
        ensure_ascii=False,
    )


def _approval_scope_from_trace(trace: dict[str, object]) -> str:
    metadata = trace.get("metadata")
    if not isinstance(metadata, dict):
        return "tool_call"
    direct_scope = metadata.get("approval_scope")
    if isinstance(direct_scope, str) and direct_scope:
        return direct_scope
    strategy = metadata.get("risk_strategy")
    if isinstance(strategy, dict):
        strategy_scope = strategy.get("approval_scope")
        if isinstance(strategy_scope, str) and strategy_scope:
            return strategy_scope
    return "tool_call"


def _policy_defer_output(
    decision: ToolInvocationDecision,
    *,
    tool_name: str,
    arguments: dict[str, Any],
    approval_request_id: str = "",
    expires_at: str = "",
) -> str:
    trace = decision.to_trace_metadata()
    payload = build_approval_payload(
        tool_name=tool_name,
        arguments=arguments,
        action="defer",
        reason=str(trace["reason"]),
        risk=str(trace["risk"]),
        approval_scope=_approval_scope_from_trace(trace),
        approval_request_id=approval_request_id,
        expires_at=expires_at,
    )
    payload["policy"] = trace
    return json.dumps(
        payload,
        ensure_ascii=False,
    )
