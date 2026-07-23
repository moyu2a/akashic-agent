# 08. 睡眠巩固与记忆库卫生评测

## 目标

本轮评测回答一个问题：在不改动真实记忆库的前提下，睡眠巩固模块能否识别重复记忆、过期记忆、低价值记忆，同时保护应该保留的关键记忆。

## Source-backed V1 真实来源证据评测

这一轮不是继续提高候选召回率，而是验证 sleep hygiene 候选背后的 `source_ref` 是否真实、可查、支持摘要，并能否作为未来恢复依据。

结论：source-backed 评测把 V3 从“proxy 可回源”推进到“真实 `SessionStore` 证据可审计”。如果某条候选无法回源或原文不支持摘要，它不能进入真实 active cleanup，只能进入 review 或 blocked。

正式报告路径：

- `my_md/memory_optimization/eval_reports/sleep_hygiene_source_backed_v1/memory_sleep_hygiene_evidence_eval.json`
- `my_md/memory_optimization/eval_reports/sleep_hygiene_source_backed_v1/memory_sleep_hygiene_evidence_eval.md`
- `my_md/memory_optimization/eval_reports/sleep_hygiene_source_backed_v1/memory_sleep_hygiene_dry_run_patch.json`
- `my_md/memory_optimization/eval_reports/sleep_hygiene_source_backed_v1/memory_target_metric_sleep_hygiene.json`
- `my_md/memory_optimization/eval_reports/sleep_hygiene_source_backed_v1/fixture_sessions.db`

本轮规模：

| 指标 | 数值 |
| --- | ---: |
| case 数 | 160 |
| 扫描 active item 数 | 224 |
| evidence row 数 | 200 |
| source fetch mode | session-store |
| source_ref parse success | 82.2086% |
| source fetch success | 36.1963% |
| source support rate | 18.4049% |
| missing source count | 75 |
| unsupported source count | 29 |
| session ref not fetchable count | 37 |
| malformed source_ref count | 29 |

### Source-backed V1 测试方案

这轮测试采用目标导向 fixture，不追求自然分布，而是故意把不同来源状态放进同一批样本，验证安全门能否识别风险：

| 来源状态 | 构造方式 | 期望结果 |
| --- | --- | --- |
| supported | `source_ref` 指向真实 `SessionStore` message id，原文包含 expected terms | 可回源，且原文支持摘要 |
| missing | `source_ref` 格式正确，但 fixture DB 里没有对应 message | 解析成功，但回源失败 |
| unsupported | `source_ref` 指向真实 message id，但原文不支持当前摘要 | 回源成功，但不能作为执行依据 |
| session_ref_not_fetchable | 使用 `cli:local@post_response` 这类 session 级来源 | 可解析，但不能按 message id 恢复原文 |
| parse_failed | 构造 malformed `source_ref` | 解析失败 |
| missing_source_ref | 不提供 `source_ref` | 直接标记来源缺失 |

执行链路：

```text
build_sleep_hygiene_source_fixture()
  -> 生成 all-case sleep hygiene 测试集
  -> 写入受控 fixture_sessions.db
  -> 用 SessionStoreSourceRefResolver.fetch_by_ids() 回源
  -> run_sleep_hygiene_evidence_eval()
  -> 输出 source_evidence_metrics / by_action
  -> 生成 dry-run patch，不写真实 DB
```

CLI 命令：

```bash
.venv/bin/python scripts/run_memory_sleep_hygiene_evidence_eval.py \
  --output-dir my_md/memory_optimization/eval_reports/sleep_hygiene_source_backed_v1 \
  --case-set all \
  --duplicate-groups 24 \
  --stale-count 24 \
  --low-value-count 24 \
  --retained-count 24 \
  --hard-per-scenario 8 \
  --source-fixture-mode balanced \
  --source-fixture-db my_md/memory_optimization/eval_reports/sleep_hygiene_source_backed_v1/fixture_sessions.db \
  --write-target-metrics \
  --write-dry-run-patch
```

按动作分组看，安全清理候选一共有 `96` 条，其中 `source_ref` 覆盖率 `79.1667%`、真实回源成功率 `30.2632%`、原文支持率 `15.7895%`。这说明 V3 的 cleanup 规则本身仍然稳定，但如果把“可恢复、可审计”作为真实执行前置条件，很多候选还不能直接 active 化。

按动作分组的来源证据：

