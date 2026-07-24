# Tool Invocation Policy Engine P1 Status

日期：2026-07-21

## 目标

`Tool Safety Gateway P1` 的第一步是先建立一次工具调用的统一裁决接口，而不是直接改变真实工具执行链路。

P1.1 只实现：

- `ToolInvocationContext`
- `ToolInvocationDecision`
- `ToolInvocationPolicyEngine`
- 最小 risk / TaskExecution work-phase 裁决规则
- 聚焦单元测试和现有工具边界兼容测试

## 已实现内容

新增代码：

- `agent/policies/tool_invocation_policy.py`
- `tests/test_tool_invocation_policy.py`

当前有效 action：

- `allow`
- `deny`
- `defer`

未提前加入 `sandbox` 作为有效 action。sandbox、ResourcePolicy、approval workflow 和 ToolAuditLedger 都是后续阶段。

## 当前裁决规则

通用规则：

- 未注册工具：`deny`
- `destructive`：`deny`
- `read-only`：`allow`
- 普通非 TaskExecution turn 下，已注册且非 destructive 的 `write`、`external-side-effect`、`unknown`：暂时 `allow`

TaskExecution `work` 阶段：

- 非 `shell` 的 `read-only`：`allow`
- TaskExecution 控制能力（`task_execution.finish/defer/abort/inspect/begin`）：`allow`
- `shell`、`write`、`external-side-effect`、`unknown`：`defer`
- `defer` metadata 写入 `durable_transition=waiting_authorization`
- 未注册和 `destructive` 优先于 work-phase 规则，仍为 `deny`

## P1.2 接入结果

日期：2026-07-22

P1.2 将 `ToolInvocationPolicyEngine` 接入真实工具 invoker 前置路径：

- `ToolExecutor` 在 pre-hook 之后、真实 invoker 之前执行调用级 policy。
- pre-hook 仍保留插件改参/拒绝能力；policy 评估的是 pre-hook 后的最终参数。
- `allow` 才会进入真实 invoker。
- executor 层 `deny/defer` 返回 JSON 字符串形式的结构化非执行结果，`invoker_reached=false`。
- `ToolRegistry.get_invocation_metadata()` 为单次调用提供 registered、risk、capabilities 快照。
- `DefaultReasoner.run_turn()` 在构造 `ToolExecutionRequest` 时传入 registry risk/capabilities、当前用户文本和 TaskExecution phase。
- `TaskExecutionRiskPolicy` 复用 `ToolInvocationPolicyEngine` 做 work-phase 风险分类，但继续保留 `task_execution_authorization_required` 等原有 reason，确保 `TaskExecutionRuntimeCoordinator` 仍负责持久化 `waiting_authorization`。
- TaskExecution 控制工具（如 `finish_task_step_execution`）通过 capability allow，不会被 executor gate 自阻断。
- 独立审阅后补充修订：`TaskExecutionRiskPolicy.evaluate()` 现在也接收 `registry_capabilities` 并传给 invocation policy；即使未来有直接调用方绕过 `TurnToolBoundaryManager`，TaskExecution 控制能力也不会因 registry risk 为 `write` 被误判。

边界仍然明确：

- 当前不是 Shell AST 解析。
- 当前不是 Docker/chroot/seccomp sandbox。
- 当前只接入文件路径参数级 `ResourcePolicy`；shell/code、URL/network 和 protected context 仍未接入。
- 当前不是完整 `ToolAuditLedger`。
- executor 的 `defer` 只是“未执行真实 invoker”的结构化结果；TaskExecution 的 durable 授权等待仍由既有 boundary/coordinator 路径负责。

## 边界说明

P1.1 阶段没有接入：

- `DefaultReasoner`
- `ToolExecutor`
- `ToolRegistry.execute()`
- ResourcePolicy
- Docker/chroot/seccomp sandbox
- approval workflow
- ToolAuditLedger 持久化

P1.2 已接入 `ToolExecutor` 和 passive reasoner 的真实执行路径。P1.3a/P1.3b 进一步接入文件路径参数级资源判断。P1.3 completion 已补齐 subagent per-tool roots、protected runtime argument、shell command 参数 gate 和 URL/network 参数 gate，但仍没有引入 sandbox、approval UI 或完整审计账本。

## P1.3a/P1.3b ResourcePolicy 接入结果

日期：2026-07-22

本阶段完成参数级文件资源策略：

