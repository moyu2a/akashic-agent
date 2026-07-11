from __future__ import annotations

from pathlib import Path

from agent.config_models import Config, WiringConfig
from agent.tools.doc_rag import FetchDocChunkTool, SearchDocsTool
from agent.tools.registry import ToolRegistry
from bootstrap.toolsets.doc_rag import DocRagToolsetProvider
from bootstrap.toolsets.protocol import ToolsetDeps
from bootstrap.wiring import resolve_toolset_provider


def _config(enabled: bool = False) -> Config:
    cfg = Config(
        provider="deepseek",
        model="deepseek-chat",
        api_key="main-key",
        base_url="https://main.example/v1",
        system_prompt="test",
    )
    cfg.doc_rag.enabled = enabled
    return cfg


def test_doc_rag_toolset_registers_document_tools_even_when_disabled(tmp_path: Path):
    registry = ToolRegistry()

    result = DocRagToolsetProvider().register(
        registry,
        ToolsetDeps(config=_config(enabled=False), workspace=tmp_path),
    )

    assert result.source_name == "doc_rag"
    assert result.tool_names == ["fetch_doc_chunk", "search_docs"]
    assert result.always_on_names == []
    assert isinstance(registry.get_tool("search_docs"), SearchDocsTool)
    assert isinstance(registry.get_tool("fetch_doc_chunk"), FetchDocChunkTool)
    assert registry.get_always_on_names().isdisjoint({"search_docs", "fetch_doc_chunk"})

    search_tool = registry.get_tool("search_docs")
    fetch_tool = registry.get_tool("fetch_doc_chunk")
    assert search_tool is not None
    assert fetch_tool is not None
    assert "fetch_doc_chunk" in search_tool.description
    assert "citation" in search_tool.description
    assert "不要用于查询用户长期记忆" in search_tool.description
    assert "doc_rag_disabled" in search_tool.description
    assert "本地文件读取" in search_tool.description
    assert "doc_rag.enabled=true" in search_tool.description
    assert "重启 Agent 服务" in search_tool.description
    assert "优先于 read_file" in fetch_tool.description
    assert "citation" in fetch_tool.description
    assert "doc_rag_disabled" in fetch_tool.description
    assert "本地文件读取" in fetch_tool.description
    assert "doc_rag.enabled=true" in fetch_tool.description
    assert "重启 Agent 服务" in fetch_tool.description

    docs = {doc.name: doc for doc in registry.get_documents()}
    assert docs["search_docs"].search_hint == (
        "文档知识库 document rag markdown 检索 search docs citation"
    )
    assert docs["fetch_doc_chunk"].search_hint == (
        "文档片段 chunk 原文 fetch content citation 展开证据"
    )


def test_resolve_toolset_provider_supports_doc_rag():
    provider = resolve_toolset_provider("doc_rag")

    assert isinstance(provider, DocRagToolsetProvider)


def test_default_wiring_includes_doc_rag_toolset():
    assert "doc_rag" in WiringConfig().toolsets
