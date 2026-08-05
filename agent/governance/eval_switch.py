from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

TOOL_GOVERNANCE_EVAL_PROFILE_KEY = "tool_governance_eval_profile"


@dataclass(frozen=True)
class ToolGovernanceEvalSwitch:
    active: bool
    profile: str
    hard_safety_enabled: bool
    intent_scope_enabled: bool
    tool_budget_enabled: bool
    evidence_completion_enabled: bool
    react_boundary_enabled: bool

    @classmethod
    def production_default(cls) -> "ToolGovernanceEvalSwitch":
        return cls(
            active=False,
            profile="production_default",
            hard_safety_enabled=True,
            intent_scope_enabled=True,
            tool_budget_enabled=True,
            evidence_completion_enabled=True,
            react_boundary_enabled=True,
        )

    def to_trace(self) -> dict[str, object]:
        return {
            "active": self.active,
            "profile": self.profile,
            "hard_safety_enabled": self.hard_safety_enabled,
            "intent_scope_enabled": self.intent_scope_enabled,
            "tool_budget_enabled": self.tool_budget_enabled,
            "evidence_completion_enabled": self.evidence_completion_enabled,
            "react_boundary_enabled": self.react_boundary_enabled,
        }


def resolve_tool_governance_eval_switch(
    metadata: Mapping[str, object] | None,
) -> ToolGovernanceEvalSwitch:
    if metadata is None or TOOL_GOVERNANCE_EVAL_PROFILE_KEY not in metadata:
        return ToolGovernanceEvalSwitch.production_default()

    profile = str(metadata.get(TOOL_GOVERNANCE_EVAL_PROFILE_KEY) or "").strip()
    if profile == "baseline_open":
        return ToolGovernanceEvalSwitch(
            active=True,
            profile=profile,
            hard_safety_enabled=True,
            intent_scope_enabled=False,
            tool_budget_enabled=False,
            evidence_completion_enabled=False,
            react_boundary_enabled=False,
        )
    if profile == "intent_scope_only":
        return ToolGovernanceEvalSwitch(
            active=True,
            profile=profile,
            hard_safety_enabled=True,
            intent_scope_enabled=True,
            tool_budget_enabled=False,
            evidence_completion_enabled=False,
            react_boundary_enabled=False,
        )
    if profile == "full_governance":
        return ToolGovernanceEvalSwitch(
            active=True,
            profile=profile,
            hard_safety_enabled=True,
            intent_scope_enabled=True,
            tool_budget_enabled=True,
            evidence_completion_enabled=True,
            react_boundary_enabled=True,
        )
    raise ValueError(f"unknown tool governance eval profile: {profile}")
