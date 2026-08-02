# Memory P6o12 Safe Version Repeat Stability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify whether the current strongest eval-only profile, `chain_tri_version_governed_answer_contract`, remains stable across repeated real LLM runs against the governed baseline.

**Architecture:** Reuse the existing comprehensive online eval CLI and existing P6o governed profiles. Do not add a new profile and do not activate graph; run a same-matrix repeat stability eval, then generate a small stability analysis report from the sanitized JSON output and record the conclusions in docs.

**Tech Stack:** Python `>=3.12`, pytest, existing `scripts/run_memory_comprehensive_online_eval.py`, existing `memory2.eval_comprehensive_online`, JSON/Markdown reports, checkpoint JSONL under `/tmp`, committed docs under `my_md/memory_optimization/eval_reports/`.

## Global Constraints

- Worktree: `/home/jjh/git_work/akashic-agent/.worktrees/memory-next`.
- Branch: `memory-next`.
- Do not sync remote/main in this plan unless the user explicitly redirects.
- Do not push without explicit user instruction.
- Do not modify production `AgentLoop`, `Reasoner`, `ToolExecutor`, `ToolRegistry`, production memory writes, production prompts, `plugins/default_memory/engine.py`, or the old `Retriever.retrieve()` return contract.
- Do not add graph/all-on profiles in this plan.
- Do not add a new eval profile in this plan.
- Real LLM matrix shape is fixed: common `20` + hard `20`, prompt variant `baseline`, repeat `3`, profiles `chain_tri_governed_answer_contract` and `chain_tri_version_governed_answer_contract`, expected `240` completed calls.
- Real LLM calls are allowed only after a fake-provider smoke with the same profile list, prompt variant, and balanced common/hard selection passes.
- Use explicit `--config /home/jjh/git_work/akashic-agent/config.toml` for real LLM runs.
- Store live checkpoint JSONL under `/tmp/akashic-memory-p6o12-version-repeat-stability/`, not in git-tracked docs.
- Do not write raw prompt, raw session text, raw memory summaries, full answers, answer debug artifacts, or API keys into committed report/docs.
- Use a temp empty `--real-memory-workspace` for fake and real runs so real memory DB sampling cannot leak content into reports.
- Success gate:
  - `infra_passed = True`;
  - `provider_error_count = 0`;
  - `timeout_count = 0`;
  - `case_count = 240`;
  - `completed_call_count = 240`;
  - `unique_case_count = 40`;
  - `profile_count = 2`;
  - `prompt_variant_count = 1`;
  - `repeat_count = 3`;
  - every profile grounding rate remains `100.0%`;
  - safe version-governed forbidden rate remains `0.0%`;
  - safe version-governed average tokens are not more than `10.0%` above governed baseline;
  - answer post-check shadow risk counts for safe version-governed do not exceed governed baseline.
- Stability interpretation gate:
  - if safe version-governed total answer rate is at least `97.5%` and each repeat is at least `39/40`, treat P6o-10 `40/40` as stable enough for the next hard-slice plan;
  - if total answer rate is below `97.5%` or any repeat is below `39/40`, treat P6o-10 `40/40` as not yet stable and require failure/sensitivity analysis before hard-slice expansion.

---

## File Structure

- Modify:
  - `my_md/memory_optimization/README.md`
  - `progress.md`
- Create:
  - `my_md/memory_optimization/eval_reports/p6o12_safe_version_repeat_stability_v1/memory_comprehensive_online_eval.json`
  - `my_md/memory_optimization/eval_reports/p6o12_safe_version_repeat_stability_v1/memory_comprehensive_online_eval.md`
  - `my_md/memory_optimization/eval_reports/p6o12_safe_version_repeat_stability_v1/repeat_stability_summary.md`
- Do not modify code unless fake-provider smoke exposes an existing report-shape regression.

---

## Task 0: Confirm Execution Baseline

**Files:**
- Modify: none

**Interfaces:**
- Consumes: current `memory-next` worktree after P6o-11 cross-report synthesis.
- Produces: clean execution baseline and known commit SHA for later review.

- [ ] **Step 1: Confirm worktree and branch**

Run:

```bash
ROOT=$(git rev-parse --show-toplevel)
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
BRANCH=$(git branch --show-current)
printf 'ROOT=%s\nGIT_DIR=%s\nGIT_COMMON=%s\nBRANCH=%s\n' "$ROOT" "$GIT_DIR" "$GIT_COMMON" "$BRANCH"
test "$ROOT" = "/home/jjh/git_work/akashic-agent/.worktrees/memory-next"
git rev-parse HEAD
```

Expected:

```text
BRANCH=memory-next
```

- [ ] **Step 2: Confirm no unrelated working tree changes**

Run:

```bash
git status --short
```

Expected:

```text
```

If output is non-empty, inspect it and do not overwrite unrelated user changes.

---

## Task 1: Fake-Provider Smoke For Repeat Matrix Shape

**Files:**
- Modify: none

**Interfaces:**
- Consumes:
  - CLI flags `--fake-provider`, `--balanced-small`, `--common-limit`, `--hard-limit`, `--profiles`, `--repeats`, `--prompt-variants`, `--checkpoint-jsonl`, `--real-memory-workspace`.
- Produces:
  - fake-provider JSON/Markdown under `/tmp/akashic-memory-p6o12-version-repeat-stability/fake/reports/`.

- [ ] **Step 1: Run fake-provider smoke**

Run:

```bash
rm -rf /tmp/akashic-memory-p6o12-version-repeat-stability/fake
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-p6o12-version-repeat-stability/fake/workspace \
  --out-dir /tmp/akashic-memory-p6o12-version-repeat-stability/fake/reports \
  --fake-provider \
  --case-pack standard \
  --balanced-small \
  --common-limit 2 \
  --hard-limit 2 \
  --profiles chain_tri_governed_answer_contract,chain_tri_version_governed_answer_contract \
  --prompt-variants baseline \
  --repeats 3 \
  --checkpoint-jsonl /tmp/akashic-memory-p6o12-version-repeat-stability/fake/checkpoint.jsonl \
  --concurrency 2 \
  --real-memory-workspace /tmp/akashic-memory-p6o12-version-repeat-stability/empty-real-workspace
```

Expected:

```text
/tmp/akashic-memory-p6o12-version-repeat-stability/fake/reports/memory_comprehensive_online_eval.json
/tmp/akashic-memory-p6o12-version-repeat-stability/fake/reports/memory_comprehensive_online_eval.md
```

- [ ] **Step 2: Validate fake-provider report shape and privacy**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path
path = Path("/tmp/akashic-memory-p6o12-version-repeat-stability/fake/reports/memory_comprehensive_online_eval.json")
payload = json.loads(path.read_text(encoding="utf-8"))
m = payload["metrics"]
assert m["infra_passed"] is True
assert m["real_llm_enabled"] is False
assert m["case_count"] == 24
assert m["completed_call_count"] == 24
assert m["unique_case_count"] == 4
assert m["profile_count"] == 2
assert m["prompt_variant_count"] == 1
assert m["repeat_count"] == 3
assert m["provider_error_count"] == 0
assert m["timeout_count"] == 0
assert set(m["profile_summaries"]) == {
    "chain_tri_governed_answer_contract",
    "chain_tri_version_governed_answer_contract",
}
for key in ("raw_query_included", "raw_memory_summary_included", "prompt_included", "session_text_included", "full_answer_included"):
    assert m[key] is False, (key, m[key])
md = Path("/tmp/akashic-memory-p6o12-version-repeat-stability/fake/reports/memory_comprehensive_online_eval.md").read_text(encoding="utf-8")
assert "raw_prompt" not in md
assert "full_answer" not in md
assert "session_text" not in md
print("fake smoke ok")
PY
```

Expected:

```text
fake smoke ok
```

---

## Task 2: Real LLM Repeat Stability Run

**Files:**
- Create:
  - `my_md/memory_optimization/eval_reports/p6o12_safe_version_repeat_stability_v1/memory_comprehensive_online_eval.json`
  - `my_md/memory_optimization/eval_reports/p6o12_safe_version_repeat_stability_v1/memory_comprehensive_online_eval.md`

**Interfaces:**
- Consumes:
  - existing real provider config at `/home/jjh/git_work/akashic-agent/config.toml`;
  - existing comprehensive online eval runner;
  - existing P6o governed profiles.
- Produces:
  - sanitized committed real LLM report with `240` completed calls.

- [ ] **Step 1: Run real LLM repeat matrix with checkpoint**

Run:

```bash
mkdir -p /tmp/akashic-memory-p6o12-version-repeat-stability/real
if test -e /tmp/akashic-memory-p6o12-version-repeat-stability/real/checkpoint.jsonl; then
  echo "Refusing to reuse existing real checkpoint. Move it aside only if intentionally resuming this exact P6o-12 matrix." >&2
  exit 2
