from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class AnswerPostCheckShadow:
    shadow_enabled: bool
    production_safe_evidence_contract: bool
    allowed_evidence_included: bool
    included_allowed_evidence_ids: tuple[str, ...]
    missing_likely_relevant_context_ids: tuple[str, ...]
    forbidden_boundary_included: bool
    included_forbidden_boundary_ids: tuple[str, ...]
    stale_evidence_included: bool
    included_stale_warning_ids: tuple[str, ...]
    conflict_evidence_included: bool
    included_conflict_warning_ids: tuple[str, ...]
    insufficient_evidence_fallback_expected: bool
    insufficient_evidence_fallback_observed: bool
    forbidden_boundary_mentions: tuple[str, ...]
    needs_retry: bool
    retry_reasons: tuple[str, ...]
    answer_candidate_contract_enabled: bool = False
    required_terms_missing: bool = False
    answer_choice_group_missing: bool = False
    language_requirement_failed: bool = False
    raw_prompt: str = ""
    raw_answer: str = ""


def build_answer_post_check_shadow(
    answer: str,
    answer_contract: Mapping[str, object],
    context_memory_ids: Sequence[str],
) -> AnswerPostCheckShadow:
    production_safe = bool(answer_contract.get("production_safe_evidence_contract"))
    if not production_safe:
        return AnswerPostCheckShadow(
            shadow_enabled=False,
            production_safe_evidence_contract=False,
            allowed_evidence_included=False,
            included_allowed_evidence_ids=(),
            missing_likely_relevant_context_ids=(),
            forbidden_boundary_included=False,
            included_forbidden_boundary_ids=(),
            stale_evidence_included=False,
            included_stale_warning_ids=(),
            conflict_evidence_included=False,
            included_conflict_warning_ids=(),
            insufficient_evidence_fallback_expected=False,
            insufficient_evidence_fallback_observed=False,
            forbidden_boundary_mentions=(),
            needs_retry=False,
            retry_reasons=(),
            answer_candidate_contract_enabled=False,
            required_terms_missing=False,
            answer_choice_group_missing=False,
            language_requirement_failed=False,
        )

    context_ids = _string_tuple(context_memory_ids)
    allowed = _string_tuple(answer_contract.get("allowed_evidence_ids", ()))
    likely = _string_tuple(answer_contract.get("likely_relevant_evidence_ids", ()))
    forbidden = _string_tuple(answer_contract.get("forbidden_boundary_ids", ()))
    stale = _string_tuple(answer_contract.get("stale_warning_ids", ()))
    conflict = _string_tuple(answer_contract.get("conflict_warning_ids", ()))
    expected_fallback = bool(answer_contract.get("insufficient_evidence_fallback"))
    candidate_contract = answer_contract.get("answer_candidate_contract")
    candidate_enabled = (
        isinstance(candidate_contract, Mapping)
        and bool(candidate_contract.get("enabled"))
    )
    answer_score = answer_contract.get("answer_score")
    score_map = answer_score if isinstance(answer_score, Mapping) else {}
    required_terms_missing = (
        candidate_enabled
        and int(score_map.get("expected_contains_miss_count", 0) or 0) > 0
    )
    answer_choice_group_missing = (
        candidate_enabled
        and int(score_map.get("expected_any_miss_count", 0) or 0) > 0
    )
    language_requirement_failed = (
        candidate_enabled
        and "language_passed" in score_map
        and not bool(score_map.get("language_passed"))
    )

    included_allowed = _intersection_in_order(context_ids, allowed)
    context_set = set(context_ids)
    missing_likely = tuple(item_id for item_id in likely if item_id not in context_set)
    included_forbidden = _intersection_in_order(context_ids, forbidden)
    included_stale = _intersection_in_order(context_ids, stale)
    included_conflict = _intersection_in_order(context_ids, conflict)
    fallback_observed = _mentions_insufficient_evidence(answer)
    boundary_mentions = tuple(
        item_id for item_id in forbidden if item_id and item_id in answer
    )

    retry_reasons: list[str] = []
    if included_forbidden:
        retry_reasons.append("forbidden_boundary_included")
    if boundary_mentions:
        retry_reasons.append("forbidden_boundary_mentioned")
    if missing_likely:
        retry_reasons.append("missing_likely_relevant_context")
    if included_stale:
        retry_reasons.append("stale_evidence_included")
    if included_conflict:
        retry_reasons.append("conflict_evidence_included")
    if expected_fallback and not fallback_observed:
        retry_reasons.append("insufficient_evidence_fallback_missing")
    if required_terms_missing:
        retry_reasons.append("required_terms_missing")
    if answer_choice_group_missing:
        retry_reasons.append("answer_choice_group_missing")
    if language_requirement_failed:
        retry_reasons.append("language_requirement_failed")

    return AnswerPostCheckShadow(
        shadow_enabled=True,
        production_safe_evidence_contract=True,
        allowed_evidence_included=bool(included_allowed),
        included_allowed_evidence_ids=included_allowed,
        missing_likely_relevant_context_ids=missing_likely,
        forbidden_boundary_included=bool(included_forbidden),
        included_forbidden_boundary_ids=included_forbidden,
        stale_evidence_included=bool(included_stale),
        included_stale_warning_ids=included_stale,
        conflict_evidence_included=bool(included_conflict),
        included_conflict_warning_ids=included_conflict,
        insufficient_evidence_fallback_expected=expected_fallback,
        insufficient_evidence_fallback_observed=fallback_observed,
        forbidden_boundary_mentions=boundary_mentions,
        needs_retry=bool(retry_reasons),
        retry_reasons=tuple(retry_reasons),
        answer_candidate_contract_enabled=candidate_enabled,
        required_terms_missing=required_terms_missing,
        answer_choice_group_missing=answer_choice_group_missing,
        language_requirement_failed=language_requirement_failed,
    )


