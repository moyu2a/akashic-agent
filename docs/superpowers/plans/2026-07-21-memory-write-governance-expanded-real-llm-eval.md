# Memory Write Governance Expanded Real LLM Eval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add fair common/hard stratified sampling for write-governance online evaluation, run a larger real LLM shadow evaluation, convert it into target-metric evidence, and document whether the 24-case pilot conclusion holds under a broader balanced sample.

**Architecture:** Keep AgentLoop and production memory behavior unchanged. First fix the evaluation sampler so `--case-set all --limit N` is stratified by both `case_set` and category; then reuse the existing online runner to send pre-labeled candidates through real `AgentLoop.process_direct()` with `skip_post_memory=True`, write checkpoint/evidence files, and convert evidence into percentage metrics.

**Tech Stack:** Python, pytest, existing `memory2/eval_write_governance_online.py`, existing `scripts/run_memory_write_governance_online_eval.py`, existing `scripts/run_memory_target_metrics_eval.py`, Markdown docs under `my_md/memory_optimization/`.

## Global Constraints

- Do not modify production `AgentLoop`, `Reasoner`, `ToolExecutor`, `ToolRegistry`, or real memory write behavior.
- The only allowed code behavior change is evaluation sampling inside `memory2/eval_write_governance_online.py`.
- Do not write production memory DB, observe DB, or live workspace; use `/tmp/akashic-memory-write-governance-expanded-real/`.
- Keep real LLM calls behind explicit `--enable-real-llm`.
- Keep `skip_post_memory=True`; this is already enforced by `run_write_governance_online_eval()`.
- Use checkpoint JSONL and `--resume` for every real LLM run.
- Treat provider errors and timeouts as infrastructure failures, not governance failures.
- Do not claim production traffic quality: candidates and labels come from `memory2/eval_write_governance_cases.py`, not natural user traffic or LLM-generated candidate extraction.
- Do not stage or commit `.superpowers/sdd/*.diff`.

---

## File Structure

- Read: `memory2/eval_write_governance_cases.py`
  - Confirms candidate universe: `1200` candidates total, `common 600 + hard 600`, six categories with `200` candidates each.
- Read: `memory2/eval_write_governance_online.py`
  - Confirms and then fixes balanced selection, checkpoint resume, evidence generation, and `skip_post_memory=True` runtime.
- Read: `scripts/run_memory_write_governance_online_eval.py`
  - Confirms CLI flags for `--enable-real-llm`, `--fake-provider`, `--limit`, `--checkpoint-jsonl`, and `--resume`.
- Read: `scripts/run_memory_target_metrics_eval.py`
  - Confirms target metrics conversion entry point.
- Modify: `memory2/eval_write_governance_online.py`
  - Change `select_write_governance_online_candidates()` so `case_set="all"` with `limit > 0` balances `common` and `hard` in addition to categories.
- Modify: `tests/test_memory_write_governance_online_eval.py`
  - Add regression tests proving `limit=24` and `limit=240` include both `common` and `hard` evenly.
- Modify after successful runs: `my_md/memory_optimization/07-memory-write-governance-count-eval.md`
  - Add expanded real LLM results, evidence distribution, target metrics row, and known limitations.
- Modify after successful runs: `my_md/memory_optimization/05-memory-target-metric-eval-plan.md`
  - Promote the write-governance online evidence section from pilot-only to expanded-run status.
- Modify after successful runs: `my_md/memory_optimization/02-memory-quality-metrics.md`
  - Update the three-table summary with the expanded real LLM write-governance evidence.
- Modify after successful runs: `my_md/memory_optimization/01-memory-optimization-roadmap.md`
  - Update the remaining evidence gap wording so it distinguishes 24 pilot, 240 expanded sample, production traffic, and candidate extraction.
