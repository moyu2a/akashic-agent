# LA-002 TaskPlan Recovery and Execution Orchestration Design

日期：2026-07-15

状态：approved / implementation plan ready

关联问题：`LA-002 local-agent/task-execution/recovery`

实施计划：`docs/superpowers/plans/2026-07-15-task-plan-recovery-execution-implementation.md`

## 用户确认的产品边界

2026-07-15 用户逐项确认以下决策：

1. LA-002 第一版只自动执行 registry `read-only` 工具；write、external、unknown 和 shell 只进入 `waiting_authorization`，批准后执行留给 P2。
2. stale running attempt 在重启或 lease 过期后转为 `blocked/outcome_unknown`，step 恢复 pending，但绝不自动重试。
3. 相同 transport request ID 视为重投并返回原 attempt；两条独立“继续”视为两个有效操作，不使用文本 hash 去重。
4. failed step 不能被普通“继续”跳过或自动重试；用户必须显式 retry 或 skip，retry 创建新 attempt。
5. 自动完成必须有至少一个成功真实工作工具 event，并通过 finish 合同；没有工具证据的纯思考步骤只能手动更新。

## 1. 背景

TaskPlan 第一阶段和 `LA-001` 已经完成以下能力：

- 每个 session 一个 active task。
- TaskPlan 与 TaskStep 的 SQLite 持久化。
- 创建、查看、手动更新计划步骤。
- active task 的限长 prompt context。
- TaskPlan 工具 deferred、non-LRU。
- create/inspect/update 的严格 capability scope。
- 纯计划不召回，显式偏好/历史最多一次对应召回。
- TaskPlan 操作成功后 action-aware final-only。

2026-07-15 主服务 turn `389-392` 再次证明这些状态与授权能力可用。但当前系统仍然只会“记录计划”，没有一个可靠的执行模型回答以下问题：

- Agent 重启时，原来 `in_progress` 的步骤到底是否仍在执行？
- 用户重复发送“继续下一步”时，如何避免重复产生副作用？
- 一次步骤执行由哪些工具结果支撑，何时允许标记为完成？
- 工具已经产生外部副作用但进程在结果落库前崩溃时，系统应如何恢复？
- 在完整权限模型尚未实现时，哪些工具允许自动执行？

`LA-002` 解决的是任务执行状态、恢复和编排边界，不重新设计 `LA-001` 的上下文授权，也不把 TaskPlan 变成一个自由运行的后台 Agent。

## 2. 目标

第一阶段目标：

1. 为每次步骤推进建立独立、持久化的 execution attempt。
2. 同一个 request 只能创建一个 attempt，同一步骤同时只能有一个非终态 attempt。
3. Agent 重启或 lease 失效后能够识别 stale attempt，且默认不自动重放。
4. 用户说“继续执行下一步”时，一次只 claim 一个步骤。
5. 只允许明确 `read-only` 的工具进入第一版自动执行范围。
6. 写入、外部副作用、未知风险和 shell 进入 `waiting_authorization`，不真实执行。
7. 任意工作工具成功都不能直接完成步骤；必须经过 attempt finish 合同。
8. 复用 Tool Access Gateway、Turn Tool Boundary 和 Turn Completion，不改 AgentLoop 主循环。
9. execution contract、attempt 和恢复状态不进入 LRU/ToolDiscoveryState。

## 3. 非目标

本阶段不实现：

- 任意 shell、文件写入、删除或外部系统写操作的自动批准。
- 完整权限 UI、目录 ACL、命令规则或审批记忆。
- 文件 diff 审查、快照和回滚。
- 一次自动执行多个 TaskStep。
- 自动无限重试、自动跳过失败步骤或失败后自动执行下一步。
- 多 active task、多 Agent 分布式执行或跨机器 lease。
- 暂停/恢复整个 TaskPlan、复杂 DAG 或步骤依赖图。
- 用 CoT/ToT 代替确定性状态机。
- exactly-once 外部副作用承诺。

## 4. 方案比较

### 方案 A：直接让模型读取 active task 后自由调用工具

优点：实现快，改动少。

缺点：没有 attempt、幂等、恢复和权限事实源；会重新出现长工具链、重复执行和状态误报。不能接受。

