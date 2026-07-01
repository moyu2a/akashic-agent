# 05 Proactive Agent

## 目标

记录主动推送链路。它是本项目区别于普通聊天机器人的核心亮点。

## 关键文件

- `bootstrap/proactive.py`
- `proactive_v2/loop.py`
- `proactive_v2/agent_tick_factory.py`
- `proactive_v2/sensor.py`
- `proactive_v2/energy.py`
- `proactive_v2/anyaction.py`
- `proactive_v2/state.py`
- `agent/turns/orchestrator.py`

## 设计层总结

主动推送系统解决的问题是：

```text
agent 如何在没有用户消息触发时，主动感知、判断、推送或跳过？
```

普通 bot 是：

```text
用户问 -> bot 答
```

这个项目希望做到：

```text
用户不问时，agent 也能根据上下文主动判断是否要联系用户。
```

主动推送可能来自：

- 订阅源有重要内容。
- 用户之前说过想关注某件事。
- 某个提醒到了。
- 近期状态需要 follow-up。
- 空闲时可以执行后台任务。

但主动推送不能只是定时任务，因为它必须避免打扰用户。

总体链路：

```text
ProactiveLoop
   |
   +--> 定期 tick
   |
   +--> Sensor 收集候选信息
   |       |
   |       +--> MCP/content feeds
   |       +--> session history
   |       +--> memory
   |       +--> presence
   |
   +--> Gate 判断
   |       |
   |       +--> passive busy?
   |       +--> cooldown?
   |       +--> duplicate?
   |       +--> user presence?
   |
   +--> LLM / AgentTick 判断
   |       |
   |       +--> reply
   |       +--> skip
   |       +--> drift
   |
   +--> TurnOrchestrator
           |
           +--> MessagePushTool
           +--> channel
```

### 为什么不是简单定时任务

简单定时推送：

```text
每隔 10 分钟发一次消息
```

会带来明显问题：

- 当前有没有值得说的内容不确定。
- 用户可能正在聊天。
- 用户可能刚刚被推送过。
- 内容可能重复。
- 渠道可能不允许主动推。
- 消息价值可能不够。

因此主动系统需要：

```text
定期感知 + 多层 gate + LLM 判断 + 统一发送编排
```

### ProactiveLoop

`ProactiveLoop` 是主动系统主循环。

它负责：

- 定期 tick。
- 轮询 feeds。
- 读取 `PROACTIVE_CONTEXT.md`。
- 管理 proactive state。
- 调用 `AgentTick`。
- 根据结果发送或跳过。

类比：

```text
AgentLoop:
  被用户消息触发

ProactiveLoop:
  被时间和外部信息源触发
```

### Sensor

`Sensor` 负责感知信息。

它收集：

- 内容源 / MCP feeds。
- 最近 session history。
- 用户 presence。
- 长期 memory。
- 上下文状态。
- 可能的设备/健康数据。

设计理解：

```text
Sensor 负责看世界
AgentTick 负责判断要不要说
```

### Presence

主动推送最怕打扰用户。

`PresenceStore` 用来记录：

- 用户最近有没有发消息。
- 刚刚是否已经推送过。
- 当前 session 是否正在处理被动消息。
- 用户是否处于活跃状态。

设计价值：

- 让主动行为考虑用户状态。
- 避免机械推送。

### Cooldown 和 Dedupe

主动推送需要两个基本保护：

```text
cooldown:
  刚发过就别再发

dedupe:
  同样内容别重复发
```

设计价值：

- 降低打扰。
- 避免重复。
- 提高主动消息质量。

### Energy Model

主动系统不是固定频率轮询，而是有节奏模型。

大致思路：

- 用户刚聊完，降低主动推送频率。
- 用户长时间没动静，可以更频繁检查。
- 有高价值内容，更可能触发。

设计价值：

- 主动触达节奏自适应。
- 避免过度打扰。

### AgentTick

`ProactiveLoop` 是常驻循环，`AgentTick` 是一次 tick 的执行器。

一次 tick 判断：

- 现在要不要做事。
- 要不要推送。
- 推送什么。
- 还是跳过。
- 还是进入 drift。

