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
| `uplift_points` | 当前开关相比 `off` 提高的分数 | 越高越好 |
| `uplift_pct` | 当前开关相比 `off` 的提升百分比 | 越高越好 |
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

#### baseline `off`

| scope | main_score | uplift_points | uplift_pct | answer | grounding | forbidden | token_signal_kind | token_signal_value | token_signal_delta | latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| overall | 10 | 0 | 0 | 0 | 0 | 0 | unavailable | unavailable | unavailable | unavailable |
| common | 10 | 0 | 0 | 0 | 0 | 0 | unavailable | unavailable | unavailable | unavailable |
| hard | 10 | 0 | 0 | 0 | 0 | 0 | unavailable | unavailable | unavailable | unavailable |

- 关闭时做得好：没有启用实验召回、注入或写入治理，因此没有额外 token 成本、延迟和实验模块引入的 forbidden 风险。
- 关闭时做得不好：answer 为 0，grounding 为 0，主分为 10，只能作为对照组，不能提供记忆增强能力。
- 开启后做得好：不适用；`off` 本身就是关闭状态。
- 开启后做得不好：不适用；`off` 本身就是关闭状态。
- 结论：关闭状态安全但无增强能力，是衡量 uplift 的 baseline。

#### 写入价值 `write_value_only`

| scope | main_score | uplift_points | uplift_pct | answer | grounding | forbidden | token_signal_kind | token_signal_value | token_signal_delta | latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| overall | 58.3345 | 48.3345 | 483.345 | 73.336 | 19.998 | 70.003 | unavailable | unavailable | unavailable | unavailable |
| common | 58.3345 | 48.3345 | 483.345 | 73.336 | 19.998 | 70.003 | unavailable | unavailable | unavailable | unavailable |
| hard | 58.3345 | 48.3345 | 483.345 | 73.336 | 19.998 | 70.003 | unavailable | unavailable | unavailable | unavailable |

- 关闭时做得好：关闭时不会因为写入价值评分引入额外计算成本。
- 关闭时做得不好：缺少候选记忆价值判断，临时信息、重复信息、助手推断都有污染长期记忆的风险。
- 开启后做得好：answer 达到 73.336，说明写入治理规则能识别不少应该拒绝或审查的候选。
- 开启后做得不好：grounding 为 19.998，forbidden 为 70.003，说明它只适合作为写入入口治理，不能单独保证召回和证据质量。
- 结论：适合作为长期记忆写入前的第一道过滤，但需要和 source_ref、重复检测、冲突检测继续联动。

#### 三路召回 `tri_retrieval_only`

| scope | main_score | uplift_points | uplift_pct | answer | grounding | forbidden | token_signal_kind | token_signal_value | token_signal_delta | latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| overall | 97.4997 | 87.4997 | 874.997 | 100 | 94.9985 | 14.9995 | unavailable | unavailable | unavailable | 0 |
| common | 96.8568 | 86.8568 | 868.568 | 100 | 94.284 | 20 | unavailable | unavailable | unavailable | 0 |
| hard | 98.1427 | 88.1427 | 881.427 | 100 | 95.713 | 9.999 | unavailable | unavailable | unavailable | 0 |

- 关闭时做得好：关闭时没有额外检索路径和融合排序成本。
- 关闭时做得不好：单一路径或无增强召回容易漏掉模糊指代、关键词不完全匹配和 source_ref 相关记忆。
- 开启后做得好：main_score 为 97.4997，answer 为 100，grounding 为 94.9985；hard 集为 98.1427。
- 开启后做得不好：forbidden 为 14.9995，说明仍可能带入旧记忆、噪声记忆或跨 scope 候选。
- 结论：当前最强直接提分项，优先级最高，但需要后接重排和注入治理。

#### 图谱召回 `graph_only`

| scope | main_score | uplift_points | uplift_pct | answer | grounding | forbidden | token_signal_kind | token_signal_value | token_signal_delta | latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| overall | 78.5001 | 68.5001 | 685.001 | 100 | 0 | 14.9995 | unavailable | unavailable | unavailable | 0 |
| common | 78 | 68 | 680 | 100 | 0 | 20 | unavailable | unavailable | unavailable | 0 |
| hard | 79.0001 | 69.0001 | 690.001 | 100 | 0 | 9.999 | unavailable | unavailable | unavailable | 0 |

- 关闭时做得好：关闭时不会引入图谱构建、实体桥接和图路径解释成本。
- 关闭时做得不好：模糊实体关系、跨概念关联和第三路补充召回能力不足。
- 开启后做得好：answer 为 100，hard 集为 79.0001，说明图谱对模糊关联和难例补召回有效。
- 开启后做得不好：grounding 为 0，forbidden 为 14.9995，说明当前图谱结果还没有充分转成可解释 source_ref 证据。
- 结论：适合作为第三路增强，但必须和溯源、重排、注入治理一起使用。

#### 重排与注入治理 `rerank_only`

| scope | main_score | uplift_points | uplift_pct | answer | grounding | forbidden | token_signal_kind | token_signal_value | token_signal_delta | latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| overall | 70.9109 | 60.9109 | 609.109 | 73.8013 | 50 | 7.4998 | prompt_token_delta | 5564 | unavailable | unavailable |
| common | 69.7108 | 59.7108 | 597.108 | 72.444 | 50 | 10 | prompt_token_delta | 2844 | unavailable | unavailable |
| hard | 72.111 | 62.111 | 621.11 | 75.1585 | 50 | 4.9995 | prompt_token_delta | 2720 | unavailable | unavailable |

