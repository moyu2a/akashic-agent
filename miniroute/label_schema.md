# MiniRoute 标签体系

MiniRoute 输出固定 JSON，用于描述当前用户请求的路由判断结果。

## 输出字段

```json
{
  "intent": "memory_query",
  "need_memory": true,
  "need_tools": false,
  "tool_scope": ["memory_tools"],
  "risk_level": "read_only"
}
```

## intent

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

## need_memory

| 值 | 含义 |
| --- | --- |
| `true` | 当前请求需要长期记忆或历史上下文。 |
| `false` | 当前请求不需要长期记忆。 |

## need_tools

| 值 | 含义 |
| --- | --- |
| `true` | 当前请求可能需要工具参与。 |
| `false` | 当前请求不需要工具。 |

## tool_scope

`tool_scope` 是建议开放的工具范围。第一版使用粗粒度分组，不直接暴露具体工具名。

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

## risk_level

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
- V2 中记忆查询和画像更新会进入 `memory_tools` 能力域，因此 `need_tools=true`。
