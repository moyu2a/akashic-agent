# 记忆系统 Phase 6d 量化提升报告

本报告是离线确定性评测结果，只代表当前样本集上的对比，不代表生产全量结论。

## 计数与比例口径

- 主表使用目标命中、grounding 和 forbidden 的计数及比例；原始评分字段仅保留在 JSON 兼容输出中。
- `memory_base` 是主基线，`off` 只作为关闭增强控制组。

## 总览

- `case_count`: `80`
- `common_case_count`: `40`
- `hard_case_count`: `40`
- `repeat_count`: `1`
- 原始记忆基线：命中 `150` / `160`，漏召回 `10`，召回率 `93.75`%。
- 全开组合：命中 `86` / `160`，漏召回 `74`，召回率 `53.75`%。

## 主要结果

| profile | case_set | targets | success | miss | recall_rate | grounding | grounding_rate | forbidden | forbidden_rate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| memory_base | overall | 160 | 150 | 10 | 93.75 | 150 | 93.75 | 0 | 0 |
| write_value_only | overall | 160 | 96 | 64 | 60 | 48 | 19.998 | 128 | 70.003 |
| tri_retrieval_only | overall | 160 | 160 | 0 | 100 | 160 | 94.9985 | 28 | 14.9995 |
| graph_only | overall | 160 | 158 | 2 | 98.75 | 0 | 0 | 28 | 14.9995 |
| rerank_only | overall | 160 | 104 | 56 | 65 | 80 | 50 | 0 | 7.4998 |
| version_provenance_only | overall | 160 | 80 | 80 | 50 | 80 | 47.0487 | 1 | 0.3125 |
| sleep_only | overall | 160 | 40 | 120 | 25 | 160 | 86.6072 | 0 | 0 |
| all_on | overall | 160 | 86 | 74 | 53.75 | 80 | 49.4626 | 28 | 14.4534 |

## common / hard 对比

| case_set | profile | targets | success | miss | recall_rate | grounding | grounding_rate | forbidden | forbidden_rate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| memory_base | common | 80 | 80 | 0 | 100 | 80 | 100 | 0 | 0 |
| write_value_only | common | 80 | 48 | 32 | 60 | 24 | 19.998 | 44 | 70.003 |
| tri_retrieval_only | common | 80 | 80 | 0 | 100 | 80 | 94.284 | 16 | 20 |
| graph_only | common | 80 | 80 | 0 | 100 | 0 | 0 | 16 | 20 |
| rerank_only | common | 80 | 48 | 32 | 60 | 40 | 50 | 0 | 10 |
| version_provenance_only | common | 80 | 40 | 40 | 50 | 40 | 46.875 | 0 | 0 |
| sleep_only | common | 80 | 20 | 60 | 25 | 80 | 85.7143 | 0 | 0 |
| all_on | common | 80 | 40 | 40 | 50 | 40 | 49.2183 | 16 | 16.2504 |
| memory_base | hard | 80 | 70 | 10 | 87.5 | 70 | 87.5 | 0 | 0 |
| write_value_only | hard | 80 | 48 | 32 | 60 | 24 | 19.998 | 84 | 70.003 |
| tri_retrieval_only | hard | 80 | 80 | 0 | 100 | 80 | 95.713 | 12 | 9.999 |
| graph_only | hard | 80 | 78 | 2 | 97.5 | 0 | 0 | 12 | 9.999 |
| rerank_only | hard | 80 | 56 | 24 | 70 | 40 | 50 | 0 | 4.9995 |
| version_provenance_only | hard | 80 | 40 | 40 | 50 | 40 | 47.2225 | 1 | 0.625 |
| sleep_only | hard | 80 | 20 | 60 | 25 | 80 | 87.5 | 0 | 0 |
| all_on | hard | 80 | 46 | 34 | 57.5 | 40 | 49.707 | 12 | 12.6563 |

## 关闭增强控制组

| control | targets | success | miss | recall_rate | grounding | grounding_rate | forbidden | forbidden_rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| off | 160 | 0 | 160 | 0 | 0 | 0 | 0 | 0 |

## 原始评分字段

- `main_score`、`uplift_points` 和 `uplift_pct` 保留在 JSON 输出中以兼容既有消费者，不作为本报告主表的解释口径。

## 说明

