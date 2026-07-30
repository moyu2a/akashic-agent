# P6o-21 Provider Timeout Diagnosis

## Objective

定位 P6o-20 前两次 real-LLM 测试 `answer_rate = 0` 的原因，区分 provider 不可用、eval wrapper 超时、checkpoint/resume 污染和真实 answer 质量问题。

## Tests

### 1. Direct provider smoke

Script: `/tmp/akashic_provider_smoke.py`

Command:

```bash
PYTHONPATH=/home/jjh/git_work/akashic-agent/.worktrees/memory-next .venv/bin/python /tmp/akashic_provider_smoke.py
```

Result:

| variant | max_tokens | content_len | thinking_len | elapsed_ms | interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| config_extra_body_16 | 16 | 0 | 67 | 1104 | thinking consumed the small output budget; no final content |
| config_extra_body_1024 | 1024 | 2 | 107 | 804 | provider returned final content |
| no_extra_body_16 | 16 | 0 | 71 | 918 | default DeepSeek thinking still consumed the small budget |
| no_extra_body_1024 | 1024 | 2 | 77 | 690 | provider returned final content |
| force_disable_thinking_16 | 16 | 2 | 0 | 584 | disabling thinking allows short completions |

Conclusion: provider connectivity is currently working. Empty direct answers can be caused by too-small `max_tokens` when DeepSeek emits reasoning. This is not the main P6o-20 eval failure because `AgentLoop` uses `LLMConfig.max_tokens = 8192` in the system-path eval.

### 2. Single-case eval, current config, timeout 30

Command:

```bash
.venv/bin/python scripts/run_memory_system_path_safe_version_eval.py --workspace /tmp/akashic-p6o-debug-current/workspace --out-dir /tmp/akashic-p6o-debug-current/out --config /home/jjh/git_work/akashic-agent/config.toml --enable-real-llm --case-pack standard --limit 1 --modes safe_version_replace --timeout-s 30
```

Result:

| metric | value |
| --- | ---: |
| case_count | 1 |
| timeout_count | 0 |
| provider_error_count | 0 |
| answer_length | 660 |
| answer_rule_passed | true |
| token_metrics_available | true |
| latency_ms | 6102 |

Conclusion: the full eval wrapper can currently produce real answers with a 30s timeout.

### 3. Single-case eval, current config, timeout 5

Command:

```bash
.venv/bin/python scripts/run_memory_system_path_safe_version_eval.py --workspace /tmp/akashic-p6o-debug-sandbox/workspace --out-dir /tmp/akashic-p6o-debug-sandbox/out --config /home/jjh/git_work/akashic-agent/config.toml --enable-real-llm --case-pack standard --limit 1 --modes safe_version_replace --timeout-s 5
```

Result:

| metric | value |
| --- | ---: |
| case_count | 1 |
| timeout_count | 1 |
| provider_error_count | 0 |
| answer_length | 0 |
| token_metrics_available | false |
| latency_ms | 5006 |

Conclusion: 5s is too short for this eval path on at least some cases; timeout rows produce empty answers and false quality failures.

### 4. Single-case eval, current config, timeout 30, same sandbox

Command:

```bash
.venv/bin/python scripts/run_memory_system_path_safe_version_eval.py --workspace /tmp/akashic-p6o-debug-sandbox30/workspace --out-dir /tmp/akashic-p6o-debug-sandbox30/out --config /home/jjh/git_work/akashic-agent/config.toml --enable-real-llm --case-pack standard --limit 1 --modes safe_version_replace --timeout-s 30
```

Result:

| metric | value |
| --- | ---: |
| case_count | 1 |
| timeout_count | 0 |
| provider_error_count | 0 |
| answer_length | 672 |
| answer_rule_passed | false |
| token_metrics_available | true |
| latency_ms | 5424 |

Conclusion: with 30s timeout, the same path produces a real answer. This run is a quality miss, not infra failure.

### 5. Fresh mini matrix, timeout 30

Command:

```bash
.venv/bin/python scripts/run_memory_system_path_safe_version_eval.py --workspace /tmp/akashic-p6o-debug-mini-matrix/workspace --out-dir /tmp/akashic-p6o-debug-mini-matrix/out --config /home/jjh/git_work/akashic-agent/config.toml --enable-real-llm --case-pack standard --limit 3 --modes safe_version_replace,safe_version_replace_guided,safe_version_replace_guided_with_retry_shadow --timeout-s 30 --checkpoint-jsonl /tmp/akashic-p6o-debug-mini-matrix/checkpoint.jsonl
```

Result:

| metric | value |
| --- | ---: |
| case_count | 9 |
| unique_case_count | 3 |
| timeout_count | 0 |
| provider_error_count | 0 |
| answer_rule_pass_rate | 33.3333 |
| memory_grounding_pass_rate | 100.0 |
| token_metrics_available | true |
| avg_latency_ms | 3116.0 |

Mode summary:

