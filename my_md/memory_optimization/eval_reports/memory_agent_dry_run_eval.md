# Memory Agent Dry-Run Evaluation Report

本报告使用真实 AgentLoop 和 fake LLM，不调用真实 LLM，不代表最终回答质量。
报告默认不包含真实 query、memory summary、prompt 或 session 原文。

## Summary

- `agent_loop_enabled`: `True`
- `agent_turn_count`: `9`
- `answer_quality_available`: `False`
- `case_count`: `9`
- `embedding_calls_enabled`: `False`
- `failed_case_count`: `0`
- `fake_llm_call_count`: `9`
- `fake_llm_enabled`: `True`
- `llm_calls_enabled`: `False`
- `passed_case_count`: `9`
- `phase6b_level`: `agent_dry_run`
- `prompt_included`: `False`
- `raw_memory_summary_included`: `False`
- `raw_query_included`: `False`
- `retrieval_request_count`: `9`
- `session_message_count`: `18`
- `session_text_included`: `False`
- `turn_committed_count`: `9`

## Case Records

- `conflict_memory`: `{"case_id": "conflict_memory", "category": "conflict_detection", "channel": "cli", "chat_id": "local", "failures": [], "fake_llm_call_count": 1, "passed": true, "reply_length": 16, "retrieval_history_seen": true, "retrieval_query_matched": true, "retrieval_request_count": 1, "session_key": "cli:local", "session_message_count": 2, "turn_committed_count": 1}`
- `cross_scope_isolation`: `{"case_id": "cross_scope_isolation", "category": "scope_isolation", "channel": "telegram", "chat_id": "123", "failures": [], "fake_llm_call_count": 1, "passed": true, "reply_length": 16, "retrieval_history_seen": true, "retrieval_query_matched": true, "retrieval_request_count": 1, "session_key": "telegram:123", "session_message_count": 2, "turn_committed_count": 1}`
- `duplicate_memory`: `{"case_id": "duplicate_memory", "category": "duplicate_detection", "channel": "cli", "chat_id": "local", "failures": [], "fake_llm_call_count": 1, "passed": true, "reply_length": 16, "retrieval_history_seen": true, "retrieval_query_matched": true, "retrieval_request_count": 1, "session_key": "cli:local", "session_message_count": 2, "turn_committed_count": 1}`
- `injection_governance_budget`: `{"case_id": "injection_governance_budget", "category": "injection_governance", "channel": "cli", "chat_id": "local", "failures": [], "fake_llm_call_count": 1, "passed": true, "reply_length": 16, "retrieval_history_seen": true, "retrieval_query_matched": true, "retrieval_request_count": 1, "session_key": "cli:local", "session_message_count": 2, "turn_committed_count": 1}`
- `preference_recall`: `{"case_id": "preference_recall", "category": "preference_recall", "channel": "cli", "chat_id": "local", "failures": [], "fake_llm_call_count": 1, "passed": true, "reply_length": 16, "retrieval_history_seen": true, "retrieval_query_matched": true, "retrieval_request_count": 1, "session_key": "cli:local", "session_message_count": 2, "turn_committed_count": 1}`
- `provenance_trace`: `{"case_id": "provenance_trace", "category": "provenance", "channel": "cli", "chat_id": "local", "failures": [], "fake_llm_call_count": 1, "passed": true, "reply_length": 16, "retrieval_history_seen": true, "retrieval_query_matched": true, "retrieval_request_count": 1, "session_key": "cli:local", "session_message_count": 2, "turn_committed_count": 1}`
- `stale_memory_sleep`: `{"case_id": "stale_memory_sleep", "category": "sleep_consolidation", "channel": "cli", "chat_id": "local", "failures": [], "fake_llm_call_count": 1, "passed": true, "reply_length": 16, "retrieval_history_seen": true, "retrieval_query_matched": true, "retrieval_request_count": 1, "session_key": "cli:local", "session_message_count": 2, "turn_committed_count": 1}`
- `temporary_memory_pollution`: `{"case_id": "temporary_memory_pollution", "category": "write_value", "channel": "cli", "chat_id": "local", "failures": [], "fake_llm_call_count": 1, "passed": true, "reply_length": 16, "retrieval_history_seen": true, "retrieval_query_matched": true, "retrieval_request_count": 1, "session_key": "cli:local", "session_message_count": 2, "turn_committed_count": 1}`
- `vague_reference_graph`: `{"case_id": "vague_reference_graph", "category": "vague_reference", "channel": "cli", "chat_id": "local", "failures": [], "fake_llm_call_count": 1, "passed": true, "reply_length": 16, "retrieval_history_seen": true, "retrieval_query_matched": true, "retrieval_request_count": 1, "session_key": "cli:local", "session_message_count": 2, "turn_committed_count": 1}`

## Failure Records
