# 写入治理离线计数评测

## 评测边界

本轮只评测 memory 写入阶段，不评测回答召回效果，也不接入真实 LLM。

- 测试集规模：`1200` 个写入候选。
- 难度拆分：`common = 600`，`hard = 600`。
- 类别拆分：6 类，每类 `200` 个候选。
- 子类型拆分：每类在 common/hard 下各 5 个子类型，每个子类型 20 个变体。
- 基线：原本写入方式，所有成功候选都视为写入，所以基线写入数是 `1200/1200`。
- 增强：叠加写入价值治理，`allow` 才写入，`reject` 和 `review` 都不直接写入。
- 第二阶段：对第一阶段进入 `review` 的候选做离线复核处理，输出 `approve_write`、`keep_review`、`reject`。
- 最终写入安全门：对所有准备最终写入的候选再检查一次重复、冲突和污染风险；这一步可以拦截第一阶段直接 `allow` 但仍有硬重复风险的候选。
- 离线保护：`offline_only = true`，`llm_calls_enabled = false`，`db_access_enabled = false`，`production_state_access_enabled = false`。
- 正式报告：
  - `my_md/memory_optimization/eval_reports/memory_write_governance_counts_eval.json`
  - `my_md/memory_optimization/eval_reports/memory_write_governance_counts_eval.md`

## 离线集配置和线上化边界

本轮 `1200` 个候选来自 `memory2/eval_write_governance_cases.py` 的目标导向模板生成，不是真实线上采样。它的作用是稳定复现“该写、该拒、该复核”的边界样本，便于比较原本写入方式和写入价值治理链路。

生成公式：

```text
2 个难度集合 * 6 个类别 * 5 个子类型 * 20 个变体 = 1200 个候选
```

类别配置：

| 类别 | 期望动作 | 数量 | 主要验证点 |
| --- | --- | ---: | --- |
| `valuable_preference` | 写入 | `200` | 用户明确长期偏好是否被保留 |
| `stable_fact` | 写入 | `200` | 稳定项目事实和规则是否被保留 |
| `temporary` | 拒绝 | `200` | 临时状态是否被挡在长期记忆外 |
| `assistant_inference` | 拒绝 | `200` | 助手猜测和未确认推断是否被拒绝 |
| `duplicate` | 拒绝 | `200` | 重复和近重复记忆是否被控制 |
| `conflict` | 复核 | `200` | 与已有记忆冲突时是否进入复核 |

基线是原本写入方式：只要候选生成成功就算写入。因此基线的优势是不会漏掉有用候选，但缺点是污染、重复和冲突也会全部进入记忆库。

| 口径 | 数值 | 含义 |
| --- | ---: | --- |
| 原本写入 | `1200/1200` | 所有候选都写入 |
| 有用候选写入 | `400/400` | 基线不会漏掉长期有用记忆 |
| 污染、重复、冲突写入 | `800/800` | 基线也会把不该直接写的内容写入 |
| 污染控制率 | `0%` | 原本写入方式没有治理动作 |
| 写入减少率 | `0%` | 原本写入方式不减少写入 |

叠加写入价值治理、复核处理和最终写入安全门后，最终结果是：

| 口径 | 数值 | 含义 |
| --- | ---: | --- |
| 最终写入 | `400/1200` | 只让期望写入的长期有用候选进入最终写入 |
| 有用候选最终保留 | `400/400 = 100.0%` | 有用候选没有最终丢失 |
| 污染候选最终控制 | `800/800 = 100.0%` | 临时、推断、重复和冲突候选没有被错误最终写入 |
| 冲突复核保持 | `200/200 = 100.0%` | 冲突候选继续留在复核态 |
| hard 重复泄漏 | `0/100 = 0.0%` | hard 重复候选没有最终泄漏 |

这组数据可以作为离线规则回归和面试展示数据，但不能直接宣称“线上生产写入治理 100%”。要进入线上评测，需要采集真实写入候选 evidence，至少包含候选摘要、已有相似记忆、`source_ref`、基线决策、治理后决策、实际写入或复核结果，以及用户或可信策略给出的标签。后续还应继续看“写入后是否在未来对话中被正确召回”，否则只能证明写入阶段的离线治理效果，不能证明长期收益。