| action | rows | source_ref 覆盖率 | 解析成功率 | 回源成功率 | 原文支持率 | 主要问题 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| safe_cleanup_candidates | 96 | 79.1667% | 82.8947% | 30.2632% | 15.7895% | 可清理候选里大量来源缺失、不可取回或原文不支持 |
| review_required | 24 | 87.5% | 85.7143% | 42.8571% | 19.0476% | 复核队列中也存在来源不可审计问题 |
| merge_suggestions | 8 | 87.5% | 85.7143% | 42.8571% | 14.2857% | 相似合并建议不能直接当清理动作 |
| retained_rows | 104 | 83.6538% | 81.6092% | 41.3793% | 20.6897% | 应保留记忆也需要来源质量治理 |

dry-run patch 已新增 source-backed 安全门：

| 指标 | 数值 |
| --- | ---: |
| patch row 数 | 200 |
| source-backed safe row 数 | 12 |
| requires review | 24 |
| source_not_fetchable | 73 |
| source_not_supporting_summary | 11 |
| not_cleanup_candidate | 80 |

这个 gate 的含义是：只有同时满足 `safe_cleanup_candidate = true`、`source_fetch_mode = session-store`、`source_fetch_success = true`、`source_support_status = supported` 的记录，才会标记 `source_backed_action_safe = true`。proxy 模式即使显示支持，也不会被当作真实可执行依据。

Fixture DB 也加了覆盖保护：如果 `--source-fixture-db` 指向一个已经存在但没有 fixture marker、也不像旧版 sleep hygiene fixture 的普通 `sessions.db`，构建器会直接失败，不会删除或覆盖它。这样可以避免误把生产会话库作为评测 fixture 路径传入。

### 为什么这轮比例偏低

这轮低比例是测试设计造成的，不是候选识别能力突然下降。V3 已经验证 cleanup recall、cleanup precision、retained protection 都可以在 synthetic hard 集达到 `100.0%`；Phase 6s 进一步把问题换成“候选能不能被真实来源支撑”。

| 低比例项 | 原因 | 正确解读 |
| --- | --- | --- |
| `source_ref 覆盖率 81.5%` | fixture 故意放入缺来源样本 | 用来验证无来源记忆会被挡住 |
| `解析成功率 82.2086%` | fixture 故意放入 malformed `source_ref` | 用来验证格式错误可统计、可阻断 |
| `真实回源成功率 36.1963%` | 分母里包含缺失 message、session 级 ref 和格式错误 ref | 只有能按 message id 找到原文才算成功 |
| `原文支持率 18.4049%` | fixture 故意放入 unsupported 原文 | 证明“能取回消息”不等于“消息支持摘要” |
| `source-backed safe 12/200` | gate 同时要求安全清理候选、真实回源成功、原文支持摘要 | 大多数候选目前只能 blocked 或 review |

因此本轮的核心结论不是“睡眠巩固性能低”，而是：

```text
候选识别已经能找到可疑记忆，但真实执行前还必须补 source_ref 质量、消息级回源和原文支持校验。
```

### 当前存在的问题

| 问题 | 当前表现 | 影响 |
| --- | --- | --- |
| `source_ref` 质量不足 | 覆盖率 `81.5%`，缺来源合计 `75` 条 | 没有来源或来源缺失的候选不能安全清理 |
| 可按消息回源比例低 | 真实回源成功率 `36.1963%` | 很多来源不能还原到具体历史消息 |
| 原文支持率低 | 原文支持率 `18.4049%` | 不能只凭记忆摘要执行清理，需要原文支撑 |
| 可安全执行候选少 | `source-backed safe = 12/200` | 当前 active cleanup 仍应关闭 |
| session 级来源不可恢复 | `session_ref_not_fetchable = 37` | `cli:local@post_response` 只能定位阶段，不能定位消息 |
| malformed 来源存在 | `malformed_source_ref = 29` | 需要统一 source_ref schema 和写入校验 |
| 当前是受控 fixture | 使用 `fixture_sessions.db` | 能证明机制，不代表生产自然流量 |
| 当前仍是 dry-run | `writes_real_db = false` | 没有真实 DB 体积下降或真实 prompt token 下降 |

后续改进方向：

