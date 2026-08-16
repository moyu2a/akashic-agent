# Memory Governance Evaluation Datasets

`memory_governance_eval_80.jsonl` is the fixed seed-42 governance dataset for the P1-P4 memory evaluation ladder.

Release requirements:

- Run `validate_memory_governance_cases()` to check structure, references, evidence graph cycles, stale memory placement, and expected/forbidden conflicts.
- Generate from `generate_memory_governance_dataset(seed=42)`; the generated JSONL must match the committed file byte-for-byte.
- Complete the 20% human semantic audit before formal real LLM runs. The audit checks whether sampled questions, memories, expected answers, forbidden terms, and distractors make sense under human common sense.
- The semantic audit is a dataset release gate only. It does not participate in model scoring.

If the audit finds more than 2 semantically absurd cases in the 16 sampled rows, regenerate the full 80-case dataset after adjusting scenario templates or weights.
