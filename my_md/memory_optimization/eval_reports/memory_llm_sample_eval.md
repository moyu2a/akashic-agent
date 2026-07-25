# Memory Real LLM Small-Sample Evaluation Report

本报告只记录答案质量指标、延迟、token 元数据和脱敏失败原因。
报告不包含原始 query、memory summary、prompt、session 原文或完整回答。

## Summary

- `answer_contains_miss_count`: `0`
- `answer_contains_pass_count`: `10`
- `answer_quality_available`: `True`
- `answer_rule_pass_count`: `10`
- `answer_rule_pass_count_by_prompt_variant`: `{'baseline': 5, 'coached': 5}`
- `avg_latency_ms`: `4697`
- `case_count`: `10`
- `completion_token_count`: `2697`
- `expected_memory_used_count`: `10`
- `failed_case_count`: `0`
- `forbidden_contains_violation_count`: `0`
- `full_answer_included`: `False`
- `language_pass_count`: `10`
- `memory_grounding_pass_count`: `10`
- `memory_grounding_pass_count_by_prompt_variant`: `{'baseline': 5, 'coached': 5}`
- `pass_count_by_prompt_variant`: `{'baseline': 5, 'coached': 5}`
- `passed_case_count`: `10`
- `phase6b_level`: `real_llm_small_sample`
- `prompt_included`: `False`
- `prompt_token_count`: `49865`
- `prompt_variant_mode`: `both`
- `provider_error_count`: `0`
- `raw_memory_summary_included`: `False`
- `raw_query_included`: `False`
- `real_llm_enabled`: `True`
- `repeat_answer_rule_pass_rate`: `1.0`
- `repeat_count`: `5`
- `repeat_memory_grounding_pass_rate`: `1.0`
- `repeat_pass_rate`: `1.0`
- `session_text_included`: `False`
- `timeout_count`: `0`
- `token_metrics_available`: `True`
- `total_latency_ms`: `46977`
- `total_token_count`: `52562`

## Case Records

