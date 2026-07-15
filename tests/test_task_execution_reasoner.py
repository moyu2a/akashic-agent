from __future__ import annotations

import asyncio
import importlib
import inspect
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from agent.config_models import TaskExecutionConfig
from agent.core.passive_turn import DefaultReasoner
from agent.core.runtime_support import LLMServices, ToolDiscoveryState
from agent.core.types import ContextRenderResult, ContextRequest
from agent.looping.ports import LLMConfig
from agent.provider import ContentSafetyError, ContextLengthError, LLMResponse, ToolCall
from agent.task_plan.execution_models import RuntimeToolEvent
from agent.task_plan.execution_service import (
    TaskExecutionConflictError,
    TaskExecutionService,
)
from agent.task_plan.orchestrator import TaskExecutionOrchestrator
from agent.task_plan.service import TaskPlanService
from agent.task_plan.store import TaskPlanStore
from agent.tools.base import Tool, ToolResult
from agent.tools.registry import ToolRegistry
from agent.tools.task_execution import (
    AbortTaskStepExecutionTool,
    BeginTaskStepExecutionTool,
    FinishTaskStepExecutionTool,
    InspectTaskExecutionTool,
    RequestTaskStepAuthorizationTool,
)
from agent.tools.task_plan import (
    CreateTaskPlanTool,
    InspectTaskPlanTool,
    UpdateTaskStepTool,
)
from agent.tools.tool_search import ToolSearchTool
from bus.events import InboundMessage


def tool_call(name: str, arguments: dict[str, object]) -> LLMResponse:
    return LLMResponse(
        content="",
        tool_calls=[ToolCall(f"call-{name}", name, dict(arguments))],
    )


def tool_call_batch(*calls: tuple[str, dict[str, object]]) -> LLMResponse:
    return LLMResponse(
        content="",
        tool_calls=[
            ToolCall(f"call-{index}-{name}", name, dict(arguments))
            for index, (name, arguments) in enumerate(calls)
        ],
    )


def final_reply(content: str) -> LLMResponse:
    return LLMResponse(content=content, tool_calls=[])


class _Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 7, 15, 8, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: int) -> None:
        self.value += timedelta(seconds=seconds)


class _Provider:
    def __init__(self) -> None:
        self.responses: list[LLMResponse | BaseException] = []
        self.calls: list[dict[str, Any]] = []

    async def chat(self, **kwargs: Any) -> LLMResponse:
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("provider.chat called more than expected")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


class _WorkTool(Tool):
    name = "fixture_work"
    description = "fixture work tool"
    parameters = {"type": "object", "properties": {}, "required": []}

    def __init__(
        self,
        name: str,
        calls: list[dict[str, Any]],
        *,
        clock: _Clock | None = None,
        advance_seconds: int = 0,
    ) -> None:
        self.name = name
        self._calls = calls
        self._clock = clock
        self._advance_seconds = advance_seconds

    async def execute(self, **kwargs: Any) -> ToolResult:
        self._calls.append(dict(kwargs))
        if self._clock is not None and self._advance_seconds:
            self._clock.advance(self._advance_seconds)
        return ToolResult(
            ok=True,
            text=json.dumps({"ok": True, "tool": self.name}, ensure_ascii=False),
        )


class _FaultInjectingExecutionService(TaskExecutionService):
    fail_next_defer = False

    def defer_attempt(self, **kwargs: Any):
        if self.fail_next_defer:
            self.fail_next_defer = False
            raise TaskExecutionConflictError("injected defer persistence failure")
        return super().defer_attempt(**kwargs)


