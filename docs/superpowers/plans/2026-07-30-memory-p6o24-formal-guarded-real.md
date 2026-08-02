# P6o-24 Formal Guarded Real Experiment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the previously errored P6o-20 real-LLM experiment with a fresh guarded 40-case run and record interpretable answer-quality data.

**Architecture:** This is an eval execution plan, not a production code change. It uses the P6o-22 infra guard in `scripts/run_memory_system_path_safe_version_eval.py`, fresh artifacts under `my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/`, detail export via `scripts/export_memory_p6o20_answer_details.py`, and a written report with method, commands, data, movement, retry-shadow summary, and final gate decision.

**Tech Stack:** Python 3.11+, existing memory eval scripts, real LLM provider from `/home/jjh/git_work/akashic-agent/config.toml`, JSON/Markdown/JSONL artifacts.

## Global Constraints

- Do not change production defaults, retrieval, prompts, graph behavior, retry behavior, or memory writes.
- Do not reuse the P6o-20 checkpoint.
- Use fresh workspace, fresh out-dir, and fresh checkpoint.
- Use P6o-22 infra guard: `--early-infra-abort-count 3 --early-infra-abort-rate 0.5`.
- Quality interpretation is allowed only if exit code is `0`, no `blocked_status.json` exists in the primary or rebuild directory, `case_count=120`, `unique_case_count=40`, `timeout_count=0`, `provider_error_count=0`, `empty_answer_count=0`, `malformed_checkpoint_line_count=0`, checkpoint row count is `120`, rebuild `checkpoint_input_count=120`, and rebuild metrics match the primary report.
- If infra guard blocks the run, stop interpreting quality and record `infra_blocked`.
- Reports must not include raw query, prompt, memory summary, full answer, API key, authorization token, or complete response.

---

## Preflight Freshness Check

Before Task 1, run:

```bash
test ! -e my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/real_balanced_40/checkpoint.jsonl
test ! -e my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/real_balanced_40
test ! -e /tmp/akashic-p6o24-formal-real/workspace
```

Expected: all commands exit `0`.

If any command fails, stop and choose a new versioned directory suffix before running the formal matrix. Do not delete existing artifacts to force freshness.

### Task 1: Run Formal Guarded Real Matrix

**Files:**
- Create: `my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/real_balanced_40/`

**Interfaces:**
- Consumes: `scripts/run_memory_system_path_safe_version_eval.py`
- Produces:
  - `real_balanced_40/system_path_safe_version_eval.json`
  - `real_balanced_40/system_path_safe_version_eval.md`
  - `real_balanced_40/checkpoint.jsonl`
  - optional `real_balanced_40/blocked_status.json` only if infra-blocked

- [x] **Step 1: Run the formal matrix**

Run:

```bash
.venv/bin/python scripts/run_memory_system_path_safe_version_eval.py --workspace /tmp/akashic-p6o24-formal-real/workspace --out-dir my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/real_balanced_40 --config /home/jjh/git_work/akashic-agent/config.toml --enable-real-llm --case-pack standard --balanced-small --common-limit 20 --hard-limit 20 --modes safe_version_replace,safe_version_replace_guided,safe_version_replace_guided_with_retry_shadow --timeout-s 30 --repeats 1 --checkpoint-jsonl my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/real_balanced_40/checkpoint.jsonl --early-infra-abort-count 3 --early-infra-abort-rate 0.5
```

Expected:

- Exit `0` for interpretable quality data, or exit `2` with `blocked_status.json` for infra-blocked data.
- If exit `2`, stop after Task 2 and record infra-blocked; do not run detail export as quality analysis.

- [x] **Step 2: Assert primary quality gate**

Run only if Step 1 exits `0`:

```bash
.venv/bin/python -c "import json, os; base='my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/real_balanced_40'; d=json.load(open(base+'/system_path_safe_version_eval.json')); m=d['metrics']; empty=sum(1 for r in d['cases'] if int(r.get('answer_length') or 0)==0); assert not os.path.exists(base+'/blocked_status.json'); assert m['case_count']==120, m; assert m['unique_case_count']==40, m; assert m['mode_count']==3, m; assert m['timeout_count']==0, m; assert m['provider_error_count']==0, m; assert m['malformed_checkpoint_line_count']==0, m; assert empty==0, empty; assert m['token_metrics_available'] is True; print({'answer_rule_pass_rate': m['answer_rule_pass_rate'], 'memory_grounding_pass_rate': m['memory_grounding_pass_rate'], 'forbidden_violation_rate': m['forbidden_violation_rate'], 'avg_latency_ms': m['avg_latency_ms'], 'mode_summaries': m['mode_summaries'], 'empty_answer_count': empty})"
```

Expected for quality run:

- `blocked_exists False`
- `case_count 120`
- `unique_case_count 40`
- `timeout_count 0`
- `provider_error_count 0`
- `empty_answer_count 0`

- [x] **Step 3: Assert checkpoint row count**

Run:

```bash
.venv/bin/python -c "from pathlib import Path; path=Path('my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/real_balanced_40/checkpoint.jsonl'); count=sum(1 for line in path.read_text(encoding='utf-8').splitlines() if line.strip()); assert count==120, count; print({'checkpoint_line_count': count})"
```

Expected for quality run: `120`.

---

### Task 2: Rebuild Checkpoint With Guard

**Files:**
- Create: `my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/checkpoint_guarded_rebuild/`

**Interfaces:**
- Consumes: `real_balanced_40/checkpoint.jsonl`
- Produces:
  - `checkpoint_guarded_rebuild/system_path_safe_version_eval.json`
  - `checkpoint_guarded_rebuild/system_path_safe_version_eval.md`
  - optional `checkpoint_guarded_rebuild/blocked_status.json`

- [x] **Step 1: Run report-only guarded rebuild**

Run:

```bash
.venv/bin/python scripts/run_memory_system_path_safe_version_eval.py --out-dir my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/checkpoint_guarded_rebuild --enable-real-llm --checkpoint-jsonl my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/real_balanced_40/checkpoint.jsonl --checkpoint-report-only --early-infra-abort-count 3 --early-infra-abort-rate 0.5
```

Expected:

- Exit `0` for quality run.
- Exit `2` and `blocked_status.json` for infra-blocked run.

- [x] **Step 2: Assert primary and rebuild metrics**

Run only if Step 1 exits `0`:

```bash
.venv/bin/python -c "import json, os; primary='my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/real_balanced_40'; rebuild='my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/checkpoint_guarded_rebuild'; assert not os.path.exists(primary+'/blocked_status.json'); assert not os.path.exists(rebuild+'/blocked_status.json'); a=json.load(open(primary+'/system_path_safe_version_eval.json'))['metrics']; b=json.load(open(rebuild+'/system_path_safe_version_eval.json'))['metrics']; keys=['case_count','unique_case_count','timeout_count','provider_error_count','answer_rule_pass_rate','memory_grounding_pass_rate','forbidden_violation_rate']; assert all(a[k]==b[k] for k in keys), {k:(a[k], b[k]) for k in keys}; assert b['checkpoint_input_count']==120, b; assert b['malformed_checkpoint_line_count']==0, b; print({k:(a[k], b[k]) for k in keys} | {'rebuild_checkpoint_input_count': b['checkpoint_input_count'], 'rebuild_malformed_checkpoint_line_count': b['malformed_checkpoint_line_count']})"
```

Expected for quality run: command exits `0`, listed values match, rebuild `checkpoint_input_count=120`, and rebuild `malformed_checkpoint_line_count=0`.

If Task 1 or Task 2 exits `2`, skip quality comparisons and record only blocked status, infra counts, checkpoint line count, and blocked reason.

---

### Task 3: Export Per-Case Detail And Movement

**Files:**
- Create: `my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/answer_details/`

**Interfaces:**
- Consumes: `real_balanced_40/system_path_safe_version_eval.json`
- Produces:
  - `answer_details/per_case_scoring_rows.jsonl`
  - `answer_details/per_case_scoring_rows.csv`
  - `answer_details/case_movement_vs_guided.json`
  - `answer_details/case_movement_vs_guided.md`
  - `answer_details/export_summary.json`

- [x] **Step 1: Run detail export**

