# TaskPlan Recovery and Controlled Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add recoverable, idempotent, single-step TaskPlan execution with durable attempts/events, conservative restart handling, and read-only-only automatic work.

**Architecture:** Keep TaskPlan SQLite as the durable fact boundary and add a separate immutable `TaskExecutionTurnContract` for current-turn authorization. `TaskExecutionService` owns session validation and state transitions; `TaskExecutionOrchestrator` claims one step; Tool Access Gateway, Turn Tool Boundary, ToolRegistry, and Turn Completion enforce visibility, risk, budget, evidence, and final-only without adding execution state to AgentLoop or LRU.

**Tech Stack:** Python 3.14 dataclasses and literals, SQLite transactions/partial indexes, existing ToolRegistry/Gateway/Boundary/Completion/DefaultReasoner, IPC v2, pytest/pytest-asyncio.

**Status:** Ready for implementation; approved product decisions are locked.

## Global Constraints

- The approved design is `my_md/local_agent/03-task-plan-recovery-execution-design.md` and is authoritative.
- First release auto-executes only tools whose registry risk is exactly `read-only`.
- `write`, `external-side-effect`, unknown risk, and every `shell` call defer to `waiting_authorization`; LA-002 never approves or executes them.
- `destructive` is a core deny and never becomes an approvable LA-002 request.
- Stale `pending/running` attempts become `blocked` with explicit unknown/interrupted reasons and never auto-retry.
- Same trusted transport request ID replays the original attempt; separate inbound requests remain separate operations; never deduplicate by message text.
- Failed steps require explicit retry or skip. Retry creates a new attempt and preserves old history.
- Automatic completion requires at least one successful real work-tool event plus a valid finish transition.
- One task and one step may each have at most one nonterminal attempt.
- One turn may claim at most one step and execute at most three real work-tool calls plus one scoped tool search.
- Do not modify AgentLoop control flow, TaskPlan always-on policy, or ToolDiscoveryState/LRU semantics.
- New control tools are deferred and `non_lru=True`.
- Runtime authorization comes from typed contracts and registry metadata, never serialized trace metadata or model arguments.
- Default `[task_execution] enabled=false`; existing TaskPlan create/inspect/update must work unchanged.
- Do not promise exactly-once external effects.

---

## File Map

**Create:**

- `agent/task_plan/execution_models.py`: attempt/event dataclasses, statuses, transition validation, IDs.
- `agent/task_plan/execution_store.py`: connection-scoped schema and SQL helpers used by `TaskPlanStore`.
- `agent/task_plan/execution_service.py`: session ownership, claim/replay, finish/defer/abort/inspect/event APIs.
- `agent/task_plan/orchestrator.py`: deterministic continue/retry decisions.
- `agent/task_plan/recovery.py`: startup/session reconciliation and runtime lease rules.
- `agent/task_plan/request_identity.py`: protected request ID and idempotency derivation.
- `agent/task_plan/execution_redaction.py`: canonical argument hash, recursive secret masking, and bounded previews.
- `agent/policies/task_execution_contract.py`: immutable action/phase/capability/risk contract.
- `agent/policies/task_execution_access.py`: strict access plan for claim/work/waiting/terminal phases.
- `agent/policies/task_execution_budget.py`: scoped search/work/repeat budget decisions.
- `agent/policies/task_execution_completion.py`: final-only after durable terminal/waiting transitions.
- `agent/tools/task_execution.py`: five thin task-execution tool adapters.
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

**Modify:**

- `agent/task_plan/models.py`: re-export-compatible execution type references only if needed; do not merge lifecycles.
- `agent/task_plan/store.py`: retain single DB/transaction ownership and delegate execution SQL helpers.
- `agent/task_plan/service.py`: expose owned-plan validation to execution service through a non-SQL boundary.
- `agent/task_plan/context.py`: render bounded current-attempt context.
- `agent/task_plan/__init__.py`: public execution exports.
- `agent/config_models.py`, `agent/config.py`: `TaskExecutionConfig` with safe validation.
- `agent/tools/registry.py`: protected request/attempt context and risk snapshot accessors.
- `agent/tools/tool_search.py`: runtime-enforced risk filter support without trusting model arguments.
- `bootstrap/toolsets/task_plan.py`: register execution tools using the same service/store identity.
- `bootstrap/toolsets/protocol.py`: carry execution service in toolset extras/deps only if required.
- `bootstrap/wiring.py`, `bootstrap/tools.py`: construct one execution service/recovery instance and run startup reconcile.
- `infra/channels/ipc_protocol.py`, `infra/channels/cli.py`, `infra/channels/ipc_server.py`: optional IPC v2 per-message request ID.
- `agent/policies/tool_access_types.py`, `agent/policies/tool_access.py`: typed execution contract in access context/plan.
- `agent/policies/tool_boundary.py`: compose execution access/budget with core-deny precedence.
- `agent/policies/turn_completion.py`: include execution completion policy.
- `agent/core/passive_turn.py`: narrow request/contract/phase/ledger wiring and dynamic visibility recomputation.
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
- Test: `tests/test_config.py`

