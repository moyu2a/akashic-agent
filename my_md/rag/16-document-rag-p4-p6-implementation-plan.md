# Document RAG P4-P6 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the second implementation stage of Document RAG: embedding client, indexer, vector retriever, and retrieval trace, so the project can index local Markdown documents and retrieve relevant chunks without Agent tool integration.

**Architecture:** Continue using the independent `doc_rag` package created in P0-P3. P4-P6 must stay below the Agent layer: no `AgentLoop` changes, no `ToolRegistry` registration, no `search_docs` / `fetch_doc_chunk` tools yet. The flow becomes `MarkdownLoader -> MarkdownChunker -> DocEmbeddingClient -> DocRagStore -> DocRagRetriever`.

## Execution Status

当前状态：P4-P6 已完成初步实现和最终验证。

已落地内容：

- P4 embedding client：`doc_rag/embedding.py`，覆盖配置解析、embedding text 构造、批量请求、超时、重试、维度校验和 API key 脱敏。
- Store search 扩展：`doc_rag/store.py`，覆盖文档/chunk 列表、缺失文档删除、sqlite-vec 检索和 JSON embedding fallback。
- P5 indexer：`doc_rag/indexer.py`，覆盖 loader/chunker/embedding/store 编排、增量跳过、dry_run、rebuild、文档级失败恢复和 meta 写入。
- P6 retriever + trace：`doc_rag/retriever.py`、`doc_rag/trace.py`，覆盖 query embedding、vector-only 检索、空 query 错误和 JSONL trace。
- 手动检查脚本：`scripts/doc_rag_index_check.py`、`scripts/doc_rag_retrieve_check.py`。

已验证命令：

```bash
uv run --with pytest pytest tests/test_doc_rag_embedding.py -v
uv run --with pytest pytest tests/test_doc_rag_store.py tests/test_doc_rag_store_search.py -v
uv run --with pytest pytest tests/test_doc_rag_indexer.py -v
uv run --with pytest pytest tests/test_doc_rag_retriever.py -v
uv run --with pytest pytest tests/test_doc_rag_config.py tests/test_doc_rag_models.py tests/test_doc_rag_store.py tests/test_doc_rag_store_search.py tests/test_doc_rag_loader.py tests/test_doc_rag_chunker.py tests/test_doc_rag_embedding.py tests/test_doc_rag_indexer.py tests/test_doc_rag_retriever.py -v
uv run --with pytest pytest tests/test_memory2_retrieval_baseline.py tests/test_tool_discovery_routing.py -v
uv run --with black black --check doc_rag tests/test_doc_rag_*.py scripts/doc_rag_index_check.py scripts/doc_rag_retrieve_check.py
python3 -m compileall -q doc_rag scripts
uv run python -m scripts.doc_rag_index_check --help
uv run python -m scripts.doc_rag_retrieve_check --help
```

最终结果：

- Doc RAG 测试矩阵：`46 passed, 1 warning`。
- 既有 memory2/tool discovery 回归：`16 passed, 1 warning`。
- black check：通过。
- compileall：通过。
- 手动脚本入口：通过。

手动测试修正：

- 现象：直接运行 `uv run python -m scripts.doc_rag_index_check --rebuild` 报 `RuntimeError: shared http resources not configured`。
- 原因：脚本绕过了 `main.py` / `AppRuntime.start()`，没有配置 `memory2.Embedder` 所需的共享 HTTP requester。
- 修复：`scripts/doc_rag_index_check.py` 和 `scripts/doc_rag_retrieve_check.py` 在运行期间创建、注册并关闭 `SharedHttpResources`。
- 新增覆盖：`tests/test_doc_rag_scripts.py`。
- 修复后验证：Doc RAG 测试矩阵 `46 passed, 1 warning`，black check 和 compileall 通过。

自审修正：

- 补齐 deleted 文档清理行为：`mark_missing_documents_deleted` 不只更新 document status，还会清理对应 chunks、chunks_fts 和 vec_chunks；新增 `test_store_clears_chunks_when_marking_missing_documents_deleted` 覆盖该行为。

完整验证命令记录：

```bash
uv run --with pytest pytest \
  tests/test_doc_rag_config.py \
  tests/test_doc_rag_models.py \
  tests/test_doc_rag_store.py \
  tests/test_doc_rag_store_search.py \
  tests/test_doc_rag_loader.py \
  tests/test_doc_rag_chunker.py \
  tests/test_doc_rag_embedding.py \
  tests/test_doc_rag_indexer.py \
  tests/test_doc_rag_retriever.py \
  -v

uv run --with pytest pytest \
  tests/test_memory2_retrieval_baseline.py \
  tests/test_tool_discovery_routing.py \
  -v

uv run --with black black --check doc_rag tests/test_doc_rag_*.py scripts/doc_rag_index_check.py scripts/doc_rag_retrieve_check.py
python3 -m compileall -q doc_rag scripts
```

**Tech Stack:** Python 3.12+, dataclasses, async embedding via existing `memory2.embedder.Embedder` pattern, SQLite + optional sqlite-vec, JSONL trace, pytest with fake embedding clients/requesters.

## Global Constraints

- Do not write document chunks into `memory2.db`.
- Do not modify `AgentLoop` in P4-P6.
- Do not register `search_docs` or `fetch_doc_chunk` in P4-P6.
- Do not call real embedding APIs in unit tests.
- Default Document RAG config remains disabled: `enabled = false`.
- Default corpus remains `my_md/doc_rag_corpus/**/*.md`.
- `source_path` must remain repo-relative POSIX path.
- API keys must not be written to meta, trace, logs, reports, or test snapshots.
- `DocEmbeddingClient` may call embedding APIs only when explicitly used by indexer/retriever at runtime.
- Indexing must be document-level atomic: changed/new documents replace old chunks only after chunks and embeddings are ready.
- sqlite-vec vectors must use `chunks.rowid == vec_chunks.rowid`.
- sqlite-vec vectors must be L2-normalized before blob storage and query; `1 - distance^2 / 2` is valid only on normalized vectors.
- Retrieval trace v0 uses JSONL, not a database table.
- P4-P6 still does not answer user questions; it only proves retrieval works.

## Why This Stage Exists

P0-P3 proved:

```text
Markdown file -> loader -> chunker -> store
```

P4-P6 must prove:

```text
Markdown file -> loader -> chunker -> embedding -> store -> retriever -> hits + trace
```

This is the minimum useful Document RAG backend. Agent tools should wait until this layer is stable, otherwise failures will be hard to attribute: a bad answer could come from chunking, embedding, indexing, retrieval, prompt usage, or tool routing.

## Design Choices

### Why use `DocEmbeddingClient` instead of calling `memory2.embedder.Embedder` directly?

Use `DocEmbeddingClient` as a Document RAG boundary.

