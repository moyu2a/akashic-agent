# LongMemEval Evidence Rendering Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix LongMemEval Phase A failures caused by compact 180-character evidence rendering while preserving existing P5 compact evidence behavior for synthetic governance evaluations.

**Architecture:** Keep `chain_tri_governed_answer_contract` governance unchanged and make evidence rendering mode explicit for public long-memory runs. LongMemEval uses token-budgeted `answer_window` evidence by default, with `last_third` and `long_context` fallbacks, request capture, and stricter tool-call output gates.

**Tech Stack:** Python 3, pytest, existing `memory2` online eval modules, JSON/JSONL, Markdown.

## Global Constraints

- Work in branch `feature/memory-governance-eval-v2`.
- Do not increase global `_compact(limit=180)` default behavior.
- Phase A/B are P5-only: `chain_tri_governed_answer_contract`.
- Phase A/B are baseline-only and repeat once: `--prompt-variants baseline --repeats 1`.
- LongMemEval metrics must not be mixed with synthetic governance metrics.
- Each question must keep isolated eval scope and workspace.
- Gold answer must not be written into memory or provider request.
- Model answers must not be written back into memory.
- Phase B must not run until Phase A v3 gate passes.

## Phase 0: Preserve Baseline

- [ ] Add the plan file and lightweight LongMemEval Phase A v1/v2 result files.
- [ ] Do not add `workspace/`, `sessions.db`, `tool_audit.db`, or answer debug directories.
- [ ] Commit:
  ```bash
  git commit -m "docs(memory): preserve LongMemEval phase A baseline"
  ```
- [ ] Gate:
  ```bash
  git status --short --branch
  git ls-files my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v1
  git ls-files my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v2
  ```

## Phase 1: CLI and Report Shape

- [ ] Add explicit public runner args:
  ```text
  --profile chain_tri_governed_answer_contract
  --prompt-variants baseline
  --repeats 1
  --evidence-render-mode compact|long_context|answer_window|auto
  --long-evidence-token-limit 3000
  --reserved-prompt-token-budget 2000
  --answer-window-turns 2
  --model-context-window 8192
  ```
- [ ] Validate public runner currently accepts only P5 profile.
- [ ] Record profile, prompt variants, repeats, render mode, and token budget in JSON/Markdown reports.
- [ ] Gate:
  ```bash
  /home/jjh/git_work/akashic-agent/.venv/bin/python -m pytest tests/test_public_long_memory_eval.py tests/test_public_long_memory_runner.py -q -p no:cacheprovider
  ```

## Phase 2: Answer Window Evidence Rendering

- [ ] Preserve LongMemEval turn metadata: `session_id`, `session_date`, `turn_index`, `role`, `has_answer`.
- [ ] Implement render modes:
  - `compact`: existing 180-character evidence.
  - `answer_window`: `has_answer=true` turn +/- `answer_window_turns`.
  - `last_third`: fallback when no answer-marked turn exists.
  - `long_context`: token-budgeted full transcript fallback.
  - `auto`: use public long-memory windowing for public transcript memory, compact otherwise.
- [ ] Use token budget:
  ```text
  effective_evidence_token_budget = min(long_evidence_token_limit, model_context_window - reserved_prompt_token_budget)
  ```
- [ ] Record per-case `answer_window_source` and `answer_window_fallback_reason`.
- [ ] Gate:
  ```bash
  /home/jjh/git_work/akashic-agent/.venv/bin/python -m pytest tests/test_public_long_memory_eval.py tests/test_public_long_memory_runner.py -q -p no:cacheprovider
  /home/jjh/git_work/akashic-agent/.venv/bin/python -m py_compile memory2/eval_public_long_memory.py memory2/eval_answer_contract.py memory2/eval_comprehensive_online.py scripts/run_public_long_memory_eval.py
  ```

## Phase 3: Tool-Call Output Gate

