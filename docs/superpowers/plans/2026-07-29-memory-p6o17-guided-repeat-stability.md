# P6o-17 Guided Repeat Stability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate whether `safe_version_replace_guided` remains better than `safe_version_replace` under the same 3-repeat stability methodology that P6o-15 used.

**Architecture:** Do not add runtime features. Reuse the existing system-path safe version eval runner, checkpoint/resume/report-only flow, and sanitized report writer to run a bounded real LLM repeat matrix, compute a guided-vs-unguided stability gate, then update durable memory optimization docs.

**Tech Stack:** Python 3.14 via `.venv/bin/python`, existing `scripts/run_memory_system_path_safe_version_eval.py`, existing `memory2.eval_system_path_safe_version`, JSON/Markdown reports, checkpoint JSONL, pytest.

## Global Constraints

- Branch/worktree: execute only in `/home/jjh/git_work/akashic-agent/.worktrees/memory-next` on branch `memory-next`.
- P6o-17 depends on the current uncommitted P6o-16 implementation that adds `safe_version_replace_guided`.
- Protected untracked path: do not stage, delete, edit, or move `my_md/memory_optimization/eval_reports/p6o13_system_path_real_llm_validation_v1/`.
- Do not add new retrieval lanes, graph/all-on, retry, fallback, production write behavior, global system prompt changes, or production default activation.
- Production default remains `MemoryConfig.safe_version_governed_mode = "off"`.
- Reports must remain sanitized: no raw prompt, raw query, session text, memory summaries, full answers, API keys, authorization values, or secrets.
- Real LLM config path is `/home/jjh/git_work/akashic-agent/config.toml`; never copy or print config contents.
- P6o-17 success gate: complete `240`-row matrix, zero provider errors, zero timeouts, real guided rows actually carry guidance metadata/contract flags, unguided rows do not carry guidance flags, token metrics are available for both modes, rebuilt checkpoint has `240` valid input rows and `0` malformed rows, guided grounding no lower than replace, guided forbidden equal to replace and no higher than `0.0`, guided answer higher than replace in aggregate, guided answer not lower than replace in at least `2` of `3` repeats, guided repeat answer spread no more than `25.0` points, guided avg tokens no more than replace + `5%`.

---

## File Structure

- Create report directory: `my_md/memory_optimization/eval_reports/p6o17_guided_repeat_stability_v1/`.
- Create summary report: `my_md/memory_optimization/eval_reports/p6o17_guided_repeat_stability_v1/guided_repeat_stability_report.md`.
- Modify docs:
  - `my_md/memory_optimization/README.md`
  - `progress.md`
- No source code changes are planned. If source changes become necessary, stop and record the blocker before editing.

---

### Task 1: Preflight And Fake Smoke

**Files:**
- Read: `scripts/run_memory_system_path_safe_version_eval.py`
- Read: `memory2/eval_system_path_safe_version.py`
- Create: `my_md/memory_optimization/eval_reports/p6o17_guided_repeat_stability_v1/fake_smoke/`

**Interfaces:**
- Consumes: eval modes `safe_version_replace` and `safe_version_replace_guided`.
- Produces: fake-provider smoke report proving the 2-mode, 3-repeat shape before real calls.

- [ ] **Step 1: Verify working tree context**

Run:

```bash
git status --short --branch
```

Expected:
- branch is `memory-next`
- P6o-16 files may be modified/untracked
- protected P6o-13 path remains untracked and untouched

- [ ] **Step 2: Run focused system-path tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_system_path_safe_version_contract.py \
  tests/test_memory_engine_contract.py \
  tests/test_turn_pipelines.py \
  tests/test_memory_system_path_safe_version_eval.py \
  -q -p no:cacheprovider
