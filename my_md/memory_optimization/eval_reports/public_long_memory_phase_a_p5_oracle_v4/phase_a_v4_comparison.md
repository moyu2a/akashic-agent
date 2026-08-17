# LongMemEval Phase A v4 Comparison

生成时间：2026-08-17

## Run Boundary

- 范围：LongMemEval Phase A 50 条分层样本，P5-only，`chain_tri_governed_answer_contract`。
- 调用形状：`50 * 1 * 1 * 1 = 50`，`prompt_variants=baseline`，`repeats=1`，`concurrency=1`。
- 证据渲染：`answer_window`，`long_evidence_token_limit=3000`，`reserved_prompt_token_budget=2000`，`answer_window_turns=2`，`model_context_window=8192`。
- v3 报告：`my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v3/public_long_memory_eval.json`
- v4 报告：`my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v4/public_long_memory_eval.json`
- v4 checkpoint：`my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v4/phase_a_checkpoint.jsonl`
- v4 request capture：`my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v4/workspace/public_long_memory_provider_requests/`
- v4 answer debug：`my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v4/workspace/public_long_memory_answer_debug/`

## Gate Result

| Gate | v4 result | Status |
| --- | ---: | --- |
| completed call count | 50 | PASS |
| actual call shape | `50 * 1 * 1 * 1 = 50` | PASS |
| provider errors | 0 | PASS |
| timeouts | 0 | PASS |
| malformed checkpoint lines | 0 | PASS |
| request capture files | 50 | PASS |
| answer debug files | 50 | PASS |
| tool-call style output | 0 | PASS |
| request snapshot mutation | 0 | PASS |
| request_time uses online run date | 0/50 | PASS |
| English-question language mismatch | 12/50 | PASS |

Phase A v4 达到进入 Phase B 前的工程 gate，但 Phase B 仍需用户显式确认后再执行。

## Metric Comparison

| Metric | v3 | v4 | Delta |
| --- | ---: | ---: | ---: |
| public answer pass | 21/50 | 27/50 | +6 |
| public answer pass rate | 42.0% | 54.0% | +12.0pp |
| provider error | 0 | 0 | 0 |
| timeout | 0 | 0 | 0 |
| tool-call style output | 0 | 0 | 0 |
| sent evidence gold hit | 27/50 | 28/50 | +1 |
| sent evidence gold hit rate | 54.0% | 56.0% | +2.0pp |
| scorer unable to score | 0 | 0 | 0 |
| request capture files | n/a | 50 | +50 |
| request snapshot mutation | n/a | 0 | 0 |
| language mismatch | 46/50 observed in v3 postmortem | 12/50 | -34 |

## Category Comparison

| Category | v3 pass | v4 pass | Delta |
| --- | ---: | ---: | ---: |
| abstention | 0/3 | 0/3 | 0 |
| knowledge-update | 4/7 | 4/7 | 0 |
| multi-session | 8/12 | 8/12 | 0 |
| single-session-assistant | 3/6 | 5/6 | +2 |
| single-session-preference | 0/3 | 0/3 | 0 |
| single-session-user | 2/6 | 4/6 | +2 |
| temporal-reasoning | 4/13 | 6/13 | +2 |

## Diagnostics

| Diagnostic | v4 count | Interpretation |
| --- | ---: | --- |
| literal_gold_hit | 28 | 证据文本直接包含 normalized gold。 |
| requires_reasoning_gold | 17 | 证据存在但需要时间、多跳、更新或偏好推理。 |
| supporting_fact_hit | 45 | 大多数失败不是召回完全缺失，而是答案格式、推理边界或 deterministic scorer 覆盖不足。 |
| abstention_intent_pass | 1 | 至少 1 条 abstention 是意图正确但 deterministic 文本未判过。 |
| semantic_review_needed | 18 | preference、长答案或同义表达需要人工/语义 judge 复核。 |
| language_mismatch | 12 | 全局中文诱导已明显下降，但仍有少量中文回答英文问题。 |

Failure attribution 聚合：

| Attribution | Count |
| --- | ---: |
| supported_but_deterministic_mismatch | 23 |
| semantic_review_needed | 18 |
| language_mismatch_scorer_false_negative_possible | 6 |
| abstention_intent_passed_deterministic_fail | 1 |

## Remaining Failure Shape

| Category | Main failure shape |
| --- | --- |
| abstention | 回答表达了证据不足，但 gold 是长句，deterministic scorer 不接受同义拒答。 |
| knowledge-update | 部分回答包含正确事实但附加旧/新状态解释，normalized contains 不稳定。 |
| multi-session | 数值题和长解释题常答对核心值，但 gold 接受形式更宽，deterministic scorer 偏窄。 |
| single-session-preference | 公开集 gold 是偏好 rubric，不是短事实答案，应走语义/人工 rubric 复核。 |
| single-session-user | 已从 2/6 提升到 4/6，剩余主要是中文回答英文问题造成 scorer false negative。 |
| temporal-reasoning | 日期锚点已修复，仍有 inclusive/exclusive day count 和长列表格式差异。 |

## Conclusion

v4 修复了 v3 的三个主要评测污染源：全局中文强制、数据集日期未进入 request_time、provider request 捕获被 answer 写回污染。线上指标也符合预期：通过率从 42.0% 提升到 54.0%，语言错配大幅下降，request_time 不再使用 2026-08-17 线上运行日。

建议：允许进入 Phase B 的前置条件已经满足，但 Phase B 应在用户确认后执行；同时应把 deterministic score 与 semantic/rubric review 分开汇报，尤其是 abstention、preference 和长答案题型。
