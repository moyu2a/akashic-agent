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


def test_vec_chunks_rowid_matches_chunks_rowid_when_vec_enabled(tmp_path):
    store = DocRagStore(tmp_path / "doc_rag.db", vec_dim=2)
    try:
        if not store.vec_enabled:
            return
        doc = _doc()
        store.replace_document_chunks(doc, [_chunk("chunk1")], [[1.0, 0.0]])

        chunk_rowid = store._db.execute(
            "SELECT rowid FROM chunks WHERE chunk_id=?", ("chunk1",)
        ).fetchone()[0]
        vec_rowid = store._db.execute("SELECT rowid FROM vec_chunks").fetchone()[0]

        assert vec_rowid == chunk_rowid
    finally:
        store.close()
