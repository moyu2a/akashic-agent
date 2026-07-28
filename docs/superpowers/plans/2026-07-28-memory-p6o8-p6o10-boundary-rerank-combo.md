# Memory P6o8-P6o10 Boundary And Rerank Combo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the gated sequence `P6o-8 修安全表达 -> P6o-8 真实验证 -> P6o-9 同场比较 -> P6o-10 组合验证` without production activation.

**Architecture:** Keep every change inside the existing eval harness. P6o-8 changes the model-visible production evidence contract so forbidden boundary raw ids remain in structured raw metadata for post-check but are not rendered into the prompt; P6o-9 reruns a same-matrix comparison of governed, rerank-governed, and revised version-governed; P6o-10 adds a new eval-only profile that combines rerank ordering with revised version-boundary metadata without recall expansion.

**Tech Stack:** Python `>=3.12`, pytest, existing `memory2.eval_answer_contract`, existing `memory2.eval_answer_post_check`, existing `memory2.eval_comprehensive_online`, existing `scripts/run_memory_comprehensive_online_eval.py`, JSON/Markdown reports, checkpoint JSONL under `/tmp`.

## Global Constraints

- Worktree: `/home/jjh/git_work/akashic-agent/.worktrees/memory-next`.
- Do not sync remote/main in this plan unless the user explicitly redirects.
- Do not push without explicit user instruction.
- Do not modify production `AgentLoop`, `Reasoner`, `ToolExecutor`, `ToolRegistry`, production memory writes, production prompts, `plugins/default_memory/engine.py`, or the old `Retriever.retrieve()` return contract.
- All profiles in this plan are eval-only and oracle-protected through existing P6o-2 candidate governance.
- Do not expand recall outside `chain_tri_governed_answer_contract` allowed evidence. Rerank may reorder governed ids; version-boundary may add metadata/warnings; neither may add model-visible evidence ids.
- P6o-8 must preserve raw `forbidden_boundary_ids` and `deleted_evidence_ids` in `result.raw["answer_contract"]` for post-check, but must not render those raw ids or the literal labels `forbidden_boundary_ids:` / `deleted_evidence_ids:` into `text_block`.
- P6o-9 must not add code unless P6o-8 verification shows a reporting/assertion gap.
- P6o-10 may add exactly one new eval-only profile: `chain_tri_rerank_version_governed_answer_contract`.
- Real LLM runs use common `20` + hard `20`, baseline prompt, repeat `1`, explicit `--config /home/jjh/git_work/akashic-agent/config.toml`, checkpoint JSONL under `/tmp`, and no answer debug output.
- Gate rule: stop before the next phase if infra is not clean, report privacy fails, answer-rate drops more than `5.0` points from governed baseline, grounding is below `100.0%`, forbidden is above governed baseline, avg tokens rise by more than `10.0%`, or per-profile post-check risk rises above governed baseline.

---

## File Structure

- Modify `memory2/eval_answer_contract.py`
  - Add a model-visible safe boundary rendering path.
  - Keep raw id fields unchanged in `ProductionEvidenceContract`.
- Modify `memory2/eval_comprehensive_online.py`
  - P6o-10 only: register `chain_tri_rerank_version_governed_answer_contract`.
  - Add combo trace helper and metadata.
- Modify `tests/test_memory_answer_contract.py`
  - P6o-8 tests for hidden forbidden/deleted raw ids in rendered text while raw contract ids remain present.
- Modify `tests/test_memory_comprehensive_online_eval.py`
  - P6o-8 tests for engine text/raw split.
  - P6o-10 tests for combo profile no recall expansion and combined metadata.
- Modify `tests/test_memory_comprehensive_online_cli.py`
  - P6o-8/P6o-9/P6o-10 fake-provider matrix shape tests.
- Create real report directories as gates pass:
  - `my_md/memory_optimization/eval_reports/p6o8_version_boundary_safe_presentation_small_online_v1/`
  - `my_md/memory_optimization/eval_reports/p6o9_governed_rerank_version_same_matrix_v1/`
  - `my_md/memory_optimization/eval_reports/p6o10_rerank_version_governed_combo_small_online_v1/`
