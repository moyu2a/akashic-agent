# P6o32 Contract Stability R3

## Goal

Validate whether the current best Evidence Contract conflict-governance scheme remains stable across three real LLM repeats on the 40-case medium system-path set.

Current best baseline:

- P6o31: `40/40 = 100.0%`
- grounding: `100.0%`
- forbidden: `0.0%`
- provider errors: `0`
- timeouts: `0`
- retry reasons: none

## Method

Plan:

- plan file: `docs/superpowers/plans/2026-07-31-p6o32-contract-stability-r3.md`
- plan review: completed before execution
- review revisions:
  - switched to fresh timestamped `/tmp` workspace and checkpoint paths;
  - added explicit run-shape gates for repeat count, repeat keys, case counts, real LLM mode, fake-provider state, and checkpoint cleanliness;
  - added direct conflict-family counters for DSML/tool/meta-action fields;
  - required conclusion language to distinguish `>=95%` stability from exact `40/40` repeat replication.

Preflight:

```bash
git status --short
```

Result:

- only unrelated existing untracked path was present:
  - `my_md/memory_optimization/eval_reports/p6o13_system_path_real_llm_validation_v1/`

P6o31 baseline verification command:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python - <<'PY'
import json
from pathlib import Path
p = Path('my_md/memory_optimization/eval_reports/p6o31_contract_conflict_medium_real_v1/system_path_safe_version_eval.json')
data = json.loads(p.read_text(encoding='utf-8'))
m = data['metrics']
print({
    'case_count': m['case_count'],
    'answer_rule_pass_rate': m['answer_rule_pass_rate'],
    'memory_grounding_pass_rate': m['memory_grounding_pass_rate'],
    'forbidden_violation_rate': m['forbidden_violation_rate'],
    'provider_error_count': m['provider_error_count'],
    'timeout_count': m['timeout_count'],
    'retry_reason_counts': m['mode_summaries']['safe_version_replace_guided_with_retry_shadow']['retry_reason_counts'],
})
PY
```

Result:

```text
{'case_count': 40, 'answer_rule_pass_rate': 100.0, 'memory_grounding_pass_rate': 100.0, 'forbidden_violation_rate': 0.0, 'provider_error_count': 0, 'timeout_count': 0, 'retry_reason_counts': {}}
```

Fresh path check:

```bash
test ! -e /tmp/akashic-p6o32-contract-stability-r3-workspace-20260731-1600
test ! -e /tmp/akashic-p6o32-contract-stability-r3-checkpoint-20260731-1600.jsonl
test ! -e my_md/memory_optimization/eval_reports/p6o32_contract_stability_r3_real_v1_20260731_1600
```

Result: all checks exited `0`.

Real LLM command:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace /tmp/akashic-p6o32-contract-stability-r3-workspace-20260731-1600 \
  --out-dir my_md/memory_optimization/eval_reports/p6o32_contract_stability_r3_real_v1_20260731_1600 \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --enable-real-llm \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --modes safe_version_replace_guided_with_retry_shadow \
  --persona-mode work \
  --repeats 3 \
  --timeout-s 60 \
  --checkpoint-jsonl /tmp/akashic-p6o32-contract-stability-r3-checkpoint-20260731-1600.jsonl \
  --early-infra-abort-count 5 \
  --early-infra-abort-rate 0.5 \
  --allow-infra-blocked-exit-zero
```

Report paths:

- `my_md/memory_optimization/eval_reports/p6o32_contract_stability_r3_real_v1_20260731_1600/system_path_safe_version_eval.json`
- `my_md/memory_optimization/eval_reports/p6o32_contract_stability_r3_real_v1_20260731_1600/system_path_safe_version_eval.md`

## Gate Criteria

Strict stability gate:

- `case_count = 120`
- `unique_case_count = 40`
- `repeat_count = 3`
- repeat keys exactly `0`, `1`, `2`
- each repeat `case_count = 40`
- `real_llm_enabled = true`
- `fake_provider_enabled = false`
- `mode_count = 1`
- only mode key is `safe_version_replace_guided_with_retry_shadow`
- `checkpoint_input_count = 0`
- `malformed_checkpoint_line_count = 0`
- `skipped_from_checkpoint_count = 0`
- aggregate answer rate `>= 95.0%`
- each repeat answer rate `>= 95.0%`
- grounding `100.0%`
- forbidden `0.0%`
- provider errors `0`
- timeouts `0`
- no `blocked_status.json`
- `dsml_tool_markup_in_final_answer = 0`
- `tool_markup_in_final_answer = 0`
- `meta_action_final_answer = 0`
- contract generation success rate `100.0%`
- answer candidate contract enabled rate `100.0%`
- post-check shadow enabled rate `100.0%`
- all three target case ids pass in all repeats

## Data

Aggregate:

| metric | value |
| --- | ---: |
| unique cases | 40 |
| case rows | 120 |
| repeats | 3 |
| real LLM | true |
| fake provider | false |
| mode count | 1 |
| checkpoint input count | 0 |
| malformed checkpoint lines | 0 |
| skipped from checkpoint | 0 |
| answer success | 118 / 120 |
| answer rate | 98.3333% |
| grounding rate | 100.0% |
| forbidden rate | 0.8333% |
| provider errors | 0 |
| timeouts | 0 |
| contract generation success | 100.0% |
| answer candidate contract enabled | 100.0% |
| post-check shadow enabled | 100.0% |
| would retry | 1 |
| retry reasons | `answer_choice_group_missing: 1` |
| conflict-family counters | none |
| avg latency | 5495.4 ms |
| avg total tokens | 6050.1667 |
| total tokens | 726020 |

Per repeat:

| repeat | rows | answer | answer rate | grounding | forbidden | would retry | retry reasons |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 0 | 40 | 39 / 40 | 97.5% | 100.0% | 2.5% | 0 | none |
| 1 | 40 | 40 / 40 | 100.0% | 100.0% | 0.0% | 0 | none |
| 2 | 40 | 39 / 40 | 97.5% | 100.0% | 0.0% | 1 | `answer_choice_group_missing: 1` |

Target case stability:

| case | repeat 0 | repeat 1 | repeat 2 | retry reasons |
| --- | --- | --- | --- | --- |
| `hard_graph_bridge_01` | pass | pass | pass | none |
| `hard_version_chain_01` | pass | pass | pass | none |
| `hard_preference_recall_02` | pass | pass | fail | repeat 2: `answer_choice_group_missing` |

Failed cases:

| repeat | case | failure | conflict-family flags | post-check retry reasons |
| ---: | --- | --- | --- | --- |
| 0 | `hard_stale_sleep_01` | `found_forbidden_answer_term` | none | none |
| 2 | `hard_preference_recall_02` | `missing_expected_answer_term_group` | none | `answer_choice_group_missing` |

Conflict-family recurrence:

| field | count |
| --- | ---: |
| `dsml_tool_markup_in_final_answer` | 0 |
| `tool_markup_in_final_answer` | 0 |
| `meta_action_final_answer` | 0 |

## Gate Result

The run passes the relaxed stability threshold:

- aggregate answer rate `98.3333%`, above `95.0%`;
- every repeat answer rate is at least `97.5%`;
- grounding is `100.0%`;
- provider errors and timeouts are `0`;
- DSML/tool/meta-action conflict-family counters are all `0`.

The run does not pass the strict stability gate:

- forbidden rate is `0.8333%`, not `0.0%`;
- one target case, `hard_preference_recall_02`, failed in repeat 2 with `answer_choice_group_missing`;
- therefore P6o31's exact `40/40` result was not replicated in every repeat.

## Conclusion

P6o32 supports that Scheme C is stable against the original prompt-conflict failure family. Across `120` real LLM rows, there were no DSML pseudo tool-call answers, no tool-markup final answers, and no "先查/先翻/核实" meta-action final answers.

However, P6o32 does not prove exact `100%` stability. The result is `118/120 = 98.3333%`, with two residual failures:

- one forbidden scorer hit on `hard_stale_sleep_01`;
- one answer-choice miss on `hard_preference_recall_02`.

Interpretation:

- The original global-history-vs-contract conflict appears fixed.
- Remaining instability is now narrower: one style/forbidden scorer issue and one preference answer-choice selection issue.
- Before moving to production retry, the next step should inspect the two failed raw answers from local session data and decide whether they are semantic failures, scorer strictness, or residual answer-selection ambiguity.
