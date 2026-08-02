# P6o-19 Answer Candidate Retry Shadow Report

## Method

- Objective: test whether an eval-only Answer Candidate Contract plus Post-check Retry Shadow can identify answer-layer misses when safe-version evidence is already grounded.
- Modes: `safe_version_replace`, `safe_version_replace_guided`, `safe_version_replace_guided_with_retry_shadow`.
- Fake smoke data: standard case pack, balanced small, common `2` + hard `2`, repeat `1`.
- Production behavior: unchanged. `MemoryConfig.safe_version_governed_mode` remains `off`; no graph-all-on, no recall expansion, no real retry/fallback, no memory write change, and no global prompt change.
- Privacy rule: committed reports contain only sanitized counts, ids already present in contract reports, booleans, and reason labels. They do not include raw query, raw prompt, session text, memory summary, full answer, API key, Authorization, or secret values.

## Artifacts

- Fake smoke JSON: `my_md/memory_optimization/eval_reports/p6o19_answer_candidate_retry_shadow_v1/fake_smoke/system_path_safe_version_eval.json`.
- Fake smoke Markdown: `my_md/memory_optimization/eval_reports/p6o19_answer_candidate_retry_shadow_v1/fake_smoke/system_path_safe_version_eval.md`.
- Gate decision: `my_md/memory_optimization/eval_reports/p6o19_answer_candidate_retry_shadow_v1/fake_smoke/gate_decision.json`.
- Gate report: `my_md/memory_optimization/eval_reports/p6o19_answer_candidate_retry_shadow_v1/fake_smoke/p6o19_answer_candidate_retry_shadow_report.md`.

## Fake Smoke Data

| metric | value |
| --- | ---: |
| unique_case_count | 4 |
| mode_count | 3 |
| case_count | 12 |
| repeat_count | 1 |
| provider_error_count | 0 |
| timeout_count | 0 |
| malformed_checkpoint_line_count | 0 |
| fake_provider_enabled | true |
| real_llm_enabled | false |

| mode | cases | answer_rate | grounding_rate | forbidden_rate | candidate_contract | would_retry | retry_reasons |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `safe_version_replace` | 4 | 0.0 | 100.0 | 0.0 | 0.0 | 0 | `{}` |
| `safe_version_replace_guided` | 4 | 0.0 | 100.0 | 0.0 | 0.0 | 0 | `{}` |
| `safe_version_replace_guided_with_retry_shadow` | 4 | 0.0 | 100.0 | 0.0 | 100.0 | 4 | `{"answer_choice_group_missing": 4, "required_terms_missing": 4}` |

## Gate

- `guided_answer_rate = 0.0`.
- `retry_shadow_answer_rate = 0.0`.
- `answer_delta_vs_guided = 0.0`.
- `retry_shadow_would_retry_count = 4`.
- `retry_shadow_reason_counts = {"answer_choice_group_missing": 4, "required_terms_missing": 4}`.
- `gate_passed = false`.

## Verification

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_system_path_safe_version_eval.py --workspace /tmp/akashic-p6o19-answer-candidate-fake/workspace --out-dir my_md/memory_optimization/eval_reports/p6o19_answer_candidate_retry_shadow_v1/fake_smoke --fake-provider --case-pack standard --balanced-small --common-limit 2 --hard-limit 2 --modes safe_version_replace,safe_version_replace_guided,safe_version_replace_guided_with_retry_shadow` -> exit `0`.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_memory_p6o19_gate.py --report-json my_md/memory_optimization/eval_reports/p6o19_answer_candidate_retry_shadow_v1/fake_smoke/system_path_safe_version_eval.json --out-dir my_md/memory_optimization/eval_reports/p6o19_answer_candidate_retry_shadow_v1/fake_smoke` -> exit `0`.
- `.venv/bin/python -m pytest tests/test_memory_system_path_safe_version_contract.py tests/test_memory_answer_post_check.py tests/test_memory_system_path_safe_version_eval.py tests/test_memory_engine_contract.py tests/test_turn_pipelines.py -q -p no:cacheprovider` -> `98 passed in 22.58s`.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m compileall memory2/system_path_safe_version_contract.py memory2/eval_answer_post_check.py memory2/eval_system_path_safe_version.py scripts/run_memory_system_path_safe_version_eval.py scripts/check_memory_p6o19_gate.py tests/test_memory_system_path_safe_version_contract.py tests/test_memory_answer_post_check.py tests/test_memory_system_path_safe_version_eval.py` -> exit `0`.
- `git diff --check` -> exit `0`.
- P6o-19 report privacy scan found no raw prompt/query/answer/secret content. The only matches were allowed documentation/boolean-field text: `raw_memory_summary_included = false` and the top-level privacy rule sentence.
- Code review was requested twice. The first review inspected the wrong checkout and was invalid; the corrected review failed with provider `403 INSUFFICIENT_BALANCE`, so no external review feedback was available to apply.

## Conclusion

P6o-19 fake smoke validates wiring, report sanitation, and retry-shadow classification. It does not validate answer-quality improvement because the fake provider is not a real LLM and both guided modes score `0.0` answer rate in this smoke.

The retry-shadow signal is functioning: all `4/4` retry-shadow rows enabled the candidate contract and were flagged as would-retry from scorer miss counts. The next quality gate requires a checkpointed real LLM small matrix and checkpoint rebuild before making any answer-lift conclusion.
