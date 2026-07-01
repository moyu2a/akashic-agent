# 08 Ordered Learning Outline

这个文档用于重新整理 `07-module-interview-qa.md` 里的 90 个问题顺序。

目标不是替代原问答文档，而是提供一个更适合学习和复盘的路径：先建立全局视角，再理解运行时主链路，然后按模块深入，最后回到面试表达、技术债和路线图。

## 使用方式

- 本文档只记录重排后的学习大纲和问题索引。
- 每个问题后面的 `Qxx` 对应 `07-module-interview-qa.md` 里的正式问答。
- 学习时建议按本文档顺序推进，而不是按原问题产生顺序推进。
- 每学完一个阶段，建议自己能画出该阶段的输入、输出、核心对象、失败场景和改进方向。

## 总体学习路线

```text
0. 全局项目定位
1. Runtime 与 AgentLoop 主架构
2. Message / Channel / Session 边界
3. Context / Prompt / Prompt Cache
4. Memory / RAG / Retrieval
5. Tool / Plugin / MCP / 副作用治理
6. Proactive / Scheduler / 主动触达
7. Background Job / Subagent / 外部 Agent
8. Observability / Testing / Evaluation
9. Config / Workspace / Deployment
10. 面试表达 / 技术债 / 产品化路线图
```

## 阶段 0：全局项目定位

学习目标：先建立“这个项目到底是什么”的判断，避免一开始陷入代码细节。

你需要能回答：

- 它为什么不是普通 chatbot？
- 它适合作为 Agent 求职项目吗？
- 它最核心的工程亮点是什么？

建议顺序：

1. Q86：如果把这个项目作为 Agent 应用求职项目，应该如何用 STAR 法则讲清楚整体项目？
2. Q88：面试官如果质疑“这只是套壳聊天机器人”，应该如何解释它和普通 chatbot 的区别？
3. Q87：这个项目最能体现 Agent 工程能力的 3-5 个亮点是什么？每个亮点对应什么业务价值？

阶段产出：

- 一段 2 分钟项目介绍。
- 一张“普通 chatbot vs Agent Runtime”的对比表。
- 一张“技术亮点 -> 业务价值”的映射表。

## 阶段 1：Runtime 与 AgentLoop 主架构

学习目标：理解项目的主干，不急着进入 memory、tool、plugin 等细节。

你需要能回答：

- AgentLoop 在系统里负责什么？
- MessageBus 和 EventBus 为什么分开？
- lifecycle phase 为什么存在？
- Provider 抽象解决什么问题？

建议顺序：

1. Q2：这个项目的 agent 设计模式是什么？有没有用到什么 agent 框架？
2. Q1：`MessageBus` 和 `EventBus` 分别是什么？为什么项目里要同时有这两个 bus？
3. Q12：这个项目为什么要把一次对话拆成多个 lifecycle phase？直接一个函数从输入跑到输出不行吗？
4. Q51：Lifecycle Phase 为什么要做成 module + slot/requires 机制？每个 phase 的边界是什么？
5. Q28：这个项目为什么要用 EventBus 做事件驱动解耦？比如 TurnCommitted / ConsolidationCommitted 起什么作用？
6. Q3：这个 AgentLoop 中有哪些状态？
7. Q18：这个项目为什么要抽象 LLM Provider？直接在 AgentLoop 里调用 OpenAI API 不行吗？
8. Q52：为什么要抽象 LLMProvider？它如何统一不同模型、stream/non-stream 和轻量模型？

阶段产出：

- 一张被动对话主链路图。
- 一张 `MessageBus / EventBus / lifecycle phase / provider` 的职责边界表。

## 阶段 2：Message / Channel / Session 边界

学习目标：理解多渠道、多会话为什么是 Agent Runtime 的基础。

你需要能回答：

- CLI、Telegram、QQ 为什么能复用同一套 Agent 核心？
- session 隔离如何影响 memory 和 tool 可见性？
- 原始消息如何被追溯？

建议顺序：

1. Q19：这个项目为什么需要 channel 和 session 抽象？只做一个 CLI 问答不行吗？
2. Q26：每个 session 的工具可见性是如何相互隔离的？不同会话、不同消息来源比如 Telegram / QQ 是如何隔离的？
3. Q27：session 隔离和 memory scope 是什么关系？长期记忆会不会在不同 Telegram / QQ 会话之间互相污染？
4. Q53：SessionStore、message id 和 source_ref 是如何支撑原始消息追溯的？
5. Q78：CLI、Telegram、QQ 等不同 channel adapter 的启动路径有什么共同点和差异？

阶段产出：

