# Memory P6o7 Version Boundary Governed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add and validate an eval-only `chain_tri_version_governed_answer_contract` profile that tests version-boundary evidence fields as governed-contract inputs without expanding recall.

**Architecture:** Reuse `chain_tri_governed_answer_contract` as the baseline candidate and add only one signal layer: version-boundary metadata. The new profile keeps the governed tri allowed-evidence id set unchanged, enriches the production-safe evidence contract with active-version, stale, superseded, conflict, and insufficient-evidence boundary fields derived from existing `version_chain_shadow` and memory item metadata, then compares it against the governed baseline in a bounded real LLM matrix. Production `AgentLoop`, memory writes, default prompt behavior, `plugins/default_memory/engine.py`, and old retriever contracts remain unchanged.

**Tech Stack:** Current `.venv` on Python `>=3.12`, pytest, existing `memory2.eval_comprehensive_online`, existing `memory2.eval_answer_contract`, existing `memory2.version_chain_experiments`, existing `scripts/run_memory_comprehensive_online_eval.py`, JSON/Markdown eval reports, checkpoint JSONL under `/tmp`.

## Global Constraints

- Worktree: `/home/jjh/git_work/akashic-agent/.worktrees/memory-next`.
- Do not sync remote/main in this plan unless the user explicitly redirects.
- Do not push without explicit user instruction.
- Do not modify production `AgentLoop`, `Reasoner`, `ToolExecutor`, `ToolRegistry`, production memory writes, production prompts, `plugins/default_memory/engine.py`, or the old `Retriever.retrieve()` return contract.
- This plan tests only `tri governed` vs `tri + version-boundary governed`; do not add rerank, graph, retry, or production activation.
- The new profile is eval-only and oracle-protected because it reuses P6o-2 protected candidate governance; label this clearly in metadata and docs.
- The new profile must not introduce ids outside `chain_tri_governed_answer_contract` allowed evidence. Version boundary fields may mark stale/superseded/conflict ids, but allowed evidence must stay exactly the governed tri id set.
- Real LLM calls are allowed only after focused tests and fake-provider smoke pass.
- Real LLM matrix for this slice is bounded: common `20` + hard `20`, profiles `chain_tri_governed_answer_contract,chain_tri_version_governed_answer_contract`, prompt variant `baseline`, repeat `1`, expected `80` completed calls.
- Store live checkpoint JSONL under `/tmp/akashic-memory-p6o7-version-boundary-governed/`, not in git-tracked docs.
- Do not write raw prompt, raw query, raw session text, raw memory summaries, full answers, answer debug artifacts, or API keys into committed report/docs.
- Success gate:
  - focused CLI fake smoke: common `2` + hard `2`, `case_count = 8`, `unique_case_count = 4`, `profile_count = 2`, `provider_error_count = 0`, `timeout_count = 0`;
  - full fake pre-real gate: common `20` + hard `20`, `case_count = 80`, `unique_case_count = 40`, `profile_count = 2`, `provider_error_count = 0`, `timeout_count = 0`;
  - real matrix, if run: common `20` + hard `20`, `case_count = 80`, `unique_case_count = 40`, `profile_count = 2`, `provider_error_count = 0`, `timeout_count = 0`, `excluded_infra_failure_count = 0`;
  - version-governed answer rate may not fall more than `5.0` points below `chain_tri_governed_answer_contract`;
  - version-governed grounding must remain `100.0%`;
  - version-governed forbidden rate must be less than or equal to the governed baseline forbidden rate;
  - version-governed avg tokens must not exceed governed baseline avg tokens by more than `10.0%`;
  - post-check risk counts should not rise above the governed baseline; if stale/conflict boundary counts rise because the profile exposes additional warnings, docs must explain whether those are warning fields, not included-context failures.

---

## File Structure

- Modify `memory2/eval_answer_contract.py`
  - Add a `VersionBoundaryInfo` dataclass.
  - Add helper `build_version_boundary_info(case: EvalCase, governed_trace_info: object) -> VersionBoundaryInfo`.
  - Let `build_production_governed_tri_evidence_contract()` accept optional `version_boundary_info`.
  - Merge version boundary ids into `active_version`, `stale_warning`, `conflict_warning`, `forbidden_boundary`, and `insufficient_evidence_fallback` fields without adding allowed evidence ids.
  - Enforce hard disjointness: `allowed_evidence_ids` and `active_version_ids` must not overlap `forbidden_boundary_ids`.
- Modify `memory2/eval_comprehensive_online.py`
  - Register `chain_tri_version_governed_answer_contract`.
  - Add helper `version_governed_tri_trace_for_case(case: EvalCase) -> dict[str, object]`.
  - Route the new profile through production-safe evidence contract rendering and post-check shadow.
  - Extend profile metadata and evidence-source reporting.
- Modify `tests/test_memory_answer_contract.py`
  - Cover version-boundary contract field merging and no fixture answer-term usage.
- Modify `tests/test_memory_comprehensive_online_eval.py`
  - Cover profile registration, no recall expansion, version boundary raw metadata, contract block, scoring expectation, and post-check shadow.
- Modify `tests/test_memory_comprehensive_online_cli.py`
  - Add a scaled fake-provider CLI matrix regression for the two-profile P6o-7 slice.
- Create execution report, only after real LLM gate passes:
  - `my_md/memory_optimization/eval_reports/p6o7_version_boundary_governed_small_online_v1/memory_comprehensive_online_eval.json`
  - `my_md/memory_optimization/eval_reports/p6o7_version_boundary_governed_small_online_v1/memory_comprehensive_online_eval.md`
