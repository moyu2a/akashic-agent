# MiniMind 训练交接说明

## 当前任务

训练 MiniRoute 小模型，用于判断用户请求的：

- `intent`
- `need_memory`
- `need_tools`
- `tool_scope`
- `risk_level`

输出必须是固定 JSON，不需要解释，不需要思考过程。

## 当前推荐数据

当前已完成 V3 训练和 train/valid/test 评测，`lora_route_v3_2` 可作为阶段性 baseline。下一轮应基于 V3.1 小修数据继续训练。

当前推荐 V3.1 数据：

```text
dataset/route_v3_1_train.jsonl
dataset/route_v3_1_valid.jsonl
dataset/route_v3_1_test.jsonl
```

对应上游文件：

```text
miniroute/data/route_v3_1_train.jsonl
miniroute/data/route_v3_1_valid.jsonl
miniroute/data/route_v3_1_test.jsonl
```

V3.1 数据规模：

```text
train: 1713
valid: 361
test: 380
total: 2454
delta_total: 74
```

## 已完成训练

已训练：

```text
full_sft + lora_route_v2
```

训练集评测：

```text
exact_match: 428/1061 = 40.34%
```

结论：

- V2 比 V1 有提升，但训练集仍未拟合。
- 不建议直接把 `lora_route_v2` 接入 MnemoAgent 主流程。

## 最新训练结论

已完成 `lora_route_v2_2` 对照训练：

```text
epochs: 3
batch_size: 16
max_seq_len: 1024
```

训练集评测：

```text
完全匹配: 428/1061 = 40.34%
```

与上一轮 `lora_route_v2` 相比，完全匹配没有变化，错误行集合完全一致。说明单纯加大 `max_seq_len` 不是当前主因。

## V3_2 阶段结论

已完成：

```text
full_sft + lora_route_v3_2
```

评测结果：

```text
train exact: 1304/1664 = 78.37%
valid exact: 290/355 = 81.69%
test exact: 284/361 = 78.67%
test schema valid: 356/361 = 98.61%
```

结论：

```text
V3 数据路线成立，lora_route_v3_2 冻结为当前阶段 baseline。
下一轮不急着移除 tool_scope，先做 V3.1 小修数据。
```

## 下一轮推荐方向

不再推荐继续单独拉高 `max_seq_len`。模板固定实验已经完成，训练侧和评测侧已统一格式。V3_2 已在 train/valid/test 上稳定，下一步推荐：

1. 生成 V3.1 小修数据，不覆盖 V3 文件。
2. 优先修复 `trace/status_query`，压低 schema bad。
3. 补 `task_plan/chat/profile_update`、`profile_update/memory_query/content_save`、`file_read/tool_execution`、`unknown_tools/file_read/content_save` 边界。
4. 训练新 LoRA，并与 V3_2 baseline 对比。
5. 如果 V3.1 无法继续提升，再考虑让小模型不直接输出 `tool_scope`，改为由规则从 `intent + risk_level` 映射。

## V3.1 推荐训练

```bash
cd /home/jjh/git_work/minimind/trainer

python train_lora.py \
  --data_path ../dataset/route_v3_1_train.jsonl \
  --from_weight full_sft \
  --lora_name lora_route_v3_1 \
  --epochs 3 \
  --batch_size 16 \
  --max_seq_len 1024 \
  --route_mode
```

V3.1 必须评测 train、valid、test 和 frozen V3 test bridge：

```bash
cd /home/jjh/git_work/minimind

python eval_route.py \
  --data_path dataset/route_v3_1_train.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v3_1 \
  --device cuda \
  --max_new_tokens 80 \
  --errors_path result/route_v3_1_train_errors.jsonl

python eval_route.py \
  --data_path dataset/route_v3_1_valid.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v3_1 \
  --device cuda \
  --max_new_tokens 80 \
  --errors_path result/route_v3_1_valid_errors.jsonl

python eval_route.py \
  --data_path dataset/route_v3_1_test.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v3_1 \
  --device cuda \
  --max_new_tokens 80 \
  --errors_path result/route_v3_1_test_errors.jsonl

python eval_route.py \
  --data_path dataset/route_v3_test.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v3_1 \
  --device cuda \
  --max_new_tokens 80 \
  --errors_path result/route_v3_1_bridge_v3_test_errors.jsonl
```

V3.1 验收门槛：

```text
route_v3_1_train exact > 82%
route_v3_1_valid exact > 83%
route_v3_1_test exact > 82%
route_v3_1_test schema bad <= 1
bridge route_v3_test exact >= 78.67%
```

## V3 推荐训练

```bash
cd /home/jjh/git_work/minimind/trainer

python train_lora.py \
  --data_path ../dataset/route_v3_train.jsonl \
  --from_weight full_sft \
  --lora_name lora_route_v3_boundary \
  --epochs 3 \
  --batch_size 16 \
  --max_seq_len 1024 \
  --route_mode
```

如果显存不足，优先降低 `batch_size`，不要降低 `max_seq_len`。

## 历史推荐训练

优先验证 `max_seq_len` 问题。

推荐训练命令：

```bash
cd /home/jjh/git_work/minimind/trainer

python train_lora.py \
  --data_path ../dataset/route_v2_train.jsonl \
  --lora_name lora_route_v2_len768 \
  --from_weight full_sft \
  --epochs 20 \
  --batch_size 16 \
  --learning_rate 2e-4 \
  --max_seq_len 768 \
  --device cuda:0
```

说明：

- V2 prompt 比 V1 长很多，不建议继续使用默认 `max_seq_len=340`。
- 先用 `max_seq_len=768` 验证训练集能否拟合。
- 如果显存不足，优先降低 `batch_size`，不要降低 `max_seq_len`。

## 评测命令

训练集：

```bash
cd /home/jjh/git_work/minimind

python eval_route.py \
  --data_path dataset/route_v2_train.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v2_len768 \
  --device cuda \
  --max_new_tokens 80 \
  --errors_path result/route_v2_len768_train_errors.jsonl
```

验证集：

```bash
python eval_route.py \
  --data_path dataset/route_v2_valid.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v2_len768 \
  --device cuda \
  --max_new_tokens 80 \
  --errors_path result/route_v2_len768_valid_errors.jsonl
```

测试集：

```bash
python eval_route.py \
  --data_path dataset/route_v2_test.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v2_len768 \
  --device cuda \
  --max_new_tokens 80 \
  --errors_path result/route_v2_len768_test_errors.jsonl
```

## 结果记录要求

每次训练后记录：

1. 训练命令。
2. 权重名称。
3. `max_seq_len`、epoch、batch size、learning rate。
4. train/valid/test 指标。
5. 错误样本路径。
6. 是否出现 schema 外输出。
7. Top 混淆模式。
8. 下一步决策。
