# MiniRoute 实验记录模板

## 基本信息

- 实验名称:
- 实验日期:
- 记录人:
- 实验状态: 未开始 / 训练中 / 已评测 / 已归档
- 关联数据版本:
- 关联 LoRA 权重:

## 实验目标

本轮要验证的问题:

```text
例如：验证固定训练模板后，训练集 exact_match 是否明显高于 40.34%。
```

判断标准:

```text
例如：如果 train exact_match 明显提升，继续模板固定路线；如果仍接近 40%，进入 V3 边界数据设计。
```

## 修改内容

本轮修改了什么:

- 代码修改:
- 数据修改:
- prompt 修改:
- 训练参数修改:
- 评测脚本修改:

关键差异:

```text
例如：禁用随机 system 注入；训练和评测都保留 empty think。
```

## 测试数据

| 数据集 | 文件路径 | 样本数 | 说明 |
| --- | --- | ---: | --- |
| train |  |  |  |
| valid |  |  |  |
| test |  |  |  |

数据生成方式:

```text
记录生成脚本、随机种子、是否从旧版本迁移、是否加入 hard negative。
```

数据校验结果:

```text
记录 validate_dataset.py 输出，尤其是 total_records、high_risk_test_count、issues。
```

## 训练方案

基座与权重:

- base weight:
- LoRA name:
- model size:

训练参数:

| 参数 | 值 |
| --- | --- |
| epochs |  |
| batch_size |  |
| learning_rate |  |
| max_seq_len |  |
| route_mode |  |
| empty think 处理 |  |
| system prompt 注入 |  |

训练命令:

```bash

```

训练日志摘要:

```text
记录每轮 loss、是否正常收敛、是否中断、是否出现显存问题。
```

## 评测方案

评测命令:

```bash

```

评测设置:

- 是否保留 empty think:
- 是否 strip empty think:
- 是否开启 schema 校验:
- `max_new_tokens`:
- `do_sample`:

错误样本输出路径:

```text

```

## 测试结果

总体指标:

| 指标 | train | valid | test |
| --- | ---: | ---: | ---: |
| strict_json |  |  |  |
| extractable_json |  |  |  |
| exact_match |  |  |  |

字段准确率:

| 字段 | train | valid | test |
| --- | ---: | ---: | ---: |
| intent |  |  |  |
| need_memory |  |  |  |
| need_tools |  |  |  |
| tool_scope |  |  |  |
| risk_level |  |  |  |

schema 外输出:

```text
例如：
intent=trace: 16
tool_scope=None: 16
risk_level=None: 16
```

## 错误分析

Top intent confusion:

```text

```

Top tool_scope confusion:

```text

```

Top risk_level confusion:

```text

```

Top predicted combos:

```text

```

典型错误样本:

```text
记录 3-5 条最有代表性的错误，包括输入、标准答案、模型输出和判断。
```

## 本轮结论

结论:

```text
说明本轮假设是否成立，不要只写“效果不好”。
```

主要原因判断:

- 训练模板问题:
- 训练参数问题:
- 数据边界问题:
- 输出空间过大:
- 模型能力不足:

## 下一步

下一轮动作:

```text
例如：进入 V3 数据边界设计，重点补 status_query/file_read/content_save 被误判为 shell_tools 的反例。
```

是否更新其他文档:

- [ ] 更新 `route_issue_log.md`
- [ ] 更新 `route_experiment_plan.md`
- [ ] 更新 `minimind_training_handoff.md`
- [ ] 更新 `my_md/README.md` 当前结论快照
