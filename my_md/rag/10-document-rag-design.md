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

## 设计记录规则

后续凡是涉及方案选型，都必须记录四件事：

- 为什么选择这个方案。
- 为什么暂时不用其他方案。
- 这个方案带来的好处。
- 这个方案解决了当前项目里的什么问题。

原因：

- RAG 的效果高度依赖切块、索引、召回、重排和生成层参数，不能只记录“最后用了什么”。
- 后续需要做性能和效果对比时，必须能回到某个设计版本，理解当时的取舍。
- 面试表达时，不只要说“我用了某框架/某向量库”，还要能解释为什么它适合当前阶段。

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

第一版只处理专门整理过的 Markdown 测试语料：

```text
my_md/doc_rag_corpus/**/*.md
```

原因：

- Markdown 结构清晰，适合按标题切块。
- 专门语料目录相对稳定，适合做 Recall@k、MRR、证据命中和答案忠实度评估。
- 现有散落在 `my_md`、`README.md`、`_handbook` 中的文档更新频率高，不适合作为 v0 baseline 数据源。
- 将“原始学习记录”和“RAG 知识库语料”分开，避免临时笔记、测试日志、错误记录污染检索。
- 便于验证 citation 和 heading_path。

为什么不默认索引现有散落 Markdown：

- 学习文档会持续更新，索引结果会频繁变化，评估不可复现。
- 测试报告、调试记录、失败日志可能被误当作知识源。
- `README.md`、`_handbook` 等文档虽然有价值，但它们不是专门为当前 Document RAG 评估设计的稳定语料。
- v0 更重要的是建立可控 baseline，而不是追求覆盖所有材料。

推荐语料目录：

```text
my_md/doc_rag_corpus/
  README.md
  agent-runtime.md
  memory-design.md
  tool-governance.md
  document-rag-design.md
  plugin-system.md
```

治理规则：

- 进入 `doc_rag_corpus` 的文档应当是人工整理后的稳定知识。
- 临时讨论、测试输出、错误日志、自动生成报告默认不进入该目录。
- 如果某份学习笔记值得进入 RAG，应先整理成稳定 Markdown，再放入该目录。

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
chunk_key
doc_id
source_path
title
heading_path
chunk_index
content
chunk_content_hash
document_content_hash
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

## models 与 store 最小接口

v0 先定义清楚内部数据对象和存储边界：

```text
models.py 定义稳定数据对象
store.py 封装 SQLite / sqlite-vec 读写
indexer.py 负责编排 loader / chunker / embedder / store
retriever.py 负责编排 embedder / store.search_vector
```

### models.py

v0 最小模型：

```text
DocConfig
LoadedDocument
LoaderError
LoaderResult
DocumentRecord
ChunkRecord
IndexRun
IndexRunDoc
RetrievalHit
SearchResult
```

职责说明：

- `DocConfig`：表示当前 Document RAG 配置快照，包括 source_root、include_globs、exclude_globs、chunk 参数、embedding 配置、trace 配置。
- `LoadedDocument`：表示 loader 读出的文档全文，包括 doc_id、source_path、title、content、content_hash、file_mtime、file_size、metadata。
- `LoaderError`：表示单个文件在扫描或读取阶段的错误，包括 source_path 或 raw_path、error_type、message。
- `LoaderResult`：表示一次 loader 执行结果，包括 documents 和 errors。
- `DocumentRecord`：表示一个原始文档，包括 doc_id、source_path、title、content_hash、file_mtime、file_size、status。
- `ChunkRecord`：表示一个检索单元，包括 chunk_id、chunk_key、doc_id、source_path、heading_path、chunk_index、content、chunk_content_hash、document_content_hash、embedding_status。
- `IndexRun`：表示一次索引任务，包括 run_id、status、计数、config_json、started_at、finished_at。
- `IndexRunDoc`：表示一次索引任务中单个文档的处理结果，包括 run_id、source_path、action、status、hash 变化、chunk 数和错误。
- `RetrievalHit`：表示一次召回命中的 chunk，包括 chunk_id、chunk_key、source_path、heading_path、score、snippet、chunk_content_hash。
- `SearchResult`：表示一次检索结果，包括 query、top_k、hits、latency_ms、error、index_run_id。

为什么这样拆：

- 文档身份、检索单元、索引可观测性和检索结果是四类不同概念，混在一个对象里会导致职责不清。
- loader、chunker、indexer、retriever 可以通过模型对象传递数据，而不是互相依赖数据库字段。
- 后续写评估和 trace 时，可以直接复用 `RetrievalHit` / `SearchResult`，减少重复结构。

### store.py

v0 只设计一个 `DocRagStore`，内部负责 SQLite + sqlite-vec。

最小接口：

```python
class DocRagStore:
    def init_schema(self) -> None: ...

    def get_meta(self) -> dict: ...
    def write_meta(self, meta: dict) -> None: ...
    def validate_index_compatible(self, config: DocConfig) -> None: ...

    def start_index_run(self, config: DocConfig) -> IndexRun: ...
    def finish_index_run(self, run_id: str, status: str, error: str | None = None) -> None: ...
    def record_index_run_doc(self, record: IndexRunDoc) -> None: ...

    def get_document(self, source_path: str) -> DocumentRecord | None: ...
    def upsert_document(self, document: DocumentRecord) -> None: ...
    def mark_document_deleted(self, doc_id: str) -> None: ...

    def replace_document_chunks(
        self,
        document: DocumentRecord,
        chunks: list[ChunkRecord],
        embeddings: list[list[float]],
    ) -> None: ...

    def get_chunk(self, chunk_id: str) -> ChunkRecord | None: ...

    def search_vector(
        self,
        query_embedding: list[float],
        top_k: int,
        filters: dict | None = None,
    ) -> list[RetrievalHit]: ...
```

为什么 `replace_document_chunks` 必须在 store 里：

- 文档级原子替换涉及删除旧 `vec_chunks`、删除旧 `chunks`、写入新 `chunks`、写入新 `vec_chunks`、更新 `documents`。
- 这些操作必须在同一个 SQLite transaction 中完成。
- 如果把删除和写入散落在 indexer 中，失败恢复会变得不可靠。
- store 封装后，indexer 只需要准备好 document、chunks、embeddings，再交给 store 原子替换。

为什么 loader / chunker 不直接碰数据库：

- loader 只负责扫描和读取文件。
- chunker 只负责把 raw content 切成 chunk。
- 这样可以单独测试 loader / chunker，不需要启动 SQLite 或 embedding。
- 数据库 schema 变化时，不影响 loader / chunker 的核心逻辑。

为什么 v0 不拆成很多 store：

- 暂不拆 `DocumentStore`、`VectorStore`、`TraceStore`、`CollectionStore`，避免过度工程。
- 当前只有一个 SQLite 数据库和一个 sqlite-vec 向量空间，一个 `DocRagStore` 足够清晰。
- 等后续迁移 Qdrant / pgvector 或支持多 collection，再抽象 `DocVectorStore`。

推荐依赖方向：

```text
config.py -> DocConfig
loader.py -> DocumentRecord + raw_content
chunker.py -> ChunkRecord list
indexer.py -> loader + chunker + embedder + store
store.py -> SQLite + sqlite-vec
retriever.py -> embedder + store.search_vector
tools.py -> retriever + store.get_chunk
```

约束：

- `store.py` 不依赖 LLM。
- `loader.py` 和 `chunker.py` 不依赖 `store.py`。
- `tools.py` 不直接写 SQL。
- `retriever.py` 不依赖 loader / chunker。

这个方案的好处：

- 后续实现顺序清楚。
- 单元测试边界清楚。
- 数据库实现可以替换，但上层流程不需要大改。
- 面试时可以清楚解释 Document RAG 的工程分层。

## Markdown Loader 设计

Markdown loader 是 Document RAG 的入口层。

职责：

```text
从配置指定的稳定语料目录中，找出应该进入 RAG 的 Markdown 文件，并转换成 LoadedDocument。
```

loader 做：

```text
1. 根据 DocConfig.source_root 定位 repo root
2. 应用 include_globs / exclude_globs 扫描文件
3. 只接受 .md / .markdown 文件
4. 过滤空文件、目录、非法路径和 repo 外 symlink
5. 读取文本内容
6. 生成 repo 相对 POSIX source_path
7. 计算 content_hash
8. 提取 title
9. 返回 LoaderResult(documents, errors)
```

loader 不做：

```text
不切 chunk
不调用 embedding
不写 SQLite
不判断是否需要重建
不做 LLM 清洗
```

为什么这样划分：

- loader 只负责“语料进入系统”的读取和规范化。
- 切块、embedding、是否重建属于后续 indexer/chunker/store 职责。
- 这样 loader 可以独立单元测试，不依赖 SQLite、embedding API 或 LLM。

### 扫描规则

v0 默认：

```text
source_root = repo root
include_globs = ["my_md/doc_rag_corpus/**/*.md"]
exclude_globs = [
  "**/*.db",
  "**/*.sqlite",
  "**/*.jsonl",
  "**/*.log",
  "**/__pycache__/**",
  "**/.pytest_cache/**"
]
```

扫描流程：

```text
1. 从 source_root 解析 include_globs
2. 收集候选文件
3. 去重
4. 应用 exclude_globs
5. 检查后缀必须是 .md 或 .markdown
6. 规范化为 repo 相对 POSIX source_path
7. 按 source_path 排序后返回
```

为什么排序：

- 文件系统遍历顺序在不同机器上可能不同。
- 稳定排序能让 index run、日志、评估报告更容易复盘。

### 路径安全

规则：

```text
文件必须在 source_root 内
source_path 必须是 repo 相对路径
source_path 不能以 ../ 开头
默认不跟随指向 repo 外部的 symlink
不把绝对路径写入 source_path
```

symlink 策略：

```text
allow_external_symlink = false
```

- 指向 repo 内的 symlink 可以允许，但 `source_path` 使用 symlink 在 repo 内的位置。
- 指向 repo 外的 symlink 默认拒绝。

为什么这样设计：

- repo 外文件不可迁移，不适合作为 v0 baseline 语料。
- 避免把个人目录、临时文件或外部资料意外纳入知识库。
- 保持 `source_path`、citation 和评估集稳定。

### 编码策略

v0 采用：

```text
默认按 UTF-8 读取
失败后用 utf-8-sig 重试
仍失败则跳过，并返回 LoaderError(decode_error)
```

为什么不默认自动猜编码：

- 自动猜编码会引入不确定性。
- v0 corpus 由项目维护，应要求使用 UTF-8。
- 遇到非 UTF-8 文件应显式暴露问题，而不是静默转换。

### 空文件和大文件

空文件：

```text
content.strip() == "" -> LoaderError(skip_empty)
```

过大文件：

```text
max_file_size_bytes = 2MB
超过则 LoaderError(skip_too_large)
```

为什么限制大文件：

- v0 corpus 是人工整理 Markdown，不应出现超大日志或导出文件。
- 大文件会增加内存、切块和 embedding 成本。
- 超大文件通常意味着入口语料治理出了问题。

### content_hash

计算规则：

```text
normalized_text = 去掉 UTF-8 BOM + 统一换行 \r\n -> \n
content_hash = sha256(normalized_text.encode("utf-8"))
```

不做：

```text
不 trim 正文
不 lowercase
不删除空格
不做 Markdown 格式清洗
```

为什么不做过度规范化：

- 空格、大小写和 Markdown 格式变化可能代表真实内容变化。
- 过度规范化会隐藏文档变化，影响增量索引判断。

### title 提取

优先级：

```text
1. 第一个一级标题：# xxx
2. 如果没有一级标题，用第一个非空标题：## xxx / ### xxx
3. 如果没有标题，用文件名 stem
```

### 错误类型

loader 不因为单个文件失败而中止整个扫描。

建议错误类型：

```text
skip_empty
skip_too_large
decode_error
outside_source_root
external_symlink
not_markdown
read_error
```

为什么 loader 不直接写 `index_run_docs`：

- loader 不知道当前 run_id。
- loader 不应该依赖 store。
- indexer 负责把 `LoaderError` 转成 `index_run_docs` 记录。

### 推荐接口

```python
class MarkdownLoader:
    def __init__(self, config: DocConfig): ...

    def scan(self) -> list[Path]: ...

    def load_path(self, path: Path) -> LoadedDocument | LoaderError: ...

    def load_all(self) -> LoaderResult: ...
```

这个方案的好处：

- 入口语料边界清楚。
- 扫描顺序稳定。
- 错误可记录、可复盘。
- loader 可独立测试。
- 后续 indexer 可以统一处理 documents 和 errors。

## 切块方案选型

v0 采用：

```text
Markdown 标题结构优先 + 段落合并 + 长段落再截断
```

为什么选择这个方案：

- 当前第一批数据来自 `my_md/doc_rag_corpus/**/*.md`，会人工整理成稳定 Markdown 结构。
- Markdown 标题能提供稳定的 `heading_path`，适合后续 citation。
- 技术文档里经常有代码块、列表、配置项和表格，结构感知切块比纯固定长度更不容易破坏语义。
- 实现复杂度适中，适合作为可评估的 v0 baseline。

为什么暂时不用其他方案：

