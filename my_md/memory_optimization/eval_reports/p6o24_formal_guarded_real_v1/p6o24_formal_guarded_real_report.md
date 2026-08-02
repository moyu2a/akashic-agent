# P6o-24 Formal Guarded Real Report

## Objective

完成之前 P6o-20 报错的真实 LLM 实验：在 fresh workspace、fresh out-dir、fresh checkpoint 下重跑 `safe_version_replace`、`safe_version_replace_guided`、`safe_version_replace_guided_with_retry_shadow` 三模式矩阵，并用 P6o-22 infra guard 防止 timeout / provider failure 被误解释成 answer-quality 结论。

本轮不修改生产默认、不改召回、不改 prompt、不改 graph 行为、不执行真实 retry、不改 memory writes。`safe_version_replace_guided_with_retry_shadow` 仍是 eval-only shadow：Answer Candidate Contract + Post-check Retry Shadow 只记录 would-retry 和失败原因。

## Plan And Review

- Plan: `docs/superpowers/plans/2026-07-30-memory-p6o24-formal-guarded-real.md`
- Review result: required revisions before execution.
- Revisions applied before run:
  - Freshness gate changed from descriptive requirement to hard `test ! -e ...` preflight.
  - Formal command explicitly added `--repeats 1`.
  - Primary/rebuild quality gates changed from print-only checks to assertion checks.
  - Detail export allowed only after the full quality gate passes.
  - If infra-blocked, the plan records `infra_blocked` and skips quality interpretation.
  - Final report requires movement counts, category breakdown, token/latency deltas, grounding/forbidden deltas, and an explicit improve/regress/tie rule.
  - Privacy scan includes raw prompt/query/answer/session/memory-summary and structured JSON report flags.

## Method

- Case pack: `standard`.
- Slice: `20` common + `20` hard = `40` unique cases.
- Modes:
  - `safe_version_replace`
  - `safe_version_replace_guided`
  - `safe_version_replace_guided_with_retry_shadow`
- Repeats: `1`.
- Intended rows: `40` cases * `3` modes = `120`.
- Timeout: `30s`.
- Infra guard:
  - `--early-infra-abort-count 3`
  - `--early-infra-abort-rate 0.5`
- Fresh workspace: `/tmp/akashic-p6o24-formal-real/workspace`
- Fresh primary out-dir: `my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/real_balanced_40`
- Fresh checkpoint: `my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/real_balanced_40/checkpoint.jsonl`

Preflight freshness checks all exited `0`:

```bash
test ! -e my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/real_balanced_40/checkpoint.jsonl
test ! -e my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/real_balanced_40
test ! -e /tmp/akashic-p6o24-formal-real/workspace
```

Formal command:

```bash
.venv/bin/python scripts/run_memory_system_path_safe_version_eval.py --workspace /tmp/akashic-p6o24-formal-real/workspace --out-dir my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/real_balanced_40 --config /home/jjh/git_work/akashic-agent/config.toml --enable-real-llm --case-pack standard --balanced-small --common-limit 20 --hard-limit 20 --modes safe_version_replace,safe_version_replace_guided,safe_version_replace_guided_with_retry_shadow --timeout-s 30 --repeats 1 --checkpoint-jsonl my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/real_balanced_40/checkpoint.jsonl --early-infra-abort-count 3 --early-infra-abort-rate 0.5
```

Result: exit `0`.

Checkpoint guarded rebuild command:

```bash
.venv/bin/python scripts/run_memory_system_path_safe_version_eval.py --out-dir my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/checkpoint_guarded_rebuild --enable-real-llm --checkpoint-jsonl my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/real_balanced_40/checkpoint.jsonl --checkpoint-report-only --early-infra-abort-count 3 --early-infra-abort-rate 0.5
```

Result: exit `0`.

Detail export command:

```bash
.venv/bin/python scripts/export_memory_p6o20_answer_details.py --report-json my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/real_balanced_40/system_path_safe_version_eval.json --out-dir my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/answer_details --anchor-mode safe_version_replace_guided --comparison-mode safe_version_replace_guided_with_retry_shadow
```

Result: exit `0`.

## Artifacts

- Primary JSON: `my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/real_balanced_40/system_path_safe_version_eval.json`
- Primary Markdown: `my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/real_balanced_40/system_path_safe_version_eval.md`
- Primary checkpoint: `my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/real_balanced_40/checkpoint.jsonl`
- Rebuild JSON: `my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/checkpoint_guarded_rebuild/system_path_safe_version_eval.json`
- Rebuild Markdown: `my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/checkpoint_guarded_rebuild/system_path_safe_version_eval.md`
- Detail JSONL: `my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/answer_details/per_case_scoring_rows.jsonl`
- Detail CSV: `my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/answer_details/per_case_scoring_rows.csv`
- Movement JSON: `my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/answer_details/case_movement_vs_guided.json`
- Movement Markdown: `my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/answer_details/case_movement_vs_guided.md`
- Export summary: `my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/answer_details/export_summary.json`

