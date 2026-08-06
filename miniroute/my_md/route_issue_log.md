# MiniRoute 问题记录

本文件持续记录 MiniRoute 数据、训练、评测中发现的问题。每次新实验后追加，不覆盖旧结论。

## Issue 001: V2 训练集仍未拟合

- 状态: 已确认
- 发现时间: 2026-08-05
- 影响范围: `lora_route_v2`

### 现象

本轮实验使用 `route_v2_train.jsonl` 训练 LoRA，并直接在同一个训练集上评测。`full_sft + lora_route_v2` 在训练集上只有：

```text
完全匹配: 428/1061 = 40.34%
```

`lora_route_v2_2` 使用 `max_seq_len=1024` 重新训练后，训练集完全匹配仍为：

```text
完全匹配: 428/1061 = 40.34%
```

### 判断

训练集准确率仍低，说明当前问题不是验证集泛化差，而是模型没有充分学会训练数据中的路由语义。后续不能把 `40.34%` 解释为“测试集太难”，而应视为训练集拟合失败。

### 下一步

优先排查：

1. `max_seq_len` 是否过短导致训练样本截断。
2. 训练 epoch、学习率、batch size 是否不足。
3. 训练和评测 chat template 是否一致。
4. 类别边界是否仍过于相似。

## Issue 002: 过度预测 shell 工具和高风险

- 状态: 已确认
- 发现时间: 2026-08-05
- 影响范围: `tool_scope`、`risk_level`

### 证据

错误样本中大量请求被预测为：

```json
{
  "intent": "tool_execution",
  "tool_scope": ["shell_tools"],
  "risk_level": "high_risk"
}
```

主要混淆：

```text
status_query -> tool_execution: 59
file_read -> tool_execution: 52
content_save -> tool_execution: 47
chat -> tool_execution: 32
unknown_tools -> shell_tools: 32
```

风险混淆：

```text
read_only -> high_risk: 143
write -> high_risk: 80
none -> high_risk: 32
```

### 判断

模型把“查看、检查、保存、调用、工具”等词面过度联想到 shell 执行和高风险。V2 的边界样本还不够，或者训练长度不足导致模型没有学到 prompt 中的风险边界。

### 下一步

先验证训练长度。如果 `max_seq_len=768` 后仍然严重过度预测 high_risk，V3 需要增加大量 read-only/write 与 high-risk 的成对反例。

## Issue 003: 普通 chat 容易误判为 memory_query

- 状态: 已确认
- 发现时间: 2026-08-05
- 影响范围: `chat`、`memory_query`

### 证据

```text
chat -> memory_query: 41
chat -> tool_execution: 32
chat -> profile_update: 16
```

典型样本：

```text
说明一下 rm 命令会做什么，不要执行。
总结一下这个观点的优缺点。
保存机制是什么意思？
```

### 判断

模型对“记忆、保存、命令、偏好”等词面过度敏感，没有稳定理解“解释概念、不执行、不保存”的 chat 边界。

### 下一步

V3 如果需要继续做数据，应增加更多 hard negative：

- 包含“保存/记忆/偏好/工具/命令”，但只是解释概念。
- 明确“不需要查文件、不需要执行、不需要保存”的普通分析请求。

## Issue 004: profile_update 与 memory_query/content_save 混淆

- 状态: 已确认
- 发现时间: 2026-08-05
- 影响范围: `profile_update`、`memory_query`、`content_save`

### 证据

```text
profile_update -> content_save: 50
profile_update -> memory_query: 28
profile_update -> tool_execution: 17
```

典型样本：

```text
请记住我以后喜欢简洁回答。
以后默认先给结论再解释。
把我的偏好更新成少用英文。
```

### 判断

模型没有稳定区分：

- 查询历史偏好：`memory_query`
- 更新用户偏好：`profile_update`
- 保存外部内容：`content_save`

### 下一步

如果 `max_seq_len=768` 后仍不改善，V3 应加入三类成对样本：

- “我之前喜欢什么？” -> `memory_query`
- “以后我喜欢什么。” -> `profile_update`
- “保存这个链接/文章/视频。” -> `content_save`

## Issue 005: 仍有 schema 外输出

