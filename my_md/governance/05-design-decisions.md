# Design Decisions

这个文档记录重要设计取舍，避免后续反复讨论同一问题。

## DD-001 测试目录保持原路径

日期：2026-07-03

决策：

- `my_md/test_docs/eval_suite` 暂时保持原路径。

原因：

- 该目录包含可执行 runner、测试集、历史报告和 README 命令示例。
- 移动路径会影响现有运行命令，不利于当前继续做回归测试。

影响：

- 文档分组时，只移动学习、架构、面试、RAG 文档。
- 测试体系仍统一放在 `my_md/test_docs`。

## DD-002 错误与演进记录单独建 evolution

日期：2026-07-03

决策：

- 新增 `my_md/evolution` 专门记录问题、失败复盘、修复路线和设计决策。

原因：

- `test_docs` 更适合记录测试方案和测试日志。
- `interview` 更适合记录面试表达。
- 真实修复需要一个独立位置沉淀技术债、失败原因和路线图。

影响：

- 后续讨论优化、测试失败、真实 bug 时，优先更新 `evolution`。
- 涉及具体测试步骤时，再同步更新 `test_docs`。

## DD-003 先修测试误判，再修核心行为

日期：2026-07-03

决策：

- 当前阶段先降低测试集误判，再针对真实 agent 行为做修复。

原因：

- 如果测试集本身有过硬断言，会把正确行为标成失败。
- 在噪声较多时直接改核心逻辑，容易修错方向。

影响：

- 优先处理 C/D 组 group-level 工具断言、中文同义表达、judge 依赖。
- 核心行为修复聚焦在记忆写入边界、no-tool 硬约束和成本控制。

## DD-004 TaskPlan 计划创建采用按上下文需求授权的召回能力

日期：2026-07-14

状态：accepted / implemented / live-verified。

决策：

- 纯 TaskPlan 创建默认不调用长期记忆或 session 历史检索。
- 不全局禁止 memory；当用户明确要求结合偏好、记忆、上次方案或之前讨论时，当前 turn 临时授权对应召回能力。
- 策略表达采用 `TaskPlan action + context requirement + capability scope`，不以持续增加具体工具名 blocklist 作为长期方案。

原因：

- turn `382` 证明 spawn/RAG/local 边界已经生效，但通用 memory/message retrieval 仍会造成额外两轮决策成本。
- 用户输入已经足够时，额外召回不会提升计划正确性；但“结合我的偏好”确实需要长期记忆，“按照上次方案”确实需要当前 session 历史。
- 全禁 memory 会损失合理能力；完全交给模型自由调用又无法满足成本和确定性要求。

能力模型：

```text
TaskPlanIntent
├── action: create | inspect | update | background_job
└── context_requirement: none | long_term_memory | session_history

CapabilityScope
├── task_state_read
├── task_state_write
├── memory_retrieval
└── session_history
```

约束：

- `context_requirement=none` 时，只允许任务状态能力和必要元工具。
- 允许召回时最多一次，不能形成 memory -> messages -> fetch -> memory 的扩展链。
- TaskPlan 工具成功后继续由 completion policy 进入 final-only。
- 所有授权保持 turn-local，不写入 LRU 或跨 turn discovery 状态。

影响：

- ToolAccessGateway 后续需要支持能力级 scope 到具体注册工具的映射。
- TaskPlan intent inference 需要新增显式偏好/历史信号和负向测试。
- 该模式可复用于 RAG、源码调查、后台 job 等其他工作流的上下文授权。

实施补记：

- 实际 capability vocabulary 为 `task_plan.create/inspect/update`、`memory.recall`、`history.search`。
- typed contract 是运行时授权源；`policy_metadata` 只用于 JSON-safe trace，不能反序列化回授权状态。
- 一次性预算由 `TaskPlanContextBudgetPolicy` 在 access hard block 之后执行；授权外调用先由网关 block，授权内重复调用由预算 soft-stop。
- `TaskPlanAccessPolicy` 在一次召回后只退休 schema/tool search visibility，不修改 execution allow scope；重复硬调用仍由预算返回稳定 reason。
- action-aware completion 同时要求 provider capability、`execution_status=success`、`result_ok=True` 和合法成功 payload。
- TaskPlan turn state 不进入 LRU/ToolDiscoveryState，也未增加 AgentLoop 主循环分支。
- 2026-07-15 主服务 turn `389-392` 复测 pure create/inspect/update/background observe 均为 2 轮且无 error，证明该决策在非隔离主服务上继续成立。
- 下一阶段的任务恢复和 execution attempt 不改变本决策：上下文 capability contract 继续只负责当前 turn 授权，长期执行状态必须由 TaskPlan 持久化边界管理。

## DD-005 TaskPlan 执行采用持久化 attempt 与只读自动执行

日期：2026-07-15

状态：accepted / implemented / live-verified。

决策：

- TaskPlan 步骤执行使用独立持久化 attempt/event，不把执行状态塞进 AgentLoop、LRU 或 ToolDiscoveryState。
- transport request ID 是 replay identity；同 ID 返回原 attempt，不使用文本 hash 去重，新 ID 同文本是独立操作。
- stale running outcome unknown 只转 blocked/pending，不自动 retry；恢复后必须显式 retry 才创建 attempt number + 1。
- 第一版只自动执行 registry exact `read-only`；write/external/unknown/shell 进入 waiting authorization，destructive 保持 core deny。
- success 必须同时有真实 read-only `counts_as_work=true` event 和显式 finish；tool search/control/synthetic result 不算工作证据。

原因：

- SQLite 可以保证内部状态原子性，但不能对进程外副作用承诺 exactly-once；崩溃后自动重放可能重复产生不可逆效果。
- request identity、attempt state 和 event ledger 能把“模型想做什么”与“runtime 实际执行了什么”分开审计。
- side-effect defer 让后续权限模型有明确接入点，又不会在批准/回滚尚未实现时提前开放写入。

验证：

- 同 raw request replay 只有一个 Step 1 attempt 和一组 work events；new-ID same-text 创建独立 Step 2 attempt。
- controlled restart 得到 `runtime_restarted_outcome_unknown`，普通 continue 无新 row，显式 retry 只有 attempt 2。
- side-effect target 未变化，write/edit/shell event 为 0，abort 后 history 保留。
- 最终复审 Full pytest baseline `1844 passed, 3 warnings in 48.12s`；finalizer injected integration `10 passed`。
- 显式 retry 不能先通过 TaskPlanService 单独提交 failed -> pending；Store 必须在同一 `BEGIN IMMEDIATE` 中校验 exact latest failed/recovery-blocked attempt、重置 step、创建 attempt 和 claim event，普通 continue 只得到 terminal/active conflict。
- 普通 continue 必须在最低序号 recovery-blocked pending step 处停止；retry reset 必须清除旧 step 结果字段；retryable blocked reason 使用 Service/Store 共享判定并在事务内复核。
- retry 与 reconcile 必须调用同一完整 reset helper；helper 只对 pending/in_progress/failed CAS 生效，绝不能覆盖 completed/skipped durable step。

影响与限制：

- LA-002 第一版可以声明 recoverable controlled read-only execution，不能声明 side-effect execution。
- P2 前需要填充 defer attempt 的 structured `requested_*` columns，并定义 approve/deny/expiry/audit；P3 前不开放真实文件写入。
