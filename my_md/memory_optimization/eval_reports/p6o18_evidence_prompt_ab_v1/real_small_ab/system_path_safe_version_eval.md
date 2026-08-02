# System Path Safe Version Governed

本报告使用 system-path provider validation；不包含原始 query、prompt、memory summary 或完整回答。

- evaluation_level: `system_path_safe_version_governed`
- real_llm_enabled: `True`
- unique_case_count: `40`
- case_count: `160`
- replacement_seeded_count: `160`

| mode | cases | answer_success | answer_rate | grounding_rate | forbidden_rate | contract_success | post_check_shadow | avg_tokens | avg_latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| safe_version_replace | 40 | 24 | 60.0 | 100.0 | 0.0 | 100.0 | 100.0 | 5394.275 | 3923.425 |
| safe_version_replace_guided | 40 | 31 | 77.5 | 100.0 | 0.0 | 100.0 | 100.0 | 5481.8 | 3625.4 |
| safe_version_replace_structured_guided | 40 | 31 | 77.5 | 100.0 | 0.0 | 100.0 | 100.0 | 5577.075 | 4032.775 |
| safe_version_replace_near_query_block | 40 | 23 | 57.5 | 100.0 | 0.0 | 100.0 | 100.0 | 5524.125 | 3954.9 |
