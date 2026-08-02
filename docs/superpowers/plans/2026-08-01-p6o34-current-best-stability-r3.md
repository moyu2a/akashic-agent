# P6o34 Current Best Stability R3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate whether the current best `safe_version_replace_guided_with_retry_shadow + work persona` scheme remains stable across three real-LLM repeats on the 80-case medium system-path set.

**Architecture:** Reuse the existing system-path eval CLI and P6o33 debug export without changing production code. Run only the current best mode across 80 cases x 3 repeats, parse the JSON report with a one-off local analysis command, inspect any failed raw-answer debug artifacts, and record method/data/conclusion in a new Markdown report.

**Tech Stack:** Python 3, existing `scripts/run_memory_system_path_safe_version_eval.py`, existing `memory2.eval_system_path_safe_version` report JSON/Markdown schema, Markdown documentation under `my_md/memory_optimization/`.

## Global Constraints

- Do not modify production code or prompts.
- Do not enable real retry; `retry_shadow` remains telemetry only.
- Use current committed HEAD after P6o33: `38c9165`.
- Use exactly one mode: `safe_version_replace_guided_with_retry_shadow`.
- Use `--persona-mode work`.
- Use `--balanced-small --common-limit 40 --hard-limit 40`.
- Use `--repeats 3`, producing `80 x 3 = 240` rows.
- Use fresh `/tmp` workspace/checkpoint and fresh eval report directory.
- Do not touch unrelated untracked `my_md/memory_optimization/eval_reports/p6o13_system_path_real_llm_validation_v1/`.

---

### Task 1: Preflight And Fresh Paths

**Files:**
- Read: `my_md/memory_optimization/18-p6o33-contract-incremental-medium-real-eval.md`
- Read: `my_md/memory_optimization/eval_reports/p6o33_contract_incremental_medium_real_v1_20260801_191927/p6o33_incremental_analysis.json`

**Interfaces:**
- Consumes P6o33 current-best baseline.
- Produces fresh P6o34 run identifiers.

- [x] **Step 1: Check branch and workspace state**

Run:

```bash
git status --short --branch
git log -1 --oneline
```

Expected:

- branch is `memory-next`
- latest commit is `38c9165 test(memory): add p6o33 incremental real eval`
- only unrelated untracked path may be `my_md/memory_optimization/eval_reports/p6o13_system_path_real_llm_validation_v1/`

- [x] **Step 2: Verify P6o33 current-best baseline**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python - <<'PY'
import json
from pathlib import Path
p = Path("my_md/memory_optimization/eval_reports/p6o33_contract_incremental_medium_real_v1_20260801_191927/p6o33_incremental_analysis.json")
a = json.loads(p.read_text(encoding="utf-8"))
s = a["mode_summaries"]["safe_version_replace_guided_with_retry_shadow"]
print({
    "gate_passed": a["gate_passed"],
    "unique_case_count": a["unique_case_count"],
    "repeat_count": a["repeat_count"],
    "answer_rule_pass_rate": s["answer_rule_pass_rate"],
    "memory_grounding_pass_rate": s["memory_grounding_pass_rate"],
    "forbidden_violation_rate": s["forbidden_violation_rate"],
    "would_retry_count": s["would_retry_count"],
})
PY
```

Expected:

```text
gate_passed=True
unique_case_count=80
repeat_count=1
answer_rule_pass_rate=100.0
memory_grounding_pass_rate=100.0
forbidden_violation_rate=0.0
would_retry_count=0
```

- [x] **Step 3: Create fresh run paths**

Use timestamped values:

```bash
cd /home/jjh/git_work/akashic-agent/.worktrees/memory-next
export RUN_ID=p6o34_current_best_stability_r3_real_v1_$(date +%Y%m%d_%H%M%S)
WORKSPACE=/tmp/akashic-${RUN_ID}-workspace
CHECKPOINT=/tmp/akashic-${RUN_ID}.jsonl
OUT_DIR=my_md/memory_optimization/eval_reports/${RUN_ID}
```

Verify:

```bash
test ! -e "$WORKSPACE"
test ! -e "$CHECKPOINT"
test ! -e "$OUT_DIR"
```

Expected: all checks exit `0`.

### Task 2: Run P6o34 Real LLM Stability Eval

**Files:**
- Create: `my_md/memory_optimization/eval_reports/p6o34_current_best_stability_r3_real_v1_<timestamp>/system_path_safe_version_eval.json`
- Create: `my_md/memory_optimization/eval_reports/p6o34_current_best_stability_r3_real_v1_<timestamp>/system_path_safe_version_eval.md`
- Create: `my_md/memory_optimization/eval_reports/p6o34_current_best_stability_r3_real_v1_<timestamp>/answer_debug/`

**Interfaces:**
- Consumes existing eval CLI and real LLM provider config.
- Produces 240 case rows and 240 debug JSON files.

- [x] **Step 1: Run the real LLM command**

```bash
cd /home/jjh/git_work/akashic-agent/.worktrees/memory-next
export RUN_ID=<actual-run-id>
WORKSPACE=/tmp/akashic-${RUN_ID}-workspace
CHECKPOINT=/tmp/akashic-${RUN_ID}.jsonl
OUT_DIR=my_md/memory_optimization/eval_reports/${RUN_ID}
PYTHONDONTWRITEBYTECODE=1 uv run python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace "$WORKSPACE" \
  --out-dir "$OUT_DIR" \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --enable-real-llm \
  --balanced-small \
  --common-limit 40 \
  --hard-limit 40 \
  --modes safe_version_replace_guided_with_retry_shadow \
  --persona-mode work \
  --repeats 3 \
  --timeout-s 60 \
  --checkpoint-jsonl "$CHECKPOINT" \
  --answer-debug-dir "$OUT_DIR/answer_debug" \
  --early-infra-abort-count 5 \
  --early-infra-abort-rate 0.5 \
  --allow-infra-blocked-exit-zero
