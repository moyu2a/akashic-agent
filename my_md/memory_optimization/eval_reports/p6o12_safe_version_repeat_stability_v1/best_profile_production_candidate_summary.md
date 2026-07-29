# P6o-12 Best Profile Production Candidate Summary

本文件记录当前最佳 memory answer path 的测试方法、数据、结论和生产化边界，方便后续把 eval-only 方案迁移到 production shadow 时回溯。

## Current Best Candidate

当前最佳生产候选来自 eval-only profile：

```text
chain_tri_version_governed_answer_contract
```

它不是 production profile，不能直接原样上线。它的可迁移结构是：

```text
tri retrieval candidate pool
+ candidate governance
+ production-safe evidence contract
+ safe version boundary
+ answer post-check shadow
```

本轮明确不包含：

- graph retrieval;
- graph-all-on;
- rerank combo;
- chain_all_on;
- production memory write changes;
- production AgentLoop / prompt activation;
- real retry / fallback execution.

## Why Graph Is Parked

P6o-11 cross-report synthesis 已经说明 graph 有离线召回价值，但没有证明适合全局默认打开：

- graph offline recall: `1994/2000 = 99.7%`;
- delta vs memory base: `+16` recalled;
- route-governance small online graph answer: `13/40 = 32.5%`, same as memory base;
- online attribution graph answer failures: `236/320`;
- online attribution graph forbidden failures: `95/320`.

因此当前不做 graph-all-on。graph 后续只作为 routed graph 候选，用于 entity alias、multi-hop relation、source_ref missing、session boundary 或 version chain bridge 等明确 graph-needed 场景。

## Scheme Components

### 1. Tri Retrieval Candidate Pool

三路召回提供候选池。已有离线召回数据说明它是最强补漏路径：

- tri offline recall: `2000/2000 = 100.0%`;
- delta vs memory base: `+22`;
- miss reduction: `100.0%`.

但 raw tri 不能直接作为最终回答方案：

- route-governance small online raw tri answer: `17/40 = 42.5%`;
- P6o-5 raw tri answer: `15/40 = 37.5%`;
- tri grounding failure: `0`;
- tri answer failures remain high in attribution.

结论：tri 适合作为 candidate pool，不适合直接把 raw evidence 全量注入给模型。

### 2. Candidate Governance

候选治理把 tri evidence 分层处理：

- `delete`: 明确 forbidden / superseded / scope mismatch;
- `downgrade`: weak source_ref / low confidence;
- `requires_review`: conflict or insufficient evidence;
- `allow`: low-risk candidate.

目的不是减少召回本身，而是避免 raw recall expansion 把 forbidden、过期或跨 scope 的候选直接暴露给回答模型。

### 3. Production-Safe Evidence Contract

production-safe evidence contract 把治理后的候选转成模型可用结构，而不是让模型从杂乱 memory block 里自行判断。

核心字段：

- `allowed_evidence`;
- `likely_relevant_evidence`;
- `stale_warning`;
- `conflict_warning`;
- `active_version`;
- `insufficient_evidence_fallback`;
- `forbidden_boundary`.

P6o 系列的主要增益来自这层：问题已经不是证据有没有召回，而是证据到了以后模型是否用对。

### 4. Safe Version Boundary

safe version boundary 在不扩 recall 的前提下追加版本链和边界信息：

- active version;
- stale/conflict warning;
- superseded boundary;
- insufficient evidence fallback;
- forbidden/deleted boundary count.

P6o-8 后的安全修复要求：

- model-visible contract 不展示 raw `forbidden_boundary_ids`;
- model-visible contract 不展示 raw `deleted_evidence_ids`;
- raw ids 只保留在 `result.raw["answer_contract"]` 中供 post-check 使用。

### 5. Answer Post-Check Shadow

post-check 当前只观测，不改变回答，不触发 retry。

记录项：

- `needs_retry`;
- forbidden boundary inclusion;
- missing likely relevant context;
- stale evidence inclusion;
- conflict evidence inclusion;
- insufficient evidence fallback missing.

P6o-12 中 governed baseline 和 safe version-governed 的 post-check 风险计数全部为 `0`。

## Test Method

### P6o-12 Repeat Stability Matrix