```

Expected: all selected tests pass.

- [ ] **Step 3: Run fake-provider repeat smoke**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace /tmp/akashic-p6o17-fake-workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o17_guided_repeat_stability_v1/fake_smoke \
  --fake-provider \
  --balanced-small \
  --common-limit 2 \
  --hard-limit 2 \
  --modes safe_version_replace,safe_version_replace_guided \
  --repeats 3
```

Expected:
- command exits `0`
- `unique_case_count = 4`
- `mode_count = 2`
- `repeat_count = 3`
- `case_count = 24`
- guided rows include `answer_guidance_enabled = true`

- [ ] **Step 4: Verify fake smoke shape**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path

path = Path("my_md/memory_optimization/eval_reports/p6o17_guided_repeat_stability_v1/fake_smoke/system_path_safe_version_eval.json")
payload = json.loads(path.read_text(encoding="utf-8"))
metrics = payload["metrics"]
rows = payload["cases"]
guided_rows = [row for row in rows if row["mode"] == "safe_version_replace_guided"]
result = {
    "unique_case_count": metrics["unique_case_count"],
    "mode_count": metrics["mode_count"],
    "repeat_count": metrics["repeat_count"],
    "case_count": metrics["case_count"],
    "guided_rows": len(guided_rows),
    "all_guided_metadata": all(
        row["safe_version_metadata"].get("answer_guidance_enabled") is True
        for row in guided_rows
    ),
    "all_guided_contract": all(
        row["safe_version_contract"].get("answer_guidance_enabled") is True
        for row in guided_rows
    ),
}
print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
if result != {
    "unique_case_count": 4,
    "mode_count": 2,
    "repeat_count": 3,
    "case_count": 24,
    "guided_rows": 12,
    "all_guided_metadata": True,
    "all_guided_contract": True,
}:
    raise SystemExit(1)
PY
```

Expected: command exits `0` and prints the expected shape.

---

### Task 2: Real Guided Repeat Stability Run

**Files:**
- Create: `my_md/memory_optimization/eval_reports/p6o17_guided_repeat_stability_v1/real_repeat/`
- Create: `my_md/memory_optimization/eval_reports/p6o17_guided_repeat_stability_v1/real_repeat_rebuilt/`

**Interfaces:**
- Consumes: Task 1 fake smoke.
- Produces: real LLM primary report, checkpoint, and checkpoint rebuilt report.

- [ ] **Step 1: Verify real workspace is fresh**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
from pathlib import Path

workspace = Path("/tmp/akashic-p6o17-real-workspace-20260729-v1")
if workspace.exists():
    raise SystemExit(f"Real eval workspace already exists and could contaminate retries: {workspace}")
print(workspace)
PY
```

Expected: command exits `0` and prints `/tmp/akashic-p6o17-real-workspace-20260729-v1`.

- [ ] **Step 2: Run real repeat matrix with checkpoint**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace /tmp/akashic-p6o17-real-workspace-20260729-v1 \
  --out-dir my_md/memory_optimization/eval_reports/p6o17_guided_repeat_stability_v1/real_repeat \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --enable-real-llm \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --modes safe_version_replace,safe_version_replace_guided \
  --timeout-s 30 \
  --repeats 3 \
  --checkpoint-jsonl my_md/memory_optimization/eval_reports/p6o17_guided_repeat_stability_v1/real_repeat/checkpoint.jsonl \
  --resume
