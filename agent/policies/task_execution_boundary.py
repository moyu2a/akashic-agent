from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, Protocol

from agent.policies.task_execution_contract import TaskExecutionTurnContract
from agent.policies.tool_invocation_policy import (
    ToolInvocationContext,
    ToolInvocationDecision,
    ToolInvocationPolicyEngine,
)

TaskExecutionRiskAction = Literal["allow", "defer", "deny", "unknown_tool"]


@dataclass(frozen=True)
class TaskExecutionRiskDecision:
    action: TaskExecutionRiskAction
    reason: str
    metadata: Mapping[str, object] = field(default_factory=dict)


class ToolInvocationPolicy(Protocol):
    def evaluate(self, context: ToolInvocationContext) -> ToolInvocationDecision: ...


class TaskExecutionRiskPolicy:
    """Classify active work calls without touching runtime or durable state."""

    def __init__(
        self,
        invocation_policy: ToolInvocationPolicy | None = None,
    ) -> None:
        self._invocation_policy = invocation_policy or ToolInvocationPolicyEngine()

    def evaluate(
        self,
        *,
        contract: TaskExecutionTurnContract | None,
        tool_name: str,
        registered: bool,
        registry_risk: str,
        registry_capabilities: frozenset[str] | None = None,
    ) -> TaskExecutionRiskDecision | None:
        if contract is None or not contract.active or contract.phase != "work":
            return None
        if not registered:
            return TaskExecutionRiskDecision(
                action="unknown_tool",
                reason="task_execution_unknown_tool",
                metadata={"tool_name": tool_name},
            )
        decision = self._invocation_policy.evaluate(
            ToolInvocationContext(
                tool_name=tool_name,
                registered=registered,
                registry_risk=registry_risk,
                capabilities=registry_capabilities or frozenset(),
                source="task_execution",
                task_execution_active=True,
                task_execution_phase="work",
            )
        )
        if decision.action == "deny":
            return TaskExecutionRiskDecision(
                action="deny",
                reason="task_execution_destructive_denied",
                metadata={"tool_name": tool_name, "tool_risk": registry_risk},
            )
        if decision.action == "defer":
            return TaskExecutionRiskDecision(
                action="defer",
                reason="task_execution_authorization_required",
                metadata={
                    "tool_name": tool_name,
                    "tool_risk": registry_risk,
                    "durable_transition": "waiting_authorization",
                    "policy_reason": decision.reason,
                },
            )
        return TaskExecutionRiskDecision(
            action="allow",
            reason=(
                "task_execution_control_allowed"
                if decision.reason == "tool_invocation_task_execution_control_allowed"
                else "task_execution_read_only_allowed"
            ),
            metadata={
                "tool_name": tool_name,
                "tool_risk": registry_risk,
                "policy_reason": decision.reason,
            },
        )
