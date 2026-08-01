# P6o34 Current Best Stability R3

## Goal

Validate whether the current best scheme remains stable across three real-LLM repeats on the same 80-case medium system-path set.

Current best:

- mode: `safe_version_replace_guided_with_retry_shadow`
- persona: `work`
- real retry: not enabled
- `retry_shadow`: telemetry only

## Method

Plan:

- `docs/superpowers/plans/2026-08-01-p6o34-current-best-stability-r3.md`

Plan review revisions:

- Replaced placeholder timestamp commands with executable shell blocks.
- Added explicit `real_llm_enabled=true` and `fake_provider_enabled=false` gates.
- Added explicit one-mode and repeat row-shape gates.
- Added repeat-to-repeat flipped-case reporting.

Preflight:

```bash
git status --short --branch
git log -1 --oneline
```

Result:

- branch: `memory-next`
- HEAD: `38c9165 test(memory): add p6o33 incremental real eval`
- only unrelated untracked path: `my_md/memory_optimization/eval_reports/p6o13_system_path_real_llm_validation_v1/`

P6o33 baseline:

```text
gate_passed=True
unique_case_count=80
repeat_count=1
answer_rule_pass_rate=100.0
memory_grounding_pass_rate=100.0
forbidden_violation_rate=0.0
would_retry_count=0
```

Run id:

- `p6o34_current_best_stability_r3_real_v1_20260801_201154`

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace /tmp/akashic-p6o34_current_best_stability_r3_real_v1_20260801_201154-workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o34_current_best_stability_r3_real_v1_20260801_201154 \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --enable-real-llm \
  --balanced-small \
  --common-limit 40 \
  --hard-limit 40 \
  --modes safe_version_replace_guided_with_retry_shadow \
  --persona-mode work \
  --repeats 3 \
  --timeout-s 60 \
  --checkpoint-jsonl /tmp/akashic-p6o34_current_best_stability_r3_real_v1_20260801_201154.jsonl \
  --answer-debug-dir my_md/memory_optimization/eval_reports/p6o34_current_best_stability_r3_real_v1_20260801_201154/answer_debug \
  --early-infra-abort-count 5 \
  --early-infra-abort-rate 0.5 \
  --allow-infra-blocked-exit-zero
