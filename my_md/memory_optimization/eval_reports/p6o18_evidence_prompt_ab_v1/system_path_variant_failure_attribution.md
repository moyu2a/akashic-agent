# System Path Variant Failure Attribution

本报告只包含脱敏 case id、repeat id、pass/fail 和 heuristic failure bucket；不包含原始问题、提示词、记忆正文或完整回答。

- anchor_mode: `safe_version_replace_guided`
- comparison_modes: `safe_version_replace, safe_version_replace_structured_guided, safe_version_replace_near_query_block`
- paired_pair_count: `120`
- failure_bucket_semantics: `sanitized_heuristic`

## Mode Failure Buckets

| mode | bucket | count |
| --- | --- | ---: |
| safe_version_replace_guided | answer_rule_miss_any_group | 2 |
| safe_version_replace_guided | answer_rule_miss_required_terms | 5 |
| safe_version_replace_guided | language_failure | 2 |
| safe_version_replace_guided | passed | 31 |
| safe_version_replace | answer_rule_miss_any_group | 6 |
| safe_version_replace | answer_rule_miss_required_terms | 8 |
| safe_version_replace | language_failure | 2 |
| safe_version_replace | passed | 24 |
| safe_version_replace_structured_guided | answer_rule_miss_any_group | 3 |
| safe_version_replace_structured_guided | answer_rule_miss_required_terms | 4 |
| safe_version_replace_structured_guided | language_failure | 2 |
| safe_version_replace_structured_guided | passed | 31 |
| safe_version_replace_near_query_block | answer_rule_miss_any_group | 8 |
| safe_version_replace_near_query_block | answer_rule_miss_required_terms | 8 |
| safe_version_replace_near_query_block | language_failure | 1 |
| safe_version_replace_near_query_block | passed | 23 |

## Pairwise Movements

| comparison_mode | movement | count |
| --- | --- | ---: |
| safe_version_replace | anchor_failed_comparison_failed | 6 |
| safe_version_replace | anchor_failed_comparison_passed | 3 |
| safe_version_replace | anchor_passed_comparison_failed | 10 |
| safe_version_replace | anchor_passed_comparison_passed | 21 |
| safe_version_replace_structured_guided | anchor_failed_comparison_failed | 5 |
| safe_version_replace_structured_guided | anchor_failed_comparison_passed | 4 |
| safe_version_replace_structured_guided | anchor_passed_comparison_failed | 4 |
| safe_version_replace_structured_guided | anchor_passed_comparison_passed | 27 |
| safe_version_replace_near_query_block | anchor_failed_comparison_failed | 7 |
| safe_version_replace_near_query_block | anchor_failed_comparison_passed | 2 |
| safe_version_replace_near_query_block | anchor_passed_comparison_failed | 10 |
| safe_version_replace_near_query_block | anchor_passed_comparison_passed | 21 |

## Missed Cases

