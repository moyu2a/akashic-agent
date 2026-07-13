from __future__ import annotations

import json

from agent.policies.evidence_contract import EvidenceContractManager
from agent.policies.tool_ledger import ToolCallLedger, ToolCallRecord


def _record(
    tool_name: str,
    *,
    result: dict,
    call_index: int,
) -> ToolCallRecord:
    if tool_name == "search_docs":
        tool_class = "retrieval"
    else:
        tool_class = "evidence_expand"
    return ToolCallRecord(
        tool_name=tool_name,
        tool_class=tool_class,  # type: ignore[arg-type]
        args_hash=f"{tool_name}-{call_index}",
        args_summary="{}",
        call_index=call_index,
        visible_before_call=True,
        decision_action="allow",
        decision_reason="within_budget",
        result_ok=result.get("ok") is True,
        hit_count=result.get("hit_count"),
        citation_refs=tuple(
            item["citation"]
            for item in result.get("hits", [])
            if isinstance(item, dict) and item.get("citation")
        )
        or tuple(
            [result["chunk"]["citation"]]
            if isinstance(result.get("chunk"), dict)
            and result["chunk"].get("citation")
            else []
        ),
        chunk_keys=tuple(
            item["chunk_id"]
            for item in result.get("hits", [])
            if isinstance(item, dict) and item.get("chunk_id")
        )
        or tuple(
            [result["chunk"]["chunk_id"]]
            if isinstance(result.get("chunk"), dict)
            and result["chunk"].get("chunk_id")
            else []
        ),
        result_has_evidence=True,
        result_has_citation=bool(
            result.get("hits") or (isinstance(result.get("chunk"), dict))
        ),
        result_summary=json.dumps(result, ensure_ascii=False),
    )


def test_document_rag_contract_separates_fetched_snippet_and_soft_stop() -> None:
    ledger = ToolCallLedger()
    ledger.add_record(
        _record(
            "search_docs",
            call_index=1,
            result={
                "ok": True,
                "hit_count": 2,
                "hits": [
                    {
                        "chunk_id": "c1",
                        "citation": "[doc.md > Agent Runtime]",
                        "snippet": "Agent runtime 负责管理 agent 的一次运行过程。",
                    },
                    {
                        "chunk_id": "c2",
                        "citation": "[doc.md > Tool Calling]",
                        "snippet": "工具调用用于让 agent 访问外部能力。",
                    },
                ],
            },
        )
    )
    ledger.add_record(
        _record(
            "fetch_doc_chunk",
            call_index=2,
            result={
                "ok": True,
                "chunk": {
                    "chunk_id": "c1",
                    "citation": "[doc.md > Agent Runtime]",
                    "content": "Agent runtime 负责管理 agent 的一次运行过程。",
                },
            },
        )
    )

    assessment = EvidenceContractManager().assess(
        user_text="根据项目文档回答agent runtime负责什么，并展开原文证据",
        intent="doc_qa_with_evidence",
        ledger=ledger,
        boundary_decisions=[
            {
                "tool": "fetch_doc_chunk",
                "action": "soft_stop",
                "reason": "document_rag_evidence_complete",
                "execute": False,
                "arguments": {"chunk_id": "c2"},
            }
        ],
    )

    by_level = {item.evidence_level: item for item in assessment.items}
    assert by_level["fetched_text"].chunk_id == "c1"
    assert by_level["retrieval_snippet"].chunk_id in {"c1", "c2"}
    assert any(
        item.evidence_level == "soft_stopped_candidate" and item.chunk_id == "c2"
        for item in assessment.items
    )
    assert assessment.sufficiency.tool_stop_allowed is True
    assert "Only successful fetch_doc_chunk results may be described" in (
        assessment.model_hint
    )
    assert "c2" in assessment.model_hint
    assert "Do not describe soft-stopped chunks as expanded original text" in (
        assessment.model_hint
    )


def test_document_rag_contract_prefers_full_result_text_over_truncated_summary() -> None:
    full_result = {
        "ok": True,
        "hit_count": 1,
        "hits": [
            {
                "chunk_id": "chunk-after-long-prefix",
                "citation": "[doc.md > Long Search Hit]",
                "snippet": "A" * 320,
            },
        ],
    }
    ledger = ToolCallLedger()
    ledger.add_record(
        ToolCallRecord(
            tool_name="search_docs",
            tool_class="retrieval",
            args_hash="search-1",
            args_summary="{}",
            call_index=1,
            visible_before_call=True,
            result_ok=True,
            hit_count=1,
            citation_refs=("[doc.md > Long Search Hit]",),
            chunk_keys=("chunk-after-long-prefix",),
            result_has_evidence=True,
            result_has_citation=True,
            result_summary=json.dumps(full_result, ensure_ascii=False)[:80],
            result_text=json.dumps(full_result, ensure_ascii=False),
        )
    )

    assessment = EvidenceContractManager().assess(
        user_text="根据项目文档回答agent runtime负责什么",
        intent="doc_qa_simple",
        ledger=ledger,
        boundary_decisions=[],
    )

    assert any(
        item.evidence_level == "retrieval_snippet"
        and item.chunk_id == "chunk-after-long-prefix"
        and item.text_preview == "A" * 240
        for item in assessment.items
    )


def test_original_evidence_requires_citation_on_fetched_text() -> None:
    ledger = ToolCallLedger()
    ledger.add_record(
        _record(
            "search_docs",
            call_index=1,
            result={
                "ok": True,
                "hit_count": 1,
                "hits": [
                    {
                        "chunk_id": "c1",
                        "citation": "[doc.md > Agent Runtime]",
                        "snippet": "Agent runtime 负责管理 agent 的一次运行过程。",
                    }
                ],
            },
        )
    )
    ledger.add_record(
        _record(
            "fetch_doc_chunk",
            call_index=2,
            result={
                "ok": True,
                "chunk": {
                    "chunk_id": "c1",
                    "content": "Agent runtime 负责管理 agent 的一次运行过程。",
                },
            },
        )
    )

    assessment = EvidenceContractManager().assess(
        user_text="根据项目文档回答agent runtime负责什么，并展开原文证据",
        intent="doc_qa_with_evidence",
        ledger=ledger,
        boundary_decisions=[],
    )

    assert assessment.sufficiency.tool_stop_allowed is False
    assert "fetched_text_citation" in assessment.sufficiency.missing_requirements
