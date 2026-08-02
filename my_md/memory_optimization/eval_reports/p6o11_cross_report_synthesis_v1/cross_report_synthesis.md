# P6o-11 Cross-Report Synthesis

本报告不重新调用 LLM，也不新增评分逻辑。它把已经完成的 graph / tri / rerank 早期评测、failure attribution，以及 P6o-5 到 P6o-10 的 governed evidence-contract 结果放到同一张分析口径里，回答：

```text
图召回和三路召回的收益，是否已经被 P6o governed / version-governed 方案覆盖？
下一步应该继续做 graph，还是先验证 version-governed 的稳定性？
```

## Data Sources

- 离线 answer/retrieval count V2:
  - `my_md/memory_optimization/eval_reports/memory_answer_retrieval_counts_eval.json`
  - `my_md/memory_optimization/eval_reports/memory_answer_retrieval_counts_eval.md`
- 早期 route-governance 真实 LLM 小矩阵:
  - `my_md/memory_optimization/eval_reports/route_governance_small_online_v1/memory_comprehensive_online_eval.json`
  - `my_md/memory_optimization/eval_reports/route_governance_small_online_v1/memory_comprehensive_online_eval.md`
- 大矩阵 online failure attribution:
  - `my_md/memory_optimization/eval_reports/online_failure_attribution/online_failure_attribution.json`
  - `my_md/memory_optimization/eval_reports/online_failure_attribution/online_failure_attribution.md`
- tri retrieval failure attribution:
  - `my_md/memory_optimization/eval_reports/tri_retrieval_failure_attribution_v1/tri_retrieval_failure_attribution.json`
  - `my_md/memory_optimization/eval_reports/tri_retrieval_failure_attribution_v1/tri_retrieval_failure_attribution.md`
- P6o governed-contract real LLM reports:
  - `my_md/memory_optimization/eval_reports/p6o5_governed_answer_contract_small_online_v1/`
  - `my_md/memory_optimization/eval_reports/p6o8_version_boundary_safe_presentation_small_online_v1/`
  - `my_md/memory_optimization/eval_reports/p6o9_governed_rerank_version_same_matrix_v1/`
  - `my_md/memory_optimization/eval_reports/p6o10_rerank_version_governed_combo_small_online_v1/`

## Boundary

- 这不是新实验，只是 cross-report synthesis。
- 不把不同日期、不同 profile 结构、不同 stochastic real LLM run 的结果当成严格同源 A/B。
- case-level overlap 只能作为归因线索，不能替代新一轮同场真实 LLM 比较。
- P6o profiles 仍是 eval/shadow-only，并且通过 fixture expected ids 保护候选集合；不能解释为生产自然流量。

## Layer 1: Offline Recall Gain

V2 离线计数回答的是“目标记忆有没有被找回来”。原始 memory 基线已经很强：`1978/2000 = 98.9%`。

| profile/module | recalled | recall | delta vs memory_base | miss reduction | interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| memory_base | `1978/2000` | `98.9%` | `0` | `0.0%` | 主基线，不使用关闭记忆夸大收益。 |
| tri_retrieval_only | `2000/2000` | `100.0%` | `+22` | `100.0%` | 最强、最稳定的召回补漏。 |
| graph_only | `1994/2000` | `99.7%` | `+16` | `72.7273%` | 有正向召回价值，但弱于三路召回。 |
| rerank_only | `1584/2000` | `79.2%` | `-394` | negative | 不适合单独当召回入口；应作为召回后的治理/排序层。 |
| version_provenance_only | `1000/2000` | `50.0%` | `-978` | negative | 不适合单独当召回入口；应作为版本/来源治理层。 |
| answer all_on | `1998/2000` | `99.9%` | `+20` | `90.9091%` | 有正向收益，但不如 tri 单项。 |

离线召回层结论：

- 三路召回是最明确的召回增强：补齐全部 `22` 条漏召。
- 图召回有价值：补回 `16` 条漏召，但低于三路。
- rerank、version/provenance 不能按“单独扩大召回池”评价；它们的价值在召回后的治理、排序、边界和可信度。
- all_on 不是当前最优，说明不能简单全开。

## Layer 2: Early Real LLM Answer-Level Matrix

route-governance small online matrix 使用 `40` unique cases、4 profiles、`160` completed real LLM calls。

| profile | answer | grounding | forbidden | avg tokens | interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| chain_memory_base | `13/40 = 32.5%` | `100.0%` | `15.0%` | `5503.7` | 原始回答弱，且 forbidden 非零。 |
| chain_tri_retrieval | `17/40 = 42.5%` | `100.0%` | `12.5%` | `5481.2` | 比 base 提升 `10` 点，但仍低。 |
| chain_graph_retrieval | `13/40 = 32.5%` | `100.0%` | `15.0%` | `5514.75` | 没超过 base。 |
| chain_rerank_injection | `18/40 = 45.0%` | `100.0%` | `10.0%` | `5426.55` | 早期 answer-level 最好，但仍只有 `45%`。 |

早期真实 LLM 层结论：

- tri / graph 都能保持 grounding `100%`，所以问题不是没有证据。
- graph 在这轮没有转化成 answer gain。
- rerank/injection 有一定 answer 和 forbidden 改善，但没有达到可生产化水平。
- 早期瓶颈已经从 recall 覆盖转移到 evidence injection、forbidden filtering 和 answer contract。

## Layer 3: Existing Failure Attribution

这部分已经做过，不需要重跑。

### Online Failure Attribution

`online_failure_attribution` 覆盖 `1920` 条真实 LLM case records、6 profiles。

| profile | answer failures | grounding failures | forbidden failures | primary issue |
| --- | ---: | ---: | ---: | --- |
| chain_memory_base | `185/320` | `12/320` | `39/320` | grounded_but_answer_failed |
| chain_tri_retrieval | `229/320` | `0/320` | `96/320` | grounded_but_answer_failed |
| chain_graph_retrieval | `236/320` | `0/320` | `95/320` | grounded_but_answer_failed |
| chain_rerank_injection | `193/320` | `0/320` | `31/320` | grounded_but_answer_failed |
| chain_version_provenance | `191/320` | `320/320` | `3/320` | grounding_only_failure |
| chain_all_on | `245/320` | `0/320` | `79/320` | grounded_but_answer_failed |

关键解释：

- tri 和 graph 的 grounding failure 都是 `0`，但 answer failure 很高。
- graph 的 forbidden failure 是 `95/320`，tri 是 `96/320`，说明 raw recall expansion 会带来噪声/禁止信息风险。
- rerank/injection 把 forbidden 降到 `31/320`，但 answer failure 仍有 `193/320`。
- 这支持 P6o 后续方向：不是继续扩大召回，而是治理候选和约束回答。

### Tri Retrieval Failure Attribution

`tri_retrieval_failure_attribution_v1` 覆盖 route-governance 小矩阵的 `40` 个 tri cases。

| metric | value |
| --- | ---: |
| `tri_case_count` | `40` |
| `tri_answer_fail_count` | `23` |
| `tri_grounding_fail_count` | `0` |
| `tri_forbidden_fail_count` | `5` |
| `baseline_failed_but_tri_passed_count` | `9` |
| `baseline_passed_but_tri_failed_count` | `5` |
| `tri_failed_but_rerank_passed_count` | `7` |

解释：

- 三路召回既能救活基线失败 case，也会让一部分原本答对的 case 回退。
- `tri_failed_but_rerank_passed_count = 7` 说明后续治理/重排有救场潜力，但不能解释为 rerank 单因素因果。
- 三路失败全部不是 grounding miss，而是证据到达后的回答规则、噪声和 forbidden 问题。

## Layer 4: Early Graph/Tri/Rerank Case-Level Patterns

route-governance 小矩阵里，tri / graph / rerank 的 pass/fail 关系如下。

### Tri vs Graph

| pattern | count |
| --- | ---: |
| tri fail / graph fail | `19` |
| tri fail / graph pass | `4` |
| tri pass / graph fail | `8` |
| tri pass / graph pass | `9` |

解释：

- graph 有 `4` 个 case 在 tri fail 时通过，说明 graph 有局部救场价值。
- 但 tri 有 `8` 个 case 在 graph fail 时通过，说明 graph 不是 tri 的全局替代。
- 两者同时 fail 有 `19` 个，说明问题大多不是单纯换召回通道可以解决。

### Memory Base vs Graph

| pattern | count |
| --- | ---: |
| base fail / graph fail | `20` |
| base fail / graph pass | `7` |
| base pass / graph fail | `7` |
| base pass / graph pass | `6` |

解释：

- graph 能救 `7` 个 base fail case，但也让 `7` 个 base pass case 回退。
- 这就是为什么 graph 不适合作为全局默认开关。

### Tri vs Rerank

| pattern | count |
| --- | ---: |
| tri fail / rerank fail | `16` |
| tri fail / rerank pass | `7` |
| tri pass / rerank fail | `6` |
| tri pass / rerank pass | `11` |

解释：

- rerank 有局部救场，但也有回退。
- rerank 的合理位置是治理/排序信号，而不是默认独立增强。

## Layer 5: P6o-5 to P6o-10 Governed Contract Results

P6o 系列回答的是另一个问题：当 recall 已经足够时，能否通过 candidate governance + production-safe evidence contract 让模型稳定用对证据。

| phase/profile | answer | grounding | forbidden | avg tokens | interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| P6o-5 tri retrieval | `15/40 = 37.5%` | `100.0%` | `12.5%` | `5518.825` | raw tri 仍然弱。 |
| P6o-5 candidate governance | `20/40 = 50.0%` | `100.0%` | `15.0%` | `5538.125` | 只过滤候选不够。 |
| P6o-5 oracle answer contract | `32/40 = 80.0%` | `100.0%` | `15.0%` | `5688.775` | 证明 answer constraints 有效，但 oracle 不可生产化。 |
| P6o-5 governed contract | `39/40 = 97.5%` | `100.0%` | `0.0%` | `6079.675` | 候选治理 + production-safe contract 产生质变。 |
| P6o-8 safe version-governed | `39/40 = 97.5%` | `100.0%` | `0.0%` | `6054.025` | 修复 boundary 表达后安全门通过。 |
| P6o-9 rerank-governed | `38/40 = 95.0%` | `100.0%` | `0.0%` | `6118.475` | 安全，但同场略低于 governed。 |
| P6o-9 safe version-governed | `38/40 = 95.0%` | `100.0%` | `0.0%` | `6021.55` | 安全，但同场略低于 governed。 |
| P6o-10 governed | `39/40 = 97.5%` | `100.0%` | `0.0%` | `6130.1` | 稳定强基线。 |
| P6o-10 rerank-governed | `39/40 = 97.5%` | `100.0%` | `0.0%` | `6131.95` | 安全但没有新增 answer gain。 |
| P6o-10 safe version-governed | `40/40 = 100.0%` | `100.0%` | `0.0%` | `6004.95` | 当前小矩阵最强。 |
| P6o-10 rerank + version combo | `39/40 = 97.5%` | `100.0%` | `0.0%` | `6036.7` | 安全且省 token，但不超过 version-only。 |

P6o 层结论：

- 与 graph/tri 早期 raw retrieval 相比，P6o 的提升是质变：从 `32.5%~45.0%` answer 区间提升到 `97.5%~100.0%`。
- 关键收益来自 candidate governance + evidence contract，而不是继续扩大召回池。
- safe version-governed 是当前最强 profile，但 P6o-9 到 P6o-10 有波动：`38/40` 到 `40/40`，需要 repeat stability。
- combo 安全但不是赢家，因此不能用它作为进入 all-on 的理由。

## Cross-Report Interpretation

### Graph 的位置

graph 不是无效。它在离线召回层有正向贡献：

- `1994/2000 = 99.7%`
- 相对 memory base 多命中 `16`
- 漏召减少 `72.7273%`

但 graph 没有证明自己适合全局默认打开：

- route-governance 小矩阵 answer 与 base 持平：`13/40 = 32.5%`
- online failure attribution 中 graph answer failures `236/320`
- graph forbidden failures `95/320`
- route 小矩阵中 graph 有救场，也有回退：base fail / graph pass `7`，base pass / graph fail `7`

因此 graph 的下一步应该是 routed graph，而不是 graph-all-on。

### Tri 的位置

tri 是召回补漏最强项，但 raw tri 不是最终 answer 方案：

- 离线 V2 召回：`2000/2000 = 100.0%`
- route 小矩阵 answer：`17/40 = 42.5%`
- P6o-5 raw tri answer：`15/40 = 37.5%`
- online failure attribution：tri grounding fail `0`，answer fail `229/320`

因此 tri 应作为 candidate pool 的入口，而不是直接把 raw tri evidence 注入给模型。

### Version 的位置

旧的 `chain_version_provenance` 单项在历史大矩阵里有 grounding 映射问题；不能直接代表当前 safe version-governed 的能力。

当前真正有价值的是 P6o-8 之后的 safe version-boundary evidence contract：

- 隐藏 model-visible raw forbidden/deleted ids；
- 保留 raw ids 给 post-check；
- safe version-governed 在 P6o-10 达到 `40/40 = 100.0%`；
- forbidden 和 post-check risk 都是 `0`；
- token 也最低。

因此 version 方向值得继续，但应该继续沿着 safe version-governed contract，而不是回到旧的 raw version_provenance profile。

### Rerank 的位置

rerank 早期能救部分 tri 失败：

- tri fail / rerank pass: `7`
- route 小矩阵最高 answer: `18/40 = 45.0%`

但在 P6o-9/P6o-10 中 rerank-governed 没有稳定超过 governed/version：

- P6o-9 rerank-governed `38/40`
- P6o-10 rerank-governed `39/40`
- P6o-10 combo `39/40`
- P6o-10 version-only `40/40`

因此 rerank 可以保留为候选排序信号，但不是当前主线 winner。

## Answer To The Original Question

“图召回的数据和 P6-P10 的数据一起对比”后的结论是：

1. 图召回在离线召回层有明确正向增益，但弱于三路召回。
2. 图召回在真实 LLM answer 层没有转化成稳定 answer gain，还带来 forbidden/noise 风险。
3. P6o-5 到 P6o-10 的 governed evidence-contract 方案解决的是 graph/tri 没解决的问题：证据到了以后如何让模型用对。
4. 当前最强不是 graph，也不是 combo，而是 P6o-10 safe version-governed。
5. graph 不应该废弃，但应该进入 routed graph：只在 graph-needed 场景，例如 entity alias、graph bridge、source_ref missing、session boundary、multi-hop relation 等场景打开。
6. 下一步不需要重做 failure attribution；已经做过。下一步应该是基于本 synthesis 制定一个更窄的 routed graph vs safe version-governed 计划，或者先做 safe version-governed repeat stability。

## Recommended Next Step

建议下一步不要叫 failure attribution，而叫：

```text
P6o-11 Routed Graph Decision Synthesis
```

执行方式：

1. 不重新跑 LLM，先从已有报告抽取 graph pass / tri fail、graph pass / governed fail、graph-only rescue 等 case。
2. 如果 graph 独有救场 case 足够明确，再设计 eval-only `chain_tri_version_routed_graph_governed_answer_contract`。
3. 如果 graph 独有救场不足，则优先做 safe version-governed repeat stability。
4. 不进入 graph-all-on，不进入 production activation。

当前更保守的推荐是：

```text
先做 safe version-governed repeat stability；
同时把 graph 作为 routed graph 候选，不做全局默认开关。
```
