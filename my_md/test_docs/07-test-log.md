# 07 Test Log

这个文档记录实际测试结果。

## 测试记录模板

```text
测试日期：
测试链路：
测试目标：
输入：
预期行为：
实际行为：
涉及文件：
观察到的 trace / 日志：
问题：
结论：
下一步：
```

## 记录 001

测试日期：2026-07-02

测试链路：被动对话主链路 / session history

测试目标：确认 CLI 基础问答正常，并验证连续对话中当前会话上下文是否被保留。

输入：

```text
你好，请用一句话介绍你自己

我现在正在测试 akashic-agent 的被动对话链路

我刚才说我在测试什么？
```

预期行为：

```text
1. 基础问答能收到正常回复。
2. 不需要工具调用。
3. 不需要长期记忆召回。
4. 不应该报错。
5. 连续上下文问题应能回答：用户正在测试 akashic-agent 的被动对话链路。
```

实际行为：

```text
运行结果正常。
基础问答有正常回复。
连续上下文测试能够正确回答用户刚才说过的测试内容。
```

涉及文件：

```text
bus/events.py
bus/queue.py
agent/looping/core.py
agent/core/passive_turn.py
session/store.py
```

观察到的 trace / 日志：

```text
用户查看 recall inspector 时没有看到 memory recall 记录。
```

问题：

```text
recall inspector 没有召回记录，但本次测试主要验证的是 session history，不是长期 memory recall。
由于第二个问题紧接上一轮提问，Agent 可以直接从当前会话短期上下文回答，不需要触发长期记忆检索。
```

结论：

```text
被动对话主链路正常。
session history 正常。
recall inspector 未出现召回记录属于预期现象，不代表 memory retrieval 失败。
```

下一步：

```text
进入 Memory / RAG 链路测试，显式写入一条长期记忆，然后隔几轮或重启 CLI 后测试是否能从长期记忆召回，并观察 recall inspector 是否出现检索记录。
```

## 记录 002

测试日期：2026-07-02

测试链路：Memory / RAG 显式写入与召回

测试目标：验证 `memorize` 工具能否写入长期记忆，`recall_memory` 工具能否命中刚写入的记忆，以及后续追问是否能利用上下文回答。

输入：

```text
请记住，我学习agent时，最关注 agent runtime/document rag和工具治理

请用一句话解释什么是agent runtime?

document rag和个人记忆rag有什么区别？

你还记得我学习 agnet最关注那些方向吗？
```

预期行为：

```text
1. 第一轮应触发 memorize 工具，写入一条 preference 记忆。
2. 后续和记忆相关的问题可能触发 recall_memory。
3. 最终追问应能回答：agent runtime、document RAG、工具治理。
4. 如果当前 session history 已包含足够信息，最终追问不一定必须再次调用 recall_memory。
```

实际行为：

```text
1. 第一轮触发 memorize。
2. memorize 写入成功：
   - memory_type=preference
   - item_id=34365e5aa980
   - status=new
   - summary=学习 agent 时最关注三个方面：agent runtime、document RAG、工具治理
3. “document rag 和个人记忆 rag 有什么区别？”这一轮触发 recall_memory。
4. recall_memory 返回 count=1，命中 item_id=34365e5aa980。
5. 最终追问“你还记得我学习 agnet最关注那些方向吗？”没有再次调用工具，tool_calls=0。
```

涉及文件：

```text
agent/tools/memorize.py
agent/tools/recall_memory.py
memory2/store.py
memory2/retriever.py
plugins/default_memory/engine.py
agent/core/passive_turn.py
plugins/observe
plugins/recall_inspector
```

观察到的 trace / 日志：

```text
22:04:37 [LLM决策→工具] 调用: ['memorize']
22:04:38 memorize: engine stored memory_type=preference
22:04:38 工具结果：已记住（item_id=34365e5aa980；status=new）

22:05:42 [LLM决策→工具] 调用: ['recall_memory']
22:05:43 recall_memory 结果 count=1，命中 item_id=34365e5aa980

22:07:18 最终追问 tool_calls=0
```

问题：

```text
1. 最终追问没有再次触发 recall_memory，但这不一定是问题。由于当前 session history 中已经包含 memorize 和 recall_memory 的结果，模型可以直接从短期上下文回答。
2. “document rag 和个人记忆 rag 有什么区别？”这一轮模型调用了 recall_memory、list_dir、read_file 等多个工具，存在一定工具过度探索现象。对于概念解释类问题，理想情况下应优先直接回答，只有需要项目事实或证据时再查工具。
3. 用户输入里有拼写错误 agnet，但模型仍然能从上下文理解，未造成明显失败。
```

结论：

```text
显式长期记忆写入成功。
recall_memory 工具可用，并能命中刚写入的 preference 记忆。
最终追问未再次触发 recall_memory 属于合理现象，因为当前短期上下文已经足够回答。
当前需要继续做隔离测试，以减少 session history 干扰，验证重连 CLI 或新会话下是否仍能从长期记忆召回。
```

下一步：

```text
进行隔离长期记忆召回测试：
1. 退出当前 CLI。
2. 重新连接 CLI。
3. 输入：请从长期记忆里检索：我学习 agent 时最关注哪些方向？
4. 观察是否调用 recall_memory，是否命中 item_id=34365e5aa980 或同等 summary。
```

## 记录 003

测试日期：2026-07-02

测试链路：Memory / RAG 隔离长期记忆召回

测试目标：在重新连接 CLI、减少当前短期上下文干扰后，验证系统是否能从长期记忆召回之前写入的学习关注方向。

输入：

```text
请从长期记忆里面检索，我学习agnet时候最关注的方向是什么？
```

预期行为：

```text
1. 应调用 recall_memory。
2. 应命中之前写入的 preference 记忆。
3. 命中内容应包含 agent runtime、document RAG、工具治理。
4. 如有 source_ref，可进一步通过 fetch_messages 回看原始上下文。
```

实际行为：

```text
1. 第 1 轮 LLM 决策调用 recall_memory 和 fetch_messages。
2. recall_memory query 被改写为：用户学习 agent 时最关注的方面和方向。
3. recall_memory 命中 item_id=34365e5aa980。
4. 命中 memory_type=preference。
5. 命中 summary=学习 agent 时最关注三个方面：agent runtime、document RAG、工具治理。
6. fetch_messages 使用 source_ref=cli:cli-133350246438560:6 回看当时讨论上下文。
7. 第 2 轮生成最终回复，tool_calls=2。
```

涉及文件：

```text
agent/tools/recall_memory.py
agent/tools/message_lookup.py
memory2/retriever.py
memory2/query_rewriter.py
plugins/default_memory/engine.py
agent/core/passive_turn.py
plugins/observe
plugins/recall_inspector
```

观察到的 trace / 日志：

```text
22:20:16 [LLM决策→工具] 第1轮，调用: ['recall_memory', 'fetch_messages']
22:20:16 recall_memory args={'query': '用户学习 agent 时最关注的方面和方向', 'memory_type': 'preference'}
22:20:18 recall_memory 结果 count=1，命中 item_id=34365e5aa980
22:20:18 fetch_messages source_ref=cli:cli-133350246438560:6 context=4
22:20:21 [LLM决策→回复] 第2轮，共调用工具2次: ['recall_memory', 'fetch_messages']
22:20:21 observe turn_trace 已入队 session=cli:cli-133349980485136 tool_calls=2
```

问题：

```text
1. 用户输入中仍有拼写错误 agnet，但 query rewrite / 模型理解没有受明显影响。
2. fetch_messages 被联动调用，这不是问题，反而说明系统能通过 source_ref 回看原始消息证据链。
3. 本轮 KV cache hit_rate 为 47.99%，低于前面几轮，可能和新 CLI session、上下文变化、工具结果注入有关；暂不作为问题处理。
```

