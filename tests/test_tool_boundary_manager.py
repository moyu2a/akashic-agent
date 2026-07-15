from __future__ import annotations

import json
import logging
from dataclasses import replace
from pathlib import Path

import pytest

from agent.policies.tool_access import ToolAccessContext
from agent.policies.tool_boundary import TurnToolBoundaryManager
from agent.policies.task_execution_contract import TaskExecutionTurnContract
from agent.tools.base import ToolResult
from agent.tools.filesystem import ReadFileTool


def _ctx(text: str) -> ToolAccessContext:
    return ToolAccessContext(
        session_key="cli:1",
        user_text=text,
        always_on_tools=frozenset({"tool_search", "read_file", "shell", "list_dir"}),
        lru_preloaded_tools=frozenset(),
        disabled_tools=frozenset(),
    )


def _execution_ctx() -> ToolAccessContext:
    contract = TaskExecutionTurnContract(
        active=True,
        action="continue",
        phase="work",
        attempt_id="attempt-1",
        target_step_id="step-1",
        required_capabilities=frozenset({"task_execution.finish"}),
        allowed_capabilities=frozenset(
            {
                "task_execution.finish",
                "task_execution.defer",
                "task_execution.abort",
            }
        ),
        allowed_risks=frozenset({"read-only"}),
        work_call_budget=3,
        tool_search_budget=1,
        completion_capability="task_execution.finish",
        reason="attempt_running",
        matched_terms=(),
    )
    risks = {
        "tool_search": "read-only",
        "read_file": "read-only",
        "shell": "read-only",
        "write_file": "write",
        "send_webhook": "external-side-effect",
        "delete_workspace": "destructive",
        "finish_task_step_execution": "write",
        "request_task_step_authorization": "write",
        "abort_task_step_execution": "write",
    }
    return ToolAccessContext(
        session_key="cli:execution",
        user_text="continue execution",
        always_on_tools=frozenset({"tool_search"}),
        lru_preloaded_tools=frozenset(),
        disabled_tools=frozenset(),
        turn_metadata={"task_execution_contract": contract},
        registered_tools=frozenset(risks),
        tool_risks=risks,
        tool_capabilities={
            "finish_task_step_execution": frozenset({"task_execution.finish"}),
            "request_task_step_authorization": frozenset({"task_execution.defer"}),
            "abort_task_step_execution": frozenset({"task_execution.abort"}),
        },
    )


def test_manager_preserves_doc_rag_access_behavior() -> None:
    manager = TurnToolBoundaryManager()
    ctx = manager.build_context(_ctx("根据项目文档回答agent runtime负责什么，并展开原文证据"))

    visible = manager.compute_visible_names(ctx)

    assert {"search_docs", "fetch_doc_chunk", "tool_search"} <= visible
    assert visible.isdisjoint({"read_file", "shell", "list_dir"})
    assert ctx.intent == "doc_qa_with_evidence"


def test_core_access_block_wins_before_budget() -> None:
    manager = TurnToolBoundaryManager()
    ctx = manager.build_context(_ctx("根据项目文档回答agent runtime负责什么，并展开原文证据"))

    decision = manager.evaluate_tool_call(
        ctx,
        tool_name="read_file",
        arguments={"path": "README.md"},
        visible_names={"search_docs", "fetch_doc_chunk"},
    )

    assert decision.action == "block"
    assert decision.reason == "tool_blocked_by_doc_rag_policy"
    assert decision.execute is False


def test_shell_is_deferred_even_when_command_looks_read_only() -> None:
    manager = TurnToolBoundaryManager()
    context = manager.build_context(_execution_ctx())

    decision = manager.evaluate_tool_call(
        context,
        tool_name="shell",
        arguments={"command": "pwd"},
        visible_names=manager.compute_visible_names(context),
    )

    assert decision.action == "soft_stop"
    assert decision.reason == "task_execution_authorization_required"
    assert decision.execute is False
    assert context.ledger.records == []


def test_destructive_is_core_denied_before_task_execution_visibility() -> None:
    manager = TurnToolBoundaryManager()
    context = manager.build_context(_execution_ctx())

    decision = manager.evaluate_tool_call(
        context,
        tool_name="delete_workspace",
        arguments={},
        visible_names=set(),
    )

    assert decision.action == "block"
    assert decision.reason == "task_execution_destructive_denied"
    assert decision.execute is False


def test_registered_write_returns_typed_defer_before_visibility_block() -> None:
    manager = TurnToolBoundaryManager()
    context = manager.build_context(_execution_ctx())

    decision = manager.evaluate_tool_call(
        context,
        tool_name="write_file",
        arguments={"path": "x.txt", "content": "x"},
        visible_names=set(),
    )

    assert decision.action == "defer"
    assert decision.execute is False
    assert decision.metadata["durable_transition"] == "waiting_authorization"


