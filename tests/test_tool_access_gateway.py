from __future__ import annotations

import json

from agent.policies.tool_access import ToolAccessContext, ToolAccessGateway


LOCAL_TOOLS = {"shell", "read_file", "list_dir"}
DOC_RAG_TOOLS = {"search_docs", "fetch_doc_chunk"}


def _ctx(
    text: str,
    *,
    always_on: set[str] | None = None,
    lru: set[str] | None = None,
    disabled: set[str] | None = None,
) -> ToolAccessContext:
    return ToolAccessContext(
        session_key="cli:1",
        user_text=text,
        always_on_tools=frozenset(always_on or {"tool_search", *LOCAL_TOOLS}),
        lru_preloaded_tools=frozenset(lru or set()),
        disabled_tools=frozenset(disabled or set()),
    )


def test_strong_doc_evidence_prefers_rag_and_blocks_local_tools() -> None:
    gateway = ToolAccessGateway()
    ctx = _ctx("根据项目文档回答agent runtime负责什么，并展开原文证据")

    plan = gateway.build_plan(ctx)
    visible = gateway.compute_visible_names(ctx, plan)

    assert DOC_RAG_TOOLS <= plan.visible_add
    assert LOCAL_TOOLS <= plan.visible_suppress
    assert LOCAL_TOOLS <= plan.tool_search_block
    assert LOCAL_TOOLS <= plan.execution_block
    assert DOC_RAG_TOOLS <= visible
    assert visible.isdisjoint(LOCAL_TOOLS)


def test_explicit_source_request_allows_local_tools() -> None:
    gateway = ToolAccessGateway()
    ctx = _ctx("根据项目文档和源码回答，请读取 agent/core/passive_turn.py")

    plan = gateway.build_plan(ctx)
    visible = gateway.compute_visible_names(ctx, plan)

    assert "search_docs" in plan.visible_add
    assert "read_file" not in plan.visible_suppress
    assert "read_file" not in plan.execution_block
    assert "read_file" in visible


def test_session_meta_suppresses_doc_rag_lru_without_mutating_lru() -> None:
    gateway = ToolAccessGateway()
    ctx = _ctx(
        "刚才第二个问题你查了哪些工具？",
        lru={"search_docs", "fetch_doc_chunk", "recall_memory"},
    )

    plan = gateway.build_plan(ctx)
    visible = gateway.compute_visible_names(ctx, plan)

    assert DOC_RAG_TOOLS <= plan.visible_suppress
    assert "recall_memory" in visible
    assert visible.isdisjoint(DOC_RAG_TOOLS)
    assert ctx.lru_preloaded_tools == frozenset(
        {"search_docs", "fetch_doc_chunk", "recall_memory"}
    )


def test_tool_search_filter_removes_blocked_matches_from_model_payload() -> None:
    gateway = ToolAccessGateway()
    ctx = _ctx("根据项目文档回答agent runtime负责什么，并展开原文证据")
    plan = gateway.build_plan(ctx)
    payload = json.dumps(
        {
            "matched": [
                {"name": "read_file", "summary": "read files"},
                {"name": "fetch_doc_chunk", "summary": "fetch chunks"},
            ]
        }
    )

    filtered, blocked = gateway.filter_tool_search_matches(plan, payload)
    data = json.loads(filtered)

    assert blocked == ("read_file",)
    assert [item["name"] for item in data["matched"]] == ["fetch_doc_chunk"]
    assert data["blocked_by_tool_access_gateway"] == ["read_file"]


def test_execution_gate_blocks_doc_rag_local_file_fallback() -> None:
    gateway = ToolAccessGateway()
    ctx = _ctx("根据项目文档回答agent runtime负责什么，并展开原文证据")
    plan = gateway.build_plan(ctx)

    result = gateway.check_tool_call(plan, "read_file", {"path": "README.md"})

    assert result.allowed is False
    assert result.error_code == "tool_blocked_by_doc_rag_policy"
    assert result.recommended_tools == ("search_docs", "fetch_doc_chunk")


def test_terminal_doc_rag_result_blocks_later_local_fallback() -> None:
    gateway = ToolAccessGateway()
    ctx = _ctx("根据项目文档和源码回答 agent runtime 负责什么")
    plan = gateway.build_plan(ctx)
    assert plan.visible_suppress.isdisjoint(LOCAL_TOOLS)

    updated = gateway.observe_tool_result(
        plan,
        "search_docs",
        json.dumps({"terminal_scope": "document_rag", "fallback_allowed": False}),
    )

    assert LOCAL_TOOLS <= updated.tool_search_block
    assert LOCAL_TOOLS <= updated.execution_block
    assert LOCAL_TOOLS <= updated.visible_suppress
