from __future__ import annotations

import json
import re
from typing import Any, cast

from agent.lifecycle.types import PromptRenderCtx
from agent.plugins import Plugin
from agent.prompting import PromptSectionRender

_PROMPT_CTX_SLOT = "prompt:ctx"
_REASONING_CTX_SLOT = "reasoning:ctx"
_PERSIST_CITED_SLOT = "persist:assistant:cited_memory_ids"
_TRAILING_PROTOCOL_TAG = r"<[a-zA-Z][a-zA-Z0-9_-]*:[^<>\s]+>"
_CITED_RE = re.compile(
    rf"(?:\n|\r\n)?§cited:\[([A-Za-z0-9_,\-\s]*)\]§(?P<trailing>(?:\s*{_TRAILING_PROTOCOL_TAG}\s*)*)$",
    re.IGNORECASE,
)
_TRAILING_PROTOCOL_TAGS_RE = re.compile(
    rf"(?:\s*{_TRAILING_PROTOCOL_TAG}\s*)+$",
    re.IGNORECASE,
)
_INLINE_MEMORY_REF_RE = re.compile(
    r"[ \t]*(?:\[§[A-Za-z0-9:_-]{1,128}\])+", re.IGNORECASE
)
_DOC_RAG_VISIBLE_CITATION_RE = re.compile(
    r"\[[^\[\]\n]+?\.m(?:d|arkdown)\s+>\s+[^\[\]\n]+\]",
    re.IGNORECASE,
)

_CITATION_PROTOCOL = """### 记忆引用协议 - 内部元数据，对用户不可见
每轮回复若用到了系统注入的记忆条目 [item_id] 前缀标识，或 recall_memory / fetch_messages 工具返回的条目，在回复正文末尾另起一行输出：
§cited:[id1,id2,id3]§
格式规则：§ 包裹，英文逗号分隔，无空格，只写 ID，不含其他内容。
若本轮未引用任何记忆条目，不输出此行。
绝对不要在正文里提及这行的存在，不要向用户解释引用了什么，不要说根据记忆。
你了解用户的事是因为你们相处了很久，直接说你上次、我记得，不要暴露内部机制。"""

_DOC_RAG_CITATION_PROTOCOL = """### Document RAG 引用规则 - 对用户可见
当你使用 search_docs / fetch_doc_chunk 的结果回答文档问题时，关键结论后必须使用工具结果里的 citation 字段引用来源，格式为 [source_path > heading_path]。
如果 search_docs 返回 hit_count=0，不要编造文档引用；应说明当前文档知识库中没有检索到可引用证据。
如果 search_docs 的 snippet 不足以支撑回答，应继续调用 fetch_doc_chunk 展开 chunk，而不是直接改用 read_file。
不要把 recall_memory 的记忆引用协议用于 Document RAG。"""


class CitationPromptModule:
    slot = "citation.prompt"
    requires = ("prompt_render.emit", _PROMPT_CTX_SLOT)
    produces = (_PROMPT_CTX_SLOT,)

    def __init__(self, plugin: "CitationPlugin") -> None:
        self._plugin = plugin

    async def run(self, frame: Any) -> Any:
        ctx = frame.slots.get(_PROMPT_CTX_SLOT)
        if not isinstance(ctx, PromptRenderCtx):
            return frame
        ctx.system_sections_bottom.append(
            PromptSectionRender(
                name="citation_protocol",
                content=_CITATION_PROTOCOL,
                is_static=True,
            )
        )
        if _doc_rag_enabled_from_context(self._plugin):
            ctx.system_sections_bottom.append(
                PromptSectionRender(
                    name="doc_rag_citation_protocol",
                    content=_DOC_RAG_CITATION_PROTOCOL,
                    is_static=True,
                )
            )
        return frame


class CitationAfterReasoningModule:
    slot = "citation.after_reasoning"
    requires = ("after_reasoning.build_ctx", _REASONING_CTX_SLOT)
    produces = (_REASONING_CTX_SLOT, _PERSIST_CITED_SLOT)

    async def run(self, frame: Any) -> Any:
        ctx = frame.slots.get(_REASONING_CTX_SLOT)
        if ctx is None:
            return frame
        reply = str(getattr(ctx, "reply", "") or "")
        cleaned, cited_ids = extract_cited_ids(reply)
        cleaned = strip_inline_memory_refs(cleaned)
        if cited_ids:
            frame.slots[_PERSIST_CITED_SLOT] = cited_ids
        else:
            fallback_ids = extract_cited_ids_from_tool_chain(
                list(getattr(ctx, "tool_chain", ()) or ())
            )
            if fallback_ids:
                frame.slots[_PERSIST_CITED_SLOT] = fallback_ids
        if cleaned != reply:
            ctx.reply = cleaned
        return frame


