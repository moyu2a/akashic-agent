from __future__ import annotations

import json

import pytest

from agent.policies.task_plan_context_budget import TaskPlanContextBudgetPolicy
from agent.policies.task_plan_contract import infer_task_plan_turn_decision
from agent.policies.tool_access_types import ToolAccessContext
from agent.policies.tool_boundary import TurnToolBoundaryManager
from agent.policies.tool_ledger import ToolCallLedger, ToolCallRecord


CAPABILITIES = {
    "create_task_plan": frozenset({"task_plan.create"}),
    "recall_memory": frozenset({"memory.recall"}),
    "search_messages": frozenset({"history.search"}),
}


def _contract(text: str):
    return infer_task_plan_turn_decision(
        text,
        has_active_task=False,
    ).contract


def _record(
    tool_name: str,
    *,
    result_ok: bool,
    execution_status: str = "success",
) -> ToolCallRecord:
    return ToolCallRecord(
        tool_name=tool_name,
        tool_class="retrieval",
        args_hash="hash",
        args_summary="{}",
        call_index=1,
        visible_before_call=True,
        result_ok=result_ok,
        execution_status=execution_status,
    )


@pytest.mark.parametrize(
    ("text", "tool_name"),
    [
        ("结合我的偏好制定计划", "recall_memory"),
        ("按照我们上次讨论制定计划", "search_messages"),
    ],
)
def test_first_allowed_context_retrieval_is_within_budget(
    text: str,
    tool_name: str,
) -> None:
    decision = TaskPlanContextBudgetPolicy().evaluate_call(
        contract=_contract(text),
        ledger=ToolCallLedger(),
        tool_name=tool_name,
        tool_capabilities=CAPABILITIES,
    )

    assert decision is not None
    assert decision.action == "allow"
    assert decision.reason == "task_plan_context_budget_available"


@pytest.mark.parametrize("execution_status", ["success", "denied", "error"])
@pytest.mark.parametrize("result_ok", [True, False])
def test_allowed_context_attempt_consumes_budget_regardless_of_outcome(
    execution_status: str,
    result_ok: bool,
) -> None:
    ledger = ToolCallLedger(
        records=[
            _record(
                "recall_memory",
                result_ok=result_ok,
                execution_status=execution_status,
            )
        ]
    )

    decision = TaskPlanContextBudgetPolicy().evaluate_call(
        contract=_contract("结合我的偏好制定计划"),
        ledger=ledger,
        tool_name="recall_memory",
        tool_capabilities=CAPABILITIES,
    )

    assert decision is not None
    assert decision.action == "soft_stop"
    assert decision.reason == "task_plan_context_budget_exhausted"
    assert decision.metadata == {
        "retrieval_budget": 1,
        "consumed_count": 1,
        "context_requirement": "long_term_memory",
    }


def test_task_plan_state_tool_does_not_consume_context_budget() -> None:
    ledger = ToolCallLedger(
        records=[
            ToolCallRecord(
                tool_name="create_task_plan",
                tool_class="unknown",
                args_hash="hash",
                args_summary="{}",
                call_index=1,
                visible_before_call=True,
                result_ok=False,
                execution_status="error",
            )
        ]
    )

    decision = TaskPlanContextBudgetPolicy().evaluate_call(
        contract=_contract("结合我的偏好制定计划"),
        ledger=ledger,
        tool_name="recall_memory",
        tool_capabilities=CAPABILITIES,
    )

    assert decision is not None
    assert decision.action == "allow"
    assert decision.reason == "task_plan_context_budget_available"
    assert decision.metadata["consumed_count"] == 0

    state_decision = TaskPlanContextBudgetPolicy().evaluate_call(
        contract=_contract("结合我的偏好制定计划"),
        ledger=ledger,
        tool_name="create_task_plan",
        tool_capabilities=CAPABILITIES,
    )
    assert state_decision is None


def _boundary_context(text: str):
    return ToolAccessContext(
        session_key="cli:s1",
        user_text=text,
        always_on_tools=frozenset({"tool_search"}),
        lru_preloaded_tools=frozenset(),
        disabled_tools=frozenset(),
        registered_tools=frozenset(CAPABILITIES),
        tool_capabilities=CAPABILITIES,
    )


