# Tool Governance Current State

日期：2026-07-28

本文记录当前工具治理主线的阶段结论：已经新增了哪些能力、哪些能力仍未开放、当前是否已经具备 sandbox 和 rollback，以及后续是否继续复杂化。

## 总结结论

当前工具治理已经完成到 P4c：`policy gate + resource policy + durable approval + managed file side-effect runtime + sandboxed shell + persistent redacted audit ledger`。

对本项目当前阶段来说，P4c 已经是一个合适的安全治理停靠点。后续推荐先做一个小的 P4d 运维收尾，然后暂停高风险执行能力扩展；除非出现明确产品需求，不建议马上进入 P5 external API side-effect replay。

完成度估算：

- 工具安全治理底座：约 `80%`。
- 完整工具能力平台：约 `60% - 65%`。
- 高风险外部执行开放程度：刻意保持低开放，很多能力仍关闭。

这个估算不是按文件数量，而是按能力边界：调用前裁决、审批、文件回滚、shell sandbox 和持久审计这些关键安全层已经完成；外部 API replay、跨 session admin audit、TaskExecution shell/external resume 等高风险或产品化能力还没有做。

## 已经新增的能力

### P1: 统一工具调用裁决

已完成：

- 新增 `ToolInvocationPolicyEngine`。
- 工具调用进入真实 invoker 前先执行统一 policy。
- 支持 `allow`、`deny`、`defer`。
- 未注册工具和 `destructive` 默认 deny。
- `read-only` 默认 allow。
- `write`、`external-side-effect`、`unknown` 默认进入 defer 或审批路径。
- TaskExecution work phase 下非 read-only 能力进入 `waiting_authorization`。

价值：

- 工具系统从“模型请求什么就尝试执行什么”变成“运行时先裁决，再决定是否触达 invoker”。
- `deny/defer` 不会触达真实 invoker，并能在结果里表达 `invoker_reached=false`。

### P1.3: ResourcePolicy 参数级边界

已完成：

- 文件路径策略：`read_file/list_dir/write_file/edit_file` 默认受 workspace scope 约束。
- 拦截 workspace escape、symlink escape、受保护系统路径和畸形路径。
- 拦截模型伪造 runtime protected 参数，例如 `_session_key`、TaskExecution protected keys、`_request_id`。
- shell 参数 gate：保守拦截明显 destructive command、compound destructive command、`sudo/xargs` wrapper 和高危 inline interpreter marker。
- URL/network 参数 gate：拒绝 unsupported scheme、localhost、`.localhost`、`.local`、trailing-dot localhost、private/loopback/link-local/reserved/unspecified IP 和 no-host URL。

价值：

- 不是完整 sandbox，但在 invoker 前阻断最常见的本地路径逃逸、伪造上下文和 SSRF 类参数风险。

### P2: 默认风险策略和审批请求

已完成：

- 新增默认 risk strategy。
- `read-only` 自动 allow。
- `write`、`external-side-effect`、`unknown` 默认 defer。
- `destructive` 默认 deny。
- `shell` 或带 `shell.execute` / `process.execute` capability 的工具，即使 registry risk 是 read-only，也默认 defer。
- `defer` 结果生成结构化 `approval_request`。
- approval request 包含 tool、risk、reason、scope、args hash 和脱敏摘要。
- 新增 minimal audit trace，记录 policy action、reason、args hash、invoker reached/succeeded。

价值：

- 审批从自然语言状态变成结构化 runtime 协议。
- P2 仍不执行批准后的副作用，只生成请求和审计事实。

### P3: Durable trusted approval workflow

已完成：

- 新增 workspace-scoped SQLite approval store。
- 新增 `/approvals`、`/approve_tool <id>`、`/deny_tool <id>`。
- approval 绑定完整 tuple：
  - `approval_request_id`
  - `session_key`
  - `request_id`
  - `tool_name`
  - `approval_scope`
  - `args_hash`
- approval single-use：consume 后不能复用。
- 防换参、防过期执行、防 denied 执行、防模型伪造 approval id。
- trusted approval context 只能由 runtime code 构造，模型工具参数中的 approval id 不可信。
- approval lifecycle 进入 trace / observe。

价值：

- 形成 durable、trusted、single-use 的审批闭环。
- 普通模型输出不能直接绕过审批边界。

### P4a: Approved file side-effect execution

已完成：