- Modify docs after each completed gate:
  - `my_md/memory_optimization/README.md`
  - `my_md/memory_optimization/02-memory-quality-metrics.md`
  - `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
  - `task_plan.md`
  - `progress.md`

---

## Phase Gate Helpers

Use this per-profile post-check snippet after each real report with `REPORT_JSON`
and `EXPECTED_CASE_COUNT` set in the shell command:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
import os
from pathlib import Path
path = Path(os.environ["REPORT_JSON"])
payload = json.loads(path.read_text(encoding="utf-8"))
m = payload["metrics"]
assert m["real_llm_enabled"] is True
assert m["case_count"] == int(os.environ["EXPECTED_CASE_COUNT"])
assert m["completed_call_count"] == int(os.environ["EXPECTED_CASE_COUNT"])
assert m["unique_case_count"] == 40
assert m["prompt_variant_count"] == 1
assert m["repeat_count"] == 1
assert m["infra_passed"] is True
assert m["provider_error_count"] == 0
assert m["timeout_count"] == 0
assert m.get("excluded_infra_failure_count", 0) == 0
for key in ("raw_query_included", "raw_memory_summary_included", "prompt_included", "session_text_included", "full_answer_included"):
    assert m[key] is False, (key, m[key])

def counts(profile):
    result = {
        "needs_retry": 0,
        "forbidden_boundary_included": 0,
        "missing_likely_relevant_context": 0,
        "stale_evidence_included": 0,
        "conflict_evidence_included": 0,
        "insufficient_fallback_missing": 0,
    }
    retry_cases = []
    for record in payload["case_records"]:
        if record["profile_name"] != profile:
            continue
        shadow = record.get("answer_post_check_shadow") or {}
        if shadow.get("needs_retry"):
            retry_cases.append(record["case_id"])
        reasons = set(shadow.get("retry_reasons") or ())
        result["needs_retry"] += int(bool(shadow.get("needs_retry")))
        result["forbidden_boundary_included"] += int(
            "forbidden_boundary_included" in reasons
            or bool(shadow.get("included_forbidden_boundary_ids"))
        )
        result["missing_likely_relevant_context"] += int(
            "missing_likely_relevant_context" in reasons
            or bool(shadow.get("missing_likely_relevant_context_ids"))
        )
        result["stale_evidence_included"] += int(
            "stale_evidence_included" in reasons
            or bool(shadow.get("included_stale_warning_ids"))
        )
        result["conflict_evidence_included"] += int(
            "conflict_evidence_included" in reasons
            or bool(shadow.get("included_conflict_warning_ids"))
        )
        result["insufficient_fallback_missing"] += int(
            "insufficient_evidence_fallback_missing" in reasons
            or (
                bool(shadow.get("insufficient_evidence_fallback_expected"))
                and not bool(shadow.get("insufficient_evidence_fallback_observed"))
            )
        )
    return result, retry_cases

base = m["profile_summaries"]["chain_tri_governed_answer_contract"]
for profile, row in m["profile_summaries"].items():
    print(profile, row["answer_success_count"], row["case_count"], row["answer_rule_pass_rate"], row["memory_grounding_pass_rate"], row["forbidden_violation_rate"], row["avg_total_token_count"], counts(profile))
    assert float(row["answer_rule_pass_rate"]) >= float(base["answer_rule_pass_rate"]) - 5.0
    assert float(row["memory_grounding_pass_rate"]) == 100.0
    assert float(row["forbidden_violation_rate"]) <= float(base["forbidden_violation_rate"])
    assert float(row["avg_total_token_count"]) <= float(base["avg_total_token_count"]) * 1.10
    if profile != "chain_tri_governed_answer_contract":
        profile_counts, _ = counts(profile)
        base_counts, _ = counts("chain_tri_governed_answer_contract")
        for key, value in profile_counts.items():
            assert value <= base_counts[key], (profile, key, base_counts, profile_counts)
print("gate ok")
PY
```

---

### Task 1: P6o-8 Hide Model-Visible Forbidden Boundary Raw IDs

**Files:**
- Modify: `tests/test_memory_answer_contract.py`
- Modify: `tests/test_memory_comprehensive_online_eval.py`
- Modify: `memory2/eval_answer_contract.py`

**Interfaces:**
- Consumes:
  - `render_production_evidence_contract_block(contract: ProductionEvidenceContract) -> str`
  - `build_production_governed_tri_evidence_contract(..., version_boundary_info=...) -> ProductionEvidenceContract`
- Produces:
  - rendered prompt text that does not include raw `forbidden_boundary_ids` values or the literal field label `forbidden_boundary_ids:`
  - raw `contract.forbidden_boundary_ids` and `result.raw["answer_contract"]["forbidden_boundary_ids"]` unchanged for post-check.

- [x] **Step 1: Write failing contract rendering test**

Add to `tests/test_memory_answer_contract.py`:

```python
def test_version_boundary_render_hides_forbidden_and_deleted_raw_ids_from_prompt() -> None:
    case = _case_with_should_not_in_tri()
    governed_trace_info = {
        "ids": ("target",),
        "trace": {
            "candidate_governance_mode": "tiered",
            "candidate_risk_tiers": [
                {"candidate_id": "target", "tier": "allow", "risks": (), "lane": "semantic"},
                {"candidate_id": "blocked", "tier": "delete", "risks": ("forbidden_candidate",), "lane": "semantic"},
            ],
        },
    }
    case = replace(
        case,
        setup={
            **case.setup,
            "memory_items": [
                {"id": "old", "summary": "old version", "status": "superseded", "source_ref": "telegram:1:0"},
                {"id": "target", "summary": "current version", "status": "active", "source_ref": "telegram:1:1"},
                {"id": "blocked", "summary": "blocked evidence", "status": "active", "source_ref": "telegram:1:2", "forbidden": True},
            ],
            "memory_replacements": [
                {
                    "old_item_id": "old",
                    "new_item_id": "target",
                    "old_summary": "old version",
                    "new_summary": "current version",
                    "old_source_ref": "telegram:1:0",
                    "new_source_ref": "telegram:1:1",
                }
            ],
        },
    )
    boundary = build_version_boundary_info(case, governed_trace_info)
    contract = build_production_governed_tri_evidence_contract(
        case,
        governed_trace_info,
        profile_name="chain_tri_version_governed_answer_contract",
        version_boundary_info=boundary,
    )

    text = render_production_evidence_contract_block(contract)

    assert set(contract.forbidden_boundary_ids) == {"blocked", "old"}
    assert contract.deleted_evidence_ids == ("blocked",)
    for item_id in contract.forbidden_boundary_ids + contract.deleted_evidence_ids:
        assert item_id not in text
    assert "forbidden_boundary_ids:" not in text
    assert "deleted_evidence_ids:" not in text
    assert "forbidden_boundary_count: 2" in text
    assert "deleted_evidence_count: 1" in text
    assert "superseded evidence exists" in text
```

- [x] **Step 2: Write failing engine raw/text split test**

Add to `tests/test_memory_comprehensive_online_eval.py`:

```python
def test_version_governed_engine_hides_forbidden_ids_but_keeps_raw_post_check() -> None:
    case = _case_with_version_boundary_signal()
    engine = ComprehensiveOnlineMemoryEngine(
        case,
        profile_name="chain_tri_version_governed_answer_contract",
        prompt_variant="baseline",
    )

    result = asyncio.run(
        engine.retrieve(
            MemoryEngineRetrieveRequest(
                query=str(case.setup["query"]),
                mode="explicit",
                top_k=8,
            )
        )
    )
    forbidden_ids = tuple(result.raw["answer_contract"]["forbidden_boundary_ids"])
    deleted_ids = tuple(result.raw["answer_contract"]["deleted_evidence_ids"])

    assert forbidden_ids
    assert "forbidden_boundary_ids:" not in result.text_block
    assert "deleted_evidence_ids:" not in result.text_block
    for item_id in forbidden_ids + deleted_ids:
        assert item_id not in result.text_block
    assert "forbidden_boundary_count:" in result.text_block
    assert "deleted_evidence_count:" in result.text_block
```

- [x] **Step 3: Run RED tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_answer_contract.py::test_version_boundary_render_hides_forbidden_raw_ids_from_prompt \
  tests/test_memory_comprehensive_online_eval.py::test_version_governed_engine_hides_forbidden_ids_but_keeps_raw_post_check \
  -q -p no:cacheprovider
```

Expected: both tests fail because current rendering includes `forbidden_boundary_ids:` and raw ids.

- [x] **Step 4: Implement safe rendering**

In `memory2/eval_answer_contract.py`, change only `render_production_evidence_contract_block()`.

Replace the current model-visible forbidden boundary lines:

```python
"不要使用 forbidden_boundary_ids 中的记忆；stale_warning_ids 和 conflict_warning_ids 只能作为风险提示。",
...
"forbidden_boundary: " + ", ".join(contract.forbidden_boundary),
...
"forbidden_boundary_ids: " + ", ".join(contract.forbidden_boundary_ids),
"deleted_evidence_ids: " + ", ".join(contract.deleted_evidence_ids),
```

with:

```python
"如果存在 forbidden boundary，表示有旧版本、越界或禁止使用的记忆边界；不要复述或引用这些边界内容。",
...
"forbidden_boundary_count: " + str(len(contract.forbidden_boundary_ids)),
"deleted_evidence_count: " + str(len(contract.deleted_evidence_ids)),
"forbidden_boundary_instruction: superseded evidence exists; use only allowed_evidence and active_version evidence.",
```

Do not remove raw fields from `ProductionEvidenceContract`.

Update existing tests that currently assert the old prompt-visible id label:

```python
assert "forbidden_boundary_count:" in result.text_block
assert "forbidden_boundary_ids:" not in result.text_block
```

Replace old assertions in `tests/test_memory_answer_contract.py` and
`tests/test_memory_comprehensive_online_eval.py` that require
`"forbidden_boundary_ids:" in text`, `"deleted_evidence_ids:" in text`,
`"forbidden_boundary_ids:" in result.text_block`, or
`"deleted_evidence_ids:" in result.text_block`.

- [x] **Step 5: Run GREEN tests and focused regressions**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_answer_contract.py \
  tests/test_memory_comprehensive_online_eval.py \
  -q -p no:cacheprovider
```

Expected: both files pass.

- [x] **Step 6: Commit P6o-8 code**

Run:

```bash
git add memory2/eval_answer_contract.py tests/test_memory_answer_contract.py tests/test_memory_comprehensive_online_eval.py
git commit -m "fix: hide forbidden boundary ids from evidence prompt"
```

---

### Task 2: P6o-8 Fake And Real Validation

**Files:**
- Modify: `tests/test_memory_comprehensive_online_cli.py`
- Create: `my_md/memory_optimization/eval_reports/p6o8_version_boundary_safe_presentation_small_online_v1/memory_comprehensive_online_eval.json`
- Create: `my_md/memory_optimization/eval_reports/p6o8_version_boundary_safe_presentation_small_online_v1/memory_comprehensive_online_eval.md`
- Modify docs listed in File Structure.

**Interfaces:**
- Consumes P6o-8 safe rendering from Task 1.
- Produces P6o-8 gate result. P6o-9 may begin only if this gate passes.

- [x] **Step 1: Add fake CLI matrix regression**

Add to `tests/test_memory_comprehensive_online_cli.py`:

```python
def test_comprehensive_online_cli_p6o8_safe_boundary_fake_provider_matrix_shape(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "reports"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_comprehensive_online_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(output_dir),
            "--fake-provider",
            "--case-pack",
            "standard",
            "--balanced-small",
            "--common-limit",
            "2",
            "--hard-limit",
            "2",
            "--profiles",
            "chain_tri_governed_answer_contract,chain_tri_version_governed_answer_contract",
            "--prompt-variants",
            "baseline",
            "--repeats",
            "1",
            "--checkpoint-jsonl",
            str(tmp_path / "checkpoint.jsonl"),
            "--real-memory-workspace",
            str(tmp_path / "empty-real-workspace"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        (output_dir / "memory_comprehensive_online_eval.json").read_text(encoding="utf-8")
    )
    markdown = (output_dir / "memory_comprehensive_online_eval.md").read_text(encoding="utf-8")
    assert payload["metrics"]["case_count"] == 8
    assert payload["metrics"]["profile_count"] == 2
    assert payload["metrics"]["provider_error_count"] == 0
    assert payload["metrics"]["timeout_count"] == 0
    assert "chain_tri_version_governed_answer_contract" in markdown
```

- [x] **Step 2: Run CLI regression**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_comprehensive_online_cli.py -q -p no:cacheprovider
```

Expected: CLI tests pass.

- [x] **Step 3: Commit CLI regression**

Run:

```bash
git add tests/test_memory_comprehensive_online_cli.py
git commit -m "test: cover p6o8 safe boundary online matrix"
```

- [x] **Step 4: Run P6o-8 fake gate**

Run:

```bash
rm -rf /tmp/akashic-memory-p6o8-safe-boundary
mkdir -p /tmp/akashic-memory-p6o8-safe-boundary
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-p6o8-safe-boundary/workspace \
  --out-dir /tmp/akashic-memory-p6o8-safe-boundary/fake-reports \
  --fake-provider \
  --case-pack standard \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --profiles chain_tri_governed_answer_contract,chain_tri_version_governed_answer_contract \
  --prompt-variants baseline \
  --repeats 1 \
  --checkpoint-jsonl /tmp/akashic-memory-p6o8-safe-boundary/fake.checkpoint.jsonl \
  --real-memory-workspace /tmp/akashic-memory-p6o8-safe-boundary/empty-real-memory \
  --concurrency 2
