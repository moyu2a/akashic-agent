from __future__ import annotations

import json
from pathlib import Path

from memory2.eval_quantitative_cases import build_quantitative_eval_cases
from memory2.eval_runner import run_eval_cases
from memory2.eval_target_metrics import (
    MetricDelta,
    TargetMetricRow,
    _delta,
    build_target_metric_report,
    write_target_metric_json,
    write_target_metric_markdown,
)


def _pct(ids: object, targets: object) -> float | str:
    if not isinstance(ids, (list, tuple)) or not isinstance(targets, (list, tuple)):
        return "unavailable"
    target_ids = [str(item) for item in targets if str(item)]
    if not target_ids:
        return "unavailable"
    found = {str(item) for item in ids if str(item)}
    return round(sum(1 for item in target_ids if item in found) / len(target_ids) * 100, 4)


def test_delta_reports_points_and_relative_uplift() -> None:
    delta_points, relative = _delta(40.0, 55.0)

    assert delta_points == 15.0
    assert relative == 37.5


def test_delta_handles_zero_or_unavailable_baseline() -> None:
    assert _delta(0.0, 35.0) == (35.0, "unavailable")
    assert _delta("unavailable", 35.0) == ("unavailable", "unavailable")


def test_target_metric_report_has_three_groups() -> None:
    report = build_target_metric_report(build_quantitative_eval_cases(limit=8))

    assert report.metrics["measurement_mode"] == "offline_trace_real_baseline_target_metrics"
    assert report.metrics["case_count"] == 8
    assert len(report.answer_retrieval_rows) > 0
    assert len(report.write_governance_rows) > 0
    assert len(report.memory_hygiene_rows) > 0


def test_answer_retrieval_before_matches_trace_baseline_ids() -> None:
    cases = build_quantitative_eval_cases(limit=8)
    run_report = run_eval_cases(cases)
    expected_values = []
    for case, case_result in zip(cases, run_report.cases, strict=True):
        trace = case_result.profiles["all"].traces["tri_retrieval"]
        expected_values.append(
            _pct(
                trace.baseline_result.get("baseline_ids"),
                case.expectations.get("should_recall_ids"),
            )
        )
    expected = round(
        sum(float(value) for value in expected_values if isinstance(value, (int, float)))
        / len(expected_values),
        4,
    )

    report = build_target_metric_report(cases)
    row = next(
        row
        for row in report.answer_retrieval_rows
        if row.case_set == "overall" and row.module_name == "三路召回"
    )

    assert row.metrics["target_recall_rate"].before == expected


def test_version_provenance_uses_active_version_targets_not_generic_recall_targets() -> None:
    report = build_target_metric_report(build_quantitative_eval_cases(limit=80))
    row = next(
        row
        for row in report.answer_retrieval_rows
        if row.case_set == "overall" and row.module_name == "版本链与溯源"
    )

    assert row.metrics["current_version_recall_rate"].after == 100.0
    assert row.metrics["target_recall_rate"].after == 100.0
    assert row.metrics["stale_version_misuse_rate"].after == 0.0


def test_hard_cases_make_tri_and_graph_retrieval_baseline_less_than_after() -> None:
    report = build_target_metric_report(build_quantitative_eval_cases())
    tri_row = next(
        row
        for row in report.answer_retrieval_rows
        if row.case_set == "hard" and row.module_name == "三路召回"
    )
    graph_row = next(
        row
        for row in report.answer_retrieval_rows
        if row.case_set == "hard" and row.module_name == "图谱召回"
    )
    common_tri_row = next(
        row
        for row in report.answer_retrieval_rows
        if row.case_set == "common" and row.module_name == "三路召回"
    )

    assert tri_row.metrics["target_recall_rate"].before < tri_row.metrics["target_recall_rate"].after
    assert graph_row.metrics["target_recall_rate"].before < graph_row.metrics["target_recall_rate"].after
    assert common_tri_row.metrics["target_recall_rate"].before == 100.0


def test_graph_retrieval_uses_graph_targets_not_tri_target_misses() -> None:
    report = build_target_metric_report(build_quantitative_eval_cases())
    hard_row = next(
        row
        for row in report.answer_retrieval_rows
        if row.case_set == "hard" and row.module_name == "图谱召回"
    )
    common_row = next(
        row
        for row in report.answer_retrieval_rows
        if row.case_set == "common" and row.module_name == "图谱召回"
    )

    assert hard_row.metrics["target_recall_rate"].before < hard_row.metrics["target_recall_rate"].after
    assert hard_row.metrics["target_recall_rate"].after == 100.0
    assert common_row.metrics["target_recall_rate"].after == 100.0


def test_version_conflict_chain_detection_becomes_measurable() -> None:
    report = build_target_metric_report(build_quantitative_eval_cases())
    hard_row = next(
        row
        for row in report.answer_retrieval_rows
        if row.case_set == "hard" and row.module_name == "版本链与溯源"
    )

    assert hard_row.metrics["current_version_recall_rate"].after == 100.0
    assert hard_row.metrics["conflict_chain_detection_rate"].after == 100.0


def test_rerank_injection_before_matches_baseline_injected_ids() -> None:
    cases = build_quantitative_eval_cases(limit=8)
    run_report = run_eval_cases(cases)
    expected_values = []
    for case, case_result in zip(cases, run_report.cases, strict=True):
        trace = case_result.profiles["all"].traces["injection_governance_shadow"]
        expected_values.append(
            _pct(
                trace.baseline_result.get("baseline_injected_ids"),
                case.expectations.get("should_not_recall_ids"),
            )
        )
    expected = round(
        sum(float(value) for value in expected_values if isinstance(value, (int, float)))
        / len(expected_values),
        4,
    )

    report = build_target_metric_report(cases)
    row = next(
        row
        for row in report.answer_retrieval_rows
        if row.case_set == "overall" and row.module_name == "重排与注入治理"
    )

    assert row.metrics["wrong_injection_rate"].before == expected


