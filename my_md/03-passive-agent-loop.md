# 03 Passive Agent Loop

## 目标

记录“一条用户消息从进入系统到最终回复”的完整过程。

## 关键文件

- `agent/looping/core.py`
- `agent/core/runner.py`
- `agent/core/passive_turn.py`
- `agent/provider.py`
- `agent/turns/outbound.py`
- `bus/queue.py`

## 设计层总结

被动对话框架解决的问题是：

```text
用户发来一条消息，agent 如何可靠地生成一个回复？
```

这个问题不只是调用一次 LLM。真实一轮对话还包括：

- 判断消息属于哪个用户和会话。
- 读取历史消息。
- 注入长期记忆。
- 决定暴露哪些工具。
- 处理 LLM 的工具调用循环。
- 处理工具失败、模型拒绝、上下文过长等异常情况。
- 把最终回复写回 session。
- 把回复发回原 channel。
- 触发记忆整理、事件通知和插件后处理。

因此它被设计成一条 turn pipeline，而不是一个巨大的 `handle_message()`。

核心链路：

```text
Channel
  -> MessageBus
  -> AgentLoop
  -> CoreRunner
  -> AgentCore
  -> PassiveTurnPipeline
  -> Reasoner / Tool Loop
  -> OutboundMessage
  -> MessageBus outbound
  -> Channel callback
```

### 模块职责

#### Channel

解决外部协议适配问题。

CLI、Telegram、QQ、IPC 的输入格式都不同，agent core 不应该关心这些差异。Channel 层负责把外部消息统一转换为：

```text
InboundMessage(channel, sender, chat_id, content, media, metadata)
```

设计价值：

- 外部协议复杂，内部核心简单。
- 新增渠道时，不需要改 agent core。

#### MessageBus

解决 channel 和 agent 的解耦问题。

它提供两个方向的队列：

```text
inbound:  channel -> agent
outbound: agent -> channel
```

设计价值：

- Channel 不直接调用 AgentLoop。
- AgentLoop 不直接依赖 Telegram/QQ/CLI。
- 出站消息也可以统一调度、重试和降级。

#### AgentLoop

解决消息消费和 turn 生命周期管理问题。

它负责：

- 持续消费 inbound 队列。
- 为每条消息创建一轮 turn。
- 记录 active task。
- 支持 `/stop` 中断。
- 标记 processing busy。
- 把具体处理交给 `CoreRunner`。

设计价值：

- 把“消息调度”与“具体推理逻辑”分离。
- 主动推送系统可以通过 busy 状态避免打扰当前会话。

#### CoreRunner

解决入站项分流问题。

进入 `AgentLoop` 的不一定都是普通用户消息，也可能是：

- `InboundMessage`: 普通用户消息。
- `SpawnCompletionItem`: 子 agent 完成事件。
- `ShellCompletionItem`: 后台 shell 完成事件。

`CoreRunner` 把普通消息交给 `AgentCore`，把内部工作项交给专门 handler。

设计价值：

- `AgentLoop` 不需要知道所有内部事件怎么处理。
- 普通对话和内部事件回灌保持边界清楚。

#### AgentCore

解决普通被动对话的统一入口问题。

`AgentCore` 本身很薄，主要持有：

```text
PassiveTurnPipeline
```

设计价值：

- 明确从这里开始进入“普通用户消息处理能力”。
- 后续替换 pipeline 或扩展 core 时有稳定门面。

#### PassiveTurnPipeline

解决一轮对话复杂度拆分问题。

一轮对话被拆成：

```text
BeforeTurn
  -> BeforeReasoning
  -> PromptRender
  -> Reasoner / Tool Loop
  -> AfterReasoning
  -> AfterTurn
```

各阶段职责：