No primary or rebuild `blocked_status.json` was written.

## Quality Gate

| criterion | expected | observed | result |
| --- | ---: | ---: | --- |
| primary exit code | 0 | 0 | pass |
| rebuild exit code | 0 | 0 | pass |
| primary blocked_status.json | absent | absent | pass |
| rebuild blocked_status.json | absent | absent | pass |
| case_count | 120 | 120 | pass |
| unique_case_count | 40 | 40 | pass |
| mode_count | 3 | 3 | pass |
| checkpoint rows | 120 | 120 | pass |
| rebuild checkpoint_input_count | 120 | 120 | pass |
| timeout_count | 0 | 0 | pass |
| provider_error_count | 0 | 0 | pass |
| empty_answer_count | 0 | 0 | pass |
| malformed_checkpoint_line_count | 0 | 0 | pass |
| rebuild metrics match primary | true | true | pass |

Gate decision: `quality_passed_for_interpretation`.

## Primary Metrics

| metric | value |
| --- | ---: |
| case_count | 120 |
| unique_case_count | 40 |
| mode_count | 3 |
| repeat_count | 1 |
| real_llm_enabled | true |
| fake_provider_enabled | false |
| answer_rule_pass_rate | 75.8333 |
| memory_grounding_pass_rate | 100.0 |
| forbidden_violation_rate | 0.0 |
| timeout_count | 0 |
| provider_error_count | 0 |
| empty_answer_count | 0 |
| malformed_checkpoint_line_count | 0 |
| token_metrics_available | true |
| total_token_count | 657852 |
| avg_total_token_count | 5482.1 |
| avg_latency_ms | 3248.8667 |

## Mode Summary

| mode | cases | answer_success | answer_rate | grounding_rate | forbidden_rate | avg_tokens | avg_latency_ms | contract_enabled | post_check_shadow | would_retry |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| safe_version_replace | 40 | 30 | 75.0 | 100.0 | 0.0 | 5407.575 | 3411.925 | 0.0 | 100.0 | 0 |
| safe_version_replace_guided | 40 | 32 | 80.0 | 100.0 | 0.0 | 5485.15 | 3283.725 | 0.0 | 100.0 | 0 |
| safe_version_replace_guided_with_retry_shadow | 40 | 29 | 72.5 | 100.0 | 0.0 | 5553.575 | 3050.95 | 100.0 | 100.0 | 11 |

## Retry Shadow Reasons

`safe_version_replace_guided_with_retry_shadow` recorded `11` would-retry rows. Reasons are not mutually exclusive, so counts can sum above `11`.

| reason | count |
| --- | ---: |
| answer_choice_group_missing | 8 |
| required_terms_missing | 5 |
| language_requirement_failed | 1 |

## Guided Vs Retry Shadow

Anchor: `safe_version_replace_guided`.

Comparison: `safe_version_replace_guided_with_retry_shadow`.

| metric | guided | retry_shadow | delta |
| --- | ---: | ---: | ---: |
| answer_rate | 80.0 | 72.5 | -7.5 |
| answer_success_count | 32 | 29 | -3 |
| memory_grounding_pass_rate | 100.0 | 100.0 | 0.0 |
| forbidden_violation_rate | 0.0 | 0.0 | 0.0 |
| avg_total_token_count | 5485.15 | 5553.575 | +68.425 |
| avg_latency_ms | 3283.725 | 3050.95 | -232.775 |

Movement counts:

| movement | count |
| --- | ---: |
| both_passed | 25 |
| both_failed | 4 |
| guided_failed_retry_shadow_passed | 4 |
| guided_passed_retry_shadow_failed | 7 |

Decision rule:

- `guided_retry_shadow` improves only if answer-rate delta vs guided is positive and there is no grounding-rate regression and no forbidden-rate regression.
- It regresses if answer-rate delta is negative or if grounding/forbidden regresses.
- Otherwise it ties.

Decision: `regresses`.

Reason: answer-rate delta is `-7.5` percentage points. Grounding and forbidden stay clean, but retry-shadow loses `7` guided-pass cases while rescuing `4` guided-fail cases.

## Category Breakdown

Each row has `2` cases per mode.

