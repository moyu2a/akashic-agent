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
- `final_total_layered_score`: `54.8896`
- `total_layered_uplift_points`: `-39.4854`

## 链路阶段对比

| step | label | answer_layer | write_governance | memory_hygiene | layered_total | 相邻增益 | 总增益 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_memory_base | 原始记忆基线 | 94.375 | unavailable | unavailable | 94.375 | 0 | 0 |
| chain_write_value | 加入写入价值治理 | 56.3347 | 49.5 | unavailable | 53.6008 | -40.7742 | -40.7742 |
| chain_tri_retrieval | 加入三路召回 | 76.9172 | 49.5 | unavailable | 65.9503 | 12.3495 | -28.4247 |
| chain_graph_retrieval | 加入图谱召回 | 77.1531 | 49.5 | unavailable | 66.0919 | 0.1416 | -28.2831 |
| chain_rerank_injection | 加入重排与注入治理 | 74.7679 | 49.5 | unavailable | 64.6607 | -1.4312 | -29.7143 |
| chain_version_provenance | 加入版本链与溯源 | 72.7618 | 49.5 | unavailable | 63.4571 | -1.2036 | -30.9179 |
| chain_sleep_consolidation | 加入睡眠巩固 | 69.3043 | 49.5 | 35.4107 | 54.8896 | -8.5675 | -39.4854 |
| chain_all_on | 全开组合校验 | 69.3043 | 49.5 | 35.4107 | 54.8896 | 0 | -39.4854 |

## 写入治理评分

| step | useful_write_precision | pollution_block | duplicate_control | review_safety | write_reduction | score |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_memory_base | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |
| chain_write_value | 70 | 30 | 20 | 30 | 100 | 49.5 |
| chain_tri_retrieval | 70 | 30 | 20 | 30 | 100 | 49.5 |
| chain_graph_retrieval | 70 | 30 | 20 | 30 | 100 | 49.5 |
| chain_rerank_injection | 70 | 30 | 20 | 30 | 100 | 49.5 |
| chain_version_provenance | 70 | 30 | 20 | 30 | 100 | 49.5 |
| chain_sleep_consolidation | 70 | 30 | 20 | 30 | 100 | 49.5 |
| chain_all_on | 70 | 30 | 20 | 30 | 100 | 49.5 |

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
| common | chain_write_value | 53.6008 | 56.3347 | 49.5 | unavailable |
| common | chain_tri_retrieval | 65.7574 | 76.5957 | 49.5 | unavailable |
| common | chain_graph_retrieval | 66.0383 | 77.0638 | 49.5 | unavailable |
| common | chain_rerank_injection | 64.2736 | 74.1226 | 49.5 | unavailable |
| common | chain_version_provenance | 63.1383 | 72.2305 | 49.5 | unavailable |
| common | chain_sleep_consolidation | 54.7105 | 68.817 | 49.5 | 35.5714 |
| common | chain_all_on | 54.7105 | 68.817 | 49.5 | 35.5714 |
| hard | chain_memory_base | 88.75 | 88.75 | unavailable | unavailable |
| hard | chain_write_value | 53.6008 | 56.3347 | 49.5 | unavailable |
| hard | chain_tri_retrieval | 66.1432 | 77.2387 | 49.5 | unavailable |
| hard | chain_graph_retrieval | 66.1455 | 77.2425 | 49.5 | unavailable |
| hard | chain_rerank_injection | 65.0479 | 75.4132 | 49.5 | unavailable |
| hard | chain_version_provenance | 63.7759 | 73.2932 | 49.5 | unavailable |
| hard | chain_sleep_consolidation | 55.0687 | 69.7916 | 49.5 | 35.25 |
| hard | chain_all_on | 55.0687 | 69.7916 | 49.5 | 35.25 |

## 结论

- 最终链路 `chain_all_on` 的三层总分为 `54.8896`。
- 相邻增益最高的步骤是 `chain_tri_retrieval`，增益为 `12.3495` 分。
- 相邻增益最低的步骤是 `chain_write_value`，变化为 `-40.7742` 分。
- 写入治理和记忆库卫生不再被单独的回答分数吞掉，但它们仍然属于离线代理指标，不是生产准确率。
