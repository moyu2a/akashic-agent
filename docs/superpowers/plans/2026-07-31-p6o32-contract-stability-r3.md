# P6o32 Contract Stability R3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate whether the current best `safe_version_replace_guided_with_retry_shadow + work persona` scheme remains stable across three real LLM repeats on the 40-case medium system-path set.

**Architecture:** Run the existing real LLM system-path eval with `repeats=3`, parse the generated JSON report, compare against P6o31 and fixed stability gates, then record method, data, failure details, and conclusion in a Markdown report. No production code or prompt changes are part of this plan.

**Tech Stack:** Python 3, existing `scripts/run_memory_system_path_safe_version_eval.py`, existing `memory2` report JSON schema, Markdown report under `my_md/memory_optimization/`.

## Global Constraints

- Do not modify production code, prompts, tests, or eval logic unless the validation command itself exposes an infrastructure blocker.
- Use the current committed best scheme at HEAD: `safe_version_replace_guided_with_retry_shadow` with `--persona-mode work`.
- Do not touch unrelated untracked `my_md/memory_optimization/eval_reports/p6o13_system_path_real_llm_validation_v1/`.
- Treat provider errors and timeouts as infrastructure signals, not model-quality failures.
- Record exact commands, metrics, failed cases, and conclusion in `my_md/memory_optimization/17-p6o32-contract-stability-r3.md`.

---

## File Structure

- Create `my_md/memory_optimization/17-p6o32-contract-stability-r3.md`
  - Responsibility: record P6o32 validation method, data, failed-case analysis, and conclusion.
- Create `my_md/memory_optimization/eval_reports/p6o32_contract_stability_r3_real_v1_20260731_1600/`
  - Responsibility: generated JSON and Markdown eval reports from the CLI.
- Use `/tmp/akashic-p6o32-contract-stability-r3-workspace-20260731-1600`
  - Responsibility: temporary eval workspace.
- Use `/tmp/akashic-p6o32-contract-stability-r3-checkpoint-20260731-1600.jsonl`
  - Responsibility: checkpoint for resumability.

---

### Task 1: Preflight

**Files:**
- Read: `my_md/memory_optimization/16-evidence-contract-conflict-governance.md`
- Read: `scripts/run_memory_system_path_safe_version_eval.py`

**Interfaces:**
- Consumes: current best P6o31 report and CLI flags.
- Produces: confidence that the run will validate the intended scheme.

- [ ] **Step 1: Check workspace state**

Run:

```bash
git status --short
```

Expected:

- No staged files.
- The only unrelated existing untracked path may be `my_md/memory_optimization/eval_reports/p6o13_system_path_real_llm_validation_v1/`.

