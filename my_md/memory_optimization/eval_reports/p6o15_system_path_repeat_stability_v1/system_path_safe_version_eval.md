# System Path Safe Version Governed

本报告使用 system-path provider validation；不包含原始 query、prompt、memory summary 或完整回答。

- evaluation_level: `system_path_safe_version_governed`
- real_llm_enabled: `True`
- unique_case_count: `40`
- case_count: `240`
- replacement_seeded_count: `240`

| mode | cases | answer_success | answer_rate | grounding_rate | forbidden_rate | contract_success | post_check_shadow | avg_tokens | avg_latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| current | 120 | 31 | 25.8333 | 100.0 | 39.1667 | 0.0 | 0.0 | 5582.0 | 4627.15 |
| safe_version_replace | 120 | 88 | 73.3333 | 100.0 | 0.0 | 100.0 | 100.0 | 5427.0833 | 3259.7667 |
