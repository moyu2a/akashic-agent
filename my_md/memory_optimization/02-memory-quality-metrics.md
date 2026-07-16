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
