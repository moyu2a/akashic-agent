# System Path Safe Version Governed

本报告使用 system-path provider validation；不包含原始 query、prompt、memory summary 或完整回答。

- evaluation_level: `system_path_safe_version_governed`
- real_llm_enabled: `False`
- unique_case_count: `2`
- case_count: `1`
- replacement_seeded_count: `1`

| mode | cases | answer_success | answer_rate | grounding_rate | forbidden_rate | contract_success | post_check_shadow | avg_tokens | avg_latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| safe_version_replace | 1 | 0 | 0.0 | 100.0 | 0.0 | 100.0 | 100.0 | 0.0 | 26.0 |
