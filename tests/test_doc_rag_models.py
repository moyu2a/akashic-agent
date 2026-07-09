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