- 状态: 已确认
- 发现时间: 2026-08-05
- 影响范围: 输出合法性

### 证据

V2 训练集错误中仍有 `16` 条：

```json
{"intent": "trace"}
```

### 判断

V2 prompt 枚举约束还没有被当前 LoRA 完全学稳。虽然可提取 JSON 达到 `100.00%`，但字段合法性仍需要治理。

### 下一步

短期在运行时做 schema 校验和回退。训练侧继续通过更长上下文训练、更多 status_query 样本和负例压制 `trace` 这类自由标签。

## Issue 006: max_seq_len 过短不是当前主因

- 状态: 已验证
- 发现时间: 2026-08-05
- 影响范围: MiniMind LoRA 训练

### 证据

MiniMind `trainer/train_lora.py` 默认：

```text
--max_seq_len 340
```

V2 样本长度：

```text
user prompt 字符数: 646-661
assistant JSON 字符数: 107-130
```

### 原始判断

如果训练时没有显式设置更大的 `max_seq_len`，V2 样本可能被截断，导致 assistant JSON 监督不足或完全不完整。这会解释为什么训练集本身仍然只有 `40.34%` 完全匹配。

### 验证结果

已训练 `lora_route_v2_2`：

```text
epochs: 3
batch_size: 16
max_seq_len: 1024
```

训练集评测：

```text
完全匹配: 428/1061 = 40.34%
intent: 526/1061 = 49.58%
need_memory: 856/1061 = 80.68%
need_tools: 939/1061 = 88.50%
tool_scope: 536/1061 = 50.52%
risk_level: 614/1061 = 57.87%
```

与上一轮 `lora_route_v2` 对比：

```text
错误行数: 633 -> 633
错误行集合交集: 633
old_only: 0
new_only: 0
```

### 当前判断

单纯增加 `max_seq_len` 没有解决训练集不能拟合的问题。它只改善了 `need_tools` 和 `risk_level` 的少数字段，但完全匹配、`intent`、`tool_scope` 没有变化。

### 下一步

停止把训练长度作为主线优化方向，转向 V3 数据边界设计和训练/评测模板核查。

## Issue 007: V2 错误行集合稳定，说明存在固定判别边界问题

- 状态: 已确认
- 发现时间: 2026-08-05
- 影响范围: V3 数据设计

### 证据

`lora_route_v2` 与 `lora_route_v2_2` 的错误行集合完全一致：

```text
old errors: 633
new errors: 633
intersection: 633
old_only: 0
new_only: 0
```

### 判断

这不是随机训练波动，而是模型在固定样本上形成了稳定错误边界。V3 应针对这些错误行设计反例，而不是继续平均扩充所有类别。

### 下一步

优先补强以下边界：

1. `status_query` vs `tool_execution`
2. `file_read` vs `tool_execution`
3. `content_save` vs `tool_execution`
4. `chat` vs `memory_query`
5. `profile_update` vs `memory_query` vs `content_save`
6. `unknown_tools` vs `shell_tools`

## Issue 008: 训练和评测模板不一致

- 状态: 已验证，已排除为当前主因
- 发现时间: 2026-08-05
- 影响范围: MiniMind LoRA 训练和 `eval_route.py` 评测

### 证据

对同一条 `route_v2_train.jsonl` 样本进行模板检查，训练侧不同随机种子下出现了多种 prompt 形态：

```text
seed 0 has_system=False has_empty_think=False prefix_equal_eval=False
seed 1 has_system=True  has_empty_think=False prefix_equal_eval=False
seed 4 has_system=False has_empty_think=True  prefix_equal_eval=True
seed 7 has_system=False has_empty_think=True  prefix_equal_eval=True
```

训练侧 `SFTDataset` 会经过：

```text
pre_processing_chat(): 约 20% 概率插入 system prompt
post_processing_chat(): 约 80% 概率移除空 <think></think>
```

评测侧 `eval_route.py` 使用：

```python
tokenizer.apply_chat_template(
    prompt_conv,
    tokenize=False,
    add_generation_prompt=True,
    open_thinking=False,
)
```

因此评测侧固定是“无额外 system + 带空 think”的生成格式。

### 判断