- 不用纯固定长度切块：容易切断标题、代码块、表格和配置说明，引用也不清楚。
- 不用 semantic chunking：需要额外 embedding 或语义边界判断，成本更高，v0 不利于先跑通闭环。
- 不用 query-adaptive chunking：工程复杂度高，适合后续优化，不适合第一版 baseline。
- 不用 LLM adaptive chunking：成本、延迟和不确定性更高，不利于建立稳定评估基线。

这个方案的好处：

- chunk 有明确主题。
- 每个 chunk 能回到原始文件和标题路径。
- 检索结果更容易解释。
- 后续可以自然升级到 hybrid search、rerank、semantic chunking 或 GraphRAG。

解决的问题：

- 解决文档检索中“召回片段无法定位来源”的问题。
- 降低 chunk 被切断导致答案不完整的风险。
- 为后续 `fetch_doc_chunk` 和 citation 提供稳定定位依据。

## Markdown Chunker 设计

Markdown chunker 的目标：

```text
让每个 chunk 语义完整、来源清楚、长度可控、可被稳定引用。
```

输入：

```text
LoadedDocument
```

输出：

```text
list[ChunkRecord]
```

chunker 做：

```text
1. 解析 Markdown 标题和块级结构
2. 维护 heading_path
3. 保护代码块、表格、列表等结构
4. 同一 heading_path 下合并短 block
5. 对超长 block 做 fallback split
6. 生成 chunk_content_hash
7. 生成 chunk_id
8. 写入 chunk metadata
```

chunker 不做：

```text
不读文件
不写 SQLite
不调用 embedding
不做检索
不调用 LLM 改写内容
```

### heading_path

chunker 维护 Markdown 标题栈：

```text
# Agent Runtime
## Agent Loop
### Tool Call
```

生成：

```text
heading_path = "Agent Runtime > Agent Loop > Tool Call"
```

如果内容出现在任何标题之前：

```text
heading_path = document.title
```

为什么必须有 `heading_path`：

- citation 更清楚。
- 检索结果更容易解释。
- `fetch_doc_chunk` 能展示来源章节。
- 评估集可以标注 expected heading。

### 块级解析

v0 不要求完整 Markdown AST，但需要识别基础 block：

```text
heading
paragraph
list
code_block
table
blockquote
horizontal_rule
```

重点保护：

```text
code_block
table
list
```

为什么要保护这些结构：

- 代码块被切断后很难用于回答。
- 表格行被拆散后，字段和值可能失去对应关系。
- 列表项被切成孤立碎片后，语义不完整。

### 合并和切分参数

v0 建议明确使用字符级参数作为 baseline：

```text
target_chunk_chars = 1600
max_chunk_chars = 2400
min_chunk_chars = 300
chunk_overlap_chars = 200
```

为什么先用 char 而不是 token：

- 实现简单，便于先跑通 baseline。
- Markdown corpus 是中文/英文混合，char 估算足够用于 v0。
- 后续可以增加 token-aware chunker 做对比实验。

段落合并规则：

```text
1. 同一 heading_path 下连续 block 尽量合并
2. 合并后不超过 max_chunk_chars
3. 小于 min_chunk_chars 的短 block，尽量和前后同标题内容合并
4. 遇到新标题，优先开启新 chunk
5. 标题文本进入 chunk content，避免 chunk 脱离主题
```

### 长块 fallback split

如果单个 block 超过 `max_chunk_chars`：

```text
普通段落 -> 按句子优先切分，失败时按字符切分
代码块 -> 尽量整体保留；过长时按行切分，并标记 split_reason = code_block_too_large
表格 -> 尽量整体保留；过长时按行切分，并复制表头到每个子 chunk
列表 -> 尽量按 list item 边界切分
```

为什么只在 fallback split 时使用 overlap：

- 普通 chunk 全量 overlap 会制造重复内容，导致 top_k 多个结果高度相似。
- fallback split 才真正需要 overlap 来缓解跨边界信息断裂。
- 这能提高召回多样性，同时避免无意义重复。

### chunk_id

v0 区分三个概念：

```text
chunk_id              # 某一版具体 chunk 的内容版本 ID
chunk_key             # 文档中某个逻辑位置的相对稳定 ID
chunk_content_hash    # chunk 正文内容 hash
document_content_hash # 文档全文内容 hash
```

生成规则：

```text
chunk_content_hash = sha256(normalized_chunk_content)
chunk_id = sha1(source_path + heading_path + chunk_index + chunk_content_hash)[:16]
chunk_key = sha1(source_path + heading_path + chunk_index)[:16]
document_content_hash = LoadedDocument.content_hash
```

字段含义：

- `chunk_id`：表示“这一次切块结果中的这个具体内容版本”，用于 `fetch_doc_chunk`、trace、向量表关联。
- `chunk_key`：表示“这个文档中这个标题路径下的第 N 个逻辑位置”，用于对比同一位置前后版本。
- `chunk_content_hash`：判断 chunk 正文是否变化。
- `document_content_hash`：判断 chunk 属于哪个文档版本。

为什么 `chunk_id` 带上 `chunk_content_hash`：

- 内容变化后 chunk_id 变化，避免 trace、cache 和评估样本混淆。
- 同一文档同一章节同一 chunk 内容不变时，ID 尽量稳定。

为什么不只用 `source_path + heading_path + chunk_index`：

- 内容变化后 ID 不变，会让旧 trace 和新内容混在一起。
- 对评估复盘不友好。

为什么增加 `chunk_key`：

- 如果只保留 `chunk_id`，内容变化后无法知道新旧 chunk 是否来自同一逻辑位置。
- `chunk_key` 能帮助对比同一 source_path、heading_path、chunk_index 的前后版本。
- 后续做 chunk diff、评估样本迁移、trace 对比时有稳定锚点。

标题变化时：

```text
heading_path 变化 -> chunk_key 变化 -> chunk_id 变化
```

这是 v0 可接受的行为，因为 citation 章节已经变化，旧引用不应假装稳定。

段落插入时：

```text
chunk_index 可能变化 -> 后续 chunk_key / chunk_id 可能变化
```

v0 接受这个代价，原因是：

- corpus 是人工整理的稳定语料，变化频率应该低。
- v0 不做复杂 chunk diff 或语义对齐，先保证规则简单可解释。
- 文档级 `index_run_docs` 已记录 old_chunk_count、new_chunk_count、previous_content_hash、new_content_hash，可用于发现变化。

v1 可选增强：

```text
chunk_key = sha1(source_path + heading_path + first_n_chars_hash)
或使用相似度对齐新旧 chunks
```

v0 不做这些增强，因为它们会增加调试复杂度。

### metadata

每个 chunk 建议记录：

```text
chunk_key
chunk_content_hash
document_content_hash
heading_level
block_types
start_line
end_line
split_reason
has_code
has_table
has_list
chunker_version
```

这些字段用于排查：

- chunk 是否被异常切断。
- 表格或代码是否被切碎。
- heading_path 是否丢失。
- chunk 是否太短或太长。

### 为什么 v0 不用 LLM chunking

- 成本高。
- 不稳定。
- 难复现。
- 不利于建立 baseline。
- 当前 corpus 是 Markdown，结构信号已经足够。

### 为什么 v0 不用 semantic chunking

- 需要额外 embedding 或语义边界算法。
- 会引入更多参数。
- 失败时难以判断问题来自 chunker 还是 embedding。
- v0 先建立 heading-aware baseline 更清晰。

这个方案的好处：

- 保留 Markdown 结构和章节语义。
- 降低代码块、表格、列表被切断的概率。
- citation 和评估标注更清楚。
- 后续能和 fixed-size、semantic chunking、LLM chunking 做对比。

解决的问题：

- 解决 chunk 主题不清的问题。
- 解决 citation 不可解释的问题。
- 解决 top_k 重复和片段断裂的问题。
- 解决评估样本难标注的问题。

## 索引与存储层设计

v0 使用独立运行时数据库：

```text
~/.akashic/workspace/doc_rag/doc_rag.db
```

不放进 `memory2.db`。

为什么选择独立 `doc_rag.db`：

- Document RAG 和 memory RAG 的数据来源、生命周期、权限边界不同。
- 文档 chunk 是可重建索引数据，个人记忆是用户长期上下文资产，二者不应混合。
- 之前 session isolation 排查已经证明：临时信息进入 memory2 会污染后续 prompt；Document RAG 必须避免继续扩大 memory2 的职责。
- 独立数据库便于后续整体重建、删除、备份和迁移。

为什么不用 `memory2.db`：

- `memory2.memory_items` 面向个人记忆，包含 `memory_type`、`reinforcement`、`emotional_weight`、`happened_at` 等记忆专用字段。
- Document RAG 需要的是 `source_path`、`heading_path`、`chunk_index`、`content_hash`、citation 等文档专用字段。
- 混用会让“用户记忆”和“文档知识”在召回层难以隔离，增加误注入风险。

向量库 v0 选择：

```text
SQLite + sqlite-vec
```

为什么选择 SQLite + sqlite-vec：

- 当前项目 `memory2` 已经使用 sqlite-vec，工程栈一致。
- 不需要额外启动 Qdrant、Milvus、Postgres 等服务。
- 适合本地 agent 项目和学习型实验。
- 普通表和向量表都在同一个 SQLite 文件中，便于调试和备份。
- 可以保留 embedding JSON 副本，在 sqlite-vec 不可用时回退到全表扫描。

为什么暂时不用其他向量库：

- 不用 Qdrant：能力强，但需要独立服务，v0 会增加部署和运维复杂度。
- 不用 pgvector：适合已有 Postgres 的生产系统，但当前项目没有 Postgres 依赖。
- 不用 Milvus / Weaviate / Pinecone：偏生产规模或云服务，当前文档量和本地开发场景不需要。
- 不用 Chroma / LanceDB：原型速度快，但当前项目已有 sqlite-vec，继续复用更利于理解底层和减少新依赖。

这个方案的好处：

- 本地单文件数据库，部署简单。
- 与现有 memory2 技术路线一致，但数据边界清晰。
- 便于做参数实验、索引重建和回归对比。
- 未来可以通过 `DocVectorStore` 接口替换成 Qdrant 或 pgvector。

解决的问题：

- 解决 Document RAG v0 的向量检索落地问题。
- 避免把文档知识写入个人长期记忆。
- 降低新增 RAG 子系统的部署成本。

### Embedding 配置设计

Document RAG 不硬编码复用 memory2 embedding，而是拥有独立配置块，并提供继承 memory2 的模式。

推荐配置：

```toml
[doc_rag.embedding]
mode = "inherit_memory"  # inherit_memory | custom
model = ""
api_key = ""
base_url = ""
dim = 1024
batch_size = 16
max_retries = 2
timeout_seconds = 30
```

模式说明：

- `inherit_memory`：使用 `[memory.embedding]` 的 `model`、`api_key`、`base_url`，降低 v0 配置成本。
- `custom`：使用 `[doc_rag.embedding]` 自己的 `model`、`api_key`、`base_url`、`dim`，支持后续文档检索专项实验。

为什么选择这个方案：

- v0 可以默认继承 memory2 配置，少一套必填配置，降低跑通闭环的阻力。
- 后续如果要把 Document RAG 和 memory RAG 的 embedding 分开，只需要改配置，不需要改核心代码。
- 支持对文档检索单独做 embedding 模型对比实验。
- 能保持“配置可继承、能力可独立”的边界。

为什么不直接硬编码复用 memory2：

- 后续一旦想拆分模型，会变成代码改造。
- memory RAG 和 Document RAG 的最佳 embedding 模型不一定相同。
- 不利于记录 Document RAG 独立实验参数。

为什么不一开始强制 custom：

- 配置复杂度更高。
- 需要额外 API key / base_url 管理。
- v0 目标是先跑通 Document RAG 闭环，不应把配置复杂度前置。

这个方案的好处：

- 默认简单，后续灵活。
- 既能复用现有配置，也能支持独立优化。
- 更适合后续性能对比和面试表达。

解决的问题：

- 避免 v0 过度配置。
- 避免未来拆分 embedding 时出现较大迁移成本。
- 让 Document RAG 的索引版本能明确记录实际生效的 embedding 配置。

索引时写入 `meta` 的是最终生效配置：

```text
embedding_mode = inherit_memory/custom
embedding_source = memory.embedding/doc_rag.embedding
embedding_model = 实际模型名
embedding_base_url = 实际 base_url
embedding_dim = 1024
```

`api_key` 不写入 `meta`。

模型变更策略：

```text
embedding_mode / embedding_model / embedding_base_url / embedding_dim 任一变化
-> 要求全量重建 doc_rag 索引
```

原因：

- 不同模型的向量空间不能混用。
- 不同维度无法写入同一个 sqlite-vec 表。
- 即使维度相同，不同模型的相似度空间也不应混检。

### DocEmbeddingClient 设计

v0 新增：

```text
doc_rag/embedder.py
```

对外提供：

```text
DocEmbeddingClient
EmbeddingConfig
EmbeddingResult
EmbeddingBatchResult
```

职责：

```text
DocEmbeddingClient
- 根据 doc_rag.embedding.mode 解析实际 embedding 配置
- 批量生成 chunk embedding
- 校验 embedding 维度
- 标准化错误返回
- 不直接写 chunks 表
```

为什么封装 `DocEmbeddingClient`：

