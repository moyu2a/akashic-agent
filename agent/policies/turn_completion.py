from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from agent.policies.tool_budget import TaskIntent
from agent.policies.tool_ledger import ToolCallLedger

TurnCompletionAction = Literal["continue_react", "final_only"]


@dataclass(frozen=True)
class TurnCompletionDecision:
    action: TurnCompletionAction
    reason: str
    model_hint: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)


class TurnCompletionController:
    def evaluate(
        self,
        *,
        intent: TaskIntent,
        ledger: ToolCallLedger,
        boundary_decisions: Sequence[Mapping[str, object]],
        local_source_allowed: bool = False,
    ) -> TurnCompletionDecision:
        if local_source_allowed:
            return TurnCompletionDecision(
                action="continue_react",
                reason="local_source_allowed",
                metadata=self._metadata(ledger, boundary_decisions),
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
