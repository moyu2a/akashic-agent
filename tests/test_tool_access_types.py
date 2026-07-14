from __future__ import annotations

from agent.policies.tool_access import (
    ToolAccessContext as GatewayToolAccessContext,
    ToolAccessGateway,
    ToolAccessPlan as GatewayToolAccessPlan,
    ToolExecutionGateResult as GatewayToolExecutionGateResult,
)
from agent.policies.task_plan_contract import infer_task_plan_turn_decision
from agent.policies.task_plan_boundary import TaskPlanAccessPolicy
from agent.policies.tool_access import _merge_plans
from agent.policies.tool_access_types import (
    ToolAccessContext,
    ToolAccessPlan,
    ToolExecutionGateResult,
)


def test_tool_access_types_keep_current_defaults() -> None:
    context = ToolAccessContext(
        session_key="cli:s1",
        user_text="hello",
        always_on_tools=frozenset({"tool_search"}),
        lru_preloaded_tools=frozenset(),
        disabled_tools=frozenset(),
    )
    plan = ToolAccessPlan()
    gate = ToolExecutionGateResult(allowed=True)

    assert context.turn_metadata == {}
    assert context.registered_tools == frozenset()
    assert context.tool_capabilities == {}
    assert context.tool_discovery_enabled is True
    assert plan.reason == "no_tool_access_policy"
    assert plan.visible_add == frozenset()
    assert plan.execution_block == frozenset()
    assert plan.policy_metadata == {}
    assert plan.task_plan_contract is None
    assert plan.strict_capability_scope is False
    assert plan.context_retrieval_tools == frozenset()
    assert plan.context_retrieval_consumed is False
    assert plan.model_hints == ()
    assert gate.allowed is True
    assert gate.error_code == ""


def test_tool_access_reexports_types_for_existing_imports() -> None:
    assert GatewayToolAccessContext is ToolAccessContext
    assert GatewayToolAccessPlan is ToolAccessPlan
    assert GatewayToolExecutionGateResult is ToolExecutionGateResult


def test_plan_merge_preserves_metadata_and_forces_strict_local_source_false() -> None:
    contract = infer_task_plan_turn_decision(
        "制定一个三步计划",
        has_active_task=False,
    ).contract
    left = ToolAccessPlan(
        local_source_allowed=True,
        policy_metadata={"doc_rag": {"source": True}},
    )
    right = ToolAccessPlan(
        task_plan_contract=contract,
        strict_capability_scope=True,
        policy_metadata={"task_plan": contract.to_trace_metadata()},
    )

    merged = _merge_plans(left, right)

    assert merged.local_source_allowed is False
    assert merged.task_plan_contract is contract
    assert merged.policy_metadata == {
        "doc_rag": {"source": True},
        "task_plan": contract.to_trace_metadata(),
    }


def test_conflicting_typed_contracts_fail_closed() -> None:
    create = infer_task_plan_turn_decision(
        "制定一个三步计划",
        has_active_task=False,
    ).contract
    inspect = infer_task_plan_turn_decision(
        "当前任务做到哪一步",
        has_active_task=True,
    ).contract

    merged = _merge_plans(
        ToolAccessPlan(
            task_plan_contract=create,
            strict_capability_scope=True,
            visible_suppress=frozenset({"inspect_task_plan"}),
            execution_block=frozenset({"inspect_task_plan"}),
        ),
        ToolAccessPlan(
            task_plan_contract=inspect,
            strict_capability_scope=True,
            visible_suppress=frozenset({"create_task_plan"}),
            execution_block=frozenset({"create_task_plan"}),
        ),
    )

    assert merged.task_plan_contract is None
    assert merged.strict_capability_scope is True
    assert merged.filter_error is True
    assert merged.reason == "conflicting_task_plan_contracts"
    assert {"create_task_plan", "inspect_task_plan"} <= merged.execution_block
    assert merged.model_hints


def test_real_strict_plan_conflict_clears_all_visible_and_executable_tools() -> None:
    capabilities = {
        "create_task_plan": frozenset({"task_plan.create"}),
        "inspect_task_plan": frozenset({"task_plan.inspect"}),
    }
    create = TaskPlanAccessPolicy().build_plan(
        ToolAccessContext(
            session_key="cli:s1",
            user_text="制定一个三步计划",
            always_on_tools=frozenset(),
            lru_preloaded_tools=frozenset(),
            disabled_tools=frozenset(),
            registered_tools=frozenset({"create_task_plan"}),
            tool_capabilities=capabilities,
        )
    )
    inspect = TaskPlanAccessPolicy().build_plan(
        ToolAccessContext(
            session_key="cli:s1",
            user_text="当前任务做到哪一步",
            always_on_tools=frozenset(),
            lru_preloaded_tools=frozenset(),
            disabled_tools=frozenset(),
            turn_metadata={"has_active_task": True},
            registered_tools=frozenset({"inspect_task_plan"}),
            tool_capabilities=capabilities,
        )
    )

    merged = _merge_plans(create, inspect)
    gateway = ToolAccessGateway()
    merged_context = ToolAccessContext(
        session_key="cli:s1",
        user_text="conflict",
        always_on_tools=frozenset(),
        lru_preloaded_tools=frozenset(),
        disabled_tools=frozenset(),
        registered_tools=frozenset(
            {"create_task_plan", "inspect_task_plan"}
        ),
        tool_capabilities=capabilities,
    )

    assert merged.visible_add == frozenset()
    assert gateway.compute_visible_names(merged_context, merged) == set()
    for tool_name in ("create_task_plan", "inspect_task_plan"):
        assert tool_name in merged.execution_block
        gate = gateway.check_tool_call(merged, tool_name, {})
        assert gate.allowed is False
        assert gate.error_code == "conflicting_task_plan_contracts"