1. 写入长期记忆时优先记录消息级 `source_ref`，避免只写 session 级来源。
2. 对 `source_ref` 做 schema 校验，拒绝 malformed 来源进入长期记忆。
3. 在记忆摘要写入或巩固时增加“摘要是否被原文支持”的校验。
4. 把 source-backed safe 作为 active cleanup 的硬门槛，未通过的候选只进 review 或 blocked。
5. 用真实样本 DB 重跑 source-backed evidence，区分 fixture 风险覆盖和生产来源质量。

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

## V3 安全候选口径

V3 已把 V2 暴露的问题落到评测口径中：不再把所有非 active shadow 候选都等同为可清理动作，而是拆成 `cleanup candidate` 和 `merge suggestion`。`near_merge_not_duplicate` 仍会保留原始 shadow merge 信号，但默认进入 review，不计入安全 token saving，也不会作为真实清理动作。

正式报告路径：

- `my_md/memory_optimization/eval_reports/sleep_hygiene_evidence_v3/memory_sleep_hygiene_evidence_eval.json`
- `my_md/memory_optimization/eval_reports/sleep_hygiene_evidence_v3/memory_sleep_hygiene_evidence_eval.md`
- `my_md/memory_optimization/eval_reports/sleep_hygiene_evidence_v3/memory_sleep_hygiene_dry_run_patch.json`
- `my_md/memory_optimization/eval_reports/sleep_hygiene_evidence_v3/memory_target_metric_sleep_hygiene.json`
- `my_md/memory_optimization/eval_reports/sleep_hygiene_evidence_v3/memory_target_metric_sleep_hygiene.md`

V3 主表：

| 分组 | case 数 | evaluated item 数 | cleanup recall | cleanup precision | retained protection | false positive cleanup | merge suggestion | review required | safe cleanup token saving |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| standard | 600 | 600 | 100.0% | 100.0% | 100.0% | 0.0% | 0 | 0 | 64.0138% |
| hard | 320 | 520 | 100.0% | 100.0% | 100.0% | 0.0% | 40 | 120 | 23.7952% |
| overall | 920 | 1120 | 100.0% | 100.0% | 100.0% | 0.0% | 40 | 120 | 42.5121% |

### V3 测试内容

本轮 V3 测试不是重新证明“基础候选能不能找到”，而是专门验证 V2 暴露出来的安全边界：

| 测试内容 | 验证目标 | 当前结果 |
| --- | --- | --- |
| standard 基础集 | 重复、过期、低价值候选是否能稳定识别，关键记忆是否保留 | cleanup recall / precision / retained protection 均为 `100.0%` |
| hard 边界集 | near-merge、跨 scope、冲突、缺 source_ref、高价值旧记忆等场景是否会误伤 | cleanup precision 和 retained protection 均为 `100.0%` |
| near-merge 专项 | 相似但不应合并的记忆是否会被当作自动清理对象 | `40` 个 merge signal 全部进入 review，不计入 cleanup |
| source_ref 证据模式 | source_ref 是否能按 proxy / mapping / session-store 三种模式表达证据强度 | 正式合成报告使用 proxy；单元测试覆盖 mapping 和 session-store |
| dry-run patch | 拟执行动作是否能拆成清理、保留和复核，并保证不写真实 DB | patch 中 `writes_real_db = false` |

### V3 主表字段含义

| 字段 | 含义 | 如何解读 |
| --- | --- | --- |
| 分组 / `case_set` | 测试集类型。`standard` 是基础场景，`hard` 是边界场景，`overall` 是两者合并。 | 面试时重点看 `hard`，因为它更能说明安全性。 |
| `case 数` | 测试 case 数量。一个 case 可以包含一条或多条 memory item。 | 说明测试覆盖规模。 |
| `evaluated item 数` | 实际进入 evidence 评估的 memory item 数。 | hard 集可能大于 case 数，因为一个 case 内可能评估多条记忆。 |
| `cleanup recall` | 应该被清理的记忆中，有多少被识别成安全清理候选。 | 越高越好，表示“该清理的能找出来”。 |
| `cleanup precision` | 被系统标成安全清理候选的记忆中，有多少确实应该清理。 | 越高越好，表示“不乱清理”。 |
| `retained protection` | 应该保留的关键记忆中，有多少没有被误伤。 | 安全性核心指标，越高越好。 |
| `false positive cleanup` | 应该保留的记忆被错误当成清理候选的比例。 | 越低越好，理想是 `0.0%`。 |
| `merge suggestion` | 系统发现的相似合并建议数量。 | 不是自动清理，只是进入复核队列。 |
| `review required` | 需要人工或策略进一步复核的候选数量。 | 数量高说明系统选择谨慎处理，而不是直接自动修改。 |
| `safe cleanup token saving` | 只统计安全清理候选后，按 evidence 估算的 token 节省比例。 | 是 dry-run 估算，不代表真实 prompt token 已下降。 |

