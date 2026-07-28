# Tool Governance P4c Audit Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a workspace-scoped, queryable, persistent, redacted `ToolAuditLedger` for P1-P4b tool governance events without expanding tool execution capability.

**Architecture:** Add `agent/policies/tool_audit_ledger.py` as a sidecar SQLite audit projection at `<workspace>/tool_audit/tool_audit.db`. Existing approval and side-effect stores remain source-of-truth; runtime surfaces write bounded ledger events fail-open.

**Tech Stack:** Python dataclasses, stdlib `sqlite3`, existing `ToolExecutor`, `ToolApprovalRuntime`, approved file/shell side-effect runtimes, status command plugin, pytest.

## Global Constraints

- Do not implement external API side-effect replay.
- Do not implement destructive operation execution.
- Do not implement shell rollback.
- Do not implement TaskExecution shell or external side-effect resume.
- Do not enable network-enabled shell sandbox.
- Do not store raw tool arguments, raw shell command, raw file path, raw file content, raw diff text, payload path, stdout/stderr text, token, cookie, secret, authorization, or API key values in the ledger.
- Ledger write failure must not change tool execution status, approval consumption/finalization status, or side-effect runtime status.
- `docs/` is ignored by `.gitignore`; force-stage plan/spec/doc files with `git add -f`.

---

## File Structure

- Create `agent/policies/tool_audit_ledger.py`: SQLite schema, event/query dataclasses, allowlisted metadata sanitizer, query/prune API, fail-open recorder helper.
- Modify `agent/tool_hooks/executor.py`: accept optional ledger store and record `tool_invocation_policy_decision` for allow/deny/defer/error outcomes.
- Modify `agent/core/passive_turn.py`: create workspace ledger store and inject it into `ToolApprovalRuntime` and `ToolExecutor`.
- Modify `agent/policies/tool_approval_runtime.py`: accept optional ledger store and record requested/approved/denied/expired/consumed/executed/execution_failed lifecycle events.
- Modify `agent/policies/approved_side_effect_runtime.py`: accept optional ledger store and record file payload/preview/execution/rollback lifecycle events.
- Modify `agent/policies/approved_shell_side_effect_runtime.py`: accept optional ledger store and record shell payload/preview/sandbox execution lifecycle events.
- Modify `plugins/status_commands/plugin.py`: create/pass ledger store, add `/tool_audit` trusted read-only query command, and route approval status commands through a ledger-aware runtime.
- Modify `plugins/status_commands/README.md`: document `/tool_audit`.
- Test `tests/test_tool_audit_ledger.py`: focused ledger schema/query/redaction/prune tests.
- Modify `tests/test_tool_executor.py`: executor ledger fail-open and allow/deny/defer coverage.
- Modify `tests/test_tool_approval_runtime.py`: approval lifecycle ledger coverage.
- Modify `tests/test_approved_side_effect_runtime.py`: file lifecycle ledger coverage.
- Modify `tests/test_approved_shell_side_effect_runtime.py`: shell lifecycle ledger coverage.
- Modify `tests/test_status_commands_approved_side_effects.py`: `/tool_audit` command coverage.
- Modify `tests/test_tool_governance_p4b_contract.py`: shell raw command absence and bounded sandbox metadata contract.
- Modify governance docs under `my_md/governance/04-fix-roadmap.md` and `my_md/governance/08-tool-invocation-policy-p1-status.md`.

---

### Task 1: Ledger Store And Bounded Event Model

**Files:**
- Create: `agent/policies/tool_audit_ledger.py`
- Create: `tests/test_tool_audit_ledger.py`

**Interfaces:**
- Produces: `ToolAuditLedgerEvent`, `ToolAuditLedgerQuery`, `ToolAuditLedgerStore`, `sanitize_tool_audit_metadata(...)`, `record_tool_audit_event_fail_open(...)`.
- Consumes: stdlib `sqlite3`, `datetime`, `uuid`, `logging`.

- [ ] **Step 1: Write the failing tests**

Add `tests/test_tool_audit_ledger.py`:

```python
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from agent.policies.tool_audit_ledger import (
    ToolAuditLedgerEvent,
    ToolAuditLedgerQuery,
    ToolAuditLedgerStore,
    sanitize_tool_audit_metadata,
)


def _event(**overrides: object) -> ToolAuditLedgerEvent:
    values = {
        "created_at": datetime(2026, 7, 28, 1, 0, tzinfo=UTC),
        "event_type": "tool_invocation_policy_decision",
        "session_key": "cli:one",
        "request_id": "call-1",
        "tool_name": "write_file",
        "source": "passive",
        "risk": "write",
        "policy_action": "defer",
        "policy_reason": "risk_strategy_write_requires_approval",
        "args_hash": "hash-1",
        "metadata": {"resource_type": "workspace"},
    }
    values.update(overrides)
    return ToolAuditLedgerEvent(**values)


def test_ledger_records_and_queries_by_core_fields(tmp_path) -> None:
    store = ToolAuditLedgerStore(tmp_path / "tool_audit.db")
    recorded = store.record_event(_event(approval_request_id="approval-1"))
    store.record_event(
        _event(
            request_id="call-2",
            approval_request_id="approval-2",
            tool_name="shell",
            event_type="tool_approval_consumed",
        )
    )

    assert recorded.event_id
    assert store.query_events(ToolAuditLedgerQuery(session_key="cli:one", limit=10))[0].event_id
    assert [event.request_id for event in store.query_events(ToolAuditLedgerQuery(request_id="call-1"))] == ["call-1"]
    assert [event.approval_request_id for event in store.query_events(ToolAuditLedgerQuery(approval_request_id="approval-2"))] == ["approval-2"]
    assert [event.tool_name for event in store.query_events(ToolAuditLedgerQuery(tool_name="shell"))] == ["shell"]
    assert [event.event_type for event in store.query_events(ToolAuditLedgerQuery(event_type="tool_approval_consumed"))] == ["tool_approval_consumed"]


def test_ledger_sanitizes_metadata_allowlist(tmp_path) -> None:
    metadata = sanitize_tool_audit_metadata(
        {
            "resource_type": "workspace",
            "exit_code": 2,
            "stdout_hash": "abc",
            "command": "rm -rf secret",
            "path": "/tmp/secret.txt",
            "content": "secret body",
            "payload_path": "/vault/payload.json",
            "authorization": "Bearer secret",
            "cookie": "session=secret",
            "nested": {"token": "secret"},
        }
    )
    assert metadata == {
        "resource_type": "workspace",
        "exit_code": 2,
        "stdout_hash": "abc",
    }

    store = ToolAuditLedgerStore(tmp_path / "tool_audit.db")
    store.record_event(_event(metadata=metadata))
    raw = store._connect().execute("SELECT metadata_json FROM tool_audit_events").fetchone()[0]
    serialized = json.dumps(json.loads(raw), sort_keys=True)
    assert "rm -rf" not in serialized
    assert "secret.txt" not in serialized
    assert "secret body" not in serialized
    assert "Bearer secret" not in serialized


def test_ledger_enforces_limit_and_prunes(tmp_path) -> None:
    store = ToolAuditLedgerStore(tmp_path / "tool_audit.db")
    base = datetime(2026, 7, 28, 1, 0, tzinfo=UTC)
    for index in range(6):
        store.record_event(_event(created_at=base + timedelta(minutes=index), request_id=f"call-{index}"))

    assert len(store.query_events(ToolAuditLedgerQuery(limit=500))) == 6
    assert [event.request_id for event in store.query_events(ToolAuditLedgerQuery(limit=2))] == ["call-5", "call-4"]
    assert store.prune(before=base + timedelta(minutes=2), max_rows=None) == 2
    assert len(store.query_events(ToolAuditLedgerQuery(limit=20))) == 4
    assert store.prune(before=None, max_rows=2) == 2
    assert [event.request_id for event in store.query_events(ToolAuditLedgerQuery(limit=20))] == ["call-5", "call-4"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_tool_audit_ledger.py -q -p no:cacheprovider
```

