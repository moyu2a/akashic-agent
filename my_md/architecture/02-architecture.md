# 02 Architecture

## 总体理解

`akashic-agent` 的核心是一个事件驱动的 Agent Runtime。它通过 bootstrap 层装配各种服务，再由两条主要运行链路完成工作：

- 被动链路：用户发消息后回复。
- 主动链路：系统定期感知内容源和用户状态，判断是否主动推送。

## 学习视角

后续不再逐行阅读所有源码，而是按模块设计理解项目。

需要掌握：

- 每个模块解决什么问题。
- 模块的输入、输出和核心对象。
- 模块之间如何调用。
- 为什么要这样拆分。
- 失败时应该定位到哪一层。
- 面试时如何解释设计取舍。

不需要掌握：

- 每个函数每一行代码的细节。
- 所有测试和兼容分支。
- 所有插件的内部实现。

但必须熟悉关键入口：

- `main.py`: 命令入口。
- `bootstrap/app.py`: 应用运行时装配。
- `bootstrap/tools.py`: core runtime 装配。
- `agent/looping/core.py`: 被动主循环。
- `agent/core/passive_turn.py`: 一轮被动对话管线。
- `agent/tools/registry.py`: 工具注册和执行。
- `bootstrap/memory.py`: 记忆运行时装配。
- `agent/plugins/manager.py`: 插件加载。
- `proactive_v2/loop.py`: 主动推送循环。

## 模块分层

```text
入口层
  main.py
  config.toml

装配层
  bootstrap/app.py
  bootstrap/tools.py
  bootstrap/wiring.py

通信层
  infra/channels/*
  bus/queue.py
  bus/event_bus.py

被动 Agent Core
  agent/looping/core.py
  agent/core/passive_turn.py
  agent/lifecycle/*

工具系统
  agent/tools/*
  bootstrap/toolsets/*
  agent/tool_hooks/*

记忆系统
  bootstrap/memory.py
  core/memory/*
  memory2/*
  plugins/default_memory/*

插件系统
  agent/plugins/*
  plugins/*

主动推送系统
  bootstrap/proactive.py
  proactive_v2/*

观测和管理
  bootstrap/dashboard_api.py
  frontend/dashboard/*
```

## 总体架构设计

这个项目可以理解成一个长期运行的 Agent Runtime。它的核心问题不是“如何调用一次 LLM”，而是：

```text
如何让一个 AI agent 长期运行、接收多渠道消息、调用工具、维护记忆、主动触达用户，并且可扩展、可观测？
```

因此它不是单层聊天 bot，而是拆成多层 runtime。

### 1. 入口层

代表文件：

- `main.py`
- `config.toml`

解决的问题：

```text
用户现在想以什么模式运行程序？
```

典型模式：

- 启动完整 agent 服务。
- 启动 CLI 客户端。
- 启动 Dashboard。
- 初始化 workspace。
- 进入 setup 配置向导。

设计取舍：

- `main.py` 只负责命令分流，不承载复杂业务。
- 真正的运行时组装放到 `bootstrap` 层。
- 入口保持简单后，服务模式、CLI 模式、Dashboard 模式可以共享配置加载逻辑。

### 2. 装配层

代表目录：

- `bootstrap/`

解决的问题：

```text
这些 runtime 对象谁来创建？谁依赖谁？启动顺序是什么？
```

它负责创建和连接：

- `Config`
- `LLMProvider`
- `MessageBus`
- `EventBus`
- `ToolRegistry`
- `MemoryRuntime`
- `AgentLoop`
- `PluginManager`
- `Scheduler`
- channels
- `ProactiveLoop`
- Dashboard

设计取舍：

- `main.py` 只说“我要启动服务”。
- `bootstrap` 负责“如何把服务搭起来”。
- 依赖创建集中在装配层，避免业务模块到处 new 对象。

### 3. 通信层

代表目录：

- `infra/channels/`
- `bus/`

解决的问题：

```text
Telegram、QQ、CLI、IPC 的消息格式不同，agent core 不应该关心这些差异。
```

通信层把外部协议统一成内部消息：

```text
InboundMessage(
  channel=...,
  sender=...,
  chat_id=...,
  content=...
)
```

