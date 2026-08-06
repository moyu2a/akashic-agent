from __future__ import annotations

from pathlib import Path

from eval.agent_harness.legacy import (
    IntegrationStatus,
    load_source_registry,
)


def test_phase_1b_baseline_contains_all_audited_sources() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "my_md/test_docs/eval_suite/phase-1b-compatibility-baseline.json"

    records = load_source_registry(path)

    assert len(records) == 10
    assert {record.source_name: record.integration_status for record in records} == {
        "live_eval_runner": IntegrationStatus.ADAPTER_PASS,
        "deep_live_eval_runner": IntegrationStatus.ADAPTER_PASS,
        "offline_trace_eval": IntegrationStatus.ADAPTER_PASS,
        "memory_eval_runner": IntegrationStatus.ADAPTER_PASS,
        "memory_comprehensive_online_eval": IntegrationStatus.ADAPTER_PASS,
        "optimization_real_ab": IntegrationStatus.ADAPTER_PASS,
        "longmemeval": IntegrationStatus.CONTRACT_PASS,
        "personamem": IntegrationStatus.CONTRACT_PASS,
        "tool_governance_evaluator": IntegrationStatus.CONTRACT_PASS,
        "miniroute_evaluation": IntegrationStatus.CONTRACT_PASS,
    }
    assert all(not record.main_gate_allowed for record in records)
    assert all(not record.adapter_ready for record in records)
    assert {record.source_name for record in records} == {
        "live_eval_runner",
        "deep_live_eval_runner",
        "offline_trace_eval",
        "memory_eval_runner",
        "memory_comprehensive_online_eval",
        "optimization_real_ab",
        "longmemeval",
        "personamem",
        "tool_governance_evaluator",
        "miniroute_evaluation",
    }
