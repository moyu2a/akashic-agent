# Memory 综合线上评测报告

本报告使用真实 AgentLoop 的 answer-level 评测链路；如开启真实 LLM，则会记录真实模型回答的规则命中、记忆 grounding、token 和延迟。它不是生产回答准确率。

## 边界

- 常规报告不包含原始 query、memory summary、prompt、session 原文或完整回答。
- 真实 memory DB 只读采样只进入聚合指标，不写样本正文。
- 主表使用 answer、grounding 和 forbidden 的计数及比例；原始评分字段仅保留在 JSON 兼容输出中。

## 总览

- `evaluation_level`: `comprehensive_online_agentloop`
- `real_llm_enabled`: `True`
- `case_count`: `1920`
- `unique_case_count`: `320`
- `completed_call_count`: `1920`
- `skipped_from_checkpoint_count`: `0`
- `checkpoint_input_count`: `1920`
- `excluded_infra_failure_count`: `0`
- `partial_due_to_infra_failure`: `False`
- `checkpoint_report_only`: `True`
- `concurrency`: `checkpoint_report_only`
- `profile_count`: `6`
- `prompt_variant_count`: `1`
- `repeat_count`: `1`
- `answer_rule_pass_rate`: `33.3854`
- `memory_grounding_pass_rate`: `82.7083`
- `forbidden_violation_rate`: `17.8646`
- `avg_latency_ms`: `4350.3875`
- `total_token_count`: `10593288`
- `avg_total_token_count`: `5517.3375`

## Checkpoint Report Notes

- 本报告由 checkpoint 重建，没有继续发起新的 LLM 调用。
- `case_count` 只统计进入最终评分的有效样本。
- `checkpoint_input_count` 是 checkpoint 原始条数，`excluded_infra_failure_count` 是被排除的 timeout / provider error 条数。
- 如果 `partial_due_to_infra_failure = True`，只能视为部分真实线上评测，不能视为完整 2560-run 结论。

## Profile Summary

| profile | cases | answer_success | grounding_success | forbidden_cases | answer_rate | grounding_rate | forbidden_rate | avg_tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_memory_base | 320 | 135 | 308 | 39 | 42.1875 | 96.25 | 12.1875 | 5516.5031 |
| chain_tri_retrieval | 320 | 91 | 320 | 96 | 28.4375 | 100 | 30 | 5643.0594 |
| chain_graph_retrieval | 320 | 84 | 320 | 95 | 26.25 | 100 | 29.6875 | 5610.6375 |
| chain_rerank_injection | 320 | 127 | 320 | 31 | 39.6875 | 100 | 9.6875 | 5448.5844 |
| chain_version_provenance | 320 | 129 | 0 | 3 | 40.3125 | 0 | 0.9375 | 5401.2 |
| chain_all_on | 320 | 75 | 320 | 79 | 23.4375 | 100 | 24.6875 | 5484.0406 |

## Answer Quality Uplift Vs Original Memory

`combo/check` marks `chain_all_on`; it is a combined verification row, not a pure single-module answer/retrieval gain.
| profile | cases | answer_pass | answer_rate | answer_lift | grounding_pass | grounding_rate | grounding_lift | forbidden_rate | forbidden_reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_memory_base | 320 | 135 | 42.1875 | 0 | 308 | 96.25 | 0 | 12.1875 | 0 |
| chain_tri_retrieval | 320 | 91 | 28.4375 | -32.5926 | 320 | 100 | 3.8961 | 30 | -146.1538 |
| chain_graph_retrieval | 320 | 84 | 26.25 | -37.7778 | 320 | 100 | 3.8961 | 29.6875 | -143.5897 |
| chain_rerank_injection | 320 | 127 | 39.6875 | -5.9259 | 320 | 100 | 3.8961 | 9.6875 | 20.5128 |
| chain_version_provenance | 320 | 129 | 40.3125 | -4.4444 | 0 | 0 | -100 | 0.9375 | 92.3077 |
| chain_all_on (combo/check) | 320 | 75 | 23.4375 | -44.4444 | 320 | 100 | 3.8961 | 24.6875 | -102.5641 |

## Chain Answer Quality Uplift

| profile | previous | answer_rate | adjacent_answer_delta | cumulative_answer_lift | grounding_rate | adjacent_grounding_delta | cumulative_grounding_lift |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_memory_base | unavailable | 42.1875 | 0 | 0 | 96.25 | 0 | 0 |
| chain_tri_retrieval | chain_memory_base | 28.4375 | -13.75 | -32.5926 | 100 | 3.75 | 3.8961 |
| chain_graph_retrieval | chain_tri_retrieval | 26.25 | -2.1875 | -37.7778 | 100 | 0 | 3.8961 |
| chain_rerank_injection | chain_graph_retrieval | 39.6875 | 13.4375 | -5.9259 | 100 | 0 | 3.8961 |
| chain_version_provenance | chain_rerank_injection | 40.3125 | 0.625 | -4.4444 | 0 | -100 | -100 |
| chain_all_on (combo/check) | chain_version_provenance | 23.4375 | -16.875 | -44.4444 | 100 | 100 | 3.8961 |

## Cost And Latency Observation

| profile | avg_tokens | token_overhead_vs_memory_base | token_reduction | avg_latency_ms | latency_overhead_ms | latency_reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_memory_base | 5516.5031 | 0 | 0 | 4277.2969 | 0 | 0 |
| chain_tri_retrieval | 5643.0594 | 126.5563 | -2.2941 | 4868.2594 | 590.9625 | -13.8163 |
| chain_graph_retrieval | 5610.6375 | 94.1344 | -1.7064 | 4543.1875 | 265.8906 | -6.2163 |
| chain_rerank_injection | 5448.5844 | -67.9187 | 1.2312 | 3904.0813 | -373.2156 | 8.7255 |
| chain_version_provenance | 5401.2 | -115.3031 | 2.0901 | 4078.6281 | -198.6688 | 4.6447 |
| chain_all_on (combo/check) | 5484.0406 | -32.4625 | 0.5885 | 4430.8719 | 153.575 | -3.5905 |

## 原始评分字段

- `main_score`、profile uplift 和 online balanced proxy 保留在 JSON 输出中以兼容既有消费者，不作为本报告主表的解释口径。

## Metric Sources

- `online_answer_level`: real AgentLoop answer scoring
- `online_balanced_proxy`: online answer-level fields converted into balanced proxy dimensions
- `offline_retrieval_proxy`: existing offline trace retrieval metrics
- `real_db_readonly_sampling_background`: aggregate-only real memory DB sampling status

## Real Memory Readonly Sampling

- `cross_scope_sample_unavailable`: `1`
- `invalid_extra_json_count`: `0`
- `memory_item_count`: `0`
- `missing_scope_count`: `0`
- `missing_table_count`: `1`
- `replacement_count`: `0`
- `sample_count`: `0`
- `usable_memory_item_count`: `0`
- `version_chain_sample_unavailable`: `1`

## 结论

- 如果某个中后段 profile 的 answer-level 增益不明显，需要结合 offline retrieval proxy 和 online balanced proxy 看治理、证据和效率价值。