核心设计：

- `Channel` 负责适配外部协议。
- `MessageBus` 负责 channel 和 agent 之间的入站/出站队列。
- `AgentLoop` 不直接依赖 Telegram/QQ/CLI。

设计价值：

- 新增渠道时，只需要增加 channel adapter。
- agent core 可以只处理统一内部消息。
- channel 和 agent 解耦，便于测试和替换。

## Channel 和通信层设计

通信层解决的问题是：

```text
CLI、Telegram、QQ、QQBot 等不同入口如何统一到同一套 Agent Core？
```

不同外部渠道的消息格式完全不同：

```text
CLI:
  本地 socket，一行 JSON

Telegram:
  bot update、chat_id、username、media、command

QQ:
  群号、用户 id、是否 @ bot、图片、权限

QQBot:
  官方 bot API、group_openid、主动推送限制
```

如果 Agent Core 直接处理这些差异，核心逻辑会被外部协议污染。因此项目使用 Channel Adapter 把外部协议适配为内部统一消息。

### 总体链路

```text
外部渠道
  CLI / IPC / Telegram / QQ / QQBot
        |
        v
Channel Adapter
        |
        v
InboundMessage
        |
        v
MessageBus inbound
        |
        v
AgentLoop
        |
        v
OutboundMessage
        |
        v
MessageBus outbound
        |
        v
Channel callback
        |
        v
外部渠道
```

### InboundMessage

无论外部来自哪里，进入 agent 后都统一成：

```text
InboundMessage(
  channel,
  sender,
  chat_id,
  content,
  timestamp,
  media,
  metadata
)
```

设计价值：

- `AgentLoop` 不关心消息来自 Telegram、CLI 还是 QQ。
- Agent Core 只处理统一格式。
- 新增渠道只需要新增 adapter。

### OutboundMessage

agent 回复时也不直接调用：

```text
telegram.send()
qq.send()
print()
```

而是统一生成：

```text
OutboundMessage(
  channel,
  chat_id,
  content,
  thinking,
  reply_to,
  media,
  metadata
)
```

然后由 `MessageBus` 找对应 channel callback 发出去。

设计价值：

- 回复路径统一。
- 发送失败可以集中处理。
- 不同 channel 可以复用同一 Agent Core。

### Channel Adapter 职责

一个 Channel Adapter 通常负责：

- 连接外部平台。
- 认证 / 权限校验。
- 接收外部消息。
- 解析文本、图片、文件。
- 处理命令，例如 `/stop`。
- 转换成 `InboundMessage`。
- 订阅 outbound 并发送回复。
- 处理发送失败。

典型例子：

```text
CLI/IPC:
  CLI client 输入 JSON
  IPC server 收到 JSON
  转成 InboundMessage(channel="cli", ...)

Telegram:
  收到 Telegram update
  校验 allow_from
  保存 media
  转成 InboundMessage(channel="telegram", ...)

QQ:
  收到群消息
  检查是否允许用户
  检查是否需要 @ bot
  转成 InboundMessage(channel="qq", ...)
```

### MessageBus

Channel 不直接调用 `AgentLoop.process()`，而是：

```text
Channel -> MessageBus -> AgentLoop
```

`MessageBus` 内部可以理解为：

```text
inbound queue:
  外部消息进入 agent

outbound queue:
  agent 回复发回外部
```

设计价值：

- Channel 不知道 agent 怎么处理。
- Agent 不知道 channel 怎么收发。
- 两边只约定 `InboundMessage` / `OutboundMessage`。
- 支持多 channel、异步缓冲、出站重试和降级。

### 出站分发

Channel 启动时会订阅自己的 channel：

```text
bus.subscribe_outbound("telegram", telegram.send)
bus.subscribe_outbound("cli", ipc._on_response)
bus.subscribe_outbound("qq", qq.send)
```

当 agent 生成：

```text
OutboundMessage(channel="telegram", chat_id="...", content="...")
```

`MessageBus.dispatch_outbound()` 会找到 `"telegram"` 的 callback 发送。

设计价值：

- agent 只需要指定 `channel` 和 `chat_id`。
- 具体怎么发送由 channel adapter 负责。

