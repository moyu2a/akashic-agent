from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class SleepHygieneDryRunPatch:
    would_merge: tuple[dict[str, object], ...]
    would_mark_stale: tuple[dict[str, object], ...]
    would_remove_low_value: tuple[dict[str, object], ...]
    would_keep: tuple[dict[str, object], ...]
    requires_review: tuple[dict[str, object], ...]
    applied_change_count: int = 0


def build_sleep_hygiene_dry_run_patch(
    records: Sequence[dict[str, object]],
) -> SleepHygieneDryRunPatch:
    would_merge: list[dict[str, object]] = []
    would_mark_stale: list[dict[str, object]] = []
    would_remove_low_value: list[dict[str, object]] = []
    would_keep: list[dict[str, object]] = []
    requires_review: list[dict[str, object]] = []

    for record in records:
        entry = _patch_entry(record)
        if record.get("requires_review") is True:
            requires_review.append(entry)
        elif record.get("candidate_action") == "duplicate_merge":
            would_merge.append(entry)
        elif record.get("candidate_action") == "stale_cleanup":
            would_mark_stale.append(entry)
        elif record.get("candidate_action") == "low_value_cleanup":
            would_remove_low_value.append(entry)
        else:
            would_keep.append(entry)

    return SleepHygieneDryRunPatch(
        would_merge=tuple(would_merge),
        would_mark_stale=tuple(would_mark_stale),
        would_remove_low_value=tuple(would_remove_low_value),
        would_keep=tuple(would_keep),
        requires_review=tuple(requires_review),
    )


def write_sleep_hygiene_dry_run_patch_json(
    patch: SleepHygieneDryRunPatch,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(patch), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _patch_entry(record: dict[str, object]) -> dict[str, object]:
    return {
        "item_id": record["item_id"],
        "case_id": record.get("case_id", ""),
        "case_set": record.get("case_set", ""),
        "scenario": record.get("scenario", ""),
        "source_ref": record.get("source_ref", ""),
        "expected_after_state": record.get("expected_after_state", ""),
        "after_state": record.get("after_state", ""),
        "shadow_after_state": record.get("shadow_after_state", ""),
        "candidate_action": record.get("candidate_action", "none"),
        "candidate_source": record.get("candidate_source", "none"),
        "baseline_token_estimate": record.get("baseline_token_estimate", 0),
        "after_token_estimate": record.get("after_token_estimate", 0),
        "source_ref_available": record.get("source_ref_available", False),
        "source_fetch_success": record.get("source_fetch_success", False),
        "source_fetch_mode": record.get("source_fetch_mode", ""),
        "source_support_status": record.get("source_support_status", ""),
        "source_backed_action_safe": _source_backed_action_safe(record),
        "source_backed_block_reason": _source_backed_block_reason(record),
        "operation_type": _operation_type(record),
        "recoverability_status": _recoverability_status(record),
        "recoverability_reason": _recoverability_reason(record),
        "writes_real_db": False,
    }


def _operation_type(record: dict[str, object]) -> str:
    action = str(record.get("candidate_action") or "none")
    if action == "duplicate_merge":
        return "would_merge"
    if action == "stale_cleanup":
        return "would_mark_stale"
    if action == "low_value_cleanup":
        return "would_remove_low_value"
    if bool(record.get("requires_review")):
        return "requires_review"
    return "would_keep"


def _recoverability_status(record: dict[str, object]) -> str:
    operation = _operation_type(record)
    if operation == "would_keep":
        return "not_applicable"
    if bool(record.get("requires_review")):
        return "review_only"
    if bool(record.get("source_fetch_success")):
        return "source_backed_report_only"
    if bool(record.get("source_ref_available")):
        return "source_ref_unverified_report_only"
    return "insufficient_restore_data"


def _recoverability_reason(record: dict[str, object]) -> str:
    status = _recoverability_status(record)
    if status == "not_applicable":
        return "record is not a cleanup or review action"
    if status == "source_backed_report_only":
        return "source evidence was available, but no database mutation was executed"
    if status == "source_ref_unverified_report_only":
        return "source_ref exists but resolver did not verify original message content"
    if status == "review_only":
        return "candidate is a review suggestion, not a cleanup action"
    return "record lacks verified source evidence for restoration"


def _source_backed_action_safe(record: dict[str, object]) -> bool:
    if not bool(record.get("safe_cleanup_candidate")):
        return False
    return (
        str(record.get("source_fetch_mode") or "") == "session-store"
        and record.get("source_fetch_success") is True
        and str(record.get("source_support_status") or "") == "supported"
    )


def _source_backed_block_reason(record: dict[str, object]) -> str:
    if bool(record.get("requires_review")):
        return "requires_review"
    if not bool(record.get("safe_cleanup_candidate")):
        return "not_cleanup_candidate"
    if str(record.get("source_fetch_mode") or "") != "session-store":
        return "not_session_store_source"
    if record.get("source_fetch_success") is not True:
        return "source_not_fetchable"
    if str(record.get("source_support_status") or "") != "supported":
        return "source_not_supporting_summary"
    return ""