@pytest.mark.parametrize("tool_name", ["write_file", "send_webhook"])
def test_missing_required_capability_blocks_registered_side_effect_before_defer(
    tool_name: str,
) -> None:
    source = _execution_ctx()
    context = replace(
        source,
        tool_capabilities={
            "request_task_step_authorization": frozenset({"task_execution.defer"}),
            "abort_task_step_execution": frozenset({"task_execution.abort"}),
        },
    )
    manager = TurnToolBoundaryManager()
    boundary_context = manager.build_context(context)

    decision = manager.evaluate_tool_call(
        boundary_context,
        tool_name=tool_name,
        arguments={},
        visible_names=set(),
    )

    assert decision.action == "block"
    assert decision.execute is False
    assert decision.reason == "task_execution_required_capability_missing"


def test_task_plan_create_blocks_spawn_at_boundary_manager() -> None:
    context = ToolAccessContext(
        session_key="cli:1",
        user_text="为修复 Document RAG 成本问题制定一个三步计划",
        always_on_tools=frozenset(
            {"tool_search", "spawn", "spawn_manage", "task_output"}
        ),
        lru_preloaded_tools=frozenset({"search_docs", "fetch_doc_chunk"}),
        disabled_tools=frozenset(),
        registered_tools=frozenset(
            {
                "tool_search",
                "create_task_plan",
                "inspect_task_plan",
                "update_task_step",
                "spawn",
                "spawn_manage",
                "task_output",
                "search_docs",
                "fetch_doc_chunk",
            }
        ),
        tool_capabilities={
            "create_task_plan": frozenset({"task_plan.create"}),
            "inspect_task_plan": frozenset({"task_plan.inspect"}),
            "update_task_step": frozenset({"task_plan.update"}),
        },
    )
    manager = TurnToolBoundaryManager()
    boundary_context = manager.build_context(context)

    decision = manager.evaluate_tool_call(
        boundary_context,
        tool_name="spawn",
        arguments={"task": "分析 RAG 成本"},
        visible_names=manager.compute_visible_names(boundary_context),
    )

    assert decision.action == "block"
    assert decision.execute is False
    assert decision.reason == "tool_blocked_by_task_plan_policy"


def test_task_plan_mixed_topic_uses_task_plan_state_boundary_intent() -> None:
    context = ToolAccessContext(
        session_key="cli:1",
        user_text="为修复 Document RAG 成本问题制定一个三步计划",
        always_on_tools=frozenset({"tool_search", "search_docs"}),
        lru_preloaded_tools=frozenset({"search_docs", "fetch_doc_chunk"}),
        disabled_tools=frozenset(),
        registered_tools=frozenset(
            {"tool_search", "search_docs", "fetch_doc_chunk", "create_task_plan"}
        ),
        tool_capabilities={
            "create_task_plan": frozenset({"task_plan.create"}),
        },
    )

    boundary_context = TurnToolBoundaryManager().build_context(context)

    assert boundary_context.intent == "task_plan_state"
    assert boundary_context.task_plan_contract is not None
    assert boundary_context.task_plan_contract.action == "plan_create"


def test_redundant_visible_tool_search_soft_stops_without_execution() -> None:
    manager = TurnToolBoundaryManager()
    ctx = manager.build_context(_ctx("根据项目文档回答agent runtime负责什么，并展开原文证据"))

    decision = manager.evaluate_tool_call(
        ctx,
        tool_name="tool_search",
        arguments={"query": "select:search_docs,fetch_doc_chunk"},
        visible_names={"tool_search", "search_docs", "fetch_doc_chunk"},
    )

    assert decision.action == "soft_stop"
    assert decision.execute is False
    assert json.loads(decision.result_payload or "{}")["error_code"] == (
        "tool_boundary_soft_stop"
    )
    assert manager.consume_pending_hint(ctx)
    assert manager.consume_pending_hint(ctx) is None