- Modify docs after fake or real execution:
  - `my_md/memory_optimization/README.md`
  - `my_md/memory_optimization/02-memory-quality-metrics.md`
  - `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
  - `task_plan.md`
  - `progress.md`

---

### Task 0: Confirm P6o-6 Data Is Recorded

**Files:**
- Modify: none

**Interfaces:**
- Consumes: committed P6o-6 report and docs.
- Produces: verified baseline for version-boundary planning.

- [ ] **Step 1: Confirm clean linked worktree and recent commits**

Run:

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
BRANCH=$(git branch --show-current)
printf 'GIT_DIR=%s\nGIT_COMMON=%s\nBRANCH=%s\n' "$GIT_DIR" "$GIT_COMMON" "$BRANCH"
git status --short --branch
git log --oneline -6
```

Expected:

```text
BRANCH=memory-next
18ac5ed docs: record p6o6 governed rerank signal
b6f6529 test: cover p6o6 governed rerank online matrix
f4a9dc9 feat: add rerank governed answer contract eval profile
85dfcd9 feat: allow governed evidence contract profile name
```

- [ ] **Step 2: Confirm P6o-6 data appears in docs**

Run:

```bash
rg -n "Phase 6o6|p6o6_governed_rerank|chain_tri_rerank_governed_answer_contract|40/40|0.77" \
  my_md/memory_optimization/README.md \
  my_md/memory_optimization/02-memory-quality-metrics.md \
  my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md \
  task_plan.md \
  progress.md
```

Expected: matches in all five files.

---

### Task 1: Add Version Boundary Contract Fields

**Files:**
- Modify: `tests/test_memory_answer_contract.py`
- Modify: `memory2/eval_answer_contract.py`

**Interfaces:**
- Consumes:
  - `build_production_governed_tri_evidence_contract(case, governed_trace_info, profile_name=...) -> ProductionEvidenceContract`
  - `render_production_evidence_contract_block(contract) -> str`
- Produces:
  - `VersionBoundaryInfo`
  - `build_version_boundary_info(case: EvalCase, governed_trace_info: object) -> VersionBoundaryInfo`
  - `build_production_governed_tri_evidence_contract(..., version_boundary_info: VersionBoundaryInfo | None = None)`

- [ ] **Step 1: Write failing version-boundary contract test**

Append this test to `tests/test_memory_answer_contract.py`:

```python
def test_production_governed_contract_merges_version_boundary_fields() -> None:
    case = _case_with_should_not_in_tri()
    governed_trace_info = {
        "ids": ("target", "weak"),
        "trace": {
            "candidate_governance_mode": "tiered",
            "candidate_risk_tiers": [
                {"candidate_id": "target", "tier": "allow", "risks": (), "lane": "semantic"},
                {"candidate_id": "weak", "tier": "downgrade", "risks": ("weak_source_ref",), "lane": "semantic"},
            ],
        },
    }
    case = replace(
        case,
        setup={
            **case.setup,
            "memory_items": [
                {
                    "id": "target",
                    "summary": "active target evidence",
                    "status": "active",
                    "source_ref": "telegram:1:1",
                },
                {
                    "id": "weak",
                    "summary": "weak source evidence",
                    "status": "active",
                    "source_ref": "session:telegram:1",
                },
                {
                    "id": "old",
                    "summary": "old superseded evidence",
                    "status": "superseded",
                    "source_ref": "telegram:1:0",
                },
                {
                    "id": "conflict",
                    "summary": "conflicting active evidence",
                    "status": "active",
                    "source_ref": "telegram:1:2",
                },
            ],
            "memory_replacements": [
                {
                    "old_item_id": "old",
                    "new_item_id": "target",
                    "old_summary": "old superseded evidence",
                    "new_summary": "active target evidence",
                    "old_source_ref": "telegram:1:0",
                    "new_source_ref": "telegram:1:1",
                },
                {
                    "old_item_id": "old",
                    "new_item_id": "conflict",
                    "old_summary": "old superseded evidence",
                    "new_summary": "conflicting active evidence",
                    "old_source_ref": "telegram:1:0",
                    "new_source_ref": "telegram:1:2",
                },
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

    assert contract.profile_name == "chain_tri_version_governed_answer_contract"
    assert contract.allowed_evidence_ids == ("target", "weak")
    assert set(contract.active_version_ids) == {"target"}
    assert "old" in contract.forbidden_boundary_ids
    assert "conflict" in contract.conflict_warning_ids
    assert "target" not in contract.forbidden_boundary_ids
    assert "conflict" not in contract.allowed_evidence_ids
    assert set(contract.allowed_evidence_ids).isdisjoint(contract.forbidden_boundary_ids)
    assert set(contract.active_version_ids).isdisjoint(contract.forbidden_boundary_ids)
    assert contract.uses_fixture_answer_expectations is False
    assert contract.required_terms == ()
    assert "active_version_ids: target" in text
    assert "forbidden_boundary_ids: old" in text
```

Update the import list in `tests/test_memory_answer_contract.py` to include:

```python
build_version_boundary_info,
```

- [ ] **Step 2: Run the RED test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_answer_contract.py::test_production_governed_contract_merges_version_boundary_fields -q -p no:cacheprovider
```

Expected: FAIL because `build_version_boundary_info` and `version_boundary_info` are not implemented.

- [ ] **Step 3: Implement version boundary dataclass and builder**

In `memory2/eval_answer_contract.py`, add imports:

```python
from memory2.version_chain_experiments import build_version_chain_shadow_result
```

Add dataclass after `ProductionEvidenceContract`:

```python
@dataclass(frozen=True)
class VersionBoundaryInfo:
    active_version_ids: tuple[str, ...]
    stale_warning_ids: tuple[str, ...]
    conflict_warning_ids: tuple[str, ...]
    forbidden_boundary_ids: tuple[str, ...]
    rollback_candidate_ids: tuple[str, ...]
    conflict_chain_count: int
    stale_recalled_count: int
    superseded_recalled_count: int
