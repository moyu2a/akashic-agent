from __future__ import annotations

import json
from pathlib import Path

from memory2.eval_cases import load_eval_case
from memory2.eval_cases import EvalCase
from memory2.eval_quantitative_cases import build_quantitative_eval_cases
from memory2.eval_runner import (
    _candidate_lanes,
    run_eval_case,
    run_eval_case_files,
    run_eval_cases,
    write_eval_report,
)


FIXTURE_ROOT = Path("tests/fixtures/memory_eval_cases")


def test_off_profile_has_no_experiment_traces_and_passes_for_preference_case() -> None:
    case = load_eval_case(FIXTURE_ROOT / "preference_recall.json")

    result = run_eval_case(case)

    off = result.profiles["off"]
    assert off.trace_features == ()
    assert off.passed is True
    assert off.failures == ()
    assert off.metrics["trace_count"] == 0


def test_phase2_profile_emits_required_tri_retrieval_metrics() -> None:
    case = load_eval_case(FIXTURE_ROOT / "vague_reference_graph.json")

    result = run_eval_case(case)

    phase2 = result.profiles["phase2"]
    assert phase2.passed is True
    assert "tri_retrieval" in phase2.trace_features
    assert "graph_retrieval" in phase2.trace_features
    tri = phase2.traces["tri_retrieval"]
    assert tri.metrics["fused_hit_count"] >= 1
    assert tri.metrics["retrieval_scene"] == "fuzzy_reference"
    assert tri.metrics["route_decision"]["graph_enabled"] is True
    assert tri.metrics["candidate_drop_counts"]["duplicate"] >= 1
    assert tri.metrics["candidate_accept_rate"] < 1.0
    assert tri.metrics["route_hit_rate"] == 1.0
    assert tri.metrics["graph_lane_used"] is False
    graph = phase2.traces["graph_retrieval"]
    assert graph.metrics["graph_fused_hit_count"] >= 1
    assert "baseline_graph_overlap_rate" in graph.metrics
    assert graph.metrics["graph_lane_used"] is False


def test_route_governance_deduplicates_candidates_across_lanes() -> None:
    case = EvalCase(
        id="route_dedupe",
        title="route dedupe",
        category="memory",
        phase_targets=("phase2a",),
        config_profiles=("phase2",),
        setup={
            "scope": {
                "session_key": "cli:local",
                "channel": "cli",
                "chat_id": "local",
            },
            "query": "alpha",
            "memory_items": [
                {
                    "id": "m_alpha",
                    "memory_type": "preference",
                    "summary": "alpha workflow preference",
                    "status": "active",
                    "scope_channel": "cli",
                    "scope_chat_id": "local",
                }
            ],
        },
        expectations={"should_recall_ids": ["m_alpha"]},
    )

    lanes = _candidate_lanes(case)

    assert [item["id"] for item in lanes.semantic_items] == ["m_alpha"]
    assert lanes.keyword_items == []
    assert lanes.route_trace["dropped_by_reason"]["duplicate"] == 1
    assert lanes.route_trace["candidate_accept_rate"] == 0.3333


def test_phase3_profile_emits_rerank_and_injection_metrics() -> None:
    case = load_eval_case(FIXTURE_ROOT / "injection_governance_budget.json")

    result = run_eval_case(case)

    phase3 = result.profiles["phase3"]
    assert phase3.passed is True
    assert "rerank_shadow" in phase3.trace_features
    assert "injection_governance_shadow" in phase3.trace_features
    assert "rerank_changed_count" in phase3.traces["rerank_shadow"].metrics
    rerank_metrics = phase3.traces["rerank_shadow"].metrics
    assert rerank_metrics["retrieval_scene"] == "unknown"
    assert rerank_metrics["route_decision"]["graph_enabled"] is False
    assert rerank_metrics["graph_lane_used"] is False
    injection_metrics = phase3.traces["injection_governance_shadow"].metrics
    assert "prompt_token_delta" in injection_metrics
    assert "dropped_by_reason" in injection_metrics


def test_eval_runner_executes_all_fixture_cases_with_expected_profiles() -> None:
    report = run_eval_case_files(FIXTURE_ROOT)

    assert report.passed is True
    assert report.metrics["case_count"] == 9
    assert report.metrics["profile_count"] == 30
    assert report.metrics["failed_profile_count"] == 0
    by_id = {case.case_id: case for case in report.cases}
    assert by_id["temporary_memory_pollution"].profiles["phase1"].traces[
        "write_value_score"
    ].metrics["temporary_risk_count"] == 1
    assert by_id["cross_scope_isolation"].profiles["phase4"].traces[
        "provenance_shadow"
    ].metrics["cross_scope_memory_count"] == 1
    assert by_id["stale_memory_sleep"].profiles["phase5"].traces[
        "sleep_consolidation_shadow"
    ].metrics["low_value_candidate_count"] == 1


def test_eval_runner_reports_should_not_recall_failure() -> None:
    case = load_eval_case(FIXTURE_ROOT / "cross_scope_isolation.json")

    result = run_eval_case(case)

    phase4 = result.profiles["phase4"]
    assert phase4.passed is True
    assert "m_qq_pref" not in phase4.recalled_ids


def test_baseline_miss_recall_ids_do_not_fail_should_recall_validation() -> None:
    case = next(
        case
        for case in build_quantitative_eval_cases()
        if case.expectations.get("baseline_miss_recall_ids")
    )

    result = run_eval_case(case)
    missed_id = str(case.expectations["baseline_miss_recall_ids"][0])

    assert result.passed is True
    assert (
        missed_id
        not in result.profiles["all"].traces["tri_retrieval"].baseline_result["baseline_ids"]
    )
    assert (
        missed_id
        in result.profiles["all"].traces["tri_retrieval"].experimental_result["fused_ids"]
    )


def test_eval_runner_reports_validation_failures_for_bad_expectations() -> None:
    case = load_eval_case(FIXTURE_ROOT / "preference_recall.json")
    bad_expectations = dict(case.expectations)
    bad_expectations["should_not_recall_ids"] = ["m_pref_cn"]
    bad_case = type(case)(
        id=case.id,
        title=case.title,
        category=case.category,
        phase_targets=case.phase_targets,
        config_profiles=case.config_profiles,
        setup=case.setup,
        expectations=bad_expectations,
        source_path=case.source_path,
    )

    result = run_eval_case(bad_case)

    assert result.passed is False
    assert any(
        "should recall id 'm_pref_cn' was not recalled" in failure
        for failure in result.failures
    )


def test_write_eval_report_serializes_stable_json(tmp_path: Path) -> None:
    report = run_eval_cases([load_eval_case(FIXTURE_ROOT / "preference_recall.json")])
    path = tmp_path / "memory_eval_report.json"

    write_eval_report(report, path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["metrics"]["case_count"] == 1
    assert payload["cases"][0]["case_id"] == "preference_recall"
    assert payload["cases"][0]["profiles"]["off"]["trace_features"] == []
    assert payload["cases"][0]["profiles"]["off"]["passed"] is True
    assert payload["cases"][0]["profiles"]["off"]["failures"] == []
    tri_metrics = payload["cases"][0]["profiles"]["phase2"]["traces"][
        "tri_retrieval"
    ]["metrics"]
    assert tri_metrics["retrieval_scene"] == "unknown"
    assert tri_metrics["route_decision"]["allowed_lanes"] == ["semantic", "keyword"]
