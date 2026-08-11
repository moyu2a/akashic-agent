# MiniRoute V3_2 Train 评测记录

## 基本信息

- 实验日期: 2026-08-05
- 数据集: `dataset/route_v3_train.jsonl`
- LoRA: `lora_route_v3_2`
- 评测集类型: train
- 错误文件: `/home/jjh/git_work/minimind/result/route_v3_2_train_errors.jsonl`

## 修改方法

本轮没有继续修改模型结构，也没有先简化输出字段，而是针对模板固定版 baseline 的稳定错误设计 V3 边界数据。

修改思路：

1. 保持 V2 输出 schema 不变，仍输出 `intent`、`need_memory`、`need_tools`、`tool_scope`、`risk_level` 五个字段。
2. 保留 V2 全量数据，避免丢失原有基础类别覆盖。
3. 新增 hard negative 和成对边界样本，专门压制高频错误。
4. 训练侧继续使用已经统一后的 route 模板，避免重新引入随机 system 和 empty think 差异。

针对的错误模式：

```text
status_query -> tool_execution
file_read -> tool_execution
content_save -> tool_execution
chat -> memory_query/profile_update
profile_update -> memory_query/content_save
unknown_tools -> shell_tools
read_only/write -> high_risk
```

新增数据来源：

```text
v3:status_query_vs_tool_execution
v3:file_read_vs_tool_execution
v3:content_save_vs_tool_execution
v3:chat_memory_profile_hard_negative
v3:profile_memory_content_boundary
v3:unknown_tools_vs_shell_tools
```

## 测试数据

V3 数据由本仓库脚本生成：

```bash
.venv/bin/python -m miniroute.tools.generate_v3_dataset
```

数据规模：

```text
route_v3_train.jsonl: 1664
route_v3_valid.jsonl: 355
route_v3_test.jsonl: 361
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

## 训练方法

MiniMind 侧训练命令：

```bash
cd ~/autodl-tmp/minimind/trainer

python train_lora.py \
  --data_path ../dataset/route_v3_train.jsonl \
  --from_weight full_sft \
  --lora_name lora_route_v3_2 \
  --epochs 3 \
  --batch_size 16 \
  --max_seq_len 1024
```

训练日志摘要：

```text
Model Params: 63.91M
Trainable Params: 63.912M
LLM 总参数量: 64.305 M
LoRA 参数量: 0.393 M
LoRA 参数占比: 0.61%
训练样本: 1664
每轮 step: 104
Epoch 1 end loss: 0.0514
Epoch 2 end loss: 0.0291
Epoch 3 end loss: 0.0180
```

说明：

```text
loss 从 0.6006 降到 0.0180，训练过程正常收敛。但本任务不能只看 loss，必须通过结构化 JSON 完全匹配和字段准确率判断效果。
```

## 测试方法

本节记录 train 评测，用于判断 V3 数据是否能被模型学会。valid 评测已经补充在本文末尾和 `route_eval_v3_2_valid.md` 中。

train 评测命令：

```bash
cd ~/autodl-tmp/minimind

python eval_route.py \
  --data_path dataset/route_v3_train.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v3_2 \
  --device cuda \
  --max_new_tokens 80 \
  --errors_path route_v3_2_train_errors.jsonl
