# Route SFT 上游数据问题交接报告

本文档用于转交给生成 route 训练集的上游项目，说明当前 MiniMind SFT/LoRA 训练中暴露的数据、schema 和评测问题。

## 背景

当前任务是训练一个路由分类模型：输入用户请求，输出严格 JSON，用于判断：

- `intent`
- `need_memory`
- `need_tools`
- `tool_scope`
- `risk_level`

当前使用模型：

```text
full_sft + lora_route_v1
```

当前数据文件：

```text
dataset/route_train.jsonl
dataset/route_valid.jsonl
dataset/route_test.jsonl
```

## 当前评测结果

### 训练集

```text
数据集: dataset/route_train.jsonl
总数: 875
严格只输出 JSON: 875/875 = 100.00%
可提取 JSON: 875/875 = 100.00%
完全匹配: 261/875 = 29.83%

字段准确率:
intent: 330/875 = 37.71%
need_memory: 675/875 = 77.14%
need_tools: 574/875 = 65.60%
tool_scope: 414/875 = 47.31%
risk_level: 432/875 = 49.37%
```

### 验证集

```text
数据集: dataset/route_valid.jsonl
总数: 184
严格只输出 JSON: 184/184 = 100.00%
可提取 JSON: 184/184 = 100.00%
完全匹配: 54/184 = 29.35%

字段准确率:
intent: 68/184 = 36.96%
need_memory: 144/184 = 78.26%
need_tools: 122/184 = 66.30%
tool_scope: 84/184 = 45.65%
risk_level: 91/184 = 49.46%
```

## 总体判断

模型已经稳定学会输出 JSON 格式，但没有学会稳定的路由语义。

训练集 exact `29.83%`，验证集 exact `29.35%`，两者几乎一致。这说明问题不是简单的“验证集泛化差”，而是训练集本身也没有被模型拟合好。

从错误分布看，当前主要问题来自：

1. 标签字段之间的语义不够自洽。
2. prompt 没有明确列出允许的枚举值。
3. 部分类别边界样本不足。
4. 样本句式过于模板化。
5. 训练/评测模板中空 `<think></think>` 的处理不一致，可能造成额外干扰。

## 问题 1: memory 标签口径不清，容易和 tools 冲突

当前 memory 类样本大致是：

```json
{
  "intent": "memory_query",
  "need_memory": true,
  "need_tools": false,
  "tool_scope": ["memory_tools"],
  "risk_level": "read_only"
}
```

以及：

```json
{
  "intent": "profile_update",
  "need_memory": true,
  "need_tools": false,
  "tool_scope": ["memory_tools"],
  "risk_level": "write"
}
```

这里存在明显歧义：

- `tool_scope` 写的是 `memory_tools`
- 但 `need_tools` 又是 `false`

模型很容易学成：只要出现 `memory_tools`，就应该 `need_tools=true`。

实际错误中也观察到：

```text
need_tools false -> true: 301 次
```

### 建议

请上游项目先统一定义：memory 是否属于 tool。

推荐方案 A：memory 也算工具。

```json
{
  "intent": "memory_query",
  "need_memory": true,
  "need_tools": true,
  "tool_scope": ["memory_tools"],
  "risk_level": "read_only"
}
```

```json
{
  "intent": "profile_update",
  "need_memory": true,
  "need_tools": true,
  "tool_scope": ["memory_tools"],
  "risk_level": "write"
}
```

备选方案 B：memory 不算工具。

```json
{
  "intent": "memory_query",
  "need_memory": true,
  "need_tools": false,
  "tool_scope": ["none"],
  "risk_level": "read_only"
}
```

如果保留 `tool_scope=["memory_tools"]`，建议采用方案 A。

## 问题 2: prompt 没有限定 schema 枚举，模型会发明新类别

当前 prompt 类似：

```text
判断用户请求的意图、记忆需求、工具需求、工具范围和风险等级，并只输出 JSON。

用户请求：...
```

