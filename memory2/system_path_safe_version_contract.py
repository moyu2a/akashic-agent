from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from memory2.retrieval_governance import (
    CandidateGovernancePolicy,
    apply_retrieval_route,
    build_retrieval_routing_decision,
)
from memory2.version_chain_experiments import build_version_chain_shadow_result


SYSTEM_SAFE_VERSION_PROFILE = "system_memory_safe_version_governed"
SAFE_VERSION_ANSWER_PROMPT_VARIANTS = {
    "standard",
    "guided",
    "structured_guided",
    "near_query_block",
    "guided_retry_shadow",
    "schema_first_shadow",
}


@dataclass(frozen=True)
class AnswerCandidateContract:
    enabled: bool
    current_truth_ids: tuple[str, ...]
    current_truth_lines: tuple[str, ...]
    must_include_term_count: int
    forbidden_old_value_ids: tuple[str, ...]
    language_requirement: str
    candidate_reason: str


@dataclass(frozen=True)
class SystemPathEvidenceContract:
    profile_name: str
    production_safe: bool
    uses_fixture_answer_expectations: bool
    answer_prompt_variant: str
    candidate_governance_mode: str
    allowed_evidence: tuple[str, ...]
    likely_relevant_evidence: tuple[str, ...]
    stale_warning: tuple[str, ...]
    conflict_warning: tuple[str, ...]
    active_version: tuple[str, ...]
    forbidden_boundary: tuple[str, ...]
    allowed_evidence_ids: tuple[str, ...]
    likely_relevant_evidence_ids: tuple[str, ...]
    downgrade_ids: tuple[str, ...]
    requires_review_ids: tuple[str, ...]
    stale_warning_ids: tuple[str, ...]
    conflict_warning_ids: tuple[str, ...]
    active_version_ids: tuple[str, ...]
    insufficient_evidence_ids: tuple[str, ...]
    insufficient_evidence_fallback: bool
    forbidden_boundary_ids: tuple[str, ...]
    deleted_evidence_ids: tuple[str, ...]
    candidate_risk_tier_counts: dict[str, int]
    accepted_candidate_risk_tier_counts: dict[str, int]
    tiered_deleted_risks_by_reason: dict[str, int]
    version_boundary: dict[str, object]
    answer_candidate_contract: AnswerCandidateContract


@dataclass(frozen=True)
class SystemPathSafeVersionResult:
    contract: SystemPathEvidenceContract
    text_block: str
    accepted_items: tuple[dict[str, object], ...]
    trace: dict[str, object]