### MessageBus 和 EventBus 的区别

这两个 bus 不要混淆。

```text
MessageBus:
  用户通信路径
  处理 InboundMessage / OutboundMessage
  负责 channel -> agent -> channel

EventBus:
  内部生命周期和插件事件路径
  处理 TurnStarted、BeforeTurnCtx、ToolCallStarted、TurnCommitted 等
  负责插件观察、审计、日志、副作用
```

一句话：

```text
MessageBus 负责用户消息通信，EventBus 负责内部生命周期事件。
```

### CLI / IPC 的特殊性

CLI 模式分两部分：

```text
main.py
  启动 agent 服务和 IPC server

main.py cli
  启动 CLI 客户端，连接 IPC server
```

CLI 客户端不是 agent，它只做：

- 读取用户输入。
- 包装成 JSON。
- 写入 socket。
- 读取 socket 返回。
- 打印结果。

真正把 JSON 转成 `InboundMessage` 的是服务侧：

```text
IPCServerChannel
```

设计价值：

- 本地开发和调试方便。
- CLI 和 Telegram/QQ 一样走统一 channel/message bus。

### PushTool 和主动推送

被动回复通常走：

```text
OutboundMessage -> MessageBus outbound -> channel callback
```

主动推送更多使用：

```text
MessagePushTool
```

它维护不同 channel 的发送函数，例如：

- telegram text/send_file/send_image
- qq text/send_file/send_image
- qqbot send_proactive

设计价值：

- 主动推送不依赖当前 inbound 消息。
- 可以按 channel/chat_id 主动发送。

### 一句话总结

```text
Channel 层把 CLI、Telegram、QQ、QQBot 等外部协议统一适配成 InboundMessage/OutboundMessage，MessageBus 用 inbound/outbound 队列解耦 channel 和 AgentLoop，EventBus 则独立负责生命周期事件和插件观察；这样 Agent Core 不关心外部平台差异，新渠道也能通过 adapter 接入。
```

### 4. 被动 Agent Core

代表目录：

- `agent/looping/`
- `agent/core/`
- `agent/lifecycle/`

解决的问题：

```text
收到用户消息后，如何完成一轮可靠的 agent 对话？
```

一轮对话包括：

- 读取 session。
- 检索记忆。
- 准备 prompt。
- 暴露工具。
- 执行 LLM tool loop。
- 解析最终回复。
- 写回会话。
- 发送结果。
- 触发后处理。

核心设计：

```text
BeforeTurn
  -> BeforeReasoning
  -> PromptRender
  -> Reasoner / Tool Loop
  -> AfterReasoning
  -> AfterTurn
```

设计价值：

- 每个阶段职责清楚。
- 插件可以挂在明确生命周期点。
- 出错时更容易定位阶段。
- 后续新增行为不需要塞进单个巨大 `handle_message()`。

### 5. 工具系统

代表目录：

- `agent/tools/`
- `bootstrap/toolsets/`
- `agent/tool_hooks/`

解决的问题：

```text
LLM 如何知道有哪些工具？如何执行工具？工具太多时如何控制 prompt 压力？危险工具如何治理？
```

核心对象：

- `ToolRegistry`
- `Tool`
- `ToolHook`
- `tool_search`

核心设计：

- `always_on` 工具每轮默认暴露。
- deferred 工具默认隐藏。
- `tool_search` 按需加载 deferred 工具。
- tool hook 可做安全拦截、限流、审计和阻断。

设计价值：

- 减少工具 schema 占用。
- 降低模型选错工具的概率。
- 给危险工具留出治理入口。

### 6. 记忆系统

代表目录：

- `core/memory/`
- `memory2/`
- `plugins/default_memory/`

解决的问题：

```text
agent 如何长期记住用户信息、历史事件和偏好？
```

核心分层：

- markdown memory: 稳定、可读、可编辑。
- semantic/vector memory: 面向 query 的相关记忆检索。

重要文件概念：

- `MEMORY.md`: 长期稳定记忆。
- `SELF.md`: 自我/用户画像相关内容。
- `RECENT_CONTEXT.md`: 近期上下文。
- `HISTORY.md`: 时间线事件。
- `PENDING.md`: 待归档缓冲。

