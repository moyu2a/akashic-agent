# 08. 睡眠巩固与记忆库卫生评测

## 目标

本轮评测回答一个问题：在不改动真实记忆库的前提下，睡眠巩固模块能否识别重复记忆、过期记忆、低价值记忆，同时保护应该保留的关键记忆。

## 当前项目真实状态

- 现有睡眠巩固仍是 shadow / dry-run。
- 它会在 `ConsolidationCommitted` 后扫描 active memory，并记录 `sleep_consolidation_shadow`。
- 它不会真实合并、删除、降权、supersede 或影响召回。
- 所以本阶段评测是 evidence 评测，不是生产清理效果评测。

## 测试集设计

| cohort | 数量 | evidence row 数 | 目的 |
| --- | ---: | ---: | --- |
| duplicate | 150 组 | 150 | 测试重复记忆能否被识别为可合并候选 |
| stale | 150 | 150 | 测试过期低强化记忆能否被识别为过期候选 |
| low_value | 150 | 150 | 测试临时、测试、本次类低价值事件能否被识别为低价值候选 |
| retained | 150 | 150 | 测试高强化、高权重关键偏好不会被误伤 |

默认 600 个 case 会扫描 750 条 active item：重复 case 每组有 2 条 item，但 evidence 只统计其中 1 条冗余项。

## 三张主表中的位置

睡眠巩固主要进入第三张表：记忆库卫生表。它不适合只用回答命中率评价，因为它的价值主要体现在记忆库变干净、可追溯、少占上下文，同时关键记忆不丢。

## 指标解释

| 指标 | 含义 |
| --- | --- |
| 重复候选识别率 | 重复 evidence row 中有多少被标记为 `merged` |
| 过期候选识别率 | 过期 evidence row 中有多少被标记为 `stale` |
| 低价值候选识别率 | 低价值 evidence row 中有多少被标记为 `low_value_removed` |
| 来源覆盖率 | 所有 evidence row 中有多少带有 `source_ref` |
| proxy 回源成功率 | 有 `source_ref` 的 evidence row 中有多少被视为可回源；当前不是实际 message lookup |
| shadow 估算 token 节省率 | 按候选 after token 估算的节省比例，不代表真实 DB 或上下文已减少 |
| 关键记忆保持率 | retained evidence row 中仍保持 `active` 的比例 |
| 关键记忆误伤候选数 | retained row 被 shadow 标记为合并、过期或低价值候选的数量 |
| 非预期候选数 | shadow-derived after_state 和 evidence label 期望不一致的数量 |
| 误伤候选率 | 关键记忆误伤候选数 / retained row 数 |

## 当前结果

正式报告路径：

- `my_md/memory_optimization/eval_reports/sleep_hygiene_evidence/memory_sleep_hygiene_evidence_eval.json`
- `my_md/memory_optimization/eval_reports/sleep_hygiene_evidence/memory_sleep_hygiene_evidence_eval.md`
- `my_md/memory_optimization/eval_reports/sleep_hygiene_evidence/memory_target_metric_sleep_hygiene.json`
- `my_md/memory_optimization/eval_reports/sleep_hygiene_evidence/memory_target_metric_sleep_hygiene.md`

| 指标 | 数值 |
| --- | ---: |
| case 数 | 600 |
| 扫描 active item 数 | 750 |
| evidence row 数 | 600 |
| 重复候选识别率 | 100.0% |
| 过期候选识别率 | 100.0% |
| 低价值候选识别率 | 100.0% |
| 来源覆盖率 | 90.0% |
| proxy 回源成功率 | 100.0% |
| shadow 估算 token 节省率 | 64.0138% |
| 关键记忆保持率 | 100.0% |
| 关键记忆误伤候选数 | 0 |
| 非预期候选数 | 0 |
| 误伤候选率 | 0.0% |
| 实际应用变更数 | 0 |

## 结论

- 当前 sleep consolidation shadow 可以稳定识别目标导向测试集里的重复、过期和低价值候选。
- 通过 per-case scope 隔离后，retained 关键记忆没有被误判为清理候选。
- `source_ref` 覆盖率为 `90.0%`，proxy 回源成功率为 `100.0%`；这里的回源成功仍只是 evidence proxy，不是实际查询历史消息。
- `shadow_estimated_token_saving_rate = 64.0138%` 说明候选层有压缩空间，但当前没有真实落库清理，所以不能说真实数据库体积或真实 prompt token 已下降。

