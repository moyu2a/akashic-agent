# 10 Document RAG Design

这个文档记录为 `akashic-agent` 引入 Document RAG 的设计决策。

目标是新增一个独立文档检索增强模块，用于检索项目文档、Markdown、PDF、网页资料或技术手册，而不是改造现有 `memory2` 个人长期记忆系统。

## 一句话设计

```text
新增 Document RAG 子系统，通过 search_docs / fetch_doc_chunk 工具接入现有 Agent Runtime；现有 AgentLoop、ToolRegistry、Plugin、MessageBus、memory2 保持边界清晰。
```

## 背景

当前项目已有个人记忆 RAG：

- 数据来源：用户对话、偏好、历史事件、用户画像、操作规则。
- 检索单元：结构化 memory item。
- 核心模块：`memory2`、default memory plugin、recall_memory、query rewrite、HyDE、RRF。

后续要新增的是文档知识库 RAG：

- 数据来源：Markdown、README、学习笔记、项目文档、PDF、网页。
- 检索单元：document chunk。
- 目标：回答“文档中怎么说”“项目文档在哪里说明”“某个设计依据是什么”。

## 目标

- 支持加载项目内 Markdown 文档。
- 支持文档切块、embedding、索引和检索。
- 支持 `search_docs` 工具查询相关文档片段。
- 支持 `fetch_doc_chunk` 工具读取完整 chunk。
- 支持返回来源引用。
- 支持基础评估集，能计算 Recall@k / MRR。
- 支持 trace 记录，方便观察召回过程。

## 非目标

第一版不做：

- 不把文档 chunk 写入 `memory2.db`。
- 不替代现有个人记忆 RAG。
- 不一开始支持所有文件格式。
- 不一开始做完整 GraphRAG。
- 不一开始做完整 LLM Wiki。
- 不让 Document RAG 自动注入每一轮 prompt。
- 不训练 LoRA。

## 第一版数据来源

第一版只处理 Markdown：

```text
README.md
my_md/*.md
_handbook/**/*.md
docs/**/*.md（如果存在）
```

原因：

- Markdown 结构清晰，适合按标题切块。
- 当前学习文档本身就是很好的 RAG 数据源。
- 便于验证 citation 和 heading_path。

## 推荐模块结构

可以新增：

```text
doc_rag/
  __init__.py
  config.py
  models.py
  loader.py
  chunker.py
  indexer.py
  store.py
  retriever.py
  citation.py
  tools.py
  eval.py
```

如果后续希望插件化，也可以迁移到：

```text
plugins/document_rag/
```

第一阶段推荐先做独立包，等边界稳定后再考虑插件化。

## 核心数据结构

### Document

```text
doc_id
source_path
title
content_hash
updated_at
metadata
```

### Chunk

```text
chunk_id
doc_id
source_path
title
heading_path
chunk_index
content
content_hash
token_count
embedding
created_at
updated_at
```

### RetrievalHit

```text
chunk_id
doc_id
source_path
heading_path
score
rank
snippet
content
metadata
```

## 工具接口

### search_docs

用途：根据用户问题搜索文档片段。

参数：

```text
query: string
top_k: int = 5
filters: object | null
```

返回：

```text
hits:
  - chunk_id
    source_path
    heading_path
    score
    snippet
```

### fetch_doc_chunk

用途：根据 chunk_id 读取完整 chunk。

参数：

```text
chunk_id: string
```

返回：

```text
chunk_id
source_path
heading_path
content
metadata
```

## 检索流程 v0

```text
user query
-> search_docs tool
-> query embedding
-> vector search top_k
-> 返回 snippet + citation
-> Agent 基于检索结果回答
```

## 检索流程 v1

```text
user query
-> query rewrite
-> vector search
-> keyword search
-> RRF fusion
-> optional rerank
-> top_n chunks
-> citation answer
```

## Citation 规则

每个回答中的关键结论尽量引用：

```text
[source_path > heading_path]
```

如果后续支持 PDF，再扩展为：

```text
[source_path p.12 > heading_path]
```

## 配置项

第一版配置：

```text
enabled
docs_paths
chunk_size
chunk_overlap
top_k
similarity_threshold
max_context_chars
embedding_model
store_path
```

后续增强：

```text
query_rewrite_enabled
hybrid_search_enabled
keyword_top_k
rrf_k
rerank_enabled
rerank_top_n
require_citation
```

## 接入现有项目的位置

推荐接入点：

- `ToolRegistry`：注册 `search_docs` 和 `fetch_doc_chunk`。
- `LLMProvider`：复用 embedding / rewrite / answer 所需模型接口。
- `Dashboard / observe`：记录检索 trace。
- `config.toml`：增加 Document RAG 配置。

第一版不要改：

- 不改 `AgentLoop` 主链路。
- 不改 `memory2` 表结构。
- 不改 proactive 主动链路。

## 设计取舍

为什么先用工具方式，而不是自动注入：

- 更可控。
- 不污染每轮上下文。
- 容易观察工具调用和召回结果。
- 更适合和现有 tool governance 结合。

为什么不直接复用 memory2：

- memory2 语义是个人长期记忆。
- Document RAG 需要文档路径、标题层级、chunk_id、引用。
- 两者生命周期不同，混在一起会污染检索和评估。

## 第一版验收标准

- 能索引 `my_md/*.md`。
- 能通过 CLI 问文档相关问题。
- Agent 能调用 `search_docs`。
- 返回结果带 source path。
- 至少 20 个问题的 Recall@5 有记录。
- 至少有 5 个回答包含正确引用。

## 后续更新提示词

```text
请根据本次 Document RAG 设计/实现进展，更新 my_md/rag/10-document-rag-design.md，补充新的架构决策、数据结构、工具接口、接入点和取舍说明。
```
