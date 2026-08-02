import json
from dataclasses import asdict
import re
from typing import Any

from agent.lifecycle.types import BeforeTurnCtx, TurnState
from agent.plugins import Plugin
from agent.plugins.decorators import tool

from .daily_review import build_daily_review_prompt
from .store import ContentLibraryStore

_CTX_SLOT = "session:ctx"
_TIME_PATTERN = re.compile(r"^(\d{1,2}):(\d{2})$")


class ContentLibrary(Plugin):
    name = "content_library"
    version = "0.1.0"

    def __init__(self) -> None:
        self._store: ContentLibraryStore | None = None

    async def initialize(self) -> None:
        workspace = self.context.workspace or self.context.plugin_dir.parent.parent
        self._store = ContentLibraryStore(workspace / "content_library.sqlite3")

    def before_turn_modules(self) -> list[object]:
        return [ContentReviewCommandModule(self)]

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


class ContentReviewCommandModule:
    slot = "content_library.review_commands"
    produces = (_CTX_SLOT,)

    def __init__(self, plugin: ContentLibrary) -> None:
        self._plugin = plugin

    async def run(self, frame) -> object:
        if _CTX_SLOT in frame.slots:
            return frame
        state = frame.input
        command = _normalize_command(state.msg.content)
        if command == "/content_review_now":
            return self._handle_review_now(frame, state)
        if command == "/content_review_daily":
            return await self._handle_review_daily(frame, state)
        return frame

    def _handle_review_now(self, frame, state: TurnState) -> object:
        hours = _hours_arg(state.msg.content, default=24)
        result = self._plugin._require_store().list_recent_items(
            channel=state.msg.channel,
            chat_id=state.msg.chat_id,
            hours=hours,
            limit=20,
            for_push=True,
        )
        frame.slots[_CTX_SLOT] = _abort_ctx(
            state,
            _format_recent_review(result.items, hours),
        )
        return frame

    async def _handle_review_daily(self, frame, state: TurnState) -> object:
        schedule_time = _time_arg(state.msg.content)
        if schedule_time is None:
            frame.slots[_CTX_SLOT] = _abort_ctx(
                state,
                "status: error\nreason: invalid_time\nusage: /content_review_daily HH:MM",
            )
            return frame
        registry = self._plugin.context.tool_registry
        if registry is None or not getattr(registry, "has_tool", lambda name: False)(
            "schedule"
        ):
            frame.slots[_CTX_SLOT] = _abort_ctx(
                state,
                "status: error\nreason: schedule_tool_unavailable",
            )
            return frame
        hour, minute = schedule_time
        result = await registry.execute(
            "schedule",
            {
                "tier": "soft",
                "trigger": "every",
                "when": f"{minute} {hour} * * *",
                "prompt": build_daily_review_prompt(24),
                "channel": state.msg.channel,
                "chat_id": state.msg.chat_id,
                "timezone": "Asia/Shanghai",
                "name": "content_daily_review",
            },
        )
        frame.slots[_CTX_SLOT] = _abort_ctx(state, str(result))
        return frame


def _normalize_command(content: str) -> str:
    parts = (content or "").strip().split(maxsplit=1)
    if not parts:
        return ""
    head = parts[0].lower()
    if "@" in head:
        head = head.split("@", 1)[0]
    return head


def _hours_arg(content: str, *, default: int) -> int:
    parts = (content or "").strip().split()
    if len(parts) < 2:
        return default
    try:
        return max(1, min(int(parts[1]), 24 * 365))
    except ValueError:
        return default


def _time_arg(content: str) -> tuple[int, int] | None:
    parts = (content or "").strip().split()
    if len(parts) < 2:
        return None
    match = _TIME_PATTERN.fullmatch(parts[1])
    if match is None:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    if hour > 23 or minute > 59:
        return None
    return hour, minute


def _format_recent_review(items: list[Any], hours: int) -> str:
    if not items:
        return f"最近 {hours} 小时没有需要回顾的收藏内容。"
    lines = [f"最近 {hours} 小时内容回顾"]
    for index, item in enumerate(items, start=1):
        title = item.title or item.url
        lines.extend(["", f"{index}. [{item.platform}] {title}"])
        if item.tags:
            lines.append(f"   标签: {', '.join(item.tags)}")
        if item.note:
            lines.append(f"   备注: {item.note}")
        if item.summary:
            lines.append(f"   摘要: {item.summary}")
        lines.append(f"   链接: {item.url}")
    return "\n".join(lines)


def _abort_ctx(state: TurnState, reply: str) -> BeforeTurnCtx:
    return BeforeTurnCtx(
        session_key=state.session_key,
        channel=state.msg.channel,
        chat_id=state.msg.chat_id,
        content=state.msg.content,
        timestamp=state.msg.timestamp,
        skill_names=[],
        retrieved_memory_block="",
        retrieval_trace_raw=None,
        history_messages=(),
        abort=True,
        abort_reply=reply,
    )


def _json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
