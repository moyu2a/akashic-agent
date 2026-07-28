# Tool Governance Current State

日期：2026-07-28

本文记录当前工具治理主线的阶段结论：已经新增了哪些能力、哪些能力仍未开放、当前是否已经具备 sandbox 和 rollback，以及后续是否继续复杂化。

## 总结结论

当前工具治理核心能力已经完成到 P4c：`policy gate + resource policy + durable approval + managed file side-effect runtime + sandboxed shell + persistent redacted audit ledger`。P4d 已完成文档和 smoke 收尾，没有新增运行时执行能力。

对本项目当前阶段来说，P4d 后的状态已经是一个合适的安全治理停靠点。后续推荐暂停高风险执行能力扩展；除非出现明确产品需求，不建议马上进入 P5 external API side-effect replay。

完成度估算：

- 工具安全治理底座：约 `80%`。
- 完整工具能力平台：约 `60% - 65%`。
- 高风险外部执行开放程度：刻意保持低开放，很多能力仍关闭。

这个估算不是按文件数量，而是按能力边界：调用前裁决、审批、文件回滚、shell sandbox 和持久审计这些关键安全层已经完成；外部 API replay、跨 session admin audit、TaskExecution shell/external resume 等高风险或产品化能力还没有做。

## 单次工具调用治理链路

当前一个工具调用不是“模型生成就直接执行”，而是按以下链路流转：

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

每一步目的：

1. `LLM tool_call`：模型提出想调用的工具和参数。它只是请求，不是可信执行事实。
2. `ToolAccessGateway / visibility boundary`：检查工具是否注册、是否可见、是否被禁用、当前 TaskExecution 阶段是否允许暴露或调用。
3. `ToolExecutor`：统一执行入口，保证工具调用先经过 hook、policy、approval 和 audit，而不是裸调 `tool.execute(args)`。
4. `pre-hook`：执行前横切治理。当前生产保留 deny-only / guard-only hook，例如 `shell_safety` 和 `tool_loop_guard`；`shell_restore` 已关闭。pre-hook 机制支持改参，但当前治理边界不允许用它做副作用语义改写。
5. `ToolInvocationPolicy`：按工具注册状态和风险等级做调用级裁决。未注册工具 deny；`destructive` deny；`read-only` 通常 allow；`write`、`shell`、`external-side-effect`、`unknown` 通常 defer。
6. `ResourcePolicy`：按具体参数做资源边界检查。覆盖文件路径 workspace scope、shell destructive command、URL/localhost/private IP、runtime protected argument 伪造等。
7. `RiskStrategy / approval request`：对未被硬拒绝但存在副作用或风险未知的调用生成审批请求。此时不触达真实 invoker，只记录 tool、risk、reason、approval scope、args hash 和脱敏摘要。
8. `Managed Runtime`：用户批准后仍不裸执行。文件副作用进入 payload 校验、policy 复查、preview/diff、apply、rollback handle；shell 进入 payload 校验、policy 复查、sandbox preview 和 Docker/Podman sandbox 执行。
9. `real invoker / sandbox`：只有前面所有 gate 通过，才触达真实执行入口。若结果是 deny 或 defer，则 `invoker_reached=false`。
10. `post observation`：执行后的观察层。`ToolExecutor` 框架支持 `post_tool_use` / `post_tool_error`，但当前生产插件尚未注册真正的 post ToolHook；已有 `@on_tool_result` 事件用于部分工具结果观察。
11. `audit / observe`：记录 policy trace、audit trace、approval lifecycle、side-effect 状态和 `ToolAuditLedger` 事件。审计层保持脱敏，不保存 raw command、raw path/content/diff、payload path、stdout/stderr 或凭证。

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

### Hook 边界更新

已完成：

- `shell_restore` 降级为 legacy disabled，不再注册 `@on_tool_pre`。
- 不再支持把 `rm` 自动改写为 `mv` 到恢复目录。
- `rm`、`rmdir`、`unlink` 等 destructive shell command 由 `ResourcePolicy` 拒绝。
- 保留 `shell_safety`、`tool_loop_guard` 这类 deny-only / guard-only hook。

结论：

- hook 机制继续存在，但职责收窄为 deny、参数归一化、默认值补全、循环保护和安全拦截。
- hook 不应静默改变副作用语义，也不应把 destructive 意图改写成另一个看似低风险的副作用。
- 如果后续需要“移动到回收区”，应做成显式受管控工具，并接入 approval、preview、audit 和 rollback 设计。

当前生产 hook 状态：

| hook / 能力 | 当前状态 | 说明 |
|---|---|---|
| `shell_safety` | 可用 | deny-only，拦截交互式 shell、可能等待密码的 sudo、缺少确认参数的包管理器写操作等。 |
| `tool_loop_guard` | 可用 | deny-only，拦截连续重复工具调用，防止工具循环。 |
| `shell_restore` | 已关闭 | legacy disabled，不再执行 `rm -> mv`。 |
| 参数归一化 hook | 机制支持，暂无主要生产实现 | 只适合不改变语义的格式整理。 |
| 补默认值 hook | 机制支持，暂无主要生产实现 | 只适合补安全默认值。 |
| 副作用语义改写 hook | 不推荐，当前关闭 | 例如 `rm -> mv` 会隐藏原始 destructive 意图。 |

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