```

Expected: exits `0`, `case_count = 80`, provider/timeout `0`.

- [x] **Step 5: Run P6o-8 real gate**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --workspace /tmp/akashic-memory-p6o8-safe-boundary/real-workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o8_version_boundary_safe_presentation_small_online_v1 \
  --enable-real-llm \
  --case-pack standard \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --profiles chain_tri_governed_answer_contract,chain_tri_version_governed_answer_contract \
  --prompt-variants baseline \
  --repeats 1 \
  --checkpoint-jsonl /tmp/akashic-memory-p6o8-safe-boundary/real.checkpoint.jsonl \
  --real-memory-workspace /tmp/akashic-memory-p6o8-safe-boundary/empty-real-memory \
  --concurrency 2
```

Expected: exits `0`.

- [x] **Step 6: Assert P6o-8 real gate**

Run:

```bash
REPORT_JSON=my_md/memory_optimization/eval_reports/p6o8_version_boundary_safe_presentation_small_online_v1/memory_comprehensive_online_eval.json \
EXPECTED_CASE_COUNT=80 \
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
import os
from pathlib import Path
path = Path(os.environ["REPORT_JSON"])
payload = json.loads(path.read_text(encoding="utf-8"))
m = payload["metrics"]
assert m["real_llm_enabled"] is True
assert m["case_count"] == int(os.environ["EXPECTED_CASE_COUNT"])
assert m["completed_call_count"] == int(os.environ["EXPECTED_CASE_COUNT"])
assert m["unique_case_count"] == 40
assert m["profile_count"] == 2
assert set(m["profile_summaries"]) == {
    "chain_tri_governed_answer_contract",
    "chain_tri_version_governed_answer_contract",
}
assert m["prompt_variant_count"] == 1
assert m["repeat_count"] == 1
assert m["infra_passed"] is True
assert m["provider_error_count"] == 0
assert m["timeout_count"] == 0
assert m.get("excluded_infra_failure_count", 0) == 0
for key in ("raw_query_included", "raw_memory_summary_included", "prompt_included", "session_text_included", "full_answer_included"):
    assert m[key] is False, (key, m[key])
def counts(profile):
    result = {"needs_retry": 0, "forbidden_boundary_included": 0, "missing_likely_relevant_context": 0, "stale_evidence_included": 0, "conflict_evidence_included": 0, "insufficient_fallback_missing": 0}
    retry_cases = []
    for record in payload["case_records"]:
        if record["profile_name"] != profile:
            continue
        shadow = record.get("answer_post_check_shadow") or {}
        if shadow.get("needs_retry"):
            retry_cases.append(record["case_id"])
        for key in result:
            result[key] += int(bool(shadow.get(key)))
    return result, retry_cases
base = m["profile_summaries"]["chain_tri_governed_answer_contract"]
base_counts, _ = counts("chain_tri_governed_answer_contract")
for profile, row in m["profile_summaries"].items():
    print(profile, row["answer_success_count"], row["case_count"], row["answer_rule_pass_rate"], row["memory_grounding_pass_rate"], row["forbidden_violation_rate"], row["avg_total_token_count"], counts(profile))
    assert float(row["answer_rule_pass_rate"]) >= float(base["answer_rule_pass_rate"]) - 5.0
    assert float(row["memory_grounding_pass_rate"]) == 100.0
    assert float(row["forbidden_violation_rate"]) <= float(base["forbidden_violation_rate"])
    assert float(row["avg_total_token_count"]) <= float(base["avg_total_token_count"]) * 1.10
    if profile != "chain_tri_governed_answer_contract":
        profile_counts, _ = counts(profile)
        for key, value in profile_counts.items():
            assert value <= base_counts[key], (profile, key, base_counts, profile_counts)
print("gate ok")
PY
```

Expected: prints `gate ok`. If this fails, stop before P6o-9.

- [x] **Step 7: Update docs and commit P6o-8 result**

Record exact P6o-8 data in all docs listed in File Structure and commit:

```bash
git add -f docs/superpowers/plans/2026-07-28-memory-p6o8-p6o10-boundary-rerank-combo.md
git add my_md/memory_optimization/README.md \
  my_md/memory_optimization/02-memory-quality-metrics.md \
  my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md \
  my_md/memory_optimization/eval_reports/p6o8_version_boundary_safe_presentation_small_online_v1/memory_comprehensive_online_eval.json \
  my_md/memory_optimization/eval_reports/p6o8_version_boundary_safe_presentation_small_online_v1/memory_comprehensive_online_eval.md \
  task_plan.md progress.md
git commit -m "docs: record p6o8 safe boundary presentation"
```

---

### Task 3: P6o-9 Same-Matrix Governed/Rerank/Version Comparison

**Files:**
- Create: `my_md/memory_optimization/eval_reports/p6o9_governed_rerank_version_same_matrix_v1/memory_comprehensive_online_eval.json`
- Create: `my_md/memory_optimization/eval_reports/p6o9_governed_rerank_version_same_matrix_v1/memory_comprehensive_online_eval.md`
- Modify docs listed in File Structure.

**Interfaces:**
- Consumes P6o-8 passing gate.
- Produces same-run comparison among existing profiles:
  - `chain_tri_governed_answer_contract`
  - `chain_tri_rerank_governed_answer_contract`
  - `chain_tri_version_governed_answer_contract`

- [x] **Step 1: Run P6o-9 fake gate**

Run:

