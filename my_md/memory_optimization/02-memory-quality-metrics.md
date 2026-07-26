# Memory Quality Metrics

## 目标

这份文档回答一个问题：参考图片中“长时记忆中间件”提到的记忆准确率、冗余下降、召回质量、压缩率等数据，当前项目哪些能测，哪些需要新增埋点，哪些必须先有评测集。

## 数据来源

当前项目已有几个主要数据源：

- `workspace/memory/memory2.db`
  - `memory_items`
  - `consolidation_events`
  - `memory_replacements`
- `workspace/observe/observe.db`
  - `turns`
  - `rag_queries`
  - `memory_writes`
- `workspace/sessions.db`
  - `messages`
  - `sessions`
- markdown memory 文件
  - `MEMORY.md`
  - `PENDING.md`
  - `HISTORY.md`
  - `RECENT_CONTEXT.md`

## 现在就能测的指标

### 1. 记忆规模

来源：`memory2.memory_items`

可测：

- 总记忆数。
- active 记忆数。
- superseded 记忆数。
- 按 `memory_type` 分布。
- 带 embedding 的记忆比例。
- 按 scope 分布。

示例：

```sql
SELECT status, memory_type, COUNT(*) AS total
FROM memory_items
GROUP BY status, memory_type;
```

### 2. 写入和强化比例

来源：

- `memory_items.reinforcement`
- `observe.memory_writes.item_id`

可测：

- 新写入数量。
- reinforced 数量。
- reinforcement 分布。
- 每天写入多少条。
- 每个 session 写入多少条。

意义：

- reinforced 比例高，说明去重/合并路径在生效。
- new 比例过高，可能说明记忆过度碎片化。

### 3. 纠错和失效比例

来源：

- `memory_items.status`
- `memory_replacements`
- `observe.memory_writes.superseded_ids`

可测：

- superseded 总量。
- superseded / active 比例。
- 每类记忆的 superseded 比例。
- 记忆替换链数量。

意义：

- 可以观察哪些类型的记忆更容易被纠错。
- 如果 superseded 比例异常高，说明写入质量可能有问题。

### 4. source_ref 覆盖率

来源：`memory_items.source_ref`

可测：

- 有 source_ref 的记忆比例。
- 无 source_ref 的记忆比例。
- 各 memory_type 的 source_ref 覆盖率。
- message-level 覆盖率：`source_ref` 能精确到消息 ID 的比例。
- source_ref 解析成功率：来源字段能被 parser 正确识别的比例。
- 真实回源成功率：通过 `SessionStore.fetch_by_ids()` 能找到原始消息的比例。
- 原文支持率：原始消息能支持当前记忆摘要的比例。
- source-backed eligible 率：同时满足真实回源成功和原文支持摘要的比例。

意义：

- source_ref 覆盖率越高，历史问题和纠错时越容易回源。
- 无 source_ref 记忆应当更谨慎注入。
- message-level 覆盖率比普通覆盖率更重要；session 级来源只能定位到会话阶段，消息级来源才能恢复原文。
- source-backed eligible 是后续睡眠巩固、安全清理、审计恢复的核心门槛。

当前 Phase 6u 测试集结果：

| 指标 | before | after | 变化 |
| --- | ---: | ---: | ---: |
| message-level 覆盖率 | 40.0% | 90.0% | +50.0 个百分点 |
| source_ref 解析成功率 | 80.0% | 100.0% | +20.0 个百分点 |
| 真实回源成功率 | 20.0% | 80.0% | +60.0 个百分点 |
| 原文支持率 | 10.0% | 70.0% | +60.0 个百分点 |
| source-backed eligible 率 | 10.0% | 70.0% | +60.0 个百分点 |

这组数据来自 `200` 条目标导向 synthetic fixture，不是生产自然流量。它证明的是：在覆盖 session 级来源、缺失来源、malformed 来源、跨会话来源、非法消息 ID、缺失消息、多消息来源和原文不支持等场景时，消息级 source_ref 治理能显著提升可回源、可审计比例，同时保留应阻断的 hard case。

### 5. scope 覆盖率

来源：`memory_items.extra_json`

可测：

- 带 `scope_channel` 的比例。
- 带 `scope_chat_id` 的比例。
- 每个 channel 的记忆数量。

意义：

- 判断记忆是否能做到会话隔离。
- 判断哪些记忆是全局稳定偏好，哪些是会话局部状态。

### 6. 检索和注入数量

来源：`observe.rag_queries`

可测：

- 每轮检索次数。
- 每轮 hit 数。
- `injected_count` 分布。
- `RETRIEVE` / `NO_RETRIEVE` 比例。
- 检索错误率。

意义：

- injected_count 过高可能污染 prompt。
- `NO_RETRIEVE` 比例能反映检索 gate 是否过于保守或过于激进。

### 7. 召回分数分布

来源：`rag_queries.hits_json`

可测：

- hit score 分布。
- injected hit 的最低分。
- 不同 memory_type 的 score 分布。
- 低置信标签比例。

意义：

- 观察 score 阈值是否合适。
- 识别大量低分注入的问题。

### 8. prompt 成本

来源：`observe.turns`

可测：

- `prompt_tokens`
- `next_turn_baseline_tokens`
- `react_input_sum_tokens`
- `react_input_peak_tokens`
- `react_cache_prompt_tokens`
- `react_cache_hit_tokens`

意义：

- 判断记忆注入是否推高 prompt 成本。
- 判断 `MEMORY.md` 低频更新是否保护了缓存命中。

## 加少量埋点后可以测的指标

### 1. consolidation 压缩率

需要新增记录：

- consolidation 输入消息 token。
- history_entries token。
- pending_items token。
- 更新后的 `MEMORY.md` 增量 token。

可测：

```text
压缩率 = 输出记忆 token / 输入对话 token
```

### 2. 检索延迟

需要新增记录：

- query rewrite 耗时。
- embedding 耗时。
- vector search 耗时。
- keyword search 耗时。
- rerank 耗时。
- 总 retrieval 耗时。

### 3. 写入门控通过率

需要新增 `MemoryWritePolicy` trace：

- 候选记忆数量。
- 通过数量。
- 拒绝数量。
- 拒绝原因。

拒绝原因可以包括：

- 临时信息。
- assistant 建议。
- 重复。
- 低价值。
- 冲突候选。
- 无 source_ref。

### 4. 召回后使用率

现在系统能知道“召回了、注入了”，但不能稳定知道模型是否真的使用了。

可以新增：

- 回答中引用的 memory id。
- 输出后引用检测。
- 使用过的 memory id 反向强化。

可测：

- 注入后被使用比例。
- 注入但未使用比例。
- 被使用记忆的平均 score。

Phase 6b-4 已经补上第一版答案级证据使用调试：

- `memory_grounding_pass_count`：期望 memory id 是否进入受控 memory engine 的使用记录。
- `answer_rule_pass_count`：最终回答是否命中答案规则。
- `repeat_count`：同一批 case 的重复轮数。
- `repeat_pass_rate`：重复评测整体通过率。
- `repeat_answer_rule_pass_rate`：重复评测中答案规则通过率。
- `repeat_memory_grounding_pass_rate`：重复评测中记忆 grounding 通过率。
- `prompt_variant_mode`：当前是 `baseline`、`coached` 还是 `both`。
- `pass_count_by_prompt_variant`：按提示词变体拆分的整体通过数。
- `answer_rule_pass_count_by_prompt_variant`：按提示词变体拆分的答案规则通过数。
- `memory_grounding_pass_count_by_prompt_variant`：按提示词变体拆分的记忆 grounding 通过数。

这些指标用于判断“记忆已经给到模型”之后，模型是否稳定使用了关键证据。完整回答和证据块只在显式开启 `--include-answer-debug` 时写入临时 workspace，不进入常规报告。

### Phase 6c-1 已建立的离线 uplift proxy report

Phase 6c-1 不是答案质量评测，而是把现有 shadow trace 转成统一的对照指标。它输出：

- `overall_avg_uplift`
- `avg_baseline_score`
- `avg_experimental_score`
- `avg_uplift`
- `positive_signal_count`
- `negative_signal_count`
- `total_token_delta`
- `estimated_token_saving`

### Phase 6d 的量化总表

Phase 6d 把前面的 trace 指标再收敛成一张可背诵的总表，主指标继续沿用同一公式：

```text
main_score = 0.7 * answer_rule_pass_rate
           + 0.2 * memory_grounding_pass_rate
           + 0.1 * (100 - forbidden_violation_rate)
```

这张表的作用不是替代前面的细分指标，而是回答更直接的问题：

- 单开某个功能，主分能涨多少。
- 全开以后，主分比 baseline 高多少。
- common 和 hard 两套样本各自表现怎样。

本轮实际结果：

- `case_count = 80`
- `common_case_count = 40`
- `hard_case_count = 40`
- `baseline_main_score = 94.375`
- `all_on_main_score = 69.3043`
- `total_uplift_points = -25.0707`
- `total_uplift_pct = 596.017`

单项 uplift：

- `tri_retrieval_only = 87.4997`
- `graph_only = 68.5001`
- `rerank_only = 60.9109`
- `version_provenance_only = 57.778`
- `write_value_only = 48.3345`
- `sleep_only = 35.1014`

这里的 token 相关字段改为 `token_signal_kind`、`token_signal_value` 和 `token_signal_delta`。`token_signal_kind` 会说明该值来自 `prompt_token_delta` 还是 `estimated_token_saving`；如果组合态同时包含成本和节省两类信号，就标记为 `mixed`，`token_signal_value` 和 `token_signal_delta` 不硬拼成一个总数。`latency_ms` 只汇总真正以毫秒计量的 trace 信号，比如 retrieval 和 sleep 的耗时；基线不可比时，delta 直接标成 `unavailable`。