## V2 hard / adversarial 评测

V1 的 600-case standard 集主要验证功能链路，所以出现 100% 是合理的。V2 新增 hard 集，目标是验证边界，而不是追求满分。

V2 和 V1 的关键差异是：V2 为每个参与评测的 memory item 都标注 `expected_after_state`，而不是只评估少数 expected id。这样如果 shadow 误伤了同一个 case 里的另一条 item，precision 和 false positive 指标也能捕捉到。

hard 集覆盖：

| scenario | 目的 |
| --- | --- |
| near_merge_not_duplicate | 相似内容进入 merge 边界，但不能被当作 duplicate |
| old_high_value | 旧但高价值，不应清理 |
| temporary_but_pinned | 临时词存在，但用户明确强化保存 |
| cross_scope_identical | 不同 scope 的相同内容不应合并 |
| opposite_preference_conflict | 正反偏好不应当重复合并 |
| multi_duplicate_pairwise | 多条重复在当前 pairwise 语义下识别冗余成员 |
| missing_source_but_important | 缺 source_ref 但高价值不应清理 |
| mixed_signal_low_value | 低价值必须满足当前 stale-derived 规则 |

V2 报告分为 standard、hard、overall 三组。standard 看基础链路，hard 看边界能力，overall 看综合表现。

正式报告路径：

- `my_md/memory_optimization/eval_reports/sleep_hygiene_evidence_v2/memory_sleep_hygiene_evidence_eval.json`
- `my_md/memory_optimization/eval_reports/sleep_hygiene_evidence_v2/memory_sleep_hygiene_evidence_eval.md`
- `my_md/memory_optimization/eval_reports/sleep_hygiene_evidence_v2/memory_target_metric_sleep_hygiene.json`
- `my_md/memory_optimization/eval_reports/sleep_hygiene_evidence_v2/memory_target_metric_sleep_hygiene.md`

## V2 当前结果

| case_set | case 数 | evaluated item 数 | candidate recall | candidate precision | retained protection | false positive cleanup | safe evidence token saving |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| standard | 600 | 600 | 100.0% | 100.0% | 100.0% | 0.0% | 64.0138% |
| hard | 320 | 520 | 100.0% | 75.0% | 90.0% | 10.0% | unsafe |
| overall | 920 | 1120 | 100.0% | 93.4426% | 92.7273% | 7.2727% | unsafe |

补充汇总：

| 指标 | 数值 |
| --- | ---: |
| case 数 | 920 |
| 扫描 active item 数 | 1270 |
| evidence row 数 | 1120 |
| 重复候选识别率 | 100.0% |
| 过期候选识别率 | 100.0% |
| 低价值候选识别率 | 100.0% |
| 来源覆盖率 | 89.2857% |
| proxy 回源成功率 | 100.0% |
| shadow 估算 token 节省率 | 46.8599% |
| 关键记忆保持率 | 92.7273% |
| 关键记忆误伤候选数 | 40 |
| 非预期候选数 | 40 |
| 误伤候选率 | 7.2727% |
| 实际应用变更数 | 0 |

V2 的主要结论是：当前 shadow 对应该清理的候选召回很强，standard 集里是 100%；但 hard 集暴露出 `near_merge_not_duplicate` 这类边界场景会被 merge 语义标成候选，导致 hard 的 candidate precision 只有 75.0%，retained protection 为 90.0%。因此不能再说“睡眠巩固完全安全”，更准确的表述是“基础候选识别稳定，但边界保留策略还需要继续治理”。

## V2 结果解读

这轮数据应分三层理解：

| 层次 | 当前数据 | 说明 |
| --- | --- | --- |
| 候选召回能力 | hard candidate recall `100.0%` | 应该被清理或合并的目标候选都能被 shadow 找到，说明重复、过期、低价值规则的覆盖是有效的。 |
| 候选精度 | hard candidate precision `75.0%` | shadow 也把一部分应该保留的相似记忆放进了非 active 候选，说明仅看 recall 会高估安全性。 |
| 关键记忆保护 | hard retained protection `90.0%` | 大部分关键记忆被保留，但 hard 集中仍有 10% retained row 被误伤，不能直接进入真实清理。 |

