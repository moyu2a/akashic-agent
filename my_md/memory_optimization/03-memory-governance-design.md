# Memory Governance Design

## 目标

这份文档描述记忆系统后续治理能力的设计草案。它不是当前实现状态，而是基于现有 `MemoryRuntime`、`default_memory`、`memory2`、`observe` 和 markdown memory 的可扩展方案。

图片中的版本链、信息价值评分、三路召回、睡眠巩固和层级溯源，建议先作为 memory 插件实验能力接入。具体开关、对照数据和阶段计划见 [04-memory-plugin-experiment-roadmap.md](./04-memory-plugin-experiment-roadmap.md)。

Phase 6h 之后，治理设计的当前口径可以分成两类：

- 回答侧：三路召回、图谱召回、重排与注入治理、版本链与溯源的离线目标指标已经对齐到 `93.75% -> 100%`、`97.5% -> 100%`、`93.75% -> 100%`、`90% -> 100%`。
- 写入/卫生侧：写入价值治理和睡眠巩固仍然主要是 shadow / proxy 结果，现阶段更适合做结构化对比，不适合直接当作真实在线证据。

因此，这份治理设计下一步要继续补的不是回答层本身，而是更真实的 write-governance evidence 和 memory-hygiene evidence。

目标是把记忆链路拆成五个治理点：

```text
候选生成
  -> 写入门控
  -> 质量评分
  -> 检索重排
  -> 生命周期维护
```

## 1. MemoryWritePolicy：写入门控

### 职责

在 consolidation、post-response memory worker 和显式 `memorize` 写入前，判断候选记忆是否应该进入长期记忆。

### 输入

```text
candidate_summary
memory_type
source_ref
scope
current_user_message
assistant_response
similar_existing_items
trigger_source
```

`trigger_source` 可取：

- `consolidation`
- `post_response`
- `memorize_tool`
- `manual_dashboard`

### 输出

```text
allow | reject | defer | needs_review
reason
quality_hints
conflict_candidates
```

### 拒绝原因

- `temporary_state`：临时状态，不适合长期记忆。
- `assistant_suggestion`：只是 assistant 建议，不是用户事实。
- `weak_inference`：弱推测，缺少用户明确表达。
- `duplicate`：已有相同记忆。
- `low_value`：长期价值低。
- `missing_source_ref`：缺少可回源证据，且不是显式用户要求。
- `conflict_candidate`：疑似和旧记忆冲突，需要更谨慎处理。

## 2. MemoryQualityScore：质量评分

### 字段

第一阶段建议先写入 `extra_json`：

```text
confidence
importance
novelty
source_quality
staleness
write_reason
last_used_at
use_count
```

### 评分来源

- 用户明确要求“记住” -> source_quality 高。
- 来自 consolidation 的用户原话 -> source_quality 中高。
- 来自 assistant 推断 -> source_quality 低，默认不应写入。
- 有 source_ref -> 置信度上限更高。
- 和旧记忆重复 -> novelty 低。
- 和旧记忆冲突 -> confidence 降低或进入 review。

### 使用方式

- 检索重排时使用。
- Dashboard 展示时使用。
- optimizer 做长期卫生时使用。
- 低置信记忆注入时必须标记“不确定”。

## 3. MemoryConflictDetector：冲突检测

### 基本流程

```text
新候选记忆
  -> 按 memory_type 检索相似旧记忆
  -> 判断是否语义相近
  -> 判断结论是否相反或状态是否更新
  -> 输出 conflict candidates
```

### 处理策略

- 显式用户纠错：允许走 `forget_memory` / supersede 流程。
- 新事实只是状态更新：旧状态降权或标记 stale，不直接删除。
- 偏好冲突：保留新旧 source_ref，必要时等待用户确认。
- 低置信冲突：不自动覆盖。

### 记录

冲突检测结果应进入 observe：

```text
candidate
old_item_id
old_summary
conflict_type
decision
reason
```

## 4. MemoryReranker：检索重排

### 当前基础

`memory2` 已经有：

- 向量 score。
- 关键词 score。
- RRF 合并。
- reinforcement。
- emotional_weight。
- scope 过滤。
- source_ref。
- low confidence label。

### 后续重排信号

```text
semantic_score
keyword_score
scope_match
memory_type_match
source_ref_present
confidence
importance
reinforcement
recency
staleness
conflict_penalty
```

### 输出

```text
raw_hits
reranked_hits
injected_hits
drop_reasons
```

### drop reason

- `low_score`
- `scope_mismatch`
- `stale`
- `low_confidence`
- `conflict_candidate`
- `too_many_same_type`
- `missing_source_ref_for_fact_question`

## 5. MemoryLifecycleManager：生命周期维护

### 状态

当前已经有：

```text
active
superseded
```

后续可以扩展为：

```text
candidate
active
stale
superseded
archived
rejected
```

第一阶段不一定改表结构，可以先在 `extra_json.lifecycle_status` 中试运行。

### 维护任务

optimizer 可以扩展出长期记忆卫生任务：

- 去重。
- 合并相似偏好。
- 压缩过长画像。
- 标记过期状态。
- 处理低置信候选。
- 输出 review 报告。

## 6. 观测和 Dashboard

建议新增观测维度：

- 候选记忆为什么写入。
- 候选记忆为什么拒绝。
- 召回项为什么注入。
- 召回项为什么被降权。
- 哪些记忆没有 source_ref。
- 哪些记忆处于 conflict candidate。

可以先写入 observe，再决定是否做 Dashboard 面板。

实验能力还需要统一记录 baseline 和 experimental 的差异。推荐每条实验记录包含：

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

其中 `mode=shadow` 时只记录差异，不影响真实写入、召回或 prompt 注入。

## 7. 与现有模块的关系

### 不改 AgentLoop

记忆治理应保持在记忆运行时和插件边界内：

```text
MemoryRuntime
default_memory engine
memory2 retriever/memorizer
observe plugin
Dashboard memory admin
```

AgentLoop 只继续通过生命周期、事件和工具抽象使用记忆。

### 保持 source_ref 作为核心证据链

任何新增质量评分、冲突检测和重排，都不能替代 source_ref。涉及历史事实和纠错时，仍应优先回源。

### 不把所有记忆强行注入 prompt

优化目标不是“召回更多”，而是“注入更准”。低置信、过期、冲突候选记忆应当被降权或提示需要回源。

## 8. 最小可行版本

### MVP 1：写入门控 trace

- 不改变写入结果，只记录候选判断。
- 输出 allow/reject 建议和 reason。
- 对比实际写入结果，积累样本。

### MVP 2：质量字段

- 在 `extra_json` 中写入 `confidence`、`source_quality`、`novelty`。
- Dashboard 可查看这些字段。

### MVP 3：检索重排 explain

- 不先改变排序，只记录原始排序、建议排序和 drop reason。
- 用评测集验证后再切换为真实排序。

## 面试表达

```text
记忆治理可以拆成写入门控、质量评分、冲突检测、检索重排和生命周期管理。写入门控解决“该不该记”，质量评分解决“这条记忆可信不可信”，冲突检测解决“新旧记忆是否矛盾”，检索重排解决“召回后该不该注入”，生命周期管理解决“长期运行后怎么去重、压缩、过期和归档”。这些能力都可以放在 MemoryRuntime、default_memory 和 memory2 内部扩展，不需要改 AgentLoop 主链路。
```