- [ ] **Step 2: Verify current best baseline**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python - <<'PY'
import json
from pathlib import Path
p = Path("my_md/memory_optimization/eval_reports/p6o31_contract_conflict_medium_real_v1/system_path_safe_version_eval.json")
data = json.loads(p.read_text(encoding="utf-8"))
m = data["metrics"]
print({
    "case_count": m["case_count"],
    "answer_rule_pass_rate": m["answer_rule_pass_rate"],
    "memory_grounding_pass_rate": m["memory_grounding_pass_rate"],
    "forbidden_violation_rate": m["forbidden_violation_rate"],
    "provider_error_count": m["provider_error_count"],
    "timeout_count": m["timeout_count"],
    "retry_reason_counts": m["mode_summaries"]["safe_version_replace_guided_with_retry_shadow"]["retry_reason_counts"],
})
PY
```

Expected:

```text
case_count: 40
answer_rule_pass_rate: 100.0
memory_grounding_pass_rate: 100.0
forbidden_violation_rate: 0.0
provider_error_count: 0
timeout_count: 0
retry_reason_counts: {}
```

- [ ] **Step 3: Verify the P6o32 paths are fresh**

Run:

```bash
test ! -e /tmp/akashic-p6o32-contract-stability-r3-workspace-20260731-1600
test ! -e /tmp/akashic-p6o32-contract-stability-r3-checkpoint-20260731-1600.jsonl
test ! -e my_md/memory_optimization/eval_reports/p6o32_contract_stability_r3_real_v1_20260731_1600
```

Expected: all three commands exit `0`. If any path exists, stop and choose a new timestamped run id rather than reusing stale eval state.

---

### Task 2: Run P6o32 Stability R3

**Files:**
- Create: `my_md/memory_optimization/eval_reports/p6o32_contract_stability_r3_real_v1_20260731_1600/system_path_safe_version_eval.json`
- Create: `my_md/memory_optimization/eval_reports/p6o32_contract_stability_r3_real_v1_20260731_1600/system_path_safe_version_eval.md`

**Interfaces:**
- Consumes: existing CLI `scripts/run_memory_system_path_safe_version_eval.py`
- Produces: a real LLM report with `40` unique cases and `120` case rows.

- [ ] **Step 1: Run real LLM stability command**

Run:

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

Expected:

- Exit code `0`.
- JSON and Markdown report paths printed.
- If a `blocked_status.json` is written, stop and classify as infrastructure-blocked rather than quality failure.

---

### Task 3: Extract Metrics and Gate Result

**Files:**
- Read: `my_md/memory_optimization/eval_reports/p6o32_contract_stability_r3_real_v1_20260731_1600/system_path_safe_version_eval.json`

**Interfaces:**
- Consumes: generated P6o32 JSON.
- Produces: aggregate metrics, per-repeat metrics, target-case stability, and failed-case detail.

- [ ] **Step 1: Extract aggregate, repeat, and failure data**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python - <<'PY'
import json
from collections import Counter, defaultdict
from pathlib import Path
p = Path("my_md/memory_optimization/eval_reports/p6o32_contract_stability_r3_real_v1_20260731_1600/system_path_safe_version_eval.json")
data = json.loads(p.read_text(encoding="utf-8"))
m = data["metrics"]
mode = m["mode_summaries"]["safe_version_replace_guided_with_retry_shadow"]
conflict_fields = (
    "dsml_tool_markup_in_final_answer",
    "tool_markup_in_final_answer",
    "meta_action_final_answer",
)
conflict_counts = Counter()
for row in data["cases"]:
    post = row.get("post_check_shadow") or {}
    for field in conflict_fields:
        if post.get(field):
            conflict_counts[field] += 1
print("AGG", {
    "unique_case_count": m["unique_case_count"],
    "case_count": m["case_count"],
    "repeat_count": m["repeat_count"],
    "real_llm_enabled": m["real_llm_enabled"],
    "fake_provider_enabled": m["fake_provider_enabled"],
    "mode_count": m["mode_count"],
    "mode_keys": sorted(m["mode_summaries"].keys()),
    "checkpoint_input_count": m["checkpoint_input_count"],
    "malformed_checkpoint_line_count": m["malformed_checkpoint_line_count"],
    "skipped_from_checkpoint_count": m["skipped_from_checkpoint_count"],
    "answer_success_count": mode["answer_success_count"],
    "answer_rule_pass_rate": m["answer_rule_pass_rate"],
    "memory_grounding_pass_rate": m["memory_grounding_pass_rate"],
    "forbidden_violation_rate": m["forbidden_violation_rate"],
    "provider_error_count": m["provider_error_count"],
    "timeout_count": m["timeout_count"],
    "contract_generation_success_rate": mode["contract_generation_success_rate"],
    "answer_candidate_contract_enabled_rate": mode["answer_candidate_contract_enabled_rate"],
    "post_check_shadow_enabled_rate": mode["post_check_shadow_enabled_rate"],
    "would_retry_count": mode["would_retry_count"],
    "retry_reason_counts": mode["retry_reason_counts"],
    "conflict_family_counts": dict(conflict_counts),
    "avg_latency_ms": m["avg_latency_ms"],
    "avg_total_token_count": m["avg_total_token_count"],
    "total_token_count": m["total_token_count"],
})
print("REPEATS")
for repeat, row in sorted(m["repeat_summaries"].items(), key=lambda item: int(item[0])):
    mm = row["mode_summaries"]["safe_version_replace_guided_with_retry_shadow"]
    print(repeat, {
        "case_count": row["case_count"],
        "answer_success_count": mm["answer_success_count"],
        "answer_rule_pass_rate": row["answer_rule_pass_rate"],
        "memory_grounding_pass_rate": row["memory_grounding_pass_rate"],
        "forbidden_violation_rate": row["forbidden_violation_rate"],
        "would_retry_count": mm["would_retry_count"],
        "retry_reason_counts": mm["retry_reason_counts"],
    })
targets = {"hard_graph_bridge_01", "hard_version_chain_01", "hard_preference_recall_02"}
print("TARGETS")
for case_id in sorted(targets):
    rows = [r for r in data["cases"] if r["case_id"] == case_id]
    print(case_id, [(r["repeat_index"], r["passed"], r["failures"], (r.get("post_check_shadow") or {}).get("retry_reasons", [])) for r in rows])
print("FAILURES")
for r in data["cases"]:
    if not r["passed"]:
        print(r["repeat_index"], r["case_id"], r["failures"], r.get("post_check_shadow"))
PY
```

- [ ] **Step 2: Apply stability gate**

Gate passes if all of these are true:

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

If the gate fails, record whether the failure is:

- infra/provider/timeout;
- old conflict-family recurrence;
- scorer miss without meta/tool behavior;
- new case-family failure.

---

### Task 4: Record Method, Data, and Conclusion

**Files:**
- Create: `my_md/memory_optimization/17-p6o32-contract-stability-r3.md`

**Interfaces:**
- Consumes: Task 3 extracted data.
- Produces: durable P6o32 report.

- [ ] **Step 1: Write Markdown report**

Create `my_md/memory_optimization/17-p6o32-contract-stability-r3.md` with these sections:

```markdown
# P6o32 Contract Stability R3

## Goal

Validate whether the current best Evidence Contract conflict-governance scheme remains stable across three real LLM repeats on the 40-case medium system-path set.

## Method

[exact command and gate criteria]

## Data

[aggregate table]

[per-repeat table]

[target-case table]

[failed-case table if any]

## Conclusion

[pass/fail, comparison to P6o31, residual risks, next step]

If the result passes the `>=95%` stability gate but does not reproduce `40/40` in every repeat, state that distinction explicitly. Do not describe it as "replicated 100%" unless every repeat is `40/40`.
```

- [ ] **Step 2: Verify report contains no placeholders**

Run:

```bash
rg -n "TBD|TODO|\\[fill\\]|\\[exact command|\\[aggregate|\\[per-repeat|\\[target-case|\\[failed-case|\\[pass/fail" my_md/memory_optimization/17-p6o32-contract-stability-r3.md
```

Expected: no matches.

---

## Self-Review

- Spec coverage: This plan covers preflight, real LLM execution, data extraction, stability gate, and durable documentation.
- Placeholder scan: The implementation report template contains bracketed placeholders only inside the plan instructions; the final report must remove them.
- Scope check: This is a validation-only plan. No production code changes are included.
