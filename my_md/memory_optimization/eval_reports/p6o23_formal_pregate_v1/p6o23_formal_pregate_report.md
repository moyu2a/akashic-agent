# P6o-23 Formal Pregate Report

## Objective

在正式 40-case real-LLM 实验前，先验证 P6o-22 infra guard 后的真实评测链路是否稳定，避免再次产生 `answer_rate=0` 的 infra 假数据。

## Method

- Case pack: `standard`.
- Slice: `5` common + `5` hard = `10` unique cases.
- Modes:
  - `safe_version_replace`
  - `safe_version_replace_guided`
  - `safe_version_replace_guided_with_retry_shadow`
- Intended calls: `10` cases * `3` modes = `30`.
- Timeout: `30s`.
- Infra guard:
  - `--early-infra-abort-count 3`
  - `--early-infra-abort-rate 0.5`
- Checkpoint: fresh.
- Production behavior: unchanged. No production default change, no graph-all-on, no recall expansion, no real retry/fallback, no memory write change, and no global prompt change.

Command:

```bash
.venv/bin/python scripts/run_memory_system_path_safe_version_eval.py --workspace /tmp/akashic-p6o23-pregate-real/workspace --out-dir my_md/memory_optimization/eval_reports/p6o23_formal_pregate_v1/real_balanced_10 --config /home/jjh/git_work/akashic-agent/config.toml --enable-real-llm --case-pack standard --balanced-small --common-limit 5 --hard-limit 5 --modes safe_version_replace,safe_version_replace_guided,safe_version_replace_guided_with_retry_shadow --timeout-s 30 --checkpoint-jsonl my_md/memory_optimization/eval_reports/p6o23_formal_pregate_v1/real_balanced_10/checkpoint.jsonl --early-infra-abort-count 3 --early-infra-abort-rate 0.5
```

Result: exit `0`.

## Artifacts

- Primary JSON: `my_md/memory_optimization/eval_reports/p6o23_formal_pregate_v1/real_balanced_10/system_path_safe_version_eval.json`
- Primary Markdown: `my_md/memory_optimization/eval_reports/p6o23_formal_pregate_v1/real_balanced_10/system_path_safe_version_eval.md`
- Checkpoint: `my_md/memory_optimization/eval_reports/p6o23_formal_pregate_v1/real_balanced_10/checkpoint.jsonl`

No `blocked_status.json` was written.

## Data

Primary metrics:

| metric | value |
| --- | ---: |
| unique_case_count | 10 |
| mode_count | 3 |
| case_count | 30 |
| checkpoint_line_count | 30 |
| timeout_count | 0 |
| provider_error_count | 0 |
| empty_answer_count | 0 |
| answer_rule_pass_rate | 60.0 |
| memory_grounding_pass_rate | 100.0 |
| forbidden_violation_rate | 0.0 |
| token_metrics_available | true |
| avg_latency_ms | 3293.9667 |

Mode summary:

| mode | cases | answer_success | answer_rate | grounding_rate | forbidden_rate | avg_tokens | avg_latency_ms | would_retry |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| safe_version_replace | 10 | 6 | 60.0 | 100.0 | 0.0 | 5416.3 | 3112.5 | 0 |
| safe_version_replace_guided | 10 | 6 | 60.0 | 100.0 | 0.0 | 5485.7 | 2747.9 | 0 |
| safe_version_replace_guided_with_retry_shadow | 10 | 6 | 60.0 | 100.0 | 0.0 | 5720.3 | 4021.5 | 4 |

Retry shadow reasons for `safe_version_replace_guided_with_retry_shadow`:

| reason | count |
| --- | ---: |
| answer_choice_group_missing | 2 |
| language_requirement_failed | 1 |
| required_terms_missing | 2 |

Per-row pass/fail summary:

| case_id | category | replace | guided | guided_retry_shadow |
| --- | --- | --- | --- | --- |
| common_preference_recall_01 | common_preference_recall | fail | fail | fail |
| common_tool_preference_01 | common_tool_preference | fail | fail | fail |
| common_style_preference_01 | common_style_preference | pass | pass | pass |
| common_tri_rrf_01 | common_tri_rrf | pass | pass | pass |
| common_graph_bridge_01 | common_graph_bridge | pass | fail | fail |
| hard_preference_recall_01 | hard_preference_recall | fail | pass | pass |
| hard_tool_preference_01 | hard_tool_preference | pass | pass | pass |
| hard_style_preference_01 | hard_style_preference | pass | fail | pass |
| hard_tri_rrf_01 | hard_tri_rrf | pass | pass | pass |
| hard_graph_bridge_01 | hard_graph_bridge | fail | pass | fail |

Movement vs `safe_version_replace`:

| comparison | improved | regressed | same_pass | same_fail |
| --- | ---: | ---: | ---: | ---: |
| safe_version_replace_guided | 2 | 2 | 4 | 2 |
| safe_version_replace_guided_with_retry_shadow | 2 | 2 | 4 | 2 |

## Gate Decision

`PASS` for running the formal experiment.

Gate criteria:

- `timeout_count = 0`: pass.
- `provider_error_count = 0`: pass.
- `empty_answer_count = 0`: pass.
- checkpoint rows match intended calls (`30`): pass.
- no `blocked_status.json`: pass.

## Conclusion

The P6o-22 guard fixed the previous failure mode where timeout-heavy data could be rebuilt into a quality-looking report. This P6o-23 pregate run produced usable answer data for all `30` rows.

The pregate is not large enough to conclude quality uplift. It only validates that the real-LLM eval path is healthy enough to run the formal `40 case * 3 mode` experiment with a fresh checkpoint and the same infra guard.