- Document RAG 可以默认继承 memory2 embedding 配置，但不应该把调用边界绑定死在 memory2。
- 后续要单独做 Document RAG embedding 模型实验，需要独立记录参数和结果。
- 批量 embedding、维度校验、失败重试是 Document RAG 索引流程的一部分，应该有自己的入口。
- chunk 级 `embedding_status` 和 `embedding_error` 由 indexer/store 写入，embedder 只返回结果。

为什么不是直接到处调用 `memory2` embedder：

- 不方便区分 memory RAG 和 Document RAG 的实验参数。
- 不方便给 Document RAG 加 batch_size、timeout、retry、维度校验。
- 后续从 `inherit_memory` 切换到 `custom` 时容易牵连 memory2。

推荐原则：

```text
复用底层实现，不复用模块边界。
```

也就是说，`DocEmbeddingClient` 内部可以复用现有 embedding 调用能力，但对上层暴露 Document RAG 自己的接口。

### 配置解析

模式：

```text
inherit_memory
- 使用 memory.embedding 的 model / api_key / base_url
- 使用 doc_rag.embedding 的 dim / batch_size / max_retries / timeout_seconds

custom
- 使用 doc_rag.embedding 自己的 model / api_key / base_url / dim
- 用于 Document RAG 专项 embedding 实验
```

写入 `meta`：

```text
embedding_mode
embedding_source
embedding_model
embedding_base_url
embedding_dim
embedding_batch_size
embedding_client_version
```

不写入：

```text
api_key
```

需要 rebuild 的变化：

```text
embedding_mode
embedding_model
embedding_base_url
embedding_dim
```

不需要 rebuild 的变化：

```text
embedding_batch_size
embedding_timeout_seconds
embedding_max_retries
```

原因：

- `embedding_mode/model/base_url/dim` 会改变向量空间或向量维度，必须 rebuild。
- batch_size、timeout、max_retries 只影响执行过程，不改变已生成向量的语义空间。
- 如果 `embedding_client_version` 改变了 embedding text 构造，则需要 rebuild；如果只是 retry、timeout 或错误封装变化，不需要 rebuild。

- 前者会改变向量空间或向量维度。
- 后者只影响执行过程，不改变已生成向量的语义空间。

### 批量 embedding

推荐接口：

```python
class DocEmbeddingClient:
    def embed_texts(self, texts: list[str]) -> EmbeddingBatchResult: ...
```

`EmbeddingBatchResult`：

```text
results: list[EmbeddingResult]
model
dim
provider
latency_ms
```

`EmbeddingResult`：

```text
index
embedding
status
error
```

为什么批量处理：

- indexer 不应该一个 chunk 调一次 API。
- batch_size 能减少网络开销和整体索引时间。
- 单条结果带 index，便于把失败映射回对应 chunk。

### 失败策略

单个 chunk embedding 失败：

```text
该 chunk embedding_status = failed
embedding_error = 错误摘要
index_runs.embedding_failed += 1
index_run_docs.embedding_failed += 1
继续处理其他 chunk / document
```

整批失败：

```text
按 max_retries 重试
仍失败后，该 batch 中所有 chunk 标记 failed
继续处理后续文档
```

系统级配置错误：

```text
缺 API key
base_url 无效
模型不可用
连续维度不匹配
```

处理方式：

```text
index_runs.status = failed
停止本次索引
```

为什么区分：

- 单个 chunk 失败可能是内容问题，不应阻塞整个知识库。
- 配置错误会影响所有 chunk，继续执行只会制造大量失败记录。

### 维度校验

每条 embedding 返回后必须校验：

```text
len(embedding) == embedding_dim
```

不一致时：

```text
status = failed
error = embedding_dim_mismatch
```

为什么必须校验：

- sqlite-vec 表是固定维度。
- 不同维度不能写入同一个向量表。
- 即使保存 JSON，也不能和当前向量空间混检。

### embedding text 构造

不要只把 chunk 正文直接送入 embedding。

v0 推荐：

```text
标题路径: {heading_path}
来源: {source_path}

{chunk.content}
```

为什么加入标题路径和来源：

- 短 chunk 可以获得章节上下文。
- 检索时更容易匹配模块名、章节名和概念问题。
- 不加入随机 chunk_id，避免污染语义。

### embedding cache 策略

v0 不单独设计复杂 cache。

原因：

- `chunks.embedding` 已经保存 JSON 副本。
- `chunk_content_hash` 可以用于判断旧 embedding 是否可复用。
- 复杂 cache 会带来一致性问题。

v0 可选简单复用：

```text
如果同一文档旧 chunk_content_hash 存在 ready embedding，可以由 indexer 复用旧 embedding。
否则重新 embedding。
```

这个复用逻辑放在 indexer，不放在 `DocEmbeddingClient`。

这个方案的好处：

- Document RAG 能复用现有 embedding 能力，但不绑定死 memory2。
- 支持独立 embedding 模型实验。
- 批量处理效率更高。
- 维度和失败可追踪。
- 职责边界清楚：embedder 产出向量，indexer/store 写状态。

## Indexer 完整流程设计

indexer 是 Document RAG v0 的编排层。

目标：

```text
把一批 Markdown 文档安全、可观测、可恢复地变成可检索的 chunks + vectors。
```

indexer 串联：

```text
config -> loader -> chunker -> embedding client -> store
```

indexer 做：

```text
1. 读取 DocConfig
2. 初始化 store schema
3. 校验 meta / schema / embedding / chunker 配置
4. 启动 index_run
5. 调用 loader.load_all()
6. 处理 loader errors
7. 对每个 LoadedDocument 判断 unchanged / changed / new
8. changed/new 文档进入 chunker
9. 调用 DocEmbeddingClient 批量生成 embedding
10. 调用 store.replace_document_chunks 做文档级原子替换
11. 记录 index_run_docs
12. 处理 deleted documents
13. 汇总 index_runs 状态：succeeded / partial_failed / failed
```

indexer 不做：

```text
不直接写 SQL
不直接调用底层 LLM provider
不自己实现 Markdown 解析
不自己实现 sqlite-vec 查询
```

### 总体流程

伪流程：

```text
run_index(config):
  store.init_schema()
  store.validate_index_compatible(config)

  run = store.start_index_run(config)

  loader_result = loader.load_all(config)

  for loader_error in loader_result.errors:
      store.record_index_run_doc(error -> failed/skipped)

  scanned_paths = set()

  for doc in loader_result.documents:
      scanned_paths.add(doc.source_path)

      old = store.get_document(doc.source_path)

      if old exists and old.content_hash == doc.content_hash:
          record skipped_unchanged
          continue

      chunks = chunker.chunk(doc)

      embedding_results = embedder.embed_texts(build_embedding_texts(chunks))

      if all required embeddings ready:
          store.replace_document_chunks(doc_record, chunks, embeddings)
          record indexed
      else:
          record failed

  handle_deleted_documents(scanned_paths)

  finish_index_run(status)
```

### 文档状态判断

按文档级 `content_hash` 判断：

```text
old 不存在 -> new
old.content_hash == loaded.content_hash -> skipped_unchanged
old.content_hash != loaded.content_hash -> changed
```

为什么按 document 粒度判断：

- 实现简单。
- v0 corpus 文档量可控。
- 与文档级原子替换策略一致。
- chunk 级 diff 可以等 baseline 稳定后再做。

### loader error 处理

loader error 不应让整个 run 失败。

例如：

```text
skip_empty
decode_error
external_symlink
skip_too_large
```

处理：

```text
index_run_docs.action = failed 或 skipped
index_run_docs.status = failed/skipped
error = loader error
继续处理其他文档
```

系统级错误才让整个 run failed：

```text
source_root 不存在
include_globs 非法
store_path 不可写
schema 不兼容
配置校验失败
```

### embedding 失败处理

v0 对单个 changed/new 文档采用严格策略：

```text
只要该文档任一 chunk embedding 失败
-> 不替换旧文档索引
-> index_run_docs.status = failed
-> index_runs.status 至少为 partial_failed
```

原因：

- 部分写入会让文档索引不完整。
- 不完整文档可能导致答案缺证据或误答。
- 旧文档更新失败时，保留旧索引比写入半成品更可靠。

整批 embedding 临时失败：

```text
按 max_retries 重试
仍失败 -> batch 内 chunk failed
该文档 failed
继续其他文档
```

系统级 embedding 错误：

```text
缺 API key
模型不可用
base_url 无效
连续维度不匹配
```

处理：

```text
index_runs.status = failed
停止本次索引
```

### 文档级原子替换

changed 文档必须先准备好：

```text
new chunks
new embeddings
new metadata
```

全部成功后再调用：

```text
store.replace_document_chunks(document, chunks, embeddings)
```

为什么：

- 避免先删旧 chunks 后 embedding 失败，导致文档从知识库消失。
- 替换要么整体成功，要么整体失败。
- 保证检索端只看到完整旧版本或完整新版本。

### deleted documents

loader 扫描结束后：

```text
active_docs - scanned_source_paths = deleted_docs
```

处理：

```text
documents.status = deleted
删除 chunks / vec_chunks
index_run_docs.action = deleted
index_run_docs.status = succeeded
```

说明：

- 如果文件不在当前 corpus 范围内，就不应继续作为 active 文档。
- include/exclude 改变会触发 rebuild，因此 deleted 判断和当前配置一致。

### run 状态判定

```text
succeeded
  所有需要处理的文档都成功；skipped_unchanged 不算失败

partial_failed
  至少一个文档 loader/chunker/embedding 失败，但其他文档成功或跳过

failed
  配置、schema、store、embedding client 系统级错误导致 run 无法继续

cancelled
  用户或系统中断
```

### index_run_docs action/status

建议 action：

```text
indexed
skipped_unchanged
deleted
failed
```

建议 status：

```text
succeeded
skipped
failed
```

例子：

```text
hash 没变:
action = skipped_unchanged
status = skipped

新文档成功:
action = indexed
status = succeeded

embedding 失败:
action = failed
status = failed

文件不在 corpus:
action = deleted
status = succeeded
```

### 计数规则

`index_runs` 汇总：

```text
docs_scanned
docs_indexed
docs_skipped
docs_deleted
docs_failed
chunks_created
chunks_deleted
embedding_failed
```

建议：

```text
docs_scanned = loader 成功读取的文档数 + loader error 数
```

这样能反映实际扫描范围，而不是只统计成功文档。

### dry-run

建议 v0.1 支持：

```text
dry_run = true
```

dry-run 做：

```text
扫描文件
比较 content_hash
输出哪些会 indexed / skipped / deleted / failed
不调用 embedding
不替换 chunks
不写 vec_chunks
```

为什么有用：

- 调试 include/exclude。
- 检查 corpus 范围。
- 避免误删误建。
- 在真实索引前预览影响面。

这个方案的好处：

- 索引过程可观测。
- 单文档失败不会破坏整个知识库。
- 旧索引不会被失败任务破坏。
- 评估时能知道文档是否成功进入索引。
- 后续可以扩展 chunk 级 diff 和 embedding cache，而不改变主流程。

## Retriever 设计

retriever 是 Document RAG 的检索执行层。

目标：

```text
把用户 query 转成 query embedding，并从 doc_rag.db 中找出最相关的 ready chunks。
```

retriever 做：

```text
1. 接收 query / top_k / filters
2. 校验当前索引是否可用
3. 调用 DocEmbeddingClient 生成 query embedding
4. 调用 DocRagStore.search_vector 做 sqlite-vec 检索
5. 过滤 documents.status = active
6. 过滤 chunks.embedding_status = ready
7. 组装 RetrievalHit / SearchResult
8. 写 retrieval trace
```

retriever 不做：

```text
不拼最终回答
不做 query rewrite
不做复杂 rerank
不直接写 chunks 表
不负责工具调用协议
```

### v0 检索策略

v0 采用：

```text
vector-only
top_k = 5
documents.status = active
chunks.embedding_status = ready
```

为什么先 vector-only：

- 建立干净 baseline。
- 方便评估 Recall@k / MRR。
- 避免 keyword、RRF、rerank 等变量干扰问题定位。
- 后续增加 hybrid search 时能清楚比较效果提升。

为什么不默认 hybrid：

- hybrid 会引入 keyword_top_k、rrf_k、融合权重等额外参数。
- 早期如果召回不好，很难判断问题来自向量、关键词还是融合。
- 当前目标是先验证文档索引和向量召回闭环。

### 异常处理

retriever 必须明确处理：

```text
index_stale
empty_index
query_embedding_failed
sqlite_vec_unavailable
no_hits
```

推荐行为：

```text
index_stale -> 返回明确错误，提示 rebuild
empty_index -> 返回空 SearchResult，不伪造答案
query_embedding_failed -> 返回 error，并写 trace
sqlite_vec_unavailable -> fallback 到 JSON embedding 全表余弦相似度
no_hits -> hits = []
```

为什么这样处理：

- 检索失败不应该伪装成“没有资料”。
- index_stale 是索引版本问题，必须提示 rebuild。
- empty_index 和 no_hits 是正常可恢复状态，不能让 Agent 编造答案。

### fallback 策略

因为 v0 保留：

```text
chunks.embedding JSON 副本
```

所以 sqlite-vec 不可用时可以 fallback：

