# P6o-20 Answer Candidate Retry Shadow Real Small Report

## Method

- Objective: run a real-LLM system-path small matrix for `safe_version_replace_guided_with_retry_shadow` and preserve full local scoring data for review.
- Case pack: `standard`.
- Slice: common `20` + hard `20`.
- Modes: `safe_version_replace`, `safe_version_replace_guided`, `safe_version_replace_guided_with_retry_shadow`.
- Repeat count: `1`.
- Intended real calls: `40` unique cases * `3` modes = `120`.
- Production behavior: unchanged. `MemoryConfig.safe_version_governed_mode` remains `off`; no graph-all-on, no recall expansion, no real retry/fallback, no memory write change, and no global prompt change.

## Commands

Fresh real run was started with:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_system_path_safe_version_eval.py --workspace /tmp/akashic-p6o20-answer-candidate-real/workspace --out-dir my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/real_small_ab --config /home/jjh/git_work/akashic-agent/config.toml --enable-real-llm --case-pack standard --balanced-small --common-limit 20 --hard-limit 20 --modes safe_version_replace,safe_version_replace_guided,safe_version_replace_guided_with_retry_shadow --checkpoint-jsonl my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/real_small_ab/checkpoint.jsonl
```

After the first `30` checkpoint rows were all timeouts, the run was interrupted and resumed with shorter timeout to complete a full blocked data shape:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_system_path_safe_version_eval.py --workspace /tmp/akashic-p6o20-answer-candidate-real/workspace --out-dir my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/real_small_ab --config /home/jjh/git_work/akashic-agent/config.toml --enable-real-llm --case-pack standard --balanced-small --common-limit 20 --hard-limit 20 --modes safe_version_replace,safe_version_replace_guided,safe_version_replace_guided_with_retry_shadow --checkpoint-jsonl my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/real_small_ab/checkpoint.jsonl --resume --timeout-s 1
```

Checkpoint rebuild:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_system_path_safe_version_eval.py --out-dir my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/real_small_ab_rebuilt --enable-real-llm --checkpoint-jsonl my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/real_small_ab/checkpoint.jsonl --checkpoint-report-only
```

Gate:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_memory_p6o19_gate.py --report-json my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/real_small_ab/system_path_safe_version_eval.json --out-dir my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1
```

Gate result: hard failure with `timeout_count must be 0`.

Detail export:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/export_memory_p6o20_answer_details.py --report-json my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/real_small_ab/system_path_safe_version_eval.json --out-dir my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/answer_details --anchor-mode safe_version_replace_guided --comparison-mode safe_version_replace_guided_with_retry_shadow
```

## Artifacts

- Primary JSON: `my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/real_small_ab/system_path_safe_version_eval.json`.
- Primary Markdown: `my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/real_small_ab/system_path_safe_version_eval.md`.
- Rebuilt JSON: `my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/real_small_ab_rebuilt/system_path_safe_version_eval.json`.
- Rebuilt Markdown: `my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/real_small_ab_rebuilt/system_path_safe_version_eval.md`.
- Blocked status: `my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/blocked_status.json`.
- Detail JSONL: `my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/answer_details/per_case_scoring_rows.jsonl`.
- Detail CSV: `my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/answer_details/per_case_scoring_rows.csv`.
- Movement JSON: `my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/answer_details/case_movement_vs_guided.json`.
- Movement Markdown: `my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/answer_details/case_movement_vs_guided.md`.
- Export summary: `my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/answer_details/export_summary.json`.

## Data

| metric | primary | rebuilt |
| --- | ---: | ---: |
| unique_case_count | 40 | 40 |
| mode_count | 3 | 3 |
| case_count | 120 | 120 |
| repeat_count | 1 | 1 |
| provider_error_count | 0 | 0 |
| timeout_count | 120 | 120 |
| malformed_checkpoint_line_count | 0 | 0 |
| checkpoint_input_count | 0 | 151 |

The checkpoint has `151` physical lines because the first interrupted partial run wrote timeout rows, and resume does not skip infra-failure rows. The rebuilt report deduplicates by spec key and yields the same `120` case rows as the primary report.

| mode | cases | answer_rate | grounding_rate | forbidden_rate | candidate_contract | would_retry | retry_reasons |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `safe_version_replace` | 40 | 0.0 | 100.0 | 0.0 | 0.0 | 0 | `{}` |
| `safe_version_replace_guided` | 40 | 0.0 | 100.0 | 0.0 | 0.0 | 0 | `{}` |
| `safe_version_replace_guided_with_retry_shadow` | 40 | 0.0 | 100.0 | 0.0 | 100.0 | 40 | `{"answer_choice_group_missing": 40, "language_requirement_failed": 40, "required_terms_missing": 40}` |

Detail export:

- `per_case_scoring_rows.jsonl`: `120` rows.
- `per_case_scoring_rows.csv`: `121` rows including header.
- `paired_case_count = 40`.
- `unpaired_case_count = 0`.
- movement counts vs guided: `both_failed = 40`, `both_passed = 0`, `anchor_failed_comparison_passed = 0`, `anchor_passed_comparison_failed = 0`.
- `forbidden_key_scan_passed = true`.

## Verification

- Focused tests: `.venv/bin/python -m pytest tests/test_memory_system_path_safe_version_contract.py tests/test_memory_answer_post_check.py tests/test_memory_system_path_safe_version_eval.py tests/test_memory_engine_contract.py tests/test_turn_pipelines.py -q -p no:cacheprovider` -> `99 passed in 22.77s`.
- Compile: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m compileall scripts/export_memory_p6o20_answer_details.py scripts/check_memory_p6o19_gate.py scripts/run_memory_system_path_safe_version_eval.py memory2/system_path_safe_version_contract.py memory2/eval_answer_post_check.py memory2/eval_system_path_safe_version.py tests/test_memory_system_path_safe_version_eval.py` -> exit `0`.
- Privacy scan: no forbidden raw payload or secret-pattern matches under the P6o-20 report directory.

## Conclusion

P6o-20 is `infra_blocked`, not `quality_failed` and not `quality_passed`.

The real-provider path did not return usable completions within the configured timeouts. All `120/120` rows are timeout rows, so answer text is empty, token metrics are unavailable, and all answer rates are `0.0`. These answer numbers must not be used to judge whether `safe_version_replace_guided_with_retry_shadow` improves answer quality.

The useful result from this run is the data pipeline: complete per-row scoring export, movement report, and export summary are now available and validated. To get a real answer-quality conclusion, rerun P6o-20 with a working provider configuration and a fresh or deliberately cleaned checkpoint.