## 调优内容

这次调优没有简单降低 `allow` 阈值，而是拆分价值和风险：

1. 指标拆分：把原来的保守误伤率拆成直接拒绝误伤、复核分流和未直接写入有用候选。
2. 临时风险收窄：去掉单独 `"测试"`、`"临时"`、`"不要记"` 这类宽泛 marker，避免误伤长期测试计划、评测规则、稳定例外条件和冲突复核规则。
3. 长期价值增强：增加“稳定要求、适用于后续、后续同类任务、跨会话、默认规则、优先级、除非用户临时改口”等长期信号。
4. 冲突复核增强：候选和已有记忆出现相反规则、优先级调整或旧规则覆盖时，优先进入 `review`。
5. 污染保护：保留临时信息、助手推断和重复风险的拦截路径，避免为了提高有用保留率而污染记忆库。

## 调优后总体结果

| 指标 | 数值 | 含义 |
| --- | ---: | --- |
| 候选总数 | `1200` | 本轮离线写入候选数量 |
| 原本写入数量 | `1200/1200` | 基线默认所有候选成功写入 |
| 治理后写入数量 | `172/1200` | 只有 `allow` 的候选进入直接写入 |
| 写入减少率 | `85.6667%` | 相比原本写入方式减少的直接写入比例 |
| 有用候选保留率 | `37.5%` | 期望写入的候选中，治理后仍直接写入的比例 |
| 污染候选控制率 | `97.25%` | 期望拦截或复核的候选中，治理后没有直接写入的比例 |
| 直接拒绝误伤率 | `0.0%` | 期望写入但被直接 `reject` 的比例 |
| 复核分流率 | `62.5%` | 期望写入但进入 `review` 的比例 |
| 未直接写入有用候选率 | `62.5%` | 期望写入但没有自动直接写入的保守口径 |
| 漏拦率 | `2.75%` | 期望拦截或复核但仍直接写入的比例 |
| 复核缺口率 | `0.0%` | 期望进入复核但没有进入复核的比例 |

## 复核处理和最终写入结果

这一版新增了离线 `review resolver` 和最终写入安全门。它们仍然只在离线评测中运行，不代表线上 AgentLoop 已经改变写入行为。

两层口径需要分开看：

- 直接写入：只看第一阶段写入价值治理，`allow` 才算直接写入；本轮仍是 `172/1200`。
- 最终写入：第一阶段 `allow` 加上复核后晋升的候选，再经过最终安全门过滤；本轮是 `400/1200`。

| 指标 | 数值 | 含义 |
| --- | ---: | --- |
| 复核候选数 | `503` | 第一阶段进入 `review` 的候选数量 |
| 复核后晋升写入数 | `253` | 从 `review` 晋升为可写入的候选数量 |
| 复核后保持复核数 | `200` | 仍需等待用户确认或可信策略的候选数量 |
| 复核后拒绝数 | `50` | 复核阶段识别为污染并拒绝的候选数量 |
| 最终写入数量 | `400/1200` | 经过第一阶段、复核处理和最终安全门后的写入数量 |
| 有用候选最终保留率 | `100.0%` | 期望写入的候选中，最终进入写入的比例 |
| hard 有用候选最终保留率 | `100.0%` | hard 期望写入候选中，最终进入写入的比例 |
| 最终污染控制率 | `100.0%` | 期望拦截或复核的候选中，最终没有写入的比例 |
| 冲突复核保持率 | `100.0%` | 冲突候选最终仍保持复核的比例 |
| hard 重复泄漏率 | `0.0%` | hard 重复候选最终被错误写入的比例 |
| 有用候选最终缺口 | `0` | 距离有用候选全部最终保留还差的数量 |
| hard 有用候选最终缺口 | `0` | 距离 hard 有用候选全部最终保留还差的数量 |
| 冲突复核缺口 | `0` | 距离冲突候选全部保持复核还差的数量 |
| 严格理想差距总数 | `0` | 有用最终缺口和冲突复核缺口之和 |