Expected: fail with `ModuleNotFoundError: No module named 'agent.policies.tool_audit_ledger'`.

- [ ] **Step 3: Implement the store**

Create `agent/policies/tool_audit_ledger.py` with these public shapes:

```python
@dataclass(frozen=True)
class ToolAuditLedgerEvent:
    event_type: str
    created_at: datetime | str | None = None
    event_id: str = ""
    session_key: str = ""
    channel: str = ""
    chat_id: str = ""
    request_id: str = ""
    turn_id: str = ""
    tool_name: str = ""
    source: str = ""
    risk: str = ""
    policy_action: str = ""
    policy_reason: str = ""
    approval_request_id: str = ""
    approval_scope: str = ""
    approval_status: str = ""
    side_effect_status: str = ""
    execution_status: str = ""
    rollback_status: str = ""
    actor: str = ""
    args_hash: str = ""
    invoker_reached: bool = False
    invoker_succeeded: bool = False
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolAuditLedgerQuery:
    session_key: str = ""
    request_id: str = ""
    approval_request_id: str = ""
    tool_name: str = ""
    event_type: str = ""
    since: datetime | str | None = None
    until: datetime | str | None = None
    limit: int = 50


class ToolAuditLedgerStore:
    @staticmethod
    def db_path_from_workspace(workspace: str | Path) -> Path: ...
    def record_event(self, event: ToolAuditLedgerEvent) -> ToolAuditLedgerEvent: ...
    def query_events(self, query: ToolAuditLedgerQuery) -> list[ToolAuditLedgerEvent]: ...
    def prune(self, *, before: datetime | None, max_rows: int | None) -> int: ...
```

Implementation requirements:

- Create table `tool_audit_events` with the columns listed in the design spec.
- Create indexes for `created_at`, `session_key`, `request_id`, `approval_request_id`, `tool_name`, and `event_type`.
- Use `uuid.uuid4().hex` when `event_id` is empty.
- Normalize timestamps to UTC ISO strings with timezone.
- Clamp query limits to `1..200`.
- Sort query results by `created_at DESC, event_id DESC`.
- `sanitize_tool_audit_metadata(...)` keeps only scalar values for this allowlist:

```python
{
    "resource_type", "resource_decision", "sandbox_backend", "sandbox_image",
    "network_mode", "workspace_mount_mode", "timeout_seconds", "exit_code",
    "stdout_ref", "stderr_ref", "stdout_hash", "stderr_hash", "stdout_bytes",
    "stderr_bytes", "stdout_truncated", "stderr_truncated", "duration_ms",
    "target_path_hash", "before_hash", "after_hash", "diff_truncated",
    "rollback_id", "error_code", "command_hash", "preview_id",
    "background_requested", "background_allowed",
}
```

- `record_tool_audit_event_fail_open(store, event, logger)` catches exceptions and logs with `logger.warning(..., exc_info=True)`.

- [ ] **Step 4: Run focused tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_tool_audit_ledger.py -q -p no:cacheprovider
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add agent/policies/tool_audit_ledger.py tests/test_tool_audit_ledger.py
git commit -m "feat: add tool audit ledger store"
```

---

### Task 2: ToolExecutor Policy Decision Ledger Writes

**Files:**
- Modify: `agent/tool_hooks/executor.py`
- Modify: `agent/core/passive_turn.py`
- Modify: `tests/test_tool_executor.py`

**Interfaces:**
- Consumes: `ToolAuditLedgerStore`, `ToolAuditLedgerEvent`, `record_tool_audit_event_fail_open(...)`.
- Produces: optional `ToolExecutor.set_audit_ledger_store(...)` and constructor parameter `audit_ledger_store`.

- [ ] **Step 1: Write failing tests**

Add tests to `tests/test_tool_executor.py`:

```python
class _RecordingLedger:
    def __init__(self) -> None:
        self.events = []
        self.raise_on_record = False

    def record_event(self, event):
        if self.raise_on_record:
            raise RuntimeError("ledger down")
        self.events.append(event)
        return event


