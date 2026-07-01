# 06 Interview Notes

## 项目定位表达

30 秒版本：

```text
这个项目是一个事件驱动的 Agent Runtime，不只是聊天机器人。它支持被动多轮对话、工具调用、长期记忆、主动推送、插件扩展、多渠道接入和 Dashboard 观测。我重点学习的是它如何把 LLM、工具、记忆和主动触达组织成一个可运行的 agent 应用框架。
```

## 3 分钟技术介绍草稿

```text
项目入口是 main.py，启动时通过 bootstrap 层装配配置、LLM provider、MessageBus、EventBus、ToolRegistry、MemoryRuntime、AgentLoop、PluginManager 和 ProactiveLoop。

被动对话链路是 Channel -> MessageBus -> AgentLoop -> PassiveTurnPipeline。每轮消息会经过 BeforeTurn、BeforeReasoning、PromptRender、Reasoner、AfterReasoning、AfterTurn 这些生命周期阶段。这样做的好处是记忆注入、工具上下文、插件扩展、事件观测都可以挂在明确的位置。

工具系统通过 ToolRegistry 管理，区分 always-on 和 deferred tools。deferred 工具默认不进入 prompt，需要通过 tool_search 按需加载，从而减少工具 schema 对上下文的占用。

记忆系统分成 markdown 记忆层和语义检索层。markdown 层负责长期稳定记忆和近期上下文，语义层负责向量检索。项目还通过 PENDING.md 和 memory optimizer 降低频繁修改长期记忆对 prompt cache 的影响。

主动推送链路由 ProactiveLoop 负责，它会轮询内容源、读取用户状态和规则上下文，判断是否应该主动发消息。它还包含去重、冷却、presence 和 drift 空闲任务机制。
```

## 总体架构表达

一句话：

```text
main.py 负责入口，bootstrap 负责装配，channels/bus 负责通信，AgentCore 负责被动对话，tools 提供行动能力，memory 提供长期上下文，plugins 提供扩展点，proactive 提供主动触达，dashboard 提供观测管理。
```

更偏技术面试的版本：

```text
这是一个事件驱动的 Agent Runtime。它通过 MessageBus 解耦渠道和 agent，通过 lifecycle pipeline 拆分一轮对话，通过 ToolRegistry 管理工具，通过 MemoryRuntime 管理长期记忆，通过 PluginManager 扩展能力，并通过 ProactiveLoop 支持主动触达。
```

如果面试官问“为什么要拆这么多层”，可以回答：

```text
因为这个项目不是一次性问答脚本，而是长期运行的 agent 服务。它需要多渠道接入、异步消息队列、工具调用、长期记忆、插件扩展、主动触达和可观测性。如果这些都放在一个 handle_message 里，后续会很难扩展和排查。所以项目把入口、装配、通信、对话核心、工具、记忆、插件、主动推送和 Dashboard 分层，每层只处理自己的问题。
```

## 可重点讲的模块

## 学习策略说明

这个项目不适合只作为“逐行读源码”的练习，更适合作为 Agent Runtime / Agent Infra 的设计案例。

面试时应该强调：

- 我重点理解的是系统拆分、模块边界、数据流和设计取舍。
- 我不会声称背下每一行实现，但能定位关键入口和核心对象。
- 对 AI 辅助编码项目，工程价值在于能设计模块、约束接口、审查输出、集成能力，而不是手写所有细节。

可用表达：

```text
我学习这个项目时没有把重点放在逐行背源码，而是按 Agent Runtime 的模块设计来拆解：入口和装配、通信总线、被动 turn pipeline、工具系统、记忆系统、插件系统、主动推送和 Dashboard。这样能更接近实际 Agent 应用开发中需要的架构判断和问题定位能力。
```

### 1. 被动 Agent Loop

可讲点：

- MessageBus 解耦 channel 和 agent。
- PassiveTurnPipeline 用 Phase 拆分一轮对话。
- Reasoner 内部执行 LLM tool loop。
- interrupt/resume 支持中断后续跑。