def build_system_path_safe_version_contract(
    *,
    query: str,
    baseline_items: Sequence[Mapping[str, Any]],
    route_trace: Mapping[str, Any],
    replacements: Sequence[Mapping[str, Any]] = (),
    top_k: int = 8,
    answer_guidance_enabled: bool = False,
    answer_prompt_variant: str = "standard",
) -> SystemPathSafeVersionResult:
    prompt_variant = normalize_safe_version_answer_prompt_variant(
        "" if bool(answer_guidance_enabled) and answer_prompt_variant == "standard" else answer_prompt_variant,
        answer_guidance_enabled=answer_guidance_enabled,
    )
    candidates_by_lane = _candidate_lanes(route_trace, baseline_items)
    decision = build_retrieval_routing_decision(query).with_candidate_governance(
        CandidateGovernancePolicy(enabled=True, mode="tiered")
    )
    accepted, trace = apply_retrieval_route(decision, candidates_by_lane)
    accepted = accepted[: max(1, int(top_k))]
    items_by_id = _item_by_id(candidates_by_lane)
    allowed_ids = _ids(accepted)
    version_boundary = build_version_chain_shadow_result(
        memory_items=list(items_by_id.values()),
        replacements=[dict(item) for item in replacements],
        recalled_items=[dict(item) for item in accepted],
    )
    records = _tier_records(trace)
    deleted_ids = tuple(
        item_id
        for item_id, record in records.items()
        if str(record.get("tier") or "") == "delete"
    )
    forbidden_boundary_ids = tuple(
        item_id
        for item_id in deleted_ids
        if "forbidden_candidate" in _string_tuple(records.get(item_id, {}).get("risks", ()))
        or _truthy(items_by_id.get(item_id, {}), "forbidden")
    )
    downgrade_ids = tuple(
        item_id
        for item_id in allowed_ids
        if str(records.get(item_id, {}).get("tier") or "") == "downgrade"
    )
    requires_review_ids = tuple(
        item_id
        for item_id in allowed_ids
        if str(records.get(item_id, {}).get("tier") or "") == "requires_review"
    )
    conflict_warning_ids = tuple(
        item_id
        for item_id in allowed_ids
        if "conflict_candidate" in _string_tuple(records.get(item_id, {}).get("risks", ()))
    )
    insufficient_ids = tuple(
        item_id
        for item_id in allowed_ids
        if "insufficient_evidence" in _string_tuple(records.get(item_id, {}).get("risks", ()))
    )
    stale_ids = tuple(
        _dedupe(
            (
                *deleted_ids,
                *version_boundary.experimental_result.get("stale_recalled_ids", []),
                *[
                    item_id
                    for item_id, item in items_by_id.items()
                    if str(item.get("status") or "").lower() == "superseded"
                ],
            )
        )
    )
    replacement_active_leaf_ids = set(
        str(item_id)
        for item_id in version_boundary.experimental_result.get("active_leaf_ids", [])
    )
    active_ids = tuple(
        item_id
        for item_id in allowed_ids
        if str(items_by_id.get(item_id, {}).get("status") or "active").lower()
        == "active"
        and (
            not replacement_active_leaf_ids
            or item_id in replacement_active_leaf_ids
            or item_id not in _replacement_ids(replacements)
        )
    )
    likely_ids = tuple(item_id for item_id in allowed_ids if item_id not in requires_review_ids)
    answer_candidate_contract = _build_answer_candidate_contract(
        enabled=prompt_variant in {"guided_retry_shadow", "schema_first_shadow"},
        prompt_variant=prompt_variant,
        active_ids=active_ids,
        likely_ids=likely_ids,
        stale_ids=stale_ids,
        deleted_ids=deleted_ids,
        items_by_id=items_by_id,
    )
    contract = SystemPathEvidenceContract(
        profile_name=SYSTEM_SAFE_VERSION_PROFILE,
        production_safe=True,
        uses_fixture_answer_expectations=False,
        answer_prompt_variant=prompt_variant,
        candidate_governance_mode="tiered",
        allowed_evidence=_evidence_lines(accepted),
        likely_relevant_evidence=_evidence_lines(
            [item for item in accepted if _item_id(item) in set(likely_ids)]
        ),
        stale_warning=stale_ids,
        conflict_warning=conflict_warning_ids,
        active_version=active_ids,
        forbidden_boundary=forbidden_boundary_ids,
        allowed_evidence_ids=allowed_ids,
        likely_relevant_evidence_ids=likely_ids,
        downgrade_ids=downgrade_ids,
        requires_review_ids=requires_review_ids,
        stale_warning_ids=stale_ids,
        conflict_warning_ids=conflict_warning_ids,
        active_version_ids=active_ids,
        insufficient_evidence_ids=insufficient_ids,
        insufficient_evidence_fallback=not bool(allowed_ids) or bool(insufficient_ids),
        forbidden_boundary_ids=forbidden_boundary_ids,
        deleted_evidence_ids=deleted_ids,
        candidate_risk_tier_counts=_int_dict(trace.get("candidate_risk_tier_counts", {})),
        accepted_candidate_risk_tier_counts=_int_dict(
            trace.get("accepted_candidate_risk_tier_counts", {})
        ),
        tiered_deleted_risks_by_reason=_int_dict(
            trace.get("tiered_deleted_risks_by_reason", {})
        ),
        version_boundary={
            "replacement_count": int(version_boundary.metrics.get("replacement_count", 0) or 0),
            "chain_count": int(version_boundary.metrics.get("chain_count", 0) or 0),
            "active_leaf_count": int(version_boundary.metrics.get("active_leaf_count", 0) or 0),
            "stale_recalled_count": int(version_boundary.metrics.get("stale_recalled_count", 0) or 0),
            "superseded_recalled_count": int(
                version_boundary.metrics.get("superseded_recalled_count", 0) or 0
            ),
            "rollback_candidate_count": int(
                version_boundary.metrics.get("rollback_candidate_count", 0) or 0
            ),
            "conflict_chain_count": int(
                version_boundary.metrics.get("conflict_chain_count", 0) or 0
            ),
        },
        answer_candidate_contract=answer_candidate_contract,
    )
    guidance_enabled = bool(answer_guidance_enabled)
    return SystemPathSafeVersionResult(
        contract=contract,
        text_block=render_system_path_evidence_contract_block(
            contract,
            answer_guidance_enabled=guidance_enabled,
            answer_prompt_variant=prompt_variant,
        ),
        accepted_items=tuple(dict(item) for item in accepted),
        trace={
            "safe_version_governed": system_path_contract_to_dict(
                contract,
                answer_guidance_enabled=guidance_enabled,
            )
        },
    )


