# Evidence Contract Conflict Governance

## Problem

P6o29 left three failed cases after the work persona improvement:

- `hard_graph_bridge_01`
- `hard_version_chain_01`
- `hard_preference_recall_02`

The failures were not recall failures. Each target case had governed `allowed_evidence`, enabled `Answer Candidate Contract`, `insufficient_evidence_fallback=false`, and `100%` grounding. The final answer failed because global history-retrieval rules sometimes caused the model to restart lookup or emit meta actions such as "先查/先翻/核实" and DSML-style pseudo `read_file` calls.

## Changes

- Added scoped Evidence Contract completion guidance in `memory2/system_path_safe_version_contract.py`.
  - Applies only when `insufficient_evidence_fallback=false` and `current_truth` is present.
  - Tells the model that retrieval and governance are already complete for this turn.
  - Blocks restarting recall/search/fetch/read memory files and pseudo tool-call final answers.
- Added a narrow global evidence-type boundary in `prompts/agent.py`.
  - Ordinary memory summaries and `RECENT_CONTEXT.md` remain candidate context.
  - Sufficient `Evidence Contract / allowed_evidence / current_truth / Answer Candidate Contract` is treated as already retrieved and governed answer evidence.
- Added post-check shadow classifications in `memory2/eval_answer_post_check.py`.
  - `dsml_tool_markup_in_final_answer`
  - `tool_markup_in_final_answer`
  - `meta_action_final_answer`
  - `answerable_evidence_contract_ignored`

## Plan Review Revisions

The initial plan was reviewed before implementation. Revisions made before code changes:

- Added a guard so completion guidance is not rendered for insufficient contracts.
- Added a negative prompt test for `insufficient_evidence_fallback=true`.
- Strengthened the global prompt test to require `Answer Candidate Contract` and `insufficient_evidence_fallback=false`.
- Changed `answerable_evidence_contract_ignored` so it does not depend on scorer misses; answerable contract plus meta/tool final answer is enough.
- Added a preflight check to prove the targeted hard slice contains the three target case ids.
- After implementation review, tightened `answerable_evidence_contract_ignored` to require `current_truth_count > 0`, with a negative regression test for enabled contracts that have no current truth.

## Test Method

Local unit and regression tests:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest \
  tests/test_memory_system_path_safe_version_contract.py::test_guided_retry_shadow_marks_contract_retrieval_complete_when_answerable \
  tests/test_memory_system_path_safe_version_contract.py::test_schema_first_shadow_marks_contract_retrieval_complete_when_answerable \
  tests/test_memory_system_path_safe_version_contract.py::test_guided_retry_shadow_does_not_mark_retrieval_complete_when_insufficient \
  -q -p no:cacheprovider

PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest \
  tests/test_memory_system_path_safe_version_contract.py -q -p no:cacheprovider

PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest \
  tests/test_message_lookup_tool.py::test_behavior_prompt_distinguishes_evidence_contract_from_memory_summary \
  -q -p no:cacheprovider

PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest \
  tests/test_memory_answer_post_check.py -q -p no:cacheprovider

PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest \
  tests/test_memory_system_path_safe_version_contract.py \
  tests/test_memory_answer_post_check.py \
  tests/test_message_lookup_tool.py \
  tests/test_memory_system_path_safe_version_eval.py \
  -q -p no:cacheprovider

PYTHONDONTWRITEBYTECODE=1 uv run python -m compileall \
  memory2/system_path_safe_version_contract.py \
  memory2/eval_answer_post_check.py \
  prompts/agent.py \
  tests/test_memory_system_path_safe_version_contract.py \
  tests/test_memory_answer_post_check.py \
  tests/test_message_lookup_tool.py
```

Real LLM target preflight:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python -c "from memory2.eval_quantitative_cases import build_quantitative_eval_cases; ids=[c.id for c in build_quantitative_eval_cases('hard', limit=20)]; targets={'hard_graph_bridge_01','hard_version_chain_01','hard_preference_recall_02'}; print([i for i in ids if i in targets]); raise SystemExit(0 if targets <= set(ids) else 1)"
```