```bash
rm -rf /tmp/akashic-memory-p6o9-same-matrix
mkdir -p /tmp/akashic-memory-p6o9-same-matrix
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-p6o9-same-matrix/workspace \
  --out-dir /tmp/akashic-memory-p6o9-same-matrix/fake-reports \
  --fake-provider \
  --case-pack standard \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --profiles chain_tri_governed_answer_contract,chain_tri_rerank_governed_answer_contract,chain_tri_version_governed_answer_contract \
  --prompt-variants baseline \
  --repeats 1 \
  --checkpoint-jsonl /tmp/akashic-memory-p6o9-same-matrix/fake.checkpoint.jsonl \
  --real-memory-workspace /tmp/akashic-memory-p6o9-same-matrix/empty-real-memory \
  --concurrency 2
```

Expected: exits `0`, `case_count = 120`, `profile_count = 3`, provider/timeout `0`.

- [x] **Step 2: Run P6o-9 real matrix**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --workspace /tmp/akashic-memory-p6o9-same-matrix/real-workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o9_governed_rerank_version_same_matrix_v1 \
  --enable-real-llm \
  --case-pack standard \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --profiles chain_tri_governed_answer_contract,chain_tri_rerank_governed_answer_contract,chain_tri_version_governed_answer_contract \
  --prompt-variants baseline \
  --repeats 1 \
  --checkpoint-jsonl /tmp/akashic-memory-p6o9-same-matrix/real.checkpoint.jsonl \
  --real-memory-workspace /tmp/akashic-memory-p6o9-same-matrix/empty-real-memory \
  --concurrency 2
```

Expected: exits `0`.

- [x] **Step 3: Assert P6o-9 gate**

Run:

```bash
REPORT_JSON=my_md/memory_optimization/eval_reports/p6o9_governed_rerank_version_same_matrix_v1/memory_comprehensive_online_eval.json \
EXPECTED_CASE_COUNT=120 \
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
import os
from pathlib import Path
path = Path(os.environ["REPORT_JSON"])
payload = json.loads(path.read_text(encoding="utf-8"))
m = payload["metrics"]
assert m["real_llm_enabled"] is True
assert m["case_count"] == int(os.environ["EXPECTED_CASE_COUNT"])
assert m["completed_call_count"] == int(os.environ["EXPECTED_CASE_COUNT"])
assert m["unique_case_count"] == 40
assert m["profile_count"] == 3
assert set(m["profile_summaries"]) == {
    "chain_tri_governed_answer_contract",
    "chain_tri_rerank_governed_answer_contract",
    "chain_tri_version_governed_answer_contract",
}
assert m["prompt_variant_count"] == 1
assert m["repeat_count"] == 1
assert m["infra_passed"] is True
assert m["provider_error_count"] == 0
assert m["timeout_count"] == 0
assert m.get("excluded_infra_failure_count", 0) == 0
for key in ("raw_query_included", "raw_memory_summary_included", "prompt_included", "session_text_included", "full_answer_included"):
    assert m[key] is False, (key, m[key])
def counts(profile):
    result = {"needs_retry": 0, "forbidden_boundary_included": 0, "missing_likely_relevant_context": 0, "stale_evidence_included": 0, "conflict_evidence_included": 0, "insufficient_fallback_missing": 0}
    for record in payload["case_records"]:
        if record["profile_name"] != profile:
            continue
        shadow = record.get("answer_post_check_shadow") or {}
        reasons = set(shadow.get("retry_reasons") or ())
        result["needs_retry"] += int(bool(shadow.get("needs_retry")))
        result["forbidden_boundary_included"] += int(
            "forbidden_boundary_included" in reasons
            or bool(shadow.get("included_forbidden_boundary_ids"))
        )
        result["missing_likely_relevant_context"] += int(
            "missing_likely_relevant_context" in reasons
            or bool(shadow.get("missing_likely_relevant_context_ids"))
        )
        result["stale_evidence_included"] += int(
            "stale_evidence_included" in reasons
            or bool(shadow.get("included_stale_warning_ids"))
        )
        result["conflict_evidence_included"] += int(
            "conflict_evidence_included" in reasons
            or bool(shadow.get("included_conflict_warning_ids"))
        )
        result["insufficient_fallback_missing"] += int(
            "insufficient_evidence_fallback_missing" in reasons
            or (
                bool(shadow.get("insufficient_evidence_fallback_expected"))
                and not bool(shadow.get("insufficient_evidence_fallback_observed"))
            )
        )
    return result
base = m["profile_summaries"]["chain_tri_governed_answer_contract"]
base_counts = counts("chain_tri_governed_answer_contract")
for profile, row in m["profile_summaries"].items():
    print(profile, row["answer_success_count"], row["case_count"], row["answer_rule_pass_rate"], row["memory_grounding_pass_rate"], row["forbidden_violation_rate"], row["avg_total_token_count"], counts(profile))
    assert float(row["answer_rule_pass_rate"]) >= float(base["answer_rule_pass_rate"]) - 5.0
    assert float(row["memory_grounding_pass_rate"]) == 100.0
    assert float(row["forbidden_violation_rate"]) <= float(base["forbidden_violation_rate"])
    assert float(row["avg_total_token_count"]) <= float(base["avg_total_token_count"]) * 1.10
    if profile != "chain_tri_governed_answer_contract":
        profile_counts = counts(profile)
        for key, value in profile_counts.items():
            assert value <= base_counts[key], (profile, key, base_counts, profile_counts)
print("gate ok")
PY
```

Expected: prints `gate ok`. If rerank or version fails the gate, stop before P6o-10.

- [x] **Step 4: Update docs and commit P6o-9 result**

Record exact P6o-9 data and commit:

```bash
git add my_md/memory_optimization/README.md \
  my_md/memory_optimization/02-memory-quality-metrics.md \
  my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md \
  my_md/memory_optimization/eval_reports/p6o9_governed_rerank_version_same_matrix_v1/memory_comprehensive_online_eval.json \
  my_md/memory_optimization/eval_reports/p6o9_governed_rerank_version_same_matrix_v1/memory_comprehensive_online_eval.md \
  task_plan.md progress.md
