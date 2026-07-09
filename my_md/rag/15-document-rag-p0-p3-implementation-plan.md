# Document RAG P0-P3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first implementation stage of Document RAG: config/models, SQLite schema/store, Markdown loader, and Markdown chunker.

**Architecture:** Add a new `doc_rag` package that stays independent from `memory2` and `AgentLoop`. P0-P3 must be testable without LLM calls, embedding APIs, tool registration, or CLI runtime.

**Tech Stack:** Python 3.12+, dataclasses, tomllib config loading, sqlite3, optional sqlite-vec initialization pattern from `memory2.store`, pytest.

## Global Constraints

- Do not write document chunks into `memory2.db`.
- Do not modify `AgentLoop` in P0-P3.
- Do not register `search_docs` or `fetch_doc_chunk` in P0-P3.
- Do not call embedding APIs in P0-P3.
- Default Document RAG config must be disabled: `enabled = false`.
- Default corpus is `my_md/doc_rag_corpus/**/*.md`.
- `source_path` must be repo-relative POSIX path.
- API keys must not be written to meta, trace, logs, or reports.
- Loader and chunker must be unit-testable without SQLite.

---

## File Structure

Create:

- `doc_rag/__init__.py`: package exports.
- `doc_rag/models.py`: dataclasses and constants shared by P0-P3.
- `doc_rag/schema.sql`: SQLite schema for v0 store.
- `doc_rag/store.py`: SQLite store, schema init, meta, documents, chunks, index run records.
- `doc_rag/loader.py`: Markdown file scanning and `LoadedDocument` creation.
- `doc_rag/chunker.py`: heading-aware Markdown chunker.
- `tests/test_doc_rag_config.py`: config loading tests.
- `tests/test_doc_rag_store.py`: store/schema tests.
- `tests/test_doc_rag_loader.py`: loader tests.
- `tests/test_doc_rag_chunker.py`: chunker tests.

Modify:

- `agent/config_models.py`: add `DocRagConfig` and nested config dataclasses.
- `agent/config.py`: load `[doc_rag]` config.
- `config.example.toml`: document default `[doc_rag]` config.
- `my_md/rag/11-document-rag-implementation-plan.md`: mark P0-P3 plan created after implementation plan is accepted.

---

### Task 1: P0 Config Models

**Files:**
- Modify: `agent/config_models.py`
- Modify: `agent/config.py`
- Modify: `config.example.toml`
- Test: `tests/test_doc_rag_config.py`

**Interfaces:**
- Produces: `DocRagConfig`, `DocRagSourcesConfig`, `DocRagChunkingConfig`, `DocRagEmbeddingConfig`, `DocRagRetrievalConfig`, `DocRagTraceConfig`, `DocRagCitationConfig`, `DocRagEvalConfig`
- Produces: `Config.doc_rag: DocRagConfig`
- Consumes: existing `MemoryEmbeddingConfig` remains unchanged

- [ ] **Step 1: Write failing config tests**

Create `tests/test_doc_rag_config.py`:

```python
from __future__ import annotations

from pathlib import Path

from agent.config import load_config


def _base_config(extra: str = "") -> str:
    return f'''
provider = "deepseek"
model = "deepseek-chat"
api_key = "sk-test"
system_prompt = "test"

[memory.embedding]
model = "text-embedding-v3"
api_key = "mem-key"
base_url = "https://example.invalid/v1"

{extra}
'''


def test_doc_rag_defaults_disabled(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(_base_config(), encoding="utf-8")

    cfg = load_config(path)

    assert cfg.doc_rag.enabled is False
    assert cfg.doc_rag.source_root == "."
    assert cfg.doc_rag.sources.include_globs == ["my_md/doc_rag_corpus/**/*.md"]
    assert cfg.doc_rag.chunking.target_chunk_chars == 1600
    assert cfg.doc_rag.embedding.mode == "inherit_memory"
    assert cfg.doc_rag.embedding.dim == 1024
    assert cfg.doc_rag.retrieval.top_k == 5
    assert cfg.doc_rag.trace.include_content is False
    assert cfg.doc_rag.citation.format == "[source_path > heading_path]"
    assert cfg.doc_rag.eval.eval_set_path == "my_md/rag/eval_sets/doc_rag_eval_v0.jsonl"


def test_doc_rag_loads_nested_config(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        _base_config(
            '''
[doc_rag]
enabled = true
source_root = "/repo"
store_path = "/tmp/doc_rag.db"
collection_id = "docs"

[doc_rag.sources]
include_globs = ["docs/**/*.md"]
exclude_globs = ["**/*.tmp"]
allowed_extensions = [".md"]
max_file_size_bytes = 1234
allow_external_symlink = true

[doc_rag.chunking]
chunker_version = "heading_block_v0"
target_chunk_chars = 1000
max_chunk_chars = 1500
min_chunk_chars = 200
chunk_overlap_chars = 100

[doc_rag.embedding]
mode = "custom"
model = "embed-x"
api_key = "${DOC_RAG_TEST_KEY}"
base_url = "https://emb.invalid/v1"
dim = 768
batch_size = 8
max_retries = 3
timeout_seconds = 20

[doc_rag.retrieval]
top_k = 7
similarity_threshold = 0.5
retrieval_mode = "vector_only"
fallback_enabled = false

[doc_rag.trace]
enabled = false
format = "jsonl"
path = "/tmp/trace.jsonl"
include_content = true
max_content_chars = 3000

[doc_rag.citation]
required_for_doc_answer = false
format = "[source]"
include_chunk_id_for_debug = true
on_no_hits = "state_no_evidence"

[doc_rag.eval]
eval_set_path = "eval.jsonl"
report_dir = "reports"
'''
        ),
        encoding="utf-8",
    )

    cfg = load_config(path)

    assert cfg.doc_rag.enabled is True
    assert cfg.doc_rag.source_root == "/repo"
    assert cfg.doc_rag.sources.include_globs == ["docs/**/*.md"]
    assert cfg.doc_rag.embedding.mode == "custom"
    assert cfg.doc_rag.embedding.model == "embed-x"
    assert cfg.doc_rag.embedding.dim == 768
    assert cfg.doc_rag.retrieval.top_k == 7
    assert cfg.doc_rag.trace.include_content is True
    assert cfg.doc_rag.citation.include_chunk_id_for_debug is True
    assert cfg.doc_rag.eval.report_dir == "reports"
```

- [ ] **Step 2: Run failing config tests**

Run:

```bash
pytest tests/test_doc_rag_config.py -v
```

Expected: fails because `Config` has no `doc_rag` attribute.

- [ ] **Step 3: Add config dataclasses**

In `agent/config_models.py`, add dataclasses after `MemoryConfig`:

```python
@dataclass
class DocRagSourcesConfig:
    include_globs: list[str] = field(
        default_factory=lambda: ["my_md/doc_rag_corpus/**/*.md"]
    )
    exclude_globs: list[str] = field(
        default_factory=lambda: [
            "**/*.db",
            "**/*.sqlite",
            "**/*.jsonl",
            "**/*.log",
            "**/__pycache__/**",
            "**/.pytest_cache/**",
        ]
    )
    allowed_extensions: list[str] = field(default_factory=lambda: [".md", ".markdown"])
    max_file_size_bytes: int = 2 * 1024 * 1024
    allow_external_symlink: bool = False


@dataclass
class DocRagChunkingConfig:
    chunker_version: str = "heading_block_v0"
    target_chunk_chars: int = 1600
    max_chunk_chars: int = 2400
    min_chunk_chars: int = 300
    chunk_overlap_chars: int = 200


@dataclass
class DocRagEmbeddingConfig:
    mode: str = "inherit_memory"
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    dim: int = 1024
    batch_size: int = 16
    max_retries: int = 2
    timeout_seconds: int = 30


@dataclass
class DocRagRetrievalConfig:
    top_k: int = 5
    similarity_threshold: float = 0.45
    retrieval_mode: str = "vector_only"
    fallback_enabled: bool = True


@dataclass
class DocRagTraceConfig:
    enabled: bool = True
    format: str = "jsonl"
    path: str = "~/.akashic/workspace/doc_rag/retrieval_traces.jsonl"
    include_content: bool = False
    max_content_chars: int = 2000


@dataclass
class DocRagCitationConfig:
    required_for_doc_answer: bool = True
    format: str = "[source_path > heading_path]"
    include_chunk_id_for_debug: bool = False
    on_no_hits: str = "state_no_evidence"


@dataclass
class DocRagEvalConfig:
    eval_set_path: str = "my_md/rag/eval_sets/doc_rag_eval_v0.jsonl"
    report_dir: str = "my_md/rag/eval_reports"


@dataclass
class DocRagConfig:
    enabled: bool = False
    source_root: str = "."
    store_path: str = "~/.akashic/workspace/doc_rag/doc_rag.db"
    collection_id: str = "default"
    sources: DocRagSourcesConfig = field(default_factory=DocRagSourcesConfig)
    chunking: DocRagChunkingConfig = field(default_factory=DocRagChunkingConfig)
    embedding: DocRagEmbeddingConfig = field(default_factory=DocRagEmbeddingConfig)
    retrieval: DocRagRetrievalConfig = field(default_factory=DocRagRetrievalConfig)
    trace: DocRagTraceConfig = field(default_factory=DocRagTraceConfig)
    citation: DocRagCitationConfig = field(default_factory=DocRagCitationConfig)
    eval: DocRagEvalConfig = field(default_factory=DocRagEvalConfig)
```

Add `doc_rag: DocRagConfig = field(default_factory=DocRagConfig)` to `Config`.

Add new classes to `__all__`.

- [ ] **Step 4: Load doc_rag config**

In `agent/config.py`, import new dataclasses and add:

```python
def _load_doc_rag_config(data: dict) -> DocRagConfig:
    raw = _as_dict(data.get("doc_rag"))
    sources = _as_dict(raw.get("sources"))
    chunking = _as_dict(raw.get("chunking"))
    embedding = _as_dict(raw.get("embedding"))
    retrieval = _as_dict(raw.get("retrieval"))
    trace = _as_dict(raw.get("trace"))
    citation = _as_dict(raw.get("citation"))
    eval_cfg = _as_dict(raw.get("eval"))
    return DocRagConfig(
        enabled=bool(raw.get("enabled", False)),
        source_root=str(raw.get("source_root", ".")),
        store_path=str(
            raw.get("store_path", "~/.akashic/workspace/doc_rag/doc_rag.db")
        ),
        collection_id=str(raw.get("collection_id", "default")),
        sources=DocRagSourcesConfig(
            include_globs=[
                str(x)
                for x in sources.get(
                    "include_globs", ["my_md/doc_rag_corpus/**/*.md"]
                )
            ],
            exclude_globs=[
                str(x)
                for x in sources.get(
                    "exclude_globs",
                    [
                        "**/*.db",
                        "**/*.sqlite",
                        "**/*.jsonl",
                        "**/*.log",
                        "**/__pycache__/**",
                        "**/.pytest_cache/**",
                    ],
                )
            ],
            allowed_extensions=[
                str(x).lower()
                for x in sources.get("allowed_extensions", [".md", ".markdown"])
            ],
            max_file_size_bytes=int(
                sources.get("max_file_size_bytes", 2 * 1024 * 1024)
            ),
            allow_external_symlink=bool(
                sources.get("allow_external_symlink", False)
            ),
        ),
        chunking=DocRagChunkingConfig(
            chunker_version=str(chunking.get("chunker_version", "heading_block_v0")),
            target_chunk_chars=int(chunking.get("target_chunk_chars", 1600)),
            max_chunk_chars=int(chunking.get("max_chunk_chars", 2400)),
            min_chunk_chars=int(chunking.get("min_chunk_chars", 300)),
            chunk_overlap_chars=int(chunking.get("chunk_overlap_chars", 200)),
        ),
        embedding=DocRagEmbeddingConfig(
            mode=str(embedding.get("mode", "inherit_memory")),
            model=str(embedding.get("model", "")),
            api_key=_resolve(str(embedding.get("api_key", ""))),
            base_url=str(embedding.get("base_url", "")),
            dim=int(embedding.get("dim", 1024)),
            batch_size=int(embedding.get("batch_size", 16)),
            max_retries=int(embedding.get("max_retries", 2)),
            timeout_seconds=int(embedding.get("timeout_seconds", 30)),
        ),
        retrieval=DocRagRetrievalConfig(
            top_k=int(retrieval.get("top_k", 5)),
            similarity_threshold=float(retrieval.get("similarity_threshold", 0.45)),
            retrieval_mode=str(retrieval.get("retrieval_mode", "vector_only")),
            fallback_enabled=bool(retrieval.get("fallback_enabled", True)),
        ),
        trace=DocRagTraceConfig(
            enabled=bool(trace.get("enabled", True)),
            format=str(trace.get("format", "jsonl")),
            path=str(
                trace.get(
                    "path",
                    "~/.akashic/workspace/doc_rag/retrieval_traces.jsonl",
                )
            ),
            include_content=bool(trace.get("include_content", False)),
            max_content_chars=int(trace.get("max_content_chars", 2000)),
        ),
        citation=DocRagCitationConfig(
            required_for_doc_answer=bool(
                citation.get("required_for_doc_answer", True)
            ),
            format=str(citation.get("format", "[source_path > heading_path]")),
            include_chunk_id_for_debug=bool(
                citation.get("include_chunk_id_for_debug", False)
            ),
            on_no_hits=str(citation.get("on_no_hits", "state_no_evidence")),
        ),
        eval=DocRagEvalConfig(
            eval_set_path=str(
                eval_cfg.get(
                    "eval_set_path", "my_md/rag/eval_sets/doc_rag_eval_v0.jsonl"
                )
            ),
            report_dir=str(eval_cfg.get("report_dir", "my_md/rag/eval_reports")),
        ),
    )
```

Call `_load_doc_rag_config(data)` inside `load_config` and pass `doc_rag=doc_rag` into `Config`.

- [ ] **Step 5: Document config example**

Add to `config.example.toml` after `[memory.embedding]`:

```toml
# =============================================================================
# Document RAG（可选，默认关闭）
# =============================================================================

[doc_rag]
enabled = false
source_root = "."
store_path = "~/.akashic/workspace/doc_rag/doc_rag.db"
collection_id = "default"

[doc_rag.sources]
include_globs = ["my_md/doc_rag_corpus/**/*.md"]
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

- [ ] **Step 6: Run config tests**

Run:

```bash
pytest tests/test_doc_rag_config.py -v
```

Expected: 4 passed.

---

### Task 2: P0 Shared Models

**Files:**
- Create: `doc_rag/__init__.py`
- Create: `doc_rag/models.py`
- Test: `tests/test_doc_rag_models.py`

**Interfaces:**
- Produces constants: `SCHEMA_VERSION = 1`, `INDEX_FORMAT_VERSION = "doc_rag_v0"`
- Produces helpers: `stable_sha1`, `stable_sha256`, `normalize_text_for_hash`
- Produces dataclasses used by loader, chunker, store

- [ ] **Step 1: Write failing model tests**

Create `tests/test_doc_rag_models.py`:

```python
from __future__ import annotations