class ProtocolTagCleanupModule:
    slot = "citation.protocol_cleanup"
    requires = ("after_reasoning.emit", _REASONING_CTX_SLOT)
    produces = (_REASONING_CTX_SLOT,)

    async def run(self, frame: Any) -> Any:
        ctx = frame.slots.get(_REASONING_CTX_SLOT)
        if ctx is None:
            return frame
        reply = str(getattr(ctx, "reply", "") or "")
        cleaned = strip_inline_memory_refs(strip_trailing_protocol_tags(reply))
        if cleaned != reply:
            ctx.reply = cleaned
        return frame


class DocRagCitationValidatorModule:
    slot = "citation.doc_rag_validator"
    requires = ("after_reasoning.build_ctx", _REASONING_CTX_SLOT)
    produces = (_REASONING_CTX_SLOT,)

    async def run(self, frame: Any) -> Any:
        ctx = frame.slots.get(_REASONING_CTX_SLOT)
        if ctx is None:
            return frame
        cleaned, summary = validate_doc_rag_citations(
            str(getattr(ctx, "reply", "") or ""),
            list(getattr(ctx, "tool_chain", ()) or ()),
        )
        ctx.reply = cleaned
        if summary["allowed_citations"] or summary["removed_fake_citations"]:
            ctx.outbound_metadata["doc_rag_citation"] = summary
        return frame


class CitationPlugin(Plugin):
    name = "citation"

    def prompt_render_modules(self) -> list[object]:
        return [CitationPromptModule(self)]

    def after_reasoning_modules(self) -> list[object]:
        return [
            CitationAfterReasoningModule(),
            DocRagCitationValidatorModule(),
            ProtocolTagCleanupModule(),
        ]


def extract_cited_ids(response: str) -> tuple[str, list[str]]:
    match = _CITED_RE.search(response)
    if not match:
        return response, []
    raw = match.group(1)
    ids = [item.strip() for item in raw.split(",") if item.strip()]
    trailing = match.group("trailing").strip()
    clean = response[: match.start()].rstrip()
    if trailing:
        clean = f"{clean} {trailing}".strip()
    return clean, ids


def strip_trailing_protocol_tags(response: str) -> str:
    return _TRAILING_PROTOCOL_TAGS_RE.sub("", response).rstrip()


def strip_inline_memory_refs(response: str) -> str:
    return _INLINE_MEMORY_REF_RE.sub("", response).rstrip()


def _doc_rag_enabled_from_context(plugin: Plugin | None) -> bool:
    app_config = getattr(getattr(plugin, "context", None), "app_config", None)
    doc_rag = getattr(app_config, "doc_rag", None)
    return bool(getattr(doc_rag, "enabled", False))


def _doc_citation(source_path: object, heading_path: object) -> str:
    source = str(source_path or "").strip()
    heading = str(heading_path or "").strip()
    if source and heading:
        return f"[{source} > {heading}]"
    if source:
        return f"[{source}]"
    return ""


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        clean = str(item or "").strip()
        if clean and clean not in seen:
            seen.add(clean)
            deduped.append(clean)
    return deduped


def _iter_tool_calls(tool_chain: list[dict[str, object]]) -> list[dict[str, object]]:
    calls_out: list[dict[str, object]] = []
    for group in tool_chain:
        calls_value = group.get("calls")
        if not isinstance(calls_value, list):
            continue
        calls = cast(list[object], calls_value)
        for raw_call in calls:
            if isinstance(raw_call, dict):
                calls_out.append(cast(dict[str, object], raw_call))
    return calls_out


def doc_rag_tool_was_called(tool_chain: list[dict[str, object]]) -> bool:
    return any(
        str(call.get("name", "") or "") in {"search_docs", "fetch_doc_chunk"}
        for call in _iter_tool_calls(tool_chain)
    )


def extract_doc_rag_citations_from_tool_chain(
    tool_chain: list[dict[str, object]],
) -> list[str]:
    citations: list[str] = []
    for call in _iter_tool_calls(tool_chain):
        name = str(call.get("name", "") or "")
        if name not in {"search_docs", "fetch_doc_chunk"}:
            continue
        raw_result = call.get("result")
        if isinstance(raw_result, dict):
            decoded = raw_result
        else:
            raw_text = str(raw_result or "").strip()
            if not raw_text:
                continue
            try:
                decoded = json.loads(raw_text)
            except (json.JSONDecodeError, TypeError, ValueError) as _exc:
                _ = _exc
                continue
        if not isinstance(decoded, dict):
            continue
        data = cast(dict[str, object], decoded)
        if name == "search_docs":
            if int(data.get("hit_count") or 0) <= 0:
                continue
            hits_value = data.get("hits")
            if not isinstance(hits_value, list):
                continue
            for raw_hit in cast(list[object], hits_value):
                if not isinstance(raw_hit, dict):
                    continue
                hit = cast(dict[str, object], raw_hit)
                citation = str(hit.get("citation", "") or "").strip()
                if not citation:
                    citation = _doc_citation(
                        hit.get("source_path"),
                        hit.get("heading_path"),
                    )
                citations.append(citation)
            continue
        chunk_value = data.get("chunk")
        if not isinstance(chunk_value, dict):
            continue
        chunk = cast(dict[str, object], chunk_value)
        citation = str(chunk.get("citation", "") or "").strip()
        if not citation:
            citation = _doc_citation(
                chunk.get("source_path"), chunk.get("heading_path")
            )
        citations.append(citation)
    return _dedupe_preserve_order(citations)


