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
- `checkpoint_input_count`: `160`
- `excluded_infra_failure_count`: `0`
- `partial_due_to_infra_failure`: `False`
- `checkpoint_report_only`: `True`
- `concurrency`: `checkpoint_report_only`
- `profile_count`: `4`
- `prompt_variant_count`: `1`
- `repeat_count`: `1`
- `answer_rule_pass_rate`: `38.125`
- `memory_grounding_pass_rate`: `100.0`
- `forbidden_violation_rate`: `13.125`
- `avg_latency_ms`: `4390.7375`
- `total_token_count`: `877048`
- `avg_total_token_count`: `5481.55`

## Checkpoint Report Notes

- 本报告由 checkpoint 重建，没有继续发起新的 LLM 调用。
- `case_count` 只统计进入最终评分的有效样本。
- `checkpoint_input_count` 是 checkpoint 原始条数，`excluded_infra_failure_count` 是被排除的 timeout / provider error 条数。
- 如果 `partial_due_to_infra_failure = True`，只能视为部分真实线上评测，不能视为完整 2560-run 结论。

## Profile Summary

| profile | cases | answer_success | grounding_success | forbidden_cases | answer_rate | grounding_rate | forbidden_rate | avg_tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_memory_base | 40 | 13 | 40 | 6 | 32.5 | 100 | 15 | 5503.7 |
| chain_tri_retrieval | 40 | 17 | 40 | 5 | 42.5 | 100 | 12.5 | 5481.2 |
| chain_graph_retrieval | 40 | 13 | 40 | 6 | 32.5 | 100 | 15 | 5514.75 |
| chain_rerank_injection | 40 | 18 | 40 | 4 | 45 | 100 | 10 | 5426.55 |

## Answer Quality Uplift Vs Original Memory

`combo/check` marks `chain_all_on`; it is a combined verification row, not a pure single-module answer/retrieval gain.
| profile | cases | answer_pass | answer_rate | answer_lift | grounding_pass | grounding_rate | grounding_lift | forbidden_rate | forbidden_reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_memory_base | 40 | 13 | 32.5 | 0 | 40 | 100 | 0 | 15 | 0 |
| chain_tri_retrieval | 40 | 17 | 42.5 | 30.7692 | 40 | 100 | 0 | 12.5 | 16.6667 |
| chain_graph_retrieval | 40 | 13 | 32.5 | 0 | 40 | 100 | 0 | 15 | 0 |
| chain_rerank_injection | 40 | 18 | 45 | 38.4615 | 40 | 100 | 0 | 10 | 33.3333 |

## Chain Answer Quality Uplift

| profile | previous | answer_rate | adjacent_answer_delta | cumulative_answer_lift | grounding_rate | adjacent_grounding_delta | cumulative_grounding_lift |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_memory_base | unavailable | 32.5 | 0 | 0 | 100 | 0 | 0 |
| chain_tri_retrieval | chain_memory_base | 42.5 | 10 | 30.7692 | 100 | 0 | 0 |
| chain_graph_retrieval | chain_tri_retrieval | 32.5 | -10 | 0 | 100 | 0 | 0 |
| chain_rerank_injection | chain_graph_retrieval | 45 | 12.5 | 38.4615 | 100 | 0 | 0 |

## Cost And Latency Observation

| profile | avg_tokens | token_overhead_vs_memory_base | token_reduction | avg_latency_ms | latency_overhead_ms | latency_reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_memory_base | 5503.7 | 0 | 0 | 4678.825 | 0 | 0 |
| chain_tri_retrieval | 5481.2 | -22.5 | 0.4088 | 4082.825 | -596 | 12.7382 |
| chain_graph_retrieval | 5514.75 | 11.05 | -0.2008 | 4465.575 | -213.25 | 4.5578 |
| chain_rerank_injection | 5426.55 | -77.15 | 1.4018 | 4335.725 | -343.1 | 7.333 |

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

## 本轮人工解读

这轮是 `20 common + 20 hard` 的 `40` case 小型真实 LLM 评测，只用于判断 route governance 后的当前回答链路是否值得继续扩测。它不能替代 `320 case / 1920 call` 的完整矩阵，也不能单独证明生产全量收益。

| profile | cases | answer_rate | grounding_rate | forbidden_rate | avg_total_token_count | avg_latency_ms | conclusion |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `chain_memory_base` | 40 | `32.5%` | `100%` | `15%` | `5503.7` | `4678.825` | 原始记忆基线，本轮作为增益参照 |
| `chain_tri_retrieval` | 40 | `42.5%` | `100%` | `12.5%` | `5481.2` | `4082.825` | 回答命中相对基线提升 `30.7692%`，forbidden 相对降低 `16.6667%` |
| `chain_graph_retrieval` | 40 | `32.5%` | `100%` | `15%` | `5514.75` | `4465.575` | 本轮与基线持平，图谱仍需要场景路由和去噪 |
| `chain_rerank_injection` | 40 | `45%` | `100%` | `10%` | `5426.55` | `4335.725` | 回答命中相对基线提升 `38.4615%`，forbidden 相对降低 `33.3333%`，是本轮最稳增强路径 |

本轮结论是：三路召回经过场景路由后，小样本表现从旧完整矩阵里的负向趋势转为正向；重排与注入治理同时提升回答命中并降低 forbidden，最值得优先扩测。图谱召回本轮没有超过基线，但当前 answer-quality fixture 中 `chain_graph_retrieval` 和 `chain_tri_retrieval` 的 evidence ids 没有充分隔离，所以图谱行只能解释为当前 profile 口径下没有超过基线，不能单独证明图谱能力无效；后续需要补图谱专用 case 或让 graph profile 输出可区分证据，再优化触发条件、候选去噪和证据注入约束。