本轮还修正了溯源治理分的口径：`provenance_shadow` 的 forbidden rate 只看实际观测到的 `cross_scope_risk_count`，不会因为样本里存在跨 scope 记忆就直接罚成 100%。

`tri_retrieval_only` 和 `graph_only` 仍然来自同一轮 phase2 runtime 的不同家族视角，读数是为了比较两条检索路径的贡献，不要把它们理解成两个独立启动的 profile。

报表文件：

- `my_md/memory_optimization/eval_reports/memory_quantitative_uplift_eval.json`
- `my_md/memory_optimization/eval_reports/memory_quantitative_uplift_eval.md`
- `my_md/memory_optimization/eval_reports/memory_quantitative_chain_eval.json`
- `my_md/memory_optimization/eval_reports/memory_quantitative_chain_eval.md`
- `metric_kind`
- `metric_name`

其中 `memory_quantitative_uplift_eval.md` 已补充“详细复盘”章节，记录测试过程、每个指标的含义、每个开关的 overall/common/hard 数据、关闭时做得好/不好、开启后做得好/不好，以及最终结论，便于后续复盘时直接查看。

其中 `memory_quantitative_chain_eval.md` 是链路方案评测，关注“前一步打开后，再打开下一步能带来多少相邻增益”。它和单项 uplift 总表不是同一个口径：

- 单项总表回答“单独打开某个能力，相比关闭状态提升多少”。
- 链路总表回答“按工程链路累计打开能力，每一步相比上一步提升或下降多少”。
- 链路里的 `uplift_points` 是相邻增益，不是相对 baseline 的总增益。
- 当前离线结果：`chain_memory_base = 94.375`，`chain_all_on = 69.3043`，`total_chain_uplift_points = -25.0707`；`chain_off` 只作为关闭增强控制组。
- 当前相邻增益：写入价值 `+48.3345`，三路召回 `+19.5826`，图谱召回 `+0.1943`，重排与注入治理 `-2.8802`，版本链与溯源 `-2.1295`，睡眠巩固 `-3.5`，全开校验 `0`。
- 负相邻增益不等于功能无效；它说明当前平均评分公式把即时回答能力、治理能力和后台维护能力放在同一张主分里，后续需要做组合权重、场景路由和 active 化策略。

### Phase 6f 的目标指标百分比 report

Phase 6f 不再用单一综合分解释所有 memory 模块，而是把评测拆成三组：

```text
回答效果组
写入治理组
记忆库卫生组
```

推荐展示方式：

```text
开启前百分比
开启后百分比
提升百分点 = 开启后百分比 - 开启前百分比
相对提升 = 提升百分点 / 开启前百分比
```

如果开启前是 `0` 或 `unavailable`，不要强行说相对提升百分比，应展示“从不可用到 A%”或“提升 A 个百分点”。

回答效果组主要评估三路召回、图谱召回、重排注入治理、版本链与溯源：

- `target_recall_rate`：目标记忆召回率。
- `answer_hit_rate`：回答命中率。
- `evidence_hit_rate`：证据命中率。
- `wrong_recall_rate`：错误召回率。
- `wrong_injection_rate`：错误注入率。
- `current_version_recall_rate`：当前有效版本召回率，只看版本链 active leaf 应命中的记忆。
- `stale_version_misuse_rate`：旧版本误用率。
- `conflict_chain_detection_rate`：冲突版本链识别率；如果 fixture 没有分叉版本链，应显示 `unavailable`。

写入治理组主要评估写入价值治理：

- `useful_write_precision`：有效写入精度。
- `pollution_block_rate`：污染写入拦截率。
- `duplicate_control_rate`：重复控制率。
- `conflict_review_rate`：冲突转审率。
- `write_reduction_rate`：写入减少率。
- `false_reject_rate`：误拒率。
- `false_accept_rate`：误收率。

记忆库卫生组主要评估睡眠巩固、层级溯源和版本链库级信号：

- `duplicate_merge_rate`：重复合并率。
- `stale_cleanup_rate`：过期清理率。
- `low_value_cleanup_rate`：低价值清理率。
- `source_ref_coverage_rate`：source_ref 覆盖率。
- `source_fetch_success_rate`：回源成功率。
- `token_saving_rate`：token 节省率。
- `post_consolidation_recall_retention_rate`：巩固后召回保持率。

详细设计见 [05-memory-target-metric-eval-plan.md](./05-memory-target-metric-eval-plan.md)。

Phase 6h 分母与冲突链修订版离线报表已经生成：

- `my_md/memory_optimization/eval_reports/memory_target_metrics_eval.json`
- `my_md/memory_optimization/eval_reports/memory_target_metrics_eval.md`

当前报表元信息：

```text
measurement_mode = offline_trace_real_baseline_target_metrics
online_status = gated_no_checkpoint
online_row_count = 0
```

三张主表的 overall 结果：

| 模块组 | 模块 | 关键结果 |
| --- | --- | --- |
| 召回与回答 | 三路召回 | 目标召回率 `93.75% -> 100%`，提升 `6.25` 个百分点；hard 子集为 `87.5% -> 100%` |
| 召回与回答 | 图谱召回 | 目标召回率 `97.5% -> 100%`，提升 `2.5` 个百分点；hard 子集为 `95% -> 100%` |
| 召回与回答 | 重排与注入治理 | 目标召回率 `93.75% -> 100%`，提升 `6.25` 个百分点；错误注入率 after 为 `0%` |
| 召回与回答 | 版本链与溯源 | 目标召回率 `90% -> 100%`，当前有效版本召回率 `90% -> 100%`；hard 当前有效版本为 `80% -> 100%` |
| 写入治理 | 写入价值治理 | Phase 6n 独立离线计数报告使用 1200 个候选：原本写入 `1200/1200`，治理后直接写入 `172/1200`，最终写入 `400/1200`，有用候选最终保留率 `100%`，最终污染控制率 `100%`，冲突复核保持率 `100%`，hard 重复泄漏率 `0%` |
| 写入治理 | 写入价值治理线上 shadow | Phase 6o 真实 LLM 扩展评测使用 240 个 common/hard 与类别双维度平衡候选：`infra_passed = True`，`provider_error_count = 0`，`timeout_count = 0`，有效写入精度 `33.3333% -> 100%`，污染拦截率 `0% -> 100%`，重复控制率 `0% -> 100%`，冲突复核率 `0% -> 100%`，写入减少率 `0% -> 66.6667%` |
| 记忆库卫生 | 睡眠巩固 | 600 条扫描记忆，重复合并率 `10%`，source_ref 覆盖率 `86.6072%`，token 节省率 `33.482%`，巩固后召回保持率 `100%` |

注意：

- 第一版 `0% -> 100%` 是展示 baseline，已经废弃。当前正式报告的 `before` 来自 trace baseline 字段；如果没有真实 baseline 事件，则显示 `unavailable`。
- Phase 6f 的 `100% -> 100%` 和版本链 `100% -> 50%` 已被 Phase 6g 修订。Phase 6h 进一步把图谱召回分母从 tri target 中拆出来，并把版本链 forked replacement-chain fixture 变成可测。
- hard miss 是目标导向离线构造，不是线上真实用户自然分布；它用于证明模块能力和报表口径，不应直接解释成生产准确率。
- 图谱召回 after 现在为 `100%`；上一轮 `98.75%` 的缺口是分母口径问题，不是 graph lane 真缺口。
- 写入价值治理的 `有效写入精度 after` 为 `unavailable`，因为当前 80 case 的候选都被治理策略拒绝或转审，没有实际允许写入的候选；此时应主要看污染拦截率、重复控制率、写入减少率和误拒率。
- 写入治理的离线模板集已经补齐“有用候选最终保留率”和误拒控制，避免了全拒绝策略拿到漂亮分数；Phase 6o 也已经补了 `240` 条真实 LLM 线上 shadow evidence，证明真实 provider 路径能在更大平衡样本下产出可消费 evidence。但它仍是测试集候选，不是生产自然流量，也没有覆盖 LLM 自动抽取候选和后续召回有用率，所以不能把离线或线上 shadow 的 `100%` 直接解释成生产效果。
- 睡眠巩固的回源成功率当前是基于 `provenance_shadow.parse_success_rate` 的离线代理，不是生产中真实执行 `fetch_messages` 的成功率；token 节省也是 shadow 估算。
- 当前 fixture 已补一个 forked replacement chain，所以 `conflict_chain_detection_rate` 在 hard / overall 行上变成 `100%`。
- Phase 6i 已把写入治理和记忆库卫生的 evidence 输入收紧为 schema 校验入口：支持 JSON 数组、`{"records": [...]}` 和 JSONL，但缺字段、字符串布尔值、非法 label / decision / state、负数或非数字 token 都会失败，不会进入线上 evidence 行。

### Phase 6j 的完整目标导向测评集

为了不用真实用户数据也能先覆盖更多目标场景，当前新增了两档 case pack：

| case pack | case 数 | 用途 |
| --- | ---: | --- |
| `standard` | 80 | 默认标准集，用来复现前面已经记录的 Phase 6d-6i 报告。 |
| `comprehensive` | 320 | 完整目标导向集，用来扩大覆盖面，后续适合做正式离线对比和真实 LLM 大样本测试。 |

完整集不是手写最终分数，而是通过场景模板生成真实 `EvalCase`。它覆盖 20 类场景，每类包含 common / hard 两套样本和 8 个变体，总计：

```text
20 scenarios * 2 case sets * 8 variants = 320 cases
320 cases * 3 memorize candidates = 960 write candidates
320 cases * 约 7.5 scanned items = 2400 hygiene scan units
```

新增覆盖点包括：

- 实体别名和图谱桥接。
- 当前偏好覆盖旧偏好。
- 低价值写入过滤。
- 高风险 / 花费工具调用前确认。
- 注入噪声控制。
- 缺失 `source_ref` 的溯源风险。
- `session_key` 边界。
- 睡眠压缩后的召回保持。
- 因果一致性版本链。
- 信息熵 / 信息量写入价值。

