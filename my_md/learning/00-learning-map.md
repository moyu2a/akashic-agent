# 00 Learning Map

## 项目一句话定位

`akashic-agent` 是一个事件驱动的 Agent Runtime，支持被动对话、主动推送、长期记忆、工具调用、插件扩展、多渠道接入和 Dashboard 观测。

## 学习目标

- 能把项目在本地跑起来。
- 能讲清楚启动流程和核心运行时对象。
- 能从设计层面讲清楚一条用户消息从 channel 到最终回复的完整链路。
- 能理解 memory、tool、plugin、proactive 的职责边界。
- 能把该项目包装成 Agent 应用/Agent Infra 求职项目。

## 学习策略

当前学习方式从“逐行源码阅读”切换为“模块设计学习”。

原因：

- 这个项目更适合作为 Agent Runtime / Agent Infra 案例来理解。
- 如果项目由 AI 辅助生成和持续迭代，逐行阅读所有代码性价比较低。
- 求职和工程理解更看重模块职责、数据流、接口边界和设计取舍。
- 仍需要能定位关键入口和核心数据结构，但不需要背每一步代码实现。

后续每个模块按同一模板学习：

```text
模块解决什么问题？
核心对象有哪些？
输入是什么？
输出是什么？
谁调用它？
它依赖谁？
关键数据流是什么？
为什么这样设计？
可能的问题和改进点是什么？
面试时怎么讲？
```

## 模块设计学习顺序

1. 总体架构: runtime 由哪些部分组成，数据如何流动。
2. 被动对话框架: 用户消息如何被处理成回复。
3. 工具系统: 工具如何注册、搜索、执行、治理。
4. 记忆系统: 长期记忆、语义检索、consolidation 如何协作。
5. 插件系统: 插件如何扩展生命周期和工具能力。
6. 主动推送系统: proactive 如何判断是否主动联系用户。
7. Channel 和通信层: CLI/Telegram/QQ/IPC 如何接入。
8. Dashboard 和可观测性: 如何观察 session、消息、proactive、插件。
9. 面试包装: 如何把项目讲成 Agent Runtime 项目。

## 源码定位参考

1. 运行和配置: `main.py`, `config.example.toml`, `agent/config.py`
2. 启动装配: `bootstrap/app.py`, `bootstrap/tools.py`
3. 被动对话: `agent/looping/core.py`, `agent/core/runner.py`, `agent/core/passive_turn.py`
4. 工具系统: `agent/tools/registry.py`, `bootstrap/toolsets/*`
5. 记忆系统: `bootstrap/memory.py`, `core/memory/runtime.py`, `plugins/default_memory/*`
6. 插件系统: `agent/plugins/manager.py`, `plugins/*/plugin.py`
7. 主动推送: `bootstrap/proactive.py`, `proactive_v2/loop.py`, `proactive_v2/agent_tick_factory.py`
8. Dashboard 和可观测性: `bootstrap/dashboard_api.py`, `frontend/dashboard/src/main.tsx`

## 当前进度

- [x] 初步了解项目定位。
- [x] 初步梳理核心目录结构。
- [x] 初步理解启动链路。
- [x] 跑通本地环境。
- [x] 跑通 CLI 对话。
- [ ] 跑通 Dashboard。
- [x] 从设计层面讲清楚完整被动对话链路。
- [x] 从设计层面理解工具系统。
- [x] 从设计层面理解记忆系统。
- [x] 从设计层面理解插件系统。
- [x] 从设计层面理解主动推送系统。
- [x] 从设计层面理解 Channel 和通信层。
- [x] 从设计层面理解 Dashboard 和可观测性。
- [ ] 跑通记忆写入和检索。
- [ ] 跑通主动推送。
- [ ] 准备面试表达稿。

## 已完成验证

- 本地环境已成功运行。
- 已能通过 CLI 与 agent 正常问答。

## 下一步

1. 进入求职项目包装阶段。
2. 整理 30 秒介绍、3 分钟技术介绍、项目亮点、难点、改进点和常见面试问答。
3. 建议补一个可复现 demo：CLI 对话 + 工具调用/记忆检索 + Dashboard 截图或主动推送 trace。

## 已学习源码点