- `BeforeTurn`: 获取 session，准备上下文，触发生命周期事件。
- `BeforeReasoning`: 同步工具上下文，整理记忆检索结果，准备推理前信息。
- `PromptRender`: 组装 system prompt、历史、记忆、用户消息和插件注入内容。
- `Reasoner / Tool Loop`: 调 LLM，解析 tool calls，执行工具，再把工具结果喂回模型。
- `AfterReasoning`: 解析最终回复，写入 session，构造 `OutboundMessage`。
- `AfterTurn`: 提交事件，触发后处理，真正 dispatch 回复。

设计价值：

- 职责分层。
- 插件可插入。
- 错误定位清晰。
- 不同阶段可以独立测试。

#### Reasoner / Tool Loop

解决 LLM 多步推理和工具调用问题。

模型可能不会直接回答，而是：

```text
LLM 请求工具
  -> 执行工具
  -> 追加工具结果
  -> LLM 继续推理
  -> 最终回复
```

Reasoner 负责管理：

- 最大迭代次数。
- 当前可见工具。
- 工具调用结果。
- 工具错误。
- 安全 retry。
- 上下文裁剪。
- 流式输出。

设计价值：

- 把 LLM 推理和工具循环集中管理。
- Pipeline 不需要关心每一步工具调用细节。

#### Outbound

解决统一回复路径问题。

最终回复被包装成：

```text
OutboundMessage(channel, chat_id, content, ...)
```

再通过：

```text
MessageBus.publish_outbound()
  -> bus.dispatch_outbound()
  -> channel callback
```

发回原渠道。

设计价值：

- 回复路径统一。
- 不同 channel 复用同一 agent core。
- 发送失败可以集中处理和降级。

## 一句话总结

```text
Channel 把外部消息转成统一 InboundMessage，MessageBus 负责异步解耦，AgentLoop 负责消费消息和管理 turn 生命周期，CoreRunner 负责区分普通消息和内部回灌事件，AgentCore/PassiveTurnPipeline 负责执行一轮被动对话，Reasoner 负责 LLM + 工具循环，最后通过 OutboundMessage 统一发回 channel。
```

## 入口

当前先从 CLI 问答场景追踪。启动方式分两部分：

```text
uv run python main.py      # 启动完整 agent 服务
uv run python main.py cli  # 启动 CLI 客户端，连接运行中的 agent
```

`main.py cli` 会走 `connect_cli(config_path)`，它不是 agent 服务本体，只是一个客户端入口。真正处理消息的服务侧由默认命令 `main.py` 启动。

已确认的入口分流：

```text
main.py cli -> connect_cli()
main.py     -> serve() -> build_app_runtime() -> AppRuntime.run()
```

下一步要追踪：

```text
connect_cli()
  -> infra.channels.cli_tui.run_tui()
  -> 或 infra.channels.cli.CLIClient.run()
  -> IPC/socket
  -> 服务侧 IPC server
  -> MessageBus.publish_inbound()
```

## CLI 客户端发送消息

`connect_cli(config_path)` 会读取配置：

```text
Config.load(config_path).channels.socket
```

然后优先启动：

```text
infra.channels.cli_tui.run_tui(socket_path)
```

如果 TUI 缺依赖，则回退：

```text
infra.channels.cli.CLIClient(socket_path).run()
```

纯文本 CLI 的核心行为：

```text
用户输入: 你好
发送 JSON: {"content": "你好"}\n
```

连接方式：

- `host:port` 形式走 TCP socket。
- 其他路径形式走 Unix socket，例如 `/tmp/akashic.sock`。

## 服务侧 IPC Server

默认服务模式 `main.py` 会进入：

```text
serve()
  -> build_app_runtime()
  -> AppRuntime.run()
  -> AppRuntime.start()
  -> start_channels()
  -> IPCServerChannel(bus, config.channels.socket)
  -> ipc.start()
```

`IPCServerChannel.start()` 会创建 socket server：

- TCP endpoint: `asyncio.start_server(...)`
- Unix socket: `asyncio.start_unix_server(...)`

当 CLI 连接进来后，`IPCServerChannel._handle_connection()` 会：

