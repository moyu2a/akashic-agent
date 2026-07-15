from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from agent.policies.doc_rag_intent import DOC_RAG_TOOL_NAMES, decide_doc_rag_preload
from agent.policies.task_execution_access import TaskExecutionAccessPolicy
from agent.policies.task_plan_boundary import TaskPlanAccessPolicy
from agent.policies.tool_access_types import (
    ToolAccessContext,
    ToolAccessPlan,
    ToolAccessPolicy,
    ToolExecutionGateResult,
)

LOCAL_FILE_TOOL_NAMES = frozenset({"shell", "read_file", "list_dir"})
TRACE_TOOL_NAMES = frozenset({"inspect_turn_trace"})

_EXPLICIT_LOCAL_SOURCE_TERMS = (
    "源码",
    "源代码",
    "仓库文件",
    "本地文件",
    "读取文件",
    "查看文件",
    "路径",
)
_SESSION_META_TERMS = (
    "记得",
    "之前说过",
    "我之前",
    "我的偏好",
    "偏好",
    "记忆",
    "刚才",
    "上一轮",
    "上轮",
    "第二个问题",
    "第一个问题",
    "第三个问题",
    "用了哪些工具",
    "用过哪些工具",
    "查了哪些工具",
    "工具链",
    "聊天记录",
    "session",
    "会话",
)
_PATH_RE = re.compile(
    r"(^|\s)(/[^ \n\t]+|[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+"
    r"\.(?:py|md|toml|yaml|yml|json|txt|sh))"
)


class DocRagAccessPolicy:
    name = "DocRagAccessPolicy"

    def build_plan(self, context: ToolAccessContext) -> ToolAccessPlan:
        decision = decide_doc_rag_preload(context.user_text)
        if not decision.preload_search_docs:
            return ToolAccessPlan()

        visible_add = {"search_docs"}
        if decision.preload_fetch_doc_chunk:
            visible_add.add("fetch_doc_chunk")

        matched_terms = decision.matched_terms
        if _has_explicit_local_source_intent(context.user_text):
            return ToolAccessPlan(
                visible_add=frozenset(visible_add),
                reason="doc_rag_allows_explicit_local_files",
                matched_terms=matched_terms,
                policies=(self.name,),
                local_source_allowed=True,
            )

        reason = (
            "doc_rag_block_local_file_tools"
            if decision.preload_fetch_doc_chunk
            else "doc_rag_prefer_rag_tools"
        )
        return ToolAccessPlan(
            visible_add=frozenset(visible_add),
            visible_suppress=LOCAL_FILE_TOOL_NAMES,
            tool_search_block=LOCAL_FILE_TOOL_NAMES,
            execution_block=LOCAL_FILE_TOOL_NAMES,
            reason=reason,
            matched_terms=matched_terms,
            policies=(self.name,),
        )

    def observe_tool_result(
        self,
        plan: ToolAccessPlan,
        tool_name: str,
        result_text: str,
        *,
        execution_status: str = "success",
    ) -> ToolAccessPlan:
        return plan


class SessionMetaAccessPolicy:
    name = "SessionMetaAccessPolicy"

    def build_plan(self, context: ToolAccessContext) -> ToolAccessPlan:
        matched = _matched_terms(context.user_text, _SESSION_META_TERMS)
        if not matched:
            return ToolAccessPlan()
        return ToolAccessPlan(
            visible_add=TRACE_TOOL_NAMES,
            visible_suppress=DOC_RAG_TOOL_NAMES,
            tool_search_block=DOC_RAG_TOOL_NAMES,
            execution_block=DOC_RAG_TOOL_NAMES,
            reason="session_meta_suppress_doc_rag_lru",
            matched_terms=matched,
            policies=(self.name,),
        )

    def observe_tool_result(
        self,
        plan: ToolAccessPlan,
        tool_name: str,
        result_text: str,
        *,
        execution_status: str = "success",
    ) -> ToolAccessPlan:
        return plan


