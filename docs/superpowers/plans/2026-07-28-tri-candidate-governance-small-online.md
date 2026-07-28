# Tri Candidate Governance Small Online Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add and run a bounded real LLM online evaluation that compares original memory baseline, current tri retrieval, and tri retrieval after candidate governance.

**Architecture:** Keep the change inside the evaluation harness. Add one eval-only profile that derives tri-retrieval evidence ids, applies candidate governance before evidence injection, and labels the result as an oracle-protected test-set upper-bound rather than production behavior. Do not change production AgentLoop, real memory writes, tool execution, production prompts, or the existing `retrieve()` contract.

**Tech Stack:** Python dataclasses / pure functions, `memory2/eval_comprehensive_online.py`, `memory2/retrieval_governance.py`, existing comprehensive online CLI, pytest, JSON/Markdown reports, real LLM gated by `--enable-real-llm`.

## Global Constraints

- Worktree: `/home/jjh/git_work/akashic-agent/.worktrees/memory-next`.
- Do not sync remote/main in this plan unless the user explicitly redirects.
- Do not push without explicit user instruction.
- Real LLM calls are allowed only in the final bounded online run, after fake-provider smoke and artifact integrity checks pass.
- Do not modify `AgentLoop`, `Reasoner`, `ToolExecutor`, `ToolRegistry`, production memory writes, production prompts, or production memory DB state.
- Keep the existing `retrieve()` return contract unchanged.
- The new governed tri profile must be eval-only and must be clearly labeled as using fixture expected ids for protected target preservation.
- Reports must not include raw prompt, raw session text, raw memory summary, full answers, API keys, or answer debug artifacts.
- Small online run target shape: `40` unique cases, common `20` + hard `20`, `3` profiles, `1` prompt variant, `1` repeat, total `120` completed real LLM calls.
- Required profiles for the small run:
  - `chain_memory_base`
  - `chain_tri_retrieval`
  - `chain_tri_candidate_governance`
- Primary metrics:
  - `answer_rule_pass_rate`
  - `memory_grounding_pass_rate`
  - `forbidden_violation_rate`
  - per-profile answer success count / rate
  - per-profile grounding success count / rate
  - per-profile forbidden count / rate
  - average total tokens
  - average latency
- Success gate for this small test:
  - infrastructure: zero provider errors, zero timeouts, zero excluded infra failures;
  - governed tri grounding should stay near current tri grounding;
  - governed tri forbidden rate should be lower than or equal to old tri retrieval;
  - governed tri answer rate should not materially drop versus old tri retrieval.

---

## File Structure

- Modify `memory2/eval_comprehensive_online.py`
  - Add eval-only profile `chain_tri_candidate_governance`.
  - Add helper to compute candidate-governed tri evidence ids by applying an oracle-protected strict filter to the existing tri fused ids while preserving fused order.
  - Add optional answer-quality table support for the new profile without making older reports appear partial.
  - Add JSON and Markdown report metadata that marks the profile as `eval_only`, `oracle_protected`, and `uses_fixture_expected_ids`.

- Modify `scripts/run_memory_comprehensive_online_eval.py`
  - Add balanced small case selection arguments so one run can select common `20` + hard `20`.
  - Preserve existing `--case-set` / `--limit` behavior for all existing callers.

- Modify `tests/test_memory_comprehensive_online_eval.py`
  - Add tests for governed tri evidence ids over the final common `20` + hard `20` selection.
  - Add tests that the optional profile appears in profile summaries and answer-quality rows when requested.
  - Add tests that older reports are not forced into a partial matrix just because the optional profile is absent.
  - Add tests that report metadata and Markdown explicitly label the profile as eval-only / oracle-protected.

- Modify `tests/test_memory_comprehensive_online_cli.py`
  - Add CLI tests for balanced common/hard case selection.
  - Add CLI fake-provider smoke test for the 3-profile small-run shape.

- Create report output after implementation:
  - `my_md/memory_optimization/eval_reports/tri_candidate_governance_small_online_v1/memory_comprehensive_online_eval.json`
  - `my_md/memory_optimization/eval_reports/tri_candidate_governance_small_online_v1/memory_comprehensive_online_eval.md`

