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
| P0 | config / models | 已完成初步实现 |
| P1 | store / schema | 已完成初步实现 |
| P2 | Markdown loader | 已完成初步实现 |
| P3 | Markdown chunker | 已完成初步实现 |
| P4 | embedding client | 待实现 |
| P5 | indexer | 待实现 |
| P6 | retriever | 待实现 |
| P7 | search_docs / fetch_doc_chunk 工具 | 待实现 |
| P8 | 接入 ToolRegistry | 待实现 |
| P9 | citation 与回答引用规则 | 待实现 |
| P10 | 评估集和评估脚本 | 待实现 |
| P11 | trace 记录 | 待实现 |
| P12 | hybrid search | 待开始 |
| P13 | query rewrite | 待开始 |
| P14 | 轻量 GraphRAG 原型 | 待开始 |
| P15 | LLM Wiki 页面雏形 | 待开始 |

## Day 1：设计和边界

目标：

- 确定不改 `memory2`。
- 确定新增 `doc_rag`。
- 确定工具接口。
- 确定 chunk schema。
- 确定配置项。
- 确定选型记录规则：每个关键方案都要记录为什么选、为什么不用其他方案、好处和解决的问题。
- 确定存储层使用独立 `doc_rag.db`，不写入 `memory2.db`。
- 确定 v0 使用 `SQLite + sqlite-vec`。
- 确定 v0 表结构：`documents`、`chunks`、`vec_chunks`、`index_runs`、`meta`。
- 确定 Document RAG embedding 配置块：支持 `inherit_memory` 和 `custom` 两种模式。
- 确定 `source_path` 规范：使用 repo 相对 POSIX 路径，不用绝对路径作为主身份字段。
- 确定 schema version 与重建策略：v0 严格校验索引配置，不兼容时阻止检索并要求显式 rebuild。
- 确定 index run 记录粒度与失败恢复策略：`index_runs` 记录总览，`index_run_docs` 记录文档级结果，文档更新采用原子替换。
- 确定配置入口和默认索引范围：新增独立 `[doc_rag]` 配置块，v0 默认只索引 `my_md/doc_rag_corpus/**/*.md`。
- 确定 `doc_rag.models` 和 `doc_rag.store` 最小接口：models 定义稳定数据对象，store 封装 SQLite / sqlite-vec 读写。

产出：

- 更新 `10-document-rag-design.md`。
- 建立模块目录草案。

当前进展：