Reasons:

- Document RAG needs document-specific embedding text formatting: source path, heading path, and chunk content.
- Document RAG needs `inherit_memory` and `custom` config modes.
- Document RAG needs dimension validation and structured errors specific to indexing/retrieval.
- Keeping a wrapper makes it easy to later add document-specific batching, retry, truncation, or provider changes.

What it avoids:

- Avoids leaking personal memory semantics into document retrieval.
- Avoids future refactors if document embeddings split from memory embeddings.

### Why implement indexer before Agent tools?

Indexer is the repeatable backend operation that creates the searchable corpus.

Reasons:

- Without indexer, retrieval tests would rely on manual ad hoc database setup.
- Indexer records `index_runs` and `index_run_docs`, which are required for debugging.
- It lets us test partial failures before LLM/tool behavior enters the system.

### Why vector-only retriever first?

v0 should establish a clean baseline.

Reasons:

- Vector-only directly tests embedding and vector store quality.
- Hybrid/rerank/query rewrite make diagnosis harder.
- The design already creates `chunks_fts`, so hybrid can be added later without changing schema direction.

### Why JSONL trace first?

Use JSONL because it is append-only, easy to inspect, and cheap to evolve while retrieval shape is still changing.

Reasons:

- Trace schema will likely change during RAG tuning.
- JSONL can be manually reviewed and diffed.
- A database trace table is better after fields stabilize.

## File Structure

Create:

- `doc_rag/embedding.py`: Document RAG embedding config resolution, text formatting, async embedding client, dimension validation.
- `doc_rag/indexer.py`: Rebuild/incremental indexing orchestration.
- `doc_rag/retriever.py`: Vector retrieval, meta validation, trace writing.
- `doc_rag/trace.py`: JSONL trace writer and trace event builder.
- `tests/test_doc_rag_embedding.py`: embedding client tests using fake requester/client.
- `tests/test_doc_rag_indexer.py`: indexer tests using fake embedding client.
- `tests/test_doc_rag_retriever.py`: retriever and trace tests.
- `scripts/doc_rag_index_check.py`: manual index script.
- `scripts/doc_rag_retrieve_check.py`: manual retrieval script.

Modify:

- `doc_rag/models.py`: add small dataclasses for retrieval trace if needed.
- `doc_rag/store.py`: add document listing, stale document deletion/marking, vector search, chunk listing helpers.
- `doc_rag/__init__.py`: export core constants only unless a task requires more.
- `my_md/rag/11-document-rag-implementation-plan.md`: update P4-P6 progress after implementation.

Do not modify:

- `agent/looping/*`
- `agent/tools/*`
- `plugins/*`
- `main.py`

---

## Task 1: P4 Embedding Client

**Files:**

- Create: `doc_rag/embedding.py`
- Modify: `doc_rag/models.py`
- Test: `tests/test_doc_rag_embedding.py`

**Interfaces:**

- Consumes: `agent.config_models.Config`, `DocRagConfig`, `DocRagEmbeddingConfig`, `MemoryEmbeddingConfig`
- Produces:
  - `EmbeddingSettings`
  - `DocEmbeddingClient`
  - `build_embedding_text(chunk: ChunkRecord) -> str`
  - `resolve_embedding_settings(config: Config) -> EmbeddingSettings`

### Required Behavior

- `inherit_memory` mode:
  - model comes from `config.memory.embedding.model`
  - api_key comes from `config.memory.embedding.api_key` or `config.light_api_key` or `config.api_key`
  - base_url comes from `config.memory.embedding.base_url` or `config.light_base_url` or `config.base_url`
  - dim comes from `config.doc_rag.embedding.dim`
- `custom` mode:
  - model/api_key/base_url come from `config.doc_rag.embedding`
  - dim comes from `config.doc_rag.embedding.dim`
- Any other mode raises `ValueError("unsupported doc_rag embedding mode: ...")`.
- `DocEmbeddingClient.embed_texts(texts)` returns `list[list[float]]`.
- Empty input returns `[]` without calling the network.
- `batch_size` controls how many texts are sent to the backend per call.
- `max_retries` controls retry attempts for failed backend calls.
- `timeout_seconds` is enforced around each backend batch call.
- Returned count must match input count.
- Each returned vector length must equal `settings.dim`; otherwise raise `ValueError("embedding dim mismatch ...")`.
- `build_embedding_text(chunk)` includes source path, heading path, title, and content.
- API keys must not appear in `repr(settings)` or error strings.

### Step Plan

- [ ] **Step 1: Write failing tests**

Create `tests/test_doc_rag_embedding.py`:

```python
from __future__ import annotations

import pytest

from agent.config_models import Config
from doc_rag.embedding import (
    DocEmbeddingClient,
    EmbeddingSettings,
    build_embedding_text,
    resolve_embedding_settings,
)
from doc_rag.models import ChunkRecord


def _config() -> Config:
    cfg = Config(
        provider="deepseek",
        model="deepseek-chat",
        api_key="main-key",
        base_url="https://main.example/v1",
        system_prompt="test",
    )
    cfg.light_api_key = "light-key"
    cfg.light_base_url = "https://light.example/v1"
    cfg.memory.embedding.model = "memory-embed"
    cfg.memory.embedding.api_key = "memory-key"
    cfg.memory.embedding.base_url = "https://memory.example/v1"
    cfg.doc_rag.embedding.dim = 3
    return cfg


def _chunk() -> ChunkRecord:
    return ChunkRecord(
        chunk_id="c1",
        chunk_key="k1",
        doc_id="d1",
        source_path="my_md/doc_rag_corpus/a.md",
        title="Doc A",
        heading_path="Doc A > Runtime",
        chunk_index=0,
        content="Agent runtime coordinates tool calls.",
        chunk_content_hash="chash",
        document_content_hash="dhash",
        token_count=8,
        char_count=38,
    )


def test_resolve_embedding_settings_inherits_memory_config() -> None:
    cfg = _config()

    settings = resolve_embedding_settings(cfg)

    assert settings.mode == "inherit_memory"
    assert settings.model == "memory-embed"
    assert settings.api_key == "memory-key"
    assert settings.base_url == "https://memory.example/v1"
    assert settings.dim == 3
    assert "memory-key" not in repr(settings)


def test_resolve_embedding_settings_custom_config() -> None:
    cfg = _config()
    cfg.doc_rag.embedding.mode = "custom"
    cfg.doc_rag.embedding.model = "doc-embed"
    cfg.doc_rag.embedding.api_key = "doc-key"
    cfg.doc_rag.embedding.base_url = "https://doc.example/v1"
    cfg.doc_rag.embedding.dim = 4

    settings = resolve_embedding_settings(cfg)

    assert settings.mode == "custom"
    assert settings.model == "doc-embed"
    assert settings.api_key == "doc-key"
    assert settings.base_url == "https://doc.example/v1"
    assert settings.dim == 4
    assert "doc-key" not in repr(settings)


def test_build_embedding_text_includes_document_context() -> None:
    text = build_embedding_text(_chunk())

    assert "source_path: my_md/doc_rag_corpus/a.md" in text
    assert "title: Doc A" in text
    assert "heading_path: Doc A > Runtime" in text
    assert "Agent runtime coordinates tool calls." in text


class _FakeBackend:
    def __init__(self, vectors: list[list[float]], fail_times: int = 0) -> None:
        self.vectors = vectors
        self.fail_times = fail_times
        self.calls: list[list[str]] = []

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        if self.fail_times > 0:
            self.fail_times -= 1
            raise RuntimeError("temporary backend failure")
        return self.vectors


@pytest.mark.anyio
async def test_doc_embedding_client_validates_count_and_dim() -> None:
    backend = _FakeBackend([[1.0, 0.0, 0.0]])
    client = DocEmbeddingClient(
        EmbeddingSettings(
            mode="custom",
            model="m",
            api_key="secret",
            base_url="https://example.invalid/v1",
            dim=3,
            batch_size=8,
            max_retries=0,
            timeout_seconds=30,
        ),
        backend=backend,
    )

    result = await client.embed_texts(["hello"])

    assert result == [[1.0, 0.0, 0.0]]
    assert backend.calls == [["hello"]]


@pytest.mark.anyio
async def test_doc_embedding_client_rejects_dim_mismatch() -> None:
    backend = _FakeBackend([[1.0, 0.0]])
    client = DocEmbeddingClient(
        EmbeddingSettings(
            mode="custom",
            model="m",
            api_key="secret",
            base_url="https://example.invalid/v1",
            dim=3,
            batch_size=8,
            max_retries=0,
            timeout_seconds=30,
        ),
        backend=backend,
    )

    with pytest.raises(ValueError, match="embedding dim mismatch"):
        await client.embed_texts(["hello"])


@pytest.mark.anyio
async def test_doc_embedding_client_empty_input_skips_backend() -> None:
    backend = _FakeBackend([])
    client = DocEmbeddingClient(
        EmbeddingSettings(
            mode="custom",
            model="m",
            api_key="secret",
            base_url="https://example.invalid/v1",
            dim=3,
            batch_size=8,
            max_retries=0,
            timeout_seconds=30,
        ),
        backend=backend,
    )

    assert await client.embed_texts([]) == []
    assert backend.calls == []


@pytest.mark.anyio
async def test_doc_embedding_client_uses_batch_size_and_retries() -> None:
    backend = _FakeBackend(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        fail_times=1,
    )
    client = DocEmbeddingClient(
        EmbeddingSettings(
            mode="custom",
            model="m",
            api_key="secret",
            base_url="https://example.invalid/v1",
            dim=3,
            batch_size=2,
            max_retries=1,
            timeout_seconds=30,
        ),
        backend=backend,
    )

    result = await client.embed_texts(["a", "b", "c"])

    assert result == [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]
    assert backend.calls == [["a", "b"], ["a", "b"], ["c"]]
```

- [ ] **Step 2: Run RED tests**

Run:

```bash
uv run --with pytest pytest tests/test_doc_rag_embedding.py -v
```

Expected: fails because `doc_rag.embedding` does not exist.

- [ ] **Step 3: Implement `doc_rag/embedding.py`**

Implementation outline:

```python
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

from agent.config_models import Config
from doc_rag.models import ChunkRecord
from memory2.embedder import Embedder


class EmbeddingBackend(Protocol):
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


@dataclass
class EmbeddingSettings:
    mode: str
    model: str
    api_key: str
    base_url: str
    dim: int
    batch_size: int
    max_retries: int
    timeout_seconds: int

    def __repr__(self) -> str:
        return (
            "EmbeddingSettings("
            f"mode={self.mode!r}, model={self.model!r}, api_key='<redacted>', "
            f"base_url={self.base_url!r}, dim={self.dim!r}, "
            f"batch_size={self.batch_size!r}, max_retries={self.max_retries!r}, "
            f"timeout_seconds={self.timeout_seconds!r})"
        )


def resolve_embedding_settings(config: Config) -> EmbeddingSettings:
    doc = config.doc_rag.embedding
    mode = doc.mode.strip() or "inherit_memory"
    if mode == "inherit_memory":
        model = config.memory.embedding.model or doc.model
        api_key = (
            config.memory.embedding.api_key
            or config.light_api_key
            or config.api_key
        )
        base_url = (
            config.memory.embedding.base_url
            or config.light_base_url
            or config.base_url
            or ""
        )
    elif mode == "custom":
        model = doc.model
        api_key = doc.api_key
        base_url = doc.base_url
    else:
        raise ValueError(f"unsupported doc_rag embedding mode: {mode}")
    if not model:
        raise ValueError("doc_rag embedding model is empty")
    if not base_url:
        raise ValueError("doc_rag embedding base_url is empty")
    if not api_key:
        raise ValueError("doc_rag embedding api_key is empty")
    return EmbeddingSettings(
        mode=mode,
        model=model,
        api_key=api_key,
        base_url=base_url,
        dim=doc.dim,
        batch_size=doc.batch_size,
        max_retries=doc.max_retries,
        timeout_seconds=doc.timeout_seconds,
    )


def build_embedding_text(chunk: ChunkRecord) -> str:
    return "\n".join(
        [
            f"source_path: {chunk.source_path}",
            f"title: {chunk.title}",
            f"heading_path: {chunk.heading_path}",
            "",
            chunk.content,
        ]
    )


class DocEmbeddingClient:
    def __init__(
        self,
        settings: EmbeddingSettings,
        backend: EmbeddingBackend | None = None,
    ) -> None:
        self.settings = settings
        self._backend = backend or Embedder(
            base_url=settings.base_url,
            api_key=settings.api_key,
            model=settings.model,
        )

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        batch_size = max(1, self.settings.batch_size)
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            vectors.extend(await self._embed_batch_with_retry(batch))
        if len(vectors) != len(texts):
            raise ValueError(
                f"embedding count mismatch: expected {len(texts)}, got {len(vectors)}"
            )
        for index, vector in enumerate(vectors):
            if len(vector) != self.settings.dim:
                raise ValueError(
                    "embedding dim mismatch at index "
                    f"{index}: expected {self.settings.dim}, got {len(vector)}"
                )
        return vectors

    async def _embed_batch_with_retry(self, batch: list[str]) -> list[list[float]]:
        last_exc: Exception | None = None
        for attempt in range(self.settings.max_retries + 1):
            try:
                return await asyncio.wait_for(
                    self._backend.embed_batch(batch),
                    timeout=max(1, self.settings.timeout_seconds),
                )
            except Exception as exc:
                last_exc = exc
                if attempt >= self.settings.max_retries:
                    raise
        assert last_exc is not None
        raise last_exc
```

