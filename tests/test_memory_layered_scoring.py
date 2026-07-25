from __future__ import annotations

from dataclasses import asdict

from memory2.eval_layered_scoring import (
    ANSWER_LAYER_FORMULA,
    LAYERED_TOTAL_FORMULA,
    LayeredProfileSummary,
    build_layered_scoring_report,
    calculate_answer_layer_score,
    calculate_layered_total_score,
    calculate_memory_hygiene_score,
    calculate_write_governance_score,
)
from memory2.eval_quantitative_cases import build_quantitative_eval_cases
from memory2.eval_quantitative_uplift import CHAIN_PROFILES, QuantitativeProfileSummary


def _summary(
    *,
    profile_name: str = "chain_tri_retrieval",
    feature_name: str = "三路召回",
    case_set: str = "overall",
    answer_rule_pass_rate: float = 0.0,
    memory_grounding_pass_rate: float = 0.0,
    forbidden_violation_rate: float = 0.0,
    main_score: float = 0.0,
) -> QuantitativeProfileSummary:
    return QuantitativeProfileSummary(
        profile_name=profile_name,
        feature_name=feature_name,
        case_set=case_set,
        case_count=1,
        target_count=1,
        success_count=0,
        miss_count=1,
        recall_rate=0.0,
        grounding_count=0,
        forbidden_count=0,
        repeat_count=1,
        answer_rule_pass_rate=answer_rule_pass_rate,
        memory_grounding_pass_rate=memory_grounding_pass_rate,
        forbidden_violation_rate=forbidden_violation_rate,
        main_score=main_score,
        baseline_score=0.0,
        uplift_points=0.0,
        uplift_pct=None,
        token_signal_kind="unavailable",
        token_signal_value="unavailable",
        token_signal_delta="unavailable",
        latency_ms="unavailable",
        latency_delta_ms="unavailable",
        unavailable=(),
    )


def test_formula_constants_are_explicit() -> None:
    assert "answer_layer_score" in ANSWER_LAYER_FORMULA
    assert "layered_total_score" in LAYERED_TOTAL_FORMULA


def test_answer_layer_score_uses_immediate_answer_formula() -> None:
    row = _summary(
        answer_rule_pass_rate=80.0,
        memory_grounding_pass_rate=50.0,
        forbidden_violation_rate=10.0,
    )

    assert calculate_answer_layer_score(row) == 75.0


def test_total_score_normalizes_unavailable_layers() -> None:
    assert calculate_layered_total_score(90.0, "unavailable", 50.0) == 75.7143


def test_write_governance_score_uses_raw_trace_metrics() -> None:
    metrics = {
        "candidate_count": 10,
        "policy_reject_count": 6,
        "policy_review_count": 2,
        "duplicate_risk_count": 1,
        "temporary_risk_count": 1,
        "assistant_inference_risk_count": 0,
        "write_reduction_rate": 0.4,
    }

    score, components = calculate_write_governance_score(metrics)
    assert score == 46.5
    assert components["useful_write_precision_score"] == 60.0
    assert components["pollution_block_score"] == 20.0
    assert components["review_safety_score"] == 20.0


def test_memory_hygiene_score_uses_raw_trace_metrics() -> None:
    metrics = {
        "scanned_count": 10,
        "missing_source_ref_count": 2,
        "stale_candidate_count": 3,
        "duplicate_group_count": 4,
        "merge_candidate_count": 2,
        "conflict_candidate_count": 1,
        "low_value_candidate_count": 2,
        "estimated_token_saving": 5,
    }

    score, components = calculate_memory_hygiene_score(metrics)
    assert score == 38.5
    assert components["source_ref_health_score"] == 80.0
    assert components["token_saving_score"] == 50.0


def test_layered_report_keeps_chain_order_and_three_layers() -> None:
    report = build_layered_scoring_report(build_quantitative_eval_cases(limit=8))
    overall = [row for row in report.layer_summaries if row.case_set == "overall"]

    assert tuple(row.profile_name for row in overall) == CHAIN_PROFILES
    assert report.metrics["measurement_mode"] == "offline_trace_layered_scoring"
    assert report.metrics["layer_count"] == 3
    assert report.metrics["case_count"] == 8
    assert overall[0].layered_total_score == 100.0
    assert isinstance(overall[0], LayeredProfileSummary)


def test_layered_report_exposes_component_breakdowns() -> None:
    report = build_layered_scoring_report(build_quantitative_eval_cases(limit=8))
    overall = {(row.case_set, row.profile_name): row for row in report.layer_summaries}

    write_row = overall[("overall", "chain_write_value")]
    sleep_row = overall[("overall", "chain_sleep_consolidation")]

    assert write_row.write_governance_score != "unavailable"
    assert write_row.write_components["write_reduction_score"] != "unavailable"
    assert write_row.layer_breakdowns[1].layer_name == "write_governance"
    assert sleep_row.memory_hygiene_score != "unavailable"
    assert sleep_row.hygiene_components["token_saving_score"] != "unavailable"
    assert sleep_row.layer_breakdowns[-1].layer_name == "memory_hygiene"


def test_missing_raw_trace_metrics_return_unavailable() -> None:
    report = build_layered_scoring_report(build_quantitative_eval_cases("common", limit=4))
    overall = {(row.case_set, row.profile_name): row for row in report.layer_summaries}

    base_row = overall[("overall", "chain_memory_base")]
    assert base_row.write_governance_score == "unavailable"
    assert base_row.memory_hygiene_score == "unavailable"
    assert base_row.unavailable_layers == ("write_governance", "memory_hygiene")