- 已确定 Document RAG 和 memory2 的边界：文档知识库不复用个人长期记忆库。
- 已确定切块方案：Markdown 标题结构优先 + 段落合并 + 长段落截断。
- 已确定存储和向量库方案：独立 SQLite 数据库 + sqlite-vec。
- 已确定增量索引策略：文件变化后按 document 粒度重建 chunks。
- 已确定 embedding 配置方向：默认 `inherit_memory`，后续可切换 `custom`。
- 已确定 chunks / vec_chunks 同步策略：使用 rowid 对齐，chunk 状态用 `embedding_status` 管理。
- 已确定 FTS5 预留策略：v0 建 `chunks_fts`，但默认仍使用 vector-only 检索。
- 已确定 retrieval trace 策略：v0 写 JSONL，默认只记录 snippet，可通过 `include_content` 开关记录截断后的完整 chunk 内容。
- 已确定 trace content 策略：生产/长期运行默认不记录完整 content；切块调试、召回评估和证据命中分析时可临时打开，并用 `max_content_chars` 控制体积。
- 已确定路径规范化策略：`source_path` 使用 repo 相对路径，`doc_id` 基于规范化后的 `source_path` 生成；绝对路径只允许作为调试信息可选进入 metadata，不参与 citation 和评估。
- 已确定 schema version 与重建策略：embedding、chunker、路径规范、schema、vector store 等索引关键配置变化时必须 rebuild；top_k、trace、rerank、hybrid 等查询/观察参数变化时不需要 rebuild。
- 已确定 index run 记录粒度：`index_runs` 记录整体状态和计数，`index_run_docs` 记录每个文档的 action、status、hash 变化、chunk 数和错误。
- 已确定失败恢复策略：单文档失败不中断整次任务，run 状态为 `partial_failed`；旧文档更新失败时保留旧索引，新文档失败时不进入 active documents。
- 已确定配置入口和默认语料边界：Document RAG 使用独立 `[doc_rag]` 配置，`enabled = false`；v0 不默认索引现有散落 Markdown，只索引专门整理的 `my_md/doc_rag_corpus/**/*.md`。
- 已确定 `models.py` 和 `store.py` 边界：`DocConfig`、`DocumentRecord`、`ChunkRecord`、`IndexRun`、`IndexRunDoc`、`RetrievalHit`、`SearchResult` 作为核心模型；`DocRagStore` 提供 schema、meta、index run、document、chunk、vector search 的最小接口。
- 已确定模块依赖方向：loader/chunker 不直接碰数据库，store 不依赖 LLM，tools 不直接写 SQL。
- 已确定 Markdown loader 设计：只负责扫描、过滤、读取、路径规范化、title 提取和 content_hash；返回 `LoadedDocument` 与 `LoaderError`，不切块、不 embedding、不写数据库。
- 已确定 Markdown chunker 设计：采用 heading-aware block chunker，维护 `heading_path`，保护代码块/表格/列表，同标题下合并短块，超长块 fallback split，chunk_id 包含 chunk 内容 hash。
- 已确定 chunk_id 稳定性方案：`chunk_id` 表示具体内容版本，`chunk_key` 表示逻辑位置，`chunk_content_hash` 判断 chunk 内容变化，`document_content_hash` 关联文档版本。
- 已确定 embedding client 设计：新增 `DocEmbeddingClient`，默认继承 memory2 embedding 配置，也支持 custom；负责批量 embedding、维度校验、标准化错误返回，不直接写数据库。
- 已确定 indexer 完整流程：按 config -> loader -> chunker -> embedding client -> store 编排；文档级增量判断，changed/new 全量准备成功后原子替换，loader/chunker/embedding 单文档失败进入 partial_failed，系统级错误进入 failed。
- 已确定 retriever 设计：v0 采用 vector-only baseline，query embedding 由 `DocEmbeddingClient` 生成，`DocRagStore.search_vector` 检索 active + ready chunks；sqlite-vec 不可用时 fallback 到 JSON embedding 全表余弦相似度；每次检索写 JSONL trace。
- 已确定工具接入设计：`search_docs` 返回 snippet + metadata + trace_id，`fetch_doc_chunk` 按 chunk_id 展开内容；工具返回结构化 JSON 和结构化 error_code；工具层不实现检索逻辑、不直接写 SQL。
- 已确定 citation 与回答引用规则：最终回答使用 `[source_path > heading_path]` 引用文档依据；`chunk_id` 默认不展示给普通用户，只用于 `fetch_doc_chunk`、trace、debug 和评估；检索失败时不编造引用。
- 已确定评估集 v0 设计：使用 `doc_rag_eval_v0.jsonl`，每条 case 记录 id、category、question、expected_sources、expected_answer_points、expected_tools、citation/no-evidence 预期；先做 20-30 条人工标注 baseline。
- 已确定评估 runner 分层设计：先做 retrieval-only runner 计算 Recall@k / MRR / evidence hit，再做 agent e2e runner 检查工具调用、citation、答案覆盖和忠实度，最后再接 LLM judge。
- 已确定失败归因标准：失败 case 记录 `failure_reasons` 和 `primary_failure_reason`，v0 使用 index_issue、retrieval_miss、ranking_bad、tool_misuse、fetch_missing、citation_missing、citation_fake、answer_incomplete、answer_unfaithful、no_evidence_failed、runtime_error、judge_uncertain。
- 已确定评估集文件落地设计：`eval_sets` 只放稳定 case，`eval_reports` 只放运行结果；`doc_rag_eval_v0.jsonl` 使用 JSONL，一行一个 case；首批 30 条按 category 分配编号区间。
- 已确定配置项最终汇总：Document RAG 使用独立分组配置 `[doc_rag]`、`[doc_rag.sources]`、`[doc_rag.chunking]`、`[doc_rag.embedding]`、`[doc_rag.retrieval]`、`[doc_rag.trace]`、`[doc_rag.citation]`、`[doc_rag.eval]`；默认关闭；通过 schema_version、index_format_version 和 index_config_hash 校验索引兼容性。
- 已确定最小实现顺序：按 config/models -> store/schema -> loader -> chunker -> embedding client -> indexer -> retriever -> tools -> eval runner 推进；先做可单测底层，再接 Agent 工具，最后做评估 runner。
- 已确定 v0 最终验收标准：Document RAG v0 必须覆盖索引、切块、检索、工具、答案引用、评估、安全复盘七类验收；最低标准是能索引、能召回、能引用、能评估、能复盘。
- 已形成第一阶段 P0-P3 文件级实现计划：见 `my_md/rag/15-document-rag-p0-p3-implementation-plan.md`，覆盖 config/models、store/schema、Markdown loader、Markdown chunker 和对应 pytest 验收。
- 已完成 P0-P3 实现计划审阅，并按审阅意见修正：补充 index run/store 事务原子性、sqlite-vec blob 写入、loader symlink/非 Markdown 错误、chunker fallback split/table header 测试和 P0-P3 验收矩阵。
- 已完成 P0-P3 初步实现：新增独立 `doc_rag` 包，包含 shared models、SQLite schema/store、Markdown loader、Markdown chunker；新增 `[doc_rag]` 配置读取和 `config.example.toml` 示例。
- 已完成 P0-P3 单元验证：`uv run --with pytest pytest tests/test_doc_rag_config.py tests/test_doc_rag_models.py tests/test_doc_rag_store.py tests/test_doc_rag_loader.py tests/test_doc_rag_chunker.py -v`，结果 `22 passed, 1 warning`。
- 自审中发现并修正 `vec_chunks.rowid` 对齐问题：向量表现在使用 `chunks.rowid`，而不是从 `chunk_id` 推导，便于后续 KNN 结果直接回表到 chunk。
- 已完成既有回归验证：`uv run --with pytest pytest tests/test_memory2_retrieval_baseline.py tests/test_tool_discovery_routing.py -v`，结果 `16 passed, 1 warning`。
- 当前实现仍未接入 AgentLoop、ToolRegistry、embedding API、indexer、retriever 和工具调用链路；因此不会影响现有 Agent 运行行为。

