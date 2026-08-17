# LongMemEval Phase A Factorial Governance 评测总结

## 运行口径

- 数据集：`my_md/memory_optimization/datasets/public_long_memory/longmemeval_oracle.json`
- 抽样：Phase A 分层抽样 50 条，seed=`42`
- 调用形状：`50 * 8 * 1 * 1 = 400`
- 固定基线：三路召回 + RRF。
- 变量：C=候选治理，S=结构化证据，A=回答引导。
- 正确性：当前表格为 strict/static scorer；最终结论应以外部 LLM Judge 调整后为准。
- token：provider 返回的 prompt/completion/total tokens。
- 时延：runner 在 `AgentLoop.process_direct` 外围记录的端到端 wall-clock latency，不是 provider-only latency。

## Gate

- completed_call_count: `400`
- provider_error_count: `0`
- timeout_count: `0`
- malformed_checkpoint_line_count: `0`
- checkpoint_provenance_mismatch_count: `0`
- provider_request_capture_file_count: `400`
- structured_evidence_snapshot_file_count: `400`
- answer_debug_file_count: `400`

## Profile 结果表

| profile | C | S | A | static pass | prompt tokens | completion tokens | total tokens | avg total/call | avg latency ms | p50 latency ms | p95 latency ms | total delta vs tri_rrf | latency delta vs tri_rrf |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| tri_rrf | 0 | 0 | 0 | 58.0 | 593933 | 36287 | 630220 | 12604.4 | 6915.64 | 5335.0 | 17023.2 | 0 | 0.0 |
| tri_rrf_candidate | 1 | 0 | 0 | 58.0 | 594733 | 36086 | 630819 | 12616.38 | 6658.18 | 4919.0 | 15601.7 | 599 | -257.46 |
| tri_rrf_structured | 0 | 1 | 0 | 58.0 | 597162 | 46465 | 643627 | 12872.54 | 8449.2 | 6226.5 | 24759.7 | 13407 | 1533.56 |
| tri_rrf_answer | 0 | 0 | 1 | 58.0 | 599833 | 39562 | 639395 | 12787.9 | 7016.94 | 5096.0 | 17973.5 | 9175 | 101.3 |
| tri_rrf_candidate_structured | 1 | 1 | 0 | 58.0 | 597962 | 35471 | 633433 | 12668.66 | 6781.4 | 4947.0 | 20238.7 | 3213 | -134.24 |
| tri_rrf_candidate_answer | 1 | 0 | 1 | 58.0 | 600633 | 39027 | 639660 | 12793.2 | 6955.92 | 5014.5 | 19438.2 | 9440 | 40.28 |
| tri_rrf_structured_answer | 0 | 1 | 1 | 58.0 | 603088 | 35494 | 638582 | 12771.64 | 6731.0 | 5130.5 | 15110.6 | 8362 | -184.64 |
| tri_rrf_candidate_structured_answer | 1 | 1 | 1 | 58.0 | 390491 | 26827 | 417318 | 8346.36 | 4858.34 | 3879.5 | 10811.55 | -212902 | -2057.3 |

## 初步观察

- static pass rate 在 8 个 profile 上均为 `58.0%`，说明本轮 strict 字符串 scorer 不足以区分治理模块正确性，必须走外部 Judge。
- full profile `tri_rrf_candidate_structured_answer` 的 total tokens 为 `417318`，相对 `tri_rrf` 的 `630220` 减少 `212902`。
- full profile 平均端到端时延 `4858.34ms`，相对 `tri_rrf` 的 `6915.64ms` 下降 `2057.3`ms。
- 当前 static FAIL 中有大量 abstention/语义等价/回答边界问题，不能直接当作真实错误。
- 下一步应对 `phase_a_factorial_case_reviews.jsonl` 进行外部 LLM Judge，按 profile 重新计算 adjusted pass rate。

## 产物

- 原始 JSON 报告：`public_long_memory_eval.json`
- Markdown 报告：`public_long_memory_eval.md`
- checkpoint：`phase_a_factorial_checkpoint.jsonl`
- 机器可读 case 明细：`phase_a_factorial_case_reviews.jsonl`
- CSV 索引：`phase_a_factorial_case_index.csv`
- static PASS 审阅文档：`phase_a_factorial_static_passed_case_human_review_zh.md`
- static FAIL 审阅文档：`phase_a_factorial_static_failed_case_human_review_zh.md`
- 外部 Judge 指令：`phase_a_factorial_LLM_judge_instructions_zh.md`
