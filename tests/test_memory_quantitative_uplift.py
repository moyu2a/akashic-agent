from __future__ import annotations

import json
from dataclasses import asdict
from types import SimpleNamespace

import pytest
from memory2.eval_cases import validate_eval_case_payload
from memory2.eval_quantitative_cases import build_quantitative_eval_cases
from memory2.eval_quantitative_uplift import (
    _score_provenance_family,
    build_quantitative_uplift_report,
    calculate_main_score,
)


def case_to_payload(case) -> dict[str, object]:
    return json.loads(json.dumps(asdict(case), ensure_ascii=False))


def test_quantitative_case_pack_has_common_and_hard_sets() -> None:
    cases = build_quantitative_eval_cases()

    assert len(cases) == 80
    assert sum(1 for case in cases if str(case.category).startswith("common_")) == 40
    assert sum(1 for case in cases if str(case.category).startswith("hard_")) == 40


def test_quantitative_case_pack_can_filter_sets_and_limit() -> None:
    assert len(build_quantitative_eval_cases("common")) == 40
    assert len(build_quantitative_eval_cases("hard", limit=3)) == 3


def test_quantitative_cases_are_valid_eval_cases() -> None:
    for case in build_quantitative_eval_cases():
        assert validate_eval_case_payload(case_to_payload(case)) == []


def test_main_score_uses_committed_formula() -> None:
    assert calculate_main_score(
        answer_rule_pass_rate=80.0,
        memory_grounding_pass_rate=50.0,
        forbidden_violation_rate=10.0,
    ) == 75.0


def test_report_contains_single_feature_and_total_uplift() -> None:
    report = build_quantitative_uplift_report(build_quantitative_eval_cases(limit=16))
    overall = {(row.case_set, row.profile_name): row for row in report.profile_summaries}

    assert overall[("overall", "off")].uplift_points == 0.0
    assert overall[("overall", "write_value_only")].uplift_points > 0
    assert overall[("overall", "tri_retrieval_only")].uplift_points >= overall[
        ("overall", "write_value_only")
    ].uplift_points
    assert overall[("overall", "all_on")].uplift_points > 0
    assert overall[("overall", "all_on")].main_score > overall[("overall", "off")].main_score
    assert report.metrics["overall_main_score"] == overall[("overall", "all_on")].main_score
    assert report.metrics["case_count"] == 16


def test_missing_case_set_metrics_are_unavailable() -> None:
    report = build_quantitative_uplift_report(
        build_quantitative_eval_cases("common", limit=8)
    )

    assert report.metrics["common_case_count"] == 8
    assert report.metrics["hard_case_count"] == 0
    assert report.metrics["common_main_score"] != "unavailable"
    assert report.metrics["hard_main_score"] == "unavailable"
    assert report.metrics["hard_baseline_main_score"] == "unavailable"


def test_full_report_has_expected_totals() -> None:
    report = build_quantitative_uplift_report(build_quantitative_eval_cases())
    overall = {(row.case_set, row.profile_name): row for row in report.profile_summaries}

    assert round(overall[("overall", "all_on")].main_score, 4) == 69.6017
    assert round(overall[("overall", "all_on")].uplift_points, 4) == 59.6017
    assert overall[("overall", "all_on")].token_signal_kind == "mixed"
    assert overall[("overall", "all_on")].token_signal_value == "unavailable"
    assert overall[("overall", "all_on")].token_signal_delta == "unavailable"
    assert overall[("overall", "tri_retrieval_only")].latency_delta_ms == "unavailable"
    assert report.metrics["total_uplift_points"] == 59.6017
    assert report.metrics["total_uplift_pct"] == 596.017


def test_token_signal_kind_is_explicit() -> None:
    report = build_quantitative_uplift_report(build_quantitative_eval_cases())
    overall = {(row.case_set, row.profile_name): row for row in report.profile_summaries}

    assert overall[("overall", "sleep_only")].token_signal_kind == "estimated_token_saving"
    assert overall[("overall", "sleep_only")].token_signal_value > 0
    assert overall[("overall", "sleep_only")].token_signal_delta == "unavailable"
    assert overall[("overall", "rerank_only")].token_signal_kind == "prompt_token_delta"
    assert overall[("overall", "rerank_only")].token_signal_value > 0
    assert overall[("overall", "rerank_only")].token_signal_delta == "unavailable"
    assert overall[("overall", "all_on")].token_signal_kind == "mixed"


def test_report_generated_at_is_deterministic() -> None:
    report_a = build_quantitative_uplift_report(build_quantitative_eval_cases(limit=8))
    report_b = build_quantitative_uplift_report(build_quantitative_eval_cases(limit=8))

    assert report_a.generated_at == report_b.generated_at == "2026-07-17T00:00:00+00:00"


def test_report_builder_raises_when_runner_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailedCase:
        case_id = "broken_case"
        failures = ("missing required trace feature",)
        passed = False

    class FailedReport:
        passed = False
        cases = (FailedCase(),)
        metrics = {"case_count": 1}

    monkeypatch.setattr(
        "memory2.eval_quantitative_uplift.run_eval_cases",
        lambda cases: FailedReport(),
    )

    with pytest.raises(RuntimeError, match="broken_case"):
        build_quantitative_uplift_report(build_quantitative_eval_cases(limit=1))


def test_provenance_forbidden_rate_depends_on_actual_risk_not_fixture_presence() -> None:
    no_risk_trace = SimpleNamespace(
        metrics={
            "source_ref_coverage": 1.0,
            "parse_success_rate": 1.0,
            "cross_scope_memory_count": 3,
            "cross_scope_risk_count": 0,
        },
    )
    partial_risk_trace = SimpleNamespace(
        metrics={
            "source_ref_coverage": 1.0,
            "parse_success_rate": 1.0,
            "cross_scope_memory_count": 3,
            "cross_scope_risk_count": 1,
        },
    )

    no_risk_score = _score_provenance_family(no_risk_trace)
    partial_risk_score = _score_provenance_family(partial_risk_trace)

    assert no_risk_score["forbidden_violation_rate"] == 0.0
    assert partial_risk_score["forbidden_violation_rate"] == 33.33