- 一张 `channel -> inbound message -> session -> agent -> outbound message` 的流程图。
- 一份 session/channel/scope 的边界说明。

## 阶段 3：Context / Prompt / Prompt Cache

学习目标：理解上下文工程，不要把 prompt 理解成简单字符串拼接。

你需要能回答：

- system prompt、prompt block、context frame 各自放什么？
- 为什么上下文不能无限塞？
- prompt cache 为什么和稳定性排序有关？

建议顺序：

1. Q5：这个项目的上下文工程是怎么组织的？
2. Q6：系统提示词是怎么设计的？
3. Q17：这个项目如何处理上下文过长？为什么不能简单把所有 memory、history、tools 都塞进 prompt？
4. Q31：prompt cache 是存储在哪里的？
5. Q32：本地 prompt block cache 和服务端 prompt cache / KV cache 有什么区别？
6. Q33：为什么 system prompt 的 prompt blocks 要按稳定性和优先级排序？这和 prompt cache 有什么关系？
7. Q34：为什么项目要把部分动态上下文放进 context frame，而不是全部放进 system prompt？

阶段产出：

- 一张 prompt 组成结构图。
- 一份“稳定上下文 / 动态上下文 / 检索注入上下文”的分类表。

## 阶段 4：Memory / RAG / Retrieval

学习目标：系统理解记忆，不只停留在“用了向量库”。

你需要能回答：

- 这个项目是否具有 RAG？
- 短期记忆、长期记忆、情景记忆、程序性记忆在哪里？
- 为什么要同时有 Markdown 记忆和数据库？
- retrieval pipeline 如何召回、排序、过滤和注入？
- 错误记忆如何纠正、失效或替换？

建议顺序：

1. Q4：当前系统是否具有 RAG？
2. Q7：memory 存储采用的什么策略？比如滑动窗口、摘要压缩等等？
3. Q29：短期记忆、长期记忆、情景记忆、程序性记忆在这个项目里分别存储在哪里？
4. Q8：为什么这个项目同时使用 Markdown 记忆文件和 memory2.db 向量数据库？只用一种不行吗？
5. Q9：这个项目里的 consolidation 是什么？为什么不能直接把每轮对话都写进长期记忆？
6. Q30：Memory Optimizer 是什么？为什么要先写 PENDING.md，再定期合并到 MEMORY.md？
7. Q38：memory 写入为什么要分成 post-response 和 consolidation 两条链路？
8. Q39：既然有自动 consolidation，为什么还需要显式 memorize 工具？
9. Q20：如果 Agent 记错了用户信息，这个项目如何处理记忆纠错？为什么不能只在回答里道歉？
10. Q35：这个项目的 memory retrieval pipeline 是怎么工作的？是不是搜到什么就直接塞进 prompt？
11. Q36：为什么 memory retrieval 要同时做向量召回和关键词召回？只用 embedding 不行吗？
12. Q43：memory 检索为什么不只靠 embedding 相似度？
13. Q44：embedding 召回的内容是不是按照 reinforcement 等方式排序？
14. Q45：检索出来的 memory 为什么不能全部注入 prompt？
15. Q46：memory 检索前为什么要做 query rewrite？
16. Q47：query rewrite 采用的是什么方案？
17. Q48：HyDE 在这个项目里起什么作用？它和 query rewrite 有什么区别？
18. Q37：为什么 procedure memory 会有强制约束？它和 preference 有什么区别？
19. Q40：既然每轮会被动注入记忆，为什么还需要 recall_memory 工具？
20. Q41：recall_memory、search_messages、fetch_messages 三者怎么分工？
21. Q42：forget_memory 为什么是标记 superseded，而不是物理删除？
22. Q81：用户撤回消息、删除消息或纠正事实时，session history、memory 和 observe trace 应该如何处理？
23. Q82：长期记忆为什么需要失效、覆盖或 supersede 机制？它和物理删除分别适合什么场景？

阶段产出：

- 一张 memory 写入链路图。
- 一张 retrieval pipeline 图。
- 一张 memory 类型、存储位置、更新方式、风险点的表。

## 阶段 5：Tool / Plugin / MCP / 副作用治理

学习目标：理解 Agent 的“行动能力”不是 function calling 演示，而是权限、可见性、执行、失败和审计的组合。

你需要能回答：

- 工具为什么不能直接写死在 AgentLoop？
- tool_search 为什么存在？
- ToolExecutor 和 ToolHook 为什么是治理边界？
- 插件如何把能力接入工具调用？
- MCP 外部工具如何进入统一工具体系？
- 高风险工具和副作用如何治理？

建议顺序：