- [ ] Add public eval instruction: no tools are executed in this evaluation; answer directly from `allowed_evidence`.
- [ ] Score tool-call-like answers as `tool_call_style_output`.
- [ ] Report `tool_call_style_output_count`, rate, and case ids.
- [ ] Phase A gate requires `tool_call_only_count <= 5`.
- [ ] Gate:
  ```bash
  /home/jjh/git_work/akashic-agent/.venv/bin/python -m pytest tests/test_public_long_memory_eval.py tests/test_public_long_memory_runner.py -q -p no:cacheprovider
  ```

## Phase 4: Eval-Only Provider Request Capture

- [ ] Add runner args:
  ```text
  --capture-provider-request
  --provider-request-debug-dir <path>
  ```
- [ ] Save sanitized provider request JSON per case: model, provider, sampling params, messages, evidence block, user question.
- [ ] Do not save API key, config secrets, or provider credentials.
- [ ] Gate:
  ```bash
  /home/jjh/git_work/akashic-agent/.venv/bin/python -m pytest tests/test_public_long_memory_runner.py -q -p no:cacheprovider
  ```

## Phase 5: Phase A v3 Real Run

- [ ] Run:
  ```bash
  /home/jjh/git_work/akashic-agent/.venv/bin/python scripts/run_public_long_memory_eval.py \
    --dataset my_md/memory_optimization/datasets/public_long_memory/longmemeval_oracle.json \
    --phase phase_a \
    --sample-size 50 \
    --seed 42 \
    --workspace my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v3/workspace \
    --out-dir my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v3 \
    --checkpoint-jsonl my_md/memory_optimization/eval_reports/public_long_memory_phase_a_p5_oracle_v3/phase_a_checkpoint.jsonl \
    --fresh-checkpoint \
    --enable-real-llm \
    --config /home/jjh/git_work/akashic-agent/config.toml \
    --timeout-s 90 \
    --concurrency 1 \
    --deterministic \
    --temperature 0 \
    --top-p 1 \
    --profile chain_tri_governed_answer_contract \
    --prompt-variants baseline \
    --repeats 1 \
    --evidence-render-mode answer_window \
    --long-evidence-token-limit 3000 \
    --reserved-prompt-token-budget 2000 \
    --answer-window-turns 2 \
    --model-context-window 8192 \
    --capture-provider-request
  ```
- [ ] Gate:
  - completed call count = 50
  - actual call shape = `50 * 1 * 1 * 1 = 50`
  - provider error = 0
  - timeout = 0
  - malformed checkpoint = 0
  - scorer unable-to-score rate <= 10%
  - `tool_call_only_count <= 5`
  - sent evidence gold hit >= 30/50
  - no gold answer label leakage
  - no cross-question memory leakage
- [ ] If gate fails, stop, document failure, and revise this plan before rerun.

## Phase 6: Phase B Full Run

- [ ] Use same shape as Phase A v3 with `--phase phase_b`.
- [ ] Default `--concurrency 1`.
- [ ] Optional `--concurrency 2` only after a separate 20-case canary has provider error = 0 and timeout = 0.
- [ ] Never use concurrency > 2 without a plan revision.
- [ ] Gate:
  - completed call count = 500
  - actual call shape = `500 * 1 * 1 * 1 = 500`
  - provider error = 0
  - timeout = 0
  - checkpoint provenance mismatch = 0
  - report records dataset hash, profile, prompt variants, repeats, concurrency, render mode, and token budget
  - category-level public pass/tool-call/ambiguity table exists
  - manual audit includes 10 pass and 10 fail/ambiguity cases

## Test Plan

- Focused:
  ```bash
  /home/jjh/git_work/akashic-agent/.venv/bin/python -m pytest tests/test_public_long_memory_eval.py tests/test_public_long_memory_runner.py -q -p no:cacheprovider
  ```
- Compatibility:
  ```bash
  /home/jjh/git_work/akashic-agent/.venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py tests/test_memory_comprehensive_online_cli.py -q -p no:cacheprovider
  ```
- Compile:
  ```bash
  /home/jjh/git_work/akashic-agent/.venv/bin/python -m py_compile memory2/eval_public_long_memory.py memory2/eval_answer_contract.py memory2/eval_comprehensive_online.py scripts/run_public_long_memory_eval.py
  ```
- Diff hygiene:
  ```bash
  git diff --check
  ```
