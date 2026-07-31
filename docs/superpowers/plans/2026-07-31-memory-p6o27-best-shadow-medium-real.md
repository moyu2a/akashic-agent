# Memory P6o27 Best Shadow Medium Real LLM Validation

## Goal

Validate the latest small-sample candidate
`safe_version_replace_guided_with_retry_shadow` on a medium real-LLM matrix
against `safe_version_replace` and `safe_version_replace_guided`.

## Method

- Case pack: `standard`
- Cases: common `20` + hard `20` = `40` unique cases
- Modes:
  - `safe_version_replace`
  - `safe_version_replace_guided`
  - `safe_version_replace_guided_with_retry_shadow`
- Repeat: `1`
- Intended calls: `120`
- Timeout: `30s`
- Fresh workspace and checkpoint rebuild
- No real retry, no production default change, no retrieval/write/global prompt change

## Gate

- `case_count = 120`
- `unique_case_count = 40`
- `mode_count = 3`
- `repeat_count = 1`
- `checkpoint rows = 120`
- `provider_error_count = 0`
- `timeout_count = 0`
- `malformed_checkpoint_line_count = 0`
- grounding `100.0%`
- forbidden `0.0%`
- token metrics available
- primary and checkpoint-rebuild mode metrics identical
- raw query/prompt/response/session/memory-summary report flags all `false`

## Results

| Mode | Answer | Grounding | Forbidden | Avg Tokens | Avg Latency |
| --- | ---: | ---: | ---: | ---: | ---: |
| `safe_version_replace` | `26/40 = 65.0%` | `100.0%` | `0.0%` | `5470.85` | `3671.025ms` |
| `safe_version_replace_guided` | `31/40 = 77.5%` | `100.0%` | `0.0%` | `5514.45` | `3204.425ms` |
| `safe_version_replace_guided_with_retry_shadow` | `34/40 = 85.0%` | `100.0%` | `0.0%` | `5631.95` | `2786.55ms` |

Retry-shadow telemetry:

- `would_retry_count = 6`
- `answer_choice_group_missing = 5`
- `required_terms_missing = 5`
- average token delta vs guided: `+117.5`, approximately `+2.13%`

## Artifacts

- Primary:
  `my_md/memory_optimization/eval_reports/p6o27_best_shadow_medium_real_v1/real_balanced_40/`
- Rebuild:
  `my_md/memory_optimization/eval_reports/p6o27_best_shadow_medium_real_v1/checkpoint_rebuild/`

## Conclusion

This medium run supports retry-shadow as a positive candidate:
`85.0%` answer rate versus guided `77.5%` and replace `65.0%`, with no
grounding or forbidden regression and only about `2.13%` average token increase.
However, P6o24 previously measured retry-shadow below guided on another
40-case run. The current evidence is therefore a medium-scale positive signal,
not proof of stable superiority. Keep the path shadow-only and run repeat
stability validation before any rollout decision.
