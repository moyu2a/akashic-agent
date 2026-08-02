import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from agent.plugins import Plugin
from agent.plugins.decorators import tool

from .store import ContentLibraryStore


class ContentLibrary(Plugin):
    name = "content_library"
    version = "0.1.0"

    def __init__(self) -> None:
        self._store: ContentLibraryStore | None = None

    async def initialize(self) -> None:
        workspace = self.context.workspace or self.context.plugin_dir.parent.parent
        self._store = ContentLibraryStore(workspace / "content_library.sqlite3")

    @tool(
        name="save_content_item",
        risk="write",
        always_on=False,
        search_hint="收藏链接 保存视频 内容收藏 记一下",
    )
    async def save_content_item(
        self,
        event: object,
        url: str,
        note: str = "",
        tags: list = None,
        title: str = "",
        summary: str = "",
    ) -> str:
        """保存用户主动分享的内容链接、备注和兴趣标签。"""
        store = self._require_store()
        scope = self._runtime_scope()
        result = store.save_item(
            **scope,
            url=url,
            note=note,
            tags=tags or [],
            title=title,
            summary=summary,
        )
        return _json(
            {
                "status": result.status,
                "item": asdict(result.item),
            }
        )

    @tool(
        name="search_content_items",
        risk="read-only",
        always_on=False,
        search_hint="找收藏过的视频 装修游戏AI内容回顾",
    )
    async def search_content_items(
        self,
        event: object,
        query: str = "",
        platform: str = "",
        tags: list = None,
        time_range: str = "",
        limit: int = 10,
    ) -> str:
        """按关键词、平台、标签或时间搜索用户保存的内容。"""
        store = self._require_store()
        result = store.search_items(
            **self._runtime_scope(),
            query=query,
            platform=platform,
            tags=tags or [],
            time_range=time_range,
            limit=limit,
        )
        return _json(
            {
                "count": result.count,
                "items": [asdict(item) for item in result.items],
            }
        )

    @tool(
        name="list_recent_content_items",
        risk="read-only",
        always_on=False,
        search_hint="最近收藏 每日内容回顾",
    )
    async def list_recent_content_items(
        self,
        event: object,
        hours: int = 24,
        limit: int = 20,
        for_push: bool = False,
    ) -> str:
        """列出最近保存的内容；主动推送时使用 for_push=true。"""
        store = self._require_store()
        result = store.list_recent_items(
            **self._runtime_scope(),
            hours=hours,
            limit=limit,
            for_push=for_push,
        )
        return _json(
            {
                "count": result.count,
                "items": [asdict(item) for item in result.items],
            }
        )

    @tool(
        name="mark_content_feedback",
        risk="write",
        always_on=False,
        search_hint="不感兴趣 少推一点 恢复推送 内容反馈",
    )
    async def mark_content_feedback(
        self,
        event: object,
        item_id: str = "",
        tag: str = "",
        feedback: str = "less_of_this",
    ) -> str:
        """记录单条内容或兴趣标签的主动推送反馈。"""
        store = self._require_store()
        result = store.mark_feedback(
            **self._runtime_scope(),
            item_id=item_id,
            tag=tag,
            feedback=feedback,
        )
        return _json(
            {
                "item": asdict(result.item) if result.item else None,
                "tag_preference": (
                    asdict(result.tag_preference) if result.tag_preference else None
                ),
            }
        )

    def _require_store(self) -> ContentLibraryStore:
        if self._store is None:
            raise RuntimeError("content library is not initialized")
        return self._store

    def _runtime_scope(self) -> dict[str, str]:
        registry = self.context.tool_registry
        context = registry.get_context() if registry is not None else {}
        channel = str(context.get("channel") or "").strip()
        chat_id = str(context.get("chat_id") or "").strip()
        if not channel or not chat_id:
            raise ValueError("content library requires channel and chat_id")
        return {"channel": channel, "chat_id": chat_id}


def _json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