```

Artifacts:

- `my_md/memory_optimization/eval_reports/p6o34_current_best_stability_r3_real_v1_20260801_201154/system_path_safe_version_eval.json`
- `my_md/memory_optimization/eval_reports/p6o34_current_best_stability_r3_real_v1_20260801_201154/system_path_safe_version_eval.md`
- `my_md/memory_optimization/eval_reports/p6o34_current_best_stability_r3_real_v1_20260801_201154/answer_debug/`

## Gate Criteria

Strict gate:

- `unique_case_count == 80`
- `case_count == 240`
- `repeat_count == 3`
- only mode is `safe_version_replace_guided_with_retry_shadow`
- each repeat has `80` rows
- aggregate answer rate `>= 95.0%`
- each repeat answer rate `>= 95.0%`
- grounding `100.0%`
- forbidden `0.0%`
- provider errors `0`
- timeouts `0`
- checkpoint input/malformed/skipped `0`
- no `blocked_status.json`

Stability reporting:

- Report flipped case count across repeats.
- `flipped_case_count=0` is strong stability.
- `flipped_case_count>0` means answer quality is above threshold but not fully deterministic.

## Data

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
| checkpoint input lines | 0 |
| malformed checkpoint lines | 0 |
| skipped from checkpoint | 0 |
| blocked status | absent |
| debug JSON files | 240 |
| total tokens | 1,455,464 |
| avg tokens / row | 6,064.4333 |
| avg latency / row | 4,512.1333 ms |

Aggregate:

| metric | value |
| --- | ---: |
| answer success | 236 / 240 |
| answer rate | 98.3333% |
| grounding rate | 100.0% |
| forbidden violation rate | 0.4167% |
| forbidden rows | 1 |
| contract generation success | 100.0% |
| answer candidate contract enabled | 100.0% |
| post-check shadow enabled | 100.0% |
| would retry | 5 |

Retry shadow reasons:

| reason | count |
| --- | ---: |
| `answer_choice_group_missing` | 3 |
| `answerable_evidence_contract_ignored` | 2 |
| `dsml_tool_markup_in_final_answer` | 1 |
| `meta_action_final_answer` | 1 |
| `tool_markup_in_final_answer` | 1 |

Per repeat:

| repeat | answer | answer rate | grounding | forbidden | would retry | retry reasons |
| ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0 | 78 / 80 | 97.5% | 100.0% | 1.25% | 1 | `answer_choice_group_missing: 1` |
| 1 | 78 / 80 | 97.5% | 100.0% | 0.0% | 3 | `answer_choice_group_missing: 2`, `answerable_evidence_contract_ignored: 1`, `dsml_tool_markup_in_final_answer: 1`, `tool_markup_in_final_answer: 1` |
| 2 | 80 / 80 | 100.0% | 100.0% | 0.0% | 1 | `answerable_evidence_contract_ignored: 1`, `meta_action_final_answer: 1` |

Flipped cases:

| case | repeat outcomes |
| --- | --- |
| `common_preference_recall_01` | repeat 0 pass, repeat 1 fail, repeat 2 pass |
| `common_preference_recall_02` | repeat 0 pass, repeat 1 fail, repeat 2 pass |
| `common_preference_recall_03` | repeat 0 fail, repeat 1 pass, repeat 2 pass |
| `hard_style_preference_01` | repeat 0 fail, repeat 1 pass, repeat 2 pass |

## Failed / Interesting Rows

There were 4 answer-failed rows, 1 forbidden row, and 5 would-retry shadow rows. Some rows overlap.

| repeat | case | category | answer pass | issue | classification | raw debug path |
| ---: | --- | --- | --- | --- | --- | --- |
| 0 | `common_preference_recall_03` | common preference recall | false | missing expected answer term group; `answer_choice_group_missing` | answer omitted expected fact group | `answer_debug/0020-repeat-00-safe_version_replace_guided_with_retry_shadow-common_preference_recall_03.json` |
| 0 | `hard_style_preference_01` | hard style preference | false | forbidden old term found | forbidden/stale leakage or scorer-sensitive old-value wording | `answer_debug/0042-repeat-00-safe_version_replace_guided_with_retry_shadow-hard_style_preference_01.json` |
| 1 | `common_preference_recall_01` | common preference recall | false | missing expected answer term group; `answer_choice_group_missing` | answer omitted expected fact group | `answer_debug/0000-repeat-01-safe_version_replace_guided_with_retry_shadow-common_preference_recall_01.json` |
| 1 | `common_preference_recall_02` | common preference recall | false | missing expected answer term group; `answer_choice_group_missing` | answer omitted expected fact group | `answer_debug/0010-repeat-01-safe_version_replace_guided_with_retry_shadow-common_preference_recall_02.json` |
| 1 | `common_preference_recall_04` | common preference recall | true | DSML pseudo `memorize` final answer; `answerable_evidence_contract_ignored` | meta-action / pseudo tool call, caught by shadow only | `answer_debug/0030-repeat-01-safe_version_replace_guided_with_retry_shadow-common_preference_recall_04.json` |
| 2 | `common_preference_recall_01` | common preference recall | true | meta-action / contract ignored shadow | shadow-only suspicious answer shape | `answer_debug/0000-repeat-02-safe_version_replace_guided_with_retry_shadow-common_preference_recall_01.json` |

Observed raw-answer patterns:

- Preference recall failures still usually mention Chinese/pytest style, but miss the exact expected fact group the scorer requires.
- One repeat produced a DSML pseudo tool-call (`memorize`) as the final answer despite the contract-completion guidance.
- One hard style preference row used wording that triggered a forbidden old-value term.

## Conclusion

P6o34 does not fully pass the strict pre-registered stability gate because forbidden violation was not `0.0%`.

What passed:

- Answer quality remained high: `236/240 = 98.3333%`.
- Every repeat stayed above the `>=95%` answer threshold:
  - repeat 0: `97.5%`
  - repeat 1: `97.5%`
  - repeat 2: `100.0%`
- Grounding stayed `100.0%`.
- Provider errors and timeouts were both `0`.

What did not pass:

- Forbidden violation was `1/240 = 0.4167%`, so the safety gate failed.
- `flipped_case_count=4`, so the current best is not fully deterministic across repeats.
- `would_retry_count=5`, including answer-choice misses and meta-action/tool-markup style issues.

Interpretation:

- The current best scheme is usable for recall/answering in this 80-case setting and clearly above the 80% target.
- It is not yet strong enough to call fully stable under the strict safety gate.
- The remaining failures are concentrated in preference/style recall and one pseudo-tool/meta-action behavior, not retrieval grounding.
- Because real retry is still off, this run suggests a targeted post-check retry could be useful specifically for `answer_choice_group_missing`, `answerable_evidence_contract_ignored`, and tool/meta-action final answers.

Recommended next step:

- Do not add broad prompt rules.
- Build or shadow-test a narrow real retry path only for the post-check reasons observed here, or tighten the final-answer suppression for DSML/tool/meta-action outputs.
