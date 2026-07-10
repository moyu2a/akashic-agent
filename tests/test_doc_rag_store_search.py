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
    finally:
        store.close()


def test_store_search_vector_treats_same_direction_non_unit_vectors_as_similar(
    tmp_path,
):
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
        store.replace_document_chunks(
            doc1,
            [_chunk("c1", "d1", doc1.source_path, [1.0, 0.0])],
            [[1.0, 0.0]],
        )
        store.replace_document_chunks(
            doc2,
            [_chunk("c2", "d2", doc2.source_path, [1.0, 0.0])],
            [[1.0, 0.0]],
        )

        count = store.mark_missing_documents_deleted({"my_md/doc_rag_corpus/a.md"})

        assert count == 1
        assert store.get_document("my_md/doc_rag_corpus/a.md").status == "active"
        assert store.get_document("my_md/doc_rag_corpus/b.md").status == "deleted"
    finally:
        store.close()


def test_store_clears_chunks_when_marking_missing_documents_deleted(tmp_path):
    store = DocRagStore(tmp_path / "doc_rag.db", vec_dim=2)
    try:
        doc = _doc("d1", "my_md/doc_rag_corpus/a.md")
        store.replace_document_chunks(
            doc,
            [_chunk("c1", "d1", doc.source_path, [1.0, 0.0])],
            [[1.0, 0.0]],
        )

        count = store.mark_missing_documents_deleted(set())

        assert count == 1
        assert store.get_document(doc.source_path).status == "deleted"
        assert store.list_chunks(doc.source_path) == []
        assert store.search_vector([1.0, 0.0], top_k=1, similarity_threshold=0.1) == []
    finally:
        store.close()