class TerminalResultAccessPolicy:
    name = "TerminalResultAccessPolicy"

    def build_plan(self, context: ToolAccessContext) -> ToolAccessPlan:
        return ToolAccessPlan()

    def observe_tool_result(
        self,
        plan: ToolAccessPlan,
        tool_name: str,
        result_text: str,
        *,
        execution_status: str = "success",
    ) -> ToolAccessPlan:
        try:
            payload = json.loads(result_text)
        except (TypeError, ValueError):
            return plan
        if not isinstance(payload, dict):
            return plan
        if (
            payload.get("terminal_scope") != "document_rag"
            or payload.get("fallback_allowed") is not False
        ):
            return plan
        return _merge_plans(
            plan,
            ToolAccessPlan(
                visible_suppress=LOCAL_FILE_TOOL_NAMES,
                tool_search_block=LOCAL_FILE_TOOL_NAMES,
                execution_block=LOCAL_FILE_TOOL_NAMES,
                reason="terminal_doc_rag_blocks_fallback",
                policies=(self.name,),
            ),
        )


class ToolAccessGateway:
    def __init__(self, policies: tuple[ToolAccessPolicy, ...] | None = None) -> None:
        self._policies = policies or (
            DocRagAccessPolicy(),
            SessionMetaAccessPolicy(),
            TaskPlanAccessPolicy(),
            TaskExecutionAccessPolicy(),
            TerminalResultAccessPolicy(),
        )

    def build_plan(self, context: ToolAccessContext) -> ToolAccessPlan:
        plan = ToolAccessPlan()
        for policy in self._policies:
            plan = _merge_plans(plan, policy.build_plan(context))
        if plan.reason == "no_tool_access_policy" and plan.policies:
            plan = replace(plan, reason=plan.policies[-1])
        return plan

    def compute_visible_names(
        self,
        context: ToolAccessContext,
        plan: ToolAccessPlan,
    ) -> set[str]:
        if plan.strict_capability_scope:
            visible = set(plan.visible_add)
        elif not context.tool_discovery_enabled:
            visible = set(context.registered_tools) or (
                set(context.always_on_tools)
                | set(context.lru_preloaded_tools)
                | set(plan.visible_add)
            )
        else:
            visible = (
                set(context.always_on_tools)
                | set(context.lru_preloaded_tools)
                | set(plan.visible_add)
            )
        visible -= set(context.disabled_tools)
        visible -= set(plan.visible_suppress)
        if context.registered_tools:
            visible &= set(context.registered_tools)
        return visible

    def merge_tool_search_unlocks(
        self,
        current_visible: set[str],
        unlocked: set[str],
        context: ToolAccessContext,
        plan: ToolAccessPlan,
    ) -> set[str]:
        visible = set(current_visible)
        allowed_unlocks = set(unlocked)
        allowed_unlocks -= set(context.disabled_tools)
        allowed_unlocks -= set(plan.visible_suppress)
        allowed_unlocks -= set(plan.tool_search_block)
        execution_contract = plan.task_execution_contract
        if (
            execution_contract is not None
            and execution_contract.active
            and execution_contract.phase == "work"
        ):
            allowed_unlocks &= set(plan.execution_dynamic_tools)
        if context.registered_tools:
            allowed_unlocks &= set(context.registered_tools)
        visible.update(allowed_unlocks)
        return visible

    def filter_tool_search_matches(
        self,
        plan: ToolAccessPlan,
        tool_search_payload: str,
    ) -> tuple[str, tuple[str, ...]]:
        try:
            payload = json.loads(tool_search_payload)
        except (TypeError, ValueError):
            return tool_search_payload, ()
        if not isinstance(payload, dict):
            return tool_search_payload, ()
        matched = payload.get("matched")
        if not isinstance(matched, list):
            return tool_search_payload, ()
        blocked: list[str] = []
        filtered: list[Any] = []
        for item in matched:
            tool_name = item.get("name") if isinstance(item, dict) else None
            execution_contract = plan.task_execution_contract
            execution_dynamic_block = (
                execution_contract is not None
                and execution_contract.active
                and execution_contract.phase == "work"
                and tool_name not in plan.execution_dynamic_tools
            )
            if isinstance(item, dict) and (
                tool_name in plan.tool_search_block or execution_dynamic_block
            ):
                blocked.append(str(item["name"]))
                continue
            filtered.append(item)
        if not blocked:
            return tool_search_payload, ()
        payload["matched"] = filtered
        payload["blocked_by_tool_access_gateway"] = blocked
        payload["tool_access_gateway_reason"] = plan.reason
        return json.dumps(payload, ensure_ascii=False, indent=2), tuple(blocked)

    def check_tool_call(
        self,
        plan: ToolAccessPlan,
        tool_name: str,
        arguments: Mapping[str, Any],
    ) -> ToolExecutionGateResult:
        if tool_name not in plan.execution_block:
            return ToolExecutionGateResult(allowed=True)
        if plan.strict_capability_scope:
            if plan.reason == "conflicting_task_plan_contracts":
                return ToolExecutionGateResult(
                    allowed=False,
                    error_code="conflicting_task_plan_contracts",
                    message=(
                        "Conflicting TaskPlan contracts were produced. No tool "
                        "execution is allowed for this turn."
                    ),
                    reason=plan.reason,
                )
            if plan.reason == "task_plan_required_capability_missing":
                hint = plan.model_hints[0] if plan.model_hints else ""
                return ToolExecutionGateResult(
                    allowed=False,
                    error_code="task_plan_required_capability_missing",
                    message=hint or "The required TaskPlan service is unavailable.",
                    reason=plan.reason,
                )
            if plan.reason == "task_execution_required_capability_missing":
                hint = plan.model_hints[0] if plan.model_hints else ""
                return ToolExecutionGateResult(
                    allowed=False,
                    error_code="task_execution_required_capability_missing",
                    message=hint or "The required TaskExecution service is unavailable.",
                    reason=plan.reason,
                )
            recommended = tuple(
                sorted(
                    set(plan.visible_add)
                    - set(plan.visible_suppress)
                    - set(plan.execution_block)
                )
            )
            execution_contract = plan.task_execution_contract
            if execution_contract is not None and execution_contract.active:
                return ToolExecutionGateResult(
                    allowed=False,
                    error_code="tool_blocked_by_task_execution_policy",
                    message=(
                        "Current TaskExecution scope allows only: "
                        + (", ".join(recommended) if recommended else "no tools")
                        + ". Use only tools in this scope."
                    ),
                    recommended_tools=recommended,
                    reason="task_execution_policy_block",
                )
            return ToolExecutionGateResult(
                allowed=False,
                error_code="tool_blocked_by_task_plan_policy",
                message=(
                    "Current TaskPlan scope allows only: "
                    + (", ".join(recommended) if recommended else "no tools")
                    + ". Use only tools in this scope."
                ),
                recommended_tools=recommended,
                reason="task_plan_policy_block",
            )
        recommended: tuple[str, ...] = ()
        if {"search_docs", "fetch_doc_chunk"} & set(plan.visible_add):
            recommended = tuple(
                name
                for name in ("search_docs", "fetch_doc_chunk")
                if name in plan.visible_add
            )
        return ToolExecutionGateResult(
            allowed=False,
            error_code="tool_blocked_by_doc_rag_policy",
            message="当前问题要求项目文档证据，请优先使用 search_docs / fetch_doc_chunk。",
            recommended_tools=recommended,
            reason=plan.reason,
        )

    def observe_tool_result(
        self,
        plan: ToolAccessPlan,
        tool_name: str,
        result_text: str,
        *,
        execution_status: str = "success",
    ) -> ToolAccessPlan:
        updated = plan
        for policy in self._policies:
            updated = policy.observe_tool_result(
                updated,
                tool_name,
                result_text,
                execution_status=execution_status,
            )
        return updated


