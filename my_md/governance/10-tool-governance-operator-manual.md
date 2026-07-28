# Tool Governance Operator Manual

日期：2026-07-28

本文是当前工具治理的使用手册。它记录哪些工具调用会直接执行、哪些需要审批、哪些会被拒绝、哪些支持 rollback，以及 shell sandbox 和 audit 的实际边界。

## 总览

当前工具调用不是模型生成后直接执行，而是经过：

```text
LLM tool_call
  -> ToolAccessGateway / visibility boundary
  -> ToolExecutor
  -> pre-hook
  -> ToolInvocationPolicy
  -> ResourcePolicy
  -> RiskStrategy / approval request
  -> Managed Runtime
  -> real invoker / sandbox
  -> post observation
  -> audit / observe
```

核心原则：

- 模型输出只是请求，不是可信执行事实。
- `deny` / `defer` 不触达真实 invoker。
- 用户 approval 不是裸执行授权；approved side effect 仍要进入受管控 runtime。
- 审计记录保持脱敏，不保存 raw command、raw path/content/diff、payload path、stdout/stderr 或凭证。

## 操作含义速查

| 结论 | 操作含义 |
|---|---|
| `shell_restore` 已关闭 | 不再把 `rm` 静默改写为 `mv`；hook 不负责改变副作用语义。 |
| destructive shell hard deny | `rm`、`rmdir`、`unlink`、`shred`、`dd`、`mkfs`、`truncate` 等直接拒绝，不进入 approval 或 sandbox。 |
| approval 不是裸执行授权 | 用户批准后只是进入 managed runtime；runtime 仍会校验 approval、session、tool、scope、args hash 和 policy。 |
| 文件副作用有 rollback | 仅 approved `write_file` / `edit_file` 支持 preview、apply 和 rollback。 |
| shell 有 sandbox | approved `shell` 进入 sandbox，保持 network off、workspace read-only、fail closed。 |
| shell 没有 rollback | shell 执行后不承诺可撤销；destructive shell 仍直接拒绝。 |
| external API 没有 replay / rollback | 外部 API 副作用不支持批准后自动重放，也不支持回滚。 |
| 高风险能力保持关闭 | 不开放 destructive execution、shell rollback、network-enabled shell sandbox、TaskExecution shell resume、external API replay。 |

## 调用结果

| 结果 | 含义 | 是否触达 invoker |
|---|---|---|
| `allow` | 当前调用可直接执行。通常只适用于已注册、范围内的 `read-only` 工具。 | 是 |
| `defer` | 当前调用需要用户审批或受管控执行流程。 | 否 |
| `deny` | 当前调用被硬拒绝。 | 否 |

## 直接执行

通常只有满足以下条件的工具会直接执行：

- 工具已注册。
- 风险等级是 `read-only`。
- 参数通过 `ResourcePolicy`。
- 当前 TaskExecution / visibility boundary 允许该工具。

示例：

- workspace 范围内的只读文件读取。
- 安全范围内的只读查询工具。

注意：

- `shell` 即使声明为 `read-only`，也默认进入 approval/sandbox 路径。
- 未注册工具不会直接执行。

## 审批流程

当工具调用存在写入、副作用、shell 或未知风险时，会生成 approval request。

常用命令：

```text
/approvals
/approve_tool <approval_id>
/deny_tool <approval_id> [reason]
```

审批绑定：

- `approval_request_id`
- `session_key`
- `request_id`
- `tool_name`
- `approval_scope`
- `args_hash`

这些字段来自 runtime 持久记录，不相信模型工具参数里的 approval id。approval 是 single-use，过期、换参、denied、重复 consume 都不会执行。

## Approved File Side Effects

当前支持受管控执行和 rollback 的文件副作用工具：

- `write_file`
- `edit_file`

流程：

```text
tool call
  -> defer / approval request
  -> /approve_tool <approval_id>
  -> /prepare_tool <approval_id>
  -> preview / diff / snapshot
  -> /run_approved_tool <approval_id>
  -> apply
  -> rollback handle
  -> /rollback_tool <approval_id>
```