| category | replace answer | guided answer | retry_shadow answer | guided -> shadow movement |
| --- | ---: | ---: | ---: | --- |
| common_conflict_resolution | 50.0 | 0.0 | 50.0 | 1 improved, 0 regressed, 0 both pass, 1 both fail |
| common_cross_scope | 100.0 | 100.0 | 100.0 | 0 improved, 0 regressed, 2 both pass, 0 both fail |
| common_duplicate_cleanup | 100.0 | 100.0 | 100.0 | 0 improved, 0 regressed, 2 both pass, 0 both fail |
| common_graph_bridge | 50.0 | 100.0 | 100.0 | 0 improved, 0 regressed, 2 both pass, 0 both fail |
| common_preference_recall | 50.0 | 0.0 | 0.0 | 0 improved, 0 regressed, 0 both pass, 2 both fail |
| common_stale_sleep | 50.0 | 100.0 | 100.0 | 0 improved, 0 regressed, 2 both pass, 0 both fail |
| common_style_preference | 100.0 | 50.0 | 100.0 | 1 improved, 0 regressed, 1 both pass, 0 both fail |
| common_tool_preference | 50.0 | 100.0 | 50.0 | 0 improved, 1 regressed, 1 both pass, 0 both fail |
| common_tri_rrf | 50.0 | 100.0 | 100.0 | 0 improved, 0 regressed, 2 both pass, 0 both fail |
| common_version_chain | 50.0 | 100.0 | 50.0 | 0 improved, 1 regressed, 1 both pass, 0 both fail |
| hard_conflict_resolution | 100.0 | 50.0 | 50.0 | 0 improved, 0 regressed, 1 both pass, 1 both fail |
| hard_cross_scope | 100.0 | 50.0 | 50.0 | 1 improved, 1 regressed, 0 both pass, 0 both fail |
| hard_duplicate_cleanup | 100.0 | 50.0 | 100.0 | 1 improved, 0 regressed, 1 both pass, 0 both fail |
| hard_graph_bridge | 100.0 | 100.0 | 50.0 | 0 improved, 1 regressed, 1 both pass, 0 both fail |
| hard_preference_recall | 100.0 | 100.0 | 100.0 | 0 improved, 0 regressed, 2 both pass, 0 both fail |
| hard_stale_sleep | 50.0 | 100.0 | 0.0 | 0 improved, 2 regressed, 0 both pass, 0 both fail |
| hard_style_preference | 100.0 | 100.0 | 50.0 | 0 improved, 1 regressed, 1 both pass, 0 both fail |
| hard_tool_preference | 100.0 | 100.0 | 100.0 | 0 improved, 0 regressed, 2 both pass, 0 both fail |
| hard_tri_rrf | 100.0 | 100.0 | 100.0 | 0 improved, 0 regressed, 2 both pass, 0 both fail |
| hard_version_chain | 0.0 | 100.0 | 100.0 | 0 improved, 0 regressed, 2 both pass, 0 both fail |

All categories have `memory_grounding_pass_rate = 100.0` and `forbidden_violation_rate = 0.0` for all three modes in this run.

## Relation To P6o-20 Answer Zero

P6o-20 produced `answer_rate = 0.0` because every real row timed out: `timeout_count = 120`, empty answers were scored as failed, and movement collapsed to `both_failed = 40`. That was an infra-blocked run, not evidence that Answer Candidate Contract + Post-check Retry Shadow failed.

P6o-24 resolves that diagnostic problem for the formal run:

- `timeout_count = 0`
- `provider_error_count = 0`
- `empty_answer_count = 0`
- checkpoint rows = `120`
- primary/rebuild metrics match
- nonzero answer data exists for all modes

Therefore the previous all-zero answer output is fixed for this fresh formal experiment path.

## Privacy Verification

The broad pattern scan only matched structured privacy flag names in the two JSON reports:

- `complete_response_included: false`
- `conversation_log_included: false`
- `raw_memory_summary_included: false`
- `raw_query_included: false`

Structured assertion checked both `system_path_safe_version_eval.json` files and confirmed all privacy flags are `false`:

- primary report checked: pass
- checkpoint rebuild report checked: pass
- `privacy_metric_files_checked = 2`

No raw query, raw prompt, raw answer, session text, memory summary, complete response, API key, authorization header, bearer token, `current_truth_lines`, or `must_include_terms` value was found in the committed report text or exported detail files.

## Conclusion

The formal experiment can now be interpreted. Retrieval/grounding is not the current bottleneck in this run: all modes have `memory_grounding_pass_rate = 100.0`, and forbidden violations are `0.0`.

The best answer-rate mode in this matrix is `safe_version_replace_guided` at `32/40 = 80.0%`. Baseline `safe_version_replace` is `30/40 = 75.0%`. `safe_version_replace_guided_with_retry_shadow` is `29/40 = 72.5%`, lower than guided by `7.5` percentage points.

Answer Candidate Contract + Post-check Retry Shadow is useful as a diagnostic surface because it identifies likely retry reasons (`answer_choice_group_missing`, `required_terms_missing`, and one language failure). But the current shadow wording/contract should not be promoted toward production default: it rescues `4` guided misses but regresses `7` guided passes, with a small token increase and no grounding/forbidden benefit.

Recommended next step: keep production default off and run a targeted answer-selection iteration over the `7` guided-pass -> retry-shadow-fail regressions and `4` retry-shadow rescues. The next modification should be eval-only and focus on reducing contract-induced answer omissions, especially hard stale/sleep, hard graph bridge, hard style preference, common tool preference, and common version-chain regressions.