### 方案 B：把每个步骤变成固定 workflow

优点：执行路径确定，容易控制成本。

缺点：TaskStep 当前是自然语言，开发任务类型差异大；过早固定 workflow 会把 TaskPlan 和 Document RAG、shell、文件工具强耦合。暂不采用。

### 方案 C：持久化 attempt + 受控单步 ReAct

优点：状态和授权确定，工作工具仍可按步骤选择；可以复用现有 Gateway、Boundary、Completion，也能逐步接入权限插件。

缺点：需要增加 attempt/event schema、动态 execution contract 和恢复逻辑。

决策：采用方案 C，并拆成两个交付切片：

- `LA-002a Recovery Foundation`：attempt、event、幂等、lease、启动/会话恢复。
- `LA-002b Controlled Read-only Execution`：单步 claim、只读工具 scope、finish/defer、completion 和 live smoke。

## 5. 设计原则

### 5.1 状态与策略分离

- SQLite 是 attempt 和恢复事实源。
- Typed contract 是当前 turn 授权源。
- Policy metadata 只用于日志，不能反序列化为授权。
- Prompt 只能解释边界，不能承担执行安全。

### 5.2 Step 与 Attempt 分离

- `TaskStep.status` 表达业务进度。
- `TaskExecutionAttempt.status` 表达一次执行尝试的生命周期。
- 多次 retry 产生多个 attempt，不能覆盖历史 attempt。
- attempt/event 不写入 `TaskStep.metadata`。

### 5.3 不声称 exactly-once

数据库事务无法和任意外部工具副作用组成同一个原子事务。如果工具已经产生副作用，但进程在记录成功前崩溃，结果只能标记为 unknown/blocked，不能自动重放。

第一版通过以下方式降低风险：

- 只自动执行明确 `read-only` 的工具。
- 非只读工具只记录授权请求，不真实执行。
- stale running attempt 默认 blocked，需要显式恢复决定。

### 5.4 不依赖当前 AgentLoop 串行实现

当前 AgentLoop 串行消费 inbound message，但数据库仍必须使用唯一约束和事务保证 attempt claim。未来即使改为 session 并行，也不能破坏不变量。

## 6. 总体架构

```text
Inbound request
      |
      v
TaskExecutionTurnContract
      |
      v
TaskExecutionOrchestrator
      |
      +--> TaskPlanService ownership check
      +--> TaskPlanStore atomic claim/finalize
      +--> TaskExecutionRecoveryService reconcile
      |
      v
ToolAccessGateway
      |
      v
TurnToolBoundaryManager
      |
      v
ToolRegistry / ToolExecutor
      |
      +--> persistent attempt event
      |
      v
TaskExecutionCompletionPolicy
      |
      v
final-only
```

AgentLoop 只继续负责消费 inbound item 和运行 turn。执行状态转换位于 TaskPlan core/service/policy 边界，不加入 AgentLoop 的长期状态字段。

## 7. 模块划分

建议新增：

```text
agent/task_plan/
  execution_models.py
  execution_store.py
  execution_service.py
  recovery.py
  orchestrator.py

agent/policies/
  task_execution_contract.py
  task_execution_access.py
  task_execution_budget.py
  task_execution_completion.py

agent/tools/
  task_execution.py
```

职责：

| 模块 | 职责 |
| --- | --- |
| `execution_models.py` | attempt/event 类型、状态和转换校验 |
| `execution_store.py` | 在既有 TaskPlan DB 事务中执行 attempt/event SQL |
| `execution_service.py` | session ownership、claim、finish、defer、inspect 业务边界 |
| `recovery.py` | startup/session reconcile、stale 判定、unknown outcome 处理 |
| `orchestrator.py` | 选择一个步骤并返回确定性执行决策 |
| `task_execution_contract.py` | 当前 turn action/phase/capability/risk/budget 合同 |
| `task_execution_access.py` | 将合同映射到工具 schema、tool search 和 execution block |
| `task_execution_budget.py` | attempt 工作工具预算和重复调用控制 |
| `task_execution_completion.py` | finish/defer/blocked 后进入 final-only |
| `task_execution.py` | 薄工具适配器，不直接访问 SQLite |

