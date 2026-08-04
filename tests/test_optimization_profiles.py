from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path
from unittest.mock import AsyncMock
import asyncio
from typing import cast

from agent.config_models import OptimizationConfig
from agent.core.passive_turn import ContextStore
from agent.core.types import ContextBundle
from agent.lifecycle.phase import Phase
from agent.lifecycle.phases.before_turn import (
    BeforeTurnFrame,
    default_before_turn_modules,
)
from agent.lifecycle.types import TurnState
from agent.optimization.profiles import (
    DEFAULT_OPTIMIZATION_PROFILES,
    resolve_optimization_profile,
)
from bus.event_bus import EventBus
from bus.events import InboundMessage
from session.manager import SessionManager
from plugins.status_commands.plugin import UsageCommandModule


def test_builtin_optimization_profiles_expose_first_wave_overrides() -> None:
    assert DEFAULT_OPTIMIZATION_PROFILES["baseline"].simple_fast_path is False
    assert DEFAULT_OPTIMIZATION_PROFILES["simple_fast_path"].simple_fast_path is True
    assert DEFAULT_OPTIMIZATION_PROFILES["context20"].memory_window == 20
    assert DEFAULT_OPTIMIZATION_PROFILES["context12"].memory_window == 12
    assert DEFAULT_OPTIMIZATION_PROFILES["tool_result_limit"].tool_result_limit_chars
    assert DEFAULT_OPTIMIZATION_PROFILES["combined_p1"].simple_fast_path is True


def test_baseline_profile_disables_all_optimizations() -> None:
    resolved = resolve_optimization_profile(
        OptimizationConfig(enabled=True, default_profile="baseline"),
        base_memory_window=24,
        session_metadata={},
        msg_metadata={},
    )

    assert resolved.name == "baseline"
    assert resolved.enabled is False
    assert resolved.simple_fast_path is False
    assert resolved.memory_window == 24
    assert resolved.tool_result_limit_chars is None
    assert resolved.overrides == {}


def test_profile_selection_prefers_message_metadata() -> None:
    resolved = resolve_optimization_profile(
        OptimizationConfig(enabled=True, default_profile="baseline"),
        base_memory_window=24,
        session_metadata={"optimization_profile": "context12"},
        msg_metadata={"optimization_profile": "combined_p1"},
    )

    assert resolved.name == "combined_p1"
    assert resolved.simple_fast_path is True
    assert resolved.memory_window == 20
    assert resolved.tool_result_limit_chars is not None


def test_global_disable_forces_baseline_even_if_session_requests_profile() -> None:
    resolved = resolve_optimization_profile(
        OptimizationConfig(enabled=False, default_profile="combined_p1"),
        base_memory_window=24,
        session_metadata={"optimization_profile": "combined_p1"},
        msg_metadata={},
    )

    assert resolved.name == "baseline"
    assert resolved.enabled is False
    assert resolved.simple_fast_path is False
    assert resolved.memory_window == 24


def test_usage_profile_command_sets_session_metadata(tmp_path: Path) -> None:
    module = UsageCommandModule(
        "status_commands",
        tmp_path / "observe.db",
        app_config=SimpleNamespace(
            optimization=OptimizationConfig(enabled=True, default_profile="baseline")
        ),
    )
    session = SimpleNamespace(metadata={}, key="cli:1")
    reply = module._build_reply(
        SimpleNamespace(
            msg=SimpleNamespace(content="/usage_profile combined_p1"),
            session=session,
            session_key="cli:1",
        )
    )

    assert "combined_p1" in reply
    assert session.metadata["optimization_profile"] == "combined_p1"
    assert session.metadata["usage_experiment_tag"] == "combined_p1"


def test_usage_profile_switch_does_not_leak_to_other_sessions(tmp_path: Path) -> None:
    module = UsageCommandModule(
        "status_commands",
        tmp_path / "observe.db",
        app_config=SimpleNamespace(
            optimization=OptimizationConfig(enabled=True, default_profile="baseline")
        ),
    )
    session_a = SimpleNamespace(metadata={}, key="cli:a")
    session_b = SimpleNamespace(metadata={}, key="cli:b")

    module._build_reply(
        SimpleNamespace(
            msg=SimpleNamespace(content="/usage_profile context12"),
            session=session_a,
            session_key="cli:a",
        )
    )
    reply_b = module._build_reply(
        SimpleNamespace(
            msg=SimpleNamespace(content="/usage_profile"),
            session=session_b,
            session_key="cli:b",
        )
    )

    assert session_a.metadata["optimization_profile"] == "context12"
    assert "current: baseline" in reply_b
    assert session_b.metadata == {}


def test_before_turn_uses_profile_memory_window() -> None:
    session = SimpleNamespace(
        key="cli:1",
        metadata={},
        get_history=lambda max_messages=500: [],
    )
    session_manager = SimpleNamespace(get_or_create=lambda key: session)
    context_store = SimpleNamespace(
        prepare=AsyncMock(return_value=ContextBundle()),
    )
    phase = Phase(
        default_before_turn_modules(
            EventBus(),
            cast(SessionManager, session_manager),
            cast(ContextStore, context_store),
            optimization=OptimizationConfig(enabled=True, default_profile="context12"),
            base_history_window=40,
        ),
        frame_factory=BeforeTurnFrame,
    )
    state = TurnState(
        msg=InboundMessage(channel="cli", sender="u", chat_id="1", content="hi"),
        session_key="cli:1",
        dispatch_outbound=False,
    )

    asyncio.run(phase.run(state))

    assert context_store.prepare.await_args.kwargs["history_window"] == 12
    assert state.extra_metadata["optimization_profile"] == "context12"
