# Memory Phase 6d Review Fix Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the Phase 6d quantitative uplift report so token-signal semantics are explicit, provenance penalties reflect observed trace risk, and report generation fails fast on eval runner failures.

**Architecture:** Keep the Phase 6d case pack and trace families unchanged. Tighten only the report layer: publish token signals with an explicit kind, stop fabricating non-comparable deltas, gate report emission on `EvalRunReport.passed`, and make provenance penalties depend on actual cross-scope risk counts. Then refresh the JSON/Markdown artifacts and the memory optimization docs from the corrected report.

**Tech Stack:** Python dataclasses, `memory2.eval_runner`, `memory2.eval_quantitative_uplift`, pytest, JSON/Markdown writers, existing memory optimization docs.

## Global Constraints

- Do not modify `AgentLoop`.
- Do not introduce a real LLM call, embedding call, external service call, or real memory DB dependency into the report path.
- Keep the quantitative case pack deterministic and goal-driven.
- Keep existing unrelated dirty files unstaged.
- Preserve the current `my_md/memory_optimization/eval_reports` output location.

---

## File Structure

- Modify `memory2/eval_quantitative_uplift.py`
  - Add explicit token-signal kind metadata and rename the raw field to `token_signal_value`.
  - Remove the misleading delta fallback for non-comparable token values.
  - Fail fast when the underlying eval runner report did not pass.
  - Make `generated_at` deterministic.

- Modify `tests/test_memory_quantitative_uplift.py`
  - Lock the revised token-signal semantics.
  - Lock fail-fast behavior on a failed runner report.
  - Lock the revised provenance penalty logic.
  - Lock deterministic report timestamps.

- Modify `tests/test_memory_quantitative_uplift_cli.py`
  - Keep CLI smoke coverage.
  - Add a failure-path smoke that proves the CLI exits non-zero when report building fails.

- Modify `my_md/memory_optimization/README.md`
  - Replace the old token-cost/uplift wording with the corrected report wording.

- Modify `my_md/memory_optimization/02-memory-quality-metrics.md`
  - Explain the corrected Phase 6d metrics and what `token_signal_kind` means.

- Modify `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
  - Update the Phase 6d milestone text and current numbers after the corrected run.

- Regenerate:
  - `my_md/memory_optimization/eval_reports/memory_quantitative_uplift_eval.json`
  - `my_md/memory_optimization/eval_reports/memory_quantitative_uplift_eval.md`

---

## Task 1: Normalize Token Signal Reporting

**Files:**
- Modify: `memory2/eval_quantitative_uplift.py`
- Modify: `tests/test_memory_quantitative_uplift.py`

**Interfaces:**
- Consumes: `EvalTrace.metrics` from the existing phase families.
- Produces: a `QuantitativeProfileSummary` that carries a `token_signal_kind` field and never pretends an unavailable baseline is a real delta.

- [ ] **Step 1: Add failing tests for token signal semantics**

```python
def test_token_signal_kind_is_explicit() -> None:
    report = build_quantitative_uplift_report(build_quantitative_eval_cases())
    overall = {(row.case_set, row.profile_name): row for row in report.profile_summaries}
    assert overall[("overall", "sleep_only")].token_signal_kind == "estimated_token_saving"
    assert overall[("overall", "rerank_only")].token_signal_kind == "prompt_token_delta"
    assert overall[("overall", "all_on")].token_signal_kind == "mixed"
    assert overall[("overall", "all_on")].token_signal_value == "unavailable"
    assert overall[("overall", "all_on")].token_signal_delta == "unavailable"

def test_non_comparable_token_deltas_do_not_fall_back_to_raw_values() -> None:
    report = build_quantitative_uplift_report(build_quantitative_eval_cases(limit=16))
    overall = {(row.case_set, row.profile_name): row for row in report.profile_summaries}
    assert overall[("overall", "sleep_only")].token_signal_delta == "unavailable"
```

- [ ] **Step 2: Run the tests and confirm the current behavior fails**

Run: `.venv/bin/python -m pytest tests/test_memory_quantitative_uplift.py -q`

Expected: the new assertions fail because the current report still falls back to raw values.

- [ ] **Step 3: Implement explicit token-signal kinds**

Add fields to `QuantitativeProfileSummary`:

```python
token_signal_kind: str
token_signal_value: float | str
token_signal_delta: float | str
```

Set it per family:

```python
# rerank_shadow / injection_governance_shadow
token_signal_kind = "prompt_token_delta"

