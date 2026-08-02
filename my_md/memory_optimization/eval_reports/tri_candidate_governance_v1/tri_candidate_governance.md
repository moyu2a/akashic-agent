# Tri Candidate Governance

本报告是三路召回候选去噪和 forbidden / 冲突过滤的离线 trace 评测，不调用 LLM。

## 复盘摘要

这轮测试的目的，是验证三路召回失败后新增的“候选治理层”能否在召回后、注入前清理坏候选，同时不误删目标证据。

| 项目 | 数据 | 结论 |
| --- | ---: | --- |
| 测试集规模 | `320` case | 使用 comprehensive 目标导向离线集，覆盖 common / hard 场景 |
| 目标证据数量 | `640` | 每个 case 主要有 2 条应召回目标证据 |
| 原始路由目标命中 | `640/640` | 原始路由在这个离线集上没有目标召回损失 |
| 受保护严格治理目标命中 | `640/640` | 候选治理在目标保护下没有误删目标证据 |
| 受保护目标损失 | `0` | 目标保护策略达成候选层安全边界 |
| should-not 候选 | `368` | 原始路由中仍会出现 fixture 标注的不应召回候选 |
| 严格治理丢弃 should-not | `368/368` | forbidden / 旧版本 / 跨 scope / 弱来源治理可以清掉已知坏候选 |
| 严格治理保留 should-not | `0` | 本轮 fixture 标注坏候选没有漏放 |
| 不受保护严格治理目标损失 | `640/640` | 直接全局硬删低置信、弱来源等候选会严重误伤 |

风险丢弃分布：

| 风险类型 | 丢弃次数 |
| --- | ---: |
| `weak_source_ref` | `3936` |
| `forbidden_candidate` | `1800` |
| `superseded_candidate` | `712` |
| `missing_source_ref` | `712` |
| `scope_mismatch` | `376` |

执行结论：

- 候选治理层本身有效：在受保护模式下，能保住 `640/640` 个目标证据，并清掉 `368/368` 个 should-not 候选。
- 候选治理不能直接无保护全局上线：不受保护严格模式会误删全部目标证据，主要因为很多正确记忆也带有 `weak_source_ref`。
- 下一步应该做小型真实 LLM 对照：比较 `chain_memory_base`、旧 `chain_tri_retrieval` 和候选治理后的三路召回，重点看 forbidden 是否下降、回答命中是否不下降、grounding 是否保持。

## Metrics

- `case_pack`: `comprehensive`
- `case_count`: `320`
- `baseline_expected_hit_count`: `640`
- `protected_expected_hit_count`: `640`
- `unprotected_expected_hit_count`: `0`
- `protected_expected_hit_loss_count`: `0`
- `unprotected_expected_hit_loss_count`: `640`
- `should_not_candidate_count`: `368`
- `strict_should_not_drop_count`: `368`
- `strict_should_not_kept_count`: `0`
- `dropped_risks_by_reason`: `{'forbidden_candidate': 1800, 'superseded_candidate': 712, 'weak_source_ref': 3936, 'missing_source_ref': 712, 'scope_mismatch': 376}`
- `unprotected_dropped_risks_by_reason`: `{'weak_source_ref': 5360, 'forbidden_candidate': 1800, 'superseded_candidate': 712, 'missing_source_ref': 712, 'scope_mismatch': 376}`
- `would_drop_protected_by_reason`: `{'weak_source_ref': 1424}`
- `failure_bucket_counts`: `{'passed': 17, 'forbidden_answer_failure': 5, 'grounded_answer_rule_miss': 18, 'not_in_40_case_report': 280}`

## Case Rows

