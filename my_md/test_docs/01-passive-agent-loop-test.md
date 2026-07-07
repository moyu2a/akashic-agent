# 01 Passive Agent Loop Test

这个文档记录被动对话主链路测试。

## 测试目标

验证最基础链路：

```text
CLI 输入
-> InboundMessage
-> MessageBus
-> AgentLoop
-> Context / Memory / Reasoner
-> OutboundMessage
-> CLI 输出
```

## 重点观察点

- CLI 消息是否被转换成 `InboundMessage`。
- `session_key` 是否正确。
- AgentLoop 是否消费消息。
- 是否写入 session history。
- 是否构建 system prompt 和 context frame。
- 是否有 memory retrieval。
- 是否生成 outbound。

## 测试 1：基础问答

输入：

```text
你好，请用一句话介绍你自己
```

预期：

- CLI 能收到回复。
- 不一定触发工具。
- 不一定触发 memory。
- session history 应该记录本轮消息。

记录：

```text
实际回复：
是否写入 session：
是否有 trace：
异常：
```

## 测试 2：连续对话

输入 1：

```text
我现在正在测试 akashic-agent 的被动对话链路
```

输入 2：

```text
我刚才说我在测试什么？
```

预期：

- 第二轮应该能利用最近对话历史回答。
- 即使不进入长期 memory，也应该能从 session history 里答出。

记录：

```text
是否命中最近上下文：
是否误用了长期记忆：
回答是否准确：
```

## 测试 3：上下文边界

输入：

```text
请总结一下我们刚才这几轮对话的主题
```

预期：

- 能基于当前 session history 总结。
- 不应该混入其他 session 的内容。

记录：

```text
是否出现其他会话信息：
是否准确总结：
```

## 需要查看的文件

- `bus/events.py`
- `bus/queue.py`
- `agent/looping/core.py`
- `agent/core/passive_turn.py`
- `session/store.py`

## 测试结论

2026-07-02 初步测试通过：

- 基础 CLI 问答正常。
- 连续对话中 session history 生效。
- recall inspector 未出现长期召回记录，但本轮测试目标不是 memory recall，因此属于预期。
- 下一步进入 `02-memory-rag-test.md`，专门测试长期记忆写入和召回。

2026-07-03 多 CLI session 隔离测试通过：

测试过程：

- 一号 CLI 输入：`我是一号会话，我的测试暗号是 blue-session`
- 二号 CLI 输入：`我刚才在这个会话里说的测试暗号是什么？`
- 一号 CLI 再输入：`我刚才说的一号会话测试暗号是什么？`

本地数据确认：

- 一号会话 `session_key=cli:cli-133349980485776`
- 二号会话 `session_key=cli:cli-133350248939024`
- 一号会话消息序列中包含 `blue-session`。
- 二号会话消息序列中不包含 `blue-session`。
- 二号会话回答：本轮会话没有找到测试暗号。
- 一号会话回答：`blue-session`。

结论：

- 两个 CLI 会话生成了不同 session_key。
- session history 没有跨会话污染。
- 同一会话内上下文可用。
- 二号会话使用 `search_messages` 时显式限制在自己的 session_key 下，未跨 session 检索。

发现的问题：

- 二号会话额外调用了 `recall_memory`，但返回的是无关的长期偏好记忆，没有泄漏一号会话暗号。
- 后续可优化：对“刚才在这个会话里”这类问题，优先只查当前 session history，减少不必要的长期记忆召回。
