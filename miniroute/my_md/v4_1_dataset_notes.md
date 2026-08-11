# MiniRoute V4.1 数据修订记录

## 背景

V4 首轮 train 评测结果：

```text
total: 2400
strict_json: 2400/2400 = 100.00%
schema_valid: 2400/2400 = 100.00%
exact_match: 1831/2400 = 76.29%
scene: 2293/2400 = 95.54%
operation: 2311/2400 = 96.29%
request_mode: 1917/2400 = 79.88%
```

错误文件：`miniroute/data/route_v4_train_errors.jsonl`。

错误分析：

```text
错误样本: 569
request_mode-only 错误: 462，占错误 81.20%
scene 或 operation 错误: 107，占总样本 4.46%
忽略 request_mode 后 scene/operation exact: 2293/2400 = 95.54%
```

根因：

```python
request_mode="compound" if index % 5 == 0 else "single"
```

V4 的 `compound` 是按序号机械生成，不是语义标注。

## V4.1 修改

- 新增 `route_v4_1_train/valid/test.jsonl`，不覆盖 V4。
- `request_mode=compound` 只用于同一 `scene`、同一 `operation` 下多个同类目标。
- 不生成跨场景 compound，例如“查历史偏好，然后改简历”。
- train、valid、test 使用不同 template family，并在 `source` 中记录 split 和 family。
- 保留 V4 错误中暴露的重点边界样本：
  - `看一下运行记录，不要查询我的长期记忆。` -> `status/query/single`
  - `保存这个网页，不是执行下载命令。` -> `content/save/single`
  - `下载并保存这个网页正文。` -> `action/execute/single`
  - `我之前说过哪些项目数据？` -> `memory/query/single`
  - `按刚才那个来。` -> `unknown/unknown/single`

## 数据规模

```text
route_v4_1_train.jsonl: 2400
route_v4_1_valid.jsonl: 300
route_v4_1_test.jsonl: 300
total: 3000
compound_count: 600
shuffle_seed: 20260806
```

## 校验结果

Schema 校验：

```text
ok: true
total_records: 3000
compound_count: 600
issues: []
```

V4.1 语义校验：

```text
issues: []
```

## 训练结果

训练集评测：

```text
total: 2400
strict_json: 2400/2400 = 100.00%
schema_valid: 2400/2400 = 100.00%
exact_match: 2396/2400 = 99.83%
scene: 2396/2400 = 99.83%
operation: 2397/2400 = 99.88%
request_mode: 2400/2400 = 100.00%
dangerous status_to_action: 1
```

验证集评测：

```text
total: 300
exact_match: 150/300 = 50.00%
scene: 199/300 = 66.33%
operation: 199/300 = 66.33%
request_mode: 240/300 = 80.00%
dangerous file_to_action: 15
dangerous unknown_to_action: 5
```

测试集评测：

```text
total: 300
exact_match: 154/300 = 51.33%
scene: 201/300 = 67.00%
operation: 201/300 = 67.00%
request_mode: 240/300 = 80.00%
dangerous file_to_action: 15
dangerous unknown_to_action: 7
```

错误文件位置：

```text
/root/autodl-tmp/minimind/result/route_v4_1_train_errors.jsonl
/root/autodl-tmp/minimind/result/route_v4_1_valid_errors.jsonl
/root/autodl-tmp/minimind/result/route_v4_1_test_errors.jsonl
```

## 结论

V4.1 修复了 request_mode 的机械标注问题，训练集 request_mode 达到 `100.00%`，train exact 达到 `99.83%`。

但 valid/test 大幅掉分，说明 split-specific template 设计导致明显分布偏移。当前更像模板/话术迁移问题，不是单纯模型能力问题。

## 下一步

下一步不要继续在这一版上堆训练轮数，而应制作 V4.2：

- 保留语义 compound 标注。
- 缩小 train/valid/test 的话术差异。
- 让 split 共享同一组模板族，只在具体句子上做 held-out。
- 继续保留 `file/status/unknown` 的边界样本。
- 再次检查 `content -> action` 和 `unknown -> action`。

V4.1 训练命令保留为复现实验：

```bash
cd /home/jjh/git_work/minimind/trainer

python train_lora.py \
  --data_path ../dataset/route_v4_1_train.jsonl \
  --from_weight full_sft \
  --lora_name lora_route_v4_1 \
  --epochs 3 \
  --batch_size 16 \
  --max_seq_len 1024 \
  --route_mode
```

优先看 train 和 valid：

```text
request_mode accuracy > 90%
request_mode-only errors < 8% of train
content_to_action < 21 train cases
```
