# Memory P6o6 Governed Rerank Signal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add and validate an eval-only `chain_tri_rerank_governed_answer_contract` profile that tests rerank/injection ordering as a governed evidence-contract input before any productionization.

**Architecture:** Reuse `chain_tri_governed_answer_contract` as the baseline candidate and add only one signal layer: rerank/injection ordering. The new profile must not expand recall beyond candidate-governed tri ids; it reorders governed ids using the existing `chain_rerank_injection` signal, then renders the same production-safe evidence contract and post-check shadow shape. Real production `AgentLoop`, memory writes, default prompt behavior, and old retrieve contracts remain unchanged.

**Tech Stack:** Current `.venv` on Python `>=3.12`, pytest, existing `memory2.eval_comprehensive_online`, existing `memory2.eval_answer_contract`, existing `scripts/run_memory_comprehensive_online_eval.py`, JSON/Markdown eval reports, checkpoint JSONL under `/tmp`.

## Global Constraints

- Worktree: `/home/jjh/git_work/akashic-agent/.worktrees/memory-next`.
- Do not sync remote/main in this plan unless the user explicitly redirects.
- Do not push without explicit user instruction.
- Do not modify production `AgentLoop`, `Reasoner`, `ToolExecutor`, `ToolRegistry`, production memory writes, production prompts, `plugins/default_memory/engine.py`, or the old `Retriever.retrieve()` return contract.
- P6o-6 first execution slice tests only `tri governed` vs `tri + rerank governed`; do not add graph, version-boundary, retry, or production activation in this plan.
- The new profile is eval-only and oracle-protected because it reuses P6o-2 protected candidate governance; label this clearly in metadata and docs.
- The new profile must not introduce ids outside `chain_tri_governed_answer_contract`; rerank/injection may change ordering, but recall expansion is forbidden in this slice.
- Real LLM calls are allowed only after focused tests and fake-provider smoke pass.
- Real LLM matrix for this slice is bounded: common `20` + hard `20`, profiles `chain_tri_governed_answer_contract,chain_tri_rerank_governed_answer_contract`, prompt variant `baseline`, repeat `1`, expected `80` completed calls.
- Store live checkpoint JSONL under `/tmp/akashic-memory-p6o6-governed-rerank/`, not in git-tracked docs.
- Do not write raw prompt, raw query, raw session text, raw memory summaries, full answers, answer debug artifacts, or API keys into committed report/docs.
- Success gate:
  - focused CLI fake smoke: common `2` + hard `2`, `case_count = 8`, `unique_case_count = 4`, `profile_count = 2`, `provider_error_count = 0`, `timeout_count = 0`;
  - full fake pre-real gate: common `20` + hard `20`, `case_count = 80`, `unique_case_count = 40`, `profile_count = 2`, `provider_error_count = 0`, `timeout_count = 0`;
  - real matrix, if run: common `20` + hard `20`, `case_count = 80`, `unique_case_count = 40`, `profile_count = 2`, `provider_error_count = 0`, `timeout_count = 0`, `excluded_infra_failure_count = 0`;
  - real rerank-governed answer rate may not fall more than `5.0` points below `chain_tri_governed_answer_contract`;
  - `chain_tri_rerank_governed_answer_contract` should keep grounding `100.0%`, forbidden close to `0.0%`, and answer rate close to P6o-5 governed `97.5%`;
  - rerank-governed forbidden rate must be less than or equal to the governed baseline forbidden rate;
  - rerank-governed avg tokens must not exceed governed baseline avg tokens by more than `10.0%`;
  - post-check shadow risk counts for the full report must not rise above the governed baseline counts.

---

## File Structure

- Modify `memory2/eval_answer_contract.py`
  - Allow production-safe governed contract builders to set `profile_name` while keeping the existing default unchanged.
- Modify `memory2/eval_comprehensive_online.py`
  - Register `chain_tri_rerank_governed_answer_contract`.
  - Add helper `rerank_governed_evidence_order(governed_ids: Sequence[str], rerank_ids: Sequence[str]) -> tuple[str, ...]`.
  - Add helper `rerank_governed_tri_trace_for_case(case: EvalCase) -> dict[str, object]`.
  - Route the new profile through production-safe evidence contract rendering and post-check shadow.
  - Extend Markdown profile metadata columns for `combines_rerank_injection` and `does_not_expand_recall`.
- Modify `scripts/run_memory_comprehensive_online_eval.py`
  - Make the fake provider recognize the new production-safe evidence contract profile.
- Modify `tests/test_memory_answer_contract.py`
  - Cover custom `profile_name` support without reintroducing fixture answer terms.
- Modify `tests/test_memory_comprehensive_online_eval.py`
  - Cover new profile registration, evidence ordering boundary, metadata, contract block, scoring expectation, and post-check shadow.
- Modify `tests/test_memory_comprehensive_online_cli.py`
  - Add a scaled fake-provider CLI matrix regression for the two-profile P6o-6 slice.
