CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    file_mtime REAL NOT NULL,
    file_size INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    chunk_key TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    source_path TEXT NOT NULL,
    title TEXT NOT NULL,
    heading_path TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    chunk_content_hash TEXT NOT NULL,
    document_content_hash TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    char_count INTEGER NOT NULL,
    embedding TEXT,
    embedding_status TEXT NOT NULL DEFAULT 'pending',
    embedding_error TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_chunks_doc_id ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS ix_chunks_source_path ON chunks(source_path);
CREATE INDEX IF NOT EXISTS ix_chunks_embedding_status ON chunks(embedding_status);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    chunk_id UNINDEXED,
    source_path UNINDEXED,
    heading_path,
    content
);

CREATE TABLE IF NOT EXISTS index_runs (
    run_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    config_json TEXT NOT NULL DEFAULT '{}',
    docs_scanned INTEGER NOT NULL DEFAULT 0,
    docs_indexed INTEGER NOT NULL DEFAULT 0,
    docs_skipped INTEGER NOT NULL DEFAULT 0,
    docs_deleted INTEGER NOT NULL DEFAULT 0,
    docs_failed INTEGER NOT NULL DEFAULT 0,
    chunks_created INTEGER NOT NULL DEFAULT 0,
    chunks_deleted INTEGER NOT NULL DEFAULT 0,
    embedding_failed INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS index_run_docs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    source_path TEXT NOT NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    old_content_hash TEXT NOT NULL DEFAULT '',
    new_content_hash TEXT NOT NULL DEFAULT '',
    chunk_count INTEGER NOT NULL DEFAULT 0,
    error_type TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
