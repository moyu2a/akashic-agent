# 07 Module Interview QA

这个文档记录模块设计学习阶段的模拟面试问答。

规则：

- 每次只记录一个问题。
- 问题类型包括：是什么、为什么这么用、有没有更好的方法、为什么不用其他方法。
- 每个回答尽量按“定义 -> 设计原因 -> 替代方案 -> 取舍/改进”组织。
- 每新增 3 个问题，更新一次下面的“全局摘要索引”。
- 对各个模块进行深挖，不能只做泛泛总结；每个关键模块都要尽量追到核心对象、调用链、输入输出、边界条件、失败场景、替代方案和改进点，确保对项目有完整、确切的理解。
- 后续每个新增问题在原有回答基础上，增加一段 STAR 法则思考：Situation 情景、Task 任务、Action 行动、Result 结果，用于把模块设计理解转化为面试项目表达。
- 后续“面试总结”部分尽量少堆具体函数名，优先改成中文职责描述；函数名只在必须精准定位代码或表达关键边界时保留。

## 全局摘要索引

### 当前统计

- 当前已记录问题数：90 个。
- 当前阶段重点：面试项目表达已覆盖 STAR 总体叙事、技术亮点与业务价值、chatbot 质疑回应、技术债识别和产品化路线图；当前文档已经从代码流程学习推进到完整 Agent Runtime 面试表达阶段。
- 后续出题原则：问题要尽量覆盖完整 Agent Runtime，而不是只围绕 memory；每个新问题继续包含“是什么 / 为什么 / 取舍 / 改进点”。对每个关键模块都要继续深挖到核心对象、调用链、输入输出、边界条件和失败场景，并补充 STAR 法则思考，方便转换成面试项目表达。
- 最近新增问题：Q88-Q90，覆盖普通 chatbot 质疑回应、项目技术债和改进方向、下一阶段产品化路线图。
- 索引更新规则：以后每新增 3 个问题更新一次本节，记录新增问题范围、模块覆盖变化和下一组建议问题。

### 模块覆盖地图

| 模块方向 | 已覆盖问题 | 当前覆盖程度 |
| --- | --- | --- |
| Runtime / AgentLoop / 架构模式 | Q1-Q3, Q12, Q18, Q28, Q51-Q52 | 已覆盖主链路、事件驱动、Provider 抽象、lifecycle 拆分、phase module 机制和多 Provider 适配 |
| Context / Prompt / Prompt Cache | Q5-Q6, Q17, Q31-Q34 | 已覆盖上下文组织、system prompt、prompt block、cache 稳定性 |
| Memory / RAG / Retrieval | Q4, Q7-Q9, Q20, Q29-Q30, Q35-Q48 | 已深挖，覆盖存储、写入、纠错、召回、注入、query rewrite、HyDE |
| Tool System / Tool Governance | Q10, Q16, Q21, Q23, Q49-Q50, Q67-Q69 | 已覆盖工具注册、工具循环、安全边界、tool_search、MCP 接入、外部 schema 适配、ToolExecutor/ToolHook 和外部工具降级 |
| Plugin System / Extension | Q11, Q22, Q50-Q51 | 已覆盖插件加载、工具注册、hook、lifecycle/event 扩展、phase module 介入方式 |
| Session / Channel / Scope | Q19, Q26-Q27, Q53 | 已覆盖 channel/session 抽象、工具可见性隔离、memory scope、message id/source_ref 原文追溯 |
| Proactive / Scheduler | Q13-Q14, Q25, Q55-Q60 | 已覆盖主动推送、scheduler 边界，并深挖 tick/gate/dedupe、兴趣判断、presence、ACK、drift 和失败处理 |
| Subagent / Background Job | Q24, Q62-Q66 | 已覆盖 background job/subagent 分层、spawn 创建、运行中管理、取消、完成回灌、权限隔离、失败恢复、超时边界和持久化状态设计 |
| MCP / 外部能力接入 | Q49, Q67-Q69 | 已覆盖 MCP 作为外部能力来源的连接、工具发现、wrapper 适配、schema 进入统一工具系统、tool_search 可见性和失败降级 |
| Peer Agent / 外部 Agent | Q70 | 已覆盖 peer agent 编排、权限边界、最小上下文、结果可信度、artifact 校验和主 Agent 最终解释权 |
| 测试与评估 | Q71-Q75 | 已覆盖被动对话测试分层、fake provider/fake tool、工具循环错误和终止条件、memory retrieval 评估、Proactive v2 测试矩阵、插件加载和副作用治理 |
| Observability / Dashboard | Q15, Q54 | 已覆盖必要性、turn trace、rag query trace、memory write trace、异步写入和诊断面板 |
| 原始消息证据链 | Q40-Q41 | 已覆盖 recall/search/fetch 分工和 citation 证据链 |
| 部署 / 配置 / 运行环境 | Q76-Q80 | 已覆盖 config.toml 分层、强类型配置、bootstrap wiring、workspace 初始化、运行状态落点、channel adapter、Dashboard 部署保护、长期服务运维 |
| 安全 / 回滚 / 副作用治理 | Q81-Q85 | 已覆盖撤回/删除/纠错的数据一致性、长期记忆 supersede 与物理删除边界、工具副作用补偿、高风险工具权限/确认/审计、插件和工具异常隔离 |
| 面试项目表达 | Q86-Q90 | 已覆盖 STAR 总体叙事、项目定位、核心技术亮点、业务价值映射、chatbot 质疑回应、技术债表达和产品化路线图 |

### 已形成的核心理解

1. 这个项目不是单纯 chatbot，而是一个事件驱动的 Agent Runtime。
2. 被动对话主链路通过 `MessageBus -> AgentLoop -> PassiveTurnPipeline -> Reasoner -> ToolRuntime` 串起来。
3. 内部副作用和插件扩展通过 `EventBus`、lifecycle phase、tool hook 解耦。
4. memory 是多层系统：session history、markdown memory、memory2.db、consolidation、optimizer、retrieval injection 共同工作。
5. retrieval 不是简单向量库：包含 query rewrite、vector lane、keyword lane、RRF、hotness、injection selection、procedure guard、HyDE。
6. 工具系统不是把所有工具塞进 prompt，而是通过注册、tool_search、可见性隔离、hook、安全策略和 runtime 执行控制来治理。
7. session/channel/scope 是多端 Agent 的基础，否则 CLI、Telegram、QQ、proactive、memory 会互相污染。
8. MCP 工具通过 wrapper 适配成标准 Tool，外部能力进入统一 ToolRegistry 后复用 tool_search、ToolExecutor 和风险治理。
9. lifecycle phase 不是简单回调列表，而是带 slot/requires 的模块化执行链，适合把 session/context/prompt/tool loop/after-turn 副作用拆到明确阶段。
10. Provider 抽象把模型供应商差异、stream/non-stream、tool_calls、thinking、cache usage 和错误分类收敛到统一 `LLMResponse`。
11. `source_ref` 把长期记忆摘要和原始 session message 连接起来，让 memory recall 可以回到原文证据。
12. observe/recall_inspector 把 turn、retrieval、memory write 和 recall 过程记录下来，让 Agent 行为可解释、可调试、可复盘。
13. Proactive v2 不是简单定时推送，而是由后台 tick、pre-gate、兴趣判断、最近对话、去重、ACK 和发送编排共同组成的主动决策链路。
14. presence 不是“在线状态”这么简单，而是用用户最后发言和主动消息最后发送时间来控制 tick 节奏、行动概率、疲劳和打扰判断。
15. ACK 是主动内容源的处理反馈，不同结果要使用不同冷却策略，避免重复候选和误丢未发送内容。
16. Drift 是没有外部候选时的空闲自主模式，通过 skill、工作区状态和发送限制约束 Agent 的自主行为。
17. 主动发送失败时，系统不会把引用内容标记为成功处理，也不会更新最后主动发送时间；但当前实现存在“先落 session 后发送”的残余改进点。
18. Background job 管任务生命周期，subagent 管具体执行，spawn 是主 Agent 派生同步或后台子任务的工具入口。
19. 后台子任务完成后不会直接把原始结果发给用户，而是通过内部事件回到原会话，由主 Agent 重新组织用户可见回复。
20. 子 Agent 权限按 profile 分层，默认只读调研；执行型任务写入独立任务目录，不能默认继承主 Agent 全部工具。
21. 后台任务当前能把完成、不完整、错误和取消转成用户可见反馈，但完整的生产级恢复还需要持久化任务状态、心跳、超时、幂等通知和重启恢复。
22. MCP server 被当作外部能力来源，通过 stdio 子进程和 JSON-RPC 连接，远端工具会被包装成项目标准 Tool 后进入统一工具系统。
23. 外部工具 schema 需要经过适配层转成统一 function schema，不能让模型直接处理 MCP 协议、命名冲突、风险等级和错误格式。
24. MCP 当前具备基础降级能力：连接失败不阻塞启动，调用错误进入工具结果，proactive 单源失败不拖垮其他来源；但还需要健康检查、熔断、退避重试和 pending ack。
25. 外部 Agent / peer agent 应被视为独立执行者，不能默认继承主 Agent 权限；当前项目通过异步任务、poller 回灌和主 Agent 总结来保持用户交互边界。
26. 被动对话测试应以 fake provider 和 fake tool 固定模型/工具行为，重点验证 session、retrieval、tool_chain、TurnCommitted 和 outbound 等工程契约。
27. 工具循环测试要覆盖 success、error、blocked、denied、tool_search unlock、max_iterations、early_stop、tool_loop 和消息链闭合。
28. memory retrieval 评估不能只看有没有命中，要同时看候选召回、排序质量、最终注入、回答提升和 session/channel 隔离。
29. Proactive v2 测试的核心是副作用治理：不该发时不能发送，该发时只发一次，发送成功后才记录投递、更新 presence 和执行长期 ACK。
30. 插件系统测试要围绕扩展边界和失败隔离：插件能注册工具、hook 和生命周期模块，但失败时必须可回滚、可观测、不能拖垮主链路。
31. 配置系统按 llm、agent、channels、memory、proactive、integrations 分层，加载后转成强类型对象，再由 bootstrap 组装运行时依赖。
32. workspace 是运行时数据边界，会话、记忆、主动状态、观测数据、调度任务和插件状态都应落在 workspace，而不是散落在代码目录。
33. 多渠道 adapter 通过统一 InboundMessage / OutboundMessage 接入 MessageBus，让 CLI、Telegram、QQ、QQBot 共享同一套 AgentLoop、memory、tools 和 proactive 逻辑。
34. Dashboard 是高权限运行时后台，能查看和修改 session、message、memory、proactive 和插件状态，部署时必须本地绑定或加认证保护。
35. 长期运行 Agent 服务需要进程守护、优雅退出、日志治理、workspace 备份、SQLite/WAL 备份意识、升级回滚和外部依赖健康检查。
36. 插件和工具是高风险扩展点，需要把失败控制在扩展边界内；安全类失败倾向阻断，观察类失败可以降级。
37. 这个项目适合作为 Agent 应用求职项目，因为它展示的是可长期运行的 Agent Runtime，而不是一次 API 调用 Demo。
38. 面试表达不能只堆功能点，要把运行时架构、记忆、工具、主动链路、插件和可观测性分别映射到业务价值。
39. 撤回、删除和纠错不能简单全删：session 负责对话记录，memory 负责未来推理使用，observe 负责审计证据，应分别处理。
40. 长期记忆需要 active/superseded 状态和替换关系；业务语义变化优先 supersede，隐私和合规删除才适合物理删除。
41. 工具副作用治理要覆盖调用前权限和幂等、调用中超时和错误收敛、调用后审计和补偿，不能把外部操作当普通函数。
42. 高风险工具需要风险分级、默认不可见、执行前确认、执行后审计；现有 risk、tool hook、shell safety/restore 是基础，但还缺统一确认和 audit log。
43. 面对“套壳聊天机器人”的质疑，要从长期状态、工具治理、主动触达、插件扩展和可观测性解释差异。
44. 技术债表达要主动承认从“能跑”到“稳定长期服务”的差距，重点放在测试评估、安全治理、主动链路状态机、记忆质量和部署运维。
45. 产品化路线图应先补可靠性和可验证性，再做用户可控记忆、权限治理、多渠道体验、插件生态和部署运维。

### 下一阶段建议问题池

后续问题应优先覆盖这些还不够深入的模块：

- Undo / 回滚：用户撤回、插件副作用、memory 写入如何回滚或失效？
- 部署与配置：配置加载、workspace 初始化、Docker、channel adapter、dashboard 启动如何协作？
- 运行治理：长期运行时如何做进程管理、日志、备份、升级和恢复？
- 安全与权限：高风险工具、插件权限、外部副作用如何确认、审计和补偿？
- 面试表达：把项目亮点、技术债、路线图整理成 STAR 项目故事。

### 最近新增问题

- Q88：如何回应“这只是套壳聊天机器人”的质疑。
- Q89：当前最大技术债和改进方向是什么，如何体现工程取舍。
- Q90：如果继续产品化，下一阶段路线图应该怎么排。

### 下次索引更新时间

- 当前最新问题：Q90。
- 下次应在继续新增 3 个正式问题后更新本索引。

## Q1: `MessageBus` 和 `EventBus` 分别是什么？为什么项目里要同时有这两个 bus？

### 标准答案

`MessageBus` 是用户通信路径，负责 channel 和 agent 之间的业务消息流转。外部渠道把消息转换成 `InboundMessage` 后放进 `MessageBus` 的 inbound queue，`AgentLoop` 消费后生成 `OutboundMessage`，再通过 outbound queue 分发回对应 channel。

`EventBus` 是内部生命周期事件路径，负责插件、观测、审计和副作用。它处理的是 `TurnStarted`、`BeforeTurnCtx`、`ToolCallStarted`、`TurnCommitted` 这类运行时事件，不负责把用户消息发给 agent，也不负责把回复发回用户。

项目同时保留两个 bus，是为了分离两类完全不同的流：

```text
MessageBus:
  用户通信路径
  channel -> agent -> channel

EventBus:
  内部生命周期路径
  pipeline/plugin/observer/side effects
```

如果只用一个 bus，用户消息、agent 回复、插件事件、工具事件和审计事件都会混在一起，边界会变得很乱。这样既增加理解成本，也容易让插件误影响用户通信主链路。

更好的替代方案不是“合并两个 bus”，而是继续强化边界，例如：

- 给事件类型加更严格的 schema。
- 给 `EventBus` 增加事件分类和订阅权限。
- 对高风险 side effect 做隔离和失败降级。

所以当前设计是合理的：`MessageBus` 保证用户通信主链路清晰，`EventBus` 提供插件和生命周期扩展能力。

## Q2: 这个项目的 agent 设计模式是什么？有没有用到什么 agent 框架？

### 标准答案

这个项目没有明显使用 LangChain、AutoGen、CrewAI 这类现成 agent 框架，而是自己实现了一套 Agent Runtime。它底层调用的是 OpenAI 兼容 Chat Completions API，但 agent 的主循环、工具系统、记忆系统、插件系统、主动推送和 Dashboard 都是项目内自己组织的。

它的设计模式可以概括为：

```text
事件驱动的 Agent Runtime
  + ReAct / tool-use 风格推理循环
  + lifecycle pipeline
  + ports/adapters 通信适配
  + plugin architecture
  + memory-augmented agent
  + proactive agent loop
```

分开解释：

1. **事件驱动架构**

   外部消息先进入 channel adapter，再变成 `InboundMessage` 放入 `MessageBus`，由 `AgentLoop` 消费。内部生命周期事件、插件观察和副作用走 `EventBus`。

2. **ReAct / tool-use 风格**

   模型不是只生成一次回答，而是可以在推理过程中调用工具、读取工具结果、继续推理，直到形成最终回复。这和 ReAct 思路接近，但不是直接使用某个 ReAct 框架。

3. **Lifecycle Pipeline**

   一轮被动对话被拆成 `BeforeTurn`、`BeforeReasoning`、`PromptRender`、`Reasoner`、`AfterReasoning`、`AfterTurn` 等阶段。这样记忆、工具、插件和后处理都有明确挂载点。

4. **Ports / Adapters**

   CLI、Telegram、QQ、QQBot 等外部渠道通过 channel adapter 转成统一 `InboundMessage` / `OutboundMessage`。Agent Core 不关心外部协议细节。

5. **Plugin Architecture**

   插件可以注册工具、挂 tool hook、注入 lifecycle phase module、监听 EventBus、扩展 Dashboard，从而在不改主链路的情况下扩展 agent 能力。

6. **Memory-Augmented Agent**

   它不是只依赖上下文窗口，而是把 session history、markdown memory、semantic/vector memory、consolidation、memory optimizer 组合起来，让 agent 有长期记忆能力。

7. **Proactive Agent Loop**

   除了被动问答，还有 `ProactiveLoop` 定期感知内容源、presence、memory 和 session 状态，判断是否主动推送、跳过或进入 drift 后台任务。

如果面试中被问“有没有用 agent 框架”，可以回答：

```text
没有直接套用 LangChain 或 AutoGen 这类 agent 框架。这个项目更像自研 Agent Runtime：LLM provider 只负责调用 OpenAI 兼容模型，agent 的消息循环、工具运行时、记忆、插件、主动推送和可观测性都是项目自己实现的。这样复杂度更高，但可控性更强，也更适合展示 Agent Infra 设计能力。
```

这个设计的优点是可控性强、扩展点清晰、适合长期运行的 agent 服务；缺点是自研 runtime 成本高，需要自己处理工具治理、状态管理、错误处理、观测、插件安全和长期维护。

## Q3: 这个 AgentLoop 中有哪些状态？

### 标准答案

`AgentLoop` 里的状态可以分成两类：一类是运行时依赖和配置，另一类是真正会随对话变化的运行状态。面试时重点讲后者。

核心运行状态包括：

```text
_running
_processing_state
_active_tasks
_active_turn_states
_interrupt_states
_tool_discovery
stream partial state
session state
```

### 1. `_running`: loop 是否继续运行

`_running` 是 AgentLoop 主循环开关。

```text
True:
  AgentLoop 持续从 MessageBus 消费 inbound 消息

False:
  loop 停止
```

它解决的是主循环生命周期控制问题。

### 2. `_processing_state`: 当前 session 是否 busy

`_processing_state` 记录某个 session 是否正在处理消息。

在 `_process()` 开始时：

```text
processing_state.enter(session_key)
```

结束时：

```text
processing_state.exit(session_key)
```

它的价值是让其他模块知道“这个会话正在被动处理”。例如 proactive 系统可以据此避免在用户当前对话处理中插入主动消息。

### 3. `_active_tasks`: 当前正在跑的 turn task

`_active_tasks` 是：

```text
session_key -> asyncio.Task
```

每当 AgentLoop 从 `MessageBus` 收到一条消息，会创建一个 task 执行 `_process(item)`，并挂到 `_active_tasks`。

它的作用：

- 记录当前哪些 session 正在处理。
- `/stop` 中断时可以找到对应 task 并 cancel。
- turn 结束后清理。

### 4. `_active_turn_states`: 当前 turn 的临时状态

`_active_turn_states` 是：

```text
session_key -> TurnInterruptState
```

虽然名字里有 interrupt，但它在正常运行时也保存当前 turn 的临时快照，例如：

- 原始用户消息。
- partial reply。
- partial thinking。
- 已使用工具。
- 当前工具链片段。

它的作用：

- 支持流式输出时累积 partial reply / thinking。
- 支持 `/stop` 时保存当前进度。
- 支持中断后续跑。

### 5. `_interrupt_states`: 被中断 turn 的快照

`_interrupt_states` 也是：

```text
session_key -> TurnInterruptState
```

区别是：`_active_turn_states` 表示“正在跑的 turn”，`_interrupt_states` 表示“已经被 /stop 中断、等待用户继续补充的 turn”。

它保存：

- 原始用户消息。
- 已经输出的 partial reply。
- 已经输出的 thinking。
- 已经使用的工具。
- 被谁中断。
- 中断时间。
- TTL。

下一次用户发消息时，`AgentLoop` 会检查 `_interrupt_states`，如果没有过期，就把上一轮进度和新消息拼接成恢复上下文。

### 6. `_tool_discovery`: 本轮或运行期工具发现状态

`_tool_discovery` 和 `tool_search_enabled` 相关，用来管理 deferred tool 的发现和可见性。

它的意义是：

- 不把所有工具一次性暴露给模型。
- 允许模型通过 `tool_search` 按需发现工具。
- 配合 Reasoner 管理当前可见工具集合。

### 7. stream partial state: 流式输出中的局部状态

AgentLoop 配置了 stream sink。模型流式输出时，会把：

- `content_delta`
- `thinking_delta`

追加到当前 session 的 `TurnInterruptState`：

```text
partial_reply
partial_thinking
```

这样即使用户中途 `/stop`，系统也知道已经输出了什么，后续可以续跑。

### 8. session state: 持久化会话状态

严格来说，session 不完全属于 `AgentLoop` 自己的内存状态，而是由 `SessionManager` 管理。但 AgentLoop 会通过 `session_services` 使用它。

session 保存：

- 历史消息。
- metadata。
- last_consolidated。
- proactive 标记。
- 工具链和额外信息。

它和 `_active_turn_states` 的区别：

```text
session:
  持久化状态，跨 turn 保存

active_turn_state:
  当前 turn 的临时内存态，turn 结束后清理
```

### 面试总结

可以这样回答：

```text
AgentLoop 的状态主要分成运行控制、任务控制、中断控制、busy 状态和会话状态几类。_running 控制主循环是否运行；_processing_state 标记 session 是否 busy，供 proactive 避免打扰；_active_tasks 记录当前正在执行的 turn task，支持 /stop 取消；_active_turn_states 保存当前 turn 的 partial reply、thinking、工具链等临时状态；_interrupt_states 保存被中断 turn 的快照，用于下一轮续跑；session state 则由 SessionManager 持久化保存历史消息和 metadata。这些状态共同让 AgentLoop 不只是消费消息，还能处理中断、流式输出、主动推送避让和多 session 管理。
```

### 为什么这样设计

如果没有这些状态，AgentLoop 只能做最简单的：

```text
取消息 -> 调模型 -> 返回
```

但真实 agent 需要：

- 多 session 并发管理。
- 中途停止。
- 停止后续跑。
- 流式 partial 保存。
- 主动推送避让。
- 工具调用过程记录。

所以这些状态是为了让被动对话从“单次函数调用”变成“可控的长期运行 turn 生命周期”。

## Q4: 当前系统是否具有 RAG？

### 标准答案

有，但它不是传统意义上“上传一批文档，然后做文档问答”的简单 RAG；更准确地说，它是一个 **memory-augmented agent**，内部包含 retrieval-augmented context 的能力。

也就是说，这个系统有 RAG 的核心链路：

```text
用户问题
  -> 构造检索请求
  -> 从长期记忆 / 语义记忆中召回相关内容
  -> 生成 retrieved_memory_block
  -> 注入 prompt
  -> LLM 基于检索上下文回答
```

项目中相关模块包括：

```text
agent/retrieval/default_pipeline.py
core/memory/runtime.py
memory2/retriever.py
memory2/query_rewriter.py
memory2/hyde_enhancer.py
plugins/default_memory/*
```

### 它和普通 RAG 的区别

普通 RAG 通常是：

```text
文档库
  -> chunk
  -> embedding
  -> vector search
  -> 把相关 chunk 塞进 prompt
  -> 回答问题
```

这个项目的 retrieval 更偏 agent memory：

```text
session history
markdown memory
semantic/vector memory
profile / facts / history
consolidation 后的长期记忆
```

它检索的不是单纯文档，而是 agent 运行过程中沉淀下来的用户偏好、历史事件、近期上下文和长期记忆。

### 是否一定启用

要注意：语义检索能力依赖配置。

如果：

```toml
[memory]
enabled = true
```

并且配置了 embedding / memory engine，那么系统会启用更完整的语义记忆检索。

如果 memory engine 没开启，系统仍可能有 markdown memory 上下文注入，但语义向量召回能力会受限。

### 面试回答

可以这样说：

```text
这个系统有 RAG 能力，但它不是传统文档 QA 型 RAG，而是面向 Agent 长期记忆的 retrieval-augmented context。每轮对话前会基于用户消息和 session history 构造检索请求，从 markdown memory 和 semantic/vector memory 中召回相关记忆，形成 retrieved_memory_block 注入 prompt。对话后又通过 consolidation 把新信息沉淀进长期记忆。也就是说，它把 RAG 和长期记忆系统结合在一起，用于持续对话和个性化上下文，而不只是检索静态文档。
```

### 有没有更好的方法

可以改进的方向包括：

- 增加更明确的 citation / source attribution，让回答能引用具体记忆来源。
- 对不同记忆类型分层召回，例如 profile、event、preference、task 分开检索。
- 对 retrieval 做质量评估，记录命中率、使用率和幻觉率。
- 引入 reranker，提高召回内容的排序质量。
- 给 Dashboard 增加每轮 RAG trace，展示 query、召回片段、注入内容和最终使用情况。

所以结论是：

```text
有 RAG，但它是 agent memory RAG，不只是普通文档 RAG。
```

## Q5: 这个项目的上下文工程是怎么组织的？

### 标准答案

这个项目的上下文工程不是简单拼一个 prompt，而是把 system prompt、session history、长期记忆、检索记忆、技能、工具、插件注入、当前消息和媒体能力组织成一套分层上下文。

可以概括为：

```text
ContextStore 准备上下文
  -> ContextBundle
  -> ContextBuilder 构建系统块
  -> PromptAssembler 组装 system prompt + context frame + history + 当前消息
  -> Reasoner 调用 LLM / tool loop
```

### 1. 输入来源

上下文来源主要有：

```text
系统身份和行为规则
session history
长期 markdown memory
semantic/vector retrieved memory
recent context
self model / user profile
skills catalog
active skills
tool visibility / tool_search 结果
plugin prompt injection
当前用户消息
当前消息时间
media / image refs
channel-specific rendering policy
```

这说明它的上下文工程不只是“历史消息 + 当前问题”，而是 agent runtime 的多个子系统共同参与。

### 2. ContextStore: 准备 turn 级上下文

`DefaultContextStore.prepare()` 负责在一轮对话开始前准备上下文 bundle。

它大致做：

```text
读取 session history
  -> 转成 history_messages
  -> 调 memory retrieval pipeline
  -> 得到 retrieved_memory_block
  -> 收集 skill mentions
  -> 输出 ContextBundle
```

`ContextBundle` 是 BeforeTurn / BeforeReasoning 之间传递上下文的结构化载体。

### 3. ContextBuilder: 构建系统上下文块

`ContextBuilder` 负责构建系统 prompt 的各个 block。

典型 block 包括：

```text
IdentityPromptBlock
BehaviorRulesPromptBlock
MemoryBlockPromptBlock
LongTermMemoryPromptBlock
SelfModelPromptBlock
RecentContextPromptBlock
SessionContextPromptBlock
ActiveSkillsPromptBlock
SkillsCatalogPromptBlock
```

这些 block 把不同类型的上下文分区管理，而不是混成一大段文本。

设计价值：

- 上下文来源清晰。
- 哪块可以裁剪、哪块应稳定更容易控制。
- 插件和后续优化更容易插入。

### 4. PromptAssembler: 统一组装 prompt

`PromptAssembler` 负责把系统块和 turn 级上下文组装成最终 LLM messages。

它做了一个很重要的区分：

```text
system sections:
  放进 system prompt

context frame sections:
  放进一个 system-reminder 风格的 user message
```

context frame 中包含：

```text
active_skills
recent_context
retrieved_memory
turn_injection_context
```

这种设计的目的是告诉模型：

```text
这些是系统提供的候选上下文，不是用户原话，也不是助手结论。
```

从而减少模型把检索结果、记忆或插件注入内容误当成用户陈述。

### 5. MessageEnvelopeBuilder: 控制消息顺序

最终 LLM messages 的顺序是有意设计的：

```text
system prompt
  -> history
  -> context frame
  -> current user message
```

这个顺序很重要：

- stable system prompt 放最前面。
- session history 保留对话连续性。
- context frame 在当前消息前提供候选上下文。
- 当前用户消息放最后，保证模型聚焦当前请求。

### 6. 当前消息时间和媒体处理

当前用户消息会被加时间信封：

```text
[当前消息时间: ...]
用户原文
```

这样模型回答时知道当前消息发生时间。

媒体处理也有分支：

- 如果主模型支持 multimodal，图片可以作为 image_url / base64 传入。
- 如果主模型不支持图片但配置了 VL 工具，会在文本中提示调用 `read_image_vision`。
- 如果没有 VL 能力，则说明当前无法直接读图。

这属于上下文工程的一部分，因为它决定模型如何理解当前消息中的非文本输入。

### 7. 工具上下文

工具不是都直接塞进 prompt。

项目通过：

```text
always_on tools
deferred tools
tool_search
turn injection hint
```

控制模型当前能看到哪些工具。

这也是上下文工程：工具 schema 本身会占上下文，也会影响模型行为。

### 8. 插件上下文

插件可以在多个生命周期阶段注入上下文：

- `BeforeTurn` 可以导出 extra hints。
- `BeforeReasoning` 可以增加 hints 或 abort。
- `PromptRender` 可以注入 prompt section。
- `BeforeStep` / `AfterStep` 可以影响工具循环过程。

这让上下文工程具备扩展性，但也带来风险：插件注入内容可能污染 prompt，所以需要 phase、slot 和事件边界。

### 9. Context Trim Plan: 上下文裁剪

项目有默认裁剪计划：

```text
full
trim_skills_catalog
trim_memes
trim_long_term_memory
trim_retrieved_memory
```

当上下文过长时，可以逐步丢弃低优先级 section。

设计价值：

- 不是粗暴截断整个 prompt。
- 可以按语义块降级。
- 优先保留更关键的系统身份、当前消息和核心上下文。

### 10. 面试总结

可以这样回答：

```text
这个项目的上下文工程是分层组织的，不是简单字符串拼接。每轮对话先由 ContextStore 准备 session history、memory retrieval 和 skill mentions，形成 ContextBundle；再由 ContextBuilder 按 prompt block 构建 identity、behavior rules、long-term memory、self model、recent context、active skills、skills catalog 等系统上下文；PromptAssembler 再把 system sections、context frame、history 和当前用户消息按固定顺序组装成 LLM messages。工具可见性、插件注入、媒体处理、当前时间、context trim plan 都属于上下文工程的一部分。
```

### 为什么这样设计

如果只是简单把所有东西拼成一个 prompt，会有几个问题：

- 不知道哪些内容来自用户，哪些来自系统。
- 记忆、工具、插件注入容易混在一起。
- 上下文过长时只能粗暴截断。
- 插件很难安全扩展 prompt。
- prompt cache 容易被高频变化内容破坏。

当前设计通过 block、context frame、trim plan 和 stable/dynamic section 区分，让上下文更可控、可裁剪、可扩展，也更适合长期运行的 agent。

### 可以改进的地方

- 在 Dashboard 中展示每轮最终 prompt breakdown。
- 记录每个 context section 的来源、token、是否被裁剪。
- 对 retrieved memory 增加 citation/source id。
- 对插件注入内容做权限和长度限制。
- 引入更强的 rerank / context selection 策略，减少无关记忆注入。

## Q6: 系统提示词是怎么设计的？

### 标准答案

这个项目的系统提示词不是一整段硬编码文本，而是 **Prompt Block 分层组装** 的。

它把系统提示词拆成多个有职责边界的 block，每个 block 有：

```text
priority
label
is_static
render()
cache_signature()
```

再由 `SystemPromptBuilder` 按 priority 升序渲染和拼接。

### 1. Prompt Block 结构

核心 block 包括：

```text
IdentityPromptBlock
BehaviorRulesPromptBlock
SkillsCatalogPromptBlock
SelfModelPromptBlock
LongTermMemoryPromptBlock
SessionContextPromptBlock
RecentContextPromptBlock
ActiveSkillsPromptBlock
MemoryBlockPromptBlock
```

这些 block 不是随便拼的，而是按稳定程度和语义职责分层。

### 2. 组装顺序

大致顺序是：

```text
10 IdentityPromptBlock
15 BehaviorRulesPromptBlock
20 SkillsCatalogPromptBlock
30 SelfModelPromptBlock
35 LongTermMemoryPromptBlock
40 SessionContextPromptBlock
45 RecentContextPromptBlock
50 ActiveSkillsPromptBlock
55 MemoryBlockPromptBlock
```

这个顺序体现了一个原则：

```text
稳定身份和行为规范在前
长期背景在中间
当前 session / recent context / active skill / retrieved memory 在后
```

也就是说，越稳定、越全局的内容越靠前；越动态、越本轮相关的内容越靠后。

### 3. 各 block 的职责

#### IdentityPromptBlock

负责 agent 身份、性格、workspace 路径、长期记忆文件位置等。

它定义：

- agent 是谁。
- 工作区在哪里。
- 长期记忆、自我认知、历史日志、近期语境和 proactive 规则面板在哪里。

这是最稳定的一层。

#### BehaviorRulesPromptBlock

负责行为规范。

包括：

- 工具与事实规则。
- 时间处理规则。
- 输出格式。
- 工具路由和 skill 使用。
- spawn 判断。
- proactive / drift 资产说明。
- 记忆纠错协议。
- 历史检索协议。

这是系统提示词中最核心的“行为宪法”。

#### SkillsCatalogPromptBlock

负责告诉模型有哪些 skills，以及命中 skill 时必须先读取 `SKILL.md`。

设计目的是：

- 让 agent 能按任务加载技能。
- 避免模型凭印象执行技能。

#### SelfModelPromptBlock

来自 `SELF.md`。

负责 agent 自我认知、用户画像或偏好类长期信息。

#### LongTermMemoryPromptBlock

来自 `MEMORY.md` / memory context。

负责长期稳定记忆。

#### SessionContextPromptBlock

负责当前环境和 session 信息，例如：

- machine architecture
- channel
- chat_id

#### RecentContextPromptBlock

来自 `RECENT_CONTEXT.md`。

负责近期上下文摘要，但会避免直接重复 recent turns，减少和滑动窗口重叠。

#### ActiveSkillsPromptBlock

负责本轮 active skills。

它会加载 always skills 和本轮命中的 skill 内容。

#### MemoryBlockPromptBlock

负责本轮语义检索出来的 `retrieved_memory_block`。

这是最高频变化的部分。

### 4. Static / Dynamic 区分

block 有 `is_static`。

静态 block 例如：

```text
identity
behavior_rules
skills_catalog
```

这些通常只有 workspace、代码或 skill 文件变化时才变。

动态 block 例如：

```text
self_model
long_term_memory
session_context
recent_context
active_skills
retrieved_memory
```

这些可能随记忆、session 或本轮 retrieval 变化。

设计价值：

- 稳定 prompt 便于缓存。
- 动态上下文可以独立变化。
- prompt cache 更容易命中。
- 上下文裁剪更可控。

### 5. Behavior Rules 的设计重点

`BehaviorRulesPromptBlock` 很重，因为它定义了 agent 的关键行为边界。

重要规则包括：

```text
执行类动作必须走工具
外部事实必须查工具，不能只靠记忆
相对时间要换算成绝对时间
输出要简洁、中文口语、不要 emoji
工具不可见时先 tool_search
命中 skill 时必须 read_file 读取 SKILL.md
用户纠正记忆时必须走记忆纠错协议
历史问题必须 recall/search/fetch 原文
proactive 规则要写 PROACTIVE_CONTEXT.md
```

这些规则的作用是降低 LLM 常见问题：

- 编造已完成动作。
- 把历史数据当当前事实。
- 乱用相对时间。
- 口吻过度安慰或跑题。
- 不按工具协议执行。
- 记忆纠错只口头承认但不实际修正。

### 6. System Prompt 和 Context Frame 的区别

不是所有上下文都塞进 system prompt。

PromptAssembler 会把部分高动态内容放进 context frame，例如：

```text
active_skills
recent_context
retrieved_memory
turn_injection_context
```

context frame 会作为一个 system-reminder 风格的 user message 注入，并明确告诉模型：

```text
这些内容由系统提供，不是用户陈述，也不是助手结论。
```

设计价值：

- 避免模型把检索记忆误认为用户本轮说的话。
- 区分稳定系统规则和本轮候选上下文。
- 减少高频变动内容污染 system prompt。

### 7. 裁剪策略

系统提示词和上下文可能过长，所以项目定义了 trim plan：

```text
full
trim_skills_catalog
trim_memes
trim_long_term_memory
trim_retrieved_memory
```

这说明裁剪不是直接截断字符串，而是按 section 降级。

设计价值：

- 优先保留核心行为规则。
- 先丢低优先级或可恢复内容。
- 避免破坏当前用户消息和关键系统约束。

### 面试总结

可以这样回答：

```text
这个项目的系统提示词是 block 化设计的，不是一整段硬编码 prompt。它通过 SystemPromptBuilder 按 priority 组装 Identity、BehaviorRules、SkillsCatalog、SelfModel、LongTermMemory、SessionContext、RecentContext、ActiveSkills 和 RetrievedMemory 等 block。稳定内容和动态内容分开，静态 block 支持缓存，动态 block 可以按轮变化；高频变化的 recent context、retrieved memory、active skills 等还会进入 context frame，而不是全部污染 system prompt。这样设计能让身份、行为规范、长期记忆、技能和本轮检索上下文边界清楚，也便于裁剪、缓存和插件扩展。
```

### 为什么这样设计

如果系统提示词只是一个大字符串，会有几个问题：

- 难以维护和测试。
- 不清楚哪些内容稳定、哪些内容动态。
- prompt cache 容易被高频变化内容破坏。
- 上下文过长时只能粗暴截断。
- 插件和 skills 很难安全注入。
- 记忆、检索结果、当前 session 信息容易混在一起。

block 化设计让系统提示词变成可组合、可裁剪、可缓存、可观测的结构。

### 可以改进的地方

- Dashboard 展示每轮 system prompt breakdown。
- 标出每个 block 的 token 数和是否命中缓存。
- 给高风险规则做自动测试，例如“外部事实必须查工具”“记忆纠错必须 forget/memorize”。
- 对插件注入的 prompt section 增加权限、长度和优先级限制。
- 把行为规范拆成更细粒度策略模块，便于按 channel 或场景启用。

## Q7: memory 存储采用的什么策略？比如滑动窗口、摘要压缩等等？

这个项目的 memory 不是单一策略，而是 **多层记忆策略**：

```text
短期会话窗口
  + RECENT_CONTEXT 摘要压缩
  + MEMORY / SELF 长期稳定记忆
  + PENDING 待归档缓冲
  + HISTORY 时间线日志
  + memory2.db 语义向量检索
```

所以它既用了滑动窗口，也用了摘要压缩，还用了长期记忆文件和向量数据库。

### 1. 短期上下文：滑动窗口

配置里有 `memory_window`，运行时会转成 `keep_count`。

它的作用是保留最近一段 session history，让模型能看到最新对话。

窗口之外的旧消息不会一直塞进 prompt，而是进入 consolidation 流程。

大致逻辑是：

```text
session.messages 太长
  -> 保留最近 keep_count 条
  -> 更旧的消息进入 consolidation window
  -> 提取成 HISTORY / PENDING / RECENT_CONTEXT / vector memory
```

默认配置示例里 `memory_window = 40`，测试里可以看到会对齐成 `keep_count = 20`。

这说明它不是无限保留原始聊天记录，而是用窗口控制 prompt 长度。

### 2. 近期语境：摘要压缩

项目会维护 `RECENT_CONTEXT.md`。

它里面主要包括：

```text
## Compression
## Ongoing Threads
## Recent Turns
```

其中 `Compression` 和 `Ongoing Threads` 是对近期上下文的压缩摘要，会进入 system prompt。

但 `Recent Turns` 在注入 prompt 时会被裁掉，因为它和 session sliding window 有重叠。

也就是说：

```text
滑动窗口负责原始近期对话
RECENT_CONTEXT.md 负责压缩后的近期主题
```

这两个不是重复设计，而是分别解决“细节”和“概览”。

### 3. 长期稳定记忆：MEMORY.md / SELF.md

`MEMORY.md` 负责长期稳定事实，例如用户偏好、身份信息、长期目标。

`SELF.md` 负责 agent 对自身、用户关系、工作方式的长期认知。

这两个文件会作为长期记忆注入 system prompt。

所以它们必须保持紧凑，不能每轮都随便追加大量内容。

### 4. 待归档缓冲：PENDING.md

旧消息经过 consolidation 后，不会直接高频改 `MEMORY.md`，而是先写入 `PENDING.md`。

原因是 `MEMORY.md` 会全文进入 system prompt。如果每轮都改，会破坏 prompt cache，让每轮推理成本和延迟变高。

所以项目用了一个缓冲层：

```text
consolidation 高频发生
  -> 新事实先写 PENDING.md

optimizer 低频运行
  -> 读取 MEMORY.md + PENDING.md
  -> 决定合并、修正、忽略
  -> 一次性更新 MEMORY.md
  -> 清空 PENDING.md
```

默认 optimizer 间隔大约是 3 小时。

这是一个比较工程化的设计：牺牲一点实时长期记忆更新，换取 prompt cache 稳定和长期记忆质量。

### 5. 时间线日志：HISTORY.md / journal

`HISTORY.md` 是追加式事件日志。

它记录“发生过什么”，更像 timeline，而不是最终用户画像。

它的价值是：

- 保留历史事件证据。
- 给后续 consolidation 提供上下文。
- 可以被 grep 或检索流程使用。
- 不像 `MEMORY.md` 那样必须保持高度浓缩。

项目还会维护 daily journal，适合按日期回看事件。

### 6. 语义记忆：memory2.db 向量数据库

除了 markdown 文件层，项目还有 `memory2.db`。

这是向量语义记忆层，用于：

- 保存 consolidation 产出的记忆项。
- embedding 后做语义召回。
- 支持 `memorize` / `forget_memory` 等工具写入和删除。
- 每轮对话前生成 `retrieved_memory_block` 注入上下文。

所以这个项目的记忆不是只靠 prompt 里的 markdown，也不是只靠向量库，而是两层并存：

```text
Markdown 层：人能读、能编辑、能审计
Vector 层：机器能搜、能召回、能排序
```

### 7. 幂等和可靠性策略

memory 写入还做了可靠性保护：

- consolidation 用 `source_ref` 标记来源消息。
- `HISTORY.md` 和 `PENDING.md` 有隐藏 marker 防止重复写。
- `consolidation_writes.db` 记录已提交窗口。
- `PENDING.md` 有 snapshot / commit / rollback，避免 optimizer 崩溃导致数据丢失。

这说明它把 memory 当成持久化数据系统处理，而不是简单往文本文件末尾追加。

### 面试总结

可以这样回答：

```text
这个项目的 memory 采用多层策略，不是单纯滑动窗口。短期上下文用 memory_window / keep_count 保留最近 session history；窗口外的旧消息进入 consolidation，被提取到 HISTORY.md、PENDING.md、RECENT_CONTEXT.md 和 memory2.db。RECENT_CONTEXT.md 做近期摘要压缩，MEMORY.md / SELF.md 保存长期稳定记忆，PENDING.md 作为待归档缓冲，由 optimizer 低频合并进 MEMORY.md，以保护 prompt cache。memory2.db 则负责语义向量检索，每轮生成 retrieved_memory_block 注入 prompt。所以它是 sliding window + summary compression + long-term markdown memory + vector retrieval 的组合架构。
```

### 为什么这么设计

如果只用滑动窗口，历史信息出了窗口就丢了。

如果只用摘要压缩，细节和证据容易损失。

如果只用向量数据库，人类不容易审计和手动修正。

如果每轮直接更新 `MEMORY.md`，prompt cache 会频繁失效。

所以这个项目拆成多层：

- 最近内容看原文。
- 近期主题看摘要。
- 稳定事实进长期记忆。
- 新事实先进入待归档缓冲。
- 细节召回交给向量库。
- 历史证据放到时间线日志。

### 可以改进的地方

- 给每条 retrieved memory 增加更清晰的来源引用。
- 在 Dashboard 展示每层 memory 的 token 占用和命中情况。
- 对不同 memory 类型设置不同保留策略，例如 profile、preference、event、task 分开管理。
- consolidation 阈值可以更自适应，根据 token 压力、会话密度和用户活跃度动态调整。
- 增加 memory 质量评估，例如重复率、过期率、召回命中率和错误记忆修正率。

## Q8: 为什么这个项目同时使用 Markdown 记忆文件和 memory2.db 向量数据库？只用一种不行吗？

不建议只用一种。

这个项目把 memory 分成两层：

```text
Markdown 文件层：MEMORY.md / SELF.md / HISTORY.md / RECENT_CONTEXT.md / PENDING.md
向量数据库层：memory2.db
```

它们解决的问题不一样。

### Markdown 层解决什么问题

Markdown 层偏“可读、可控、可审计”。

例如：

- `MEMORY.md`：长期稳定记忆。
- `SELF.md`：agent 的自我认知和工作方式。
- `RECENT_CONTEXT.md`：近期上下文摘要。
- `HISTORY.md`：追加式历史事件日志。
- `PENDING.md`：待归档事实缓冲区。

这些文件的优势是人可以直接打开看、手动改、审计错误记忆。

这对 agent 应用很重要，因为长期记忆一旦写错，会持续影响后续回答。

### 向量库层解决什么问题

`memory2.db` 偏“语义检索和规模化召回”。

它适合处理：

- 历史细节太多，不能全部塞进 prompt。
- 用户当前问题和旧记忆不是关键词完全匹配，但语义相关。
- 需要按相关性召回几条最有用的 memory item。
- 工具调用可以 `memorize` / `forget_memory` 精确增删记忆。

也就是说，向量库负责“找得到”，Markdown 负责“看得懂、管得住”。

### 为什么只用 Markdown 不够

只用 Markdown 会遇到几个问题：

- 文件越写越长，不能全部注入 prompt。
- 靠关键词 grep 召回不够稳定。
- 相似语义但不同表达的内容可能找不到。
- 很难做 ranking、去重、embedding 检索和 memory item 级管理。

所以 Markdown 适合作为长期可读记忆，但不适合作为唯一检索系统。

### 为什么只用向量库也不够

只用向量库也有问题：

- 人类不容易审计里面到底记了什么。
- 错误记忆修正成本更高。
- 缺少一个稳定的长期画像文件。
- 不方便把核心长期记忆作为 system prompt 的稳定部分。
- 记忆来源、归档状态和历史时间线不够直观。

Agent 的长期记忆不只是“能搜到”，还要“能维护、能解释、能纠错”。

### 面试总结

可以这样回答：

```text
这个项目同时使用 Markdown 和向量库，是因为两者职责不同。Markdown 层负责可读、可审计、可手动维护的长期记忆，例如 MEMORY.md、SELF.md、HISTORY.md、RECENT_CONTEXT.md 和 PENDING.md；向量库 memory2.db 负责语义检索、相关性排序和 memory item 级别的增删改。只用 Markdown 会导致检索能力弱、文件膨胀；只用向量库又会降低可解释性和可维护性。所以这个项目采用双层记忆架构：Markdown 做稳定认知和人工可控的事实面板，向量库做动态召回和细节检索。
```

### 可以改进的地方

- 给 Markdown 记忆和向量记忆建立更明确的双向引用。
- 在 Dashboard 里展示某条 retrieved memory 来自哪个 Markdown / consolidation source。
- 给 `MEMORY.md` 中的长期事实加版本、来源和最后确认时间。
- 对向量库召回结果增加 rerank 和冲突检测。
- 当用户修正记忆时，同时展示 Markdown 层和 vector 层会如何被更新。

## Q9: 这个项目里的 consolidation 是什么？为什么不能直接把每轮对话都写进长期记忆？

`consolidation` 可以理解为“记忆整理/归档流程”。

它不是简单把聊天记录原样保存，而是把窗口外的旧对话提取成更适合长期保存和检索的结构化记忆。

大致流程是：

```text
一轮对话结束
  -> 检查 session.messages 是否超过保留窗口
  -> 选出窗口外、尚未整理的一段旧消息
  -> 调 LLM 做记忆提取
  -> 写入 HISTORY.md
  -> 写入 PENDING.md
  -> 更新 RECENT_CONTEXT.md
  -> 通过事件同步到 memory2.db
```

### 它整理的是什么

consolidation 主要把原始聊天转成几类信息：

- 历史事件：写入 `HISTORY.md`。
- 待归档长期事实：写入 `PENDING.md`。
- 近期主题摘要：写入 `RECENT_CONTEXT.md`。
- 可检索语义记忆：写入 `memory2.db`。

也就是说，它把“聊天记录”变成“可长期使用的 agent memory”。

### 为什么不每轮都直接写 MEMORY.md

原因有四个。

第一，很多对话内容不值得进入长期记忆。  
例如临时问题、寒暄、一次性命令，如果都写入 `MEMORY.md`，长期记忆会很快变脏。

第二，直接写长期记忆容易重复和冲突。  
同一个偏好可能被多次表达，也可能后来被纠正，需要归并和判断，而不是简单追加。

第三，`MEMORY.md` 会进入 system prompt。  
如果每轮都修改它，会破坏 prompt cache，增加延迟和成本。

第四，原始聊天不等于可用记忆。  
长期记忆需要抽象、压缩、分类、去重和纠错。

### PENDING.md 的意义

`PENDING.md` 是 consolidation 和长期记忆之间的缓冲区。

它先接收“可能值得长期保存”的候选事实。

后续 optimizer 再低频读取：

```text
MEMORY.md + PENDING.md
  -> LLM 判断哪些要合并
  -> 哪些要忽略
  -> 哪些是修正
  -> 最后更新 MEMORY.md
```

这样可以避免长期记忆被高频、低质量地污染。

### 面试总结

可以这样回答：

```text
consolidation 是这个项目的记忆整理流程。它在对话结束后检查 session history，把滑动窗口之外、尚未整理的旧消息交给 LLM 提取，生成 HISTORY.md 的时间线事件、PENDING.md 的待归档事实、RECENT_CONTEXT.md 的近期摘要，并同步到 memory2.db 做语义检索。它不直接每轮写 MEMORY.md，是为了避免长期记忆污染、重复冲突、prompt cache 失效，以及把原始聊天和稳定记忆混在一起。PENDING.md 起到缓冲作用，optimizer 再低频把候选事实合并进 MEMORY.md。
```

### 可以改进的地方

- 给 consolidation 提取结果增加置信度。
- 对不同类型信息设置不同归档规则，例如偏好、身份、任务、事件分开处理。
- 在 Dashboard 展示每次 consolidation 的输入窗口、输出结果和是否写入成功。
- 对 PENDING 候选增加人工确认模式，避免敏感或错误事实自动进入长期记忆。
- 增加 memory regression test，验证某类对话是否会被正确归档或忽略。

## Q10: 这个项目的工具系统是怎么设计的？为什么工具不直接写死在 AgentLoop 里？

这个项目的工具系统是插件化、注册式的设计。

AgentLoop 本身不应该知道所有工具细节，而是通过工具注册表、插件和运行时来管理工具。

可以理解为：

```text
插件 / 内置模块
  -> 注册 tool schema 和 handler
  -> Agent 构建可用工具列表
  -> LLM 决定是否 tool call
  -> ToolRuntime 执行工具
  -> 工具结果回到下一轮 reasoning
```

### 工具系统解决什么问题

LLM 本身只能生成文本。

但 agent 应用需要做很多外部动作，例如：

- 查询记忆。
- 写入记忆。
- 删除错误记忆。
- 调用外部 MCP 数据源。
- 执行插件提供的能力。
- 查询状态、撤销操作、检查上下文。

这些都不应该让模型“凭空回答”，而应该通过工具完成。

### 为什么不写死在 AgentLoop

如果工具直接写死在 AgentLoop，会有几个问题：

- AgentLoop 会越来越臃肿。
- 新增工具必须改核心代码。
- 插件无法灵活扩展工具。
- 不同 channel / session / skill 下难以动态控制工具可见性。
- 工具权限、拦截、观测和测试都会混在主流程里。

所以项目把工具能力拆出去，让 AgentLoop 只负责“调用流程”，工具系统负责“有哪些工具、怎么执行”。

### 工具调用的大致流程

一次工具调用可以这样理解：

```text
用户输入
  -> BeforeTurn / BeforeReasoning 准备上下文
  -> PromptRender 暴露可用 tools
  -> Reasoner 调 LLM
  -> LLM 返回 tool_calls
  -> ToolRuntime 执行对应 handler
  -> 工具结果追加到消息历史
  -> LLM 基于工具结果继续回答
```

这就是典型的 tool-using agent loop。

### 插件和工具的关系

插件可以注册工具。

这意味着工具能力不是固定的，而是可以由插件扩展。

例如 memory 插件可以提供：

```text
memorize
forget_memory
recall_memory
```

其他插件也可以注册自己的工具。

这样项目的扩展方式更像 agent runtime，而不是一个固定聊天机器人。

### 为什么这是求职项目亮点

因为它展示了 agent infra 的关键设计：

- 工具 schema 和执行逻辑分离。
- 核心 loop 和具体工具解耦。
- 插件可以动态扩展工具。
- 工具结果进入对话上下文，支持多步推理。
- 可以围绕工具做权限、拦截、日志和测试。

这比“写几个函数让 LLM 调”更接近真实工程里的 agent 平台设计。

### 面试总结

可以这样回答：

```text
这个项目的工具系统不是写死在 AgentLoop 里的，而是注册式和插件化设计。插件或内置模块负责注册 tool schema 和 handler，Agent 在 prompt render 阶段暴露当前可用工具，LLM 返回 tool_calls 后由 ToolRuntime 执行对应 handler，再把工具结果放回消息历史让模型继续推理。这样设计可以让核心 AgentLoop 保持稳定，把工具扩展、权限控制、拦截、观测和测试都放到工具/插件层处理，更适合做可扩展的 agent runtime。
```

### 可以改进的地方

- 给工具增加更明确的权限模型，例如 read/write/destructive 分类。
- Dashboard 展示每次 tool call 的参数、耗时、结果和失败原因。
- 对高风险工具增加二次确认或人工审批。
- 给工具 schema 做自动测试，避免参数描述和 handler 行为不一致。
- 增加工具选择评估，统计模型什么时候该调用工具却没调用，或者错误调用工具。

## Q11: 这个项目的插件系统解决了什么问题？为什么不把所有能力都放进核心代码？

插件系统解决的是 agent runtime 的可扩展性问题。

这个项目里，核心 AgentLoop 只负责主流程：

```text
接收消息
  -> 准备上下文
  -> 渲染 prompt
  -> 调模型
  -> 执行工具
  -> 提交结果
  -> 触发后处理
```

但很多能力不是核心 loop 自身的一部分，例如：

- memory 工具。
- undo 命令。
- status 命令。
- dashboard 面板。
- recall inspector。
- memory rollup。
- proactive / drift 相关扩展。
- lifecycle hook 中的上下文增强和后处理。

这些能力如果都写进核心代码，AgentLoop 会变成一个很难维护的大文件。

### 插件可以介入哪些地方

插件不是只能注册工具，它还可以介入生命周期。

典型介入方式包括：

```text
注册 tools
监听 EventBus 事件
实现 lifecycle phase module
拦截 tool call
提供 Dashboard 面板
提供配置和后台任务
```

这说明插件系统不仅是“函数扩展”，而是 runtime 级扩展。

### 为什么这比简单函数调用更重要

Agent 应用不是一次性脚本。

真实项目里经常需要：

- 增加一种新工具。
- 增加一种新 memory 策略。
- 在推理前注入上下文。
- 在回复后做审计和归档。
- 给 Dashboard 增加观测页面。
- 针对某些工具做权限或拦截。

如果没有插件系统，每次扩展都要改核心 loop，回归风险会很高。

插件系统让核心流程稳定，扩展能力外置。

### 插件系统和 EventBus / MessageBus 的关系

插件常常通过事件介入系统。

例如某个事件发生后：

```text
TurnCommitted
ConsolidationCommitted
ToolCalled
PromptRendered
```

插件可以订阅这些事件，执行自己的逻辑。

这使得核心模块不需要显式调用每个插件。

核心只发事件，插件自己响应。

这就是解耦。

### 面试总结

可以这样回答：

```text
这个项目的插件系统是为了让 Agent Runtime 可扩展。核心 AgentLoop 只保留接收消息、准备上下文、渲染 prompt、调用模型、执行工具和提交结果这些主流程；memory、status、undo、dashboard、recall inspector、memory rollup 等能力通过插件扩展。插件可以注册工具、监听事件、介入 lifecycle phase、拦截工具调用、提供 Dashboard 面板和后台任务。这样核心 loop 不需要知道所有扩展细节，新增能力也不需要频繁改核心代码，系统更容易维护和测试。
```

### 为什么这样设计

如果没有插件系统，会有几个问题：

- 核心代码膨胀。
- 新增能力要频繁改 AgentLoop。
- memory、tools、dashboard、proactive 等模块边界变混乱。
- 不同功能之间耦合变重。
- 测试和回归成本升高。

插件系统把“稳定主流程”和“可变扩展能力”分开，是 agent runtime 工程化的重要体现。

### 可以改进的地方

- 给插件增加更严格的权限声明，例如可读记忆、可写记忆、可注册工具、可发消息。
- Dashboard 展示每个插件注册了哪些 hook、tools 和事件监听器。
- 插件加载失败时提供隔离策略，避免一个插件拖垮主 agent。
- 对插件执行耗时做 tracing，定位慢插件。
- 增加插件依赖和版本约束，避免扩展之间隐式冲突。

## Q12: 这个项目为什么要把一次对话拆成多个 lifecycle phase？直接一个函数从输入跑到输出不行吗？

把一次对话拆成多个 lifecycle phase，是为了让 agent 主流程可插拔、可观测、可测试。

如果直接写成一个大函数：

```text
收到用户消息
  -> 拼 prompt
  -> 调 LLM
  -> 执行工具
  -> 返回结果
```

短期能跑，但后面要加 memory、plugin、tool intercept、dashboard、retry、安全检查、consolidation 时，就会不断往这个大函数里塞逻辑。

这个项目选择把一轮对话拆成阶段：

```text
BeforeTurn
  -> BeforeReasoning
  -> PromptRender
  -> Reasoner
  -> AfterReasoning
  -> AfterTurn
  -> TurnCommitted
```

每个阶段有明确职责。

### 每个阶段大概负责什么

`BeforeTurn`：准备本轮输入、session、上下文 bundle、初始 memory retrieval。

`BeforeReasoning`：在正式推理前做进一步上下文处理，插件可以在这里调整信息。

`PromptRender`：把 system prompt、context frame、history、tools 等渲染成模型输入。

`Reasoner`：调用 LLM，处理模型输出、tool call、多轮工具执行。

`AfterReasoning`：模型推理完成后做结果检查、插件后处理、可能的修正。

`AfterTurn`：提交前的收尾阶段，比如准备事件、状态更新、观测数据。

`TurnCommitted`：一轮真正落盘或提交后触发，memory consolidation 这类后处理可以在这里接上。

### 为什么这对插件很重要

插件需要明确知道自己应该在哪个时机介入。

例如：

- memory retrieval 应该发生在推理前。
- prompt 注入应该发生在 prompt render 前后。
- 工具拦截应该发生在 tool call 执行前。
- consolidation 应该发生在 turn committed 之后。
- dashboard tracing 应该贯穿整个生命周期。

如果没有阶段划分，插件只能侵入主流程，系统会变得很难维护。

### 为什么这对测试和观测很重要

阶段化之后，每个 phase 都可以单独测试。

例如：

- 测 `BeforeTurn` 是否正确生成 retrieved memory。
- 测 `PromptRender` 是否正确组装 prompt。
- 测 `Reasoner` 是否正确处理 tool call。
- 测 `AfterTurn` 是否触发正确事件。

Dashboard 也可以按阶段展示耗时、输入、输出和错误。

这对 agent 应用很关键，因为 agent 的问题经常不是“代码崩了”，而是“上下文不对、工具没暴露、记忆召回错了、模型没按预期调用工具”。

### 面试总结

可以这样回答：

```text
这个项目把一次对话拆成多个 lifecycle phase，是为了让 agent 主流程可插拔、可观测、可测试。BeforeTurn 负责准备 session 和上下文，BeforeReasoning 负责推理前增强，PromptRender 负责组装模型输入，Reasoner 负责 LLM 和工具调用，AfterReasoning / AfterTurn 负责后处理和状态更新，TurnCommitted 之后可以触发 memory consolidation。这样插件可以在明确阶段介入，而不是侵入一个巨大的 AgentLoop 函数，也方便测试每个阶段和在 Dashboard 里观察每轮执行过程。
```

### 可以改进的地方

- 给每个 phase 输出标准 trace，方便排查上下文问题。
- Dashboard 展示每个 phase 的耗时、输入摘要、输出摘要和插件修改点。
- 对 phase module 增加更严格的依赖声明和执行顺序校验。
- 给关键 phase 增加 contract test，防止插件破坏上下文结构。
- 当某个 phase 失败时支持局部降级，而不是整轮对话直接失败。

## Q13: 这个项目里的被动 Agent 和主动 Agent 有什么区别？为什么需要 ProactiveLoop？

被动 Agent 是“用户触发”的。

主动 Agent 是“系统定时触发”的。

可以这样区分：

```text
Passive AgentLoop
  用户发消息
  -> agent 理解问题
  -> 检索记忆
  -> 调工具
  -> 回复用户

ProactiveLoop
  系统定时轮询
  -> 拉取 alert / content / context
  -> 判断是否值得打扰用户
  -> 主动推送或跳过
  -> 空闲时执行 drift 后台任务
```

### 被动 Agent 解决什么问题

被动 Agent 负责正常问答。

典型流程是：

- 用户通过 CLI / channel 发来消息。
- 系统准备 session history、memory、tools、prompt。
- LLM 推理并可能调用工具。
- 最后返回回复。

它适合处理明确的用户请求。

### 主动 Agent 解决什么问题

主动 Agent 负责“用户没问，但系统可能应该提醒”的场景。

例如：

- 外部数据源出现高优先级 alert。
- 某个内容流出现值得推送的信息。
- 用户长时间没交互，但系统可以根据上下文做轻量判断。
- 没有可推送内容时，执行 drift 后台任务，例如整理记忆、自检、补充用户画像。

这让 agent 更像一个持续运行的助手，而不是一次性聊天接口。

### 为什么不能只靠被动问答

如果只有被动问答，agent 永远等用户输入。

但很多 assistant 场景需要主动性：

- 提醒用户重要变化。
- 在后台整理信息。
- 根据上下文判断是否打扰。
- 把系统从“聊天工具”升级为“持续陪伴/持续工作”的 agent。

所以 `ProactiveLoop` 是为了让系统具备主动感知和主动行动能力。

### 主动推送为什么要有“是否打扰”的判断

主动 Agent 最大的风险是打扰用户。

所以它不是拿到内容就推送，而是要判断：

- 内容是否重要。
- 是否和用户当前上下文相关。
- 最近是否刚打扰过用户。
- 用户 presence / 活跃状态如何。
- 推送收益是否大于干扰成本。

这就是主动 agent 和普通定时任务的区别。

普通定时任务是“到点执行”。

主动 agent 是“感知上下文后决定是否行动”。

### Drift 后台任务的意义

如果没有值得推送的内容，系统也不一定空转。

它可以进入 drift：

```text
没有 alert / content 可推送
  -> 执行后台 skill
  -> 做记忆审计、自检、整理等低优先级任务
```

这让 agent 在空闲时也能产生维护价值。

### 面试总结

可以这样回答：

```text
这个项目里 Passive AgentLoop 是用户触发的对话主循环，负责接收用户消息、准备上下文、检索记忆、调用工具并回复。ProactiveLoop 是系统定时触发的主动循环，会拉取 alert、content、context 等外部信号，再结合用户状态和上下文判断是否主动推送。如果没有值得推送的内容，还可以进入 drift 执行后台任务。这样系统不只是被动 chatbot，而是具备持续感知、主动判断和后台维护能力的 agent。
```

### 可以改进的地方

- 给主动推送增加更透明的打扰预算，例如每日最多推送次数。
- 让用户可以配置哪些主题允许主动提醒。
- Dashboard 展示每次 proactive 决策为什么推送或为什么跳过。
- 对主动推送做反馈学习，例如用户忽略、点击、回复后调整策略。
- 给 drift 任务增加优先级队列和执行结果审计。

## Q14: 主动推送系统最难的点是什么？为什么不是拿到新内容就直接推给用户？

主动推送最难的点不是“能不能推”，而是“什么时候不该推”。

如果 agent 一看到新内容就推送，会很快变成噪音系统。

所以主动推送需要做决策：

```text
新内容出现
  -> 判断重要性
  -> 判断和用户是否相关
  -> 判断当前是否适合打扰
  -> 判断近期是否已经推送过
  -> 决定推送 / 跳过 / 延后 / 进入 drift
```

### 为什么不能直接推送

原因有几个。

第一，内容新不等于重要。  
很多内容只是更新了，但对用户没有实际价值。

第二，内容重要不等于和用户相关。  
主动 agent 应该结合用户偏好、当前任务和近期上下文判断。

第三，相关也不等于现在该打扰。  
如果用户刚刚交互完、正在忙、或者短时间内已经收到很多推送，就应该克制。

第四，频繁错误推送会损害信任。  
用户会觉得 agent 很吵，最后关闭主动能力。

### 主动推送和普通通知系统的区别

普通通知系统通常是规则触发：

```text
出现事件
  -> 满足规则
  -> 发送通知
```

主动 agent 更像是上下文决策：

```text
出现事件
  -> 理解内容
  -> 结合用户状态和记忆
  -> 判断价值和打扰成本
  -> 决定是否行动
```

所以它不只是 notification，而是 context-aware decision。

### 项目里的主动推送思路

这个项目的 proactive 设计大致是：

- 拉取 `alert`：高优先级内容，优先处理。
- 拉取 `content`：内容流，需要评分和筛选。
- 拉取 `context`：背景上下文，可作为 fallback。
- 结合 presence / session / memory 判断是否推送。
- 没有合适内容时进入 drift 后台任务。

这说明主动推送不是盲目发送，而是有筛选和跳过机制。

### 面试总结

可以这样回答：

```text
主动推送最难的不是推送能力，而是打扰控制。新内容不一定重要，重要内容也不一定和用户相关，相关内容也不一定适合现在推。所以这个项目的 ProactiveLoop 会拉取 alert、content、context 等信号，再结合用户状态、近期上下文和记忆做决策，决定推送、跳过或进入 drift。它和普通通知系统的区别在于，普通通知是规则触发，主动 agent 是上下文感知后的行动决策。
```

### 可以改进的地方

- 增加用户级打扰预算，例如每小时、每天最多主动推送多少次。
- 让用户显式配置主动推送主题和静默时间。
- 对跳过原因做结构化记录，方便调试 proactive 策略。
- 引入用户反馈信号，例如忽略、点击、回复、关闭通知。
- 对不同类型推送设置信心阈值和冷却时间。

## Q15: 为什么 Agent 应用需要 Dashboard 和可观测性？只看日志不行吗？

Agent 应用很需要 Dashboard 和可观测性，因为它的问题往往不是普通程序里的“报错崩溃”，而是“决策过程不符合预期”。

例如：

- 为什么这轮没有调用工具？
- 为什么召回了这条 memory？
- 为什么系统提示词里缺了某个 block？
- 为什么主动推送选择跳过？
- 为什么模型用了错误上下文回答？
- 为什么某个插件修改了上下文？

这些问题只靠普通日志很难快速定位。

### Agent 的问题为什么更难排查

传统后端系统通常是确定性流程：

```text
输入
  -> 业务逻辑
  -> 数据库
  -> 输出
```

Agent 系统里多了很多不确定因素：

```text
用户输入
  -> memory retrieval
  -> prompt assembly
  -> tool selection
  -> LLM reasoning
  -> plugin hooks
  -> post processing
  -> memory consolidation
```

其中任何一个环节出问题，最终回答都会变差。

所以不能只看最终回复，还要看中间过程。

### Dashboard 应该看什么

一个合格的 Agent Dashboard 应该能看：

- 当前 session history。
- system prompt breakdown。
- context frame 注入了什么。
- retrieved memory 有哪些。
- tools 暴露了哪些。
- tool calls 的参数、结果、耗时。
- lifecycle phase 的执行顺序和耗时。
- plugin hook 做了哪些修改。
- proactive 推送为什么发送或跳过。
- consolidation 写入了哪些 memory。

这些信息能帮助开发者判断 agent 的行为是不是符合设计。

### 为什么日志不够

日志当然有用，但日志通常是线性的、碎片化的。

Agent 调试需要把一轮对话的上下文串起来看：

```text
这一轮用户说了什么
  -> 系统注入了什么上下文
  -> 模型看到了什么 prompt
  -> 模型为什么调用这个工具
  -> 工具返回了什么
  -> 最终回答如何生成
  -> 后续写入了什么 memory
```

Dashboard 更适合做这种“按 turn 聚合”的观察。

### 面试总结

可以这样回答：

```text
Agent 应用需要 Dashboard 和可观测性，因为很多问题不是代码异常，而是决策链路异常。比如 memory 召回不准、prompt block 缺失、工具没有暴露、LLM 没有调用工具、插件修改了上下文、proactive 错误跳过等。只看日志通常太碎片，Dashboard 可以按一轮 turn 聚合展示 session、prompt breakdown、retrieved memory、tool calls、lifecycle phase、plugin hooks 和 memory 写入，让开发者能解释 agent 为什么这么做。这对调试和面试展示都很重要。
```

### 可以改进的地方

- 每轮对话生成完整 trace id，串起 prompt、tool、memory、plugin、LLM 调用。
- Dashboard 增加 prompt diff，比较两轮上下文变化。
- 展示每个 prompt block 的 token 数、来源和裁剪状态。
- 对 tool call 和 memory retrieval 增加失败原因分类。
- 支持从 Dashboard 回放某一轮 turn，复现模型输入和工具结果。

## Q16: 工具调用为什么需要边界控制？如何避免 Agent 陷入无限 tool loop 或错误工具调用？

工具调用需要边界控制，因为 LLM 可能会反复调用工具、调用错误工具、调用参数错误的工具，或者在工具结果不足时一直循环。

Agent 如果没有限制，可能出现：

- 无限 tool loop。
- 工具调用次数过多导致成本失控。
- 重复调用同一个工具拿相同结果。
- 上下文越来越长直到超限。
- 高风险工具被错误执行。
- 工具失败后模型继续基于错误结果推理。

### 这个项目里的控制思路

这个项目不是让工具调用无限跑，而是在 Reasoner / passive turn 里做了边界控制。

核心包括：

```text
max_iterations
  限制一轮 ReAct / tool loop 的最大迭代次数

tool_calls 结果写入 history
  让模型看到工具结果后再继续推理

context trim / retry
  上下文过长时按策略裁剪后重试

tool pre interceptor
  插件可以在工具执行前拦截高风险或不合规调用

tool call trace
  记录工具调用链，方便观测和调试
```

### 为什么需要 max_iterations

LLM 有时会一直觉得“还需要调用工具”。

例如：

```text
调用 search
  -> 结果不满意
  -> 再调用 search
  -> 又不满意
  -> 继续调用
```

如果没有 `max_iterations`，这一轮可能永远不结束。

`max_iterations` 的作用是给一轮推理设置硬边界。

到了上限，系统应该停止继续 tool loop，并返回可控结果或 fallback。

### 为什么需要工具前置拦截

不是所有模型提出的工具调用都应该执行。

比如 shell 类工具可能有风险：

- 打开交互式编辑器。
- 执行需要密码的命令。
- 执行破坏性命令。
- 卡住等待确认。

项目里的插件可以通过 tool pre hook 做拦截。

这说明工具执行不是“模型说什么就做什么”，中间还有 runtime guard。

### 为什么需要 context trim / retry

工具调用会不断增加上下文：

```text
assistant tool_call
tool result
assistant tool_call
tool result
...
```

如果工具结果很长，很容易导致上下文超限。

所以系统需要 trim plan：

- 先裁剪低优先级上下文。
- 再缩小 history window。
- 必要时裁掉 retrieved memory 或 long-term memory。

这保证 tool loop 在复杂场景下仍然有机会完成。

### 面试总结

可以这样回答：

```text
工具调用必须有边界控制，因为 LLM 可能重复调用工具、调用错误工具、参数错误，甚至陷入无限 ReAct loop。这个项目通过 max_iterations 限制一轮 tool loop 的最大迭代次数，通过 tool result 写回 history 让模型基于结果继续推理，通过 context trim / retry 处理上下文过长，通过 tool pre interceptor 让插件在执行前拦截高风险工具调用，并通过 trace 记录工具链路。这样工具调用既可用，又不会完全失控。
```

### 可以改进的地方

- 对重复 tool call 做 signature 去重，避免相同参数反复调用。
- 给工具配置单独的 timeout、重试次数和成本预算。
- 对高风险工具增加 user approval。
- 对工具结果做结构化错误分类，帮助模型决定重试还是停止。
- Dashboard 展示 tool loop 的迭代次数、停止原因和最后一次工具结果。

## Q17: 这个项目如何处理上下文过长？为什么不能简单把所有 memory、history、tools 都塞进 prompt？

不能把所有内容都塞进 prompt。

原因很直接：

- 模型上下文窗口有限。
- prompt 越长，延迟和成本越高。
- 无关 memory 会干扰模型判断。
- 工具列表过长会降低工具选择质量。
- 长期记忆、检索记忆、近期 history 混在一起会让模型分不清信息来源。

所以这个项目做了 context budget 和 trim plan。

### 上下文里主要有哪些内容

一轮对话的模型输入大概包括：

```text
system prompt
  identity / behavior rules / skills catalog
  self model / long-term memory / recent context

context frame
  active skills
  retrieved memory
  turn injection context

session history
  最近对话窗口

current user message

tools
  当前可用工具 schema
```

这些内容都可能变长。

如果不做预算，复杂一点的会话很容易超出模型上下文限制。

### 项目里的裁剪思路

这个项目不是粗暴截断字符串，而是按 section 降级。

之前看过的 trim plan 包括：

```text
full
trim_skills_catalog
trim_memes
trim_long_term_memory
trim_retrieved_memory
```

也就是说，系统会先尝试完整上下文。

如果太长，再逐步裁剪低优先级或可恢复内容。

### 为什么按 section 裁剪更好

简单截断字符串的问题是：

- 可能截断 system rule。
- 可能截断 JSON / tool schema。
- 可能把一条 memory 截成半句。
- 可能保留了无关内容，却丢了关键用户消息。

按 section 裁剪更可控。

例如：

- 核心身份和行为规则优先保留。
- 当前用户消息必须保留。
- 最近 history 比很旧 history 更重要。
- retrieved memory 如果不够相关，可以裁掉。
- skills catalog 可以在必要时降级。

这体现了“上下文不是越多越好，而是要按价值排序”。

### 和滑动窗口的关系

滑动窗口负责控制 session history 的长度。

trim plan 负责控制整个 prompt 的组成。

两者配合：

```text
history 太长
  -> 用 memory_window / keep_count 控制最近消息

整体 prompt 太长
  -> 用 trim plan 裁剪动态 section
```

所以 memory window 是局部策略，context budget 是全局策略。

### 面试总结

可以这样回答：

```text
这个项目不会把所有 memory、history、tools 都无脑塞进 prompt，而是做了上下文预算和分层裁剪。模型输入由 system prompt、context frame、session history、当前用户消息和 tools 组成，其中 memory、skills、retrieved context 都可能变长。项目通过 memory_window 控制最近历史窗口，通过 trim plan 按 section 降级，例如先裁剪 skills catalog、memes、long-term memory、retrieved memory 等，而不是简单截断字符串。这样可以优先保留核心系统规则、当前用户输入和高价值上下文，降低成本和干扰。
```

### 可以改进的地方

- Dashboard 展示每个 prompt section 的 token 数和裁剪状态。
- 给每条 retrieved memory 增加相关性分数，用于裁剪排序。
- 根据任务类型动态调整裁剪策略，例如 coding、问答、记忆修正使用不同预算。
- 对工具 schema 做按需暴露，而不是总是暴露完整工具集。
- 增加“上下文质量评估”，统计裁剪后回答质量是否下降。

## Q18: 这个项目为什么要抽象 LLM Provider？直接在 AgentLoop 里调用 OpenAI API 不行吗？

不建议直接在 AgentLoop 里调用具体模型 API。

这个项目把模型调用封装成 `LLMProvider`，核心原因是让 AgentLoop 不依赖某一个厂商或某一种调用细节。

可以理解为：

```text
AgentLoop / Reasoner
  -> 调 provider.chat()
  -> provider 负责适配具体模型 API
  -> 返回统一的 LLMResponse
```

### Provider 层负责什么

`LLMProvider` 主要负责把不同模型的差异统一起来。

包括：

- OpenAI 兼容 Chat Completions 调用。
- `tools` 和 `tool_choice` 参数。
- tool calls 的解析。
- 流式输出。
- thinking / reasoning_content 字段处理。
- provider-specific extra_body。
- context length error / safety error 识别。
- prompt cache token 信息提取。
- 不同 base_url / model 配置。

这样上层 Reasoner 只需要面对统一结果：

```text
LLMResponse(
  content=...,
  tool_calls=...,
  thinking=...,
  cache_prompt_tokens=...,
  cache_hit_tokens=...
)
```

### 为什么不能把这些写进 AgentLoop

如果 AgentLoop 直接调用模型 API，会有几个问题：

- 模型厂商差异污染核心逻辑。
- 流式输出、tool call、thinking 字段会和 agent loop 混在一起。
- 更换模型或 base_url 要改主流程。
- 测试时很难 mock 模型调用。
- 错误处理、重试、上下文超限识别会分散在业务代码里。

Provider 抽象把“模型适配”从“agent 决策流程”里拆出来。

### 为什么项目里还有 main / light / agent / vl 等模型配置

不同任务不一定要用同一个模型。

例如：

- 主对话需要质量更高的 main model。
- 记忆摘要、轻量判断可以用 light model。
- 后台 agent 或 subagent 可以用 agent model。
- 图片理解可能需要 vl model。

Provider 抽象让这些模型可以共享统一调用接口，但底层配置不同。

这也是工程化 agent runtime 常见设计。

### 和工具调用的关系

工具调用依赖模型返回 `tool_calls`。

但不同 provider 在 tool call、streaming tool call、reasoning 字段上的格式可能不同。

Provider 层负责把这些差异转成统一结构：

```text
ToolCall(id, name, arguments)
```

这样 Reasoner 只管执行工具，不需要关心具体厂商返回格式。

### 面试总结

可以这样回答：

```text
这个项目抽象 LLMProvider，是为了把模型适配和 AgentLoop 解耦。AgentLoop / Reasoner 只调用 provider.chat()，拿到统一的 LLMResponse；Provider 层负责 OpenAI 兼容 API、tools/tool_choice、tool_calls 解析、流式输出、thinking 字段、extra_body、context length error、safety error、prompt cache token 等差异处理。这样更换模型、配置 main/light/agent/vl 不需要改核心 loop，也方便测试和扩展不同厂商模型。
```

### 可以改进的地方

- 给不同 provider 增加能力声明，例如是否支持 tools、streaming、vision、reasoning。
- 根据任务自动选择 main / light / agent 模型。
- 对 provider 错误做更结构化分类，便于 fallback。
- 增加多 provider fallback，例如主模型失败时自动切备用模型。
- Dashboard 展示每轮使用的 provider、model、token、cache hit 和错误信息。

## Q19: 这个项目为什么需要 channel 和 session 抽象？只做一个 CLI 问答不行吗？

只做 CLI 问答当然能跑，但它会把输入输出、用户身份、会话状态和 agent 主循环耦合在一起。

这个项目做 channel / session 抽象，是为了让同一个 Agent Runtime 可以接入不同入口。

可以理解为：

```text
CLI / Web / IM / API / Proactive
  -> Channel Adapter
  -> Message / Session
  -> AgentLoop
  -> Reply / Push
```

### channel 解决什么问题

`channel` 负责处理“消息从哪里来、回复发到哪里去”。

不同入口的协议不一样：

- CLI 是终端输入输出。
- Web 可能是 HTTP/WebSocket。
- IM 可能有 chat_id、user_id、群聊、私聊。
- Proactive 可能不是用户发消息，而是系统主动推送。

如果没有 channel 抽象，AgentLoop 就要知道每个平台怎么收消息、怎么发消息。

这会让核心逻辑和具体通信协议耦合。

### session 解决什么问题

`session` 负责保存一次持续对话的状态。

例如：

- 当前用户是谁。
- 当前 channel 是什么。
- 当前 chat_id 是什么。
- 历史 messages。
- last_consolidated 指针。
- session metadata。
- 最近工具调用统计。

Agent 需要根据 session 找到对应上下文，而不是把所有用户的消息混在一起。

### 为什么这对 memory 很重要

memory consolidation 依赖 session history。

如果没有 session 边界，会出现几个问题：

- 不同用户的对话混在一起。
- 不同 channel 的上下文互相污染。
- memory_window 不知道该裁剪哪段历史。
- last_consolidated 无法正确记录整理进度。

所以 session 是长期记忆和上下文工程的基础。

### 为什么这对主动推送也重要

主动推送不是用户发来一条消息，而是系统决定要不要发消息给某个 channel/chat。

这就要求系统知道：

```text
推给哪个 channel
推给哪个 chat_id
使用哪个 session context
是否支持 stream events
是否应该 suppress stream
```

所以 proactive 也需要 channel/session 抽象。

### 面试总结

可以这样回答：

```text
这个项目需要 channel 和 session 抽象，是为了让 AgentLoop 不绑定 CLI。channel 负责不同入口的收发协议，例如 CLI、Web、IM、主动推送；session 负责保存某个用户或 chat 的连续对话状态，包括 history、metadata、last_consolidated 等。这样同一个 Agent Runtime 可以复用到多种通信入口，也能保证 memory、context window、proactive push 都按正确会话隔离。如果只做 CLI 问答，短期能跑，但扩展到多用户、多平台、主动推送时会很快耦合。
```

### 可以改进的地方

- 给 session 增加更明确的生命周期管理，例如过期、归档、迁移。
- 支持多用户共享 session 时的权限和身份区分。
- Dashboard 展示 channel、chat_id、session key 和最近活跃时间。
- 对不同 channel 设置不同回复策略，例如是否流式、是否允许主动推送。
- 给 session memory 做更清晰的 scope，区分全局记忆、用户记忆、channel 记忆和 chat 记忆。

## Q20: 如果 Agent 记错了用户信息，这个项目如何处理记忆纠错？为什么不能只在回答里道歉？

不能只在回答里道歉。

如果长期记忆没有被真正修正，错误信息下次还会被召回，继续污染回答。

所以记忆纠错必须落到 memory 系统里，而不是只做一次性口头修正。

### 正确纠错流程

比较合理的流程是：

```text
用户指出记忆错误
  -> 使用 recall_memory 查找相关记忆
  -> 确认哪条 memory summary 与错误内容匹配
  -> 调 forget_memory 标记错误条目 superseded
  -> 如果用户给出正确版本，再调用 memorize 写入新记忆
  -> 回复用户说明已修正
```

也就是说：

```text
先确认
再失效
再写入正确版本
```

### forget_memory 的作用

`forget_memory` 不是简单删除文本。

它会把确认错误的 memory item 标记为 `superseded`。

这样做有几个好处：

- 错误记忆不再作为 active memory 被召回。
- 系统仍可保留审计痕迹。
- 避免物理删除导致无法追踪问题来源。
- 可以区分“用户要求忘记”和“记忆被新版本替代”。

### 为什么要先 recall_memory

因为不能盲目删除。

用户说“你记错了”，系统需要先找到具体哪条记忆错了。

否则可能误删无关记忆。

项目里的 `forget_memory` 工具描述也强调：只有在用户明确纠正，并且已经通过 `recall_memory` 确认 summary 与错误内容吻合时才调用。

这就是一个防误删机制。

### 如果用户给出正确版本怎么办

如果用户说：

```text
你记错了，我不是学生，我已经毕业了。
```

理想处理是：

```text
recall_memory 找到“用户是学生”
forget_memory 失效这条旧记忆
memorize 写入“用户已经毕业”
```

这样错误记忆被移除，正确记忆被补上。

### consolidation 里的 correction

除了显式工具纠错，consolidation 也支持 `correction` 类型的 pending item。

这说明系统在自动整理记忆时，也会把“对已有长期记忆的明确更正”作为特殊类型处理。

但面试时要强调：用户明确纠错时，最可靠的是通过工具链实际修改 memory store。

### 面试总结

可以这样回答：

```text
这个项目处理记忆纠错时，不能只在回复里道歉，因为错误长期记忆如果仍然存在，下次还会被召回。正确流程是先用 recall_memory 找到与错误内容匹配的 memory item，再用 forget_memory 将其标记为 superseded；如果用户提供了正确版本，再用 memorize 写入新的记忆。forget_memory 不是盲删，而是让错误条目失效并保留审计痕迹。consolidation 里也有 correction 类型，用于识别对已有记忆的更正。
```

### 可以改进的地方

- Dashboard 提供“记忆纠错向导”，展示旧记忆、用户纠正、新记忆。
- 对 superseded 记忆保留 superseded_by 关系，形成版本链。
- 纠错后自动检查 `MEMORY.md` 和 `memory2.db` 是否都已同步。
- 对高敏感记忆纠错增加用户确认。
- 统计错误记忆来源，评估是 memorize、consolidation 还是 retrieval 导致的问题。

## Q21: Agent 可以调用工具和插件后，系统如何做安全边界？只靠 prompt 约束够吗？

只靠 prompt 约束不够。

因为 LLM 可能误判、遗漏规则、被用户诱导，或者生成看起来合理但实际危险的工具调用。

所以安全边界应该放在 runtime 里，而不是只写在 system prompt 里。

### 这个项目里的安全思路

这个项目通过工具执行前的 hook 做安全控制。

典型机制是：

```text
LLM 生成 tool_call
  -> ToolRuntime 准备执行
  -> on_tool_pre hook 先检查
  -> 插件可以 allow / deny / rewrite
  -> 通过后才真正执行工具
```

也就是说，模型不是说调用就调用，中间有运行时拦截层。

### 典型安全插件

项目里有几个很典型的安全插件。

`shell_safety`：

- 拦截 `vim`、`nano` 等交互式编辑器。
- 拦截可能等待密码的 `sudo`。
- 拦截缺少 `--noconfirm` 的包管理器写操作。
- 避免 shell 工具卡死在交互流程里。

`shell_restore`：

- 拦截 `rm`。
- 把删除改写成 `mv` 到 restore 目录。
- 避免 LLM 误删文件导致不可恢复。

`tool_loop_guard`：

- 检测连续重复工具调用。
- 超过阈值后 deny。
- 避免 agent 陷入重复 tool loop。

这些说明项目的安全不是一句 prompt，而是工具运行前的实际控制点。

### 为什么安全要放在工具执行层

因为真正有副作用的是工具执行，不是模型输出文本。

例如模型说：

```text
我要删除这个文件
```

本身还没有造成影响。

但如果它调用了 shell 工具执行：

```text
rm -rf ...
```

就会产生真实副作用。

所以最关键的安全边界应该在工具执行前。

### 安全边界应该分层

一个成熟 agent 应该有多层保护：

```text
Prompt rule
  告诉模型什么能做、什么不能做

Tool visibility
  控制当前场景能看到哪些工具

Tool pre hook
  执行前检查、拒绝或改写参数

Runtime permission
  对高风险操作做权限控制或用户确认

Audit log
  记录谁在什么上下文调用了什么工具
```

这个项目已经有 prompt rule、工具可见性、pre hook、安全插件和观测能力，后续可以继续增强权限模型。

### 面试总结

可以这样回答：

```text
只靠 prompt 约束不够，因为 LLM 可能误判或被诱导。这个项目把安全边界放在工具 runtime 层：LLM 生成 tool_call 后，真正执行前会经过 on_tool_pre hook，插件可以拒绝或改写调用。比如 shell_safety 会拦截交互式 shell、可能等待密码的 sudo 和缺少确认参数的包管理器操作；shell_restore 会把 rm 改写成 mv 到恢复目录；tool_loop_guard 会阻止重复工具调用形成循环。这样安全控制不是口头规则，而是在工具执行前实际生效。
```

### 可以改进的地方

- 给工具增加统一 risk level，例如 read / write / destructive。
- 对 destructive 工具加入用户审批。
- 对插件声明权限，例如是否允许注册工具、写记忆、执行 shell。
- 给每次被拦截的工具调用记录结构化审计日志。
- 支持按 channel、user、session 配置不同工具权限。

## Q22: 插件在这里是如何起作用的？比如如何引入插件，并让插件在工具调用中生效？

插件起作用分两步：

```text
启动时：发现插件、加载插件、注册 hook / tools / lifecycle modules
运行时：Agent 执行到对应阶段时，调用插件注册的扩展点
```

所以插件不是“运行时临时 import 一段代码”，而是启动阶段被 `PluginManager` 发现并注册到 runtime 里。

### 1. 插件如何被引入

项目通过 `PluginManager` 扫描插件目录。

它会查找类似这样的目录结构：

```text
plugins/
  shell_safety/
    plugin.py
  shell_restore/
    plugin.py
  tool_loop_guard/
    plugin.py
```

`PluginManager.discover()` 会扫描 plugin_dirs 下的子目录。

只要子目录里有 `plugin.py`，就认为这是一个可加载插件。

大致流程：

```text
PluginManager.discover()
  -> 找到 plugin.py
  -> importlib 从文件路径加载模块
  -> 找到 Plugin 子类
  -> 实例化插件
  -> 注入 PluginContext
  -> 绑定 handlers / tools / lifecycle modules / tool hooks
  -> 调 initialize()
```

`PluginContext` 会给插件提供一些运行时能力，例如：

- `event_bus`
- `tool_registry`
- `workspace`
- `session_manager`
- `memory_engine`
- 插件自己的配置和 kv store

所以插件加载后，不只是一个 Python 类，而是被接入了 agent runtime。

### 2. 插件如何声明自己要介入工具调用

插件通过装饰器声明 hook。

例如：

```python
from agent.plugins import Plugin, on_tool_pre
from agent.tool_hooks import HookOutcome

class ShellSafety(Plugin):
    name = "shell_safety"

    @on_tool_pre(tool_name="shell")
    async def block_interactive_shell(self, event):
        command = event.arguments.get("command", "")
        if "vim" in command:
            return HookOutcome(
                decision="deny",
                reason="禁止执行交互式编辑器"
            )
        return None
```

这里的关键是 `@on_tool_pre(tool_name="shell")`。

它表示：当 LLM 准备调用 `shell` 工具时，先运行这个插件方法。

如果不传 `tool_name`：

```python
@on_tool_pre()
```

就表示对所有工具调用都生效，例如 `tool_loop_guard` 就是这种通配 hook。

### 3. on_tool_pre 是如何注册进去的

`@on_tool_pre` 装饰器会把插件方法记录成一种 metadata：

```text
MetadataKind.TOOL_HOOK
```

插件加载时，`PluginManager` 会读取这些 metadata，并转换成 `_PluginToolHook`。

然后放进：

```text
PluginManager.tool_hooks
```

也就是说，插件方法最终会变成 ToolExecutor 能识别的 hook。

### 4. 工具调用时插件如何真正生效

LLM 返回 tool call 后，Reasoner 不会直接执行真实工具。

它会先走 `ToolExecutor`：

```text
LLM 返回 tool_call
  -> Reasoner 收到 tool_call
  -> ToolExecutor.execute(...)
  -> 依次运行匹配的 pre hooks
  -> hook 可以修改参数 / 拒绝调用
  -> 如果没被拒绝，才调用 ToolRegistry.execute(...)
  -> 工具结果返回给模型
```

这条链路很重要：

```text
插件 hook 不替代工具本身
插件 hook 只是在工具执行前做拦截、改参或放行
真实工具仍然由 ToolRegistry.execute 执行
```

### 5. 插件可以返回什么

`on_tool_pre` 插件一般有三种返回：

```text
None
  不处理，继续执行工具

dict
  改写工具参数，用新的 arguments 执行工具

HookOutcome(decision="deny", reason="...")
  拒绝执行工具，把 reason 返回给模型
```

例如：

- `shell_safety`：返回 deny，阻止交互式 shell。
- `shell_restore`：返回新的 arguments，把 `rm` 改成 `mv`。
- `tool_loop_guard`：检测重复调用，超过阈值后 deny。

### 面试总结

可以这样回答：

```text
插件通过 PluginManager 引入。启动时 PluginManager 扫描 plugin_dirs，找到包含 plugin.py 的插件目录，用 importlib 加载模块，实例化 Plugin 子类，注入 PluginContext，然后绑定插件声明的 tools、lifecycle modules、event handlers 和 tool hooks。对于工具调用，插件通过 @on_tool_pre 声明 pre-tool hook；装饰器会把方法注册成 TOOL_HOOK metadata，PluginManager 加载时把它适配成 ToolExecutor 的 hook。运行时 LLM 返回 tool_call 后，Reasoner 不直接执行工具，而是先交给 ToolExecutor；ToolExecutor 会运行匹配的插件 hook，插件可以放行、改写参数或 deny，之后才进入 ToolRegistry.execute 执行真实工具。

• 可以，面试里可以这样说：

  这个项目的插件系统是通过插件管理器接入的。程序启动时，插件管理器会扫描配置里的插件目录，找到包含 plugin.py 的插件文件夹，然后通过动态导入的方式加载插件模块。插件类被加载
  后，会自动注册到插件注册表中，插件管理器再创建插件实例，并把运行时上下文对象交给插件使用。这个上下文里包含事件总线、工具注册表、插件配置、工作目录、会话管理器和记忆引擎等
  能力。

  插件加载完成后，插件管理器会把插件声明的能力统一挂到主系统里，包括插件工具、生命周期模块、事件处理函数和工具调用钩子。

  在工具调用流程里，插件可以声明“工具执行前钩子”，用来拦截某些工具调用。比如 shell 安全插件可以在真正执行 shell 命令前检查命令内容。插件管理器加载插件时，会把这些钩子转换成
  工具执行器可以识别的形式。

  运行时，大模型返回工具调用请求后，推理模块不会直接执行工具，而是先把请求交给工具执行器。工具执行器会先运行所有匹配的插件钩子。插件可以选择直接放行，也可以改写工具参数，或
  者拒绝这次调用。只有通过这些检查后，请求才会进入工具注册表，执行真正的工具。

  更简洁一点的面试版可以说：

  这个项目没有让大模型直接调用工具，而是在中间加了一层工具执行器。插件系统启动时由插件管理器统一加载插件，并把插件声明的工具、生命周期模块、事件监听器和工具钩子注册到运行
  时。工具调用发生时，插件的前置钩子会先于真实工具执行，可以做安全检查、参数改写、审计或阻断。这样工具执行链路既可扩展，也更容易做安全治理。


注：“注入 PluginContext”在这个项目里更准确地说是：插件管理器创建插件实例后，给它设置 instance.context = PluginContext(...)。这不是通过构造函数传参，而是把一个上下文对象挂到插
  件实例上。

  这个上下文里实际包含：

  - event_bus：事件总线
  - kv_store：插件自己的简单键值存储
  - config：插件配置
  - app_config：应用配置
  - workspace：工作目录
  所以“注入”就是“由插件管理器把运行时能力交给插件使用”。插件不用自己到处 import 或查找全局对象，而是通过 self.context 访问系统提供给它的能力。
```

### 为什么这样设计

这样设计的好处是：

- 核心 AgentLoop 不需要知道每个插件细节。
- 插件可以独立扩展工具安全、参数改写、循环保护等能力。
- 工具执行前有统一拦截点。
- 插件逻辑和真实工具实现解耦。
- 安全策略可以通过插件增删，而不用改核心 Reasoner。

### 可以改进的地方

- Dashboard 展示每次工具调用命中了哪些 plugin hook。
- 给插件 hook 增加优先级和冲突处理规则。
- 对改写参数的 hook 展示 before / after diff。
- 给插件声明权限范围，例如能否 deny、能否 rewrite、能否注册工具。
- 插件加载失败时展示明确错误和禁用状态。

## Q23: 为什么项目要做工具可见性和 tool_search？为什么不把所有工具每轮都暴露给 LLM？

不应该每轮把所有工具都暴露给 LLM。

工具多了以后，全量暴露会带来几个问题：

- prompt 变长，成本和延迟上升。
- 模型更容易选错工具。
- 工具 schema 太多会稀释注意力。
- 高风险工具暴露面扩大。
- 插件注册的工具越来越多时，主循环难以控制上下文预算。

所以这个项目做了工具可见性和按需发现。

### 工具分成 always_on 和 deferred

可以理解为两类工具：

```text
always_on 工具
  每轮默认可见
  通常是高频、低风险、元工具

deferred 工具
  默认不暴露
  需要通过 tool_search 搜索/选择后解锁
```

例如 `tool_search` 本身通常是 always_on。

其他不常用工具可以先不出现在 prompt 里。

### tool_search 的作用

`tool_search` 像是工具目录搜索器。

当模型知道需要某类能力，但当前可见工具里没有时，可以调用：

```text
tool_search(query="...")
```

或者：

```text
tool_search(query="select:某个工具名")
```

搜索结果里返回匹配工具，系统再把这些工具加入当前可见工具集合。

下一轮 LLM 调用时，这些工具 schema 才会真正暴露给模型。

### 运行时如何控制可见工具

当 `tool_search_enabled=True` 时，Reasoner 会维护 `visible_names`：

```text
visible_names = always_on + preloaded
```

然后调用模型时只传：

```text
tools.get_schemas(names=visible_names)
```

所以模型不是看到全部工具，而是只看到当前允许的工具子集。

### 如果模型直接调用不可见工具怎么办

如果模型直接调用了一个已注册但不可见的 deferred 工具，系统不会直接执行。

它会返回一个引导信息，提示应该先通过 `tool_search` 选择或解锁。

这避免模型绕过可见性机制。

大致逻辑是：

```text
LLM 调用 tool_x
  -> tool_x 不在 visible_names
  -> 不执行真实工具
  -> 返回提示，引导使用 tool_search/select
```

### preloaded 和 LRU 是什么

项目还有 `ToolDiscoveryState`。

它会按 session 记住最近解锁或使用过的 deferred 工具。

逻辑类似 LRU：

```text
本轮使用了某些 deferred tools
  -> 写入 session 级 LRU
  -> 下一轮作为 preloaded tools 自动可见
```

但 always_on 和 `tool_search` 本身不会写入 LRU，因为它们本来就默认可见。

这样可以做到：

- 常用工具在同一 session 里短期保持可见。
- 不常用工具不会永久污染 prompt。
- 每个 session 的工具可见性相互隔离。

### 面试总结

可以这样回答：

```text
这个项目没有每轮暴露所有工具，而是做了工具可见性和按需发现。工具分为 always_on 和 deferred：always_on 每轮默认可见，deferred 默认隐藏，需要通过 tool_search 搜索或 select 后解锁。开启 tool_search_enabled 后，Reasoner 只把 visible_names 对应的 tool schema 传给 LLM；如果模型直接调用不可见工具，系统会拦截并引导先用 tool_search。ToolDiscoveryState 还会按 session 用 LRU 记住最近解锁的工具，作为下一轮 preloaded tools。这样能降低 prompt 成本，减少误选工具，并控制工具暴露面。


```

### 为什么这样设计

这个设计的核心是：工具不是越多越好，而是要“当前任务需要什么，就暴露什么”。

它解决了三个问题：

- 上下文预算：减少每轮 tool schema token。
- 工具选择质量：减少模型在大量工具里误选。
- 安全边界：降低不相关工具的暴露面。

### 可以改进的地方

- 给 deferred 工具增加更强的语义分类和标签。
- 根据用户任务自动预加载相关工具，而不完全依赖模型搜索。
- Dashboard 展示当前 visible tools、preloaded tools 和 newly unlocked tools。
- 对工具搜索结果做 rerank，提升工具发现质量。
- 为高风险工具设置“即使搜索到也需要人工确认”的策略。

## Q24: 为什么项目需要 subagent / background job？主 Agent 自己完成所有任务不行吗？

主 Agent 可以完成短任务，但不适合把所有长任务都放在当前对话里做。

原因是：

- 长任务会阻塞用户当前会话。
- 多步工具调用会撑大上下文。
- 主 Agent 需要同时负责用户沟通和任务执行，职责变重。
- 长任务失败、超时、循环时会影响本轮回复体验。
- 有些任务适合后台慢慢做，完成后再回传结果。

所以项目引入了 `spawn` / subagent / background job。

### spawn 解决什么问题

`spawn` 工具的作用是把一个有界的多步任务交给独立 subagent。

适合场景：

```text
需要 4 步以上工具调用
任务可以独立完成
中途不需要用户确认
产出是报告 / 文件 / 分析结论
预计耗时较长
```

不适合场景：

```text
只需要 1-3 次工具调用
需要立即执行的动作
需要和用户来回确认
需要修改当前会话状态
直接回答就能解决的问题
```

### 同步执行和后台执行

`spawn` 支持两种模式：

```text
run_in_background = false
  同步执行
  主会话等待 subagent 结果
  适合不太长、但步骤较多的任务

run_in_background = true
  后台执行
  主会话先继续
  任务完成后通过 completion event 回到原会话
```

这让主 Agent 可以把重任务委派出去，而不是一直卡住用户。

### subagent 和主 Agent 的职责区别

主 Agent 更像调度者和用户沟通者：

- 判断任务是否需要委派。
- 写清楚 task。
- 选择 profile。
- 决定同步还是后台。
- 最后把结果解释给用户。

subagent 更像执行者：

- 按 task 独立完成多步操作。
- 使用被授权的工具。
- 产出结果摘要、报告或文件。
- 不直接和用户来回沟通。

这是一种任务委派模式。

### profile 权限有什么意义

`spawn` 里有 profile：

```text
research
  只读调研，可搜索、读文件、抓网页

scripting
  执行型，可运行 shell、写任务目录文件，通常不访问网络

general
  两者都有，只在明确需要时使用
```

这说明 subagent 不是拿到所有工具权限，而是根据任务选择工具权限边界。

这是安全和任务隔离的一部分。

### 后台任务如何回到主会话

后台 subagent 完成后，不是直接把原始结果发给用户。

它会生成 completion event：

```text
subagent 完成
  -> AgentBackgroundJobResult
  -> SpawnCompletionItem
  -> publish_inbound
  -> 主 Agent 收到后台任务回传
  -> 主模型整理成用户可见回复
```

也就是说，后台结果会重新进入主 Agent 的对话处理链路。

这样可以：

- 复用主 Agent 的回复风格。
- 经过 AfterReasoning / dispatch / 插件链。
- 避免把内部 job_id、subagent 细节直接暴露给用户。
- 必要时让主 Agent 判断是否需要重试或补充说明。

### 面试总结

可以这样回答：

```text
项目引入 subagent / background job，是为了把长任务和当前对话解耦。主 Agent 负责用户沟通和任务调度，遇到独立、多步、耗时较长的任务时，可以通过 spawn 交给 subagent 执行。spawn 支持同步和后台两种模式：同步模式主会话等待结果，后台模式主会话先继续，任务完成后通过 SpawnCompletionItem 回灌到原 channel/chat_id，再由主 Agent 生成用户可见回复。subagent 还支持 research、scripting、general 等 profile，用于限制工具权限，避免长任务拿到不必要的能力。
（  spawn 不是一个完全自动的调度器，而是作为常驻工具暴露给主 Agent。主 Agent 通过工具描述判断任务是否适合派生，比如长调研、多步分析、独立文件整理等场景。如果模型选择调用
  spawn，工具层会再做并发和上下文校验，然后创建同步或后台子任务。真正执行任务的是受限权限的 SubAgent，它在独立上下文里完成工作；后台模式完成后再把结果回灌到原会话。
如果察觉到后台或者同步任务达到三个则拒绝创建后台任务
）
```

### 为什么这是 Agent Runtime 的亮点

它说明这个项目不是单轮聊天机器人，而是有任务调度能力：

- 当前对话和长任务解耦。
- 长任务可后台执行。
- 任务完成后能回到原会话。
- 子任务有权限 profile。
- 主 Agent 可以做委派、汇总和重试判断。

这更接近真实 agent 系统里的多任务运行时。

### 可以改进的地方

- Dashboard 展示后台任务列表、状态、耗时、exit_reason 和结果摘要。
- 给 background job 增加持久化恢复，避免进程重启丢任务。
- 支持用户手动暂停、恢复、取消任务。
- 给 subagent 任务增加资源预算，例如最大工具调用次数、最大 token、最大运行时间。
- 对 subagent 输出增加结构化结果协议，减少主 Agent 二次解释成本。

## Q25: 这个项目里的 scheduler 解决什么问题？它和 proactive / background job 有什么区别？

`scheduler` 解决的是“未来某个时间或周期性触发任务”的问题。

它让 agent 不只是当场回答，还可以执行定时提醒、周期任务和未来触发的 AI 任务。

可以理解为：

```text
用户要求定时任务
  -> schedule 工具注册 job
  -> SchedulerService 持久化 job
  -> tick 循环检查是否到期
  -> 到期后执行 instant 或 soft 任务
  -> 执行后取消或重排下一次触发时间
```

### scheduler 支持哪些触发方式

`schedule` 工具支持三种 trigger：

```text
at
  指定绝对时间
  例如 14:30 / 2026-06-26T09:00

after
  相对延迟
  例如 30s / 5m / 2h

every
  周期触发
  例如 1h / 30m / 0 9 * * *
```

`every` 支持 interval，也支持 cron 表达式。

### scheduler 支持哪些执行模式

它有两个 tier：

```text
instant
  到时间直接推送固定 message
  适合喝水提醒、固定文本提醒

soft
  到时间调用 AI 生成内容
  适合天气、新闻、日报、上下文相关提醒
```

这两个模式很不一样。

`instant` 是固定消息，不需要模型推理。

`soft` 会调用 agent loop 生成内容，然后再 push 给用户。

### soft 为什么要提前触发

soft 任务需要 AI 生成内容，有延迟。

如果等到目标时间才开始调用 AI，用户收到消息就会晚。

所以项目里有 `compute_actual_trigger`：

```text
instant: fire_at
soft: fire_at - P90 latency
```

也就是说，soft 任务会根据历史 AI 耗时提前触发，尽量让最终推送接近用户期望时间。

这是一个很工程化的小设计。

### scheduler 如何持久化和恢复

`SchedulerService` 会把 jobs 保存到 JSON。

启动时会 `load_and_recover()`：

- 加载未完成 job。
- 处理已经错过触发时间的 misfire。
- 周期任务推进到下一个未来时间。
- 超过宽限期的一次性任务丢弃。

这避免进程重启后所有定时任务都丢失。

### scheduler 和 proactive 的区别

`scheduler` 是用户明确注册的时间任务。

```text
用户说：明天 9 点提醒我
用户说：每天早上发天气
```

它是时间驱动。

`proactive` 是系统主动感知外部内容和上下文后决定是否推送。

```text
有新 alert
内容流里出现重要信息
系统判断当前值得打扰用户
```

它是事件/上下文驱动。

### scheduler 和 background job 的区别

`scheduler` 负责“什么时候触发”。

`background job / subagent` 负责“长任务如何执行”。

一个是时间调度，一个是任务执行隔离。

它们可以组合，但职责不同：

```text
scheduler
  定时触发

background job
  后台执行长任务
```

### 面试总结

可以这样回答：

```text
scheduler 让项目具备未来触发和周期任务能力。用户可以通过 schedule 工具注册 at、after、every 三类任务，并选择 instant 或 soft 两种执行模式。instant 到点直接推送固定消息；soft 到点前会根据历史 P90 AI 延迟提前触发 agent loop 生成内容，再推送给用户。SchedulerService 会把 job 持久化到 JSON，启动时恢复并处理 misfire。它和 proactive 的区别是：scheduler 是用户明确注册的时间驱动任务，proactive 是系统根据外部信号和上下文主动判断是否推送；它和 background job 的区别是：scheduler 负责什么时候触发，background job 负责长任务如何执行。
```

### 可以改进的地方

- Dashboard 展示所有 schedule job、下次触发时间、run_count 和最近执行结果。
- 支持自然语言时间解析的确认步骤，避免模型误设时间。
- 对 soft 任务记录实际触发时间和目标时间偏差。
- 周期任务失败时支持重试和告警。
- 支持用户按名称、tag、channel 批量管理定时任务。

## Q26: 每个 session 的工具可见性是如何相互隔离的？不同会话、不同消息来源比如 Telegram / QQ 是如何隔离的？

隔离的核心是 `session_key`。

项目里每条入口消息都有：

```text
channel
chat_id
```

然后组合成：

```text
session_key = f"{channel}:{chat_id}"
```

例如：

```text
telegram:123
qq:123
qqbot:c2c:user-1
cli:local
```

即使 Telegram 和 QQ 的 `chat_id` 都是 `123`，因为 `channel` 不同，最终 `session_key` 也不同。

### 1. 消息入口如何生成 session_key

`InboundMessage` 里有一个属性：

```python
@property
def session_key(self) -> str:
    return f"{self.channel}:{self.chat_id}"
```

后台任务完成事件、shell 完成事件也有类似逻辑：

```text
SpawnCompletionItem.session_key = channel:chat_id
ShellCompletionItem.session_key = channel:chat_id
```

所以无论消息来自用户、后台任务还是 shell completion，只要回到某个 channel/chat，就会映射到同一个 session。

### 2. 不同会话历史如何隔离

`AgentLoop` 处理消息时会拿：

```text
key = session_key or msg.session_key
```

然后通过：

```text
SessionManager.get_or_create(key)
```

读取或创建对应 session。

`SessionStore` 里 messages 表也有：

```text
session_key
seq
```

并且有：

```text
UNIQUE(session_key, seq)
```

这意味着每个 session 的消息序列是按自己的 `session_key` 独立保存的。

所以：

```text
telegram:123 的 history
qq:123 的 history
cli:local 的 history
```

是三份不同的对话历史。

### 3. 工具可见性如何按 session 隔离

工具可见性状态在 `ToolDiscoveryState` 里维护。

它内部是：

```python
_unlocked: dict[str, OrderedDict[str, None]]
```

key 就是 `session_key`。

也就是说：

```text
_unlocked["telegram:123"] = 这个 Telegram 会话解锁过的 deferred tools
_unlocked["qq:123"]       = 这个 QQ 会话解锁过的 deferred tools
_unlocked["cli:local"]    = 这个 CLI 会话解锁过的 deferred tools
```

当一轮开始时：

```python
preloaded = discovery.get_preloaded(session.key)
```

只会取当前 session 的工具 LRU。

当一轮结束后：

```python
discovery.update(session.key, tools_used, always_on)
```

也只会更新当前 session 对应的 LRU。

所以一个 Telegram 会话通过 `tool_search` 解锁了某个工具，不会让 QQ 会话自动看到这个工具。

### 4. 为什么 always_on 不需要隔离

`always_on` 工具默认所有 session 都可见。

例如某些元工具、低风险工具、`tool_search` 本身。

它们不进入 session LRU。

真正需要隔离的是 deferred tools 的“解锁状态”。

所以隔离的是：

```text
哪些额外工具在这个 session 里被短期预加载
```

不是隔离工具注册表本身。

工具注册表是全局的，工具可见性是按 session 过滤出来的。

### 5. 工具执行上下文如何区分 channel/chat

在执行工具前，工具注册表会设置上下文：

```text
channel
chat_id
```

工具执行时会把这些作为低优先级默认参数传进去。

所以像 `schedule`、`spawn`、`message_push`、`memorize` 这类需要知道当前会话的工具，可以拿到当前 channel/chat。

这保证工具知道自己是在：

```text
telegram:123
```

还是：

```text
qq:123
```

里被调用。

### 6. 还有哪些状态也按 session_key 隔离

除了工具可见性，很多状态也按 `session_key` 隔离：

- session history。
- last_consolidated。
- busy processing state。
- proactive 是否正在处理某个目标会话。
- undo 插件操作的会话。
- scheduler soft job 的临时 session，例如 `scheduler:{job_id}`。
- subagent 内部也会生成自己的 tool session key。

这说明 `session_key` 是整个项目的会话隔离主键。

### 面试总结

可以这样回答：

```text
这个项目用 session_key 隔离不同会话，session_key 由 channel 和 chat_id 拼出来，例如 telegram:123、qq:123、cli:local。即使不同平台的 chat_id 相同，只要 channel 不同，session_key 就不同。SessionManager 用 session_key 读取和保存各自的 history，SessionStore 的 messages 表也按 session_key + seq 记录消息。工具可见性也按 session_key 隔离：ToolDiscoveryState 内部是 dict[session_key, LRU]，每轮开始只读取当前 session 的 preloaded tools，每轮结束也只更新当前 session 的工具 LRU。所以 Telegram 会话解锁的 deferred tool 不会自动影响 QQ 会话。

  这个项目用 session_key 区分不同会话。session_key 由渠道和聊天标识拼接而成，比如 telegram:123、qq:123、cli:local。这样即使不同平台上的聊天标识相同，只要来源渠道不同，最终的
  会话标识也不同。

  会话管理器会根据 session_key 分别读取和保存各自的对话历史。底层会话存储中，消息表也是按照 session_key 和消息序号记录消息，因此不同会话的历史不会混在一起。

  工具可见性也按 session_key 做隔离。项目里有些工具不是默认全部暴露给模型，而是延迟加载的。每个会话都有自己的工具可见状态：一轮对话开始时，只读取当前会话已经加载过的工具；一
  轮结束时，也只更新当前会话的工具使用记录。

  所以，比如 Telegram 会话中解锁过某个延迟工具，并不会让 QQ 会话自动看到这个工具。不同渠道、不同聊天窗口之间的历史和工具状态都是隔离的。

```

### 为什么这样设计

这样设计解决了几个问题：

- 多平台 chat_id 可能重复，必须加 channel 区分。
- 不同用户/群聊不能共享 session history。
- 工具解锁状态不能跨会话污染。
- proactive、scheduler、background completion 都能回到正确会话。
- memory consolidation 可以知道整理的是哪一段 session history。

### 可以改进的地方

- 对 `session_key` 做统一封装类型，避免到处手写字符串拼接。
- 给 group chat、private chat、thread 增加更细的 scope 字段。
- Dashboard 展示每个 session 当前 preloaded tools。
- 支持用户级共享偏好和 session 级临时上下文分层。
- 给跨 channel 同一用户做可选身份绑定，但默认仍保持会话隔离。

## Q27: session 隔离和 memory scope 是什么关系？长期记忆会不会在不同 Telegram / QQ 会话之间互相污染？

要区分两个概念：

```text
session 隔离
  隔离的是当前会话历史、工具可见性、busy state、last_consolidated 等运行状态。

memory scope
  控制长期记忆写入和检索时是否带 channel/chat_id 范围。
```

session 隔离更严格，memory scope 更灵活。

### 1. session history 是严格按 session_key 隔离的

这个前面讲过：

```text
session_key = channel:chat_id
```

所以：

```text
telegram:123
qq:123
cli:local
```

它们的 session history 是不同的。

`SessionManager`、`SessionStore`、`ToolDiscoveryState` 都按这个 key 管状态。

### 2. memory 写入时会带 scope 信息

长期记忆系统里有：

```python
MemoryScope(
  session_key="telegram:123",
  channel="telegram",
  chat_id="123"
)
```

`memorize` 工具执行时，会从工具上下文拿到当前 `channel` 和 `chat_id`，再构造 `MemoryScope`。

consolidation / post-response memory 也会把当前会话的：

```text
scope_channel
scope_chat_id
```

写进 memory item 的 `extra_json`。

这意味着一条长期记忆可以知道自己来源于哪个 channel/chat。

### 3. memory 检索是否严格按 scope，要看调用方

这是关键点。

底层 retriever 支持：

```text
scope_channel
scope_chat_id
require_scope_match
```

如果：

```text
require_scope_match = true
```

那么检索会要求 memory item 的：

```text
extra_json.scope_channel == 当前 channel
extra_json.scope_chat_id == 当前 chat_id
```

这样就是严格同 scope 召回。

如果：

```text
require_scope_match = false
```

那么 scope 只作为上下文传入，不强制过滤，系统可能召回更广范围的相关记忆。

### 4. 普通被动检索和特定检索的策略不同

普通被动对话前的 memory retrieval 会传入当前 session scope：

```text
session_key
channel
chat_id
```

但是否强制 `require_scope_match` 取决于 hints。

也就是说，它可以允许更全局的长期记忆参与召回。

而一些更敏感或目标明确的检索，例如 proactive interest recall，会更倾向于要求当前 channel/chat scope match。

所以不能简单说“所有长期记忆都完全按 session 隔离”。

更准确的说法是：

```text
session 状态严格隔离；
memory item 带 scope；
memory 检索支持按 scope 严格过滤，但普通召回可以根据策略允许全局记忆参与。
```

### 5. 为什么 memory 不一定完全按 session 隔离

因为长期记忆有时是跨会话有价值的。

比如：

```text
用户喜欢中文回答
用户偏好直接一点
用户正在学习 agent 项目
```

这些偏好可能不只适用于 Telegram，也适用于 CLI。

如果长期记忆完全锁死在某个 session，agent 在另一个入口就会丢失用户偏好。

但某些内容确实应该按 chat/channel 限定：

```text
某个群聊里的上下文
某个私聊里的临时任务
某个 channel 特有的操作偏好
某个 proactive 目标会话的兴趣召回
```

所以项目采用的是“带 scope 的长期记忆”，而不是简单的“所有记忆全局共享”或“所有记忆完全 session 私有”。

### 面试总结

可以这样回答：

```text
这个项目里 session 隔离和 memory scope 是两层概念。session history、工具可见性 LRU、busy state、last_consolidated 等运行状态严格按 session_key 隔离，session_key 由 channel:chat_id 组成，所以 telegram:123 和 qq:123 是不同会话。长期记忆写入时会带 MemoryScope，把 scope_channel 和 scope_chat_id 写进 memory item。检索时底层支持 require_scope_match，如果开启就只召回同 channel/chat 的记忆；如果不开启，则可以允许更全局的长期记忆参与召回。这样既能避免会话状态互相污染，又能让真正有价值的用户偏好在不同入口复用。


  这个项目里，会话隔离和长期记忆作用域是两层不同的设计。

  第一层是运行时会话隔离。系统用 session_key 区分不同会话，session_key 通常由渠道和聊天标识组成，比如 telegram:123、qq:123、cli:local。所以即使 Telegram 和 QQ 的聊天标识都是
  123，只要渠道不同，它们就是两个不同会话。

  会话历史、会话元信息、处理中状态、last_consolidated 这些运行时状态都按 session_key 管理。SessionManager 读取和保存历史时使用 session_key，底层消息表也用 session_key 加消息
  序号记录消息，因此不同会话的历史不会混在一起。被动消息处理中的 busy 状态也是按 session_key 计数，一个会话正在处理，不会影响另一个会话。

  工具可见性也按会话隔离。项目里的延迟工具不是所有会话一开始都可见，而是通过工具搜索逐步解锁。ToolDiscoveryState 内部按 session_key 维护各自的最近使用工具缓存；每轮开始只读
  取当前会话已经解锁的工具，每轮结束也只更新当前会话的工具记录。因此 Telegram 会话里解锁过的工具，不会自动出现在 QQ 会话里。

  第二层是长期记忆作用域。长期记忆接口里有 MemoryScope，包含 session_key、channel 和 chat_id。默认记忆引擎会把 session_key 解析成渠道和聊天标识，并在检索时传入 scope_channel
  和 scope_chat_id。底层检索支持 require_scope_match：开启时，只召回同一渠道、同一聊天标识下的记忆；不开启时，则允许更全局的长期记忆参与召回。

  这样设计的好处是：短期会话状态严格隔离，避免不同入口互相污染；长期记忆又可以根据场景选择是只看当前会话，还是允许复用更全局的用户偏好和稳定事实。

```

### 为什么这样设计

完全全局记忆的问题是容易跨会话污染。

完全 session 私有的问题是用户偏好无法跨入口复用。

带 scope 的记忆设计处在中间：

- 来源可追踪。
- 需要严格隔离时可以按 scope 过滤。
- 需要个性化时可以复用跨会话长期偏好。
- Dashboard 可以按 scope 查看记忆来源。

### 可以改进的地方

- 明确区分 global / user / channel / chat / session 五种 memory scope。
- `memorize` 工具写入时把 scope 也写入显式记忆 extra，而不只依赖部分路径。
- `recall_memory` 工具增加参数，让用户选择是否只查当前会话。
- Dashboard 展示每条 memory 的 scope 和是否参与当前召回。
- 对群聊记忆和私聊记忆设置不同默认召回策略。

## Q28: 这个项目为什么要用 EventBus 做事件驱动解耦？比如 TurnCommitted / ConsolidationCommitted 起什么作用？

EventBus 的作用是把主流程和后处理模块解耦。

Agent 一轮对话完成后，不应该在核心 AgentLoop 里硬编码：

```text
写 observe trace
写 markdown memory
写 vector memory
触发 post-response memory
通知插件
更新 dashboard
```

否则核心流程会越来越重，也会直接依赖所有扩展模块。

这个项目的做法是：

```text
核心流程发布事件
  -> 关心这个事件的模块自己订阅
  -> 各模块独立处理自己的副作用
```

### EventBus 有哪些调用方式

项目里的 `EventBus` 大致有几种语义：

```text
on(event_type, handler)
  注册事件处理器

fanout(event)
  并发通知所有观察者，适合生命周期广播

observe(event)
  顺序观察，单个观察者失败不打断主流程

enqueue(event)
  放入后台队列，避免主回复等待后处理

emit(event)
  依次执行干预链，handler 可以返回新 event
```

这说明 EventBus 不只是简单 pub/sub，而是区分了同步广播、后台观察和可变更事件链。

### TurnCommitted 是什么

`TurnCommitted` 表示一轮对话已经完成并提交。

里面包含：

- `session_key`
- `channel`
- `chat_id`
- 用户输入
- assistant response
- tools_used
- thinking
- tool_chain
- post_reply_budget
- react_stats
- extra metadata

它是在 AfterTurn 阶段构建并 fanout 的。

也就是说，主流程把“这一轮已经完成”的事实广播出去。

### 谁会订阅 TurnCommitted

例如：

`observe` 插件会订阅 `TurnCommitted`：

```text
TurnCommitted
  -> 写 turn trace
  -> 给 Dashboard 展示
```

memory 插件也会订阅 `TurnCommitted`：

```text
TurnCommitted
  -> 转成 TurnIngested
  -> enqueue 到后台
  -> post-response memory worker 处理
```

注意这里 memory 插件不是让主回复等待完整记忆写入，而是把后处理放到后台队列。

这能减少用户等待时间。

### ConsolidationCommitted 是什么

`ConsolidationCommitted` 表示 markdown consolidation 已经完成。

它里面包含：

- history entries
- source_ref
- scope_channel
- scope_chat_id
- conversation

它的作用是桥接 markdown memory 和 vector memory。

大致流程：

```text
markdown consolidation
  -> 写 HISTORY.md / PENDING.md / RECENT_CONTEXT.md
  -> emit ConsolidationCommitted
  -> memory2 订阅事件
  -> 把同一批历史事件写入 memory2.db
```

这样 markdown 层和 vector 层不需要互相直接调用。

### 为什么这比直接调用更好

如果 markdown consolidation 直接调用 vector memory，会产生强耦合：

```text
MarkdownMemoryService
  -> 必须知道 memory2 怎么写
  -> memory2 失败可能影响 markdown 提交流程
  -> 后续加 observe / audit / dashboard 也要继续改核心代码
```

事件驱动后：

```text
Markdown 层只负责提交自己的结果并发布事件
Vector 层只负责订阅事件并处理自己的写入
Observe 插件只负责订阅事件并记录 trace
```

模块边界更清楚。

### 面试总结

可以这样回答：

```text
这个项目用 EventBus 做事件驱动解耦，让核心 AgentLoop 不需要硬编码所有后处理。AfterTurn 阶段会构建 TurnCommitted 并 fanout，observe 插件可以用它写 trace，memory 插件可以用它触发 post-response memory ingest。markdown consolidation 完成后会发布 ConsolidationCommitted，memory2 订阅这个事件，把同一批 history entries 写入向量数据库。这样主流程只发布事实，具体副作用由订阅者处理，markdown memory、vector memory、Dashboard、插件之间不需要强依赖。

  这个项目用事件总线做运行时解耦，核心 Agent 流程只负责发布关键事实，不把所有后处理逻辑硬编码进去。

  比如一轮对话结束后，AfterTurn 阶段会构建一个“对话已提交”事件，里面包含会话标识、用户输入、模型回复、工具调用链、思考内容和一些统计信息。然后系统通过事件总线把这个事件分发
  出去。

  后续的副作用由订阅者各自处理。比如观察插件订阅这个事件后，会把本轮对话、工具调用和上下文预算等信息写入 trace；默认记忆插件订阅这个事件后，会触发回复后的记忆摄入流程，把本
  轮对话交给记忆系统做后处理。核心 AgentLoop 不需要知道这些插件具体怎么写数据库、怎么做记忆提取。

  记忆合并也是类似的设计。Markdown 记忆完成 consolidation 后，会发布“记忆合并已提交”事件，事件里带着本次提取出的历史条目、来源引用、会话作用域和原始对话内容。默认记忆引擎订
  阅这个事件后，会把这些历史条目写入向量记忆库，并从同一段对话中继续抽取更长期的用户画像、偏好和行为规则。

  这样主流程只发布“发生了什么”，具体副作用交给订阅者完成。Markdown 记忆、向量记忆、观察插件和 Dashboard 相关数据之间不需要互相直接调用，系统扩展性会更好，后处理逻辑也更容易
  替换或关闭。

```

### 为什么这是工程亮点

它解决了几个问题：

- 核心 AgentLoop 不会被后处理逻辑污染。
- 插件可以新增订阅者，不需要改主流程。
- memory 写入、observe trace 可以异步处理。
- markdown 层和 vector 层通过事件桥接。
- 单个 observer 失败不一定打断主回复。

### 可以改进的地方

- 给事件增加 trace_id，串起一轮 turn 的所有后处理。
- Dashboard 展示每个事件有哪些订阅者、耗时和失败情况。
- 对关键事件增加重试和 dead-letter queue。
- 对事件 payload 做版本管理，避免插件升级后字段不兼容。
- 明确哪些事件是同步关键路径，哪些事件必须后台异步。

## Q29: 短期记忆、长期记忆、情景记忆、程序性记忆在这个项目里分别存储在哪里？

先说明一点：这些是认知科学里的分类，项目代码里不一定直接使用这些中文名字。

在这个项目里，可以这样映射：

| 记忆类型 | 项目里的对应实现 | 主要存储位置 |
| --- | --- | --- |
| 短期记忆 | 当前 session history、滑动窗口、近期上下文摘要 | `sessions.db` / `session.messages` / `RECENT_CONTEXT.md` |
| 长期记忆 | 稳定用户事实、偏好、自我认知 | `MEMORY.md` / `SELF.md` / `memory2.db` 中的 `profile`、`preference` |
| 情景记忆 | 发生过的事件、某次对话、时间线历史 | `HISTORY.md` / `journal/YYYY-MM-DD.md` / `memory2.db` 中的 `event` |
| 程序性记忆 | 操作流程、工具调用规则、执行步骤 | `memory2.db` 中的 `procedure`，部分会进入检索注入块 |

### 1. 短期记忆存在哪里

短期记忆主要是当前会话上下文。

包括：

```text
session.messages
sessions.db
memory_window / keep_count 保留的最近 history
RECENT_CONTEXT.md
```

`session.messages` 是运行中的会话消息列表。

`SessionStore` 会把消息持久化到 `sessions.db`，按 `session_key` 读取：

```text
SELECT ... FROM messages WHERE session_key = ? ORDER BY seq ASC
```

模型每轮真正看到的短期对话，不是全部历史，而是经过 `memory_window / keep_count` 控制后的最近窗口。

另外，`RECENT_CONTEXT.md` 保存近期上下文摘要：

```text
## Compression
## Ongoing Threads
## Recent Turns
```

其中 `Compression` 和 `Ongoing Threads` 会作为近期摘要进入 prompt，`Recent Turns` 通常会避免和滑动窗口重复。

所以短期记忆不是一个地方，而是：

```text
原始近期对话：session history
压缩近期语境：RECENT_CONTEXT.md
```

### 2. 长期记忆存在哪里

长期稳定记忆主要在：

```text
memory/MEMORY.md
memory/SELF.md
memory2.db
```

`MEMORY.md` 存用户长期稳定事实，例如：

- 用户身份。
- 稳定偏好。
- 长期目标。
- 明确要求记住的信息。

`SELF.md` 存 agent 对自身和关系的长期认知，例如：

- agent 的自我定位。
- 与用户的协作方式。
- 对用户长期理解的抽象。

这两个文件会全文进入 system prompt。

另外，`memory2.db` 里也有长期语义记忆，尤其是：

```text
profile
preference
```

其中：

- `profile` 更像用户画像/稳定事实。
- `preference` 更像偏好、禁忌、回答习惯。

### 3. 情景记忆存在哪里

情景记忆可以理解为“发生过什么”的事件记忆。

项目里主要对应：

```text
HISTORY.md
journal/YYYY-MM-DD.md
memory2.db 中的 event
```

`HISTORY.md` 是追加式时间线事件日志。

consolidation 会从旧对话里提取 history entries 写进去。

`journal/YYYY-MM-DD.md` 是按日期组织的事件时间线。

`memory2.db` 里的 `event` 则是可语义检索的情景记忆。

consolidation 完成后，会通过 `ConsolidationCommitted` 把 history entries 同步到向量层：

```text
HISTORY.md 的 history_entry
  -> ConsolidationCommitted
  -> memory2.db(memory_type="event")
```

所以：

```text
HISTORY.md / journal 负责人类可读时间线
memory2.db event 负责机器可检索事件
```

### 4. 程序性记忆存在哪里

程序性记忆可以理解为“以后遇到某类任务该怎么做”。

项目里主要对应：

```text
memory2.db 中的 memory_type="procedure"
```

`procedure` 里可能包含：

- 需要调用哪个工具。
- 执行步骤。
- 触发条件。
- 任务流程规范。

检索注入时，`procedure` 会被放到类似这样的 section：

```text
## 【流程规范】用户偏好与规则
```

如果 procedure 带 `tool_requirement`，还可能进入：

```text
## 【强制约束】记忆规则（必须执行）
```

这说明程序性记忆不是普通事实，而是会影响后续行动方式。

### 5. PENDING.md 属于哪类记忆

`PENDING.md` 不是最终记忆层，而是待归档缓冲区。

它里面可能有：

```text
identity
preference
key_info
health_long_term
requested_memory
correction
```

这些内容经过 optimizer 处理后，才会合并进 `MEMORY.md`。

所以它更像：

```text
长期记忆候选队列
```

不是最终长期记忆。

### 面试总结

可以这样回答：

```text
这个项目里短期记忆主要是 session history 和 RECENT_CONTEXT.md：session history 保留最近对话原文，RECENT_CONTEXT.md 保存近期摘要。长期记忆主要是 MEMORY.md、SELF.md，以及 memory2.db 里的 profile/preference。情景记忆主要是 HISTORY.md、journal/YYYY-MM-DD.md，以及 memory2.db 里的 event，用来记录发生过的事件。程序性记忆主要是 memory2.db 里的 procedure，保存操作流程、工具要求和执行步骤。PENDING.md 是长期记忆候选缓冲区，不是最终记忆层。
```

### 为什么这样设计

不同记忆类型的访问方式不同：

- 短期记忆需要快速进入 prompt，所以用 session window。
- 长期稳定记忆要紧凑可靠，所以放进 `MEMORY.md` / `SELF.md`。
- 情景记忆需要按时间线追溯，所以有 `HISTORY.md` / journal。
- 程序性记忆需要被任务触发和语义检索，所以放进 `memory2.db`。
- 语义检索需要 embedding 和排序，所以 `event/profile/preference/procedure` 都会进入向量层。

### 可以改进的地方

- 在 Dashboard 中按短期/长期/情景/程序性四类展示记忆。
- 给 `MEMORY.md` 里的条目增加来源和更新时间。
- 让 `procedure` 的触发条件更结构化，减少误触发。
- 给情景记忆增加更明确的时间、地点、人物字段。
- 把 `PENDING.md` 的候选分类和最终归档结果关联起来。

## Q30: Memory Optimizer 是什么？为什么要先写 PENDING.md，再定期合并到 MEMORY.md？

Memory Optimizer 是长期记忆整理器。

它负责把 `PENDING.md` 里的候选事实，定期合并进 `MEMORY.md`。

它不是每轮对话都运行，而是低频运行。

项目文档里默认间隔大约是：

```text
memory_optimizer_interval_seconds = 10800
约 3 小时
```

### 为什么不直接写 MEMORY.md

因为 `MEMORY.md` 会全文注入 system prompt。

如果每轮 conversation consolidation 都直接修改 `MEMORY.md`，会带来几个问题：

- `MEMORY.md` 高频变化。
- prompt cache 很难命中。
- 每轮请求成本和延迟上升。
- 长期记忆容易被临时信息污染。
- 重复、冲突、纠错没有统一整理过程。

所以项目没有让 consolidation 直接写最终长期记忆。

它先把候选事实写入：

```text
PENDING.md
```

再由 optimizer 低频整理。

### PENDING.md 是什么角色

`PENDING.md` 是长期记忆候选缓冲区。

它保存从对话中提取出来、可能值得长期保存的信息。

例如：

```text
- [identity] 用户是...
- [preference] 用户偏好...
- [requested_memory] 用户要求记住...
- [correction] 用户纠正了...
```

这些内容还不是最终长期记忆。

它们需要经过判断：

- 是否真的值得长期保存。
- 是否和已有记忆重复。
- 是否和已有记忆冲突。
- 是否是对旧记忆的纠正。
- 应该放到 `MEMORY.md` 的哪个分类里。

### Optimizer 具体做什么

optimizer 大致流程是：

```text
读取 MEMORY.md
读取 PENDING.md
  -> 调 LLM 判断候选事实
  -> 新事实：合并进 MEMORY.md
  -> 重复事实：忽略
  -> 冲突事实：更新或替换旧内容
  -> correction：修正已有记忆
  -> 写回新的 MEMORY.md
  -> 清空 PENDING.md
```

所以 optimizer 的核心不是“压缩文本”，而是“长期记忆治理”。

### 它优化的是什么

它主要优化三个东西。

第一，优化 prompt cache。

`MEMORY.md` 高频变化会让 system prompt 高频变化，cache 命中率下降。

PENDING 缓冲让 `MEMORY.md` 在一段时间内保持稳定。

第二，优化长期记忆质量。

不是所有信息都应该进长期记忆。

optimizer 可以统一去重、合并、纠错和分类。

第三，优化人工可读性。

`MEMORY.md` 是人类可读文件，不能像日志一样无限追加。

optimizer 要让它保持紧凑。

### 为什么这是工程亮点

很多简单 agent 会这样做：

```text
用户说记住
  -> 直接 append 到 memory
```

这个项目更工程化：

```text
高频提取
  -> PENDING.md

低频整理
  -> MEMORY.md
```

它把“事实提取”和“长期记忆归档”拆成两个阶段。

这类似数据库里的 write buffer / compaction 思路。

### 面试总结

可以这样回答：

```text
Memory Optimizer 是长期记忆整理器。consolidation 会把候选长期事实先写入 PENDING.md，而不是直接修改 MEMORY.md；optimizer 低频读取 MEMORY.md 和 PENDING.md，判断哪些是新事实、重复事实、冲突事实或 correction，然后一次性更新 MEMORY.md 并清空 PENDING。这样设计主要是为了保护 prompt cache，因为 MEMORY.md 会全文注入 system prompt，频繁修改会导致 cache miss；同时也能提高长期记忆质量，避免临时信息、重复信息和冲突信息直接污染长期记忆。
```

### 可以改进的地方

- Dashboard 展示 PENDING 候选到 MEMORY 条目的合并结果。
- 对 optimizer 输出增加 diff，让用户看到长期记忆被改了什么。
- 给不同 tag 设置不同归档策略，例如 `correction` 优先级更高。
- 支持人工审核模式，重要记忆需要确认后才进入 `MEMORY.md`。
- 统计 PENDING 中被采纳、忽略、合并、纠正的比例，用来评估记忆质量。

## Q31: prompt cache 是存储在哪里的？

这个项目里说的 `prompt cache`，主要不是本地存储的文件。

更准确地说：

```text
真正的 prompt cache / KV cache
  存在模型服务商侧，例如 DeepSeek / OpenAI 兼容服务端

项目本地
  只记录 cache 命中统计，不保存服务端 KV cache 内容
```

所以你在项目目录里一般找不到一个“prompt_cache.db”保存完整 prompt cache。

### 1. 服务商侧的 prompt cache

很多模型服务会对重复的 prompt 前缀做缓存。

比如 system prompt、稳定上下文、稳定工具 schema 如果多轮保持一致，服务端就可能复用前面已经计算过的 KV。

这类 cache 通常由模型服务商维护。

项目只是发送请求：

```text
system prompt
context frame
history
current user message
tools
```

服务端判断哪些 token 命中缓存。

### 2. 项目本地记录的是什么

项目本地记录的是命中统计。

`LLMProvider` 会从 provider 返回的 usage 里提取：

```text
prompt_cache_hit_tokens
prompt_cache_miss_tokens
```

然后转成：

```text
cache_prompt_tokens = hit + miss
cache_hit_tokens = hit
```

这些字段进入 `LLMResponse`：

```text
LLMResponse.cache_prompt_tokens
LLMResponse.cache_hit_tokens
```

后续 observe 插件会把它们写入：

```text
observe/observe.db
turns.react_cache_prompt_tokens
turns.react_cache_hit_tokens
```

所以本地保存的是：

```text
这一轮有多少 prompt token 参与 cache 统计
其中多少 token 命中 cache
```

不是 cache 内容本身。

### 3. /kvcache 查的是什么

项目里有 `/kvcache` 或 `/cache_status` 命令。

它查询的是：

```text
observe/observe.db
turns 表
react_cache_prompt_tokens
react_cache_hit_tokens
```

然后计算命中率。

所以 `/kvcache` 展示的是统计结果，不是服务端缓存文件。

### 4. 为什么 PENDING.md 能保护 prompt cache

因为 `MEMORY.md` 会全文注入 system prompt。

如果每轮都修改 `MEMORY.md`，system prompt 前缀就会频繁变化。

服务端 prompt cache 一般依赖稳定前缀。

前缀变了，就更容易 cache miss。

所以项目设计成：

```text
高频变化的新事实
  -> 先写 PENDING.md

稳定长期记忆
  -> 低频更新 MEMORY.md
```

这样 `MEMORY.md` 在多轮对话中保持稳定，服务端更容易复用 prompt cache。

### 5. 还有一种本地 prompt block cache

项目里还有 `SystemPromptBuilder` 的 block 级缓存概念。

例如某些 prompt block 是 static 的，可以根据 `cache_signature` 判断是否复用渲染结果。

但这只是本地 prompt 组装层面的缓存。

它和模型服务商侧的 KV cache 不是一回事。

可以区分为：

```text
本地 prompt block cache
  缓存 prompt section 的渲染结果

服务端 prompt cache / KV cache
  缓存模型对重复 prompt token 的计算结果
```

前者减少本地组装重复工作。

后者减少模型推理成本和延迟。

### 面试总结

可以这样回答：

```text
这个项目里提到的 prompt cache 主要存储在模型服务商侧，不是项目本地的某个文件。项目本地不会保存完整 KV cache，只会从 provider usage 里读取 prompt_cache_hit_tokens 和 prompt_cache_miss_tokens，然后把统计值记录到 observe/observe.db 的 turns 表中，例如 react_cache_prompt_tokens 和 react_cache_hit_tokens。/kvcache 命令查的也是这些统计指标。PENDING.md 保护 prompt cache 的意思是：避免频繁修改 MEMORY.md 这种会全文注入 system prompt 的稳定前缀，从而提高服务端 prompt cache 命中率。
```

### 可以改进的地方

- Dashboard 展示每轮 prompt cache hit rate 和 system prompt 变化原因。
- 记录每个 prompt block 的 hash，定位是哪一段导致 cache miss。
- 区分本地 prompt block cache 和服务端 KV cache 的指标展示。
- 当 `MEMORY.md` 变化时记录 optimizer diff，解释下一轮 cache miss。
- 对高频动态 section 做更明确的 context frame 隔离，减少破坏稳定 system prompt 前缀。

## Q32: 本地 prompt block cache 和服务端 prompt cache / KV cache 有什么区别？

这两个 cache 不是一回事。

可以这样区分：

```text
本地 prompt block cache
  项目进程内缓存 prompt section 的渲染结果

服务端 prompt cache / KV cache
  模型服务商缓存重复 prompt token 的模型计算结果
```

一个发生在本地 prompt 组装阶段。

一个发生在远端模型推理阶段。

### 1. 本地 prompt block cache 存在哪里

本地 prompt block cache 在项目进程内。

实现是 `SectionCache`：

```python
class SectionCache:
    def __init__(self):
        self._data: dict[tuple[str, str, str], str] = {}
```

key 是：

```text
workspace scope
section name
cache signature
```

value 是：

```text
这个 prompt section 渲染出来的文本
```

它是一个内存 dict，不是数据库。

进程重启后就没有了。

### 2. 哪些 block 会用本地 cache

只有 `is_static=True` 且能产生 `cache_signature` 的 block 才会用。

例如：

```text
IdentityPromptBlock
BehaviorRulesPromptBlock
SkillsCatalogPromptBlock
```

这些内容变化频率低。

而下面这些动态 block 通常不会走本地 static cache：

```text
SelfModelPromptBlock
LongTermMemoryPromptBlock
RecentContextPromptBlock
ActiveSkillsPromptBlock
MemoryBlockPromptBlock
```

因为它们可能随记忆、技能命中、retrieval 结果变化。

### 3. 本地 cache 优化什么

本地 prompt block cache 优化的是：

```text
少重复构造 prompt section
少重复扫描或读取稳定内容
让 prompt builder 更快
记录 debug_breakdown 里的 cache_hit
```

它不会减少模型 token 成本。

因为最终发给模型的 prompt 文本还是一样要发送。

### 4. 服务端 prompt cache / KV cache 存在哪里

服务端 prompt cache 在模型服务商侧。

例如 DeepSeek / OpenAI 兼容服务会根据重复 prompt 前缀复用 KV。

项目拿不到它的具体内容，也不会把 KV cache 存到本地。

项目只能通过 provider 返回的 usage 看到统计：

```text
prompt_cache_hit_tokens
prompt_cache_miss_tokens
```

再记录到：

```text
observe/observe.db
```

### 5. 服务端 cache 优化什么

服务端 prompt cache 优化的是：

```text
模型推理成本
首 token 延迟
重复 system prompt / prefix 的计算
```

它依赖 prompt 前缀稳定。

所以项目才会尽量让：

```text
Identity
BehaviorRules
SkillsCatalog
SELF.md
MEMORY.md
SessionContext
```

这些相对稳定的内容排在前面。

高频变化的内容，例如：

```text
retrieved_memory
active_skills
turn_injection
当前用户消息
```

放在后面或 context frame 中，减少对前缀 cache 的破坏。

### 6. 两者关系是什么

它们可以配合，但层级不同。

```text
本地 prompt block cache
  帮项目更快组装 prompt

服务端 prompt cache
  帮模型服务更快处理重复 prompt
```

本地 cache 命中，不代表服务端 KV cache 一定命中。

服务端 KV cache 命中，也不依赖本地 `SectionCache` 是否命中。

真正影响服务端 cache 的，是最终发送给模型的 token 前缀是否稳定。

### 面试总结

可以这样回答：

```text
本地 prompt block cache 和服务端 prompt cache 不是一回事。本地 cache 是 SystemPromptBuilder 里的 SectionCache，一个进程内 dict，用 workspace、section name、cache signature 缓存静态 prompt block 的渲染文本，主要减少本地重复构造 prompt 的开销。服务端 prompt cache / KV cache 存在模型服务商侧，缓存的是重复 prompt token 的模型计算结果，项目本地只记录 prompt_cache_hit_tokens 和 prompt_cache_miss_tokens 到 observe/observe.db。前者优化 prompt 组装，后者优化模型推理成本和延迟。
```

### 可以改进的地方

- Dashboard 同时展示本地 section cache hit 和服务端 KV cache hit。
- 给每个 prompt block 记录 hash，定位哪一块导致服务端 cache miss。
- 对动态 block 的位置做更严格约束，减少破坏稳定前缀。
- 将 `SELF.md` / `MEMORY.md` 的变更时间和 cache miss 关联展示。
- 给 `SectionCache` 增加大小限制和清理策略，避免长进程里无限增长。

## Q33: 为什么 system prompt 的 prompt blocks 要按稳定性和优先级排序？这和 prompt cache 有什么关系？

prompt blocks 的顺序不是随便拼的。

这个项目按 priority 组织 system prompt，大致顺序是：

```text
10 Identity
15 BehaviorRules
20 SkillsCatalog
30 SelfModel
35 LongTermMemory
40 SessionContext
45 RecentContext
50 ActiveSkills
55 RetrievedMemory
```

越靠前的内容越稳定，越靠后的内容越动态。

### 为什么稳定内容要放前面

服务端 prompt cache 通常更依赖稳定前缀。

如果 prompt 前面部分每轮都变化，那么后面再稳定也很难复用前缀缓存。

所以项目把最稳定的内容放前面：

```text
Identity
BehaviorRules
SkillsCatalog
SelfModel
LongTermMemory
```

这些内容变化频率低。

而高频变化内容放后面：

```text
ActiveSkills
RetrievedMemory
当前用户消息
```

这样即使后面动态内容变化，前面的稳定前缀仍然更容易命中服务端 prompt cache。

### 不同 block 的稳定性

可以按变化频率理解：

```text
最稳定：
  Identity
  BehaviorRules

低频变化：
  SkillsCatalog
  SELF.md
  MEMORY.md

中频变化：
  SessionContext
  RECENT_CONTEXT.md

高频变化：
  ActiveSkills
  retrieved_memory
  turn_injection
  current user message
```

这就是为什么 `PENDING.md -> MEMORY.md` 要低频合并。

因为 `MEMORY.md` 位于比较靠前的长期记忆 block，如果频繁变化，会破坏较大一段 system prompt 前缀。

### 为什么这也有助于上下文管理

排序不仅是为了 cache。

它还让模型看到的上下文层次更清楚：

```text
先看身份和行为规则
再看长期稳定认知
再看当前 session 信息
再看近期上下文
最后看本轮动态检索和用户消息
```

这能减少模型混淆信息来源。

例如：

- 系统身份规则不应该被 retrieved memory 覆盖。
- 当前用户消息比旧记忆优先级更高。
- retrieved memory 是候选上下文，不是用户本轮陈述。
- active skills 是本轮能力提示，不是长期规则。

### 为什么不能把 retrieved_memory 放前面

`retrieved_memory` 每轮都可能不同。

如果把它放在 system prompt 前面，几乎每轮 prompt 前缀都会变。

这会带来两个问题：

- 服务端 prompt cache 命中率下降。
- 模型可能把检索记忆误当成更高优先级规则。

所以它适合放在后面，甚至放到 context frame 中，并明确标注是系统提供的候选上下文。

### 面试总结

可以这样回答：

```text
这个项目的 prompt blocks 按 priority 和稳定性排序，越稳定、越核心的内容越靠前，例如 Identity、BehaviorRules、SkillsCatalog、SelfModel、LongTermMemory；越动态的内容越靠后，例如 ActiveSkills、RetrievedMemory 和本轮用户消息。这样做一方面能让服务端 prompt cache 更容易命中稳定前缀，另一方面也能让模型区分系统规则、长期记忆、近期上下文和本轮动态检索的优先级。PENDING.md 低频合并到 MEMORY.md 也是为了避免长期记忆 block 高频变化，破坏 prompt cache。
```

### 可以改进的地方

- 给每个 prompt block 记录 hash 和变化原因。
- Dashboard 展示当前 system prompt 的 block 顺序、token 数和 cache 影响。
- 对高频动态 block 固定放入 context frame，减少污染 system prompt 前缀。
- 当某个低频 block 变化时标记“本轮可能 cache miss”。
- 为不同场景设计不同 prompt block 排序策略，例如 coding、proactive、memory optimizer。

## Q34: 为什么项目要把部分动态上下文放进 context frame，而不是全部放进 system prompt？

context frame 的作用是隔离高动态上下文。

项目不是把所有内容都塞进 system prompt，而是把一部分动态内容放进一个特殊的 user message：

```text
<system-reminder data-system-context-frame="true">

以下内容由系统提供，不是用户陈述，也不是助手结论。
只能作为候选上下文...

## active_skills
...

## recent_context
...

## retrieved_memory
...

</system-reminder>
```

这个 message 的 role 是：

```text
user
```

但内容里明确标记它是系统提供的 context frame，不是用户原话。

### context frame 里放什么

项目里默认会放这些动态 section：

```text
active_skills
recent_context
retrieved_memory
turn_injection
```

这些内容有共同特点：

- 每轮可能变化。
- 属于候选上下文。
- 不应该覆盖核心系统规则。
- 不适合污染稳定 system prompt 前缀。

### messages 的顺序是什么

最终模型输入顺序大致是：

```text
system prompt
  -> stable identity / behavior / long-term memory

history
  -> 最近对话

context frame
  -> 系统提供的本轮候选上下文

current user message
  -> 当前用户真正说的话
```

也就是：

```text
stable system -> history -> context frame -> current user message
```

这个顺序是有意设计的。

### 为什么不全部放 system prompt

如果把 `retrieved_memory`、`active_skills` 这类高动态内容都放进 system prompt，会有几个问题：

第一，破坏 prompt cache。

这些内容每轮都可能不同，放进 system prompt 会让 system prompt 高频变化。

第二，优先级容易混乱。

检索记忆只是候选上下文，不应该和系统身份、行为规则处在同一层级。

第三，容易让模型误判来源。

模型可能把 retrieved memory 当成用户本轮陈述，或者当成不可违背的系统规则。

第四，裁剪不方便。

动态 context frame 可以整体裁剪或按 section 裁剪，而不影响稳定 system prompt。

### 为什么它用 user message 承载

Chat Completions 格式里 system message 通常只有一个或少数几个。

项目已经把稳定身份、规则和长期记忆放进 system prompt。

动态上下文如果也不断改 system prompt，会影响稳定前缀。

所以项目把它包装成一个特殊 user message，放在当前用户消息之前。

这样模型能在回答当前问题前看到这些候选上下文，但又能通过标记知道：

```text
这不是用户原话
也不是助手结论
只是系统提供的候选上下文
```

### 为什么它放在当前用户消息前面

因为 context frame 是为当前用户消息服务的。

放在当前用户消息前，模型处理当前问题时能参考它。

但最后一条仍然是用户真实输入，能保持对当前用户意图的聚焦。

### 面试总结

可以这样回答：

```text
context frame 是用来隔离高动态上下文的。项目把 active_skills、recent_context、retrieved_memory、turn_injection 这类每轮可能变化的内容，包装成 system-reminder 风格的 user message，放在 history 和当前用户消息之间。这样它们可以作为本轮候选上下文被模型看到，但不会污染稳定 system prompt，也不会破坏前缀 prompt cache。同时 context frame 明确标注“这是系统提供的候选上下文，不是用户陈述，也不是助手结论”，避免模型混淆来源。
```

### 可以改进的地方

- Dashboard 单独展示 context frame 内容。
- 对 context frame 每个 section 加来源和 token 数。
- 给 retrieved memory 增加 citation，减少模型误用旧记忆。
- 对 context frame 加更明确的优先级提示，例如“当前用户消息优先于旧记忆”。
- 当 context frame 过长时，按 section 和相关性分数裁剪。

## Q35: 这个项目的 memory retrieval pipeline 是怎么工作的？是不是搜到什么就直接塞进 prompt？

不是。

这个项目的 memory retrieval 不是“搜到什么就塞什么”，而是一个分层流程：

```text
用户消息
  -> 构造 RetrievalRequest
  -> 转成 MemoryEngineRetrieveRequest
  -> 选择 memory types / queries / scope
  -> 向量召回 + 关键词召回
  -> RRF 融合排序
  -> 按类型、分数、预算选择注入项
  -> 生成 retrieved_memory_block
  -> 放进 context frame / prompt
```

### 1. Agent 侧先构造检索请求

被动对话前，Agent 会把当前消息、session、channel、chat_id、history 等信息传给 retrieval pipeline。

`DefaultMemoryRetrievalPipeline` 做的事比较克制：

```text
RetrievalRequest
  -> MemoryEngineRetrieveRequest
```

它不自己决定复杂检索策略，而是把检索语义交给 MemoryEngine。

请求里会带：

```text
query = 当前用户消息
scope = session_key / channel / chat_id
context = history / session metadata
hints = 额外提示
```

### 2. MemoryEngine 决定查哪些类型

MemoryEngine 会根据 mode / hints 选择 memory types。

例如：

```text
mode = procedure
  -> 查 procedure / preference

mode = episodic
  -> 查 event / profile

默认
  -> 不限制 memory type
```

所以它不是永远查全部，也可以按任务类型收窄范围。

### 3. 查询可以有辅助 query

项目支持把一个原始 query 扩展成多路 query。

例如：

- procedure 模式会构造更适合流程规则召回的 query。
- 显式 recall 里会生成 event/general 风格的 hypothesis。
- 部分路径支持 HyDE 或 aux queries，用于提升语义召回。

但要注意：不是每一轮普通对话都必然走复杂 query rewrite。

更准确的说法是：

```text
检索框架支持 query 改写 / 辅助 query / HyDE；
具体是否启用取决于模式和配置。
```

### 4. 向量召回和关键词召回并行存在

`memory2.retriever` 里有两条 lane：

```text
vector lane
  query + aux_queries
  走 embedding 语义检索

keyword lane
  原始 query
  做关键词 / summary 匹配
```

为什么需要两条？

向量检索擅长语义相似：

```text
“我不喜欢压抑风格”
≈ “避免悬疑阴暗氛围”
```

关键词检索擅长精确字面命中：

```text
人名
项目名
工具名
日期
特定术语
```

两者互补。

### 5. RRF 融合排序

向量结果和关键词结果不是简单拼接。

项目会做 RRF merge：

```text
vector_items
keyword_items
  -> _rrf_merge(...)
  -> fused items
```

这样避免单一路召回决定最终结果。

语义相关和字面命中都可以进入候选。

### 6. 不是所有召回结果都会注入

召回只是候选。

真正注入 prompt 前，还要过一层 injection selection。

它会根据：

- memory_type
- score threshold
- 每类数量上限
- 字符预算
- procedure 是否有 tool_requirement
- happened_at 时间
- forced / normal / event 分组

来决定最终注入哪些。

例如：

```text
procedure + tool_requirement
  -> 可能进入【强制约束】记忆规则

procedure / preference
  -> 进入【流程规范】用户偏好与规则

event / profile
  -> 进入【相关历史】
```

最后生成的不是散乱列表，而是结构化的 memory block。

### 7. 注入还有预算控制

retriever 会应用字符预算：

```text
_inject_max_chars
```

如果内容太长，不会全部塞进 prompt。

但带强制约束的 procedure 会被优先保留。

这说明 retrieval pipeline 同时考虑：

```text
相关性
记忆类型
优先级
上下文预算
```

### 8. 还会产出 trace

pipeline 不只返回文本块，还返回 trace。

例如：

```text
injected_count
route_decision
rewritten_query
raw retrieval event
```

这些 trace 可以给 Dashboard / observe 用来调试：

- 召回了什么。
- 注入了几条。
- 为什么这轮用了某些记忆。
- 是否发生 query rewrite。

### 面试总结

可以这样回答：

```text
这个项目的 memory retrieval 不是搜到什么就直接塞进 prompt。被动对话前，DefaultMemoryRetrievalPipeline 会把当前消息、session scope、history 和 hints 转成 MemoryEngineRetrieveRequest；MemoryEngine 根据 mode/hints 选择 memory types 和 queries；底层 retriever 同时走 vector lane 和 keyword lane，再用 RRF 融合结果。召回结果还要经过 injection selection，根据 memory_type、score threshold、数量上限、字符预算和 procedure 的 tool_requirement 分组筛选，最终生成 retrieved_memory_block。这个 block 会带【强制约束】、【流程规范】、【相关历史】等结构化 section，并返回 trace 供观测。
```

### 可以改进的地方

- Dashboard 展示 vector lane、keyword lane、RRF 融合前后的结果。
- 给每条 injected memory 展示 score、memory_type、source_ref 和 scope。
- 对 query rewrite / HyDE 的启用条件做更清楚的配置化。
- 增加 reranker，对融合后的候选做二次排序。
- 做 retrieval eval，统计召回准确率、误召回率和 answer impact。

## Q36: 为什么 memory retrieval 要同时做向量召回和关键词召回？只用 embedding 不行吗？

只用 embedding 不够稳。

向量检索擅长语义相似，但不擅长所有场景。

这个项目采用 hybrid retrieval：

```text
vector lane
  负责语义相似召回

keyword lane
  负责字面关键词命中

RRF merge
  融合两路结果
```

### 向量召回擅长什么

向量召回适合处理表达不完全一致，但语义相关的内容。

例如：

```text
用户现在问：我不想要太压抑的设计

历史记忆：用户不喜欢悬疑阴暗风格
```

这两个句子关键词不完全一样，但语义相关。

embedding 更容易把它们召回。

### 关键词召回擅长什么

关键词召回适合精确匹配。

例如：

- 人名。
- 项目名。
- 工具名。
- 文件名。
- 日期。
- ID。
- 特定术语。

这些内容有时语义上不明显，但字面非常关键。

比如：

```text
Akashic
memory2.db
Qwen
Telegram
```

如果只靠 embedding，可能会把语义相近但字面不匹配的内容排到前面。

关键词检索能补这个短板。

### 为什么需要 RRF 融合

两路召回不能简单拼接。

否则可能出现：

- 向量结果太多，淹没关键词命中。
- 关键词结果太多，召回语义相关性下降。
- 重复 item 出现多次。

RRF merge 的作用是把两路排名融合：

```text
vector_items
keyword_items
  -> RRF
  -> fused_items
```

这样语义相关和字面命中都能进入候选。

### 为什么这对 Agent memory 特别重要

Agent memory 里有很多不是标准文档的内容。

例如：

```text
用户偏好
历史事件
工具规则
具体项目名
对话中出现的临时 ID
```

这类数据有时要靠语义召回，有时要靠精确命中。

所以 hybrid retrieval 比单纯向量库更可靠。

### 面试总结

可以这样回答：

```text
这个项目的 memory retrieval 同时使用向量召回和关键词召回，是因为两者解决的问题不同。向量召回适合语义相似，比如用户表达换了一种说法；关键词召回适合人名、项目名、工具名、日期、ID 等精确字面命中。只用 embedding 可能漏掉关键实体，只用关键词又无法处理语义改写。项目通过 vector lane 和 keyword lane 分别召回，再用 RRF 融合排序，最后再做注入筛选。这种 hybrid retrieval 更适合 Agent 长期记忆。
```

### 可以改进的地方

- 对不同 memory_type 设置不同的 vector/keyword 权重。
- 对实体类 query 增强关键词优先级。
- 增加 reranker，对 RRF 后的候选做二次判断。
- Dashboard 展示某条记忆来自 vector、keyword 还是两者都命中。
- 做 retrieval eval，统计纯向量、纯关键词、hybrid 三种方案的差异。

---

## Q37: 为什么 procedure memory 会有强制约束？它和 preference 有什么区别？

### 问题

面试官可能会问：

```text
你说这个项目里有 procedure memory，那它为什么会被当成强制约束？
它和普通 preference memory 有什么区别？
它是如何影响工具调用的？
```

### 答案

这个项目里，`preference` 和 `procedure` 的区别不只是分类名称不同，而是语义强度不同。

`preference` 表示用户偏好，通常是软约束。

例如：

```text
用户喜欢简洁回答。
用户希望先给结论再解释。
用户偏好中文说明。
```

这些信息会影响回答风格，但不一定强制改变执行流程。

`procedure` 表示未来遇到某类任务时，Agent 应该遵守的执行规则。

例如：

```text
遇到代码修改任务时，必须先阅读相关文件。
查询实时信息时，必须调用搜索工具。
执行某类操作前，必须先确认上下文。
```

所以 `procedure memory` 更像是“可执行的行为规范”，而不是普通背景信息。

### 项目里是如何区分的

在 memory 写入时，如果一条记忆被判断为 `procedure`，系统会检查它是否真的包含：

- 明确的工具要求。
- 或明确的执行步骤。

如果没有工具要求，也没有步骤，它会被降级为 `preference`。

这说明项目并不希望把所有偏好都升级成强规则。

可以理解为：

```text
preference = 用户希望 Agent 怎么表现
procedure = 用户要求 Agent 以后遇到某类任务必须怎么做
```

### 它如何影响工具调用

`procedure memory` 里可以带有 `tool_requirement`、`steps`、`rule_schema` 等结构化信息。

当记忆检索阶段命中这类 procedure，并且它包含工具要求时，系统会把它放进更强的上下文区域，例如：

```text
## 【强制约束】记忆规则（必须执行）
- [memory_id] xxx（必须调用工具：某工具）
```

这和普通偏好注入不一样。

普通偏好通常进入类似：

```text
## 【流程规范】用户偏好与规则
```

而带工具要求的 procedure 会被提升到“必须执行”的位置，直接影响模型后续是否应该调用工具。

### 为什么要这样设计

Agent 和普通聊天机器人的一个关键区别是：Agent 会做动作。

只把记忆当作参考信息是不够的，因为某些记忆本质上是在约束行动。

例如用户长期要求：

```text
涉及实时新闻时必须联网查询。
修改代码前必须先看现有实现。
生成总结前必须先读取最新文档。
```

这些不是简单偏好，而是执行流程规则。

如果模型忽略这些规则，可能会造成错误工具调用、漏调用工具，甚至基于过期信息回答。

所以项目把 procedure memory 设计成比 preference 更强的上下文信号。

### 面试总结

可以这样回答：

```text
这个项目把 memory 分成 preference 和 procedure，是因为它们对 Agent 行为的约束强度不同。preference 是软偏好，主要影响回答风格和服务方式；procedure 是可执行规则，通常带有步骤或工具要求，会影响 Agent 的行动路径。项目在写入时会校验 procedure 是否包含 tool_requirement 或 steps，否则会降级为 preference；在检索时，如果命中的 procedure 带有工具要求，会被注入到“强制约束”区域，提示模型必须调用对应工具。因此 procedure memory 是连接长期记忆和工具调用策略的关键设计。
```

### 可以改进的地方

- 给 procedure 增加更精确的触发条件，避免误触发。
- 给强制工具调用增加置信度阈值。
- 区分“必须调用工具”和“建议调用工具”。
- 在 Dashboard 中展示哪条 procedure memory 触发了工具要求。
- 为 procedure retrieval 增加专门测试，验证触发准确率。

---

## Q38: memory 写入为什么要分成 post-response 和 consolidation 两条链路？

### 问题

面试官可能会问：

```text
这个项目里长期记忆是怎么写入的？
为什么不在每轮回复后直接把所有有用信息都写入 memory2.db？
post-response memory 和 consolidation memory 的边界是什么？
```

### 答案

这个项目的 memory 写入不是单一路径，而是分成两类：

```text
每轮回复后 post-response ingest
窗口期整理 consolidation ingest
```

它们解决的问题不同。

### post-response 主要处理什么

每轮对话真正提交后，系统会发布 `TurnCommitted`。

默认 memory 插件监听这个事件，然后入队一个 `TurnIngested`：

```text
TurnCommitted
  -> TurnIngested
  -> PostResponseMemoryWorker
```

但当前实现里，`PostResponseMemoryWorker` 不是负责把每轮对话都抽成长期记忆。

它主要做两件事：

- 收集本轮显式 `memorize` 工具已经写入的记忆，避免后续误删。
- 检测用户是否明确否定旧规则或旧偏好，然后 supersede 旧记忆。

也就是说，post-response 更偏“即时纠错/废弃旧记忆”，而不是大规模隐式抽取。

### consolidation 主要处理什么

`consolidation` 发生在一段对话窗口整理时。

它会把滑动窗口外、尚未整理的历史对话交给整理流程，生成：

- `HISTORY.md` 里的时间线事件。
- `RECENT_CONTEXT.md` 里的近期摘要。
- `PENDING.md` 里的长期记忆候选。
- `memory2.db` 里的可检索 memory item。

在 memory2 层，`ConsolidationCommitted` 会触发两类写入：

```text
history_entry -> memory_type="event"
conversation  -> implicit profile / preference / procedure
```

其中：

- `history_entry` 会被写成 `event`，用于情景记忆检索。
- 整段 `conversation` 会经过 LLM 抽取隐式长期记忆，写成 `profile`、`preference`、`procedure`。

### 为什么不每轮都直接抽取长期记忆

因为每轮都直接写长期记忆会有几个问题。

第一，噪声太多。

很多对话只是临时任务、追问、确认、调试输出，不值得成为长期记忆。

第二，成本太高。

每轮都调用 LLM 做长期记忆抽取，会增加延迟和 token 消耗。

第三，容易重复和冲突。

同一件事可能在连续多轮里被反复提到，如果每轮都写，就会产生重复 memory。

第四，难以判断稳定性。

长期记忆应该记录相对稳定的信息，而不是每轮的临时表达。

consolidation 通过窗口级整理，可以看到更完整的上下文，更适合判断哪些信息值得沉淀。

### 设计上的分工

可以这样理解：

```text
post-response = 快速响应本轮副作用，尤其是纠错和 supersede
consolidation = 批量整理历史对话，提取 event 和长期稳定记忆
```

这是一种“在线轻处理 + 离线重整理”的设计。

它既不阻塞主回复链路，又能在后续整理中提升长期记忆质量。

### 面试总结

可以这样回答：

```text
这个项目没有把每轮对话都直接写进长期记忆，而是把 memory 写入分成 post-response 和 consolidation 两条链路。post-response 在 TurnCommitted 后异步执行，当前主要负责处理显式 memorize 结果和用户对旧记忆的否定，从而 supersede 错误的 preference/procedure。真正的隐式长期记忆抽取放在 consolidation 阶段，系统基于一个对话窗口生成 event、profile、preference、procedure，再写入 markdown memory 和 memory2.db。这样做可以减少噪声、降低每轮延迟、避免重复冲突，也让长期记忆更稳定。
```

### 可以改进的地方

- 给 post-response 和 consolidation 的写入结果都增加 trace，方便调试来源。
- 为隐式抽取结果增加置信度和人工审核开关。
- 对高价值信息允许 post-response 立即写入，对低价值信息延迟到 consolidation。
- 增加重复记忆检测评估，衡量 consolidation 的去重效果。
- 在 Dashboard 中展示某条 memory 是来自显式工具、post-response 还是 consolidation。

---

## Q39: 既然有自动 consolidation，为什么还需要显式 memorize 工具？

### 问题

面试官可能会问：

```text
这个项目已经有自动 memory consolidation 了，为什么还要提供 memorize 工具？
用户明确说“记住”的时候，系统为什么不等 consolidation 自动提取？
memorize 和自动长期记忆抽取的边界是什么？
```

### 答案

`memorize` 工具解决的是“用户明确要求立即记住”的场景。

`consolidation` 解决的是“系统从历史对话中自动提炼长期信息”的场景。

两者不是重复关系，而是优先级和确定性不同。

### memorize 的作用

`memorize` 是显式写入工具。

它的工具描述里明确要求：

```text
仅在用户明确表达意图时调用
例如：记住、以后、下次、你要
```

也就是说，当用户直接说：

```text
以后回答我都先给结论。
记住：查询实时资料时必须先联网。
下次改代码前先读现有实现。
```

Agent 不应该等后续 consolidation 猜测，而应该立即调用 `memorize` 写入长期记忆。

### memorize 写入了什么

`memorize` 工具参数包括：

- `summary`
- `memory_type`
- `tool_requirement`
- `steps`

它会调用默认 memory engine 的 `remember()`。

写入时会带上当前会话 scope：

```text
channel
chat_id
session_key = channel:chat_id
```

同时来源会绑定到当前用户消息的 `source_ref`，方便以后追溯这条记忆来自哪句话。

如果写入的是 `procedure`，系统还会检查是否包含工具要求或执行步骤。

没有工具要求、也没有步骤的 `procedure` 会被降级为 `preference`。

### 和 consolidation 的区别

`consolidation` 是批处理、延迟整理。

它适合从一段对话中提取：

- 发生过的事件。
- 用户画像。
- 长期偏好。
- 行为规则。

但它不是实时承诺。

如果用户明确说“记住这个规则”，等待 consolidation 有几个问题：

- 可能延迟生效。
- 可能被模型判断为不值得保存。
- 可能因为窗口整理失败而漏掉。
- 用户明确意图没有被即时满足。

所以显式 `memorize` 是更强、更直接的写入通道。

### 为什么不能什么都用 memorize

`memorize` 也不能滥用。

因为它是长期写入工具，风险级别是 `write`。

项目的工具描述明确禁止记录很多不适合长期保存的内容，比如：

- 第三方行为描述。
- 用户个人印象。
- 普通知识分享。
- 已存储偏好的重复记录。
- 时效性事件。
- 系统连接状态。
- 单次任务的专项操作规范。

这说明 `memorize` 只适合用户明确授权、并且确实有长期价值的信息。

### 和 post-response worker 的关系

每轮回复后，`PostResponseMemoryWorker` 会扫描本轮工具调用链。

如果本轮调用过 `memorize`，worker 会收集新写入的 item id，放进 protected ids。

这样后续做旧记忆失效判断时，不会把本轮刚显式写入的新记忆误删。

也就是说：

```text
memorize = 明确写入
post-response = 保护显式写入 + 处理旧记忆废弃
consolidation = 后续窗口级自动整理
```

### 面试总结

可以这样回答：

```text
虽然项目有自动 consolidation，但仍然需要 memorize 工具，因为两者语义不同。consolidation 是延迟的自动整理，适合从历史对话中提取长期信息；memorize 是用户明确要求“记住”时的即时写入通道，优先级更高、确定性更强。memorize 会把 summary、memory_type、tool_requirement、steps 写入 memory engine，并绑定当前 channel/chat scope 和 source_ref。如果是 procedure，还会生成 rule_schema 和触发标签。post-response worker 还会保护本轮显式写入的 memory，避免后续 supersede 误删。因此 memorize 是用户授权的显式长期记忆写入口，而 consolidation 是系统自动的长期记忆沉淀流程。
```

### 可以改进的地方

- 在工具返回中展示最终写入的 `actual_type`，例如 procedure 是否被降级为 preference。
- 对 `memorize` 增加更严格的重复检测提示。
- 对敏感或高风险记忆增加二次确认。
- 在 Dashboard 中标记 memory 来源是 `memorize_tool` 还是 `consolidation`。
- 给用户提供查看、撤销本轮新增记忆的交互入口。

---

## Q40: 既然每轮会被动注入记忆，为什么还需要 recall_memory 工具？

### 问题

面试官可能会问：

```text
这个项目每轮对话前不是已经会自动检索并注入 retrieved_memory_block 吗？
那为什么还需要 recall_memory 工具？
被动检索和显式 recall_memory 的区别是什么？
```

### 答案

被动记忆注入和 `recall_memory` 工具解决的是两个不同问题。

被动注入解决的是：

```text
在模型回答前，系统自动补充可能相关的长期记忆。
```

`recall_memory` 解决的是：

```text
当用户明确问历史、偏好、做过什么、记不记得时，模型主动检索记忆数据库。
```

一个是自动上下文增强，一个是显式查找工具。

### 被动注入是怎么走的

每轮被动对话准备上下文时，流程大致是：

```text
DefaultContextStore.prepare()
  -> 读取 session history
  -> DefaultMemoryRetrievalPipeline.retrieve()
  -> MemoryEngine.retrieve()
  -> 返回 retrieved_memory_block
  -> 注入 prompt
```

这条链路的特点是自动发生。

用户没有明确问记忆时，系统也可以根据当前消息召回相关偏好、流程规则或历史线索。

它适合解决：

- 回答风格偏好。
- 常用流程规范。
- 和当前任务相关的长期背景。
- 带工具要求的 procedure 约束。

### recall_memory 是什么

`recall_memory` 是一个显式工具。

它的工具描述里明确说，它用于检索长期记忆中的：

- 提炼事实。
- 偏好。
- 流程。
- 历史事件线索。

当用户问：

```text
你还记得我之前说过什么吗？
我以前做过这个功能吗？
我通常喜欢什么风格？
上周我们聊过哪些重构？
```

模型应该主动调用 `recall_memory`，而不是只依赖被动注入。

### 为什么被动注入不能替代 recall_memory

第一，被动注入有预算限制。

系统只会把少量最高优先级的记忆注入 prompt，不能保证覆盖用户想查的全部历史。

第二，被动注入是系统猜测。

它根据当前消息自动判断相关内容，但用户有时是在问一个明确的历史问题，需要更定向的检索。

第三，`recall_memory` 支持显式参数。

例如：

```text
memory_type
search_mode
time_filter
limit
```

这让模型可以选择：

- semantic：按 query 做向量 + 关键词召回。
- grep：按时间范围列出 event 时间线。
- time_filter：限定 today、recent_7d、某个日期范围。

被动注入不适合承担这种精确检索交互。

第四，`recall_memory` 有引用协议。

它返回 `id`、`memory_type`、`summary`、`source_ref` 等信息，并要求最终使用这些记忆时输出：

```text
§cited:[id1,id2,...]§
```

这让“回答基于哪些记忆”变得可追踪。

### 记忆摘要不是最终证据

`recall_memory` 的一个重要设计是：它返回的是 L1 记忆线索层，不是原文证据。

工具描述明确要求：

```text
如果结果相关且有 source_ref，需要继续调用 fetch_messages(source_refs) 取原文。
```

所以正确链路是：

```text
recall_memory
  -> 找到可能相关的记忆摘要和 source_ref
  -> fetch_messages
  -> 读取原始对话证据
  -> 再回答用户
```

这比直接根据摘要回答更可靠。

### 面试总结

可以这样回答：

```text
被动记忆注入和 recall_memory 是两层不同机制。被动注入发生在每轮上下文准备阶段，DefaultContextStore 会通过 DefaultMemoryRetrievalPipeline 调用 MemoryEngine，把少量相关记忆作为 retrieved_memory_block 注入 prompt，主要用于自动增强回答和约束行为。recall_memory 是显式工具，当用户主动询问历史、偏好、做过什么时，模型可以带 memory_type、search_mode、time_filter、limit 做定向检索。它返回的是记忆摘要线索，不是最终证据；如果有 source_ref，应该继续 fetch_messages 取原文。因此 recall_memory 不能被被动注入替代，它负责可控、可追溯、面向问题的主动记忆查询。
```

### 可以改进的地方

- 在被动注入 trace 中标明哪些记忆被注入、哪些因预算被丢弃。
- `recall_memory` 返回结果中区分“可直接参考”和“必须 fetch 原文确认”。
- 对纯时间回顾类问题自动选择 `grep + time_filter`。
- 在 Dashboard 中同时展示被动注入和显式 recall 的检索结果差异。
- 增加评估集，比较被动注入是否覆盖用户显式历史问题。

---

## Q41: recall_memory、search_messages、fetch_messages 三者怎么分工？

### 问题

面试官可能会问：

```text
这个项目里已经有 recall_memory 了，为什么还需要 search_messages 和 fetch_messages？
这三个工具分别解决什么问题？
为什么 recall_memory 的结果不能直接当最终证据？
```

### 答案

这三个工具对应三层不同能力：

```text
recall_memory   = 长期记忆语义线索
search_messages = 原始消息关键词定位
fetch_messages  = 原始消息证据读取
```

它们不是重复工具，而是从“找线索”到“取证据”的链路。

### recall_memory：找长期记忆线索

`recall_memory` 检索的是长期记忆数据库里的提炼结果。

它返回的通常是：

- 记忆 id。
- memory_type。
- summary。
- happened_at。
- score。
- source_ref。

它适合回答这类问题的第一步：

```text
你还记得我以前做过什么吗？
我有什么偏好？
我们之前聊过某个功能吗？
最近几天发生过哪些相关事件？
```

但是它返回的是摘要，不是原始对话。

摘要可能经过 consolidation、改写、压缩、去重，所以不能直接当作事实证据。

### search_messages：做关键词定位

`search_messages` 是对原始 session history 做 grep 式搜索。

它适合查找：

- 某个文件名。
- 某个报错。
- 某条命令。
- 某个配置值。
- 某个原话关键词。

例如：

```text
之前哪里提过 uv.lock？
我有没有发过这个报错？
哪个消息里出现过 akashic-agent？
```

它返回的是命中消息的预览和 `source_ref`。

但预览仍然不能作为最终证据，因为它可能被截断，也缺少完整上下文。

所以如果最终回答依赖具体事实，还要继续调用 `fetch_messages`。

### fetch_messages：读取原文证据

`fetch_messages` 根据 message id 或 `source_ref` 读取原始历史消息。

它是三条链路里唯一可以直接作为最终证据的工具。

它还能通过 `context` 参数扩展前后文：

```text
fetch_messages(source_ref="...", context=3)
```

这样可以还原某条消息前后的完整上下文。

项目工具描述里明确要求：

```text
回答依赖具体时间、原话、金额、配置值、是否发生过时，需要 fetch_messages 取证。
```

### 正确使用链路

如果用户问长期记忆或历史事实，常见链路是：

```text
recall_memory
  -> 找到相关 memory summary 和 source_ref
  -> fetch_messages
  -> 基于原文回答
```

如果 `recall_memory` 没有结果，或者结果像是元对话噪声，可以补充：

```text
search_messages
  -> 找到关键词命中的 source_ref
  -> fetch_messages
  -> 基于原文回答
```

也就是说：

```text
recall_memory 负责“语义上可能相关”
search_messages 负责“字面上出现过”
fetch_messages 负责“原文证据确认”
```

### 为什么要分三层

如果只用 `recall_memory`，系统可能会因为摘要压缩而丢失细节。

如果只用 `search_messages`，系统找不到语义相近但字面不同的历史内容。

如果只用 `fetch_messages`，模型必须先知道具体 message id，否则无法定位。

所以三者组合起来，形成更可靠的历史查询链路。

### 面试总结

可以这样回答：

```text
这个项目把历史查询拆成 recall_memory、search_messages、fetch_messages 三层。recall_memory 查长期记忆摘要，适合语义召回历史事实、偏好和流程，但它只是 L1 线索层，不能直接当最终证据；search_messages 对原始 session history 做关键词搜索，适合定位文件名、报错、命令、配置项等字面信息，但返回的是预览；fetch_messages 根据 source_ref 读取原始消息和上下文，是最终可引用的证据层。正确链路通常是 recall_memory 或 search_messages 先定位 source_ref，再用 fetch_messages 取原文后回答。
```

### 可以改进的地方

- 在 `recall_memory` 结果里标注“建议 fetch”的强度。
- 对 `search_messages` 命中结果增加更好的上下文摘要。
- 让 `fetch_messages` 支持一次性展开 memory item 的多个 source_ref。
- 在 Dashboard 中展示从 recall/search 到 fetch 的完整证据链。
- 对引用协议做自动校验，防止模型用了记忆却漏掉 citation。

---

## Q42: forget_memory 为什么是标记 superseded，而不是物理删除？

### 问题

面试官可能会问：

```text
这个项目里 forget_memory 为什么不是直接删除记忆？
把 memory item 标记为 superseded 有什么好处？
如果错误记忆还留在数据库里，会不会继续被召回？
```

### 答案

`forget_memory` 的作用不是物理删除，而是把已确认错误的记忆标记为：

```text
status = "superseded"
```

也可以理解为“退休”或“失效”。

这样做的核心原因是：长期记忆需要可审计、可追溯、可纠错，而不是简单删除。

### forget_memory 的使用前提

工具描述里要求很严格：

```text
只在用户明确纠正你，并且已经先用 recall_memory 确认 summary 与错误内容吻合时调用。
```

也就是说，不能凭感觉删除。

正确流程通常是：

```text
用户指出记忆错误
  -> recall_memory 找到相关 memory item
  -> 确认 summary 确实匹配错误内容
  -> forget_memory(ids)
  -> 如有正确版本，再 memorize 写入新记忆
```

这个流程防止模型误删无关记忆。

### 为什么不物理删除

第一，保留审计痕迹。

如果直接删除，就不知道系统曾经记错过什么，也无法分析错误来源。

保留 superseded item 可以追溯：

- 这条记忆是什么。
- 它来自哪个 `source_ref`。
- 它什么时候被写入。
- 它后来为什么不应该再使用。

第二，避免误删不可恢复。

如果模型误删了正确记忆，物理删除很难恢复。

软失效至少保留原始条目，Dashboard 或维护工具还可以查看。

第三，支持记忆演化。

长期记忆不是静态表，而是会不断更新。

例如用户原来喜欢 A，后来不喜欢 A 了。

此时旧记忆不应该继续影响回答，但它仍然是历史状态的一部分。

所以更合理的是：

```text
旧偏好 -> superseded
新偏好 -> active
```

第四，便于去重和强化。

写入新记忆时，系统会对高相似旧的 `preference` / `procedure` 做 supersede，避免同类偏好堆积。

同时，如果相同 content_hash 的记忆后来再次被写入，底层 upsert 逻辑还可以把 superseded 条目重新激活并增加 reinforcement。

这说明 superseded 不只是删除标记，也参与记忆生命周期管理。

### superseded 会不会继续被召回

正常不会。

memory2 的检索默认只查：

```text
status = "active"
```

包括向量检索、事件时间线查询、procedure 关键词匹配等普通召回路径，默认都会过滤掉 `superseded` 条目。

所以被 `forget_memory` 失效的记忆不会继续进入普通回答上下文。

除非 Dashboard 或维护接口显式要求 `include_superseded`，才会看到这些失效条目。

### 面试总结

可以这样回答：

```text
这个项目里的 forget_memory 不是物理删除，而是把 memory item 标记为 status='superseded'。这样做是为了保留审计痕迹、避免误删不可恢复，并支持长期记忆的演化。用户纠正错误记忆时，正确流程是先 recall_memory 找到匹配条目，再 forget_memory 将其失效，如果用户提供了正确版本，再用 memorize 写入新记忆。普通检索默认只查 active 条目，所以 superseded 记忆不会继续被召回。相比直接删除，软失效更适合 Agent 长期记忆系统。
```

### 可以改进的地方

- 给 `forget_memory` 结果记录操作原因，例如用户哪句话触发了失效。
- 建立 memory relation，明确新记忆 supersede 了哪条旧记忆。
- Dashboard 中展示 active/superseded 的时间线变化。
- 对高风险遗忘操作增加二次确认。
- 增加自动检测：如果回答引用了 superseded item，直接报警。

---

## Q43: memory 检索为什么不只靠 embedding 相似度？

### 问题

面试官可能会问：

```text
这个项目已经用了向量检索，为什么还要引入 reinforcement、emotional_weight、hotness、关键词召回和 RRF？
只按 embedding 相似度排序不可以吗？
```

### 答案

只靠 embedding 相似度不够。

Agent memory 不是普通文档检索，它存的是：

- 用户偏好。
- 历史事件。
- 操作规则。
- 工具调用约束。
- 反复出现的重要事实。

这些记忆的“重要性”不完全等于“语义相似度”。

### embedding 相似度解决什么

embedding 相似度解决的是：

```text
当前 query 和 memory summary 在语义上是否接近。
```

例如用户问：

```text
我之前做过这个功能吗？
```

系统可以召回语义相近的历史事件。

但 embedding 有几个短板：

- 对文件名、ID、工具名、项目名等精确文本不稳定。
- 不能判断某条记忆是否被反复确认。
- 不能判断某条记忆是否近期更重要。
- 不能体现某条记忆的情绪或重要程度。

所以项目在 embedding 之外又引入了其他信号。

### reinforcement 是什么

`reinforcement` 表示一条记忆被重复写入、重复确认或重复使用的强度。

如果同样的内容多次出现，系统不会无限新增重复条目，而是增加已有条目的 reinforcement。

这表示：

```text
这条记忆更稳定、更常用、更值得保留。
```

在关键词检索里，排序也会参考 reinforcement：

```text
ORDER BY kw_score DESC, reinforcement DESC
```

也就是说，关键词命中一样时，被强化过的记忆会排得更前。

### emotional_weight 是什么

`emotional_weight` 是记忆的重要程度信号，范围通常是 0-10。

它不是简单情绪标签，而是帮助系统判断某条记忆是否应该衰减得慢一点。

在 hotness 计算里，`emotional_weight` 会影响有效半衰期：

```text
emotional_weight 越高，有效 half-life 越长
```

也就是说，高权重记忆不会因为时间过去就很快降权。

### hotness 是什么

项目里的 hotness 大致由两个因素构成：

```text
频度 reinforcement
时间衰减 recency
```

再结合 emotional_weight 调整时间衰减速度。

最终向量召回里的分数不是纯 semantic score，而是：

```text
final = (1 - alpha) * semantic + alpha * hotness
```

默认 `hotness_alpha` 大约是 `0.20`。

这表示语义相似度仍然是主导，但近期、反复确认、重要的记忆会得到适度加权。

### 为什么还要关键词召回

关键词召回补的是 embedding 的精确匹配短板。

例如：

```text
akashic-agent
uv.lock
memory2.db
telegram:123
某个具体报错
```

这些内容语义上未必明显，但字面命中非常关键。

所以项目同时做：

```text
vector lane
keyword lane
```

然后用 RRF 融合两路结果。

### RRF 的作用

RRF 不是简单把两个列表拼起来。

它会根据每条结果在向量召回和关键词召回中的排名综合打分。

这样可以避免：

- 向量结果淹没关键词命中。
- 关键词结果淹没语义相关结果。
- 同一个 item 重复出现。

最终结果既考虑语义相关，也考虑字面命中。

### 面试总结

可以这样回答：

```text
这个项目的 memory 检索不只靠 embedding，因为 Agent memory 的价值不只取决于语义相似度。embedding 负责语义相关性，但它无法很好处理文件名、ID、工具名等精确匹配，也无法表达一条记忆是否被反复确认、是否近期重要、是否情绪权重高。项目通过 reinforcement 表示重复确认，通过 emotional_weight 调整记忆衰减，通过 hotness 把频度和时间衰减融合进向量分数，公式大致是 final=(1-alpha)*semantic+alpha*hotness。同时项目还有 keyword lane，并用 RRF 融合 vector 和 keyword 两路结果。这样比单纯向量检索更适合长期 Agent memory。
```

### 可以改进的地方

- 为不同 memory_type 设置不同的 `hotness_alpha`。
- 对 `procedure` 降低时间衰减，避免长期流程规则过快失效。
- 对 `event` 增强时间过滤和 recency 权重。
- 在 Dashboard 展示 `_score_debug`，让用户看到 semantic、hotness、final。
- 建立检索评估集，比较 pure vector、hybrid、hotness fusion 的效果。

---

## Q44: embedding 召回的内容是不是按照 reinforcement 等方式排序？

### 问题

我自己的问题：

```text
也就是说，这里面 embedding 召回的内容按照 reinforcement 等方式进行排序？
```

### 答案

接近，但要说得更准确一点：

```text
不是单独按 reinforcement 排序，
而是先算 embedding 语义相似度，再把 hotness 融合进去形成最终 score。
```

向量召回里核心分数大致是：

```text
final = (1 - alpha) * semantic + alpha * hotness
```

其中：

- `semantic` 来自 embedding 相似度。
- `hotness` 来自 reinforcement、updated_at、emotional_weight。
- `alpha` 控制 hotness 占比，当前默认大约是 `0.20`。

所以向量结果最终不是纯 embedding 排序，而是：

```text
语义相似度为主
+ 近期性
+ 重复确认次数
+ 情绪/重要性权重
```

### reinforcement 在哪里起作用

`reinforcement` 不会完全替代 embedding 相似度。

它主要影响 hotness：

```text
reinforcement 越高，hotness 越高
```

也就是说，如果两条记忆语义相似度接近，那么被多次确认、反复出现的记忆更可能排在前面。

但如果一条记忆语义上完全不相关，仅靠 reinforcement 通常不应该排到前面。

### emotional_weight 在哪里起作用

`emotional_weight` 会影响记忆的时间衰减速度。

权重越高，有效 half-life 越长。

可以理解为：

```text
重要记忆衰减慢
普通记忆衰减快
```

### 还要注意关键词召回

项目不是只有 embedding lane。

完整流程更像：

```text
vector lane:
  semantic + hotness -> vector result ranking

keyword lane:
  keyword_score + reinforcement -> keyword result ranking

RRF:
  merge vector result + keyword result
```

所以最终进入候选集的排序，还会受到关键词召回和 RRF 融合影响。

### 面试总结

可以这样回答：

```text
严格来说，不是 embedding 召回后单纯按 reinforcement 排序。项目的向量召回会先计算 embedding 相似度 semantic，然后在 hotness_alpha 大于 0 时融合 hotness，形成 final score。hotness 由 reinforcement、updated_at 和 emotional_weight 共同影响，所以被反复确认、近期更新、重要性更高的记忆会有一定加权。但 semantic 仍然是主导。另外项目还有 keyword lane，关键词结果会按 keyword_score 和 reinforcement 排序，最后 vector lane 和 keyword lane 再通过 RRF 融合。
```

---

## Q45: 检索出来的 memory 为什么不能全部注入 prompt？

### 问题

面试官可能会问：

```text
memory retrieval 已经召回了一批相关记忆，为什么不直接全部塞进 prompt？
为什么还要有 injection selection？
召回和注入有什么区别？
```

### 答案

召回和注入是两个阶段。

```text
召回 retrieval = 从 memory store 里找候选
注入 injection = 决定哪些候选真正进入 prompt
```

这两个阶段不能混在一起。

召回阶段可以尽量多找一些候选，保证不漏。

注入阶段必须严格筛选，保证 prompt 里只放最有价值、最相关、最安全的内容。

### 为什么不能全部注入

第一，prompt 有预算限制。

长期记忆可能很多，如果全部注入，会快速挤占上下文窗口，影响当前任务、历史对话和工具结果。

第二，召回结果不一定都足够可靠。

有些候选只是低分相似，可能是弱相关或误召回。

如果全部放进 prompt，模型可能被噪声误导。

第三，不同类型 memory 的优先级不同。

`procedure`、`preference`、`event`、`profile` 对当前回答的作用不同，不能用同一种方式塞进去。

第四，强制约束需要特殊处理。

带 `tool_requirement` 的 `procedure` 不是普通参考信息，而是会影响工具调用的规则。

它应该进入更高优先级区域，而不是和普通历史事件混在一起。

### 项目里的注入筛选逻辑

项目会先按 score 降序处理候选，然后根据 memory_type 和配置做筛选。

主要规则包括：

- 不同 memory_type 有不同阈值。
- `procedure` 默认阈值更高，例如 `0.66`。
- `preference`、`event`、`profile` 默认阈值较低，例如 `0.5`。
- 强制 procedure 有单独上限，例如最多 `3` 条。
- 普通 procedure/preference 有数量上限，例如最多 `4` 条。
- event/profile 有数量上限，例如最多 `4` 条。
- 最终注入文本还有总字符预算，例如 `max_chars = 6000`。

这说明系统不是“搜到就注入”，而是做了二次选择。

### 注入后的结构

被选中的记忆不是无结构拼接，而是分成几个 section：

```text
## 【强制约束】记忆规则（必须执行）

## 【流程规范】用户偏好与规则

## 【相关历史】你与当前用户的过往对话
```

这个结构很重要。

它让模型知道：

- 哪些是必须遵守的规则。
- 哪些是偏好和流程规范。
- 哪些只是相关历史背景。

这比一堆无序 bullet 更容易被模型正确使用。

### forced procedure 的特殊地位

如果命中的 `procedure` 带有 `tool_requirement`，并且开启了 `procedure_guard_enabled`，它会被放进：

```text
## 【强制约束】记忆规则（必须执行）
```

格式类似：

```text
- [id] 查询实时信息时必须联网（必须调用工具：web_search）
```

这类记忆可以绕过普通 score 阈值逻辑的一部分，优先进入强制约束区，但仍然受 forced 数量上限控制。

### 面试总结

可以这样回答：

```text
这个项目把 memory retrieval 和 injection selection 分成两个阶段。retrieval 负责从 memory2.db 里尽量找出相关候选，injection 负责决定哪些候选真的进入 prompt。不能把所有召回结果都注入，因为 prompt 有预算限制，低分候选可能带来噪声，不同 memory_type 的作用也不同。项目会按 score、memory_type 阈值、数量上限和字符预算筛选，并把结果分成【强制约束】、【流程规范】、【相关历史】三个 section。带 tool_requirement 的 procedure 会进入强制约束区，直接影响工具调用。这是上下文工程的一部分，而不是简单的检索拼接。
```

### 可以改进的地方

- 注入 trace 中展示每条候选被保留或丢弃的原因。
- 对不同任务动态调整 `procedure/preference/event/profile` 的注入上限。
- 给低置信度记忆增加更明确的提示，避免模型过度相信。
- 对强制约束区增加冲突检测，避免多个 procedure 互相矛盾。
- 根据当前 prompt 剩余 token 动态压缩相关历史 section。

---

## Q46: memory 检索前为什么要做 query rewrite？

### 问题

面试官可能会问：

```text
用户消息已经有了，为什么不直接拿用户原话去查 memory？
为什么还要把 history query 和 procedure query 分开改写？
```

### 答案

用户原话不一定适合直接检索 memory。

用户消息通常是面向对话的，而 memory summary 是面向存储和召回的。

例如用户说：

```text
你还记得我那个设备是什么吗？
```

如果直接用这句话查，关键词是“那个设备”，语义很模糊。

更适合检索的 query 应该是：

```text
用户使用的设备型号
```

所以 query rewrite 的作用是把“对话表达”改写成“记忆库容易命中的摘要表达”。

### 为什么要判断是否需要查历史

不是每条用户消息都需要查历史。

例如：

```text
你好
继续
解释一下这个概念
以后回答先给结论
```

这些消息不一定需要查 `event/profile`。

项目里的 `QueryRewriter` 会判断：

```text
RETRIEVE
NO_RETRIEVE
```

如果用户是在问过去发生的事、个人事实、是否告诉过某件事，就生成 `history_query`。

如果只是闲聊、当前轮确认、通用知识问题，或者提出新的偏好规则，就可以不查历史事件。

### 为什么 procedure query 要单独改写

`procedure/preference` 和 `event/profile` 的检索目标不同。

`event/profile` 更像是在找：

```text
过去发生过什么
用户有什么事实信息
```

`procedure/preference` 更像是在找：

```text
用户希望 agent 怎么做
以后遇到某类请求要遵守什么流程
应该用什么工具
```

所以项目把 procedure query 单独改写成 summary 风格。

例如：

```text
用户消息：以后遇到这种问题先给结论再解释
procedure query：用户希望 agent 回答时先给结论再解释
```

又如：

```text
用户消息：帮我看看这张图
procedure query：用户发送图片并要求 agent 分析
```

这类 query 更容易命中已有的 procedure/preference 规则。

### 为什么两条改写要并发

实现里，history 判断和 procedure query 改写是并发执行的。

大致是：

```text
main_task:
  判断是否 RETRIEVE，并生成 history_query

procedure_task:
  生成 procedure/preference query
```

这样做有两个好处。

第一，降低延迟。

两次 LLM 改写并发跑，比串行等待更快。

第二，避免互相影响。

即使 history 判断失败，也可以保留 procedure query。

即使 procedure query 失败，也不影响 history retrieval 的 fallback。

### 和 memory_type 路由的关系

query rewrite 不只是改写文本，也会影响检索类型。

在 engine 里：

```text
mode = procedure
  -> 查 procedure / preference

mode = episodic
  -> 查 event / profile
```

所以系统不是把所有记忆混在一起查，而是根据查询目的选择不同 memory type。

这能减少噪声。

### fail-open 设计

`QueryRewriter` 有 fallback。

如果 LLM 改写超时、失败或输出格式不合法，系统会回退到：

```text
needs_episodic = True
episodic_query = user_msg
```

也就是说，宁愿查得宽一点，也不要因为改写失败导致完全漏召回。

这是一个偏保守的设计。

### 面试总结

可以这样回答：

```text
这个项目在 memory 检索前做 query rewrite，是因为用户原话通常是对话式表达，不一定匹配 memory summary。QueryRewriter 会判断当前消息是否需要查历史事件或用户事实，并把它改写成 history_query；同时还会单独生成 procedure_query，用来召回 preference/procedure 规则。两条改写并发执行，避免互相阻塞。engine 层还会根据 mode 路由 memory_type：procedure 模式查 procedure/preference，episodic 模式查 event/profile。这样可以降低噪声，提高召回命中率；如果改写失败，系统会 fail-open 回退到原始用户消息。
```

### 可以改进的地方

- 在 trace 中展示原始 query、history_query、procedure_query。
- 对 query rewrite 增加缓存，减少重复改写成本。
- 对失败 fallback 做统计，观察改写器稳定性。
- 对不同语言、代码词、文件名场景增加专门改写规则。
- 建立 query rewrite eval，评估改写前后召回命中率。

---

## Q47: query rewrite 采用的是什么方案？

### 问题

我自己的问题：

```text
query rewrite 采用的什么方案？
```

### 答案

这个项目的 query rewrite 采用的是：

```text
轻量 LLM 改写 + 结构化标签解析 + 并发双路改写 + fail-open fallback
```

它不是纯规则关键词匹配，也不是复杂的独立检索模型，而是用 LLM 把用户原话改写成更适合 memory summary 命中的查询。

### 具体怎么做

核心类是 `QueryRewriter`。

它会并发跑两条改写链路：

```text
main_task:
  判断是否需要查 episodic memory
  输出 RETRIEVE / NO_RETRIEVE
  输出 history_query

procedure_task:
  把用户消息改写成 procedure/preference 可命中的 summary 风格 query
```

也就是说，它不是只生成一个 query，而是拆成两种查询目的。

### 第一条：history query

history query 负责查：

```text
event
profile
```

它会判断用户是不是在问：

- 过去发生过什么。
- 用户是否告诉过某事。
- 用户个人事实。
- 某段历史记录。

LLM 输出格式类似：

```xml
<decision>RETRIEVE</decision>
<history_query>用户使用的 Fitbit 设备型号</history_query>
```

如果是普通闲聊、通用知识问答、简单“继续”、或者用户提出新的偏好规则，就可能输出：

```xml
<decision>NO_RETRIEVE</decision>
<history_query></history_query>
```

### 第二条：procedure query

procedure query 负责查：

```text
procedure
preference
```

它会把用户消息改写成“长期规则/偏好摘要”的形式。

例如：

```text
用户消息：以后遇到这种问题先给结论再解释
procedure_query：用户希望 agent 回答时先给结论再解释
```

又如：

```text
用户消息：帮我看看这张图
procedure_query：用户发送图片并要求 agent 分析
```

这样更容易命中已有的 procedure/preference 记忆。

### 为什么要用 LLM 改写

因为用户问题经常包含：

- 指代词：这个、那个、它、他。
- 省略表达：上次那个、之前说的。
- 元问题：你还记得吗。
- 混合意图：既有当前任务，也暗含历史查询。

纯关键词规则很难稳定处理这些表达。

LLM 改写可以结合近期对话，把用户的自然表达转成更明确的检索 query。

### 为什么不是完全依赖 LLM

项目没有把 LLM 输出直接无条件使用。

它做了几层约束：

- 要求 history query 用 XML 标签输出。
- 只接受 `RETRIEVE` / `NO_RETRIEVE` 两种 decision。
- procedure query 会清洗空白、去掉无效占位词。
- LLM 超时或格式错误时使用 fallback。
- history 和 procedure 两路并发，任一路失败不吞掉另一条。

这说明它是“LLM 做语义改写，代码做协议约束和降级处理”。

### fallback 方案

如果改写失败，系统会 fail-open：

```text
needs_episodic = True
episodic_query = 原始用户消息
```

也就是说，宁愿多查一点，也不因为 query rewrite 失败完全不查。

这对 memory 系统比较保守，能降低漏召回风险。

### 面试总结

可以这样回答：

```text
这个项目的 query rewrite 采用轻量 LLM 改写方案。QueryRewriter 会并发生成两类 query：一类是 history_query，用 XML decision 判断是否需要查 event/profile；另一类是 procedure_query，把用户消息改写成 preference/procedure summary 风格，用于召回流程规则和偏好。LLM 负责理解指代、省略和自然语言意图，代码负责结构化解析、清洗、超时控制和 fail-open fallback。它不是纯规则方案，也不是完全信任 LLM，而是 LLM semantic rewrite + deterministic guardrail 的组合。
```

### 可以改进的地方

- 给 query rewrite 增加单元测试和评估集。
- 对 LLM 输出失败率做统计。
- 对高频 query 做缓存。
- 对代码类、文件名类 query 增加规则增强。
- 在 Dashboard 展示 rewrite 前后的 query 和最终命中的 memory。

---

## Q48: HyDE 在这个项目里起什么作用？它和 query rewrite 有什么区别？

### 问题

面试官可能会问：

```text
这个项目里提到了 HyDE，它和 query rewrite 是一回事吗？
HyDE 是怎么增强 memory retrieval 的？
为什么要生成 hypothetical memory？
```

### 答案

HyDE 和 query rewrite 都会用 LLM 改写输入，但目的不同。

```text
Query rewrite = 规范化用户 query，决定查什么类型的 memory
HyDE = 生成假想记忆条目，用来补充召回
```

Query rewrite 更偏“路由和查询规范化”。

HyDE 更偏“召回增强”。

### HyDE 是什么

HyDE 全称是：

```text
Hypothetical Document Embeddings
```

在这个项目里，可以理解为：

```text
根据用户问题，生成一条“如果记忆库里存在答案，它大概会长什么样”的假想记忆条目。
```

例如用户问：

```text
我之前是不是做过 akashic 的运行时重构？
```

HyDE 可能生成：

```text
用户之前做过 akashic-agent 的运行时架构重构
```

这条假想文本不是答案，也不会写入数据库。

它只是用来作为第二个检索 query，帮助召回更接近 memory summary 风格的条目。

### 项目里的 HyDE 流程

`HyDEEnhancer` 的流程是：

```text
1. raw query 直接检索
2. 同时用 light LLM 生成 hypothesis
3. 如果 hypothesis 成功，再用 hypothesis 检索一次
4. raw hits 和 hyde hits 做 union dedup
5. 失败或超时则退回 raw hits
```

也就是说，它不是替换原始检索，而是补一路检索。

项目还保留 raw 结果的完整性：

```text
raw 结果全部保留
hyde 只追加 raw 里没有的 item
不修改已有 item 的 score
```

这说明 HyDE 是 recall 扩展，不是 reranker。

### 为什么 HyDE 有用

memory 数据库存的是 summary 风格条目。

用户问题是自然问句，两者语体不同。

例如：

```text
用户问题：我之前是不是提过那个数据库文件？
memory summary：用户在 akashic-agent 中使用 memory2.db 存储长期记忆
```

直接用用户问题做 embedding，可能不如用一个“假想 memory summary”更容易命中。

HyDE 的价值就是把查询变成更接近数据库条目的表达。

### 和 query rewrite 的区别

`QueryRewriter` 主要回答：

```text
要不要查历史？
查 event/profile 还是 procedure/preference？
用户原话应该改成什么检索 query？
```

它影响检索路由。

HyDE 主要回答：

```text
如果答案存在于记忆库里，它可能被写成什么样？
```

它扩展召回候选。

可以这样理解：

```text
query rewrite:
  用户话术 -> 检索意图 query

HyDE:
  用户问题 -> 假想记忆条目 -> 再检索一次
```

### 显式 recall_memory 里的类似机制

在显式 `recall_memory` 的 semantic 检索里，项目还会并发生成两种 hypothesis：

```text
event hypothesis
general hypothesis
```

然后作为 `aux_queries` 传给底层检索。

这和 HyDE 思路类似：用更接近 memory summary 的假设文本来增强召回。

### 风险

HyDE 的风险是模型可能生成过度具体或偏离用户问题的假想条目。

如果完全相信 HyDE，可能引入误召回。

所以项目的处理比较保守：

- raw 检索结果保留。
- HyDE 只追加新结果。
- 不修改原有 score。
- 失败或超时直接降级为 raw。

### 面试总结

可以这样回答：

```text
HyDE 在这个项目里是召回增强机制，不是 query rewrite 的替代。Query rewrite 负责把用户原话改成适合检索的 query，并决定查 event/profile 还是 procedure/preference；HyDE 则根据用户问题生成一条假想 memory summary，再用这条 hypothesis 做第二路检索。项目会并行做 raw 检索和 hypothesis 生成，随后用 hypothesis 再检索一次，最后 raw hits 和 hyde hits union dedup。raw 结果全部保留，HyDE 只追加新条目，不改 score；失败或超时就退回 raw。这样可以提高召回率，同时控制 hallucination 风险。
```

### 可以改进的地方

- 对 HyDE hypothesis 做质量过滤，避免偏离用户问题。
- 在 trace 中展示 hypothesis 和追加了哪些 item。
- 对不同 memory_type 使用不同 HyDE prompt。
- 增加 HyDE 开关，根据任务类型动态启用。
- 用评估集比较 raw retrieval 和 raw+HyDE 的召回率差异。


---

## Q49: MCP 工具是如何接入这个 Agent Runtime 的？它和普通内置 Tool 有什么区别？

### 问题

面试官可能会问：

```text
这个项目支持 MCP 吗？
MCP server 的工具是怎么被 Agent 发现、注册和调用的？
它和项目里的普通内置 Tool 有什么区别？
```

### 答案

这个项目支持 MCP，并且把 MCP 工具接入到了现有 Tool 系统里。

整体思路是：

```text
MCP server
  -> McpClient 连接并读取 tools/list
  -> McpToolWrapper 包装成标准 Tool
  -> ToolRegistry 注册
  -> tool_search / LLM tool_call / ToolExecutor 正常调用
```

也就是说，MCP 工具最终会被适配成项目内部统一的 `Tool` 接口。

### 核心对象

MCP 接入主要有四类对象：

```text
McpToolsetProvider
McpServerRegistry
McpClient
McpToolWrapper
```

它们职责不同。

`McpToolsetProvider` 负责在启动装配阶段注册 MCP 管理工具：

```text
mcp_add
mcp_remove
mcp_list
```

`McpServerRegistry` 负责管理多个 MCP server 的生命周期，并把远端工具同步到 `ToolRegistry`。

`McpClient` 负责连接单个 MCP server 子进程，并通过 stdio JSON-RPC 通信。

`McpToolWrapper` 负责把 MCP 远端工具包装成本地标准 `Tool`。

### 接入流程

第一步，启动时注册 MCP 管理工具。

`McpToolsetProvider` 会创建 `McpServerRegistry`，并注册：

```text
mcp_add
mcp_remove
mcp_list
```

这些工具本身也是普通 Tool，用来让 Agent 动态管理 MCP server。

第二步，通过 `mcp_add` 添加 MCP server。

`mcp_add` 接收：

```text
name
command
env
```

例如：

```text
name = calendar
command = ["python", "/path/to/server.py"]
```

第三步，`McpServerRegistry` 创建 `McpClient`。

`McpClient` 会启动 stdio 子进程，然后进行 MCP JSON-RPC 握手：

```text
initialize
notifications/initialized
tools/list
```

第四步，读取远端工具列表。

`tools/list` 返回每个工具的：

```text
name
description
inputSchema
```

项目把它们保存成 `McpToolInfo`。

第五步，包装成标准 Tool。

每个远端工具都会被包装成 `McpToolWrapper`。

工具名格式是：

```text
mcp_{server_name}__{tool_name}
```

例如：

```text
mcp_calendar__create_event
```

这样可以避免和内置工具重名，也能看出工具来自哪个 MCP server。

第六步，注册进 `ToolRegistry`。

注册时会标记：

```text
source_type = "mcp"
source_name = server_name
risk = "external-side-effect"
```

注册完成后，MCP 工具就进入了项目统一工具系统。

### 调用流程

当 LLM 选择调用一个 MCP 工具时，后续流程和普通工具类似：

```text
LLM tool_call: mcp_calendar__create_event
  -> ToolRegistry 找到 McpToolWrapper
  -> McpToolWrapper.execute(**kwargs)
  -> McpClient.call(tool_name, arguments)
  -> JSON-RPC tools/call
  -> MCP server 执行并返回结果
```

`McpClient.call()` 会向远端 server 发送：

```text
method = "tools/call"
params = {
  "name": 原始 MCP 工具名,
  "arguments": 参数
}
```

然后把 MCP 返回的 content 转成字符串，交回普通工具链路。

### 和普通内置 Tool 的区别

普通内置 Tool 是项目本地 Python 类，执行逻辑就在当前进程里。

MCP Tool 是远端工具，执行逻辑在 MCP server 子进程里。

区别可以这样看：

| 维度 | 内置 Tool | MCP Tool |
| --- | --- | --- |
| 实现位置 | 当前项目代码 | 外部 MCP server |
| 注册方式 | 直接 `ToolRegistry.register()` | `tools/list` 后包装注册 |
| 执行方式 | 调用 Python `execute()` | JSON-RPC `tools/call` |
| 生命周期 | 随 Agent 进程 | 由 `McpClient` 管理子进程 |
| 工具名 | 原始工具名 | `mcp_{server}__{tool}` |
| 风险 | 可配置 | 默认 external-side-effect |

但它们最终都会适配到统一的 `Tool` 接口，所以 Agent 主链路不需要区分太多。

### 持久化和重连

MCP server 配置会保存到 workspace 下：

```text
mcp_servers.json
```

保存内容包括：

```text
server name
command
env
cwd
```

启动时 `McpServerRegistry` 可以读取配置并重连所有 server。

同时它支持后台重连，避免阻塞主服务启动。

### 为什么这样设计

这样设计有几个好处：

第一，复用现有工具系统。

MCP 工具注册进 `ToolRegistry` 后，可以继续使用：

- tool_search
- 工具可见性控制
- ToolExecutor
- ToolHook
- 风险标记
- Dashboard / observability

第二，隔离外部能力。

MCP server 运行在子进程里，Agent 通过 JSON-RPC 调用，不需要把外部工具代码直接 import 进核心进程。

第三，动态扩展。

用户可以通过 `mcp_add` 在运行时接入新的 MCP server，而不需要改 Agent 核心代码。

### 风险和边界

MCP 工具有外部副作用风险。

例如它可能操作文件、调用第三方 API、访问账号数据。

所以项目默认把 MCP 工具注册为：

```text
risk = "external-side-effect"
```

另外还要注意：

- MCP server 可能启动失败。
- `initialize` 或 `tools/list` 可能超时。
- 工具调用可能返回错误。
- 子进程 stdout 可能输出非 JSON 内容。
- 外部工具 schema 质量不一定稳定。

项目通过 timeout、stderr drain、非 JSON 输出跳过、disconnect 清理等方式做了基础防护。

### 面试总结

可以这样回答：

```text
这个项目通过适配器方式接入 MCP。McpToolsetProvider 在启动时注册 mcp_add/mcp_remove/mcp_list 管理工具；mcp_add 会让 McpServerRegistry 创建 McpClient，启动 MCP server stdio 子进程，通过 JSON-RPC 完成 initialize、initialized、tools/list，拿到远端工具 schema。每个 MCP 工具会被 McpToolWrapper 包装成项目内部标准 Tool，名称格式是 mcp_{server}__{tool}，然后注册进 ToolRegistry，source_type 标记为 mcp。后续 LLM 调用时，ToolRegistry 找到 wrapper，wrapper 再通过 McpClient 发送 tools/call 给远端 server。这样 MCP 工具能复用项目已有的 tool_search、ToolExecutor、ToolHook 和风险治理能力，同时保持外部工具和核心 runtime 解耦。
```

### 可以改进的地方

- 给 MCP server 增加健康检查和自动重连策略。
- 对 MCP 工具 schema 做校验和清洗，避免劣质 schema 影响 LLM。
- 对不同 MCP server 设置更细粒度权限，而不是统一 external-side-effect。
- Dashboard 展示 MCP server 状态、工具列表、最近调用和错误日志。
- 支持按 session 控制 MCP 工具可见性，避免某个会话误用高风险外部工具。

---

## Q50: ToolExecutor 和 ToolHook 是怎么工作的？为什么工具调用不能直接走 ToolRegistry.execute？

### 问题

面试官可能会问：

```text
这个项目里为什么有 ToolExecutor 和 ToolHook？
LLM 返回 tool_call 后，为什么不直接调用 ToolRegistry.execute？
插件是如何在工具调用前拦截、改写或拒绝工具的？
```

### 答案

`ToolRegistry` 负责“有哪些工具，以及如何执行具体工具”。

`ToolExecutor` 负责“执行一次工具调用时，先经过哪些治理流程”。

两者职责不同。

可以这样理解：

```text
ToolRegistry = 工具目录 + 真实执行入口
ToolExecutor = 工具调用治理层
ToolHook     = 插件插入工具执行链路的扩展点
```

如果 LLM 返回 tool_call 后直接调用 `ToolRegistry.execute()`，插件就很难在工具执行前做安全检查、参数改写、循环截断和审计记录。

### 工具调用主流程

被动对话里，LLM 返回 tool_call 后，大致流程是：

```text
LLM tool_call
  -> 构造 ToolExecutionRequest
  -> ToolExecutor.execute()
      -> pre_tool_use hooks
      -> ToolRegistry.execute()
      -> post_tool_use / post_tool_error hooks
  -> 工具结果写回 messages
  -> 模型继续推理
```

真实工具执行入口仍然是：

```text
ToolRegistry.execute
```

但它被包在 `ToolExecutor` 里面。

这样工具调用就有了统一的治理层。

### ToolExecutionRequest 里有什么

一次工具调用会被包装成 `ToolExecutionRequest`。

里面包括：

- `call_id`
- `tool_name`
- `arguments`
- `source`
- `session_key`
- `channel`
- `chat_id`
- `request_text`
- `tool_batch`
- `tool_batch_index`

这些字段让 hook 不只是知道“调用了哪个工具”，还知道：

- 来自被动对话、主动任务还是 subagent。
- 当前属于哪个 session。
- 当前 tool_call 在一批工具调用里的位置。
- 这轮用户请求是什么。

这对安全判断和循环检测很重要。

### pre hook 能做什么

`pre_tool_use` 是工具执行前的 hook。

它可以做三件事：

```text
pass       放行
deny       拒绝工具调用
updated_input  改写工具参数
```

例如：

`shell_safety` 插件会在 `shell` 工具执行前检查命令。

如果发现：

- `vim`
- `nano`
- 可能等待密码的 `sudo`
- 需要确认的包管理器写操作

就返回：

```text
HookOutcome(decision="deny", reason="...")
```

这样真实 shell 工具不会被执行。

再比如 `shell_restore` 这类插件可以在 shell 前改写命令参数。

### post hook 能做什么

`post_tool_use` 和 `post_tool_error` 发生在工具执行之后。

它们主要用于：

- 记录工具结果。
- 补充 trace。
- 做观察型副作用。
- 在工具失败后记录错误信息。

注意：post hook 不负责回写执行参数。

参数改写只允许发生在 pre hook 阶段。

这让执行语义更清楚：

```text
执行前可以治理输入
执行后主要做观察和记录
```

### 插件如何注册 ToolHook

插件通过装饰器注册 pre hook：

```python
@on_tool_pre(tool_name="shell")
async def block_interactive_shell(self, event):
    ...
```

这个装饰器不会走普通 EventBus。

它会写入插件 registry，类型是：

```text
MetadataKind.TOOL_HOOK
```

插件加载时，`PluginManager` 会把这个 handler 包装成 `_PluginToolHook`。

然后 Reasoner 会把这些 hook 加入：

```text
ToolExecutor.add_hooks()
```

最终工具执行时，`ToolExecutor` 逐个运行匹配的 hook。

### hook 如何匹配工具

`@on_tool_pre(tool_name="shell")` 表示只匹配 `shell` 工具。

如果不传 `tool_name`：

```python
@on_tool_pre()
```

就表示匹配所有工具。

例如 `tool_loop_guard` 就是全局 pre hook。

它会根据：

```text
tool_name + arguments
```

生成 signature，如果同一个 session 连续重复调用同样工具超过阈值，就拒绝后续调用，避免 Agent 陷入工具循环。

### ToolExecutor 的执行结果

`ToolExecutor.execute()` 返回 `ToolExecutionResult`。

里面包括：

- `status`: success / denied / error
- `output`
- `final_arguments`
- `extra_messages`
- `pre_hook_trace`
- `post_hook_trace`

这很重要。

因为 tool chain 持久化时，不只记录原始 arguments，还会记录：

```text
final_arguments
pre_hook_trace
post_hook_trace
status
result preview
```

这样后续 Dashboard、debug、memory post-processing 都能知道：

- 工具是否真的执行了。
- 参数有没有被 hook 改写。
- 哪个 hook 拦截了工具。
- 拦截原因是什么。

### 为什么不用 EventBus 做工具拦截

项目里也有 `BeforeToolCallCtx` 和 `AfterToolResultCtx` 这类 EventBus 事件。

但它们更适合观察和通知。

真正需要“改参数 / 拒绝执行”的逻辑不能只靠普通事件广播。

因为普通 EventBus fanout 很难形成清晰的控制流：

```text
哪个 handler 能改参数？
多个 handler 改同一个参数谁优先？
谁能终止执行？
终止原因如何返回给模型？
```

所以项目把工具治理做成明确的 `ToolExecutor + ToolHook` 链。

这比把所有插件都挂到 EventBus 上更可控。

### 面试总结

可以这样回答：

```text
ToolRegistry 负责保存工具和执行具体工具，ToolExecutor 负责一次工具调用的治理流程。LLM 返回 tool_call 后，Reasoner 不直接调用 ToolRegistry.execute，而是构造 ToolExecutionRequest 交给 ToolExecutor。ToolExecutor 先跑 pre_tool_use hooks，插件可以放行、改写参数或 deny；如果未拒绝，再调用 ToolRegistry.execute 执行真实工具；执行后再跑 post_tool_use 或 post_tool_error hooks 做观察和 trace。插件通过 @on_tool_pre 注册 hook，PluginManager 会把它适配成 ToolHook，并注入 Reasoner 的 ToolExecutor。这样 shell_safety、tool_loop_guard 等插件可以在不侵入 AgentLoop 的情况下治理工具调用。
```

### 可以改进的地方

- 给 hook 增加优先级和冲突处理策略。
- 支持 post hook 对结果做结构化标注，但不直接篡改原始结果。
- 在 Dashboard 里展示每次工具调用的 hook trace。
- 对高风险工具增加多阶段审批 hook。
- 为不同 source 设置不同 hook 策略，例如 passive、proactive、subagent 分别治理。

---

## Q51: Lifecycle Phase 为什么要做成 module + slot/requires 机制？每个 phase 的边界是什么？

### 问题

面试官可能会问：

```text
这个项目已经有 AgentLoop 和 PassiveTurnPipeline 了，为什么还要设计 lifecycle phase？
为什么 phase 里面又拆成 module、slot、requires？
每个 phase 到底应该放什么逻辑？
```

### 答案

Lifecycle Phase 的作用是把“一轮对话”拆成可插拔、可观测、可测试的阶段。

更进一步，项目没有把每个 phase 写成一个大函数，而是拆成：

```text
Phase
  -> PhaseFrame
  -> PhaseModule
  -> slot / requires / produces
  -> topo_sort_modules
```

这说明它不只是回调机制，而是一套小型的阶段编排系统。

### 为什么不直接写成一个大函数

一轮 Agent 对话要做很多事情：

- 获取 session。
- 准备上下文。
- 检索 memory。
- 同步工具上下文。
- 渲染 prompt。
- 执行 LLM reasoning。
- 多轮工具调用。
- 工具前后治理。
- 写 session history。
- fanout TurnCommitted。
- 触发 memory consolidation / observe。
- 派发 outbound message。

如果全部写在一个函数里，短期能跑，但后面插件、memory、dashboard、proactive、tool safety 都会不断插进主流程，最后变成一个难以维护的大函数。

phase 化之后，每个阶段有明确输入输出，插件也有明确插入点。

### Phase 框架的核心机制

`PhaseFrame` 里有三个核心字段：

```text
input
slots
output
```

`input` 是这个 phase 的输入。

`slots` 是 phase 内部模块共享的中间状态。

`output` 是这个 phase 的最终输出。

每个 `PhaseModule` 有：

```text
slot
requires
produces
```

`slot` 表示模块自己的唯一名字。

`requires` 表示它依赖哪些前置模块或中间 slot。

`produces` 表示它会产出哪些 slot。

启动时，系统会用 `topo_sort_modules()` 对模块做拓扑排序。

这样可以保证：

- 模块按依赖顺序执行。
- 插件模块能插入到合适位置。
- slot 重复会报错。
- 模块循环依赖会报错。
- 依赖缺失的插件模块会被禁用。

### 为什么 slot/requires 很重要

如果只用普通 list 顺序执行插件，会有几个问题：

- 插件必须知道自己前面有哪些模块。
- 插件顺序容易靠约定和运气。
- 某个插件需要 session/context/prompt 时，很难表达依赖。
- 新增内置模块可能打乱旧插件行为。

`slot/requires` 让插件可以声明：

```text
我需要 before_turn.prepare_context 之后运行
我会产出 prompt:section_bottom:xxx
我需要 step:ctx 存在
```

这比“按注册顺序执行”更稳定。

### BeforeTurn 的边界

`BeforeTurn` 负责准备一轮对话开始前的基础上下文。

默认模块包括：

```text
before_turn.acquire_session
before_turn.prepare_context
before_turn.build_ctx
before_turn.emit
before_turn.collect_exports
before_turn.return
```

它主要做：

- 获取或创建 session。
- 调用 ContextStore 准备 session history、retrieved memory、skill mentions。
- 构造 `BeforeTurnCtx`。
- 通过 EventBus emit 给插件。
- 收集插件导出的 extra hints 或 abort reply。

这个阶段适合做：

- 会话级准备。
- 上下文检索前后增强。
- 判断是否直接 abort。
- 提供本轮 extra hints。

### BeforeReasoning 的边界

`BeforeReasoning` 是真正进入 LLM 推理前的准备阶段。

它会做：

- 同步 ToolRegistry context。
- 注入当前 channel/chat_id。
- 预测 current_user_source_ref。
- 构造 `BeforeReasoningCtx`。
- 给插件修改 reasoning 前状态的机会。
- 做 prompt warmup。

这个阶段适合做：

- 工具上下文同步。
- 当前用户消息 source_ref 准备。
- 推理前策略检查。
- 轻量 abort。

### PromptRender 的边界

`PromptRender` 负责把上下文渲染成模型真正看到的 messages。

默认流程是：

```text
build PromptRenderCtx
emit 给插件
collect plugin exported sections / hints
ContextBuilder.render()
return PromptRenderResult
```

插件可以通过 slot 导出：

```text
prompt:section_top:xxx
prompt:section_bottom:xxx
prompt:extra_hint:xxx
```

这让插件可以安全地给 system prompt 增加 section，而不是直接改一大段 prompt 字符串。

这个阶段适合做：

- 增加系统提示 section。
- 增加本轮上下文 hint。
- 控制 disabled sections。
- 修改最终 prompt 组装输入。

### BeforeStep / AfterStep 的边界

`BeforeStep` 和 `AfterStep` 发生在 LLM/tool loop 的每一轮 iteration 内。

`BeforeStep` 主要用于：

- 估算当前 messages token。
- 暴露当前 visible tool names。
- 给插件注入本 step 的 hints。
- 允许 early stop 当前 tool loop。

`AfterStep` 主要用于：

- 观察本轮工具调用情况。
- 记录 partial reply。
- 收集 step telemetry。
- 标记 early stop reason。

这两个 phase 适合做 tool loop 级别的监控和干预，而不是整轮对话级别的后处理。

### AfterTurn 的边界

`AfterTurn` 发生在模型已经产出最终回复之后。

它负责：

- 计算 post-reply context budget。
- 提取 ReAct stats。
- 构造 tool_chain。
- 构造 `TurnCommitted`。
- fanout `TurnCommitted`。
- 构造 `AfterTurnCtx`。
- fanout after-turn 观察事件。
- dispatch outbound message。
- return outbound。

其中 `TurnCommitted` 很关键。

memory、observe、post-response worker 等后处理可以监听它，而不是耦合进 AgentLoop。

这个阶段适合做：

- 记录 trace。
- 触发 memory ingest。
- 触发 observability。
- 处理 outbound dispatch 前后的副作用。

### GATE 和 TAP 的区别

项目里 before 类 ctx 通常是 GATE 风格。

也就是说，插件可以修改 ctx，影响后续流程。

例如：

```text
BeforeTurnCtx.abort = True
BeforeReasoningCtx.extra_hints.append(...)
PromptRenderCtx.system_sections_bottom.append(...)
BeforeStepCtx.early_stop = True
```

after 类 ctx 更偏 TAP 风格，主要用于观察和记录。

例如：

```text
AfterStepCtx
AfterTurnCtx
TurnCommitted
```

这样可以避免后处理插件随意改变已经发生的事实。

### 为什么这套设计适合插件系统

插件最怕两种情况：

第一，没有稳定插入点，只能 monkey patch 主流程。

第二，插入点太自由，插件可以随便改任何状态。

这个项目通过 phase + ctx + slots 形成边界：

- 插件知道自己挂在哪个阶段。
- 插件拿到的是阶段 ctx，不是整个 runtime。
- 插件要导出内容时走 slot prefix。
- phase 内部用 topo sort 保证依赖顺序。
- after 阶段主要观察，不鼓励改事实。

这比在 AgentLoop 里到处写 if plugin enabled 更稳。

### 面试总结

可以这样回答：

```text
这个项目把一轮对话拆成 lifecycle phase，是为了让 Agent 主链路可插拔、可观测、可测试。每个 phase 又由多个 PhaseModule 组成，模块通过 slot/requires/produces 声明依赖，启动时用 topo_sort_modules 做拓扑排序，运行时通过 PhaseFrame 的 slots 传递中间结果。BeforeTurn 负责 session 和 context 准备，BeforeReasoning 负责工具上下文和推理前增强，PromptRender 负责组装模型 messages，BeforeStep/AfterStep 负责 tool loop 每轮干预和观测，AfterTurn 负责 TurnCommitted、trace、memory 后处理和 outbound dispatch。这种设计让插件可以在明确阶段介入，而不是侵入 AgentLoop。
```

### 可以改进的地方

- 给每个 phase 自动生成 dependency tree，并在 Dashboard 展示。
- 对插件 module 的 slot 命名做命名空间约束，避免冲突。
- 为每个 phase 增加耗时统计和失败隔离。
- 对 GATE 插件修改 ctx 的字段做 diff trace。
- 增加 phase module 单元测试模板，降低插件开发成本。

---

## Q52: 为什么要抽象 LLMProvider？它如何统一不同模型、stream/non-stream 和轻量模型？

### 问题

面试官可能会问：

```text
这个项目为什么要封装 LLMProvider？
直接在 Reasoner 里调用 OpenAI SDK 不行吗？
它是如何兼容不同模型供应商、stream/non-stream、主模型和轻量模型的？
```

### 答案

`LLMProvider` 是项目里对模型调用的统一适配层。

它把不同模型供应商、不同请求参数、不同返回格式、stream/non-stream 差异、thinking 字段、tool_calls、cache usage、错误分类都收敛到一个统一接口：

```python
await provider.chat(
    messages=...,
    tools=...,
    model=...,
    max_tokens=...,
    tool_choice="auto",
)
```

返回统一的：

```text
LLMResponse
  content
  tool_calls
  thinking
  provider_fields
  cache_prompt_tokens
  cache_hit_tokens
```

这样 Reasoner、memory、proactive、HyDE、query rewrite 都不需要直接关心底层模型厂商细节。

### 为什么不能直接在 Reasoner 里调 OpenAI SDK

直接调 SDK 的短期代码会更少，但长期会出现几个问题。

第一，供应商差异会污染主链路。

DeepSeek、DashScope、OpenAI 兼容接口虽然都像 Chat Completions，但细节不同：

- thinking / reasoning_content 字段不同。
- 是否支持 image content 不同。
- stream_options 不同。
- extra_body 字段不同。
- content safety 错误码不同。
- context length 错误文本不同。

如果这些逻辑写在 Reasoner 里，AgentLoop 会变得很脏。

第二，stream 和 non-stream 处理不同。

非流式响应一次性返回 message。

流式响应需要不断拼接：

- content delta
- thinking delta
- tool_call delta
- usage / cache 信息

这些处理逻辑不应该散落在业务模块里。

第三，不同任务需要不同模型。

主对话可以用强模型。

query rewrite、HyDE、memory invalidation、procedure tagging 这类任务可以用 light model。

proactive 或 subagent 也可能使用单独 provider。

如果没有 provider 抽象，模型选择会到处散落。

### ProviderStrategy 解决什么问题

项目里 `LLMProvider` 内部还有一层 `ProviderStrategy`。

它用来处理不同供应商的特殊行为。

默认策略做基础规范化：

```text
normalize_messages
prepare_request
extract_message
provider_fields_for_tool_call
prepare_stream_request
```

DeepSeek 策略会处理：

- `reasoning_content`
- thinking enable/disable
- `reasoning_effort`
- stream usage
- 特定 message normalize

DashScope 策略会处理：

- `enable_thinking`
- disable thinking 时清理相关参数

所以整体结构是：

```text
Reasoner
  -> LLMProvider.chat()
      -> select ProviderStrategy
      -> normalize messages
      -> prepare kwargs / extra_body
      -> call AsyncOpenAI
      -> normalize response into LLMResponse
```

这让模型厂商差异被限制在 provider 层。

### stream 是怎么统一的

`LLMProvider.chat()` 有一个参数：

```python
on_content_delta
```

如果传了这个回调，就走 streaming。

streaming 里会逐 chunk 读取：

- 普通内容 delta。
- reasoning / thinking delta。
- tool_call delta。
- usage 里的 cache 信息。

最后仍然组装成统一的 `LLMResponse`。

也就是说，调用方最终还是拿到同一种响应结构。

区别只是 streaming 过程中可以把内容增量发给 channel。

### 错误分类为什么重要

Provider 不只是转发请求，还会分类错误。

例如：

```text
ContentSafetyError
ContextLengthError
retryable transient error
```

context length 错误会被上层 retry/trim 逻辑处理。

安全审查错误可以走特殊回复或降级策略。

429、5xx、timeout 这类错误可以重试。

如果没有统一错误分类，上层只能看到一堆供应商原始异常，很难做稳定恢复。

### main / light / agent / vl provider 的分工

启动装配时，`build_providers()` 会创建多个 provider：

```text
provider        主模型 provider
light_provider 轻量任务 provider
agent_provider 可选 agent 专用 provider
vl_provider    可选视觉模型 provider
```

主模型用于被动对话和复杂推理。

light model 用于：

- memory query rewrite
- HyDE
- invalidation 判断
- procedure tagging
- proactive judge 里的轻量判断

这样做的好处是：

- 降低成本。
- 降低延迟。
- 避免所有后台小任务都占用主模型。
- 可以对轻量模型强制关闭 thinking。

### prompt cache usage 如何进入系统

`LLMResponse` 里有：

```text
cache_prompt_tokens
cache_hit_tokens
```

Provider 会从 usage 中提取 prompt cache 命中信息。

Reasoner 后续会把这些信息累计到 ReAct stats / trace 里。

这让系统能观察 prompt cache 是否生效，而不是只凭感觉判断。

### 设计取舍

这个设计的优点是统一、稳定、可扩展。

业务模块只依赖 `provider.chat()` 和 `LLMResponse`，不关心底层供应商。

缺点是 provider 层会变得比较复杂。

它需要处理：

- message normalization
- stream chunk assembly
- tool call JSON 解析
- thinking 字段兼容
- 错误分类
- extra_body 清洗
- cache usage 提取

但这些复杂性集中在一层，比散落在 Reasoner、memory、proactive 里更可维护。

### STAR 法则思考

**Situation 情景：**

项目不是单一 OpenAI 调用脚本，而是一个 Agent Runtime。它既要服务主对话，又要支持 memory、query rewrite、HyDE、proactive、subagent 等多个 LLM 调用场景，还可能接入 DeepSeek、Qwen/DashScope、OpenAI 兼容服务。

**Task 任务：**

需要设计一个统一的模型调用层，让上层 Agent 模块不直接依赖具体厂商 SDK 细节，同时支持工具调用、streaming、thinking、错误分类、prompt cache usage 和多模型分工。

**Action 行动：**

项目封装了 `LLMProvider.chat()` 作为统一入口，返回标准 `LLMResponse`；内部用 `ProviderStrategy` 处理不同供应商差异；用 `on_content_delta` 统一 streaming；用 `build_providers()` 装配 main/light/agent/vl provider；在 provider 层统一处理 retry、context length、安全错误和 cache usage。

**Result 结果：**

Reasoner、memory、proactive 等模块都可以用同一套接口调用模型，供应商差异被隔离在 provider 层。项目可以更容易切换模型、引入轻量模型降低成本、支持流式输出，并让上下文超长和安全错误进入可控恢复流程。

### 面试总结

可以这样回答：

```text
这个项目抽象 LLMProvider，是为了把模型供应商差异和 Agent 主链路隔离开。Reasoner、memory、proactive 等模块只调用 provider.chat，并拿到统一的 LLMResponse。Provider 内部通过 ProviderStrategy 处理 DeepSeek、DashScope 等供应商的 thinking、reasoning_content、extra_body、stream_options 和 message normalization 差异；同时统一 stream/non-stream、tool_calls 解析、cache usage 提取、retry、context length 和 safety error 分类。启动时还会构建 main/light/agent/vl provider，让主对话、轻量记忆任务、子 agent、视觉任务可以用不同模型。这样比在 AgentLoop 里直接调用 OpenAI SDK 更可维护，也更适合多模型 Agent Runtime。
```

### 可以改进的地方

- 给每个 provider strategy 增加契约测试，验证 tool_calls、streaming、thinking 字段是否正常。
- 把 provider capability 显式建模，例如是否支持 vision、tool call、reasoning、prompt cache。
- 对不同模型调用场景记录成本和延迟指标。
- 增加 provider fallback，例如主模型失败时切换备用模型。
- 在 Dashboard 展示每轮 LLM 调用的 provider、model、tokens、cache hit、latency 和错误分类。

---

## Q53: SessionStore、message id 和 source_ref 是如何支撑原始消息追溯的？

### 问题

面试官可能会问：

```text
这个项目里的长期记忆如何追溯到原始对话？
SessionStore 存了什么？
source_ref 是怎么产生的？
为什么 recall_memory 之后还能用 fetch_messages 找回原文？
```

### 答案

这个项目把“长期记忆摘要”和“原始消息证据”分开存储。

长期记忆存在：

```text
memory2.db
Markdown memory
```

原始会话消息存在：

```text
sessions.db
```

两者之间通过 `source_ref` 关联。

可以理解为：

```text
memory item = 摘要线索
source_ref  = 回到原始消息的指针
messages    = 原始证据
```

### SessionStore 存什么

`SessionStore` 是 SQLite-backed store。

核心表有两个：

```text
sessions
messages
```

`sessions` 保存会话级状态：

- `key`
- `created_at`
- `updated_at`
- `last_consolidated`
- `metadata`
- `last_user_at`
- `last_proactive_at`
- `next_seq`

`messages` 保存原始消息：

- `id`
- `session_key`
- `seq`
- `role`
- `content`
- `tool_chain`
- `extra`
- `ts`

其中最关键的是：

```text
id = session_key:seq
```

例如：

```text
telegram:12345:17
```

这表示 `telegram:12345` 这个 session 的第 17 条消息。

### message id 为什么重要

message id 是整个证据链的基础。

它必须稳定、可预测、可回查。

项目用：

```text
session_key + seq
```

生成 message id。

`seq` 由 `SessionStore.next_seq()` 管理，并写入 `sessions.next_seq`。

写入消息时，`insert_message()` 会生成：

```text
message_id = f"{session_key}:{seq}"
```

然后把消息写入 `messages` 表。

这让后续任何模块只要拿到 message id，就能用 `fetch_messages` 回到原文。

### current_user_source_ref 是怎么来的

有一个细节很关键：用户当前这条消息在工具调用时可能还没最终持久化。

但 `memorize` 工具需要把记忆来源绑定到“当前用户这条消息”。

所以项目在 `BeforeReasoning` 阶段会调用：

```text
predict_current_user_source_ref()
```

它会通过：

```text
session_manager.peek_next_message_id(session.key)
```

预测当前用户消息即将写入的 message id。

这个值会放进 `ToolRegistry` context：

```text
current_user_source_ref
```

于是 `memorize` 工具写入记忆时，就可以把 source_ref 绑定到当前用户消息。

这解决了一个时序问题：

```text
工具调用发生在 turn 持久化前
但 memory 需要引用当前用户消息
```

### consolidation 的 source_ref

consolidation 不是引用单条消息，而是引用一个窗口内的多条旧消息。

它会构造：

```text
source_ref = JSON list of message ids
```

例如：

```json
["telegram:123:10", "telegram:123:11", "telegram:123:12"]
```

如果同一个 consolidation 窗口生成多条 history entry，项目还会给单条 entry 加子键：

```text
["..."]#h:<digest>
```

这样同一个窗口里的不同 memory item 不会互相覆盖。

### fetch_messages 如何回到原文

`fetch_messages` 支持：

```text
ids
source_ref
source_refs
context
```

它会先解析 source_ref。

如果 source_ref 是：

```text
message_id
```

就直接查这条消息。

如果 source_ref 是：

```text
JSON list of message ids
```

就展开成多个 message id。

如果 source_ref 后面带：

```text
#h:digest
```

会先去掉后缀，只取前面的 message ids。

然后调用：

```text
SessionStore.fetch_by_ids()
SessionStore.fetch_by_ids_with_context()
```

所以 recall 到 memory item 后，只要 item 里有 source_ref，就能继续 fetch 原始消息。

### search_messages 如何定位原始消息

`search_messages` 是原始消息层的关键词搜索。

底层 `SessionStore` 建了 FTS5 表：

```text
messages_fts
```

并使用：

```text
tokenize='trigram'
```

trigram 对中文和子串匹配更友好。

搜索时，项目会优先走 FTS + LIKE 的混合方案。

如果 FTS 不可用，就回退到 LIKE。

这让用户可以通过文件名、报错、配置项、短语去定位原始消息。

### 为什么要分 memory summary 和 raw message

因为 memory summary 适合召回，但不适合做最终证据。

长期记忆可能经过：

- consolidation
- 改写
- 摘要
- 去重
- 合并
- supersede

它是高层线索，不是原话。

而 `sessions.db.messages` 保存的是原始对话记录。

所以正确链路是：

```text
recall_memory
  -> memory summary + source_ref
  -> fetch_messages(source_ref)
  -> 原始消息证据
  -> 回答用户
```

### 和 memory 的关系

memory item 里保存 source_ref。

memory retrieval 返回 item 时，也会带 source_ref。

`recall_memory` 返回给模型后，模型可以继续调用 `fetch_messages`。

这形成了一条完整证据链：

```text
messages.id
  -> source_ref
  -> memory item
  -> recall_memory result
  -> fetch_messages
  -> original message
```

这也是为什么之前说 `recall_memory` 是 L1 线索层，`fetch_messages` 是证据层。

### 设计取舍

优点：

- memory 摘要和原始证据分离。
- 长期记忆可以压缩，原文仍可追溯。
- Dashboard 可以按 session/message/source_ref 查问题。
- 纠错时可以回到原始来源。
- fetch_messages 可以扩展上下文，避免断章取义。

代价：

- source_ref 格式需要维护一致性。
- 删除消息时要考虑 memory item 是否变成悬空引用。
- consolidation source_ref 是 JSON list，解析逻辑比单 id 复杂。
- 当前用户 source_ref 需要预测 next_seq，有时序复杂度。

### STAR 法则思考

**Situation 情景：**

Agent 长期记忆会把对话压缩成 summary，但用户追问历史事实时，不能只凭摘要回答。项目需要同时支持“语义召回”和“原文取证”。

**Task 任务：**

设计一套消息持久化和引用机制，让 memory item 能追溯到原始 session message，并支持 recall 后继续 fetch 原文。

**Action 行动：**

项目用 `sessions.db` 保存 session 和 messages，message id 采用 `session_key:seq` 稳定格式；`SessionManager` 写入消息时补齐 id；`predict_current_user_source_ref()` 在工具调用前预测当前用户消息 id；consolidation 用 message id JSON list 作为 source_ref；`fetch_messages` 解析 source_ref 并读取原文和上下文；`search_messages` 用 FTS trigram + LIKE 支持原始消息搜索。

**Result 结果：**

长期记忆可以保持轻量摘要，同时仍能追溯原始证据。用户问历史事实时，Agent 可以先通过 memory 找线索，再用 fetch_messages 查原文，提升回答可信度，也方便 Dashboard 调试和记忆纠错。

### 面试总结

可以这样回答：

```text
这个项目用 SessionStore 保存原始会话消息，用 memory2.db 保存长期记忆摘要，两者通过 source_ref 关联。SessionStore 里 messages 表的 id 采用 session_key:seq 的稳定格式，SessionManager 持久化消息时会补齐 id。memorize 工具需要引用当前用户消息，但工具调用发生在 turn 持久化前，所以 BeforeReasoning 会通过 peek_next_message_id 预测 current_user_source_ref。consolidation 则把一个窗口内的 message ids 序列化成 JSON list 作为 source_ref，并给单条 history entry 加 #h:digest 子键。recall_memory 返回 memory item 的 source_ref 后，fetch_messages 可以解析 message id 或 JSON list，回到 sessions.db 读取原始消息和上下文。这让 memory summary 成为线索层，原始 session message 成为证据层。
```

### 可以改进的地方

- 给 source_ref 定义结构化类型，而不是主要依赖字符串和 JSON list。
- 删除 message 时检测并提示相关 memory item 会变成悬空引用。
- Dashboard 展示 source_ref 到原始消息的完整跳转链。
- 对 current_user_source_ref 预测和实际落盘 id 做一致性校验。
- 给 fetch_messages 增加 source_ref 解析失败的诊断信息。

---

## Q54: Observe / Dashboard trace 是如何记录一轮 Agent 行为的？为什么只看日志不够？

### 问题

面试官可能会问：

```text
Agent 应用为什么需要 observability？
这个项目是如何记录一轮 turn、memory retrieval 和 memory write 的？
Dashboard 背后的 trace 数据从哪里来？
```

### 答案

Agent 应用的可观测性不是锦上添花，而是核心能力。

普通应用看日志通常能知道函数是否报错。

但 Agent 应用还需要解释：

- 模型看到了什么上下文。
- 检索到了哪些 memory。
- 哪些 memory 最终注入 prompt。
- 调用了哪些工具。
- 工具参数有没有被 hook 改写。
- 工具结果是什么。
- 一轮 ReAct 循环跑了几次。
- prompt/cache/token 压力如何。
- 哪些记忆被写入或失效。

这些问题只靠普通日志很难系统回答。

所以项目引入了 observe 插件和 Dashboard 数据层。

### observe 插件监听哪些事件

`ObservePlugin` 初始化时会创建：

```text
TraceWriter(workspace / "observe" / "observe.db")
```

然后订阅三个核心事件：

```text
TurnCommitted
RetrievalCompleted
MemoryWritten
```

这三类事件对应三条可观测主线：

```text
TurnCommitted     -> 一轮对话发生了什么
RetrievalCompleted -> memory retrieval 查了什么、注入了什么
MemoryWritten     -> 长期记忆写入/失效了什么
```

### TurnCommitted 记录什么

`TurnCommitted` 是 AfterTurn 阶段构造并 fanout 的。

observe 插件会把它转换成 `TurnTrace`。

记录内容包括：

- `session_key`
- 用户输入。
- 最终回复。
- 原始模型输出。
- tool calls。
- tool_chain_json。
- history window。
- history chars / tokens。
- prompt tokens。
- next_turn_baseline_tokens。
- ReAct iteration count。
- ReAct 输入 token 累计、峰值、最终输入 token。
- prompt cache prompt tokens / hit tokens。

所以它不是只记录“用户问了什么、助手答了什么”，还记录了一轮 Agent 的推理和工具执行结构。

### tool_chain_json 的价值

`tool_chain_json` 保存每轮工具调用链。

它能回答：

```text
模型在哪一轮调用了哪些工具？
工具参数是什么？
工具返回了什么？
最终回复是否依赖这些工具？
```

这对调试工具循环、错误工具调用、工具结果污染非常重要。

如果没有 tool_chain trace，只看最终回复，很难解释 Agent 为什么这样回答。

### RetrievalCompleted 记录什么

memory retrieval 完成后，会产生 `RetrievalCompleted`。

observe 插件把它转换成 `RagQueryLog`。

记录内容包括：

- caller：passive / proactive / explicit。
- session_key。
- rewrite 后 query。
- 原始 query。
- aux_queries，例如 HyDE hypothesis。
- hits。
- injected_count。
- route_decision。
- error。

每个 hit 会记录：

- item id。
- memory_type。
- score。
- summary。
- 是否 injected。
- confidence_label。
- forced。

这能回答 memory 系统最关键的问题：

```text
这轮为什么召回了这些记忆？
为什么有些记忆被注入，有些没注入？
是否有强制 procedure 进入 prompt？
query rewrite / HyDE 是否参与了召回？
```

### MemoryWritten 记录什么

memory 写入或失效时，会产生 `MemoryWritten`。

observe 插件写成 `MemoryWriteTrace`。

记录内容包括：

- session_key。
- source_ref。
- action：write / supersede。
- memory_type。
- item_id。
- summary。
- superseded_ids。
- error。

这能追踪：

```text
哪轮对话写入了什么记忆？
记忆来源是哪条消息？
哪些旧记忆被 supersede？
是否写入失败？
```

这对长期记忆纠错很关键。

### TraceWriter 为什么要异步队列

`TraceWriter.emit()` 是非阻塞的。

它把事件放进 asyncio queue：

```text
Queue max = 500
```

后台 task 再消费队列写 SQLite。

如果队列满了，会 drop 并计数，不会阻塞主 AgentLoop。

这个取舍很重要：

```text
observability 不能拖垮主回复链路
```

也就是说，trace 是重要辅助能力，但不能因为写 trace 慢导致用户对话卡住。

### observe.db 的表结构

observe 数据写入：

```text
workspace/observe/observe.db
```

核心表有：

```text
turns
rag_queries
memory_writes
```

`turns` 记录一轮对话。

`rag_queries` 记录 memory 检索。

`memory_writes` 记录 memory 写入和 supersede。

这些表通过：

```text
session_key
ts
source_ref
item_id
```

串联起来。

### recall_inspector 补充了什么

除了 observe 插件，项目还有 `recall_inspector` 插件。

它更专注于 memory retrieval 诊断。

它通过 before_turn module 记录：

```text
context_prepare
```

包括：

- retrieved_memory_block。
- injected_items。
- retrieval_trace_raw。
- all_hits。

它还通过 `@on_tool_result()` 监听显式 `recall_memory` 工具结果，记录：

- recall 参数。
- recall 返回 items。
- raw_result。

数据写入：

```text
workspace/observe/recall_inspector.jsonl
```

这让用户能比较：

```text
被动注入 memory
显式 recall_memory
```

两条链路的差异。

### Dashboard 在这里的价值

Dashboard 不是普通管理后台。

它更像 Agent observability console。

它能帮助回答：

- 这轮为什么调用了某个工具？
- 哪些 memory 被召回？
- 哪些 memory 被注入 prompt？
- prompt/token 压力是否过大？
- prompt cache 是否命中？
- memory 是否被错误写入？
- proactive tick 为什么 reply / skip？
- plugin panel 提供了哪些额外诊断？

这对 Agent 应用很重要，因为 Agent 的行为不是固定规则输出，而是模型、工具、记忆、上下文共同作用的结果。

### 为什么只看日志不够

普通日志通常是线性的文本。

Agent trace 需要结构化数据。

比如：

```text
turn -> tool_chain -> retrieval hits -> injected memory -> memory writes
```

这些关系需要按 session、turn、memory item、source_ref 查询。

如果只看文本日志：

- 很难筛选某个 session。
- 很难比较不同 turn。
- 很难展开 tool_chain。
- 很难统计 cache hit。
- 很难追踪 memory item 来源。
- 很难做 Dashboard 可视化。

所以项目把关键运行事件结构化写入 SQLite/JSONL，而不是只写文本日志。

### 设计取舍

优点：

- 主流程和观测解耦。
- trace 可结构化查询。
- Dashboard 可以复盘 turn / retrieval / memory。
- observe 写入失败不会阻断用户回复。
- recall_inspector 能专门分析 memory 注入和显式 recall。

代价：

- trace schema 需要维护。
- 事件字段要持续和主流程同步。
- 队列满时可能丢 trace。
- 数据库需要 retention 策略。
- 工具参数和结果需要截断，避免 observe.db 过大或泄露敏感信息。

### STAR 法则思考

**Situation 情景：**

Agent Runtime 的行为由模型、工具、记忆、插件、上下文共同决定。出现错误回答时，仅靠最终回复和普通日志很难解释原因。

**Task 任务：**

需要设计一套可观测机制，能记录一轮对话的输入输出、工具链、memory retrieval、memory write、token/cache 压力，并能被 Dashboard 查询和复盘。

**Action 行动：**

项目通过 `ObservePlugin` 订阅 `TurnCommitted`、`RetrievalCompleted`、`MemoryWritten`，转换成 `TurnTrace`、`RagQueryLog`、`MemoryWriteTrace`，由异步 `TraceWriter` 写入 `observe.db`。同时 `recall_inspector` 记录被动 memory 注入和显式 `recall_memory` 结果到 JSONL，用于诊断 memory 召回链路。

**Result 结果：**

项目可以从 Dashboard 或数据库层复盘 Agent 行为：一轮调用了哪些工具、检索了哪些记忆、注入了哪些 memory、写入了哪些长期记忆、token 和 cache 压力如何。这样能显著提升调试效率，也让项目更像一个可运维的 Agent Runtime，而不是黑盒聊天脚本。

### 面试总结

可以这样回答：

```text
这个项目的 observability 主要通过 observe 插件实现。ObservePlugin 订阅 TurnCommitted、RetrievalCompleted、MemoryWritten 三类事件，分别记录一轮对话 trace、memory retrieval trace 和 memory write trace。TurnTrace 会保存用户输入、最终回复、tool_chain、ReAct 迭代数、history/token/cache 统计；RagQueryLog 会保存 query、orig_query、aux_queries、hits、injected_count、forced memory；MemoryWriteTrace 会保存 source_ref、memory_type、item_id、summary 和 superseded_ids。TraceWriter 用异步队列写入 observe.db，避免阻塞主 AgentLoop。recall_inspector 还会额外记录被动注入和显式 recall_memory 的结果。这样 Dashboard 可以解释 Agent 为什么这样回答、用了哪些工具、看到了哪些记忆，而不是只看普通日志。
```

### 可以改进的地方

- 给 turn、retrieval、memory write 建立统一 trace_id，方便跨表关联。
- Dashboard 增加一轮 turn 的完整时间线视图。
- 对 ToolHook trace、phase trace 做更完整展示。
- 对 observe queue drop 增加告警。
- 对敏感工具参数和结果做脱敏，而不仅是截断。

## Q55: Proactive v2 为什么不是有新内容就主动推送？它的 tick / gate / dedupe 流程是什么？

### 标准答案

Proactive v2 的核心不是“定时把 feed 推给用户”，而是一个独立于被动 `AgentLoop` 的后台主动决策系统。

它要解决的问题是：

```text
有新内容 ≠ 应该打扰用户
```

主动 Agent 比被动问答更容易出问题，因为它不是用户显式发起的。如果只要 feed 有内容就推送，会带来几个风险：

- 打扰用户。
- 重复推送相似内容。
- 把抓取失败或低价值内容误判为可推送内容。
- 在用户正在和被动 Agent 对话时插入主动消息。
- 多个来源的候选内容没有经过兴趣判断就直接发送。

所以这个项目把 proactive 做成了：

```text
后台 loop
  -> feed poll
  -> 自适应 tick
  -> pre-gate
  -> DataGateway 预取
  -> LLM tool loop 分类/决策
  -> completeness/reflection 兜底
  -> post-loop dedupe
  -> TurnOrchestrator 统一落库和发送
  -> ACK / state side effects
```

### 启动和依赖注入

主动链路由 `bootstrap/proactive.py` 的 `build_proactive_runtime()` 创建。

只有配置里：

```text
config.proactive.enabled = true
```

才会启动。

启动时会注入这些核心依赖：

- `SessionManager`：用于定位目标 session、读取最近聊天、落会话消息。
- `LLMProvider`：用于 proactive tick 中的模型决策。
- `MessagePushTool`：用于真正把主动消息推给用户。
- `MemoryRuntime`：用于 recall 用户兴趣、雷点、长期偏好。
- `PresenceStore`：用于判断用户最近活跃状态。
- `agent_loop.processing_state.is_busy`：用于判断被动对话是否正在处理。
- `ToolHook` 和 shared tools：让主动工具调用也能走统一治理。
- `ProactiveStateStore(workspace / "proactive.db")`：保存主动链路状态、tick trace、去重记录。

这说明 proactive 不是另一个孤立脚本，而是复用主 Agent Runtime 的 session、memory、provider、tool hook、outbound 编排能力。

### ProactiveLoop 做什么

`ProactiveLoop` 是常驻后台循环。

它启动时会做几件事：

1. 准备 `PROACTIVE_CONTEXT.md`。
2. 初始化 `ProactiveStateStore`。
3. 初始化 `PresenceStore`、`Sensor`、`AnyActionGate`、`MessageDeduper`、`TurnOrchestrator`。
4. 连接 MCP content source pool。
5. 先同步 poll 一次 feed，保证第一次 tick 能拿到新内容。
6. 后台持续 poll feed，同时按自适应间隔执行 tick。

关键点是：

```text
feed poll 和 proactive tick 是分开的
```

feed poll 负责把候选内容同步进来；tick 负责判断“现在是否应该处理、是否应该发、发什么”。

这样做比“poll 到内容立即发”更稳，因为 tick 前后可以插入 presence、quota、cooldown、dedupe、memory recall、recent chat 等判断。

### 自适应 tick 间隔

`ProactiveLoop._next_interval()` 会根据 presence 计算下一次 tick 间隔。

如果没有 presence，就退回固定：

```text
config.interval_seconds
```

如果有 presence，就根据用户最后活跃时间计算 energy score，再用：

```text
next_tick_from_score(...)
```

把 score 映射到不同 tick 间隔。

这个设计表达的是：

```text
用户越可能可被打扰，tick 可以更积极；
用户越不适合被打扰，tick 间隔应该拉长。
```

同时它会把配置快照和 rate 决策写入：

```text
workspace/memory/proactive_config_trace.jsonl
workspace/memory/proactive_rate_trace.jsonl
```

方便后续解释为什么 tick 这么频繁或这么保守。

### pre-gate：为什么还没调用 LLM 就可能跳过

`AgentTick.tick()` 在真正调用模型前会先做硬门控。

主要包括：

```text
1. no_target
2. passive_busy
3. delivery_cooldown
4. AnyAction gate
5. context fallback quota/probability
```

分别解释：

`no_target`：

如果没有 `default_chat_id`，说明不知道要推给谁，直接跳过。

`passive_busy`：

如果被动 `AgentLoop` 正在处理同一个 session，主动链路直接让路。这避免用户正在提问时，后台主动消息插入对话。

`delivery_cooldown`：

如果这个 session 在冷却窗口内已经收到过主动消息，就跳过。它防止主动消息频率过高。

`AnyAction gate`：

`AnyActionGate` 会检查每日 quota、最小动作间隔、用户 idle 时间和概率门。它不是只看“有没有内容”，而是先问：

```text
今天还剩多少主动动作额度？
距离上次主动动作够久吗？
用户 idle 时间是否足够？
当前概率抽样是否允许行动？
```

`context fallback`：

当没有 alert/content 时，系统允许低概率使用 context 主动展开话题，但有最小间隔和每日次数上限。

这些 pre-gate 的价值是：

```text
在最便宜、最确定的层面先挡掉不该发生的 proactive 行为。
```

这样可以减少 LLM 调用，也降低误打扰。

### DataGateway：为什么先预取再让模型决策

通过 pre-gate 后，`AgentTick._run_loop()` 会创建 `DataGateway`，并行预取三类输入：

```text
alerts
content
context
```

其中：

- `alerts`：高优先级告警，直接进入 prompt。
- `context`：背景上下文，直接进入 prompt。
- `content`：先保留轻量 meta，同时并行 `web_fetch` 正文，正文放到 `content_store`。

注意 content 的正文不是直接全部塞进 prompt，而是：

```text
content_meta 放 prompt
正文放 hashmap
模型需要时用 get_content 按 item_id 取
```

这样做可以控制 prompt 体积，也能让模型按需读取正文。

如果 alert、content 都为空，并且 context fallback 没打开，系统会直接 skip LLM。若 drift 功能开启，则可能尝试 drift，否则直接：

```text
terminal_action = skip
skip_reason = no_content
```

### proactive tool loop 如何决策

进入 LLM loop 后，系统 prompt 会明确告诉模型：

```text
Alert > Content > Context-fallback
```

模型可用的关键工具包括：

- `recall_memory`：检索用户兴趣、偏好、雷点。
- `get_content`：从本 tick 预取缓存里读取正文。
- `web_fetch`：对候选自带 URL 做直接来源验证。
- `get_recent_chat`：判断现在是否适合打扰。
- `mark_interesting`：标记候选内容值得推。
- `mark_not_interesting`：标记候选内容不值得推。
- `message_push`：暂存要发送的消息草稿。
- `finish_turn`：提交 reply 或 skip，终止 loop。

这里非常重要的一点是：

```text
mark_interesting / mark_not_interesting 不是终止动作
message_push 也不是终止动作
只有 finish_turn 才终止本轮 tick
```

这让模型必须经历：

```text
分类 -> 生成草稿 -> 提交决策
```

而不是随便标记一个内容后就结束。

### completeness 和 reflection 兜底

项目还做了两个约束，防止模型半途而废。

第一个是 completeness check。

如果模型已经 `finish_turn(skip)`，但本轮 content 里还有未分类条目，系统会清空 terminal action，再提示模型补完分类：

```text
每条 content 必须 mark_interesting 或 mark_not_interesting
```

第二个是 reflection pass。

如果模型已经标记了 interesting，但还没有调用 `finish_turn`，系统会注入提示，要求它：

```text
message_push + finish_turn(reply)
或 finish_turn(skip)
```

这两个兜底说明项目承认 LLM tool loop 可能不稳定，所以用确定性程序逻辑约束它的完成状态。

### post-loop dedupe：为什么模型说要发也不一定真的发

LLM loop 结束后，`_post_loop()` 会把 `AgentTickContext` 归并成 `TurnResult`，但在真正发送前还有 post-guard。

主要有两层去重：

```text
1. delivery dedupe
2. message semantic dedupe
```

`delivery dedupe` 看的是来源证据集合。

它会根据本轮引用的 content/alert 构造 `delivery_key`，如果同一批来源内容在窗口期内已经发过，就跳过。

`message semantic dedupe` 看的是最终消息语义。

如果开启 `message_dedupe_enabled`，系统会拿新消息和最近主动消息比较，判断是否实质重复。如果重复，也会 skip。

所以 proactive 的发送逻辑不是：

```text
模型决定 reply -> 一定发送
```

而是：

```text
模型决定 reply
  -> delivery dedupe 通过
  -> semantic dedupe 通过
  -> TurnOrchestrator 发送
```

这能减少“同一条新闻换个说法又推一次”的问题。

### ACK 和状态副作用

主动链路还会根据结果做 ACK。

大致逻辑是：

- 成功发送：记录 delivery，必要时记录 context-only send，对引用内容或 alert 做成功 ACK。
- skip：对 discarded 内容做 ACK，避免短期内重复出现。
- post-guard 去重失败：对相关内容做 post-guard fail ACK。
- 发送失败：对 discarded 内容做 ACK 或进入失败副作用。

这些副作用以 `TurnResult` 的 side effects 形式交给 `TurnOrchestrator` 处理。

这和被动链路共享一个重要思想：

```text
决策结果和外部副作用分离
```

模型只负责形成 `reply/skip` 决策和消息草稿，真正落 session、发送、ACK、记录 delivery 由编排器和状态层完成。

### 状态和观测

Proactive v2 的状态主要落在：

```text
workspace/proactive.db
```

里面包括：

- tick_log：每次 tick 的整体结果。
- tick_step_log：每一步工具调用及调用后状态。
- seen_items：已见内容。
- deliveries：已发送内容去重。
- semantic_items / rejection_cooldown 等主动相关状态。

每个 tick 会记录：

```text
tick_id
session_key
gate_exit
terminal_action
skip_reason
steps_taken
alert_count
content_count
context_count
interesting_ids
discarded_ids
cited_ids
drift_entered
final_message
```

这让 Dashboard 或后续排查可以回答：

```text
这次为什么没发？
是 no_target、busy、cooldown、presence gate，还是 LLM skip？
模型分类了哪些内容？
最后引用了哪些 evidence？
是否因为 delivery/message dedupe 被拦截？
```

### 设计取舍

优点：

- 主动链路不会简单打扰用户。
- pre-gate 降低成本和误触发。
- content 预取和按需读取平衡了信息量和 prompt 体积。
- completeness/reflection 能约束 LLM tool loop 不完整的问题。
- delivery dedupe 和 semantic dedupe 降低重复推送。
- `TurnOrchestrator` 统一处理 session 落库、发送和 side effects。
- `proactive.db` 和 trace 文件让主动行为可解释。

代价：

- 链路复杂，比简单 scheduler 难理解。
- 配置项多，需要调参。
- 多层 gate 可能导致“明明有内容却不推”，需要 Dashboard 辅助解释。
- LLM 分类仍可能误判，需要更好的评估集和回放机制。
- ACK 策略如果过强，可能把后续有价值内容也过滤掉。

### STAR 法则思考

**Situation 情景：**

项目需要让 Agent 不仅能被动回答，还能在有重要内容、上下文机会或用户兴趣命中时主动触达用户。但主动消息天然有打扰风险。

**Task 任务：**

需要设计一套 proactive runtime，既能处理 alerts/content/context，又能控制频率、判断兴趣、避免重复、尊重用户当前状态，并且能在出错时复盘原因。

**Action 行动：**

项目把主动能力拆成 `ProactiveLoop` 和 `AgentTick`：后台 loop 负责 feed poll 和自适应 tick；pre-gate 负责 no_target、busy、cooldown、quota、presence 判断；`DataGateway` 负责预取 alerts/content/context；LLM tool loop 负责逐条分类、召回记忆、读取正文、生成草稿和 finish；post-loop 负责 delivery/message dedupe；`TurnOrchestrator` 统一执行发送、落库和 ACK side effects。

**Result 结果：**

最终 proactive 不再是粗暴的定时推送，而是一个可控、可解释、可调试的主动 Agent 子系统。它能降低打扰和重复推送风险，也能通过 `proactive.db`、tick trace、step trace 复盘每次主动行为为什么 reply 或 skip。

### 面试总结

可以这样回答：

```text
Proactive v2 不是有内容就推，而是一个独立于被动 AgentLoop 的后台主动决策 runtime。它由 build_proactive_runtime 启动，ProactiveLoop 负责 feed poll 和自适应 tick，AgentTick 负责单次主动决策。每次 tick 先经过 no_target、passive_busy、delivery_cooldown、AnyAction quota/probability、context fallback 等 pre-gate；通过后 DataGateway 并行预取 alerts/content/context；再由 LLM tool loop 使用 recall_memory、get_content、web_fetch、get_recent_chat、mark_interesting、message_push、finish_turn 完成分类和决策。模型决定 reply 后还要经过 delivery dedupe 和 message semantic dedupe，最后由 TurnOrchestrator 统一落 session、发送消息和执行 ACK side effects。状态记录在 proactive.db 的 tick_log/tick_step_log/deliveries 等表里，所以主动行为可以解释和回放。
```

### 可以改进的地方

- 给 proactive 增加离线 replay/evaluation，用历史 feed 回放测试误推率和漏推率。
- 把 gate_exit、dedupe_reason、ACK 结果在 Dashboard 上做成单次 tick 时间线。
- 对 context fallback 引入更明确的策略分类，避免无内容时主动闲聊过多。
- 对 ACK TTL 做分层策略，区分“永久不感兴趣”和“当前时机不适合”。
- 对 proactive prompt 增加自动化测试，检查模型是否严格遵守 evidence 和分类完整性要求。

## Q56: Proactive v2 的兴趣判断是怎么做的？为什么要同时使用候选内容、长期记忆、最近对话和工作区主动规则？

### 标准答案

Proactive v2 的兴趣判断不是一个单独的“打分函数”，也不是简单用向量相似度判断“用户可能喜欢什么”。它更像一套受约束的主动决策流程：

```text
候选内容提供事实来源
长期记忆提供用户偏好和雷点
工作区主动规则提供当前主动推送约束
最近对话提供打扰判断和语境判断
模型工具循环负责逐条分类和生成最终消息
```

也就是说，兴趣判断不是只问：

```text
这条内容和用户兴趣像不像？
```

而是同时问：

```text
这条内容是不是本轮真实候选？
它是否命中用户长期兴趣？
它是否踩到用户雷点？
它是否违反当前主动推送规则？
现在发会不会打扰用户？
如果要发，最终消息能不能引用真实 evidence？
```

这就是为什么它必须同时使用多类输入。

### 第一层：候选内容决定“能判断什么”

主动链路首先通过数据预取拿到三类输入：

```text
alerts
content
context
```

它们的职责不同：

- `alerts` 是高优先级通知，优先级最高。
- `content` 是候选内容，比如 feed、外部数据源、MCP content source。
- `context` 是背景上下文，只能辅助判断，不能直接变成新闻事实。

兴趣判断的第一条边界是：

```text
只能围绕本轮真实候选内容判断，不能凭长期记忆或规则面板自行脑补新事件。
```

这点很关键。

比如用户长期喜欢某个战队，不代表 proactive 可以自己生成一条“这个战队今天可能有新闻”的推送。只有当本轮 content 里真的出现相关候选，系统才能围绕它判断是否值得发。

所以候选内容承担的是：

```text
事实来源边界
```

长期记忆和规则只能辅助筛选，不能扩展事实池。

### 第二层：长期记忆判断“用户为什么可能关心或不关心”

Proactive v2 里的 `recall_memory` 不是普通聊天里的泛用检索。

它会走兴趣召回入口，只检索：

```text
preference
profile
```

不会把普通事件记忆全部混进来。

这样设计是为了避免一个问题：

```text
用户以前聊过某事件 ≠ 用户长期关心这个主题
```

如果 proactive 把所有 event memory 都拿来做兴趣判断，就容易误以为“用户提过一次的东西都应该主动推”。所以项目把主动兴趣判断收敛到偏好和画像类记忆，重点看：

- 用户明确喜欢什么。
- 用户长期关注什么。
- 用户明确不喜欢什么。
- 用户对内容形式有什么偏好。
- 用户有哪些稳定禁忌和雷点。

工具描述里还要求模型对每条内容分别构造正向和负向假设：

```text
如果这条内容对用户有价值，用户为什么会关心？
如果这条内容让用户不感兴趣，原因可能是什么？
```

这个设计比单纯“相似度高就推”更稳，因为它同时寻找兴趣证据和反证。

### 第三层：工作区主动规则判断“当前应该怎么筛”

项目有一个专门的主动规则文件：

```text
PROACTIVE_CONTEXT.md
```

它不是普通长期记忆，也不是新闻来源，而是主动推送的规则面板。

适合放这些内容：

- 主动推送白名单。
- 主动推送黑名单。
- 哪些主题必须先验证。
- 哪些来源优先。
- 哪些内容不要主动发。
- 只在什么条件下发。
- 当前阶段用户临时调整的推送规则。

被动主 Agent 的系统提示词里也提醒：如果用户说“以后主动推送别发什么、多发什么、先验证什么、只在什么条件下发”，应维护到这个主动规则文件。

这说明项目把用户规则分成了两类：

```text
长期稳定偏好 -> 写入普通长期记忆
主动推送策略 -> 写入主动规则面板
```

这样做的好处是，proactive 不需要从大量聊天记忆里猜“当前推送策略”，而是每轮都读取一份明确的主动规则。

### 第四层：最近对话判断“现在适不适合发”

最近对话不是主要事实来源，也不是主要兴趣来源。

它更多用于判断：

```text
现在发这条消息是否自然？
用户是不是正在忙？
用户刚刚是否已经在聊相关话题？
这条主动消息会不会打断当前上下文？
```

代码里最近对话会过滤掉上下文帧，也会过滤主动推送消息，避免 proactive 把自己之前发过的主动消息当成新的事实继续循环引用。

这个设计很重要，因为主动推送不是只要内容相关就可以发。比如内容确实命中用户兴趣，但用户刚刚在进行一段紧密对话，或者刚被主动推过类似内容，此时继续发就会变成打扰。

所以最近对话承担的是：

```text
当前会话语境和打扰判断
```

### 第五层：逐条分类，而不是整批命中

Proactive v2 的 prompt 明确要求：

```text
Content 评估必须逐条进行
每条内容必须单独标记为感兴趣或不感兴趣
不能因为其中一两条相关，就把整批候选都标为感兴趣
```

这解决的是 feed 场景里的常见问题。

一个批次里可能同时有：

- 用户高度关注的内容。
- 用户完全不关心的内容。
- 标题稀疏、需要看来源的内容。
- 抓取失败但不能直接否定的内容。
- 需要按主动规则验证的内容。

如果整批统一判断，很容易误推。

所以系统要求模型对每条 content 分别：

```text
看标题和来源
必要时召回偏好记忆
必要时读取正文
必要时访问直接来源验证
最后单独分类
```

分类结果写入当前 tick 的上下文状态，后面再决定是否生成主动消息。

### 第六层：最终消息必须回到 evidence

即使某条内容被判断为感兴趣，最终发送时也不能随便发挥。

项目要求主动消息里的证据必须来自本轮真实候选：

```text
alert evidence
content evidence
```

当本轮没有 alert/content，仅允许低概率 context fallback 时，evidence 必须为空，并且不能引用外部可验证事实。

这背后的设计原则是：

```text
兴趣判断可以参考记忆和规则，但最终事实必须来自本轮候选。
```

这样可以防止 proactive 用长期记忆、训练数据或规则面板脑补事实。

### 为什么不只靠长期记忆

只靠长期记忆会有三个问题。

第一，长期记忆不是实时事实来源。

用户喜欢某个主题，不代表今天一定有值得推送的新事件。

第二，长期记忆可能过宽。

用户长期关注 AI，不代表所有 AI 新闻都值得主动发。

第三，长期记忆缺少当前推送策略。

用户可能最近临时要求“这个月不要推某类内容”或“只推经过验证的消息”，这些更适合放在主动规则里。

所以长期记忆只能回答：

```text
用户可能关心什么？
用户可能讨厌什么？
```

不能单独回答：

```text
现在该不该主动发？
```

### 为什么不只靠最近对话

只靠最近对话也不够。

最近对话只能反映短期上下文，容易被当前话题牵引。

比如用户刚刚在聊部署问题，不代表以后只对部署感兴趣；用户刚刚没提某个长期爱好，也不代表相关重要内容不该推。

最近对话更适合回答：

```text
现在发是否自然？
是否会打断用户？
是否有未完成话题可以轻轻延续？
```

它不能替代长期偏好。

### 为什么不只靠工作区主动规则

主动规则是强约束，但不是兴趣模型。

比如规则写着：

```text
只推经过来源验证的电竞转会消息
```

这条规则告诉系统怎么筛，但不告诉系统用户具体喜欢哪些队伍、哪些选手、哪些信息密度。

所以主动规则主要回答：

```text
哪些必须过滤？
哪些必须验证？
哪些条件下允许推？
```

它不能单独判断用户兴趣强度。

### 为什么不只靠 embedding 相似度

embedding 相似度适合做召回，但不适合直接做主动推送决策。

原因是主动推送的判断包含很多非相似度因素：

- 内容是否来自本轮候选。
- 是否违反主动规则。
- 是否需要先验证。
- 用户此刻是否适合被打扰。
- 是否和最近主动消息重复。
- 是否能提供可靠 evidence。
- 是否应该 ACK 或跳过。

这些都不是一个向量相似度分数能完整表达的。

所以项目选择的是：

```text
检索负责提供偏好证据
规则负责约束边界
最近对话负责判断时机
候选内容负责事实来源
模型工具循环负责综合决策
```

### 设计取舍

优点：

- 不会因为用户喜欢某主题就凭空脑补新闻。
- 能同时利用长期偏好和当前主动规则。
- 可以发现用户雷点，不只是找相似兴趣。
- 最近对话能降低打扰感。
- 逐条分类降低整批误推风险。
- evidence 约束让最终消息可追溯。

代价：

- 判断链路变长，成本高于简单打分。
- prompt 和工具协议更复杂。
- 模型仍可能分类不稳定，需要 completeness check 和后续评估。
- 主动规则文件需要被维护，否则规则可能过期。
- 长期记忆如果质量差，会影响兴趣判断。

### STAR 法则思考

**Situation 情景：**

主动 Agent 需要从外部候选内容中筛出真正值得推给用户的内容，但用户没有发起当前请求，误推和打扰风险都比被动问答更高。

**Task 任务：**

需要设计一套兴趣判断机制，既能识别用户长期偏好和雷点，又能遵守当前主动推送规则，还要保证最终消息基于真实候选内容，并考虑当前会话时机。

**Action 行动：**

项目把兴趣判断拆成多输入综合流程：候选内容限定事实边界；长期记忆提供偏好和雷点；主动规则面板提供白名单、黑名单、验证要求和临时策略；最近对话用于判断是否打扰；模型通过工具循环逐条分类候选内容，再根据分类结果生成或跳过主动消息。

**Result 结果：**

主动推送从“看到相关内容就发”变成了“有事实来源、有用户偏好证据、有规则约束、有时机判断、有 evidence 追溯”的决策流程，能显著降低误推、脑补事实和打扰用户的风险。

### 面试总结

可以这样回答：

```text
这个项目的主动兴趣判断不是单纯相似度排序，而是多输入综合决策。候选内容负责限定事实来源，长期记忆负责提供用户偏好和雷点，工作区主动规则负责约束当前推送策略，最近对话负责判断当下是否适合打扰用户。系统要求对每条候选内容逐条分类，不能因为整批里有一条相关就全部推送。最终如果要发送，消息还必须绑定本轮真实候选证据。这样主动链路既能个性化，又能避免凭空脑补、重复打扰和违反用户临时规则。
```

### 可以改进的地方

- 给兴趣判断增加离线标注集，用真实 feed 样本评估误推和漏推。
- 把“为什么这条内容被判定为感兴趣”的证据链展示到 Dashboard。
- 给主动规则文件增加过期时间或版本说明，避免旧规则长期影响判断。
- 区分“内容本身不感兴趣”和“当前时机不适合”，让 ACK 更精细。
- 对兴趣判断结果加入用户反馈闭环，例如用户忽略、回复、纠正后更新偏好权重。

## Q57: Proactive v2 里的 presence 和打扰控制如何工作？它如何判断用户当前是否适合被主动触达？

### 标准答案

Proactive v2 里的 presence 不是传统意义上的“用户是否在线”，而是一套用于主动触达决策的行为时间信号。

它主要记录两类时间：

```text
用户最后一次发消息的时间
系统最后一次主动发送成功的时间
```

这两类时间会影响四件事：

```text
1. 下一次 proactive tick 多久后发生
2. 本次 tick 是否允许进入主动行动
3. 最近是否已经主动发过，是否需要降低频率
4. 最终发送前是否要考虑用户当前对话状态
```

所以 presence 的作用不是单点判断：

```text
在线 -> 发
离线 -> 不发
```

而是参与一整套打扰控制策略。

### presence 数据存在哪里

presence 底层复用 session 数据库。

每个 session 会维护：

```text
last_user_at
last_proactive_at
```

含义分别是：

- `last_user_at`：这个 session 最近一次用户发消息时间。
- `last_proactive_at`：这个 session 最近一次主动消息成功发送时间。

这样设计的好处是：

```text
presence 和 session 绑定
```

不同渠道、不同会话的主动触达节奏不会混在一起。

比如：

```text
telegram:123
qq:456
cli:local
```

它们各自有独立的最后用户消息时间和最后主动发送时间。

### presence 什么时候更新

用户消息的 presence 更新发生在被动对话链路里。

当用户发来一条普通消息，并且这条消息会被写入 session history 时，系统会记录：

```text
当前 session 的 last_user_at
```

主动消息的 presence 更新发生在主动发送链路里。

只有当主动消息真正 dispatch 成功后，系统才记录：

```text
当前 session 的 last_proactive_at
```

这个细节很重要。

如果主动消息只是模型决定要发，但最后发送失败，就不应该更新 `last_proactive_at`。否则系统会误以为用户已经被打扰过，后续主动机会会被错误压低。

### 第一层控制：presence 影响 tick 节奏

ProactiveLoop 会周期性 tick，但 tick 间隔不是固定不变的。

如果系统没有 presence，就退回固定间隔。

如果有 presence，它会根据用户最后活跃时间计算一个“互动能量”。

直观理解是：

```text
刚聊完：互动余温高，不需要太频繁主动试探
很久没聊：互动余温低，可以拉高主动检查意愿
```

然后系统把这个信号转换成下一次 tick 的等待时间。

也就是：

```text
更适合主动检查 -> tick 间隔更短
不适合主动检查 -> tick 间隔更长
```

这不是直接决定发不发，而是决定后台主动系统“多久醒来判断一次”。

### 第二层控制：AnyAction gate 决定是否允许行动

tick 到了以后，也不是马上调用模型。

系统会先通过行动门控。

这个门控会综合：

- 今日主动动作额度。
- 距离上次主动动作的最小间隔。
- 用户距离上次发消息过去了多久。
- 当前时间下的概率抽样。

其中用户 idle 时间来自 presence。

如果用户刚刚发过消息，idle 时间很短，系统主动行动的概率会低。

如果用户很久没有发消息，idle 时间变长，主动行动概率会上升，但仍然不是 100%，因为还要经过概率抽样和 quota 限制。

这个设计体现的是：

```text
主动触达要有机会，但不能规律、频繁、确定性地打扰用户。
```

### 第三层控制：被动对话忙碌时主动链路让路

除了 presence，系统还有一个硬 veto：

```text
被动对话正在处理同一个 session 时，主动链路直接跳过
```

这解决的是实时冲突问题。

presence 只能告诉系统“用户最近什么时候说过话”，但不能告诉系统“被动 Agent 当前是不是正在处理这条消息”。

所以项目同时用了：

```text
presence 时间信号
被动处理状态
```

前者用于节奏和概率，后者用于防止主动消息插入正在进行的被动回复。

### 第四层控制：最近对话判断是否自然

通过前面的门控后，模型还可以调用最近对话读取工具。

最近对话用于判断：

- 用户是否正在进行一个未完成话题。
- 主动消息是否会打断当前上下文。
- 是否可以自然延续最近话题。
- 当前是否应该跳过，避免显得突兀。

这里要注意：

```text
presence 是时间信号
最近对话是语义信号
```

presence 能说“用户多久没说话”，但不能理解“用户刚才说的内容是不是还没聊完”。最近对话可以补上这一点。

### 第五层控制：疲劳和主动消息历史

系统还会记录最近主动发送次数和最近主动消息。

这用于两个方面：

第一，疲劳控制。

如果过去一段时间已经发过多次主动消息，就降低继续主动触达的倾向。

第二，重复控制。

如果新消息和最近主动消息语义上重复，即使模型认为可以发，最后也会被去重逻辑拦住。

presence 在这里的作用是给系统提供：

```text
用户是否回应过主动消息
距离上次主动消息多久
最近主动触达是否过密
```

比如系统主动发了一条，用户没有回应，那么后续主动概率就应该更保守。

如果用户主动回应了，说明这次主动触达可能是有效的，后续判断可以更积极一些，但仍然受 quota、冷却和语义去重控制。

### 为什么不直接按“用户在线”判断

只看用户在线不够。

原因有三个。

第一，在线不代表愿意被打扰。

用户可能正在忙，只是刚刚打开过某个渠道。

第二，离线不代表不能发。

很多主动消息本来就是异步通知，用户之后再看也可以。

第三，不同 channel 的在线状态不一定可靠。

Telegram、QQ、CLI、后台任务的活跃信号格式不同，如果强依赖“在线状态”，系统会变得很脆弱。

所以项目选择记录更稳定的行为信号：

```text
用户什么时候主动说过话
系统什么时候主动发过消息
用户有没有回应主动消息
最近主动发送是否过密
```

这些信号比“在线/离线”更适合 Agent 主动触达。

### 为什么要分多层控制

主动触达的风险不是单一风险。

它至少包含：

- 时间上是否太频繁。
- 当前是否正在被动对话。
- 内容是否值得发。
- 语义上是否重复。
- 用户是否可能反感。
- 最近是否已经疲劳。

如果只用一个规则，比如“超过 1 小时没说话就发”，会太粗糙。

所以项目拆成多层：

```text
tick 间隔：控制检查频率
行动门控：控制是否进入主动行为
被动忙碌：避免和被动对话冲突
最近对话：判断语义打扰
冷却和疲劳：控制频率
去重：控制重复消息
```

每层只解决一类问题，整体组合起来才像一个可用的主动 Agent。

### 设计取舍

优点：

- 不依赖不稳定的在线状态。
- 能按 session 独立控制主动节奏。
- 主动消息成功发送后才更新主动时间，避免失败发送污染状态。
- 用户刚说话、正在被动处理、近期已主动发送等情况都能被抑制。
- 既有确定性门控，也有概率探索，行为不会过于机械。
- 最近对话补足了 presence 无法理解语义的问题。

代价：

- 参数较多，需要调优。
- 多层 gate 可能导致“明明有内容却不发”，需要观测工具解释。
- presence 只能表示行为时间，不能精确表示用户真实心情。
- 不同 channel 的活跃模式不同，统一策略可能需要按渠道微调。
- 如果 session 记录不完整，打扰控制会变弱。

### STAR 法则思考

**Situation 情景：**

主动 Agent 需要在用户没有显式提问时主动触达，但如果频率过高、时机不对或插入正在进行的对话，就会让用户觉得被打扰。

**Task 任务：**

需要设计一套不依赖在线状态的打扰控制机制，能根据用户活跃时间、主动消息历史、被动处理状态和最近对话语义判断当前是否适合主动发送。

**Action 行动：**

项目把 presence 作为 session 级行为时间信号：用户消息更新最后发言时间，主动消息成功发送后更新最后主动发送时间。主动链路使用这些信号调整 tick 间隔、行动概率、疲劳控制和最近主动消息判断；同时用被动忙碌状态防止插入正在处理的对话，用最近对话判断语义上是否自然。

**Result 结果：**

主动触达从简单定时通知变成了分层打扰控制：既能减少频繁打扰和重复推送，也能在用户较久未互动、内容确实有价值时保留主动触达机会。

### 面试总结

可以这样回答：

```text
这个项目的 presence 不是简单在线状态，而是记录每个会话里用户最后发言时间和系统最后主动发送成功时间。主动链路会用这些时间信号控制检查频率、行动概率、疲劳和冷却：用户刚聊完时更保守，久未互动时可以更积极，但仍要经过额度、最小间隔、被动对话忙碌、最近对话语义、去重等多层判断。这样设计的重点是降低主动消息的打扰感，让主动 Agent 不只是定时推送，而是根据用户行为节奏和当前上下文决定是否适合触达。
```

### 可以改进的地方

- 在 Dashboard 上展示一次 proactive skip 到底是 presence、quota、busy、cooldown 还是语义去重导致。
- 按 channel 配置不同的打扰策略，例如 CLI、Telegram、QQ 的活跃模式不同。
- 增加用户反馈信号，比如用户忽略、回复、手动关闭主动推送后调整主动概率。
- 区分“刚刚聊完不适合插入”和“刚刚聊完但用户明确等待通知”的特殊场景。
- 为 presence 增加更丰富的状态，例如用户本地时间段、勿扰窗口、工作日/周末模式。

## Q58: Proactive v2 的 ACK 策略是什么？为什么不同结果要有不同的已读、丢弃和冷却处理？

### 标准答案

Proactive v2 的 ACK 策略，本质上是在回答一个问题：

```text
本轮看过的 alert/content，后续还要不要再出现？
如果要避免重复，应该避免多久？
```

这里的 ACK 不是普通聊天里的“确认收到”，而是主动内容源的处理反馈。

它告诉外部数据源或 MCP content source：

```text
这条内容已经被处理过
短期内不要再作为候选重复出现
```

但不同结果不能用同一个 ACK 策略。

因为：

```text
成功发送
模型主动丢弃
发送前被去重拦截
最终发送失败
```

这几种情况表达的含义完全不同。

### 为什么需要 ACK

主动链路会不断轮询外部内容源。

如果没有 ACK，系统会反复看到同一批内容：

```text
feed 里同一条内容
alert 里同一个事件
抓取失败但仍留在源里的候选
已经判断不感兴趣的条目
已经成功推给用户的条目
```

这样会导致几个问题：

- 同一条内容反复进入模型判断。
- 用户可能收到重复推送。
- 模型成本浪费。
- Dashboard 里大量重复 tick 噪声。
- 主动系统看起来像“卡在同一批内容上”。

所以 ACK 的作用是：

```text
把主动系统对候选内容的处理结果反馈给内容源，让后续候选池更新。
```

### ACK 和 delivery dedupe 的区别

ACK 和发送去重不是一回事。

ACK 面向内容源：

```text
这条候选内容后续还要不要再拿出来
```

发送去重面向用户侧：

```text
这条消息或这批来源是否已经推给用户
```

两者都防重复，但边界不同。

比如同一篇文章换了 event id，如果只靠 ACK，可能挡不住；所以项目还会根据稳定 URL、标题、来源等构造发送去重标识。

反过来，如果只靠发送去重，不做 ACK，内容源仍会反复把同一条候选拿出来，导致每次 tick 都要重新判断。

所以它们是互补关系：

```text
ACK 控制候选池重复
delivery/message dedupe 控制用户侧重复发送
```

### 成功发送后的 ACK

当主动消息真正发送成功后，系统会做三类处理。

第一，被最终消息引用的 content 会被较长时间 ACK。

含义是：

```text
这条内容已经成功推给用户，短期内不要再出现
```

当前策略里，被引用的 content 使用较长冷却，约 168 小时。

第二，被判断为 interesting 但没有被最终引用的 content，会被短时间 ACK。

含义是：

```text
这条内容有一定价值，但本轮没有放进最终消息，短期内先别重复打扰判断
```

当前策略里，这类内容约 24 小时。

第三，被明确判断为不感兴趣的 content，会被长时间 ACK。

含义是：

```text
这条内容本质上不适合用户，较长时间内不要再出现
```

当前策略里，这类内容约 720 小时，也就是 30 天。

这三个时间长度不同，是因为它们代表的语义不同：

```text
已发送：用户已经看过
有价值但未引用：可能以后还有机会
不感兴趣：长时间过滤
```

### alert 为什么要单独 ACK

alert 和 content 的 ACK 通道不同。

content 通常走：

```text
内容条目 ACK + TTL
```

alert 通常走：

```text
事件 ACK
```

alert 是高优先级通知，更像一次性事件。

比如：

```text
某个系统告警
某个即时提醒
某个外部事件触发
```

这类事件被处理后，不应该像普通 content 那样依赖相同 TTL 策略，而应该走 alert 专用确认通道。

如果没有 alert 专用通道，系统才回退到普通 content ACK。

这说明项目区分了两种来源语义：

```text
content 是可重复候选内容
alert 是一次性高优先级事件
```

### 普通 skip 的 ACK

如果模型最终决定 skip，并且没有进入发送路径，系统不会把所有候选都 ACK。

它只会对明确被标记为不感兴趣的内容做长时间 ACK。

这很合理。

因为 skip 可能有很多原因：

- 本轮没有值得推的内容。
- 用户当前不适合被打扰。
- 模型没有找到足够证据。
- 内容抓取失败。
- 候选内容还没被充分分类。

如果 skip 时把所有内容都 ACK 掉，会导致：

```text
一些只是“当前时机不适合”的内容被误判为“长期不感兴趣”
```

所以普通 skip 的 ACK 比成功发送更保守。

它只处理模型明确丢弃的内容，不随便清空候选池。

### 发送前去重命中后的 ACK

如果模型已经生成了要发的消息，但在真正发送前被去重拦截，系统会走 post-guard fail ACK。

这通常发生在：

```text
同一批来源内容已经发过
新消息和最近主动消息语义重复
```

这种情况和普通 skip 不一样。

普通 skip 可能是内容不够好；去重 skip 是内容可能有效，但用户已经收到过相似信息。

所以项目会对：

- 被引用的 content 做短时间 ACK。
- 被引用的 alert 走 alert ACK。
- 未引用但 interesting 的 content 做短时间 ACK。
- discarded 内容做长时间 ACK。
- 本轮其他未引用 alert 也会被清掉，避免 alert 批次反复触发。

这里用短时间 ACK 的原因是：

```text
内容不是没价值，而是当前重复了
```

所以不应该像“不感兴趣”那样长时间屏蔽。

### 发送失败后的 ACK

发送失败时，系统不会把 cited 内容当作已发送处理。

这点非常关键。

如果消息没发出去，却把引用内容做长时间 ACK，系统就会误以为用户已经看过这条内容。

因此发送失败路径只 ACK 被明确丢弃的内容。

也就是说：

```text
发送成功 -> 可以 ACK 已引用内容
发送失败 -> 不能 ACK 已引用内容
```

这避免了“消息没发出，但内容消失”的问题。

### ACK 副作用为什么挂在 TurnResult 上

项目没有在模型调用工具时立刻 ACK。

ACK 是在一轮主动决策收口成结果后，以 side effect 的形式交给发送编排器处理。

这样做有两个好处。

第一，模型决策和外部副作用分离。

模型只负责：

```text
分类
写草稿
提交 reply/skip
```

系统负责：

```text
发送
落会话
记录发送去重
ACK 内容源
更新 presence
```

第二，ACK 可以根据最终发送结果选择不同路径。

比如主动消息真正发送成功，才执行成功路径的 ACK；发送失败则执行失败路径的 ACK。

如果 ACK 在模型刚标记 interesting 时就执行，就无法区分这些最终结果。

### ACK 策略背后的核心原则

可以把 Proactive v2 的 ACK 原则概括成四条：

```text
看过但不一定处理完，不要随便 ACK
明确不感兴趣，可以长时间 ACK
成功发给用户，可以较长时间 ACK
重复或去重拦截，只做短时间 ACK
发送失败，不能把引用内容当作已发送 ACK
```

这套策略的重点是避免两个极端。

第一个极端是 ACK 太弱：

```text
同一批内容反复出现，系统重复判断、重复推送。
```

第二个极端是 ACK 太强：

```text
有价值内容因为一次失败、一次时机不合适，就长期消失。
```

当前设计就是在两者之间做平衡。

### 设计取舍

优点：

- 避免同一内容反复进入主动候选池。
- 成功发送、丢弃、重复、失败四类结果语义清楚。
- 发送失败不会误 ACK 用户没看到的内容。
- alert 和 content 分通道处理，符合不同来源语义。
- ACK 作为 side effect 延后执行，能根据最终结果选择正确路径。

代价：

- ACK 规则较复杂，调试成本高。
- TTL 固定配置可能不适合所有内容源。
- 如果模型错误标记不感兴趣，内容会被长时间屏蔽。
- alert 批次清空策略可能误清理未完全处理的 alert。
- 内容源必须正确实现 ACK 工具，否则主动链路会反复看到旧内容。

### STAR 法则思考

**Situation 情景：**

主动 Agent 会持续轮询外部内容源。如果没有处理反馈，同一批内容会反复出现，导致重复判断、重复推送和用户打扰。

**Task 任务：**

需要设计一套 ACK 策略，能根据主动决策结果区分成功发送、不感兴趣、重复拦截和发送失败，既避免重复，又不能误删用户还没看到的有价值内容。

**Action 行动：**

项目把 ACK 放在主动 turn 的副作用阶段处理：成功发送后确认已引用内容、短期确认未引用但有价值的内容、长期确认明确不感兴趣的内容；普通跳过只确认明确丢弃内容；发送前去重命中时做短期确认；发送失败时不确认已引用内容，只处理明确丢弃项。alert 走独立事件确认通道，content 走带冷却时间的内容确认通道。

**Result 结果：**

主动链路可以减少重复候选和重复推送，同时避免“消息没发出去但内容被当作已发送”的错误。不同结果对应不同冷却时间，也让系统在去重和保留未来机会之间取得平衡。

### 面试总结

可以这样回答：

```text
这个项目的 ACK 不是简单已读，而是主动内容源的处理反馈。成功发出的内容会较长时间冷却，明确不感兴趣的内容会更长时间屏蔽，有价值但未引用或因为重复被拦截的内容只做短期冷却，发送失败则不能把引用内容当作已发送处理。alert 和普通 content 还走不同确认通道。这样做的原因是，不同结果表达的语义不同：有的是用户已经看过，有的是内容本身不适合，有的是当前重复，有的是发送失败。统一 ACK 会导致要么重复推送，要么误丢有价值内容。
```

### 可以改进的地方

- 在 Dashboard 上展示每个 item 的 ACK 原因和 TTL。
- 把 ACK TTL 配置按内容源、主题或优先级细分。
- 区分“模型不感兴趣判断”和“规则过滤判断”，使用不同冷却时间。
- 对 alert 批次清空策略增加更细粒度证据，避免未处理 alert 被误确认。
- 增加 ACK 失败重试或补偿队列，避免内容源确认失败导致重复出现。

## Q59: Proactive v2 的 drift 机制解决什么问题？它和普通 content/alert 推送有什么区别？

### 标准答案

Drift 机制解决的是一个和普通主动推送不同的问题：

```text
当没有外部 alert/content 候选时，Agent 是否还能利用空闲时间做一点有意义的事？
```

普通 proactive 更像“基于外部候选内容的主动推送”。

Drift 更像“空闲时的自主小行动”。

两者的目标不同：

```text
普通 proactive:
  有 alert/content/context -> 判断是否值得发给用户

drift:
  没有 alert/content 可推 -> 看看是否有长期记忆、近期上下文或 skill 里的小任务值得推进
```

所以 drift 不是普通 content 推送的另一个名字，而是主动链路里的另一种工作模式。

### drift 什么时候会进入

Drift 不是每次 tick 都进入。

它有几个前提：

```text
1. proactive 已经通过前置 gate
2. 本轮没有 alert
3. 本轮没有 content
4. context fallback 没有打开
5. drift 功能已启用
6. 距离上次 drift 已经过了最小间隔
7. 当前存在可用 drift skill
```

这说明 drift 是一个 fallback 路径。

它不是抢在普通主动推送之前运行，而是在普通主动链路没有外部候选可处理时，才尝试进入。

如果没有 alert/content，而且 drift 也不能进入，系统会直接 skip，原因是：

```text
no_content
```

### 为什么 drift 需要最小间隔

Drift 属于更“自主”的行为。

它不像 alert 那样有明确外部事件，也不像 content 那样有明确候选事实。

如果没有频率控制，Agent 可能会频繁进行自发行动，用户会觉得它过于主动。

所以系统记录每个 session 的上次 drift 时间，并配置最小间隔。

这表达的是：

```text
drift 可以存在，但必须比普通内容推送更克制。
```

### drift 的输入是什么

Drift 的输入和普通 proactive 不同。

普通 proactive 主要看：

```text
alerts
content
context
workspace proactive rules
long-term memory
recent chat
```

Drift 主要看：

```text
长期记忆
近期上下文
drift skills
drift 运行历史
drift 工作区文件
可挂载的外部能力
```

它的上下文会告诉模型：

- drift 工作区在哪里。
- 用户长期记忆是什么。
- 最近上下文是什么。
- 当前有哪些可用 skill。
- 每个 skill 最近运行过几次。
- skill 的 next 状态是什么。
- 最近几次 drift 做了什么。
- 有哪些 MCP server 可以挂载。

这说明 drift 的重点不是“筛新闻”，而是：

```text
从一组长期小任务或兴趣技能中，选一个当前最值得推进的动作。
```

### drift skill 是什么

Drift 通过 skill 组织自主行为。

每个 skill 有自己的：

```text
SKILL.md
state.json
working files
next
run_count
last_run_at
requires_mcp
```

模型进入 drift 后，不能随便瞎聊。

它必须先比较所有可用 skill，再选择一个当前最值得执行的 skill，然后读取该 skill 的说明和工作文件，执行一个明确动作。

这让 drift 有了“任务边界”。

否则自主行为很容易变成：

```text
模型突然想聊什么就聊什么
```

而 skill 机制把它约束成：

```text
围绕已定义的小能力、小项目、小兴趣任务推进
```

### drift 能调用哪些工具

Drift 有自己的一组工具。

主要包括：

- 读写 drift 工作区文件。
- 编辑 drift 工作区文件。
- 召回记忆。
- 搜索和抓取网页。
- 搜索或回看历史消息。
- 执行 shell。
- 发送一条主动消息。
- 结束 drift 并保存状态。
- 挂载外部 MCP 能力。

这些工具不是为了处理本轮 content 候选，而是为了完成一个 drift skill 的小动作。

比如：

```text
整理一个长期小项目的下一步
维护一个用户可能关心的素材库
基于记忆做一次轻量探索
生成一张图片或整理一个灵感
在合适时机发一句自然的消息
```

### drift 发送消息的限制

Drift 可以发送消息，但限制比普通主动推送更严格。

单次 drift 只能发送一次。

一旦已经发送消息，后续工具会被限制为：

```text
写文件
编辑文件
结束 drift
```

也就是说，发送后不允许继续搜索、继续召回、继续调用外部工具。

这个设计是为了防止：

```text
已经打扰用户以后，Agent 还在后台继续扩展话题和做额外动作
```

Drift 发送应该是一次轻量触达，不应该变成开放式工具链。

### drift 必须保存结束状态

Drift 结束时必须保存：

```text
本轮用了哪个 skill
做了什么一句话总结
下一步是什么
本轮是否发送了消息
可选备注
```

这些状态会写到 drift 工作区。

下一次 drift 进入时，系统会把最近运行记录和 skill 的 next 状态放回上下文。

这让 drift 不是一次性闲聊，而是有连续性的自主小任务。

### drift 和普通 proactive 的关键区别

可以从六个维度区分。

第一，触发条件不同。

普通 proactive 处理 alert/content/context。

Drift 只在没有 alert/content、普通路径没有可处理内容时进入。

第二，事实来源不同。

普通 proactive 的最终事实必须来自本轮候选 evidence。

Drift 更偏向长期记忆、近期上下文、skill 工作文件和自主探索。

第三，输出目标不同。

普通 proactive 目标是判断“这条候选是否值得推”。

Drift 目标是判断“空闲时是否有一个小任务值得推进，必要时是否自然告诉用户”。

第四，状态管理不同。

普通 proactive 状态围绕 tick、候选内容、ACK、delivery、dedupe。

Drift 状态围绕 skill、run history、next action 和 drift 工作区文件。

第五，工具边界不同。

普通 proactive 的工具围绕内容分类、读取正文、记忆召回、最近对话和发送。

Drift 的工具更像一个小工作台，包含文件、搜索、记忆、外部能力挂载和结束状态保存。

第六，风险不同。

普通 proactive 的主要风险是重复推送和误判内容价值。

Drift 的主要风险是过度自主、偏离用户真实需求、把内部任务感暴露给用户。

### 为什么不把 drift 合并进普通 proactive

如果把 drift 合并进普通 proactive，会让普通主动推送 prompt 变得非常混乱。

普通 proactive 需要严格遵守：

```text
只围绕本轮候选内容
不能脑补事实
必须逐条分类
必须 evidence 绑定
```

而 drift 需要允许：

```text
读取 skill
推进文件
基于长期记忆做轻量探索
没有 evidence 时也可以 silent 完成
必要时自然发一句消息
```

这两套规则是冲突的。

如果放在一个 prompt 里，模型很容易：

- 在普通 content 推送里脑补长期记忆事实。
- 在 drift 里误以为必须引用 content evidence。
- 把空闲小任务和新闻推送混在一起。
- 发送过于流程化的“我刚刚做了某任务”的消息。

所以项目把它们拆开：

```text
普通 proactive: 内容候选决策
drift: 空闲自主小行动
```

### drift 和 context fallback 的区别

Context fallback 是普通 proactive 的低概率分支。

它仍然更接近“基于当前背景上下文发一条轻量消息”。

Drift 则是 skill 驱动的自主工作模式。

两者区别可以理解为：

```text
context fallback:
  没有内容，但最近上下文里有自然延伸话题，可以轻轻说一句

drift:
  没有内容，进入一个带状态的小工作区，选择一个 skill 做一点事
```

所以 drift 的动作范围更大，也更需要状态保存和频率限制。

### drift 的可观测性

Drift 进入后会在 tick 日志里标记：

```text
drift_entered
```

Dashboard 可以按普通 proactive 和 drift 区分查看。

同时 drift 自己会保存最近运行记录，包括：

```text
skill
run_at
one_line
message_result
next
```

这能解释：

```text
为什么这次没有普通推送却有一次 drift？
drift 做了什么？
有没有发消息？
下一步准备做什么？
```

### 设计取舍

优点：

- 让 Agent 在没有外部内容时也能做轻量、有状态的小行动。
- 和普通 content/alert 推送分离，避免规则冲突。
- skill 机制给自主行为加了边界。
- run history 和 next action 让小任务有连续性。
- 单次发送限制降低过度主动风险。
- 可挂载 MCP 能力，保留扩展空间。

代价：

- 自主性更强，风险比普通内容推送更高。
- skill 质量决定 drift 质量，空 skill 或坏 skill 会让效果变差。
- 需要维护 drift 工作区状态。
- 如果频率控制不当，用户可能觉得 Agent 过度活跃。
- 需要更强的评估和审计，判断 drift 是否真的有价值。

### STAR 法则思考

**Situation 情景：**

主动 Agent 不是每次 tick 都有外部内容可推。如果没有内容就完全空转，Agent 的长期陪伴感和自主性会比较弱；但如果随便主动聊天，又容易打扰用户或偏离需求。

**Task 任务：**

需要设计一种空闲模式，让 Agent 在没有 alert/content 时，也能围绕用户长期记忆、近期上下文和预定义 skill 做轻量、有边界、有状态的小行动，并在必要时自然触达用户。

**Action 行动：**

项目把 drift 设计成普通主动推送之后的 fallback：只有无外部候选且满足间隔限制时才进入。进入后读取长期记忆、近期上下文、可用 skill、运行历史和工作区状态；模型必须选择一个 skill，读取说明和工作文件，执行明确动作，并用结束工具保存本轮总结、下一步和是否发消息。若发送消息，单轮只能发一次，发送后只能写文件或结束。

**Result 结果：**

Agent 在没有内容可推时也能推进长期小任务或轻量探索，同时不会破坏普通 proactive 的 evidence 约束。Drift 通过 skill、状态文件、间隔限制和发送限制，把“自主性”控制在可解释、可复盘的边界内。

### 面试总结

可以这样回答：

```text
Drift 是主动链路里的空闲自主模式，不是普通内容推送。普通主动推送处理外部 alert 和 content，要求事实来自本轮候选并绑定证据；Drift 只在没有外部候选、普通路径无事可做且满足间隔限制时进入。它会基于长期记忆、近期上下文和一组预定义 skill，选择一个小任务推进，必要时自然发一条消息，并保存本轮做了什么和下一步。这样既让 Agent 有一定自主性，又不会把普通新闻推送和空闲小行动混在一起。
```

### 可以改进的地方

- 为每个 drift skill 增加明确的风险等级和可用工具白名单。
- Dashboard 展示 drift 的 skill 选择理由、工具步骤和最终状态。
- 增加用户反馈闭环，用户不喜欢某类 drift 时自动降低频率或禁用 skill。
- 区分只写工作区的 silent drift 和会触达用户的 sent drift，分别配置频率。
- 给 drift 增加离线评估集，判断它是否真正产生了有价值的长期小成果。

## Q60: 主动推送失败时系统如何处理？如何避免消息没发出去但内容被错误标记为已处理？

### 标准答案

主动推送失败处理的核心目标是：

```text
不能让用户没看到的内容，被系统当成已经成功发送。
```

主动链路里失败可能发生在多个阶段：

- 数据源拉取失败。
- 模型没有返回工具调用。
- 工具调用失败。
- 发送前被去重拦截。
- 外部渠道发送失败。
- ACK 内容源失败。
- side effect 执行失败。
- drift message_push 失败。

这些失败不能用同一种方式处理。

项目的总体策略是：

```text
前置失败不进入发送
模型/工具失败会停止本轮或走 skip
去重拦截走短期 ACK
真正发送失败不 ACK 已引用内容
发送成功后才记录 delivery 和 presence
side effect 失败只记日志，不拖垮主链路
```

### 数据源拉取失败如何处理

主动链路会先通过数据预取拿到：

```text
alerts
content
context
```

每一路拉取都有容错。

如果某一路失败，通常会记录 warning，然后返回空列表，不阻断其他来源。

这样做的原因是：

```text
某个内容源失败，不应该让整个 proactive tick 崩掉。
```

比如 content feed 失败，但 context 仍然可用；alert 失败，也不代表 memory 和 recent context 都不可用。

不过这里也有代价：

```text
部分数据源失败可能表现为本轮无内容
```

所以 Dashboard 和日志需要能看出是“真的无内容”，还是“拉取失败导致无内容”。

### 模型或工具失败如何处理

进入主动工具循环后，如果模型没有返回工具调用，本轮会停止继续执行。

如果工具执行返回错误，系统会：

```text
记录本步工具错误
把工具错误结果写回消息上下文
停止当前 loop
```

这避免模型在错误工具调用上无限循环。

如果最终没有形成 `reply` 决策，后处理会把这一轮收口为 skip。

普通 skip 路径不会把所有候选都 ACK，只会处理模型明确标记为不感兴趣的内容。

这可以避免：

```text
只是因为工具失败或模型中断，就把候选内容错误标记为已处理。
```

### 发送前去重拦截不算发送失败

如果模型已经决定要发，但发送前命中来源去重或语义去重，这不属于渠道发送失败。

它表示：

```text
这条内容可能有价值，但用户最近已经收到过相同或相似内容。
```

所以系统不会真正发送消息，而是转成 skip。

这类 skip 会走短期 ACK。

原因是：

```text
内容不是没价值，只是当前重复。
```

因此它不能用“不感兴趣”的长时间屏蔽，也不能当成发送成功记录。

### 外部渠道发送失败如何处理

真正的发送失败发生在：

```text
系统已经准备好 outbound 消息
但外部渠道 dispatch 返回失败或抛异常
```

发送编排器会捕获异常，并把发送结果标记为失败。

如果发送失败：

```text
不记录最后主动发送时间
不执行成功路径的 ACK
不记录 successful delivery
只执行失败路径副作用
```

失败路径当前只对明确丢弃的内容做 ACK。

也就是说，最终消息引用的内容不会被当作已发送内容处理。

这点非常关键。

如果消息没发出去，但系统仍然把引用内容长时间 ACK，下一轮就不会再看到这条内容，用户也永远没收到。

当前设计避免了这个问题：

```text
只有发送成功，才把 cited 内容当作已处理。
```

### 为什么发送成功后才更新 presence

主动消息成功发送后，系统会记录：

```text
last_proactive_at
```

这个时间会影响后续打扰控制。

如果发送失败也更新这个时间，就会出现错误：

```text
用户没有收到消息
但系统以为刚刚主动打扰过用户
后续主动机会被压低
```

所以项目只在 dispatch 成功后更新 presence。

这符合主动触达的语义：

```text
只有用户实际收到主动消息，才算一次主动触达。
```

### 为什么发送成功后才记录 delivery

发送去重记录也只应该在发送成功后写入。

如果发送失败也记录 delivery，就会导致：

```text
同一批内容后续被 delivery dedupe 拦截
但用户其实从来没看到过
```

当前设计把记录 delivery 放在成功副作用里。

也就是说：

```text
只有真正发出去，才记录这批内容已经推送过。
```

这能避免“失败发送污染去重状态”。

### ACK 失败如何处理

内容源 ACK 本身也可能失败。

比如 MCP server 断开、ack 工具异常、外部数据源不可用。

当前实现里，ACK 失败主要记录 warning，不会让主流程崩溃。

发送编排器执行 side effect 时也会捕获异常，避免某个副作用失败拖垮整轮。

这个取舍是合理的：

```text
ACK 是重要副作用，但不能因为 ACK 失败就回滚已经发出的用户消息。
```

代价是：

```text
ACK 失败可能导致同一内容后续再次出现。
```

所以更好的改进是增加 ACK 失败重试队列，而不是让 ACK 异常直接中断主流程。

### drift 发送失败如何处理

Drift 的发送也走统一的主动发送编排。

Drift message_push 会调用发送函数。

如果发送失败，工具会返回错误，不会把 `drift_message_sent` 标记为成功。

结束 drift 时，如果声明本轮 `sent`，但实际上没有成功发送，会被拒绝。

这保证了 drift 状态和真实发送结果一致：

```text
没有成功发送，就不能把本轮记录成 sent。
```

这点对 drift 很重要，因为 drift 的 run history 会影响后续自主行动。

### 当前实现里的残余风险

这里有一个需要诚实说明的工程边界：

主动 reply 路径里，系统会先把 proactive assistant 消息写入 session，然后再尝试外部渠道发送。

如果外部发送失败，当前实现不会更新 presence、不会记录 delivery、不会 ACK cited 内容，这是正确的。

但 session history 里可能已经有一条 proactive assistant 记录。

这会带来潜在问题：

- Dashboard 或历史消息可能看到一条实际没发出的主动消息。
- 后续去重或最近 proactive 读取如果依赖 session history，可能误以为发过。
- 用户侧没收到，但内部历史里已经存在。

所以更严谨的做法是：

```text
先发送成功，再落 proactive session
或者写入 pending_send 状态，发送成功后标记 sent，失败后标记 failed
```

这属于当前实现可以继续改进的地方。

### 为什么不能失败后简单重试

主动发送失败后，不能无脑立即重试。

原因是：

- 外部渠道可能临时不可用。
- 重试可能造成重复消息。
- 用户可能在重试期间已经收到延迟消息。
- 内容时效性可能已经变化。
- 重试也需要重新检查打扰控制。

更合理的策略是：

```text
记录失败原因
保留未 ACK 的 cited 内容
后续 tick 重新经过 gate、dedupe 和发送判断
必要时有专门的 retry 队列
```

当前项目更接近保守策略：失败不把 cited 内容标记成功处理，让未来仍有机会重新进入判断。

### 失败处理的核心原则

可以总结成五条：

```text
没成功发送，就不要更新最后主动发送时间
没成功发送，就不要记录 successful delivery
没成功发送，就不要 ACK cited 内容为已发送
明确丢弃的内容可以继续 ACK
副作用失败不能拖垮主流程，但需要可观测和可补偿
```

这几条原则能保护主动链路不出现最危险的问题：

```text
用户没看到，但系统以为用户看到了。
```

### 设计取舍

优点：

- 发送失败不会污染 presence。
- 发送失败不会把 cited 内容错误 ACK。
- 发送失败不会记录 delivery，后续还有机会重新处理。
- 工具错误和模型中断不会导致全量候选被清空。
- side effect 异常不会拖垮主流程。
- drift 状态会校验真实发送结果。

代价：

- ACK 失败后可能重复看到旧内容。
- side effect 失败目前主要靠日志，缺少补偿队列。
- 发送失败后 session 可能已有 proactive 记录，这是潜在不一致。
- 没有专门的重试策略，可能依赖后续 tick 自然恢复。
- 失败原因需要更结构化地进入 Dashboard。

### STAR 法则思考

**Situation 情景：**

主动 Agent 的发送链路包含模型决策、工具调用、外部渠道发送、内容源 ACK 和状态更新。任何一环失败，都可能导致用户没收到消息，或者系统状态被错误更新。

**Task 任务：**

需要设计一套失败处理机制，保证主动消息没真正发出去时，不会错误更新打扰状态、发送去重状态和内容源处理状态，同时让系统能继续运行。

**Action 行动：**

项目把主动决策收口成结果对象，并把发送成功和发送失败的副作用分开：成功后才记录主动发送时间、记录发送去重、确认已引用内容；失败时只处理明确丢弃的内容，不确认已引用内容。工具错误会记录 step 并停止本轮，ACK 或其他副作用失败只记日志，不阻断主流程。Drift 发送也会校验真实发送结果，没发出去不能记录为 sent。

**Result 结果：**

系统能避免“用户没看到但内容被当作已发送”的严重状态污染。即使渠道发送失败，引用内容仍可能在后续 tick 中重新进入判断；同时主循环不会因为单个副作用失败而崩溃。

### 面试总结

可以这样回答：

```text
主动推送失败处理的重点是防止状态污染。这个项目只有在外部渠道真正发送成功后，才更新最后主动发送时间、记录这批内容已经推送过，并确认已引用内容。发送失败时，不会把引用内容当作已处理，只会处理明确丢弃的内容；工具错误和模型中断也不会清空所有候选。这样可以避免用户没收到消息，但系统以为已经发送和已读。当前还有一个可改进点：主动消息会先写入内部 session 再发送，发送失败时内部历史可能留下未真正送达的 proactive 记录，后续可以改成 pending/sent/failed 状态。
```

### 可以改进的地方

- 把 proactive session 消息改成 pending/sent/failed 三态。
- 发送成功后再写入正式 session history，或失败时标记不可用于去重。
- 为 ACK 失败增加持久化重试队列。
- 在 Dashboard 中展示发送失败、ACK 失败、side effect 失败的结构化原因。
- 为渠道发送失败设计指数退避重试，但重试前重新检查去重和打扰控制。

## Q61: 主动链路应该如何做离线回放和效果评估？如何衡量误推、漏推和重复推送？

### 标准答案

主动链路的评估，不能只看“有没有发出去”。

因为 proactive 的目标不是简单提高发送量，而是：

```text
在合适时机，把真正有价值、不过度重复、不打扰用户的内容发出去。
```

所以它至少要评估三类问题：

```text
误推：不该发却发了
漏推：该发却没发
重复推：相同或相似内容反复发
```

除此之外，还要看：

- 是否遵守主动规则。
- 是否引用了真实候选证据。
- 是否在用户忙碌时打扰。
- 是否错误 ACK 了内容。
- 是否因为 gate 太严导致长期不发。
- drift 是否真的产生长期价值。

### 当前项目已经具备什么基础

当前项目已经有几类评估基础。

第一，主动 tick 日志。

每次 proactive tick 会记录：

```text
tick_id
session_key
started_at / finished_at
gate_exit
terminal_action
skip_reason
steps_taken
alert_count
content_count
context_count
interesting_ids
discarded_ids
cited_ids
drift_entered
final_message
```

这些字段可以回答：

```text
这一轮有没有进入主动链路？
为什么跳过？
有没有发？
引用了哪些候选？
是否进入 drift？
```

第二，工具步骤日志。

每一步工具调用会记录：

```text
工具名
工具参数
工具结果
调用后 terminal action
调用后 interesting / discarded / cited 状态
调用后 final message
```

这可以用于复盘模型为什么把某条内容标成 interesting 或 discarded。

第三，Dashboard 查询。

Dashboard 已经能按 proactive / drift 区分 tick，查看 result counts、flow counts、tick logs 和 tick steps。

这说明项目已经有在线观测基础。

第四，测试基础。

当前测试已经覆盖：

- pre-gate。
- agent loop 终止条件。
- message quality。
- recent chat 过滤。
- ACK 和 post-guard。
- drift 工具和状态。
- proactive 配置。

这些测试保证了关键机制没有明显回归。

但这还不是完整离线评估。

### 为什么单元测试不等于评估

单元测试通常回答：

```text
代码是否按预期执行？
```

主动链路评估还要回答：

```text
这个决策对用户来说是否正确？
```

比如：

- 工具循环按规则执行了，但模型可能误判兴趣。
- ACK TTL 正确执行了，但可能屏蔽了本该再看的内容。
- 去重逻辑生效了，但可能误拦截了同主题不同价值的信息。
- presence gate 生效了，但可能太保守导致漏推。

这些不是普通单元测试能完全覆盖的。

所以 proactive 需要离线回放和标注评估。

### 离线回放应该回放什么

离线回放要尽量重建一轮主动 tick 的输入。

至少包括：

```text
候选 alerts
候选 content meta
候选 content 正文
context 数据
长期记忆快照
近期上下文
工作区主动规则
presence 时间
最近主动消息
delivery / ACK / cooldown 状态
配置参数
```

只有这些输入固定，才能判断：

```text
同样输入下，模型和规则会做什么决策？
```

如果只保存最终消息，不保存当时看到的候选和状态，就无法离线复盘。

### 离线回放的基本流程

一个合理的离线回放流程可以是：

```text
1. 从历史 tick 或人工构造数据集中读取输入样本
2. 固定候选内容、记忆、规则、presence、最近对话
3. 使用 mock 数据源替代真实 MCP / 外部渠道
4. 运行主动决策链路，但禁止真实发送和真实 ACK
5. 记录模型分类、最终决策、引用证据、跳过原因
6. 和人工标注或规则期望做对比
7. 输出误推、漏推、重复、规则违规等指标
```

关键是：

```text
回放时不能真的发消息
回放时不能真的 ACK 内容源
```

否则评估会污染真实运行状态。

### 样本集应该怎么设计

主动链路评估样本不能只收集“系统真的发过的消息”。

因为那只能评估误推，无法评估漏推。

应该同时收集：

- 已发送样本。
- 被 skip 的样本。
- 被 gate 拦截的样本。
- 被去重拦截的样本。
- 内容源失败样本。
- drift sent / silent 样本。
- 人工构造的边界样本。

其中人工构造样本很重要。

例如：

```text
内容高度相关但用户刚刚被主动推过
内容相关但来源不可验证
内容看似相关但违反主动规则
同一新闻换 URL 或 event_id
用户明确不想看的主题
alert 和普通 content 同时出现
模型容易脑补比分、排名、日期的内容
```

这些边界样本能测出主动链路是否真的稳。

### 如何衡量误推

误推指：

```text
系统发了，但其实不该发。
```

常见原因包括：

- 内容与用户长期兴趣不匹配。
- 内容违反主动规则。
- 内容来源不可靠或未验证。
- 用户当前不适合被打扰。
- 内容已经发过或语义重复。
- 最终消息包含本轮候选之外的脑补事实。

误推指标可以包括：

```text
误推率 = 不该发但发了的数量 / 实际发送数量
规则违规率 = 违反主动规则的发送数量 / 实际发送数量
无证据发送率 = 没有合法 evidence 的发送数量 / 实际发送数量
打扰误推率 = 忙碌或冷却场景下发送数量 / 相关样本数量
```

误推是主动链路最敏感的指标。

因为用户通常能接受偶尔漏掉一条内容，但很难接受频繁打扰。

### 如何衡量漏推

漏推指：

```text
系统没发，但其实应该发。
```

常见原因包括：

- gate 太严格。
- 记忆召回没有命中真实兴趣。
- 模型把相关内容标成不感兴趣。
- 去重过强，误拦截不同价值内容。
- ACK 或 cooldown 过强，内容没进入候选池。
- 内容抓取失败后被错误丢弃。

漏推指标可以包括：

```text
漏推率 = 应该发但没发的数量 / 应该发的样本数量
兴趣误杀率 = 相关内容被标记为 not_interesting 的数量 / 相关样本数量
gate 误杀率 = gate 拦截但人工认为应处理的数量 / gate 拦截样本数量
去重误杀率 = 被去重拦截但人工认为应发的数量 / 去重拦截样本数量
```

漏推需要依赖标注集。

因为系统没有发送的内容，用户未必能直接反馈。

### 如何衡量重复推送

重复推送分两类。

第一，来源重复。

同一篇内容换了 event id、URL 参数、来源包装，又被发了一次。

第二，语义重复。

不同来源说的是同一件事，最终消息对用户价值高度重复。

指标可以包括：

```text
来源重复率 = 相同稳定来源重复发送数量 / 发送数量
语义重复率 = 与最近主动消息高度相似的发送数量 / 发送数量
重复间隔中位数 = 重复消息之间相隔多久
去重命中准确率 = 被去重拦截的样本中，人工认为确实重复的比例
```

重复推送的难点是：

```text
同主题不一定重复
不同主题也可能对用户价值重复
```

所以需要同时看 URL/title/source 等稳定来源特征和语义相似度。

### 如何评估打扰控制

打扰控制不是只看发送频率。

还要看发送时机。

可以评估：

- 用户刚刚发言后多久系统主动发送。
- 被动对话处理中是否被主动插入。
- 24 小时内主动发送次数。
- 用户是否回复主动消息。
- 用户是否忽略主动消息。
- 主动消息后用户是否表达负反馈。

可以设计指标：

```text
主动触达频率
冷却违规次数
用户回应率
主动消息后负反馈率
连续未回应后的继续发送次数
```

其中用户回应率不是绝对越高越好，但可以作为信号：

```text
用户常回应 -> 说明主动内容可能有价值
用户长期不回应 -> 应降低主动频率或调整内容类型
```

### 如何评估 drift

Drift 不能只用“有没有发消息”评估。

因为 drift 也可以 silent 地推进小任务。

可以评估：

- 本轮是否选择了合适 skill。
- 是否真的执行了一个明确动作。
- 是否保存了下一步。
- 是否重复做无意义动作。
- 是否过于频繁触达用户。
- sent drift 是否自然，不像流程汇报。
- silent drift 是否积累了可见成果。

指标可以包括：

```text
有效行动率
重复无效行动率
skill 覆盖度
sent / silent 比例
drift 后用户回应率
drift 工作区成果增长
```

Drift 的评估更偏长期，需要结合运行历史和人工审阅。

### 应该如何补齐评估框架

当前项目已有日志、Dashboard 和单元测试基础，但还可以补一个专门的 proactive evaluation harness。

建议包含：

```text
fixtures/
  proactive_cases/
    case_001.json
    case_002.json

runner:
  读取 case
  mock 数据源、memory、presence、recent chat、outbound、ACK
  跑主动决策
  输出 decision trace

labels:
  expected_decision: reply / skip
  expected_interesting_ids
  expected_cited_ids
  expected_skip_reason
  allowed_message_claims
  forbidden_claims

report:
  误推率
  漏推率
  重复率
  规则违规率
  evidence 合法率
  gate 误杀率
```

这样可以把 proactive 从“能运行”推进到“能被评估和调参”。

### 为什么这对面试很重要

Agent 项目面试里，很多人只能讲：

```text
我做了 RAG
我接了工具
我加了主动推送
```

但真正工程化的回答应该包括：

```text
我如何知道它推得对不对？
我如何知道它有没有打扰用户？
我如何知道某次 skip 是好事还是坏事？
我如何避免优化一个指标伤害另一个指标？
```

能讲清离线回放和评估，说明你不是只会把模型接上去，而是在考虑 Agent 行为的质量闭环。

### 设计取舍

优点：

- 离线回放能在不打扰用户的情况下验证主动策略。
- 标注集能同时衡量误推和漏推。
- tick/step 日志让失败原因可复盘。
- mock 外部源可以避免评估污染真实 ACK 和发送状态。
- 指标可以指导 gate、ACK、去重、prompt 和记忆策略调参。

代价：

- 样本标注成本高。
- 用户兴趣会变化，旧标注可能过期。
- LLM 输出有随机性，回放需要控制模型版本和参数。
- 误推/漏推往往有主观性，不能完全靠自动指标。
- 过度优化离线集可能导致线上泛化变差。

### STAR 法则思考

**Situation 情景：**

主动 Agent 的行为不是用户显式请求触发的，错误主动消息会带来明显打扰风险。仅靠单元测试和在线日志，无法判断系统到底推得准不准。

**Task 任务：**

需要设计一套离线回放和效果评估机制，能在不真实发送、不真实 ACK 的前提下复现主动决策，并衡量误推、漏推、重复推送、规则违规和打扰控制效果。

**Action 行动：**

项目已经记录 tick、工具步骤、候选数量、分类结果、引用证据、跳过原因和 drift 标记，也有 Dashboard 和 proactive 测试基础。下一步可以构建评估 harness：用固定样本 mock 候选内容、记忆、规则、presence 和最近对话，运行主动决策但禁止真实副作用，再与人工标注对比，输出误推率、漏推率、重复率、证据合法率和 gate 误杀率。

**Result 结果：**

主动链路可以从“能运行、能观测”提升到“能回放、能比较、能调参”。这能帮助系统持续降低打扰和重复推送，同时发现 gate 过严、记忆召回不足或 prompt 规则失效导致的漏推问题。

### 面试总结

可以这样回答：

```text
主动链路不能只看发送成功率，核心要评估误推、漏推和重复推送。这个项目已经有 tick 日志、工具步骤日志、Dashboard 查询和 proactive 单元测试，能复盘每轮为什么 reply 或 skip。更完整的做法是建立离线回放：固定候选内容、记忆、主动规则、presence、最近对话和去重状态，用 mock 数据源跑主动决策，但禁止真实发送和 ACK，然后和人工标注对比。指标上要看误推率、漏推率、重复率、证据合法率、规则违规率、gate 误杀率和用户回应/负反馈。这样才能证明主动 Agent 不是只会发消息，而是有质量闭环。
```

### 可以改进的地方

- 建立 `proactive_cases` 离线样本集，覆盖发送、跳过、去重、失败、drift 等场景。
- 给每个样本标注 expected decision、expected cited ids、forbidden claims 和 skip reason。
- 增加 replay runner，禁止真实 outbound 和 ACK，只输出决策 trace。
- Dashboard 增加评估报表，展示误推、漏推、重复和规则违规趋势。
- 引入用户反馈闭环，把忽略、回复、纠正、关闭推送等行为转成评估信号。

## Q62: 这个项目里的 background job 和 subagent 分别解决什么问题？它们和主 Agent 的边界在哪里？

### 标准答案

这个项目里的 background job 和 subagent 不是同一个概念。

可以这样区分：

```text
background job 是任务生命周期抽象
subagent 是执行这类任务的一种 Agent 引擎
spawn 是主 Agent 创建 subagent job 的工具入口
```

换句话说：

```text
background job 关心“任务如何创建、运行、完成、取消、回灌”
subagent 关心“一个独立 Agent 如何拿固定工具集完成单个任务”
```

两者配合后，主 Agent 就不需要把所有耗时、多步、上下文很重的任务都塞进当前对话 turn 里完成。

### 为什么需要 background job

主 Agent 的一轮对话应该保持响应性。

如果用户让系统做一个长任务，例如：

- 调研多个网页。
- 阅读一批文件。
- 对比多个实现。
- 生成一份报告。
- 执行较长的数据处理。
- 做需要很多工具调用的分析。

如果主 Agent 在当前 turn 里同步完成全部工作，会有几个问题：

- 用户等待时间长。
- 当前对话上下文被工具结果撑爆。
- 主 Agent 容易陷入长工具链。
- 一旦任务失败，整轮对话体验很差。
- 多个长任务无法管理、取消和追踪。

background job 解决的是：

```text
把长任务从当前对话 turn 中拆出去，给它独立生命周期。
```

它需要管理：

```text
job_id
label
task
status
exit_reason
result_summary
started_at / finished_at
completion_mode
persistence_mode
```

这些字段表达的是“任务状态”，而不是“模型如何推理”。

### 为什么需要 subagent

Subagent 解决的是另一个问题：

```text
长任务应该由谁执行？
```

主 Agent 可以自己执行工具，但主 Agent 同时还负责：

- 和用户沟通。
- 管理当前 session 上下文。
- 决定是否调用工具。
- 维护记忆和插件生命周期。
- 控制最终用户回复。

如果让主 Agent 直接做所有长任务，它会变得很重。

Subagent 则是一个独立的一次性 Agent：

```text
固定工具集
固定系统提示
固定最大步数
单次任务输入
返回文本结果
不维护长期对话历史
不直接写当前 session memory
不直接面对用户
```

它适合执行一个边界清楚的子任务，然后把结果交回主 Agent。

### spawn 工具在中间起什么作用

主 Agent 不是直接 new 一个 subagent，而是通过 spawn 工具发起。

spawn 工具负责：

- 判断是否允许派生任务。
- 区分同步模式和后台模式。
- 选择工具权限 profile。
- 要求任务描述包含目标、约束、上下文和输出格式。
- 在后台模式下绑定原 channel 和 chat_id。
- 返回 job_id 或同步结果。

所以 spawn 是用户对话世界和后台执行世界之间的入口。

它把主 Agent 的一句“这个任务交给子任务做”变成可管理的后台任务。

### 同步 spawn 和后台 spawn 的区别

项目里 spawn 有两种模式。

第一种是同步模式。

```text
主会话等待 subagent 完成
结果作为工具结果直接返回给主 Agent
适合预计较短、需要马上回答用户的任务
```

同步模式会使用更短的执行预算。

第二种是后台模式。

```text
主会话立即返回
subagent 在后台运行
完成后通过内部事件回灌原会话
适合预计较长、可以独立完成的任务
```

后台模式会登记 running job，用户可以查看或取消。

这个设计让主 Agent 可以根据任务规模选择：

```text
短任务：同步等待
长任务：后台执行
```

### background job 如何回到主会话

后台任务完成后，不是直接把原始结果发给用户。

系统会把完成结果包装成内部工作项，再投回 MessageBus。

这个内部工作项包含：

```text
job_id
label
task
status
exit_reason
result
retry_count
profile
```

主 Agent 收到后，会把它当成“后台任务完成事件”处理，再由主模型生成用户可见回复。

这样做有两个好处。

第一，避免把 subagent 原始输出直接暴露给用户。

第二，主 Agent 可以根据当前会话上下文，把后台结果组织成自然回复。

也就是说：

```text
subagent 负责干活
主 Agent 负责对用户表达
```

### 主 Agent 和 subagent 的边界

主 Agent 的边界是：

- 判断用户意图。
- 决定是否需要派生任务。
- 和用户沟通任务已开始、已完成或失败。
- 接收后台结果并转换成用户可见回复。
- 控制 session、memory、插件、最终回复。

Subagent 的边界是：

- 执行一个明确任务。
- 使用被授予的固定工具集。
- 输出报告、结论或产物路径。
- 不直接和用户对话。
- 不修改主会话状态。
- 不自行创建新的后台任务。

这个边界非常重要。

如果 subagent 可以直接写 session、直接回复用户、直接改记忆，主 Agent 就失去了对用户体验和状态一致性的控制。

### 工具权限 profile 如何划分边界

项目用 profile 控制 subagent 工具权限。

主要有三类：

```text
research:
  只读调研
  可以搜索、抓网页、读文件
  禁止写文件和执行命令

scripting:
  执行型
  可以运行命令、在任务目录写文件
  禁止网络访问

general:
  调研和执行都有
  只在确实需要时使用
```

这说明 subagent 不是默认继承主 Agent 的全部工具。

它每次执行任务时，只拿到和 profile 匹配的工具集。

这是一种最小权限原则。

### task_dir 的作用

后台任务会有独立任务目录。

这个目录通常位于：

```text
workspace/subagent-runs/{job_id}
```

执行型和通用型 subagent 的写入会限制在这个任务目录。

这样可以避免：

- 子任务产物散落到项目根目录。
- 子任务误改主工作区文件。
- 多个后台任务互相覆盖文件。
- 后续无法追踪某个 job 的产物。

所以 task_dir 是子任务的文件系统边界。

### 任务状态和退出原因

Subagent 执行后会有退出原因。

例如：

```text
completed
forced_summary
tool_loop
error
cancelled
```

background job 会把退出原因归一化成状态：

```text
completed
incomplete
error
cancelled
```

这让主 Agent 可以根据结果决定：

- 直接向用户汇报。
- 告诉用户只完成了部分。
- 询问是否重试。
- 对预算耗尽或工具循环场景重试一次。

这比只返回一段字符串更可靠。

### 为什么不让主 Agent 直接做所有事

直接让主 Agent 做所有事的问题是：

```text
长任务会污染当前对话上下文
当前 turn 可能长时间无响应
失败后难以恢复
无法取消
无法列出运行中任务
无法为不同任务配置不同权限
```

Subagent + background job 则把这些问题拆开：

```text
主 Agent 保持对话控制
background job 管理生命周期
subagent 执行独立任务
task_dir 管理产物
completion event 回灌结果
```

### 和普通 shell 后台任务的区别

项目里也有 shell 后台任务。

shell 后台任务更偏：

```text
执行一个具体命令
命令完成后回传输出
```

subagent background job 更偏：

```text
执行一个开放式多步任务
可能调用多个工具
可能调研、读取、分析、写报告
最终汇总结果
```

两者都可以回灌主会话，但执行主体不同。

shell 是命令进程。

subagent 是一个受限工具集下的独立 Agent。

### 设计取舍

优点：

- 主对话不会被长任务阻塞。
- 子任务有 job_id、状态、取消和 trace。
- 工具权限按 profile 限制。
- 写入产物限定在任务目录。
- 后台结果回到原会话，由主 Agent 统一表达。
- 同步和后台两种模式兼顾短任务和长任务。

代价：

- 架构复杂度增加。
- 子任务需要写好 task，否则上下文不足。
- 后台结果回灌可能需要二次整理。
- 任务目录和 trace 需要清理策略。
- 当前后台任务主要是进程内运行，重启后的恢复能力仍需加强。

### STAR 法则思考

**Situation 情景：**

Agent 经常会遇到多步调研、文件分析、报告生成等长任务。如果都放在主对话 turn 里执行，用户等待时间长，主上下文也容易被工具结果撑爆。

**Task 任务：**

需要设计一种机制，把可独立完成的长任务从主对话中拆出去，同时保留任务状态、权限边界、取消能力和结果回灌能力。

**Action 行动：**

项目把长任务拆成三层：background job 负责任务生命周期和状态归一化；subagent 负责用固定工具集执行单个任务；spawn 工具负责让主 Agent 创建同步或后台子任务。后台模式创建 job_id 和任务目录，任务完成后通过内部事件回到原会话，再由主 Agent 生成用户可见回复。

**Result 结果：**

主 Agent 可以保持对话响应性，把复杂任务交给受限子 Agent 执行；用户可以看到任务已开始、完成、失败或取消；系统也能通过 trace 和 job_id 追踪后台任务过程。

### 面试总结

可以这样回答：

```text
这个项目里 background job 和 subagent 是分层设计。background job 管任务生命周期，包括创建、运行、完成、取消、状态、结果回灌；subagent 是具体执行引擎，用固定工具集和独立上下文完成一个单次任务。主 Agent 通过 spawn 发起任务，短任务可以同步等结果，长任务可以后台执行，完成后通过内部事件回到原会话，由主 Agent 重新组织成用户可见回复。这样主 Agent 保持对话控制，subagent 负责干活，权限和产物通过 profile 和任务目录隔离。
```

### 可以改进的地方

- 增加持久化 job store，让进程重启后能恢复或标记未完成任务。
- 给后台任务增加超时、重试和优先级调度。
- 在 Dashboard 展示 running/completed/cancelled jobs 和 spawn trace。
- 增加任务目录清理和产物归档策略。
- 让 completion event 带更结构化的产物列表，而不是只靠文本结果。

## Q63: 子任务是如何被创建、排队、执行和结束的？为什么不能让主对话流程同步等待所有长任务？

### 标准答案

这个项目里的子任务生命周期可以概括为：

```text
主 Agent 决定派生任务
  -> spawn 工具校验任务和会话上下文
  -> 创建 job_id 和任务目录
  -> 写 started trace
  -> 创建后台 asyncio task
  -> 登记 running job
  -> 主 Agent 立即回复用户
  -> 子 Agent 独立执行
  -> 归一化任务结果
  -> 通过内部事件回灌原会话
  -> 主 Agent 生成用户可见回复
  -> 写 completed / cancelled trace
  -> 清理 running job
```

这里最核心的设计点是：

```text
后台模式下，创建任务和执行任务是分离的。
```

主会话只负责发起任务和告知用户“已开始处理”，不阻塞等待整个长任务完成。

### 第一步：主 Agent 通过 spawn 发起任务

当主 Agent 认为任务适合派生时，会调用 spawn 工具。

spawn 的任务描述必须包含：

- 任务目标。
- 关键约束。
- 关键上下文。
- 期望输出格式。

这是因为 subagent 没有看过当前完整会话。

如果 task 写得太短，比如：

```text
帮我研究一下
```

subagent 很可能不知道研究范围、用户偏好、输出格式和限制条件。

所以 spawn 工具要求主 Agent 像写交接文档一样描述任务。

### 第二步：判断同步还是后台

spawn 支持两种执行模式。

同步模式：

```text
主会话等待子任务完成
子任务结果作为工具结果返回
主 Agent 继续当前 turn 并回复用户
```

适合预计较短的任务。

后台模式：

```text
主会话不等待子任务完成
系统创建后台任务
完成后再把结果带回原会话
```

适合长任务。

这个区别非常重要。

不是所有 spawn 都是后台任务。

同步 spawn 更像“把一段多步调研封装成一个工具调用”；后台 spawn 才是真正异步执行。

### 第三步：后台模式需要原会话上下文

后台模式必须知道：

```text
origin_channel
origin_chat_id
```

因为任务完成后要回到原来的会话。

如果当前工具上下文里没有 channel/chat_id，系统会拒绝创建后台任务。

这是必要的。

否则后台任务完成时不知道应该通知哪个用户、哪个渠道、哪个 session。

同步模式不需要这个要求，因为结果直接回到当前工具调用里。

### 第四步：创建 job_id 和任务目录

后台任务创建时会生成一个短 job_id。

同时会创建任务目录：

```text
workspace/subagent-runs/{job_id}
```

这个目录有几个作用：

- 存放子任务产物。
- 限制可写范围。
- 方便排查某个 job 做了什么。
- 避免不同后台任务互相覆盖文件。

对于执行型或通用型子任务，写文件只能写到这个任务目录。

这就是文件系统层面的隔离。

### 第五步：先写 started trace

创建后台 task 之前，系统会先写一条 started trace。

这条 trace 记录：

```text
job_id
label
task_dir
origin channel/chat_id
profile
retry_count
delegation decision
```

这样即使后台任务刚启动就失败，也能查到：

```text
曾经创建过这个任务
它来自哪个会话
它准备用什么 profile 执行
```

这是 observability 设计。

### 第六步：创建后台 asyncio task

真正的执行逻辑会被放进后台 task。

主 spawn 调用不会等待它完成。

它只会返回一段确认文本给主 Agent，例如：

```text
已创建后台任务，完成后会继续回复。
```

然后主 Agent 可以立即回复用户。

这一步就是“非阻塞”的关键。

### 第七步：登记 running job

后台 task 创建后，系统会把它登记到运行中任务表。

运行中任务包含：

```text
job_id
label
task
profile
origin_channel
origin_chat_id
task_dir
retry_count
started_at
status
```

这样 spawn_manage 可以：

- 列出运行中的任务。
- 按 job_id 取消任务。

没有 running job 记录，用户就无法问：

```text
现在有哪些后台任务？
帮我取消那个任务。
```

### 第八步：子 Agent 独立执行

后台 task 内部会创建 subagent，并交给统一 job runner 执行。

subagent 执行时：

- 使用固定工具集。
- 使用独立 system prompt。
- 使用独立消息上下文。
- 有最大迭代次数。
- 工具结果会截断，防止上下文爆炸。
- 旧工具结果会被清理成占位符，控制上下文长度。
- 工具循环会被 hook 拦截。
- 达到预算后会强制生成进度总结。

所以子任务不是无限运行。

它是一个有边界的执行循环。

### 第九步：归一化执行结果

subagent 结束后，系统不会只拿一段文本。

它会把结果归一化成：

```text
status
exit_reason
result_summary
started_at
finished_at
completion_mode
persistence_mode
```

例如：

```text
completed -> completed
forced_summary -> incomplete
tool_loop -> incomplete
error -> error
cancelled -> cancelled
```

这样主 Agent 能知道：

```text
这个任务是完整完成，还是只完成了一部分，还是失败了。
```

### 第十步：完成结果回灌原会话

后台任务完成后，系统会把结果包装成内部工作项，重新投递到 MessageBus。

这个内部工作项会带上原来的 channel/chat_id。

主 Agent 消费到它后，会走专门的 completion handler。

注意：

```text
后台任务原始结果不会直接写入用户可见回复。
```

系统会构造一段“后台任务回传”上下文，让主模型判断如何对用户表达。

这样主 Agent 可以：

- 汇报完成结果。
- 说明未完成部分。
- 在必要时读取产物文件。
- 对预算耗尽的任务选择是否重试。
- 避免向用户暴露 job_id、spawn、subagent 等内部概念。

### 第十一步：写 completion trace 并清理运行状态

完成回灌后，系统会写 completed trace。

如果任务被取消，会写 cancelled trace。

后台 task 结束后，会通过 done callback 清理：

```text
running task
running job
cancel announced state
```

这样运行中任务列表不会长期残留已经结束的任务。

### 取消流程怎么走

用户可以通过 spawn_manage 取消后台任务。

取消时系统会：

1. 查找 running task。
2. 如果任务存在且未完成，先向原会话发布 cancelled completion event。
3. 调用 task.cancel()。
4. 后台执行层捕获取消，写 cancelled trace。
5. 清理 running job。

取消也会回灌原会话。

这让用户不会只看到“任务消失了”，而是能收到“任务已取消”的状态。

### 为什么不能让主对话同步等待所有长任务

如果所有长任务都让主对话同步等待，会造成几个问题。

第一，用户体验差。

长任务可能几十秒甚至几分钟，用户会觉得 Agent 卡住。

第二，上下文污染。

长任务的工具结果、网页内容、文件片段会进入当前对话链路，容易撑爆上下文。

第三，主 Agent 失去调度能力。

当前 turn 被一个长任务占住，用户不能自然继续沟通，也不能管理其他任务。

第四，失败恢复差。

长任务失败时，整轮对话可能只有一个失败结果，缺少 job_id、trace、取消和回灌机制。

第五，权限边界不清。

如果主 Agent 自己执行所有工具，就很难按任务类型限制工具权限。

后台子任务可以用 profile 做最小权限。

### 那为什么还保留同步 spawn

同步 spawn 仍然有价值。

有些任务虽然多步，但预计很短，而且用户需要本轮立即得到结果。

比如：

```text
快速比较几个文件
查几个资料点后总结
读一段代码并给结论
```

这类任务如果放后台，反而让交互变慢。

所以项目保留同步模式：

```text
短任务同步
长任务后台
```

并给同步模式更短的迭代预算，避免它变成长阻塞。

### 当前实现的边界

当前设计已经有：

- job_id。
- running job 管理。
- 任务目录。
- completion event。
- cancel。
- spawn trace。
- profile 权限。
- 同步和后台两种模式。

但也有边界：

- running job 主要是内存态。
- 进程重启后，后台任务恢复能力有限。
- 没有完整持久化 job store。
- 没有优先级队列。
- 没有统一超时调度。
- 完成结果主要是文本 summary，不是结构化 artifact list。

所以它已经具备工程雏形，但还可以继续产品化。

### 设计取舍

优点：

- 长任务不会阻塞主对话。
- 每个后台任务有 job_id、trace 和任务目录。
- 用户可以查询和取消运行中任务。
- 完成后回到原会话，由主 Agent 组织回复。
- 子任务有迭代预算和强制收尾，避免无限运行。
- 同步/后台两种模式覆盖不同任务规模。

代价：

- 生命周期链路比直接同步调用复杂。
- 任务状态主要在内存中，重启恢复能力有限。
- 主 Agent 必须写好 task 交接，否则子任务质量会差。
- 完成回灌会再次调用主模型，增加成本。
- 后台任务结果和产物还不够结构化。

### STAR 法则思考

**Situation 情景：**

用户可能要求 Agent 执行长时间、多步骤任务。如果全部同步塞进当前对话，主 Agent 会长时间卡住，工具结果也会污染当前上下文。

**Task 任务：**

需要设计一套子任务生命周期，让主 Agent 能快速发起长任务、保持当前对话响应，同时让后台任务可追踪、可取消、可回灌结果。

**Action 行动：**

项目通过 spawn 创建子任务：先校验是否允许派生和是否有原会话上下文，再生成 job_id、任务目录和 started trace，随后创建后台执行 task 并登记 running job。子 Agent 在独立上下文和固定工具权限下执行，结束后把状态和结果包装成内部事件投回原会话，主 Agent 再生成用户可见回复。取消时也会发回取消事件并清理运行状态。

**Result 结果：**

长任务不再阻塞主对话；用户可以继续交流、查询任务或取消任务；任务完成后系统能回到原会话继续回复，同时保留 trace 和任务目录用于排查。

### 面试总结

可以这样回答：

```text
子任务的生命周期是：主 Agent 调用 spawn，系统判断同步还是后台；后台模式会校验原会话上下文，生成 job_id 和任务目录，写 started trace，创建后台执行任务并登记 running job，然后主会话立即回复用户。子 Agent 在独立上下文和固定工具权限下执行，完成后把状态、退出原因和结果包装成内部事件投回原会话，再由主 Agent 生成用户可见回复。结束后写 completion trace 并清理运行中状态。不能让主对话同步等待所有长任务，因为这会阻塞用户、污染上下文、难以取消和恢复，也不利于权限隔离。
```

### 可以改进的地方

- 引入持久化 job store，保存 running/completed/cancelled/error 状态。
- 给后台任务增加统一超时、优先级和并发队列。
- 对完成结果增加结构化 artifact list，例如文件路径、摘要、状态。
- 进程重启后能把未完成任务标记为 interrupted，并通知用户。
- 在 Dashboard 增加后台任务时间线，展示 started、running、cancelled、completed trace。

## Q64: 后台任务的结果如何回灌到主会话、记忆或通知系统？如何避免结果丢失或重复通知？

### 标准答案

后台任务的结果不是直接发送给用户，也不是直接塞进长期记忆，而是先作为内部完成事件回到原会话，再由主 Agent 重新组织成用户可见回复。

它的核心链路是：

```text
subagent 执行结束
  -> 生成统一后台任务结果
  -> 包装成后台任务完成事件
  -> 通过 MessageBus 投回原 channel/chat_id
  -> 主会话消费这个内部事件
  -> 主 Agent 读取原会话历史并生成用户可见回复
  -> 走正常 after-reasoning / outbound / session 持久化流程
```

也就是说，后台任务完成后回到的是“原来的会话上下文”，而不是一个孤立通知。

### 为什么不直接把 subagent 原始结果发给用户

因为 subagent 的原始结果通常是中间产物，不一定适合直接展示。

它可能包含：

- 内部任务描述。
- 文件路径。
- 工具输出片段。
- 未整理的搜索结果。
- 不完整结论。
- 需要主 Agent 再判断是否重试的状态。

所以项目选择让后台任务只负责“完成工作并上报结果”，主 Agent 负责“把结果解释给用户”。

这有几个好处：

第一，用户体验更自然。

用户看到的是一段普通回复，而不是内部执行日志。

第二，主 Agent 可以结合原会话历史。

比如用户前面说过输出格式、语言、偏好，后台任务本身不一定知道完整上下文。回到主会话后，主 Agent 可以把这些偏好重新纳入回复。

第三，可以统一处理失败和不完整结果。

如果后台任务因为迭代预算耗尽、工具循环或错误而结束，主 Agent 可以判断是直接说明进展，还是触发一次补跑。

第四，避免把大量原始结果污染 session history 和长期记忆。

原始结果只作为当前回灌 prompt 的输入，不作为用户消息原文长期保存。

### 结果如何回到原会话

后台任务创建时会记录来源：

```text
origin_channel
origin_chat_id
```

这两个字段决定任务完成后投回哪里。

完成时，系统把结果包装成一个 typed internal item，里面包含：

```text
job_id
label
task
status
exit_reason
result
retry_count
profile
channel
chat_id
```

然后通过消息总线重新进入主 Agent 的消费流程。

这个设计的关键点是：后台任务完成事件和用户消息走同一个会话路由模型，但类型不同。

普通用户消息是：

```text
InboundMessage
```

后台任务完成是：

```text
SpawnCompletionItem
```

主循环看到这是后台任务完成项后，不会当作普通用户输入处理，而是走专门的完成事件处理路径。

### 主 Agent 如何处理回灌结果

主 Agent 收到后台完成事件后，会构造一段内部回传消息，大致包含：

```text
后台任务标签
原始任务
退出原因
执行结果
处理指引
```

这里的处理指引会告诉主 Agent：

- 如果结果完整，就直接向用户汇报。
- 如果结果因为迭代预算耗尽或工具循环而不完整，可以考虑补跑。
- 如果结果为空或明显出错，就告知失败或询问是否重试。
- 如果已经重试过一次，就不要继续无限重试。

然后主 Agent 会用原会话的历史消息重新渲染 prompt，再调用模型生成最终回复。

所以用户最终看到的是主 Agent 的整理结果，而不是后台任务原始文本。

### 记忆系统如何处理

这里要区分三类内容：

```text
1. 原始后台任务结果
2. 回灌时的内部标记消息
3. 主 Agent 给用户的最终回复
```

原始后台任务结果不会直接写入 session history。

系统只会在 session history 里记录一个很短的内部标记，例如：

```text
[后台任务完成] 整理任务 (incomplete) [forced_summary]
```

这样 session history 知道“发生过一次后台任务完成”，但不会被几千字工具结果撑爆。

同时，这个伪消息带有 `skip_post_memory` 标记，表示不要把这类内部回灌事件交给 post-memory 流程提炼成长期记忆。

主 Agent 最后发给用户的回复，会按正常 assistant message 进入会话历史。

因此当前策略可以概括为：

```text
原始结果：作为当前回灌输入使用，不直接保存为对话原文
内部完成标记：可进入 session history，帮助对话连续
长期记忆：跳过内部回灌事件，避免把执行日志当成用户事实
最终回复：作为普通 assistant 回复保存
```

### 通知系统如何处理

后台任务完成后，不是由子任务自己直接调用 Telegram、QQ 或 CLI adapter。

它只把完成事件投回消息总线。

之后由主 Agent 生成 `OutboundMessage`，再由原来的 channel adapter 发送给对应用户。

这样设计能保证：

- 子任务不需要知道不同渠道怎么发消息。
- 通知一定绑定到创建任务时的原 channel/chat_id。
- 插件、after-reasoning、session 保存等主链路能力还能继续生效。
- 不同来源的会话不会串线。

取消任务也走同一套 completion event，因此用户不会只看到任务消失，而是能收到“已取消”的状态回复。

### 如何避免结果丢失

当前项目主要通过几层机制降低丢失风险。

第一，创建任务时先写 started trace。

即使任务刚创建还没结束，也能在 `memory/spawn_trace.jsonl` 里看到来源、任务目录、profile 和决策信息。

第二，任务完成后写 completion trace。

完成 trace 会记录任务状态、退出原因、完成时间、profile 和 retry_count，方便排查“任务到底有没有结束”。

第三，完成事件携带原 channel/chat_id。

这避免了后台任务完成后不知道该回到哪个会话。

第四，结果会被截断到上限。

如果 subagent 结果太长，系统会裁剪后再投递，避免超大 payload 把主会话 prompt、trace 或消息队列撑爆。

第五，取消时也会发 completion event。

取消不是静默删除，而是作为一种明确状态回灌。

### 如何避免重复通知

当前实现有一些基础防重机制，但还没有做到完整的分布式幂等。

已有机制包括：

- 每个任务有唯一 job_id。
- running task 和 running job 都按 job_id 管理。
- 后台 task 结束后会清理运行中状态。
- 取消任务时会记录已宣布取消，避免取消路径重复发两次取消通知。
- retry_count 会限制回灌后的自动重试建议，避免无限补跑。

这些机制能覆盖常见的单进程重复问题。

但如果从更严格的工程角度看，当前还缺少：

- 持久化 job 状态表。
- 完成事件的幂等消费记录。
- durable queue。
- completed job 的唯一投递约束。
- 进程重启后的恢复扫描。

所以它现在更像“单进程异步任务回灌机制”，还不是完整可靠任务系统。

### 当前实现的边界

当前设计有一个重要边界：后台任务和运行中状态主要是内存态。

如果进程重启，可能出现：

- running job 丢失。
- 内存中的 asyncio task 被中断。
- 已经完成但尚未投递的事件丢失。
- started trace 存在，但没有 completed trace。
- 用户不知道任务到底失败、取消还是被进程打断。

另外，消息总线本身也不是持久队列。

如果完成事件 publish 之后、消费之前进程崩溃，就可能丢失。

还有一个重复风险：如果未来引入恢复扫描，但没有幂等表，同一个 completed trace 可能被重复转成用户通知。

所以这个模块的下一步强化点不是“再包一层 try/except”，而是引入明确的状态机和幂等机制。

### 更好的设计方案

如果要把这个模块产品化，可以改成下面的可靠任务模型：

```text
jobs 表：
  job_id
  origin_channel
  origin_chat_id
  task
  status
  retry_count
  created_at
  started_at
  finished_at
  result_ref
  completion_event_id
  notified_at

job_events 表：
  event_id
  job_id
  event_type
  payload
  created_at
  consumed_at
```

状态流转可以设计为：

```text
created -> running -> completed -> notifying -> notified
created -> running -> failed -> notifying -> notified
created -> running -> cancelled -> notifying -> notified
running -> interrupted
```

这样可以做到：

- 进程重启后扫描 running 但没有心跳的任务，标记为 interrupted。
- 对每个 job_id 只生成一次 completion event。
- 对每个 completion_event_id 只消费一次。
- 通知失败时可以重试。
- 用户可以查询历史后台任务。
- Dashboard 可以展示完整任务时间线。

### 设计取舍

当前实现的优点：

- 链路轻量，适合单机 Agent Runtime。
- 回灌回到原会话，用户体验连续。
- 原始结果不直接污染 session 和长期记忆。
- 子任务不直接耦合渠道发送能力。
- trace 能帮助排查任务开始和结束状态。
- 取消、失败、不完整结果都能统一回灌。

当前实现的代价：

- 任务状态不够持久。
- 没有完整幂等消费。
- 进程重启恢复能力弱。
- 完成结果主要是文本，不是结构化产物。
- 通知投递没有 durable queue 保障。

所以它适合当前项目阶段，但如果要作为长期运行服务，需要继续补可靠任务系统。

### STAR 法则思考

**Situation 情景：**

用户让 Agent 执行长任务时，任务可能在后台运行很久。完成后如果直接丢给用户原始日志，会影响体验；如果没有可靠回灌，用户又可能收不到结果。

**Task 任务：**

需要设计一套后台任务结果回灌机制，让子任务完成后能回到原会话、生成自然回复，并尽量避免结果丢失、重复通知和记忆污染。

**Action 行动：**

项目让后台任务记录原始 channel 和 chat_id，完成后把状态、退出原因和结果包装成内部完成事件，通过消息总线投回原会话。主 Agent 收到后用原会话历史重新生成用户可见回复，并通过正常发送链路通知用户。系统同时写 spawn trace、截断过长结果、用取消宣布标记减少重复取消通知，并用 `skip_post_memory` 避免内部回灌事件进入长期记忆。

**Result 结果：**

后台任务可以不阻塞主对话，完成后仍然能自然接回原会话；用户收到的是整理后的回复，而不是内部执行日志；session history 保留轻量完成标记，长期记忆不会被后台原始结果污染。不过，当前方案仍需要持久化 job store、幂等消费和 durable queue 才能达到生产级可靠性。

### 面试总结

可以这样回答：

```text
后台任务完成后不会直接把原始执行结果发给用户，而是先把任务状态、退出原因和结果包装成内部完成事件，再按任务创建时记录的渠道和会话 ID 投回原会话。主 Agent 收到这个内部事件后，会结合原会话历史重新组织一段用户可见回复，再走正常的发送、插件和会话保存流程。记忆层面，系统只保存一个轻量的完成标记和最终 assistant 回复，不会把后台原始结果直接写成长期记忆。为了减少丢失和重复，系统会记录任务 trace、绑定 job_id、限制结果长度、取消时只宣布一次，并用重试次数控制补跑建议。但当前仍是单进程异步回灌机制，缺少持久化任务表、幂等消费和持久队列，这是后续产品化要补的重点。
```

### 可以改进的地方

- 增加持久化任务状态表，保存 created/running/completed/notified/interrupted。
- 为完成事件增加幂等 ID，保证同一个 job 只通知一次。
- 把 MessageBus 的内部完成事件换成 durable queue 或至少可恢复队列。
- 把长结果落成 artifact，再在完成事件里只传 artifact reference。
- Dashboard 展示每个后台任务的 started、completed、notified、failed 时间线。
- 进程重启后自动扫描未完成任务，并向用户报告 interrupted 状态。

## Q65: subagent / background job 的权限应该如何限制？为什么不能默认继承主 Agent 的全部工具权限？

### 标准答案

subagent 和 background job 的权限应该按任务类型做最小授权，而不是默认继承主 Agent 的全部工具权限。

这个项目里的做法是用 profile 区分子任务权限：

```text
research:
  只读调研
  可搜索、抓网页、读文件、列目录
  禁止写文件
  禁止执行 shell

scripting:
  执行型任务
  可运行 shell
  可读工作区
  只能写入当前任务目录
  禁止网络访问

general:
  调研 + 执行
  可搜索、读文件、写任务目录、执行 shell
  仅在明确需要两类能力时使用
```

默认 profile 是 `research`，也就是只读调研。

这个默认值很关键：大多数后台任务只是“查、读、分析、总结”，不应该天然拥有写文件、执行命令、调用外部服务的能力。

### 权限限制具体限制了什么

这个项目对子任务权限的限制不是只写在 prompt 里，而是同时体现在真实工具集合上。

第一，工具集合不同。

research 子任务构造时只给只读工具，不给写文件工具，也不给 shell 工具。

所以即使模型想写文件或执行命令，也没有对应工具可调用。

第二，写入目录受限。

scripting 和 general 虽然可以写文件，但写入工具的允许目录是当前任务目录：

```text
workspace/subagent-runs/{job_id}
```

它们不应该直接修改工作区根目录里的现有文件。

第三，shell 工作目录受限。

执行型子任务的 shell 默认工作目录也是任务目录。

这能让命令产物集中在子任务目录里，方便主 Agent 后续检查和引用。

第四，网络访问可以按 profile 关闭。

scripting profile 允许执行命令，但禁止网络访问。

这可以避免一个“本来只是本地脚本处理”的任务突然去下载依赖、访问外部服务或泄露上下文。

第五，提示词继续强化行为边界。

每个 profile 都有自己的子 Agent 系统提示词，明确说明不能做什么、产物放哪里、最终怎么汇报。

这里要注意：prompt 约束是软约束，工具集合和路径限制是硬边界。

两者配合才比较可靠。

### 为什么不能默认继承主 Agent 全部工具

原因很直接：后台任务是异步、独立、长时间运行的，默认继承全部工具会扩大风险面。

第一，权限过大。

主 Agent 可能拥有发消息、写记忆、写文件、执行 shell、调用 MCP、触发插件等能力。

如果子 Agent 默认继承这些能力，一个后台任务就可能在用户不关注的时候执行高风险动作。

第二，边界不清。

主 Agent 的职责是理解用户意图、控制对话节奏、做最终决策。

子 Agent 的职责是完成一个有界任务。

如果子 Agent 继承全部能力，它就不再只是“任务执行者”，而可能变成另一个完整主 Agent，系统边界会失控。

第三，副作用难追踪。

后台任务可能运行很久，中间多次调用工具。

如果它可以发消息、写长期记忆、修改项目文件或调用外部服务，那么失败后很难判断哪些副作用已经发生、哪些需要补偿。

第四，容易污染上下文和记忆。

子 Agent 没有完整会话视角，也不应该直接改 session memory。

如果允许它写记忆，可能把未验证的中间结论写成长期事实。

第五，递归派生风险。

如果子 Agent 也能继续 spawn 子任务，任务树可能失控，出现并发爆炸、成本失控和结果难以回收。

项目的 general profile 提示词明确说子 Agent 没有 spawn 工具，就是为了避免这种递归派生。

第六，跨渠道副作用风险。

主 Agent 知道当前用户、渠道和会话上下文。

子 Agent 如果直接继承发送消息能力，就可能绕过主会话路由和用户确认机制，造成消息发错、重复发或在不合适的时候发。

### 为什么用 profile，而不是每次动态拼工具

profile 的价值是把常见任务类型固定成可审计的权限模板。

它比每次动态临时拼工具更容易理解、测试和面试表达。

比如：

```text
查资料、读代码、总结报告 -> research
本地生成文件、跑脚本、处理数据 -> scripting
既要联网调研又要生成产物 -> general
```

这样主 Agent 只需要选择任务类型，而不是每次都精确列出几十个工具权限。

同时，profile 可以被测试覆盖。

比如测试可以断言：

- research 没有写文件工具。
- research 没有 shell。
- scripting 的写入目录只能是 task_dir。
- scripting 的 shell 禁止网络。
- general 虽然权限更大，但仍不能写任务目录之外。

这比“模型自己判断该不该调用某工具”可靠得多。

### 为什么还保留 general profile

按最小权限原则看，general profile 风险最大。

但它仍然有价值，因为有些任务确实需要调研和执行同时存在。

例如：

```text
查一个接口文档，然后生成本地调用示例
阅读项目代码，再在任务目录生成分析报告
抓取资料，整理成结构化文件
```

如果没有 general，只能让主 Agent 先 research，再 scripting，中间要人工或主 Agent 搬运上下文，效率会下降。

所以更合理的策略不是删除 general，而是把它设置成“明确需要时才使用”的高权限 profile。

也就是说：

```text
默认 research
需要本地执行时 scripting
明确需要调研 + 执行时 general
```

### 当前权限设计的优点

这个项目当前的权限设计有几个优点。

第一，默认安全。

默认 profile 是只读调研，符合最小权限。

第二，写入隔离。

子任务产物放在独立任务目录，不直接污染工作区根目录。

第三，网络和执行分离。

scripting 能执行但不能联网，research 能调研但不能执行，减少组合风险。

第四，主 Agent 保留最终解释权。

子 Agent 不直接发消息给用户，而是把结果回传给主 Agent。

第五，工具级硬边界配合提示词软约束。

模型看到的说明和实际可调用工具是一致的，降低越权概率。

### 当前权限设计的不足

也有一些边界需要注意。

第一，profile 选择仍然由模型参数决定。

如果主 Agent 错选 general，子任务就会拿到更大的权限。

第二，缺少用户确认机制。

对于高风险 profile，当前没有看到强制用户确认或策略审批。

第三，权限粒度还比较粗。

现在主要是 research/scripting/general 三档，还不是细粒度 capability，例如“只能读某几个路径”“只能调用某个 MCP 工具”“只能写某个文件类型”。

第四，任务目录限制不能覆盖所有副作用。

shell 虽然工作目录受限，但命令本身仍可能有系统级影响，因此还需要沙箱、容器或更严格命令白名单。

第五，审计还可以更细。

spawn trace 记录任务级信息，但每个子任务内部工具调用的权限决策、拒绝原因、风险等级还可以更结构化地记录。

### 更好的设计方案

如果继续增强，可以把 profile 扩展成 capability manifest。

例如：

```text
capabilities:
  filesystem:
    read:
      - workspace/**
    write:
      - workspace/subagent-runs/{job_id}/**
  shell:
    enabled: true
    network: false
    cwd: workspace/subagent-runs/{job_id}
    denied_commands:
      - rm
      - curl
      - ssh
  network:
    web_fetch: false
    web_search: false
  memory:
    write: false
  messaging:
    send: false
  spawn:
    enabled: false
```

这样每个后台任务在创建时都有一份明确的权限清单。

主 Agent 选择 profile 后，系统可以把 profile 展开成 capability manifest，再由工具执行层统一校验。

对于高风险能力，还可以加入：

- 用户确认。
- 插件审批。
- 审计日志。
- 沙箱执行。
- 时间限制。
- 成本限制。
- 输出产物扫描。

### 设计取舍

当前方案的优点：

- 简单清晰，容易理解。
- 默认只读，风险较低。
- 写入集中到任务目录，方便回收和排查。
- 能覆盖调研型、执行型、混合型三类常见任务。
- profile 可以直接写进工具说明和测试用例，面试表达也清楚。

当前方案的代价：

- profile 粒度较粗。
- 高权限 profile 仍依赖主 Agent 正确选择。
- 缺少强制审批和持久化权限审计。
- shell 仍然是高风险能力，需要更强沙箱。
- 对 MCP、外部 API、消息发送这类能力还需要更细的隔离策略。

所以面试中可以说：这个项目已经有“最小权限 profile + 任务目录隔离”的雏形，但如果要生产化，需要进一步演进成 capability-based security。

### STAR 法则思考

**Situation 情景：**

后台子任务可能长时间运行，并且不在用户实时关注下。如果它默认拥有主 Agent 的全部工具，就可能在异步状态下执行写文件、发消息、联网、写记忆等高风险操作。

**Task 任务：**

需要给子 Agent 设计权限边界，让它只拿到完成当前任务所需的工具，同时保证任务产物可追踪、副作用可控制、失败后可审计。

**Action 行动：**

项目把子任务权限拆成 research、scripting、general 三类 profile。默认使用只读调研权限；执行型任务只能在任务目录写入并可关闭网络；混合型权限仅在明确需要时使用。子 Agent 不直接向用户发消息，也不直接写长期记忆，结果必须回传主 Agent，由主会话完成最终回复。

**Result 结果：**

后台任务可以独立完成调研或执行工作，但不会默认获得主 Agent 的全部能力。任务产物集中在独立目录，回传和通知仍由主链路控制，降低了越权、误写、误发和记忆污染风险。当前方案已经适合项目学习和原型使用，但生产化还需要更细粒度的 capability manifest、审批和审计。

### 面试总结

可以这样回答：

```text
这个项目没有让子 Agent 默认继承主 Agent 的所有工具，而是按任务类型分配权限。默认是只读调研，只能搜索、抓网页和读文件；执行型任务可以运行命令和写文件，但写入限制在独立任务目录，并且可以禁止网络；混合型权限只在明确需要时使用。这样做是为了遵守最小权限原则，因为后台任务是异步运行的，如果它能直接发消息、写记忆、修改项目文件或继续派生任务，副作用会很难追踪。当前设计的优点是边界清楚、任务产物集中、主 Agent 保留最终回复权；不足是权限粒度还比较粗，高风险 profile 缺少强制审批。更好的方向是把 profile 演进成 capability 权限清单，并在工具执行层统一校验和审计。
```

### 可以改进的地方

- 把 research/scripting/general 扩展成结构化 capability manifest。
- 对 general profile 或 shell 能力增加用户确认或策略审批。
- 给每个后台任务保存权限快照，方便事后审计。
- 对子任务内部工具调用记录风险等级、拒绝原因和路径边界。
- 用容器或更严格沙箱执行高风险 shell。
- 对 MCP、消息发送、长期记忆写入等能力单独设定默认禁用策略。
- 在 Dashboard 中展示每个后台任务拿到了哪些权限。

## Q66: 后台任务失败、超时或被取消时，系统应该如何恢复？哪些状态需要持久化？

### 标准答案

后台任务失败、超时或被取消时，系统不能只把异常吞掉，也不能只在日志里打印错误。它应该把任务状态归一化成可理解的生命周期结果，然后回灌原会话，让主 Agent 告诉用户当前发生了什么、哪些工作已完成、是否需要重试。

这个项目当前已经有一套基础恢复逻辑：

```text
正常完成 -> completed
执行出错 -> error
预算耗尽 / 工具循环 / 强制总结 -> incomplete
用户取消 -> cancelled
```

其中 `completed / error / incomplete` 是后台任务运行器归一化出来的状态，`cancelled` 是子任务管理层在取消路径里单独处理的状态。

### 当前项目如何处理失败

后台子任务执行时，如果底层子 Agent 抛异常，后台任务运行器会捕获异常，并把结果归一化为：

```text
status = error
exit_reason = error
result_summary = 后台任务执行失败信息
```

然后子任务管理层会把这个结果包装成完成事件，投回原来的 channel/chat_id。

主 Agent 收到后，不会直接把异常日志原样发给用户，而是根据回灌指引决定：

- 告诉用户任务失败。
- 说明已经完成和未完成的部分。
- 必要时询问用户是否重试。
- 如果系统判断还可补救，也可以按限制触发一次补跑。

所以失败恢复的第一层不是“自动重跑”，而是“把失败变成可解释状态，并回到原会话”。

### 当前项目如何处理不完整任务

不完整任务主要来自几类情况：

```text
1. 子 Agent 达到最大迭代预算
2. 工具循环保护触发
3. 强制收尾总结
4. 强制收尾总结失败后的 fallback
```

这些情况不一定是硬错误。

比如子 Agent 已经查到了大部分资料，但还没整理完整；或者它已经生成了部分文件，但最后一步没跑完。

项目会让子 Agent 尽量生成一个收尾总结，说明：

- 已完成什么。
- 当前未完成什么。
- 产出文件路径是什么。
- 下一步应该怎么继续。

然后后台任务运行器会把这些退出原因统一归为：

```text
status = incomplete
```

主 Agent 收到 incomplete 后，可以判断是直接汇报当前进展，还是补跑一次。

这里的关键设计是：不完整不等于失败。

很多长任务的中间结果仍然有价值，应该回传给用户，而不是丢弃。

### 当前项目如何处理取消

取消由后台任务管理层处理。

当用户要求取消某个 job_id 时，系统会：

```text
1. 查找运行中的任务
2. 如果任务存在，先发布 cancelled 完成事件
3. 调用 task.cancel()
4. 后台协程捕获取消状态
5. 写 cancelled trace
6. 清理 running task / running job
```

取消不是静默停止，而是显式回灌一个：

```text
status = cancelled
exit_reason = cancelled
result = 后台任务已按请求取消
```

这样用户能看到任务已经被取消，而不是后台任务突然消失。

项目里还用“已宣布取消”的集合避免取消路径重复发两次取消通知。

### 当前项目如何处理超时

这里要区分“子 Agent 步骤预算耗尽”和“真正的 wall-clock timeout”。

当前子任务有最大迭代预算：

```text
后台模式：较长预算
同步模式：较短预算
```

当步骤预算耗尽时，子 Agent 会进入强制总结，把当前进度整理出来，并把退出原因标记成强制收尾或 fallback。

这属于“预算耗尽恢复”，不是严格意义上的时间超时。

目前从后台子任务主链路看，还没有完整的 wall-clock timeout 状态机，例如：

```text
running 超过 10 分钟 -> timeout -> 取消执行 -> 写 timeout 状态 -> 通知用户
```

所以如果面试官问“这个项目是否有完整超时恢复”，应该直接回答：

```text
当前已有迭代预算和强制收尾机制，但后台任务级 wall-clock timeout、心跳和重启恢复还不完整。
```

这个判断很重要，不能把 max_iterations 误说成完整超时系统。

### 哪些状态需要持久化

如果要把后台任务做成可靠系统，至少要持久化这些状态。

第一，任务基础信息。

```text
job_id
job_kind
label
task
profile
origin_channel
origin_chat_id
task_dir
retry_count
created_at
```

这些字段用于知道任务是什么、从哪里来、完成后回到哪里。

第二，生命周期状态。

```text
created
running
completed
incomplete
error
cancel_requested
cancelled
timeout
interrupted
notifying
notified
```

其中 `interrupted` 很关键。

如果进程重启，原来的内存任务已经没了，但持久化状态里还显示 running，就应该把它恢复成 interrupted，而不是假装任务还在跑。

第三，执行结果和退出原因。

```text
exit_reason
result_summary
result_ref
artifact_paths
error_message
```

长结果不一定适合直接存在任务表里，可以保存为文件或 artifact，再在表里存引用。

第四，通知状态。

```text
completion_event_id
published_at
consumed_at
notified_at
notify_attempts
last_notify_error
```

这些字段用于防止“任务已经完成但没通知用户”或“重复通知用户”。

第五，运行时治理信息。

```text
max_iterations
iterations_used
tools_called
permission_profile
capability_snapshot
started_at
finished_at
heartbeat_at
```

这些字段用于排查任务为什么卡住、用了哪些能力、是否越权、是否应该被恢复扫描处理。

### 进程重启后应该如何恢复

生产级恢复流程可以设计成：

```text
服务启动
  -> 扫描 jobs 表中 status=running 的任务
  -> 检查 heartbeat_at 和进程实例
  -> 标记为 interrupted 或 retry_pending
  -> 如果已有 result_ref 但未通知，重新投递 completion event
  -> 如果未完成且可重试，按策略重新入队
  -> 如果不可重试，通知用户任务被中断
```

这个流程里最重要的是不要盲目重跑。

因为后台任务可能已经产生了副作用，例如写了文件、调用了外部服务、消耗了额度。

所以恢复时要先判断：

- 任务是否幂等。
- 是否已有产物。
- 是否已经通知过用户。
- 是否需要用户确认才能重试。
- 是否已经达到重试上限。

### 失败后应该如何重试

当前项目的回灌指引里已经有一个简单规则：

```text
首次 incomplete/error 可以考虑补跑
retry_count >= 1 后不再继续自动重试
```

这个策略很保守，是合理的。

因为 Agent 任务失败的原因经常不是偶发异常，而是任务描述不清、工具权限不够、上下文不足或模型陷入循环。

盲目无限重试只会浪费成本。

更好的重试策略应该区分原因：

```text
网络抖动 -> 可以自动重试
模型超时 -> 可以短延迟重试
工具权限不足 -> 不重试，要求改权限或改任务
任务描述不清 -> 回到用户确认
工具循环 -> 重写 task 后最多补跑一次
产生副作用后失败 -> 不自动重试，先审计产物
```

### 为什么恢复不能只靠日志

日志适合排查问题，但不适合驱动恢复。

原因是：

- 日志不是结构化任务状态。
- 日志不能保证幂等。
- 日志不能表达是否已经通知用户。
- 日志不能可靠保存任务产物引用。
- 日志不适合让 Dashboard 查询运行中任务。

所以恢复需要持久化状态表，日志和 trace 只是辅助诊断。

当前项目的 `spawn_trace.jsonl` 已经能帮助排查任务开始、完成和取消，但它还不是完整 job store。

### 当前设计的优点和边界

当前已有优点：

- 子 Agent 有迭代预算，避免无限运行。
- 预算耗尽后会尽量强制总结，而不是直接丢失进度。
- 失败会被归一化成 error 状态。
- 不完整会被归一化成 incomplete 状态。
- 取消会明确回灌 cancelled 状态。
- started/completed/cancelled trace 能帮助排查任务生命周期。
- 结果回灌会回到原会话，而不是只写日志。

当前边界：

- running job 主要是内存态。
- 没有持久化 job store。
- 没有 wall-clock timeout 状态。
- 没有 heartbeat。
- 没有 durable queue。
- 没有完成事件幂等消费表。
- 进程重启后不能自动恢复或通知 interrupted。

所以它已经有“失败可解释”的能力，但还没有完整“失败可恢复”的能力。

### 更好的设计方案

更完整的后台任务状态机可以是：

```text
created
  -> running
  -> completed
  -> notifying
  -> notified

running
  -> incomplete
  -> notifying
  -> notified

running
  -> error
  -> retry_pending
  -> running

running
  -> cancel_requested
  -> cancelled
  -> notifying
  -> notified

running
  -> timeout
  -> retry_pending / notifying

running
  -> interrupted
  -> retry_pending / notifying
```

配套机制包括：

- 持久化 jobs 表。
- 持久化 job_events 表。
- 心跳字段。
- 幂等 completion_event_id。
- 任务产物 artifact 表。
- 重试策略表。
- 通知投递状态表。
- Dashboard 任务时间线。

这样才能回答三个关键问题：

```text
任务现在在哪里？
任务是否已经产生结果？
用户是否已经收到通知？
```

### 设计取舍

当前方案的优点：

- 实现简单，符合单机原型阶段。
- 对失败、不完整和取消都有用户可见反馈。
- 子任务不会无限循环。
- 回灌链路能复用主 Agent 的表达能力。
- trace 足够支持基础排查。

当前方案的代价：

- 进程级故障会导致 running job 丢失。
- 任务完成事件可能在投递或消费过程中丢失。
- 不能可靠判断用户是否已经收到结果。
- 超时和恢复策略还不完整。
- 对有副作用任务的补偿能力不足。

所以面试中要承认边界：它现在是一个可用的后台任务机制，不是完整任务队列系统。能清楚讲出这个差异，反而体现工程判断。

### STAR 法则思考

**Situation 情景：**

后台任务可能因为模型异常、工具失败、迭代预算耗尽、用户取消或进程重启而中断。如果系统只打印日志，用户不知道任务结果，开发者也难以判断是否需要重试或补偿。

**Task 任务：**

需要让后台任务在失败、取消或不完整时仍然能回到原会话，给用户明确反馈，并为后续恢复、重试、审计和通知幂等留下状态基础。

**Action 行动：**

项目把子任务退出原因归一化成完成、不完整和错误，并在取消路径里显式发布取消结果。子 Agent 在预算耗尽或工具循环时会尝试生成进度总结，任务管理层写入 started/completed/cancelled trace，并把结果通过内部完成事件投回原会话。对于不完整结果，主 Agent 可以根据重试次数决定是否补跑一次。

**Result 结果：**

用户不会因为后台任务失败或取消而完全没有反馈；不完整任务的中间成果也能被保留下来并回传。当前机制已经能支持单进程场景下的基本恢复和解释，但要达到生产级，还需要持久化任务状态、心跳、超时、幂等通知和重启恢复。

### 面试总结

可以这样回答：

```text
这个项目对后台任务失败和取消有基础恢复机制。子任务正常完成会标记为完成；执行出错会标记为错误；预算耗尽、工具循环或强制总结会标记为不完整；用户取消会显式回灌取消状态。这样用户至少能知道任务发生了什么，而不是只在日志里留下异常。当前还没有完整的 wall-clock 超时、心跳和重启恢复，所以它更像单进程异步任务机制，不是完整任务队列系统。生产化时应该持久化任务基础信息、生命周期状态、退出原因、结果引用、通知状态、权限快照和心跳，用状态机保证任务可恢复、通知可幂等、失败可审计。
```

### 可以改进的地方

- 增加持久化 jobs 表，记录完整生命周期状态。
- 增加 heartbeat，服务重启后把遗留 running 任务标记为 interrupted。
- 增加 wall-clock timeout，和 max_iterations 区分开。
- 增加 completion_event_id 和消费记录，避免重复通知。
- 把长结果和文件产物保存为 artifact，再由任务状态引用。
- 按失败原因设计不同重试策略，而不是统一重试。
- 对有副作用的任务增加补偿和人工确认机制。
- Dashboard 展示任务状态机和每次状态迁移。

## Q67: MCP server 作为外部能力来源时，项目如何处理连接、工具发现、调用和断开？

### 标准答案

MCP server 在这个项目里是“外部能力来源”。它不直接暴露给模型，而是先由项目启动 MCP 子进程、完成协议握手、发现远端工具，再把远端工具包装成项目内部标准 Tool，注册进统一工具系统。

整体链路可以概括为：

```text
mcp_servers.json
  -> MCP registry 读取 server 配置
  -> 启动 stdio 子进程
  -> JSON-RPC initialize 握手
  -> tools/list 发现远端工具
  -> 每个远端工具包装成本地 Tool
  -> 注册进 ToolRegistry
  -> Agent 通过普通工具调用链执行
  -> wrapper 转成 tools/call 发给 MCP server
  -> 结果返回给 Agent
```

也就是说，MCP 是外部协议；项目内部仍然只认统一 Tool 抽象。

### 连接是如何处理的

当前项目使用的是 stdio 模式。

每个 MCP server 对应一个本地子进程，配置里保存启动命令、环境变量和可选工作目录。

配置文件在 workspace 下：

```text
mcp_servers.json
```

典型结构是：

```json
{
  "servers": {
    "calendar": {
      "command": ["python", "/path/to/run_server.py"],
      "env": {"GOOGLE_CLIENT_ID": "..."},
      "cwd": "/path/to/server"
    }
  }
}
```

连接时系统会：

```text
1. 合并当前进程环境变量和 server 自己的 env
2. 启动子进程
3. 建立 stdin/stdout JSON-RPC 通信
4. 后台持续读取 stderr，避免子进程 stderr 缓冲区阻塞
5. 给连接过程设置超时
```

如果没有显式 cwd，项目会尝试从启动命令里的绝对路径推断工作目录，避免 MCP 子进程直接继承 Agent 的工作目录。

这个细节很有工程意义：外部 server 不应该随便在 Agent 当前目录下运行。

### 协议握手和工具发现怎么做

连接建立后，项目按 MCP 协议发起初始化：

```text
initialize
notifications/initialized
tools/list
```

第一步，发送 initialize 请求，告诉 MCP server：

```text
协议版本
客户端能力
客户端名称和版本
```

第二步，发送 initialized 通知。

第三步，调用 tools/list 获取远端工具列表。

每个远端工具会被整理成：

```text
name
description
input_schema
```

这个对象不是最终给模型看的工具，而是后续包装成本地 Tool 的原始元信息。

### 远端工具如何进入统一工具系统

项目不会让模型直接调用 MCP 协议。

它会给每个 MCP 远端工具创建一个本地 wrapper。

工具名会带上 server 前缀：

```text
mcp_{server_name}__{tool_name}
```

这样做有两个好处。

第一，避免命名冲突。

不同 server 都可能有 `search`、`query`、`get_events` 这类通用工具名。如果不加 server 前缀，很容易覆盖内置工具或其他 MCP 工具。

第二，方便追踪来源。

看到工具名就知道它来自哪个 MCP server。

注册进工具系统时，项目会给 MCP 工具标记：

```text
source_type = mcp
source_name = server 名称
risk = external-side-effect
```

因此它们可以复用项目已有的工具搜索、工具执行、风险分级和 hook 机制。

### 工具调用是如何转发的

当 Agent 决定调用某个 MCP wrapper 时，内部流程和调用普通工具一致：

```text
Agent 选择工具
  -> ToolExecutor 执行本地 wrapper
  -> wrapper 调 MCP client
  -> client 发送 tools/call JSON-RPC 请求
  -> MCP server 返回结果
  -> client 把结果转成字符串
  -> ToolExecutor 把工具结果交回 Agent
```

远端调用实际发送的是：

```text
method = tools/call
params = {
  name: 原始 MCP 工具名,
  arguments: 模型传入的参数
}
```

如果 MCP server 返回 content list，项目会把里面的 text 拼成字符串。

如果返回 error，项目会把错误转成可读文本，而不是让异常直接炸掉主链路。

### 添加、列出、移除 MCP server 如何做

项目提供了三个管理工具：

```text
mcp_add
mcp_list
mcp_remove
```

它们本质上是让 Agent 可以动态管理 MCP server。

`mcp_add` 做的事情是：

```text
连接 server
发现工具
注册工具
保存配置到 mcp_servers.json
返回已注册工具列表
```

`mcp_list` 用来查看当前已连接 server 和工具。

`mcp_remove` 做的事情是：

```text
注销该 server 的所有工具
断开 MCP 子进程
从运行中 registry 移除 client
保存新的 mcp_servers.json
```

这样工具系统不会留下已经断开的远端工具。

### 启动和关闭生命周期

项目启动时，MCP registry 会读取 workspace 中的 `mcp_servers.json`，并在后台重连所有已配置 server。

这里是后台重连，而不是阻塞主服务启动。

这个取舍合理：MCP 是外部能力，某个 server 启动慢或失败，不应该导致整个 Agent 无法启动。

关闭时，系统会：

```text
取消后台连接任务
断开所有 MCP client
清空 server/tool 映射
关闭子进程
```

这避免 Agent 退出后留下孤儿 MCP 子进程。

### 主动链路里的 MCP 来源

除了普通工具调用，项目里 Proactive v2 还有一条 MCP sources 链路。

它通过 `proactive_sources.json` 声明哪些 MCP server 作为内容源、提醒源或上下文源。

这条链路使用常驻连接池：

```text
McpClientPool
```

它会按 server 维持连接，并用每个 server 一个锁来串行调用。

原因是 stdio MCP 通道不适合对同一个子进程并发写入多个请求，否则响应 id 和输出顺序容易复杂化。

主动链路里 MCP sources 主要做：

```text
拉取 alert/content/context
按 kind 过滤事件
给事件补 ack_server
按 server 分组 ack
调用失败时记录日志或重连
```

这说明 MCP 在项目里不只是“给聊天 Agent 加工具”，也可以作为后台信息源。

### 为什么需要 registry，而不是每次调用都启动 server

每次调用都启动 MCP server 会有几个问题。

第一，性能差。

很多 MCP server 启动时要加载配置、认证、初始化 SDK。每次调用都重启会很慢。

第二，状态丢失。

有些 server 可能维护连接池、token、缓存或游标，频繁重启会丢失这些状态。

第三，工具发现重复。

如果每次调用前都 tools/list，会增加延迟，也容易让工具 schema 不稳定。

第四，治理困难。

统一 registry 可以知道当前有哪些 server、每个 server 注册了哪些工具、关闭时要断开哪些子进程。

所以 registry 的职责是管理外部 server 生命周期，而不是只做一次性调用。

### 当前实现的优点

当前 MCP 设计有几个优点：

- MCP 工具进入统一 ToolRegistry，复用现有工具治理。
- 工具名带 server 前缀，避免命名冲突。
- server 配置持久化到 workspace，重启后可自动重连。
- 添加、列出、移除都有工具入口。
- 连接、接收和调用都有超时。
- stderr 后台读取，减少子进程阻塞风险。
- shutdown 会主动断开子进程。
- proactive sources 通过连接池复用 MCP 能力。

### 当前实现的边界

也有一些边界要直接承认。

第一，目前普通工具侧主要支持 stdio MCP。

没有看到完整的 HTTP/SSE MCP transport 抽象。

第二，MCP server 的权限粒度还比较粗。

注册时统一标记为外部副作用风险，但还没有对每个远端工具做更细的读写权限、确认策略或 allowlist。

第三，配置里可能包含敏感 env。

如果把 token 明文写进 `mcp_servers.json`，会有安全风险。更好的做法是引用 secret manager 或环境变量名。

第四，连接恢复还比较基础。

普通 registry 启动时会重连；主动连接池调用失败时会尝试重连。但还没有完整健康检查、退避重试、熔断和状态可视化。

第五，schema 信任边界需要加强。

远端 server 返回的 input schema 会被包装进工具系统。生产环境应该校验 schema 大小、字段合法性、描述注入风险和工具数量上限。

### 更好的设计方案

如果要继续产品化，可以把 MCP 接入演进成更完整的外部能力管理层。

可以增加：

```text
transport:
  stdio
  http
  sse

server state:
  configured
  connecting
  connected
  degraded
  disconnected
  disabled

tool policy:
  read-only
  write
  external-side-effect
  requires-confirmation
  disabled-by-default

health:
  last_connected_at
  last_error
  consecutive_failures
  latency_ms
```

同时，MCP server 配置可以拆成：

```text
server 基础配置
secret 引用
tool allowlist
每个工具的风险等级
是否允许在 proactive 中使用
是否允许在 subagent 中使用
```

这样 MCP 就不只是“能接上”，而是“可治理、可审计、可降级”。

### 设计取舍

当前方案的优点是实现直接、集成成本低，能快速把 MCP server 的能力接入 Agent Runtime。

它没有为 MCP 单独重做一套调用系统，而是把 MCP 工具适配成项目标准 Tool，所以后续工具搜索、工具执行、hook、风险标签都可以复用。

代价是 MCP 自身的复杂性被压到 registry 和 wrapper 里：连接健康、schema 安全、细粒度权限、secret 管理、非 stdio transport 还需要继续补。

所以面试中可以这样定位：当前 MCP 接入已经完成“协议适配和工具统一”，但还没有完全完成“外部能力治理平台”。

### STAR 法则思考

**Situation 情景：**

Agent 需要接入日历、文档、监控、内容源等外部能力。如果每个外部服务都写成项目内置工具，扩展成本高，也会让工具系统越来越耦合。

**Task 任务：**

需要设计一种外部能力接入方式，让 MCP server 能被动态连接、发现工具、进入统一工具系统，同时保证启动、调用和关闭生命周期可控。

**Action 行动：**

项目通过 MCP registry 读取 workspace 配置，启动 stdio 子进程，完成 JSON-RPC 初始化和工具发现。每个远端工具会被包装成本地标准工具，并带上 server 前缀和外部副作用风险标记后注册进统一工具系统。调用时，普通工具执行链会转发到 MCP 的 tools/call；移除或关闭时，系统会注销工具并断开子进程。主动链路还用连接池复用 MCP server 拉取事件和上下文。

**Result 结果：**

外部 MCP 能力可以像普通工具一样被 Agent 搜索和调用，同时保留 server 来源、风险标签和生命周期管理。项目已经具备可扩展的外部工具接入能力，但生产化还需要加强 transport 抽象、secret 管理、细粒度权限、健康检查和降级策略。

### 面试总结

可以这样回答：

```text
这个项目把 MCP server 当成外部能力来源处理。系统先从 workspace 配置里读取 server 启动命令，启动 stdio 子进程，完成初始化握手，然后调用工具发现接口拿到远端工具列表。每个远端工具不会直接暴露给模型，而是包装成项目内部标准工具，工具名带 server 前缀，并注册进统一工具系统。Agent 调用时走普通工具执行链，wrapper 再把调用转成 MCP 的远端工具调用。移除时会注销该 server 的工具并断开子进程，系统关闭时也会统一断开。这个设计的核心价值是把外部协议适配到统一工具治理里；当前不足是主要支持 stdio，权限、secret、健康检查和降级还可以继续加强。
```

### 可以改进的地方

- 抽象 MCP transport，支持 stdio、HTTP、SSE 等不同连接方式。
- 为每个 MCP 工具配置独立风险等级和确认策略。
- 增加工具 allowlist，避免 server 暴露的所有工具都自动可用。
- 用 secret 引用替代明文 env 保存。
- 增加 server 健康检查、退避重试、熔断和 Dashboard 状态页。
- 校验远端 schema 的大小、字段和描述，避免 schema 注入或超大 schema。
- 区分“普通对话可用”“proactive 可用”“subagent 可用”的 MCP 工具范围。

## Q68: 外部工具 schema 如何进入统一工具系统？为什么需要适配层而不是让模型直接调用外部协议？

### 标准答案

外部工具 schema 进入项目统一工具系统的路径是：

```text
MCP tools/list 返回 inputSchema
  -> McpToolInfo.input_schema
  -> McpToolWrapper.parameters
  -> Tool.to_schema()
  -> ToolRegistry.get_schemas()
  -> OpenAI function calling tools
  -> 模型看到统一工具 schema
```

也就是说，MCP 返回的是外部协议里的工具描述；项目会把它转成内部标准 Tool，再由统一工具系统输出模型能理解的 function schema。

模型最终看到的不是 MCP 原始协议，而是项目内部统一后的工具定义。

### schema 进入系统的具体过程

第一步，MCP server 返回远端工具列表。

远端工具里最关键的字段是：

```text
name
description
inputSchema
```

第二步，项目把它整理成内部工具元信息。

这里会把 MCP 的 `inputSchema` 变成项目内部的 `input_schema`。

第三步，项目创建本地 wrapper。

wrapper 会提供三个标准 Tool 属性：

```text
name
description
parameters
```

其中：

```text
name        = mcp_{server_name}__{tool_name}
description = [MCP:{server_name}] + 远端工具描述
parameters  = 远端 inputSchema
```

第四步，ToolRegistry 注册这个 wrapper。

注册时会额外记录：

```text
risk = external-side-effect
source_type = mcp
source_name = server 名称
```

第五步，当 Agent 需要工具 schema 时，ToolRegistry 调用每个工具的标准 schema 方法，把工具转成 OpenAI function calling 格式：

```json
{
  "type": "function",
  "function": {
    "name": "mcp_calendar__create_event",
    "description": "[MCP:calendar] create event",
    "parameters": {
      "type": "object",
      "properties": {}
    }
  }
}
```

这就是模型真正看到的 schema。

### 为什么需要适配层

适配层的核心价值是：把外部协议差异收敛到项目内部统一工具抽象。

如果没有适配层，让模型直接调用 MCP 协议，会带来很多问题。

第一，模型要理解底层协议。

模型不应该知道：

```text
JSON-RPC id 怎么生成
method 是 tools/call 还是 tools/list
params 如何包装
stdio 怎么通信
initialize 什么时候发
initialized 通知要不要等响应
```

这些都是系统工程问题，不应该交给模型决策。

第二，无法复用 ToolRegistry。

项目已有工具系统能做：

- 工具注册。
- 工具搜索。
- 工具可见性控制。
- 风险等级标记。
- 来源追踪。
- 统一执行。
- 统一错误处理。
- 插件 hook。

如果模型直接调用 MCP 协议，MCP 工具就绕过了这些治理能力。

第三，命名冲突无法控制。

多个 MCP server 可能都有同名工具。

适配层通过：

```text
mcp_{server}__{tool}
```

把命名空间显式化。

如果直接暴露远端工具名，模型可能不知道该调用哪个 server 的 `search` 或 `create_event`。

第四，风险等级无法统一。

MCP 工具可能会读外部数据、写远端系统、发送消息、修改日历、触发自动化。

适配层至少可以先把它们统一标记为外部副作用风险，并进入现有风险过滤体系。

第五，错误和结果格式无法统一。

MCP 返回可能是 content list、JSON、文本或 error。

适配层可以把这些结果收敛成项目 Tool 返回值，避免模型面对各种协议格式。

### 适配层承担了哪些职责

可以把适配层理解成四层职责。

第一层，协议转换。

```text
项目 Tool.execute(**kwargs)
  -> MCP tools/call
  -> MCP response
  -> 项目工具结果
```

第二层，schema 转换。

```text
MCP inputSchema
  -> Tool.parameters
  -> OpenAI function parameters
```

第三层，治理元数据补充。

```text
source_type
source_name
risk
search document
tool_search 可见性
```

第四层，命名空间隔离。

```text
远端 tool_name
  -> mcp_server__tool_name
```

这些职责都不适合交给模型。

模型只需要知道“有哪些工具、参数是什么、什么时候调用”，不应该负责“这个工具来自哪个协议、怎么发 JSON-RPC、怎么处理子进程”。

### schema 为什么不能原样全信任

当前项目基本是把 MCP 的 inputSchema 直接作为 Tool.parameters 使用。

这在原型阶段足够简单，但生产环境要更谨慎。

因为外部 server 返回的 schema 可能存在问题：

- 顶层不是 object。
- 字段类型不符合 OpenAI function schema 要求。
- schema 太大，撑爆 prompt。
- description 里带 prompt injection。
- required 字段和 properties 不匹配。
- enum 太长。
- 工具数量过多。
- 工具描述诱导模型绕过安全策略。

所以更严格的适配层应该增加 schema sanitizer。

例如：

```text
校验顶层 type 必须是 object
限制 schema 总长度
限制 description 长度
过滤不支持的 JSON Schema 关键字
校验 required 字段存在于 properties
为缺失 parameters 的工具补空 object schema
记录 schema 校验失败原因
```

当前项目已经有基础兜底：如果远端工具没有 inputSchema，会使用空 object schema。

但还没有完整 sanitizer。

### schema 进入 tool_search 的方式

MCP 工具注册进 ToolRegistry 后，不只是进入 LLM tools 列表，也会进入工具搜索索引。

工具搜索索引里会保存：

```text
name
description
risk
always_on
source_type
source_name
search_hint
```

当 tool_search 开启时，模型不是一开始看到所有工具，而是通过搜索或 select 加载需要的工具。

MCP 工具会按来源分组：

```text
mcp:
  calendar:
    - mcp_calendar__create_event
    - mcp_calendar__list_events
```

这对外部工具尤其重要。

因为 MCP 工具可能很多，如果全部塞进 prompt，会增加 token 成本，也会让模型更容易误调用。

### 为什么不能把所有外部 schema 直接塞进 prompt

直接塞所有外部 schema 有几个问题。

第一，token 成本高。

MCP server 多了以后，工具 schema 可能非常长。

第二，误调用概率高。

模型看到太多工具时，更容易选择错误工具。

第三，风险面扩大。

外部副作用工具越多，越需要按需加载和风险过滤。

第四，schema 不稳定。

外部 server 升级后 schema 可能变化，如果全量暴露，会影响每一轮 prompt 稳定性。

第五，prompt cache 变差。

工具列表频繁变化会降低 prompt cache 命中。

所以更好的策略是：

```text
基础工具常驻
外部工具进入工具目录
需要时通过 tool_search 解锁
高风险工具再加确认或审批
```

### 当前实现的优点

当前 schema 适配设计有几个优点：

- MCP 工具复用项目标准 Tool 抽象。
- schema 输出统一为 OpenAI function calling 格式。
- 工具名有 server 命名空间。
- 工具来源和风险等级能进入 ToolRegistry。
- MCP 工具能被 tool_search 搜索和按需加载。
- 远端调用细节被 wrapper 隐藏。
- 内置工具和外部工具走同一条执行链。

这让 MCP 接入成本低，同时不破坏原来的 Agent Runtime。

### 当前实现的边界

当前实现也有明显边界。

第一，schema sanitizer 不够强。

远端 inputSchema 基本直接进入工具系统。

第二，风险等级过粗。

当前 MCP 工具统一按外部副作用处理，没有按单个工具区分只读、写入、发送消息、删除资源等。

第三，没有 schema 版本管理。

server 工具 schema 变化后，系统没有记录版本差异，也没有兼容性检查。

第四，缺少工具 allowlist。

server 暴露什么工具，连接成功后就可能都注册进来。

第五，缺少 schema 安全审计。

例如 description 注入、过长 enum、嵌套过深对象还需要防护。

### 更好的设计方案

更完整的适配层可以设计成：

```text
MCP raw schema
  -> schema validation
  -> schema sanitization
  -> tool policy merge
  -> namespaced tool wrapper
  -> registry document
  -> LLM-visible function schema
```

其中 tool policy 可以来自配置：

```json
{
  "servers": {
    "calendar": {
      "command": ["python", "server.py"],
      "tools": {
        "list_events": {
          "enabled": true,
          "risk": "read-only"
        },
        "create_event": {
          "enabled": true,
          "risk": "external-side-effect",
          "requires_confirmation": true
        },
        "delete_event": {
          "enabled": false
        }
      }
    }
  }
}
```

这样适配层不只是“转格式”，而是外部能力治理入口。

### 设计取舍

当前方案的取舍是：用很薄的 wrapper 快速把 MCP 工具接入统一 Tool 系统。

优点是简单、直接、低耦合，适合当前项目阶段。

代价是对外部 schema 的信任较高，权限和安全治理还比较粗。

如果面试官问“这里有没有过度设计”，可以回答：

```text
当前没有做复杂 schema 网关，是为了先完成 MCP 到内部工具系统的闭环；但设计上已经把 MCP 工具包进统一 ToolRegistry，所以后续加 sanitizer、allowlist、风险策略和确认机制，不需要推翻主链路。
```

### STAR 法则思考

**Situation 情景：**

项目需要接入 MCP server 暴露的外部工具，但不同外部工具的 schema、命名、风险和调用协议都不属于主 Agent 的核心对话逻辑。

**Task 任务：**

需要把外部工具 schema 转成项目内部统一工具 schema，让模型能像调用普通工具一样调用 MCP 能力，同时保留命名隔离、风险治理和执行链路一致性。

**Action 行动：**

项目通过 MCP 工具 wrapper 把远端工具的名称、描述和输入 schema 转成标准 Tool 属性，并在注册时补充来源和风险元数据。之后 ToolRegistry 统一输出 OpenAI function calling schema，tool_search 负责按需发现和解锁工具，实际执行时 wrapper 再把普通工具调用转成 MCP 远端调用。

**Result 结果：**

MCP 工具能够无缝进入原有工具系统，模型不需要理解 MCP 协议，也不会绕过工具搜索、风险标签和执行治理。当前适配层已经完成统一接入，但还需要加强 schema 校验、工具 allowlist、细粒度风险和确认机制。

### 面试总结

可以这样回答：

```text
外部 MCP 工具的 schema 会先通过工具发现拿到远端的输入 schema，然后被包装成项目内部标准工具。wrapper 会生成带 server 命名空间的工具名，把远端描述和输入 schema 暴露为标准工具字段，再注册进统一工具系统。之后模型看到的是 OpenAI function calling 格式的统一工具 schema，而不是 MCP 协议本身。之所以需要适配层，是因为模型不应该处理 JSON-RPC、子进程、工具发现、命名冲突和风险治理这些工程问题。适配层可以统一命名、统一执行、统一错误处理、记录来源和风险，并让 MCP 工具复用 tool_search 和 ToolRegistry。当前不足是 schema 校验和细粒度权限还比较弱，后续应增加 sanitizer、allowlist 和按工具配置风险策略。
```

### 可以改进的地方

- 增加 MCP schema sanitizer，校验顶层类型、required、长度和嵌套深度。
- 为 MCP 工具配置 allowlist，避免所有远端工具自动进入系统。
- 给每个 MCP 工具单独配置风险等级和确认策略。
- 对 schema description 做长度限制和注入风险过滤。
- 记录 MCP 工具 schema 版本，便于发现外部 server 升级带来的变化。
- 在 Dashboard 展示每个 MCP 工具的来源、schema、风险和最近调用结果。
- 区分对话、主动链路、子 Agent 三类场景可见的外部工具范围。

## Q69: MCP 工具失败、超时或返回异常格式时，Agent Runtime 应该如何降级？

### 标准答案

MCP 工具失败时，Agent Runtime 应该把外部能力故障限制在工具调用边界内，不能让整个 Agent 主链路崩掉。

当前项目里，MCP 降级大致分成几类：

```text
连接失败：不注册该 server 的工具，启动继续
调用返回 error：转成可读文本结果交给 Agent
调用抛异常：ToolRegistry 捕获并返回“工具执行出错”
调用超时：抛 TimeoutError，连接池断开该 client
主动链路 fetch 失败：记录日志，跳过单个源
主动链路 poll 失败：收集失败源并向上抛出
ack 失败：记录日志，不阻断主流程
异常格式：尽量过滤、忽略或转成字符串
```

这个策略的核心是：外部工具失败不能污染会话状态，不能阻塞主服务启动，也不能导致其他工具和其他来源全部不可用。

### 连接失败如何降级

MCP server 连接失败主要发生在两个场景。

第一，启动时重连已有 server。

项目启动后会后台读取 `mcp_servers.json` 并连接所有已配置 server。

如果某个 server 失败，系统会记录错误，但不会阻塞整个 Agent 服务启动。

这很重要，因为 MCP 是外部能力，不应该因为一个日历 server 或 feed server 启动失败，就让 CLI、Telegram、普通对话、记忆和其他工具全部不可用。

第二，用户通过管理工具新增 MCP server。

如果连接失败，新增工具会直接返回错误文本：

```text
连接 MCP server 'xxx' 失败：...
```

这时不会保存成功配置，也不会注册该 server 的工具。

所以连接失败的降级原则是：

```text
启动期：记录失败，主服务继续
动态添加：返回错误，不注册工具
```

### 工具调用返回 error 如何降级

如果 MCP server 正常响应 JSON-RPC，但响应里包含 error 字段，项目不会把它当成 Python 异常直接抛出。

当前做法是把它转成可读文本：

```text
MCP error (server/tool): message
```

然后作为工具结果返回给 Agent。

这有一个好处：模型还能看到远端工具失败的原因，并尝试换一种方式回答用户。

比如：

```text
远端日历服务返回权限不足
远端文档服务说资源不存在
远端搜索服务说参数非法
```

这些错误对 Agent 有信息价值，不一定要直接中断整轮对话。

### 工具调用抛异常如何降级

如果 wrapper 执行时抛异常，比如子进程断开、stdout 关闭、JSON-RPC 等待超时，最终会回到统一工具执行层。

ToolRegistry 的执行入口会捕获异常，并返回：

```text
工具执行出错: ...
```

这能保证普通对话链路不会因为某个 MCP 工具异常而崩掉。

模型下一轮可以基于这个工具结果做降级回答，例如：

- 告诉用户外部服务暂时不可用。
- 换用其他工具。
- 请求用户稍后重试。
- 不把失败结果写成确定事实。

### 超时如何降级

MCP client 在接收响应时有超时控制。

如果某个阶段等待太久，会抛出 TimeoutError，并且错误信息里会带上诊断信息：

```text
阶段名
expected_id
command
cwd
recent_stdout
recent_stderr
```

这些信息对排查很有价值。

比如 MCP server 实际已经启动，但一直没有按 JSON-RPC 返回 initialize；或者 server 在 stderr 打印了“认证失败”。

在 proactive 的常驻连接池里，超时会被特殊处理：

```text
1. 移除当前 client
2. 尝试 disconnect
3. 不立即重试同一次调用
4. 把 TimeoutError 抛给上层
```

为什么超时不立刻重试？

因为 stdio 子进程在超时后可能已经处于半坏状态，继续复用同一个连接风险更高。先断开，下一轮再重连更稳。

### 返回异常格式如何降级

异常格式主要有几种。

第一，stdout 输出非 JSON。

当前 client 会跳过非 JSON 行，只记录 debug 日志。

这适合处理某些 MCP server 启动时误把日志打印到 stdout 的情况。

第二，收到 JSON-RPC notification。

有 method 但没有 id 的消息会被识别为通知并跳过，不会当成目标响应。

第三，收到非当前 expected_id 的响应。

当前 client 会跳过 id 不匹配的消息，继续等目标 id。

第四，tools/list 返回的工具缺少 inputSchema。

项目会使用空 object schema 兜底：

```json
{"type": "object", "properties": {}}
```

第五，proactive sources 返回格式异常。

主动链路对返回值有过滤：

- alert/content 期望 list[dict]，否则返回空列表。
- context 允许 dict 或 list[dict]，其他类型忽略。
- event 的 kind 不匹配会被过滤。

这类降级是“忽略异常项”，而不是让整个 tick 崩掉。

### Proactive 链路如何降级

Proactive 的 MCP sources 和普通对话工具不同，因为它是后台 tick 拉取外部内容。

当前项目有几种不同策略。

第一，拉取 alert/content/context 时，单个源失败只记录 warning，不阻断其他源。

也就是说：

```text
feed A 失败，不影响 feed B 和 context C
```

第二，poll content feeds 时，如果某些内容源失败，会收集失败 server，并在最后抛 RuntimeError。

这是为了让上层知道“本轮内容源刷新不完整”。

第三，ack 失败只记录日志。

ACK 是处理反馈，如果 ack 失败，不应该阻断主流程；否则可能因为远端 ack 服务异常导致用户消息发送失败。

但 ack 失败也有风险：同一内容可能下次继续出现。

所以更好的策略是记录 pending ack，后续补偿重试。

### 为什么不同场景降级策略不同

不能所有 MCP 失败都用同一种处理方式。

对普通对话来说：

```text
工具失败 -> 返回工具错误 -> Agent 给用户解释或换工具
```

对主动内容拉取来说：

```text
单个源失败 -> 跳过该源 -> 保留其他源结果
```

对内容刷新 poll 来说：

```text
刷新失败 -> 上抛，让 scheduler/日志知道本轮不完整
```

对 ack 来说：

```text
ack 失败 -> 不阻塞用户回复，但要记录风险
```

背后的原则是：越靠近用户实时交互，越要避免外部故障打断主链路；越靠近后台数据一致性，越要保留失败信号，方便后续重试和排查。

### 当前实现的优点

当前 MCP 降级设计有几个优点：

- 连接失败不会阻塞 Agent 启动。
- 动态添加失败会直接反馈，不会注册半成功工具。
- JSON-RPC error 会转成可读文本。
- 工具异常会被统一工具执行层捕获。
- 接收超时带有最近 stdout/stderr，方便排查。
- 非 JSON stdout 和 notification 会被跳过。
- proactive fetch 单源失败不会拖垮其他源。
- proactive pool 对普通异常会断开并重连一次。
- timeout 后会移除坏连接，避免继续复用半坏 client。

### 当前实现的边界

也要明确当前不足。

第一，普通 MCP registry 没有完整健康状态。

工具注册后，如果 server 后续死掉，工具仍然可能留在 ToolRegistry 中，直到调用时报错。

第二，缺少熔断。

同一个 MCP server 连续失败时，当前没有自动进入 disabled/degraded 状态。

第三，缺少退避重试。

启动重连失败只是记录错误，没有指数退避和后续周期性恢复。

第四，ack 失败没有持久化补偿。

ack 失败只记录日志，可能导致内容重复出现。

第五，异常格式校验仍然有限。

tools/list 如果返回工具缺少 name，当前构造时可能抛异常；schema 不合法也可能后续影响工具 schema 输出。

第六，缺少用户级降级策略。

例如 MCP calendar 不可用时，系统可以告诉用户“我暂时无法访问日历，但可以先记录草稿”，当前还没有统一 fallback policy。

### 更好的设计方案

生产化可以增加一层 MCP health manager。

状态可以设计成：

```text
connected
degraded
disconnected
disabled
cooldown
```

每个 server 记录：

```text
last_success_at
last_failure_at
consecutive_failures
last_error
average_latency_ms
registered_tools
disabled_until
```

调用策略可以是：

```text
连续失败 N 次 -> 熔断
熔断期间 tool_search 不返回该 server 工具
冷却后尝试健康检查
健康恢复后重新注册工具
```

对于 ack，可以增加：

```text
pending_ack 表
ack_retry_count
last_ack_error
next_retry_at
```

对于 schema 异常，可以在连接阶段做：

```text
校验 tools/list 返回结构
跳过非法工具
记录非法原因
只注册合法工具
```

### 设计取舍

当前设计的取舍是：让 MCP 失败在多数情况下变成“工具级失败”，而不是“Agent 级失败”。

这对原型和单机运行很实际。

代价是外部能力治理还不够成熟，特别是健康检查、熔断、补偿重试和 schema 校验。

面试里可以这样表达：

```text
当前项目已经做到了 MCP 故障不拖垮主链路，但还没有完整做到 MCP 服务健康治理。
```

这个回答比单纯说“有 try/except”更准确。

### STAR 法则思考

**Situation 情景：**

Agent 接入 MCP 后，外部 server 可能启动失败、调用超时、返回 JSON-RPC error，或者返回不符合预期的数据格式。如果不做降级，一个外部能力故障可能拖垮主对话或主动推送链路。

**Task 任务：**

需要让 MCP 失败被限制在工具或单个来源范围内，同时保留足够诊断信息，让 Agent 能继续回答用户或让后台链路继续处理其他来源。

**Action 行动：**

项目在连接阶段设置超时并在失败时清理子进程；启动重连失败只记录错误，不阻塞主服务。调用阶段把 JSON-RPC error 转成文本结果，工具异常由统一执行层捕获。Proactive 连接池会对普通异常断开并重连一次，对超时则移除坏连接并抛给上层；拉取单个来源失败时跳过该源，ack 失败只记录日志。

**Result 结果：**

MCP 故障不会直接拖垮 Agent Runtime；用户对话可以继续，主动链路也能尽量保留其他来源结果。当前方案具备基础降级能力，但生产级还需要健康状态、熔断、退避重试、pending ack 和 schema 校验。

### 面试总结

可以这样回答：

```text
MCP 工具失败时，这个项目的基本策略是把故障限制在工具边界内。连接失败不会阻塞主服务启动，动态添加失败会返回错误且不注册工具；远端返回 JSON-RPC error 时会转成可读工具结果；调用抛异常时由统一工具执行层捕获并返回工具执行错误；超时时会带上阶段、命令和最近输出方便排查。主动链路里，单个 MCP 来源拉取失败会跳过，不影响其他来源；ack 失败只记录日志，不阻断用户回复。当前已经做到 MCP 故障不拖垮主链路，但还缺少完整健康检查、熔断、退避重试、ack 补偿和 schema 校验。
```

### 可以改进的地方

- 增加 MCP server 健康状态和连续失败计数。
- 连续失败后进入熔断，暂时从 tool_search 结果中隐藏该 server 工具。
- 增加指数退避重连和周期性健康检查。
- 对 tools/list 返回结构做严格校验，非法工具跳过而不是整服失败。
- 对 ack 失败写 pending ack，后续补偿重试。
- 在 Dashboard 展示 server 状态、最近错误、延迟和失败次数。
- 为常见外部能力设计用户可见 fallback，例如“日历不可用时先生成草稿”。

## Q70: 如果未来接入外部 Agent 或 peer agent，应该如何设计权限、上下文边界和结果可信度？

### 标准答案

外部 Agent / peer agent 不能当成主 Agent 的“内部函数”来信任，而应该当成一个独立、异步、可能不可信的外部执行者。

这个项目当前已经有 peer agent 雏形：配置里声明 peer agent，启动时生成委托工具；调用工具时冷启动 peer agent 子进程，通过 A2A 风格 JSON-RPC 提交任务；poller 后台轮询任务状态，完成后把系统通知注入原会话，让主 Agent 读取产物并总结给用户。

当前链路可以概括为：

```text
配置 peer agent
  -> 生成 delegate_xxx 工具
  -> 主 Agent 调用委托工具
  -> 确保 peer agent 进程健康
  -> 提交异步任务
  -> 记录 task_id + channel/chat_id
  -> poller 轮询任务状态
  -> 完成/失败/超时后注入原会话
  -> 主 Agent 汇报结果
```

这里最重要的设计原则是：外部 Agent 负责执行任务，主 Agent 保留最终解释权和用户交互权。

### 权限应该如何设计

外部 Agent 权限应该按能力、任务和来源分层，不应该默认继承主 Agent 的全部权限。

至少要区分这些能力：

```text
能否读取工作区文件
能否写入文件
能否访问网络
能否调用外部 API
能否发送消息给用户
能否写长期记忆
能否再委托其他 Agent
能否执行 shell
能否访问用户隐私数据
```

当前 peer agent 工具在项目里被注册为：

```text
risk = external-side-effect
always_on = false
```

这说明它不是默认常驻工具，而是高风险外部能力，需要按需发现和调用。

这是合理的起点。

更完整的设计应该给每个 peer agent 配一份 capability policy：

```text
agent_name: deep_research
allowed_tasks:
  - research
  - report_generation
filesystem:
  read: false
  write: artifacts_only
network: true
memory_write: false
user_messaging: false
spawn_peer_agent: false
max_runtime_minutes: 60
max_cost: 低/中/高
requires_confirmation: true
```

这样主 Agent 委托前可以先判断：这个外部 Agent 是否真的有资格执行当前任务。

### 上下文边界应该如何设计

上下文边界的原则是：只给完成任务所需的最小上下文，不把整个主会话、长期记忆和用户隐私原样交给外部 Agent。

当前 peer agent 工具提交任务时，主要传：

```text
goal
breadth
rounds
```

其中 `goal` 要求是用户原始请求，不让主 Agent 随便扩写。

同时，工具执行层会把 channel/chat_id 作为路由信息记录到 poller，但这些信息主要用于结果回灌，不应该成为外部 Agent 的业务上下文。

这种设计已经体现了一个基本边界：

```text
给外部 Agent 的是任务目标
留在主系统内的是会话路由和最终回复
```

未来更好的做法是增加 context envelope：

```text
task_goal: 用户要完成什么
constraints: 输出格式、时间范围、禁止事项
allowed_context: 精选摘要或引用
forbidden_context: 不允许外传的记忆和隐私
artifact_contract: 期望产物格式
callback_policy: 完成后只回传 artifact，不直接联系用户
```

这样外部 Agent 不需要也不应该看到完整 session history。

### 为什么不能让 peer agent 直接回复用户

外部 Agent 直接回复用户会破坏主 Agent 的控制边界。

原因包括：

第一，风格不一致。

用户和主 Agent 建立的是一个连续对话，如果外部 Agent 直接插入回复，语气、上下文和承诺可能不一致。

第二，权限绕过。

外部 Agent 如果能直接发消息，就绕过了主 Agent 的确认、插件、审计和会话保存链路。

第三，结果未校验。

外部 Agent 可能产出错误、不完整或过时内容。主 Agent 应该先检查、总结，再对用户负责。

第四，多渠道路由风险。

CLI、Telegram、QQ 的发送方式和会话隔离不同，外部 Agent 不应该直接处理这些渠道细节。

所以当前项目让 poller 把完成通知注入 MessageBus，再由主 Agent 总结回复，是更稳的方式。

### 结果可信度应该如何设计

外部 Agent 的结果不能默认当成事实。

应该至少区分三层可信度：

```text
1. 任务状态可信度：它是否真的完成了？
2. 产物可信度：产物文件是否存在、格式是否符合要求？
3. 内容可信度：结论是否有证据、引用和可复核来源？
```

当前 poller 会从 A2A 任务结果里提取 artifacts，并把产出文件路径注入原会话，让主 Agent 后续根据产物内容汇报。

这是对结果可信度的一种间接控制：不是只相信一句“我完成了”，而是要求有 artifact。

但还可以继续加强：

- 检查 artifact 路径是否在允许目录。
- 检查文件是否存在。
- 检查产物大小和格式。
- 要求报告包含引用来源。
- 对关键结论做二次核验。
- 给结果打 confidence。
- 区分事实、推断和建议。

如果 peer agent 做的是深度调研，最终报告最好带：

```text
引用来源
检索时间
方法说明
未覆盖范围
不确定性
```

这样主 Agent 才能负责任地转述。

### 当前项目已有的边界

当前 peer agent 机制已经具备一些边界。

第一，独立进程。

peer agent 通过独立子进程和 HTTP/A2A 接口运行，不直接进入主 AgentLoop。

第二，冷启动和健康检查。

调用前会检查健康，未运行则启动，并等待健康检查通过。

第三，异步任务。

提交任务后立即返回，结果由 poller 后台轮询，不阻塞主对话。

第四，原会话路由。

poller 保存 channel/chat_id，完成后把系统消息注入原会话。

第五，硬超时。

pending 任务超过一定时间会被标记为超时，注入失败通知，并终止 peer agent 进程。

第六，任务完成后回收进程。

任务完成或失败后会 terminate peer agent，避免长期残留。

这些都是好的工程边界。

### 当前项目的不足

当前 peer agent 机制也有明显不足。

第一，权限策略还比较粗。

peer agent 工具只是整体标记为外部副作用，没有细分它内部能做什么。

第二，上下文 envelope 不够结构化。

当前主要传 goal、breadth、rounds，还没有明确的隐私过滤、上下文摘要和禁止事项字段。

第三，artifact 校验不足。

poller 提取 artifact 文本或路径，但没有强校验路径、存在性、格式和引用完整性。

第四，结果可信度没有评分。

主 Agent 收到结果后，没有统一的 provenance/confidence 结构。

第五，任务状态仍是内存 pending。

进程重启后 pending peer task 可能丢失。

第六，安全隔离还不够强。

peer agent 子进程 cwd、网络、文件系统和 token 权限需要更明确的沙箱策略。

### 更好的设计方案

更完整的 peer agent 接入可以设计成四个协议。

第一，能力声明协议。

```text
agent_card:
  name
  description
  skills
  input_schema
  output_schema
  permissions_required
  max_runtime
  supported_artifacts
```

第二，任务委托协议。

```text
task:
  task_id
  goal
  constraints
  allowed_context
  redacted_fields
  output_contract
  callback_channel
  timeout
```

第三，结果回传协议。

```text
result:
  status
  artifacts
  summary
  citations
  confidence
  limitations
  errors
```

第四，治理协议。

```text
policy:
  allowed_tools
  allowed_network_domains
  filesystem_scope
  secret_scope
  audit_required
  user_confirmation_required
```

这四层合起来，才能让外部 Agent 变成可治理的协作者，而不是一个黑箱任务执行器。

### 设计取舍

当前项目的 peer agent 设计偏务实。

它先解决了：

- 如何把外部 Agent 包装成工具。
- 如何冷启动外部进程。
- 如何异步提交长任务。
- 如何把结果回到原会话。
- 如何在超时或失败时通知用户。

但它还没有完整解决：

- 外部 Agent 权限最小化。
- 上下文隐私过滤。
- artifact 和证据校验。
- 结果可信度评分。
- 任务状态持久化。
- 沙箱和 secret 管理。

面试里可以这样回答：当前项目已经有 peer agent orchestration 的骨架，但要生产化，需要补上 capability policy、context envelope、artifact verification 和 trust scoring。

### STAR 法则思考

**Situation 情景：**

Agent 应用可能需要把深度调研、长报告生成或专门领域任务委托给外部 Agent。外部 Agent 能力更强，但也带来权限扩大、上下文泄露和结果不可验证的问题。

**Task 任务：**

需要设计一套外部 Agent 接入边界，让它能执行长任务，又不能直接继承主 Agent 权限、读取全部上下文或绕过主链路直接影响用户。

**Action 行动：**

项目把 peer agent 包装成外部副作用工具，调用前先健康检查和冷启动，提交任务后只记录 task_id、原会话路由和目标，由 poller 后台轮询完成状态。完成或失败后，系统把结果作为系统通知注入原会话，由主 Agent 读取产物并组织最终回复。未来应继续增加能力策略、上下文信封、artifact 校验和结果可信度评分。

**Result 结果：**

外部 Agent 可以承担长任务，主对话不会阻塞，结果也能回到原会话。同时，主 Agent 保留最终解释权和用户沟通权。当前机制已经有编排骨架，但还需要更强权限隔离和可信度治理才能用于高风险生产场景。

### 面试总结

可以这样回答：

```text
外部 Agent 或 peer agent 不能默认当成主 Agent 的内部函数来信任，而应该当成独立外部执行者。这个项目当前会把 peer agent 包装成一个外部副作用工具，调用前做健康检查和冷启动，提交异步任务后由后台轮询任务状态，完成或失败后把系统通知注入原会话，再由主 Agent 汇报给用户。这样主 Agent 保留最终解释权，peer agent 不直接回复用户，也不直接写主会话记忆。后续更完整的设计应该给每个 peer agent 配能力策略，只传最小必要上下文，限制文件、网络、消息发送和记忆写入权限，并对产物路径、引用来源、结果置信度和失败状态做校验。
```

### 可以改进的地方

- 为 peer agent 增加 capability policy，声明文件、网络、消息、记忆和再委托权限。
- 用结构化 context envelope 替代裸 goal，加入隐私过滤和输出契约。
- 持久化 peer task 状态，支持进程重启后的恢复和通知。
- 校验 artifact 路径、存在性、格式、大小和引用完整性。
- 给结果增加 citations、confidence、limitations 和 provenance。
- 对 peer agent 子进程增加沙箱、工作目录和 secret scope。
- 在 Dashboard 展示 peer agent 任务状态、产物、失败原因和可信度检查结果。

## Q71: 这个项目应该如何测试一轮被动 Agent 对话？哪些部分适合单元测试，哪些适合集成测试？

### 标准答案

一轮被动 Agent 对话不能只测试“模型最后说了什么”，而要按链路拆开测试：

```text
InboundMessage
  -> session/context/retrieval 准备
  -> prompt render
  -> reasoner / tool loop
  -> after reasoning
  -> session 持久化
  -> lifecycle event
  -> outbound dispatch
```

测试策略应该是：核心逻辑用 fake provider 和 fake tool 做确定性测试，不依赖真实 LLM；完整链路用集成测试验证消息、session、事件和输出；少量 smoke test 验证启动配置和运行时接线。

### 为什么不能直接用真实模型测试

真实模型测试不适合作为主测试。

原因是：

- 输出不稳定。
- 成本高。
- 速度慢。
- 网络和供应商状态会影响结果。
- 工具调用选择可能随模型版本变化。
- 很难断言具体中间状态。

Agent Runtime 的测试应该优先验证工程契约，而不是验证模型“聪不聪明”。

比如我们真正要断言的是：

```text
是否正确读取 session history
是否正确注入 retrieval block
是否正确传入工具 schema
是否正确执行工具调用
是否拦截不可见工具
是否保存 user/assistant 消息
是否发布 TurnCommitted
是否按 channel/chat_id 生成 outbound
```

这些都可以用 fake provider 和 fake tool 稳定验证。

### 单元测试适合测什么

单元测试应该覆盖“纯逻辑或边界明确的模块”。

第一，Reasoner / 工具循环。

适合测试：

- 模型先返回 tool_call，再返回 final。
- 工具执行结果是否进入下一轮。
- `tools_used` 是否记录正确。
- `tool_chain` 是否记录调用、参数、结果和状态。
- 最大迭代次数是否生效。
- 模型超时如何处理。
- 工具被禁用时是否不执行。
- tool_search 是否能解锁工具。
- 不可见工具是否被拦截。

现有测试里已经大量使用 fake provider：

```text
第 1 次 provider.chat -> 返回工具调用
第 2 次 provider.chat -> 返回最终回复
```

这种方式很适合测试 ReAct 工具循环。

第二，ToolRegistry / tool_search。

适合测试：

- always_on 工具是否默认可见。
- deferred 工具是否需要 tool_search 解锁。
- select 精确加载是否生效。
- risk 过滤是否生效。
- MCP 工具是否按 source_name 分组。
- 不存在工具是否返回错误。

第三，Context / Prompt Render。

适合测试：

- session history 是否按窗口截断。
- retrieval block 是否进入 prompt。
- system prompt 和 prompt block 是否稳定。
- disabled section 是否生效。
- prompt cache 相关稳定段是否不乱变。

第四，AfterReasoning / Commit。

适合测试：

- user message 是否持久化。
- assistant reply 是否持久化。
- `omit_user_turn` 是否跳过用户消息。
- `skip_post_memory` 是否阻止后续记忆写入。
- outbound 是否按 dispatch_outbound 控制发送。
- TurnCommitted 事件是否带上工具链和统计信息。

第五，CoreRunner 路由。

适合测试：

- 普通用户消息是否走被动对话核心。
- spawn completion 是否走后台任务完成处理。
- shell completion 是否走 shell 完成处理。
- 内部事件是否不被当成普通用户消息。

### 集成测试适合测什么

集成测试应该覆盖多个模块协作的契约。

例如一轮被动对话集成测试可以构造：

```text
fake session manager
fake memory engine
fake retrieval pipeline
fake provider
fake tools
real AgentLoop / AgentCore / PassiveTurnPipeline
```

然后输入：

```text
InboundMessage(channel="cli", chat_id="1", content="hello")
```

断言：

```text
1. session key 是 cli:1
2. retrieval pipeline 收到原始用户消息
3. prompt render 使用了 retrieval block
4. provider.chat 被调用
5. 如果有 tool_call，工具被执行
6. 最终 OutboundMessage channel/chat_id 正确
7. session 里追加 user 和 assistant
8. TurnCommitted 被发布
9. metadata 里 tools_used / streamed_reply / req_id 等字段正确
10. dispatch_outbound 的开关行为正确
```

这种测试不关心模型自然语言质量，而关心 Runtime 是否按契约完成一轮 turn。

### 端到端 smoke test 适合测什么

端到端 smoke test 不应该覆盖所有细节，而是验证系统能被正确组装。

适合测试：

- 配置文件能加载。
- workspace 初始化会创建必要目录和默认文件。
- toolsets 能注册。
- MessageBus、AgentLoop、Scheduler、Dashboard 能启动和关闭。
- MCP registry、peer agent resources、plugin manager 的接线不会崩。
- shutdown 能清理 event bus、MCP、peer process 等资源。

这类测试通常不深入断言每个工具调用，而是确保应用能“起得来、连得上、关得掉”。

### 一轮被动对话的推荐测试用例

可以设计一组最小但完整的测试。

第一，纯文本无工具回复。

输入：

```text
用户：你好
模型：你好，我在
```

断言：

- 不调用工具。
- session 保存 user 和 assistant。
- outbound 内容正确。
- TurnCommitted 发布。

第二，单工具调用。

输入：

```text
用户：查一下 X
模型第 1 轮：调用工具
工具：返回结果
模型第 2 轮：总结结果
```

断言：

- 工具调用参数正确。
- 工具结果进入下一轮模型消息。
- `tools_used` 包含该工具。
- `tool_chain` 包含调用记录。

第三，工具不可见或不存在。

输入：

```text
模型尝试调用 hidden_tool
```

断言：

- hidden_tool 未执行。
- 工具结果里提示先 tool_search/select。
- 模型下一轮能继续。

第四，retrieval 注入。

构造 fake retrieval pipeline 返回：

```text
MEM_BLOCK
```

断言：

- retrieval 请求里包含用户消息和 session key。
- prompt render 或 reasoner 输入里带上 retrieval block。

第五，特殊 metadata。

测试：

```text
omit_user_turn
skip_post_memory
disabled_tools
suppress_stream_events
```

断言对应行为真的生效。

第六，内部事件。

测试后台任务完成或 shell 完成：

- 不走普通用户消息处理。
- 能回到原 channel/chat_id。
- 是否跳过 post memory。
- 是否生成正确 outbound。

### 应该避免的测试方式

有几类测试不建议作为主测试。

第一，断言完整 prompt 字符串。

prompt 会频繁演进，完整字符串断言很脆。

更好的方式是断言关键 section 是否存在、顺序是否合理、关键字段是否进入。

第二，调用真实外部服务。

真实 MCP server、真实 Telegram、真实模型都应该放到少量手动或 nightly 测试里，不适合作为默认单元测试。

第三，只断言最终回复文本。

Agent 运行时的关键价值在中间链路。只断言最终文本，很容易漏掉 session、memory、tool_chain、event bus 的回归。

第四，过度 mock 到没有真实协作。

如果把 AgentCore、Reasoner、ToolRegistry、SessionManager 全都 mock 掉，就测不到 Runtime 组合契约。

所以要分层：单元测试可以细 mock，集成测试要保留真实协作对象。

### 当前项目测试覆盖的亮点

当前项目已经有一些不错的测试实践：

- Reasoner 使用 fake provider 覆盖工具循环。
- Tool visibility 测试覆盖 tool_search、deferred tool 和 LRU。
- CoreRunner 测试覆盖普通消息、spawn completion、shell completion 路由。
- Passive turn 测试覆盖 retrieval pipeline 和 TurnCommitted。
- Commit 测试覆盖 session 持久化、outbound dispatch 和 lifecycle event。
- Runtime smoke 测试覆盖配置加载、workspace 初始化、启动和关闭。

这些测试说明项目不是只测函数，而是在测 Agent Runtime 的关键契约。

### 当前还可以补的测试

还可以继续增强几类测试。

第一，完整 passive turn golden trace。

用 fake provider 固定输出，记录一轮 turn 的关键 trace：

```text
input
retrieval block
visible tools
tool calls
final reply
session diff
events
```

第二，失败路径。

覆盖：

- provider 超时。
- tool 抛异常。
- retrieval 抛异常。
- session 保存失败。
- outbound 发送失败。

第三，插件干预。

覆盖 before_turn、prompt_render、tool_hook、after_turn 插件对一轮对话的影响。

第四，多 channel 隔离。

同样 chat_id 在 CLI 和 Telegram 下不应该共享 session。

第五，memory 写入边界。

验证 `skip_post_memory`、内部事件、撤回/纠错场景不会误写长期记忆。

### 设计取舍

测试 Agent Runtime 的难点是模型不可控，但工程链路必须可控。

所以当前最实用的策略是：

```text
模型行为用 fake provider 固定
外部工具用 fake tool 固定
核心对象尽量真实组合
边界条件用单元测试细测
启动接线用 smoke test 兜底
```

这样既能保证测试稳定，又能覆盖 Agent 系统最容易回归的部分。

### STAR 法则思考

**Situation 情景：**

Agent 对话不是简单函数调用，而是一条包含 session、prompt、模型、工具、记忆、事件和发送的长链路。如果只测最终回复，很难发现中间状态错误。

**Task 任务：**

需要建立一套稳定、低成本的测试方法，既能验证工具循环和上下文组织，又能验证完整被动对话能正确持久化、发事件和返回用户。

**Action 行动：**

项目通过 fake provider 固定模型输出，用 fake tool 固定工具行为，把 Reasoner、ToolRegistry、CoreRunner、PassiveTurnPipeline、AgentCore 分层测试。单元测试覆盖工具循环、工具可见性、prompt/context 和 commit；集成测试组合 session、retrieval、reasoner 和 event bus；smoke test 验证配置、workspace 和运行时启动关闭。

**Result 结果：**

测试可以在不依赖真实模型和外部服务的情况下稳定验证 Agent Runtime 的关键契约。这样既能快速发现工具循环、session 持久化、事件分发和内部消息路由的回归，也能支持后续重构。

### 面试总结

可以这样回答：

```text
测试一轮被动 Agent 对话时，我不会主要依赖真实模型，而是用 fake provider 固定模型每一轮输出，用 fake tool 固定工具结果。单元测试重点测推理循环、工具可见性、上下文渲染、提交阶段和内部事件路由；集成测试则用真实 AgentCore 或 AgentLoop 组合 fake session、fake memory、fake retrieval 和 fake provider，输入一条 InboundMessage，断言最终 OutboundMessage、session 追加、工具链、TurnCommitted 事件和 metadata 都正确。少量 smoke test 用来验证配置加载、workspace 初始化、工具注册和启动关闭。这样测试的是 Agent Runtime 的工程契约，而不是模型文本是否每次一样。
```

### 可以改进的地方

- 增加 passive turn golden trace，用结构化方式记录一轮对话关键状态。
- 增加 provider/tool/retrieval/session/outbound 失败路径测试。
- 增加插件对一轮对话影响的集成测试。
- 增加多 channel、多 session 隔离测试。
- 增加内部事件不误写 memory 的测试。
- 增加真实模型的少量 nightly eval，但不放进默认单元测试。

## Q72: 工具调用循环应该如何测试？如何覆盖工具错误、参数错误、循环过长和终止条件？

### 标准答案

工具调用循环测试的核心不是看模型最终回复是否漂亮，而是验证 ReAct 循环里的每一种状态都能被正确处理：

```text
模型请求工具
  -> 工具是否可见
  -> 工具参数是否可执行
  -> hook 是否改参或拒绝
  -> 工具是否成功/失败
  -> 工具结果是否回填给模型
  -> 是否继续下一轮
  -> 是否达到终止条件
  -> 是否生成最终回复或进度总结
```

测试方式应该用 fake provider 固定模型每一轮输出，用 fake tool 控制工具成功、失败、抛异常、重复调用和参数边界。

### 工具循环要覆盖哪些状态

至少要覆盖这些状态：

```text
success：工具执行成功
error：工具执行抛异常或工具层返回错误
blocked：工具被禁用或不可见
denied：hook 拒绝执行
tool_search unlock：通过 tool_search 解锁 deferred 工具
max_iterations：达到最大迭代次数
early_stop：插件或上下文压力提前收尾
tool_loop：重复工具调用被循环保护截断
final：模型不再调用工具，直接输出最终回复
```

这些状态都应该进入 `tool_chain` 或生命周期事件，不能只靠日志。

### 如何测试正常工具调用

正常路径可以用两轮 fake provider：

```text
第 1 轮：模型返回 tool_call
工具：返回 ok
第 2 轮：模型返回 final
```

断言：

- 工具实际被调用一次。
- 工具参数正确。
- `tools_used` 包含工具名。
- `tool_chain` 记录 call_id、name、arguments、result。
- provider 第二次调用的 messages 中有 tool result。
- 最终 reply 是第二轮模型输出。

这个测试验证的是最基础的 ReAct 闭环。

### 如何测试工具错误

工具错误有两类。

第一类，工具自己返回错误文本。

比如：

```text
错误：文件不存在
错误：参数不合法
MCP error(...)
```

这种情况工具调用本身没有抛异常，状态可能仍然是 success，但结果文本表示业务失败。

测试重点是：

- 错误文本是否回填给模型。
- Agent 是否还有机会换工具或解释给用户。
- 不要把错误文本当成最终事实。

第二类，工具执行抛异常。

ToolExecutor 或 ToolRegistry 应该把异常收敛成：

```text
工具执行出错: ...
```

测试重点是：

- 主循环不能崩。
- tool result 要被追加，保持消息链闭合。
- `tool_chain` 中记录 error 状态或错误结果。
- 下一轮模型仍然可以继续生成回复。

### 如何测试参数错误

参数错误可以从三层测。

第一，工具 schema 参数校验。

例如工具要求：

```text
x: integer
required: ["x"]
```

测试：

```text
缺少 x
x 类型错误
x 超过 minimum/maximum
enum 不匹配
```

这类适合测 Tool 基类或具体工具的 `validate_params`。

第二，工具自身业务校验。

很多工具会在 execute 内返回业务错误，例如：

```text
message/file/image 至少提供一个
channel 和 chat_id 为必填项
路径不存在
```

这类测试应该直接调用工具，断言错误信息可读、不会抛未处理异常。

第三，模型给错参数时的工具循环行为。

可以让 fake provider 第一轮给错参数，工具返回错误；第二轮模型修正参数，再调用成功；第三轮最终回复。

断言：

- 第一次错误结果进入 messages。
- 第二次工具参数已修正。
- 最终工具结果和 reply 正确。

这样才能验证 Agent 有机会从参数错误中恢复。

### 如何测试不可见工具和禁用工具

不可见工具是 tool_search 机制里的关键边界。

测试场景：

```text
tool_search_enabled = true
hidden_tool 已注册但不是 always_on
模型第一轮直接调用 hidden_tool
```

期望：

- hidden_tool 不执行。
- tool result 提示 `tool_search(query="select:hidden_tool")`。
- `tool_chain` 里该调用状态是 blocked。
- 模型下一轮可以继续。

禁用工具是另一类边界。

例如后台任务或 scheduler 场景禁用 `message_push`。

期望：

- schema 里不出现 disabled tool。
- 即使模型强行调用，也不执行。
- 生命周期事件记录 blocked。
- 结果提示当前不可用。

这类测试很重要，因为它验证的是安全边界，不是功能成功路径。

### 如何测试 tool_search 解锁

tool_search 测试可以固定三轮：

```text
第 1 轮：调用 tool_search("hidden")
tool_search：返回 hidden_tool
第 2 轮：模型调用 hidden_tool
hidden_tool：返回 ok
第 3 轮：模型输出 final
```

断言：

- 第一次模型调用时 tools 里只有 always_on 和 tool_search。
- tool_search 返回后 visible_names 包含 hidden_tool。
- hidden_tool 只在解锁后执行。
- `tools_used` 包含 hidden_tool。

这验证“工具目录搜索 -> 本轮解锁 -> 后续调用”的闭环。

### 如何测试循环过长

循环过长有两种情况。

第一，达到最大迭代次数。

测试方式：

```text
max_iterations = 1
第 1 轮模型调用工具
工具返回结果
下一轮达到上限
系统触发收尾总结
```

断言：

- 最终回复不是生硬的“达到最大迭代次数”模板。
- 回复应该说明已完成什么、还缺什么、下一步是什么。
- `tools_used` 和 `tool_chain` 保留已经执行的工具。

第二，重复同一工具签名导致 tool loop。

测试方式：

```text
模型连续调用 dummy(x=1)
前两次允许执行
第三次被 tool_loop_guard 拦截
随后强制总结
```

断言：

- 第三次不执行真实工具。
- 工具调用链仍然闭合，不能留下 unresolved tool_call。
- 最终回复是阶段性总结。
- subagent 场景下 last_exit_reason 应标记为 tool_loop。

这里最容易出 bug 的地方是：拦截多工具 batch 中间某个调用后，后续 skipped 工具也要补 tool result，否则 OpenAI 工具消息链会不合法。

### 如何测试 early_stop / context pressure

有些时候不是达到 max_iterations，而是上下文压力或插件要求提前收尾。

测试方式：

```text
工具返回超长结果
after_step 插件判断 context pressure 超阈值
系统不再继续工具循环
调用总结分支
```

断言：

- 第二次模型调用不再带工具 schema。
- 总结 prompt 包含收尾原因。
- 回复说明当前进度。
- `tool_chain` 保留已执行工具。

这能验证“不是所有终止都靠 max_iterations”，还有插件驱动的提前停止。

### 如何测试工具事件

工具调用不仅要产出结果，还要产出可观测事件。

应该测试：

```text
ToolCallStarted
ToolCallCompleted
```

断言：

- session_key 正确。
- channel/chat_id 正确。
- iteration 正确。
- call_id 正确。
- tool_name 正确。
- arguments 和 final_arguments 正确。
- completed status 是 success / blocked / error / denied。
- result_preview 不泄露过长内容。

这对 Dashboard、trace 和调试非常重要。

### 如何测试消息链闭合

工具循环里一个隐蔽但重要的问题是：每个 assistant tool_call 都必须有对应 tool result。

特别是在：

- 工具被拦截。
- hook 拒绝。
- tool_loop_guard 截断。
- 多工具 batch 部分跳过。
- 工具抛异常。

这些路径都要补 tool result。

测试可以写一个 strict fake provider，在每次 chat 前检查 messages：

```text
所有 assistant.tool_calls 的 call_id
都必须能在后续 tool 消息里找到
```

如果有未闭合 tool_call，就直接让测试失败。

这类测试能抓住很多工具循环的协议错误。

### 推荐测试矩阵

可以整理成一个测试矩阵：

```text
正常路径:
  tool success -> final

工具错误:
  tool returns error text
  tool raises exception
  post hook error

参数错误:
  missing required
  wrong type
  business validation failed
  model corrects args in next round

可见性:
  nonexistent tool
  deferred tool direct call
  tool_search unlock
  disabled tool

循环终止:
  max_iterations
  repeated same signature
  repeated multi-tool batch
  context pressure early stop

事件与可观测性:
  ToolCallStarted
  ToolCallCompleted
  tool_chain status
  no unresolved tool_calls
```

这个矩阵比只测“工具调用成功”完整得多。

### 当前项目已有覆盖

当前项目已经覆盖了不少关键点：

- Reasoner 正常工具循环。
- tool_search 可见性和解锁。
- disabled tool 被 blocked。
- 不可见工具返回 select 引导。
- ToolCallStarted / ToolCallCompleted 事件。
- context pressure 提前收尾。
- repeated same signature 被 tool_loop_guard 截断。
- max_iterations 触发进度总结。
- subagent tool_loop 和 max_iterations 的退出原因。
- 严格检查工具消息链闭合。

这些测试说明项目已经比较重视工具循环的工程正确性。

### 还可以补的测试

还可以补：

- ToolExecutor 中 pre hook 改参是否进入 final_arguments。
- pre hook 抛异常时是否返回 error 而不是崩溃。
- post hook 抛异常时 fail_open / fail_closed 行为是否符合预期。
- 工具返回超长结果时是否截断。
- 多模态 ToolResult 是否能正常进入消息。
- MCP 工具异常是否走统一错误路径。
- shell 自动转后台时工具循环是否能正确处理 background_task_id。

### 设计取舍

工具循环测试要足够细，因为它是 Agent 和外部世界交互的核心边界。

但测试也不能依赖真实模型。

最好的方式是把模型当成脚本化状态机：

```text
fake provider 第 N 次返回什么
fake tool 第 N 次返回什么
然后断言 Runtime 是否按规则推进
```

这样测试稳定、快，而且能覆盖真实模型很难稳定复现的错误路径。

### STAR 法则思考

**Situation 情景：**

Agent 的工具循环容易出现复杂错误，比如工具不可见、参数不对、工具抛异常、模型重复调用同一工具、达到迭代上限或消息链不闭合。

**Task 任务：**

需要设计一套测试，让工具循环的成功、失败、拦截、重试、收尾和可观测事件都能被稳定验证。

**Action 行动：**

项目通过 fake provider 固定模型每轮 tool_call，通过 fake tool 和 tool hook 控制工具结果、错误和拒绝。测试覆盖正常工具调用、tool_search 解锁、disabled tool 拦截、context pressure 收尾、max_iterations 总结、tool_loop_guard 截断，并用严格 provider 检查每个 tool_call 都有对应 tool result。

**Result 结果：**

工具循环测试能够稳定发现外部交互边界的回归，避免出现工具被越权执行、重复调用失控、异常导致主链路崩溃或工具消息链不合法的问题。

### 面试总结

可以这样回答：

```text
工具调用循环应该用 fake provider 和 fake tool 做确定性测试。fake provider 按顺序返回工具调用和最终回复，fake tool 控制成功、业务错误、抛异常和重复调用。测试要覆盖正常调用、参数错误、工具异常、不可见工具、禁用工具、tool_search 解锁、最大迭代次数、上下文压力提前收尾和重复工具调用截断。除了最终回复，还要断言 tools_used、tool_chain、ToolCallStarted/Completed 事件、final_arguments、blocked/error 状态，以及每个 tool_call 都有对应 tool result，保证消息链闭合。
```

### 可以改进的地方

- 增加 pre hook 改参和拒绝路径的专门测试。
- 增加 post hook 出错时 fail_open / fail_closed 的测试。
- 增加工具返回超长结果和多模态结果的测试。
- 增加 MCP 工具异常和超时走统一错误路径的测试。
- 增加 shell 后台任务结果如何进入工具循环的测试。
- 把工具循环测试矩阵整理成固定文档，避免新增工具治理能力时漏测。

## Q73: memory retrieval 应该如何评估？如何判断召回内容相关、排序合理、注入不过量？

### 问题

面试官可能会问：

```text
memory retrieval 是 Agent 项目里很核心的一环。你会如何评估它做得好不好？怎么判断召回内容相关、排序合理、最终注入到上下文里的内容不过量？
```

### 回答

memory retrieval 的评估不能只看“有没有召回到东西”，而要拆成几层来看：

1. **召回是否正确**

也就是用户的问题需要某条记忆时，系统是否能把它找出来。

例如用户问：

```text
我之前说过我想用这个项目投什么岗位？
```

如果长期记忆里保存过“想用该项目申请 Agent 应用工程岗位”，那 retrieval 至少应该能把这条记忆召回到候选结果里。

这一层可以看：

- `recall@k`：前 k 条候选里是否包含目标记忆。
- `hit rate`：一组测试问题中，有多少问题能召回正确记忆。
- `source_ref` 覆盖率：召回结果是否能追溯到原始消息或来源。

2. **排序是否合理**

召回到正确记忆还不够，正确内容应该排在足够靠前的位置。

如果用户问“我喜欢什么模型风格”，最相关的记忆应该排在前面，而不是被最近但无关的聊天、情绪化内容或高热度内容挤下去。

这一层可以看：

- `MRR`：第一条正确结果排得越靠前越好。
- `nDCG`：多条相关记忆时，相关性更高的是否排在更前面。
- `precision@k`：前 k 条里有多少是真正相关的。
- 排序对照实验：分别关闭 query rewrite、HyDE、关键词通道、向量通道、热度加权，观察排序变化。

这里要特别注意：项目里不是简单按 embedding 分数排序，而是可能综合语义相似度、关键词匹配、RRF 融合、热度、最近使用、情绪权重等因素。因此评估时不能只看“分数高不高”，还要看这些因素有没有把无关内容错误抬高。

3. **注入是否克制**

memory retrieval 的最终目的不是把所有候选结果都塞进 prompt，而是只把最有用的内容注入给模型。

所谓“注入不过量”，不是指越少越好，而是指：

- 注入内容和当前问题直接相关。
- 不重复注入语义相同的记忆。
- 不注入已经过期、被纠正或被覆盖的事实。
- 不把程序性记忆、偏好记忆、情景记忆混在一起造成噪声。
- 不超过上下文预算。
- 不因为历史记忆太多而压缩掉当前用户问题和系统约束。

可以评估：

- `injected_count`：最终注入了几条。
- `injected_precision`：注入内容中有多少真正有用。
- `injected_recall`：应该注入的关键记忆是否进入最终上下文。
- token 占比：记忆块占整体 prompt 的比例是否合理。
- 去重率：相似记忆是否被合并或只保留代表项。
- 过期记忆率：注入内容是否包含被 supersede 或纠正的旧事实。

4. **对最终回答是否有帮助**

retrieval 做得好，最终应该体现在回答质量上。

可以做 ablation 对照：

```text
同一批问题：
不开 memory retrieval 运行一次
开启 memory retrieval 运行一次
比较答案准确率、个性化程度、事实一致性和幻觉率
```

如果开启 retrieval 后答案更准确、更符合用户历史偏好，并且没有引入错误旧信息，说明这条链路是有效的。

5. **隔离和安全是否正确**

memory retrieval 还要评估 scope。

不同 session、不同 channel、不同用户之间的记忆不能串用。例如 Telegram 里的私人事实，不应该被 CLI 会话错误召回；同一个 chat_id 在不同 channel 下也应该按 channel/session scope 隔离。

这一层要测试：

- 同一用户不同会话是否按设计共享或隔离。
- 不同 channel 是否不会互相污染。
- 私有记忆是否不会进入不该进入的上下文。
- 工具显式 recall 和自动 retrieval 是否遵守同一套范围规则。

### 项目里的证据

从项目结构看，memory retrieval 已经有比较清晰的可评估边界：

- `agent/retrieval/protocol.py` 定义了检索请求和检索结果，里面包含用户消息、会话信息、channel、chat_id、历史上下文和 trace。
- `agent/retrieval/default_pipeline.py` 把底层 memory engine 的结果转换成 Agent 运行时可注入的 retrieval block，并记录注入数量。
- `core/memory/engine.py` 定义了 memory hit 的基础结构，包括分数、来源引用、是否注入等字段。
- `plugins/default_memory/engine.py` 负责实际调用 retriever，并根据 injection block 判断哪些结果真正进入上下文。
- `plugins/observe` 会记录 query、orig_query、命中结果、注入数量、路由决策等诊断信息。
- `plugins/recall_inspector` 能记录注入内容和显式 recall 工具调用，适合用来排查“为什么这条记忆被召回/为什么没被召回”。
- `memory2` 下有 query rewrite、HyDE、retriever、injection planner、去重、程序性记忆标记等能力，说明 retrieval 不是单一向量搜索，而是一条可拆解评估的流水线。

测试层面已经有一些基础覆盖：

- memory engine contract 测试验证结果块、hits、注入标记和 session scope。
- retrieval baseline 测试验证基础排序和热度权重。
- HyDE 测试验证增强检索失败时能降级。
- query rewriter 测试验证是否基于近期历史改写问题。
- recall memory tool 测试覆盖语义检索、grep 模式和 embedding 失败后的关键词兜底。
- observe writer 测试验证 retrieval trace 的字段记录。
- PersonaMem / LongMemEval 相关目录可以作为更系统的离线评估基础。

### 如何设计评估集

我会准备一套固定的 memory retrieval gold set，至少覆盖这些类型：

- 用户偏好：比如“我喜欢中文回答”“我偏向工程化解释”。
- 用户身份：比如“我正在学习 Agent 项目并准备求职”。
- 项目事实：比如“这个项目有哪些模块、插件、记忆策略”。
- 情景事件：比如“上次我们学习到 Q72”。
- 纠错覆盖：比如用户先说 A，后来纠正为 B，系统应该召回 B 而不是 A。
- 程序性记忆：比如“以后回答面试总结时少放函数名，多用中文职责描述”。
- 跨会话隔离：比如 CLI、Telegram、QQ 的记忆边界。
- 无关问题：系统应该少召回或不注入，避免硬塞记忆。

每个测试样本可以写成：

```text
输入问题
期望召回的 memory_id
允许召回的辅助 memory_id
不允许注入的 memory_id
期望注入数量上限
期望回答要点
```

这样就能同时评估候选召回、排序、注入和最终回答。

### 设计取舍

memory retrieval 的难点是“召回更多”和“注入更少”之间存在张力。

召回阶段可以宽一些，因为漏召回会导致模型完全拿不到相关事实；但注入阶段必须更严格，因为无关记忆进入 prompt 会污染回答，甚至比没召回更糟。

所以合理设计是：

```text
候选召回偏宽
排序融合偏稳
上下文注入偏严
最终回答可追溯
```

这也解释了为什么项目里需要 retrieval trace、recall inspector 和 observe 插件：memory retrieval 的质量不能只靠主观感觉，需要能回放、能定位、能比较。

### STAR 法则思考

**Situation 情景：**

Agent 项目需要利用历史记忆回答当前问题，但记忆数量会不断增长，里面可能有重复、过期、跨会话、弱相关甚至相互冲突的内容。

**Task 任务：**

需要建立一套评估方法，判断 memory retrieval 是否能找对内容、排好顺序、控制注入量，并最终提升回答质量。

**Action 行动：**

把评估拆成召回、排序、注入、最终回答和范围隔离五层。用固定 gold set 记录期望命中的记忆、禁止注入的记忆、注入数量上限和最终答案要点；再结合检索 trace、recall 诊断页面和离线 benchmark 做对照实验。

**Result 结果：**

这样可以把“感觉记忆好像有用”变成可度量的工程指标：能知道是没召回、排序错、注入过多、旧记忆污染，还是最终模型没有正确使用记忆，从而有针对性地优化。

### 面试总结

可以这样回答：

```text
我不会只用“有没有召回到记忆”来评估 memory retrieval，而会拆成五层：第一看候选召回是否找到了正确记忆，第二看排序是否把最相关内容放在前面，第三看最终注入是否克制，第四看它是否提升最终回答质量，第五看会话和渠道边界是否安全。指标上可以用 recall@k、precision@k、MRR、nDCG、注入数量、注入准确率、过期记忆率和开启/关闭记忆的对照实验。这个项目里检索请求、候选结果、注入标记、来源引用和诊断 trace 都已经有边界，所以适合进一步建设固定评估集和回归测试。
```

### 可以改进的地方

- 建立正式的 memory retrieval gold set，并把样本纳入 CI 或定期评估。
- 给不同记忆类型分别统计召回和注入质量，比如偏好、事实、情景、程序性记忆分开看。
- 增加开启/关闭 query rewrite、HyDE、热度权重、关键词通道的 ablation 报告。
- 在 Dashboard 中展示每轮检索的候选排序、注入原因、未注入原因和 token 占比。
- 增加过期记忆、冲突记忆、跨 session 污染的自动检测。
- 对最终回答增加“是否正确使用了记忆”的人工或半自动评分。

## Q74: Proactive v2 应该如何测试？如何模拟 feed、presence、cooldown、dedupe 和发送失败？

### 问题

面试官可能会问：

```text
Proactive v2 是主动触达链路，比普通问答更容易误推、重复推、漏推。你会如何测试它？feed、presence、cooldown、dedupe 和发送失败这些场景应该怎么模拟？
```

### 回答

Proactive v2 的测试重点不是“能不能发出一条消息”，而是要证明它在不同边界条件下能正确决定：

```text
该不该看候选内容
该不该打扰用户
该不该进入模型判断
该不该发送
发送后该怎么 ACK
失败后哪些状态不能提前落库
```

因此我会把测试拆成五层。

### 1. feed / alert 输入层测试

第一层要模拟外部内容源。

feed 和 alert 本质上都是候选事件输入，测试时不应该依赖真实 RSS、MCP server 或外部 HTTP 服务，而应该用 fake gateway 返回固定数据。

典型样本包括：

- 没有任何候选内容。
- 有一条普通内容。
- 多条内容来自不同 source。
- 同一内容换了 event_id，但 URL 一样。
- 内容缺少 URL，只能依赖 source + title。
- alert 和 feed 同时存在。
- 外部内容源返回异常、超时或脏数据。

要验证的不是模型最终说了什么，而是：

- 候选内容是否被标准化。
- `ack_server`、`event_id`、`url`、`title` 等关键字段是否保留下来。
- cited item 是否能回到原始候选内容。
- alert 和 content 的 ACK 通道是否区分。
- 内容源失败时是否不会拖垮整个 tick。

### 2. presence / 打扰控制测试

第二层测试用户当前是否适合被主动触达。

presence 需要模拟：

- 用户刚刚发过消息。
- 用户很久没有活跃。
- 刚刚发过 proactive 消息。
- 当前被动对话正在处理。
- presence 数据为空。
- 多个 session 中最近活跃时间不同。

测试时可以用 fake presence store 或 fake `last_user_at_fn`，让主动链路看到不同的用户状态。

关键断言是：

- 用户忙时不进入主动发送。
- 被动对话正在处理时不打断。
- presence gate 拦截时不应该 ACK feed，因为系统还没有真正处理这些候选内容。
- gate 失败要留下可观测记录，方便知道本轮是因为 busy、presence 还是配额被挡住。

### 3. cooldown / 配额测试

第三层测试冷却和频率控制。

主动 Agent 最大风险之一是“有内容就一直说”。因此 cooldown 要单独测。

需要模拟：

- 最近 N 小时已经发送过主动消息。
- 最近没有发送过主动消息。
- 配置里的冷却窗口变化。
- context-only 主动消息的每日上限。
- context-only 主动消息的最小间隔。
- 随机概率 gate 打开或关闭。

测试方法是让 fake state store 返回固定的发送计数、上次发送时间和随机数。

关键断言是：

- 冷却命中时直接退出，不进入模型循环。
- 冷却命中时不 ACK 候选内容。
- 冷却窗口使用配置值，而不是写死。
- context-only 的概率、每日上限、最小间隔同时生效。
- 发送成功后才记录本次 delivery。

### 4. dedupe / 重复发送测试

第四层测试去重。

Proactive v2 需要避免同一篇内容重复推送。这里不能只按 event_id 去重，因为很多内容源会变化 id。

项目里 delivery key 的思路是：

```text
优先使用稳定 URL
没有 URL 时使用来源 + 标题
再不行才退回候选 id
如果没有 cited item，则用消息文本摘要
```

测试样本应该覆盖：

- cited item 顺序不同，但 delivery key 相同。
- 同一 URL，不同 event_id，仍然判定重复。
- 没有 URL，但 source + title 相同，仍然判定重复。
- 不同内容应该生成不同 delivery key。
- 没有 cited item 时按消息文本生成 key。
- 文本过长时只使用截断后的稳定摘要。

还要测 post guard：

- delivery duplicate 命中后不发送。
- message dedupe 命中后不发送。
- dedupe 命中后，已引用内容短期 ACK，避免马上再次循环处理。
- 被丢弃内容长期 ACK，避免反复消耗判断。

### 5. 发送成功 / 发送失败测试

第五层测试真正的发送边界。

主动消息不能在“还没发出去”时就把内容标记成已成功投递，否则会造成用户没收到，但系统以为已经处理。

需要模拟：

- message push 成功。
- message push 抛异常。
- outbound adapter 返回失败。
- 发送成功但后处理记录失败。
- 发送失败后再次 tick 是否还能重新处理内容。

关键断言是：

- 发送成功后才记录 proactive session 消息。
- 发送成功后才更新 last proactive time。
- 发送成功后 cited content ACK 较长时间。
- 发送失败时不能 mark delivery。
- 发送失败时不能把 cited content 当成成功送达处理。
- discarded 内容可以按丢弃策略 ACK，因为它们本来就不该再推。
- 失败要有日志或 trace，方便后续排查。

### 项目里的证据

从代码结构看，Proactive v2 已经具备比较适合测试的边界：

- `proactive_v2/loop.py` 负责组装主动循环，把 sensor、presence、state store、message deduper、turn orchestrator 和 agent tick 接起来。
- `proactive_v2/agent_tick.py` 把单次 tick 拆成 pre-gate、工具循环、post guard、ACK 和 delivery 记录。
- `proactive_v2/presence.py` 负责记录用户最近发言和最近主动触达时间。
- `proactive_v2/state.py` 负责主动链路的状态持久化，比如 delivery、context-only、drift、tick log。
- `proactive_v2/gateway.py` 负责把 feed、alert、context 等外部输入统一成候选事件。
- `proactive_v2/judge.py` 负责消息级去重判断。
- `agent/turns/orchestrator.py` 负责 proactive 结果如何发送、如何写入 proactive session、发送失败如何处理。

现有测试也已经按这个方向拆开：

- `tests/proactive_v2/test_pregate.py` 覆盖用户忙、冷却、presence gate、context gate、配额和概率。
- `tests/proactive_v2/test_agent_loop.py` 覆盖 proactive agent tick 的工具循环、最大步数、终止动作、消息历史和 cited ids。
- `tests/proactive_v2/test_post_guard_ack.py` 覆盖 delivery key、ACK TTL、成功、丢弃、post guard 失败等路径。
- `tests/proactive_v2/test_integration.py` 验证 ProactiveLoop 会稳定路由到 AgentTick。
- `tests/test_presence.py` 覆盖 presence store 的基础读写。
- `tests/proactive_v2/test_drift.py` 覆盖 drift 相关主动行为。

### 建议的测试矩阵

可以把 Proactive v2 的测试矩阵整理成这样：

```text
输入层：
feed 空 / 单条 / 多条 / 重复 URL / 缺字段 / 异常

前置 gate：
用户忙 / 刚互动 / 冷却中 / 配额耗尽 / 概率关闭 / 全部通过

模型循环：
无工具调用 / 拉取内容 / 标记不感兴趣 / 发送消息 / skip / 超过最大步数

后置 guard：
delivery 重复 / 文本重复 / cited 内容重复 / alert 重复 / 无重复

发送结果：
发送成功 / 发送失败 / adapter 异常 / 后处理异常 / 重试后成功

状态副作用：
ACK 是否正确 / delivery 是否记录 / presence 是否更新 / session 是否写入 / trace 是否落库
```

这个矩阵的价值是：每个测试都只验证一个明确问题，不需要真实模型参与。

### 为什么要用 fake，而不是直接跑真实模型

Proactive v2 测试必须大量使用 fake provider、fake gateway、fake state store、fake ack sink 和 fake sender。

原因是：

- 真实模型输出不稳定，不适合做回归测试。
- 外部 feed 内容会变化，不适合做确定性断言。
- presence 和 cooldown 依赖时间，需要可控时钟或 fake state。
- 发送消息有真实副作用，测试里必须隔离。
- ACK 和 delivery 记录属于关键副作用，需要精确断言。

所以测试里应该让 fake LLM 按脚本返回工具调用：

```text
第 1 步：get_content_events
第 2 步：message_push
第 3 步：finish_turn(reply)
```

然后断言系统是否按预期推进，而不是断言模型自然语言是否“看起来合理”。

### STAR 法则思考

**Situation 情景：**

主动 Agent 会在用户没有提问时发起触达，一旦测试不足，就可能出现误打扰、重复推送、发送失败后状态错误、候选内容被错误 ACK 等问题。

**Task 任务：**

需要建立一套测试方法，证明 Proactive v2 在内容输入、用户状态、频率控制、去重、发送和状态副作用上都是可控的。

**Action 行动：**

把主动链路拆成 feed 输入、presence 判断、cooldown 配额、dedupe 后置保护、发送结果和状态副作用几层。用 fake gateway 模拟候选内容，用 fake state store 模拟冷却和历史发送，用 fake LLM 固定工具调用序列，用 fake sender 模拟成功或失败，再断言 ACK、delivery、presence、session 和 trace 是否正确。

**Result 结果：**

这样可以把主动触达从“模型觉得该说就说”变成可验证的工程流程，确保系统不会频繁打扰用户，不会重复发送同一内容，也不会在发送失败时错误标记状态。

### 面试总结

可以这样回答：

```text
Proactive v2 的测试重点是副作用治理。它不是普通问答链路，而是主动决定是否打扰用户，所以我要分别测试候选内容输入、用户在线状态、冷却和配额、重复推送保护、发送成功失败以及状态落库。测试里不依赖真实模型和真实 feed，而是用假的内容源、假的状态存储、假的模型工具调用序列和假的发送器，让每条路径都可重复。核心断言是：不该发时不能进入发送，该发时只发一次，发送成功后才记录投递和更新时间，发送失败不能把内容当成已处理，ACK 的时长也要符合不同结果的语义。
```

### 可以改进的地方

- 增加发送失败后下一轮重试的完整集成测试。
- 增加 feed 源异常、脏字段、超时的降级测试。
- 增加多 session、多 channel 下 proactive 状态隔离测试。
- 增加真实 state store 的数据库级测试，验证 delivery、tick log、context-only 记录能正确持久化。
- 增加 Dashboard 上 proactive trace 的快照测试，确保排查误推时有足够信息。
- 增加一套离线回放集，把历史 feed 和用户 presence 固定下来，评估误推率、漏推率和重复率。

## Q75: 插件系统应该如何测试？如何确保插件不会破坏主链路或引入不可控副作用？

### 问题

面试官可能会问：

```text
这个项目有插件系统，插件可以注册工具、监听生命周期、改写工具参数、写自己的状态。你会如何测试插件系统？怎么确保插件不会破坏 Agent 主链路，或者引入不可控副作用？
```

### 回答

插件系统的测试不能只测“插件能不能加载”，而要测它和主链路之间的边界是否可靠。

我会把插件测试拆成六层：

```text
发现与加载
上下文和配置注入
工具注册与卸载
生命周期扩展
工具 hook 治理
异常、回滚和副作用隔离
```

### 1. 发现与加载测试

第一层测试插件是否能被正确发现、导入、实例化。

需要覆盖：

- 插件目录不存在时不会报错。
- 目录里没有 `plugin.py` 时跳过。
- 插件导入失败时只记录 warning，不影响其他插件。
- 重名插件按 first-wins 处理，后续同名插件跳过。
- 插件类没有成功注册时跳过。
- `manifest.yaml` 能覆盖插件名称、版本、描述、作者。
- `initialize` 成功后才算真正加载完成。
- `terminate` 能在退出时被调用。

这一层的目标是保证插件生态是“可插拔”的：单个插件坏了，不能导致整个 Agent 启动失败。

### 2. 上下文和配置注入测试

第二层测试插件拿到的上下文是否正确。

插件不应该到处直接访问全局对象，而应该通过上下文拿到被允许的能力，比如：

- 事件总线。
- 工具注册表。
- 插件自己的目录。
- 插件自己的 KV 存储。
- 插件配置。
- workspace 路径。
- session manager。
- memory engine。

测试要覆盖：

- `_conf_schema.json` 的默认值是否注入。
- `plugin_config.json` 是否能覆盖默认值。
- 没有配置文件时 config 是否为空。
- 插件 KV 存储是否只写在插件自己的目录。
- 同一个插件重启后 KV 是否能持久化。
- 不同插件的 KV 是否互不污染。

这样可以保证插件状态有边界，不会把运行状态散落到项目根目录或其他插件目录里。

### 3. 工具注册与卸载测试

第三层测试插件工具如何进入统一工具系统。

插件工具不是模型随便发现的函数，而是要注册成标准工具，带上名称、描述、参数 schema、风险等级、是否 always-on、搜索提示和来源信息。

测试要覆盖：

- 插件工具是否被注册到工具注册表。
- 工具参数 schema 是否保留。
- 调用插件工具时是否只传入它声明接受的参数。
- 工具返回值是否被统一转成字符串或标准结果。
- 插件卸载时是否注销工具。
- 插件初始化失败时，已经注册的工具是否会被回滚。
- 不同插件注册同名工具时是否有明确处理策略。

这层要保证插件扩展的是统一工具系统，而不是绕过工具治理单独开执行入口。

### 4. 生命周期扩展测试

第四层测试插件能否在 Agent 生命周期里正确介入。

项目里插件可以参与：

- turn 开始前。
- reasoning 前。
- prompt 渲染时。
- 每一步工具循环前后。
- reasoning 后。
- turn 结束后。
- 内部事件写入，如 observe、memory trace、dashboard 统计。

测试要验证：

- 对应阶段的 handler 会被触发。
- handler 能收到正确的 session、channel、chat_id、当前内容和 trace 信息。
- handler 修改 metadata 或追加信息后，后续阶段能看到。
- phase module 的顺序依赖能正确排序。
- 某个插件只监听 fanout 事件时，不应该阻塞主链路。
- 插件的 after-turn 副作用不应该改变已经确定的用户可见回复。

这层的重点是：插件可以扩展主链路，但不能让主链路变成不可预测的隐式流程。

### 5. 工具 hook 治理测试

第五层测试插件对工具调用的拦截能力。

工具 hook 风险很高，因为它能在工具真正执行前改变参数，甚至拒绝调用。

测试要覆盖：

- hook 的 tool_name 过滤是否生效。
- pre hook 能否修改参数。
- pre hook 返回 deny 时真实工具不会执行。
- pre hook 抛异常时工具调用返回 error，而不是主循环崩溃。
- post hook 能记录成功结果。
- 工具本身失败时，error hook 能记录错误。
- post hook 在观察型场景下应该尽量 fail-open，避免日志插件失败影响工具结果。
- hook trace 是否记录 matched、decision、reason、extra_message。

这里的边界是：

```text
pre hook 可以治理执行
post hook 主要负责观察
hook 失败要转成可见错误或 trace
不能让异常直接炸穿 AgentLoop
```

### 6. 异常、回滚和副作用隔离测试

第六层测试插件失败时系统如何恢复。

插件可能在这些地方失败：

- 导入失败。
- 初始化失败。
- 注册工具后初始化失败。
- lifecycle handler 抛异常。
- phase module 抛异常。
- tool hook 抛异常。
- 插件工具执行失败。
- terminate 失败。
- 插件写 KV 或数据库失败。

测试重点是：

- 初始化失败要回滚已经注册的工具、hook 和 phase module。
- terminate 失败只记录 warning，不影响其他插件释放。
- 观察型插件失败不应该阻塞核心回复。
- 安全型插件失败不能默认放行高风险操作，除非明确设计为 fail-open。
- 插件写自己的状态时要用临时目录或独立数据库测试，避免污染真实 workspace。
- 每个测试前后要清空全局插件注册表，避免插件状态跨测试串扰。

### 项目里的证据

从项目实现看，插件系统已经有清晰测试边界：

- `agent/plugins/manager.py` 负责插件发现、导入、实例化、配置注入、工具注册、hook 收集、phase module 收集、初始化回滚和卸载。
- `agent/plugins/base.py` 定义插件基类，插件通过继承自动注册。
- `agent/plugins/context.py` 给插件提供受控上下文和插件级 KV 存储。
- `agent/plugins/registry.py` 保存插件类、实例和装饰器元数据。
- `agent/tool_hooks/executor.py` 统一执行工具 hook，并区分 pre hook、post success hook 和 post error hook。
- `agent/lifecycle` 下的 phase facade 和 phase modules 负责把插件模块插入到 turn 生命周期里。
- `plugins/observe`、`plugins/recall_inspector`、`plugins/plugin_undo`、`plugins/shell_safety`、`plugins/tool_loop_guard` 都是不同类型插件测试的现实样本。

现有测试也覆盖了不少关键点：

- `tests/test_plugin_manager.py` 覆盖插件加载、重复名称、manifest、配置、KV 持久化、工具注册、生命周期事件、observe 写入等。
- `tests/test_lifecycle_phase.py` 覆盖 phase module 的执行顺序、依赖和异常传播。
- `tests/test_shell_safety_plugin.py` 覆盖安全插件对 shell 工具的拦截。
- `tests/test_plugin_undo.py` 覆盖撤回插件对 session 和 memory rollback 的副作用治理。
- `tests/test_recall_inspector_plugin.py` 覆盖 recall 诊断插件是否记录上下文和 recall 工具调用。
- `tests/test_citation_plugin.py` 覆盖 citation 插件如何维护原始证据链。

### 推荐的插件测试矩阵

可以把插件系统测试矩阵写成：

```text
加载：
正常插件 / 无 plugin.py / 导入失败 / 重名插件 / manifest 覆盖 / initialize 失败

配置：
无配置 / schema 默认值 / 用户覆盖 / 配置格式错误 / KV 持久化 / KV 隔离

工具：
注册成功 / 参数过滤 / 执行成功 / 执行失败 / 卸载注销 / 初始化失败回滚

生命周期：
before turn / prompt render / before step / after step / after turn / 顺序依赖 / 异常路径

hook：
不匹配 / 改参 / deny / pre hook 异常 / post hook 异常 / 工具异常后的 error hook

副作用：
observe 写库 / undo 回滚 / safety 拦截 / recall inspector 记录 / dashboard 数据读取
```

每个插件测试都应该回答两个问题：

```text
这个插件有没有完成自己的职责？
它失败时会不会破坏主链路？
```

### 为什么插件测试要比普通模块更严格

普通模块的边界通常比较固定，插件系统的风险更高，因为它允许第三方代码插入运行时。

它可能影响：

- prompt 内容。
- 工具参数。
- 工具是否执行。
- 记忆写入。
- session 记录。
- 观测数据库。
- 用户可见回复后的副作用。

所以插件测试的核心不是追求插件“功能更多”，而是确认扩展点可控：

```text
插件能扩展能力
插件有自己的状态边界
插件失败可以被隔离
插件副作用可以追踪
插件卸载可以清理
```

### STAR 法则思考

**Situation 情景：**

Agent 项目需要通过插件扩展工具、记忆、观测、安全和 Dashboard 能力，但插件是高风险扩展点，可能改 prompt、拦工具、写状态或监听生命周期事件。

**Task 任务：**

需要设计一套插件测试方法，既证明插件能正常扩展系统，又保证插件失败时不会破坏主对话、工具调用和状态一致性。

**Action 行动：**

把插件测试拆成加载、配置、工具注册、生命周期、工具 hook、异常回滚和副作用隔离几层。用 fixture 插件模拟正常、失败、配置、工具、hook、KV、observe 等场景；每个测试前后清理全局注册表；对工具、hook、phase module 和 after-turn 副作用分别做断言。

**Result 结果：**

这样插件系统就不是“能 import 就算成功”，而是变成一套可回归的扩展平台。新增插件时可以快速判断它是否破坏主链路、是否越过工具治理、是否污染其他插件状态，以及失败时能否被隔离。

### 面试总结

可以这样回答：

```text
插件系统测试要围绕扩展边界和失败隔离来做。我会先测插件发现、加载、manifest、配置和 KV 存储，再测插件工具是否按统一工具系统注册和卸载；然后测它在生命周期阶段是否按顺序触发，最后重点测工具 hook 的改参、拒绝、异常和 trace。更重要的是异常路径：插件导入失败、初始化失败、hook 失败、工具失败、terminate 失败时，系统应该能回滚已注册能力或把错误收敛成可观察结果，而不是破坏主对话链路。插件能扩展系统，但不能绕过工具治理，也不能把副作用变成不可追踪的黑盒。
```

### 可以改进的地方

- 增加插件初始化失败后的完整回滚断言，包括工具、hook、phase module、实例注册是否全部清理。
- 增加插件权限模型测试，明确哪些插件能访问 memory、session、workspace 或外部网络。
- 增加插件超时测试，避免生命周期 handler 或 hook 长时间阻塞主链路。
- 增加插件隔离测试，验证一个插件的 KV、数据库和配置不会污染其他插件。
- 增加插件卸载后的回归测试，确保工具不可见、hook 不再触发、事件 handler 不再产生副作用。
- 增加高风险插件的审计日志测试，比如 shell safety、undo、message push 类插件。

## Q76: 项目的配置系统是如何组织的？模型、渠道、memory、proactive、插件配置应该如何分层？

### 问题

面试官可能会问：

```text
这个项目要同时配置模型、渠道、memory、proactive、插件、MCP、peer agent 等能力。你怎么理解它的配置系统？为什么要分层？如果让你改进，你会怎么设计？
```

### 回答

这个项目的配置系统不是把所有参数平铺成一坨全局变量，而是采用“主配置文件 + 强类型配置对象 + bootstrap 分发 + 插件局部配置”的结构。

整体可以理解成四层：

```text
config.toml
  -> load_config 解析和归一化
  -> Config / 子配置 dataclass
  -> bootstrap 按模块组装运行时对象
  -> 插件和子系统读取自己的局部配置
```

这样做的核心原因是：Agent 应用的配置天然分属不同生命周期和不同风险等级，不能混在一起。

### 1. 主配置层：config.toml

项目的主配置入口是 `config.toml`，示例文件是 `config.example.toml`。

它按领域分块：

```toml
[llm]
[llm.main]
[llm.fast]
[llm.vl]

[agent]
[agent.context]
[agent.tools]
[agent.wiring]

[channels.telegram]
[channels.qq]
[channels.qqbot]

[memory]
[memory.embedding]

[proactive]
[proactive.target]
[proactive.agent]
[proactive.drift]

[integrations.fitbit]
[[integrations.peer_agents]]
```

这个分层比较合理，因为每块配置对应一个相对独立的运行时子系统：

- `llm` 管模型供应商、主模型、轻量模型、视觉模型。
- `agent` 管 Agent 行为，比如系统提示词、最大 token、最大工具循环次数、上下文窗口、工具搜索。
- `channels` 管 Telegram、QQ、QQBot、CLI socket。
- `memory` 管记忆开关、记忆引擎、embedding 模型。
- `proactive` 管主动触达目标、频率、drift、agent tick 参数。
- `integrations` 管外部集成，比如 Fitbit、peer agent。

### 2. 强类型配置层：Config dataclass

配置文件读进来后，不是到处传原始 dict，而是转成 `Config` 和一组子配置对象。

例如：

- `Config` 保存主模型、系统提示词、工具开关、运行参数。
- `ChannelsConfig` 保存不同 channel 的配置。
- `MemoryConfig` 保存记忆和 embedding 配置。
- `ProactiveConfig` 保存主动链路配置。
- `PeerAgentConfig` 保存外部 Agent 的启动和连接信息。
- `WiringConfig` 保存 context、memory、toolsets 的组装策略。

这种设计的好处是：

- 业务代码不用反复处理原始 dict。
- 字段默认值集中在配置模型里。
- 模块之间依赖更清楚。
- 测试时可以直接构造配置对象，不必每次写 TOML。
- 将来增加字段时，能更容易发现谁在使用它。

### 3. 解析和兼容层：load_config

`agent/config.py` 负责把 TOML 解析成强类型配置。

它做了几件重要事情：

1. **环境变量插值**

配置支持 `${ENV_VAR}`，适合把 API key、token 这类秘密放到环境变量里。

2. **默认值和兼容旧字段**

项目还兼容一些旧的平铺字段，例如旧版 `model`、`api_key`、`max_tokens`。这说明项目在演进中保留了向后兼容。

3. **按子系统解析**

主 loader 会分别调用 channel、proactive、memory、peer agent、fitbit、wiring 的加载逻辑。

4. **可选 channel 自动跳过**

例如 Telegram token 为空时，不启用 Telegram；QQ bot_uin 为空时，不启用 QQ。这让同一份配置可以只开启需要的 channel。

5. **proactive 配置 fail-fast**

如果 proactive 配置不合法，会直接启动失败，而不是运行一半才发现主动链路参数错误。

### 4. 运行时组装层：bootstrap

配置对象本身不直接启动系统，而是交给 `bootstrap` 层组装运行时。

典型流程是：

```text
Config
  -> build_providers
  -> build_core_runtime
  -> build_registered_tools
  -> build_memory_runtime
  -> start_channels
  -> build_proactive_runtime
  -> build_dashboard_server
```

这层的作用是把“配置值”转换成“真实运行对象”：

- 模型配置变成主 provider、轻量 provider、视觉 provider。
- channel 配置变成 Telegram、QQ、QQBot、IPC channel。
- memory 配置变成 memory runtime、markdown store、memory engine、retrieval pipeline。
- wiring 配置决定加载哪些工具集。
- proactive 配置决定是否启动主动循环。
- peer agent 配置决定是否拉起外部 agent 并注册 peer 工具。

这比在业务代码里到处读配置更清晰，因为启动阶段统一完成依赖组装，运行阶段只依赖已经构建好的对象。

### 5. 模型配置应该如何分层

模型配置不能只有一个 `model` 字段，因为不同任务对模型要求不同。

当前项目分成：

- 主模型：负责主要对话、复杂推理、工具调用。
- 轻量模型：负责 memory gate、query rewrite、HyDE、低成本判断。
- agent 模型：可给子 Agent 或特定 agent 任务使用。
- 视觉模型：当主模型不支持多模态时，单独处理图片。

这样设计的好处是成本和延迟可控。

例如：

```text
主对话用强模型
记忆检索改写用快模型
图片理解用视觉模型
子任务可单独指定模型
```

缺点是配置复杂度会上升，所以需要示例配置和合理默认值。

### 6. 渠道配置应该如何分层

渠道配置要独立于 Agent 核心配置。

原因是 Telegram、QQ、QQBot、CLI 的认证方式、用户标识、白名单、群聊规则都不一样。

当前项目把它们放在 `channels` 下：

- Telegram 配 token 和 allow_from。
- QQ 配 bot_uin、allow_from、groups、require_at。
- QQBot 配 app_id、client_secret、openid、group 配置。
- CLI 配 socket。

这符合多端 Agent 的要求：channel adapter 只关心自己那一块配置，主 Agent 不需要知道 Telegram token 或 QQ websocket 的细节。

### 7. memory 配置应该如何分层

memory 配置至少要分成三层：

```text
是否启用 memory
使用哪个 memory engine
embedding 模型怎么配置
```

当前项目里：

- `[memory]` 控制 enabled 和 engine。
- `[memory.embedding]` 控制 embedding model、api_key、base_url。
- default memory 的更细检索阈值放在插件自己的配置文件里。

这说明项目把“主系统是否启用记忆”和“某个记忆插件内部如何调参”分开了。

这个边界是对的，因为 memory engine 可以替换；主配置只应该关心选择哪个 engine 和必要连接参数，具体召回阈值、排序参数、写入策略更适合归属于 memory 插件自身。

### 8. proactive 配置应该如何分层

proactive 的配置最复杂，不能简单平铺。

当前项目采用：

- `enabled`：是否开启主动链路。
- `profile`：选择主动策略预设。
- `target`：主动发到哪个 channel/chat。
- `feed`：内容源轮询。
- `agent`：主动 agent tick 的步数、内容限制、web_fetch 限制、冷却。
- `drift`：无候选时的自主行为配置。
- `overrides`：对策略预设做白名单覆盖。

这个设计比全部开放参数更稳，因为主动触达涉及打扰用户、重复推送、内容 ACK 和冷却策略。如果把所有算法参数都暴露，很容易配置出危险组合。

所以 proactive 采用“预设 + 白名单覆盖 + 范围校验”是合理的。

### 9. 插件配置应该如何分层

插件配置不应该全部塞进主 `config.toml`。

原因是插件是可插拔能力，插件自己的参数最好和插件目录绑定。

当前插件配置方式是：

- 插件目录里可以有 `_conf_schema.json`，声明默认值。
- 插件目录里可以有 `plugin_config.json`，覆盖默认值。
- 插件加载时把配置注入到插件上下文。
- 插件还有自己的 KV 存储，用于运行状态。

这样设计的好处是：

- 主配置不会被插件参数污染。
- 插件迁移时可以带着自己的 schema 和默认值。
- 插件之间的配置和状态隔离。
- 插件卸载时更容易清理。

### 设计取舍

这个配置系统的主要优点是：

- 主配置按领域分块，比较清晰。
- 强类型配置对象降低运行时错误。
- bootstrap 层统一完成依赖组装。
- proactive 配置有预设、白名单和范围校验。
- 插件配置局部化，避免污染主配置。
- channel 为空自动跳过，适合多端按需启用。

主要缺点是：

- 新旧字段兼容让 loader 逻辑变复杂。
- 配置校验不完全统一，有些在 dataclass 默认值里，有些在 loader 里，有些在子系统里。
- 密钥管理还比较基础，主要依赖环境变量和本地文件。
- 插件配置没有统一的类型校验能力，更多依赖插件自己正确读取。
- 多环境配置能力不足，例如 dev/staging/prod 还没有标准 overlay 机制。

### 可以改进的方向

如果继续工程化，我会这样改进：

- 引入统一配置 schema 校验，把类型、必填、范围、弃用字段集中管理。
- 支持 `config.local.toml` 或环境 overlay，区分开发、测试、生产。
- 对 API key、token、client_secret 做更明确的 secret 管理，不在示例里鼓励明文。
- 给 `akashic config doctor` 之类命令，启动前检查模型、channel、memory、proactive、插件配置是否有效。
- 给插件配置增加 schema 校验和类型转换，避免插件拿到错误类型。
- 把旧字段兼容标记为 deprecated，并在日志中提示迁移。

### STAR 法则思考

**Situation 情景：**

这个 Agent 项目要同时管理模型供应商、多端渠道、记忆系统、主动推送、插件、MCP 和外部 Agent，配置项多、风险等级不同，而且部分配置包含密钥。

**Task 任务：**

需要设计一套配置结构，让不同子系统只读取自己的配置，同时启动阶段能把配置转换成清晰的运行时依赖，并在关键参数错误时尽早失败。

**Action 行动：**

项目用 `config.toml` 做主配置入口，按 llm、agent、channels、memory、proactive、integrations 分块；再由配置加载器解析成强类型对象；bootstrap 层根据配置构建 provider、channel、memory runtime、toolset、proactive loop 和 dashboard；插件则使用插件目录内的 schema、局部配置和 KV 存储。

**Result 结果：**

配置系统既能支持多模型、多渠道、多插件的复杂运行时，又能保持模块边界清楚。新增 channel、memory engine 或工具集时，不需要重写主 Agent，只要增加配置模型、加载逻辑和 bootstrap wiring 即可。

### 面试总结

可以这样回答：

```text
这个项目的配置系统是分层的。最外层是 config.toml，按模型、Agent 行为、渠道、memory、proactive、外部集成分块；加载后会转成强类型配置对象，而不是让业务代码到处读原始字典；启动时再由 bootstrap 层把配置组装成模型提供者、渠道适配器、记忆运行时、工具集、主动循环和 Dashboard。插件配置则放在插件自己的目录里，通过 schema 默认值、用户覆盖和插件 KV 存储保持局部隔离。这样设计的价值是让配置边界和模块边界一致，同时让高风险配置，比如 proactive 和密钥，能做更明确的校验和治理。
```

### 可以补充到简历/面试里的亮点

- 配置分层体现了 Agent 工程化能力，不是 demo 式硬编码。
- 主模型、轻量模型、视觉模型分离，体现成本和延迟优化。
- proactive 使用预设和白名单覆盖，体现高风险能力的配置治理。
- 插件配置局部化，体现扩展系统的隔离设计。
- bootstrap wiring 让不同 memory engine、toolset、context builder 可以被替换，体现可演进架构。

## Q77: workspace 初始化时需要创建哪些目录、数据库和默认文件？为什么运行状态不能散落在项目根目录？

### 问题

面试官可能会问：

```text
这个项目为什么要有 workspace？初始化 workspace 时会创建哪些目录、数据库和默认文件？为什么不直接把运行状态放在项目根目录里？
```

### 回答

workspace 是这个 Agent 的“运行时数据边界”。

代码仓库放的是程序本身，workspace 放的是用户数据、会话状态、记忆、调度任务、主动推送状态、插件状态和观测数据。

可以简单理解为：

```text
代码仓库 = 程序定义
workspace = 这个 Agent 实例的运行状态
```

这个分离很重要，因为 Agent 是长期运行系统，不是一次性脚本。它会不断产生状态，如果这些状态散落在项目根目录里，会带来备份、迁移、部署、测试和权限管理上的问题。

### workspace 初始化会创建什么

项目里 `bootstrap/init_workspace.py` 负责初始化 workspace。

初始化时主要创建五类资源。

### 1. 主配置文件

如果 `config.toml` 不存在，会从 `config.example.toml` 复制一份。

这个文件不一定在 workspace 内，取决于传入的 `config_path`，但它是启动前必须准备的主配置入口。

它包含：

- 模型配置。
- channel 配置。
- memory 配置。
- proactive 配置。
- 外部集成配置。

### 2. memory 文本文件

workspace 下会创建 `memory/` 目录，并预置这些文件：

```text
memory/MEMORY.md
memory/HISTORY.md
memory/RECENT_CONTEXT.md
memory/PENDING.md
memory/SELF.md
```

它们的职责不同：

- `MEMORY.md`：长期 markdown 记忆。
- `HISTORY.md`：历史归档或人类可读的历史记录。
- `RECENT_CONTEXT.md`：近期语境压缩，给 proactive 和 drift 使用。
- `PENDING.md`：待处理或 pending memory。
- `SELF.md`：Agent 自我模型和关系理解，初始化时会写入默认模板。

这些文件适合人类查看和手动编辑，因此放在 workspace 下的 `memory/` 里。

### 3. workspace 级 JSON 文件

初始化还会创建一些 JSON 文件：

```text
mcp_servers.json
schedules.json
proactive_sources.json
memes/manifest.json
proactive_quota.json
```

它们分别对应：

- `mcp_servers.json`：MCP server 配置。
- `schedules.json`：定时任务配置和状态。
- `proactive_sources.json`：主动信息源配置。
- `memes/manifest.json`：meme 插件的资源清单。
- `proactive_quota.json`：主动行为配额状态。

这些是轻量结构化状态，用 JSON 比较直观，也方便人工排查。

### 4. SQLite 数据库

workspace 初始化会创建多个数据库。

最核心的是：

```text
sessions.db
memory/consolidation_writes.db
proactive.db
memory/memory2.db
observe/observe.db
```

其中：

- `sessions.db` 保存 session 元数据、消息、presence 时间、全文索引。
- `memory/consolidation_writes.db` 保存 markdown memory consolidation 的幂等写入记录。
- `proactive.db` 保存主动推送的 seen、delivery、context-only、drift、tick log 等状态。
- `memory/memory2.db` 保存默认语义记忆引擎的数据。
- `observe/observe.db` 保存 turn trace、retrieval trace、memory write trace 等观测数据。

严格说，`observe.db` 通常由 observe 插件或 dashboard 访问时初始化，不一定在 init_workspace 里直接创建；但它也属于 workspace 运行状态。

### 5. 运行目录

初始化会创建这些目录：

```text
observe/
skills/
drift/skills/
mcp/
memory/journal/
memes/
```

其中：

- `observe/` 存观测数据库和诊断数据。
- `skills/` 存普通 skill。
- `drift/skills/` 存 drift 相关 skill。
- `mcp/` 存 MCP 相关运行文件。
- `memory/journal/` 存 memory 相关流水或中间记录。
- `memes/` 存 meme 资源清单和素材。

插件也可能在自己的目录里维护 `.kv.json`，这是插件级状态，不直接混到主 workspace 根目录。

### 为什么运行状态不能散落在项目根目录

主要有六个原因。

### 1. 代码和数据生命周期不同

代码可以更新、回滚、重装。

但用户会话、长期记忆、主动推送状态、任务状态不能因为升级代码就丢失。

如果运行数据散落在项目目录里，升级或重新 clone 仓库时很容易误删状态。

### 2. 便于备份和迁移

workspace 是一个清晰的数据边界。

要迁移 Agent 实例时，可以迁移：

```text
config.toml
workspace/
```

而不是在整个项目目录里找各种 `.db`、`.json`、`.md`、日志和插件状态。

### 3. 支持多实例

同一份代码可以服务多个 Agent 实例，只要使用不同 workspace。

例如：

```text
workspace-personal/
workspace-work/
workspace-test/
```

如果状态写死在项目根目录，一个代码仓库只能安全运行一个实例，多实例会互相污染。

### 4. 便于测试隔离

测试可以用临时 workspace。

这样每个测试都能创建独立的：

- session 数据库。
- memory 文件。
- proactive 状态。
- observe 数据库。
- 插件 KV。

测试结束后删掉临时目录即可，不会污染真实用户数据。

### 5. 权限和隐私边界更清楚

workspace 里包含隐私数据：

- 用户消息。
- 长期记忆。
- API 使用痕迹。
- channel chat_id。
- 主动推送状态。
- 插件记录。

这些数据不应该和代码文件混在一起，更不应该被误提交到 git。

workspace 独立后，可以单独做权限控制、备份加密和脱敏。

### 6. Dashboard 和运维更容易

Dashboard 只要指向 workspace，就能读取：

- `sessions.db`
- `memory/`
- `proactive.db`
- `observe/observe.db`
- 插件 dashboard 数据

这让可观测界面和运行实例绑定，而不是和代码仓库绑定。

### 项目里的证据

从代码看，workspace 贯穿运行时：

- `build_app_runtime` 默认 workspace 是 `~/.akashic/workspace`。
- `bootstrap/init_workspace.py` 负责创建默认文件、目录和数据库。
- `SessionStore` 使用 `workspace/sessions.db` 保存会话和消息。
- `MemoryStore` 使用 `workspace/memory/` 下的 markdown 文件和 consolidation 数据库。
- default memory engine 默认使用 `workspace/memory/memory2.db`。
- `ProactiveStateStore` 使用 `workspace/proactive.db`。
- scheduler 使用 `workspace/schedules.json`。
- MCP 使用 `workspace/mcp_servers.json`。
- Dashboard 读取 workspace 下的 session、memory、proactive 和 observe 数据。
- 插件 manager 会把 workspace 注入插件上下文，让插件知道自己的运行实例边界。

### 设计取舍

workspace 设计的优点是边界清晰：

```text
程序可以升级
数据可以保留
实例可以复制
测试可以隔离
运维可以备份
```

缺点是：

- 初次使用需要初始化步骤。
- 用户要理解 config 和 workspace 的区别。
- 数据文件较多，缺少统一说明时容易迷路。
- 不同状态文件的创建时机不完全一致，有些 init 时创建，有些首次使用时创建。

但对长期运行 Agent 来说，这个复杂度是值得的。

### 可以改进的方向

- 增加 `workspace manifest`，列出每个文件/目录的用途、创建者和是否可备份。
- 增加 `akashic doctor` 检查 workspace 是否完整、数据库 schema 是否可用。
- 增加 `akashic backup` 和 `akashic restore`，统一备份 memory、session、proactive、observe 和插件状态。
- 把 `observe.db`、插件 KV、memory2.db 等首次使用创建的资源纳入初始化报告。
- 给敏感文件增加权限检查，避免过宽权限暴露用户记忆和 channel 标识。
- 增加 workspace 版本号和迁移机制，方便未来 schema 升级。

### STAR 法则思考

**Situation 情景：**

Agent 是长期运行系统，会持续产生用户会话、长期记忆、主动推送状态、观测数据、插件状态和调度任务。如果这些状态散落在代码目录里，升级、备份、测试和多实例运行都会变得混乱。

**Task 任务：**

需要设计一个统一的运行时数据边界，让代码和数据分离，同时让初始化、迁移、备份和诊断都有明确入口。

**Action 行动：**

项目通过 workspace 承载运行状态，并在初始化时创建 memory 文档、会话数据库、主动推送数据库、调度文件、MCP 配置、skills 目录、observe 目录和 memory engine 存储。启动和 Dashboard 都围绕 workspace 构建运行对象和诊断视图。

**Result 结果：**

这样同一份代码可以对应多个独立 Agent 实例，用户数据不会被代码升级破坏，测试可以使用临时 workspace 隔离状态，运维也可以围绕 workspace 做备份、迁移和排查。

### 面试总结

可以这样回答：

```text
workspace 是这个项目的运行时数据边界。初始化时会创建 memory 文档、SELF 模板、PROACTIVE_CONTEXT、MCP 配置、调度文件、主动源配置、skills 目录、observe 目录、sessions.db、proactive.db、memory consolidation 数据库，以及默认语义记忆库。会话、长期记忆、主动推送状态、观测 trace 和插件状态都应该放在 workspace，而不是散落在项目根目录。这样代码升级和用户数据分离，多实例可以共用一份代码但使用不同 workspace，测试可以用临时 workspace，部署时也更容易备份、迁移和做权限控制。
```

### 可以补充到简历/面试里的亮点

- 通过 workspace 把 Agent 程序和用户运行状态解耦。
- 会话、记忆、主动推送、观测、插件状态都有明确落点。
- 支持多实例和测试隔离，体现长期运行 Agent 的工程化思维。
- 初始化过程不是只创建空目录，而是预置默认文件、数据库 schema 和下一步操作提示。

## Q78: CLI、Telegram、QQ 等不同 channel adapter 的启动路径有什么共同点和差异？

### 问题

面试官可能会问：

```text
这个项目支持 CLI、Telegram、QQ、QQBot 等多个入口。它们的启动路径有什么共同点？不同 channel adapter 的差异在哪里？为什么要统一成 MessageBus，而不是每个渠道直接调用 Agent？
```

### 回答

这些 channel adapter 的共同点是：它们都只是“通信适配层”，不直接实现 Agent 推理逻辑。

每个 channel 做三件事：

```text
接收外部消息
转换成统一 InboundMessage
订阅本渠道 OutboundMessage 并发回外部平台
```

也就是说，不管消息来自 CLI、Telegram、QQ 私聊还是 QQ 群聊，进入 Agent 之前都会被统一成：

```text
channel
sender
chat_id
content
media
metadata
```

然后通过 `MessageBus` 交给 AgentLoop。

AgentLoop 不需要知道 Telegram polling、QQ WebSocket、QQBot REST API 或 CLI socket 的细节。

### 共同启动路径

项目启动时，`AppRuntime.start()` 会先构建核心运行时，然后调用 channel 启动逻辑。

整体路径可以概括为：

```text
AppRuntime.start
  -> build_core_runtime
  -> start_channels
  -> 启动 IPC / Telegram / QQ / QQBot
  -> channel 发布 InboundMessage 到 MessageBus
  -> AgentLoop 消费消息
  -> AgentLoop 发布 OutboundMessage
  -> MessageBus 按 channel 分发给对应 adapter
```

共同点包括：

- 都依赖同一个 `MessageBus`。
- 都把外部消息包装成统一入站消息。
- 都通过 `channel + chat_id` 形成 session_key。
- 都订阅自己的出站 channel。
- 都可以把发送能力注册到 `MessagePushTool`，供 proactive 或工具主动发消息。
- 都和 `SessionManager` 协作，维护会话、用户映射或元数据。
- 都可以接入中断控制，比如 `/stop`。

### CLI adapter 的特点

CLI 入口走的是本地 IPC。

项目里 `IPCServerChannel` 会启动：

- POSIX 上默认 Unix domain socket。
- Windows 上使用 loopback TCP。

CLI 客户端连接后，每一行 JSON 都会被解析成消息。

它的特点是：

- 本地开发和调试最简单。
- 不需要外部平台 token。
- 每个连接会生成一个临时 chat_id，例如 `cli-<writer id>`。
- 入站消息的 channel 是 `cli`。
- 出站时根据 chat_id 找到对应 socket writer，把回复写回 CLI。
- socket 文件权限会设置为 `0600`，避免本机其他用户随便连接。

CLI 更像本地控制台入口，适合开发、测试和单用户交互。

### Telegram adapter 的特点

Telegram 入口走 Telegram Bot API。

启动时会：

- 创建 Telegram Application。
- 注册文本、图片、文件、命令 handler。
- 注册 `/stop`。
- 启动 polling。
- 订阅 `telegram` channel 的出站消息。
- 注册 Telegram 的主动发送能力到 `MessagePushTool`。

Telegram 的特点是：

- 需要 bot token。
- 支持 allow_from 白名单，可以按 user id 或 username 过滤。
- chat_id 来自 Telegram chat id。
- session_key 形如 `telegram:<chat_id>`。
- 支持图片和文件下载到 workspace uploads。
- 支持 reply 上下文，把被回复消息和媒体带入入站内容。
- 支持 bot commands，由插件提供的命令也能注册进去。
- 支持 live update，比如思考、工具调用、流式回复。
- 出站发送要处理 Markdown、限流、流式消息和图片文件。

Telegram adapter 比 CLI 复杂，因为它要处理真实平台的消息重投、文件下载、格式限制、用户身份映射和发送限流。

### QQ adapter 的特点

普通 QQ 入口基于 NapCat / NcatBot。

它的特点是：

- 需要配置 bot_uin。
- NcatBot 的后端启动是同步阻塞的，所以要放到 executor 里运行。
- NcatBot 回调可能在独立线程或 event loop，需要用跨 loop 提交把消息送回主 loop。
- 支持 QQ 私聊和群聊。
- 私聊 chat_id 是用户 QQ 号。
- 群聊 chat_id 形如 `gqq:<group_id>`。
- 群聊是否处理要看 groups 配置、allow_from 和 require_at。
- QQ 图片通过 CQ 码提取 URL，再下载成本地附件。
- 出站时根据 chat_id 判断私聊或群聊，调用不同发送 API。
- 本地文件发送给 QQ 时可能要转成 base64 URI。

QQ adapter 的复杂度主要来自 SDK 和平台协议：线程模型、群聊过滤、CQ 码、图片下载、私聊/群聊发送 API 都需要适配。

### QQBot adapter 的特点

官方 QQBot 入口和普通 QQ 不同。

它使用：

- 官方 access token。
- Gateway WebSocket 接收事件。
- REST API 发送消息。
- 私聊 c2c openid 作为目标。

特点是：

- 配置 app_id 和 client_secret。
- channel 是 `qqbot`。
- 私聊 chat_id 形如 `c2c:<user_openid>`。
- 当前实现主要支持私聊。
- 需要维护 token 缓存和 gateway 心跳。
- 收到 C2C 消息后会记录 message_id，用于发送输入状态或流式消息。
- 出站支持普通消息和官方 stream_messages，失败时降级普通发送。
- proactive 发送时会校验 chat_id 是否为 c2c。

QQBot 更接近官方平台协议，认证和发送路径比 NapCat QQ 更规范，但限制也更多。

### 统一 MessageBus 的价值

如果每个 channel 直接调用 Agent，会出现几个问题：

- AgentLoop 要知道所有平台细节。
- 每新增一个 channel 都要改主 Agent。
- session_key、media、metadata、sender 的结构会不统一。
- 出站发送失败、重试、降级逻辑难以集中。
- proactive 和 message_push 工具很难复用多平台发送能力。
- 测试需要真实平台，难以用 fake bus 做集成测试。

统一成 MessageBus 后，边界变成：

```text
channel adapter 负责平台协议
MessageBus 负责消息排队和路由
AgentLoop 负责推理和工具循环
MessagePushTool 负责主动发送抽象
```

这样 channel 和 Agent 核心解耦。

### channel adapter 的输入输出边界

入站边界：

```text
外部平台原始事件
  -> 鉴权 / 白名单 / 群聊过滤 / 去重
  -> 下载附件
  -> 组装 InboundMessage
  -> publish_inbound
```

出站边界：

```text
OutboundMessage
  -> MessageBus 按 channel 分发
  -> adapter 格式化文本 / markdown / 图片 / 文件
  -> 调外部平台 API
  -> 失败时记录或降级
```

这个边界让 AgentLoop 只关心统一消息，而不关心外部平台。

### 不同 channel 的 session_key 差异

所有入站消息都有统一的 `session_key` 规则：

```text
session_key = channel + ":" + chat_id
```

但 chat_id 的含义因平台不同：

```text
CLI:      cli-<connection id>
Telegram: Telegram chat.id
QQ 私聊:  QQ user_id
QQ 群聊:  gqq:<group_id>
QQBot:   c2c:<user_openid>
```

这个设计很关键，因为它保证：

- 不同 channel 不会因为 chat_id 相同而串 session。
- QQ 私聊和群聊可以区分。
- QQBot openid 和普通 QQ 号不会混淆。
- memory scope、presence、tool visibility 都能基于 session_key 隔离。

### 设计取舍

这种 channel adapter 设计的优点是：

- Agent 核心不依赖具体平台。
- 多渠道可以复用同一套 AgentLoop、memory、tools、plugins。
- 每个 adapter 可以独立处理平台差异。
- proactive 可以通过 MessagePushTool 统一发送。
- 测试可以绕过真实平台，直接构造 InboundMessage。

缺点是：

- channel adapter 自己会比较复杂，特别是 Telegram live update 和 QQ loop 桥接。
- 平台特有能力不容易完全统一，比如 Telegram 文件、QQ CQ 码、QQBot stream。
- 出站能力在不同渠道不完全一致，需要降级策略。
- CLI 当前 chat_id 绑定连接，连接断开后 session 连续性弱。
- channel 层和 session metadata 的关系需要维护好，否则主动推送找不到用户映射。

### 项目里的证据

从代码看：

- `bootstrap/channels.py` 统一启动 IPC、Telegram、QQ、QQBot，并把发送函数注册到 `MessagePushTool`。
- `bus/events.py` 定义统一的 `InboundMessage` 和 `OutboundMessage`。
- `bus/queue.py` 负责入站队列、出站队列和按 channel 分发。
- `infra/channels/ipc_server.py` 负责 CLI 本地 socket。
- `infra/channels/telegram_channel.py` 负责 Telegram Bot polling、白名单、文件下载、live update。
- `infra/channels/qq_channel.py` 负责 NapCat/NcatBot、QQ 私聊、QQ群聊、CQ 图片和跨 event loop 桥接。
- `infra/channels/qqbot_channel.py` 负责官方 QQBot gateway、token、私聊消息、REST 发送和 stream_messages。
- `agent/tools/message_push.py` 把不同 channel 的发送能力收敛成主动推送工具。

### STAR 法则思考

**Situation 情景：**

Agent 项目需要支持本地 CLI、Telegram、QQ、QQBot 等多个入口，每个平台的协议、鉴权、消息格式、附件处理和发送 API 都不同。

**Task 任务：**

需要让多平台接入不污染 Agent 核心，同时保证会话隔离、出站路由、主动推送和中断控制都能复用。

**Action 行动：**

项目把不同平台封装成 channel adapter，每个 adapter 只负责平台协议，把消息转换成统一入站结构并发布到 MessageBus；AgentLoop 只消费统一消息；回复通过统一出站消息按 channel 分发；主动推送能力通过 MessagePushTool 注册各 channel 的发送函数。

**Result 结果：**

新增渠道时不用重写 Agent 主链路，只要实现入站转换和出站发送即可。CLI、Telegram、QQ、QQBot 可以复用同一套记忆、工具、插件、生命周期和主动推送逻辑，同时通过 channel + chat_id 保持 session 隔离。

### 面试总结

可以这样回答：

```text
CLI、Telegram、QQ、QQBot 的共同点是都只是 channel adapter，不直接做 Agent 推理。它们负责接收平台消息、做鉴权和过滤、下载附件，然后统一包装成 InboundMessage 发到 MessageBus；AgentLoop 处理完后再发布 OutboundMessage，由 MessageBus 按 channel 分发回对应 adapter。差异在于平台协议：CLI 是本地 socket，Telegram 是 Bot API polling，QQ 是 NapCat/NcatBot 和群聊过滤，QQBot 是官方 gateway 加 REST API。统一 MessageBus 的价值是让 Agent 核心和平台协议解耦，多端共享同一套 memory、tools、plugins 和 proactive 逻辑，并通过 channel + chat_id 保持会话隔离。
```

### 可以改进的地方

- 给 channel adapter 定义更明确的接口协议，统一 start、stop、send、send_stream、send_file、send_image 能力。
- 为不同 channel 的能力做 capability 描述，避免 proactive 调用某个 channel 不支持的发送类型。
- 增加 channel 级健康检查，Dashboard 显示 Telegram polling、QQ WebSocket、QQBot gateway 状态。
- 增加 CLI 稳定身份机制，让本地 CLI 重连后可以复用同一个 session。
- 增加统一的附件生命周期管理，定期清理 uploads 中不再引用的文件。
- 增加 channel adapter 的集成测试矩阵，用 fake platform client 覆盖鉴权、去重、群聊过滤、附件下载和发送失败。

## Q79: Dashboard 在部署中应该如何启动、保护和访问？为什么它不应该只是开发期临时页面？

### 问题

面试官可能会问：

```text
这个项目有 Dashboard。它在部署时应该怎么启动、怎么保护、怎么访问？为什么 Dashboard 不应该只是开发期临时页面？
```

### 回答

Dashboard 在这个项目里不只是“开发调试页面”，而是 Agent 长期运行时的运维和诊断入口。

因为 Agent 是一个长期运行系统，它会持续产生：

- 会话消息。
- 长期记忆。
- memory retrieval trace。
- memory write trace。
- proactive tick log。
- 工具调用链。
- 插件诊断数据。
- 用户可见和不可见的副作用状态。

这些东西只靠命令行日志很难排查，所以 Dashboard 应该被当成运行时可观测和人工干预界面，而不是临时网页。

### Dashboard 如何启动

项目启动时，`AppRuntime.start()` 会构建 Dashboard server。

整体路径是：

```text
AppRuntime.start
  -> build_dashboard_server
  -> create_dashboard_app
  -> uvicorn.Server.serve()
```

Dashboard 使用 FastAPI + Uvicorn。

当前默认参数是：

```text
host = 0.0.0.0
port = 2236
```

启动后会提供：

- `/`：Dashboard 前端页面。
- `/assets/*`：静态前端资源。
- `/api/dashboard/*`：核心 Dashboard API。
- `/plugins/{plugin_id}/panel.js`：插件面板 JS。
- `/plugins/{plugin_id}/panel.css`：插件面板 CSS。

它读取的主要数据源在 workspace 下：

- `sessions.db`
- `memory/memory2.db`
- `memory/*.md`
- `proactive.db`
- `observe/observe.db`
- 插件自己的 dashboard 数据

### Dashboard 能做什么

当前 Dashboard 已经不是只读页面，它包含很多运行时操作。

它可以查看：

- session 列表。
- 某个 session 的消息。
- message 详情。
- memory item 列表。
- 相似 memory。
- proactive overview。
- proactive delivery。
- seen items。
- rejection cooldown。
- semantic items。
- tick log。
- tick step。
- 插件自定义面板。

它也可以执行写操作：

- 修改 session metadata。
- 删除 session。
- 批量删除 session。
- 修改 message。
- 删除 message。
- 批量删除 message。
- 修改 memory 状态和字段。
- 删除 memory。
- 批量删除 memory。
- 手动触发 memory consolidation。
- 手动触发 memory optimizer。
- 删除 proactive seen items。
- 删除 proactive rejection cooldown。
- 插件面板可能提供更多操作，比如 memory rollup 提交候选。

这意味着 Dashboard 是高权限入口。

它能影响 Agent 记忆、会话、主动推送状态和诊断数据，所以部署时必须保护。

### 为什么不能裸露到公网

当前代码里没有看到完整的认证和授权中间件。

而 Dashboard 默认绑定 `0.0.0.0:2236`，如果部署机器对公网开放这个端口，就可能让任何人访问到：

- 用户聊天记录。
- 长期记忆。
- 用户身份和 channel chat_id。
- 主动推送状态。
- 工具调用链。
- memory 写入记录。
- 插件诊断数据。

更严重的是，Dashboard 还提供删除和修改接口。

所以部署时不能裸露公网。

更合理的方式是：

```text
默认只监听 127.0.0.1
通过 SSH tunnel 或 VPN 访问
如果必须远程访问，用反向代理加认证、HTTPS、IP 白名单
高风险写操作增加 CSRF / 二次确认 / 审计日志
```

### 推荐部署方式

我会按安全等级分三种部署方式。

### 1. 本机开发环境

适合学习、调试和单机使用。

建议：

```text
host = 127.0.0.1
port = 2236
```

只允许本机浏览器访问。

如果当前代码默认是 `0.0.0.0`，部署时最好改配置或启动参数，让 Dashboard 只绑定本地。

### 2. 远程服务器个人使用

适合 Agent 跑在云服务器上。

建议不要直接开放 2236。

可以用 SSH tunnel：

```text
ssh -L 2236:127.0.0.1:2236 user@server
```

然后本地访问：

```text
http://127.0.0.1:2236
```

这样 Dashboard 对公网不可见。

### 3. 团队或生产环境

如果必须多人访问，需要把 Dashboard 放到反向代理后面。

至少要有：

- HTTPS。
- 登录认证。
- IP 白名单。
- Basic Auth 或 OAuth。
- 写操作审计。
- 只读角色和管理员角色区分。
- 访问日志。
- 备份和恢复机制。

否则 Dashboard 的风险比普通管理后台还高，因为里面有用户记忆和可修改的 Agent 状态。

### 为什么 Dashboard 不应该只是开发期临时页面

因为 Agent 的很多问题只在长期运行中出现。

例如：

- 某条记忆为什么被召回。
- 哪个 session 的上下文过长。
- proactive 为什么没有推送。
- proactive 为什么重复推送。
- memory 写入是否覆盖了旧事实。
- 某条消息有没有进入 session history。
- 工具调用链是否异常。
- 插件是否写入了诊断记录。
- memory optimizer 是否正在运行。
- 某个用户的 last_proactive_at 是否异常。

这些都不是开发期一次性问题，而是运行期运维问题。

如果没有 Dashboard，排查只能靠：

```text
翻日志
查 sqlite
打开 markdown 文件
手动 grep jsonl
猜测 Agent 当时的上下文
```

效率很低，也不利于面试时表达工程能力。

Dashboard 的意义是把 Agent 的内部状态变成可观察、可操作、可复盘的运行系统。

### Dashboard 和插件系统的关系

Dashboard 还支持插件面板。

插件目录里可以提供：

- `dashboard.py`
- `dashboard_panel.ts`
- `dashboard_panel.js`
- `dashboard_panel.css`

Dashboard 启动时会扫描插件目录：

- 编译或加载插件面板。
- 挂载插件自己的 API。
- 前端动态加载插件 panel。

这让 Dashboard 不只是核心系统页面，也可以成为插件的诊断入口。

例如：

- recall inspector 展示每轮 recall 的上下文和工具调用。
- memory rollup 提供长期记忆候选确认。
- status commands 展示 KV cache 统计。
- default memory 提供 memory engine 诊断面板。

这个设计符合插件化 Agent 的架构：插件不仅扩展工具，也能扩展运维可视化。

### 项目里的证据

从代码看：

- `bootstrap/app.py` 在主应用启动时创建并运行 dashboard server。
- `bootstrap/dashboard_api.py` 使用 FastAPI 创建 Dashboard API。
- `build_dashboard_server` 默认返回 Uvicorn server。
- 静态前端资源在 `static/dashboard/`。
- 前端源码在 `frontend/dashboard/src/`。
- API 会读取 `SessionStore`、memory admin、`ProactiveStateStore` 和插件 dashboard。
- `plugins/recall_inspector/dashboard.py`、`plugins/memory_rollup/dashboard.py`、`plugins/status_commands/dashboard.py` 都会给 Dashboard 增加插件视图。
- `tests/test_dashboard_api.py` 覆盖了 session、memory、proactive、手动 consolidation、memory optimizer 等接口。

### 设计取舍

Dashboard 的优点是：

- 运行状态可视化。
- 记忆和会话可检索。
- proactive 行为可复盘。
- 插件可扩展自己的诊断面板。
- 可以手动触发维护任务。

风险是：

- 里面包含敏感数据。
- 当前接口有高权限写操作。
- 默认 `0.0.0.0` 对部署不够保守。
- 如果没有认证，不能对外开放。
- 写操作缺少更细粒度权限和审计。

所以 Dashboard 的正确定位是：

```text
它应该是长期运行 Agent 的本地/受保护运维后台
而不是公网开放的普通网页
```

### 可以改进的方向

- 默认 host 改成 `127.0.0.1`，除非用户显式配置公开监听。
- 增加 dashboard 配置块，例如 host、port、enabled、auth、readonly。
- 增加认证机制，至少支持 token 或 basic auth。
- 增加只读模式，学习或观测时禁用删除和修改接口。
- 对删除、批量删除、memory 修改、proactive 状态清理增加二次确认和审计日志。
- 增加 CSRF 防护，避免浏览器侧误触发写接口。
- 增加 Dashboard 健康检查和版本信息。
- 增加敏感字段脱敏，例如 chat_id、token、source_ref 中的隐私片段。

### STAR 法则思考

**Situation 情景：**

Agent 长期运行后会积累大量内部状态，包括会话、记忆、主动推送状态、工具链路和插件诊断数据。只靠日志很难理解系统为什么做出某个决策。

**Task 任务：**

需要提供一个运行时诊断入口，让开发者或运维者能查看、检索、复盘和必要时修正 Agent 状态，同时保证这个入口不会暴露用户隐私或成为高风险管理后门。

**Action 行动：**

项目把 Dashboard 集成到主应用启动流程中，用 FastAPI 提供 session、message、memory、proactive 和插件面板 API，读取 workspace 下的数据库和状态文件，并支持手动 consolidation、memory optimizer 等维护操作。部署上应把它放在本地监听、SSH tunnel、VPN 或反向代理认证之后。

**Result 结果：**

Dashboard 让 Agent 从黑盒运行变成可观察、可诊断、可维护的系统。它能帮助定位 memory 召回、proactive 决策、session 状态和插件行为问题，但也必须被视为高权限后台，不能裸露公网。

### 面试总结

可以这样回答：

```text
Dashboard 在这个项目里不是开发期临时页面，而是长期运行 Agent 的运维后台。它启动时由主应用创建 FastAPI/Uvicorn server，读取 workspace 里的 session、memory、proactive、observe 和插件数据，提供会话、消息、记忆、主动推送和插件诊断视图，还能触发 memory consolidation、memory optimizer、删除或修改部分状态。因此它必须被保护：生产部署不应该裸露 0.0.0.0 端口，最好只监听 127.0.0.1，通过 SSH tunnel、VPN 或反向代理认证访问。因为它包含用户隐私和高权限写操作，所以后续应该补认证、只读模式、审计日志和二次确认。
```

### 可以补充到简历/面试里的亮点

- Dashboard 把 Agent 内部状态产品化为可观测后台。
- 支持 session、memory、proactive、插件诊断，覆盖运行时关键问题。
- 插件可以扩展自己的 Dashboard 面板，说明系统有可扩展运维界面。
- 能明确指出当前 Dashboard 的安全缺口和生产化改进方向，体现工程判断。

## Q80: 如果要把这个项目部署成长期运行的 Agent 服务，需要关注哪些进程管理、日志、备份和升级问题？

### 问题

面试官可能会问：

```text
如果这个项目不只是本地跑 demo，而是要作为长期运行的 Agent 服务部署，你会关注哪些进程管理、日志、备份和升级问题？
```

### 回答

长期运行的 Agent 服务和一次性 CLI demo 最大区别是：它会持续接收消息、调用工具、写记忆、跑定时任务、主动推送、维护插件状态。

所以部署时不能只关心“进程能不能启动”，而要关心：

```text
进程如何守护
异常如何恢复
状态如何持久化
日志如何排查
数据如何备份
升级如何回滚
外部依赖如何降级
```

### 1. 进程管理

这个项目主入口是 `main.py`。

常见模式包括：

```text
python main.py init       初始化配置和 workspace
python main.py            启动 Agent 服务
python main.py gateway    启动 Agent 服务
python main.py cli        连接到运行中的 Agent
python main.py dashboard  单独启动 Dashboard
```

长期部署时，Agent 主服务应该交给进程管理器，而不是手动开终端运行。

可以选择：

- `systemd`
- Docker Compose
- supervisor
- tmux 只适合临时调试，不适合生产

进程管理要保证：

- 开机自启。
- 崩溃自动拉起。
- 标准输出和错误输出被收集。
- 工作目录固定。
- 环境变量固定。
- 使用固定 config 和 workspace。
- 停止时发送 SIGTERM，让服务优雅退出。

项目里 `serve()` 已经监听 `SIGINT` 和 `SIGTERM`，收到信号后会取消 runtime task 并进入 shutdown 流程，这对 systemd/Docker 都是必要基础。

### 2. 运行时任务管理

主服务启动后，不是只有一个循环，而是多个后台任务同时运行。

包括：

- AgentLoop 消费入站消息。
- MessageBus 分发出站消息。
- Scheduler 运行定时任务。
- Dashboard server。
- Memory optimizer。
- Proactive loop。
- MCP 连接池。
- Peer agent poller。
- Telegram / QQ / QQBot channel。
- 插件生命周期。

这意味着长期运行时要关注：

- 某个后台任务异常退出后，整个服务是否会退出。
- 退出时是否关闭 channel、MCP、HTTP client、memory runtime。
- Dashboard 是否能随主服务退出。
- proactive 和 scheduler 是否会重复启动。
- 子进程和外部 agent 是否会残留。

当前 `AppRuntime.shutdown()` 会依次停止 core、IPC、Telegram、QQ、QQBot、memory runtime 和 HTTP 资源，这是一个好的基础。

但生产级还应该补：

- 后台任务健康检查。
- 单个任务异常时的告警。
- MCP/QQBot gateway 断线重连指标。
- 子进程残留检测。
- 关闭超时和强制清理。

### 3. 日志管理

当前项目用 Python logging 输出到 stdout，并降低了 httpx、telegram、apscheduler、openai 等库的日志噪音。

这适合容器和 systemd，因为 stdout 可以被外部系统接管。

部署时要关注：

- 日志是否进入 journald、Docker logs 或集中日志系统。
- 是否有 logrotate，避免磁盘被打满。
- INFO 日志是否足够定位问题。
- DEBUG 日志是否会泄漏 prompt、用户消息、API key。
- 关键错误是否带 session_key、channel、chat_id、tool_name、tick_id。
- Dashboard 高频访问日志是否被降噪。

这个项目里 Dashboard 已经对访问日志做了过滤：普通轮询访问不在 INFO 下大量刷屏，debug 模式才保留。这是长期运行很重要的细节。

### 4. 状态持久化和备份

长期运行 Agent 最重要的数据都在 workspace。

备份至少要覆盖：

```text
config.toml
workspace/sessions.db
workspace/memory/
workspace/proactive.db
workspace/proactive_quota.json
workspace/schedules.json
workspace/mcp_servers.json
workspace/proactive_sources.json
workspace/observe/
插件自己的状态文件
```

其中最重要的是：

- `sessions.db`：会话和消息。
- `memory/MEMORY.md`、`SELF.md`、`RECENT_CONTEXT.md`、`PENDING.md`：markdown 记忆。
- `memory/memory2.db`：语义记忆。
- `memory/consolidation_writes.db`：记忆整理幂等记录。
- `proactive.db`：主动推送状态。
- `observe/observe.db`：诊断 trace。
- `schedules.json`：定时任务。

SQLite 数据库要注意 WAL。

如果直接复制 `.db` 文件，可能漏掉 `.db-wal` 和 `.db-shm`，导致备份不完整。

更稳的方式是：

```text
停止服务后备份整个 workspace
或者使用 sqlite backup API / .backup
或者至少同时复制 db、db-wal、db-shm
```

备份策略建议：

- 每日自动备份 workspace。
- 保留最近 7 天和每周快照。
- 备份前记录当前 git commit、配置摘要和版本号。
- 备份加密，因为里面有用户消息和长期记忆。
- 定期做恢复演练，不只是生成备份文件。

### 5. 升级和回滚

升级 Agent 服务不能只 `git pull` 后重启。

因为项目有：

- SQLite schema。
- 插件状态。
- memory engine 存储。
- proactive 状态。
- session 表结构。
- 前端 dashboard bundle。
- MCP 配置和外部子进程。

升级前应该：

1. 记录当前代码版本。
2. 停止服务或进入维护状态。
3. 备份 config 和 workspace。
4. 更新代码和依赖。
5. 运行测试或 smoke test。
6. 启动服务。
7. 检查 channel、Dashboard、memory、proactive、scheduler 是否正常。
8. 发现问题时回滚代码和 workspace。

如果 schema migration 是自动执行的，回滚更要谨慎：旧代码可能读不了新 schema。

所以生产级应该补充：

- workspace/schema 版本号。
- 数据库 migration 记录。
- 升级前自动备份。
- 回滚脚本。
- smoke test 命令。
- 插件兼容性检查。

### 6. 配置和密钥管理

长期部署时，API key、bot token、client_secret 不应该明文随代码提交。

建议：

- `config.toml` 不进 git。
- 密钥用环境变量。
- systemd EnvironmentFile 或 Docker secrets 管理密钥。
- 限制 config 和 workspace 文件权限。
- Dashboard 不展示完整密钥。
- 日志不打印 API key、token、Authorization header。

项目当前支持 `${ENV_VAR}` 插值，这是基础能力。

但生产级还可以增加：

- 配置 doctor。
- secret 脱敏日志。
- 必填配置检查。
- 不同环境配置 overlay。

### 7. 外部依赖健康

长期运行 Agent 依赖很多外部系统：

- LLM provider。
- embedding provider。
- Telegram Bot API。
- QQ/NapCat。
- 官方 QQBot gateway。
- MCP server。
- Peer agent。
- 网络和 DNS。

这些依赖都会失败。

因此部署时要关注：

- LLM 请求超时和重试。
- embedding 失败时是否降级关键词检索。
- Telegram polling conflict。
- QQ WebSocket 断开重连。
- QQBot token 过期和 gateway reconnect。
- MCP server 掉线后的工具可见性。
- Peer agent 子进程健康检查。
- proactive 数据源失败时是否影响其他来源。

长期服务需要可观测这些依赖，而不是失败后只能等用户反馈“机器人没反应”。

### 8. 安全和权限

长期运行还要控制副作用。

需要关注：

- shell 工具是否限制工作目录。
- 高风险工具是否需要确认。
- 插件能否访问 workspace 和 memory。
- Dashboard 是否有认证。
- proactive 是否会给错误 channel 推送。
- QQ/Telegram 白名单是否配置正确。
- MCP server 是否可信。
- peer agent 是否有独立权限边界。

这些不是“上线以后再说”的问题，因为 Agent 一旦长期运行，就会持续拥有外部操作能力。

### 项目里的证据

从项目代码看，已经具备一些长期运行基础：

- 主入口支持 init、setup、gateway、dashboard、cli 等模式。
- 服务监听 SIGINT/SIGTERM，支持优雅退出。
- AppRuntime 管理 core、channel、scheduler、Dashboard、proactive、memory optimizer 等后台任务。
- shutdown 会关闭 channel、memory runtime、HTTP resources、MCP、peer poller 等资源。
- workspace 把 session、memory、proactive、observe、schedule、MCP 等状态集中管理。
- Dashboard 提供运行时诊断和手动维护入口。
- Docker debug 目录提供了容器调试和 profile workspace 的思路。
- observe 插件把 turn、retrieval、memory write 写入数据库，便于长期排查。

### 当前不足

如果按生产级长期服务看，还缺一些能力：

- 没有内置 systemd unit 或生产 Docker Compose。
- 没有统一健康检查接口。
- Dashboard 默认没有认证。
- 没有统一备份/恢复命令。
- 没有 workspace 版本和 migration 记录。
- 没有明确的日志轮转和敏感字段脱敏策略。
- 子任务、后台任务和外部 agent 的持久化恢复还不完整。
- channel adapter 的健康状态没有统一汇总到 Dashboard。

这些不足不代表项目不能用，而是说明它还处在“可长期运行的个人 Agent”到“生产级 Agent 服务”的中间阶段。

### 推荐上线清单

如果我要部署它，我会准备这样的 checklist：

```text
启动：
  init workspace
  配置 config.toml
  使用 systemd 或 Docker Compose 启动
  固定 --config 和 --workspace

安全：
  Dashboard 只监听 127.0.0.1 或加反代认证
  Telegram/QQ 白名单配置
  API key 用环境变量
  workspace 权限收紧

日志：
  stdout 接入 journald/Docker logs
  配置 logrotate
  关键错误包含 session_key 和工具信息

备份：
  每日备份 config + workspace
  SQLite 使用安全备份方式
  备份加密
  定期恢复演练

升级：
  停服或维护模式
  备份
  更新代码和依赖
  跑 smoke test
  检查 channel、Dashboard、memory、proactive
  保留回滚路径
```

### STAR 法则思考

**Situation 情景：**

这个 Agent 项目如果长期运行，会同时处理用户消息、工具调用、记忆写入、主动推送、定时任务、插件状态和外部依赖连接。任何一个环节出问题都可能影响用户体验或造成状态污染。

**Task 任务：**

需要把它从“本地可运行程序”部署成“可守护、可观测、可备份、可升级、可回滚”的长期服务。

**Action 行动：**

部署时使用 systemd 或 Docker Compose 管理进程，固定 config 和 workspace；利用信号处理和 shutdown 流程做优雅退出；把 stdout 日志接入系统日志；围绕 workspace 做定期备份；升级前先备份并跑 smoke test；Dashboard 只允许受保护访问；对 channel、MCP、provider、proactive、scheduler 做健康检查和告警。

**Result 结果：**

这样 Agent 服务即使长期运行，也能在崩溃、重启、升级、外部依赖失败和数据恢复场景下保持可控，不会因为一次部署或一次异常导致会话、记忆或主动状态不可恢复。

### 面试总结

可以这样回答：

```text
如果把这个项目部署成长期运行的 Agent 服务，我会把重点放在进程守护、状态持久化、日志、备份和升级回滚上。进程应该交给 systemd 或 Docker Compose，而不是手动开终端；服务收到 SIGTERM 要优雅关闭 channel、MCP、HTTP client、memory runtime 和 Dashboard。状态数据集中在 workspace，所以备份要覆盖 config、sessions.db、memory、memory2.db、proactive.db、observe.db、schedules 和插件状态；SQLite 备份要注意 WAL。日志要进入 journald 或容器日志，并控制敏感信息。升级前先备份，升级后跑 smoke test，出问题能回滚代码和 workspace。Dashboard 和高风险工具也必须做访问控制，不能裸露公网。
```

### 可以补充到简历/面试里的亮点

- 能把 Agent 从 demo 视角提升到长期服务运维视角。
- 明确区分代码、配置、workspace、日志和外部依赖。
- 能指出 SQLite/WAL、workspace 备份、Dashboard 保护、优雅退出等真实部署问题。
- 能承认当前项目的生产化缺口，并给出可执行改进路线。

## Q81: 用户撤回消息、删除消息或纠正事实时，session history、memory 和 observe trace 应该如何处理？

### 问题

面试官可能会问：

```text
如果用户撤回消息、删除消息，或者说“我刚才说错了”，系统里的 session history、长期记忆和 observe trace 应该怎么处理？是都直接删除吗？
```

### 回答

不能简单地“哪里有就全删掉”。

这三个层次的职责不同：

```text
session history：对话事实记录
memory：被 Agent 用来推理的长期知识
observe trace：运行时审计和调试证据
```

因此处理用户撤回、删除或纠错时，要按语义分开：

- 对话历史可以删除或标记。
- 长期记忆应该失效、覆盖或恢复旧版本。
- observe trace 通常应该保留审计记录，但可以做脱敏或标记。

### 1. 用户撤回消息时怎么处理

撤回更接近“上一轮对话不应该继续影响系统”。

理想处理是：

```text
删除上一轮 user/assistant 消息
回滚 session 的 consolidation cursor
找到由这轮消息写入的 memory
把相关 memory 标记为失效或恢复旧版本
写一条审计记录说明发生了 undo
```

项目里已经有 `plugin_undo` 插件，支持 `/undo` 撤销上一轮被动对话。

它做了几件关键事：

- 找到最近一轮真实用户消息和对应 assistant 回复。
- 删除这一轮相关 session messages。
- 如果前面有 context frame，也一起处理。
- 调整 `last_consolidated`，避免 memory consolidation 游标错位。
- 根据被删除消息 id 找相关 memory source。
- 调用 memory engine 的 undo 能力，让记忆失效或恢复。

这个设计比只删 session 消息更完整。

因为如果只删聊天记录，但长期记忆还保留，Agent 后续仍然可能基于被撤回内容回答。

### 2. 用户删除消息时怎么处理

删除消息有两种语义：

```text
用户只是清理聊天界面
用户要求这条消息不再被系统使用
```

这两者要区分。

如果只是 UI 层清理，可以删除 session message，但最好不自动删除 observe trace，因为 trace 是系统运行证据。

如果是隐私删除或“不要再使用这条信息”，则应该：

- 删除或隐藏 session message。
- 删除或失效由这条消息衍生出来的 memory。
- 从检索索引中移除相关向量。
- 对 observe trace 做脱敏或受控删除。
- 记录一条删除审计，说明哪些数据被处理。

项目的 Dashboard 已经支持删除 session、删除 message、批量删除 message、删除 memory。

但从工程完整性看，还需要把它们做成一条更明确的“级联删除/隐私删除”流程，而不是让用户手动分别删三处。

### 3. 用户纠正事实时怎么处理

纠正事实不应该物理删除旧记忆，而应该做 supersede。

例如用户说：

```text
我刚才说错了，我不是在上海，我现在在杭州。
```

系统应该：

- 写入新事实：“用户现在在杭州”。
- 找到旧事实：“用户在上海”。
- 将旧事实标记为 superseded。
- 保留替换关系，方便追溯为什么旧事实不用了。
- 后续 retrieval 默认只召回 active memory。

项目里的 memory2 已经有 `status` 字段，支持 `active` 和 `superseded`。

记忆写入逻辑里也有 supersede 思路：

- 新偏好、新程序性规则、新 profile/status 可能覆盖旧项。
- post-response worker 会检测用户明确否定旧行为或旧事实的情况。
- memory store 能把旧 item 标记为 superseded。
- replacement 表可以记录旧 item 和新 item 的关系。

这是合理的，因为纠错不是“从没发生过”，而是“旧知识已经不应该被用于当前推理”。

### 4. observe trace 应该怎么处理

observe trace 不应该默认跟着 session/message 一起物理删除。

原因是 observe trace 是调试和审计证据，它回答的是：

```text
当时系统为什么这么回答？
当时召回了哪些记忆？
当时写入了哪些 memory？
当时用了哪些工具？
```

如果每次用户撤回都把 trace 删除，系统就失去排查能力。

更合理的是分级处理：

- 普通撤回：trace 保留，并记录 undo 事件。
- 普通纠错：trace 保留，memory write trace 记录 supersede。
- 隐私删除：trace 中敏感字段脱敏，必要时删除原文内容，但保留结构化审计。
- 合规删除：按用户要求和产品政策执行物理删除，但要有内部删除审计。

也就是说，observe trace 的默认策略应该是“可审计、可脱敏、可按策略删除”，而不是简单全删。

### 三层处理原则

可以总结成：

```text
session history 管对话可见历史
memory 管未来推理是否使用
observe trace 管过去行为是否可解释
```

因此：

- 撤回：重点是 undo 本轮影响。
- 删除：重点是权限和隐私语义。
- 纠错：重点是 supersede，而不是物理删除。
- 审计：重点是保留系统行为证据，同时保护隐私。

### 项目里的证据

从代码看：

- `plugins/plugin_undo/plugin.py` 已经实现 `/undo`，会删除上一轮消息并调用 memory undo。
- `SessionStore` 支持删除 session、删除 message、批量删除 message，并能更新 session 游标。
- `memory2.store` 有 `status` 字段，支持 `active` / `superseded`。
- memory store 支持 `mark_superseded`、`mark_superseded_batch`、replacement 记录和 dashboard 更新。
- Dashboard 支持修改、删除 session/message/memory。
- observe 插件记录 turn、retrieval、memory write，是事后审计的重要来源。

### 设计取舍

物理删除的优点是简单、彻底。

但缺点也明显：

- 很难解释历史行为。
- 很难恢复误删。
- 可能破坏 consolidation cursor。
- 可能让 memory replacement 关系断裂。
- 可能让 observe trace 和 session/memory 对不上。

supersede/失效的优点是：

- 旧事实不会再参与推理。
- 仍然能追溯为什么旧事实失效。
- 支持恢复和审计。
- 更适合“用户纠正事实”这种语义。

所以工程上应该优先用：

```text
撤回 = undo 影响
纠错 = supersede 旧记忆
隐私删除 = 受控物理删除 + 脱敏审计
```

### 可以改进的地方

- 增加统一的“隐私删除”命令，级联处理 session、memory、observe。
- 给 observe trace 增加脱敏/擦除策略，而不是只保留原文。
- memory undo 应记录更完整的 undo audit，包括 affected_ids、restored_ids、source message ids。
- Dashboard 删除 message 时提示是否同步处理相关 memory。
- 对 memory replacement 提供更清晰的可视化，让用户看到“旧事实为什么被覆盖”。
- 对撤回和删除操作增加二次确认，避免误删关键历史。

### STAR 法则思考

**Situation 情景：**

Agent 会把用户对话转化为长期记忆，并把推理过程写入 observe trace。如果用户撤回、删除或纠正事实，系统不能只改聊天记录，否则旧记忆仍可能继续影响回答。

**Task 任务：**

需要设计一套数据一致性策略，让 session history、memory 和 observe trace 在用户撤回、删除、纠错时各自按职责处理。

**Action 行动：**

将三层职责拆开：session 负责对话记录，memory 负责未来推理使用，observe 负责审计和诊断。撤回时删除本轮消息并回滚相关 memory；纠错时写入新事实并 supersede 旧事实；隐私删除时再做受控物理删除和 trace 脱敏。

**Result 结果：**

这样既能尊重用户撤回和纠错，又不会让系统失去可解释性。旧信息不会继续污染回答，关键审计链路也能保留下来用于排查和恢复。

### 面试总结

可以这样回答：

```text
我不会把撤回、删除、纠错都简单理解成物理删除。session history、memory、observe trace 的职责不同：session 是对话记录，memory 是未来推理依据，observe 是系统行为证据。撤回上一轮时，应该删除对应 user/assistant 消息，回滚 consolidation 游标，并让相关 memory 失效或恢复旧版本；用户纠正事实时，应该写入新事实并 supersede 旧记忆，而不是直接删掉旧记录；observe trace 默认应保留审计价值，但可以对隐私字段做脱敏或按合规要求删除。这样才能同时保证用户控制权、记忆一致性和系统可解释性。
```

## Q82: 长期记忆为什么需要失效、覆盖或 supersede 机制？它和物理删除分别适合什么场景？

### 问题

面试官可能会问：

```text
长期记忆里如果出现旧事实、错误事实或被用户纠正的事实，为什么不能直接删除？为什么需要失效、覆盖或 supersede 机制？它和物理删除分别适合什么场景？
```

### 回答

长期记忆不是普通数据库里的静态资料，而是 Agent 未来推理会使用的“知识层”。

因此长期记忆不能只做简单的增删改查。

它至少需要三种处理方式：

```text
失效：旧记忆不再参与推理
覆盖：新记忆替代旧记忆
supersede：保留旧记忆，但标记它已被新事实取代
物理删除：彻底移除记录和索引
```

其中 supersede 是长期记忆系统里非常关键的设计。

### 为什么不能只物理删除

物理删除看起来简单，但在 Agent 记忆里有几个问题。

第一，删除会破坏解释链。

如果 Agent 昨天根据“用户在上海”回答了问题，今天用户纠正“我现在在杭州”，旧记忆如果被直接删除，后面就很难解释昨天为什么那么回答。

第二，删除会破坏替换关系。

用户纠错时，系统需要知道：

```text
旧事实是什么
新事实是什么
为什么旧事实不用了
什么时候发生了替换
替换来源是哪轮对话
```

如果直接删旧记忆，这条关系就没了。

第三，删除容易误伤。

有些记忆不是错了，而是过期了。

例如：

```text
用户正在准备面试
用户面试已经结束
```

第一条不一定是错误事实，只是状态变化了。直接删除会丢掉时间线；标记为 superseded 更合理。

第四，删除不利于恢复。

如果系统误判一条记忆过期，物理删除后恢复成本很高；如果只是 supersede，还可以在 Dashboard 或工具里恢复为 active。

### supersede 解决什么问题

supersede 解决的是“旧记忆不应继续参与推理，但仍要保留历史和关系”的问题。

它适合这些情况：

- 用户纠正旧事实。
- 用户偏好发生变化。
- 用户状态发生变化。
- 程序性规则被新规则替代。
- 旧记忆与新记忆高度相似但新记忆更准确。
- Agent 发现旧行为建议是错的。

例如：

```text
旧记忆：用户喜欢英文回答
新记忆：用户希望后续全部用中文解释
```

这时不应该让两条记忆同时 active，否则 retrieval 可能把两条都召回，导致模型混乱。

更好的做法是：

```text
旧记忆 status = superseded
新记忆 status = active
替换关系记录 old_id -> new_id
```

后续默认检索只召回 active 记忆。

### 失效、覆盖、supersede、物理删除的区别

可以这样区分：

```text
失效：
  让旧记忆不再参与未来推理。
  适合过期、低质量、被否定但仍需保留证据的记忆。

覆盖：
  新事实替代旧事实。
  适合同一主题的偏好、状态、程序性规则变化。

supersede：
  覆盖的一种可追溯实现。
  旧记忆保留但状态变为 superseded，新记忆保持 active。

物理删除：
  从存储和索引里彻底移除。
  适合隐私删除、误写垃圾数据、用户明确要求删除、合规删除。
```

简单说：

```text
业务语义变化：优先 supersede
隐私和合规要求：使用物理删除
系统误写低质内容：可以删除或标记失效
旧事实仍有历史价值：不要直接删
```

### 项目里的设计证据

这个项目已经具备 supersede 的基础设施。

在 `memory2` 存储里：

- memory item 有 `status` 字段。
- 默认状态是 `active`。
- 旧记忆可以被标记为 `superseded`。
- 检索默认过滤掉 superseded 记忆。
- Dashboard 可以按 status 查看和修改记忆。
- 相似记忆覆盖时会把旧 item 标为 superseded。
- replacement 记录可以保存旧 item 和新 item 的关系。

在记忆写入逻辑里：

- 显式记忆写入可以根据相似度覆盖旧 preference/procedure/profile。
- profile 里的 status/purchase 类事实会按类别考虑覆盖。
- post-response worker 会检测用户是否明确否定旧事实或旧行为。
- 用户纠正旧行为时，可以触发旧条目 supersede。

这说明项目不是把 memory 当成简单向量库，而是把它当成可演化的知识系统。

### 为什么 retrieval 默认不应该召回 superseded 记忆

长期记忆最终会进入 prompt。

如果已经过期或被覆盖的记忆还被召回，会导致模型混乱。

例如：

```text
active: 用户现在在杭州
superseded: 用户在上海
```

如果两条都进入 prompt，模型可能回答得含糊，甚至错误引用旧事实。

所以默认检索应该只召回 active。

只有在这些场景下才应该查看 superseded：

- Dashboard 审计。
- 用户问“我之前是不是说过什么”。
- debug memory 冲突。
- 恢复误失效记忆。
- 分析替换关系。

### 物理删除适合什么场景

物理删除适合更强的语义：

1. **用户明确要求删除隐私**

例如：

```text
删除我刚才发的身份证号，不要保留。
```

这时不应该只 supersede，而应该从 session、memory、embedding、observe 可识别原文中删除或脱敏。

2. **系统误写垃圾记忆**

例如空内容、解析错误、明显 hallucination 产生的记忆，可以物理删除。

3. **合规删除**

如果产品有隐私政策或用户数据删除要求，需要物理删除。

4. **重复数据清理**

大量完全重复、没有历史价值的记忆，可以物理删除或合并。

5. **测试数据清理**

临时测试 workspace 或测试 session 中的数据可以直接删。

### 设计取舍

supersede 的优点：

- 保留历史。
- 支持审计。
- 支持恢复。
- 不污染未来检索。
- 能解释为什么旧事实不用了。

supersede 的缺点：

- 存储会增长。
- 查询逻辑要过滤状态。
- UI 要能展示 active/superseded。
- 替换关系需要维护。

物理删除的优点：

- 干净。
- 节省存储。
- 符合隐私删除语义。

物理删除的缺点：

- 不可追溯。
- 不易恢复。
- 可能破坏解释链。
- 容易和 observe trace、source_ref 断开。

所以成熟的 Agent 记忆系统应该同时支持两者，而不是只选一个。

### 可以改进的地方

- 在 Dashboard 中提供“查看替换链路”，展示 old memory -> new memory。
- 给 superseded memory 增加 reason 字段，例如 correction、preference_change、duplicate、manual。
- 增加 memory conflict detector，自动发现同一 scope 下冲突 active 记忆。
- 增加记忆恢复入口，把误 supersede 的条目恢复 active。
- 对物理删除增加级联清理，包括向量索引、replacement、observe 脱敏。
- 给用户提供自然语言命令，例如“忘掉这条记忆”“这条不对，改成...”。

### STAR 法则思考

**Situation 情景：**

Agent 长期运行后会积累大量用户事实、偏好、状态和程序性规则，这些记忆会不断变化、过期或被用户纠正。

**Task 任务：**

需要让长期记忆既能保持最新、避免旧事实污染回答，又能保留历史替换关系，支持审计和恢复。

**Action 行动：**

项目通过 memory status 区分 active 和 superseded。新事实写入时，可以把旧事实标记为 superseded，并记录替换关系；retrieval 默认只召回 active 记忆；只有隐私删除、垃圾数据或合规删除场景才使用物理删除。

**Result 结果：**

这样 Agent 可以随着用户事实和偏好的变化持续更新认知，同时避免旧记忆继续影响推理；需要排查时也能看到旧事实为什么被替代，而不是只剩下不可解释的删除结果。

### 面试总结

可以这样回答：

```text
长期记忆不能只靠物理删除，因为很多旧记忆不是“从未发生过”，而是被新事实覆盖了。比如用户从上海搬到杭州，旧事实有历史价值，但不应该再参与当前推理。所以更合理的是 supersede：旧记忆保留但标记为失效，新记忆保持 active，检索默认只召回 active。物理删除适合隐私删除、合规删除、明显垃圾数据和测试数据清理。这个项目里 memory item 有 active/superseded 状态，写入逻辑也会根据相似度和用户纠错覆盖旧记忆，这说明它把 memory 当成可演化知识层，而不是简单向量库。
```

## Q83: 工具副作用如何治理？比如发消息、写文件、调用外部服务失败后如何补偿？

### 问题

面试官可能会问：

```text
Agent 调工具不只是读数据，还可能发消息、写文件、调用外部服务。工具副作用应该怎么治理？如果发消息失败、写文件失败、外部服务调用一半失败，系统应该如何补偿？
```

### 回答

工具副作用治理的核心是：不能把工具调用当成普通函数调用。

因为很多工具会改变外部世界：

- 发消息给用户。
- 写文件。
- 删除文件。
- 修改 session。
- 写 memory。
- 发起网络请求。
- 调 MCP 工具。
- 启动后台任务。
- 调用外部 Agent。
- 修改 proactive ACK 状态。

这些操作一旦执行，不能简单靠“重试一下”解决。

所以要从三个阶段治理：

```text
调用前：权限、确认、参数校验、幂等键
调用中：超时、错误收敛、隔离、事务边界
调用后：审计、状态提交、补偿、重试或回滚
```

### 1. 调用前治理

调用前要先判断这个工具有没有副作用。

项目的工具注册里已经有 `risk` 元数据，例如：

- `read-only`
- `write`
- `external-side-effect`

这说明工具系统已经开始区分风险等级。

调用前应该做：

- 工具是否对当前 session 可见。
- 工具是否被 tool_search 解锁。
- 工具风险是否允许当前上下文调用。
- 参数是否完整。
- 目标 channel/chat_id 是否正确。
- 文件路径是否在允许范围内。
- 是否需要用户确认。
- 是否需要幂等 key，避免重复执行。

例如发消息工具不能只看模型给了 `message`，还要确认：

```text
channel 是否已注册
chat_id 是否有效
message/file/image 至少有一个
该 channel 是否支持对应发送类型
当前调用是否来自允许的主动链路
```

项目里的 `MessagePushTool` 已经做了一部分：

- channel 未注册会返回错误。
- message/file/image 都为空会返回错误。
- channel 不支持 file/image 会返回说明。
- 发送异常会捕获并返回失败信息。

但如果是生产级，还应该增加更明确的权限和审计。

### 2. 调用中治理

工具执行过程中要避免异常炸穿主链路。

项目里 `ToolRegistry.execute` 会捕获工具异常，并返回统一错误文本。

工具 hook 执行器也会处理：

- pre hook 抛异常时返回 error。
- pre hook deny 时不执行真实工具。
- 工具执行失败后可触发 error hook。
- post hook 在部分观察场景下可以 fail-open。

这说明工具调用不是裸调用，而是有一个执行治理层。

调用中还应该关注：

- 超时控制。
- 外部服务重试。
- 速率限制。
- 网络错误分类。
- 后台任务和前台任务分离。
- 取消时是否能杀掉子进程。
- 大输出是否截断。
- 多模态结果是否结构化。

例如 shell 工具这种高风险工具，项目里已经有：

- 后台执行机制。
- 超时后转后台。
- 任务停止。
- 日志文件清理。
- shell safety 插件。
- shell restore 插件把危险删除改成移动到恢复目录。

这些都属于副作用治理。

### 3. 调用后治理

调用后最重要的是：只有确认副作用成功后，才能提交对应状态。

比如 proactive 推送：

```text
消息真正发出成功
  -> 记录 last_proactive_at
  -> 记录 delivery
  -> ACK cited content

消息发送失败
  -> 不应该 mark delivery
  -> 不应该把 cited content 当成成功处理
  -> 应保留候选内容下次重试机会
```

这就是副作用提交顺序问题。

如果顺序反了：

```text
先写状态，再发消息
```

一旦消息发送失败，系统就会以为内容已经推过，用户却没收到。

项目前面 Q60 已经提到：主动发送失败时不应错误标记引用内容为成功处理。当前实现里也有一些残余问题，比如 proactive session 可能先落再发送，这是后续要改进的点。

### 4. 不同副作用的补偿策略

不同副作用不能用同一种补偿方式。

### 发消息失败

发消息是外部不可事务化操作。

补偿策略：

- 发送失败时不要记录 delivery。
- 不更新 last_proactive_at。
- 不对 cited content 做成功 ACK。
- 可以记录失败 trace。
- 可以短期冷却，避免立即重复轰炸。
- 可让下轮重新处理候选。
- 如果是用户主动请求，可以返回“发送失败”。

发消息不能随便自动重试太多次，因为可能造成重复消息。

### 写文件失败

写文件适合做原子写和备份。

补偿策略：

- 写临时文件，再 rename。
- 修改前备份旧文件。
- 失败时保留旧文件。
- 删除改成移动到恢复目录。
- 记录操作日志。
- 限制路径在 workspace 或允许目录内。

项目里的 shell restore 插件就是一个例子：把危险删除改成移动到恢复目录，这比直接执行 `rm` 更可恢复。

### 写 memory 失败

memory 写入失败不能影响主回复已经发送的事实，但要记录。

补偿策略：

- post-response memory 写入失败写 observe trace。
- consolidation 使用 source_ref 做幂等，避免重启重复写。
- PENDING 写入前可以做 snapshot。
- memory2 通过 source_ref 和 consolidation_events 避免重复消费。
- Dashboard 提供手动修复入口。

### 外部服务调用失败

外部服务包括 MCP、web fetch、embedding provider、LLM provider、peer agent。

补偿策略：

- 超时和重试。
- 熔断和降级。
- 返回结构化错误给模型。
- 不把失败伪装成成功。
- 对只读查询可以安全重试。
- 对写操作必须幂等或人工确认。

例如 embedding 失败时，项目里 recall memory tool 有关键词兜底；MCP 工具失败时会进入工具错误结果，而不是让整个 Agent 崩溃。

### 5. 幂等设计

副作用治理里最重要的是幂等。

因为模型可能重复调用工具，网络可能重试，服务可能重启。

常见幂等键包括：

- message id。
- source_ref。
- delivery_key。
- task_id。
- tool_call_id。
- session_key + seq。
- external request id。

项目里已经有不少幂等思路：

- session message 有 id 和 seq。
- memory consolidation 用 source_ref 避免重复写。
- proactive delivery 用 delivery_key 去重。
- shell background task 用 task_id 管理。
- observe trace 记录 turn 和 tool chain。

这些都是长期 Agent 服务必须有的基础。

### 6. 审计和可观测

副作用工具必须可审计。

至少要记录：

- 谁触发的。
- 哪个 session。
- 哪个 channel/chat。
- 调了什么工具。
- 参数是什么。
- 最终参数有没有被 hook 改写。
- 成功还是失败。
- 外部返回是什么。
- 是否产生补偿。
- 是否写入了状态。

项目里的 tool chain、ToolCallStarted/Completed、observe trace、Dashboard、plugin audit 都是审计基础。

但高风险副作用还应该更进一步：

- 增加单独 audit log。
- 增加人工确认记录。
- 增加失败补偿记录。
- 增加可重放/不可重放标记。

### 项目里的证据

从项目实现看，已有这些副作用治理基础：

- `ToolRegistry` 有 risk 元数据和统一 execute 错误收敛。
- `ToolExecutor` 支持 pre hook 改参、deny、post hook、error hook 和 trace。
- `MessagePushTool` 统一多 channel 发送，并处理未注册 channel、不支持发送类型和发送异常。
- `MessageBus.dispatch_outbound` 对出站消息失败会重试一次，并尝试降级通知。
- proactive 的 ACK/delivery 设计区分发送成功、post guard fail、discarded 等不同结果。
- `plugin_undo` 支持撤回上一轮对话并处理相关 memory。
- `shell_restore` 把危险删除改成移动到恢复目录。
- `shell_safety` 拦截部分高风险 shell 行为。
- memory consolidation 和 memory2 使用 source_ref 做幂等。

### 设计取舍

副作用治理有一个现实矛盾：

```text
治理越严格，Agent 越安全，但交互越慢
治理越宽松，Agent 越流畅，但风险越高
```

所以要按风险分层：

- 只读工具：可以低摩擦调用。
- 可恢复写操作：可以允许，但要记录和可回滚。
- 外部副作用：要幂等、审计和失败处理。
- 不可逆高风险操作：需要确认或默认禁止。

### 可以改进的地方

- 给每个工具增加明确的 capability 和 side_effect_type。
- 为高风险工具增加用户确认机制。
- 给 message_push 增加 delivery_key，避免重复发送。
- 给所有外部写操作增加幂等 request id。
- 增加统一 audit log，记录高风险工具调用和补偿结果。
- 给 Dashboard 增加副作用操作历史。
- 对工具返回的“部分成功”做结构化表达，而不是只返回字符串。
- 对发消息、写文件、外部服务调用分别定义补偿策略。

### STAR 法则思考

**Situation 情景：**

Agent 会调用各种工具，其中很多工具会产生真实副作用，比如发消息、写文件、修改记忆、调用外部服务或启动后台任务。

**Task 任务：**

需要让工具调用既能扩展 Agent 能力，又不会因为重复调用、失败、异常或不可逆操作导致状态污染和外部副作用失控。

**Action 行动：**

项目通过工具风险等级、统一工具执行器、pre hook 拦截、post hook 记录、message push 统一发送、proactive ACK/delivery、source_ref 幂等、shell safety 和 shell restore 等机制治理副作用。调用前做权限和参数检查，调用中收敛异常，调用后根据真实结果提交状态或执行补偿。

**Result 结果：**

这样工具调用不再是裸函数执行，而是一条可控制、可审计、可补偿的外部交互链路。即使消息发送失败、工具异常或文件操作风险较高，也能尽量避免主链路崩溃和状态错误。

### 面试总结

可以这样回答：

```text
工具副作用不能当普通函数调用处理。我的思路是调用前做风险分级、权限检查、参数校验和必要确认；调用中要有超时、错误收敛和 hook 治理；调用后只有在真实副作用成功后才提交状态。比如 proactive 发消息成功后才能记录 delivery 和 ACK，发送失败就不能把内容标记成已处理。写文件要尽量用备份、原子写或可恢复移动；外部服务调用要区分只读重试和写操作幂等。这个项目里已经有工具风险等级、ToolExecutor hook、MessagePushTool、proactive ACK/delivery、source_ref 幂等、shell safety 和 shell restore，这些都是副作用治理的基础。
```

## Q84: 高风险工具应该如何做权限控制、确认机制和审计记录？

### 问题

面试官可能会问：

```text
Agent 可能会调用 shell、发消息、写文件、删除数据、调用外部服务。你会如何设计高风险工具的权限控制、用户确认和审计记录？
```

### 回答

高风险工具不能只靠 prompt 约束。

因为模型可能误判、工具参数可能被 prompt injection 影响，插件或 MCP 工具也可能带来不可控外部副作用。

所以高风险工具应该有四层治理：

```text
注册时标注风险
运行时控制可见性
执行前做确认或拦截
执行后留下审计记录
```

### 1. 注册时标注风险

每个工具在注册时应该有风险等级。

这个项目的 `ToolRegistry` 已经有 `risk` 元数据，例如：

- `read-only`
- `write`
- `external-side-effect`

这是一切治理的基础。

如果工具没有风险等级，系统就无法区分：

```text
读取文件
写入文件
删除文件
发消息
调用外部服务
启动子进程
```

这些操作的风险完全不同。

更完整的风险模型可以继续细分：

```text
read-only：只读查询
local-write：写本地 workspace
external-read：访问外部 API
external-write：修改外部系统
message-send：给用户或群发消息
filesystem-delete：删除或移动文件
process-exec：执行 shell/子进程
memory-mutate：修改长期记忆
admin-operation：删除 session、清理状态
```

风险越高，默认可见性越低，确认要求越强，审计越详细。

### 2. 运行时控制可见性

高风险工具不应该默认全部暴露给模型。

项目里已有工具可见性机制：

- always-on 工具默认可见。
- deferred 工具需要通过 tool_search 解锁。
- 每个 session 有自己的工具可见性状态。
- tool_search 可以按风险和语义搜索工具。
- subagent/profile 可以限制工具集合。

这比“所有工具都塞进 prompt”安全很多。

高风险工具应该遵循：

```text
默认不可见
需要明确任务意图才能搜索到
搜索结果显示风险
解锁只对当前 session 或当前 turn 生效
子 Agent 默认不继承主 Agent 的高风险工具
```

例如 shell、message_push、delete memory、external-side-effect 工具，都不应该在普通聊天里一直暴露。

### 3. 执行前确认机制

有些工具即使被模型选中，也不应该立即执行。

需要确认的典型场景：

- 删除文件。
- 批量修改文件。
- 发送消息给外部用户或群。
- 删除 session / memory。
- 调用会产生费用的外部服务。
- 启动长时间后台任务。
- 修改系统配置。
- 调用外部 Agent 执行写操作。

确认机制可以分级：

```text
低风险：无需确认
中风险：模型说明意图，用户可打断
高风险：必须用户确认
不可逆风险：默认禁止或 require explicit override
```

确认时要展示：

- 工具名。
- 操作目标。
- 关键参数。
- 影响范围。
- 是否可恢复。
- 预计副作用。

例如：

```text
将删除 workspace/memory/memory2.db 中 12 条记忆。
是否确认？输入 yes 继续。
```

确认不能只让模型自己“确认”，必须来自用户或可信策略。

### 4. hook 拦截和参数改写

项目里的 `ToolExecutor` 和插件 hook 已经提供了治理入口。

pre hook 可以：

- 检查工具名。
- 检查参数。
- 改写参数。
- 返回 deny。
- 添加额外提示。

这很适合做高风险工具策略。

例如：

- shell safety 拦截交互式包管理命令。
- shell restore 把危险删除改成移动到恢复目录。
- tool loop guard 阻止重复工具调用。
- 插件可以基于 channel/session/chat_id 决定是否允许工具。

更完整的做法是增加一个统一的 policy hook：

```text
if tool.risk in high_risk:
    check permission
    check confirmation
    write audit pending record
    allow / deny / require_confirmation
```

### 5. 执行后审计记录

高风险工具必须有审计记录。

审计记录至少包括：

- 时间。
- session_key。
- channel。
- chat_id。
- sender。
- 工具名。
- 风险等级。
- 原始参数。
- hook 修改后的最终参数。
- 是否经过用户确认。
- 执行状态。
- 返回结果摘要。
- 错误信息。
- 是否产生补偿。
- 关联的 tool_call_id / turn_id。

项目里已经有一些审计基础：

- tool_chain 会记录工具调用链。
- ToolCallStarted / ToolCallCompleted 事件可以记录开始和结束。
- ToolExecutor 有 pre/post hook trace。
- observe 插件记录 turn trace。
- Dashboard 可以查看部分工具链路和状态。

但高风险工具还应该有专门的 audit log，而不是只混在普通 turn trace 里。

因为普通 trace 主要用于调试，高风险审计还要支持安全追责和恢复。

### 6. 高风险工具失败后的审计

失败也要记录，而且要比成功更详细。

例如发消息失败，要记录：

- 目标 channel/chat_id。
- 是否已真正发出。
- 是否重试。
- 是否记录 delivery。
- 是否 ACK。

写文件失败，要记录：

- 是否写入了临时文件。
- 是否替换原文件。
- 是否保留备份。
- 是否需要人工恢复。

shell 失败，要记录：

- 命令。
- cwd。
- 退出码。
- stdout/stderr 摘要。
- 是否后台任务。
- 是否被超时终止。

这些记录决定了后续能不能补偿。

### 项目里的证据

从项目看，已有这些基础：

- `ToolRegistry` 保存工具 risk、always_on、source_type、source_name。
- tool_search 可以避免所有工具默认暴露。
- `ToolExecutor` 支持 pre hook、deny、post hook、error hook 和 hook trace。
- shell safety 插件能拦截部分危险 shell 行为。
- shell restore 插件能把危险删除改写成可恢复移动。
- message_push 统一处理跨 channel 发送，并返回失败结果。
- proactive ACK/delivery 体现了“发送成功后再提交状态”的思想。
- observe 和 Dashboard 提供运行时可观测能力。
- subagent/background job 已经有 profile/权限隔离思路。

### 当前不足

如果按生产级高风险工具治理看，还缺：

- 统一的用户确认协议。
- 明确的高风险工具 allowlist/denylist。
- 每个工具的 capability 描述。
- 专门的 audit log 表。
- 工具调用前的 pending confirmation 状态。
- 确认过期机制。
- Dashboard 高风险操作审计页面。
- 对 MCP 工具和插件工具的风险强制声明。
- 高风险工具默认只读或禁用策略。

### 设计取舍

高风险治理的难点是不要把 Agent 变成完全不能用。

如果所有写操作都要确认，体验会很差。

如果全部自动执行，风险又太高。

所以我会采用分层策略：

```text
只读工具：默认允许
workspace 内可恢复写操作：允许，但记录审计
外部副作用：需要更严格权限和幂等
不可逆或外部写操作：需要用户确认
未知来源工具：默认低权限
```

特别是 MCP 和插件工具，不能因为“能被发现”就默认高权限执行。

### 可以改进的地方

- 给 ToolMeta 增加 `requires_confirmation`、`side_effect_type`、`reversible`。
- 增加统一 confirmation manager，支持 pending 确认和确认过期。
- 在 tool_search 结果中展示风险等级和确认要求。
- 增加高风险工具 audit 表，写入 workspace。
- Dashboard 增加高风险操作历史和回滚入口。
- 对外部 MCP 工具默认标记为 `external-side-effect`，除非显式声明只读。
- 对 shell 增加更强策略：默认只允许 workspace 内读写，危险命令 require confirm。
- 对 message_push 增加防误发策略，例如目标确认和 delivery key。

### STAR 法则思考

**Situation 情景：**

Agent 可以调用 shell、文件、消息推送、MCP、插件和外部 Agent 等工具，其中很多工具会造成不可逆或外部可见副作用。

**Task 任务：**

需要设计一套高风险工具治理机制，让 Agent 既能完成真实任务，又不会因为模型误判、prompt injection 或插件风险造成越权操作。

**Action 行动：**

将工具按风险分级，默认限制高风险工具可见性；执行前用 hook 和权限策略检查参数、必要时要求用户确认；执行后记录完整审计，包括原始参数、最终参数、确认状态、执行结果和补偿情况。对 shell、message_push、MCP、插件工具等外部副作用能力使用更严格策略。

**Result 结果：**

这样高风险工具不会因为出现在工具列表里就被随意执行，系统也能在出问题时追溯谁触发了什么操作、是否确认过、最终执行到哪一步，以及是否需要恢复。

### 面试总结

可以这样回答：

```text
高风险工具不能只靠 prompt 约束，必须在工具系统层治理。我会先在注册阶段标注风险等级，比如只读、写入、外部副作用、发消息、执行进程；运行时默认不把高风险工具全部暴露给模型，而是通过 tool_search 和 session 可见性控制。真正执行前，用 hook 或 policy 检查参数和权限，必要时要求用户确认；执行后写审计记录，包含工具名、风险等级、原始参数、最终参数、确认状态、执行结果和错误。这个项目里已经有 ToolRegistry risk、ToolExecutor hook、shell safety、shell restore、message_push 和 observe trace，这些是基础，但还需要补统一确认机制和高风险 audit log。
```

## Q85: 插件或工具出现异常时，系统如何保证主对话链路不被拖垮？

### 问题

面试官可能会问：

```text
插件和工具都是扩展点，也最容易出异常。如果插件初始化失败、hook 报错、工具执行失败、外部服务超时，系统如何保证主对话链路不被拖垮？
```

### 回答

插件和工具是 Agent Runtime 里最容易引入不稳定性的部分。

因为它们可能来自：

- 内置工具。
- 插件工具。
- MCP 外部工具。
- shell / 文件系统。
- 外部 API。
- peer agent。
- proactive 数据源。

所以系统不能假设“工具一定成功、插件一定可靠”，而要把扩展点当成不可信边界来设计。

核心原则是：

```text
核心对话链路要稳定
扩展能力失败要可隔离
错误要进入可观察结果
安全边界失败要 fail-closed
观察型能力失败可以 fail-open
```

### 1. 插件加载失败不能影响启动

插件加载阶段要有隔离。

如果某个插件导入失败、没有注册类、manifest 解析失败、配置读取失败，不应该导致整个 Agent 启动失败。

项目里的插件管理器已经做了类似处理：

- 只加载有 `plugin.py` 的目录。
- 导入失败会记录 warning 并跳过。
- 未注册插件类会跳过。
- manifest 解析失败不会阻塞整个插件系统。
- 插件初始化失败时，会回滚已注册的工具、hook 和 phase module。

这很关键。

因为插件是可选扩展，某个插件坏了，主 Agent 至少应该还能正常回答普通问题。

### 2. 插件初始化失败要回滚

插件初始化失败比导入失败更危险。

因为它可能已经注册了一部分能力：

- 工具。
- tool hook。
- lifecycle module。
- event handler。
- prompt render module。

如果初始化失败后不回滚，会出现半加载状态。

例如：

```text
工具已经注册
hook 也生效
但插件内部资源没初始化
```

这会导致后续工具调用更隐蔽地失败。

所以正确做法是：

```text
记录注册前状态
初始化失败
注销插件实例
注销已注册工具
删除新增 hook
删除新增 phase module
跳过该插件
```

项目里的 PluginManager 已经有这种回滚思路。

### 3. 工具执行失败不能炸穿 AgentLoop

工具执行阶段也要隔离。

如果工具抛异常，AgentLoop 不应该直接崩溃。

项目里的工具注册执行层会捕获工具异常，并返回统一错误文本。

工具执行器也会把 hook 或工具异常收敛成结构化状态：

- `success`
- `error`
- `denied`

这样模型可以看到工具失败结果，然后决定：

- 换一种方式回答。
- 调用其他工具。
- 告诉用户失败原因。
- 停止工具循环。

这比异常直接冒泡更适合 Agent。

### 4. hook 异常要区分 fail-open 和 fail-closed

不是所有 hook 失败都应该同样处理。

可以分两类：

```text
安全型 hook：失败时应该 fail-closed
观察型 hook：失败时可以 fail-open
```

安全型 hook 例如：

- shell safety。
- 高风险工具权限检查。
- 用户确认检查。
- 路径限制。

如果这类 hook 失败，不能默认放行，否则等于安全机制失效。

观察型 hook 例如：

- 写 trace。
- 记录统计。
- 附加调试信息。
- Dashboard 诊断。

如果这类 hook 失败，可以记录错误但不要阻塞主回答。

项目里的工具执行器对 post hook 有 fail-open 设计，这适合观察型插件。

### 5. lifecycle 插件异常要按阶段分级

lifecycle module 的异常也要分级。

不同阶段影响不同：

- before_turn：可能决定是否中断本轮。
- prompt_render：可能影响 prompt。
- before_step：可能影响工具循环。
- after_step：通常偏观察和进度。
- after_turn：可能影响持久化、记忆、出站后处理。

如果所有阶段异常都直接中断，会降低系统可用性。

但如果所有异常都吞掉，又可能掩盖严重一致性问题。

更合理的是：

```text
影响核心输入/安全边界的阶段：严格处理
观察和统计阶段：记录错误后继续
持久化阶段：失败要暴露并告警
```

项目已经通过 phase module 和 event bus 把生命周期拆开，这为分阶段治理提供了基础。

### 6. 外部工具失败要降级

外部工具包括：

- MCP 工具。
- web fetch。
- web search。
- embedding provider。
- peer agent。
- Telegram / QQ 发送。

外部工具失败不能让整个 Agent 不可用。

降级策略包括：

- 连接失败时工具不注册或标记不可用。
- 调用失败时返回工具错误。
- embedding 失败时关键词检索兜底。
- web_fetch 不可用时 proactive 禁用相关能力。
- 出站消息失败时 MessageBus 重试一次，再尝试降级通知。
- proactive 单一数据源失败不影响其他来源。

这样用户至少能得到一个解释，而不是进程崩溃或无响应。

### 7. 主链路和副作用要解耦

主链路应该优先保证：

```text
用户消息能被接收
Agent 能生成回复
回复能尽量发出
失败能被用户看到
```

而像 memory 写入、observe trace、插件统计、Dashboard 面板这类副作用，不应该轻易阻断主回复。

但是也不能完全静默失败。

应该：

- 记录日志。
- 写错误 trace。
- Dashboard 显示异常。
- 必要时给用户提示。
- 对关键持久化失败触发告警。

### 项目里的证据

从项目实现看，已有这些基础：

- PluginManager 导入失败跳过，初始化失败回滚工具、hook、phase module。
- 工具执行层捕获工具异常，返回统一错误文本。
- ToolExecutor 将 hook 和工具错误转为执行结果。
- post hook 有 fail-open 路径，适合观察型插件。
- MessageBus 出站失败会重试一次，并尝试降级通知。
- AppRuntime 启动失败时会 shutdown 已创建资源。
- AppRuntime shutdown 会关闭 core、channel、memory runtime、HTTP resources。
- MCP 连接失败不应该阻塞整个启动。
- proactive 和 memory 测试里已经覆盖部分 fallback 场景。

### 当前不足

如果继续生产化，还应该补：

- 明确的插件异常策略：哪些阶段 fail-open，哪些 fail-closed。
- 插件健康状态面板。
- 工具失败率统计。
- 高风险安全 hook 失败时默认拒绝。
- 插件初始化失败回滚的更完整测试。
- event bus fanout handler 异常隔离策略。
- 统一错误分类：用户错误、模型错误、工具错误、外部依赖错误、系统错误。
- 对观察型副作用失败提供 Dashboard 告警，而不是只打日志。

### 设计取舍

这里最大的取舍是：

```text
稳定性 vs 正确性
可用性 vs 安全性
透明错误 vs 静默降级
```

我的判断是：

- 对安全边界，宁可 fail-closed。
- 对观察统计，倾向 fail-open。
- 对用户可见主链路，尽量返回可理解错误。
- 对持久化一致性，不能静默吞掉。
- 对外部依赖，优先降级而不是崩溃。

这才是长期 Agent Runtime 应该有的异常策略。

### 可以改进的地方

- 给插件和 hook 增加 failure_policy，明确 fail-open / fail-closed。
- 增加工具错误分类和统一错误码。
- Dashboard 增加插件健康页和工具失败率统计。
- observe 记录插件异常和 hook 异常。
- 对高风险 hook 失败默认 deny。
- 对 memory/observe 失败增加后台重试队列。
- 对外部工具增加熔断和退避。
- 给每个 turn 增加“降级原因摘要”，便于面试和排查。

### STAR 法则思考

**Situation 情景：**

Agent 项目的工具和插件能力很强，但也引入了大量不稳定边界。插件可能初始化失败，工具可能抛异常，外部服务可能超时，hook 也可能写错。

**Task 任务：**

需要保证这些扩展点失败时不会拖垮主对话链路，同时又不能把安全错误和一致性错误静默吞掉。

**Action 行动：**

项目通过插件加载失败跳过、初始化失败回滚、工具异常收敛、hook deny/error 状态、post hook fail-open、MessageBus 出站重试和 AppRuntime 统一 shutdown 来隔离异常。设计上进一步区分安全型 fail-closed 和观察型 fail-open。

**Result 结果：**

这样单个插件或工具失败不会让整个 Agent 不可用，用户仍能得到可理解的错误或降级回复；同时关键错误会进入日志、trace 或 Dashboard，方便后续修复。

### 面试总结

可以这样回答：

```text
插件和工具是高风险扩展点，不能假设它们总是可靠。我的设计是把它们当成不可信边界：插件导入失败就跳过，初始化失败要回滚已经注册的工具、hook 和生命周期模块；工具执行失败不能让 AgentLoop 崩溃，而要返回结构化 error 结果，让模型或用户知道失败原因。hook 还要区分安全型和观察型，安全型失败应该 fail-closed，观察型失败可以 fail-open。这个项目里已经有插件初始化回滚、工具异常收敛、ToolExecutor hook trace、MessageBus 出站重试和 AppRuntime shutdown，这些都是保证主链路不被拖垮的基础。
```

## Q86: 如果把这个项目作为 Agent 应用求职项目，应该如何用 STAR 法则讲清楚整体项目？

### 问题

如果把这个项目作为 Agent 应用求职项目，应该如何用 STAR 法则讲清楚整体项目？

### 回答

这个问题的核心不是背代码，而是把项目讲成一个完整的 Agent 工程案例：

```text
我不是做了一个简单聊天机器人，而是围绕长期运行、多渠道接入、记忆、工具、主动触达、插件扩展和可观测性，搭建了一个 Agent Runtime。
```

用 STAR 法则讲时，需要把“为什么做、要解决什么、怎么设计、产生什么结果”讲清楚。

### Situation 情景

普通聊天机器人通常只解决“用户问一句，模型答一句”的问题，但真实 Agent 应用还会遇到更复杂的场景：

- 用户可能来自 CLI、Telegram、QQ 等不同入口。
- Agent 需要记住长期事实、最近上下文和历史偏好。
- Agent 需要调用工具，而工具有权限、失败、副作用和审计问题。
- Agent 不能只被动回答，还要根据 feed、提醒、上下文变化做主动触达。
- 长期运行后，必须能观察每一轮对话、记忆召回、工具调用和主动推送的原因。

所以这个项目的背景可以概括为：

```text
我想把“聊天模型”升级成一个可长期运行、可扩展、可诊断、具备记忆和行动能力的 Agent 应用。
```

### Task 任务

项目要完成的任务不是单点功能，而是一套运行时能力：

- 统一多渠道消息入口，让不同平台的消息进入同一套 Agent 主链路。
- 设计被动对话流程，支持上下文组装、记忆召回、模型推理、工具调用和最终回复。
- 建立长期记忆系统，让 Agent 能沉淀事实、偏好、任务和上下文。
- 建立工具治理系统，让模型可以按需发现和调用工具，同时控制权限和风险。
- 建立插件机制，让新能力可以扩展进系统，而不是改动核心代码。
- 建立主动触达链路，让 Agent 可以在合适时机主动联系用户。
- 建立可观测能力，让每轮行为可以被调试、复盘和评估。

面试里可以把任务表达成：

```text
我的目标是设计一个 Agent Runtime，而不是一个单页面 Demo。它要能支撑多端接入、长期记忆、工具调用、主动推送、插件扩展和运行时诊断。
```

### Action 行动

具体行动可以按模块讲，不需要陷入每个函数细节：

1. 先把系统拆成运行时主链路

把用户消息统一成标准入站消息，再进入 Agent 主流程。主流程负责加载会话、组织上下文、召回记忆、调用模型、执行工具、生成回复，并在结束后写回会话、记忆和观察数据。

2. 用统一消息层隔离不同渠道

CLI、Telegram、QQ 等渠道只负责收发消息和平台适配，不直接耦合记忆、工具和模型逻辑。这样新增渠道时不用重写 Agent 核心。

3. 用记忆系统增强长期上下文

项目把短期会话、长期记忆、最近上下文、任务状态和结构化记忆分开管理。回答前先做检索和注入，回答后再根据需要写入或更新记忆。

4. 用工具注册和工具发现治理能力调用

不是把所有工具一次性暴露给模型，而是通过统一注册、风险等级、工具搜索、可见性控制、执行器和 hook 机制来管理工具调用。

5. 用插件机制保持核心稳定

插件可以注册工具、hook、生命周期模块和 Dashboard 面板。插件失败时需要隔离和回滚，避免扩展能力拖垮主流程。

6. 用主动链路实现“Agent 主动性”

系统通过定时 tick、候选源、兴趣判断、打扰控制、去重、冷却、ACK 和消息推送来决定是否主动联系用户，而不是简单定时群发。

7. 用观察和 Dashboard 支撑工程调试

项目记录对话轮次、工具调用、记忆召回、记忆写入和主动推送过程，让 Agent 的行为可以解释，而不是出现问题只能猜。

### Result 结果

最终结果可以从工程能力和业务价值两方面讲：

- 工程上，它形成了一个比较完整的 Agent Runtime，而不是一次性脚本。
- 架构上，它把渠道、主流程、模型、记忆、工具、插件、主动链路和观察系统拆开，模块边界清晰。
- 能力上，它支持多渠道对话、长期记忆、工具调用、主动推送和运行时诊断。
- 扩展上，新工具、新插件、新渠道、新模型提供方可以在既有边界内接入。
- 面试表达上，它能覆盖 Agent 应用岗位关心的核心能力：上下文工程、RAG、工具调用、插件系统、多端接入、主动智能、可观测性和部署运维。

可以把结果压缩成一句：

```text
这个项目把 LLM 从“问答接口”组织成了一个可长期运行的 Agent 应用框架，重点体现的是 Agent 工程化能力。
```

### 为什么适合作为 Agent 应用求职项目

它适合的原因是：它覆盖的不是单个 Agent 特性，而是多个 Agent 应用必备模块之间的组合关系。

面试官通常会看这些点：

- 你是否理解 AgentLoop，而不是只会调 API。
- 你是否理解上下文如何组织，而不是只会拼 prompt。
- 你是否理解记忆召回如何影响回答，而不是只说用了向量库。
- 你是否理解工具调用的权限和失败处理，而不是只展示 function calling。
- 你是否理解多渠道和 session 隔离，而不是只跑本地 CLI。
- 你是否理解主动推送的打扰控制和去重，而不是简单定时任务。
- 你是否理解可观测性和部署，而不是只做开发期 Demo。

这些点刚好都能在这个项目里找到对应模块。

### 面试时推荐说法

可以这样说：

```text
这个项目的背景是：普通聊天机器人只能被动问答，缺少长期记忆、主动触达、工具治理和多端运行能力。所以我把它作为一个 Agent Runtime 来设计。

我的任务是让它具备长期运行能力：不同渠道可以接入，同一套主流程能处理消息；系统能组织上下文和召回记忆；模型可以安全调用工具；插件可以扩展能力；主动链路可以判断什么时候联系用户；Dashboard 可以观察每轮行为。

具体做法上，我把系统拆成消息层、Agent 主流程、模型提供层、记忆系统、工具系统、插件系统、主动触达系统和可观测系统。这样每个模块都有清晰职责，新增能力也不会直接破坏核心链路。

结果是，这个项目不只是一个 chatbot，而是一个具备记忆、工具、主动性、多渠道和可诊断能力的 Agent 应用框架。它能体现我对 Agent 工程化的理解，包括上下文工程、RAG、工具治理、插件扩展、主动推送和运行时可观测性。
```

### 设计取舍

这个项目作为求职项目，也要主动讲清楚取舍：

- 它的优势是模块覆盖完整，适合展示 Agent Runtime 的整体理解。
- 它的风险是模块较多，如果只泛泛介绍，面试官会觉得不够深入。
- 所以讲项目时不能只说“我实现了很多功能”，而要按主链路和模块边界讲。
- 对重点模块，比如 memory、tool、proactive、plugin、observability，要能讲到输入输出、失败场景和改进方向。
- 不需要背所有代码，但必须知道关键模块为什么存在、解决什么问题、和其他模块怎么协作。

### 可以改进的地方

如果继续把它打磨成更强的求职项目，可以补这些材料：

- 一张整体架构图：渠道层、运行时、模型层、记忆层、工具层、主动层、观察层。
- 一张被动对话时序图：用户消息如何变成最终回复。
- 一张主动推送时序图：候选内容如何经过判断、去重、发送和 ACK。
- 一份面试项目讲稿：按 STAR 法则压缩成 2 分钟、5 分钟、15 分钟三个版本。
- 一份技术亮点清单：每个亮点对应业务价值、技术难点和改进方向。
- 一份技术债清单：说明当前项目仍有哪些不足，以及你会如何继续演进。

### STAR 法则思考

**Situation 情景：**

普通 LLM 聊天应用只能完成即时问答，缺少长期记忆、工具治理、主动触达、多渠道运行和可观测能力，难以体现真实 Agent 应用工程复杂度。

**Task 任务：**

需要把项目讲成一个完整 Agent Runtime：它要支持用户从不同渠道进入，同一套主链路处理对话，同时具备记忆、工具、插件、主动推送和诊断能力。

**Action 行动：**

设计上把系统拆成消息接入、Agent 主流程、模型提供、记忆检索、工具治理、插件扩展、主动链路和观察诊断几个层次；每层只承担自己的职责，并通过统一消息、事件、工具注册和运行时配置协作。

**Result 结果：**

项目最终可以作为一个 Agent 工程化案例来讲：它不只是会聊天，还能长期运行、记住用户、调用工具、主动触达、扩展插件并解释自己的运行过程，适合用于展示 Agent 应用岗位所需的系统设计能力。

### 面试总结

可以这样回答：

```text
如果用 STAR 法则讲这个项目，我会先说背景：普通聊天机器人只会被动问答，不具备长期记忆、主动触达、工具治理和多端运行能力。然后说任务：我希望把它设计成一个可长期运行的 Agent Runtime。行动上，我把系统拆成消息接入、对话主流程、模型适配、记忆系统、工具系统、插件扩展、主动推送和可观测诊断几个模块。结果上，它从一个聊天入口升级成了一个具备记忆、行动、主动性、扩展性和诊断能力的 Agent 应用框架。这个项目适合求职展示，因为它覆盖了 Agent 应用工程里最关键的模块，而不只是 API 调用。
```

## Q87: 这个项目最能体现 Agent 工程能力的 3-5 个亮点是什么？每个亮点对应什么业务价值？

### 问题

这个项目最能体现 Agent 工程能力的 3-5 个亮点是什么？每个亮点对应什么业务价值？

### 回答

如果把这个项目拿去面试，最值得讲的不是“我接了某个模型 API”，而是它把 Agent 应用里几个难点做成了相对完整的工程模块。

我建议重点讲 5 个亮点：

```text
1. 可长期运行的 Agent Runtime
2. 多层记忆与检索注入
3. 工具调用治理体系
4. 主动触达链路
5. 插件化和可观测能力
```

这 5 个亮点分别对应不同业务价值。

### 亮点一：可长期运行的 Agent Runtime

这个项目不是把用户输入直接转发给模型，而是设计了一条完整的运行时主链路：

- 多渠道消息统一进入系统。
- 会话和上下文按 session 管理。
- 模型推理、工具调用、记忆召回和回复发送被组织在同一条流程里。
- 对话结束后还会触发记忆写入、观察记录和事件通知。

它体现的工程能力是：

- 能把一次模型调用扩展成一个完整应用运行时。
- 能区分消息层、对话层、模型层、工具层和状态层。
- 能让 CLI、Telegram、QQ 等入口复用同一套核心逻辑。

对应的业务价值是：

```text
同一个 Agent 能稳定运行在多个入口上，后续新增渠道或替换模型时，不需要重写核心业务逻辑。
```

面试时可以这样讲：

```text
我把项目设计成 Agent Runtime，而不是单次问答脚本。消息入口、上下文组织、模型调用、工具执行、回复发送和状态写回都有明确边界，这让系统具备长期运行和多渠道扩展能力。
```

### 亮点二：多层记忆与检索注入

项目里的记忆不是简单把历史消息全塞进 prompt，而是拆成多类信息：

- 当前会话历史。
- 最近上下文。
- 长期事实和偏好。
- 任务状态。
- 可召回的结构化记忆。

回答前，系统会根据当前问题做记忆召回和注入；回答后，又可以把新的事实、偏好或任务进展写回记忆。

它体现的工程能力是：

- 理解上下文窗口不是无限的，必须做选择性注入。
- 理解长期记忆需要召回、排序、过滤和失效机制。
- 理解记忆不是越多越好，错误记忆和过量注入都会影响回答质量。

对应的业务价值是：

```text
Agent 可以持续理解用户，而不是每次都像第一次见面；同时避免把无关历史塞满上下文，降低成本和错误率。
```

面试时可以这样讲：

```text
这个项目的记忆系统重点不是“用了向量库”，而是把会话历史、长期记忆、最近上下文和任务状态分开管理。回答前按需召回，回答后再更新记忆，这样 Agent 才能在长期使用中保持连续性。
```

### 亮点三：工具调用治理体系

普通 function calling 往往只是让模型看到一批工具，然后根据模型输出执行。这个项目更强调工具治理：

- 工具先进入统一注册体系。
- 不同 session 有不同工具可见性。
- 模型可以通过工具搜索发现更多工具，而不是一次性暴露所有工具。
- 工具执行有风险等级、hook、错误收敛和审计空间。
- 外部工具也需要适配成统一格式后再进入系统。

它体现的工程能力是：

- 知道工具调用不是“能调就行”，还要管权限、风险、失败和副作用。
- 知道工具列表过大时，需要工具发现机制，而不是把所有 schema 塞进上下文。
- 知道外部工具协议需要适配层，不能让模型直接面对复杂协议。

对应的业务价值是：

```text
Agent 能安全地使用外部能力，降低误调用、高风险副作用和工具失败导致主链路崩溃的概率。
```

面试时可以这样讲：

```text
我把工具系统当成 Agent 的行动边界来设计。工具需要注册、可见性控制、风险分级、执行拦截和错误处理。这样模型不只是会调用工具，而是在受控环境里行动。
```

### 亮点四：主动触达链路

很多聊天项目只有被动问答，这个项目有主动链路。主动链路不是简单定时发消息，而是会综合候选内容、用户状态、冷却时间、去重和发送结果。

它体现的工程能力是：

- 能把 Agent 从“被动回复”推进到“主动判断是否应该行动”。
- 能处理主动推送里的打扰控制问题。
- 能区分候选内容被看到、被丢弃、发送成功和发送失败。
- 能避免重复推送和错误 ACK。

对应的业务价值是：

```text
Agent 不只是回答问题，还能在合适时机提醒、跟进和主动提供帮助，但不会变成高频打扰用户的通知机器人。
```

面试时可以这样讲：

```text
主动链路是这个项目区别于普通聊天机器人的关键点之一。它会先判断用户是否适合被打扰，再判断内容是否值得推送，并在发送成功后才更新状态，避免重复推送和误处理。
```

### 亮点五：插件化和可观测能力

项目支持插件扩展，插件可以增加工具、hook、生命周期模块和 Dashboard 面板。同时系统也记录对话、检索、工具调用、记忆写入和主动推送过程。

它体现的工程能力是：

- 能把扩展能力放在插件边界内，而不是不断修改核心代码。
- 能让插件失败时尽量不拖垮主链路。
- 能通过 Dashboard 和观察记录解释 Agent 为什么这样回答、为什么召回这些记忆、为什么调用某个工具。

对应的业务价值是：

```text
系统可以持续扩展新能力，并且出现问题时能定位原因，而不是只能靠猜。
```

面试时可以这样讲：

```text
插件化解决的是能力扩展问题，可观测性解决的是长期运行后的诊断问题。Agent 系统越复杂，越需要知道每一轮发生了什么，否则记忆、工具和主动推送出了问题都很难排查。
```

### 设计取舍

这 5 个亮点不能平均用力。面试时应该根据岗位方向取舍：

- 如果岗位偏 Agent 应用开发，重点讲运行时、工具治理、上下文和主动触达。
- 如果岗位偏 RAG，重点讲记忆、召回、排序、注入和评估。
- 如果岗位偏平台工程，重点讲插件化、多渠道、运行状态、部署和可观测。
- 如果面试时间很短，优先讲“Agent Runtime + 记忆 + 工具治理”三个点。

这里的关键是：不要说“我实现了很多模块”，而要说“这些模块分别解决了 Agent 应用的什么真实问题”。

### 更好的表达方式

可以把 5 个亮点整理成面试表格：

| 技术亮点 | 解决的问题 | 业务价值 |
| --- | --- | --- |
| Agent Runtime | 单次模型调用无法支撑长期应用 | 多渠道、可扩展、可长期运行 |
| 多层记忆 | 模型没有稳定长期上下文 | 用户体验连续，回答更个性化 |
| 工具治理 | 工具调用存在权限、失败和副作用风险 | Agent 能安全行动 |
| 主动触达 | 被动聊天不能主动跟进任务 | 提醒、跟进和主动帮助 |
| 插件与可观测 | 能力扩展困难，问题难排查 | 可扩展、可诊断、可运维 |

### STAR 法则思考

**Situation 情景：**

普通聊天应用通常只展示“能和模型对话”，但真实 Agent 应用需要长期运行、记住用户、调用工具、主动触达，并且在出错时能被诊断。

**Task 任务：**

需要从项目中提炼出能证明 Agent 工程能力的亮点，并把每个亮点都对应到明确业务价值，而不是只罗列功能。

**Action 行动：**

可以把项目拆成 5 个亮点来讲：运行时主链路体现系统架构能力，记忆系统体现上下文工程能力，工具治理体现安全行动能力，主动链路体现 Agent 主动性，插件和可观测体现扩展与运维能力。

**Result 结果：**

这样讲项目时，面试官能看到你不是只会调模型接口，而是理解 Agent 应用从 Demo 走向长期服务需要解决的工程问题：状态、上下文、行动、扩展、诊断和风险控制。

### 面试总结

可以这样回答：

```text
这个项目最能体现 Agent 工程能力的亮点有 5 个。第一是可长期运行的 Agent Runtime，它把多渠道消息、上下文组织、模型推理、工具执行和状态写回串成完整主链路，业务价值是支持长期运行和多渠道扩展。第二是多层记忆和检索注入，让 Agent 能持续理解用户，而不是每轮都从零开始。第三是工具治理体系，它把工具调用放进权限、风险、可见性和错误处理边界里，让 Agent 能安全行动。第四是主动触达链路，让 Agent 不只是被动回答，还能在合适时机提醒和跟进。第五是插件化和可观测能力，让系统能持续扩展，并且出现问题时能解释和排查。这些点合在一起，能证明这个项目不是普通 chatbot，而是一个 Agent 工程化项目。
```

## Q88: 面试官如果质疑“这只是套壳聊天机器人”，应该如何解释它和普通 chatbot 的区别？

### 问题

面试官如果质疑“这只是套壳聊天机器人”，应该如何解释它和普通 chatbot 的区别？

### 回答

这个问题要直接回答，不能回避。

可以先承认相似点，再强调差异点：

```text
从用户表面体验看，它确实也是通过对话交互；但从工程结构看，它不是简单把用户输入转发给模型，而是一个围绕消息、上下文、记忆、工具、主动推送、插件和可观测性组织起来的 Agent Runtime。
```

普通 chatbot 的核心路径通常是：

```text
用户输入 -> 拼接 prompt -> 调模型 -> 返回文本
```

这个项目的核心路径更接近：

```text
多渠道消息 -> 会话隔离 -> 上下文组织 -> 记忆召回 -> 模型推理 -> 工具调用循环 -> 回复发送 -> 状态写回 -> 观察记录 -> 后台主动链路
```

两者最大的区别不在“有没有聊天界面”，而在系统是否具备长期状态、行动能力、扩展机制和运行时治理。

### 区别一：普通 chatbot 是单次问答，这个项目是长期运行时

普通 chatbot 通常关注一次请求响应：

- 用户输入一句话。
- 服务端把历史消息和系统提示词拼起来。
- 调模型生成答案。
- 返回结果。

这个项目关注的是长期运行：

- 不同渠道的消息都进入统一主链路。
- 每个会话有独立历史、上下文和工具可见性。
- 对话结束后要写回状态、记忆和观察数据。
- 后台还有主动任务、插件和长期运行状态。

对应差异是：

```text
chatbot 更像接口封装；这个项目更像一个 Agent 应用运行环境。
```

### 区别二：普通 chatbot 主要靠短期上下文，这个项目有多层记忆

普通 chatbot 多数只依赖当前窗口内的历史消息。上下文太长时，要么截断，要么简单总结。

这个项目把上下文拆成多个层次：

- 当前会话消息。
- 最近上下文。
- 长期记忆。
- 任务和 pending 信息。
- 可检索的结构化记忆。

它不是把所有内容塞进 prompt，而是根据当前问题做召回、排序、过滤和注入。

对应差异是：

```text
chatbot 主要“看见当前对话”；这个项目尝试让 Agent 在长期使用中形成连续理解。
```

### 区别三：普通 chatbot 调工具偏功能演示，这个项目强调工具治理

普通工具调用 Demo 常见做法是：

- 把一批 function schema 给模型。
- 模型选择一个工具。
- 服务端执行后把结果返回模型。

这个项目更重视治理：

- 工具需要统一注册。
- 工具可见性按 session 隔离。
- 不一定一次性暴露全部工具，可以通过工具搜索逐步发现。
- 工具执行有风险等级、执行拦截、错误收敛和审计空间。
- 外部工具接入时需要适配成统一工具格式。

对应差异是：

```text
chatbot 的工具调用重点是“能不能调”；Agent Runtime 的工具系统重点是“能否安全、可控、可诊断地行动”。
```

### 区别四：普通 chatbot 是被动响应，这个项目有主动触达

普通 chatbot 基本只在用户发消息时响应。

这个项目有主动链路：

- 后台定时检查候选内容。
- 判断用户当前是否适合被打扰。
- 判断内容是否值得主动推送。
- 做去重、冷却和 ACK。
- 发送失败时避免错误标记为已处理。

对应差异是：

```text
chatbot 等用户来问；这个项目可以在合适时机主动跟进用户关心的事情。
```

### 区别五：普通 chatbot 扩展靠改代码，这个项目有插件和生命周期扩展

普通项目新增能力时，往往直接修改主流程。随着功能增加，主逻辑会越来越乱。

这个项目提供插件扩展点：

- 插件可以注册工具。
- 插件可以参与执行前后的 hook。
- 插件可以扩展生命周期阶段。
- 插件可以提供 Dashboard 面板。
- 插件失败时要能隔离和回滚。

对应差异是：

```text
chatbot 更像固定应用；这个项目更像可扩展平台。
```

### 区别六：普通 chatbot 出问题难解释，这个项目有可观测性

普通 chatbot 出错时，常见问题是很难判断原因：

- 是 prompt 问题？
- 是记忆召回问题？
- 是工具调用问题？
- 是模型输出问题？
- 是主动推送判断问题？

这个项目有观察记录和 Dashboard，可以查看：

- 每轮对话发生了什么。
- 召回了哪些记忆。
- 工具调用是否成功。
- 记忆写入是否发生。
- 主动推送为什么发送或跳过。

对应差异是：

```text
chatbot 常常只能看最终回答；Agent Runtime 必须能解释中间过程。
```

### 面试中要避免的回答

不要这样回答：

```text
它不是套壳，因为我写了很多代码。
```

这个回答没有说服力。代码多不等于工程价值高。

也不要只说：

```text
它有 RAG、有工具、有插件。
```

这仍然像功能堆叠。

更好的表达是：

```text
我把它和普通 chatbot 的区别定义在运行时能力上：是否有长期状态、是否有工具治理、是否有主动行为、是否可扩展、是否可诊断。
```

### STAR 法则思考

**Situation 情景：**

面试官可能会认为很多 Agent 项目只是把大模型 API 包了一层聊天界面，没有真正体现工程设计能力。

**Task 任务：**

需要清楚解释这个项目和普通 chatbot 的边界，让面试官看到它解决的是长期运行、状态管理、行动治理和系统扩展问题。

**Action 行动：**

回答时先承认表面交互都是对话，再从六个维度展开：长期运行时、多层记忆、工具治理、主动触达、插件扩展和可观测性。每个维度都说明普通 chatbot 怎么做、这个项目怎么做、差异带来什么价值。

**Result 结果：**

这样可以把质疑转化成项目亮点：它不是靠聊天界面证明价值，而是靠 Agent Runtime 的系统能力证明价值。面试官也更容易判断你是否理解 Agent 应用和普通聊天封装的本质区别。

### 面试总结

可以这样回答：

```text
如果只看交互形式，它确实也是聊天；但普通 chatbot 通常是用户输入、拼 prompt、调模型、返回文本。这个项目的重点不是聊天界面，而是 Agent Runtime。它有统一消息入口和会话隔离，有多层记忆和检索注入，有受控的工具调用体系，有主动触达链路，有插件扩展和可观测诊断。也就是说，它解决的是长期运行、状态管理、安全行动、主动跟进和问题排查这些 Agent 工程问题。所以我不会把它定义成套壳聊天机器人，而是一个以对话为入口的 Agent 应用框架。
```

## Q89: 这个项目当前最大的技术债和改进方向是什么？如何体现你对工程取舍的理解？

### 问题

这个项目当前最大的技术债和改进方向是什么？如何体现你对工程取舍的理解？

### 回答

这个问题不能回答成“没有技术债”。一个覆盖 Agent Runtime、memory、tool、plugin、proactive、dashboard、多渠道的项目，一定会有技术债。

更好的回答方式是：

```text
这个项目的价值在于模块覆盖完整，能展示 Agent 应用的核心工程能力；但它的技术债也主要来自模块多、链路长、状态多、外部依赖多。当前最应该补的是测试评估体系、权限与副作用治理、主动链路可靠性、记忆质量评估、部署运维标准化。
```

面试时要体现的是：你知道哪些地方目前“能跑”，但还没到“生产级稳定”。

### 技术债一：测试和评估体系还不够系统

Agent 项目最大的问题之一是：功能能跑，不代表行为稳定。

当前项目有很多复杂链路：

- 被动对话链路。
- 工具调用循环。
- 记忆召回和注入。
- 主动推送。
- 插件加载和 hook。
- 多渠道消息适配。

这些链路如果没有系统测试，很容易出现：

- 一次重构破坏工具调用。
- 记忆召回变差但没人发现。
- 主动推送重复发送。
- 插件异常拖慢主链路。
- 某个渠道消息格式变化导致 session 污染。

改进方向：

- 为被动对话建立 fake provider 和 fake tool 集成测试。
- 为工具调用建立成功、失败、拒绝、超时、循环上限测试。
- 为记忆召回建立离线评估集，记录命中率、排序质量、注入质量。
- 为主动推送建立回放测试，覆盖去重、冷却、ACK 和发送失败。
- 为插件系统建立沙盒插件和失败插件测试。

工程取舍：

```text
早期为了快速验证架构，可以先让主链路跑通；但一旦模块稳定，必须补测试和评估，否则 Agent 行为会随着功能增加越来越不可控。
```

### 技术债二：权限、安全和副作用治理需要更细

项目已经有工具注册、可见性、风险等级、hook 和高风险工具确认的设计思路，但如果要产品化，还需要更严格。

当前风险点包括：

- 工具权限粒度可能还不够细。
- 不同 channel、session、subagent 的权限继承边界需要更明确。
- 写文件、发消息、调用外部服务等副作用需要更完整的审计和补偿。
- 插件能力如果过大，可能绕过核心安全策略。
- 外部工具失败后，需要更明确的幂等、重试和回滚规则。

改进方向：

- 做统一权限模型，按用户、会话、渠道、工具、插件、子任务分层授权。
- 高风险操作默认需要确认或策略审批。
- 所有副作用工具记录审计日志。
- 工具执行引入幂等 key，避免重复执行。
- 插件扩展点区分只读、低风险、高风险权限。

工程取舍：

```text
不能为了演示方便把所有工具都默认开放。Agent 一旦具备行动能力，权限和副作用治理就是核心工程问题。
```

### 技术债三：主动链路的可靠性还需要加强

主动触达是项目亮点，但也是容易出问题的地方。

主动链路涉及：

- 候选内容来源。
- 兴趣判断。
- presence 和打扰控制。
- 去重。
- 冷却。
- ACK。
- 消息发送。
- 失败恢复。

当前要重点关注的技术债是：主动消息的状态一致性。比如内容已经决定发送，但实际发送失败；或者发送成功了，但 ACK 没写成功；或者系统重启后重复推送。

改进方向：

- 给主动推送引入明确状态机：候选、计划发送、发送中、已发送、发送失败、已确认处理。
- 发送成功后再更新最终 ACK。
- 引入 pending 队列和重试机制。
- 对每条主动消息建立幂等标识，防止重复发送。
- 建立离线回放评估主动链路的误推、漏推和重复推送。

工程取舍：

```text
主动能力很能体现 Agent 特点，但它不能只追求“会主动发”。更重要的是不误打扰、不重复、不丢状态、失败可恢复。
```

### 技术债四：记忆质量需要可评估和可纠错

记忆系统是 Agent 长期体验的关键，但也是最容易慢慢变差的模块。

风险包括：

- 错误事实写入长期记忆。
- 旧记忆没有失效。
- 多条记忆互相矛盾。
- 召回结果相关性不够。
- 注入过多导致模型偏题。
- 用户纠正后，历史错误仍然影响回答。

改进方向：

- 为记忆写入增加更明确的置信度和来源记录。
- 为记忆更新增加 supersede 和冲突检测。
- 为召回建立评估集和可视化诊断。
- 对注入内容设置预算和优先级。
- 支持用户显式查看、编辑、删除关键记忆。

工程取舍：

```text
记忆不是越多越好。短期看，写入更多记忆会显得 Agent 更聪明；长期看，错误记忆和无关记忆会降低可信度，所以必须引入质量控制。
```

### 技术债五：部署和运维还需要标准化

项目已经有 workspace、配置、Dashboard、多渠道和长期运行相关设计，但如果要对外部署，还需要补齐运维标准。

风险包括：

- 配置项过多，新用户不容易启动。
- workspace 数据备份和迁移策略不明确。
- 数据库损坏或升级失败时恢复困难。
- Dashboard 权限保护不足会暴露高敏感运行状态。
- 多进程或多实例运行时可能出现状态竞争。

改进方向：

- 提供标准部署文档和最小可运行配置。
- 提供 workspace 备份、恢复、迁移脚本。
- 对数据库 schema 做版本迁移管理。
- Dashboard 默认只绑定本地或加认证。
- 长期运行使用进程守护、结构化日志和健康检查。

工程取舍：

```text
早期项目重点是证明 Agent 架构成立；产品化阶段重点就要转向稳定启动、可备份、可升级、可观测和可恢复。
```

### 如何体现工程取舍

面试时不要只说“我会继续优化”。要按优先级讲：

1. 第一优先级：测试和评估

因为没有测试和评估，后续任何重构都不可靠。

2. 第二优先级：权限和副作用治理

因为 Agent 一旦能行动，安全边界比功能数量更重要。

3. 第三优先级：主动链路状态机

因为主动推送直接影响用户体验，误推和重复推送会很伤害信任。

4. 第四优先级：记忆质量控制

因为长期记忆决定长期体验，错误记忆会持续污染回答。

5. 第五优先级：部署运维标准化

因为产品化要考虑备份、升级、监控和恢复，而不是只在本地跑通。

这能体现你的工程判断：

```text
不是所有问题都同时解决，而是先保障系统可验证，再保障行动安全，然后提升主动能力和长期记忆质量，最后补齐产品化运维。
```

### STAR 法则思考

**Situation 情景：**

这个项目已经覆盖 Agent Runtime 的主要模块，但模块越多，越容易出现链路复杂、行为不稳定、状态不一致和安全边界不清的问题。

**Task 任务：**

需要识别当前项目从 Demo 走向长期服务时最关键的技术债，并说明哪些问题应该优先解决，以及为什么这样排序。

**Action 行动：**

可以把技术债分成五类：测试评估不足、权限和副作用治理不够细、主动链路可靠性需要加强、记忆质量需要可评估和可纠错、部署运维需要标准化。每类都对应具体风险和改进路径。

**Result 结果：**

这样回答能证明你不是只会包装项目亮点，也理解 Agent 应用产品化时真正困难的部分：行为可验证、权限可控、状态一致、记忆可信、运行可恢复。

### 面试总结

可以这样回答：

```text
这个项目最大的技术债不是某一个函数写得不好，而是 Agent 系统从能跑到稳定运行之间的工程差距。第一是测试和评估体系还要补强，否则记忆、工具和主动推送的行为变化很难量化。第二是权限和副作用治理要更细，因为 Agent 一旦能调用工具，就必须控制风险、审计操作和处理失败补偿。第三是主动链路需要更明确的状态机，避免重复推送、误 ACK 和发送失败后的状态不一致。第四是记忆质量要能评估和纠错，避免错误记忆长期污染回答。第五是部署和运维要标准化，包括配置、备份、迁移、健康检查和 Dashboard 保护。我的取舍是先保证行为可验证，再保证行动安全，然后再提升主动能力、记忆质量和产品化运维。
```

## Q90: 如果要把这个项目继续产品化，下一阶段路线图应该怎么排？

### 问题

如果要把这个项目继续产品化，下一阶段路线图应该怎么排？

### 回答

如果继续产品化，路线图不能只是“再加更多功能”。这个项目已经有 Agent Runtime、memory、tool、plugin、proactive、dashboard、多渠道等模块，下一阶段更重要的是把系统从“能力完整”推进到“稳定、可控、可用、可运维”。

我建议分成 5 个阶段：

```text
阶段一：可靠性和评估基线
阶段二：记忆与上下文产品化
阶段三：工具权限和副作用治理
阶段四：多渠道体验和主动触达优化
阶段五：插件生态、部署运维和商业化包装
```

### 阶段一：可靠性和评估基线

第一阶段不急着加新功能，而是先建立“系统行为可验证”的基础。

要做的事：

- 被动对话集成测试：固定模型返回和工具返回，验证一轮对话链路稳定。
- 工具调用测试：覆盖成功、失败、参数错误、拒绝、循环上限和超时。
- 记忆召回评估：建立测试问题集，观察召回内容是否相关、排序是否合理、注入是否过量。
- 主动推送回放：模拟候选内容、用户状态、冷却、去重和发送失败。
- 插件失败测试：验证插件加载失败、执行失败、hook 失败不会拖垮主链路。
- 观察指标整理：记录每轮对话、工具调用、记忆召回和主动推送结果。

业务价值：

```text
先让系统行为可验证，后续才能放心重构、扩展和部署。
```

为什么排第一：

Agent 系统不是普通 CRUD，很多错误不是接口直接报错，而是回答质量下降、记忆污染、主动误推或工具误调用。如果没有评估基线，后续优化没有依据。

### 阶段二：记忆与上下文产品化

第二阶段要让用户能理解和控制 Agent 的记忆。

要做的事：

- 增加记忆管理界面：查看、编辑、删除、停用关键记忆。
- 给记忆增加来源、时间、置信度和状态。
- 对冲突记忆做提示和替换关系。
- 优化记忆写入策略，避免把临时信息写成长期事实。
- 优化上下文注入预算，避免召回内容过多。
- 增加“为什么记得这件事”的解释能力。

业务价值：

```text
让长期记忆从黑盒能力变成用户可控能力，提高信任感和长期使用体验。
```

为什么排第二：

记忆是个人 Agent 的核心价值，但错误记忆也最容易损害信任。产品化时，用户必须能看见和纠正 Agent 记住了什么。

### 阶段三：工具权限和副作用治理

第三阶段要把 Agent 的行动能力做安全。

要做的事：

- 建立统一权限模型：按用户、会话、渠道、插件、子任务、工具分层。
- 高风险工具默认不可见，需要显式授权或确认。
- 对发消息、写文件、外部 API 调用等副作用建立审计记录。
- 工具执行支持幂等 key，避免重复执行。
- 工具失败支持结构化错误、重试策略和补偿机制。
- 插件权限分级，避免插件绕过核心安全策略。
- 子 Agent 和后台任务使用最小权限，不能默认继承主 Agent 全部能力。

业务价值：

```text
让 Agent 可以真正执行任务，同时降低误操作、越权调用和外部副作用风险。
```

为什么排第三：

Agent 产品化的关键分水岭是：它不只是说话，还会行动。一旦能行动，权限、确认、审计、幂等和补偿就必须成为核心能力。

### 阶段四：多渠道体验和主动触达优化

第四阶段要优化用户体验，而不是只保证后端链路能跑。

要做的事：

- 统一 CLI、Telegram、QQ 等渠道的体验差异。
- 对不同渠道做消息格式适配，比如长消息拆分、引用、附件、按钮、确认交互。
- 主动推送引入更明确状态机：候选、计划、发送中、已发送、失败、已确认。
- 优化 presence 和打扰控制，减少误打扰。
- 增加主动推送偏好设置，让用户控制频率、类型和时间段。
- 对主动推送效果做统计：打开率、回复率、误推率、重复率。

业务价值：

```text
让 Agent 真正融入用户日常入口，同时主动能力不打扰、不重复、可调节。
```

为什么排第四：

多渠道和主动触达是强体验模块，但必须建立在可靠性、记忆质量和权限治理之上。否则主动能力越强，出错影响越大。

### 阶段五：插件生态、部署运维和商业化包装

第五阶段要把项目从个人工程推进到可交付产品。

要做的事：

- 提供插件开发模板和插件权限说明。
- 插件市场或插件列表支持启用、禁用、配置和健康状态查看。
- 标准化部署文档，提供最小配置和推荐配置。
- workspace 支持备份、恢复、迁移和版本升级。
- Dashboard 增加认证、访问控制和敏感信息保护。
- 增加健康检查、结构化日志和告警。
- 包装项目案例：架构图、时序图、演示脚本、面试讲稿、技术债和路线图。

业务价值：

```text
让系统不只是开发者本地能跑，而是能被部署、维护、扩展和对外展示。
```

为什么排第五：

插件生态和部署运维适合在核心链路稳定后推进。否则过早做生态和包装，会把不稳定能力放大。

### 路线图优先级

可以把路线图压缩成一个优先级顺序：

```text
先可验证 -> 再可信记忆 -> 再安全行动 -> 再体验优化 -> 最后生态和部署
```

对应解释是：

- 可验证：没有测试和评估，系统越改越不确定。
- 可信记忆：没有可控记忆，长期使用会失去信任。
- 安全行动：没有权限和审计，工具越多风险越大。
- 体验优化：没有打扰控制和渠道体验，用户不会长期使用。
- 生态部署：没有稳定底座，插件和部署只会放大复杂度。

### STAR 法则思考

**Situation 情景：**

当前项目已经具备 Agent Runtime 的核心模块，但如果要产品化，不能继续只堆功能，而要解决稳定性、用户信任、行动安全、体验一致性和长期运维问题。

**Task 任务：**

需要制定一条从工程 Demo 到可交付 Agent 产品的路线图，明确先做什么、后做什么，以及每一步对应的业务价值。

**Action 行动：**

路线图按五个阶段推进：先建立测试评估和可观测基线，再把记忆做成用户可控能力，然后强化工具权限和副作用治理，接着优化多渠道体验和主动触达，最后补齐插件生态、部署运维和项目包装。

**Result 结果：**

这样推进可以避免盲目加功能，让项目从“能展示 Agent 能力”进一步变成“能稳定运行、能被用户信任、能安全行动、能长期维护”的产品化 Agent 应用。

### 面试总结

可以这样回答：

```text
如果继续产品化，我不会优先堆新功能，而是按五个阶段推进。第一阶段先建立测试、评估和观察基线，让系统行为可验证。第二阶段把记忆产品化，让用户能查看、纠正和管理 Agent 记住的内容。第三阶段强化工具权限和副作用治理，让 Agent 的行动能力安全可控。第四阶段优化多渠道体验和主动触达，包括消息适配、打扰控制、去重、冷却和主动偏好。第五阶段再做插件生态、部署运维和项目包装，包括插件权限、备份迁移、Dashboard 保护、健康检查和演示材料。这个顺序体现的取舍是：先保证可验证和可信任，再扩大行动能力和产品体验，最后做生态和交付。
```

## 后续待回答问题清单

说明：本节只是后续题目规划，不计入“已记录问题数”。后续真正回答时，再按正式 `## Qxx` 格式追加到文档末尾，并继续补充 STAR 法则思考。面试总结部分应优先用中文职责描述，少堆具体函数名。

### 当前内容审阅结论

当前已经完成 Q1-Q55，覆盖了 Agent Runtime 的主干理解：

- 主链路：消息入口、AgentLoop、生命周期阶段、事件驱动、模型提供层。
- 上下文：系统提示词、prompt block、动态 context frame、prompt cache。
- 记忆与 RAG：短期/长期/情景/程序性记忆、写入、合并、纠错、召回、排序、注入、query rewrite、HyDE。
- 工具与插件：工具注册、工具可见性、工具执行治理、MCP 接入、插件 hook、lifecycle 扩展。
- 会话与证据链：channel/session 隔离、memory scope、原始消息追溯、source_ref。
- 可观测性：turn trace、memory retrieval trace、memory write trace、Dashboard 诊断。
- 主动链路：已经从基础 proactive 概念推进到 tick、gate、dedupe 的整体流程。

当前还需要补齐的重点是：

- Proactive v2 的细节机制。
- 后台任务和子 Agent 的完整生命周期。
- MCP / 外部能力接入的失败和权限边界。
- 测试、评估、部署、配置和运行环境。
- 安全、回滚、副作用治理。
- 最后把技术设计整理成面试项目表达。

### Proactive v2 深挖

- [x] Q56：Proactive v2 的兴趣判断是怎么做的？为什么要同时使用候选内容、长期记忆、最近对话和工作区主动规则？
- [x] Q57：Proactive v2 里的 presence 和打扰控制如何工作？它如何判断用户当前是否适合被主动触达？
- [x] Q58：Proactive v2 的 ACK 策略是什么？为什么不同结果要有不同的已读、丢弃和冷却处理？
- [x] Q59：Proactive v2 的 drift 机制解决什么问题？它和普通 content/alert 推送有什么区别？
- [x] Q60：主动推送失败时系统如何处理？如何避免消息没发出去但内容被错误标记为已处理？
- [x] Q61：主动链路应该如何做离线回放和效果评估？如何衡量误推、漏推和重复推送？

### Background Job / Subagent 深挖

- [x] Q62：这个项目里的 background job 和 subagent 分别解决什么问题？它们和主 Agent 的边界在哪里？
- [x] Q63：子任务是如何被创建、排队、执行和结束的？为什么不能让主对话流程同步等待所有长任务？
- [x] Q64：后台任务的结果如何回灌到主会话、记忆或通知系统？如何避免结果丢失或重复通知？
- [x] Q65：subagent / background job 的权限应该如何限制？为什么不能默认继承主 Agent 的全部工具权限？
- [x] Q66：后台任务失败、超时或被取消时，系统应该如何恢复？哪些状态需要持久化？

### MCP / 外部能力接入

- [x] Q67：MCP server 作为外部能力来源时，项目如何处理连接、工具发现、调用和断开？
- [x] Q68：外部工具 schema 如何进入统一工具系统？为什么需要适配层而不是让模型直接调用外部协议？
- [x] Q69：MCP 工具失败、超时或返回异常格式时，Agent Runtime 应该如何降级？
- [x] Q70：如果未来接入外部 Agent 或 peer agent，应该如何设计权限、上下文边界和结果可信度？

### 测试与评估

- [x] Q71：这个项目应该如何测试一轮被动 Agent 对话？哪些部分适合单元测试，哪些适合集成测试？
- [x] Q72：工具调用循环应该如何测试？如何覆盖工具错误、参数错误、循环过长和终止条件？
- [x] Q73：memory retrieval 应该如何评估？如何判断召回内容相关、排序合理、注入不过量？
- [x] Q74：Proactive v2 应该如何测试？如何模拟 feed、presence、cooldown、dedupe 和发送失败？
- [x] Q75：插件系统应该如何测试？如何确保插件不会破坏主链路或引入不可控副作用？

### 部署 / 配置 / 运行环境

- [x] Q76：项目的配置系统是如何组织的？模型、渠道、memory、proactive、插件配置应该如何分层？
- [x] Q77：workspace 初始化时需要创建哪些目录、数据库和默认文件？为什么运行状态不能散落在项目根目录？
- [x] Q78：CLI、Telegram、QQ 等不同 channel adapter 的启动路径有什么共同点和差异？
- [x] Q79：Dashboard 在部署中应该如何启动、保护和访问？为什么它不应该只是开发期临时页面？
- [x] Q80：如果要把这个项目部署成长期运行的 Agent 服务，需要关注哪些进程管理、日志、备份和升级问题？

### 安全 / 回滚 / 副作用治理

- [x] Q81：用户撤回消息、删除消息或纠正事实时，session history、memory 和 observe trace 应该如何处理？
- [x] Q82：长期记忆为什么需要失效、覆盖或 supersede 机制？它和物理删除分别适合什么场景？
- [x] Q83：工具副作用如何治理？比如发消息、写文件、调用外部服务失败后如何补偿？
- [x] Q84：高风险工具应该如何做权限控制、确认机制和审计记录？
- [x] Q85：插件或工具出现异常时，系统如何保证主对话链路不被拖垮？

### 面试项目表达

- [x] Q86：如果把这个项目作为 Agent 应用求职项目，应该如何用 STAR 法则讲清楚整体项目？
- [x] Q87：这个项目最能体现 Agent 工程能力的 3-5 个亮点是什么？每个亮点对应什么业务价值？
- [x] Q88：面试官如果质疑“这只是套壳聊天机器人”，应该如何解释它和普通 chatbot 的区别？
- [x] Q89：这个项目当前最大的技术债和改进方向是什么？如何体现你对工程取舍的理解？
- [x] Q90：如果要把这个项目继续产品化，下一阶段路线图应该怎么排？

### TaskPlan / capability contract

- [x] Q91：为什么纯计划创建不应该默认调用 memory，而“结合偏好制定计划”又不能全禁 memory？
- [x] Q92：`TaskPlanTurnContract` 如何把 action、context requirement、capability scope、budget 和 completion 统一起来？
- [x] Q93：为什么一次召回返回失败、被 hook 拒绝或 executor error 后仍要消耗预算？
- [x] Q94：strict capability scope 如何同时约束 schema、tool search 和 execution，并避免污染 LRU？
- [x] Q95：为什么 TaskPlan completion 要按 capability 判断，而不能硬编码“任一 TaskPlan 工具 ok 就结束”？
- [x] Q96：真实 smoke 如何验证纯计划 2 轮、偏好/历史各一次召回，以及 background passthrough 不被破坏？
- [x] Q97：TaskPlan 状态管理与任务执行器的边界是什么，为什么需要 execution attempt、幂等恢复和副作用授权？

## Q97: TaskPlan 状态管理与任务执行器的边界是什么，为什么需要 execution attempt、幂等恢复和副作用授权？

TaskPlan 负责长期业务状态：任务、步骤顺序、pending/in-progress/completed/failed/skipped 和结果摘要。Task execution 负责一次执行尝试的运行事实：request identity、attempt number、owner/lease、tool event、waiting/blocked/terminal reason。两者不能混成一张步骤状态表，否则重启或重复消息时无法区分“步骤业务上没完成”和“某次执行结果未知”。

项目采用独立 attempt/event 的原因有三点：

1. 幂等：同一 transport request ID replay 返回原 attempt，不按文本 hash 去重；新 ID 即使文本相同也是独立操作。
2. 恢复：旧 runtime 的 running attempt 在重启后标记 `runtime_restarted_outcome_unknown`，step 回 pending，但系统绝不自动重放；只有显式 retry 才创建 attempt number + 1。
3. 副作用安全：第一版只自动执行 registry exact read-only。write/external/unknown/shell 必须先进入 waiting authorization，destructive 保持 core deny；成功还必须有真实 `counts_as_work=true` work event 和 finish。

验证不能只看模型回复。Task 10 使用独立 PID/socket/workspace/SQLite/dashboard，发送 raw IPC duplicate frame，执行 controlled restart，并对比 agent log、observe turn 和 SQLite rows。结果是 replay 0 new attempt、restart 0 auto replay、ordinary continue 0 retry、explicit retry exactly one new attempt；文件修改计划目标不变且 write/edit/shell event 为 0。完整回归为 `1835 passed, 3 warnings`。

当前边界也要说清楚：这证明的是 recoverable controlled read-only execution，不是完整自主本地执行器。批准/拒绝协议、structured authorization request columns、文件 diff、snapshot 和 rollback 仍属于 P2/P3。

STAR 法则思考：

- Situation：计划状态已持久化，但重复请求、重启和副作用没有执行事实边界。
- Task：保证一次只推进一步、重复请求不重复工作、unknown outcome 不自动重放。
- Action：引入 attempt/event、request replay-first、lease recovery、read-only scope、defer 和 finalizer，并做 isolated raw IPC/restart/SQLite smoke。
- Result：4 succeeded、1 blocked、1 cancelled、0 active live attempts，真实 write/edit/shell 为 0；用户原 Agent 全程未受影响。
