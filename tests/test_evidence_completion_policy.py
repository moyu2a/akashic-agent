from __future__ import annotations

from agent.policies.evidence_completion import EvidenceCompletionPolicy
from agent.policies.tool_ledger import ToolCallLedger, ToolCallRecord


def test_evidence_complete_soft_stops_additional_expansion() -> None:
    ledger = ToolCallLedger()
    ledger.add_record(
        ToolCallRecord(
            tool_name="search_docs",
            tool_class="retrieval",
            args_hash="h1",
            args_summary="{}",
            call_index=1,
            visible_before_call=True,
            result_ok=True,
            hit_count=1,
            result_has_evidence=True,
        )
    )
    ledger.add_record(
        ToolCallRecord(
            tool_name="fetch_doc_chunk",
            tool_class="evidence_expand",
            args_hash="h2",
            args_summary="{}",
            call_index=2,
            visible_before_call=True,
            result_ok=True,
            citation_refs=("my_md/doc.md > Agent Runtime",),
            chunk_keys=("c1",),
            result_has_evidence=True,
            result_has_citation=True,
        )
    )

    decision = EvidenceCompletionPolicy().evaluate_call(
        intent="doc_qa_with_evidence",
        ledger=ledger,
        tool_name="fetch_doc_chunk",
        arguments={"chunk_id": "c2"},
    )

    assert decision.action == "soft_stop"
    assert decision.reason == "document_rag_evidence_complete"


def test_no_hit_retrieval_does_not_soft_stop() -> None:
    ledger = ToolCallLedger()
    ledger.add_record(
        ToolCallRecord(
            tool_name="search_docs",
            tool_class="retrieval",
            args_hash="h1",
            args_summary="{}",
            call_index=1,
            visible_before_call=True,
            result_ok=True,
            hit_count=0,
        )
    )

    decision = EvidenceCompletionPolicy().evaluate_call(
        intent="doc_qa_with_evidence",
        ledger=ledger,
        tool_name="fetch_doc_chunk",
        arguments={"chunk_id": "c1"},
    )

    assert decision.action == "allow"
    assert decision.reason == "evidence_not_complete"


def test_search_hit_citation_without_chunk_does_not_soft_stop() -> None:
    ledger = ToolCallLedger()
    ledger.add_record(
        ToolCallRecord(
            tool_name="search_docs",
            tool_class="retrieval",
            args_hash="h1",
            args_summary="{}",
            call_index=1,
            visible_before_call=True,
            result_ok=True,
            hit_count=1,
            citation_refs=("my_md/doc.md > Agent Runtime",),
            result_has_evidence=True,
            result_has_citation=True,
        )
    )

    decision = EvidenceCompletionPolicy().evaluate_call(
        intent="doc_qa_with_evidence",
        ledger=ledger,
        tool_name="fetch_doc_chunk",
        arguments={"chunk_id": "c1"},
    )

    assert decision.action == "allow"
    assert decision.reason == "evidence_not_complete"


def test_chunk_without_citation_does_not_soft_stop() -> None:
    ledger = ToolCallLedger()
    ledger.add_record(
        ToolCallRecord(
            tool_name="search_docs",
            tool_class="retrieval",
            args_hash="h1",
            args_summary="{}",
            call_index=1,
            visible_before_call=True,
            result_ok=True,
            hit_count=1,
            result_has_evidence=True,
        )
    )
    ledger.add_record(
        ToolCallRecord(
            tool_name="fetch_doc_chunk",
            tool_class="evidence_expand",
            args_hash="h2",
            args_summary="{}",
            call_index=2,
            visible_before_call=True,
            result_ok=True,
            result_has_evidence=True,
            result_has_citation=False,
        )
    )

    decision = EvidenceCompletionPolicy().evaluate_call(
        intent="doc_qa_with_evidence",
        ledger=ledger,
        tool_name="fetch_doc_chunk",
        arguments={"chunk_id": "c2"},
    )

    assert decision.action == "allow"
    assert decision.reason == "evidence_not_complete"


def test_broader_exploration_intent_does_not_soft_stop() -> None:
    ledger = ToolCallLedger()
    ledger.add_record(
        ToolCallRecord(
            tool_name="search_docs",
            tool_class="retrieval",
            args_hash="h1",
            args_summary="{}",
            call_index=1,
            visible_before_call=True,
            result_ok=True,
            hit_count=1,
            result_has_evidence=True,
            result_has_citation=True,
        )
    )

    decision = EvidenceCompletionPolicy().evaluate_call(
        intent="open_exploration",
        ledger=ledger,
        tool_name="fetch_doc_chunk",
        arguments={"chunk_id": "c2"},
    )

    assert decision.action == "allow"
    assert decision.reason == "non_doc_evidence_intent"
