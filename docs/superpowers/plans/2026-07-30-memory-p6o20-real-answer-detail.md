# Memory P6o-20 Real Answer Detail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a checkpointed real-LLM P6o-20 system-path experiment and preserve complete local scoring data so reviewers can inspect answer pass/fail movement for `safe_version_replace_guided_with_retry_shadow`.

**Architecture:** Reuse the existing P6o-19 eval mode and gate. Add a report-only detail exporter that consumes `system_path_safe_version_eval.json` and writes per-row scoring JSONL/CSV plus guided-vs-retry-shadow movement JSON/Markdown. Then run a real LLM small matrix with checkpoint and rebuild, gate it, export full scoring details, and document method/data/conclusion.

**Tech Stack:** Python stdlib (`argparse`, `csv`, `json`, `pathlib`), existing `scripts/run_memory_system_path_safe_version_eval.py`, existing `scripts/check_memory_p6o19_gate.py`, pytest, real `AgentLoop.process_direct()` system-path eval harness.

## Global Constraints

- Worktree: `/home/jjh/git_work/akashic-agent/.worktrees/memory-next`.
- Branch: `memory-next`.
- Production default remains `MemoryConfig.safe_version_governed_mode = "off"`.
- No graph-all-on, no recall expansion, no production retry/fallback execution, no production memory write changes, no global system prompt change.
- Real retry remains disabled; `safe_version_replace_guided_with_retry_shadow` only records shadow telemetry.
- Full local scoring data may be recorded for review: case id, category, mode, repeat index, pass/fail fields, scorer counts, sanitized failures, post-check flags/reasons, token counts, latency, safe contract ids/counts, and candidate contract counts.
- Do not record API key, Authorization header, provider request payload, raw prompt, session text, or secret values.
- Raw answer text is not required for this experiment. If future local-only raw answer capture is requested, add an explicit opt-in flag and do not commit it by default.
- Use `.venv/bin/python`, not `uv run`, because `uv run` has failed in this environment with snap-confine permissions.
- Protected untracked directory must not be deleted or overwritten: `my_md/memory_optimization/eval_reports/p6o13_system_path_real_llm_validation_v1/`.

---

## Execution Status

- [x] Plan reviewed by subagent and revised for gate taxonomy, complete scoring export, validation, checkpoint resume, and privacy scan semantics.
- [x] Detail exporter implemented with TDD.
- [x] Fake detail smoke completed.
- [x] Real LLM matrix attempted and completed as `infra_blocked` due `timeout_count = 120`.
- [x] Checkpoint rebuild, gate hard-failure evidence, full detail export, tests, compileall, privacy scan, and documentation completed.

---

## File Structure

- Create `scripts/export_memory_p6o20_answer_details.py`
  - Input: `--report-json path/to/system_path_safe_version_eval.json`.
  - Output directory: `--out-dir`.
  - Writes:
    - `per_case_scoring_rows.jsonl`
    - `per_case_scoring_rows.csv`
    - `case_movement_vs_guided.json`
    - `case_movement_vs_guided.md`
    - `export_summary.json`
  - Performs report-only validation of exact expected modes, equal mode row counts, paired guided/retry rows, forbidden raw keys, and emitted artifact safety.
- Modify `tests/test_memory_system_path_safe_version_eval.py`
  - Add unit/CLI tests for detail export and movement calculation.
  - Keep tests synthetic and local; no real LLM in tests.
- Modify docs after execution:
  - `my_md/memory_optimization/README.md`
  - `progress.md`
  - Create `my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/p6o20_answer_candidate_retry_shadow_real_report.md`

---

### Task 1: Detail Exporter

**Files:**
- Create: `scripts/export_memory_p6o20_answer_details.py`
- Modify: `tests/test_memory_system_path_safe_version_eval.py`

**Interfaces:**
- Produces function:
  - `build_answer_detail_exports(payload: dict[str, Any], *, anchor_mode: str, comparison_mode: str) -> dict[str, Any]`
- Produces CLI:
  - `scripts/export_memory_p6o20_answer_details.py --report-json <json> --out-dir <dir> --anchor-mode safe_version_replace_guided --comparison-mode safe_version_replace_guided_with_retry_shadow`
