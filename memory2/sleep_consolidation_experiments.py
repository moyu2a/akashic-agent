from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class SleepConsolidationShadowResult:
    baseline_result: dict[str, Any]
    experimental_result: dict[str, Any]
    metrics: dict[str, Any]


def build_sleep_consolidation_shadow_result(
    *,
    memory_items: list[dict[str, object]],
    now: datetime | None = None,
    duplicate_threshold: float = 0.88,
    merge_threshold: float = 0.55,
    stale_days: int = 180,
    max_duplicate_groups: int = 100,
    max_merge_candidates: int = 100,
    max_conflict_candidates: int = 100,
    max_stale_candidates: int = 100,
    max_low_value_candidates: int = 100,
) -> SleepConsolidationShadowResult:
    started_at = time.perf_counter()
    current_time = now or datetime.now(timezone.utc)
    active_items = [
        dict(item)
        for item in memory_items
        if str(item.get("status") or "active").strip() == "active"
        and str(item.get("id") or "").strip()
    ]
    conflict_pairs = _conflict_pair_ids(active_items)
    all_conflicts = _conflict_candidates(active_items, conflict_pairs)
    all_duplicate_groups = _duplicate_groups(
        active_items,
        duplicate_threshold,
        excluded_pairs=conflict_pairs,
    )
    all_merge_candidates = _merge_candidates(
        active_items,
        all_duplicate_groups,
        merge_threshold,
        duplicate_threshold,
        excluded_pairs=conflict_pairs,
    )
    duplicate_groups = all_duplicate_groups[: max(0, int(max_duplicate_groups))]
    merge_candidates = all_merge_candidates[: max(0, int(max_merge_candidates))]
    conflicts = all_conflicts[: max(0, int(max_conflict_candidates))]
    all_stale_ids = _stale_candidate_ids(
        active_items,
        now=current_time,
        stale_days=stale_days,
    )
    all_low_value_ids = _low_value_candidate_ids(active_items, all_stale_ids)
    stale_ids = all_stale_ids[: max(0, int(max_stale_candidates))]
    low_value_ids = all_low_value_ids[: max(0, int(max_low_value_candidates))]
    missing_source_ref_count = sum(
        1 for item in active_items if not str(item.get("source_ref") or "").strip()
    )
    duplicate_item_ids = sorted(
        {item_id for group in duplicate_groups for item_id in group["item_ids"]}
    )
    estimated_token_saving = _estimated_token_saving(
        active_items,
        duplicate_item_ids=duplicate_item_ids,
        merge_candidates=merge_candidates,
        stale_ids=stale_ids,
    )
    latency_ms = round((time.perf_counter() - started_at) * 1000, 4)

    return SleepConsolidationShadowResult(
        baseline_result={
            "active_memory_count": len(active_items),
            "baseline_item_ids": _ids(active_items),
        },
        experimental_result={
            "duplicate_groups": duplicate_groups,
            "merge_candidates": merge_candidates,
            "stale_candidate_ids": stale_ids,
            "low_value_candidate_ids": low_value_ids,
            "conflict_candidates": conflicts,
        },
        metrics={
            "scanned_count": len(active_items),
            "duplicate_group_count": len(duplicate_groups),
            "duplicate_item_count": len(duplicate_item_ids),
            "merge_candidate_count": len(merge_candidates),
            "stale_candidate_count": len(all_stale_ids),
            "low_value_candidate_count": len(all_low_value_ids),
            "conflict_candidate_count": len(conflicts),
            "missing_source_ref_count": missing_source_ref_count,
            "estimated_token_saving": estimated_token_saving,
            "estimated_redundancy_drop": _ratio(
                len(duplicate_item_ids),
                len(active_items),
            ),
            "job_latency_ms": latency_ms,
            "applied_change_count": 0,
            "duplicate_group_truncated_count": max(
                0,
                len(all_duplicate_groups) - len(duplicate_groups),
            ),
            "merge_candidate_truncated_count": max(
                0,
                len(all_merge_candidates) - len(merge_candidates),
            ),
            "conflict_candidate_truncated_count": max(
                0,
                len(all_conflicts) - len(conflicts),
            ),
            "stale_candidate_truncated_count": max(
                0,
                len(all_stale_ids) - len(stale_ids),
            ),
            "low_value_candidate_truncated_count": max(
                0,
                len(all_low_value_ids) - len(low_value_ids),
            ),
        },
    )


