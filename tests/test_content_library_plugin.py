from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.lifecycle.types import TurnState
from agent.plugins.manager import PluginManager
from agent.plugins.context import PluginContext, PluginKVStore
from agent.plugins.registry import plugin_registry
from agent.tools.base import Tool
from agent.tools.registry import ToolRegistry
from bus.events import InboundMessage
from bus.event_bus import EventBus


@pytest.fixture(autouse=True)
def _clean_plugin_registry():
    plugin_registry._handlers._handlers.clear()
    plugin_registry._classes.clear()
    plugin_registry._instances.clear()
    yield
    plugin_registry._handlers._handlers.clear()
    plugin_registry._classes.clear()
    plugin_registry._instances.clear()


def test_store_upserts_content_by_scope_and_normalized_url(tmp_path: Path) -> None:
    from plugins.content_library.store import ContentLibraryStore

    store = ContentLibraryStore(tmp_path / "content.sqlite3")

    first = store.save_item(
        channel="telegram",
        chat_id="123",
        url="https://www.bilibili.com/video/BV123/?spm_id_from=333",
        title="小户型收纳",
        note="以后装修用",
        tags=["装修", "收纳"],
    )
    second = store.save_item(
        channel="telegram",
        chat_id="123",
        url="https://www.bilibili.com/video/BV123/",
        title="小户型收纳更新",
        note="补充备注",
        tags=["小户型"],
    )

    assert first.status == "created"
    assert second.status == "updated"
    assert second.item.id == first.item.id
    assert second.item.platform == "bilibili"
    assert second.item.tags == ["小户型", "装修", "收纳"]

    other_scope = store.search_items(
        channel="telegram",
        chat_id="other",
        query="装修",
    )
    assert other_scope.count == 0


def test_store_searches_by_query_platform_tags_and_time(tmp_path: Path) -> None:
    from plugins.content_library.store import ContentLibraryStore

    store = ContentLibraryStore(tmp_path / "content.sqlite3")
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    store.save_item(
        channel="cli",
        chat_id="1",
        url="https://www.xiaohongshu.com/explore/abc",
        title="装修灵感",
        note="玄关收纳",
        tags=["装修", "收纳"],
        captured_at=now - timedelta(hours=2),
    )
    store.save_item(
        channel="cli",
        chat_id="1",
        url="https://www.douyin.com/video/123",
        title="游戏攻略",
        note="周末玩",
        tags=["游戏"],
        captured_at=now - timedelta(days=10),
    )

    result = store.search_items(
        channel="cli",
        chat_id="1",
        query="玄关",
        platform="xiaohongshu",
        tags=["装修"],
        time_range="recent_7d",
        limit=10,
        now=now,
    )

    assert result.count == 1
    assert result.items[0].title == "装修灵感"


def test_tag_feedback_escalates_and_push_listing_filters(tmp_path: Path) -> None:
    from plugins.content_library.store import ContentLibraryStore

    store = ContentLibraryStore(tmp_path / "content.sqlite3")
    now = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    store.save_item(
        channel="cli",
        chat_id="1",
        url="https://www.bilibili.com/video/BV111",
        title="装修 A",
        tags=["装修"],
        captured_at=now - timedelta(hours=1),
    )
    store.save_item(
        channel="cli",
        chat_id="1",
        url="https://www.bilibili.com/video/BV222",
        title="装修 B",
        tags=["装修"],
        captured_at=now - timedelta(hours=1),
    )

    assert (
        store.mark_feedback(
            channel="cli",
            chat_id="1",
            tag="装修",
            feedback="less_of_this",
        ).tag_preference.push_state
        == "deprioritized"
    )
    assert (
        store.mark_feedback(
            channel="cli",
            chat_id="1",
            tag="装修",
            feedback="less_of_this",
        ).tag_preference.push_state
        == "suppressed"
    )

    assert (
        store.list_recent_items(
            channel="cli",
            chat_id="1",
            hours=24,
            for_push=False,
            now=now,
        ).count
        == 2
    )
    assert (
        store.list_recent_items(
            channel="cli",
            chat_id="1",
            hours=24,
            for_push=True,
            now=now,
        ).count
        == 0
    )

    muted = store.mark_feedback(
        channel="cli",
        chat_id="1",
        tag="装修",
        feedback="less_of_this",
    )
    assert muted.tag_preference.push_state == "muted"
    restored = store.mark_feedback(
        channel="cli",
        chat_id="1",
        tag="装修",
        feedback="restore",
    )
    assert restored.tag_preference.push_state == "normal"


def test_daily_review_prompt_requires_push_safe_recent_items() -> None:
    from plugins.content_library.daily_review import build_daily_review_prompt

    prompt = build_daily_review_prompt()

    assert "list_recent_content_items(hours=24, for_push=true)" in prompt
    assert "count=0" in prompt
    assert "不要调用 message_push" in prompt


class RecordingScheduleTool(Tool):
    name = "schedule"
    description = "record schedule calls"
    parameters = {
        "type": "object",
        "properties": {},
    }

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def execute(self, **kwargs):
        self.calls.append(dict(kwargs))
        return "已注册定时任务 「content_daily_review」"


