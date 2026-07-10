from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol

from agent.config_models import Config
from doc_rag.chunker import MarkdownChunker
from doc_rag.embedding import (
    DocEmbeddingClient,
    build_embedding_text,
    resolve_embedding_settings,
)
from doc_rag.loader import MarkdownLoader
from doc_rag.models import (
    INDEX_FORMAT_VERSION,
    SCHEMA_VERSION,
    ChunkRecord,
    DocumentRecord,
    LoadedDocument,
)
from doc_rag.store import DocRagStore


class EmbeddingClientLike(Protocol):
    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


@dataclass
class IndexOptions:
    rebuild: bool = False
    dry_run: bool = False


@dataclass
class IndexSummary:
    run_id: str
    status: str
    docs_scanned: int = 0
    docs_indexed: int = 0
    docs_skipped: int = 0
    docs_deleted: int = 0
    docs_failed: int = 0
    chunks_created: int = 0
    embedding_failed: int = 0
    error: str = ""


class DocRagIndexer:
    def __init__(
        self,
        config: Config,
        *,
        store: DocRagStore | None = None,
        loader: MarkdownLoader | None = None,
        chunker: MarkdownChunker | None = None,
        embedding_client: EmbeddingClientLike | None = None,
    ) -> None:
        self.config = config
        self.doc_config = config.doc_rag
        self.store = store or DocRagStore(
            self.doc_config.store_path,
            vec_dim=self.doc_config.embedding.dim,
        )
        self.loader = loader or MarkdownLoader(self.doc_config)
        self.chunker = chunker or MarkdownChunker(self.doc_config.chunking)
        if embedding_client is None:
            embedding_client = DocEmbeddingClient(resolve_embedding_settings(config))
        self.embedding_client = embedding_client

    async def run(self, options: IndexOptions | None = None) -> IndexSummary:
        options = options or IndexOptions()
        meta = self._index_meta()
        run = self.store.start_index_run(
            config_hash=str(meta["index_config_hash"]),
            config=meta,
        )
        summary = IndexSummary(run_id=run.run_id, status="running")
        try:
            result = self.loader.load_all()
            summary.docs_scanned = len(result.documents) + len(result.errors)

            for error in result.errors:
                summary.docs_failed += 1
                self.store.record_index_run_doc(
                    run_id=run.run_id,
                    source_path=error.source_path,
                    action="load",
                    status="failed",
                    error_type=error.error_type,
                    error=error.message,
                )

            active_paths = {document.source_path for document in result.documents}
            if not options.dry_run:
                summary.docs_deleted = self.store.mark_missing_documents_deleted(
                    active_paths
                )

            for document in result.documents:
                await self._index_document(document, options, summary, run.run_id)

            summary.status = (
                "partial_failed" if summary.docs_failed > 0 else "succeeded"
            )
            if not options.dry_run:
                self.store.write_meta(meta)
            self.store.finish_index_run(
                run.run_id,
                summary.status,
                docs_scanned=summary.docs_scanned,
                docs_indexed=summary.docs_indexed,
                docs_skipped=summary.docs_skipped,
                docs_deleted=summary.docs_deleted,
                docs_failed=summary.docs_failed,
                chunks_created=summary.chunks_created,
                embedding_failed=summary.embedding_failed,
            )
            return summary
        except Exception as exc:
            summary.status = "failed"
            summary.error = str(exc)
            self.store.finish_index_run(run.run_id, "failed", error=str(exc))
            return summary

    async def _index_document(
        self,
        document: LoadedDocument,
        options: IndexOptions,
        summary: IndexSummary,
        run_id: str,
    ) -> None:
        existing = self.store.get_document(document.source_path)
        if (
            existing is not None
            and existing.status == "active"
            and existing.content_hash == document.content_hash
            and not options.rebuild
        ):
            summary.docs_skipped += 1
            self.store.record_index_run_doc(
                run_id=run_id,
                source_path=document.source_path,
                action="skipped_unchanged",
                status="succeeded",
                old_content_hash=existing.content_hash,
                new_content_hash=document.content_hash,
            )
            return

        old_hash = existing.content_hash if existing else ""
        try:
            chunks = self.chunker.chunk(document)
            embeddings = await self.embedding_client.embed_texts(
                [build_embedding_text(chunk) for chunk in chunks]
            )
            ready_chunks = [
                self._ready_chunk(chunk, document.content_hash) for chunk in chunks
            ]
            summary.docs_indexed += 1
            summary.chunks_created += len(ready_chunks)
            if not options.dry_run:
                self.store.replace_document_chunks(
                    self._document_record(document),
                    ready_chunks,
                    embeddings,
                )
            self.store.record_index_run_doc(
                run_id=run_id,
                source_path=document.source_path,
                action="indexed",
                status="succeeded",
                old_content_hash=old_hash,
                new_content_hash=document.content_hash,
                chunk_count=len(ready_chunks),
            )
        except Exception as exc:
            summary.docs_failed += 1
            summary.embedding_failed += 1
            self.store.record_index_run_doc(
                run_id=run_id,
                source_path=document.source_path,
                action="indexed",
                status="failed",
                old_content_hash=old_hash,
                new_content_hash=document.content_hash,
                error_type=exc.__class__.__name__,
                error=str(exc),
            )

    def _ready_chunk(
        self,
        chunk: ChunkRecord,
        document_content_hash: str,
    ) -> ChunkRecord:
        chunk.embedding_status = "ready"
        chunk.embedding_error = ""
        chunk.document_content_hash = document_content_hash
        return chunk

    def _document_record(self, document: LoadedDocument) -> DocumentRecord:
        return DocumentRecord(
            doc_id=document.doc_id,
            source_path=document.source_path,
            title=document.title,
            content_hash=document.content_hash,
            file_mtime=document.file_mtime,
            file_size=document.file_size,
            status="active",
            metadata=document.metadata,
        )

    def _index_meta(self) -> dict[str, object]:
        embedding = self.doc_config.embedding
        meta: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "index_format_version": INDEX_FORMAT_VERSION,
            "embedding_mode": embedding.mode,
            "embedding_model": embedding.model,
            "embedding_base_url": embedding.base_url,
            "embedding_dim": embedding.dim,
            "chunker_version": self.doc_config.chunking.chunker_version,
            "source_root": self.doc_config.source_root,
            "include_globs": list(self.doc_config.sources.include_globs),
            "allowed_extensions": list(self.doc_config.sources.allowed_extensions),
        }
        meta["index_config_hash"] = _stable_config_hash(meta)
        return meta


def _stable_config_hash(meta: dict[str, object]) -> str:
    raw = json.dumps(meta, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