输出可以理解为：

```text
TurnResult
```

典型结果：

```text
reply:
  发送主动消息

skip:
  不发送，只记录原因或副作用

drift:
  没有合适推送时，执行后台任务
```

### Drift

如果没有内容值得推送，agent 不一定只能空转。

它可以进入 drift：

- 审计记忆。
- 补充用户画像。
- 检查长期任务。
- 做自我诊断。
- 执行 `SKILL.md` 定义的后台流程。

设计价值：

- agent 空闲时也能产生长期价值。
- 主动系统不只是推消息，也能驱动后台自治任务。

### PROACTIVE_CONTEXT.md

workspace 下会维护：

```text
~/.akashic/workspace/PROACTIVE_CONTEXT.md
```

它记录主动推送规则：

- 用户对主动推送的要求。
- 白名单。
- 黑名单。
- 过滤条件。
- 优先级。
- 必须验证的规则。

设计价值：

- 主动行为可控。
- 用户规则可以长期维护。
- agent 不只是凭一次 prompt 随机判断。

### TurnOrchestrator

主动推送最后也不能直接调用 channel send。

它通过：

```text
TurnOrchestrator
  -> MessagePushTool
  -> channel
```

统一处理：

- 写 session。
- 执行 side effects。
- 发送成功/失败处理。
- 更新 presence。
- 记录 trace。

设计价值：

- 主动消息也有完整生命周期。
- 不是裸发消息。

### 一句话总结

```text
主动推送系统通过 ProactiveLoop 定期 tick，由 Sensor 收集内容源、用户状态和记忆上下文，再经过 busy/cooldown/dedupe/presence 等 gate 和 AgentTick 判断，决定 reply、skip 或 drift；最终通过 TurnOrchestrator 和 MessagePushTool 统一发送和记录，从而让 agent 从被动问答变成能主动触达和后台自治的长期运行系统。
```

## 启动条件

主动链路由 `build_proactive_runtime()` 构建。

如果：

```toml
[proactive]
enabled = false
```

则主动链路不会启动。

## 总体流程

```text
ProactiveLoop.run()
  -> 定期 poll feeds
  -> 计算下一次 tick 间隔
  -> AgentTick 执行单次判断
  -> 生成 TurnResult
  -> TurnOrchestrator.handle_proactive_turn()
  -> MessagePushTool 发送
```

## ProactiveLoop 主要依赖

- `SessionManager`: 读取用户历史和 session 状态。
- `LLMProvider`: 判断是否应该主动发消息。
- `MessagePushTool`: 实际推送消息。
- `ProactiveStateStore`: 记录 seen items、deliveries、tick logs。
- `PresenceStore`: 记录用户最近交互和主动推送状态。
- `MemoryRuntime`: 提供长期记忆上下文。
- `ToolRegistry`: 复用部分工具。
- `ToolHook`: 主动链路也可以走工具 hook。

## PROACTIVE_CONTEXT.md

workspace 下会维护：

```text
~/.akashic/workspace/PROACTIVE_CONTEXT.md
```

它用于记录主动推送规则，例如：

- 白名单/黑名单
- 过滤条件
- 优先级
- 需要先验证的步骤

当前理解：这是 proactive agent 每轮都会读取的规则面板。

## 推送或跳过

`TurnResult` 可能是：

- `reply`: 发送主动消息。
- `skip`: 不发送，只执行副作用。

`TurnOrchestrator` 会负责：

- 写入 proactive session。
- 发送前 side effects。
- 发送成功/失败 side effects。
- 更新 presence。

## 需要继续理解的问题

- `energy.py` 如何计算轮询间隔。
- `Sensor` 如何合并 alert/content/context 三类数据。
- `AgentTickFactory` 具体组装了哪些 gate。
- drift 空闲任务如何被触发。
- dedupe 和 cooldown 如何防止重复打扰。

## 后续更新提示词

```text
请更新 my_md/05-proactive-agent.md：把这次学习到的 proactive tick、数据源、gate、推送/跳过逻辑和源码路径补充进去。
```
