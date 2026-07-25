# Memory Answer Quality Online Uplift Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an answer-quality online uplift report that compares original memory baseline against retrieval enhancement profiles using real AgentLoop answer traces, with counts and percentages for answer correctness, memory grounding, forbidden/noise violations, token cost, and latency.

**Architecture:** Reuse `memory2.eval_comprehensive_online` and `scripts/run_memory_comprehensive_online_eval.py` instead of creating a new AgentLoop runner. Add a profile-uplift table layer on top of the existing comprehensive online report so the same checkpoint can produce interview-friendly tables: single profile vs original memory baseline, and cumulative answer/retrieval chain vs original memory baseline. Define a dedicated answer/retrieval profile set for this report instead of reusing the full `COMPREHENSIVE_CHAIN_PROFILES`, because the default project chain also contains `chain_write_value`, `chain_sleep_consolidation`, and `chain_off`.

**Tech Stack:** Python dataclasses and dictionaries, existing comprehensive online evaluator, existing checkpoint JSONL format, Markdown/JSON report writers, pytest, optional real LLM through the existing config-gated provider path.

## Global Constraints

- Baseline means original memory behavior: `chain_memory_base`.
- `chain_off` is only a disabled-memory control row, not the main baseline.
- This plan measures answer/retrieval quality only.
- Do not include write governance or sleep consolidation as measured modules in the answer-quality uplift table.
- Do not include `chain_write_value` in the answer-quality uplift table. It is a write-side治理模块 and should be measured by write-governance reports.
- Do not include `chain_sleep_consolidation` in the answer-quality uplift table. It is a memory-library hygiene module and should be measured by sleep-hygiene reports.
- `chain_all_on` may appear only as a组合校验行, and its interpretation must say that it includes non-answer modules, so it is not a pure answer/retrieval single-module gain.
- Do not change production `AgentLoop`, `Reasoner`, `ToolExecutor`, `ToolRegistry`, memory writes, or observe DB writes.
- Real LLM execution must stay behind `--enable-real-llm`; fake-provider and checkpoint-report-only paths must remain available.
- Report raw counts first, then percentages. Do not hide low denominators behind score-only output.
- Higher-is-better metrics: answer pass rate and memory grounding pass rate.
- Lower-is-better metrics: forbidden violation rate.
- Cost observation metrics: average total tokens and average latency. These are reported as overhead/reduction relative to `chain_memory_base`, but they must not be mixed into answer quality improvement claims.
- Relative uplift must be computed against `chain_memory_base` only when the denominator is valid.
- Cost and latency deltas must be reported as deltas/reduction percentages, not as quality gains.
- If a denominator is zero, render `None` in JSON and `N/A` in Markdown.
- Do not claim production natural-traffic accuracy. The result is test-set-driven online/shadow evaluation.
- If checkpoint rows do not contain all required answer/retrieval profiles for the same case set, mark the report as partial and do not present it as a full matrix.
- New report fields must be added inside `_metrics_from_results()`, because that is where `profile_summaries` is built. `_build_comprehensive_report()` only wraps the metrics dict into `ComprehensiveOnlineReport`.
- `_empty_metrics()` must include the same new top-level keys with empty values so gated reports keep a stable schema.

---

## File Structure

- Modify: `memory2/eval_comprehensive_online.py`
  - Add `ANSWER_QUALITY_PROFILES` for this report:
    `chain_memory_base`, `chain_tri_retrieval`, `chain_graph_retrieval`, `chain_rerank_injection`, `chain_version_provenance`, `chain_all_on`.
  - Add online uplift helper functions.
  - Add profile-level uplift rows against `chain_memory_base`.
  - Add chain-adjacent and cumulative uplift rows.
  - Add Markdown tables for answer correctness, grounding, forbidden/noise, token, and latency.
- Modify: `tests/test_memory_comprehensive_online_eval.py`
  - Add unit tests for JSON uplift fields.
  - Add unit tests for Markdown tables and formulas.
  - Add checkpoint rebuild tests so existing real LLM checkpoint can be reused without new model calls.
- Modify: `tests/test_memory_comprehensive_online_cli.py`
  - Add CLI smoke for fake-provider report containing the new uplift tables.
  - Add CLI smoke for checkpoint-report-only preserving the uplift fields.
- Modify: `scripts/run_memory_comprehensive_online_eval.py`
  - Keep current CLI shape. Only wire optional report labels if the report writer needs them.
- Modify: `my_md/memory_optimization/05-memory-target-metric-eval-plan.md`
  - Record that answer quality metrics are produced by the comprehensive online report, not by the offline retrieval count report.