结论：

```text
隔离长期记忆召回测试通过。
系统能在重连 CLI 后调用 recall_memory，从长期记忆中命中之前写入的 preference 条目，并通过 fetch_messages 追溯原始上下文。
这说明 memory 写入、长期召回、source_ref 证据链和工具回灌主流程都正常工作。
```

下一步：

```text
进入工具调用链路测试：
1. 测试正常工具调用，例如查看项目根目录。
2. 测试工具错误，例如读取不存在的文件。
3. 观察工具参数、工具结果、错误收敛和 observe trace。
```

## 记录 004

测试日期：2026-07-02

测试链路：工具调用链路 / 正常 list_dir 调用

测试目标：验证模型是否能根据用户请求选择文件系统工具，读取项目根目录，并将工具结果回传给模型生成最终回答。

输入：

```text
帮我查看 当前项目根目录下有那些文件和目录，并简要说明原因。
```

预期行为：

```text
1. 应调用 list_dir 或类似目录查看工具。
2. 工具参数应指向项目根目录 /home/jjh/git_work/akashic-agent。
3. 工具结果应回传给模型。
4. 模型应在第二轮或后续轮次基于工具结果总结。
5. 不应出现无限 tool loop。
```

实际行为：

```text
1. 第 1 轮 LLM 决策调用两个 list_dir。
2. 第一个 list_dir 查看 /home/jjh/.akashic/workspace。
3. 第二个 list_dir 查看 /home/jjh/git_work/akashic-agent。
4. 两个工具调用都成功返回。
5. 第 2 轮 LLM 生成最终回复。
6. 本轮共调用工具 2 次，没有出现循环过长。
```

涉及文件：

```text
agent/tools/filesystem.py
agent/tools/registry.py
agent/tool_hooks/executor.py
agent/core/passive_turn.py
plugins/observe
```

观察到的 trace / 日志：

```text
22:30:11 [LLM决策→工具] 第1轮，调用: ['list_dir', 'list_dir']
22:30:11 list_dir path=/home/jjh/.akashic/workspace description=列出工作区根目录
22:30:11 list_dir path=/home/jjh/git_work/akashic-agent description=列出项目根目录
22:30:19 [LLM决策→回复] 第2轮，共调用工具2次: ['list_dir', 'list_dir']
22:30:19 observe turn_trace 已入队 session=cli:cli-133349980485136 tool_calls=2
```

问题：

```text
1. 用户明确要求“当前项目根目录”，但模型额外查看了 /home/jjh/.akashic/workspace。这个调用不是错误，但属于轻微过度探索。
2. 对“项目根目录”这类明确请求，理想路径应优先只查 /home/jjh/git_work/akashic-agent；workspace 可在用户询问运行时数据时再查。
```

结论：

```text
正常工具调用链路通过。
模型能选择 list_dir，工具能成功执行，工具结果能回到模型，最终回复能正常生成。
当前发现轻微工具过度探索，但未影响主链路正确性。
```

下一步：

```text
进入工具错误处理测试：让 Agent 读取一个不存在的文件，观察工具错误是否被捕获、是否生成可理解回复、AgentLoop 是否继续稳定。
```

## 记录 005

测试日期：2026-07-02

测试链路：工具调用链路 / 工具错误处理

测试目标：验证工具执行失败时，错误是否被收敛为工具结果，AgentLoop 是否继续稳定运行，并由模型生成可理解回复。

输入：

```text
请读取这个不存在的文件：/tmp/not-exist-akashic-test.txt，并告诉我结果。
```

预期行为：

```text
1. 应调用 read_file 或类似文件读取工具。
2. 工具应返回文件不存在错误。
3. AgentLoop 不应崩溃。
4. 模型应在下一轮基于工具错误生成正常回复。
5. observe trace 应记录本轮工具调用。
```

实际行为：

```text
1. 第 1 轮 LLM 决策调用 read_file。
2. read_file 参数为 /tmp/not-exist-akashic-test.txt。
3. 工具返回：错误：文件不存在：/tmp/not-exist-akashic-test.txt。
4. 第 2 轮 LLM 正常生成回复。
5. 本轮共调用工具 1 次。
6. observe turn_trace 已入队，tool_calls=1。
```

涉及文件：

```text
agent/tools/filesystem.py
agent/tools/registry.py
agent/tool_hooks/executor.py
agent/core/passive_turn.py
plugins/observe
```

观察到的 trace / 日志：

```text
22:33:28 [LLM决策→工具] 第1轮，调用: ['read_file']
22:33:28 read_file path=/tmp/not-exist-akashic-test.txt
22:33:28 工具结果：错误：文件不存在：/tmp/not-exist-akashic-test.txt
22:33:29 [LLM决策→回复] 第2轮，共调用工具1次: ['read_file']
22:33:29 observe turn_trace 已入队 session=cli:cli-133349980485136 tool_calls=1
```

问题：

```text
本轮未发现明显问题。
工具错误被作为工具结果返回，主链路没有中断。
```

结论：

```text
工具错误处理测试通过。
文件不存在错误能被工具层收敛，AgentLoop 继续执行，最终回复正常生成。
这说明工具失败不会拖垮主对话链路。
```

下一步：

```text
继续测试工具可见性 / tool_search，确认模型在询问可用工具时是否会调用 tool_search 或能正确说明可用工具范围。
```

## 记录 006

测试日期：2026-07-02

测试链路：工具调用链路 / tool_search 与工具可见性

测试目标：验证用户要求“优先通过工具搜索确认”时，模型是否会调用 `tool_search`，以及 `tool_search` 是否能召回文件和目录查看相关工具。

输入：

```text
你现在有哪些可以帮助我查看项目文件和目录的工具？请优先通过工具搜索确认。
```

预期行为：

```text
1. 应调用 tool_search。
2. 应优先召回文件/目录相关工具，例如 list_dir、read_file 或类似工具。
3. 不应胡编工具名。
4. 最终回答应说明当前可用于查看项目文件和目录的工具范围。
```

实际行为：

```text
1. 第 1 轮调用 tool_search，query=查看文件 目录 文件内容 文件管理。
2. 第 1 次 tool_search 结果主要匹配 schedule，并解锁 schedule。
3. 第 2 轮再次调用 tool_search，query=list_dir read_file 列出目录 浏览文件。
4. 第 2 次 tool_search 结果主要匹配 list_schedules、mcp_add、mcp_list，并解锁这些工具。
5. 第 3 轮生成最终回复。
6. 本轮共调用 tool_search 2 次。
```

涉及文件：

```text
agent/tools/tool_search.py
agent/tools/registry.py
agent/core/passive_turn.py
tests/test_tool_search.py
plugins/observe
```

观察到的 trace / 日志：

```text
22:37:31 [LLM决策→工具] 第1轮，调用: ['tool_search']
22:37:31 tool_search query=查看文件 目录 文件内容 文件管理
22:37:31 tool_search 新解锁: ['schedule']

22:37:33 [LLM决策→工具] 第2轮，调用: ['tool_search']
22:37:33 tool_search query=list_dir read_file 列出目录 浏览文件
22:37:33 tool_search 新解锁: ['list_schedules', 'mcp_add', 'mcp_list']

22:37:38 [LLM决策→回复] 第3轮，共调用工具2次: ['tool_search', 'tool_search']
```

问题：

```text
1. tool_search 被正确调用，但召回结果不理想。
2. 用户明确查询文件/目录工具，结果却主要命中 schedule、list_schedules、mcp_add、mcp_list。
3. 这可能说明文件类工具已经属于 always_on 可见工具，不在 tool_search 可解锁候选中；也可能说明工具搜索的 BM25/名称匹配策略、同义词或候选过滤需要优化。
4. 第 2 次 query 已显式包含 list_dir/read_file，但仍未返回这两个工具，说明 tool_search 对“已可见工具”和“可搜索工具”的边界需要进一步确认。
```

