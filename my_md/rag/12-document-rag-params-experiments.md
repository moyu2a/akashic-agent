# 12 Document RAG Params Experiments

这个文档记录 Document RAG 参数实验。

目标是避免“凭感觉调 RAG”，而是记录不同切块、召回、重排和注入参数对效果的影响。

## 配置分组

v0 配置按职责分组：

```text
[doc_rag]            # 开关、存储位置、collection
[doc_rag.sources]    # 语料边界
[doc_rag.chunking]   # 切块行为
[doc_rag.embedding]  # 向量空间和 embedding 执行
[doc_rag.retrieval]  # 查询阶段
[doc_rag.trace]      # 观察和调试
[doc_rag.citation]   # 回答引用规则
[doc_rag.eval]       # 评估集和报告输出
```

为什么分组：

- 便于区分“索引配置”和“查询/观察配置”。
- 便于判断哪些参数变化需要 rebuild。
- 后续扩展 hybrid、rerank、GraphRAG 时不会把所有参数塞进一个大配置块。

## 当前默认参数候选

```text
vector_store = sqlite_vec
embedding_mode = inherit_memory
embedding_source = memory.embedding
embedding_model = text-embedding-v3
embedding_dim = 1024
embedding_batch_size = 16
embedding_max_retries = 2
embedding_timeout_seconds = 30
embedding_client_version = doc_embedding_client_v0
chunker_version = markdown_heading_v0
target_chunk_chars = 1600
max_chunk_chars = 2400
min_chunk_chars = 300
chunk_overlap_chars = 200
top_k = 5
similarity_threshold = 0.45
max_context_chars = 4000
hybrid_search_enabled = false
rerank_enabled = false
trace_enabled = true
trace_format = jsonl
trace_include_content = false
trace_max_content_chars = 2000
citation_required_for_doc_answer = true
citation_format = "[source_path > heading_path]"
citation_include_chunk_id_for_debug = false
eval_set_path = my_md/rag/eval_sets/doc_rag_eval_v0.jsonl
eval_report_dir = my_md/rag/eval_reports
```

这些只是初始候选，后续必须通过评估集调整。

## 参数分类

### 切块参数

```text
chunker_version
target_chunk_chars
max_chunk_chars
min_chunk_chars
chunk_overlap_chars
split_by_heading
merge_short_chunks
preserve_heading_path
protect_code_block
protect_table
protect_list
fallback_split_enabled
chunk_id_strategy
chunk_key_strategy
chunk_hash_strategy
```

### 召回参数

