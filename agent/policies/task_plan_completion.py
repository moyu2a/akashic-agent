from __future__ import annotations

import json
from collections.abc import Mapping

from agent.policies.task_plan_contract import TaskPlanTurnContract
from agent.policies.tool_ledger import ToolCallLedger
from agent.policies.turn_completion_types import TurnCompletionDecision


class TaskPlanCompletionPolicy:
    def evaluate(
        self,
        *,
        contract: TaskPlanTurnContract | None,
        ledger: ToolCallLedger,
        tool_capabilities: Mapping[str, frozenset[str]],
    ) -> TurnCompletionDecision | None:
        if contract is None or not contract.active:
            return None
        completion_capability = contract.completion_capability
        if completion_capability is None:
            return None

        for record in reversed(ledger.records):
            if completion_capability not in tool_capabilities.get(
                record.tool_name, frozenset()
            ):
                continue
            if (
                record.execution_status != "success"
                or not record.result_ok
                or not _task_plan_result_ok(record.result_text)
            ):
                continue
            return TurnCompletionDecision(
                action="final_only",
                reason="task_plan_completion_capability_satisfied",
                model_hint=(
                    "TaskPlan state management is complete for this turn. Do not "
                    "call more tools. Reply with the current plan or step status, "
                    "and do not start background tasks unless explicitly asked."
                ),
                metadata={
                    "tool_name": record.tool_name,
                    "completion_capability": completion_capability,
                },
            )
        return None


def _task_plan_result_ok(result_text: str) -> bool:
    try:
        payload = json.loads(result_text)
    except (TypeError, ValueError):
        return False
    return isinstance(payload, dict) and payload.get("ok") is True
