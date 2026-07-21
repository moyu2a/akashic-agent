from __future__ import annotations

from collections import Counter

from memory2.eval_write_governance_cases import build_write_governance_candidates
from memory2.eval_write_governance_counts import build_write_governance_count_report


def test_write_governance_candidate_pack_has_1200_balanced_candidates() -> None:
    candidates = build_write_governance_candidates()

    assert len(candidates) == 1200
    assert sum(1 for item in candidates if item.case_set == "common") == 600
    assert sum(1 for item in candidates if item.case_set == "hard") == 600
    assert Counter(item.category for item in candidates) == {
        "valuable_preference": 200,
        "stable_fact": 200,
        "temporary": 200,
        "assistant_inference": 200,
        "duplicate": 200,
        "conflict": 200,
    }
    assert all(item.expected_action in {"write", "block", "review"} for item in candidates)
    assert all(item.summary for item in candidates)


def test_write_governance_candidate_pack_has_real_subtype_coverage() -> None:
    candidates = build_write_governance_candidates()
    subtype_counts = Counter((item.case_set, item.category, item.subtype) for item in candidates)

    assert len(subtype_counts) == 60
    assert set(subtype_counts.values()) == {20}
    assert all(item.subtype for item in candidates)


def test_write_governance_common_and_hard_sets_do_not_reuse_summaries() -> None:
    common = {item.summary for item in build_write_governance_candidates("common")}
    hard = {item.summary for item in build_write_governance_candidates("hard")}

    assert len(common) == 600
    assert len(hard) == 600
    assert not (common & hard)


def test_write_governance_candidates_are_not_index_only_templates() -> None:
    candidates = build_write_governance_candidates()
    stems = {
        item.summary.rsplit("，样本", 1)[0].rsplit("，编号", 1)[0]
        for item in candidates
    }

    assert len(stems) >= 180
    assert any("先不用长期保存" in item.summary for item in candidates if item.category == "temporary")
    assert any("从回答中猜到" in item.summary for item in candidates if item.category == "assistant_inference")
    assert any("优先级" in item.summary for item in candidates if item.category == "conflict")


def test_write_governance_report_uses_original_write_baseline() -> None:
    report = build_write_governance_count_report(build_write_governance_candidates())

    assert report.metrics["measurement_mode"] == "offline_write_governance_count_eval"
    assert report.metrics["candidate_count"] == 1200
    assert report.metrics["baseline_written_count"] == 1200
    assert report.metrics["baseline_profile"] == "original_write_behavior"
    assert report.metrics["enhanced_profile"] == "write_value_governance"
    assert report.metrics["offline_only"] is True
    assert report.metrics["llm_calls_enabled"] is False
    assert report.metrics["db_access_enabled"] is False
    assert report.metrics["production_state_access_enabled"] is False
    assert report.main_rows


def test_write_governance_report_outputs_count_and_percentage_metrics() -> None:
    report = build_write_governance_count_report(build_write_governance_candidates())
    rows = {row["category"]: row for row in report.main_rows}

    assert set(rows) == {
        "valuable_preference",
        "stable_fact",
        "temporary",
        "assistant_inference",
        "duplicate",
        "conflict",
    }
    assert rows["valuable_preference"]["expected_action"] == "write"
    assert rows["temporary"]["expected_action"] == "block"
    assert rows["duplicate"]["expected_action"] == "block"
    assert rows["conflict"]["expected_action"] == "review"
    assert rows["temporary"]["baseline_written_count"] == 200
    assert rows["temporary"]["pollution_reduction_count"] >= 0
    for key in (
        "write_reduction_rate",
        "useful_retention_rate",
        "pollution_control_rate",
        "false_reject_rate",
        "false_accept_rate",
        "review_miss_rate",
    ):
        assert isinstance(report.metrics[key], float)


def test_write_governance_report_has_difficulty_and_subtype_breakdowns() -> None:
    report = build_write_governance_count_report(build_write_governance_candidates())

    assert len(report.case_set_rows) == 12
    assert len(report.subtype_rows) == 60
    assert {row["case_set"] for row in report.case_set_rows} == {"common", "hard"}
    assert all("subtype" in row for row in report.subtype_rows)


def test_write_governance_report_counts_partial_review_misses() -> None:
    report = build_write_governance_count_report(build_write_governance_candidates())
    conflict = next(row for row in report.main_rows if row["category"] == "conflict")

    assert conflict["review_miss_count"] == conflict["candidate_count"] - conflict["enhanced_review_count"]
    assert any(row["category"] == "conflict" for row in report.review_miss_rows)


def test_write_governance_report_rates_are_recomputed_from_counts() -> None:
    report = build_write_governance_count_report(build_write_governance_candidates())
    metrics = report.metrics
    useful_total = sum(row["candidate_count"] for row in report.main_rows if row["expected_action"] == "write")
    pollution_total = sum(row["candidate_count"] for row in report.main_rows if row["expected_action"] != "write")
    review_total = sum(row["candidate_count"] for row in report.main_rows if row["expected_action"] == "review")

    assert metrics["useful_retention_rate"] == round(
        metrics["useful_written_count"] / useful_total * 100,
        4,
    )
    assert metrics["pollution_control_rate"] == round(
        metrics["pollution_controlled_count"] / pollution_total * 100,
        4,
    )
    assert metrics["false_reject_rate"] == round(
        metrics["false_reject_count"] / useful_total * 100,
        4,
    )
    assert metrics["false_accept_rate"] == round(
        metrics["false_accept_count"] / pollution_total * 100,
        4,
    )
    assert metrics["review_miss_rate"] == round(
        metrics["review_miss_count"] / review_total * 100,
        4,
    )


def test_write_governance_report_is_offline_only(monkeypatch) -> None:
    def fail_connect(*args: object, **kwargs: object) -> object:
        raise AssertionError("offline write-governance eval must not open sqlite databases")

    monkeypatch.setattr("sqlite3.connect", fail_connect)
    report = build_write_governance_count_report(build_write_governance_candidates(limit=24))

    assert report.metrics["offline_only"] is True
    assert report.metrics["candidate_count"] == 24
