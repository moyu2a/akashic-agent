# 记忆系统链路量化评测报告

本报告是离线确定性评测结果，只代表当前样本集上的链路对比，不代表生产全量结论。

## 评测口径

- 链路评测按累计开关计算，每一步包含前面已经打开的能力。
- `uplift_points` 在本报告中表示相邻增益，也就是当前步骤相对上一步的分数变化。
- `total_chain_uplift_points` 表示最终步骤相对 `chain_off` 的总提升。
- 链路分数不是单项分数相加；新增能力可能补短板，也可能因为治理成本或非即时能力拉低综合分。

## 总览

- 样本规模：80 个目标导向 case，其中 common 40 个，hard 40 个。
- `case_count`: `80`
- `common_case_count`: `40`
- `hard_case_count`: `40`
- `chain_step_count`: `8`
- `baseline_main_score`: `10.0`
- `final_main_score`: `69.6017`
- `total_chain_uplift_points`: `59.6017`
- `total_chain_uplift_pct`: `596.017`

## 链路阶段增益

| step | label | main_score | 相邻增益 | total_uplift | answer | grounding | forbidden | token_signal_kind | token_signal_value |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| chain_off | 关闭记忆增强 | 10 | 0 | 0 | 0 | 0 | 0 | unavailable | unavailable |
| chain_write_value | 加入写入价值治理 | 58.3345 | 48.3345 | 48.3345 | 73.336 | 19.998 | 70.003 | unavailable | unavailable |
| chain_tri_retrieval | 加入三路召回 | 77.9171 | 19.5826 | 67.9171 | 86.668 | 57.4983 | 42.5012 | unavailable | unavailable |
| chain_graph_retrieval | 加入图谱召回 | 78.1114 | 0.1943 | 68.1114 | 91.112 | 38.3321 | 33.334 | unavailable | unavailable |
| chain_rerank_injection | 加入重排与注入治理 | 75.2312 | -2.8802 | 65.2312 | 84.1877 | 42.9993 | 23.0003 | prompt_token_delta | 5564 |
| chain_version_provenance | 加入版本链与溯源 | 73.1017 | -2.1295 | 63.1017 | 79.8762 | 44.1563 | 16.4288 | prompt_token_delta | 5564 |
| chain_sleep_consolidation | 加入睡眠巩固 | 69.6017 | -3.5 | 59.6017 | 73.0667 | 49.4626 | 14.3752 | mixed | unavailable |
| chain_all_on | 全开组合校验 | 69.6017 | 0 | 59.6017 | 73.0667 | 49.4626 | 14.3752 | mixed | unavailable |

## common / hard 链路对比

| case_set | step | main_score | 相邻增益 | answer | grounding | forbidden |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| common | chain_off | 10 | 0 | 0 | 0 | 0 |
| common | chain_write_value | 58.3345 | 48.3345 | 73.336 | 19.998 | 70.003 |
| common | chain_tri_retrieval | 77.5957 | 19.2612 | 86.668 | 57.141 | 45.0015 |
| common | chain_graph_retrieval | 77.7304 | 0.1347 | 91.112 | 38.094 | 36.6677 |
| common | chain_rerank_injection | 74.5226 | -3.2078 | 83.6448 | 42.8564 | 26.0006 |
| common | chain_version_provenance | 72.5161 | -2.0065 | 79.3892 | 44.0046 | 18.5719 |
| common | chain_sleep_consolidation | 69.067 | -3.4491 | 72.6405 | 49.2183 | 16.2504 |
| common | chain_all_on | 69.067 | 0 | 72.6405 | 49.2183 | 16.2504 |
| hard | chain_off | 10 | 0 | 0 | 0 | 0 |
| hard | chain_write_value | 58.3345 | 48.3345 | 73.336 | 19.998 | 70.003 |
| hard | chain_tri_retrieval | 78.2386 | 19.9041 | 86.668 | 57.8555 | 40.001 |
| hard | chain_graph_retrieval | 78.4924 | 0.2538 | 91.112 | 38.5703 | 30.0003 |
| hard | chain_rerank_injection | 75.9399 | -2.5525 | 84.7306 | 43.1422 | 20 |
| hard | chain_version_provenance | 73.6873 | -2.2526 | 80.3633 | 44.308 | 14.2857 |
| hard | chain_sleep_consolidation | 70.1364 | -3.5509 | 73.4929 | 49.707 | 12.5 |
| hard | chain_all_on | 70.1364 | 0 | 73.4929 | 49.707 | 12.5 |

## 结论

- 最终链路 `chain_all_on` 主分为 `69.6017`，相对关闭状态提升 `59.6017` 分。
- 相邻增益最高的步骤是 `chain_write_value`，增益为 `48.3345` 分。
- 相邻增益最低的步骤是 `chain_sleep_consolidation`，变化为 `-3.5` 分。
- 如果某一步相邻增益为负，表示它在当前评分公式下引入了治理成本或非即时能力稀释；这不是功能无效，而是提示后续要调整组合权重和 active 化策略。