| mode | cases | answer_rate | avg_latency_ms | retry_shadow_would_retry |
| --- | ---: | ---: | ---: | ---: |
| safe_version_replace | 3 | 66.6667 | 3085.3333 | 0 |
| safe_version_replace_guided | 3 | 0.0 | 3536.6667 | 0 |
| safe_version_replace_guided_with_retry_shadow | 3 | 33.3333 | 2726.0 | 2 |

Conclusion: a fresh small matrix currently produces non-empty answer data. The answer metrics are usable for debugging quality, unlike the P6o-20 timeout-only run.

## P6o-20 Checkpoint Forensics

Checkpoint:

`my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/real_small_ab/checkpoint.jsonl`

Stats:

| metric | value |
| --- | ---: |
| physical_lines | 151 |
| unique_specs | 120 |
| duplicate_spec_keys | 31 |
| timeout_rows | 151 |
| provider_error_rows | 0 |
| rows_around_30s_timeout | 31 |
| rows_around_1s_timeout | 120 |

Mode timeout counts:

| mode | timeout_rows |
| --- | ---: |
| safe_version_replace | 51 |
| safe_version_replace_guided | 50 |
| safe_version_replace_guided_with_retry_shadow | 50 |

Mechanism:

- The first interrupted P6o-20 run wrote about 31 timeout rows at roughly 30 seconds each.
- The resumed run was executed with `--timeout-s 1`, which is below observed normal latency for this eval path.
- Resume intentionally does not treat infra-failure rows as reusable successes, so those specs were retried.
- The 1s resumed run wrote 120 timeout rows.
- Checkpoint rebuild includes infra failures and keeps the last row per spec key, so the 1s timeout rows dominate the rebuilt 120-case report.

## Conclusion

The previous all-zero P6o-20 answer results were caused by infra/checkpoint conditions, not by answer quality:

- `answer_rate = 0` came from timeout rows with empty answers.
- The 1s resume timeout was guaranteed to produce invalid quality data for this path.
- Current fresh runs with timeout 30 produce real answer text and token metrics.
- Direct provider can return empty content when `max_tokens` is too small and thinking consumes the output budget, but system-path eval uses a larger token budget and is not blocked by that in the current smoke tests.

## Next Step

Before rerunning P6o-20, use a fresh checkpoint/out-dir and keep timeout at least 30 seconds. Add an early infra abort guard: if the first few rows have timeout/provider_error rate above threshold, stop the run and mark `infra_blocked` instead of filling the checkpoint with invalid quality rows.

## P6o-22 Retest

### Fix

Implemented an eval-only infra guard for `scripts/run_memory_system_path_safe_version_eval.py` and `memory2/eval_system_path_safe_version.py`.

Behavior:

- Fresh runs can pass `--early-infra-abort-count N` and `--early-infra-abort-rate R`.
- Once at least `N` fresh rows exist, the runner checks cumulative fresh-row timeout/provider-error rate.
- If the rate meets or exceeds `R`, the run stops early and writes `blocked_status.json`.
- `blocked_status.json` sets `status=infra_blocked` and `quality_interpretation_allowed=false`.
- `--checkpoint-report-only` can now also mark timeout/provider-error-heavy checkpoint rebuilds as blocked.
- Production memory defaults, retrieval, prompts, retry behavior, graph behavior, and memory writes are unchanged.

### Verification Commands

Focused tests:

```bash
.venv/bin/python -m pytest tests/test_memory_system_path_safe_version_eval.py tests/test_memory_answer_post_check.py tests/test_memory_system_path_safe_version_contract.py -q -p no:cacheprovider
```

Result after adding the checkpoint-report-only guard regression: `41 passed in 28.13s`.