- `main.py` 是项目命令入口。
- `python main.py` 默认启动完整 agent 服务，进入 `serve()`。
- `python main.py cli` 不启动完整 agent，只调用 `connect_cli()` 连接已有服务。
- `python main.py setup` 进入配置向导。
- `python main.py init` 执行非交互初始化。
- `python main.py dashboard` 只启动 Dashboard 管理界面。
- `--config`、`--workspace`、`--host`、`--port` 是通用覆盖参数。
- `connect_cli()` 会读取 `config.toml` 中的 `channels.socket`，优先启动 Textual TUI，失败时回退纯文本 CLI。
- CLI 客户端把用户输入包装成一行 JSON：`{"content": "..."}\n`，通过 Unix socket 或 TCP 发给服务端。
- 默认服务模式会在 `AppRuntime.start()` 中调用 `start_channels()`，创建 `IPCServerChannel`。
- `IPCServerChannel` 负责监听 CLI socket，收到 JSON 后转换成 `InboundMessage` 并调用 `MessageBus.publish_inbound()`。
- `MessageBus` 内部有 `_inbound` 和 `_outbound` 两个队列，分别表示 channel 到 agent、agent 到 channel。
- `AgentLoop.run()` 常驻消费 `MessageBus.consume_inbound()`，拿到消息后创建 task 执行 `_process()`。
- `AgentLoop._process()` 会处理 interrupt resume、发布 `TurnStarted`、标记 busy，然后交给 `CoreRunner.process()`。
- `CoreRunner` 根据入站项类型分流，普通 `InboundMessage` 进入 `AgentCore.process()`。
- `AgentCore` 本身很薄，只持有 `PassiveTurnPipeline`，`process()` 直接委托给 pipeline。
- `PassiveTurnPipeline.run()` 会创建 `TurnState`，然后依次执行 `BeforeTurn`、`BeforeReasoning`、`Reasoner.run_turn()`、`AfterReasoning`、`AfterTurn`。
- `BeforeTurn` 内置模块链会获取 session、准备上下文 bundle、构造 `BeforeTurnCtx`、通过 `EventBus.emit()` 交给插件/观察者、收集插件导出的 extra hints 或 abort reply。
- 从设计层面理解了被动对话链路：`Channel -> MessageBus -> AgentLoop -> CoreRunner -> AgentCore -> PassiveTurnPipeline -> Reasoner/Tool Loop -> Outbound`。
- 被动链路的核心设计价值是解耦渠道、统一消息格式、管理 turn 生命周期、拆分一轮对话阶段，并为工具、记忆、插件和后处理提供明确挂载点。
- 从设计层面理解了工具系统：外部能力被标准化为 `Tool`，统一注册到 `ToolRegistry`；`always_on`/deferred/tool_search 控制 prompt 压力；`ToolExecutor` 和 `ToolHook` 提供执行治理；toolset、plugin、MCP 提供扩展来源。
- 从设计层面理解了记忆系统：短期 session history、可读可控的 markdown memory、可语义召回的 vector memory 分层；对话前 retrieval 注入 prompt，对话后 consolidation 提取长期事实，先进入 `PENDING.md`/`HISTORY.md`，再由 memory optimizer 归档，兼顾记忆质量和 prompt cache 稳定性。
- 从设计层面理解了插件系统：`PluginManager` 负责发现、加载、实例化、注入 `PluginContext`、绑定工具/hook/phase module/event handler；插件可以在不改主链路的情况下扩展工具、工具治理、生命周期、事件观察和 Dashboard。
- 从设计层面理解了主动推送系统：`ProactiveLoop` 定期 tick，`Sensor` 收集内容源、session、presence 和 memory，上层 gate 用 busy/cooldown/dedupe/presence 控制打扰，`AgentTick` 判断 reply/skip/drift，最后由 `TurnOrchestrator` 和 `MessagePushTool` 统一发送和记录。
- 从设计层面理解了 Channel 和通信层：CLI/IPC、Telegram、QQ/QQBot 等外部协议由 channel adapter 转换为统一 `InboundMessage`；回复统一成 `OutboundMessage` 走 `MessageBus` outbound；`MessageBus` 负责用户通信路径，`EventBus` 负责生命周期事件和插件观察。
- 从设计层面理解了 Dashboard 和可观测性：Dashboard 不是普通 CRUD 后台，而是 Agent observability console，用于查看 session、message、memory、proactive tick logs、plugin panels 和 manual operations，解释 agent 看过什么、做过什么、为什么推送/跳过，以及记忆和插件状态。

## 核心模块地图

```text
main.py
  -> bootstrap.app.AppRuntime
      -> bootstrap.tools.build_core_runtime
          -> MessageBus / EventBus
          -> LLMProvider
          -> ToolRegistry
          -> MemoryRuntime
          -> AgentLoop
          -> PluginManager
      -> channels
      -> dashboard
      -> proactive loop
```

## 问题池

- `MessageBus` 和 `EventBus` 的职责边界是什么？
- `PassiveTurnPipeline` 每个 Phase 具体做了什么？
- `tool_search` 是如何减少 prompt 中工具 schema 数量的？
- markdown memory 和语义 memory engine 是如何协作的？
- proactive loop 如何判断“该不该主动打扰用户”？
- 插件能在哪些生命周期点介入？
- 如果只按模块设计学习，哪些源码入口必须保留基本熟悉？
- 这个项目作为 AI 辅助编码项目，哪些地方需要重点审查设计一致性？

## 后续更新提示词

```text
请更新 my_md/learning/00-learning-map.md：根据本次学习内容调整学习进度，补充新的问题池、已掌握模块和下一步学习计划。
```
