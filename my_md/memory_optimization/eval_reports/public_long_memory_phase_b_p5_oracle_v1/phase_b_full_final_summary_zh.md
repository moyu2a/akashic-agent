# LongMemEval Phase B Full P5-only 总结

## 执行结论

- 数据集：`my_md/memory_optimization/datasets/public_long_memory/longmemeval_oracle.json`
- dataset SHA256：`821a2034d219ab45846873dd14c14f12cfe7776e73527a483f9dac095d38620c`
- profile：`chain_tri_governed_answer_contract`
- prompt variants：`baseline`
- repeats：`1`
- phase：`phase_b`
- 调用形状：`500 * 1 * 1 * 1 = 500`
- 输出目录：`my_md/memory_optimization/eval_reports/public_long_memory_phase_b_p5_oracle_v1`

本轮只测试 P5-only 公开 LongMemEval full benchmark，不是 P1-P5 消融，也不比较不同治理方案。

## Infra Gate

| 指标 | 结果 |
| --- | ---: |
| completed_call_count | 500 |
| provider_error_count | 0 |
| timeout_count | 0 |
| malformed_checkpoint_line_count | 0 |
| checkpoint_provenance_mismatch_count | 0 |
| structured_evidence_snapshot_file_count | 500 |
| structured_evidence_snapshot_parse_error_count | 0 |
| provider_request_capture_file_count | 500 |
| provider_request_snapshot_clean_count | 500 |
| provider_request_snapshot_mutation_count | 0 |
| answer_debug_file_count | 500 |
| tool_call_style_output_count | 0 |

备注：首次 fresh run 中有 2 条 timeout，随后用同参数 `--resume` 补跑成功。因此最终报告 `timeout_count=0`，但 checkpoint 原始行数为 502，`skipped_from_checkpoint_count=498`，`fresh_checkpoint_valid=false` 是 resume 语义导致，不是最终结果污染。

## Raw Static 结果

| 指标 | 结果 |
| --- | ---: |
| strict_public_answer_pass_count | 289 |
| strict_public_answer_pass_rate | 57.8% |
| secondary_public_answer_pass_count | 303 |
| secondary_public_answer_pass_rate | 60.6% |
| scorer_unable_to_score_count | 0 |
| scorer_unable_to_score_rate | 0.0% |
| supporting_fact_hit_count | 449 |
| sent_evidence_gold_hit_count | 244 |
| final_stance_review_needed_count | 60 |
| semantic_review_needed_count | 181 |

raw strict/static scorer 只作为拆包和回归参考，不作为最终 correctness 结论。

## 外部 LLM Judge 结果

外部 Judge 已完成 `500/500` 条逐 case 审阅，原文已归档到 `phase_b_full_external_LLM_judge_raw.md`，机器可读索引见 `phase_b_full_external_LLM_judge_case_index.json`，详细中文汇总见 `phase_b_full_external_LLM_judge_summary_zh.md`。

| Judge 分类 | 数量 |
| --- | ---: |
| 合理 PASS | 277 |
| static FAIL 但 Judge 认为正确（false negative） | 180 |
| static PASS 但 Judge 认为模型错误（false positive） | 8 |
| static FAIL 且 Judge 认为明确模型错误 | 12 |
| 偏好型 partial，记录但不纳入主事实错误 | 14 |
| gold / 证据边界，主指标剔除 | 9 |

调整后主事实口径：

| 指标 | 结果 |
| --- | ---: |
| 原始 case 数 | 500 |
| gold / 证据边界剔除 | 9 |
| 有效分母 | 491 |
| true factual model error | 20 |
| 主事实口径错误率 | 4.07% |
| 主事实口径通过数 | 471 |
| 主事实口径通过率 | 95.93% |

保守口径如果把 `14` 条 preference partial 也算作错误，则错误数为 `34/491`，通过率为 `93.08%`。按当前复盘口径，preference gold / 偏好 partial 不作为主事实正确率的 blocker，但必须单独保留用于后续产品体验修复。

错误场景复盘已记录在 `phase_b_full_external_LLM_judge_summary_zh.md` 的“错误场景与稳定性判断”和“两类稳定错误的根因分析”章节。主要稳定问题是多 session 数量/金额汇总少算、knowledge-update 当前状态/版本选择错误；抽查代表 case 显示这些问题多数不是证据截断，而是聚合策略和 recency/currentness 版本决策不够硬。preference partial 属于产品体验优化项，static scorer false negative 属于评分器噪声。

## Language Metric

| 指标 | 结果 |
| --- | ---: |
| language_mismatch_count | 80 |
| mixed_language_mismatch_count | 49 |
| answer_language_contract_failed_count | 80 |

按当前复盘口径，语言错配单独记录；如果事实内容正确，不计入 adjusted factual/preference error。

## Category 分布

| category | count |
| --- | ---: |
| abstention | 30 |
| knowledge-update | 72 |
| multi-session | 121 |
| single-session-assistant | 56 |
| single-session-preference | 30 |
| single-session-user | 64 |
| temporal-reasoning | 127 |

## 人工审核包

- strict PASS 文档：`phase_b_full_passed_case_human_review_zh.md`
- strict FAIL 文档：`phase_b_full_failed_case_human_review_zh.md`
- case 索引：`phase_b_full_case_review_index.json`
- 外部 Judge 说明：`phase_b_full_LLM_judge_instructions_zh.md`
- 外部 Judge 原文归档：`phase_b_full_external_LLM_judge_raw.md`
- 外部 Judge 机器可读索引：`phase_b_full_external_LLM_judge_case_index.json`
- 外部 Judge 中文汇总：`phase_b_full_external_LLM_judge_summary_zh.md`