```text
vector_store
retrieval_mode
fallback_enabled
score_type
embedding_mode
embedding_source
embedding_model
embedding_dim
embedding_batch_size
embedding_max_retries
embedding_timeout_seconds
embedding_client_version
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

### Citation 参数

```text
citation_required_for_doc_answer
citation_format
citation_include_chunk_id_for_debug
citation_on_no_hits
citation_max_per_answer
citation_deduplicate_same_heading
```

### Trace 参数

```text
trace_enabled
trace_format
trace_include_content
trace_max_content_chars
trace_record_failures
```

### 工具参数

```text
search_docs_top_k_max
search_docs_include_content_default
search_docs_max_snippet_chars
fetch_doc_chunk_max_chars
tool_return_format
tool_error_format
```

### 索引和存储参数

```text
store_path
source_root
include_globs
exclude_globs
collection_id
source_path_mode
path_separator
allow_external_symlink
allowed_extensions
max_file_size_bytes
text_encoding
normalize_newlines_for_hash
schema_version
index_format_version
index_run_id
index_run_status
index_run_docs_enabled
indexer_dry_run
document_rebuild_policy
save_embedding_json
sqlite_vec_enabled
fallback_full_scan_enabled
embedding_status_filter
fts5_enabled
fts5_tokenizer
hybrid_enabled_for_search_docs
trace_enabled
trace_include_content
trace_max_content_chars
store_interface_version
embedding_client_version
```

这些参数必须记录，原因是同一套问答评估结果会受到索引版本、embedding 模型、chunker 版本和向量库能力影响。

## 实验记录表

| 实验 ID | 日期 | 目的 | vector_store | embedding_mode | embedding_model | chunker_version | target_chars | max_chars | overlap_chars | top_k | 检索方式 | Recall@5 | MRR | 主要问题 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- | --- |
| E001 | 待填 | baseline | sqlite_vec | inherit_memory | text-embedding-v3 | markdown_heading_v0 | 1600 | 2400 | 200 | 5 | vector | 待填 | 待填 | 待填 | 待填 |

## 切块实验

### 实验问题

- chunk 太小是否导致上下文不完整？
- chunk 太大是否导致召回不精确？
- 只在 fallback split 使用 overlap 是否能减少 top_k 重复？
- heading_path 是否显著提升回答可解释性？
- 代码块、表格、列表保护是否减少不可用 chunk？
- chunk_id 带 chunk_content_hash 是否更利于 trace 和评估复盘？

### 待测组合

| 组合 | target_chars | max_chars | overlap_chars | 策略 |
| --- | ---: | ---: | ---: | --- |
| A | 1200 | 1800 | 150 | 标题 + 段落，fallback overlap |
| B | 1600 | 2400 | 200 | 标题 + 段落，结构保护 baseline |
| C | 2200 | 3200 | 250 | 标题 + 段落，大 chunk 对比 |

v0 baseline：

```text
chunker_version = markdown_heading_v0
target_chunk_chars = 1600
max_chunk_chars = 2400
min_chunk_chars = 300
chunk_overlap_chars = 200
protect_code_block = true
protect_table = true
protect_list = true
fallback_split_enabled = true
chunk_id_strategy = source_path_heading_index_content_hash
chunk_key_strategy = source_path_heading_index
chunk_hash_strategy = sha256_normalized_chunk_content
```

为什么选择这个 baseline：

- Markdown 标题结构能提供稳定 `heading_path`。
- 字符级参数实现简单，适合先建立 v0 baseline。
- 只在 fallback split 使用 overlap，避免普通 chunk 大量重复。
- chunk_id 包含 chunk_content_hash，能避免内容变化后 trace/cache 混淆。
- chunk_key 不包含内容 hash，用于关联同一逻辑位置的新旧 chunk。

为什么暂时不用其他方案：

- 不用纯固定长度：容易切断标题、表格、代码块和列表。
- 不用 semantic chunking：需要额外 embedding 或语义边界判断，参数更多，不利于 v0 归因。
- 不用 LLM chunking：成本高、不稳定、难复现。
- 不先做 token-aware chunking：实现成本更高，等 char baseline 有指标后再比较。

### Chunk ID 稳定性实验

v0 策略：

```text
chunk_id = sha1(source_path + heading_path + chunk_index + chunk_content_hash)[:16]
chunk_key = sha1(source_path + heading_path + chunk_index)[:16]
chunk_content_hash = sha256(normalized_chunk_content)
document_content_hash = LoadedDocument.content_hash
```

实验问题：

- 内容轻微变化时，chunk_id 是否能反映版本变化？
- 同一逻辑位置是否能通过 chunk_key 关联前后版本？
- 标题变化时 chunk_key / chunk_id 一起变化是否符合 citation 预期？
- 插入段落导致 chunk_index 变化时，是否需要 v1 引入更稳定的 chunk 对齐策略？

为什么选择这个策略：

- chunk_id 表示具体内容版本，适合 trace、fetch 和向量表关联。
- chunk_key 表示逻辑位置，适合对比同一位置前后版本。
- v0 不做复杂 chunk diff，规则简单可解释。

为什么不用永远稳定的 chunk_id：

- 内容变化但 ID 不变，会让旧 trace 和新内容混在一起。
- 评估样本和缓存难以判断命中的是哪一版内容。

为什么不用复杂语义对齐：

- 需要额外相似度计算或 embedding。
- 会增加实现和调试复杂度。
- v0 corpus 应该相对稳定，暂时不需要复杂对齐。

记录表：

| 日期 | 变更类型 | chunk_id 是否变化 | chunk_key 是否变化 | 是否符合预期 | 备注 |
| --- | --- | --- | --- | --- | --- |
| 待填 | 内容修改 | 待填 | 待填 | 待填 | 待填 |
| 待填 | 标题修改 | 待填 | 待填 | 待填 | 待填 |
| 待填 | 段落插入 | 待填 | 待填 | 待填 | 待填 |

## 召回实验

### 实验问题

- vector-only baseline 的 Recall@k / MRR 是否达标？
- sqlite-vec 和 JSON fallback 的 top_k 是否基本一致？
- active + ready 过滤是否生效？
- index_stale / empty_index / no_hits 是否被正确区分？
- top_k 从 5 提到 10 是否增加噪声？

### 待测组合

| 组合 | retrieval_mode | backend | fallback_enabled | final_top_k | score_type |
| --- | --- | --- | --- | ---: | --- |
| A | vector_only | sqlite_vec | true | 5 | sqlite_vec_distance_converted |
| B | vector_only | sqlite_vec | true | 10 | sqlite_vec_distance_converted |
| C | vector_only | json_embedding_scan | true | 5 | cosine_similarity |

v1 后续再比较：

```text
keyword only
vector + keyword + RRF
rerank
```

v0 不直接比较 hybrid，原因是需要先建立纯向量 baseline。

### Retriever 稳定性实验

需要观察的指标：

```text
query
top_k
hit_count
latency_ms
fallback_used
score_type
error
index_run_id
```

错误场景：

```text
index_stale
empty_index
query_embedding_failed
sqlite_vec_unavailable
no_hits
```

实验问题：

- index_stale 是否阻止检索并提示 rebuild？
- empty_index 和 no_hits 是否返回空结果而不是报系统错误？
- sqlite-vec 不可用时是否能 fallback 到 JSON embedding 扫描？
- fallback 检索是否记录 `fallback_used = true`？
- trace 是否记录 score_type、latency、hits、error？

记录表：

| 日期 | 场景 | backend | fallback_used | hit_count | error | 是否符合预期 | 结论 |
| --- | --- | --- | --- | ---: | --- | --- | --- |
| 待填 | 正常检索 | sqlite_vec | false | 待填 | 无 | 待填 | 待填 |
| 待填 | fallback 检索 | json_embedding_scan | true | 待填 | 无 | 待填 | 待填 |
| 待填 | 空索引 | none | false | 0 | empty_index | 待填 | 待填 |
| 待填 | 索引过期 | none | false | 0 | index_stale | 待填 | 待填 |

### 工具接入实验

实验问题：

- Agent 是否能在文档问题中优先调用 `search_docs`？
- Agent 是否会把用户长期记忆问题误交给 `search_docs`？
- `search_docs` 是否默认只返回 snippet？
- `fetch_doc_chunk` 是否只在需要展开证据时调用？
- top_k、max_snippet_chars、max_chars 是否能限制返回长度？
- 结构化 error_code 是否便于自动测试？

关键指标：

```text
tool_call_accuracy
expected_tool_called
unexpected_tool_called
tool_error_code
result_size_chars
content_truncated
trace_id_present
```

工具错误码：

```text
doc_rag_disabled
index_stale
empty_index
query_embedding_failed
chunk_not_found
invalid_top_k
invalid_chunk_id
invalid_max_chars
retrieval_failed
```

记录表：

| 日期 | case | expected_tool | actual_tool | error_code | result_size | 是否符合预期 | 结论 |
| --- | --- | --- | --- | --- | ---: | --- | --- |
| 待填 | 文档检索 | search_docs | 待填 | 待填 | 待填 | 待填 | 待填 |
| 待填 | 展开 chunk | fetch_doc_chunk | 待填 | 待填 | 待填 | 待填 | 待填 |
| 待填 | 错误 chunk_id | fetch_doc_chunk | 待填 | chunk_not_found | 待填 | 待填 | 待填 |
| 待填 | 用户记忆问题 | recall_memory | 待填 | 待填 | 待填 | 待填 | 待填 |

### 工具意图预加载实验

实验目标：

- 降低强文档问题中的工具发现成本。
- 避免把非文档问题误导到 Document RAG。
- 验证同 session 上一轮使用过 `search_docs` 后，下一轮强记忆/session 问题不会因为 LRU 残留暴露 Document RAG 工具。

当前设计原则：

```text
宁可漏预加载，让模型走 tool_search；也不要乱预加载，把记忆/session 问题带偏到 Document RAG。
```

候选参数和统计项：

```text
doc_rag_intent_preload_enabled
doc_rag_intent_preload_rate
doc_rag_tool_search_avoided_rate
doc_rag_false_preload_count
doc_rag_lru_suppression_count
memory_after_doc_lru_leak_count
avg_react_iterations_doc_question
avg_tool_calls_doc_question
```

实验 case：

| case | 预期行为 | 关键指标 | 风险 |
| --- | --- | --- | --- |
| 明确文档知识库问题 | 当前 turn 预加载 `search_docs` | `doc_rag_tool_search_avoided_rate` | 规则过窄导致仍走 `tool_search` |
| 文档原文/证据展开问题 | 当前 turn 预加载 `search_docs` 和 `fetch_doc_chunk` | `avg_react_iterations_doc_question` | 过早展开导致 token 成本上升 |
| 普通架构问题 | 不做 Document RAG 预加载 | `doc_rag_false_preload_count` | 错误意图导致工具空间污染 |
| 记忆/session 问题 | 不做 Document RAG 预加载 | `doc_rag_false_preload_count` | 记忆问题被文档工具误导 |
| memory-after-doc-LRU | 当前 turn 临时压制 doc_rag LRU 残留 | `doc_rag_lru_suppression_count`, `memory_after_doc_lru_leak_count` | 上一轮工具使用影响下一轮 |

## 存储和向量库实验

### 当前 v0 选择

```text
vector_store = sqlite_vec
retrieval_mode = vector_only
fallback_enabled = true
score_type = sqlite_vec_distance_converted
store_path = ~/.akashic/workspace/doc_rag/doc_rag.db
source_root = repo_root
include_globs = ["my_md/doc_rag_corpus/**/*.md"]
exclude_globs = ["**/*.db", "**/*.sqlite", "**/*.jsonl", "**/*.log", "**/__pycache__/**", "**/.pytest_cache/**"]
collection_id = default
source_path_mode = repo_relative
path_separator = posix_slash
allow_external_symlink = false
allowed_extensions = [".md", ".markdown"]
max_file_size_bytes = 2097152
text_encoding = utf-8
normalize_newlines_for_hash = true
schema_version = 1
index_format_version = doc_rag_v0
index_run_docs_enabled = true
indexer_dry_run = false
store_interface_version = doc_rag_store_v0
embedding_mode = inherit_memory
embedding_source = memory.embedding
embedding_model = text-embedding-v3
embedding_dim = 1024
embedding_batch_size = 16
embedding_max_retries = 2
embedding_timeout_seconds = 30
embedding_client_version = doc_embedding_client_v0
save_embedding_json = true
document_rebuild_policy = rebuild_changed_document
embedding_status_filter = ready
fts5_enabled = true
fts5_tokenizer = trigram
hybrid_enabled_for_search_docs = false
trace_enabled = true
trace_include_content = false
trace_max_content_chars = 2000
search_docs_top_k_max = 10
search_docs_include_content_default = false
search_docs_max_snippet_chars = 500
fetch_doc_chunk_max_chars = 4000
tool_return_format = json
tool_error_format = structured_error_code
citation_required_for_doc_answer = true
citation_format = "[source_path > heading_path]"
citation_include_chunk_id_for_debug = false
citation_on_no_hits = "state_no_evidence"
citation_max_per_answer = 5
citation_deduplicate_same_heading = true
```

为什么选择：

- 与项目现有 `memory2` 的 sqlite-vec 技术路线一致。
- 不引入额外服务，适合本地 agent 和学习型实验。
- `retrieval_mode = vector_only` 能建立干净 baseline，避免 hybrid/rerank 干扰早期评估。
- `fallback_enabled = true` 能在 sqlite-vec 不可用时用 JSON embedding 全表余弦相似度兜底。
- `include_globs = ["my_md/doc_rag_corpus/**/*.md"]` 能让 v0 使用稳定、专门整理的测试语料。
- `source_path_mode = repo_relative` 能保证同一文档在不同机器、容器或 CI 环境下保持稳定标识。
- `allowed_extensions`、`max_file_size_bytes` 和 `text_encoding` 能把入口语料治理问题暴露在 loader 层。
- `schema_version` 和 `index_format_version` 能防止旧索引在新结构下被静默使用。
- `index_run_docs_enabled = true` 能记录每个文档的处理结果，便于定位索引失败和召回缺失。
- `indexer_dry_run` 可用于预览 indexed / skipped / deleted / failed，降低误索引风险。
- `store_interface_version = doc_rag_store_v0` 用于记录当前 store 接口边界，避免实验时混淆底层实现差异。
- `embedding_client_version = doc_embedding_client_v0` 用于记录当前 embedding 调用、批处理和错误处理边界。
- embedding JSON 副本便于 debug 和 fallback。
- 独立 `doc_rag.db` 能避免文档知识污染个人长期记忆。
- `embedding_mode = inherit_memory` 能降低 v0 配置成本，同时保留后续切换 custom 的空间。
- `embedding_status_filter = ready` 能避免 pending / failed chunk 进入检索结果。
- v0 预留 FTS5 但不启用 hybrid，既减少后续迁移，又保留 vector-only baseline。
- trace 默认写 JSONL 且不记录完整 content，避免长期运行时文件膨胀。
- `trace_include_content` 可在开发/测试阶段打开，方便检查 chunk 内容是否完整。
- `trace_max_content_chars` 用于限制单个 hit 写入 trace 的最大正文长度，避免一次检索写入过多内容。
- `search_docs` 默认只返回 snippet，避免一次工具调用把过多 chunk 正文注入上下文。
- `fetch_doc_chunk_max_chars` 限制按需展开内容的最大长度，控制上下文成本。
- `citation_required_for_doc_answer = true` 能约束文档类回答必须给出来源，减少“看起来合理但不可验证”的答案。
- `citation_format = "[source_path > heading_path]"` 同时兼顾用户可读性、repo 可迁移性和自动评估。
- `citation_include_chunk_id_for_debug = false` 避免普通回答暴露内部 ID；调试和评估场景仍可通过 trace 查看 `chunk_id`。
- `citation_on_no_hits = "state_no_evidence"` 要求无召回时明确说明没有文档证据，而不是编造引用。
- `citation_deduplicate_same_heading = true` 避免同一章节多个 chunk 被重复引用，提升回答可读性。

为什么暂时不用其他方案：

- 不用 Qdrant：v0 不需要独立向量服务。
- 不用 pgvector：当前项目没有 Postgres 基础设施。
- 不用 Chroma / LanceDB：当前更希望复用已有 sqlite-vec 并理解底层检索。
- 不默认索引现有散落 Markdown：这些文档更新频率高，且混有测试、复盘、错误记录和临时输出，会影响评估稳定性。
- 不默认索引 `README.md`、`my_md/**/*.md`、`_handbook/**/*.md`：它们可以后续人工整理后进入 corpus，但不适合作为 v0 baseline 语料。
- 不用绝对路径作为 `source_path`：绝对路径不可迁移，会把个人目录写入索引、trace 和评估报告。
- 不默认允许 repo 外 symlink：避免索引范围失控，也避免 citation 指向项目外部未知文件。
- 不自动猜编码：v0 corpus 应该使用 UTF-8；自动猜编码会让 loader 行为不可复现。
- 不索引超大文件：超大 Markdown 通常是误放日志、导出文件或未治理资料，不适合作为 v0 baseline。
- 不做自动 schema migration：v0 索引是可重建数据，显式 rebuild 更利于建立可信评估基线。
- 不只记录 `index_runs` 总数：总数不能说明具体哪个文档失败，也不方便按 expected source 排查评估问题。
- 不允许 changed 文档部分写入：如果任一 chunk embedding 失败，保留旧索引，不写入半成品。
- 不在 v0 建 `index_run_chunks`：chunk 级状态先由 `chunks.embedding_status / embedding_error` 承担，避免第一版写入和实现复杂度过高。
- 不让 loader / chunker 直接写数据库：保持数据处理逻辑可单测，数据库写入统一由 `DocRagStore` 管理。
- 不拆多个 store：v0 一个 `DocRagStore` 足够，过早抽象 VectorStore / DocumentStore 会增加复杂度。
- 不强制 custom embedding：v0 先跑通闭环；需要文档检索专项实验时再切换。
- 不让 embedding client 直接写数据库：embedding client 只返回向量和错误，状态写入由 indexer/store 负责。
- 不做复杂 embedding cache：`chunks.embedding` 和 `chunk_content_hash` 已能支持简单复用，复杂 cache 留到后续。
- 不直接启用 hybrid search：先建立纯向量 baseline，避免早期问题定位被融合参数干扰。
- 不把不同 score_type 的分数直接横向比较：sqlite-vec distance 转换分和 cosine similarity 语义不同。
- 不默认记录完整 content：chunk 原文可通过 `chunk_id` 回查，长期 trace 只保留 snippet 更轻量。
- 不取消 content 记录能力：开发测试阶段如果只看 snippet，无法准确判断切块是否破坏语义、召回是否缺上下文、证据是否足以支撑答案。
- 不让工具返回自然语言大段解释：工具返回结构化 JSON，最终回答由 Agent 生成。
- 不把 Document RAG 工具和 memory 工具混用：`search_docs` 查文档知识库，`recall_memory` 查用户长期记忆。
- 不只给文件名作为 citation：文件名粒度太粗，无法定位具体章节。
- 不默认展示 chunk_id：内部 ID 不适合普通用户阅读，但应保留在 trace 和评估报告中。
- 不用复杂脚注系统作为 v0：第一版优先保证检索、回答、trace 和评估闭环，复杂脚注后续再做 UI 化。
- 不允许模型自由编造 citation：citation 必须来自 `search_docs` 或 `fetch_doc_chunk` 的返回字段，方便自动评估。

后续对比条件：

- 当文档量明显变大或需要服务化部署时，对比 Qdrant。
- 当项目引入 Postgres 或需要复杂权限/事务时，对比 pgvector。
- 当需要快速原型或多模态数据时，再评估 Chroma / LanceDB。
- 当 vector-only 在关键词类问题上 Recall@k 不稳定时，启用 `vector + keyword + RRF` 对比。

### Rebuild 触发规则

必须 rebuild 的参数：

```text
schema_version
index_format_version
source_root
include_globs
exclude_globs
collection_id
allowed_extensions
max_file_size_bytes
embedding_mode
embedding_model
embedding_base_url
embedding_dim
chunker_version
target_chunk_chars
max_chunk_chars
min_chunk_chars
chunk_overlap_chars
source_path_mode
path_separator
vector_store
fts5_tokenizer
```

不触发 rebuild 的 embedding 执行参数：

```text
embedding_batch_size
embedding_max_retries
embedding_timeout_seconds
embedding_client_version
```

说明：

- `embedding_mode/model/base_url/dim` 改变向量空间或维度，必须 rebuild。
- batch/retry/timeout 只影响执行过程，不改变已生成向量的语义空间。
- `embedding_client_version` 如果只是错误处理或批处理逻辑变化，不需要 rebuild；如果改变 embedding text 构造，则应升级 `chunker_version` 或单独标记需要 rebuild。

不需要 rebuild 的参数：

```text
enabled
top_k
similarity_threshold
retrieval_mode
fallback_enabled
trace.enabled
trace.include_content
trace.max_content_chars
citation.format
citation.include_chunk_id_for_debug
eval.eval_set_path
eval.report_dir
rerank_enabled
hybrid_search_enabled
```

为什么要区分：

- 第一类参数改变索引内容、向量空间、chunk 边界或文档身份，继续用旧索引会让召回结果不可信。
- 第二类参数只影响查询、注入、观察、引用、评估或排序层，可以在同一个索引版本上做对比实验。

schema / index 校验：

```text
schema_version
index_format_version
index_config_hash
```

检索前必须对比当前配置和 meta 中的索引配置。

如果不兼容：

```text
返回 index_stale 或 schema_mismatch
要求显式 rebuild
```

v0 不做自动 migration。

原因：

- Document RAG 索引可重建。
- 显式 rebuild 更容易复盘。
- 自动 migration 容易隐藏版本不兼容问题。

实验记录要求：

- 每次 Recall@k / MRR 实验都必须记录 `index_run_id`。
- 如果发生 rebuild，需要记录 rebuild 触发原因。
- 如果只调整查询参数，不应更新 `index_run_id`，但要记录查询参数变化。

记录表：

| 日期 | 变更参数 | 是否 rebuild | 原 index_run_id | 新 index_run_id | 原因 | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |

### Embedding 实验

实验问题：

- `inherit_memory` 是否足够作为 Document RAG v0 baseline？
- custom embedding 是否能提升文档检索 Recall@k / MRR？
- batch_size 对索引耗时和失败率有什么影响？
- embedding text 加入 heading_path / source_path 是否提升章节类问题召回？
- 维度校验是否能及时发现配置错误？

v0 embedding text：

```text
标题路径: {heading_path}
来源: {source_path}

