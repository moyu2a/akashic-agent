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
Phase 6a-1 已完成第一版：评测集 schema 和 9 个静态 fixture
Phase 6a-2 已完成第一版：离线 eval runner 和 JSON report
Phase 6b-1 已完成第一版：真实 memory 只读采样、真实样本 EvalCase 转换、unforced candidate 指标和报告 CLI
Phase 6b-2 已完成第一版：真实 AgentLoop dry-run，fake LLM，临时 workspace
Phase 6b-3 已完成第一版：显式门控的 LLM 小样本答案级评测，fake-provider 报告链路
Phase 6b-4 已完成第一版：证据使用 debug、repeat 评测和 baseline/coached 真实 LLM 对照
Phase 6c-1 已完成第一版：离线 uplift report
Phase 6d   已完成第一版：80 case 量化 uplift 总表，输出 common/hard 双集和单项 / 总增益 JSON + Markdown
Phase 6   待做：Dashboard、连续评测和 active 化决策
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

Phase 6a-1 已完成第一版：评测集 schema 和静态 fixture。

- 新增 `memory2/eval_cases.py`，包含 `EvalCase`、`load_eval_case()`、`load_eval_cases()` 和 `validate_eval_case_payload()`。
- 固定 `EVAL_PHASE_TARGETS`：`phase1`、`phase2a`、`phase2b`、`phase3a`、`phase3b`、`phase4a`、`phase4b`、`phase5`。
- 固定 `EVAL_CONFIG_PROFILES`：`off`、`phase1`、`phase2`、`phase3`、`phase4`、`phase5`、`all`。
- 新增 `EVAL_CONFIG_MATRIX`，把 profile 映射到真实 `memory_experiments` 配置开关，后续 runner 可以基于同一个 case 跑关闭、单阶段开启和全量开启对照。
- 新增 `tests/fixtures/memory_eval_cases/`，第一批 9 个 case 覆盖偏好召回、临时信息污染、重复记忆、冲突记忆、图谱模糊召回、注入治理、跨 scope 隔离、过期记忆睡眠巩固和层级溯源。
- 新增 schema / fixture 校验测试，确保 case id 与文件名一致、phase target 与 profile 对应、期望召回 id 能在 setup 中找到、指标字段挂在已声明 trace feature 上。

当前 Phase 6a-1 不做这些事：

- 不实现 eval runner。
- 不启动 Agent。
- 不调用 LLM 或 embedding。
- 不写真实 memory DB。
- 不生成正式 eval report。
- 不改变真实写入、真实召回、真实 `recall_memory` 工具结果和 prompt 注入。

Phase 6a-1 验证结论：

- focused suite：`14 passed`。
- 当前结论是“评测 schema 和 fixture 可以稳定加载和校验”。真正的 off/on A/B 指标要等后续 runner 把同一批 case 跑过 `EVAL_CONFIG_MATRIX` 后才能产出。

Phase 6a-2 已完成第一版：离线 eval runner 和 JSON report。

- 新增 `memory2/eval_runner.py`，包含 `EvalTrace`、`EvalProfileResult`、`EvalCaseResult`、`EvalRunReport`。
- 新增 `run_eval_case()`、`run_eval_cases()`、`run_eval_case_files()` 和 `write_eval_report()`。
- runner 只消费 fixture 和已有 shadow 纯函数，不启动 Agent，不调用 LLM，不调用 embedding，不写真实 memory DB，也不写 observe DB。
- `off` profile 不产生 trace；单阶段 profile 和 `all` profile 只运行当前 case 声明过的 trace，避免无关 trace 噪音。
- runner 校验 required / forbidden trace、profile metric key、全局 expected metric key、应召回 id、不应召回 / 不应注入 id。
- `tri_retrieval`、`graph_retrieval`、`injection_governance_shadow` 的输出会归一化到 `EvalTrace.metrics`，让 fixture 可以统一校验指标字段。
- `sleep_consolidation_shadow` 使用固定时间并归一化 `job_latency_ms`，保证离线 report 可重复。

