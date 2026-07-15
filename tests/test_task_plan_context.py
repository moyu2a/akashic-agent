from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from agent.context import ContextBuilder
from agent.lifecycle.phase import Phase
from agent.lifecycle.phases.prompt_render import (
    PromptRenderFrame,
    default_prompt_render_modules,
)
from agent.lifecycle.types import PromptRenderInput
from agent.task_plan.context import (
    TaskPlanPromptRenderModule,
    render_task_plan_context,
)
from agent.config_models import TaskExecutionConfig
from agent.task_plan.execution_service import TaskExecutionService
from agent.task_plan.service import TaskPlanService
from agent.task_plan.store import TaskPlanStore
from bootstrap.tools import CoreRuntime
from bus.event_bus import EventBus


def _service(tmp_path: Path) -> TaskPlanService:
    return TaskPlanService(TaskPlanStore(tmp_path / "task_plans.db"))


def _memory() -> Any:
    return SimpleNamespace(
        read_self=lambda: "",
        read_profile=lambda: "",
        read_recent_context=lambda: "",
        get_memory_context=lambda: "",
    )


def test_render_task_plan_context_is_compact(tmp_path: Path) -> None:
    service = _service(tmp_path)
    plan = service.create_task_plan(
        session_key="cli:s1",
        title="Fix RAG",
        steps=["Read logs", "Update docs", "Run tests"],
    )
    service.update_step_status(
        session_key="cli:s1",
        task_id=plan.task_id,
        step_index=1,
        status="completed",
        result_summary="Logs reviewed",
    )
    plan = service.update_step_status(
        session_key="cli:s1",
        task_id=plan.task_id,
        step_index=2,
        status="in_progress",
    )

    rendered = render_task_plan_context(plan, max_chars=500)

    assert "当前任务计划" in rendered
    assert "Fix RAG" in rendered
    assert "current_step" in rendered
    assert "next_step" in rendered
    assert len(rendered) <= 500


def test_render_task_plan_context_distinguishes_spawn_job(tmp_path: Path) -> None:
    service = _service(tmp_path)
    plan = service.create_task_plan(
        session_key="cli:s1",
        title="Fix RAG",
        steps=["Read logs"],
    )

    rendered = render_task_plan_context(plan, max_chars=1200)

    assert "不等同于后台 spawn job" in rendered
    assert "不要自动启动后台任务" in rendered


def test_prompt_renders_only_current_attempt_summary(tmp_path: Path) -> None:
    store = TaskPlanStore(tmp_path / "task_plans.db")
    service = TaskPlanService(store)
    execution = TaskExecutionService(
        store=store,
        plan_service=service,
        runtime_instance_id="runtime-test",
        config=TaskExecutionConfig(),
        clock=lambda: datetime.now(UTC),
    )
    service.create_task_plan(
        session_key="cli:s1",
        title="Fix RAG",
        steps=["Read logs"],
    )
    started = execution.begin_next_step(session_key="cli:s1", request_id="request-1")
    running = execution.start_attempt(
        session_key="cli:s1", attempt_id=started.attempt.attempt_id
    )
    waiting = execution.defer_attempt(
        session_key="cli:s1",
        attempt_id=running.attempt.attempt_id,
        tool_name="write_file",
        requested_arguments={"token": "secret-value"},
        requested_capabilities=("filesystem.write",),
        reason="waiting_authorization",
    )
    plan = service.get_active_task_plan(session_key="cli:s1")

    assert plan is not None
    rendered = render_task_plan_context(plan, execution=waiting)

    assert "Execution:" in rendered
    assert "waiting_authorization" in rendered
    assert "secret-value" not in rendered
    assert "old-attempt-event" not in rendered


@pytest.mark.asyncio
async def test_prompt_render_phase_includes_task_context_when_active_task_exists(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    service.create_task_plan(
        session_key="cli:s1",
        title="Fix RAG",
        steps=["Read logs"],
    )
    phase = Phase(
        default_prompt_render_modules(
            EventBus(),
            ContextBuilder(tmp_path, memory=cast(Any, _memory())),
            plugin_modules=[TaskPlanPromptRenderModule(service)],
        ),
        frame_factory=PromptRenderFrame,
    )

    result = await phase.run(
        PromptRenderInput(
            session_key="cli:s1",
            channel="cli",
            chat_id="s1",
            content="继续",
            media=None,
            timestamp=datetime.now(UTC),
            history=[],
            skill_names=None,
            retrieved_memory_block="",
            disabled_sections=set(),
            turn_injection_prompt="",
        )
    )

    serialized = "\n".join(str(message.get("content", "")) for message in result.messages)
    assert "当前任务计划" in serialized
    assert "Fix RAG" in serialized


@pytest.mark.asyncio
async def test_core_runtime_start_registers_task_plan_prompt_module(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    recorded: list[object] = []
    runtime = CoreRuntime(
        config=cast(Any, SimpleNamespace(peer_agents=[])),
        http_resources=cast(Any, SimpleNamespace()),
        loop=cast(
            Any,
            SimpleNamespace(
                add_prompt_render_plugin_modules=lambda modules: recorded.extend(
                    modules
                ),
            ),
        ),
        bus=cast(Any, SimpleNamespace()),
        event_bus=EventBus(),
        tools=cast(Any, SimpleNamespace()),
        push_tool=cast(Any, SimpleNamespace()),
        session_manager=cast(Any, SimpleNamespace()),
        scheduler=cast(Any, SimpleNamespace()),
        provider=cast(Any, SimpleNamespace()),
        light_provider=None,
        mcp_registry=cast(
            Any,
            SimpleNamespace(start_connect_all_background=lambda: None),
        ),
        memory_runtime=cast(Any, SimpleNamespace()),
        presence=cast(Any, SimpleNamespace()),
        peer_process_manager=None,
        peer_poller=None,
        task_plan_service=service,
        plugin_manager=None,
    )

    await runtime.start()

    assert any(isinstance(module, TaskPlanPromptRenderModule) for module in recorded)
