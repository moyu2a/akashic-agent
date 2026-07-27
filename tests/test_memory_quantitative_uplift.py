from __future__ import annotations

from collections import Counter
import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest
from memory2.eval_cases import validate_eval_case_payload
from memory2.eval_quantitative_cases import (
    EVAL_CASE_PACKS,
    build_quantitative_eval_cases,
)
from memory2.eval_quantitative_uplift import (
    CHAIN_REPORT_PROFILES,
    CHAIN_PROFILES,
    build_quantitative_balanced_report,
    build_quantitative_chain_report,
    _score_provenance_family,
    build_quantitative_uplift_report,
    calculate_balanced_scores,
    calculate_main_score,
    write_quantitative_chain_markdown,
    write_quantitative_uplift_markdown,
)


def case_to_payload(case) -> dict[str, object]:
    return json.loads(json.dumps(asdict(case), ensure_ascii=False))


def test_quantitative_case_pack_has_common_and_hard_sets() -> None:
    cases = build_quantitative_eval_cases()

    assert len(cases) == 80
    assert sum(1 for case in cases if str(case.category).startswith("common_")) == 40
    assert sum(1 for case in cases if str(case.category).startswith("hard_")) == 40


def test_comprehensive_quantitative_case_pack_is_larger_and_balanced() -> None:
    cases = build_quantitative_eval_cases(case_pack="comprehensive")

    assert EVAL_CASE_PACKS == ("standard", "comprehensive", "answer_comprehensive_v2")
    assert len(cases) == 320
    assert sum(1 for case in cases if str(case.category).startswith("common_")) == 160
    assert sum(1 for case in cases if str(case.category).startswith("hard_")) == 160
    categories = {
        case.category.removeprefix("common_").removeprefix("hard_")
        for case in cases
    }
    assert len(categories) == 20
    assert any(case.id.startswith("hard_entity_alias") for case in cases)
    assert any(case.id.startswith("common_entropy_value") for case in cases)


def test_answer_comprehensive_v2_case_pack_is_answer_retrieval_only() -> None:
    cases = build_quantitative_eval_cases(case_pack="answer_comprehensive_v2")

    assert len(cases) == 1000
    assert sum(1 for case in cases if str(case.category).startswith("common_")) == 500
    assert sum(1 for case in cases if str(case.category).startswith("hard_")) == 500
    assert sum(
        len(case.expectations.get("should_recall_ids", [])) for case in cases
    ) == 2000
    forbidden_measurement_families = {"write_governance", "sleep_consolidation"}
    assert not {
        str(case.setup.get("measurement_family") or "") for case in cases
    } & forbidden_measurement_families

    scenario_names = {str(case.setup.get("scenario_name") or "") for case in cases}
    assert len(scenario_names) == 25
    assert {
        "implicit_rrf_alias",
        "networkx_entity_bridge",
        "current_version_preference",
        "source_grounded_answer",
        "rerank_noise_suppression",
        "semantic_phrase_variation",
        "source_ref_entity_bridge",
        "ambiguous_entity_disambiguation",
        "rerank_scope_priority",
        "version_rollback_candidate",
        "provenance_cross_scope_guard",
    } <= scenario_names
    assert {
        str(case.setup.get("measurement_family") or "") for case in cases
    } <= {
        "tri_retrieval",
        "graph_retrieval",
        "rerank_injection",
        "version_provenance",
        "provenance",
    }
    by_set_and_scenario = Counter(
        (
            "common" if str(case.category).startswith("common_") else "hard",
            str(case.setup.get("scenario_name") or ""),
        )
        for case in cases
    )
    assert set(by_set_and_scenario.values()) == {20}