- 关闭时做得好：关闭时没有额外 prompt token 增量。
- 关闭时做得不好：召回候选可能直接进入上下文，低质量、低置信度或冲突记忆更容易污染 prompt。
- 开启后做得好：forbidden 降到 7.4998，hard 集为 72.111，说明它能有效控制哪些记忆进入 prompt。
- 开启后做得不好：token_signal_kind 为 prompt_token_delta，token_signal_value 为 5564；grounding 为 50。
- 结论：是召回后的必要治理层，重点价值是降风险，但需要继续控制 token 成本。

#### 版本链与溯源 `version_provenance_only`

| scope | main_score | uplift_points | uplift_pct | answer | grounding | forbidden | token_signal_kind | token_signal_value | token_signal_delta | latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| overall | 67.778 | 57.778 | 577.78 | 69.0975 | 47.0487 | 0 | unavailable | unavailable | unavailable | unavailable |
| common | 67.5 | 57.5 | 575 | 68.75 | 46.875 | 0 | unavailable | unavailable | unavailable | unavailable |
| hard | 68.056 | 58.056 | 580.56 | 69.445 | 47.2225 | 0 | unavailable | unavailable | unavailable | unavailable |

- 关闭时做得好：关闭时没有版本链扫描和 source_ref 解析成本。
- 关闭时做得不好：旧版本、新版本、跨会话记忆容易混在一起，难以判断记忆来源是否可信。
- 开启后做得好：forbidden 为 0，说明旧版本误用和跨 scope 风险被有效压住。
- 开启后做得不好：answer 为 69.0975，grounding 为 47.0487，不如三路召回直接提分明显。
- 结论：是长期记忆可信度基础设施，价值在一致性、隔离和可追溯，不是单独的最强召回模块。

#### 睡眠巩固 `sleep_only`

| scope | main_score | uplift_points | uplift_pct | answer | grounding | forbidden | token_signal_kind | token_signal_value | token_signal_delta | latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| overall | 45.1014 | 35.1014 | 351.014 | 25.4 | 86.6072 | 0 | estimated_token_saving | 896 | unavailable | 0 |
| common | 44.9229 | 34.9229 | 349.229 | 25.4 | 85.7143 | 0 | estimated_token_saving | 448 | unavailable | 0 |
| hard | 45.28 | 35.28 | 352.8 | 25.4 | 87.5 | 0 | estimated_token_saving | 448 | unavailable | 0 |

- 关闭时做得好：关闭时不会执行后台扫描、去重和压缩估算。
- 关闭时做得不好：重复、过期、低价值、冲突记忆会持续堆积，长期增加 prompt 噪声和维护成本。
- 开启后做得好：grounding 达到 86.6072，forbidden 为 0，并输出 estimated_token_saving 896。
- 开启后做得不好：answer 为 25.4，说明它不是即时召回模块，不能直接提高单轮回答命中。
- 结论：适合作为后台长期质量维护能力，主要价值是去重、压缩、清理和降噪。

#### 全开组合 `all_on`

| scope | main_score | uplift_points | uplift_pct | answer | grounding | forbidden | token_signal_kind | token_signal_value | token_signal_delta | latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| overall | 69.6017 | 59.6017 | 596.017 | 73.0667 | 49.4626 | 14.3752 | mixed | unavailable | unavailable | 0 |
| common | 69.067 | 59.067 | 590.67 | 72.6405 | 49.2183 | 16.2504 | mixed | unavailable | unavailable | 0 |
| hard | 70.1364 | 60.1364 | 601.364 | 73.4929 | 49.707 | 12.5 | mixed | unavailable | unavailable | 0 |

- 关闭时做得好：关闭时最简单、最安全、没有组合复杂度。
- 关闭时做得不好：没有召回增强、图谱、重排治理、版本链、溯源和睡眠巩固，记忆能力不足。
- 开启后做得好：overall 主分达到 69.6017，common 集为 69.067，hard 集为 70.1364，说明组合能力可以覆盖当前已评测样本。
- 开启后做得不好：分数低于单独三路召回，因为组合态混入写入、睡眠等非即时问答能力；token_signal_kind 为 mixed，不能合并成一个 token 数。
- 结论：全开证明整体方向有效，但后续要优化组合权重，不能简单把所有模块平均计算。

### 总结

- 全开组合 `all_on` 的主分为 `69.6017`，相比 `off` 提高 `59.6017` 分。
- 单项直接提分最强的是 `tri_retrieval_only`，它是当前样本集上的最高 uplift profile。
- `graph_only` 对模糊关联命中有效，但需要继续和 source_ref / provenance 联动提升证据支撑。
- `rerank_only` 和 `version_provenance_only` 更偏治理，价值在降低错误注入、旧版本误用和跨 scope 风险。
- `write_value_only` 和 `sleep_only` 更偏长期质量维护，不应只用即时回答主分评价。
- `all_on` 不是单项分数相加；它是多类能力同时打开后的组合态，后续需要优化组合权重和 active 化策略。
