from __future__ import annotations

from collections.abc import Mapping

from agent.policies.task_plan_contract import TaskPlanTurnContract
from agent.policies.tool_budget import ToolBoundaryDecision
from agent.policies.tool_ledger import ToolCallLedger

_CONTEXT_CAPABILITY_BY_REQUIREMENT = {
    "long_term_memory": "memory.recall",
    "session_history": "history.search",
}


class TaskPlanContextBudgetPolicy:
    """Enforce a turn-local, one-shot TaskPlan context retrieval budget."""

    def evaluate_call(
        self,
        *,
        contract: TaskPlanTurnContract | None,
        ledger: ToolCallLedger,
        tool_name: str,
        tool_capabilities: Mapping[str, frozenset[str]],
    ) -> ToolBoundaryDecision | None:
        if contract is None or not contract.active or contract.retrieval_budget == 0:
            return None

        context_capability = _CONTEXT_CAPABILITY_BY_REQUIREMENT.get(
            contract.context_requirement
        )
        if context_capability is None:
            return None
        if context_capability not in tool_capabilities.get(tool_name, frozenset()):
            return None

        consumed_count = sum(
            1
            for record in ledger.records
            if context_capability
            in tool_capabilities.get(record.tool_name, frozenset())
        )
        if consumed_count < contract.retrieval_budget:
            return ToolBoundaryDecision(
                action="allow",
                reason="task_plan_context_budget_available",
                metadata={
                    "retrieval_budget": contract.retrieval_budget,
                    "consumed_count": consumed_count,
                    "context_requirement": contract.context_requirement,
                },
            )

        hint = (
            "Planning context lookup is complete. Create the task plan from the "
            "available context or ask one necessary clarification; do not call "
            "more retrieval tools."
        )
        if contract.context_requirement == "session_history":
            hint = (
                "Session-history search is complete. Treat its preview as planning "
                "context; fetch_messages is unavailable in this turn. Create the "
                "task plan now or ask one necessary clarification."
            )
        return ToolBoundaryDecision(
            action="soft_stop",
            reason="task_plan_context_budget_exhausted",
            model_hint=hint,
            metadata={
                "retrieval_budget": contract.retrieval_budget,
                "consumed_count": consumed_count,
                "context_requirement": contract.context_requirement,
            },
        )
