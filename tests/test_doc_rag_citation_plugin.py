from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from agent.config_models import Config
from agent.lifecycle.types import PromptRenderCtx
from plugins.citation.plugin import (
    CitationPlugin,
    append_doc_rag_references,
    extract_doc_rag_citations_from_tool_chain,
    extract_visible_doc_citations,
    validate_doc_rag_citations,
)


def _search_docs_tool_chain(
    *,
    citation: str = "[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]",
    hit_count: int = 1,
) -> list[dict[str, object]]:
    hits: list[dict[str, object]] = []
    if hit_count:
        hits.append(
            {
                "citation": citation,
                "source_path": "my_md/doc_rag_corpus/manual_test.md",
                "heading_path": "Agent Runtime",
            }
        )
    return [
        {
            "text": "",
            "calls": [
                {
                    "name": "search_docs",
                    "result": json.dumps(
                        {
                            "ok": True,
                            "hit_count": hit_count,
                            "hits": hits,
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
        }
    ]


def test_extract_doc_rag_citations_from_search_docs_tool_chain() -> None:
    assert extract_doc_rag_citations_from_tool_chain(_search_docs_tool_chain()) == [
        "[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]"
    ]


def test_extract_doc_rag_citations_from_fetch_doc_chunk_tool_chain() -> None:
    tool_chain = [
        {
            "text": "",
            "calls": [
                {
                    "name": "fetch_doc_chunk",
                    "result": json.dumps(
                        {
                            "ok": True,
                            "chunk": {
                                "citation": (
                                    "[my_md/doc_rag_corpus/manual_test.md > "
                                    "Agent Runtime]"
                                )
                            },
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
        }
    ]

    assert extract_doc_rag_citations_from_tool_chain(tool_chain) == [
        "[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]"
    ]


def test_extract_doc_rag_citations_ignores_no_hits() -> None:
    assert (
        extract_doc_rag_citations_from_tool_chain(_search_docs_tool_chain(hit_count=0))
        == []
    )


def test_extract_doc_rag_citations_ignores_disabled_search_docs() -> None:
    tool_chain = [
        {
            "text": "",
            "calls": [
                {
                    "name": "search_docs",
                    "result": json.dumps(
                        {
                            "ok": False,
                            "error_code": "doc_rag_disabled",
                            "terminal": True,
                            "terminal_scope": "document_rag",
                            "restart_required": True,
                            "restart_target": "agent_service",
                            "current_process_can_enable": False,
                            "retrieval_available_this_turn": False,
                            "hits": [],
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
        }
    ]

    assert extract_doc_rag_citations_from_tool_chain(tool_chain) == []


def test_extract_visible_doc_citations_ignores_memory_protocol() -> None:
    reply = (
        "答案。[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]\n"
        "§cited:[abc123]§"
    )

    assert extract_visible_doc_citations(reply) == [
        "[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]"
    ]


def test_extract_visible_doc_citations_ignores_plain_markdown_reference() -> None:
    reply = "请阅读 [README.md] 和 [notes.markdown]，这不是 Document RAG 引用。"

    assert extract_visible_doc_citations(reply) == []


def test_append_doc_rag_references_when_reply_missing_citation() -> None:
    reply = "Agent runtime 负责管理 agent 的一次运行过程。"
    citations = ["[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]"]

    assert append_doc_rag_references(reply, citations) == (
        "Agent runtime 负责管理 agent 的一次运行过程。\n\n"
        "参考来源：[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]"
    )


def test_append_doc_rag_references_does_not_duplicate_existing_citation() -> None:
    reply = (
        "Agent runtime 负责管理 agent 的一次运行过程。"
        "[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]"
    )
    citations = ["[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]"]

    assert append_doc_rag_references(reply, citations) == reply


def test_validate_doc_rag_citations_removes_fake_and_appends_real() -> None:
    reply, summary = validate_doc_rag_citations(
        "Agent runtime 负责调度。[fake.md > Fake]",
        _search_docs_tool_chain(),
    )

    assert "[fake.md > Fake]" not in reply
    assert "[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]" in reply
    assert summary["removed_fake_citations"] == ["[fake.md > Fake]"]
    assert summary["inserted_fallback"] is True


def test_validate_doc_rag_citations_skips_no_evidence_reply() -> None:
    reply, summary = validate_doc_rag_citations(
        "当前文档知识库中没有足够文档证据回答这个问题。",
        _search_docs_tool_chain(),
    )

    assert "[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]" not in reply
    assert summary["skipped_no_evidence"] is True


def test_validate_doc_rag_citations_does_not_skip_positive_evidence_reply() -> None:
    reply, summary = validate_doc_rag_citations(
        "不是没有证据，而是证据显示 agent runtime 负责调度。",
        _search_docs_tool_chain(),
    )

    assert "[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]" in reply
    assert summary["skipped_no_evidence"] is False
    assert summary["inserted_fallback"] is True


def test_validate_doc_rag_citations_ignores_reply_without_doc_rag_tool_call() -> None:
    reply = "请阅读 [notes.md > local draft]，这是用户自己写的普通文本。"

    cleaned, summary = validate_doc_rag_citations(reply, tool_chain=[])

    assert cleaned == reply
    assert summary["doc_rag_tool_called"] is False
    assert summary["removed_fake_citations"] == []


def test_validate_doc_rag_citations_keeps_plain_markdown_reference() -> None:
    reply = "用户提到 [README.md]，这只是普通 markdown 文件名。"

    cleaned, summary = validate_doc_rag_citations(
        reply,
        tool_chain=_search_docs_tool_chain(hit_count=0),
    )

    assert cleaned == reply
    assert summary["doc_rag_tool_called"] is True
    assert summary["removed_fake_citations"] == []


def test_validate_doc_rag_citations_disabled_removes_fake_without_append() -> None:
    tool_chain = [
        {
            "text": "",
            "calls": [
                {
                    "name": "search_docs",
                    "result": json.dumps(
                        {
                            "ok": False,
                            "error_code": "doc_rag_disabled",
                            "terminal": True,
                            "terminal_scope": "document_rag",
                            "fallback_allowed": False,
                            "restart_required": True,
                            "restart_target": "agent_service",
                            "current_process_can_enable": False,
                            "retrieval_available_this_turn": False,
                            "hits": [],
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
        }
    ]

    cleaned, summary = validate_doc_rag_citations(
        "文档知识库未启用。[fake.md > Fake]",
        tool_chain=tool_chain,
    )

    assert "[fake.md > Fake]" not in cleaned
    assert summary["allowed_citations"] == []
    assert summary["removed_fake_citations"] == ["[fake.md > Fake]"]
    assert summary["inserted_fallback"] is False
    assert summary["doc_rag_tool_called"] is True


@pytest.mark.anyio
async def test_after_reasoning_module_writes_doc_rag_citation_metadata() -> None:
    ctx = SimpleNamespace(
        reply="Agent runtime 负责调度。[fake.md > Fake]",
        tool_chain=tuple(_search_docs_tool_chain()),
        outbound_metadata={},
    )
    modules = CitationPlugin().after_reasoning_modules()
    validator = next(
        module
        for module in modules
        if getattr(module, "slot", "") == "citation.doc_rag_validator"
    )

    await validator.run(SimpleNamespace(slots={"reasoning:ctx": ctx}))

    assert "[fake.md > Fake]" not in ctx.reply
    assert "[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]" in ctx.reply
    assert ctx.outbound_metadata["doc_rag_citation"]["removed_fake_citations"] == [
        "[fake.md > Fake]"
    ]


def _prompt_ctx() -> PromptRenderCtx:
    return PromptRenderCtx(
        session_key="cli:test",
        channel="cli",
        chat_id="test",
        content="hello",
        media=None,
        timestamp=datetime.now(),
        history=[],
        skill_names=None,
        retrieved_memory_block="",
        disabled_sections=set(),
        turn_injection_prompt="",
    )


def _plugin_with_doc_rag_enabled(enabled: bool) -> CitationPlugin:
    cfg = Config(
        provider="deepseek",
        model="deepseek-chat",
        api_key="key",
        system_prompt="test",
    )
    cfg.doc_rag.enabled = enabled
    plugin = CitationPlugin()
    plugin.context = SimpleNamespace(app_config=cfg)  # type: ignore[assignment]
    return plugin


@pytest.mark.anyio
async def test_prompt_protocol_is_injected_only_when_doc_rag_enabled() -> None:
    disabled_ctx = _prompt_ctx()
    enabled_ctx = _prompt_ctx()

    disabled_module = _plugin_with_doc_rag_enabled(False).prompt_render_modules()[0]
    enabled_module = _plugin_with_doc_rag_enabled(True).prompt_render_modules()[0]

    await disabled_module.run(SimpleNamespace(slots={"prompt:ctx": disabled_ctx}))
    await enabled_module.run(SimpleNamespace(slots={"prompt:ctx": enabled_ctx}))

    disabled_names = [section.name for section in disabled_ctx.system_sections_bottom]
    enabled_names = [section.name for section in enabled_ctx.system_sections_bottom]
    assert "citation_protocol" in disabled_names
    assert "citation_protocol" in enabled_names
    assert "doc_rag_citation_protocol" not in disabled_names
    assert "doc_rag_citation_protocol" in enabled_names
