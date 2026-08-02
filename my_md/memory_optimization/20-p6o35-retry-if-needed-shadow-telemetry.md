# P6o35 Retry-If-Needed Shadow Telemetry

## Goal

Validate a narrow retry-if-needed telemetry layer for the current best scheme without changing prompt behavior or enabling real retry.

Current best under test:

- mode: `safe_version_replace_guided_with_retry_shadow`
- persona: `work`
- prompt variant: unchanged `guided_retry_shadow`
- real retry: not enabled
- retry-if-needed: telemetry only

## Plan And Review

Plan:

- `docs/superpowers/plans/2026-08-01-p6o35-retry-if-needed-shadow-telemetry.md`

The initial plan proposed a new final-answer hygiene prompt variant. Plan review rejected that as too easy to confuse with a prompt-performance experiment. The revised plan instead:

- keeps current best prompt and mode unchanged;
- adds separate retry-if-needed shadow fields instead of reusing broad `needs_retry`;
- classifies forbidden answer-term hits as blocked, not retry-eligible;
- requires privacy-by-construction for new telemetry fields;
- keeps production retry and production defaults unchanged.

## Code Changes

- `memory2/eval_answer_post_check.py`
  - Added `retry_if_needed_shadow_enabled`.
  - Added `retry_if_needed_eligible`.
  - Added `retry_if_needed_reasons`.
  - Added `retry_if_needed_blocked_reasons`.
  - Added `forbidden_answer_term_found` as a broad retry reason and narrow blocked reason when scorer reports forbidden answer terms.
- `memory2/eval_system_path_safe_version.py`
  - Passes `forbidden_contains_violation_count` from scorer into post-check `answer_score`.
- Tests:
  - `tests/test_memory_answer_post_check.py`
  - `tests/test_memory_system_path_safe_version_eval.py`

No prompt variant, global prompt, recall path, write path, fallback path, or real retry path was changed.

## Test Method

Focused test command:

```bash
.venv/bin/pytest tests/test_memory_answer_post_check.py tests/test_memory_system_path_safe_version_eval.py -q
```

Result:

```text
43 passed in 37.01s
```

The final focused suite also verifies that
`safe_version_replace_guided_with_retry_shadow` makes exactly one provider call
per case. The post-check only records telemetry and does not execute a second
LLM call.

Fake smoke command:

```bash
.venv/bin/python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace /tmp/akashic-p6o35-fake-workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o35_retry_if_needed_shadow_fake_v1 \
  --fake-provider \
  --balanced-small \
  --common-limit 2 \
  --hard-limit 2 \
  --modes safe_version_replace_guided_with_retry_shadow \
  --persona-mode work
```

Fake smoke artifacts:

- `my_md/memory_optimization/eval_reports/p6o35_retry_if_needed_shadow_fake_v1/system_path_safe_version_eval.json`
- `my_md/memory_optimization/eval_reports/p6o35_retry_if_needed_shadow_fake_v1/system_path_safe_version_eval.md`

Fake smoke result:

| metric | value |
| --- | ---: |
| unique cases | 4 |
| case rows | 4 |
| modes | 1 |
| real LLM | false |
| fake provider | true |
| answer candidate contract enabled | 100.0% |
| post-check shadow enabled | 100.0% |
| retry-if-needed fields on all rows | true |
| forbidden raw keys in normal report | none |

## Real R3 Method

Run id:

- `p6o35_retry_if_needed_shadow_real_r3_v1_20260801_204846`

Note:

- An initial run without `--config` failed before evaluation because this runner requires a TOML config path in this environment.
- The real run below used the same config path recorded by P6o32/P6o34.

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace /tmp/akashic-p6o35_retry_if_needed_shadow_real_r3_v1_20260801_204846-workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o35_retry_if_needed_shadow_real_r3_v1_20260801_204846 \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --enable-real-llm \
  --balanced-small \
  --common-limit 40 \
  --hard-limit 40 \
  --modes safe_version_replace_guided_with_retry_shadow \
  --persona-mode work \
  --repeats 3 \
  --timeout-s 60 \
  --checkpoint-jsonl /tmp/akashic-p6o35_retry_if_needed_shadow_real_r3_v1_20260801_204846.jsonl \
  --early-infra-abort-count 20 \
  --early-infra-abort-rate 0.5 \
  --answer-debug-dir my_md/memory_optimization/eval_reports/p6o35_retry_if_needed_shadow_real_r3_v1_20260801_204846/answer_debug
```

Artifacts:

- `my_md/memory_optimization/eval_reports/p6o35_retry_if_needed_shadow_real_r3_v1_20260801_204846/system_path_safe_version_eval.json`
- `my_md/memory_optimization/eval_reports/p6o35_retry_if_needed_shadow_real_r3_v1_20260801_204846/system_path_safe_version_eval.md`
- `my_md/memory_optimization/eval_reports/p6o35_retry_if_needed_shadow_real_r3_v1_20260801_204846/answer_debug/`

## Real R3 Data

Run shape:

| metric | value |
| --- | ---: |
| unique cases | 80 |
| case rows | 240 |
| repeats | 3 |
| modes | 1 |
| real LLM | true |
| fake provider | false |
| provider errors | 0 |
| timeouts | 0 |
| malformed checkpoint lines | 0 |
| blocked status | absent |
| debug JSON files | 240 |
| total tokens | 1,457,054 |
| avg tokens / row | 6,071.0583 |
| avg latency / row | 4,758.8042 ms |

Aggregate:

| metric | value |
| --- | ---: |
| answer success | 237 / 240 |
| answer rate | 98.75% |
| grounding rate | 100.0% |
| forbidden violation rate | 0.8333% |
| forbidden rows | 2 |
| contract generation success | 100.0% |
| answer candidate contract enabled | 100.0% |
| post-check shadow enabled | 100.0% |
| broad would retry | 4 |
| retry-if-needed eligible rows | 2 |
| retry-if-needed blocked rows | 2 |

Broad retry shadow reasons:

| reason | count |
| --- | ---: |
| `answer_choice_group_missing` | 1 |
| `answerable_evidence_contract_ignored` | 1 |
| `forbidden_answer_term_found` | 2 |
| `meta_action_final_answer` | 1 |

Retry-if-needed telemetry:

| bucket | reason | row count |
| --- | --- | ---: |
| eligible | `answer_choice_group_missing` | 1 |
| eligible | `answerable_evidence_contract_ignored` | 1 |
| eligible | `meta_action_final_answer` | 1 |
| blocked | `forbidden_answer_term_found` | 2 |

The eligible reason row counts overlap: the `answerable_evidence_contract_ignored` row is the same row as `meta_action_final_answer`.

Per repeat:

| repeat | answer | answer rate | grounding | forbidden | broad would retry | retry reasons |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0 | 79 / 80 | 98.75% | 100.0% | 1.25% | 1 | `forbidden_answer_term_found: 1` |
| 1 | 78 / 80 | 97.5% | 100.0% | 1.25% | 2 | `answer_choice_group_missing: 1`, `forbidden_answer_term_found: 1` |
| 2 | 80 / 80 | 100.0% | 100.0% | 0.0% | 1 | `answerable_evidence_contract_ignored: 1`, `meta_action_final_answer: 1` |

Flipped cases:

| case | repeat outcomes | observed issue |
| --- | --- | --- |
| `common_preference_recall_02` | pass, fail, pass | repeat 1 missed expected answer group; retry-if-needed eligible |
| `common_style_preference_04` | pass, fail, pass | repeat 1 forbidden answer term; retry-if-needed blocked |
| `hard_style_preference_03` | fail, pass, pass | repeat 0 forbidden answer term; retry-if-needed blocked |

Interesting rows:

| repeat | case | category | answer pass | issue | retry-if-needed | debug path |
| ---: | --- | --- | --- | --- | --- | --- |
| 0 | `hard_style_preference_03` | hard style preference | false | forbidden answer term | blocked: `forbidden_answer_term_found` | `answer_debug/0062-repeat-00-safe_version_replace_guided_with_retry_shadow-hard_style_preference_03.json` |
| 1 | `common_preference_recall_02` | common preference recall | false | missing expected answer group | eligible: `answer_choice_group_missing` | `answer_debug/0010-repeat-01-safe_version_replace_guided_with_retry_shadow-common_preference_recall_02.json` |
| 1 | `common_style_preference_04` | common style preference | false | forbidden answer term | blocked: `forbidden_answer_term_found` | `answer_debug/0032-repeat-01-safe_version_replace_guided_with_retry_shadow-common_style_preference_04.json` |
| 2 | `common_preference_recall_03` | common preference recall | true | shadow-only meta-action style phrase | eligible: `meta_action_final_answer`, `answerable_evidence_contract_ignored` | `answer_debug/0020-repeat-02-safe_version_replace_guided_with_retry_shadow-common_preference_recall_03.json` |

Local raw-answer inspection:

- The two forbidden rows were style/preference answers that included old or scorer-forbidden wording. They are correctly treated as blocked, not eligible retry-if-needed rows.
- The failed preference recall row was a clean answer-selection miss and is a valid future retry candidate.
- The shadow-only meta-action row passed answer scoring, but included a conditional “check before answering” style sentence. The current meta-action detector is conservative and may over-flag this class.

## Comparison With P6o34

| run | answer | grounding | forbidden | broad would retry | flipped cases |
| --- | ---: | ---: | ---: | ---: | ---: |
| P6o34 current best R3 | 236 / 240 = 98.3333% | 100.0% | 1 / 240 = 0.4167% | 5 | 4 |
| P6o35 same prompt + retry-if-needed telemetry | 237 / 240 = 98.75% | 100.0% | 2 / 240 = 0.8333% | 4 | 3 |

Interpretation:

- P6o35 is not a prompt-performance improvement experiment, because the prompt and real retry behavior were unchanged.
- The answer rate remained in the same high band as P6o34.
- Grounding remained clean.
- Strict safety still did not pass because forbidden rate was not `0.0%`.
- The new telemetry improved interpretability: forbidden answer-term rows are now separated into blocked reasons, while answer-choice/meta-action rows remain eligible.

## Gate Decision

| gate | result | evidence |
| --- | --- | --- |
| infra | pass | provider errors `0`, timeouts `0`, malformed checkpoint lines `0`, no `blocked_status.json` |
| row shape | pass | one mode, 80 unique cases, 240 rows, 3 repeats |
| telemetry presence | pass | retry-if-needed fields present on all 240 rows |
| normal report privacy | pass | no raw prompt/answer/query/memory summary keys in normal report |
| grounding | pass | 100.0% |
| safety | fail | forbidden `2/240 = 0.8333%` |
| production readiness | fail | real retry still not implemented; safety gate not clean |

## Conclusion

P6o35 successfully adds the missing decision surface for future retry design, but it does not make the current best production-ready.

What improved:

- `needs_retry` is no longer the only interpretation path.
- Retry-if-needed eligible rows are separated from blocked safety/context rows.
- Forbidden answer-term failures are visible as `forbidden_answer_term_found` and are not retry eligible.

What remains unresolved:

- The current best still occasionally emits forbidden/stale wording in style preference cases.
- Meta-action detection may over-flag answers that mention “check first” as a future behavior rule rather than an actual tool/meta final answer.
- Real retry is still off, so this run does not measure retry repair effectiveness.

Recommended next step:

- Do not enable real retry yet.
- First calibrate the meta-action detector to reduce false positives on conditional style commitments.
- Then run a narrow targeted retry pilot only for `answer_choice_group_missing` and high-confidence tool/meta final-answer failures, while keeping `forbidden_answer_term_found` as blocked safety telemetry.