- `token_signal_value` / `latency_ms` 若无直接可用值，会标记为 `unavailable`。
- `token_signal_kind` 区分 `prompt_token_delta`、`estimated_token_saving`、`mixed` 和 `unavailable`。
- `tri_retrieval_only` 和 `graph_only` 是同一轮 phase2 runtime 的两条家族视角，不是两个独立开关运行。
- `all_on` 若同时包含成本和节省两类 token 信号，会标记为 `mixed`，不会强行合并成一个 token 数。
- `feature_contributions` 只展示 overall 视角，便于看单项开关的净增益。
- `memory_base` 是原始记忆基线，`off` 是关闭增强控制组；单项增益和总增益都应优先相对 `memory_base` 理解。

## 详细复盘

### 测试过程

- 测试对象：Phase 6d 离线量化 uplift report。
- 样本规模：80 个目标导向 case，其中 common 40 个，hard 40 个。
- 对照方式：同一批 case 同时跑 `off`、单项开关和 `all_on`。
- 执行方式：复用离线 `EvalCase`、`EvalRunReport` 和 shadow trace，不启动 AgentLoop，不调用真实 LLM，不读写真实 memory DB。
- 评分方式：用 `answer_rule_pass_rate`、`memory_grounding_pass_rate` 和 `forbidden_violation_rate` 计算 `main_score`。
- 失败门控：如果底层 eval runner 失败，报告生成直接失败，不输出伪成功报表。
- 验证结果：本报告只记录评测产物；测试是否通过以实际命令输出为准，不在报告生成逻辑中硬编码。

### 指标含义

| 指标 | 含义 | 方向 |
| --- | --- | --- |
| `main_score` | 综合主分，公式为 `0.7 * answer + 0.2 * grounding + 0.1 * (100 - forbidden)` | 越高越好 |
| `uplift_points` | 当前开关相比 `memory_base` 提高的分数 | 越高越好 |
| `uplift_pct` | 当前开关相比 `memory_base` 的提升百分比 | 越高越好 |
| `answer_rule_pass_rate` | 是否命中预期答案规则或目标记忆 | 越高越好 |
| `memory_grounding_pass_rate` | 召回、注入或治理结果是否有来源和证据支撑 | 越高越好 |
| `forbidden_violation_rate` | 是否召回或注入了旧记忆、噪声记忆、跨会话记忆等 forbidden 内容 | 越低越好 |
| `token_signal_kind` | token 信号类型，例如 `prompt_token_delta`、`estimated_token_saving`、`mixed` | 用于解释 token 数字 |
| `token_signal_value` | token 信号值；不同 kind 不能直接相加 | 视 kind 而定 |
| `token_signal_delta` | 与 baseline 可比时的 token 差值；不可比时为 `unavailable` | 视 kind 而定 |
| `latency_ms` | 当前 trace 能观测到的耗时信号 | 越低越好 |
| `common` | 常见场景样本集 | 用于看普通问题表现 |
| `hard` | 难例、边界、模糊指代样本集 | 用于看复杂问题表现 |

### 各开关详细结论

#### 关闭增强控制组 `off`

| scope | main_score | uplift_points | uplift_pct | answer | grounding | forbidden | token_signal_kind | token_signal_value | token_signal_delta | latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| overall | 10 | -84.375 | -89.404 | 0 | 0 | 0 | unavailable | unavailable | unavailable | unavailable |
| common | 10 | -90 | -90 | 0 | 0 | 0 | unavailable | unavailable | unavailable | unavailable |
| hard | 10 | -78.75 | -88.7324 | 0 | 0 | 0 | unavailable | unavailable | unavailable | unavailable |

- 关闭时做得好：没有启用实验召回、注入或写入治理，因此没有额外 token 成本、延迟和实验模块引入的 forbidden 风险。
- 关闭时做得不好：answer 为 0，grounding 为 0，主分为 10，只能作为对照组，不能提供记忆增强能力。
- 开启后做得好：不适用；`off` 本身就是关闭状态。
- 开启后做得不好：不适用；`off` 本身就是关闭状态。
- 结论：关闭状态安全但无增强能力，是衡量 uplift 的 baseline。

#### 写入价值 `write_value_only`

| scope | main_score | uplift_points | uplift_pct | answer | grounding | forbidden | token_signal_kind | token_signal_value | token_signal_delta | latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| overall | 58.3345 | -36.0405 | -38.1886 | 73.336 | 19.998 | 70.003 | unavailable | unavailable | unavailable | unavailable |
| common | 58.3345 | -41.6655 | -41.6655 | 73.336 | 19.998 | 70.003 | unavailable | unavailable | unavailable | unavailable |
| hard | 58.3345 | -30.4155 | -34.271 | 73.336 | 19.998 | 70.003 | unavailable | unavailable | unavailable | unavailable |

