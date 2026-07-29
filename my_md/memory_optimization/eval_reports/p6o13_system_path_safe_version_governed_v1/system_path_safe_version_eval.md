# P6o-13 System Path Safe Version Governed

本报告使用 system-path fake/provider validation；不包含原始 query、prompt、memory summary 或完整回答。

- evaluation_level: `system_path_safe_version_governed`
- unique_case_count: `40`
- case_count: `120`
- replacement_seeded_count: `120`

| mode | case_count | contract_success | post_check_shadow |
| --- | ---: | ---: | ---: |
| current | 40 | 0.0 | 0.0 |
| safe_version_shadow | 40 | 100.0 | 100.0 |
| safe_version_replace | 40 | 100.0 | 100.0 |
