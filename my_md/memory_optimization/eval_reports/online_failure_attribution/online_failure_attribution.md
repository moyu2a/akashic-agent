# Online Failure Attribution

本报告用于解释真实/线上回答质量评测中每个 profile 的失败类型，不重新评分历史 checkpoint。

## Overview

- `case_record_count`: `1920`
- `profile_count`: `6`
- `source_real_llm_enabled`: `True`

## Profile Attribution

| profile | cases | answer_fail | grounding_fail | forbidden_fail | grounded_but_answer_failed | answer_pass_but_grounding_failed | primary_issue | avg_token_delta_vs_base | avg_latency_delta_vs_base |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| chain_all_on | 320 | 245 | 0 | 79 | 245 | 0 | grounded_but_answer_failed | -32.4625 | 153.575 |
| chain_graph_retrieval | 320 | 236 | 0 | 95 | 236 | 0 | grounded_but_answer_failed | 94.1344 | 265.8906 |
| chain_memory_base | 320 | 185 | 12 | 39 | 180 | 7 | grounded_but_answer_failed | N/A | N/A |
| chain_rerank_injection | 320 | 193 | 0 | 31 | 193 | 0 | grounded_but_answer_failed | -67.9188 | -373.2156 |
| chain_tri_retrieval | 320 | 229 | 0 | 96 | 229 | 0 | grounded_but_answer_failed | 126.5563 | 590.9625 |
| chain_version_provenance | 320 | 191 | 320 | 3 | 0 | 129 | grounding_only_failure | -115.3031 | -198.6687 |

## Failure Codes

- `chain_all_on`: `found_forbidden_answer_term`=79, `missing_expected_answer_term`=158, `missing_expected_answer_term_group`=217
- `chain_graph_retrieval`: `found_forbidden_answer_term`=95, `missing_expected_answer_term`=151, `missing_expected_answer_term_group`=191
- `chain_memory_base`: `answer_is_not_detected_as_chinese`=2, `found_forbidden_answer_term`=41, `missing_expected_answer_term`=118, `missing_expected_answer_term_group`=176, `missing_expected_memory_ids`=12
- `chain_rerank_injection`: `answer_is_not_detected_as_chinese`=3, `found_forbidden_answer_term`=32, `missing_expected_answer_term`=138, `missing_expected_answer_term_group`=178
- `chain_tri_retrieval`: `answer_is_not_detected_as_chinese`=1, `found_forbidden_answer_term`=96, `missing_expected_answer_term`=143, `missing_expected_answer_term_group`=184
- `chain_version_provenance`: `found_forbidden_answer_term`=3, `missing_expected_answer_term`=186, `missing_expected_answer_term_group`=214, `missing_expected_memory_ids`=320

## Representative Failure Examples

- `chain_all_on`: `missing_expected_answer_term_group` ; `found_forbidden_answer_term` ; `missing_expected_answer_term`
- `chain_graph_retrieval`: `missing_expected_answer_term_group` ; `found_forbidden_answer_term` ; `missing_expected_answer_term`
- `chain_memory_base`: `missing_expected_answer_term` ; `missing_expected_answer_term_group` ; `found_forbidden_answer_term` ; `answer is not detected as Chinese` ; `missing_expected_memory_ids`
- `chain_rerank_injection`: `missing_expected_answer_term_group` ; `answer is not detected as Chinese` ; `found_forbidden_answer_term` ; `missing_expected_answer_term`
- `chain_tri_retrieval`: `found_forbidden_answer_term` ; `missing_expected_answer_term` ; `missing_expected_answer_term_group` ; `answer is not detected as Chinese`
- `chain_version_provenance`: `missing_expected_answer_term_group` ; `missing_expected_memory_ids` ; `missing_expected_answer_term` ; `found_forbidden_answer_term`
