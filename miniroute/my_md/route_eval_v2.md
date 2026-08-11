# MiniRoute V2 评测记录

## 评测目标

本轮评测用于判断 `lora_route_v2` 是否已经学会 V2 路由数据，尤其是训练集是否能够被拟合。

如果训练集准确率仍低，优先排查训练长度、训练参数、模板一致性和标签边界，而不是直接把问题归因于验证集泛化。

## 重要前提: 本轮是训练集评测

本轮实验使用 `dataset/route_v2_train.jsonl` 训练 LoRA，并直接在同一个 `dataset/route_v2_train.jsonl` 上评测。

因此，`40.34%` 完全匹配率不能解释为“验证集太难”或“泛化不足”。它首先说明模型连训练过的数据都没有稳定学会，即训练集拟合失败。

后续分析应优先围绕：

1. 训练和评测模板是否一致。
2. LoRA 学习能力和训练范式是否足够。
3. 标签边界是否对 64M 小模型过难。
4. 是否需要降低输出空间复杂度，例如由规则映射 `tool_scope`。

## 评测环境

评测位置：

```text
/home/jjh/git_work/minimind
```

数据文件：

```text
dataset/route_v2_train.jsonl
```

错误样本输出：

```text
/home/jjh/git_work/minimind/result/route_v2_train_errors.jsonl
```

模型：

```text
full_sft + lora_route_v2
```

参数规模：

```text
Model Params: 64.31M
```

## 评测命令

```bash
python eval_route.py \
  --data_path dataset/route_v2_train.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v2 \
  --device cuda \
  --max_new_tokens 80 \
  --errors_path route_v2_train_errors.jsonl
```

## 总体结果

```text
数据集: dataset/route_v2_train.jsonl
模型: full_sft + lora_route_v2
总数: 1061
严格只输出 JSON: 1047/1061 = 98.68%
可提取 JSON: 1061/1061 = 100.00%
完全匹配: 428/1061 = 40.34%
```

字段准确率：

```text
intent: 526/1061 = 49.58%
need_memory: 856/1061 = 80.68%
need_tools: 905/1061 = 85.30%
tool_scope: 536/1061 = 50.52%
risk_level: 598/1061 = 56.36%
```

## 和 V1 的对比

V1 训练集结果：

```text
完全匹配: 261/875 = 29.83%
intent: 330/875 = 37.71%
need_memory: 675/875 = 77.14%
need_tools: 574/875 = 65.60%
tool_scope: 414/875 = 47.31%
risk_level: 432/875 = 49.37%
```

V2 训练集结果：

```text
完全匹配: 428/1061 = 40.34%
intent: 526/1061 = 49.58%
need_memory: 856/1061 = 80.68%
need_tools: 905/1061 = 85.30%
tool_scope: 536/1061 = 50.52%
risk_level: 598/1061 = 56.36%
```

结论：

- V2 比 V1 有提升，说明标签口径和 prompt 枚举修正有效。
- `need_tools` 从 `65.60%` 提升到 `85.30%`，提升最明显。
- 训练集完全匹配仍只有 `40.34%`，说明当前模型仍没有拟合训练集。
- 当前主要问题已经从“字段自相矛盾”转为“类别边界、训练长度和模型学习能力不足”。

## 错误样本统计

错误样本数量：

```text
633 /home/jjh/git_work/minimind/result/route_v2_train_errors.jsonl
```

错误样本中的字段错误计数：

```text
intent: 535
tool_scope: 525
risk_level: 463
need_memory: 205
need_tools: 156
```

说明：

- `intent`、`tool_scope`、`risk_level` 是主要错误来源。
- `need_tools` 已经明显改善，但仍会被其他字段错误拖累完全匹配。

## 主要混淆模式

Top intent 混淆：

```text
59 status_query -> tool_execution
52 file_read -> tool_execution
50 memory_query -> memory_query
50 profile_update -> content_save
47 content_save -> tool_execution
41 chat -> memory_query
33 task_plan -> chat
32 chat -> tool_execution
32 tool_execution -> tool_execution
28 profile_update -> memory_query
21 file_read -> content_save
18 status_query -> chat
18 file_read -> memory_query
17 profile_update -> tool_execution
16 status_query -> trace
16 task_plan -> tool_execution
16 chat -> profile_update
```

