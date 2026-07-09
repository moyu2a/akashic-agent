from __future__ import annotations

from pathlib import Path

from agent.config import load_config


def _base_config(extra: str = "") -> str:
    return f"""
provider = "deepseek"
model = "deepseek-chat"
api_key = "sk-test"
system_prompt = "test"

[memory.embedding]
model = "text-embedding-v3"
api_key = "mem-key"
base_url = "https://example.invalid/v1"

{extra}
"""


def test_doc_rag_defaults_disabled(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(_base_config(), encoding="utf-8")

    cfg = load_config(path)

    assert cfg.doc_rag.enabled is False
    assert cfg.doc_rag.source_root == "."
    assert cfg.doc_rag.sources.include_globs == ["my_md/doc_rag_corpus/**/*.md"]
    assert cfg.doc_rag.chunking.target_chunk_chars == 1600
    assert cfg.doc_rag.embedding.mode == "inherit_memory"
    assert cfg.doc_rag.embedding.dim == 1024
    assert cfg.doc_rag.retrieval.top_k == 5
    assert cfg.doc_rag.trace.include_content is False
    assert cfg.doc_rag.citation.format == "[source_path > heading_path]"
    assert cfg.doc_rag.eval.eval_set_path == (
        "my_md/rag/eval_sets/doc_rag_eval_v0.jsonl"
    )


def test_doc_rag_loads_nested_config(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        _base_config("""
[doc_rag]
enabled = true
source_root = "/repo"
store_path = "/tmp/doc_rag.db"
collection_id = "docs"

[doc_rag.sources]
include_globs = ["docs/**/*.md"]
exclude_globs = ["**/*.tmp"]
allowed_extensions = [".md"]
max_file_size_bytes = 1234
allow_external_symlink = true

[doc_rag.chunking]
chunker_version = "heading_block_v0"
target_chunk_chars = 1000
max_chunk_chars = 1500
min_chunk_chars = 200
chunk_overlap_chars = 100

[doc_rag.embedding]
mode = "custom"
model = "embed-x"
api_key = "${DOC_RAG_TEST_KEY}"
base_url = "https://emb.invalid/v1"
dim = 768
batch_size = 8
max_retries = 3
timeout_seconds = 20

[doc_rag.retrieval]
top_k = 7
similarity_threshold = 0.5
retrieval_mode = "vector_only"
fallback_enabled = false

[doc_rag.trace]
enabled = false
format = "jsonl"
path = "/tmp/trace.jsonl"
include_content = true
max_content_chars = 3000

[doc_rag.citation]
required_for_doc_answer = false
format = "[source]"
include_chunk_id_for_debug = true
on_no_hits = "state_no_evidence"

[doc_rag.eval]
eval_set_path = "eval.jsonl"
report_dir = "reports"
"""),
        encoding="utf-8",
    )

    cfg = load_config(path)

    assert cfg.doc_rag.enabled is True
    assert cfg.doc_rag.source_root == "/repo"
    assert cfg.doc_rag.sources.include_globs == ["docs/**/*.md"]
    assert cfg.doc_rag.embedding.mode == "custom"
    assert cfg.doc_rag.embedding.model == "embed-x"
    assert cfg.doc_rag.embedding.dim == 768
    assert cfg.doc_rag.retrieval.top_k == 7
    assert cfg.doc_rag.trace.include_content is True
    assert cfg.doc_rag.citation.include_chunk_id_for_debug is True
    assert cfg.doc_rag.eval.report_dir == "reports"