设计价值：

- markdown 层保证可读和可控。
- 向量层提升召回能力。
- `PENDING.md` 减少频繁修改长期 memory 对 prompt cache 的破坏。

### 7. 插件系统

代表目录：

- `agent/plugins/`
- `plugins/`

解决的问题：

```text
如果想新增能力，是否必须改 AgentLoop 主链路？
```

插件可以：

- 注册工具。
- 注册工具 hook。
- 注入 lifecycle phase module。
- 监听事件。
- 提供 Dashboard 面板。

设计价值：

- 核心链路保持稳定。
- 扩展能力通过插件接入。
- 功能可以独立演进。

### 8. 主动推送系统

代表目录：

- `bootstrap/proactive.py`
- `proactive_v2/`

解决的问题：

```text
agent 能不能不等用户问，而是在合适的时候主动找用户？
```

主动推送不是简单定时任务，它需要判断：

- 有没有值得推送的内容。
- 用户最近是否活跃。
- 是否刚刚推送过。
- 内容是否重复。
- 是否会打扰用户。
- 空闲时是否进入 drift 后台任务。

核心对象：

- `ProactiveLoop`
- `Sensor`
- `PresenceStore`
- energy model
- dedupe / cooldown
- `AgentTick`
- `TurnOrchestrator`

设计价值：

- 从普通 request-response bot 升级为主动 agent。
- 通过 presence/cooldown/dedupe 降低打扰。
- drift 让 agent 空闲时也能执行后台任务。

### 9. Dashboard 和可观测性

代表目录：

- `bootstrap/dashboard_api.py`
- `frontend/dashboard/`

解决的问题：

```text
agent 长期运行后，如何知道它做过什么？
```

Dashboard 关注：

- sessions
- messages
- proactive tick logs
- memory
- plugin panels
- manual consolidation

设计价值：

- 降低 agent 黑盒程度。
- 方便排查为什么回复、为什么推送、为什么跳过。
- 支持长期运行系统的运营和调试。

## Dashboard 和可观测性设计

Dashboard 解决的问题是：

```text
如何观察、调试、管理一个长期运行的 agent？
```

普通 demo 只需要看命令行输出，但长期运行的 agent 会积累很多状态：

- 用户说过什么。
- agent 回过什么。
- 用了什么工具。
- 记住了什么。
- 主动推送过什么。
- 为什么跳过推送。
- 插件是否正常。
- 记忆整理是否成功。

如果没有 Dashboard，agent 很容易变成黑盒。

### 总体链路

```text
Agent Runtime
   |
   +--> SessionStore
   +--> Message history
   +--> Memory store
   +--> ProactiveStateStore
   +--> Plugin panels
   +--> Manual operations
             |
             v
      Dashboard API
             |
             v
       React Dashboard
```

### 为什么 Agent 特别需要可观测性

普通 Web 服务通常是：

```text
请求 -> 业务逻辑 -> 响应
```

Agent 多了很多不确定性：

- LLM 输出不稳定。
- 工具调用路径不固定。
- 记忆可能影响回答。
- 插件可能介入流程。
- 主动推送可能跳过。
- 多轮 session 状态会积累。

因此排查问题不能只看最终回答，还要知道：

- 它看到了什么上下文。
- 它用了什么工具。
- 它为什么记住这件事。
- 它为什么主动推送。
- 它为什么没有推。
- 哪个插件介入了。

### Sessions

Session 是 agent 的用户上下文单位。

Dashboard 看 session 可以知道：

- 有哪些会话。
- 最后一次用户消息是什么时候。
- 最后一次主动推送是什么时候。
- session metadata。
- `last_consolidated`。
- channel/chat_id。

设计价值：

- 知道 agent 在和谁持续交互。
- 知道每个用户/会话的状态。
- 定位某个用户的历史上下文。

### Messages

Message history 用来还原 agent 的交互过程。

它不仅是聊天记录，还可能包含：

- role
- content
- tool_chain
- metadata
- media
- proactive 标记
- evidence ids
- source refs
- state summary tag

设计价值：

- 定位某次回答为什么这么说。
- 查看是否用了工具。
- 查看是否是主动消息。
- 查看引用和证据来源。

