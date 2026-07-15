from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agent.policies.task_execution_contract import TaskExecutionTurnContract
from agent.policies.task_plan_contract import TaskPlanTurnContract

_EXPLICIT_PLAN_UPDATE_TERMS = (
    "标记",
    "完成第",
    "更新步骤",
    "更新任务",
    "跳过",
)


@dataclass(frozen=True)
class TaskControlIntentDecision:
    task_plan_contract: TaskPlanTurnContract | None
    task_execution_contract: TaskExecutionTurnContract
    reason: str


class TaskControlIntentArbiter:
    """Chooses exactly one strict control scope for a turn."""

    def resolve(
        self,
        *,
        task_plan_contract: TaskPlanTurnContract,
        task_execution_contract: TaskExecutionTurnContract,
        user_text: str,
        metadata: Mapping[str, Any],
    ) -> TaskControlIntentDecision:
        if task_execution_contract.action == "replay":
            return TaskControlIntentDecision(
                task_plan_contract=None,
                task_execution_contract=task_execution_contract,
                reason="runtime_request_replay",
            )

        if task_plan_contract.active and _is_explicit_plan_contract(
            task_plan_contract, user_text
        ):
            return TaskControlIntentDecision(
                task_plan_contract=task_plan_contract,
                task_execution_contract=TaskExecutionTurnContract.inactive(),
                reason="explicit_task_plan_intent",
            )

        if task_execution_contract.active:
            return TaskControlIntentDecision(
                task_plan_contract=None,
                task_execution_contract=task_execution_contract,
                reason="explicit_task_execution_intent",
            )

        if task_plan_contract.active:
            return TaskControlIntentDecision(
                task_plan_contract=task_plan_contract,
                task_execution_contract=TaskExecutionTurnContract.inactive(),
                reason="task_plan_fallback",
            )

        return TaskControlIntentDecision(
            task_plan_contract=None,
            task_execution_contract=TaskExecutionTurnContract.inactive(),
            reason="no_strict_task_control_intent",
        )


def _is_explicit_plan_contract(contract: TaskPlanTurnContract, text: str) -> bool:
    if contract.action in {"plan_create", "plan_inspect"}:
        return True
    normalized = (text or "").lower()
    return any(term.lower() in normalized for term in _EXPLICIT_PLAN_UPDATE_TERMS)
