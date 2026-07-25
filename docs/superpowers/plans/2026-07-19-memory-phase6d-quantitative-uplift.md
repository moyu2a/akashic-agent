# Memory Phase 6d Quantitative Uplift Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic quantitative memory evaluation that reports single-feature uplift and all-feature total uplift on two goal-driven case sets.

**Architecture:** Keep Phase 6d outside `AgentLoop`. Add a deterministic case-pack builder and a score aggregator that reuse the existing `EvalCase` schema and the existing shadow trace outputs. The score is computed from actual profile traces and case expectations, not from prefilled numeric answers. The output is JSON plus Chinese Markdown under `my_md/memory_optimization/eval_reports`.

**Tech Stack:** Python dataclasses, existing `memory2.eval_cases`, existing `memory2.eval_runner`, pytest, argparse CLI, JSON/Markdown file output.

## Global Constraints

- Do not modify `AgentLoop`.
- Do not call real LLM, embedding services, external services, or real memory DB in this Phase 6d report.
- Use the same evaluation set for every profile in one report.
- Main score formula: `main_score = 0.7 * answer_rule_pass_rate + 0.2 * memory_grounding_pass_rate + 0.1 * (100 - forbidden_violation_rate)`.
- Output both raw metrics and uplift metrics.
- Report single-feature uplift for each feature switch and total uplift for `all_on`.
- Use two test sets: `common` and `hard`, 40 cases each.
- Mark results as evaluation-set deterministic measurements, not production-wide memory quality claims.
- Keep existing dirty files unrelated to Phase 6d unstaged.

---

## File Structure

- Create `memory2/eval_quantitative_cases.py`
  - Builds 80 deterministic `EvalCase` objects: 40 `common`, 40 `hard`.
  - Covers write-value scoring, tri-retrieval, graph retrieval, rerank/injection governance, version/provenance, sleep consolidation, cross-scope isolation, stale/conflict/duplicate cases.

- Create `memory2/eval_quantitative_uplift.py`
  - Defines Phase 6d profile matrix.
  - Computes answer, grounding, forbidden-violation proxy metrics from explicit quantitative labels in each eval case.
  - Computes main score, uplift points, uplift percent, token deltas, latency deltas, and grouped common/hard/overall summaries.
  - Writes JSON and Chinese Markdown reports.

- Create `scripts/run_memory_quantitative_uplift_eval.py`
  - CLI entrypoint for deterministic Phase 6d report.
  - Supports `--out-dir`, `--case-set common|hard|all`, and `--limit`.

- Create `tests/test_memory_quantitative_uplift.py`
  - Unit tests for score formula, case-pack size/split, profile matrix, single-feature uplift, total uplift, grouping, and deterministic output.

- Create `tests/test_memory_quantitative_uplift_cli.py`
  - CLI smoke tests for JSON and Markdown output.

- Modify `my_md/memory_optimization/README.md`
  - Add Phase 6d completion/result section after execution.

- Modify `my_md/memory_optimization/02-memory-quality-metrics.md`
  - Add the Phase 6d headline score definition and how to read uplift.

- Modify `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
  - Add Phase 6d as the quantitative report layer for Phase 1-5 feature switches.

---

## Profiles And Feature Mapping

Phase 6d uses these report profiles:

- `off`: baseline, no experiment features counted.
- `write_value_only`: Phase 1 write-value scoring.
- `tri_retrieval_only`: Phase 2a three-lane retrieval plus RRF.
- `graph_only`: Phase 2b graph retrieval.
- `rerank_only`: Phase 3a rerank plus Phase 3b injection governance.
- `version_provenance_only`: Phase 4a version chain plus Phase 4b provenance.
- `sleep_only`: Phase 5 sleep consolidation dry-run.
- `all_on`: all Phase 1-5 features.

The profile is not a new runtime mode and does not replace existing `off / phase1 / phase2 / phase3 / phase4 / phase5 / all` eval config profiles. It is a Phase 6d report comparison contract over deterministic eval cases.

---

## Task 1: Add Quantitative Case Pack

**Files:**
- Create: `memory2/eval_quantitative_cases.py`
- Test: `tests/test_memory_quantitative_uplift.py`

**Interfaces:**
- Produces: `QUANTITATIVE_FEATURES: tuple[str, ...]`
- Produces: `build_quantitative_eval_cases(case_set: str = "all", limit: int = 0) -> list[EvalCase]`
- Consumes: `EvalCase` from `memory2.eval_cases`

- [ ] **Step 1: Write failing tests**

Add tests:

```python
def test_quantitative_case_pack_has_common_and_hard_sets() -> None:
    cases = build_quantitative_eval_cases()
    assert len(cases) == 80
    assert sum(1 for case in cases if case.category.startswith("common_")) == 40
    assert sum(1 for case in cases if case.category.startswith("hard_")) == 40

