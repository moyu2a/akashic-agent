# MiniRoute V3.1 Train 评测记录

## 基本信息

- 实验日期: 2026-08-06
- 数据集: `dataset/route_v3_1_train.jsonl`
- LoRA: `lora_route_v3_1`
- 评测集类型: train
- 错误文件: `/home/jjh/git_work/minimind/result/route_v3_1_train_errors.jsonl`

## 训练方法

```bash
cd ~/autodl-tmp/minimind/trainer

python train_lora.py \
  --data_path ../dataset/route_v3_1_train.jsonl \
  --from_weight full_sft \
  --lora_name lora_route_v3_1 \
  --epochs 3 \
  --batch_size 16 \
  --max_seq_len 1024
```

训练日志：

```text
训练样本: 1713
每轮 step: 108
Epoch 1 end loss: 0.0363
Epoch 2 end loss: 0.0125
Epoch 3 end loss: 0.0198
```

训练过程正常收敛，但第三轮结束 loss 高于第二轮，说明继续增加训练轮数不一定带来更好结果，最终仍以结构化评测为准。

## 测试方法

```bash
cd ~/autodl-tmp/minimind

python eval_route.py \
  --data_path dataset/route_v3_1_train.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v3_1 \
  --device cuda \
  --max_new_tokens 80 \
  --errors_path route_v3_1_train_errors.jsonl
```

## 测试结果

```text
总数: 1713
严格只输出 JSON: 1713/1713 = 100.00%
可提取 JSON: 1713/1713 = 100.00%
Schema 合法: 1712/1713 = 99.94%
完全匹配: 1357/1713 = 79.22%
错误样本: 356/1713 = 20.78%
```

字段准确率：

```text
intent: 1385/1713 = 80.85%
need_memory: 1609/1713 = 93.93%
need_tools: 1595/1713 = 93.11%
tool_scope: 1379/1713 = 80.50%
risk_level: 1438/1713 = 83.95%
```

与 V3_2 train 对比：

| 指标 | V3_2 | V3.1 | 变化 |
| --- | ---: | ---: | ---: |
| 完全匹配 | 78.37% | 79.22% | +0.85 个百分点 |
| intent | 80.05% | 80.85% | +0.80 个百分点 |
| need_memory | 90.08% | 93.93% | +3.85 个百分点 |
| need_tools | 93.93% | 93.11% | -0.82 个百分点 |
| tool_scope | 79.75% | 80.50% | +0.75 个百分点 |
| risk_level | 85.64% | 83.95% | -1.69 个百分点 |
| Schema 合法 | 99.16% | 99.94% | +0.78 个百分点 |

## 错误统计

错误文件共 `356` 条，schema 非法样本 `1` 条。

字段错误：

```text
tool_scope: 334，占总样本 19.50%，占错误样本 93.82%
intent: 328，占总样本 19.15%，占错误样本 92.13%
risk_level: 275，占总样本 16.05%，占错误样本 77.25%
need_tools: 118，占总样本 6.89%，占错误样本 33.15%
need_memory: 104，占总样本 6.07%，占错误样本 29.21%
```

Top intent confusion：

```text
31 memory_query -> chat
28 file_read -> tool_execution
25 profile_update -> chat
23 tool_execution -> file_read
23 tool_execution -> content_save
20 task_plan -> tool_execution
19 task_plan -> chat
19 profile_update -> content_save
19 file_read -> content_save
18 file_read -> status_query
16 chat -> profile_update
15 status_query -> tool_execution
15 chat -> content_save
13 memory_query -> profile_update
11 memory_query -> status_query
10 status_query -> chat
```

Top tool_scope confusion：

```text
56 memory_tools -> none
29 file_read_tools -> observe_tools
28 unknown_tools -> shell_tools
23 unknown_tools -> content_tools
20 task_tools -> shell_tools
19 task_tools -> none
19 memory_tools -> content_tools
19 file_read_tools -> content_tools
17 file_read_tools -> shell_tools
16 none -> memory_tools
15 none -> content_tools
14 observe_tools -> shell_tools
```

Top risk confusion：

```text
59 read_only -> high_risk
55 read_only -> write
44 write -> none
42 read_only -> none
32 none -> write
20 write -> high_risk
13 high_risk -> read_only
```

Top predicted combos：

```text
85 chat + none + none
79 tool_execution + shell_tools + high_risk
76 content_save + content_tools + write
38 status_query + observe_tools + read_only
30 profile_update + memory_tools + write
25 file_read + file_read_tools + read_only
11 tool_execution + observe_tools + read_only
9 memory_query + memory_tools + read_only
1 trace + none + none
```

## 出错原因

1. **五字段联动错误仍然存在**  
   `intent`、`tool_scope`、`risk_level` 同时出错，说明模型仍然依赖固定组合，而不是先理解用户动作再独立判断风险和工具范围。

2. **记忆类边界仍不稳定**  
   `memory_query -> chat: 31`、`profile_update -> chat: 25`、`profile_update -> content_save: 19`。模型仍无法稳定区分“查询过去记忆”“更新未来偏好”“保存外部内容”。

3. **文件读取和工具执行仍然双向混淆**  
   `file_read -> tool_execution: 28`、`tool_execution -> file_read: 23`。模型对“打开、查看、覆盖、执行”等动作词的风险边界仍不稳定。

4. **task_plan 仍被吸收到 chat 或高风险工具执行**  
   `task_plan -> tool_execution: 20`、`task_plan -> chat: 19`。当前训练数据对“现在创建计划”和“解释计划概念”的区分仍不够。

5. **unknown_tools 仍被错误映射到 shell/content**  
   `unknown_tools -> shell_tools: 28`、`unknown_tools -> content_tools: 23`。OCR、图片识别、音频转写等任务还没有形成稳定的未知工具域边界。

6. **schema 合法性明显改善，但 trace 问题没有完全消失**  
   schema bad 从 V3_2 train 的 `14` 条降到 `1` 条，但仍出现 `intent=trace`，需要继续补 trace/status_query 对照样本。

## 本轮结论

V3.1 train 结果为 `79.22%`，相比 V3_2 train 的 `78.37%` 仅提升 `0.85` 个百分点，尚未达到计划目标 `>82%`。

本轮可以确认：

- schema 约束有效，合法率从 `99.16%` 提升到 `99.94%`。
- `need_memory` 提升明显。
- 整体 intent、tool_scope、risk_level 边界没有获得实质性改善。
- V3.1 小修数据目前不能仅凭 train 结果判定成功。

## 下一步

继续评测 V3.1 valid、V3.1 test 和 frozen V3 test bridge：

1. 如果 valid/test 达到目标，并且 bridge 不低于 `78.67%`，再保留 V3.1。
2. 如果 valid/test 也只有约 `79%`，说明当前小修数据不足，需要重新设计边界样本。
3. 在 valid/test 结果出来前，不替换 `lora_route_v3_2` baseline。