| case_id | category | bucket | scene | expected | baseline_hits | protected_hits | unprotected_hits | protected_loss | unprotected_loss | baseline_candidates | protected_candidates |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `common_preference_recall_01` | `common_preference_recall` | `passed` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_tool_preference_01` | `common_tool_preference` | `passed` | `tool_preference` | 2 | 2 | 2 | 0 | 0 | 2 | 8 | 2 |
| `common_style_preference_01` | `common_style_preference` | `forbidden_answer_failure` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_tri_rrf_01` | `common_tri_rrf` | `forbidden_answer_failure` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_graph_bridge_01` | `common_graph_bridge` | `passed` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_version_chain_01` | `common_version_chain` | `passed` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_cross_scope_01` | `common_cross_scope` | `grounded_answer_rule_miss` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_duplicate_cleanup_01` | `common_duplicate_cleanup` | `passed` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_conflict_resolution_01` | `common_conflict_resolution` | `grounded_answer_rule_miss` | `partial_conflict` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_stale_sleep_01` | `common_stale_sleep` | `grounded_answer_rule_miss` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_entity_alias_01` | `common_entity_alias` | `passed` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_temporal_preference_01` | `common_temporal_preference` | `passed` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_low_value_filter_01` | `common_low_value_filter` | `grounded_answer_rule_miss` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_costly_call_preference_01` | `common_costly_call_preference` | `passed` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_injection_noise_01` | `common_injection_noise` | `grounded_answer_rule_miss` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_source_ref_missing_01` | `common_source_ref_missing` | `passed` | `source_lookup` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_session_boundary_01` | `common_session_boundary` | `grounded_answer_rule_miss` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_sleep_compaction_01` | `common_sleep_compaction` | `forbidden_answer_failure` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_causal_consistency_01` | `common_causal_consistency` | `forbidden_answer_failure` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_entropy_value_01` | `common_entropy_value` | `passed` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_preference_recall_02` | `common_preference_recall` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_tool_preference_02` | `common_tool_preference` | `not_in_40_case_report` | `tool_preference` | 2 | 2 | 2 | 0 | 0 | 2 | 8 | 2 |
| `common_style_preference_02` | `common_style_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_tri_rrf_02` | `common_tri_rrf` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_graph_bridge_02` | `common_graph_bridge` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_version_chain_02` | `common_version_chain` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_cross_scope_02` | `common_cross_scope` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_duplicate_cleanup_02` | `common_duplicate_cleanup` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_conflict_resolution_02` | `common_conflict_resolution` | `not_in_40_case_report` | `partial_conflict` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_stale_sleep_02` | `common_stale_sleep` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_entity_alias_02` | `common_entity_alias` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_temporal_preference_02` | `common_temporal_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_low_value_filter_02` | `common_low_value_filter` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_costly_call_preference_02` | `common_costly_call_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_injection_noise_02` | `common_injection_noise` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_source_ref_missing_02` | `common_source_ref_missing` | `not_in_40_case_report` | `source_lookup` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_session_boundary_02` | `common_session_boundary` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_sleep_compaction_02` | `common_sleep_compaction` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_causal_consistency_02` | `common_causal_consistency` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_entropy_value_02` | `common_entropy_value` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_preference_recall_03` | `common_preference_recall` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_tool_preference_03` | `common_tool_preference` | `not_in_40_case_report` | `tool_preference` | 2 | 2 | 2 | 0 | 0 | 2 | 8 | 2 |
| `common_style_preference_03` | `common_style_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_tri_rrf_03` | `common_tri_rrf` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_graph_bridge_03` | `common_graph_bridge` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_version_chain_03` | `common_version_chain` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_cross_scope_03` | `common_cross_scope` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_duplicate_cleanup_03` | `common_duplicate_cleanup` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_conflict_resolution_03` | `common_conflict_resolution` | `not_in_40_case_report` | `partial_conflict` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_stale_sleep_03` | `common_stale_sleep` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_entity_alias_03` | `common_entity_alias` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_temporal_preference_03` | `common_temporal_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_low_value_filter_03` | `common_low_value_filter` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_costly_call_preference_03` | `common_costly_call_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_injection_noise_03` | `common_injection_noise` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_source_ref_missing_03` | `common_source_ref_missing` | `not_in_40_case_report` | `source_lookup` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_session_boundary_03` | `common_session_boundary` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_sleep_compaction_03` | `common_sleep_compaction` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_causal_consistency_03` | `common_causal_consistency` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_entropy_value_03` | `common_entropy_value` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_preference_recall_04` | `common_preference_recall` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_tool_preference_04` | `common_tool_preference` | `not_in_40_case_report` | `tool_preference` | 2 | 2 | 2 | 0 | 0 | 2 | 8 | 2 |
| `common_style_preference_04` | `common_style_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_tri_rrf_04` | `common_tri_rrf` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_graph_bridge_04` | `common_graph_bridge` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_version_chain_04` | `common_version_chain` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_cross_scope_04` | `common_cross_scope` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_duplicate_cleanup_04` | `common_duplicate_cleanup` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_conflict_resolution_04` | `common_conflict_resolution` | `not_in_40_case_report` | `partial_conflict` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_stale_sleep_04` | `common_stale_sleep` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_entity_alias_04` | `common_entity_alias` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_temporal_preference_04` | `common_temporal_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_low_value_filter_04` | `common_low_value_filter` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_costly_call_preference_04` | `common_costly_call_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_injection_noise_04` | `common_injection_noise` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_source_ref_missing_04` | `common_source_ref_missing` | `not_in_40_case_report` | `source_lookup` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_session_boundary_04` | `common_session_boundary` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_sleep_compaction_04` | `common_sleep_compaction` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_causal_consistency_04` | `common_causal_consistency` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_entropy_value_04` | `common_entropy_value` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_preference_recall_05` | `common_preference_recall` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_tool_preference_05` | `common_tool_preference` | `not_in_40_case_report` | `tool_preference` | 2 | 2 | 2 | 0 | 0 | 2 | 8 | 2 |
| `common_style_preference_05` | `common_style_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_tri_rrf_05` | `common_tri_rrf` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_graph_bridge_05` | `common_graph_bridge` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_version_chain_05` | `common_version_chain` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_cross_scope_05` | `common_cross_scope` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_duplicate_cleanup_05` | `common_duplicate_cleanup` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_conflict_resolution_05` | `common_conflict_resolution` | `not_in_40_case_report` | `partial_conflict` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_stale_sleep_05` | `common_stale_sleep` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_entity_alias_05` | `common_entity_alias` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_temporal_preference_05` | `common_temporal_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_low_value_filter_05` | `common_low_value_filter` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_costly_call_preference_05` | `common_costly_call_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_injection_noise_05` | `common_injection_noise` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_source_ref_missing_05` | `common_source_ref_missing` | `not_in_40_case_report` | `source_lookup` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_session_boundary_05` | `common_session_boundary` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_sleep_compaction_05` | `common_sleep_compaction` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_causal_consistency_05` | `common_causal_consistency` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_entropy_value_05` | `common_entropy_value` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_preference_recall_06` | `common_preference_recall` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_tool_preference_06` | `common_tool_preference` | `not_in_40_case_report` | `tool_preference` | 2 | 2 | 2 | 0 | 0 | 2 | 8 | 2 |
| `common_style_preference_06` | `common_style_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_tri_rrf_06` | `common_tri_rrf` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_graph_bridge_06` | `common_graph_bridge` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_version_chain_06` | `common_version_chain` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_cross_scope_06` | `common_cross_scope` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_duplicate_cleanup_06` | `common_duplicate_cleanup` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_conflict_resolution_06` | `common_conflict_resolution` | `not_in_40_case_report` | `partial_conflict` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_stale_sleep_06` | `common_stale_sleep` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_entity_alias_06` | `common_entity_alias` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_temporal_preference_06` | `common_temporal_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_low_value_filter_06` | `common_low_value_filter` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_costly_call_preference_06` | `common_costly_call_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_injection_noise_06` | `common_injection_noise` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_source_ref_missing_06` | `common_source_ref_missing` | `not_in_40_case_report` | `source_lookup` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_session_boundary_06` | `common_session_boundary` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_sleep_compaction_06` | `common_sleep_compaction` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_causal_consistency_06` | `common_causal_consistency` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_entropy_value_06` | `common_entropy_value` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_preference_recall_07` | `common_preference_recall` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_tool_preference_07` | `common_tool_preference` | `not_in_40_case_report` | `tool_preference` | 2 | 2 | 2 | 0 | 0 | 2 | 8 | 2 |
| `common_style_preference_07` | `common_style_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_tri_rrf_07` | `common_tri_rrf` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_graph_bridge_07` | `common_graph_bridge` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_version_chain_07` | `common_version_chain` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_cross_scope_07` | `common_cross_scope` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_duplicate_cleanup_07` | `common_duplicate_cleanup` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_conflict_resolution_07` | `common_conflict_resolution` | `not_in_40_case_report` | `partial_conflict` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_stale_sleep_07` | `common_stale_sleep` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_entity_alias_07` | `common_entity_alias` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_temporal_preference_07` | `common_temporal_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_low_value_filter_07` | `common_low_value_filter` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_costly_call_preference_07` | `common_costly_call_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_injection_noise_07` | `common_injection_noise` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_source_ref_missing_07` | `common_source_ref_missing` | `not_in_40_case_report` | `source_lookup` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_session_boundary_07` | `common_session_boundary` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_sleep_compaction_07` | `common_sleep_compaction` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_causal_consistency_07` | `common_causal_consistency` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_entropy_value_07` | `common_entropy_value` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_preference_recall_08` | `common_preference_recall` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_tool_preference_08` | `common_tool_preference` | `not_in_40_case_report` | `tool_preference` | 2 | 2 | 2 | 0 | 0 | 2 | 8 | 2 |
| `common_style_preference_08` | `common_style_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_tri_rrf_08` | `common_tri_rrf` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_graph_bridge_08` | `common_graph_bridge` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_version_chain_08` | `common_version_chain` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_cross_scope_08` | `common_cross_scope` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_duplicate_cleanup_08` | `common_duplicate_cleanup` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_conflict_resolution_08` | `common_conflict_resolution` | `not_in_40_case_report` | `partial_conflict` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_stale_sleep_08` | `common_stale_sleep` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_entity_alias_08` | `common_entity_alias` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_temporal_preference_08` | `common_temporal_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_low_value_filter_08` | `common_low_value_filter` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_costly_call_preference_08` | `common_costly_call_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_injection_noise_08` | `common_injection_noise` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_source_ref_missing_08` | `common_source_ref_missing` | `not_in_40_case_report` | `source_lookup` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_session_boundary_08` | `common_session_boundary` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_sleep_compaction_08` | `common_sleep_compaction` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_causal_consistency_08` | `common_causal_consistency` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `common_entropy_value_08` | `common_entropy_value` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_preference_recall_01` | `hard_preference_recall` | `passed` | `fuzzy_reference` | 2 | 2 | 2 | 0 | 0 | 2 | 9 | 2 |
| `hard_tool_preference_01` | `hard_tool_preference` | `passed` | `tool_preference` | 2 | 2 | 2 | 0 | 0 | 2 | 8 | 2 |
| `hard_style_preference_01` | `hard_style_preference` | `passed` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_tri_rrf_01` | `hard_tri_rrf` | `passed` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_graph_bridge_01` | `hard_graph_bridge` | `grounded_answer_rule_miss` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_version_chain_01` | `hard_version_chain` | `grounded_answer_rule_miss` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_cross_scope_01` | `hard_cross_scope` | `passed` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_duplicate_cleanup_01` | `hard_duplicate_cleanup` | `passed` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_conflict_resolution_01` | `hard_conflict_resolution` | `grounded_answer_rule_miss` | `partial_conflict` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_stale_sleep_01` | `hard_stale_sleep` | `grounded_answer_rule_miss` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_entity_alias_01` | `hard_entity_alias` | `grounded_answer_rule_miss` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_temporal_preference_01` | `hard_temporal_preference` | `passed` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_low_value_filter_01` | `hard_low_value_filter` | `grounded_answer_rule_miss` | `fuzzy_reference` | 2 | 2 | 2 | 0 | 0 | 2 | 9 | 2 |
| `hard_costly_call_preference_01` | `hard_costly_call_preference` | `grounded_answer_rule_miss` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_injection_noise_01` | `hard_injection_noise` | `grounded_answer_rule_miss` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_source_ref_missing_01` | `hard_source_ref_missing` | `grounded_answer_rule_miss` | `source_lookup` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_session_boundary_01` | `hard_session_boundary` | `grounded_answer_rule_miss` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_sleep_compaction_01` | `hard_sleep_compaction` | `forbidden_answer_failure` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_causal_consistency_01` | `hard_causal_consistency` | `grounded_answer_rule_miss` | `partial_conflict` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_entropy_value_01` | `hard_entropy_value` | `grounded_answer_rule_miss` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_preference_recall_02` | `hard_preference_recall` | `not_in_40_case_report` | `fuzzy_reference` | 2 | 2 | 2 | 0 | 0 | 2 | 9 | 2 |
| `hard_tool_preference_02` | `hard_tool_preference` | `not_in_40_case_report` | `tool_preference` | 2 | 2 | 2 | 0 | 0 | 2 | 8 | 2 |
| `hard_style_preference_02` | `hard_style_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_tri_rrf_02` | `hard_tri_rrf` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_graph_bridge_02` | `hard_graph_bridge` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_version_chain_02` | `hard_version_chain` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_cross_scope_02` | `hard_cross_scope` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_duplicate_cleanup_02` | `hard_duplicate_cleanup` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_conflict_resolution_02` | `hard_conflict_resolution` | `not_in_40_case_report` | `partial_conflict` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_stale_sleep_02` | `hard_stale_sleep` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_entity_alias_02` | `hard_entity_alias` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_temporal_preference_02` | `hard_temporal_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_low_value_filter_02` | `hard_low_value_filter` | `not_in_40_case_report` | `fuzzy_reference` | 2 | 2 | 2 | 0 | 0 | 2 | 9 | 2 |
| `hard_costly_call_preference_02` | `hard_costly_call_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_injection_noise_02` | `hard_injection_noise` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_source_ref_missing_02` | `hard_source_ref_missing` | `not_in_40_case_report` | `source_lookup` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_session_boundary_02` | `hard_session_boundary` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_sleep_compaction_02` | `hard_sleep_compaction` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_causal_consistency_02` | `hard_causal_consistency` | `not_in_40_case_report` | `partial_conflict` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_entropy_value_02` | `hard_entropy_value` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_preference_recall_03` | `hard_preference_recall` | `not_in_40_case_report` | `fuzzy_reference` | 2 | 2 | 2 | 0 | 0 | 2 | 9 | 2 |
| `hard_tool_preference_03` | `hard_tool_preference` | `not_in_40_case_report` | `tool_preference` | 2 | 2 | 2 | 0 | 0 | 2 | 8 | 2 |
| `hard_style_preference_03` | `hard_style_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_tri_rrf_03` | `hard_tri_rrf` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_graph_bridge_03` | `hard_graph_bridge` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_version_chain_03` | `hard_version_chain` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_cross_scope_03` | `hard_cross_scope` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_duplicate_cleanup_03` | `hard_duplicate_cleanup` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_conflict_resolution_03` | `hard_conflict_resolution` | `not_in_40_case_report` | `partial_conflict` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_stale_sleep_03` | `hard_stale_sleep` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_entity_alias_03` | `hard_entity_alias` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_temporal_preference_03` | `hard_temporal_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_low_value_filter_03` | `hard_low_value_filter` | `not_in_40_case_report` | `fuzzy_reference` | 2 | 2 | 2 | 0 | 0 | 2 | 9 | 2 |
| `hard_costly_call_preference_03` | `hard_costly_call_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_injection_noise_03` | `hard_injection_noise` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_source_ref_missing_03` | `hard_source_ref_missing` | `not_in_40_case_report` | `source_lookup` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_session_boundary_03` | `hard_session_boundary` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_sleep_compaction_03` | `hard_sleep_compaction` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_causal_consistency_03` | `hard_causal_consistency` | `not_in_40_case_report` | `partial_conflict` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_entropy_value_03` | `hard_entropy_value` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_preference_recall_04` | `hard_preference_recall` | `not_in_40_case_report` | `fuzzy_reference` | 2 | 2 | 2 | 0 | 0 | 2 | 9 | 2 |
| `hard_tool_preference_04` | `hard_tool_preference` | `not_in_40_case_report` | `tool_preference` | 2 | 2 | 2 | 0 | 0 | 2 | 8 | 2 |
| `hard_style_preference_04` | `hard_style_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_tri_rrf_04` | `hard_tri_rrf` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_graph_bridge_04` | `hard_graph_bridge` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_version_chain_04` | `hard_version_chain` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_cross_scope_04` | `hard_cross_scope` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_duplicate_cleanup_04` | `hard_duplicate_cleanup` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_conflict_resolution_04` | `hard_conflict_resolution` | `not_in_40_case_report` | `partial_conflict` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_stale_sleep_04` | `hard_stale_sleep` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_entity_alias_04` | `hard_entity_alias` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_temporal_preference_04` | `hard_temporal_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_low_value_filter_04` | `hard_low_value_filter` | `not_in_40_case_report` | `fuzzy_reference` | 2 | 2 | 2 | 0 | 0 | 2 | 9 | 2 |
| `hard_costly_call_preference_04` | `hard_costly_call_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_injection_noise_04` | `hard_injection_noise` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_source_ref_missing_04` | `hard_source_ref_missing` | `not_in_40_case_report` | `source_lookup` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_session_boundary_04` | `hard_session_boundary` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_sleep_compaction_04` | `hard_sleep_compaction` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_causal_consistency_04` | `hard_causal_consistency` | `not_in_40_case_report` | `partial_conflict` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_entropy_value_04` | `hard_entropy_value` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_preference_recall_05` | `hard_preference_recall` | `not_in_40_case_report` | `fuzzy_reference` | 2 | 2 | 2 | 0 | 0 | 2 | 9 | 2 |
| `hard_tool_preference_05` | `hard_tool_preference` | `not_in_40_case_report` | `tool_preference` | 2 | 2 | 2 | 0 | 0 | 2 | 8 | 2 |
| `hard_style_preference_05` | `hard_style_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_tri_rrf_05` | `hard_tri_rrf` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_graph_bridge_05` | `hard_graph_bridge` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_version_chain_05` | `hard_version_chain` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_cross_scope_05` | `hard_cross_scope` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_duplicate_cleanup_05` | `hard_duplicate_cleanup` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_conflict_resolution_05` | `hard_conflict_resolution` | `not_in_40_case_report` | `partial_conflict` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_stale_sleep_05` | `hard_stale_sleep` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_entity_alias_05` | `hard_entity_alias` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_temporal_preference_05` | `hard_temporal_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_low_value_filter_05` | `hard_low_value_filter` | `not_in_40_case_report` | `fuzzy_reference` | 2 | 2 | 2 | 0 | 0 | 2 | 9 | 2 |
| `hard_costly_call_preference_05` | `hard_costly_call_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_injection_noise_05` | `hard_injection_noise` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_source_ref_missing_05` | `hard_source_ref_missing` | `not_in_40_case_report` | `source_lookup` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_session_boundary_05` | `hard_session_boundary` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_sleep_compaction_05` | `hard_sleep_compaction` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_causal_consistency_05` | `hard_causal_consistency` | `not_in_40_case_report` | `partial_conflict` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_entropy_value_05` | `hard_entropy_value` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_preference_recall_06` | `hard_preference_recall` | `not_in_40_case_report` | `fuzzy_reference` | 2 | 2 | 2 | 0 | 0 | 2 | 9 | 2 |
| `hard_tool_preference_06` | `hard_tool_preference` | `not_in_40_case_report` | `tool_preference` | 2 | 2 | 2 | 0 | 0 | 2 | 8 | 2 |
| `hard_style_preference_06` | `hard_style_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_tri_rrf_06` | `hard_tri_rrf` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_graph_bridge_06` | `hard_graph_bridge` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_version_chain_06` | `hard_version_chain` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_cross_scope_06` | `hard_cross_scope` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_duplicate_cleanup_06` | `hard_duplicate_cleanup` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_conflict_resolution_06` | `hard_conflict_resolution` | `not_in_40_case_report` | `partial_conflict` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_stale_sleep_06` | `hard_stale_sleep` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_entity_alias_06` | `hard_entity_alias` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_temporal_preference_06` | `hard_temporal_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_low_value_filter_06` | `hard_low_value_filter` | `not_in_40_case_report` | `fuzzy_reference` | 2 | 2 | 2 | 0 | 0 | 2 | 9 | 2 |
| `hard_costly_call_preference_06` | `hard_costly_call_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_injection_noise_06` | `hard_injection_noise` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_source_ref_missing_06` | `hard_source_ref_missing` | `not_in_40_case_report` | `source_lookup` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_session_boundary_06` | `hard_session_boundary` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_sleep_compaction_06` | `hard_sleep_compaction` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_causal_consistency_06` | `hard_causal_consistency` | `not_in_40_case_report` | `partial_conflict` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_entropy_value_06` | `hard_entropy_value` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_preference_recall_07` | `hard_preference_recall` | `not_in_40_case_report` | `fuzzy_reference` | 2 | 2 | 2 | 0 | 0 | 2 | 9 | 2 |
| `hard_tool_preference_07` | `hard_tool_preference` | `not_in_40_case_report` | `tool_preference` | 2 | 2 | 2 | 0 | 0 | 2 | 8 | 2 |
| `hard_style_preference_07` | `hard_style_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_tri_rrf_07` | `hard_tri_rrf` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_graph_bridge_07` | `hard_graph_bridge` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_version_chain_07` | `hard_version_chain` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_cross_scope_07` | `hard_cross_scope` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_duplicate_cleanup_07` | `hard_duplicate_cleanup` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_conflict_resolution_07` | `hard_conflict_resolution` | `not_in_40_case_report` | `partial_conflict` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_stale_sleep_07` | `hard_stale_sleep` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_entity_alias_07` | `hard_entity_alias` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_temporal_preference_07` | `hard_temporal_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_low_value_filter_07` | `hard_low_value_filter` | `not_in_40_case_report` | `fuzzy_reference` | 2 | 2 | 2 | 0 | 0 | 2 | 9 | 2 |
| `hard_costly_call_preference_07` | `hard_costly_call_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_injection_noise_07` | `hard_injection_noise` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_source_ref_missing_07` | `hard_source_ref_missing` | `not_in_40_case_report` | `source_lookup` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_session_boundary_07` | `hard_session_boundary` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_sleep_compaction_07` | `hard_sleep_compaction` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_causal_consistency_07` | `hard_causal_consistency` | `not_in_40_case_report` | `partial_conflict` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_entropy_value_07` | `hard_entropy_value` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_preference_recall_08` | `hard_preference_recall` | `not_in_40_case_report` | `fuzzy_reference` | 2 | 2 | 2 | 0 | 0 | 2 | 9 | 2 |
| `hard_tool_preference_08` | `hard_tool_preference` | `not_in_40_case_report` | `tool_preference` | 2 | 2 | 2 | 0 | 0 | 2 | 8 | 2 |
| `hard_style_preference_08` | `hard_style_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_tri_rrf_08` | `hard_tri_rrf` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_graph_bridge_08` | `hard_graph_bridge` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_version_chain_08` | `hard_version_chain` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_cross_scope_08` | `hard_cross_scope` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_duplicate_cleanup_08` | `hard_duplicate_cleanup` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_conflict_resolution_08` | `hard_conflict_resolution` | `not_in_40_case_report` | `partial_conflict` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_stale_sleep_08` | `hard_stale_sleep` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_entity_alias_08` | `hard_entity_alias` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_temporal_preference_08` | `hard_temporal_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_low_value_filter_08` | `hard_low_value_filter` | `not_in_40_case_report` | `fuzzy_reference` | 2 | 2 | 2 | 0 | 0 | 2 | 9 | 2 |
| `hard_costly_call_preference_08` | `hard_costly_call_preference` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_injection_noise_08` | `hard_injection_noise` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_source_ref_missing_08` | `hard_source_ref_missing` | `not_in_40_case_report` | `source_lookup` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_session_boundary_08` | `hard_session_boundary` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_sleep_compaction_08` | `hard_sleep_compaction` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_causal_consistency_08` | `hard_causal_consistency` | `not_in_40_case_report` | `partial_conflict` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
| `hard_entropy_value_08` | `hard_entropy_value` | `not_in_40_case_report` | `unknown` | 2 | 2 | 2 | 0 | 0 | 2 | 7 | 2 |
