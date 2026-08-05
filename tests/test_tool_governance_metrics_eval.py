from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import asyncio

from agent.governance.metrics_eval import (
    DEFAULT_TOOL_GOVERNANCE_CASES,
    DEFAULT_TOOL_GOVERNANCE_PROFILES,
    TOOL_GOVERNANCE_EVAL_PROFILE_KEY,
    ToolGovernanceEvalRecord,
    build_real_llm_turn_specs,
    run_tool_governance_dry_eval,
    run_tool_governance_real_eval,
    summarize_tool_governance_records,
    write_tool_governance_report_json,
    write_tool_governance_report_markdown,
)


def test_default_matrix_has_twenty_cases_and_three_profiles() -> None:
    scenarios = {}
    for case in DEFAULT_TOOL_GOVERNANCE_CASES:
        scenarios[case.scenario] = scenarios.get(case.scenario, 0) + 1

    assert len(DEFAULT_TOOL_GOVERNANCE_CASES) == 20
    assert scenarios == {
        "doc_rag_boundary": 5,
        "task_plan_boundary": 5,
        "high_risk_side_effect": 5,
        "session_trace_boundary": 5,
    }
    assert DEFAULT_TOOL_GOVERNANCE_PROFILES == (
        "baseline_open",
        "intent_scope_only",
        "full_governance",
    )


def test_dry_eval_generates_full_sixty_turn_matrix() -> None:
    report = run_tool_governance_dry_eval(run_id="dry-test")

    assert report.metrics["mode"] == "dry"
    assert report.metrics["real_llm"] is False
    assert report.metrics["case_count"] == 20
    assert report.metrics["turn_count"] == 60
    assert report.metrics["max_react_iterations"] == 12
    assert report.metrics["max_real_llm_calls"] == 720
    assert report.metrics["gate_pass"] is True
    assert report.profile_summaries["full_governance"]["turn_count"] == 20
    assert report.scenario_summaries["doc_rag_boundary"]["turn_count"] == 15
    assert report.paired_deltas["full_governance"]["paired_case_count"] == 20
    assert report.paired_deltas["full_governance"]["executed_tools_delta_pct"] < 0


def test_summary_hard_gate_fails_for_security_and_audit_violations() -> None:
    report = summarize_tool_governance_records(
        [
            ToolGovernanceEvalRecord(
                run_id="unit",
                mode="dry",
                profile="full_governance",
                case_id="risk_001",
                scenario="high_risk_side_effect",
                prompt_preview="write outside workspace",
                correctness="PASS",
                actual_prompt_tokens_sum=100,
                actual_total_tokens_sum=120,
                turn_duration_ms=1000,
                llm_duration_ms_sum=900,
                react_iteration_count=2,
                tool_call_count=1,
                executed_tool_count=1,
                expected_tools=("write_file",),
                actual_tools=("write_file",),
                forbidden_tools=("write_file",),
                expected_tool_missing_count=0,
                forbidden_tool_call_count=1,
                forbidden_tool_executed_count=1,
                soft_stop_count=0,
                batch_skip_count=0,
                deny_count=1,
                defer_count=0,
                approval_created_count=0,
                approval_bypass_count=1,
                args_hash_mismatch_count=0,
                resource_policy_deny_count=0,
                destructive_hard_deny_count=0,
                invoker_reached_when_denied_count=1,
                audit_event_count=0,
                audit_event_coverage_passed=False,
                redaction_violation_count=1,
                approval_lifecycle_complete_rate=0.0,
                trace_query_accuracy=True,
                note="unit",
            )
        ],
        mode="dry",
        run_id="unit",
    )

    assert report.metrics["gate_pass"] is False
    assert report.metrics["hard_gate_fail_count"] == 5
    row = report.profile_summaries["full_governance"]
    assert row["forbidden_tool_executed_count"] == 1
    assert row["approval_bypass_count"] == 1
    assert row["redaction_violation_count"] == 1
    assert row["invoker_reached_when_denied_count"] == 1
    assert row["audit_coverage_failure_count"] == 1