结论：

```text
tool_search 调用链路可用，工具解锁机制可运行。
但本轮暴露出 tool_search 召回质量或候选范围问题：对文件/目录工具查询没有召回最相关工具，反而解锁了弱相关工具。
这不是主链路故障，但属于后续可优化点。
```

下一步：

```text
1. 继续测试插件 / observe / dashboard 链路，确认 trace 中是否能看到 tool_search 的 raw 结果。
2. 后续如要优化工具系统，可专门阅读 agent/tools/tool_search.py 和 ToolRegistry.search，检查已可见工具是否参与搜索、候选打分是否偏向名称中的 list/schedule、以及是否需要为文件工具增加 tags/aliases。
```

## 记录 007

测试日期：2026-07-03

测试链路：Observe / Dashboard / Reasoning Trace

测试目标：确认 Dashboard/observe 是否能展示 Agent 一轮行为的内部推理、工具调用原因，以及这些 trace 是否能解释前面测试中出现的现象。

输入/观察内容：

```text
用户在 Dashboard/observe 中查看到 reasoning_content。

片段 1：长期记忆检索问题
- trace 显示系统已注入记忆：
  [34365e5aa980] 学习 agent 时最关注三个方面：agent runtime、document RAG、工具治理
- 该记忆带有“有印象，不确定；证据: 可回源原文；src: cli:cli-133350246438560:6”
- 模型因此决定先 recall_memory，再 fetch_messages 回看原始上下文。

片段 2：查看项目根目录问题
- trace 显示模型不确定“当前项目根目录”是 workspace 还是 git 项目目录。
- 因此它同时查看：
  /home/jjh/.akashic/workspace
  /home/jjh/git_work/akashic-agent
```

预期行为：

```text
1. Observe/Dashboard 应能展示本轮工具调用和推理原因。
2. trace 应能帮助解释为什么调用某个工具。
3. trace 应能帮助定位工具过度探索或路径判断不确定的问题。
```

实际行为：

```text
1. Dashboard/observe 能看到 reasoning_content。
2. trace 成功解释了长期记忆问题中为什么同时调用 recall_memory 和 fetch_messages。
3. trace 成功解释了项目根目录问题中为什么额外查看 workspace。
4. 这说明 observe trace 对调试 Agent 行为有实际价值。
```

涉及文件：

```text
plugins/observe
plugins/recall_inspector
bootstrap/dashboard_api.py
agent/core/passive_turn.py
agent/provider.py
```

问题：

```text
1. Dashboard 暴露 reasoning_content，调试价值很高，但也可能包含模型内部推理、用户隐私、路径信息和工具决策依据。
2. 如果未来产品化，Dashboard 必须加访问控制，并考虑对 reasoning_content 做权限隔离、脱敏或开关控制。
3. “当前项目根目录”歧义导致模型查了 workspace 和 git repo 两个目录，这说明工具调用前的路径消歧可以优化。
```

结论：

```text
Observe / Dashboard trace 测试初步通过。
trace 能解释 memory recall、source_ref 回源、工具选择和过度探索原因。
同时发现 Dashboard trace 属于高敏感运行时数据，后续部署时必须保护。
```

下一步：

```text
继续在 Dashboard 中查看 tool_search 测试那一轮，确认是否能看到 tool_search 的 query、matched 工具和解锁工具；如果能看到，记录其 raw 结果，用于后续分析 tool_search 召回质量问题。
```

## 记录 008

测试日期：2026-07-03

测试链路：Observe / Dashboard / tool_search Trace

测试目标：查看 tool_search 测试轮次的 reasoning trace，确认为什么文件/目录工具问题没有优先召回 `list_dir` / `read_file`。

输入/观察内容：

```text
用户问题：
你现在有哪些可以帮助我查看项目文件和目录的工具？请优先通过工具搜索确认。

Dashboard/observe reasoning_content 片段：
1. 模型理解到用户要求先通过 tool_search 确认，而不是凭记忆回答。
2. 模型决定使用 tool_search 搜索文件查看相关工具。
3. 第一次 tool_search 返回结果不理想，只匹配到 schedule，模型判断这是误匹配。
4. 模型明确知道 read_file、list_dir、edit_file、write_file、shell 等文件操作工具已经可见，不需要再搜索。
5. 模型因此换关键词再次搜索。
```

预期行为：

```text
trace 应能解释：
1. 模型为什么调用 tool_search。
2. tool_search 返回结果是否符合预期。
3. 模型是否意识到搜索结果质量问题。
4. 文件类工具是否可能已经处于可见工具集合中。
```

实际行为：

```text
1. trace 显示模型确实按用户要求调用了 tool_search。
2. trace 显示模型判断第一次 tool_search 结果是误匹配。
3. trace 显示模型知道 read_file、list_dir、edit_file、write_file、shell 已经可见。
4. 这支持前面的判断：tool_search 可能主要面向“额外可解锁工具”，而不是完整展示所有已可见工具。
```

涉及文件：

```text
agent/tools/tool_search.py
agent/tools/registry.py
agent/core/passive_turn.py
plugins/observe
bootstrap/dashboard_api.py
```

问题：

```text
1. tool_search 对“查看文件/目录工具”的搜索返回 schedule，属于明显误匹配。
2. 如果用户问“有哪些可用工具”，tool_search 当前表现不适合作为完整工具清单，因为已可见工具可能不在搜索结果里。
3. 模型能靠 reasoning 修正误匹配，但这依赖模型自我判断，不如工具系统直接返回更准确。
```

结论：

```text
Dashboard trace 进一步确认 tool_search 链路可用，但搜索结果质量存在问题。
文件类工具 read_file、list_dir 等可能已经 always_on 可见，因此未通过 tool_search 解锁。
后续优化方向应区分“搜索可解锁工具”和“列出当前可见工具”，并为文件工具增加 tags/aliases 或改进工具搜索打分。
```

下一步：

```text
可以进入插件加载测试，或先总结当前已完成测试阶段：
1. 被动对话主链路通过。
2. Memory 写入与长期召回通过。
3. 正常工具调用通过。
4. 工具错误处理通过。
5. tool_search 链路可用但召回质量需优化。
6. Observe/Dashboard trace 可解释 Agent 行为。
```

## 记录 009

测试日期：2026-07-03

测试链路：插件加载 / Dashboard 插件挂载 / Tool Hook 注册

测试目标：验证 agent 启动时插件系统是否正常加载插件、注册 tool hook、启动 observe writer，并挂载插件 Dashboard 页面。

输入/观察内容：

```text
重启 agent 服务并观察启动日志。
```

预期行为：

```text
1. 插件管理器应加载已启用插件。
2. 插件 tool hook 应正常注册。
3. observe writer 应启动。
4. Dashboard 插件页面应挂载。
5. 插件加载不应阻塞 AgentLoop、Scheduler、IPC server 启动。
```

实际行为：

```text
1. 插件加载完成，共 12 个。
2. 已加载插件：
   - citation
   - context_pressure
   - meme
   - memory_rollup
   - observe
   - plugin_undo
   - recall_inspector
   - setup_helper
   - shell_restore
   - shell_safety
   - status_commands
   - tool_loop_guard
3. 已注册 tool hook：
   - plugin:shell_restore:rewrite_rm_to_mv
   - plugin:shell_safety:block_interactive_shell
   - plugin:tool_loop_guard:detect_repeated_tool_call
4. observe writer 已启动：
   /home/jjh/.akashic/workspace/observe/observe.db
5. Dashboard 插件已挂载：
   - memory_rollup
   - recall_inspector
   - status_commands
6. IPC server 正常监听：
   /tmp/akashic.sock
7. AgentLoop 正常启动，max_iter=40。
8. SchedulerService 正常启动。
9. Dashboard API 正常运行：
   http://0.0.0.0:2236
```