- [ ] **Step 4: Run GREEN tests**

Run:

```bash
uv run --with pytest pytest tests/test_doc_rag_embedding.py -v
```

Expected: all tests pass.

---

## Task 2: Store Search and Index Support Extensions

**Files:**

- Modify: `doc_rag/store.py`
- Modify: `doc_rag/models.py`
- Test: `tests/test_doc_rag_store_search.py`

**Interfaces:**

- Consumes: existing `DocRagStore`, `ChunkRecord`, `DocumentRecord`, `RetrievalHit`
- Produces:
  - `DocRagStore.list_documents() -> list[DocumentRecord]`
  - `DocRagStore.list_chunks(source_path: str | None = None) -> list[ChunkRecord]`
  - `DocRagStore.mark_missing_documents_deleted(active_source_paths: set[str]) -> int`
  - `DocRagStore.search_vector(query_vec: list[float], top_k: int, similarity_threshold: float) -> list[RetrievalHit]`

### Required Behavior

- `search_vector` returns only:
  - active documents
  - chunks with `embedding_status = 'ready'`
  - chunks with non-null embedding
- sqlite-vec path:
  - query uses `vec_chunks MATCH ?`
  - joins `chunks.rowid = vec_chunks.rowid`
  - stores normalized vectors in `vec_chunks`
  - normalizes the query vector before sqlite-vec search
  - converts sqlite-vec L2 distance to cosine similarity by `1 - distance^2 / 2`
- fallback path:
  - if sqlite-vec unavailable, use JSON embedding stored in `chunks.embedding`
  - compute cosine similarity in Python
- Results:
  - sorted by score descending
  - filtered by `similarity_threshold`
  - limited to `top_k`
  - snippets are truncated chunk content, not full answer generation
- API keys are not involved.

### Step Plan

- [ ] **Step 1: Write failing store search tests**

Create `tests/test_doc_rag_store_search.py`:

```python
from __future__ import annotations

from doc_rag.models import ChunkRecord, DocumentRecord
from doc_rag.store import DocRagStore


def _doc(doc_id: str, source_path: str, content_hash: str = "hash") -> DocumentRecord:
    return DocumentRecord(
        doc_id=doc_id,
        source_path=source_path,
        title=source_path.rsplit("/", 1)[-1],
        content_hash=content_hash,
        file_mtime=1.0,
        file_size=10,
    )


def _chunk(
    chunk_id: str,
    doc_id: str,
    source_path: str,
    embedding: list[float],
    status: str = "ready",
) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=chunk_id,
        chunk_key=f"{chunk_id}-key",
        doc_id=doc_id,
        source_path=source_path,
        title="Doc",
        heading_path="Doc > Section",
        chunk_index=0,
        content=f"content for {chunk_id}",
        chunk_content_hash=f"{chunk_id}-hash",
        document_content_hash="hash",
        token_count=3,
        char_count=20,
        embedding=embedding,
        embedding_status=status,
    )


def test_store_lists_documents_and_chunks(tmp_path):
    store = DocRagStore(tmp_path / "doc_rag.db", vec_dim=2)
    try:
        doc = _doc("d1", "my_md/doc_rag_corpus/a.md")
        store.replace_document_chunks(
            doc,
            [_chunk("c1", "d1", doc.source_path, [1.0, 0.0])],
            [[1.0, 0.0]],
        )

        assert [item.source_path for item in store.list_documents()] == [
            "my_md/doc_rag_corpus/a.md"
        ]
        assert [item.chunk_id for item in store.list_chunks()] == ["c1"]
        assert [item.chunk_id for item in store.list_chunks(doc.source_path)] == ["c1"]
    finally:
        store.close()


def test_store_search_vector_filters_and_ranks_ready_active_chunks(tmp_path):
    store = DocRagStore(tmp_path / "doc_rag.db", vec_dim=2)
    try:
        doc1 = _doc("d1", "my_md/doc_rag_corpus/a.md")
        doc2 = _doc("d2", "my_md/doc_rag_corpus/b.md")
        store.replace_document_chunks(
            doc1,
            [
                _chunk("c1", "d1", doc1.source_path, [1.0, 0.0]),
                _chunk("c2", "d1", doc1.source_path, [0.0, 1.0]),
            ],
            [[1.0, 0.0], [0.0, 1.0]],
        )
        store.replace_document_chunks(
            doc2,
            [_chunk("c3", "d2", doc2.source_path, [0.9, 0.1], status="pending")],
            [[0.9, 0.1]],
        )

        hits = store.search_vector([1.0, 0.0], top_k=2, similarity_threshold=0.1)

        assert [hit.chunk_id for hit in hits] == ["c1"]
        assert hits[0].score > 0.99
        assert hits[0].source_path == "my_md/doc_rag_corpus/a.md"


def test_store_search_vector_treats_same_direction_non_unit_vectors_as_similar(tmp_path):
    store = DocRagStore(tmp_path / "doc_rag.db", vec_dim=2)
    try:
        doc = _doc("d1", "my_md/doc_rag_corpus/a.md")
        store.replace_document_chunks(
            doc,
            [_chunk("c1", "d1", doc.source_path, [2.0, 0.0])],
            [[2.0, 0.0]],
        )

        hits = store.search_vector([10.0, 0.0], top_k=1, similarity_threshold=0.99)

        assert [hit.chunk_id for hit in hits] == ["c1"]
        assert hits[0].score > 0.99
    finally:
        store.close()


def test_store_marks_missing_documents_deleted(tmp_path):
    store = DocRagStore(tmp_path / "doc_rag.db", vec_dim=2)
    try:
        doc1 = _doc("d1", "my_md/doc_rag_corpus/a.md")
        doc2 = _doc("d2", "my_md/doc_rag_corpus/b.md")
        store.replace_document_chunks(doc1, [_chunk("c1", "d1", doc1.source_path, [1.0, 0.0])], [[1.0, 0.0]])
        store.replace_document_chunks(doc2, [_chunk("c2", "d2", doc2.source_path, [1.0, 0.0])], [[1.0, 0.0]])

        count = store.mark_missing_documents_deleted({"my_md/doc_rag_corpus/a.md"})

        assert count == 1
        assert store.get_document("my_md/doc_rag_corpus/a.md").status == "active"
        assert store.get_document("my_md/doc_rag_corpus/b.md").status == "deleted"
    finally:
        store.close()
```

- [ ] **Step 2: Run RED tests**

Run:

```bash
uv run --with pytest pytest tests/test_doc_rag_store_search.py -v
```

Expected: fails because store methods do not exist.

- [ ] **Step 3: Implement store extensions**

Implementation requirements:

- Add `_cosine_similarity(a, b)` helper.
- Add `_normalize_embedding(vec)` helper.
- Add `_l2dist_to_cosine(distance)` helper.
- Add `_snippet(text, max_chars=240)` helper.
- Add `list_documents`, `list_chunks`, `mark_missing_documents_deleted`, `search_vector`.
- Keep all writes under `self._lock`.
- Do not change existing method signatures.

- [ ] **Step 4: Run store search tests**

Run:

```bash
uv run --with pytest pytest tests/test_doc_rag_store.py tests/test_doc_rag_store_search.py -v
```

Expected: all store tests pass.

---

## Task 3: P5 Indexer

**Files:**

- Create: `doc_rag/indexer.py`
- Test: `tests/test_doc_rag_indexer.py`

**Interfaces:**

- Consumes:
  - `MarkdownLoader.load_all() -> LoaderResult`
  - `MarkdownChunker.chunk(document) -> list[ChunkRecord]`
  - `DocEmbeddingClient.embed_texts(texts) -> list[list[float]]`
  - `DocRagStore.replace_document_chunks(document, chunks, embeddings)`
  - `DocRagStore.start_index_run(...)`
  - `DocRagStore.record_index_run_doc(...)`
  - `DocRagStore.finish_index_run(...)`
- Produces:
  - `IndexOptions(rebuild: bool = False, dry_run: bool = False)`
  - `IndexSummary`
  - `DocRagIndexer.run(options: IndexOptions | None = None) -> IndexSummary`

### Required Behavior

- Loads documents from configured corpus.
- Records loader errors in `index_run_docs`.
- For each loaded document:
  - if existing document same `content_hash` and not rebuild: `skipped_unchanged`
  - if new: `indexed`
  - if changed: `indexed`
  - if embedding/chunking fails: `failed`
- `dry_run=True` records planned actions but does not replace chunks.
- `rebuild=True` re-indexes all loaded documents.
- Missing previously active documents are marked `deleted`.
- Changed document indexing failure must keep the old active document and old chunks.
- For each indexed document:
  - chunk first
  - build embedding text for each chunk
  - embed all chunk texts
  - set each chunk `embedding_status = "ready"`
  - call `replace_document_chunks`
- If any document fails, run status is `partial_failed`.
- If system-level setup fails before document processing, run status is `failed`.
- `meta` receives sanitized index metadata:
  - `schema_version`
  - `index_format_version`
  - `embedding_mode`
  - `embedding_model`
  - `embedding_base_url`
  - `embedding_dim`
  - `chunker_version`
  - `source_root`
  - `include_globs`
  - `allowed_extensions`
  - `index_config_hash`
- `api_key` must not be written to meta.

### Step Plan

- [ ] **Step 1: Write failing indexer tests**