```text
遍历 ready chunks
读取 embedding JSON
计算 cosine similarity
排序取 top_k
```

适用范围：

- 本地开发。
- sqlite-vec 扩展不可用。
- 调试向量表损坏或 KNN 查询异常。

不适合：

- 大规模生产数据。
- 高并发检索。

为什么仍然保留：

- v0 文档量小，fallback 成本可接受。
- 能降低 sqlite-vec 环境问题对调试的阻塞。
- 有助于验证 embedding 本身是否有效。

### score 设计

v0 返回：

```text
rank
score
distance
score_type
```

sqlite-vec 如果返回 distance：

```text
score = 1 / (1 + distance)
score_type = sqlite_vec_distance_converted
```

JSON fallback 使用 cosine：

```text
score = cosine_similarity
score_type = cosine_similarity
```

注意：

- 不同后端的 score 不应直接跨实验比较。
- trace 中必须记录 `score_type` 和 `fallback_used`。

### RetrievalHit

v0 返回字段：

```text
rank
chunk_id
chunk_key
doc_id
source_path
heading_path
score
distance
score_type
snippet
chunk_content_hash
document_content_hash
token_count
metadata
```

### SearchResult

v0 返回字段：

```text
query
normalized_query
top_k
filters
hits
hit_count
latency_ms
index_run_id
fallback_used
error
trace_id
```

### trace

每次检索写 JSONL trace：

```text
trace_id
query
normalized_query
top_k
filters
embedding_model
embedding_dim
vector_store
fallback_used
score_type
latency_ms
hit_count
hits
error
```

如果 `include_content = true`：

```text
content
content_truncated
```

为什么 retriever 写 trace：

- trace 记录的是检索层事实，不是最终回答。
- 能用于 Recall@k、证据命中、空召回和 fallback 排查。
- 后续 observe / dashboard 可以消费这些 trace。

### 推荐接口

```python
class DocRetriever:
    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: dict | None = None,
    ) -> SearchResult: ...
```

内部依赖：

```text
DocEmbeddingClient
DocRagStore
RetrievalTraceWriter
```

这个方案的好处：

- 检索链路简单可评估。
- v0 baseline 不被 hybrid/rerank 干扰。
- 错误、空结果和 fallback 都可观测。
- 后续可以自然扩展 query rewrite、hybrid search、RRF 和 rerank。

### v0 表结构

#### documents

记录原始文档级元数据。

```sql
CREATE TABLE documents (
    doc_id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'markdown',
    title TEXT,
    content_hash TEXT NOT NULL,
    file_mtime REAL,
    file_size INTEGER,
    status TEXT NOT NULL DEFAULT 'active',
    metadata_json TEXT,
    indexed_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

设计原因：

- 用 `content_hash` 判断文件是否变化。
- 用 `status` 支持文档删除和后续清理。
- 用 `metadata_json` 给后续 collection、标签、来源类型预留空间。
- 文档级信息不重复写入每个 chunk。

#### chunks

记录检索基本单元。

```sql
CREATE TABLE chunks (
    chunk_id TEXT PRIMARY KEY,
    chunk_key TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    source_path TEXT NOT NULL,
    title TEXT,
    heading_path TEXT,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    chunk_content_hash TEXT NOT NULL,
    document_content_hash TEXT NOT NULL,
    token_count INTEGER,
    char_count INTEGER,
    embedding TEXT,
    embedding_status TEXT NOT NULL DEFAULT 'pending',
    embedding_error TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);

CREATE INDEX ix_chunks_doc_id ON chunks(doc_id);
CREATE INDEX ix_chunks_chunk_key ON chunks(chunk_key);
CREATE INDEX ix_chunks_source_path ON chunks(source_path);
CREATE INDEX ix_chunks_heading_path ON chunks(heading_path);
```

设计原因：

- `chunk_id` 是 `search_docs` 和 `fetch_doc_chunk` 的稳定定位键。
- `chunk_key` 是逻辑位置锚点，便于对比同一位置的新旧 chunk。
- `heading_path` 支持可解释引用。
- `chunk_content_hash` 支持判断 chunk 内容变化。
- `document_content_hash` 支持关联 chunk 所属文档版本。
- `embedding TEXT` 保存 JSON 副本，方便 debug 和 sqlite-vec fallback。
- `embedding_status` 区分 `pending`、`ready`、`failed`，避免没有可用向量的 chunk 进入检索。
- `embedding_error` 记录单个 chunk 的 embedding 失败原因，便于重试和排查。

#### vec_chunks

记录 chunk 向量。

```sql
CREATE VIRTUAL TABLE vec_chunks USING vec0(
    embedding float[1024]
);
```

设计原因：

- 与 `chunks.rowid` 对齐，KNN 命中后回表读取 chunk 元数据。
- 维度默认复用当前 memory2 embedding 维度 1024。
- 如果后续 embedding 模型变更，需要全量重建索引。

#### chunks_fts

v0 预留关键词索引，但默认不启用 hybrid search。

```sql
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    content,
    source_path,
    heading_path,
    content='chunks',
    content_rowid='rowid',
    tokenize='trigram'
);
```

设计原因：

- 技术文档里有大量函数名、文件名、配置项、case id，纯向量检索对这类强关键词问题不一定稳定。
- 预留 FTS5 能让 v1 升级 hybrid search 时减少 schema 迁移。
- v0 仍保持 vector-only baseline，方便先评估纯向量召回效果。
- `trigram` 对中文、英文片段和代码标识符更友好，也和当前 `session/store.py` 中 messages FTS 的思路一致。

为什么 v0 不直接启用 hybrid：

- 第一版如果同时启用 vector、keyword、RRF，失败时难以判断问题来自哪一层。
- hybrid 需要额外设计 `keyword_top_k`、`rrf_k`、融合权重和评估对照。
- 当前优先目标是跑通 Document RAG 闭环，并建立稳定 baseline。

同步方式：

- 推荐使用 SQLite trigger 自动同步 `chunks` 到 `chunks_fts`。
- 插入、删除、更新 chunk 时由 trigger 维护 FTS。
- 后续启用 hybrid search 时，历史 chunk 已有关键词索引。

#### index_runs

记录索引运行过程。

```sql
CREATE TABLE index_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    docs_scanned INTEGER DEFAULT 0,
    docs_indexed INTEGER DEFAULT 0,
    docs_skipped INTEGER DEFAULT 0,
    docs_deleted INTEGER DEFAULT 0,
    docs_failed INTEGER DEFAULT 0,
    chunks_created INTEGER DEFAULT 0,
    chunks_deleted INTEGER DEFAULT 0,
    embedding_failed INTEGER DEFAULT 0,
    error TEXT,
    config_json TEXT
);
```

设计原因：

- RAG 调参时需要知道某次评估对应哪次索引配置。
- 便于快速判断一次索引整体是成功、失败还是部分失败。
- 便于后续 Dashboard / observe 展示索引状态。

`status` 建议取值：

```text
running
succeeded
partial_failed
failed
cancelled
```

状态含义：

- `succeeded`：本次扫描范围内所有需要处理的文档都处理成功。
- `partial_failed`：部分文档失败，但其他文档已经成功处理。
- `failed`：索引任务整体失败，通常是数据库、配置、schema 或初始化阶段错误。
- `cancelled`：用户或系统中断。

#### index_run_docs

记录一次索引运行中每个文档的处理结果。

```sql
CREATE TABLE index_run_docs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    doc_id TEXT,
    source_path TEXT NOT NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    previous_content_hash TEXT,
    new_content_hash TEXT,
    old_chunk_count INTEGER DEFAULT 0,
    new_chunk_count INTEGER DEFAULT 0,
    embedding_failed INTEGER DEFAULT 0,
    error TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    FOREIGN KEY (run_id) REFERENCES index_runs(run_id)
);

CREATE INDEX ix_index_run_docs_run_id ON index_run_docs(run_id);
CREATE INDEX ix_index_run_docs_source_path ON index_run_docs(source_path);
CREATE INDEX ix_index_run_docs_status ON index_run_docs(status);
```

`action` 建议取值：

```text
indexed             # 新文档或变更文档已索引
skipped_unchanged   # content_hash 没变，跳过
deleted             # 文件不存在，标记删除并清理索引
failed              # 本文档处理失败
```

为什么新增 `index_run_docs`：

- `index_runs` 只能回答“这次整体怎么样”，不能回答“哪个文档失败、为什么失败”。
- RAG 排查经常需要判断某个问题没召回是因为文档没索引，还是召回策略不好。
- 文档级记录能支持失败重试、评估排查和 Dashboard 展示。

为什么不只记录总数：

- `docs_failed = 3` 不足以判断失败的是核心文档还是无关笔记。
- 没有文档级错误，就无法定位失败原因和恢复范围。
- 后续 Recall@k 异常时，需要能从 expected source 反查该文档最近一次索引状态。

为什么 v0 不建 `index_run_chunks`：

- `chunks` 表已有 `embedding_status` 和 `embedding_error`，可以覆盖第一版 chunk 级失败排查。
- chunk 级运行表会显著增加写入量和实现复杂度。
- v0 更需要先解决文档级失败恢复；chunk 级延迟、重试次数、token 分布可以留到 v1。

### Index Run 失败恢复策略

v0 采用：

```text
继续处理其他文档 + 文档级原子替换 + 失败可重试
```

整体规则：

- 单个文档失败，不中断整次索引任务。
- 只要有文档失败，`index_runs.status = partial_failed`。
- 如果初始化、schema、数据库连接、配置校验失败，`index_runs.status = failed`。
- 新文档失败时，不进入 active documents。
- 旧文档更新失败时，保留旧索引，不让知识库突然缺文档。

变更文档的推荐流程：

```text
1. 读取旧 documents 记录和旧 chunks
2. 生成新 chunks
3. 生成新 embeddings
4. 新 chunks / embeddings 全部准备成功后
5. 在同一个 SQLite transaction 中删除旧 vec_chunks / chunks
6. 写入新 chunks / vec_chunks
7. 更新 documents.content_hash / indexed_at / updated_at
8. 写入 index_run_docs.status = succeeded
```

为什么选择文档级原子替换：

- 避免“先删旧索引，再 embedding 失败，导致该文档从知识库消失”。
- 单个文档处理失败时，不影响其他文档检索。
- 旧文档至少还能提供上一次成功索引的知识。
- 恢复策略清晰：下次只需要重试 failed 或 content_hash 不一致的文档。

为什么不让单文档失败导致整次 run failed：

- 文档索引是批处理任务，一个文件坏了不应阻塞其他文件。
- 对 RAG 来说，部分可用通常比整体不可用更有价值。
- `partial_failed` 能明确提醒“本次索引不是完全健康”，同时保留已成功处理的结果。

新文档失败策略：

```text
index_run_docs.status = failed
index_run_docs.error = 失败原因
documents 不标记 active
chunks / vec_chunks 不写入 ready 数据
```

旧文档更新失败策略：

```text
保留旧 documents / chunks / vec_chunks
index_run_docs.status = failed
记录 previous_content_hash 和 new_content_hash
提示当前索引落后于文件内容
```

删除文档策略：

```text
文件不存在 -> documents.status = deleted
删除对应 chunks / vec_chunks
index_run_docs.action = deleted
```

这个方案的好处：

- 能快速定位失败文档。
- 能保证旧索引不会因为一次失败重建而被破坏。
- 能支持后续只重试失败文档。
- 能让评估报告关联到具体 `index_run_id` 和文档处理状态。

解决的问题：

- 解决“某个文档没召回，但不知道是否被索引成功”的问题。
- 解决索引过程中部分失败导致知识库不一致的问题。
- 解决只记录总数无法复盘失败原因的问题。

#### meta

记录库级配置。

```sql
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

建议写入：

```text
schema_version = 1
index_format_version = doc_rag_v0
embedding_mode = inherit_memory
embedding_source = memory.embedding
embedding_model = text-embedding-v3
embedding_base_url = <resolved-base-url>
embedding_dim = 1024
embedding_batch_size = 16
embedding_client_version = doc_embedding_client_v0
chunker_version = markdown_heading_v0
target_chunk_chars = 1600
max_chunk_chars = 2400
min_chunk_chars = 300
chunk_overlap_chars = 200
source_path_mode = repo_relative
path_separator = posix_slash
vector_store = sqlite_vec
```

设计原因：

- schema 或 embedding 变化时能判断是否需要全量重建。
- 后续对比实验时能追溯索引版本。

### Schema Version 与重建策略

v0 采用：

```text
严格版本检测 + 显式重建
```

也就是：如果当前运行配置和 `meta` 中记录的索引配置不兼容，系统不继续静默使用旧索引，而是阻止检索并提示执行 rebuild。

为什么选择这个方案：

- RAG 的召回质量高度依赖索引版本，旧索引混入会让评估结果不可信。
- v0 的目标是建立可复盘 baseline，显式 rebuild 比自动迁移更容易定位问题。
- 自动迁移需要处理 schema 变更、向量维度变更、chunk 边界变化和失败回滚，复杂度较高。
- 阻止检索能避免“以为在测试新配置，实际仍在用旧索引”的问题。

为什么暂时不做自动 migration：

