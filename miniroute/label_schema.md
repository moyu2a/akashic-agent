# MiniRoute 标签体系

MiniRoute 输出固定 JSON，用于描述当前用户请求的路由判断结果。

MiniRoute 只负责路由建议，不负责选择具体工具、拆分任务或执行工具。V4 当前主线使用三字段场景协议；V1-V3 的五字段协议只作为历史 baseline 保留。

## V4 当前主线

V4 起，MiniRoute 的主线协议改为三字段场景识别。它只根据 `has_active_task` 和 `user_message` 判断请求场景，不读取完整记忆、历史、工具列表、插件信息、文件内容或检索结果。

```json
{
  "scene": "task",
  "operation": "plan",
  "request_mode": "single"
}
```

### scene

| 标签 | 含义 | 示例 |
| --- | --- | --- |
| `chat` | 普通解释、讨论、改写、分析 | `这个项目描述怎么写更清楚？` |
| `memory` | 查询长期记忆或历史偏好 | `你还记得我之前说的回答偏好吗？` |
| `profile` | 用户主动设置偏好、身份、习惯 | `以后回答我先给结论。` |
| `task` | 计划、下一步、任务推进 | `下一步该做什么？` |
| `file` | 读取、查看、总结文件 | `帮我看一下 README。` |
| `status` | 查询运行状态、trace、工具记录 | `刚才用了哪些工具？` |
| `content` | 保存、收藏、记录外部内容 | `帮我保存这个链接。` |
| `action` | 明确执行命令、写文件、安装、删除等动作 | `删除这个目录。` |
| `unknown` | 表达不完整、能力未知或无法判断 | `帮我弄一下。` |

### operation

| 标签 | 含义 |
| --- | --- |
| `answer` | 回答、解释、分析 |
| `query` | 查询记忆、状态或已有信息 |
| `update` | 更新用户画像或偏好 |
| `plan` | 制定计划、推进任务 |
| `read` | 读取文件或资料 |
| `save` | 保存内容 |
| `execute` | 执行动作 |
| `unknown` | 无法判断 |

### request_mode

| 标签 | 含义 |
| --- | --- |
| `single` | 单一请求 |
| `compound` | 同一场景、同一操作下包含多个可比较目标或同类子请求 |

V4.1 中，`compound` 不表示跨场景工作流。比如“查一下历史偏好，然后改这段简历”同时涉及 `memory` 和 `chat/profile`，V4.1 不生成这类样本，因为当前协议只有一个 `scene` 和一个 `operation`，无法稳定表达混合流程。

可以标为 `compound` 的例子：

- `查看最近 trace 和 token 消耗。` -> `status/query/compound`
- `保存这个链接和这篇文章。` -> `content/save/compound`
- `比较这个概念和那个概念，并说明区别。` -> `chat/answer/compound`

虽然包含连接词但仍为 `single` 的例子：

- `下载并保存这个网页正文。` -> `action/execute/single`
- `保存这个网页，不是执行下载命令。` -> `content/save/single`

## V1-V3 历史五字段协议

V1-V3 使用五字段输出，当前保留用于历史实验、baseline 和对照分析。

### 输出字段

```json
{
  "intent": "memory_query",
  "need_memory": true,
  "need_tools": false,
  "tool_scope": ["memory_tools"],
  "risk_level": "read_only"
}
```

### intent

| 标签 | 含义 | 示例 |
| --- | --- | --- |
| `chat` | 普通对话、解释、闲聊，不需要工具执行 | `你觉得这个项目怎么介绍更好？` |
| `memory_query` | 查询长期记忆或历史偏好 | `你还记得我上次说的回答偏好吗？` |
| `profile_update` | 用户主动表达偏好、身份、习惯等画像信息 | `以后回答我尽量简洁一点。` |
| `task_plan` | 创建、修改或查看任务计划 | `帮我把这个功能拆成几个步骤。` |
| `content_save` | 收藏链接、保存内容、记录资料 | `帮我保存这个 B 站视频。` |
| `file_read` | 读取、查看、总结文件内容 | `帮我看看 README 里写了什么。` |
| `tool_execution` | 明确要求执行工具或产生副作用 | `帮我删除这个目录。` |
| `status_query` | 查询系统状态、工具历史、运行轨迹 | `刚才用了哪些工具？` |

### need_memory

| 值 | 含义 |
| --- | --- |
| `true` | 当前请求需要长期记忆或历史上下文。 |
| `false` | 当前请求不需要长期记忆。 |

### need_tools

| 值 | 含义 |
| --- | --- |
| `true` | 当前请求可能需要工具参与。 |
| `false` | 当前请求不需要工具。 |

### tool_scope

`tool_scope` 是建议开放的工具范围集合。第一版使用粗粒度分组，不直接暴露具体工具名。
一个请求可以同时包含多个工具域。

| 标签 | 含义 |
| --- | --- |
| `none` | 不建议开放工具。 |
| `memory_tools` | 长期记忆查询相关工具。 |
| `content_tools` | 内容收藏、内容查询相关工具。 |
| `file_read_tools` | 只读文件工具。 |
| `file_write_tools` | 写文件、编辑文件工具。 |
| `shell_tools` | 命令行工具。 |
| `task_tools` | 任务计划、任务状态工具。 |
| `observe_tools` | 运行轨迹、状态查询工具。 |
| `unknown_tools` | 请求明显需要工具，但无法归入当前定义的工具域。 |

示例：

```json
{
  "tool_scope": ["memory_tools", "task_tools"]
}
```

表示请求可能需要记忆查询和任务工具，不代表模型已经选择了具体工具。
如果模型输出的工具域在运行时工具注册表中不可用，MnemoAgent 应将该工具域改写为
`unknown_tools`，而不是猜测为 `shell_tools` 或其他工具域。

### risk_level

| 标签 | 含义 | 示例 |
| --- | --- | --- |
| `none` | 无工具风险 | 普通解释、闲聊 |
| `read_only` | 只读风险 | 查询记忆、读文件、查状态 |
| `write` | 写入风险 | 保存链接、写文件、修改任务计划 |
| `high_risk` | 高风险或不可逆风险 | 删除文件、执行 shell、安装软件、访问敏感路径 |

## 安全原则

- 小模型输出只是建议，不是最终授权。
- 高风险工具仍必须由 MnemoAgent 原治理链路裁决。
- 当模型输出不合法 JSON 时，系统应回退到原路由逻辑。
- 当小模型不确定时，应偏保守，减少工具开放范围。
- `high_risk` 召回优先级高于 intent 准确率。
- `none` 表示明确不需要工具；`unknown_tools` 表示需要工具但工具域未知。
- `tool_scope` 不是最终授权；多个工具域需要由任务规划器拆分后逐步治理。
- V2 中记忆查询和画像更新会进入 `memory_tools` 能力域，因此 `need_tools=true`。

## MiniRoute 内部字段

V3.1 曾为了降低五字段同时生成的难度，将训练拆成两个内部阶段：

```json
{
  "intent": "task_plan",
  "operation": "plan",
  "request_mode": "compound"
}
```

- `operation`：`none`、`query`、`update`、`read`、`write`、`execute`、`plan`。
- `request_mode`：`single` 或 `compound`。

这两个字段只属于 MiniRoute 内部路由，不改变对外五字段接口。任务拆分和具体工具调用仍由 MnemoAgent 负责。

V4 已将 `scene`、`operation`、`request_mode` 升级为主协议，不再要求小模型同时生成 `need_memory`、`need_tools`、`tool_scope` 和 `risk_level`。