```

Add builder:

```python
def build_version_boundary_info(
    case: EvalCase,
    governed_trace_info: object,
) -> VersionBoundaryInfo:
    trace_info = (
        dict(governed_trace_info) if isinstance(governed_trace_info, Mapping) else {}
    )
    governed_ids = set(_string_tuple(trace_info.get("ids", ())))
    memory_items = [
        dict(item)
        for item in case.setup.get("memory_items", ())
        if isinstance(item, Mapping)
    ]
    replacements = [
        dict(item)
        for item in case.setup.get("memory_replacements", ())
        if isinstance(item, Mapping)
    ]
    recalled_items = [
        item
        for item in memory_items
        if str(item.get("id") or item.get("memory_id") or "") in governed_ids
    ]
    result = build_version_chain_shadow_result(
        memory_items=memory_items,
        replacements=replacements,
        recalled_items=recalled_items,
    )
    experimental = result.experimental_result
    metrics = result.metrics
    active_ids = tuple(
        item_id
        for item_id in _string_tuple(experimental.get("active_leaf_ids", ()))
        if item_id in governed_ids
    )
    stale_ids = _string_tuple(experimental.get("stale_recalled_ids", ()))
    governed_predecessor_ids = {
        str(replacement.get("old_item_id") or "")
        for replacement in replacements
        if str(replacement.get("new_item_id") or "") in set(active_ids)
    }
    rollback_ids = tuple(
        item_id
        for item_id in _string_tuple(experimental.get("rollback_candidate_ids", ()))
        if item_id in governed_predecessor_ids
        and item_id not in governed_ids
        and item_id not in active_ids
    )
    conflict_ids = _conflict_warning_ids_from_shadow_result(experimental, governed_ids)
    forbidden_ids = tuple(
        item_id
        for item_id in _dedupe_ids((*rollback_ids,))
        if item_id not in governed_ids and item_id not in active_ids
    )
    return VersionBoundaryInfo(
        active_version_ids=active_ids,
        stale_warning_ids=stale_ids,
        conflict_warning_ids=conflict_ids,
        forbidden_boundary_ids=forbidden_ids,
        rollback_candidate_ids=rollback_ids,
        conflict_chain_count=int(metrics.get("conflict_chain_count", 0) or 0),
        stale_recalled_count=int(metrics.get("stale_recalled_count", 0) or 0),
        superseded_recalled_count=int(metrics.get("superseded_recalled_count", 0) or 0),
    )
```

Add helpers near `_string_tuple()`:

```python
def _conflict_warning_ids_from_shadow_result(
    experimental: Mapping[str, object],
    governed_ids: set[str],
) -> tuple[str, ...]:
    active_ids = set(_string_tuple(experimental.get("active_leaf_ids", ())))
    chains = experimental.get("chains", ())
    if not isinstance(chains, (list, tuple)):
        return ()
    result: list[str] = []
    for chain in chains:
        chain_ids = _string_tuple(chain)
        if not (set(chain_ids) & governed_ids):
            continue
        active_in_chain = [item_id for item_id in chain_ids if item_id in active_ids]
        if len(active_in_chain) <= 1:
            continue
        result.extend(active_in_chain)
    return _dedupe_ids(tuple(result))


def _dedupe_ids(ids: tuple[str, ...]) -> tuple[str, ...]:
    result: list[str] = []
    for item_id in ids:
        if item_id and item_id not in result:
            result.append(item_id)
    return tuple(result)
```

- [ ] **Step 4: Merge version boundary into production-safe contract**

Change `build_production_governed_tri_evidence_contract()` signature:

```python
def build_production_governed_tri_evidence_contract(
    case: EvalCase,
    governed_trace_info: object,
    *,
    profile_name: str = GOVERNED_TRI_ANSWER_CONTRACT_PROFILE,
    version_boundary_info: VersionBoundaryInfo | None = None,
) -> ProductionEvidenceContract:
```

After computing base ids, add:

```python
version_active_ids = (
    version_boundary_info.active_version_ids if version_boundary_info else ()
)
version_stale_ids = (
    version_boundary_info.stale_warning_ids if version_boundary_info else ()
)
version_conflict_ids = (
    version_boundary_info.conflict_warning_ids if version_boundary_info else ()
)
version_forbidden_ids = (
    version_boundary_info.forbidden_boundary_ids if version_boundary_info else ()
)
```

Replace final id assignments with deduped merged ids:

```python
merged_conflict_warning_ids = _dedupe_ids((*conflict_warning_ids, *version_conflict_ids))
merged_stale_warning_ids = _dedupe_ids((*stale_warning_ids, *version_stale_ids))
merged_forbidden_boundary_ids = _dedupe_ids((*forbidden_boundary_ids, *version_forbidden_ids))
merged_forbidden_boundary_ids = tuple(
    item_id
    for item_id in merged_forbidden_boundary_ids
    if item_id not in allowed_ids
)
merged_active_version_ids = _dedupe_ids(
    tuple(item_id for item_id in (*active_version_ids, *version_active_ids) if item_id in allowed_ids)
)
merged_active_version_ids = tuple(
    item_id
    for item_id in merged_active_version_ids
    if item_id not in merged_forbidden_boundary_ids
)
```

Use these merged variables for `stale_warning`, `conflict_warning`, `active_version`, `forbidden_boundary`, and corresponding `*_ids` fields. Keep `allowed_evidence_ids=allowed_ids` unchanged.

- [ ] **Step 5: Run GREEN focused contract test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_answer_contract.py::test_production_governed_contract_merges_version_boundary_fields -q -p no:cacheprovider
```

Expected:

```text
1 passed
```