```

评测指标：

```text
严格只输出 JSON
可提取 JSON
Schema 合法
完全匹配
字段准确率
错误样本 Top confusion
schema bad
Top predicted combos
```

## 总体结果

```text
总数: 1664
严格只输出 JSON: 1650/1664 = 99.16%
可提取 JSON: 1650/1664 = 99.16%
Schema 合法: 1650/1664 = 99.16%
完全匹配: 1304/1664 = 78.37%
错误样本: 360/1664 = 21.63%
```

字段准确率：

```text
intent: 1332/1664 = 80.05%
need_memory: 1499/1664 = 90.08%
need_tools: 1563/1664 = 93.93%
tool_scope: 1327/1664 = 79.75%
risk_level: 1425/1664 = 85.64%
```

## 相比 Baseline

模板固定版 baseline：

```text
完全匹配: 428/1061 = 40.34%
错误率: 59.66%
```

V3_2 train：

```text
完全匹配: 1304/1664 = 78.37%
错误率: 21.63%
```

结论：

```text
V3 边界数据显著有效，train exact 提升 38.03 个百分点。
```

## 错误统计

错误文件共 `360` 条，其中 schema 非法样本 `14` 条。

字段错误：

```text
tool_scope: 323，占总样本 19.41%，占错误样本 89.72%
intent: 318，占总样本 19.11%，占错误样本 88.33%
risk_level: 225，占总样本 13.52%，占错误样本 62.50%
need_memory: 151，占总样本 9.07%，占错误样本 41.94%
need_tools: 87，占总样本 5.23%，占错误样本 24.17%
```

Top intent confusion：

```text
36 task_plan -> chat
29 tool_execution -> file_read
28 file_read -> tool_execution
27 chat -> profile_update
27 status_query -> memory_query
23 profile_update -> memory_query
19 profile_update -> content_save
18 task_plan -> profile_update
18 file_read -> profile_update
15 memory_query -> chat
15 tool_execution -> content_save
14 content_save -> tool_execution
14 status_query -> tool_execution
```

Top tool_scope confusion：

```text
36 task_tools -> none
28 unknown_tools -> shell_tools
28 file_read_tools -> shell_tools
27 none -> memory_tools
27 observe_tools -> memory_tools
24 memory_tools -> none
19 memory_tools -> content_tools
18 task_tools -> memory_tools
18 file_read_tools -> memory_tools
17 unknown_tools -> file_read_tools
15 unknown_tools -> content_tools
14 content_tools -> unknown_tools
14 observe_tools -> unknown_tools
```

Top risk confusion：

```text
56 read_only -> high_risk
45 write -> none
37 write -> read_only
33 read_only -> write
27 none -> write
15 read_only -> none
12 high_risk -> read_only
```

Top predicted combos：

```text
71 profile_update + memory_tools + write
60 chat + none + none
56 tool_execution + shell_tools + high_risk
50 memory_query + memory_tools + read_only
34 content_save + content_tools + write
29 file_read + file_read_tools + read_only
28 tool_execution + unknown_tools + read_only
18 status_query + observe_tools + read_only
14 invalid schema
```

Schema bad：

```text
14 intent=None
14 need_memory=None
14 need_tools=None
14 tool_scope=None
14 risk_level=None
```

典型非法输出：

```text
用户请求: 查询最近的 trace。
模型输出: intent=trace_trace_trace_trace...
```

## 本轮结论

V3 数据方向成立，尤其是 train exact 已经从 `40.34%` 提升到 `78.37%`。当前主要剩余问题不是整体不拟合，而是部分边界仍不清楚：

1. `task_plan` 容易被当成普通 `chat`。
2. `unknown_tools` 仍会被吸到 `shell_tools/high_risk`。
3. `file_read` 与 `tool_execution` 仍有双向混淆。
4. `profile_update` 与 `memory_query/content_save` 仍有混淆。
5. `trace` 相关请求仍可能触发 schema 外生成。

更具体的结论：

1. V3 hard negative 明显缓解了旧问题，`tool_execution + shell_tools + high_risk` 在错误样本中的预测次数从 baseline 的 `207` 次下降到 `56` 次。
2. 完全匹配率提升 `38.03` 个百分点，说明问题确实主要来自数据边界，而不是训练模板或 `max_seq_len`。
3. 当前主错误已经转移到更细的边界：`task_plan/chat`、`file_read/tool_execution`、`profile_update/memory_query`、`unknown_tools/shell_tools`。
4. `trace` 仍会诱导 schema 外输出，需要在下一版 prompt 或数据中明确 `trace` 属于 `status_query`，不是合法 intent。
5. 由于本轮只测了 train，还不能证明泛化，需要继续测 valid。

## Valid 补充结果

已完成 `route_v3_valid.jsonl` 评测：

```text
完全匹配: 290/355 = 81.69%
错误样本: 65/355 = 18.31%
Schema 合法: 353/355 = 99.44%
```

valid 比 train 高 `3.32` 个百分点，说明 V3 的提升不是单纯训练集记忆化。

## Test 补充结果

已完成 `route_v3_test.jsonl` 评测：

```text
完全匹配: 284/361 = 78.67%
错误样本: 77/361 = 21.33%
Schema 合法: 356/361 = 98.61%
```

train、valid、test 均稳定在 `78%-82%` 区间，`lora_route_v3_2` 冻结为当前阶段 baseline。

## 下一步

V3 方向可以作为当前主线。下一步按 `v3_1_fix_plan.md` 做 V3.1 小修数据，重点补 `trace/status_query`、`task_plan/chat/profile_update`、`profile_update/memory_query/content_save`。
