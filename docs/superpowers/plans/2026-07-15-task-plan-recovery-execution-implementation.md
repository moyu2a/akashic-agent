# TaskPlan Recovery and Controlled Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add recoverable, idempotent, single-step TaskPlan execution with durable attempts/events, conservative restart handling, and read-only-only automatic work.

**Architecture:** Keep TaskPlan SQLite as the durable fact boundary, use one `TaskControlIntentArbiter` to select the only strict-active TaskPlan/TaskExecution contract, and add a turn-local `TaskExecutionRuntimeCoordinator` between pure Gateway/Boundary decisions and durable service transitions. `TaskExecutionService` enforces session/owner/lease/evidence invariants; store operations atomically update attempt/event/step/plan; the coordinator owns ephemeral protected identity, durable defer, event classification, lease guard, and all turn-exit cleanup without adding execution state to AgentLoop or LRU.

**Tech Stack:** Python 3.14 dataclasses and literals, SQLite transactions/partial indexes, existing ToolRegistry/Gateway/Boundary/Completion/DefaultReasoner, IPC v2, pytest/pytest-asyncio.

**Status:** Ready for implementation; independent re-review found no remaining Critical or Important issues.

## Global Constraints

- The approved design is `my_md/local_agent/03-task-plan-recovery-execution-design.md` and is authoritative.
- First release auto-executes only tools whose registry risk is exactly `read-only`.
- A tool registration with no explicit risk is `unknown`, never implicit read-only; audit all production registrations to keep intended existing classifications explicit.
- `write`, `external-side-effect`, unknown risk, and every `shell` call defer to `waiting_authorization`; LA-002 never approves or executes them.
- `destructive` is a core deny and never becomes an approvable LA-002 request.
- Stale `pending/running` attempts become `blocked` with explicit unknown/interrupted reasons; their pending step remains ineligible for ordinary continue until explicit retry or skip.
- Same trusted transport request ID replays the original attempt; separate inbound requests remain separate operations; never deduplicate by message text.
- Failed and recovery-blocked steps require explicit retry or skip. Retry creates a new attempt and preserves old history.
- Automatic completion requires at least one runtime-classified, executor-reached, exact-read-only `counts_as_work=true` event plus a valid finish transition; discovery/control/synthetic results never count.
- One task and one step may each have at most one nonterminal attempt.
- One turn may claim at most one step and execute at most three real work-tool calls plus one scoped tool search.
- Do not modify AgentLoop control flow, TaskPlan always-on policy, or ToolDiscoveryState/LRU semantics.
- New control tools are deferred and `non_lru=True`.
- Runtime authorization comes from typed contracts and registry metadata, never serialized trace metadata or model arguments.
- Request replay lookup precedes active-plan and step selection, including terminal/replaced plans.
- Start/event/finish/defer mutations require current runtime owner and unexpired lease through atomic compare-and-set.
- Every normal/error/cancel turn exit deterministically transitions or preserves the attempt; no active attempt may be stranded until restart recovery.
- Existing manual update/complete/cancel/replace rejects a nonterminal execution attempt and directs the caller to abort first.
- Default `[task_execution] enabled=false`; existing TaskPlan create/inspect/update must work unchanged.
- Do not promise exactly-once external effects.

---

## File Map

**Create:**

- `agent/task_plan/execution_models.py`: attempt/event dataclasses, statuses, transition validation, IDs.
- `agent/task_plan/execution_store.py`: connection-scoped schema and SQL helpers used by `TaskPlanStore`.
- `agent/task_plan/execution_service.py`: session ownership, claim/replay, finish/defer/abort/inspect/event APIs.
- `agent/task_plan/execution_runtime.py`: turn-local coordinator, lease guard, event classification, durable defer, and finalizer.
- `agent/task_plan/orchestrator.py`: deterministic continue/retry decisions.
- `agent/task_plan/recovery.py`: startup/session reconciliation and runtime lease rules.
- `agent/task_plan/request_identity.py`: protected request ID and idempotency derivation.
- `agent/task_plan/execution_redaction.py`: canonical argument hash, recursive secret masking, and bounded previews.
- `agent/policies/task_execution_contract.py`: immutable action/phase/capability/risk contract.
- `agent/policies/task_control_arbiter.py`: deterministic LA-001 TaskPlan versus TaskExecution intent arbitration.
- `agent/policies/task_execution_access.py`: strict access plan for claim/work/waiting/terminal phases.
- `agent/policies/task_execution_budget.py`: scoped search/work/repeat budget decisions.
- `agent/policies/task_execution_boundary.py`: pure registered-risk allow/defer/deny decisions before ordinary visibility gating.
- `agent/policies/task_execution_completion.py`: final-only after durable terminal/waiting transitions.
- `agent/tools/task_execution.py`: five thin task-execution tool adapters.
- `agent/tools/execution_context.py`: immutable per-call protected context passed to registry execution.
- `tests/test_task_execution_models.py`
- `tests/test_task_execution_store.py`
- `tests/test_task_execution_service.py`
- `tests/test_task_execution_request_identity.py`
- `tests/test_task_execution_redaction.py`
- `tests/test_task_execution_recovery.py`
- `tests/test_task_execution_contract.py`
- `tests/test_task_execution_access.py`
- `tests/test_task_execution_budget.py`
- `tests/test_task_execution_completion.py`
- `tests/test_task_execution_tools.py`
- `tests/test_task_execution_reasoner.py`
- `tests/test_task_execution_lru.py`
- `tests/test_task_execution_runtime.py`
- `tests/test_task_control_arbiter.py`
- `tests/test_task_execution_config.py`
- `tests/test_task_execution_tool_results.py`

**Modify:**

- `agent/task_plan/store.py`: retain single DB/transaction ownership and delegate execution SQL helpers.
- `agent/task_plan/service.py`: expose owned-plan validation to execution service through a non-SQL boundary.
- `agent/task_plan/context.py`: render bounded current-attempt context.
- `agent/task_plan/__init__.py`: public execution exports.
- `agent/config_models.py`, `agent/config.py`: `TaskExecutionConfig` with safe validation.
- `agent/tools/registry.py`: per-call ephemeral protected execution context and risk snapshot accessors; do not store attempt identity in global registry context.
- `agent/tools/base.py`: optional structured `ToolResult.ok/error_code` without changing legacy text rendering.
- `agent/tools/filesystem.py`: structured outcomes for read-only `read_file/list_dir` smoke paths.
- `agent/tool_hooks/types.py`, `agent/tool_hooks/executor.py`: authoritative invoker-reached/succeeded facts.
- `agent/tools/tool_search.py`: runtime-enforced risk filter support without trusting model arguments.
- `bootstrap/toolsets/task_plan.py`: register execution tools using the same service/store identity.
- `bootstrap/wiring.py`, `bootstrap/tools.py`: construct one execution service/recovery instance and run startup reconcile.
- `infra/channels/ipc_protocol.py`, `infra/channels/cli.py`, `infra/channels/ipc_server.py`: optional IPC v2 per-message request ID.
- `agent/policies/tool_access_types.py`, `agent/policies/tool_access.py`: typed execution contract in access context/plan.
- `agent/policies/tool_boundary.py`: compose execution access/budget with core-deny precedence.
- `agent/policies/turn_completion.py`: include execution completion policy.
- `agent/core/passive_turn.py`: call the turn-local coordinator and recompute contract/visibility; do not add execution state to AgentLoop.
- `tests/test_ipc_protocol.py`, `tests/test_io_modules.py`, `tests/test_channel_clients.py`
- `tests/test_bootstrap_toolsets_p1.py`, `tests/test_bootstrap_wiring_p2.py`
- `tests/test_tool_access_gateway_reasoner.py`, `tests/test_tool_boundary_manager.py`
- `tests/test_tool_capabilities.py`
- `my_md/local_agent/03-task-plan-recovery-execution-design.md`
- Governance, STAR, interview, `findings.md`, `progress.md`, and `task_plan.md` after live smoke.

---

## Task 1: Execution Domain Types and Configuration Contract

**Files:**

- Create: `agent/task_plan/execution_models.py`
- Create: `agent/task_plan/execution_redaction.py`
- Modify: `agent/task_plan/__init__.py`
- Modify: `agent/config_models.py`
- Modify: `agent/config.py`
- Test: `tests/test_task_execution_models.py`
- Test: `tests/test_task_execution_redaction.py`
- Test: `tests/test_task_execution_config.py`

**Interfaces:**

- Produces `AttemptStatus`, `ExecutionMode`, `ExecutionEventType`, `TaskExecutionAttempt`, `TaskExecutionEvent`, `RuntimeToolEvent`, `TaskExecutionSnapshot`, and transition validators.
- Produces `AttemptClaimDisposition` and `AttemptClaimResult` so request replay and active-attempt conflict cannot be conflated.
- Produces `TaskExecutionConfig(enabled, auto_allowed_risks, max_work_tool_calls, max_tool_search_calls, lease_seconds)`.
- Produces `redact_execution_arguments()`, `hash_execution_arguments()`, and `bounded_execution_preview()` for every persisted/observed execution payload.
- Later tasks import these exact names; do not put SQL or policy logic in this file.

- [ ] **Step 1: Write failing model and config tests**

```python
from dataclasses import replace

import pytest

from agent.config_models import TaskExecutionConfig
from agent.task_plan.execution_redaction import redact_execution_arguments
from agent.task_plan.execution_models import (
    TaskExecutionAttempt,
    validate_attempt_transition,
)


def test_attempt_terminal_state_cannot_transition() -> None:
    with pytest.raises(ValueError, match="terminal attempt"):
        validate_attempt_transition("succeeded", "running")


def test_attempt_to_dict_deep_copies_nested_metadata() -> None:
    attempt = replace(
        TaskExecutionAttempt.new(
            task_id="task-1",
            step_id="step-1",
            session_key="cli:s1",
            request_id="req-1",
            idempotency_key="idem-1",
            attempt_no=1,
            owner_instance_id="runtime-1",
            lease_expires_at="2026-07-15T01:00:00+00:00",
        ),
        metadata={"nested": {"value": "original"}},
    )
    payload = attempt.to_dict()
    payload["metadata"]["nested"]["value"] = "changed"
    assert attempt.metadata["nested"]["value"] == "original"


def test_waiting_attempt_can_only_cancel_in_la002() -> None:
    validate_attempt_transition("waiting_authorization", "cancelled")
    with pytest.raises(ValueError, match="invalid attempt transition"):
        validate_attempt_transition("waiting_authorization", "pending")


def test_task_execution_config_rejects_unsafe_auto_risk() -> None:
    with pytest.raises(ValueError, match="read-only"):
        TaskExecutionConfig(auto_allowed_risks=["read-only", "write"])


def test_attempt_serialization_returns_copies() -> None:
    attempt = TaskExecutionAttempt.new(
        task_id="task_1",
        step_id="step_1",
        session_key="cli:s1",
        request_id="req_1",
        idempotency_key="idem_1",
        attempt_no=1,
        owner_instance_id="runtime_1",
        lease_expires_at="2026-07-15T01:00:00+00:00",
    )
    payload = attempt.to_dict()
    payload["metadata"]["mutated"] = True
    assert attempt.metadata == {}
    assert replace(attempt, status="pending").status == "pending"


def test_execution_arguments_are_recursively_redacted() -> None:
    redacted = redact_execution_arguments(
        {
            "path": "README.md",
            "headers": {"Authorization": "Bearer secret"},
            "api_key": "sk-secret",
            "nested": [{"password": "p"}, {"value": "visible"}],
        }
    )
    assert redacted["path"] == "README.md"
    assert redacted["headers"]["Authorization"] == "[REDACTED]"
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"][0]["password"] == "[REDACTED]"
    assert redacted["nested"][1]["value"] == "visible"
```

- [ ] **Step 2: Run tests and confirm RED**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_task_execution_models.py \
  tests/test_task_execution_redaction.py \
  tests/test_task_execution_config.py -q
```

Expected: collection fails because `execution_models` and `TaskExecutionConfig` do not exist.

- [ ] **Step 3: Implement exact statuses and transition table**

```python
# agent/task_plan/execution_models.py
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Literal, cast
from uuid import uuid4

from agent.task_plan.models import utc_now_iso