def test_tool_executor_records_allow_policy_decision_to_ledger() -> None:
    ledger = _RecordingLedger()
    executor = ToolExecutor(audit_ledger_store=ledger)
    result = asyncio.run(
        executor.execute(
            ToolExecutionRequest(
                call_id="call-allow",
                tool_name="dummy",
                arguments={"x": 1},
                source="passive",
                registry_risk="read-only",
                session_key="cli:s",
                channel="cli",
            ),
            _invoke,
        )
    )
    assert result.status == "success"
    assert len(ledger.events) == 1
    event = ledger.events[0]
    assert event.event_type == "tool_invocation_policy_decision"
    assert event.request_id == "call-allow"
    assert event.policy_action == "allow"
    assert event.invoker_reached is True
    assert event.invoker_succeeded is True


def test_tool_executor_ledger_failure_does_not_change_result() -> None:
    ledger = _RecordingLedger()
    ledger.raise_on_record = True
    result = asyncio.run(
        ToolExecutor(audit_ledger_store=ledger).execute(
            ToolExecutionRequest(
                call_id="call-allow",
                tool_name="dummy",
                arguments={"x": 1},
                source="passive",
                registry_risk="read-only",
            ),
            _invoke,
        )
    )
    assert result.status == "success"
    assert result.invoker_reached is True
    assert result.invoker_succeeded is True
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_tool_executor.py::test_tool_executor_records_allow_policy_decision_to_ledger tests/test_tool_executor.py::test_tool_executor_ledger_failure_does_not_change_result -q -p no:cacheprovider
```

Expected: fail because `ToolExecutor.__init__()` does not accept `audit_ledger_store`.

- [ ] **Step 3: Implement executor wiring**

Implementation requirements:

- Add `audit_ledger_store: object | None = None` to `ToolExecutor.__init__`.
- Add `set_audit_ledger_store(self, audit_ledger_store: object | None) -> None`.
- Add private `_record_policy_decision_to_ledger(...)`.
- Call it for every result that already gets `_audit_trace(...)`: deny, defer, managed-side-effect defer, invoker success, invoker error, post-hook error after invoker.
- Keep pre-hook denies unchanged unless a policy decision exists; P4c records core invocation policy decisions, not pre-hook-only denials.
- In `agent/core/passive_turn.py`, add `_tool_audit_ledger_from_context(context)` and call `self._tool_executor.set_audit_ledger_store(...)` beside `set_approval_runtime(...)`.

The recorder builds `ToolAuditLedgerEvent` with:

```python
ToolAuditLedgerEvent(
    event_type="tool_invocation_policy_decision",
    session_key=request.session_key,
    channel=request.channel,
    chat_id=request.chat_id,
    request_id=request.call_id,
    tool_name=request.tool_name,
    source=_policy_source(request),
    risk=policy_decision.risk,
    policy_action=policy_decision.action,
    policy_reason=policy_decision.reason,
    args_hash=canonical_args_hash(final_arguments),
    invoker_reached=invoker_reached,
    invoker_succeeded=invoker_succeeded,
    metadata={
        "resource_type": str(policy_decision.metadata.get("resource_type") or ""),
        "resource_decision": str(policy_decision.metadata.get("resource_decision") or ""),
    },
)
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_tool_executor.py tests/test_tool_invocation_policy_gate.py -q -p no:cacheprovider
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add agent/tool_hooks/executor.py agent/core/passive_turn.py tests/test_tool_executor.py
git commit -m "feat: record tool policy decisions in audit ledger"
```

---

### Task 3: Approval Lifecycle Ledger Writes

**Files:**
- Modify: `agent/policies/tool_approval_runtime.py`
- Modify: `plugins/status_commands/plugin.py`
- Modify: `tests/test_tool_approval_runtime.py`

**Interfaces:**
- Consumes: `ToolAuditLedgerStore`.
- Produces: ledger-aware `ToolApprovalRuntime` methods for requested/approved/denied/expired/consumed/executed/execution_failed.

- [ ] **Step 1: Write failing tests**

Add tests to `tests/test_tool_approval_runtime.py`:

```python
def test_approval_runtime_records_requested_consumed_and_executed_to_ledger(tmp_path) -> None:
    ledger = ToolAuditLedgerStore(tmp_path / "audit.db")
    runtime = ToolApprovalRuntime(
        ToolApprovalStore(tmp_path / "approvals.db"),
        audit_ledger_store=ledger,
        now_factory=lambda: datetime(2026, 7, 28, 1, 0, tzinfo=UTC),
    )
    record = runtime.record_defer_request(
        request_id="call-1",
        session_key="cli:s",
        channel="cli",
        chat_id="chat",
        source="passive",
        tool_name="write_file",
        risk="write",
        approval_scope="tool_call",
        policy_reason="risk_strategy_write_requires_approval",
        arguments={"path": "notes.md", "content": "secret"},
    )
    runtime.approve_request(
        approval_request_id=record.approval_request_id,
        session_key="cli:s",
        actor="status_command",
    )
    consume = runtime.consume_for_execution(
        trusted_context=trusted_approval_from_runtime(record.approval_request_id, actor="status_command"),
        request_id="call-1",
        session_key="cli:s",
        tool_name="write_file",
        approval_scope="tool_call",
        arguments={"path": "notes.md", "content": "secret"},
    )
    assert consume.allows_invoker
    runtime.finalize_execution(
        approval_request_id=record.approval_request_id,
        request_id="call-1",
        session_key="cli:s",
        tool_name="write_file",
        approval_scope="tool_call",
        arguments={"path": "notes.md", "content": "secret"},
        execution_status="executed",
    )

    events = ledger.query_events(ToolAuditLedgerQuery(approval_request_id=record.approval_request_id, limit=10))
    assert [event.event_type for event in reversed(events)] == [
        "tool_approval_requested",
        "tool_approval_approved",
        "tool_approval_consumed",
        "tool_approval_executed",
    ]
    assert all("secret" not in str(event.metadata) for event in events)
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_tool_approval_runtime.py::test_approval_runtime_records_requested_consumed_and_executed_to_ledger -q -p no:cacheprovider
```

Expected: fail because `ToolApprovalRuntime.__init__()` does not accept `audit_ledger_store`.

- [ ] **Step 3: Implement approval lifecycle recording**

Implementation requirements:

- Add optional `audit_ledger_store` constructor argument.
- Add runtime wrappers:
  - `expire_pending_requests(self) -> list[ToolApprovalDecision]`
  - `approve_request(self, *, approval_request_id: str, session_key: str, actor: str) -> ToolApprovalDecision`
  - `deny_request(self, *, approval_request_id: str, session_key: str, actor: str, reason: str) -> ToolApprovalDecision`
- Existing methods `record_defer_request`, `consume_for_execution`, and `finalize_execution` must record ledger events after store mutation returns.
- Status commands should use the runtime wrappers instead of calling `ToolApprovalStore.approve_request(...)`, `deny_request(...)`, and `expire_pending_requests(...)` directly.
- Event type mapping:
  - `requested` -> `tool_approval_requested`
  - `approved` -> `tool_approval_approved`
  - `denied` -> `tool_approval_denied`
  - `expired` -> `tool_approval_expired`
  - `consumed` -> `tool_approval_consumed`
  - `executed` -> `tool_approval_executed`
  - `execution_failed` -> `tool_approval_execution_failed`

- [ ] **Step 4: Run focused tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_tool_approval_runtime.py tests/test_status_commands_approved_side_effects.py -q -p no:cacheprovider
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add agent/policies/tool_approval_runtime.py plugins/status_commands/plugin.py tests/test_tool_approval_runtime.py tests/test_status_commands_approved_side_effects.py
git commit -m "feat: record approval lifecycle in audit ledger"
```

