# Memory Plugin Experiment Roadmap

## 目标

这份文档把图片中提到的记忆能力，转成 `akashic-agent` memory 插件的可实验扩展路线。

核心要求不是“直接宣称已经实现”，而是每个方向都必须满足：

- 有独立配置开关。
- 能先以 shadow / dry-run 方式运行，不影响真实对话。
- 能同时记录 baseline 和 experimental 的结果。
- 能输出可比较的测试数据。
- 数据稳定后，再决定是否切到 active。

## 总体原则

### 1. 默认不影响真实链路

新增能力默认不改变真实写入、真实召回和真实 prompt 注入。先把实验结果写入 observe 或 eval report。

### 2. 每项能力都有对照数据

不能只记录“新方案跑了什么”，还要记录“旧方案跑了什么”。否则无法判断优化是否有效。

### 3. 先 shadow，再 active

推荐模式：

```text
off
  -> shadow
  -> active
  -> ab
```

- `off`：完全关闭。
- `shadow`：实验逻辑旁路运行，只记录数据，不影响真实链路。
- `active`：实验逻辑参与真实写入、召回或巩固。
- `ab`：按 session 或 turn 分组，一部分走旧逻辑，一部分走新逻辑。

## 建议配置

```toml
[memory_experiments]
enabled = true
mode = "shadow"   # off | shadow | active | ab
trace_enabled = true
dashboard_enabled = true
eval_report_dir = "my_md/memory_optimization/eval_reports"

[memory_experiments.version_chain]
enabled = true
mode = "shadow"

[memory_experiments.write_value_score]
enabled = true
mode = "shadow"

[memory_experiments.tri_retrieval]
enabled = true
mode = "shadow"

[memory_experiments.rerank_injection]
enabled = true
mode = "shadow"

[memory_experiments.sleep_consolidation]
enabled = true
dry_run = true
interval_seconds = 10800

[memory_experiments.provenance]
enabled = true
mode = "shadow"
span_level = true
```

第一版可以先放在 `plugins/default_memory/config.local.toml` 或新增 memory governance 插件配置中。正式产品化后，再考虑并入主配置。

## 方案选择

推荐采用：

```text
memory_governance 实验插件
  + default_memory / memory2 少量接口扩展
```

原因：

- 实验开关、数据记录、Dashboard 展示放在独立插件里，边界清楚。
- 真正影响写入、召回、重排的位置仍由 `default_memory` 和 `memory2` 承接。
- 不需要改 `AgentLoop`，主循环仍只通过 `MemoryRuntime`、事件和工具使用记忆。

不推荐一开始把所有逻辑直接塞进 `memory2`，否则很难区分当前能力、实验能力和已验证能力。

## 1. 因果一致性版本链表

### 目的

把当前 `superseded` 和 `memory_replacements` 扩展成可追踪的记忆版本链，用于纠错、替换、回滚和解释。

### 当前基础

项目已经有：

- `memory_items.status`
- `memory_replacements`
- `source_ref`
- `forget_memory`

这些能表示“旧记忆失效了”，但还不是完整版本链。

### 扩展字段

```text
chain_id
parent_item_id
revision_no
relation_type
causal_source_ref
decision_reason
```

示例：

```text
mem_v1 -> mem_v2 -> mem_v3
```

### 输出数据

- `replacement_count`：替换次数。
- `chain_count`：版本链数量。
- `avg_chain_depth`：平均链深度。
- `rollback_candidates`：可回滚候选数。
- `stale_recalled_count`：旧版本被误召回次数。
- `conflict_chain_count`：存在冲突的版本链数量。

### 对照方式

```text
baseline：只看 active / superseded 状态
experimental：使用完整 version chain 判断当前有效版本
```

## 2. 信息熵和内容价值评分

### 目的

写入长期记忆前，判断一轮对话值不值得记，减少临时信息、重复信息和 assistant 推断污染长期记忆。

### 扩展模块

```text
MemoryWritePolicy
MemoryValueScorer
```

### 评分信号

- 是否用户明确表达。
- 是否长期稳定。
- 是否包含新实体、新偏好、新约束。
- 是否和旧记忆重复。
- 是否只是临时状态。
- 是否只是 assistant 推断。
- 是否有 `source_ref`。

这里的信息熵可以理解为“新增信息量”：和已有记忆高度重复时分数低，改变长期偏好或重要事实时分数高。

### 输出数据

