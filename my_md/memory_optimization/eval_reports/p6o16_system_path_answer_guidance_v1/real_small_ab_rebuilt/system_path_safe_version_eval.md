# System Path Safe Version Governed

本报告使用 system-path provider validation；不包含原始 query、prompt、memory summary 或完整回答。

- evaluation_level: `system_path_safe_version_governed`
- real_llm_enabled: `True`
- unique_case_count: `40`
- case_count: `120`
- replacement_seeded_count: `120`

| mode | cases | answer_success | answer_rate | grounding_rate | forbidden_rate | contract_success | post_check_shadow | avg_tokens | avg_latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| current | 40 | 10 | 25.0 | 100.0 | 27.5 | 0.0 | 0.0 | 5530.525 | 4734.875 |
| safe_version_replace | 40 | 26 | 65.0 | 100.0 | 0.0 | 100.0 | 100.0 | 5382.625 | 3261.825 |
| safe_version_replace_guided | 40 | 29 | 72.5 | 100.0 | 0.0 | 100.0 | 100.0 | 5467.7 | 3207.6 |
