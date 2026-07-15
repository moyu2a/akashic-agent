from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from agent.policies.task_execution_contract import TaskExecutionTurnContract

TaskExecutionRiskAction = Literal["allow", "defer", "deny", "unknown_tool"]


@dataclass(frozen=True)
class TaskExecutionRiskDecision:
    action: TaskExecutionRiskAction
    reason: str
    metadata: Mapping[str, object] = field(default_factory=dict)


class TaskExecutionRiskPolicy:
    """Classify active work calls without touching runtime or durable state."""

    def evaluate(
        self,
        *,
        contract: TaskExecutionTurnContract | None,
        tool_name: str,
        registered: bool,
        registry_risk: str,
    ) -> TaskExecutionRiskDecision | None:
        if contract is None or not contract.active or contract.phase != "work":
            return None
        if not registered:
            return TaskExecutionRiskDecision(
                action="unknown_tool",
                reason="task_execution_unknown_tool",
                metadata={"tool_name": tool_name},
            )
        if registry_risk == "destructive":
            return TaskExecutionRiskDecision(
                action="deny",
                reason="task_execution_destructive_denied",
                metadata={"tool_name": tool_name, "tool_risk": registry_risk},
            )
        if tool_name == "shell" or registry_risk != "read-only":
            return TaskExecutionRiskDecision(
                action="defer",
                reason="task_execution_authorization_required",
                metadata={
                    "tool_name": tool_name,
                    "tool_risk": registry_risk,
                    "durable_transition": "waiting_authorization",
                },
            )
        return TaskExecutionRiskDecision(
            action="allow",
            reason="task_execution_read_only_allowed",
            metadata={"tool_name": tool_name, "tool_risk": registry_risk},
        )