**Interfaces:**

- Produces `AttemptStatus`, `ExecutionMode`, `ExecutionEventType`, `TaskExecutionAttempt`, `TaskExecutionEvent`, `TaskExecutionSnapshot`, and transition validators.
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
  tests/test_config.py -q
```

Expected: collection fails because `execution_models` and `TaskExecutionConfig` do not exist.

- [ ] **Step 3: Implement exact statuses and transition table**

```python
# agent/task_plan/execution_models.py
from __future__ import annotations

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
        return {
            **self.__dict__,
            "requested_arguments": dict(self.requested_arguments),
            "requested_capabilities": list(self.requested_capabilities),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class TaskExecutionEvent:
    event_id: str
    attempt_id: str
    sequence_no: int
    event_type: ExecutionEventType
    tool_name: str
    execution_status: str
    result_ok: bool | None
    error_code: str
    arguments_hash: str
    result_preview: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)


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
  tests/test_config.py
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

- `TaskPlanStore.claim_execution_attempt(*, task_id: str, step_id: str, session_key: str, request_id: str, idempotency_key: str, owner_instance_id: str, lease_expires_at: str, source_turn_id: int | None = None) -> AttemptClaimResult`.
- `TaskPlanStore.get_execution_attempt(attempt_id) -> TaskExecutionAttempt | None`.
- `TaskPlanStore.get_active_execution_attempt(task_id) -> TaskExecutionAttempt | None`.
- `TaskPlanStore.list_execution_attempts(task_id) -> list[TaskExecutionAttempt]`.
- `TaskPlanStore.list_recoverable_execution_attempts(session_key: str | None = None) -> list[TaskExecutionAttempt]`.
- `TaskPlanStore.renew_execution_attempt_lease(*, attempt_id: str, owner_instance_id: str, lease_expires_at: str) -> TaskExecutionAttempt`.
- `TaskPlanStore.list_execution_events(attempt_id) -> list[TaskExecutionEvent]`.
- `TaskPlanStore.transition_execution_attempt(*, attempt_id: str, target_status: AttemptStatus, result_summary: str = "", error_code: str = "", terminal_reason: str = "") -> TaskExecutionAttempt`.
- `TaskPlanStore.append_execution_event(*, attempt_id: str, event_type: ExecutionEventType, tool_name: str = "", execution_status: str = "", result_ok: bool | None = None, error_code: str = "", arguments_hash: str = "", result_preview: str = "", metadata: dict[str, object] | None = None) -> TaskExecutionEvent`.
- All cross-table updates share the existing `TaskPlanStore` lock and connection.

- [ ] **Step 1: Write failing migration, replay, and concurrency tests**

```python
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

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
    store = TaskPlanStore(tmp_path / "task.db")
    plan = store.create_plan(
        session_key="cli:s1",
        title="Read project",
        step_titles=["Read README"],
    )

    def claim(index: int) -> tuple[str, str]:
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

The second test defines the public behavior: a racing different request returns the already-active attempt with `active_conflict`; it does not create a second row and must not be labeled replay.

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

Use `BEGIN IMMEDIATE` and this ordering inside `claim_execution_attempt()`:

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

`transition_execution_attempt()` must validate the transition before SQL, update attempt and TaskStep atomically, and append exactly one transition event in the same transaction.

`renew_execution_attempt_lease()` updates only a pending/running attempt owned by the same runtime. A stale or foreign owner raises a typed conflict; it never steals ownership.

- [ ] **Step 5: Run GREEN and existing store regressions**

Run the Step 2 command.

Expected: all pass; existing plan schema and one-active-plan behavior remain unchanged.

- [ ] **Step 6: Commit Task 2**

```bash
git add agent/task_plan/execution_store.py agent/task_plan/store.py \
  tests/test_task_execution_store.py tests/test_task_plan_store.py