- `write_file/edit_file` approved 后不再由普通 `ToolExecutor` 直接执行。
- 新增 workspace 私有 `SideEffectPayloadVault` 保存原始文件参数。
- 新增文件 preview/apply/rollback primitives。
- 新增 `ApprovedSideEffectStore` 记录 payload、preview、execution、rollback 状态。
- 新增 `ApprovedSideEffectRuntime`：
  - 校验 approval record。
  - 校验 payload hash / session / tool / scope。
  - 重新执行 P1 resource policy。
  - 生成 snapshot/diff preview。
  - trusted apply 后 finalize approval。
  - 成功 apply 后记录 rollback handle。
- 新增 trusted status/admin commands：
  - `/prepare_tool <approval_id>`
  - `/run_approved_tool <approval_id>`
  - `/rollback_tool <approval_id>`
- TaskExecution 只开放 managed file side-effect resume。

价值：

- 文件写入具备“先看 diff，再执行，必要时 rollback”的安全流程。
- 文件内容、真实路径、payload path、完整 diff 不进入 observe 或 ledger。

### P4b: Sandboxed approved shell execution

已完成：

- approved `shell` request 不再由普通 `ToolExecutor` 直接执行。
- approved shell 进入 `ApprovedShellSideEffectRuntime`。
- runtime 从私有 payload vault 读取原始 shell 参数。
- 重新执行 P1/P2 policy。
- 生成 sandbox preview。
- 只通过 Docker/Podman sandbox runner 执行。
- Docker/Podman 不可用时 fail closed，不回退宿主 shell。

当前 sandbox 配置：

- workspace read-only mount。
- network off。
- non-root user。
- read-only rootfs。
- cap drop。
- no-new-privileges。
- pids/memory/cpu/timeout limits。

价值：

- shell 已有第一版 sandbox。
- 它不是无限制宿主 shell，也不会在 sandbox 不可用时退回普通 shell。

### P4c: Persistent redacted ToolAuditLedger

已完成：

- 新增 workspace-scoped SQLite ledger：`<workspace>/tool_audit/tool_audit.db`。
- 新增 `ToolAuditLedgerEvent`、`ToolAuditLedgerQuery`、`ToolAuditLedgerStore`。
- 支持 record、query、prune。
- ledger 写入 fail-open，不改变工具执行、approval 状态或 side-effect 状态。
- 记录以下治理事件：
  - tool policy decision
  - approval requested/approved/denied/expired/consumed/executed/execution_failed
  - approved file side-effect payload/preview/apply/rollback/failure
  - approved shell sandbox payload/preview/execution/timeout/failure/persistence failure
- 新增 `/tool_audit` 只读查询命令：
  - `/tool_audit [limit]`
  - `/tool_audit request <request_id>`
  - `/tool_audit approval <approval_id>`
  - `/tool_audit tool <tool_name> [limit]`
  - `/tool_audit event <event_type> [limit]`
- `/tool_audit` 默认只查当前 `session_key`。

脱敏边界：

- 不保存 raw tool args。
- 不保存 raw shell command。
- 不保存 raw file path/content。
- 不保存 raw diff text。
- 不保存 payload path。
- 不保存 stdout/stderr text。
- 不保存 token、cookie、secret、authorization、API key。
- allowlisted metadata 同时校验 key 和 value。
- 凭证前缀值会被丢弃，例如 `ghp_`、`sk-proj-`、`cred_live_`。
- `/tool_audit` display 层再次 sanitize。

价值：

- 工具治理事实不再只散落在 turn trace、observe、approval store 和 side-effect store。
- 后续排查“为什么这个工具被拒绝/审批/执行/失败”有了统一持久审计投影。

## Sandbox 和 rollback 现状

### 已经有 sandbox

已有：approved shell sandbox。

范围：

- 只覆盖 approved `shell`。
- 只走 Docker/Podman sandbox runner。
- network off。
- workspace read-only。
- sandbox 不可用时 fail closed。

未覆盖：

- 不支持 network-enabled shell sandbox。
- 不支持普通未审批 shell 直接 sandbox 执行。
- 不支持 external API 工具 sandbox。

### 已经有 rollback

已有：approved file side-effect rollback。

范围：

- 覆盖 `write_file/edit_file`。
- 执行前生成 preview 和 snapshot。
- 成功 apply 后记录 rollback handle。
- `/rollback_tool <approval_id>` 可以回滚文件变更。

未覆盖：