- Modify documentation after the run:
  - `my_md/memory_optimization/README.md`
  - `my_md/memory_optimization/02-memory-quality-metrics.md`
  - `my_md/memory_optimization/03-memory-governance-design.md`
  - `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
  - `progress.md`
  - `task_plan.md`

---

### Task 1: Add Eval-Only Governed Tri Profile

**Files:**
- Modify: `memory2/eval_comprehensive_online.py`
- Modify: `tests/test_memory_comprehensive_online_eval.py`

**Interfaces:**
- Produces:
  - `TRI_CANDIDATE_GOVERNANCE_PROFILE = "chain_tri_candidate_governance"`
  - `OPTIONAL_ANSWER_QUALITY_PROFILES = ("chain_tri_candidate_governance",)`
  - `governed_tri_evidence_ids_for_case(case: EvalCase) -> tuple[str, ...]`
- Consumes:
  - `CandidateGovernancePolicy`
  - `apply_retrieval_route`
  - `build_retrieval_routing_decision`
  - `evidence_ids_for_profile(case, "chain_tri_retrieval")`

- [ ] **Step 1: Write failing test for governed tri evidence ids**

Append this test to `tests/test_memory_comprehensive_online_eval.py`:

```python
def test_governed_tri_profile_preserves_targets_and_drops_should_not_candidates() -> None:
    cases = (
        build_quantitative_eval_cases(case_set="common", limit=20, case_pack="standard")
        + build_quantitative_eval_cases(case_set="hard", limit=20, case_pack="standard")
    )
    cases_with_should_not_in_tri = 0

    for case in cases:
        tri_ids = list(evidence_ids_for_profile(case, "chain_tri_retrieval"))
        governed_ids = list(
            evidence_ids_for_profile(case, "chain_tri_candidate_governance")
        )
        expected_ids = {str(item) for item in case.expectations["should_recall_ids"]}
        should_not_ids = {
            str(item) for item in case.expectations["should_not_recall_ids"]
        }
        governed_set = set(governed_ids)

        assert expected_ids <= set(tri_ids)
        assert expected_ids <= governed_set
        assert not (governed_set & should_not_ids)
        assert len(governed_ids) == len(governed_set)
        assert governed_ids == [item_id for item_id in tri_ids if item_id in governed_set]
        if set(tri_ids) & should_not_ids:
            cases_with_should_not_in_tri += 1

    assert len(cases) == 40
    assert cases_with_should_not_in_tri > 0
```

- [ ] **Step 2: Run test and confirm RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py::test_governed_tri_profile_preserves_targets_and_drops_should_not_candidates -q -p no:cacheprovider
```

Expected: fails with `ValueError: unknown profile_name: chain_tri_candidate_governance`.

- [ ] **Step 3: Implement governed tri evidence helper**

In `memory2/eval_comprehensive_online.py`, add imports:

```python
from memory2.retrieval_governance import (
    CandidateGovernancePolicy,
    apply_retrieval_route,
    build_retrieval_routing_decision,
)
```

Add constants near `ANSWER_QUALITY_PROFILES`:

```python
TRI_CANDIDATE_GOVERNANCE_PROFILE = "chain_tri_candidate_governance"
OPTIONAL_ANSWER_QUALITY_PROFILES: tuple[str, ...] = (
    TRI_CANDIDATE_GOVERNANCE_PROFILE,
)
PROFILE_METADATA: dict[str, dict[str, object]] = {
    TRI_CANDIDATE_GOVERNANCE_PROFILE: {
        "eval_only": True,
        "oracle_protected": True,
        "uses_fixture_expected_ids": True,
        "description": (
            "Applies strict candidate governance to existing tri fused ids "
            "while protecting fixture should_recall_ids."
        ),
    }
}
```

Update `evidence_ids_for_profile()` before the `COMPREHENSIVE_CHAIN_PROFILES` validation:

```python
    if profile_name == TRI_CANDIDATE_GOVERNANCE_PROFILE:
        return governed_tri_evidence_ids_for_case(case)
```

Add helper functions near `evidence_ids_for_profile()`:

```python
def governed_tri_evidence_ids_for_case(case: EvalCase) -> tuple[str, ...]:
    tri_ids = tuple(_ids_from_trace(case, "tri_retrieval", "fused_ids"))
    if not tri_ids:
        return ()
    expected_ids = tuple(
        str(item) for item in case.expectations.get("should_recall_ids", ())
    )
    should_not_ids = {
        str(item) for item in case.expectations.get("should_not_recall_ids", ())
    }
    candidates = _ordered_candidates_for_governed_tri(case, tri_ids, should_not_ids)
    decision = build_retrieval_routing_decision(str(case.setup.get("query") or ""))
    decision = replace(
        decision,
        allowed_lanes=("semantic",),
        max_per_lane={"semantic": max(len(candidates), 1)},
        require_source_ref=False,
        require_scope_match=False,
        graph_enabled=False,
    )
    decision = decision.with_candidate_governance(
        CandidateGovernancePolicy(
            enabled=True,
            protected_expected_ids=expected_ids,
        )
    )
    governed, _trace = apply_retrieval_route(decision, {"semantic": candidates})
    return tuple(
        str(candidate.get("id") or candidate.get("memory_id") or "")
        for candidate in governed
        if candidate.get("id") or candidate.get("memory_id")
    )


def _ordered_candidates_for_governed_tri(
    case: EvalCase,
    tri_ids: tuple[str, ...],
    should_not_ids: set[str],
) -> list[dict[str, object]]:
    scope = dict(case.setup.get("scope") or {})
    by_id = {
        str(item.get("id") or item.get("memory_id") or ""): item
        for item in case.setup.get("memory_items", [])
        if isinstance(item, dict)
    }
    candidates: list[dict[str, object]] = []
    seen: set[str] = set()
    for item_id in tri_ids:
        if item_id in seen:
            continue
        seen.add(item_id)
        item = by_id.get(item_id)
        if item is None:
            continue
        candidate = dict(item)
        candidate["scope_match"] = (
            str(candidate.get("scope_channel") or "") == str(scope.get("channel") or "")
            and str(candidate.get("scope_chat_id") or "") == str(scope.get("chat_id") or "")
        )
        candidate["should_not_recall"] = item_id in should_not_ids
        candidates.append(candidate)
    return candidates
```

This helper intentionally runs as a strict filter over the already fused tri ids. It does not claim to re-run the original semantic / keyword / provenance lanes, and report metadata must label it as eval-only / oracle-protected.

- [ ] **Step 4: Add profile evidence source label**

Update `profile_evidence_source()`:

```python
        TRI_CANDIDATE_GOVERNANCE_PROFILE: (
            "tri_candidate_governance.protected_strict_ids"
        ),
```

