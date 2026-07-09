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
    chunks = MarkdownChunker(DocRagChunkingConfig(max_chunk_chars=80)).chunk(
        _doc(content)
    )

    assert [chunk.heading_path for chunk in chunks] == ["A", "A > B", "A > B > C"]
    assert all(chunk.source_path == "my_md/doc_rag_corpus/a.md" for chunk in chunks)
    assert all(chunk.chunk_id for chunk in chunks)
    assert all(chunk.chunk_key for chunk in chunks)


def test_chunker_keeps_code_block_together() -> None:
    content = "# A\n\nBefore\n\n```python\nprint('a')\nprint('b')\n```\n\nAfter"
    chunks = MarkdownChunker(DocRagChunkingConfig(max_chunk_chars=500)).chunk(
        _doc(content)
    )

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
    assert all(
        chunk.metadata["split_reason"] in {"heading_block", "fallback_split"}
        for chunk in chunks
    )
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
