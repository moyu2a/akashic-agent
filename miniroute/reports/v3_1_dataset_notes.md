# MiniRoute V3.1 数据说明

## Baseline

V3.1 以 `lora_route_v3_2` 作为冻结 baseline。

| 数据集 | V3_2 完全匹配 | 错误率 | Schema 合法 |
| --- | ---: | ---: | ---: |
| train | 78.37% | 21.63% | 99.16% |
| valid | 81.69% | 18.31% | 99.44% |
| test | 78.67% | 21.33% | 98.61% |

V3.1 的目标不是重做任务，而是在保留五字段 schema 的基础上，减少 test 中剩余的边界错误。

## 修改方法

V3.1 保留 V3 全量 split，不重新切分 V3 原始样本，只把 V3.1 delta 样本按 intent 分层切分后追加到对应 split。

这样做是为了保证：

```text
route_v3_train 原始样本仍在 route_v3_1_train
route_v3_valid 原始样本仍在 route_v3_1_valid
route_v3_test 原始样本仍在 route_v3_1_test
```

V3.1 只追加小修样本，不覆盖 V3 文件，不移除 `tool_scope`，不修改五字段 schema。

## 数据规模

生成命令：

```bash
.venv/bin/python -m miniroute.tools.generate_v3_1_dataset
```

输出结果：

```text
train: 1713
valid: 361
test: 380
total: 2454
delta_train: 49
delta_valid: 6
delta_test: 19
delta_total: 74
shuffle_seed: 20260805
```

V3.1 delta source 计数：

```text
v3_1:file_read_tool_execution_boundary: 12
v3_1:profile_memory_content_boundary: 18
v3_1:task_plan_chat_profile_boundary: 20
v3_1:trace_status_query_schema_fix: 12
v3_1:unknown_tools_boundary: 12
```

数据校验：

```bash
.venv/bin/python -m miniroute.tools.validate_dataset \
  --train miniroute/data/route_v3_1_train.jsonl \
  --valid miniroute/data/route_v3_1_valid.jsonl \
  --test miniroute/data/route_v3_1_test.jsonl
```

校验结果：

```json
{
  "ok": true,
  "total_records": 2454,
  "high_risk_test_count": 34,
  "issues": []
}
```

V3 原始文件未被修改：

```bash
git diff -- miniroute/data/route_v3_train.jsonl miniroute/data/route_v3_valid.jsonl miniroute/data/route_v3_test.jsonl
```

结果为空 diff。

## 测试方法

本地测试：

```bash
.venv/bin/python -m pytest tests/test_miniroute_v2.py tests/test_miniroute_v3.py tests/test_miniroute_v3_1.py -q -p no:cacheprovider
.venv/bin/python -m compileall miniroute
.venv/bin/python -m miniroute.tools.validate_dataset \
  --train miniroute/data/route_v3_1_train.jsonl \
  --valid miniroute/data/route_v3_1_valid.jsonl \
  --test miniroute/data/route_v3_1_test.jsonl
```

MiniMind 侧训练后必须评测：

```text
route_v3_1_train.jsonl
route_v3_1_valid.jsonl
route_v3_1_test.jsonl
route_v3_test.jsonl 作为 bridge eval
```

bridge eval 用于确认 `lora_route_v3_1` 在冻结 V3 test 上不低于 `lora_route_v3_2` 的 `78.67%`。

## 验收标准

V3.1 只有在云端评测满足以下条件时才接受：

```text
route_v3_1_train exact > 82%
route_v3_1_valid exact > 83%
route_v3_1_test exact > 82%
route_v3_1_test schema bad <= 1
bridge route_v3_test exact >= 78.67%
trace/status_query schema bad 从 V3_2 test 的 5 条降到 0-1 条
```

如果 V3.1 未达到以上标准，则继续保留 `lora_route_v3_2` 作为当前 baseline。

## V3.1 Train 初步结果

已完成 `lora_route_v3_1` train 评测：

```text
完全匹配: 1357/1713 = 79.22%
错误样本: 356/1713 = 20.78%
Schema 合法: 1712/1713 = 99.94%
```

与 V3_2 train 对比：

```text
78.37% -> 79.22%，提升 0.85 个百分点
```

初步结论：

```text
V3.1 明显改善了 Schema 合法率，但整体路由准确率提升有限。
目前不能仅凭 train 结果接受 V3.1，必须继续评测 valid、test 和 bridge。
```

主要剩余错误：

```text
memory_query -> chat: 31
file_read -> tool_execution: 28
profile_update -> chat: 25
tool_execution -> file_read: 23
tool_execution -> content_save: 23
task_plan -> tool_execution: 20
task_plan -> chat: 19
unknown_tools -> shell_tools: 28
unknown_tools -> content_tools: 23
read_only -> high_risk: 59
read_only -> write: 55
```
