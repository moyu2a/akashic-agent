# System Path Safe Version Governed

本报告记录 P6o-15 system-path repeat stability。报告使用真实 LLM 和 fixture-seeded temporary system-path store；不读取真实用户 memory DB，不包含原始 query、prompt、memory summary、完整回答或 secrets。

## Test Method

- evaluation_level: `system_path_safe_version_governed`
- real_llm_enabled: `True`
- unique_case_count: `40`
- case_count: `240`
- case_pack: `standard`
- case_slice: common `20` + hard `20`
- modes: `current`, `safe_version_replace`
- repeats: `3`
- provider_error_count: `0`
- timeout_count: `0`
- token_metrics_available: `True`
- replacement_seeded_count: `240`
- checkpoint: `/tmp/akashic-memory-p6o15-system-path-repeat-real/checkpoint.jsonl`
- production default: `MemoryConfig.safe_version_governed_mode = "off"`

Runner changes used by this report:

- `--repeats`
- `--checkpoint-jsonl`
- `--resume`
- `--checkpoint-report-only`

Review follow-up after the run hardened checkpoint behavior: resume skips provider_error/timeout rows so they can be retried, while report-only rebuilds include infra rows and malformed trailing JSONL is counted instead of blocking recovery.

## Aggregate Result

| mode | cases | answer_success | answer_rate | grounding_rate | forbidden_rate | contract_success | post_check_shadow | avg_tokens | avg_latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| current | 120 | 31 | 25.8333 | 100.0 | 39.1667 | 0.0 | 0.0 | 5582.0 | 4627.15 |
| safe_version_replace | 120 | 88 | 73.3333 | 100.0 | 0.0 | 100.0 | 100.0 | 5427.0833 | 3259.7667 |

Delta vs `current`:

- answer: `+47.5` points
- grounding: `0.0` points
- forbidden: `-39.1667` points
- avg tokens: `-154.9167`
- avg latency: `-1367.3833ms`

## Repeat Stability

| repeat | current answer | replace answer | current forbidden | replace forbidden | replace avg tokens | replace avg latency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0` | `10/40 = 25.0%` | `29/40 = 72.5%` | `45.0%` | `0.0%` | `5421.525` | `3386.275ms` |
| `1` | `14/40 = 35.0%` | `29/40 = 72.5%` | `27.5%` | `0.0%` | `5441.275` | `3416.425ms` |
| `2` | `7/40 = 17.5%` | `30/40 = 75.0%` | `45.0%` | `0.0%` | `5418.45` | `2976.6ms` |

Repeat gate passed:

- complete matrix: `240` rows, `40` unique cases, `2` modes, `3` repeats
- replace answer was higher than current in every repeat
- replace answer floor stayed above `45.0%`
- replace answer spread was `2.5` points
- grounding stayed `100.0%`
- forbidden stayed `0.0%`
- token and latency did not increase

## Conclusion

P6o-15 supports the P6o-14 direction and improves the estimate: P6o-14 `safe_version_replace` was `21/40 = 52.5%`, while P6o-15 repeat stability is `88/120 = 73.3333%`.

The result is directionally strong enough to proceed to P6o-16 system-path answer guidance. It is not enough for production default activation because it is still controlled fixture-seeded system-path evaluation and remains below the P6o-12 eval-only `97.5%` reference.

## Boundary

- no graph/all-on
- no production write, retry, fallback, answer guidance, prompt placement, or production contract-format change in P6o-15
- default production mode remains `off`
- `--real-memory-workspace` remains CLI compatibility only for this runner
