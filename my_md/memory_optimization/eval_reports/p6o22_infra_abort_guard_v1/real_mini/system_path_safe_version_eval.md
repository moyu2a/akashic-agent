# System Path Safe Version Governed

本报告使用 system-path provider validation；不包含原始 query、prompt、memory summary 或完整回答。

- evaluation_level: `system_path_safe_version_governed`
- real_llm_enabled: `True`
- unique_case_count: `3`
- case_count: `9`
- replacement_seeded_count: `9`

| mode | cases | answer_success | answer_rate | grounding_rate | forbidden_rate | contract_success | post_check_shadow | avg_tokens | avg_latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| safe_version_replace | 3 | 2 | 66.6667 | 100.0 | 0.0 | 100.0 | 100.0 | 5509.3333 | 5606.6667 |
| safe_version_replace_guided | 3 | 1 | 33.3333 | 100.0 | 0.0 | 100.0 | 100.0 | 5482.3333 | 4172.3333 |
| safe_version_replace_guided_with_retry_shadow | 3 | 1 | 33.3333 | 100.0 | 0.0 | 100.0 | 100.0 | 5473.3333 | 3491.3333 |
