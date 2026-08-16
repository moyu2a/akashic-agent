# Memory Governance Perturbed Eval Review

本文件记录 2026-08-17 扰动集 P1-P5 线上 real LLM 评测的测试方案、数据结论、正确/错误 case 的记录形式和代表样例。完整逐条复盘数据见同目录 `memory_governance_perturbed_case_review.jsonl`。

## Source Files

- Full perturbed dataset: `my_md/memory_optimization/datasets/memory_governance_eval_80_perturbed_full.jsonl`
- Lightweight perturbation index: `my_md/memory_optimization/datasets/memory_governance_eval_80_perturbed.jsonl`
- Online report JSON: `my_md/memory_optimization/eval_reports/memory_governance_perturbed_p1_p5_v1/memory_comprehensive_online_eval.json`
- Online report Markdown: `my_md/memory_optimization/eval_reports/memory_governance_perturbed_p1_p5_v1/memory_comprehensive_online_eval.md`
- Full case review JSONL: `my_md/memory_optimization/eval_reports/memory_governance_perturbed_p1_p5_v1/memory_governance_perturbed_case_review.jsonl`
- Checkpoint: `/tmp/akashic-memory-governance-perturbed-p1-p5-v1.checkpoint.jsonl`
- Answer debug source: `/tmp/akashic-memory-governance-perturbed-p1-p5-v1-workspace/answer_debug`

## Test Plan

| Item | Value |
| --- | --- |
| Dataset | 80 base memory governance cases, each expanded into 3 question perturbations |
| Perturbation templates | `请再确认一下：{question}`; `换个说法问，{question}`; `基于当前有效记忆，{question}` |
| Full-schema cases | 240 |
| Profiles | P1 `chain_tri_retrieval`; P2 `chain_tri_candidate_governance`; P3 `chain_tri_evidence_only`; P4 `chain_tri_answer_contract`; P5 `chain_tri_governed_answer_contract` |
| LLM calls | 240 cases x 5 profiles x 1 prompt variant x 1 repeat = 1200 |
| Prompt variant | `baseline` |
| Repeat | `1` |
| Deterministic args | `temperature=0`, `top_p=1`, `seed=42` |
| Real LLM | enabled |
| Fresh checkpoint | true |
| Provider errors | 0 |
| Timeouts | 0 |
| Malformed checkpoint rows | 0 |
| Checkpoint provenance mismatch | 0 |

Main command:

```bash
AKASHIC_RUN_LIVE_SMOKE=1 /home/jjh/git_work/akashic-agent/.venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-governance-perturbed-p1-p5-v1-workspace \
  --memory-governance-dataset my_md/memory_optimization/datasets/memory_governance_eval_80_perturbed_full.jsonl \
  --profile-ladder memory_governance_p1_p4 \
  --deterministic \
  --temperature 0 \
  --top-p 1 \
  --seed 42 \
  --prompt-variants baseline \
  --repeats 1 \
  --out-dir my_md/memory_optimization/eval_reports/memory_governance_perturbed_p1_p5_v1 \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --enable-real-llm \
  --checkpoint-jsonl /tmp/akashic-memory-governance-perturbed-p1-p5-v1.checkpoint.jsonl \
  --fresh-checkpoint \
  --include-answer-debug \
  --answer-debug-dir /tmp/akashic-memory-governance-perturbed-p1-p5-v1-workspace/answer_debug
```

## Data Conclusions

| Profile | Cases | Answer Success | Answer Rate | Forbidden Cases | Forbidden Rate | Grounding |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| P1 `chain_tri_retrieval` | 240 | 89 | 37.0833 | 55 | 22.9167 | 100.0 |
| P2 `chain_tri_candidate_governance` | 240 | 126 | 52.5 | 0 | 0.0 | 100.0 |
| P3 `chain_tri_evidence_only` | 240 | 61 | 25.4167 | 139 | 57.9167 | 100.0 |
| P4 `chain_tri_answer_contract` | 240 | 202 | 84.1667 | 37 | 15.4167 | 100.0 |
| P5 `chain_tri_governed_answer_contract` | 240 | 240 | 100.0 | 0 | 0.0 | 100.0 |

Overall:

| Metric | Value |
| --- | ---: |
| Total calls | 1200 |
| Unique cases | 240 |
| Correct profile-cases | 718 |
| Error profile-cases | 482 |
| Overall answer pass rate | 59.8333 |
| Overall forbidden violation rate | 19.25 |
| Overall grounding pass rate | 100.0 |
| Answer post-check `needs_retry_count` | 5 |

