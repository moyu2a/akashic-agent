# P6o36 Memory Answer Governance Fixes

## Goal

Address the three P6o35 R3 failure modes without changing retrieval or production defaults.

Scope:

- forbidden old-term wording in final answers;
- one answer-choice omission row;
- one meta-action shadow false-positive row.

## Root Cause

- Recall was not the bottleneck: P6o35 grounding was `100.0%` across `240` real LLM rows.
- The two forbidden rows were final-answer wording failures: the answer repeated old/stale style terms that should not appear in the final answer.
- The answer-choice row had enough allowed evidence, but the final answer omitted one required fact group.
- The meta-action shadow row passed answer scoring, but the classifier still treated a low-risk future-facing phrase as retry eligible.
- The answer-choice omission is not necessarily only an agent bug: the agent/prompt can leave too much freedom, and the model can still compress, generalize, or randomly drop one expected fact group.

## Changes

- Strengthened `guided_retry_shadow` answer guidance:
  - only state current truth from `current_truth` and `allowed_evidence`;
  - do not repeat old, stale, or superseded values verbatim;
  - when replacement history matters, say `旧版本已失效` without naming the old value.
- Calibrated post-check meta-action classification:
  - passing answers with low-risk meta phrasing remain broad telemetry only;
  - action-only meta answers still remain retry eligible;
  - DSML/tool markup remains retry eligible.
- Added an eval-only targeted retry pilot:
  - applies only when `retry_if_needed_eligible=true` and no blocked reasons exist;
  - prioritizes `answer_choice_group_missing`, then required terms/language/tool/meta reasons;
  - never retries forbidden/stale/context safety blocked rows;
  - makes at most one additional LLM call per eval row;
  - keeps production defaults unchanged.

## Verification

Focused pytest:

```bash
uv run pytest tests/test_memory_answer_post_check.py tests/test_memory_system_path_safe_version_contract.py tests/test_memory_system_path_safe_version_eval.py -q
```

Result:

```text
64 passed in 41.00s
```

Fake-provider smoke:

```bash
uv run python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace /tmp/akashic-p6o36-memory-governance-fake-workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o36_memory_answer_governance_fake_v1 \
  --fake-provider \
  --balanced-small \
  --common-limit 2 \
  --hard-limit 2 \
  --modes safe_version_replace_guided_with_retry_shadow \
  --persona-mode work
```

Artifacts:

- `my_md/memory_optimization/eval_reports/p6o36_memory_answer_governance_fake_v1/system_path_safe_version_eval.json`
- `my_md/memory_optimization/eval_reports/p6o36_memory_answer_governance_fake_v1/system_path_safe_version_eval.md`

Fake smoke data:

| metric | value |
| --- | ---: |
| case rows | 4 |
| unique cases | 4 |
| real LLM | false |
| fake provider | true |
| provider errors | 0 |
| timeouts | 0 |
| malformed checkpoint lines | 0 |
| grounding rate | 100.0% |
| forbidden rate | 0.0% |
| answer rate | 0.0% |
| retry applied rows | 4 |
| avg tokens / row | 60.0 |

Interpretation:

- `answer rate = 0.0%` is expected for this fake provider because scripted answers are not designed to satisfy the quantitative answer terms.
- `avg tokens / row = 60.0` is expected because each fake row makes the original 30-token call plus one 30-token targeted retry.
- The smoke validates wiring, retry field shape, provider-call behavior, and report generation, not real answer quality.

## Conclusion

This closes the local governance bug class for unit/fake validation. The project now has a controlled eval-only path to test whether targeted answer retry can repair answer omissions while leaving forbidden/stale safety rows blocked.

The third failure class should be treated as a joint agent/model issue until a real LLM rerun proves otherwise. Guide can reduce it, but prompt alone does not guarantee coverage of every required answer group.

Production retry remains off. The next gate should be a targeted real LLM rerun on the P6o35 failed/interesting rows plus a small stability sample, and it should require zero forbidden rows and no answer-rate regression before any production default changes.

## Small Real LLM A/B: Tri Retrieval Vs Governed Evidence Contract

Purpose:

- Compare the original tri-retrieval answer path with the governed answer path under the same `comprehensive online eval` runner.
- Measure answer quality, grounding, forbidden violations, token cost, and latency together.
- Keep the comparison narrow: only compare original tri retrieval against tri retrieval plus candidate governance, structured evidence, and answer guidance.

Important boundary:

- This is an evaluation runner result, not proof that the production AgentLoop has already loaded the full governed path by default.
- `chain_tri_governed_answer_contract` is still marked `eval_only=true`, `oracle_protected=true`, and `uses_fixture_expected_ids=true` in report metadata.

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-tri-vs-governed-small-workspace \
  --out-dir my_md/memory_optimization/eval_reports/tri_vs_governed_cost_quality_small_real_v1 \
  --config config.toml \
  --enable-real-llm \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --profiles chain_tri_retrieval,chain_tri_governed_answer_contract \
  --prompt-variants baseline \
  --repeats 1 \
  --timeout-s 60 \
  --checkpoint-jsonl /tmp/akashic-tri-vs-governed-cost-quality-small-real-v1.jsonl \
  --include-answer-debug