测试目的：

```text
验证 P6o-10 的 40/40 是否稳定，还是一次性 stochastic run 效果。
```

测试配置：

- case pack: `standard`;
- unique cases: common `20` + hard `20` = `40`;
- prompt variant: `baseline`;
- repeats: `3`;
- profiles:
  - `chain_tri_governed_answer_contract`;
  - `chain_tri_version_governed_answer_contract`;
- expected calls: `40 * 2 * 3 = 240`;
- completed calls: `240`;
- provider errors: `0`;
- timeouts: `0`.

测试边界：

- no graph/all-on;
- no new eval profile;
- no production activation;
- no production AgentLoop / prompt / write path changes;
- reports are sanitized and do not include raw query, raw memory summary, full prompt, session text or full answer.

## Test Data

### Profile Totals

| profile | cases | answer | grounding | forbidden | avg tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| `chain_tri_governed_answer_contract` | `120` | `119/120 = 99.1667%` | `100.0%` | `0.0%` | `6122.6917` |
| `chain_tri_version_governed_answer_contract` | `120` | `117/120 = 97.5%` | `100.0%` | `0.0%` | `6030.3833` |

### Per-Repeat Counts

| profile | repeat 0 | repeat 1 | repeat 2 |
| --- | ---: | ---: | ---: |
| `chain_tri_governed_answer_contract` | `40/40` | `39/40` | `40/40` |
| `chain_tri_version_governed_answer_contract` | `39/40` | `39/40` | `39/40` |

### Post-Check Shadow

| profile | needs_retry | forbidden_boundary_included | missing_likely_relevant_context | stale_evidence_included | conflict_evidence_included |
| --- | ---: | ---: | ---: | ---: | ---: |
| `chain_tri_governed_answer_contract` | `0` | `0` | `0` | `0` | `0` |
| `chain_tri_version_governed_answer_contract` | `0` | `0` | `0` | `0` | `0` |

### Token Result

safe version-governed 平均 token 低于 governed baseline：

```text
6030.3833 - 6122.6917 = -92.3084 avg tokens
```

## Conclusion

当前效果足够支撑“初步闭环”：

1. 已经完成从问题归因到方案验证的闭环：
   - raw tri / graph grounding 高但 answer 和 forbidden 不稳定；
   - candidate governance + production-safe evidence contract 明显改善 answer 和 forbidden；
   - safe version boundary 进一步保留版本链边界并降低 token；
   - P6o-12 repeat stability 验证了当前 best path 的稳定性。
2. safe version-governed 稳定性 gate 通过：
   - total answer `117/120 = 97.5%`;
   - each repeat `39/40`;
   - grounding `100.0%`;
   - forbidden `0.0%`;
   - post-check risk all `0`.
3. P6o-10 的 `40/40` 不能解释为固定 100% 保证。
4. 更准确表述是：

```text
safe version-governed 在当前 40-case slice 上稳定处于 39/40 到 40/40 区间。
```

## Production Readiness Boundary

当前还不能直接生产默认开启，原因：

- unique cases 仍只有 `40`;
- profile 仍是 eval/shadow-only;
- 仍存在 fixture-protected 候选集合;
- post-check 只记录风险，不触发 production retry / fallback;
- 还没有真实自然流量 shadow 数据。

可进入的下一阶段不是 production activation，而是 production shadow design。

## Recommended Next Step

优先方向：

```text
P6o-13 production-shadow safe version-governed design
```

建议分阶段：

1. 把 eval-only profile 拆成 production-shadow 模块：
   - production tri candidate pool;
   - production candidate risk tiering;
   - production-safe evidence contract renderer;
   - safe version boundary metadata;
   - post-check shadow logger.
2. 只记录 shadow output，不改变 production answer。
3. 继续保留原 production answer 作为用户可见输出。
4. 对比 shadow contract 是否能在真实消息中生成完整 allowed evidence / active version / fallback / boundary。
5. 通过 targeted hard-slice 或 production-shadow sample 后，再讨论是否启用 retry/fallback。

当前不建议：

- graph-all-on;
- chain_all_on;
- 直接生产默认开启;
- 直接把 eval fixture expectation 搬到生产。