Create `tests/test_doc_rag_indexer.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from agent.config_models import Config
from doc_rag.indexer import DocRagIndexer, IndexOptions
from doc_rag.store import DocRagStore


class _FakeEmbeddingClient:
    def __init__(self, dim: int = 2, fail_on: str = "") -> None:
        self.dim = dim
        self.fail_on = fail_on
        self.texts: list[str] = []

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if self.fail_on and any(self.fail_on in text for text in texts):
            raise ValueError("fake embedding failure")
        self.texts.extend(texts)
        return [[1.0, 0.0] for _ in texts]


def _config(repo: Path, db_path: Path) -> Config:
    cfg = Config(
        provider="deepseek",
        model="deepseek-chat",
        api_key="main-key",
        base_url="https://main.example/v1",
        system_prompt="test",
    )
    cfg.doc_rag.enabled = True
    cfg.doc_rag.source_root = str(repo)
    cfg.doc_rag.store_path = str(db_path)
    cfg.doc_rag.embedding.mode = "custom"
    cfg.doc_rag.embedding.model = "fake"
    cfg.doc_rag.embedding.api_key = "secret-doc-key"
    cfg.doc_rag.embedding.base_url = "https://embedding.example/v1"
    cfg.doc_rag.embedding.dim = 2
    return cfg


def _write_doc(repo: Path, name: str, body: str) -> None:
    path = repo / "my_md" / "doc_rag_corpus" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


@pytest.mark.anyio
async def test_indexer_indexes_new_documents_and_writes_sanitized_meta(tmp_path):
    repo = tmp_path / "repo"
    _write_doc(repo, "a.md", "# A\n\nAgent runtime docs")
    store = DocRagStore(tmp_path / "doc_rag.db", vec_dim=2)
    cfg = _config(repo, tmp_path / "doc_rag.db")
    embedder = _FakeEmbeddingClient()

    try:
        summary = await DocRagIndexer(cfg, store=store, embedding_client=embedder).run()

        assert summary.status == "succeeded"
        assert summary.docs_indexed == 1
        assert summary.docs_failed == 0
        docs = store.list_documents()
        assert docs[0].source_path == "my_md/doc_rag_corpus/a.md"
        chunks = store.list_chunks("my_md/doc_rag_corpus/a.md")
        assert chunks
        assert chunks[0].embedding_status == "ready"
        meta = store.get_meta()
        assert meta["embedding_model"] == "fake"
        assert meta["embedding_dim"] == 2
        assert "secret-doc-key" not in str(meta)
    finally:
        store.close()


@pytest.mark.anyio
async def test_indexer_skips_unchanged_documents(tmp_path):
    repo = tmp_path / "repo"
    _write_doc(repo, "a.md", "# A\n\nStable")
    store = DocRagStore(tmp_path / "doc_rag.db", vec_dim=2)
    cfg = _config(repo, tmp_path / "doc_rag.db")

    try:
        await DocRagIndexer(cfg, store=store, embedding_client=_FakeEmbeddingClient()).run()
        second_embedder = _FakeEmbeddingClient()
        summary = await DocRagIndexer(cfg, store=store, embedding_client=second_embedder).run()

        assert summary.docs_skipped == 1
        assert summary.docs_indexed == 0
        assert second_embedder.texts == []
    finally:
        store.close()


@pytest.mark.anyio
async def test_indexer_dry_run_does_not_write_chunks(tmp_path):
    repo = tmp_path / "repo"
    _write_doc(repo, "a.md", "# A\n\nDry run")
    store = DocRagStore(tmp_path / "doc_rag.db", vec_dim=2)
    cfg = _config(repo, tmp_path / "doc_rag.db")

    try:
        summary = await DocRagIndexer(
            cfg, store=store, embedding_client=_FakeEmbeddingClient()
        ).run(IndexOptions(dry_run=True))

        assert summary.docs_indexed == 1
        assert store.list_documents() == []
        assert store.list_chunks() == []
    finally:
        store.close()


@pytest.mark.anyio
async def test_indexer_partial_failure_keeps_other_documents(tmp_path):
    repo = tmp_path / "repo"
    _write_doc(repo, "a.md", "# A\n\nGood")
    _write_doc(repo, "b.md", "# B\n\nFAIL_ME")
    store = DocRagStore(tmp_path / "doc_rag.db", vec_dim=2)
    cfg = _config(repo, tmp_path / "doc_rag.db")

    try:
        summary = await DocRagIndexer(
            cfg,
            store=store,
            embedding_client=_FakeEmbeddingClient(fail_on="FAIL_ME"),
        ).run()

        assert summary.status == "partial_failed"
        assert summary.docs_indexed == 1
        assert summary.docs_failed == 1
        assert store.get_document("my_md/doc_rag_corpus/a.md") is not None
        assert store.get_document("my_md/doc_rag_corpus/b.md") is None
    finally:
        store.close()


@pytest.mark.anyio
async def test_indexer_records_loader_errors(tmp_path):
    repo = tmp_path / "repo"
    corpus = repo / "my_md" / "doc_rag_corpus"
    corpus.mkdir(parents=True)
    (corpus / "empty.md").write_text("   \n", encoding="utf-8")
    store = DocRagStore(tmp_path / "doc_rag.db", vec_dim=2)
    cfg = _config(repo, tmp_path / "doc_rag.db")

    try:
        summary = await DocRagIndexer(
            cfg, store=store, embedding_client=_FakeEmbeddingClient()
        ).run()

        docs = store.list_index_run_docs(summary.run_id)
        assert summary.status == "partial_failed"
        assert summary.docs_failed == 1
        assert docs[0]["source_path"] == "my_md/doc_rag_corpus/empty.md"
        assert docs[0]["error_type"] == "skip_empty"
    finally:
        store.close()


@pytest.mark.anyio
async def test_indexer_rebuild_reindexes_unchanged_documents(tmp_path):
    repo = tmp_path / "repo"
    _write_doc(repo, "a.md", "# A\n\nStable")
    store = DocRagStore(tmp_path / "doc_rag.db", vec_dim=2)
    cfg = _config(repo, tmp_path / "doc_rag.db")

    try:
        await DocRagIndexer(cfg, store=store, embedding_client=_FakeEmbeddingClient()).run()
        second_embedder = _FakeEmbeddingClient()
        summary = await DocRagIndexer(cfg, store=store, embedding_client=second_embedder).run(
            IndexOptions(rebuild=True)
        )

        assert summary.docs_indexed == 1
        assert summary.docs_skipped == 0
        assert second_embedder.texts
    finally:
        store.close()


@pytest.mark.anyio
async def test_indexer_marks_missing_documents_deleted(tmp_path):
    repo = tmp_path / "repo"
    _write_doc(repo, "a.md", "# A\n\nTo delete")
    db_path = tmp_path / "doc_rag.db"
    store = DocRagStore(db_path, vec_dim=2)
    cfg = _config(repo, db_path)

    try:
        await DocRagIndexer(cfg, store=store, embedding_client=_FakeEmbeddingClient()).run()
        (repo / "my_md" / "doc_rag_corpus" / "a.md").unlink()
        summary = await DocRagIndexer(cfg, store=store, embedding_client=_FakeEmbeddingClient()).run()

        assert summary.docs_deleted == 1
        assert store.get_document("my_md/doc_rag_corpus/a.md").status == "deleted"
    finally:
        store.close()


@pytest.mark.anyio
async def test_indexer_changed_document_failure_keeps_old_chunks(tmp_path):
    repo = tmp_path / "repo"
    _write_doc(repo, "a.md", "# A\n\nOld")
    db_path = tmp_path / "doc_rag.db"
    store = DocRagStore(db_path, vec_dim=2)
    cfg = _config(repo, db_path)

    try:
        await DocRagIndexer(cfg, store=store, embedding_client=_FakeEmbeddingClient()).run()
        old_doc = store.get_document("my_md/doc_rag_corpus/a.md")
        old_chunks = store.list_chunks("my_md/doc_rag_corpus/a.md")
        _write_doc(repo, "a.md", "# A\n\nFAIL_ME changed")

        summary = await DocRagIndexer(
            cfg,
            store=store,
            embedding_client=_FakeEmbeddingClient(fail_on="FAIL_ME"),
        ).run()

        assert summary.status == "partial_failed"
        assert store.get_document("my_md/doc_rag_corpus/a.md").content_hash == old_doc.content_hash
        assert [chunk.chunk_id for chunk in store.list_chunks("my_md/doc_rag_corpus/a.md")] == [
            chunk.chunk_id for chunk in old_chunks
        ]
    finally:
        store.close()
```

- [ ] **Step 2: Run RED tests**

Run:

```bash
uv run --with pytest pytest tests/test_doc_rag_indexer.py -v
```

Expected: fails because `doc_rag.indexer` does not exist.

- [ ] **Step 3: Implement `doc_rag/indexer.py`**

Implementation requirements:

- Define `IndexOptions`.
- Define `IndexSummary`.
- Define `DocRagIndexer`.
- Constructor accepts optional `store`, `loader`, `chunker`, `embedding_client` for tests.
- If no `store`, create `DocRagStore(config.doc_rag.store_path, vec_dim=config.doc_rag.embedding.dim)`.
- If no `embedding_client`, resolve settings and instantiate `DocEmbeddingClient`.
- Use `build_embedding_text(chunk)` for each chunk.
- Write sanitized meta with no `api_key`.
- Use `store.start_index_run`, `record_index_run_doc`, `finish_index_run`.

- [ ] **Step 4: Run indexer tests**

Run:

```bash
uv run --with pytest pytest tests/test_doc_rag_indexer.py -v
```

Expected: all tests pass.

---

## Task 4: P6 Retriever and JSONL Trace

**Files:**

- Create: `doc_rag/retriever.py`
- Create: `doc_rag/trace.py`
- Test: `tests/test_doc_rag_retriever.py`

**Interfaces:**

- Consumes:
  - `DocRagStore.search_vector(query_vec, top_k, similarity_threshold)`
  - `DocEmbeddingClient.embed_texts([query])`
  - `DocRagConfig.retrieval`
  - `DocRagConfig.trace`
- Produces:
  - `DocRagRetriever.search(query: str, top_k: int | None = None) -> SearchResult`
  - `write_retrieval_trace(path, event) -> None`

### Required Behavior

- Empty query returns `SearchResult(error="empty_query")`.
- Query embedding uses `DocEmbeddingClient.embed_texts([query])`.
- Retrieval uses config `top_k` if method `top_k` is not provided.
- Retrieval filters using `similarity_threshold`.
- Trace event includes:
  - `trace_id`
  - `query`
  - `top_k`
  - `hit_count`
  - `hits`
  - `latency_ms`
  - `retrieval_mode`
  - `error`
  - `created_at`
