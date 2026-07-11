# 13 Document RAG Evaluation

这个文档记录 Document RAG 的评估集、指标和实验结果。

## 评估目标

Document RAG 的目标不是“看起来能回答”，而是：

- 正确 chunk 能被召回。
- 排名尽量靠前。
- 注入内容不过量。
- 回答忠于文档。
- 引用来源准确。
- 文档没有答案时能拒答。

## 评估集字段

建议使用 JSONL：

```json
{
  "id": "q001",
  "question": "这个项目的 AgentLoop 是什么？",
  "question_type": "architecture",
  "expected_doc_id": "",
  "expected_chunk_id": "",
  "expected_source_path": "",
  "gold_answer": "",
  "answerable": true,
  "notes": ""
}
```

## 核心指标

### Recall@k

正确 chunk 是否出现在前 k 个召回结果中。

```text
Recall@5 = 命中问题数 / 总问题数
```

### MRR

正确 chunk 排名越靠前越好。

```text
MRR = mean(1 / rank)
```

### Context Precision

注入上下文中相关内容占比。

### Faithfulness

回答是否忠于文档，不编造文档没有的内容。

### Citation Accuracy

回答引用是否指向正确来源。

### Tool Path And Cost

Document RAG 不能只看“答对没答对”，还要看是否用了合理路径答对。

```text
tool_search_avoidance_rate = 强文档意图中未调用 tool_search 的问题数 / 强文档意图问题数
intent_preload_precision = 正确预加载的问题数 / 实际预加载的问题数
memory_intent_doc_rag_leak_rate = 记忆/session 问题中暴露或调用 Document RAG 工具的问题数 / 记忆/session 问题数
```

同时记录：

- `react_iteration_count`
- `tool_call_count`
- `expected_tools`
- `forbidden_tools`
- `used_tool_search`
- `doc_rag_lru_suppressed`

### No-answer Accuracy

文档没有答案时，是否能明确说没有找到依据。

## 初始评估问题池

先准备 20-30 条问题。

### 架构类

- Q001：这个项目为什么不是普通 chatbot？
- Q002：AgentLoop 在项目中负责什么？
- Q003：MessageBus 和 EventBus 有什么区别？
- Q004：Lifecycle phase 为什么存在？
- Q005：LLMProvider 抽象解决什么问题？

### Memory / RAG 类

- Q006：当前项目的 memory2 是怎么召回记忆的？
- Q007：为什么 memory retrieval 不只靠 embedding？
- Q008：query rewrite 在记忆召回中有什么作用？
- Q009：HyDE 在项目中解决什么问题？
- Q010：forget_memory 为什么使用 supersede？

### Tool / Plugin 类

- Q011：工具系统为什么需要 ToolRegistry？
- Q012：tool_search 为什么存在？
- Q013：ToolHook 解决什么问题？
- Q014：插件如何向系统注册能力？
- Q015：MCP 工具如何接入？

### Proactive 类

- Q016：Proactive v2 为什么不是有新内容就推送？
- Q017：presence 和打扰控制如何工作？
- Q018：ACK 策略解决什么问题？

### 部署 / 运维类

- Q019：workspace 为什么是运行状态边界？
- Q020：Dashboard 为什么需要保护？

### 无答案类

- Q021：项目是否已经完整实现 Document RAG？
- Q022：项目是否已经训练了 Query Rewrite LoRA？
- Q023：项目是否已经有完整 GraphRAG？

### 工具意图预加载类

- Q024：请从文档知识库中检索 agent runtime 负责什么？回答必须带文档引用。
  - 预期：强文档意图，当前 turn 预加载 `search_docs`，不需要先调用 `tool_search`。
- Q025：请从文档知识库中检索 agent runtime 负责什么？如果需要展开原文证据，请读取命中的 chunk。
  - 预期：强文档意图 + 原文证据展开，当前 turn 预加载 `search_docs` 和 `fetch_doc_chunk`。
- Q026：这个项目的 agent runtime 是什么？
  - 预期：语义上可能是架构问题，但没有明确文档知识库意图；v0 规则可以不预加载，让模型自行决定是否 `tool_search`。
- Q027：请从长期记忆里检索：我学习 agent 时最关注哪些方向？
  - 预期：强记忆意图，不预加载 `search_docs` / `fetch_doc_chunk`。
- Q028：同 session 上一轮刚查过文档后，再问“你还记得我刚才说我关注哪些学习方向吗？”
  - 预期：memory-after-doc-LRU 场景，当前 turn 临时压制 doc_rag LRU 残留，不暴露或调用 `search_docs`。

## 评估结果记录

| 日期 | 版本 | 问题数 | Recall@5 | MRR | Citation Accuracy | No-answer Accuracy | 结论 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 待填 | baseline | 0 | 待填 | 待填 | 待填 | 待填 | 待填 |

## 失败案例记录

| 问题 ID | 问题 | 期望来源 | 实际召回 | 错误类型 | 改进方案 |
| --- | --- | --- | --- | --- | --- |
| 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |

## 评估报告模板

```text
本轮评估日期：
索引文档范围：
chunk 参数：
召回参数：
问题数量：

Recall@5：
MRR：
Citation Accuracy：
No-answer Accuracy：

主要提升：
主要失败：
下一轮优化：
```

## 更新提示词

```text
请根据本次 Document RAG 评估结果，更新 my_md/rag/13-document-rag-evaluation.md，补充评估参数、指标结果、失败案例和下一步优化建议。
```