def test_recorded_evidence_causes_next_fetch_soft_stop() -> None:
    manager = TurnToolBoundaryManager()
    ctx = manager.build_context(_ctx("根据项目文档回答agent runtime负责什么，并展开原文证据"))
    manager.record_tool_result(
        ctx,
        tool_name="search_docs",
        arguments={"query": "agent runtime"},
        result_text=json.dumps(
            {
                "ok": True,
                "hit_count": 1,
                "hits": [{"chunk_id": "c1", "citation": "my_md/doc.md > Agent Runtime"}],
            }
        ),
        visible_before_call=True,
        decision_action="allow",
        decision_reason="within_budget",
    )
    manager.record_tool_result(
        ctx,
        tool_name="fetch_doc_chunk",
        arguments={"chunk_id": "c1"},
        result_text=json.dumps(
            {
                "ok": True,
                "chunk": {
                    "chunk_id": "c1",
                    "citation": "my_md/doc.md > Agent Runtime",
                    "text": "Agent runtime 负责管理 agent 的一次运行过程。",
                },
            }
        ),
        visible_before_call=True,
        decision_action="allow",
        decision_reason="within_budget",
    )

    decision = manager.evaluate_tool_call(
        ctx,
        tool_name="fetch_doc_chunk",
        arguments={"chunk_id": "c2"},
        visible_names={"search_docs", "fetch_doc_chunk"},
    )

    assert decision.action == "soft_stop"
    assert decision.reason == "document_rag_evidence_complete"
    assert decision.execute is False


def test_trace_contains_decisions_and_ledger_summary() -> None:
    manager = TurnToolBoundaryManager()
    ctx = manager.build_context(_ctx("根据项目文档回答agent runtime负责什么，并展开原文证据"))
    manager.evaluate_tool_call(
        ctx,
        tool_name="tool_search",
        arguments={"query": "select:search_docs,fetch_doc_chunk"},
        visible_names={"tool_search", "search_docs", "fetch_doc_chunk"},
    )

    trace = manager.trace(ctx)

    assert trace["intent"] == "doc_qa_with_evidence"
    assert trace["decisions"][0]["action"] == "soft_stop"
    assert trace["ledger_summary"]["tool_calls"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(("path", "expected_ok"), [("README.md", True), ("missing", False)])
async def test_boundary_ledger_preserves_read_file_structured_outcome(
    tmp_path: Path,
    path: str,
    expected_ok: bool,
) -> None:
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")
    manager = TurnToolBoundaryManager()
    context = manager.build_context(_ctx("read a local file"))
    result = await ReadFileTool(allowed_dir=tmp_path).execute(path)

    assert isinstance(result, ToolResult)
    manager.record_tool_result(
        context,
        tool_name="read_file",
        arguments={"path": path},
        result_text=result,
        visible_before_call=True,
        decision_action="allow",
        decision_reason="within_budget",
        execution_status="success",
    )

    assert context.ledger.records[-1].result_ok is expected_ok


def test_recent_decisions_exposes_soft_stop_for_completion_controller(caplog) -> None:
    manager = TurnToolBoundaryManager()
    ctx = manager.build_context(_ctx("根据项目文档回答 agent runtime，并展开原文证据"))
    visible = {"tool_search", "search_docs", "fetch_doc_chunk"}

    search = manager.evaluate_tool_call(
        ctx,
        tool_name="search_docs",
        arguments={"query": "agent runtime"},
        visible_names=visible,
    )
    assert search.execute is True
    manager.record_tool_result(
        ctx,
        tool_name="search_docs",
        arguments={"query": "agent runtime"},
        result_text=json.dumps(
            {
                "ok": True,
                "hit_count": 1,
                "hits": [{"chunk_id": "c1", "citation": "[doc.md > A]"}],
            }
        ),
        visible_before_call=True,
        decision_action=search.action,
        decision_reason=search.reason,
    )
    fetch = manager.evaluate_tool_call(
        ctx,
        tool_name="fetch_doc_chunk",
        arguments={"chunk_id": "c1"},
        visible_names=visible,
    )
    assert fetch.execute is True
    manager.record_tool_result(
        ctx,
        tool_name="fetch_doc_chunk",
        arguments={"chunk_id": "c1"},
        result_text=json.dumps(
            {
                "ok": True,
                "chunk": {"chunk_id": "c1", "citation": "[doc.md > A]"},
            }
        ),
        visible_before_call=True,
        decision_action=fetch.action,
        decision_reason=fetch.reason,
    )

    with caplog.at_level(logging.INFO, logger="agent.policies.tool_boundary"):
        stopped = manager.evaluate_tool_call(
            ctx,
            tool_name="fetch_doc_chunk",
            arguments={"chunk_id": "c2"},
            visible_names=visible,
        )

    assert stopped.execute is False
    decisions = manager.recent_decisions(ctx)
    assert decisions[-1]["action"] == "soft_stop"
    assert decisions[-1]["reason"] == "document_rag_evidence_complete"
    assert (
        "[tool_boundary] soft_stop tool=fetch_doc_chunk "
        "reason=document_rag_evidence_complete"
    ) in caplog.text