Phase 6a-2 验证结论：

- focused suite：`21 passed`。
- fixture 全量 report：`case_count = 9`、`profile_count = 30`、`passed_case_count = 9`、`failed_case_count = 0`、`failed_profile_count = 0`、`trace_count = 30`、`profile_pass_rate = 1.0`。
- 当前结论是“Phase 1-5 的 shadow trace 已经能在同一批离线 fixture 上做 off/on 对照”。这还不是生产准确率评测，也不能替代答案级 `recall_at_k`、`precision_at_k`、answer grounding 或 source support。

Phase 6b-1 已完成第一版：真实 memory 只读采样和真实样本报告。

- 新增 `memory2/eval_real_samples.py`，使用 raw sqlite read-only 连接读取真实 `workspace/memory/memory2.db`，并启用 `PRAGMA query_only=ON`。
- 不实例化 `MemoryStore2` 或 `SessionStore`，避免真实 DB 在评测过程中被初始化、迁移或写入。
- 采样 preference、procedure、cross_scope、version_chain 类真实 memory 样本，并转换成 Phase 6a-2 runner 可消费的 `EvalCase`。
- 新增 `memory2/eval_real_candidates.py`，计算 unforced candidate 指标，不把 `should_recall_ids` 强制注入候选结果。
- 新增 `memory2/eval_real_report.py` 和 `scripts/run_memory_real_sample_eval.py`，输出 `memory_real_sample_eval.json` 和 `memory_real_sample_eval.md`。
- 报告默认不包含真实 memory summary 或 session 原文，只输出 id、类别、scope、指标和失败原因。

Phase 6b-1 可输出的数据：

- `sample_count`
- `memory_item_count`
- `replacement_count`
- `category_counts`
- `labelled_contract_pass_rate`
- `labelled_should_not_violation_count`
- `candidate_hit_rate_without_label_forcing`
- `candidate_wrong_scope_count`
- `candidate_labelled_wrong_scope_count`
- `candidate_count_by_category`
- `sample_records`
- `profile_records`
- `candidate_records`
- `failure_records`
- `invalid_extra_json_count`
- `missing_scope_count`
- `missing_table_count`
- `cross_scope_sample_unavailable`

Phase 6b-1 不做这些事：

- 不启动 Agent。
- 不调用 LLM。
- 不调用 embedding。
- 不写真实 memory DB、session DB 或 observe DB。
- 不统计最终回答质量、answer grounding 或 source support。

Phase 6b-1 验证结论：

- 初版 focused Phase6b suite：`16 passed`。
- 初版 Phase6a + Phase6b focused suite：`37 passed`。
- 本机实跑时当前工作区和主仓库都没有 `workspace/memory/memory2.db`，CLI 按预期生成降级报告并返回 exit code 1。
- 降级报告路径：`my_md/memory_optimization/eval_reports/memory_real_sample_eval.json` 和 `memory_real_sample_eval.md`。
- 降级报告摘要：`sample_count = 0`、`memory_item_count = 0`、`replacement_count = 0`、`missing_table_count = 1`、`cross_scope_sample_unavailable = 1`、`profile_count = 0`、`trace_count = 0`、`label_forced_recall = false`、`llm_calls_enabled = false`、`answer_quality_available = false`。
- 当前结论是“真实样本评测代码和报告链路已经具备；本机缺少真实 memory DB，所以还没有真实样本效果数据”。

审阅后修订：

- 报告已增加脱敏审计明细：`sample_records`、`profile_records`、`candidate_records`、`failure_records`。
- `cross_scope_sample_unavailable` 和 `version_chain_sample_unavailable` 改为按真实数据是否具备可采样对象计算，不再因为 `--limit-per-category 0` 误报 unavailable。
- `candidate_wrong_scope_count` 统计所有跨 scope 候选数量，`candidate_labelled_wrong_scope_count` 单独统计跨 scope 候选命中 `should_not_recall_ids` 的数量。
- 有真实 DB 且显式 `--limit-per-category 0` 时，CLI 作为 dry-run 返回 0；缺少真实 DB 时仍返回 1。
- 修订后 focused Phase6b suite：`19 passed`。
- 修订后 Phase6a + Phase6b focused suite：`40 passed`。

