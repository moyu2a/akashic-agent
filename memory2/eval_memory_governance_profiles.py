from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


MEMORY_GOVERNANCE_PROFILE_ORDER: tuple[str, ...] = (
    "chain_tri_retrieval",
    "chain_tri_candidate_governance",
    "chain_tri_evidence_only",
    "chain_tri_answer_contract",
    "chain_tri_governed_answer_contract",
)


@dataclass(frozen=True)
class MemoryGovernanceProfileSpec:
    name: str
    candidate_governance: bool
    structured_evidence: bool
    answer_contract: bool
    production_safe_contract: bool
    answer_guidance: bool


_PROFILES: dict[str, MemoryGovernanceProfileSpec] = {
    "chain_tri_retrieval": MemoryGovernanceProfileSpec(
        name="chain_tri_retrieval",
        candidate_governance=False,
        structured_evidence=False,
        answer_contract=False,
        production_safe_contract=False,
        answer_guidance=False,
    ),
    "chain_tri_candidate_governance": MemoryGovernanceProfileSpec(
        name="chain_tri_candidate_governance",
        candidate_governance=True,
        structured_evidence=False,
        answer_contract=False,
        production_safe_contract=False,
        answer_guidance=False,
    ),
    "chain_tri_evidence_only": MemoryGovernanceProfileSpec(
        name="chain_tri_evidence_only",
        candidate_governance=True,
        structured_evidence=True,
        answer_contract=False,
        production_safe_contract=False,
        answer_guidance=False,
    ),
    "chain_tri_answer_contract": MemoryGovernanceProfileSpec(
        name="chain_tri_answer_contract",
        candidate_governance=False,
        structured_evidence=True,
        answer_contract=True,
        production_safe_contract=False,
        answer_guidance=True,
    ),
    "chain_tri_governed_answer_contract": MemoryGovernanceProfileSpec(
        name="chain_tri_governed_answer_contract",
        candidate_governance=True,
        structured_evidence=True,
        answer_contract=True,
        production_safe_contract=True,
        answer_guidance=True,
    ),
}


def get_memory_governance_profile(name: str) -> MemoryGovernanceProfileSpec:
    try:
        return _PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"unknown memory governance profile: {name}") from exc


def render_structured_evidence_only_block(
    *,
    allowed_evidence: Sequence[dict[str, object]],
    forbidden_evidence: Sequence[dict[str, object]],
    conflict_evidence: Sequence[dict[str, object]],
    version_boundaries: Sequence[dict[str, object]],
) -> str:
    sections = [
        ("Allowed Evidence", allowed_evidence),
        ("Forbidden Evidence", forbidden_evidence),
        ("Conflict Evidence", conflict_evidence),
        ("Version Boundaries", version_boundaries),
    ]
    lines = ["Evidence Structure: chain_tri_evidence_only"]
    for title, rows in sections:
        lines.extend(["", title])
        if not rows:
            lines.append("- none")
            continue
        for row in rows:
            lines.append("- " + _render_row(row))
    return "\n".join(lines)


def _render_row(row: dict[str, object]) -> str:
    preferred = ("id", "summary", "from", "to", "type", "status", "confidence")
    fields = [
        f"{key}={row[key]}"
        for key in preferred
        if key in row and str(row[key]).strip()
    ]
    if not fields:
        fields = [f"{key}={value}" for key, value in sorted(row.items())]
    return "; ".join(fields)