这个 prompt 没有告诉模型 `intent`、`tool_scope`、`risk_level` 的允许取值。

已观察到错误：

```json
{
  "intent": "trace",
  "need_memory": false,
  "need_tools": true,
  "tool_scope": ["trace_tools"],
  "risk_level": "write"
}
```

但当前 schema 中并没有 `trace` 或 `trace_tools`。

### 建议

训练集里的每条 user prompt 应包含明确枚举，例如：

```text
你是路由分类器。只根据用户请求分类，不要执行请求。

intent 只能是：
chat, memory_query, profile_update, task_plan, content_save, file_read, tool_execution, status_query

tool_scope 只能是：
none, memory_tools, task_tools, content_tools, file_read_tools, shell_tools, observe_tools

risk_level 只能是：
none, read_only, write, high_risk

输出 JSON 字段固定为：
intent, need_memory, need_tools, tool_scope, risk_level

只输出 JSON，不要解释。

用户请求：...
```

## 问题 3: `chat` 类边界太弱

训练集里 `chat` 类 exact 是：

```text
chat: 0/105 = 0.00%
```

主要混淆：

```text
chat -> profile_update: 63
chat -> memory_query: 27
chat -> content_save: 15
```

说明模型经常把普通对话误判为画像更新、记忆查询或内容保存。

### 建议

增加 `chat` hard negative，特别是包含这些词但不应该触发工具/记忆的样本：

| 关键词 | 应覆盖的普通 chat 示例 |
| --- | --- |
| 项目 | “你觉得这个项目怎么介绍更好？” |
| 记 | “帮我记一下这个概念是什么意思？” |
| 总结 | “总结一下这个观点的优缺点。” |
| 偏好 | “你觉得这种表达偏好吗？” |
| 保存 | “保存机制是什么意思？” |
| 工具 | “解释一下工具调用的原理。” |

这些样本应该明确标为：

```json
{
  "intent": "chat",
  "need_memory": false,
  "need_tools": false,
  "tool_scope": ["none"],
  "risk_level": "none"
}
```

## 问题 4: `memory_query` 和 `profile_update` 边界不清

训练集结果：

```text
memory_query: 0/105 = 0.00%
profile_update: 11/105 = 10.48%
```

主要混淆：

```text
memory_query -> profile_update: 63
memory_query -> chat: 21
profile_update -> memory_query: 21
profile_update -> task_plan: 21
```

### 建议

上游数据应明确：

- `memory_query`: 用户要求读取、回忆、查询既有记忆。
- `profile_update`: 用户要求写入、更新、保存偏好/画像/长期设定。

建议增加成对样本：

```text
你还记得我喜欢什么回答风格吗？
=> memory_query, read_only
```

```text
请记住我以后喜欢简洁回答。
=> profile_update, write
```

```text
我喜欢简洁回答这种风格吗？
=> chat，不一定写记忆
```

## 问题 5: `tool_execution` 和 `file_read` 混淆严重

训练集主要混淆：

```text
tool_execution -> file_read: 70
risk_level high_risk -> read_only: 70
```

这说明模型没有稳定区分：

- 只读文件/目录: `file_read`, `read_only`
- 修改系统或执行命令: `tool_execution`, `high_risk`

### 建议

增加成对边界样本：

```text
帮我看看 README 里写了什么
=> file_read, read_only
```

```text
帮我删除这个目录
=> tool_execution, high_risk
```

```text
读取这个配置文件
=> file_read, read_only
```

```text
覆盖这个配置文件
=> tool_execution, high_risk
```

```text
解释一下这个命令会做什么
=> chat, none
```

```text
执行这个命令
=> tool_execution, high_risk
```

## 问题 6: 样本按类别连续排列

当前 train/valid/test 都按 intent 连续分块排列。

这会导致：