- [ ] **Step 6: Run focused answer contract regression**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_answer_contract.py -q -p no:cacheprovider
```

Expected: all tests in `tests/test_memory_answer_contract.py` pass.

- [ ] **Step 7: Commit Task 1**

Run:

```bash
git add memory2/eval_answer_contract.py tests/test_memory_answer_contract.py
git commit -m "feat: add version boundary evidence contract fields"
```

---

### Task 2: Add Eval-Only Version-Governed Profile

**Files:**
- Modify: `tests/test_memory_comprehensive_online_eval.py`
- Modify: `memory2/eval_comprehensive_online.py`

**Interfaces:**
- Consumes:
  - `governed_tri_trace_for_case(case: EvalCase) -> dict[str, object]`
  - `build_version_boundary_info(case: EvalCase, governed_trace_info: object) -> VersionBoundaryInfo`
  - `build_production_governed_tri_evidence_contract(..., version_boundary_info=...)`
- Produces:
  - constant `TRI_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE = "chain_tri_version_governed_answer_contract"`
  - `version_governed_tri_trace_for_case(case: EvalCase) -> dict[str, object]`
  - optional profile accepted by `build_comprehensive_run_specs()`
  - production-safe contract block and raw metadata for the new profile.

- [ ] **Step 1: Write failing profile tests**

Update imports from `memory2.eval_comprehensive_online` in `tests/test_memory_comprehensive_online_eval.py` to include:

```python
version_governed_tri_trace_for_case,
```

Append these tests:

```python
def _case_with_version_boundary_signal():
    for case in (
        build_quantitative_eval_cases(case_set="common", limit=20, case_pack="standard")
        + build_quantitative_eval_cases(case_set="hard", limit=20, case_pack="standard")
    ):
        if case.setup.get("memory_replacements"):
            return case
    raise AssertionError("fixture must include memory replacements")


def test_version_governed_profile_does_not_expand_governed_ids() -> None:
    case = _case_with_version_boundary_signal()

    governed_ids = evidence_ids_for_profile(
        case,
        "chain_tri_governed_answer_contract",
    )
    version_governed_ids = evidence_ids_for_profile(
        case,
        "chain_tri_version_governed_answer_contract",
    )

    assert version_governed_ids == governed_ids
    assert set(version_governed_ids) == set(governed_ids)
    assert profile_evidence_source(
        "chain_tri_version_governed_answer_contract"
    ) == "tri_version_governed_answer_contract.version_boundaried_governed_allowed_evidence_ids"


def test_version_governed_trace_exposes_boundary_without_recall_expansion() -> None:
    case = _case_with_version_boundary_signal()

    trace_info = version_governed_tri_trace_for_case(case)
    version_boundary = trace_info["trace"]["version_boundary"]
    governed_ids = evidence_ids_for_profile(
        case,
        "chain_tri_governed_answer_contract",
    )

    assert trace_info["ids"] == governed_ids
    assert version_boundary["recall_expanded"] is False
    assert isinstance(version_boundary["active_version_ids"], list)
    assert isinstance(version_boundary["stale_warning_ids"], list)
    assert isinstance(version_boundary["forbidden_boundary_ids"], list)
    assert set(version_boundary["active_version_ids"]) <= set(governed_ids)
    assert set(version_boundary["stale_warning_ids"]) <= set(governed_ids)
    assert set(version_boundary["forbidden_boundary_ids"]).isdisjoint(governed_ids)


def test_version_governed_profile_injects_production_safe_contract_block(
    tmp_path: Path,
) -> None:
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

    assert "Evidence Contract: chain_tri_version_governed_answer_contract" in result.text_block
    assert "active_version_ids:" in result.text_block
    assert "stale_warning_ids:" in result.text_block
    assert "forbidden_boundary_ids:" in result.text_block
    assert result.raw["evidence_source"] == (
        "tri_version_governed_answer_contract.version_boundaried_governed_allowed_evidence_ids"
    )
    assert result.raw["answer_contract"]["production_safe_evidence_contract"] is True
    assert result.raw["answer_contract"]["combines_candidate_governance"] is True
    assert result.raw["answer_contract"]["combines_version_boundary"] is True
    assert result.raw["version_boundary"]["recall_expanded"] is False
    assert tuple(result.raw["ids"]) == evidence_ids_for_profile(
        case,
        "chain_tri_governed_answer_contract",
    )
    assert tuple(memory_id for memory_id in engine.used_memory_ids) == evidence_ids_for_profile(
        case,
        "chain_tri_governed_answer_contract",
    )
    assert tuple(hit.id for hit in result.hits) == evidence_ids_for_profile(
        case,
        "chain_tri_governed_answer_contract",
    )
    assert set(result.raw["answer_contract"]["forbidden_boundary_ids"]).isdisjoint(
        result.raw["answer_contract"]["allowed_evidence_ids"]
    )


def test_version_governed_profile_report_metadata_and_post_check_shadow(
    tmp_path: Path,
) -> None:
    case = _case_with_version_boundary_signal()
    specs = build_comprehensive_run_specs(
        [case],
        profiles=("chain_tri_version_governed_answer_contract",),
        prompt_variants=("baseline",),
        repeats=1,
    )

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            real_llm_enabled=False,
        )
    )

    metadata = report.metrics["profile_metadata"][
        "chain_tri_version_governed_answer_contract"
    ]
    assert metadata["eval_only"] is True
    assert metadata["oracle_protected"] is True
    assert metadata["production_safe_evidence_contract"] is True
    assert metadata["combines_candidate_governance"] is True
    assert metadata["combines_version_boundary"] is True
    assert metadata["does_not_expand_recall"] is True
    assert report.metrics["answer_post_check_shadow"]["case_count"] == 1
    assert report.case_records[0]["answer_post_check_shadow"]["shadow_enabled"] is True


def test_version_governed_answer_expectation_is_grounding_only_not_oracle_terms() -> None:
    case = _case_with_version_boundary_signal()

    expectation = answer_expectation_for_profile(
        case,
        "chain_tri_version_governed_answer_contract",
    )

    assert expectation.expected_answer_contains == ()
    assert expectation.expected_answer_contains_any == ()
    assert expectation.forbidden_answer_contains == ()
    assert expectation.expected_memory_ids == evidence_ids_for_profile(
        case,
        "chain_tri_version_governed_answer_contract",
    )
    assert expectation.grounding_required is True


