from __future__ import annotations

import json

from eval.agent_harness.protocol import RunManifest, TaskSpec
from eval.agent_harness.real_trace import normalize_real_trace
from eval.agent_harness.runtime_profiles import resolve_runtime_profile_patch


def _manifest() -> RunManifest:
    return RunManifest(
        run_id="real-run",
        git_sha="abc123",
        dataset_version="g10a",
        dataset_hash="hash",
        model="real-model",
        provider="real-provider",
        config_hash="cfg",
        governance_profile="full_governance",
        environment_kind="ipc_live",
        seed=0,
        repeat_index=0,
        runner_version="agent-harness-v2",
    )


def _task() -> TaskSpec:
    return TaskSpec(case_id="case-1", category="security")


def test_missing_token_and_latency_stay_none() -> None:
    result = normalize_real_trace(
        {
            "status": "pass",
            "events": [
                {"event_type": "prompt", "payload": {"text": "secret prompt"}},
                {"event_type": "reply", "payload": {"text": "secret reply"}},
            ],
        },
        task=_task(),
        manifest=_manifest(),
        runtime_profile=resolve_runtime_profile_patch("budget_limited"),
        observed_fields=set(),
    )

    assert result.metrics["prompt_tokens"] is None
    assert result.metrics["latency_ms"] is None
    assert (
        result.metrics["metric_provenance"]["prompt_tokens"] == "missing:not_recorded"
    )
    assert result.metrics["metric_provenance"]["latency_ms"] == "missing:not_recorded"
    rendered = json.dumps(result.events, ensure_ascii=False)
    assert "secret prompt" not in rendered
    assert "secret reply" not in rendered


def test_denied_tool_execution_increments_hard_gate_failure() -> None:
    result = normalize_real_trace(
        {
            "status": "fail",
            "security_hard_gates": {"forbidden_execution": 1},
        },
        task=_task(),
        manifest=_manifest(),
        runtime_profile=resolve_runtime_profile_patch("budget_limited"),
        observed_fields={"call_budget_observed"},
    )

    assert result.metrics["security_hard_gates"]["forbidden_execution"] == 1
    assert result.metrics["security_hard_gate_passed"] is False


def test_denied_but_skipped_tool_does_not_increment_forbidden_execution() -> None:
    result = normalize_real_trace(
        {
            "status": "fail",
            "security_hard_gates": {
                "denied_invoker_reach": 1,
                "forbidden_execution": 0,
            },
        },
        task=_task(),
        manifest=_manifest(),
        runtime_profile=resolve_runtime_profile_patch("budget_limited"),
        observed_fields={"call_budget_observed"},
    )

    assert result.metrics["security_hard_gates"]["forbidden_execution"] == 0
    assert result.metrics["security_hard_gates"]["denied_invoker_reach"] == 1


def test_full_governance_required_fields_remain_missing_until_observed() -> None:
    result = normalize_real_trace(
        {
            "status": "pass",
            "observed_fields": ["tool_scope_enforced", "path_check_enabled"],
        },
        task=_task(),
        manifest=_manifest(),
        runtime_profile=resolve_runtime_profile_patch("full_governance"),
        observed_fields={"tool_scope_enforced", "path_check_enabled"},
    )

    assert result.metrics["profile_contract_observed_fields"] == (
        "tool_scope_enforced",
        "path_check_enabled",
    )
    assert result.metrics["profile_contract_missing_fields"] == (
        "risk_preflight_enabled",
        "approval_required_for_high_risk",
        "restricted_execution_enabled",
    )


def test_budget_limited_records_budget_evidence_from_real_trace_fields() -> None:
    result = normalize_real_trace(
        {
            "status": "pass",
            "call_budget_observed": True,
            "evidence_stop_observed": True,
            "prompt_tokens": 17,
            "completion_tokens": 9,
            "total_tokens": 26,
        },
        task=_task(),
        manifest=_manifest(),
        runtime_profile=resolve_runtime_profile_patch("budget_limited"),
        observed_fields={"call_budget_observed", "evidence_stop_observed"},
    )

    assert result.metrics["call_budget_observed"] is True
    assert result.metrics["evidence_stop_observed"] is True
    assert result.metrics["prompt_tokens"] == 17
    assert result.metrics["total_tokens"] == 26