运行命令：

```bash
.venv/bin/python scripts/run_memory_target_metrics_eval.py \
  --out-dir /tmp/akashic-memory-comprehensive-pack \
  --case-pack comprehensive
```

本轮离线 smoke 已跑通，结果摘要：

| 组 | 模块 | 规模 | before | after | 说明 |
| --- | --- | ---: | ---: | ---: | --- |
| 召回与回答 | 三路召回 | 320 case | `98.125%` | `100%` | hard 子集仍能制造 baseline miss。 |
| 召回与回答 | 图谱召回 | 320 case | `98.75%` | `100%` | 使用 graph 专用目标分母。 |
| 召回与回答 | 重排与注入治理 | 320 case | `98.125%` | `100%` | 错误注入率 after 为 `0%`。 |
| 召回与回答 | 版本链与溯源 | 320 case | `97.5%` | `100%` | 当前有效版本召回率 after 为 `100%`。 |
| 写入治理 | 写入价值治理 | 960 candidates | `unavailable` | `100%` 污染拦截 | before 没有真实决策计数，不能计算相对提升。 |
| 记忆库卫生 | 睡眠巩固 | 2400 scanned units | `0%` token saving | `32.8125%` token saving | 仍是 shadow 估算，不是生产 token 实测。 |

### Phase 6m Answer Comprehensive V2 召回计数结果

为了让“召回与回答”这张表更适合面试和复盘展示，当前新增了 `answer_comprehensive_v2` 目标导向测试集。它只评价回答侧召回链路，不包含写入治理和睡眠巩固。

正式报告路径：

```text
my_md/memory_optimization/eval_reports/memory_answer_retrieval_counts_eval.json
my_md/memory_optimization/eval_reports/memory_answer_retrieval_counts_eval.md
```

评测规模：

```text
case_count = 1000
target_count = 2000
measurement_mode = offline_answer_retrieval_count_eval
baseline_profile = memory_base
chain_baseline_profile = chain_memory_base
```

单模块启动结果：

| 模块 | 命中 | 漏召 | 召回率 | 相对召回率提升 | 相对基线漏召减少率 | 结论 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 原始 memory | `1978/2000` | `22/2000` | `98.9%` | `0.0%` | `0.0%` | 主基线，不用关闭记忆夸大收益。 |
| 三路召回 | `2000/2000` | `0/2000` | `100.0%` | `1.1122%` | `100.0%` | 补齐全部 22 条漏召回，是当前最直接的召回增强。 |
| 图谱召回 | `1994/2000` | `6/2000` | `99.7%` | `0.8089%` | `72.7273%` | 对实体别名、模糊指代和关系跳转有正向贡献。 |
| 重排与注入治理 | `1584/2000` | `416/2000` | `79.2%` | `-19.9191%` | `-1790.9091%` | 单独开启会因候选池不足放大漏召，不应当作扩召回入口评价。 |
| 版本链与溯源 | `1000/2000` | `1000/2000` | `50.0%` | `-49.4439%` | `-4445.4545%` | 单独看召回会低估它，主要价值是版本选择和证据可信度。 |
| 回答链路全开 | `1998/2000` | `2/2000` | `99.9%` | `1.0111%` | `90.9091%` | answer-only 组合有正向收益，但仍比三路召回单项少 2 条。 |

模块依次启动结果：

| 链路步骤 | 命中 | 漏召 | 累计相对召回率提升 | 累计漏召减少率 | 结论 |
| --- | ---: | ---: | ---: | ---: | --- |
| 原始 memory | `1978/2000` | `22/2000` | `0.0%` | `0.0%` | 原始基线已经很强。 |
| + 三路召回 | `2000/2000` | `0/2000` | `1.1122%` | `100.0%` | 补齐所有 baseline miss。 |
| + 图谱召回 | `2000/2000` | `0/2000` | `1.1122%` | `100.0%` | 在三路已满召回后不再增加命中，但不损伤召回。 |
| + 重排与注入治理 | `2000/2000` | `0/2000` | `1.1122%` | `100.0%` | 放在召回后做候选治理时不损伤召回。 |
| + 版本链与溯源 | `1998/2000` | `2/2000` | `1.0111%` | `90.9091%` | 仍保持高召回，但组合权重和版本选择还可优化。 |
| 回答链路全开 | `1998/2000` | `2/2000` | `1.0111%` | `90.9091%` | 全开不是最强召回路径，三路召回仍是当前最强基础增强。 |

本轮新增的百分比口径：

```text
相对召回率提升 = 召回率变化百分点 / 原始基线召回率
漏召回减少率 = 漏召回减少数 / 原始基线漏召数
```

注意：这份离线计数报告只回答“目标记忆有没有被召回”。回答正确性、证据命中、噪声控制和上下文成本不能从这份报告中直接计算，需要后续在线 shadow / agent dry-run 采集真实 LLM 输出、source_ref / grounding trace、注入条目明细和 token / latency evidence。

这个完整集的定位：

- 可以直接用于更有说服力的离线开关对比。
- 可以作为真实 LLM runner 的输入，但如果按 `8 profiles * 2 prompt variants * 2 repeats` 全量跑，会变成 `10240` 次调用，必须显式评估 token 和时间成本。
- 它仍然不是线上真实自然分布。它是目标导向压力集，目的是证明“某个能力开关是否能处理我们关心的问题”。

### Phase 6k 的真实 LLM core matrix

本轮真实 LLM core matrix 已完成，并带 checkpoint 恢复：

```text
320 cases * 4 profiles * 1 prompt variant * 1 repeat = 1280 calls
```

真实报告路径：

```text
/tmp/akashic-memory-phase6k-real/reports/memory_comprehensive_online_eval.json
/tmp/akashic-memory-phase6k-real/reports/memory_comprehensive_online_eval.md
```

checkpoint 重建版路径：

```text
/tmp/akashic-memory-phase6k-real/checkpoint-report/memory_comprehensive_online_eval.json
/tmp/akashic-memory-phase6k-real/checkpoint-report/memory_comprehensive_online_eval.md
```

最终真实报告摘要：

- `case_count = 1280`
- `unique_case_count = 320`
- `profile_count = 4`
- `prompt_variant_count = 1`
- `repeat_count = 1`
- `answer_rule_pass_rate = 23.9844`
- `memory_grounding_pass_rate = 75.0`
- `forbidden_violation_rate = 15.7812`
- `avg_latency_ms = 4639.9172`
- `total_token_count = 6971048`

这份结果只覆盖 answer/retrieval 核心矩阵，不包含写入治理和睡眠巩固的真实 evidence。写入治理后续已通过 Phase 6o 单独补了 `240` 条真实 LLM 线上 shadow evidence；睡眠巩固仍缺真实 evidence。

### Phase 6e 的综合线上 answer-level report

Phase 6e 把离线 80 个目标导向 case 接到真实 `AgentLoop.process_direct()` 和真实 LLM 上。完整设计规模是：

```text
80 cases * 8 chain profiles * 2 prompt variants * 2 repeats = 2560 runs
```

本轮真实执行过程中，外部 provider 在 checkpoint 已有 `1599` 条记录时返回 `402 Insufficient Balance`。按计划停止后，报告用 `--checkpoint-report-only --exclude-infra-failures` 从 checkpoint 重建，只统计没有 timeout / provider error 的有效样本：

- `case_count = 1417`
- `unique_case_count = 45`
- `checkpoint_input_count = 1599`
- `excluded_infra_failure_count = 182`
- `partial_due_to_infra_failure = True`
- `infra_passed = True`
- `answer_quality_passed = False`
- `passed_case_count = 315`
- `failed_answer_case_count = 975`
- `total_token_count = 7600606`
- `avg_latency_ms = 4976.7276`

这份报告可以回答“余额耗尽前的真实 answer-level 样本里，各 profile 表现如何”，不能回答“完整 2560-run 最终结论是什么”。
报告 JSON 顶层 `passed = False`，表示答案质量没有全量通过；CLI 返回 0 只表示排除基础设施失败后的报告成功生成。

answer-level 主指标仍沿用：

```text
main_score = 0.7 * answer_rule_pass_rate
           + 0.2 * memory_grounding_pass_rate
           + 0.1 * (100 - forbidden_violation_rate)
```

本轮有效样本的 profile 结果：

| profile | main_score | uplift_vs_off | adjacent_uplift | answer_rule_pass_rate | memory_grounding_pass_rate | forbidden_violation_rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| chain_off | 18.4269 | 0 | 0 | 12.9213 | 0 | 6.1798 |
| chain_write_value | 18.0791 | -0.3478 | -0.3478 | 12.4294 | 0 | 6.2147 |
| chain_tri_retrieval | 53.9548 | 35.5279 | 35.8757 | 38.4181 | 100 | 29.3785 |
| chain_graph_retrieval | 54.8588 | 36.4319 | 0.904 | 38.9831 | 100 | 24.2938 |
| chain_rerank_injection | 61.5819 | 43.155 | 6.7231 | 46.3277 | 100 | 8.4746 |
| chain_version_provenance | 42.3729 | 23.946 | -19.209 | 46.3277 | 0 | 0.565 |
| chain_sleep_consolidation | 47.0057 | 28.5788 | 4.6328 | 28.2486 | 100 | 27.6836 |
| chain_all_on | 45.4237 | 26.9968 | -1.582 | 25.9887 | 100 | 27.6836 |

online balanced proxy 不是生产准确率。它把线上回答字段映射到回答、证据、治理、效率等维度，用来解释为什么某些中后段治理能力在单一 answer score 上不明显：

