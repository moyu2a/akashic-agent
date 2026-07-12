from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from agent.policies.evidence_completion import EvidenceCompletionPolicy
from agent.policies.tool_access import (
    ToolAccessContext,
    ToolAccessGateway,
    ToolAccessPlan,
)
from agent.policies.tool_budget import (
    TaskIntent,
    ToolBoundaryDecision,
    ToolBudgetPolicy,
    infer_task_intent,
)
from agent.policies.tool_ledger import (
    ToolCallLedger,
    ToolCallRecord,
    classify_tool_name,
    extract_tool_result_facts,
    stable_args_hash,
    summarize_args,
)

logger = logging.getLogger(__name__)


@dataclass
class ToolBoundaryContext:
    access_context: ToolAccessContext
    access_plan: ToolAccessPlan
    intent: TaskIntent
    ledger: ToolCallLedger = field(default_factory=ToolCallLedger)
    pending_hints: list[str] = field(default_factory=list)
    decisions: list[dict[str, object]] = field(default_factory=list)


@dataclass(frozen=True)
class BoundaryExecutionDecision:
    action: str
    reason: str
    execute: bool
    result_payload: str | None = None
    model_hint: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


class TurnToolBoundaryManager:
    def __init__(
        self,
        *,
        access_gateway: ToolAccessGateway | None = None,
        budget_policy: ToolBudgetPolicy | None = None,
        evidence_policy: EvidenceCompletionPolicy | None = None,
    ) -> None:
        self._access = access_gateway or ToolAccessGateway()
        self._budget = budget_policy or ToolBudgetPolicy()
        self._evidence = evidence_policy or EvidenceCompletionPolicy()

    def build_context(self, access_context: ToolAccessContext) -> ToolBoundaryContext:
        access_plan = self._access.build_plan(access_context)
        return ToolBoundaryContext(
            access_context=access_context,
            access_plan=access_plan,
            intent=infer_task_intent(access_context.user_text),
        )

    def compute_visible_names(self, context: ToolBoundaryContext) -> set[str]:
        return self._access.compute_visible_names(
            context.access_context,
            context.access_plan,
        )

    def filter_tool_search_matches(
        self,
        context: ToolBoundaryContext,
        tool_search_payload: str,
    ) -> tuple[str, tuple[str, ...]]:
        return self._access.filter_tool_search_matches(
            context.access_plan,
            tool_search_payload,
        )

    def merge_tool_search_unlocks(
        self,
        *,
        context: ToolBoundaryContext,
        current_visible: set[str],
        unlocked: set[str],
    ) -> set[str]:
        return self._access.merge_tool_search_unlocks(
            current_visible=current_visible,
            unlocked=unlocked,
            context=context.access_context,
            plan=context.access_plan,
        )

    def recent_decisions(
        self,
        context: ToolBoundaryContext,
    ) -> tuple[Mapping[str, object], ...]:
        return tuple(context.decisions)

    def observe_access_tool_result(
        self,
        context: ToolBoundaryContext,
        tool_name: str,
        result_text: str,
    ) -> None:
        context.access_plan = self._access.observe_tool_result(
            context.access_plan,
            tool_name,
            result_text,
        )

    def evaluate_tool_call(
        self,
        context: ToolBoundaryContext,
        *,
        tool_name: str,
        arguments: Mapping[str, Any],
        visible_names: set[str] | None,
    ) -> BoundaryExecutionDecision:
        gate = self._access.check_tool_call(
            context.access_plan,
            tool_name,
            dict(arguments),
        )
        if not gate.allowed:
            decision = BoundaryExecutionDecision(
                action="block",
                reason=gate.error_code or gate.reason or "tool_access_block",
                execute=False,
                result_payload=json.dumps(
                    {
                        "ok": False,
                        "error_code": gate.error_code,
                        "message": gate.message,
                        "recommended_tools": list(gate.recommended_tools),
                        "fallback_allowed": False,
                    },
                    ensure_ascii=False,
                ),
                metadata={"recommended_tools": list(gate.recommended_tools)},
            )
            self._record_decision(context, tool_name, decision)
            return decision

        evidence_decision = self._evidence.evaluate_call(
            intent=context.intent,
            ledger=context.ledger,
            tool_name=tool_name,
            arguments=arguments,
        )
        budget_decision = self._budget.evaluate_call(
            intent=context.intent,
            ledger=context.ledger,
            tool_name=tool_name,
            arguments=arguments,
            visible_names=visible_names,
        )
        final = _more_restrictive(evidence_decision, budget_decision)
        if final.action == "soft_stop":
            payload = _soft_stop_payload(final)
            if final.model_hint:
                context.pending_hints.append(final.model_hint)
            logger.info(
                "[tool_boundary] soft_stop tool=%s reason=%s",
                tool_name,
                final.reason,
            )
            decision = BoundaryExecutionDecision(
                action="soft_stop",
                reason=final.reason,
                execute=False,
                result_payload=payload,
                model_hint=final.model_hint,
                metadata=dict(final.metadata),
            )
            self._record_decision(context, tool_name, decision)
            return decision

        decision = BoundaryExecutionDecision(
            action=final.action,
            reason=final.reason,
            execute=True,
            model_hint=final.model_hint,
            metadata=dict(final.metadata),
        )
        self._record_decision(context, tool_name, decision)
        return decision

    def record_tool_result(
        self,
        context: ToolBoundaryContext,
        *,
        tool_name: str,
        arguments: Mapping[str, Any],
        result_text: str,
        visible_before_call: bool,
        decision_action: str,
        decision_reason: str,
        requested_unlocks: tuple[str, ...] = (),
        unlocked_tools: tuple[str, ...] = (),
        blocked_tools: tuple[str, ...] = (),
    ) -> None:
        facts = extract_tool_result_facts(tool_name, result_text)
        context.ledger.add_record(
            ToolCallRecord(
                tool_name=tool_name,
                tool_class=classify_tool_name(tool_name),
                args_hash=stable_args_hash(arguments),
                args_summary=summarize_args(arguments),
                call_index=context.ledger.next_call_index(),
                visible_before_call=visible_before_call,
                decision_action=decision_action,
                decision_reason=decision_reason,
                requested_unlocks=requested_unlocks,
                unlocked_tools=unlocked_tools,
                blocked_tools=blocked_tools,
                result_ok=facts.result_ok,
                hit_count=facts.hit_count,
                citation_refs=facts.citation_refs,
                chunk_keys=facts.chunk_keys,
                terminal_scope=facts.terminal_scope,
                result_summary=result_text[:240],
                result_has_evidence=facts.result_has_evidence,
                result_has_citation=facts.result_has_citation,
                result_error_code=facts.result_error_code,
            )
        )

    def consume_pending_hint(self, context: ToolBoundaryContext) -> str | None:
        if not context.pending_hints:
            return None
        return context.pending_hints.pop(0)

    def trace(self, context: ToolBoundaryContext) -> dict[str, object]:
        return {
            "intent": context.intent,
            "tool_access": {
                "reason": context.access_plan.reason,
                "policies": list(context.access_plan.policies),
                "visible_add": sorted(context.access_plan.visible_add),
                "visible_suppress": sorted(context.access_plan.visible_suppress),
                "tool_search_block": sorted(context.access_plan.tool_search_block),
                "execution_block": sorted(context.access_plan.execution_block),
                "matched_terms": list(context.access_plan.matched_terms),
                "filter_error": context.access_plan.filter_error,
            },
            "decisions": list(context.decisions),
            "ledger_summary": context.ledger.summary(),
        }

    def _record_decision(
        self,
        context: ToolBoundaryContext,
        tool_name: str,
        decision: BoundaryExecutionDecision,
    ) -> None:
        context.decisions.append(
            {
                "tool": tool_name,
                "action": decision.action,
                "reason": decision.reason,
                "execute": decision.execute,
                "metadata": dict(decision.metadata),
            }
        )


def _soft_stop_payload(decision: ToolBoundaryDecision) -> str:
    return json.dumps(
        {
            "ok": False,
            "error_code": "tool_boundary_soft_stop",
            "terminal_scope": "current_turn_tool_budget",
            "fallback_allowed": False,
            "recommended_action": "answer_from_existing_evidence",
            "message": decision.model_hint
            or "Current turn already has enough evidence; answer from existing evidence.",
            "reason": decision.reason,
        },
        ensure_ascii=False,
    )


_ACTION_RANK = {
    "allow": 0,
    "warn": 1,
    "require_reason": 2,
    "soft_stop": 3,
    "block": 4,
}


def _more_restrictive(
    left: ToolBoundaryDecision,
    right: ToolBoundaryDecision,
) -> ToolBoundaryDecision:
    if _ACTION_RANK[right.action] > _ACTION_RANK[left.action]:
        return right
    return left