Phase 6 后续建议拆分：

Phase 6b-2 已完成第一版：真实 AgentLoop dry-run。

- 新增 `memory2/eval_agent_dry_run.py`，构造真实 `AgentLoop`、真实 `SessionManager`、真实 `DefaultMemoryRetrievalPipeline`、真实 `EventBus` 和受控 fake LLM / memory engine。
- 新增 `scripts/run_memory_agent_dry_run_eval.py`，读取 Phase 6a fixture，写出 `memory_agent_dry_run_eval.json` 和 `.md`。
- 每个 case 通过 `AgentLoop.process_direct()` 进入真实被动 turn pipeline。
- dry-run 会检查 retrieval request 的 query、scope 和 history 字段，并观察 `TurnCommitted`。
- 所有 session 写入只发生在显式传入的临时 workspace。
- 报告默认不包含 raw query、memory summary、prompt、session text 或 fake LLM response。

Phase 6b-2 可输出的数据：

- `agent_loop_enabled`
- `fake_llm_enabled`
- `llm_calls_enabled`
- `embedding_calls_enabled`
- `answer_quality_available`
- `case_count`
- `passed_case_count`
- `failed_case_count`
- `agent_turn_count`
- `retrieval_request_count`
- `fake_llm_call_count`
- `turn_committed_count`
- `session_message_count`
- `retrieval_query_matched`
- `retrieval_history_seen`
- `raw_query_included`
- `raw_memory_summary_included`
- `prompt_included`
- `session_text_included`

Phase 6b-2 验证结论：

- harness tests：`3 passed`。
- CLI tests：`2 passed`。
- 本地 CLI dry-run：9 个 fixture case 全部通过。
- dry-run report：`case_count = 9`、`passed_case_count = 9`、`failed_case_count = 0`。
- 集成指标：`agent_turn_count = 9`、`retrieval_request_count = 9`、`fake_llm_call_count = 9`、`turn_committed_count = 9`、`session_message_count = 18`。
- 当前结论是“评测集已经能穿过真实 Agent turn pipeline”。它仍然不代表真实 LLM 回答质量、真实召回准确率、source support 或 token 成本。

Phase 6b-3 已完成第一版：显式门控的 LLM 小样本答案级评测。

- 新增 `answer_expectations`，当前只放入 3 个稳定答案级 case：`cross_scope_isolation`、`preference_recall`、`vague_reference_graph`。
- 新增答案评分器，检查期望关键词、禁止关键词、期望 memory id、中文输出。
- 新增 `memory2/eval_llm_sample.py`，复用真实 `AgentLoop.process_direct()`，使用临时 workspace 和受控 memory engine。
- 新增 `scripts/run_memory_llm_sample_eval.py`，默认禁止真实 LLM；只有显式传入 `--enable-real-llm` 才允许构造真实 `LLMProvider`。
- CLI 支持 `--fake-provider`，用于不消耗 token 的链路验证。
- 报告不包含原始 query、memory summary、prompt、session text 或完整答案。

Phase 6b-3 fake-provider 验证结论：

- harness tests：`8 passed`。
- CLI tests：`5 passed`。
- 默认 gate 命令返回 exit code 1，并写出 `real_llm_enabled = false` 的 gated report。
- fake-provider CLI 本地跑完 3 个稳定 case：`case_count = 3`、`passed_case_count = 3`、`failed_case_count = 0`。
- 答案指标：`answer_contains_pass_count = 5`、`answer_contains_miss_count = 0`、`expected_memory_used_count = 3`、`forbidden_contains_violation_count = 0`、`language_pass_count = 3`。
- 运行指标：`provider_error_count = 0`、`timeout_count = 0`、`token_metrics_available = true`、`total_token_count = 90`、`total_latency_ms = 56`。
- 当前结论是“答案级小样本评测链路和真实 LLM 显式门控已经具备”。本轮还没有消耗真实 token，真实模型质量、真实费用和真实延迟需要后续人工确认运行。