| profile | balanced_proxy | adjacent_delta |
| --- | ---: | ---: |
| chain_off | 28.8221 | 0 |
| chain_write_value | 28.6527 | -0.1694 |
| chain_tri_retrieval | 63.4069 | 34.7542 |
| chain_graph_retrieval | 64.1737 | 0.7668 |
| chain_rerank_injection | 69.6528 | 5.4791 |
| chain_version_provenance | 43.652 | -26.0008 |
| chain_sleep_consolidation | 58.0787 | 14.4267 |
| chain_all_on | 56.8747 | -1.204 |

本轮结论：

- 三路召回、图谱召回、重排与注入治理在真实 answer-level 有正向贡献，其中 `chain_rerank_injection` 当前主分最高。
- 写入价值、睡眠巩固这类能力不一定直接提升当前回答命中，应继续结合离线写入污染率、去重率、token 节省和 balanced proxy 判断。
- 版本链与溯源 profile 的 `memory_grounding_pass_rate = 0`，导致相邻主分明显下降。这不是版本链思想无效，而是当前受控证据 ID / active leaf 注入策略还没和答案级 grounding 规则对齐。
- 全开不等于最优。当前结果更支持“先 active 三路召回 + 图谱召回 + 重排注入治理，再修订版本链、睡眠巩固和全开组合策略”。

### 写入价值和睡眠巩固的正确评测口径

Phase 6e 的 answer-level report 对三路召回、图谱召回、重排注入治理更公平，因为这些能力会直接改变“当前回答能看到什么证据”。但写入价值和睡眠巩固属于长期记忆治理能力，它们的收益主要体现在后续轮次、记忆库质量和成本控制上。

#### 写入价值评分应该怎么测

写入价值评分要回答的问题不是“当前回答有没有变好”，而是：

- 这条候选记忆是否值得长期保存。
- 是否拒绝了临时信息、重复信息和 assistant 推断。
- 是否保留了真正稳定的用户偏好、长期约束和重要事实。
- 被保留下来的记忆在未来轮次是否真的能被召回并改善回答。

推荐测试方法：

```text
同一批对话输入
  -> baseline：按旧逻辑生成候选写入
  -> experimental：写入价值评分给出 allow / reject / reason
  -> 延迟评测：用后续问题验证被保留记忆是否能被用上
```

推荐测试集：

- 稳定偏好：例如长期语言偏好、工具偏好、格式偏好。
- 长期事实：例如项目路径、常用命令、固定约束。
- 临时状态：例如“今天先这样”“这次不用”等不应长期保存的信息。
- assistant 推断：模型自己推测出的用户偏好，不应直接写入长期记忆。
- 重复表达：用户多次表达同一偏好，应强化或合并，而不是写多条。
- 冲突纠错：用户明确改口时，应写新版本并让旧版本失效。

核心指标：

| 指标 | 含义 |
| --- | --- |
| `candidate_count` | 候选记忆数量 |
| `baseline_written_count` | 旧逻辑会写入的数量 |
| `policy_allow_count` | 新策略建议写入数量 |
| `policy_reject_count` | 新策略建议拒绝数量 |
| `reject_reason_distribution` | 拒绝原因分布 |
| `temporary_reject_count` | 临时信息拒写数量 |
| `assistant_inference_reject_count` | assistant 推断拒写数量 |
| `duplicate_risk_count` | 重复风险数量 |
| `write_reduction_rate` | 写入减少比例 |
| `memory_pollution_rate` | 错写、脏写、临时写入的比例 |
| `useful_memory_precision` | 写入后被判定为有长期价值的比例 |
| `future_recall_usefulness` | 后续问题中被正确召回并改善回答的比例 |
| `false_reject_rate` | 不该拒绝却被拒绝的重要记忆比例 |
| `false_accept_rate` | 不该写入却被放行的低价值记忆比例 |

判断标准：

- 好结果不是“写得越少越好”，而是污染率下降、重复率下降，同时关键偏好和长期约束没有被误拒。
- 写入价值可以在 answer-level 上短期无提升甚至微降；只要后续轮次的有效召回率、记忆精度和污染控制提升，就是它的真实收益。

#### 睡眠巩固应该怎么测

睡眠巩固要回答的问题不是“当前这一问是否答得更准”，而是：

- 长期记忆库是否变得更干净。
- 重复、过期、低价值、冲突记忆是否被识别。
- prompt 注入是否更省 token。
- 巩固后是否没有伤害关键记忆召回。
- 检索结果是否更集中、更少错误召回。

推荐测试方法：

```text
同一份 memory DB 快照
  -> before：直接跑检索和答案评测
  -> dry-run：只输出睡眠巩固候选，不修改 DB
  -> active-on-clone：在临时克隆 DB 上应用合并 / 过期 / 降权
  -> after：用同一批检索问题和答案问题复测
```

推荐测试集：

- 大量重复偏好：验证合并和强化。
- 过期信息：验证 stale 检测和降权。
- 低价值碎片：验证低价值候选识别。
- 冲突记忆链：验证旧版本不再污染当前召回。
- source_ref 缺失：验证缺少来源的记忆是否被标记为低可信。
- 关键长期偏好：验证睡眠巩固不能误删、误降权重要记忆。

核心指标：

| 指标 | 含义 |
| --- | --- |
| `scanned_count` | 扫描记忆数量 |
| `duplicate_group_count` | 重复组数量 |
| `duplicate_item_count` | 重复记忆条数 |
| `merge_candidate_count` | 可合并候选数量 |
| `stale_candidate_count` | 过期候选数量 |
| `low_value_candidate_count` | 低价值候选数量 |
| `conflict_candidate_count` | 冲突候选数量 |
| `missing_source_ref_count` | 缺少来源引用数量 |
| `estimated_token_saving` | 预计节省 token |
| `estimated_redundancy_drop` | 预计冗余下降 |
| `before_active_count` / `after_active_count` | 巩固前后 active 记忆数量 |
| `post_consolidation_recall_precision` | 巩固后的召回精度 |
| `post_consolidation_wrong_recall_rate` | 巩固后的错误召回率 |
| `protected_memory_recall_rate` | 关键记忆保护召回率 |
| `prompt_token_delta` | 注入 prompt token 变化 |

判断标准：

- 好结果不是“删得越多越好”，而是在关键记忆不丢失的前提下降低重复、过期和低价值注入。
- 睡眠巩固适合用 before/after 快照评测，而不是只看单轮 answer-level 分数。
- 如果 answer-level 主分没有明显提升，但 token、重复率、错误召回率和治理分改善，仍然说明睡眠巩固有价值。

报表文件：

- `my_md/memory_optimization/eval_reports/memory_comprehensive_online_eval.json`
- `my_md/memory_optimization/eval_reports/memory_comprehensive_online_eval.md`

其中 `memory_quantitative_balanced_eval.md` 是分层 balanced 链路评测，用来缓解单一主分对后段治理能力不公平的问题。它不是把所有能力重新包装成一个更好看的分数，而是把指标拆成：

- `answer_score`：回答规则或目标记忆命中代理分。
- `retrieval_proxy_score`：召回相关链路步骤上的离线召回代理分，不是真实 `recall@k`。
- `grounding_score`：来源、证据或可解释字段覆盖情况。
- `governance_score`：综合 forbidden 控制和 grounding 的治理分。
- `efficiency_score`：token 节省或 prompt token 控制的效率分；缺失时为 `unavailable`。
- `balanced_score`：只用可用维度归一化后的综合代理分。

公式为：

```text
balanced_score = 0.30 * answer_score
               + 0.25 * retrieval_proxy_score
               + 0.20 * grounding_score
               + 0.15 * governance_score
               + 0.10 * efficiency_score
```

如果某个维度是 `unavailable`，不会把它当成 0 或 50，而是从本次综合分里移除，并按剩余可用维度重新归一化权重。

Balanced report 借鉴 RAG/Agent 分层评测共识，把回答、召回代理、证据、治理和效率分开；本项目的改进是把 memory 生命周期治理纳入评分，包括 forbidden、source_ref、版本链、scope 隔离和 token/sleep 信号。它仍然是离线代理评测，不是生产回答准确率。

本轮 balanced 结果：

- `case_count = 80`
- `common_case_count = 40`
- `hard_case_count = 40`
- `baseline_balanced_score = 12.6923`
- `final_balanced_score = 67.2022`
- `total_balanced_uplift_points = 54.5099`
- `common_final_balanced_score = 66.6972`
- `hard_final_balanced_score = 67.7072`
- 相邻增益最高：`chain_write_value = +33.1924`
- 相邻增益最低：`chain_rerank_injection = -4.5898`

报表文件：

- `my_md/memory_optimization/eval_reports/memory_quantitative_balanced_eval.json`
- `my_md/memory_optimization/eval_reports/memory_quantitative_balanced_eval.md`

解释边界：

- retrieval / injection 可以作为离线质量 proxy。
- version/provenance/sleep 更多是治理信号 proxy。
- 因为没有真实 LLM 和真实 memory DB，不能宣称真实回答准确率提升。

### 5. 回源成功率

需要记录 `fetch_messages` 与 memory source_ref 的关联：

- 有 source_ref 的召回项。
- 是否调用 fetch_messages。
- fetch 是否成功。
- fetch 后是否用于最终回答。

## 必须有评测集才能测的指标

这些不能只靠日志得出：

- 检索准确率。
- 错误召回率。
- 记忆污染率。
- 纠错成功率。
- 跨 session 隔离正确率。
- 临时信息拒写正确率。
- 冲突检测准确率。

需要构造标注集：

```text
输入问题
期望召回 memory id
不应召回 memory id
期望 source_ref
期望是否写入长期记忆
期望是否拒绝写入
```

建议评测维度：

- 偏好召回。
- 历史事件回源。
- 纠错后旧记忆不再召回。
- 临时会话信息不写入长期记忆。
- 跨 session 不错误召回。
- 过期状态不强注入。

### Phase 6a-1 已建立的评测集 schema

