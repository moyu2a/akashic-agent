from __future__ import annotations

from pathlib import Path

from memory2.eval_memory_governance_dataset import load_memory_governance_cases
from memory2.eval_memory_perturbation import build_question_perturbations


def test_build_question_perturbations_creates_three_variants_per_case() -> None:
    cases = load_memory_governance_cases(
        Path("my_md/memory_optimization/datasets/memory_governance_eval_80.jsonl")
    )

    perturbations = build_question_perturbations(cases)

    assert len(perturbations) == 240
    assert {row["variant_id"] for row in perturbations}
    assert all(row["embedding_similarity_to_original"] >= 0.85 for row in perturbations)