Compile:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m compileall memory2/eval_system_path_safe_version.py scripts/run_memory_system_path_safe_version_eval.py tests/test_memory_system_path_safe_version_eval.py
```

Result: exit `0`.

### Old P6o-20 Checkpoint Guarded Rebuild

Command:

```bash
.venv/bin/python scripts/run_memory_system_path_safe_version_eval.py --out-dir my_md/memory_optimization/eval_reports/p6o22_infra_abort_guard_v1/p6o20_checkpoint_guarded_rebuild --enable-real-llm --checkpoint-jsonl my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/real_small_ab/checkpoint.jsonl --checkpoint-report-only --early-infra-abort-count 3 --early-infra-abort-rate 0.5
```

Result: exit `2`, as expected. The same old P6o-20 checkpoint that previously rebuilt into an all-zero quality-looking report is now explicitly marked infra-blocked.

Blocked status:

| metric | value |
| --- | ---: |
| status | infra_blocked |
| quality_interpretation_allowed | false |
| case_count | 120 |
| unique_case_count | 40 |
| checkpoint_line_count | 151 |
| timeout_count | 120 |
| provider_error_count | 0 |
| checkpoint_input_count | 151 |

Reason: `checkpoint infra failure rate 100.0% met or exceeded 50.0%`.

### Fake Infra Abort Smoke

Command:

```bash
.venv/bin/python scripts/run_memory_system_path_safe_version_eval.py --workspace /tmp/akashic-p6o22-infra-abort-fake/workspace --out-dir my_md/memory_optimization/eval_reports/p6o22_infra_abort_guard_v1/fake_abort --fake-provider --fake-provider-delay-s 0.05 --case-pack standard --limit 2 --modes safe_version_replace --timeout-s 0.001 --checkpoint-jsonl my_md/memory_optimization/eval_reports/p6o22_infra_abort_guard_v1/fake_abort/checkpoint.jsonl --early-infra-abort-count 1 --early-infra-abort-rate 1.0
```

Result: exit `2`, as expected for an infra-blocked run.

Blocked status:

| metric | value |
| --- | ---: |
| status | infra_blocked |
| quality_interpretation_allowed | false |
| case_count | 1 |
| unique_case_count | 2 |
| checkpoint_line_count | 1 |
| timeout_count | 1 |
| provider_error_count | 0 |
| fresh_case_count | 1 |
| fresh_timeout_count | 1 |
| fresh_provider_error_count | 0 |
| early_infra_abort_count | 1 |
| early_infra_abort_rate | 1.0 |

Reason: `early infra failure rate 100.0% met or exceeded 100.0%`.

### Fresh Real Mini Matrix

Command:

```bash
.venv/bin/python scripts/run_memory_system_path_safe_version_eval.py --workspace /tmp/akashic-p6o22-real-mini/workspace --out-dir my_md/memory_optimization/eval_reports/p6o22_infra_abort_guard_v1/real_mini --config /home/jjh/git_work/akashic-agent/config.toml --enable-real-llm --case-pack standard --limit 3 --modes safe_version_replace,safe_version_replace_guided,safe_version_replace_guided_with_retry_shadow --timeout-s 30 --checkpoint-jsonl my_md/memory_optimization/eval_reports/p6o22_infra_abort_guard_v1/real_mini/checkpoint.jsonl --early-infra-abort-count 3 --early-infra-abort-rate 0.5
```

Result: exit `0`; no `blocked_status.json` was written.

Primary metrics:

| metric | value |
| --- | ---: |
| case_count | 9 |
| unique_case_count | 3 |
| checkpoint_line_count | 9 |
| timeout_count | 0 |
| provider_error_count | 0 |
| answer_rule_pass_rate | 44.4444 |
| memory_grounding_pass_rate | 100.0 |
| token_metrics_available | true |
| avg_latency_ms | 4423.4444 |

Mode summary:

| mode | cases | answer_success | answer_rate | grounding_rate | forbidden_rate | avg_latency_ms | retry_shadow_would_retry |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| safe_version_replace | 3 | 2 | 66.6667 | 100.0 | 0.0 | 5606.6667 | 0 |
| safe_version_replace_guided | 3 | 1 | 33.3333 | 100.0 | 0.0 | 4172.3333 | 0 |
| safe_version_replace_guided_with_retry_shadow | 3 | 1 | 33.3333 | 100.0 | 0.0 | 3491.3333 | 2 |

Per-row answer lengths:

| case_id | mode | answer_passed | answer_length | timeout | provider_error |
| --- | --- | --- | ---: | --- | --- |
| common_preference_recall_01 | safe_version_replace | true | 91 | false | false |
| common_preference_recall_01 | safe_version_replace_guided | false | 30 | false | false |
| common_preference_recall_01 | safe_version_replace_guided_with_retry_shadow | false | 184 | false | false |
| common_tool_preference_01 | safe_version_replace | false | 7 | false | false |
| common_tool_preference_01 | safe_version_replace_guided | false | 7 | false | false |
| common_tool_preference_01 | safe_version_replace_guided_with_retry_shadow | false | 7 | false | false |
| common_style_preference_01 | safe_version_replace | true | 34 | false | false |
| common_style_preference_01 | safe_version_replace_guided | true | 53 | false | false |
| common_style_preference_01 | safe_version_replace_guided_with_retry_shadow | true | 79 | false | false |

### P6o-22 Conclusion

The earlier all-zero P6o-20 data is confirmed invalid for answer-quality interpretation. The failure mode was an infra/checkpoint issue: timeout rows, especially the 1s resumed rows, were rebuilt into a normal-looking report.

The corrected runner now separates the two states:

- Infra-heavy runs stop early and write `blocked_status.json` with `quality_interpretation_allowed=false`.
- Fresh healthy runs produce non-empty answer rows, token metrics, and usable quality data.

The next full P6o-20 rerun should use a fresh out-dir/checkpoint, `--timeout-s 30` or higher, and the P6o-22 guard. If it blocks, the result should be treated as infra_blocked. If it exits 0 with `timeout_count=0` and `provider_error_count=0`, then answer quality can be interpreted.