- 新增 `ResourcePolicyContext`、`ResourcePolicyDecision`、`ResourcePolicyEngine`。
- `ToolInvocationPolicyEngine` 在工具级 unregistered/destructive deny 之后、TaskExecution work-phase defer 之前调用 `ResourcePolicyEngine`。
- `ToolExecutionRequest.resource_roots` 通过 `ToolExecutor` 进入 `ToolInvocationContext.metadata`。
- `DefaultReasoner.run_turn()` 为真实 passive turn 传入 `ContextBuilder.workspace` 解析出的 workspace root；仅在缺少 context 时 fallback 到 process cwd。
- `read_file/list_dir/write_file/edit_file` 的 `path` 参数会进行 workspace scope 判断。
- workspace 内相对路径、绝对路径、缺失文件和缺失写入父目录允许继续交给真实工具处理。
- workspace 外路径、受保护系统路径、symlink 逃逸和畸形路径会在 invoker 前被拒绝，返回结构化 JSON，`invoker_reached=false`。

边界：

- 仍不是 shell AST。
- 仍不是 URL/network 策略。
- 仍不是 Docker/chroot/seccomp sandbox。
- 仍不是 approval workflow。
- `resource_roots` 为空时当前兼容 allow；非 passive / subagent / 其他直接 `ToolExecutor` 调用方需要后续继续传 root，才能声称全局硬保护。

## P1.3 Completion 接入结果

日期：2026-07-22

本阶段完成 P1.3 收尾：

- `SubAgent` 支持默认 `resource_roots` 和 `resource_roots_by_tool`，subagent tool calls 在进入真实 invoker 前带上 per-tool roots。
- subagent profiles 按工具类别传 root：`read_file/list_dir` 使用 workspace root，`write_file/edit_file` 使用 task-dir root。
- `ResourcePolicyEngine` 会在 file/shell/URL 检查前拒绝伪造 runtime protected arguments，包括 `_session_key`、TaskExecution protected keys、`_request_id`、`_attempt_id`、`_transport_request_id`。
- `ResourcePolicyEngine` 对 `shell.command` 增加保守参数 gate：拦截高置信 destructive command、compound destructive command、`sudo/xargs` wrapper 场景，以及有限的 inline interpreter 高危 marker。
- shell gate 使用 quote-aware + punctuation-aware tokenization，覆盖 `a|xargs rm`、`a;rm` 这类无空格 operator，同时不把 quoted `;` 或 quoted `$()` 文本当作 top-level shell operator。
- `ResourcePolicyEngine` 对 `web_fetch.url` 增加 URL 参数 gate：拒绝 unsupported scheme、localhost、`.localhost`、`.local`、trailing-dot localhost、private/loopback/link-local/reserved/unspecified IP 和 no-host URL。
- `ToolInvocationPolicyEngine` composition 测试覆盖 protected argument deny、shell allow 后 TaskExecution work-phase 仍 defer、URL allow metadata 保真。

边界：

- Shell command policy 不是完整 shell AST，也不是 sandbox；它只是 invoker 前的保守参数 gate。
- URL policy 不做 DNS 解析，不检查 redirect 后目标；`web_fetch` 自身 runtime SSRF 校验仍是第二道保护。
- `send_webhook` URL 参数映射仅作为 future-compatible policy map；当前不声明该工具已在 runtime 注册。
- `message_push.file/image` 这类 mixed local path / URL 参数不在 P1.3 completion 范围内，需要后续 dedicated mixed-resource policy。
- Docker/chroot/seccomp、approval workflow、ToolAuditLedger 持久化仍属于 P2/P3/P4。

## P2 Approval Policy 接入结果

日期：2026-07-22

本阶段在 P1 hard gate 之上完成默认风险策略、结构化授权/延迟协议和最小审计 trace：