- `candidate_count`：候选记忆数。
- `baseline_written_count`：旧逻辑写入数。
- `policy_allow_count`：新策略建议写入数。
- `policy_reject_count`：新策略建议拒绝数。
- `reject_reason_distribution`：拒绝原因分布。
- `avg_entropy_score`：平均信息价值分。
- `duplicate_risk_count`：重复风险数量。
- `temporary_reject_count`：临时信息拒写数量。
- `assistant_inference_reject_count`：assistant 推断拒写数量。

### 补充评测后可测

- `memory_pollution_rate`：记忆污染率。
- `useful_memory_precision`：有效记忆精度。
- `write_reduction_rate`：写入减少比例。
- `future_recall_usefulness`：后续召回有用率。

## 3. 三路召回方案

### 目的

三路召回不是“多搜几次”，而是把不同证据来源分开记录、融合、评测。

### 三路定义

```text
第一路：语义召回
  -> memory2 vector

第二路：关键词召回
  -> memory2 keyword / search_messages

第三路：溯源召回
  -> Phase 2a: source_ref / scope / 模糊指代 / 文本重叠
  -> 后续阶段: fetch_messages / 时间线索 / 图谱线索
```

当前项目已经有向量召回、关键词召回、RRF 融合、`recall_memory`、`search_messages`、`fetch_messages` 和 `source_ref` 回源。Phase 2a 只把三路候选和 RRF 融合结果显式记录下来；真实 `fetch_messages` 回源、时间线索增强和注入决策治理留到后续阶段。

### 输出数据

- `semantic_hit_count`：语义召回数量。
- `keyword_hit_count`：关键词召回数量。
- `provenance_hit_count`：溯源召回数量。
- `fused_hit_count`：融合后数量。
- `lane_contribution`：每一路对最终结果的贡献。
- `rerank_changed_count`：重排改变名次次数。
- `dropped_by_reason`：候选被丢弃原因。
- `injected_count`：最终注入数量。
- `retrieval_latency_ms`：召回耗时。
- `fetch_success_rate`：回源成功率，Phase 2a 不统计，留到真实回源增强阶段。

### 补充评测后可测

- `recall_at_k`
- `precision_at_k`
- `wrong_recall_rate`
- `evidence_hit_rate`
- `answer_grounding_rate`

### 对照方式

```text
baseline：当前 vector + keyword + RRF
experimental：Phase 2a 为三路候选 + RRF shadow；质量重排和回源增强属于后续阶段
```

## 4. 召回重排和注入治理

### 目的

三路召回只解决“候选从哪里来”，重排和注入治理解决“哪些候选真正进入 prompt”。

### 重排信号

```text
semantic_score
keyword_score
scope_match
source_ref_present
confidence
importance
reinforcement
recency
staleness
version_current
conflict_penalty
```

### 输出数据

- `raw_rank`
- `experimental_rank`
- `rank_delta`
- `drop_reason`
- `baseline_injected`
- `experimental_injected`
- `prompt_token_delta`
- `low_confidence_injected_count`
- `stale_dropped_count`

### 对照方式

```text
baseline：当前注入筛选结果
experimental：重排和治理后的建议注入结果
```

## 5. 离线异步睡眠巩固守护进程

### 目的

后台定期做长期记忆卫生，不阻塞用户对话。

第一版必须是 dry-run：

```text
扫描 memory_items
  -> 找重复
  -> 找冲突
  -> 找过期
  -> 找可合并项
  -> 生成候选报告
  -> 写 observe
```

### 输出数据

- `scanned_count`：扫描记忆数。
- `duplicate_group_count`：重复组数量。
- `merge_candidate_count`：可合并候选数量。
- `stale_candidate_count`：过期候选数量。
- `low_value_candidate_count`：低价值候选数量。
- `conflict_candidate_count`：冲突候选数量。
- `missing_source_ref_count`：缺少来源引用数量。
- `estimated_token_saving`：预计节省 token。
- `estimated_redundancy_drop`：预计冗余下降。
- `job_latency_ms`：任务耗时。
- `applied_change_count`：真实执行修改数，第一版固定为 0。
- `duplicate_group_truncated_count`：因 trace 输出上限被截断的重复组数量。
- `merge_candidate_truncated_count`：因 trace 输出上限被截断的可合并候选数量。
- `conflict_candidate_truncated_count`：因 trace 输出上限被截断的冲突候选数量。
- `stale_candidate_truncated_count`：因 trace 输出上限被截断的过期候选数量。
- `low_value_candidate_truncated_count`：因 trace 输出上限被截断的低价值候选数量。

### active 后可测

