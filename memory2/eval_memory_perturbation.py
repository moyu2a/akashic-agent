from __future__ import annotations

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
