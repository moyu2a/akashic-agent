# P6o-17 Guided Repeat Stability Retry V2

## Purpose

Validate whether `safe_version_replace_guided` remains better than `safe_version_replace` under the same 3-repeat real LLM stability methodology used by P6o-15.

## Method

- Case pack: standard balanced small, common `20` + hard `20`.
- Modes: `safe_version_replace`, `safe_version_replace_guided`.
- Repeats: `3`.
- Real calls: `40` unique cases * `2` modes * `3` repeats = `240`.
- Workspace: `/tmp/akashic-p6o17-real-workspace-20260729-v2`.
- Primary report: `real_repeat_retry_v2/system_path_safe_version_eval.json` and `.md`.
- Checkpoint: `real_repeat_retry_v2/checkpoint.jsonl`.
- Rebuilt report: `real_repeat_retry_v2_rebuilt/system_path_safe_version_eval.json` and `.md`.
- Prior blocked attempt remains documented separately in `guided_repeat_stability_blocked_report.md`.

## Infra Gate

- `case_count = 240`.
- `unique_case_count = 40`.
- `mode_count = 2`.
- `repeat_count = 3`.
- `provider_error_count = 0`.
- `timeout_count = 0`.
- real guided metadata enabled: `true`.
- real guided contract enabled: `true`.
- unguided replace remains unguided: `true`.
- token metrics available: `true`.

## Results

| mode | cases | answer_success | answer_rate | grounding_rate | forbidden_rate | contract_success | post_check_shadow | avg_tokens | avg_latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `safe_version_replace` | 120 | 77 | 64.1667 | 100.0 | 0.0 | 100.0 | 100.0 | 5418.8833 | 3441.175 |
| `safe_version_replace_guided` | 120 | 80 | 66.6667 | 100.0 | 0.0 | 100.0 | 100.0 | 5522.75 | 3518.9083 |

## Delta

- answer delta: `2.5` points.
- forbidden delta: `0.0` points.
- grounding delta: `0.0` points.
- average token delta: `103.8667`.
- guided token threshold: `5689.8275`.

## Repeat Results

| repeat | replace_success | replace_answer_rate | guided_success | guided_answer_rate | guided_delta | guided_forbidden_rate | guided_grounding_rate |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 23/40 | 57.5 | 23/40 | 57.5 | 0.0 | 0.0 | 100.0 |
| 1 | 24/40 | 60.0 | 28/40 | 70.0 | 10.0 | 0.0 | 100.0 |
| 2 | 30/40 | 75.0 | 29/40 | 72.5 | -2.5 | 0.0 | 100.0 |

## Gate

- guided repeat not-lower count: `2/3`.
- guided answer spread: `15.0` points.
- gate passed: `true`.

## P6o-15 Context

P6o-15 remains the historical stability baseline for unguided `safe_version_replace`: `120` replace calls, `73.3333%` answer rate, `100.0%` grounding, `0.0%` forbidden, `5427.0833` average tokens, and `2.5` point repeat spread. P6o-17 uses same-run comparison for the guided candidate, so P6o-15 is context rather than a hard cross-run gate.

## Conclusion

P6o-17 passed: `safe_version_replace_guided` is now repeat-confirmed as a small positive lift over `safe_version_replace` in the same-run 3-repeat matrix, while preserving grounding, forbidden safety, and token budget. This supports moving next to config-gated shadow rollout planning, not production default activation.

## Next Step

Design config-gated shadow rollout for guided safe-version replacement. The rollout should record guided-vs-unguided post-check deltas without changing production replies, and production default should remain `off` until shadow telemetry is reviewed.