_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_WORD_RE = re.compile(r"[A-Za-z0-9_]+")

_POSITIVE_MARKERS = ("喜欢", "偏好", "prefer", "always")
_NEGATIVE_MARKERS = ("不喜欢", "不要", "避免", "dislike", "avoid")
_TEMPORARY_MARKERS = ("临时", "测试", "本次", "temporary")


def _ids(items: list[dict[str, object]]) -> list[str]:
    return [
        str(item.get("id") or "").strip()
        for item in items
        if str(item.get("id") or "").strip()
    ]


def _tokens(text: object) -> set[str]:
    raw = str(text or "").lower()
    tokens = set(_WORD_RE.findall(raw))
    tokens.update(ch for ch in raw if _CJK_RE.match(ch))
    return {token for token in tokens if token.strip()}


def _similarity(left: dict[str, object], right: dict[str, object]) -> float:
    left_text = left.get("summary")
    right_text = right.get("summary")
    left_tokens = _tokens(left_text)
    right_tokens = _tokens(right_text)
    if not left_tokens or not right_tokens:
        return 0.0
    base = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    shared_terms = _word_terms(left_text) & _word_terms(right_text)
    bonus = 0.08 if shared_terms else 0.0
    return round(min(1.0, base + bonus), 4)


def _same_scope(left: dict[str, object], right: dict[str, object]) -> bool:
    return (
        str(left.get("scope_channel") or "")
        == str(right.get("scope_channel") or "")
        and str(left.get("scope_chat_id") or "")
        == str(right.get("scope_chat_id") or "")
    )


def _word_terms(text: object) -> set[str]:
    return {
        token for token in _WORD_RE.findall(str(text or "").lower()) if len(token) > 1
    }


def _same_type_and_scope(
    left: dict[str, object],
    right: dict[str, object],
) -> bool:
    return (
        str(left.get("memory_type") or "") == str(right.get("memory_type") or "")
        and _same_scope(left, right)
    )