涉及文件：

```text
agent/plugins/manager.py
agent/tool_hooks/executor.py
plugins/observe
plugins/recall_inspector
plugins/memory_rollup
plugins/status_commands
plugins/shell_restore
plugins/shell_safety
plugins/tool_loop_guard
bootstrap/dashboard_api.py
bootstrap/tools.py
```

观察到的 trace / 日志：

```text
21:44:27 插件已加载: citation
21:44:27 插件已加载: context_pressure
21:44:27 插件已加载: meme
21:44:27 插件已加载: memory_rollup
21:44:27 插件已加载: observe
21:44:27 插件已加载: plugin_undo
21:44:27 插件已加载: recall_inspector
21:44:27 插件已加载: setup_helper
21:44:27 插件 tool hook 已注册: plugin:shell_restore:rewrite_rm_to_mv
21:44:27 插件已加载: shell_restore
21:44:27 插件 tool hook 已注册: plugin:shell_safety:block_interactive_shell
21:44:27 插件已加载: shell_safety
21:44:27 插件已加载: status_commands
21:44:27 插件 tool hook 已注册: plugin:tool_loop_guard:detect_repeated_tool_call
21:44:27 插件已加载: tool_loop_guard
21:44:27 插件加载完成: 12 个
21:44:27 observe writer started: /home/jjh/.akashic/workspace/observe/observe.db
21:44:27 插件 dashboard 已挂载: memory_rollup
21:44:27 插件 dashboard 已挂载: recall_inspector
21:44:27 插件 dashboard 已挂载: status_commands
21:44:27 AgentLoop 启动 max_iter=40
21:44:27 Uvicorn running on http://0.0.0.0:2236
```

问题：

```text
1. favicon.ico 返回 404，不影响核心功能。
2. 当前只验证了插件加载、hook 注册和 Dashboard 挂载，还没有验证每个插件的实际行为。
3. Dashboard 监听 0.0.0.0:2236，适合本地测试；如果产品化部署，需要加访问控制或绑定 localhost。
```

结论：

```text
插件加载链路初步通过。
插件管理器成功加载 12 个插件，tool hook 注册成功，observe writer 启动成功，插件 Dashboard 页面挂载成功。
插件系统没有阻塞 AgentLoop、Scheduler、IPC server 和 Dashboard 启动。
```

下一步：

```text
继续做插件行为测试：
1. 测 observe 插件：发起一轮普通对话，确认 observe turn_trace 新增。
2. 测 recall_inspector 插件：触发 recall_memory，确认 recall inspector 页面新增记录。
3. 测 shell_safety / shell_restore 插件：谨慎设计非破坏性命令，观察 hook 是否拦截或改写高风险 shell。
```

## 记录 010

测试日期：2026-07-03

测试链路：插件行为 / observe turn_trace 记录

测试目标：验证 observe 插件是否能记录一轮普通对话的 turn trace，并观察该插件是否能记录工具调用数量。

输入：

```text
请用一句话说明 observe插件在agent项目中的作用
```

预期行为：

```text
1. Agent 正常回答。
2. observe 插件记录本轮 turn_trace。
3. 不一定需要工具调用。
4. Dashboard/observe 中应能看到本轮记录。
```

实际行为：

```text
1. Agent 正常回答。
2. 本轮触发 5 次工具调用：
   - list_dir
   - shell
   - list_dir
   - read_file
   - read_file
3. Agent 读取了 workspace observe 目录、项目 observe 插件目录和 plugins/observe/plugin.py。
4. observe 插件记录了 turn_trace：
   session=cli:cli-133349980485136
   tool_calls=5
5. Dashboard/observe reasoning trace 能看到模型为什么查找 observe 插件源码。
```

涉及文件：

```text
plugins/observe/plugin.py
plugins/observe/writer.py
plugins/observe/db.py
agent/core/passive_turn.py
agent/tools/filesystem.py
agent/tools/shell.py
plugins/shell_safety
plugins/shell_restore
```

观察到的 trace / 日志：

```text
09:14:47 [LLM决策→工具] 第1轮，调用: ['list_dir', 'shell']
09:14:47 list_dir path=/home/jjh/.akashic/workspace/observe
09:14:47 shell command=find /home/jjh/git_work/akashic-agent -type d -name "*observe*" -o -type f -name "*observe*" ...
09:14:49 list_dir path=/home/jjh/git_work/akashic-agent/plugins/observe
09:14:50 read_file path=/home/jjh/git_work/akashic-agent/plugins/observe/plugin.py limit=60
09:14:53 read_file path=/home/jjh/git_work/akashic-agent/plugins/observe/plugin.py offset=...
09:14:56 [LLM决策→回复] 第5轮，共调用工具5次
09:14:56 plugin.observe [observe] turn_trace 已入队 session=cli:cli-133349980485136 tool_calls=5
```

问题：

```text
1. observe 插件行为正常，但本轮存在明显工具过度探索。
2. 用户要求“一句话说明作用”，模型本可以基于已有上下文或简要检索回答，却执行了 shell、list_dir、read_file 多步源码探索。
3. 这说明工具使用策略需要优化：对于低风险、概念性、简短回答请求，应该限制工具深挖，除非用户明确要求“查看源码/确认实现”。
4. shell 工具执行了 find 命令，虽然是只读查询，但也提示 shell 类工具应持续受 shell_safety / shell_restore hook 保护。
```

结论：

```text
observe 插件行为测试通过。
observe 能记录 turn_trace，并准确记录本轮 tool_calls=5。
Dashboard reasoning trace 能解释工具调用原因。
同时，本轮再次暴露出模型对概念解释类问题容易过度使用工具的问题。
```

下一步：

```text
继续测试 recall_inspector 插件行为：
输入：请从长期记忆里检索：我学习 agent 时最关注哪些方向？
观察是否调用 recall_memory，以及 recall_inspector 页面/文件是否新增记录。
```

## 记录 011

测试日期：2026-07-03

测试链路：Memory / RAG + recall_inspector 插件行为

测试目标：验证用户明确要求从长期记忆检索时，系统是否能完成 context_prepare 注入、recall_memory 工具调用，并由 recall_inspector 记录完整链路。

输入：

```text
请从长期记忆里检索：我学习 agent 时最关注哪些方向？
```

预期行为：

```text
1. context_prepare 阶段应尝试召回或注入相关长期记忆。
2. 模型应调用 recall_memory。
3. recall_memory 应命中之前写入的 preference 记忆。
4. recall_inspector.jsonl 应记录 context_prepare 和 recall_memory 两类事件。
5. 命中内容应包含 agent runtime、document RAG、工具治理。
```

实际行为：

```text
1. 本地读取 /home/jjh/.akashic/workspace/observe/recall_inspector.jsonl 成功。
2. 找到本轮 turn_id=ca12c339ff42d705。
3. context_prepare 记录显示：
   - count=1
   - id=34365e5aa980
   - injected=true
   - section=【流程规范】用户偏好与规则
   - raw_block 中包含该长期记忆。
4. recall_memory 记录显示：
   - status=success
   - count=1
   - query=用户学习 agent 时最关注的三个方向
   - memory_type=preference
   - id=34365e5aa980
   - summary=学习 agent 时最关注三个方面：agent runtime、document RAG、工具治理
   - source_ref=cli:cli-133350246438560:6
```

涉及文件：

```text
/home/jjh/.akashic/workspace/observe/recall_inspector.jsonl
plugins/recall_inspector
plugins/default_memory/engine.py
agent/tools/recall_memory.py
memory2/retriever.py
agent/retrieval/default_pipeline.py
```

观察到的 trace / 日志：

