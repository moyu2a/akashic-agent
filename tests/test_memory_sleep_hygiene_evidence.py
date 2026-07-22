from __future__ import annotations

from memory2.eval_sleep_hygiene_cases import build_sleep_hygiene_cases
from memory2.eval_sleep_hygiene_evidence import (
    build_sleep_hygiene_evidence_records,
    run_sleep_hygiene_evidence_eval,
    strip_sleep_hygiene_evidence_for_target_metrics,
)


def test_sleep_hygiene_evidence_records_use_target_metric_schema() -> None:
    cases = build_sleep_hygiene_cases(
        duplicate_groups=2,
        stale_count=2,
        low_value_count=2,
        retained_count=2,
        missing_source_count=1,
    )

    records = build_sleep_hygiene_evidence_records(cases)

    assert len(records) == 8
    assert all(record["baseline_state"] == "active" for record in records)
    assert {record["label"] for record in records} == {
        "duplicate",
        "stale",
        "low_value",
        "retained",
    }
    assert any(record["after_state"] == "merged" for record in records)
    assert any(record["after_state"] == "stale" for record in records)
    assert any(record["after_state"] == "low_value_removed" for record in records)
    assert any(
        record["label"] == "retained" and record["after_state"] == "active"
        for record in records
    )
    assert sum(1 for record in records if not record["source_ref_available"]) == 1
    assert all(record["infra_error"] is False for record in records)


def test_sleep_hygiene_report_exposes_counts_percentages_and_safety() -> None:
    report = run_sleep_hygiene_evidence_eval(
        duplicate_groups=3,
        stale_count=4,
        low_value_count=5,
        retained_count=6,
        missing_source_count=2,
    )

    assert report.metrics["case_count"] == 18
    assert report.metrics["scanned_active_item_count"] == 21
    assert report.metrics["evaluated_evidence_row_count"] == 18
    assert report.metrics["duplicate_item_count"] == 3
    assert report.metrics["stale_item_count"] == 4
    assert report.metrics["low_value_item_count"] == 5
    assert report.metrics["retained_item_count"] == 6
    assert report.metrics["duplicate_merge_rate"] == 100.0
    assert report.metrics["stale_cleanup_rate"] == 100.0
    assert report.metrics["low_value_cleanup_rate"] == 100.0
    assert report.metrics["post_consolidation_recall_retention_rate"] == 100.0
    assert report.metrics["retained_candidate_leak_count"] == 0
    assert report.metrics["unexpected_candidate_count"] == 0
    assert report.metrics["false_positive_cleanup_rate"] == 0.0
    assert report.metrics["source_ref_coverage_rate"] < 100.0
    assert report.metrics["source_fetch_success_rate"] == 100.0
    assert report.metrics["shadow_estimated_token_saving_rate"] > 0
    assert report.shadow_metrics["applied_change_count"] == 0


def test_retained_rows_are_not_hard_coded_safe_when_shadow_marks_candidate() -> None:
    cases = build_sleep_hygiene_cases(
        duplicate_groups=0,
        stale_count=0,
        low_value_count=0,
        retained_count=2,
        missing_source_count=0,
    )
    first, second = cases
    unsafe_cases = (
        first,
        type(second)(
            case_id=second.case_id,
            label=second.label,
            memory_items=(
                {
                    **second.memory_items[0],
                    "summary": first.memory_items[0]["summary"],
                    "scope_chat_id": first.memory_items[0]["scope_chat_id"],
                },
            ),
            expected_item_ids=second.expected_item_ids,
        ),
    )

    report = run_sleep_hygiene_evidence_eval(cases=unsafe_cases)

    assert report.metrics["retained_candidate_leak_count"] > 0
    assert report.metrics["false_positive_cleanup_rate"] > 0
    assert report.metrics["post_consolidation_recall_retention_rate"] < 100.0


def test_sleep_hygiene_report_normalizes_runtime_latency_for_stable_reports() -> None:
    first = run_sleep_hygiene_evidence_eval(
        duplicate_groups=2,
        stale_count=2,
        low_value_count=2,
        retained_count=2,
    )
    second = run_sleep_hygiene_evidence_eval(
        duplicate_groups=2,
        stale_count=2,
        low_value_count=2,
        retained_count=2,
    )

    assert first.shadow_metrics["job_latency_ms"] == 0.0
    assert first.shadow_metrics == second.shadow_metrics


def test_sleep_hygiene_evidence_emits_rows_for_all_expected_item_states() -> None:
    cases = build_sleep_hygiene_cases(
        case_set="hard",
        hard_per_scenario=1,
        missing_source_count=1,
    )

    records = build_sleep_hygiene_evidence_records(cases)

    expected_rows = sum(len(case.expected_item_states) for case in cases)
    assert len(records) == expected_rows
    assert all(record["case_id"] for record in records)
    assert all(record["case_set"] == "hard" for record in records)
    assert all(record["scenario"] for record in records)
    assert all(record["expected_after_state"] for record in records)


def test_sleep_hygiene_all_report_splits_case_and_item_counts() -> None:
    cases = build_sleep_hygiene_cases(
        case_set="all",
        duplicate_groups=3,
        stale_count=4,
        low_value_count=5,
        retained_count=6,
        hard_per_scenario=3,
        missing_source_count=2,
    )

    report = run_sleep_hygiene_evidence_eval(cases=cases)
    grouped = report.metrics["group_metrics"]

    assert set(grouped) == {"standard", "hard", "overall"}
    assert grouped["standard"]["case_count"] == 18
    assert grouped["hard"]["case_count"] == 24
    assert grouped["overall"]["case_count"] == 42
    assert grouped["standard"]["evaluated_item_count"] == 18
    assert grouped["hard"]["evaluated_item_count"] > grouped["hard"]["case_count"]
    assert grouped["overall"]["evaluated_item_count"] == (
        grouped["standard"]["evaluated_item_count"]
        + grouped["hard"]["evaluated_item_count"]
    )
    assert "candidate_precision" in grouped["hard"]
    assert "candidate_recall" in grouped["hard"]
    assert "retained_protection_rate" in grouped["hard"]
    assert "safe_evidence_estimated_token_saving_rate" in grouped["hard"]


def test_sleep_hygiene_target_metric_records_are_stripped_to_schema_fields() -> None:
    report = run_sleep_hygiene_evidence_eval(
        cases=build_sleep_hygiene_cases(case_set="hard", hard_per_scenario=1)
    )

    stripped = strip_sleep_hygiene_evidence_for_target_metrics(report.records)

    assert stripped
    assert "case_id" not in stripped[0]
    assert "expected_after_state" not in stripped[0]
    assert set(stripped[0]) == {
        "item_id",
        "baseline_state",
        "after_state",
        "label",
        "source_ref_available",
        "source_fetch_success",
        "baseline_token_estimate",
        "after_token_estimate",
        "infra_error",
    }