当前第一版评测集已经落到 `memory2/eval_cases.py` 和 `tests/fixtures/memory_eval_cases/`。它解决的是“后续 runner 用什么数据结构做对照”，不是直接运行评测。

每个 case 至少包含：

- `id` / `title` / `category`：评测用例身份和类别。
- `phase_targets`：这个 case 想验证的实验阶段，例如 `phase2a`、`phase3b`、`phase5`。这里不能写 `off` 或 `all`。
- `config_profiles`：runner 后续要跑的配置 profile，包括 `off`、对应阶段 profile 和 `all`。
- `setup.scope`：会话 scope，包含 `session_key`、`channel`、`chat_id`。
- `setup.memory_items`：预置记忆项，用于构造召回、冲突、跨 scope、过期等场景。
- `setup.memory_replacements`：可选，用于版本链和纠错场景。
- `setup.memorize_calls`：可选，用于表达写入候选或写入污染场景。
- `setup.query` 或 `setup.conversation`：触发召回或写入判断的输入。
- `expectations.should_recall_ids`：应该被召回的 memory id。
- `expectations.should_not_recall_ids`：不应该被召回或不应该被写入的 memory id。
- `expectations.expected_trace_features`：该 case 期望观察到的实验 trace 名称。
- `expectations.expected_metric_keys`：每个 trace 至少应产出的指标字段。
- `expectations.profile_expectations`：不同 profile 下应该出现或不应该出现的 trace / metric。

第一批 9 个 case 覆盖：

- `preference_recall`：偏好召回。
- `temporary_memory_pollution`：临时信息写入污染。
- `duplicate_memory`：重复记忆与写入减少。
- `conflict_memory`：冲突记忆和版本链。
- `vague_reference_graph`：模糊指代下的图谱召回。
- `injection_governance_budget`：注入治理和 prompt 预算。
- `cross_scope_isolation`：跨 channel/chat scope 隔离。
- `stale_memory_sleep`：过期记忆和睡眠巩固。
- `provenance_trace`：层级化溯源。

配置 profile 到真实开关的第一版映射：

| profile | 作用 |
| --- | --- |
| `off` | `memory_experiments.enabled = false`，作为关闭实验能力的基线。 |
| `phase1` | 只开启实验框架和写入价值 shadow 的基础配置。 |
| `phase2` | 开启 `graph_retrieval_enabled`，用于三路召回 / 图谱召回对照。 |
| `phase3` | 开启 `rerank_shadow_enabled` 和 `injection_governance_shadow_enabled`。 |
| `phase4` | 开启 `version_chain_shadow_enabled` 和 `provenance_shadow_enabled`。 |
| `phase5` | 开启 `sleep_consolidation_shadow_enabled`。 |
| `all` | 开启 Phase 2-5 已有 shadow 开关，用于完整实验组合。 |

Phase 6a-1 的测试只校验 schema 和 fixture 一致性，包括：

- fixture id 必须等于文件名。
- 每个 case 必须包含 `off` 和 `all` profile。
- `phase_targets` 必须能映射到对应 profile。
- 期望召回 id 必须存在于预置记忆或写入候选中。
- 指标字段只能挂在已声明的 trace feature 上。

因此，当前能得到的是“评测集可被后续 runner 稳定消费”的结论，还不能得到 `recall_at_k`、`precision_at_k` 或污染率等真实对比数据。

### Phase 6a-2 已建立的离线 runner

Phase 6a-2 新增 `memory2/eval_runner.py`，把 Phase 6a-1 的静态 fixture 真正跑成 profile 对照报告。它仍然是离线 runner，不启动 Agent，不调用 LLM，不调用 embedding，不写真实 memory DB，也不写 observe DB。

runner 的核心行为：

- 每个 case 按自己的 `config_profiles` 运行，例如 `off`、`phase2`、`phase3`、`all`。
- `off` profile 不产生实验 trace，用作关闭实验能力的基线。
- 单阶段 profile 只运行该阶段对应的 trace。
- `all` profile 只运行该 case 声明过、且当前已实现的 trace，避免无关 trace 噪音。
- 对每个 profile 校验 required trace、forbidden trace、metric key、应召回 id、不应召回 / 不应注入 id。
- 生成 `EvalRunReport`，并可通过 `write_eval_report()` 输出稳定 JSON。

当前 report 汇总字段：

- `case_count`：本次评测 case 数量。
- `profile_count`：所有 case 展开的 profile 总数。
- `passed_case_count`：通过的 case 数量。
- `failed_case_count`：失败的 case 数量。
- `failed_profile_count`：失败的 profile 数量。
- `trace_count`：总 trace 数量。
- `trace_count_by_feature`：按 trace feature 统计的数量。
- `profile_pass_rate`：profile 通过率。

本轮 fixture 全量运行结果：

```text
case_count = 9
profile_count = 30
passed_case_count = 9
failed_case_count = 0
failed_profile_count = 0
trace_count = 30
profile_pass_rate = 1.0
```

`trace_count_by_feature`：

```text
version_chain_shadow = 2
sleep_consolidation_shadow = 6
provenance_shadow = 4
write_value_score = 4
rerank_shadow = 4
injection_governance_shadow = 4
tri_retrieval = 4
graph_retrieval = 2
```

这说明当前能做的是“fixture-contract 级别的 off/on trace 对照”：某个 profile 开启后，期望 trace 是否出现，关键指标字段是否齐全，fixture 标注的应召回 / 不应召回约束是否满足。

这还不能直接说明：

- 生产环境真实召回准确率。
- `recall_at_k` / `precision_at_k`。
- 模型最终回答是否真的使用了正确记忆。
- source evidence 是否支撑最终答案。
- active 化后是否长期稳定。

这些仍需要后续加入答案级标注、真实检索样本、Dashboard 展示和连续评测。

### Phase 6b-1 已建立的真实样本评测链路

Phase 6b-1 新增真实 memory 数据的只读采样和报告链路。它和 Phase 6a 的静态 fixture 不同：数据来源变成真实 `workspace/memory/memory2.db`。但它仍然不是线上 Agent 评测，不启动 Agent，不调用 LLM，不调用 embedding，不写真实 memory DB 或 observe DB。

第一版实现边界：

- 使用 raw sqlite 只读连接打开 `workspace/memory/memory2.db`。
- 启用 `PRAGMA query_only=ON`，避免采样过程产生迁移或写入副作用。
- 不实例化 `MemoryStore2` 或 `SessionStore`，因为这些构造路径可能初始化或迁移 schema。
- 默认不把真实 memory summary 或 session 原文写入报告，只输出 id、类别、scope、指标和失败原因。
- 把真实样本转换成 `EvalCase` 后复用 Phase 6a-2 的离线 runner，得到 labelled contract metrics。
- 额外计算 unforced candidate metrics，不把 `should_recall_ids` 强行塞进召回结果，更接近真实候选行为。

当前 Phase 6b-1 可输出两类指标。

第一类是 labelled contract metrics：

- `sample_count`：真实样本数量。
- `case_count`：由真实样本转换出的 eval case 数量。
- `profile_count`：展开后的 profile 数量。
- `profile_pass_rate`：profile contract 通过率。
- `labelled_contract_pass_rate`：标注契约通过率。
- `labelled_should_not_violation_count`：不应召回约束违规数量。
- `trace_count_by_feature`：按实验 trace 统计的输出数量。

第二类是 unforced candidate metrics：

- `label_forced_recall = false`：明确表示没有用标注强制命中。
- `candidate_hit_count_without_label_forcing`：不强制标注时命中候选数量。
- `candidate_miss_count_without_label_forcing`：不强制标注时未命中候选数量。
- `candidate_hit_rate_without_label_forcing`：不强制标注时的候选命中率。
- `candidate_wrong_scope_count`：候选中 scope 不匹配的数量。
- `candidate_labelled_wrong_scope_count`：跨 scope 候选同时命中 `should_not_recall_ids` 标注的数量。
- `candidate_count_by_category`：按样本类别统计的候选数量。

审计明细字段：

- `sample_records`：脱敏样本明细，包含 `sample_id`、`session_key`、类别、scope、memory id 和 replacement edge，不包含 query 或 memory summary。
- `profile_records`：每个 case/profile 的通过状态、trace feature、召回 id、注入 id、指标和失败原因。
- `candidate_records`：每个真实样本的不强制候选 id、跨 scope 候选 id 和标注命中的 wrong-scope id。
- `failure_records`：按 case/profile 展开的失败原因。

降级和数据质量计数：

- `invalid_extra_json_count`：真实 memory 的 `extra_json` 无法解析。
- `missing_scope_count`：真实 memory 缺少 `scope_channel` 或 `scope_chat_id`。
- `missing_table_count`：真实库缺少评测需要的表，或本地没有对应 DB。
- `cross_scope_sample_unavailable`：当前数据不足以构造跨 scope 样本。

本机实跑结果：

```text
workspace/memory/memory2.db 不存在
/home/jjh/git_work/akashic-agent/workspace/memory/memory2.db 不存在
```

因此 CLI 正常生成降级报告，但返回 exit code 1，表示没有真实样本可评测。报告路径：

```text
my_md/memory_optimization/eval_reports/memory_real_sample_eval.json
my_md/memory_optimization/eval_reports/memory_real_sample_eval.md
```

本次降级报告摘要：

```text
sample_count = 0
memory_item_count = 0
replacement_count = 0
missing_table_count = 1
cross_scope_sample_unavailable = 1
profile_count = 0
trace_count = 0
candidate_hit_rate_without_label_forcing = 0.0
label_forced_recall = false
llm_calls_enabled = false
answer_quality_available = false
```

当前能得出的结论是：真实样本评测代码和报告链路已经具备；本机缺少真实 memory DB，所以还没有真实样本效果数据。要得到真实数值，需要先提供或生成 `workspace/memory/memory2.db`。

### Phase 6b-2 已建立的 Agent dry-run 链路

