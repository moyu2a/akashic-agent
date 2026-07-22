from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

RiskStrategyAction = Literal["allow", "deny", "defer", "not_applicable"]

_ACTIONS = frozenset({"allow", "deny", "defer", "not_applicable"})
_SHELL_CAPABILITIES = frozenset({"shell.execute", "process.execute"})


@dataclass(frozen=True)
class RiskStrategyContext:
    tool_name: str
    registry_risk: str = "unknown"
    capabilities: frozenset[str] = field(default_factory=frozenset)
    source: str = "passive"
    task_execution_active: bool = False
    task_execution_phase: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "capabilities", frozenset(self.capabilities))


@dataclass(frozen=True)
class RiskStrategyDecision:
    action: RiskStrategyAction
    reason: str
    risk: str
    approval_scope: str = ""
    user_prompt: str = ""
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.action not in _ACTIONS:
            raise ValueError("unsupported risk strategy action")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def effective(self) -> bool:
        return self.action != "not_applicable"

    def to_trace_metadata(self) -> dict[str, object]:
        return {
            "action": self.action,
            "reason": self.reason,
            "risk": self.risk,
            "approval_scope": self.approval_scope,
            "user_prompt": self.user_prompt,
            "metadata": dict(self.metadata),
        }


class DefaultToolRiskStrategy:
    policy_name = "DefaultToolRiskStrategy"

    def evaluate(self, context: RiskStrategyContext) -> RiskStrategyDecision:
        risk = context.registry_risk or "unknown"
        if context.source != "passive":
            return RiskStrategyDecision(
                action="not_applicable",
                reason="risk_strategy_non_passive_not_applicable",
                risk=risk,
            )
        if context.task_execution_active:
            return RiskStrategyDecision(
                action="not_applicable",
                reason="risk_strategy_task_execution_not_applicable",
                risk=risk,
            )
        if context.tool_name == "shell" or context.capabilities & _SHELL_CAPABILITIES:
            return RiskStrategyDecision(
                action="defer",
                reason="risk_strategy_shell_requires_approval",
                risk=risk,
                approval_scope="tool_call",
                user_prompt="This shell command needs explicit approval before execution.",
            )
        if risk == "destructive":
            return RiskStrategyDecision(
                action="deny",
                reason="risk_strategy_destructive_denied",
                risk=risk,
            )
        if risk == "read-only":
            return RiskStrategyDecision(
                action="allow",
                reason="risk_strategy_read_only_allowed",
                risk=risk,
            )
        if risk == "write":
            return RiskStrategyDecision(
                action="defer",
                reason="risk_strategy_write_requires_approval",
                risk=risk,
                approval_scope="tool_call",
                user_prompt="This write operation needs explicit approval before execution.",
            )
        if risk == "external-side-effect":
            return RiskStrategyDecision(
                action="defer",
                reason="risk_strategy_external_side_effect_requires_approval",
                risk=risk,
                approval_scope="tool_call",
                user_prompt="This external side effect needs explicit approval before execution.",
            )
        return RiskStrategyDecision(
            action="defer",
            reason="risk_strategy_unknown_requires_approval",
            risk=risk,
            approval_scope="tool_call",
            user_prompt="This tool has unknown execution risk and needs approval.",
        )