def answer_post_check_shadow_to_dict(
    shadow: AnswerPostCheckShadow,
) -> dict[str, object]:
    return {
        "shadow_enabled": shadow.shadow_enabled,
        "production_safe_evidence_contract": shadow.production_safe_evidence_contract,
        "allowed_evidence_included": shadow.allowed_evidence_included,
        "included_allowed_evidence_ids": list(shadow.included_allowed_evidence_ids),
        "missing_likely_relevant_context_ids": list(
            shadow.missing_likely_relevant_context_ids
        ),
        "forbidden_boundary_included": shadow.forbidden_boundary_included,
        "included_forbidden_boundary_ids": list(shadow.included_forbidden_boundary_ids),
        "stale_evidence_included": shadow.stale_evidence_included,
        "included_stale_warning_ids": list(shadow.included_stale_warning_ids),
        "conflict_evidence_included": shadow.conflict_evidence_included,
        "included_conflict_warning_ids": list(shadow.included_conflict_warning_ids),
        "insufficient_evidence_fallback_expected": (
            shadow.insufficient_evidence_fallback_expected
        ),
        "insufficient_evidence_fallback_observed": (
            shadow.insufficient_evidence_fallback_observed
        ),
        "forbidden_boundary_mentions": list(shadow.forbidden_boundary_mentions),
        "needs_retry": shadow.needs_retry,
        "retry_reasons": list(shadow.retry_reasons),
        "answer_candidate_contract_enabled": shadow.answer_candidate_contract_enabled,
        "required_terms_missing": shadow.required_terms_missing,
        "answer_choice_group_missing": shadow.answer_choice_group_missing,
        "language_requirement_failed": shadow.language_requirement_failed,
    }


def _intersection_in_order(
    source: tuple[str, ...],
    allowed: tuple[str, ...],
) -> tuple[str, ...]:
    allowed_set = set(allowed)
    return tuple(item_id for item_id in source if item_id in allowed_set)


def _mentions_insufficient_evidence(answer: str) -> bool:
    markers = ("证据不足", "无法确认", "不能确认", "insufficient evidence")
    return any(marker.lower() in answer.lower() for marker in markers)


def _string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value else ()
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item) for item in value if str(item))