- Modify: `my_md/memory_optimization/06-memory-320-baseline-plus-count-eval.md`
  - Link the offline recall-count result to this online answer-quality follow-up.
- Modify: `my_md/memory_optimization/README.md`
  - Add the new phase summary, commands, and boundary notes after execution.
- Modify: `progress.md` and `task_plan.md`
  - Record the plan execution result, test output, generated report paths, and any known issues.

---

### Task 1: Add Profile Uplift Rows

**Files:**
- Modify: `memory2/eval_comprehensive_online.py`
- Test: `tests/test_memory_comprehensive_online_eval.py`

**Interfaces:**
- Consumes: `report.metrics["profile_summaries"]`
- Produces: `report.metrics["profile_answer_quality_uplift_vs_memory_base"]`
- Produces: `report.metrics["answer_quality_required_profiles"]`
- Produces: `report.metrics["answer_quality_missing_profiles"]`
- Produces: `report.metrics["answer_quality_partial_matrix"]`
- Produces constant: `ANSWER_QUALITY_PROFILES: tuple[str, ...]`
- Produces helper: `_relative_rate_lift(after: float, baseline: float) -> float | None`
- Produces helper: `_relative_reduction(before: float, after: float) -> float | None`

When adding tests, extend the import from `memory2.eval_comprehensive_online` to include `ANSWER_QUALITY_PROFILES`.

- [ ] **Step 1: Write failing test for profile uplift rows**

Add this test to `tests/test_memory_comprehensive_online_eval.py`:

```python
def test_online_report_exposes_answer_quality_uplift_vs_memory_base(
    tmp_path: Path,
) -> None:
    cases = build_quantitative_eval_cases(limit=4, case_pack="comprehensive")
    specs = build_comprehensive_run_specs(
        cases,
        repeats=1,
        prompt_variants=("baseline",),
        profiles=("chain_memory_base", "chain_tri_retrieval", "chain_all_on"),
    )

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            timeout_s=5.0,
            real_llm_enabled=False,
        )
    )

    rows = report.metrics["profile_answer_quality_uplift_vs_memory_base"]
    base = rows["chain_memory_base"]
    tri = rows["chain_tri_retrieval"]

    assert base["baseline_profile"] == "chain_memory_base"
    assert base["is_combo_check_row"] is False
    assert base["answer_pass_relative_lift_percent"] == 0.0
    assert base["grounding_pass_relative_lift_percent"] == 0.0
    assert tri["case_count"] == 4
    assert tri["is_combo_check_row"] is False
    assert "answer_pass_delta_points" in tri
    assert "grounding_pass_delta_points" in tri
    assert "forbidden_violation_reduction_percent" in tri
    assert "avg_total_token_overhead" in tri
    assert "avg_latency_overhead_ms" in tri
    assert report.metrics["answer_quality_required_profiles"] == list(ANSWER_QUALITY_PROFILES)
    assert report.metrics["answer_quality_missing_profiles"] == []
    assert report.metrics["answer_quality_partial_matrix"] is False
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py::test_online_report_exposes_answer_quality_uplift_vs_memory_base -q -p no:cacheprovider
```

Expected: fail because `profile_answer_quality_uplift_vs_memory_base` does not exist.

- [ ] **Step 3: Implement uplift helpers**

Add near `COMPREHENSIVE_CHAIN_PROFILES` in `memory2/eval_comprehensive_online.py`:

```python
ANSWER_QUALITY_PROFILES: tuple[str, ...] = (
    "chain_memory_base",
    "chain_tri_retrieval",
    "chain_graph_retrieval",
    "chain_rerank_injection",
    "chain_version_provenance",
    "chain_all_on",
)
```

Then add near existing metric helpers:

```python
def _relative_rate_lift(after: float, baseline: float) -> float | None:
    if float(baseline) == 0.0:
        return None
    return round(((float(after) - float(baseline)) / float(baseline)) * 100.0, 4)


def _relative_reduction(before: float, after: float) -> float | None:
    if float(before) == 0.0:
        return None
    return round(((float(before) - float(after)) / float(before)) * 100.0, 4)
```

- [ ] **Step 4: Implement profile uplift builder**

Add:

```python
def _build_profile_answer_quality_uplift_rows(
    profile_summaries: dict[str, dict[str, object]],
    *,
    baseline_profile: str = "chain_memory_base",
    profiles: Sequence[str] = ANSWER_QUALITY_PROFILES,
) -> dict[str, dict[str, object]]:
    baseline = profile_summaries.get(baseline_profile)
    if not isinstance(baseline, dict):
        return {}
    rows: dict[str, dict[str, object]] = {}
    base_answer = float(baseline.get("answer_rule_pass_rate") or 0.0)
    base_grounding = float(baseline.get("memory_grounding_pass_rate") or 0.0)
    base_forbidden = float(baseline.get("forbidden_violation_rate") or 0.0)
    base_tokens = float(baseline.get("avg_total_token_count") or 0.0)
    base_latency = float(baseline.get("avg_latency_ms") or 0.0)
    for profile in profiles:
        summary = profile_summaries.get(profile)
        if not isinstance(summary, dict):
            continue
        answer = float(summary.get("answer_rule_pass_rate") or 0.0)
        grounding = float(summary.get("memory_grounding_pass_rate") or 0.0)
        forbidden = float(summary.get("forbidden_violation_rate") or 0.0)
        tokens = float(summary.get("avg_total_token_count") or 0.0)
        latency = float(summary.get("avg_latency_ms") or 0.0)
        rows[profile] = {
            "baseline_profile": baseline_profile,
            "is_combo_check_row": profile == "chain_all_on",
            "case_count": summary.get("case_count", 0),
            "answer_success_count": summary.get("answer_success_count", 0),
            "grounding_success_count": summary.get("grounding_success_count", 0),
            "forbidden_case_count": summary.get("forbidden_case_count", 0),
            "answer_rule_pass_rate": answer,
            "answer_pass_delta_points": round(answer - base_answer, 4),
            "answer_pass_relative_lift_percent": _relative_rate_lift(answer, base_answer),
            "memory_grounding_pass_rate": grounding,
            "grounding_pass_delta_points": round(grounding - base_grounding, 4),
            "grounding_pass_relative_lift_percent": _relative_rate_lift(grounding, base_grounding),
            "forbidden_violation_rate": forbidden,
            "forbidden_violation_delta_points": round(forbidden - base_forbidden, 4),
            "forbidden_violation_reduction_percent": _relative_reduction(base_forbidden, forbidden),
            "avg_total_token_count": tokens,
            "avg_total_token_overhead": round(tokens - base_tokens, 4),
            "avg_total_token_reduction_percent": _relative_reduction(base_tokens, tokens),
            "avg_latency_ms": latency,
            "avg_latency_overhead_ms": round(latency - base_latency, 4),
            "avg_latency_reduction_percent": _relative_reduction(base_latency, latency),
        }
    return rows
```

Wire it inside `_metrics_from_results()` after `profile_summaries` is built:

```python
answer_quality_rows = _build_profile_answer_quality_uplift_rows(profile_summaries)
answer_quality_missing_profiles = [
    profile for profile in ANSWER_QUALITY_PROFILES if profile not in profile_summaries
]
```

Because `_metrics_from_results()` currently returns a dict literal, the implementer should compute `answer_quality_rows` and `answer_quality_missing_profiles` just before the return, then add these keys to the returned dict:

```python
"answer_quality_required_profiles": list(ANSWER_QUALITY_PROFILES),
"answer_quality_missing_profiles": answer_quality_missing_profiles,
"answer_quality_partial_matrix": bool(answer_quality_missing_profiles),
"profile_answer_quality_uplift_vs_memory_base": answer_quality_rows,
```

Also extend `_empty_metrics()`:

```python
"answer_quality_required_profiles": list(ANSWER_QUALITY_PROFILES),
"answer_quality_missing_profiles": list(ANSWER_QUALITY_PROFILES),
"answer_quality_partial_matrix": True,
"profile_answer_quality_uplift_vs_memory_base": {},
"chain_answer_quality_uplift_rows": (),
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py -q -p no:cacheprovider
```

Expected: existing comprehensive online tests pass.

---

### Task 2: Add Chain Adjacent And Cumulative Rows

**Files:**
- Modify: `memory2/eval_comprehensive_online.py`
- Test: `tests/test_memory_comprehensive_online_eval.py`

**Interfaces:**
- Consumes: `ANSWER_QUALITY_PROFILES`
- Consumes: `profile_answer_quality_uplift_vs_memory_base`
- Produces: `report.metrics["chain_answer_quality_uplift_rows"]`

- [ ] **Step 1: Write failing test for chain rows**

Add:

```python
def test_online_report_exposes_chain_answer_quality_rows(tmp_path: Path) -> None:
    cases = build_quantitative_eval_cases(limit=4, case_pack="comprehensive")
    profiles = (
        "chain_memory_base",
        "chain_tri_retrieval",
        "chain_graph_retrieval",
        "chain_rerank_injection",
        "chain_version_provenance",
        "chain_all_on",
    )
    specs = build_comprehensive_run_specs(
        cases,
        repeats=1,
        prompt_variants=("baseline",),
        profiles=profiles,
    )
    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            timeout_s=5.0,
            real_llm_enabled=False,
        )
    )

    rows = report.metrics["chain_answer_quality_uplift_rows"]
    assert [row["profile_name"] for row in rows] == list(profiles)
    assert rows[0]["previous_profile"] is None
    assert rows[1]["previous_profile"] == "chain_memory_base"
    assert "adjacent_answer_pass_delta_points" in rows[1]
    assert "cumulative_answer_pass_relative_lift_percent" in rows[-1]
    assert "cumulative_grounding_pass_relative_lift_percent" in rows[-1]
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py::test_online_report_exposes_chain_answer_quality_rows -q -p no:cacheprovider
```