def test_version_governed_boundary_ignores_unrelated_superseded_fixture_rows() -> None:
    case = _case_with_version_boundary_signal()
    governed_ids = evidence_ids_for_profile(
        case,
        "chain_tri_governed_answer_contract",
    )
    case = replace(
        case,
        setup={
            **case.setup,
            "memory_items": [
                *case.setup.get("memory_items", ()),
                {
                    "id": "unrelated_old",
                    "summary": "unrelated superseded fixture evidence",
                    "status": "superseded",
                    "source_ref": "telegram:unrelated:0",
                },
                {
                    "id": "unrelated_new",
                    "summary": "unrelated active fixture evidence",
                    "status": "active",
                    "source_ref": "telegram:unrelated:1",
                },
            ],
            "memory_replacements": [
                *case.setup.get("memory_replacements", ()),
                {
                    "old_item_id": "unrelated_old",
                    "new_item_id": "unrelated_new",
                    "old_summary": "unrelated superseded fixture evidence",
                    "new_summary": "unrelated active fixture evidence",
                    "old_source_ref": "telegram:unrelated:0",
                    "new_source_ref": "telegram:unrelated:1",
                },
            ],
        },
    )

    trace_info = version_governed_tri_trace_for_case(case)
    boundary = trace_info["trace"]["version_boundary"]

    assert trace_info["ids"] == governed_ids
    assert "unrelated_old" not in boundary["stale_warning_ids"]
    assert "unrelated_old" not in boundary["forbidden_boundary_ids"]
    assert "unrelated_new" not in boundary["active_version_ids"]
```

- [ ] **Step 2: Run RED profile tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_comprehensive_online_eval.py::test_version_governed_profile_does_not_expand_governed_ids \
  tests/test_memory_comprehensive_online_eval.py::test_version_governed_trace_exposes_boundary_without_recall_expansion \
  tests/test_memory_comprehensive_online_eval.py::test_version_governed_profile_injects_production_safe_contract_block \
  tests/test_memory_comprehensive_online_eval.py::test_version_governed_profile_report_metadata_and_post_check_shadow \
  tests/test_memory_comprehensive_online_eval.py::test_version_governed_answer_expectation_is_grounding_only_not_oracle_terms \
  -q -p no:cacheprovider
```

Expected: FAIL because the new profile and helper are unknown.

- [ ] **Step 3: Register constants and metadata**

In `memory2/eval_comprehensive_online.py`, import:

```python
build_version_boundary_info,
```

Add after `TRI_RERANK_GOVERNED_ANSWER_CONTRACT_PROFILE`:

```python
TRI_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE = (
    "chain_tri_version_governed_answer_contract"
)
```

Add it to `PRODUCTION_GOVERNED_ANSWER_CONTRACT_PROFILES` and `OPTIONAL_ANSWER_QUALITY_PROFILES`.

Add `PROFILE_METADATA` entry:

```python
TRI_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE: {
    "eval_only": True,
    "oracle_protected": True,
    "uses_fixture_expected_ids": True,
    "diagnostic_answer_contract": True,
    "uses_fixture_answer_expectations": False,
    "production_safe_evidence_contract": True,
    "combines_candidate_governance": True,
    "combines_version_boundary": True,
    "does_not_expand_recall": True,
    "candidate_governance_mode": "tiered",
    "description": (
        "Keeps candidate-governed tri allowed ids unchanged and adds "
        "version-boundary fields for active versions, stale/superseded "
        "warnings, conflict warnings, and forbidden boundaries."
    ),
},
```

- [ ] **Step 4: Add trace helper, evidence ids, and evidence source**

Add:

```python
def version_governed_tri_trace_for_case(case: EvalCase) -> dict[str, object]:
    governed_trace = governed_tri_trace_for_case(case)
    governed_ids = tuple(str(item) for item in governed_trace.get("ids", ()))
    boundary = build_version_boundary_info(case, governed_trace)
    trace = dict(governed_trace.get("trace", {}))
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
    return {"ids": governed_ids, "trace": trace}
```

In `evidence_ids_for_profile()`, add:

```python
if profile_name == TRI_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE:
    return tuple(version_governed_tri_trace_for_case(case).get("ids", ()))
```

In `profile_evidence_source()`, add:

```python
TRI_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE: (
    "tri_version_governed_answer_contract."
    "version_boundaried_governed_allowed_evidence_ids"
),
```

- [ ] **Step 5: Route the new profile through production-safe contract rendering**

Update governed trace selection in `ComprehensiveOnlineMemoryEngine.retrieve()`:

```python
governed_trace = (
    version_governed_tri_trace_for_case(self.case)
    if self.profile_name == TRI_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE
    else rerank_governed_tri_trace_for_case(self.case)
    if self.profile_name == TRI_RERANK_GOVERNED_ANSWER_CONTRACT_PROFILE
    else governed_tri_trace_for_case(self.case)
)
```

In the production-safe branch, build version boundary only for the new profile:

```python
version_boundary_info = (
    build_version_boundary_info(self.case, governed_trace)
    if self.profile_name == TRI_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE
    else None
)
contract = build_production_governed_tri_evidence_contract(
    self.case,
    governed_trace,
    profile_name=self.profile_name,
    version_boundary_info=version_boundary_info,
)
```

Add:

```python
combines_version_boundary = (
    self.profile_name == TRI_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE
)
```

Add to raw payload:

```python
"combines_version_boundary": combines_version_boundary,
"version_boundary": trace.get("version_boundary", {}),
```

Add to `raw["answer_contract"]`:

```python
"combines_version_boundary": combines_version_boundary,
```

- [ ] **Step 6: Extend Markdown metadata columns**

In `_profile_metadata_markdown_section()`, add `combines_version_boundary` column and value:

```python
"combines_rerank_injection | combines_version_boundary | does_not_expand_recall |"
```

and:

```python
_fmt(row.get("combines_version_boundary")),
```