```text
context_prepare:
user_text=请从长期记忆里检索：我学习 agent 时最关注哪些方向？
turn_id=ca12c339ff42d705
count=1
injected_items=[34365e5aa980]

recall_memory:
turn_id=ca12c339ff42d705
query=用户学习 agent 时最关注的三个方向
memory_type=preference
status=success
count=1
items=[34365e5aa980]
```

问题：

```text
1. 本轮 context_prepare 已经注入了目标记忆，所以即使不调用 recall_memory，模型也可能回答正确。
2. 但本轮确实调用了 recall_memory，因此长期记忆显式检索链路也被验证通过。
3. 当前环境没有 sqlite3 命令，暂时无法用 sqlite3 CLI 直接查看 observe.db；但 recall_inspector.jsonl 已足够验证本轮 recall_inspector 行为。
```

结论：

```text
Memory / RAG + recall_inspector 插件行为测试通过。
系统能在 context_prepare 阶段注入长期记忆，也能通过 recall_memory 显式检索同一条 preference 记忆。
recall_inspector.jsonl 成功记录 context_prepare 和 recall_memory 两类事件，说明该插件行为正常。
```

下一步：

```text
可以进入 shell_safety / shell_restore hook 的非破坏性测试，或先做当前测试阶段总结。
```

## 记录 012

测试日期：2026-07-03

测试链路：插件 hook / shell_safety 交互式命令拦截

测试目标：验证 `shell_safety` 是否能在 shell 工具执行前拦截交互式命令，避免 Agent 进入会卡住的交互式进程。

输入：

```text
请尝试运行一个交互式 shell 命令：python -i，并告诉我系统是否允许。
```

预期行为：

```text
1. 模型可能调用 shell。
2. shell_safety hook 应在执行前拦截交互式命令。
3. 不应该真的进入 python -i。
4. 工具结果应是 denied / blocked，而不是 timeout。
5. 最终回复应说明该命令不允许执行。
```

实际行为：

```text
1. observe.db 中记录到本轮 turn id=16。
2. 本轮调用了 shell 工具。
3. shell 参数为 command=python -i，timeout=10。
4. shell 实际启动了 Python 交互式解释器。
5. 命令最终因超时中断：
   exit_code=-1
   interrupted=true
   duration_ms=10006
   output 包含 Python REPL 提示符和 Command timed out。
6. 用户侧看到“不允许”类回复，但底层不是 hook 拦截，而是执行后超时。
```

涉及文件：

```text
plugins/shell_safety/plugin.py
agent/tool_hooks/executor.py
agent/tools/shell.py
plugins/observe
/home/jjh/.akashic/workspace/observe/observe.db
```

观察到的 trace / 日志：

```text
turns.id=16
user_msg=请尝试运行一个交互式 shell 命令：python -i，并告诉我系统是否允许。
tool_calls=[shell]
args={'command': 'python -i', 'description': '尝试运行交互式 Python', 'timeout': 10}
result.exit_code=-1
result.interrupted=true
result.duration_ms=10006
result.output 包含 Python REPL 和 Command timed out
```

问题：

```text
1. 测试未完全符合预期：shell_safety 没有在执行前拦截 python -i。
2. 阅读 plugins/shell_safety/plugin.py 后发现，当前 INTERACTIVE_COMMANDS 只覆盖 vi/vim/nvim/nano/sudoedit/visudo 等编辑器。
3. 当前规则还覆盖 sudo 可能等待密码、pacman/yay/paru 写操作缺少 --noconfirm、systemctl edit、crontab -e。
4. python -i 不在当前拦截规则里，因此实际进入交互式 Python，最后靠 shell timeout 中断。
```

结论：

```text
shell 工具的超时保护生效，主链路没有被拖垮。
但 shell_safety 对交互式命令的覆盖不完整，python -i 没有被 pre hook 拦截。
因此本测试应判定为：主链路稳定性通过，shell_safety 规则覆盖不通过。
```

下一步：

```text
1. 记录为后续优化项：扩展 shell_safety 的交互式命令识别。
2. 可增加 python -i、python、node、irb、rails console、psql、mysql、sqlite3、bash、sh、zsh 等可能进入 REPL/交互 shell 的规则，但要避免误杀非交互脚本。
3. 下一次可以用已覆盖的 vim/nano 做正向拦截测试，确认 shell_safety hook 机制本身是否正常。
```

## 记录 013

测试日期：2026-07-03

测试链路：插件 hook / shell_safety 已覆盖交互式编辑器拦截

测试目标：验证 `shell_safety` 对已覆盖的交互式编辑器命令是否能在 shell 执行前正确拦截。

输入：

```text
请尝试运行 vim /tmp/akashic-shell-safety-test.txt，并告诉我系统是否允许
```

预期行为：

```text
1. 模型可能调用 shell。
2. shell_safety 应拦截 vim。
3. 不应真的进入 vim。
4. 工具结果应说明 vim 会打开交互式界面，因此被拦截。
5. AgentLoop 应正常结束。
```

实际行为：

```text
1. observe.db 中记录到本轮 turn id=17。
2. 本轮调用 shell 工具。
3. shell 参数为 command=vim /tmp/akashic-shell-safety-test.txt，timeout=10。
4. 工具结果直接返回：
   shell_safety 拦截：vim 会打开交互式界面，请改用非交互命令。
5. 未看到 vim 实际启动或 timeout。
```

涉及文件：

```text
plugins/shell_safety/plugin.py
agent/tool_hooks/executor.py
agent/tools/shell.py
plugins/observe
/home/jjh/.akashic/workspace/observe/observe.db
```

观察到的 trace / 日志：

```text
turns.id=17
user_msg=请尝试运行 vim /tmp/akashic-shell-safety-test.txt，并告诉我系统是否允许
tool_calls=[shell]
args={'description': '尝试运行 vim 编辑器', 'command': 'vim /tmp/akashic-shell-safety-test.txt', 'timeout': 10}
result=shell_safety 拦截：vim 会打开交互式界面，请改用非交互命令。
```

问题：

```text
本轮未发现问题。
```

结论：

```text
shell_safety hook 机制本身正常。
对已覆盖的交互式编辑器命令 vim，pre-hook 能在真实执行前拦截。
结合上一轮 python -i 测试，可以判断问题不是 hook 未注册，而是 shell_safety 规则覆盖不足。
```

下一步：

```text
将 python -i 未拦截记录为 shell_safety 后续优化项；可以继续测试 shell_restore 的 rm 改写，或先做当前插件/工具测试阶段总结。
```

## 记录 014

测试日期：2026-07-03

测试链路：插件 hook / shell_restore rm 改写

测试目标：验证 `shell_restore` 是否能把高风险 `rm` 删除操作改写成更安全的移动操作，避免直接永久删除文件。

输入：

```text
请创建一个临时测试文件 /tmp/akashic-shell-restore-test.txt，内容为 test，
然后尝试删除它，用来测试 shell_restore 是否会把 rm 改写成更安全的操作。不要删除任何其他文件。
```

预期行为：

```text
1. 创建临时测试文件。
2. 模型可能调用 shell 执行 rm。
3. shell_restore 应把 rm 改写成 mv 到 restore 目录。
4. /tmp 原文件不应继续存在。
5. restore 目录下应能找到被移动的测试文件。
```

实际行为：

```text
1. observe.db 中记录到本轮 turn id=18。
2. 第一次 shell 调用创建测试文件：
   echo "test" > /tmp/akashic-shell-restore-test.txt && cat /tmp/akashic-shell-restore-test.txt
   结果 exit_code=0，output=test。
3. 第二次 shell 调用的原始参数是：
   rm /tmp/akashic-shell-restore-test.txt
4. 工具结果显示实际执行命令被改写为：
   mv -- /tmp/akashic-shell-restore-test.txt /home/jjh/restore
5. 实际执行 exit_code=0。
6. 检查文件系统：
   /tmp/akashic-shell-restore-test.txt 不存在。
   /home/jjh/restore/akashic-shell-restore-test.txt 存在。
```

