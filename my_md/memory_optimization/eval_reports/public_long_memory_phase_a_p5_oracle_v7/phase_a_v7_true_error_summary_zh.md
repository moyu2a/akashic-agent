# LongMemEval Phase A v7 真实错误汇总

## 当前计分口径

- 数据源：`public_long_memory_eval.json`
- 人工/LLM Judge 来源：`phase_a_v7_passed_case_human_review_LLM_judge.md`
- 新规则：从本轮开始，英文问题被中文或中英混杂回答不再计入“真实错误”。
- 保留规则：除语言错配以外，事实答案错误、最终立场错误、过度拒答、偏好判断明显不符合 evidence 的 case 仍照常计入真实错误。
- 语言问题仍保留为独立诊断字段，不混入 factual correctness。

## 总体结论

| 口径 | 数量 | 比例 | 说明 |
| --- | ---: | ---: | --- |
| strict deterministic PASS | 28/50 | 56.0% | 原始字符串/归一化 scorer 口径 |
| secondary PASS | 31/50 | 62.0% | 加入 abstention intent 等二级诊断 |
| LLM Judge 调整后明确真实正确 | 48/50 | 96.0% | 不计语言错配；只扣明确事实/推理错误 |
| 明确真实错误 | 2/50 | 4.0% | `852ce960`, `gpt4_1d80365e` |
| 边界 / partial / gold questionable | 3/50 | 6.0% | 不默认计入真实错误，但后续可单独复核 |
| 语言错配但事实正确 | 6/50 | 12.0% | 新规则下不计真实错误，保留为 language contract 诊断 |

## 保守复盘口径：4/49

后续审查采用一个更保守、也更适合对外说明的 adjusted factual/preference 口径：

- 将 `a2f3aa27` 从分母移除：它属于 gold/case 设计问题，证据原文是 `close to 1300`，gold 简化成精确 `1300`，不应惩罚模型。
- 将明确真实错误计错：`852ce960`, `gpt4_1d80365e`。
- 将 partial / preference coverage 不完整计错：`0a34ad58`, `a89d7624`。
- 语言错配但事实正确仍不计错，只保留为独立 language contract 诊断。

| adjusted 口径 | 数量 | 比例 | 说明 |
| --- | ---: | ---: | --- |
| 有效分母 | 49/50 | 98.0% | 剔除 `a2f3aa27` gold-defective case |
| adjusted 错误 | 4/49 | 8.16% | `852ce960`, `gpt4_1d80365e`, `0a34ad58`, `a89d7624` |
| adjusted 通过 | 45/49 | 91.84% | 不计语言错配；不计 gold-defective case |

因此后续建议使用这句话作为 v7 当前成果的保守结论：

> 在剔除 1 条 gold questionable case 后，按“明确错误 + partial preference miss 均计错、语言错配不计错”的保守口径，v7 当前错误率为 `4/49 = 8.16%`，通过率为 `45/49 = 91.84%`。

## 明确真实错误

| case_id | category | 原始 strict | Judge 结论 | 错误原因 | 后续修复方向 |
| --- | --- | --- | --- | --- | --- |
| `852ce960` | `knowledge-update` | PASS | false positive | 模型答案包含 gold `$400,000`，但最终主结论落在 `$350,000`，与 gold 立场相反。strict scorer 只做子串命中，未判断 final stance。 | scorer 增加 final stance 检查；当答案出现多个候选数值、转折词、冲突解释时，不允许单靠 gold 子串 PASS。 |
| `gpt4_1d80365e` | `temporal-reasoning` | FAIL | 合理 FAILED | 证据显示 2023-05-15 开始 Yosemite solo camping trip，2023-05-17 返回；gold 接受 `2 days` 或含首尾的 `3 days`。模型却说无法确定，没有给出可接受答案。虽然也有语言错配，但真实错误是过度保守/漏算。 | temporal reasoning 应在证据给出 start/end anchor 时计算差值；允许说明 inclusive/exclusive 两种口径，而不是直接拒答。 |

## 边界 / Partial / Gold Questionable

这些不默认计入“明确真实错误”，但不应计作干净 PASS。

| case_id | category | Judge 结论 | 为什么是边界 |
| --- | --- | --- | --- |
| `a2f3aa27` | `knowledge-update` | gold questionable / 从 adjusted 分母移除 | evidence 是 `close to 1300`，gold 简化为 `1300`。模型谨慎说 around/close to 1300，更忠实于证据；这是 gold/case 边界，不计模型错误。 |
| `0a34ad58` | `single-session-preference` | partial positive / adjusted 计错 | Tokyo tips 使用了 Suica、路线、地铁等用户上下文，但没有明确覆盖 TripIt。按保守 preference coverage 口径，计为 partial miss。 |
| `a89d7624` | `single-session-preference` | partial positive / adjusted 计错 | Denver 建议抓住 live music 核心偏好，推荐音乐场景地点；没有点名 Brandon Flowers。按保守 preference coverage 口径，计为 partial miss。 |

## 不再计入真实错误的语言类 case

