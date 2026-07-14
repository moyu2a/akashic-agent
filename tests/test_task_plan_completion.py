from __future__ import annotations

import json

import pytest

from agent.policies.task_plan_completion import TaskPlanCompletionPolicy
from agent.policies.task_plan_contract import (
    TaskPlanTurnContract,
    infer_task_plan_turn_decision,
)
from agent.policies.tool_ledger import ToolCallLedger, ToolCallRecord
from agent.policies.turn_completion import TurnCompletionController


CAPABILITIES = {
    "create_task_plan": frozenset({"task_plan.create"}),
    "inspect_task_plan": frozenset({"task_plan.inspect"}),
    "update_task_step": frozenset({"task_plan.update"}),
    "alternate_update": frozenset({"task_plan.update"}),
    "recall_memory": frozenset({"memory.recall"}),
}


def _contract(text: str, *, has_active_task: bool = False) -> TaskPlanTurnContract:
    return infer_task_plan_turn_decision(
        text,
        has_active_task=has_active_task,
    ).contract


def _record(
    tool_name: str,
    result_text: str,
    *,
    ok: bool = True,
    execution_status: str = "success",
    call_index: int = 1,
) -> ToolCallRecord:
    return ToolCallRecord(
        tool_name=tool_name,
        tool_class="unknown",
        args_hash=f"h-{call_index}",
        args_summary="{}",
        call_index=call_index,
        visible_before_call=True,
        decision_action="allow",
        decision_reason="allowed",
        execution_status=execution_status,
        result_ok=ok,
        result_summary=result_text[:240],
        result_text=result_text,
        result_error_code="" if ok else "task_not_found",
    )


@pytest.mark.parametrize(
    ("contract", "tool_name", "completion_capability"),
    [
        (_contract("制定一个三步计划"), "create_task_plan", "task_plan.create"),
        (
            _contract("当前任务做到哪一步", has_active_task=True),
            "inspect_task_plan",
            "task_plan.inspect",
        ),
        (
            _contract("把第一步标记完成", has_active_task=True),
            "update_task_step",
            "task_plan.update",
        ),
    ],
)
def test_matching_completion_capability_requests_final_only(
    contract: TaskPlanTurnContract,
    tool_name: str,
    completion_capability: str,
) -> None:
    ledger = ToolCallLedger(
        records=[_record(tool_name, json.dumps({"ok": True}))]
    )

    decision = TaskPlanCompletionPolicy().evaluate(
        contract=contract,
        ledger=ledger,
        tool_capabilities=CAPABILITIES,
    )

    assert decision is not None
    assert decision.action == "final_only"
    assert decision.reason == "task_plan_completion_capability_satisfied"
    assert decision.metadata == {
        "tool_name": tool_name,
        "completion_capability": completion_capability,
    }


@pytest.mark.parametrize(
    ("contract", "non_completing_tool"),
    [
        (
            _contract("制定一个三步计划", has_active_task=True),
            "inspect_task_plan",
        ),
        (
            _contract("制定一个三步计划", has_active_task=True),
            "update_task_step",
        ),
        (
            _contract("当前任务做到哪一步", has_active_task=True),
            "create_task_plan",
        ),
        (
            _contract("当前任务做到哪一步", has_active_task=True),
            "update_task_step",
        ),
        (
            _contract("把第一步标记完成", has_active_task=True),
            "inspect_task_plan",
        ),
        (
            _contract("把第一步标记完成", has_active_task=True),
            "create_task_plan",
        ),
    ],
)
def test_non_matching_task_plan_capability_does_not_complete(
    contract: TaskPlanTurnContract,
    non_completing_tool: str,
) -> None:
    decision = TaskPlanCompletionPolicy().evaluate(
        contract=contract,
        ledger=ToolCallLedger(
            records=[_record(non_completing_tool, '{"ok": true}')]
        ),
        tool_capabilities=CAPABILITIES,
    )

    assert decision is None