Phase 6b-3 真实 LLM 人工确认运行结论：

- 使用主 checkout 的 `config.toml` 跑通真实 provider，报告 `real_llm_enabled = true`。
- 没有 provider error，也没有 timeout：`provider_error_count = 0`、`timeout_count = 0`。
- 3 个稳定 case 中 1 个通过、2 个失败：`case_count = 3`、`passed_case_count = 1`、`failed_case_count = 2`。
- 失败原因不是 memory id 未命中：`expected_memory_used_count = 3`。失败来自固定关键词规则，分别缺少 `Telegram` 和 `三路召回`。
- 本轮真实 token/延迟指标：`token_metrics_available = true`、`total_token_count = 14911`、`total_latency_ms = 10114`、`avg_latency_ms = 3371`。
- 当前修订方向：答案评分器增加同义词任一命中组，fixture 不再把平台名或某个中文术语作为唯一正确表达；token usage 解析兼容更多 provider 字段。

Phase 6b-3 修订后真实 LLM 复测结论：

- 答案期望已支持同义词任一命中组，报告新增 `answer_rule_pass_count` 和 `memory_grounding_pass_count`，可以区分“记忆命中”与“回答规则命中”。
- `LLMProvider` 已暴露标准 usage，真实报告可以记录 completion token：`completion_token_count = 602`。
- 复测结果：`case_count = 3`、`passed_case_count = 2`、`failed_case_count = 1`、`memory_grounding_pass_count = 3`、`answer_rule_pass_count = 2`、`total_token_count = 17098`、`total_latency_ms = 9427`。
- `vague_reference_graph` 仍失败，原因是没有命中 `RRF` 和第三路相关同义词。该结果说明模型对模糊指代下的具体排序证据使用仍不稳定，后续应优化证据注入、提示约束或增加显式引用检测。

当前存在的问题和可能原因：

- 问题 1：`vague_reference_graph` 记忆命中但答案未命中关键证据。
  - 证据：`memory_grounding_pass_count = 3`，但 `answer_rule_pass_count = 2`。
  - 可能原因：模型没有被强制引用或复述注入记忆中的 `RRF 融合排序`，模糊指代问题也增加了证据使用难度。
- 问题 2：真实 LLM 评测样本太少。
  - 证据：当前仅 3 个 case。
  - 可能原因：Phase 6b-3 先验证链路和指标，没有扩展到真实 memory DB 样本集。
- 问题 3：评测 memory 仍是受控 fixture。
  - 证据：harness 使用受控 memory engine，不读取真实 memory2 DB。
  - 可能原因：当前阶段为了隔离 LLM 行为和报告链路，先固定 memory 输入；后续需要把 Phase 6b-1 的真实样本和 Phase 6b-3 的答案级评测联动。
- 问题 4：答案质量判断仍偏规则化。
  - 证据：评分依赖关键词和同义词组。
  - 可能原因：规则评测可重复、低成本、无额外 LLM 调用，但对复杂语义等价表达覆盖有限。

后续建议拆分：

Phase 6b-4 已完成第一版：证据使用 debug 和真实 LLM 对照。