Top tool_scope 混淆：

```text
59 observe_tools -> shell_tools
57 none -> memory_tools
52 file_read_tools -> shell_tools
50 memory_tools -> content_tools
47 content_tools -> shell_tools
33 task_tools -> none
32 none -> shell_tools
32 unknown_tools -> shell_tools
21 file_read_tools -> content_tools
18 observe_tools -> none
18 file_read_tools -> memory_tools
17 memory_tools -> shell_tools
16 observe_tools -> missing
16 task_tools -> shell_tools
15 task_tools -> memory_tools
```

Top risk_level 混淆：

```text
143 read_only -> high_risk
80 write -> high_risk
43 write -> read_only
41 none -> read_only
41 read_only -> write
33 write -> none
32 none -> high_risk
18 read_only -> none
16 read_only -> missing
16 none -> write
```

## Schema 外输出

仍发现 `16` 条 schema 外 intent：

```json
{"intent": "trace"}
```

这说明 V2 prompt 的枚举约束有帮助，但 LoRA 当前还没有完全压住基础模型的自由生成倾向。

## 当前判断

本轮 V2 结果不能直接判定为“数据集没用”。更准确的判断是：

1. V2 数据集修复方向有效，但提升不够。
2. 训练集仍未拟合，所以问题不只是验证集泛化。
3. 错误集中在几个固定偏置上：
   - 过度预测 `tool_execution + shell_tools + high_risk`。
   - 把普通对话误判为 `memory_query`。
   - 把画像更新误判为内容保存或记忆查询。
   - 把状态查询误判为 shell 工具执行。
   - 把 `unknown_tools` 误判为 `shell_tools`。
4. 当前优先怀疑训练长度问题。V2 user prompt 约 `646-661` 字符，assistant JSON 约 `107-130` 字符；如果训练时仍使用 MiniMind `train_lora.py` 默认 `max_seq_len=340`，可能导致样本被截断或 assistant 监督不足。

## 下一步

已完成 `max_seq_len=1024` 对照训练，结果见下方。该实验表明训练长度不是当前主因，下一步进入 V3 数据边界设计，并继续核查训练/评测模板。

## 追加评测: lora_route_v2_2

### 训练命令

```bash
cd ~/autodl-tmp/minimind/trainer

python train_lora.py \
  --data_path ../dataset/route_v2_train.jsonl \
  --from_weight full_sft \
  --lora_name lora_route_v2_2 \
  --epochs 3 \
  --batch_size 16 \
  --max_seq_len 1024
```

训练日志显示 loss 下降明显：

```text
Epoch 1 end loss: 0.0978
Epoch 2 end loss: 0.0522
Epoch 3 end loss: 0.0289
```

### 评测命令

```bash
cd ~/autodl-tmp/minimind

python eval_route.py \
  --data_path dataset/route_v2_train.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v2_2 \
  --device cuda \
  --max_new_tokens 80 \
  --errors_path route_v2_2_train_errors.jsonl
```

本地同步错误文件：

```text
/home/jjh/git_work/minimind/result/route_v2_2_train_errors.jsonl
```

### 总体结果

```text
数据集: dataset/route_v2_train.jsonl
模型: full_sft + lora_route_v2_2
总数: 1061
严格只输出 JSON: 1047/1061 = 98.68%
可提取 JSON: 1061/1061 = 100.00%
完全匹配: 428/1061 = 40.34%
```

字段准确率：

```text
intent: 526/1061 = 49.58%
need_memory: 856/1061 = 80.68%
need_tools: 939/1061 = 88.50%
tool_scope: 536/1061 = 50.52%
risk_level: 614/1061 = 57.87%
```

### 和 lora_route_v2 对比

```text
完全匹配: 40.34% -> 40.34%
intent: 49.58% -> 49.58%
need_memory: 80.68% -> 80.68%
need_tools: 85.30% -> 88.50%
tool_scope: 50.52% -> 50.52%
risk_level: 56.36% -> 57.87%
```

错误文件对比：

```text
lora_route_v2 错误行数: 633
lora_route_v2_2 错误行数: 633
错误行集合交集: 633
old_only: 0
new_only: 0
```

### 主要变化