- [ ] **Step 5: Run focused test and confirm GREEN**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py::test_governed_tri_profile_preserves_targets_and_drops_should_not_candidates -q -p no:cacheprovider
```

Expected: passes.

---

### Task 2: Keep Optional Profile Out Of Required Historical Matrix

**Files:**
- Modify: `memory2/eval_comprehensive_online.py`
- Modify: `tests/test_memory_comprehensive_online_eval.py`

**Interfaces:**
- Consumes:
  - `ANSWER_QUALITY_PROFILES`
  - `OPTIONAL_ANSWER_QUALITY_PROFILES`
- Produces:
  - optional rows for `chain_tri_candidate_governance` when the profile is present;
  - no forced `answer_quality_partial_matrix=True` for old reports that do not contain the optional profile.
  - `profile_metadata` JSON entry for `chain_tri_candidate_governance`;
  - Markdown sections that display optional profile rows and eval-only metadata.

- [ ] **Step 1: Write failing report test**

Append:

```python
def test_optional_tri_candidate_governance_profile_does_not_make_old_reports_partial(
    tmp_path: Path,
) -> None:
    cases = build_quantitative_eval_cases(limit=2, case_pack="standard")
    specs = build_comprehensive_run_specs(
        cases,
        repeats=1,
        prompt_variants=("baseline",),
        profiles=("chain_memory_base", "chain_tri_retrieval"),
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

    assert "chain_tri_candidate_governance" not in report.metrics[
        "answer_quality_missing_profiles"
    ]
    assert "chain_tri_candidate_governance" not in report.metrics["profile_metadata"]
```

- [ ] **Step 2: Write failing optional-row test**

Append:

```python
def test_optional_tri_candidate_governance_profile_gets_answer_quality_row(
    tmp_path: Path,
) -> None:
    cases = build_quantitative_eval_cases(limit=2, case_pack="standard")
    specs = build_comprehensive_run_specs(
        cases,
        repeats=1,
        prompt_variants=("baseline",),
        profiles=(
            "chain_memory_base",
            "chain_tri_retrieval",
            "chain_tri_candidate_governance",
        ),
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
    assert "chain_tri_candidate_governance" in rows
    assert rows["chain_tri_candidate_governance"]["case_count"] == 2
    metadata = report.metrics["profile_metadata"]["chain_tri_candidate_governance"]
    assert metadata["eval_only"] is True
    assert metadata["oracle_protected"] is True
    assert metadata["uses_fixture_expected_ids"] is True
```

- [ ] **Step 3: Write failing Markdown visibility test**

Append:

```python
def test_optional_tri_candidate_governance_profile_is_visible_in_markdown(
    tmp_path: Path,
) -> None:
    cases = build_quantitative_eval_cases(limit=2, case_pack="standard")
    specs = build_comprehensive_run_specs(
        cases,
        repeats=1,
        prompt_variants=("baseline",),
        profiles=(
            "chain_memory_base",
            "chain_tri_retrieval",
            "chain_tri_candidate_governance",
        ),
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
    markdown_path = tmp_path / "report.md"

    write_comprehensive_online_markdown(report, markdown_path)

    markdown = markdown_path.read_text(encoding="utf-8")
    assert "chain_tri_candidate_governance" in markdown
    assert "eval_only" in markdown
    assert "oracle_protected" in markdown
```

- [ ] **Step 4: Run tests and confirm RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_comprehensive_online_eval.py::test_optional_tri_candidate_governance_profile_does_not_make_old_reports_partial \
  tests/test_memory_comprehensive_online_eval.py::test_optional_tri_candidate_governance_profile_gets_answer_quality_row \
  tests/test_memory_comprehensive_online_eval.py::test_optional_tri_candidate_governance_profile_is_visible_in_markdown \
  -q -p no:cacheprovider
```

Expected: optional profile is either rejected or absent from answer-quality rows.

- [ ] **Step 5: Implement optional profile support**

Update `_profiles_in_order()` so optional profiles can be ordered after built-in chain profiles:

```python
def _profiles_in_order(results: tuple[ComprehensiveCaseResult, ...]) -> tuple[str, ...]:
    seen = {result.profile_name for result in results}
    ordered = tuple(profile for profile in COMPREHENSIVE_CHAIN_PROFILES if profile in seen)
    optional = tuple(profile for profile in OPTIONAL_ANSWER_QUALITY_PROFILES if profile in seen)
    unknown = tuple(
        profile
        for profile in sorted(seen)
        if profile not in set(ordered) and profile not in set(optional)
    )
    return (*ordered, *optional, *unknown)
```

Update `build_comprehensive_run_specs()` profile validation:

```python
    allowed_profiles = set(COMPREHENSIVE_CHAIN_PROFILES) | set(
        OPTIONAL_ANSWER_QUALITY_PROFILES
    )
    invalid_profiles = [profile for profile in profiles if profile not in allowed_profiles]
```

Update answer-quality row builders to include optional profiles when present:

```python
def _answer_quality_profiles_for_report(
    profile_summaries: dict[str, dict[str, object]],
) -> tuple[str, ...]:
    optional = tuple(
        profile
        for profile in OPTIONAL_ANSWER_QUALITY_PROFILES
        if profile in profile_summaries
    )
    return (*ANSWER_QUALITY_PROFILES, *optional)
```

Use `_answer_quality_profiles_for_report(profile_summaries)` when building JSON rows and Markdown tables. Keep `answer_quality_required_profiles` equal to `ANSWER_QUALITY_PROFILES`, not the optional profile list.

Add profile metadata to `_metrics_from_results()`:

```python
    profile_metadata = {
        profile: dict(PROFILE_METADATA[profile])
        for profile in profiles
        if profile in PROFILE_METADATA
    }
```

Then include it in the returned metrics:

```python
        "profile_metadata": profile_metadata,
```

In `_empty_metrics()`, add:

```python
        "profile_metadata": {},
```

Update Markdown rendering:

- the profile summary table should iterate over `_profiles_for_markdown(metrics)`, not only `COMPREHENSIVE_CHAIN_PROFILES`;
- answer quality and cost tables should iterate over `_answer_quality_profiles_for_report(profile_summaries)`;
- add an "Eval-Only Profile Metadata" section if `metrics["profile_metadata"]` is non-empty.

Add helpers:

```python
def _profiles_for_markdown(metrics: dict[str, object]) -> tuple[str, ...]:
    summaries = metrics.get("profile_summaries", {})
    if not isinstance(summaries, dict):
        return ()
    ordered = tuple(
        profile for profile in COMPREHENSIVE_CHAIN_PROFILES if profile in summaries
    )
    optional = tuple(
        profile for profile in OPTIONAL_ANSWER_QUALITY_PROFILES if profile in summaries
    )
    return (*ordered, *optional)
```

For the metadata Markdown section, render a compact table:

```markdown
| profile | eval_only | oracle_protected | uses_fixture_expected_ids |
| --- | ---: | ---: | ---: |
```

- [ ] **Step 6: Run focused tests and confirm GREEN**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py -q -p no:cacheprovider
```

Expected: all comprehensive online eval tests pass.

---

### Task 3: Add Balanced Small Case Selection To CLI

**Files:**
- Modify: `scripts/run_memory_comprehensive_online_eval.py`
- Modify: `tests/test_memory_comprehensive_online_cli.py`

**Interfaces:**
- Produces CLI args:
  - `--balanced-small`
  - `--common-limit`
  - `--hard-limit`
- Behavior:
  - if `--balanced-small` is false, preserve existing `--case-set` + `--limit`;
  - if `--balanced-small` is true, build common and hard case slices separately and concatenate them.
  - reject negative `--common-limit` or `--hard-limit`.

- [ ] **Step 1: Write failing CLI test for balanced selection**

Append to `tests/test_memory_comprehensive_online_cli.py`:

```python
def test_comprehensive_online_cli_balanced_small_selects_common_and_hard(tmp_path: Path) -> None:
    output_dir = tmp_path / "reports"
    workspace = tmp_path / "workspace"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_comprehensive_online_eval.py",
            "--workspace",
            str(workspace),
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
            "chain_memory_base,chain_tri_retrieval,chain_tri_candidate_governance",
            "--prompt-variants",
            "baseline",
            "--repeats",
            "1",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        (output_dir / "memory_comprehensive_online_eval.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["metrics"]["unique_case_count"] == 4
    assert payload["metrics"]["profile_count"] == 3
    assert payload["metrics"]["case_count"] == 12
    ids = {row["case_id"] for row in payload["case_records"]}
    assert any(case_id.startswith("common_") for case_id in ids)
    assert any(case_id.startswith("hard_") for case_id in ids)
```

- [ ] **Step 2: Run test and confirm RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_comprehensive_online_cli.py::test_comprehensive_online_cli_balanced_small_selects_common_and_hard -q -p no:cacheprovider
```

Expected: CLI rejects `--balanced-small`.

- [ ] **Step 3: Write failing CLI validation test**

Append:

```python
def test_comprehensive_online_cli_balanced_small_rejects_negative_limits(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_comprehensive_online_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(tmp_path / "reports"),
            "--fake-provider",
            "--balanced-small",
            "--common-limit",
            "-1",
            "--hard-limit",
            "2",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "common-limit and hard-limit must be non-negative" in completed.stderr
```

- [ ] **Step 4: Implement CLI args**

In `scripts/run_memory_comprehensive_online_eval.py`, add parser args:

```python
    parser.add_argument("--balanced-small", action="store_true")
    parser.add_argument("--common-limit", type=int, default=20)
    parser.add_argument("--hard-limit", type=int, default=20)
```

After `args = parser.parse_args()`, add:

```python
    if int(args.common_limit) < 0 or int(args.hard_limit) < 0:
        parser.error("common-limit and hard-limit must be non-negative")
```

Replace the existing case-building block with:

```python
            if bool(args.balanced_small):
                common_cases = build_quantitative_eval_cases(
                    case_set="common",
                    limit=int(args.common_limit),
                    case_pack=str(args.case_pack),
                )
                hard_cases = build_quantitative_eval_cases(
                    case_set="hard",
                    limit=int(args.hard_limit),
                    case_pack=str(args.case_pack),
                )
                cases = [*common_cases, *hard_cases]
            else:
                cases = build_quantitative_eval_cases(
                    case_set=str(args.case_set),
                    limit=int(args.limit),
                    case_pack=str(args.case_pack),
                )
```

- [ ] **Step 5: Run CLI focused tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_comprehensive_online_cli.py -q -p no:cacheprovider
```

Expected: all comprehensive online CLI tests pass.

---

### Task 4: Fake-Provider Smoke And Report Integrity Gate

**Files:**
- No code changes expected unless Task 1-3 tests reveal a defect.
- May create temporary report under `/tmp/akashic-memory-tri-governance-small-fake`.

- [ ] **Step 1: Run fake-provider small matrix**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-tri-governance-small-fake/workspace \
  --out-dir /tmp/akashic-memory-tri-governance-small-fake/reports \
  --fake-provider \
  --case-pack standard \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --profiles chain_memory_base,chain_tri_retrieval,chain_tri_candidate_governance \
  --prompt-variants baseline \
  --repeats 1 \
  --concurrency 1 \
  --real-memory-workspace /tmp/akashic-memory-tri-governance-small-fake/empty-real-memory-workspace
```

Expected:

- exit code `0`;
- `case_count = 120`;
- `unique_case_count = 40`;
- `profile_count = 3`;
- `real_llm_enabled = False`.

- [ ] **Step 2: Validate fake report shape**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path
path = Path("/tmp/akashic-memory-tri-governance-small-fake/reports/memory_comprehensive_online_eval.json")
data = json.loads(path.read_text(encoding="utf-8"))
metrics = data["metrics"]
assert metrics["case_count"] == 120
assert metrics["unique_case_count"] == 40
assert metrics["profile_count"] == 3
assert metrics["real_llm_enabled"] is False
assert metrics["provider_error_count"] == 0
assert metrics["timeout_count"] == 0
assert "chain_tri_candidate_governance" in metrics["profile_summaries"]
assert "chain_tri_candidate_governance" in metrics["profile_answer_quality_uplift_vs_memory_base"]
assert metrics["profile_metadata"]["chain_tri_candidate_governance"]["eval_only"] is True
assert metrics["profile_metadata"]["chain_tri_candidate_governance"]["oracle_protected"] is True
text = path.read_text(encoding="utf-8")
for forbidden in ("raw_prompt", "full_answer", "session_text", "api_key"):
    assert forbidden not in text
print("fake tri governance small report ok")
PY
```

Expected: prints `fake tri governance small report ok`.

---

### Task 5: Run Bounded Real LLM Small Online Test

**Files:**
- Create report outputs:
  - `my_md/memory_optimization/eval_reports/tri_candidate_governance_small_online_v1/memory_comprehensive_online_eval.json`
  - `my_md/memory_optimization/eval_reports/tri_candidate_governance_small_online_v1/memory_comprehensive_online_eval.md`

- [ ] **Step 1: Run real LLM matrix with checkpoint**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-tri-governance-small-online/workspace \
  --out-dir my_md/memory_optimization/eval_reports/tri_candidate_governance_small_online_v1 \
  --config config.toml \
  --enable-real-llm \
  --case-pack standard \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --profiles chain_memory_base,chain_tri_retrieval,chain_tri_candidate_governance \
  --prompt-variants baseline \
  --repeats 1 \
  --concurrency 1 \
  --timeout-s 60 \
  --real-memory-workspace /tmp/akashic-memory-tri-governance-small-online/empty-real-memory-workspace \
  --checkpoint-jsonl /tmp/akashic-memory-tri-governance-small-online/reports/memory_comprehensive_online_eval.checkpoint.jsonl \
  --resume
```

Expected:

- exit code `0`;
- `case_count = 120`;
- `unique_case_count = 40`;
- `completed_call_count = 120`;
- `provider_error_count = 0`;
- `timeout_count = 0`;
- `excluded_infra_failure_count = 0`.

- [ ] **Step 2: Validate real report integrity**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path
path = Path("my_md/memory_optimization/eval_reports/tri_candidate_governance_small_online_v1/memory_comprehensive_online_eval.json")
data = json.loads(path.read_text(encoding="utf-8"))
metrics = data["metrics"]
assert metrics["real_llm_enabled"] is True
assert metrics["case_count"] == 120
assert metrics["unique_case_count"] == 40
assert metrics["profile_count"] == 3
assert metrics["provider_error_count"] == 0
assert metrics["timeout_count"] == 0
assert metrics.get("excluded_infra_failure_count", 0) == 0
for profile in ("chain_memory_base", "chain_tri_retrieval", "chain_tri_candidate_governance"):
    assert profile in metrics["profile_summaries"]
    assert metrics["profile_summaries"][profile]["case_count"] == 40
print(json.dumps(metrics["profile_summaries"], ensure_ascii=False, indent=2))
PY
```

Expected: prints all three profile summaries.

- [ ] **Step 3: Compare governed tri against old tri**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path
path = Path("my_md/memory_optimization/eval_reports/tri_candidate_governance_small_online_v1/memory_comprehensive_online_eval.json")
metrics = json.loads(path.read_text(encoding="utf-8"))["metrics"]
profiles = metrics["profile_summaries"]
base = profiles["chain_memory_base"]
tri = profiles["chain_tri_retrieval"]
gov = profiles["chain_tri_candidate_governance"]
def row(name, data):
    return {
        "profile": name,
        "answer": f'{data["answer_success_count"]}/{data["case_count"]}',
        "answer_rate": data["answer_rule_pass_rate"],
        "grounding_rate": data["memory_grounding_pass_rate"],
        "forbidden_rate": data["forbidden_violation_rate"],
        "avg_tokens": data["avg_total_token_count"],
        "avg_latency_ms": data["avg_latency_ms"],
    }
print(json.dumps([row("base", base), row("tri", tri), row("governed_tri", gov)], ensure_ascii=False, indent=2))
print("governed_forbidden_delta_vs_tri", round(float(gov["forbidden_violation_rate"]) - float(tri["forbidden_violation_rate"]), 4))
print("governed_answer_delta_vs_tri", round(float(gov["answer_rule_pass_rate"]) - float(tri["answer_rule_pass_rate"]), 4))
print("governed_grounding_delta_vs_tri", round(float(gov["memory_grounding_pass_rate"]) - float(tri["memory_grounding_pass_rate"]), 4))
PY
```

Expected:

- a three-row JSON summary;
- deltas for forbidden, answer, and grounding.

---

### Task 6: Update Docs And Commit

**Files:**
- Modify:
  - `my_md/memory_optimization/README.md`
  - `my_md/memory_optimization/02-memory-quality-metrics.md`
  - `my_md/memory_optimization/03-memory-governance-design.md`
  - `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
  - `progress.md`
  - `task_plan.md`

- [ ] **Step 1: Document run parameters**

Record:

- case pack;
- common/hard split;
- profiles;
- prompt variants;
- repeats;
- real LLM enabled;
- provider errors / timeouts;
- token and latency totals;
- checkpoint path.

- [ ] **Step 2: Document the three-profile result table**

Use this table shape:

```markdown
| profile | answer_success | answer_rate | grounding_rate | forbidden_rate | avg_tokens | avg_latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `chain_memory_base` | `x/40` | `x%` | `x%` | `x%` | `x` | `x` |
| `chain_tri_retrieval` | `x/40` | `x%` | `x%` | `x%` | `x` | `x` |
| `chain_tri_candidate_governance` | `x/40` | `x%` | `x%` | `x%` | `x` | `x` |
```

- [ ] **Step 3: Document interpretation boundaries**

State explicitly:

- this is a controlled 40-case small online run, not production natural traffic;
- `chain_tri_candidate_governance` is eval-only and oracle-protected;
- if forbidden drops but answer rate does not improve, next work is evidence injection and answer constraints;
- if grounding drops, next work is candidate governance false-positive tuning;
- if answer and forbidden both improve, expand to a larger rerun.

- [ ] **Step 4: Run final verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_comprehensive_online_eval.py \
  tests/test_memory_comprehensive_online_cli.py \
  tests/test_memory_retrieval_governance.py \
  tests/test_memory_tri_candidate_governance.py \
  -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m compileall -q memory2 scripts tests
git diff --check
```

Expected:

- pytest passes;
- compileall exit `0`;
- diff check exit `0`.

- [ ] **Step 5: Commit locally**

Run:

```bash
git add memory2/eval_comprehensive_online.py \
  scripts/run_memory_comprehensive_online_eval.py \
  tests/test_memory_comprehensive_online_eval.py \
  tests/test_memory_comprehensive_online_cli.py \
  my_md/memory_optimization/README.md \
  my_md/memory_optimization/02-memory-quality-metrics.md \
  my_md/memory_optimization/03-memory-governance-design.md \
  my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md \
  my_md/memory_optimization/eval_reports/tri_candidate_governance_small_online_v1/ \
  progress.md task_plan.md
git add -f docs/superpowers/plans/2026-07-28-tri-candidate-governance-small-online.md
git commit -m "test: add tri candidate governance small online eval"
```

Expected: local commit created, no push.

---

## Self-Review

Spec coverage:

- Records a bounded real LLM small test plan: Task 5.
- Adds the missing governed tri profile: Task 1.
- Avoids corrupting historical answer-quality matrix requirements: Task 2.
- Ensures balanced common/hard 40-case selection: Task 3.
- Requires fake-provider smoke before real LLM calls: Task 4.
- Records docs, verification, and commit: Task 6.

Placeholder scan:

- No `TBD`, `TODO`, or unspecified implementation steps.
- Commands and expected outputs are concrete.

Type consistency:

- `chain_tri_candidate_governance` is introduced as an optional eval-only profile.
- `governed_tri_evidence_ids_for_case(case: EvalCase) -> tuple[str, ...]` is used consistently.
- Existing production chain profiles remain unchanged.

## Execution Notes

Executed on `2026-07-28` in worktree `/home/jjh/git_work/akashic-agent/.worktrees/memory-next`.

Completed implementation:

- Added optional eval-only profile `chain_tri_candidate_governance`.
- Added optional profile metadata to JSON and Markdown reports.
- Added balanced small CLI selection with `--balanced-small`, `--common-limit`, and `--hard-limit`.
- Ran fake-provider smoke before real LLM.
- Ran bounded real LLM small matrix.

Fake-provider smoke result:

- `case_count = 120`
- `unique_case_count = 40`
- `profile_count = 3`
- `provider_error_count = 0`
- `timeout_count = 0`

Real LLM small online result:

- report dir: `my_md/memory_optimization/eval_reports/tri_candidate_governance_small_online_v1`
- checkpoint: `/tmp/akashic-memory-tri-governance-small-online/reports/memory_comprehensive_online_eval.checkpoint.jsonl`
- `case_count = 120`
- `unique_case_count = 40`
- `completed_call_count = 120`
- `provider_error_count = 0`
- `timeout_count = 0`
- `total_token_count = 655992`
- `avg_latency_ms = 4565.5`

| profile | answer_success | answer_rate | grounding_rate | forbidden_rate | avg_tokens | avg_latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `chain_memory_base` | `20/40` | `50.0%` | `100.0%` | `10.0%` | `5486.7` | `4785.5` |
| `chain_tri_retrieval` | `22/40` | `55.0%` | `100.0%` | `15.0%` | `5529.875` | `4922.225` |
| `chain_tri_candidate_governance` | `17/40` | `42.5%` | `100.0%` | `0.0%` | `5383.225` | `3988.775` |

Gate result:

- Infrastructure gate passed.
- Forbidden-control goal passed: governed tri reduced forbidden from `15.0%` to `0.0%`.
- Answer-quality gate failed: governed tri dropped answer rate from `55.0%` to `42.5%`.
- Grounding stayed `100.0%`, so the next bottleneck is answer use of evidence, not target recall.