## 8. Core 与插件边界

必须属于 core module：

- Attempt/Event 数据模型与数据库约束。
- session ownership。
- claim、状态转换、幂等和恢复。
- runtime-owned request/attempt identity。
- 默认 deny/defer 安全规则。

可插件化扩展：

- 根据工作区、工具、参数和用户配置作出的授权策略。
- 自定义步骤执行器或固定 workflow adapter。
- 执行前后审计、通知和指标。
- 后续的审批 UI 或远程审批 channel。

插件只能返回 allow/defer/deny 决策，不能直接修改 attempt 表。最终状态变更必须经过 `TaskExecutionService`。

策略合并优先级：

```text
core deny > plugin deny > defer > allow
```

第一版只实现 core 默认策略，不要求现有插件管理器立即支持 execution policy 注册。

## 9. 数据模型

### 9.1 TaskExecutionAttempt

```text
attempt_id
task_id
step_id
session_key
request_id
idempotency_key
attempt_no
status
execution_mode
owner_instance_id
lease_expires_at
source_turn_id
requested_tool_name
requested_arguments_json
requested_capabilities_json
result_summary
error_code
terminal_reason
created_at
started_at
updated_at
finished_at
metadata_json
```

`execution_mode` 第一版只有：

- `read_only_auto`
- `authorization_required`

敏感数据约束：

- 普通 event 默认只保存参数摘要、稳定 hash 和 redacted preview。
- 等待授权的 proposed arguments 可以保存完整结构，但必须经过现有/新增 redaction，并设置大小上限。
- secret、token、Authorization header 和环境变量值不得写入普通 trace。

### 9.2 TaskExecutionEvent

```text
event_id
attempt_id
sequence_no
event_type
tool_name
execution_status
result_ok
error_code
arguments_hash
result_preview
created_at
metadata_json
```

第一版 event type：

- `attempt_claimed`
- `attempt_started`
- `tool_started`
- `tool_finished`
- `authorization_deferred`
- `attempt_succeeded`
- `attempt_failed`
- `attempt_blocked`
- `attempt_cancelled`
- `recovery_reconciled`

## 10. Attempt 状态机

```text
pending
  |-- execution scope ready --> running
  |-- side effect required --> waiting_authorization
  |-- crash/reconcile -------> blocked
  |-- explicit abort --------> cancelled

running
  |-- finish success --------> succeeded
  |-- finish failure --------> failed
  |-- side effect required --> waiting_authorization
  |-- lease/restart ---------> blocked
  |-- explicit abort --------> cancelled

waiting_authorization
  |-- P2 approval -----------> pending       # LA-002 不启用该转换
  |-- explicit abort --------> cancelled

succeeded / failed / blocked / cancelled
  |-- no transition; retry creates a new attempt
```

合法状态集合：

```text
pending
running
waiting_authorization
succeeded
failed
blocked
cancelled
```

终态：`succeeded/failed/blocked/cancelled`。

`waiting_authorization` 是持久化非终态，但当前 turn 必须结束，不能继续生成工作工具调用。

## 11. Step 与 Attempt 映射

| Attempt 状态 | TaskStep 状态 | 说明 |
| --- | --- | --- |
| `pending` | `pending` | 已 claim，尚未进入工作 scope |
| `running` | `in_progress` | 正在执行只读工作 |
| `waiting_authorization` | `pending` | 等待权限，不表示已经开始副作用 |
| `succeeded` | `completed` | finish 合同验证成功 |
| `failed` | `failed` | 需要显式 retry，不自动跳到下一步 |
| `blocked` | `pending` | 结果未知或恢复受阻，需显式处理 |
| `cancelled` | `pending` | attempt 取消，不等于跳过步骤 |

TaskPlan 仍只在所有步骤为 `completed/skipped` 时自动完成。单个 failed step 不自动把整个 TaskPlan 标记 failed。

## 12. SQLite 约束与事务

新增表：

```sql
CREATE TABLE task_execution_attempts (...);
CREATE TABLE task_execution_events (...);
```

关键唯一约束：

```sql
UNIQUE(step_id, attempt_no)
UNIQUE(session_key, request_id)
UNIQUE(idempotency_key)
```

Partial unique indexes：

