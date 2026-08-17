from __future__ import annotations

from pathlib import Path

from memory2.eval_memory_governance_dataset import (
    load_memory_governance_cases,
    validate_memory_governance_cases,
)
from memory2.eval_memory_perturbation import (
    build_full_schema_perturbed_cases,
    build_question_perturbations,
)


def test_build_question_perturbations_creates_three_variants_per_case() -> None:
    cases = load_memory_governance_cases(
        Path("my_md/memory_optimization/datasets/memory_governance_eval_80.jsonl")
    )

    perturbations = build_question_perturbations(cases)

    assert len(perturbations) == 240
    assert {row["variant_id"] for row in perturbations}
    assert all(row["embedding_similarity_to_original"] >= 0.85 for row in perturbations)


def test_build_full_schema_perturbed_cases_preserves_eval_contract() -> None:
    cases = load_memory_governance_cases(
        Path("my_md/memory_optimization/datasets/memory_governance_eval_80.jsonl")
    )
    perturbations = build_question_perturbations(cases)

    full_cases = build_full_schema_perturbed_cases(cases, perturbations)

    assert len(full_cases) == 240
    assert full_cases[0].case_id == "mgov_001_p1"
    assert full_cases[0].user_question.startswith("请再确认一下：")
    assert full_cases[0].should_recall_ids == cases[0].should_recall_ids
    assert full_cases[0].should_not_recall_ids == cases[0].should_not_recall_ids
    assert full_cases[0].expected_answer_contains == cases[0].expected_answer_contains
    assert full_cases[0].forbidden_answer_contains == cases[0].forbidden_answer_contains
    assert full_cases[0].memories == cases[0].memories
    assert "source_case_id=mgov_001" in full_cases[0].notes
    assert validate_memory_governance_cases(full_cases) == ()
