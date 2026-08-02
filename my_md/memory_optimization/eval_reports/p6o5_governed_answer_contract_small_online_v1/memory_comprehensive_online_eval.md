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
- `answer_rule_pass_rate`: `66.25`
- `memory_grounding_pass_rate`: `100.0`
- `forbidden_violation_rate`: `10.625`
- `avg_latency_ms`: `4744.6062`
- `total_token_count`: `913016`
- `avg_total_token_count`: `5706.35`

## Profile Summary

| profile | cases | answer_success | grounding_success | forbidden_cases | answer_rate | grounding_rate | forbidden_rate | avg_tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_tri_retrieval | 40 | 15 | 40 | 5 | 37.5 | 100 | 12.5 | 5518.825 |
| chain_tri_candidate_governance | 40 | 20 | 40 | 6 | 50 | 100 | 15 | 5538.125 |
| chain_tri_answer_contract | 40 | 32 | 40 | 6 | 80 | 100 | 15 | 5688.775 |
| chain_tri_governed_answer_contract | 40 | 39 | 40 | 0 | 97.5 | 100 | 0 | 6079.675 |

## Answer Quality Uplift Vs Original Memory

`combo/check` marks `chain_all_on`; it is a combined verification row, not a pure single-module answer/retrieval gain.
- No answer-quality uplift rows available.

## Chain Answer Quality Uplift

- No chain answer-quality uplift rows available.

## Cost And Latency Observation

| profile | avg_tokens | token_overhead_vs_memory_base | token_reduction | avg_latency_ms | latency_overhead_ms | latency_reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |

## Eval-Only Profile Metadata

| profile | eval_only | oracle_protected | uses_fixture_expected_ids | diagnostic_answer_contract | uses_fixture_answer_expectations | production_safe_evidence_contract | combines_candidate_governance |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_tri_answer_contract | True | unavailable | unavailable | True | True | unavailable | unavailable |
| chain_tri_candidate_governance | True | True | True | unavailable | unavailable | unavailable | unavailable |
| chain_tri_governed_answer_contract | True | True | True | True | False | True | True |

## Answer Post-Check Shadow

- `case_count`: `40`
- `enabled_case_count`: `40`
- `needs_retry_count`: `0`
- `forbidden_boundary_included_count`: `0`
- `stale_evidence_included_count`: `0`
- `conflict_evidence_included_count`: `0`
- `missing_likely_relevant_context_count`: `0`
- `insufficient_fallback_missing_count`: `0`

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
