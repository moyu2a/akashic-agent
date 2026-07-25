# 记忆系统链路量化评测报告

本报告是离线确定性评测结果，只代表当前样本集上的链路对比，不代表生产全量结论。

## 评测口径

- 链路评测按累计开关计算，每一步包含前面已经打开的能力。
- 主表使用目标命中、grounding 和 forbidden 的计数及比例；原始评分字段仅保留在 JSON 兼容输出中。
- `chain_memory_base` 是主基线，`chain_off` 只作为关闭增强控制组。
- 链路不是单项分数相加；后一步会继承前一步的上下文、治理成本和候选变化。

## 总览

- 样本规模：80 个目标导向 case，其中 common 40 个，hard 40 个。
- `case_count`: `80`
- `common_case_count`: `40`
- `hard_case_count`: `40`
- `chain_step_count`: `8`
- 原始记忆基线：命中 `150` / `160`，漏召回 `10`，召回率 `93.75`%。
- 全开组合：命中 `86` / `160`，漏召回 `74`，召回率 `53.75`%。

## 链路主要结果

| step | label | targets | success | miss | recall_rate | grounding | grounding_rate | forbidden | forbidden_rate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_memory_base | 原始记忆基线 | 160 | 150 | 10 | 93.75 | 150 | 93.75 | 0 | 0 |
| chain_write_value | 加入写入价值治理 | 160 | 96 | 64 | 60 | 48 | 19.998 | 128 | 70.003 |
| chain_tri_retrieval | 加入三路召回 | 160 | 160 | 0 | 100 | 80 | 57.4983 | 96 | 42.5012 |
| chain_graph_retrieval | 加入图谱召回 | 160 | 158 | 2 | 98.75 | 80 | 38.3321 | 60 | 33.334 |
| chain_rerank_injection | 加入重排与注入治理 | 160 | 160 | 0 | 100 | 80 | 42.9993 | 32 | 23.0003 |
| chain_version_provenance | 加入版本链与溯源 | 160 | 160 | 0 | 100 | 80 | 44.1563 | 29 | 16.5181 |
| chain_sleep_consolidation | 加入睡眠巩固 | 160 | 86 | 74 | 53.75 | 80 | 49.4626 | 28 | 14.4534 |
| chain_all_on | 全开组合校验 | 160 | 86 | 74 | 53.75 | 80 | 49.4626 | 28 | 14.4534 |

## common / hard 对比

| case_set | step | targets | success | miss | recall_rate | grounding | grounding_rate | forbidden | forbidden_rate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| common | chain_memory_base | 80 | 80 | 0 | 100 | 80 | 100 | 0 | 0 |
| common | chain_write_value | 80 | 48 | 32 | 60 | 24 | 19.998 | 44 | 70.003 |
| common | chain_tri_retrieval | 80 | 80 | 0 | 100 | 40 | 57.141 | 40 | 45.0015 |
| common | chain_graph_retrieval | 80 | 80 | 0 | 100 | 40 | 38.094 | 20 | 36.6677 |
| common | chain_rerank_injection | 80 | 80 | 0 | 100 | 40 | 42.8564 | 16 | 26.0006 |
| common | chain_version_provenance | 80 | 80 | 0 | 100 | 40 | 44.0046 | 16 | 18.5719 |
| common | chain_sleep_consolidation | 80 | 40 | 40 | 50 | 40 | 49.2183 | 16 | 16.2504 |
| common | chain_all_on | 80 | 40 | 40 | 50 | 40 | 49.2183 | 16 | 16.2504 |
| hard | chain_memory_base | 80 | 70 | 10 | 87.5 | 70 | 87.5 | 0 | 0 |
| hard | chain_write_value | 80 | 48 | 32 | 60 | 24 | 19.998 | 84 | 70.003 |
| hard | chain_tri_retrieval | 80 | 80 | 0 | 100 | 40 | 57.8555 | 56 | 40.001 |
| hard | chain_graph_retrieval | 80 | 78 | 2 | 97.5 | 40 | 38.5703 | 40 | 30.0003 |
| hard | chain_rerank_injection | 80 | 80 | 0 | 100 | 40 | 43.1422 | 16 | 20 |
| hard | chain_version_provenance | 80 | 80 | 0 | 100 | 40 | 44.308 | 13 | 14.4643 |
| hard | chain_sleep_consolidation | 80 | 46 | 34 | 57.5 | 40 | 49.707 | 12 | 12.6563 |
| hard | chain_all_on | 80 | 46 | 34 | 57.5 | 40 | 49.707 | 12 | 12.6563 |

## 关闭增强控制组

| control | targets | success | miss | recall_rate | grounding | grounding_rate | forbidden | forbidden_rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_off | 160 | 0 | 160 | 0 | 0 | 0 | 0 | 0 |
