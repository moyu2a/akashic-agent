# MiniRoute V3_2 Valid 评测记录

## 基本信息

- 实验日期: 2026-08-05
- 数据集: `dataset/route_v3_valid.jsonl`
- LoRA: `lora_route_v3_2`
- 评测集类型: valid
- 错误文件: `/home/jjh/git_work/minimind/result/route_v3_valid.jsonl`

## 测试方法

valid 评测用于判断 V3 边界数据是否具备泛化能力，不能只看 train 结果。

评测命令：

```bash
cd ~/autodl-tmp/minimind

python eval_route.py \
  --data_path dataset/route_v3_valid.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v3_2 \
  --device cuda \
  --max_new_tokens 80 \
  --errors_path route_v3_valid.jsonl
```

说明：

```text
实际错误文件位于 /home/jjh/git_work/minimind/result/route_v3_valid.jsonl。
错误文件共有 65 行，与 355 - 290 = 65 对齐。
```

## 总体结果

```text
总数: 355
严格只输出 JSON: 353/355 = 99.44%
可提取 JSON: 353/355 = 99.44%
Schema 合法: 353/355 = 99.44%
完全匹配: 290/355 = 81.69%
错误样本: 65/355 = 18.31%
```

字段准确率：

```text
intent: 294/355 = 82.82%
need_memory: 327/355 = 92.11%
need_tools: 336/355 = 94.65%
tool_scope: 298/355 = 83.94%
risk_level: 307/355 = 86.48%
```

## 对比结果

模板固定版 baseline：

```text
train exact: 428/1061 = 40.34%
```

V3_2 train：

```text
train exact: 1304/1664 = 78.37%
```

V3_2 valid：

```text
valid exact: 290/355 = 81.69%
```

结论：

```text
V3 valid 比 train 高 3.32 个百分点，说明当前提升不是单纯训练集记忆化。
V3 相比 baseline 提升 41.35 个百分点。
```

## 错误统计

错误样本共 `65` 条，其中 schema 非法样本 `2` 条。

字段错误：

```text
intent: 59，占总样本 16.62%，占错误样本 90.77%
tool_scope: 55，占总样本 15.49%，占错误样本 84.62%
risk_level: 46，占总样本 12.96%，占错误样本 70.77%
need_memory: 26，占总样本 7.32%，占错误样本 40.00%
need_tools: 17，占总样本 4.79%，占错误样本 26.15%
```

Top intent confusion：

```text
8 tool_execution -> file_read
8 profile_update -> memory_query
6 task_plan -> chat
5 status_query -> memory_query
5 memory_query -> chat
5 file_read -> tool_execution
4 chat -> profile_update
4 file_read -> profile_update
3 tool_execution -> content_save
2 memory_query -> status_query
2 profile_update -> content_save
2 profile_update -> chat
2 content_save -> profile_update
1 tool_execution -> status_query
1 content_save -> tool_execution
1 status_query -> tool_execution
```

Top tool_scope confusion：

```text
7 memory_tools -> none
6 task_tools -> none
5 observe_tools -> memory_tools
5 file_read_tools -> shell_tools
4 none -> memory_tools
4 shell_tools -> file_read_tools
4 file_read_tools -> memory_tools
4 unknown_tools -> file_read_tools
4 unknown_tools -> shell_tools
3 unknown_tools -> content_tools
```

Top risk confusion：

```text
9 write -> read_only
9 read_only -> high_risk
8 write -> none
7 read_only -> write
5 read_only -> none
4 none -> write
4 high_risk -> read_only
```

Top predicted combos：

```text
13 memory_query + memory_tools + read_only
13 chat + none + none
10 profile_update + memory_tools + write
9 tool_execution + shell_tools + high_risk
8 file_read + file_read_tools + read_only
5 content_save + content_tools + write
3 status_query + observe_tools + read_only
2 tool_execution + unknown_tools + read_only
2 invalid schema
```

Schema bad：

```text
2 intent=None
2 need_memory=None
2 need_tools=None
2 tool_scope=None
2 risk_level=None
```

典型非法输出：

```text
用户请求: 查询最近的 trace。
模型输出: intent=trace_trace_trace_trace...
```

## 本轮结论

V3 数据在 valid 上验证有效。当前结果满足前一轮设定的判断标准：

```text
train exact > 60%: 78.37%，通过
valid exact > 55%: 81.69%，通过
schema bad 接近 0: 2/355 = 0.56%，基本通过
高风险 shell 过度预测明显下降: 通过
```

当前剩余问题已经从“大量高风险 shell 误判”转为更细的边界问题：

1. `profile_update` 与 `memory_query` 仍需补边界。
2. `task_plan` 仍容易被判为 `chat`。
3. `tool_execution` 与 `file_read/content_save/status_query` 仍有少量混淆。
4. `trace` 请求仍会诱导 schema 外输出。

## 下一步

V3 方向可以作为当前主线。下一步建议：

1. V3_2 test 已完成，`284/361 = 78.67%`，可以冻结为当前阶段 baseline。
2. 按 `v3_1_fix_plan.md` 设计 V3.1 小修数据，重点补 `trace/status_query`、`task_plan/chat/profile_update`、`profile_update/memory_query/content_save`。
3. 暂时不急着移除 `tool_scope`，因为 V3 test 已经达到 `78.67%`。
