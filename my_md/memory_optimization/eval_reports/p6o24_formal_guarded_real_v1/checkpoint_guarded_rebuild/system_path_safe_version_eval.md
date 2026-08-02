# System Path Safe Version Governed

本报告使用 system-path provider validation；不包含原始 query、prompt、memory summary 或完整回答。

- evaluation_level: `system_path_safe_version_governed`
- real_llm_enabled: `True`
- unique_case_count: `40`
- case_count: `120`
- replacement_seeded_count: `120`

| mode | cases | answer_success | answer_rate | grounding_rate | forbidden_rate | contract_success | post_check_shadow | avg_tokens | avg_latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| safe_version_replace | 40 | 30 | 75.0 | 100.0 | 0.0 | 100.0 | 100.0 | 5407.575 | 3411.925 |
| safe_version_replace_guided | 40 | 32 | 80.0 | 100.0 | 0.0 | 100.0 | 100.0 | 5485.15 | 3283.725 |
| safe_version_replace_guided_with_retry_shadow | 40 | 29 | 72.5 | 100.0 | 0.0 | 100.0 | 100.0 | 5553.575 | 3050.95 |