```sql
UNIQUE(step_id)
WHERE status IN ('pending', 'running', 'waiting_authorization');

UNIQUE(task_id)
WHERE status IN ('pending', 'running', 'waiting_authorization');
```

这同时保证：

- 同一步骤只有一个 active attempt。
- 同一个 TaskPlan 一次只推进一个步骤。
- 同一个可信 request ID 不会创建两个 attempt。

所有 claim/finalize/reconcile 使用 `BEGIN IMMEDIATE`。claim 必须在一个事务内：

1. 验证 task 属于当前 session 且为 active。
2. 检查/处理已有 active attempt。
3. 选择最低 index 的 pending step；failed step只允许显式 retry。
4. 分配 `attempt_no`。
5. 插入 attempt 和 `attempt_claimed` event。
6. commit 后返回 typed attempt。

`execution_store.py` 可以拆分 SQL helper，但事务和连接仍由同一个 TaskPlan persistence boundary 持有，不能让两个 repository 分别提交 step 与 attempt。

迁移策略：第一版仅新增表和索引，使用幂等、事务化 migration；不重写已有 plan/step 数据。旧 active task 没有 attempt 时仍可正常 inspect/update。

## 13. Request identity 与幂等

不能使用用户文本 hash 作为幂等键，因为用户连续两次发送“继续”可能是有意推进两个不同步骤。

request ID 优先级：

1. channel 提供并经过保护的稳定 message/request ID。
2. IPC v2 客户端生成的 per-message UUID，server 放入 `InboundMessage.metadata`。
3. runtime 在 turn 开始时生成的 UUID；在同一 turn 的 retry/trim/safety retry 中复用。

`idempotency_key` 由 runtime 生成：

```text
sha256(session_key + request_id + task_id + step_id + action)
```

模型不能传入或覆盖 `_request_id`、`_idempotency_key`、`_attempt_id`。

保证范围：

- 有稳定 transport request ID：可防止断线重投产生重复 attempt。
- 只有 runtime UUID：保证同一 turn 内部 retry 幂等，并由 active-attempt/step 状态防止并发 claim；不能把两个独立 inbound message 猜测为同一请求。

## 14. TaskExecutionTurnContract

不扩张已有 `TaskPlanTurnContract`。新增独立 immutable contract：

```text
action:
  inactive | continue | retry | inspect | abort

phase:
  inactive | claim | work | waiting_authorization | finish | terminal

attempt_id
required_capabilities
allowed_capabilities
allowed_risks
work_call_budget
completion_capability
```

初始 capability vocabulary：

```text
task_execution.begin
task_execution.inspect
task_execution.finish
task_execution.defer
task_execution.abort
```

合同优先级：

1. 显式 create/inspect/update TaskPlan 继续由 `TaskPlanTurnContract` 处理。
2. “继续/执行下一步/重试该步骤”进入 execution contract。
3. “查看后台任务/job/subagent”继续走 background passthrough。
4. 普通对话不激活 execution contract。

两个 contract 同一 turn 不得同时 strict-active。冲突时显式 update/inspect 优先于模糊“继续”。

## 15. 工具适配器

建议提供五个薄工具：

### `begin_task_step_execution`

- capability：`task_execution.begin`
- risk：`write`
- non-LRU
- 使用 protected session/request identity claim 一个步骤。
- 返回 attempt、step、execution mode 和下一阶段提示。

### `finish_task_step_execution`

- capability：`task_execution.finish`
- risk：`write`
- non-LRU
- `_attempt_id` 由 runtime 注入。
- service 验证 attempt 事件和工具结果后才允许 success。

### `request_task_step_authorization`

- capability：`task_execution.defer`
- risk：`write`
- non-LRU
- 记录请求的工具/capability、参数和理由，将 attempt 转为 waiting。
- 本阶段不批准或执行该副作用。

### `inspect_task_execution`

- capability：`task_execution.inspect`
- risk：`read-only`
- non-LRU
- 返回 active/latest attempt、恢复原因和等待授权摘要。

### `abort_task_step_execution`

- capability：`task_execution.abort`
- risk：`write`
- non-LRU
- 只允许终止当前 session 的 `pending/running/waiting_authorization` attempt。
- attempt 转为 cancelled，step 恢复 pending；保留全部 attempt/event 历史。