from doc_rag.models import (
    INDEX_FORMAT_VERSION,
    SCHEMA_VERSION,
    ChunkRecord,
    LoadedDocument,
    build_chunk_id,
    build_chunk_key,
    normalize_text_for_hash,
    stable_sha256,
)


def test_hash_normalization_is_stable() -> None:
    assert normalize_text_for_hash("\ufeffa\r\nb\r") == "a\nb\n"
    assert stable_sha256("abc") == stable_sha256("abc")
    assert stable_sha256("abc") != stable_sha256("abd")


def test_chunk_ids_include_content_version() -> None:
    key1 = build_chunk_key("docs/a.md", "A > B", 0)
    key2 = build_chunk_key("docs/a.md", "A > B", 0)
    assert key1 == key2

    id1 = build_chunk_id("docs/a.md", "A > B", 0, "hash1")
    id2 = build_chunk_id("docs/a.md", "A > B", 0, "hash2")
    assert id1 != id2


def test_core_records_construct() -> None:
    doc = LoadedDocument(
        doc_id="doc1",
        source_path="my_md/doc_rag_corpus/a.md",
        title="A",
        content="hello",
        content_hash="hash",
        file_mtime=1.0,
        file_size=5,
        metadata={},
    )
    chunk = ChunkRecord(
        chunk_id="c1",
        chunk_key="k1",
        doc_id=doc.doc_id,
        source_path=doc.source_path,
        title=doc.title,
        heading_path="A",
        chunk_index=0,
        content="hello",
        chunk_content_hash="chash",
        document_content_hash=doc.content_hash,
        token_count=1,
        char_count=5,
        embedding=None,
        embedding_status="pending",
        embedding_error="",
        metadata={},
    )

    assert SCHEMA_VERSION == 1
    assert INDEX_FORMAT_VERSION == "doc_rag_v0"
    assert chunk.source_path == doc.source_path
```

- [ ] **Step 2: Run failing model tests**

Run:

```bash
pytest tests/test_doc_rag_models.py -v
```

Expected: fails because `doc_rag.models` does not exist.

- [ ] **Step 3: Implement models**

Create `doc_rag/models.py` with dataclasses:

```python
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1
INDEX_FORMAT_VERSION = "doc_rag_v0"


def normalize_text_for_hash(text: str) -> str:
    return text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")


def stable_sha256(text: str) -> str:
    return hashlib.sha256(normalize_text_for_hash(text).encode("utf-8")).hexdigest()


def stable_sha1(text: str, length: int = 16) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:length]


def build_doc_id(source_path: str) -> str:
    return stable_sha1(source_path)


def build_chunk_key(source_path: str, heading_path: str, chunk_index: int) -> str:
    return stable_sha1(f"{source_path}\n{heading_path}\n{chunk_index}")


def build_chunk_id(
    source_path: str,
    heading_path: str,
    chunk_index: int,
    chunk_content_hash: str,
) -> str:
    return stable_sha1(
        f"{source_path}\n{heading_path}\n{chunk_index}\n{chunk_content_hash}"
    )


@dataclass
class LoadedDocument:
    doc_id: str
    source_path: str
    title: str
    content: str
    content_hash: str
    file_mtime: float
    file_size: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LoaderError:
    raw_path: str
    source_path: str
    error_type: str
    message: str


@dataclass
class LoaderResult:
    documents: list[LoadedDocument] = field(default_factory=list)
    errors: list[LoaderError] = field(default_factory=list)


@dataclass
class DocumentRecord:
    doc_id: str
    source_path: str
    title: str
    content_hash: str
    file_mtime: float
    file_size: int
    status: str = "active"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkRecord:
    chunk_id: str
    chunk_key: str
    doc_id: str
    source_path: str
    title: str
    heading_path: str
    chunk_index: int
    content: str
    chunk_content_hash: str
    document_content_hash: str
    token_count: int
    char_count: int
    embedding: list[float] | None = None
    embedding_status: str = "pending"
    embedding_error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IndexRun:
    run_id: str
    status: str
    config_hash: str
    started_at: str
    finished_at: str = ""
    error: str = ""


@dataclass
class IndexRunDoc:
    run_id: str
    source_path: str
    action: str
    status: str
    old_content_hash: str = ""
    new_content_hash: str = ""
    chunk_count: int = 0
    error_type: str = ""
    error: str = ""


@dataclass
class RetrievalHit:
    rank: int
    chunk_id: str
    chunk_key: str
    source_path: str
    heading_path: str
    score: float
    score_type: str
    snippet: str
    chunk_content_hash: str
    document_content_hash: str


@dataclass
class SearchResult:
    query: str
    top_k: int
    hits: list[RetrievalHit]
    trace_id: str = ""
    error: str = ""
    latency_ms: float = 0.0
```

Create `doc_rag/__init__.py`:

```python
from doc_rag.models import INDEX_FORMAT_VERSION, SCHEMA_VERSION

__all__ = ["INDEX_FORMAT_VERSION", "SCHEMA_VERSION"]
```

- [ ] **Step 4: Run model tests**

Run:

```bash
pytest tests/test_doc_rag_models.py -v
```

Expected: 7 passed.

---

### Task 3: P1 Store and Schema

**Files:**
- Create: `doc_rag/schema.sql`
- Create: `doc_rag/store.py`
- Test: `tests/test_doc_rag_store.py`

**Interfaces:**
- Consumes: `DocumentRecord`, `ChunkRecord`, schema constants
- Produces: `DocRagStore.init_schema`, `get_meta`, `write_meta`, `start_index_run`, `finish_index_run`, `record_index_run_doc`, `get_document`, `upsert_document`, `replace_document_chunks`, `get_chunk`

Store implementation constraints:

- Enable `PRAGMA foreign_keys=ON` immediately after opening SQLite.
- Use `BEGIN IMMEDIATE` in `replace_document_chunks`.
- `replace_document_chunks` must not call a public method that commits inside the transaction.
- Add a private `_upsert_document_no_commit(document)` helper and commit only once at the end.
- Validate embedding count and dimensions before deleting old chunks.
- If any ready chunk has no valid vector, fail before replacing old data.
- Use the same sqlite-vec blob style as `memory2.store`, not JSON text, for `vec_chunks`.

- [ ] **Step 1: Write failing store tests**

Create `tests/test_doc_rag_store.py`:

```python
from __future__ import annotations

from doc_rag.models import ChunkRecord, DocumentRecord
from doc_rag.store import DocRagStore


def _doc() -> DocumentRecord:
    return DocumentRecord(
        doc_id="doc1",
        source_path="my_md/doc_rag_corpus/a.md",
        title="A",
        content_hash="doc-hash",
        file_mtime=1.0,
        file_size=10,
        metadata={"kind": "test"},
    )


def _chunk(chunk_id: str = "chunk1") -> ChunkRecord:
    return ChunkRecord(
        chunk_id=chunk_id,
        chunk_key="key1",
        doc_id="doc1",
        source_path="my_md/doc_rag_corpus/a.md",
        title="A",
        heading_path="A > Intro",
        chunk_index=0,
        content="hello world",
        chunk_content_hash="chunk-hash",
        document_content_hash="doc-hash",
        token_count=2,
        char_count=11,
        embedding=[1.0, 0.0],
        embedding_status="ready",
        metadata={"block_types": ["paragraph"]},
    )