1. 给连接生成 `chat_id = "cli-<writer id>"`。
2. 保存 `chat_id -> writer`，方便之后把回复写回同一个 CLI。
3. 按行读取 JSON。
4. 取出 `content`。
5. 构造内部统一消息：

```text
InboundMessage(
  channel="cli",
  sender="cli-user",
  chat_id="cli-...",
  content="用户输入"
)
```

6. 调用：

```text
MessageBus.publish_inbound()
```

## MessageBus 入站队列

`MessageBus` 内部有两个队列：

```text
_inbound   channel -> agent
_outbound  agent -> channel
```

CLI 消息进入：

```text
publish_inbound(msg)
  -> _inbound.put(msg)
```

此时消息还没有被 LLM 处理，只是进入 agent 的入站队列。

`AgentLoop.run()` 不断从 `MessageBus` 消费入站消息：

```text
item = await bus.consume_inbound()
task = asyncio.create_task(self._process(item))
```

## AgentLoop 消费入站消息

完整服务启动时，`AppRuntime.start()` 会创建长期任务：

```text
self.agent_loop.run()
self.bus.dispatch_outbound()
self.scheduler.run()
```

其中 `AgentLoop.run()` 负责消费 `_inbound`：

```text
bus.consume_inbound()
  -> _inbound.get()
```

拿到消息后：

1. 计算 `key = item.session_key`。
2. 创建 active turn state，用于记录本轮 partial reply、工具链和中断状态。
3. 创建 task 执行 `self._process(item)`。
4. 等待 task 完成。
5. 清理 active task 和 active turn state。

CLI 场景的 `session_key` 形如：

```text
cli:cli-<writer id>
```

## AgentLoop._process()

`_process()` 会：

1. 处理 interrupt resume 状态。
2. 发出 `TurnStarted` 事件。
3. 标记 processing busy。
4. 调用 `CoreRunner.process()`。
5. 退出 busy 状态。

这里的 `TurnStarted` 走的是 `EventBus`，用于插件、观察者、状态追踪，不是直接给用户发消息。

`processing_state.enter(key)` 会标记这个 session 正在处理消息。主动推送链路可以据此避免在用户当前对话处理中插入消息。

## CoreRunner

`CoreRunner` 根据入站消息类型分流：

- `InboundMessage`: 普通被动消息，进入 `AgentCore.process()`。
- `SpawnCompletionItem`: 子 agent 完成事件。
- `ShellCompletionItem`: 后台 shell 完成事件。

CLI 问答属于普通 `InboundMessage`，因此最终进入：

```text
AgentCore.process(msg, key, dispatch_outbound=True)
```

## PassiveTurnPipeline

`AgentCore` 是一个很薄的门面：

```text
AgentCore.process()
  -> self._passive_pipeline.run(msg, key, dispatch_outbound=...)
```

真正的一轮被动对话由 `PassiveTurnPipeline.run()` 执行。

普通消息进入 `PassiveTurnPipeline.run()` 后，依次经过：

1. `BeforeTurn`
2. `BeforeReasoning`
3. `Reasoner.run_turn`
4. `AfterReasoning`
5. `AfterTurn`

`PassiveTurnPipeline.run()` 开始时会创建：

```text
TurnState(
  msg=msg,
  session_key=key,
  dispatch_outbound=dispatch_outbound
)
```

这个 `TurnState` 是本轮被动对话的主状态对象。后续 phase 会不断往里面填：

- `session`
- `extra_metadata`
- 本轮消息上下文
- 是否需要直接 abort

## Pipeline Phase 构建

`PassiveTurnPipeline.__init__()` 会保存依赖：

- session services
- context store
- context builder
- tool registry
- reasoner
- event bus
- outbound port
- plugin modules

然后构建 4 个 pipeline 外层 phase：

```text
self._before_turn = self._build_before_turn_phase()
self._before_reasoning = self._build_before_reasoning_phase()
self._after_reasoning = self._build_after_reasoning_phase()
self._after_turn = self._build_after_turn_phase()
```

