# Answer Selection Follow-up Handoff

## Context

本文件记录 side conversation 中关于 memory next / P6o-18 后续方向的讨论，方便回到主线继续推进。

当前判断来自已讨论的 P6o-18 数据：

- 最佳当前组合：`safe_version_replace_guided`。
- answer：`31/40 = 77.5%`。
- grounding：`100.0%`。
- forbidden：`0.0%`。
- provider error：`0`。
- timeout：`0`。

核心结论：证据已经召回并进入回答上下文，安全边界和 grounding 基本有效；剩余瓶颈不是继续扩大召回，而是模型在 allowed evidence 中选择正确证据、执行版本/冲突优先级，并按评测要求表达答案。

## Failure Shape

`safe_version_replace_guided` 剩余 `9/40` 未命中：

| bucket | count | meaning |
| --- | ---: | --- |
| required-term miss | 5 | 答案没有包含评测要求的关键术语或明确事实 |
| any-group miss | 2 | 答案覆盖了部分信息，但没有命中某组可接受表达 |
| language failure | 2 | 没有稳定按中文要求输出 |

已排除的方向：

- 不是 infra 问题：provider error `0`，timeout `0`。
- 不是安全边界问题：forbidden `0.0%`，版本边界和 forbidden boundary 没有泄漏。
- 不是 grounding 问题：grounding `100.0%`，回答基于 allowed evidence。
- 不是单纯召回不足：当前失败更像 evidence-to-answer / answer-selection 问题。

## Why Existing Variants Were Not Enough

| variant | result | conclusion |
| --- | --- | --- |
| `safe_version_replace` | `24/40 = 60.0%` | 缺少 answer guidance，模型更容易漏掉关键表达 |
| `safe_version_replace_guided` | `31/40 = 77.5%` | 当前最好，仍有 `9` 个 expression/selection miss |
| `safe_version_replace_structured_guided` | `31/40 = 77.5%` | 修复 `4` 个 guided miss，但也弄丢 `4` 个 guided pass，且 token/latency 更高 |
| `safe_version_replace_near_query_block` | `23/40 = 57.5%` | 过度强化 near-query 局部证据，丢失全局版本/冲突判断 |

当前不建议继续推进 `structured_guided` 和 `near_query_block` 的现有 wording。

## Candidate Solutions Not Fully Tried Yet

### 1. Selected Evidence Contract

目标：不要只告诉模型有哪些 allowed evidence，而是显式要求本轮答案选择哪些 evidence。

候选结构：

```text
selected_evidence:
  - id: m3
    status: active
    answer_role: must_use

ignored_evidence:
  - id: m1
    status: superseded
    ignore_reason: replaced_by_active_version

final_answer_rule:
  - answer from selected active evidence only
  - do not answer from superseded/conflict/stale evidence
```

预期解决：

- 版本优先没有被执行。
- allowed evidence 太多时模型选错。
- active version 被提到但没有成为最终答案。

注意边界：不能把 fixture oracle 直接放进生产 contract；生产只能用 active version、source status、scope match、conflict/stale marker 等真实信号生成。

### 2. Answer Verifier + Retry Shadow

目标：回答生成后做轻量校验，先 shadow 记录，不直接改变生产回答。

检查项：

- 是否使用 selected/allowed evidence。
- 是否遗漏 active version。
- 是否引用 forbidden / superseded / conflict memory。
- 是否缺 required-term 类关键事实。
- 是否语言不符合要求。
- 是否需要 retry。

下一步可以先做 shadow：

```text
retrieval -> governance -> evidence contract -> answer -> verifier shadow
```

之后再评估是否进入：

```text
answer -> verifier failed -> retry once -> final
```

预期解决：

- 一次回答偶发漏选正确 evidence。
- 答案语义接近但表达不稳定。
- 中文输出约束不稳定。

### 3. Routed Prompt Policy

目标：不要一套 guided prompt 覆盖所有 case，而是按风险/场景路由 answer policy。

候选路由：

| route | when | guidance focus |
| --- | --- | --- |
| preference recall | 用户偏好/工具偏好 | 必须回答当前偏好，避免泛化 |
| version chain | 有 replacement / active version | 使用 active version，忽略 superseded |
| stale/conflict | 有 stale 或 conflict warning | 给出当前可确认结论，必要时说明证据不足 |
| graph bridge | 需要桥接关系 | 使用桥接证据，但不全局打开 graph |
| language enforcement | 中文 case | 强制中文、短句、直接回答 |

预期解决：

- preference recall required-term miss。
- version/stale answer choice 不稳定。
- graph bridge case 证据到了但没选中。
- language failure。

### 4. Two-stage Answering / Schema First

目标：先让模型做结构化选择，再生成自然语言答案。

候选流程：

```text
stage 1: select evidence and facts
stage 2: render final user-facing answer
```

候选 schema：

```json
{
  "selected_evidence_ids": [],
  "active_version_used": true,
  "ignored_superseded_ids": [],
  "final_answer_facts": [],
  "insufficient_evidence": false
}
```

预期解决：

- 模型直接自然语言回答时跳过关键证据。
- 评测 required term 被漏掉。
- 多条相似证据下选择不稳定。

风险：

- token 和 latency 可能上升。
- schema 解析和失败恢复要先做 shadow。

### 5. Targeted Prompt Adjustment on Guided Misses

目标：只围绕 `safe_version_replace_guided` 的 `9` 个 miss 做小矩阵，不再盲目扩大 prompt。

重点 case 类型：

- preference recall。
- version chain / stale sleep。
- graph bridge。
- language failure。

候选小矩阵：

| candidate | purpose |
| --- | --- |
| active-preference wording | 要求偏好类回答直接给当前偏好 |
| version-final-answer wording | 要求版本链场景只输出 active/current 结论 |
| selected-evidence-first wording | 要求先内部选定 selected evidence |
| language-lock wording | 中文输出 hard constraint |

### 6. Graph Routed-on

目标：保留 graph 作为 routed candidate，不全局打开。

适用场景：

- 明确 graph-needed。
- hard graph bridge。
- 需要跨条记忆桥接的 case。

不建议：

- graph-all-on。
- 用 graph 解决所有 answer miss。

原因：当前 P6o-18 主要瓶颈不是召回；graph 优先级低于 answer-selection/verifier。

## Recommended Next Sequence

建议不要一次做生产化，分三步：

1. **P6o-19 selected evidence contract shadow**
   - 只生成 selected evidence / ignored evidence / final answer rule。
   - 不改变回答。
   - 对 `40` case 跑 fake smoke + real small A/B report-only。

2. **P6o-20 verifier shadow**
   - 在 `safe_version_replace_guided` 后记录 verifier 结果。
   - 重点看 guided 的 `9` 个 miss 是否能被 verifier 标出。
   - 不做 retry，不改变生产回答。

3. **P6o-21 targeted retry / routed prompt pilot**
   - 只在 verifier 标记失败的 case 上试 retry 或 routed prompt。
   - 先用 common `20` + hard `20`，不要扩大。
   - 成功门槛：answer 提升，grounding 保持 `100%`，forbidden 保持 `0%`，token 不明显上升。

## Non-goals For Next Step

- 不继续推进当前 `near_query_block` wording。
- 不把 `structured_guided` 升为默认。
- 不打开 graph-all-on。
- 不扩大 case pack。
- 不直接改变生产默认：`safe_version_governed_mode` 仍应保持 `off`，直到 shadow telemetry 证明可控。