def test_store_initializes_schema_and_meta(tmp_path):
    store = DocRagStore(tmp_path / "doc_rag.db", vec_dim=2)
    try:
        store.write_meta({"schema_version": 1, "index_format_version": "doc_rag_v0"})
        meta = store.get_meta()
        assert meta["schema_version"] == 1
        assert meta["index_format_version"] == "doc_rag_v0"
    finally:
        store.close()


def test_store_upserts_document_and_replaces_chunks(tmp_path):
    store = DocRagStore(tmp_path / "doc_rag.db", vec_dim=2)
    try:
        doc = _doc()
        store.upsert_document(doc)
        assert store.get_document(doc.source_path).doc_id == "doc1"

        store.replace_document_chunks(doc, [_chunk()], [[1.0, 0.0]])
        found = store.get_chunk("chunk1")
        assert found is not None
        assert found.heading_path == "A > Intro"
        assert found.embedding_status == "ready"

        store.replace_document_chunks(doc, [_chunk("chunk2")], [[0.0, 1.0]])
        assert store.get_chunk("chunk1") is None
        assert store.get_chunk("chunk2") is not None
    finally:
        store.close()


def test_store_records_index_run_and_doc_errors(tmp_path):
    store = DocRagStore(tmp_path / "doc_rag.db", vec_dim=2)
    try:
        run = store.start_index_run(config_hash="hash1", config={"enabled": True})
        store.record_index_run_doc(
            run_id=run.run_id,
            source_path="my_md/doc_rag_corpus/a.md",
            action="indexed",
            status="succeeded",
            old_content_hash="",
            new_content_hash="new",
            chunk_count=2,
        )
        store.record_index_run_doc(
            run_id=run.run_id,
            source_path="my_md/doc_rag_corpus/b.md",
            action="indexed",
            status="failed",
            error_type="decode_error",
            error="not utf-8",
        )
        store.finish_index_run(
            run.run_id,
            status="partial_failed",
            docs_scanned=2,
            docs_indexed=1,
            docs_skipped=0,
            docs_deleted=0,
            docs_failed=1,
        )

        saved = store.get_index_run(run.run_id)
        assert saved["status"] == "partial_failed"
        assert saved["docs_scanned"] == 2
        assert saved["docs_failed"] == 1
        docs = store.list_index_run_docs(run.run_id)
        assert [doc["status"] for doc in docs] == ["succeeded", "failed"]
    finally:
        store.close()


def test_replace_document_chunks_rolls_back_on_embedding_dim_error(tmp_path):
    store = DocRagStore(tmp_path / "doc_rag.db", vec_dim=2)
    try:
        doc = _doc()
        store.replace_document_chunks(doc, [_chunk("old")], [[1.0, 0.0]])
        changed = DocumentRecord(
            doc_id="doc1",
            source_path="my_md/doc_rag_corpus/a.md",
            title="A changed",
            content_hash="changed-hash",
            file_mtime=2.0,
            file_size=20,
        )

        try:
            store.replace_document_chunks(changed, [_chunk("new")], [[1.0, 0.0, 0.0]])
        except ValueError as exc:
            assert "embedding dim" in str(exc)
        else:
            raise AssertionError("expected embedding dimension validation failure")

        assert store.get_chunk("old") is not None
        assert store.get_chunk("new") is None
        assert store.get_document(doc.source_path).content_hash == "doc-hash"
    finally:
        store.close()
```

- [ ] **Step 2: Run failing store tests**

Run:

```bash
pytest tests/test_doc_rag_store.py -v
```

Expected: fails because `doc_rag.store` does not exist.

- [ ] **Step 3: Create schema**

Create `doc_rag/schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    file_mtime REAL NOT NULL,
    file_size INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    chunk_key TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    source_path TEXT NOT NULL,
    title TEXT NOT NULL,
    heading_path TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    chunk_content_hash TEXT NOT NULL,
    document_content_hash TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    char_count INTEGER NOT NULL,
    embedding TEXT,
    embedding_status TEXT NOT NULL DEFAULT 'pending',
    embedding_error TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_chunks_doc_id ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS ix_chunks_source_path ON chunks(source_path);
CREATE INDEX IF NOT EXISTS ix_chunks_embedding_status ON chunks(embedding_status);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED,
    source_path UNINDEXED,
    heading_path,
    content
);