```

Artifacts:

- `my_md/memory_optimization/eval_reports/tri_vs_governed_cost_quality_small_real_v1/memory_comprehensive_online_eval.json`
- `my_md/memory_optimization/eval_reports/tri_vs_governed_cost_quality_small_real_v1/memory_comprehensive_online_eval.md`
- checkpoint rows: `/tmp/akashic-tri-vs-governed-cost-quality-small-real-v1.jsonl`
- answer debug files: `/tmp/akashic-tri-vs-governed-small-workspace/answer_debug/`

Run shape:

| item | value |
| --- | ---: |
| unique cases | 40 |
| common cases | 20 |
| hard cases | 20 |
| profiles | 2 |
| repeats | 1 |
| real LLM calls | 80 |
| completed calls | 80 |
| provider errors | 0 |
| timeouts | 0 |

Profile results:

| profile | meaning | calls | answer success | grounding | forbidden cases | failed calls | avg tokens | total tokens | avg latency |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `chain_tri_retrieval` | original semantic + keyword + source tri retrieval | 40 | 18/40 = 45.00% | 40/40 = 100.00% | 5/40 = 12.50% | 22 | 6351.35 | 254054 | 10240.98 ms |
| `chain_tri_governed_answer_contract` | tri retrieval + candidate governance + structured evidence + answer guidance | 40 | 40/40 = 100.00% | 40/40 = 100.00% | 0/40 = 0.00% | 0 | 6956.43 | 278257 | 10707.05 ms |

Governed path delta vs original tri retrieval:

| metric | delta |
| --- | ---: |
| answer success rate | +55.00 pp |
| forbidden violation rate | -12.50 pp |
| avg total tokens | +605.08 tokens |
| avg total token ratio | +9.53% |
| avg latency | +466.07 ms |
| avg latency ratio | +4.55% |

Failure attribution:

| profile | failed calls | unique failed cases | failure reasons |
| --- | ---: | ---: | --- |
| `chain_tri_retrieval` | 22 | 22 | `missing_expected_answer_term` x20; `missing_expected_answer_term_group` x20; `found_forbidden_answer_term` x5; `answer is not detected as Chinese` x1 |
| `chain_tri_governed_answer_contract` | 0 | 0 | none |

Token and latency analysis:

| metric | original tri retrieval | governed path | delta |
| --- | ---: | ---: | ---: |
| avg prompt tokens | 5314.35 | 5881.75 | +567.40 |
| avg completion tokens | 1037.00 | 1074.68 | +37.68 |
| avg total tokens | 6351.35 | 6956.43 | +605.08 |
| avg answer length | 205.18 chars | 135.72 chars | -69.45 chars |
| avg used memory ids | 5.35 | 5.00 | -0.35 |
| avg evidence block length | 355.4 chars | 2154.6 chars | +1799.2 chars |
| median evidence block length | 380 chars | 2264 chars | +1884 chars |

Why token cost increased:

- The increase is mainly prompt-side input cost, not answer-side output cost.
- Governed answers were shorter on average, but the governed evidence block was much longer.
- Original tri retrieval injects a compact list of memory ids and summaries.
- Governed retrieval injects an Evidence Contract with `allowed_evidence`, `likely_relevant_evidence`, stale/conflict/active-version fields, forbidden boundary fields, fallback flags, and evidence id lists.
- The average prompt-token delta was `+567.40`, while the average completion-token delta was only `+37.68`; this explains almost all of the `+605.08` average total-token increase.

Why latency increased:

- The average latency increase was modest: `+466.07 ms`, or `+4.55%`.
- Latency did not rise in every paired case. In the 40 paired cases, the governed path was slower in 18 cases and faster in 22 cases.
- A few slow cases pulled the average upward, especially rows where completion tokens also increased:

| case | total token delta | latency delta |
| --- | ---: | ---: |
| `hard_version_chain_02` | +1985 | +16099 ms |
| `common_tri_rrf_01` | +1893 | +16023 ms |
| `hard_duplicate_cleanup_02` | +2094 | +15443 ms |
| `hard_graph_bridge_01` | +1982 | +13471 ms |
| `hard_cross_scope_02` | +1934 | +12029 ms |

Conclusion:

- The small real LLM A/B gate passed.
- The governed path substantially improved answer success and eliminated forbidden violations in this test set.
- The cost increase is explainable and mostly comes from structured Evidence Contract input.
- The latency increase is smaller than the token increase and partly shaped by provider/model variance plus a few slow rows.
- The next optimization target should be Evidence Contract compression: omit empty sections, merge duplicate id lists, and only include stale/conflict/forbidden fields when present.