```

Expected:
- command exits `0`
- `case_count = 240`
- `unique_case_count = 40`
- `mode_count = 2`
- `repeat_count = 3`
- `provider_error_count = 0`
- `timeout_count = 0`

- [ ] **Step 3: Verify real guidance flags and token availability**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path

path = Path("my_md/memory_optimization/eval_reports/p6o17_guided_repeat_stability_v1/real_repeat/system_path_safe_version_eval.json")
payload = json.loads(path.read_text(encoding="utf-8"))
metrics = payload["metrics"]
rows = payload["cases"]
guided_rows = [row for row in rows if row["mode"] == "safe_version_replace_guided"]
replace_rows = [row for row in rows if row["mode"] == "safe_version_replace"]
result = {
    "case_count": metrics["case_count"],
    "unique_case_count": metrics["unique_case_count"],
    "mode_count": metrics["mode_count"],
    "repeat_count": metrics["repeat_count"],
    "provider_error_count": metrics["provider_error_count"],
    "timeout_count": metrics["timeout_count"],
    "guided_rows": len(guided_rows),
    "replace_rows": len(replace_rows),
    "guided_metadata_enabled": all(
        row["safe_version_metadata"].get("answer_guidance_enabled") is True
        for row in guided_rows
    ),
    "guided_contract_enabled": all(
        row["safe_version_contract"].get("answer_guidance_enabled") is True
        for row in guided_rows
    ),
    "replace_metadata_unguided": all(
        row["safe_version_metadata"].get("answer_guidance_enabled") is not True
        for row in replace_rows
    ),
    "replace_contract_unguided": all(
        row["safe_version_contract"].get("answer_guidance_enabled") is not True
        for row in replace_rows
    ),
    "replace_token_metrics_available": metrics["mode_summaries"]["safe_version_replace"].get("token_metrics_available") is True,
    "guided_token_metrics_available": metrics["mode_summaries"]["safe_version_replace_guided"].get("token_metrics_available") is True,
}
print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
expected = {
    "case_count": 240,
    "unique_case_count": 40,
    "mode_count": 2,
    "repeat_count": 3,
    "provider_error_count": 0,
    "timeout_count": 0,
    "guided_rows": 120,
    "replace_rows": 120,
    "guided_metadata_enabled": True,
    "guided_contract_enabled": True,
    "replace_metadata_unguided": True,
    "replace_contract_unguided": True,
    "replace_token_metrics_available": True,
    "guided_token_metrics_available": True,
}
if result != expected:
    raise SystemExit(1)
PY
```

Expected: command exits `0` and prints the expected shape, guidance flags, and token availability.

- [ ] **Step 4: Rebuild report from checkpoint**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_system_path_safe_version_eval.py \
  --out-dir my_md/memory_optimization/eval_reports/p6o17_guided_repeat_stability_v1/real_repeat_rebuilt \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --enable-real-llm \
  --checkpoint-jsonl my_md/memory_optimization/eval_reports/p6o17_guided_repeat_stability_v1/real_repeat/checkpoint.jsonl \
  --checkpoint-report-only
```

Expected:
- command exits `0`
- rebuilt report contains the same `case_count` and `mode_summaries` as the primary report

- [ ] **Step 5: Verify primary/rebuilt metrics and checkpoint health**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path

base = Path("my_md/memory_optimization/eval_reports/p6o17_guided_repeat_stability_v1")
primary = json.loads((base / "real_repeat" / "system_path_safe_version_eval.json").read_text(encoding="utf-8"))["metrics"]
rebuilt = json.loads((base / "real_repeat_rebuilt" / "system_path_safe_version_eval.json").read_text(encoding="utf-8"))["metrics"]
keys = [
    "unique_case_count",
    "mode_count",
    "case_count",
    "repeat_count",
    "provider_error_count",
    "timeout_count",
    "mode_summaries",
    "repeat_summaries",
]
result = {
    "metrics_match": all(primary[key] == rebuilt[key] for key in keys),
    "primary_case_count": primary["case_count"],
    "rebuilt_case_count": rebuilt["case_count"],
    "rebuilt_checkpoint_input_count": rebuilt.get("checkpoint_input_count"),
    "rebuilt_malformed_checkpoint_line_count": rebuilt.get("malformed_checkpoint_line_count"),
    "rebuilt_provider_error_count": rebuilt["provider_error_count"],
    "rebuilt_timeout_count": rebuilt["timeout_count"],
}
print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
if not (
    result["metrics_match"]
    and result["rebuilt_checkpoint_input_count"] == 240
    and result["rebuilt_malformed_checkpoint_line_count"] == 0
    and result["rebuilt_provider_error_count"] == 0
    and result["rebuilt_timeout_count"] == 0
):
    raise SystemExit(1)
PY
```

