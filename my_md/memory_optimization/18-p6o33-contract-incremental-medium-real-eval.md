# P6o33 Contract Incremental Medium Real Eval

## Goal

Compare three incremental system-path answer schemes under the current `memory-next` HEAD and `work` persona:

| Arm | Mode | Meaning | Real retry |
| --- | --- | --- | --- |
| A | `safe_version_replace` | Evidence Contract only | no |
| B | `safe_version_replace_guided` | A + Answer Guidance | no |
| C | `safe_version_replace_guided_with_retry_shadow` | B + Answer Candidate Contract + shadow verifier telemetry | no |

`retry_shadow` is telemetry only. It does not perform a second LLM call and must not be interpreted as real retry quality.

## Reviewed Protocol

- Dataset: `--balanced-small --common-limit 40 --hard-limit 40`
- Persona: `--persona-mode work`
- Modes: A/B/C above
- Real LLM: enabled
- Repeats: `1` for the medium incremental pass
- Target: C answer rate `>= 80%`
- Incremental signal: C vs B answer delta `>= 5pp` or B->C paired wins greater than paired losses
- Safety gates: grounding `100%`, forbidden violation `0%`, provider errors `0`, timeouts `0`
- Privacy: regular reports omit raw prompt/query/memory/full answer; raw answers are exported only to local `answer_debug/`

## Implementation Notes

- Added `--answer-debug-dir` to `scripts/run_memory_system_path_safe_version_eval.py`.
- Added one debug JSON per case/mode/repeat with raw answer, query, sanitized contract, post-check shadow, score failures, token/latency, and run metadata.
- Added `scripts/analyze_memory_p6o33_incremental_eval.py` for strict gate checks, uplift, paired comparison, category summaries, failure counts, and Markdown output.

## Verification

Commands:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_memory_system_path_safe_version_eval.py -q
PYTHONDONTWRITEBYTECODE=1 uv run python scripts/run_memory_system_path_safe_version_eval.py --help
PYTHONDONTWRITEBYTECODE=1 uv run python scripts/analyze_memory_p6o33_incremental_eval.py --help
```

Result:

- `28 passed in 37.44s`
- both CLI help commands exited `0`

## Real LLM Run

Run id:

- `p6o33_contract_incremental_medium_real_v1_20260801_191927`

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace /tmp/akashic-p6o33_contract_incremental_medium_real_v1_20260801_191927-workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o33_contract_incremental_medium_real_v1_20260801_191927 \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --enable-real-llm \
  --balanced-small \
  --common-limit 40 \
  --hard-limit 40 \
  --modes safe_version_replace,safe_version_replace_guided,safe_version_replace_guided_with_retry_shadow \
  --persona-mode work \
  --repeats 1 \
  --timeout-s 60 \
  --checkpoint-jsonl /tmp/akashic-p6o33_contract_incremental_medium_real_v1_20260801_191927.jsonl \
  --answer-debug-dir my_md/memory_optimization/eval_reports/p6o33_contract_incremental_medium_real_v1_20260801_191927/answer_debug \
  --early-infra-abort-count 5 \
  --early-infra-abort-rate 0.5 \
  --allow-infra-blocked-exit-zero
```

Analysis command:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python scripts/analyze_memory_p6o33_incremental_eval.py \
  --report-json my_md/memory_optimization/eval_reports/p6o33_contract_incremental_medium_real_v1_20260801_191927/system_path_safe_version_eval.json \
  --out-dir my_md/memory_optimization/eval_reports/p6o33_contract_incremental_medium_real_v1_20260801_191927
