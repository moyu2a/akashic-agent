# Public Long Memory Eval Report

This report evaluates LongMemEval through the existing AgentLoop memory path.
It is a P5-only public benchmark run, not a P1-P5 ablation.

## Metrics

- `benchmark`: `longmemeval`
- `phase`: `phase_a`
- `profile`: `tri_rrf_candidate_structured_answer`
- `dataset_case_count`: `500`
- `sampled_case_count`: `50`
- `completed_call_count`: `400`
- `provider_error_count`: `0`
- `timeout_count`: `0`
- `malformed_checkpoint_line_count`: `0`
- `checkpoint_provenance_mismatch_count`: `0`
- `public_answer_pass_rate`: `58.0`
- `tool_call_style_output_count`: `0`
- `sent_evidence_gold_hit_count`: `224`
- `language_mismatch_count`: `40`
- `mixed_language_mismatch_count`: `32`
- `answer_language_contract_failed_count`: `40`
- `missed_salient_context_possible_count`: `32`
- `final_stance_review_needed_count`: `72`
- `evidence_render_mode`: `answer_window`
- `effective_evidence_token_budget`: `3000`
- `structured_evidence_snapshot_file_count`: `400`
- `structured_evidence_snapshot_parse_error_count`: `0`
- `scorer_unable_to_score_rate`: `0.0`
- `real_llm_enabled`: `True`
- `fake_provider_enabled`: `False`

## Profile Accuracy And Cost

| profile | cases | static_pass_rate | prompt_tokens | completion_tokens | total_tokens | avg_prompt | avg_completion | avg_total | avg_latency_ms | p50_latency_ms | p95_latency_ms | total_token_delta_vs_tri_rrf | avg_latency_delta_vs_tri_rrf |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| tri_rrf | 50 | 58.0 | 593933 | 36287 | 630220 | 11878.66 | 725.74 | 12604.4 | 6915.64 | 5335.0 | 17023.2 | 0 | 0.0 |
| tri_rrf_candidate | 50 | 58.0 | 594733 | 36086 | 630819 | 11894.66 | 721.72 | 12616.38 | 6658.18 | 4919.0 | 15601.7 | 599 | -257.46 |
| tri_rrf_structured | 50 | 58.0 | 597162 | 46465 | 643627 | 11943.24 | 929.3 | 12872.54 | 8449.2 | 6226.5 | 24759.7 | 13407 | 1533.56 |
| tri_rrf_answer | 50 | 58.0 | 599833 | 39562 | 639395 | 11996.66 | 791.24 | 12787.9 | 7016.94 | 5096.0 | 17973.5 | 9175 | 101.3 |
| tri_rrf_candidate_structured | 50 | 58.0 | 597962 | 35471 | 633433 | 11959.24 | 709.42 | 12668.66 | 6781.4 | 4947.0 | 20238.7 | 3213 | -134.24 |
| tri_rrf_candidate_answer | 50 | 58.0 | 600633 | 39027 | 639660 | 12012.66 | 780.54 | 12793.2 | 6955.92 | 5014.5 | 19438.2 | 9440 | 40.28 |
| tri_rrf_structured_answer | 50 | 58.0 | 603088 | 35494 | 638582 | 12061.76 | 709.88 | 12771.64 | 6731.0 | 5130.5 | 15110.6 | 8362 | -184.64 |
| tri_rrf_candidate_structured_answer | 50 | 58.0 | 390491 | 26827 | 417318 | 7809.82 | 536.54 | 8346.36 | 4858.34 | 3879.5 | 10811.55 | -212902 | -2057.3 |

## Cost Metric Definitions