- [ ] **Step 7: Run GREEN focused profile tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_comprehensive_online_eval.py::test_version_governed_profile_does_not_expand_governed_ids \
  tests/test_memory_comprehensive_online_eval.py::test_version_governed_trace_exposes_boundary_without_recall_expansion \
  tests/test_memory_comprehensive_online_eval.py::test_version_governed_profile_injects_production_safe_contract_block \
  tests/test_memory_comprehensive_online_eval.py::test_version_governed_profile_report_metadata_and_post_check_shadow \
  tests/test_memory_comprehensive_online_eval.py::test_version_governed_answer_expectation_is_grounding_only_not_oracle_terms \
  -q -p no:cacheprovider
```

Expected:

```text
5 passed
```

- [ ] **Step 8: Run comprehensive eval regression**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py -q -p no:cacheprovider
```

Expected: all tests in `tests/test_memory_comprehensive_online_eval.py` pass.

- [ ] **Step 9: Commit Task 2**

Run:

```bash
git add memory2/eval_comprehensive_online.py tests/test_memory_comprehensive_online_eval.py
git commit -m "feat: add version governed answer contract eval profile"
```

---

### Task 3: Add P6o-7 Fake-Provider CLI Matrix Smoke

**Files:**
- Modify: `tests/test_memory_comprehensive_online_cli.py`

**Interfaces:**
- Consumes:
  - CLI `--balanced-small`, `--common-limit`, `--hard-limit`, `--profiles`, `--fake-provider`, `--real-memory-workspace`.
  - Profile metadata and post-check aggregate from Task 2.
- Produces:
  - Test `test_comprehensive_online_cli_p6o7_version_governed_fake_provider_matrix_shape()`.

- [ ] **Step 1: Write CLI integration smoke**

Append this test to `tests/test_memory_comprehensive_online_cli.py`:

```python
def test_comprehensive_online_cli_p6o7_version_governed_fake_provider_matrix_shape(
    tmp_path: Path,
) -> None:
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
            (
                "chain_tri_governed_answer_contract,"
                "chain_tri_version_governed_answer_contract"
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
        (output_dir / "memory_comprehensive_online_eval.json").read_text(
            encoding="utf-8"
        )
    )
    markdown = (output_dir / "memory_comprehensive_online_eval.md").read_text(
        encoding="utf-8"
    )

    assert payload["metrics"]["case_count"] == 8
    assert payload["metrics"]["unique_case_count"] == 4
    assert payload["metrics"]["completed_call_count"] == 8
    assert payload["metrics"]["profile_count"] == 2
    assert payload["metrics"]["prompt_variant_count"] == 1
    assert payload["metrics"]["repeat_count"] == 1
    assert payload["metrics"]["provider_error_count"] == 0
    assert payload["metrics"]["timeout_count"] == 0
    assert payload["metrics"]["answer_post_check_shadow"]["case_count"] == 8
    assert set(payload["metrics"]["profile_summaries"]) == {
        "chain_tri_governed_answer_contract",
        "chain_tri_version_governed_answer_contract",
    }
    metadata = payload["metrics"]["profile_metadata"][
        "chain_tri_version_governed_answer_contract"
    ]
    assert metadata["production_safe_evidence_contract"] is True
    assert metadata["combines_version_boundary"] is True
    assert metadata["does_not_expand_recall"] is True
    assert "chain_tri_version_governed_answer_contract" in markdown
    assert "combines_version_boundary" in markdown
    assert "raw_prompt" not in markdown
    assert "full_answer" not in markdown
    assert "session_text" not in markdown
```

- [ ] **Step 2: Run the CLI integration smoke**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_comprehensive_online_cli.py::test_comprehensive_online_cli_p6o7_version_governed_fake_provider_matrix_shape -q -p no:cacheprovider
```

Expected:

```text
1 passed
```

- [ ] **Step 3: Run focused CLI regression**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_comprehensive_online_cli.py -q -p no:cacheprovider
```

Expected: all CLI tests pass.

- [ ] **Step 4: Commit Task 3**

Run:

```bash
git add tests/test_memory_comprehensive_online_cli.py
git commit -m "test: cover p6o7 version governed online matrix"
```

---

### Task 4: Run P6o-7 Fake Smoke, Then Optional Real Matrix, And Record Docs

**Files:**
- Create, if real matrix is run:
  - `my_md/memory_optimization/eval_reports/p6o7_version_boundary_governed_small_online_v1/memory_comprehensive_online_eval.json`
  - `my_md/memory_optimization/eval_reports/p6o7_version_boundary_governed_small_online_v1/memory_comprehensive_online_eval.md`
- Modify:
  - `my_md/memory_optimization/README.md`
  - `my_md/memory_optimization/02-memory-quality-metrics.md`
  - `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
  - `task_plan.md`
  - `progress.md`

**Interfaces:**
- Consumes: Tasks 1-3 implementation and tests.
- Produces: P6o-7 bounded smoke/real conclusion and docs handoff to the next slice.

- [ ] **Step 1: Run fake-provider 40-case smoke**

Run:

```bash
rm -rf /tmp/akashic-memory-p6o7-version-boundary-governed
mkdir -p /tmp/akashic-memory-p6o7-version-boundary-governed
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-p6o7-version-boundary-governed/workspace \
  --out-dir /tmp/akashic-memory-p6o7-version-boundary-governed/fake-reports \
  --fake-provider \
  --case-pack standard \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --profiles chain_tri_governed_answer_contract,chain_tri_version_governed_answer_contract \
  --prompt-variants baseline \
  --repeats 1 \
  --checkpoint-jsonl /tmp/akashic-memory-p6o7-version-boundary-governed/fake.checkpoint.jsonl \
  --real-memory-workspace /tmp/akashic-memory-p6o7-version-boundary-governed/empty-real-memory \
  --concurrency 2
