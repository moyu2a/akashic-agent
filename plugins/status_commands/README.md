# status_commands 插件

内置诊断命令拦截器。在 BeforeTurn 管道的早期阶段识别 `/memory_status` 和 `/kvcache` 命令，直接返回诊断报告，绕过后续的记忆检索和 LLM 推理。

---

## 接入点

| 接入方式 | 阶段 |
|---|---|
| `before_turn_modules()` | `before_turn.acquire_session` 之后——命令识别与 abort |

---

## 运作逻辑

两个命令各对应一个 PhaseModule，均插入在记忆检索（`_PrepareContextModule`）之前。任意一个命中时，向 `session:ctx` slot 写入一个 `abort=True` 的 `BeforeTurnCtx`，后续管道模块及 LLM 推理全部跳过，直接返回该 slot 的内容作为本轮回复。

### MemoryStatusCommandModule（`/memory_status` / `/compact_status`）

读取当前 session 的 `messages` 列表和 `last_consolidated` 指针，统计：

- 已整理到的用户消息数量（`last_consolidated` 之前）。
- 尚未整理的用户消息数量。
- 最后一条已整理用户消息的预览。
- 当前会话总消息数。

格式化为可读文本后作为 abort_reply 返回。只统计"真实用户消息"（role=user 且非 context frame 占位符）。

### KVCacheCommandModule（`/kvcache` / `/cache_status`）

查询 observe 数据库（`observe/observe.db`），从 `turns` 表取最近 N 轮（默认 5，可追加参数覆盖，最大 30）的 KVCache 统计字段：

- `react_cache_prompt_tokens`：本轮送入的 prompt tokens 总量。
- `react_cache_hit_tokens`：命中缓存的 tokens 数量。

计算每轮命中率和总体命中率，格式化为表格后返回。若 observe 数据库不存在则返回提示信息。

### ToolApprovalCommandModule

- `/approvals`: 查看当前 session 待审批工具调用。
- `/approve_tool <approval_id>`: 批准一个待审批工具调用；该命令只记录决策，不执行 side effect。
- `/deny_tool <approval_id>`: 拒绝一个待审批工具调用。
- `/prepare_tool <approval_id>`: generate a bounded diff preview for an approved file side effect, or prepare an approved shell sandbox preview.
- `/run_approved_tool <approval_id>`: apply a prepared approved file side effect through the managed P4 runtime, or execute an approved shell command in its sandbox.
- `/rollback_tool <approval_id>`: restore the snapshot for an executed P4 file side effect. Shell rollback is not supported.
- `/tool_audit [limit]`: show recent redacted tool governance audit events for the current session.
- `/tool_audit request <request_id>`: show current-session audit events for one tool request.
- `/tool_audit approval <approval_id>`: show current-session audit events for one approval request.
- `/tool_audit tool <tool_name> [limit]`: show current-session audit events for one tool.
- `/tool_audit event <event_type> [limit]`: show current-session audit events of one event type.

Approved shell execution requires Docker or Podman. Shell command text is held in the private payload vault and is not printed or stored in observe metadata; status replies expose only safe lifecycle and sandbox result metadata.

`/tool_audit` reads the workspace `tool_audit/tool_audit.db` sidecar ledger only. It does not mutate approval state, side-effect state, `ToolDiscoveryState`, or LRU preload state. The V1 command intentionally does not expose `since` / `until`; time-range filtering remains an internal ledger API.

Audit output includes event type, tool name, policy decision, lifecycle statuses, short request/approval ids, invoker result flags, and sanitized metadata key/value pairs. Raw tool arguments, shell commands, file paths, file content, diffs, payload paths, stdout/stderr text, tokens, cookies, authorization headers, secrets, and API keys must not appear in ledger rows or command output.
