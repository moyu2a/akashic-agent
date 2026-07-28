# Memory 综合线上评测报告

本报告使用真实 AgentLoop 的 answer-level 评测链路；如开启真实 LLM，则会记录真实模型回答的规则命中、记忆 grounding、token 和延迟。它不是生产回答准确率。

## 边界

- 常规报告不包含原始 query、memory summary、prompt、session 原文或完整回答。
- 真实 memory DB 只读采样只进入聚合指标，不写样本正文。
- 主表使用 answer、grounding 和 forbidden 的计数及比例；原始评分字段仅保留在 JSON 兼容输出中。

## 总览

- `evaluation_level`: `comprehensive_online_agentloop`
- `real_llm_enabled`: `True`
- `case_count`: `160`
- `unique_case_count`: `40`
- `completed_call_count`: `160`
- `skipped_from_checkpoint_count`: `0`
- `checkpoint_input_count`: `unavailable`
- `excluded_infra_failure_count`: `unavailable`
- `partial_due_to_infra_failure`: `unavailable`
- `checkpoint_report_only`: `unavailable`
- `concurrency`: `1`
- `profile_count`: `4`
- `prompt_variant_count`: `1`
- `repeat_count`: `1`
- `answer_rule_pass_rate`: `50.625`
- `memory_grounding_pass_rate`: `100.0`
- `forbidden_violation_rate`: `8.125`
- `avg_latency_ms`: `3921.9625`
- `total_token_count`: `884766`
- `avg_total_token_count`: `5529.7875`

## Profile Summary

| profile | cases | answer_success | grounding_success | forbidden_cases | answer_rate | grounding_rate | forbidden_rate | avg_tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_memory_base | 40 | 14 | 40 | 3 | 35 | 100 | 7.5 | 5499.525 |
| chain_tri_retrieval | 40 | 16 | 40 | 5 | 40 | 100 | 12.5 | 5492.15 |
| chain_tri_candidate_governance | 40 | 21 | 40 | 0 | 52.5 | 100 | 0 | 5428.85 |
| chain_tri_answer_contract | 40 | 30 | 40 | 5 | 75 | 100 | 12.5 | 5698.625 |

## Answer Quality Uplift Vs Original Memory

`combo/check` marks `chain_all_on`; it is a combined verification row, not a pure single-module answer/retrieval gain.
| profile | cases | answer_pass | answer_rate | answer_lift | grounding_pass | grounding_rate | grounding_lift | forbidden_rate | forbidden_reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_memory_base | 40 | 14 | 35 | 0 | 40 | 100 | 0 | 7.5 | 0 |
| chain_tri_retrieval | 40 | 16 | 40 | 14.2857 | 40 | 100 | 0 | 12.5 | -66.6667 |
| chain_tri_candidate_governance | 40 | 21 | 52.5 | 50 | 40 | 100 | 0 | 0 | 100 |
| chain_tri_answer_contract | 40 | 30 | 75 | 114.2857 | 40 | 100 | 0 | 12.5 | -66.6667 |

## Chain Answer Quality Uplift

| profile | previous | answer_rate | adjacent_answer_delta | cumulative_answer_lift | grounding_rate | adjacent_grounding_delta | cumulative_grounding_lift |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_memory_base | unavailable | 35 | 0 | 0 | 100 | 0 | 0 |
| chain_tri_retrieval | chain_memory_base | 40 | 5 | 14.2857 | 100 | 0 | 0 |
| chain_tri_candidate_governance | chain_tri_retrieval | 52.5 | 12.5 | 50 | 100 | 0 | 0 |
| chain_tri_answer_contract | chain_tri_candidate_governance | 75 | 22.5 | 114.2857 | 100 | 0 | 0 |

## Cost And Latency Observation

| profile | avg_tokens | token_overhead_vs_memory_base | token_reduction | avg_latency_ms | latency_overhead_ms | latency_reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_memory_base | 5499.525 | 0 | 0 | 4152.275 | 0 | 0 |
| chain_tri_retrieval | 5492.15 | -7.375 | 0.1341 | 3768.3 | -383.975 | 9.2473 |
| chain_tri_candidate_governance | 5428.85 | -70.675 | 1.2851 | 3869.3 | -282.975 | 6.8149 |
| chain_tri_answer_contract | 5698.625 | 199.1 | -3.6203 | 3897.975 | -254.3 | 6.1244 |

## Eval-Only Profile Metadata

| profile | eval_only | oracle_protected | uses_fixture_expected_ids | diagnostic_answer_contract | uses_fixture_answer_expectations |
| --- | ---: | ---: | ---: | ---: | ---: |
| chain_tri_answer_contract | True | unavailable | unavailable | True | True |
| chain_tri_candidate_governance | True | True | True | unavailable | unavailable |

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