`PromptRender`、`BeforeStep`、`AfterStep` 不在 `PassiveTurnPipeline.run()` 外层直接调用，而是在 `Reasoner` 内部执行。

## Phase 职责

### BeforeTurn

当前理解：

- 获取或创建 session。
- 准备基础 turn state。
- 触发生命周期事件。

源码位置：

- `agent/core/passive_turn.py`
- `agent/lifecycle/phases/before_turn.py`

`BeforeTurn` 的默认模块链来自：

```text
default_before_turn_modules(...)
```

内置模块顺序：

```text
_AcquireSessionModule
  -> _PrepareContextModule
  -> _BuildBeforeTurnCtxModule
  -> _EmitBeforeTurnCtxModule
  -> _CollectBeforeTurnExportSlotsModule
  -> _ReturnBeforeTurnCtxModule
```

#### 1. Acquire Session

```text
session_manager.get_or_create(state.session_key)
state.session = session
```

作用：

- 用 `session_key` 获取或创建会话。
- 把 session 写入 `TurnState`。
- 把 session 放入 phase slots，供后续模块使用。

#### 2. Prepare Context

```text
context_store.prepare(
  msg=state.msg,
  session_key=state.session_key,
  session=session
)
```

作用：

- 读取 session history。
- 执行记忆检索。
- 收集 skill mentions。
- 生成 `ContextBundle`。

这一步具体由 `DefaultContextStore.prepare()` 实现，后续需要单独追踪。

#### 3. Build BeforeTurnCtx

把 `TurnState` 和 `ContextBundle` 转成生命周期上下文：

```text
BeforeTurnCtx(
  session_key=...,
  channel=...,
  chat_id=...,
  content=...,
  timestamp=...,
  skill_names=...,
  retrieved_memory_block=...,
  retrieval_trace_raw=...,
  history_messages=...
)
```

作用：

- 给插件和事件监听者一个稳定的上下文对象。
- 把检索到的记忆和历史消息带到后续 phase。

#### 4. Emit BeforeTurnCtx

```text
ctx = await event_bus.emit(ctx)
```

作用：

- 让插件或事件监听者有机会读取/修改 `BeforeTurnCtx`。

#### 5. Collect Exports

收集插件模块写入 slots 的导出：

- `session:extra_hint:*` 会追加到 `ctx.extra_hints`。
- `session:abort_reply` 会让本轮提前 abort。

如果 `before_turn.abort` 为 true，`PassiveTurnPipeline.run()` 会直接构造 `OutboundMessage`，不再进入 LLM reasoning。

#### 6. Return Ctx

把最终 `BeforeTurnCtx` 作为 phase 输出，返回给 `PassiveTurnPipeline.run()`。

### BeforeReasoning

当前理解：

- 准备工具上下文。
- 执行记忆检索。
- 收集 skill mentions。
- 生成额外 prompt hints。

### PromptRender

当前理解：

- 由 `ContextBuilder` 构造最终 LLM messages。
- 插件可以注入 prompt 内容。

### Reasoner

当前理解：

- 调用 LLM。
- 如果返回 tool calls，则执行工具。
- 将工具结果追加到消息。
- 循环直到生成最终回复或达到限制。

### AfterReasoning

当前理解：

- 解析 LLM 输出。
- 写入 session。
- 构造 `OutboundMessage`。

### AfterTurn

当前理解：

- 提交 turn。
- 发布事件。
- 根据 `dispatch_outbound` 决定是否发送。

## 需要继续追踪的问题

- `DefaultReasoner.run_turn()` 的 retry / trim / safety retry 细节。
- tool loop 中工具 schema 何时可见。
- stream delta 如何同步到 Telegram 和 session partial state。
- `AfterReasoning` 如何触发 post memory consolidation。

## 后续更新提示词

```text
请更新 my_md/03-passive-agent-loop.md：把这次追踪到的被动对话调用链、关键函数、Phase 行为和未理解问题补充进去。
```
