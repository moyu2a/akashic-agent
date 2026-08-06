from __future__ import annotations

from dataclasses import asdict, dataclass

from agent.config_models import TaskExecutionConfig

DEFAULT_G10A_PROFILE_NAMES = (
    "baseline_open",
    "budget_limited",
    "full_governance",
)


@dataclass(frozen=True)
class GovernanceProfileSpec:
    name: str
    task_execution_enabled: bool
    max_work_tool_calls: int
    max_tool_search_calls: int
    call_budget_enabled: bool
    evidence_stop_enabled: bool
    tool_scope_enforced: bool
    risk_preflight_enabled: bool
    approval_required_for_high_risk: bool
    path_check_enabled: bool
    restricted_execution_enabled: bool
    production_mapping_notes: tuple[str, ...] = ()

    @property
    def requires_real_executor_fields(self) -> tuple[str, ...]:
        fields: list[str] = []
        for field_name in (
            "tool_scope_enforced",
            "risk_preflight_enabled",
            "approval_required_for_high_risk",
            "path_check_enabled",
            "restricted_execution_enabled",
        ):
            if bool(getattr(self, field_name)):
                fields.append(field_name)
        return tuple(fields)

    def to_task_execution_config(self) -> TaskExecutionConfig:
        return TaskExecutionConfig(
            enabled=self.task_execution_enabled,
            auto_allowed_risks=["read-only"],
            max_work_tool_calls=self.max_work_tool_calls,
            max_tool_search_calls=self.max_tool_search_calls,
        )

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["requires_real_executor_fields"] = self.requires_real_executor_fields
        payload["task_execution_config"] = asdict(self.to_task_execution_config())
        return payload


_PROFILE_SPECS: dict[str, GovernanceProfileSpec] = {
    "baseline_open": GovernanceProfileSpec(
        name="baseline_open",
        task_execution_enabled=False,
        max_work_tool_calls=12,
        max_tool_search_calls=1,
        call_budget_enabled=False,
        evidence_stop_enabled=False,
        tool_scope_enforced=False,
        risk_preflight_enabled=False,
        approval_required_for_high_risk=False,
        path_check_enabled=False,
        restricted_execution_enabled=False,
        production_mapping_notes=(
            "Baseline disables task execution governance in the eval profile.",
        ),
    ),
    "budget_limited": GovernanceProfileSpec(
        name="budget_limited",
        task_execution_enabled=True,
        max_work_tool_calls=2,
        max_tool_search_calls=1,
        call_budget_enabled=True,
        evidence_stop_enabled=True,
        tool_scope_enforced=False,
        risk_preflight_enabled=False,
        approval_required_for_high_risk=False,
        path_check_enabled=False,
        restricted_execution_enabled=False,
        production_mapping_notes=(
            "Maps to TaskExecutionConfig budgets available in current production config.",
        ),
    ),
    "full_governance": GovernanceProfileSpec(
        name="full_governance",
        task_execution_enabled=True,
        max_work_tool_calls=3,
        max_tool_search_calls=1,
        call_budget_enabled=True,
        evidence_stop_enabled=True,
        tool_scope_enforced=True,
        risk_preflight_enabled=True,
        approval_required_for_high_risk=True,
        path_check_enabled=True,
        restricted_execution_enabled=True,
        production_mapping_notes=(
            "TaskExecutionConfig supplies the budget subset.",
            "Tool scope, risk preflight, approval, path check, and restricted execution still require real executor wiring.",
        ),
    ),
}


def resolve_governance_profile(name: str) -> GovernanceProfileSpec:
    normalized = str(name or "").strip().lower().replace("-", "_")
    spec = _PROFILE_SPECS.get(normalized)
    if spec is None:
        allowed = ", ".join(DEFAULT_G10A_PROFILE_NAMES)
        raise ValueError(f"unknown governance profile: {name}; allowed: {allowed}")
    return spec


def profile_specs_for(names: tuple[str, ...]) -> tuple[GovernanceProfileSpec, ...]:
    return tuple(resolve_governance_profile(name) for name in names)