- 新增 `LLMSampleRunSpec`，让同一 EvalCase 可以按 `prompt_variant` 和 `repeat_index` 变成多条可对照运行记录。
- 新增 `--case-id`，支持指定单个或多个 case，选择顺序按用户传参保留。
- 新增 `--repeat-count`，重复次数小于 1 时直接报错，不做静默修正。
- 新增 `--evidence-prompt-mode baseline|coached|both`。`baseline` 保持原记忆块，`coached` 只在 eval harness 内提示模型优先使用记忆并保留关键术语，`both` 同时跑基线和增强两组。
- 新增 `--include-answer-debug`，只有显式打开时才把完整回答、证据块、命中词、缺失词和失败原因写到 `<workspace>/answer_debug/`。
- 常规 JSON/Markdown 报告仍不包含原始 query、memory summary、prompt、session text 或完整回答。

Phase 6b-4 可输出的数据：

- `repeat_count`
- `repeat_pass_rate`
- `repeat_answer_rule_pass_rate`
- `repeat_memory_grounding_pass_rate`
- `prompt_variant_mode`
- `pass_count_by_prompt_variant`
- `answer_rule_pass_count_by_prompt_variant`
- `memory_grounding_pass_count_by_prompt_variant`
- 本地 debug 文件中的 `evidence_block_text`、`answer_text`、`matched_expected_terms`、`missing_expected_terms`、`matched_any_groups`、`missing_any_groups`

Phase 6b-4 验证结论：

- focused harness tests：`16 passed`。
- focused CLI tests：`9 passed`。
- fake-provider smoke：`vague_reference_graph` 使用 `repeat_count = 2`、`prompt_variant_mode = both` 跑出 4 条记录并生成 4 个本地 debug 文件。
- 真实 LLM 对照：`vague_reference_graph` 使用 `repeat_count = 5`、`prompt_variant_mode = both`，共 10 次真实调用，全部通过。
- 真实 LLM 指标：`case_count = 10`、`passed_case_count = 10`、`failed_case_count = 0`、`answer_rule_pass_count = 10`、`memory_grounding_pass_count = 10`、`repeat_pass_rate = 1.0`。
- 按变体拆分：baseline 5/5 通过，coached 5/5 通过。
- token/延迟：`prompt_token_count = 49865`、`completion_token_count = 2697`、`total_token_count = 52562`、`total_latency_ms = 46977`、`avg_latency_ms = 4697`。
- 本轮结论：上一轮 `vague_reference_graph` 失败没有稳定复现；baseline 已经 5/5 通过，所以不能把本轮改进归因于 coached 提示。Phase 6b-4 的主要产出是可重复对照和可手动排查的 debug 能力，后续需要扩大样本、增加更难的模糊指代 case，才能判断提示增强是否有统计意义。

Phase 6c-1 已完成第一版：离线 uplift report。

- 复用 Phase 6a fixture 和 `EvalRunReport`。
- 输出 Phase 2/3/4/5/all 的离线 proxy uplift。
- 不调用真实 LLM，不读取真实 memory DB。
- 当前结论只能说明 shadow trace 在 fixture 上产生了可比较的 proxy 信号，不能说明真实生产回答提升。

后续建议拆分：

1. Phase 6c：把 eval report 接入 Dashboard 或 observe 查询界面。
2. Phase 6d：已经完成 80 case 量化 uplift 总表，输出 common/hard 双集和单项 / 总增益 JSON + Markdown，当前结果为 `baseline_main_score = 10.0`、`all_on_main_score = 68.9767`、`total_uplift_points = 58.9767`，报表路径见 `my_md/memory_optimization/eval_reports/memory_quantitative_uplift_eval.json`。
3. Phase 6e：基于连续评测结果决定哪些策略可以从 shadow 切到 active。

## 面试表达

```text
我会把图片里的记忆能力作为 memory 插件的实验扩展路线，而不是直接说已经实现。每个能力都有独立开关，先用 shadow 或 dry-run 跑旁路实验，不影响真实写入和召回，同时记录 baseline 和 experimental 的差异。比如写入价值评分会输出拒写原因和污染风险，三路召回会输出每一路贡献、准确率和回源命中，睡眠巩固会输出冗余下降和压缩率。等实验数据证明有效后，再把对应能力从 shadow 切到 active。
```
