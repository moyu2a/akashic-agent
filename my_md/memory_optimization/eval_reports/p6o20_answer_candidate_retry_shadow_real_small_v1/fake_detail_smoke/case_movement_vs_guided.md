# P6o-20 Case Movement vs Guided

- anchor_mode: `safe_version_replace_guided`
- comparison_mode: `safe_version_replace_guided_with_retry_shadow`
- paired_case_count: `4`
- unpaired_case_count: `0`
- movement_counts: `{"anchor_failed_comparison_passed": 0, "anchor_passed_comparison_failed": 0, "both_failed": 4, "both_passed": 0}`

| case_id | category | repeat | anchor_passed | comparison_passed | movement | anchor_failures | comparison_failures | comparison_retry_reasons |
| --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| `common_preference_recall_01` | `common_preference_recall` | 0 | false | false | `both_failed` | `missing_expected_answer_term, missing_expected_answer_term_group, missing_expected_answer_term_group` | `missing_expected_answer_term, missing_expected_answer_term_group, missing_expected_answer_term_group` | `required_terms_missing, answer_choice_group_missing` |
| `common_tool_preference_01` | `common_tool_preference` | 0 | false | false | `both_failed` | `missing_expected_answer_term, missing_expected_answer_term_group, missing_expected_answer_term_group` | `missing_expected_answer_term, missing_expected_answer_term_group, missing_expected_answer_term_group` | `required_terms_missing, answer_choice_group_missing` |
| `hard_preference_recall_01` | `hard_preference_recall` | 0 | false | false | `both_failed` | `missing_expected_answer_term, missing_expected_answer_term_group, missing_expected_answer_term_group` | `missing_expected_answer_term, missing_expected_answer_term_group, missing_expected_answer_term_group` | `required_terms_missing, answer_choice_group_missing` |
| `hard_tool_preference_01` | `hard_tool_preference` | 0 | false | false | `both_failed` | `missing_expected_answer_term, missing_expected_answer_term_group, missing_expected_answer_term_group` | `missing_expected_answer_term, missing_expected_answer_term_group, missing_expected_answer_term_group` | `required_terms_missing, answer_choice_group_missing` |