## 本轮讨论确认的问题和边界

### 1. `rm` 不能通过 hook 自动安全化

当前不再采用 `shell_restore` 的 `rm -> mv` 改写。原因是 pre-hook 在 policy 前运行，若它把 `rm` 改成 `mv`，后续 `ToolInvocationPolicy` / `ResourcePolicy` 看到的是改写后的命令，原始 destructive 意图会丢失。

结论：

- `rm`、`rmdir`、`unlink`、`shred`、`dd`、`mkfs`、`chmod`、`chown`、`truncate` 当前按 destructive shell command 拦截。
- destructive shell command 直接 deny，不进入 approval，不进入 sandbox，不执行。
- 如果用户需要“删除”语义，后续应做显式 `move_to_trash` / `managed_delete` 工具，而不是恢复 shell hook 自动改写。

### 2. approval 不是直接执行授权

对 `write_file/edit_file` 这类文件副作用，当前是两段式：

```text
模型提出工具调用
  -> defer / approval request
  -> 用户 approve
  -> prepare preview / diff
  -> run approved tool
  -> apply
  -> rollback handle
```

第一段 approval 表示“允许进入受管控执行流程”；第二段 run/apply 才是真正落盘。这样可以防止用户在没有看 preview/diff 的情况下直接写入，也能用 args hash、session、tool、scope 防止审批后换参。

### 3. shell approval 后仍必须走 sandbox

approved shell 不会回到普通宿主 shell。它进入 `ApprovedShellSideEffectRuntime`，重新校验 payload、approval、args hash、session、tool 和 policy，再生成 sandbox preview，并通过 Docker/Podman sandbox 执行。sandbox 不可用时 fail closed。

当前 shell sandbox 没有 rollback，也不支持 network-enabled sandbox。

### 4. post-hook 治理能力还没有生产化

`ToolExecutor` 框架层支持：

- `post_tool_use`
- `post_tool_error`

但当前生产插件没有注册真正的 post ToolHook。已有的是插件事件层 `@on_tool_result`，例如 `recall_inspector` 用它观察 `recall_memory` 工具结果。

结论：

- “工具结果观察”已有一部分能力。
- “治理链路 post ToolHook 插件”接口存在，但生产尚未用起来。
- 它不是当前安全边界的关键层；核心安全边界仍在 pre-hook、policy、resource policy、approval 和 managed runtime。

### 5. 参数归一化和补默认值是机制能力，不是当前主要生产能力

pre-hook 机制技术上可以更新参数，因此可以支持参数归一化和补默认值。但当前生产插件主要只保留 deny/guard：

- 参数归一化：适合把路径、URL、大小写、空白等整理成规范形式，不改变工具语义。
- 补默认值：适合补 `encoding=utf-8`、`limit=50` 等安全默认值。
- 不允许借此改变副作用语义，例如删除变移动、外部发送变本地保存。

### 6. 当前安全删除的推荐方向

当前不能“安全执行 `rm`”。更合适的产品化能力是：

- 显式 `move_to_trash(path)` / `managed_delete(path)` 工具。
- path 必须在 workspace 内。
- 禁止 glob、parent escape、symlink escape 和系统保护路径。
- preview 列出将影响的目标。
- 用户 approval。
- apply 时移动到 workspace 内 `.trash/` / `.restore/`。
- 记录 audit ledger。
- 支持 rollback / restore。

这个能力如果要做，应作为单独 P4d/P5 设计，不应通过 shell pre-hook 静默实现。

## 仍未开放的能力

这些能力当前没有实现，且属于有意关闭：

- external API side-effect replay。
- destructive execution。
- TaskExecution shell resume。
- TaskExecution external side-effect resume。
- shell rollback。
- network-enabled shell sandbox。
- post ToolHook 生产插件。
- `move_to_trash` / `managed_delete` 这类安全删除工具。
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

1. P4d 作为当前工具治理阶段完成点。
2. 保留 P1-P4c 运行时能力边界，并以 P4d 文档和 smoke 作为交接记录。
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

P4d closeout smoke 结果：

```text
Hook/resource/policy smoke: 111 passed in 2.12s
File approval/rollback smoke: 20 passed in 1.69s
Shell sandbox governance smoke: 36 passed in 2.23s
Audit ledger smoke: 23 passed in 1.47s
```

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

1. 先确认是否只是 P4d 后的文档/运维精进，还是确实需要 P5 external API replay。
2. 如果只是文档/运维精进，优先改善 `/tool_audit` 查询体验、retention/prune/status 文档或 smoke 脚本化，不新增执行能力。
3. 如果是 P5，必须先写 design spec，再写 implementation plan，不直接实现 replay。
4. 无论 P4d/P5，都继续保持这些红线：
   - 不开放 destructive execution。
   - 不开放 shell rollback。
   - 不开放 network-enabled shell sandbox。
   - 不开放 TaskExecution shell/external resume，除非有单独设计。
   - 不保存 raw args、raw command、raw path/content/diff、payload path、stdout/stderr text 或凭证。