- Create execution report, only after real LLM gate passes:
  - `my_md/memory_optimization/eval_reports/p6o6_governed_rerank_small_online_v1/memory_comprehensive_online_eval.json`
  - `my_md/memory_optimization/eval_reports/p6o6_governed_rerank_small_online_v1/memory_comprehensive_online_eval.md`
- Modify docs after fake or real execution:
  - `my_md/memory_optimization/README.md`
  - `my_md/memory_optimization/02-memory-quality-metrics.md`
  - `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
  - `task_plan.md`
  - `progress.md`

---

### Task 0: Confirm P6o-6 Baseline

**Files:**
- Modify: none

**Interfaces:**
- Consumes: current `memory-next` worktree after P6o-5 docs.
- Produces: known clean baseline before implementation.

- [ ] **Step 1: Confirm linked worktree and branch**

Run:

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
BRANCH=$(git branch --show-current)
printf 'GIT_DIR=%s\nGIT_COMMON=%s\nBRANCH=%s\n' "$GIT_DIR" "$GIT_COMMON" "$BRANCH"
```

Expected:

```text
BRANCH=memory-next
```

- [ ] **Step 2: Inspect status and current P6o-5/P6o-6 handoff commits**

Run:

```bash
git status --short --branch
git log --oneline -8
```

Expected: status has no unrelated unstaged implementation edits. Recent commits include:

```text
a3b6444 docs: record p6o6 combination guidance
ecb7e80 docs: add p6o5 small real llm ab plan
589e193 docs: record p6o5 small online governed answer contract
```

---

### Task 1: Add Custom Production Evidence Contract Profile Name

**Files:**
- Modify: `tests/test_memory_answer_contract.py`
- Modify: `memory2/eval_answer_contract.py`

**Interfaces:**
- Consumes:
  - `build_production_governed_tri_evidence_contract(case, governed_trace_info) -> ProductionEvidenceContract`
  - `render_production_evidence_contract_block(contract) -> str`
- Produces:
  - `build_production_governed_tri_evidence_contract(case, governed_trace_info, profile_name: str = "chain_tri_governed_answer_contract") -> ProductionEvidenceContract`

- [ ] **Step 1: Write the failing test**

Append this test to `tests/test_memory_answer_contract.py`:

```python
def test_production_governed_contract_accepts_eval_profile_name() -> None:
    case = _case_with_should_not_in_tri()
    governed_trace_info = {
        "ids": ("custom_target",),
        "trace": {
            "candidate_governance_mode": "tiered",
            "candidate_risk_tiers": [
                {
                    "candidate_id": "custom_target",
                    "tier": "allow",
                    "risks": (),
                    "lane": "semantic",
                },
            ],
        },
    }
    case = replace(
        case,
        setup={
            **case.setup,
            "memory_items": [
                {
                    "id": "custom_target",
                    "summary": "custom profile evidence",
                    "status": "active",
                    "source_ref": "telegram:1:1",
                }
            ],
        },
    )

    contract = build_production_governed_tri_evidence_contract(
        case,
        governed_trace_info,
        profile_name="chain_tri_rerank_governed_answer_contract",
    )
    text = render_production_evidence_contract_block(contract)

    assert contract.profile_name == "chain_tri_rerank_governed_answer_contract"
    assert "Evidence Contract: chain_tri_rerank_governed_answer_contract" in text
    assert contract.production_safe is True
    assert contract.uses_fixture_answer_expectations is False
    assert contract.required_terms == ()
    assert contract.forbidden_terms == ()
```

- [ ] **Step 2: Run the RED test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_answer_contract.py::test_production_governed_contract_accepts_eval_profile_name -q -p no:cacheprovider
```

Expected: FAIL with `TypeError` for unexpected keyword argument `profile_name`.

- [ ] **Step 3: Implement the minimal code**

In `memory2/eval_answer_contract.py`, change the function signature:

```python
def build_production_governed_tri_evidence_contract(
    case: EvalCase,
    governed_trace_info: object,
    *,
    profile_name: str = GOVERNED_TRI_ANSWER_CONTRACT_PROFILE,
) -> ProductionEvidenceContract:
```

In the returned `ProductionEvidenceContract`, replace:

```python
profile_name=GOVERNED_TRI_ANSWER_CONTRACT_PROFILE,
```

with:

```python
profile_name=profile_name,
```

- [ ] **Step 4: Run the GREEN test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_answer_contract.py::test_production_governed_contract_accepts_eval_profile_name -q -p no:cacheprovider
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Run focused contract regression**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_answer_contract.py -q -p no:cacheprovider
```

