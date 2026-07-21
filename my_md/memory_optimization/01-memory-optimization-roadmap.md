# Memory Optimization Roadmap

## 背景

当前项目的记忆系统已经具备比较完整的工程基础：

- `session history`：按 `session_key` 保存短期会话历史。
- `markdown memory`：用 `MEMORY.md`、`SELF.md`、`HISTORY.md`、`PENDING.md`、`RECENT_CONTEXT.md` 保存人类可读的长期记忆和近期摘要。
- `memory2`：用 SQLite + embedding 保存结构化记忆条目，支持语义检索、显式记忆、失效和 `source_ref` 回源。
- 事件驱动：`TurnCommitted` 触发 markdown consolidation，`ConsolidationCommitted` 同步到 `memory2`。
- 显式工具：`memorize`、`forget_memory`、`recall_memory` 支持模型主动读写记忆。
- 观测能力：`observe.db`、`rag_queries`、`memory_writes` 和 `recall_inspector` 能观察召回和写入过程。

参考图片中的“Agent 长时记忆中间件”，下一步重点不是“再加一个向量库”，而是把记忆系统从“能保存和召回”升级成“会筛选、会打分、会重排、会纠错、会压缩”。

## 当前已有能力

### 1. 分层记忆

```text
session history
  -> markdown memory
  -> memory2 vector memory
```

这已经覆盖短期上下文、长期画像、事件日志、近期摘要和语义召回。

### 2. 幂等和回源

- markdown consolidation 使用 `source_ref` 避免同一批消息重复写入。
- `memory2` 条目保存 `source_ref`，历史问题或纠错时可以回到原始消息。
- `forget_memory` 把错误记忆标记为 `superseded`，不是直接覆盖。

### 3. 缓存友好

`PENDING.md -> optimizer -> MEMORY.md` 这层设计避免每轮直接修改 `MEMORY.md`，减少 system prompt 高频变化对 prompt cache 的影响。

### 4. 基础质量信号

`memory2` 已有一些可以用于质量治理的字段：

- `status`
- `source_ref`
- `reinforcement`
- `emotional_weight`
- `memory_type`
- `extra_json`
- `scope_channel`
- `scope_chat_id`

## 主要短板

### 1. 写入前缺少统一价值判断

现在系统能写入、能去重、能 supersede，但还缺少统一的 `MemoryWritePolicy` 来判断：

- 是否来自用户明确表达。
- 是否稳定可复用。
- 是否只是临时情绪或临时状态。
- 是否是 assistant 自己的建议。
- 是否已有相同或冲突记忆。
- 是否有可回源证据。

### 2. 质量评分还不完整

当前有 `reinforcement` 和 `emotional_weight`，但缺少更直接的质量字段：

- `confidence`
- `importance`
- `novelty`
- `source_quality`
- `staleness`
- `last_used_at`
- `use_count`

### 3. 检索排序仍偏召回分数

`memory2` 已经支持向量检索、关键词检索、RRF、hotness 等逻辑，但还可以把更多治理信号纳入最终注入决策：

- scope 是否严格匹配。
- source_ref 是否可回源。
- memory_type 是否适合当前问题。
- 记忆是否过期。
- 是否低置信或疑似冲突。

### 4. 缺少系统化评测集

没有固定 memory eval，就无法证明“优化后更好”。尤其是这些指标不能只靠日志判断：

- 检索准确率。
- 错误召回率。
- 记忆污染率。
- 纠错成功率。
- 跨 session 隔离正确率。

### 5. 当前评测集仍需继续增强

Phase 6f 的真实 baseline 版目标指标报告证明：如果 `before` 来自真实 trace baseline，而不是展示用的固定 `0%`，原 80 个离线 case 里三路召回、图谱召回、重排注入治理的目标召回率都是 `100% -> 100%`。这个结果不是“召回模块无效”，而是说明当时测试集太容易，baseline 已经能命中目标记忆。

Phase 6g 已补充显式 hard miss，并修订版本链 active leaf 口径。Phase 6h 继续修订 graph 专用分母，并补入 forked replacement-chain fixture。当前离线目标指标变为：