def _merge_plans(left: ToolAccessPlan, right: ToolAccessPlan) -> ToolAccessPlan:
    if right == ToolAccessPlan():
        return left
    policies = _dedupe_tuple((*left.policies, *right.policies))
    matched = _dedupe_tuple((*left.matched_terms, *right.matched_terms))
    reason = right.reason if right.reason != "no_tool_access_policy" else left.reason
    strict = left.strict_capability_scope or right.strict_capability_scope
    task_plan_contract = left.task_plan_contract or right.task_plan_contract
    task_execution_contract = (
        left.task_execution_contract or right.task_execution_contract
    )
    task_plan_conflict = (
        left.task_plan_contract is not None
        and right.task_plan_contract is not None
        and left.task_plan_contract != right.task_plan_contract
    )
    task_execution_conflict = (
        left.task_execution_contract is not None
        and right.task_execution_contract is not None
        and left.task_execution_contract != right.task_execution_contract
    )
    strict_control_conflict = (
        left.task_plan_contract is not None
        and left.task_plan_contract.active
        and right.task_execution_contract is not None
        and right.task_execution_contract.active
    ) or (
        right.task_plan_contract is not None
        and right.task_plan_contract.active
        and left.task_execution_contract is not None
        and left.task_execution_contract.active
    )
    model_hints = _dedupe_tuple((*left.model_hints, *right.model_hints))
    filter_error = left.filter_error or right.filter_error
    visible_add = left.visible_add | right.visible_add
    visible_suppress = left.visible_suppress | right.visible_suppress
    tool_search_block = left.tool_search_block | right.tool_search_block
    execution_block = left.execution_block | right.execution_block
    context_retrieval_tools = (
        left.context_retrieval_tools | right.context_retrieval_tools
    )
    execution_dynamic_tools = (
        left.execution_dynamic_tools | right.execution_dynamic_tools
    )
    policy_metadata = {**dict(left.policy_metadata), **dict(right.policy_metadata)}
    if task_plan_conflict or task_execution_conflict or strict_control_conflict:
        conflict_universe = frozenset(
            set(visible_add)
            | set(visible_suppress)
            | set(tool_search_block)
            | set(execution_block)
            | set(context_retrieval_tools)
            | set(execution_dynamic_tools)
        )
        task_plan_contract = None
        task_execution_contract = None
        reason = (
            "conflicting_task_plan_contracts"
            if task_plan_conflict
            else "conflicting_task_execution_contracts"
            if task_execution_conflict
            else "conflicting_strict_task_control_contracts"
        )
        filter_error = True
        visible_add = frozenset()
        visible_suppress = conflict_universe
        tool_search_block = conflict_universe
        execution_block = conflict_universe
        context_retrieval_tools = frozenset()
        execution_dynamic_tools = frozenset()
        policy_metadata["strict_contract_conflict"] = {
            "left_task_plan": (
                left.task_plan_contract.to_trace_metadata()
                if left.task_plan_contract is not None
                else None
            ),
            "right_task_plan": (
                right.task_plan_contract.to_trace_metadata()
                if right.task_plan_contract is not None
                else None
            ),
            "left_task_execution": (
                left.task_execution_contract.to_trace_metadata()
                if left.task_execution_contract is not None
                else None
            ),
            "right_task_execution": (
                right.task_execution_contract.to_trace_metadata()
                if right.task_execution_contract is not None
                else None
            ),
        }
        model_hints = _dedupe_tuple(
            (
                *model_hints,
                "Conflicting strict task-control contracts were produced; no tool fallback "
                "is allowed for this turn.",
            )
        )
    return ToolAccessPlan(
        visible_add=visible_add,
        visible_suppress=visible_suppress,
        tool_search_block=tool_search_block,
        execution_block=execution_block,
        reason=reason,
        matched_terms=matched,
        policies=policies,
        filter_error=filter_error,
        local_source_allowed=(
            False
            if strict
            else left.local_source_allowed or right.local_source_allowed
        ),
        policy_metadata=policy_metadata,
        task_plan_contract=task_plan_contract,
        task_execution_contract=task_execution_contract,
        strict_capability_scope=strict,
        context_retrieval_tools=context_retrieval_tools,
        context_retrieval_consumed=(
            left.context_retrieval_consumed
            or right.context_retrieval_consumed
        ),
        execution_dynamic_tools=execution_dynamic_tools,
        final_only=left.final_only or right.final_only,
        model_hints=model_hints,
    )


def _matched_terms(text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    normalized = (text or "").lower()
    return tuple(term for term in terms if term.lower() in normalized)


def _has_explicit_local_source_intent(text: str) -> bool:
    if _matched_terms(text, _EXPLICIT_LOCAL_SOURCE_TERMS):
        return True
    return bool(_PATH_RE.search(text or ""))


def _dedupe_tuple(items: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return tuple(result)
