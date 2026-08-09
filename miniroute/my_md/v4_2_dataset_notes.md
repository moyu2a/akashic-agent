# MiniRoute V4.2 数据修订记录

## 背景

V4.1 修复了 V4 的 `request_mode` 机械标注问题，train 评测达到：

```text
exact_match: 2396/2400 = 99.83%
request_mode: 2400/2400 = 100.00%
```

但 V4.1 valid/test 只有约 `50%-51%`：

```text
valid exact_match: 150/300 = 50.00%
test exact_match: 154/300 = 51.33%
valid scene/operation: 66.33% / 66.33%
test scene/operation: 67.00% / 67.00%
```

主要问题不是 `request_mode`，而是 V4.1 的 train、valid、test 使用了不同
template family，导致验证集和测试集话术分布与训练集差异过大。

## 修改方法

V4.2 不覆盖 V4/V4.1 文件，新增：

```text
miniroute/tools/generate_v4_2_dataset.py
tests/test_miniroute_v4_2.py
miniroute/data/route_v4_2_train.jsonl
miniroute/data/route_v4_2_valid.jsonl
miniroute/data/route_v4_2_test.jsonl
```

核心修改：

- 保留 V4 三字段输出：`scene`、`operation`、`request_mode`。
- 保留 V4.1 的语义 `compound` 定义：只表示同一场景、同一操作下多个同类目标。
- 让 train、valid、test 共享同一组 template family，避免 split-specific 模板迁移问题。
- 每个 split 使用不同 held-out 句式，避免完全重复训练句子。
- 增加边界模板族：`file_no_shell`、`unknown_not_action`、`content_save_no_download`、`status_not_memory`、`memory_not_status` 等。
- 修复固定句式批量扩展问题：固定模板第一次保留原文，后续重复时追加不同业务背景，避免 split 内重复。
- 将生成扰动从 Python 内置 `hash()` 改成 `sha256` 稳定哈希，保证同一版本可复现。

## 数据规模

```text
route_v4_2_train.jsonl: 2400
route_v4_2_valid.jsonl: 300
route_v4_2_test.jsonl: 300
total: 3000
compound_count: 600
shuffle_seed: 20260806
```

场景分布：

```text
chat: 450
memory: 360
profile: 300
task: 390
file: 360
status: 300
content: 300
action: 360
unknown: 180
```

## 测试方法

本地单测：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_miniroute_v4_2.py -q -p no:cacheprovider
```

覆盖内容：

- split 大小和文件名。
- template family 是否在 train/valid/test 共享。
- exact input 是否跨 split 泄漏。
- normalized input 是否跨 split 泄漏。
- split 内 normalized input 是否重复。
- 同模板族跨 split 的 4-gram Jaccard 近重复相似度。
- `compound` 是否有明确复合语义标记。
- connector-single 边界是否仍为 single。
- hard-negative 模板族训练样本数是否足够。
- V4 schema 校验是否通过。

生成命令：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m miniroute.tools.generate_v4_2_dataset
```

schema 校验：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m miniroute.tools.validate_dataset --schema v4 --train miniroute/data/route_v4_2_train.jsonl --valid miniroute/data/route_v4_2_valid.jsonl --test miniroute/data/route_v4_2_test.jsonl
```

## 测试结果

本地单测：

```text
7 passed in 1.59s
```

生成期结果：

```text
train: 2400
valid: 300
test: 300
total: 3000
compound_count: 600
max same-family cross-split 4-gram Jaccard similarity: 0.3871
issues: []
```

schema 校验结果：

```text
ok: true
total_records: 3000
compound_count: 600
issues: []
```

## 本轮发现的问题

第一次实现中有两个问题：

- 全局 cross-split Jaccard 两两比较过慢，测试超过 60 秒仍未结束。已改为：exact/normalized overlap 仍全量检查，Jaccard 近重复只在同一 template family 跨 split 内比较。
- 部分固定模板需要生成多条唯一样本，但原 `_expand_family` 遇到重复后只跳过，导致构建卡住。已改为重复时追加不同业务背景。

第二轮校验发现的数据规则问题：

- 少量 `compound` 模板没有包含复合语义标记。
- `profile/task/file/status/content/action/unknown` 的 single template family 数量不足。
- `下载并保存这个网页正文。` 被放到 compound 模板中，但它是 connector-single 边界样本，应标为 `action/execute/single`。

以上问题均已在 V4.2 生成器中修正。

## 结论

V4.2 数据生成、语义校验和 schema 校验已经通过。它解决的是 V4.1 的数据分布设计问题，不代表模型训练结果已经提升。

下一步在 MiniMind 云服务器训练 `lora_route_v4_2`，重点看 valid/test 是否从 V4.1 的 `50%-51%` 回升到目标区间：

```text
valid exact >= 85%
test exact >= 85%
valid/test scene >= 90%
valid/test operation >= 90%
valid/test request_mode >= 90%
file_to_action <= 3 on valid/test
unknown_to_action <= 2 on valid/test
```

如果 V4.2 valid/test 仍低，说明问题可能不是 split 模板分布，而是 MiniMind 对该任务的泛化能力或 schema 设计仍然不合适。
