# 00 Test Strategy

这个文档记录项目测试的总体策略。

## 测试目标

通过分步测试，真正理解这个项目的运行链路，而不是只停留在文档理解。

重点验证：

- 消息如何进入 AgentLoop。
- 上下文如何构建。
- memory 是否召回和注入。
- 工具是否被正确调用。
- 插件是否生效。
- 主动链路是否按条件触发。
- trace 和 dashboard 是否能解释行为。
- 失败场景是否有降级和错误记录。

## 总体测试顺序

建议按这个顺序推进：

```text
1. 被动对话主链路
2. Memory / RAG 链路
3. 工具调用链路
4. 插件扩展链路
5. Observe / Dashboard 链路
6. Proactive 主动链路
7. Background Job / Subagent 链路
8. 回归测试
```

原因：

- 被动对话是所有能力的基础。
- memory 和工具是 Agent 能力核心。
- 插件和 observe 是扩展与诊断能力。
- proactive 和 background job 更复杂，适合后测。

## 测试原则

- 每次只测一条主链路。
- 每个测试都要有明确输入和预期行为。
- 不只看最终回答，还要看 session、memory、tool、trace。
- 出现问题时先记录，不急着修。
- 每次测试后更新 `07-test-log.md`。

## 测试环境假设

当前假设：

- 项目已经能通过 CLI 正常问答。
- 本地配置文件已经可用。
- 至少有一个 LLM Provider 可调用。
- 当前 workspace 能写入 session、memory 和 observe 数据。

如果这些假设不成立，先回到 `my_md/learning/01-runbook.md` 排查运行问题。

## 测试完成标准

当你能解释下面这些问题时，说明测试有效：

- 一条用户消息进入后，经过了哪些模块？
- memory 是什么时候召回的？
- 工具调用失败时系统怎么处理？
- 插件是否能影响工具或生命周期？
- trace 里能否看到一轮对话的关键过程？
- 主动推送为什么发或不发？

## 当前优先级

第一阶段只做：

```text
被动对话主链路
Memory / RAG
工具调用
Observe / Dashboard
```

暂时不急着测：

```text
Proactive
Background Job
Subagent
MCP
多渠道 Telegram / QQ
```
