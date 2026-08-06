# MiniRoute 后续实验方案

## 当前阶段目标

先判断 `lora_route_v2` 训练集准确率低的主要原因：

1. V2 prompt 变长后，训练样本被 `max_seq_len=340` 截断。
2. LoRA 训练参数不足，例如 epoch、学习率或 batch 设置不合适。
3. 训练和评测模板存在不一致。
4. V2 数据边界仍不够清晰，需要 V3 数据。

当前优先级：训练长度已经通过 `max_seq_len=1024` 对照验证，不是主因。模板固定实验也已经完成，最新结果仍存在大规模类别混淆，因此模板不一致也不是当前主因。下一步进入 V3 数据边界设计，并准备输出空间简化对照。

## 实验 1: max_seq_len 对照训练

目的：验证 V2 样本是否因为默认 `max_seq_len=340` 被截断，导致训练集无法拟合。

已执行命令：

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

结果：

```text
完全匹配: 40.34% -> 40.34%
错误行集合: 完全一致，633/633
```

结论：

```text
max_seq_len 不是当前主因。
```

## 实验 2: 训练/评测模板一致性检查

目的：确认空 `<think></think>` 或 chat template 差异是否影响路由输出。

检查点：

- 训练时 `SFTDataset` 会调用 `post_processing_chat()`，可能以概率移除空 think。
- 评测时 `eval_route.py` 使用 `apply_chat_template(..., add_generation_prompt=True, open_thinking=False)`。
- 如果训练和评测 prompt 分布不一致，路由准确率会被低估。

建议：

- 在 MiniMind 侧增加一个评测开关，例如 `--strip_empty_think`。
- 对同一个 LoRA 同时跑保留空 think和移除空 think 两组。
- 先跑训练集，再跑验证集。

已确认现象：

```text
训练侧：约 20% 概率插入 system prompt，约 80% 概率移除空 think。
评测侧：固定无额外 system，固定带空 think。
```

已执行一次 strip-empty-think 尝试，结果显示该方向不适合作为主线：

```text
lora_route_v3
严格 JSON: 0.00%
可提取 JSON: 100.00%
完全匹配: 42.04%
```

原因是评测侧去掉 empty think 后，模型会主动生成 `<think>\n\n</think>\n\n`，导致严格 JSON 归零。

后续已完成模板固定实验：

1. 训练侧禁用随机 system 注入。
2. 训练侧和评测侧统一 empty think 处理。
3. 训练和评测使用一致的 chat template。

最新结果仍出现大量 `tool_execution + shell_tools + high_risk` 过度预测、记忆类边界混淆和 schema 外输出。因此，模板问题已排除为当前主因。

## 实验 3: V3 数据设计

V3 不应平均扩充所有类别，而应围绕 V2/V2_2 的稳定错误行做边界数据。

当前状态：已执行，并完成 train、valid、test 评测。

已生成数据：

```text
route_v3_train.jsonl: 1664
route_v3_valid.jsonl: 355
route_v3_test.jsonl: 361
total: 2380
```

已完成 train 结果：

```text
模型: full_sft + lora_route_v3_2
完全匹配: 1304/1664 = 78.37%
相比 baseline 40.34% 提升 38.03 个百分点
```

已完成 valid 结果：

```text
模型: full_sft + lora_route_v3_2
完全匹配: 290/355 = 81.69%
相比 baseline 40.34% 提升 41.35 个百分点
```

已完成 test 结果：

```text
模型: full_sft + lora_route_v3_2
完全匹配: 284/361 = 78.67%
相比 baseline 40.34% 提升 38.33 个百分点
错误样本: 77/361 = 21.33%
Schema 合法: 356/361 = 98.61%
```

当前结论：

```text
V3 边界数据方向成立，train/valid/test 均稳定在 78%-82% 区间。
```

重点方向：

1. `status_query` vs `tool_execution`
   - “查看上一轮工具调用链”是状态查询，不是 shell 执行。
   - “查询最近 trace”应输出 `status_query + observe_tools + read_only`。
2. `file_read` vs `tool_execution`
   - “看一下 README”是文件读取，不是命令执行。
   - “列一下目录主要文件”当前容易被打成 `shell_tools/high_risk`，需要明确只读边界。
3. `content_save` vs `tool_execution`
   - “保存链接/视频/资料”是内容保存，不是 shell 执行。
4. `chat` vs `memory_query`
   - “保存机制是什么意思”是概念解释，不是保存或记忆查询。
   - “说明 rm 命令会做什么，不要执行”是普通解释，不是工具执行。
5. `profile_update` vs `memory_query` vs `content_save`
   - “以后默认先给结论”是画像更新。
   - “上次我说过什么偏好”是记忆查询。
   - “保存这个链接”是内容保存。
6. `unknown_tools` vs `shell_tools`
   - OCR、图片识别、数据库查询、音频转写等可以先标 `unknown_tools`，不要默认映射到 shell。

## 实验 4: 更小输出空间对照

如果 V3 数据后仍难以拟合，可以考虑降低第一版小模型任务难度。

方案：

- 小模型只预测：
  - `intent`
  - `need_memory`
  - `need_tools`
  - `risk_level`
- `tool_scope` 由规则从 `intent + risk_level` 映射出来。

理由：

- 当前 `intent` 和 `tool_scope` 高度绑定，但模型需要同时生成两者，增加了组合错误。
- 对 64M 小模型来说，先拆成“分类 + 规则映射”可能更稳。

## 实验 5: 错误混淆统计

目的：每轮训练后快速定位主要错法。

建议统计：

- 字段准确率。
- Top intent confusion。
- Top tool_scope confusion。
- Top risk_level confusion。
- schema 外输出数量。
- high_risk 过度预测和漏召数量。

本轮 V2 的重点混淆已经记录在 [route_eval_v2.md](route_eval_v2.md)。

## 推荐执行顺序

1. 冻结 `lora_route_v3_2` 作为阶段性 baseline。
2. V3.1 小修数据已生成：train `1713`、valid `361`、test `380`，delta `74`。
3. 云端训练 `lora_route_v3_1`。
4. 评测 `route_v3_1_train/valid/test.jsonl`。
5. 额外评测冻结 `route_v3_test.jsonl` 作为 bridge eval。
6. 接受 V3.1 的门槛：train `>82%`、valid `>83%`、test `>82%`、test schema bad `<=1`、bridge `route_v3_test` 不低于 `78.67%`。
7. 暂时不移除 `tool_scope`，除非 V3.1 后仍无法继续提升或线上 shadow 暴露该字段不稳定。