这说明同一条 route 样本在训练中大多数时候不是评测时看到的 prompt 前缀。粗略看，只有“未插入 system 且保留空 think”的训练样本会与评测前缀一致；在当前默认概率下，这类样本大约只占少数。

这会削弱 LoRA 对路由 JSON 的学习，尤其是本任务要求严格输出固定字段，prompt 前缀差异会直接影响 assistant 起始位置后的分布。

### 下一步

已完成模板固定对照实验：

1. 训练侧为 route 任务禁用随机 system 注入。
2. 训练侧和评测侧统一 empty think 处理。
3. 训练和评测使用一致的 chat template。

最新结果仍出现大量类别混淆，因此模板不一致不是当前主要原因。后续不再把模板修正作为主线，转向 V3 边界数据设计和输出空间简化。

## Issue 009: 只在评测侧 strip empty think 会破坏严格 JSON

- 状态: 已确认
- 发现时间: 2026-08-05
- 影响范围: `eval_route.py` 评测方式

### 证据

`eval_route.py` 加入：

```python
prompt = prompt.replace("<think>\n\n</think>\n\n", "")
```

随后评测 `lora_route_v3`：

```text
严格只输出 JSON: 0/1061 = 0.00%
可提取 JSON: 1061/1061 = 100.00%
完全匹配: 446/1061 = 42.04%
```

错误样本中模型输出全部以 `<think>` 开头：

```text
prefix Counter({'think': 615})
```

### 判断

评测侧去掉 empty think 后，模型在 assistant 起始位置主动生成 `<think>\n\n</think>\n\n`，所以严格 JSON 指标被直接打到 `0%`。

这说明 route 任务不适合只在评测侧 strip empty think。当前更稳的路线是保留评测侧 empty think，并让训练侧固定保留 empty think。

### 下一步

下一轮模板固定训练应采用：

```text
训练侧: 无随机 system + 保留 empty think
评测侧: 无额外 system + 保留 empty think
```

不要再把 `prompt.replace("<think>\n\n</think>\n\n", "")` 作为默认评测逻辑。可以保留为对照开关，但不应作为主评测方式。

## Issue 010: 模板固定后仍存在稳定类别混淆

- 状态: 已确认
- 发现时间: 2026-08-05
- 影响范围: V3 数据设计、输出字段设计

### 证据

最新训练结果来自已修改训练侧和评测侧后的模板一致版本，但仍出现以下高频混淆：

```text
status_query -> tool_execution: 59
file_read -> tool_execution: 52
content_save -> tool_execution: 47
profile_update -> memory_query: 46
chat -> memory_query: 41
chat -> profile_update: 35
```

工具范围混淆：

```text
none -> memory_tools: 76
observe_tools -> shell_tools: 59
file_read_tools -> shell_tools: 52
content_tools -> shell_tools: 47
unknown_tools -> shell_tools: 16
```

风险等级混淆：

```text
read_only -> high_risk: 127
write -> high_risk: 80
write -> read_only: 61
none -> read_only: 41
```

预测组合高度集中：

```text
tool_execution + shell_tools + high_risk: 207
memory_query + memory_tools + read_only: 144
profile_update + memory_tools + write: 65
```

仍有 schema 外输出：

```text
intent=trace: 16
tool_scope=None: 16
risk_level=None: 16
```

### 判断

模板一致后问题仍存在，说明当前主要矛盾已经转为：

1. 类别边界样本不足，尤其是只读、写入和高风险之间的反例不够。
2. 模型对“查看、保存、工具、命令、状态、记忆”等词面过度敏感。
3. `intent` 与 `tool_scope` 高度绑定，但同时生成会放大连锁错误。
4. 当前五字段联合生成任务对 64M 小模型偏难。

### 下一步

优先做 V3 数据边界修正：

1. 补 `status_query/file_read/content_save` 与 `tool_execution` 的成对反例。
2. 补 `chat` 与 `memory_query/profile_update` 的 hard negative。
3. 补 `profile_update/memory_query/content_save` 三类边界样本。
4. 补 `unknown_tools` 与 `shell_tools` 的边界样本。

如果 V3 训练集仍难以拟合，改为简化输出空间：小模型不直接输出 `tool_scope`，而是由规则根据 `intent + risk_level` 映射。
