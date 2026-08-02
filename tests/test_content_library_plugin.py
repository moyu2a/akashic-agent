from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agent.plugins.manager import PluginManager
from agent.plugins.registry import plugin_registry
from agent.tools.registry import ToolRegistry
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
