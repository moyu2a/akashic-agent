from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InjectionGovernanceShadowResult:
    baseline_result: dict[str, Any]
    experimental_result: dict[str, Any]
    metrics: dict[str, Any]


def build_injection_governance_shadow_result(
    *,
    baseline_items: list[dict[str, object]],
    baseline_injected_ids: list[str],
    baseline_text_block: str,
    candidate_items: list[dict[str, object]],
    max_chars: int,
    max_items: int,
) -> InjectionGovernanceShadowResult:
    safe_max_chars = max(60, int(max_chars))
    safe_max_items = max(1, int(max_items))
    baseline_ids = _ids(baseline_items)
    baseline_injected = [
        str(item_id) for item_id in baseline_injected_ids if str(item_id).strip()
    ]
    ordered_candidates = sorted(
        [dict(item) for item in candidate_items if _hit_id(item)],
        key=lambda item: (
            float(item.get("experimental_score") or item.get("score") or 0.0),
            _type_priority(str(item.get("memory_type") or "")),
            _hit_id(item),
        ),
        reverse=True,
    )
    experimental_ids: list[str] = []
    inject_reasons: dict[str, str] = {}
    drop_reasons: dict[str, str] = {}
    used_chars = 0
    seen_summaries: set[str] = set()
    for item in ordered_candidates:
        item_id = _hit_id(item)
        summary = str(item.get("summary") or "").strip()
        reason = _drop_reason(item, seen_summaries=seen_summaries)
        if reason:
            drop_reasons[item_id] = reason
            continue
        line_chars = len(summary) + len(item_id) + 8
        if used_chars + line_chars > safe_max_chars:
            drop_reasons[item_id] = "over_budget"
            continue
        if len(experimental_ids) >= safe_max_items:
            drop_reasons[item_id] = "max_items"
            continue
        experimental_ids.append(item_id)
        used_chars += line_chars
        seen_summaries.add(summary)
        inject_reasons[item_id] = _inject_reason(item)

    prompt_delta = used_chars - len(str(baseline_text_block or ""))
    low_confidence_injected_count = sum(
        1
        for item in baseline_items
        if _hit_id(item) in set(baseline_injected)
        and float(item.get("score") or 0.0) < 0.6
    )
    return InjectionGovernanceShadowResult(
        baseline_result={
            "baseline_ids": baseline_ids,
            "baseline_injected_ids": baseline_injected,
            "baseline_injected_count": len(baseline_injected),
            "baseline_text_chars": len(str(baseline_text_block or "")),
        },
        experimental_result={
            "experimental_injected_ids": experimental_ids,
            "experimental_injected_count": len(experimental_ids),
            "drop_reasons": drop_reasons,
            "inject_reasons": inject_reasons,
            "experimental_text_chars": used_chars,
        },
        metrics={
            "baseline_injected_count": len(baseline_injected),
            "experimental_injected_count": len(experimental_ids),
            "prompt_token_delta": prompt_delta,
            "low_confidence_injected_count": low_confidence_injected_count,
            "dropped_count": len(drop_reasons),
            "newly_injected_count": len(set(experimental_ids) - set(baseline_injected)),
            "removed_from_injection_count": len(set(baseline_injected) - set(experimental_ids)),
        },
    )


def _drop_reason(item: dict[str, object], *, seen_summaries: set[str]) -> str:
    summary = str(item.get("summary") or "").strip()
    score = float(item.get("score") or item.get("experimental_score") or 0.0)
    experimental_score = float(item.get("experimental_score") or score)
    if not summary:
        return "empty_summary"
    if summary in seen_summaries:
        return "duplicate"
    if len(summary) > 600:
        return "over_budget"
    if score < 0.55:
        return "low_confidence"
    if experimental_score < 0.35:
        return "weak_relevance"
    return ""


def _inject_reason(item: dict[str, object]) -> str:
    memory_type = str(item.get("memory_type") or "")
    if memory_type == "procedure":
        return "high_value_rule"
    if memory_type == "preference":
        return "stable_preference"
    if str(item.get("source_ref") or "").strip():
        return "sourced_context"
    return "ranked_context"


def _hit_id(item: dict[str, object]) -> str:
    return str(item.get("id") or "").strip()


def _ids(items: list[dict[str, object]]) -> list[str]:
    result: list[str] = []
    for item in items:
        item_id = _hit_id(item)
        if item_id:
            result.append(item_id)
    return result


def _type_priority(memory_type: str) -> int:
    if memory_type == "procedure":
        return 3
    if memory_type == "preference":
        return 2
    if memory_type == "profile":
        return 1
    if memory_type == "event":
        return 0
    return -1