Expected: all tests in `tests/test_memory_answer_contract.py` pass.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add memory2/eval_answer_contract.py tests/test_memory_answer_contract.py
git commit -m "feat: allow governed evidence contract profile name"
```

---

### Task 2: Add Eval-Only Rerank-Governed Profile

**Files:**
- Modify: `tests/test_memory_comprehensive_online_eval.py`
- Modify: `memory2/eval_comprehensive_online.py`

**Interfaces:**
- Consumes:
  - `governed_tri_trace_for_case(case: EvalCase) -> dict[str, object]`
  - `evidence_ids_for_profile(case, "chain_rerank_injection") -> tuple[str, ...]`
  - `build_production_governed_tri_evidence_contract(case, trace_info, profile_name=...)`
- Produces:
  - helper `rerank_governed_evidence_order(governed_ids: Sequence[str], rerank_ids: Sequence[str]) -> tuple[str, ...]`
  - constant `TRI_RERANK_GOVERNED_ANSWER_CONTRACT_PROFILE = "chain_tri_rerank_governed_answer_contract"`
  - `rerank_governed_tri_trace_for_case(case: EvalCase) -> dict[str, object]`
  - optional profile accepted by `build_comprehensive_run_specs()`
  - production-safe contract block and raw metadata for the new profile.

- [ ] **Step 1: Write failing profile tests**

Add `rerank_governed_evidence_order` to the import list from `memory2.eval_comprehensive_online`, then append these tests to `tests/test_memory_comprehensive_online_eval.py`:

```python
def test_rerank_governed_evidence_order_reorders_only_within_governed_set() -> None:
    ordered = rerank_governed_evidence_order(
        governed_ids=("target", "weak", "tail", "stale"),
        rerank_ids=("outside", "tail", "target", "outside_2"),
    )

    assert ordered == ("tail", "target", "weak", "stale")


def _case_with_rerank_governed_order_delta():
    for case in (
        build_quantitative_eval_cases(case_set="common", limit=20, case_pack="standard")
        + build_quantitative_eval_cases(case_set="hard", limit=20, case_pack="standard")
    ):
        governed_ids = evidence_ids_for_profile(
            case,
            "chain_tri_governed_answer_contract",
        )
        rerank_ids = evidence_ids_for_profile(case, "chain_rerank_injection")
        rerank_set = set(rerank_ids)
        expected_order = tuple(
            [item_id for item_id in rerank_ids if item_id in set(governed_ids)]
            + [item_id for item_id in governed_ids if item_id not in rerank_set]
        )
        if governed_ids and expected_order != governed_ids:
            return case, governed_ids, rerank_ids, expected_order
    raise AssertionError("fixture must include a rerank/governed ordering delta")


def test_rerank_governed_profile_reorders_without_expanding_governed_ids() -> None:
    case, governed_ids, rerank_ids, expected_order = (
        _case_with_rerank_governed_order_delta()
    )

    rerank_governed_ids = evidence_ids_for_profile(
        case,
        "chain_tri_rerank_governed_answer_contract",
    )

    assert rerank_governed_ids == expected_order
    assert set(rerank_governed_ids) == set(governed_ids)
    assert set(rerank_governed_ids).isdisjoint(
        set(evidence_ids_for_profile(case, "chain_tri_retrieval")) - set(governed_ids)
    )
    assert any(item_id in rerank_ids for item_id in rerank_governed_ids)
    assert profile_evidence_source(
        "chain_tri_rerank_governed_answer_contract"
    ) == "tri_rerank_governed_answer_contract.reranked_governed_allowed_evidence_ids"


def test_rerank_governed_profile_never_expands_recall_on_p6o6_slice() -> None:
    cases = (
        build_quantitative_eval_cases(case_set="common", limit=20, case_pack="standard")
        + build_quantitative_eval_cases(case_set="hard", limit=20, case_pack="standard")
    )

    for case in cases:
        governed_ids = evidence_ids_for_profile(
            case,
            "chain_tri_governed_answer_contract",
        )
        rerank_governed_ids = evidence_ids_for_profile(
            case,
            "chain_tri_rerank_governed_answer_contract",
        )

        assert set(rerank_governed_ids) == set(governed_ids)
        assert len(rerank_governed_ids) == len(governed_ids)


