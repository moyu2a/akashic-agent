from __future__ import annotations

import json
from typing import Any, Protocol

from agent.config_models import Config
from agent.tools.base import Tool
from doc_rag.models import ChunkRecord, SearchResult
from doc_rag.retriever import DocRagRetriever
from doc_rag.store import DocRagStore

_MAX_TOP_K = 10
_MIN_FETCH_CHARS = 200
_MAX_FETCH_CHARS = 8000
_DEFAULT_FETCH_CHARS = 2000


class RetrieverLike(Protocol):
    async def search(self, query: str, top_k: int | None = None) -> SearchResult: ...


class StoreLike(Protocol):
    def get_chunk(self, chunk_id: str) -> ChunkRecord | None: ...


class SearchDocsTool(Tool):
    name = "search_docs"
    description = (
        "用于检索已索引的 Markdown 文档知识库，返回相关 chunk 的 source_path、"
        "heading_path、chunk_id、score、snippet、citation 和 trace_id。"
        "如果使用本工具结果回答文档问题，最终回答的关键结论必须带 "
        "citation 字段中的 [source_path > heading_path] 引用。"
        "如果 snippet 不足以回答，必须继续调用 fetch_doc_chunk，"
        "而不是直接改用 read_file。不要用于查询用户长期记忆。"
        "如果返回 error_code=doc_rag_disabled，表示 Document RAG 未启用；"
        "应直接说明文档知识库当前不可用，不要用本地文件读取、list_dir "
        "或 shell 结果替代 Document RAG 检索。"
        "需设置 doc_rag.enabled=true 并重启 Agent 服务后才可检索。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "要在文档知识库中检索的问题或关键词",
                "minLength": 1,
            },
            "top_k": {
                "type": "integer",
                "description": "最多返回多少个文档片段，默认使用配置值，范围 1-10",
                "minimum": 1,
                "maximum": _MAX_TOP_K,
                "default": 5,
            },
        },
        "required": ["query"],
    }

    def __init__(
        self,
        config: Config,
        retriever: RetrieverLike | None = None,
    ) -> None:
        self._config = config
        self._retriever = retriever

    async def execute(
        self,
        query: str,
        top_k: int | None = None,
        **_: Any,
    ) -> str:
        if not self._config.doc_rag.enabled:
            return _doc_rag_disabled_error(hits=[])

        clean_query = str(query or "").strip()
        if not clean_query:
            return _json_error("empty_query", "query is empty", hits=[])

        clean_top_k = (
            top_k if top_k is not None else self._config.doc_rag.retrieval.top_k
        )
        try:
            clean_top_k = int(clean_top_k)
        except TypeError:
            return _json_error(
                "invalid_top_k",
                f"top_k must be between 1 and {_MAX_TOP_K}",
                hits=[],
            )
        except ValueError:
            return _json_error(
                "invalid_top_k",
                f"top_k must be between 1 and {_MAX_TOP_K}",
                hits=[],
            )
        if clean_top_k < 1 or clean_top_k > _MAX_TOP_K:
            return _json_error(
                "invalid_top_k",
                f"top_k must be between 1 and {_MAX_TOP_K}",
                hits=[],
            )

        try:
            result = await self._get_retriever().search(clean_query, top_k=clean_top_k)
        except Exception as exc:
            return _json_error(
                "retrieval_error",
                _safe_error(exc, _config_secret_values(self._config)),
                hits=[],
            )

        if result.error:
            code = "empty_query" if result.error == "empty_query" else "retrieval_error"
            return _json_error(
                code,
                _safe_text(result.error, _config_secret_values(self._config)),
                hits=[],
            )

        return _json_dump(
            {
                "ok": True,
                "error_code": "",
                "query": result.query,
                "top_k": result.top_k,
                "trace_id": result.trace_id,
                "hit_count": len(result.hits),
                "hits": [
                    {
                        "rank": hit.rank,
                        "chunk_id": hit.chunk_id,
                        "source_path": hit.source_path,
                        "heading_path": hit.heading_path,
                        "citation": _doc_citation(hit.source_path, hit.heading_path),
                        "score": hit.score,
                        "score_type": hit.score_type,
                        "snippet": hit.snippet,
                        "chunk_content_hash": hit.chunk_content_hash,
                        "document_content_hash": hit.document_content_hash,
                    }
                    for hit in result.hits
                ],
            }
        )

    def _get_retriever(self) -> RetrieverLike:
        if self._retriever is None:
            self._retriever = DocRagRetriever(self._config)
        return self._retriever


