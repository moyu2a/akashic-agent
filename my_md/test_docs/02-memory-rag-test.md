# 02 Memory RAG Test

这个文档记录 memory / RAG 链路测试。

## 测试目标

验证：

```text
用户事实
-> session history
-> memory 写入 / consolidation
-> memory2.db
-> retrieval
-> prompt 注入
-> 回答使用记忆
```

## 重点观察点

- 用户事实是否被记录。
- 是否进入 `PENDING.md`、`MEMORY.md` 或 `memory2.db`。
- 后续问题是否触发 retrieval。
- 召回内容是否相关。
- 是否错误召回其他 session 内容。
- 用户纠错后旧记忆是否 supersede。

## 测试 1：短期上下文记忆

输入 1：

```text
我现在在学习 akashic-agent 的 memory2 模块
```

输入 2：

```text
我现在在学习哪个模块？
```

预期：

- 应该能从当前 session history 回答。
- 不一定需要长期 memory。

记录：

```text
回答是否准确：
是否触发 retrieval：
```

## 测试 2：长期记忆写入和召回

输入：

```text
请记住：我学习这个项目时，优先关注 Agent Runtime、RAG 和工具治理。
```

稍后输入：

```text
你还记得我学习这个项目时优先关注什么吗？
```

预期：

- 应触发记忆召回。
- 回答应包含 Agent Runtime、RAG、工具治理。

记录：

```text
是否写入 memory：
召回内容：
回答是否准确：
```

## 测试 3：记忆纠错

输入：

```text
刚才记错了，我优先关注的是 Document RAG、GraphRAG 和 LLM Wiki。
```

后续输入：

```text
我现在优先关注哪些方向？
```

预期：

- 新事实应覆盖旧事实。
- 旧记忆不应继续主导回答。

记录：

```text
旧记忆是否还影响回答：
是否出现 supersede：
```

## 测试 4：无关召回

输入：

```text
请解释一下 FastAPI 的 Depends 是什么
```

预期：

- 这类通用知识问题不应该强行召回个人记忆。
- 如果召回，也不应污染答案。

记录：

```text
是否触发 retrieval：
召回是否相关：
```

## 需要查看的文件

- `memory2/retriever.py`
- `memory2/store.py`
- `memory2/query_rewriter.py`
- `memory2/hyde_enhancer.py`
- `plugins/default_memory/engine.py`
- `agent/retrieval/default_pipeline.py`

## 测试结论

2026-07-02 初步测试结果：

- 显式 `memorize` 工具写入成功。
- 写入记忆类型为 `preference`。
- 写入结果包含 `item_id=34365e5aa980`，状态为 `new`。
- `recall_memory` 工具在后续问题中被调用，并命中该记忆。
- 最终追问没有再次调用 `recall_memory`，但由于当前 session history 已经包含相关信息，因此属于合理现象。

发现的问题：

- 对“document rag 和个人记忆 rag 有什么区别？”这类概念解释问题，模型调用了较多工具，包括 `recall_memory`、`list_dir`、`read_file`，存在工具过度探索倾向。
- 后续可考虑通过工具调用策略、query routing 或 system prompt 约束，减少概念解释类问题的无必要工具调用。

下一步：

- 隔离长期记忆召回测试已完成并通过：退出并重新连接 CLI 后，要求从长期记忆检索“我学习 agent 时最关注哪些方向”，系统调用了 `recall_memory`，命中 `item_id=34365e5aa980`。
- 本轮还调用了 `fetch_messages`，通过 `source_ref=cli:cli-133350246438560:6` 回看原始上下文，说明 source_ref 证据链可用。
- 下一步进入工具调用链路测试，验证正常工具调用、工具错误和工具 trace。

2026-07-03 追加验证：

- 用户再次输入：“请从长期记忆里检索：我学习 agent 时最关注哪些方向？”
- 本地读取 `recall_inspector.jsonl` 确认本轮 `turn_id=ca12c339ff42d705`。
- `context_prepare` 阶段已注入 `item_id=34365e5aa980`，`injected=true`。
- 本轮同时调用了 `recall_memory`，参数为：
  - `query=用户学习 agent 时最关注的三个方向`
  - `memory_type=preference`
- `recall_memory` 返回 `status=success`、`count=1`，命中同一条记忆。
- 结论：长期记忆自动注入和显式 recall_memory 检索都符合预期。

2026-07-03 长期记忆跨 session 与当前会话边界测试通过：

测试过程：

- 一号 CLI 输入：`记住：我的长期测试偏好是 memory-cross-session-test`
- 二号 CLI 输入：`请从长期记忆里检索：我的长期测试偏好是什么？`
- 二号 CLI 再输入：`我刚才在这个会话里说过 memory-cross-session-test 吗？`

实际结果：

- 一号会话 `session_key=cli:cli-133349980485776` 调用了 `memorize`。
- 写入记忆：
  - `item_id=2cd8202927b9`
  - `memory_type=preference`
  - `summary=用户长期测试偏好是 memory-cross-session-test`
  - `source_ref=cli:cli-133349980485776:4`
- 二号会话 `session_key=cli:cli-133350248939024` 的 `context_prepare` 阶段注入了该长期记忆。
- 二号会话能回答长期测试偏好是 `memory-cross-session-test`。
- 当二号会话被问“我刚才在这个会话里说过吗？”时，回答为：没有在这个会话里说过，但长期记忆里有。