AttemptStatus = Literal[
    "pending",
    "running",
    "waiting_authorization",
    "succeeded",
    "failed",
    "blocked",
    "cancelled",
]
ExecutionMode = Literal["read_only_auto", "authorization_required"]
AttemptClaimDisposition = Literal[
    "created",
    "request_replay",
    "active_conflict",
]
ExecutionEventType = Literal[
    "attempt_claimed",
    "attempt_started",
    "tool_started",
    "tool_finished",
    "authorization_deferred",
    "attempt_succeeded",
    "attempt_failed",
    "attempt_blocked",
    "attempt_cancelled",
    "recovery_reconciled",
]

ACTIVE_ATTEMPT_STATUSES = frozenset(
    {"pending", "running", "waiting_authorization"}
)
TERMINAL_ATTEMPT_STATUSES = frozenset(
    {"succeeded", "failed", "blocked", "cancelled"}
)
_TRANSITIONS = {
    "pending": frozenset(
        {"running", "waiting_authorization", "blocked", "cancelled"}
    ),
    "running": frozenset(
        {
            "waiting_authorization",
            "succeeded",
            "failed",
            "blocked",
            "cancelled",
        }
    ),
    "waiting_authorization": frozenset({"cancelled"}),
    "succeeded": frozenset(),
    "failed": frozenset(),
    "blocked": frozenset(),
    "cancelled": frozenset(),
}


def new_attempt_id() -> str:
    return f"attempt_{uuid4().hex}"


def validate_attempt_status(value: str) -> AttemptStatus:
    if value not in _TRANSITIONS:
        raise ValueError(f"invalid attempt status: {value}")
    return cast(AttemptStatus, value)


def validate_attempt_transition(current: str, target: str) -> AttemptStatus:
    source = validate_attempt_status(current)
    destination = validate_attempt_status(target)
    if source in TERMINAL_ATTEMPT_STATUSES:
        raise ValueError("terminal attempt cannot transition")
    if destination not in _TRANSITIONS[source]:
        raise ValueError(f"invalid attempt transition: {source} -> {destination}")
    return destination


@dataclass(frozen=True)
class TaskExecutionAttempt:
    attempt_id: str
    task_id: str
    step_id: str
    session_key: str
    request_id: str
    idempotency_key: str
    attempt_no: int
    status: AttemptStatus
    execution_mode: ExecutionMode
    owner_instance_id: str
    lease_expires_at: str
    source_turn_id: int | None
    requested_tool_name: str
    requested_arguments: dict[str, Any]
    requested_capabilities: tuple[str, ...]
    result_summary: str
    error_code: str
    terminal_reason: str
    created_at: str
    started_at: str | None
    updated_at: str
    finished_at: str | None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def new(
        cls,
        *,
        task_id: str,
        step_id: str,
        session_key: str,
        request_id: str,
        idempotency_key: str,
        attempt_no: int,
        owner_instance_id: str,
        lease_expires_at: str,
        source_turn_id: int | None = None,
    ) -> "TaskExecutionAttempt":
        now = utc_now_iso()
        return cls(
            attempt_id=new_attempt_id(),
            task_id=task_id,
            step_id=step_id,
            session_key=session_key,
            request_id=request_id,
            idempotency_key=idempotency_key,
            attempt_no=attempt_no,
            status="pending",
            execution_mode="read_only_auto",
            owner_instance_id=owner_instance_id,
            lease_expires_at=lease_expires_at,
            source_turn_id=source_turn_id,
            requested_tool_name="",
            requested_arguments={},
            requested_capabilities=(),
            result_summary="",
            error_code="",
            terminal_reason="",
            created_at=now,
            started_at=None,
            updated_at=now,
            finished_at=None,
            metadata={},
        )

    def to_dict(self) -> dict[str, Any]:
        payload = deepcopy(self.__dict__)
        payload["requested_capabilities"] = list(self.requested_capabilities)
        return payload


@dataclass(frozen=True)
class TaskExecutionEvent:
    event_id: str
    attempt_id: str
    sequence_no: int
    event_type: ExecutionEventType
    tool_name: str
    tool_call_id: str
    source_turn_id: int | None
    tool_risk: str
    tool_capabilities: tuple[str, ...]
    counts_as_work: bool
    invoker_reached: bool
    invoker_succeeded: bool
    execution_status: str
    result_ok: bool | None
    error_code: str
    arguments_hash: str
    result_preview: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeToolEvent:
    event_type: Literal["tool_started", "tool_finished"]
    tool_name: str
    tool_call_id: str
    source_turn_id: int | None
    tool_risk: str
    tool_capabilities: tuple[str, ...]
    counts_as_work: bool
    invoker_reached: bool
    invoker_succeeded: bool
    execution_status: str
    result_ok: bool | None
    error_code: str
    arguments_hash: str
    result_preview: str


@dataclass(frozen=True)
class TaskExecutionSnapshot:
    attempt: TaskExecutionAttempt | None
    events: tuple[TaskExecutionEvent, ...] = ()


@dataclass(frozen=True)
class AttemptClaimResult:
    attempt: TaskExecutionAttempt
    disposition: AttemptClaimDisposition
```

- [ ] **Step 4: Add safe configuration validation**

```python
# agent/config_models.py
@dataclass
class TaskExecutionConfig:
    enabled: bool = False
    auto_allowed_risks: list[str] = field(default_factory=lambda: ["read-only"])
    max_work_tool_calls: int = 3
    max_tool_search_calls: int = 1
    lease_seconds: int = 300

    def __post_init__(self) -> None:
        if set(self.auto_allowed_risks) != {"read-only"}:
            raise ValueError("task execution auto risk must be exactly read-only")
        if self.max_work_tool_calls < 1:
            raise ValueError("max_work_tool_calls must be positive")
        if self.max_tool_search_calls != 1:
            raise ValueError("max_tool_search_calls must be exactly 1")
        if self.lease_seconds < 30:
            raise ValueError("lease_seconds must be at least 30")
```

Add `task_execution: TaskExecutionConfig` to `Config` and parse `[task_execution]` through a dedicated `_load_task_execution_config()` that applies these defaults. Do not silently accept unsafe values.

Implement redaction with deterministic JSON hashing and fixed limits:

```python
# agent/task_plan/execution_redaction.py
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

_SECRET_KEYS = frozenset(
    {"authorization", "api_key", "apikey", "token", "password", "secret", "cookie"}
)