下一步：

- 进入 P4-P6：实现 `DocEmbeddingClient`、indexer 和 retriever，让 Document RAG 从“可加载/可切块/可入库”进入“可索引/可召回/可 trace”。
- 继续保持 TDD：先写 embedding/indexer/retriever 测试，再实现代码；仍不急于接 Agent 工具，避免底层问题和 Agent 行为问题混在一起。

## v0 总体验收

Document RAG v0 完成时，必须满足七类验收：

| 类别 | 必须证明 |
| --- | --- |
| 索引 | 稳定索引 `my_md/doc_rag_corpus/**/*.md`，不误索引散落文档，meta/index_run 可追踪 |
| 切块 | chunk 有 source_path、heading_path、chunk_id、chunk_key，结构保护和 hash 正确 |
| 检索 | search_docs/retriever 能返回 top_k，vector-only 可用，错误结构化，trace 可查 |
| 工具 | Agent 能调用 search_docs/fetch_doc_chunk，工具返回 JSON，工具层不直接写 SQL |
| Citation | 文档回答带 `[source_path > heading_path]`，不伪造引用，无证据时明确说明 |
| 评估 | 有 20-30 条 eval case，能跑 retrieval-only 和 agent e2e，输出 JSON/MD report |
| 安全复盘 | api_key 不进入 meta/trace/report，失败 case 有 primary_failure_reason |

完成判断：

```text
能索引 + 能召回 + 能引用 + 能评估 + 能复盘 = v0 闭环
```

如果只做到“能回答文档问题”，但没有 trace、citation、eval 和 failure_reason，只能算 demo，不能算 v0 完成。

## 实现阶段顺序

| 阶段 | 模块 | 目标 | 主要验收 |
| --- | --- | --- | --- |
| P0 | config / models | 定义配置和数据对象边界 | 配置可加载，默认关闭，模型可构造 |
| P1 | store / schema | 建立 SQLite + sqlite-vec 存储底座 | 能 init schema、写 meta、记录 index run、replace chunks |
| P2 | Markdown loader | 读取稳定 corpus | 只扫描 doc_rag_corpus，source_path repo 相对，错误可记录 |
| P3 | Markdown chunker | 生成结构化 chunk | heading_path 正确，保护代码/表格/列表，chunk_id 稳定 |
| P4 | embedding client | 生成向量 | 支持 inherit_memory/custom，批量 embedding，维度校验 |
| P5 | indexer | 文档入库闭环 | rebuild/dry_run/增量/失败恢复/meta 写入 |
| P6 | retriever | 文档检索闭环 | meta 校验、vector-only、fallback、trace |
| P7 | tools | 暴露给 Agent | search_docs/fetch_doc_chunk 结构化返回和错误码 |
| P8 | eval runner | 自动评估 | retrieval-only、agent e2e、JSON/MD report |

