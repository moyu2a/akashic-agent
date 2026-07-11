from __future__ import annotations

import json

import pytest

from agent.config_models import Config
from agent.tools.doc_rag import FetchDocChunkTool, SearchDocsTool
from doc_rag.models import ChunkRecord, RetrievalHit, SearchResult


def _config(enabled: bool = True) -> Config:
    cfg = Config(
        provider="deepseek",
        model="deepseek-chat",
        api_key="main-secret",
        base_url="https://main.example/v1",
        system_prompt="test",
    )
    cfg.doc_rag.enabled = enabled
    cfg.doc_rag.store_path = "/tmp/should-not-be-opened.db"
    cfg.doc_rag.embedding.dim = 2
    cfg.doc_rag.retrieval.top_k = 5
    return cfg


def _hit(rank: int = 1) -> RetrievalHit:
    return RetrievalHit(
        rank=rank,
        chunk_id=f"chunk-{rank}",
        chunk_key=f"chunk-key-{rank}",
        source_path="my_md/doc_rag_corpus/manual_test.md",
        heading_path="Agent Runtime",
        score=0.806164,
        score_type="vector",
        snippet="Agent runtime 负责管理 agent 的一次运行过程。",
        chunk_content_hash="chunk-hash",
        document_content_hash="doc-hash",
    )


def _chunk(
    content: str = "Agent runtime 负责管理 agent 的一次运行过程。",
) -> ChunkRecord:
    return ChunkRecord(
        chunk_id="chunk-1",
        chunk_key="chunk-key-1",
        doc_id="doc-1",
        source_path="my_md/doc_rag_corpus/manual_test.md",
        title="Agent Runtime",
        heading_path="Agent Runtime",
        chunk_index=0,
        content=content,
        chunk_content_hash="chunk-hash",
        document_content_hash="doc-hash",
        token_count=10,
        char_count=len(content),
        embedding_status="ready",
    )


class _FakeRetriever:
    def __init__(self, result: SearchResult | None = None, fail: bool = False) -> None:
        self.result = result or SearchResult(
            query="agent runtime 负责什么",
            top_k=5,
            hits=[_hit()],
            trace_id="trace-1",
            error="",
            latency_ms=12.3,
        )
        self.fail = fail
        self.calls: list[tuple[str, int | None]] = []

    async def search(self, query: str, top_k: int | None = None) -> SearchResult:
        self.calls.append((query, top_k))
        if self.fail:
            raise RuntimeError("backend failed with main-secret")
        return self.result


class _FakeStore:
    def __init__(self, chunk: ChunkRecord | None = None, fail: bool = False) -> None:
        self.chunk = chunk
        self.fail = fail
        self.calls: list[str] = []

    def get_chunk(self, chunk_id: str) -> ChunkRecord | None:
        self.calls.append(chunk_id)
        if self.fail:
            raise RuntimeError("store failed with main-secret")
        return self.chunk


@pytest.mark.anyio
async def test_search_docs_returns_structured_hits_without_content() -> None:
    retriever = _FakeRetriever()
    tool = SearchDocsTool(_config(), retriever=retriever)

    payload = json.loads(await tool.execute(query="agent runtime 负责什么", top_k=3))

    assert payload["ok"] is True
    assert payload["error_code"] == ""
    assert payload["trace_id"] == "trace-1"
    assert payload["hit_count"] == 1
    assert payload["hits"][0]["chunk_id"] == "chunk-1"
    assert payload["hits"][0]["source_path"] == "my_md/doc_rag_corpus/manual_test.md"
    assert payload["hits"][0]["heading_path"] == "Agent Runtime"
    assert payload["hits"][0]["citation"] == (
        "[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]"
    )
    assert payload["hits"][0]["score"] == 0.806164
    assert payload["hits"][0]["score_type"] == "vector"
    assert "snippet" in payload["hits"][0]
    assert "content" not in payload["hits"][0]
    assert retriever.calls == [("agent runtime 负责什么", 3)]