---

### Task 4: Approved File And Shell Side-Effect Ledger Writes

**Files:**
- Modify: `agent/policies/approved_side_effect_runtime.py`
- Modify: `agent/policies/approved_shell_side_effect_runtime.py`
- Modify: `plugins/status_commands/plugin.py`
- Modify: `tests/test_approved_side_effect_runtime.py`
- Modify: `tests/test_approved_shell_side_effect_runtime.py`
- Modify: `tests/test_tool_governance_p4b_contract.py`

**Interfaces:**
- Consumes: `ToolAuditLedgerStore`.
- Produces: lifecycle ledger events for managed file and shell side-effect runtimes.

- [ ] **Step 1: Write failing tests**

Add one file-runtime test and one shell-runtime test:

```python
def test_file_side_effect_runtime_records_preview_execute_and_rollback(tmp_path) -> None:
    ledger = ToolAuditLedgerStore(tmp_path / "audit.db")
    runtime = _runtime(tmp_path, audit_ledger_store=ledger)
    approval_id = _approved_write_file_request(tmp_path, runtime.approval_runtime)

    prepared = runtime.prepare(approval_id, "cli:s", "status_command", tmp_path, (str(tmp_path),))
    applied = runtime.apply(approval_id, "cli:s", "status_command", tmp_path, (str(tmp_path),))
    rolled_back = runtime.rollback(approval_id, "cli:s", "status_command", tmp_path, (str(tmp_path),))

    assert prepared.ok
    assert applied.ok
    assert rolled_back.ok
    events = ledger.query_events(ToolAuditLedgerQuery(approval_request_id=approval_id, limit=20))
    event_types = {event.event_type for event in events}
    assert "approved_side_effect_payload_recorded" in event_types
    assert "approved_side_effect_preview_ready" in event_types
    assert "approved_side_effect_executed" in event_types
    assert "approved_side_effect_rolled_back" in event_types
    assert all("payload_ref" not in event.metadata for event in events)
```

