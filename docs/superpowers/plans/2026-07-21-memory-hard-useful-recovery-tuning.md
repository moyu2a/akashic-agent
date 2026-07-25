# Memory Hard Useful Recovery Tuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve offline write-governance final retention for hard useful memory candidates by removing broad temporary-marker false positives, while preserving pollution control, duplicate blocking, and conflict review behavior.

**Architecture:** Keep the current two-stage write-governance architecture: first-stage `score_write_candidate_shadow()` classifies candidates as `allow/review/reject`, then `resolve_write_review_candidate()` and `apply_final_write_safety_gate()` produce final offline write decisions. This plan only tightens first-stage temporary-risk detection in `plugins/default_memory/experiments.py` and extends offline diagnostics/reporting; it does not change AgentLoop, live memory writes, production DB state, or real LLM behavior.

**Tech Stack:** Python dataclasses, existing `plugins.default_memory.experiments.score_write_candidate_shadow`, existing `memory2.write_governance_review`, existing 1200-candidate offline case pack, pytest, JSON/Markdown report writers.

## Global Constraints

- All commands must run from `/home/jjh/git_work/akashic-agent/.worktrees/memory-experiments-phase0`.
- Do not call a real LLM.
- Do not read or write production memory DB, observe DB, or user workspace memory state.
- Do not modify AgentLoop, Reasoner, ToolExecutor, ToolRegistry, or live memory write behavior.
- Do not lower the global `allow` threshold to improve metrics.
- Keep original write behavior as baseline: all candidates are counted as written before governance.
- Keep first-stage direct-write metrics comparable with the previous report.
- Keep resolver and final safety gate decision logic free of eval labels such as `category`, `case_set`, and `subtype`; those labels may be used only by offline report grouping and metric denominators.
- This phase may modify first-stage marker logic in `score_write_candidate_shadow()` because the current hard useful gap is caused before candidates reach the review resolver.
- `score_write_candidate_shadow()` is shared by offline/shadow experiment traces, including `MemoryExperimentRunner.record_write_value_shadow()`. Therefore final verification must cover both write-governance count tests and existing memory experiment runner tests.
- Current measured gap before this plan:
  - useful final retention: `350/400 = 87.5%`;
  - hard useful final retention: `150/200 = 75.0%`;
  - hard useful miss count: `50/200`;
  - conflict review preservation: `196/200 = 98.0%`;
  - conflict miss count: `4/200`;
  - final pollution control: `800/800 = 100.0%`;
  - hard duplicate leakage: `0/100 = 0.0%`.
- Root cause found before this plan:
  - the `50` hard useful misses are all first-stage `reject` with reason `temporary_state`;
  - they contain stable exception wording such as `除非用户临时改口，否则在更新 my_md 时保持标出风险`;
  - the remaining `4` conflict misses are also first-stage `reject` with reason `temporary_state`, caused by broad matching such as `不要记` inside `不要记录来源`.
- Offline gate targets after this plan:
  - useful final retention `>= 95.0%`;
  - hard useful final retention `>= 95.0%`;
  - final pollution control `>= 98.0%`;
  - conflict review preservation `>= 99.0%`;
  - hard duplicate leakage `== 0.0%`.

---

### Task 0: Commit Current Gap Documentation State

**Files:**
- Modify already pending: `my_md/memory_optimization/07-memory-write-governance-count-eval.md`
- Modify already pending: `my_md/memory_optimization/README.md`
- Modify already pending: `progress.md`
- Modify already pending: `task_plan.md`

**Interfaces:**
- Produces a clean documentation baseline commit before code tuning.

- [ ] **Step 1: Verify pending files**

Run:

```bash
git status --short
```

Expected: only the four documentation files above are modified, plus untracked `.superpowers/sdd/*.diff` review artifacts. This plan lives under ignored `docs/`, so normal `git status --short` may not show it until it is staged with `git add -f`. If any other modified tracked file appears, stop and inspect it before staging; do not revert user changes.