可 rollback 的范围：

- 仅限 approved `write_file` / `edit_file`。
- 执行前有 snapshot / preview。
- 成功 apply 后记录 rollback handle。

不可 rollback 的范围：

- shell。
- external API。
- destructive operation。
- 任意未受管控的宿主副作用。

## Approved Shell Sandbox

当前 approved `shell` 不会回到普通宿主 shell。它进入 `ApprovedShellSideEffectRuntime`，重新校验 payload、approval、args hash、session、tool 和 policy，然后生成 sandbox preview，并通过 Docker/Podman sandbox runner 执行。

当前 sandbox 边界：

- Docker/Podman runner。
- sandbox 不可用时 fail closed。
- workspace read-only mount。
- network off。
- non-root user。
- read-only rootfs。
- cap drop。
- no-new-privileges。
- pids / memory / cpu / timeout limits。

不支持：

- network-enabled shell sandbox。
- host writable shell。
- shell rollback。
- TaskExecution shell resume。
- external API replay。

## Destructive Commands

当前 destructive shell command 直接拒绝，不进入 approval，也不进入 sandbox。

示例：

- `rm`
- `rmdir`
- `unlink`
- `shred`
- `dd`
- `mkfs`
- `chmod`
- `chown`
- `truncate`

`shell_restore` 已关闭，不再把 `rm` 自动改写为 `mv`。原因是 pre-hook 在 policy 前运行，自动改写会隐藏原始 destructive 意图，使后续 policy 只看到改写后的副作用。

如果后续需要“可恢复删除”，应单独设计显式 `move_to_trash` / `managed_delete` 工具，并接入 workspace scope、preview、approval、audit 和 rollback。当前没有实现该能力。

## Hook 边界

当前生产 pre-hook：

| hook | 状态 | 职责 |
|---|---|---|
| `shell_safety` | 可用 | deny-only，拦截交互式 shell、可能等待密码的 sudo、缺少确认参数的包管理器写操作等。 |
| `tool_loop_guard` | 可用 | deny-only，拦截连续重复工具调用。 |
| `shell_restore` | 已关闭 | legacy disabled，不再注册 pre-hook，不再执行 `rm -> mv`。 |

允许的 hook 职责：

- deny。
- 参数归一化。
- 补安全默认值。
- 循环保护。
- 安全拦截。

不允许的 hook 职责：

- 静默改变副作用语义。
- 把 destructive 意图改写成看似低风险的副作用。
- 绕过 `ToolInvocationPolicy`、`ResourcePolicy`、approval 或 managed runtime。

## Audit

当前已有 workspace-scoped `ToolAuditLedger`：

```text
<workspace>/tool_audit/tool_audit.db
```

可查询命令：

```text
/tool_audit [limit]
/tool_audit request <request_id>
/tool_audit approval <approval_id>
/tool_audit tool <tool_name> [limit]
/tool_audit event <event_type> [limit]
```

当前 `/tool_audit` 默认当前 session 范围，不提供跨 session admin 查询。

审计记录覆盖：

- policy decision。
- approval lifecycle。
- approved file side-effect lifecycle。
- approved shell sandbox lifecycle。

审计不保存：

- raw args。
- raw shell command。
- raw file path/content。
- raw diff text。
- payload path。
- stdout/stderr text。
- token、cookie、secret、authorization、API key。

## 当前推荐操作

短期推荐：

- 维持 destructive hard deny。
- 使用 approved file side-effect runtime 处理文件写入和回滚。
- 使用 approved shell sandbox 处理必要 shell，但保持 network off、workspace read-only、fail closed。
- 用 `/tool_audit` 查询当前 session 的工具治理事件。

短期不推荐：

- 开放 destructive execution。
- 开放 shell rollback。
- 开放 network-enabled shell sandbox。
- 开放 TaskExecution shell resume。
- 开放 external API replay。

后续如果确实需要删除语义，优先设计显式、可预览、可审批、可恢复、可审计的 managed delete 工具，而不是开放通用 shell `rm`。
