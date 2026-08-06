from __future__ import annotations

from eval.agent_harness.differential import compare_case_reports
from eval.agent_harness.protocol import EpisodeResult


def test_differential_report_accepts_status_preserving_conversion() -> None:
    report = compare_case_reports(
        [{"case_id": "case-1", "status": "pass", "score": 1.0}],
        [
            EpisodeResult(
                episode_id="case-1-r0",
                status="PASS",
                outcome_passed=True,
                metrics={"case_id": "case-1", "raw_status": "pass"},
            )
        ],
    )

    assert report.passed is True
    assert report.missing_case_ids == ()
    assert report.status_mismatches == ()


def test_differential_report_detects_missing_and_changed_cases() -> None:
    report = compare_case_reports(
        [
            {"case_id": "case-1", "status": "pass"},
            {"case_id": "case-2", "status": "fail"},
        ],
        [
            EpisodeResult(
                episode_id="case-1-r0",
                status="FAIL",
                outcome_passed=False,
                metrics={"case_id": "case-1", "raw_status": "pass"},
            ),
            EpisodeResult(
                episode_id="case-3-r0",
                status="PASS",
                outcome_passed=True,
                metrics={"case_id": "case-3", "raw_status": "pass"},
            ),
        ],
    )

    assert report.passed is False
    assert report.missing_case_ids == ("case-2",)
    assert report.unexpected_case_ids == ("case-3",)
    assert report.status_mismatches == (("case-1", "pass", "FAIL"),)
