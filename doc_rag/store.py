from __future__ import annotations

import json
import math
import sqlite3
import struct
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from doc_rag.models import ChunkRecord, DocumentRecord, RetrievalHit

try:
    import sqlite_vec

    _SQLITE_VEC_AVAILABLE = True
except Exception:
    sqlite_vec = None
    _SQLITE_VEC_AVAILABLE = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_embedding(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vec))
    if norm < 1e-9:
        return vec
    return [value / norm for value in vec]


def _emb_to_blob(vec: list[float]) -> bytes:
    normalized = _normalize_embedding(vec)
    return struct.pack(f"{len(normalized)}f", *normalized)


def _l2dist_to_cosine(distance: float) -> float:
    return 1.0 - (distance * distance) / 2.0


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    a_norm = math.sqrt(sum(value * value for value in a))
    b_norm = math.sqrt(sum(value * value for value in b))
    if a_norm < 1e-9 or b_norm < 1e-9:
        return 0.0
    dot = sum(left * right for left, right in zip(a, b, strict=False))
    return dot / a_norm / b_norm


def _snippet(text: str, max_chars: int = 240) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max(0, max_chars - 1)].rstrip() + "…"


class DocRagStore:
    def __init__(self, db_path: str | Path, vec_dim: int = 1024) -> None:
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys=ON")
        self._lock = threading.RLock()
        self._closed = False
        self._vec_dim = vec_dim
        self._vec_enabled = False
        self._vec_init_error = ""
        self.init_schema()
        self._init_vec()

    @property
    def vec_enabled(self) -> bool:
        return self._vec_enabled

    @property
    def vec_init_error(self) -> str:
        return self._vec_init_error

    def init_schema(self) -> None:
        schema_path = Path(__file__).with_name("schema.sql")
        self._db.executescript(schema_path.read_text(encoding="utf-8"))
        self._db.commit()

    def _init_vec(self) -> None:
        if not _SQLITE_VEC_AVAILABLE:
            self._vec_init_error = "sqlite_vec 未安装"
            return
        try:
            assert sqlite_vec is not None
            self._db.enable_load_extension(True)
            sqlite_vec.load(self._db)
            self._db.enable_load_extension(False)
            self._db.executescript(f"""
CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(
    embedding float[{self._vec_dim}]
);
""")
            self._db.commit()
            self._vec_enabled = True
        except Exception as exc:
            self._vec_init_error = str(exc)

    def close(self) -> None:
        if self._closed:
            return
        self._db.close()
        self._closed = True

    def get_meta(self) -> dict[str, Any]:
        rows = self._db.execute("SELECT key, value FROM meta").fetchall()
        result: dict[str, Any] = {}
        for row in rows:
            key = str(row["key"])
            try:
                result[key] = json.loads(str(row["value"]))
            except json.JSONDecodeError:
                result[key] = row["value"]
        return result

    def write_meta(self, meta: dict[str, Any]) -> None:
        with self._lock:
            self._db.executemany(
                "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
                [
                    (key, json.dumps(value, ensure_ascii=False))
                    for key, value in meta.items()
                ],
            )
            self._db.commit()

    def start_index_run(
        self, config_hash: str, config: dict[str, Any]
    ) -> SimpleNamespace:
        run_id = uuid.uuid4().hex
        with self._lock:
            self._db.execute(
                """
                INSERT INTO index_runs(
                    run_id, status, config_hash, config_json, started_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    "running",
                    config_hash,
                    json.dumps(config, ensure_ascii=False),
                    _now_iso(),
                ),
            )
            self._db.commit()
        return SimpleNamespace(run_id=run_id, status="running", config_hash=config_hash)

    def finish_index_run(
        self,
        run_id: str,
        status: str,
        *,
        docs_scanned: int = 0,
        docs_indexed: int = 0,
        docs_skipped: int = 0,
        docs_deleted: int = 0,
        docs_failed: int = 0,
        chunks_created: int = 0,
        chunks_deleted: int = 0,
        embedding_failed: int = 0,
        error: str = "",
    ) -> None:
        with self._lock:
            self._db.execute(
                """
                UPDATE index_runs
                SET status=?, docs_scanned=?, docs_indexed=?, docs_skipped=?,
                    docs_deleted=?, docs_failed=?, chunks_created=?, chunks_deleted=?,
                    embedding_failed=?, finished_at=?, error=?
                WHERE run_id=?
                """,
                (
                    status,
                    docs_scanned,
                    docs_indexed,
                    docs_skipped,
                    docs_deleted,
                    docs_failed,
                    chunks_created,
                    chunks_deleted,
                    embedding_failed,
                    _now_iso(),
                    error,
                    run_id,
                ),
            )
            self._db.commit()

    def record_index_run_doc(
        self,
        *,
        run_id: str,
        source_path: str,
        action: str,
        status: str,
        old_content_hash: str = "",
        new_content_hash: str = "",
        chunk_count: int = 0,
        error_type: str = "",
        error: str = "",
    ) -> None:
        with self._lock:
            self._db.execute(
                """
                INSERT INTO index_run_docs(
                    run_id, source_path, action, status, old_content_hash,
                    new_content_hash, chunk_count, error_type, error
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    source_path,
                    action,
                    status,
                    old_content_hash,
                    new_content_hash,
                    chunk_count,
                    error_type,
                    error,
                ),
            )
            self._db.commit()

    def get_index_run(self, run_id: str) -> dict[str, Any]:
        row = self._db.execute(
            "SELECT * FROM index_runs WHERE run_id=?", (run_id,)
        ).fetchone()
        return dict(row) if row else {}

    def list_index_run_docs(self, run_id: str) -> list[dict[str, Any]]:
        rows = self._db.execute(
            "SELECT * FROM index_run_docs WHERE run_id=? ORDER BY id", (run_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    def get_document(self, source_path: str) -> DocumentRecord | None:
        row = self._db.execute(
            "SELECT * FROM documents WHERE source_path=?", (source_path,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_document(row)

    def list_documents(self, status: str | None = "active") -> list[DocumentRecord]:
        if status is None:
            rows = self._db.execute(
                "SELECT * FROM documents ORDER BY source_path"
            ).fetchall()
        else:
            rows = self._db.execute(
                "SELECT * FROM documents WHERE status=? ORDER BY source_path",
                (status,),
            ).fetchall()
        return [self._row_to_document(row) for row in rows]

    def _row_to_document(self, row: sqlite3.Row) -> DocumentRecord:
        return DocumentRecord(
            doc_id=row["doc_id"],
            source_path=row["source_path"],
            title=row["title"],
            content_hash=row["content_hash"],
            file_mtime=float(row["file_mtime"]),
            file_size=int(row["file_size"]),
            status=row["status"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )

    def upsert_document(self, document: DocumentRecord) -> None:
        with self._lock:
            self._upsert_document_no_commit(document)
            self._db.commit()

    def _upsert_document_no_commit(self, document: DocumentRecord) -> None:
        self._db.execute(
            """
            INSERT INTO documents(
                doc_id, source_path, title, content_hash, file_mtime,
                file_size, status, metadata_json, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(doc_id) DO UPDATE SET
                source_path=excluded.source_path,
                title=excluded.title,
                content_hash=excluded.content_hash,
                file_mtime=excluded.file_mtime,
                file_size=excluded.file_size,
                status=excluded.status,
                metadata_json=excluded.metadata_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                document.doc_id,
                document.source_path,
                document.title,
                document.content_hash,
                document.file_mtime,
                document.file_size,
                document.status,
                json.dumps(document.metadata, ensure_ascii=False),
            ),
        )

    def _validate_embeddings(
        self,
        chunks: list[ChunkRecord],
        embeddings: list[list[float]] | None,
    ) -> list[list[float] | None]:
        if embeddings is not None and len(embeddings) != len(chunks):
            raise ValueError("embedding count does not match chunks")
        resolved: list[list[float] | None] = []
        for index, chunk in enumerate(chunks):
            embedding = embeddings[index] if embeddings is not None else chunk.embedding
            if chunk.embedding_status == "ready":
                if embedding is None:
                    raise ValueError(f"ready chunk has no embedding: {chunk.chunk_id}")
                if len(embedding) != self._vec_dim:
                    raise ValueError(
                        f"embedding dim mismatch for {chunk.chunk_id}: "
                        f"expected {self._vec_dim}, got {len(embedding)}"
                    )
            elif embedding is not None and len(embedding) != self._vec_dim:
                raise ValueError(
                    f"embedding dim mismatch for {chunk.chunk_id}: "
                    f"expected {self._vec_dim}, got {len(embedding)}"
                )
            resolved.append(embedding)
        return resolved

    def replace_document_chunks(
        self,
        document: DocumentRecord,
        chunks: list[ChunkRecord],
        embeddings: list[list[float]] | None = None,
    ) -> None:
        resolved_embeddings = self._validate_embeddings(chunks, embeddings)
        with self._lock:
            try:
                self._db.execute("BEGIN IMMEDIATE")
                old_rows = self._db.execute(
                    "SELECT rowid FROM chunks WHERE doc_id=?", (document.doc_id,)
                ).fetchall()
                old_rowids = [int(row["rowid"]) for row in old_rows]
                self._upsert_document_no_commit(document)
                self._db.execute(
                    "DELETE FROM chunks WHERE doc_id=?", (document.doc_id,)
                )
                self._db.execute(
                    "DELETE FROM chunks_fts WHERE source_path=?",
                    (document.source_path,),
                )
                if self._vec_enabled:
                    self._delete_vec_chunks(old_rowids)

                for chunk, embedding in zip(chunks, resolved_embeddings, strict=True):
                    self._insert_chunk_no_commit(chunk, embedding)

                self._db.commit()
            except Exception:
                self._db.rollback()
                raise

    def _insert_chunk_no_commit(
        self, chunk: ChunkRecord, embedding: list[float] | None
    ) -> None:
        cur = self._db.execute(
            """
            INSERT INTO chunks(
                chunk_id, chunk_key, doc_id, source_path, title, heading_path,
                chunk_index, content, chunk_content_hash, document_content_hash,
                token_count, char_count, embedding, embedding_status,
                embedding_error, metadata_json, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                chunk.chunk_id,
                chunk.chunk_key,
                chunk.doc_id,
                chunk.source_path,
                chunk.title,
                chunk.heading_path,
                chunk.chunk_index,
                chunk.content,
                chunk.chunk_content_hash,
                chunk.document_content_hash,
                chunk.token_count,
                chunk.char_count,
                (
                    json.dumps(embedding, ensure_ascii=False)
                    if embedding is not None
                    else None
                ),
                chunk.embedding_status,
                chunk.embedding_error,
                json.dumps(chunk.metadata, ensure_ascii=False),
            ),
        )
        self._db.execute(
            """
            INSERT INTO chunks_fts(chunk_id, source_path, heading_path, content)
            VALUES (?, ?, ?, ?)
            """,
            (chunk.chunk_id, chunk.source_path, chunk.heading_path, chunk.content),
        )
        if self._vec_enabled and embedding is not None:
            self._insert_vec_chunk(int(cur.lastrowid), embedding)

    def _insert_vec_chunk(self, rowid: int, embedding: list[float]) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO vec_chunks(rowid, embedding) VALUES (?, ?)",
            (rowid, _emb_to_blob(embedding)),
        )

    def _delete_vec_chunks(self, rowids: list[int]) -> None:
        if not rowids:
            return
        self._db.executemany(
            "DELETE FROM vec_chunks WHERE rowid=?", [(rowid,) for rowid in rowids]
        )

    def list_chunks(self, source_path: str | None = None) -> list[ChunkRecord]:
        if source_path is None:
            rows = self._db.execute(
                "SELECT * FROM chunks ORDER BY source_path, chunk_index"
            ).fetchall()
        else:
            rows = self._db.execute(
                """
                SELECT * FROM chunks
                WHERE source_path=?
                ORDER BY chunk_index
                """,
                (source_path,),
            ).fetchall()
        return [self._row_to_chunk(row) for row in rows]

    def mark_missing_documents_deleted(self, active_source_paths: set[str]) -> int:
        with self._lock:
            try:
                self._db.execute("BEGIN IMMEDIATE")
                if active_source_paths:
                    placeholders = ",".join("?" for _ in active_source_paths)
                    params = tuple(sorted(active_source_paths))
                    documents = self._db.execute(
                        f"""
                        SELECT doc_id, source_path
                        FROM documents
                        WHERE status='active'
                          AND source_path NOT IN ({placeholders})
                        """,
                        params,
                    ).fetchall()
                else:
                    documents = self._db.execute("""
                        SELECT doc_id, source_path
                        FROM documents
                        WHERE status='active'
                    """).fetchall()

                if not documents:
                    self._db.commit()
                    return 0

                doc_ids = [str(row["doc_id"]) for row in documents]
                source_paths = [str(row["source_path"]) for row in documents]
                doc_placeholders = ",".join("?" for _ in doc_ids)
                old_rows = self._db.execute(
                    f"SELECT rowid FROM chunks WHERE doc_id IN ({doc_placeholders})",
                    tuple(doc_ids),
                ).fetchall()
                old_rowids = [int(row["rowid"]) for row in old_rows]

                if self._vec_enabled:
                    self._delete_vec_chunks(old_rowids)
                self._db.execute(
                    f"DELETE FROM chunks WHERE doc_id IN ({doc_placeholders})",
                    tuple(doc_ids),
                )
                self._db.executemany(
                    "DELETE FROM chunks_fts WHERE source_path=?",
                    [(source_path,) for source_path in source_paths],
                )
                self._db.execute(
                    f"""
                    UPDATE documents
                    SET status='deleted', updated_at=CURRENT_TIMESTAMP
                    WHERE doc_id IN ({doc_placeholders})
                    """,
                    tuple(doc_ids),
                )
                self._db.commit()
                return len(documents)
            except Exception:
                self._db.rollback()
                raise

    def search_vector(
        self,
        query_vec: list[float],
        top_k: int,
        similarity_threshold: float,
    ) -> list[RetrievalHit]:
        if self._vec_enabled:
            try:
                return self._search_vector_sqlite_vec(
                    query_vec, top_k, similarity_threshold
                )
            except Exception:
                return self._search_vector_fullscan(
                    query_vec, top_k, similarity_threshold
                )
        return self._search_vector_fullscan(query_vec, top_k, similarity_threshold)

    def _search_vector_sqlite_vec(
        self,
        query_vec: list[float],
        top_k: int,
        similarity_threshold: float,
    ) -> list[RetrievalHit]:
        rows = self._db.execute(
            """
            SELECT c.*, v.distance
            FROM (
                SELECT rowid, distance
                FROM vec_chunks
                WHERE embedding MATCH ?
                  AND k = ?
            ) v
            JOIN chunks c ON c.rowid = v.rowid
            JOIN documents d ON d.doc_id = c.doc_id
            WHERE d.status='active'
              AND c.embedding_status='ready'
              AND c.embedding IS NOT NULL
            ORDER BY v.distance ASC
            """,
            (_emb_to_blob(query_vec), top_k),
        ).fetchall()
        hits: list[RetrievalHit] = []
        for row in rows:
            score = _l2dist_to_cosine(float(row["distance"]))
            if score < similarity_threshold:
                continue
            hits.append(self._row_to_hit(row, len(hits) + 1, score, "vector"))
            if len(hits) >= top_k:
                break
        return hits

    def _search_vector_fullscan(
        self,
        query_vec: list[float],
        top_k: int,
        similarity_threshold: float,
    ) -> list[RetrievalHit]:
        rows = self._db.execute("""
            SELECT c.*
            FROM chunks c
            JOIN documents d ON d.doc_id = c.doc_id
            WHERE d.status='active'
              AND c.embedding_status='ready'
              AND c.embedding IS NOT NULL
            """).fetchall()
        scored: list[tuple[sqlite3.Row, float]] = []
        for row in rows:
            embedding = json.loads(row["embedding"]) if row["embedding"] else None
            if not isinstance(embedding, list):
                continue
            score = _cosine_similarity(query_vec, [float(value) for value in embedding])
            if score >= similarity_threshold:
                scored.append((row, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return [
            self._row_to_hit(row, rank, score, "vector_fallback")
            for rank, (row, score) in enumerate(scored[:top_k], start=1)
        ]

    def _row_to_hit(
        self,
        row: sqlite3.Row,
        rank: int,
        score: float,
        score_type: str,
    ) -> RetrievalHit:
        return RetrievalHit(
            rank=rank,
            chunk_id=row["chunk_id"],
            chunk_key=row["chunk_key"],
            source_path=row["source_path"],
            heading_path=row["heading_path"],
            score=round(score, 6),
            score_type=score_type,
            snippet=_snippet(row["content"]),
            chunk_content_hash=row["chunk_content_hash"],
            document_content_hash=row["document_content_hash"],
        )

    def get_chunk(self, chunk_id: str) -> ChunkRecord | None:
        row = self._db.execute(
            "SELECT * FROM chunks WHERE chunk_id=?", (chunk_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_chunk(row)

    def _row_to_chunk(self, row: sqlite3.Row) -> ChunkRecord:
        embedding = json.loads(row["embedding"]) if row["embedding"] else None
        return ChunkRecord(
            chunk_id=row["chunk_id"],
            chunk_key=row["chunk_key"],
            doc_id=row["doc_id"],
            source_path=row["source_path"],
            title=row["title"],
            heading_path=row["heading_path"],
            chunk_index=int(row["chunk_index"]),
            content=row["content"],
            chunk_content_hash=row["chunk_content_hash"],
            document_content_hash=row["document_content_hash"],
            token_count=int(row["token_count"]),
            char_count=int(row["char_count"]),
            embedding=embedding,
            embedding_status=row["embedding_status"],
            embedding_error=row["embedding_error"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )
