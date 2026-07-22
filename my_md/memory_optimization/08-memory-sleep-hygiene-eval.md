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

## 当前限制

- 当前数据集是目标导向的确定性集合，不是真实线上自然分布。
- 当前回源成功是 proxy，尚未执行真实 message lookup。
- 当前模块没有 active 化，所以没有真实删除、真实合并后的生产收益。
- 当前不能证明长期运行后的数据库体积下降，只能证明 shadow 判断、候选识别和 evidence 口径可用。

## 下一步

1. 引入真实 `source_ref` 回源检查，区分可解析和真的能取回原消息。
2. 增加更难的误伤测试：相似但不应合并、旧但高强化、临时但被用户明确要求长期保存。
3. 在安全开关下做 active dry-run patch，不落库，只输出拟执行变更计划。
4. 等 dry-run 精度稳定后，再讨论是否允许真实 merge / supersede。