```python
def test_shell_side_effect_runtime_records_bounded_sandbox_metadata(tmp_path) -> None:
    ledger = ToolAuditLedgerStore(tmp_path / "audit.db")
    runtime = _runtime(tmp_path, audit_ledger_store=ledger, sandbox_runner=_FakeSandboxRunner())
    approval_id = _approved_shell_request(tmp_path, runtime.approval_runtime, command="echo raw-secret")

    prepared = runtime.prepare(approval_id, "cli:s", "status_command", tmp_path, (str(tmp_path),))
    applied = runtime.apply(approval_id, "cli:s", "status_command", tmp_path, (str(tmp_path),))

    assert prepared.ok
    assert applied.ok
    events = ledger.query_events(ToolAuditLedgerQuery(approval_request_id=approval_id, limit=20))
    serialized = "\n".join(str(event.metadata) for event in events)
    assert "command_hash" in serialized
    assert "stdout_hash" in serialized
    assert "echo raw-secret" not in serialized
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_approved_side_effect_runtime.py tests/test_approved_shell_side_effect_runtime.py -q -p no:cacheprovider
```

Expected: fail on missing `audit_ledger_store` helper wiring or missing lifecycle ledger events.

- [ ] **Step 3: Implement runtime ledger recording**

Implementation requirements:

- Add optional `audit_ledger_store` constructor argument to both runtimes.
- Record file events:
  - `approved_side_effect_payload_recorded`
  - `approved_side_effect_preview_ready`
  - `approved_side_effect_executed`
  - `approved_side_effect_execution_failed`
  - `approved_side_effect_rolled_back`
  - `approved_side_effect_rollback_failed`
- Record shell events:
  - `approved_shell_payload_recorded`
  - `approved_shell_sandbox_preview_ready`
  - `approved_shell_sandbox_executed`
  - `approved_shell_sandbox_execution_failed`
  - `approved_shell_sandbox_unavailable`
  - `approved_shell_sandbox_timeout`
- Metadata must use existing hashes and artifact refs only: `target_path_hash`, `before_hash`, `after_hash`, `diff_truncated`, `rollback_id`, `command_hash`, `sandbox_backend`, `sandbox_image`, `network_mode`, `workspace_mount_mode`, `timeout_seconds`, `exit_code`, `stdout_ref`, `stderr_ref`, `stdout_hash`, `stderr_hash`, `stdout_bytes`, `stderr_bytes`, `stdout_truncated`, `stderr_truncated`, `duration_ms`.
- Do not pass `payload_ref`, `diff_ref`, raw command, raw path, raw diff, stdout text, or stderr text to the ledger.
- `plugins/status_commands/plugin.py` must pass the ledger store into both runtime constructors.

