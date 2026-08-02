# System Path Safe Version Governed

本报告使用 system-path provider validation；不包含原始 query、prompt、memory summary 或完整回答。

- evaluation_level: `system_path_safe_version_governed`
- real_llm_enabled: `True`
- unique_case_count: `40`
- case_count: `240`
- replacement_seeded_count: `240`

| mode | cases | answer_success | answer_rate | grounding_rate | forbidden_rate | contract_success | post_check_shadow | avg_tokens | avg_latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| safe_version_replace | 120 | 77 | 64.1667 | 100.0 | 0.0 | 100.0 | 100.0 | 5418.8833 | 3441.175 |
| safe_version_replace_guided | 120 | 80 | 66.6667 | 100.0 | 0.0 | 100.0 | 100.0 | 5522.75 | 3518.9083 |
