"""Eval-only answer contract helpers for tri-retrieval diagnostics."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from memory2.eval_quantitative_cases import EvalCase
from memory2.eval_quantitative_uplift import _family_trace_for_case
from memory2.eval_public_long_memory import (
    build_public_evidence_render_config,
    render_public_long_memory_evidence,
)
from memory2.version_chain_experiments import build_version_chain_shadow_result


TRI_ANSWER_CONTRACT_PROFILE = "chain_tri_answer_contract"
GOVERNED_TRI_ANSWER_CONTRACT_PROFILE = "chain_tri_governed_answer_contract"


@dataclass(frozen=True)
class AnswerContract:
    profile_name: str
    diagnostic_eval_only: bool
    tri_ids: tuple[str, ...]
    must_use_ids: tuple[str, ...]
    allowed_evidence_ids: tuple[str, ...]
    forbidden_ids: tuple[str, ...]
    governance_dropped_ids: tuple[str, ...]
    required_terms: tuple[str, ...]
    required_term_groups: tuple[tuple[str, ...], ...]
    forbidden_terms: tuple[str, ...]
    evidence_summaries: tuple[tuple[str, str], ...]
    raw_prompt: str = ""
    raw_answer: str = ""


@dataclass(frozen=True)
class ProductionEvidenceContract:
    profile_name: str
    diagnostic_eval_only: bool
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
    required_terms: tuple[str, ...] = ()
    required_term_groups: tuple[tuple[str, ...], ...] = ()
    forbidden_terms: tuple[str, ...] = ()
    evidence_summaries: tuple[tuple[str, str], ...] = ()
    evidence_render_metadata: tuple[dict[str, object], ...] = ()
    public_long_memory_eval: bool = False
    raw_prompt: str = ""
    raw_answer: str = ""


@dataclass(frozen=True)
class VersionBoundaryInfo:
    active_version_ids: tuple[str, ...]
    stale_warning_ids: tuple[str, ...]
    conflict_warning_ids: tuple[str, ...]
    forbidden_boundary_ids: tuple[str, ...]
    rollback_candidate_ids: tuple[str, ...]
    conflict_chain_count: int
    stale_recalled_count: int
    superseded_recalled_count: int


def build_tri_answer_contract(case: EvalCase) -> AnswerContract:
    return _build_answer_contract(
        case,
        profile_name=TRI_ANSWER_CONTRACT_PROFILE,
        governed_evidence_ids=None,
    )


def build_governed_tri_answer_contract(
    case: EvalCase,
    governed_evidence_ids: object,
) -> AnswerContract:
    return _build_answer_contract(
        case,
        profile_name=GOVERNED_TRI_ANSWER_CONTRACT_PROFILE,
        governed_evidence_ids=governed_evidence_ids,
    )


def build_production_governed_tri_evidence_contract(
    case: EvalCase,
    governed_trace_info: object,
    *,
    profile_name: str = GOVERNED_TRI_ANSWER_CONTRACT_PROFILE,
    version_boundary_info: VersionBoundaryInfo | None = None,
) -> ProductionEvidenceContract:
    trace_info = (
        dict(governed_trace_info) if isinstance(governed_trace_info, Mapping) else {}
    )
    trace = trace_info.get("trace", {})
    trace = dict(trace) if isinstance(trace, Mapping) else {}
    allowed_ids = _string_tuple(trace_info.get("ids", ()))
    tier_records = _tier_records_by_id(trace.get("candidate_risk_tiers", ()))
    by_id = _memory_items_by_id(case)

    downgrade_ids = _ids_with_tier(allowed_ids, tier_records, "downgrade")
    requires_review_ids = _ids_with_tier(
        allowed_ids,
        tier_records,
        "requires_review",
    )
    conflict_warning_ids = _ids_with_risk(
        allowed_ids,
        tier_records,
        "conflict_candidate",
    )
    insufficient_evidence_ids = tuple(
        item_id
        for item_id in allowed_ids
        if _record_has_risk(tier_records.get(item_id, {}), "insufficient_evidence")
        or _item_truthy(by_id.get(item_id, {}), "insufficient_evidence")
    )
    deleted_ids = tuple(
        item_id
        for item_id, record in tier_records.items()
        if str(record.get("tier") or "") == "delete"
    )
    forbidden_boundary_ids = tuple(
        item_id
        for item_id in deleted_ids
        if _record_has_risk(tier_records.get(item_id, {}), "forbidden_candidate")
        or _item_truthy(by_id.get(item_id, {}), "forbidden")
        or _item_truthy(by_id.get(item_id, {}), "forbidden_candidate")
    )
    stale_warning_ids = tuple(
        item_id
        for item_id in deleted_ids
        if _record_has_risk(tier_records.get(item_id, {}), "superseded_candidate")
        or str(by_id.get(item_id, {}).get("status") or "").lower() == "superseded"
    )
    active_version_ids = tuple(
        item_id
        for item_id in allowed_ids
        if str(by_id.get(item_id, {}).get("status") or "active").lower() == "active"
    )
    version_active_ids = (
        version_boundary_info.active_version_ids if version_boundary_info else ()
    )
    version_stale_ids = (
        version_boundary_info.stale_warning_ids if version_boundary_info else ()
    )
    version_conflict_ids = (
        version_boundary_info.conflict_warning_ids if version_boundary_info else ()
    )
    version_forbidden_ids = (
        version_boundary_info.forbidden_boundary_ids if version_boundary_info else ()
    )
    merged_conflict_warning_ids = _dedupe_ids(
        (*conflict_warning_ids, *version_conflict_ids)
    )
    merged_stale_warning_ids = _dedupe_ids((*stale_warning_ids, *version_stale_ids))
    merged_forbidden_boundary_ids = tuple(
        item_id
        for item_id in _dedupe_ids((*forbidden_boundary_ids, *version_forbidden_ids))
        if item_id not in allowed_ids
    )
    active_version_source_ids = (
        version_active_ids if version_boundary_info else active_version_ids
    )
    merged_active_version_ids = tuple(
        item_id
        for item_id in _dedupe_ids(active_version_source_ids)
        if item_id in allowed_ids and item_id not in merged_forbidden_boundary_ids
    )
    likely_relevant_ids = tuple(
        item_id for item_id in allowed_ids if item_id not in requires_review_ids
    )
    evidence_summaries, evidence_render_metadata = _summaries_for_ids(
        case,
        allowed_ids,
    )
    return ProductionEvidenceContract(
        profile_name=profile_name,
        diagnostic_eval_only=True,
        production_safe=True,
        uses_fixture_answer_expectations=False,
        candidate_governance_mode=str(trace.get("candidate_governance_mode") or "tiered"),
        allowed_evidence=allowed_ids,
        likely_relevant_evidence=likely_relevant_ids,
        stale_warning=merged_stale_warning_ids,
        conflict_warning=merged_conflict_warning_ids,
        active_version=merged_active_version_ids,
        forbidden_boundary=merged_forbidden_boundary_ids,
        allowed_evidence_ids=allowed_ids,
        likely_relevant_evidence_ids=likely_relevant_ids,
        downgrade_ids=downgrade_ids,
        requires_review_ids=requires_review_ids,
        stale_warning_ids=merged_stale_warning_ids,
        conflict_warning_ids=merged_conflict_warning_ids,
        active_version_ids=merged_active_version_ids,
        insufficient_evidence_ids=insufficient_evidence_ids,
        insufficient_evidence_fallback=not allowed_ids
        or bool(insufficient_evidence_ids),
        forbidden_boundary_ids=merged_forbidden_boundary_ids,
        deleted_evidence_ids=deleted_ids,
        evidence_summaries=evidence_summaries,
        evidence_render_metadata=evidence_render_metadata,
        public_long_memory_eval=_is_public_long_memory_case(case),
    )


def build_version_boundary_info(
    case: EvalCase,
    governed_trace_info: object,
) -> VersionBoundaryInfo:
    trace_info = (
        dict(governed_trace_info) if isinstance(governed_trace_info, Mapping) else {}
    )
    governed_ids = set(_string_tuple(trace_info.get("ids", ())))
    memory_items = [
        dict(item)
        for item in case.setup.get("memory_items", ())
        if isinstance(item, Mapping)
    ]
    replacements = [
        dict(item)
        for item in case.setup.get("memory_replacements", ())
        if isinstance(item, Mapping)
    ]
    recalled_items = [
        item
        for item in memory_items
        if str(item.get("id") or item.get("memory_id") or "") in governed_ids
    ]
    result = build_version_chain_shadow_result(
        memory_items=memory_items,
        replacements=replacements,
        recalled_items=recalled_items,
    )
    experimental = result.experimental_result
    metrics = result.metrics
    active_ids = tuple(
        item_id
        for item_id in _string_tuple(experimental.get("active_leaf_ids", ()))
        if item_id in governed_ids
    )
    stale_ids = _string_tuple(experimental.get("stale_recalled_ids", ()))
    governed_predecessor_ids = {
        str(replacement.get("old_item_id") or "")
        for replacement in replacements
        if str(replacement.get("new_item_id") or "") in set(active_ids)
    }
    rollback_ids = tuple(
        item_id
        for item_id in _string_tuple(experimental.get("rollback_candidate_ids", ()))
        if item_id in governed_predecessor_ids
        and item_id not in governed_ids
        and item_id not in active_ids
    )
    conflict_ids = _conflict_warning_ids_from_shadow_result(
        experimental,
        governed_ids,
    )
    forbidden_ids = tuple(
        item_id
        for item_id in _dedupe_ids(rollback_ids)
        if item_id not in governed_ids and item_id not in active_ids
    )
    return VersionBoundaryInfo(
        active_version_ids=active_ids,
        stale_warning_ids=stale_ids,
        conflict_warning_ids=conflict_ids,
        forbidden_boundary_ids=forbidden_ids,
        rollback_candidate_ids=rollback_ids,
        conflict_chain_count=int(metrics.get("conflict_chain_count", 0) or 0),
        stale_recalled_count=int(metrics.get("stale_recalled_count", 0) or 0),
        superseded_recalled_count=int(metrics.get("superseded_recalled_count", 0) or 0),
    )


def _build_answer_contract(
    case: EvalCase,
    *,
    profile_name: str,
    governed_evidence_ids: object | None,
) -> AnswerContract:
    tri_ids = _ids_from_trace(case, "tri_retrieval", "fused_ids")
    expected_ids = _string_tuple(case.expectations.get("should_recall_ids", ()))
    should_not_ids = set(_string_tuple(case.expectations.get("should_not_recall_ids", ())))
    if governed_evidence_ids is None:
        allowed_ids = tuple(item_id for item_id in tri_ids if item_id not in should_not_ids)
    else:
        governed_ids = _string_tuple(governed_evidence_ids)
        tri_set = set(tri_ids)
        allowed_ids = tuple(
            item_id
            for item_id in governed_ids
            if item_id in tri_set and item_id not in should_not_ids
        )
    allowed_set = set(allowed_ids)
    forbidden_ids = tuple(item_id for item_id in tri_ids if item_id in should_not_ids)
    governance_dropped_ids = tuple(
        item_id
        for item_id in tri_ids
        if item_id not in allowed_set and item_id not in should_not_ids
    )
    answer_expectations = case.expectations.get("answer_expectations") or {}
    summaries, _metadata = _summaries_for_ids(case, allowed_ids)
    return AnswerContract(
        profile_name=profile_name,
        diagnostic_eval_only=True,
        tri_ids=tri_ids,
        must_use_ids=tuple(item_id for item_id in expected_ids if item_id in allowed_ids),
        allowed_evidence_ids=allowed_ids,
        forbidden_ids=forbidden_ids,
        governance_dropped_ids=governance_dropped_ids,
        required_terms=_string_tuple(answer_expectations.get("expected_answer_contains", ())),
        required_term_groups=_term_groups(
            answer_expectations.get("expected_answer_contains_any", ())
        ),
        forbidden_terms=_string_tuple(
            answer_expectations.get("forbidden_answer_contains", ())
        ),
        evidence_summaries=summaries,
    )


def tri_answer_contract_evidence_ids(case: EvalCase) -> tuple[str, ...]:
    return build_tri_answer_contract(case).allowed_evidence_ids


def tri_governed_answer_contract_evidence_ids(
    case: EvalCase,
    governed_evidence_ids: object,
) -> tuple[str, ...]:
    return build_governed_tri_answer_contract(
        case,
        governed_evidence_ids,
    ).allowed_evidence_ids


def render_answer_contract_block(contract: AnswerContract) -> str:
    lines = [
        f"Answer Contract: {contract.profile_name}",
        "diagnostic_eval_only=true",
        "请只根据 allowed_evidence 回答；不要使用 forbidden_memory_ids 中的记忆。",
        "Answer in the same language as the user question unless the user explicitly requests another language.",
        "如果 required_terms 或 required_term_groups 与证据一致，请在回答中保留这些关键术语。",
        "如果证据不足以支持 required_terms，请说明无法确认，不要补写 forbidden_terms。",
        "must_use_memory_ids: " + ", ".join(contract.must_use_ids),
        "forbidden_memory_ids: " + ", ".join(contract.forbidden_ids),
        "governance_dropped_memory_ids: " + ", ".join(contract.governance_dropped_ids),
        "required_terms: " + ", ".join(contract.required_terms),
        "required_term_groups: " + _format_groups(contract.required_term_groups),
        "forbidden_terms: " + ", ".join(contract.forbidden_terms),
        "allowed_evidence:",
    ]
    for item_id, summary in contract.evidence_summaries:
        lines.append(f"- memory_id={item_id}; summary={summary}")
    return "\n".join(lines)


def render_production_evidence_contract_block(
    contract: ProductionEvidenceContract,
) -> str:
    lines = [
        f"Evidence Contract: {contract.profile_name}",
        "diagnostic_eval_only=true",
        "production_safe=true",
        "请只根据 allowed_evidence 回答；如果 insufficient_evidence_fallback=true，请说明证据不足。",
        "Answer in the same language as the user question unless the user explicitly requests another language.",
        "如果存在 forbidden boundary，表示有旧版本、越界或禁止使用的记忆边界；不要复述或引用这些边界内容。",
        "allowed_evidence: " + ", ".join(contract.allowed_evidence),
        "likely_relevant_evidence: " + ", ".join(contract.likely_relevant_evidence),
        "stale_warning: " + ", ".join(contract.stale_warning),
        "conflict_warning: " + ", ".join(contract.conflict_warning),
        "active_version: " + ", ".join(contract.active_version),
        "forbidden_boundary_count: " + str(len(contract.forbidden_boundary_ids)),
        "deleted_evidence_count: " + str(len(contract.deleted_evidence_ids)),
        "forbidden_boundary_instruction: superseded evidence exists; use only allowed_evidence and active_version evidence.",
        "allowed_evidence_ids: " + ", ".join(contract.allowed_evidence_ids),
        "likely_relevant_evidence_ids: "
        + ", ".join(contract.likely_relevant_evidence_ids),
        "downgrade_ids: " + ", ".join(contract.downgrade_ids),
        "requires_review_ids: " + ", ".join(contract.requires_review_ids),
        "stale_warning_ids: " + ", ".join(contract.stale_warning_ids),
        "conflict_warning_ids: " + ", ".join(contract.conflict_warning_ids),
        "active_version_ids: " + ", ".join(contract.active_version_ids),
        "insufficient_evidence_ids: "
        + ", ".join(contract.insufficient_evidence_ids),
        "insufficient_evidence_fallback: "
        + ("true" if contract.insufficient_evidence_fallback else "false"),
        "allowed_evidence:",
    ]
    if contract.public_long_memory_eval:
        lines.append(
            "Public long-memory benchmark constraint: no tools are executed in this evaluation; do not output tool_call, function calls, or XML; answer directly from allowed_evidence."
        )
    for item_id, summary in contract.evidence_summaries:
        lines.append(f"- memory_id={item_id}; summary={summary}")
    return "\n".join(lines)


def _summaries_for_ids(
    case: EvalCase,
    ids: tuple[str, ...],
) -> tuple[tuple[tuple[str, str], ...], tuple[dict[str, object], ...]]:
    by_id = {
        str(item.get("id") or item.get("memory_id") or ""): item
        for item in case.setup.get("memory_items", ())
        if isinstance(item, dict)
    }
    rows: list[tuple[str, str]] = []
    metadata_rows: list[dict[str, object]] = []
    render_config = _public_evidence_render_config_from_case(case)
    for item_id in ids:
        item = by_id.get(item_id) or {}
        summary = str(item.get("summary") or item.get("content") or "")
        if render_config is not None and _is_public_long_memory_item(item):
            rendered, metadata = render_public_long_memory_evidence(item, render_config)
            rows.append((item_id, rendered))
            metadata_rows.append({"memory_id": item_id, **metadata})
        else:
            rows.append((item_id, _compact(summary)))
    return tuple(rows), tuple(metadata_rows)


def _public_evidence_render_config_from_case(case: EvalCase) -> object | None:
    raw = case.setup.get("public_long_memory_evidence_render")
    if not isinstance(raw, Mapping):
        return None
    return build_public_evidence_render_config(
        mode=str(raw.get("mode") or "answer_window"),  # type: ignore[arg-type]
        long_evidence_token_limit=int(raw.get("long_evidence_token_limit") or 3000),
        reserved_prompt_token_budget=int(raw.get("reserved_prompt_token_budget") or 2000),
        model_context_window=int(raw.get("model_context_window") or 8192),
        answer_window_turns=int(raw.get("answer_window_turns") or 2),
    )


def _is_public_long_memory_case(case: EvalCase) -> bool:
    return str(case.setup.get("measurement_family") or "") == "public_long_memory"


def _is_public_long_memory_item(item: Mapping[str, Any]) -> bool:
    extra = item.get("extra_json")
    return (
        str(item.get("memory_type") or "") == "public_long_memory_history"
        or (isinstance(extra, Mapping) and extra.get("benchmark") == "longmemeval")
    )


def _memory_items_by_id(case: EvalCase) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("id") or item.get("memory_id") or ""): dict(item)
        for item in case.setup.get("memory_items", ())
        if isinstance(item, Mapping)
    }


def _tier_records_by_id(records: object) -> dict[str, dict[str, Any]]:
    if not isinstance(records, (list, tuple)):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, Mapping):
            continue
        candidate_id = str(record.get("candidate_id") or "")
        if candidate_id:
            result[candidate_id] = dict(record)
    return result


def _ids_with_tier(
    ids: tuple[str, ...],
    records: dict[str, dict[str, Any]],
    tier: str,
) -> tuple[str, ...]:
    return tuple(
        item_id
        for item_id in ids
        if str(records.get(item_id, {}).get("tier") or "allow") == tier
    )


def _ids_with_risk(
    ids: tuple[str, ...],
    records: dict[str, dict[str, Any]],
    risk: str,
) -> tuple[str, ...]:
    return tuple(
        item_id for item_id in ids if _record_has_risk(records.get(item_id, {}), risk)
    )


def _record_has_risk(record: Mapping[str, Any], risk: str) -> bool:
    risks = record.get("risks", ())
    return isinstance(risks, (list, tuple, set)) and risk in {
        str(item) for item in risks
    }


def _item_truthy(item: Mapping[str, Any], key: str) -> bool:
    return item.get(key) is True


def _ids_from_trace(case: EvalCase, family_name: str, key: str) -> tuple[str, ...]:
    trace = _family_trace_for_case(case, family_name)
    if trace is None:
        return ()
    raw_ids = trace.experimental_result.get(key, [])
    return _string_tuple(raw_ids)


def _string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value else ()
    if not isinstance(value, (list, tuple, set)):
        return ()
    return tuple(str(item) for item in value if str(item))


def _conflict_warning_ids_from_shadow_result(
    experimental: Mapping[str, object],
    governed_ids: set[str],
) -> tuple[str, ...]:
    active_ids = set(_string_tuple(experimental.get("active_leaf_ids", ())))
    chains = experimental.get("chains", ())
    if not isinstance(chains, (list, tuple)):
        return ()
    result: list[str] = []
    for chain in chains:
        chain_ids = _string_tuple(chain)
        if not (set(chain_ids) & governed_ids):
            continue
        active_in_chain = [item_id for item_id in chain_ids if item_id in active_ids]
        if len(active_in_chain) <= 1:
            continue
        result.extend(item_id for item_id in active_in_chain if item_id not in governed_ids)
    return _dedupe_ids(tuple(result))


def _dedupe_ids(ids: tuple[str, ...]) -> tuple[str, ...]:
    result: list[str] = []
    for item_id in ids:
        if item_id and item_id not in result:
            result.append(item_id)
    return tuple(result)


def _term_groups(value: object) -> tuple[tuple[str, ...], ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    groups: list[tuple[str, ...]] = []
    for group in value:
        terms = _string_tuple(group)
        if terms:
            groups.append(terms)
    return tuple(groups)


def _format_groups(groups: tuple[tuple[str, ...], ...]) -> str:
    return " | ".join("(" + ", ".join(group) + ")" for group in groups)


def _compact(text: str, *, limit: int = 180) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."