Expected: fail because `chain_answer_quality_uplift_rows` does not exist.

- [ ] **Step 3: Implement chain row builder**

Add:

```python
def _build_chain_answer_quality_rows(
    profile_summaries: dict[str, dict[str, object]],
    *,
    ordered_profiles: Sequence[str] = ANSWER_QUALITY_PROFILES,
    baseline_profile: str = "chain_memory_base",
) -> tuple[dict[str, object], ...]:
    baseline = profile_summaries.get(baseline_profile)
    if not isinstance(baseline, dict):
        return ()
    rows: list[dict[str, object]] = []
    previous: dict[str, object] | None = None
    previous_profile: str | None = None
    for profile in ordered_profiles:
        current = profile_summaries.get(profile)
        if not isinstance(current, dict):
            continue
        base_answer = float(baseline.get("answer_rule_pass_rate") or 0.0)
        base_grounding = float(baseline.get("memory_grounding_pass_rate") or 0.0)
        current_answer = float(current.get("answer_rule_pass_rate") or 0.0)
        current_grounding = float(current.get("memory_grounding_pass_rate") or 0.0)
        prev_answer = (
            float(previous.get("answer_rule_pass_rate") or 0.0)
            if isinstance(previous, dict)
            else current_answer
        )
        prev_grounding = (
            float(previous.get("memory_grounding_pass_rate") or 0.0)
            if isinstance(previous, dict)
            else current_grounding
        )
        rows.append(
            {
                "profile_name": profile,
                "previous_profile": previous_profile,
                "is_combo_check_row": profile == "chain_all_on",
                "case_count": current.get("case_count", 0),
                "answer_rule_pass_rate": current_answer,
                "adjacent_answer_pass_delta_points": round(current_answer - prev_answer, 4),
                "cumulative_answer_pass_delta_points": round(current_answer - base_answer, 4),
                "cumulative_answer_pass_relative_lift_percent": _relative_rate_lift(current_answer, base_answer),
                "memory_grounding_pass_rate": current_grounding,
                "adjacent_grounding_pass_delta_points": round(current_grounding - prev_grounding, 4),
                "cumulative_grounding_pass_delta_points": round(current_grounding - base_grounding, 4),
                "cumulative_grounding_pass_relative_lift_percent": _relative_rate_lift(current_grounding, base_grounding),
            }
        )
        previous = current
        previous_profile = profile
    return tuple(rows)
```

Wire it inside `_metrics_from_results()`:

```python
answer_quality_chain_rows = _build_chain_answer_quality_rows(profile_summaries)
```

Then include this key in the `_metrics_from_results()` return dict:

```python
"chain_answer_quality_uplift_rows": answer_quality_chain_rows,
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py -q -p no:cacheprovider
```

Expected: all comprehensive online unit tests pass.

---

### Task 3: Render JSON And Markdown Tables

**Files:**
- Modify: `memory2/eval_comprehensive_online.py`
- Test: `tests/test_memory_comprehensive_online_eval.py`
- Test: `tests/test_memory_comprehensive_online_cli.py`

**Interfaces:**
- Consumes: `profile_answer_quality_uplift_vs_memory_base`
- Consumes: `chain_answer_quality_uplift_rows`
- Produces Markdown sections:
  - `## Answer Quality Uplift Vs Original Memory`
  - `## Chain Answer Quality Uplift`
  - `## Cost And Latency Observation`

- [ ] **Step 1: Write failing Markdown test**

Add:

```python
def test_online_markdown_renders_answer_quality_uplift_tables(tmp_path: Path) -> None:
    cases = build_quantitative_eval_cases(limit=2, case_pack="comprehensive")
    specs = build_comprehensive_run_specs(
        cases,
        repeats=1,
        prompt_variants=("baseline",),
        profiles=("chain_memory_base", "chain_tri_retrieval", "chain_all_on"),
    )
    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            timeout_s=5.0,
            real_llm_enabled=False,
        )
    )
    path = tmp_path / "report.md"
    write_comprehensive_online_markdown(report, path)
    markdown = path.read_text(encoding="utf-8")

    assert "## Answer Quality Uplift Vs Original Memory" in markdown
    assert "| profile | cases | answer_pass | answer_rate | answer_lift | grounding_pass | grounding_rate | grounding_lift | forbidden_rate | forbidden_reduction |" in markdown
    assert "## Chain Answer Quality Uplift" in markdown
    assert "| profile | previous | answer_rate | adjacent_answer_delta | cumulative_answer_lift | grounding_rate | adjacent_grounding_delta | cumulative_grounding_lift |" in markdown
    assert "## Cost And Latency Observation" in markdown
    assert "chain_write_value" not in markdown.split("## Answer Quality Uplift Vs Original Memory", 1)[1].split("## Chain Answer Quality Uplift", 1)[0]
    assert "chain_sleep_consolidation" not in markdown.split("## Answer Quality Uplift Vs Original Memory", 1)[1].split("## Chain Answer Quality Uplift", 1)[0]
    assert "combo/check" in markdown
```

- [ ] **Step 2: Run Markdown-focused test and verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py::test_online_markdown_renders_answer_quality_uplift_tables -q -p no:cacheprovider
```

Expected: fail because the sections are missing.

- [ ] **Step 3: Add table rendering helpers**

Add a helper for nullable percent display:

```python
def _fmt_percent(value: object) -> str:
    if value is None:
        return "N/A"
    return _fmt(value)
```

Extend `write_comprehensive_online_markdown()` after the existing profile summary table with the three sections. Use only values already present in `report.metrics`; do not inspect raw case answers.

- [ ] **Step 4: Add CLI smoke assertion**

Update `test_comprehensive_online_cli_fake_provider_writes_report()`:

```python
assert "## Answer Quality Uplift Vs Original Memory" in markdown
assert "## Chain Answer Quality Uplift" in markdown
assert "## Cost And Latency Observation" in markdown
assert "profile_answer_quality_uplift_vs_memory_base" in payload["metrics"]
assert "chain_answer_quality_uplift_rows" in payload["metrics"]
assert payload["metrics"]["answer_quality_partial_matrix"] is False
```

Also update `test_comprehensive_online_cli_gates_real_llm_by_default()`:

```python
assert "profile_answer_quality_uplift_vs_memory_base" in payload["metrics"]
assert "chain_answer_quality_uplift_rows" in payload["metrics"]
assert payload["metrics"]["answer_quality_missing_profiles"] == [
    "chain_memory_base",
    "chain_tri_retrieval",
    "chain_graph_retrieval",
    "chain_rerank_injection",
    "chain_version_provenance",
    "chain_all_on",
]
assert payload["metrics"]["answer_quality_partial_matrix"] is True
```

- [ ] **Step 5: Run report tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py tests/test_memory_comprehensive_online_cli.py -q -p no:cacheprovider
```

Expected: all comprehensive online tests pass.

---

### Task 3.5: Add Formula And Partial-Matrix Tests

**Files:**
- Modify: `tests/test_memory_comprehensive_online_eval.py`
- Modify: `memory2/eval_comprehensive_online.py`

**Interfaces:**
- Consumes: `_checkpoint_result()` test helper.
- Consumes: `build_comprehensive_online_report_from_checkpoint()`.
- Produces tests that make denominator-zero, profile filtering, combo row, and partial matrix behavior executable.

- [ ] **Step 1: Write failing checkpoint formula test**

Add:

```python
def test_answer_quality_uplift_handles_zero_denominators_and_filters_profiles(
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "checkpoint.jsonl"
    rows = [
        (
            "base",
            {
                **_checkpoint_result(
                    case_id="case-base",
                    profile_name="chain_memory_base",
                    passed=False,
                ),
                "answer_rule_passed": False,
                "memory_grounding_passed": False,
                "forbidden_contains_violation_count": 1,
                "total_token_count": 100,
                "latency_ms": 1000,
            },
        ),
        (
            "tri",
            {
                **_checkpoint_result(
                    case_id="case-tri",
                    profile_name="chain_tri_retrieval",
                    passed=True,
                ),
                "answer_rule_passed": True,
                "memory_grounding_passed": True,
                "forbidden_contains_violation_count": 0,
                "total_token_count": 120,
                "latency_ms": 900,
            },
        ),
        (
            "write",
            _checkpoint_result(
                case_id="case-write",
                profile_name="chain_write_value",
                passed=True,
            ),
        ),
    ]
    checkpoint.write_text(
        "\n".join(
            json.dumps({"spec_key": key, "result": result})
            for key, result in rows
        ),
        encoding="utf-8",
    )

    report = build_comprehensive_online_report_from_checkpoint(
        checkpoint,
        real_llm_enabled=True,
    )

    uplift = report.metrics["profile_answer_quality_uplift_vs_memory_base"]
    tri = uplift["chain_tri_retrieval"]
    assert "chain_write_value" not in uplift
    assert tri["answer_pass_relative_lift_percent"] is None
    assert tri["grounding_pass_relative_lift_percent"] is None
    assert tri["answer_pass_delta_points"] == 100.0
    assert tri["grounding_pass_delta_points"] == 100.0
    assert tri["forbidden_violation_reduction_percent"] == 100.0
    assert tri["avg_total_token_overhead"] == 20.0
    assert tri["avg_latency_overhead_ms"] == -100.0
    assert report.metrics["answer_quality_partial_matrix"] is True
    assert "chain_graph_retrieval" in report.metrics["answer_quality_missing_profiles"]
```