结论：

- 长期记忆是跨 session 共享的。
- 短期 session history 仍然按 session 隔离。
- 模型能区分“当前会话里说过”和“长期记忆中知道”。

发现的问题：

- 第三轮 `search_messages` 对二号会话搜索 `memory-cross-session-test` 时返回 `count=0` 但 `matched_count=1`、`has_more=true`、`messages=[]`，结果字段存在轻微不一致，后续可以检查分页或 FTS 计数逻辑。

2026-07-03 记忆纠错 / 覆盖策略测试通过：

测试过程：

- 用户先纠错旧记忆：`刚才那条长期测试偏好需要纠正：我的长期测试偏好不是 memory-cross-session-`
- 随后补充新值：`而是 memory-correction-test`
- 再询问：`请从长期记忆里检索：我的长期测试偏好现在是什么？`
- 最后询问：`我的长期测试偏好以前是什么？现在是什么？`

实际结果：

- 第一轮纠错调用 `forget_memory`，目标为旧记忆 `2cd8202927b9`。
- `forget_memory` 返回 `superseded_ids=["2cd8202927b9"]`。
- 第二轮调用 `memorize` 写入新记忆：
  - `item_id=1f03e6b91580`
  - `summary=用户长期测试偏好是 memory-correction-test`
  - `memory_type=preference`
- 后续 `context_prepare` 只注入新记忆 `1f03e6b91580`。
- `recall_memory` 检索当前长期测试偏好时，命中新记忆，未返回旧测试偏好。
- `memory2.db` 中确认：
  - 旧记忆 `2cd8202927b9` 状态为 `superseded`
  - 新记忆 `1f03e6b91580` 状态为 `active`

结论：

- 旧记忆能被显式遗忘 / 标记为 superseded。
- 新记忆能写入并成为 active。
- 后续回答“当前是什么”时没有被旧记忆误导。
- 模型还能结合当前会话历史回答“以前是什么、现在是什么”。

发现的问题：

- `memory_replacements` 表没有记录 `2cd8202927b9 -> 1f03e6b91580` 的替换关系；当前主要依赖旧条目 `status=superseded` 和新条目 `active`。
- 用户第一条纠错消息似乎被截断为 `memory-cross-session-`，模型先清除了旧记忆，等用户下一条补充后再写入新值；最终结果正确，但说明多轮纠错依赖会话连续性。

2026-07-03 无关技术问题误召回测试部分通过：

测试输入：

```text
请用三句话解释 FastAPI 的 Depends 是什么
```

实际结果：

- observe.db 中出现两轮相同测试：
  - `id=34`，`session_key=cli:cli-133349980485776`
  - `id=35`，`session_key=cli:cli-133349980485136`
- 两轮 `tool_calls` 均为空。
- 没有调用 `recall_memory`。
- 最终回答都只解释了 FastAPI `Depends` 的依赖注入、自动调用依赖函数、复用认证/数据库连接/参数校验等用途。
- 最终回答没有提到：
  - `memory-correction-test`
  - `memory-cross-session-test`
  - agent runtime
  - document RAG
  - 工具治理

结论：

- 对通用技术问题，最终回答没有被个人长期记忆污染。
- 模型没有主动调用 `recall_memory`，工具路由表现正常。

发现的问题：

- `context_prepare` 仍然自动注入了无关个人记忆 `34365e5aa980`：`学习 agent 时最关注三个方面：agent runtime、document RAG、工具治理`。
- 虽然该记忆没有污染最终答案，但这说明自动上下文注入策略偏宽；后续可以优化 memory injection planner，让通用知识问题更少注入无关个人偏好。

2026-07-03 source_ref 回源证据链测试通过：

测试输入：

```text
请从长期记忆里检索我的长期测试偏好，并回看原始消息证据
```

实际结果：

- `context_prepare` 阶段注入当前 active 记忆：
  - `id=1f03e6b91580`
  - `summary=用户长期测试偏好是 memory-correction-test`
  - `source_ref=cli:cli-133349980485776:8`
- 本轮调用 `recall_memory`：
  - `query=用户的长期测试偏好是什么`
  - `memory_type=preference`
  - 命中新记忆 `1f03e6b91580`
- 本轮调用 `fetch_messages`：
  - `source_ref=cli:cli-133349980485776:8`
  - `context=4`
  - 回看到了旧值、纠错、新值写入等上下文。
- 最终回答说明：
  - 最初是 `memory-cross-session-test`
  - 后来纠正为 `memory-correction-test`
  - 当前长期测试偏好是 `memory-correction-test`

结论：

- `source_ref` 能从长期记忆回到原始 session 消息。
- `fetch_messages` 能围绕 source_ref 取回上下文证据。
- 当前 active 记忆没有被旧 superseded 记忆覆盖。
- 最终回答能结合原始证据解释新旧变化。

发现的问题：

- `context_prepare` 除了注入目标记忆外，还额外注入了两条无关历史：读取不存在文件、学习 agent 关注方向。
- 最终回答没有被污染，但自动注入仍然偏宽，和前一轮无关技术问题测试的观察一致。
