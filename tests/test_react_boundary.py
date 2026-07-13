from __future__ import annotations

import json

from agent.policies.evidence_contract import (
    EvidenceAssessment,
    EvidenceSufficiency,
    TaskEvidenceRequirement,
)
from agent.policies.react_boundary import ReactBoundaryManager
from agent.policies.tool_ledger import ToolCallLedger, ToolCallRecord


def _record(
    tool_name: str,
    *,
    tool_class: str,
    call_index: int,
    result_ok: bool = True,
    hit_count: int | None = None,
    citation_refs: tuple[str, ...] = (),
    chunk_keys: tuple[str, ...] = (),
) -> ToolCallRecord:
    return ToolCallRecord(
        tool_name=tool_name,
        tool_class=tool_class,  # type: ignore[arg-type]
        args_hash=f"{tool_name}-{call_index}",
        args_summary="{}",
        call_index=call_index,
        visible_before_call=True,
        result_ok=result_ok,
        hit_count=hit_count,
        citation_refs=citation_refs,
        chunk_keys=chunk_keys,
        result_has_evidence=result_ok,
        result_has_citation=bool(citation_refs),
    )


def _assessment_ready(task_type: str = "doc_qa_with_evidence") -> EvidenceAssessment:
    return EvidenceAssessment(
        requirement=TaskEvidenceRequirement(task_type=task_type),
        items=(),
        sufficiency=EvidenceSufficiency(
            tool_stop_allowed=True,
            answer_ready=True,
            reason="requirements_satisfied",
        ),
        constraints=(),
        model_hint="Evidence contract for this answer:",
    )


def _assessment_missing() -> EvidenceAssessment:
    return EvidenceAssessment(
        requirement=TaskEvidenceRequirement(task_type="doc_qa_with_evidence"),
        items=(),
        sufficiency=EvidenceSufficiency(
            tool_stop_allowed=False,
            answer_ready=True,
            reason="missing_evidence",
            missing_requirements=("fetched_text",),
        ),
        constraints=(),
        model_hint="Evidence contract for this answer:",
    )


def test_after_tool_result_recommends_final_only_from_assessment() -> None:
    decision = ReactBoundaryManager().evaluate_after_tool_result(
        intent="doc_qa_with_evidence",
        ledger=ToolCallLedger(),
        evidence_assessment=_assessment_ready(),
        local_source_allowed=False,
    )

    assert decision.recommend_final_only is True
    assert decision.reason == "document_rag_evidence_complete"
    assert decision.recommended_suppress == frozenset({"search_docs", "fetch_doc_chunk"})
    assert decision.metadata["evidence_reason"] == "requirements_satisfied"


def test_after_tool_result_does_not_final_only_for_local_source() -> None:
    decision = ReactBoundaryManager().evaluate_after_tool_result(
        intent="doc_qa_with_evidence",
        ledger=ToolCallLedger(),
        evidence_assessment=_assessment_ready(),
        local_source_allowed=True,
    )

    assert decision.recommend_final_only is False
    assert decision.reason == "local_source_allowed"
    assert decision.recommended_suppress == frozenset()


def test_batch_skip_after_first_successful_fetch_and_ready_evidence() -> None:
    ledger = ToolCallLedger()
    ledger.add_record(
        _record(
            "fetch_doc_chunk",
            tool_class="evidence_expand",
            call_index=1,
            citation_refs=("my_md/doc.md > Agent Runtime",),
            chunk_keys=("c1",),
        )
    )

    decision = ReactBoundaryManager().evaluate_batch_tool_call(
        intent="doc_qa_with_evidence",
        tool_name="fetch_doc_chunk",
        tool_batch_index=1,
        ledger=ledger,
        evidence_assessment=_assessment_ready(),
        local_source_allowed=False,
    )

    assert decision.action == "skip"
    assert decision.reason == "document_rag_batch_evidence_complete"
    assert decision.status == "batch_skipped_by_react_boundary"
    payload = json.loads(decision.result_payload)
    assert payload["error_code"] == "react_boundary_batch_skip"
    assert payload["terminal_scope"] == "document_rag"


def test_batch_does_not_skip_when_evidence_missing() -> None:
    ledger = ToolCallLedger()
    ledger.add_record(
        _record(
            "fetch_doc_chunk",
            tool_class="evidence_expand",
            call_index=1,
            citation_refs=("my_md/doc.md > Agent Runtime",),
            chunk_keys=("c1",),
        )
    )

    decision = ReactBoundaryManager().evaluate_batch_tool_call(
        intent="doc_qa_with_evidence",
        tool_name="fetch_doc_chunk",
        tool_batch_index=1,
        ledger=ledger,
        evidence_assessment=_assessment_missing(),
        local_source_allowed=False,
    )

    assert decision.action == "execute"
    assert decision.reason == "evidence_incomplete"


def test_batch_does_not_skip_for_local_source() -> None:
    ledger = ToolCallLedger()
    ledger.add_record(
        _record("fetch_doc_chunk", tool_class="evidence_expand", call_index=1)
    )

    decision = ReactBoundaryManager().evaluate_batch_tool_call(
        intent="doc_qa_with_evidence",
        tool_name="fetch_doc_chunk",
        tool_batch_index=1,
        ledger=ledger,
        evidence_assessment=_assessment_ready(),
        local_source_allowed=True,
    )

    assert decision.action == "execute"
    assert decision.reason == "local_source_allowed"
