# System Path Safe Version Governed

本报告使用 system-path provider validation；不包含原始 query、prompt、memory summary 或完整回答。

- evaluation_level: `system_path_safe_version_governed`
- real_llm_enabled: `True`
- unique_case_count: `10`
- case_count: `30`
- replacement_seeded_count: `30`

| mode | cases | answer_success | answer_rate | grounding_rate | forbidden_rate | contract_success | post_check_shadow | avg_tokens | avg_latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| safe_version_replace | 10 | 6 | 60.0 | 100.0 | 0.0 | 100.0 | 100.0 | 5416.3 | 3112.5 |
| safe_version_replace_guided | 10 | 6 | 60.0 | 100.0 | 0.0 | 100.0 | 100.0 | 5485.7 | 2747.9 |
| safe_version_replace_guided_with_retry_shadow | 10 | 6 | 60.0 | 100.0 | 0.0 | 100.0 | 100.0 | 5720.3 | 4021.5 |