def test_update_contract_does_not_finish_after_inspect_success() -> None:
    ledger = ToolCallLedger(
        records=[_record("inspect_task_plan", '{"ok": true}')]
    )

    decision = TaskPlanCompletionPolicy().evaluate(
        contract=_contract("把第一步标记完成", has_active_task=True),
        ledger=ledger,
        tool_capabilities=CAPABILITIES,
    )

    assert decision is None


def test_update_contract_finishes_after_inspect_then_update() -> None:
    ledger = ToolCallLedger(
        records=[
            _record("inspect_task_plan", '{"ok": true}', call_index=1),
            _record("update_task_step", '{"ok": true}', call_index=2),
        ]
    )

    decision = TaskPlanCompletionPolicy().evaluate(
        contract=_contract("把第一步标记完成", has_active_task=True),
        ledger=ledger,
        tool_capabilities=CAPABILITIES,
    )

    assert decision is not None
    assert decision.metadata["tool_name"] == "update_task_step"


def test_context_retrieval_success_does_not_finish_contextual_create() -> None:
    ledger = ToolCallLedger(
        records=[_record("recall_memory", '{"ok": true}')]
    )

    decision = TaskPlanCompletionPolicy().evaluate(
        contract=_contract("结合我的偏好制定计划"),
        ledger=ledger,
        tool_capabilities=CAPABILITIES,
    )

    assert decision is None


def test_alternate_provider_can_satisfy_completion_capability() -> None:
    ledger = ToolCallLedger(
        records=[_record("alternate_update", '{"ok": true}')]
    )

    decision = TaskPlanCompletionPolicy().evaluate(
        contract=_contract("把第一步标记完成", has_active_task=True),
        ledger=ledger,
        tool_capabilities=CAPABILITIES,
    )

    assert decision is not None
    assert decision.metadata["tool_name"] == "alternate_update"


@pytest.mark.parametrize("execution_status", ["denied", "error"])
def test_non_successful_executor_status_never_completes(
    execution_status: str,
) -> None:
    ledger = ToolCallLedger(
        records=[
            _record(
                "create_task_plan",
                '{"ok": true}',
                execution_status=execution_status,
            )
        ]
    )

    decision = TaskPlanCompletionPolicy().evaluate(
        contract=_contract("制定一个三步计划"),
        ledger=ledger,
        tool_capabilities=CAPABILITIES,
    )

    assert decision is None


@pytest.mark.parametrize(
    "record",
    [
        _record("create_task_plan", '{"ok": false}', ok=False),
        _record("create_task_plan", "not-json", ok=True),
        _record("create_task_plan", '{"ok": true}', ok=False),
    ],
)
def test_failed_or_inconsistent_result_does_not_complete(
    record: ToolCallRecord,
) -> None:
    decision = TaskPlanCompletionPolicy().evaluate(
        contract=_contract("制定一个三步计划"),
        ledger=ToolCallLedger(records=[record]),
        tool_capabilities=CAPABILITIES,
    )

    assert decision is None


def test_inactive_or_missing_contract_has_no_completion_decision() -> None:
    ledger = ToolCallLedger(
        records=[_record("create_task_plan", '{"ok": true}')]
    )
    policy = TaskPlanCompletionPolicy()

    assert policy.evaluate(
        contract=None,
        ledger=ledger,
        tool_capabilities=CAPABILITIES,
    ) is None
    assert policy.evaluate(
        contract=TaskPlanTurnContract.inactive(reason="background_start_passthrough"),
        ledger=ledger,
        tool_capabilities=CAPABILITIES,
    ) is None


def test_controller_checks_task_plan_completion_before_local_source_escape() -> None:
    contract = _contract("制定一个三步计划")
    ledger = ToolCallLedger(
        records=[_record("create_task_plan", '{"ok": true}')]
    )

    decision = TurnCompletionController().evaluate(
        intent="task_plan_state",
        ledger=ledger,
        boundary_decisions=(),
        task_plan_contract=contract,
        tool_capabilities=CAPABILITIES,
        local_source_allowed=True,
    )

    assert decision.action == "final_only"
    assert decision.reason == "task_plan_completion_capability_satisfied"
