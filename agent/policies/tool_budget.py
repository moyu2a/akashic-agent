from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from agent.policies.doc_rag_intent import decide_doc_rag_preload
from agent.policies.tool_ledger import (
    ToolCallLedger,
    ToolClass,
    classify_tool_name,
    stable_args_hash,
)

TaskIntent = Literal[
    "task_plan_state",
    "doc_qa_simple",
    "doc_qa_with_evidence",
    "memory_qa",
    "code_inspection",
    "no_tool",
    "open_exploration",
]
ToolBoundaryAction = Literal["allow", "warn", "soft_stop", "require_reason", "block"]


@dataclass(frozen=True)
class ToolBoundaryDecision:
    action: ToolBoundaryAction
    reason: str
    model_hint: str | None = None
    user_visible_message: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BudgetProfile:
    class_max_calls: Mapping[ToolClass, int]


_DOC_SIMPLE_PROFILE = BudgetProfile(
    class_max_calls={"retrieval": 1, "evidence_expand": 1}
)
_DOC_EVIDENCE_PROFILE = BudgetProfile(
    class_max_calls={"retrieval": 1, "evidence_expand": 2}
)


class ToolBudgetPolicy:
    def evaluate_call(
        self,
        *,
        intent: TaskIntent,
        ledger: ToolCallLedger,
        tool_name: str,
        arguments: Mapping[str, Any],
        visible_names: set[str] | None,
    ) -> ToolBoundaryDecision:
        select_targets = _select_targets(arguments)
        if (
            tool_name == "tool_search"
            and visible_names is not None
            and select_targets
            and select_targets <= visible_names
        ):
            return ToolBoundaryDecision(
                action="soft_stop",
                reason="redundant_visible_tool_search",
                model_hint=(
                    "The requested tools are already visible in this turn. "
                    "Use the visible tool directly or answer from existing evidence."
                ),
                metadata={"requested_tools": sorted(select_targets)},
            )

        profile = _profile_for_intent(intent)
        if profile is None:
            return ToolBoundaryDecision(action="allow", reason="no_budget_profile")

        tool_class = classify_tool_name(tool_name)
        max_calls = profile.class_max_calls.get(tool_class)
        if max_calls is None:
            return ToolBoundaryDecision(action="allow", reason="within_budget")

        if ledger.count_class(tool_class) >= max_calls:
            reason = (
                "retrieval_budget_exceeded"
                if tool_class == "retrieval"
                else "evidence_expand_budget_exceeded"
            )
            return ToolBoundaryDecision(
                action="soft_stop",
                reason=reason,
                model_hint="Current turn tool budget is enough; answer from existing evidence.",
                metadata={
                    "tool_class": tool_class,
                    "max_calls": max_calls,
                    "current_calls": ledger.count_class(tool_class),
                },
            )

        args_hash = stable_args_hash(arguments)
        if ledger.same_args_count(tool_name, args_hash) > 0:
            return ToolBoundaryDecision(
                action="soft_stop",
                reason="repeated_same_args",
                model_hint="This repeats a previous tool call; answer from existing evidence.",
                metadata={"tool_name": tool_name},
            )

        return ToolBoundaryDecision(action="allow", reason="within_budget")


def infer_task_intent(user_text: str) -> TaskIntent:
    text = user_text or ""
    if "不用工具" in text or "不要调用工具" in text:
        return "no_tool"
    doc_decision = decide_doc_rag_preload(text)
    if doc_decision.preload_search_docs and doc_decision.preload_fetch_doc_chunk:
        return "doc_qa_with_evidence"
    if doc_decision.preload_search_docs:
        return "doc_qa_simple"
    if "记忆" in text or "session" in text or "会话" in text:
        return "memory_qa"
    if "源码" in text or "读取" in text or ".py" in text:
        return "code_inspection"
    return "open_exploration"


def _profile_for_intent(intent: TaskIntent) -> BudgetProfile | None:
    if intent == "doc_qa_simple":
        return _DOC_SIMPLE_PROFILE
    if intent == "doc_qa_with_evidence":
        return _DOC_EVIDENCE_PROFILE
    return None


def _select_targets(arguments: Mapping[str, Any]) -> set[str]:
    query = str(arguments.get("query") or "")
    if not query.startswith("select:"):
        return set()
    raw = query.removeprefix("select:")
    return {item.strip() for item in raw.split(",") if item.strip()}