@pytest.mark.parametrize(
    ("text", "tool_name", "result_text", "execution_status"),
    [
        ("结合我的偏好制定计划", "recall_memory", '{"ok": true}', "success"),
        ("按照我们上次讨论制定计划", "search_messages", '{"ok": true}', "success"),
        ("结合我的偏好制定计划", "recall_memory", '{"ok": false}', "success"),
        ("结合我的偏好制定计划", "recall_memory", '{"ok": true}', "error"),
        ("结合我的偏好制定计划", "recall_memory", '{"ok": true}', "denied"),
    ],
)
def test_same_batch_second_context_call_is_soft_stopped(
    text: str,
    tool_name: str,
    result_text: str,
    execution_status: str,
) -> None:
    manager = TurnToolBoundaryManager()
    context = manager.build_context(_boundary_context(text))
    visible = manager.compute_visible_names(context)

    first = manager.evaluate_tool_call(
        context,
        tool_name=tool_name,
        arguments={"query": "context"},
        visible_names=visible,
    )
    assert first.execute is True
    manager.record_tool_result(
        context,
        tool_name=tool_name,
        arguments={"query": "context"},
        result_text=result_text,
        execution_status=execution_status,
        visible_before_call=True,
        decision_action=first.action,
        decision_reason=first.reason,
    )
    manager.observe_access_tool_result(
        context,
        tool_name,
        result_text,
        execution_status=execution_status,
    )

    second = manager.evaluate_tool_call(
        context,
        tool_name=tool_name,
        arguments={"query": "context again"},
        visible_names=manager.compute_visible_names(context),
    )

    assert second.execute is False
    assert second.action == "soft_stop"
    assert second.reason == "task_plan_context_budget_exhausted"


def test_context_result_retires_retrieval_but_keeps_create_visible() -> None:
    manager = TurnToolBoundaryManager()
    context = manager.build_context(
        _boundary_context("按照我们上次讨论制定计划")
    )
    assert manager.compute_visible_names(context) == {
        "search_messages",
        "create_task_plan",
    }

    manager.observe_access_tool_result(
        context,
        "search_messages",
        json.dumps({"ok": True}),
        execution_status="success",
    )

    assert manager.compute_visible_names(context) == {"create_task_plan"}
    assert context.access_plan.context_retrieval_consumed is True
    assert "search_messages" in context.access_plan.visible_suppress
    assert "search_messages" in context.access_plan.tool_search_block
    assert "search_messages" not in context.access_plan.execution_block
    assert context.access_plan.model_hints
    assert "fetch_messages" in context.access_plan.model_hints[-1]
    assert "fetch_messages" in (manager.consume_pending_hint(context) or "")
    assert manager.consume_pending_hint(context) is None


def test_context_budget_trace_exposes_decision_and_execution_status() -> None:
    manager = TurnToolBoundaryManager()
    context = manager.build_context(
        _boundary_context("结合我的偏好制定计划")
    )

    decision = manager.evaluate_tool_call(
        context,
        tool_name="recall_memory",
        arguments={"query": "preferences"},
        visible_names=manager.compute_visible_names(context),
    )
    manager.record_tool_result(
        context,
        tool_name="recall_memory",
        arguments={"query": "preferences"},
        result_text='{"ok": false}',
        execution_status="error",
        visible_before_call=True,
        decision_action=decision.action,
        decision_reason=decision.reason,
    )
    manager.observe_access_tool_result(
        context,
        "recall_memory",
        '{"ok": false}',
        execution_status="error",
    )

    trace = manager.trace(context)

    assert trace["task_plan_context_budget"] == {
        "retrieval_budget": 1,
        "consumed_count": 1,
        "consumed": True,
        "decision_reason": "task_plan_context_budget_available",
        "last_execution_status": "error",
    }
    assert trace["tool_access"]["policy_metadata"]["task_plan"][
        "context_retrieval_execution_status"
    ] == "error"


def test_cross_family_context_call_is_access_blocked_before_budget() -> None:
    manager = TurnToolBoundaryManager()
    context = manager.build_context(
        _boundary_context("结合我的偏好制定计划")
    )

    decision = manager.evaluate_tool_call(
        context,
        tool_name="search_messages",
        arguments={"query": "history"},
        visible_names=manager.compute_visible_names(context),
    )

    assert decision.action == "block"
    assert decision.reason == "tool_blocked_by_task_plan_policy"
