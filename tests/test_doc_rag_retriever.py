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


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


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
