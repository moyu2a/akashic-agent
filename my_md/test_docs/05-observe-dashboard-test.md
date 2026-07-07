# 05 Observe Dashboard Test

这个文档记录 Observe、Dashboard、Trace 测试。

## 测试目标

验证 Agent 行为是否可观察：

- 一轮对话是否有 trace。
- memory retrieval 是否有 trace。
- 工具调用是否有记录。
- memory 写入是否有记录。
- Dashboard 是否能查看运行状态。

## 重点观察点

- trace 是否能还原一轮对话。
- trace 是否包含 query、retrieval hits、tool calls。
- Dashboard 是否能查看 session、memory、插件和 proactive 状态。
- 观察系统失败是否影响主链路。

## 测试 1：普通问答 trace

输入：

```text
请简单介绍一下这个项目的主要模块
```

预期：

- 应产生一轮 turn trace。
- Dashboard 或 observe 文件中能看到记录。

记录：

```text
trace 文件 / 页面：
包含哪些字段：
是否能定位本轮对话：
```

## 测试 2：memory retrieval trace

输入：

```text
你还记得我之前说过我关注哪些方向吗？
```

预期：

- 如果触发 retrieval，应记录检索 query、hits、注入数量。

记录：

```text
rewrite query：
hits：
injected_count：
```

## 测试 3：tool call trace

输入：

```text
帮我查看项目根目录有哪些文件
```

预期：

- 工具调用应出现在 trace 中。

记录：

```text
tool name：
arguments：
result：
error：
```

## 测试 4：Dashboard 访问

目标：

- 启动 Dashboard。
- 查看 session、memory、插件、proactive 等页面。

记录：

```text
Dashboard 地址：
是否可访问：
页面列表：
异常：
```

## 需要查看的文件

- `bootstrap/dashboard_api.py`
- `plugins/observe`
- `plugins/recall_inspector`
- `plugins/memory_rollup`
- `plugins/status_commands`

## 测试结论

2026-07-03 初步测试通过：

- Dashboard/observe 能看到 `reasoning_content`。
- 对长期记忆检索问题，trace 显示模型看到已注入的记忆条目 `34365e5aa980`，但因为标注为“有印象，不确定”且带 `source_ref`，所以进一步调用 `recall_memory` 和 `fetch_messages` 回源确认。
- 对查看项目根目录问题，trace 显示模型不确定“当前项目根目录”指 workspace 还是 git 项目目录，因此同时查看了 `/home/jjh/.akashic/workspace` 和 `/home/jjh/git_work/akashic-agent`。

测试结论：

- observe trace 对解释 Agent 行为有效，能帮助理解工具为什么被调用。
- trace 能帮助定位“工具过度探索”的原因：有时不是工具系统错误，而是模型对用户意图或路径边界不确定。
- Dashboard 中的 reasoning trace 属于高敏感运行时数据，后续产品化必须加访问控制，并考虑脱敏、权限隔离或开关控制。

下一步：

- tool_search 测试轮次的 trace 已查看：模型确认用户要求先搜索工具，调用了 `tool_search`；第一次结果命中 `schedule` 后，模型判断这是误匹配，并明确知道 `read_file`、`list_dir`、`edit_file`、`write_file`、`shell` 等文件工具已经可见。
- 该 trace 支持判断：当前 `tool_search` 更像可解锁工具搜索，不适合作为完整“当前可见工具清单”；同时搜索打分存在误匹配问题。
- 下一步可以进入插件加载测试，或整理当前测试阶段总结。

2026-07-03 observe 插件行为测试通过：

- 用户要求一句话说明 observe 插件作用。
- Agent 最终正常回答。
- observe 插件记录本轮 `turn_trace`，日志显示 `tool_calls=5`。
- Dashboard/observe reasoning trace 能看到模型查找 observe 插件源码的原因。

发现的问题：

- 本轮存在明显工具过度探索：用户只要求一句话说明，但模型调用了 `list_dir`、`shell`、`read_file` 等多个工具，并读取了 `plugins/observe/plugin.py`。
- 这不是 observe 插件失败，而是工具使用策略问题。
- 后续可优化：对“简短解释/概念说明”类问题限制工具深挖，除非用户明确要求查看源码或确认实现。

2026-07-03 recall_inspector 文件读取验证通过：

- 直接读取 `/home/jjh/.akashic/workspace/observe/recall_inspector.jsonl`。
- 找到用户问题：“请从长期记忆里检索：我学习 agent 时最关注哪些方向？”
- `context_prepare` 记录显示目标记忆 `34365e5aa980` 被注入。
- `recall_memory` 记录显示本轮显式检索成功，命中同一条 preference 记忆。
- 这说明 recall_inspector 插件不仅能记录上下文准备阶段，也能记录显式 `recall_memory` 工具调用。