CREATE TABLE IF NOT EXISTS index_runs (
    run_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    config_json TEXT NOT NULL DEFAULT '{}',
    docs_scanned INTEGER NOT NULL DEFAULT 0,
    docs_indexed INTEGER NOT NULL DEFAULT 0,
    docs_skipped INTEGER NOT NULL DEFAULT 0,
    docs_deleted INTEGER NOT NULL DEFAULT 0,
    docs_failed INTEGER NOT NULL DEFAULT 0,
    chunks_created INTEGER NOT NULL DEFAULT 0,
    chunks_deleted INTEGER NOT NULL DEFAULT 0,
    embedding_failed INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS index_run_docs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    source_path TEXT NOT NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    old_content_hash TEXT NOT NULL DEFAULT '',
    new_content_hash TEXT NOT NULL DEFAULT '',
    chunk_count INTEGER NOT NULL DEFAULT 0,
    error_type TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

- [ ] **Step 4: Implement store**

Create `doc_rag/store.py` with:

```python
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from array import array
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from doc_rag.models import ChunkRecord, DocumentRecord

try:
    import sqlite_vec

    _SQLITE_VEC_AVAILABLE = True
except Exception:
    sqlite_vec = None
    _SQLITE_VEC_AVAILABLE = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emb_to_blob(vec: list[float]) -> bytes:
    return array("f", vec).tobytes()


class DocRagStore:
    def __init__(self, db_path: str | Path, vec_dim: int = 1024) -> None:
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys=ON")
        self._lock = threading.RLock()
        self._closed = False
        self._vec_dim = vec_dim
        self._vec_enabled = False
        self._vec_init_error = ""
        self.init_schema()
        self._init_vec()

    @property
    def vec_enabled(self) -> bool:
        return self._vec_enabled

    @property
    def vec_init_error(self) -> str:
        return self._vec_init_error

    def init_schema(self) -> None:
        schema_path = Path(__file__).with_name("schema.sql")
        self._db.executescript(schema_path.read_text(encoding="utf-8"))
        self._db.commit()

    def _init_vec(self) -> None:
        if not _SQLITE_VEC_AVAILABLE:
            self._vec_init_error = "sqlite_vec 未安装"
            return
        try:
            self._db.enable_load_extension(True)
            sqlite_vec.load(self._db)
            self._db.enable_load_extension(False)
            self._db.executescript(
                f"""
CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(
    embedding float[{self._vec_dim}]
);
"""
            )
            self._db.commit()
            self._vec_enabled = True
        except Exception as exc:
            self._vec_init_error = str(exc)

    def close(self) -> None:
        if self._closed:
            return
        self._db.close()
        self._closed = True

    def get_meta(self) -> dict[str, Any]:
        rows = self._db.execute("SELECT key, value FROM meta").fetchall()
        result: dict[str, Any] = {}
        for row in rows:
            try:
                result[str(row["key"])] = json.loads(str(row["value"]))
            except json.JSONDecodeError:
                result[str(row["key"])] = row["value"]
        return result

    def write_meta(self, meta: dict[str, Any]) -> None:
        with self._lock:
            self._db.executemany(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                [(key, json.dumps(value, ensure_ascii=False)) for key, value in meta.items()],
            )
            self._db.commit()

    def start_index_run(self, config_hash: str, config: dict[str, Any]) -> Any:
        run_id = uuid.uuid4().hex
        with self._lock:
            self._db.execute(
                """
                INSERT INTO index_runs(run_id, status, config_hash, config_json, started_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    "running",
                    config_hash,
                    json.dumps(config, ensure_ascii=False),
                    _now_iso(),
                ),
            )
            self._db.commit()
        from types import SimpleNamespace

        return SimpleNamespace(run_id=run_id, status="running", config_hash=config_hash)

    def finish_index_run(
        self,
        run_id: str,
        status: str,
        *,
        docs_scanned: int = 0,
        docs_indexed: int = 0,
        docs_skipped: int = 0,
        docs_deleted: int = 0,
        docs_failed: int = 0,
        chunks_created: int = 0,
        chunks_deleted: int = 0,
        embedding_failed: int = 0,
        error: str = "",
    ) -> None:
        with self._lock:
            self._db.execute(
                """
                UPDATE index_runs
                SET status=?, docs_scanned=?, docs_indexed=?, docs_skipped=?,
                    docs_deleted=?, docs_failed=?, chunks_created=?, chunks_deleted=?,
                    embedding_failed=?, finished_at=?, error=?
                WHERE run_id=?
                """,
                (
                    status,
                    docs_scanned,
                    docs_indexed,
                    docs_skipped,
                    docs_deleted,
                    docs_failed,
                    chunks_created,
                    chunks_deleted,
                    embedding_failed,
                    _now_iso(),
                    error,
                    run_id,
                ),
            )
            self._db.commit()

    def record_index_run_doc(
        self,
        *,
        run_id: str,
        source_path: str,
        action: str,
        status: str,
        old_content_hash: str = "",
        new_content_hash: str = "",
        chunk_count: int = 0,
        error_type: str = "",
        error: str = "",
    ) -> None:
        with self._lock:
            self._db.execute(
                """
                INSERT INTO index_run_docs(
                    run_id, source_path, action, status, old_content_hash,
                    new_content_hash, chunk_count, error_type, error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    source_path,
                    action,
                    status,
                    old_content_hash,
                    new_content_hash,
                    chunk_count,
                    error_type,
                    error,
                ),
            )
            self._db.commit()

    def get_index_run(self, run_id: str) -> dict[str, Any]:
        row = self._db.execute(
            "SELECT * FROM index_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        return dict(row) if row else {}

    def list_index_run_docs(self, run_id: str) -> list[dict[str, Any]]:
        rows = self._db.execute(
            "SELECT * FROM index_run_docs WHERE run_id=? ORDER BY id", (run_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    def get_document(self, source_path: str) -> DocumentRecord | None:
        row = self._db.execute(
            "SELECT * FROM documents WHERE source_path=?", (source_path,)
        ).fetchone()
        if row is None:
            return None
        return DocumentRecord(
            doc_id=row["doc_id"],
            source_path=row["source_path"],
            title=row["title"],
            content_hash=row["content_hash"],
            file_mtime=float(row["file_mtime"]),
            file_size=int(row["file_size"]),
            status=row["status"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )

    def upsert_document(self, document: DocumentRecord) -> None:
        with self._lock:
            self._upsert_document_no_commit(document)
            self._db.commit()

    def _upsert_document_no_commit(self, document: DocumentRecord) -> None:
        self._db.execute(
            """
            INSERT INTO documents(
                doc_id, source_path, title, content_hash, file_mtime,
                file_size, status, metadata_json, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(doc_id) DO UPDATE SET
                source_path=excluded.source_path,
                title=excluded.title,
                content_hash=excluded.content_hash,
                file_mtime=excluded.file_mtime,
                file_size=excluded.file_size,
                status=excluded.status,
                metadata_json=excluded.metadata_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                document.doc_id,
                document.source_path,
                document.title,
                document.content_hash,
                document.file_mtime,
                document.file_size,
                document.status,
                json.dumps(document.metadata, ensure_ascii=False),
            ),
        )

    def _validate_embeddings(
        self,
        chunks: list[ChunkRecord],
        embeddings: list[list[float]] | None,
    ) -> list[list[float] | None]:
        if embeddings is not None and len(embeddings) != len(chunks):
            raise ValueError("embedding count does not match chunk count")
        resolved: list[list[float] | None] = []
        for index, chunk in enumerate(chunks):
            emb = embeddings[index] if embeddings is not None else chunk.embedding
            if chunk.embedding_status == "ready":
                if emb is None:
                    raise ValueError(f"ready chunk {chunk.chunk_id} has no embedding")
                if len(emb) != self._vec_dim:
                    raise ValueError(
                        f"embedding dim {len(emb)} does not match vec_dim {self._vec_dim}"
                    )
            resolved.append(emb)
        return resolved

    def replace_document_chunks(
        self,
        document: DocumentRecord,
        chunks: list[ChunkRecord],
        embeddings: list[list[float]] | None = None,
    ) -> None:
        resolved_embeddings = self._validate_embeddings(chunks, embeddings)
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                self._upsert_document_no_commit(document)
                old_rows = self._db.execute(
                    "SELECT rowid FROM chunks WHERE doc_id=?", (document.doc_id,)
                ).fetchall()
                old_rowids = [int(row["rowid"]) for row in old_rows]
                if self._vec_enabled:
                    self._db.executemany(
                        "DELETE FROM vec_chunks WHERE rowid=?",
                        [(rowid,) for rowid in old_rowids],
                    )
                self._db.execute("DELETE FROM chunks_fts WHERE source_path=?", (document.source_path,))
                self._db.execute("DELETE FROM chunks WHERE doc_id=?", (document.doc_id,))
                for index, chunk in enumerate(chunks):
                    emb = resolved_embeddings[index]
                    emb_json = json.dumps(emb, ensure_ascii=False) if emb is not None else None
                    cur = self._db.execute(
                        """
                        INSERT INTO chunks(
                            chunk_id, chunk_key, doc_id, source_path, title,
                            heading_path, chunk_index, content, chunk_content_hash,
                            document_content_hash, token_count, char_count, embedding,
                            embedding_status, embedding_error, metadata_json
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            chunk.chunk_id,
                            chunk.chunk_key,
                            chunk.doc_id,
                            chunk.source_path,
                            chunk.title,
                            chunk.heading_path,
                            chunk.chunk_index,
                            chunk.content,
                            chunk.chunk_content_hash,
                            chunk.document_content_hash,
                            chunk.token_count,
                            chunk.char_count,
                            emb_json,
                            chunk.embedding_status,
                            chunk.embedding_error,
                            json.dumps(chunk.metadata, ensure_ascii=False),
                        ),
                    )
                    rowid = int(cur.lastrowid)
                    self._db.execute(
                        "INSERT INTO chunks_fts(chunk_id, source_path, heading_path, content) VALUES (?, ?, ?, ?)",
                        (chunk.chunk_id, chunk.source_path, chunk.heading_path, chunk.content),
                    )
                    if self._vec_enabled and emb is not None:
                        self._db.execute(
                            "INSERT INTO vec_chunks(rowid, embedding) VALUES (?, ?)",
                            (rowid, _emb_to_blob(emb)),
                        )
                self._db.commit()
            except Exception:
                self._db.rollback()
                raise

    def get_chunk(self, chunk_id: str) -> ChunkRecord | None:
        row = self._db.execute(
            "SELECT * FROM chunks WHERE chunk_id=?", (chunk_id,)
        ).fetchone()
        if row is None:
            return None
        embedding = json.loads(row["embedding"]) if row["embedding"] else None
        return ChunkRecord(
            chunk_id=row["chunk_id"],
            chunk_key=row["chunk_key"],
            doc_id=row["doc_id"],
            source_path=row["source_path"],
            title=row["title"],
            heading_path=row["heading_path"],
            chunk_index=int(row["chunk_index"]),
            content=row["content"],
            chunk_content_hash=row["chunk_content_hash"],
            document_content_hash=row["document_content_hash"],
            token_count=int(row["token_count"]),
            char_count=int(row["char_count"]),
            embedding=embedding,
            embedding_status=row["embedding_status"],
            embedding_error=row["embedding_error"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )
```

- [ ] **Step 5: Verify transaction and vector validation are mandatory**

Check the implementation before running tests:

```text
upsert_document() calls _upsert_document_no_commit() and then commits
replace_document_chunks() calls _validate_embeddings() before BEGIN IMMEDIATE
replace_document_chunks() calls _upsert_document_no_commit() inside the transaction
replace_document_chunks() commits exactly once at the end
replace_document_chunks() rolls back on any exception
vec_chunks uses _emb_to_blob(), not json.dumps()
```

- [ ] **Step 6: Run store tests**

Run:

```bash
pytest tests/test_doc_rag_store.py -v
```

Expected: 4 passed.

---

### Task 4: P2 Markdown Loader

**Files:**
- Create: `doc_rag/loader.py`
- Test: `tests/test_doc_rag_loader.py`

**Interfaces:**
- Consumes: `DocRagConfig`
- Produces: `MarkdownLoader.load_all() -> LoaderResult`

- [ ] **Step 1: Write failing loader tests**

Create `tests/test_doc_rag_loader.py`:

```python
from __future__ import annotations

from pathlib import Path

from agent.config_models import DocRagConfig
from doc_rag.loader import MarkdownLoader


def test_loader_scans_only_configured_corpus(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    corpus = repo / "my_md" / "doc_rag_corpus"
    corpus.mkdir(parents=True)
    (corpus / "a.md").write_text("# Title A\n\nBody", encoding="utf-8")
    other = repo / "my_md" / "rag"
    other.mkdir(parents=True)
    (other / "ignore.md").write_text("# Ignore", encoding="utf-8")

    cfg = DocRagConfig(source_root=str(repo))
    result = MarkdownLoader(cfg).load_all()

    assert [doc.source_path for doc in result.documents] == [
        "my_md/doc_rag_corpus/a.md"
    ]
    assert result.documents[0].title == "Title A"
    assert result.errors == []


def test_loader_reports_empty_and_decode_errors(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    corpus = repo / "my_md" / "doc_rag_corpus"
    corpus.mkdir(parents=True)
    (corpus / "empty.md").write_text("   \n", encoding="utf-8")
    (corpus / "bad.md").write_bytes(b"\xff\xfe\x00")

    cfg = DocRagConfig(source_root=str(repo))
    result = MarkdownLoader(cfg).load_all()

    assert result.documents == []
    assert {err.error_type for err in result.errors} == {"skip_empty", "decode_error"}


def test_loader_uses_repo_relative_posix_source_path(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    nested = repo / "my_md" / "doc_rag_corpus" / "nested"
    nested.mkdir(parents=True)
    (nested / "b.md").write_text("## Subtitle\ncontent", encoding="utf-8")

    cfg = DocRagConfig(source_root=str(repo))
    result = MarkdownLoader(cfg).load_all()

    assert result.documents[0].source_path == "my_md/doc_rag_corpus/nested/b.md"
    assert "\\" not in result.documents[0].source_path


def test_loader_reports_non_markdown_when_include_matches(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    corpus = repo / "my_md" / "doc_rag_corpus"
    corpus.mkdir(parents=True)
    (corpus / "note.txt").write_text("not markdown", encoding="utf-8")

    cfg = DocRagConfig(source_root=str(repo))
    cfg.sources.include_globs = ["my_md/doc_rag_corpus/**/*"]
    result = MarkdownLoader(cfg).load_all()

    assert result.documents == []
    assert [(err.source_path, err.error_type) for err in result.errors] == [
        ("my_md/doc_rag_corpus/note.txt", "not_markdown")
    ]


def test_loader_reports_too_large_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    corpus = repo / "my_md" / "doc_rag_corpus"
    corpus.mkdir(parents=True)
    (corpus / "large.md").write_text("# Large\n\nabcdef", encoding="utf-8")

    cfg = DocRagConfig(source_root=str(repo))
    cfg.sources.max_file_size_bytes = 4
    result = MarkdownLoader(cfg).load_all()

    assert result.errors[0].error_type == "skip_too_large"


def test_loader_internal_symlink_keeps_symlink_source_path(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    corpus = repo / "my_md" / "doc_rag_corpus"
    target_dir = repo / "docs"
    corpus.mkdir(parents=True)
    target_dir.mkdir()
    (target_dir / "target.md").write_text("# Target\n\nBody", encoding="utf-8")
    (corpus / "linked.md").symlink_to(target_dir / "target.md")

    cfg = DocRagConfig(source_root=str(repo))
    result = MarkdownLoader(cfg).load_all()

    assert result.documents[0].source_path == "my_md/doc_rag_corpus/linked.md"


def test_loader_external_symlink_is_error(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    corpus = repo / "my_md" / "doc_rag_corpus"
    outside = tmp_path / "outside.md"
    corpus.mkdir(parents=True)
    outside.write_text("# Outside", encoding="utf-8")
    (corpus / "outside.md").symlink_to(outside)

    cfg = DocRagConfig(source_root=str(repo))
    result = MarkdownLoader(cfg).load_all()

    assert result.documents == []
    assert result.errors[0].source_path == "my_md/doc_rag_corpus/outside.md"
    assert result.errors[0].error_type == "external_symlink"
```

- [ ] **Step 2: Run failing loader tests**

Run:

```bash
pytest tests/test_doc_rag_loader.py -v
```

Expected: fails because `doc_rag.loader` does not exist.

- [ ] **Step 3: Implement loader**

Create `doc_rag/loader.py`:

```python
from __future__ import annotations

from pathlib import Path

from agent.config_models import DocRagConfig
from doc_rag.models import (
    LoadedDocument,
    LoaderError,
    LoaderResult,
    build_doc_id,
    stable_sha256,
)


class MarkdownLoader:
    def __init__(self, config: DocRagConfig) -> None:
        self.config = config
        self.source_root = Path(config.source_root).expanduser().resolve()

    def load_all(self) -> LoaderResult:
        result = LoaderResult()
        for path in self.scan():
            item = self.load_path(path)
            if isinstance(item, LoadedDocument):
                result.documents.append(item)
            else:
                result.errors.append(item)
        result.documents.sort(key=lambda doc: doc.source_path)
        result.errors.sort(key=lambda err: err.source_path or err.raw_path)
        return result

    def scan(self) -> list[Path]:
        candidates: set[Path] = set()
        for pattern in self.config.sources.include_globs:
            candidates.update(self.source_root.glob(pattern))
        paths = []
        for path in candidates:
            if not path.is_file():
                continue
            source_path = self._source_path(path)
            if self._is_excluded(source_path):
                continue
            paths.append(path)
        return sorted(paths, key=lambda p: self._source_path(p))

    def load_path(self, path: Path) -> LoadedDocument | LoaderError:
        raw_path = str(path)
        try:
            source_path = self._source_path(path)
            resolved = path.resolve()
            if path.is_symlink() and not self.config.sources.allow_external_symlink:
                if not self._is_within_root(resolved):
                    return LoaderError(raw_path, source_path, "external_symlink", "symlink 指向 repo 外")
            if not self._is_within_root(path.parent.resolve()):
                return LoaderError(raw_path, source_path, "outside_source_root", "文件不在 source_root 内")
            if path.suffix.lower() not in self.config.sources.allowed_extensions:
                return LoaderError(raw_path, source_path, "not_markdown", "不是 Markdown 文件")
            size = path.stat().st_size
            if size > self.config.sources.max_file_size_bytes:
                return LoaderError(raw_path, source_path, "skip_too_large", "文件超过大小限制")
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                try:
                    content = path.read_text(encoding="utf-8-sig")
                except UnicodeDecodeError:
                    return LoaderError(raw_path, source_path, "decode_error", "文件不是 UTF-8")
            if not content.strip():
                return LoaderError(raw_path, source_path, "skip_empty", "空 Markdown 文件")
            return LoadedDocument(
                doc_id=build_doc_id(source_path),
                source_path=source_path,
                title=self._extract_title(content, path),
                content=content,
                content_hash=stable_sha256(content),
                file_mtime=path.stat().st_mtime,
                file_size=size,
                metadata={},
            )
        except OSError as exc:
            return LoaderError(raw_path, "", "read_error", str(exc))

    def _source_path(self, path: Path) -> str:
        return path.relative_to(self.source_root).as_posix()

    def _is_within_root(self, path: Path) -> bool:
        try:
            path.relative_to(self.source_root)
            return True
        except ValueError:
            return False

    def _is_excluded(self, source_path: str) -> bool:
        from fnmatch import fnmatch

        return any(fnmatch(source_path, pattern) for pattern in self.config.sources.exclude_globs)

    def _extract_title(self, content: str, path: Path) -> str:
        first_heading = ""
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                title = stripped.lstrip("#").strip()
                if stripped.startswith("# ") and title:
                    return title
                if title and not first_heading:
                    first_heading = title
        return first_heading or path.stem
```

- [ ] **Step 4: Run loader tests**

Run:

```bash
pytest tests/test_doc_rag_loader.py -v
```

Expected: 7 passed.

---

### Task 5: P3 Markdown Chunker

**Files:**
- Create: `doc_rag/chunker.py`
- Test: `tests/test_doc_rag_chunker.py`

**Interfaces:**
- Consumes: `LoadedDocument`, `DocRagChunkingConfig`
- Produces: `MarkdownChunker.chunk(document: LoadedDocument) -> list[ChunkRecord]`

- [ ] **Step 1: Write failing chunker tests**

Create `tests/test_doc_rag_chunker.py`:

```python
from __future__ import annotations

from agent.config_models import DocRagChunkingConfig
from doc_rag.chunker import MarkdownChunker
from doc_rag.models import LoadedDocument, stable_sha256


def _doc(content: str) -> LoadedDocument:
    return LoadedDocument(
        doc_id="doc1",
        source_path="my_md/doc_rag_corpus/a.md",
        title="A",
        content=content,
        content_hash=stable_sha256(content),
        file_mtime=1.0,
        file_size=len(content.encode("utf-8")),
        metadata={},
    )


def test_chunker_preserves_heading_path() -> None:
    content = "# A\n\nIntro\n\n## B\n\nBody\n\n### C\n\nDeep body"
    chunks = MarkdownChunker(DocRagChunkingConfig(max_chunk_chars=80)).chunk(_doc(content))

    assert [chunk.heading_path for chunk in chunks] == ["A", "A > B", "A > B > C"]
    assert all(chunk.source_path == "my_md/doc_rag_corpus/a.md" for chunk in chunks)
    assert all(chunk.chunk_id for chunk in chunks)
    assert all(chunk.chunk_key for chunk in chunks)


def test_chunker_keeps_code_block_together() -> None:
    content = "# A\n\nBefore\n\n```python\nprint('a')\nprint('b')\n```\n\nAfter"
    chunks = MarkdownChunker(DocRagChunkingConfig(max_chunk_chars=500)).chunk(_doc(content))

    joined = "\n".join(chunk.content for chunk in chunks)
    assert "```python\nprint('a')\nprint('b')\n```" in joined
    assert any(chunk.metadata["has_code"] for chunk in chunks)


def test_chunk_id_changes_when_content_changes() -> None:
    chunker = MarkdownChunker(DocRagChunkingConfig(max_chunk_chars=500))
    chunk_a = chunker.chunk(_doc("# A\n\nhello"))[0]
    chunk_b = chunker.chunk(_doc("# A\n\nhello changed"))[0]

    assert chunk_a.chunk_key == chunk_b.chunk_key
    assert chunk_a.chunk_id != chunk_b.chunk_id


def test_chunker_splits_oversized_paragraph_with_overlap() -> None:
    text = " ".join(f"word{i:02d}" for i in range(80))
    cfg = DocRagChunkingConfig(
        target_chunk_chars=90,
        max_chunk_chars=120,
        min_chunk_chars=20,
        chunk_overlap_chars=20,
    )
    chunks = MarkdownChunker(cfg).chunk(_doc(f"# A\n\n{text}"))

    assert len(chunks) > 1
    assert all(chunk.char_count <= cfg.max_chunk_chars for chunk in chunks)
    assert all(chunk.metadata["split_reason"] in {"heading_block", "fallback_split"} for chunk in chunks)
    assert any(chunk.metadata["split_reason"] == "fallback_split" for chunk in chunks)


def test_chunker_splits_large_table_and_repeats_header() -> None:
    rows = "\n".join(f"| k{i} | v{i} |" for i in range(20))
    table = "| key | value |\n| --- | --- |\n" + rows
    cfg = DocRagChunkingConfig(
        target_chunk_chars=80,
        max_chunk_chars=120,
        min_chunk_chars=20,
        chunk_overlap_chars=0,
    )
    chunks = MarkdownChunker(cfg).chunk(_doc(f"# A\n\n{table}"))

    table_chunks = [chunk for chunk in chunks if chunk.metadata["has_table"]]
    assert len(table_chunks) > 1
    assert all("| key | value |" in chunk.content for chunk in table_chunks)
    assert all(chunk.char_count <= cfg.max_chunk_chars for chunk in table_chunks)
```

- [ ] **Step 2: Run failing chunker tests**

Run:

```bash
pytest tests/test_doc_rag_chunker.py -v
```

Expected: fails because `doc_rag.chunker` does not exist.

- [ ] **Step 3: Implement heading-aware block chunker**

Create `doc_rag/chunker.py`:

Implementation requirements:

- Parse Markdown into block records with `heading_path`, `block_type`, `start_line`, and `end_line`.
- Merge adjacent blocks under the same `heading_path` until adding another block would exceed `max_chunk_chars`.
- If a single paragraph/list/code/table block exceeds `max_chunk_chars`, apply fallback split.
- Fallback paragraph split should prefer whitespace boundaries and add `chunk_overlap_chars` overlap where possible.
- Fallback table split must copy the table header and separator into every table sub-chunk.
- Every emitted chunk must satisfy `char_count <= max_chunk_chars` unless a single unbreakable line itself exceeds `max_chunk_chars`; in that case set `metadata["split_reason"] = "unbreakable_too_large"`.
- Metadata must include `block_types`, `has_code`, `has_table`, `has_list`, `split_reason`, `start_line`, and `end_line`.

```python
from __future__ import annotations

from dataclasses import dataclass

from agent.config_models import DocRagChunkingConfig
from doc_rag.models import (
    ChunkRecord,
    LoadedDocument,
    build_chunk_id,
    build_chunk_key,
    stable_sha256,
)


@dataclass
class _Block:
    heading_path: str
    text: str
    block_type: str


class MarkdownChunker:
    def __init__(self, config: DocRagChunkingConfig) -> None:
        self.config = config

    def chunk(self, document: LoadedDocument) -> list[ChunkRecord]:
        blocks = self._parse_blocks(document)
        chunks: list[ChunkRecord] = []
        current: list[_Block] = []
        current_heading = ""

        def flush() -> None:
            nonlocal current, current_heading
            if not current:
                return
            text = "\n\n".join(block.text for block in current).strip()
            if text:
                chunks.append(self._make_chunk(document, current_heading, text, len(chunks), current))
            current = []
            current_heading = ""

        for block in blocks:
            if current and block.heading_path != current_heading:
                flush()
            candidate_text = "\n\n".join([b.text for b in current] + [block.text]).strip()
            if current and len(candidate_text) > self.config.max_chunk_chars:
                flush()
            current.append(block)
            current_heading = block.heading_path
        flush()
        return chunks

    def _parse_blocks(self, document: LoadedDocument) -> list[_Block]:
        lines = document.content.splitlines()
        headings: list[tuple[int, str]] = []
        blocks: list[_Block] = []
        pending: list[str] = []
        in_code = False
        code_lines: list[str] = []

        def heading_path() -> str:
            return " > ".join(title for _, title in headings) or document.title

        def flush_pending() -> None:
            nonlocal pending
            text = "\n".join(pending).strip()
            if text:
                blocks.append(_Block(heading_path(), text, self._classify_block(text)))
            pending = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```"):
                if in_code:
                    code_lines.append(line)
                    blocks.append(_Block(heading_path(), "\n".join(code_lines), "code_block"))
                    code_lines = []
                    in_code = False
                else:
                    flush_pending()
                    in_code = True
                    code_lines = [line]
                continue
            if in_code:
                code_lines.append(line)
                continue
            if stripped.startswith("#"):
                title = stripped.lstrip("#").strip()
                if title:
                    flush_pending()
                    level = len(stripped) - len(stripped.lstrip("#"))
                    headings = [(lvl, val) for lvl, val in headings if lvl < level]
                    headings.append((level, title))
                    pending = [line]
                    continue
            if not stripped:
                flush_pending()
                continue
            pending.append(line)
        if in_code and code_lines:
            blocks.append(_Block(heading_path(), "\n".join(code_lines), "code_block"))
        flush_pending()
        return blocks

    def _classify_block(self, text: str) -> str:
        lines = text.splitlines()
        if text.startswith("```"):
            return "code_block"
        if lines and all(line.strip().startswith("|") for line in lines if line.strip()):
            return "table"
        if lines and all(line.lstrip().startswith(("-", "*", "+")) for line in lines if line.strip()):
            return "list"
        if text.startswith("#"):
            return "heading"
        return "paragraph"

    def _make_chunk(
        self,
        document: LoadedDocument,
        heading_path: str,
        content: str,
        chunk_index: int,
        blocks: list[_Block],
    ) -> ChunkRecord:
        chunk_hash = stable_sha256(content)
        block_types = sorted({block.block_type for block in blocks})
        metadata = {
            "block_types": block_types,
            "has_code": "code_block" in block_types,
            "has_table": "table" in block_types,
            "has_list": "list" in block_types,
            "split_reason": "heading_block",
        }
        return ChunkRecord(
            chunk_id=build_chunk_id(
                document.source_path, heading_path, chunk_index, chunk_hash
            ),
            chunk_key=build_chunk_key(document.source_path, heading_path, chunk_index),
            doc_id=document.doc_id,
            source_path=document.source_path,
            title=document.title,
            heading_path=heading_path,
            chunk_index=chunk_index,
            content=content,
            chunk_content_hash=chunk_hash,
            document_content_hash=document.content_hash,
            token_count=max(1, len(content) // 4),
            char_count=len(content),
            metadata=metadata,
        )
```

- [ ] **Step 4: Run chunker tests**

Run:

```bash
pytest tests/test_doc_rag_chunker.py -v
```

Expected: 5 passed.

---

## P0-P3 Verification

Run all P0-P3 tests:

```bash
pytest \
  tests/test_doc_rag_config.py \
  tests/test_doc_rag_models.py \
  tests/test_doc_rag_store.py \
  tests/test_doc_rag_loader.py \
  tests/test_doc_rag_chunker.py \
  -v
```

Expected: all tests pass.

Run focused existing regression checks:

```bash
pytest tests/test_memory2_retrieval_baseline.py tests/test_tool_discovery_routing.py -v
```

Expected: existing memory retrieval and tool discovery tests still pass.

## P0-P3 Acceptance Matrix

| Requirement | Test / Check |
| --- | --- |
| `doc_rag` config defaults disabled | `test_doc_rag_defaults_disabled` |
| nested `[doc_rag.*]` config loads | `test_doc_rag_loads_nested_config` |
| shared model hashes are stable | `test_hash_normalization_is_stable` |
| `chunk_id` changes on content version change | `test_chunk_ids_include_content_version` |
| store initializes schema and meta | `test_store_initializes_schema_and_meta` |
| store records index run counts and doc errors | `test_store_records_index_run_and_doc_errors` |
| document chunk replacement is atomic | `test_replace_document_chunks_rolls_back_on_embedding_dim_error` |
| ready chunks cannot be stored with invalid vectors | `test_replace_document_chunks_rolls_back_on_embedding_dim_error` |
| loader only scans configured corpus by default | `test_loader_scans_only_configured_corpus` |
| loader returns `skip_empty` and `decode_error` | `test_loader_reports_empty_and_decode_errors` |
| loader uses repo-relative POSIX `source_path` | `test_loader_uses_repo_relative_posix_source_path` |
| broad include reports non-Markdown as `not_markdown` | `test_loader_reports_non_markdown_when_include_matches` |
| loader reports oversized files | `test_loader_reports_too_large_file` |
| internal symlink keeps symlink path identity | `test_loader_internal_symlink_keeps_symlink_source_path` |
| external symlink is rejected | `test_loader_external_symlink_is_error` |
| chunker preserves heading paths | `test_chunker_preserves_heading_path` |
| chunker keeps normal code blocks together | `test_chunker_keeps_code_block_together` |
| chunker splits oversized paragraph and marks fallback | `test_chunker_splits_oversized_paragraph_with_overlap` |
| chunker splits large table and repeats header | `test_chunker_splits_large_table_and_repeats_header` |

## Commit Plan

Commit after P0-P3 verification:

```bash
git add \
  agent/config_models.py \
  agent/config.py \
  config.example.toml \
  doc_rag \
  tests/test_doc_rag_config.py \
  tests/test_doc_rag_models.py \
  tests/test_doc_rag_store.py \
  tests/test_doc_rag_loader.py \
  tests/test_doc_rag_chunker.py \
  my_md/rag/11-document-rag-implementation-plan.md \
  my_md/rag/15-document-rag-p0-p3-implementation-plan.md

git commit -m "feat(doc-rag): add p0-p3 document rag foundation"
```

## Self-Review Checklist

- P0-P3 does not call LLM or embedding APIs.
- P0-P3 does not register Agent tools.
- P0-P3 does not modify AgentLoop.
- `enabled` defaults to `false`.
- `source_path` remains repo-relative POSIX.
- loader/chunker tests do not require SQLite.
- store tests do not require real sqlite-vec.
- API keys are only loaded into config, not written to meta or test outputs.