## 16. 受控单步执行流程

### 16.1 只读 happy path

```text
用户：继续执行下一步
  -> begin_task_step_execution
  -> execution contract phase=work
  -> scoped tool_search / read-only tool(s)
  -> finish_task_step_execution
  -> final-only
```

规则：

- 一次 turn 只有一个 attempt。
- 默认工作工具预算为 3 次真实执行。
- `tool_search` 结果只允许 exact `risk=read-only`，且仍受普通 access policy 约束。
- execution turn 解锁的工作工具不写 LRU。
- finish success 至少需要一个当前 attempt 的成功工作 event；纯状态/控制工具不算工作证据。
- 如果步骤本身不需要工具，用户应使用手动 `update_task_step`，不能伪造执行成功。

第一版目标轮次：

- 已知只读工具：`begin -> work tool -> finish -> final`，最多 4 轮。
- 需要 tool search：最多 5-6 轮。

### 16.2 需要副作用

```text
begin
  -> model 判断需要 write/shell/external-side-effect
  -> request_task_step_authorization
  -> attempt=waiting_authorization
  -> final-only，向用户说明待授权内容
```

第一版不得在同一 turn 中从 waiting 状态恢复并执行副作用。

### 16.3 失败

- 工具 `ok:false`、hook denied、executor error 都记录 event。
- 预算耗尽或无法取得必要信息时，attempt 标记 failed/blocked，并 final-only。
- failed step 不自动执行下一步。
- retry 必须由显式用户意图创建新 attempt_no。

## 17. 授权边界

第一版默认策略：

| Registry risk | 决策 |
| --- | --- |
| `read-only` | 可进入候选，仍受普通 access policy 和预算约束 |
| `write` | defer / waiting authorization |
| `external-side-effect` | defer / waiting authorization |
| `destructive` | core deny，绝不创建可批准的 LA-002 请求 |
| unknown / plugin default | defer |

特别约束：

- `shell` 无论命令文本看似只读，第一版都不自动执行。
- 风险分类来自 registry/runtime，不能相信模型参数声明。
- tool_search 结果过滤、schema visibility 和 execution gate 必须使用同一风险结论。
- 插件不能把 core deny 降级成 allow。

## 18. 工具事件与完成判定

每次真实工作工具执行后，runtime 将以下事实立即追加到 attempt event：

- tool name
- registry capability/risk snapshot
- execution status
- result ok/error code
- arguments hash/redacted preview
- bounded result preview

`finish_task_step_execution(success=true)` 的条件：

1. attempt 属于当前 session。
2. attempt 为 running。
3. 当前 turn/attempt 至少有一个成功工作 event。
4. 没有未解决的 deny/error 要求。
5. finish payload 合法且 result summary 非空。

工作工具成功不会自动结束 ReAct；只有 finish/defer/blocked 的持久化状态转换触发 `TaskExecutionCompletionPolicy`。

## 19. Recovery 设计

Runtime 启动时生成 `runtime_instance_id`。Attempt running 时记录 owner 和 lease。

恢复入口：

- bootstrap 完成 TaskPlan service wiring 后、AgentLoop 启动前执行一次 startup reconcile。
- 每次 execution inspect/claim 前执行当前 session reconcile。

恢复规则：

| 状态 | 条件 | 动作 |
| --- | --- | --- |
| `waiting_authorization` | 任意重启 | 保持等待，不自动批准 |
| `pending` | owner 为旧实例 | 转 blocked，reason=`dispatch_interrupted` |
| `running` | owner 为旧实例 | 转 blocked，reason=`runtime_restarted_outcome_unknown` |
| `running` | lease 过期 | 转 blocked，reason=`lease_expired_outcome_unknown` |
| terminal | 任意 | 不修改 |

stale attempt 对应 step：

- 如果 step 仍为 `in_progress`，原子恢复为 `pending`。
- attempt 保留 blocked 历史。
- 不自动创建 retry attempt。
- inspect 必须明确告诉用户“上次结果未知，需要检查后重试”。

即使第一版只自动执行 read-only，也保留 unknown-outcome 语义，避免未来接入副作用工具后更改恢复协议。