- [ ] **Step 2: Run documentation diff check**

Run:

```bash
git diff --check
```

Expected: exit `0`.

- [ ] **Step 3: Stage current documentation gap files only**

Run:

```bash
git add my_md/memory_optimization/07-memory-write-governance-count-eval.md my_md/memory_optimization/README.md progress.md task_plan.md
```

- [ ] **Step 4: Commit current documentation gap files**

Run:

```bash
git commit -m "docs: record write governance ideal gap"
```

Expected: commit succeeds. Do not stage `.superpowers/sdd/*.diff`.

---

### Task 1: Add Regression Tests For Temporary Marker False Positives

**Files:**
- Modify: `tests/test_memory_write_governance_counts.py`

**Interfaces:**
- Consumes: `score_write_candidate_shadow(summary, source_ref="", existing_memories=None) -> dict[str, Any]`
- Consumes: `resolve_write_review_candidate(summary=str, score_result=dict, source_ref=str) -> WriteReviewResolution`
- Produces: regression tests proving stable exception wording and `不要记录来源` are not temporary-state pollution.

- [ ] **Step 1: Add failing regression tests**

Append these tests near the existing write-governance policy tests in `tests/test_memory_write_governance_counts.py`:

```python
def test_write_governance_treats_temporary_exception_as_stable_rule() -> None:
    summary = "难例/valuable_preference/exception_rule：面试材料：除非用户临时改口，否则在更新 my_md 时保持标出风险，样本 18"
    scored = score_write_candidate_shadow(
        summary,
        source_ref="offline:test",
    )

    assert scored["reason"] != "temporary_state"
    assert "temporary_state" not in scored["reasons"]
    assert scored["decision"] in {"allow", "review"}

    resolution = resolve_write_review_candidate(
        summary=summary,
        score_result=scored,
        source_ref="offline:test",
    )

    assert resolution.decision == "approve_write"


def test_write_governance_treats_english_temporary_exception_as_stable_rule() -> None:
    scored = score_write_candidate_shadow(
        "Stable rule: unless the user makes a temporary exception, keep source references in follow-up memory reports",
        source_ref="offline:test",
    )

    assert scored["reason"] != "temporary_state"
    assert "temporary_state" not in scored["reasons"]
    assert scored["decision"] in {"allow", "review"}


def test_write_governance_does_not_treat_do_not_record_source_as_temporary() -> None:
    scored = score_write_candidate_shadow(
        "常见/conflict/opposite_scope：面试材料：长期项目约定改为不要记录来源，而是先完整铺开解释，样本 6",
        source_ref="offline:test",
        existing_memories=[
            {
                "id": "existing",
                "summary": "面试材料：长期项目约定是在解释失败原因时记录来源，样本 6",
                "memory_type": "procedure",
            }
        ],
    )

    assert scored["decision"] == "review"
    assert scored["reason"] == "conflict_with_existing_memory"
    assert "temporary_state" not in scored["reasons"]


def test_write_governance_keeps_precise_temporary_markers_rejected() -> None:
    samples = [
        "记忆实验：今天这次先保留关键数字，后续不用沿用，样本 1",
        "代码审阅：本轮调试临时采用完整长文解释，完成后恢复默认，样本 2",
        "插件文档：这个草稿只服务当前排查，先不用长期保存，样本 3",
        "评测报告：会议前临时记一下记录来源，过期后不再使用，样本 4",
        "用户偏好：不要写入长期记忆，只用于当前会话，样本 5",
        "用户偏好：不要记住这条临时状态，样本 6",
    ]

    for summary in samples:
        scored = score_write_candidate_shadow(summary, source_ref="offline:test")
        assert scored["decision"] == "reject", summary
        assert scored["reason"] == "temporary_state", summary
```

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_write_governance_counts.py::test_write_governance_treats_temporary_exception_as_stable_rule tests/test_memory_write_governance_counts.py::test_write_governance_does_not_treat_do_not_record_source_as_temporary tests/test_memory_write_governance_counts.py::test_write_governance_keeps_precise_temporary_markers_rejected -q -p no:cacheprovider
```

Expected before implementation: at least the first two tests fail because current broad temporary matching treats `临时` and `不要记` too broadly.

---

### Task 2: Tighten Temporary-Risk Detection

**Files:**
- Modify: `plugins/default_memory/experiments.py`
- Modify: `tests/test_memory_write_governance_counts.py`

**Interfaces:**
- Produces helper:

```python
def _has_temporary_risk_marker(text: str) -> bool
```

- Keeps public function signature unchanged:

```python
def score_write_candidate_shadow(
    summary: str,
    *,
    source_ref: str = "",
    existing_memories: list[dict[str, object]] | None = None,
) -> dict[str, Any]
```

- [ ] **Step 1: Replace broad temporary matching with a helper**

In `plugins/default_memory/experiments.py`, delete the local `temporary_markers` block inside `score_write_candidate_shadow()`:

```python
    temporary_markers = (
        "临时",
        "临时测试",
        "本轮调试",
        "今天这次",
        "本次",
        "这一次",
        "先不用长期保存",
        "过期后不再使用",
        "不要写入长期记忆",
        "不要记",
        "do not remember",
    )