- Trace hit includes:
  - `rank`
  - `chunk_id`
  - `source_path`
  - `heading_path`
  - `score`
  - `snippet`
  - optionally `content` only when `trace.include_content = true`
- Trace must not include API keys.
- If trace path parent does not exist, create it.

### Step Plan

- [ ] **Step 1: Write failing retriever tests**

Create `tests/test_doc_rag_retriever.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.config_models import Config
from doc_rag.indexer import DocRagIndexer
from doc_rag.retriever import DocRagRetriever
from doc_rag.store import DocRagStore


class _FakeEmbeddingClient:
    def __init__(self, query_vec: list[float] | None = None) -> None:
        self.query_vec = query_vec or [1.0, 0.0]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if len(texts) == 1 and "runtime" in texts[0].lower():
            return [self.query_vec]
        return [[1.0, 0.0] for _ in texts]


def _config(repo: Path, db_path: Path, trace_path: Path) -> Config:
    cfg = Config(
        provider="deepseek",
        model="deepseek-chat",
        api_key="main-secret",
        base_url="https://main.example/v1",
        system_prompt="test",
    )
    cfg.doc_rag.enabled = True
    cfg.doc_rag.source_root = str(repo)
    cfg.doc_rag.store_path = str(db_path)
    cfg.doc_rag.embedding.mode = "custom"
    cfg.doc_rag.embedding.model = "fake"
    cfg.doc_rag.embedding.api_key = "doc-secret"
    cfg.doc_rag.embedding.base_url = "https://embedding.example/v1"
    cfg.doc_rag.embedding.dim = 2
    cfg.doc_rag.retrieval.top_k = 3
    cfg.doc_rag.retrieval.similarity_threshold = 0.1
    cfg.doc_rag.trace.path = str(trace_path)
    cfg.doc_rag.trace.enabled = True
    return cfg


def _write_doc(repo: Path) -> None:
    path = repo / "my_md" / "doc_rag_corpus" / "runtime.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Runtime\n\nAgent runtime manages tool calls.", encoding="utf-8")


@pytest.mark.anyio
async def test_retriever_returns_hits_and_writes_trace(tmp_path):
    repo = tmp_path / "repo"
    db_path = tmp_path / "doc_rag.db"
    trace_path = tmp_path / "trace" / "retrieval.jsonl"
    _write_doc(repo)
    cfg = _config(repo, db_path, trace_path)
    store = DocRagStore(db_path, vec_dim=2)
    try:
        await DocRagIndexer(
            cfg, store=store, embedding_client=_FakeEmbeddingClient()
        ).run()

        result = await DocRagRetriever(
            cfg, store=store, embedding_client=_FakeEmbeddingClient()
        ).search("runtime")

        assert result.error == ""
        assert result.hits
        assert result.hits[0].source_path == "my_md/doc_rag_corpus/runtime.md"
        assert result.trace_id

        lines = trace_path.read_text(encoding="utf-8").splitlines()
        event = json.loads(lines[-1])
        assert event["trace_id"] == result.trace_id
        assert event["hit_count"] == len(result.hits)
        assert "doc-secret" not in lines[-1]
        assert "main-secret" not in lines[-1]
    finally:
        store.close()


@pytest.mark.anyio
async def test_retriever_empty_query_returns_error(tmp_path):
    cfg = _config(tmp_path / "repo", tmp_path / "doc_rag.db", tmp_path / "trace.jsonl")
    store = DocRagStore(tmp_path / "doc_rag.db", vec_dim=2)
    try:
        result = await DocRagRetriever(
            cfg, store=store, embedding_client=_FakeEmbeddingClient()
        ).search("  ")

        assert result.error == "empty_query"
        assert result.hits == []
    finally:
        store.close()


@pytest.mark.anyio
async def test_retriever_can_include_content_in_trace_when_enabled(tmp_path):
    repo = tmp_path / "repo"
    db_path = tmp_path / "doc_rag.db"
    trace_path = tmp_path / "trace.jsonl"
    _write_doc(repo)
    cfg = _config(repo, db_path, trace_path)
    cfg.doc_rag.trace.include_content = True
    cfg.doc_rag.trace.max_content_chars = 20
    store = DocRagStore(db_path, vec_dim=2)
    try:
        await DocRagIndexer(
            cfg, store=store, embedding_client=_FakeEmbeddingClient()
        ).run()
        await DocRagRetriever(
            cfg, store=store, embedding_client=_FakeEmbeddingClient()
        ).search("runtime")

        event = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[-1])
        assert "content" in event["hits"][0]
        assert len(event["hits"][0]["content"]) <= 20
    finally:
        store.close()
```

- [ ] **Step 2: Run RED tests**

Run:

```bash
uv run --with pytest pytest tests/test_doc_rag_retriever.py -v
```

Expected: fails because `doc_rag.retriever` does not exist.

- [ ] **Step 3: Implement trace writer**

Create `doc_rag/trace.py` with:

```python
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def new_trace_id() -> str:
    return uuid.uuid4().hex


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_retrieval_trace(path: str, event: dict[str, Any]) -> None:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
```

- [ ] **Step 4: Implement retriever**

Create `doc_rag/retriever.py` with:

- `DocRagRetriever.__init__(config, store=None, embedding_client=None)`
- `async search(query, top_k=None) -> SearchResult`
- uses `store.search_vector`
- writes trace when `config.doc_rag.trace.enabled`
- returns structured `SearchResult`

- [ ] **Step 5: Run retriever tests**

Run:

```bash
uv run --with pytest pytest tests/test_doc_rag_retriever.py -v
```

Expected: all tests pass.

---

## Task 5: Manual Check Scripts and Documentation Update

**Files:**

- Create: `scripts/doc_rag_index_check.py`
- Create: `scripts/doc_rag_retrieve_check.py`
- Modify: `my_md/rag/11-document-rag-implementation-plan.md`
- Modify: `my_md/rag/README.md` if it has a progress index

**Interfaces:**

- Consumes: implemented `DocRagIndexer`, `DocRagRetriever`
- Produces: manual commands for human verification

### Required Behavior

- Manual scripts must be runnable with `uv run python -m scripts.<name>`.
- Scripts must not print API keys.
- Manual scripts are standalone developer checks and may run even when `doc_rag.enabled = false`; Agent tool exposure remains controlled by `enabled` in later P7+ work.
- Index script prints:
  - status
  - docs scanned/indexed/skipped/failed/deleted
  - store path
- Retrieve script prints:
  - query
  - trace_id
  - top hits with source path, heading path, score, snippet

### Step Plan

- [ ] **Step 1: Add `scripts/doc_rag_index_check.py`**

Script outline:

```python
from __future__ import annotations

import asyncio

from agent.config import load_config
from doc_rag.indexer import DocRagIndexer, IndexOptions


async def main() -> None:
    cfg = load_config("config.toml")
    summary = await DocRagIndexer(cfg).run(IndexOptions(rebuild=False, dry_run=False))
    print("status:", summary.status)
    print("docs_scanned:", summary.docs_scanned)
    print("docs_indexed:", summary.docs_indexed)
    print("docs_skipped:", summary.docs_skipped)
    print("docs_deleted:", summary.docs_deleted)
    print("docs_failed:", summary.docs_failed)
    print("store_path:", cfg.doc_rag.store_path)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Add `scripts/doc_rag_retrieve_check.py`**

Script outline:

```python
from __future__ import annotations

import asyncio
import sys

from agent.config import load_config
from doc_rag.retriever import DocRagRetriever


async def main() -> None:
    query = " ".join(sys.argv[1:]).strip() or "agent runtime"
    cfg = load_config("config.toml")
    result = await DocRagRetriever(cfg).search(query)
    print("query:", query)
    print("trace_id:", result.trace_id)
    print("error:", result.error)
    print("hits:", len(result.hits))
    for hit in result.hits:
        print("---")
        print("rank:", hit.rank)
        print("score:", hit.score)
        print("source_path:", hit.source_path)
        print("heading_path:", hit.heading_path)
        print("chunk_id:", hit.chunk_id)
        print("snippet:", hit.snippet)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Update implementation progress document**

Update `my_md/rag/11-document-rag-implementation-plan.md`:

- Mark P4 embedding client complete.
- Mark P5 indexer complete.
- Mark P6 retriever complete.
- Record test commands and result counts.
- Record manual commands:

```bash
uv run python -m scripts.doc_rag_index_check
uv run python -m scripts.doc_rag_retrieve_check "agent runtime"
```

---

## Full Verification

After all P4-P6 tasks:

```bash
uv run --with pytest pytest \
  tests/test_doc_rag_config.py \
  tests/test_doc_rag_models.py \
  tests/test_doc_rag_store.py \
  tests/test_doc_rag_store_search.py \
  tests/test_doc_rag_loader.py \
  tests/test_doc_rag_chunker.py \
  tests/test_doc_rag_embedding.py \
  tests/test_doc_rag_indexer.py \
  tests/test_doc_rag_retriever.py \
  -v
```

Expected: all Document RAG tests pass.

Existing regression:

```bash
uv run --with pytest pytest \
  tests/test_memory2_retrieval_baseline.py \
  tests/test_tool_discovery_routing.py \
  -v
```

Expected: existing memory/tool discovery tests still pass.

Format and syntax:

```bash
uv run --with black black --check doc_rag tests/test_doc_rag_*.py scripts/doc_rag_index_check.py scripts/doc_rag_retrieve_check.py
python3 -m compileall -q doc_rag scripts
```

Expected: Black clean; compileall clean.

## Manual Verification

Prepare corpus:

```bash
mkdir -p my_md/doc_rag_corpus
cat > my_md/doc_rag_corpus/manual_rag_test.md <<'EOF'
# Agent Runtime

Agent runtime coordinates model calls, tool calls, iteration limits, and context assembly.

## Document RAG

Document RAG indexes Markdown files, chunks them by heading, embeds chunks, and retrieves evidence for user questions.
EOF
```

Run indexing:

```bash
uv run python -m scripts.doc_rag_index_check
```

Expected shape:

```text
status: succeeded
docs_scanned: ...
docs_indexed: ...
store_path: ~/.akashic/workspace/doc_rag/doc_rag.db
```

Run retrieval:

```bash
uv run python -m scripts.doc_rag_retrieve_check "what does agent runtime coordinate?"
```

Expected shape:

```text
query: what does agent runtime coordinate?
trace_id: ...
error:
hits: 1
---
rank: 1
score: ...
source_path: my_md/doc_rag_corpus/manual_rag_test.md
heading_path: Agent Runtime
snippet: Agent runtime coordinates model calls...
```

## Acceptance Matrix

| Requirement | Test / Check |
| --- | --- |
| embedding config inherits memory config | `test_resolve_embedding_settings_inherits_memory_config` |
| embedding config supports custom config | `test_resolve_embedding_settings_custom_config` |
| API key redacted in settings repr | embedding config tests |
| embedding text includes source/title/heading/content | `test_build_embedding_text_includes_document_context` |
| embedding count/dim validation | `test_doc_embedding_client_validates_count_and_dim`, `test_doc_embedding_client_rejects_dim_mismatch` |
| store can list documents/chunks | `test_store_lists_documents_and_chunks` |
| store vector search filters pending chunks | `test_store_search_vector_filters_and_ranks_ready_active_chunks` |
| missing docs can be marked deleted | `test_store_marks_missing_documents_deleted` |
| indexer indexes new docs | `test_indexer_indexes_new_documents_and_writes_sanitized_meta` |
| indexer skips unchanged docs | `test_indexer_skips_unchanged_documents` |
| dry run does not write chunks | `test_indexer_dry_run_does_not_write_chunks` |
| single doc failure becomes partial_failed | `test_indexer_partial_failure_keeps_other_documents` |
| retriever returns hits | `test_retriever_returns_hits_and_writes_trace` |
| retriever writes JSONL trace | `test_retriever_returns_hits_and_writes_trace` |
| trace excludes API keys | retriever trace test |
| trace content is optional and capped | `test_retriever_can_include_content_in_trace_when_enabled` |

## Out of Scope for P4-P6

- No `search_docs` tool.
- No `fetch_doc_chunk` tool.
- No Agent prompt changes.
- No citation enforcement in final answers.
- No hybrid search.
- No rerank.
- No query rewrite.
- No LLM judge.
- No GraphRAG.
- No LLM Wiki.

## Commit Plan

Commit after full verification:

```bash
git add \
  doc_rag \
  tests/test_doc_rag_embedding.py \
  tests/test_doc_rag_store_search.py \
  tests/test_doc_rag_indexer.py \
  tests/test_doc_rag_retriever.py \
  scripts/doc_rag_index_check.py \
  scripts/doc_rag_retrieve_check.py \
  my_md/rag/11-document-rag-implementation-plan.md \
  my_md/rag/16-document-rag-p4-p6-implementation-plan.md

git commit -m "feat(doc-rag): add indexing and retrieval backend"
```

## Self-Review Checklist

- P4-P6 does not modify `AgentLoop`.
- P4-P6 does not register tools.
- Unit tests do not call real embedding APIs.
- API keys do not appear in meta, trace, logs, reports, or repr strings.
- Changed/new documents are replaced only after embeddings are ready.
- `vec_chunks.rowid` remains aligned with `chunks.rowid`.
- `source_path` remains repo-relative POSIX.
- Retrieval trace is JSONL and append-only.
- Existing memory2 retrieval tests still pass.
