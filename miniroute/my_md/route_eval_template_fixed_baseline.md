# MiniRoute 模板固定版 Baseline

## 基本信息

- 实验日期: 2026-08-05
- 实验状态: 已评测，作为 V3 对照基线
- 数据版本: `route_v2_train.jsonl`
- 样本数量: 1061
- 说明: 本轮结果来自修改过训练侧和评测侧后的模板一致版本。

## 实验目标

验证训练侧和评测侧模板统一后，MiniRoute 是否能拟合当前 V2 训练集。

本轮已排除的问题：

- 训练侧随机 system 注入。
- 训练侧和评测侧 empty think 处理不一致。
- 训练和评测 chat template 不一致。

## 测试结果

总体结果：

```text
总样本数: 1061
完全正确: 428
错误样本: 633
完全匹配率: 40.34%
错误率: 59.66%
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

## 错误原因

当前主要问题不是 JSON 格式，也不是训练和评测模板不一致，而是类别边界没有学稳。

核心错误：

1. 高风险 shell 过度预测。
2. `status_query`、`file_read`、`content_save` 被吸收到 `tool_execution`。
3. `chat`、`memory_query`、`profile_update`、`content_save` 边界混乱。
4. `tool_scope` 与 `intent` 连带出错。
5. 当前五字段联合生成任务对 64M 小模型偏难。

## 下一步结论

以本文件作为 V3 对照基线。下一轮不继续优先调模板和 `max_seq_len`，而是生成 V3 边界数据，重点补 hard negative 和成对反例。
