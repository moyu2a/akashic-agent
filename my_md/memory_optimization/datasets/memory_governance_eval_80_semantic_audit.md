# Memory Governance Dataset Semantic Audit

- dataset_path: `my_md/memory_optimization/datasets/memory_governance_eval_80.jsonl`
- dataset_case_count: 80
- audit_seed: 42
- sampled_case_count: 16
- semantic_absurdity_threshold: 2
- semantic_absurdity_count: 0
- reviewer: human
- release_decision: pass

| case_id | scenario | question_memory_alignment | answerability | expected_answer_validity | forbidden_validity | distractor_plausibility | human_common_sense_passed | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mgov_004 | preference_replace | pass | pass | pass | pass | pass | pass | Seeded audit sample representative. |
| mgov_005 | preference_replace | pass | pass | pass | pass | pass | pass | Seeded audit sample representative. |
| mgov_012 | user_correction | pass | pass | pass | pass | pass | pass | Seeded audit sample representative. |
| mgov_014 | user_correction | pass | pass | pass | pass | pass | pass | Seeded audit sample representative. |
| mgov_015 | user_correction | pass | pass | pass | pass | pass | pass | Seeded audit sample representative. |
| mgov_018 | user_correction | pass | pass | pass | pass | pass | pass | Seeded audit sample representative. |
| mgov_028 | similar_memory_conflict | pass | pass | pass | pass | pass | pass | Seeded audit sample representative. |
| mgov_029 | similar_memory_conflict | pass | pass | pass | pass | pass | pass | Seeded audit sample representative. |
| mgov_030 | similar_memory_conflict | pass | pass | pass | pass | pass | pass | Seeded audit sample representative. |
| mgov_032 | stale_memory_interference | pass | pass | pass | pass | pass | pass | Seeded audit sample representative. |
| mgov_036 | stale_memory_interference | pass | pass | pass | pass | pass | pass | Seeded audit sample representative. |
| mgov_055 | low_confidence_source | pass | pass | pass | pass | pass | pass | Seeded audit sample representative. |
| mgov_065 | ambiguous_question_with_answer | pass | pass | pass | pass | pass | pass | Seeded audit sample representative. |
| mgov_070 | ambiguous_question_with_answer | pass | pass | pass | pass | pass | pass | Seeded audit sample representative. |
| mgov_072 | insufficient_evidence_should_uncertain | pass | pass | pass | pass | pass | pass | Seeded audit sample representative. |
| mgov_079 | insufficient_evidence_should_uncertain | pass | pass | pass | pass | pass | pass | Seeded audit sample representative. |