- [ ] **Step 2: Run focused formula test and verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py::test_answer_quality_uplift_handles_zero_denominators_and_filters_profiles -q -p no:cacheprovider
```

Expected: fail before implementation.

- [ ] **Step 3: Implement missing fields and formula behavior**

Use the helpers and `_metrics_from_results()` wiring from Tasks 1 and 2. Ensure:

```python
"chain_write_value" not in metrics["profile_answer_quality_uplift_vs_memory_base"]
"chain_sleep_consolidation" not in metrics["profile_answer_quality_uplift_vs_memory_base"]
metrics["answer_quality_partial_matrix"] == bool(metrics["answer_quality_missing_profiles"])
```

- [ ] **Step 4: Run focused formula test**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py::test_answer_quality_uplift_handles_zero_denominators_and_filters_profiles -q -p no:cacheprovider
```

Expected: pass.

---

### Task 4: Generate Fake-Provider Smoke Report

**Files:**
- Generated outside repo: `/tmp/akashic-memory-answer-quality-uplift-fake/`
- Modify docs only after validating output.

**Interfaces:**
- Consumes CLI: `scripts/run_memory_comprehensive_online_eval.py`
- Produces:
  - `/tmp/akashic-memory-answer-quality-uplift-fake/reports/memory_comprehensive_online_eval.json`
  - `/tmp/akashic-memory-answer-quality-uplift-fake/reports/memory_comprehensive_online_eval.md`

- [ ] **Step 1: Run fake-provider smoke**

Run:

```bash
.venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-answer-quality-uplift-fake/workspace \
  --out-dir /tmp/akashic-memory-answer-quality-uplift-fake/reports \
  --fake-provider \
  --case-pack comprehensive \
  --case-set all \
  --limit 40 \
  --profiles chain_memory_base,chain_tri_retrieval,chain_graph_retrieval,chain_rerank_injection,chain_version_provenance,chain_all_on \
  --repeats 1 \
  --prompt-variants baseline \
  --concurrency 4 \
  --real-memory-workspace /tmp/akashic-memory-answer-quality-uplift-fake/empty-real-workspace
```

Expected: exit `0`, JSON/Markdown files are written, `real_llm_enabled = False`, `infra_passed = True`.

- [ ] **Step 2: Inspect key fake-provider metrics**

Run:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/akashic-memory-answer-quality-uplift-fake/reports/memory_comprehensive_online_eval.json")
payload = json.loads(path.read_text(encoding="utf-8"))
metrics = payload["metrics"]
print("case_count", metrics["case_count"])
print("profile_count", metrics["profile_count"])
print("real_llm_enabled", metrics["real_llm_enabled"])
print("infra_passed", metrics["infra_passed"])
print("profiles", sorted(metrics["profile_answer_quality_uplift_vs_memory_base"]))
PY
```

Expected:

```text
case_count 240
profile_count 6
real_llm_enabled False
infra_passed True
profiles [...]
```

- [ ] **Step 3: Decide whether to run real LLM**

If fake-provider output has the expected schema, prepare real LLM run. If schema is wrong, stop and fix report code before spending provider calls.
If fake-provider output includes `chain_write_value` or `chain_sleep_consolidation` in the answer-quality table, stop and fix the profile filter before spending provider calls.

---

### Task 5: Rebuild Existing Real Checkpoint Before New Token Spend

**Files:**
- Read existing checkpoint if present:
  - `/tmp/akashic-memory-phase6k-real/reports/memory_comprehensive_online_eval.checkpoint.jsonl`
- Generated outside repo:
  - `/tmp/akashic-memory-answer-quality-uplift-checkpoint-report/`

**Interfaces:**
- Consumes: existing checkpoint JSONL
- Produces checkpoint-only report with new uplift tables

- [ ] **Step 1: Check checkpoint exists**

Run:

```bash
test -f /tmp/akashic-memory-phase6k-real/reports/memory_comprehensive_online_eval.checkpoint.jsonl
```

Expected: exit `0`. If missing, skip this task and run a small real LLM smoke only after user approval.

- [ ] **Step 2: Rebuild report from checkpoint without new LLM calls**

Run:

```bash
.venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-answer-quality-uplift-checkpoint-report/workspace \
  --out-dir /tmp/akashic-memory-answer-quality-uplift-checkpoint-report/reports \
  --enable-real-llm \
  --checkpoint-jsonl /tmp/akashic-memory-phase6k-real/reports/memory_comprehensive_online_eval.checkpoint.jsonl \
  --checkpoint-report-only \
  --exclude-infra-failures \
  --real-memory-workspace /tmp/akashic-memory-answer-quality-uplift-checkpoint-report/empty-real-workspace