- 新增 `agent/policies/tool_risk_strategy.py`，把 passive turn 中的工具风险收束为统一矩阵：`read-only` 自动允许，`write`、`external-side-effect`、`unknown` 默认 `defer`，`destructive` 默认 `deny`。
- `shell` 工具和带 `shell.execute` / `process.execute` capability 的工具，即使 registry risk 被标成 `read-only`，也会默认 `defer`，等待显式授权，不再依赖 shell safety pre-hook 的 allow 结论直接执行。
- TaskExecution work phase 仍由既有 durable authorization path 负责；executor 层 P2 defer 是非执行 fallback，不替代 `waiting_authorization` 的持久化所有权。
- TaskPlan 控制面能力（`task_plan.create/update/inspect`）作为 session 内部控制工具被显式允许，避免 P2 unknown/write 默认 defer 误伤计划创建和更新。
- 新增 `agent/policies/tool_approval.py`，`defer` 结果返回结构化 `approval_request`，包含 tool、risk、reason、approval scope、参数 hash 和脱敏参数摘要。
- 新增 `agent/policies/tool_audit.py`，每次进入 invocation policy 后的结果都会生成最小审计 metadata：request/session/channel/chat/tool/source/risk/action/reason/args hash/invoker reached/succeeded。
- `ToolExecutionResult.audit_trace` 进入 passive turn tool trace；observe slim trace 只保留固定白名单审计字段，不保存 `args_summary` 这类可能含敏感内容的参数摘要。
- `DefaultReasoner` 已确保 `defer/deny` 这类没有触达真实 invoker 的工具调用不会被计入真实执行工具、不会污染 tool LRU 解锁路径。

重要边界：

- P2 仍不是 approval UI，也不是用户批准后的继续执行协议；它只产生结构化授权请求和不执行真实 invoker 的安全结果。
- P2 仍不是完整 `ToolAuditLedger` 数据库；当前审计只随 turn trace/observe 传播，满足“为什么执行/为什么没执行”的最小回放需要。
- P2 仍不是 Docker/chroot/seccomp sandbox，也不是 shell AST；shell 安全目前是 `ResourcePolicy` 参数 gate + shell safety pre-hook + P2 默认 defer 的组合防线。
- shell safety 插件测试已调整语义：插件层“允许”只表示 pre-hook 未拒绝，最终是否真实执行由 P2 invocation policy 决定。

## P3 Approval Workflow 接入结果

日期：2026-07-24

本阶段把 P2 的结构化 `defer + approval_request` 推进为 durable、trusted、single-use 的审批闭环，同时保留 P1/P2 的硬边界：

- 新增 workspace-scoped SQLite approval store：持久化 pending/approved/denied/expired/consumed/executed/execution_failed 状态。
- 审批绑定 tuple 为 `approval_request_id + session_key + request_id + tool_name + approval_scope + args_hash`，approve/deny/consume/finalize 均按完整 tuple 校验。
- `ToolApprovalRuntime` 是 executor、status command、TaskExecution bridge 的共享 facade，`DefaultReasoner` 每 turn 按 workspace 注入同一 approval DB。
- `ToolExecutionRequest.trusted_approval_context` 只能由 runtime code 构造；模型在工具参数里伪造 `approval_request_id` 不会触发执行。
- `ToolExecutor` 在 P2 `defer` 后创建或复用 pending request；用户审批后，只有 trusted context 且参数 hash 完全一致时才会原子 consume 并进入真实 invoker。
- approval 是 single-use：第一次 resume consume 后才能执行，重复 resume、变参、denied、expired、mismatch、not_found 均不触达真实 invoker。
- P1 deny 仍优先：即使存在 approved request，workspace escape、protected argument、destructive shell 等 P1/P1.3 deny 仍在 consume/execution 前阻断。
- `plugins/status_commands` 新增 trusted command surface：`/approvals`、`/approve_tool <id>`、`/deny_tool <id> [reason]`。命令只接受 approval id，绑定字段全部来自持久 record，不从命令文本读取。
- TaskExecution `waiting_authorization` 已持久化 bounded metadata：approval id、expires_at、approval_scope、args_hash、args_summary、policy_reason；但 P3 不开放 TaskExecution write/edit/shell side-effect resume。
- 新增 bounded approval lifecycle audit：requested、approved、denied、expired、consumed、executed、execution_failed 事件进入 executor trace、status command metadata 和 observe slim trace。
- observe 仅保留 allowlist 字段：approval id、request/session/tool/source/risk/scope/policy reason/status/args hash/timestamps；不保存 raw args、`args_summary`、command、content、code、body、secret、cookie、token。

明确边界：

- P3 不是 sandbox，不提供 Docker/chroot/seccomp、non-root user、read-only rootfs、resource limit。
- P3 不提供 filesystem snapshot/diff/rollback，也不承诺批准后自动恢复 TaskExecution 副作用执行。
- P3 不是完整企业级 `ToolAuditLedger`；当前是随 turn trace/observe 传播的 bounded lifecycle metadata。可查询持久审计账本、retention 和 dashboard/admin 审计检索属于 P4/P5。

## 验证结果

