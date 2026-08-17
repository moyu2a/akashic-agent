from __future__ import annotations

import random

from memory2.eval_memory_governance_dataset import MemoryGovernanceEvalCase


def select_semantic_audit_sample(
    cases: tuple[MemoryGovernanceEvalCase, ...],
    *,
    sample_rate: float = 0.2,
    seed: int = 42,
) -> tuple[str, ...]:
    if not 0 < sample_rate <= 1:
        raise ValueError("sample_rate must be in (0, 1]")
    sample_count = int(len(cases) * sample_rate)
    if len(cases) and sample_count < 1:
        sample_count = 1
    ids = [case.case_id for case in cases]
    selected = set(random.Random(seed).sample(ids, sample_count))
    return tuple(case.case_id for case in cases if case.case_id in selected)


def semantic_audit_release_decision(
    *,
    semantic_absurdity_count: int,
    semantic_absurdity_threshold: int = 2,
) -> str:
    if semantic_absurdity_count <= semantic_absurdity_threshold:
        return "pass"
    return "regenerate_required"