## 20. 动态工具可见性

Execution contract phase 变化后，`DefaultReasoner` 复用 LA-001 已有的网关重算模式：

- `claim`：只显示 begin/inspect。
- `work`：显示 finish/defer、scoped tool_search 和已授权 read-only 工具。
- `waiting_authorization`：不显示工作工具，当前 turn 下一轮 final-only；后续显式 abort turn 只显示 inspect/abort。
- `terminal`：不显示工具，下一轮 final-only。

所有工作工具还必须通过 `TurnToolBoundaryManager` 的执行前检查。模型即使硬调用隐藏的 write/shell 工具，也只能得到稳定的 authorization-required/blocked 结果，不能真实执行。

## 21. Budget 与停止条件

第一版预算：

- 每个 attempt 最多 3 次真实工作工具调用。
- 每个 attempt 最多一次 scoped `tool_search`；它不计入成功工作证据。
- control tools 不计入工作预算，但每类 control transition 只能成功一次。
- 相同工具和相同 arguments hash 的重复调用由 boundary soft-stop。
- 同批超过预算的候选执行 batch skip，不写成功 event。

达到以下任一条件后结束工具循环：

- attempt succeeded。
- attempt failed/blocked/cancelled。
- attempt waiting authorization。
- 工作预算耗尽且无法 finish。

Completion 只读取 typed contract、persistent attempt state 和 executor ledger，不从自然语言 result preview 猜测完成。

## 22. Prompt context

Active TaskPlan context 增加限长 execution 摘要：

```text
Execution:
- attempt: attempt_xxx
- step: 1
- state: waiting_authorization
- requested capability: workspace.write
- last result: ...
```

约束：

- 只展示当前或最近 attempt，不注入完整 event history。
- 参数只显示 redacted summary。
- 无 active attempt 时不增加 execution block。
- Prompt 不列出 strict scope 禁止调用的具体工具目录。

## 23. 配置

建议新增保守配置：

```toml
[task_execution]
enabled = false
auto_allowed_risks = ["read-only"]
max_work_tool_calls = 3
lease_seconds = 300
```

默认 `enabled=false`，完成自动化、迁移和真实 smoke 后再考虑默认开启。

配置约束：

- `auto_allowed_risks` 第一版不能配置 `write/external-side-effect/destructive`。
- 非法高风险配置启动时拒绝或降级为只读，并输出明确日志。
- 关闭 task execution 不影响现有 create/inspect/update TaskPlan。

## 24. 错误处理

稳定 error/reason 建议：

- `task_execution_disabled`
- `task_execution_no_active_task`
- `task_execution_no_pending_step`
- `task_execution_failed_step_requires_retry`
- `task_execution_request_replayed`
- `task_execution_attempt_already_active`
- `task_execution_authorization_required`
- `task_execution_work_budget_exhausted`
- `task_execution_attempt_not_running`
- `task_execution_result_evidence_missing`
- `task_execution_runtime_restarted_outcome_unknown`
- `task_execution_lease_expired_outcome_unknown`

对模型返回结构化、可继续处理的 tool result；对用户最终回答使用简短、明确的状态说明。

## 25. 可观测性

日志标签：

```text
[task_execution] contract ...
[task_execution] claimed ...
[task_execution] tool_event ...
[task_execution] deferred ...
[task_execution] recovered ...
[task_execution] completed ...
```

Observe metadata 增加：

- attempt_id
- task_id/step_id
- action/phase
- request replay hit
- work tool count/budget
- authorization decision
- recovery action/reason
- final attempt state

禁止把完整敏感参数复制到普通 observe metadata。

## 26. 测试策略

### Model/transition tests

- 所有合法状态转换。
- terminal attempt 不可复活。
- retry 必须新建 attempt。
- Step/Attempt 映射正确。

### Store tests

- migration 幂等。
- 一个 task 只有一个 active attempt。
- 一个 step 只有一个 active attempt。
- request ID replay 返回原 attempt。
- claim/finalize/reconcile 原子性。
- 并发 claim 只有一个成功。

### Service/orchestrator tests