class ReasonerExecutionFixture:
    session_key = "cli:execution"
    runtime_instance_id = "runtime-task-9-test"

    def __init__(
        self,
        tmp_path: Path,
        *,
        enabled: bool = True,
        provider_present: bool = True,
        lease_expiring_read: bool = False,
    ) -> None:
        self.clock = _Clock()
        self.config = TaskExecutionConfig(enabled=enabled, lease_seconds=30)
        self.store = TaskPlanStore(tmp_path / "task_execution_reasoner.db")
        self.plan_service = TaskPlanService(self.store)
        self.execution_service = _FaultInjectingExecutionService(
            self.store,
            self.plan_service,
            runtime_instance_id=self.runtime_instance_id,
            config=self.config,
            clock=self.clock,
        )
        self.plan = self.plan_service.create_task_plan(
            session_key=self.session_key,
            title="Task 9 execution",
            steps=["Read README", "Summarize result"],
        )
        self.llm = _Provider()
        self.discovery = ToolDiscoveryState()
        self.executed_work_tools: list[str] = []
        self.read_executor_calls: list[dict[str, Any]] = []
        self.write_executor_calls: list[dict[str, Any]] = []
        self.protocol_correction_count = 0
        self.fail_after_claim_commit = False
        self.last_request_id = ""
        self._attempt_count_before_replay = 0

        registry = ToolRegistry()
        registry.register(ToolSearchTool(registry), always_on=True, risk="read-only")
        registry.register(
            CreateTaskPlanTool(self.plan_service), risk="write", non_lru=True
        )
        registry.register(
            UpdateTaskStepTool(self.plan_service), risk="write", non_lru=True
        )
        registry.register(
            InspectTaskPlanTool(self.plan_service), risk="read-only", non_lru=True
        )
        orchestrator = TaskExecutionOrchestrator(self.execution_service)
        registry.register(
            BeginTaskStepExecutionTool(orchestrator), risk="write", non_lru=True
        )
        registry.register(
            FinishTaskStepExecutionTool(self.execution_service),
            risk="write",
            non_lru=True,
        )
        registry.register(
            RequestTaskStepAuthorizationTool(self.execution_service),
            risk="write",
            non_lru=True,
        )
        registry.register(
            InspectTaskExecutionTool(self.execution_service),
            risk="read-only",
            non_lru=True,
        )
        registry.register(
            AbortTaskStepExecutionTool(self.execution_service),
            risk="write",
            non_lru=True,
        )
        read_tool = _WorkTool(
            "read_file",
            self.read_executor_calls,
            clock=self.clock if lease_expiring_read else None,
            advance_seconds=31 if lease_expiring_read else 0,
        )
        registry.register(read_tool, always_on=True, risk="read-only")
        registry.register(
            _WorkTool("write_file", self.write_executor_calls),
            always_on=True,
            risk="write",
        )
        self.registry = registry

        def render(request: ContextRequest, **_kwargs: object) -> ContextRenderResult:
            return ContextRenderResult(
                system_prompt="",
                messages=[{"role": "user", "content": request.current_message}],
            )

        async def save_async(*_args: object, **_kwargs: object) -> None:
            return None

        coordinator = None
        try:
            runtime_module = importlib.import_module(
                "agent.task_plan.execution_runtime"
            )
        except ModuleNotFoundError:
            runtime_module = None
        if runtime_module is not None:
            coordinator = runtime_module.TaskExecutionRuntimeCoordinator(
                self.execution_service if provider_present else None,
                config=self.config,
                runtime_instance_id=self.runtime_instance_id,
                clock=self.clock,
            )

        kwargs: dict[str, object] = {}
        if (
            "task_execution_coordinator"
            in inspect.signature(DefaultReasoner).parameters
        ):
            kwargs["task_execution_coordinator"] = coordinator
        self.reasoner = DefaultReasoner(
            llm=cast(Any, LLMServices(provider=self.llm, light_provider=self.llm)),
            llm_config=LLMConfig(model="fixture", max_iterations=8, max_tokens=256),
            tools=registry,
            discovery=self.discovery,
            tool_search_enabled=True,
            memory_window=10,
            context=cast(Any, SimpleNamespace(render=render)),
            session_manager=cast(Any, SimpleNamespace(save_async=save_async)),
            task_plan_service=self.plan_service,
            **cast(dict[str, Any], kwargs),
        )
        self.coordinator = coordinator
        self.session = SimpleNamespace(
            key=self.session_key,
            messages=[],
            metadata={},
            get_history=lambda max_messages=40, *, start_index=None: [],
            last_consolidated=0,
        )

    async def run_turn(
        self,
        content: str,
        *,
        request_id: str | None = None,
    ):
        msg = InboundMessage(
            channel="cli",
            sender="tester",
            chat_id="execution",
            content=content,
            timestamp=self.clock(),
            metadata=(
                {"_transport_request_id": request_id} if request_id is not None else {}
            ),
        )
        if self.fail_after_claim_commit and self.coordinator is not None:
            original = self.coordinator.after_tool_call
            failed = False

            async def fail_after_claim(*args: Any, **kwargs: Any):
                nonlocal failed
                if (
                    not failed
                    and kwargs.get("tool_name") == "begin_task_step_execution"
                ):
                    failed = True
                    raise RuntimeError("after claim commit")
                return await original(*args, **kwargs)

            self.coordinator.after_tool_call = fail_after_claim
        try:
            result = await self.reasoner.run_turn(
                msg=msg,
                session=cast(Any, self.session),
            )
        finally:
            self.last_request_id = str(
                msg.metadata.get("_task_execution_request_id") or ""
            )
        if self.coordinator is not None:
            self.protocol_correction_count = getattr(
                self.coordinator, "protocol_correction_count", 0
            )
        self.executed_work_tools = [
            *("read_file" for _ in self.read_executor_calls),
            *("write_file" for _ in self.write_executor_calls),
        ]
        return result

    def step_status(self, index: int) -> str:
        plan = self.plan_service.require_owned_task_plan(
            session_key=self.session_key,
            task_id=self.plan.task_id,
        )
        return plan.steps[index - 1].status

    def attempts(self):
        return self.store.list_execution_attempts(self.plan.task_id)

    def latest_attempt(self):
        attempts = self.attempts()
        assert attempts
        return attempts[-1]

    def attempt_status(self) -> str:
        return self.latest_attempt().status

    def attempt_reason(self) -> str:
        return self.latest_attempt().terminal_reason.split(";", 1)[0]

    def active_attempt_count(self) -> int:
        return sum(
            attempt.status in {"pending", "running", "waiting_authorization"}
            for attempt in self.attempts()
        )

    def lru_names(self) -> set[str]:
        return self.discovery.get_preloaded(self.session_key)

    def attempt_for_request(self, request_id: str | None = None):
        target = request_id or self.last_request_id
        attempt = self.store.get_execution_attempt_by_request(
            session_key=self.session_key,
            request_id=target,
        )
        assert attempt is not None
        return attempt

    @property
    def new_attempt_count(self) -> int:
        return len(self.attempts()) - self._attempt_count_before_replay

    def complete_final_step(self) -> tuple[str, str]:
        first = self.plan.steps[0]
        self.plan_service.update_step_status(
            session_key=self.session_key,
            task_id=self.plan.task_id,
            step_id=first.step_id,
            status="completed",
            result_summary="already complete",
        )
        request_id = "terminal-replay-request"
        claimed = self.execution_service.begin_next_step(
            session_key=self.session_key,
            request_id=request_id,
        )
        self.execution_service.start_attempt(
            session_key=self.session_key,
            attempt_id=claimed.attempt.attempt_id,
        )
        self.execution_service.record_tool_event(
            session_key=self.session_key,
            attempt_id=claimed.attempt.attempt_id,
            event=RuntimeToolEvent(
                event_type="tool_finished",
                tool_name="read_file",
                tool_call_id="terminal-work",
                source_turn_id=None,
                tool_risk="read-only",
                tool_capabilities=(),
                counts_as_work=True,
                invoker_reached=True,
                invoker_succeeded=True,
                execution_status="success",
                result_ok=True,
                error_code="",
                arguments_hash="terminal-hash",
                result_preview="done",
            ),
        )
        self.execution_service.finish_attempt(
            session_key=self.session_key,
            attempt_id=claimed.attempt.attempt_id,
            success=True,
            result_summary="final step complete",
        )
        return request_id, claimed.attempt.attempt_id

    async def replay_turn(self, request_id: str):
        self._attempt_count_before_replay = len(self.attempts())
        self.llm.responses = [final_reply("Replayed terminal execution")]
        return await self.run_turn("继续执行下一步", request_id=request_id)

    async def run_exit_scenario(self, kind: str) -> None:
        if kind == "provider_error":
            self.llm.responses = [
                tool_call("begin_task_step_execution", {}),
                RuntimeError("provider unavailable"),
            ]
        elif kind == "timeout":
            self.llm.responses = [
                tool_call("begin_task_step_execution", {}),
                asyncio.TimeoutError(),
            ]
        elif kind == "cancelled":
            self.llm.responses = [
                tool_call("begin_task_step_execution", {}),
                asyncio.CancelledError(),
            ]
        elif kind == "context_error_after_begin":
            self.llm.responses = [
                tool_call("begin_task_step_execution", {}),
                ContextLengthError("context too long"),
            ]
        elif kind == "safety_error_after_begin":
            self.llm.responses = [
                tool_call("begin_task_step_execution", {}),
                ContentSafetyError("unsafe"),
            ]
        elif kind == "hook_error":
            self.llm.responses = [
                tool_call("begin_task_step_execution", {}),
                tool_call("read_file", {"path": "README.md"}),
            ]
            if self.coordinator is not None:
                original = self.coordinator.after_tool_call

                async def hook_fault(*args: Any, **kwargs: Any):
                    if kwargs.get("tool_name") == "read_file":
                        raise RuntimeError("hook failed")
                    return await original(*args, **kwargs)

                self.coordinator.after_tool_call = hook_fault
        elif kind == "max_iterations":
            self.reasoner._llm_config.max_iterations = 2
            self.llm.responses = [
                tool_call("begin_task_step_execution", {}),
                tool_call("read_file", {"path": "README.md"}),
                final_reply("summary"),
            ]
        elif kind == "second_bare_final":
            self.llm.responses = [
                tool_call("begin_task_step_execution", {}),
                tool_call("read_file", {"path": "README.md"}),
                final_reply("bare one"),
                final_reply("bare two"),
                final_reply("failed cleanly"),
            ]
        else:
            raise AssertionError(f"unknown exit scenario: {kind}")
        try:
            await self.run_turn("继续执行下一步")
        except BaseException as exc:
            expected = (
                RuntimeError,
                asyncio.TimeoutError,
                asyncio.CancelledError,
                ContextLengthError,
                ContentSafetyError,
            )
            if not isinstance(exc, expected):
                raise