Interpretation:

- P5 在 240 条扰动 case 上保持 `240/240` answer success 和 `0` forbidden，说明“候选治理 + production-safe answer contract”对这三类问法扰动稳定。
- P2 的 forbidden 为 0，说明候选治理有效降低旧值/干扰项泄露，但 answer success 只有 52.5%，因为没有回答契约强制输出目标术语。
- P3 的 forbidden rate 最高，达到 57.9167%，继续验证“结构化证据单独暴露 forbidden/version boundary 会诱导模型复述边界词”的反直觉问题。
- P4 answer success 高于 P2/P3，但 forbidden 仍有 37 条，说明回答契约不能替代候选过滤。
- P1 在扰动集上 answer rate 为 37.0833%，forbidden rate 为 22.9167%，表现接近“只召回不是治理”的预期。

## Failure Type Summary

| Profile | Failed Rows | Failure Types | Root Cause |
| --- | ---: | --- | --- |
| P1 `chain_tri_retrieval` | 151 | `missing_expected_answer_term` 96; `missing_expected_answer_term_group` 96; `found_forbidden_answer_term` 55 | 无候选治理、无回答契约，旧值/干扰项进入上下文，且模型不稳定保留 expected term。 |
| P2 `chain_tri_candidate_governance` | 114 | `missing_expected_answer_term` 114; `missing_expected_answer_term_group` 114 | 过滤 forbidden 后仍缺少回答契约，模型可能泛化、转工具调用或省略精确值。 |
| P3 `chain_tri_evidence_only` | 179 | `found_forbidden_answer_term` 139; `missing_expected_answer_term` 44; `missing_expected_answer_term_group` 44 | 结构化列出 forbidden/version boundary，但没有禁止复述边界词的回答契约。 |
| P4 `chain_tri_answer_contract` | 38 | `found_forbidden_answer_term` 37; `missing_expected_answer_term` 1; `missing_expected_answer_term_group` 1 | 回答契约提升目标值命中，但旧值仍可能存在于上下文并被解释性复述。 |
| P5 `chain_tri_governed_answer_contract` | 0 | none | 候选治理先过滤风险证据，再用 production-safe contract 约束 allowed evidence 输出。 |

## Case Review JSONL Format

`memory_governance_perturbed_case_review.jsonl` 每行是一条 profile-case 复盘记录，覆盖 1200 条线上调用。字段形态如下：

| Field | Meaning |
| --- | --- |
| `review_class` | `correct` 或 `error` |
| `profile_name` | P1-P5 profile 名称 |
| `case_id` | 扰动 case id，例如 `mgov_001_p1` |
| `source_case_id` | 原始 80-case id，例如 `mgov_001` |
| `scenario` | 场景类型 |
| `user_question_original` | 扰动后的用户问题原文 |
| `memories_original` | synthetic memory 原文列表，含 id/status/confidence/summary/content |
| `expected_original` | should recall / should not recall / expected / forbidden 配置 |
| `model_answer_original` | 模型回答原文 |
| `evidence_block_text_original` | 注入给模型的 evidence/contract 文本 |
| `used_memory_ids` | 本 profile 实际使用的 memory ids |
| `answer_rule_passed` | deterministic answer rules 是否通过 |
| `memory_grounding_passed` | grounding 是否通过 |
| `forbidden_contains_violation_count` | forbidden 命中次数 |
| `failures` | failure type 列表 |
| `matched_expected_terms` | 命中的 expected term |
| `missing_expected_terms` | 缺失的 expected term |
| `root_causes` | profile/failure 对应的归因说明 |
| `case_record` | 原始 report 中的 compact case record |

## Correct Case Form

正确 case 的判定形式：

- `answer_rule_passed=true`
- `memory_grounding_passed=true`
- `failures=[]`
- 模型回答包含 expected term 或 expected any group
- 模型回答不包含 forbidden term
- `used_memory_ids` 包含当前 allowed memory，且不依赖 forbidden/stale memory

Representative correct sample:

| Field | Value |
| --- | --- |
| Profile | P5 `chain_tri_governed_answer_contract` |
| Case | `mgov_001_p1` |
| Scenario | `preference_replace` |
| Question | 请再确认一下：我现在在回答语言上的有效偏好是什么？ |
| Memories | `mgov_001_old[superseded,medium]`: 用户过去在回答语言上的偏好是英文<br>`mgov_001_new[active,high]`: 用户现在在回答语言上的偏好是中文<br>`mgov_001_distractor[active,low]`: 用户在相邻但不同主题上的记录是代码注释保持英文 |
| Expected / Forbidden | expected `中文`; forbidden `英文`; should recall `mgov_001_new`; should not recall `mgov_001_old`, `mgov_001_distractor` |
| Model answer | 确认了，当前生效的偏好是：回答用中文。 |
| Used memory | `mgov_001_new` |
| Result | pass; no failures |
| Why correct | 只使用当前 active memory，表达当前值 `中文`，没有复述 forbidden term `英文`。 |

## Error Case Forms

| Error Form | Typical Profile | 判定方式 | Root Cause |
| --- | --- | --- | --- |
| Forbidden explanation leak | P1/P3/P4 | 回答选对当前值，但解释旧值、干扰项或边界时复述 forbidden term | 风险证据仍在上下文，或结构化边界被模型当作解释材料。 |
| Missing exact expected term | P1/P2/P3 | 语义接近但没有命中 expected term 或 any group | 缺少回答契约，或模型省略编号/插入空格/泛化表达。 |
| Tool-call instead of final answer | P2/P1 | 回答转为查工具，没有直接输出目标答案 | 候选过滤不是答案生成契约，不能保证最终回答形态。 |
| Contract-only boundary leak | P4 | 有回答契约但无候选治理，回答中仍出现旧值 | 契约不能替代候选级风险证据过滤。 |

Representative error samples:

| Profile | Case | Error Form | Question | Expected / Forbidden | Model answer | Failure | Root Cause |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P1 `chain_tri_retrieval` | `mgov_001_p1` | Forbidden explanation leak | 请再确认一下：我现在在回答语言上的有效偏好是什么？ | expected `中文`; forbidden `英文` | 你现在的有效偏好是：**回答语言用中文**。<br><br>另一条“代码注释保持英文”是相邻主题的记录，指的是代码注释，不是回答语言，所以它不顶替这条。 | `found_forbidden_answer_term` | 只召回无候选治理，`mgov_001_distractor` 进入上下文后被复述。 |
| P2 `chain_tri_candidate_governance` | `mgov_002_p2` | Tool-call / missing expected | 换个说法问，我现在在输出格式上的有效偏好是什么？ | expected `中文1`; forbidden `英文1` | 我先查一下记忆库里关于输出格式偏好的条目。<br><br>`<tool_call>` 调用 `recall_memory`，query 为“用户在输出格式上的有效偏好是中文”。 | `missing_expected_answer_term`, `missing_expected_answer_term_group` | 候选治理过滤了 forbidden，但没有强制回答必须输出 `中文1`。 |
| P3 `chain_tri_evidence_only` | `mgov_001_p1` | Forbidden boundary replay | 请再确认一下：我现在在回答语言上的有效偏好是什么？ | expected `中文`; forbidden `英文` | 确认过了，你当前在回答语言上的有效偏好是**中文**。<br><br>之前那条“回答语言偏好英文”的记录已经失效了，所以现在按中文来。 | `found_forbidden_answer_term` | 结构化 evidence 暴露 forbidden/version boundary，但没有回答契约禁止复述边界词。 |
| P4 `chain_tri_answer_contract` | `mgov_071_p1` | Contract-only boundary leak | 请再确认一下：关于尚未确认的餐厅，我现在应该怎么回答？ | expected `无法确认`; forbidden `已确认` | 关于尚未确认的餐厅——应该回答“无法确认”，不要说“已确认”。 | `found_forbidden_answer_term` | 回答契约命中目标值，但旧值没有被候选治理移除，解释“不要说旧值”时复述 forbidden。 |

## Review Conclusion

扰动集结论与 80-case 主评测一致，但证据更强：P5 在 3 类问法扰动、240 个 case、1200-call 同表 profile ladder 中保持 100% answer success 和 0 forbidden。P2/P4 各自只解决治理链路的一半，P3 的反直觉失败继续存在。后续如果要写面试或论文式结论，应表述为：

> 在 240 条问法扰动样本上，最终组合 P5 `candidate governance + production-safe answer contract` 达到 100% answer success 和 0 forbidden；单独的候选治理、结构化证据或回答契约都不能同时保证答案命中和禁答边界。
