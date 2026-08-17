# Public Long Memory Eval Report

This report evaluates LongMemEval through the existing AgentLoop memory path.
It is a P5-only public benchmark run, not a P1-P5 ablation.

## Metrics

- `benchmark`: `longmemeval`
- `phase`: `phase_a`
- `profile`: `chain_tri_governed_answer_contract`
- `dataset_case_count`: `500`
- `sampled_case_count`: `50`
- `completed_call_count`: `50`
- `provider_error_count`: `0`
- `timeout_count`: `0`
- `malformed_checkpoint_line_count`: `0`
- `checkpoint_provenance_mismatch_count`: `0`
- `public_answer_pass_rate`: `54.0`
- `tool_call_style_output_count`: `0`
- `sent_evidence_gold_hit_count`: `28`
- `evidence_render_mode`: `answer_window`
- `effective_evidence_token_budget`: `3000`
- `scorer_unable_to_score_rate`: `0.0`
- `real_llm_enabled`: `True`
- `fake_provider_enabled`: `False`

## Category Distribution

| category | dataset | sampled |
| --- | ---: | ---: |
| abstention | 30 | 3 |
| knowledge-update | 72 | 7 |
| multi-session | 121 | 12 |
| single-session-assistant | 56 | 6 |
| single-session-preference | 30 | 3 |
| single-session-user | 64 | 6 |
| temporal-reasoning | 127 | 13 |

## Case Reviews

| source_id | category | provider_error | timeout | public_method | public_pass |
| --- | --- | ---: | ---: | --- | ---: |
| 60bf93ed_abs | abstention | False | False | deterministic_mismatch | False |
| 88432d0a_abs | abstention | False | False | deterministic_mismatch | False |
| c8090214_abs | abstention | False | False | deterministic_mismatch | False |
| 031748ae | knowledge-update | False | False | deterministic_mismatch | False |
| 0f05491a | knowledge-update | False | False | exact | True |
| 1cea1afa | knowledge-update | False | False | exact | True |
| 830ce83f | knowledge-update | False | False | deterministic_mismatch | False |
| 852ce960 | knowledge-update | False | False | exact | True |
| a2f3aa27 | knowledge-update | False | False | exact | True |
| e493bb7c | knowledge-update | False | False | deterministic_mismatch | False |
| 2e6d26dc | multi-session | False | False | exact | True |
| 60472f9c | multi-session | False | False | deterministic_mismatch | False |
| 61f8c8f8 | multi-session | False | False | exact | True |
| 6456829e | multi-session | False | False | deterministic_mismatch | False |
| 88432d0a | multi-session | False | False | exact | True |
| 8e91e7d9 | multi-session | False | False | exact | True |
| a3332713 | multi-session | False | False | exact | True |
| b3c15d39 | multi-session | False | False | deterministic_mismatch | False |
| bb7c3b45 | multi-session | False | False | exact | True |
| ef9cf60a | multi-session | False | False | exact | True |
| gpt4_2f91af09 | multi-session | False | False | exact | True |
| gpt4_7fce9456 | multi-session | False | False | deterministic_mismatch | False |
| 3249768e | single-session-assistant | False | False | exact | True |
| 3e321797 | single-session-assistant | False | False | exact | True |
| 51b23612 | single-session-assistant | False | False | exact | True |
| 8aef76bc | single-session-assistant | False | False | exact | True |
| ceb54acb | single-session-assistant | False | False | deterministic_mismatch | False |
| e982271f | single-session-assistant | False | False | exact | True |
| 0a34ad58 | single-session-preference | False | False | deterministic_mismatch | False |
| 54026fce | single-session-preference | False | False | deterministic_mismatch | False |
| a89d7624 | single-session-preference | False | False | deterministic_mismatch | False |
| 4100d0a0 | single-session-user | False | False | deterministic_mismatch | False |
| 6f9b354f | single-session-user | False | False | normalized | True |
| 86b68151 | single-session-user | False | False | exact | True |
| ad7109d1 | single-session-user | False | False | exact | True |
| caf9ead2 | single-session-user | False | False | exact | True |
| f4f1d8a4 | single-session-user | False | False | deterministic_mismatch | False |
| 0bc8ad93 | temporal-reasoning | False | False | deterministic_mismatch | False |
| a3838d2b | temporal-reasoning | False | False | exact | True |
| b46e15ee | temporal-reasoning | False | False | normalized | True |
| eac54add | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_1d80365e | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_2f56ae70 | temporal-reasoning | False | False | exact | True |
| gpt4_4929293a | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_61e13b3c | temporal-reasoning | False | False | exact | True |
| gpt4_6dc9b45b | temporal-reasoning | False | False | exact | True |
| gpt4_8279ba02 | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_93159ced | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_d6585ce8 | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_f420262d | temporal-reasoning | False | False | exact | True |
