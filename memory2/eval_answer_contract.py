"""Eval-only answer contract helpers for tri-retrieval diagnostics."""

from __future__ import annotations

from dataclasses import dataclass

from memory2.eval_quantitative_cases import EvalCase
from memory2.eval_quantitative_uplift import _family_trace_for_case


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
    summaries = _summaries_for_ids(case, allowed_ids)
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
        "如果 required_terms 或 required_term_groups 与证据一致，请在中文回答中保留这些关键术语。",
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


def _summaries_for_ids(case: EvalCase, ids: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    by_id = {
        str(item.get("id") or item.get("memory_id") or ""): item
        for item in case.setup.get("memory_items", ())
        if isinstance(item, dict)
    }
    rows: list[tuple[str, str]] = []
    for item_id in ids:
        item = by_id.get(item_id) or {}
        summary = str(item.get("summary") or item.get("content") or "")
        rows.append((item_id, _compact(summary)))
    return tuple(rows)


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
