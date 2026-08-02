# Memory 综合线上评测报告

本报告使用真实 AgentLoop 的 answer-level 评测链路；如开启真实 LLM，则会记录真实模型回答的规则命中、记忆 grounding、token 和延迟。它不是生产回答准确率。

## 边界

- 常规报告不包含原始 query、memory summary、prompt、session 原文或完整回答。
- 真实 memory DB 只读采样只进入聚合指标，不写样本正文。
- 主表使用 answer、grounding 和 forbidden 的计数及比例；原始评分字段仅保留在 JSON 兼容输出中。

## 总览

- `evaluation_level`: `comprehensive_online_agentloop`
- `real_llm_enabled`: `True`
- `case_count`: `120`
- `unique_case_count`: `40`
- `completed_call_count`: `120`
- `skipped_from_checkpoint_count`: `0`
- `checkpoint_input_count`: `unavailable`
- `excluded_infra_failure_count`: `unavailable`
- `partial_due_to_infra_failure`: `unavailable`
- `checkpoint_report_only`: `unavailable`
- `concurrency`: `1`
- `profile_count`: `3`
- `prompt_variant_count`: `1`
- `repeat_count`: `1`
- `answer_rule_pass_rate`: `49.1667`
- `memory_grounding_pass_rate`: `100.0`
- `forbidden_violation_rate`: `8.3333`
- `avg_latency_ms`: `4565.5`
- `total_token_count`: `655992`
- `avg_total_token_count`: `5466.6`

## Profile Summary

| profile | cases | answer_success | grounding_success | forbidden_cases | answer_rate | grounding_rate | forbidden_rate | avg_tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_memory_base | 40 | 20 | 40 | 4 | 50 | 100 | 10 | 5486.7 |
| chain_tri_retrieval | 40 | 22 | 40 | 6 | 55 | 100 | 15 | 5529.875 |
| chain_tri_candidate_governance | 40 | 17 | 40 | 0 | 42.5 | 100 | 0 | 5383.225 |

## Answer Quality Uplift Vs Original Memory

`combo/check` marks `chain_all_on`; it is a combined verification row, not a pure single-module answer/retrieval gain.
| profile | cases | answer_pass | answer_rate | answer_lift | grounding_pass | grounding_rate | grounding_lift | forbidden_rate | forbidden_reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_memory_base | 40 | 20 | 50 | 0 | 40 | 100 | 0 | 10 | 0 |
| chain_tri_retrieval | 40 | 22 | 55 | 10 | 40 | 100 | 0 | 15 | -50 |
| chain_tri_candidate_governance | 40 | 17 | 42.5 | -15 | 40 | 100 | 0 | 0 | 100 |

## Chain Answer Quality Uplift

| profile | previous | answer_rate | adjacent_answer_delta | cumulative_answer_lift | grounding_rate | adjacent_grounding_delta | cumulative_grounding_lift |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_memory_base | unavailable | 50 | 0 | 0 | 100 | 0 | 0 |
| chain_tri_retrieval | chain_memory_base | 55 | 5 | 10 | 100 | 0 | 0 |
| chain_tri_candidate_governance | chain_tri_retrieval | 42.5 | -12.5 | -15 | 100 | 0 | 0 |

## Cost And Latency Observation

| profile | avg_tokens | token_overhead_vs_memory_base | token_reduction | avg_latency_ms | latency_overhead_ms | latency_reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_memory_base | 5486.7 | 0 | 0 | 4785.5 | 0 | 0 |
| chain_tri_retrieval | 5529.875 | 43.175 | -0.7869 | 4922.225 | 136.725 | -2.8571 |
| chain_tri_candidate_governance | 5383.225 | -103.475 | 1.8859 | 3988.775 | -796.725 | 16.6487 |

## Eval-Only Profile Metadata

| profile | eval_only | oracle_protected | uses_fixture_expected_ids |
| --- | ---: | ---: | ---: |
| chain_tri_candidate_governance | True | True | True |

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