fi
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-p6o12-version-repeat-stability/real/workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o12_safe_version_repeat_stability_v1 \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --enable-real-llm \
  --case-pack standard \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --profiles chain_tri_governed_answer_contract,chain_tri_version_governed_answer_contract \
  --prompt-variants baseline \
  --repeats 3 \
  --checkpoint-jsonl /tmp/akashic-memory-p6o12-version-repeat-stability/real/checkpoint.jsonl \
  --resume \
  --timeout-s 60 \
  --concurrency 2 \
  --real-memory-workspace /tmp/akashic-memory-p6o12-version-repeat-stability/empty-real-workspace
```

Expected:

```text
my_md/memory_optimization/eval_reports/p6o12_safe_version_repeat_stability_v1/memory_comprehensive_online_eval.json
my_md/memory_optimization/eval_reports/p6o12_safe_version_repeat_stability_v1/memory_comprehensive_online_eval.md
```

- [ ] **Step 2: Validate real report gates**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from collections import defaultdict
from pathlib import Path
path = Path("my_md/memory_optimization/eval_reports/p6o12_safe_version_repeat_stability_v1/memory_comprehensive_online_eval.json")
payload = json.loads(path.read_text(encoding="utf-8"))
m = payload["metrics"]
assert m["real_llm_enabled"] is True
assert m["infra_passed"] is True
assert m["case_count"] == 240
assert m["completed_call_count"] == 240
assert m["unique_case_count"] == 40
assert m["profile_count"] == 2
assert m["prompt_variant_count"] == 1
assert m["repeat_count"] == 3
assert m["provider_error_count"] == 0
assert m["timeout_count"] == 0
assert m.get("excluded_infra_failure_count", 0) in (0, "unavailable")
for key in ("raw_query_included", "raw_memory_summary_included", "prompt_included", "session_text_included", "full_answer_included"):
    assert m[key] is False, (key, m[key])
profiles = m["profile_summaries"]
base = profiles["chain_tri_governed_answer_contract"]
version = profiles["chain_tri_version_governed_answer_contract"]
assert float(base["memory_grounding_pass_rate"]) == 100.0
assert float(version["memory_grounding_pass_rate"]) == 100.0
assert float(version["forbidden_violation_rate"]) == 0.0
assert float(version["avg_total_token_count"]) <= float(base["avg_total_token_count"]) * 1.10
shadow = m["answer_post_check_shadow"]
assert shadow["enabled_case_count"] == 240
per_profile = defaultdict(lambda: defaultdict(int))
per_repeat_answer = defaultdict(lambda: defaultdict(int))
per_repeat_cases = defaultdict(lambda: defaultdict(int))
for record in payload["case_records"]:
    profile = record["profile_name"]
    repeat = int(record["repeat_index"])
    per_repeat_cases[profile][repeat] += 1
    per_repeat_answer[profile][repeat] += int(bool(record["answer_rule_passed"]))
    check = record.get("answer_post_check_shadow") or {}
    reasons = set(check.get("retry_reasons") or ())
    per_profile[profile]["needs_retry"] += int(bool(check.get("needs_retry")))
    per_profile[profile]["forbidden_boundary_included"] += int(
        "forbidden_boundary_included" in reasons
        or bool(check.get("included_forbidden_boundary_ids"))
    )
    per_profile[profile]["missing_likely_relevant_context"] += int(
        "missing_likely_relevant_context" in reasons
        or bool(check.get("missing_likely_relevant_context_ids"))
    )
    per_profile[profile]["stale_evidence_included"] += int(
        "stale_evidence_included" in reasons
        or bool(check.get("included_stale_warning_ids"))
    )
    per_profile[profile]["conflict_evidence_included"] += int(
        "conflict_evidence_included" in reasons
        or bool(check.get("included_conflict_warning_ids"))
    )
for key, value in per_profile["chain_tri_version_governed_answer_contract"].items():
    assert value <= per_profile["chain_tri_governed_answer_contract"][key], (
        key,
        per_profile["chain_tri_governed_answer_contract"],
        per_profile["chain_tri_version_governed_answer_contract"],
    )
for profile, repeats in sorted(per_repeat_cases.items()):
    for repeat, cases in sorted(repeats.items()):
        print(profile, "repeat", repeat, per_repeat_answer[profile][repeat], "/", cases)
for repeat, cases in per_repeat_cases["chain_tri_version_governed_answer_contract"].items():
    assert cases == 40
print("real gates ok")
PY
```