```

Expected: command exits `0` and writes JSON/Markdown under `/tmp/akashic-memory-p6o7-version-boundary-governed/fake-reports/`.

- [ ] **Step 2: Assert fake-provider report shape**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path
path = Path('/tmp/akashic-memory-p6o7-version-boundary-governed/fake-reports/memory_comprehensive_online_eval.json')
payload = json.loads(path.read_text(encoding='utf-8'))
m = payload['metrics']
assert m['case_count'] == 80, m['case_count']
assert m['unique_case_count'] == 40, m['unique_case_count']
assert m['profile_count'] == 2, m['profile_count']
assert m['prompt_variant_count'] == 1, m['prompt_variant_count']
assert m['repeat_count'] == 1, m['repeat_count']
assert m['provider_error_count'] == 0, m['provider_error_count']
assert m['timeout_count'] == 0, m['timeout_count']
assert m['answer_post_check_shadow']['case_count'] == 80, m['answer_post_check_shadow']
assert set(m['profile_summaries']) == {
    'chain_tri_governed_answer_contract',
    'chain_tri_version_governed_answer_contract',
}, m['profile_summaries'].keys()
meta = m['profile_metadata']['chain_tri_version_governed_answer_contract']
assert meta['production_safe_evidence_contract'] is True, meta
assert meta['combines_version_boundary'] is True, meta
assert meta['does_not_expand_recall'] is True, meta
print('fake p6o7 report shape ok')
PY
```

Expected:

```text
fake p6o7 report shape ok
```

- [ ] **Step 3: Run real LLM matrix only if fake gate passes**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --workspace /tmp/akashic-memory-p6o7-version-boundary-governed/real-workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o7_version_boundary_governed_small_online_v1 \
  --enable-real-llm \
  --case-pack standard \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --profiles chain_tri_governed_answer_contract,chain_tri_version_governed_answer_contract \
  --prompt-variants baseline \
  --repeats 1 \
  --checkpoint-jsonl /tmp/akashic-memory-p6o7-version-boundary-governed/real.checkpoint.jsonl \
  --real-memory-workspace /tmp/akashic-memory-p6o7-version-boundary-governed/empty-real-memory \
  --concurrency 2
```

Expected if provider is available: command exits `0` and writes sanitized committed report files. If provider returns an infra failure, stop and rebuild only a checkpoint report with infra failures excluded; do not claim a full P6o-7 result.

Infra-failure checkpoint-only recovery command:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-p6o7-version-boundary-governed/checkpoint-workspace \
  --out-dir /tmp/akashic-memory-p6o7-version-boundary-governed/checkpoint-report \
  --checkpoint-report-only \
  --exclude-infra-failures \
  --checkpoint-jsonl /tmp/akashic-memory-p6o7-version-boundary-governed/real.checkpoint.jsonl \
  --enable-real-llm \
  --real-memory-workspace /tmp/akashic-memory-p6o7-version-boundary-governed/empty-real-memory
```

If this path is used, keep the checkpoint-only report under `/tmp`, update docs with `partial_due_to_infra_failure = True`, and do not commit it as the formal P6o-7 real result.

- [ ] **Step 4: Assert real report integrity**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path
path = Path('my_md/memory_optimization/eval_reports/p6o7_version_boundary_governed_small_online_v1/memory_comprehensive_online_eval.json')
payload = json.loads(path.read_text(encoding='utf-8'))
m = payload['metrics']
assert m['real_llm_enabled'] is True, m['real_llm_enabled']
assert m['case_count'] == 80, m['case_count']
assert m['unique_case_count'] == 40, m['unique_case_count']
assert m['completed_call_count'] == 80, m['completed_call_count']
assert m['profile_count'] == 2, m['profile_count']
assert m.get('excluded_infra_failure_count', 0) == 0, m.get('excluded_infra_failure_count')
assert m['provider_error_count'] == 0, m['provider_error_count']
assert m['timeout_count'] == 0, m['timeout_count']
assert m['answer_post_check_shadow']['case_count'] == 80, m['answer_post_check_shadow']
summaries = m['profile_summaries']
base = summaries['chain_tri_governed_answer_contract']
version = summaries['chain_tri_version_governed_answer_contract']
assert float(version['answer_rule_pass_rate']) >= float(base['answer_rule_pass_rate']) - 5.0, (base, version)
assert float(version['memory_grounding_pass_rate']) == 100.0, version
assert float(version['forbidden_violation_rate']) <= float(base['forbidden_violation_rate']), (base, version)
assert float(version['avg_total_token_count']) <= float(base['avg_total_token_count']) * 1.10, (base, version)
for profile in ('chain_tri_governed_answer_contract', 'chain_tri_version_governed_answer_contract'):
    row = m['profile_summaries'][profile]
    print(profile, row['answer_success_count'], row['case_count'], row['answer_rule_pass_rate'], row['memory_grounding_pass_rate'], row['forbidden_violation_rate'], row['avg_total_token_count'])
def post_check_counts(profile):
    counts = {
        'needs_retry': 0,
        'forbidden_boundary_included': 0,
        'missing_likely_relevant_context': 0,
        'stale_evidence_included': 0,
        'conflict_evidence_included': 0,
        'insufficient_fallback_missing': 0,
    }
    for record in payload['case_records']:
        if record['profile_name'] != profile:
            continue
        shadow = record.get('answer_post_check_shadow') or {}
        for key in counts:
            counts[key] += int(bool(shadow.get(key)))
    return counts
base_counts = post_check_counts('chain_tri_governed_answer_contract')
version_counts = post_check_counts('chain_tri_version_governed_answer_contract')
for key, value in version_counts.items():
    assert value <= base_counts[key], (key, base_counts, version_counts)