- [ ] **Step 4: Run focused tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_approved_side_effect_runtime.py tests/test_approved_shell_side_effect_runtime.py tests/test_tool_governance_p4b_contract.py -q -p no:cacheprovider
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add agent/policies/approved_side_effect_runtime.py agent/policies/approved_shell_side_effect_runtime.py plugins/status_commands/plugin.py tests/test_approved_side_effect_runtime.py tests/test_approved_shell_side_effect_runtime.py tests/test_tool_governance_p4b_contract.py
git commit -m "feat: record managed side effects in audit ledger"
```

---

### Task 5: Tool Audit Status Command

**Files:**
- Modify: `plugins/status_commands/plugin.py`
- Modify: `plugins/status_commands/README.md`
- Modify: `tests/test_status_commands_approved_side_effects.py`

**Interfaces:**
- Consumes: `ToolAuditLedgerStore.query_events(...)`.
- Produces: `/tool_audit` trusted read-only command.

- [ ] **Step 1: Write failing tests**

Add tests:

```python
def test_tool_audit_command_lists_current_session_events(tmp_path) -> None:
    ledger = ToolAuditLedgerStore(tmp_path / "audit.db")
    ledger.record_event(ToolAuditLedgerEvent(event_type="tool_invocation_policy_decision", session_key="cli:s", request_id="call-1", tool_name="write_file", policy_action="defer", policy_reason="risk_strategy_write_requires_approval"))
    ledger.record_event(ToolAuditLedgerEvent(event_type="tool_invocation_policy_decision", session_key="cli:other", request_id="call-2", tool_name="shell", policy_action="defer", policy_reason="risk_strategy_shell_requires_approval"))
    module = ToolApprovalCommandModule("status_commands", ToolApprovalStore(tmp_path / "approvals.db"), audit_ledger_store=ledger)

    reply = _run_status_command(module, "/tool_audit 10", session_key="cli:s")

    assert "tool_invocation_policy_decision" in reply
    assert "write_file" in reply
    assert "call-1" in reply
    assert "call-2" not in reply


def test_tool_audit_command_never_prints_raw_metadata(tmp_path) -> None:
    ledger = ToolAuditLedgerStore(tmp_path / "audit.db")
    ledger.record_event(ToolAuditLedgerEvent(event_type="approved_shell_sandbox_executed", session_key="cli:s", tool_name="shell", metadata={"command": "echo secret", "command_hash": "abc"}))
    module = ToolApprovalCommandModule("status_commands", ToolApprovalStore(tmp_path / "approvals.db"), audit_ledger_store=ledger)

    reply = _run_status_command(module, "/tool_audit tool shell 5", session_key="cli:s")

    assert "command_hash" in reply
    assert "abc" in reply
    assert "echo secret" not in reply
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_status_commands_approved_side_effects.py -q -p no:cacheprovider
```

Expected: fail because `/tool_audit` is not handled.

- [ ] **Step 3: Implement command**

Implementation requirements:

- Add `audit_ledger_store: ToolAuditLedgerStore | None = None` to `ToolApprovalCommandModule.__init__`.
- Handle:
  - `/tool_audit [limit]`
  - `/tool_audit request <request_id>`
  - `/tool_audit approval <approval_request_id>`
  - `/tool_audit tool <tool_name> [limit]`
  - `/tool_audit event <event_type> [limit]`
- Default query scope is `session_key=state.session_key`.
- Clamp limit through `ToolAuditLedgerQuery`.
- If store is missing, return `Tool audit ledger unavailable.`
- Format each event with timestamp, event type, tool, policy action/reason, lifecycle status fields, short request id, short approval id, invoker reached/succeeded, and sanitized metadata keys.
- Add `("tool_audit", "查看工具治理审计记录")` to `telegram_bot_commands`.
- Update README with examples and redaction boundary.

- [ ] **Step 4: Run focused tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_status_commands_approved_side_effects.py -q -p no:cacheprovider
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add plugins/status_commands/plugin.py plugins/status_commands/README.md tests/test_status_commands_approved_side_effects.py
git commit -m "feat: add tool audit status command"
```

