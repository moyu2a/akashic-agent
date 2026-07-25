from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from core.memory.events import ConsolidationCommitted
from plugins.default_memory.engine import (
    DefaultMemoryEngine,
    _session_key_from_source_ref,
)


class _Runner:
    enabled = True

    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def record_sleep_consolidation_shadow(self, **kwargs: object) -> None:
        self.records.append(dict(kwargs))


class _Store:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.update_calls = 0
        self.delete_calls = 0

    def list_items_for_dashboard(self, **kwargs: object):
        self.calls.append(dict(kwargs))
        return (
            [
                {
                    "id": "m1",
                    "summary": "用户喜欢中文回答",
                    "memory_type": "preference",
                    "status": "active",
                    "source_ref": "cli:local@post_response",
                    "scope_channel": "cli",
                    "scope_chat_id": "local",
                },
                {
                    "id": "m2",
                    "summary": "用户喜欢中文回答",
                    "memory_type": "preference",
                    "status": "active",
                    "source_ref": "cli:local@post_response",
                    "scope_channel": "cli",
                    "scope_chat_id": "local",
                },
            ],
            2,
        )

    def update_item_for_dashboard(self, *args: object, **kwargs: object) -> None:
        self.update_calls += 1

    def delete_item(self, *args: object, **kwargs: object) -> None:
        self.delete_calls += 1


def _event(source_ref: str = "cli:local@post_response") -> ConsolidationCommitted:
    return ConsolidationCommitted(
        history_entry_payloads=[],
        source_ref=source_ref,
        scope_channel="cli",
        scope_chat_id="local",
        conversation="USER: hello",
    )


def test_sleep_consolidation_shadow_records_after_consolidation_without_writes() -> None:
    runner = _Runner()
    store = _Store()
    engine = SimpleNamespace(
        _experiment_runner=runner,
        _sleep_consolidation_shadow_enabled=True,
        _sleep_consolidation_max_items=10,
        _v2_store=store,
    )
    engine._list_shadow_memory_items = (
        DefaultMemoryEngine._list_shadow_memory_items.__get__(
            engine,
            DefaultMemoryEngine,
        )
    )

    DefaultMemoryEngine._record_sleep_consolidation_shadow_from_event(
        engine,
        _event(),
    )

    assert store.calls == [{"status": "active", "page": 1, "page_size": 10}]
    assert store.update_calls == 0
    assert store.delete_calls == 0
    assert len(runner.records) == 1
    record = runner.records[0]
    assert record["session_key"] == "cli:local"
    assert record["turn_id"] == "cli:local@post_response@sleep_consolidation"
    assert record["metrics"]["applied_change_count"] == 0


def test_sleep_consolidation_shadow_disabled_does_not_scan() -> None:
    runner = _Runner()
    store = _Store()
    engine = SimpleNamespace(
        _experiment_runner=runner,
        _sleep_consolidation_shadow_enabled=False,
        _sleep_consolidation_max_items=10,
        _v2_store=store,
    )

    DefaultMemoryEngine._record_sleep_consolidation_shadow_from_event(
        engine,
        _event(),
    )

    assert store.calls == []
    assert runner.records == []


def test_session_key_from_source_ref_is_conservative() -> None:
    assert (
        _session_key_from_source_ref(
            "cli:local@post_response",
            channel="qq",
            chat_id="123",
        )
        == "cli:local"
    )
    assert (
        _session_key_from_source_ref(
            '["telegram:123:abc@message"]',
            channel="telegram",
            chat_id="123",
        )
        == "telegram:123"
    )
    assert (
        _session_key_from_source_ref(
            "cli:local@post_response#h:abc",
            channel="qq",
            chat_id="456",
        )
        == "qq:456"
    )


@pytest.mark.asyncio
async def test_consolidation_event_invokes_sleep_shadow_after_existing_work() -> None:
    engine = SimpleNamespace()
    engine._save_from_consolidation = AsyncMock()
    engine._extract_implicit_long_term = AsyncMock(return_value={})
    engine._save_implicit_long_term = AsyncMock()
    engine._record_sleep_consolidation_shadow_from_event = Mock()

    await DefaultMemoryEngine._on_consolidation_committed(
        engine,
        ConsolidationCommitted(
            history_entry_payloads=[("[2026-07-17 10:00] 用户说喜欢中文", 0)],
            source_ref="cli:local@post_response",
            scope_channel="cli",
            scope_chat_id="local",
            conversation="USER: 我喜欢中文回答",
        ),
    )

    engine._save_from_consolidation.assert_awaited_once()
    engine._extract_implicit_long_term.assert_awaited_once()
    engine._save_implicit_long_term.assert_not_awaited()
    engine._record_sleep_consolidation_shadow_from_event.assert_called_once()