git commit -m "docs: record p6o9 governed rerank version comparison"
```

---

### Task 4: P6o-10 Add Rerank + Revised Version Combo Profile

**Files:**
- Modify: `tests/test_memory_comprehensive_online_eval.py`
- Modify: `tests/test_memory_comprehensive_online_cli.py`
- Modify: `memory2/eval_comprehensive_online.py`

**Interfaces:**
- Consumes:
  - `rerank_governed_tri_trace_for_case(case: EvalCase) -> dict[str, object]`
  - `build_version_boundary_info(case, governed_trace_info) -> VersionBoundaryInfo`
  - safe rendering from P6o-8.
- Produces:
  - `TRI_RERANK_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE = "chain_tri_rerank_version_governed_answer_contract"`
  - `rerank_version_governed_tri_trace_for_case(case: EvalCase) -> dict[str, object]`
  - optional profile accepted by CLI/eval harness.

- [x] **Step 1: Write failing combo tests**

Add to `tests/test_memory_comprehensive_online_eval.py`:

```python
def _case_with_version_boundary_and_rerank_delta():
    for case in (
        build_quantitative_eval_cases(case_set="common", limit=20, case_pack="standard")
        + build_quantitative_eval_cases(case_set="hard", limit=20, case_pack="standard")
    ):
        if not case.setup.get("memory_replacements"):
            continue
        governed_ids = evidence_ids_for_profile(
            case,
            "chain_tri_governed_answer_contract",
        )
        rerank_ids = evidence_ids_for_profile(
            case,
            "chain_tri_rerank_governed_answer_contract",
        )
        if rerank_ids != governed_ids and set(rerank_ids) == set(governed_ids):
            return case
    raise AssertionError("fixture must include version boundary case with rerank delta")


def test_rerank_version_governed_profile_reorders_without_recall_expansion() -> None:
    case = _case_with_version_boundary_and_rerank_delta()

    combo_ids = evidence_ids_for_profile(
        case,
        "chain_tri_rerank_version_governed_answer_contract",
    )
    rerank_ids = evidence_ids_for_profile(
        case,
        "chain_tri_rerank_governed_answer_contract",
    )
    governed_ids = evidence_ids_for_profile(
        case,
        "chain_tri_governed_answer_contract",
    )

    assert combo_ids == rerank_ids
    assert combo_ids != governed_ids
    assert set(combo_ids) == set(governed_ids)
    assert profile_evidence_source(
        "chain_tri_rerank_version_governed_answer_contract"
    ) == (
        "tri_rerank_version_governed_answer_contract."
        "reranked_version_boundaried_governed_allowed_evidence_ids"
    )


def test_rerank_version_governed_profile_injects_safe_combined_contract() -> None:
    case = _case_with_version_boundary_and_rerank_delta()
    engine = ComprehensiveOnlineMemoryEngine(
        case,
        profile_name="chain_tri_rerank_version_governed_answer_contract",
        prompt_variant="baseline",
    )

    result = asyncio.run(
        engine.retrieve(
            MemoryEngineRetrieveRequest(
                query=str(case.setup["query"]),
                mode="explicit",
                top_k=8,
            )
        )
    )

    assert "Evidence Contract: chain_tri_rerank_version_governed_answer_contract" in result.text_block
    assert "forbidden_boundary_ids:" not in result.text_block
    assert result.raw["answer_contract"]["combines_candidate_governance"] is True
    assert result.raw["answer_contract"]["combines_rerank_injection"] is True
    assert result.raw["answer_contract"]["combines_version_boundary"] is True
    assert result.raw["answer_contract"]["does_not_expand_recall"] is True
    assert result.raw["rerank_signal"]["recall_expanded"] is False
    assert result.raw["version_boundary"]["recall_expanded"] is False
```

- [x] **Step 2: Run RED combo tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_comprehensive_online_eval.py::test_rerank_version_governed_profile_reorders_without_recall_expansion \
  tests/test_memory_comprehensive_online_eval.py::test_rerank_version_governed_profile_injects_safe_combined_contract \
  -q -p no:cacheprovider
```

Expected: fail because the profile/helper is unknown.

- [x] **Step 3: Implement combo profile**

In `memory2/eval_comprehensive_online.py`:

Add constant:

```python
TRI_RERANK_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE = (
    "chain_tri_rerank_version_governed_answer_contract"
)
```

Add it to `PRODUCTION_GOVERNED_ANSWER_CONTRACT_PROFILES` and `OPTIONAL_ANSWER_QUALITY_PROFILES`.

Add metadata:

```python
TRI_RERANK_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE: {
    "eval_only": True,
    "oracle_protected": True,
    "uses_fixture_expected_ids": True,
    "diagnostic_answer_contract": True,
    "uses_fixture_answer_expectations": False,
    "production_safe_evidence_contract": True,
    "combines_candidate_governance": True,
    "combines_rerank_injection": True,
    "combines_version_boundary": True,
    "does_not_expand_recall": True,
    "candidate_governance_mode": "tiered",
    "description": (
        "Reorders candidate-governed tri evidence with rerank signal and "
        "adds safe version-boundary metadata without recall expansion."
    ),
},
```

Add helper:

```python
def rerank_version_governed_tri_trace_for_case(case: EvalCase) -> dict[str, object]:
    trace_info = rerank_governed_tri_trace_for_case(case)
    ids = tuple(str(item) for item in trace_info.get("ids", ()))
    boundary = build_version_boundary_info(case, trace_info)
    trace = dict(trace_info.get("trace", {}))
    trace["version_boundary"] = {
        "active_version_ids": list(boundary.active_version_ids),
        "stale_warning_ids": list(boundary.stale_warning_ids),
        "conflict_warning_ids": list(boundary.conflict_warning_ids),
        "forbidden_boundary_ids": list(boundary.forbidden_boundary_ids),
        "rollback_candidate_ids": list(boundary.rollback_candidate_ids),
        "conflict_chain_count": boundary.conflict_chain_count,
        "stale_recalled_count": boundary.stale_recalled_count,
        "superseded_recalled_count": boundary.superseded_recalled_count,
        "recall_expanded": False,
    }
    return {"ids": ids, "trace": trace}
```

Route this helper wherever governed trace is selected. Add profile source:

```python
TRI_RERANK_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE: (
    "tri_rerank_version_governed_answer_contract."
    "reranked_version_boundaried_governed_allowed_evidence_ids"
),
```

Set `combines_version_boundary` and `combines_rerank_injection` true for this profile and pass `version_boundary_info` for both version-only and combo profiles.

Add `does_not_expand_recall` to production-safe answer contract raw payload:

```python
does_not_expand_recall = self.profile_name in {
    TRI_RERANK_GOVERNED_ANSWER_CONTRACT_PROFILE,
    TRI_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE,
    TRI_RERANK_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE,
}
```

and inside `raw["answer_contract"]`:

```python
"does_not_expand_recall": does_not_expand_recall,
```

- [x] **Step 4: Add CLI fake smoke for combo**

Add to `tests/test_memory_comprehensive_online_cli.py`:

```python
def test_comprehensive_online_cli_p6o10_combo_fake_provider_matrix_shape(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "reports"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_comprehensive_online_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(output_dir),
            "--fake-provider",
            "--case-pack",
            "standard",
            "--balanced-small",
            "--common-limit",
            "2",
            "--hard-limit",
            "2",
            "--profiles",
            (
                "chain_tri_governed_answer_contract,"
                "chain_tri_rerank_governed_answer_contract,"
                "chain_tri_version_governed_answer_contract,"
                "chain_tri_rerank_version_governed_answer_contract"
            ),
            "--prompt-variants",
            "baseline",
            "--repeats",
            "1",
            "--checkpoint-jsonl",
            str(tmp_path / "checkpoint.jsonl"),
            "--real-memory-workspace",
            str(tmp_path / "empty-real-workspace"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        (output_dir / "memory_comprehensive_online_eval.json").read_text(encoding="utf-8")
    )
    assert payload["metrics"]["case_count"] == 16
    assert payload["metrics"]["profile_count"] == 4
    metadata = payload["metrics"]["profile_metadata"][
        "chain_tri_rerank_version_governed_answer_contract"
    ]
    assert metadata["combines_rerank_injection"] is True
    assert metadata["combines_version_boundary"] is True
    assert metadata["does_not_expand_recall"] is True
```

- [x] **Step 5: Run GREEN combo tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_comprehensive_online_eval.py \
  tests/test_memory_comprehensive_online_cli.py \
  -q -p no:cacheprovider
```

Expected: both files pass.

- [x] **Step 6: Commit combo code**

Run:

```bash
git add memory2/eval_comprehensive_online.py tests/test_memory_comprehensive_online_eval.py tests/test_memory_comprehensive_online_cli.py
git commit -m "feat: add rerank version governed answer contract profile"
```

---

### Task 5: P6o-10 Combo Fake And Real Validation

**Files:**
- Create: `my_md/memory_optimization/eval_reports/p6o10_rerank_version_governed_combo_small_online_v1/memory_comprehensive_online_eval.json`
- Create: `my_md/memory_optimization/eval_reports/p6o10_rerank_version_governed_combo_small_online_v1/memory_comprehensive_online_eval.md`
- Modify docs listed in File Structure.

**Interfaces:**
- Consumes P6o-10 combo profile from Task 4.
- Produces P6o-10 real gate result.

- [ ] **Step 1: Run P6o-10 fake gate**

Run:

```bash
rm -rf /tmp/akashic-memory-p6o10-combo
mkdir -p /tmp/akashic-memory-p6o10-combo
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-p6o10-combo/workspace \
  --out-dir /tmp/akashic-memory-p6o10-combo/fake-reports \
  --fake-provider \
  --case-pack standard \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --profiles chain_tri_governed_answer_contract,chain_tri_rerank_governed_answer_contract,chain_tri_version_governed_answer_contract,chain_tri_rerank_version_governed_answer_contract \
  --prompt-variants baseline \
  --repeats 1 \
  --checkpoint-jsonl /tmp/akashic-memory-p6o10-combo/fake.checkpoint.jsonl \
  --real-memory-workspace /tmp/akashic-memory-p6o10-combo/empty-real-memory \
  --concurrency 2
```

Expected: exits `0`, `case_count = 160`, `profile_count = 4`, provider/timeout `0`.

- [ ] **Step 2: Run P6o-10 real matrix**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --workspace /tmp/akashic-memory-p6o10-combo/real-workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o10_rerank_version_governed_combo_small_online_v1 \
  --enable-real-llm \
  --case-pack standard \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --profiles chain_tri_governed_answer_contract,chain_tri_rerank_governed_answer_contract,chain_tri_version_governed_answer_contract,chain_tri_rerank_version_governed_answer_contract \
  --prompt-variants baseline \
  --repeats 1 \
  --checkpoint-jsonl /tmp/akashic-memory-p6o10-combo/real.checkpoint.jsonl \
  --real-memory-workspace /tmp/akashic-memory-p6o10-combo/empty-real-memory \
  --concurrency 2
```

Expected: exits `0`.

- [ ] **Step 3: Assert P6o-10 gate**

Run:

