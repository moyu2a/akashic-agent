from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent.policies.tool_budget import TaskIntent, ToolBoundaryDecision
from agent.policies.tool_ledger import ToolCallLedger, classify_tool_name


class EvidenceCompletionPolicy:
    def evaluate_call(
        self,
        *,
        intent: TaskIntent,
        ledger: ToolCallLedger,
        tool_name: str,
        arguments: Mapping[str, Any],
    ) -> ToolBoundaryDecision:
        if intent != "doc_qa_with_evidence":
            return ToolBoundaryDecision(action="allow", reason="non_doc_evidence_intent")

        tool_class = classify_tool_name(tool_name)
        if tool_class not in {"retrieval", "evidence_expand"}:
            return ToolBoundaryDecision(action="allow", reason="not_evidence_tool")

        if ledger.has_successful_retrieval() and ledger.has_citation_evidence():
            return ToolBoundaryDecision(
                action="soft_stop",
                reason="document_rag_evidence_complete",
                model_hint=(
                    "Document RAG already has retrieval hits and citation-bearing "
                    "chunk evidence. Answer now with existing citations."
                ),
            )

        return ToolBoundaryDecision(action="allow", reason="evidence_not_complete")
