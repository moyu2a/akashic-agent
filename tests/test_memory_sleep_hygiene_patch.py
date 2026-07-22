from __future__ import annotations

from memory2.eval_sleep_hygiene_cases import build_sleep_hygiene_cases
from memory2.eval_sleep_hygiene_evidence import run_sleep_hygiene_evidence_eval
from memory2.eval_sleep_hygiene_patch import build_sleep_hygiene_dry_run_patch


def test_sleep_hygiene_dry_run_patch_splits_cleanup_and_review() -> None:
    report = run_sleep_hygiene_evidence_eval(
        cases=build_sleep_hygiene_cases(
            case_set="hard",
            hard_per_scenario=2,
            missing_source_count=1,
        )
    )

    patch = build_sleep_hygiene_dry_run_patch(report.records)

    assert patch.applied_change_count == 0
    assert patch.would_remove_low_value
    assert patch.would_merge
    assert patch.requires_review
    assert all(item["writes_real_db"] is False for item in patch.would_remove_low_value)
    assert all("recoverability_status" in item for item in patch.requires_review)
    assert all(
        item["candidate_action"] == "merge_suggestion"
        for item in patch.requires_review
        if item["scenario"] == "near_merge_not_duplicate"
    )
    assert not any(
        item["scenario"] == "near_merge_not_duplicate"
        for item in patch.would_merge
    )