| mode | case_id | repeat | category | bucket |
| --- | --- | ---: | --- | --- |
| safe_version_replace | common_conflict_resolution_02 | 0 | common_conflict_resolution | answer_rule_miss_any_group |
| safe_version_replace_structured_guided | common_conflict_resolution_02 | 0 | common_conflict_resolution | answer_rule_miss_any_group |
| safe_version_replace | common_cross_scope_01 | 0 | common_cross_scope | answer_rule_miss_any_group |
| safe_version_replace_near_query_block | common_cross_scope_01 | 0 | common_cross_scope | answer_rule_miss_required_terms |
| safe_version_replace | common_cross_scope_02 | 0 | common_cross_scope | answer_rule_miss_required_terms |
| safe_version_replace | common_preference_recall_01 | 0 | common_preference_recall | answer_rule_miss_any_group |
| safe_version_replace_guided | common_preference_recall_01 | 0 | common_preference_recall | answer_rule_miss_required_terms |
| safe_version_replace_near_query_block | common_preference_recall_01 | 0 | common_preference_recall | answer_rule_miss_any_group |
| safe_version_replace | common_preference_recall_02 | 0 | common_preference_recall | answer_rule_miss_any_group |
| safe_version_replace_guided | common_preference_recall_02 | 0 | common_preference_recall | answer_rule_miss_required_terms |
| safe_version_replace_near_query_block | common_preference_recall_02 | 0 | common_preference_recall | answer_rule_miss_any_group |
| safe_version_replace_structured_guided | common_preference_recall_02 | 0 | common_preference_recall | answer_rule_miss_required_terms |
| safe_version_replace | common_stale_sleep_01 | 0 | common_stale_sleep | answer_rule_miss_any_group |
| safe_version_replace_near_query_block | common_stale_sleep_01 | 0 | common_stale_sleep | answer_rule_miss_required_terms |
| safe_version_replace | common_style_preference_02 | 0 | common_style_preference | answer_rule_miss_required_terms |
| safe_version_replace_near_query_block | common_style_preference_02 | 0 | common_style_preference | answer_rule_miss_required_terms |
| safe_version_replace | common_tool_preference_01 | 0 | common_tool_preference | language_failure |
| safe_version_replace_guided | common_tool_preference_01 | 0 | common_tool_preference | language_failure |
| safe_version_replace_structured_guided | common_tool_preference_01 | 0 | common_tool_preference | language_failure |
| safe_version_replace | common_tool_preference_02 | 0 | common_tool_preference | language_failure |
| safe_version_replace_guided | common_tool_preference_02 | 0 | common_tool_preference | language_failure |
| safe_version_replace_near_query_block | common_tool_preference_02 | 0 | common_tool_preference | language_failure |
| safe_version_replace_structured_guided | common_tool_preference_02 | 0 | common_tool_preference | language_failure |
| safe_version_replace_guided | common_version_chain_02 | 0 | common_version_chain | answer_rule_miss_any_group |
| safe_version_replace_near_query_block | common_version_chain_02 | 0 | common_version_chain | answer_rule_miss_any_group |
| safe_version_replace_near_query_block | hard_conflict_resolution_01 | 0 | hard_conflict_resolution | answer_rule_miss_any_group |
| safe_version_replace_structured_guided | hard_conflict_resolution_01 | 0 | hard_conflict_resolution | answer_rule_miss_any_group |
| safe_version_replace_near_query_block | hard_cross_scope_01 | 0 | hard_cross_scope | answer_rule_miss_any_group |
| safe_version_replace | hard_cross_scope_02 | 0 | hard_cross_scope | answer_rule_miss_any_group |
| safe_version_replace_near_query_block | hard_cross_scope_02 | 0 | hard_cross_scope | answer_rule_miss_any_group |
| safe_version_replace_structured_guided | hard_cross_scope_02 | 0 | hard_cross_scope | answer_rule_miss_required_terms |
| safe_version_replace_near_query_block | hard_duplicate_cleanup_01 | 0 | hard_duplicate_cleanup | answer_rule_miss_required_terms |
| safe_version_replace_guided | hard_graph_bridge_02 | 0 | hard_graph_bridge | answer_rule_miss_required_terms |
| safe_version_replace | hard_preference_recall_01 | 0 | hard_preference_recall | answer_rule_miss_required_terms |
| safe_version_replace_guided | hard_preference_recall_01 | 0 | hard_preference_recall | answer_rule_miss_required_terms |
| safe_version_replace_near_query_block | hard_preference_recall_01 | 0 | hard_preference_recall | answer_rule_miss_required_terms |
| safe_version_replace_structured_guided | hard_preference_recall_01 | 0 | hard_preference_recall | answer_rule_miss_required_terms |
| safe_version_replace_guided | hard_preference_recall_02 | 0 | hard_preference_recall | answer_rule_miss_required_terms |
| safe_version_replace_near_query_block | hard_preference_recall_02 | 0 | hard_preference_recall | answer_rule_miss_required_terms |
| safe_version_replace_structured_guided | hard_preference_recall_02 | 0 | hard_preference_recall | answer_rule_miss_required_terms |
| safe_version_replace | hard_stale_sleep_01 | 0 | hard_stale_sleep | answer_rule_miss_required_terms |
| safe_version_replace_guided | hard_stale_sleep_01 | 0 | hard_stale_sleep | answer_rule_miss_any_group |
| safe_version_replace_near_query_block | hard_stale_sleep_01 | 0 | hard_stale_sleep | answer_rule_miss_required_terms |
| safe_version_replace | hard_stale_sleep_02 | 0 | hard_stale_sleep | answer_rule_miss_required_terms |
| safe_version_replace_near_query_block | hard_stale_sleep_02 | 0 | hard_stale_sleep | answer_rule_miss_any_group |
| safe_version_replace_structured_guided | hard_stale_sleep_02 | 0 | hard_stale_sleep | answer_rule_miss_any_group |
| safe_version_replace | hard_style_preference_02 | 0 | hard_style_preference | answer_rule_miss_required_terms |
| safe_version_replace_near_query_block | hard_style_preference_02 | 0 | hard_style_preference | answer_rule_miss_required_terms |
| safe_version_replace | hard_tri_rrf_01 | 0 | hard_tri_rrf | answer_rule_miss_required_terms |
| safe_version_replace | hard_version_chain_02 | 0 | hard_version_chain | answer_rule_miss_required_terms |
| safe_version_replace_near_query_block | hard_version_chain_02 | 0 | hard_version_chain | answer_rule_miss_any_group |