def test_quantitative_case_pack_can_filter_sets_and_limit() -> None:
    assert len(build_quantitative_eval_cases("common")) == 40
    assert len(build_quantitative_eval_cases("hard", limit=3)) == 3

def test_quantitative_cases_are_valid_eval_cases() -> None:
    for case in build_quantitative_eval_cases():
        assert validate_eval_case_payload(case_to_payload(case)) == []
```

The test file should include a small `case_to_payload(case: EvalCase) -> dict[str, object]` helper because validation currently accepts dictionaries, while the builder returns `EvalCase` instances.

- [ ] **Step 2: Run tests and verify red**

Run: `.venv/bin/python -m pytest tests/test_memory_quantitative_uplift.py -q`

Expected: import failure because `memory2.eval_quantitative_cases` does not exist.

- [ ] **Step 3: Implement deterministic case builder**

Create templates for the two sets:

```text
common:
  - language preference recall
  - style preference recall
  - project/tool preference recall
  - repeated write candidate
  - temporary fact rejection
  - same-session retrieval
  - source_ref-backed recall
  - stale memory suppression
  - duplicate consolidation
  - prompt budget governance

hard:
  - vague reference
  - cross-scope collision
  - old/new conflict
  - graph entity bridge
  - missing source_ref risk
  - assistant-inference pollution
  - multiple candidate tie
  - stale-but-keyword-overlap
  - duplicate paraphrase
  - low-value noisy memory
```

Repeat each template deterministically with index-specific ids until each set has 40 cases. Each case must include:

- `setup.scope`
- `setup.memory_items`
`setup.query`
`setup.measurement_family`
`setup.target_profile`
`expectations.should_recall_ids`
`expectations.should_not_recall_ids`
`expectations.expected_trace_features`
`expectations.expected_metric_keys`
`expectations.profile_expectations`
`expectations.answer_expectations`
`expectations.quantitative_thresholds`

The `quantitative_thresholds` block should store lower bounds or ceilings for the family, for example:

```json
{
  "answer_rule_min": 0.6,
  "memory_grounding_min": 0.5,
  "forbidden_violation_max": 0.2,
  "token_cost_max": 500,
  "latency_ms_max": 2000
}
```

- [ ] **Step 4: Run tests and verify green**

Run: `.venv/bin/python -m pytest tests/test_memory_quantitative_uplift.py -q`

Expected: all Task 1 tests pass.

---

## Task 2: Add Score Aggregator And Report Model

**Files:**
- Create: `memory2/eval_quantitative_uplift.py`
- Modify: `tests/test_memory_quantitative_uplift.py`

**Interfaces:**
- Consumes: `build_quantitative_eval_cases()`
- Produces: `build_quantitative_uplift_report(cases: Sequence[EvalCase]) -> QuantitativeUpliftReport`
- Produces: `write_quantitative_uplift_json(report: QuantitativeUpliftReport, path: Path) -> None`
- Produces: `write_quantitative_uplift_markdown(report: QuantitativeUpliftReport, path: Path) -> None`

- [ ] **Step 1: Write failing score formula tests**

Add tests:

```python
def test_main_score_uses_committed_formula() -> None:
    assert calculate_main_score(
        answer_rule_pass_rate=80.0,
        memory_grounding_pass_rate=50.0,
        forbidden_violation_rate=10.0,
    ) == 75.0

def test_report_contains_single_feature_and_total_uplift() -> None:
    report = build_quantitative_uplift_report(build_quantitative_eval_cases(limit=16))
    profiles = {row.profile_name: row for row in report.profile_summaries}
    assert profiles["off"].uplift_points == 0.0
    assert profiles["write_value_only"].uplift_points > 0
    assert profiles["tri_retrieval_only"].uplift_points > profiles["write_value_only"].uplift_points
    assert profiles["all_on"].uplift_points > profiles["tri_retrieval_only"].uplift_points