Expected:

```text
real gates ok
```

- [ ] **Step 3: Interpret stability without aborting valid unstable runs**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from collections import defaultdict
from pathlib import Path
path = Path("my_md/memory_optimization/eval_reports/p6o12_safe_version_repeat_stability_v1/memory_comprehensive_online_eval.json")
payload = json.loads(path.read_text(encoding="utf-8"))
m = payload["metrics"]
version = m["profile_summaries"]["chain_tri_version_governed_answer_contract"]
per_repeat_answer = defaultdict(int)
per_repeat_cases = defaultdict(int)
for record in payload["case_records"]:
    if record["profile_name"] != "chain_tri_version_governed_answer_contract":
        continue
    repeat = int(record["repeat_index"])
    per_repeat_cases[repeat] += 1
    per_repeat_answer[repeat] += int(bool(record["answer_rule_passed"]))
stable = (
    float(version["answer_rule_pass_rate"]) >= 97.5
    and all(per_repeat_cases[idx] == 40 and per_repeat_answer[idx] >= 39 for idx in sorted(per_repeat_cases))
    and float(version["memory_grounding_pass_rate"]) == 100.0
    and float(version["forbidden_violation_rate"]) == 0.0
)
for repeat in sorted(per_repeat_cases):
    print("safe_version_repeat", repeat, per_repeat_answer[repeat], "/", per_repeat_cases[repeat])