def test_quantitative_case_pack_can_filter_sets_and_limit() -> None:
    assert len(build_quantitative_eval_cases("common")) == 40
    assert len(build_quantitative_eval_cases("hard", limit=3)) == 3
    assert len(build_quantitative_eval_cases("common", case_pack="comprehensive")) == 160
    assert len(build_quantitative_eval_cases("hard", limit=3, case_pack="comprehensive")) == 3
    assert (
        len(build_quantitative_eval_cases("common", case_pack="answer_comprehensive_v2"))
        == 500
    )


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

    assert overall[("overall", "memory_base")].uplift_points == 0.0
    assert overall[("overall", "off")].uplift_points < 0
    assert overall[("overall", "write_value_only")].uplift_points <= 0
    assert overall[("overall", "tri_retrieval_only")].uplift_points >= overall[
        ("overall", "write_value_only")
    ].uplift_points
    assert overall[("overall", "all_on")].main_score < overall[
        ("overall", "memory_base")
    ].main_score
    assert report.metrics["overall_main_score"] == overall[("overall", "all_on")].main_score
    assert report.metrics["case_count"] == 16


def test_memory_base_scores_original_recalled_items_as_baseline() -> None:
    report = build_quantitative_uplift_report(build_quantitative_eval_cases(limit=8))
    overall = {(row.case_set, row.profile_name): row for row in report.profile_summaries}
    baseline = overall[("overall", "memory_base")]
    control = overall[("overall", "off")]

    assert baseline.target_count == 16
    assert baseline.success_count + baseline.miss_count == baseline.target_count
    assert baseline.recall_rate == round(
        baseline.success_count / baseline.target_count * 100.0,
        4,
    )
    assert baseline.baseline_score == baseline.main_score
    assert baseline.uplift_points == 0.0
    assert report.metrics["baseline_profile"] == "memory_base"
    assert report.metrics["control_profile"] == "off"
    assert report.metrics["baseline_main_score"] == baseline.main_score
    assert control.baseline_score == baseline.main_score


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

    assert round(overall[("overall", "memory_base")].main_score, 4) == 94.375
    assert round(overall[("overall", "all_on")].main_score, 4) == 68.8579
    assert round(overall[("overall", "all_on")].uplift_points, 4) == -25.5171
    assert overall[("overall", "all_on")].token_signal_kind == "mixed"
    assert overall[("overall", "all_on")].token_signal_value == "unavailable"
    assert overall[("overall", "all_on")].token_signal_delta == "unavailable"
    assert overall[("overall", "tri_retrieval_only")].latency_delta_ms == "unavailable"
    assert report.metrics["total_uplift_points"] == -25.5171
    assert report.metrics["total_uplift_pct"] == -27.038


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


def test_chain_report_contains_ordered_cumulative_steps() -> None:
    report = build_quantitative_chain_report(build_quantitative_eval_cases(limit=8))
    overall = [row for row in report.profile_summaries if row.case_set == "overall"]

    assert tuple(row.profile_name for row in overall) == CHAIN_REPORT_PROFILES
    assert overall[0].profile_name == "chain_memory_base"
    assert overall[-2].profile_name == "chain_all_on"
    assert overall[-1].profile_name == "chain_off"
    assert report.metrics["measurement_mode"] == "offline_trace_quantitative_chain"
    assert report.metrics["chain_step_count"] == len(CHAIN_PROFILES)


def test_chain_report_uses_original_memory_base_not_disabled_control() -> None:
    report = build_quantitative_chain_report(build_quantitative_eval_cases(limit=8))
    overall = {(row.case_set, row.profile_name): row for row in report.profile_summaries}
    baseline = overall[("overall", "chain_memory_base")]
    control = overall[("overall", "chain_off")]
    final = overall[("overall", "chain_all_on")]

    assert baseline.target_count == 16
    assert baseline.success_count + baseline.miss_count == baseline.target_count
    assert report.metrics["baseline_profile"] == "chain_memory_base"
    assert report.metrics["control_profile"] == "chain_off"
    assert report.metrics["baseline_main_score"] == baseline.main_score
    assert control.baseline_score == baseline.main_score
    assert report.metrics["total_chain_uplift_points"] == round(
        final.main_score - baseline.main_score,
        4,
    )