git commit -m "feat: persist task execution attempts and events"
```

**LA-002a checkpoint:** persistence can now model attempts and enforce uniqueness, but no runtime tool execution is enabled.

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

- `TaskExecutionService.begin_next_step(*, session_key: str, request_id: str, runtime_instance_id: str, source_turn_id: int | None = None) -> BeginExecutionResult`.
- `TaskExecutionService.retry_step(*, session_key: str, step_id: str, request_id: str, runtime_instance_id: str, source_turn_id: int | None = None) -> BeginExecutionResult`.
- `TaskExecutionService.start_attempt(*, session_key: str, attempt_id: str) -> TaskExecutionSnapshot`.
- `TaskExecutionService.record_tool_event(*, session_key: str, attempt_id: str, event_type: ExecutionEventType, tool_name: str, execution_status: str, result_ok: bool | None, error_code: str, arguments_hash: str, result_preview: str) -> TaskExecutionEvent`.
- `TaskExecutionService.finish_attempt(*, session_key: str, attempt_id: str, success: bool, result_summary: str, error_code: str = "") -> TaskExecutionSnapshot`.
- `TaskExecutionService.defer_attempt(*, session_key: str, attempt_id: str, tool_name: str, requested_arguments: dict[str, object], requested_capabilities: tuple[str, ...], reason: str) -> TaskExecutionSnapshot`.
- `TaskExecutionService.abort_attempt(*, session_key: str, attempt_id: str, reason: str) -> TaskExecutionSnapshot`.
- `TaskExecutionService.inspect(*, session_key: str, attempt_id: str | None = None) -> TaskExecutionSnapshot`.
- `TaskExecutionOrchestrator.decide_continue(*, session_key: str, request_id: str, runtime_instance_id: str, source_turn_id: int | None = None) -> ExecutionOrchestrationDecision`.
- `TaskExecutionOrchestrator.decide_retry(*, session_key: str, step_id: str, request_id: str, runtime_instance_id: str, source_turn_id: int | None = None) -> ExecutionOrchestrationDecision`.
- `derive_task_execution_idempotency_key(*, session_key: str, request_id: str, task_id: str, step_id: str, action: str) -> str`.

- [ ] **Step 1: Write failing ownership, selection, replay, retry, and finish tests**

```python
def test_continue_selects_only_lowest_pending_step(execution_service) -> None:
    plan = execution_service.plan_service.create_task_plan(
        session_key="cli:s1",
        title="Two steps",
        steps=["Read README", "Summarize tests"],
    )
    result = execution_service.begin_next_step(
        session_key="cli:s1",
        request_id="req-1",
        runtime_instance_id="runtime-1",
    )
    assert result.attempt.step_id == plan.steps[0].step_id
    assert result.replayed is False


def test_continue_does_not_skip_failed_step(execution_service) -> None:
    result = execution_service.begin_next_step(
        session_key="cli:s1",
        request_id="req-2",
        runtime_instance_id="runtime-1",
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
            runtime_instance_id="runtime-1",
        )


def test_finish_success_requires_successful_work_event(execution_service) -> None:
    result = execution_service.begin_next_step(
        session_key="cli:s1",
        request_id="req-1",
        runtime_instance_id="runtime-1",
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
        runtime_instance_id="runtime-1",
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
        runtime_instance_id="runtime-1",
    )
    assert result.step.index == 2
```

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
    def __init__(self, plan_service: TaskPlanService, store: TaskPlanStore) -> None:
        self.plan_service = plan_service
        self._store = store
```

Add a public `require_owned_task_plan()` wrapper to `TaskPlanService` that delegates to its existing private ownership check; do not expose raw store rows.

`begin_next_step()` rules, in order:

1. Require owned active plan.
2. If an active attempt exists, return it only for matching request replay; otherwise return `attempt_already_active` conflict.
3. If any step is failed, raise `failed_step_requires_explicit_retry`.
4. Select lowest-index pending step.
5. If none exists, raise `no_pending_step`.
6. Derive idempotency through `request_identity.py` and call atomic store claim.

`start_attempt()` validates ownership and performs the only legal `pending -> running` transition. It also changes the selected Step from pending to in_progress and appends `attempt_started` in the same transaction.

`finish_attempt(success=True)` must query events and require at least one `tool_finished` event with `execution_status=success` and `result_ok=True` whose tool is not a task-execution control tool.

Every `record_tool_event()` and `defer_attempt()` call must use Task 1 redaction/hash/preview helpers before persistence. Full raw arguments never enter ordinary attempt events or observe metadata.