print("stability_gate", "passed" if stable else "failed")
PY
```

Expected: prints per-repeat counts and either `stability_gate passed` or `stability_gate failed`. A failed stability gate is a valid experimental conclusion and must continue to Task 3; failed infra/privacy/safety gates from Step 2 remain blockers.

---

## Task 3: Generate Repeat Stability Summary

**Files:**
- Create:
  - `my_md/memory_optimization/eval_reports/p6o12_safe_version_repeat_stability_v1/repeat_stability_summary.md`

**Interfaces:**
- Consumes:
  - `memory_comprehensive_online_eval.json`.
- Produces:
  - concise Markdown summary with per-profile totals, per-repeat answer counts, post-check counts, token comparison, and next decision.

- [ ] **Step 1: Generate summary Markdown**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from collections import defaultdict
from pathlib import Path
report_dir = Path("my_md/memory_optimization/eval_reports/p6o12_safe_version_repeat_stability_v1")
payload = json.loads((report_dir / "memory_comprehensive_online_eval.json").read_text(encoding="utf-8"))
m = payload["metrics"]
records = payload["case_records"]
per_repeat = defaultdict(lambda: defaultdict(lambda: {"cases": 0, "answer": 0, "grounding": 0, "forbidden": 0, "tokens": 0}))
post = defaultdict(lambda: defaultdict(int))
for record in records:
    profile = record["profile_name"]
    repeat = int(record["repeat_index"])
    row = per_repeat[profile][repeat]
    row["cases"] += 1
    row["answer"] += int(bool(record["answer_rule_passed"]))
    row["grounding"] += int(bool(record["memory_grounding_passed"]))
    row["forbidden"] += int((record.get("forbidden_contains_violation_count") or 0) > 0)
    row["tokens"] += int(record.get("total_token_count") or 0)
    check = record.get("answer_post_check_shadow") or {}
    reasons = set(check.get("retry_reasons") or ())
    post[profile]["needs_retry"] += int(bool(check.get("needs_retry")))
    post[profile]["forbidden_boundary_included"] += int(
        "forbidden_boundary_included" in reasons
        or bool(check.get("included_forbidden_boundary_ids"))
    )
    post[profile]["missing_likely_relevant_context"] += int(
        "missing_likely_relevant_context" in reasons
        or bool(check.get("missing_likely_relevant_context_ids"))
    )
    post[profile]["stale_evidence_included"] += int(
        "stale_evidence_included" in reasons
        or bool(check.get("included_stale_warning_ids"))
    )
    post[profile]["conflict_evidence_included"] += int(
        "conflict_evidence_included" in reasons
        or bool(check.get("included_conflict_warning_ids"))
    )
profiles = m["profile_summaries"]
base = profiles["chain_tri_governed_answer_contract"]
version = profiles["chain_tri_version_governed_answer_contract"]
version_repeat_answers = [
    per_repeat["chain_tri_version_governed_answer_contract"][idx]["answer"]
    for idx in sorted(per_repeat["chain_tri_version_governed_answer_contract"])
]
stable = (
    float(version["answer_rule_pass_rate"]) >= 97.5
    and all(value >= 39 for value in version_repeat_answers)
    and float(version["memory_grounding_pass_rate"]) == 100.0
    and float(version["forbidden_violation_rate"]) == 0.0
)
lines = [
    "# P6o-12 Safe Version Repeat Stability Summary",
    "",
    "This report is a repeat-stability analysis over an existing real LLM eval output. It does not add profiles, does not enable graph/all-on, and does not change production behavior.",
    "",
    "## Matrix",
    "",
    f"- `case_count`: `{m['case_count']}`",
    f"- `unique_case_count`: `{m['unique_case_count']}`",
    f"- `profile_count`: `{m['profile_count']}`",
    f"- `prompt_variant_count`: `{m['prompt_variant_count']}`",
    f"- `repeat_count`: `{m['repeat_count']}`",
    f"- `provider_error_count`: `{m['provider_error_count']}`",
    f"- `timeout_count`: `{m['timeout_count']}`",
    "",
    "## Profile Totals",
    "",
    "| profile | cases | answer | grounding | forbidden | avg tokens |",
    "| --- | ---: | ---: | ---: | ---: | ---: |",
]
for profile, row in profiles.items():
    lines.append(
        f"| {profile} | {row['case_count']} | {row['answer_success_count']}/{row['case_count']} = {row['answer_rule_pass_rate']}% | {row['memory_grounding_pass_rate']}% | {row['forbidden_violation_rate']}% | {row['avg_total_token_count']} |"
    )
lines.extend(["", "## Per-Repeat Answer Counts", "", "| profile | repeat | answer | grounding | forbidden | avg tokens |", "| --- | ---: | ---: | ---: | ---: | ---: |"])
for profile in sorted(per_repeat):
    for repeat in sorted(per_repeat[profile]):
        row = per_repeat[profile][repeat]
        avg_tokens = round(row["tokens"] / row["cases"], 4) if row["cases"] else 0.0
        lines.append(
            f"| {profile} | {repeat} | {row['answer']}/{row['cases']} | {row['grounding']}/{row['cases']} | {row['forbidden']}/{row['cases']} | {avg_tokens} |"
        )
lines.extend(["", "## Post-Check Shadow", "", "| profile | needs_retry | forbidden_boundary_included | missing_likely_relevant_context | stale_evidence_included | conflict_evidence_included |", "| --- | ---: | ---: | ---: | ---: | ---: |"])
for profile in sorted(post):
    row = post[profile]
    lines.append(
        f"| {profile} | {row['needs_retry']} | {row['forbidden_boundary_included']} | {row['missing_likely_relevant_context']} | {row['stale_evidence_included']} | {row['conflict_evidence_included']} |"
    )
token_delta = round(float(version["avg_total_token_count"]) - float(base["avg_total_token_count"]), 4)
lines.extend([
    "",
    "## Conclusion",
    "",
    f"- Safe version-governed stability gate: `{'passed' if stable else 'failed'}`.",
    f"- Token delta vs governed baseline: `{token_delta}` avg tokens.",
    "- If passed, next step is targeted hard-slice validation before any routed graph design.",
    "- If failed, next step is failure/sensitivity analysis on the unstable repeats before expanding the matrix.",
    "",
])
(report_dir / "repeat_stability_summary.md").write_text("\n".join(lines), encoding="utf-8")
print(report_dir / "repeat_stability_summary.md")
PY
```

Expected:

```text
my_md/memory_optimization/eval_reports/p6o12_safe_version_repeat_stability_v1/repeat_stability_summary.md
```

---

## Task 4: Record Results In Docs

**Files:**
- Modify:
  - `my_md/memory_optimization/README.md`
  - `progress.md`

**Interfaces:**
- Consumes:
  - `memory_comprehensive_online_eval.md`;
  - `repeat_stability_summary.md`.
