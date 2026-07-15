from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any

from agent.policies.task_execution_contract import (
    TaskExecutionTurnContract,
    infer_task_execution_contract,
)
from agent.policies.task_plan_contract import (
    TaskPlanTurnContract,
    infer_task_plan_turn_decision,
)
from agent.policies.tool_access_types import ToolAccessContext

_EXPLICIT_PLAN_UPDATE_TERMS = (
    "标记",
    "完成第",
    "更新步骤",
    "更新任务",
    "跳过",
)
_RESOLUTION_MARKER = object()
_RESOLUTION_MARKER_KEY = "_task_control_resolution_marker"
_BACKGROUND_MODE_KEY = "_task_control_background_mode"


@dataclass(frozen=True)
class TaskControlIntentDecision:
    task_plan_contract: TaskPlanTurnContract
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
                task_plan_contract=TaskPlanTurnContract.inactive(),
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
                task_plan_contract=TaskPlanTurnContract.inactive(),
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
            task_plan_contract=TaskPlanTurnContract.inactive(),
            task_execution_contract=TaskExecutionTurnContract.inactive(),
            reason="no_strict_task_control_intent",
        )


def _is_explicit_plan_contract(contract: TaskPlanTurnContract, text: str) -> bool:
    if contract.action in {"plan_create", "plan_inspect"}:
        return True
    normalized = (text or "").lower()
    return any(term.lower() in normalized for term in _EXPLICIT_PLAN_UPDATE_TERMS)


def resolve_task_control_context(context: ToolAccessContext) -> ToolAccessContext:
    """Attach the one canonical task-control decision to an access context."""
    metadata = dict(context.turn_metadata)
    if metadata.get(_RESOLUTION_MARKER_KEY) is _RESOLUTION_MARKER:
        return context

    task_plan_decision = infer_task_plan_turn_decision(
        context.user_text,
        has_active_task=bool(metadata.get("has_active_task")),
    )
    supplied_task_plan = metadata.get("task_plan_contract")
    task_plan_contract = (
        supplied_task_plan
        if isinstance(supplied_task_plan, TaskPlanTurnContract)
        else task_plan_decision.contract
    )
    supplied_execution = metadata.get("task_execution_contract")
    task_execution_contract = (
        supplied_execution
        if isinstance(supplied_execution, TaskExecutionTurnContract)
        else infer_task_execution_contract(context.user_text, metadata)
    )
    decision = TaskControlIntentArbiter().resolve(
        task_plan_contract=task_plan_contract,
        task_execution_contract=task_execution_contract,
        user_text=context.user_text,
        metadata=metadata,
    )
    metadata["task_plan_contract"] = decision.task_plan_contract
    metadata["task_execution_contract"] = decision.task_execution_contract
    metadata[_BACKGROUND_MODE_KEY] = (
        task_plan_decision.background_mode
        if not decision.task_plan_contract.active
        and not decision.task_execution_contract.active
        else "none"
    )
    metadata[_RESOLUTION_MARKER_KEY] = _RESOLUTION_MARKER
    return replace(context, turn_metadata=metadata)