---

### Task 6: Governance Docs And Final Verification

**Files:**
- Modify: `my_md/governance/04-fix-roadmap.md`
- Modify: `my_md/governance/08-tool-invocation-policy-p1-status.md`
- Modify: `task_plan.md`
- Modify: `progress.md`
- Modify: `findings.md`

**Interfaces:**
- Consumes: all previous tasks.
- Produces: measured verification record and updated follow-up boundary.

- [ ] **Step 1: Update governance docs**

Record:

- P4c/P5a implements queryable persistent redacted `ToolAuditLedger`.
- Approval and side-effect stores remain source-of-truth.
- Ledger is fail-open audit projection.
- External API side-effect replay remains the next closed follow-up.
- Destructive execution, TaskExecution shell resume, shell rollback, and network-enabled shell sandbox remain unavailable.

- [ ] **Step 2: Run focused governance suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_tool_audit.py tests/test_tool_audit_ledger.py tests/test_tool_executor.py tests/test_tool_approval_runtime.py tests/test_approved_side_effect_runtime.py tests/test_approved_shell_side_effect_runtime.py tests/test_status_commands_approved_side_effects.py tests/test_tool_governance_p4b_contract.py -q -p no:cacheprovider
```

Expected: pass.

- [ ] **Step 3: Run P1-P4c baseline**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_resource_policy.py tests/test_tool_invocation_resource_policy.py tests/test_tool_invocation_policy.py tests/test_tool_approval.py tests/test_tool_executor_approval_workflow.py tests/test_tool_governance_p3_contract.py tests/test_tool_governance_p4_contract.py tests/test_tool_governance_p4b_contract.py tests/test_tool_audit_ledger.py -q -p no:cacheprovider
```

Expected: pass.

- [ ] **Step 4: Run compatibility and syntax checks**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python -m compileall agent/policies agent/tool_hooks agent/core/passive_turn.py plugins/status_commands tests/test_tool_audit_ledger.py
git diff --check
```

Expected: compileall exits `0`; `git diff --check` emits no output.

- [ ] **Step 5: Update persistent plan records**

Update root `task_plan.md`, `progress.md`, and `findings.md` with exact test counts and final boundaries.

- [ ] **Step 6: Commit**

```bash
git add agent/policies/tool_audit_ledger.py agent/tool_hooks/executor.py agent/core/passive_turn.py agent/policies/tool_approval_runtime.py agent/policies/approved_side_effect_runtime.py agent/policies/approved_shell_side_effect_runtime.py plugins/status_commands/plugin.py plugins/status_commands/README.md tests/test_tool_audit_ledger.py tests/test_tool_executor.py tests/test_tool_approval_runtime.py tests/test_approved_side_effect_runtime.py tests/test_approved_shell_side_effect_runtime.py tests/test_status_commands_approved_side_effects.py tests/test_tool_governance_p4b_contract.py my_md/governance/04-fix-roadmap.md my_md/governance/08-tool-invocation-policy-p1-status.md task_plan.md progress.md findings.md
git commit -m "docs: record p4c audit ledger verification"
```

---

## Self-Review Notes

- Spec coverage: Tasks 1-6 cover ledger store/query/prune, metadata redaction, executor policy decisions, approval lifecycle, file and shell side-effect lifecycle, status command query, docs, and final verification.
- Scope check: No task opens external API replay, destructive execution, shell rollback, TaskExecution shell resume, or network-enabled shell sandbox.
- Type consistency: All tasks use `ToolAuditLedgerEvent`, `ToolAuditLedgerQuery`, `ToolAuditLedgerStore`, and optional `audit_ledger_store` constructor arguments.
- Security check: The only metadata passed to the ledger is allowlisted; command/path/content/payload/output text fields are excluded.
