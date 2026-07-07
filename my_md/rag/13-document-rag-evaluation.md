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
