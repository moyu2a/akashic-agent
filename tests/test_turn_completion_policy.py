from __future__ import annotations

from agent.policies.tool_ledger import ToolCallLedger, ToolCallRecord
from agent.policies.turn_completion import TurnCompletionController


def _record(
    tool_name: str,
    *,
    tool_class: str,
    ok: bool = True,
    hit_count: int | None = None,
    has_citation: bool = False,
) -> ToolCallRecord:
    return ToolCallRecord(
        tool_name=tool_name,
        tool_class=tool_class,  # type: ignore[arg-type]
        args_hash=f"{tool_name}-hash",
        args_summary=f"{tool_name} args",
        call_index=1,
        visible_before_call=True,
        decision_action="allow",
        decision_reason="within_budget",
        result_ok=ok,
        hit_count=hit_count,
        citation_refs=("[doc.md > Heading]",) if has_citation else (),
        chunk_keys=("chunk-1",) if has_citation else (),
        result_has_evidence=ok,
        result_has_citation=has_citation,
    )


def _ledger_with_doc_evidence() -> ToolCallLedger:
    ledger = ToolCallLedger()
    ledger.add_record(
        _record("search_docs", tool_class="retrieval", ok=True, hit_count=3)
    )
    ledger.add_record(
        _record(
            "fetch_doc_chunk",
            tool_class="evidence_expand",
            ok=True,
            has_citation=True,
        )
    )
    return ledger


def test_doc_evidence_complete_soft_stop_switches_to_final_only() -> None:
    decision = TurnCompletionController().evaluate(
        intent="doc_qa_with_evidence",
        ledger=_ledger_with_doc_evidence(),
        local_source_allowed=False,
        boundary_decisions=[
            {
                "tool": "fetch_doc_chunk",
                "action": "soft_stop",
                "reason": "document_rag_evidence_complete",
                "execute": False,
            }
        ],
    )

    assert decision.action == "final_only"
    assert decision.reason == "document_rag_evidence_complete"
    assert "answer from the existing Document RAG evidence" in decision.model_hint
    assert decision.metadata["successful_retrieval"] is True
    assert decision.metadata["citation_evidence"] is True


def test_no_hit_retrieval_does_not_final_only() -> None:
    ledger = ToolCallLedger()
    ledger.add_record(
        _record("search_docs", tool_class="retrieval", ok=True, hit_count=0)
    )

    decision = TurnCompletionController().evaluate(
        intent="doc_qa_with_evidence",
        ledger=ledger,
        local_source_allowed=False,
        boundary_decisions=[
            {
                "tool": "search_docs",
                "action": "soft_stop",
                "reason": "document_rag_evidence_complete",
                "execute": False,
            }
        ],
    )

    assert decision.action == "continue_react"
    assert decision.reason == "evidence_not_complete"


def test_chunk_without_citation_does_not_final_only() -> None:
    ledger = ToolCallLedger()
    ledger.add_record(
        _record("search_docs", tool_class="retrieval", ok=True, hit_count=2)
    )
    ledger.add_record(
        _record(
            "fetch_doc_chunk",
            tool_class="evidence_expand",
            ok=True,
            has_citation=False,
        )
    )

    decision = TurnCompletionController().evaluate(
        intent="doc_qa_with_evidence",
        ledger=ledger,
        local_source_allowed=False,
        boundary_decisions=[
            {
                "tool": "fetch_doc_chunk",
                "action": "soft_stop",
                "reason": "document_rag_evidence_complete",
                "execute": False,
            }
        ],
    )

    assert decision.action == "continue_react"
    assert decision.reason == "evidence_not_complete"


def test_non_doc_intent_does_not_final_only() -> None:
    decision = TurnCompletionController().evaluate(
        intent="open_exploration",
        ledger=_ledger_with_doc_evidence(),
        local_source_allowed=False,
        boundary_decisions=[
            {
                "tool": "fetch_doc_chunk",
                "action": "soft_stop",
                "reason": "document_rag_evidence_complete",
                "execute": False,
            }
        ],
    )

    assert decision.action == "continue_react"
    assert decision.reason == "non_doc_evidence_intent"


def test_soft_stop_without_evidence_complete_reason_does_not_final_only() -> None:
    decision = TurnCompletionController().evaluate(
        intent="doc_qa_with_evidence",
        ledger=_ledger_with_doc_evidence(),
        local_source_allowed=False,
        boundary_decisions=[
            {
                "tool": "tool_search",
                "action": "soft_stop",
                "reason": "redundant_visible_tool_search",
                "execute": False,
            }
        ],
    )

    assert decision.action == "continue_react"
    assert decision.reason == "completion_signal_absent"


def test_local_source_allowed_does_not_final_only() -> None:
    decision = TurnCompletionController().evaluate(
        intent="doc_qa_with_evidence",
        ledger=_ledger_with_doc_evidence(),
        local_source_allowed=True,
        boundary_decisions=[
            {
                "tool": "fetch_doc_chunk",
                "action": "soft_stop",
                "reason": "document_rag_evidence_complete",
                "execute": False,
            }
        ],
    )

    assert decision.action == "continue_react"
    assert decision.reason == "local_source_allowed"