- 当前索引是可重建数据，不是用户不可丢失资产。
- v0 文档量预计较小，重建成本可接受。
- 自动迁移会引入额外失败模式，不利于早期调参和评估。
- schema、chunker、embedding 变化时，很多情况本质上不是迁移，而是必须重新生成 chunk 和向量。

必须重建的变化：

```text
schema_version 变化
index_format_version 变化
embedding_mode 变化
embedding_model 变化
embedding_base_url 变化
embedding_dim 变化
chunker_version 变化
target_chunk_chars 变化
max_chunk_chars 变化
min_chunk_chars 变化
chunk_overlap_chars 变化
source_path_mode 变化
path_separator 变化
vector_store 变化
```

为什么这些变化必须重建：

- embedding 相关变化会改变向量空间，旧向量不能和新向量混用。
- chunker 和 chunk 参数变化会改变 chunk 边界，旧 chunk 不再代表当前切块策略。
- path 规则变化会改变 `source_path`、`doc_id` 和 citation 身份。
- vector store 变化可能改变底层索引格式和查询方式。
- schema 不兼容时继续读取可能导致字段缺失、含义错误或查询异常。

不需要重建的变化：

```text
top_k
similarity_threshold
max_context_chars
trace_include_content
trace_max_content_chars
rerank_enabled
hybrid_search_enabled
```

为什么这些变化不需要重建：

- 它们属于查询层、注入层或观察层参数。
- 它们不改变 `documents`、`chunks`、`embedding` 和 `vec_chunks` 的内容。
- 可以用于同一索引版本下做检索参数实验。

检索前校验流程：

```text
1. 读取 doc_rag.db 的 meta
2. 解析当前运行配置
3. 对比必须一致的索引配置
4. 如果一致，允许检索
5. 如果不一致，返回 index_stale 错误，并提示 rebuild
```

错误提示示例：

```text
Document RAG index is stale:
- target_chunk_chars changed: indexed=1600, current=2200
- embedding_model changed: indexed=text-embedding-v3, current=xxx

Please rebuild the document index.
```

这个方案的好处：

- 每次评估都能明确对应一个索引版本。
- 旧索引不会静默污染新参数实验。
- 实现简单，失败模式清楚。
- 后续需要时可以在 v1 增加 `migrate` 命令，但不影响 v0 baseline。

解决的问题：

- 解决“代码和参数已变，但数据库还是旧索引”的隐性错误。
- 解决向量空间混用导致召回异常的问题。
- 解决不同切块策略下评估结果不可比较的问题。

### chunks 与 vec_chunks 同步策略

v0 使用：

```text
chunks.rowid <-> vec_chunks.rowid
```

为什么选择 rowid 对齐：

- sqlite-vec 的 KNN 查询天然返回 rowid，回表查询简单。
- 当前 `memory2` 已采用类似方式，项目内实现经验可复用。
- v0 不需要多向量空间、多索引映射或跨库映射。
- 少一张映射表，降低同步复杂度。

为什么不用单独映射表：

- 当前只有一个向量索引空间。
- `chunk_id` 已经作为外部稳定 ID，内部不需要再维护 `chunk_id -> vector_id`。
- 映射表会增加删除、重建和排查复杂度。

写入流程：

```text
1. chunk 写入 chunks，embedding_status = pending
2. 调用 embedding
3. embedding 成功后写 chunks.embedding JSON 副本
4. 使用 chunks.rowid 写入 vec_chunks
5. 成功后 embedding_status = ready
6. 失败时 embedding_status = failed，并写 embedding_error
```

embedding 失败策略：

- 单个 chunk embedding 失败，不中断整个 index run。
- 失败 chunk 保留在 `chunks` 中，状态为 `failed`，不参与默认检索。
- `index_runs.embedding_failed` 计数增加。
- 后续可以重试 failed chunk，或通过 JSON embedding / fallback 路径排查。

检索过滤规则：

```text
documents.status = active
chunks.embedding_status = ready
```

文档重建时的删除顺序：

```text
1. SELECT rowid FROM chunks WHERE doc_id = ?
2. DELETE FROM vec_chunks WHERE rowid IN (...)
3. DELETE FROM chunks WHERE doc_id = ?
4. 重新切块并写入 chunks / vec_chunks
```

为什么要先查 rowid：

- 删除 chunks 后就无法可靠知道对应 vec_chunks 的 rowid。
- 先收集 rowid 能保证向量表不会残留孤儿向量。

为什么保留 embedding JSON 副本：

- sqlite-vec 不可用时可以回退到 Python 全表余弦相似度。
- 便于 debug 维度、内容和向量是否匹配。
- 可以重建 `vec_chunks`，不必重新调用 embedding API。

代价：

- 数据库体积会变大。
- v0 文档量有限，这个代价可接受。

### FTS5 / Keyword Search 预留策略

v0 决策：

```text
建 chunks_fts
默认 search_docs 仍使用 vector-only
keyword_search 只作为内部 debug 能力
hybrid search 延后到 v1
```

为什么选择这个方案：

- 保留 v0 检索链路简单性。
- 避免后续新增 hybrid search 时再大改 schema。
- 技术文档天然包含大量关键词，预留 FTS5 是合理铺垫。
- 有助于后续对比 vector-only 与 hybrid 的 Recall@k / MRR。

为什么不完全推迟 FTS5：

- 后续补建 FTS5 需要 schema 迁移和历史数据 rebuild。
- 提前建表但不启用，对 v0 检索行为影响很小。

为什么不直接启用 hybrid：

- v0 需要先建立纯向量 baseline。
- hybrid 参数会引入额外变量，影响早期问题定位。
- 等有 20-30 条评估集和 baseline 指标后，再启用 RRF 更稳。

### Retrieval Trace 设计

v0 使用 JSONL 文件记录每次 `search_docs` 检索：

```text
~/.akashic/workspace/doc_rag/retrieval_traces.jsonl
```

为什么选择 JSONL：

- 实现简单，每次检索追加一行 JSON 即可。
- 不需要一开始设计复杂 trace schema 和迁移。
- 便于 `tail -f`、脚本分析和失败样本排查。
- trace 写入失败不应影响主检索链路。
- 结构可以随开发阶段逐步演化。

为什么暂时不用数据库表：

- 如果用 SQL 表，需要额外设计 `retrieval_traces`、`retrieval_trace_hits`、索引、清理策略和字段迁移。
- v0 更重要的是跑通 RAG 闭环和快速观察召回质量。
- 等 Dashboard、聚合统计、长期趋势分析需要时，再迁移到数据库表更合适。

默认配置：

```toml
[doc_rag.trace]
enabled = true
path = "~/.akashic/workspace/doc_rag/retrieval_traces.jsonl"
include_content = false
max_content_chars = 2000
```

为什么默认不记录完整 content：

- trace 文件会快速变大。
- chunk 原文已经在 `doc_rag.db` 中，可以通过 `chunk_id` 回查。
- 避免未来文档含敏感内容时，trace 成为第二份内容副本。
- 长期运行时只记录 snippet 更轻量。

为什么提供 `include_content` 开关：

- 开发和测试阶段需要直接看到完整 chunk，判断切块是否合理、召回结果是否完整、snippet 是否误导。
- 排查“召回到了但生成没用”这类问题时，只看 snippet 不够。
- 参数实验阶段需要观察 top_k chunk 之间是否重复、是否缺上下文。
- 做 Recall@k、证据命中和答案忠实度分析时，完整 content 能减少频繁回查数据库的成本。

`include_content = true` 时：

- trace hit 额外记录 `content`。
- `content` 最多保留 `max_content_chars` 字符。
- 超长时记录 `content_truncated = true`。

为什么不把完整 content 设为默认开启：

- 长期运行时 trace 会成为第二套文档内容存储，增加磁盘占用和清理成本。
- 如果后续索引公司文档、个人笔记或非公开资料，trace 默认保存全文会扩大敏感信息暴露面。
- 默认 snippet 更适合生产观察；需要深度排查时再临时打开 `include_content`。

开发/测试建议：

```text
平时运行：include_content = false
切块调试：include_content = true, max_content_chars = 4000
召回质量评估：include_content = true, max_content_chars = 8000
长期压测：include_content = false
```

这个方案的好处：

- 既能在开发阶段看清楚“到底召回了什么”，又不会让长期 trace 无限膨胀。
- 方便把同一条 query 的 query、score、snippet、content、source_path 放在一行 JSONL 中审查。
- 后续如果接入 Dashboard，可以先消费 JSONL；如果需要统计，再迁移到数据库表。

解决的问题：

- 解决只看 snippet 时难以判断 chunk 完整性的排查问题。
- 解决 trace 记录过重和调试信息不足之间的矛盾。
- 为后续 RAG 评估中的“证据命中”和“答案忠实度”提供可审查材料。

v0 trace 顶层字段：

```text
trace_id
ts
query
normalized_query
top_k
filters
embedding_mode
embedding_model
embedding_dim
vector_store
index_run_id
latency_ms
hit_count
hits
error
```

hit 字段：

```text
rank
chunk_id
chunk_key
doc_id
source_path
heading_path
score
snippet
chunk_content_hash
document_content_hash
token_count
content            # include_content=true 时记录
content_truncated  # include_content=true 时记录
```

失败也要记录 trace：

```json
{
  "query": "Document RAG 为什么不用 memory2",
  "hit_count": 0,
  "hits": [],
  "error": "embedding failed: timeout"
}
```

为什么失败也记录：

- RAG 失败可能来自 embedding API、向量库、过滤条件或空索引。
- 没有失败 trace，就无法统计系统稳定性。

v0 不记录最终 answer：

- Document RAG trace 只负责检索层。
- 最终回答属于 Agent turn / observe 层。
- 后续端到端评估可以用 `trace_id` 关联 `turn_id`、answer 和 judge score。

### ID 生成策略

`source_path` 使用 repo 相对路径，并统一为 POSIX 风格：

```text
README.md
my_md/rag/10-document-rag-design.md
_handbook/example.md
```

不使用绝对路径作为主身份字段：

```text
/home/jjh/git_work/akashic-agent/my_md/rag/10-document-rag-design.md
```

路径规范化规则：

```text
1. 以项目 repo root 作为 source_root
2. 被索引文件必须位于 repo root 下
3. 真实文件路径转为 repo 相对路径
4. 统一使用 / 分隔符
5. 去掉开头的 ./
6. 不做 lowercase，因为 Linux 路径大小写敏感
7. 默认不索引指向 repo 外部的 symlink
```

为什么选择 repo 相对路径：

- 同一个项目换机器、换用户名、换工作目录后，逻辑路径仍然稳定。
- 更适合 Git、评估集和 citation，引用的是项目内部文件，而不是某台机器上的物理路径。
- 避免 `/home/jjh/...` 这类本地信息进入索引、trace 和评估报告。
- `doc_id` 可以稳定复现，便于回归测试和历史 trace 对比。

为什么不用绝对路径：

- 绝对路径不可迁移，换机器、容器或 CI 环境后会变化。
- 如果 `doc_id` 基于绝对路径生成，同一文件在不同环境会得到不同 ID。
- 绝对路径会让 citation 和评估集绑定到个人电脑目录，不适合作为项目级文档身份。

绝对路径如何处理：

- v0 不把绝对路径作为 `source_path`。
- 如果开发调试确实需要，可以在 `metadata_json` 中可选记录 `abs_path_debug`。
- `abs_path_debug` 不参与 `doc_id`、`chunk_id`、citation 和评估标注。

多知识库预留：

```text
v0: doc_id = sha1(source_path)[:16]
v1: doc_id = sha1(collection_id + ":" + source_path)[:16]
```

为什么 v0 暂不引入 `collection_id`：

- 当前第一阶段只索引当前 repo 内文档。
- 提前加入 collection 会增加配置和测试复杂度。
- 后续如果同时索引多个 repo、网页或外部资料，再升级 ID 生成规则。

这个方案的好处：

- 文档身份稳定。
- citation 可读。
- 评估集可迁移。
- trace 不依赖本地机器目录。

解决的问题：

- 解决同一文档在不同环境下 ID 不一致的问题。
- 解决绝对路径泄漏和不可迁移问题。
- 为后续 Recall@k、证据命中、答案忠实度评估提供稳定 source 标识。

```text
doc_id = sha1(normalized_source_path)[:16]
chunk_key = sha1(source_path + heading_path + chunk_index)[:16]
chunk_id = sha1(source_path + heading_path + chunk_index + chunk_content_hash)[:16]
```

为什么不用自增 ID：

- 自增 ID 在重建索引后不稳定，不适合 citation 和评估集。
- 稳定 ID 便于 `fetch_doc_chunk`、评估标注和回归对比。

### 增量索引策略

v0 采用 document 粒度重建：

```text
文件 content_hash 没变 -> 跳过
文件 content_hash 变了 -> 删除该 doc 旧 chunks，重新切块、重新 embedding
文件不存在 -> documents.status = deleted，并删除对应 chunks / vec_chunks
```

为什么选择 document 粒度重建：

- 实现简单，适合 v0。
- Markdown 文档通常不大，整篇重建成本可接受。
- 避免 chunk 级 diff 带来的复杂度。

为什么暂时不用 chunk 级 diff：

- chunk 边界会随标题和段落变化连锁改变。
- 复杂 diff 不利于先跑通 Document RAG 闭环。
- 等评估集稳定后，再考虑优化索引速度。

