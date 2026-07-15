from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from agent.policies.task_execution_contract import TaskExecutionTurnContract
from agent.policies.tool_budget import ToolBoundaryDecision
from agent.policies.tool_ledger import ToolCallLedger, stable_args_hash


@dataclass(frozen=True)
class TaskExecutionEventMetadata:
    tool_name: str
    tool_call_id: str
    tool_risk: str
    counts_as_work: bool
    invoker_reached: bool
    invoker_succeeded: bool
    execution_status: str
    result_ok: bool


class TaskExecutionEventClassifier:
    """Labels executor facts; callers persist only after the executor is reached."""

    def classify(
        self,
        *,
        tool_name: str,
        tool_call_id: str,
        registry_risk: str,
        invoker_reached: bool,
        invoker_succeeded: bool,
        execution_status: str,
        result_ok: bool,
    ) -> TaskExecutionEventMetadata:
        return TaskExecutionEventMetadata(
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            tool_risk=registry_risk,
            counts_as_work=(
                tool_name != "tool_search"
                and registry_risk == "read-only"
                and invoker_reached
            ),
            invoker_reached=invoker_reached,
            invoker_succeeded=invoker_succeeded,
            execution_status=execution_status,
            result_ok=result_ok,
        )


class TaskExecutionBudgetPolicy:
    def evaluate(
        self,
        *,
        contract: TaskExecutionTurnContract | None,
        ledger: ToolCallLedger,
        tool_name: str,
        arguments: dict[str, object] | Mapping[str, object],
        tool_risk: str,
        tool_capabilities: Mapping[str, frozenset[str]],
    ) -> ToolBoundaryDecision | None:
        del tool_capabilities
        if (
            contract is None
            or not contract.active
            or contract.phase != "work"
            or tool_risk != "read-only"
        ):
            return None

        if tool_name == "tool_search":
            consumed = ledger.count_tool("tool_search")
            if consumed >= contract.tool_search_budget:
                return _terminal_stop(
                    "task_execution_tool_search_budget_exhausted",
                    budget=contract.tool_search_budget,
                    consumed=consumed,
                    tool_name=tool_name,
                )
            return ToolBoundaryDecision(
                action="allow",
                reason="task_execution_tool_search_budget_available",
                metadata={
                    "tool_search_budget": contract.tool_search_budget,
                    "consumed": consumed,
                },
            )

        consumed = ledger.count_task_execution_work()
        if consumed >= contract.work_call_budget:
            return _terminal_stop(
                "task_execution_batch_budget_skip",
                budget=contract.work_call_budget,
                consumed=consumed,
                tool_name=tool_name,
            )

        args_hash = stable_args_hash(arguments)
        if ledger.same_task_execution_work_args(tool_name, args_hash) > 0:
            return _terminal_stop(
                "task_execution_repeated_work_call",
                budget=contract.work_call_budget,
                consumed=consumed,
                tool_name=tool_name,
            )
        return ToolBoundaryDecision(
            action="allow",
            reason="task_execution_work_budget_available",
            metadata={
                "work_call_budget": contract.work_call_budget,
                "consumed": consumed,
            },
        )


def _terminal_stop(
    reason: str,
    *,
    budget: int,
    consumed: int,
    tool_name: str,
) -> ToolBoundaryDecision:
    return ToolBoundaryDecision(
        action="soft_stop",
        reason=reason,
        model_hint=(
            "Task execution work budget is exhausted. Do not call more tools for "
            "this attempt."
        ),
        metadata={
            "tool_name": tool_name,
            "budget": budget,
            "consumed": consumed,
            "terminal_transition": "failed",
        },
    )