def redact_execution_arguments(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): (
                "[REDACTED]"
                if str(key).casefold() in _SECRET_KEYS
                else redact_execution_arguments(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [redact_execution_arguments(item) for item in value]
    return value


def hash_execution_arguments(arguments: Mapping[str, Any]) -> str:
    payload = json.dumps(arguments, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def bounded_execution_preview(value: object, *, max_chars: int = 512) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= max_chars else text[: max_chars - 3].rstrip() + "..."
```

- [ ] **Step 5: Run GREEN tests**

Run the Step 2 command.

Expected: all selected tests pass.

- [ ] **Step 6: Commit Task 1**

```bash
git add agent/task_plan/execution_models.py agent/task_plan/execution_redaction.py \
  agent/task_plan/__init__.py \
  agent/config_models.py agent/config.py \
  tests/test_task_execution_models.py tests/test_task_execution_redaction.py \
  tests/test_task_execution_config.py
git commit -m "feat: define task execution state contract"
```

---

## Task 2: Attempt/Event Schema and Atomic Persistence

**Files:**

- Create: `agent/task_plan/execution_store.py`
- Modify: `agent/task_plan/store.py`
- Test: `tests/test_task_execution_store.py`
- Test: `tests/test_task_plan_store.py`

**Interfaces:**

- `TaskPlanStore.claim_execution_attempt(*, task_id: str, step_id: str, session_key: str, request_id: str, idempotency_key: str, owner_instance_id: str, lease_expires_at: str, source_turn_id: int | None = None, retry_from_attempt_id: str | None = None) -> AttemptClaimResult`. Retry mode atomically validates the exact latest failed/recovery-blocked attempt, resets the step when needed, and inserts the new attempt/event in the same `BEGIN IMMEDIATE`; normal mode rejects a terminal latest attempt.
- `TaskPlanStore.get_execution_attempt(attempt_id) -> TaskExecutionAttempt | None`.
- `TaskPlanStore.get_execution_attempt_by_request(*, session_key: str, request_id: str) -> TaskExecutionAttempt | None`.
- `TaskPlanStore.get_active_execution_attempt(task_id) -> TaskExecutionAttempt | None`.
- `TaskPlanStore.get_latest_execution_attempt_for_step(step_id) -> TaskExecutionAttempt | None`.
- `TaskPlanStore.list_execution_attempts(task_id) -> list[TaskExecutionAttempt]`.
- `TaskPlanStore.list_recoverable_execution_attempts(session_key: str | None = None) -> list[TaskExecutionAttempt]`.
- `TaskPlanStore.renew_execution_attempt_lease(*, attempt_id: str, owner_instance_id: str, now: datetime, lease_expires_at: str) -> TaskExecutionAttempt` uses an unexpired owner CAS and never resurrects an expired lease.
- `TaskPlanStore.list_execution_events(attempt_id) -> list[TaskExecutionEvent]`.
- `TaskPlanStore.start_execution_attempt(...)`, `finalize_execution_attempt(...)`, `block_execution_attempt(...)`, `defer_execution_attempt(...)`, `abort_execution_attempt(...)`, and `reconcile_execution_attempts(...)` each update attempt/event/step and, where required, task status in one `BEGIN IMMEDIATE` transaction.
- `TaskPlanStore.append_execution_event(...)` accepts runtime-derived `tool_call_id`, `source_turn_id`, `tool_risk`, `tool_capabilities`, `counts_as_work`, `invoker_reached`, and `invoker_succeeded`; it is not exposed to model-facing adapters.
- All cross-table updates share the existing `TaskPlanStore` lock and connection.

- [ ] **Step 1: Write failing migration, replay, and concurrency tests**

```python
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from agent.task_plan.store import TaskPlanStore


def test_claim_replays_same_request(tmp_path: Path) -> None:
    store = TaskPlanStore(tmp_path / "task.db")
    plan = store.create_plan(
        session_key="cli:s1",
        title="Read project",
        step_titles=["Read README", "Summarize tests"],
    )
    first = store.claim_execution_attempt(
        task_id=plan.task_id,
        step_id=plan.steps[0].step_id,
        session_key="cli:s1",
        request_id="req-1",
        idempotency_key="idem-1",
        owner_instance_id="runtime-1",
        lease_expires_at="2026-07-15T01:00:00+00:00",
    )
    second = store.claim_execution_attempt(
        task_id=plan.task_id,
        step_id=plan.steps[0].step_id,
        session_key="cli:s1",
        request_id="req-1",
        idempotency_key="idem-1",
        owner_instance_id="runtime-1",
        lease_expires_at="2026-07-15T01:00:00+00:00",
    )
    assert first.attempt.attempt_id == second.attempt.attempt_id
    assert first.disposition == "created"
    assert second.disposition == "request_replay"


def test_concurrent_claim_has_one_active_attempt(tmp_path: Path) -> None:
    db_path = tmp_path / "task.db"
    setup_store = TaskPlanStore(db_path)
    plan = setup_store.create_plan(
        session_key="cli:s1",
        title="Read project",
        step_titles=["Read README"],
    )

    barrier = Barrier(2)

    def claim(index: int) -> tuple[str, str]:
        store = TaskPlanStore(db_path)
        barrier.wait()
        result = store.claim_execution_attempt(
            task_id=plan.task_id,
            step_id=plan.steps[0].step_id,
            session_key="cli:s1",
            request_id=f"req-{index}",
            idempotency_key=f"idem-{index}",
            owner_instance_id="runtime-1",
            lease_expires_at="2026-07-15T01:00:00+00:00",
        )
        return result.attempt.attempt_id, result.disposition

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, [1, 2]))
    assert len({attempt_id for attempt_id, _ in results}) == 1
    assert {disposition for _, disposition in results} == {
        "created",
        "active_conflict",
    }
```

The second test deliberately uses two store instances and two SQLite connections, so instance `RLock` cannot serialize away the database race. A racing different request returns the already-active attempt with `active_conflict`; it does not create a second row and must not be labeled replay. Add failure-injection tests after attempt insert, event insert, step update, and plan completion; every injected exception must roll back the complete transaction.

- [ ] **Step 2: Run RED store tests**

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_task_execution_store.py \
  tests/test_task_plan_store.py -q
```

Expected: FAIL because schema and store APIs are absent.

- [ ] **Step 3: Implement additive schema helper**

```python
# agent/task_plan/execution_store.py
EXECUTION_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS task_execution_attempts (
    attempt_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    session_key TEXT NOT NULL,
    request_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    attempt_no INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN (
            'pending', 'running', 'waiting_authorization',
            'succeeded', 'failed', 'blocked', 'cancelled'
        )
    ),
    execution_mode TEXT NOT NULL CHECK (
        execution_mode IN ('read_only_auto', 'authorization_required')
    ),
    owner_instance_id TEXT NOT NULL,
    lease_expires_at TEXT NOT NULL,
    source_turn_id INTEGER,
    requested_tool_name TEXT NOT NULL DEFAULT '',
    requested_arguments_json TEXT NOT NULL DEFAULT '{}',
    requested_capabilities_json TEXT NOT NULL DEFAULT '[]',
    result_summary TEXT NOT NULL DEFAULT '',
    error_code TEXT NOT NULL DEFAULT '',
    terminal_reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    started_at TEXT,
    updated_at TEXT NOT NULL,
    finished_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(task_id) REFERENCES task_plans(task_id) ON DELETE CASCADE,
    FOREIGN KEY(step_id) REFERENCES task_steps(step_id) ON DELETE CASCADE,
    UNIQUE(step_id, attempt_no),
    UNIQUE(session_key, request_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_task_execution_one_active_per_step
ON task_execution_attempts(step_id)
WHERE status IN ('pending', 'running', 'waiting_authorization');

CREATE UNIQUE INDEX IF NOT EXISTS ux_task_execution_one_active_per_task
ON task_execution_attempts(task_id)
WHERE status IN ('pending', 'running', 'waiting_authorization');

CREATE TABLE IF NOT EXISTS task_execution_events (
    event_id TEXT PRIMARY KEY,
    attempt_id TEXT NOT NULL,
    sequence_no INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    tool_name TEXT NOT NULL DEFAULT '',
    tool_call_id TEXT NOT NULL DEFAULT '',
    source_turn_id INTEGER,
    tool_risk TEXT NOT NULL DEFAULT '',
    tool_capabilities_json TEXT NOT NULL DEFAULT '[]',
    counts_as_work INTEGER NOT NULL DEFAULT 0,
    invoker_reached INTEGER NOT NULL DEFAULT 0,
    invoker_succeeded INTEGER NOT NULL DEFAULT 0,
    execution_status TEXT NOT NULL DEFAULT '',
    result_ok INTEGER,
    error_code TEXT NOT NULL DEFAULT '',
    arguments_hash TEXT NOT NULL DEFAULT '',
    result_preview TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(attempt_id) REFERENCES task_execution_attempts(attempt_id)
        ON DELETE CASCADE,
    UNIQUE(attempt_id, sequence_no)
);

CREATE INDEX IF NOT EXISTS ix_task_execution_events_attempt_sequence
ON task_execution_events(attempt_id, sequence_no);
"""
```

Call this SQL from `TaskPlanStore._ensure_schema()` after existing plan/step tables are created.

- [ ] **Step 4: Implement atomic claim and transition helpers**

Use `BEGIN IMMEDIATE` and this ordering inside `claim_execution_attempt()`. Replay lookup is the first database operation and is valid even if the original task is now terminal or no longer active:

```python
conn.execute("BEGIN IMMEDIATE")
replay = conn.execute(
    """
    SELECT * FROM task_execution_attempts
    WHERE session_key = ? AND request_id = ?
    """,
    (session_key, request_id),
).fetchone()
if replay is not None:
    conn.commit()
    return AttemptClaimResult(
        attempt=row_to_execution_attempt(replay),
        disposition="request_replay",
    )

active = conn.execute(
    """
    SELECT * FROM task_execution_attempts
    WHERE task_id = ?
      AND status IN ('pending', 'running', 'waiting_authorization')
    ORDER BY created_at DESC LIMIT 1
    """,
    (task_id,),
).fetchone()
if active is not None:
    conn.commit()
    return AttemptClaimResult(
        attempt=row_to_execution_attempt(active),
        disposition="active_conflict",
    )
```

Then revalidate task/session/step ownership, calculate `attempt_no` with `MAX(attempt_no)+1`, insert attempt and event sequence 1, and commit with disposition `created`. Convert uniqueness races into a deterministic fetch classified as `request_replay` only when request IDs match, otherwise `active_conflict`; do not leak `sqlite3.IntegrityError` to tools.

Implement explicit atomic transition methods instead of a generic public transition helper:

- start: pending attempt + pending step -> running + in_progress;
- finish success: running -> succeeded, step -> completed, and plan -> completed when every step is completed/skipped;
- finish failure: running -> failed and step -> failed;
- block: current-owner unexpired pending/running -> blocked, step -> pending, append `attempt_blocked`; used by runtime finalization, not as an implicit retry;
- defer: pending/running -> waiting_authorization and step -> pending;
- reconcile: stale pending/running -> blocked and only an in_progress step -> pending;
- abort: active/waiting -> cancelled and step -> pending.

All methods append exactly one matching transition event before commit. Add rollback injection specifically between blocked-attempt update, step reset, and event insert. Manual `update_step`, `set_task_status`, and `create_plan(replace_active=True)` must reject when the affected task has an active execution attempt; the user must abort it first.

`renew_execution_attempt_lease()` and start/event/finish/defer compare `(attempt_id, owner_instance_id, expected_status, lease_expires_at > now)` in SQL. A stale, expired, or foreign owner raises a typed conflict; it never steals ownership or revives an attempt.

- [ ] **Step 5: Run GREEN and existing store regressions**

Run the Step 2 command.

Expected: all pass; existing plan schema and one-active-plan behavior remain unchanged.

- [ ] **Step 6: Commit Task 2**

```bash
git add agent/task_plan/execution_store.py agent/task_plan/store.py \
  tests/test_task_execution_store.py tests/test_task_plan_store.py
git commit -m "feat: persist task execution attempts and events"
```

**Persistence checkpoint only:** schema and atomic transitions exist, but LA-002a is not complete until service replay/retry gates, lease ownership, and recovery tests in Tasks 3-5 pass. No runtime work tool is enabled.

---

## Task 3: Execution Service and Deterministic Orchestrator

**Files:**

- Create: `agent/task_plan/execution_service.py`
- Create: `agent/task_plan/orchestrator.py`
- Create: `agent/task_plan/request_identity.py`
- Modify: `agent/task_plan/service.py`
- Modify: `agent/task_plan/__init__.py`
- Test: `tests/test_task_execution_service.py`
- Test: `tests/test_task_execution_request_identity.py`

**Interfaces:**

- `TaskExecutionService(store, plan_service, runtime_instance_id, config, clock)` binds all automatic mutations to one runtime owner and clock.
- `TaskExecutionService.replay_request(*, session_key: str, request_id: str) -> BeginExecutionResult | None` is called before active-plan lookup.
- `TaskExecutionService.begin_next_step(*, session_key: str, request_id: str, source_turn_id: int | None = None) -> BeginExecutionResult`.
- `TaskExecutionService.retry_step(*, session_key: str, step_id: str, request_id: str, source_turn_id: int | None = None) -> BeginExecutionResult` accepts only latest failed or unknown/interrupted blocked attempts.
- `TaskExecutionService.find_retryable_step(*, session_key: str) -> TaskStep | None` returns the lowest-index owned step whose latest attempt is failed or approved recovery-blocked.
- `TaskExecutionService.start_attempt(*, session_key: str, attempt_id: str) -> TaskExecutionSnapshot` uses owner/status/lease CAS.
- `TaskExecutionService.record_tool_event(*, session_key: str, attempt_id: str, event: RuntimeToolEvent) -> TaskExecutionEvent` accepts only runtime-created event facts and uses owner/status/lease CAS.
- `TaskExecutionService.finish_attempt(*, session_key: str, attempt_id: str, success: bool, result_summary: str, error_code: str = "") -> TaskExecutionSnapshot`.
- `TaskExecutionService.block_attempt(*, session_key: str, attempt_id: str, terminal_reason: str, error_code: str = "") -> TaskExecutionSnapshot` atomically blocks a current-owner unexpired pending/running attempt and resets its step.
- `TaskExecutionService.defer_attempt(*, session_key: str, attempt_id: str, tool_name: str, requested_arguments: dict[str, object], requested_capabilities: tuple[str, ...], reason: str) -> TaskExecutionSnapshot`.
- `TaskExecutionService.abort_attempt(*, session_key: str, attempt_id: str, reason: str) -> TaskExecutionSnapshot`.
- `TaskExecutionService.inspect(*, session_key: str, attempt_id: str | None = None) -> TaskExecutionSnapshot`.
- `TaskExecutionOrchestrator.decide_continue(*, session_key: str, request_id: str, source_turn_id: int | None = None) -> ExecutionOrchestrationDecision`.
- `TaskExecutionOrchestrator.decide_retry(*, session_key: str, step_id: str, request_id: str, source_turn_id: int | None = None) -> ExecutionOrchestrationDecision`.
- `derive_task_execution_idempotency_key(*, session_key: str, request_id: str, task_id: str, step_id: str, action: str) -> str`.

- [ ] **Step 1: Write failing ownership, selection, replay, retry, and finish tests**

```python
import pytest

from agent.task_plan.execution_models import RuntimeToolEvent


def test_continue_selects_only_lowest_pending_step(execution_service) -> None:
    plan = execution_service.plan_service.create_task_plan(
        session_key="cli:s1",
        title="Two steps",
        steps=["Read README", "Summarize tests"],
    )
    result = execution_service.begin_next_step(
        session_key="cli:s1",
        request_id="req-1",
    )
    assert result.attempt.step_id == plan.steps[0].step_id
    assert result.replayed is False


def test_continue_does_not_skip_failed_step(execution_service) -> None:
    result = execution_service.begin_next_step(
        session_key="cli:s1",
        request_id="req-2",
    )
    execution_service.start_attempt(
        session_key="cli:s1",
        attempt_id=result.attempt.attempt_id,
    )
    execution_service.finish_attempt(
        session_key="cli:s1",
        attempt_id=result.attempt.attempt_id,
        success=False,
        result_summary="read failed",
        error_code="read_error",
    )
    with pytest.raises(TaskExecutionConflictError, match="explicit retry"):
        execution_service.begin_next_step(
            session_key="cli:s1",
            request_id="req-3",
        )


def test_finish_success_requires_successful_work_event(execution_service) -> None:
    result = execution_service.begin_next_step(
        session_key="cli:s1",
        request_id="req-1",
    )
    execution_service.start_attempt(
        session_key="cli:s1",
        attempt_id=result.attempt.attempt_id,
    )
    with pytest.raises(TaskExecutionConflictError, match="work event"):
        execution_service.finish_attempt(
            session_key="cli:s1",
            attempt_id=result.attempt.attempt_id,
            success=True,
            result_summary="done",
        )


def test_explicit_skip_allows_continue_after_failed_step(execution_service) -> None:
    plan = execution_service.plan_service.create_task_plan(
        session_key="cli:s1",
        title="Two steps",
        steps=["Read README", "Summarize tests"],
    )
    failed = execution_service.begin_next_step(
        session_key="cli:s1",
        request_id="req-fail",
    )
    execution_service.start_attempt(
        session_key="cli:s1",
        attempt_id=failed.attempt.attempt_id,
    )
    execution_service.finish_attempt(
        session_key="cli:s1",
        attempt_id=failed.attempt.attempt_id,
        success=False,
        result_summary="read failed",
        error_code="read_error",
    )
    execution_service.plan_service.update_step_status(
        session_key="cli:s1",
        task_id=plan.task_id,
        step_id=plan.steps[0].step_id,
        status="skipped",
        result_summary="user explicitly skipped failed step",
    )
    result = execution_service.begin_next_step(
        session_key="cli:s1",
        request_id="req-after-skip",
    )
    assert result.step.index == 2


def test_replay_is_returned_after_final_step_completed(execution_service) -> None:
    execution_service.plan_service.create_task_plan(
        session_key="cli:s1",
        title="One step",
        steps=["Read README"],
    )
    original = execution_service.begin_next_step(
        session_key="cli:s1",
        request_id="req-final",
    )
    execution_service.start_attempt(
        session_key="cli:s1",
        attempt_id=original.attempt.attempt_id,
    )
    execution_service.record_tool_event(
        session_key="cli:s1",
        attempt_id=original.attempt.attempt_id,
        event=RuntimeToolEvent(
            event_type="tool_finished",
            tool_name="read_file",
            tool_call_id="call-1",
            source_turn_id=10,
            tool_risk="read-only",
            tool_capabilities=(),
            counts_as_work=True,
            invoker_reached=True,
            invoker_succeeded=True,
            execution_status="success",
            result_ok=True,
            error_code="",
            arguments_hash="hash-1",
            result_preview="README",
        ),
    )
    execution_service.finish_attempt(
        session_key="cli:s1",
        attempt_id=original.attempt.attempt_id,
        success=True,
        result_summary="Read README",
    )
    replay = execution_service.begin_next_step(
        session_key="cli:s1",
        request_id="req-final",
    )
    assert replay.replayed is True
    assert replay.attempt.attempt_id == original.attempt.attempt_id


def test_search_only_event_cannot_finish(execution_service) -> None:
    execution_service.plan_service.create_task_plan(
        session_key="cli:s1",
        title="Search",
        steps=["Find a tool"],
    )
    claimed = execution_service.begin_next_step(
        session_key="cli:s1",
        request_id="req-search",
    )
    execution_service.start_attempt(
        session_key="cli:s1",
        attempt_id=claimed.attempt.attempt_id,
    )
    execution_service.record_tool_event(
        session_key="cli:s1",
        attempt_id=claimed.attempt.attempt_id,
        event=RuntimeToolEvent(
            event_type="tool_finished",
            tool_name="tool_search",
            tool_call_id="call-search",
            source_turn_id=11,
            tool_risk="read-only",
            tool_capabilities=(),
            counts_as_work=False,
            invoker_reached=True,
            invoker_succeeded=True,
            execution_status="success",
            result_ok=True,
            error_code="",
            arguments_hash="hash-search",
            result_preview="read_file",
        ),
    )
    with pytest.raises(TaskExecutionConflictError, match="work event"):
        execution_service.finish_attempt(
            session_key="cli:s1",
            attempt_id=claimed.attempt.attempt_id,
            success=True,
            result_summary="searched only",
        )


def test_runtime_block_resets_step_without_marking_failed(execution_service) -> None:
    execution_service.plan_service.create_task_plan(
        session_key="cli:s1",
        title="Interrupted",
        steps=["Read README"],
    )
    claimed = execution_service.begin_next_step(
        session_key="cli:s1",
        request_id="req-block",
    )
    execution_service.start_attempt(
        session_key="cli:s1",
        attempt_id=claimed.attempt.attempt_id,
    )
    snapshot = execution_service.block_attempt(
        session_key="cli:s1",
        attempt_id=claimed.attempt.attempt_id,
        terminal_reason="turn_interrupted_outcome_unknown",
    )
    plan = execution_service.plan_service.get_active_task_plan(session_key="cli:s1")
    assert snapshot.attempt.status == "blocked"
    assert plan.steps[0].status == "pending"
```

Also test replay after failed/blocked attempts, retry creates a new attempt number while preserving events, expired/foreign-owner mutation CAS failures, final-step atomic plan completion, and manual update/complete/cancel/replace rejection while an attempt is nonterminal.

- [ ] **Step 2: Run RED service tests**

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_task_execution_service.py \
  tests/test_task_execution_request_identity.py -q
```

Expected: import/attribute failures.

- [ ] **Step 3: Implement typed results and service boundary**

```python
# agent/task_plan/execution_service.py
@dataclass(frozen=True)
class BeginExecutionResult:
    attempt: TaskExecutionAttempt
    step: TaskStep
    replayed: bool


class TaskExecutionError(RuntimeError):
    pass


class TaskExecutionConflictError(TaskExecutionError):
    pass


class TaskExecutionAccessDeniedError(TaskExecutionError):
    pass


class TaskExecutionService:
    def __init__(
        self,
        plan_service: TaskPlanService,
        store: TaskPlanStore,
        *,
        runtime_instance_id: str,
        config: TaskExecutionConfig,
        now: Callable[[], datetime],
    ) -> None:
        self.plan_service = plan_service
        self._store = store
        self._runtime_instance_id = runtime_instance_id
        self._config = config
        self._now = now
```

Add a public `require_owned_task_plan()` wrapper to `TaskPlanService` that delegates to its existing private ownership check; do not expose raw store rows.

`begin_next_step()` rules, in order:

1. Call `replay_request(session_key, request_id)` and immediately return the historical attempt when present, regardless of task state.
2. Require owned active plan.
3. If an active attempt exists, return `attempt_already_active` conflict; a different request is never labeled replay.
4. If any step is failed, raise `failed_step_requires_explicit_retry`.
5. For each candidate pending step, inspect its latest attempt; unknown/interrupted blocked requires explicit retry or skip and cannot be selected by continue.
6. Select the lowest-index eligible pending step; if none exists, return the specific blocked/failed/no-pending error.
7. Derive idempotency through `request_identity.py` and call atomic store claim.

`retry_step()` first performs the same replay-first lookup, then verifies that the target belongs to the active owned plan and its latest attempt is `failed` or `blocked` with an approved interrupted/unknown terminal reason. It never retries succeeded/cancelled/waiting/running attempts and always creates `attempt_no + 1`.

`start_attempt()` validates ownership and performs the only legal `pending -> running` transition. It also changes the selected Step from pending to in_progress and appends `attempt_started` in the same transaction.

`finish_attempt(success=True)` must query events and require at least one `tool_finished` event with `counts_as_work=True`, exact persisted `tool_risk == "read-only"`, `invoker_reached=True`, `invoker_succeeded=True`, `result_ok=True`, and no unresolved execution error. `tool_search`, legacy unstructured results, task-execution control calls, synthetic gate results, and batch skips are ineligible by construction.

`block_attempt()` uses the dedicated store transition and never aliases finish-failure. If lease renewal shows the lease is already expired, call session recovery instead of reviving it; recovery performs the blocked transition under stale-attempt rules. Block is idempotent when the target is already terminal and must not overwrite succeeded/failed/cancelled.

Every `record_tool_event()` and `defer_attempt()` call must use Task 1 redaction/hash/preview helpers before persistence. Full raw arguments never enter ordinary attempt events or observe metadata.

`record_tool_event()` rejects model-built mappings and receives a frozen `RuntimeToolEvent` created by Task 9's coordinator from ToolRegistry risk/capability snapshots and actual executor status. The service/store still revalidates owner, status, and unexpired lease.

Implement the pure identity helper in this task so service tests are independent:

```python
def derive_task_execution_idempotency_key(
    *, session_key: str, request_id: str, task_id: str, step_id: str, action: str
) -> str:
    raw = "\x1f".join((session_key, request_id, task_id, step_id, action))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Implement orchestrator decisions without SQL**

```python
# agent/task_plan/orchestrator.py
ExecutionOrchestrationAction = Literal[
    "claimed",
    "replayed",
    "inspect",
    "conflict",
]


@dataclass(frozen=True)
class ExecutionOrchestrationDecision:
    action: ExecutionOrchestrationAction
    reason: str
    snapshot: TaskExecutionSnapshot


class TaskExecutionOrchestrator:
    def __init__(self, service: TaskExecutionService) -> None:
        self._service = service

    def decide_continue(self, **kwargs: object) -> ExecutionOrchestrationDecision:
        result = self._service.begin_next_step(**kwargs)
        return ExecutionOrchestrationDecision(
            action="replayed" if result.replayed else "claimed",
            reason=(
                "task_execution_request_replayed"
                if result.replayed
                else "task_execution_step_claimed"
            ),
            snapshot=TaskExecutionSnapshot(attempt=result.attempt),
        )
```

Use explicit parameters in production code rather than `**kwargs`; the snippet only shows decision construction. Keep model intent parsing out of this class.

- [ ] **Step 5: Run GREEN service tests**

Run Step 2 command.

Expected: all pass.

- [ ] **Step 6: Commit Task 3**

```bash
git add agent/task_plan/execution_service.py agent/task_plan/orchestrator.py \
  agent/task_plan/request_identity.py agent/task_plan/service.py \
  agent/task_plan/__init__.py tests/test_task_execution_service.py \
  tests/test_task_execution_request_identity.py
git commit -m "feat: add idempotent task execution service"
```

---

## Task 4: Trusted Request Identity and IPC v2 Replay Key

**Files:**

- Modify: `agent/task_plan/request_identity.py`
- Modify: `infra/channels/ipc_protocol.py`
- Modify: `infra/channels/cli.py`
- Modify: `infra/channels/ipc_server.py`
- Modify: `tests/test_task_execution_request_identity.py`
- Test: `tests/test_ipc_protocol.py`
- Test: `tests/test_io_modules.py`
- Test: `tests/test_channel_clients.py`

**Interfaces:**

- `ensure_task_execution_request_id(msg: InboundMessage) -> str` mutates protected metadata only once.
- `derive_task_execution_idempotency_key(*, session_key: str, request_id: str, task_id: str, step_id: str, action: str) -> str` uses SHA-256 fields from the approved design.
- IPC v2 user payload includes a UUID `request_id`; old clients without it remain valid.

- [ ] **Step 1: Write failing request identity and protocol tests**

```python
from bus.events import InboundMessage
from agent.task_plan.request_identity import (
    derive_task_execution_idempotency_key,
    ensure_task_execution_request_id,
)


def test_existing_transport_request_id_is_preserved() -> None:
    msg = InboundMessage(
        channel="cli",
        sender="user",
        chat_id="s1",
        content="continue",
        metadata={"_transport_request_id": "req-transport"},
    )
    assert ensure_task_execution_request_id(msg) == "req-transport"
    assert msg.metadata["_task_execution_request_id"] == "req-transport"


def test_idempotency_key_changes_for_distinct_request() -> None:
    first = derive_task_execution_idempotency_key(
        session_key="cli:s1",
        request_id="req-1",
        task_id="task-1",
        step_id="step-1",
        action="continue",
    )
    second = derive_task_execution_idempotency_key(
        session_key="cli:s1",
        request_id="req-2",
        task_id="task-1",
        step_id="step-1",
        action="continue",
    )
    assert first != second
```

Add IPC tests asserting `request_id` reaches `InboundMessage.metadata`, and legacy/v2 frames without it still work.

- [ ] **Step 2: Run RED identity/protocol tests**

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_task_execution_request_identity.py \
  tests/test_ipc_protocol.py \
  tests/test_io_modules.py \
  tests/test_channel_clients.py -q
```

Expected: new identity imports/assertions fail.

- [ ] **Step 3: Implement protected identity**

```python
# agent/task_plan/request_identity.py additions
from __future__ import annotations

import hashlib
from uuid import uuid4

from bus.events import InboundMessage


def ensure_task_execution_request_id(msg: InboundMessage) -> str:
    existing = str(msg.metadata.get("_task_execution_request_id") or "").strip()
    if existing:
        return existing
    trusted = str(msg.metadata.get("_transport_request_id") or "").strip()
    request_id = trusted or f"runtime-{uuid4().hex}"
    msg.metadata["_task_execution_request_id"] = request_id
    return request_id


```

Keep the pure `derive_task_execution_idempotency_key()` implementation from Task 3 unchanged.

- [ ] **Step 4: Add backward-compatible IPC request IDs**

In `infra/channels/cli.py`, generate one UUID per user submit and send:

```python
payload = {
    "type": "user",
    "request_id": uuid.uuid4().hex,
    "content": text,
}
writer.write(encode_frame(payload))
```

In `ipc_server._handle_payload()`, copy only a bounded/sanitized request ID:

```python
request_id = str(data.get("request_id") or "").strip()[:128]
metadata = {"_transport_request_id": request_id} if request_id else {}
InboundMessage(
    channel=CHANNEL,
    sender="cli-user",
    chat_id=chat_id,
    content=content,
    metadata=metadata,
)
```

Do not require request ID in `read_frame()` or hello; old clients stay compatible.

- [ ] **Step 5: Run GREEN identity/protocol tests**

Run Step 2 command.

Expected: all pass.

- [ ] **Step 6: Commit Task 4**

```bash
git add agent/task_plan/request_identity.py infra/channels/ipc_protocol.py \
  infra/channels/cli.py infra/channels/ipc_server.py \
  tests/test_task_execution_request_identity.py tests/test_ipc_protocol.py \
  tests/test_io_modules.py tests/test_channel_clients.py
git commit -m "feat: add replay-safe task execution request identity"
```

---

## Task 5: Startup and Session Recovery

**Files:**

- Create: `agent/task_plan/recovery.py`
- Modify: `agent/task_plan/execution_store.py`
- Modify: `agent/task_plan/store.py`
- Modify: `bootstrap/tools.py`
- Modify: `bootstrap/wiring.py`
- Test: `tests/test_task_execution_recovery.py`
- Test: `tests/test_bootstrap_wiring_p2.py`

**Interfaces:**

- `TaskExecutionRecoveryService(service, clock)` uses the runtime identity already bound inside `TaskExecutionService`.
- `reconcile_startup() -> tuple[RecoveryResult, ...]`.
- `reconcile_session(session_key) -> tuple[RecoveryResult, ...]`.
- `RecoveryResult(attempt_id, previous_status, current_status, reason, step_reset)`.

- [ ] **Step 1: Write failing restart, lease, waiting, and no-replay tests**

```python
import pytest

from agent.task_plan.execution_service import TaskExecutionConflictError


def test_old_runtime_running_attempt_blocks_without_retry(recovery_fixture) -> None:
    fixture = recovery_fixture(status="running", owner="runtime-old")
    results = fixture.recovery.reconcile_session("cli:s1")
    snapshot = fixture.execution_service.inspect(
        session_key="cli:s1",
        attempt_id=fixture.attempt_id,
    )
    plan = fixture.plan_service.get_active_task_plan(session_key="cli:s1")
    assert results[0].reason == "runtime_restarted_outcome_unknown"
    assert snapshot.attempt.status == "blocked"
    assert plan.steps[0].status == "pending"
    assert len(fixture.store.list_execution_attempts(fixture.task_id)) == 1


def test_waiting_authorization_survives_restart(recovery_fixture) -> None:
    fixture = recovery_fixture(status="waiting_authorization", owner="runtime-old")
    assert fixture.recovery.reconcile_session("cli:s1") == ()
    snapshot = fixture.execution_service.inspect(
        session_key="cli:s1",
        attempt_id=fixture.attempt_id,
    )
    assert snapshot.attempt.status == "waiting_authorization"


def test_expired_current_runtime_lease_blocks_as_unknown(recovery_fixture) -> None:
    fixture = recovery_fixture(
        status="running",
        owner="runtime-current",
        lease_expires_at="2026-07-15T00:00:00+00:00",
        now="2026-07-15T00:01:00+00:00",
    )
    results = fixture.recovery.reconcile_session("cli:s1")
    snapshot = fixture.execution_service.inspect(
        session_key="cli:s1",
        attempt_id=fixture.attempt_id,
    )
    assert results[0].reason == "lease_expired_outcome_unknown"
    assert snapshot.attempt.status == "blocked"


def test_recovered_blocked_step_requires_explicit_retry(recovery_fixture) -> None:
    fixture = recovery_fixture(status="running", owner="runtime-old")
    fixture.recovery.reconcile_session("cli:s1")
    before = fixture.store.list_execution_attempts(fixture.task_id)
    with pytest.raises(TaskExecutionConflictError, match="retry or skip"):
        fixture.execution_service.begin_next_step(
            session_key="cli:s1",
            request_id="req-ordinary-continue",
        )
    after = fixture.store.list_execution_attempts(fixture.task_id)
    assert [item.attempt_id for item in after] == [
        item.attempt_id for item in before
    ]
```

- [ ] **Step 2: Run RED recovery tests**

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_task_execution_recovery.py \
  tests/test_bootstrap_wiring_p2.py -q
```

Expected: recovery classes and wiring absent.

- [ ] **Step 3: Implement conservative reconciliation**

```python
# agent/task_plan/recovery.py
@dataclass(frozen=True)
class RecoveryResult:
    attempt_id: str
    previous_status: AttemptStatus
    current_status: AttemptStatus
    reason: str
    step_reset: bool


class TaskExecutionRecoveryService:
    def __init__(
        self,
        *,
        service: TaskExecutionService,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._service = service
        self._now = now or (lambda: datetime.now(UTC))

    def reconcile_session(self, session_key: str) -> tuple[RecoveryResult, ...]:
        return self._service.reconcile_attempts(
            session_key=session_key,
            now=self._now(),
        )
```

Store reconciliation rules must be one transaction per batch. Do not modify `waiting_authorization` or terminal attempts. For stale running reset only a still-`in_progress` step to pending; never overwrite completed/skipped. The blocked terminal reason remains the durable gate checked by ordinary continue; recovery never changes it into an implicitly retryable blank pending step.

- [ ] **Step 4: Wire one runtime instance and startup reconcile**

Create one `runtime_instance_id = f"runtime_{uuid4().hex}"` in bootstrap composition. Build one execution service and recovery service from the same `TaskPlanStore` used by TaskPlan tools. Run `reconcile_startup()` after services exist and before AgentLoop starts accepting inbound messages. Log counts/reasons; a recovery error must fail closed by disabling task execution, not prevent ordinary Agent startup.

- [ ] **Step 5: Run GREEN and bootstrap tests**

Run Step 2 command.

Expected: all pass; startup recovery never invokes ToolRegistry.

- [ ] **Step 6: Commit Task 5**

```bash
git add agent/task_plan/recovery.py agent/task_plan/execution_store.py \
  agent/task_plan/store.py bootstrap/tools.py bootstrap/wiring.py \
  tests/test_task_execution_recovery.py tests/test_bootstrap_wiring_p2.py
git commit -m "feat: reconcile stale task execution attempts"
```

**LA-002a complete checkpoint:** before enabling any execution tool, run exactly:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_task_execution_models.py \
  tests/test_task_execution_redaction.py \
  tests/test_task_execution_config.py \
  tests/test_task_execution_store.py \
  tests/test_task_execution_service.py \
  tests/test_task_execution_request_identity.py \
  tests/test_task_execution_recovery.py \
  tests/test_task_plan_store.py \
  tests/test_task_plan_service.py \
  tests/test_bootstrap_wiring_p2.py -q
```

Pass criteria: terminal/replaced-plan replay works; recovery-blocked ordinary continue creates no row; explicit retry creates a new attempt; owner/lease CAS rejects stale mutation; dedicated runtime block resets step without marking failed; final-step success atomically completes plan; active attempt blocks manual mutation; two independent connections prove one active claim; rollback injection leaves no partial attempt/event/step/plan state. No TaskExecution work/control tool is registered or executable at this checkpoint.

---

## Task 6: Typed Execution Contract and Access Policy

**Files:**

- Create: `agent/policies/task_execution_contract.py`
- Create: `agent/policies/task_control_arbiter.py`
- Create: `agent/policies/task_execution_access.py`
- Modify: `agent/policies/tool_access_types.py`
- Modify: `agent/policies/tool_access.py`
- Modify: `agent/policies/__init__.py`
- Test: `tests/test_task_execution_contract.py`
- Test: `tests/test_task_control_arbiter.py`
- Test: `tests/test_task_execution_access.py`
- Test: `tests/test_tool_access_types.py`

**Interfaces:**

- `TaskExecutionTurnContract.inactive()` canonical inactive value.
- `infer_task_execution_contract(user_text, metadata) -> TaskExecutionTurnContract`.
- `TaskControlIntentArbiter.resolve(*, task_plan_contract, task_execution_contract, user_text, metadata) -> TaskControlIntentDecision` returns at most one strict-active contract.
- `TaskExecutionAccessPolicy.build_plan(context) -> ToolAccessPlan` follows the existing `ToolAccessPolicy` protocol.
- `ToolAccessPlan.task_execution_contract` is typed runtime state; `policy_metadata` stays trace-only.
- `ToolAccessContext.tool_risks` is a runtime snapshot from `ToolRegistry.get_risks_by_name()`, not model/tool-search output.

- [ ] **Step 1: Write failing contract precedence/invariant tests**

```python
from agent.policies.task_control_arbiter import TaskControlIntentArbiter
from agent.policies.task_execution_contract import infer_task_execution_contract
from agent.policies.task_plan_contract import infer_task_plan_turn_decision


def test_continue_requires_active_task_and_enabled_execution() -> None:
    inactive = infer_task_execution_contract(
        "继续执行下一步",
        {"has_active_task": False, "task_execution_enabled": True},
    )
    active = infer_task_execution_contract(
        "继续执行下一步",
        {"has_active_task": True, "task_execution_enabled": True},
    )
    assert inactive.active is False
    assert active.action == "continue"
    assert active.phase == "claim"
    assert active.required_capabilities == frozenset({"task_execution.begin"})


def test_explicit_task_update_beats_ambiguous_continue() -> None:
    contract = infer_task_execution_contract(
        "不要继续执行，把第一步标记完成",
        {"has_active_task": True, "task_execution_enabled": True},
    )
    assert contract.active is False


def test_explicit_execution_continue_beats_generic_plan_update() -> None:
    text = "继续执行下一步"
    task_plan = infer_task_plan_turn_decision(
        text,
        has_active_task=True,
    ).contract
    execution = infer_task_execution_contract(
        text,
        {"has_active_task": True, "task_execution_enabled": True},
    )
    decision = TaskControlIntentArbiter().resolve(
        task_plan_contract=task_plan,
        task_execution_contract=execution,
        user_text=text,
        metadata={},
    )
    assert decision.task_plan_contract is None
    assert decision.task_execution_contract.action == "continue"


def test_retry_resolves_protected_target_step() -> None:
    text = "重试刚才被中断的步骤"
    task_plan = infer_task_plan_turn_decision(
        text,
        has_active_task=True,
    ).contract
    execution = infer_task_execution_contract(
        text,
        {
            "has_active_task": True,
            "latest_retryable_step_id": "step-1",
            "task_execution_enabled": True,
        },
    )
    decision = TaskControlIntentArbiter().resolve(
        task_plan_contract=task_plan,
        task_execution_contract=execution,
        user_text=text,
        metadata={"latest_retryable_step_id": "step-1"},
    )
    assert decision.task_execution_contract.action == "retry"
    assert decision.task_execution_contract.target_step_id == "step-1"


def test_runtime_replay_is_active_without_active_plan() -> None:
    execution = infer_task_execution_contract(
        "继续执行下一步",
        {
            "has_active_task": False,
            "task_execution_enabled": True,
            "request_replay_attempt_id": "attempt-final",
        },
    )
    assert execution.active is True
    assert execution.action == "replay"
    assert execution.phase == "terminal"
    assert execution.attempt_id == "attempt-final"
```

Add arbiter cases for create/inspect/manual update/skip precedence, explicit continue/retry/abort, negation, mixed intent, background passthrough, and feature disabled. Add contract invariants: inactive has no target/capabilities/attempt/budget; retry requires a runtime-resolved target; work allows only exact `read-only`; waiting/terminal cannot allow work capabilities; only one execution action is active.

- [ ] **Step 2: Run RED policy tests**

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_task_execution_contract.py \
  tests/test_task_control_arbiter.py \
  tests/test_task_execution_access.py \
  tests/test_tool_access_types.py -q
```

Expected: missing contract/policy failures.

- [ ] **Step 3: Implement immutable contract**

```python
# agent/policies/task_execution_contract.py
TaskExecutionAction = Literal[
    "inactive", "replay", "continue", "retry", "inspect", "abort"
]
TaskExecutionPhase = Literal[
    "inactive",
    "claim",
    "work",
    "waiting_authorization",
    "finish",
    "terminal",
]


@dataclass(frozen=True)
class TaskExecutionTurnContract:
    active: bool
    action: TaskExecutionAction
    phase: TaskExecutionPhase
    attempt_id: str | None
    target_step_id: str | None
    required_capabilities: frozenset[str]
    allowed_capabilities: frozenset[str]
    allowed_risks: frozenset[str]
    work_call_budget: int
    tool_search_budget: int
    completion_capability: str | None
    reason: str
    matched_terms: tuple[str, ...]

    @classmethod
    def inactive(cls) -> "TaskExecutionTurnContract":
        return cls(
            active=False,
            action="inactive",
            phase="inactive",
            attempt_id=None,
            target_step_id=None,
            required_capabilities=frozenset(),
            allowed_capabilities=frozenset(),
            allowed_risks=frozenset(),
            work_call_budget=0,
            tool_search_budget=0,
            completion_capability=None,
            reason="no_task_execution_intent",
            matched_terms=(),
        )
```

Implement `__post_init__` canonical validation equivalent in rigor to `TaskPlanTurnContract`.

Implement `TaskControlIntentArbiter` as the sole strict-contract selector. Runtime-confirmed request replay has highest priority and produces `action=replay, phase=terminal` even without an active plan. Text precedence then remains explicit TaskPlan create/inspect/manual update/skip, explicit execution retry/abort/continue, and generic LA-001 plan update. A losing contract is replaced with its canonical inactive value; contracts are never merged. The arbiter receives retryable step identity from runtime metadata, not from model tool arguments.

- [ ] **Step 4: Implement strict access plan**

Claim phase allows begin/inspect only. Work phase allows finish/defer/abort, scoped tool search, and read-only providers dynamically unlocked in this turn. Waiting allows inspect/abort only and schedules final-only. Required capability missing is fail closed with `task_execution_required_capability_missing`.

Merge rule: existing core disabled/access block remains stronger than execution allow; task execution strict scope must never weaken TaskPlan, Document RAG, or plugin core deny.

- [ ] **Step 5: Run GREEN contract/access tests**

Run Step 2 command.

Expected: all pass.

- [ ] **Step 6: Commit Task 6**

```bash
git add agent/policies/task_execution_contract.py \
  agent/policies/task_control_arbiter.py agent/policies/task_execution_access.py \
  agent/policies/tool_access_types.py \
  agent/policies/tool_access.py agent/policies/__init__.py \
  tests/test_task_execution_contract.py tests/test_task_control_arbiter.py \
  tests/test_task_execution_access.py \
  tests/test_tool_access_types.py
git commit -m "feat: add strict task execution turn contract"
```

---

## Task 7: Execution Tools, Shared Toolset Wiring, and Prompt Context

**Files:**

- Create: `agent/tools/task_execution.py`
- Create: `agent/tools/execution_context.py`
- Modify: `bootstrap/toolsets/task_plan.py`
- Modify: `bootstrap/tools.py`
- Modify: `bootstrap/wiring.py`
- Modify: `agent/task_plan/context.py`
- Modify: `agent/tools/registry.py`
- Modify: `agent/tools/base.py`
- Modify: `agent/tools/filesystem.py`
- Modify: `agent/tool_hooks/types.py`
- Modify: `agent/tool_hooks/executor.py`
- Test: `tests/test_task_execution_tools.py`
- Modify: `tests/test_task_plan_toolset.py`
- Modify: `tests/test_task_plan_context.py`
- Modify: `tests/test_bootstrap_toolsets_p1.py`
- Modify: `tests/test_tool_capabilities.py`
- Modify: `tests/test_tool_executor.py`
- Test: `tests/test_task_execution_tool_results.py`

**Interfaces:**

- Five tools from the approved design, all non-LRU.
- `TaskPlanToolsetProvider` receives one plan service and one execution service backed by the same store.
- `ToolExecutionContext(protected: Mapping[str, object], propagate_tool_errors: bool)` is immutable and passed per `ToolRegistry.execute()` call; request/action/target/attempt identity never enters the registry's retained `_context`.
- `ToolExecutionResult.invoker_reached` and `.invoker_succeeded` are runtime facts; pre-hook denial is false/false, invocation exception is true/false, return is true/true.
- `ToolResult.ok: bool | None` and `error_code: str` provide optional structured business success; legacy string results remain `ok=None` and cannot satisfy execution completion.
- `ToolRegistry.get_risks_by_name() -> dict[str, str]` returns copies of registered risk metadata for Gateway/Boundary decisions.

- [ ] **Step 1: Write failing tool/schema/context tests**

```python
import pytest

from agent.tools.base import Tool
from agent.tools.execution_context import ToolExecutionContext


class UnclassifiedTool(Tool):
    name = "unclassified"
    description = "Test tool with no risk classification."
    parameters = {"type": "object", "properties": {}}

    async def execute(self) -> str:
        return "ok"


def test_execution_tools_hide_protected_identity(execution_toolset) -> None:
    schemas = execution_toolset.registry.get_schemas()
    by_name = {item["function"]["name"]: item for item in schemas}
    begin = by_name["begin_task_step_execution"]
    finish = by_name["finish_task_step_execution"]
    assert "_task_execution_request_id" not in begin["function"]["parameters"]["properties"]
    assert "_task_execution_attempt_id" not in finish["function"]["parameters"]["properties"]


def test_execution_tools_are_non_lru(execution_toolset) -> None:
    assert {
        "begin_task_step_execution",
        "finish_task_step_execution",
        "request_task_step_authorization",
        "inspect_task_execution",
        "abort_task_step_execution",
    } <= execution_toolset.registry.get_non_lru_names()


def test_registry_risk_snapshot_is_internal_and_stable(execution_toolset) -> None:
    risks = execution_toolset.registry.get_risks_by_name()
    assert risks["read_file"] == "read-only"
    risks["read_file"] = "write"
    assert execution_toolset.registry.get_risks_by_name()["read_file"] == "read-only"


def test_unclassified_tool_is_unknown_not_read_only(execution_toolset) -> None:
    execution_toolset.registry.register(UnclassifiedTool())
    assert execution_toolset.registry.get_risks_by_name()["unclassified"] == "unknown"


@pytest.mark.asyncio
async def test_execution_identity_is_ephemeral_per_call(execution_toolset) -> None:
    first = ToolExecutionContext(
        protected={
            "_task_execution_request_id": "req-1",
            "_task_execution_attempt_id": "attempt-1",
        },
        propagate_tool_errors=True,
    )
    await execution_toolset.registry.execute(
        "inspect_task_execution",
        {},
        execution_context=first,
    )
    await execution_toolset.registry.execute(
        "inspect_task_execution",
        {},
        execution_context=ToolExecutionContext(
            protected={},
            propagate_tool_errors=True,
        ),
    )
    assert execution_toolset.inspect_calls[-1].attempt_id is None
    assert "_task_execution_attempt_id" not in execution_toolset.registry.get_context()


@pytest.mark.asyncio
async def test_throwing_tool_has_authoritative_invoker_failure(executor_fixture) -> None:
    result = await executor_fixture.execute_throwing_tool(
        execution_context=ToolExecutionContext(
            protected={},
            propagate_tool_errors=True,
        )
    )
    assert result.status == "error"
    assert result.invoker_reached is True
    assert result.invoker_succeeded is False


@pytest.mark.asyncio
async def test_pre_hook_deny_never_reaches_invoker(executor_fixture) -> None:
    result = await executor_fixture.execute_pre_hook_denied_tool()
    assert result.status == "denied"
    assert result.invoker_reached is False
    assert result.invoker_succeeded is False


def test_prompt_renders_only_current_attempt_summary(task_context_fixture) -> None:
    rendered = task_context_fixture.render()
    assert "Execution:" in rendered
    assert "waiting_authorization" in rendered
    assert "secret-value" not in rendered
    assert "old-attempt-event" not in rendered
```

- [ ] **Step 2: Run RED tool/context tests**

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_task_execution_tools.py \
  tests/test_task_plan_toolset.py \
  tests/test_task_plan_context.py \
  tests/test_bootstrap_toolsets_p1.py \
  tests/test_tool_capabilities.py \
  tests/test_tool_executor.py \
  tests/test_task_execution_tool_results.py -q
```

Expected: execution tools absent.

- [ ] **Step 3: Implement thin adapters**

```python
# agent/tools/task_execution.py
class BeginTaskStepExecutionTool(Tool):
    name = "begin_task_step_execution"
    description = (
        "Claim exactly one current TaskPlan step for controlled execution. "
        "This does not authorize write, shell, or external side effects."
    )
    capabilities = frozenset({"task_execution.begin"})

    async def execute(
        self,
        *,
        _session_key: str,
        _task_execution_request_id: str,
        _task_execution_action: str,
        _task_execution_target_step_id: str = "",
        description: str = "",
    ) -> dict[str, object]:
        if _task_execution_action == "retry":
            result = self._orchestrator.decide_retry(
                session_key=_session_key,
                request_id=_task_execution_request_id,
                step_id=_task_execution_target_step_id,
            )
        else:
            result = self._orchestrator.decide_continue(
                session_key=_session_key,
                request_id=_task_execution_request_id,
            )
        return {"ok": True, "error_code": "", "decision": result.to_dict()}
```

Implement finish/defer/inspect/abort with the same protected-context rule and stable payload keys `ok`, `error_code`, `attempt`, `events`, and `decision`. The begin adapter rejects unsupported/missing protected actions and retry without a protected target. Tool adapters catch typed service errors and map them to stable error codes; they do not query SQLite.

- [ ] **Step 4: Register shared services and bounded context**

Register control tools with risks:

```python
begin_tool = BeginTaskStepExecutionTool(orchestrator)
finish_tool = FinishTaskStepExecutionTool(execution_service)
defer_tool = RequestTaskStepAuthorizationTool(execution_service)
inspect_tool = InspectTaskExecutionTool(execution_service)
abort_tool = AbortTaskStepExecutionTool(execution_service)
tool_specs = (
    (begin_tool, "write"),
    (finish_tool, "write"),
    (defer_tool, "write"),
    (inspect_tool, "read-only"),
    (abort_tool, "write"),
)
```

All registrations use `always_on=False`, `non_lru=True`. Add execution summary to `TaskPlanPromptRenderModule` using `TaskExecutionService.inspect()` and cap the combined TaskPlan/execution block at the existing bound plus at most 400 execution chars.

Add `ToolRegistry.get_risks_by_name()` beside `get_capabilities_by_name()` and pass that snapshot through `ToolAccessContext`; never serialize the complete risk map into model-visible prompts. Change an omitted registry risk to authoritative `unknown` and audit production registrations so every intended read-only/write/external/destructive tool passes an explicit value. Add a compatibility test that the production registry has no accidental unknown entries while third-party/fixture tools without metadata remain unknown and therefore defer in execution scope.

Use these backward-compatible result fields:

```python
# agent/tools/base.py
@dataclass
class ToolResult:
    text: str = ""
    content_blocks: list[dict[str, Any]] = field(default_factory=list)
    ok: bool | None = None
    error_code: str = ""


# agent/tool_hooks/types.py
@dataclass
class ToolExecutionResult:
    status: ToolExecStatus
    output: Any
    final_arguments: dict[str, Any]
    invoker_reached: bool = False
    invoker_succeeded: bool = False
    extra_messages: list[str] = field(default_factory=_empty_str_list)
    pre_hook_trace: list[HookTraceItem] = field(default_factory=_empty_pre_trace)
    post_hook_trace: list[HookTraceItem] = field(default_factory=_empty_post_trace)
```

Every `ToolExecutor.execute()` return site sets invoker facts explicitly: pre-hook error/deny false/false, invoker exception true/false, normal return true/true. `preflight()` always returns false/false because it never invokes the tool.

Extend `ToolRegistry.execute(name, arguments, *, execution_context=None)` compatibly: merge existing public context, model arguments, existing protected session context, then the per-call `ToolExecutionContext.protected` at highest priority. Do not mutate `_context`; discard the execution context when the call returns. When `propagate_tool_errors=True`, re-raise tool exceptions so `ToolExecutor` records true/false instead of converting them to a success string; retain legacy wrapping for ordinary calls during this migration. Add cross-turn and cross-session tests proving an omitted attempt/action/target cannot reuse a previous value.

Extend `ToolExecutionResult` with invoker facts on every constructor path and `ToolResult` with optional `ok/error_code`. Runtime result classification uses explicit `ToolResult.ok`, or a JSON-object top-level boolean `ok`; plain strings are unknown. Migrate `ReadFileTool` and `ListDirTool` to return `ToolResult(ok=True)` on successful reads/listing and `ToolResult(ok=False, error_code=...)` on missing/invalid/binary/access errors without changing displayed text. Tests must prove successful README reads are true and missing-file strings are false, while pre-hook denial and thrown exceptions never become work success.

- [ ] **Step 5: Run GREEN tool/context tests**

Run Step 2 command.

Expected: all pass; existing three TaskPlan tools still share the same service and schema.

- [ ] **Step 6: Commit Task 7**

```bash
git add agent/tools/task_execution.py agent/tools/execution_context.py \
  bootstrap/toolsets/task_plan.py \
  bootstrap/tools.py bootstrap/wiring.py agent/task_plan/context.py \
  agent/tools/registry.py agent/tools/base.py agent/tools/filesystem.py \
  agent/tool_hooks/types.py agent/tool_hooks/executor.py \
  tests/test_task_execution_tools.py tests/test_tool_executor.py \
  tests/test_task_execution_tool_results.py \
  tests/test_task_plan_toolset.py tests/test_task_plan_context.py \
  tests/test_bootstrap_toolsets_p1.py tests/test_tool_capabilities.py
git commit -m "feat: expose controlled task execution tools"
```

---

## Task 8: Work Budget, Risk Enforcement, Event Ledger, and Completion

**Files:**

- Create: `agent/policies/task_execution_budget.py`
- Create: `agent/policies/task_execution_boundary.py`
- Create: `agent/policies/task_execution_completion.py`
- Modify: `agent/policies/tool_boundary.py`
- Modify: `agent/policies/turn_completion.py`
- Modify: `agent/policies/tool_ledger.py`
- Modify: `agent/tools/tool_search.py`
- Test: `tests/test_task_execution_budget.py`
- Test: `tests/test_task_execution_completion.py`
- Modify: `tests/test_tool_boundary_manager.py`

**Interfaces:**

- `TaskExecutionBudgetPolicy.evaluate(*, contract: TaskExecutionTurnContract, ledger: ToolCallLedger, tool_name: str, arguments: dict[str, object], tool_risk: str, tool_capabilities: Mapping[str, frozenset[str]]) -> ToolBoundaryDecision | None`.
- `TaskExecutionRiskPolicy.evaluate(*, contract, tool_name, registered, registry_risk) -> TaskExecutionRiskDecision | None` is pure and returns `allow`, `defer`, `deny`, or `unknown_tool`; it never persists state.
- `TaskExecutionCompletionPolicy.evaluate(*, contract: TaskExecutionTurnContract, snapshot: TaskExecutionSnapshot, ledger: ToolCallLedger, tool_capabilities: Mapping[str, frozenset[str]]) -> TurnCompletionDecision | None`.
- Work events are persisted only for calls that pass access/budget and reach executor.
- Tool search risk is runtime-enforced as exact read-only.

- [ ] **Step 1: Write failing risk, budget, event, and completion tests**

```python
def test_shell_is_deferred_even_when_command_looks_read_only(boundary_fixture) -> None:
    decision = boundary_fixture.evaluate(
        tool_name="shell",
        arguments={"command": "pwd"},
        registry_risk="external-side-effect",
    )
    assert decision.action == "soft_stop"
    assert decision.reason == "task_execution_authorization_required"
    assert boundary_fixture.executor_calls == []


def test_destructive_is_core_denied(boundary_fixture) -> None:
    decision = boundary_fixture.evaluate(
        tool_name="delete_workspace",
        arguments={},
        registry_risk="destructive",
    )
    assert decision.action == "block"
    assert decision.reason == "task_execution_destructive_denied"


def test_registered_write_returns_typed_defer_before_visibility_block(
    boundary_fixture,
) -> None:
    decision = boundary_fixture.evaluate(
        tool_name="write_file",
        arguments={"path": "x.txt", "content": "x"},
        registry_risk="write",
        visible=False,
    )
    assert decision.action == "defer"
    assert decision.execute is False
    assert decision.metadata["durable_transition"] == "waiting_authorization"


def test_finish_only_completes_after_persisted_work_event(completion_fixture) -> None:
    assert completion_fixture.evaluate_without_work_event() is None
    decision = completion_fixture.evaluate_after_successful_read_and_finish()
    assert decision.action == "final_only"
    assert decision.reason == "task_execution_attempt_succeeded"


def test_tool_search_never_counts_as_work(event_classifier) -> None:
    event = event_classifier.classify(
        tool_name="tool_search",
        tool_call_id="call-search",
        registry_risk="read-only",
        invoker_reached=True,
        invoker_succeeded=True,
        execution_status="success",
        result_ok=True,
    )
    assert event.counts_as_work is False
```

- [ ] **Step 2: Run RED boundary/completion tests**

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_task_execution_budget.py \
  tests/test_task_execution_completion.py \
  tests/test_tool_boundary_manager.py -q
```

Expected: missing policies and unsafe paths fail.

- [ ] **Step 3: Implement budget and risk decisions**

For an active work contract, apply registered-risk policy before ordinary schema visibility: unregistered name -> unknown-tool block; destructive -> core deny; shell or registered write/external/unknown -> typed defer; exact read-only continues through normal access and budget checks. Boundary remains pure and sets `execute=False`; it never calls execution service.

Count only real work tools toward `work_call_budget`; control tools and tool_search are separate. Count tool_search attempts regardless of hit/no-hit. Same tool + canonical arguments hash repeats soft-stop. In the same assistant batch, calls beyond remaining budget return `task_execution_batch_budget_skip` and never create a success event. Exhaustion returns typed `terminal_transition=failed` metadata for Task 9's coordinator; a soft-stop alone must not leave the attempt running.

Decision precedence:

```text
disabled/core access block
> destructive core deny
> task execution risk defer
> task execution search/work/repeat budget
> plugin soft governance
> allow
```

When a disallowed side-effect is proposed, return its typed defer decision to Task 9. RuntimeCoordinator must persist `authorization_deferred` and move the attempt to waiting before synthesizing the model result. If persistence fails, it never executes the requested tool and attempts a `blocked/defer_persistence_failed` transition.

- [ ] **Step 4: Enforce read-only tool search at runtime**

Do not trust model `allowed_risk`. For execution work phase, pass protected runtime search scope and intersect it inside ToolSearchTool/registry:

```python
effective_allowed_risk = ["read-only"] if execution_read_only else allowed_risk
```

Filter tool search results, newly unlocked schemas, and execution gate with the same registry risk snapshot. `shell` remains deferred by explicit name even if metadata is accidentally changed.

- [ ] **Step 5: Implement completion from durable state**

Completion fires only when attempt state is `succeeded`, `failed`, `blocked`, `cancelled`, or `waiting_authorization` and the corresponding durable transition was executed successfully. `succeeded` additionally requires finish capability and a persisted `counts_as_work=true`, exact-read-only, invoker-reached/succeeded, structured-result-ok event. Return tools empty for final-only and serialize bounded attempt metadata to trace. Pure boundary metadata or synthetic tool results can never trigger completion by themselves.

- [ ] **Step 6: Run GREEN boundary/completion tests**

Run Step 2 command.

Expected: all pass.

- [ ] **Step 7: Commit Task 8**

```bash
git add agent/policies/task_execution_budget.py \
  agent/policies/task_execution_boundary.py \
  agent/policies/task_execution_completion.py agent/policies/tool_boundary.py \
  agent/policies/turn_completion.py agent/policies/tool_ledger.py \
  agent/tools/tool_search.py tests/test_task_execution_budget.py \
  tests/test_task_execution_completion.py tests/test_tool_boundary_manager.py
git commit -m "feat: enforce task execution risk and completion boundaries"
```

---

## Task 9: DefaultReasoner Dynamic Execution Integration

**Files:**

- Create: `agent/task_plan/execution_runtime.py`
- Modify: `agent/core/passive_turn.py`
- Modify: `agent/core/runtime_support.py`
- Modify: `agent/policies/tool_access.py`
- Modify: `agent/policies/tool_boundary.py`
- Test: `tests/test_task_execution_reasoner.py`
- Test: `tests/test_task_execution_runtime.py`
- Test: `tests/test_task_execution_lru.py`
- Modify: `tests/test_tool_access_gateway_reasoner.py`

**Interfaces:**

- `DefaultReasoner` receives one `TaskExecutionRuntimeCoordinator`; it does not own attempt state or call execution SQL.
- `TaskExecutionRuntimeCoordinator.prepare_turn()`, `before_tool_call()`, `after_tool_call()`, `handle_model_final()`, and `finalize_turn()` are the only reasoner integration surface.
- `TaskExecutionLeaseGuard` renews via service at `lease_seconds/3` while an active attempt waits on LLM/executor and stops at terminal/waiting state.
- `ReasonerExecutionFixture.run_exit_scenario(kind)` is a test-only driver that creates a two-step plan, begins Step 1, injects the named LLM/hook/timeout/cancellation/max-iteration exit, and returns after coordinator finalization; its status/count accessors read the real SQLite store.
- `ReasonerExecutionFixture.complete_final_step()`, `replay_turn(request_id)`, and `attempt_for_request()` are test-only helpers backed by real service/store calls for terminal replay and post-claim fault injection; they do not mock persistence.
- Request identity is created once before retry plans.
- Contract phase and visible tools are recomputed after begin/defer/finish without changing AgentLoop.
- Successful real work calls append persistent events after executor result and before the next LLM call.

- [ ] **Step 1: Write failing end-to-end reasoner tests**

```python
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
async def test_defer_persistence_failure_never_executes_write(
    reasoner_fixture,
) -> None:
    reasoner_fixture.execution_service.fail_next_defer = True
    reasoner_fixture.llm.responses = [
        tool_call("begin_task_step_execution", {}),
        tool_call("write_file", {"path": "x.txt", "content": "x"}),
        final_reply("Execution was blocked"),
    ]
    await reasoner_fixture.run_turn("继续执行下一步")
    assert reasoner_fixture.write_executor_calls == []
    assert reasoner_fixture.attempt_status() == "blocked"


@pytest.mark.asyncio
async def test_fault_after_claim_commit_is_recovered_by_request(
    reasoner_fixture,
) -> None:
    reasoner_fixture.fail_after_claim_commit = True
    with pytest.raises(RuntimeError, match="after claim commit"):
        await reasoner_fixture.run_turn("继续执行下一步")
    attempt = reasoner_fixture.attempt_for_request()
    assert attempt.status == "blocked"
    assert reasoner_fixture.step_status(1) == "pending"


@pytest.mark.asyncio
async def test_terminal_replay_precedes_missing_active_plan(
    reasoner_fixture,
) -> None:
    request_id, attempt_id = reasoner_fixture.complete_final_step()
    result = await reasoner_fixture.replay_turn(request_id)
    assert result.context_retry["task_execution"]["request_replayed"] is True
    assert result.context_retry["task_execution"]["attempt_id"] == attempt_id
    assert reasoner_fixture.new_attempt_count == 0
```

Add a parameterized finalizer matrix with exact expectations:

```python
@pytest.mark.parametrize(
    ("exit_kind", "attempt_status", "step_status", "reason"),
    [
        ("provider_error", "blocked", "pending", "turn_interrupted_outcome_unknown"),
        ("timeout", "blocked", "pending", "turn_interrupted_outcome_unknown"),
        ("cancelled", "blocked", "pending", "turn_interrupted_outcome_unknown"),
        ("hook_error", "blocked", "pending", "turn_interrupted_outcome_unknown"),
        ("context_error_after_begin", "blocked", "pending", "turn_interrupted_outcome_unknown"),
        ("safety_error_after_begin", "blocked", "pending", "turn_interrupted_outcome_unknown"),
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
```

Add named end-to-end tests `test_terminal_request_replay_does_not_claim_next_step`, `test_recovery_blocked_continue_creates_no_attempt`, `test_explicit_retry_preserves_history_and_increments_attempt_no`, `test_inspect_then_abort_waiting_attempt`, `test_execution_disabled_is_not_discoverable`, `test_provider_missing_fails_closed`, `test_same_batch_calls_after_defer_are_skipped`, `test_lease_expiry_rejects_late_tool_result`, and `test_ordinary_task_plan_turn_remains_la001` using the same fixture APIs established in this task.

- [ ] **Step 2: Run RED reasoner tests**

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_task_execution_reasoner.py \
  tests/test_task_execution_runtime.py \
  tests/test_task_execution_lru.py \
  tests/test_tool_access_gateway_reasoner.py -q
```

Expected: execution integration absent.

- [ ] **Step 3: Add narrow run_turn preflight wiring**

Before safety/context retry loop, call `coordinator.prepare_turn()` in this exact order:

1. Ensure protected request ID once.
2. Call `execution_service.replay_request(session_key, request_id)` before active-plan lookup. A hit yields a terminal replay contract/snapshot immediately, even with no active plan; it never starts or claims.
3. Reconcile current session when no replay exists.
4. Load the owned active plan and call `find_retryable_step()` to populate typed `latest_retryable_step_id`; failed/recovery-blocked attempts are not inferred from active-attempt state.
5. Add `has_active_task`, `task_execution_enabled`, active attempt snapshot, runtime instance ID, and retry target to typed boundary inputs.
6. Infer TaskPlan and execution candidates.
7. Resolve them through `TaskControlIntentArbiter`; never pass two strict-active contracts to Gateway.

The runtime typed contract is stored in `ToolBoundaryContext`; `retry_trace` gets only `contract.to_trace_dict()`. Coordinator constructs a fresh `ToolExecutionContext` for every control/work call with request/action/target/attempt values and never calls `ToolRegistry.set_context()` for those fields.

- [ ] **Step 4: Add dynamic phase recomputation inside run()**

After a successful begin tool result, coordinator fetches the attempt snapshot, transitions pending to running through lease CAS, builds work-phase contract, and recomputes visibility through ToolAccessGateway. Before each call, `before_tool_call()` handles typed deny/defer/budget decisions; defer is persisted before any synthetic result. After every work result, `after_tool_call()` creates a frozen `RuntimeToolEvent` from registry snapshots plus `ToolExecutionResult.invoker_reached`, `invoker_succeeded`, and structured `result_ok`, then persists it before the next LLM call. After defer/finish/abort, recompute completion and call the next LLM with `tools=[]`.

Wrap only the execution-active section of `DefaultReasoner.run()` in coordinator finalization. `handle_model_final()` permits one protocol-correction round when work is running without finish; a second bare final marks failed. `finalize_turn()` maps provider/timeout/context/hook/cancellation/max-iteration exits to the exact table in the design and calls `service.block_attempt()` for current-owner unexpired pending/running attempts. If no local attempt is known, it first calls `replay_request(session_key, request_id)` to recover a claim committed before adapter-result handling. Expired leases use recovery reconcile. Finalization is idempotent if a durable finish/defer/abort already occurred and must not swallow the original runtime exception.

Integrate with the existing outer safety/context retry: before scheduling another `run()`, ask `coordinator.request_has_claimed_attempt(session_key, request_id)`. If false, existing retry behavior remains. If true, stop the outer ReAct retry, finalize/block once, and return the existing deterministic safety/context failure response under terminal/final-only scope. Never reuse the original claim-phase contract after an attempt exists.

Run `TaskExecutionLeaseGuard` around active-attempt LLM and executor awaits. Lease-renewal conflict stops further tool execution and transitions through the conservative blocked path; an expired owner never records a late success.

Do not persist execution work tools in discovery LRU: include all tools used while execution contract is active in the turn-local non-LRU update exclusion, without changing their global registry metadata.

- [ ] **Step 5: Add structured trace/log fields**

Use log tags from the design and add bounded trace:

```python
retry_trace["task_execution"] = {
    "attempt_id": snapshot.attempt.attempt_id,
    "action": contract.action,
    "phase": contract.phase,
    "status": snapshot.attempt.status,
    "work_tool_count": work_count,
    "work_tool_budget": contract.work_call_budget,
    "request_replayed": request_replayed,
    "reason": decision_reason,
}
```

No full arguments or result bodies in this metadata.

- [ ] **Step 6: Run GREEN reasoner tests**

Run Step 2 command.

Expected: all pass.

- [ ] **Step 7: Commit Task 9**

```bash
git add agent/task_plan/execution_runtime.py agent/core/passive_turn.py \
  agent/core/runtime_support.py \
  agent/policies/tool_access.py agent/policies/tool_boundary.py \
  tests/test_task_execution_reasoner.py tests/test_task_execution_runtime.py \
  tests/test_task_execution_lru.py \
  tests/test_tool_access_gateway_reasoner.py
git commit -m "feat: integrate controlled task execution into reasoner"
```

---

## Task 10: Compatibility, Full Verification, Live Smoke, and Documentation

**Files:**

- Modify affected existing tests listed in File Map.
- Modify: `my_md/local_agent/03-task-plan-recovery-execution-design.md`
- Modify: `my_md/local_agent/README.md`
- Modify governance issue/evolution/roadmap/decision/STAR docs.
- Modify interview notes/Q&A, `findings.md`, `progress.md`, `task_plan.md`.

**Interfaces:**

- Produces final evidence for LA-002a and LA-002b.
- Does not mark LA-002 fixed until automated, replay, restart, authorization-defer, and real CLI gates pass.

- [ ] **Step 1: Run LA-002 focused suites**

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_task_execution_models.py \
  tests/test_task_execution_redaction.py \
  tests/test_task_execution_config.py \
  tests/test_task_execution_store.py \
  tests/test_task_execution_service.py \
  tests/test_task_execution_request_identity.py \
  tests/test_task_execution_recovery.py \
  tests/test_task_control_arbiter.py \
  tests/test_task_execution_contract.py \
  tests/test_task_execution_access.py \
  tests/test_task_execution_budget.py \
  tests/test_task_execution_completion.py \
  tests/test_task_execution_tools.py \
  tests/test_task_execution_tool_results.py \
  tests/test_task_execution_runtime.py \
  tests/test_task_execution_reasoner.py \
  tests/test_task_execution_lru.py -q
```

Expected: all pass, no xfail for approved product decisions.

- [ ] **Step 2: Run compatibility suites**

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_task_plan_models.py \
  tests/test_task_plan_store.py \
  tests/test_task_plan_service.py \
  tests/test_task_plan_tools.py \
  tests/test_task_plan_toolset.py \
  tests/test_task_plan_contract.py \
  tests/test_task_plan_context_budget.py \
  tests/test_task_plan_gateway.py \
  tests/test_task_plan_context.py \
  tests/test_tool_access_gateway_reasoner.py \
  tests/test_tool_boundary_manager.py \
  tests/test_tool_executor.py \
  tests/test_turn_completion_reasoner.py \
  tests/test_doc_rag_intent_preload.py \
  tests/test_turn_trace_reasoner.py \
  tests/test_spawn_tool.py \
  tests/test_ipc_protocol.py \
  tests/test_io_modules.py \
  tests/test_channel_clients.py \
  tests/test_bootstrap_toolsets_p1.py \
  tests/test_bootstrap_wiring_p2.py \
  tests/test_runtime_smoke.py -q
```

Expected: all pass; TaskPlan 2-round create/inspect/update tests remain unchanged while execution is disabled.

- [ ] **Step 3: Run full verification**

```bash
uv run --with pytest --with pytest-asyncio pytest -q
uv run python -m compileall \
  agent/task_plan \
  agent/policies/task_control_arbiter.py \
  agent/policies/task_execution_contract.py \
  agent/policies/task_execution_access.py \
  agent/policies/task_execution_budget.py \
  agent/policies/task_execution_completion.py \
  agent/tools/task_execution.py \
  agent/tools/execution_context.py \
  agent/core/passive_turn.py
git diff --check
```

Expected: zero failures, compileall exit 0, diff check clean. Record exact counts/warnings.

- [ ] **Step 4: Run isolated real CLI smoke**

Use a dedicated config with `[task_execution] enabled=true`, unique socket/workspace/dashboard port, and do not disturb the user service.

Prompts:

```text
为检查项目状态创建两步计划：第一步读取 README.md 标题，第二步总结测试命令。只创建计划。
继续执行下一步
当前任务和执行尝试是什么状态？
```

Acceptance:

- Only Step 1 is claimed/completed; Step 2 remains pending.
- Chain is `begin -> read-only work -> finish -> final`, no write/shell.
- Execution-created work tools are not added to LRU.
- Observe and SQLite attempt/event records agree.
- The successful work event is `counts_as_work=true`; `tool_search` and control events are false.

- [ ] **Step 5: Verify request replay**

Send the same raw IPC v2 frame twice with one request ID. Acceptance: same attempt ID, one work execution, Step 2 remains pending. Then send a new request ID with the same text; acceptance: it is a distinct operation and may claim Step 2.

- [ ] **Step 6: Verify restart recovery**

Create a controlled running attempt in the isolated DB, terminate only the isolated Agent, restart it, and inspect. Acceptance: attempt blocked with `runtime_restarted_outcome_unknown`, step pending, no tool replay. Send ordinary “继续执行下一步” and verify no new attempt. Then send explicit retry and verify exactly one new attempt number.

- [ ] **Step 7: Verify side-effect defer**

Create a step requiring file modification and continue it. Acceptance: attempt waiting authorization; write/shell real execution count is zero; target file unchanged. Then explicitly abort and verify attempt cancelled, step pending, history retained.

- [ ] **Step 8: Verify turn-exit finalizer**

In the isolated runtime, inject one provider failure after begin and one model bare-final-without-finish scenario. Acceptance: provider failure leaves blocked/pending and propagates the original error; bare final receives at most one correction and then fails deterministically; neither case leaves a pending/running attempt.

- [ ] **Step 9: Update documents with facts only**

Record exact turn IDs, chains, ReAct iterations, tool counts, request replay behavior, recovery reason, SQLite rows, full pytest count, and remaining limitations. Do not mark side-effect execution implemented.

- [ ] **Step 10: Final review and commit**

Invoke `superpowers:requesting-code-review`, fix Critical/Important findings, rerun Step 3, then commit:

```bash
git add agent bootstrap infra tests my_md findings.md progress.md task_plan.md
git commit -m "feat: add recoverable controlled TaskPlan execution"
```

---

## Plan Self-Review Checklist

- [x] Every approved design decision maps to an implementation task and a negative test.
- [x] LA-002a can be reviewed before any work tool is enabled.
- [x] All public type and method names are consistent across tasks.
- [x] No model-controlled field can override session/request/attempt identity.
- [x] No text-hash deduplication exists.
- [x] No stale attempt auto-retry exists.
- [x] Recovery-blocked pending steps remain gated from ordinary continue.
- [x] Replay lookup occurs before active task/step selection and survives terminal/replaced plans.
- [x] Explicit retry is reachable through arbiter, protected target, begin adapter, orchestrator, and service.
- [x] Owner/status/unexpired-lease CAS protects all automatic mutations.
- [x] Runtime finalization has a dedicated atomic block transition distinct from finish-failure and stale reconcile.
- [x] Attempt/event/step/final-plan transitions are atomic and manual mutation conflicts are defined.
- [x] No write/external/unknown/shell automatic execution exists.
- [x] Destructive remains core denied.
- [x] Success requires a successful real work event plus finish.
- [x] Discovery/control/synthetic results are durably classified `counts_as_work=false`.
- [x] Completion evidence requires authoritative invoker-reached/succeeded and structured result success; registry exception strings cannot become success.
- [x] Typed defer is pure at Boundary and persisted by RuntimeCoordinator before any model result.
- [x] Every normal/error/cancel turn exit has a deterministic finalizer transition.
- [x] Post-claim/pre-result faults recover the attempt by request ID, and outer safety/context retries stop after claim.
- [x] Protected execution identity is per-call and cannot leak through retained ToolRegistry context.
- [x] TaskPlan and TaskExecution strict contracts have one deterministic arbiter.
- [x] Existing TaskPlan/Document RAG/Turn Trace/background paths retain regression coverage.
- [x] No TaskPlan execution state is added to AgentLoop, LRU, or ToolDiscoveryState.