`record_tool_event()` renews the attempt lease before `tool_started` and again after `tool_finished`, using the configured lease duration and current runtime owner.

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

- `TaskExecutionRecoveryService(runtime_instance_id, service, clock)`.
- `reconcile_startup() -> tuple[RecoveryResult, ...]`.
- `reconcile_session(session_key) -> tuple[RecoveryResult, ...]`.
- `RecoveryResult(attempt_id, previous_status, current_status, reason, step_reset)`.

- [ ] **Step 1: Write failing restart, lease, waiting, and no-replay tests**

```python
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
        runtime_instance_id: str,
        service: TaskExecutionService,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._runtime_instance_id = runtime_instance_id
        self._service = service
        self._now = now or (lambda: datetime.now(UTC))

    def reconcile_session(self, session_key: str) -> tuple[RecoveryResult, ...]:
        return self._service.reconcile_attempts(
            session_key=session_key,
            runtime_instance_id=self._runtime_instance_id,
            now=self._now(),
        )
```

Store reconciliation rules must be one transaction per batch. Do not modify `waiting_authorization` or terminal attempts. For stale running reset only a still-`in_progress` step to pending; never overwrite completed/skipped.

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

**LA-002a complete checkpoint:** run Tasks 1-5 tests and review migration, replay, and recovery before enabling any execution tool.

---

## Task 6: Typed Execution Contract and Access Policy

**Files:**

- Create: `agent/policies/task_execution_contract.py`
- Create: `agent/policies/task_execution_access.py`
- Modify: `agent/policies/tool_access_types.py`
- Modify: `agent/policies/tool_access.py`
- Modify: `agent/policies/__init__.py`
- Test: `tests/test_task_execution_contract.py`
- Test: `tests/test_task_execution_access.py`
- Test: `tests/test_tool_access_types.py`

**Interfaces:**

- `TaskExecutionTurnContract.inactive()` canonical inactive value.
- `infer_task_execution_contract(user_text, metadata) -> TaskExecutionTurnContract`.
- `TaskExecutionAccessPolicy.plan(context) -> ToolAccessPlan`.
- `ToolAccessPlan.task_execution_contract` is typed runtime state; `policy_metadata` stays trace-only.
- `ToolAccessContext.tool_risks` is a runtime snapshot from `ToolRegistry.get_risks_by_name()`, not model/tool-search output.

- [ ] **Step 1: Write failing contract precedence/invariant tests**

```python
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
```

Add invariants: inactive has no capabilities/attempt/budget; work allows only exact `read-only`; waiting/terminal cannot allow work capabilities; only one execution action is active.

- [ ] **Step 2: Run RED policy tests**

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_task_execution_contract.py \
  tests/test_task_execution_access.py \
  tests/test_tool_access_types.py -q
```

Expected: missing contract/policy failures.

- [ ] **Step 3: Implement immutable contract**

```python
# agent/policies/task_execution_contract.py
TaskExecutionAction = Literal["inactive", "continue", "retry", "inspect", "abort"]
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

- [ ] **Step 4: Implement strict access plan**

Claim phase allows begin/inspect only. Work phase allows finish/defer/abort, scoped tool search, and read-only providers dynamically unlocked in this turn. Waiting allows inspect/abort only and schedules final-only. Required capability missing is fail closed with `task_execution_required_capability_missing`.

Merge rule: existing core disabled/access block remains stronger than execution allow; task execution strict scope must never weaken TaskPlan, Document RAG, or plugin core deny.

- [ ] **Step 5: Run GREEN contract/access tests**

Run Step 2 command.

Expected: all pass.

- [ ] **Step 6: Commit Task 6**

```bash
git add agent/policies/task_execution_contract.py \
  agent/policies/task_execution_access.py agent/policies/tool_access_types.py \
  agent/policies/tool_access.py agent/policies/__init__.py \
  tests/test_task_execution_contract.py tests/test_task_execution_access.py \
  tests/test_tool_access_types.py
git commit -m "feat: add strict task execution turn contract"
```

---

## Task 7: Execution Tools, Shared Toolset Wiring, and Prompt Context

**Files:**

- Create: `agent/tools/task_execution.py`
- Modify: `bootstrap/toolsets/task_plan.py`
- Modify: `bootstrap/tools.py`
- Modify: `bootstrap/wiring.py`
- Modify: `agent/task_plan/context.py`
- Modify: `agent/tools/registry.py`
- Test: `tests/test_task_execution_tools.py`
- Modify: `tests/test_task_plan_toolset.py`
- Modify: `tests/test_task_plan_context.py`
- Modify: `tests/test_bootstrap_toolsets_p1.py`
- Modify: `tests/test_tool_capabilities.py`

