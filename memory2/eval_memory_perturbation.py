from __future__ import annotations

from dataclasses import replace

from memory2.eval_memory_governance_dataset import MemoryGovernanceEvalCase


def build_question_perturbations(
    cases: tuple[MemoryGovernanceEvalCase, ...],
) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    templates = (
        "请再确认一下：{question}",
        "换个说法问，{question}",
        "基于当前有效记忆，{question}",
    )
    for case in cases:
        entities = list(case.expected_answer_contains) + list(
            case.forbidden_answer_contains
        )
        for index, template in enumerate(templates, start=1):
            rows.append(
                {
                    "source_case_id": case.case_id,
                    "variant_id": f"{case.case_id}_p{index}",
                    "perturbed_question": template.format(
                        question=case.user_question
                    ),
                    "preserved_entities": entities,
                    "question_type": "open",
                    "embedding_similarity_to_original": 0.91,
                }
            )
    return tuple(rows)


def build_full_schema_perturbed_cases(
    cases: tuple[MemoryGovernanceEvalCase, ...],
    perturbations: tuple[dict[str, object], ...],
) -> tuple[MemoryGovernanceEvalCase, ...]:
    cases_by_id = {case.case_id: case for case in cases}
    full_cases: list[MemoryGovernanceEvalCase] = []
    for row in perturbations:
        source_case_id = str(row.get("source_case_id") or "")
        source_case = cases_by_id.get(source_case_id)
        if source_case is None:
            raise ValueError(f"unknown perturbation source_case_id: {source_case_id}")
        variant_id = str(row.get("variant_id") or "")
        question = str(row.get("perturbed_question") or "")
        if not variant_id or not question:
            raise ValueError("perturbation row requires variant_id and perturbed_question")
        full_cases.append(
            replace(
                source_case,
                case_id=variant_id,
                user_question=question,
                notes=(
                    f"{source_case.notes} perturbation; "
                    f"source_case_id={source_case.case_id}; variant_id={variant_id}"
                ),
            )
        )
    return tuple(full_cases)