- Modify after successful runs: `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
  - Update Phase 6o status and next step.
- Modify after successful runs: `my_md/memory_optimization/README.md`
  - Update current execution position.
- Modify after successful runs: `progress.md`
  - Add exact command outputs and conclusion for session recovery.
- Modify after successful runs: `task_plan.md`
  - Add execution evidence, boundaries, and next task.

## Evaluation Design

Run three levels, stopping only if the previous level has infrastructure failures that cannot be resolved:

| Level | Purpose | Candidate count | Expected rough cost/time from pilot |
| --- | --- | ---: | --- |
| fake full dry-run | Verify full `1200` candidate path without provider spend | `1200` | low cost, local only |
| real balanced expanded | Main result for the next report, with common/hard and category stratification | `240` | about `1.24M` tokens, about `11-15` minutes at pilot latency |
| real full optional | Strongest dataset-driven result if budget/time allow | `1200` | about `6.2M` tokens, about `55-75` minutes at pilot latency |

Primary report for the user should be the `240` real balanced expanded run unless the user explicitly chooses the full `1200` run after seeing the `240` result.

## Success Criteria

- Fake full dry-run completes with `candidate_count = 1200`, `infra_passed = True`, `provider_error_count = 0`, and `timeout_count = 0`.
- `select_write_governance_online_candidates(case_set="all", limit=240)` returns `common 120 + hard 120` and each of the six categories has `40` candidates.
- Real expanded run completes with `candidate_count = 240`, checkpoint row count `240`, evidence row count `240`, `infra_passed = True`, `provider_error_count = 0`, and `timeout_count = 0`.
- Target metrics conversion accepts the real evidence JSONL and produces an online write evidence row.
- The final written conclusion uses counts and percentages:
  - useful candidates: allowed/rejected/reviewed counts;
  - pollution candidates: rejected/reviewed/allowed counts;
  - duplicate candidates: rejected/reviewed/allowed counts;
  - conflict candidates: review/reject/allow counts;
  - effective write precision before/after;
  - pollution block rate before/after;
  - duplicate control rate before/after;
  - conflict review rate before/after;
  - write reduction rate before/after;
  - false reject rate before/after;
  - false accept rate before/after.
- Documentation clearly states that this is still test-set-driven real LLM shadow evidence, not production natural traffic and not LLM candidate extraction quality.

---

### Task 1: Preflight and Current Sampler Sanity Check

**Files:**
- Read: `memory2/eval_write_governance_cases.py`
- Read: `memory2/eval_write_governance_online.py`

**Interfaces:**
- Consumes: `build_write_governance_candidates(case_set="all")`
- Consumes: `select_write_governance_online_candidates(case_set="all", limit=N)`
- Produces: verified candidate universe and confirms whether current limited sampling is fair across `common` and `hard`.

- [ ] **Step 1: Confirm worktree and untracked review diff boundary**

Run:

```bash
git status --short
```

Expected:

```text
Only .superpowers/sdd/*.diff may be untracked before this task starts.
No production code or docs should be dirty except files intentionally modified later by this plan.
```

- [ ] **Step 2: Confirm total candidate universe**

Run:

```bash
.venv/bin/python - <<'PY'
from collections import Counter
from memory2.eval_write_governance_cases import build_write_governance_candidates

candidates = build_write_governance_candidates(case_set="all")
print("total", len(candidates))
print("case_set", dict(Counter(c.case_set for c in candidates)))
print("category", dict(Counter(c.category for c in candidates)))
PY
```

Expected:

```text
total 1200
case_set {'common': 600, 'hard': 600}
category {'valuable_preference': 200, 'stable_fact': 200, 'temporary': 200, 'assistant_inference': 200, 'duplicate': 200, 'conflict': 200}
```

- [ ] **Step 3: Inspect current `240` sample before changing code**

Run:

```bash
.venv/bin/python - <<'PY'
from collections import Counter
from memory2.eval_write_governance_online import select_write_governance_online_candidates, label_for_candidate

candidates = select_write_governance_online_candidates(case_set="all", limit=240)
print("total", len(candidates))
print("case_set", dict(Counter(c.case_set for c in candidates)))
print("category", dict(Counter(c.category for c in candidates)))
print("label", dict(Counter(label_for_candidate(c) for c in candidates)))
PY
```

Expected:

```text
total 240
case_set currently may show {'common': 240}; that is the bug this plan fixes.
category {'valuable_preference': 40, 'stable_fact': 40, 'temporary': 40, 'assistant_inference': 40, 'duplicate': 40, 'conflict': 40}
label {'useful': 80, 'pollution': 80, 'duplicate': 40, 'conflict': 40}
```

---

### Task 2: Add Common/Hard Stratified Sampler

**Files:**
- Modify: `tests/test_memory_write_governance_online_eval.py`
- Modify: `memory2/eval_write_governance_online.py`

**Interfaces:**
- Consumes: `select_write_governance_online_candidates(case_set="all", limit=N)`
- Produces: selector behavior where `case_set="all"` balances both `case_set` and category for limited samples.

- [ ] **Step 1: Add failing sampler regression test**

Append this test to `tests/test_memory_write_governance_online_eval.py`:

```python
def test_select_write_governance_online_candidates_balances_case_set_and_category() -> None:
    from collections import Counter

    pilot_candidates = select_write_governance_online_candidates(case_set="all", limit=24)
    candidates = select_write_governance_online_candidates(case_set="all", limit=240)

    assert len(pilot_candidates) == 24
    assert Counter(candidate.case_set for candidate in pilot_candidates) == {
        "common": 12,
        "hard": 12,
    }
    assert Counter(candidate.category for candidate in pilot_candidates) == {
        "valuable_preference": 4,
        "stable_fact": 4,
        "temporary": 4,
        "assistant_inference": 4,
        "duplicate": 4,
        "conflict": 4,
    }

    assert len(candidates) == 240
    assert Counter(candidate.case_set for candidate in candidates) == {
        "common": 120,
        "hard": 120,
    }
    assert Counter(candidate.category for candidate in candidates) == {
        "valuable_preference": 40,
        "stable_fact": 40,
        "temporary": 40,
        "assistant_inference": 40,
        "duplicate": 40,
        "conflict": 40,
    }
```

- [ ] **Step 2: Run test and verify it fails before implementation**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_write_governance_online_eval.py::test_select_write_governance_online_candidates_balances_case_set_and_category -q -p no:cacheprovider
```

Expected:

```text
FAIL because current limited selection is category-balanced but not common/hard-balanced.
```

- [ ] **Step 3: Implement stratified limited selection**

Replace the limited-selection block in `memory2/eval_write_governance_online.py` with this shape:

```python
def select_write_governance_online_candidates(
    *,
    case_set: str = "all",
    limit: int = 0,
) -> tuple[WriteGovernanceCandidate, ...]:
    from memory2.eval_write_governance_cases import build_write_governance_candidates

    candidates = build_write_governance_candidates(case_set=case_set)
    if limit <= 0 or limit >= len(candidates):
        return tuple(candidates)
    if str(case_set or "all").strip().lower() == "all":
        return _select_write_governance_candidates_by_case_set_and_category(
            candidates,
            limit,
        )
    return _select_write_governance_candidates_by_category(candidates, limit)


def _select_write_governance_candidates_by_category(
    candidates: Sequence[WriteGovernanceCandidate],
    limit: int,
) -> tuple[WriteGovernanceCandidate, ...]:
    by_category: dict[str, list[WriteGovernanceCandidate]] = {
        category: [] for category in _CATEGORY_ORDER
    }
    for candidate in candidates:
        by_category.setdefault(candidate.category, []).append(candidate)
    selected: list[WriteGovernanceCandidate] = []
    while len(selected) < limit:
        progressed = False
        for category in _CATEGORY_ORDER:
            bucket = by_category.get(category) or []
            if bucket:
                selected.append(bucket.pop(0))
                progressed = True
                if len(selected) >= limit:
                    break
        if not progressed:
            break
    return tuple(selected)


def _select_write_governance_candidates_by_case_set_and_category(
    candidates: Sequence[WriteGovernanceCandidate],
    limit: int,
) -> tuple[WriteGovernanceCandidate, ...]:
    case_set_order = ("common", "hard")
    by_stratum: dict[tuple[str, str], list[WriteGovernanceCandidate]] = {
        (current_case_set, category): []
        for current_case_set in case_set_order
        for category in _CATEGORY_ORDER
    }
    for candidate in candidates:
        by_stratum.setdefault((candidate.case_set, candidate.category), []).append(candidate)
    selected: list[WriteGovernanceCandidate] = []
    while len(selected) < limit:
        progressed = False
        for current_case_set in case_set_order:
            for category in _CATEGORY_ORDER:
                bucket = by_stratum.get((current_case_set, category)) or []
                if bucket:
                    selected.append(bucket.pop(0))
                    progressed = True
                    if len(selected) >= limit:
                        break
            if len(selected) >= limit:
                break
        if not progressed:
            break
    return tuple(selected)
```

- [ ] **Step 4: Run focused sampler tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_write_governance_online_eval.py::test_select_write_governance_online_candidates_balances_categories tests/test_memory_write_governance_online_eval.py::test_select_write_governance_online_candidates_balances_case_set_and_category -q -p no:cacheprovider
```

Expected:

```text
Both tests pass.
```

---

### Task 3: Run Fake Full Dry-Run Before Spending Provider Tokens

**Files:**
- Output only: `/tmp/akashic-memory-write-governance-expanded-fake/`

**Interfaces:**
- Consumes: `scripts/run_memory_write_governance_online_eval.py --fake-provider --limit 0`
- Produces: fake full report and target metrics report.

- [ ] **Step 1: Run full fake-provider online shadow**

Run:

```bash
.venv/bin/python scripts/run_memory_write_governance_online_eval.py \
  --workspace /tmp/akashic-memory-write-governance-expanded-fake/workspace \
  --out-dir /tmp/akashic-memory-write-governance-expanded-fake/reports \
  --fake-provider \
  --case-set all \
  --limit 0 \
  --checkpoint-jsonl /tmp/akashic-memory-write-governance-expanded-fake/reports/checkpoint.jsonl \
  --resume
```

Expected:

```text
/tmp/akashic-memory-write-governance-expanded-fake/reports/memory_write_governance_online_eval.json
/tmp/akashic-memory-write-governance-expanded-fake/reports/memory_write_governance_online_eval.md
/tmp/akashic-memory-write-governance-expanded-fake/reports/memory_write_governance_online_evidence.jsonl
```

- [ ] **Step 2: Convert fake evidence into target metrics**

Run:

```bash
.venv/bin/python scripts/run_memory_target_metrics_eval.py \
  --out-dir /tmp/akashic-memory-write-governance-expanded-fake/target \
  --online-checkpoint-source fake_provider \
  --online-write-evidence-json /tmp/akashic-memory-write-governance-expanded-fake/reports/memory_write_governance_online_evidence.jsonl
```

Expected:

```text
/tmp/akashic-memory-write-governance-expanded-fake/target/memory_target_metrics_eval.json
/tmp/akashic-memory-write-governance-expanded-fake/target/memory_target_metrics_eval.md
```

- [ ] **Step 3: Inspect fake full summary**

Run:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

report = json.loads(Path("/tmp/akashic-memory-write-governance-expanded-fake/reports/memory_write_governance_online_eval.json").read_text(encoding="utf-8"))
metrics = report["metrics"]
print("candidate_count", metrics["candidate_count"])
print("infra_passed", metrics["infra_passed"])
print("provider_error_count", metrics["provider_error_count"])
print("timeout_count", metrics["timeout_count"])
print("evidence_record_count", metrics["evidence_record_count"])
PY
```

Expected:

```text
candidate_count 1200
infra_passed True
provider_error_count 0
timeout_count 0
evidence_record_count 1200
```

---

### Task 4: Run Real LLM Expanded 240-Case Shadow Eval

**Files:**
- Output only: `/tmp/akashic-memory-write-governance-expanded-real-240/`

**Interfaces:**
- Consumes: `scripts/run_memory_write_governance_online_eval.py --enable-real-llm --limit 240`
- Produces: checkpoint, real online report, evidence JSONL, and target metrics report.

- [ ] **Step 1: Run the real LLM expanded shadow evaluation**

Run:

```bash
.venv/bin/python scripts/run_memory_write_governance_online_eval.py \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --workspace /tmp/akashic-memory-write-governance-expanded-real-240/workspace \
  --out-dir /tmp/akashic-memory-write-governance-expanded-real-240/reports \
  --enable-real-llm \
  --case-set all \
  --limit 240 \
  --timeout-s 60 \
  --concurrency 1 \
  --checkpoint-jsonl /tmp/akashic-memory-write-governance-expanded-real-240/reports/checkpoint.jsonl \
  --resume
```

Expected:

```text
The command exits 0 if all 240 rows complete without provider_error or timeout.
If network/provider fails, keep the checkpoint and rerun the exact command with --resume after resolving the infrastructure issue.
```

- [ ] **Step 2: Convert real evidence into target metrics**

Run:

```bash
.venv/bin/python scripts/run_memory_target_metrics_eval.py \
  --out-dir /tmp/akashic-memory-write-governance-expanded-real-240/target \
  --online-checkpoint-source real_llm \
  --online-write-evidence-json /tmp/akashic-memory-write-governance-expanded-real-240/reports/memory_write_governance_online_evidence.jsonl
```

Expected:

```text
/tmp/akashic-memory-write-governance-expanded-real-240/target/memory_target_metrics_eval.json
/tmp/akashic-memory-write-governance-expanded-real-240/target/memory_target_metrics_eval.md
```

- [ ] **Step 3: Extract counts for the final user-facing table**

Run:

```bash
.venv/bin/python - <<'PY'
import json
from collections import Counter, defaultdict
from pathlib import Path

base = Path("/tmp/akashic-memory-write-governance-expanded-real-240")
report = json.loads((base / "reports/memory_write_governance_online_eval.json").read_text(encoding="utf-8"))
records = [
    json.loads(line)
    for line in (base / "reports/memory_write_governance_online_evidence.jsonl").read_text(encoding="utf-8").splitlines()
    if line.strip()
]
metrics = report["metrics"]
print("summary", {k: metrics[k] for k in ["candidate_count", "infra_passed", "provider_error_count", "timeout_count", "total_token_count", "avg_latency_ms"]})
by_label = defaultdict(Counter)
for row in records:
    by_label[row["label"]][row["after_decision"]] += 1
    by_label[row["label"]]["total"] += 1
print("by_label", {label: dict(counter) for label, counter in sorted(by_label.items())})
PY
```

Expected:

```text
summary includes candidate_count 240, infra_passed True, provider_error_count 0, timeout_count 0.
by_label includes useful total 80, pollution total 80, duplicate total 40, conflict total 40.
```

---

### Task 5: Optional Full 1200-Case Real LLM Run

**Files:**
- Output only: `/tmp/akashic-memory-write-governance-expanded-real-1200/`

**Interfaces:**
- Consumes: same runner as Task 4 with `--limit 0`
- Produces: strongest dataset-driven real LLM shadow evidence if budget/time allow.

- [ ] **Step 1: Decide whether to run full 1200**

Use the Task 4 results as a gate:

```text
Run full 1200 only if the 240 run has provider_error_count = 0, timeout_count = 0, and the user accepts the expected token/time cost.
```

- [ ] **Step 2: Run full 1200 real LLM evaluation if approved**

Run:

```bash
.venv/bin/python scripts/run_memory_write_governance_online_eval.py \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --workspace /tmp/akashic-memory-write-governance-expanded-real-1200/workspace \
  --out-dir /tmp/akashic-memory-write-governance-expanded-real-1200/reports \
  --enable-real-llm \
  --case-set all \
  --limit 0 \
  --timeout-s 60 \
  --concurrency 1 \
  --checkpoint-jsonl /tmp/akashic-memory-write-governance-expanded-real-1200/reports/checkpoint.jsonl \
  --resume
```

Expected:

```text
The command exits 0 if all 1200 rows complete without provider_error or timeout.
If interrupted, rerun the same command with --resume.
```

- [ ] **Step 3: Convert full real evidence if full run is executed**

Run:

```bash
.venv/bin/python scripts/run_memory_target_metrics_eval.py \
  --out-dir /tmp/akashic-memory-write-governance-expanded-real-1200/target \
  --online-checkpoint-source real_llm \
  --online-write-evidence-json /tmp/akashic-memory-write-governance-expanded-real-1200/reports/memory_write_governance_online_evidence.jsonl
```

Expected:

```text
Target metrics report exists and uses online_write_record_count 1200.
```

---

### Task 6: Update Documentation With Expanded Results

**Files:**
- Modify: `my_md/memory_optimization/07-memory-write-governance-count-eval.md`
- Modify: `my_md/memory_optimization/05-memory-target-metric-eval-plan.md`
- Modify: `my_md/memory_optimization/02-memory-quality-metrics.md`
- Modify: `my_md/memory_optimization/01-memory-optimization-roadmap.md`
- Modify: `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
- Modify: `my_md/memory_optimization/README.md`
- Modify: `progress.md`
- Modify: `task_plan.md`

**Interfaces:**
- Consumes: reports from Task 4 and optional Task 5.
- Produces: persistent documentation for session recovery and later interview explanation.

- [ ] **Step 1: Add the expanded run result to `07-memory-write-governance-count-eval.md`**

Insert a new section after the current 24-case pilot:

```markdown
## 真实 LLM 扩展样本评测

本轮使用同一条写入治理线上 shadow 链路，把样本从 `24` 条扩展到 `240` 条平衡候选。候选仍来自测试集，标签仍来自人工设计的目标导向模板；真实 LLM 只参与 `AgentLoop.process_direct()` 的在线路径，不负责生成候选标签。

| 项目 | 数值 |
| --- | ---: |
| candidate_count | `240` |
| real_llm_enabled | `True` |
| infra_passed | `True` |
| provider_error_count | `0` |
| timeout_count | `0` |
| total_token_count | measured value from `/tmp/akashic-memory-write-governance-expanded-real-240/reports/memory_write_governance_online_eval.json` |
| avg_latency_ms | measured value from `/tmp/akashic-memory-write-governance-expanded-real-240/reports/memory_write_governance_online_eval.json` |

| label | count | after allow | after reject | after review |
| --- | ---: | ---: | ---: | ---: |
| useful | `80` | measured value | measured value | measured value |
| pollution | `80` | measured value | measured value | measured value |
| duplicate | `40` | measured value | measured value | measured value |
| conflict | `40` | measured value | measured value | measured value |
```

Replace every `measured value` cell with values from Task 4 before committing the document.

- [ ] **Step 2: Update target metric table references**

In `05-memory-target-metric-eval-plan.md` and `02-memory-quality-metrics.md`, replace pilot-only wording with:

```text
Phase 6o 已有 24 条真实 LLM pilot 和 240 条真实 LLM 扩展样本。当前正式展示优先使用 240 条扩展样本；24 条 pilot 保留为链路验证历史。
```

- [ ] **Step 3: Update roadmap and README**

In `01-memory-optimization-roadmap.md`, `04-memory-plugin-experiment-roadmap.md`, and `README.md`, add:

```text
Phase 6o 的当前主结论已从 24 条 pilot 升级为 240 条真实 LLM shadow 扩展样本。它证明测试集驱动 evidence 链路在更大平衡样本下仍可运行，但仍不是生产流量，也不是候选抽取质量评测。
```

- [ ] **Step 4: Update recovery docs**

In `progress.md` and `task_plan.md`, record:

```text
report paths
target metric paths
exact command
candidate_count
checkpoint row count
evidence row count
provider_error_count
timeout_count
total_token_count
avg_latency_ms
main target metric percentages
boundary notes
```

---

### Task 7: Verification and Commit

**Files:**
- Verify: `memory2/eval_write_governance_online.py`
- Verify: `tests/test_memory_write_governance_online_eval.py`
- Verify: all docs modified in Task 6.
- Verify: this plan file.

**Interfaces:**
- Consumes: all doc edits and generated reports.
- Produces: one documentation/evidence commit.

- [ ] **Step 1: Run focused regression tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_memory_write_governance_online_eval.py \
  tests/test_memory_write_governance_online_cli.py \
  tests/test_memory_target_metrics_cli.py \
  tests/test_memory_write_governance_counts.py \
  tests/test_memory_write_governance_counts_cli.py \
  -q -p no:cacheprovider
```

Expected:

```text
All selected tests pass.
```

- [ ] **Step 2: Run diff whitespace checks**

Run:

```bash
git diff --check
```

Expected:

```text
No output and exit code 0.
```

- [ ] **Step 3: Confirm staged file list excludes review diffs**

Run:

```bash
git status --short
```

Expected:

```text
Modified docs/progress/task_plan files are visible.
.superpowers/sdd/*.diff may remain untracked but must not be staged.
```

- [ ] **Step 4: Stage only intended docs**

Run:

```bash
git add \
  memory2/eval_write_governance_online.py \
  tests/test_memory_write_governance_online_eval.py \
  my_md/memory_optimization/01-memory-optimization-roadmap.md \
  my_md/memory_optimization/07-memory-write-governance-count-eval.md \
  my_md/memory_optimization/05-memory-target-metric-eval-plan.md \
  my_md/memory_optimization/02-memory-quality-metrics.md \
  my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md \
  my_md/memory_optimization/README.md \
  progress.md \
  task_plan.md
git add -f docs/superpowers/plans/2026-07-21-memory-write-governance-expanded-real-llm-eval.md
```

Expected:

```text
Only the sampler code, sampler test, plan file, and intended documentation files are staged.
.superpowers/sdd/*.diff remains unstaged.
```

- [ ] **Step 5: Verify staged diff and commit**

Run:

```bash
git diff --cached --check
git diff --cached --stat
git commit -m "feat: stratify write governance online eval sample"
```

Expected:

```text
git diff --cached --check exits 0.
Commit is created.
```

---

## Plan Self-Review

### Spec Coverage

- The plan expands the current 24-case pilot into a larger real LLM write-governance shadow evaluation.
- The plan fixes the current limited sampler so the expanded `240` result is not biased toward `common` cases.
- It keeps the evaluation scoped to write governance, not answer/retrieval and not sleep hygiene.
- It preserves project safety boundaries: no production memory DB writes, no AgentLoop behavior changes, checkpoint/resume required, provider errors separated from governance metrics.
- It produces counts and percentages instead of opaque scores.
- It includes documentation updates and commit steps.

### Placeholder Scan

- The plan contains no placeholder tokens such as `TBD`, `TODO`, or `<fill>`.
- Documentation templates use the phrase `measured value`, and the task explicitly requires replacing those cells with actual report values before commit.

### Type and Interface Consistency

- `build_write_governance_candidates(case_set="all")` and `select_write_governance_online_candidates(case_set="all", limit=240)` match the current code.
- CLI flags match `scripts/run_memory_write_governance_online_eval.py`.
- Target metric evidence flag `--online-write-evidence-json` matches `scripts/run_memory_target_metrics_eval.py`.
- The expected evidence labels `useful`, `pollution`, `duplicate`, and `conflict` match `label_for_candidate()`.

## Execution Results

Executed on 2026-07-22.

- Task 1 complete: preflight confirmed `1200` total candidates, `common = 600`, `hard = 600`, six categories with `200` each. Old limited sampling returned `common = 240`, `hard = 0` for `limit=240`.
- Task 2 complete: added regression coverage and implemented common/hard + category stratified limited sampling.
  - RED: new test failed with `Counter({'common': 24})`.
  - GREEN: focused sampler tests passed with `2 passed in 0.21s`.
- Task 3 complete: fake-provider full 1200 run passed.
  - reports: `/tmp/akashic-memory-write-governance-expanded-fake/reports`
  - target: `/tmp/akashic-memory-write-governance-expanded-fake/target`
  - `candidate_count = 1200`, `checkpoint rows = 1200`, `evidence rows = 1200`, `provider_error_count = 0`, `timeout_count = 0`.
- Task 4 complete: real LLM 240 run passed.
  - reports: `/tmp/akashic-memory-write-governance-expanded-real-240/reports`
  - target: `/tmp/akashic-memory-write-governance-expanded-real-240/target`
  - `candidate_count = 240`, `common = 120`, `hard = 120`, each category `40`, `provider_error_count = 0`, `timeout_count = 0`, `total_token_count = 1236228`, `avg_latency_ms = 2366.625`.
  - evidence: useful `80` allow, pollution `80` reject, duplicate `40` reject, conflict `40` review.
  - target metrics: useful write precision `33.3333% -> 100.0%`, pollution block `0.0% -> 100.0%`, duplicate control `0.0% -> 100.0%`, conflict review `0.0% -> 100.0%`, write reduction `0.0% -> 66.6667%`, false reject `0.0% -> 0.0%`, false accept `100.0% -> 0.0%`.
- Task 5 skipped by design: optional real 1200 run was not executed without explicit cost approval.
- Task 6 complete: memory optimization docs, `progress.md`, and `task_plan.md` updated.
- Task 7 verification and commit are handled after this plan update.