```

Artifacts:

- `my_md/memory_optimization/eval_reports/p6o33_contract_incremental_medium_real_v1_20260801_191927/system_path_safe_version_eval.json`
- `my_md/memory_optimization/eval_reports/p6o33_contract_incremental_medium_real_v1_20260801_191927/system_path_safe_version_eval.md`
- `my_md/memory_optimization/eval_reports/p6o33_contract_incremental_medium_real_v1_20260801_191927/p6o33_incremental_analysis.json`
- `my_md/memory_optimization/eval_reports/p6o33_contract_incremental_medium_real_v1_20260801_191927/p6o33_incremental_analysis.md`
- `my_md/memory_optimization/eval_reports/p6o33_contract_incremental_medium_real_v1_20260801_191927/answer_debug/` contains `240` local raw-answer debug JSON files.

## Data

Run shape:

| metric | value |
| --- | ---: |
| unique cases | 80 |
| case rows | 240 |
| modes | 3 |
| repeats | 1 |
| real LLM | true |
| fake provider | false |
| provider errors | 0 |
| timeouts | 0 |
| checkpoint input lines | 0 |
| malformed checkpoint lines | 0 |
| skipped from checkpoint | 0 |
| total tokens | 1,412,729 |
| avg tokens / row | 5,886.3708 |
| avg latency / row | 5,282.1667 ms |

Overall:

| Arm | Mode | Answer | Answer rate | Grounding | Forbidden | Would retry | Retry reasons | Avg tokens | Avg latency |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| A | `safe_version_replace` | 71 / 80 | 88.75% | 100.0% | 0.0% | 4 | `dsml_tool_markup_in_final_answer: 3`, `tool_markup_in_final_answer: 4`, `meta_action_final_answer: 2` | 5795.475 | 5789.9625 ms |
| B | `safe_version_replace_guided` | 74 / 80 | 92.5% | 100.0% | 0.0% | 3 | `dsml_tool_markup_in_final_answer: 3`, `tool_markup_in_final_answer: 3` | 5823.475 | 5352.9625 ms |
| C | `safe_version_replace_guided_with_retry_shadow` | 80 / 80 | 100.0% | 100.0% | 0.0% | 0 | none | 6040.1625 | 4703.575 ms |

Common vs hard:

| Split | Mode | Answer | Answer rate | Grounding | Forbidden |
| --- | --- | ---: | ---: | ---: | ---: |
| common | `safe_version_replace` | 36 / 40 | 90.0% | 100.0% | 0.0% |
| common | `safe_version_replace_guided` | 37 / 40 | 92.5% | 100.0% | 0.0% |
| common | `safe_version_replace_guided_with_retry_shadow` | 40 / 40 | 100.0% | 100.0% | 0.0% |
| hard | `safe_version_replace` | 35 / 40 | 87.5% | 100.0% | 0.0% |
| hard | `safe_version_replace_guided` | 37 / 40 | 92.5% | 100.0% | 0.0% |
| hard | `safe_version_replace_guided_with_retry_shadow` | 40 / 40 | 100.0% | 100.0% | 0.0% |

Incremental effect:

| Comparison | Delta | Paired wins | Paired losses | Paired ties |
| --- | ---: | ---: | ---: | ---: |
| A -> B | +3.75 pp | 5 | 2 | 73 |
| B -> C | +7.5 pp | 6 | 0 | 74 |

Failure reason counts:

| Mode | Failure reasons |
| --- | --- |
| `safe_version_replace` | `missing_expected_answer_term: 5`, `missing_expected_answer_term_group: 6`, `answer_language_not_chinese: 1` |
| `safe_version_replace_guided` | `missing_expected_answer_term: 3`, `missing_expected_answer_term_group: 4` |
| `safe_version_replace_guided_with_retry_shadow` | none |

## Failed Cases

There were `15` failed rows, all in A or B. C had no failed rows.

| Case | Failed mode | Failure | Observed pattern | C behavior |
| --- | --- | --- | --- | --- |
| `common_preference_recall_01` | A, B | missing answer term group | Answer acknowledged Chinese/pytest style but omitted the required structured fact group. | Directly stated Chinese +条目式/pytest style. |
| `common_preference_recall_02` | A, B | missing answer term group | Answer expanded style details or treated evidence as insufficient instead of selecting the expected fact group. | Directly stated Chinese +条目式/pytest style. |
| `common_preference_recall_04` | A, B | missing answer term group | Answer confirmed style but did not include the required expected group wording. | Directly stated Chinese +条目式/pytest style. |
| `common_tool_preference_04` | A | answer language not Chinese | Answer was only `pytest。`; scorer did not detect Chinese language. | Directly answered `优先用 pytest` with supporting fact. |
| `hard_graph_bridge_01` | B | missing expected term | Output became DSML pseudo tool-call instead of final answer. | Directly answered NetworkX entity graph + third-route recall + source_ref bridge. |
| `hard_duplicate_cleanup_01` | A | missing expected term/group | Answer said it would check memory instead of answering from contract. | Directly answered duplicate content should be merged, not retained. |
| `hard_graph_bridge_02` | A, B | missing expected term | Output became pseudo tool/read-file action instead of final answer. | Directly answered graph route connection to third-route recall and source_ref. |
| `hard_graph_bridge_03` | A | missing expected term | Output became pseudo workspace/file search action. | Directly answered NetworkX graph supports third-route recall and source_ref linkage. |
| `hard_duplicate_cleanup_03` | B | missing expected term/group | Output became pseudo read-file action. | Directly answered duplicate sentence is not retained; duplicates are merged. |
| `hard_preference_recall_04` | A | missing expected term/group | Output became pseudo `recall_memory` tool call. | Directly answered Chinese +条目式输出. |
| `hard_graph_bridge_04` | A | missing expected term | Output became pseudo read-file action. | Directly answered NetworkX graph as third-route recall support connected via source_ref. |

Root cause pattern:

- A/B still sometimes treat an answerable contract as a reason to inspect tools/files again.
- A/B can answer with useful but scorer-incomplete wording in preference-recall cases.
- C's Answer Candidate Contract + completion rule moved these cases to direct natural-language answers.
- C had `would_retry_count=0`, so the pass came from first-shot answer structure, not real retry.

## Conclusion

P6o33 passed the pre-registered medium gate.

- C reached the target: `80/80 = 100.0%`, above the `>=80%` goal.
- C improved over B by `+7.5 pp`, with paired `wins=6`, `losses=0`, `ties=74`.
- Safety gates passed: grounding `100.0%`, forbidden `0.0%`, provider errors `0`, timeouts `0`.
- The effective increment is Answer Candidate Contract / current_truth / contract-completion guidance under the current global prompt.
- This experiment does not validate real retry. Real retry is still not enabled and was not needed in this run.

Next recommended step: run a C-only stability repeat on the same 80-case set, or expand to a larger case pack, before treating `100%` as a stable production estimate.