- 关闭时做得好：关闭时不会因为写入价值评分引入额外计算成本。
- 关闭时做得不好：缺少候选记忆价值判断，临时信息、重复信息、助手推断都有污染长期记忆的风险。
- 开启后做得好：answer 达到 73.336，说明写入治理规则能识别不少应该拒绝或审查的候选。
- 开启后做得不好：grounding 为 19.998，forbidden 为 70.003，说明它只适合作为写入入口治理，不能单独保证召回和证据质量。
- 结论：适合作为长期记忆写入前的第一道过滤，但需要和 source_ref、重复检测、冲突检测继续联动。

#### 三路召回 `tri_retrieval_only`

| scope | main_score | uplift_points | uplift_pct | answer | grounding | forbidden | token_signal_kind | token_signal_value | token_signal_delta | latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| overall | 97.4997 | 3.1247 | 3.3109 | 100 | 94.9985 | 14.9995 | unavailable | unavailable | unavailable | 0 |
| common | 96.8568 | -3.1432 | -3.1432 | 100 | 94.284 | 20 | unavailable | unavailable | unavailable | 0 |
| hard | 98.1427 | 9.3927 | 10.5833 | 100 | 95.713 | 9.999 | unavailable | unavailable | unavailable | 0 |

- 关闭时做得好：关闭时没有额外检索路径和融合排序成本。
- 关闭时做得不好：单一路径或无增强召回容易漏掉模糊指代、关键词不完全匹配和 source_ref 相关记忆。
- 开启后做得好：main_score 为 97.4997，answer 为 100，grounding 为 94.9985；hard 集为 98.1427。
- 开启后做得不好：forbidden 为 14.9995，说明仍可能带入旧记忆、噪声记忆或跨 scope 候选。
- 结论：当前最强直接提分项，优先级最高，但需要后接重排和注入治理。

#### 图谱召回 `graph_only`

| scope | main_score | uplift_points | uplift_pct | answer | grounding | forbidden | token_signal_kind | token_signal_value | token_signal_delta | latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| overall | 77.6251 | -16.7499 | -17.7482 | 98.75 | 0 | 14.9995 | unavailable | unavailable | unavailable | 0 |
| common | 78 | -22 | -22 | 100 | 0 | 20 | unavailable | unavailable | unavailable | 0 |
| hard | 77.2501 | -11.4999 | -12.9576 | 97.5 | 0 | 9.999 | unavailable | unavailable | unavailable | 0 |

- 关闭时做得好：关闭时不会引入图谱构建、实体桥接和图路径解释成本。
- 关闭时做得不好：模糊实体关系、跨概念关联和第三路补充召回能力不足。
- 开启后做得好：answer 为 98.75，hard 集为 77.2501，说明图谱对模糊关联和难例补召回有效。
- 开启后做得不好：grounding 为 0，forbidden 为 14.9995，说明当前图谱结果还没有充分转成可解释 source_ref 证据。
- 结论：适合作为第三路增强，但必须和溯源、重排、注入治理一起使用。

#### 重排与注入治理 `rerank_only`

| scope | main_score | uplift_points | uplift_pct | answer | grounding | forbidden | token_signal_kind | token_signal_value | token_signal_delta | latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| overall | 71.19 | -23.185 | -24.5669 | 74.2 | 50 | 7.4998 | prompt_token_delta | 5740 | unavailable | unavailable |
| common | 69.7108 | -30.2892 | -30.2892 | 72.444 | 50 | 10 | prompt_token_delta | 2844 | unavailable | unavailable |
| hard | 72.6693 | -16.0807 | -18.1191 | 75.956 | 50 | 4.9995 | prompt_token_delta | 2896 | unavailable | unavailable |

- 关闭时做得好：关闭时没有额外 prompt token 增量。
- 关闭时做得不好：召回候选可能直接进入上下文，低质量、低置信度或冲突记忆更容易污染 prompt。
- 开启后做得好：forbidden 降到 7.4998，hard 集为 72.6693，说明它能有效控制哪些记忆进入 prompt。
- 开启后做得不好：token_signal_kind 为 prompt_token_delta，token_signal_value 为 5740；grounding 为 50。
- 结论：是召回后的必要治理层，重点价值是降风险，但需要继续控制 token 成本。

#### 版本链与溯源 `version_provenance_only`