### V3 数据结论

| 结论点 | 数据依据 | 说明 |
| --- | --- | --- |
| 基础候选识别稳定 | standard cleanup recall / precision 均为 `100.0%` | 重复、过期、低价值这类基础场景仍能被识别。 |
| hard 集安全口径改善 | hard false positive cleanup 从 V2 的 `10.0%` 变成 V3 的 `0.0%` | V3 不再把 near-merge 当作自动清理。 |
| 关键记忆保护恢复 | hard retained protection 从 V2 的 `90.0%` 变成 V3 的 `100.0%` | 相似但应保留的记忆不会被计入 cleanup。 |
| 相似信号没有被隐藏 | hard merge suggestion 为 `40` | 原始 merge signal 仍然可观测，只是进入 review。 |
| 仍不能宣称生产清理有效 | `writes_real_db = false`，正式报告为 proxy source mode | 当前是评测和治理口径改进，不是真实 DB 清理。 |

near-merge 专项：

| scenario | case 数 | evaluated item 数 | cleanup recall | cleanup precision | retained protection | merge suggestion | review required | safe cleanup token saving |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| near_merge_not_duplicate | 40 | 80 | unavailable | unavailable | 100.0% | 40 | 40 | 0.0% |

这组数据说明：V3 没有“消灭”原始 merge 信号，而是把它从可清理动作中剥离出来。这样面试表达时可以说：V2 发现 near-merge 会误伤 retained protection；V3 通过动作分层，把相似但不确定的合并信号转成复核建议，使安全清理口径下 hard retained protection 回到 `100.0%`，false positive cleanup 降到 `0.0%`。

## V3 回源和 dry-run 边界

V3 新增了三种 `source_ref` 证据模式：

| 模式 | 用途 | 结论边界 |
| --- | --- | --- |
| proxy | 合成测试集和历史可复现报告 | 只说明记录带有可解析来源，不代表真实消息存在。 |
| mapping | 单元测试和确定性 fixture | 可以验证 source_ref 到正文的支持关系，但不是生产库查询。 |
| session-store | fixture 或真实 `sessions.db` | 通过 `SessionStore.fetch_by_ids()` 查询真实消息 ID；session 级 ref 只算可解析，不能按消息 ID 回源。 |

本轮正式 V3 报告继续使用 `source_fetch_mode = proxy`，原因是合成测试集的 `source_ref` 是目标导向构造，不保证存在于真实 `sessions.db`。因此不能把 V3 的 `source_fetch_success` 表述为真实历史消息回源成功。

V3 还生成了 `memory_sleep_hygiene_dry_run_patch.json`，其中动作被拆成：

- `would_merge`
- `would_mark_stale`
- `would_remove_low_value`
- `would_keep`
- `requires_review`

所有 patch 记录都带有 `writes_real_db = false`，并输出 `recoverability_status` 和 `recoverability_reason`。这意味着当前只是动作计划和安全审计材料，不会真实合并、删除、标记过期或修改 memory DB。

## V3 当前结论

- standard 集继续证明基础重复、过期、低价值候选识别稳定。
- hard 集证明 V2 的主要误伤可以通过动作分层治理：near-merge 不再算安全清理，只进入 review。
- `review_required_count = 120` 说明 hard 集里仍有相当一部分候选需要策略或人工复核；这不是缺陷，而是避免过度自动清理的安全边界。
- V3 仍然不能证明真实生产记忆库已经变干净，也不能证明真实 prompt token 已下降，因为没有 active cleanup。
- 下一步如果要进入更真实的结论，需要用 session-store 模式跑 fixture 或真实 `sessions.db`，再评估真实回源成功率、恢复性和清理后召回质量。

## Source-backed V1 当前结论

- `session-store` fixture 已证明评测链路可以通过真实 `SessionStore.fetch_by_ids()` 查消息，而不是只依赖 proxy。
- 源证据可信度已被拆成覆盖率、解析成功率、真实回源成功率、原文支持率和失败原因分布。
- dry-run patch 已经具备 source-backed 安全门，但仍然只写报告，不会修改真实 memory DB。
- 当前 source support 是基于确定性 expected terms 的轻量支持判断，不是完整语义蕴含判断。
- 当前 `fixture_sessions.db` 是受控测试库，不是生产自然流量，所以只能证明机制可审计，不能证明真实线上来源质量。

