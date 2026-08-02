# System Path Safe Version Governed

本报告使用 system-path provider validation；不包含原始 query、prompt、memory summary 或完整回答。

- evaluation_level: `system_path_safe_version_governed`
- real_llm_enabled: `True`
- unique_case_count: `80`
- case_count: `240`
- replacement_seeded_count: `243`

| mode | cases | answer_success | answer_rate | grounding_rate | forbidden_rate | contract_success | post_check_shadow | avg_tokens | avg_latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| safe_version_replace | 80 | 71 | 88.75 | 100.0 | 0.0 | 100.0 | 100.0 | 5795.475 | 5789.9625 |
| safe_version_replace_guided | 80 | 74 | 92.5 | 100.0 | 0.0 | 100.0 | 100.0 | 5823.475 | 5352.9625 |
| safe_version_replace_guided_with_retry_shadow | 80 | 80 | 100.0 | 100.0 | 0.0 | 100.0 | 100.0 | 6040.1625 | 4703.575 |
