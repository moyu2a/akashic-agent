# LongMemEval Phase B Full 外部 LLM Judge 总结

## 结论

- 外部 Judge 文件：`/home/jjh/git_work/akashic-agent/b1_LLM_Judge.md`
- 已归档副本：`phase_b_full_external_LLM_judge_raw.md`
- 覆盖范围：`500/500`，所有 case_id 均与 Phase B case index 对齐。
- 本轮仍然只代表 LongMemEval public full 的 P5-only `chain_tri_governed_answer_contract`，不代表 P1-P5 消融或不同治理方案比较。
- 按用户既定口径，中英混搭/语言不一致只记录为语言指标；preference gold/偏好 partial 不纳入主事实错误，但单独保留。

## Judge 分类

| 分类 | 数量 | 说明 |
| --- | ---: | --- |
| `reasonable_pass` | 277 | 合理 PASS |
| `false_negative` | 180 | static FAIL 但 Judge 认为正确 |
| `false_positive_model_error` | 8 | static PASS 但 Judge 认为模型错误 |
| `explicit_model_error` | 12 | static FAIL 且 Judge 认为模型明确错误 |
| `partial_preference_miss` | 14 | 偏好型 partial，记录但不进主事实错误 |
| `gold_or_evidence_boundary` | 9 | gold / 证据边界，主指标剔除 |

## 调整后指标

| 指标 | 数值 |
| --- | ---: |
| 原始 case 数 | 500 |
| gold / 证据边界剔除 | 9 |
| 有效分母 | 491 |
| 主事实口径 true factual model error | 20 |
| 主事实口径错误率 | 4.07% |
| 主事实口径通过数 | 471 |
| 主事实口径通过率 | 95.93% |
| preference partial 记录项 | 14 |
| 保守口径错误数，计入 preference partial | 34 |
| 保守口径通过率，计入 preference partial 为错误 | 93.08% |

## 错误场景与稳定性判断

保守口径为 `457/491 = 93.08%`，其中 `34` 条错误由 `20` 条 true factual model error 加 `14` 条 preference partial 组成。主事实口径为 `471/491 = 95.93%`。

| 场景 | 涉及数量/位置 | 典型表现 | 原因判断 | 稳定性 |
| --- | ---: | --- | --- | --- |
| 多 session 数量/金额汇总 | true error 中 `multi-session` 10 条 | 少算一个 item、漏掉一笔费用、漏掉一个项目/活动 | 模型在多证据计数、求和、集合合并时偏保守；当证据分散在多个 session 或有时间窗口限制时，容易把应计入项排除。 | 固定模式问题 |
| knowledge-update 当前状态判断 | true error 中 `knowledge-update` 6 条 | 最新额度、当前保存位置、最近一次习惯变化、奖励积分等答成旧状态或反向 | 对 `current` / `now` / `most recently` / `usually` 的版本优先级不够硬；新旧证据冲突时仍可能选错旧状态。 | 固定模式问题 |
| 时间推理边界 | true error 中 `temporal-reasoning` 2 条，gold boundary 3 条 | relative date、先后顺序、`last week` / `5 days ago` 等边界判断 | 系统大体能处理时间题，但复杂相对时间、数据集时间锚和 gold 边界混在一起时会产生少量错误。 | 混合：少量偶发推理错误 + 数据边界 |
| 不足信息时的 abstention | true error 中 `abstention` 1 条，partial 4 条 | 应说信息不足时进行了估算，或拒答但没有指出关键已知对照 | 对“缺少价格/地点/目标对象”等不可推断字段的硬拒答还不够一致；有时会补估计值。 | 低频但可规则加固 |
| preference / recommendation partial | partial 中主要集中在 `single-session-preference` 8 条 | 推荐题回答泛化，没有充分利用已有偏好或用户上下文 | 这不是事实召回失败，而是产品体验问题；模型过度要求用户补充信息，没有把记忆偏好转化为建议。 | 固定体验问题 |
| static scorer 误判 | false negative 180 条 | 模型事实答对，但字符串、格式、语言或语义等价导致 static FAIL | strict/static scorer 明显低估真实能力；该问题属于评测器噪声，不是 agent 事实能力问题。 | 固定评分器问题 |

复盘结论：

- 真正需要优先修 agent 的稳定问题是：多证据聚合少算、当前状态/版本选择错误。
- preference partial 应作为产品体验优化项处理，不应和事实召回错误混在一起。
- 中英混搭和 static scorer false negative 不应继续作为核心错误看待；它们适合保留为语言指标和评分器噪声指标。
- 当前错误不是纯随机抖动，主导问题可以归纳为几个链路弱点；后续修复应针对能力模式加固，而不是针对单个 case 写特例。

## Static Scorer 复盘

| 项目 | 数量 |
| --- | ---: |
| static PASS 且 Judge 合理 PASS | 277 |
| static PASS 但 Judge 判模型错误 false positive | 8 |
| static PASS 但 gold/证据边界 | 4 |
| static FAIL 但 Judge 判正确 false negative | 180 |
| static FAIL 且 Judge 判明确模型错误 | 12 |
| static FAIL 且 Judge 判 preference partial | 14 |
| static FAIL 且 gold/证据边界 | 5 |