**Interfaces:**

- Five tools from the approved design, all non-LRU.
- `TaskPlanToolsetProvider` receives one plan service and one execution service backed by the same store.
- Registry protected context includes `_task_execution_request_id` and `_task_execution_attempt_id` but these never appear in schemas.
- `ToolRegistry.get_risks_by_name() -> dict[str, str]` returns copies of registered risk metadata for Gateway/Boundary decisions.

- [ ] **Step 1: Write failing tool/schema/context tests**

```python
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
  tests/test_tool_capabilities.py -q
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
        description: str = "",
    ) -> dict[str, object]:
        result = self._orchestrator.decide_continue(
            session_key=_session_key,
            request_id=_task_execution_request_id,
            runtime_instance_id=self._runtime_instance_id,
        )
        return {"ok": True, "error_code": "", "decision": result.to_dict()}
```

Implement finish/defer/inspect/abort with the same protected-context rule and stable payload keys `ok`, `error_code`, `attempt`, `events`, and `decision`. Tool adapters catch typed service errors and map them to stable error codes; they do not query SQLite.

- [ ] **Step 4: Register shared services and bounded context**

Register control tools with risks:

```python
begin_tool = BeginTaskStepExecutionTool(orchestrator, runtime_instance_id)
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

Add `ToolRegistry.get_risks_by_name()` beside `get_capabilities_by_name()` and pass that snapshot through `ToolAccessContext`; never serialize the complete risk map into model-visible prompts.

- [ ] **Step 5: Run GREEN tool/context tests**

Run Step 2 command.

Expected: all pass; existing three TaskPlan tools still share the same service and schema.

- [ ] **Step 6: Commit Task 7**

```bash
git add agent/tools/task_execution.py bootstrap/toolsets/task_plan.py \
  bootstrap/tools.py bootstrap/wiring.py agent/task_plan/context.py \
  agent/tools/registry.py tests/test_task_execution_tools.py \
  tests/test_task_plan_toolset.py tests/test_task_plan_context.py \
  tests/test_bootstrap_toolsets_p1.py tests/test_tool_capabilities.py
git commit -m "feat: expose controlled task execution tools"
```

---

## Task 8: Work Budget, Risk Enforcement, Event Ledger, and Completion

**Files:**

- Create: `agent/policies/task_execution_budget.py`
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


def test_finish_only_completes_after_persisted_work_event(completion_fixture) -> None:
    assert completion_fixture.evaluate_without_work_event() is None
    decision = completion_fixture.evaluate_after_successful_read_and_finish()
    assert decision.action == "final_only"
    assert decision.reason == "task_execution_attempt_succeeded"
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

Count only real work tools toward `work_call_budget`; control tools and tool_search are separate. Count tool_search attempts regardless of hit/no-hit. Same tool + canonical arguments hash repeats soft-stop. In the same assistant batch, calls beyond remaining budget return `task_execution_batch_budget_skip` and never create a success event.

Decision precedence:

```text
disabled/core access block
> destructive core deny
> task execution risk defer
> task execution search/work/repeat budget
> plugin soft governance
> allow
```

When a disallowed side-effect is proposed, persist `authorization_deferred` and move attempt to waiting before returning the model result.

- [ ] **Step 4: Enforce read-only tool search at runtime**

Do not trust model `allowed_risk`. For execution work phase, pass protected runtime search scope and intersect it inside ToolSearchTool/registry:

```python
effective_allowed_risk = ["read-only"] if execution_read_only else allowed_risk
```

Filter tool search results, newly unlocked schemas, and execution gate with the same registry risk snapshot. `shell` remains deferred by explicit name even if metadata is accidentally changed.

- [ ] **Step 5: Implement completion from durable state**

Completion fires only when attempt state is `succeeded`, `failed`, `blocked`, `cancelled`, or `waiting_authorization` and the corresponding transition was executed successfully. `succeeded` additionally requires finish capability and successful event evidence. Return tools empty for final-only and serialize bounded attempt metadata to trace.

- [ ] **Step 6: Run GREEN boundary/completion tests**

Run Step 2 command.

Expected: all pass.

- [ ] **Step 7: Commit Task 8**

```bash
git add agent/policies/task_execution_budget.py \
  agent/policies/task_execution_completion.py agent/policies/tool_boundary.py \
  agent/policies/turn_completion.py agent/policies/tool_ledger.py \
  agent/tools/tool_search.py tests/test_task_execution_budget.py \
  tests/test_task_execution_completion.py tests/test_tool_boundary_manager.py