```

Then replace the local marker call:

```python
    temporary = _contains_any(text, temporary_markers)
```

with:

```python
    temporary = _has_temporary_risk_marker(text)
```

- [ ] **Step 2: Add the helper near the existing marker helpers**

Add this helper in `plugins/default_memory/experiments.py` near `_contains_any()` or before `score_write_candidate_shadow()`:

```python
def _has_temporary_risk_marker(text: str) -> bool:
    normalized = str(text or "")
    temporary_markers = (
        "临时测试",
        "本轮调试",
        "今天这次",
        "本次",
        "这一次",
        "当前会话",
        "只用于当前",
        "只服务当前排查",
        "先不用长期保存",
        "过期后不再使用",
        "不要写入长期记忆",
        "不要记住",
        "不要记录到长期记忆",
        "temporary",
        "do not remember",
    )
    return _contains_any(normalized, temporary_markers)
```

Do not include broad standalone `"临时"`, `"不要记"`, or English `"temporary"` in this helper. The wording `除非用户临时改口` and `temporary exception` are stable-rule exception clauses, and `不要记录来源` is a conflict/update rule, not temporary memory pollution.

- [ ] **Step 3: Run the regression tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_write_governance_counts.py::test_write_governance_treats_temporary_exception_as_stable_rule tests/test_memory_write_governance_counts.py::test_write_governance_does_not_treat_do_not_record_source_as_temporary tests/test_memory_write_governance_counts.py::test_write_governance_keeps_precise_temporary_markers_rejected -q -p no:cacheprovider
```

Expected: `3 passed`.

- [ ] **Step 4: Run the existing write-governance focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_write_governance_counts.py -q -p no:cacheprovider
```

Expected: all tests pass. If any temporary-pollution regression fails, restore a precise marker for that case rather than reintroducing broad `"临时"` or `"不要记"`.

---

### Task 3: Add Final Gap Metrics To The Offline Report

**Files:**
- Modify: `memory2/eval_write_governance_counts.py`
- Modify: `tests/test_memory_write_governance_counts.py`

**Interfaces:**
- Adds metrics keys to `WriteGovernanceCountReport.metrics`:

```python
"useful_final_gap_count": int
"hard_useful_final_gap_count": int
"conflict_review_gap_count": int
"strict_ideal_gap_count": int
```
- Adds Markdown rows under `## 复核处理总体指标`:

```python
        f"| 有用候选最终缺口 | {report.metrics['useful_final_gap_count']} |",
        f"| hard 有用候选最终缺口 | {report.metrics['hard_useful_final_gap_count']} |",
        f"| 冲突复核缺口 | {report.metrics['conflict_review_gap_count']} |",
        f"| 严格理想差距总数 | {report.metrics['strict_ideal_gap_count']} |",
```