@pytest.fixture
def reasoner_fixture(tmp_path: Path) -> ReasonerExecutionFixture:
    return ReasonerExecutionFixture(tmp_path)


@pytest.mark.asyncio
async def test_read_only_execution_is_begin_work_finish_final(reasoner_fixture) -> None:
    reasoner_fixture.llm.responses = [
        tool_call("begin_task_step_execution", {}),
        tool_call("read_file", {"path": "README.md"}),
        tool_call(
            "finish_task_step_execution",
            {"success": True, "result_summary": "Read README title"},
        ),
        final_reply("Step 1 completed"),
    ]
    result = await reasoner_fixture.run_turn("继续执行下一步")
    assert result.tools_used == [
        "begin_task_step_execution",
        "read_file",
        "finish_task_step_execution",
    ]
    assert reasoner_fixture.step_status(1) == "completed"
    assert reasoner_fixture.step_status(2) == "pending"
    assert reasoner_fixture.lru_names() == set()


@pytest.mark.asyncio
async def test_write_proposal_defers_without_executor(reasoner_fixture) -> None:
    reasoner_fixture.llm.responses = [
        tool_call("begin_task_step_execution", {}),
        tool_call("write_file", {"path": "x.txt", "content": "x"}),
        final_reply("Waiting for authorization"),
    ]
    result = await reasoner_fixture.run_turn("继续执行下一步")
    assert "write_file" not in reasoner_fixture.executed_work_tools
    assert reasoner_fixture.attempt_status() == "waiting_authorization"
    assert result.context_retry["task_execution"]["reason"] == (
        "task_execution_authorization_required"
    )