## Pairwise Mismatches

| comparison_mode | case_id | repeat | category | movement |
| --- | --- | ---: | --- | --- |
| safe_version_replace | common_conflict_resolution_02 | 0 | common_conflict_resolution | anchor_passed_comparison_failed |
| safe_version_replace_structured_guided | common_conflict_resolution_02 | 0 | common_conflict_resolution | anchor_passed_comparison_failed |
| safe_version_replace | common_cross_scope_01 | 0 | common_cross_scope | anchor_passed_comparison_failed |
| safe_version_replace_near_query_block | common_cross_scope_01 | 0 | common_cross_scope | anchor_passed_comparison_failed |
| safe_version_replace | common_cross_scope_02 | 0 | common_cross_scope | anchor_passed_comparison_failed |
| safe_version_replace_structured_guided | common_preference_recall_01 | 0 | common_preference_recall | anchor_failed_comparison_passed |
| safe_version_replace | common_stale_sleep_01 | 0 | common_stale_sleep | anchor_passed_comparison_failed |
| safe_version_replace_near_query_block | common_stale_sleep_01 | 0 | common_stale_sleep | anchor_passed_comparison_failed |
| safe_version_replace | common_style_preference_02 | 0 | common_style_preference | anchor_passed_comparison_failed |
| safe_version_replace_near_query_block | common_style_preference_02 | 0 | common_style_preference | anchor_passed_comparison_failed |
| safe_version_replace_near_query_block | common_tool_preference_01 | 0 | common_tool_preference | anchor_failed_comparison_passed |
| safe_version_replace | common_version_chain_02 | 0 | common_version_chain | anchor_failed_comparison_passed |
| safe_version_replace_structured_guided | common_version_chain_02 | 0 | common_version_chain | anchor_failed_comparison_passed |
| safe_version_replace_structured_guided | hard_conflict_resolution_01 | 0 | hard_conflict_resolution | anchor_passed_comparison_failed |
| safe_version_replace_near_query_block | hard_conflict_resolution_01 | 0 | hard_conflict_resolution | anchor_passed_comparison_failed |
| safe_version_replace_near_query_block | hard_cross_scope_01 | 0 | hard_cross_scope | anchor_passed_comparison_failed |
| safe_version_replace | hard_cross_scope_02 | 0 | hard_cross_scope | anchor_passed_comparison_failed |
| safe_version_replace_structured_guided | hard_cross_scope_02 | 0 | hard_cross_scope | anchor_passed_comparison_failed |
| safe_version_replace_near_query_block | hard_cross_scope_02 | 0 | hard_cross_scope | anchor_passed_comparison_failed |
| safe_version_replace_near_query_block | hard_duplicate_cleanup_01 | 0 | hard_duplicate_cleanup | anchor_passed_comparison_failed |
| safe_version_replace | hard_graph_bridge_02 | 0 | hard_graph_bridge | anchor_failed_comparison_passed |
| safe_version_replace_structured_guided | hard_graph_bridge_02 | 0 | hard_graph_bridge | anchor_failed_comparison_passed |
| safe_version_replace_near_query_block | hard_graph_bridge_02 | 0 | hard_graph_bridge | anchor_failed_comparison_passed |
| safe_version_replace | hard_preference_recall_02 | 0 | hard_preference_recall | anchor_failed_comparison_passed |
| safe_version_replace_structured_guided | hard_stale_sleep_01 | 0 | hard_stale_sleep | anchor_failed_comparison_passed |
| safe_version_replace | hard_stale_sleep_02 | 0 | hard_stale_sleep | anchor_passed_comparison_failed |
| safe_version_replace_structured_guided | hard_stale_sleep_02 | 0 | hard_stale_sleep | anchor_passed_comparison_failed |
| safe_version_replace_near_query_block | hard_stale_sleep_02 | 0 | hard_stale_sleep | anchor_passed_comparison_failed |
| safe_version_replace | hard_style_preference_02 | 0 | hard_style_preference | anchor_passed_comparison_failed |
| safe_version_replace_near_query_block | hard_style_preference_02 | 0 | hard_style_preference | anchor_passed_comparison_failed |
| safe_version_replace | hard_tri_rrf_01 | 0 | hard_tri_rrf | anchor_passed_comparison_failed |
| safe_version_replace | hard_version_chain_02 | 0 | hard_version_chain | anchor_passed_comparison_failed |
| safe_version_replace_near_query_block | hard_version_chain_02 | 0 | hard_version_chain | anchor_passed_comparison_failed |