- `before_active_count`
- `after_active_count`
- `compression_ratio`
- `post_consolidation_recall_precision`
- `post_consolidation_wrong_recall_rate`

## 6. 层级化溯源 scheme

### 目的

让每条记忆不仅能回到一个 `source_ref`，还可以逐层追到 session、turn、message，后续再扩展到原文片段。

### 当前基础

项目已经有：

- `session_key`
- message id
- `source_ref`
- `fetch_messages`
- `scope_channel`
- `scope_chat_id`

### 扩展层级

```text
session_key
  -> turn_id
  -> message_id
  -> span_start / span_end
  -> memory_item_id
  -> chain_id
  -> derived_from
```

### 输出数据

- `source_ref_coverage`：有 source_ref 的记忆比例。
- `parse_success_rate`：现有 source_ref 可解析比例。
- `session_level_source_count` / `message_level_source_count` / `span_level_source_count`：来源层级数量。
- `orphan_memory_count`：无来源记忆数量。
- `cross_scope_memory_count`：扫描快照里的跨 scope 来源数量。
- `cross_scope_risk_count`：本轮真实召回项里的跨 scope 风险数量。

### 补充评测后可测

- `span_coverage`
- `fetch_success_rate`
- `evidence_precision`
- `citation_correctness`
- `source_support_rate`
- `unsupported_memory_rate`

## 统一数据出口

建议新增实验观测表或 jsonl：

```text
memory_experiment_runs
memory_policy_traces
memory_retrieval_comparisons
memory_version_chain_traces
memory_sleep_jobs
memory_provenance_traces
memory_eval_results
```

每条记录统一带：

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

这样 Dashboard 可以展示：

- baseline 召回了什么。
- experimental 召回了什么。
- 两者差异是什么。
- 实验方案是否更准。
- 是否增加延迟。
- 是否减少 token。
- 是否存在误拒、误删、误召回。

## 大致阶段

当前执行位置：

```text
Phase 0   已完成：实验框架、配置开关、shadow trace、运行态 smoke
Phase 1a  已完成：显式 memorize 的写入价值结构化 shadow scoring
Phase 1b  已完成：信息熵 / 新颖度 / 重复度评分
Phase 2a  已完成：三路召回 + RRF 融合 shadow
Phase 2b  已完成：NetworkX 实体图谱 graph shadow
Phase 3a  已完成：召回质量重排 shadow
Phase 3b  已完成：注入治理 shadow
Phase 4a  已完成：因果一致性版本链 shadow
Phase 4b  已完成：层级化溯源 shadow
Phase 5   已完成第一版：离线睡眠巩固 shadow dry-run
Phase 6   待做：评测集、Dashboard 和 active 化决策
```

后续计划按 6 个主要步骤推进。trace 汇总报告属于数据出口和验证手段，不单独替代某个 memory 能力阶段。

### Phase 0：实验框架和开关

- 增加 `memory_experiments` 配置。
- 支持 `off / shadow / active / ab`。
- 建立 baseline vs experimental 数据记录。

## Phase 0 实施说明

第一版实现范围限定为：

- 解析 `memory_experiments` 配置。
- 支持 `off` 和 `shadow`。
- 写入 `workspace/observe/memory_experiments.jsonl`。
- 在 post-response memory worker 中记录显式 `memorize` 的写入价值评分 shadow trace。

第一版不改变真实写入、真实召回、真实 prompt 注入，也不启用 `active` 或 `ab` 行为。

### 运行态验证

Phase 0 需要通过 live smoke 验证：

- 真实启动 `main.py`。
- 通过 IPC v2 发送用户消息。
- fake LLM 返回 `memorize` 工具调用。
- 真实 `memorize` 工具完成写入。
- post-response worker 写出 `write_value_score` trace。
- 跨 session 场景下，只在发生显式 `memorize` 的 session 记录写入价值 trace。

验证通过只能说明 shadow trace 链路可用，不代表写入价值评分已经参与真实写入决策。

### Phase 1：写入价值评分 shadow

- 增加信息熵、新颖度、稳定性、`source_ref` 可信度评分。
- 只旁路打分，不影响真实写入。
- 输出写入减少率、拒写原因和污染风险数据。

第一步先增强显式 `memorize` 的 shadow scoring：

- 对每条候选记忆输出结构化 signals。
- 汇总 allow / reject / review 数量。
- 记录临时信息风险、assistant 推断风险和重复风险。
- 保持真实写入结果不变，等 trace 数据足够后再讨论 active。

Phase 1b 要补的不是单纯报告，而是让评分真正参考已有记忆：

