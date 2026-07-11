from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DocRagIntentConfidence = Literal["none", "low", "high"]

DOC_RAG_TOOL_NAMES = frozenset({"search_docs", "fetch_doc_chunk"})


@dataclass(frozen=True)
class DocRagPreloadDecision:
    preload_search_docs: bool
    preload_fetch_doc_chunk: bool
    suppress_doc_rag_lru: bool
    confidence: DocRagIntentConfidence
    reason: str
    matched_terms: tuple[str, ...] = ()


_EXPLICIT_NO_DOC_TERMS = (
    "不要查文档",
    "不要用文档",
    "只从长期记忆",
    "只从记忆",
)

_STRONG_DOC_TERMS = (
    "文档知识库",
    "Document RAG",
    "doc rag",
    "文档检索",
    "检索文档",
    "从文档中检索",
    "从知识库中检索",
    "知识库里检索",
    "根据文档回答",
    "回答必须带文档引用",
    "文档引用",
    "引用文档来源",
    "项目文档",
    "文档库",
    "资料库",
    "按资料回答",
    "search_docs",
    "fetch_doc_chunk",
)

_FETCH_INTENT_TERMS = (
    "原文",
    "完整内容",
    "文档证据",
    "展开",
    "chunk",
    "片段",
    "引用来源",
    "fetch_doc_chunk",
)

_MEMORY_SESSION_TERMS = (
    "长期记忆",
    "记忆",
    "我之前",
    "你还记得",
    "聊天记录",
    "session",
    "会话",
    "刚才说",
    "历史消息",
    "我的偏好",
    "从长期记忆",
    "回看消息",
)


def decide_doc_rag_preload(text: str) -> DocRagPreloadDecision:
    """Decide current-turn Document RAG tool visibility from conservative rules."""
    normalized = (text or "").lower()

    explicit_no_doc = _matched_terms(normalized, _EXPLICIT_NO_DOC_TERMS)
    if explicit_no_doc:
        return DocRagPreloadDecision(
            preload_search_docs=False,
            preload_fetch_doc_chunk=False,
            suppress_doc_rag_lru=True,
            confidence="high",
            reason="blocked_by_explicit_no_doc",
            matched_terms=explicit_no_doc,
        )

    strong_doc = _matched_terms(normalized, _STRONG_DOC_TERMS)
    if strong_doc:
        fetch_terms = _matched_terms(normalized, _FETCH_INTENT_TERMS)
        if fetch_terms:
            return DocRagPreloadDecision(
                preload_search_docs=True,
                preload_fetch_doc_chunk=True,
                suppress_doc_rag_lru=False,
                confidence="high",
                reason="strong_doc_with_fetch_intent",
                matched_terms=_dedupe_terms((*strong_doc, *fetch_terms)),
            )
        return DocRagPreloadDecision(
            preload_search_docs=True,
            preload_fetch_doc_chunk=False,
            suppress_doc_rag_lru=False,
            confidence="high",
            reason="strong_doc_intent",
            matched_terms=strong_doc,
        )

    memory_terms = _matched_terms(normalized, _MEMORY_SESSION_TERMS)
    if memory_terms:
        return DocRagPreloadDecision(
            preload_search_docs=False,
            preload_fetch_doc_chunk=False,
            suppress_doc_rag_lru=True,
            confidence="high",
            reason="blocked_by_memory_intent",
            matched_terms=memory_terms,
        )

    return DocRagPreloadDecision(
        preload_search_docs=False,
        preload_fetch_doc_chunk=False,
        suppress_doc_rag_lru=False,
        confidence="none",
        reason="no_doc_intent",
        matched_terms=(),
    )


def _matched_terms(normalized_text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(term for term in terms if term.lower() in normalized_text)


def _dedupe_terms(terms: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    deduped: list[str] = []
    for term in terms:
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(term)
    return tuple(deduped)