阶段节奏：

```text
第一阶段：P0-P3
目标：配置、schema、loader、chunker 可单测

第二阶段：P4-P6
目标：能索引、能检索、能 trace

第三阶段：P7-P8
目标：Agent 可调用、评估可运行
```

v0 暂缓：

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

原因：

- v0 目标是跑通 Document RAG 闭环。
- 先建立 baseline，再做优化。
- 太早引入 hybrid / rerank 会让问题定位复杂化。

## Day 2：Markdown Loader

目标：

- 读取指定路径下 Markdown 文件。
- 提取标题、路径、内容 hash、更新时间。
- 忽略空文件和非 Markdown 文件。
- 将文件路径规范化为 repo 相对 POSIX `source_path`。
- 默认拒绝索引 repo root 外的文件或指向 repo 外部的 symlink。
- 默认只扫描 `my_md/doc_rag_corpus/**/*.md`，不扫描现有散落学习文档。
- 读取 UTF-8 / UTF-8-SIG 文本，编码失败返回 loader error。
- 空文件、超大文件、非 Markdown 文件返回 loader error，不中断整体扫描。
- 计算基于规范化换行后的 `content_hash`。
- 按 source_path 排序，保证索引顺序稳定。

验收：

- 能列出 `my_md/doc_rag_corpus/**/*.md` 的文档元数据。
- 不会把 `my_md/rag/**/*.md`、测试结果、日志或自动生成报告纳入 v0 默认索引。
- 同一文件在不同机器根目录下应得到相同 `source_path`。
- `source_path` 不包含 `/home/...` 这类本地绝对路径。
- loader 可单元测试，不需要 SQLite、embedding API 或 LLM。
- loader errors 能被 indexer 转换为 `index_run_docs` 记录。

## Day 3：Chunker

目标：

- 按 Markdown 标题和段落切块。
- 保留 heading_path。
- 识别 heading、paragraph、list、code_block、table、blockquote 等基础 block。
- 保护代码块、表格和列表，避免随意切断结构。
- 控制 target_chunk_chars、max_chunk_chars、min_chunk_chars 和 chunk_overlap_chars。
- 只在超长 block fallback split 时使用 overlap。
- 生成稳定 chunk_id。
- 生成 chunk_key、chunk_content_hash 和 document_content_hash。
- 记录 chunk metadata：chunk_key、chunk_content_hash、document_content_hash、heading_level、block_types、start_line、end_line、split_reason、has_code、has_table、has_list。

验收：

- 每个 chunk 能追溯到原始文件和标题。
- chunk 不应过短或过长。
- heading_path 能正确反映 Markdown 标题层级。
- 代码块不会被普通段落合并逻辑切断。
- 表格过长切分时能保留表头。
- chunk_id 基于 source_path、heading_path、chunk_index 和 chunk_content_hash 生成。
- chunk_key 基于 source_path、heading_path 和 chunk_index 生成。
- 内容变化时 chunk_id 应变化；同一逻辑位置可通过 chunk_key 关联。

## Day 4：Embedding 和 Store

目标：