## 工具接口

工具层只负责把 Document RAG 能力安全暴露给 Agent。

工具层做：

```text
参数校验
调用 retriever / store
结果裁剪
错误格式化
返回结构化 JSON
```

工具层不做：

```text
不实现检索算法
不直接写 SQL
不切 chunk
不调用 embedding 底层 provider
不拼最终自然语言回答
```

为什么设计两个工具：

```text
search_docs -> 轻量检索，返回 snippet + metadata
fetch_doc_chunk -> 按 chunk_id 展开完整内容
```

原因：

- 避免 `search_docs` 一次性返回过多正文污染上下文。
- Agent 可以先检索，再按需展开证据。
- 工具调用链路更容易评估：先看工具选择是否正确，再看证据展开是否必要。

### search_docs

用途：根据用户问题搜索文档片段。

参数：

```text
query: string
top_k: int = 5
include_content: bool = false
max_snippet_chars: int = 500
filters: object | null
```

限制：

```text
1 <= top_k <= 10
max_snippet_chars <= 1000
include_content 默认 false
```

推荐行为：

- 默认只返回 snippet，不返回完整 content。
- 如果 `include_content = true`，也必须做长度截断。
- 更推荐 Agent 使用 `fetch_doc_chunk` 按需展开完整 chunk。

返回：

```text
ok
query
hit_count
trace_id
hits
error
```

每个 hit：

```text
rank
chunk_id
chunk_key
source_path
heading_path
score
score_type
snippet
chunk_content_hash
document_content_hash
```

如果 `include_content = true`：

```text
content
content_truncated
```

### fetch_doc_chunk

用途：根据 chunk_id 读取完整 chunk。

参数：

```text
chunk_id: string
max_chars: int = 4000
```

限制：

```text
max_chars <= 8000
```

返回：

```text
ok
chunk_id
chunk_key
source_path
heading_path
content
content_truncated
chunk_content_hash
document_content_hash
metadata
error
```

为什么限制 `max_chars`：

- 防止一次工具调用塞入过大上下文。
- 避免超长 chunk 影响 Agent 回答。
- 保持工具治理和成本可控。

### 结构化错误

两个工具都返回结构化错误：

```json
{
  "ok": false,
  "error_code": "index_stale",
  "message": "Document RAG index is stale, please rebuild.",
  "suggestion": "Run doc_rag index rebuild."
}
```

常见错误码：

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

为什么使用结构化错误：

- Agent 能区分“没资料”“索引过期”“参数错误”“系统失败”。
- 自动评估更容易判断工具调用是否正确。
- trace 和 observe 更容易聚合错误类型。

### 工具返回格式

v0 工具返回结构化 JSON，不返回大段自然语言解释。

原因：

- Agent 更容易解析。
- 自动测试更容易断言。
- 避免把“工具解释”和“最终回答”混在一起。
- 后续 dashboard / eval 可以直接消费。

### ToolRegistry 接入

注册：

```text
search_docs
fetch_doc_chunk
```

`search_docs` 描述：

```text
用于检索 Document RAG 语料库中的相关文档片段。适合回答“文档里怎么说”“某设计依据在哪”。
```

`fetch_doc_chunk` 描述：

```text
根据 search_docs 返回的 chunk_id 读取更完整内容。适合需要展开证据时使用。
```

与 memory 工具区分：

```text
recall_memory -> 用户长期记忆
search_docs -> 文档知识库
```

工具可见性：

```text
v0 为测试简单，search_docs 和 fetch_doc_chunk 可以都 always_on。
后续如果工具过多，可以 search_docs always_on，fetch_doc_chunk 由工具搜索或上下文策略解锁。
```

### trace 与 citation

`search_docs` 调用 retriever，retriever 写 retrieval trace。

工具返回：

```text
trace_id
```

`fetch_doc_chunk` 不写 retrieval trace，因为它不是召回，只是按 ID 读取内容；它可以进入普通 tool trace / observe。

每个 hit 必须带：

```text
source_path
heading_path
chunk_id
```

这样最终回答可以引用：

```text
[source_path > heading_path]
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

## Citation 与回答引用规则

### 设计目标

Document RAG 的回答不能只“看起来合理”，还要能回到具体文档位置验证。

引用规则要解决四个问题：

- 用户知道答案来自哪份文档。
- 开发者能用 `source_path`、`heading_path` 和 `chunk_id` 回查证据。
- 评估脚本能判断 evidence hit 和答案忠实度。
- Agent 在没有检索证据时，不把模型先验伪装成文档结论。

### v0 引用格式

最终回答中的文档依据使用：

```text
[source_path > heading_path]
```

示例：

```text
Document RAG 的 v0 检索采用 vector-only baseline，主要是为了减少 hybrid 和 rerank 对早期问题定位的干扰。[my_md/doc_rag_corpus/rag-design.md > 检索流程]
```

如果 `heading_path` 为空，则退化为：

```text
[source_path]
```

如果后续支持 PDF，再扩展为：

```text
[source_path p.12 > heading_path]
```

### 是否在回答里暴露 chunk_id

默认不在面向用户的回答正文中展示 `chunk_id`。

原因：

- `chunk_id` 对用户不友好，阅读负担大。
- 用户更关心“哪份文档、哪个章节”，而不是内部索引 ID。
- `chunk_id` 更适合作为 trace、debug、评估和 `fetch_doc_chunk` 的内部定位键。

但是在调试模式、评估报告或用户明确要求“给出检索证据 ID”时，可以附带：

```text
证据：chunk_id=xxxx
```

### 什么时候必须引用

以下回答必须引用：

- 用户明确问“文档里怎么说”“依据是什么”“这个设计在哪”。
- Agent 调用了 `search_docs` 并使用了检索结果回答。
- 回答中出现项目设计、配置、表结构、流程、约束、取舍等可由文档支撑的结论。
- 多个文档片段共同支持同一答案时，应尽量给出多个来源。

以下情况可以不引用：

- 普通闲聊。
- 用户询问个人长期记忆、偏好、当前会话上下文，这应使用 memory / session，而不是 Document RAG。
- 用户要求给出建议，而建议主要来自模型推理；但此时要区分“文档依据”和“我的建议”。

### 没有检索证据时如何回答

如果 `search_docs` 返回 `empty_index`、`index_stale`、`no_hits` 或检索失败：

- 不要编造文档依据。
- 明确说明“当前没有从文档知识库检索到可引用证据”。
- 可以给出一般性推理，但要标注这是建议，不是文档结论。

推荐回答结构：

```text
我没有从 Document RAG 中检索到可引用证据。基于通用 RAG 设计经验，我建议……
```

### 多个 chunk 支撑一个结论

如果一个结论来自多个 chunk：

- 优先引用最直接支撑结论的 1-2 个来源。
- 不要把 top_k 全部堆到回答末尾。
- 如果多个 chunk 来自同一文档同一章节，只引用一次。
- 如果不同章节分别支撑不同子结论，就在对应子结论后分别引用。

### 和工具返回字段的关系

`search_docs` hit 必须返回：

```text
source_path
heading_path
chunk_id
chunk_key
chunk_content_hash
document_content_hash
snippet
score
trace_id
```

其中：

- `source_path + heading_path` 用于面向用户的引用。
- `chunk_id` 用于 `fetch_doc_chunk`、trace 和评估回查。
- `chunk_content_hash` 和 `document_content_hash` 用于判断引用对应的内容版本。
- `trace_id` 用于把最终回答和检索链路关联起来。

### 为什么选择这种引用格式

选择 `[source_path > heading_path]`，是因为它同时满足可读性、可迁移性和可测试性。

好处：

- 用户能直接理解来源位置。
- repo 相对路径不会绑定到个人机器目录。
- heading_path 能表达章节语义，比只给文件名更清楚。
- 评估集可以标注 expected source / expected heading。
- 后续接入 Web UI 时，可以自然转换成文件链接或文档详情页。

### 为什么不用其他方案

不用只给文件名：

- 文件名粒度太粗，无法判断答案来自哪个章节。
- 同一文档较长时，用户仍然很难核对证据。

不用默认展示 chunk_id：

- 对用户不直观。
- chunk_id 是内部定位键，不适合作为主要阅读引用。

不用复杂脚注系统作为 v0：

- 第一版重点是跑通检索、回答、trace 和评估闭环。
- 复杂脚注需要额外的渲染、编号合并和 UI 支持，容易拖慢实现。

不用让模型自由生成引用格式：

- 不利于自动评估。
- 容易出现引用缺失、格式不统一或伪造来源。

### 对 Agent 提示词的要求

后续接入时，应在 Document RAG 工具说明或系统提示词中加入规则：

```text
当你使用 search_docs / fetch_doc_chunk 的结果回答文档问题时，关键结论后必须使用 [source_path > heading_path] 格式引用来源。不要编造未出现在工具结果中的引用。
```

这条规则不要求 Agent 每句话都引用，但要求关键结论能被文档证据支撑。

## 评估集 v0 设计

### 设计目标

Document RAG 的评估集不是只为了得到一个总分，而是为了把问题拆清楚：

```text
问了什么？
应该召回什么文档？
实际召回了什么？
答案有没有引用证据？
答案是否忠实？
失败时是召回失败、工具选择失败，还是生成失败？
```

所以 v0 评估集采用：

```text
人工标注 + 自动统计 + 可复盘
```

### 评估集文件

推荐目录：

```text
my_md/rag/eval_sets/
  doc_rag_eval_v0.jsonl
  README.md

my_md/rag/eval_reports/
  doc_rag_eval_v0_YYYYMMDD_HHMMSS.json
  doc_rag_eval_v0_YYYYMMDD_HHMMSS.md
