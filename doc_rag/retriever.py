from __future__ import annotations

import time
from typing import Protocol

from agent.config_models import Config
from doc_rag.embedding import DocEmbeddingClient, resolve_embedding_settings
from doc_rag.models import RetrievalHit, SearchResult
from doc_rag.store import DocRagStore
from doc_rag.trace import new_trace_id, now_iso, write_retrieval_trace


class EmbeddingClientLike(Protocol):
    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class DocRagRetriever:
    def __init__(
        self,
        config: Config,
        *,
        store: DocRagStore | None = None,
        embedding_client: EmbeddingClientLike | None = None,
    ) -> None:
        self.config = config
        self.doc_config = config.doc_rag
        self.store = store or DocRagStore(
            self.doc_config.store_path,
            vec_dim=self.doc_config.embedding.dim,
        )
        if embedding_client is None:
            embedding_client = DocEmbeddingClient(resolve_embedding_settings(config))
        self.embedding_client = embedding_client

    async def search(self, query: str, top_k: int | None = None) -> SearchResult:
        started = time.perf_counter()
        trace_id = new_trace_id()
        normalized_query = query.strip()
        effective_top_k = top_k or self.doc_config.retrieval.top_k
        if not normalized_query:
            result = SearchResult(
                query=query,
                top_k=effective_top_k,
                hits=[],
                trace_id=trace_id,
                error="empty_query",
                latency_ms=self._latency_ms(started),
            )
            self._write_trace(result)
            return result

        try:
            query_vec = (await self.embedding_client.embed_texts([normalized_query]))[0]
            hits = self.store.search_vector(
                query_vec,
                top_k=effective_top_k,
                similarity_threshold=self.doc_config.retrieval.similarity_threshold,
            )
            result = SearchResult(
                query=normalized_query,
                top_k=effective_top_k,
                hits=hits,
                trace_id=trace_id,
                error="",
                latency_ms=self._latency_ms(started),
            )
        except Exception as exc:
            result = SearchResult(
                query=normalized_query,
                top_k=effective_top_k,
                hits=[],
                trace_id=trace_id,
                error=str(exc),
                latency_ms=self._latency_ms(started),
            )
        self._write_trace(result)
        return result

    def _write_trace(self, result: SearchResult) -> None:
        if not self.doc_config.trace.enabled:
            return
        event = {
            "trace_id": result.trace_id,
            "query": result.query,
            "top_k": result.top_k,
            "hit_count": len(result.hits),
            "hits": [self._trace_hit(hit) for hit in result.hits],
            "latency_ms": result.latency_ms,
            "retrieval_mode": self.doc_config.retrieval.retrieval_mode,
            "error": result.error,
            "created_at": now_iso(),
        }
        write_retrieval_trace(self.doc_config.trace.path, event)

    def _trace_hit(self, hit: RetrievalHit) -> dict[str, object]:
        payload: dict[str, object] = {
            "rank": hit.rank,
            "chunk_id": hit.chunk_id,
            "source_path": hit.source_path,
            "heading_path": hit.heading_path,
            "score": hit.score,
            "snippet": hit.snippet,
        }
        if self.doc_config.trace.include_content:
            chunk = self.store.get_chunk(hit.chunk_id)
            content = chunk.content if chunk else ""
            payload["content"] = content[: self.doc_config.trace.max_content_chars]
        return payload

    @staticmethod
    def _latency_ms(started: float) -> float:
        return round((time.perf_counter() - started) * 1000.0, 3)
