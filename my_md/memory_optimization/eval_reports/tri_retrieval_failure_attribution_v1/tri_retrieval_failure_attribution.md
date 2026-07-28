# Tri Retrieval Failure Attribution

本报告专门解释 `chain_tri_retrieval` 在短线上真实 LLM 评测中的失败原因。

## 边界

- 本报告不包含原始 prompt、session 原文、memory summary 或完整回答。
- 本报告不重新调用 LLM，也不改变生产召回和 prompt。
- 如果 `memory_grounding_passed = True` 但 `answer_rule_passed = False`，这里归因为证据使用、噪声、排序、注入或评分规则问题，不归因为召回缺失。
- `fixture_*` evidence count 是 offline fixture proxy, not observed context ids；它不能直接证明真实 prompt 中的噪声规模。
- `chain_rerank_injection` 是后续累计 profile；三路失败而该 profile 通过，只说明后续组合链路可能救活，不证明 rerank 单因素因果。
- 本轮 `40` 个 case 的 category 粒度较细，不把单个 category 失败解释为统计集中。

## 总览

- `source_case_count`: `160`
- `source_unique_case_count`: `40`
- `tri_case_count`: `40`
- `tri_answer_fail_count`: `23`
- `tri_answer_fail_rate`: `57.5`
- `tri_grounded_answer_fail_count_any`: `23`
- `tri_grounded_non_forbidden_answer_fail_count`: `18`
- `tri_grounding_fail_count`: `0`
- `tri_forbidden_fail_count`: `5`
- `baseline_passed_but_tri_failed_count`: `5`
- `baseline_failed_but_tri_passed_count`: `9`
- `tri_failed_but_rerank_passed_count`: `7`
- `avg_fixture_tri_evidence_id_count`: `4.95`
- `avg_fixture_evidence_count_delta_vs_base`: `0.375`
- `fixture_rerank_reduced_evidence_count_cases`: `34`

## Case Set 汇总

| case_set | cases | answer_fail | grounded_any | grounded_non_forbidden | forbidden_fail | base_pass_tri_fail | tri_fail_rerank_pass | answer_fail_rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `common` | 20 | 10 | 10 | 6 | 4 | 2 | 4 | 50.0 |
| `hard` | 20 | 13 | 13 | 12 | 1 | 3 | 3 | 65.0 |

## Scenario Family 汇总

| scenario | cases | answer_fail | grounded_any | forbidden_fail | base_pass_tri_fail | tri_fail_rerank_pass |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `causal_consistency` | 2 | 2 | 2 | 1 | 0 | 0 |
| `conflict_resolution` | 2 | 2 | 2 | 0 | 2 | 0 |
| `costly_call_preference` | 2 | 1 | 1 | 0 | 0 | 0 |
| `cross_scope` | 2 | 1 | 1 | 0 | 0 | 1 |
| `duplicate_cleanup` | 2 | 0 | 0 | 0 | 0 | 0 |
| `entity_alias` | 2 | 1 | 1 | 0 | 1 | 1 |
| `entropy_value` | 2 | 1 | 1 | 0 | 1 | 0 |
| `graph_bridge` | 2 | 1 | 1 | 0 | 0 | 0 |
| `injection_noise` | 2 | 2 | 2 | 0 | 0 | 0 |
| `low_value_filter` | 2 | 2 | 2 | 0 | 0 | 0 |
| `preference_recall` | 2 | 0 | 0 | 0 | 0 | 0 |
| `session_boundary` | 2 | 2 | 2 | 0 | 0 | 1 |
| `sleep_compaction` | 2 | 2 | 2 | 2 | 0 | 1 |
| `source_ref_missing` | 2 | 1 | 1 | 0 | 0 | 1 |
| `stale_sleep` | 2 | 2 | 2 | 0 | 0 | 0 |
| `style_preference` | 2 | 1 | 1 | 1 | 1 | 0 |
| `temporal_preference` | 2 | 0 | 0 | 0 | 0 | 0 |
| `tool_preference` | 2 | 0 | 0 | 0 | 0 | 0 |
| `tri_rrf` | 2 | 1 | 1 | 1 | 0 | 1 |
| `version_chain` | 2 | 1 | 1 | 0 | 0 | 1 |

