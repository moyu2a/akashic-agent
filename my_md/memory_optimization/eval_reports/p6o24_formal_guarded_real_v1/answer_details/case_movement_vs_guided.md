# P6o-20 Case Movement vs Guided

- anchor_mode: `safe_version_replace_guided`
- comparison_mode: `safe_version_replace_guided_with_retry_shadow`
- paired_case_count: `40`
- unpaired_case_count: `0`
- movement_counts: `{"anchor_failed_comparison_passed": 4, "anchor_passed_comparison_failed": 7, "both_failed": 4, "both_passed": 25}`

| case_id | category | repeat | anchor_passed | comparison_passed | movement | anchor_failures | comparison_failures | comparison_retry_reasons |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| `common_conflict_resolution_01` | `common_conflict_resolution` | 0 | false | false | `both_failed` | `missing_expected_answer_term, missing_expected_answer_term_group, missing_expected_answer_term_group` | `missing_expected_answer_term_group` | `answer_choice_group_missing` |
| `common_conflict_resolution_02` | `common_conflict_resolution` | 0 | false | true | `anchor_failed_comparison_passed` | `missing_expected_answer_term_group` | `` | `` |
| `common_cross_scope_01` | `common_cross_scope` | 0 | true | true | `both_passed` | `` | `` | `` |
| `common_cross_scope_02` | `common_cross_scope` | 0 | true | true | `both_passed` | `` | `` | `` |
| `common_duplicate_cleanup_01` | `common_duplicate_cleanup` | 0 | true | true | `both_passed` | `` | `` | `` |
| `common_duplicate_cleanup_02` | `common_duplicate_cleanup` | 0 | true | true | `both_passed` | `` | `` | `` |
| `common_graph_bridge_01` | `common_graph_bridge` | 0 | true | true | `both_passed` | `` | `` | `` |
| `common_graph_bridge_02` | `common_graph_bridge` | 0 | true | true | `both_passed` | `` | `` | `` |
| `common_preference_recall_01` | `common_preference_recall` | 0 | false | false | `both_failed` | `missing_expected_answer_term_group` | `missing_expected_answer_term, missing_expected_answer_term_group, missing_expected_answer_term_group` | `required_terms_missing, answer_choice_group_missing` |
| `common_preference_recall_02` | `common_preference_recall` | 0 | false | false | `both_failed` | `missing_expected_answer_term_group` | `missing_expected_answer_term_group` | `answer_choice_group_missing` |
| `common_stale_sleep_01` | `common_stale_sleep` | 0 | true | true | `both_passed` | `` | `` | `` |
| `common_stale_sleep_02` | `common_stale_sleep` | 0 | true | true | `both_passed` | `` | `` | `` |
| `common_style_preference_01` | `common_style_preference` | 0 | false | true | `anchor_failed_comparison_passed` | `missing_expected_answer_term, missing_expected_answer_term_group, missing_expected_answer_term_group` | `` | `` |
| `common_style_preference_02` | `common_style_preference` | 0 | true | true | `both_passed` | `` | `` | `` |
| `common_tool_preference_01` | `common_tool_preference` | 0 | true | false | `anchor_passed_comparison_failed` | `` | `answer_language_not_chinese` | `language_requirement_failed` |
| `common_tool_preference_02` | `common_tool_preference` | 0 | true | true | `both_passed` | `` | `` | `` |
| `common_tri_rrf_01` | `common_tri_rrf` | 0 | true | true | `both_passed` | `` | `` | `` |
| `common_tri_rrf_02` | `common_tri_rrf` | 0 | true | true | `both_passed` | `` | `` | `` |
| `common_version_chain_01` | `common_version_chain` | 0 | true | true | `both_passed` | `` | `` | `` |
| `common_version_chain_02` | `common_version_chain` | 0 | true | false | `anchor_passed_comparison_failed` | `` | `missing_expected_answer_term_group` | `answer_choice_group_missing` |
| `hard_conflict_resolution_01` | `hard_conflict_resolution` | 0 | false | false | `both_failed` | `missing_expected_answer_term_group` | `missing_expected_answer_term_group` | `answer_choice_group_missing` |
| `hard_conflict_resolution_02` | `hard_conflict_resolution` | 0 | true | true | `both_passed` | `` | `` | `` |
| `hard_cross_scope_01` | `hard_cross_scope` | 0 | false | true | `anchor_failed_comparison_passed` | `missing_expected_answer_term_group` | `` | `` |
| `hard_cross_scope_02` | `hard_cross_scope` | 0 | true | false | `anchor_passed_comparison_failed` | `` | `missing_expected_answer_term_group` | `answer_choice_group_missing` |
| `hard_duplicate_cleanup_01` | `hard_duplicate_cleanup` | 0 | true | true | `both_passed` | `` | `` | `` |
| `hard_duplicate_cleanup_02` | `hard_duplicate_cleanup` | 0 | false | true | `anchor_failed_comparison_passed` | `missing_expected_answer_term, missing_expected_answer_term_group` | `` | `` |
| `hard_graph_bridge_01` | `hard_graph_bridge` | 0 | true | true | `both_passed` | `` | `` | `` |
| `hard_graph_bridge_02` | `hard_graph_bridge` | 0 | true | false | `anchor_passed_comparison_failed` | `` | `missing_expected_answer_term` | `required_terms_missing` |
| `hard_preference_recall_01` | `hard_preference_recall` | 0 | true | true | `both_passed` | `` | `` | `` |
| `hard_preference_recall_02` | `hard_preference_recall` | 0 | true | true | `both_passed` | `` | `` | `` |
| `hard_stale_sleep_01` | `hard_stale_sleep` | 0 | true | false | `anchor_passed_comparison_failed` | `` | `missing_expected_answer_term, missing_expected_answer_term, missing_expected_answer_term_group, missing_expected_answer_term_group` | `required_terms_missing, answer_choice_group_missing` |
| `hard_stale_sleep_02` | `hard_stale_sleep` | 0 | true | false | `anchor_passed_comparison_failed` | `` | `missing_expected_answer_term` | `required_terms_missing` |
| `hard_style_preference_01` | `hard_style_preference` | 0 | true | true | `both_passed` | `` | `` | `` |
| `hard_style_preference_02` | `hard_style_preference` | 0 | true | false | `anchor_passed_comparison_failed` | `` | `missing_expected_answer_term, missing_expected_answer_term_group, missing_expected_answer_term_group` | `required_terms_missing, answer_choice_group_missing` |
| `hard_tool_preference_01` | `hard_tool_preference` | 0 | true | true | `both_passed` | `` | `` | `` |
| `hard_tool_preference_02` | `hard_tool_preference` | 0 | true | true | `both_passed` | `` | `` | `` |
| `hard_tri_rrf_01` | `hard_tri_rrf` | 0 | true | true | `both_passed` | `` | `` | `` |
| `hard_tri_rrf_02` | `hard_tri_rrf` | 0 | true | true | `both_passed` | `` | `` | `` |
| `hard_version_chain_01` | `hard_version_chain` | 0 | true | true | `both_passed` | `` | `` | `` |
| `hard_version_chain_02` | `hard_version_chain` | 0 | true | true | `both_passed` | `` | `` | `` |
