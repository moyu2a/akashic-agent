# Memory Real LLM Small-Sample Evaluation Report

本报告只记录答案质量指标、延迟、token 元数据和脱敏失败原因。
报告不包含原始 query、memory summary、prompt、session 原文或完整回答。

## Summary

- `answer_contains_miss_count`: `0`
- `answer_contains_pass_count`: `5`
- `answer_quality_available`: `True`
- `avg_latency_ms`: `18`
- `case_count`: `3`
- `completion_token_count`: `30`
- `expected_memory_used_count`: `3`
- `failed_case_count`: `0`
- `forbidden_contains_violation_count`: `0`
- `full_answer_included`: `False`
- `language_pass_count`: `3`
- `passed_case_count`: `3`
- `phase6b_level`: `real_llm_small_sample`
- `prompt_included`: `False`
- `prompt_token_count`: `60`
- `provider_error_count`: `0`
- `raw_memory_summary_included`: `False`
- `raw_query_included`: `False`
- `real_llm_enabled`: `False`
- `session_text_included`: `False`
- `timeout_count`: `0`
- `token_metrics_available`: `True`
- `total_latency_ms`: `56`
- `total_token_count`: `90`

## Case Records

- `cross_scope_isolation`: `{"answer_length": 21, "case_id": "cross_scope_isolation", "category": "scope_isolation", "channel": "telegram", "chat_id": "123", "completion_token_count": 10, "expected_contains_miss_count": 0, "expected_contains_pass_count": 2, "expected_memory_used": true, "failures": [], "forbidden_contains_violation_count": 0, "language_passed": true, "latency_ms": 20, "passed": true, "prompt_token_count": 20, "provider_error": false, "session_key": "telegram:123", "timeout": false, "token_metrics_available": true, "total_token_count": 30, "used_memory_ids": ["m_tg_pref"]}`
- `preference_recall`: `{"answer_length": 10, "case_id": "preference_recall", "category": "preference_recall", "channel": "cli", "chat_id": "local", "completion_token_count": 10, "expected_contains_miss_count": 0, "expected_contains_pass_count": 1, "expected_memory_used": true, "failures": [], "forbidden_contains_violation_count": 0, "language_passed": true, "latency_ms": 18, "passed": true, "prompt_token_count": 20, "provider_error": false, "session_key": "cli:local", "timeout": false, "token_metrics_available": true, "total_token_count": 30, "used_memory_ids": ["m_pref_cn"]}`
- `vague_reference_graph`: `{"answer_length": 30, "case_id": "vague_reference_graph", "category": "vague_reference", "channel": "cli", "chat_id": "local", "completion_token_count": 10, "expected_contains_miss_count": 0, "expected_contains_pass_count": 2, "expected_memory_used": true, "failures": [], "forbidden_contains_violation_count": 0, "language_passed": true, "latency_ms": 18, "passed": true, "prompt_token_count": 20, "provider_error": false, "session_key": "cli:local", "timeout": false, "token_metrics_available": true, "total_token_count": 30, "used_memory_ids": ["m_graph_1", "m_graph_2"]}`

## Failure Records