- 三路召回：`93.75% -> 100%`。
- 图谱召回：`97.5% -> 100%`。
- 重排与注入治理：`93.75% -> 100%`。
- 版本链与溯源：`90% -> 100%`。
- hard 子集三路召回：`87.5% -> 100%`。
- hard 子集图谱召回：`95% -> 100%`。
- hard 子集当前有效版本召回：`80% -> 100%`。
- hard/overall 的 `conflict_chain_detection_rate.after`：`100%`。

剩余要补充：

- baseline 语义召回失败但三路召回成功的 case。
- baseline 关键词召回失败但图谱桥接成功的 case。
- 相似实体、模糊指代、跨 session 和旧版本干扰 case。
- 写入治理更大规模真实 LLM shadow evidence，以及记忆库卫生 evidence，用于把 shadow estimate 和显式证据输入分开。

当前 graph `98.75%` 缺口已定位为指标分母问题：图谱召回不应被 tri-retrieval-only 的 `_target` miss 惩罚。当前冲突链识别率也已经通过 forked replacement-chain fixture 变成可测。写入治理已补 `24` 条真实 LLM 线上 shadow pilot，能证明 AgentLoop + 真实 provider + target metrics evidence 链路可用；下一步应把写入治理扩大到更大平衡样本，同时补记忆库卫生的显式 evidence，再跑真实 LLM 续测或 checkpoint 转换。

Phase 6j 已先补一版更大的目标导向测评集：默认 `standard` 仍是 80 case，新增显式 `comprehensive` 为 320 case，common 160 / hard 160。完整集覆盖 20 类场景和 8 个变体，并已通过 `scripts/run_memory_target_metrics_eval.py --case-pack comprehensive` 离线 smoke。这个改动解决“覆盖面不够”的一部分问题，但仍然不是线上真实 LLM 或真实 memory DB evidence。

## 优化目标

### P0：减少记忆污染

目标：

- 不把临时信息写成长记忆。
- 不把 assistant 建议写成用户事实。
- 不把弱推测写成稳定偏好。
- 写入前能识别重复和冲突候选。

建议能力：

- `MemoryWritePolicy`
- 写入拒绝原因 trace
- 候选记忆审计日志

### P1：建立记忆质量评分

目标：

- 每条记忆有质量信号。
- 检索时能区分高置信和低置信记忆。
- 长期未使用、低价值、过期风险高的记忆自动降权。

建议字段：

```text
confidence
importance
novelty
source_quality
staleness
last_used_at
use_count
```

第一阶段可以先放在 `extra_json`，后续再考虑表结构迁移。

### P2：增强检索重排

目标：

- 不只按向量相似度注入记忆。
- 结合语义、关键词、scope、时间、类型、质量和回源能力重排。

建议公式：

```text
final_score =
  semantic_score
  + keyword_rrf
  + scope_bonus
  + source_ref_bonus
  + confidence_bonus
  + importance_bonus
  + recency_bonus
  - staleness_penalty
```

### P3：增加冲突检测

目标：

- 新记忆写入前检查同类型旧记忆。
- 如果旧记忆语义相近但结论相反，标记为 `conflict_candidate`。
- 不自动覆盖高价值旧记忆，必要时要求回源或等待用户确认。

### P4：长期记忆卫生

目标：

- optimizer 不只归档 `PENDING.md`，还负责长期记忆卫生。
- 定期去重、合并、压缩、降权和冲突复核。

建议任务：

- 合并重复偏好。
- 压缩过长画像。
- 降权过期状态。
- 把过程类记忆转成 skill 或 procedure。

### P5：可观测和评测

目标：

- 能解释为什么写入、为什么拒绝、为什么召回、为什么注入。
- 建立 memory eval，验证优化是否真的减少错误。

## 实验化扩展方向

图片中提到的高级记忆能力，进入本项目时应先作为 memory 插件实验路线，而不是直接改成默认行为。详细方案见 [04-memory-plugin-experiment-roadmap.md](./04-memory-plugin-experiment-roadmap.md)。

每个方向都必须满足：

- 有独立开关。
- 支持 `off / shadow / active / ab` 或 dry-run。
- 能记录 baseline 和 experimental 对比。
- 能输出测试数据。
- 数据验证后再进入真实链路。

## 阶段计划

当前状态：

