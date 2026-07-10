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
            config.memory.embedding.api_key or config.light_api_key or config.api_key
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
        for attempt in range(max(0, self.settings.max_retries) + 1):
            try:
                return await asyncio.wait_for(
                    self._backend.embed_batch(batch),
                    timeout=max(1, self.settings.timeout_seconds),
                )
            except Exception as exc:
                last_exc = exc
                if attempt >= max(0, self.settings.max_retries):
                    raise
        assert last_exc is not None
        raise last_exc