结论：strict/static scorer 的 `57.8%` 明显低估真实能力，主要噪声来自字符串/格式/语义等价导致的 false negative；最终 correctness 应以外部 Judge 调整后指标为准。

## 真正事实错误 Case

| order | case_id | category | static | Judge 结论 |
| ---: | --- | --- | --- | --- |
| 32 | `gpt4_fe651585` | temporal-reasoning | PASS | false positive。模型不应算 PASS |
| 33 | `3a704032` | multi-session | PASS | false positive。模型少算 |
| 34 | `gpt4_d84a3211` | multi-session | PASS | false positive。模型少算 |
| 37 | `46a3abf7` | multi-session | PASS | false positive。模型少算 |
| 73 | `852ce960` | knowledge-update | PASS | false positive。模型最终答案与 gold 相反 |
| 77 | `ce6d2d27` | knowledge-update | PASS | false positive。模型应答 Friday |
| 81 | `0f05491a` | knowledge-update | PASS | false positive。模型 final stance 不正确 |
| 103 | `59524333` | knowledge-update | PASS | false positive。模型不应算 PASS |
| 318 | `0a995998` | multi-session | FAIL | 明确模型错误 |
| 319 | `6d550036` | multi-session | FAIL | 明确模型错误 |
| 325 | `c4a1ceb8` | multi-session | FAIL | 明确模型错误 |
| 326 | `gpt4_a56e767c` | multi-session | FAIL | 明确模型错误 |
| 335 | `gpt4_731e37d7` | multi-session | FAIL | 明确模型错误 |
| 358 | `c6853660` | knowledge-update | FAIL | 明确模型错误 |
| 366 | `07741c45` | knowledge-update | FAIL | 明确模型错误 |
| 401 | `dc439ea3` | single-session-assistant | FAIL | 明确模型错误 |
| 482 | `gpt4_68e94288` | temporal-reasoning | FAIL | 明确模型错误 |
| 484 | `85fa3a3f` | multi-session | FAIL | 明确模型错误 |
| 487 | `9ee3ecd6` | multi-session | FAIL | 明确模型错误 |
| 498 | `09ba9854_abs` | abstention | FAIL | 明确模型错误 |

## Preference Partial 记录项

| order | case_id | category | static |
| ---: | --- | --- | --- |
| 322 | `e831120c` | multi-session | FAIL |
| 340 | `edced276_abs` | abstention | FAIL |
| 341 | `gpt4_372c3eed_abs` | abstention | FAIL |
| 354 | `e66b632c` | knowledge-update | FAIL |
| 360 | `031748ae_abs` | abstention | FAIL |
| 362 | `2133c1b5_abs` | abstention | FAIL |
| 370 | `0edc2aef` | single-session-preference | FAIL |
| 371 | `35a27287` | single-session-preference | FAIL |
| 378 | `6b7dfb22` | single-session-preference | FAIL |
| 388 | `1da05512` | single-session-preference | FAIL |
| 389 | `fca70973` | single-session-preference | FAIL |
| 392 | `b0479f84` | single-session-preference | FAIL |
| 393 | `1d4e3b97` | single-session-preference | FAIL |
| 396 | `0a34ad58` | single-session-preference | FAIL |

## Gold / 证据边界剔除项

| order | case_id | category | static | Judge 结论 |
| ---: | --- | --- | --- | --- |
| 67 | `bf659f65` | multi-session | PASS | gold boundary / 边界 PASS，不算模型明确错误 |
| 113 | `a2f3aa27` | knowledge-update | PASS | gold boundary / 边界 PASS，不算模型错误 |
| 203 | `8a137a7f` | single-session-user | PASS | gold / 证据边界。模型事实处理可接受，不算明确模型错误 |
| 242 | `51c32626` | multi-session | PASS | gold / 证据边界。模型不算明确错误 |
| 301 | `gpt4_8c8961ae` | temporal-reasoning | FAIL | gold / 证据边界 |
| 329 | `7024f17c` | multi-session | FAIL | gold / 证据边界 |
| 453 | `370a8ff4` | temporal-reasoning | FAIL | gold / 证据边界 |
| 469 | `71017277` | temporal-reasoning | FAIL | gold / 证据边界 |
| 492 | `37f165cf` | multi-session | FAIL | gold / 证据边界 |

## Category 维度

| category | reasonable_pass | false_negative | true_error | partial_preference | gold_boundary |
| --- | ---: | ---: | ---: | ---: | ---: |
| abstention | 0 | 25 | 1 | 4 | 0 |
| knowledge-update | 48 | 16 | 6 | 1 | 1 |
| multi-session | 88 | 18 | 10 | 1 | 4 |
| single-session-assistant | 37 | 18 | 1 | 0 | 0 |
| single-session-preference | 0 | 22 | 0 | 8 | 0 |
| single-session-user | 53 | 10 | 0 | 0 | 1 |
| temporal-reasoning | 51 | 71 | 2 | 0 | 3 |

## 产物

- 逐 case Judge 原文归档：`phase_b_full_external_LLM_judge_raw.md`
- 机器可读分类索引：`phase_b_full_external_LLM_judge_case_index.json`
- 本总结：`phase_b_full_external_LLM_judge_summary_zh.md`