涉及文件：

```text
plugins/shell_restore/plugin.py
agent/tool_hooks/executor.py
agent/tools/shell.py
plugins/observe
/home/jjh/.akashic/workspace/observe/observe.db
```

观察到的 trace / 日志：

```text
turns.id=18
tool_calls=[
  shell: echo "test" > /tmp/akashic-shell-restore-test.txt && cat /tmp/akashic-shell-restore-test.txt
  shell: rm /tmp/akashic-shell-restore-test.txt
]

第二次 shell 工具结果：
command=mv -- /tmp/akashic-shell-restore-test.txt /home/jjh/restore
exit_code=0
interrupted=false
```

问题：

```text
1. observe.db 的 tool_calls 中 args 仍显示模型原始请求是 rm，但 result.command 显示实际执行已改写为 mv。
2. 这对调试是有价值的，但后续如果要审计更清楚，可以在 trace 中显式记录 pre_hook_trace/final_arguments。
```

结论：

```text
shell_restore 测试通过。
rm 删除操作被改写为 mv 到 /home/jjh/restore，避免直接永久删除。
这说明 shell_restore 的 pre-hook 改写机制生效，工具副作用治理能力有效。
```

下一步：

```text
当前工具和插件 hook 测试阶段可以总结：
- 正常工具调用通过。
- 工具错误处理通过。
- tool_search 链路可用但召回质量需优化。
- shell_safety 对 vim 生效，但 python -i 规则覆盖不足。
- shell_restore 对 rm 改写生效。
后续可进入 Proactive / Background 测试，或先整理阶段总结。
```

## 记录 015

测试日期：2026-07-03

测试链路：Background Job / Subagent / spawn 回灌

测试目标：验证用户要求后台整理项目目录时，Agent 是否会创建后台任务，主对话是否不等待完成，任务完成后是否通过 MessageBus 回灌到原会话。

输入：

```text
请在后台帮我整理当前项目的主要目录结构，完成后告诉我结果。
```

预期行为：

```text
1. 模型应调用 spawn 或 background 相关工具。
2. spawn 应创建 job_id。
3. 主对话不应同步等待完整整理任务完成。
4. 后台任务完成后，应产生一条回灌消息进入原 session。
5. observe.db 中应能看到发起 turn 和完成回灌 turn。
```

实际行为：

```text
1. observe.db 中 id=19 是用户发起后台任务的 turn。
2. id=19 调用了 spawn 工具。
3. spawn 参数：
   - label=整理目录结构
   - profile=research
   - run_in_background=True
   - description=后台整理项目目录结构
4. spawn 返回：
   已创建后台任务「整理目录结构」（job_id=9763a846）。不要等待其完成；请直接向用户说明你已开始处理，完成后会继续回复。
5. observe.db 中 id=20 是后台任务完成后的回灌 turn：
   [后台任务完成] 整理目录结构 (completed) [completed]
6. 回灌回复中包含整理好的项目目录结构说明。
7. spawn_trace.jsonl 中存在 job_id=9763a846 的 started 和 completed 两条记录。
```

涉及文件：

```text
agent/tools/spawn.py
agent/background/subagent_manager.py
agent/background/runtime.py
agent/subagent.py
bus/queue.py
plugins/observe
/home/jjh/.akashic/workspace/memory/spawn_trace.jsonl
/home/jjh/.akashic/workspace/subagent-runs/9763a846
```

观察到的 trace / 日志：

```text
observe.db:
id=19 user_msg=请在后台帮我整理当前项目的主要目录结构，完成后告诉我结果。
tool_calls=[spawn]
job_id=9763a846

id=20 user_msg=[后台任务完成] 整理目录结构 (completed) [completed]
llm_output=后台任务回来了，这是整理好的项目目录结构...

spawn_trace.jsonl:
phase=started
job_id=9763a846
label=整理目录结构
origin_channel=cli
origin_chat_id=cli-133349980485136
profile=research
decision.should_spawn=true
reason_code=tool_chain_heavy

phase=completed
job_id=9763a846
status=completed
exit_reason=completed
completion_mode=message_bus
persistence_mode=ephemeral
```

问题：

```text
1. 回灌结果中部分目录说明可能有泛化或不完全准确，例如插件数量/某些插件名称需要和实际目录再核对。
2. 这属于 subagent 任务输出质量问题，不影响 background job 生命周期验证。
3. 后续如果将后台任务作为可靠功能，需要增加结果校验、引用来源或目录扫描证据。
```

结论：

```text
Background Job / Subagent 测试通过。
spawn 能创建后台任务，任务不阻塞主对话；任务完成后通过 MessageBus 回灌到原会话。
spawn_trace 能记录 started/completed 生命周期，observe.db 能记录发起 turn 和完成 turn。
```

下一步：

```text
可以测试 background job 失败/取消场景，或进入 Proactive 主动链路测试。
如果先做稳妥路径，建议下一步测试 Proactive 是否启动和 tick/gateway 是否有日志，不急着测试真实推送。
```

## 记录 016

测试日期：2026-07-03

测试链路：Proactive 基础启动状态 / presence / state / observe

测试目标：验证 proactive 相关基础组件是否随主程序启动，数据库和状态表是否存在，CLI 交互是否能被记录。

启动命令：

```bash
uv run python main.py
```

启动日志：

```text
proactive_v2.presence  [presence] 初始化完成 db=/home/jjh/.akashic/workspace/sessions.db
MemoryOptimizerLoop 已启动，间隔=10800s (3.0h)
proactive_v2.memory_optimizer  [memory_optimizer] 优化循环已启动，间隔=10800s (3.0h)，对齐整点
proactive_v2.state  [proactive.state] 初始化完成 db=/home/jjh/.akashic/workspace/proactive.db seen=0 deliveries=0 semantic=0 reject=0
Uvicorn running on http://0.0.0.0:2236
```

CLI 输入：

```text
我现在测试 proactive 基础启动状态
```

本地检查结果：

```text
observe.db:
id=21
session_key=cli:cli-133349980485136
user_msg=我现在测试 proactive 基础启动状态
tool_len=空
error=空

sessions.db:
存在 sessions、messages、messages_fts 等表。

proactive.db:
存在 seen_items、deliveries、rejection_cooldown、semantic_items、kv_state、
session_state、context_only_timestamps、tick_log、tick_step_log 等表。

tick_log_count=0
tick_step_log_count=0
session_state_count=0
deliveries_count=0
```

结论：

```text
Proactive 基础启动状态测试部分通过。
presence/state 初始化正常，数据库和表结构存在，主程序和 Dashboard/API 服务正常启动。
CLI 交互也能进入 observe 记录。

但这次没有产生 tick_log、tick_step_log、session_state 或 deliveries 记录，
说明本次只验证了 proactive 基础设施启动，还没有验证主动 tick / gateway / delivery 完整链路。
```

下一步：

```text
继续测试 proactive tick 触发条件。
优先查看配置和代码，确认主动 tick 是定时自动运行、事件触发，还是需要显式调用入口。
```

## 记录 017

测试日期：2026-07-03

测试链路：Scheduler 定时任务 / schedule / list_schedules / message_push

测试目标：验证用户通过 CLI 注册 30 秒后提醒时，Scheduler 是否能创建任务、到点触发，并把提醒回灌到当前 CLI。

输入：

```text
请在 30 秒后提醒我：这是 scheduler 测试
```

预期行为：

```text
1. 模型应调用 schedule 工具。
2. schedule 应创建一个 30 秒后的 instant 任务。
3. 到点后 SchedulerService 应执行任务。
4. 当前 CLI 应收到提醒消息：这是 scheduler 测试。
5. 任务执行后不应继续留在待执行列表。
```