误伤主要来自 `near_merge_not_duplicate`：这类样本是“相似但不应清理”的边界场景。当前算法把它识别成 merge candidate，从 evidence 口径看 after_state 变成 `merged`，因此被统计为 retained false positive。这个结果不是测试失败，而是评测集发挥作用：它把 V1 standard 集看不到的边界风险暴露出来了。

## 后续完善方案

### 1. 区分 merge 建议和 cleanup 动作

当前 evidence 把 `merged`、`stale`、`low_value_removed` 都视为非 active 状态，因此 near-merge 建议会影响 retained protection。下一步应把候选分成两类：

| 类型 | 示例 | 是否可直接清理 |
| --- | --- | --- |
| cleanup candidate | stale、low_value_removed、明确重复的冗余项 | 可以进入严格 dry-run patch |
| review / merge suggestion | near-merge、弱相似、信息互补 | 只能进入人工或策略复核，不能直接删除 |

这样可以保留 merge 的提示价值，同时避免把相似但互补的记忆当作可删除收益。

### 2. 给 hard 集增加按场景指标

目前 V2 已经有 standard / hard / overall 三组指标，但 hard 内部还没有按 scenario 单独出表。下一步应输出：

```text
near_merge_not_duplicate precision / false positive
old_high_value retained protection
temporary_but_pinned retained protection
cross_scope_identical scope safety
opposite_preference_conflict conflict protection
multi_duplicate_pairwise duplicate recall
missing_source_but_important missing-source protection
mixed_signal_low_value cleanup recall
```

这样能直接定位是哪一类边界拉低了 hard precision，而不是只看到 hard 总分。

### 3. 增加真实回源 evidence

当前 `source_fetch_success_rate = 100.0%` 是 proxy 口径，只表示带 `source_ref` 的记录被视为可回源。下一步需要真的调用消息查询能力，验证：

- `source_ref` 能否解析。
- 原始消息是否还存在。
- 原始消息是否支持当前记忆摘要。
- 跨 session / 跨 channel 是否被正确隔离。

只有真实回源通过，才能把“来源覆盖率”升级成“证据可信度”指标。

### 4. 做 active dry-run patch，但不落库

在不修改真实 DB 的前提下，生成拟执行变更：

```text
would_merge: [...]
would_mark_stale: [...]
would_remove_low_value: [...]
would_keep: [...]
requires_review: [...]
```

报告中要展示每条拟变更的原因、source_ref、是否可恢复、预计 token 变化和风险等级。这样可以从“候选识别评测”推进到“治理动作评测”，但仍保持安全边界。

### 5. 等 hard precision 稳定后再讨论真实启用

建议进入真实启用前至少满足：

| 指标 | 建议门槛 |
| --- | ---: |
| cleanup candidate recall | >= 98% |
| cleanup candidate precision | >= 98% |
| retained protection | >= 99% |
| false positive cleanup | <= 1% |
| 真实 source_ref 回源成功率 | >= 95% |
| active dry-run 可恢复率 | 100% |

在达到这些门槛前，睡眠巩固适合作为 shadow evidence、Dashboard 观测和离线评测模块，不适合直接执行真实删除或合并。

## 当前限制

- 当前数据集是目标导向的确定性集合，不是真实线上自然分布。
- 当前回源成功是 proxy，尚未执行真实 message lookup。
- 当前模块没有 active 化，所以没有真实删除、真实合并后的生产收益。
- 当前不能证明长期运行后的数据库体积下降，只能证明 shadow 判断、候选识别和 evidence 口径可用。

## 下一步

1. 针对 hard 集误伤，细分 merge 候选和 cleanup 候选，避免“可合并建议”被直接等同于“可清理”。
2. 引入真实 `source_ref` 回源检查，区分可解析和真的能取回原消息。
3. 在安全开关下做 active dry-run patch，不落库，只输出拟执行变更计划。
4. 等 hard precision 和 retained protection 稳定后，再讨论是否允许真实 merge / supersede。
