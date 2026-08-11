# MiniRoute 分层路由设计

## 目标

MiniRoute 只负责在主 Agent 执行前提供粗粒度路由建议：

```text
用户请求
  -> 意图与操作判断
  -> 记忆、工具范围和风险判断
  -> 输出五字段路由结果
```

它不负责具体工具选择、工具参数、任务拆分和工具执行。

## 两阶段内部结果

第一阶段：

```json
{
  "intent": "task_plan",
  "operation": "plan",
  "request_mode": "compound"
}
```

第二阶段：

```json
{
  "need_memory": true,
  "tool_scope": ["memory_tools", "task_tools"],
  "risk_level": "write"
}
```

对外仍输出原有五字段：

```json
{
  "intent": "task_plan",
  "need_memory": true,
  "need_tools": true,
  "tool_scope": ["memory_tools", "task_tools"],
  "risk_level": "write"
}
```

## 工具范围

`tool_scope` 是能力域集合，不是具体工具名称：

```text
memory_tools
task_tools
content_tools
file_read_tools
shell_tools
unknown_tools
```

一个请求需要多个能力时，输出多个范围。任务规划器负责把请求拆成步骤，并为每个步骤重新进行治理。

## 未知工具

当请求明确需要工具，但无法匹配当前能力域时，使用：

```json
{"tool_scope": ["unknown_tools"]}
```

MiniRoute 不负责确认运行时工具是否存在。MnemoAgent 的工具注册表负责校验：

```text
模型输出已知工具域
  -> 注册表中不存在
  -> 改写为 unknown_tools
  -> 不自动执行
```

未知工具不能自动猜测为 `shell_tools`。

## 运行边界

```text
MiniRoute：提出路由建议
工具注册表：确认能力是否存在
任务规划器：拆分复合任务
工具治理器：逐步授权和拦截
工具执行器：调用具体工具
```

MiniRoute 服务不可用、输出非法或与安全规则冲突时，回退到原有路由和治理链路。