Phase 6b-2 把 Phase 6a fixture 接入真实 `AgentLoop.process_direct()`，用于验证 eval case 能否穿过真实被动 turn pipeline。它比 Phase 6a-2 更接近真实运行链路，但仍然不是线上 Agent 评测。

第一版实现边界：

- 使用真实 `AgentLoop`。
- 使用真实 `SessionManager`，但只写入显式传入的临时 workspace。
- 使用真实 `DefaultMemoryRetrievalPipeline`，把 case query、session scope 和 history 转换成 `MemoryEngineRetrieveRequest`。
- 使用真实 `EventBus`，观察 `TurnCommitted`。
- LLM 使用 fake provider，固定返回 deterministic response。
- memory engine 使用受控测试 engine，只返回 memory id，不返回真实 summary。
- 不启动 `main.py`、IPC、Dashboard 或任何长驻服务。
- 不调用真实 LLM、embedding、网络或外部服务。
- 不写真实 `workspace/memory/memory2.db`、`workspace/sessions.db` 或 `workspace/observe/observe.db`。

当前 Phase 6b-2 可输出的集成指标：

- `agent_loop_enabled`：是否经过真实 `AgentLoop`。
- `fake_llm_enabled`：是否使用 fake LLM。
- `llm_calls_enabled`：固定为 `false`，表示没有真实 LLM 调用。
- `embedding_calls_enabled`：固定为 `false`。
- `answer_quality_available`：固定为 `false`，表示不评估最终回答质量。
- `case_count`：dry-run case 数量。
- `passed_case_count` / `failed_case_count`：通过和失败 case 数量。
- `agent_turn_count`：真实 Agent turn 数量。
- `retrieval_request_count`：进入 memory retrieval pipeline 的请求数量。
- `fake_llm_call_count`：fake provider 被调用次数。
- `turn_committed_count`：观察到的 `TurnCommitted` 数量。
- `session_message_count`：临时 session 中写入的消息数量。
- `retrieval_query_matched`：检索请求 query 是否来自当前 case。
- `retrieval_history_seen`：检索请求是否带 history 字段。

隐私和正文输出边界：

- `raw_query_included = false`
- `raw_memory_summary_included = false`
- `prompt_included = false`
- `session_text_included = false`

本轮本地 dry-run 结果：

```text
case_count = 9
passed_case_count = 9
failed_case_count = 0
agent_turn_count = 9
retrieval_request_count = 9
fake_llm_call_count = 9
turn_committed_count = 9
session_message_count = 18
```

当前能得出的结论是：评测集已经能穿过真实 Agent turn pipeline，并能观察到检索请求、会话写入和 `TurnCommitted`。但由于 LLM 是 fake provider，memory engine 是受控测试 engine，它仍然不能说明真实回答质量、真实召回准确率、source support 或 token 成本。

### Phase 6b-3 已建立的答案级小样本评测链路

Phase 6b-3 在 Phase 6b-2 的真实 `AgentLoop` dry-run 基础上增加答案级评分。它仍然默认不调用真实 LLM；真实 provider 只有在 CLI 显式传入 `--enable-real-llm` 后才会构造。自动化测试和本轮提交报告都使用 fake provider。

第一版实现边界：

- 只选择带 `expectations.answer_expectations` 的 fixture。
- 首批运行 3 个稳定 case：`cross_scope_isolation`、`preference_recall`、`vague_reference_graph`。
- 使用受控 memory engine 注入 fixture memory summary，但报告只保留 memory id 和指标，不写 summary 原文。
- 使用确定性规则评分答案：期望关键词、禁止关键词、期望 memory id 是否被使用、中文检测。
- token 统计是 best-effort；如果 provider 没有返回 usage 字段，报告会标记 `token_metrics_available = false`。
- provider 异常只记录为脱敏类别，例如 `provider_error`，不写原始异常文本。
- 不写真实 `workspace/memory/memory2.db`、真实 `workspace/sessions.db` 或真实 `workspace/observe/observe.db`。

当前可输出的答案级指标：

- `answer_quality_available`
- `answer_contains_pass_count`
- `answer_contains_miss_count`
- `forbidden_contains_violation_count`
- `expected_memory_used_count`
- `language_pass_count`
- `provider_error_count`
- `timeout_count`
- `prompt_token_count`
- `completion_token_count`
- `total_token_count`
- `token_metrics_available`
- `total_latency_ms`
- `avg_latency_ms`

本轮 fake-provider 报告结果：

```text
case_count = 3
passed_case_count = 3
failed_case_count = 0
answer_contains_pass_count = 5
answer_contains_miss_count = 0
forbidden_contains_violation_count = 0
expected_memory_used_count = 3
language_pass_count = 3
provider_error_count = 0
timeout_count = 0
token_metrics_available = true
prompt_token_count = 60
completion_token_count = 30
total_token_count = 90
total_latency_ms = 56
avg_latency_ms = 18
```

这些数据证明答案级评测、token 元数据采集和脱敏报告链路已经跑通。由于本轮使用 fake provider，token 数和延迟只用于验证链路，不代表真实模型费用或真实响应性能。真实质量数据需要后续人工确认后运行 `--enable-real-llm`。

真实 LLM 人工确认运行结果：

```text
real_llm_enabled = true
case_count = 3
passed_case_count = 1
failed_case_count = 2
answer_contains_pass_count = 3
answer_contains_miss_count = 2
forbidden_contains_violation_count = 0
expected_memory_used_count = 3
language_pass_count = 3
provider_error_count = 0
timeout_count = 0
token_metrics_available = true
prompt_token_count = 14911
completion_token_count = 0
total_token_count = 14911
total_latency_ms = 10114
avg_latency_ms = 3371
```

失败明细：

- `cross_scope_isolation`：缺少固定期望词 `Telegram`。
- `vague_reference_graph`：缺少固定期望词 `三路召回`。

这次真实运行可以得出两个分层结论：

- 记忆注入 / grounding 链路是通的：3 个 case 都记录到了期望 memory id。
- 答案规则需要修订：当前 `expected_answer_contains` 要求每个固定词都出现，容易把合理同义表达误判为失败。

因此下一步不应简单放宽为“全部通过”，而应把答案期望结构扩展成“必须命中项 + 同义词任一命中组”，并增强 token usage 解析。

修订后真实 LLM 复测结果：

```text
real_llm_enabled = true
case_count = 3
passed_case_count = 2
failed_case_count = 1
answer_rule_pass_count = 2
memory_grounding_pass_count = 3
answer_contains_pass_count = 2
answer_contains_miss_count = 1
forbidden_contains_violation_count = 0
expected_memory_used_count = 3
language_pass_count = 3
provider_error_count = 0
timeout_count = 0
token_metrics_available = true
prompt_token_count = 16496
completion_token_count = 602
total_token_count = 17098
total_latency_ms = 9427
avg_latency_ms = 3142
```

修订效果：

- `cross_scope_isolation` 通过：不再要求回答必须出现平台名 `Telegram`，而是用 memory id 命中和禁止出现 `QQ` / `更短` 验证 scope 隔离。
- token usage 通过 provider 层标准 usage 暴露后，`completion_token_count` 从 0 变为 602。
- `vague_reference_graph` 仍失败：回答没有命中 `RRF`，也没有命中 `三路召回 / 第三路 / 第三路方案 / 融合排序` 任一同义词组。这个失败应保留为真实答案质量信号，后续需要加强 memory evidence 使用或增加显式引用要求，而不是继续无约束放宽评分。

当前问题和可能原因：

| 问题 | 当前证据 | 可能原因 |
| --- | --- | --- |
| 模糊指代图谱 case 未通过 | `vague_reference_graph` 的 `memory_grounding_passed = true`，但 `answer_rule_passed = false` | 模型拿到了 memory id，但没有稳定使用 `RRF / 第三路 / 融合排序` 这类关键排序证据 |
| 真实样本覆盖不足 | 真实 LLM 只跑了 3 个受控 case | 当前阶段目标是验证链路和指标，不足以统计整体准确率 |
| 真实 memory DB 未参与 | memory 来自 fixture，不读取 `workspace/memory/memory2.db` | 为了隔离变量，Phase 6b-3 先固定 memory 输入；真实库评测需要后续样本采集和召回链路组合 |
| 语义等价判断有限 | 评分器使用固定词和同义词组 | 简单规则可解释、可重复，但无法替代人工标注或 LLM-as-judge |
| 答案正文不可见 | 报告只记录长度和脱敏失败原因 | 隐私边界优先，排查复杂语义失败时需要显式 debug 开关写临时文件 |
| prompt 可能没有足够证据约束 | memory id 命中但关键术语未出现在答案规则中 | 注入内容没有要求模型引用 memory id、复述关键事实或说明依据 |

下一步优化方向不是继续放宽 `vague_reference_graph` 的评分，而是验证模型为什么没有使用关键证据。可选方案包括：给答案级 eval 增加显式引用要求、在 prompt 中标注“回答必须使用相关记忆证据”、增加 answer debug 手动开关，或把真实三路召回 / 图谱路径证据接入该小样本评测。

## 指标优先级

### P-1：实验对照输出

新增 memory 插件实验能力时，每条实验记录都应能关联：

```text
run_id
session_key
turn_id
feature_name
mode
baseline_result
experimental_result
diff_json
metrics_json
created_at
```

这样才能在 shadow 模式下回答：

- 旧逻辑写入了什么，新策略建议写入什么。
- 旧逻辑召回了什么，三路召回召回了什么。
- 旧排序注入了什么，新重排建议注入什么。
- 后台巩固建议改什么，真实库是否被修改。

Phase 0 首个落地点是 `write_value_score` shadow trace。它先记录显式 `memorize` 工具调用中的候选记忆：

- `baseline_written_count`
- `policy_allow_count`
- `policy_reject_count`
- `reject_reason_distribution`

这只是实验数据，不代表真实写入策略已经改变。

