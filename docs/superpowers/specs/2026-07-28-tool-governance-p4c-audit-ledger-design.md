# Tool Governance P4c Queryable Tool Audit Ledger Design

日期：2026-07-28

## Goal

P4c/P5a 建立第一版可查询、持久、脱敏的 `ToolAuditLedger`，把 P1-P4b 已经存在于 turn trace / observe slim trace / approval store / side-effect store 中的工具治理事实汇聚成 workspace-scoped audit ledger。

本阶段不扩展工具执行能力，不开放 external API side-effect replay，不开放 destructive execution，不开放 TaskExecution shell resume，不开放 shell rollback，也不开放 network-enabled shell sandbox。

## Context

P1-P4b 已经完成：

- P1/P2：工具调用前置裁决、resource policy、默认 defer/deny、minimal audit trace。
- P3：durable trusted approval workflow 和 bounded approval lifecycle trace。
- P4a：approved file side-effect runtime、snapshot/diff/apply/rollback、bounded side-effect lifecycle trace。
- P4b：approved shell runtime 和 Docker/Podman sandbox，raw shell arguments 仅保存在 private payload vault。

当前缺口是：这些审计事实分散在多个 runtime trace 和 store 中，不能用统一 query API 追问“某个 session / request / approval / tool 在什么时候为什么被允许、拒绝、延迟、批准、消费、执行或回滚”。

## Design Alternatives

### Option A: Query Observe Only

只从 `observe.turns.tool_chain_json` / `tool_calls` 回源。

优点：不新增数据库。  
缺点：observe 是 turn trace，不是治理账本；status command、approval runtime、side-effect runtime 的生命周期事实并不总是以适合审计查询的粒度出现；retention 和索引也不适合直接叠加。

### Option B: Add Ledger As Sidecar Store

新增 workspace-scoped `tool_audit/tool_audit.db`，由 executor、approval runtime、side-effect runtime 写入 bounded event。

优点：查询模型清晰，不改现有 approval / side-effect source-of-truth；可以独立做 retention、索引和 status/admin 查询；更适合作为 external API replay 前置安全基础。  
缺点：需要在多个 runtime surface 接入写入点，并处理 ledger 写入失败。

### Option C: Merge Ledger Into Approval / Side-Effect Stores

扩展 `tool_approval_requests` 和 `approved_side_effects`，把所有事件都塞进现有 SQLite。

优点：少一个数据库文件。  
缺点：普通 read-only deny/allow 没有 approval id；approval store 和 side-effect store 的 ownership 会被混合；外部 API replay 后还会继续膨胀。

## Selected Approach

选择 Option B：新增 sidecar `ToolAuditLedgerStore`。

理由：P4c 的核心目标是“统一查询与留存”，不是改变 approval store 或 side-effect store 的事务语义。Ledger 是审计投影，不是执行 source-of-truth；approval 和 side-effect runtime 仍以自己的 store 决定状态，ledger 只记录 bounded fact。

## Scope

P4c/P5a 包含：

- 新增 `ToolAuditLedgerStore` 和 `ToolAuditLedgerEvent`。
- 新增 query service，支持按 session、request、approval、tool、event type、时间范围、limit 查询。
- 接入普通工具 invocation policy decision：allow / deny / defer。
- 接入 approval lifecycle：requested / approved / denied / expired / consumed / executed / execution_failed。
- 接入 approved side-effect lifecycle：payload_recorded / preview_ready / executed / execution_failed / rolled_back / rollback_failed。
- 接入 shell sandbox execution metadata：backend basename、image、network mode、mount mode、timeout、exit code、stdout/stderr refs and hashes。
- 新增 status/admin command 查询最近 audit events。
- 新增 retention pruning API，第一版只按 age 和 max rows 裁剪。
- 更新 governance docs 和 tests。

不包含：

- external API side-effect replay。
- destructive operation execution。
- shell rollback。
- TaskExecution shell/external side-effect resume。
- network-enabled shell sandbox。
- dashboard UI。
- 将 ledger failure 作为工具执行成功/失败的判定来源。

## Data Model

新增文件建议：

- `agent/policies/tool_audit_ledger.py`
- `tests/test_tool_audit_ledger.py`

