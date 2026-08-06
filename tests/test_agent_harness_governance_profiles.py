from __future__ import annotations

import pytest

from agent.config_models import TaskExecutionConfig
from eval.agent_harness.governance_profiles import (
    DEFAULT_G10A_PROFILE_NAMES,
    resolve_governance_profile,
)


def test_governance_profiles_define_increasing_constraints() -> None:
    baseline = resolve_governance_profile("baseline_open")
    budget = resolve_governance_profile("budget-limited")
    full = resolve_governance_profile("full_governance")

    assert DEFAULT_G10A_PROFILE_NAMES == (
        "baseline_open",
        "budget_limited",
        "full_governance",
    )
    assert baseline.call_budget_enabled is False
    assert budget.call_budget_enabled is True
    assert budget.evidence_stop_enabled is True
    assert full.risk_preflight_enabled is True
    assert full.path_check_enabled is True
    assert full.restricted_execution_enabled is True


def test_governance_profile_maps_to_existing_task_execution_config_subset() -> None:
    budget = resolve_governance_profile("budget_limited")
    full = resolve_governance_profile("full_governance")

    budget_config = budget.to_task_execution_config()
    full_config = full.to_task_execution_config()

    assert isinstance(budget_config, TaskExecutionConfig)
    assert budget_config.enabled is True
    assert budget_config.max_work_tool_calls == 2
    assert full_config.enabled is True
    assert full_config.max_work_tool_calls == 3
    assert full_config.auto_allowed_risks == ["read-only"]


def test_profile_marks_capabilities_that_still_need_real_executor_wiring() -> None:
    full = resolve_governance_profile("full_governance")

    assert full.requires_real_executor_fields == (
        "tool_scope_enforced",
        "risk_preflight_enabled",
        "approval_required_for_high_risk",
        "path_check_enabled",
        "restricted_execution_enabled",
    )


def test_unknown_governance_profile_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown governance profile"):
        resolve_governance_profile("unsafe-open-ended")