- session ownership。
- lowest pending step selection。
- failed step 阻止普通 continue，显式 retry 创建新 attempt_no。
- no active task/no pending step 稳定返回。
- 同一 request replay 不推进下一步骤。

### Recovery tests

- old runtime pending/running 变 blocked。
- waiting authorization 跨重启保留。
- step `in_progress` 在 unknown outcome 后恢复 pending。
- recovery 不自动执行工具或创建 retry。

### Gateway/boundary tests

- claim/work/waiting/terminal visibility。
- 只读 tool search 过滤。
- write/shell/unknown 风险不可见且不可执行。
- plugin allow 不能覆盖 core deny。
- 工作预算和 same-batch skip。
- execution 工具不写 LRU。

### Completion tests

- 工作工具成功但未 finish 时不完成。
- 无成功工作 event 的 finish success 被拒绝。
- finish/defer/blocked 后 final-only。
- denied/error payload 不能被误判 success。

### Compatibility tests

- TaskPlan create/inspect/update 与 LA-001 保持不变。
- Document RAG、Turn Trace、memory/session 和 background passthrough 保持不变。
- `task_execution.enabled=false` 时普通 turn 行为不变。
- IPC v2 request ID 不破坏旧 client 兼容。

## 27. 真实 CLI Smoke

使用独立 session 和只读步骤：

```text
为检查项目状态创建两步计划：第一步读取 README.md 标题，第二步总结测试命令。只创建计划。
继续执行下一步
当前任务和执行尝试是什么状态？
```

预期：

- 只 claim Step 1。
- 只执行 read-only 工具。
- `begin -> read -> finish -> final`，通常不超过 4-6 轮。
- Step 1 completed，Step 2 pending。
- 重发相同 transport request ID 不创建新 attempt、不推进 Step 2。

重启恢复 smoke：

1. 创建 running attempt 后模拟进程中断。
2. 重启 Agent。
3. inspect execution。

预期：attempt blocked，reason 为 outcome unknown，step 返回 pending，不自动重放。

副作用 smoke：

```text
继续执行需要修改文件的下一步
```

预期：attempt waiting authorization，不执行 write/shell，不改变目标文件。

## 28. 验收标准

LA-002 完成必须同时满足：

- 同一可信 request ID 只有一个 attempt。
- 同一 task/step 同时只有一个 active attempt。
- 一次 turn 最多推进一个步骤。
- stale attempt 可恢复且不自动重放。
- 第一版自动执行的真实工作工具全部为 registry `read-only`。
- write/shell/external/unknown 真实执行次数为 0。
- success step 有持久化成功工作 event 和 finish transition。
- failed/denied/error 不会标记 completed。
- execution contract/attempt 不进入 LRU/ToolDiscoveryState。
- AgentLoop 主循环无执行状态机分支。
- 现有完整 pytest 无回归，并增加并发、重启、重复请求和权限负向测试。
- 真实 CLI smoke 覆盖 happy path、request replay、restart recovery 和 authorization defer。

## 29. 分阶段交付

### LA-002a Recovery Foundation

- 数据模型、migration、attempt/event store。
- request identity 和幂等 claim。
- recovery service 与 inspect。
- 默认关闭，不执行工作工具。

### LA-002b Controlled Read-only Execution

- execution contract、orchestrator 和 thin tools。
- 动态 gateway scope、只读 tool search、预算和 completion。
- authorization defer，不执行副作用。
- 自动化与真实 smoke。

### 后续 P2/P3

- P2 接入本地操作权限与用户确认，决定 waiting attempt 是否可恢复。
- P3 接入 diff/snapshot/rollback 后，才考虑放开受控文件写入。
- destructive 操作即使后续开放，也必须保持更高等级确认和补偿策略。

## 30. 最终结论

`LA-002` 应作为 TaskPlan core module 的下一层，而不是普通插件或 AgentLoop 分支。Core 负责持久化事实、状态转换、幂等和恢复；Gateway/Boundary/Completion 负责当前 turn 的工具授权与收尾；插件只扩展授权和审计策略。

第一版以“只读自动执行、其他副作用待授权、崩溃不自动重放”为安全边界。它不会直接完成完整本地开发 Agent，但会建立后续权限模型、文件回滚和开发任务闭环必须依赖的可靠执行底座。
