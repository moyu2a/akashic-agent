from __future__ import annotations

import asyncio
import importlib
from datetime import datetime, timezone

import pytest

from agent.task_plan.execution_runtime import (
    TaskExecutionLeaseGuard,
    TaskExecutionLeaseLostError,
)


def test_runtime_coordinator_module_is_available() -> None:
    try:
        module = importlib.import_module("agent.task_plan.execution_runtime")
    except ModuleNotFoundError:
        module = None
    assert module is not None, "TaskExecutionRuntimeCoordinator integration is absent"
    assert hasattr(module, "TaskExecutionRuntimeCoordinator")
    assert hasattr(module, "TaskExecutionLeaseGuard")


def test_lease_guard_renews_through_service() -> None:
    try:
        module = importlib.import_module("agent.task_plan.execution_runtime")
    except ModuleNotFoundError:
        module = None
    assert module is not None, "TaskExecutionLeaseGuard integration is absent"

    class Service:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def renew_attempt_lease(self, *, session_key: str, attempt_id: str):
            self.calls.append((session_key, attempt_id))
            return object()

    service = Service()
    guard = module.TaskExecutionLeaseGuard(
        service,
        session_key="cli:test",
        attempt_id="attempt-1",
        lease_seconds=30,
        clock=lambda: datetime(2026, 7, 15, tzinfo=timezone.utc),
    )
    guard.renew_now()
    assert service.calls == [("cli:test", "attempt-1")]


class _ConflictingLeaseService:
    def __init__(self) -> None:
        self.called = asyncio.Event()

    def renew_attempt_lease(self, *, session_key: str, attempt_id: str):
        del session_key, attempt_id
        self.called.set()
        raise RuntimeError("lease conflict")


@pytest.mark.asyncio
async def test_async_lease_conflict_raises_lease_lost_after_successful_body() -> None:
    service = _ConflictingLeaseService()
    guard = TaskExecutionLeaseGuard(
        service,
        session_key="cli:test",
        attempt_id="attempt-1",
        lease_seconds=0.03,
        clock=lambda: datetime(2026, 7, 15, tzinfo=timezone.utc),
    )

    with pytest.raises(TaskExecutionLeaseLostError, match="lease renewal"):
        async with guard:
            await asyncio.wait_for(service.called.wait(), timeout=1)


@pytest.mark.asyncio
async def test_async_lease_conflict_preserves_original_body_exception() -> None:
    service = _ConflictingLeaseService()
    guard = TaskExecutionLeaseGuard(
        service,
        session_key="cli:test",
        attempt_id="attempt-1",
        lease_seconds=0.03,
        clock=lambda: datetime(2026, 7, 15, tzinfo=timezone.utc),
    )

    with pytest.raises(ValueError, match="provider failed"):
        async with guard:
            await asyncio.wait_for(service.called.wait(), timeout=1)
            raise ValueError("provider failed")
