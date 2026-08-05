# MiniRoute 数据集计划

## 数据目标

构建一套面向个人智能体意图路由的小型监督微调数据集。每条样本包含用户输入和固定 JSON 输出，用于训练 MiniMind 判断用户请求的意图、记忆需求、工具需求、工具范围和风险等级。

## 推荐数据规模

第一版建议：

- 训练集：1000 到 2000 条。
- 验证集：200 到 300 条。
- 测试集：200 到 300 条。

如果时间有限，可先做最小版本：

- 训练集：400 到 800 条。
- 验证集：100 条。
- 测试集：100 条。

## 数据来源

1. 项目已有测试用例：工具治理、任务计划、状态查询、记忆查询等测试可以改造成样本。
2. 真实对话日志：需要脱敏，删除路径、密钥、账号、私密内容。
3. 人工模板扩写：每类 intent 设计 50 到 200 条表达变体。
4. 失败和混淆样本：专门加入高风险、工具能力询问、记忆查询和内容收藏等容易误判的表达。

## 样本格式

建议使用 MiniMind 对话 JSONL，每行一条样本。

```json
{"conversations":[{"role":"user","content":"判断用户请求的意图、记忆需求、工具需求、工具范围和风险等级，并只输出 JSON。\n\n用户请求：你还记得我上次说的回答偏好吗？"},{"role":"assistant","content":"{\"intent\":\"memory_query\",\"need_memory\":true,\"need_tools\":false,\"tool_scope\":[\"memory_tools\"],\"risk_level\":\"read_only\"}"}]}
```

## 样本分布建议

| intent | 训练样本建议 |
| --- | ---: |
| `chat` | 150 到 250 |
| `memory_query` | 150 到 250 |
| `profile_update` | 100 到 200 |
| `task_plan` | 100 到 200 |
| `content_save` | 100 到 200 |
| `file_read` | 100 到 200 |
| `tool_execution` | 150 到 250 |
| `status_query` | 80 到 150 |

高风险样本建议不少于测试集的 15%，否则无法可靠评估高风险召回率。

## 重点混淆样本

| 用户输入 | 期望判断 |
| --- | --- |
| `你能删除文件吗？` | `chat`，`read_only`，因为只是询问能力 |
| `帮我删除这个目录` | `tool_execution`，`high_risk` |
| `你还记得我喜欢什么回答格式吗？` | `memory_query`，`need_memory=true` |
| `以后回答我简洁点` | `profile_update`，`need_memory=true` |
| `帮我看看 README` | `file_read`，`read_only` |
| `保存这个链接，晚上提醒我看` | `content_save`，`write` |
| `刚才用了哪些工具？` | `status_query`，`observe_tools` |

## 数据质量检查

每次训练前必须检查：

- JSONL 每行能被解析。
- `conversations` 必须包含 user 和 assistant 两条消息。
- assistant 的 `content` 字符串能被解析为 JSON。
- 标签只使用 `label_schema.md` 中定义的枚举值。
- `need_tools=false` 时，`tool_scope` 应为 `none` 或空列表。
- `risk_level=high_risk` 的样本不能被标成 `need_tools=false`，除非只是询问能力。
- 训练集、验证集、测试集不要有完全重复输入。