@pytest.mark.asyncio
async def test_bare_final_gets_one_correction_then_fails_attempt(
    reasoner_fixture,
) -> None:
    reasoner_fixture.llm.responses = [
        tool_call("begin_task_step_execution", {}),
        tool_call("read_file", {"path": "README.md"}),
        final_reply("I read it"),
        final_reply("Done"),
        final_reply("Step failed because finish was missing"),
    ]
    await reasoner_fixture.run_turn("继续执行下一步")
    assert reasoner_fixture.attempt_status() == "failed"
    assert reasoner_fixture.attempt_reason() == "protocol_finish_missing"
    assert reasoner_fixture.protocol_correction_count == 1


@pytest.mark.asyncio
async def test_provider_error_blocks_and_releases_step(reasoner_fixture) -> None:
    reasoner_fixture.llm.responses = [
        tool_call("begin_task_step_execution", {}),
        RuntimeError("provider unavailable"),
    ]
    with pytest.raises(RuntimeError, match="provider unavailable"):
        await reasoner_fixture.run_turn("继续执行下一步")
    assert reasoner_fixture.attempt_status() == "blocked"
    assert reasoner_fixture.step_status(1) == "pending"


@pytest.mark.asyncio
async def test_defer_persistence_failure_never_executes_write(reasoner_fixture) -> None:
    reasoner_fixture.execution_service.fail_next_defer = True
    reasoner_fixture.llm.responses = [
        tool_call("begin_task_step_execution", {}),
        tool_call("write_file", {"path": "x.txt", "content": "x"}),
        final_reply("Execution was blocked"),
    ]
    result = await reasoner_fixture.run_turn("继续执行下一步")
    assert reasoner_fixture.write_executor_calls == []
    assert reasoner_fixture.attempt_status() == "blocked"
    assert result.tool_chain[1]["calls"][0]["status"] == (
        "blocked_by_task_execution_persistence"
    )
    assert result.context_retry["task_execution"]["reason"] == (
        "defer_persistence_failed"
    )