```

目录分工：

```text
eval_sets   -> 稳定评估集，只记录标准问题和预期
eval_reports -> 每次运行结果，只记录实际测试输出
```

选择 JSONL 的原因：

- 一行一个 case，方便追加、筛选、定位失败样本。
- 自动 runner 可以逐行读取，不需要一次加载大 JSON。
- 后续按 category 拆分、合并或抽样都比较简单。

单条 case 结构：

```json
{
  "id": "DRAG-V0-001",
  "category": "fact_lookup",
  "question": "Document RAG v0 默认索引哪个目录？",
  "expected_sources": [
    {
      "source_path": "my_md/doc_rag_corpus/document-rag-design.md",
      "heading_path": "第一版数据来源"
    }
  ],
  "expected_answer_points": [
    "默认索引 my_md/doc_rag_corpus/**/*.md",
    "不默认索引 README.md、my_md/**/*.md、_handbook/**/*.md"
  ],
  "expected_tools": ["search_docs"],
  "should_have_citation": true,
  "should_have_no_evidence_response": false,
  "difficulty": "easy",
  "tags": ["corpus", "source_scope"],
  "notes": "测试基础事实定位和 citation"
}
```

### 字段规则

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

字段含义：

- `id`：稳定编号，用于报告、复盘和问题追踪。
- `category`：问题类型，用于分组统计。
- `question`：接近真实用户提问的自然语言问题。
- `expected_sources`：正确文档来源，用于 Recall@k、MRR、citation_valid。
- `expected_answer_points`：答案应该覆盖的关键点。
- `expected_tools`：期望调用的工具，例如 `search_docs`。
- `should_have_citation`：是否必须给出文档引用。
- `should_have_no_evidence_response`：是否必须明确回答没有可引用证据。
- `difficulty`：`easy`、`medium`、`hard`。
- `tags`：用于筛选问题，例如 `chunker`、`embedding`、`citation`、`memory_boundary`。
- `requires_fetch`：是否期望调用 `fetch_doc_chunk` 展开完整证据。

### 命名规则

Document RAG v0 使用：

```text
DRAG-V0-001
DRAG-V0-002
...
```

后续扩展：

```text
DRAG-V1-001
GRAG-V0-001
LLMWIKI-V0-001
```

这样可以从 ID 直接看出评估路线和版本。

### case 分类

v0 先准备 20-30 条人工标注 case。

推荐分布：

```text
fact_lookup: 6
design_rationale: 6
pipeline_reasoning: 6
boundary_distinction: 5
no_evidence: 4
multi_hop: 3
```

首批 30 条编号区间：

```text
DRAG-V0-001 ~ 006: fact_lookup
DRAG-V0-007 ~ 012: design_rationale
DRAG-V0-013 ~ 018: pipeline_reasoning
DRAG-V0-019 ~ 023: boundary_distinction
DRAG-V0-024 ~ 027: no_evidence
DRAG-V0-028 ~ 030: multi_hop
```

分类含义：

- `fact_lookup`：测试基本事实定位，例如默认语料目录、配置项、表名。
- `design_rationale`：测试设计取舍，例如为什么选 sqlite-vec，为什么不用 Qdrant。
- `pipeline_reasoning`：测试流程理解，例如 indexer、retriever、tool 的调用链。
- `boundary_distinction`：测试边界区分，例如 Document RAG 和 memory2 的差异。
- `no_evidence`：测试无证据问题时是否拒绝编造。
- `multi_hop`：测试多个模块组合回答，例如 loader 和 chunker 的边界分别是什么。

### 标注策略

`expected_sources` 第一版只强制标：

```text
source_path
heading_path
```

暂不强制标 `chunk_id`。

原因：

- v0 期间 chunker 参数可能变化，`chunk_id` 会随 chunk 内容和边界变化。
- `source_path + heading_path` 更适合作为第一版稳定评估锚点。
- 等 chunker 稳定后，再补充 `expected_chunk_id` 或 `expected_chunk_key`。

`expected_answer_points` 用于检查答案是否覆盖关键点。

第一版可以先人工 judge，后续再接 LLM judge。

### README 维护规则

`eval_sets/README.md` 记录：

```text
评估集测什么
每个字段是什么意思
如何新增 case
如何修改 case
哪些字段不能随便改
如何处理 chunk_id 变化
```

维护规则：

- 评估集文件不记录运行结果。
- 运行结果只写入 `eval_reports`。
- 如果修改 `question`、`expected_sources` 或 `expected_answer_points`，必须记录原因。
- 如果只是补充 `notes`，不算语义变化。
- `id` 一旦进入报告，不应复用给另一个问题。
- 如果问题废弃，保留 ID 并标记 deprecated，而不是让新问题占用旧 ID。

### 评估指标

v0 关注：

```text
Recall@1
Recall@3
Recall@5
MRR
evidence_hit
citation_valid
answer_faithfulness
tool_correctness
```

指标解释：

- `Recall@k`：前 k 个召回结果是否包含 expected source / heading。
- `MRR`：正确证据首次出现的位置。
- `evidence_hit`：召回证据是否真的能支撑答案。
- `citation_valid`：回答引用是否来自真实检索结果。
- `answer_faithfulness`：答案是否忠实于证据。
- `tool_correctness`：是否正确调用 `search_docs` / `fetch_doc_chunk`。

### 为什么选择小规模人工评估集

选择 20-30 条人工标注 case，是因为当前阶段最重要的是建立可信 baseline。

好处：

- 标注质量可控。
- 失败样本容易逐条复盘。
- 能覆盖核心模块和核心问题类型。
- 后续扩展到 100+ 条时，有清晰模板可复用。

为什么不一开始做大规模自动 judge：

- 早期链路未稳定，自动 judge 可能把检索、生成和 judge 自身不稳定混在一起。
- 大量低质量 case 会误导参数优化。
- 小而准的评估集更适合先验证 loader、chunker、embedding、retriever、citation 是否闭环。

为什么不用 Markdown 表格：

- Markdown 表格不适合自动 runner 解析。
- `expected_sources`、`tags`、`expected_answer_points` 这类多值字段很难维护。
- 后续接自动评估和报告会增加额外解析成本。

为什么不用单个大 JSON 数组：

- 追加样本时 diff 更大。
- 多人维护时更容易冲突。
- JSONL 一行一个 case，更适合定位、筛选和增量追加。

## 评估 Runner 设计

### 分层测试

评估 runner v0 分两层：

```text
retrieval-only runner
agent e2e runner
```

第一层只测检索：

```text
question -> DocRetriever/search_docs -> top_k hits -> Recall@k/MRR
```

第二层测端到端回答：

```text
question -> AgentLoop/CLI -> tools -> final answer -> citation/judge
```

### 为什么分两层

如果只测端到端，失败原因会混在一起：

```text
没有召回正确 chunk
召回了但排在太后
Agent 没有调用 search_docs
Agent 调用了 search_docs 但没用证据
Agent 引用了错误来源
生成时遗漏关键点
```

分两层后，排查路径更清楚：

```text
检索层失败 -> 查 corpus / loader / chunker / embedding / retriever
检索层成功但端到端失败 -> 查工具描述 / prompt / citation / 生成逻辑
```

### retrieval-only runner

职责：

- 读取 `doc_rag_eval_v0.jsonl`。
- 对每条 question 调用 retriever 或 `search_docs`。
- 记录 top_k hits。
- 计算 `Recall@1/3/5`、`MRR`、`expected_source_hit`、`expected_heading_hit`。
- 不依赖 Agent 最终回答。

适合定位：

- 文档是否进入索引。
- chunk 是否合理。
- embedding 是否能召回正确内容。
- 排序是否把正确证据放到前面。

### agent e2e runner

职责：

- 通过 CLI / AgentLoop 发送同一批 question。
- 记录工具调用。
- 记录最终回答。
- 检查是否调用预期工具。
- 检查 citation 是否存在且真实。
- 检查答案是否覆盖 `expected_answer_points`。
- 检查无证据问题是否拒绝编造。

适合定位：

- Agent 是否会主动选择 `search_docs`。
- 需要完整证据时是否调用 `fetch_doc_chunk`。
- 工具返回结果是否被正确用于回答。
- citation 规则是否被遵守。
- 生成层是否忠实于证据。

### 报告输出

推荐每次运行输出：

```text
my_md/rag/eval_reports/doc_rag_eval_v0_YYYYMMDD_HHMMSS.json
my_md/rag/eval_reports/doc_rag_eval_v0_YYYYMMDD_HHMMSS.md
```

JSON 用于机器分析，Markdown 用于学习复盘。

总报告结构：

```json
{
  "run_id": "doc-rag-eval-20260709-001",
  "eval_set": "doc_rag_eval_v0",
  "summary": {
    "total": 30,
    "retrieval_recall_at_5": 0.0,
    "retrieval_mrr": 0.0,
    "tool_call_accuracy": 0.0,
    "citation_valid_rate": 0.0,
    "answer_faithfulness_rate": 0.0
  },
  "cases": []
}
```

每个 case 记录：

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

### 推荐实现顺序

```text
1. retrieval-only runner
2. agent e2e runner
3. LLM judge
```

原因：

- retrieval-only 最稳定，最容易自动化。
- agent e2e 受模型行为影响，需要更多日志。
- LLM judge 最后接入，避免早期把 judge 不稳定也混入问题定位。

### v0 暂不做

暂不直接做：

```text
全自动大评测
复杂加权总分
强依赖 LLM judge 的忠实度评分
```

原因：

- v0 需要先验证底层硬指标。
- 如果 retrieval 不稳定，生成层打分意义有限。
- 复杂总分容易掩盖具体失败原因。
- 先把 Recall@k、MRR、citation_valid、tool_correctness 跑通更重要。

## 失败归因标准

### 设计目标

评估结果不能只记录 `pass / fail`。

每个失败 case 都要回答：

```text
失败发生在哪一层？
最可能影响哪个模块？
下一步应该优先排查什么？
```

核心原则：

```text
先定位层级，再定位模块。
```

### v0 failure_reason 枚举

建议第一版使用：

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

含义：

- `index_issue`：expected source 没有进入索引，或索引状态不兼容。
- `retrieval_miss`：top_k 没有召回正确文档或章节。
- `ranking_bad`：召回到了正确证据，但排名太靠后。
- `tool_misuse`：Agent 没有调用预期工具，或调用了不该调用的工具。
- `fetch_missing`：需要展开完整 chunk，但没有调用 `fetch_doc_chunk`。
- `citation_missing`：应该引用文档来源，但最终回答没有 citation。
- `citation_fake`：引用了不存在的来源，或引用不来自工具返回结果。
- `answer_incomplete`：答案没有覆盖 `expected_answer_points`。
- `answer_unfaithful`：答案和检索证据不一致，或过度发挥。
- `no_evidence_failed`：无证据问题却编造了文档结论或引用。
- `runtime_error`：工具、数据库、embedding、模型调用或 runner 异常。
- `judge_uncertain`：自动 judge 无法稳定判断，需要人工复核。

### case 级记录

每个失败 case 可以记录多个原因，但必须有一个主原因：

```json
{
  "passed": false,
  "failure_reasons": ["retrieval_miss"],
  "primary_failure_reason": "retrieval_miss",
  "debug_note": "expected heading 未出现在 top5，可能是切块或 embedding 问题"
}
```

为什么要区分 `failure_reasons` 和 `primary_failure_reason`：

- 一个 case 可能同时出现召回失败和引用缺失。
- 主失败原因用于统计和优先级排序。
- 多原因用于完整复盘，避免丢失后续问题。

### 排查路径

归因到不同失败类型后，优先排查方向如下：

| failure_reason | 优先排查 |
| --- | --- |
| index_issue | corpus 范围、loader、index_run_docs、schema/meta、source_path |
| retrieval_miss | chunker、embedding text、embedding 模型、top_k、similarity_threshold |
| ranking_bad | chunk 粒度、query 表达、score 计算、后续 hybrid/rerank |
| tool_misuse | 工具描述、ToolRegistry 可见性、系统提示词、工具治理 |
| fetch_missing | `search_docs` 返回字段、`fetch_doc_chunk` 工具描述、Agent 展开证据策略 |
| citation_missing | citation prompt、最终回答约束、工具结果注入格式 |
| citation_fake | citation 校验、禁止自由编造引用、工具返回字段约束 |
| answer_incomplete | expected_answer_points、上下文注入长度、是否需要 fetch 完整 chunk |
| answer_unfaithful | 生成提示词、证据不足、模型过度发挥、是否允许 model prior |
| no_evidence_failed | no_hits 回答模板、无证据策略、citation 约束 |
| runtime_error | 工具异常、数据库异常、embedding API、LLM API、runner 超时 |
| judge_uncertain | judge prompt、人工复核、评估标准是否太模糊 |

### 为什么这样设计

选择标准化失败归因，是因为 RAG 优化需要知道“该改哪里”。

好处：

- 分数下降时能快速定位原因。
- 参数实验能区分召回问题和生成问题。
- 后续写复盘和 STAR 案例时，有清楚的问题、行动和结果链路。
- 面试表达时可以说明自己不是只堆 RAG 功能，而是建立了评估和治理闭环。

为什么不用单一 pass/fail：

- pass/fail 只能说明结果不对，不能说明该修哪里。
- 同样是 fail，可能分别来自索引、召回、工具、引用或生成。
- 没有归因就很难做稳定迭代。

## 配置项

v0 在现有项目配置体系中增加独立 `doc_rag` 配置块。

原则：

```text
配置独立
默认关闭
索引可校验
不影响 memory2 / AgentLoop / 现有工具默认行为
```

### 分组配置

```toml
[doc_rag]
enabled = false
source_root = "."
store_path = "~/.akashic/workspace/doc_rag/doc_rag.db"
collection_id = "default"

[doc_rag.sources]
include_globs = [
  "my_md/doc_rag_corpus/**/*.md"
]
exclude_globs = [
  "**/*.db",
  "**/*.sqlite",
  "**/*.jsonl",
  "**/*.log",
  "**/__pycache__/**",
  "**/.pytest_cache/**"
]
allowed_extensions = [".md", ".markdown"]
max_file_size_bytes = 2097152
allow_external_symlink = false

[doc_rag.chunking]
chunker_version = "heading_block_v0"
target_chunk_chars = 1600
max_chunk_chars = 2400
min_chunk_chars = 300
chunk_overlap_chars = 200

[doc_rag.embedding]
mode = "inherit_memory"
model = ""
api_key = ""
base_url = ""
dim = 1024
batch_size = 16
max_retries = 2
timeout_seconds = 30

[doc_rag.retrieval]
top_k = 5
similarity_threshold = 0.45
retrieval_mode = "vector_only"
fallback_enabled = true

[doc_rag.trace]
enabled = true
format = "jsonl"
path = "~/.akashic/workspace/doc_rag/retrieval_traces.jsonl"
include_content = false
max_content_chars = 2000

[doc_rag.citation]
required_for_doc_answer = true
format = "[source_path > heading_path]"
include_chunk_id_for_debug = false
on_no_hits = "state_no_evidence"

