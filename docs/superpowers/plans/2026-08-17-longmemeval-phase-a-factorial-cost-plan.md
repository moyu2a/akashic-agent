# LongMemEval Phase A 8-Combination Governance Ablation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a Phase A LongMemEval 8-combination governance ablation that compares accuracy, prompt/completion/total token cost, and end-to-end latency.

**Architecture:** Keep tri-retrieval + RRF as the fixed base, then toggle candidate governance, structured evidence, and answer guidance as independent profile flags. Extend the public LongMemEval runner from P5-only to multi-profile reports while keeping existing single-profile behavior compatible.

**Tech Stack:** Python 3.14, pytest, existing `memory2` eval modules, existing online LLM provider config.

## Global Constraints

- Work on branch `feature/longmemeval-phase-a-factorial-cost`.
- Do not commit unrelated user-local files from the main checkout.
- Phase A sample uses `--seed 42` and `--sample-size 50` for comparability with Phase A v5/v7.
- Prompt variant is `baseline`; repeats is `1`; concurrency is `2`.
- Token cost is reported separately as provider `prompt_tokens`, `completion_tokens`, and `total_tokens`.
- Latency is runner-observed per-case end-to-end wall-clock latency from `time.perf_counter()`, reported as avg/p50/p95.
- No dollar-cost conversion in this run.
- Final correctness uses external LLM Judge; strict/static scoring is regression/package signal only.
- No LongMemEval case-specific fixes.

---

## Phase 0: Branch And Baseline

- [x] Create branch/worktree from `main`.
- [x] Save this plan.
- [x] Commit the plan file.

Gate:
- Current branch is `feature/longmemeval-phase-a-factorial-cost`.
- `git status` excludes unrelated user-local files.

## Phase 1: Add 8 Factorial Profiles

Profiles:

| profile | C | S | A |
| --- | ---: | ---: | ---: |
| `tri_rrf` | 0 | 0 | 0 |
| `tri_rrf_candidate` | 1 | 0 | 0 |
| `tri_rrf_structured` | 0 | 1 | 0 |
| `tri_rrf_answer` | 0 | 0 | 1 |
| `tri_rrf_candidate_structured` | 1 | 1 | 0 |
| `tri_rrf_candidate_answer` | 1 | 0 | 1 |
| `tri_rrf_structured_answer` | 0 | 1 | 1 |
| `tri_rrf_candidate_structured_answer` | 1 | 1 | 1 |

- [x] Add profile specs and compatibility aliases.
- [x] Add tests for profile flags and unknown profile validation.
- [x] Commit.

## Phase 2: Implement Factorial Evidence Rendering

- [x] Implement evidence behavior for all 8 profiles.
- [x] Keep provider request snapshots gold-free.
- [x] Ensure debug artifact names include profile.
- [x] Add fake-provider tests for `1 case * 8 profiles`.
- [x] Commit.

## Phase 3: Extend Public LongMemEval Runner

- [x] Add `--profiles` while keeping `--profile`.
- [x] Update call shape and checkpoint provenance for profile lists.
- [x] Add per-profile summaries with prompt/completion/total token and avg/p50/p95 latency.
- [x] Add profile deltas vs `tri_rrf`.
- [x] Update Markdown report with cost/accuracy tables and metric definitions.
- [x] Run `pytest tests/test_public_long_memory_eval.py tests/test_public_long_memory_runner.py`.
- [x] Commit.

## Phase 4: Run Phase A 400-Call Online Test

Command:

```bash
PROFILES="tri_rrf,tri_rrf_candidate,tri_rrf_structured,tri_rrf_answer,tri_rrf_candidate_structured,tri_rrf_candidate_answer,tri_rrf_structured_answer,tri_rrf_candidate_structured_answer"

.venv/bin/python scripts/run_public_long_memory_eval.py \
  --dataset my_md/memory_optimization/datasets/public_long_memory/longmemeval_oracle.json \
  --phase phase_a \
  --sample-size 50 \
  --seed 42 \
  --profiles "$PROFILES" \
  --prompt-variants baseline \
  --repeats 1 \
  --evidence-render-mode answer_window \
  --long-evidence-token-limit 3000 \
  --reserved-prompt-token-budget 2000 \
  --answer-window-turns 2 \
  --model-context-window 8192 \
  --enable-real-llm \
  --config config.toml \
  --timeout-s 60 \
  --concurrency 2 \
  --capture-provider-request \
  --workspace my_md/memory_optimization/eval_reports/public_long_memory_phase_a_factorial_v1/workspace \
  --out-dir my_md/memory_optimization/eval_reports/public_long_memory_phase_a_factorial_v1 \
  --checkpoint-jsonl my_md/memory_optimization/eval_reports/public_long_memory_phase_a_factorial_v1/phase_a_factorial_checkpoint.jsonl \
  --fresh-checkpoint
```

Gate:
- `completed_call_count = 400`
- `actual_call_shape = 50 * 8 * 1 * 1 = 400`
- `sampling.seed = 42`
- provider errors, timeouts, malformed checkpoint lines, and provenance mismatches are zero after any required resume.
- Provider request, structured evidence, and answer debug artifacts each cover all 400 calls.

## Phase 5: Generate Review Package

- [x] Generate profile summary, case review index, pass/fail review docs, and external Judge instructions.
- [x] Include C/S/A flags, model answer, gold, evidence paths, provider request path, token fields, latency, language mismatch, and failure attribution for each row.
- [x] Commit.

## Phase 6: External LLM Judge And Adjusted Metrics

- [ ] Record external Judge raw output. Pending external Judge output.
- [ ] Generate case index and adjusted summary. Pending external Judge output.
- [ ] Report adjusted and conservative pass rate per profile. Pending external Judge output.
- [ ] Report prompt/completion/total token and avg/p50/p95 latency per profile. Cost/latency are available in static summary; adjusted correctness pending external Judge output.
- [ ] Commit. Pending external Judge output.

## Phase 7: Final Verification And Push

- [x] Run targeted eval tests.
- [ ] Run full pytest if time allows. Not run; targeted public LongMemEval/comprehensive/profile suite passed.
- [x] Verify report assertions.
- [x] Push `feature/longmemeval-phase-a-factorial-cost`.
