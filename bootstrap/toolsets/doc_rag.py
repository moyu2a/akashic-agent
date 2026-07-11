from __future__ import annotations

from agent.tools.doc_rag import FetchDocChunkTool, SearchDocsTool
from agent.tools.registry import ToolRegistry
from bootstrap.toolsets.protocol import (
    ToolsetDeps,
    ToolsetProvider,
    build_registration_result,
)


class DocRagToolsetProvider(ToolsetProvider):
    def register(self, registry: ToolRegistry, deps: ToolsetDeps):
        before = set(registry._tools.keys())
        if deps.config is None:
            raise RuntimeError("DocRagToolsetProvider requires config")
        registry.register(
            SearchDocsTool(deps.config),
            risk="read-only",
            search_hint="文档知识库 document rag markdown 检索 search docs citation",
        )
        registry.register(
            FetchDocChunkTool(deps.config),
            risk="read-only",
            search_hint="文档片段 chunk 原文 fetch content citation 展开证据",
        )
        return build_registration_result(
            registry=registry,
            source_name="doc_rag",
            before=before,
        )
