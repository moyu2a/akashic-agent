# P6o33 Contract Incremental Medium Real Eval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a medium real-LLM incremental comparison for `safe_version_replace`, `safe_version_replace_guided`, and `safe_version_replace_guided_with_retry_shadow`.

**Architecture:** Keep the existing system-path eval report private by default, add a local debug-only raw answer artifact path for failure review, then run a strict analysis script over the generated JSON report. The experiment attributes effects only to incremental prompt/contract packages under the current global prompt at HEAD.

**Tech Stack:** Python 3, pytest, existing `scripts/run_memory_system_path_safe_version_eval.py`, existing `memory2.eval_system_path_safe_version` report schema.

## Global Constraints

- Do not enable real retry.
- Keep production defaults unchanged.
- Keep regular JSON/Markdown reports free of raw prompt, raw query, raw memory summary, and full answer text.
- Treat `retry_shadow` as telemetry only.
- Record raw answers only under the local eval artifact directory.
- Do not touch unrelated untracked `my_md/memory_optimization/eval_reports/p6o13_system_path_real_llm_validation_v1/`.

---

### Task 1: Add Debug-Only Raw Answer Export

**Files:**
- Modify: `memory2/eval_system_path_safe_version.py`
- Modify: `scripts/run_memory_system_path_safe_version_eval.py`
- Test: `tests/test_memory_system_path_safe_version_eval.py`

**Interfaces:**
- Adds optional CLI flag `--answer-debug-dir`.
- Adds optional `answer_debug_dir: Path | None` and `run_metadata: dict[str, object] | None` to `run_system_path_safe_version_cases`.
- Produces one JSON file per case/mode/repeat only when the flag is set.

- [x] Write a failing CLI test for `--answer-debug-dir`.
- [x] Verify the test fails because the flag is missing.
- [x] Implement debug-only JSON export.
- [x] Verify the test passes.

### Task 2: Add P6o33 Incremental Analysis

**Files:**
- Create: `scripts/analyze_memory_p6o33_incremental_eval.py`
- Test: `tests/test_memory_system_path_safe_version_eval.py`

**Interfaces:**
- CLI: `--report-json`, `--out-dir`, optional `--target-answer-rate`.
- Outputs: `p6o33_incremental_analysis.json` and `p6o33_incremental_analysis.md`.

- [x] Write failing tests for uplift, paired comparison, category summary, and mode-set rejection.
- [x] Verify tests fail because the script is missing.
- [x] Implement strict report gate and analysis rendering.
- [x] Verify tests pass.

### Task 3: Run Verification

**Files:**
- Read: test output only.

- [x] Run targeted system-path tests:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/test_memory_system_path_safe_version_eval.py -q
```

- [x] Run CLI help smoke:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python scripts/run_memory_system_path_safe_version_eval.py --help
PYTHONDONTWRITEBYTECODE=1 uv run python scripts/analyze_memory_p6o33_incremental_eval.py --help
```

### Task 4: Run Real LLM Eval And Document

**Files:**
- Create: `my_md/memory_optimization/eval_reports/p6o33_contract_incremental_medium_real_v1_<timestamp>/`
- Create: `my_md/memory_optimization/18-p6o33-contract-incremental-medium-real-eval.md`

- [x] Run 80-case, 3-mode, real-LLM eval with `--persona-mode work`, `--repeats 1`, and `--answer-debug-dir`.
- [x] Run P6o33 analysis script.
- [x] Document method, commands, data tables, failed cases, raw artifact paths, and conclusion.
- [ ] Commit code, tests, plan, report, and eval artifacts.