## Phase 6t Source Ref 写入质量 Shadow

Source-backed V1 暴露的主要问题不是 sleep hygiene 候选识别能力，而是长期记忆里的 `source_ref` 质量不足：很多来源只能定位到 `session@post_response`，或者格式错误、缺失、无法按消息 ID 找回原文。Phase 6t 因此专门评估一件事：如果写入阶段能拿到明确的消息级 `message_id`，把 session 级、缺失或 malformed 的 `source_ref` 在 shadow 报告中规范成消息级引用，会带来多少来源质量提升。

本阶段仍然不改真实记忆写入，不重写 `memory_items.source_ref`，不启用 active cleanup，也不打开生产 `sessions.db`。评估器只消费注入的 `SourceRefResolver`；CLI 只创建带本阶段 fixture marker 的受控 `fixture_sessions.db`，并拒绝覆盖未标记的普通会话库。

正式报告路径：

- `my_md/memory_optimization/eval_reports/source_ref_quality_shadow_v1/memory_source_ref_quality_eval.json`
- `my_md/memory_optimization/eval_reports/source_ref_quality_shadow_v1/memory_source_ref_quality_eval.md`
- `my_md/memory_optimization/eval_reports/source_ref_quality_shadow_v1/fixture_sessions.db`

测试方案：

| 样本类型 | baseline source_ref | candidate message ids | 期望 |
| --- | --- | --- | --- |
| 已是消息级且原文支持 | `cli:local:0` | `cli:local:0` | 保留，eligible |
| session 级可升级 | `cli:local@post_response` | `cli:local:1` | shadow 升级为消息级，eligible |
| 缺失可升级 | 空字符串 | `cli:local:2` | shadow 升级为消息级，eligible |
| malformed 可升级 | 非法 JSON | `cli:local:3` | shadow 升级为消息级，eligible |
| 消息级但原文不支持 | `cli:local:4` | `cli:local:4` | 可回源但不 eligible |
| session 级且无候选消息 | `cli:local@post_response` | 空 | 不猜测，不 eligible |

额外边界测试：

- candidate message ids 必须唯一、格式可解析，并且属于当前 `session_key`。
- baseline 和 normalized 两侧都做同会话校验，跨会话消息不能算成功回源。
- resolver opener 拒绝未标记 fixture DB。
- 空候选集合的百分比指标返回 `unavailable`。

当前 shadow 结果：

| 指标 | before | after | 变化 |
| --- | ---: | ---: | ---: |
| message-level 覆盖率 | 33.3333% | 83.3333% | +50.0 个百分点 |
| source_ref 解析成功率 | 66.6667% | 100.0% | +33.3333 个百分点 |
| 真实回源成功率 | 33.3333% | 83.3333% | +50.0 个百分点 |
| 原文支持率 | 16.6667% | 66.6667% | +50.0 个百分点 |
| source-backed eligible 率 | 16.6667% | 66.6667% | +50.0 个百分点 |

计数结果：

| 指标 | 数值 |
| --- | ---: |
| candidate_count | 6 |
| source_backed_eligible before | 1 |
| source_backed_eligible after | 4 |
| malformed_source_ref before | 1 |
| malformed_source_ref after | 0 |

结论：

- 只要写入阶段能提供明确的当前会话消息 ID，`source_ref` 质量可以从“阶段级来源”推进到“消息级可回源来源”。
- 这能直接提高后续 source-backed cleanup 的安全门通过率，因为 `source_backed_eligible` 明确定义为“回源成功且原文支持摘要”。
- 当前数据是 synthetic controlled fixture / shadow 结果，不是生产自然流量，也不是线上真实提升。
- 下一步如果要进入真实链路，需要在记忆候选生成或写入治理阶段携带候选来源消息 ID，然后继续以 shadow 方式采集真实样本。

## Phase 6u Source Ref 扩展测试集

Phase 6t 的 6 条 fixture 只能证明链路可用，覆盖面不够。Phase 6u 把 source_ref 写入质量评测扩展成 `200` 条目标导向测试集，分成 common / hard 两组，每组 `100` 条，继续保持 synthetic controlled fixture / shadow-only。