### Memory

记忆系统如果不可见，会很危险，因为 agent 的回答可能受长期记忆影响。

Dashboard / memory admin 可以帮助：

- 查看记忆条目。
- 修改错误记忆。
- 删除污染记忆。
- 手动触发 consolidation。
- 手动触发 memory optimize。

设计价值：

- 长期记忆可审计。
- 错误记忆可修正。
- 记忆整理可人工干预。

### Proactive Tick Logs

主动推送尤其需要可观测性，因为它不只要看“发了什么”，还要看：

- 为什么发。
- 为什么没发。
- 卡在哪个 gate。
- 是否 cooldown。
- 是否 duplicate。
- 是否 passive busy。
- 是否 LLM 判断 skip。
- 是否进入 drift。

Dashboard 可以观察：

- tick_id
- session_key
- started_at / finished_at
- gate_exit
- terminal_action
- skip_reason
- steps_taken
- drift_entered
- source refs

设计价值：

- 主动推送可解释。
- 跳过原因可排查。
- 长期主动行为可审计。

### Plugin Panels

插件可以有自己的状态和数据，例如：

- `recall_inspector`
- `memory_rollup`
- `status_commands`
- `observe`

插件面板可以展示：

- 插件日志。
- 召回结果。
- 记忆 rollup。
- 观察事件。
- 状态统计。

设计价值：

- 插件不仅能扩展运行时，也能扩展观测面。
- 每个插件可以提供最适合自己的 debug UI。

### Manual Operations

长期 agent 不能完全自动化。

Dashboard 提供手动操作，例如：

- 手动 consolidation。
- 手动 memory optimizer。
- 编辑 session metadata。
- 删除 message。
- 删除 memory。
- 清理 proactive 状态。

设计价值：

- 当自动流程出错时，人可以介入修正。
- 适合长期运行和真实用户数据管理。

### Dashboard API 和前端分工

后端：

```text
bootstrap/dashboard_api.py
```

负责：

- 读取 session db。
- 读取 proactive db。
- 读取 memory admin。
- 暴露 REST API。
- 处理手动操作。
- 挂载静态前端。
- 加载插件面板配置。

前端：

```text
frontend/dashboard/
```

负责：

- 展示 session/message/proactive 列表。
- 筛选、分页、排序。
- 展示详情。
- 加载插件 panel。
- 触发手动操作。

设计价值：

- 后端靠近 runtime 数据。
- 前端负责交互和可视化。
- 插件 panel 可以扩展 UI。

### Dashboard 和普通后台的区别

普通后台页面通常管理业务数据。

这个 Dashboard 管的是 agent runtime 状态：

- agent 为什么这么做。
- agent 记住了什么。
- agent 使用了什么工具。
- agent 为什么主动推或跳过。
- 插件是否影响了流程。

所以它更接近：

```text
Agent observability console
```

而不只是 CRUD 后台。

### 一句话总结

```text
Dashboard 为长期运行的 agent 提供可观测和人工干预能力，围绕 session、message、memory、proactive tick、plugin panel 和 manual operations 展示 agent 的对话历史、记忆状态、主动推送决策和插件运行状态，降低 agent 黑盒程度，方便调试、审计和运营。
```

## 一句话架构总结

```text
main.py 负责入口，bootstrap 负责装配，channels/bus 负责通信，AgentCore 负责被动对话，tools 提供行动能力，memory 提供长期上下文，plugins 提供扩展点，proactive 提供主动触达，dashboard 提供观测管理。
```

面试版：

```text
这是一个事件驱动的 Agent Runtime。它通过 MessageBus 解耦渠道和 agent，通过 lifecycle pipeline 拆分一轮对话，通过 ToolRegistry 管理工具，通过 MemoryRuntime 管理长期记忆，通过 PluginManager 扩展能力，并通过 ProactiveLoop 支持主动触达。
```

## 模块学习模板

每个模块后续都按这个模板记录：

```text
模块解决的问题:
核心对象:
输入:
输出:
上游调用方:
下游依赖:
关键数据流:
设计取舍:
风险/不足:
面试表达:
```

## 启动主线

