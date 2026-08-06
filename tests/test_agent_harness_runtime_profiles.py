from __future__ import annotations

from dataclasses import asdict

import pytest

from agent.config_models import TaskExecutionConfig
from eval.agent_harness.runtime_profiles import (
    RuntimeProfilePatch,
    missing_required_observed_fields,
    profile_observation_satisfied,
    resolve_runtime_profile_patch,
)


def test_runtime_profile_patch_maps_baseline_open_to_disabled_task_execution() -> None:
    patch = resolve_runtime_profile_patch("baseline-open")

    assert patch == RuntimeProfilePatch(
        governance_profile="baseline_open",
        task_execution=TaskExecutionConfig(enabled=False),
        optimization_profile="baseline",
        metadata={
            "call_budget_enabled": False,
            "evidence_stop_enabled": False,
            "profile_contract": "g10a_real_executor",
        },
        requires_real_executor_fields=(),
    )


def test_runtime_profile_patch_maps_budget_limited_to_current_budget_subset() -> None:
    patch = resolve_runtime_profile_patch("budget_limited")

    assert patch.governance_profile == "budget_limited"
    assert patch.task_execution == TaskExecutionConfig(
        enabled=True,
        max_work_tool_calls=2,
        max_tool_search_calls=1,
    )
    assert patch.optimization_profile == "baseline"
    assert patch.requires_real_executor_fields == ()
    assert patch.metadata["call_budget_enabled"] is True
    assert patch.metadata["evidence_stop_enabled"] is True


def test_runtime_profile_patch_keeps_full_governance_observed_fields_explicit() -> None:
    patch = resolve_runtime_profile_patch("full_governance")

    assert patch.task_execution == TaskExecutionConfig(
        enabled=True,
        max_work_tool_calls=3,
        max_tool_search_calls=1,
    )
    assert patch.requires_real_executor_fields == (
        "tool_scope_enforced",
        "risk_preflight_enabled",
        "approval_required_for_high_risk",
        "path_check_enabled",
        "restricted_execution_enabled",
    )
    assert patch.metadata["profile_contract"] == "g10a_real_executor"


def test_full_governance_is_not_observed_until_all_required_fields_are_present() -> (
    None
):
    patch = resolve_runtime_profile_patch("full_governance")

    observed = {
        "tool_scope_enforced",
        "risk_preflight_enabled",
        "path_check_enabled",
    }

    assert profile_observation_satisfied(patch, observed) is False
    assert missing_required_observed_fields(patch, observed) == (
        "approval_required_for_high_risk",
        "restricted_execution_enabled",
    )


def test_profile_observation_is_satisfied_when_all_required_fields_are_present() -> (
    None
):
    patch = resolve_runtime_profile_patch("full_governance")

    assert profile_observation_satisfied(
        patch,
        {
            "tool_scope_enforced",
            "risk_preflight_enabled",
            "approval_required_for_high_risk",
            "path_check_enabled",
            "restricted_execution_enabled",
            "extra_trace_field",
        },
    )


def test_unknown_runtime_profile_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown governance profile"):
        resolve_runtime_profile_patch("shadow-open")


def test_runtime_profile_patch_is_report_serializable_without_private_config() -> None:
    patch = resolve_runtime_profile_patch("budget_limited")

    payload = asdict(patch)

    assert payload["governance_profile"] == "budget_limited"
    assert payload["task_execution"]["enabled"] is True
    assert payload["task_execution"]["max_work_tool_calls"] == 2