{chunk.content}
```

为什么这样构造：

- heading_path 给短 chunk 补充章节语义。
- source_path 给模型一点文档来源上下文。
- 不加入 chunk_id 这类随机标识，避免污染语义。

待测组合：

| 组合 | embedding_mode | embedding_model | dim | batch_size | text 构造 | Recall@5 | MRR | 失败率 | 结论 |
| --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: | --- |
| A | inherit_memory | text-embedding-v3 | 1024 | 16 | heading_path + source_path + content | 待填 | 待填 | 待填 | baseline |
| B | custom | 待填 | 待填 | 16 | heading_path + source_path + content | 待填 | 待填 | 待填 | 待比较 |
| C | inherit_memory | text-embedding-v3 | 1024 | 32 | heading_path + source_path + content | 待填 | 待填 | 待填 | batch 对比 |

失败记录：

```text
embedding_failed
embedding_error_types
embedding_dim_mismatch_count
embedding_latency_ms
embedding_batch_size
```

记录表：

| 日期 | index_run_id | embedding_mode | model | batch_size | failed | dim_mismatch | latency_ms | 结论 |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |

### Indexer 流程实验

实验问题：

- unchanged 文档是否能正确 skipped？
- changed 文档是否在 chunks + embeddings 全部成功后才原子替换？
- changed 文档 embedding 失败时，旧索引是否仍可检索？
- new 文档 embedding 失败时，是否不会进入 active documents？
- deleted 文档是否能被标记 deleted，并清理 chunks / vec_chunks？
- loader error 是否只影响单文档，不导致整个 run failed？
- 系统级配置错误是否能让 run failed 并停止？
- dry_run 是否能正确预览 indexed / skipped / deleted / failed？

关键状态：

```text
indexed
skipped_unchanged
deleted
failed
```

run 状态：

```text
succeeded
partial_failed
failed
cancelled
```

记录表：

| 日期 | 场景 | dry_run | run_status | indexed | skipped | deleted | failed | 是否符合预期 | 结论 |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| 待填 | 全新索引 | false | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |
| 待填 | 无变化重跑 | false | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |
| 待填 | 单文档 embedding 失败 | false | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |
| 待填 | dry-run 预览 | true | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |

### Corpus 范围实验

v0 baseline 固定语料范围：

```text
my_md/doc_rag_corpus/**/*.md
```

实验目的：

- 保持 RAG 评估集稳定。
- 避免高频更新学习笔记导致索引和 Recall@k 波动。
- 用人工整理后的文档构造更可控的 expected source。

为什么选择专门 corpus：

- RAG 的测试语料应该稳定、可解释、可复现。
- 散落文档适合记录学习过程，但不适合作为 baseline 知识库。
- 专门 corpus 能人为覆盖 agent runtime、memory、tool governance、plugin、Document RAG 等模块。

为什么暂时不扩大范围：

- 扩大到 `my_md/**/*.md` 会把测试报告、失败记录、设计草稿混入知识库。
- 扩大到 `README.md` 和 `_handbook/**/*.md` 会提升覆盖面，但也会引入未治理内容，影响 v0 指标解释。
- 等 baseline 稳定后，可以做“corpus-only vs broader-docs”的对比实验。

记录表：

| 实验 ID | include_globs | exclude_globs | 文档数 | chunk 数 | Recall@5 | 主要噪声 | 结论 |
| --- | --- | --- | ---: | ---: | ---: | --- | --- |
| C001 | my_md/doc_rag_corpus/**/*.md | 默认排除 | 待填 | 待填 | 待填 | 待填 | baseline |
| C002 | my_md/**/*.md | 默认排除 | 待填 | 待填 | 待填 | 待填 | 待比较 |

### Loader 稳定性实验

需要观察的 loader 指标：

```text
files_matched
files_loaded
files_skipped
loader_error_count
loader_error_types
max_file_size_bytes
encoding
```

错误类型：

```text
skip_empty
skip_too_large
decode_error
outside_source_root
external_symlink
not_markdown
read_error
```

实验问题：

- corpus 中是否存在空文件、超大文件或非 UTF-8 文件？
- include/exclude 是否稳定排除了测试输出和日志？
- source_path 是否稳定且不包含绝对路径？
- loader error 是否能被 indexer 记录到 `index_run_docs`？

记录表：

| 日期 | files_matched | files_loaded | files_skipped | error_types | 是否影响索引 | 结论 |
| --- | ---: | ---: | ---: | --- | --- | --- |
| 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |

### Index Run 失败恢复记录

需要观察的指标：

```text
index_run_status
docs_scanned
docs_indexed
docs_skipped
docs_deleted
docs_failed
chunks_created
chunks_deleted
embedding_failed
failed_source_paths
```

状态判断：

```text
succeeded       # 所有需要处理的文档成功
partial_failed  # 部分文档失败，但其他文档继续完成
failed          # 初始化、配置、schema 或数据库级失败
cancelled       # 用户或系统中断
```

实验问题：

- 单个坏文档是否会阻塞其他文档索引？
- 旧文档更新失败时，旧索引是否仍然可检索？
- 新文档失败时，是否不会进入 active documents？
- `index_run_docs` 是否能说明某个 expected source 为什么没有进入索引？

为什么这样记录：

- RAG 评估中如果某个问题没召回，第一步要确认 expected source 是否成功索引。
- `partial_failed` 比简单 failed 更准确，能表示知识库部分可用但不完全健康。
- 文档级记录能支持后续只重试失败文档，而不是每次全量重建。

记录表：

| 日期 | index_run_id | status | docs_scanned | docs_failed | failed_source_paths | 是否保留旧索引 | 结论 |
| --- | --- | --- | ---: | ---: | --- | --- | --- |
| 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |

### Trace Content 实验

实验目的：

- 判断是否需要在不同开发阶段打开完整 content。
- 观察 `trace_include_content` 对排查效率、文件体积和敏感信息风险的影响。
- 验证 `trace_max_content_chars` 是否足够覆盖常见 chunk，同时避免 trace 过大。

建议对比：

| 组合 | trace_include_content | trace_max_content_chars | 使用场景 | 关注指标 |
| --- | --- | ---: | --- | --- |
| A | false | 2000 | 日常运行 / 长期观察 | trace 体积、查询链路是否稳定 |
| B | true | 4000 | 切块调试 | chunk 是否完整、是否截断 |
| C | true | 8000 | 召回质量评估 | 证据命中、答案忠实度、top_k 重复度 |

为什么这样设计：

- 日常运行不需要重复存全文，只要保留 query、score、snippet 和 chunk_id。
- 切块调试需要看到更完整的段落，否则无法判断切块边界是否合理。
- 召回评估需要审查证据是否足以支撑答案，因此可以临时提高 `trace_max_content_chars`。

为什么不用一直记录全文：

- 文档规模扩大后 trace 文件会增长很快。
- trace 可能比原始文档更难统一权限管理和清理。
- 长期保存全文会增加敏感信息副本。

结论记录方式：

| 实验 ID | include_content | max_content_chars | trace 文件增长 | 是否便于排查 | 风险 | 结论 |
| --- | --- | ---: | --- | --- | --- | --- |
| T001 | false | 2000 | 待填 | 待填 | 待填 | 待填 |
| T002 | true | 4000 | 待填 | 待填 | 待填 | 待填 |
| T003 | true | 8000 | 待填 | 待填 | 待填 | 待填 |

## Citation 实验

### 实验问题

- 文档问答是否都带有 `[source_path > heading_path]` 引用？
- 引用是否来自真实的 `search_docs` / `fetch_doc_chunk` 返回字段？
- no_hits / empty_index / index_stale 时，Agent 是否会明确说明没有可引用证据？
- 同一章节多个 chunk 是否被去重引用？
- citation 是否能帮助人工判断答案忠实度？

### 关注指标

```text
citation_presence_rate
citation_source_valid_rate
citation_heading_valid_rate
fake_citation_count
no_evidence_response_rate
dedup_effective_rate
answer_faithfulness_with_citation
```

### 推荐测试类型

| 类型 | 输入示例 | 预期行为 |
| --- | --- | --- |
| 文档事实问题 | Document RAG 的默认语料目录是什么？ | 回答并引用对应文档章节 |
| 设计取舍问题 | 为什么 v0 不默认启用 hybrid search？ | 给出理由并引用设计章节 |
| 无证据问题 | 文档里是否提到某个不存在的模块？ | 说明没有检索到可引用证据 |
| 多证据问题 | loader 和 chunker 的边界分别是什么？ | 分别引用对应章节 |
| 调试问题 | 给出这条答案使用的 chunk_id | 可在调试模式输出 chunk_id |

### 记录表

| 日期 | case | 是否调用 search_docs | citation 是否存在 | source 是否真实 | heading 是否真实 | 是否伪引用 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 待填 | 文档事实问题 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |
| 待填 | 无证据问题 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |
| 待填 | 多证据问题 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |

为什么单独做 citation 实验：

- RAG 不只是“召回到内容”，还要让答案可验证。
- citation 能把检索结果、最终回答和人工复核连接起来。
- 如果引用格式不稳定，后续 Recall@k、证据命中和忠实度评估都会变难。

## 评估集 v0 与 Runner 实验

### 评估集文件

v0 使用：

```text
my_md/rag/eval_sets/
  doc_rag_eval_v0.jsonl
  README.md

