from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1
INDEX_FORMAT_VERSION = "doc_rag_v0"


def normalize_text_for_hash(text: str) -> str:
    return text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")


def stable_sha256(text: str) -> str:
    return hashlib.sha256(normalize_text_for_hash(text).encode("utf-8")).hexdigest()


def stable_sha1(text: str, length: int = 16) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:length]


def build_doc_id(source_path: str) -> str:
    return stable_sha1(source_path)


def build_chunk_key(source_path: str, heading_path: str, chunk_index: int) -> str:
    return stable_sha1(f"{source_path}\n{heading_path}\n{chunk_index}")


def build_chunk_id(
    source_path: str,
    heading_path: str,
    chunk_index: int,
    chunk_content_hash: str,
) -> str:
    return stable_sha1(
        f"{source_path}\n{heading_path}\n{chunk_index}\n{chunk_content_hash}"
    )


@dataclass
class LoadedDocument:
    doc_id: str
    source_path: str
    title: str
    content: str
    content_hash: str
    file_mtime: float
    file_size: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LoaderError:
    raw_path: str
    source_path: str
    error_type: str
    message: str


@dataclass
class LoaderResult:
    documents: list[LoadedDocument] = field(default_factory=list)
    errors: list[LoaderError] = field(default_factory=list)


@dataclass
class DocumentRecord:
    doc_id: str
    source_path: str
    title: str
    content_hash: str
    file_mtime: float
    file_size: int
    status: str = "active"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkRecord:
    chunk_id: str
    chunk_key: str
    doc_id: str
    source_path: str
    title: str
    heading_path: str
    chunk_index: int
    content: str
    chunk_content_hash: str
    document_content_hash: str
    token_count: int
    char_count: int
    embedding: list[float] | None = None
    embedding_status: str = "pending"
    embedding_error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IndexRun:
    run_id: str
    status: str
    config_hash: str
    started_at: str
    finished_at: str = ""
    error: str = ""


@dataclass
class IndexRunDoc:
    run_id: str
    source_path: str
    action: str
    status: str
    old_content_hash: str = ""
    new_content_hash: str = ""
    chunk_count: int = 0
    error_type: str = ""
    error: str = ""


@dataclass
class RetrievalHit:
    rank: int
    chunk_id: str
    chunk_key: str
    source_path: str
    heading_path: str
    score: float
    score_type: str
    snippet: str
    chunk_content_hash: str
    document_content_hash: str


@dataclass
class SearchResult:
    query: str
    top_k: int
    hits: list[RetrievalHit]
    trace_id: str = ""
    error: str = ""
    latency_ms: float = 0.0