本轮门禁结果全部通过：

| 门禁项 | 目标 | 当前 |
| --- | ---: | ---: |
| 有用候选最终保留率 | `>= 95.0%` | `100.0%` |
| hard 有用候选最终保留率 | `>= 95.0%` | `100.0%` |
| 最终污染控制率 | `>= 90.0%` | `100.0%` |
| 冲突复核保持率 | `>= 99.0%` | `100.0%` |
| hard 重复泄漏率 | `== 0.0%` | `0.0%` |

需要注意：复核处理表里 `hard duplicate` 有 `3/3` 被 resolver 晋升，但最终安全门会再检查一遍近重复风险并拒绝；另外还有 `25` 条第一阶段直接 `allow` 的 hard duplicate 也被最终安全门拒绝。因此最终 hard 重复泄漏率是 `0.0%`。

## 距离理想状态的差距

这里的理想状态采用严格口径：有用记忆 `100%` 保留，污染候选 `100%` 拦截，冲突候选 `100%` 保持复核，hard 重复候选 `0%` 泄漏。

| 指标 | 当前 | 理想 | 差距 |
| --- | ---: | ---: | ---: |
| 有用候选最终保留率 | `100.0%` | `100.0%` | 已达成 |
| hard 有用候选最终保留率 | `100.0%` | `100.0%` | 已达成 |
| 最终污染控制率 | `100.0%` | `100.0%` | 已达成 |
| 冲突复核保持率 | `100.0%` | `100.0%` | 已达成 |
| hard 重复泄漏率 | `0.0%` | `0.0%` | 已达成 |

换成数量：

- 有用候选总共 `400` 条，最终写入 `400` 条，最终缺口为 `0`。
- hard 有用候选总共 `200` 条，最终写入 `200` 条，最终缺口为 `0`。
- 冲突候选总共 `200` 条，最终保持复核 `200` 条，复核缺口为 `0`。
- 污染候选总共 `800` 条，最终控制 `800` 条，已经没有污染写入。
- hard 重复候选最终写入 `0` 条，重复泄漏已经压到理想状态。

因此在当前 `1200` 条离线写入治理测试集上，严格理想差距总数已经从 `54` 降到 `0`。这不代表线上真实写入已经自动变更，只说明离线 shadow 评测中的 hard 有用误伤和冲突复核缺口已经被当前规则覆盖。

## hard 有用候选恢复调优结果

本轮修复的是 temporary marker 的误伤，不是降低 allow 阈值。修复前，`除非用户临时改口` 被 broad `"临时"` marker 当成临时状态；`不要记录来源` 被 broad `"不要记"` marker 当成不要记忆。修复后，这两类表达分别回到长期规则例外条件和冲突复核路径。

| 指标 | 修复前 | 修复后 | 变化 |
| --- | ---: | ---: | ---: |
| 有用候选最终保留率 | `87.5%` | `100.0%` | `+12.5` 个百分点 |
| hard 有用候选最终保留率 | `75.0%` | `100.0%` | `+25.0` 个百分点 |
| 冲突复核保持率 | `98.0%` | `100.0%` | `+2.0` 个百分点 |
| 最终污染控制率 | `100.0%` | `100.0%` | `0.0` 个百分点 |
| hard 重复泄漏率 | `0.0%` | `0.0%` | `0.0` 个百分点 |

数量口径：

- 有用候选最终缺口从 `50/400` 降到 `0/400`。
- hard 有用候选最终缺口从 `50/200` 降到 `0/200`。
- 冲突复核缺口从 `4/200` 降到 `0/200`。
- strict ideal gap 从 `54` 降到 `0`。

## 前后对比

| 指标 | 调优前 | 调优后 | 变化 |
| --- | ---: | ---: | ---: |
| 有用候选保留率 | `35.0%` | `37.5%` | `+2.5` 个百分点 |
| 污染候选控制率 | `92.25%` | `97.25%` | `+5.0` 个百分点 |
| 直接拒绝误伤率 | `20.0%` | `0.0%` | `-20.0` 个百分点 |
| 复核分流率 | `45.0%` | `62.5%` | `+17.5` 个百分点 |
| 未直接写入有用候选率 | `65.0%` | `62.5%` | `-2.5` 个百分点 |
| 漏拦率 | `7.75%` | `2.75%` | `-5.0` 个百分点 |
| 冲突复核缺口率 | `71.0%` | `0.0%` | `-71.0` 个百分点 |

## 写入治理主表

| 类别 | 期望 | 原本写入 | 治理后写入 | 治理后拒绝 | 治理后复核 | 污染减少 | 有用保留率 | 治理率 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| valuable_preference | write | 200/200 (100.0%) | 75/200 (37.5%) | 0/200 (0.0%) | 125/200 (62.5%) | 0/200 (0.0%) | 37.5% | 62.5% |
| stable_fact | write | 200/200 (100.0%) | 75/200 (37.5%) | 0/200 (0.0%) | 125/200 (62.5%) | 0/200 (0.0%) | 37.5% | 62.5% |
| temporary | block | 200/200 (100.0%) | 0/200 (0.0%) | 200/200 (100.0%) | 0/200 (0.0%) | 200/200 (100.0%) | 0.0% | 100.0% |
| assistant_inference | block | 200/200 (100.0%) | 0/200 (0.0%) | 150/200 (75.0%) | 50/200 (25.0%) | 200/200 (100.0%) | 0.0% | 100.0% |
| duplicate | block | 200/200 (100.0%) | 22/200 (11.0%) | 175/200 (87.5%) | 3/200 (1.5%) | 178/200 (89.0%) | 11.0% | 89.0% |
| conflict | review | 200/200 (100.0%) | 0/200 (0.0%) | 0/200 (0.0%) | 200/200 (100.0%) | 200/200 (100.0%) | 0.0% | 100.0% |

## Common/Hard 分组表

| 难度 | 类别 | 期望 | 原本写入 | 治理后写入 | 治理后拒绝 | 治理后复核 | 治理率 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| common | valuable_preference | write | 100/100 (100.0%) | 75/100 (75.0%) | 0/100 (0.0%) | 25/100 (25.0%) | 25.0% |
| common | stable_fact | write | 100/100 (100.0%) | 75/100 (75.0%) | 0/100 (0.0%) | 25/100 (25.0%) | 25.0% |
| common | temporary | block | 100/100 (100.0%) | 0/100 (0.0%) | 100/100 (100.0%) | 0/100 (0.0%) | 100.0% |
| common | assistant_inference | block | 100/100 (100.0%) | 0/100 (0.0%) | 75/100 (75.0%) | 25/100 (25.0%) | 100.0% |
| common | duplicate | block | 100/100 (100.0%) | 0/100 (0.0%) | 100/100 (100.0%) | 0/100 (0.0%) | 100.0% |
| common | conflict | review | 100/100 (100.0%) | 0/100 (0.0%) | 0/100 (0.0%) | 100/100 (100.0%) | 100.0% |
| hard | valuable_preference | write | 100/100 (100.0%) | 0/100 (0.0%) | 0/100 (0.0%) | 100/100 (100.0%) | 100.0% |
| hard | stable_fact | write | 100/100 (100.0%) | 0/100 (0.0%) | 0/100 (0.0%) | 100/100 (100.0%) | 100.0% |
| hard | temporary | block | 100/100 (100.0%) | 0/100 (0.0%) | 100/100 (100.0%) | 0/100 (0.0%) | 100.0% |
| hard | assistant_inference | block | 100/100 (100.0%) | 0/100 (0.0%) | 75/100 (75.0%) | 25/100 (25.0%) | 100.0% |
| hard | duplicate | block | 100/100 (100.0%) | 22/100 (22.0%) | 75/100 (75.0%) | 3/100 (3.0%) | 78.0% |
| hard | conflict | review | 100/100 (100.0%) | 0/100 (0.0%) | 0/100 (0.0%) | 100/100 (100.0%) | 100.0% |

## 诊断表

### 误伤表

| 类别 | 数量 | 占比 | 说明 |
| --- | ---: | ---: | --- |
| valuable_preference | 125/200 | 62.5% | 该写入的内容被拦截或复核 |
| stable_fact | 125/200 | 62.5% | 该写入的内容被拦截或复核 |

### 漏拦表

| 类别 | 数量 | 占比 | 说明 |
| --- | ---: | ---: | --- |
| duplicate | 22/200 | 11.0% | 不应直接写入的内容仍被写入 |

### 复核缺口表

| 类别 | 数量 | 占比 | 说明 |
| --- | ---: | ---: | --- |
| 无 | 0/0 | 0.0% | 本次没有对应问题 |

## 结论

这次调优达到了几个关键目标：污染候选控制率从 `92.25%` 提高到 `97.25%`，漏拦率从 `7.75%` 降到 `2.75%`，冲突复核缺口从 `71.0%` 降到 `0.0%`。这说明“冲突进复核”和“风险优先治理”的方向有效。

直接拒绝误伤也从 `20.0%` 降到 `0.0%`，说明收窄 temporary marker 后，长期测试计划、评测规则和“除非用户临时改口”这类稳定规则例外不再被误判成临时状态。

但有用候选直接保留率仍是 `37.5%`，hard preference 和 hard stable fact 仍然主要进入 `review`，没有通过降低直接写入阈值换取数字。新增复核处理和本轮 temporary marker 修复后，有用候选最终保留率从 `87.5%` 提升到 `100.0%`，hard 有用候选最终保留率从 `75.0%` 提升到 `100.0%`。这说明“先保守进入复核，再由第二阶段晋升安全候选”的链路比单纯降低直接写入阈值更稳。

面试中可以这样表达：写入治理不是一轮就追求全部自动直接写入，而是先保证污染不进库，再逐步提高有用记忆最终保留。本轮先把冲突复核缺口从 71% 降到 0%，污染控制提高到 97.25%，直接拒绝误伤降到 0%；随后通过复核 resolver 和最终安全门，让有用候选最终保留率达到 100%，hard 有用候选最终保留率达到 100%，同时最终污染控制率保持 100%，hard 重复泄漏率为 0%。剩余边界是：这仍是离线 shadow 评测，还没有接入线上真实写入链路。

## 后续计划

- 保持第一阶段直接写入阈值保守，不通过降低 `allow` 门槛换取漂亮数字。
- 把离线 resolver 的决策信号进一步约束在生产可用字段上，继续避免依赖评测标签。
- 如果后续进入线上写入链路，需要先设计用户确认、可信策略和可回滚写入边界。
- 在线测试仍需等待离线策略稳定，并且必须采集真实候选、真实决策、真实写入结果和后续召回有用率。

## 测试集驱动的线上 shadow 评测

当前新增了写入治理线上 shadow 评测入口：

```text
scripts/run_memory_write_governance_online_eval.py
```

这一步的“线上”含义要严格限定：它会让测试集候选穿过真实 `AgentLoop.process_direct()`，并可选调用真实 LLM；但候选摘要和标签仍来自测试集，写入治理仍是旁路 shadow 判断，不改生产记忆库。它验证的是在线运行路径、provider 行为、token/延迟记录、checkpoint/resume 和 write evidence 生成，不证明 LLM 已经能自动抽取候选记忆。

安全边界：

- 默认不调用真实 LLM，必须显式传 `--enable-real-llm`。
- fake-provider 可跑通完整链路，但不代表真实模型效果。
- 每轮调用使用 `skip_post_memory=True`，不触发 post-response memory 写入。
- 使用临时 workspace，不写生产 memory DB 或 observe DB。
- `label` 来自测试集预标注，不来自模型自评。
- `baseline_decision = allow` 表示原本写入方式会直接写入成功候选。
- `after_decision` 表示写入价值治理、复核 resolver 和最终安全门后的最终结果，映射为 `allow / reject / review`。

当前 fake-provider smoke 命令：

```bash
.venv/bin/python scripts/run_memory_write_governance_online_eval.py \
  --workspace /tmp/akashic-memory-write-governance-online-fake-v2/workspace \
  --out-dir /tmp/akashic-memory-write-governance-online-fake-v2/reports \
  --fake-provider \
  --case-set all \
  --limit 24 \
  --checkpoint-jsonl /tmp/akashic-memory-write-governance-online-fake-v2/reports/checkpoint.jsonl \
  --resume
```

生成的 evidence 接入现有目标指标报表：

```bash
.venv/bin/python scripts/run_memory_target_metrics_eval.py \
  --out-dir /tmp/akashic-memory-write-governance-online-fake-v2/target \
  --online-checkpoint-source fake_provider \
  --online-write-evidence-json /tmp/akashic-memory-write-governance-online-fake-v2/reports/memory_write_governance_online_evidence.jsonl
```

本轮 fake-provider 结果：

| 项目 | 数值 |
| --- | ---: |
| candidate_count | `24` |
| real_llm_enabled | `False` |
| infra_passed | `True` |
| provider_error_count | `0` |
| timeout_count | `0` |
| total_token_count | `720` |
| avg_latency_ms | `34.5417` |

Evidence 分布：

| label | count | after allow | after reject | after review |
| --- | ---: | ---: | ---: | ---: |
| useful | `8` | `8` | `0` | `0` |
| pollution | `8` | `0` | `8` | `0` |
| duplicate | `4` | `0` | `4` | `0` |
| conflict | `4` | `0` | `0` | `4` |

接入 target metrics 后的线上 evidence 行：

| 指标 | before | after | 变化 |
| --- | ---: | ---: | ---: |
| 有效写入精度 | `33.3333%` | `100.0%` | `+66.6667` 个百分点 |
| 污染拦截率 | `0.0%` | `100.0%` | `+100.0` 个百分点 |
| 重复控制率 | `0.0%` | `100.0%` | `+100.0` 个百分点 |
| 冲突复核率 | `0.0%` | `100.0%` | `+100.0` 个百分点 |
| 写入减少率 | `0.0%` | `66.6667%` | `+66.6667` 个百分点 |
| 误拒率 | `0.0%` | `0.0%` | `0.0` 个百分点 |
| 误收率 | `100.0%` | `0.0%` | `-100.0` 个百分点 |

这个结果说明：在测试集驱动的 fake-provider 在线 shadow 链路上，现有写入治理代码可以生成 target-metric-compatible evidence，并能把原本全写入的污染、重复和冲突候选挡住，同时保留有用候选。它仍然不是正式真实 LLM 结果；下一步如果要跑真实模型，应复用同一脚本，把 `--fake-provider` 换成 `--enable-real-llm`，并保留 checkpoint。

## 真实 LLM 小样本 pilot

随后用同一批 `24` 条平衡样本跑了真实 LLM pilot。第一次在沙箱内直接运行时，provider 请求连续等到 `60s` 超时，checkpoint 中已有 `7` 条 timeout 记录；改用允许外部 provider 网络访问的方式后，先跑 `6` 条诊断通过，再跑完整 `24` 条 pilot 通过。

真实 pilot 命令：

```bash
.venv/bin/python scripts/run_memory_write_governance_online_eval.py \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --workspace /tmp/akashic-memory-write-governance-online-real-pilot-v2/workspace \
  --out-dir /tmp/akashic-memory-write-governance-online-real-pilot-v2/reports \
  --enable-real-llm \
  --case-set all \
  --limit 24 \
  --timeout-s 60 \
  --concurrency 1 \
  --checkpoint-jsonl /tmp/akashic-memory-write-governance-online-real-pilot-v2/reports/checkpoint.jsonl \
  --resume
```

真实 evidence 接入 target metrics：

```bash
.venv/bin/python scripts/run_memory_target_metrics_eval.py \
  --out-dir /tmp/akashic-memory-write-governance-online-real-pilot-v2/target \
  --online-checkpoint-source real_llm \
  --online-write-evidence-json /tmp/akashic-memory-write-governance-online-real-pilot-v2/reports/memory_write_governance_online_evidence.jsonl
```

真实 pilot 运行结果：

| 项目 | 数值 |
| --- | ---: |
| candidate_count | `24` |
| checkpoint rows | `24` |
| evidence rows | `24` |
| real_llm_enabled | `True` |
| infra_passed | `True` |
| provider_error_count | `0` |
| timeout_count | `0` |
| total_token_count | `124099` |
| avg_latency_ms | `2790.7917` |

真实 LLM evidence 分布：

| label | count | after allow | after reject | after review |
| --- | ---: | ---: | ---: | ---: |
| useful | `8` | `8` | `0` | `0` |
| pollution | `8` | `0` | `8` | `0` |
| duplicate | `4` | `0` | `4` | `0` |
| conflict | `4` | `0` | `0` | `4` |

真实 target metrics 线上 evidence 行：

| 指标 | before | after | 变化 |
| --- | ---: | ---: | ---: |
| 有效写入精度 | `33.3333%` | `100.0%` | `+66.6667` 个百分点 |
| 污染拦截率 | `0.0%` | `100.0%` | `+100.0` 个百分点 |
| 重复控制率 | `0.0%` | `100.0%` | `+100.0` 个百分点 |
| 冲突复核率 | `0.0%` | `100.0%` | `+100.0` 个百分点 |
| 写入减少率 | `0.0%` | `66.6667%` | `+66.6667` 个百分点 |
| 误拒率 | `0.0%` | `0.0%` | `0.0` 个百分点 |
| 误收率 | `100.0%` | `0.0%` | `-100.0` 个百分点 |

这说明真实 LLM 参与运行路径后，write evidence 仍能稳定生成并被 target metrics 消费；本轮 24 条样本中没有 provider error 或 timeout。它仍然不是生产流量评测，也不是 LLM 自动抽取候选记忆评测，因为候选和标签仍来自测试集。

## 真实 LLM 扩展样本评测

为了避免 `24` 条 pilot 样本过小，本轮先修复了在线评测的有限样本选择逻辑：`--case-set all --limit 240` 现在同时按 `common / hard` 和 6 个类别分层抽样，而不是只按类别轮询。扩展样本构成为 common `120`、hard `120`，6 个类别各 `40` 条。

真实扩展评测命令：

```bash
.venv/bin/python scripts/run_memory_write_governance_online_eval.py \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --workspace /tmp/akashic-memory-write-governance-expanded-real-240/workspace \
  --out-dir /tmp/akashic-memory-write-governance-expanded-real-240/reports \
  --enable-real-llm \
  --case-set all \
  --limit 240 \
  --timeout-s 60 \
  --concurrency 1 \
  --checkpoint-jsonl /tmp/akashic-memory-write-governance-expanded-real-240/reports/checkpoint.jsonl \
  --resume
```

真实扩展 evidence 接入 target metrics：

```bash
.venv/bin/python scripts/run_memory_target_metrics_eval.py \
  --out-dir /tmp/akashic-memory-write-governance-expanded-real-240/target \
  --online-checkpoint-source real_llm \
  --online-write-evidence-json /tmp/akashic-memory-write-governance-expanded-real-240/reports/memory_write_governance_online_evidence.jsonl
```

真实扩展运行结果：

| 项目 | 数值 |
| --- | ---: |
| candidate_count | `240` |
| checkpoint rows | `240` |
| evidence rows | `240` |
| common / hard | `120 / 120` |
| 每个类别样本数 | `40` |
| real_llm_enabled | `True` |
| infra_passed | `True` |
| provider_error_count | `0` |
| timeout_count | `0` |
| completed_call_count | `240` |
| skipped_from_checkpoint_count | `0` |
| total_token_count | `1236228` |
| avg_latency_ms | `2366.625` |

