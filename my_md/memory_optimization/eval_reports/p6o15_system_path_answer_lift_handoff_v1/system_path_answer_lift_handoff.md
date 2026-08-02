# P6o-15 System Path Answer Lift Handoff

本文用于从 side conversation 回到主线程后继续推进。它记录 P6o-14 的测试方法、数据、结论、发现的问题，以及下一阶段目标和计划方法。

## 当前基线

当前最新有效报告：

- `my_md/memory_optimization/eval_reports/p6o14_system_path_safe_version_real_llm_ab_v1/system_path_safe_version_eval.json`
- `my_md/memory_optimization/eval_reports/p6o14_system_path_safe_version_real_llm_ab_v1/system_path_safe_version_eval.md`

P6o-14 的目标不是复测 eval-only profile，而是验证 safe version-governed 方案接入真实 system path 后是否仍然有效。

实际链路：

```text
AgentLoop
-> DefaultMemoryRetrievalPipeline
-> DefaultMemoryEngine.retrieve()
-> retrieved_memory_block
-> prompt render
-> real LLM answer
-> answer expectation scoring
```

## P6o-14 测试方法

- case pack：`standard`
- case 规模：common `20` + hard `20`
- unique case：`40`
- mode：
  - `current`
  - `safe_version_replace`
- total calls：`80`
- provider：真实 LLM
- config：`/home/jjh/git_work/akashic-agent/config.toml`
- workspace：临时目录 `/tmp/akashic-memory-p6o14-system-path-safe-version-real/workspace`
- memory 数据：fixture-seeded temporary system-path store
- `--real-memory-workspace`：仅为 CLI 兼容保留，本 runner 未读取真实用户 memory DB
- scoring：
  - 使用 `answer_expectation_from_case()`
  - 使用 `score_answer_text()`
  - 统计 answer、grounding、forbidden、token、latency、contract success、post-check shadow
- 隐私边界：
  - committed report 不写 prompt text
  - 不写用户 query 原文
  - 不写 memory summary 原文
  - 不写 complete response
  - 不写 conversation log
  - 不写 secrets 或 authorization values

## P6o-14 数据

整体指标：

| metric | value |
| --- | ---: |
| unique_case_count | `40` |
| case_count | `80` |
| provider_error_count | `0` |
| timeout_count | `0` |
| token_metrics_available | `True` |
| aggregate answer_rate | `40.0%` |
| aggregate grounding_rate | `100.0%` |
| aggregate forbidden_rate | `16.25%` |
| total_token_count | `436123` |
| avg_total_token_count | `5451.5375` |
| avg_latency_ms | `4867.4375` |

Per-mode result：

| mode | answer | grounding | forbidden | avg tokens | avg latency | contract success | post-check shadow |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `current` | `11/40 = 27.5%` | `40/40 = 100.0%` | `13/40 = 32.5%` | `5488.75` | `5329.475ms` | `0.0%` | `0.0%` |
| `safe_version_replace` | `21/40 = 52.5%` | `40/40 = 100.0%` | `0/40 = 0.0%` | `5414.325` | `4405.4ms` | `100.0%` | `100.0%` |

Delta vs `current`：

| metric | delta |
| --- | ---: |
| answer_rate | `+25.0` points |
| grounding_rate | `0.0` points |
| forbidden_rate | `-32.5` points |
| avg_total_token_count | `-74.425` |
| avg_latency_ms | `-924.075ms` |

## P6o-14 结论

P6o-14 real system-path A/B gate passed。

判断依据：

- `safe_version_replace` answer rate 高于 `current`：`52.5%` vs `27.5%`
- grounding 不下降：两组都是 `100.0%`
- forbidden 明显下降：`32.5% -> 0.0%`
- contract generation 在 replace mode 为 `100.0%`
- post-check shadow 在 replace mode 为 `100.0%`
- token 和 latency 没有上升，反而下降
- provider error 和 timeout 均为 `0`

因此，`safe_version_replace` 不是只在 fake smoke 中可用；它在真实 LLM system path 小矩阵中也明显优于当前路径。

## 为什么没有复现之前接近 100% 的数据

之前接近 `100%` 的结果来自 eval-only / comprehensive profile：

- P6o-10：`chain_tri_version_governed_answer_contract` 曾达到 `40/40 = 100.0%`
- P6o-12：repeat stability 后 safe version-governed 为 `117/120 = 97.5%`

这些 profile 使用的是更理想的 evidence / answer contract 注入方式，模型看到的约束更强。

P6o-14 改成 system path 后，测试口径更真实：

- evidence contract 通过 memory block 进入真实 AgentLoop
- 真实系统提示、工具边界、turn 结构和 memory block 拼接都会影响模型
- answer scoring 从“是否有可用路径”变成真正命中 answer expectation
- grounding 已经 `100.0%`，说明目标证据进入上下文；answer 仍不高，说明瓶颈是 evidence-to-answer

所以 P6o-14 的 `52.5%` 不是方案失效，而是测试从理想 profile 升级为真实 system path 后暴露了新的主要问题：模型没有稳定把已进入上下文的证据转成符合答案规则的回答。

## 当前发现的问题

1. **命中率仍不足以生产默认开启**
   - `safe_version_replace` 只有 `21/40 = 52.5%`
   - 虽然明显优于 current，但距离 P6o-12 eval profile 的 `97.5%` 仍有明显差距

2. **主要瓶颈不是召回**
   - 两组 grounding 都是 `100.0%`
   - 说明目标证据已进入上下文
   - 后续不应优先扩大 graph/all-on 或继续堆召回

3. **system path 的 model-visible contract 还不够强**
   - replace mode 能生成 contract，但模型没有稳定按 contract 回答
   - 需要把 allowed evidence、active version、forbidden boundary、fallback 等表达成更可执行的回答约束

4. **current path forbidden 风险很高**
   - `current` forbidden rate 为 `32.5%`
   - 这说明原始 system path 对旧版本、冲突、禁用信息的约束不足

5. **还缺失败归因**
   - replace mode 仍有 `19/40` answer miss
   - 需要拆分是评分表达问题、回答太泛、active version 没被识别、还是 contract 格式不够明确

## 当前目标

下一阶段目标不是继续扩召回，而是提升 system path 的 answer hit rate。

目标方向：

```text
把 P6o-14 safe_version_replace 的 52.5%
向 P6o-12 eval-only safe version-governed 的 97.5% 靠近，
同时保持 grounding 100.0%、forbidden 0.0%、token 不明显上升。
```

阶段性成功门槛建议：

| metric | target |
| --- | --- |
| answer_rate | 明显高于 P6o-14 的 `52.5%` |
| grounding_rate | 不低于 `100.0%` 或不低于当前 best |
| forbidden_rate | 保持 `0.0%` |
| contract_generation_success | `100.0%` |
| post_check_shadow | `100.0%` |
| token | 不明显上升 |
| repeat stability | 至少 repeat `3` 后仍稳定 |

## 后续计划方法

建议制定一个总 plan，覆盖 5 个方向，但分阶段执行，避免把多个变量混在一起。

### P6o-15：repeat stability + failure attribution

目的：

- 确认 P6o-14 的 `52.5%` 是否稳定
- 拆分 replace mode 的 `19/40` answer miss
- 判断问题是 answer guidance、contract rendering、scoring 口径，还是 evidence ordering

建议测试：

- `current` vs `safe_version_replace`
- common `20` + hard `20`
- repeat `3`
- baseline prompt
- 约 `240` real calls

输出：

- repeat-level answer/grounding/forbidden/token/latency
- per-case pass/fail matrix
- failure buckets：
  - evidence present but answer missed
  - active version not expressed
  - answer too generic
  - semantic answer but strict scorer miss
  - forbidden controlled but answer incomplete

### P6o-16：system-path answer guidance 强化

目的：

- 在不使用 fixture expected answer 的前提下，把 system-path evidence contract 表达得更可执行

可优化内容：

- allowed evidence summary 更短、更直接
- active version 明确标为 current truth
- stale / superseded 只作为边界，不暴露旧内容
- likely relevant facts 变成回答 checklist
- insufficient evidence fallback 更明确

注意：

- 不复制 fixture answer expectations
- 不引入 graph/all-on
- 不改变默认生产 `off`

### P6o-17：post-check retry shadow

目的：

- 不改变回答，只记录如果开启 retry 会触发哪些 case

shadow 信号：

- answer did not use allowed evidence
- active version missing
- answer too generic
- missing likely relevant fact
- forbidden boundary mentioned
- insufficient fallback missing

输出：

- would_retry_count
- retry_reason_counts
- would_retry_case_ids
- risk no-rise metrics

### P6o-18：memory block placement / format A/B

目的：

- 验证 system path 中 contract 的位置和格式是否影响 answer hit rate

候选格式：

- current memory block format
- compact evidence contract
- answer guidance block before memory details
- current truth first, details second

门槛：

- answer 提升
- forbidden 不上升
- token 不明显上升

### P6o-19：组合验证

目的：

- 把 P6o-16 到 P6o-18 中有效的改动组合起来
- 和 P6o-14 best (`safe_version_replace`) 做同场比较

建议矩阵：

- `current`
- `safe_version_replace`
- `safe_version_replace_guided`
- `safe_version_replace_guided_with_retry_shadow`

成功门槛：

- answer 明显高于 `52.5%`
- grounding 保持 `100.0%`
- forbidden 保持 `0.0%`
- token 不明显上升
- post-check 风险不增加

## P6o-15 执行结果更新

P6o-15 已完成，不再只是计划项。

新增报告：

- `my_md/memory_optimization/eval_reports/p6o15_system_path_repeat_stability_v1/system_path_safe_version_eval.json`
- `my_md/memory_optimization/eval_reports/p6o15_system_path_repeat_stability_v1/system_path_safe_version_eval.md`
- `my_md/memory_optimization/eval_reports/p6o15_system_path_repeat_stability_v1/system_path_failure_attribution.json`
- `my_md/memory_optimization/eval_reports/p6o15_system_path_repeat_stability_v1/system_path_failure_attribution.md`

测试方法：

- case pack：`standard`
- case 规模：common `20` + hard `20`
- unique case：`40`
- mode：`current` vs `safe_version_replace`
- repeat：`3`
- total calls：`240`
- provider：真实 LLM
- checkpoint：`/tmp/akashic-memory-p6o15-system-path-repeat-real/checkpoint.jsonl`
- memory 数据：fixture-seeded temporary system-path store
- 生产默认：仍为 `MemoryConfig.safe_version_governed_mode = "off"`
- review 后 checkpoint 可靠性修复：
  - resume 跳过 provider_error / timeout rows，以便重试失败调用
  - checkpoint-report-only 保留 provider_error / timeout rows，避免报告隐藏 partial failure
  - malformed trailing JSONL 不阻断恢复，并记录 `malformed_checkpoint_line_count`
  - append 时遇到 partial line 会先补换行

核心数据：

| mode | answer | grounding | forbidden | avg tokens | avg latency | contract success | post-check shadow |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `current` | `31/120 = 25.8333%` | `120/120 = 100.0%` | `47/120 = 39.1667%` | `5582.0` | `4627.15ms` | `0.0%` | `0.0%` |
| `safe_version_replace` | `88/120 = 73.3333%` | `120/120 = 100.0%` | `0/120 = 0.0%` | `5427.0833` | `3259.7667ms` | `100.0%` | `100.0%` |

Repeat stability：

| repeat | current answer | replace answer | current forbidden | replace forbidden |
| --- | ---: | ---: | ---: | ---: |
| `0` | `10/40 = 25.0%` | `29/40 = 72.5%` | `45.0%` | `0.0%` |
| `1` | `14/40 = 35.0%` | `29/40 = 72.5%` | `27.5%` | `0.0%` |
| `2` | `7/40 = 17.5%` | `30/40 = 75.0%` | `45.0%` | `0.0%` |

Failure attribution：

| bucket | count |
| --- | ---: |
| `passed` | `88` |
| `answer_rule_miss_required_terms` | `16` |
| `answer_rule_miss_any_group` | `13` |
| `language_failure` | `3` |

Movement：

| movement | count |
| --- | ---: |
| `baseline_failed_candidate_passed` | `64` |
| `baseline_passed_candidate_failed` | `7` |
| `baseline_passed_candidate_passed` | `24` |
| `baseline_failed_candidate_failed` | `25` |

结论：

- P6o-15 repeat gate 通过。
- P6o-14 的 `52.5%` 不是 system-path replace 的稳定上限；repeat 后 `safe_version_replace` 达到 `88/120 = 73.3333%`。
- grounding 保持 `100.0%`，forbidden 保持 `0.0%`，平均 token 和 latency 均低于 current。
- 当前 remaining miss 主要是 answer-rule required/any-group miss 和少量 language failure；问题仍然是 evidence-to-answer 表达，而不是召回不足。
- 下一步应进入 P6o-16 system-path answer guidance，不应先打开 graph/all-on，也不应改生产默认 `off`。

最终验证：

- focused safe-version/system-path slice：`30 passed`
- regression slice：`17 passed`
- `git diff --check` passed
- P6o-15 docs/report privacy gate passed

## 下一步建议

主线程恢复后，优先制定正式 plan：

```text
P6o-15 to P6o-19 system-path answer lift roadmap
```

但实际执行顺序应先做：

```text
P6o-15 repeat stability + failure attribution
```

原因：

- 当前 grounding 已经 `100.0%`
- answer 低的原因必须先分桶
- 直接改 prompt 或 contract 可能让 forbidden 重新上升
- 只有知道失败类型，P6o-16 的 answer guidance 才能有针对性

## 不应做的事

- 不要直接 graph/all-on
- 不要继续盲目扩大召回
- 不要直接生产默认开启
- 不要把 fixture expected answer 写进 runtime
- 不要直接开启真实 retry
- 不要只看 aggregate answer rate，必须看 per-case failure movement