面试表达：

```text
被动对话不是简单调用 LLM，而是一条 turn pipeline。项目用 MessageBus 解耦渠道和 agent，用 AgentLoop 管理消息消费和任务生命周期，用 CoreRunner 区分普通消息和内部回灌事件，用 PassiveTurnPipeline 拆分 BeforeTurn、BeforeReasoning、PromptRender、Reasoner、AfterReasoning、AfterTurn 等阶段，让记忆、工具、插件和后处理都能挂在明确位置。
```

如果面试官问“为什么不直接 channel 调 LLM”，可以回答：

```text
因为真实 agent 一轮对话需要处理 session、历史、长期记忆、工具调用、插件、错误兜底、流式输出和最终 dispatch。如果 channel 直接调 LLM，会把协议适配、任务生命周期和推理逻辑耦合在一起。这个项目用 Channel -> MessageBus -> AgentLoop -> Pipeline 的方式分层，让外部协议、消息调度和 agent reasoning 各自独立。
```

### 2. Tool System

可讲点：

- `ToolRegistry` 统一注册和执行。
- `always_on` vs deferred tools。
- `tool_search` 降低 prompt 压力。
- tool hook 可以做安全、限流、审计、阻断。

面试表达：

```text
这个项目没有把工具简单写成函数列表，而是做了工具运行时。ToolRegistry 统一管理工具和元信息，toolset、plugin、MCP 都可以注册工具；always_on 和 deferred tools 解决工具数量增长导致的 prompt 压力；tool_search 提供按需工具发现；ToolHook 和 ToolExecutor 提供安全拦截和执行治理。这让它更像 Agent Infra，而不是简单 function calling demo。
```

如果面试官问“为什么需要 deferred tool search”，可以回答：

```text
工具一多，如果每轮都把所有 schema 暴露给模型，会造成 token 成本高、上下文变长、模型选错工具概率上升。deferred tools 默认隐藏，只保留少量 always_on 工具；当模型需要能力时先通过 tool_search 发现相关工具，再加载使用。这样可以支持更多工具和 MCP server，同时控制 prompt 压力。
```

如果面试官问“工具调用怎么保证安全”，可以回答：

```text
工具调用不是直接 tool.execute，而是经过 ToolExecutor 和 ToolHook。Hook 可以在执行前做 allow、deny、rewrite、audit、rate limit、loop guard 和 safety check。比如 shell_safety 可以阻止危险 shell，tool_loop_guard 可以防止模型重复调用同一个工具。
```

### 3. Memory System

可讲点：

- markdown memory 和 vector memory 分层。
- consolidation 自动提取长期事实。
- `PENDING.md` 保护 prompt cache。
- post-response worker 在回复后异步整理记忆。

面试表达：

```text
这个项目的记忆系统不是简单把聊天记录塞进向量库，而是分成 markdown 长期记忆和 semantic/vector 检索层。Markdown 层提供可读、可审计、可人工修正的长期背景，vector 层负责按语义召回相关事实。对话后通过 consolidation 提取长期事实，先写入 PENDING.md 和 HISTORY.md，再由 memory optimizer 定期整理进 MEMORY.md，这样可以减少长期记忆污染，也避免频繁修改 system prompt 破坏 prompt cache。
```

如果面试官问“为什么不能只用 session history”，可以回答：

```text
Session history 适合短期上下文，但它太长、未结构化、容易超窗口，也不适合跨 session 复用。长期记忆需要被提取、压缩、结构化和检索，所以项目把最近对话和长期记忆分开管理。
```

如果面试官问“为什么要有 PENDING.md”，可以回答：

```text
如果每轮对话后都直接改 MEMORY.md，会导致长期记忆频繁变化，破坏 prompt cache，也容易把未经整理的信息污染稳定记忆。PENDING.md 是缓冲层，先暂存新提取的信息，再由 memory optimizer 批量整理进 MEMORY.md，兼顾性能和记忆质量。
```