# sleep_consolidation_shadow
token_signal_kind = "estimated_token_saving"

# all unavailable families
token_signal_kind = "unavailable"
```

Change `_delta_value()` so it only returns a numeric delta when both values are numeric and comparable. Otherwise return `"unavailable"` instead of falling back to the raw profile value.

When a profile aggregates more than one kind of token signal, mark `token_signal_kind = "mixed"` and set `token_signal_value = "unavailable"` instead of summing unlike quantities. That keeps `all_on` honest: it still reports the main score uplift, but it does not fake a single combined token number.

- [ ] **Step 4: Re-run the tests**

Run: `.venv/bin/python -m pytest tests/test_memory_quantitative_uplift.py -q`

Expected: token-signal assertions pass.

---

## Task 2: Fail Fast on Runner Failure

**Files:**
- Modify: `memory2/eval_quantitative_uplift.py`
- Modify: `tests/test_memory_quantitative_uplift.py`
- Modify: `tests/test_memory_quantitative_uplift_cli.py`

**Interfaces:**
- Consumes: `run_eval_cases(cases)` result.
- Produces: a hard failure from `build_quantitative_uplift_report()` when `eval_report.passed` is false.

- [ ] **Step 1: Add failing tests for the failure gate**

```python
def test_report_builder_raises_when_runner_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailedReport:
        passed = False
        cases = ()
        metrics = {"case_count": 1}

    monkeypatch.setattr("memory2.eval_quantitative_uplift.run_eval_cases", lambda cases: FailedReport())

    with pytest.raises(RuntimeError, match="eval runner failed"):
        build_quantitative_uplift_report(build_quantitative_eval_cases(limit=1))
```

- [ ] **Step 2: Run the targeted test and confirm it fails**

Run: `.venv/bin/python -m pytest tests/test_memory_quantitative_uplift.py -q`

Expected: the new failure-gate test fails until the guard is added.

- [ ] **Step 3: Implement the fail-fast guard**

Insert this check immediately after `run_eval_cases(cases)`:

```python
if not eval_report.passed:
    failures = "\n".join(
        f"- {case.case_id}: {', '.join(case.failures) or 'unknown failure'}"
        for case in eval_report.cases
        if not case.passed
    )
    raise RuntimeError(f"eval runner failed before uplift report generation:\n{failures}")
```

Let the CLI inherit the exception so it exits non-zero and emits no polished report files when the runner is broken.

- [ ] **Step 4: Re-run the targeted tests**

Run: `.venv/bin/python -m pytest tests/test_memory_quantitative_uplift.py tests/test_memory_quantitative_uplift_cli.py -q`

Expected: the failure-gate test passes, and the CLI failure-path test confirms non-zero exit behavior.

---

## Task 3: Tighten Provenance Penalty Logic

**Files:**
- Modify: `memory2/eval_quantitative_uplift.py`
- Modify: `tests/test_memory_quantitative_uplift.py`

**Interfaces:**
- Consumes: `cross_scope_memory_count` and `cross_scope_risk_count` from `build_provenance_shadow_result()`.
- Produces: provenance forbidden rates driven by actual risk, not by the mere presence of cross-scope memory items.

- [ ] **Step 1: Add a failing provenance test**

```python
def test_provenance_forbidden_rate_depends_on_actual_risk_not_fixture_presence() -> None:
    report = build_quantitative_uplift_report(build_quantitative_eval_cases())
    overall = {(row.case_set, row.profile_name): row for row in report.profile_summaries}
    assert overall[("hard", "version_provenance_only")].forbidden_violation_rate < 100.0
