from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal, Protocol

from agent.policies.tool_budget import TaskIntent
from agent.policies.tool_ledger import ToolCallLedger, ToolCallRecord

EvidenceLevel = Literal[
    "fetched_text",
    "retrieval_snippet",
    "soft_stopped_candidate",
    "title_metadata",
    "memory_summary",
    "message_excerpt",
    "code_excerpt",
    "inferred",
]


@dataclass(frozen=True)
class EvidenceItem:
    id: str
    source_tool: str
    evidence_level: EvidenceLevel
    source_ref: str = ""
    citation: str = ""
    text_preview: str = ""
    chunk_id: str = ""
    tool_call_index: int | None = None
    allowed_labels: tuple[str, ...] = ()
    forbidden_labels: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskEvidenceRequirement:
    task_type: str
    required_evidence_levels: tuple[EvidenceLevel, ...] = ()
    min_retrieval_hits: int = 0
    min_fetched_items: int = 0
    required_citations: bool = False
    coverage_mode: Literal[
        "main_question",
        "all_requested_items",
        "best_effort",
    ] = "best_effort"
    allow_partial_answer: bool = True


@dataclass(frozen=True)
class EvidenceSufficiency:
    tool_stop_allowed: bool
    answer_ready: bool
    reason: str
    covered_requirements: tuple[str, ...] = ()
    missing_requirements: tuple[str, ...] = ()
    required_next_actions: tuple[str, ...] = ()


@dataclass(frozen=True)
class AnswerConstraint:
    kind: Literal[
        "allowed_label",
        "forbidden_label",
        "must_qualify",
        "citation_required",
        "missing_evidence",
    ]
    target: str
    message: str
    severity: Literal["info", "warn", "block"] = "warn"


@dataclass(frozen=True)
class EvidenceAssessment:
    requirement: TaskEvidenceRequirement
    items: tuple[EvidenceItem, ...]
    sufficiency: EvidenceSufficiency
    constraints: tuple[AnswerConstraint, ...]
    risk_flags: tuple[str, ...] = ()
    model_hint: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)


class EvidencePolicy(Protocol):
    name: str

    def extract_items(
        self,
        *,
        ledger: ToolCallLedger,
        boundary_decisions: Sequence[Mapping[str, object]],
    ) -> tuple[EvidenceItem, ...]:
        ...


class DocumentRagEvidencePolicy:
    name = "DocumentRagEvidencePolicy"

    def extract_items(
        self,
        *,
        ledger: ToolCallLedger,
        boundary_decisions: Sequence[Mapping[str, object]],
    ) -> tuple[EvidenceItem, ...]:
        items: list[EvidenceItem] = []
        for record in ledger.records:
            if record.tool_name == "search_docs" and record.result_ok:
                items.extend(_search_doc_items(record))
            if record.tool_name == "fetch_doc_chunk" and record.result_ok:
                items.extend(_fetch_doc_items(record))

        fetched = {
            item.chunk_id
            for item in items
            if item.evidence_level == "fetched_text" and item.chunk_id
        }
        for decision in boundary_decisions:
            if (
                decision.get("tool") == "fetch_doc_chunk"
                and decision.get("action") == "soft_stop"
                and decision.get("execute") is False
            ):
                chunk_id = _decision_chunk_id(decision)
                if chunk_id and chunk_id in fetched:
                    continue
                items.append(
                    EvidenceItem(
                        id=f"soft_stop:{chunk_id or len(items)}",
                        source_tool="fetch_doc_chunk",
                        evidence_level="soft_stopped_candidate",
                        chunk_id=chunk_id,
                        forbidden_labels=("原文展开", "已读取", "已展开"),
                        metadata={"reason": str(decision.get("reason") or "")},
                    )
                )
        return tuple(items)


