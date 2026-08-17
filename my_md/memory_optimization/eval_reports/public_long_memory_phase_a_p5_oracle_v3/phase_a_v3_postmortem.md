# LongMemEval Phase A v3 Postmortem

## Run Method

This run evaluated LongMemEval Oracle through the existing AgentLoop memory path.
It is a P5-only public benchmark run, not a P1-P5 ablation.

| field | value |
| --- | --- |
| dataset | `my_md/memory_optimization/datasets/public_long_memory/longmemeval_oracle.json` |
| dataset_sha256 | `821a2034d219ab45846873dd14c14f12cfe7776e73527a483f9dac095d38620c` |
| phase | `phase_a` |
| sample_size | `50` |
| seed | `42` |
| profile | `chain_tri_governed_answer_contract` |
| prompt_variants | `baseline` |
| repeats | `1` |
| actual_call_shape | `50 * 1 * 1 * 1 = 50` |
| evidence_render_mode | `answer_window` |
| effective_evidence_token_budget | `3000` |
| concurrency | `1` |
| real_llm_enabled | `true` |
| capture_provider_request | `true` |

Command shape was the planned Phase A v3 shape: P5-only, baseline-only, repeat once,
deterministic sampling (`temperature=0`, `top_p=1`), and request capture enabled.

## Artifacts

| artifact | path | note |
| --- | --- | --- |
| JSON report | `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v3/public_long_memory_eval.json` | aggregate metrics and case reviews |
| Markdown report | `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v3/public_long_memory_eval.md` | lightweight human report |
| checkpoint | `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v3/phase_a_checkpoint.jsonl` | 50 completed rows |
| answer debug | `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v3/workspace/public_long_memory_answer_debug/` | 50 answer/evidence files |
| provider requests | `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v3/workspace/public_long_memory_provider_requests/` | 50 captured request files |
| per-case workspaces | `my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v3/workspace/case-*/` | session DBs, not intended for commit |

Important caveat: provider request capture in v3 used a shallow copy of the provider
kwargs. Some captured `messages` lists show the assistant answer appended after the
provider call, so v3 request files should be treated as diagnostic evidence, not an
immutable wire snapshot.

## Results

| metric | value |
| --- | ---: |
| completed_call_count | 50 |
| provider_error_count | 0 |
| timeout_count | 0 |
| malformed_checkpoint_line_count | 0 |
| checkpoint_provenance_mismatch_count | 0 |
| fresh_checkpoint_valid | true |
| public_answer_pass_count | 21 |
| public_answer_pass_rate | 42.0% |
| deterministic_mismatch_count | 29 |
| exact_count | 21 |
| scorer_unable_to_score_count | 0 |
| scorer_unable_to_score_rate | 0.0% |
| tool_call_style_output_count | 0 |
| sent_evidence_gold_hit_count | 27 |
| sent_evidence_gold_hit_rate | 54.0% |

The online path itself was stable: all 50 calls completed with no provider error,
timeout, malformed checkpoint row, or tool-call-style output. The answer-quality
number is not yet a clean model capability number because several prompt, time, and
scoring issues contaminate the run.

## Category Breakdown

| category | total | pass | fail | pass_rate |
| --- | ---: | ---: | ---: | ---: |
| `multi-session` | 12 | 8 | 4 | 66.7% |
| `knowledge-update` | 7 | 4 | 3 | 57.1% |
| `single-session-assistant` | 6 | 3 | 3 | 50.0% |
| `single-session-user` | 6 | 2 | 4 | 33.3% |
| `temporal-reasoning` | 13 | 4 | 9 | 30.8% |
| `single-session-preference` | 3 | 0 | 3 | 0.0% |
| `abstention` | 3 | 0 | 3 | 0.0% |

## Captured Flow Samples

### `60bf93ed_abs` - Abstention

- Question: `How many days did it take for my iPad case to arrive after I bought it?`
- Gold: `The information provided is not enough. You did not mention buying an iPad case.`
- Model answer: Chinese refusal stating the evidence did not mention buying an iPad case.
- Public score: `deterministic_mismatch`.
- Diagnosis: likely scorer false negative. The answer is semantically aligned with abstention,
  but deterministic scoring expects the English gold wording.

### `031748ae` - Knowledge Update

- Question asks how many engineers the user led when starting a Senior Software Engineer role
  and how many they lead now.
- Gold: `When you just started your new role as Senior Software Engineer, you led 4 engineers. Now, you lead 5 engineers`
- Model answer: `刚开始的时候是 4 个工程师。现在带 5 个工程师了。`
- Public score: `deterministic_mismatch`.
- Diagnosis: likely language/scorer false negative. The answer is semantically correct but in Chinese.

### `gpt4_8279ba02` - Temporal Reasoning

- Question: `How many days ago did I buy a smoker?`
- Gold: `10 days ago. 11 days (including the last day) is also acceptable.`
- Model answer: states it cannot compute the date because memory only says "today" and lacks the exact date.
- Public score: `deterministic_mismatch`.
- Diagnosis: real evidence-rendering/time-anchor issue. The dataset has `question_date` and
  session dates, but v3 used online run time (`2026-08-17`) in the current message and did
  not render `session_date` into allowed evidence.

## Confirmed Problems

| priority | problem | evidence | impact |
| --- | --- | --- | --- |
| P0 | Global prompt unconditionally induces Chinese | 50/50 captured requests have system prompt containing Chinese style rules; 46/50 answers were Chinese or mixed | English benchmark answers are scored against English gold and receive false negatives |
| P0 | Wrong temporal anchor | captured user messages use run time `2026-08-17`, not dataset `question_date` | temporal-reasoning with `days ago`, `months ago`, `a month ago` is polluted |
| P0 | `session_date` not rendered into evidence text | adapter preserves dates in metadata, but answer_window evidence renders turn content only | model cannot map `today/yesterday` inside session text to absolute dates |
| P1 | Request capture is a shallow-copy diagnostic | captured requests can include later assistant answer mutation | "true sent request" audit is not fully reliable |
| P1 | Deterministic scorer has false negatives | Chinese correct answers, translated short facts, and abstention refusals fail exact/normalized contains | public pass rate underestimates answer quality |
| P1 | `sent_evidence_gold_hit` is too literal for reasoning cases | computed answers such as `17 + 5 + 1 = 23` need not appear literally in evidence | gate `>=30/50` can reject sufficient evidence |
| P1 | `answer_window` can be narrow for multi-hop cases | some multi-session/temporal questions need multiple session snippets plus dates | selected evidence may miss supporting facts even when relevant sessions exist |
| P2 | Abstention lacks intent scoring | 3/3 abstention cases failed despite refusal-style answers | unable to distinguish correct refusal from wrong answer |
| P2 | Preference cases need rubric/semantic scoring | 3/3 preference cases failed; gold answers are long preference descriptions | contains scoring is structurally weak for this category |

## Fix Direction

The next run should be v4, not Phase B. v4 must first fix the global language policy,
LongMemEval date handling, provider request snapshotting, and scoring diagnostics. Phase B
should remain blocked until Phase A v4 passes its gates.
