from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any, Protocol

from agent.policies.doc_rag_intent import DOC_RAG_TOOL_NAMES, decide_doc_rag_preload

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


@dataclass(frozen=True)
class ToolAccessContext:
    session_key: str
    user_text: str
    always_on_tools: frozenset[str]
    lru_preloaded_tools: frozenset[str]
    disabled_tools: frozenset[str]
    turn_metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolAccessPlan:
    visible_add: frozenset[str] = frozenset()
    visible_suppress: frozenset[str] = frozenset()
    tool_search_block: frozenset[str] = frozenset()
    execution_block: frozenset[str] = frozenset()
    reason: str = "no_tool_access_policy"
    matched_terms: tuple[str, ...] = ()
    policies: tuple[str, ...] = ()
    filter_error: bool = False
    local_source_allowed: bool = False


@dataclass(frozen=True)
class ToolExecutionGateResult:
    allowed: bool
    error_code: str = ""
    message: str = ""
    recommended_tools: tuple[str, ...] = ()
    reason: str = ""


class ToolAccessPolicy(Protocol):
    name: str

    def build_plan(self, context: ToolAccessContext) -> ToolAccessPlan:
        ...

    def observe_tool_result(
        self,
        plan: ToolAccessPlan,
        tool_name: str,
        result_text: str,
    ) -> ToolAccessPlan:
        ...


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
        visible = (
            set(context.always_on_tools)
            | set(context.lru_preloaded_tools)
            | set(plan.visible_add)
        )
        visible -= set(context.disabled_tools)
        visible -= set(plan.visible_suppress)
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
            if isinstance(item, dict) and item.get("name") in plan.tool_search_block:
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
    ) -> ToolAccessPlan:
        updated = plan
        for policy in self._policies:
            updated = policy.observe_tool_result(updated, tool_name, result_text)
        return updated


def _merge_plans(left: ToolAccessPlan, right: ToolAccessPlan) -> ToolAccessPlan:
    if right == ToolAccessPlan():
        return left
    policies = _dedupe_tuple((*left.policies, *right.policies))
    matched = _dedupe_tuple((*left.matched_terms, *right.matched_terms))
    reason = right.reason if right.reason != "no_tool_access_policy" else left.reason
    return ToolAccessPlan(
        visible_add=left.visible_add | right.visible_add,
        visible_suppress=left.visible_suppress | right.visible_suppress,
        tool_search_block=left.tool_search_block | right.tool_search_block,
        execution_block=left.execution_block | right.execution_block,
        reason=reason,
        matched_terms=matched,
        policies=policies,
        filter_error=left.filter_error or right.filter_error,
        local_source_allowed=(
            left.local_source_allowed or right.local_source_allowed
        ),
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
