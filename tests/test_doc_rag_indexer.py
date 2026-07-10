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


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


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
        await DocRagIndexer(
            cfg, store=store, embedding_client=_FakeEmbeddingClient()
        ).run()
        second_embedder = _FakeEmbeddingClient()
        summary = await DocRagIndexer(
            cfg, store=store, embedding_client=second_embedder
        ).run()

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
        await DocRagIndexer(
            cfg, store=store, embedding_client=_FakeEmbeddingClient()
        ).run()
        second_embedder = _FakeEmbeddingClient()
        summary = await DocRagIndexer(
            cfg, store=store, embedding_client=second_embedder
        ).run(IndexOptions(rebuild=True))

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
        await DocRagIndexer(
            cfg, store=store, embedding_client=_FakeEmbeddingClient()
        ).run()
        (repo / "my_md" / "doc_rag_corpus" / "a.md").unlink()
        summary = await DocRagIndexer(
            cfg, store=store, embedding_client=_FakeEmbeddingClient()
        ).run()

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
        await DocRagIndexer(
            cfg, store=store, embedding_client=_FakeEmbeddingClient()
        ).run()
        old_doc = store.get_document("my_md/doc_rag_corpus/a.md")
        old_chunks = store.list_chunks("my_md/doc_rag_corpus/a.md")
        _write_doc(repo, "a.md", "# A\n\nFAIL_ME changed")

        summary = await DocRagIndexer(
            cfg,
            store=store,
            embedding_client=_FakeEmbeddingClient(fail_on="FAIL_ME"),
        ).run()

        assert summary.status == "partial_failed"
        assert (
            store.get_document("my_md/doc_rag_corpus/a.md").content_hash
            == old_doc.content_hash
        )
        assert [
            chunk.chunk_id for chunk in store.list_chunks("my_md/doc_rag_corpus/a.md")
        ] == [chunk.chunk_id for chunk in old_chunks]
    finally:
        store.close()