- 为 chunk 生成 embedding。
- 通过 `DocEmbeddingClient.embed_texts` 批量生成 embedding。
- 解析 `doc_rag.embedding.mode`，支持 `inherit_memory` 和 `custom`。
- 校验每条 embedding 维度。
- 构造 embedding text 时加入 heading_path 和 source_path 上下文。
- 存储 chunk 元数据和向量。
- 第一版使用独立 SQLite + sqlite-vec。
- Document RAG 拥有独立 embedding 配置块，默认继承 memory2 配置，可切换为 custom。
- 配置模型应新增 DocRagConfig 及 sources/chunking/embedding/retrieval/trace/citation/eval 子配置。
- `enabled = false` 为 v0 默认值，避免影响现有 Agent 行为。
- `schema_version`、`index_format_version`、`index_config_hash` 不兼容时，retriever 返回 index_stale / schema_mismatch，而不是继续使用旧索引。
- `chunks.embedding` 保留 JSON 副本，`vec_chunks` 用于向量检索。
- `chunks.embedding_status` 管理 pending / ready / failed 状态。
- `chunks_fts` 在 v0 建表并同步，但默认不参与 `search_docs` 召回。
- 记录 `index_runs`、`index_run_docs` 和 `meta`，支持调参、重建判断和失败排查。
- `DocRagStore.replace_document_chunks` 封装文档级原子替换，外部 indexer 不直接操作删除/插入细节。
- `DocEmbeddingClient` 不直接写 `embedding_status`，由 indexer/store 根据 embedding 结果写入。
- indexer 负责判断 new / changed / skipped_unchanged / deleted。
- changed/new 文档必须 chunks + embeddings 全部准备成功后才替换旧索引。
- loader error 记录到 `index_run_docs`，不直接导致整个 run failed。
- 系统级配置、schema、store、embedding client 错误导致整个 run failed。
- 可选支持 dry_run，用于预览 indexed / skipped / deleted / failed。

验收：

- 能重建索引。
- 能按 chunk_id 查询 chunk。
- sqlite-vec 可用时走 KNN；不可用时能基于 JSON embedding 做 fallback。
- `documents.content_hash` 不变时跳过重建；变化时重建该文档 chunks。
- embedding 失败的 chunk 不影响其他 chunk 索引，且不会进入默认检索。
- embedding 维度不匹配时能记录 `embedding_dim_mismatch`，系统级配置错误应让本次 index run failed。
- `embedding_mode/model/base_url/dim` 写入 meta，`api_key` 不写入 meta。
- `embedding_batch_size/max_retries/timeout` 变化不触发 rebuild。
- FTS5 能随 chunks 同步，但 v0 默认检索结果仍来自 vector-only。
- 当前配置与 `meta` 中索引关键配置不兼容时，检索应返回 index_stale，而不是继续使用旧索引。
- api_key 不得写入 meta、trace 或 eval report。
- 支持显式 rebuild，重建后 `meta` 和 `index_runs.config_json` 能记录新的索引配置。
- 单文档索引失败时，`index_run_docs` 能记录 source_path、action、status、error。
- 有文档失败但整体任务继续时，`index_runs.status = partial_failed`。
- 旧文档更新失败时，旧 chunks / vec_chunks 仍可检索，不会先删后失败。
- new 文档 embedding 失败时不会进入 active documents。
- deleted 文档能标记 `documents.status = deleted` 并清理 chunks / vec_chunks。
- `docs_scanned/docs_indexed/docs_skipped/docs_deleted/docs_failed` 统计准确。
- loader / chunker 单元测试不需要连接 SQLite。
- tools 不直接操作 SQL，只通过 retriever 或 store 查询。

## Day 5：Retriever

目标：

- 实现 `search(query, top_k)`。
- 使用 `DocEmbeddingClient` 生成 query embedding。
- 使用 `DocRagStore.search_vector` 做 sqlite-vec vector-only 检索。
- 默认过滤 `documents.status = active` 和 `chunks.embedding_status = ready`。
- sqlite-vec 不可用时 fallback 到 JSON embedding 全表 cosine similarity。
- 返回 chunk_id、chunk_key、score、distance、score_type、source_path、heading_path、snippet。
- 写 retrieval trace，记录 fallback_used、score_type、latency、hits 和 error。

验收：

- 对 5 个手工问题能召回相关 chunk。
- index_stale 时返回明确错误，不继续使用旧索引。
- empty_index / no_hits 返回空结果，不伪造答案。
- fallback 路径可用，且 trace 中能看到 fallback_used。
- score_type 能区分 sqlite_vec_distance_converted 和 cosine_similarity。

## Day 6：工具接入

目标：

- 实现 `search_docs`。
- 实现 `fetch_doc_chunk`。
- 注册到 `ToolRegistry`。
- `search_docs` 调用 `DocRetriever.search`，默认只返回 snippet。
- `fetch_doc_chunk` 调用 `DocRagStore.get_chunk`，按 max_chars 截断 content。
- 工具返回结构化 JSON，不返回大段自然语言。
- 错误使用结构化 error_code：doc_rag_disabled、index_stale、empty_index、chunk_not_found、invalid_top_k 等。
- 区分 Document RAG 工具和 `recall_memory`：前者查文档知识库，后者查用户长期记忆。