P6o30 targeted hard-slice real LLM command:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace /tmp/akashic-p6o30-contract-conflict-targeted-workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o30_contract_conflict_targeted_real_v1 \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --enable-real-llm \
  --balanced-small \
  --common-limit 0 \
  --hard-limit 20 \
  --modes safe_version_replace_guided_with_retry_shadow \
  --persona-mode work \
  --timeout-s 60 \
  --checkpoint-jsonl /tmp/akashic-p6o30-contract-conflict-targeted-checkpoint.jsonl \
  --early-infra-abort-count 5 \
  --early-infra-abort-rate 0.5 \
  --allow-infra-blocked-exit-zero
```

Note: `--common-limit 0` means unlimited in the current CLI, not zero. The run therefore contained `60` cases: all common standard cases plus hard limit `20`. The three target hard cases were still present and are reported separately below.

P6o31 medium real LLM command:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace /tmp/akashic-p6o31-contract-conflict-medium-workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o31_contract_conflict_medium_real_v1 \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --enable-real-llm \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --modes safe_version_replace_guided_with_retry_shadow \
  --persona-mode work \
  --timeout-s 60 \
  --checkpoint-jsonl /tmp/akashic-p6o31-contract-conflict-medium-checkpoint.jsonl \
  --early-infra-abort-count 5 \
  --early-infra-abort-rate 0.5 \
  --allow-infra-blocked-exit-zero
```

## Data

| run | scope | cases | answer | grounding | forbidden | provider errors | timeouts | key retry reasons |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| P6o29 baseline | medium real LLM | 40 | 37/40 = 92.5% | 100.0% | 0.0% | 0 | 0 | `required_terms_missing: 3`, `answer_choice_group_missing: 1` |
| P6o30 | targeted hard-slice real LLM | 60 | 58/60 = 96.6667% | 100.0% | 1.6667% | 0 | 0 | `answer_choice_group_missing: 1` |
| P6o31 | medium real LLM | 40 | 40/40 = 100.0% | 100.0% | 0.0% | 0 | 0 | none |

P6o30 target-case results:

| case | passed | answer | grounding | forbidden | DSML/tool markup | meta action | retry reasons |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `hard_graph_bridge_01` | true | true | true | 0 | false | false | none |
| `hard_version_chain_01` | true | true | true | 0 | false | false | none |
| `hard_preference_recall_02` | true | true | true | 0 | false | false | none |

P6o31 target-case results:

| case | passed | failures | retry reasons |
| --- | --- | --- | --- |
| `hard_graph_bridge_01` | true | none | none |
| `hard_version_chain_01` | true | none | none |
| `hard_preference_recall_02` | true | none | none |

P6o30 non-target failed cases:

| case | failure | post-check classification |
| --- | --- | --- |
| `common_preference_recall_02` | `missing_expected_answer_term_group` | `answer_choice_group_missing` |
| `hard_style_preference_01` | `found_forbidden_answer_term` | no post-check retry reason; forbidden scorer caught it |

P6o31 failed cases:

None.

## Final Local Verification

- Focused local regression after review fix: `70 passed in 31.15s`.
- Compile check after review fix: `compileall` exit `0`.
- Review fix did not change prompts or LLM behavior; it only narrowed a shadow-only post-check classification, so P6o30/P6o31 real LLM reports were not rerun.

## Conclusion

Scheme C passed the targeted conflict-family gate and improved the medium real LLM result from P6o29 `37/40 = 92.5%` to P6o31 `40/40 = 100.0%`.

The specific prompt-conflict failures were resolved in both P6o30 and P6o31:

- no DSML pseudo tool-call final answers;
- no tool-markup final answers;
- no "先查/先翻/核实" meta-action final answers;
- no `required_terms_missing` or `answer_choice_group_missing` on the three target cases.

The local post-check now also classifies future recurrences of this failure family instead of collapsing them into generic scorer misses.
