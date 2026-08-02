# P6o-18 Evidence Prompt A/B

## Method

- Case pack: standard balanced small, common `20` + hard `20`.
- Modes: `safe_version_replace`, `safe_version_replace_guided`, `safe_version_replace_structured_guided`, `safe_version_replace_near_query_block`.
- Repeats: `1`.
- Real calls: `40` unique cases * `4` modes = `160`.

## Infra

- case_count: `160`.
- unique_case_count: `40`.
- mode_count: `4`.
- repeat_count: `1`.
- provider_error_count: `0`.
- timeout_count: `0`.
- checkpoint_input_count: `160`.
- malformed_checkpoint_line_count: `0`.

## Results

| mode | cases | answer_success | answer_rate | grounding_rate | forbidden_rate | avg_tokens | avg_latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `safe_version_replace` | 40 | 24 | 60.0 | 100.0 | 0.0 | 5394.275 | 3923.425 |
| `safe_version_replace_guided` | 40 | 31 | 77.5 | 100.0 | 0.0 | 5481.8 | 3625.4 |
| `safe_version_replace_near_query_block` | 40 | 23 | 57.5 | 100.0 | 0.0 | 5524.125 | 3954.9 |
| `safe_version_replace_structured_guided` | 40 | 31 | 77.5 | 100.0 | 0.0 | 5577.075 | 4032.775 |

## Gate

- best_new_mode: `safe_version_replace_structured_guided`.
- token_limit: `5825.817`.
- gate_passed: `false`.

## Conclusion

P6o-18 did not pass: neither new prompt variant produced a sufficient same-run lift over `safe_version_replace_guided` under the exploratory gate.

## Failure Attribution Follow-up

- Report: `my_md/memory_optimization/eval_reports/p6o18_evidence_prompt_ab_v1/system_path_variant_failure_attribution.json` and `.md`.
- Method: report-only analysis from the completed real `160` rows; anchor mode is `safe_version_replace_guided`; comparisons are `safe_version_replace`, `safe_version_replace_structured_guided`, and `safe_version_replace_near_query_block`.
- Privacy: attribution includes only sanitized case id, repeat id, category, pass/fail, movement, and heuristic bucket; it excludes raw query, prompt, memory text, session text, and full answer.

| mode | passed | required-term miss | any-group miss | language failure |
| --- | ---: | ---: | ---: | ---: |
| `safe_version_replace` | 24 | 8 | 6 | 2 |
| `safe_version_replace_guided` | 31 | 5 | 2 | 2 |
| `safe_version_replace_structured_guided` | 31 | 4 | 3 | 2 |
| `safe_version_replace_near_query_block` | 23 | 8 | 8 | 1 |

| comparison vs `safe_version_replace_guided` | both pass | guided fixes comparison miss | comparison fixes guided miss | both fail |
| --- | ---: | ---: | ---: | ---: |
| `safe_version_replace` | 21 | 10 | 3 | 6 |
| `safe_version_replace_structured_guided` | 27 | 4 | 4 | 5 |
| `safe_version_replace_near_query_block` | 21 | 10 | 2 | 7 |

Attribution conclusion: the remaining guided failures are answer-expression/scoring misses, not recall, safety, or infra failures. `safe_version_replace_guided` misses `9/40` cases: `5` required-term misses, `2` any-group misses, and `2` language failures. `structured_guided` swaps wins and losses against guided (`4` fixed, `4` regressed) while spending more tokens, so it is not a net improvement. `near_query_block` causes a broad selection regression: it loses `10` cases that guided answered correctly and only fixes `2` guided misses.

Next: do not continue the current structured or near-query wording. The useful next step is targeted answer-selection work on the guided miss set: preference-recall, version-chain/stale-sleep, graph-bridge, and the two language failures.

## Error Analysis Conclusion

The errors are concentrated in the answer layer, not the memory layer. The real run has `provider_error_count = 0`, `timeout_count = 0`, `grounding_rate = 100.0%`, and `forbidden_rate = 0.0%`, so the missed cases should not be treated as retrieval misses, unsafe boundary failures, or infra noise.

The current best mode is still `safe_version_replace_guided`: it passes `31/40 = 77.5%` and leaves `9` misses. Those `9` misses split into `5` required-term misses, `2` any-group misses, and `2` language failures. This means the model usually received safe usable evidence, but did not consistently select or phrase the answer in the expected form.

The weaker modes fail for different reasons:

- `safe_version_replace` lacks answer guidance, so it has more expression misses: `16` total misses versus guided's `9`.
- `safe_version_replace_structured_guided` is not better than guided because it only trades cases: it fixes `4` guided misses but regresses `4` guided passes, with higher token and latency cost.
- `safe_version_replace_near_query_block` is actively worse because it over-focuses the model on query-near evidence: it loses `10` guided-passed cases and fixes only `2` guided misses.

Operational conclusion: do not expand recall, enable graph-all-on, or promote structured/near-query wording based on these errors. The next useful work is targeted answer-selection/prompt adjustment for the guided miss set, especially preference recall, version/stale choice, graph-bridge evidence use, and Chinese language compliance.
