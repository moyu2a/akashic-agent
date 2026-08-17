from __future__ import annotations

from memory2.eval_memory_governance_audit import (
    semantic_audit_release_decision,
    select_semantic_audit_sample,
)
from memory2.eval_memory_governance_generator import generate_memory_governance_dataset


def test_semantic_audit_sample_is_deterministic() -> None:
    cases = generate_memory_governance_dataset(seed=42)

    assert select_semantic_audit_sample(cases, seed=42) == select_semantic_audit_sample(cases, seed=42)


def test_semantic_audit_sample_selects_16_of_80_cases() -> None:
    cases = generate_memory_governance_dataset(seed=42)

    assert len(select_semantic_audit_sample(cases, sample_rate=0.2, seed=42)) == 16


def test_semantic_audit_release_gate_rejects_more_than_two_absurd_cases() -> None:
    assert semantic_audit_release_decision(semantic_absurdity_count=3) == "regenerate_required"


def test_semantic_audit_release_gate_allows_two_or_fewer_absurd_cases() -> None:
    assert semantic_audit_release_decision(semantic_absurdity_count=2) == "pass"