@pytest.mark.asyncio
async def test_fault_after_claim_commit_is_recovered_by_request(
    reasoner_fixture,
) -> None:
    reasoner_fixture.fail_after_claim_commit = True
    reasoner_fixture.llm.responses = [tool_call("begin_task_step_execution", {})]
    with pytest.raises(RuntimeError, match="after claim commit"):
        await reasoner_fixture.run_turn("继续执行下一步")
    attempt = reasoner_fixture.attempt_for_request()
    assert attempt.status == "blocked"
    assert reasoner_fixture.step_status(1) == "pending"


@pytest.mark.asyncio
async def test_terminal_replay_precedes_missing_active_plan(reasoner_fixture) -> None:
    request_id, attempt_id = reasoner_fixture.complete_final_step()
    result = await reasoner_fixture.replay_turn(request_id)
    assert result.context_retry["task_execution"]["request_replayed"] is True
    assert result.context_retry["task_execution"]["attempt_id"] == attempt_id
    assert reasoner_fixture.new_attempt_count == 0


@pytest.mark.parametrize(
    ("exit_kind", "attempt_status", "step_status", "reason"),
    [
        ("provider_error", "blocked", "pending", "turn_interrupted_outcome_unknown"),
        ("timeout", "blocked", "pending", "turn_interrupted_outcome_unknown"),
        ("cancelled", "blocked", "pending", "turn_interrupted_outcome_unknown"),
        ("hook_error", "blocked", "pending", "turn_interrupted_outcome_unknown"),
        (
            "context_error_after_begin",
            "blocked",
            "pending",
            "turn_interrupted_outcome_unknown",
        ),
        (
            "safety_error_after_begin",
            "blocked",
            "pending",
            "turn_interrupted_outcome_unknown",
        ),
        ("max_iterations", "failed", "failed", "work_budget_exhausted"),
        ("second_bare_final", "failed", "failed", "protocol_finish_missing"),
    ],
)
@pytest.mark.asyncio
async def test_execution_exit_matrix(
    reasoner_fixture,
    exit_kind,
    attempt_status,
    step_status,
    reason,
) -> None:
    await reasoner_fixture.run_exit_scenario(exit_kind)
    assert reasoner_fixture.attempt_status() == attempt_status
    assert reasoner_fixture.step_status(1) == step_status
    assert reasoner_fixture.attempt_reason() == reason
    assert reasoner_fixture.active_attempt_count() == 0


@pytest.mark.asyncio
async def test_terminal_request_replay_does_not_claim_next_step(
    reasoner_fixture,
) -> None:
    request_id, attempt_id = reasoner_fixture.complete_final_step()
    await reasoner_fixture.replay_turn(request_id)
    assert [attempt.attempt_id for attempt in reasoner_fixture.attempts()] == [
        attempt_id
    ]


@pytest.mark.asyncio
async def test_recovery_blocked_continue_creates_no_attempt(reasoner_fixture) -> None:
    claimed = reasoner_fixture.execution_service.begin_next_step(
        session_key=reasoner_fixture.session_key,
        request_id="old-request",
    )
    reasoner_fixture.execution_service.start_attempt(
        session_key=reasoner_fixture.session_key,
        attempt_id=claimed.attempt.attempt_id,
    )
    reasoner_fixture.execution_service.block_attempt(
        session_key=reasoner_fixture.session_key,
        attempt_id=claimed.attempt.attempt_id,
        terminal_reason="turn_interrupted_outcome_unknown",
    )
    reasoner_fixture.llm.responses = [final_reply("Explicit retry is required")]
    await reasoner_fixture.run_turn("继续执行下一步")
    assert len(reasoner_fixture.attempts()) == 1