@pytest.mark.anyio
async def test_search_docs_no_hits_is_successful_empty_result() -> None:
    retriever = _FakeRetriever(
        SearchResult(
            query="unknown topic",
            top_k=5,
            hits=[],
            trace_id="trace-empty",
            error="",
        )
    )
    tool = SearchDocsTool(_config(), retriever=retriever)

    payload = json.loads(await tool.execute(query="unknown topic"))

    assert payload["ok"] is True
    assert payload["error_code"] == ""
    assert payload["trace_id"] == "trace-empty"
    assert payload["hit_count"] == 0
    assert payload["hits"] == []


@pytest.mark.anyio
async def test_search_docs_disabled_does_not_call_retriever() -> None:
    retriever = _FakeRetriever()
    tool = SearchDocsTool(_config(enabled=False), retriever=retriever)

    payload = json.loads(await tool.execute(query="agent runtime"))

    assert payload["ok"] is False
    assert payload["error_code"] == "doc_rag_disabled"
    assert payload["terminal"] is True
    assert payload["terminal_reason"] == "doc_rag_disabled"
    assert payload["terminal_scope"] == "document_rag"
    assert payload["retryable"] is False
    assert payload["fallback_allowed"] is False
    assert payload["recommended_action"] == "answer_doc_rag_disabled"
    assert payload["restart_required"] is True
    assert payload["restart_target"] == "agent_service"
    assert payload["current_process_can_enable"] is False
    assert payload["retrieval_available_this_turn"] is False
    assert payload["config_key"] == "doc_rag.enabled"
    assert payload["required_config_value"] is True
    assert "Do not claim you can enable" in payload["instructions"]
    assert "restart the Agent service" in payload["instructions"]
    assert "Do not continue retrieval in this turn" in payload["instructions"]
    assert "read_file" in payload["instructions"]
    assert "list_dir" in payload["instructions"]
    assert "shell" in payload["instructions"]
    assert "文档知识库当前未启用" in payload["user_message"]
    assert "当前运行中的 Agent" in payload["user_message"]
    assert "重启 Agent 服务" in payload["user_message"]
    assert "重启前本轮不能继续检索" in payload["user_message"]
    assert payload["hits"] == []
    assert "hit_count" not in payload
    assert retriever.calls == []


@pytest.mark.anyio
async def test_search_docs_validates_query_and_top_k() -> None:
    tool = SearchDocsTool(_config(), retriever=_FakeRetriever())

    empty = json.loads(await tool.execute(query="  "))
    invalid_low = json.loads(await tool.execute(query="runtime", top_k=0))
    invalid_high = json.loads(await tool.execute(query="runtime", top_k=11))

    assert empty["error_code"] == "empty_query"
    assert invalid_low["error_code"] == "invalid_top_k"
    assert invalid_high["error_code"] == "invalid_top_k"


@pytest.mark.anyio
async def test_search_docs_backend_error_is_structured_and_redacted() -> None:
    tool = SearchDocsTool(_config(), retriever=_FakeRetriever(fail=True))

    raw = await tool.execute(query="runtime")
    payload = json.loads(raw)

    assert payload["ok"] is False
    assert payload["error_code"] == "retrieval_error"
    assert "main-secret" not in raw


@pytest.mark.anyio
async def test_fetch_doc_chunk_returns_capped_content() -> None:
    store = _FakeStore(_chunk("0123456789" * 30))
    tool = FetchDocChunkTool(_config(), store=store)

    payload = json.loads(await tool.execute(chunk_id="chunk-1", max_chars=200))

    assert payload["ok"] is True
    assert payload["error_code"] == ""
    assert payload["chunk"]["chunk_id"] == "chunk-1"
    assert payload["chunk"]["source_path"] == "my_md/doc_rag_corpus/manual_test.md"
    assert payload["chunk"]["title"] == "Agent Runtime"
    assert payload["chunk"]["heading_path"] == "Agent Runtime"
    assert payload["chunk"]["citation"] == (
        "[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]"
    )
    assert payload["chunk"]["chunk_index"] == 0
    assert len(payload["chunk"]["content"]) == 200
    assert payload["chunk"]["content_truncated"] is True
    assert store.calls == ["chunk-1"]