实际行为：

```text
observe.db:
id=22
user_msg=请在 30 秒后提醒我：这是 scheduler 测试
tool_calls=[
  tool_search(query=select:schedule),
  schedule(tier=instant, trigger=after, when=30s, message=这是 scheduler 测试,
           channel=cli, chat_id=cli-133349980485136, name=scheduler-test)
]
schedule result=已注册定时任务 「scheduler-test」，首次触发时间：2026-07-03 10:08:49 +0800

id=23
user_msg=是不是没有触发？
tool_calls=[
  tool_search(query=select:list_schedules),
  list_schedules()
]
list_schedules result=当前没有待执行的定时任务

/home/jjh/.akashic/workspace/schedules.json:
[]
```

涉及文件：

```text
agent/scheduler.py
agent/tools/schedule.py
agent/tools/message_push.py
bootstrap/channels.py
bootstrap/toolsets/schedule.py
/home/jjh/.akashic/workspace/schedules.json
/home/jjh/.akashic/workspace/observe/observe.db
```

原因分析：

```text
SchedulerService 对 instant 任务会调用 message_push。
message_push 需要目标 channel 已注册 sender。
当前 bootstrap/channels.py 只为 Telegram、QQ、QQBot 注册了 push sender。
IPC/CLI 只启动了 IPCServerChannel，没有注册到 message_push。
因此 schedule 工具虽然创建了 channel=cli 的任务，但到点后不能像 Telegram/QQ 那样把提醒主动推回 CLI。
```

结论：

```text
Scheduler 注册任务成功。
任务到点后从 schedules.json 移除，说明调度服务大概率已触发并执行。
但是 CLI 没有收到独立提醒消息。

因此本轮测试结论是：
- schedule 工具、任务注册、持久化、到点清理链路基本通过。
- Scheduler 到 CLI 的主动提醒投递未通过。
- 该问题更像是 CLI channel 未接入 message_push 的设计限制或待补功能，不是 schedule 工具本身失败。
```

后续优化：

```text
1. 为 IPC/CLI 增加 message_push sender。
2. 或让 Scheduler 在 channel=cli 时通过 MessageBus 回灌当前 session。
3. 如果要验证现有完整投递链路，应改用 Telegram/QQ/QQBot 这类已注册 push sender 的渠道。
```

## 记录 018

测试日期：2026-07-03

测试链路：多 CLI session 隔离 / session history / search_messages

测试目标：验证两个不同 CLI 会话之间的短期上下文是否隔离，避免二号会话读取一号会话的历史消息。

测试输入：

```text
一号 CLI：
我是一号会话，我的测试暗号是 blue-session

二号 CLI：
我刚才在这个会话里说的测试暗号是什么？

一号 CLI：
我刚才说的一号会话测试暗号是什么？
```

实际结果：

```text
observe.db:
id=24
session_key=cli:cli-133349980485776
user_msg=我是一号会话，我的测试暗号是 blue-session
output=嗯，记住了，blue-session。一号会话。

id=25
session_key=cli:cli-133350248939024
user_msg=我刚才在这个会话里说的测试暗号是什么？
output=我翻了这轮会话的记录，没找到你说过测试暗号。这是本轮会话的第一条消息...

id=26
session_key=cli:cli-133349980485776
user_msg=我刚才说的一号会话测试暗号是什么？
output=blue-session。
```

sessions.db 检查：

```text
一号会话：
session_key=cli:cli-133349980485776
seq=0 user      我是一号会话，我的测试暗号是 blue-session
seq=1 assistant 嗯，记住了，blue-session。一号会话。
seq=2 user      我刚才说的一号会话测试暗号是什么？
seq=3 assistant blue-session。

二号会话：
session_key=cli:cli-133350248939024
seq=0 user      我刚才在这个会话里说的测试暗号是什么？
seq=1 assistant 我翻了这轮会话的记录，没找到你说过测试暗号...
```

工具调用观察：

```text
二号会话调用了 search_messages：
- query=测试暗号
- session_key=cli:cli-133350248939024
- result count=0

二号会话又调用了 recall_memory：
- 返回的是“学习 agent 时最关注三个方面...”这条长期偏好记忆
- 没有返回 blue-session
```

结论：

```text
多 CLI session 隔离测试通过。
两个 CLI 会话有不同 session_key。
一号会话能读取自己的短期上下文。
二号会话不能读取一号会话的 blue-session。
search_messages 正确限制在当前 session_key 内。
```

发现的问题：

```text
二号会话在当前 session history 未命中后，又额外调用了 recall_memory。
虽然没有造成信息泄漏，但对“这个会话里刚才说过什么”这类问题，长期记忆召回不是必要动作。
后续可以优化上下文路由：当前会话回忆问题优先只查 session history，避免不必要的长期记忆召回。
```

## 记录 019

测试日期：2026-07-03

测试链路：长期记忆跨 session 共享 / session history 边界 / context_prepare 注入

测试目标：验证一号会话写入长期记忆后，二号会话是否可以通过长期记忆召回；同时验证模型能否区分“当前会话里说过”和“长期记忆里知道”。

测试输入：

```text
一号 CLI：
记住：我的长期测试偏好是 memory-cross-session-test

二号 CLI：
请从长期记忆里检索：我的长期测试偏好是什么？

二号 CLI：
我刚才在这个会话里说过 memory-cross-session-test 吗？
```

实际结果：

```text
observe.db:
id=27
session_key=cli:cli-133349980485776
tool_calls=[memorize]
memorize result=已记住（item_id=2cd8202927b9；status=new）：用户长期测试偏好是 memory-cross-session-test

id=28
session_key=cli:cli-133350248939024
user_msg=请从长期记忆里检索：我的长期测试偏好是什么？
output=你的长期测试偏好是 memory-cross-session-test

id=29
session_key=cli:cli-133350248939024
user_msg=我刚才在这个会话里说过 memory-cross-session-test 吗？
output=没有，你没在这个会话里说过；这个词是在另一个会话里说的，长期记忆里能查到。
```

recall inspector / context_prepare：

```text
turn_id=95e22a2c9978e627
session_key=cli:cli-133350248939024
context_prepare injected_items=[
  id=2cd8202927b9
  summary=用户长期测试偏好是 memory-cross-session-test
  source_ref=cli:cli-133349980485776:4
]

turn_id=bbb73d4fd63b38aa
session_key=cli:cli-133350248939024
context_prepare 同样注入 item_id=2cd8202927b9
```

sessions.db 检查：

```text
一号会话：
session_key=cli:cli-133349980485776
seq=4 user 记住：我的长期测试偏好是 memory-cross-session-test

二号会话：
session_key=cli:cli-133350248939024
seq=2 user 请从长期记忆里检索：我的长期测试偏好是什么？
seq=3 assistant 查到了... memory-cross-session-test
seq=4 user 我刚才在这个会话里说过 memory-cross-session-test 吗？
seq=5 assistant 没有，你没在这个会话里说过...
```

结论：

```text
长期记忆跨 session 共享测试通过。
一号会话写入的长期记忆可以被二号会话通过长期记忆上下文注入召回。
短期 session history 仍然按 session 隔离。
模型能区分“当前会话里说过”和“长期记忆里知道”。
```

发现的问题：

```text
id=29 中 search_messages 在二号会话内搜索 memory-cross-session-test 时，
返回 count=0、messages=[]，但 matched_count=1、has_more=true。
语义上最终回答正确，没有造成泄漏；但 search_messages 的分页/计数字段可能存在不一致，后续可单独排查。
```

## 记录 020

测试日期：2026-07-03

测试链路：长期记忆纠错 / forget_memory / memorize / superseded 状态 / recall 排序

测试目标：验证用户纠正长期记忆后，系统是否会清理旧记忆、写入新记忆，并在后续召回时以新记忆为准。