my_md/rag/eval_reports/
  doc_rag_eval_v0_YYYYMMDD_HHMMSS.json
  doc_rag_eval_v0_YYYYMMDD_HHMMSS.md
```

目录职责：

- `eval_sets`：只放稳定评估集和维护说明。
- `eval_reports`：只放每次运行结果。

单条 case 建议字段：

```text
id
category
question
expected_sources
expected_answer_points
expected_tools
should_have_citation
should_have_no_evidence_response
difficulty
tags
notes
```

必填字段：

```text
id
category
question
expected_sources
expected_answer_points
expected_tools
should_have_citation
should_have_no_evidence_response
difficulty
tags
```

可选字段：

```text
notes
expected_chunk_id
expected_chunk_key
requires_fetch
judge_mode
```

`expected_sources` v0 先标：

```text
source_path
heading_path
```

暂不强制标 `chunk_id`。

原因：

- chunker 参数还可能调整，`chunk_id` 不是 v0 最稳定的人工标注锚点。
- `source_path + heading_path` 足够支持 Recall@k、MRR、citation_valid 和人工复核。
- 等 chunker 稳定后，再补充 `expected_chunk_id` 或 `expected_chunk_key`。

### 命名和维护规则

Document RAG v0 case ID：

```text
DRAG-V0-001
DRAG-V0-002
...
DRAG-V0-030
```

首批编号区间：

| 编号区间 | category |
| --- | --- |
| DRAG-V0-001 ~ 006 | fact_lookup |
| DRAG-V0-007 ~ 012 | design_rationale |
| DRAG-V0-013 ~ 018 | pipeline_reasoning |
| DRAG-V0-019 ~ 023 | boundary_distinction |
| DRAG-V0-024 ~ 027 | no_evidence |
| DRAG-V0-028 ~ 030 | multi_hop |

维护规则：

- `eval_sets` 不写运行结果。
- `eval_reports` 不反向修改评估集。
- 修改 `question`、`expected_sources` 或 `expected_answer_points` 时，需要记录原因。
- `id` 一旦进入报告，不应复用给另一个问题。
- 如果 case 废弃，保留 ID 并标记 deprecated。

### case 分类

推荐 v0 规模为 20-30 条：

| category | 建议数量 | 测试目标 |
| --- | ---: | --- |
| fact_lookup | 6 | 基础事实定位 |
| design_rationale | 6 | 设计取舍召回 |
| pipeline_reasoning | 6 | 多步骤流程理解 |
| boundary_distinction | 5 | memory / document RAG / tool 边界 |
| no_evidence | 4 | 无证据时拒绝编造 |
| multi_hop | 3 | 多模块组合回答 |

为什么这样分：

- 事实定位能验证最基本召回能力。
- 设计取舍适合面试表达，也最能体现“为什么这么设计”。
- 流程理解能暴露 chunk 是否切断链路。
- 边界区分能防止 Document RAG、长期记忆和工具治理混用。
- 无证据类能测试答案忠实度。
- 多模块组合能接近真实用户问题。

### Retrieval-only Runner

实验目的：

- 只验证文档检索层，不受 Agent 生成影响。
- 判断 expected source 是否进入索引、能否被召回、排名是否靠前。

输入：

```text
doc_rag_eval_v0.jsonl
```

输出指标：

```text
retrieval_recall_at_1
retrieval_recall_at_3
retrieval_recall_at_5
retrieval_mrr
expected_source_hit
expected_heading_hit
retrieval_latency_ms
```

记录表：

| 日期 | eval_set | total | Recall@1 | Recall@3 | Recall@5 | MRR | source_hit | heading_hit | 结论 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 待填 | doc_rag_eval_v0 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |

### Agent E2E Runner

实验目的：

- 验证完整链路：用户问题 -> Agent -> 工具选择 -> 文档检索 -> 回答 -> citation。
- 判断检索成功后，Agent 是否真的使用证据回答。

输出指标：

```text
tool_call_accuracy
expected_tool_called
unexpected_tool_called
citation_presence_rate
citation_valid_rate
answer_point_coverage
answer_faithfulness_rate
no_evidence_success_rate
avg_latency_ms
avg_tool_calls
avg_input_tokens
```

记录表：

| 日期 | eval_set | total | tool_accuracy | citation_valid | answer_coverage | no_evidence_success | avg_tool_calls | 结论 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 待填 | doc_rag_eval_v0 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |

### 报告输出

每次运行建议输出：

```text
my_md/rag/eval_reports/doc_rag_eval_v0_YYYYMMDD_HHMMSS.json
my_md/rag/eval_reports/doc_rag_eval_v0_YYYYMMDD_HHMMSS.md
```

JSON 用于机器分析，Markdown 用于学习复盘。

case 级记录字段：

```text
case_id
question
category
expected_sources
retrieved_hits
retrieval_metrics
agent_tool_calls
agent_answer
citations
judge_result
failure_reason
latency_ms
token_usage
```

为什么 runner 要分层：

- retrieval-only 失败时，优先查 corpus、loader、chunker、embedding、retriever。
- retrieval-only 成功但 agent e2e 失败时，优先查工具描述、提示词、citation 规则和生成逻辑。
- 分层后，优化方向不会混在一起。

为什么 LLM judge 最后接：

- 早期优先跑通硬指标。
- LLM judge 自身也可能不稳定，过早接入会干扰问题定位。
- 等 Recall@k、MRR、citation_valid 和 tool_correctness 稳定后，再评估答案忠实度自动评分。

## 失败归因实验

### failure_reason 枚举

v0 使用标准枚举，避免报告中出现大量不可统计的自由文本：

```text
index_issue
retrieval_miss
ranking_bad
tool_misuse
fetch_missing
citation_missing
citation_fake
answer_incomplete
answer_unfaithful
no_evidence_failed
runtime_error
judge_uncertain
```

### 记录字段

每个失败 case 至少记录：

```text
passed
failure_reasons
primary_failure_reason
debug_note
```

示例：

```json
{
  "passed": false,
  "failure_reasons": ["retrieval_miss"],
  "primary_failure_reason": "retrieval_miss",
  "debug_note": "expected heading 未出现在 top5，优先检查 chunker 和 embedding text"
}
```

### 归因到排查路径

| failure_reason | 优先排查 |
| --- | --- |
| index_issue | corpus、loader、index_run_docs、schema/meta、source_path |
| retrieval_miss | chunker、embedding text、embedding 模型、top_k、similarity_threshold |
| ranking_bad | chunk 粒度、query 表达、score 计算、hybrid/rerank |
| tool_misuse | 工具描述、ToolRegistry 可见性、系统提示词、工具治理 |
| fetch_missing | fetch_doc_chunk 描述、证据展开策略、search_docs 返回字段 |
| citation_missing | citation prompt、最终回答约束、工具结果注入格式 |
| citation_fake | citation 校验、禁止自由编造引用、工具返回字段约束 |
| answer_incomplete | expected_answer_points、上下文注入长度、是否需要 fetch 完整 chunk |
| answer_unfaithful | 生成提示词、证据不足、模型过度发挥、allow_model_prior |
| no_evidence_failed | no_hits 回答模板、无证据策略、citation 约束 |
| runtime_error | 工具异常、数据库异常、embedding API、LLM API、runner 超时 |
| judge_uncertain | judge prompt、人工复核、评估标准是否太模糊 |

### 统计表

| 日期 | eval_set | total_failed | index_issue | retrieval_miss | ranking_bad | tool_misuse | citation_fake | answer_unfaithful | no_evidence_failed | 主要结论 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 待填 | doc_rag_eval_v0 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 | 待填 |

为什么这样记录：

- 失败类型可以直接指导下一轮优化动作。
- 如果 `retrieval_miss` 占比高，优先优化切块、embedding 和召回。
- 如果 `tool_misuse` 占比高，优先优化工具描述和系统提示词。
- 如果 `citation_fake` 或 `answer_unfaithful` 占比高，优先优化回答约束和证据注入。
- 这比只看总通过率更适合做长期演进复盘。

## 实现阶段验收记录

Document RAG v0 实现按三阶段推进：

```text
第一阶段：P0-P3，配置、schema、loader、chunker 可单测
第二阶段：P4-P6，能索引、能检索、能 trace
第三阶段：P7-P8，Agent 可调用、评估可运行
```

### P0-P8 验收表

| 阶段 | 模块 | 验收重点 | 验收结果 | 问题记录 |
| --- | --- | --- | --- | --- |
| P0 | config / models | 配置可加载，默认关闭，模型可构造 | 待填 | 待填 |
| P1 | store / schema | init schema、meta、index run、replace chunks | 待填 | 待填 |
| P2 | loader | 只扫描 corpus，source_path 稳定，错误可记录 | 待填 | 待填 |
| P3 | chunker | heading_path、结构保护、chunk_id 稳定 | 待填 | 待填 |
| P4 | embedding client | inherit/custom、批量 embedding、维度校验 | 待填 | 待填 |
| P5 | indexer | rebuild、dry_run、增量、失败恢复、meta 写入 | 待填 | 待填 |
| P6 | retriever | meta 校验、vector-only、fallback、trace | 待填 | 待填 |
| P7 | tools | search_docs / fetch_doc_chunk 结构化返回 | 待填 | 待填 |
| P8 | eval runner | retrieval-only、agent e2e、JSON/MD report | 待填 | 待填 |

### 暂缓功能记录

v0 暂不进入参数实验的功能：

```text
hybrid search
rerank
query rewrite
GraphRAG
LLM Wiki
复杂 UI dashboard
自动 migration
复杂权限系统
大规模 LLM judge
```

暂缓原因：

- 先建立 Document RAG baseline。
- 避免早期问题定位被多个优化变量干扰。
- 等 Recall@k、MRR、citation_valid 和 tool_correctness 稳定后，再逐个引入增强能力。

## v0 最终验收记录

Document RAG v0 的最低标准：

```text
能索引
能召回
能引用
能评估
能复盘
```

总体验收表：

| 验收类别 | 验收项 | 验收结果 | 证据/报告位置 | 问题记录 |
| --- | --- | --- | --- | --- |
| 索引 | 只索引 doc_rag_corpus，不误索引散落文档 | 待填 | 待填 | 待填 |
| 索引 | index_runs / index_run_docs / meta 可追踪 | 待填 | 待填 | 待填 |
| 切块 | chunk 包含 source_path / heading_path / chunk_id / chunk_key | 待填 | 待填 | 待填 |
| 切块 | 代码块、表格、列表有结构保护 | 待填 | 待填 | 待填 |
| 检索 | search_docs / retriever 返回 top_k hits | 待填 | 待填 | 待填 |
| 检索 | empty_index / no_hits / index_stale 有结构化错误 | 待填 | 待填 | 待填 |
| 检索 | 每次检索写 retrieval trace | 待填 | 待填 | 待填 |
| 工具 | Agent 能调用 search_docs / fetch_doc_chunk | 待填 | 待填 | 待填 |
| 工具 | 工具返回结构化 JSON 和 error_code | 待填 | 待填 | 待填 |
| Citation | 文档回答带 `[source_path > heading_path]` | 待填 | 待填 | 待填 |
| Citation | 无证据时不编造引用 | 待填 | 待填 | 待填 |
| 评估 | 有 20-30 条 doc_rag_eval_v0 case | 待填 | 待填 | 待填 |
| 评估 | retrieval-only runner 输出 Recall@k / MRR | 待填 | 待填 | 待填 |
| 评估 | agent e2e runner 记录 tool calls / citation / failure_reason | 待填 | 待填 | 待填 |
| 安全复盘 | api_key 不进入 meta / trace / eval report | 待填 | 待填 | 待填 |
| 安全复盘 | 失败 case 有 primary_failure_reason | 待填 | 待填 | 待填 |

完成判断：

- 如果以上验收项全部通过，Document RAG v0 可以认为完成。
- 如果只实现文档问答，但没有 trace、citation、eval 和 failure_reason，只能算 demo。
- 如果评估指标不理想但链路完整，可以进入参数优化阶段。

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