def _content_plugin_context(
    *,
    tmp_path: Path,
    registry: ToolRegistry | None = None,
) -> PluginContext:
    return PluginContext(
        event_bus=EventBus(),
        tool_registry=registry or ToolRegistry(),
        plugin_id="content_library",
        plugin_dir=tmp_path / "plugins" / "content_library",
        kv_store=PluginKVStore(tmp_path / "kv.json"),
        workspace=tmp_path,
    )


async def _run_content_command(module, content: str):
    msg = InboundMessage(
        channel="cli",
        sender="user",
        chat_id="local",
        content=content,
        timestamp=datetime(2026, 8, 2, 21, 0, tzinfo=timezone.utc),
    )
    state = TurnState(msg=msg, session_key="cli:local", dispatch_outbound=True)
    frame = SimpleNamespace(slots={}, input=state)
    await module.run(frame)
    ctx = frame.slots["session:ctx"]
    assert ctx.abort is True
    return ctx


@pytest.mark.asyncio
async def test_content_review_now_command_summarizes_recent_push_safe_items(
    tmp_path: Path,
) -> None:
    from plugins.content_library.plugin import ContentLibrary

    plugin = ContentLibrary()
    plugin.context = PluginContext(
        event_bus=EventBus(),
        tool_registry=ToolRegistry(),
        plugin_id="content_library",
        plugin_dir=tmp_path / "plugins" / "content_library",
        kv_store=PluginKVStore(tmp_path / "kv.json"),
        workspace=tmp_path,
    )
    await plugin.initialize()
    store = plugin._require_store()
    store.save_item(
        channel="cli",
        chat_id="local",
        url="https://www.bilibili.com/video/BV123/",
        title="英雄联盟 TheShy 视频",
        note="晚点看",
        tags=["英雄联盟", "TheShy"],
        captured_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    module = plugin.before_turn_modules()[0]

    ctx = await _run_content_command(module, "/content_review_now 24")

    assert "最近 24 小时内容回顾" in ctx.abort_reply
    assert "英雄联盟 TheShy 视频" in ctx.abort_reply
    assert "bilibili" in ctx.abort_reply
    assert "晚点看" in ctx.abort_reply
    assert "https://bilibili.com/video/BV123" in ctx.abort_reply


@pytest.mark.asyncio
async def test_content_review_daily_command_registers_soft_schedule(
    tmp_path: Path,
) -> None:
    from plugins.content_library.plugin import ContentLibrary

    registry = ToolRegistry()
    schedule = RecordingScheduleTool()
    registry.register(schedule, risk="write")
    registry.set_context(channel="cli", chat_id="local", session_key="cli:local")
    plugin = ContentLibrary()
    plugin.context = PluginContext(
        event_bus=EventBus(),
        tool_registry=registry,
        plugin_id="content_library",
        plugin_dir=tmp_path / "plugins" / "content_library",
        kv_store=PluginKVStore(tmp_path / "kv.json"),
        workspace=tmp_path,
    )
    await plugin.initialize()
    module = plugin.before_turn_modules()[0]

    ctx = await _run_content_command(module, "/content_review_daily 21:30")

    assert "已注册定时任务" in ctx.abort_reply
    assert schedule.calls == [
        {
            "tier": "soft",
            "trigger": "every",
            "when": "30 21 * * *",
            "prompt": (
                "这是个人内容收藏每日回顾任务。\n"
                "必须先调用 list_recent_content_items(hours=24, for_push=true)。\n"
                "如果返回 count=0，直接返回空文本，不要发送或编造内容。\n"
                "如果有内容，只根据工具返回的事实生成简短中文摘要：按主题分组，"
                "列出平台、标题、备注和链接；不要声称看过视频本体。\n"
                "不要调用 message_push；当前任务由调度器负责发送最终文本。\n"
                "不要因为本次摘要自动写入长期记忆。"
            ),
            "channel": "cli",
            "chat_id": "local",
            "timezone": "Asia/Shanghai",
            "name": "content_daily_review",
            "session_key": "cli:local",
        }
    ]


@pytest.mark.asyncio
async def test_content_review_status_reports_missing_schedule(tmp_path: Path) -> None:
    from agent.scheduler import LatencyTracker, SchedulerService
    from agent.tools.message_push import MessagePushTool
    from agent.tools.schedule import ListSchedulesTool
    from plugins.content_library.plugin import ContentLibrary

    scheduler = SchedulerService(
        store_path=tmp_path / "schedules.json",
        push_tool=MessagePushTool(),
        tracker=LatencyTracker(default=25.0),
    )
    registry = ToolRegistry()
    registry.register(ListSchedulesTool(scheduler), risk="read-only")
    plugin = ContentLibrary()
    plugin.context = _content_plugin_context(tmp_path=tmp_path, registry=registry)
    await plugin.initialize()
    module = plugin.before_turn_modules()[0]

    ctx = await _run_content_command(module, "/content_review_status")

    assert "内容回顾状态" in ctx.abort_reply
    assert "status: not_scheduled" in ctx.abort_reply
    assert "/content_review_daily HH:MM" in ctx.abort_reply


@pytest.mark.asyncio
async def test_content_review_status_reports_schedule_and_recent_count(
    tmp_path: Path,
) -> None:
    from agent.scheduler import LatencyTracker, SchedulerService
    from agent.tools.message_push import MessagePushTool
    from agent.tools.schedule import ListSchedulesTool
    from plugins.content_library.plugin import ContentLibrary
    from tests.conftest import make_job

    scheduler = SchedulerService(
        store_path=tmp_path / "schedules.json",
        push_tool=MessagePushTool(),
        tracker=LatencyTracker(default=25.0),
    )
    target = make_job(
        name="content_daily_review",
        tier="soft",
        channel="cli",
        chat_id="local",
        prompt="内容回顾",
        timezone_="Asia/Shanghai",
    )
    target.run_count = 1
    target.last_status = "pushed"
    target.last_push_result = "文本已发送"
    target.last_content_preview = "最近你保存了 1 条内容"
    other = make_job(
        name="content_daily_review",
        tier="soft",
        channel="telegram",
        chat_id="other",
        prompt="内容回顾",
    )
    other.last_status = "failed"
    other.last_error = "boom"
    scheduler._jobs[target.id] = target
    scheduler._jobs[other.id] = other

    registry = ToolRegistry()
    registry.register(ListSchedulesTool(scheduler), risk="read-only")
    plugin = ContentLibrary()
    plugin.context = _content_plugin_context(tmp_path=tmp_path, registry=registry)
    await plugin.initialize()
    store = plugin._require_store()
    store.save_item(
        channel="cli",
        chat_id="local",
        url="https://www.bilibili.com/video/BV123/",
        title="英雄联盟 TheShy 视频",
        tags=["英雄联盟"],
        captured_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    module = plugin.before_turn_modules()[0]

    ctx = await _run_content_command(module, "/content_review_status")

    assert "内容回顾状态" in ctx.abort_reply
    assert "content_daily_review" in ctx.abort_reply
    assert "最近: pushed" in ctx.abort_reply
    assert "文本已发送" in ctx.abort_reply
    assert "最近你保存了 1 条内容" in ctx.abort_reply
    assert "最近 24 小时可回顾内容: 1 条" in ctx.abort_reply
    assert "boom" not in ctx.abort_reply


@pytest.mark.asyncio
async def test_content_library_plugin_registers_tools_with_risks(
    tmp_path: Path,
) -> None:
    plugin_root = tmp_path / "plugins"
    shutil.copytree(
        Path(__file__).parents[1] / "plugins" / "content_library",
        plugin_root / "content_library",
    )
    tools = ToolRegistry()
    manager = PluginManager(
        plugin_dirs=[plugin_root],
        event_bus=EventBus(),
        tool_registry=tools,
        workspace=tmp_path,
    )

    await manager.load_all()

    assert {
        "save_content_item",
        "search_content_items",
        "list_recent_content_items",
        "mark_content_feedback",
    } <= tools.get_registered_names()
    risks = tools.get_risks_by_name()
    assert risks["save_content_item"] == "write"
    assert risks["mark_content_feedback"] == "write"
    assert risks["search_content_items"] == "read-only"
    assert risks["list_recent_content_items"] == "read-only"
    schemas = tools.get_schemas(
        {"save_content_item", "search_content_items", "list_recent_content_items"}
    )
    schema_by_name = {item["function"]["name"]: item["function"] for item in schemas}
    assert (
        schema_by_name["save_content_item"]["parameters"]["properties"]["tags"]["type"]
        == "array"
    )
    assert (
        schema_by_name["list_recent_content_items"]["parameters"]["properties"][
            "for_push"
        ]["type"]
        == "boolean"
    )


@pytest.mark.asyncio
async def test_content_library_plugin_tools_use_runtime_scope(tmp_path: Path) -> None:
    plugin_root = tmp_path / "plugins"
    shutil.copytree(
        Path(__file__).parents[1] / "plugins" / "content_library",
        plugin_root / "content_library",
    )
    tools = ToolRegistry()
    tools.set_context(channel="telegram", chat_id="123", session_key="telegram:123")
    manager = PluginManager(
        plugin_dirs=[plugin_root],
        event_bus=EventBus(),
        tool_registry=tools,
        workspace=tmp_path,
    )
    await manager.load_all()

    saved = json.loads(
        await tools.execute(
            "save_content_item",
            {
                "url": "https://www.bilibili.com/video/BV999",
                "title": "AI 视频",
                "note": "以后看",
                "tags": ["AI"],
                "channel": "telegram",
                "chat_id": "other",
            },
        )
    )
    assert saved["item"]["id"]

    same_scope = json.loads(
        await tools.execute("search_content_items", {"query": "AI"})
    )
    assert same_scope["count"] == 1

    tools.set_context(channel="telegram", chat_id="other", session_key="telegram:other")
    other_scope = json.loads(
        await tools.execute("search_content_items", {"query": "AI"})
    )
    assert other_scope["count"] == 0
