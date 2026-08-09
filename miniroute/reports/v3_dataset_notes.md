# MiniRoute V3 数据说明

## 目标

V3 在 V2 数据基础上新增边界样本，用于修复模板固定后仍然存在的稳定混淆。

本轮不改变输出 schema，仍保留：

```json
{
  "intent": "",
  "need_memory": true,
  "need_tools": true,
  "tool_scope": [],
  "risk_level": ""
}
```

## 修改方法

V3 的修改方式是“保留原数据 + 定向补边界”，不是重新设计标签体系。

具体方法：

1. 继续使用 V2 的完整标签 schema，不改输出字段。
2. 复用 V2 全量样本，保证基础类别覆盖不倒退。
3. 根据模板固定版错误统计，抽取高频混淆作为 V3 的补强方向。
4. 为每个混淆方向设计 hard negative，让样本文本中包含容易误导模型的关键词，但标签仍指向正确类别。
5. 继续使用固定随机种子 `20260805` 做分层切分，保证 train、valid、test 可复现。

本轮没有做的事情：

```text
没有移除 tool_scope。
没有修改 risk_level 枚举。
没有把 unknown_tools 改成 shell_tools。
没有把小模型改成授权模型。
```

## 数据规模

生成命令：

```bash
.venv/bin/python -m miniroute.tools.generate_v3_dataset
```

输出结果：

```text
train: 1664
valid: 355
test: 361
total: 2380
shuffle_seed: 20260805
```

数据校验：

```bash
.venv/bin/python -m miniroute.tools.validate_dataset \
  --train miniroute/data/route_v3_train.jsonl \
  --valid miniroute/data/route_v3_valid.jsonl \
  --test miniroute/data/route_v3_test.jsonl
```

校验结果：

```json
{
  "ok": true,
  "total_records": 2380,
  "high_risk_test_count": 33,
  "issues": []
}
```

## 新增边界样本

V3 基于 V2 全量数据追加以下来源：

```text
v3:status_query_vs_tool_execution
v3:file_read_vs_tool_execution
v3:content_save_vs_tool_execution
v3:chat_memory_profile_hard_negative
v3:profile_memory_content_boundary
v3:unknown_tools_vs_shell_tools
```

重点修复：

1. `status_query -> tool_execution`
2. `file_read -> tool_execution`
3. `content_save -> tool_execution`
4. `chat -> memory_query/profile_update`
5. `profile_update -> memory_query/content_save`
6. `unknown_tools -> shell_tools`
7. `read_only/write -> high_risk`

## 测试方法

本地测试分三层：

1. 单元测试：确认 V3 包含指定 hard negative 来源，且关键来源标签正确。
2. 数据生成：确认能生成 `route_v3_train/valid/test.jsonl`。
3. 数据校验：确认 JSONL、枚举值、schema 一致性和高风险测试样本数量合法。

本地测试命令：

```bash
.venv/bin/python -m pytest tests/test_miniroute_v2.py tests/test_miniroute_v3.py -q -p no:cacheprovider
.venv/bin/python -m compileall miniroute
.venv/bin/python -m miniroute.tools.validate_dataset \
  --train miniroute/data/route_v3_train.jsonl \
  --valid miniroute/data/route_v3_valid.jsonl \
  --test miniroute/data/route_v3_test.jsonl
```

本地测试结果：

```text
tests/test_miniroute_v2.py + tests/test_miniroute_v3.py: 8 passed
compileall miniroute: 通过
validate_dataset: ok=true, total_records=2380, high_risk_test_count=33, issues=[]
```

MiniMind 侧测试分两步：

1. train 评测：判断 V3 数据是否能被模型学会。
2. valid 评测：判断是否具备泛化。
3. test 评测：形成阶段性结论，决定是否冻结 V3_2。

已完成 train 评测：

```text
模型: full_sft + lora_route_v3_2
数据集: route_v3_train.jsonl
完全匹配: 1304/1664 = 78.37%
错误样本: 360/1664 = 21.63%
```

已完成 valid 评测：

```text
模型: full_sft + lora_route_v3_2
数据集: route_v3_valid.jsonl
完全匹配: 290/355 = 81.69%
错误样本: 65/355 = 18.31%
Schema 合法: 353/355 = 99.44%
```

已完成 test 评测：

```text
模型: full_sft + lora_route_v3_2
数据集: route_v3_test.jsonl
完全匹配: 284/361 = 78.67%
错误样本: 77/361 = 21.33%
Schema 合法: 356/361 = 98.61%
```

相比模板固定版 baseline：

```text
baseline -> train: 40.34% -> 78.37%，提升 38.03 个百分点
baseline -> valid: 40.34% -> 81.69%，提升 41.35 个百分点
baseline -> test: 40.34% -> 78.67%，提升 38.33 个百分点
```

## V3 原始判断标准

V3 训练后先评测 train 和 valid，方向成立后再评测 test。

当时建议判断标准：

```text
train exact_match > 60%
valid exact_match > 55%
schema bad 接近 0
tool_execution + shell_tools + high_risk 过度预测明显下降
```

实际结果已经超过该标准，且 test 也保持稳定。因此当前不进入 `tool_scope` 移除方案，转向 V3.1 小修。

## 当前结论

V3 数据方向已在 train、valid、test 上验证有效。当前不能再把主要问题归因于训练模板、`max_seq_len` 或模型完全无法学习；更准确的判断是：补足边界数据后，模型能够明显提升，并且 test 结果没有明显掉分。

当前冻结 baseline：

```text
train exact: 78.37%
valid exact: 81.69%
test exact: 78.67%
test schema valid: 98.61%
```

下一步优先级：

1. 按 `my_md/v3_1_fix_plan.md` 做 V3.1 小修数据。
2. 重点补 `trace/status_query`、`task_plan/chat/profile_update`、`profile_update/memory_query/content_save`。
3. 继续补 `file_read/tool_execution` 和 `unknown_tools/file_read/content_save`。
4. 暂时不移除 `tool_scope`，因为 V3 test 已达到 `78.67%`。