### 4. Plugin System

可讲点：

- `PluginManager` 负责插件发现、加载、初始化和失败回滚。
- `PluginContext` 显式注入 runtime 能力。
- 插件可以注册工具、tool hook、phase module、EventBus handler 和 Dashboard 面板。
- Phase module 参与主链路，EventBus 更适合观测和副作用。

面试表达：

```text
这个项目的插件系统不是只做工具扩展，而是提供了完整的 runtime extension 机制。插件可以注册工具到 ToolRegistry，可以通过 ToolHook 横切工具执行流程，可以通过 lifecycle phase module 影响一轮对话的不同阶段，也可以通过 EventBus 做观测和副作用，甚至扩展 Dashboard。这样核心 AgentLoop 和 PassiveTurnPipeline 可以保持稳定，新增能力通过插件独立演进。
```

如果面试官问“插件和 toolset 有什么区别”，可以回答：

```text
toolset 更像启动时批量注册一组核心工具，偏系统内置能力；plugin 是完整的运行时扩展单元，不只可以注册工具，还能注册 hook、phase module、事件监听器和 Dashboard 面板。简单说，toolset 是工具分组，plugin 是扩展包。
```

如果面试官问“插件系统有什么风险”，可以回答：

```text
插件能力很强，风险是可能破坏主流程、注入不稳定 prompt、注册危险工具、和其他插件产生顺序冲突，甚至影响启动。这个项目通过 initialize 失败回滚、phase module 的 slot/requires/produces 拓扑排序、ToolHook 统一接入和 PluginContext 显式注入来控制风险。后续还可以加强权限声明、插件隔离、启用/禁用配置、版本管理和 sandbox。
```

### 5. Proactive Agent

可讲点：

- 主动触达不是定时群发，而是基于内容源、用户状态和规则判断。
- presence/cooldown/dedupe 降低打扰。
- drift 让 agent 空闲时执行后台任务。

面试表达：

```text
这个项目的 proactive 不是简单定时任务，而是一条主动 agent loop。它会定期感知内容源、session、presence 和 memory，通过 cooldown、dedupe、busy state 等 gate 避免打扰，再由 AgentTick/LLM 判断是否值得主动推送。如果不适合发消息，还可以进入 drift 执行后台任务。最终主动消息通过 TurnOrchestrator 统一写 session、发送、记录成功失败和更新 presence。
```

如果面试官问“为什么主动推送不能只是 cron”，可以回答：

```text
cron 只能按时间触发，但主动 agent 需要判断内容是否有价值、用户是否正在对话、是否刚推送过、是否重复、渠道是否允许、是否应该跳过或做后台任务。所以它需要 Sensor、presence、cooldown、dedupe、busy gate 和 AgentTick 的综合判断。
```

如果面试官问“drift 是什么”，可以回答：

```text
drift 是 agent 空闲时的后台自治任务。没有合适内容推送时，agent 不一定空转，可以执行记忆审计、用户画像补充、自我诊断或 SKILL.md 定义的长期任务。这样 proactive 系统不只是发消息，也能让 agent 在空闲时积累长期价值。
```

### 6. Channel / Communication

可讲点：

- Channel Adapter 把 CLI/Telegram/QQ/QQBot 外部协议统一成 `InboundMessage`。
- agent 回复统一成 `OutboundMessage`。
- `MessageBus` 解耦 channel 和 `AgentLoop`。
- `EventBus` 不负责用户通信，而负责生命周期事件和插件观察。
- CLI 是客户端，服务侧 `IPCServerChannel` 才负责转成内部消息。

面试表达：

```text
项目用 Channel Adapter + MessageBus 解耦外部协议和 agent core。不同平台的消息先被 adapter 转成统一 InboundMessage，AgentLoop 只消费内部消息；回复统一成 OutboundMessage，再由 MessageBus 分发给对应 channel callback。EventBus 不走用户通信，而是用于生命周期事件、插件和观测。这种设计让 CLI、Telegram、QQ、主动推送都能共享同一个 Agent Core。
```