def _conflict_pair_ids(items: list[dict[str, object]]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for left, right in _item_pairs(items):
        if not _same_type_and_scope(left, right):
            continue
        if _similarity(left, right) < 0.35:
            continue
        if not _has_opposite_preference_signal(left, right):
            continue
        pairs.add(_pair_id(left, right))
    return pairs


def _conflict_candidates(
    items: list[dict[str, object]],
    conflict_pairs: set[tuple[str, str]],
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    by_id = {str(item.get("id") or "").strip(): item for item in items}
    for left_id, right_id in sorted(conflict_pairs):
        left = by_id.get(left_id)
        right = by_id.get(right_id)
        if left is None or right is None:
            continue
        candidates.append(
            {
                "item_ids": [left_id, right_id],
                "reason": "opposite_preference_signal",
                "similarity": _similarity(left, right),
            }
        )
    return _sort_candidates(candidates)


def _duplicate_groups(
    items: list[dict[str, object]],
    duplicate_threshold: float,
    *,
    excluded_pairs: set[tuple[str, str]],
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for left, right in _item_pairs(items):
        if _pair_id(left, right) in excluded_pairs:
            continue
        if not _same_type_and_scope(left, right):
            continue
        similarity = _similarity(left, right)
        if similarity < duplicate_threshold:
            continue
        candidates.append(
            {
                "item_ids": sorted([_item_id(left), _item_id(right)]),
                "reason": "near_duplicate",
                "similarity": similarity,
            }
        )
    return _sort_candidates(candidates)


def _merge_candidates(
    items: list[dict[str, object]],
    duplicate_groups: list[dict[str, object]],
    merge_threshold: float,
    duplicate_threshold: float,
    *,
    excluded_pairs: set[tuple[str, str]],
) -> list[dict[str, object]]:
    duplicated_ids = {
        str(item_id)
        for group in duplicate_groups
        for item_id in group.get("item_ids", [])
    }
    candidates: list[dict[str, object]] = []
    for left, right in _item_pairs(items):
        pair_id = _pair_id(left, right)
        if pair_id in excluded_pairs:
            continue
        if pair_id[0] in duplicated_ids or pair_id[1] in duplicated_ids:
            continue
        if not _same_type_and_scope(left, right):
            continue
        similarity = _similarity(left, right)
        if similarity < merge_threshold or similarity >= duplicate_threshold:
            continue
        candidates.append(
            {
                "item_ids": list(pair_id),
                "reason": "same_type_related_content",
                "similarity": similarity,
            }
        )
    return _sort_candidates(candidates)


def _stale_candidate_ids(
    items: list[dict[str, object]],
    *,
    now: datetime,
    stale_days: int,
) -> list[str]:
    stale: list[str] = []
    for item in items:
        updated_at = _parse_datetime(item.get("updated_at"))
        if updated_at is None:
            continue
        age_days = (now - updated_at).total_seconds() / 86400.0
        if age_days < stale_days:
            continue
        if _coerce_int(item.get("reinforcement"), 1) > 1:
            continue
        if _coerce_int(item.get("emotional_weight"), 0) > 1:
            continue
        stale.append(_item_id(item))
    return sorted(stale)


def _low_value_candidate_ids(
    items: list[dict[str, object]],
    stale_ids: list[str],
) -> list[str]:
    stale_set = set(stale_ids)
    low_value: list[str] = []
    for item in items:
        item_id = _item_id(item)
        if item_id not in stale_set:
            continue
        summary = str(item.get("summary") or "").lower()
        if str(item.get("memory_type") or "") == "event" or _contains_any(
            summary,
            _TEMPORARY_MARKERS,
        ):
            low_value.append(item_id)
    return sorted(low_value)


def _estimated_token_saving(
    items: list[dict[str, object]],
    *,
    duplicate_item_ids: list[str],
    merge_candidates: list[dict[str, object]],
    stale_ids: list[str],
) -> int:
    by_id = {_item_id(item): item for item in items}
    saving_ids = set(duplicate_item_ids) | set(stale_ids)
    for candidate in merge_candidates:
        candidate_ids = [str(item_id) for item_id in candidate.get("item_ids", [])]
        saving_ids.update(candidate_ids[1:])
    return sum(_token_estimate(by_id[item_id]) for item_id in saving_ids if item_id in by_id)


def _token_estimate(item: dict[str, object]) -> int:
    return max(1, len(str(item.get("summary") or "")) // 4)


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _item_pairs(
    items: list[dict[str, object]],
) -> list[tuple[dict[str, object], dict[str, object]]]:
    ordered = sorted(items, key=_item_id)
    pairs: list[tuple[dict[str, object], dict[str, object]]] = []
    for index, left in enumerate(ordered):
        for right in ordered[index + 1 :]:
            pairs.append((left, right))
    return pairs


def _pair_id(
    left: dict[str, object],
    right: dict[str, object],
) -> tuple[str, str]:
    return tuple(sorted([_item_id(left), _item_id(right)]))


def _item_id(item: dict[str, object]) -> str:
    return str(item.get("id") or "").strip()


def _has_opposite_preference_signal(
    left: dict[str, object],
    right: dict[str, object],
) -> bool:
    left_text = str(left.get("summary") or "").lower()
    right_text = str(right.get("summary") or "").lower()
    left_direction = _preference_direction(left_text)
    right_direction = _preference_direction(right_text)
    return bool(left_direction and right_direction and left_direction != right_direction)


def _preference_direction(text: str) -> str:
    if _contains_any(text, _NEGATIVE_MARKERS):
        return "negative"
    if _contains_any(text, _POSITIVE_MARKERS):
        return "positive"
    return ""


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _parse_datetime(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _coerce_int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _sort_candidates(candidates: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        candidates,
        key=lambda item: (
            -float(item.get("similarity") or 0.0),
            [str(item_id) for item_id in item.get("item_ids", [])],
        ),
    )