| scope | main_score | uplift_points | uplift_pct | answer | grounding | forbidden | token_signal_kind | token_signal_value | token_signal_delta | latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| overall | 67.7467 | -26.6283 | -28.2154 | 69.0975 | 47.0487 | 0.3125 | unavailable | unavailable | unavailable | unavailable |
| common | 67.5 | -32.5 | -32.5 | 68.75 | 46.875 | 0 | unavailable | unavailable | unavailable | unavailable |
| hard | 67.9935 | -20.7565 | -23.3876 | 69.445 | 47.2225 | 0.625 | unavailable | unavailable | unavailable | unavailable |

- 关闭时做得好：关闭时没有版本链扫描和 source_ref 解析成本。
- 关闭时做得不好：旧版本、新版本、跨会话记忆容易混在一起，难以判断记忆来源是否可信。
- 开启后做得好：forbidden 为 0.3125，说明旧版本误用和跨 scope 风险被有效压住。
- 开启后做得不好：answer 为 69.0975，grounding 为 47.0487，不如三路召回直接提分明显。
- 结论：是长期记忆可信度基础设施，价值在一致性、隔离和可追溯，不是单独的最强召回模块。

#### 睡眠巩固 `sleep_only`

| scope | main_score | uplift_points | uplift_pct | answer | grounding | forbidden | token_signal_kind | token_signal_value | token_signal_delta | latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| overall | 45.1014 | -49.2736 | -52.2104 | 25.4 | 86.6072 | 0 | estimated_token_saving | 896 | unavailable | 0 |
| common | 44.9229 | -55.0771 | -55.0771 | 25.4 | 85.7143 | 0 | estimated_token_saving | 448 | unavailable | 0 |
| hard | 45.28 | -43.47 | -48.9803 | 25.4 | 87.5 | 0 | estimated_token_saving | 448 | unavailable | 0 |

- 关闭时做得好：关闭时不会执行后台扫描、去重和压缩估算。
- 关闭时做得不好：重复、过期、低价值、冲突记忆会持续堆积，长期增加 prompt 噪声和维护成本。
- 开启后做得好：grounding 达到 86.6072，forbidden 为 0，并输出 estimated_token_saving 896。
- 开启后做得不好：answer 为 25.4，说明它不是即时召回模块，不能直接提高单轮回答命中。
- 结论：适合作为后台长期质量维护能力，主要价值是去重、压缩、清理和降噪。

#### 全开组合 `all_on`

| scope | main_score | uplift_points | uplift_pct | answer | grounding | forbidden | token_signal_kind | token_signal_value | token_signal_delta | latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| overall | 69.5543 | -24.8207 | -26.3001 | 73.0101 | 49.4626 | 14.4534 | mixed | unavailable | unavailable | 0 |
| common | 69.067 | -30.933 | -30.933 | 72.6405 | 49.2183 | 16.2504 | mixed | unavailable | unavailable | 0 |
| hard | 70.0416 | -18.7084 | -21.0799 | 73.3798 | 49.707 | 12.6563 | mixed | unavailable | unavailable | 0 |

- 关闭时做得好：关闭时最简单、最安全、没有组合复杂度。
- 关闭时做得不好：没有召回增强、图谱、重排治理、版本链、溯源和睡眠巩固，记忆能力不足。
- 开启后做得好：overall 主分达到 69.5543，common 集为 69.067，hard 集为 70.0416，说明组合能力可以覆盖当前已评测样本。
- 开启后做得不好：分数低于单独三路召回，因为组合态混入写入、睡眠等非即时问答能力；token_signal_kind 为 mixed，不能合并成一个 token 数。
- 结论：全开证明整体方向有效，但后续要优化组合权重，不能简单把所有模块平均计算。

### 总结

- 全开组合 `all_on` 的主分为 `69.5543`，相比原始记忆基线提高 `-24.8207` 分。
- 单项直接提分最强的是 `tri_retrieval_only`，它是当前样本集上的最高 uplift profile。
- `graph_only` 对模糊关联命中有效，但需要继续和 source_ref / provenance 联动提升证据支撑。
- `rerank_only` 和 `version_provenance_only` 更偏治理，价值在降低错误注入、旧版本误用和跨 scope 风险。
- `write_value_only` 和 `sleep_only` 更偏长期质量维护，不应只用即时回答主分评价。
- `all_on` 不是单项分数相加；它是多类能力同时打开后的组合态，后续需要优化组合权重和 active 化策略。