class EvidenceContractManager:
    def __init__(self, policies: Sequence[EvidencePolicy] | None = None) -> None:
        self._policies = tuple(policies or (DocumentRagEvidencePolicy(),))

    def assess(
        self,
        *,
        user_text: str,
        intent: TaskIntent,
        ledger: ToolCallLedger,
        boundary_decisions: Sequence[Mapping[str, object]],
    ) -> EvidenceAssessment:
        requirement = infer_requirement(user_text=user_text, intent=intent)
        items: list[EvidenceItem] = []
        for policy in self._policies:
            items.extend(
                policy.extract_items(
                    ledger=ledger,
                    boundary_decisions=boundary_decisions,
                )
            )
        item_tuple = tuple(items)
        sufficiency = evaluate_sufficiency(requirement, item_tuple)
        constraints = build_answer_constraints(requirement, item_tuple)
        risk_flags = _risk_flags(item_tuple)
        model_hint = render_model_hint(
            requirement=requirement,
            items=item_tuple,
            sufficiency=sufficiency,
            constraints=constraints,
        )
        return EvidenceAssessment(
            requirement=requirement,
            items=item_tuple,
            sufficiency=sufficiency,
            constraints=constraints,
            risk_flags=risk_flags,
            model_hint=model_hint,
            metadata={
                "item_count": len(item_tuple),
                "fetched_text_count": _count_level(item_tuple, "fetched_text"),
                "retrieval_snippet_count": _count_level(
                    item_tuple,
                    "retrieval_snippet",
                ),
                "soft_stopped_candidate_count": _count_level(
                    item_tuple,
                    "soft_stopped_candidate",
                ),
            },
        )


def infer_requirement(
    *,
    user_text: str,
    intent: TaskIntent,
) -> TaskEvidenceRequirement:
    text = user_text or ""
    wants_original = any(term in text for term in ("原文", "展开", "chunk"))
    wants_citation = any(term in text for term in ("引用", "citation", "证据", "原文"))
    if intent == "doc_qa_with_evidence":
        return TaskEvidenceRequirement(
            task_type=intent,
            required_evidence_levels=(
                "retrieval_snippet",
                "fetched_text",
            ),
            min_retrieval_hits=1,
            min_fetched_items=1 if wants_original else 0,
            required_citations=wants_citation,
            coverage_mode="main_question",
            allow_partial_answer=True,
        )
    if intent == "doc_qa_simple":
        return TaskEvidenceRequirement(
            task_type=intent,
            required_evidence_levels=("retrieval_snippet",),
            min_retrieval_hits=1,
            required_citations=wants_citation,
            coverage_mode="main_question",
            allow_partial_answer=True,
        )
    return TaskEvidenceRequirement(task_type=str(intent))


def evaluate_sufficiency(
    requirement: TaskEvidenceRequirement,
    items: Sequence[EvidenceItem],
) -> EvidenceSufficiency:
    retrieval_count = _count_level(items, "retrieval_snippet")
    fetched_count = _count_level(items, "fetched_text")
    has_citation = any(item.citation for item in items)
    has_fetched_citation = any(
        item.evidence_level == "fetched_text" and item.citation for item in items
    )
    missing: list[str] = []
    covered: list[str] = []

    if retrieval_count < requirement.min_retrieval_hits:
        missing.append("retrieval_hit")
    elif requirement.min_retrieval_hits:
        covered.append("retrieval_hit")

    if fetched_count < requirement.min_fetched_items:
        missing.append("fetched_text")
    elif requirement.min_fetched_items:
        covered.append("fetched_text")

    if requirement.required_citations and not has_citation:
        missing.append("citation")
    elif requirement.required_citations:
        covered.append("citation")

    if (
        requirement.required_citations
        and requirement.min_fetched_items > 0
        and not has_fetched_citation
    ):
        missing.append("fetched_text_citation")
    elif requirement.required_citations and requirement.min_fetched_items > 0:
        covered.append("fetched_text_citation")

    tool_stop_allowed = not missing
    answer_ready = tool_stop_allowed or requirement.allow_partial_answer
    return EvidenceSufficiency(
        tool_stop_allowed=tool_stop_allowed,
        answer_ready=answer_ready,
        reason="requirements_satisfied" if tool_stop_allowed else "missing_evidence",
        covered_requirements=tuple(covered),
        missing_requirements=tuple(missing),
        required_next_actions=tuple(f"collect_{item}" for item in missing),
    )