class FetchDocChunkTool(Tool):
    name = "fetch_doc_chunk"
    description = (
        "根据 search_docs 返回的 chunk_id 读取更完整的文档 chunk。"
        "用于展开 search_docs 命中的证据，优先于 read_file。"
        "返回 source_path、heading_path、citation 和截断后的 content。"
        "最终回答应使用返回的 citation 字段引用来源。"
        "如果返回 doc_rag_disabled，表示 Document RAG 未启用；"
        "应直接说明文档知识库当前不可用，不要用本地文件读取替代。"
        "需设置 doc_rag.enabled=true 并重启 Agent 服务后才可检索。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "chunk_id": {
                "type": "string",
                "description": "search_docs 返回的 chunk_id",
                "minLength": 1,
            },
            "max_chars": {
                "type": "integer",
                "description": "最多返回多少字符，范围 200-8000，默认 2000",
                "minimum": _MIN_FETCH_CHARS,
                "maximum": _MAX_FETCH_CHARS,
                "default": _DEFAULT_FETCH_CHARS,
            },
        },
        "required": ["chunk_id"],
    }

    def __init__(
        self,
        config: Config,
        store: StoreLike | None = None,
    ) -> None:
        self._config = config
        self._store = store

    async def execute(
        self,
        chunk_id: str,
        max_chars: int = _DEFAULT_FETCH_CHARS,
        **_: Any,
    ) -> str:
        if not self._config.doc_rag.enabled:
            return _doc_rag_disabled_error()

        clean_chunk_id = str(chunk_id or "").strip()
        if not clean_chunk_id:
            return _json_error("invalid_chunk_id", "chunk_id is empty")

        try:
            clean_max_chars = int(max_chars)
        except TypeError:
            return _json_error(
                "invalid_max_chars",
                f"max_chars must be between {_MIN_FETCH_CHARS} and {_MAX_FETCH_CHARS}",
            )
        except ValueError:
            return _json_error(
                "invalid_max_chars",
                f"max_chars must be between {_MIN_FETCH_CHARS} and {_MAX_FETCH_CHARS}",
            )
        if clean_max_chars < _MIN_FETCH_CHARS or clean_max_chars > _MAX_FETCH_CHARS:
            return _json_error(
                "invalid_max_chars",
                f"max_chars must be between {_MIN_FETCH_CHARS} and {_MAX_FETCH_CHARS}",
            )

        try:
            chunk = self._get_store().get_chunk(clean_chunk_id)
        except Exception as exc:
            return _json_error(
                "store_error",
                _safe_error(exc, _config_secret_values(self._config)),
            )
        if chunk is None:
            return _json_error("chunk_not_found", "chunk not found")

        content = chunk.content[:clean_max_chars]
        return _json_dump(
            {
                "ok": True,
                "error_code": "",
                "chunk": {
                    "chunk_id": chunk.chunk_id,
                    "source_path": chunk.source_path,
                    "title": chunk.title,
                    "heading_path": chunk.heading_path,
                    "citation": _doc_citation(chunk.source_path, chunk.heading_path),
                    "chunk_index": chunk.chunk_index,
                    "content": content,
                    "content_truncated": len(chunk.content) > clean_max_chars,
                    "chunk_content_hash": chunk.chunk_content_hash,
                    "document_content_hash": chunk.document_content_hash,
                },
            }
        )

    def _get_store(self) -> StoreLike:
        if self._store is None:
            self._store = DocRagStore(
                self._config.doc_rag.store_path,
                vec_dim=self._config.doc_rag.embedding.dim,
            )
        return self._store


def _json_error(error_code: str, message: str, **extra: Any) -> str:
    return _json_dump(
        {
            "ok": False,
            "error_code": error_code,
            "message": message,
            **extra,
        }
    )


def _doc_rag_disabled_error(**extra: Any) -> str:
    return _json_error(
        "doc_rag_disabled",
        "Document RAG is disabled",
        terminal=True,
        terminal_reason="doc_rag_disabled",
        terminal_scope="document_rag",
        retryable=False,
        fallback_allowed=False,
        recommended_action="answer_doc_rag_disabled",
        restart_required=True,
        restart_target="agent_service",
        current_process_can_enable=False,
        retrieval_available_this_turn=False,
        config_key="doc_rag.enabled",
        required_config_value=True,
        instructions=(
            "Tell the user Document RAG is disabled. Do not claim you can enable "
            "it for the current running process. The user must set "
            "doc_rag.enabled=true and restart the Agent service before Document "
            "RAG retrieval can work. Do not continue retrieval in this turn. Do "
            "not use read_file, list_dir, shell, or other file tools as a "
            "substitute for document knowledge base retrieval."
        ),
        user_message=(
            "文档知识库当前未启用，当前运行中的 Agent 无法从 Document RAG "
            "检索文档证据。请将 doc_rag.enabled=true 写入配置后重启 Agent "
            "服务；重启前本轮不能继续检索。"
        ),
        **extra,
    )


def _json_dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _doc_citation(source_path: str, heading_path: str) -> str:
    source = str(source_path or "").strip()
    heading = str(heading_path or "").strip()
    if source and heading:
        return f"[{source} > {heading}]"
    if source:
        return f"[{source}]"
    return ""


def _safe_error(exc: Exception, secrets: list[str]) -> str:
    return _safe_text(str(exc), secrets)


def _safe_text(text: str, secrets: list[str]) -> str:
    # Avoid returning raw backend errors that may include bearer tokens or API keys.
    for marker in [*secrets, "sk-", "Bearer "]:
        if marker in text:
            return "backend error"
    return text


def _config_secret_values(config: Config) -> list[str]:
    candidates = [
        config.api_key,
        config.light_api_key,
        config.agent_api_key,
        config.vl_api_key,
        config.memory.embedding.api_key,
        config.doc_rag.embedding.api_key,
    ]
    return [value for value in candidates if value]