@pytest.mark.asyncio
async def test_explicit_retry_preserves_history_and_increments_attempt_no(
    reasoner_fixture,
) -> None:
    reasoner_fixture.llm.responses = [
        tool_call("begin_task_step_execution", {}),
        tool_call("read_file", {"path": "README.md"}),
        tool_call(
            "finish_task_step_execution",
            {"success": False, "result_summary": "Read failed"},
        ),
        final_reply("Failed"),
    ]
    await reasoner_fixture.run_turn("继续执行下一步")
    first = reasoner_fixture.latest_attempt()
    reasoner_fixture.llm.responses = [
        tool_call("begin_task_step_execution", {}),
        tool_call("read_file", {"path": "README.md", "retry": True}),
        tool_call(
            "finish_task_step_execution",
            {"success": True, "result_summary": "Retry succeeded"},
        ),
        final_reply("Retried"),
    ]
    await reasoner_fixture.run_turn("重试刚才失败的任务步骤")
    attempts = reasoner_fixture.attempts()
    assert [attempt.attempt_no for attempt in attempts] == [1, 2]
    assert attempts[0].attempt_id == first.attempt_id
    assert reasoner_fixture.store.list_execution_events(first.attempt_id)


@pytest.mark.asyncio
async def test_inspect_then_abort_waiting_attempt(reasoner_fixture) -> None:
    reasoner_fixture.llm.responses = [
        tool_call("begin_task_step_execution", {}),
        tool_call("write_file", {"path": "x.txt", "content": "x"}),
        final_reply("Waiting"),
    ]
    await reasoner_fixture.run_turn("继续执行下一步")
    reasoner_fixture.llm.responses = [
        tool_call("inspect_task_execution", {}),
        final_reply("Still waiting"),
    ]
    await reasoner_fixture.run_turn("检查任务执行状态")
    reasoner_fixture.llm.responses = [
        tool_call("abort_task_step_execution", {"reason": "user cancelled"}),
        final_reply("Cancelled"),
    ]
    await reasoner_fixture.run_turn("取消执行")
    assert reasoner_fixture.attempt_status() == "cancelled"


@pytest.mark.asyncio
async def test_execution_disabled_is_not_discoverable(tmp_path: Path) -> None:
    fixture = ReasonerExecutionFixture(tmp_path, enabled=False)
    fixture.llm.responses = [final_reply("Execution disabled")]
    await fixture.run_turn("继续执行下一步")
    names = {schema["function"]["name"] for schema in fixture.llm.calls[0]["tools"]}
    assert "begin_task_step_execution" not in names


@pytest.mark.asyncio
async def test_provider_missing_fails_closed(tmp_path: Path) -> None:
    fixture = ReasonerExecutionFixture(tmp_path, provider_present=False)
    fixture.llm.responses = [final_reply("Execution unavailable")]
    result = await fixture.run_turn("继续执行下一步")
    names = {schema["function"]["name"] for schema in fixture.llm.calls[0]["tools"]}
    assert "begin_task_step_execution" not in names
    assert result.context_retry["task_execution"]["reason"] == (
        "task_execution_provider_unavailable"
    )


@pytest.mark.asyncio
async def test_same_batch_calls_after_defer_are_skipped(reasoner_fixture) -> None:
    reasoner_fixture.llm.responses = [
        tool_call("begin_task_step_execution", {}),
        tool_call_batch(
            ("write_file", {"path": "x.txt", "content": "x"}),
            ("read_file", {"path": "README.md"}),
        ),
        final_reply("Waiting"),
    ]
    await reasoner_fixture.run_turn("继续执行下一步")
    assert reasoner_fixture.write_executor_calls == []
    assert reasoner_fixture.read_executor_calls == []
    assert reasoner_fixture.attempt_status() == "waiting_authorization"


@pytest.mark.asyncio
async def test_lease_expiry_rejects_late_tool_result(tmp_path: Path) -> None:
    fixture = ReasonerExecutionFixture(tmp_path, lease_expiring_read=True)
    fixture.llm.responses = [
        tool_call("begin_task_step_execution", {}),
        tool_call("read_file", {"path": "README.md"}),
        final_reply("Late result must not complete"),
    ]
    await fixture.run_turn("继续执行下一步")
    assert fixture.attempt_status() == "blocked"
    events = fixture.store.list_execution_events(fixture.latest_attempt().attempt_id)
    assert not any(
        event.event_type == "tool_finished" and event.invoker_succeeded
        for event in events
    )