如果面试官问“MessageBus 和 EventBus 有什么区别”，可以回答：

```text
MessageBus 是用户通信路径，处理 InboundMessage 和 OutboundMessage，负责 channel -> agent -> channel。EventBus 是内部生命周期事件路径，处理 TurnStarted、BeforeTurnCtx、ToolCallStarted、TurnCommitted 等事件，主要给插件、审计、日志和副作用使用。
```

如果面试官问“为什么 channel 不直接调用 AgentLoop”，可以回答：

```text
直接调用会让 channel 和 agent core 强耦合，也很难统一多渠道、异步缓冲、出站重试和降级。MessageBus 让 channel 只负责协议适配，AgentLoop 只负责消费内部消息，两边通过 InboundMessage/OutboundMessage 约定边界。
```

### 7. Dashboard / Observability

可讲点：

- Dashboard 不是普通 CRUD，而是 Agent observability console。
- 可以看 session、message、memory、proactive tick logs、plugin panels。
- 可以解释 agent 为什么回复、为什么主动推、为什么跳过。
- 支持手动 consolidation、memory optimize、删除错误数据等人工干预。

面试表达：

```text
这个项目的 Dashboard 不是普通后台 CRUD，而是 Agent observability console。因为 agent 的行为受 LLM、工具、记忆、插件和主动推送 gate 共同影响，最终回答本身不足以解释系统行为。Dashboard 通过 session/message、memory、proactive tick logs 和 plugin panels 展示 agent 看过什么、做过什么、记住了什么、为什么推送或跳过，并提供手动 consolidation、memory optimize 等干预入口。
```

如果面试官问“为什么 agent 需要 Dashboard”，可以回答：

```text
长期运行的 agent 会积累 session、message、memory、tool chain、plugin state 和 proactive decision。LLM 输出和工具调用路径都有不确定性，如果没有 Dashboard，就很难解释某次回复或主动推送的原因。Dashboard 可以降低黑盒程度，支持调试、审计、人工修正和运营。
```

如果面试官问“proactive tick log 有什么价值”，可以回答：

```text
主动推送的关键不只是发了什么，还包括为什么没发。tick log 可以记录 gate_exit、terminal_action、skip_reason、drift_entered、source refs 等信息，用来排查是 cooldown、dedupe、busy state，还是 LLM 判断 skip。这让主动行为可解释。
```

## 可能被问的问题

### 这个项目和普通聊天机器人有什么区别？

回答要点：

- 普通 bot 主要是 request-response。
- 这个项目有主动推送、长期记忆、工具系统、插件生命周期和 Dashboard 观测。
- 更接近 Agent Runtime，而不是单个聊天接口封装。

### 为什么需要 deferred tool search？

回答要点：

- 工具多时全量 schema 会占用大量上下文。
- 大量无关工具会干扰模型选择。
- deferred 工具通过搜索按需暴露，降低 token 成本和决策噪声。

### 为什么 memory 要分 markdown 和语义检索？

回答要点：

- markdown 层适合稳定、可读、可编辑的长期记忆。
- 语义层适合按 query 检索相关事实。
- 两者结合可以兼顾可控性和召回能力。

### 主动推送如何避免打扰用户？

回答要点：

- presence 记录用户状态。
- cooldown 和 dedupe 防止重复推送。
- energy 模型调节 tick 频率。
- proactive context 记录用户明确规则。

## 还需要准备的材料

- 一张架构图。
- 一个本地可运行 demo。
- 一次完整消息链路 trace。
- 一次记忆写入和检索 demo。
- 一次 proactive 推送 demo。

## 后续更新提示词

```text
请更新 my_md/06-interview-notes.md：把这次学习内容转化成面试表达，补充 30 秒介绍、3 分钟介绍、可讲亮点、难点和可能问题回答。
```