def test_online_answer_rows_are_paired_by_case_variant_and_repeat() -> None:
    report = build_target_metric_report(
        build_quantitative_eval_cases(limit=8),
        online_case_records=(
            {
                "case_id": "case_a",
                "profile_name": "chain_off",
                "prompt_variant": "baseline",
                "repeat_index": 0,
                "answer_rule_passed": False,
                "memory_grounding_passed": False,
                "forbidden_contains_violation_count": 1,
                "provider_error": False,
                "timeout": False,
            },
            {
                "case_id": "case_a",
                "profile_name": "chain_tri_retrieval",
                "prompt_variant": "baseline",
                "repeat_index": 0,
                "answer_rule_passed": True,
                "memory_grounding_passed": True,
                "forbidden_contains_violation_count": 0,
                "provider_error": False,
                "timeout": False,
            },
            {
                "case_id": "case_b",
                "profile_name": "chain_tri_retrieval",
                "prompt_variant": "baseline",
                "repeat_index": 0,
                "answer_rule_passed": True,
                "memory_grounding_passed": True,
                "forbidden_contains_violation_count": 0,
                "provider_error": False,
                "timeout": False,
            },
        ),
        online_checkpoint_source="real_llm",
    )

    row = next(
        row
        for row in report.answer_retrieval_rows
        if row.measurement_layer == "online_checkpoint" and row.module_name == "三路召回"
    )

    assert row.metrics["answer_hit_rate"].before == 0.0
    assert row.metrics["answer_hit_rate"].after == 100.0
    assert row.unit_count == 1
    assert row.measurement_source == "comprehensive_online_checkpoint"
    assert row.checkpoint_source == "real_llm"


def test_target_metric_report_exposes_module_specific_percentages() -> None:
    report = build_target_metric_report(build_quantitative_eval_cases(limit=8))

    answer_rows = {
        (row.case_set, row.module_name): row for row in report.answer_retrieval_rows
    }
    write_rows = {
        (row.case_set, row.module_name): row for row in report.write_governance_rows
    }
    hygiene_rows = {
        (row.case_set, row.module_name): row for row in report.memory_hygiene_rows
    }

    assert (
        answer_rows[("overall", "三路召回")]
        .metrics["target_recall_rate"]
        .after
        != "unavailable"
    )
    assert (
        answer_rows[("overall", "重排与注入治理")]
        .metrics["wrong_injection_rate"]
        .after
        != "unavailable"
    )
    assert (
        write_rows[("overall", "写入价值治理")]
        .metrics["pollution_block_rate"]
        .after
        != "unavailable"
    )
    assert (
        hygiene_rows[("overall", "睡眠巩固")]
        .metrics["token_saving_rate"]
        .after
        != "unavailable"
    )


def test_target_metric_report_can_filter_common_subset() -> None:
    report = build_target_metric_report(build_quantitative_eval_cases("common", limit=8))

    assert report.metrics["common_case_count"] == 8
    assert report.metrics["hard_case_count"] == 0
    assert all(row.case_set != "hard" for row in report.answer_retrieval_rows)


def test_target_metric_writers_emit_json_and_three_markdown_tables(tmp_path: Path) -> None:
    report = build_target_metric_report(build_quantitative_eval_cases())
    json_path = tmp_path / "memory_target_metrics_eval.json"
    md_path = tmp_path / "memory_target_metrics_eval.md"

    write_target_metric_json(report, json_path)
    write_target_metric_markdown(report, md_path)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = md_path.read_text(encoding="utf-8")

    assert payload["metrics"]["measurement_mode"] == "offline_trace_real_baseline_target_metrics"
    assert payload["metrics"]["online_row_count"] == 0
    assert "answer_retrieval_rows" in payload
    assert "write_governance_rows" in payload
    assert "memory_hygiene_rows" in payload
    assert all("measurement_layer" in row for row in payload["answer_retrieval_rows"])
    assert "# 记忆系统目标指标百分比评测报告" in markdown
    assert "离线真实 before/after" in markdown
    assert "线上真实 LLM / checkpoint before/after" in markdown
    assert "## 召回与回答增益表" in markdown
    assert "## 写入治理增益表" in markdown
    assert "## 记忆库卫生增益表" in markdown
    assert "measurement_layer" in markdown
    assert "measurement_source" in markdown
    assert "提升百分点" in markdown
    assert "相对提升" in markdown
    version_rows = [
        row
        for row in payload["answer_retrieval_rows"]
        if row["module_name"] == "版本链与溯源"
    ]
    hard_version_row = next(row for row in version_rows if row["case_set"] == "hard")
    assert "current_version_recall_rate" in hard_version_row["metrics"]
    assert "conflict_chain_detection_rate" in hard_version_row["metrics"]
    assert "current_version_recall_rate" in markdown
    assert "conflict_chain_detection_rate" in markdown
    assert hard_version_row["metrics"]["conflict_chain_detection_rate"]["after"] == 100.0


def test_target_metric_row_uses_metric_delta_shape() -> None:
    row = TargetMetricRow(
        group_name="召回与回答",
        module_name="三路召回",
        profile_name="chain_tri_retrieval",
        case_set="overall",
        case_count=1,
        metrics={
            "target_recall_rate": MetricDelta(
                name="target_recall_rate",
                before=0.0,
                after=100.0,
                delta_points=100.0,
                relative_uplift_pct="unavailable",
            )
        },
    )

    assert row.metrics["target_recall_rate"].after == 100.0