1. Q10：这个项目的工具系统是怎么设计的？为什么工具不直接写死在 AgentLoop 里？
2. Q23：为什么项目要做工具可见性和 tool_search？为什么不把所有工具每轮都暴露给 LLM？
3. Q16：工具调用为什么需要边界控制？如何避免 Agent 陷入无限 tool loop 或错误工具调用？
4. Q21：Agent 可以调用工具和插件后，系统如何做安全边界？只靠 prompt 约束够吗？
5. Q50：ToolExecutor 和 ToolHook 是怎么工作的？为什么工具调用不能直接走 ToolRegistry.execute？
6. Q11：这个项目的插件系统解决了什么问题？为什么不把所有能力都放进核心代码？
7. Q22：插件在这里是如何起作用的？比如如何引入插件，并让插件在工具调用中生效？
8. Q49：MCP 工具是如何接入这个 Agent Runtime 的？它和普通内置 Tool 有什么区别？
9. Q67：MCP server 作为外部能力来源时，项目如何处理连接、工具发现、调用和断开？
10. Q68：外部工具 schema 如何进入统一工具系统？为什么需要适配层而不是让模型直接调用外部协议？
11. Q69：MCP 工具失败、超时或返回异常格式时，Agent Runtime 应该如何降级？
12. Q83：工具副作用如何治理？比如发消息、写文件、调用外部服务失败后如何补偿？
13. Q84：高风险工具应该如何做权限控制、确认机制和审计记录？
14. Q85：插件或工具出现异常时，系统如何保证主对话链路不被拖垮？

阶段产出：

- 一张工具调用生命周期图。
- 一张工具风险等级、确认机制、审计记录、失败处理的治理表。
- 一张插件扩展点地图。

## 阶段 6：Proactive / Scheduler / 主动触达

学习目标：理解主动 Agent 不等于定时发消息，而是兴趣判断、打扰控制、去重、ACK 和失败恢复。

你需要能回答：

- 被动 Agent 和主动 Agent 的区别是什么？
- scheduler、proactive、background job 的边界是什么？
- 为什么不能有新内容就直接推？
- presence、ACK、drift 分别解决什么问题？

建议顺序：

1. Q13：这个项目里的被动 Agent 和主动 Agent 有什么区别？为什么需要 ProactiveLoop？
2. Q14：主动推送系统最难的点是什么？为什么不是拿到新内容就直接推给用户？
3. Q25：这个项目里的 scheduler 解决什么问题？它和 proactive / background job 有什么区别？
4. Q55：Proactive v2 为什么不是有新内容就主动推送？它的 tick / gate / dedupe 流程是什么？
5. Q56：Proactive v2 的兴趣判断是怎么做的？为什么要同时使用候选内容、长期记忆、最近对话和工作区主动规则？
6. Q57：Proactive v2 里的 presence 和打扰控制如何工作？它如何判断用户当前是否适合被主动触达？
7. Q58：Proactive v2 的 ACK 策略是什么？为什么不同结果要有不同的已读、丢弃和冷却处理？
8. Q59：Proactive v2 的 drift 机制解决什么问题？它和普通 content/alert 推送有什么区别？
9. Q60：主动推送失败时系统如何处理？如何避免消息没发出去但内容被错误标记为已处理？
10. Q61：主动链路应该如何做离线回放和效果评估？如何衡量误推、漏推和重复推送？

阶段产出：

- 一张 proactive tick 到 outbound 的时序图。
- 一张主动推送状态表：候选、跳过、发送、失败、ACK。

## 阶段 7：Background Job / Subagent / 外部 Agent

学习目标：理解长任务、子 Agent 和外部 Agent 的边界。

你需要能回答：

- 为什么主 Agent 不能同步等所有长任务？
- background job 和 subagent 各自负责什么？
- 子任务结果如何回到主会话？
- 子 Agent 和 peer agent 为什么不能默认继承主 Agent 权限？

建议顺序：

1. Q24：为什么项目需要 subagent / background job？主 Agent 自己完成所有任务不行吗？
2. Q62：这个项目里的 background job 和 subagent 分别解决什么问题？它们和主 Agent 的边界在哪里？
3. Q63：子任务是如何被创建、排队、执行和结束的？为什么不能让主对话流程同步等待所有长任务？
4. Q64：后台任务的结果如何回灌到主会话、记忆或通知系统？如何避免结果丢失或重复通知？
5. Q65：subagent / background job 的权限应该如何限制？为什么不能默认继承主 Agent 的全部工具权限？
6. Q66：后台任务失败、超时或被取消时，系统应该如何恢复？哪些状态需要持久化？
7. Q70：如果未来接入外部 Agent 或 peer agent，应该如何设计权限、上下文边界和结果可信度？

