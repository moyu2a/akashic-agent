# 14 Document RAG Interview Notes

这个文档记录后续 Document RAG、GraphRAG、LLM Wiki、LoRA 和推理优化相关的面试表达。

## 项目增强定位

可以这样说：

```text
原项目已经有个人长期记忆 RAG，但它服务的是用户偏好、历史事件和操作规则。为了补齐文档问答能力，我新增独立 Document RAG 子系统。它通过工具接入现有 Agent Runtime，复用 ToolRegistry、LLMProvider、Dashboard 和可观测能力，同时避免污染 memory2 个人记忆系统。
```

## 为什么不直接复用 memory2

```text
memory2 的检索单元是个人记忆 item，而 Document RAG 的检索单元是文档 chunk。前者关注用户事实、偏好、规则和纠错，后者关注文档来源、标题层级、chunk 引用和原文追溯。混在一起会导致个人记忆和文档知识互相污染，也不利于评估。
```

## 为什么先做工具方式

```text
第一版我没有把文档检索结果自动注入每轮 prompt，而是通过 search_docs 和 fetch_doc_chunk 工具暴露给 Agent。这样更可控，也方便观察模型什么时候需要查文档、查到了什么、引用是否准确。等评估稳定后，再考虑自动检索或混合注入。
```

## Document RAG 技术亮点

可以按 5 点讲：

1. 独立知识库边界。
2. Markdown 标题感知切块。
3. 向量 + 关键词 hybrid retrieval。
4. citation 和无答案拒答。
5. Recall@k / MRR / Faithfulness 评估。

## GraphRAG 表达

```text
普通 Document RAG 解决“从原文片段中找答案”，GraphRAG 进一步解决“知识之间有什么关系”。我会从文档 chunk 中抽取模块、工具、事件、配置之间的实体关系，形成轻量图谱，用来回答模块依赖、多跳影响分析和跨文档综合问题。GraphRAG 不替代普通 RAG，它需要普通 RAG 做原文证据和引用校验。
```

## LLM Wiki 表达

```text
LLM Wiki 是在 Document RAG 和 GraphRAG 之上的知识沉淀层。它把高频主题、模块设计、概念关系编译成可读 Wiki 页面，并保留来源引用。Agent 可以先读 Wiki 建立全局理解，再回到底层 chunk 做证据校验。
```

## LoRA 表达

```text
我不会用 LoRA 记文档知识，因为文档更新频繁，应该走 RAG。LoRA 更适合优化 RAG 里的稳定行为，比如 query rewrite、RAG 路由、文档问答格式和无答案拒答。最小实验是训练 Query Rewrite LoRA，然后用 Recall@k 和 MRR 对比微调前后的召回效果。
```

## 推理加速表达

```text
推理加速在这个项目里属于模型服务层优化。项目通过 OpenAI-compatible LLMProvider 接入不同后端，比如 API、Ollama、vLLM 或 llama.cpp。然后记录首 token 延迟、总延迟、tokens/s、cache 命中和错误率。对于 query rewrite、RAG 路由、memory extraction 这类轻任务，可以路由到小模型；复杂回答仍走大模型。
```

## Agent Gateway 表达

```text
当前项目被动链路没有独立 Agent Gateway，而是由 channel adapter 把不同平台消息转成 InboundMessage，再通过 MessageBus 进入 AgentLoop。MessageBus 起到了部分消息网关作用，但还不包含认证、限流、幂等、审计、trace 和统一错误标准化。后续产品化可以新增 AgentGateway 层来收敛这些入口治理能力。
```

## STAR 表达模板

### Situation

```text
原项目已有个人记忆系统，但无法很好回答项目文档、技术手册和外部资料相关问题。普通聊天模型也容易在文档问题上幻觉，缺少来源引用。
```

### Task

```text
目标是新增一个独立 Document RAG 子系统，让 Agent 能检索项目文档，并基于可追溯来源回答问题，同时保持和个人 memory2 系统隔离。
```

### Action

```text
我设计了 loader、chunker、indexer、retriever、citation、eval 和工具接入层。第一版通过 search_docs / fetch_doc_chunk 接入 ToolRegistry，后续再增强 hybrid search、query rewrite、rerank、GraphRAG 和 LLM Wiki。
```

### Result

```text
最终 Agent 不仅能记住用户，还能查项目文档、给出来源引用，并通过 Recall@k、MRR、Citation Accuracy 等指标评估效果。这体现了我对 RAG 从数据处理、检索、生成到评估的完整理解。
```

## 常见面试问题

1. 为什么文档 RAG 不直接塞进现有 memory2？
2. chunk_size 和 chunk_overlap 怎么选？
3. 为什么要保留 heading_path？
4. 为什么不只用 embedding？
5. query rewrite 什么时候会伤害召回？
6. rerank 的成本和值不值得？
7. 文档没有答案时怎么处理？
8. citation 怎么保证准确？
9. GraphRAG 和普通 RAG 的边界是什么？
10. LLM Wiki 是否会替代 RAG？
11. LoRA 是否可以替代 RAG？
12. 如何评估 RAG 效果？

## 更新提示词

```text
请根据本次 Document RAG / GraphRAG / LLM Wiki / LoRA / 推理优化讨论，更新 my_md/rag/14-document-rag-interview-notes.md，补充面试表达、STAR 叙事、常见追问和回答。
```