```

Expected:

- command exits `0`
- no `blocked_status.json`
- report JSON/Markdown paths are printed
- checkpoint has `240` lines
- debug directory has `240` JSON files

### Task 3: Analyze Stability Gates

**Files:**
- Read: generated `system_path_safe_version_eval.json`
- Read: generated `answer_debug/*.json` only for failed rows

**Interfaces:**
- Produces copied metrics and failure analysis for final documentation.

- [x] **Step 1: Run shape and gate analysis**

Run:

```bash
cd /home/jjh/git_work/akashic-agent/.worktrees/memory-next
export RUN_ID=<actual-run-id>
export OUT_DIR=my_md/memory_optimization/eval_reports/${RUN_ID}
PYTHONDONTWRITEBYTECODE=1 uv run python - <<'PY'
import json
import os
from pathlib import Path
base = Path(os.environ["OUT_DIR"])
p = base / "system_path_safe_version_eval.json"
d = json.loads(p.read_text(encoding="utf-8"))
m = d["metrics"]
mode = m["mode_summaries"]["safe_version_replace_guided_with_retry_shadow"]
rows = d["cases"]
repeat_rows = {
    str(repeat): [
        row for row in rows if int(row["repeat_index"]) == int(repeat)
    ]
    for repeat in sorted({int(row["repeat_index"]) for row in rows})
}
case_outcomes = {}
for row in rows:
    case_outcomes.setdefault(row["case_id"], []).append(bool(row["answer_rule_passed"]))
flipped_cases = {
    case_id: values
    for case_id, values in case_outcomes.items()
    if len(set(values)) > 1
}
assert m["unique_case_count"] == 80
assert m["case_count"] == 240
assert m["repeat_count"] == 3
assert m["real_llm_enabled"] is True
assert m["fake_provider_enabled"] is False
assert set(m["mode_summaries"]) == {"safe_version_replace_guided_with_retry_shadow"}
assert all(len(items) == 80 for items in repeat_rows.values())
assert m["provider_error_count"] == 0
assert m["timeout_count"] == 0
assert m["checkpoint_input_count"] == 0
assert m["malformed_checkpoint_line_count"] == 0
assert m["skipped_from_checkpoint_count"] == 0
assert mode["answer_rule_pass_rate"] >= 95.0
assert mode["memory_grounding_pass_rate"] == 100.0
assert mode["forbidden_violation_rate"] == 0.0
assert all(
    summary["mode_summaries"]["safe_version_replace_guided_with_retry_shadow"]["answer_rule_pass_rate"] >= 95.0
    for summary in m["repeat_summaries"].values()
)
print({
    "unique_case_count": m["unique_case_count"],
    "case_count": m["case_count"],
    "repeat_count": m["repeat_count"],
    "real_llm_enabled": m["real_llm_enabled"],
    "fake_provider_enabled": m["fake_provider_enabled"],
    "provider_error_count": m["provider_error_count"],
    "timeout_count": m["timeout_count"],
    "checkpoint_input_count": m["checkpoint_input_count"],
    "malformed_checkpoint_line_count": m["malformed_checkpoint_line_count"],
    "skipped_from_checkpoint_count": m["skipped_from_checkpoint_count"],
    "answer_rule_pass_rate": mode["answer_rule_pass_rate"],
    "memory_grounding_pass_rate": mode["memory_grounding_pass_rate"],
    "forbidden_violation_rate": mode["forbidden_violation_rate"],
    "would_retry_count": mode["would_retry_count"],
    "retry_reason_counts": mode["retry_reason_counts"],
    "repeat_summaries": m["repeat_summaries"],
    "flipped_case_count": len(flipped_cases),
    "flipped_cases": flipped_cases,
})
failed = [r for r in d["cases"] if not r["answer_rule_passed"] or r.get("failures")]
print("failed_rows", len(failed))
for row in failed:
    print(row["repeat_index"], row["case_id"], row["category"], row["failures"], row["post_check_shadow"])
PY
```

Strict gate:

- `unique_case_count == 80`
- `case_count == 240`
- `repeat_count == 3`
- only mode is `safe_version_replace_guided_with_retry_shadow`
- `real_llm_enabled == true`
- `fake_provider_enabled == false`
- each repeat has `80` rows
- aggregate answer rate `>= 95.0%`
- each repeat answer rate `>= 95.0%`
- report `flipped_case_count`; `0` is strong stability, `>0` is acceptable only if all repeats still pass and failures are explained
- grounding `100.0%`
- forbidden `0.0%`
- provider errors `0`
- timeouts `0`
- checkpoint input/malformed/skipped `0`
- no `blocked_status.json`

- [x] **Step 2: Inspect failed raw answers if any**

For each failed row, open the matching debug JSON:

```bash
cd /home/jjh/git_work/akashic-agent/.worktrees/memory-next
export RUN_ID=<actual-run-id>
export OUT_DIR=my_md/memory_optimization/eval_reports/${RUN_ID}
PYTHONDONTWRITEBYTECODE=1 uv run python - <<'PY'
import json
import os
from pathlib import Path
base = Path(os.environ["OUT_DIR"])
report = json.loads((base / "system_path_safe_version_eval.json").read_text(encoding="utf-8"))
debug = {}
for p in (base / "answer_debug").glob("*.json"):
    d = json.loads(p.read_text(encoding="utf-8"))
    debug[(d["repeat_index"], d["case_id"], d["mode"])] = (p, d)
for r in report["cases"]:
    if r["answer_rule_passed"] and not r.get("failures"):
        continue
    p, d = debug[(r["repeat_index"], r["case_id"], r["mode"])]
    print("---", r["repeat_index"], r["case_id"], r["failures"])
    print("debug_path:", p)
    print("answer:", d["answer_text"].replace("\\n", " ")[:800])
PY
```

Classify each failure as one of:

- scorer strictness / evaluation artifact
- answer omitted expected fact
- meta-action / pseudo tool call
- forbidden/stale leakage
- infra/provider issue

### Task 4: Document Results

**Files:**
- Create: `my_md/memory_optimization/19-p6o34-current-best-stability-r3.md`

**Interfaces:**
- Consumes run commands, metrics, and failed-case review.
- Produces durable handoff documentation.

- [x] **Step 1: Record method**

Write:

- run id and exact command
- dataset shape
- mode/persona/repeats
- proof that real retry was not enabled
- raw artifact directory

- [x] **Step 2: Record data tables**

Include:

- aggregate metrics
- per-repeat metrics
- failed row table
- flipped case count and flipped case table
- retry shadow reason counts
- token/latency summary

- [x] **Step 3: Record conclusion**

Use these rules:

- If aggregate and every repeat are `>=95%` with safety gates passing: conclude current best is stable on this 80-case medium set.
- If any repeat falls below `95%`: conclude not yet stable and prioritize failed-case analysis.
- If `would_retry_count > 0`: explicitly state whether failures look retry-fixable, but do not claim real retry quality.

### Task 5: Verification And Commit

**Files:**
- Stage only P6o34 plan/report/artifacts.
- Do not stage unrelated p6o13 directory.

- [ ] **Step 1: Verify artifacts**

Run:

```bash
test -f "$OUT_DIR/system_path_safe_version_eval.json"
test -f "$OUT_DIR/system_path_safe_version_eval.md"
test "$(find "$OUT_DIR/answer_debug" -type f -name '*.json' | wc -l)" -eq 240
git status --short
```

- [ ] **Step 2: Commit**

Run:

```bash
git add -f docs/superpowers/plans/2026-08-01-p6o34-current-best-stability-r3.md
git add my_md/memory_optimization/19-p6o34-current-best-stability-r3.md "$OUT_DIR"
git commit -m "test(memory): record p6o34 current best stability"
```
