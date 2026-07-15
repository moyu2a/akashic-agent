from __future__ import annotations

from agent.policies.task_execution_access import TaskExecutionAccessPolicy
from agent.policies.task_execution_contract import TaskExecutionTurnContract
from agent.policies.tool_access import ToolAccessGateway
from agent.policies.tool_access_types import ToolAccessContext


def _ctx(
    contract: TaskExecutionTurnContract, *, disabled: set[str] | None = None
) -> ToolAccessContext:
    capabilities = {
        "begin_task_step_execution": frozenset({"task_execution.begin"}),
        "inspect_task_execution": frozenset({"task_execution.inspect"}),
        "finish_task_step_execution": frozenset({"task_execution.finish"}),
        "request_task_step_authorization": frozenset({"task_execution.defer"}),
        "abort_task_step_execution": frozenset({"task_execution.abort"}),
    }
    risks = {
        "begin_task_step_execution": "write",
        "inspect_task_execution": "read-only",
        "finish_task_step_execution": "write",
        "request_task_step_authorization": "write",
        "abort_task_step_execution": "write",
        "tool_search": "read-only",
        "read_file": "read-only",
        "shell": "read-only",
        "write_file": "write",
    }
    return ToolAccessContext(
        session_key="cli:s1",
        user_text="continue",
        always_on_tools=frozenset({"tool_search"}),
        lru_preloaded_tools=frozenset({"read_file", "write_file"}),
        disabled_tools=frozenset(disabled or set()),
        turn_metadata={"task_execution_contract": contract},
        registered_tools=frozenset(risks),
        tool_capabilities=capabilities,
        tool_risks=risks,
    )


def _claim_contract() -> TaskExecutionTurnContract:
    return TaskExecutionTurnContract(
        active=True,
        action="continue",
        phase="claim",
        attempt_id=None,
        target_step_id=None,
        required_capabilities=frozenset({"task_execution.begin"}),
        allowed_capabilities=frozenset(
            {"task_execution.begin", "task_execution.inspect"}
        ),
        allowed_risks=frozenset(),
        work_call_budget=0,
        tool_search_budget=0,
        completion_capability="task_execution.begin",
        reason="continue_execution",
        matched_terms=("继续执行",),
    )


def _work_contract() -> TaskExecutionTurnContract:
    return TaskExecutionTurnContract(
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


def test_claim_phase_allows_only_begin_and_inspect() -> None:
    context = _ctx(_claim_contract())
    gateway = ToolAccessGateway(policies=(TaskExecutionAccessPolicy(),))

    plan = gateway.build_plan(context)

    assert gateway.compute_visible_names(context, plan) == {
        "begin_task_step_execution",
        "inspect_task_execution",
    }
    assert "read_file" in plan.execution_block
    assert gateway.check_tool_call(plan, "read_file", {}).error_code == (
        "tool_blocked_by_task_execution_policy"
    )


def test_work_phase_exposes_controls_and_only_unlocks_registered_read_only_tools() -> (
    None
):
    context = _ctx(_work_contract())
    gateway = ToolAccessGateway(policies=(TaskExecutionAccessPolicy(),))
    plan = gateway.build_plan(context)
    visible = gateway.compute_visible_names(context, plan)

    assert visible == {
        "abort_task_step_execution",
        "finish_task_step_execution",
        "request_task_step_authorization",
        "tool_search",
    }
    assert plan.execution_dynamic_tools == frozenset({"read_file"})
    assert gateway.merge_tool_search_unlocks(
        current_visible=visible,
        unlocked={"read_file", "shell", "write_file"},
        context=context,
        plan=plan,
    ) == visible | {"read_file"}


def test_waiting_phase_allows_inspect_abort_and_requests_final_only() -> None:
    contract = TaskExecutionTurnContract(
        active=True,
        action="abort",
        phase="waiting_authorization",
        attempt_id="attempt-1",
        target_step_id=None,
        required_capabilities=frozenset({"task_execution.abort"}),
        allowed_capabilities=frozenset(
            {"task_execution.inspect", "task_execution.abort"}
        ),
        allowed_risks=frozenset(),
        work_call_budget=0,
        tool_search_budget=0,
        completion_capability="task_execution.abort",
        reason="attempt_waiting_authorization",
        matched_terms=(),
    )
    context = _ctx(contract)
    gateway = ToolAccessGateway(policies=(TaskExecutionAccessPolicy(),))

    plan = gateway.build_plan(context)

    assert gateway.compute_visible_names(context, plan) == {
        "abort_task_step_execution",
        "inspect_task_execution",
    }
    assert plan.final_only is True


def test_missing_required_capability_fails_closed() -> None:
    context = _ctx(_claim_contract(), disabled={"begin_task_step_execution"})
    gateway = ToolAccessGateway(policies=(TaskExecutionAccessPolicy(),))

    plan = gateway.build_plan(context)

    assert gateway.compute_visible_names(context, plan) == set()
    assert plan.reason == "task_execution_required_capability_missing"
    assert plan.filter_error is True
    assert gateway.check_tool_call(plan, "inspect_task_execution", {}).error_code == (
        "task_execution_required_capability_missing"
    )