def normalize_safe_version_answer_prompt_variant(
    value: object,
    *,
    answer_guidance_enabled: bool = False,
) -> str:
    variant = str(value or "").strip()
    if not variant:
        return "guided" if bool(answer_guidance_enabled) else "standard"
    if variant not in SAFE_VERSION_ANSWER_PROMPT_VARIANTS:
        return "guided" if bool(answer_guidance_enabled) else "standard"
    return variant


def render_system_path_evidence_contract_block(
    contract: SystemPathEvidenceContract,
    *,
    answer_guidance_enabled: bool = False,
    answer_prompt_variant: str = "standard",
) -> str:
    variant = normalize_safe_version_answer_prompt_variant(
        answer_prompt_variant,
        answer_guidance_enabled=answer_guidance_enabled,
    )
    lines = [
        f"Evidence Contract: {contract.profile_name}",
        "production_safe=true",
        "uses_fixture_answer_expectations=false",
        "candidate_governance_mode: " + contract.candidate_governance_mode,
        "allowed_evidence:",
        *_indent_lines(contract.allowed_evidence),
        "likely_relevant_evidence_count: " + str(len(contract.likely_relevant_evidence_ids)),
        "active_version_count: " + str(len(contract.active_version_ids)),
        "stale_warning_count: " + str(len(contract.stale_warning_ids)),
        "conflict_warning_count: " + str(len(contract.conflict_warning_ids)),
        "forbidden_boundary_count: " + str(len(contract.forbidden_boundary_ids)),
        "deleted_evidence_count: " + str(len(contract.deleted_evidence_ids)),
        "insufficient_evidence_fallback: "
        + ("true" if contract.insufficient_evidence_fallback else "false"),
        (
            "Instruction: answer only from allowed_evidence. If evidence is "
            "insufficient, say that the available memory is insufficient. Do not "
            "use deleted, superseded, cross-scope, or forbidden boundary evidence."
        ),
    ]
    if variant == "guided":
        lines.extend(
            [
                "Answer Guidance:",
                "  Use allowed_evidence as the only source for the answer.",
                "  State concrete facts from allowed_evidence directly.",
                "  Prefer active versions when active_version_count is greater than 0.",
                "  If the evidence is insufficient, say the available memory is insufficient.",
                "  Do not mention deleted, superseded, or forbidden boundary evidence.",
                "  Answer in the user's language.",
            ]
        )
    elif variant == "structured_guided":
        lines.extend(
            [
                "Structured Answer Guidance:",
                "answer_critical_evidence:",
                *_indent_lines(contract.likely_relevant_evidence),
                "active_allowed_evidence_count: "
                + str(len(contract.active_version_ids)),
                "  Use answer_critical_evidence first.",
                "  Prefer active allowed evidence over downgraded or review evidence.",
                "  State concrete facts from allowed_evidence directly.",
                "  If answer_critical_evidence is empty or insufficient, say the available memory is insufficient.",
                "  Do not mention deleted, superseded, or forbidden boundary evidence.",
                "  Answer in the user's language.",
            ]
        )
    elif variant == "near_query_block":
        lines.extend(
            [
                "Question-Proximal Memory Evidence:",
                "  Use this block for the immediately following user request.",
                "  Select the most direct facts from allowed_evidence before answering.",
                "  Prefer active versions when active_version_count is greater than 0.",
                "  If the evidence is insufficient, say the available memory is insufficient.",
                "  Do not use deleted, superseded, cross-scope, or forbidden boundary evidence.",
                "  Answer in the user's language.",
            ]
        )
    elif variant == "guided_retry_shadow":
        candidate = contract.answer_candidate_contract
        lines.extend(
            [
                "Answer Guidance:",
                "  Use allowed_evidence as the only source for the answer.",
                "  Use the Answer Candidate Contract to select the final answer.",
                *_answerable_contract_completion_guidance(contract),
                "  Directly answer the user's question first.",
                "  Restate at least one concrete current_truth fact in the answer.",
                "  Include the required current facts when they are supported by current_truth.",
                "  Do not answer with only an acknowledgement, meta action, or clarification question.",
                "  Do not output code blocks unless the user explicitly asks for code.",
                "  Answer in the user's language.",
                "Answer Candidate Contract:",
                "current_truth:",
                *_indent_lines(candidate.current_truth_lines),
                "must_include_term_count: " + str(candidate.must_include_term_count),
                "forbidden_old_value_count: "
                + str(len(candidate.forbidden_old_value_ids)),
                "language_requirement: " + candidate.language_requirement,
            ]
        )
    elif variant == "schema_first_shadow":
        candidate = contract.answer_candidate_contract
        lines.extend(
            [
                "Schema-First Answer Shadow:",
                "  Use allowed_evidence as the only source for the answer.",
                *_answerable_contract_completion_guidance(contract),
                "  First select the answer facts internally using this schema:",
                "  selected_facts: concrete current facts that answer the user.",
                "  active_version_used: true when an active/current version supports the answer.",
                "  ignored_superseded_or_stale: evidence ignored because it is old, stale, or superseded.",
                "  insufficient_evidence: true only when allowed_evidence cannot answer.",
                "  Then write only the final natural-language answer for the user.",
                "  Do not expose JSON, schema fields, memory ids, or internal selection notes.",
                "  Prefer current_truth facts when available.",
                "  Do not answer with only an acknowledgement, meta action, or clarification question.",
                "  Answer in the user's language.",
                "current_truth:",
                *_indent_lines(candidate.current_truth_lines),
                "must_include_term_count: " + str(candidate.must_include_term_count),
                "forbidden_old_value_count: "
                + str(len(candidate.forbidden_old_value_ids)),
                "language_requirement: " + candidate.language_requirement,
            ]
        )
    return "\n".join(lines)