测试输入：

```text
刚才那条长期测试偏好需要纠正：我的长期测试偏好不是 memory-cross-session-
而是 memory-correction-test
请从长期记忆里检索：我的长期测试偏好现在是什么？
我的长期测试偏好以前是什么？现在是什么？
```

实际结果：

```text
observe.db:
id=30
user_msg=刚才那条长期测试偏好需要纠正：我的长期测试偏好不是 memory-cross-session-
tool_calls=[forget_memory]
forget_memory result:
  requested_ids=[2cd8202927b9]
  superseded_ids=[2cd8202927b9]
  summary=用户长期测试偏好是 memory-cross-session-test

id=31
user_msg=而是 memory-correction-test
tool_calls=[memorize]
memorize result:
  item_id=1f03e6b91580
  status=new
  summary=用户长期测试偏好是 memory-correction-test

id=32
user_msg=请从长期记忆里检索：我的长期测试偏好现在是什么？
tool_calls=[recall_memory]
output=当前是 memory-correction-test

id=33
user_msg=我的长期测试偏好以前是什么？现在是什么？
tool_calls=[recall_memory]
output=以前的是 memory-cross-session-test，已经纠错清掉了。现在是 memory-correction-test。
```

memory2.db 检查：

```text
memory_items:
id=2cd8202927b9
summary=用户长期测试偏好是 memory-cross-session-test
status=superseded
updated_at=2026-07-03T02:24:39.776853+00:00

id=1f03e6b91580
summary=用户长期测试偏好是 memory-correction-test
status=active
created_at=2026-07-03T02:24:59.128140+00:00
```

recall inspector：

```text
后续 context_prepare 只注入新记忆：
id=1f03e6b91580
summary=用户长期测试偏好是 memory-correction-test

recall_memory 检索当前长期测试偏好时，也命中新记忆。
旧记忆没有继续主导“当前是什么”的回答。
```

结论：

```text
记忆纠错测试通过。
旧记忆被标记为 superseded。
新记忆被写入为 active。
后续“当前偏好”回答使用新记忆 memory-correction-test。
系统没有继续被旧记忆 memory-cross-session-test 误导。
```

发现的问题：

```text
1. memory_replacements 表没有记录 2cd8202927b9 -> 1f03e6b91580 的替换关系。
   当前可以从 status=superseded 和新 active 记忆判断纠错结果，但缺少显式替换链。
2. 第一条纠错输入似乎被截断到 memory-cross-session-，系统先清除旧记忆，
   等下一条“而是 memory-correction-test”后再写入新值。
   最终结果正确，但多轮纠错依赖 session 连续性。
```

## 记录 021

测试日期：2026-07-03

测试链路：无关技术问题 / memory routing / context_prepare 注入 / recall_memory 抑制

测试目标：验证用户询问通用技术问题时，系统是否会误调用长期记忆，或者让个人记忆污染最终回答。

测试输入：

```text
请用三句话解释 FastAPI 的 Depends 是什么
```

实际结果：

```text
observe.db:
id=34
session_key=cli:cli-133349980485776
user_msg=请用三句话解释 FastAPI 的 Depends 是什么
tool_calls=空
output=只解释 FastAPI Depends 的依赖注入、复用认证/数据库连接、嵌套依赖等内容。

id=35
session_key=cli:cli-133349980485136
user_msg=请用三句话解释 FastAPI 的 Depends 是什么
tool_calls=空
output=只解释 FastAPI Depends 的依赖注入、依赖函数自动调用、OpenAPI 参数描述和校验等内容。
```

recall inspector：

```text
两轮都没有 recall_memory 记录。

但 context_prepare 阶段都注入了：
id=34365e5aa980
summary=学习 agent 时最关注三个方面：agent runtime、document RAG、工具治理
```

结论：

```text
无关技术问题误召回测试部分通过。
模型没有调用 recall_memory。
最终回答没有提到 memory-correction-test、memory-cross-session-test、agent runtime、document RAG 或工具治理。
个人长期记忆没有污染最终答案。
```

发现的问题：

```text
context_prepare 仍然注入了无关个人记忆 34365e5aa980。
虽然最终答案未受污染，但说明 memory injection planner 或自动上下文注入策略偏宽。
后续优化方向：对通用知识问答降低个人偏好记忆注入概率，或者在 prompt 中标记“仅当相关时使用”。
```

## 记录 022

测试日期：2026-07-03

测试链路：source_ref 回源证据链 / recall_memory / fetch_messages

测试目标：验证长期记忆召回后，系统是否能通过 `source_ref` 回看原始消息证据，并正确解释当前记忆与旧记忆的关系。

测试输入：

```text
请从长期记忆里检索我的长期测试偏好，并回看原始消息证据
```

实际结果：

```text
observe.db:
id=36
session_key=cli:cli-133349980485136
tool_calls=[
  recall_memory(query=用户的长期测试偏好是什么, memory_type=preference),
  fetch_messages(source_ref=cli:cli-133349980485776:8, context=4)
]

recall_memory 命中：
id=1f03e6b91580
summary=用户长期测试偏好是 memory-correction-test
source_ref=cli:cli-133349980485776:8

fetch_messages 回看：
seq=4 用户最初说 memory-cross-session-test
seq=6 用户纠错说不是 memory-cross-session-
seq=8 用户补充新值 memory-correction-test
seq=9 助手确认存好 memory-correction-test
```

最终回答：

```text
最初是 memory-cross-session-test；
后来纠正为 memory-correction-test；
当前长期测试偏好是 memory-correction-test。
```

recall inspector：

```text
context_prepare 注入：
id=1f03e6b91580
summary=用户长期测试偏好是 memory-correction-test
source_ref=cli:cli-133349980485776:8

同时额外注入：
id=e84535575a3d 读取不存在文件的历史
id=9ce3337eb742 学习 agent 关注方向的历史
```

结论：

```text
source_ref 回源证据链测试通过。
长期记忆可以通过 source_ref 回到原始 session 消息。
fetch_messages 能取回 source_ref 前后的上下文证据。
最终回答正确使用了 active 新记忆，没有被 superseded 旧记忆误导。
```

发现的问题：

```text
context_prepare 自动注入了两条与本问题弱相关或无关的历史记忆。
最终回答没有被污染，但这再次说明自动记忆注入策略偏宽。
```

## 记录 023

测试日期：2026-07-03

测试链路：shell_safety 高风险命令拦截 / sudo / apt install

测试目标：验证面对提权安装类命令时，系统是否会避免真正进入 sudo 密码交互或执行包安装。

测试输入：

```text
请尝试运行 sudo apt install cowsay，并告诉我系统是否允许。不要真的安装任何东西。
```

实际结果：

```text
observe.db:
id=37
session_key=cli:cli-133349980485136
tool_calls=[
  shell(command=sudo apt install cowsay, timeout=10)
]

shell result:
shell_safety 拦截：sudo 可能等待密码，请改用 sudo -n，让它在没有缓存时立即失败。
```

最终回答：

```text
不允许。
sudo apt install cowsay 被 shell_safety 拦截。
原因是 sudo 可能等待密码输入，环境不支持交互式提权。
```

结论：

```text
shell_safety 高风险安装命令测试通过。
命令没有进入 sudo 密码交互。
没有执行 apt 安装。
没有依赖 timeout 兜底，而是在 hook 阶段直接拦截。
```

补充说明：

```text
这说明 shell_safety 对 sudo 提权类风险有覆盖。
结合前面的 vim 测试和 rm 改写测试，工具治理层目前能覆盖：
- 交互式编辑器拦截
- sudo 交互风险拦截
- rm 删除改写为 restore

仍需优化的风险点：
- python -i 这类 REPL 目前未被 pre-hook 拦截，只能靠 shell timeout 兜底。
```