- Produces:
  - P6o-12 result entry and next-step decision.

- [ ] **Step 1: Update `my_md/memory_optimization/README.md`**

Add one bullet after `Phase 6o11-cross-report-synthesis` with:

```text
Phase 6o12-safe-version-repeat-stability
```

The bullet must include:

```text
report path
matrix shape
provider_error_count
timeout_count
profile total answer/grounding/forbidden/token metrics
per-repeat safe version-governed answer counts
stability gate passed/failed
next decision
```

- [ ] **Step 2: Update `progress.md`**

Append a section:

```markdown
## 2026-07-29 P6o-12 safe version repeat stability
```

The section must include:

```text
plan file path
real report path
summary report path
no graph/all-on
no production activation
key metrics
stability conclusion
next step
```

- [ ] **Step 3: Verify reports/docs do not contain raw prompts or full answers**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path
report = Path("my_md/memory_optimization/eval_reports/p6o12_safe_version_repeat_stability_v1/memory_comprehensive_online_eval.json")
payload = json.loads(report.read_text(encoding="utf-8"))
m = payload["metrics"]
for key in ("raw_query_included", "raw_memory_summary_included", "prompt_included", "session_text_included", "full_answer_included"):
    assert m[key] is False, (key, m[key])
print("json privacy flags ok")
PY
if rg -n "raw_prompt|api[_-]?key|Authorization" \
  my_md/memory_optimization/eval_reports/p6o12_safe_version_repeat_stability_v1/*.md \
  my_md/memory_optimization/README.md; then
  exit 1
fi
if git diff -U0 -- my_md/memory_optimization/README.md progress.md | rg -n "raw_prompt|api[_-]?key|Authorization"; then
  exit 1
else
  echo "docs privacy grep ok"
fi
```

Expected: Python prints `json privacy flags ok`; final shell prints `docs privacy grep ok`.

---

## Task 5: Verification And Commit

**Files:**
- Modify:
  - `my_md/memory_optimization/README.md`
  - `progress.md`
- Create:
  - `docs/superpowers/plans/2026-07-29-memory-p6o12-safe-version-repeat-stability.md`
  - `my_md/memory_optimization/eval_reports/p6o12_safe_version_repeat_stability_v1/memory_comprehensive_online_eval.json`
  - `my_md/memory_optimization/eval_reports/p6o12_safe_version_repeat_stability_v1/memory_comprehensive_online_eval.md`
  - `my_md/memory_optimization/eval_reports/p6o12_safe_version_repeat_stability_v1/repeat_stability_summary.md`

**Interfaces:**
- Consumes: all generated P6o-12 artifacts.
- Produces: one docs/eval commit.

- [ ] **Step 1: Run targeted CLI smoke regression**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_comprehensive_online_cli.py::test_comprehensive_online_cli_p6o8_safe_boundary_fake_provider_matrix_shape \
  tests/test_memory_comprehensive_online_cli.py::test_comprehensive_online_cli_p6o7_version_governed_fake_provider_matrix_shape \
  -q -p no:cacheprovider
```

Expected:

```text
2 passed
```

- [ ] **Step 2: Run diff whitespace check**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 3: Inspect final diff**

Run:

```bash
git status --short
git diff --stat
```

Expected:

```text
M my_md/memory_optimization/README.md
M progress.md
?? my_md/memory_optimization/eval_reports/p6o12_safe_version_repeat_stability_v1/
```

Because `/docs/` is ignored by `.gitignore`, the new plan file is intentionally added with `git add -f` in Step 4.

- [ ] **Step 4: Commit**

Run:

```bash
git add -f \
  docs/superpowers/plans/2026-07-29-memory-p6o12-safe-version-repeat-stability.md
git add \
  my_md/memory_optimization/README.md \
  progress.md \
  my_md/memory_optimization/eval_reports/p6o12_safe_version_repeat_stability_v1/memory_comprehensive_online_eval.json \
  my_md/memory_optimization/eval_reports/p6o12_safe_version_repeat_stability_v1/memory_comprehensive_online_eval.md \
  my_md/memory_optimization/eval_reports/p6o12_safe_version_repeat_stability_v1/repeat_stability_summary.md
git commit -m "docs: record p6o12 safe version repeat stability"
```

Expected: one commit is created on `memory-next`.