Run only if the full quality gate passes:

- primary run exits `0`
- guarded rebuild exits `0`
- no primary or rebuild `blocked_status.json`
- primary `case_count=120`
- primary `unique_case_count=40`
- primary checkpoint rows `120`
- primary `timeout_count=0`
- primary `provider_error_count=0`
- primary `empty_answer_count=0`
- rebuild metrics match primary metrics
- rebuild `checkpoint_input_count=120`

```bash
.venv/bin/python scripts/export_memory_p6o20_answer_details.py --report-json my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/real_balanced_40/system_path_safe_version_eval.json --out-dir my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/answer_details --anchor-mode safe_version_replace_guided --comparison-mode safe_version_replace_guided_with_retry_shadow
```

Expected:

- Exit `0`.
- `total_rows=120`.
- `paired_case_count=40`.
- `unpaired_case_count=0`.
- `forbidden_key_scan_passed=true`.

- [x] **Step 2: Capture detail summary**

Run:

```bash
.venv/bin/python -c "import json; s=json.load(open('my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/answer_details/export_summary.json')); assert s['total_rows']==120, s; assert s['paired_case_count']==40, s; assert s['unpaired_case_count']==0, s; assert s['forbidden_key_scan_passed'] is True, s; print(s)"
sed -n '1,160p' my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/answer_details/case_movement_vs_guided.md
```

Expected: movement counts and row counts are available for the final report.

---

### Task 4: Write Final Experiment Report

**Files:**
- Create: `my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1/p6o24_formal_guarded_real_report.md`

**Interfaces:**
- Consumes all P6o-24 artifacts.
- Produces final method/data/conclusion document.

- [x] **Step 1: Write report**

Create a Markdown report containing:

- Objective: complete previously errored P6o-20 experiment.
- Method: case pack, slice, modes, timeout, infra guard, fresh checkpoint, production constraints.
- Commands: formal run, guarded rebuild, detail export.
- Artifacts: all output paths.
- Data:
  - primary metrics
  - mode summaries
  - checkpoint count
  - rebuild comparison
  - retry-shadow reason counts
  - movement vs guided
  - guided answer rate
  - retry-shadow answer rate
  - guided-to-retry-shadow absolute answer-rate delta
  - paired movement counts
  - category breakdown
  - grounding delta
  - forbidden delta
  - token and latency deltas
  - per-category concise pass/fail table
- Gate decision:
  - `quality_passed_for_interpretation` if infra criteria pass.
  - `infra_blocked` if blocked.
- Conclusion:
  - whether the previous `answer=0` failure is resolved for this formal run.
  - whether `safe_version_replace_guided_with_retry_shadow` improves, regresses, or ties `safe_version_replace_guided`.
  - decision rule: `guided_retry_shadow` improves only if answer-rate delta vs guided is positive and there is no grounding-rate regression and no forbidden-rate regression; it regresses if answer-rate delta is negative or if grounding/forbidden regresses; otherwise it ties.
  - recommended next step.

- [x] **Step 2: Privacy scan**

Run:

```bash
rg -n -i "api_key|sk-|authorization|bearer|raw_query|raw_prompt|full_answer|raw_answer|session_text|memory_summary|complete_response|conversation_log|current_truth_lines|must_include_terms" my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1
.venv/bin/python -c "import json, pathlib; paths=list(pathlib.Path('my_md/memory_optimization/eval_reports/p6o24_formal_guarded_real_v1').glob('**/system_path_safe_version_eval.json')); assert paths; flags=('raw_query_included','raw_memory_summary_included','prompt_included','conversation_log_included','complete_response_included');\nfor path in paths:\n    metrics=json.load(open(path))['metrics']\n    assert all(metrics.get(flag) is False for flag in flags), (path, {flag: metrics.get(flag) for flag in flags})\nprint({'privacy_metric_files_checked': len(paths)})"
```

Expected: no matches.

- [x] **Step 3: Final status check**

Run:

```bash
git status --short
```

Expected: P6o-24 artifacts and updated P6o-23 report are uncommitted; pre-existing `p6o13_system_path_real_llm_validation_v1/` may remain untracked and should not be modified.