Expected: `metrics_match = true`, `rebuilt_checkpoint_input_count = 240`, `rebuilt_malformed_checkpoint_line_count = 0`, `rebuilt_provider_error_count = 0`, and `rebuilt_timeout_count = 0`.

---

### Task 3: Gate, Privacy, And Report

**Files:**
- Create: `my_md/memory_optimization/eval_reports/p6o17_guided_repeat_stability_v1/guided_repeat_stability_report.md`
- Modify: `my_md/memory_optimization/README.md`
- Modify: `progress.md`

**Interfaces:**
- Consumes: Task 2 real reports.
- Produces: gate decision, durable docs, and privacy-verified artifacts.

- [ ] **Step 1: Compute guided repeat gate**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path

path = Path("my_md/memory_optimization/eval_reports/p6o17_guided_repeat_stability_v1/real_repeat/system_path_safe_version_eval.json")
payload = json.loads(path.read_text(encoding="utf-8"))
metrics = payload["metrics"]
rows = payload["cases"]
summaries = metrics["mode_summaries"]
replace = summaries["safe_version_replace"]
guided = summaries["safe_version_replace_guided"]
guided_rows = [row for row in rows if row["mode"] == "safe_version_replace_guided"]
replace_rows = [row for row in rows if row["mode"] == "safe_version_replace"]
repeat_summaries = metrics["repeat_summaries"]
guided_repeat_rates = []
replace_repeat_rates = []
for repeat_index in sorted(repeat_summaries, key=lambda value: int(value)):
    modes = repeat_summaries[repeat_index]["mode_summaries"]
    replace_repeat_rates.append(float(modes["safe_version_replace"]["answer_rule_pass_rate"]))
    guided_repeat_rates.append(float(modes["safe_version_replace_guided"]["answer_rule_pass_rate"]))