关键文件：

- `main.py`
- `bootstrap/app.py`
- `bootstrap/tools.py`

### `main.py` 命令分流

`main.py` 是项目总入口。程序从 `if __name__ == "__main__"` 开始读取命令行参数：

```python
args = sys.argv[1:]
```

默认值：

- `config_path = "config.toml"`
- `workspace = None`，后续使用 `~/.akashic/workspace`
- `dashboard_host = "0.0.0.0"`
- `dashboard_port = 2236`

支持的通用覆盖参数：

- `--config`: 指定配置文件。
- `--workspace`: 指定 workspace。
- `--host`: 指定 Dashboard host。
- `--port`: 指定 Dashboard port。

命令分流：

```text
python main.py setup      -> run_setup_wizard()，交互式配置向导
python main.py init       -> init_workspace()，非交互初始化
python main.py gateway    -> serve()，启动完整服务
python main.py dashboard  -> run_dashboard_api()，只启动 Dashboard
python main.py cli        -> connect_cli()，连接已运行 agent
python main.py            -> serve()，启动完整 agent 服务
```

需要注意：

- `main.py cli` 是客户端模式，它不会启动完整 agent。
- CLI 要能问答，前提是已有一个 `main.py` 默认服务进程正在运行。
- 默认服务模式最终会进入 `serve(config_path, workspace)`。

启动流程：

```text
main.py
  -> Config.load(config.toml)
  -> build_app_runtime(config, workspace)
  -> AppRuntime.start()
      -> build_core_runtime()
      -> core.start()
      -> start_channels()
      -> build_memory_optimizer_task()
      -> build_dashboard_server()
      -> build_proactive_runtime()
  -> asyncio.gather(runtime tasks)
```

### 默认服务模式

当没有传特殊命令时，最后执行：

```python
asyncio.run(serve(config_path, workspace))
```

`serve()` 会：

1. 读取配置：`Config.load(config_path)`。
2. 构建运行时：`build_app_runtime(config, workspace=...)`。
3. 注册 `SIGINT` / `SIGTERM` 停止信号。
4. 创建 `runtime.run()` 后台任务。
5. 等待运行时结束或收到停止信号。

下一步需要继续阅读：

- `connect_cli()`：CLI 如何连接已有服务。
- `serve()`：完整 agent runtime 如何启动。

## 核心运行时对象

- `MessageBus`: channel 和 agent 之间的入站/出站消息队列。
- `EventBus`: 生命周期事件和插件观察者使用的事件总线。
- `AgentLoop`: 被动对话主循环。
- `ToolRegistry`: 工具注册、检索、schema 暴露和执行入口。
- `MemoryRuntime`: markdown memory 和语义 memory engine 的统一门面。
- `PluginManager`: 扫描和加载插件，注册工具、hook、phase module。
- `ProactiveLoop`: 主动推送常驻循环。
- `DashboardServer`: 管理和观测用 HTTP 服务。

## 主要数据流

### 被动消息

```text
Channel
  -> MessageBus.publish_inbound
  -> AgentLoop.consume_inbound
  -> CoreRunner
  -> AgentCore
  -> PassiveTurnPipeline
  -> LLM / Tools / Memory
  -> MessageBus.publish_outbound
  -> Channel callback
```

### 主动推送

```text
ProactiveLoop
  -> Sensor / MCP sources / presence / memory
  -> AgentTick
  -> TurnResult
  -> TurnOrchestrator
  -> MessagePushTool
  -> Channel
```

## MessageBus 与 EventBus

当前理解：

- `MessageBus` 面向“用户消息和 agent 回复”的业务通道。
- `EventBus` 面向“生命周期事件、插件、观测、副作用”的内部事件。

## 可插拔点

- wiring: `bootstrap/wiring.py`
- toolsets: `bootstrap/toolsets/*`
- memory plugin: `plugins/*/memory_plugin.py`
- lifecycle phase module: `agent/lifecycle/*`
- plugin hook: `agent/plugins/manager.py`

## 后续更新提示词

```text
请更新 my_md/architecture/02-architecture.md：根据这次阅读源码的结果，补充架构图、关键对象职责、调用链路和源码路径。
```