print('per_profile_post_check', {'base': base_counts, 'version': version_counts})
print('post_check', m['answer_post_check_shadow'])
PY
```

Expected: prints the two profile rows and exits `0`.

- [ ] **Step 5: Assert committed report privacy**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path
base = Path('my_md/memory_optimization/eval_reports/p6o7_version_boundary_governed_small_online_v1')
payload = json.loads((base / 'memory_comprehensive_online_eval.json').read_text(encoding='utf-8'))
metrics = payload['metrics']
for key in (
    'raw_query_included',
    'raw_memory_summary_included',
    'prompt_included',
    'session_text_included',
    'full_answer_included',
):
    assert metrics[key] is False, (key, metrics[key])
texts = {
    'json': (base / 'memory_comprehensive_online_eval.json').read_text(encoding='utf-8'),
    'markdown': (base / 'memory_comprehensive_online_eval.md').read_text(encoding='utf-8'),
}
for name, text in texts.items():
    for forbidden in ('answer_debug', 'api_key'):
        assert forbidden not in text, (name, forbidden)
print('p6o7 report privacy ok')
PY
```

Expected:

```text
p6o7 report privacy ok
```

- [ ] **Step 6: Generate docs summary block from report**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path
p = Path('my_md/memory_optimization/eval_reports/p6o7_version_boundary_governed_small_online_v1/memory_comprehensive_online_eval.json')
m = json.loads(p.read_text(encoding='utf-8'))['metrics']
print('### Phase 6o7 Version-Boundary Governed')
print()
print('P6o-7 tested only one added signal: `chain_tri_version_governed_answer_contract`. It keeps `chain_tri_governed_answer_contract` allowed evidence unchanged and adds version-boundary fields for active versions, stale/superseded warnings, conflict warnings, forbidden boundaries, and insufficient-evidence fallback. This is still eval/shadow-only and oracle-protected through P6o-2 candidate governance; it is not production traffic.')
print()
print('Report path:')
print()
print('- `my_md/memory_optimization/eval_reports/p6o7_version_boundary_governed_small_online_v1/memory_comprehensive_online_eval.json`')
print('- `my_md/memory_optimization/eval_reports/p6o7_version_boundary_governed_small_online_v1/memory_comprehensive_online_eval.md`')
print()
print('| profile | answer_success | answer_rate | grounding_rate | forbidden_rate | avg_tokens |')
print('| --- | ---: | ---: | ---: | ---: | ---: |')
for profile in ('chain_tri_governed_answer_contract', 'chain_tri_version_governed_answer_contract'):
    row = m['profile_summaries'][profile]
    print(f\"| `{profile}` | `{row['answer_success_count']}/{row['case_count']}` | `{row['answer_rule_pass_rate']}%` | `{row['memory_grounding_pass_rate']}%` | `{row['forbidden_violation_rate']}%` | `{row['avg_total_token_count']}` |\")
print()
print('Post-check shadow aggregate:')
print()
print('| metric | value |')
print('| --- | ---: |')
for key, value in m['answer_post_check_shadow'].items():
    print(f'| `{key}` | `{value}` |')
PY
```

Expected: prints a complete Markdown block with no placeholders. Paste that block into `my_md/memory_optimization/02-memory-quality-metrics.md`, then add concise one-paragraph summaries to `README.md`, `04-memory-plugin-experiment-roadmap.md`, `task_plan.md`, and `progress.md` using the same measured numbers.

- [ ] **Step 7: Run final verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_answer_contract.py \
  tests/test_memory_comprehensive_online_eval.py \
  tests/test_memory_comprehensive_online_cli.py \
  -q -p no:cacheprovider
.venv/bin/python -m compileall -q memory2 scripts tests
git diff --check
```

Expected: pytest passes, compileall exits `0`, diff check exits `0`.

- [ ] **Step 8: Commit Task 4**

Run:

```bash
git add -f docs/superpowers/plans/2026-07-28-memory-p6o7-version-boundary-governed.md
git add \
  my_md/memory_optimization/README.md \
  my_md/memory_optimization/02-memory-quality-metrics.md \
  my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md \
  my_md/memory_optimization/eval_reports/p6o7_version_boundary_governed_small_online_v1/memory_comprehensive_online_eval.json \
  my_md/memory_optimization/eval_reports/p6o7_version_boundary_governed_small_online_v1/memory_comprehensive_online_eval.md \
  task_plan.md \
  progress.md
git commit -m "docs: record p6o7 version boundary governed signal"
```

If no real LLM matrix was run, omit the report paths and use:

```bash
git add -f docs/superpowers/plans/2026-07-28-memory-p6o7-version-boundary-governed.md
git add \
  my_md/memory_optimization/README.md \
  my_md/memory_optimization/02-memory-quality-metrics.md \
  my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md \
  task_plan.md \
  progress.md
git commit -m "docs: record p6o7 version boundary smoke"
```

---

## Self-Review

**Spec coverage:** This plan first verifies that the previous P6o-6 data is already recorded, then implements only the requested next slice: `tri governed` vs `tri + version-boundary governed`. It explicitly excludes rerank, graph, retry, production prompt changes, production retriever changes, and production writes.

**Placeholder scan:** The plan does not contain `TBD`, `TODO`, `implement later`, `fill in details`, or `Similar to Task`. The docs step generates measured Markdown from the report instead of requiring placeholder replacement.

**Type consistency:** The profile name is consistently `chain_tri_version_governed_answer_contract`. The constant is `TRI_VERSION_GOVERNED_ANSWER_CONTRACT_PROFILE`. The helper is `version_governed_tri_trace_for_case(case: EvalCase) -> dict[str, object]`. The contract boundary object is `VersionBoundaryInfo`.

**Reviewer-driven revision:** Version-boundary computation is scoped to governed tri ids plus their direct replacement neighbors. This keeps `allowed_evidence_ids` identical to the governed baseline and prevents unrelated full-memory version-chain warnings from contaminating the P6o-7 comparison. Active leaf/current ids are explicitly excluded from `forbidden_boundary_ids`.

**Execution boundary:** Tasks 1-3 are code/test only and can be committed independently. Task 4 runs fake-provider gate before real LLM calls and records either full real data or an explicit partial/not-run boundary.
