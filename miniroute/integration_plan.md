# MiniRoute 接入 MnemoAgent 计划

## 接入原则

MiniRoute 第一阶段只做 Shadow 预测，不改变 MnemoAgent 真实运行结果。

V4 起，小模型输出只作为场景建议，不能绕过现有工具治理、审批、路径检查和风险裁决。

## 接入位置

建议放在用户消息进入后、上下文准备和工具开放之前。

概念流程：

```text
用户消息
  -> MiniRoute V4 场景识别
  -> 记录 shadow 决策
  -> MnemoAgent 原有流程继续运行
  -> 对比原系统上下文、工具、token 和时延
```

## Shadow 记录字段

每轮建议记录：

- `session_key`
- `message_id`
- `user_message`
- `has_active_task`
- `miniroute_scene`
- `miniroute_operation`
- `miniroute_request_mode`
- `original_context_profile`
- `actual_memory_retrieval_used`
- `actual_tools_used`
- `actual_tool_count`
- `prompt_tokens`
- `latency_ms`
- `fallback_reason`

## 第一阶段禁止行为

MiniRoute 不允许直接控制：

- shell 工具开放。
- 写文件工具开放。
- 删除、覆盖、安装等高风险操作。
- 审批通过或拒绝。
- 外部副作用工具。

## 模块边界

V4 MiniRoute 只输出粗粒度场景建议：

```text
scene
operation
request_mode
```

工具注册表、任务规划器和工具执行器属于 MnemoAgent，不属于 MiniRoute 模型：

```text
MiniRoute V4
  -> scene 映射 context_profile
  -> MnemoAgent 原流程组装上下文
  -> 工具注册表校验能力是否可用
  -> 任务规划器拆分复合请求
  -> 工具治理器逐步审批
  -> 工具执行器调用具体工具
```

V4 不再输出 `tool_scope`。当请求需要具体工具时，由 MnemoAgent 原有工具注册表、任务规划器和工具治理器处理。

## 可选低风险启用项

Shadow 验证稳定后，可以优先尝试：

- 是否需要长期记忆检索。
- 是否进入工作模式。
- 是否启用任务状态摘要。
- 是否使用短上下文或完整上下文。

## 失败回退

以下情况必须回退到原系统逻辑：

- MiniRoute 服务不可用。
- MiniRoute 超时。
- 输出不是合法 JSON。
- 输出包含未知标签。
- 输出 `scene=unknown`。
- 输出和原系统强规则冲突。