- `entropy_score`：候选相对已有记忆的新增信息量。
- `novelty_score`：是否包含新的偏好、实体、规则或长期约束。
- `duplicate_risk_score`：和已有记忆重复或近似重复的风险。
- `similar_memory_count`：相似已有记忆数量。
- `nearest_memory_ids`：最相似的已有记忆 id。
- `write_reduction_rate`：shadow 策略相对真实写入的预计减少比例。

当前 Phase 1b 已按 shadow-only 落地第一版：`MemoryExperimentRunner` 只读 active memory summary 快照，用词元重叠近似计算信息熵、新颖度和重复风险，并从快照中排除本轮真实写入的 `item_id`，避免候选和自己匹配。这里的 `entropy_score` 和 `novelty_score` 当前同源，都是基于“最大词元重叠相似度”的近似值；`nearest_memory_ids` 只表示达到高相似阈值的近邻。Phase 1b 仍然只写实验 trace，不改变真实 `memorize` 写入。

Phase 1b 验证结论：

- focused suite：`30 passed`。
- live smoke：`3 passed`。
- `compileall` 和 `git diff --check` 通过。
- live smoke 出现过 Python 3.14 asyncio transport 析构 warning，但测试结果通过。

### Phase 2：三路召回 shadow

- 第一路：语义召回，`memory2 vector`。
- 第二路：关键词召回，`memory2 keyword / search_messages`。
- 第三路：溯源召回，Phase 2a 只使用 `source_ref`、scope、模糊指代和文本重叠线索；真实 `fetch_messages` 回源和时间线索留到后续阶段。
- 同时跑旧召回和三路召回，对比命中、排序、注入差异。
- 输出 `lane_contribution`、`precision_at_k`、`recall_at_k`、`wrong_recall_rate`、`evidence_hit_rate`、`latency_ms`。

Phase 2 拆成两步推进：

1. Phase 2a：先做三路召回 + RRF 融合 shadow。第三路只使用已有的 source_ref、scope、模糊指代和文本重叠线索，不引入图谱依赖，也不执行真实回源。输出每一路命中数、RRF 融合结果、lane contribution 和延迟。
2. Phase 2b：在第三路中加入 NetworkX 实体图谱，把 MemoryItem、Entity、Session、SourceRef、Topic 连接起来，提升“那个、上次、之前说的方案”等模糊指代场景的召回准确率。当前已按 shadow-only 落地，不改变真实召回和 prompt 注入。

Phase 2a 已按 shadow-only 落地第一版：

- `Retriever.retrieve()` 仍返回当前 baseline 融合结果。
- 新增 `retrieve_with_lanes()`，在同一次召回中暴露语义 lane 和关键词 lane，避免额外 embedding 调用。
- 第三路 provenance lane 只使用 active memory 快照里的 `source_ref`、scope 和模糊指代线索，不引入 NetworkX。
- `DefaultMemoryEngine.retrieve()` 在实验开关启用时记录 `tri_retrieval` trace，但真实注入仍使用 baseline items。
- trace 输出 `semantic_ids`、`keyword_ids`、`provenance_ids`、`fused_ids`、`lane_contribution`、`lane_count`、`rerank_changed_count`、`baseline_experimental_overlap_rate`、`source_ref_coverage`、`retrieval_latency_ms` 和 `rrf_weights`。

Phase 2a 不改变真实召回结果，只记录 baseline 和 experimental 的差异；RRF 结果先用于观测，不参与 prompt 注入。

Phase 2b 已按 shadow-only 落地：

- 新增 `memory_experiments.graph_retrieval_enabled`、`graph_retrieval_max_nodes`、`graph_retrieval_max_hops`。
- 新增 NetworkX graph lane，从 active memory 的 summary、active topics、scope 和 source_ref 建实体图。
- `DefaultMemoryEngine.retrieve()` 仍返回 baseline hits，只在启用 graph shadow 时额外记录 `graph_retrieval` trace。
- `graph_retrieval` trace 输出 `graph_ids`、`graph_fused_ids`、`graph_fused_items`、`graph_path_count`、`avg_graph_path_length`、`entity_match_count`、`graph_score_distribution`、`retrieval_latency_ms` 和 `baseline_graph_overlap_rate`。
- 真实 fetch 回源、`fetch_success_rate` 和 graph 结果 active 化仍留到后续阶段。

Phase 2a 验证结论：

- focused suite：`46 passed`。
- broader memory experiment suite：`51 passed`。
- `compileall` 和 `git diff --check` 通过。

Phase 2b 验证结论：