- `vague_reference_graph`: `{"answer_length": 257, "answer_rule_passed": true, "case_id": "vague_reference_graph", "category": "vague_reference", "channel": "cli", "chat_id": "local", "completion_token_count": 324, "expected_contains_miss_count": 0, "expected_contains_pass_count": 1, "expected_memory_used": true, "failures": [], "forbidden_contains_violation_count": 0, "language_passed": true, "latency_ms": 5488, "memory_grounding_passed": true, "passed": true, "prompt_token_count": 4973, "prompt_variant": "baseline", "provider_error": false, "repeat_index": 0, "session_key": "cli:local", "timeout": false, "token_metrics_available": true, "total_token_count": 5297, "used_memory_ids": ["m_graph_1", "m_graph_2"]}`
- `vague_reference_graph`: `{"answer_length": 69, "answer_rule_passed": true, "case_id": "vague_reference_graph", "category": "vague_reference", "channel": "cli", "chat_id": "local", "completion_token_count": 283, "expected_contains_miss_count": 0, "expected_contains_pass_count": 1, "expected_memory_used": true, "failures": [], "forbidden_contains_violation_count": 0, "language_passed": true, "latency_ms": 5061, "memory_grounding_passed": true, "passed": true, "prompt_token_count": 5000, "prompt_variant": "coached", "provider_error": false, "repeat_index": 0, "session_key": "cli:local", "timeout": false, "token_metrics_available": true, "total_token_count": 5283, "used_memory_ids": ["m_graph_1", "m_graph_2"]}`
- `vague_reference_graph`: `{"answer_length": 110, "answer_rule_passed": true, "case_id": "vague_reference_graph", "category": "vague_reference", "channel": "cli", "chat_id": "local", "completion_token_count": 224, "expected_contains_miss_count": 0, "expected_contains_pass_count": 1, "expected_memory_used": true, "failures": [], "forbidden_contains_violation_count": 0, "language_passed": true, "latency_ms": 3634, "memory_grounding_passed": true, "passed": true, "prompt_token_count": 4973, "prompt_variant": "baseline", "provider_error": false, "repeat_index": 1, "session_key": "cli:local", "timeout": false, "token_metrics_available": true, "total_token_count": 5197, "used_memory_ids": ["m_graph_1", "m_graph_2"]}`
- `vague_reference_graph`: `{"answer_length": 134, "answer_rule_passed": true, "case_id": "vague_reference_graph", "category": "vague_reference", "channel": "cli", "chat_id": "local", "completion_token_count": 429, "expected_contains_miss_count": 0, "expected_contains_pass_count": 1, "expected_memory_used": true, "failures": [], "forbidden_contains_violation_count": 0, "language_passed": true, "latency_ms": 6588, "memory_grounding_passed": true, "passed": true, "prompt_token_count": 5000, "prompt_variant": "coached", "provider_error": false, "repeat_index": 1, "session_key": "cli:local", "timeout": false, "token_metrics_available": true, "total_token_count": 5429, "used_memory_ids": ["m_graph_1", "m_graph_2"]}`
- `vague_reference_graph`: `{"answer_length": 168, "answer_rule_passed": true, "case_id": "vague_reference_graph", "category": "vague_reference", "channel": "cli", "chat_id": "local", "completion_token_count": 304, "expected_contains_miss_count": 0, "expected_contains_pass_count": 1, "expected_memory_used": true, "failures": [], "forbidden_contains_violation_count": 0, "language_passed": true, "latency_ms": 4801, "memory_grounding_passed": true, "passed": true, "prompt_token_count": 4973, "prompt_variant": "baseline", "provider_error": false, "repeat_index": 2, "session_key": "cli:local", "timeout": false, "token_metrics_available": true, "total_token_count": 5277, "used_memory_ids": ["m_graph_1", "m_graph_2"]}`
- `vague_reference_graph`: `{"answer_length": 34, "answer_rule_passed": true, "case_id": "vague_reference_graph", "category": "vague_reference", "channel": "cli", "chat_id": "local", "completion_token_count": 142, "expected_contains_miss_count": 0, "expected_contains_pass_count": 1, "expected_memory_used": true, "failures": [], "forbidden_contains_violation_count": 0, "language_passed": true, "latency_ms": 2632, "memory_grounding_passed": true, "passed": true, "prompt_token_count": 5000, "prompt_variant": "coached", "provider_error": false, "repeat_index": 2, "session_key": "cli:local", "timeout": false, "token_metrics_available": true, "total_token_count": 5142, "used_memory_ids": ["m_graph_1", "m_graph_2"]}`
- `vague_reference_graph`: `{"answer_length": 106, "answer_rule_passed": true, "case_id": "vague_reference_graph", "category": "vague_reference", "channel": "cli", "chat_id": "local", "completion_token_count": 395, "expected_contains_miss_count": 0, "expected_contains_pass_count": 1, "expected_memory_used": true, "failures": [], "forbidden_contains_violation_count": 0, "language_passed": true, "latency_ms": 6597, "memory_grounding_passed": true, "passed": true, "prompt_token_count": 4973, "prompt_variant": "baseline", "provider_error": false, "repeat_index": 3, "session_key": "cli:local", "timeout": false, "token_metrics_available": true, "total_token_count": 5368, "used_memory_ids": ["m_graph_1", "m_graph_2"]}`
- `vague_reference_graph`: `{"answer_length": 69, "answer_rule_passed": true, "case_id": "vague_reference_graph", "category": "vague_reference", "channel": "cli", "chat_id": "local", "completion_token_count": 131, "expected_contains_miss_count": 0, "expected_contains_pass_count": 1, "expected_memory_used": true, "failures": [], "forbidden_contains_violation_count": 0, "language_passed": true, "latency_ms": 2958, "memory_grounding_passed": true, "passed": true, "prompt_token_count": 5000, "prompt_variant": "coached", "provider_error": false, "repeat_index": 3, "session_key": "cli:local", "timeout": false, "token_metrics_available": true, "total_token_count": 5131, "used_memory_ids": ["m_graph_1", "m_graph_2"]}`
- `vague_reference_graph`: `{"answer_length": 61, "answer_rule_passed": true, "case_id": "vague_reference_graph", "category": "vague_reference", "channel": "cli", "chat_id": "local", "completion_token_count": 188, "expected_contains_miss_count": 0, "expected_contains_pass_count": 1, "expected_memory_used": true, "failures": [], "forbidden_contains_violation_count": 0, "language_passed": true, "latency_ms": 4228, "memory_grounding_passed": true, "passed": true, "prompt_token_count": 4973, "prompt_variant": "baseline", "provider_error": false, "repeat_index": 4, "session_key": "cli:local", "timeout": false, "token_metrics_available": true, "total_token_count": 5161, "used_memory_ids": ["m_graph_1", "m_graph_2"]}`
- `vague_reference_graph`: `{"answer_length": 72, "answer_rule_passed": true, "case_id": "vague_reference_graph", "category": "vague_reference", "channel": "cli", "chat_id": "local", "completion_token_count": 277, "expected_contains_miss_count": 0, "expected_contains_pass_count": 1, "expected_memory_used": true, "failures": [], "forbidden_contains_violation_count": 0, "language_passed": true, "latency_ms": 4990, "memory_grounding_passed": true, "passed": true, "prompt_token_count": 5000, "prompt_variant": "coached", "provider_error": false, "repeat_index": 4, "session_key": "cli:local", "timeout": false, "token_metrics_available": true, "total_token_count": 5277, "used_memory_ids": ["m_graph_1", "m_graph_2"]}`

## Failure Records
