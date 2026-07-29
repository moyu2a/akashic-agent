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


@dataclass(frozen=True)
class SystemPathEvidenceContract:
    profile_name: str
    production_safe: bool
    uses_fixture_answer_expectations: bool
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
) -> SystemPathSafeVersionResult:
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
    contract = SystemPathEvidenceContract(
        profile_name=SYSTEM_SAFE_VERSION_PROFILE,
        production_safe=True,
        uses_fixture_answer_expectations=False,
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
    )
    return SystemPathSafeVersionResult(
        contract=contract,
        text_block=render_system_path_evidence_contract_block(contract),
        accepted_items=tuple(dict(item) for item in accepted),
        trace={"safe_version_governed": system_path_contract_to_dict(contract)},
    )


def render_system_path_evidence_contract_block(
    contract: SystemPathEvidenceContract,
) -> str:
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
    return "\n".join(lines)


def system_path_contract_to_dict(contract: SystemPathEvidenceContract) -> dict[str, object]:
    return {
        "profile_name": contract.profile_name,
        "production_safe": contract.production_safe,
        "production_safe_evidence_contract": contract.production_safe,
        "uses_fixture_answer_expectations": contract.uses_fixture_answer_expectations,
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
    }


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