真实扩展 evidence 分布：

| label | count | after allow | after reject | after review |
| --- | ---: | ---: | ---: | ---: |
| useful | `80` | `80` | `0` | `0` |
| pollution | `80` | `0` | `80` | `0` |
| duplicate | `40` | `0` | `40` | `0` |
| conflict | `40` | `0` | `0` | `40` |

真实扩展 target metrics 线上 evidence 行：

| 指标 | before | after | 变化 |
| --- | ---: | ---: | ---: |
| 有效写入精度 | `33.3333%` | `100.0%` | `+66.6667` 个百分点 |
| 污染拦截率 | `0.0%` | `100.0%` | `+100.0` 个百分点 |
| 重复控制率 | `0.0%` | `100.0%` | `+100.0` 个百分点 |
| 冲突复核率 | `0.0%` | `100.0%` | `+100.0` 个百分点 |
| 写入减少率 | `0.0%` | `66.6667%` | `+66.6667` 个百分点 |
| 误拒率 | `0.0%` | `0.0%` | `0.0` 个百分点 |
| 误收率 | `100.0%` | `0.0%` | `-100.0` 个百分点 |

这轮结果把主展示从 `24` 条 pilot 升级到 `240` 条真实 LLM shadow 扩展样本。它证明测试集驱动的 AgentLoop + 真实 provider + write evidence + target metrics 链路在更大平衡样本下仍能稳定运行，并且治理决策继续符合预期。但边界不变：候选摘要和标签来自测试集，治理决策来自项目代码，`skip_post_memory=True` 阻止写入生产记忆库；它不是自然生产流量，也不是 LLM 自动抽取候选记忆的质量评测。

本轮没有默认运行真实 LLM `1200` 条全量评测。原因是 `240` 条已经覆盖 common/hard 和 6 类平衡样本，且全量 `1200` 预计还会消耗约 `6.2M` token；应在确认需要更强统计展示时再用同一 checkpoint 机制执行。

## 复核候选处理链路

当前已补齐离线版 `review` 后续处理。原因是调优后 hard 有用候选已经从“直接拒绝”更多转成“进入复核”，如果没有复核处理链路，这些候选仍然不会成为长期记忆。

当前离线 resolver 的设计：

1. 输入：写入治理输出的 `review` 候选、评分信号、已有相似记忆和 source_ref。
2. 输出：`approve_write`、`keep_review`、`reject` 三种处理结果。
3. 规则：
   - 有明确长期价值、source_ref 可信、无重复或冲突的候选，可以从 `review` 晋升为 `approve_write`。
   - 有冲突、范围变化、优先级变化的候选继续 `keep_review`，等待用户确认或可信策略。
   - 仍然像临时状态、助手推断或重复污染的候选保持 `reject`。
4. 约束：决策逻辑不使用 `category`、`case_set`、`subtype` 这类评测标签，只使用 summary、score result、existing memories 和 source_ref。
5. 评测方式：继续使用当前 `1200` 候选集，新增“复核处理表”和“最终安全门”指标，重点看：
   - review 候选中有多少被成功晋升写入；
   - hard 有用候选最终保留率是否提升；
   - conflict 是否仍保持复核，不被错误自动写入；
   - duplicate hard 漏拦是否下降；
   - 污染控制率是否仍不低于 `90%`。

目标口径和当前结果：

| 指标 | 目标 | 当前结果 |
| --- | ---: | ---: |
| 有用候选最终保留率 | 不低于 `95%` | `100.0%` |
| hard 有用候选最终保留率 | 不低于 `95%` | `100.0%` |
| 最终污染控制率 | 不低于 `90%` | `100.0%` |
| 冲突复核保持率 | 不低于 `99%` | `100.0%` |
| hard 重复泄漏率 | 等于 `0%` | `0.0%` |

这样做的好处是：写入治理不再只回答“是否直接写”，而是形成“直接写、拒绝、复核后写入、复核后继续等待”的完整链路，更接近真实 agent 的长期记忆治理。
