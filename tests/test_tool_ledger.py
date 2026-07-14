from __future__ import annotations

import json

from agent.policies.tool_ledger import (
    ToolCallLedger,
    ToolCallRecord,
    classify_tool_name,
    extract_tool_result_facts,
    stable_args_hash,
)


def test_classifies_known_tool_classes() -> None:
    assert classify_tool_name("tool_search") == "discovery"
    assert classify_tool_name("search_docs") == "retrieval"
    assert classify_tool_name("recall_memory") == "retrieval"
    assert classify_tool_name("fetch_doc_chunk") == "evidence_expand"
    assert classify_tool_name("fetch_messages") == "evidence_expand"
    assert classify_tool_name("read_file") == "local_file"
    assert classify_tool_name("list_dir") == "local_file"
    assert classify_tool_name("shell") == "execution"
    assert classify_tool_name("memorize") == "memory_write"
    assert classify_tool_name("custom_tool") == "unknown"


def test_stable_args_hash_is_order_insensitive() -> None:
    left = stable_args_hash({"query": "agent runtime", "top_k": 5})
    right = stable_args_hash({"top_k": 5, "query": "agent runtime"})
    assert left == right
    assert len(left) == 16


def test_extracts_search_docs_facts() -> None:
    result = json.dumps(
        {
            "ok": True,
            "hit_count": 2,
            "hits": [
                {
                    "chunk_id": "c1",
                    "citation": "my_md/doc.md > Agent Runtime",
                }
            ],
        }
    )

    facts = extract_tool_result_facts("search_docs", result)

    assert facts.result_ok is True
    assert facts.hit_count == 2
    assert facts.result_has_evidence is True
    assert facts.result_has_citation is True
    assert facts.citation_refs == ("my_md/doc.md > Agent Runtime",)
    assert facts.chunk_keys == ("c1",)


def test_extracts_fetch_doc_chunk_facts() -> None:
    result = json.dumps(
        {
            "ok": True,
            "chunk": {
                "chunk_id": "c1",
                "citation": "my_md/doc.md > Agent Runtime",
                "text": "Agent runtime 负责管理 agent 的一次运行过程。",
            },
        }
    )

    facts = extract_tool_result_facts("fetch_doc_chunk", result)

    assert facts.result_ok is True
    assert facts.result_has_evidence is True
    assert facts.result_has_citation is True
    assert facts.hit_count is None
    assert facts.citation_refs == ("my_md/doc.md > Agent Runtime",)
    assert facts.chunk_keys == ("c1",)


def test_extracts_terminal_scope() -> None:
    facts = extract_tool_result_facts(
        "search_docs",
        json.dumps({"terminal_scope": "document_rag", "fallback_allowed": False}),
    )
    assert facts.terminal_scope == "document_rag"


def test_ledger_counts_and_summary() -> None:
    ledger = ToolCallLedger()
    args_hash = stable_args_hash({"query": "agent runtime"})
    ledger.add_record(
        ToolCallRecord(
            tool_name="search_docs",
            tool_class="retrieval",
            args_hash=args_hash,
            args_summary='{"query":"agent runtime"}',
            call_index=1,
            visible_before_call=True,
            result_ok=True,
            hit_count=1,
            citation_refs=("my_md/doc.md > Agent Runtime",),
            chunk_keys=("c1",),
            result_has_evidence=True,
            result_has_citation=True,
        )
    )
    ledger.add_record(
        ToolCallRecord(
            tool_name="search_docs",
            tool_class="retrieval",
            args_hash=args_hash,
            args_summary='{"query":"agent runtime"}',
            call_index=2,
            visible_before_call=True,
            decision_action="soft_stop",
            decision_reason="retrieval_budget_exceeded",
        )
    )

    assert ledger.count_tool("search_docs") == 2
    assert ledger.count_class("retrieval") == 2
    assert ledger.same_args_count("search_docs", args_hash) == 2
    assert ledger.has_successful_retrieval() is True
    assert ledger.has_citation_evidence() is True
    assert ledger.summary() == {
        "tool_calls": 2,
        "class_counts": {"retrieval": 2},
        "has_successful_retrieval": True,
        "has_citation_evidence": True,
    }


def test_ledger_preserves_execution_status_independently_of_result_ok() -> None:
    ledger = ToolCallLedger()
    for index, (status, result_ok) in enumerate(
        (("success", True), ("denied", True), ("error", False)),
        start=1,
    ):
        ledger.add_record(
            ToolCallRecord(
                tool_name="recall_memory",
                tool_class="retrieval",
                args_hash=str(index),
                args_summary="{}",
                call_index=index,
                visible_before_call=True,
                result_ok=result_ok,
                execution_status=status,
            )
        )

    assert [record.execution_status for record in ledger.records] == [
        "success",
        "denied",
        "error",
    ]
    assert [record.result_ok for record in ledger.records] == [True, True, False]
