from __future__ import annotations

from collections.abc import Mapping, Sequence

from agent.policies.evidence_contract import EvidenceAssessment
from agent.policies.task_plan_completion import TaskPlanCompletionPolicy
from agent.policies.task_plan_contract import TaskPlanTurnContract
from agent.policies.task_execution_completion import TaskExecutionCompletionPolicy
from agent.policies.task_execution_contract import TaskExecutionTurnContract
from agent.policies.tool_budget import TaskIntent
from agent.policies.tool_ledger import ToolCallLedger
from agent.policies.turn_completion_types import (
    TurnCompletionAction,
    TurnCompletionDecision,
)
from agent.task_plan.execution_models import TaskExecutionSnapshot


class TurnCompletionController:
    def __init__(
        self,
        *,
        task_plan_policy: TaskPlanCompletionPolicy | None = None,
        task_execution_policy: TaskExecutionCompletionPolicy | None = None,
    ) -> None:
        self._task_plan = task_plan_policy or TaskPlanCompletionPolicy()
        self._task_execution = task_execution_policy or TaskExecutionCompletionPolicy()

    def evaluate(
        self,
        *,
        intent: TaskIntent,
        ledger: ToolCallLedger,
        boundary_decisions: Sequence[Mapping[str, object]],
        evidence_assessment: EvidenceAssessment | None = None,
        local_source_allowed: bool = False,
        proactive_allowed: bool = False,
        task_plan_contract: TaskPlanTurnContract | None = None,
        task_execution_contract: TaskExecutionTurnContract | None = None,
        task_execution_snapshot: TaskExecutionSnapshot | None = None,
        tool_capabilities: Mapping[str, frozenset[str]] | None = None,
    ) -> TurnCompletionDecision:
        task_execution_decision = self._task_execution.evaluate(
            contract=task_execution_contract,
            snapshot=task_execution_snapshot,
            ledger=ledger,
            tool_capabilities=tool_capabilities or {},
        )
        if task_execution_decision is not None:
            return TurnCompletionDecision(
                action=task_execution_decision.action,
                reason=task_execution_decision.reason,
                model_hint=task_execution_decision.model_hint,
                metadata={
                    **self._metadata(ledger, boundary_decisions),
                    **dict(task_execution_decision.metadata),
                },
            )
        task_plan_decision = self._task_plan.evaluate(
            contract=task_plan_contract,
            ledger=ledger,
            tool_capabilities=tool_capabilities or {},
        )
        if task_plan_decision is not None:
            return TurnCompletionDecision(
                action=task_plan_decision.action,
                reason=task_plan_decision.reason,
                model_hint=task_plan_decision.model_hint,
                metadata={
                    **self._metadata(ledger, boundary_decisions),
                    **dict(task_plan_decision.metadata),
                },
            )

        if local_source_allowed:
            return TurnCompletionDecision(
                action="continue_react",
                reason="local_source_allowed",
                metadata=self._metadata(ledger, boundary_decisions),
            )

        if proactive_allowed and evidence_assessment is not None:
            if evidence_assessment.sufficiency.tool_stop_allowed:
                if intent == "doc_qa_simple":
                    return TurnCompletionDecision(
                        action="final_only",
                        reason="document_rag_retrieval_complete",
                        model_hint=(
                            "Document RAG retrieval is complete for this turn. "
                            "Do not request more tools. Answer from the existing "
                            "search_docs evidence and include available citations."
                        ),
                        metadata={
                            **self._metadata(ledger, boundary_decisions),
                            "proactive": True,
                            "evidence_reason": (
                                evidence_assessment.sufficiency.reason
                            ),
                        },
                    )
                if intent == "doc_qa_with_evidence":
                    return TurnCompletionDecision(
                        action="final_only",
                        reason="document_rag_evidence_complete",
                        model_hint=(
                            "Document RAG evidence is complete for this turn. "
                            "Do not request more tools. Answer from the existing "
                            "Document RAG evidence and include available citations."
                        ),
                        metadata={
                            **self._metadata(ledger, boundary_decisions),
                            "proactive": True,
                            "evidence_reason": (
                                evidence_assessment.sufficiency.reason
                            ),
                        },
                    )

        if intent != "doc_qa_with_evidence":
            return TurnCompletionDecision(
                action="continue_react",
                reason="non_doc_evidence_intent",
                metadata=self._metadata(ledger, boundary_decisions),
            )

        has_signal = any(
            item.get("action") == "soft_stop"
            and item.get("reason") == "document_rag_evidence_complete"
            and item.get("execute") is False
            for item in boundary_decisions
        )
        if not has_signal:
            return TurnCompletionDecision(
                action="continue_react",
                reason="completion_signal_absent",
                metadata=self._metadata(ledger, boundary_decisions),
            )

        if not ledger.has_successful_retrieval() or not ledger.has_citation_evidence():
            return TurnCompletionDecision(
                action="continue_react",
                reason="evidence_not_complete",
                metadata=self._metadata(ledger, boundary_decisions),
            )

        return TurnCompletionDecision(
            action="final_only",
            reason="document_rag_evidence_complete",
            model_hint=(
                "Document RAG evidence is complete for this turn. Do not request "
                "more tools. answer from the existing Document RAG evidence and "
                "include the available citations."
            ),
            metadata=self._metadata(ledger, boundary_decisions),
        )

    def _metadata(
        self,
        ledger: ToolCallLedger,
        boundary_decisions: Sequence[Mapping[str, object]],
    ) -> dict[str, object]:
        return {
            "successful_retrieval": ledger.has_successful_retrieval(),
            "citation_evidence": ledger.has_citation_evidence(),
            "soft_stop_count": sum(
                1 for item in boundary_decisions if item.get("action") == "soft_stop"
            ),
        }