SQLite path:

```text
<workspace>/tool_audit/tool_audit.db
```

Table: `tool_audit_events`

Core columns:

- `event_id TEXT PRIMARY KEY`
- `created_at TEXT NOT NULL`
- `event_type TEXT NOT NULL`
- `session_key TEXT NOT NULL DEFAULT ''`
- `channel TEXT NOT NULL DEFAULT ''`
- `chat_id TEXT NOT NULL DEFAULT ''`
- `request_id TEXT NOT NULL DEFAULT ''`
- `turn_id TEXT NOT NULL DEFAULT ''`
- `tool_name TEXT NOT NULL DEFAULT ''`
- `source TEXT NOT NULL DEFAULT ''`
- `risk TEXT NOT NULL DEFAULT ''`
- `policy_action TEXT NOT NULL DEFAULT ''`
- `policy_reason TEXT NOT NULL DEFAULT ''`
- `approval_request_id TEXT NOT NULL DEFAULT ''`
- `approval_scope TEXT NOT NULL DEFAULT ''`
- `approval_status TEXT NOT NULL DEFAULT ''`
- `side_effect_status TEXT NOT NULL DEFAULT ''`
- `execution_status TEXT NOT NULL DEFAULT ''`
- `rollback_status TEXT NOT NULL DEFAULT ''`
- `actor TEXT NOT NULL DEFAULT ''`
- `args_hash TEXT NOT NULL DEFAULT ''`
- `invoker_reached INTEGER NOT NULL DEFAULT 0`
- `invoker_succeeded INTEGER NOT NULL DEFAULT 0`
- `metadata_json TEXT NOT NULL DEFAULT '{}'`

Indexes:

- `(created_at, event_id)`
- `(session_key, created_at)`
- `(request_id, created_at)`
- `(approval_request_id, created_at)`
- `(tool_name, created_at)`
- `(event_type, created_at)`

## Metadata Rules

`metadata_json` is allowlisted, not raw-dump based.

Allowed examples:

- `resource_type`
- `resource_decision`
- `sandbox_backend`
- `sandbox_image`
- `network_mode`
- `workspace_mount_mode`
- `timeout_seconds`
- `exit_code`
- `stdout_ref`
- `stderr_ref`
- `stdout_hash`
- `stderr_hash`
- `stdout_bytes`
- `stderr_bytes`
- `stdout_truncated`
- `stderr_truncated`
- `duration_ms`
- `target_path_hash`
- `before_hash`
- `after_hash`
- `diff_truncated`
- `rollback_id`
- `error_code`

Forbidden in ledger:

- raw tool arguments
- raw shell command
- raw file path
- raw file content
- raw diff text
- payload path
- secret / token / cookie / authorization / api key values
- stdout / stderr text
- HTTP body
- URL query strings that may contain credentials

If a field is not explicitly allowlisted, it is dropped.

## Runtime Integration

### ToolExecutor

After `_audit_trace(...)` is built, `ToolExecutor` records one `tool_invocation_policy_decision` event.

Rules:

- `invoker_reached=false` for deny/defer.
- `invoker_reached=true` only when real invoker was called.
- `invoker_succeeded` mirrors existing executor result, not ledger write status.
- Ledger write failure is logged and attached to local debug trace if possible, but it must not relabel the tool execution result.

### ToolApprovalRuntime

Approval lifecycle methods record bounded lifecycle events:

- pending request creation: `tool_approval_requested`
- approve / deny / expire
- consume
- finalize executed / execution_failed

The existing approval store remains source-of-truth. Ledger events are an audit projection.

### ApprovedSideEffectRuntime

File side-effect runtime records:

- payload recorded
- preview ready
- executed / execution_failed
- rolled_back / rollback_failed

Ledger metadata stores only hashes, ids, statuses and truncated flags. It must not store raw target paths, diff text, or payload refs.

### ApprovedShellSideEffectRuntime

Shell runtime records:

- payload recorded
- sandbox preview ready
- sandbox executed / execution_failed
- sandbox unavailable / image unavailable / timeout / launch failure

Ledger metadata stores command hash and sandbox/output metadata, but never raw command or raw shell arguments.

### Status Commands