验收：

- CLI 中 Agent 可以调用文档检索工具。
- `search_docs` 返回 trace_id、hit_count、chunk_id、source_path、heading_path、score、snippet。
- `fetch_doc_chunk` 能按 chunk_id 读取内容，并遵守 max_chars。
- invalid_top_k / invalid_chunk_id / chunk_not_found 能返回结构化错误。
- search_docs 默认不返回完整 content，避免上下文膨胀。

## Day 7：Citation 与评估集 v0

Citation 目标：

- Agent 使用 Document RAG 结果回答时，关键结论必须带来源。
- 面向用户的引用格式使用 `[source_path > heading_path]`。
- 不默认暴露 `chunk_id`，但 trace / eval / debug 必须保留 `chunk_id`。
- 检索失败、索引为空或索引过期时，不允许编造文档引用。
- 区分“文档依据”和“模型建议”：前者需要 citation，后者不能伪装成文档结论。

Citation 验收：

- 至少 5 个文档问答能输出正确的 `[source_path > heading_path]`。
- 引用中的 `source_path` 必须来自 `search_docs` 或 `fetch_doc_chunk` 返回结果。
- 引用中的 `heading_path` 必须来自检索 hit，不由模型自由编造。
- 如果 `search_docs` 返回 no_hits，最终回答应说明没有可引用证据。
- 同一文档同一章节的多个 chunk 不应在回答里重复堆叠引用。

评估集目标：

- 准备 20-30 条问题。
- 使用 `my_md/rag/eval_sets/doc_rag_eval_v0.jsonl` 记录评估集。
- 使用 `my_md/rag/eval_sets/README.md` 记录字段说明和维护规则。
- 使用 `my_md/rag/eval_reports/` 保存每次运行报告。
- 标注 category、question、expected_sources、expected_answer_points、expected_tools。
- case 必填字段包括 id、category、question、expected_sources、expected_answer_points、expected_tools、citation/no-evidence 预期、difficulty、tags。
- expected_sources v0 先标 `source_path + heading_path`，不强制标 `chunk_id`。
- 覆盖 fact_lookup、design_rationale、pipeline_reasoning、boundary_distinction、no_evidence、multi_hop。
- 首批 ID 使用 `DRAG-V0-001` 到 `DRAG-V0-030`。
- 实现 Recall@k / MRR 计算。
- 实现 retrieval-only runner。
- 实现 agent e2e runner。
- 输出 JSON 和 Markdown 两种评估报告。

验收：

- 能输出一份评估报告。
- retrieval-only runner 能统计 Recall@1、Recall@3、Recall@5、MRR、expected source hit、expected heading hit。
- agent e2e runner 能记录工具调用、最终回答、citation、失败原因、latency、token usage。
- 每个失败 case 必须记录 `primary_failure_reason`，可选记录多个 `failure_reasons`。
- failure_reason 必须使用标准枚举，避免自由文本导致后续统计困难。
- no_evidence 类问题不能编造文档引用。

## Day 8：参数优化

目标：

- 调整 target_chunk_chars。
- 调整 max_chunk_chars。
- 调整 min_chunk_chars。
- 调整 chunk_overlap_chars。
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
- v0 先写入 `~/.akashic/workspace/doc_rag/retrieval_traces.jsonl`。
- 默认只记录 snippet，不记录完整 content。
- 提供 `include_content` 和 `max_content_chars` 配置，开发/测试阶段可记录截断后的完整 chunk 内容。
- 记录 `content_truncated`，避免误以为 trace 中看到的是完整原文。
- 失败检索也记录 trace。
- 后续可接 Dashboard 或迁移到数据库表。

验收：

- 每次 search_docs 都有 JSONL trace。
- trace 中包含 query、top_k、filters、embedding 配置、index_run_id、latency、hits、error。
- `include_content=false` 时 hit 不含完整 content。
- `include_content=true` 时 hit 包含 content 和 content_truncated。
- `max_content_chars` 生效，超长 chunk 不会无限写入 trace。

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
