# Memory Governance Design

## 目标

这份文档描述记忆系统后续治理能力的设计草案。它不是当前实现状态，而是基于现有 `MemoryRuntime`、`default_memory`、`memory2`、`observe` 和 markdown memory 的可扩展方案。

图片中的版本链、信息价值评分、三路召回、睡眠巩固和层级溯源，建议先作为 memory 插件实验能力接入。具体开关、对照数据和阶段计划见 [04-memory-plugin-experiment-roadmap.md](./04-memory-plugin-experiment-roadmap.md)。

Phase 6h 之后，治理设计的当前口径可以分成两类：

- 回答侧：三路召回、图谱召回、重排与注入治理、版本链与溯源的离线目标指标已经对齐到 `93.75% -> 100%`、`97.5% -> 100%`、`93.75% -> 100%`、`90% -> 100%`。
- 写入/卫生侧：写入价值治理和睡眠巩固仍然主要是 shadow / proxy 结果，现阶段更适合做结构化对比，不适合直接当作真实在线证据。

因此，这份治理设计下一步要继续补的不是回答层本身，而是更真实的 write-governance evidence 和 memory-hygiene evidence。

Phase 6m 真实 LLM answer-quality 矩阵和失败归因又补充了一个新的结论：三路召回和图谱召回不能再按“默认全开”理解。它们能把证据召回进上下文，但在部分场景会提高噪声和 forbidden 风险，导致回答质量下降。因此当前回答侧治理新增一层“场景路由 + 候选治理”：

```text
用户问题
  -> 识别召回场景
  -> 选择允许的召回通道
  -> 限制每路候选数量
  -> 按 source_ref、scope、低置信和重复规则丢弃候选
  -> 再交给后续重排、注入治理和回答约束
```

当前已经落地的实现是 `memory2/retrieval_governance.py`。它把查询分成模糊指代、工具偏好、部分冲突、精确召回、来源查询和未知场景，并为每类场景配置召回通道、每路上限、是否要求来源、是否要求同作用域、是否启用图谱和是否丢弃低置信候选。`DefaultMemoryEngine.retrieve()` 透出 route trace，但不修改主循环、真实写入或工具执行边界。

Phase 6m-tri-candidate-governance 在这层之后继续补了一层可选的候选治理策略：

```text
召回候选
  -> classify_candidate_risks
  -> CandidateGovernancePolicy
  -> 受保护严格过滤
  -> trace 记录保留、丢弃和 would-drop 原因
```

当前识别的候选风险包括：

- `forbidden_candidate`：fixture 或候选字段显式标记为不应召回。
- `superseded_candidate`：旧版本、已被替换的记忆。
- `conflict_candidate`：候选字段显式标记为冲突项；不会再仅凭摘要里出现“冲突”两个字就判风险。
- `scope_mismatch`：候选 scope 和当前会话不一致。
- `missing_source_ref`：缺少来源。
- `weak_source_ref`：来源过弱，例如 session 级或 post-response 级来源。
- `low_confidence`：低置信候选。

这层默认关闭，只有显式设置 `CandidateGovernancePolicy(enabled=True)` 才执行严格过滤，因此不会改变现有生产召回契约。本轮 320 case 离线 trace 结果显示：受保护严格治理能保住 `640/640` 个目标证据，目标损失为 `0`，同时丢弃 `368/368` 个 should-not 候选；但不受保护严格治理会误删 `640/640` 个目标证据。结论是候选去噪必须和场景路由、来源质量、目标保护或生产替代信号一起使用，不能把“低置信/弱来源”规则直接全局硬删。

## 行业通用处理方式

针对“证据已经召回进上下文，但回答质量仍然不好”的问题，市面上的 RAG / Agent 方案通常不会继续盲目扩大召回，而是把链路拆开治理：

| 通用方向 | 常见做法 | 解决的问题 |
| --- | --- | --- |
| 分层评测 | 分开评估召回质量、上下文相关性、答案正确性、faithfulness / groundedness 和 forbidden 风险 | 避免只看最终答案分数，无法判断是召回错了还是生成没用对证据 |
| 候选去噪 | 去重、低置信过滤、冲突隔离、权限和 scope 过滤、旧版本过滤 | 解决召回候选太多、相似候选太杂、旧信息干扰回答的问题 |
| 重排 | 用规则分、交叉编码器、LLM reranker 或 RRF 后再排序 | 把真正关键的证据放到更靠前的位置，降低模型忽略关键证据的概率 |
| 上下文压缩 | 只保留关键句、实体、时间、来源和必要上下文 | 降低 prompt 噪声和 token 成本 |
| 场景路由 | 按问题类型选择不同检索策略，例如精确事实、模糊指代、工具偏好、冲突判断分别处理 | 避免高噪声通道在不适合的场景默认打开 |
| 证据注入约束 | 在 prompt 中明确证据 ID、来源、当前有效版本和回答依据 | 让模型更稳定地使用正确记忆 |
| 回答后校验 | 对输出做 grounding、relevance、forbidden 和 policy check，不通过则重试、降级或拒答 | 处理证据到了但答案仍答偏、幻觉或越界的问题 |
| 观测和回归集 | 把失败 query、召回候选、回答、评分和 trace 记录成可复现 case | 后续每次改召回、重排、prompt 或模型时做回归对比 |