def test_primary_offline_markdown_tables_use_counts_and_rates(tmp_path: Path) -> None:
    cases = build_quantitative_eval_cases(limit=8)
    uplift_path = tmp_path / "uplift.md"
    chain_path = tmp_path / "chain.md"

    write_quantitative_uplift_markdown(
        build_quantitative_uplift_report(cases),
        uplift_path,
    )
    write_quantitative_chain_markdown(
        build_quantitative_chain_report(cases),
        chain_path,
    )

    uplift_markdown = uplift_path.read_text(encoding="utf-8")
    chain_markdown = chain_path.read_text(encoding="utf-8")
    assert "| profile | case_set | targets | success | miss | recall_rate |" in uplift_markdown
    assert "| profile | case_set | main_score |" not in uplift_markdown
    assert "## 三路召回路由表" in uplift_markdown
    assert "| scene | cases | baseline_success | gated_success | graph_success |" in uplift_markdown
    assert "| step | label | targets | success | miss | recall_rate |" in chain_markdown
    assert "| step | label | main_score |" not in chain_markdown


def test_chain_report_step_delta_uses_previous_step() -> None:
    report = build_quantitative_chain_report(build_quantitative_eval_cases(limit=8))
    overall = [row for row in report.profile_summaries if row.case_set == "overall"]

    for previous, current in zip(overall, overall[1:]):
        expected_delta = round(current.main_score - previous.main_score, 4)
        assert current.uplift_points == expected_delta
        if (
            isinstance(previous.latency_ms, (int, float))
            and isinstance(current.latency_ms, (int, float))
        ):
            assert current.latency_delta_ms == round(
                current.latency_ms - previous.latency_ms,
                4,
            )
        if (
            previous.token_signal_kind == current.token_signal_kind
            and previous.token_signal_kind not in {"mixed", "unavailable"}
            and isinstance(previous.token_signal_value, (int, float))
            and isinstance(current.token_signal_value, (int, float))
        ):
            assert current.token_signal_delta == round(
                current.token_signal_value - previous.token_signal_value,
                4,
            )
    assert report.metrics["total_chain_uplift_points"] == round(
        overall[-2].main_score - overall[0].main_score,
        4,
    )


def test_balanced_scores_split_answer_retrieval_governance_efficiency() -> None:
    report = build_quantitative_chain_report(build_quantitative_eval_cases(limit=8))
    row = next(
        item
        for item in report.profile_summaries
        if item.case_set == "overall" and item.profile_name == "chain_tri_retrieval"
    )

    scores = calculate_balanced_scores(row)

    assert set(scores) == {
        "answer_score",
        "retrieval_proxy_score",
        "grounding_score",
        "governance_score",
        "efficiency_score",
        "balanced_score",
        "balanced_score_available_dimensions",
        "unavailable_dimensions",
    }
    assert scores["answer_score"] == row.answer_rule_pass_rate
    assert scores["grounding_score"] == row.memory_grounding_pass_rate
    assert scores["governance_score"] == round(
        0.55 * (100.0 - row.forbidden_violation_rate)
        + 0.45 * row.memory_grounding_pass_rate,
        4,
    )
    assert scores["retrieval_proxy_score"] != "unavailable"
    assert "efficiency_score" in scores["unavailable_dimensions"]
    expected_without_efficiency = round(
        (
            0.30 * row.answer_rule_pass_rate
            + 0.25 * float(scores["retrieval_proxy_score"])
            + 0.20 * row.memory_grounding_pass_rate
            + 0.15 * float(scores["governance_score"])
        )
        / 0.90,
        4,
    )
    assert scores["balanced_score"] == expected_without_efficiency


def test_balanced_report_keeps_chain_order_and_step_delta() -> None:
    report = build_quantitative_balanced_report(build_quantitative_eval_cases(limit=8))
    overall = [row for row in report.balanced_summaries if row.case_set == "overall"]

    assert tuple(row.profile_name for row in overall) == CHAIN_PROFILES
    assert overall[0].balanced_delta_points == 0.0
    for previous, current in zip(overall, overall[1:]):
        assert current.balanced_delta_points == round(
            current.balanced_score - previous.balanced_score,
            4,
        )
    assert report.metrics["measurement_mode"] == "offline_trace_quantitative_balanced"
    assert report.metrics["balanced_step_count"] == len(CHAIN_PROFILES)


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