Add a trusted read-only status/admin query surface, for example:

```text
/tool_audit [limit]
/tool_audit request <request_id>
/tool_audit approval <approval_request_id>
/tool_audit tool <tool_name> [limit]
```

First version returns concise text:

- timestamp
- event type
- tool
- policy action/reason or lifecycle status
- request id / approval id short form
- invoker reached/succeeded

It must not print raw command, raw args, raw paths, raw content, raw output, or diff text.

## Query API

Suggested interface:

```python
@dataclass(frozen=True)
class ToolAuditLedgerQuery:
    session_key: str = ""
    request_id: str = ""
    approval_request_id: str = ""
    tool_name: str = ""
    event_type: str = ""
    since: str = ""
    until: str = ""
    limit: int = 50

class ToolAuditLedgerStore:
    @staticmethod
    def db_path_from_workspace(workspace: str | Path) -> Path: ...
    def record_event(self, event: ToolAuditLedgerEvent) -> ToolAuditLedgerEvent: ...
    def query_events(self, query: ToolAuditLedgerQuery) -> list[ToolAuditLedgerEvent]: ...
    def prune(self, *, before: datetime | None, max_rows: int | None) -> int: ...
```

Query limits:

- default `limit=50`
- max `limit=200`
- sort newest first for status command output
- stable tie-breaker by `event_id`

## Retention

First version retention:

- No automatic background deletion.
- Expose explicit `prune(...)`.
- Status/admin command may expose a narrow pruning command later; the first implementation plan should decide whether to include it after tests prove query safety.
- Recommended defaults for config design: retain 30 days and cap at 100000 rows, but do not enforce config until implementation has a concrete config surface.

## Error Handling

Ledger is audit projection, not execution source-of-truth.

- Ledger write failure must not turn a successful tool execution into `execution_failed`.
- Ledger write failure must not consume or un-consume approvals.
- Ledger write failure must be visible in ordinary logs.
- Tests must cover that persistence failure does not relabel execution outcome.

## Security Invariants

- Raw shell command never enters ledger.
- Raw file content never enters ledger.
- Raw target path never enters ledger; use hash.
- Payload vault paths never enter ledger.
- Output artifacts are referenced by bounded refs and hashes only.
- Ledger query commands are read-only.
- Ledger query is session-safe by default: status commands should default to current session unless a trusted admin path explicitly asks broader scope.
- Ledger query must not unlock tools or write `ToolDiscoveryState` / LRU.

## Testing Strategy

Focused tests:

- `tests/test_tool_audit_ledger.py`
  - schema creation and indexes
  - record/query by session, request, approval, tool, event type
  - max limit enforcement
  - metadata allowlist drops raw args, command, content, path, token, cookie
  - retention prune by time and max rows

Integration tests:

- `tests/test_tool_executor_approval_workflow.py`
  - deny/defer/allow writes ledger event without raw args
- `tests/test_status_commands_approved_side_effects.py`
  - `/tool_audit` lists bounded events
- `tests/test_tool_governance_p4b_contract.py`
  - approved shell sandbox ledger event contains command hash and artifact metadata only
- `tests/test_observe_writer.py`
  - observe slim trace remains bounded and independent from ledger

Regression tests:

- Shell raw command appears in payload vault only, not ledger.
- File content appears in payload vault/file artifacts only, not ledger.
- Ledger write failure does not alter approval finalization or side-effect execution result.

## Implementation Plan Shape

Expected task sequence:

1. Ledger store and bounded event model.
2. ToolExecutor policy decision ledger writes.
3. Approval lifecycle ledger writes.
4. Approved file/shell side-effect lifecycle ledger writes.
5. Query service and status command.
6. Retention, docs, final verification.

Each task should be TDD-first and reviewed before the next task.

## Acceptance Criteria

- A user/admin can query recent tool governance events by session/request/approval/tool.
- P1/P2/P3/P4a/P4b lifecycle events appear in a single ledger.
- No raw args, raw command, raw file content, raw target path, raw output text, payload path, token, cookie or secret appears in ledger rows.
- Existing approval and side-effect stores remain source-of-truth.
- Existing observe behavior remains compatible.
- External API replay remains unavailable after P4c/P5a.