- `prompt_tokens`: provider-reported input tokens for system prompt, user question, and rendered evidence.
- `completion_tokens`: provider-reported output tokens.
- `total_tokens`: provider-reported prompt plus completion tokens.
- `latency_ms`: runner-observed per-call end-to-end wall-clock latency measured around `AgentLoop.process_direct`; it is not provider-only latency.
- `p50_latency_ms` and `p95_latency_ms`: percentile latency across calls in the same profile.

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
| 60bf93ed_abs | abstention | False | False | deterministic_mismatch | False |
| 60bf93ed_abs | abstention | False | False | deterministic_mismatch | False |
| 60bf93ed_abs | abstention | False | False | deterministic_mismatch | False |
| 60bf93ed_abs | abstention | False | False | deterministic_mismatch | False |
| 60bf93ed_abs | abstention | False | False | deterministic_mismatch | False |
| 60bf93ed_abs | abstention | False | False | deterministic_mismatch | False |
| 60bf93ed_abs | abstention | False | False | deterministic_mismatch | False |
| 88432d0a_abs | abstention | False | False | deterministic_mismatch | False |
| 88432d0a_abs | abstention | False | False | deterministic_mismatch | False |
| 88432d0a_abs | abstention | False | False | deterministic_mismatch | False |
| 88432d0a_abs | abstention | False | False | deterministic_mismatch | False |
| 88432d0a_abs | abstention | False | False | deterministic_mismatch | False |
| 88432d0a_abs | abstention | False | False | deterministic_mismatch | False |
| 88432d0a_abs | abstention | False | False | deterministic_mismatch | False |
| 88432d0a_abs | abstention | False | False | deterministic_mismatch | False |
| c8090214_abs | abstention | False | False | deterministic_mismatch | False |
| c8090214_abs | abstention | False | False | deterministic_mismatch | False |
| c8090214_abs | abstention | False | False | deterministic_mismatch | False |
| c8090214_abs | abstention | False | False | deterministic_mismatch | False |
| c8090214_abs | abstention | False | False | deterministic_mismatch | False |
| c8090214_abs | abstention | False | False | deterministic_mismatch | False |
| c8090214_abs | abstention | False | False | deterministic_mismatch | False |
| c8090214_abs | abstention | False | False | deterministic_mismatch | False |
| 031748ae | knowledge-update | False | False | deterministic_mismatch | False |
| 031748ae | knowledge-update | False | False | deterministic_mismatch | False |
| 031748ae | knowledge-update | False | False | deterministic_mismatch | False |
| 031748ae | knowledge-update | False | False | deterministic_mismatch | False |
| 031748ae | knowledge-update | False | False | deterministic_mismatch | False |
| 031748ae | knowledge-update | False | False | deterministic_mismatch | False |
| 031748ae | knowledge-update | False | False | deterministic_mismatch | False |
| 031748ae | knowledge-update | False | False | deterministic_mismatch | False |
| 0f05491a | knowledge-update | False | False | exact | True |
| 0f05491a | knowledge-update | False | False | exact | True |
| 0f05491a | knowledge-update | False | False | exact | True |
| 0f05491a | knowledge-update | False | False | exact | True |
| 0f05491a | knowledge-update | False | False | exact | True |
| 0f05491a | knowledge-update | False | False | exact | True |
| 0f05491a | knowledge-update | False | False | exact | True |
| 1cea1afa | knowledge-update | False | False | exact | True |
| 0f05491a | knowledge-update | False | False | exact | True |
| 1cea1afa | knowledge-update | False | False | exact | True |
| 1cea1afa | knowledge-update | False | False | exact | True |
| 1cea1afa | knowledge-update | False | False | exact | True |
| 1cea1afa | knowledge-update | False | False | exact | True |
| 1cea1afa | knowledge-update | False | False | exact | True |
| 1cea1afa | knowledge-update | False | False | exact | True |
| 1cea1afa | knowledge-update | False | False | exact | True |
| 830ce83f | knowledge-update | False | False | exact | True |
| 830ce83f | knowledge-update | False | False | exact | True |
| 830ce83f | knowledge-update | False | False | exact | True |
| 830ce83f | knowledge-update | False | False | exact | True |
| 830ce83f | knowledge-update | False | False | exact | True |
| 830ce83f | knowledge-update | False | False | exact | True |
| 830ce83f | knowledge-update | False | False | exact | True |
| 852ce960 | knowledge-update | False | False | exact | True |
| 830ce83f | knowledge-update | False | False | exact | True |
| 852ce960 | knowledge-update | False | False | exact | True |
| 852ce960 | knowledge-update | False | False | exact | True |
| 852ce960 | knowledge-update | False | False | exact | True |
| 852ce960 | knowledge-update | False | False | exact | True |
| 852ce960 | knowledge-update | False | False | exact | True |
| 852ce960 | knowledge-update | False | False | exact | True |
| a2f3aa27 | knowledge-update | False | False | exact | True |
| 852ce960 | knowledge-update | False | False | exact | True |
| a2f3aa27 | knowledge-update | False | False | exact | True |
| a2f3aa27 | knowledge-update | False | False | exact | True |
| a2f3aa27 | knowledge-update | False | False | exact | True |
| a2f3aa27 | knowledge-update | False | False | exact | True |
| a2f3aa27 | knowledge-update | False | False | exact | True |
| a2f3aa27 | knowledge-update | False | False | exact | True |
| a2f3aa27 | knowledge-update | False | False | exact | True |
| e493bb7c | knowledge-update | False | False | deterministic_mismatch | False |
| e493bb7c | knowledge-update | False | False | deterministic_mismatch | False |
| e493bb7c | knowledge-update | False | False | deterministic_mismatch | False |
| e493bb7c | knowledge-update | False | False | deterministic_mismatch | False |
| e493bb7c | knowledge-update | False | False | deterministic_mismatch | False |
| e493bb7c | knowledge-update | False | False | deterministic_mismatch | False |
| e493bb7c | knowledge-update | False | False | deterministic_mismatch | False |
| e493bb7c | knowledge-update | False | False | deterministic_mismatch | False |
| 2e6d26dc | multi-session | False | False | exact | True |
| 2e6d26dc | multi-session | False | False | exact | True |
| 2e6d26dc | multi-session | False | False | exact | True |
| 2e6d26dc | multi-session | False | False | exact | True |
| 2e6d26dc | multi-session | False | False | exact | True |
| 2e6d26dc | multi-session | False | False | exact | True |
| 2e6d26dc | multi-session | False | False | exact | True |
| 2e6d26dc | multi-session | False | False | exact | True |
| 60472f9c | multi-session | False | False | deterministic_mismatch | False |
| 60472f9c | multi-session | False | False | deterministic_mismatch | False |
| 60472f9c | multi-session | False | False | deterministic_mismatch | False |
| 60472f9c | multi-session | False | False | deterministic_mismatch | False |
| 60472f9c | multi-session | False | False | deterministic_mismatch | False |
| 60472f9c | multi-session | False | False | deterministic_mismatch | False |
| 60472f9c | multi-session | False | False | deterministic_mismatch | False |
| 60472f9c | multi-session | False | False | deterministic_mismatch | False |
| 61f8c8f8 | multi-session | False | False | deterministic_mismatch | False |
| 61f8c8f8 | multi-session | False | False | deterministic_mismatch | False |
| 61f8c8f8 | multi-session | False | False | deterministic_mismatch | False |
| 61f8c8f8 | multi-session | False | False | deterministic_mismatch | False |
| 61f8c8f8 | multi-session | False | False | deterministic_mismatch | False |
| 61f8c8f8 | multi-session | False | False | deterministic_mismatch | False |
| 61f8c8f8 | multi-session | False | False | deterministic_mismatch | False |
| 61f8c8f8 | multi-session | False | False | deterministic_mismatch | False |
| 6456829e | multi-session | False | False | deterministic_mismatch | False |
| 6456829e | multi-session | False | False | deterministic_mismatch | False |
| 6456829e | multi-session | False | False | deterministic_mismatch | False |
| 6456829e | multi-session | False | False | deterministic_mismatch | False |
| 6456829e | multi-session | False | False | deterministic_mismatch | False |
| 6456829e | multi-session | False | False | deterministic_mismatch | False |
| 6456829e | multi-session | False | False | deterministic_mismatch | False |
| 6456829e | multi-session | False | False | deterministic_mismatch | False |
| 88432d0a | multi-session | False | False | exact | True |
| 88432d0a | multi-session | False | False | exact | True |
| 88432d0a | multi-session | False | False | exact | True |
| 88432d0a | multi-session | False | False | exact | True |
| 88432d0a | multi-session | False | False | exact | True |
| 88432d0a | multi-session | False | False | exact | True |
| 88432d0a | multi-session | False | False | exact | True |
| 8e91e7d9 | multi-session | False | False | exact | True |
| 8e91e7d9 | multi-session | False | False | exact | True |
| 88432d0a | multi-session | False | False | exact | True |
| 8e91e7d9 | multi-session | False | False | exact | True |
| 8e91e7d9 | multi-session | False | False | exact | True |
| 8e91e7d9 | multi-session | False | False | exact | True |
| 8e91e7d9 | multi-session | False | False | exact | True |
| 8e91e7d9 | multi-session | False | False | exact | True |
| a3332713 | multi-session | False | False | exact | True |
| 8e91e7d9 | multi-session | False | False | exact | True |
| a3332713 | multi-session | False | False | exact | True |
| a3332713 | multi-session | False | False | exact | True |
| a3332713 | multi-session | False | False | exact | True |
| a3332713 | multi-session | False | False | exact | True |
| a3332713 | multi-session | False | False | exact | True |
| a3332713 | multi-session | False | False | exact | True |
| a3332713 | multi-session | False | False | exact | True |
| b3c15d39 | multi-session | False | False | deterministic_mismatch | False |
| b3c15d39 | multi-session | False | False | deterministic_mismatch | False |
| b3c15d39 | multi-session | False | False | deterministic_mismatch | False |
| b3c15d39 | multi-session | False | False | deterministic_mismatch | False |
| b3c15d39 | multi-session | False | False | deterministic_mismatch | False |
| b3c15d39 | multi-session | False | False | deterministic_mismatch | False |
| b3c15d39 | multi-session | False | False | deterministic_mismatch | False |
| b3c15d39 | multi-session | False | False | deterministic_mismatch | False |
| bb7c3b45 | multi-session | False | False | exact | True |
| bb7c3b45 | multi-session | False | False | exact | True |
| bb7c3b45 | multi-session | False | False | exact | True |
| bb7c3b45 | multi-session | False | False | exact | True |
| bb7c3b45 | multi-session | False | False | exact | True |
| bb7c3b45 | multi-session | False | False | exact | True |
| bb7c3b45 | multi-session | False | False | exact | True |
| bb7c3b45 | multi-session | False | False | exact | True |
| ef9cf60a | multi-session | False | False | exact | True |
| ef9cf60a | multi-session | False | False | exact | True |
| ef9cf60a | multi-session | False | False | exact | True |
| ef9cf60a | multi-session | False | False | exact | True |
| ef9cf60a | multi-session | False | False | exact | True |
| ef9cf60a | multi-session | False | False | exact | True |
| ef9cf60a | multi-session | False | False | exact | True |
| ef9cf60a | multi-session | False | False | exact | True |
| gpt4_2f91af09 | multi-session | False | False | exact | True |
| gpt4_2f91af09 | multi-session | False | False | exact | True |
| gpt4_2f91af09 | multi-session | False | False | exact | True |
| gpt4_2f91af09 | multi-session | False | False | exact | True |
| gpt4_2f91af09 | multi-session | False | False | exact | True |
| gpt4_2f91af09 | multi-session | False | False | exact | True |
| gpt4_2f91af09 | multi-session | False | False | exact | True |
| gpt4_2f91af09 | multi-session | False | False | exact | True |
| gpt4_7fce9456 | multi-session | False | False | deterministic_mismatch | False |
| gpt4_7fce9456 | multi-session | False | False | deterministic_mismatch | False |
| gpt4_7fce9456 | multi-session | False | False | deterministic_mismatch | False |
| gpt4_7fce9456 | multi-session | False | False | deterministic_mismatch | False |
| gpt4_7fce9456 | multi-session | False | False | deterministic_mismatch | False |
| gpt4_7fce9456 | multi-session | False | False | deterministic_mismatch | False |
| gpt4_7fce9456 | multi-session | False | False | deterministic_mismatch | False |
| gpt4_7fce9456 | multi-session | False | False | deterministic_mismatch | False |
| 3249768e | single-session-assistant | False | False | exact | True |
| 3249768e | single-session-assistant | False | False | exact | True |
| 3249768e | single-session-assistant | False | False | exact | True |
| 3249768e | single-session-assistant | False | False | exact | True |
| 3249768e | single-session-assistant | False | False | exact | True |
| 3249768e | single-session-assistant | False | False | exact | True |
| 3249768e | single-session-assistant | False | False | exact | True |
| 3249768e | single-session-assistant | False | False | exact | True |
| 3e321797 | single-session-assistant | False | False | exact | True |
| 3e321797 | single-session-assistant | False | False | exact | True |
| 3e321797 | single-session-assistant | False | False | exact | True |
| 3e321797 | single-session-assistant | False | False | exact | True |
| 3e321797 | single-session-assistant | False | False | exact | True |
| 3e321797 | single-session-assistant | False | False | exact | True |
| 3e321797 | single-session-assistant | False | False | exact | True |
| 3e321797 | single-session-assistant | False | False | exact | True |
| 51b23612 | single-session-assistant | False | False | exact | True |
| 51b23612 | single-session-assistant | False | False | exact | True |
| 51b23612 | single-session-assistant | False | False | exact | True |
| 51b23612 | single-session-assistant | False | False | exact | True |
| 51b23612 | single-session-assistant | False | False | exact | True |
| 51b23612 | single-session-assistant | False | False | exact | True |
| 51b23612 | single-session-assistant | False | False | exact | True |
| 8aef76bc | single-session-assistant | False | False | exact | True |
| 51b23612 | single-session-assistant | False | False | exact | True |
| 8aef76bc | single-session-assistant | False | False | exact | True |
| 8aef76bc | single-session-assistant | False | False | exact | True |
| 8aef76bc | single-session-assistant | False | False | exact | True |
| 8aef76bc | single-session-assistant | False | False | exact | True |
| 8aef76bc | single-session-assistant | False | False | exact | True |
| 8aef76bc | single-session-assistant | False | False | exact | True |
| 8aef76bc | single-session-assistant | False | False | exact | True |
| ceb54acb | single-session-assistant | False | False | deterministic_mismatch | False |
| ceb54acb | single-session-assistant | False | False | deterministic_mismatch | False |
| ceb54acb | single-session-assistant | False | False | deterministic_mismatch | False |
| ceb54acb | single-session-assistant | False | False | deterministic_mismatch | False |
| ceb54acb | single-session-assistant | False | False | deterministic_mismatch | False |
| ceb54acb | single-session-assistant | False | False | deterministic_mismatch | False |
| ceb54acb | single-session-assistant | False | False | deterministic_mismatch | False |
| e982271f | single-session-assistant | False | False | exact | True |
| ceb54acb | single-session-assistant | False | False | deterministic_mismatch | False |
| e982271f | single-session-assistant | False | False | exact | True |
| e982271f | single-session-assistant | False | False | exact | True |
| e982271f | single-session-assistant | False | False | exact | True |
| e982271f | single-session-assistant | False | False | exact | True |
| e982271f | single-session-assistant | False | False | exact | True |
| e982271f | single-session-assistant | False | False | exact | True |
| e982271f | single-session-assistant | False | False | exact | True |
| 0a34ad58 | single-session-preference | False | False | deterministic_mismatch | False |
| 0a34ad58 | single-session-preference | False | False | deterministic_mismatch | False |
| 0a34ad58 | single-session-preference | False | False | deterministic_mismatch | False |
| 0a34ad58 | single-session-preference | False | False | deterministic_mismatch | False |
| 0a34ad58 | single-session-preference | False | False | deterministic_mismatch | False |
| 0a34ad58 | single-session-preference | False | False | deterministic_mismatch | False |
| 0a34ad58 | single-session-preference | False | False | deterministic_mismatch | False |
| 0a34ad58 | single-session-preference | False | False | deterministic_mismatch | False |
| 54026fce | single-session-preference | False | False | deterministic_mismatch | False |
| 54026fce | single-session-preference | False | False | deterministic_mismatch | False |
| 54026fce | single-session-preference | False | False | deterministic_mismatch | False |
| 54026fce | single-session-preference | False | False | deterministic_mismatch | False |
| 54026fce | single-session-preference | False | False | deterministic_mismatch | False |
| 54026fce | single-session-preference | False | False | deterministic_mismatch | False |
| 54026fce | single-session-preference | False | False | deterministic_mismatch | False |
| a89d7624 | single-session-preference | False | False | deterministic_mismatch | False |
| 54026fce | single-session-preference | False | False | deterministic_mismatch | False |
| a89d7624 | single-session-preference | False | False | deterministic_mismatch | False |
| a89d7624 | single-session-preference | False | False | deterministic_mismatch | False |
| a89d7624 | single-session-preference | False | False | deterministic_mismatch | False |
| a89d7624 | single-session-preference | False | False | deterministic_mismatch | False |
| a89d7624 | single-session-preference | False | False | deterministic_mismatch | False |
| a89d7624 | single-session-preference | False | False | deterministic_mismatch | False |
| 4100d0a0 | single-session-user | False | False | deterministic_mismatch | False |
| a89d7624 | single-session-preference | False | False | deterministic_mismatch | False |
| 4100d0a0 | single-session-user | False | False | deterministic_mismatch | False |
| 4100d0a0 | single-session-user | False | False | deterministic_mismatch | False |
| 4100d0a0 | single-session-user | False | False | deterministic_mismatch | False |
| 4100d0a0 | single-session-user | False | False | deterministic_mismatch | False |
| 4100d0a0 | single-session-user | False | False | deterministic_mismatch | False |
| 4100d0a0 | single-session-user | False | False | deterministic_mismatch | False |
| 4100d0a0 | single-session-user | False | False | deterministic_mismatch | False |
| 6f9b354f | single-session-user | False | False | exact | True |
| 6f9b354f | single-session-user | False | False | exact | True |
| 6f9b354f | single-session-user | False | False | exact | True |
| 6f9b354f | single-session-user | False | False | exact | True |
| 6f9b354f | single-session-user | False | False | exact | True |
| 6f9b354f | single-session-user | False | False | exact | True |
| 6f9b354f | single-session-user | False | False | exact | True |
| 6f9b354f | single-session-user | False | False | exact | True |
| 86b68151 | single-session-user | False | False | exact | True |
| 86b68151 | single-session-user | False | False | exact | True |
| 86b68151 | single-session-user | False | False | exact | True |
| 86b68151 | single-session-user | False | False | exact | True |
| 86b68151 | single-session-user | False | False | exact | True |
| 86b68151 | single-session-user | False | False | exact | True |
| 86b68151 | single-session-user | False | False | exact | True |
| 86b68151 | single-session-user | False | False | exact | True |
| ad7109d1 | single-session-user | False | False | exact | True |
| ad7109d1 | single-session-user | False | False | exact | True |
| ad7109d1 | single-session-user | False | False | exact | True |
| ad7109d1 | single-session-user | False | False | exact | True |
| ad7109d1 | single-session-user | False | False | exact | True |
| ad7109d1 | single-session-user | False | False | exact | True |
| ad7109d1 | single-session-user | False | False | exact | True |
| ad7109d1 | single-session-user | False | False | exact | True |
| caf9ead2 | single-session-user | False | False | exact | True |
| caf9ead2 | single-session-user | False | False | exact | True |
| caf9ead2 | single-session-user | False | False | exact | True |
| caf9ead2 | single-session-user | False | False | exact | True |
| caf9ead2 | single-session-user | False | False | exact | True |
| caf9ead2 | single-session-user | False | False | exact | True |
| caf9ead2 | single-session-user | False | False | exact | True |
| caf9ead2 | single-session-user | False | False | exact | True |
| f4f1d8a4 | single-session-user | False | False | deterministic_mismatch | False |
| f4f1d8a4 | single-session-user | False | False | deterministic_mismatch | False |
| f4f1d8a4 | single-session-user | False | False | deterministic_mismatch | False |
| f4f1d8a4 | single-session-user | False | False | deterministic_mismatch | False |
| f4f1d8a4 | single-session-user | False | False | deterministic_mismatch | False |
| f4f1d8a4 | single-session-user | False | False | deterministic_mismatch | False |
| f4f1d8a4 | single-session-user | False | False | deterministic_mismatch | False |
| f4f1d8a4 | single-session-user | False | False | deterministic_mismatch | False |
| 0bc8ad93 | temporal-reasoning | False | False | deterministic_mismatch | False |
| 0bc8ad93 | temporal-reasoning | False | False | deterministic_mismatch | False |
| 0bc8ad93 | temporal-reasoning | False | False | deterministic_mismatch | False |
| 0bc8ad93 | temporal-reasoning | False | False | deterministic_mismatch | False |
| 0bc8ad93 | temporal-reasoning | False | False | deterministic_mismatch | False |
| 0bc8ad93 | temporal-reasoning | False | False | deterministic_mismatch | False |
| 0bc8ad93 | temporal-reasoning | False | False | deterministic_mismatch | False |
| 0bc8ad93 | temporal-reasoning | False | False | deterministic_mismatch | False |
| a3838d2b | temporal-reasoning | False | False | exact | True |
| a3838d2b | temporal-reasoning | False | False | exact | True |
| a3838d2b | temporal-reasoning | False | False | exact | True |
| a3838d2b | temporal-reasoning | False | False | exact | True |
| a3838d2b | temporal-reasoning | False | False | exact | True |
| a3838d2b | temporal-reasoning | False | False | exact | True |
| a3838d2b | temporal-reasoning | False | False | exact | True |
| b46e15ee | temporal-reasoning | False | False | normalized | True |
| a3838d2b | temporal-reasoning | False | False | exact | True |
| b46e15ee | temporal-reasoning | False | False | normalized | True |
| b46e15ee | temporal-reasoning | False | False | normalized | True |
| b46e15ee | temporal-reasoning | False | False | normalized | True |
| b46e15ee | temporal-reasoning | False | False | normalized | True |
| b46e15ee | temporal-reasoning | False | False | normalized | True |
| b46e15ee | temporal-reasoning | False | False | normalized | True |
| eac54add | temporal-reasoning | False | False | deterministic_mismatch | False |
| b46e15ee | temporal-reasoning | False | False | normalized | True |
| eac54add | temporal-reasoning | False | False | deterministic_mismatch | False |
| eac54add | temporal-reasoning | False | False | deterministic_mismatch | False |
| eac54add | temporal-reasoning | False | False | deterministic_mismatch | False |
| eac54add | temporal-reasoning | False | False | deterministic_mismatch | False |
| eac54add | temporal-reasoning | False | False | deterministic_mismatch | False |
| eac54add | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_1d80365e | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_1d80365e | temporal-reasoning | False | False | deterministic_mismatch | False |
| eac54add | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_1d80365e | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_1d80365e | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_1d80365e | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_1d80365e | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_1d80365e | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_1d80365e | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_2f56ae70 | temporal-reasoning | False | False | exact | True |
| gpt4_2f56ae70 | temporal-reasoning | False | False | exact | True |
| gpt4_2f56ae70 | temporal-reasoning | False | False | exact | True |
| gpt4_2f56ae70 | temporal-reasoning | False | False | exact | True |
| gpt4_2f56ae70 | temporal-reasoning | False | False | exact | True |
| gpt4_2f56ae70 | temporal-reasoning | False | False | exact | True |
| gpt4_2f56ae70 | temporal-reasoning | False | False | exact | True |
| gpt4_2f56ae70 | temporal-reasoning | False | False | exact | True |
| gpt4_4929293a | temporal-reasoning | False | False | exact | True |
| gpt4_4929293a | temporal-reasoning | False | False | exact | True |
| gpt4_4929293a | temporal-reasoning | False | False | exact | True |
| gpt4_4929293a | temporal-reasoning | False | False | exact | True |
| gpt4_4929293a | temporal-reasoning | False | False | exact | True |
| gpt4_4929293a | temporal-reasoning | False | False | exact | True |
| gpt4_4929293a | temporal-reasoning | False | False | exact | True |
| gpt4_61e13b3c | temporal-reasoning | False | False | exact | True |
| gpt4_61e13b3c | temporal-reasoning | False | False | exact | True |
| gpt4_4929293a | temporal-reasoning | False | False | exact | True |
| gpt4_61e13b3c | temporal-reasoning | False | False | exact | True |
| gpt4_61e13b3c | temporal-reasoning | False | False | exact | True |
| gpt4_61e13b3c | temporal-reasoning | False | False | exact | True |
| gpt4_61e13b3c | temporal-reasoning | False | False | exact | True |
| gpt4_61e13b3c | temporal-reasoning | False | False | exact | True |
| gpt4_61e13b3c | temporal-reasoning | False | False | exact | True |
| gpt4_6dc9b45b | temporal-reasoning | False | False | exact | True |
| gpt4_6dc9b45b | temporal-reasoning | False | False | exact | True |
| gpt4_6dc9b45b | temporal-reasoning | False | False | exact | True |
| gpt4_6dc9b45b | temporal-reasoning | False | False | exact | True |
| gpt4_6dc9b45b | temporal-reasoning | False | False | exact | True |
| gpt4_6dc9b45b | temporal-reasoning | False | False | exact | True |
| gpt4_6dc9b45b | temporal-reasoning | False | False | exact | True |
| gpt4_6dc9b45b | temporal-reasoning | False | False | exact | True |
| gpt4_8279ba02 | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_8279ba02 | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_8279ba02 | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_8279ba02 | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_8279ba02 | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_8279ba02 | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_8279ba02 | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_8279ba02 | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_93159ced | temporal-reasoning | False | False | exact | True |
| gpt4_93159ced | temporal-reasoning | False | False | exact | True |
| gpt4_93159ced | temporal-reasoning | False | False | exact | True |
| gpt4_93159ced | temporal-reasoning | False | False | exact | True |
| gpt4_93159ced | temporal-reasoning | False | False | exact | True |
| gpt4_93159ced | temporal-reasoning | False | False | exact | True |
| gpt4_93159ced | temporal-reasoning | False | False | exact | True |
| gpt4_d6585ce8 | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_93159ced | temporal-reasoning | False | False | exact | True |
| gpt4_d6585ce8 | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_d6585ce8 | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_d6585ce8 | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_d6585ce8 | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_d6585ce8 | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_d6585ce8 | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_d6585ce8 | temporal-reasoning | False | False | deterministic_mismatch | False |
| gpt4_f420262d | temporal-reasoning | False | False | exact | True |
| gpt4_f420262d | temporal-reasoning | False | False | exact | True |
| gpt4_f420262d | temporal-reasoning | False | False | exact | True |
| gpt4_f420262d | temporal-reasoning | False | False | exact | True |
| gpt4_f420262d | temporal-reasoning | False | False | exact | True |
| gpt4_f420262d | temporal-reasoning | False | False | exact | True |
| gpt4_f420262d | temporal-reasoning | False | False | exact | True |
| gpt4_f420262d | temporal-reasoning | False | False | exact | True |