@pytest.mark.anyio
async def test_fetch_doc_chunk_disabled_does_not_call_store() -> None:
    store = _FakeStore(_chunk())
    tool = FetchDocChunkTool(_config(enabled=False), store=store)

    payload = json.loads(await tool.execute(chunk_id="chunk-1"))

    assert payload["ok"] is False
    assert payload["error_code"] == "doc_rag_disabled"
    assert payload["terminal"] is True
    assert payload["terminal_reason"] == "doc_rag_disabled"
    assert payload["terminal_scope"] == "document_rag"
    assert payload["retryable"] is False
    assert payload["fallback_allowed"] is False
    assert payload["recommended_action"] == "answer_doc_rag_disabled"
    assert payload["restart_required"] is True
    assert payload["restart_target"] == "agent_service"
    assert payload["current_process_can_enable"] is False
    assert payload["retrieval_available_this_turn"] is False
    assert payload["config_key"] == "doc_rag.enabled"
    assert payload["required_config_value"] is True
    assert "Do not claim you can enable" in payload["instructions"]
    assert "restart the Agent service" in payload["instructions"]
    assert "Do not continue retrieval in this turn" in payload["instructions"]
    assert "read_file" in payload["instructions"]
    assert "文档知识库当前未启用" in payload["user_message"]
    assert "当前运行中的 Agent" in payload["user_message"]
    assert "重启 Agent 服务" in payload["user_message"]
    assert "重启前本轮不能继续检索" in payload["user_message"]
    assert "hits" not in payload
    assert "hit_count" not in payload
    assert store.calls == []


@pytest.mark.anyio
async def test_fetch_doc_chunk_validates_inputs_and_missing_chunk() -> None:
    tool = FetchDocChunkTool(_config(), store=_FakeStore(None))

    empty = json.loads(await tool.execute(chunk_id=" "))
    invalid_low = json.loads(await tool.execute(chunk_id="chunk-1", max_chars=199))
    invalid_high = json.loads(await tool.execute(chunk_id="chunk-1", max_chars=8001))
    missing = json.loads(await tool.execute(chunk_id="missing", max_chars=200))

    assert empty["error_code"] == "invalid_chunk_id"
    assert invalid_low["error_code"] == "invalid_max_chars"
    assert invalid_high["error_code"] == "invalid_max_chars"
    assert missing["error_code"] == "chunk_not_found"


@pytest.mark.anyio
async def test_fetch_doc_chunk_store_error_is_structured_and_redacted() -> None:
    tool = FetchDocChunkTool(_config(), store=_FakeStore(fail=True))

    raw = await tool.execute(chunk_id="chunk-1")
    payload = json.loads(raw)

    assert payload["ok"] is False
    assert payload["error_code"] == "store_error"
    assert "main-secret" not in raw


def test_doc_rag_tools_describe_disabled_behavior() -> None:
    assert "doc_rag_disabled" in SearchDocsTool.description
    assert "不要" in SearchDocsTool.description
    assert "本地文件读取" in SearchDocsTool.description
    assert "Document RAG" in SearchDocsTool.description
    assert "doc_rag.enabled=true" in SearchDocsTool.description
    assert "重启 Agent 服务" in SearchDocsTool.description

    assert "doc_rag_disabled" in FetchDocChunkTool.description
    assert "不要" in FetchDocChunkTool.description
    assert "本地文件读取" in FetchDocChunkTool.description
    assert "doc_rag.enabled=true" in FetchDocChunkTool.description
    assert "重启 Agent 服务" in FetchDocChunkTool.description