- `need_tools` 从 `85.30%` 提升到 `88.50%`。
- `risk_level` 从 `56.36%` 提升到 `57.87%`。
- `intent`、`tool_scope` 和完全匹配没有变化。
- 错误行集合完全一致，说明 `max_seq_len=1024` 没有改变哪些样本被模型判错。
- schema 外输出仍有 `16` 条，但从 `trace` 变成了 `tracepse_tool_execution`，说明枚举外生成仍未解决。

### 结论

`max_seq_len=1024` 不是当前主要瓶颈。虽然更长上下文让少数字段略有改善，但没有提升完全匹配，也没有改变错误样本集合。

当前主因更可能是：

1. 类别边界样本不足，模型按词面触发 `shell_tools/high_risk` 和 `memory_tools`。
2. V2 数据表达仍过于模板化，同一类句式重复较多，模型没有学到足够稳的判别边界。
3. 输出空间对 64M 小模型仍偏复杂，`intent + tool_scope + risk_level` 的组合关系难学。
4. 训练/评测模板仍需核查，但它已经不是唯一可解释因素。

下一步应开始 V3 数据设计，而不是继续单纯增加 `max_seq_len`。

## 追加评测: lora_route_v3 strip-empty-think 尝试

### 操作记录

评测侧确认加入了 prompt 替换：

```bash
grep -n "prompt.replace" eval_route.py
```

输出：

```text
94:            prompt = prompt.replace("<think>\n\n</think>\n\n", "")
```

随后训练：

```bash
cd ~/autodl-tmp/minimind/trainer

python train_lora.py \
  --data_path ../dataset/route_v2_train.jsonl \
  --from_weight full_sft \
  --lora_name lora_route_v3 \
  --epochs 3 \
  --batch_size 16 \
  --max_seq_len 1024
```

评测：

```bash
cd ~/autodl-tmp/minimind

python eval_route.py \
  --data_path dataset/route_v2_train.jsonl \
  --weight full_sft \
  --lora_weight lora_route_v3 \
  --device cuda \
  --max_new_tokens 80 \
  --errors_path route_v3_test_errors.jsonl
```

注意：虽然错误文件名是 `route_v3_test_errors.jsonl`，但实际评测数据是训练集 `dataset/route_v2_train.jsonl`。

### 总体结果

```text
数据集: dataset/route_v2_train.jsonl
模型: full_sft + lora_route_v3
总数: 1061
严格只输出 JSON: 0/1061 = 0.00%
可提取 JSON: 1061/1061 = 100.00%
完全匹配: 446/1061 = 42.04%
```

字段准确率：

```text
intent: 475/1061 = 44.77%
need_memory: 903/1061 = 85.11%
need_tools: 919/1061 = 86.62%
tool_scope: 501/1061 = 47.22%
risk_level: 578/1061 = 54.48%
```

### 和 lora_route_v2_2 对比

```text
完全匹配: 40.34% -> 42.04%
错误行数: 633 -> 615
intent: 49.58% -> 44.77%
need_memory: 80.68% -> 85.11%
need_tools: 88.50% -> 86.62%
tool_scope: 50.52% -> 47.22%
risk_level: 57.87% -> 54.48%
```

错误行集合变化：

```text
old errors: 633
new errors: 615
intersection: 564
old_only: 69
new_only: 51
```

### 关键现象

`lora_route_v3` 的错误样本输出全部以 `<think>` 开头：

```text
prefix Counter({'think': 615})
```

这解释了为什么严格 JSON 是 `0.00%`：评测侧把 prompt 中的空 think 去掉后，模型在生成阶段又主动补出了 `<think>\n\n</think>\n\n`，然后再输出 JSON。虽然 JSON 可提取率仍是 `100.00%`，但严格输出格式变差。

### 当前判断

这次实验不能证明“模板固定训练有效”。更准确的判断是：

1. 只在评测侧 strip empty think 会诱发模型重新生成 `<think>`，导致严格 JSON 降到 `0%`。
2. 完全匹配只从 `40.34%` 小幅升到 `42.04%`，但 `intent`、`tool_scope`、`risk_level` 反而下降。
3. 这不是理想方向。route 任务更适合让训练和评测都固定为“无额外 system + 保留 empty think”的模板，因为该模板下严格 JSON 表现更稳定。
4. 下一轮应恢复评测侧 empty think，并在训练侧禁用随机 system 注入和随机 empty think 移除，使训练模板和评测模板真正一致。