增强后的写入价值 shadow 评分会为每个候选输出：

- `final_score`
- `decision`
- `reason`
- `reasons`
- `signals.explicit_user_intent_score`
- `signals.long_term_stability_score`
- `signals.novelty_score`
- `signals.temporary_risk_score`
- `signals.assistant_inference_risk_score`
- `signals.duplicate_risk_score`
- `signals.source_ref_confidence_score`

这些字段只用于实验观测，不参与真实 `memorize` 写入决策。

运行态 smoke 重点检查：

- `session_key`
- `turn_id`
- `baseline_result.attempted_count`
- `baseline_result.baseline_written_count`
- `metrics_json.policy_allow_count`
- `metrics_json.policy_reject_count`

这些字段能证明实验记录来自真实工具调用结果，而不是单独构造的 runner 单元测试。跨 session smoke 还会检查普通 session 不会因为另一个 session 发生过显式 `memorize` 而多出写入价值 trace。

建议新增或扩展的数据出口：

- `memory_experiment_runs`
- `memory_policy_traces`
- `memory_retrieval_comparisons`
- `memory_version_chain_traces`
- `memory_sleep_jobs`
- `memory_provenance_traces`
- `memory_eval_results`

### 后续 6 步的测试数据

后续实验阶段必须能输出对比数据，不能只说明实现了某个能力：

| 阶段 | 主要能力 | 必须输出的数据 |
| --- | --- | --- |
| Phase 1b | 信息熵 / 新颖度 / 重复度评分 | `entropy_score`、`novelty_score`、`duplicate_risk_score`、`similar_memory_count`、`nearest_memory_ids`、`write_reduction_rate` |
| Phase 2a | 三路召回 + RRF shadow | `semantic_hit_count`、`keyword_hit_count`、`provenance_hit_count`、`fused_hit_count`、`semantic_ids`、`keyword_ids`、`provenance_ids`、`fused_ids`、`lane_contribution`、`lane_count`、`rerank_changed_count`、`baseline_experimental_overlap_rate`、`rrf_score_distribution`、`source_ref_coverage`、`retrieval_latency_ms`、`rrf_weights` |
| Phase 2b | NetworkX 实体图谱召回 | `graph_hit_count`、`graph_ids`、`graph_fused_ids`、`graph_path_count`、`avg_graph_path_length`、`entity_match_count`、`graph_lane_contribution`、`graph_score_distribution`、`retrieval_latency_ms`、`baseline_graph_overlap_rate` |
| Phase 3 | 召回重排和注入治理 | `raw_rank`、`experimental_rank`、`rank_delta`、`score_breakdown`、`rerank_changed_count`、`baseline_experimental_overlap_rate`、`drop_reason`、`inject_reason`、`baseline_injected_ids`、`experimental_injected_ids`、`prompt_token_delta` |
| Phase 4 | 因果一致性版本链和层级化溯源 | `replacement_count`、`chain_count`、`avg_chain_depth`、`max_chain_depth`、`active_leaf_count`、`stale_recalled_count`、`superseded_recalled_count`、`rollback_candidate_count`、`conflict_chain_count`、`orphan_replacement_count`、`source_ref_coverage`、`parse_success_rate`、`source_ref_parse_success_rate`、`session_level_source_count`、`message_level_source_count`、`span_level_source_count`、`malformed_source_ref_count`、`orphan_memory_count`、`cross_scope_memory_count`、`cross_scope_risk_count` |
| Phase 5 | 离线睡眠巩固 shadow dry-run | `scanned_count`、`duplicate_group_count`、`duplicate_item_count`、`merge_candidate_count`、`stale_candidate_count`、`low_value_candidate_count`、`conflict_candidate_count`、`missing_source_ref_count`、`estimated_token_saving`、`estimated_redundancy_drop`、`job_latency_ms`、`applied_change_count`、`duplicate_group_truncated_count`、`merge_candidate_truncated_count`、`conflict_candidate_truncated_count`、`stale_candidate_truncated_count`、`low_value_candidate_truncated_count` |
| Phase 6a-1 | 评测集 schema 和静态 fixture | `phase_targets`、`config_profiles`、`should_recall_ids`、`should_not_recall_ids`、`expected_trace_features`、`expected_metric_keys`、`profile_expectations` |
| Phase 6a-2 | 离线 runner 和 profile 对照报告 | `case_count`、`profile_count`、`passed_case_count`、`failed_case_count`、`failed_profile_count`、`trace_count`、`trace_count_by_feature`、`profile_pass_rate` |
| Phase 6b-1 | 真实 memory 只读采样和候选指标 | `sample_count`、`memory_item_count`、`replacement_count`、`category_counts`、`labelled_contract_pass_rate`、`candidate_hit_rate_without_label_forcing`、`candidate_wrong_scope_count`、`candidate_labelled_wrong_scope_count`、`sample_records`、`profile_records`、`candidate_records`、`failure_records`、`invalid_extra_json_count`、`missing_scope_count`、`missing_table_count` |
| Phase 6b-2 | 真实 AgentLoop dry-run | `agent_loop_enabled`、`fake_llm_enabled`、`llm_calls_enabled`、`embedding_calls_enabled`、`answer_quality_available`、`agent_turn_count`、`retrieval_request_count`、`fake_llm_call_count`、`turn_committed_count`、`session_message_count`、`retrieval_query_matched`、`retrieval_history_seen` |
| Phase 6b-3 | 答案级小样本评测和真实 LLM 显式门控 | `answer_quality_available`、`answer_contains_pass_count`、`answer_contains_miss_count`、`forbidden_contains_violation_count`、`expected_memory_used_count`、`language_pass_count`、`provider_error_count`、`timeout_count`、`token_metrics_available`、`prompt_token_count`、`completion_token_count`、`total_token_count`、`total_latency_ms`、`avg_latency_ms` |
| Phase 6c-1 | 离线 uplift proxy report | `overall_avg_uplift`、`phase_summaries`、`feature_records`、`positive_signal_count`、`negative_signal_count`、`total_token_delta`、`estimated_token_saving` |
| Phase 6d | 80 case 量化 uplift 总表和链路评测 | `baseline_main_score`、`all_on_main_score`、`total_uplift_points`、`total_chain_uplift_points`、`chain_step_count`、`strongest_step`、`weakest_step`、`common_final_main_score`、`hard_final_main_score` |
| Phase 6 后续 | Dashboard、连续真实样本评测和 active 化决策 | `recall_at_k`、`precision_at_k`、`wrong_recall_rate`、`memory_pollution_rate`、`compression_ratio`、`source_support_rate` |

其中 Phase 1b 到 Phase 5 默认仍然是 shadow 或 dry-run。只有 Phase 6 的评测数据稳定后，才讨论把某些策略切到 active。

Phase 1b 已补充写入候选和已有 active 记忆的只读对比。当前实现先使用词元重叠近似计算，不调用 embedding 或外部服务：

- `signals.entropy_score`
- `signals.novelty_score`
- `signals.duplicate_risk_score`
- `similar_memory_count`
- `nearest_memory_ids`
- `metrics_json.existing_memory_count`
- `metrics_json.existing_memory_snapshot_count`
- `metrics_json.avg_entropy_score`
- `metrics_json.avg_novelty_score`
- `metrics_json.written_candidate_allow_count`
- `metrics_json.write_reduction_rate`

这些字段仍然只用于 shadow 实验，不影响真实 `memorize` 写入。本轮真实写入产生的 `item_id` 会从已有记忆快照里排除，避免候选和自己匹配导致重复风险失真。

当前 `entropy_score` 和 `novelty_score` 都来自“候选和已有记忆最大词元重叠相似度”的近似计算，可先用于实验对比，不等价于真正的信息论熵。`nearest_memory_ids` 只记录达到高相似阈值的近邻 id，用于解释重复风险；低相似候选不会进入该列表。`existing_memory_count` / `existing_memory_snapshot_count` 表示本次 shadow scoring 实际读取并参与比较的 active 记忆快照数量，不代表库中全部 active 记忆总数。

Phase 4a/4b 已补充版本链和层级溯源 shadow 指标：

- `stale_recalled_count > 0` 表示 baseline 可能召回了已经被替换的旧记忆。
- `conflict_chain_count > 0` 表示同一 replacement 图存在多个 active 叶子，后续 active 化前必须审查。
- `rollback_candidate_count` 表示当前 active leaf 背后可以回退的旧版本数量。
- `source_ref_coverage` 越低，说明记忆可解释性越差。
- `parse_success_rate` / `source_ref_parse_success_rate` 衡量现有 `source_ref` 是否能解析成 session/message/span 层级。
- `orphan_memory_count` 表示缺少来源的记忆数量。
- `cross_scope_memory_count` 表示扫描快照里存在其他 channel/chat 的来源。
- `cross_scope_risk_count` 表示当前会话真实召回项可能混入其他 channel/chat 的来源。

Phase 5 已补充离线睡眠巩固 shadow dry-run 指标：

- `scanned_count`：本次扫描的 active memory 数量。
- `duplicate_group_count`：高度相似的重复组数量。
- `duplicate_item_count`：参与重复组的记忆数量。
- `merge_candidate_count`：同类、同 scope、语义接近但未达到重复阈值的候选数量。
- `stale_candidate_count`：更新时间较久、强化次数低、情绪权重低的候选数量。
- `low_value_candidate_count`：过期且偏临时/事件型的候选数量。
- `conflict_candidate_count`：同一偏好方向存在相反表达的候选数量。
- `missing_source_ref_count`：缺少来源引用的记忆数量。
- `estimated_token_saving`：如果后续合并/清理候选，预计可减少的 token 量。
- `estimated_redundancy_drop`：重复项占扫描集合的比例。
- `job_latency_ms`：本次 shadow job 耗时。
- `applied_change_count`：第一版固定为 0，表示没有真实副作用。
- `duplicate_group_truncated_count`：因 trace 输出上限被截断的重复组数量。
- `merge_candidate_truncated_count`：因 trace 输出上限被截断的可合并候选数量。
- `conflict_candidate_truncated_count`：因 trace 输出上限被截断的冲突候选数量。
- `stale_candidate_truncated_count`：因 trace 输出上限被截断的过期候选数量。
- `low_value_candidate_truncated_count`：因 trace 输出上限被截断的低价值候选数量。