def system_path_contract_to_dict(
    contract: SystemPathEvidenceContract,
    *,
    answer_guidance_enabled: bool = False,
) -> dict[str, object]:
    prompt_variant = normalize_safe_version_answer_prompt_variant(
        contract.answer_prompt_variant,
        answer_guidance_enabled=answer_guidance_enabled,
    )
    return {
        "profile_name": contract.profile_name,
        "production_safe": contract.production_safe,
        "production_safe_evidence_contract": contract.production_safe,
        "uses_fixture_answer_expectations": contract.uses_fixture_answer_expectations,
        "answer_guidance_enabled": prompt_variant != "standard",
        "answer_prompt_variant": prompt_variant,
        "candidate_governance_mode": contract.candidate_governance_mode,
        "allowed_evidence_ids": list(contract.allowed_evidence_ids),
        "likely_relevant_evidence_ids": list(contract.likely_relevant_evidence_ids),
        "downgrade_ids": list(contract.downgrade_ids),
        "requires_review_ids": list(contract.requires_review_ids),
        "stale_warning_ids": list(contract.stale_warning_ids),
        "conflict_warning_ids": list(contract.conflict_warning_ids),
        "active_version_ids": list(contract.active_version_ids),
        "insufficient_evidence_ids": list(contract.insufficient_evidence_ids),
        "insufficient_evidence_fallback": contract.insufficient_evidence_fallback,
        "forbidden_boundary_ids": list(contract.forbidden_boundary_ids),
        "deleted_evidence_ids": list(contract.deleted_evidence_ids),
        "candidate_risk_tier_counts": dict(contract.candidate_risk_tier_counts),
        "accepted_candidate_risk_tier_counts": dict(
            contract.accepted_candidate_risk_tier_counts
        ),
        "tiered_deleted_risks_by_reason": dict(contract.tiered_deleted_risks_by_reason),
        "version_boundary": dict(contract.version_boundary),
        "answer_candidate_contract": {
            "enabled": contract.answer_candidate_contract.enabled,
            "current_truth_count": len(contract.answer_candidate_contract.current_truth_ids),
            "must_include_term_count": contract.answer_candidate_contract.must_include_term_count,
            "forbidden_old_value_count": len(
                contract.answer_candidate_contract.forbidden_old_value_ids
            ),
            "language_requirement": contract.answer_candidate_contract.language_requirement,
            "candidate_reason": contract.answer_candidate_contract.candidate_reason,
        },
    }