def build_answer_constraints(
    requirement: TaskEvidenceRequirement,
    items: Sequence[EvidenceItem],
) -> tuple[AnswerConstraint, ...]:
    constraints: list[AnswerConstraint] = []
    for item in items:
        if item.evidence_level == "fetched_text":
            constraints.append(
                AnswerConstraint(
                    kind="allowed_label",
                    target=item.id,
                    message=(
                        "This evidence may be described as fetched original text."
                    ),
                    severity="info",
                )
            )
        elif item.evidence_level == "retrieval_snippet":
            constraints.append(
                AnswerConstraint(
                    kind="must_qualify",
                    target=item.id,
                    message=(
                        "This is a search hit summary. Do not call it original "
                        "expanded text."
                    ),
                )
            )
        elif item.evidence_level == "soft_stopped_candidate":
            constraints.append(
                AnswerConstraint(
                    kind="forbidden_label",
                    target=item.id,
                    message=(
                        "This chunk request was soft-stopped. Do not say it was "
                        "fetched or expanded."
                    ),
                )
            )

    if requirement.required_citations:
        constraints.append(
            AnswerConstraint(
                kind="citation_required",
                target="doc_claims",
                message="Document factual claims must include available citations.",
            )
        )
    return tuple(constraints)


def render_model_hint(
    *,
    requirement: TaskEvidenceRequirement,
    items: Sequence[EvidenceItem],
    sufficiency: EvidenceSufficiency,
    constraints: Sequence[AnswerConstraint],
) -> str:
    fetched = [item for item in items if item.evidence_level == "fetched_text"]
    snippets = [item for item in items if item.evidence_level == "retrieval_snippet"]
    stopped = [
        item for item in items if item.evidence_level == "soft_stopped_candidate"
    ]
    lines = [
        "Evidence contract for this answer:",
        "",
        f"Task evidence status: {sufficiency.reason}.",
        f"Answer ready: {str(sufficiency.answer_ready).lower()}.",
        f"Tool stop allowed: {str(sufficiency.tool_stop_allowed).lower()}.",
        "",
        "Fetched original text:",
    ]
    if fetched:
        for item in fetched[:8]:
            lines.append(f"- {_item_label(item)}")
    else:
        lines.append("- none")

    lines.extend(["", "Retrieval summaries only:"])
    if snippets:
        for item in snippets[:8]:
            lines.append(f"- {_item_label(item)}")
    else:
        lines.append("- none")

    lines.extend(["", "Soft-stopped candidates:"])
    if stopped:
        for item in stopped[:8]:
            lines.append(f"- {_item_label(item)}")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "Answer rules:",
            "- Only successful fetch_doc_chunk results may be described as original text or 原文展开.",
            "- search_docs hits are retrieval summaries, not expanded chunks.",
            "- Do not describe soft-stopped chunks as expanded original text.",
            "- If evidence is only a summary, use weaker wording and say it is a 检索命中摘要.",
        ]
    )
    if constraints:
        lines.append("- Document factual claims must include available citations when present.")
    if sufficiency.missing_requirements:
        lines.append(
            "- Missing evidence: "
            + ", ".join(sufficiency.missing_requirements)
            + ". State this limitation if you answer."
        )
    return "\n".join(lines)


def assessment_trace(assessment: EvidenceAssessment | None) -> dict[str, object] | None:
    if assessment is None:
        return None
    return {
        "sufficiency": {
            "tool_stop_allowed": assessment.sufficiency.tool_stop_allowed,
            "answer_ready": assessment.sufficiency.answer_ready,
            "reason": assessment.sufficiency.reason,
            "covered_requirements": list(
                assessment.sufficiency.covered_requirements
            ),
            "missing_requirements": list(
                assessment.sufficiency.missing_requirements
            ),
            "required_next_actions": list(
                assessment.sufficiency.required_next_actions
            ),
        },
        "metadata": dict(assessment.metadata),
        "items": [
            {
                "source_tool": item.source_tool,
                "evidence_level": item.evidence_level,
                "source_ref": item.source_ref,
                "citation": item.citation,
                "chunk_id": item.chunk_id,
            }
            for item in assessment.items
        ],
        "constraints": [
            {
                "kind": constraint.kind,
                "target": constraint.target,
                "severity": constraint.severity,
            }
            for constraint in assessment.constraints
        ],
        "risk_flags": list(assessment.risk_flags),
    }


