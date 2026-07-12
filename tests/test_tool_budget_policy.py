from __future__ import annotations

from agent.policies.tool_budget import (
    ToolBoundaryDecision,
    ToolBudgetPolicy,
    infer_task_intent,
)
from agent.policies.tool_ledger import (
    ToolCallLedger,
    ToolCallRecord,
    classify_tool_name,
    stable_args_hash,
)


def _record(
    tool_name: str,
    args: dict,
    *,
    ok: bool = True,
    hit_count: int | None = None,
) -> ToolCallRecord:
    return ToolCallRecord(
        tool_name=tool_name,
        tool_class=classify_tool_name(tool_name),
        args_hash=stable_args_hash(args),
        args_summary=str(args),
        call_index=1,
        visible_before_call=True,
        result_ok=ok,
        hit_count=hit_count,
        result_has_evidence=ok and ((hit_count or 0) > 0),
    )


def test_infers_doc_qa_with_evidence_intent() -> None:
    assert (
        infer_task_intent("根据项目文档回答agent runtime负责什么，并展开原文证据")
        == "doc_qa_with_evidence"
    )


def test_infers_doc_qa_simple_intent() -> None:
    assert infer_task_intent("请从文档知识库中检索agent runtime负责什么") == "doc_qa_simple"


def test_infers_open_exploration_for_non_doc_prompt() -> None:
    assert infer_task_intent("帮我分析这个项目下一步怎么做") == "open_exploration"


def test_redundant_tool_search_for_visible_target_soft_stops() -> None:
    decision = ToolBudgetPolicy().evaluate_call(
        intent="doc_qa_with_evidence",
        ledger=ToolCallLedger(),
        tool_name="tool_search",
        arguments={"query": "select:search_docs,fetch_doc_chunk"},
        visible_names={"tool_search", "search_docs", "fetch_doc_chunk"},
    )

    assert decision.action == "soft_stop"
    assert decision.reason == "redundant_visible_tool_search"
    assert "already visible" in (decision.model_hint or "")


def test_second_similar_search_docs_soft_stops_after_successful_retrieval() -> None:
    ledger = ToolCallLedger()
    ledger.add_record(_record("search_docs", {"query": "agent runtime"}, hit_count=3))

    decision = ToolBudgetPolicy().evaluate_call(
        intent="doc_qa_with_evidence",
        ledger=ledger,
        tool_name="search_docs",
        arguments={"query": "agent runtime"},
        visible_names={"search_docs", "fetch_doc_chunk"},
    )

    assert decision.action == "soft_stop"
    assert decision.reason == "retrieval_budget_exceeded"


def test_third_fetch_doc_chunk_soft_stops() -> None:
    ledger = ToolCallLedger()
    ledger.add_record(_record("fetch_doc_chunk", {"chunk_id": "c1"}))
    ledger.add_record(_record("fetch_doc_chunk", {"chunk_id": "c2"}))

    decision = ToolBudgetPolicy().evaluate_call(
        intent="doc_qa_with_evidence",
        ledger=ledger,
        tool_name="fetch_doc_chunk",
        arguments={"chunk_id": "c3"},
        visible_names={"search_docs", "fetch_doc_chunk"},
    )

    assert decision.action == "soft_stop"
    assert decision.reason == "evidence_expand_budget_exceeded"


def test_budget_allows_first_required_doc_rag_calls() -> None:
    policy = ToolBudgetPolicy()
    ledger = ToolCallLedger()

    first_search = policy.evaluate_call(
        intent="doc_qa_with_evidence",
        ledger=ledger,
        tool_name="search_docs",
        arguments={"query": "agent runtime"},
        visible_names={"search_docs", "fetch_doc_chunk"},
    )
    first_fetch = policy.evaluate_call(
        intent="doc_qa_with_evidence",
        ledger=ledger,
        tool_name="fetch_doc_chunk",
        arguments={"chunk_id": "c1"},
        visible_names={"search_docs", "fetch_doc_chunk"},
    )

    assert first_search == ToolBoundaryDecision(action="allow", reason="within_budget")
    assert first_fetch == ToolBoundaryDecision(action="allow", reason="within_budget")
