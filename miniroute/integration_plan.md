# MiniRoute 接入 MnemoAgent 计划

## 接入原则

MiniRoute 第一阶段只做 Shadow 预测，不改变 MnemoAgent 真实运行结果。

小模型输出只能作为路由建议，不能绕过现有工具治理、审批、路径检查和风险裁决。

## 接入位置

建议放在用户消息进入后、上下文准备和工具开放之前。

概念流程：

```text
用户消息
  -> MiniRoute 路由预测
  -> 记录 shadow 决策
  -> MnemoAgent 原有流程继续运行
  -> 对比原系统决策和 MiniRoute 决策
```

## Shadow 记录字段

每轮建议记录：

- `session_key`
- `message_id`
- `user_message`
- `miniroute_intent`
- `miniroute_need_memory`
- `miniroute_need_tools`
- `miniroute_tool_scope`
- `miniroute_risk_level`
- `original_route_decision`
- `actual_tools_used`
- `actual_tool_count`
- `high_risk_detected_by_original`
- `high_risk_detected_by_miniroute`
- `scope_overopen`
- `scope_underopen`

## 第一阶段禁止行为

MiniRoute 不允许直接控制：

- shell 工具开放。
- 写文件工具开放。
- 删除、覆盖、安装等高风险操作。
- 审批通过或拒绝。
- 外部副作用工具。

## 可选低风险启用项

Shadow 验证稳定后，可以优先尝试：

- 是否需要长期记忆检索。
- 是否进入工作模式。
- 是否开放只读记忆工具。
- 是否开放运行轨迹查询工具。

## 失败回退

以下情况必须回退到原系统逻辑：

- MiniRoute 服务不可用。
- MiniRoute 超时。
- 输出不是合法 JSON。
- 输出包含未知标签。
- 输出建议开放高风险工具。
- 输出和原工具治理强规则冲突。
