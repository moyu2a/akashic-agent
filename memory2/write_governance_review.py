from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class WriteReviewResolution:
    decision: str
    reason: str
    promoted: bool
    controlled: bool
    reasons: tuple[str, ...]


def resolve_write_review_candidate(
    *,
    summary: str,
    score_result: dict[str, Any],
    existing_memories: Sequence[dict[str, object]] = (),
    source_ref: str = "",
    category: str = "",
    case_set: str = "",
    subtype: str = "",
) -> WriteReviewResolution:
    del category, case_set, subtype
    decision = str(score_result.get("decision") or "").strip()
    reasons = _score_reasons(score_result)
    final_score = _score_value(score_result)
    text = str(summary or "")

    if decision == "allow":
        return _resolution("approve_write", "already_allowed", ("already_allowed",))
    if decision == "reject":
        return _resolution("reject", "already_rejected", ("already_rejected",))
    if _has_pollution_reason(reasons) or _looks_like_inference_pollution(text):
        return _resolution("reject", "pollution_risk", reasons)
    if "conflict_with_existing_memory" in reasons:
        return _resolution("keep_review", "conflict_requires_confirmation", reasons)
    if _detect_lexical_conflict(text, existing_memories):
        return _resolution(
            "keep_review",
            "conflict_requires_confirmation",
            (*reasons, "lexical_conflict"),
        )
    if _has_broad_change_marker(text) and existing_memories:
        return _resolution(
            "keep_review",
            "conflict_requires_confirmation",
            (*reasons, "broad_change_marker"),
        )
    if (
        str(source_ref or "").strip()
        and "long_term_stability" in reasons
        and final_score >= 0.45
    ):
        return _resolution("approve_write", "trusted_useful_review", reasons)
    return _resolution("keep_review", "insufficient_review_confidence", reasons)


def apply_final_write_safety_gate(
    *,
    summary: str,
    score_result: dict[str, Any],
    existing_memories: Sequence[dict[str, object]] = (),
    source_ref: str = "",
) -> WriteReviewResolution | None:
    del source_ref
    reasons = _score_reasons(score_result)
    text = str(summary or "")
    if _has_pollution_reason(reasons) or _looks_like_inference_pollution(text):
        return _resolution("reject", "pollution_risk", reasons)
    if "conflict_with_existing_memory" in reasons:
        return _resolution("keep_review", "conflict_requires_confirmation", reasons)
    if _detect_lexical_conflict(text, existing_memories):
        return _resolution(
            "keep_review",
            "conflict_requires_confirmation",
            (*reasons, "lexical_conflict"),
        )
    if _detect_near_duplicate(text, existing_memories):
        return _resolution(
            "reject",
            "duplicate_safety_gate",
            (*reasons, "near_duplicate_existing_memory"),
        )
    return None


def _resolution(
    decision: str,
    reason: str,
    reasons: Sequence[str],
) -> WriteReviewResolution:
    return WriteReviewResolution(
        decision=decision,
        reason=reason,
        promoted=decision == "approve_write",
        controlled=decision != "approve_write",
        reasons=tuple(dict.fromkeys(str(item) for item in reasons if str(item).strip())),
    )


def _score_reasons(score_result: dict[str, Any]) -> tuple[str, ...]:
    raw = score_result.get("reasons")
    if isinstance(raw, list | tuple):
        return tuple(str(item) for item in raw if str(item).strip())
    reason = str(score_result.get("reason") or "").strip()
    return (reason,) if reason else ()


def _score_value(score_result: dict[str, Any]) -> float:
    raw = score_result.get("final_score", score_result.get("score", 0.0))
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def _has_pollution_reason(reasons: Sequence[str]) -> bool:
    pollution = {
        "temporary_state",
        "assistant_inference",
        "duplicate_existing_memory",
    }
    return any(reason in pollution for reason in reasons)


def _looks_like_inference_pollution(text: str) -> bool:
    markers = (
        "助手推断",
        "可能喜欢",
        "从回答中猜到",
        "模型感觉",
        "大概希望",
        "看起来",
        "应该偏向",
        "但没有确认",
    )
    return any(marker in text for marker in markers)


def _has_broad_change_marker(text: str) -> bool:
    markers = (
        "改为",
        "不要",
        "替代",
        "覆盖旧规则",
        "优先级调整",
        "先忽略旧",
    )
    return any(marker in text for marker in markers)


def _detect_lexical_conflict(
    summary: str,
    existing_memories: Sequence[dict[str, object]],
) -> bool:
    text = str(summary or "")
    if not text or not existing_memories:
        return False
    if not _has_broad_change_marker(text):
        return False
    for item in existing_memories:
        existing = str(item.get("summary") or "")
        if not existing:
            continue
        if "不要先给结论" in text and "先给结论" in existing:
            return True
        if ("完整铺开解释" in text or "完整长文解释" in text) and (
            "先给结论" in existing or "简短结论" in existing
        ):
            return True
        if _token_overlap(text, existing) >= 0.18:
            return True
    return False


def _detect_near_duplicate(
    summary: str,
    existing_memories: Sequence[dict[str, object]],
) -> bool:
    text = str(summary or "")
    if not text or not existing_memories:
        return False
    for item in existing_memories:
        existing = str(item.get("summary") or "")
        if not existing:
            continue
        if _token_overlap(text, existing) >= 0.25:
            return True
        if _shared_action_phrase(text, existing):
            return True
    return False


def _shared_action_phrase(left: str, right: str) -> bool:
    phrases = (
        "先给结论",
        "保留关键数字",
        "避免泛化",
        "写清验证命令",
        "说明边界",
        "标出风险",
        "记录来源",
        "保留反例",
    )
    return any(phrase in left and phrase in right for phrase in phrases)


def _token_overlap(left: str, right: str) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _tokens(text: str) -> set[str]:
    normalized = str(text or "").lower()
    ascii_tokens = {
        chunk
        for chunk in normalized.replace("_", " ").split()
        if chunk.strip()
    }
    cjk_tokens = {char for char in normalized if "\u4e00" <= char <= "\u9fff"}
    return ascii_tokens | cjk_tokens