- 使用 `--limit 20` 时只评到 `chat` 类。
- 人工查看前几条时容易误判整体效果。
- 如果某些训练流程没有正确 shuffle，会放大类别顺序偏置。

### 建议

- 输出数据文件前先 shuffle。
- 或者评测脚本支持 stratified limit，每个 intent 抽固定数量。
- 保留一个按类别排序的 debug 文件可以，但训练/评测主文件建议打乱。

## 问题 7: 样本模板过窄

当前很多样本只是少数模板加编号，例如：

```text
帮我解释一下这个概念，第1版。
帮我解释一下这个概念，第6版。
帮我解释一下这个概念，第11版。
```

这容易让模型学编号和固定句式，而不是学真实意图。

### 建议

每个 intent 增加更多真实表达：

- 中文口语表达
- 简短命令
- 长句请求
- 含上下文但不触发工具的请求
- 含关键词但类别不同的 hard negative
- 多个动作混合但主意图明确的请求

## 问题 8: 空 `<think></think>` 模板需要统一

MiniMind 的 chat template 支持 reasoning，会在 assistant 前加入：

```text
<think>

</think>
```

当前观察到：

- 训练流程可能随机移除大部分空 think。
- 评测流程之前固定保留空 think。

快速对照中，去掉空 think 后前 20 条 valid exact 从 `0/20` 到 `1/20`，有轻微改善，但不是主要原因。

### 建议

route 分类任务不需要 reasoning。建议上游数据和训练/评测流程统一使用无空 think 格式，或者全部保留，不要随机混合。

推荐：route 任务统一去掉空 think。

## 建议的 V2 数据格式

建议每条样本使用更明确的 prompt：

```json
{
  "conversations": [
    {
      "role": "user",
      "content": "你是路由分类器。只根据用户请求分类，不要执行请求。\n\nintent 只能是：chat, memory_query, profile_update, task_plan, content_save, file_read, tool_execution, status_query\n\ntool_scope 只能是：none, memory_tools, task_tools, content_tools, file_read_tools, shell_tools, observe_tools\n\nrisk_level 只能是：none, read_only, write, high_risk\n\n输出 JSON 字段固定为：intent, need_memory, need_tools, tool_scope, risk_level\n\n只输出 JSON，不要解释。\n\n用户请求：请记住我以后喜欢简洁回答。"
    },
    {
      "role": "assistant",
      "content": "{\"intent\": \"profile_update\", \"need_memory\": true, \"need_tools\": true, \"tool_scope\": [\"memory_tools\"], \"risk_level\": \"write\"}"
    }
  ]
}
```

如果上游决定 memory 不属于 tool，则需要同步改成：

```json
{
  "need_tools": false,
  "tool_scope": ["none"]
}
```

但不要继续使用 `need_tools=false` 同时 `tool_scope=["memory_tools"]` 的混合口径。

## 上游优先修改清单

1. 决定 memory 是否属于 tool，并统一所有 memory 类标签。
2. 在 prompt 中加入 intent/tool_scope/risk_level 的允许枚举。
3. 禁止生成 schema 外类别，例如 `trace`、`trace_tools`。
4. 增加 `chat` hard negative。
5. 增加 `memory_query` vs `profile_update` 成对样本。
6. 增加 `file_read` vs `tool_execution` 成对样本。
7. 打乱 train/valid/test 主文件。
8. 统一 route 任务的空 `<think></think>` 处理。

## 验收建议

V2 数据生成后，建议按以下顺序验收：

1. 先检查 JSON schema，确保没有 schema 外枚举。
2. 统计每个 intent 的数量和字段组合。
3. 检查 memory 类中 `need_tools` 和 `tool_scope` 是否一致。
4. 训练 `lora_route_v2`。
5. 先跑训练集评测，确认训练集 exact 明显高于 V1。
6. 再跑验证集评测。
7. 最后跑测试集评测，测试集不要用于反复调参。
