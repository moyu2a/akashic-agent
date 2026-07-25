from __future__ import annotations

import json
from pathlib import Path

from memory2.eval_cases import load_eval_cases
from memory2.eval_runner import run_eval_cases
from memory2.eval_uplift import (
    build_uplift_report,
    write_uplift_json,
    write_uplift_markdown,
)


FIXTURE_ROOT = Path("tests/fixtures/memory_eval_cases")


def test_build_uplift_report_summarizes_phase2_to_phase5() -> None:
    cases = load_eval_cases(FIXTURE_ROOT)
    eval_report = run_eval_cases(cases)
    report = build_uplift_report(cases, eval_report)

    assert report.metrics["phase6c_level"] == "offline_uplift_proxy"
    assert report.metrics["offline_fixture_only"] is True
    assert report.metrics["llm_calls_enabled"] is False
    assert report.metrics["embedding_calls_enabled"] is False
    assert report.metrics["real_memory_db_enabled"] is False
    assert report.metrics["answer_quality_available"] is False
    assert report.metrics["production_uplift_claimed"] is False
    assert report.metrics["case_count"] == 9
    assert report.metrics["profile_count"] == 30
    assert report.metrics["feature_record_count"] >= 9
    assert set(report.phase_summaries) >= {"phase2", "phase3", "phase4", "phase5", "all"}
    assert report.phase_summaries["phase2"].feature_record_count >= 2
    assert report.phase_summaries["phase5"].estimated_token_saving >= 3
    assert report.metrics["production_uplift_claimed"] is False


def test_uplift_report_records_feature_level_proxy_scores() -> None:
    cases = load_eval_cases(FIXTURE_ROOT)
    eval_report = run_eval_cases(cases)
    report = build_uplift_report(cases, eval_report)
    by_feature = {
        (record.case_id, record.profile, record.feature_name): record
        for record in report.feature_records
    }

    graph = by_feature[("vague_reference_graph", "phase2", "graph_retrieval")]
    assert graph.phase == "phase2"
    assert graph.metric_kind == "retrieval_proxy"
    assert graph.metric_name == "label_hit_rate"
    assert graph.experimental_score >= graph.baseline_score
    assert graph.expected_ids == ("m_graph_1", "m_graph_2")
    assert graph.uplift >= 0.0

    injection = by_feature[
        ("injection_governance_budget", "phase3", "injection_governance_shadow")
    ]
    assert injection.metric_kind == "injection_proxy"
    assert injection.positive_signal_count >= 1
    assert injection.token_delta == 14

    sleep = by_feature[("stale_memory_sleep", "phase5", "sleep_consolidation_shadow")]
    assert sleep.metric_kind == "consolidation_proxy"
    assert sleep.positive_signal_count >= 2


def test_write_uplift_reports_are_stable_and_sanitized(tmp_path: Path) -> None:
    cases = load_eval_cases(FIXTURE_ROOT)
    eval_report = run_eval_cases(cases)
    report = build_uplift_report(cases, eval_report)
    json_path = tmp_path / "memory_uplift_eval.json"
    md_path = tmp_path / "memory_uplift_eval.md"

    write_uplift_json(report, json_path)
    write_uplift_markdown(report, md_path)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["metrics"]["phase6c_level"] == "offline_uplift_proxy"
    assert "phase2" in payload["phase_summaries"]
    assert payload["feature_records"]
    assert md_path.read_text(encoding="utf-8").startswith(
        "# Memory Offline Uplift Evaluation Report"
    )
    combined = json_path.read_text(encoding="utf-8") + md_path.read_text(
        encoding="utf-8"
    )
    assert "api_key" not in combined
    assert "sk-" not in combined
    assert "answer_text" not in combined