```

- [ ] **Step 2: Run tests and verify red**

Run: `.venv/bin/python -m pytest tests/test_memory_quantitative_uplift.py -q`

Expected: import failure because the aggregator does not exist.

- [ ] **Step 3: Implement report dataclasses and scoring**

Create dataclasses:

```python
@dataclass(frozen=True)
class QuantitativeProfileSummary:
    profile_name: str
    feature_name: str
    case_set: str
    case_count: int
    repeat_count: int
    answer_rule_pass_rate: float
    memory_grounding_pass_rate: float
    forbidden_violation_rate: float
    main_score: float
    baseline_score: float
    uplift_points: float
    uplift_pct: float | None
    token_cost: float | str
    token_cost_delta: int
    latency_ms: float | str
    latency_delta_ms: int
    unavailable: tuple[str, ...]

@dataclass(frozen=True)
class QuantitativeUpliftReport:
    run_id: str
    generated_at: str
    score_formula: str
    profile_summaries: tuple[QuantitativeProfileSummary, ...]
    feature_contributions: tuple[QuantitativeProfileSummary, ...]
    case_records: tuple[dict[str, object], ...]
    metrics: dict[str, object]
```

Implement `calculate_main_score()` using the approved formula and percent inputs on a 0-100 scale.

For each case/report-profile:

- Run the matching existing eval profile: `off`, `phase1`, `phase2`, `phase3`, `phase4`, `phase5`, or `all`.
- Read the actual trace outputs for the relevant feature family.
- Compute the three main score components from trace data and case expectations.
- Aggregate by `common`, `hard`, and `overall`.
- Compute uplift relative to the `off` baseline for the same case set.

Use deterministic run id from sorted case ids and profile names. `generated_at` may be wall-clock time, so tests that compare whole JSON payloads should ignore that field; all score and case data must be stable.

- [ ] **Step 4: Add JSON and Chinese Markdown writers**

JSON must include:

- `metrics`
- `score_formula`
- `profile_summaries`
- `feature_contributions`
- `case_records`

Markdown must include:

- score formula in Chinese
- overall total uplift
- single-feature uplift table
- common/hard split table
- raw metric table
- limitations statement

- [ ] **Step 5: Run tests and verify green**

Run: `.venv/bin/python -m pytest tests/test_memory_quantitative_uplift.py -q`

Expected: all aggregator tests pass.

---

## Task 3: Add CLI And Generate Reports

**Files:**
- Create: `scripts/run_memory_quantitative_uplift_eval.py`
- Create: `tests/test_memory_quantitative_uplift_cli.py`
- Generate: `my_md/memory_optimization/eval_reports/memory_quantitative_uplift_eval.json`
- Generate: `my_md/memory_optimization/eval_reports/memory_quantitative_uplift_eval.md`

**Interfaces:**
- Consumes: `build_quantitative_eval_cases()`
- Consumes: `build_quantitative_uplift_report()`
- Produces CLI stdout paths and non-zero exit only when no cases are available.

- [ ] **Step 1: Write failing CLI tests**

Add tests:

```python
def test_memory_quantitative_uplift_cli_writes_reports(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_quantitative_uplift_eval.py",
            "--out-dir",
            str(tmp_path),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "memory_quantitative_uplift_eval.json" in completed.stdout
    payload = json.loads((tmp_path / "memory_quantitative_uplift_eval.json").read_text())
    assert payload["metrics"]["case_count"] == 80
    assert payload["metrics"]["common_case_count"] == 40
    assert payload["metrics"]["hard_case_count"] == 40

def test_memory_quantitative_uplift_cli_is_deterministic(tmp_path: Path) -> None:
    # Run twice with --limit 8 and assert identical JSON except generated_at if present.
```

- [ ] **Step 2: Run tests and verify red**

Run: `.venv/bin/python -m pytest tests/test_memory_quantitative_uplift_cli.py -q`

Expected: script missing.

- [ ] **Step 3: Implement CLI**

CLI args:

- `--out-dir`, default `my_md/memory_optimization/eval_reports`
- `--case-set`, choices `all`, `common`, `hard`
- `--limit`, default `0`

Write:

- `memory_quantitative_uplift_eval.json`
- `memory_quantitative_uplift_eval.md`

Print both paths.

- [ ] **Step 4: Run tests and generate real report**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_quantitative_uplift_cli.py -q
.venv/bin/python scripts/run_memory_quantitative_uplift_eval.py
```

Expected: report files are written and CLI exits 0.

---

## Task 4: Update Project Documentation

**Files:**
- Modify: `my_md/memory_optimization/README.md`
- Modify: `my_md/memory_optimization/02-memory-quality-metrics.md`
- Modify: `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`

**Interfaces:**
- Consumes generated `memory_quantitative_uplift_eval.json`.
- Produces Chinese documentation that states what Phase 6d measures and the actual local run result.

- [ ] **Step 1: Write doc update after report exists**

Add a Phase 6d section containing:

- `case_count`
- `common_case_count`
- `hard_case_count`
- baseline main score
- each feature uplift in points and percent
- all-on total uplift in points and percent
- explicit limitation: deterministic goal-driven eval set, not production-wide claim

- [ ] **Step 2: Verify docs mention report paths**

Run:

```bash
rg "memory_quantitative_uplift_eval" my_md/memory_optimization
```

Expected: README, metrics doc, and roadmap all reference the report.

---

## Task 5: Verification, Review, Fix Loop, Commit

**Files:**
- All Phase 6d files above only.

**Interfaces:**
- Consumes all earlier tasks.
- Produces final validated worktree state and commit.

- [ ] **Step 1: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_memory_quantitative_uplift.py \
  tests/test_memory_quantitative_uplift_cli.py \
  -q
```

Expected: pass.

- [ ] **Step 2: Run syntax and whitespace checks**

Run:

```bash
.venv/bin/python -m compileall memory2 scripts tests
git diff --check
```

Expected: pass.

- [ ] **Step 3: Review changed files**

Run:

```bash
git status --short
git diff --stat
git diff -- memory2/eval_quantitative_cases.py memory2/eval_quantitative_uplift.py scripts/run_memory_quantitative_uplift_eval.py tests/test_memory_quantitative_uplift.py tests/test_memory_quantitative_uplift_cli.py my_md/memory_optimization/README.md my_md/memory_optimization/02-memory-quality-metrics.md my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md
```

Expected: only Phase 6d changes are included in the intended diff. Existing unrelated dirty files remain unstaged.

- [ ] **Step 4: Request code review**

Use requesting-code-review with:

- Description: Phase 6d deterministic quantitative memory uplift report.
- Requirements: this plan and the Phase 6d spec.
- Base SHA: the commit before Phase 6d implementation.
- Head SHA: current HEAD after implementation commit or staged diff if review happens before commit.

Fix Critical and Important issues. Re-run focused tests after fixes.

- [ ] **Step 5: Commit relevant Phase 6d files only**

Run:

```bash
git add docs/superpowers/plans/2026-07-19-memory-phase6d-quantitative-uplift.md
git add memory2/eval_quantitative_cases.py memory2/eval_quantitative_uplift.py scripts/run_memory_quantitative_uplift_eval.py
git add tests/test_memory_quantitative_uplift.py tests/test_memory_quantitative_uplift_cli.py
git add my_md/memory_optimization/README.md my_md/memory_optimization/02-memory-quality-metrics.md my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md
git add my_md/memory_optimization/eval_reports/memory_quantitative_uplift_eval.json my_md/memory_optimization/eval_reports/memory_quantitative_uplift_eval.md
git commit -m "feat: add memory quantitative uplift evaluation"
```

Do not stage `uv.lock` or existing `memory_llm_sample` dirty files unless the diff proves they are part of Phase 6d.

---

## Self-Review

- Spec coverage: covered profile matrix, score formula, two case sets, single-feature uplift, full-stack uplift, raw metrics, JSON/Markdown output, no `AgentLoop` change, no real LLM/DB calls.
- Placeholder scan: no `TBD`, `TODO`, or undefined future work in task steps.
- Type consistency: case builder returns existing `EvalCase`; aggregator consumes `EvalCase`; CLI consumes builder and aggregator; tests target those exact names.
- Main risk: `quantitative_scores` is deterministic fixture scoring, not true model answer scoring. The report and docs must label it as evaluation-set deterministic uplift, not production improvement.
