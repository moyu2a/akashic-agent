# 11 Document RAG Implementation Plan

这个文档记录 Document RAG 的实施计划、任务拆分和进度。

## 当前目标

两周内完成：

```text
Document RAG 扎实闭环 + GraphRAG / LLM Wiki 可演示雏形
```

如果时间不足，优先保证：

```text
Document RAG 可用 + 有评估 + 有 trace
```

## 任务总览

| 阶段 | 任务 | 状态 |
| --- | --- | --- |
| P0 | 明确设计边界和数据结构 | 待开始 |
| P1 | Markdown loader | 待开始 |
| P2 | Markdown chunker | 待开始 |
| P3 | embedding 与 store | 待开始 |
| P4 | retriever | 待开始 |
| P5 | search_docs / fetch_doc_chunk 工具 | 待开始 |
| P6 | 接入 ToolRegistry | 待开始 |
| P7 | citation 格式 | 待开始 |
| P8 | 评估集和评估脚本 | 待开始 |
| P9 | trace 记录 | 待开始 |
| P10 | hybrid search | 待开始 |
| P11 | query rewrite | 待开始 |
| P12 | 轻量 GraphRAG 原型 | 待开始 |
| P13 | LLM Wiki 页面雏形 | 待开始 |

## Day 1：设计和边界

目标：

- 确定不改 `memory2`。
- 确定新增 `doc_rag`。
- 确定工具接口。
- 确定 chunk schema。
- 确定配置项。

产出：

- 更新 `10-document-rag-design.md`。
- 建立模块目录草案。

## Day 2：Markdown Loader

目标：

- 读取指定路径下 Markdown 文件。
- 提取标题、路径、内容 hash、更新时间。
- 忽略空文件和非 Markdown 文件。

验收：

- 能列出 `my_md/*.md` 的文档元数据。

## Day 3：Chunker

目标：

- 按 Markdown 标题和段落切块。
- 保留 heading_path。
- 控制 chunk_size 和 overlap。
- 生成稳定 chunk_id。

验收：

- 每个 chunk 能追溯到原始文件和标题。
- chunk 不应过短或过长。

## Day 4：Embedding 和 Store

目标：

- 为 chunk 生成 embedding。
- 存储 chunk 元数据和向量。
- 第一版可以使用 SQLite + sqlite-vec 或先用 SQLite + JSON embedding。

验收：

- 能重建索引。
- 能按 chunk_id 查询 chunk。

## Day 5：Retriever

目标：

- 实现 `search(query, top_k)`。
- 返回 chunk_id、score、source_path、heading_path、snippet。

验收：

- 对 5 个手工问题能召回相关 chunk。

## Day 6：工具接入

目标：

- 实现 `search_docs`。
- 实现 `fetch_doc_chunk`。
- 注册到 `ToolRegistry`。

验收：

- CLI 中 Agent 可以调用文档检索工具。

## Day 7：评估集 v0

目标：

- 准备 20-30 条问题。
- 标注 expected_doc / expected_chunk。
- 实现 Recall@k / MRR 计算。

验收：

- 能输出一份评估报告。

## Day 8：参数优化

目标：

- 调整 chunk_size。
- 调整 chunk_overlap。
- 调整 top_k。
- 调整 max_context_chars。

验收：

- 至少完成 2-3 组参数对比。

## Day 9：Hybrid Search

目标：

- 增加关键词召回。
- 与向量召回做 RRF 融合。

验收：

- 对关键词明确的问题，召回质量提升。

## Day 10：Trace

目标：

- 记录 query、hits、score、source、latency。
- 后续可接 Dashboard。

验收：

- 每次 search_docs 都有 JSONL trace。

## Day 11：轻量 GraphRAG

目标：

- 从文档中抽取模块、文件、工具、事件关系。
- 第一版可以用规则或 LLM 生成简单 triples。

验收：

- 能回答“某模块和哪些模块有关”。

## Day 12：Graph Tool

目标：

- 实现 `search_graph` 或 `find_related_modules`。

验收：

- Agent 能调用 graph 工具查询模块关系。

## Day 13：LLM Wiki 雏形

目标：

- 生成 3-5 个模块 Wiki 页面。
- 页面保留来源引用。

验收：

- 至少生成 Agent Runtime、Memory、Tool、Proactive、Plugin 页面。

## Day 14：总结和演示

目标：

- 整理演示脚本。
- 整理技术总结。
- 整理面试表达。
- 更新文档。

验收：

- 能 5 分钟讲清楚 Document RAG 设计和效果。

## 风险和砍项顺序

如果时间不足：

```text
先砍 LLM Wiki
再砍 GraphRAG
不要砍评估
不要砍 citation
不要砍 trace
```

## 每次推进后的更新提示词

```text
请根据本次 Document RAG 实现进展，更新 my_md/rag/11-document-rag-implementation-plan.md，标记任务状态、记录完成内容、遇到的问题、下一步任务和风险。
```
