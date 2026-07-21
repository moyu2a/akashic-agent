# 记忆系统三层评分评测报告

本报告是离线确定性代理结果，只代表当前样本集上的分层对比，不代表生产全量结论。

## 评分口径

- `answer_layer_score = 0.70 * answer_rule_pass_rate + 0.20 * memory_grounding_pass_rate + 0.10 * (100 - forbidden_violation_rate)`
- `write_governance_score = 0.35 * useful_write_precision_score + 0.25 * pollution_block_score + 0.15 * duplicate_control_score + 0.15 * review_safety_score + 0.10 * write_reduction_score`
- `memory_hygiene_score = 0.25 * source_ref_health_score + 0.20 * stale_cleanup_signal_score + 0.20 * duplicate_merge_signal_score + 0.15 * conflict_resolution_signal_score + 0.10 * low_value_cleanup_signal_score + 0.10 * token_saving_score`
- `layered_total_score = 0.45 * answer_layer_score + 0.30 * write_governance_score + 0.25 * memory_hygiene_score; unavailable layers are omitted and remaining weights are normalized`
- 三层分开评估：即时回答、写入治理、记忆库卫生。
- 总分只是概览，不是生产准确率，也不是最终上线排序。

## 总览

- 样本规模：80 个目标导向 case，其中 common 40 个，hard 40 个。
- `case_count`: `80`
- `common_case_count`: `40`
- `hard_case_count`: `40`
- `layer_count`: `3`
- `baseline_total_layered_score`: `94.375`
- `final_total_layered_score`: `54.9521`
- `total_layered_uplift_points`: `-39.4229`

## 链路阶段对比

| step | label | answer_layer | write_governance | memory_hygiene | layered_total | 相邻增益 | 总增益 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_memory_base | 原始记忆基线 | 94.375 | unavailable | unavailable | 94.375 | 0 | 0 |
| chain_write_value | 加入写入价值治理 | 58.3345 | 49.3334 | unavailable | 54.7341 | -39.6409 | -39.6409 |
| chain_tri_retrieval | 加入三路召回 | 77.9171 | 49.3334 | unavailable | 66.4836 | 11.7495 | -27.8914 |
| chain_graph_retrieval | 加入图谱召回 | 77.8197 | 49.3334 | unavailable | 66.4252 | -0.0584 | -27.9498 |
| chain_rerank_injection | 加入重排与注入治理 | 75.1679 | 49.3334 | unavailable | 64.8341 | -1.5911 | -29.5409 |
| chain_version_provenance | 加入版本链与溯源 | 73.0476 | 49.3334 | unavailable | 63.5619 | -1.2722 | -30.8131 |
| chain_sleep_consolidation | 加入睡眠巩固 | 69.5542 | 49.3334 | 35.4107 | 54.9521 | -8.6098 | -39.4229 |
| chain_all_on | 全开组合校验 | 69.5542 | 49.3334 | 35.4107 | 54.9521 | 0 | -39.4229 |

## 写入治理评分

| step | useful_write_precision | pollution_block | duplicate_control | review_safety | write_reduction | score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_memory_base | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |
| chain_write_value | 73.3334 | 26.6666 | 20 | 26.6666 | 100 | 49.3334 |
| chain_tri_retrieval | 73.3334 | 26.6666 | 20 | 26.6666 | 100 | 49.3334 |
| chain_graph_retrieval | 73.3334 | 26.6666 | 20 | 26.6666 | 100 | 49.3334 |
| chain_rerank_injection | 73.3334 | 26.6666 | 20 | 26.6666 | 100 | 49.3334 |
| chain_version_provenance | 73.3334 | 26.6666 | 20 | 26.6666 | 100 | 49.3334 |
| chain_sleep_consolidation | 73.3334 | 26.6666 | 20 | 26.6666 | 100 | 49.3334 |
| chain_all_on | 73.3334 | 26.6666 | 20 | 26.6666 | 100 | 49.3334 |

## 记忆库卫生评分

| step | source_ref_health | stale_cleanup | duplicate_merge | conflict_resolution | low_value_cleanup | token_saving | score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_memory_base | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |
| chain_write_value | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |
| chain_tri_retrieval | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |
| chain_graph_retrieval | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |
| chain_rerank_injection | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |
| chain_version_provenance | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |
| chain_sleep_consolidation | 86.6072 | 13.3929 | 1.3393 | 0 | 13.3929 | 94.7321 | 35.4107 |
| chain_all_on | 86.6072 | 13.3929 | 1.3393 | 0 | 13.3929 | 94.7321 | 35.4107 |

## common / hard 对比

| case_set | step | layered_total | answer_layer | write_governance | memory_hygiene |
| --- | --- | ---: | ---: | ---: | ---: |
| common | chain_memory_base | 100 | 100 | unavailable | unavailable |
| common | chain_write_value | 54.7341 | 58.3345 | 49.3334 | unavailable |
| common | chain_tri_retrieval | 66.2907 | 77.5956 | 49.3334 | unavailable |
| common | chain_graph_retrieval | 66.3716 | 77.7304 | 49.3334 | unavailable |
| common | chain_rerank_injection | 64.4469 | 74.5226 | 49.3334 | unavailable |
| common | chain_version_provenance | 63.2431 | 72.5162 | 49.3334 | unavailable |
| common | chain_sleep_consolidation | 54.773 | 69.067 | 49.3334 | 35.5714 |
| common | chain_all_on | 54.773 | 69.067 | 49.3334 | 35.5714 |
| hard | chain_memory_base | 88.75 | 88.75 | unavailable | unavailable |
| hard | chain_write_value | 54.7341 | 58.3345 | 49.3334 | unavailable |
| hard | chain_tri_retrieval | 66.6765 | 78.2386 | 49.3334 | unavailable |
| hard | chain_graph_retrieval | 66.4788 | 77.9091 | 49.3334 | unavailable |
| hard | chain_rerank_injection | 65.2213 | 75.8132 | 49.3334 | unavailable |
| hard | chain_version_provenance | 63.8808 | 73.579 | 49.3334 | unavailable |
| hard | chain_sleep_consolidation | 55.1312 | 70.0416 | 49.3334 | 35.25 |
| hard | chain_all_on | 55.1312 | 70.0416 | 49.3334 | 35.25 |

## 结论

- 最终链路 `chain_all_on` 的三层总分为 `54.9521`。
- 相邻增益最高的步骤是 `chain_tri_retrieval`，增益为 `11.7495` 分。
- 相邻增益最低的步骤是 `chain_write_value`，变化为 `-39.6409` 分。
- 写入治理和记忆库卫生不再被单独的回答分数吞掉，但它们仍然属于离线代理指标，不是生产准确率。