def test_paired_delta_keeps_zero_executed_tool_counts() -> None:
    base = ToolGovernanceEvalRecord(
        run_id="unit",
        mode="real_llm",
        profile="baseline_open",
        case_id="risk_002",
        scenario="high_risk_side_effect",
        prompt_preview="deny outside workspace write",
        correctness="PASS",
        actual_prompt_tokens_sum=100,
        actual_total_tokens_sum=120,
        turn_duration_ms=1000,
        llm_duration_ms_sum=900,
        react_iteration_count=2,
        tool_call_count=2,
        executed_tool_count=4,
        expected_tools=("write_file",),
        actual_tools=("write_file",),
        forbidden_tools=(),
        expected_tool_missing_count=0,
        forbidden_tool_call_count=0,
        forbidden_tool_executed_count=0,
        soft_stop_count=0,
        batch_skip_count=0,
        deny_count=0,
        defer_count=0,
        approval_created_count=0,
        approval_bypass_count=0,
        args_hash_mismatch_count=0,
        resource_policy_deny_count=0,
        destructive_hard_deny_count=0,
        invoker_reached_when_denied_count=0,
        audit_event_count=2,
        audit_event_coverage_passed=True,
        redaction_violation_count=0,
        approval_lifecycle_complete_rate=0.0,
        trace_query_accuracy=True,
        note="unit",
    )
    candidate = ToolGovernanceEvalRecord(
        **{
            **base.__dict__,
            "profile": "full_governance",
            "executed_tool_count": 0,
            "actual_tools": (),
        }
    )

    report = summarize_tool_governance_records(
        [base, candidate],
        mode="real_llm",
        run_id="unit",
    )

    assert report.paired_deltas["full_governance"]["executed_tools_delta_pct"] == -100


def test_report_writers_emit_metrics_without_raw_secret(tmp_path: Path) -> None:
    report = run_tool_governance_dry_eval(run_id="dry-secret")
    json_path = tmp_path / "tool_governance_metrics.json"
    md_path = tmp_path / "tool_governance_metrics.md"

    write_tool_governance_report_json(report, json_path)
    write_tool_governance_report_markdown(report, md_path)

    raw_json = json_path.read_text(encoding="utf-8")
    payload = json.loads(raw_json)
    assert payload["metrics"]["turn_count"] == 60
    assert payload["metrics"]["gate_pass"] is True
    assert "secret-value" not in raw_json
    assert "Bearer " not in raw_json
    text = md_path.read_text(encoding="utf-8")
    assert "# Tool Governance Metrics v1" in text
    assert "baseline_open" in text
    assert "full_governance" in text
    assert "Paired Delta" in text


def test_cli_dry_run_writes_reports(tmp_path: Path) -> None:
    out_dir = tmp_path / "reports"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_tool_governance_metrics_eval.py",
            "--mode",
            "dry",
            "--out-dir",
            str(out_dir),
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "tool_governance_metrics.json" in completed.stdout
    assert (out_dir / "tool_governance_metrics.json").exists()
    assert (out_dir / "tool_governance_metrics.md").exists()


def test_cli_real_mode_requires_explicit_real_llm_gate(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_tool_governance_metrics_eval.py",
            "--mode",
            "real_llm",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(tmp_path / "reports"),
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 2
    assert "--enable-real-llm is required" in completed.stderr


def test_real_llm_turn_specs_inject_profile_metadata() -> None:
    specs = build_real_llm_turn_specs(max_react_iterations=12)

    assert len(specs) == 60
    assert specs[0].case_id == "doc_001"
    assert specs[0].profile == "baseline_open"
    assert specs[0].max_react_iterations == 12
    assert specs[0].turn_metadata == {
        TOOL_GOVERNANCE_EVAL_PROFILE_KEY: "baseline_open",
        "tool_governance_eval_case_id": "doc_001",
        "tool_governance_eval_scenario": "doc_rag_boundary",
    }
    assert specs[-1].profile == "full_governance"


def test_real_llm_runner_requires_runtime_adapter() -> None:
    try:
        asyncio.run(run_tool_governance_real_eval(run_id="real-missing-adapter"))
    except RuntimeError as exc:
        assert "real LLM runtime adapter is required" in str(exc)
    else:
        raise AssertionError("real LLM runner must not synthesize fake records")


def test_cli_real_mode_reaches_adapter_boundary_after_gate(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        """
provider = "openai"
model = "test-model"
api_key = ""
base_url = "https://example.invalid/v1"
""".strip() + "\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_tool_governance_metrics_eval.py",
            "--mode",
            "real_llm",
            "--workspace",
            str(tmp_path / "workspace"),
            "--config",
            str(config),
            "--out-dir",
            str(tmp_path / "reports"),
            "--enable-real-llm",
        ],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 2
    assert (
        "real LLM governance metrics require a configured api_key" in completed.stderr
    )
    assert "not wired yet" not in completed.stderr