```

- [ ] **Step 2: Run the test and verify the current blanket penalty**

Run: `.venv/bin/python -m pytest tests/test_memory_quantitative_uplift.py -q`

Expected: the provenance assertion fails because the current code still forces a 100% forbidden rate when cross-scope memory exists.

- [ ] **Step 3: Remove the blanket provenance penalty**

Replace the current hard-coded `max(..., 100%)` logic with:

```python
forbidden = _ratio(cross_scope_risk_count, max(1, cross_scope_memory_count))
```

Keep the metric grounded in the observed `cross_scope_risk_count`. If the trace saw cross-scope memory but did not flag it as risky, the forbidden rate should stay low instead of being inflated by fixture composition.

- [ ] **Step 4: Re-run the provenance test**

Run: `.venv/bin/python -m pytest tests/test_memory_quantitative_uplift.py -q`

Expected: provenance penalty now reflects observed risk only.

---

## Task 4: Refresh Artifacts And Docs

**Files:**
- Modify: `memory2/eval_quantitative_uplift.py`
- Modify: `my_md/memory_optimization/README.md`
- Modify: `my_md/memory_optimization/02-memory-quality-metrics.md`
- Modify: `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
- Regenerate: `my_md/memory_optimization/eval_reports/memory_quantitative_uplift_eval.json`
- Regenerate: `my_md/memory_optimization/eval_reports/memory_quantitative_uplift_eval.md`
- Modify: `tests/test_memory_quantitative_uplift_cli.py`

**Interfaces:**
- Consumes the corrected report model.
- Produces updated local report files and plain Chinese documentation that matches the new semantics.

- [ ] **Step 1: Make the report timestamp deterministic**

Use a fixed UTC timestamp or a deterministic value derived from the report inputs instead of `datetime.now(...)`.

Example:

```python
generated_at=_FIXED_REPORT_TIME.isoformat()
```

This keeps the JSON stable across repeated runs with identical cases.

- [ ] **Step 2: Update docs and report output**

Rewrite the relevant docs so they state:

- `token_signal_value` is a raw family token signal, not a cross-family normalized cost.
- `token_signal_kind` tells the reader whether the number is a prompt token delta or an estimated token saving.
- `token_signal_delta` is unavailable when the baseline is not comparable.
- provenance forbidden rate now depends on observed cross-scope risk.

- [ ] **Step 3: Regenerate the reports and run the verification gates**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_quantitative_uplift.py tests/test_memory_quantitative_uplift_cli.py -q
.venv/bin/python -m compileall memory2 scripts tests
git diff --check
.venv/bin/python scripts/run_memory_quantitative_uplift_eval.py
```

Expected: tests pass, compileall passes, diff check is clean, and both report files are rewritten with the corrected semantics.

- [ ] **Step 4: Commit only the Phase 6d fix files**

Stage and commit the changed Phase 6d report, tests, docs, and generated artifacts only. Leave unrelated dirty files untouched.

---

## Self-Review

- Spec coverage: covered token-signal semantics, fail-fast report generation, provenance penalty correction, deterministic output, regenerated artifacts, and documentation refresh.
- Placeholder scan: no `TODO`, `TBD`, or undefined follow-up language in executable steps.
- Type consistency: the new `token_signal_kind` field is introduced before later steps read it; the fail-fast guard uses `EvalRunReport.passed`, which already exists in `memory2.eval_runner`.
- Main risk: the token-signal renaming must be carried through the JSON/Markdown writers and docs together; otherwise the new terms will be inconsistent.

## Execution Result

- Implemented token-signal fields: `token_signal_kind`, `token_signal_value`, and `token_signal_delta`.
- `all_on` now reports `token_signal_kind = mixed` and leaves `token_signal_value` / `token_signal_delta` as `unavailable` instead of summing prompt token delta with estimated token saving.
- Report generation now raises `RuntimeError` if `run_eval_cases(cases).passed` is false.
- `generated_at` is fixed at `2026-07-17T00:00:00+00:00` for deterministic report output.
- `provenance_shadow` forbidden rate now uses observed `cross_scope_risk_count / cross_scope_memory_count`; it no longer applies a blanket 100% penalty when cross-scope fixture memory exists.
- Corrected report result: `baseline_main_score = 10.0`, `all_on_main_score = 69.6017`, `total_uplift_points = 59.6017`, `total_uplift_pct = 596.017`, `common_main_score = 69.067`, `hard_main_score = 70.1364`.
- Verification passed:
  - `.venv/bin/python -m pytest tests/test_memory_quantitative_uplift.py tests/test_memory_quantitative_uplift_cli.py -q` -> `13 passed`
  - `.venv/bin/python -m compileall memory2 scripts tests -q` -> passed
  - `git diff --check` -> passed
  - `.venv/bin/python -m json.tool my_md/memory_optimization/eval_reports/memory_quantitative_uplift_eval.json` -> passed
- Code review found no Critical issues and one Important test gap. Fixed by adding a non-zero provenance risk ratio assertion (`1 / 3 -> 33.33`) and by asserting CLI failure leaves no JSON/Markdown output files in the requested output directory.
