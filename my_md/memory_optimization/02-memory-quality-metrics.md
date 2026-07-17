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

意义：

- source_ref 覆盖率越高，历史问题和纠错时越容易回源。
- 无 source_ref 记忆应当更谨慎注入。

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
| Phase 6 | 评测集、Dashboard 和 active 化决策 | `recall_at_k`、`precision_at_k`、`wrong_recall_rate`、`memory_pollution_rate`、`compression_ratio`、`source_support_rate` |

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

当前 Phase 4b 不执行真实 `fetch_messages` 回源，所以 `fetch_success_rate`、`evidence_precision`、`source_support_rate` 仍然不能由本阶段 trace 直接给出，需要后续回源评测或标注集。

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

## 面试表达

```text
记忆优化不能只说“召回更准了”，必须能测。我们当前已经能从 memory2.db 和 observe.db 直接测记忆规模、写入量、强化比例、superseded 比例、source_ref 覆盖率、召回 hit 数、注入数量、score 分布和 prompt token 成本。下一步需要补 consolidation 压缩率、检索延迟、写入门控通过率和回源成功率。真正的准确率、污染率和纠错成功率不能只看日志，必须建立 memory eval 标注集。
```
