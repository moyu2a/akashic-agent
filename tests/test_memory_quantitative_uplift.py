from __future__ import annotations

import json
from dataclasses import asdict

from memory2.eval_cases import validate_eval_case_payload
from memory2.eval_quantitative_cases import build_quantitative_eval_cases
from memory2.eval_quantitative_uplift import (
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


def test_full_report_has_expected_totals() -> None:
    report = build_quantitative_uplift_report(build_quantitative_eval_cases())
    overall = {(row.case_set, row.profile_name): row for row in report.profile_summaries}

    assert round(overall[("overall", "all_on")].main_score, 4) == 68.9767
    assert round(overall[("overall", "all_on")].uplift_points, 4) == 58.9767
    assert overall[("overall", "all_on")].token_cost_delta == 240.0
    assert overall[("overall", "tri_retrieval_only")].latency_delta_ms == 0.0
    assert report.metrics["total_uplift_points"] == 58.9767
    assert report.metrics["total_uplift_pct"] == 589.767