def extract_visible_doc_citations(reply: str) -> list[str]:
    return _dedupe_preserve_order(_DOC_RAG_VISIBLE_CITATION_RE.findall(reply or ""))


def reply_has_doc_rag_citation(reply: str, citations: list[str]) -> bool:
    return any(citation and citation in reply for citation in citations)


def is_doc_rag_no_evidence_reply(reply: str) -> bool:
    lowered = str(reply or "").lower()
    markers = [
        "当前文档知识库中没有检索到",
        "当前文档知识库中没有",
        "文档知识库中没有找到",
        "没有足够的文档证据",
        "没有足够文档证据",
        "无法从文档知识库",
        "无法根据文档知识库",
        "no document evidence",
        "no evidence in the document knowledge base",
        "not found in the document",
    ]
    return any(marker in lowered for marker in markers)


def remove_unknown_doc_citations(
    reply: str,
    allowed: list[str],
) -> tuple[str, list[str]]:
    allowed_set = set(allowed)
    removed: list[str] = []
    cleaned = reply
    for citation in extract_visible_doc_citations(reply):
        if citation in allowed_set:
            continue
        removed.append(citation)
        cleaned = cleaned.replace(citation, "")
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([。！？,.!?；;：:])", r"\1", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.rstrip(), removed


def append_doc_rag_references(
    reply: str,
    citations: list[str],
    limit: int = 2,
) -> str:
    selected = [item for item in citations if item][:limit]
    if not selected:
        return reply
    if reply_has_doc_rag_citation(reply, selected):
        return reply
    return f"{reply.rstrip()}\n\n参考来源：{'；'.join(selected)}"


def validate_doc_rag_citations(
    reply: str,
    tool_chain: list[dict[str, object]],
) -> tuple[str, dict[str, object]]:
    doc_rag_tool_called = doc_rag_tool_was_called(tool_chain)
    allowed = extract_doc_rag_citations_from_tool_chain(tool_chain)
    cleaned, removed_fake = (
        remove_unknown_doc_citations(reply, allowed)
        if doc_rag_tool_called
        else (reply, [])
    )
    inserted = False
    skipped_no_evidence = bool(allowed and is_doc_rag_no_evidence_reply(cleaned))
    if allowed and not skipped_no_evidence:
        before = cleaned
        cleaned = append_doc_rag_references(cleaned, allowed)
        inserted = cleaned != before
    return cleaned, {
        "allowed_citations": allowed,
        "removed_fake_citations": removed_fake,
        "inserted_fallback": inserted,
        "skipped_no_evidence": skipped_no_evidence,
        "doc_rag_tool_called": doc_rag_tool_called,
    }


def extract_cited_ids_from_tool_chain(
    tool_chain: list[dict[str, object]],
) -> list[str]:
    cited: list[str] = []
    seen: set[str] = set()
    for group in tool_chain:
        calls_value = group.get("calls")
        if not isinstance(calls_value, list):
            continue
        calls = cast(list[object], calls_value)
        for raw_call in calls:
            if not isinstance(raw_call, dict):
                continue
            call = cast(dict[str, object], raw_call)
            if str(call.get("name", "") or "") != "recall_memory":
                continue
            raw_result = str(call.get("result", "") or "").strip()
            if not raw_result:
                continue
            try:
                decoded = json.loads(raw_result)
            except (json.JSONDecodeError, TypeError, ValueError) as _exc:
                _ = _exc
                continue
            if not isinstance(decoded, dict):
                continue
            data = cast(dict[str, object], decoded)
            raw_ids: list[object] = []
            cited_ids = data.get("cited_item_ids")
            if isinstance(cited_ids, list):
                raw_ids.extend(cast(list[object], cited_ids))
            else:
                items_value = data.get("items")
                if isinstance(items_value, list):
                    items = cast(list[object], items_value)
                    for raw_item in items:
                        if isinstance(raw_item, dict):
                            item = cast(dict[str, object], raw_item)
                            raw_ids.append(item.get("id"))
            for raw_id in raw_ids:
                item_id = str(raw_id or "").strip()
                if item_id and item_id not in seen:
                    seen.add(item_id)
                    cited.append(item_id)
    return cited