- [ ] **Step 1: Add metrics recomputation tests**

Append this test to `tests/test_memory_write_governance_counts.py`:

```python
def test_write_governance_report_exposes_gap_to_strict_ideal() -> None:
    report = build_write_governance_count_report(build_write_governance_candidates())
    metrics = report.metrics

    assert metrics["useful_final_gap_count"] == (
        metrics["useful_candidate_count"] - metrics["useful_final_written_count"]
    )
    assert metrics["hard_useful_final_gap_count"] == (
        metrics["hard_useful_candidate_count"] - metrics["hard_useful_final_written_count"]
    )
    assert metrics["conflict_review_gap_count"] == (
        metrics["expected_review_candidate_count"] - metrics["conflict_review_preservation_count"]
    )
    assert metrics["strict_ideal_gap_count"] == (
        metrics["useful_final_gap_count"] + metrics["conflict_review_gap_count"]
    )
```

- [ ] **Step 2: Run the new test and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_write_governance_counts.py::test_write_governance_report_exposes_gap_to_strict_ideal -q -p no:cacheprovider
```

Expected before implementation: FAIL with missing metric key.

- [ ] **Step 3: Implement the metrics**

In `_metrics()` in `memory2/eval_write_governance_counts.py`, add:

```python
    useful_final_gap_count = useful_candidates - useful_final_written
    hard_useful_final_gap_count = len(hard_useful_records) - hard_useful_final_written
    conflict_review_gap_count = len(conflict_records) - conflict_final_review
```

Then add these keys to the returned metrics dict:

```python
        "useful_final_gap_count": useful_final_gap_count,
        "hard_useful_final_gap_count": hard_useful_final_gap_count,
        "conflict_review_gap_count": conflict_review_gap_count,
        "strict_ideal_gap_count": useful_final_gap_count + conflict_review_gap_count,
```

- [ ] **Step 4: Add Markdown rows for gap metrics**

In `write_write_governance_count_markdown()` in `memory2/eval_write_governance_counts.py`, after:

```python
        f"| hard 重复泄漏率 | {report.metrics['duplicate_hard_leakage_rate']}% |",
```

add:

```python
        f"| 有用候选最终缺口 | {report.metrics['useful_final_gap_count']} |",
        f"| hard 有用候选最终缺口 | {report.metrics['hard_useful_final_gap_count']} |",
        f"| 冲突复核缺口 | {report.metrics['conflict_review_gap_count']} |",
        f"| 严格理想差距总数 | {report.metrics['strict_ideal_gap_count']} |",
```

- [ ] **Step 5: Update CLI Markdown assertions**

In `tests/test_memory_write_governance_counts_cli.py`, add:

```python
    assert "有用候选最终缺口" in markdown
    assert "hard 有用候选最终缺口" in markdown
    assert "冲突复核缺口" in markdown
    assert "严格理想差距总数" in markdown
```

- [ ] **Step 6: Run the new test and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_write_governance_counts.py::test_write_governance_report_exposes_gap_to_strict_ideal -q -p no:cacheprovider
```

Expected: `1 passed`.

---

### Task 4: Regenerate Report And Enforce Stricter Offline Gates

**Files:**
- Modify generated: `my_md/memory_optimization/eval_reports/memory_write_governance_counts_eval.json`
- Modify generated: `my_md/memory_optimization/eval_reports/memory_write_governance_counts_eval.md`
- Modify: `tests/test_memory_write_governance_counts.py`
- Modify: `tests/test_memory_write_governance_counts_cli.py`

**Interfaces:**
- Keeps report path unchanged:
  - `my_md/memory_optimization/eval_reports/memory_write_governance_counts_eval.json`
  - `my_md/memory_optimization/eval_reports/memory_write_governance_counts_eval.md`

- [ ] **Step 1: Tighten aggregate metric tests**

In `test_write_governance_report_includes_review_resolution_metrics()`, keep existing assertions and add:

```python
    assert metrics["useful_final_retention_rate"] >= 95.0
    assert metrics["hard_useful_final_retention_rate"] >= 95.0
    assert metrics["final_pollution_control_rate"] >= 98.0
    assert metrics["conflict_review_preservation_rate"] >= 99.0
    assert metrics["duplicate_hard_leakage_rate"] == 0.0
```

- [ ] **Step 2: Update CLI report assertions**

In `tests/test_memory_write_governance_counts_cli.py`, add:

```python
    assert payload["metrics"]["useful_final_retention_rate"] >= 95.0
    assert payload["metrics"]["hard_useful_final_retention_rate"] >= 95.0
    assert payload["metrics"]["final_pollution_control_rate"] >= 98.0
    assert payload["metrics"]["conflict_review_preservation_rate"] >= 99.0
    assert payload["metrics"]["duplicate_hard_leakage_rate"] == 0.0
```

- [ ] **Step 3: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_write_governance_counts.py tests/test_memory_write_governance_counts_cli.py tests/test_memory_experiments_runner.py tests/test_memory_eval_runner.py -q -p no:cacheprovider
```

Expected: all tests pass.

- [ ] **Step 4: Regenerate formal report**

Run:

```bash
.venv/bin/python scripts/run_memory_write_governance_counts_eval.py --out-dir my_md/memory_optimization/eval_reports
```

Expected stdout includes:

```text
my_md/memory_optimization/eval_reports/memory_write_governance_counts_eval.json
my_md/memory_optimization/eval_reports/memory_write_governance_counts_eval.md
```

- [ ] **Step 5: Run strict metric gate**

Run:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("my_md/memory_optimization/eval_reports/memory_write_governance_counts_eval.json").read_text(encoding="utf-8"))
metrics = payload["metrics"]
assert metrics["useful_final_retention_rate"] >= 95.0, metrics
assert metrics["hard_useful_final_retention_rate"] >= 95.0, metrics
assert metrics["final_pollution_control_rate"] >= 98.0, metrics
assert metrics["conflict_review_preservation_rate"] >= 99.0, metrics
assert metrics["duplicate_hard_leakage_rate"] == 0.0, metrics
print("hard useful recovery metric gate passed")
print(json.dumps({
    "useful_final_retention_rate": metrics["useful_final_retention_rate"],
    "hard_useful_final_retention_rate": metrics["hard_useful_final_retention_rate"],
    "final_pollution_control_rate": metrics["final_pollution_control_rate"],
    "conflict_review_preservation_rate": metrics["conflict_review_preservation_rate"],
    "duplicate_hard_leakage_rate": metrics["duplicate_hard_leakage_rate"],
    "useful_final_gap_count": metrics["useful_final_gap_count"],
    "hard_useful_final_gap_count": metrics["hard_useful_final_gap_count"],
    "conflict_review_gap_count": metrics["conflict_review_gap_count"],
    "strict_ideal_gap_count": metrics["strict_ideal_gap_count"],
}, ensure_ascii=False, indent=2))
PY
```

Expected: gate passes. If `strict_ideal_gap_count` is not `0`, inspect whether the remaining gap is useful retention or conflict preservation before changing gates.

---

### Task 5: Update Documentation With Before/After Results

**Files:**
- Modify: `my_md/memory_optimization/07-memory-write-governance-count-eval.md`
- Modify: `my_md/memory_optimization/README.md`
- Modify: `progress.md`
- Modify: `task_plan.md`

**Interfaces:**
- Documents exact before/after count and percentage changes.

- [ ] **Step 1: Update the write-governance document**

In `my_md/memory_optimization/07-memory-write-governance-count-eval.md`, update the “距离理想状态的差距” section with the new generated values. Use this structure:

```markdown
## hard 有用候选恢复调优结果

本轮修复的是 temporary marker 的误伤，不是降低 allow 阈值。修复前，`除非用户临时改口` 被 broad `"临时"` marker 当成临时状态；`不要记录来源` 被 broad `"不要记"` marker 当成不要记忆。修复后，这两类表达分别回到长期规则例外条件和冲突复核路径。

| 指标 | 修复前 | 修复后 | 变化 |
| --- | ---: | ---: | ---: |
| 有用候选最终保留率 | `87.5%` | `100.0%` | `+12.5` 个百分点 |
| hard 有用候选最终保留率 | `75.0%` | `100.0%` | `+25.0` 个百分点 |
| 冲突复核保持率 | `98.0%` | `100.0%` | `+2.0` 个百分点 |
| 最终污染控制率 | `100.0%` | `100.0%` | `0.0` 个百分点 |
| hard 重复泄漏率 | `0.0%` | `0.0%` | `0.0` 个百分点 |

数量口径：

- 有用候选最终缺口从 `50/400` 降到 `0/400`。
- hard 有用候选最终缺口从 `50/200` 降到 `0/200`。
- 冲突复核缺口从 `4/200` 降到 `0/200`。
- strict ideal gap 从 `54` 降到 `0`。
```

If the regenerated JSON report does not match these values, stop and inspect the remaining gap before updating documentation. Do not write optimistic values that the report does not prove.

- [ ] **Step 2: Update README summary**

In `my_md/memory_optimization/README.md`, update the Phase 6n paragraph to include the new hard useful recovery result and the remaining gap, if any.

- [ ] **Step 3: Update progress ledger**

Append a `2026-07-21 Memory Hard Useful Recovery Tuning` section to `progress.md` with:

- root cause;
- files changed;
- before/after metrics;
- metric gate result;
- test commands and outputs.

- [ ] **Step 4: Update task plan ledger**

Append a matching section to `task_plan.md` with:

- goal;
- completed task list;
- before/after metrics;
- verification commands;
- explicit note that this remains offline shadow evaluation only.

---

### Task 6: Final Verification And Commit

**Files:**
- Stage only files changed by this plan.

**Interfaces:**
- Produces the final implementation commit. The full plan may also produce the earlier documentation baseline commit from Task 0. Does not push.

- [ ] **Step 1: Run final focused verification**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_write_governance_counts.py tests/test_memory_write_governance_counts_cli.py tests/test_post_response_memory_experiments.py tests/test_memory_experiments_runner.py tests/test_memory_eval_runner.py -q -p no:cacheprovider
```

Expected: all tests pass.

- [ ] **Step 2: Run compileall**

Run:

```bash
.venv/bin/python -m compileall plugins/default_memory/experiments.py memory2/write_governance_review.py memory2/eval_write_governance_counts.py tests/test_memory_write_governance_counts.py tests/test_memory_write_governance_counts_cli.py -q
```

Expected: exit `0`.

- [ ] **Step 3: Run diff checks**

Run:

```bash
git diff --check
git diff --cached --check
```

Expected: both exit `0`.

- [ ] **Step 4: Inspect status**

Run:

```bash
git status --short
```

Expected: only intended files are modified plus untracked `.superpowers/sdd/*.diff` review artifacts. Do not stage `.superpowers/sdd/*.diff`.

- [ ] **Step 5: Stage intended files**

Run:

```bash
git add plugins/default_memory/experiments.py memory2/eval_write_governance_counts.py tests/test_memory_write_governance_counts.py tests/test_memory_write_governance_counts_cli.py my_md/memory_optimization/eval_reports/memory_write_governance_counts_eval.json my_md/memory_optimization/eval_reports/memory_write_governance_counts_eval.md my_md/memory_optimization/07-memory-write-governance-count-eval.md my_md/memory_optimization/README.md progress.md task_plan.md
```

Also stage the reviewed implementation plan:

```bash
git add -f docs/superpowers/plans/2026-07-21-memory-hard-useful-recovery-tuning.md
```

- [ ] **Step 6: Re-run cached diff check**

Run:

```bash
git diff --cached --check
```

Expected: exit `0`.

- [ ] **Step 7: Commit**

Run:

```bash
git commit -m "fix: recover hard useful memory writes"
```

Expected: commit succeeds. Do not push.
