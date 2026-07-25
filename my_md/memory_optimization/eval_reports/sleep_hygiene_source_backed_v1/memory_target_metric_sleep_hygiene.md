# 记忆系统目标指标百分比评测报告

本报告是离线确定性代理结果，用于把 memory 模块效果拆成可解释百分比；它不是生产准确率。

## 总览

- `case_count`: `8`
- `common_case_count`: `8`
- `hard_case_count`: `0`
- `measurement_mode`: `offline_trace_real_baseline_plus_online_checkpoint_target_metrics`
- `online_status`: `available`
- `online_row_count`: `1`

## 离线真实 before/after

离线层的 `before` 来自同一轮 trace 的 baseline 字段，不再固定写成 0。它是可复现代理指标，不是生产准确率。

## 线上真实 LLM / checkpoint before/after

线上层来自真实 AgentLoop/checkpoint 或显式 evidence JSON；如果没有输入，报告会标记为 gated/unavailable，不会复用离线数值。

## 召回与回答增益表

| measurement_layer | measurement_source | checkpoint_source | 模块 | case 数 | 目标召回率 before | 目标召回率 after | 提升百分点 | 相对提升 | 回答命中率 after | 证据命中率 after | 错误召回率 after | 错误注入率 after |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| offline_trace | eval_runner_trace | none | 三路召回 | 8 | 100 | 100 | 0 | 0 | 100 | 92.855 | 25 | unavailable |
| offline_trace | eval_runner_trace | none | 图谱召回 | 8 | 100 | 100 | 0 | 0 | 100 | unavailable | 25 | unavailable |
| offline_trace | eval_runner_trace | none | 重排与注入治理 | 8 | 100 | 100 | 0 | 0 | 100 | unavailable | 0 | 0 |
| offline_trace | eval_runner_trace | none | 版本链与溯源 | 8 | 100 | 100 | 0 | 0 | 100 | 93.75 | 0 | unavailable |

## 写入治理增益表

| measurement_layer | measurement_source | checkpoint_source | 模块 | candidate 数 | 有效写入精度 before | 有效写入精度 after | 污染拦截率 before | 污染拦截率 after | 重复控制率 after | 写入减少率 after | 误拒率 after |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| offline_trace | eval_runner_trace | none | 写入价值治理 | 24 | 0 | unavailable | unavailable | 100 | 79.1667 | 100 | 0 |

## 记忆库卫生增益表

| measurement_layer | measurement_source | checkpoint_source | 模块 | scanned 数 | 重复合并率 after | 过期清理率 after | 低价值清理率 after | source_ref 覆盖率 after | 回源成功率 after | token 节省率 after | 巩固后召回保持率 after |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| offline_trace | eval_runner_trace | none | 睡眠巩固 | 56 | 12.5 | 14.2857 | 14.2857 | 85.7143 | 100 | 35.7137 | 100 |
| online_evidence | memory_hygiene_evidence_json | sleep_hygiene_source_backed_fixture | 睡眠巩固 | 200 | 100 | 100 | 100 | 81.5 | 36.1963 | 40.5157 | 100 |

## 在线证据行

| group | measurement_source | checkpoint_source | measurement_layer | 主要结果 |
| --- | --- | --- | --- | --- |
| 记忆库卫生 | memory_hygiene_evidence_json | sleep_hygiene_source_backed_fixture | online_evidence | source_ref 覆盖率 after 81.5; token 节省率 after 40.5157 |

## 版本链专项指标

| measurement_layer | measurement_source | checkpoint_source | case_set | case 数 | current_version_recall_rate before | current_version_recall_rate after | stale_version_misuse_rate before | stale_version_misuse_rate after | conflict_chain_detection_rate after |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| offline_trace | eval_runner_trace | none | overall | 8 | 100 | 100 | 0 | 0 | unavailable |

## common / hard 明细

| group | case_set | 模块 | 主指标 before | 主指标 after | 提升百分点 | 相对提升 |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| 召回与回答 | common | 三路召回 | 100 | 100 | 0 | 0 |
| 召回与回答 | common | 图谱召回 | 100 | 100 | 0 | 0 |
| 召回与回答 | common | 重排与注入治理 | 100 | 100 | 0 | 0 |
| 召回与回答 | common | 版本链与溯源 | 100 | 100 | 0 | 0 |
| 写入治理 | common | 写入价值治理 | unavailable | 100 | unavailable | unavailable |
| 记忆库卫生 | common | 睡眠巩固 | 0 | 35.7137 | 35.7137 | unavailable |

## 说明

- `提升百分点` 是 after - before。
- `相对提升` 只有 before 是有效且非零数值时才计算。
- 写入治理和记忆库卫生的指标来自 shadow trace，是离线代理指标。
- 真实 LLM 报告应复用 Phase 6e checkpoint，避免仅为换展示口径重复调用 provider。