token_limit = round(float(replace["avg_total_token_count"]) * 1.05, 4)
repeat_not_lower_count = sum(
    1
    for guided_rate, replace_rate in zip(guided_repeat_rates, replace_repeat_rates)
    if guided_rate >= replace_rate
)
guided_spread = round(max(guided_repeat_rates) - min(guided_repeat_rates), 4)
guided_metadata_enabled = all(
    row["safe_version_metadata"].get("answer_guidance_enabled") is True
    for row in guided_rows
)
guided_contract_enabled = all(
    row["safe_version_contract"].get("answer_guidance_enabled") is True
    for row in guided_rows
)
replace_metadata_unguided = all(
    row["safe_version_metadata"].get("answer_guidance_enabled") is not True
    for row in replace_rows
)
replace_contract_unguided = all(
    row["safe_version_contract"].get("answer_guidance_enabled") is not True
    for row in replace_rows
)
replace_token_metrics_available = replace.get("token_metrics_available") is True
guided_token_metrics_available = guided.get("token_metrics_available") is True
gate_passed = (
    int(metrics["case_count"]) == 240
    and int(metrics["unique_case_count"]) == 40
    and int(metrics["mode_count"]) == 2
    and int(metrics["repeat_count"]) == 3
    and int(metrics["provider_error_count"]) == 0
    and int(metrics["timeout_count"]) == 0
    and len(guided_rows) == 120
    and len(replace_rows) == 120
    and guided_metadata_enabled
    and guided_contract_enabled
    and replace_metadata_unguided
    and replace_contract_unguided
    and replace_token_metrics_available
    and guided_token_metrics_available
    and float(guided["memory_grounding_pass_rate"]) >= float(replace["memory_grounding_pass_rate"])
    and float(guided["forbidden_violation_rate"]) == float(replace["forbidden_violation_rate"])
    and float(guided["forbidden_violation_rate"]) <= 0.0
    and float(guided["answer_rule_pass_rate"]) > float(replace["answer_rule_pass_rate"])
    and repeat_not_lower_count >= 2
    and guided_spread <= 25.0
    and float(guided["avg_total_token_count"]) <= token_limit
)
result = {
    "gate_passed": gate_passed,
    "replace_answer_rate": replace["answer_rule_pass_rate"],
    "guided_answer_rate": guided["answer_rule_pass_rate"],
    "replace_forbidden_rate": replace["forbidden_violation_rate"],
    "guided_forbidden_rate": guided["forbidden_violation_rate"],
    "replace_grounding_rate": replace["memory_grounding_pass_rate"],
    "guided_grounding_rate": guided["memory_grounding_pass_rate"],
    "replace_avg_tokens": replace["avg_total_token_count"],
    "guided_avg_tokens": guided["avg_total_token_count"],
    "token_limit": token_limit,
    "replace_repeat_answer_rates": replace_repeat_rates,
    "guided_repeat_answer_rates": guided_repeat_rates,
    "guided_repeat_not_lower_count": repeat_not_lower_count,
    "guided_answer_spread": guided_spread,
    "guided_metadata_enabled": guided_metadata_enabled,
    "guided_contract_enabled": guided_contract_enabled,
    "replace_metadata_unguided": replace_metadata_unguided,
    "replace_contract_unguided": replace_contract_unguided,
    "replace_token_metrics_available": replace_token_metrics_available,
    "guided_token_metrics_available": guided_token_metrics_available,
}
out = Path("my_md/memory_optimization/eval_reports/p6o17_guided_repeat_stability_v1/gate_decision.json")
out.write_text(
    json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
PY
```

Expected:
- command exits `0`
- `gate_decision.json` is written
- if `gate_passed` is false, continue documentation and mark guided repeat as failed while keeping production default off

- [ ] **Step 2: Run privacy key scan**

Run:

```bash
rg -n '"(raw_prompt|prompt|raw_query|query|full_answer|raw_answer|session_text|memory_summary|raw_memory_summary|api_key|authorization|secret)"' \
  my_md/memory_optimization/eval_reports/p6o17_guided_repeat_stability_v1
```

Expected: no matches and exit code `1`.

- [ ] **Step 3: Run secret pattern scan**

Run:

```bash
rg -in 'bearer|api[_-]?key|authorization|secret|token[[:space:]]*[:=]' \
  my_md/memory_optimization/eval_reports/p6o17_guided_repeat_stability_v1
```

Expected: no matches and exit code `1`.

- [ ] **Step 4: Run value-based privacy scan**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path
from memory2.eval_quantitative_cases import build_quantitative_eval_cases

base = Path("my_md/memory_optimization/eval_reports/p6o17_guided_repeat_stability_v1")
report_text = ""
for path in base.rglob("*"):
    if path.is_file() and path.suffix in {".json", ".md", ".jsonl"}:
        report_text += path.read_text(encoding="utf-8") + "\n"
cases = (
    build_quantitative_eval_cases("common", case_pack="standard", limit=20)
    + build_quantitative_eval_cases("hard", case_pack="standard", limit=20)
)
leaks = []
for case in cases:
    setup = case.setup
    values = [str(setup.get("query") or "").strip()]
    for item in setup.get("memory_items", []):
        if isinstance(item, dict):
            values.append(str(item.get("summary") or "").strip())
    for replacement in setup.get("memory_replacements", []):
        if isinstance(replacement, dict):
            values.append(str(replacement.get("old_summary") or "").strip())
            values.append(str(replacement.get("new_summary") or "").strip())
    for value in values:
        if not value:
            continue
        snippets = {value}
        if len(value) >= 32:
            snippets.add(value[:32])
            snippets.add(value[-32:])
        leaks.extend(snippet for snippet in snippets if snippet and snippet in report_text)
result = {"leak_count": len(leaks)}
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
if leaks:
    raise SystemExit(1)
PY
```

Expected: `{"leak_count": 0}`.

- [ ] **Step 5: Write P6o-17 summary report**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path

base = Path("my_md/memory_optimization/eval_reports/p6o17_guided_repeat_stability_v1")
payload = json.loads((base / "real_repeat" / "system_path_safe_version_eval.json").read_text(encoding="utf-8"))
gate = json.loads((base / "gate_decision.json").read_text(encoding="utf-8"))
metrics = payload["metrics"]
summaries = metrics["mode_summaries"]
replace = summaries["safe_version_replace"]
guided = summaries["safe_version_replace_guided"]
repeat_summaries = metrics["repeat_summaries"]
guided_repeat_rates = []
replace_repeat_rates = []
repeat_rows = []
for repeat_index in sorted(repeat_summaries, key=lambda value: int(value)):
    modes = repeat_summaries[repeat_index]["mode_summaries"]
    replace_rate = float(modes["safe_version_replace"]["answer_rule_pass_rate"])
    guided_rate = float(modes["safe_version_replace_guided"]["answer_rule_pass_rate"])
    replace_repeat_rates.append(replace_rate)
    guided_repeat_rates.append(guided_rate)
    repeat_rows.append(
        f"| {repeat_index} | {replace_rate} | {guided_rate} | {round(guided_rate - replace_rate, 4)} | "
        f"{modes['safe_version_replace_guided']['forbidden_violation_rate']} | "
        f"{modes['safe_version_replace_guided']['memory_grounding_pass_rate']} |"
    )
token_limit = round(float(replace["avg_total_token_count"]) * 1.05, 4)
repeat_not_lower_count = sum(
    1
    for guided_rate, replace_rate in zip(guided_repeat_rates, replace_repeat_rates)
    if guided_rate >= replace_rate
)
guided_spread = round(max(guided_repeat_rates) - min(guided_repeat_rates), 4)
gate_passed = (
    int(metrics["provider_error_count"]) == 0
    and int(metrics["timeout_count"]) == 0
    and gate["guided_metadata_enabled"] is True
    and gate["guided_contract_enabled"] is True
    and gate["replace_metadata_unguided"] is True
    and gate["replace_contract_unguided"] is True
    and gate["replace_token_metrics_available"] is True
    and gate["guided_token_metrics_available"] is True
    and float(guided["memory_grounding_pass_rate"]) >= float(replace["memory_grounding_pass_rate"])
    and float(guided["forbidden_violation_rate"]) == float(replace["forbidden_violation_rate"])
    and float(guided["forbidden_violation_rate"]) <= 0.0
    and float(guided["answer_rule_pass_rate"]) > float(replace["answer_rule_pass_rate"])
    and repeat_not_lower_count >= 2
    and guided_spread <= 25.0
    and float(guided["avg_total_token_count"]) <= token_limit
)
conclusion = (
    "P6o-17 passed: guided replace remains the better repeat-stability candidate and can proceed to config-gated shadow rollout planning."
    if gate_passed
    else "P6o-17 did not pass: keep guided replace as an eval-only candidate and run failure attribution before any rollout plan."
)
next_step = (
    "Design a config-gated shadow rollout that records guided-vs-unguided post-check deltas without changing production replies."
    if gate_passed
    else "Compare guided and unguided failure buckets by repeat and case before changing prompt wording or placement."
)

def row(mode: str) -> str:
    data = summaries[mode]
    return (
        f"| {mode} | {data['case_count']} | {data['answer_rule_pass_rate']} | "
        f"{data['memory_grounding_pass_rate']} | {data['forbidden_violation_rate']} | "
        f"{data['contract_generation_success_rate']} | {data['post_check_shadow_enabled_rate']} | "
        f"{data['avg_total_token_count']} | {data['avg_latency_ms']} |"
    )

report = "\n".join(
    [
        "# P6o-17 Guided Repeat Stability",
        "",
        "## Purpose",
        "",
        "Validate whether `safe_version_replace_guided` remains better than `safe_version_replace` under a 3-repeat real LLM stability matrix.",
        "",
        "## Method",
        "",
        "- Case pack: standard balanced small, common `20` + hard `20`.",
        "- Modes: `safe_version_replace`, `safe_version_replace_guided`.",
        "- Repeats: `3`.",
        "- Real calls: `40` unique cases * `2` modes * `3` repeats = `240`.",
        "- Checkpoint: `real_repeat/checkpoint.jsonl`.",
        "- Rebuilt report: `real_repeat_rebuilt/`.",
        "- Reports exclude raw prompt, raw query, session text, memory summaries, full answers, API keys, authorization values, and secrets.",
        "",
        "## Results",
        "",
        "| mode | cases | answer_rate | grounding_rate | forbidden_rate | contract_success | post_check_shadow | avg_tokens | avg_latency_ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        row("safe_version_replace"),
        row("safe_version_replace_guided"),
        "",
        "## Repeat Results",
        "",
        "| repeat | replace_answer_rate | guided_answer_rate | guided_delta | guided_forbidden_rate | guided_grounding_rate |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
        *repeat_rows,
        "",
        "## Gate",
        "",
        f"- provider_error_count: `{metrics['provider_error_count']}`.",
        f"- timeout_count: `{metrics['timeout_count']}`.",
        f"- guided_repeat_not_lower_count: `{repeat_not_lower_count}/3`.",
        f"- guided_answer_spread: `{guided_spread}`.",
        f"- guided token threshold: `{token_limit}`.",
        f"- real guided metadata enabled: `{str(gate['guided_metadata_enabled']).lower()}`.",
        f"- real guided contract enabled: `{str(gate['guided_contract_enabled']).lower()}`.",
        f"- unguided replace remains unguided: `{str(gate['replace_metadata_unguided'] and gate['replace_contract_unguided']).lower()}`.",
        f"- token metrics available: `{str(gate['replace_token_metrics_available'] and gate['guided_token_metrics_available']).lower()}`.",
        f"- gate_passed: `{str(gate_passed).lower()}`.",
        "",
        "## P6o-15 Context",
        "",
        "P6o-15 remains the historical stability baseline for unguided `safe_version_replace`: `120` replace calls, `73.3333%` answer rate, `100.0%` grounding, `0.0%` forbidden, `5427.0833` average tokens, and `2.5` point repeat spread. P6o-17 uses same-run comparison for the guided candidate, so P6o-15 is context rather than a hard cross-run gate.",
        "",
        "## Conclusion",
        "",
        conclusion,
        "",
        "## Next Step",
        "",
        next_step,
        "",
    ]
)
(base / "guided_repeat_stability_report.md").write_text(report, encoding="utf-8")
print(base / "guided_repeat_stability_report.md")
PY
```

Expected: summary report is written with actual metrics and no unresolved template markers.

- [ ] **Step 6: Update README and progress**

Add a P6o-17 entry to `my_md/memory_optimization/README.md` and `progress.md` with:
- test method: `40` cases, `2` modes, `3` repeats, `240` calls
- per-mode answer/grounding/forbidden/token data
- repeat answer rates
- gate result
- P6o-15 context as a historical baseline, not a hard cross-run gate
- conclusion and next step

- [ ] **Step 7: Final verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_system_path_safe_version_contract.py \
  tests/test_memory_engine_contract.py \
  tests/test_turn_pipelines.py \
  tests/test_memory_system_path_safe_version_eval.py \
  -q -p no:cacheprovider
git diff --check
```

Expected:
- pytest exits `0`
- `git diff --check` exits `0`

- [ ] **Step 8: Show final working tree**

Run:

```bash
git status --short --branch
```

Expected:
- P6o-16 implementation/report changes remain present
- P6o-17 report/doc changes are present
- protected P6o-13 untracked path remains untouched
