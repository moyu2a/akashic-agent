# MiniRoute 当前错误混淆记录

## 基本信息

- 实验日期: 2026-08-05
- 记录来源: MiniMind 侧评测输出
- 关联问题: 训练集拟合不足、类别边界混淆、高风险 shell 过度预测
- 当前状态: 最新模板固定实验结果已记录，模板不一致已排除为主因

## 本轮需要补充确认的信息

当前仍需要补齐：

- 具体 LoRA 权重名称。
- 评测数据文件，是 train、valid 还是 test。
- 完整评测命令和错误样本文件路径。

已确认信息：

- 本轮结果来自修改过训练侧和评测侧后的最新训练。
- 训练侧和评测侧模板已经保持一致。
- 因此，模板不一致不再作为当前主要原因。

## 错误统计

Top intent confusion:

```text
59 ('status_query', 'tool_execution')
52 ('file_read', 'tool_execution')
47 ('content_save', 'tool_execution')
46 ('profile_update', 'memory_query')
41 ('chat', 'memory_query')
35 ('chat', 'profile_update')
33 ('task_plan', 'chat')
32 ('profile_update', 'content_save')
21 ('file_read', 'content_save')
18 ('status_query', 'chat')
18 ('file_read', 'memory_query')
17 ('profile_update', 'tool_execution')
16 ('status_query', 'trace')
16 ('task_plan', 'tool_execution')
15 ('task_plan', 'memory_query')
14 ('memory_query', 'profile_update')
13 ('memory_query', 'status_query')
12 ('status_query', 'memory_query')
```

Top tool_scope confusion:

```text
76 ('none', 'memory_tools')
59 ('observe_tools', 'shell_tools')
52 ('file_read_tools', 'shell_tools')
47 ('content_tools', 'shell_tools')
33 ('task_tools', 'none')
32 ('memory_tools', 'content_tools')
21 ('file_read_tools', 'content_tools')
18 ('observe_tools', 'none')
18 ('file_read_tools', 'memory_tools')
17 ('memory_tools', 'shell_tools')
16 ('unknown_tools', 'shell_tools')
16 ('observe_tools', 'None')
16 ('task_tools', 'shell_tools')
15 ('task_tools', 'memory_tools')
13 ('memory_tools', 'observe_tools')
12 ('observe_tools', 'memory_tools')
12 ('unknown_tools', 'memory_tools')
8 ('unknown_tools', 'none')
7 ('unknown_tools', 'observe_tools')
```

Top risk confusion:

```text
127 ('read_only', 'high_risk')
80 ('write', 'high_risk')
61 ('write', 'read_only')
41 ('none', 'read_only')
41 ('read_only', 'write')
35 ('none', 'write')
33 ('write', 'none')
26 ('read_only', 'none')
16 ('read_only', None)
```

Top predicted combos:

```text
207 ('tool_execution', 'shell_tools', 'high_risk')
144 ('memory_query', 'memory_tools', 'read_only')
65 ('profile_update', 'memory_tools', 'write')
59 ('chat', 'none', 'none')
59 ('content_save', 'content_tools', 'write')
20 ('status_query', 'observe_tools', 'read_only')
16 ('trace', 'None', None)
```

Schema bad:

```text
16 ('intent', 'trace')
16 ('tool_scope', 'None')
16 ('risk_level', None)
```

## 初步判断

这批错误显示模型已经具备 JSON 输出能力，但分类边界仍不稳定，主要问题集中在：

1. 过度预测 `tool_execution + shell_tools + high_risk`。
2. 将 `status_query`、`file_read`、`content_save` 错误吸收到 shell 执行。
3. 将普通 `chat` 错误吸收到 `memory_query` 或 `profile_update`。
4. `profile_update`、`memory_query`、`content_save` 三类边界仍然混乱。
5. 仍有 schema 外输出，例如 `intent=trace`、`tool_scope=None`、`risk_level=None`。

由于本轮已经完成训练/评测模板统一，当前低准确率不能继续主要归因于模板不一致。更合理的判断是：

1. 当前五字段联合生成任务对 64M 小模型偏难。
2. `intent` 与 `tool_scope` 高度绑定，但模型需要同时生成，导致错误连锁放大。
3. 数据边界样本不足，尤其是 read-only/write 与 high-risk 的成对反例不够。
4. 模型对“查看、保存、工具、命令、状态、记忆”等词面过度敏感，缺少足够 hard negative。

## 对后续实验的影响

本轮结果来自模板固定后的 LoRA，说明问题不再主要是模板不一致，应进入 V3 数据边界设计或简化输出空间：

- V3 数据重点补 `status_query/file_read/content_save` 与 `tool_execution` 的成对反例。
- 增加 `chat` 与 `memory_query/profile_update` 的 hard negative。
- 增加 `unknown_tools` 与 `shell_tools` 的边界样本。
- 考虑让模型不直接输出 `tool_scope`，改为由规则从 `intent + risk_level` 映射。

## 下一步记录要求

拿到下一轮完整评测结果后，需要补充：

1. 本轮 LoRA 权重名称。
2. train、valid、test 完整指标。
3. 错误样本路径。
4. 当前错误行是否与 V2/V2_2 错误行重合。
5. 是否更新 `route_issue_log.md` 中的稳定问题。