P1.1 目标测试：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_tool_invocation_policy.py -q -p no:cacheprovider
```

历史结果：

```text
13 passed
```

P1.1 兼容测试：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_tool_invocation_policy.py tests/test_tool_boundary_manager.py tests/test_task_execution_access.py -q -p no:cacheprovider
```

历史结果：

```text
32 passed
```

格式检查：

```bash
git diff --check
```

结果：通过，无输出。

P1.2 targeted 回归：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_tool_invocation_policy_gate.py tests/test_tool_invocation_policy.py tests/test_tool_executor.py tests/test_tool_boundary_manager.py tests/test_task_execution_access.py tests/test_shell_safety_plugin.py tests/test_tool_access_gateway.py tests/test_task_plan_gateway.py tests/test_task_plan_contract.py tests/test_tool_access_gateway_reasoner.py::test_reasoner_policy_gate_blocks_destructive_registered_tool_as_json tests/test_task_execution_reasoner.py::test_read_only_execution_is_begin_work_finish_final tests/test_task_execution_reasoner.py::test_write_proposal_defers_without_executor -q -p no:cacheprovider
```

结果：

```text
143 passed in 0.75s
```

补充校验：

```bash
python3 -m compileall agent/tool_hooks agent/policies agent/tools/registry.py agent/core/passive_turn.py tests/test_tool_invocation_policy_gate.py tests/test_tool_invocation_policy.py tests/test_tool_boundary_manager.py tests/test_tool_access_gateway_reasoner.py
```

结果：通过，退出码 0。

独立审阅结果：未发现阻断问题。剩余风险是非 `DefaultReasoner` 调用方如果直接使用 `ToolExecutor`，仍必须显式传入 registered/risk/capabilities metadata；否则只能得到兼容默认值下的策略判断。

P1.3a/P1.3b focused 回归：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_resource_policy.py tests/test_tool_invocation_resource_policy.py -q -p no:cacheprovider
```

结果：

```text
16 passed in 0.12s
```

P1.2 + P1.3 相关回归：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_tool_invocation_policy_gate.py tests/test_tool_invocation_resource_policy.py tests/test_resource_policy.py tests/test_tool_invocation_policy.py tests/test_tool_executor.py tests/test_tool_boundary_manager.py tests/test_task_execution_access.py tests/test_shell_safety_plugin.py tests/test_tool_access_gateway.py tests/test_task_plan_gateway.py tests/test_task_plan_contract.py tests/test_tool_access_gateway_reasoner.py::test_reasoner_policy_gate_blocks_destructive_registered_tool_as_json tests/test_tool_access_gateway_reasoner.py::test_reasoner_resource_policy_blocks_parent_escape_read_file tests/test_tool_access_gateway_reasoner.py::test_reasoner_resource_roots_come_from_context_workspace tests/test_task_execution_reasoner.py::test_read_only_execution_is_begin_work_finish_final tests/test_task_execution_reasoner.py::test_write_proposal_defers_without_executor -q -p no:cacheprovider
```

结果：

```text
164 passed in 0.86s
```

P1.3 completion focused 回归：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_resource_policy.py tests/test_tool_invocation_resource_policy.py tests/test_subagent_resource_policy.py -q -p no:cacheprovider
```

结果：

```text
41 passed in 0.20s
```

P1.2/P1.3 completion 相关回归：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_resource_policy.py tests/test_tool_invocation_resource_policy.py tests/test_subagent_resource_policy.py tests/test_tool_invocation_policy_gate.py tests/test_tool_invocation_policy.py tests/test_tool_executor.py tests/test_tool_boundary_manager.py tests/test_task_execution_access.py tests/test_shell_safety_plugin.py tests/test_tool_access_gateway.py tests/test_task_plan_gateway.py tests/test_task_plan_contract.py tests/test_tool_access_gateway_reasoner.py::test_reasoner_policy_gate_blocks_destructive_registered_tool_as_json tests/test_tool_access_gateway_reasoner.py::test_reasoner_resource_policy_blocks_parent_escape_read_file tests/test_tool_access_gateway_reasoner.py::test_reasoner_resource_roots_come_from_context_workspace tests/test_task_execution_reasoner.py::test_read_only_execution_is_begin_work_finish_final tests/test_task_execution_reasoner.py::test_write_proposal_defers_without_executor tests/test_subagent_spawn_task_dir.py tests/test_tool_loop_guard.py -q -p no:cacheprovider
```

结果：

```text
221 passed in 1.66s
```

编译与 whitespace 检查：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python -m compileall agent/policies agent/tool_hooks agent/core/passive_turn.py agent/subagent.py agent/background/subagent_profiles.py tests/test_resource_policy.py tests/test_tool_invocation_resource_policy.py tests/test_subagent_resource_policy.py
git diff --check
```

