from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from agent.policies.evidence_contract import EvidenceAssessment
from agent.policies.tool_budget import TaskIntent
from agent.policies.tool_ledger import ToolCallLedger

DOC_RAG_RUNTIME_TOOLS = frozenset({"search_docs", "fetch_doc_chunk"})

BatchToolAction = Literal["execute", "skip"]


@dataclass(frozen=True)
class BatchToolDecision:
    action: BatchToolAction
    reason: str
    status: str = ""
    result_payload: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ReactBoundaryDecision:
    recommend_final_only: bool
    reason: str
    model_hint: str = ""
    recommended_suppress: frozenset[str] = frozenset()
    metadata: Mapping[str, object] = field(default_factory=dict)


class ReactBoundaryManager:
    def evaluate_after_tool_result(
        self,
        *,
        intent: TaskIntent,
        ledger: ToolCallLedger,
        evidence_assessment: EvidenceAssessment | None,
        local_source_allowed: bool = False,
    ) -> ReactBoundaryDecision:
        metadata = _metadata(ledger, evidence_assessment)
        if local_source_allowed:
            return ReactBoundaryDecision(
                recommend_final_only=False,
                reason="local_source_allowed",
                metadata=metadata,
            )
        if evidence_assessment is None:
            return ReactBoundaryDecision(
                recommend_final_only=False,
                reason="evidence_assessment_absent",
                metadata=metadata,
            )
        if not evidence_assessment.sufficiency.tool_stop_allowed:
            return ReactBoundaryDecision(
                recommend_final_only=False,
                reason="evidence_incomplete",
                metadata=metadata,
            )
        if intent == "doc_qa_simple":
            return ReactBoundaryDecision(
                recommend_final_only=True,
                reason="document_rag_retrieval_complete",
                model_hint=(
                    "Document RAG retrieval is complete for this turn. "
                    "Do not request more tools. Answer from the existing "
                    "search_docs evidence and include available citations."
                ),
                recommended_suppress=DOC_RAG_RUNTIME_TOOLS,
                metadata=metadata,
            )
        if intent == "doc_qa_with_evidence":
            return ReactBoundaryDecision(
                recommend_final_only=True,
                reason="document_rag_evidence_complete",
                model_hint=(
                    "Document RAG evidence is complete for this turn. "
                    "Do not request more tools. Answer from the existing "
                    "Document RAG evidence and include available citations."
                ),
                recommended_suppress=DOC_RAG_RUNTIME_TOOLS,
                metadata=metadata,
            )
        return ReactBoundaryDecision(
            recommend_final_only=False,
            reason="non_doc_rag_intent",
            metadata=metadata,
        )

    def evaluate_batch_tool_call(
        self,
        *,
        intent: TaskIntent,
        tool_name: str,
        tool_batch_index: int,
        ledger: ToolCallLedger,
        evidence_assessment: EvidenceAssessment | None,
        local_source_allowed: bool = False,
    ) -> BatchToolDecision:
        if local_source_allowed:
            return BatchToolDecision(action="execute", reason="local_source_allowed")
        if tool_name not in DOC_RAG_RUNTIME_TOOLS:
            return BatchToolDecision(action="execute", reason="non_doc_rag_tool")
        if tool_batch_index == 0:
            return BatchToolDecision(action="execute", reason="first_batch_tool")
        if evidence_assessment is None:
            return BatchToolDecision(action="execute", reason="evidence_assessment_absent")
        if not evidence_assessment.sufficiency.tool_stop_allowed:
            return BatchToolDecision(action="execute", reason="evidence_incomplete")

        should_skip = False
        if (
            intent == "doc_qa_with_evidence"
            and tool_name == "fetch_doc_chunk"
            and _successful_tool_count(ledger, "fetch_doc_chunk") > 0
        ):
            should_skip = True
        elif (
            intent == "doc_qa_simple"
            and tool_name in DOC_RAG_RUNTIME_TOOLS
            and ledger.has_successful_retrieval()
            and ledger.has_citation_evidence()
        ):
            should_skip = True

        if not should_skip:
            return BatchToolDecision(action="execute", reason="within_batch_budget")

        return BatchToolDecision(
            action="skip",
            reason="document_rag_batch_evidence_complete",
            status="batch_skipped_by_react_boundary",
            result_payload=_batch_skip_payload(),
            metadata={
                "tool_name": tool_name,
                "tool_batch_index": tool_batch_index,
            },
        )


def _successful_tool_count(ledger: ToolCallLedger, tool_name: str) -> int:
    return sum(
        1
        for record in ledger.records
        if record.tool_name == tool_name and record.result_ok
    )


def _metadata(
    ledger: ToolCallLedger,
    evidence_assessment: EvidenceAssessment | None,
) -> dict[str, object]:
    metadata: dict[str, object] = {
        "successful_retrieval": ledger.has_successful_retrieval(),
        "citation_evidence": ledger.has_citation_evidence(),
        "tool_calls": len(ledger.records),
    }
    if evidence_assessment is not None:
        metadata["evidence_reason"] = evidence_assessment.sufficiency.reason
    return metadata


def _batch_skip_payload() -> str:
    return json.dumps(
        {
            "ok": False,
            "error_code": "react_boundary_batch_skip",
            "terminal_scope": "document_rag",
            "message": (
                "This Document RAG tool call was skipped because enough evidence "
                "was already collected in this assistant tool-call batch. Answer "
                "from the successful search_docs/fetch_doc_chunk evidence already "
                "available."
            ),
            "action": "answer_from_existing_evidence",
        },
        ensure_ascii=False,
    )