- Phase 0 已完成：实验配置、shadow trace、运行态 smoke 均已落地。
- Phase 1a 已完成：显式 `memorize` 的写入价值 shadow scoring 已输出结构化 signals。
- Phase 1b 已完成：写入候选会和已有 active 记忆做只读对比，输出信息熵、新颖度、重复风险、相似记忆和写入减少率。
- Phase 2a 已完成：三路召回 + RRF 融合 shadow 已输出三路候选、RRF 融合结果和排序差异 trace，不改变真实召回结果。
- Phase 2b 已完成：NetworkX 实体图谱 graph shadow 已输出 graph lane、graph-augmented RRF 融合结果和路径指标，不改变真实召回结果。
- Phase 3a 已完成：召回质量重排 shadow 已输出 rerank 后的候选顺序、分数拆解和名次变化，不改变真实召回结果。
- Phase 3b 已完成：注入治理 shadow 已输出 baseline 与 experimental 的注入差异、丢弃原因和 prompt 预算变化，不改变真实召回结果。
- Phase 4a 已完成：因果一致性版本链 shadow 已输出 replacement-only 版本链、当前 active leaf、旧版本误召回、冲突链和回滚候选，不改变真实召回结果。
- Phase 4b 已完成：层级化溯源 shadow 已输出 source_ref 解析、来源覆盖、孤儿记忆、扫描级跨 scope 数量和本轮召回级跨 scope 风险；第一版不执行真实回源。
- Phase 5 已完成第一版：离线睡眠巩固 shadow dry-run 已输出重复、可合并、过期、低价值、冲突、缺失来源和预计 token 节省，不改变真实记忆库。
- 后续下一步是 Phase 6：评测集、Dashboard 和 active 化决策。

### Phase 0：实验框架和开关

- 增加 `memory_experiments` 配置。
- 支持 `off / shadow / active / ab`。
- 建立 baseline vs experimental 数据记录。

### Phase 1：写入价值评分 shadow

- 增加信息熵、新颖度、稳定性、`source_ref` 可信度评分。
- 只旁路打分，不影响真实写入。
- 输出写入减少率、拒写原因和污染风险数据。
- Phase 1a 已完成：结构化记录 `final_score`、`decision`、`reason`、`signals` 和风险计数。
- Phase 1b 已完成：候选记忆和已有记忆对比，补充信息熵、新颖度、重复度、相似记忆和写入减少率。

Phase 1b 验证结论：

- focused suite：`30 passed`。
- live smoke：`3 passed`。
- `compileall` 和 `git diff --check` 通过。
- 仍然是 shadow-only，不改变真实 `memorize` 写入。

Phase 2a 验证结论：

- focused suite：`46 passed`。
- broader memory experiment suite：`51 passed`。
- `compileall` 和 `git diff --check` 通过。
- 仍然是 shadow-only，不改变真实召回和 prompt 注入。

### Phase 2：三路召回 shadow

- 第一路：语义召回，`memory2 vector`。
- 第二路：关键词召回，`memory2 keyword / search_messages`。
- 第三路：溯源召回，Phase 2a 只使用 `source_ref`、scope、模糊指代和文本重叠线索；真实 `fetch_messages` 回源和时间线索留到后续阶段。
- 同时跑旧召回和三路召回，对比命中、排序、注入差异。
- 输出 `lane_contribution`、`lane_count`、`rerank_changed_count`、`baseline_experimental_overlap_rate`、`rrf_score_distribution`、`source_ref_coverage`、`retrieval_latency_ms`。
- Phase 2a 已完成：先实现三路召回 shadow 和 RRF 融合排序，不改变真实召回结果。
- Phase 2b 已完成：第三路加入 NetworkX 实体图谱，只记录 `graph_retrieval` trace，用于评估“那个、上次、之前说的方案”等模糊指代场景的召回变化。
- Phase 2b 仍然是 shadow-only：真实 `retrieve()` 返回值、真实 `recall_memory` 工具结果和 prompt 注入都不使用 graph 结果。
- Phase 2b 输出 `graph_ids`、`graph_fused_ids`、`graph_fused_items`、`graph_path_count`、`avg_graph_path_length`、`entity_match_count`、`graph_score_distribution`、`retrieval_latency_ms` 和 `baseline_graph_overlap_rate`。
- 真实 `fetch_messages` 回源、`fetch_success_rate` 和 active 化决策仍留到后续阶段。