```bash
REPORT_JSON=my_md/memory_optimization/eval_reports/p6o10_rerank_version_governed_combo_small_online_v1/memory_comprehensive_online_eval.json \
EXPECTED_CASE_COUNT=160 \
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
import os
from pathlib import Path
path = Path(os.environ["REPORT_JSON"])
payload = json.loads(path.read_text(encoding="utf-8"))
m = payload["metrics"]
assert m["real_llm_enabled"] is True
assert m["case_count"] == int(os.environ["EXPECTED_CASE_COUNT"])
assert m["completed_call_count"] == int(os.environ["EXPECTED_CASE_COUNT"])
assert m["unique_case_count"] == 40
assert m["profile_count"] == 4
assert set(m["profile_summaries"]) == {
    "chain_tri_governed_answer_contract",
    "chain_tri_rerank_governed_answer_contract",
    "chain_tri_version_governed_answer_contract",
    "chain_tri_rerank_version_governed_answer_contract",
}
assert m["prompt_variant_count"] == 1
assert m["repeat_count"] == 1
assert m["infra_passed"] is True
assert m["provider_error_count"] == 0
assert m["timeout_count"] == 0
assert m.get("excluded_infra_failure_count", 0) == 0
for key in ("raw_query_included", "raw_memory_summary_included", "prompt_included", "session_text_included", "full_answer_included"):
    assert m[key] is False, (key, m[key])
def counts(profile):
    result = {"needs_retry": 0, "forbidden_boundary_included": 0, "missing_likely_relevant_context": 0, "stale_evidence_included": 0, "conflict_evidence_included": 0, "insufficient_fallback_missing": 0}
    for record in payload["case_records"]:
        if record["profile_name"] != profile:
            continue
        shadow = record.get("answer_post_check_shadow") or {}
        reasons = set(shadow.get("retry_reasons") or ())
        result["needs_retry"] += int(bool(shadow.get("needs_retry")))
        result["forbidden_boundary_included"] += int(
            "forbidden_boundary_included" in reasons
            or bool(shadow.get("included_forbidden_boundary_ids"))
        )
        result["missing_likely_relevant_context"] += int(
            "missing_likely_relevant_context" in reasons
            or bool(shadow.get("missing_likely_relevant_context_ids"))
        )
        result["stale_evidence_included"] += int(
            "stale_evidence_included" in reasons
            or bool(shadow.get("included_stale_warning_ids"))
        )
        result["conflict_evidence_included"] += int(
            "conflict_evidence_included" in reasons
            or bool(shadow.get("included_conflict_warning_ids"))
        )
        result["insufficient_fallback_missing"] += int(
            "insufficient_evidence_fallback_missing" in reasons
            or (
                bool(shadow.get("insufficient_evidence_fallback_expected"))
                and not bool(shadow.get("insufficient_evidence_fallback_observed"))
            )
        )
    return result
base = m["profile_summaries"]["chain_tri_governed_answer_contract"]
base_counts = counts("chain_tri_governed_answer_contract")
for profile, row in m["profile_summaries"].items():
    print(profile, row["answer_success_count"], row["case_count"], row["answer_rule_pass_rate"], row["memory_grounding_pass_rate"], row["forbidden_violation_rate"], row["avg_total_token_count"], counts(profile))
    assert float(row["answer_rule_pass_rate"]) >= float(base["answer_rule_pass_rate"]) - 5.0
    assert float(row["memory_grounding_pass_rate"]) == 100.0
    assert float(row["forbidden_violation_rate"]) <= float(base["forbidden_violation_rate"])
    assert float(row["avg_total_token_count"]) <= float(base["avg_total_token_count"]) * 1.10
    if profile != "chain_tri_governed_answer_contract":
        profile_counts = counts(profile)
        for key, value in profile_counts.items():
            assert value <= base_counts[key], (profile, key, base_counts, profile_counts)
print("gate ok")
PY
```

Expected: prints `gate ok`. If it fails, docs must state which gate failed and P6o-10 must remain eval-only failed evidence.

- [ ] **Step 4: Update docs and commit P6o-10 result**

Record exact P6o-10 data and commit:

```bash
git add my_md/memory_optimization/README.md \
  my_md/memory_optimization/02-memory-quality-metrics.md \
  my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md \
  my_md/memory_optimization/eval_reports/p6o10_rerank_version_governed_combo_small_online_v1/memory_comprehensive_online_eval.json \
  my_md/memory_optimization/eval_reports/p6o10_rerank_version_governed_combo_small_online_v1/memory_comprehensive_online_eval.md \
  task_plan.md progress.md
git commit -m "docs: record p6o10 rerank version governed combo"
```

---

### Task 6: Final Verification

**Files:**
- Modify: none unless docs need final correction.

**Interfaces:**
- Consumes all completed tasks.
- Produces final local branch state.

- [ ] **Step 1: Run full focused verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_answer_contract.py \
  tests/test_memory_comprehensive_online_eval.py \
  tests/test_memory_comprehensive_online_cli.py \
  -q -p no:cacheprovider
.venv/bin/python -m compileall -q memory2 scripts tests
git diff --check
git status --short --branch
```

Expected: pytest passes, compileall exits `0`, diff check exits `0`, and only expected committed state remains.

---

## Self-Review

**Spec coverage:** The plan covers P6o-8 safe boundary rendering, P6o-8 real verification, P6o-9 same-matrix comparison, and P6o-10 combo validation. It defines explicit stop gates between phases.

**Placeholder scan:** Executable tasks contain concrete commands, code snippets, expected results, and no deferred-work markers.

**Type consistency:** Profile names are exact: `chain_tri_version_governed_answer_contract`, `chain_tri_rerank_governed_answer_contract`, and `chain_tri_rerank_version_governed_answer_contract`. The combo helper is `rerank_version_governed_tri_trace_for_case(case: EvalCase) -> dict[str, object]`.

**Risk boundary:** This plan changes only eval harness behavior. It keeps raw ids available for post-check while removing raw forbidden boundary ids from model-visible prompt text. It does not activate production retry or production memory behavior.
