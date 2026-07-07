# 12 Document RAG Params Experiments

这个文档记录 Document RAG 参数实验。

目标是避免“凭感觉调 RAG”，而是记录不同切块、召回、重排和注入参数对效果的影响。

## 当前默认参数候选

```text
chunk_size = 800
chunk_overlap = 120
top_k = 5
similarity_threshold = 0.45
max_context_chars = 4000
hybrid_search_enabled = false
rerank_enabled = false
```

这些只是初始候选，后续必须通过评估集调整。

## 参数分类

### 切块参数

```text
chunk_size
chunk_overlap
min_chunk_chars
max_chunk_chars
split_by_heading
merge_short_chunks
preserve_heading_path
```

### 召回参数

```text
top_k
similarity_threshold
vector_top_k
keyword_top_k
metadata_filters
```

### 融合参数

```text
hybrid_search_enabled
rrf_k
keyword_weight
vector_weight
```

### 重排参数

```text
rerank_enabled
rerank_top_n
reranker_model
```

### 注入参数

```text
max_chunks
max_context_chars
per_chunk_max_chars
require_citation
allow_model_prior
```

## 实验记录表

| 实验 ID | 日期 | 目的 | chunk_size | overlap | top_k | 检索方式 | Recall@5 | MRR | 主要问题 | 结论 |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | --- | --- |
| E001 | 待填 | baseline | 800 | 120 | 5 | vector | 待填 | 待填 | 待填 | 待填 |

## 切块实验

### 实验问题

- chunk 太小是否导致上下文不完整？
- chunk 太大是否导致召回不精确？
- overlap 多大能覆盖跨段信息？
- heading_path 是否显著提升回答可解释性？

### 待测组合

| 组合 | chunk_size | overlap | 策略 |
| --- | ---: | ---: | --- |
| A | 512 | 80 | 固定长度 |
| B | 800 | 120 | 标题 + 段落 |
| C | 1000 | 150 | 标题 + 段落 |

## 召回实验

### 实验问题

- vector only 是否漏掉关键词明确的问题？
- keyword only 是否漏掉语义改写问题？
- hybrid 是否优于 vector only？
- top_k 从 5 提到 10 是否增加噪声？

### 待测组合

| 组合 | vector_top_k | keyword_top_k | fusion | final_top_k |
| --- | ---: | ---: | --- | ---: |
| A | 5 | 0 | none | 5 |
| B | 10 | 10 | RRF | 5 |
| C | 20 | 20 | RRF | 5 |

## Query Rewrite 实验

### 实验问题

- rewrite 是否提升 Recall@k？
- rewrite 是否引入错误意图？
- 对配置类问题、代码流程类问题、概念类问题效果是否不同？

### 对比方式

```text
raw query
rule rewrite
LLM rewrite
LoRA rewrite（后续）
```

## Rerank 实验

### 实验问题

- rerank 是否提升前 3 个 chunk 的相关性？
- rerank 增加的延迟是否可接受？
- rerank 后是否更容易生成准确引用？

## 失败案例记录

| 日期 | 问题 | 错误表现 | 原因猜测 | 修复方案 | 是否解决 |
| --- | --- | --- | --- | --- | --- |
| 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |

## 更新提示词

```text
请根据本次 Document RAG 参数实验，更新 my_md/rag/12-document-rag-params-experiments.md，记录实验配置、评估结果、失败案例、结论和下一轮参数建议。
```