```

Expected: no provider calls; report generated from checkpoint rows.

- [ ] **Step 3: Inspect checkpoint report**

Run:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/akashic-memory-answer-quality-uplift-checkpoint-report/reports/memory_comprehensive_online_eval.json")
payload = json.loads(path.read_text(encoding="utf-8"))
metrics = payload["metrics"]
print("case_count", metrics["case_count"])
print("checkpoint_input_count", metrics["checkpoint_input_count"])
print("excluded_infra_failure_count", metrics["excluded_infra_failure_count"])
print("real_llm_enabled", metrics["real_llm_enabled"])
print("answer_rule_pass_rate", metrics["answer_rule_pass_rate"])
print("memory_grounding_pass_rate", metrics["memory_grounding_pass_rate"])
print("forbidden_violation_rate", metrics["forbidden_violation_rate"])
PY
```

Expected: values match the existing checkpoint boundary. If profile coverage is incomplete, document it as partial and do not call it a full matrix.

- [ ] **Step 4: Check profile coverage before interpreting uplift**

Run:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

path = Path("/tmp/akashic-memory-answer-quality-uplift-checkpoint-report/reports/memory_comprehensive_online_eval.json")
payload = json.loads(path.read_text(encoding="utf-8"))
metrics = payload["metrics"]
required = {
    "chain_memory_base",
    "chain_tri_retrieval",
    "chain_graph_retrieval",
    "chain_rerank_injection",
    "chain_version_provenance",
    "chain_all_on",
}
present = set(metrics.get("profile_summaries", {}))
missing = sorted(required - present)
print("missing_answer_quality_profiles", missing)
PY
```

Expected: `missing_answer_quality_profiles []` for a full answer-quality matrix. If the list is not empty, document the checkpoint rebuild as partial evidence only. The generated JSON must also expose `answer_quality_partial_matrix = true`.

---

### Task 6: Optional Full Real LLM Resume

**Files:**
- Generated outside repo:
  - `/tmp/akashic-memory-answer-quality-uplift-real/`

**Interfaces:**
- Consumes real provider config from existing `config.toml`
- Consumes checkpoint path if continuing a previous run
- Produces real LLM comprehensive answer-quality report

- [ ] **Step 1: Only run after explicit approval**

Use this command only after user approves time/token cost:

```bash
.venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-answer-quality-uplift-real/workspace \
  --out-dir /tmp/akashic-memory-answer-quality-uplift-real/reports \
  --config config.toml \
  --enable-real-llm \
  --case-pack comprehensive \
  --case-set all \
  --profiles chain_memory_base,chain_tri_retrieval,chain_graph_retrieval,chain_rerank_injection,chain_version_provenance,chain_all_on \
  --repeats 1 \
  --prompt-variants baseline \
  --concurrency 2 \
  --checkpoint-jsonl /tmp/akashic-memory-answer-quality-uplift-real/reports/memory_comprehensive_online_eval.checkpoint.jsonl \
  --resume \
  --include-answer-debug \
  --real-memory-workspace /tmp/akashic-memory-answer-quality-uplift-real/empty-real-workspace
```

Expected target scale:

```text
496 cases * 6 profiles * 1 prompt variant * 1 repeat = 2976 model calls
```

This estimate follows the current `comprehensive` case pack shape in `memory2/eval_quantitative_cases.py`: common and hard scenarios both use `variant_count = 8`, producing `496` answer-capable cases for `case-set all`. If the implementation changes the case pack shape, rerun a dry count with `build_comprehensive_run_specs()` before spending real provider calls.

- [ ] **Step 2: Rebuild final report after completion or interruption**

Run:

```bash
.venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-answer-quality-uplift-real/checkpoint-report-workspace \
  --out-dir /tmp/akashic-memory-answer-quality-uplift-real/checkpoint-report \
  --enable-real-llm \
  --checkpoint-jsonl /tmp/akashic-memory-answer-quality-uplift-real/reports/memory_comprehensive_online_eval.checkpoint.jsonl \
  --checkpoint-report-only \
  --exclude-infra-failures \
  --real-memory-workspace /tmp/akashic-memory-answer-quality-uplift-real/empty-real-workspace
