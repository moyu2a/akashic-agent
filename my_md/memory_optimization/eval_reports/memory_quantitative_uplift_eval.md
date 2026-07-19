# 记忆系统 Phase 6d 量化提升报告

本报告是离线确定性评测结果，只代表当前样本集上的对比，不代表生产全量结论。

## 评分公式

- `main_score = 0.7 * answer_rule_pass_rate + 0.2 * memory_grounding_pass_rate + 0.1 * (100 - forbidden_violation_rate)`

## 总览

- `case_count`: `80`
- `common_case_count`: `40`
- `hard_case_count`: `40`
- `repeat_count`: `1`
- `baseline_main_score`: `10.0`
- `all_on_main_score`: `69.6017`
- `total_uplift_points`: `59.6017`
- `total_uplift_pct`: `596.017`

## 单项提升

| profile | case_set | main_score | uplift_points | uplift_pct | answer | grounding | forbidden | token_signal_kind | token_signal_value | token_signal_delta | latency_ms | latency_delta_ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| write_value_only | overall | 58.3345 | 48.3345 | 483.345 | 73.336 | 19.998 | 70.003 | unavailable | unavailable | unavailable | unavailable | unavailable |
| tri_retrieval_only | overall | 97.4997 | 87.4997 | 874.997 | 100 | 94.9985 | 14.9995 | unavailable | unavailable | unavailable | 0 | unavailable |
| graph_only | overall | 78.5001 | 68.5001 | 685.001 | 100 | 0 | 14.9995 | unavailable | unavailable | unavailable | 0 | unavailable |
| rerank_only | overall | 70.9109 | 60.9109 | 609.109 | 73.8013 | 50 | 7.4998 | prompt_token_delta | 5564 | unavailable | unavailable | unavailable |
| version_provenance_only | overall | 67.778 | 57.778 | 577.78 | 69.0975 | 47.0487 | 0 | unavailable | unavailable | unavailable | unavailable | unavailable |
| sleep_only | overall | 45.1014 | 35.1014 | 351.014 | 25.4 | 86.6072 | 0 | estimated_token_saving | 896 | unavailable | 0 | unavailable |
| all_on | overall | 69.6017 | 59.6017 | 596.017 | 73.0667 | 49.4626 | 14.3752 | mixed | unavailable | unavailable | 0 | unavailable |

## common / hard 对比

| case_set | profile | main_score | uplift_points | answer | grounding | forbidden | token_signal_kind | token_signal_value | token_signal_delta | latency_delta_ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| common | write_value_only | 58.3345 | 48.3345 | 73.336 | 19.998 | 70.003 | unavailable | unavailable | unavailable | unavailable |
| common | tri_retrieval_only | 96.8568 | 86.8568 | 100 | 94.284 | 20 | unavailable | unavailable | unavailable | unavailable |
| common | graph_only | 78 | 68 | 100 | 0 | 20 | unavailable | unavailable | unavailable | unavailable |
| common | rerank_only | 69.7108 | 59.7108 | 72.444 | 50 | 10 | prompt_token_delta | 2844 | unavailable | unavailable |
| common | version_provenance_only | 67.5 | 57.5 | 68.75 | 46.875 | 0 | unavailable | unavailable | unavailable | unavailable |
| common | sleep_only | 44.9229 | 34.9229 | 25.4 | 85.7143 | 0 | estimated_token_saving | 448 | unavailable | unavailable |
| common | all_on | 69.067 | 59.067 | 72.6405 | 49.2183 | 16.2504 | mixed | unavailable | unavailable | unavailable |
| hard | write_value_only | 58.3345 | 48.3345 | 73.336 | 19.998 | 70.003 | unavailable | unavailable | unavailable | unavailable |
| hard | tri_retrieval_only | 98.1427 | 88.1427 | 100 | 95.713 | 9.999 | unavailable | unavailable | unavailable | unavailable |
| hard | graph_only | 79.0001 | 69.0001 | 100 | 0 | 9.999 | unavailable | unavailable | unavailable | unavailable |
| hard | rerank_only | 72.111 | 62.111 | 75.1585 | 50 | 4.9995 | prompt_token_delta | 2720 | unavailable | unavailable |
| hard | version_provenance_only | 68.056 | 58.056 | 69.445 | 47.2225 | 0 | unavailable | unavailable | unavailable | unavailable |
| hard | sleep_only | 45.28 | 35.28 | 25.4 | 87.5 | 0 | estimated_token_saving | 448 | unavailable | unavailable |
| hard | all_on | 70.1364 | 60.1364 | 73.4929 | 49.707 | 12.5 | mixed | unavailable | unavailable | unavailable |

## 原始指标

- `baseline_main_score`: `10.0`
- `case_count`: `80`
- `case_record_count`: `640`
- `common_baseline_main_score`: `10.0`
- `common_case_count`: `40`
- `common_main_score`: `69.067`
- `feature_count`: `8`
- `hard_baseline_main_score`: `10.0`
- `hard_case_count`: `40`
- `hard_main_score`: `70.1364`
- `measurement_mode`: `offline_trace_quantitative_uplift`
- `overall_answer_rule_pass_rate`: `73.0667`
- `overall_forbidden_violation_rate`: `14.3752`
- `overall_main_score`: `69.6017`
- `overall_memory_grounding_pass_rate`: `49.4626`
- `profile_count`: `8`
- `profile_summary_count`: `24`
- `repeat_count`: `1`
- `score_formula`: `main_score = 0.7 * answer_rule_pass_rate + 0.2 * memory_grounding_pass_rate + 0.1 * (100 - forbidden_violation_rate)`
- `total_uplift_pct`: `596.017`
- `total_uplift_points`: `59.6017`
- `unavailable_count`: `560`

## 说明

- `token_signal_value` / `latency_ms` 若无直接可用值，会标记为 `unavailable`。
- `token_signal_kind` 区分 `prompt_token_delta`、`estimated_token_saving`、`mixed` 和 `unavailable`。
- `tri_retrieval_only` 和 `graph_only` 是同一轮 phase2 runtime 的两条家族视角，不是两个独立开关运行。
- `all_on` 若同时包含成本和节省两类 token 信号，会标记为 `mixed`，不会强行合并成一个 token 数。
- `feature_contributions` 只展示 overall 视角，便于看单项开关的净增益。
- `off` 作为 baseline，只用于对比，不应单独解读为生产结论。