## Failure Bucket Counts

- `forbidden_answer_failure`: `5`
- `grounded_answer_rule_miss`: `18`
- `passed`: `17`

## Pass Pattern Counts

- `base_fail_tri_fail_rerank_fail`: `12`
- `base_fail_tri_fail_rerank_pass`: `6`
- `base_fail_tri_pass_rerank_fail`: `5`
- `base_fail_tri_pass_rerank_pass`: `4`
- `base_pass_tri_fail_rerank_fail`: `4`
- `base_pass_tri_fail_rerank_pass`: `1`
- `base_pass_tri_pass_rerank_fail`: `1`
- `base_pass_tri_pass_rerank_pass`: `7`

## Failure Bucket To Code Cross Table

- `forbidden_answer_failure`: `found_forbidden_answer_term`=5, `missing_expected_answer_term`=2, `missing_expected_answer_term_group`=4
- `grounded_answer_rule_miss`: `missing_expected_answer_term`=16, `missing_expected_answer_term_group`=19
- `passed`: `none`

## Case 明细

| case_id | case_set | scenario | bucket | pattern | base_pass | tri_pass | rerank_pass | fixture_tri_evidence | fixture_delta_vs_base | used_memory_ids | failures |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `common_preference_recall_01` | `common` | `preference_recall` | `passed` | `base_fail_tri_pass_rerank_pass` | False | True | True | 6 | 0 | 6 | `` |
| `common_tool_preference_01` | `common` | `tool_preference` | `passed` | `base_fail_tri_pass_rerank_pass` | False | True | True | 5 | 0 | 5 | `` |
| `common_style_preference_01` | `common` | `style_preference` | `forbidden_answer_failure` | `base_pass_tri_fail_rerank_fail` | True | False | False | 5 | 0 | 5 | `found_forbidden_answer_term` |
| `common_tri_rrf_01` | `common` | `tri_rrf` | `forbidden_answer_failure` | `base_fail_tri_fail_rerank_pass` | False | False | True | 6 | 1 | 6 | `missing_expected_answer_term,missing_expected_answer_term_group,missing_expected_answer_term_group,found_forbidden_answer_term` |
| `common_graph_bridge_01` | `common` | `graph_bridge` | `passed` | `base_fail_tri_pass_rerank_fail` | False | True | False | 6 | 0 | 6 | `` |
| `common_version_chain_01` | `common` | `version_chain` | `passed` | `base_pass_tri_pass_rerank_pass` | True | True | True | 6 | 1 | 6 | `` |
| `common_cross_scope_01` | `common` | `cross_scope` | `grounded_answer_rule_miss` | `base_fail_tri_fail_rerank_pass` | False | False | True | 7 | 1 | 7 | `missing_expected_answer_term_group` |
| `common_duplicate_cleanup_01` | `common` | `duplicate_cleanup` | `passed` | `base_pass_tri_pass_rerank_pass` | True | True | True | 7 | 1 | 7 | `` |
| `common_conflict_resolution_01` | `common` | `conflict_resolution` | `grounded_answer_rule_miss` | `base_pass_tri_fail_rerank_fail` | True | False | False | 4 | 0 | 4 | `missing_expected_answer_term,missing_expected_answer_term_group,missing_expected_answer_term_group` |
| `common_stale_sleep_01` | `common` | `stale_sleep` | `grounded_answer_rule_miss` | `base_fail_tri_fail_rerank_fail` | False | False | False | 4 | 0 | 4 | `missing_expected_answer_term,missing_expected_answer_term,missing_expected_answer_term_group,missing_expected_answer_term_group` |
| `common_entity_alias_01` | `common` | `entity_alias` | `passed` | `base_pass_tri_pass_rerank_pass` | True | True | True | 5 | 0 | 5 | `` |
| `common_temporal_preference_01` | `common` | `temporal_preference` | `passed` | `base_pass_tri_pass_rerank_pass` | True | True | True | 3 | 0 | 3 | `` |
| `common_low_value_filter_01` | `common` | `low_value_filter` | `grounded_answer_rule_miss` | `base_fail_tri_fail_rerank_fail` | False | False | False | 5 | 0 | 5 | `missing_expected_answer_term,missing_expected_answer_term,missing_expected_answer_term_group,missing_expected_answer_term_group` |
| `common_costly_call_preference_01` | `common` | `costly_call_preference` | `passed` | `base_fail_tri_pass_rerank_pass` | False | True | True | 5 | 0 | 5 | `` |
| `common_injection_noise_01` | `common` | `injection_noise` | `grounded_answer_rule_miss` | `base_fail_tri_fail_rerank_fail` | False | False | False | 5 | 0 | 5 | `missing_expected_answer_term_group` |
| `common_source_ref_missing_01` | `common` | `source_ref_missing` | `passed` | `base_fail_tri_pass_rerank_fail` | False | True | False | 5 | 0 | 5 | `` |
| `common_session_boundary_01` | `common` | `session_boundary` | `grounded_answer_rule_miss` | `base_fail_tri_fail_rerank_pass` | False | False | True | 4 | 0 | 4 | `missing_expected_answer_term` |
| `common_sleep_compaction_01` | `common` | `sleep_compaction` | `forbidden_answer_failure` | `base_fail_tri_fail_rerank_pass` | False | False | True | 6 | 1 | 6 | `missing_expected_answer_term_group,found_forbidden_answer_term` |
| `common_causal_consistency_01` | `common` | `causal_consistency` | `forbidden_answer_failure` | `base_fail_tri_fail_rerank_fail` | False | False | False | 6 | 0 | 6 | `found_forbidden_answer_term` |
| `common_entropy_value_01` | `common` | `entropy_value` | `passed` | `base_pass_tri_pass_rerank_pass` | True | True | True | 5 | 0 | 5 | `` |
| `hard_preference_recall_01` | `hard` | `preference_recall` | `passed` | `base_fail_tri_pass_rerank_fail` | False | True | False | 6 | 0 | 6 | `` |
| `hard_tool_preference_01` | `hard` | `tool_preference` | `passed` | `base_pass_tri_pass_rerank_pass` | True | True | True | 5 | 0 | 5 | `` |
| `hard_style_preference_01` | `hard` | `style_preference` | `passed` | `base_fail_tri_pass_rerank_pass` | False | True | True | 2 | 0 | 2 | `` |
| `hard_tri_rrf_01` | `hard` | `tri_rrf` | `passed` | `base_fail_tri_pass_rerank_fail` | False | True | False | 6 | 1 | 6 | `` |
| `hard_graph_bridge_01` | `hard` | `graph_bridge` | `grounded_answer_rule_miss` | `base_fail_tri_fail_rerank_fail` | False | False | False | 6 | 0 | 6 | `missing_expected_answer_term` |
| `hard_version_chain_01` | `hard` | `version_chain` | `grounded_answer_rule_miss` | `base_fail_tri_fail_rerank_pass` | False | False | True | 2 | 0 | 2 | `missing_expected_answer_term` |
| `hard_cross_scope_01` | `hard` | `cross_scope` | `passed` | `base_fail_tri_pass_rerank_fail` | False | True | False | 7 | 1 | 7 | `` |
| `hard_duplicate_cleanup_01` | `hard` | `duplicate_cleanup` | `passed` | `base_pass_tri_pass_rerank_fail` | True | True | False | 7 | 1 | 7 | `` |
| `hard_conflict_resolution_01` | `hard` | `conflict_resolution` | `grounded_answer_rule_miss` | `base_pass_tri_fail_rerank_fail` | True | False | False | 4 | 2 | 4 | `missing_expected_answer_term_group` |
| `hard_stale_sleep_01` | `hard` | `stale_sleep` | `grounded_answer_rule_miss` | `base_fail_tri_fail_rerank_fail` | False | False | False | 6 | 0 | 6 | `missing_expected_answer_term,missing_expected_answer_term_group` |
| `hard_entity_alias_01` | `hard` | `entity_alias` | `grounded_answer_rule_miss` | `base_pass_tri_fail_rerank_pass` | True | False | True | 4 | 0 | 4 | `missing_expected_answer_term,missing_expected_answer_term,missing_expected_answer_term_group,missing_expected_answer_term_group` |
| `hard_temporal_preference_01` | `hard` | `temporal_preference` | `passed` | `base_pass_tri_pass_rerank_pass` | True | True | True | 2 | 0 | 2 | `` |
| `hard_low_value_filter_01` | `hard` | `low_value_filter` | `grounded_answer_rule_miss` | `base_fail_tri_fail_rerank_fail` | False | False | False | 5 | 2 | 5 | `missing_expected_answer_term_group` |
| `hard_costly_call_preference_01` | `hard` | `costly_call_preference` | `grounded_answer_rule_miss` | `base_fail_tri_fail_rerank_fail` | False | False | False | 2 | 0 | 2 | `missing_expected_answer_term_group` |
| `hard_injection_noise_01` | `hard` | `injection_noise` | `grounded_answer_rule_miss` | `base_fail_tri_fail_rerank_fail` | False | False | False | 3 | 0 | 3 | `missing_expected_answer_term,missing_expected_answer_term_group` |
| `hard_source_ref_missing_01` | `hard` | `source_ref_missing` | `grounded_answer_rule_miss` | `base_fail_tri_fail_rerank_pass` | False | False | True | 5 | 0 | 5 | `missing_expected_answer_term` |
| `hard_session_boundary_01` | `hard` | `session_boundary` | `grounded_answer_rule_miss` | `base_fail_tri_fail_rerank_fail` | False | False | False | 4 | 1 | 4 | `missing_expected_answer_term_group` |
| `hard_sleep_compaction_01` | `hard` | `sleep_compaction` | `forbidden_answer_failure` | `base_fail_tri_fail_rerank_fail` | False | False | False | 6 | 1 | 6 | `missing_expected_answer_term,missing_expected_answer_term_group,found_forbidden_answer_term` |
| `hard_causal_consistency_01` | `hard` | `causal_consistency` | `grounded_answer_rule_miss` | `base_fail_tri_fail_rerank_fail` | False | False | False | 5 | 0 | 5 | `missing_expected_answer_term,missing_expected_answer_term_group` |
| `hard_entropy_value_01` | `hard` | `entropy_value` | `grounded_answer_rule_miss` | `base_pass_tri_fail_rerank_fail` | True | False | False | 6 | 1 | 6 | `missing_expected_answer_term,missing_expected_answer_term,missing_expected_answer_term_group,missing_expected_answer_term_group` |

## 下一步建议

- 优先查看 `grounded_answer_rule_miss`：证据已经进入上下文，但回答没有稳定用对。
- 如果 `tri_failed_but_rerank_passed_count` 较高，优先设计 `route + tri + graph/rerank/injection` 后续组合验证；不要把它解释为 rerank 单因素因果。
- 如果 `baseline_passed_but_tri_failed_count` 较高，优先做候选去噪和 forbidden 过滤。
- 如果 failure bucket 或 pass pattern 集中，下一轮围绕该模式做小型真实 LLM 复测。
- 如果只有单个 scenario 失败，先把它作为 case-level 诊断，不作为统计集中结论。