正式报告路径：

- `my_md/memory_optimization/eval_reports/source_ref_quality_expanded_v1/memory_source_ref_quality_eval.json`
- `my_md/memory_optimization/eval_reports/source_ref_quality_expanded_v1/memory_source_ref_quality_eval.md`
- `my_md/memory_optimization/eval_reports/source_ref_quality_expanded_v1/fixture_sessions.db`

测试集设计：

| case_set | scenario | 数量 | 验证目标 |
| --- | --- | ---: | --- |
| common | already_message_supported | 20 | 已是消息级且原文支持时保持不变 |
| common | session_level_upgradable | 20 | session 级来源能升级为消息级来源 |
| common | missing_upgradable | 20 | 缺失来源在有候选消息 ID 时能补成消息级来源 |
| common | malformed_upgradable | 20 | malformed 来源在有候选消息 ID 时能修正 |
| common | unsupported_message_kept | 20 | 能回源但原文不支持摘要时不能 eligible |
| hard | foreign_candidate_filtered | 20 | 只有跨会话 candidate IDs 时不能升级 |
| hard | foreign_baseline_replaced | 20 | 跨会话 baseline 消息来源会被当前会话消息来源替换 |
| hard | invalid_same_session_baseline | 20 | 同会话但非法消息 ID 会被当前合法消息来源替换 |
| hard | missing_message_id | 20 | 消息 ID 格式合法但 DB 缺失时仍不能 eligible |
| hard | multi_message_supported | 20 | 多消息来源可以用 JSON message-id list 表达并回源 |

整体结果：

| 指标 | before | after | 变化 |
| --- | ---: | ---: | ---: |
| message-level 覆盖率 | 40.0% | 90.0% | +50.0 个百分点 |
| source_ref 解析成功率 | 80.0% | 100.0% | +20.0 个百分点 |
| 真实回源成功率 | 20.0% | 80.0% | +60.0 个百分点 |
| 原文支持率 | 10.0% | 70.0% | +60.0 个百分点 |
| source-backed eligible 率 | 10.0% | 70.0% | +60.0 个百分点 |

计数结果：

| 指标 | before | after |
| --- | ---: | ---: |
| candidate_count | 200 | 200 |
| source-backed eligible | 20 | 140 |
| malformed source_ref | 20 | 0 |

common / hard 分组：

| case_set | candidates | before eligible | after eligible | 变化 |
| --- | ---: | ---: | ---: | ---: |
| common | 100 | 20.0% | 80.0% | +60.0 个百分点 |
| hard | 100 | 0.0% | 60.0% | +60.0 个百分点 |

scenario 细分：

| scenario | candidates | before eligible | after eligible | after fetch | after support |
| --- | ---: | ---: | ---: | ---: | ---: |
| already_message_supported | 20 | 100.0% | 100.0% | 100.0% | 100.0% |
| session_level_upgradable | 20 | 0.0% | 100.0% | 100.0% | 100.0% |
| missing_upgradable | 20 | 0.0% | 100.0% | 100.0% | 100.0% |
| malformed_upgradable | 20 | 0.0% | 100.0% | 100.0% | 100.0% |
| unsupported_message_kept | 20 | 0.0% | 0.0% | 100.0% | 0.0% |
| foreign_candidate_filtered | 20 | 0.0% | 0.0% | 0.0% | 0.0% |
| foreign_baseline_replaced | 20 | 0.0% | 100.0% | 100.0% | 100.0% |
| invalid_same_session_baseline | 20 | 0.0% | 100.0% | 100.0% | 100.0% |
| missing_message_id | 20 | 0.0% | 0.0% | 0.0% | 0.0% |
| multi_message_supported | 20 | 0.0% | 100.0% | 100.0% | 100.0% |

结论：

- expanded case pack 比 6 条 smoke fixture 更适合面试展示，因为它覆盖了正常、缺失、格式错误、跨会话、非法 ID、缺失消息、多消息来源和原文不支持等场景。
- message-level normalization 在目标导向测试集中把 source-backed eligible 从 `20/200` 提升到 `140/200`。
- hard 组 after eligible 只有 `60.0%` 是预期结果，因为 foreign-only、missing message 和 unsupported source 不能被安全门放行。
- 这仍不是生产自然流量，也不代表真实线上提升；它证明的是“在覆盖这些来源质量问题的测试集上，消息级来源治理机制有效且可审计”。
