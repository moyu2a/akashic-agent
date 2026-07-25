# Memory 综合线上评测报告

本报告使用真实 AgentLoop 的 answer-level 评测链路；如开启真实 LLM，则会记录真实模型回答的规则命中、记忆 grounding、token 和延迟。它不是生产回答准确率。

## 边界

- 常规报告不包含原始 query、memory summary、prompt、session 原文或完整回答。
- 真实 memory DB 只读采样只进入聚合指标，不写样本正文。
- profile uplift 是受控评测集上的 answer-level / proxy 指标，不代表线上全量结论。

## 总览

- `evaluation_level`: `comprehensive_online_agentloop`
- `real_llm_enabled`: `True`
- `case_count`: `1417`
- `unique_case_count`: `45`
- `completed_call_count`: `1417`
- `skipped_from_checkpoint_count`: `0`
- `checkpoint_input_count`: `1599`
- `excluded_infra_failure_count`: `182`
- `partial_due_to_infra_failure`: `True`
- `checkpoint_report_only`: `True`
- `concurrency`: `checkpoint_report_only`
- `profile_count`: `8`
- `prompt_variant_count`: `2`
- `repeat_count`: `2`
- `answer_rule_pass_rate`: `31.1927`
- `memory_grounding_pass_rate`: `62.4559`
- `forbidden_violation_rate`: `16.302`
- `avg_latency_ms`: `4976.7276`
- `total_token_count`: `7600606`
- `avg_total_token_count`: `5363.8716`

## Checkpoint Report Notes

- 本报告由 checkpoint 重建，没有继续发起新的 LLM 调用。
- `case_count` 只统计进入最终评分的有效样本。
- `checkpoint_input_count` 是 checkpoint 原始条数，`excluded_infra_failure_count` 是被排除的 timeout / provider error 条数。
- 如果 `partial_due_to_infra_failure = True`，只能视为部分真实线上评测，不能视为完整 2560-run 结论。

## Profile Summary

| profile | main_score | uplift_vs_off | adjacent_uplift | answer | grounding | forbidden | avg_tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_off | 18.4269 | 0 | 0 | 12.9213 | 0 | 6.1798 | 5237.9719 |
| chain_write_value | 18.0791 | -0.3478 | -0.3478 | 12.4294 | 0 | 6.2147 | 5214.5198 |
| chain_tri_retrieval | 53.9548 | 35.5279 | 35.8757 | 38.4181 | 100 | 29.3785 | 5537.2825 |
| chain_graph_retrieval | 54.8588 | 36.4319 | 0.904 | 38.9831 | 100 | 24.2938 | 5500.7627 |
| chain_rerank_injection | 61.5819 | 43.155 | 6.7231 | 46.3277 | 100 | 8.4746 | 5366.2147 |
| chain_version_provenance | 42.3729 | 23.946 | -19.209 | 46.3277 | 0 | 0.565 | 5269.6441 |
| chain_sleep_consolidation | 47.0057 | 28.5788 | 4.6328 | 28.2486 | 100 | 27.6836 | 5412.1469 |
| chain_all_on | 45.4237 | 26.9968 | -1.582 | 25.9887 | 100 | 27.6836 | 5373.1412 |

## Online Balanced Proxy Summary

| profile | balanced_proxy | adjacent_delta | answer | grounding | governance | efficiency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_off | 28.8221 | 0 | 12.9213 | 0 | 51.6011 | 100 |
| chain_write_value | 28.6527 | -0.1694 | 12.4294 | 0 | 51.5819 | 100.2345 |
| chain_tri_retrieval | 63.4069 | 34.7542 | 38.4181 | 100 | 83.8418 | 97.0069 |
| chain_graph_retrieval | 64.1737 | 0.7668 | 38.9831 | 100 | 86.6384 | 97.3721 |
| chain_rerank_injection | 69.6528 | 5.4791 | 46.3277 | 100 | 95.339 | 98.7176 |
| chain_version_provenance | 43.652 | -26.0008 | 46.3277 | 0 | 54.6893 | 99.6833 |
| chain_sleep_consolidation | 58.0787 | 14.4267 | 28.2486 | 100 | 84.774 | 98.2583 |
| chain_all_on | 56.8747 | -1.204 | 25.9887 | 100 | 84.774 | 98.6483 |

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
- 本轮有效样本里，三路召回、图谱召回、重排注入治理更适合用 answer-level 主分评估；写入价值和睡眠巩固应使用专项治理指标评估。
- `chain_write_value` 相对关闭为 `-0.3478`，不能解读为写入价值无效。它不直接向当前回答注入证据，主要价值应体现在污染率、重复率、误写率和后续召回可用性。
- `chain_sleep_consolidation` answer-level 相邻 `+4.6328`，balanced proxy 相邻 `+14.4267`。它的重点不是即时回答，而是重复合并、过期降权、低价值清理、token 节省和关键记忆保护。

## 写入价值专项评测建议

写入价值应按“候选记忆 -> allow / reject / reason -> 后续召回验证”评测。

建议关注：

- `policy_allow_count`
- `policy_reject_count`
- `reject_reason_distribution`
- `temporary_reject_count`
- `assistant_inference_reject_count`
- `duplicate_risk_count`
- `write_reduction_rate`
- `memory_pollution_rate`
- `useful_memory_precision`
- `false_reject_rate`
- `false_accept_rate`
- `future_recall_usefulness`

判断标准：污染率下降、重复率下降、临时信息和 assistant 推断被拒写，同时稳定偏好和长期约束没有被误拒。

## 睡眠巩固专项评测建议

睡眠巩固应按“memory DB 快照 before/after”评测，第一步仍保持 dry-run，active 试验只在临时克隆 DB 上运行。

建议关注：

- `scanned_count`
- `duplicate_group_count`
- `merge_candidate_count`
- `stale_candidate_count`
- `low_value_candidate_count`
- `conflict_candidate_count`
- `missing_source_ref_count`
- `estimated_token_saving`
- `estimated_redundancy_drop`
- `before_active_count` / `after_active_count`
- `post_consolidation_recall_precision`
- `post_consolidation_wrong_recall_rate`
- `protected_memory_recall_rate`
- `prompt_token_delta`

判断标准：在关键记忆不丢失的前提下，重复、过期、低价值注入减少，prompt token 成本下降，检索结果更集中。