- shell 没有 rollback。
- external API 没有 replay/rollback。
- destructive operation 没有执行也没有 rollback。

结论：

- “文件副作用”已经有可用 rollback。
- “shell 副作用”已有 sandbox，但没有 rollback。
- “外部 API 副作用”目前既没有 replay，也没有 rollback。

## 仍未开放的能力

这些能力当前没有实现，且属于有意关闭：

- external API side-effect replay。
- destructive execution。
- TaskExecution shell resume。
- TaskExecution external side-effect resume。
- shell rollback。
- network-enabled shell sandbox。
- `/tool_audit` 跨 session admin 查询。
- dashboard/admin audit search UI。
- 更完整的 retention 运维策略。
- mixed-resource policy，例如一个工具同时包含本地文件、URL、图片、附件参数。

## 后续候选能力

### 推荐短期: P4d 运维收尾

建议优先做小而稳的 P4d，而不是马上打开新执行能力。

候选内容：

- `/tool_audit` 输出更易读。
- `/tool_audit` 增加少量安全过滤或分页体验。
- 增加手动 prune/status 命令或配置化 retention。
- 写一份工具治理使用手册：
  - 哪些工具会直接执行。
  - 哪些工具需要 approval。
  - 哪些工具可 rollback。
  - shell sandbox 的限制。
  - 哪些能力明确不支持。
- 做一次真实 smoke：
  - file approval -> prepare -> run -> rollback -> `/tool_audit`。
  - shell approval -> sandbox run -> `/tool_audit`。

为什么推荐：

- 风险低。
- 能提升可观测性和可运维性。
- 不打开 external API 或 destructive 这类不可逆副作用。

### 中期可选: P5 external API side-effect replay design

只有在有明确产品需求时再做，而且应先 design-first。

必须先设计：

- 哪些 external-side-effect 工具允许 replay。
- payload 如何保存、绑定、脱敏。
- approval 如何防伪造、防换参、防复用。
- replay 前如何重新跑 URL/network/resource policy。
- 是否需要 per-tool idempotency key。
- 如何处理第三方 API 的成功、失败、超时和未知结果。
- 如何写入 `ToolAuditLedger`。
- 哪些外部操作仍必须禁止，例如支付、转账、删除云资源、凭证变更、批量通知。

风险：

- 外部 API 副作用通常不可逆。
- 第三方状态不受本地 SQLite 事务保护。
- 凭证治理、网络策略、幂等性和未知结果恢复都会明显增加复杂度。

### 不推荐短期做

- destructive execution。
- shell rollback。
- network-enabled shell sandbox。
- TaskExecution shell resume。

原因：

- 风险高。
- 需要更多产品级约束和人工确认体验。
- 当前项目收益不明显，容易把工具治理做得过度复杂。

## 推荐停止点

当前最合适的策略：

1. P4c 作为当前主线完成点。
2. 补一个 P4d 小收尾，增强文档、真实 smoke 和审计运维体验。
3. 暂停高风险能力扩展。
4. 后续只有出现真实需求时，再进入 P5 external API replay design。

不建议现在直接实现 P5。

原因：

- 当前已经具备本地 agent 工具治理的核心闭环。
- file side-effect 有 preview/apply/rollback。
- shell 有 sandbox 且 fail closed。
- 审计有持久 ledger 和只读查询。
- 继续打开 external API 或 destructive 能力会显著提高复杂度和风险。

## 当前验证

最近一次 P4c 验证结果：

```text
P4c direct regression: 58 passed in 3.76s
P4c focused governance: 160 passed in 6.30s
P1-P4c baseline: 197 passed in 4.01s
Compileall: exit 0
git diff --check: no output
git diff --check 7794819..HEAD: no output
```

## 后续恢复工作提示

如果后续继续工具治理，推荐从这里开始：

1. 先确认是否只是 P4d 运维收尾，还是确实需要 P5 external API replay。
2. 如果是 P4d，优先做真实 smoke 和 `/tool_audit` 运维体验，不新增执行能力。
3. 如果是 P5，必须先写 design spec，再写 implementation plan，不直接实现 replay。
4. 无论 P4d/P5，都继续保持这些红线：
   - 不开放 destructive execution。
   - 不开放 shell rollback。
   - 不开放 network-enabled shell sandbox。
   - 不开放 TaskExecution shell/external resume，除非有单独设计。
   - 不保存 raw args、raw command、raw path/content/diff、payload path、stdout/stderr text 或凭证。