这些字段由 `sleep_consolidation_shadow` trace 输出。第一版只在 memory consolidation 事件后做有界扫描，不执行合并、删除、supersede 或 active 清理。

Phase 6a-1 已补充评测集 schema 和静态 fixture：

- `EVAL_CONFIG_PROFILES` 固定配置 profile：`off`、`phase1`、`phase2`、`phase3`、`phase4`、`phase5`、`all`。
- `EVAL_PHASE_TARGETS` 固定评测阶段：`phase1`、`phase2a`、`phase2b`、`phase3a`、`phase3b`、`phase4a`、`phase4b`、`phase5`。
- `EVAL_CONFIG_MATRIX` 把 profile 映射到真实 `memory_experiments` 开关，后续 runner 可以直接用它构造 off/on 对照。
- 9 个 fixture 覆盖写入价值、三路召回、图谱召回、重排、注入治理、版本链、溯源、睡眠巩固和跨 scope 隔离。
- 本阶段不计算真实 `recall_at_k` 或 `precision_at_k`，只为后续 runner 准备可复用、可校验的输入和期望字段。

Phase 6a-2 已补充离线 profile runner：

- `run_eval_case()`：运行单个 `EvalCase` 的全部 `config_profiles`。
- `run_eval_cases()`：运行一组 case 并聚合 `EvalRunReport.metrics`。
- `run_eval_case_files()`：从 fixture 目录加载并运行。
- `write_eval_report()`：把 report 写成稳定 JSON，供后续 Dashboard 或人工审阅使用。
- runner 会把 `tri_retrieval` / `graph_retrieval` 中位于 `experimental_result` 的 hit count 归一化到 `EvalTrace.metrics`，让 fixture 的 `expected_metric_keys` 可以统一校验。
- `sleep_consolidation_shadow` 使用固定时间并归一化 `job_latency_ms`，避免离线报告受当前时间或运行耗时影响。

当前 Phase 4b 不执行真实 `fetch_messages` 回源，所以 `fetch_success_rate`、`evidence_precision`、`source_support_rate` 仍然不能由本阶段 trace 直接给出，需要后续回源评测或标注集。

Phase 6b-1 已补充真实 memory 只读采样和报告链路：

- `collect_real_memory_samples()` 从真实 `workspace/memory/memory2.db` 中采样 preference、procedure、cross_scope、version_chain 类样本。
- `real_sample_to_eval_case()` 把真实样本转换成 Phase 6a-2 runner 可消费的 `EvalCase`。
- `evaluate_unforced_candidates()` 计算不使用 `should_recall_ids` 强制命中的候选指标。
- `build_real_eval_summary()` 汇总真实样本、labelled contract 和 unforced candidate 三类结果。
- `scripts/run_memory_real_sample_eval.py` 输出 `memory_real_sample_eval.json` 和 `memory_real_sample_eval.md`。
- 报告增加 `sample_records`、`profile_records`、`candidate_records` 和 `failure_records`，用于回查每个指标来自哪个样本、哪个 profile 和哪个候选集合；这些字段默认只写 id、scope、指标和失败原因，不写真实记忆正文。

本阶段明确不提供答案级质量指标：

- `llm_calls_enabled = false`
- `answer_quality_available = false`
- 不统计最终回答是否正确使用记忆。
- 不统计 source support 或 answer grounding。

本机实跑时缺少 `workspace/memory/memory2.db`，所以报告是降级报告：`sample_count = 0`、`missing_table_count = 1`、`profile_count = 0`、`trace_count = 0`。这说明 CLI 的缺库路径可观测，但还没有真实 memory 样本的效果数据。

Phase 1b 的测试结论：

- focused suite：`30 passed`。
- live smoke：`3 passed`。
- `compileall`：通过。
- `git diff --check`：通过。
- live smoke 出现的 Python 3.14 asyncio transport 析构 warning 不影响测试通过结论，但后续如果要收敛测试噪音，可以单独处理。

Phase 2a 的指标重点会从“写入候选质量”转向“召回候选来源”。其中 RRF 融合适合三路分数不可直接相加的情况：语义召回有向量相似度，关键词召回有关键词命中分，溯源召回有 source_ref、scope、模糊指代和文本重叠线索，统一用每一路内部排名做融合更稳。

Phase 2a 已实现后，`tri_retrieval` trace 应包含：

- `baseline_result.baseline_ids`
- `experimental_result.semantic_ids`
- `experimental_result.keyword_ids`
- `experimental_result.provenance_ids`
- `experimental_result.fused_ids`
- `experimental_result.fused_items[].rrf_score`
- `experimental_result.fused_items[].lane_hits`
- `metrics_json.lane_contribution`
- `metrics_json.lane_count`
- `metrics_json.rerank_changed_count`
- `metrics_json.baseline_experimental_overlap_rate`
- `metrics_json.rrf_score_distribution`
- `metrics_json.source_ref_coverage`
- `metrics_json.retrieval_latency_ms`
- `metrics_json.rrf_weights`

Phase 2a 不使用 NetworkX，不调用真实 fetch 回源，不改变真实召回和 prompt 注入。`fetch_success_rate` 留到后续真正执行回源增强时再统计。

Phase 2a 的测试结论：

- focused suite：`46 passed`。
- broader memory experiment suite：`51 passed`。
- `compileall`：通过。
- `git diff --check`：通过。

Phase 2b 已实现后，`graph_retrieval` trace 应包含：

- `baseline_result.baseline_ids`
- `baseline_result.baseline_fused_ids`
- `experimental_result.graph_ids`
- `experimental_result.graph_fused_ids`
- `experimental_result.graph_fused_items[].graph_score`
- `experimental_result.graph_fused_items[].graph_path_length`
- `metrics_json.graph_lane_contribution`
- `metrics_json.graph_path_count`
- `metrics_json.avg_graph_path_length`
- `metrics_json.entity_match_count`
- `metrics_json.graph_score_distribution`
- `metrics_json.retrieval_latency_ms`
- `metrics_json.baseline_graph_overlap_rate`

Phase 2b 只记录 graph shadow，不改变真实召回和 prompt 注入。真实 `fetch_messages` 回源、`fetch_success_rate` 和基于评测集的 active 化决策仍留到后续阶段。

Phase 2b 的测试结论：

- focused suite：`56 passed`。
- broader memory experiment suite：`77 passed`。
- `compileall`：通过。
- `git diff --check`：通过。

## Phase 3 可输出的指标

### 召回重排

- `baseline_ids`
- `reranked_ids`
- `raw_rank`
- `experimental_rank`
- `rank_delta`
- `score_breakdown`
- `rerank_changed_count`
- `baseline_experimental_overlap_rate`
- `avg_experimental_score`
- `scope_match_count`
- `source_ref_count`

### 注入治理

- `baseline_injected_ids`
- `baseline_injected_count`
- `experimental_injected_ids`
- `experimental_injected_count`
- `drop_reasons`
- `inject_reasons`
- `prompt_token_delta`
- `low_confidence_injected_count`
- `dropped_count`
- `newly_injected_count`
- `removed_from_injection_count`

### P0：直接建立基线

- active / superseded 数量。
- memory_type 分布。
- source_ref 覆盖率。
- injected_count 分布。
- hit score 分布。
- prompt token 成本。

### P1：新增埋点

- consolidation 压缩率。
- retrieval latency。
- 写入门控通过率。
- 拒绝原因分布。

### P2：评测集

- Recall@K。
- Precision@K。
- MRR。
- 记忆污染率。
- 纠错成功率。

## 三层评分口径

当前项目已经可以把记忆评测拆成三层：

- 即时回答评分：看 `answer_rule_pass_rate`、`memory_grounding_pass_rate` 和 `forbidden_violation_rate`，主要反映当前回答是否命中。
- 写入治理评分：看 `policy_reject_count`、`policy_review_count`、`duplicate_risk_count`、`temporary_risk_count`、`assistant_inference_risk_count` 和 `write_reduction_rate`，主要反映写入是否干净、是否少污染。
- 记忆库卫生评分：看 `scanned_count`、`missing_source_ref_count`、`stale_candidate_count`、`duplicate_group_count`、`merge_candidate_count`、`conflict_candidate_count`、`low_value_candidate_count` 和 `estimated_token_saving`，主要反映睡眠巩固后记忆库是否更健康。

当前离线报表路径：

- `my_md/memory_optimization/eval_reports/memory_layered_scoring_eval.json`
- `my_md/memory_optimization/eval_reports/memory_layered_scoring_eval.md`

当前离线结果：

- `baseline_total_layered_score = 94.375`
- `final_total_layered_score = 54.9521`
- `total_layered_uplift_points = -39.4229`
- `chain_all_on` 的写入治理分 `49.3334`
- `chain_all_on` 的记忆库卫生分 `35.4107`

这组数值的含义不是“生产准确率”，而是说明写入和巩固类能力应当独立评价，不能只靠回答分数判断好坏。

## 面试表达

```text
记忆优化不能只说“召回更准了”，必须能测。我们当前已经能从 memory2.db 和 observe.db 直接测记忆规模、写入量、强化比例、superseded 比例、source_ref 覆盖率、召回 hit 数、注入数量、score 分布和 prompt token 成本。下一步需要补 consolidation 压缩率、检索延迟、写入门控通过率和回源成功率。真正的准确率、污染率和纠错成功率不能只看日志，必须建立 memory eval 标注集。
```