Phase 2b 验证结论：

- focused suite：`56 passed`。
- broader memory experiment suite：`77 passed`。
- `compileall` 和 `git diff --check` 通过。

Phase 3a/3b 验证结论：

- focused rerank / injection tests：通过。
- engine contract 回归：通过。

Phase 4a/4b 验证结论：

- focused Phase 4 suite：`45 passed`。
- 版本链和层级溯源仍然是 shadow-only。
- 不改变真实写入、真实召回、真实 `recall_memory` 工具结果和 prompt 注入。
- 真实 `fetch_messages` 回源、`fetch_success_rate`、`evidence_precision` 和 active 化决策留到后续评测阶段。
- broader memory suite：`136 passed, 3 skipped, 1 warning`。
- full pytest：`1915 passed, 3 skipped, 3 warnings`。
- `compileall` 和 `git diff --check`：通过。

### Phase 3：召回重排和注入治理

- Phase 3a 已完成：在三路召回候选上做质量重排 shadow，输出 rerank 顺序、分数拆解和名次变化。
- Phase 3b 已完成：在真实注入块之上做注入治理 shadow，输出 baseline / experimental 注入差异和预算变化。

- 在三路召回候选上做统一重排。
- 加入 scope、`source_ref`、质量分、版本链、过期状态。
- 输出 `rerank_changed_count`、`drop_reason`、`injected_count`、prompt token 变化。

### Phase 4：版本链和层级溯源

- Phase 4a 已完成：建立 replacement-only 版本链、旧版本误召回检测、冲突链检测和回滚候选 shadow。
- Phase 4b 已完成：解析现有 `source_ref` 到 session/message/span 层级，记录来源覆盖、解析成功率、孤儿记忆和跨 scope 风险 shadow。
- 第一版不执行真实 `fetch_messages` 回源，因此 `fetch_success_rate`、`evidence_precision` 和 `source_support_rate` 留到后续回源评测阶段。
- 输出 `replacement_count`、`chain_count`、`avg_chain_depth`、`max_chain_depth`、`active_leaf_count`、`stale_recalled_count`、`rollback_candidate_count`、`conflict_chain_count`、`source_ref_coverage`、`parse_success_rate`、`orphan_memory_count`、`cross_scope_memory_count`、`cross_scope_risk_count`。

### Phase 5：离线异步睡眠巩固

- Phase 5 已完成第一版 shadow dry-run。
- 在 `ConsolidationCommitted` 事件后有界扫描 active memory。
- 输出重复组、可合并候选、过期候选、低价值候选、冲突候选、缺失 `source_ref` 数量、预计 token 节省、预计冗余下降和任务耗时。
- 候选 trace 有输出上限，并记录截断数量，避免 shadow trace 过大。
- 第一版不合并、不删除、不 supersede、不修改真实召回和 prompt 注入。
- 常驻 scheduler / daemon、真实压缩率和 active 清理留到 Phase 6 评测后再判断。

Phase 5 验证结论：

- 提交：`3492cf2 feat: add memory sleep consolidation shadow experiment`。
- focused suite：`49 passed`。
- broader memory suite：`151 passed, 3 skipped, 1 warning`。
- full pytest：`1930 passed, 3 skipped, 3 warnings`。
- `compileall` 和 `git diff --check`：通过。
- 当前仍是 shadow-only / dry-run，不改变真实写入、真实召回、真实 `recall_memory` 工具结果和 prompt 注入。

### Phase 6：评测集和 Dashboard

- 构造偏好召回、历史回源、纠错、跨 session、临时信息污染等测试集。
- 形成可重复跑的 memory eval。
- 展示 baseline / experimental 对照。

## 面试表达

```text
我们当前的记忆系统已经有短期历史、markdown 长期记忆、向量记忆、source_ref 回源和 optimizer。后续优化重点不是简单换一个向量库，而是做记忆治理：写入前判断是否值得记，写入后给记忆打质量分，检索后结合 scope、时间、source_ref 和置信度重排，长期运行中再做去重、冲突检测和过期降权。这样可以把记忆从“能保存”升级成“记得准、用得对、可评测”。
```
