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
        return self.vectors[: len(texts)]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


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
        [1.0, 0.0, 0.0],
    ]
    assert backend.calls == [["a", "b"], ["a", "b"], ["c"]]