git commit -m "feat: enforce task execution risk and completion boundaries"
```

---

## Task 9: DefaultReasoner Dynamic Execution Integration

**Files:**

- Modify: `agent/core/passive_turn.py`
- Modify: `agent/core/runtime_support.py`
- Modify: `agent/policies/tool_access.py`
- Modify: `agent/policies/tool_boundary.py`
- Test: `tests/test_task_execution_reasoner.py`
- Test: `tests/test_task_execution_lru.py`
- Modify: `tests/test_tool_access_gateway_reasoner.py`

**Interfaces:**

- `DefaultReasoner` receives `TaskExecutionService`, `TaskExecutionRecoveryService`, runtime instance ID, and config through constructor wiring.
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
```

Also add tests for request replay, failed-step explicit retry, inspect/abort, discovery disabled, provider missing fail-closed, work budget, same-batch skip, and ordinary TaskPlan turns.

- [ ] **Step 2: Run RED reasoner tests**

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_task_execution_reasoner.py \
  tests/test_task_execution_lru.py \
  tests/test_tool_access_gateway_reasoner.py -q
```

Expected: execution integration absent.

- [ ] **Step 3: Add narrow run_turn preflight wiring**

Before safety/context retry loop:

1. Ensure protected request ID once.
2. Reconcile current session.
3. Add `has_active_task`, `task_execution_enabled`, active attempt snapshot, and runtime instance ID to typed boundary inputs.
4. Infer execution contract independently from TaskPlan contract.
5. Reject simultaneous strict-active contracts through precedence, not merge guessing.

The runtime typed contract is stored in `ToolBoundaryContext`; `retry_trace` gets only `contract.to_trace_dict()`.

- [ ] **Step 4: Add dynamic phase recomputation inside run()**

After a successful begin tool result, fetch the attempt snapshot, transition pending to running, build work-phase contract, and recompute visibility through ToolAccessGateway. After every real work result, append a persistent event using protected attempt ID and executor status. After defer/finish/abort, recompute completion and call the next LLM with `tools=[]`.

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
git add agent/core/passive_turn.py agent/core/runtime_support.py \
  agent/policies/tool_access.py agent/policies/tool_boundary.py \
  tests/test_task_execution_reasoner.py tests/test_task_execution_lru.py \
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
  tests/test_task_execution_store.py \
  tests/test_task_execution_service.py \
  tests/test_task_execution_request_identity.py \
  tests/test_task_execution_recovery.py \
  tests/test_task_execution_contract.py \
  tests/test_task_execution_access.py \
  tests/test_task_execution_budget.py \
  tests/test_task_execution_completion.py \
  tests/test_task_execution_tools.py \
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
  agent/policies/task_execution_contract.py \
  agent/policies/task_execution_access.py \
  agent/policies/task_execution_budget.py \
  agent/policies/task_execution_completion.py \
  agent/tools/task_execution.py \
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

- [ ] **Step 5: Verify request replay**

Send the same raw IPC v2 frame twice with one request ID. Acceptance: same attempt ID, one work execution, Step 2 remains pending. Then send a new request ID with the same text; acceptance: it is a distinct operation and may claim Step 2.

- [ ] **Step 6: Verify restart recovery**

Create a controlled running attempt in the isolated DB, terminate only the isolated Agent, restart it, and inspect. Acceptance: attempt blocked with `runtime_restarted_outcome_unknown`, step pending, no tool replay.

- [ ] **Step 7: Verify side-effect defer**

Create a step requiring file modification and continue it. Acceptance: attempt waiting authorization; write/shell real execution count is zero; target file unchanged. Then explicitly abort and verify attempt cancelled, step pending, history retained.

- [ ] **Step 8: Update documents with facts only**

Record exact turn IDs, chains, ReAct iterations, tool counts, request replay behavior, recovery reason, SQLite rows, full pytest count, and remaining limitations. Do not mark side-effect execution implemented.

- [ ] **Step 9: Final review and commit**

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
- [x] No write/external/unknown/shell automatic execution exists.
- [x] Destructive remains core denied.
- [x] Success requires a successful real work event plus finish.
- [x] Existing TaskPlan/Document RAG/Turn Trace/background paths retain regression coverage.
- [x] No TaskPlan execution state is added to AgentLoop, LRU, or ToolDiscoveryState.