def test_rerank_governed_profile_injects_production_safe_contract_block(
    tmp_path: Path,
) -> None:
    case, _governed_ids, _rerank_ids, _expected_order = (
        _case_with_rerank_governed_order_delta()
    )
    engine = ComprehensiveOnlineMemoryEngine(
        case,
        profile_name="chain_tri_rerank_governed_answer_contract",
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

    assert "Evidence Contract: chain_tri_rerank_governed_answer_contract" in result.text_block
    assert "production_safe=true" in result.text_block
    assert "allowed_evidence:" in result.text_block
    assert "forbidden_boundary_ids:" in result.text_block
    assert result.raw["evidence_source"] == (
        "tri_rerank_governed_answer_contract.reranked_governed_allowed_evidence_ids"
    )
    assert result.raw["answer_contract"]["production_safe_evidence_contract"] is True
    assert result.raw["answer_contract"]["combines_candidate_governance"] is True
    assert result.raw["answer_contract"]["combines_rerank_injection"] is True
    assert result.raw["rerank_signal"]["recall_expanded"] is False


def test_rerank_governed_profile_report_metadata_and_post_check_shadow(
    tmp_path: Path,
) -> None:
    case, _governed_ids, _rerank_ids, _expected_order = (
        _case_with_rerank_governed_order_delta()
    )
    specs = build_comprehensive_run_specs(
        [case],
        profiles=("chain_tri_rerank_governed_answer_contract",),
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
        "chain_tri_rerank_governed_answer_contract"
    ]
    assert metadata["eval_only"] is True
    assert metadata["oracle_protected"] is True
    assert metadata["production_safe_evidence_contract"] is True
    assert metadata["combines_candidate_governance"] is True
    assert metadata["combines_rerank_injection"] is True
    assert metadata["does_not_expand_recall"] is True
    assert report.metrics["answer_post_check_shadow"]["case_count"] == 1
    assert report.case_records[0]["answer_post_check_shadow"]["shadow_enabled"] is True


def test_rerank_governed_answer_expectation_is_grounding_only_not_oracle_terms() -> None:
    case, _governed_ids, _rerank_ids, _expected_order = (
        _case_with_rerank_governed_order_delta()
    )

    expectation = answer_expectation_for_profile(
        case,
        "chain_tri_rerank_governed_answer_contract",
    )

    assert expectation.expected_answer_contains == ()
    assert expectation.expected_answer_contains_any == ()
    assert expectation.forbidden_answer_contains == ()
    assert expectation.expected_memory_ids == evidence_ids_for_profile(
        case,
        "chain_tri_rerank_governed_answer_contract",
    )
    assert expectation.grounding_required is True
```

- [ ] **Step 2: Run RED tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_comprehensive_online_eval.py::test_rerank_governed_evidence_order_reorders_only_within_governed_set \
  tests/test_memory_comprehensive_online_eval.py::test_rerank_governed_profile_reorders_without_expanding_governed_ids \
  tests/test_memory_comprehensive_online_eval.py::test_rerank_governed_profile_never_expands_recall_on_p6o6_slice \
  tests/test_memory_comprehensive_online_eval.py::test_rerank_governed_profile_injects_production_safe_contract_block \
  tests/test_memory_comprehensive_online_eval.py::test_rerank_governed_profile_report_metadata_and_post_check_shadow \
  tests/test_memory_comprehensive_online_eval.py::test_rerank_governed_answer_expectation_is_grounding_only_not_oracle_terms \
  -q -p no:cacheprovider
```

Expected: FAIL because `rerank_governed_evidence_order` and the new profile do not exist.

- [ ] **Step 3: Register constants and metadata**

In `memory2/eval_comprehensive_online.py`, add after `TRI_GOVERNED_ANSWER_CONTRACT_PROFILE`:

```python
TRI_RERANK_GOVERNED_ANSWER_CONTRACT_PROFILE = (
    "chain_tri_rerank_governed_answer_contract"
)
PRODUCTION_GOVERNED_ANSWER_CONTRACT_PROFILES: tuple[str, ...] = (
    TRI_GOVERNED_ANSWER_CONTRACT_PROFILE,
    TRI_RERANK_GOVERNED_ANSWER_CONTRACT_PROFILE,
)
```

Update `OPTIONAL_ANSWER_QUALITY_PROFILES` to include:

```python
TRI_RERANK_GOVERNED_ANSWER_CONTRACT_PROFILE,
```

Add `PROFILE_METADATA` entry:

```python
TRI_RERANK_GOVERNED_ANSWER_CONTRACT_PROFILE: {
    "eval_only": True,
    "oracle_protected": True,
    "uses_fixture_expected_ids": True,
    "diagnostic_answer_contract": True,
    "uses_fixture_answer_expectations": False,
    "production_safe_evidence_contract": True,
    "combines_candidate_governance": True,
    "combines_rerank_injection": True,
    "does_not_expand_recall": True,
    "candidate_governance_mode": "tiered",
    "description": (
        "Reorders candidate-governed tri ids with the existing rerank/injection "
        "signal, without adding ids outside governed tri evidence, then renders "
        "a production-safe evidence contract."
    ),
},
```

- [ ] **Step 4: Add rerank-governed trace helper and profile evidence source**

In `memory2/eval_comprehensive_online.py`, add:

```python
def rerank_governed_evidence_order(
    governed_ids: Sequence[str],
    rerank_ids: Sequence[str],
) -> tuple[str, ...]:
    governed = tuple(str(item_id) for item_id in governed_ids if str(item_id))
    governed_set = set(governed)
    rerank = tuple(str(item_id) for item_id in rerank_ids if str(item_id))
    rerank_set = set(rerank)
    return tuple(
        [item_id for item_id in rerank if item_id in governed_set]
        + [item_id for item_id in governed if item_id not in rerank_set]
    )
```

Then add:

```python
def rerank_governed_tri_trace_for_case(case: EvalCase) -> dict[str, object]:
    governed_trace = governed_tri_trace_for_case(case)
    governed_ids = tuple(str(item) for item in governed_trace.get("ids", ()))
    if not governed_ids:
        trace = dict(governed_trace.get("trace", {}))
        trace["rerank_signal"] = {
            "rerank_profile": "chain_rerank_injection",
            "rerank_ids": [],
            "reranked_governed_ids": [],
            "recall_expanded": False,
            "reordered_count": 0,
        }
        return {"ids": (), "trace": trace}
    rerank_ids = tuple(evidence_ids_for_profile(case, "chain_rerank_injection"))
    governed_set = set(governed_ids)
    ordered_ids = rerank_governed_evidence_order(governed_ids, rerank_ids)
    trace = dict(governed_trace.get("trace", {}))
    trace["rerank_signal"] = {
        "rerank_profile": "chain_rerank_injection",
        "rerank_ids": list(rerank_ids),
        "reranked_governed_ids": list(ordered_ids),
        "recall_expanded": bool(set(ordered_ids) - governed_set),
        "reordered_count": sum(
            1
            for index, item_id in enumerate(ordered_ids)
            if index >= len(governed_ids) or governed_ids[index] != item_id
        ),
    }
    return {"ids": ordered_ids, "trace": trace}
```

In `evidence_ids_for_profile()`, add:

```python
if profile_name == TRI_RERANK_GOVERNED_ANSWER_CONTRACT_PROFILE:
    return tuple(rerank_governed_tri_trace_for_case(case).get("ids", ()))
```

In `profile_evidence_source()`, add:

```python
TRI_RERANK_GOVERNED_ANSWER_CONTRACT_PROFILE: (
    "tri_rerank_governed_answer_contract.reranked_governed_allowed_evidence_ids"
),
```

- [ ] **Step 5: Route the new profile through production-safe contract rendering**

In `ComprehensiveOnlineMemoryEngine.retrieve()`, update governed trace selection:

```python
if self.profile_name in {
    TRI_CANDIDATE_GOVERNANCE_PROFILE,
    TRI_GOVERNED_ANSWER_CONTRACT_PROFILE,
    TRI_RERANK_GOVERNED_ANSWER_CONTRACT_PROFILE,
}:
    governed_trace = (
        rerank_governed_tri_trace_for_case(self.case)
        if self.profile_name == TRI_RERANK_GOVERNED_ANSWER_CONTRACT_PROFILE
        else governed_tri_trace_for_case(self.case)
    )
    ids = list(tuple(governed_trace.get("ids", ())))
```

Update answer-contract profile condition to:

```python
if self.profile_name in {
    TRI_ANSWER_CONTRACT_PROFILE,
    *PRODUCTION_GOVERNED_ANSWER_CONTRACT_PROFILES,
}:
```

Update the production-safe branch condition to:

```python
if self.profile_name in PRODUCTION_GOVERNED_ANSWER_CONTRACT_PROFILES:
```

Build the contract with the current profile name:

```python
contract = build_production_governed_tri_evidence_contract(
    self.case,
    governed_trace,
    profile_name=self.profile_name,
)
```

Add rerank raw fields inside the production-safe raw payload:

```python
"combines_rerank_injection": (
    self.profile_name == TRI_RERANK_GOVERNED_ANSWER_CONTRACT_PROFILE
),
"rerank_signal": trace.get("rerank_signal", {}),
```

Add the same `combines_rerank_injection` field inside `raw["answer_contract"]`.

- [ ] **Step 6: Update scoring expectation and post-check profile set**

In `answer_expectation_for_profile()`, change:

```python
if profile_name == TRI_GOVERNED_ANSWER_CONTRACT_PROFILE:
```

to:

```python
if profile_name in PRODUCTION_GOVERNED_ANSWER_CONTRACT_PROFILES:
```

and use:

```python
governed_ids = evidence_ids_for_profile(case, profile_name)
```

In `_run_comprehensive_case()`, change the post-check guard to:

```python
if (
    spec.profile_name in PRODUCTION_GOVERNED_ANSWER_CONTRACT_PROFILES
    and isinstance(answer_contract, dict)
):
```

- [ ] **Step 7: Run GREEN focused tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_comprehensive_online_eval.py::test_rerank_governed_evidence_order_reorders_only_within_governed_set \
  tests/test_memory_comprehensive_online_eval.py::test_rerank_governed_profile_reorders_without_expanding_governed_ids \
  tests/test_memory_comprehensive_online_eval.py::test_rerank_governed_profile_never_expands_recall_on_p6o6_slice \
  tests/test_memory_comprehensive_online_eval.py::test_rerank_governed_profile_injects_production_safe_contract_block \
  tests/test_memory_comprehensive_online_eval.py::test_rerank_governed_profile_report_metadata_and_post_check_shadow \
  tests/test_memory_comprehensive_online_eval.py::test_rerank_governed_answer_expectation_is_grounding_only_not_oracle_terms \
  -q -p no:cacheprovider
```

Expected:

```text
6 passed
```

- [ ] **Step 8: Run broader comprehensive eval regression**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py -q -p no:cacheprovider
```

Expected: all tests in `tests/test_memory_comprehensive_online_eval.py` pass.

- [ ] **Step 9: Commit Task 2**

Run:

```bash
git add memory2/eval_comprehensive_online.py tests/test_memory_comprehensive_online_eval.py
git commit -m "feat: add rerank governed answer contract eval profile"
```

---

### Task 3: Add P6o-6 Fake-Provider CLI Matrix Smoke

**Files:**
- Modify: `tests/test_memory_comprehensive_online_cli.py`
- Modify: `tests/test_memory_comprehensive_online_eval.py`
- Modify: `memory2/eval_comprehensive_online.py`
- Modify: `scripts/run_memory_comprehensive_online_eval.py`

**Interfaces:**
- Consumes:
  - CLI `--balanced-small`, `--common-limit`, `--hard-limit`, `--profiles`, `--fake-provider`, `--real-memory-workspace`.
  - Profile metadata and post-check aggregate from Task 2.
- Produces:
  - Test `test_comprehensive_online_cli_p6o6_rerank_governed_fake_provider_matrix_shape()`.
  - Markdown metadata columns for `combines_rerank_injection` and `does_not_expand_recall`.
  - Fake-provider branch for `Evidence Contract: chain_tri_rerank_governed_answer_contract`.

- [ ] **Step 1: Write the failing Markdown metadata test**

Append this test to `tests/test_memory_comprehensive_online_eval.py`:

```python
def test_rerank_governed_profile_metadata_markdown_exposes_rerank_columns(
    tmp_path: Path,
) -> None:
    case, _governed_ids, _rerank_ids, _expected_order = (
        _case_with_rerank_governed_order_delta()
    )
    specs = build_comprehensive_run_specs(
        [case],
        profiles=("chain_tri_rerank_governed_answer_contract",),
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

    md_path = tmp_path / "report.md"
    write_comprehensive_online_markdown(report, md_path)
    markdown = md_path.read_text(encoding="utf-8")

    assert "combines_rerank_injection" in markdown
    assert "does_not_expand_recall" in markdown
    assert "chain_tri_rerank_governed_answer_contract" in markdown
```

- [ ] **Step 2: Run the RED Markdown metadata test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py::test_rerank_governed_profile_metadata_markdown_exposes_rerank_columns -q -p no:cacheprovider
```

Expected: FAIL because `_profile_metadata_markdown_section()` does not include the rerank columns.

- [ ] **Step 3: Extend Markdown metadata renderer**

In `_profile_metadata_markdown_section()` in `memory2/eval_comprehensive_online.py`, update the header to:

```python
(
    "| profile | eval_only | oracle_protected | uses_fixture_expected_ids | "
    "diagnostic_answer_contract | uses_fixture_answer_expectations | "
    "production_safe_evidence_contract | combines_candidate_governance | "
    "combines_rerank_injection | does_not_expand_recall |"
),
"| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
```

Add the two values to each row:

```python
_fmt(row.get("combines_rerank_injection")),
_fmt(row.get("does_not_expand_recall")),
```

- [ ] **Step 4: Update fake providers**

In `scripts/run_memory_comprehensive_online_eval.py`, change:

```python
elif "Evidence Contract: chain_tri_governed_answer_contract" in text:
```

to:

```python
elif "Evidence Contract: chain_tri_" in text:
```

In `tests/test_memory_comprehensive_online_eval.py`, make the same change in `ComprehensiveScriptedProvider.chat()`.

- [ ] **Step 5: Run GREEN Markdown metadata test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py::test_rerank_governed_profile_metadata_markdown_exposes_rerank_columns -q -p no:cacheprovider
```

Expected:

```text
1 passed
```

- [ ] **Step 6: Write the CLI integration smoke**

Append this test to `tests/test_memory_comprehensive_online_cli.py`:

```python
def test_comprehensive_online_cli_p6o6_rerank_governed_fake_provider_matrix_shape(
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
                "chain_tri_rerank_governed_answer_contract"
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
        "chain_tri_rerank_governed_answer_contract",
    }
    metadata = payload["metrics"]["profile_metadata"][
        "chain_tri_rerank_governed_answer_contract"
    ]
    assert metadata["production_safe_evidence_contract"] is True
    assert metadata["combines_rerank_injection"] is True
    assert metadata["does_not_expand_recall"] is True
    assert "chain_tri_rerank_governed_answer_contract" in markdown
    assert "combines_rerank_injection" in markdown
    assert "raw_prompt" not in markdown
    assert "full_answer" not in markdown
    assert "session_text" not in markdown
```

- [ ] **Step 7: Run the CLI integration smoke**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_comprehensive_online_cli.py::test_comprehensive_online_cli_p6o6_rerank_governed_fake_provider_matrix_shape -q -p no:cacheprovider
```

Expected:

```text
1 passed
```

If this fails for a real CLI/report gap, fix only:

```text
scripts/run_memory_comprehensive_online_eval.py
memory2/eval_comprehensive_online.py
```

- [ ] **Step 8: Run focused CLI regression**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_comprehensive_online_cli.py -q -p no:cacheprovider
```

Expected: all CLI tests pass.

- [ ] **Step 9: Commit Task 3**

Run:

```bash
git add tests/test_memory_comprehensive_online_cli.py tests/test_memory_comprehensive_online_eval.py scripts/run_memory_comprehensive_online_eval.py memory2/eval_comprehensive_online.py
git commit -m "test: cover p6o6 governed rerank online matrix"
```

---

### Task 4: Run P6o-6 Fake Smoke, Then Optional Real Matrix, And Record Docs

**Files:**
- Create, if real matrix is run:
  - `my_md/memory_optimization/eval_reports/p6o6_governed_rerank_small_online_v1/memory_comprehensive_online_eval.json`
  - `my_md/memory_optimization/eval_reports/p6o6_governed_rerank_small_online_v1/memory_comprehensive_online_eval.md`
- Modify:
  - `my_md/memory_optimization/README.md`
  - `my_md/memory_optimization/02-memory-quality-metrics.md`
  - `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
  - `task_plan.md`
  - `progress.md`

**Interfaces:**
- Consumes: Tasks 1-3 implementation and tests.
- Produces: P6o-6 bounded smoke/real conclusion and docs handoff to P6o-7.

- [ ] **Step 1: Run fake-provider 40-case smoke**

Run:

```bash
rm -rf /tmp/akashic-memory-p6o6-governed-rerank
mkdir -p /tmp/akashic-memory-p6o6-governed-rerank
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-p6o6-governed-rerank/workspace \
  --out-dir /tmp/akashic-memory-p6o6-governed-rerank/fake-reports \
  --fake-provider \
  --case-pack standard \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --profiles chain_tri_governed_answer_contract,chain_tri_rerank_governed_answer_contract \
  --prompt-variants baseline \
  --repeats 1 \
  --checkpoint-jsonl /tmp/akashic-memory-p6o6-governed-rerank/fake.checkpoint.jsonl \
  --real-memory-workspace /tmp/akashic-memory-p6o6-governed-rerank/empty-real-memory \
  --concurrency 2
```

Expected: command exits `0` and writes JSON/Markdown under `/tmp/akashic-memory-p6o6-governed-rerank/fake-reports/`.

- [ ] **Step 2: Assert fake-provider report shape**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path
path = Path('/tmp/akashic-memory-p6o6-governed-rerank/fake-reports/memory_comprehensive_online_eval.json')
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
    'chain_tri_rerank_governed_answer_contract',
}, m['profile_summaries'].keys()
meta = m['profile_metadata']['chain_tri_rerank_governed_answer_contract']
assert meta['production_safe_evidence_contract'] is True, meta
assert meta['combines_rerank_injection'] is True, meta
assert meta['does_not_expand_recall'] is True, meta
print('fake p6o6 report shape ok')
PY
```

Expected:

```text
fake p6o6 report shape ok
```

- [ ] **Step 3: Run real LLM matrix only if fake gate passes**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-p6o6-governed-rerank/real-workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o6_governed_rerank_small_online_v1 \
  --enable-real-llm \
  --case-pack standard \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --profiles chain_tri_governed_answer_contract,chain_tri_rerank_governed_answer_contract \
  --prompt-variants baseline \
  --repeats 1 \
  --checkpoint-jsonl /tmp/akashic-memory-p6o6-governed-rerank/real.checkpoint.jsonl \
  --real-memory-workspace /tmp/akashic-memory-p6o6-governed-rerank/empty-real-memory \
  --concurrency 2
```

Expected if provider is available: command exits `0` and writes sanitized committed report files. If provider returns an infra failure, stop and rebuild only a checkpoint report with infra failures excluded; do not claim a full P6o-6 result.

Infra-failure checkpoint-only recovery command:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-p6o6-governed-rerank/checkpoint-workspace \
  --out-dir /tmp/akashic-memory-p6o6-governed-rerank/checkpoint-report \
  --checkpoint-report-only \
  --exclude-infra-failures \
  --checkpoint-jsonl /tmp/akashic-memory-p6o6-governed-rerank/real.checkpoint.jsonl \
  --enable-real-llm \
  --real-memory-workspace /tmp/akashic-memory-p6o6-governed-rerank/empty-real-memory
```

If this path is used, keep the checkpoint-only report under `/tmp`, update docs with `partial_due_to_infra_failure = True`, and do not commit it as the formal P6o-6 real result.

- [ ] **Step 4: Assert real report integrity**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path
path = Path('my_md/memory_optimization/eval_reports/p6o6_governed_rerank_small_online_v1/memory_comprehensive_online_eval.json')
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
rerank = summaries['chain_tri_rerank_governed_answer_contract']
assert float(rerank['answer_rule_pass_rate']) >= float(base['answer_rule_pass_rate']) - 5.0, (base, rerank)
assert float(rerank['memory_grounding_pass_rate']) == 100.0, rerank
assert float(rerank['forbidden_violation_rate']) <= float(base['forbidden_violation_rate']), (base, rerank)
assert float(rerank['avg_total_token_count']) <= float(base['avg_total_token_count']) * 1.10, (base, rerank)
shadow = m['answer_post_check_shadow']
for key in (
    'needs_retry_count',
    'forbidden_boundary_included_count',
    'missing_likely_relevant_context_count',
    'stale_evidence_included_count',
    'conflict_evidence_included_count',
    'insufficient_fallback_missing_count',
):
    assert int(shadow[key]) == 0, (key, shadow)
for profile in ('chain_tri_governed_answer_contract', 'chain_tri_rerank_governed_answer_contract'):
    row = m['profile_summaries'][profile]
    print(profile, row['answer_success_count'], row['case_count'], row['answer_rule_pass_rate'], row['memory_grounding_pass_rate'], row['forbidden_violation_rate'], row['avg_total_token_count'])
PY
```

Expected: prints the two profile rows and exits `0`.

- [ ] **Step 5: Assert committed report privacy**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path
base = Path('my_md/memory_optimization/eval_reports/p6o6_governed_rerank_small_online_v1')
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
    for forbidden in (
        'answer_debug',
        'api_key',
    ):
        assert forbidden not in text, (name, forbidden)
print('p6o6 report privacy ok')
PY
```

Expected:

```text
p6o6 report privacy ok
```

- [ ] **Step 6: Update documentation with measured data**

Add a new P6o-6 note to `my_md/memory_optimization/README.md`, `02-memory-quality-metrics.md`, and `04-memory-plugin-experiment-roadmap.md` with this structure:

```markdown
### Phase 6o6 Governed Rerank Signal

P6o-6 tests only one added signal: `chain_tri_rerank_governed_answer_contract`.
It reorders `chain_tri_governed_answer_contract` evidence using the existing
`chain_rerank_injection` signal, but does not add evidence ids outside the
candidate-governed tri set. This is still eval/shadow-only and oracle-protected
through P6o-2 candidate governance; it is not production traffic.

Results:

| profile | answer | grounding | forbidden | avg tokens |
| --- | ---: | ---: | ---: | ---: |
| chain_tri_governed_answer_contract | <fill from report> | <fill from report> | <fill from report> | <fill from report> |
| chain_tri_rerank_governed_answer_contract | <fill from report> | <fill from report> | <fill from report> | <fill from report> |

Conclusion:

- If rerank-governed matches the governed baseline, rerank ordering can proceed to the next signal-expansion gate.
- If it lowers answer rate or raises forbidden, keep P6o-5 governed as the best candidate and inspect which rerank-ordered ids changed the context priority.
- The next P6o-6 slice should test version-boundary fields separately, not graph or all-on.
```

Replace every `<fill from report>` before committing.

Update `task_plan.md` and `progress.md` with:

```markdown
## 2026-07-28 Memory P6o6 Governed Rerank Signal

- Plan: `docs/superpowers/plans/2026-07-28-memory-p6o6-governed-rerank-signal.md`.
- Scope: eval-only `chain_tri_rerank_governed_answer_contract`; no production behavior change.
- Fake-provider gate: <fill>.
- Real LLM result: <fill if run; otherwise state not run and why>.
- Current conclusion: <fill>.
- Next step: version-boundary governed slice only after this result is interpreted.
```

- [ ] **Step 7: Run final verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_answer_contract.py \
  tests/test_memory_comprehensive_online_eval.py \
  tests/test_memory_comprehensive_online_cli.py \
  -q -p no:cacheprovider
python -m compileall -q memory2 scripts tests
git diff --check
```

Expected: pytest passes, compileall exits `0`, diff check exits `0`.

- [ ] **Step 8: Commit Task 4**

Run:

```bash
git add \
  my_md/memory_optimization/README.md \
  my_md/memory_optimization/02-memory-quality-metrics.md \
  my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md \
  my_md/memory_optimization/eval_reports/p6o6_governed_rerank_small_online_v1/memory_comprehensive_online_eval.json \
  my_md/memory_optimization/eval_reports/p6o6_governed_rerank_small_online_v1/memory_comprehensive_online_eval.md \
  task_plan.md \
  progress.md
git commit -m "docs: record p6o6 governed rerank signal"
```

If no real LLM matrix was run, omit the report paths and use:

```bash
git add \
  my_md/memory_optimization/README.md \
  my_md/memory_optimization/02-memory-quality-metrics.md \
  my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md \
  task_plan.md \
  progress.md
git commit -m "docs: record p6o6 governed rerank smoke"
```

---

## Self-Review

**Spec coverage:** The plan implements only the first P6o-6 slice: `tri governed` vs `tri + rerank governed`. It explicitly excludes graph, version-boundary, retry, production prompt changes, production retriever changes, and production writes. It includes TDD, fake-provider gate, optional bounded real LLM matrix, privacy boundaries, docs, and final verification.

**Placeholder scan:** The only placeholder-like strings are in Task 4 documentation templates, and that task explicitly requires replacing every `<fill from report>` before committing. There are no `TBD`, `TODO`, `implement later`, or undefined plan steps.

**Type consistency:** The new profile name is consistently `chain_tri_rerank_governed_answer_contract`. The new constant is `TRI_RERANK_GOVERNED_ANSWER_CONTRACT_PROFILE`. The new helpers are `rerank_governed_evidence_order(governed_ids: Sequence[str], rerank_ids: Sequence[str]) -> tuple[str, ...]` and `rerank_governed_tri_trace_for_case(case: EvalCase) -> dict[str, object]`. `build_production_governed_tri_evidence_contract()` keeps its existing positional parameters and adds a keyword-only `profile_name` with a backward-compatible default.

**Execution boundary:** Tasks 1-3 are code/test only and can be committed independently. Task 4 runs the fake-provider gate before any real LLM calls and records either real data or an explicit not-run boundary.