- Output JSON shape:
  - `case_movement_vs_guided.json`:
    - `anchor_mode: str`
    - `comparison_mode: str`
    - `case_count: int`
    - `paired_case_count: int`
    - `movement_counts: dict[str, int]`
    - `rows: list[dict[str, object]]`
  - `export_summary.json`:
    - `source_report_json: str`
    - `total_rows: int`
    - `expected_modes: list[str]`
    - `mode_row_counts: dict[str, int]`
    - `paired_case_count: int`
    - `unpaired_case_count: int`
    - `movement_counts: dict[str, int]`
    - `forbidden_key_scan_passed: bool`

- [ ] **Step 1: Write failing exporter test**

Add to `tests/test_memory_system_path_safe_version_eval.py`:

```python
def test_p6o20_detail_export_writes_per_case_scoring_and_movement(
    tmp_path: Path,
) -> None:
    report_json = tmp_path / "system_path_safe_version_eval.json"
    out_dir = tmp_path / "details"
    payload = _p6o19_gate_payload(
        replace_answer_rate=50.0,
        guided_answer_rate=0.0,
        retry_shadow_answer_rate=100.0,
    )
    for row in payload["cases"]:
        row["case_id"] = "case-shared"
        row["category"] = "hard"
        row["repeat_index"] = 0
        row["expected_contains_pass_count"] = 1 if row["answer_rule_passed"] else 0
        row["expected_contains_miss_count"] = 0 if row["answer_rule_passed"] else 1
        row["expected_any_pass_count"] = 1 if row["answer_rule_passed"] else 0
        row["expected_any_miss_count"] = 0 if row["answer_rule_passed"] else 1
        row["language_passed"] = True
        row["failures"] = [] if row["answer_rule_passed"] else ["missing_expected_answer_term"]
        row["latency_ms"] = 10
        row["token_count"] = 30
    report_json.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/export_memory_p6o20_answer_details.py",
            "--report-json",
            str(report_json),
            "--out-dir",
            str(out_dir),
            "--anchor-mode",
            "safe_version_replace_guided",
            "--comparison-mode",
            "safe_version_replace_guided_with_retry_shadow",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    rows = [
        json.loads(line)
        for line in (out_dir / "per_case_scoring_rows.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    movement = json.loads(
        (out_dir / "case_movement_vs_guided.json").read_text(encoding="utf-8")
    )
    summary = json.loads((out_dir / "export_summary.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "case_movement_vs_guided.md").read_text(encoding="utf-8")

    assert rows
    assert {
        "case_id",
        "mode",
        "answer_rule_passed",
        "expected_contains_miss_count",
        "expected_any_miss_count",
        "language_passed",
        "failures",
        "post_check_needs_retry",
        "post_check_retry_reasons",
    } <= set(rows[0])
    assert "raw_prompt" not in str(rows)
    assert "raw_answer" not in str(rows)
    assert isinstance(rows[0]["failures"], list)
    assert isinstance(rows[0]["post_check_retry_reasons"], list)
    assert "allowed_evidence_ids" in rows[0]
    assert "version_boundary_replacement_count" in rows[0]
    assert movement["movement_counts"]["anchor_failed_comparison_passed"] == 1
    assert summary["forbidden_key_scan_passed"] is True
    assert summary["paired_case_count"] == 1
    assert "| case_id | category | repeat | anchor_passed | comparison_passed | movement |" in markdown
```