[doc_rag.eval]
eval_set_path = "my_md/rag/eval_sets/doc_rag_eval_v0.jsonl"
report_dir = "my_md/rag/eval_reports"
```

为什么分组：

- `doc_rag`：控制开关、存储位置和 collection 身份。
- `doc_rag.sources`：控制语料边界和文件治理。
- `doc_rag.chunking`：控制切块行为。
- `doc_rag.embedding`：控制向量空间。
- `doc_rag.retrieval`：控制查询阶段。
- `doc_rag.trace`：控制观察和调试。
- `doc_rag.citation`：控制回答引用规则。
- `doc_rag.eval`：控制评估集和报告输出。

为什么选择独立 `[doc_rag]` 配置块：

- Document RAG 和 memory RAG 的数据源、索引、评估参数不同，配置应当独立。
- 配置独立后，可以清楚记录每次实验使用了哪些语料和参数。
- 后续切换索引范围、embedding 或 chunker 时，不需要改代码。
- `enabled = false` 避免默认启动时产生额外 embedding 成本和行为变化。

为什么默认关闭：

- 避免启动 Agent 时自动产生 embedding 成本。
- 避免用户没有准备 corpus 时出现额外错误。
- 避免改变现有 CLI、memory、tool 行为。
- 适合先作为可选能力开发和测试。

### embedding 配置

Document RAG embedding 支持两种模式：

```text
inherit_memory
custom
```

`inherit_memory`：

```text
复用 memory2 当前 embedding 的 model / base_url / api_key / dim
```

`custom`：

```text
使用 doc_rag.embedding 自己的 model / base_url / api_key / dim
```

约束：

```text
api_key 不能写入 meta
api_key 不能写入 trace
api_key 不能写入 eval report
```

meta 只能记录：

```text
embedding_mode
embedding_model
embedding_base_url
embedding_dim
```

为什么这样设计：

- 默认继承 memory 配置，降低 v0 使用成本。
- 保留 custom 模式，方便后续做文档检索专项 embedding 实验。
- 不记录 api_key，避免敏感信息进入数据库、trace 或报告。

为什么默认只索引 `my_md/doc_rag_corpus/**/*.md`：

- 该目录专门用于稳定测试语料，便于构造 expected source 和评估集。
- 不会被现有高频更新的学习文档影响。
- 避免把测试输出、错误记录、临时讨论误纳入知识库。
- 更符合 RAG 语料治理：先整理，再入库。

为什么不默认索引 `README.md`、`my_md/**/*.md`、`_handbook/**/*.md`：

- 这些文档可能频繁变化，导致索引和评估结果不稳定。
- `my_md` 中包含测试、复盘、错误、评估结果等多种用途文档，边界不清。
- `_handbook` 和 `README.md` 可以后续人工整理后复制到 corpus，而不是直接混入 baseline。

### schema 与 index 校验

v0 使用两个版本概念：

```text
schema_version = 1
index_format_version = "doc_rag_v0"
```

`schema_version` 表示数据库表结构版本。

如果代码期望的 schema version 和数据库 meta 不一致：

```text
返回 schema_mismatch 或 index_stale
要求显式 rebuild
```

`index_format_version` 表示索引逻辑版本。

它和以下内容绑定：

```text
source_root
include_globs
exclude_globs
allowed_extensions
chunker_version
chunk 参数
embedding mode/model/base_url/dim
source_path_mode
vector_store
```

检索前校验流程：

```text
1. 读取当前 DocRagConfig
2. 读取 doc_rag.db meta
3. 对比 schema_version
4. 对比 index_format_version
5. 对比关键索引配置 hash
6. 如果不一致，返回 index_stale
7. 如果一致，允许检索
```

索引完成后写入 meta：

```text
schema_version
index_format_version
index_config_hash
source_root
include_globs
exclude_globs
collection_id
embedding_mode
embedding_model
embedding_base_url
embedding_dim
chunker_version
chunk 参数
source_path_mode
vector_store
last_index_run_id
```

为什么 v0 不做自动 migration：

- Document RAG 索引是可重建数据。
- 显式 rebuild 更容易理解和复盘。
- 自动 migration 容易隐藏版本不兼容问题。
- v0 先降低实现复杂度。

### 哪些配置变化需要 rebuild

```text
schema_version
index_format_version
source_root
include_globs
exclude_globs
allowed_extensions
max_file_size_bytes
collection_id
allow_external_symlink
chunker_version
target_chunk_chars
max_chunk_chars
min_chunk_chars
chunk_overlap_chars
embedding_mode
embedding_model
embedding_base_url
embedding_dim
source_path_mode
vector_store
```

为什么这些变化需要 rebuild：

- 它们会改变进入索引的文档集合、文档身份、chunk 边界或向量空间。
- 如果不重建，检索结果无法代表当前配置。

### 哪些配置变化不需要 rebuild

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
embedding.batch_size
embedding.max_retries
embedding.timeout_seconds
```

为什么这些变化不需要 rebuild：

- 它们只影响运行开关、查询阶段、观察、引用、评估或执行过程。
- 不改变已经写入数据库的文档、chunk 和向量。

注意：

- 如果后续 `retrieval_mode = hybrid` 只是启用已经同步好的 FTS5 表，可以不 rebuild。
- 如果改变 FTS 建表策略或 tokenizer，则需要 rebuild。

后续增强配置：

```text
query_rewrite_enabled
hybrid_search_enabled
keyword_top_k
rrf_k
rerank_enabled
rerank_top_n
require_citation
```

## 最小实现顺序

Document RAG v0 按“从底层到入口，从可单测到端到端”的顺序实现。

核心原则：

```text
先定义数据边界
再建立索引底座
再实现加载和切块
再接 embedding 和检索
最后暴露工具和评估
```

不要一开始就写 Agent 工具，也不要一开始就接 AgentLoop。

原因：

- 如果底层索引和检索还不稳定，端到端失败很难定位。
- loader、chunker、store 都可以单测，应先把可控部分做扎实。
- 工具层只是暴露能力，不应该承载核心检索逻辑。

### P0：配置和模型

实现：

```text
doc_rag/models.py
config 中的 DocRagConfig
```

核心对象：

```text
DocRagConfig
LoadedDocument
LoaderError
DocumentRecord
ChunkRecord
IndexRun
IndexRunDoc
RetrievalHit
SearchResult
```

验收：

- 配置能加载。
- 默认 `enabled = false`。
- doc_rag 子配置有默认值。
- 模型对象能被单元测试构造。

为什么先做：

- 后续模块都依赖这些结构。
- 先定义边界，避免每个模块临时传 dict。

### P1：Store / Schema

实现：

```text
doc_rag/store.py
doc_rag/schema.sql
```

表：

```text
documents
chunks
vec_chunks
chunks_fts
index_runs
index_run_docs
meta
```

验收：

- 能初始化 `doc_rag.db`。
- 能写入 meta。
- 能记录 index run。
- 能 upsert document。
- 能 replace document chunks。
- 能 get_chunk。
- sqlite-vec 不可用时有明确 fallback 标记。

为什么第二步做：

- store 是索引和检索的共同底座。
- 先封装数据库边界，避免 indexer / retriever 直接写 SQL。

### P2：Markdown Loader

实现：

```text
doc_rag/loader.py
```

验收：

- 只扫描 `my_md/doc_rag_corpus/**/*.md`。
- 输出 `LoadedDocument`。
- `source_path` 是 repo 相对路径。
- 能跳过空文件、超大文件、非 UTF-8 文件。
- loader errors 可返回，不中断整体扫描。

为什么第三步做：

- loader 不依赖 LLM、不依赖 embedding，容易单测。
- 能先验证语料边界是否正确。

### P3：Markdown Chunker

实现：

```text
doc_rag/chunker.py
```

验收：

- 能按 `heading_path` 切块。
- 保护代码块、表格、列表。
- 生成 `chunk_id`、`chunk_key`、`chunk_content_hash`。
- chunk 长度在参数范围内。
- 标题变化和内容变化时 ID 行为符合预期。

为什么第四步做：

- chunker 决定召回质量。
- 不接 embedding 也能通过单测验证切块边界。

### P4：Embedding Client

实现：

```text
doc_rag/embedding.py
```

验收：

- 支持 `inherit_memory`。
- 支持 `custom`。
- 支持批量 embedding。
- 校验向量维度。
- 不写数据库。
- `api_key` 不进入日志、meta、trace、eval report。

为什么第五步做：

- embedding 是索引前最后一步。
- 独立封装后，indexer 不需要知道具体 provider 细节。

### P5：Indexer

实现：

```text
doc_rag/indexer.py
```

流程：

```text
config -> loader -> chunker -> embedding client -> store
```

验收：

- 能 rebuild。
- 能 dry_run。
- 能跳过 unchanged 文档。
- changed 文档成功后原子替换。
- embedding 失败不污染旧索引。
- `index_runs` / `index_run_docs` 记录准确。
- meta 写入 `schema_version` / `index_config_hash`。

为什么第六步做：

- 到这里才形成“文档入库”闭环。
- 没有 indexer，retriever 没有数据可查。

### P6：Retriever

实现：

```text
doc_rag/retriever.py
```

验收：

- 检索前校验 meta。
- `index_stale` 时拒绝检索。
- 能生成 query embedding。
- 能执行 vector-only search。
- sqlite-vec 不可用时 fallback 到 JSON embedding cosine。
- 返回 `RetrievalHit`。
- 写 retrieval trace。

为什么第七步做：

- retriever 是 `search_docs` 的真正核心。
- 先直接测 retriever，再接工具，定位更清楚。

### P7：Tools

实现：

```text
doc_rag/tools.py
```

注册：

```text
search_docs
fetch_doc_chunk
```

验收：

- `search_docs` 返回结构化 JSON。
- `fetch_doc_chunk` 能按 `chunk_id` 读取内容。
- 错误返回结构化 `error_code`。
- 工具不直接写 SQL。
- 工具描述能区分 `search_docs` 和 `recall_memory`。

为什么第八步做：

- 这时底层检索已经可用。
- 工具只是把能力暴露给 Agent。

### P8：Eval Runner

实现：

```text
doc_rag/eval_runner.py
my_md/rag/eval_sets/doc_rag_eval_v0.jsonl
```

验收：

- 能跑 retrieval-only。
- 输出 Recall@k / MRR。
- 能跑 agent e2e。
- 记录 tool calls / citation / failure_reason。
- 输出 JSON + Markdown report。

为什么最后做：

- 评估 runner 依赖检索和工具。
- 先有 v0 能力，再评估它，结果才有意义。

### 阶段节奏

```text
第一阶段：P0-P3
目标：配置、schema、loader、chunker 可单测

第二阶段：P4-P6
目标：能索引、能检索、能 trace

第三阶段：P7-P8
目标：Agent 可调用、评估可运行
```

### v0 暂缓内容

第一版先不做：

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

- v0 目标是 Document RAG 闭环。
- 先建立 baseline，再做优化。
- 太早引入 hybrid / rerank 会让问题定位复杂化。

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

## v0 最终验收标准

Document RAG v0 的最低完成标准不是“能回答文档问题”，而是：

```text
能索引
能召回
能引用
能评估
能复盘
```

换句话说：

```text
Document RAG v0 = 可控语料 + 稳定索引 + 可解释召回 + 工具接入 + 引用回答 + 自动评估 + 失败归因
```

### 1. 索引验收

必须满足：

```text
能索引 my_md/doc_rag_corpus/**/*.md
不会默认索引 README.md、my_md/**/*.md、_handbook/**/*.md
source_path 是 repo 相对路径
index_runs / index_run_docs 有记录
meta 写入 schema_version / index_format_version / index_config_hash
配置不兼容时返回 index_stale 或 schema_mismatch
```

验收意义：

- 证明语料边界可控。
- 证明索引状态可追踪。
- 证明旧索引不会被静默误用。

### 2. 切块验收

必须满足：

```text
chunk 带 source_path / heading_path / chunk_id / chunk_key
代码块、表格、列表不会被普通逻辑随意切断
chunk 长度大体符合 target/max/min 参数
chunk_content_hash 和 document_content_hash 正确记录
```

验收意义：

- 证明召回单元可解释。
- 证明 citation 能定位到文档章节。
- 证明后续内容变化可以被追踪。

### 3. 检索验收

必须满足：

```text
search_docs / retriever 能返回 top_k hits
默认 vector-only
能过滤 inactive document 和 embedding_status != ready 的 chunk
sqlite-vec 不可用时 fallback 明确
empty_index / no_hits / index_stale 有结构化错误
每次检索写 retrieval trace
```

验收意义：

- 证明检索链路可用。
- 证明失败不会静默异常。
- 证明后续能按 trace 排查召回问题。

### 4. 工具验收

必须满足：

```text
Agent 能调用 search_docs
Agent 能在需要时调用 fetch_doc_chunk
工具返回结构化 JSON
错误返回 error_code
工具层不直接写 SQL
search_docs 和 recall_memory 语义区分清楚
```

验收意义：

- 证明 Document RAG 已接入 Agent 工具体系。
- 证明文档检索和长期记忆不会混用。
- 证明工具层保持轻薄，不承载核心检索逻辑。

### 5. 答案和 citation 验收

必须满足：

```text
文档类回答关键结论带 [source_path > heading_path]
citation 必须来自 search_docs / fetch_doc_chunk 返回结果
无证据时不编造引用
不默认向普通用户展示 chunk_id
至少 5 个文档问答包含正确引用
```

验收意义：

- 证明答案可验证。
- 证明模型没有把先验知识伪装成文档依据。
- 证明引用格式可被人工和自动评估使用。

### 6. 评估验收

必须满足：

```text
有 doc_rag_eval_v0.jsonl
至少 20-30 条 case
能跑 retrieval-only runner
能输出 Recall@1 / Recall@3 / Recall@5 / MRR
能跑 agent e2e runner
能记录 tool calls / citation / failure_reason
能输出 JSON + Markdown report
```

验收意义：

- 证明 Document RAG 不是一次性 demo。
- 证明后续可以用指标持续优化。
- 证明失败 case 能被追踪和复盘。

### 7. 安全和复盘验收

必须满足：

```text
api_key 不写入 meta / trace / eval report
eval_sets 不记录运行结果
eval_reports 不反向修改测试集
失败 case 有 primary_failure_reason
v0 暂缓功能有明确记录
```

验收意义：

- 证明敏感配置不会泄漏进可观测数据。
- 证明评估集和运行结果边界清楚。
- 证明后续复盘能形成“问题-行动-结果”的闭环。

### v0 完成判断

如果以上七类验收都满足，可以认为 Document RAG v0 完成。

如果只能做到“能回答文档问题”，但没有 trace、citation、eval 和 failure_reason，则只能算 demo，不能算 v0 闭环。

## 后续更新提示词

```text
请根据本次 Document RAG 设计/实现进展，更新 my_md/rag/10-document-rag-design.md，补充新的架构决策、数据结构、工具接口、接入点和取舍说明。
```