def _build_answer_candidate_contract(
    *,
    enabled: bool,
    prompt_variant: str,
    active_ids: Sequence[str],
    likely_ids: Sequence[str],
    stale_ids: Sequence[str],
    deleted_ids: Sequence[str],
    items_by_id: Mapping[str, Mapping[str, object]],
) -> AnswerCandidateContract:
    if not enabled:
        return AnswerCandidateContract(
            enabled=False,
            current_truth_ids=(),
            current_truth_lines=(),
            must_include_term_count=0,
            forbidden_old_value_ids=(),
            language_requirement="",
            candidate_reason="disabled",
        )
    likely_set = set(likely_ids)
    current_ids = tuple(item_id for item_id in active_ids if item_id in likely_set)
    current_lines = tuple(
        summary
        for item_id in current_ids
        if item_id in items_by_id
        if (summary := str(items_by_id[item_id].get("summary") or "").strip())
    )
    return AnswerCandidateContract(
        enabled=True,
        current_truth_ids=current_ids,
        current_truth_lines=current_lines,
        must_include_term_count=len(current_lines),
        forbidden_old_value_ids=tuple(_dedupe((*stale_ids, *deleted_ids))),
        language_requirement="match_user_language",
        candidate_reason=(
            "safe_version_schema_first_shadow"
            if prompt_variant == "schema_first_shadow"
            else "safe_version_guided_retry_shadow"
        ),
    )


def _candidate_lanes(
    route_trace: Mapping[str, Any],
    baseline_items: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    raw_lanes = route_trace.get("candidates_by_lane")
    if isinstance(raw_lanes, Mapping):
        return {
            str(lane): [dict(item) for item in items if isinstance(item, Mapping)]
            for lane, items in raw_lanes.items()
            if isinstance(items, Sequence) and not isinstance(items, (str, bytes))
        }
    return {"semantic": [dict(item) for item in baseline_items]}


def _ids(items: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    return tuple(item_id for item in items if (item_id := _item_id(item)))


def _item_id(item: Mapping[str, Any]) -> str:
    return str(item.get("id") or item.get("memory_id") or "").strip()


def _item_by_id(
    candidates_by_lane: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, dict[str, object]]:
    items: dict[str, dict[str, object]] = {}
    for lane_items in candidates_by_lane.values():
        for item in lane_items:
            item_id = _item_id(item)
            if item_id:
                items[item_id] = dict(item)
    return items


def _tier_records(trace: Mapping[str, object]) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    raw_records = trace.get("candidate_risk_tiers", [])
    if not isinstance(raw_records, Sequence) or isinstance(raw_records, (str, bytes)):
        return records
    for record in raw_records:
        if not isinstance(record, Mapping):
            continue
        item_id = str(record.get("candidate_id") or "").strip()
        if item_id:
            records[item_id] = dict(record)
    return records


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(str(item) for item in value)


def _truthy(item: Mapping[str, Any], key: str) -> bool:
    value = item.get(key)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _dedupe(values: Sequence[object]) -> list[str]:
    result: list[str] = []
    for value in values:
        item_id = str(value or "").strip()
        if item_id and item_id not in result:
            result.append(item_id)
    return result


def _int_dict(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): int(count or 0) for key, count in value.items()}


def _evidence_lines(items: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    return tuple(
        summary
        for item in items
        if (summary := str(item.get("summary") or "").strip())
    )


def _replacement_ids(replacements: Sequence[Mapping[str, Any]]) -> set[str]:
    return {
        item_id
        for replacement in replacements
        for item_id in (
            str(replacement.get("old_item_id") or "").strip(),
            str(replacement.get("new_item_id") or "").strip(),
        )
        if item_id
    }


def _indent_lines(lines: Sequence[str]) -> list[str]:
    return ["  " + line for line in lines]


def _answerable_contract_completion_guidance(
    contract: SystemPathEvidenceContract,
) -> list[str]:
    if (
        contract.insufficient_evidence_fallback
        or not contract.answer_candidate_contract.current_truth_lines
    ):
        return []
    return [
        "  Because insufficient_evidence_fallback=false and current_truth is present, retrieval and governance for this turn are already complete.",
        "  When insufficient_evidence_fallback=false and current_truth or allowed_evidence answers the user, answer directly from this contract.",
        "  Do not restart recall, search, fetch, or read memory files such as MEMORY.md, HISTORY.md, or RECENT_CONTEXT.md.",
        "  Do not output pseudo tool calls, DSML markup, tool-call placeholders, or internal action plans as the final answer.",
        "  Do not answer with \"先查\", \"先翻\", or \"核实\" when the contract already contains the answer.",
    ]