阶段产出：

- 一张主 Agent、background job、subagent、peer agent 的边界图。
- 一张长任务生命周期状态图。

## 阶段 8：Observability / Testing / Evaluation

学习目标：理解 Agent 工程为什么必须能观察、测试和评估。

你需要能回答：

- Dashboard 和日志有什么区别？
- 一轮 Agent 行为如何被 trace？
- 被动对话、工具循环、memory retrieval、proactive、plugin 分别怎么测？

建议顺序：

1. Q15：为什么 Agent 应用需要 Dashboard 和可观测性？只看日志不行吗？
2. Q54：Observe / Dashboard trace 是如何记录一轮 Agent 行为的？为什么只看日志不够？
3. Q71：这个项目应该如何测试一轮被动 Agent 对话？哪些部分适合单元测试，哪些适合集成测试？
4. Q72：工具调用循环应该如何测试？如何覆盖工具错误、参数错误、循环过长和终止条件？
5. Q73：memory retrieval 应该如何评估？如何判断召回内容相关、排序合理、注入不过量？
6. Q74：Proactive v2 应该如何测试？如何模拟 feed、presence、cooldown、dedupe 和发送失败？
7. Q75：插件系统应该如何测试？如何确保插件不会破坏主链路或引入不可控副作用？

阶段产出：

- 一张可观测数据流图。
- 一张测试矩阵：模块、测试类型、fake 对象、关键断言。

## 阶段 9：Config / Workspace / Deployment

学习目标：理解项目如何从本地可运行走向长期服务。

你需要能回答：

- 配置系统怎么分层？
- workspace 为什么是运行状态边界？
- Dashboard 为什么需要保护？
- 长期部署需要哪些进程、日志、备份和升级策略？

建议顺序：

1. Q76：项目的配置系统是如何组织的？模型、渠道、memory、proactive、插件配置应该如何分层？
2. Q77：workspace 初始化时需要创建哪些目录、数据库和默认文件？为什么运行状态不能散落在项目根目录？
3. Q79：Dashboard 在部署中应该如何启动、保护和访问？为什么它不应该只是开发期临时页面？
4. Q80：如果要把这个项目部署成长期运行的 Agent 服务，需要关注哪些进程管理、日志、备份和升级问题？

阶段产出：

- 一张配置加载到运行时组装的流程图。
- 一份生产部署检查清单。

## 阶段 10：面试表达 / 技术债 / 产品化路线图

学习目标：把技术理解转成面试表达，而不是只会讲模块名字。

你需要能回答：

- 项目的技术债是什么？
- 如何体现工程取舍？
- 如果继续产品化，下一阶段路线图怎么排？

建议顺序：

1. Q89：这个项目当前最大的技术债和改进方向是什么？如何体现你对工程取舍的理解？
2. Q90：如果要把这个项目继续产品化，下一阶段路线图应该怎么排？

复盘建议：

- 回看 Q86，把整体项目讲成 STAR。
- 回看 Q87，把技术亮点映射到业务价值。
- 回看 Q88，准备回应“套壳 chatbot”的质疑。

阶段产出：

- 一段 2 分钟项目讲稿。
- 一段 5 分钟项目讲稿。
- 一份技术债和产品路线图。

## 推荐复习节奏

### 第一轮：建立全局

只看阶段 0、1、2、3。

目标是能说明：

- 项目是什么。
- 主链路怎么跑。
- 多渠道和 session 如何隔离。
- prompt 和上下文如何组织。

### 第二轮：深入核心能力

重点看阶段 4、5、6。

目标是能说明：

- memory 如何写入、召回、排序、注入和纠错。
- tool/plugin/MCP 如何接入、执行和治理。
- proactive 如何判断、去重、发送和 ACK。

### 第三轮：补工程化

重点看阶段 7、8、9。

目标是能说明：

- 长任务和子 Agent 如何管理。
- Dashboard 和 trace 如何支撑诊断。
- 测试、评估、配置、workspace、部署如何支撑长期运行。

### 第四轮：面试表达

重点看阶段 10，并回看阶段 0。

目标是能说明：

- 项目亮点。
- 项目边界。
- 技术债。
- 产品化路线图。
- 为什么它能体现 Agent 工程能力。

## 一句话总纲

```text
这个项目的学习顺序应该是：先理解它为什么是 Agent Runtime，再理解被动对话主链路，然后深入 context、memory、tool、plugin、proactive、subagent、observability、deployment，最后把这些模块组织成面试中的 STAR 项目表达。
```