- [ ] **Step 2: Verify exporter test fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_system_path_safe_version_eval.py::test_p6o20_detail_export_writes_per_case_scoring_and_movement -q -p no:cacheprovider
```

Expected: FAIL because `scripts/export_memory_p6o20_answer_details.py` does not exist.

- [ ] **Step 3: Implement exporter**

Reviewer-required implementation refinements:

- Add `answer_length` to the exported scalar fields.
- JSONL must preserve typed list fields for `failures`, `post_check_retry_reasons`, evidence ids, and reason lists. Do not pipe-join lists in JSONL.
- CSV and Markdown may stringify lists with a stable separator.
- Exported rows must include sanitized contract/debug fields already present in the source report: safe-version metadata flags, prompt variant, allowed/likely/downgrade/review/stale/conflict/active/forbidden/deleted ids, version-boundary counts, risk-tier count dictionaries, and answer-candidate contract count fields.
- Exporter validation must fail before writing misleading details when expected modes are missing/extra, mode row counts differ, guided/retry-shadow pairs are missing, or forbidden raw keys appear in the source/emitted rows.
- Forbidden keys for exporter validation: `raw_prompt`, `full_answer`, `raw_answer`, `session_text`, `Authorization`, `api_key`, `current_truth_lines`, `must_include_terms`.
- Exporter must also write `export_summary.json` with source path, total rows, expected modes, mode row counts, paired/unpaired counts, movement counts, and `forbidden_key_scan_passed`.
- The code block below is illustrative; if it conflicts with these refinements, implement the refinements.

Create `scripts/export_memory_p6o20_answer_details.py` with:

```python
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