这些做法和公开资料里的 RAG 评测、grounding guardrail、企业级 RAG 治理是一致的：

- Braintrust 的 RAG evaluation 把检索和生成分开评估，常用指标包括 context precision、context recall、answer relevancy 和 groundedness / faithfulness。
- Amazon Bedrock Guardrails 的 contextual grounding check 会同时检查回答是否基于来源、是否和用户问题相关，并支持阈值和阻断动作。
- AWS 的 grounding and RAG 指南强调生产系统需要在 grounding 之外加入安全、合规、访问控制、可追溯和自动推理。

参考：

- https://www.braintrust.dev/articles/what-is-rag-evaluation
- https://www.braintrust.dev/articles/rag-evaluation-metrics
- https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-contextual-grounding-check.html
- https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-serverless/grounding-and-rag.html

## 我们项目的对应方案

结合 Phase 6m 三路召回失败归因，本项目当前问题更像“召回后的回答治理”，不是单纯召回覆盖不足：

| 我们的现象 | 数据 | 对应治理方案 |
| --- | --- | --- |
| 目标记忆已经召回 | `tri_grounding_fail_count = 0` | 不继续把重点放在扩大召回覆盖 |
| 证据到了但没答对 | `tri_grounded_answer_fail_count_any = 23`，其中非 forbidden 失败 `18` | 加强证据注入模板、答案约束和回答后 grounding / relevance 校验 |
| 三路有救活能力也有回退 | 救活基线 `9` 个 case，回退基线 `5` 个 case | 做场景路由、候选去噪和低置信过滤，避免全局默认打开 |
| forbidden 风险仍存在 | `tri_forbidden_fail_count = 5` | 加 forbidden 过滤、旧版本过滤、冲突候选隔离 |
| 后续累计链路可救回部分失败 | `tri_failed_but_rerank_passed_count = 7` | 验证 `route + tri + graph/rerank/injection` 组合链路，但不把它解释成 rerank 单因素因果 |

拟定执行顺序：

1. 先做候选去噪：对三路候选加重复、低置信、旧版本、跨 scope 和弱来源过滤。
2. 再做 forbidden / 冲突治理：把 forbidden term、superseded item、冲突链旧节点和低可信来源候选隔离出注入上下文。
3. 然后做证据注入约束：让进入 prompt 的记忆带上更清晰的来源、当前有效版本、关键事实和回答时必须使用的证据边界。
4. 再做回答后校验：对生成结果检查是否 grounded、是否回答了问题、是否包含 forbidden；失败时重试、降级为基线召回或输出证据不足。
5. 最后做小型真实 LLM 复测：用同一批 40 case 或更聚焦的失败 case，比较 `answer_rate`、`forbidden_rate`、`baseline_passed_but_tri_failed_count` 和 `grounded_answer_rule_miss` 是否改善。

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

Phase 6m 之后，检索重排前新增了 `RetrievalRoutingDecision`。它不是新的排序算法，而是排序前的候选准入层：先判断当前问题适合哪些召回通道，再限制每个通道最多进入多少候选。比如模糊指代允许少量图谱候选，工具偏好只走语义和关键词，部分冲突和来源查询优先要求同 scope 且可追溯的来源证据。

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
route_decision
allowed_lanes
accepted_by_lane
dropped_by_reason
expected_route_hit_rate
candidate_accept_rate
```

### drop reason

- `low_score`
- `scope_mismatch`
- `stale`
- `low_confidence`
- `conflict_candidate`
- `too_many_same_type`
- `missing_source_ref_for_fact_question`
- `lane_not_allowed`
- `lane_cap`
- `missing_source_ref`
- `scope_mismatch`
- `low_confidence`
- `duplicate`

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

### Tri Candidate Governance 小型线上结论

本轮新增的 `chain_tri_candidate_governance` 只存在于评测 harness 中，不进入生产链路。它的作用是把现有三路召回的 `fused_ids` 作为候选集合，再应用严格候选治理：

- 过滤 forbidden / should-not 候选。
- 保留原三路融合顺序。
- 去重。
- 用 fixture `should_recall_ids` 做目标保护。
- 在报告中明确标记 `eval_only`、`oracle_protected` 和 `uses_fixture_expected_ids`。

真实 LLM 小矩阵结果：

| profile | answer_rate | grounding_rate | forbidden_rate |
| --- | ---: | ---: | ---: |
| `chain_memory_base` | `50.0%` | `100.0%` | `10.0%` |
| `chain_tri_retrieval` | `55.0%` | `100.0%` | `15.0%` |
| `chain_tri_candidate_governance` | `42.5%` | `100.0%` | `0.0%` |

设计结论：

- 候选治理对 forbidden 风险有效，证明边界治理不是只停留在离线 proxy。
- answer 降低说明“过滤坏候选”还不等于“让模型更会回答”；证据集合变短、关键上下文丢失、候选置信度没有分层、回答约束不够强，都可能让答案命中下降。
- 后续治理不应把所有候选一刀切删除，而应引入风险分级：高风险删除，中风险降权或放入 requires_review，低风险保留并通过重排控制注入位置。
- 生产化前还需要去掉 oracle-protected 依赖，用真实 source_ref、scope、版本链、冲突状态和候选置信度做决策。

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
