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


def test_sleep_hygiene_patch_marks_unverified_cleanup_as_not_source_backed_safe() -> None:
    records = (
        {
            "item_id": "low-1",
            "case_id": "case-1",
            "case_set": "standard",
            "scenario": "",
            "source_ref": "cli:local:1",
            "expected_after_state": "low_value_removed",
            "after_state": "low_value_removed",
            "shadow_after_state": "low_value_removed",
            "candidate_action": "low_value_cleanup",
            "candidate_source": "low_value_candidate",
            "baseline_token_estimate": 10,
            "after_token_estimate": 0,
            "source_ref_available": True,
            "source_fetch_success": False,
            "source_fetch_mode": "session-store",
            "source_support_status": "missing",
            "safe_cleanup_candidate": True,
            "requires_review": False,
        },
    )

    patch = build_sleep_hygiene_dry_run_patch(records)

    entry = patch.would_remove_low_value[0]
    assert entry["source_backed_action_safe"] is False
    assert entry["source_backed_block_reason"] == "source_not_fetchable"


def test_sleep_hygiene_patch_rejects_proxy_source_as_source_backed_safe() -> None:
    records = (
        {
            "item_id": "low-1",
            "case_id": "case-1",
            "case_set": "standard",
            "scenario": "",
            "source_ref": "cli:local:1",
            "expected_after_state": "low_value_removed",
            "after_state": "low_value_removed",
            "shadow_after_state": "low_value_removed",
            "candidate_action": "low_value_cleanup",
            "candidate_source": "low_value_candidate",
            "baseline_token_estimate": 10,
            "after_token_estimate": 0,
            "source_ref_available": True,
            "source_fetch_success": True,
            "source_fetch_mode": "proxy",
            "source_support_status": "supported",
            "safe_cleanup_candidate": True,
            "requires_review": False,
        },
    )

    patch = build_sleep_hygiene_dry_run_patch(records)

    entry = patch.would_remove_low_value[0]
    assert entry["source_backed_action_safe"] is False
    assert entry["source_backed_block_reason"] == "not_session_store_source"