```

Expected: report is reproducible from checkpoint and can be resumed if provider fails.

---

### Task 7: Update Documentation With Results

**Files:**
- Modify: `my_md/memory_optimization/05-memory-target-metric-eval-plan.md`
- Modify: `my_md/memory_optimization/06-memory-320-baseline-plus-count-eval.md`
- Modify: `my_md/memory_optimization/README.md`
- Modify: `progress.md`
- Modify: `task_plan.md`

**Interfaces:**
- Consumes generated fake-provider report.
- Consumes checkpoint-only or real LLM report if available.
- Produces documented tables with exact counts and percentages.

- [ ] **Step 1: Add result table format**

Document the answer-quality table with these columns:

```markdown
| profile | cases | answer pass | answer rate | answer lift vs 原始记忆 | grounding pass | grounding rate | grounding lift vs 原始记忆 | forbidden rate | forbidden reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
```

Add a note that `combo/check` marks `chain_all_on`, which is not a pure single-module answer/retrieval gain.

- [ ] **Step 2: Add chain table format**

Document the cumulative chain table with these columns:

```markdown
| step | previous | answer rate | adjacent answer delta | cumulative answer lift | grounding rate | adjacent grounding delta | cumulative grounding lift |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
```

- [ ] **Step 3: Add cost table format**

Document the cost table with these columns:

```markdown
| profile | avg tokens | token overhead vs 原始记忆 | token reduction | avg latency ms | latency overhead ms | latency reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
```

- [ ] **Step 4: Record boundary**

Add this exact boundary:

```markdown
这张表衡量的是测试集驱动的回答层结果：模型看到不同 profile 注入的记忆后，最终回答是否命中规则、是否使用期望记忆、是否出现 forbidden 内容，以及上下文成本变化。它不是生产自然流量准确率，也不评价写入治理或睡眠巩固。`chain_all_on` 是组合校验行，不作为某个单一回答/召回模块的独立增益。
```

---

### Task 8: Final Verification And Commit

**Files:**
- Modify only files listed above.
- Do not stage `.superpowers/sdd/*.diff`.
- Do not stage unrelated dirty `my_md/memory_optimization/08-memory-sleep-hygiene-eval.md` unless this task intentionally updates it.

**Interfaces:**
- Produces one commit for answer-quality online uplift reporting.

- [ ] **Step 1: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py tests/test_memory_comprehensive_online_cli.py -q -p no:cacheprovider
```

Expected: all tests pass.

- [ ] **Step 2: Run diff check**

Run:

```bash
git diff --check
```

Expected: exit `0`.

- [ ] **Step 3: Inspect status**

Run:

```bash
git status --short
```

Expected: only intended implementation/docs/report files are modified, plus pre-existing unrelated files still unstaged.

- [ ] **Step 4: Stage intended files**

Run:

```bash
git add \
  memory2/eval_comprehensive_online.py \
  scripts/run_memory_comprehensive_online_eval.py \
  tests/test_memory_comprehensive_online_eval.py \
  tests/test_memory_comprehensive_online_cli.py \
  my_md/memory_optimization/05-memory-target-metric-eval-plan.md \
  my_md/memory_optimization/06-memory-320-baseline-plus-count-eval.md \
  my_md/memory_optimization/README.md \
  progress.md \
  task_plan.md
```

If `scripts/run_memory_comprehensive_online_eval.py` has no changes, omit it from staging.

- [ ] **Step 5: Commit**

Run:

```bash
git commit -m "feat: add memory answer quality uplift report"
```

Expected: commit succeeds. Do not push.

---

## Self-Review

1. Spec coverage: the plan directly addresses the next gap after offline recall counts: answer correctness, evidence/grounding, forbidden/noise, token cost, and latency. It keeps write governance and sleep hygiene separate.
2. Placeholder scan: no `TBD`, `TODO`, or unspecified “write tests” steps remain. Each test step names a file, function, command, and expected failure/pass condition.
3. Type consistency: helper names used in tasks match the names wired into `_metrics_from_results()`, `_empty_metrics()`, and `write_comprehensive_online_markdown()`.
4. Boundary check: production AgentLoop behavior is not changed; the plan only changes evaluation/report code and documentation.
5. Cost check: real LLM execution is optional and gated. The default execution path is fake-provider plus checkpoint rebuild.