结果：均通过，退出码 0；`git diff --check` 无输出。

P2 focused 回归：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_tool_risk_strategy.py tests/test_tool_approval.py tests/test_tool_audit.py tests/test_tool_invocation_policy.py tests/test_tool_invocation_policy_gate.py tests/test_tool_invocation_resource_policy.py tests/test_resource_policy.py tests/test_tool_executor.py tests/test_tool_boundary_manager.py tests/test_task_execution_access.py tests/test_task_execution_reasoner.py tests/test_shell_safety_plugin.py tests/test_tool_access_gateway.py tests/test_observe_writer.py -q -p no:cacheprovider
```

结果：

```text
192 passed in 4.83s
```

P2 audit focused 回归：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_tool_audit.py tests/test_tool_invocation_policy_gate.py tests/test_tool_executor.py tests/test_observe_writer.py -q -p no:cacheprovider
```

结果：

```text
30 passed in 0.38s
```

P1/P2 contract 回归：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_tool_governance_p1_p2_contract.py -q -p no:cacheprovider
```

结果：

```text
6 passed in 0.08s
```

该短测试集用于快速验证第一大步和第二大步的核心合同：

- P1：workspace escape、protected runtime argument、destructive shell wrapper 都必须在真实 invoker 前被拒绝。
- P2：read-only 资源通过后可执行；write 和 shell 默认 defer，返回 `approval_request`，并带最小 `audit_trace`。
- P2：敏感 `content` 只进入 hash/脱敏摘要，不暴露 preview。

P3 approval workflow focused 回归：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_tool_approval.py tests/test_tool_approval_store.py tests/test_tool_approval_runtime.py tests/test_tool_executor_approval_workflow.py tests/test_tool_approval_wiring.py tests/test_task_execution_approval_bridge.py tests/test_tool_audit.py tests/test_observe_writer.py tests/test_tool_governance_p1_p2_contract.py tests/test_tool_governance_p3_contract.py -q -p no:cacheprovider
```

结果：

```text
63 passed in 2.04s
```

P3 compatibility 回归：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_tool_invocation_policy.py tests/test_tool_invocation_policy_gate.py tests/test_tool_invocation_resource_policy.py tests/test_resource_policy.py tests/test_tool_executor.py tests/test_tool_boundary_manager.py tests/test_task_execution_access.py tests/test_task_execution_reasoner.py tests/test_task_execution_store.py tests/test_task_execution_contract.py tests/test_shell_safety_plugin.py tests/test_tool_access_gateway.py tests/test_observe_writer.py tests/test_lifecycle_phases.py -q -p no:cacheprovider
```

结果：

```text
260 passed in 6.52s
```

P3 compileall 与 whitespace 检查：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python -m compileall agent/policies agent/tool_hooks agent/core/passive_turn.py agent/task_plan plugins/status_commands plugins/observe tests/test_tool_approval_store.py tests/test_tool_approval_runtime.py tests/test_tool_executor_approval_workflow.py tests/test_tool_approval_wiring.py tests/test_task_execution_approval_bridge.py tests/test_tool_governance_p3_contract.py
git diff --check
```

结果：compileall 退出码 0；`git diff --check` 无输出。

## 后续步骤

P3 已完成 trusted approval workflow、single-use consume、status command approve/deny、TaskExecution bounded authorization metadata 和 approval lifecycle trace。下一步不应直接声称生产级安全，而是进入 P4/P5，把“批准后安全执行环境”和“可查询持久审计账本”补成闭环：

1. P4 设计 sandbox/diff/snapshot/rollback：Docker/Podman、non-root user、read-only rootfs、resource limits、filesystem snapshot/diff/rollback。
2. P4/P5 设计可查询持久 `ToolAuditLedger`：timestamp、actor、request id、policy decision、args hash、脱敏摘要、执行结果预览和 retention 策略。
3. 继续收敛 no-root 兼容 allow，只让明确无法提供 workspace 的直接调用方走兼容路径。
4. 评估 TaskExecution side-effect resume 的开放条件：只有 P4 具备 diff/snapshot/rollback 后，才允许 approved write/edit/shell 从 `waiting_authorization` 继续真实执行。