- focused suite：`56 passed`。
- broader memory experiment suite：`77 passed`。
- `compileall` 和 `git diff --check` 通过。

### Phase 3：召回重排和注入治理

- Phase 3a 已完成：召回质量重排 shadow。
- Phase 3b 已完成：注入治理 shadow。

- 在三路召回候选上做统一重排。
- 加入 scope、`source_ref`、质量分、版本链、过期状态。
- 输出 `rerank_changed_count`、`drop_reason`、`injected_count`、prompt token 变化。

### Phase 4：版本链和层级溯源

Phase 4a 已完成：因果一致性版本链 shadow。

- 只读取 `memory_items.status`、`memory_replacements` 和本轮 baseline recalled items。
- 版本链只统计参与 replacement 图的条目，不把普通 active 单点记忆计入 `chain_count`。
- 输出 `replacement_count`、`chain_count`、`avg_chain_depth`、`max_chain_depth`、`active_leaf_count`、`stale_recalled_count`、`superseded_recalled_count`、`rollback_candidate_count`、`conflict_chain_count`、`orphan_replacement_count`。
- 不改变真实写入、真实召回和真实 prompt 注入。

Phase 4b 已完成：层级化溯源 shadow。

- 第一版只解析现有 `source_ref`，不执行真实 `fetch_messages` 回源。
- 支持解析 message id JSON、`@post_response` session ref、`channel:chat:message` 和 `channel:chat` 这几类现有格式。
- 输出 `source_ref_coverage`、`parse_success_rate`、`source_ref_parse_success_rate`、`message_level_source_count`、`session_level_source_count`、`span_level_source_count`、`malformed_source_ref_count`、`orphan_memory_count`、`cross_scope_memory_count`、`cross_scope_risk_count`。
- `cross_scope_memory_count` 面向扫描快照，`cross_scope_risk_count` 面向本轮真实召回项。
- `fetch_success_rate`、`evidence_precision` 和 `source_support_rate` 留到后续带回源评测阶段。

Phase 4a/4b 验证结论：

- focused Phase 4 suite：`45 passed`。
- 版本链纯函数、溯源纯函数、实验 trace writer 和 engine contract 回归均通过。
- 仍然是 shadow-only，不改变真实写入、真实召回、真实 `recall_memory` 工具结果和 prompt 注入。

### Phase 5：离线异步睡眠巩固

Phase 5 已完成第一版：离线睡眠巩固 shadow dry-run。

- 在 `ConsolidationCommitted` 事件处理后执行有界 active memory 扫描。
- 输出重复组、可合并候选、过期候选、低价值候选、冲突候选和缺失 `source_ref` 数量。
- 输出预计 token 节省、预计冗余下降、任务耗时和候选截断数量。
- 只写 `sleep_consolidation_shadow` trace，不合并、不删除、不 supersede、不修改真实召回和 prompt 注入。
- 冲突候选会先于重复/合并候选识别，避免“喜欢”和“不喜欢”这类相反偏好被误当成可合并重复项。
- 第一版不是常驻后台守护进程；是否做 scheduler / daemon 留到 active 化前评估。

Phase 5 验证结论：

- 提交：`3492cf2 feat: add memory sleep consolidation shadow experiment`。
- sleep consolidation 纯函数测试覆盖重复、可合并、过期、低价值、冲突、缺失来源、trace 截断，以及“两个负向偏好不误判为冲突”的场景。
- 配置、trace writer 和 engine shadow 挂点测试通过。
- focused suite：`49 passed`。
- broader memory suite：`151 passed, 3 skipped, 1 warning`。
- full pytest：`1930 passed, 3 skipped, 3 warnings`。
- `compileall` 和 `git diff --check`：通过。
- 当前仍是 shadow-only / dry-run，不改变真实写入、真实召回、真实 `recall_memory` 工具结果和 prompt 注入。

### Phase 6：评测集和 Dashboard

- 固定 memory eval。
- 展示 baseline / experimental 对照。
- 输出准确率、召回率、污染率、压缩率、回源成功率。

## 面试表达

```text
我会把图片里的记忆能力作为 memory 插件的实验扩展路线，而不是直接说已经实现。每个能力都有独立开关，先用 shadow 或 dry-run 跑旁路实验，不影响真实写入和召回，同时记录 baseline 和 experimental 的差异。比如写入价值评分会输出拒写原因和污染风险，三路召回会输出每一路贡献、准确率和回源命中，睡眠巩固会输出冗余下降和压缩率。等实验数据证明有效后，再把对应能力从 shadow 切到 active。
```