这些 case 的事实内容被 Judge 认为正确或基本正确；问题只是英文问题被中文/中英混杂回答。按新规则，不计入真实错误，但保留 `language_mismatch` / `mixed_language_mismatch` 诊断，后续作为语言合同质量单独优化。

| case_id | 原始 strict | category | 事实判断 | 语言问题 |
| --- | --- | --- | --- | --- |
| `88432d0a` | PASS | `multi-session` | 事实正确：过去两周烘焙 4 次。 | 英文问题中文回答。 |
| `gpt4_7fce9456` | FAIL | `multi-session` | 事实正确：Brookside townhouse 前看过 4 套，并给出未 offer 原因。 | 英文问题中文回答/中英混杂。 |
| `b46e15ee` | FAIL | `temporal-reasoning` | 事实正确：参加的是 `Walk for Hunger`。 | 英文问题中文回答。 |
| `gpt4_6dc9b45b` | FAIL | `temporal-reasoning` | 事实正确：SIFF 大约 4 个月前。 | 英文问题中文回答。 |
| `gpt4_8279ba02` | FAIL | `temporal-reasoning` | 事实正确：买/收到 smoker 是 10 天前，inclusive 可为 11 天。 | 英文问题中文回答。 |
| `gpt4_d6585ce8` | FAIL | `temporal-reasoning` | 事实正确：音乐活动顺序与 gold 一致。 | 英文问题中文回答/中英混杂。 |

说明：`gpt4_1d80365e` 也存在语言错配，但它不在本表中，因为它同时存在非语言真实错误：没有给出 `2 days` / `3 days`。

## 原始 FAIL 中被 Judge 认定为 false negative 的 case

这些 case 不计入真实错误，主要是 deterministic scorer 对同义表达、数字英文形式、abstention 改写、长 gold answer、偏好型答案不鲁棒。

| case_id | category | 原始问题类型 | Judge 结论 |
| --- | --- | --- | --- |
| `60bf93ed_abs` | `abstention` | 正确拒答但未匹配 gold 原句 | false negative |
| `88432d0a_abs` | `abstention` | 正确拒答但未匹配 gold 原句 | false negative |
| `c8090214_abs` | `abstention` | 正确拒答但未匹配 gold 原句 | false negative |
| `031748ae` | `knowledge-update` | 语义正确：刚开始 4，现在 5 | false negative |
| `e493bb7c` | `knowledge-update` | 语义正确：painting 当前在 bedroom | false negative |
| `60472f9c` | `multi-session` | 语义正确：two projects | false negative |
| `6456829e` | `multi-session` | 给出 5 tomato + 3 cucumber，等价于 8 total | false negative / 可接受答案 |
| `b3c15d39` | `multi-session` | 给出 5 days，gold 接受 5 或 6 inclusive | false negative |
| `ceb54acb` | `single-session-assistant` | 四个术语全部列出，只是附带解释 | false negative |
| `54026fce` | `single-session-preference` | 使用 virtual coffee break 等用户上下文 | false negative |
| `4100d0a0` | `single-session-user` | mixed Irish and Italian ethnicity | false negative |
| `f4f1d8a4` | `single-session-user` | sister gave the stand mixer | false negative |
| `0bc8ad93` | `temporal-reasoning` | 正确区分两个月前 museum visit 没有 friend | false negative |
| `eac54add` | `temporal-reasoning` | first freelance client contract | false negative |

## 后续统计建议

| 指标 | 建议定义 |
| --- | --- |
| factual_pass_rate | 不计语言错配，只看事实/推理/偏好核心是否正确。v7 当前明确口径约 `48/50 = 96.0%`。 |
| adjusted_factual_preference_pass_rate | 剔除 gold-defective case，并把明确错误 + partial preference miss 都计错。v7 当前为 `45/49 = 91.84%`。 |
| adjusted_factual_preference_error_rate | 剔除 gold-defective case，并把明确错误 + partial preference miss 都计错。v7 当前为 `4/49 = 8.16%`。 |
| strict_static_pass_rate | 保留原始 deterministic scorer，可用于回归比较。v7 为 `28/50 = 56.0%`。 |
| language_contract_pass_rate | 单独统计同语言回答能力。v7 language mismatch 为 `7/50`，pass 为 `43/50 = 86.0%`。 |
| clean_pass_rate | 同时满足 factual correctness 与 language contract，且非边界。需要在 LLM Judge 后单独计算。 |
| boundary_case_rate | partial / gold questionable 单独列出。v7 当前为 `3/50 = 6.0%`，其中 `a2f3aa27` 从 adjusted 分母移除，`0a34ad58` 和 `a89d7624` 在 adjusted 保守口径中计错。 |

## 当前应优先修复的问题

1. scorer final stance false positive：解决 `852ce960` 这类“答案包含 gold，但最终选择相反值”的问题。
2. temporal reasoning over-abstention：解决 `gpt4_1d80365e` 这类 start/end anchor 已充分但模型不计算的问题。
3. deterministic scorer false negative：改用 slot/key-fact 评分、abstention intent、数字英文归一化和 preference rubric。
4. language contract 作为独立质量项继续优化，但从本口径开始不再计入真实错误。