def _search_doc_items(record: ToolCallRecord) -> tuple[EvidenceItem, ...]:
    payload = _loads_record_payload(record)
    hits = payload.get("hits") if payload else None
    items: list[EvidenceItem] = []
    if isinstance(hits, list):
        for index, hit in enumerate(hits):
            if not isinstance(hit, dict):
                continue
            chunk_id = str(hit.get("chunk_id") or "")
            citation = str(hit.get("citation") or "")
            source_ref = str(hit.get("source_path") or hit.get("heading_path") or "")
            text = str(hit.get("snippet") or "")
            items.append(
                EvidenceItem(
                    id=f"search_docs:{chunk_id or record.call_index}:{index}",
                    source_tool="search_docs",
                    evidence_level="retrieval_snippet",
                    source_ref=source_ref,
                    citation=citation,
                    text_preview=text[:240],
                    chunk_id=chunk_id,
                    tool_call_index=record.call_index,
                    allowed_labels=("检索命中", "检索摘要", "snippet"),
                    forbidden_labels=("原文展开", "完整原文", "已展开 chunk"),
                )
            )
    if items:
        return tuple(items)

    return tuple(
        EvidenceItem(
            id=f"search_docs:{chunk_id or record.call_index}:{index}",
            source_tool="search_docs",
            evidence_level="retrieval_snippet",
            citation=record.citation_refs[index] if index < len(record.citation_refs) else "",
            chunk_id=chunk_id,
            tool_call_index=record.call_index,
            allowed_labels=("检索命中", "检索摘要", "snippet"),
            forbidden_labels=("原文展开", "完整原文", "已展开 chunk"),
        )
        for index, chunk_id in enumerate(record.chunk_keys)
    )


def _fetch_doc_items(record: ToolCallRecord) -> tuple[EvidenceItem, ...]:
    payload = _loads_record_payload(record)
    chunk = payload.get("chunk") if payload else None
    if isinstance(chunk, dict):
        chunk_id = str(chunk.get("chunk_id") or "")
        citation = str(chunk.get("citation") or "")
        source_ref = str(
            chunk.get("source_path") or chunk.get("heading_path") or ""
        )
        text = str(chunk.get("content") or chunk.get("text") or "")
        return (
            EvidenceItem(
                id=f"fetch_doc_chunk:{chunk_id or record.call_index}",
                source_tool="fetch_doc_chunk",
                evidence_level="fetched_text",
                source_ref=source_ref,
                citation=citation,
                text_preview=text[:240],
                chunk_id=chunk_id,
                tool_call_index=record.call_index,
                allowed_labels=("原文", "原文展开", "chunk 原文"),
            ),
        )

    return tuple(
        EvidenceItem(
            id=f"fetch_doc_chunk:{chunk_id or record.call_index}:{index}",
            source_tool="fetch_doc_chunk",
            evidence_level="fetched_text",
            citation=record.citation_refs[index] if index < len(record.citation_refs) else "",
            chunk_id=chunk_id,
            tool_call_index=record.call_index,
            allowed_labels=("原文", "原文展开", "chunk 原文"),
        )
        for index, chunk_id in enumerate(record.chunk_keys)
    )


def _loads_dict(text: str) -> dict[str, object]:
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _loads_record_payload(record: ToolCallRecord) -> dict[str, object]:
    return _loads_dict(record.result_text) or _loads_dict(record.result_summary)


def _decision_chunk_id(decision: Mapping[str, object]) -> str:
    arguments = decision.get("arguments")
    if isinstance(arguments, Mapping):
        value = arguments.get("chunk_id")
        if isinstance(value, str):
            return value
    metadata = decision.get("metadata")
    if isinstance(metadata, Mapping):
        value = metadata.get("chunk_id")
        if isinstance(value, str):
            return value
    return ""


def _count_level(items: Sequence[EvidenceItem], level: EvidenceLevel) -> int:
    return sum(1 for item in items if item.evidence_level == level)


def _risk_flags(items: Sequence[EvidenceItem]) -> tuple[str, ...]:
    flags: list[str] = []
    if any(item.evidence_level == "soft_stopped_candidate" for item in items):
        flags.append("has_soft_stopped_candidates")
    if any(item.evidence_level == "retrieval_snippet" for item in items):
        flags.append("has_retrieval_snippets")
    return tuple(flags)


def _item_label(item: EvidenceItem) -> str:
    parts = []
    if item.chunk_id:
        parts.append(f"chunk_id={item.chunk_id}")
    if item.citation:
        parts.append(f"citation={item.citation}")
    if item.source_ref:
        parts.append(f"source={item.source_ref}")
    return ", ".join(parts) if parts else item.id
