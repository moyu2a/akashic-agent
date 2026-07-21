# Tool Invocation Policy Engine P1 Status

日期：2026-07-21

## 目标

`Tool Safety Gateway P1` 的第一步是先建立一次工具调用的统一裁决接口，而不是直接改变真实工具执行链路。

本阶段只实现：

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
- `shell`、`write`、`external-side-effect`、`unknown`：`defer`
- `defer` metadata 写入 `durable_transition=waiting_authorization`
- 未注册和 `destructive` 优先于 work-phase 规则，仍为 `deny`

## 边界说明

本阶段没有接入：

- `DefaultReasoner`
- `ToolExecutor`
- `ToolRegistry.execute()`
- ResourcePolicy
- Docker/chroot/seccomp sandbox
- approval workflow
- ToolAuditLedger 持久化

因此 P1.1 不改变当前主 Agent 的真实工具执行行为。它只是后续调用级安全边界的稳定接口和基础规则。

## 验证结果

目标测试：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_tool_invocation_policy.py -q -p no:cacheprovider
```

结果：

```text
13 passed
```

兼容测试：

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_tool_invocation_policy.py tests/test_tool_boundary_manager.py tests/test_task_execution_access.py -q -p no:cacheprovider
```

结果：

```text
32 passed
```

格式检查：

```bash
git diff --check
```

结果：通过，无输出。

## 后续步骤

下一步不应直接上 sandbox，而是先做 P1.2：

1. 设计 `ToolInvocationPolicyEngine` 与真实执行链路的接入点。
2. 明确 `defer` 如何映射到现有 TaskExecution `waiting_authorization` 语义。
3. 在接入前补 `invoker_reached=false` 的集成测试。
4. 保持普通 passive turn 行为不变，直到 ResourcePolicy 和 approval 策略准备好。