SCORING_FIELDS = (
    "case_id",
    "case_index",
    "repeat_index",
    "category",
    "mode",
    "passed",
    "answer_rule_passed",
    "memory_grounding_passed",
    "expected_memory_used",
    "forbidden_contains_violation_count",
    "expected_contains_pass_count",
    "expected_contains_miss_count",
    "expected_any_pass_count",
    "expected_any_miss_count",
    "language_passed",
    "failures",
    "provider_error",
    "timeout",
    "latency_ms",
    "token_count",
    "prompt_token_count",
    "completion_token_count",
    "token_metrics_available",
    "replacement_seeded_count",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-json", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--anchor-mode", default="safe_version_replace_guided")
    parser.add_argument(
        "--comparison-mode",
        default="safe_version_replace_guided_with_retry_shadow",
    )
    args = parser.parse_args(argv)

    payload = json.loads(Path(args.report_json).read_text(encoding="utf-8"))
    export = build_answer_detail_exports(
        payload,
        anchor_mode=args.anchor_mode,
        comparison_mode=args.comparison_mode,
    )
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = list(export["per_case_rows"])
    (out_dir / "per_case_scoring_rows.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    with (out_dir / "per_case_scoring_rows.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else list(SCORING_FIELDS))
        writer.writeheader()
        writer.writerows(rows)
    movement = dict(export["movement"])
    (out_dir / "case_movement_vs_guided.json").write_text(
        json.dumps(movement, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / "case_movement_vs_guided.md").write_text(
        render_movement_markdown(movement),
        encoding="utf-8",
    )
    print(out_dir / "per_case_scoring_rows.jsonl")
    print(out_dir / "per_case_scoring_rows.csv")
    print(out_dir / "case_movement_vs_guided.json")
    print(out_dir / "case_movement_vs_guided.md")
    return 0


def build_answer_detail_exports(
    payload: dict[str, Any],
    *,
    anchor_mode: str,
    comparison_mode: str,
) -> dict[str, Any]:
    rows = [_flatten_row(dict(row)) for row in payload.get("cases", [])]
    movement = _build_movement(rows, anchor_mode=anchor_mode, comparison_mode=comparison_mode)
    return {"per_case_rows": rows, "movement": movement}


def _flatten_row(row: dict[str, Any]) -> dict[str, Any]:
    post = dict(row.get("post_check_shadow") or {})
    contract = dict(row.get("safe_version_contract") or {})
    candidate = dict(contract.get("answer_candidate_contract") or {})
    flat = {field: row.get(field) for field in SCORING_FIELDS}
    flat["failures"] = "|".join(str(item) for item in row.get("failures", []) or [])
    flat["post_check_needs_retry"] = bool(post.get("needs_retry"))
    flat["post_check_retry_reasons"] = "|".join(
        str(item) for item in post.get("retry_reasons", []) or []
    )
    flat["post_check_shadow_enabled"] = bool(post.get("shadow_enabled"))
    flat["answer_candidate_contract_enabled"] = bool(candidate.get("enabled"))
    flat["answer_candidate_current_truth_count"] = int(candidate.get("current_truth_count") or 0)
    flat["answer_candidate_must_include_term_count"] = int(candidate.get("must_include_term_count") or 0)
    flat["answer_candidate_forbidden_old_value_count"] = int(candidate.get("forbidden_old_value_count") or 0)
    flat["answer_prompt_variant"] = contract.get("answer_prompt_variant") or ""
    return flat


def _build_movement(
    rows: list[dict[str, Any]],
    *,
    anchor_mode: str,
    comparison_mode: str,
) -> dict[str, Any]:
    by_key: dict[tuple[str, int], dict[str, dict[str, Any]]] = {}
    for row in rows:
        key = (str(row.get("case_id") or ""), int(row.get("repeat_index") or 0))
        by_key.setdefault(key, {})[str(row.get("mode") or "")] = row
    movement_rows: list[dict[str, Any]] = []
    counts = {
        "both_passed": 0,
        "anchor_passed_comparison_failed": 0,
        "anchor_failed_comparison_passed": 0,
        "both_failed": 0,
    }
    for (case_id, repeat_index), modes in sorted(by_key.items()):
        if anchor_mode not in modes or comparison_mode not in modes:
            continue
        anchor = modes[anchor_mode]
        comparison = modes[comparison_mode]
        anchor_passed = bool(anchor.get("answer_rule_passed"))
        comparison_passed = bool(comparison.get("answer_rule_passed"))
        if anchor_passed and comparison_passed:
            movement = "both_passed"
        elif anchor_passed and not comparison_passed:
            movement = "anchor_passed_comparison_failed"
        elif not anchor_passed and comparison_passed:
            movement = "anchor_failed_comparison_passed"
        else:
            movement = "both_failed"
        counts[movement] += 1
        movement_rows.append(
            {
                "case_id": case_id,
                "category": comparison.get("category") or anchor.get("category") or "",
                "repeat_index": repeat_index,
                "anchor_mode": anchor_mode,
                "comparison_mode": comparison_mode,
                "anchor_passed": anchor_passed,
                "comparison_passed": comparison_passed,
                "movement": movement,
                "anchor_failures": anchor.get("failures", ""),
                "comparison_failures": comparison.get("failures", ""),
                "comparison_retry_reasons": comparison.get("post_check_retry_reasons", ""),
            }
        )
    return {
        "anchor_mode": anchor_mode,
        "comparison_mode": comparison_mode,
        "case_count": len(rows),
        "paired_case_count": len(movement_rows),
        "movement_counts": counts,
        "rows": movement_rows,
    }


def render_movement_markdown(movement: dict[str, Any]) -> str:
    lines = [
        "# P6o-20 Case Movement vs Guided",
        "",
        f"- anchor_mode: `{movement['anchor_mode']}`",
        f"- comparison_mode: `{movement['comparison_mode']}`",
        f"- paired_case_count: `{movement['paired_case_count']}`",
        f"- movement_counts: `{json.dumps(movement['movement_counts'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "| case_id | category | repeat | anchor_passed | comparison_passed | movement | anchor_failures | comparison_failures | comparison_retry_reasons |",
        "| --- | --- | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in movement["rows"]:
        lines.append(
            f"| `{row['case_id']}` | `{row['category']}` | {row['repeat_index']} | "
            f"{str(row['anchor_passed']).lower()} | {str(row['comparison_passed']).lower()} | "
            f"`{row['movement']}` | `{row['anchor_failures']}` | "
            f"`{row['comparison_failures']}` | `{row['comparison_retry_reasons']}` |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Verify exporter test passes**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_system_path_safe_version_eval.py::test_p6o20_detail_export_writes_per_case_scoring_and_movement -q -p no:cacheprovider
```

Expected: PASS.

---

### Task 2: Exporter Fake-Smoke Validation

**Files:**
- Existing input: `my_md/memory_optimization/eval_reports/p6o19_answer_candidate_retry_shadow_v1/fake_smoke/system_path_safe_version_eval.json`
- Output: `my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/fake_detail_smoke/`

**Interfaces:**
- Consumes Task 1 CLI.
- Produces fake-smoke detail artifacts before real LLM spend.

- [ ] **Step 1: Run exporter on existing P6o-19 fake smoke**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/export_memory_p6o20_answer_details.py \
  --report-json my_md/memory_optimization/eval_reports/p6o19_answer_candidate_retry_shadow_v1/fake_smoke/system_path_safe_version_eval.json \
  --out-dir my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/fake_detail_smoke \
  --anchor-mode safe_version_replace_guided \
  --comparison-mode safe_version_replace_guided_with_retry_shadow
```

Expected: writes all four detail files and exits `0`.

- [ ] **Step 2: Inspect fake detail counts**

Run:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
path = Path("my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/fake_detail_smoke/case_movement_vs_guided.json")
payload = json.loads(path.read_text(encoding="utf-8"))
print(json.dumps(payload["movement_counts"], ensure_ascii=False, sort_keys=True))
PY
```

Expected: paired case movement is present; fake-provider answer rates are not interpreted as quality signal.

---

### Task 3: Real LLM Small Matrix

**Files:**
- Output directory: `my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/real_small_ab/`
- Checkpoint: `my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/real_small_ab/checkpoint.jsonl`

**Interfaces:**
- Consumes existing `scripts/run_memory_system_path_safe_version_eval.py`.
- Produces real `system_path_safe_version_eval.json` and `.md`.

- [ ] **Step 1: Run checkpointed real matrix**

Run:

```bash
test ! -s my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/real_small_ab/checkpoint.jsonl
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace /tmp/akashic-p6o20-answer-candidate-real/workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/real_small_ab \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --enable-real-llm \
  --case-pack standard \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --modes safe_version_replace,safe_version_replace_guided,safe_version_replace_guided_with_retry_shadow \
  --checkpoint-jsonl my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/real_small_ab/checkpoint.jsonl
```

Expected if provider is available: `case_count = 120`, `unique_case_count = 40`, `mode_count = 3`.

If the command is interrupted and checkpoint rows exist, resume intentionally instead of appending duplicate rows:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace /tmp/akashic-p6o20-answer-candidate-real/workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/real_small_ab \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --enable-real-llm \
  --case-pack standard \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --modes safe_version_replace,safe_version_replace_guided,safe_version_replace_guided_with_retry_shadow \
  --checkpoint-jsonl my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/real_small_ab/checkpoint.jsonl \
  --resume
```

If provider returns `402`/`403` insufficient balance or another infra error:
- Stop quality interpretation.
- Keep checkpoint/report only as blocked evidence.
- Record provider error count and do not compare answer rates.

- [ ] **Step 2: Rebuild from checkpoint**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_system_path_safe_version_eval.py \
  --out-dir my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/real_small_ab_rebuilt \
  --enable-real-llm \
  --checkpoint-jsonl my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/real_small_ab/checkpoint.jsonl \
  --checkpoint-report-only
```

Expected: rebuilt `case_count`, `mode_summaries`, `provider_error_count`, `timeout_count`, and `malformed_checkpoint_line_count` can be compared against primary.

---

### Task 4: Gate and Detail Export on Real Data

**Files:**
- Input: real primary report JSON.
- Output:
  - `my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/gate_decision.json`
  - `my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/p6o19_answer_candidate_retry_shadow_report.md`
  - `my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/p6o20_gate_report.md`
  - `my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/answer_details/per_case_scoring_rows.jsonl`
  - `my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/answer_details/per_case_scoring_rows.csv`
  - `my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/answer_details/case_movement_vs_guided.json`
  - `my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/answer_details/case_movement_vs_guided.md`

- [ ] **Step 1: Run P6o-19/P6o-20 gate**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_memory_p6o19_gate.py \
  --report-json my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/real_small_ab/system_path_safe_version_eval.json \
  --out-dir my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1
cp \
  my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/p6o19_answer_candidate_retry_shadow_report.md \
  my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/p6o20_gate_report.md
```

Expected:
- Hard failure for infra/checkpoint/mode/row/safety abnormality.
- If hard checks pass, inspect `gate_decision.json`.
- Status taxonomy:
  - `infra_blocked`: gate command exits nonzero or real run has provider/checkpoint abnormalities. Write blocked status into the P6o-20 report and do not interpret answer quality.
  - `quality_failed`: gate command exits zero and `gate_decision.json.gate_passed = false`.
  - `quality_passed`: gate command exits zero and `gate_decision.json.gate_passed = true`.
- A shell exit `0` from the gate script means only that hard checks passed; it does not mean answer lift passed.

- [ ] **Step 2: Export complete scoring details**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/export_memory_p6o20_answer_details.py \
  --report-json my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/real_small_ab/system_path_safe_version_eval.json \
  --out-dir my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/answer_details \
  --anchor-mode safe_version_replace_guided \
  --comparison-mode safe_version_replace_guided_with_retry_shadow
```

Expected:
- `per_case_scoring_rows.jsonl` has `120` rows for a full real run.
- `case_movement_vs_guided.json` has `40` paired rows for `repeat_count = 1` / `repeat_index = 0`.
- `export_summary.json` has `total_rows = 120`, exact expected modes, no unpaired guided/retry rows, and `forbidden_key_scan_passed = true`.

- [ ] **Step 3: Privacy and safety scan**

Run:

```bash
if rg -n "raw_prompt|full_answer|raw_answer|session_text|Authorization|api_key|sk-|BEGIN|PRIVATE KEY" \
  my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1; then
  echo "forbidden content found"
  exit 1
else
  echo "privacy scan clean"
fi
```

Expected: no committed raw prompt/answer/session/secret fields. Scoring fields and local fixture case ids are allowed.

---

### Task 5: Verification and Documentation

**Files:**
- Modify: `my_md/memory_optimization/README.md`
- Modify: `progress.md`
- Create: `my_md/memory_optimization/eval_reports/p6o20_answer_candidate_retry_shadow_real_small_v1/p6o20_answer_candidate_retry_shadow_real_report.md`

- [ ] **Step 1: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_memory_system_path_safe_version_contract.py \
  tests/test_memory_answer_post_check.py \
  tests/test_memory_system_path_safe_version_eval.py \
  tests/test_memory_engine_contract.py \
  tests/test_turn_pipelines.py \
  -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 2: Run compileall**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m compileall \
  scripts/export_memory_p6o20_answer_details.py \
  scripts/check_memory_p6o19_gate.py \
  scripts/run_memory_system_path_safe_version_eval.py \
  memory2/system_path_safe_version_contract.py \
  memory2/eval_answer_post_check.py \
  memory2/eval_system_path_safe_version.py \
  tests/test_memory_system_path_safe_version_eval.py
```

Expected: exit `0`.

- [ ] **Step 3: Run diff whitespace check**

Run:

```bash
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 4: Write P6o-20 report**

The report must include:
- Method:
  - exact commands used;
  - real/fake status;
  - case pack, limits, mode list, repeat count.
- Data:
  - `unique_case_count`, `case_count`, `mode_count`, `repeat_count`;
  - provider/checkpoint health;
  - per-mode answer/grounding/forbidden/token/latency;
  - retry-shadow candidate contract rate;
  - retry-shadow would-retry count and retry reason counts;
  - movement counts vs guided;
  - locations of JSONL/CSV/JSON/Markdown detail artifacts.
- Conclusion:
  - If infra dirty, state blocked and do not interpret answer quality.
  - If infra clean and gate passed, state `guided-with-retry-shadow` candidate contract improved same-run answer scoring and recommend P6o-21 repeat stability.
  - If infra clean and gate failed, state which failure buckets remain and recommend targeted prompt/retry-shadow design.

- [ ] **Step 5: Update README and progress**

Append concise P6o-20 bullet to `my_md/memory_optimization/README.md`.

Append detailed execution record to `progress.md`.

---

## Gate Interpretation

P6o-20 passes only if:

- `provider_error_count = 0`;
- `timeout_count = 0`;
- `malformed_checkpoint_line_count = 0`;
- expected modes are exactly:
  - `safe_version_replace`;
  - `safe_version_replace_guided`;
  - `safe_version_replace_guided_with_retry_shadow`;
- every mode has the same number of rows;
- grounding remains `100.0%`;
- forbidden violation remains `0.0%`;
- retry-shadow candidate contract enabled rate is `100.0%`;
- guided-with-retry-shadow answer rate is greater than guided answer rate.

P6o-20 does not authorize production activation and does not prove a real retry. A successful P6o-20 only shows that the guided-with-retry-shadow candidate contract improved same-run answer scoring and authorizes P6o-21 repeat stability.
