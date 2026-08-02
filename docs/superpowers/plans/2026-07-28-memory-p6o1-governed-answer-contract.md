# Memory P6o1 Governed Answer Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an eval-only `chain_tri_governed_answer_contract` profile that combines candidate-governed tri evidence with answer-contract prompting, without changing production memory behavior.

**Architecture:** Keep production retrieval, writing, AgentLoop, ToolExecutor, Reasoner, and prompt behavior unchanged. Extend the existing eval-only answer contract helper so it can render a contract over externally supplied governed evidence ids, then wire a new optional comprehensive-online profile that uses `governed_tri_evidence_ids_for_case(case)` as the allowed evidence set. This P6o-1 plan only adds the eval profile, fake-provider smoke, metadata, and docs; real LLM A/B remains a later P6o step.

**Tech Stack:** Python 3.14, dataclasses, existing `memory2.eval_answer_contract`, existing `memory2.eval_comprehensive_online`, pytest, existing comprehensive online eval CLI.

## Global Constraints

- Work only in `/home/jjh/git_work/akashic-agent/.worktrees/memory-next`.
- Do not modify production `AgentLoop`, `Reasoner`, `ToolExecutor`, `ToolRegistry`, memory write behavior, production prompt behavior, or the old `Retriever.retrieve()` return contract.
- `chain_tri_governed_answer_contract` is eval-only and must be marked diagnostic/oracle-assisted.
- P6o-1 must not run real LLM. It should only add the eval profile, focused tests, fake-provider smoke, and docs that make the next real A/B runnable.
- Do not commit raw prompts, raw session text, raw memory summaries, full answers, API keys, or `answer_debug` artifacts.
- Existing uncommitted docs edits in `my_md/memory_optimization/` belong to the current documentation thread. Do not revert them or mix them into P6o-1 implementation commits; handle them in Task 0.
- Do not push without explicit user instruction.

---

## File Structure

- Modify `memory2/eval_answer_contract.py`: add governed-contract builder support without importing `memory2.eval_comprehensive_online`.
- Modify `memory2/eval_comprehensive_online.py`: register `chain_tri_governed_answer_contract`, route its evidence ids through existing candidate governance, and render a governed answer contract block in the eval memory engine.
- Modify `tests/test_memory_answer_contract.py`: pure tests for governed contract ids, profile name rendering, expected-id preservation, and forbidden ids.
- Modify `tests/test_memory_comprehensive_online_eval.py`: integration tests for optional profile registration, retrieve block, report metadata, and fake-provider behavior.
- Modify `scripts/run_memory_comprehensive_online_eval.py`: fake-provider answer selection recognizes the governed answer contract block.
- Modify `my_md/memory_optimization/README.md`, `my_md/memory_optimization/02-memory-quality-metrics.md`, `my_md/memory_optimization/03-memory-governance-design.md`, and `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`: record P6o-1 profile shape and P6o-5 real A/B handoff.
- Modify `progress.md` and `task_plan.md`: record plan execution and verification.

---

### Task 0: Preserve Existing Documentation Follow-Up Notes

**Files:**
- Modify: no code files
- Existing docs: `my_md/memory_optimization/README.md`, `my_md/memory_optimization/02-memory-quality-metrics.md`, `my_md/memory_optimization/03-memory-governance-design.md`, `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`

**Interfaces:**
- Consumes: current uncommitted documentation edits that record P6n/P6o follow-up direction.
- Produces: a clean baseline before implementation commits, with the current docs saved separately.

- [ ] **Step 1: Inspect current status**

Run:

```bash
git status --short
```

Expected before P6o-1 implementation starts:

```text
 M my_md/memory_optimization/02-memory-quality-metrics.md
 M my_md/memory_optimization/03-memory-governance-design.md
 M my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md
 M my_md/memory_optimization/README.md
```

If additional files are dirty, stop and inspect them before continuing. Do not revert user changes.

- [ ] **Step 2: Verify documentation-only diff is clean**

Run:

```bash
git diff --check
```

Expected: exit `0`.

- [ ] **Step 3: Commit existing docs separately**

Run:

```bash
git add my_md/memory_optimization/README.md my_md/memory_optimization/02-memory-quality-metrics.md my_md/memory_optimization/03-memory-governance-design.md my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md
git commit -m "docs: record memory p6o follow-up direction"
```

Expected: commit succeeds locally. This keeps the current follow-up notes separate from P6o-1 code changes.

---

### Task 1: Extend Pure Answer Contract Helper For Governed Evidence

**Files:**
- Modify: `memory2/eval_answer_contract.py`
- Test: `tests/test_memory_answer_contract.py`

**Interfaces:**
- Consumes: `EvalCase`, existing `tri_retrieval.fused_ids`, fixture `answer_expectations`, and caller-supplied `governed_evidence_ids`.
- Produces:
  - `GOVERNED_TRI_ANSWER_CONTRACT_PROFILE = "chain_tri_governed_answer_contract"`.
  - `build_governed_tri_answer_contract(case: EvalCase, governed_evidence_ids: object) -> AnswerContract`.
  - `tri_governed_answer_contract_evidence_ids(case: EvalCase, governed_evidence_ids: object) -> tuple[str, ...]`.
  - `render_answer_contract_block(contract: AnswerContract)` uses `contract.profile_name` instead of a hardcoded profile name.
  - `AnswerContract.governance_dropped_ids: tuple[str, ...]`, separate from `forbidden_ids`.

- [ ] **Step 1: Add focused failing pure tests**

Append to `tests/test_memory_answer_contract.py`:

```python
def test_governed_contract_uses_supplied_allowed_ids_and_marks_dropped_tri_ids() -> None:
    case = _case_with_should_not_in_tri()
    base_contract = build_tri_answer_contract(case)
    governed_ids = tuple(
        item_id
        for item_id in base_contract.allowed_evidence_ids
        if item_id in set(str(item) for item in case.expectations["should_recall_ids"])
    )

    contract = build_governed_tri_answer_contract(case, governed_ids)

    assert contract.profile_name == "chain_tri_governed_answer_contract"
    assert contract.allowed_evidence_ids == governed_ids
    assert set(contract.must_use_ids) == set(
        str(item) for item in case.expectations["should_recall_ids"]
    )
    assert set(contract.forbidden_ids) == (
        set(base_contract.tri_ids)
        & set(str(item) for item in case.expectations["should_not_recall_ids"])
    )
    assert set(contract.governance_dropped_ids) == (
        set(base_contract.tri_ids) - set(governed_ids) - set(contract.forbidden_ids)
    )
    assert set(contract.forbidden_ids).isdisjoint(contract.allowed_evidence_ids)
    assert set(contract.governance_dropped_ids).isdisjoint(contract.allowed_evidence_ids)


def test_governed_contract_evidence_ids_preserve_governed_order_and_tri_membership() -> None:
    case = _case_with_should_not_in_tri()
    base_contract = build_tri_answer_contract(case)
    governed_ids = tuple(reversed(base_contract.allowed_evidence_ids))
    expected_ids = set(str(item) for item in case.expectations["should_recall_ids"])

    ids = tri_governed_answer_contract_evidence_ids(case, governed_ids)

    assert ids == tuple(
        item_id
        for item_id in governed_ids
        if item_id in set(base_contract.tri_ids)
        and item_id not in set(base_contract.forbidden_ids)
    )
    assert expected_ids <= set(ids)


def test_render_governed_contract_uses_profile_name() -> None:
    case = _case_with_should_not_in_tri()
    contract = build_governed_tri_answer_contract(
        case,
        build_tri_answer_contract(case).allowed_evidence_ids,
    )

    text = render_answer_contract_block(contract)

    assert "Answer Contract: chain_tri_governed_answer_contract" in text
    assert "must_use_memory_ids" in text
    assert "governance_dropped_memory_ids" in text
    assert "allowed_evidence:" in text
```

Add these imports at the top of the same file:

```python
from memory2.eval_answer_contract import (
    build_governed_tri_answer_contract,
    build_tri_answer_contract,
    render_answer_contract_block,
    tri_governed_answer_contract_evidence_ids,
    tri_answer_contract_evidence_ids,
)
```

- [ ] **Step 2: Run pure tests to verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_answer_contract.py::test_governed_contract_uses_supplied_allowed_ids_and_marks_dropped_tri_ids tests/test_memory_answer_contract.py::test_governed_contract_evidence_ids_preserve_governed_order_and_tri_membership tests/test_memory_answer_contract.py::test_render_governed_contract_uses_profile_name -q -p no:cacheprovider
```

Expected: fail with missing `build_governed_tri_answer_contract` / `tri_governed_answer_contract_evidence_ids`.

- [ ] **Step 3: Implement governed helper support**

Modify `memory2/eval_answer_contract.py`:

```python
TRI_ANSWER_CONTRACT_PROFILE = "chain_tri_answer_contract"
GOVERNED_TRI_ANSWER_CONTRACT_PROFILE = "chain_tri_governed_answer_contract"


def build_tri_answer_contract(case: EvalCase) -> AnswerContract:
    return _build_answer_contract(
        case,
        profile_name=TRI_ANSWER_CONTRACT_PROFILE,
        governed_evidence_ids=None,
    )


def build_governed_tri_answer_contract(
    case: EvalCase,
    governed_evidence_ids: object,
) -> AnswerContract:
    return _build_answer_contract(
        case,
        profile_name=GOVERNED_TRI_ANSWER_CONTRACT_PROFILE,
        governed_evidence_ids=governed_evidence_ids,
    )


def _build_answer_contract(
    case: EvalCase,
    *,
    profile_name: str,
    governed_evidence_ids: object | None,
) -> AnswerContract:
    tri_ids = _ids_from_trace(case, "tri_retrieval", "fused_ids")
    expected_ids = _string_tuple(case.expectations.get("should_recall_ids", ()))
    should_not_ids = set(_string_tuple(case.expectations.get("should_not_recall_ids", ())))
    if governed_evidence_ids is None:
        allowed_ids = tuple(item_id for item_id in tri_ids if item_id not in should_not_ids)
    else:
        governed_ids = _string_tuple(governed_evidence_ids)
        tri_set = set(tri_ids)
        allowed_ids = tuple(
            item_id
            for item_id in governed_ids
            if item_id in tri_set and item_id not in should_not_ids
        )
    allowed_set = set(allowed_ids)
    forbidden_ids = tuple(item_id for item_id in tri_ids if item_id in should_not_ids)
    governance_dropped_ids = tuple(
        item_id
        for item_id in tri_ids
        if item_id not in allowed_set and item_id not in should_not_ids
    )
    answer_expectations = case.expectations.get("answer_expectations") or {}
    summaries = _summaries_for_ids(case, allowed_ids)
    return AnswerContract(
        profile_name=profile_name,
        diagnostic_eval_only=True,
        tri_ids=tri_ids,
        must_use_ids=tuple(item_id for item_id in expected_ids if item_id in allowed_ids),
        allowed_evidence_ids=allowed_ids,
        forbidden_ids=forbidden_ids,
        governance_dropped_ids=governance_dropped_ids,
        required_terms=_string_tuple(answer_expectations.get("expected_answer_contains", ())),
        required_term_groups=_term_groups(
            answer_expectations.get("expected_answer_contains_any", ())
        ),
        forbidden_terms=_string_tuple(
            answer_expectations.get("forbidden_answer_contains", ())
        ),
        evidence_summaries=summaries,
    )
```

Add:

```python
def tri_governed_answer_contract_evidence_ids(
    case: EvalCase,
    governed_evidence_ids: object,
) -> tuple[str, ...]:
    return build_governed_tri_answer_contract(
        case,
        governed_evidence_ids,
    ).allowed_evidence_ids
```

Change the first rendered line in `render_answer_contract_block()`:

```python
f"Answer Contract: {contract.profile_name}",
```

Also add a distinct rendered line after `forbidden_memory_ids`:

```python
"governance_dropped_memory_ids: " + ", ".join(contract.governance_dropped_ids),
```

Update the `AnswerContract` dataclass by adding:

```python
governance_dropped_ids: tuple[str, ...]
```

- [ ] **Step 4: Run pure tests to verify GREEN**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_answer_contract.py -q -p no:cacheprovider
```

Expected: all tests in `tests/test_memory_answer_contract.py` pass.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add memory2/eval_answer_contract.py tests/test_memory_answer_contract.py
git commit -m "feat: add governed tri answer contract helper"
```

Expected: commit succeeds locally.

---

### Task 2: Wire Eval-Only Governed Answer Contract Profile

**Files:**
- Modify: `memory2/eval_comprehensive_online.py`
- Test: `tests/test_memory_comprehensive_online_eval.py`

**Interfaces:**
- Consumes: `build_governed_tri_answer_contract(case, governed_ids)` from Task 1 and existing `governed_tri_evidence_ids_for_case(case)`.
- Produces:
  - `TRI_GOVERNED_ANSWER_CONTRACT_PROFILE = "chain_tri_governed_answer_contract"`.
  - Optional eval profile metadata with candidate-governance and answer-contract boundaries.
  - `profile_evidence_source("chain_tri_governed_answer_contract") == "tri_governed_answer_contract.governed_allowed_evidence_ids"`.

- [ ] **Step 1: Add failing integration tests**

Append to `tests/test_memory_comprehensive_online_eval.py` near the existing answer-contract tests:

```python
def _case_with_tri_governance_drop():
    for case in (
        build_quantitative_eval_cases(case_set="common", limit=20, case_pack="standard")
        + build_quantitative_eval_cases(case_set="hard", limit=20, case_pack="standard")
    ):
        tri_ids = set(evidence_ids_for_profile(case, "chain_tri_retrieval"))
        governed_ids = set(
            evidence_ids_for_profile(case, "chain_tri_candidate_governance")
        )
        if tri_ids - governed_ids:
            return case
    raise AssertionError("fixture must include at least one governed tri drop")


def test_tri_governed_answer_contract_profile_is_optional_eval_only() -> None:
    case = _case_with_tri_governance_drop()

    specs = build_comprehensive_run_specs(
        [case],
        profiles=("chain_tri_governed_answer_contract",),
        prompt_variants=("baseline",),
        repeats=1,
    )

    assert len(specs) == 1
    assert evidence_ids_for_profile(case, "chain_tri_governed_answer_contract")
    assert evidence_ids_for_profile(
        case,
        "chain_tri_governed_answer_contract",
    ) == evidence_ids_for_profile(case, "chain_tri_candidate_governance")
    assert set(evidence_ids_for_profile(case, "chain_tri_retrieval")) > set(
        evidence_ids_for_profile(case, "chain_tri_governed_answer_contract")
    )
    assert (
        profile_evidence_source("chain_tri_governed_answer_contract")
        == "tri_governed_answer_contract.governed_allowed_evidence_ids"
    )


def test_tri_governed_answer_contract_profile_injects_governed_contract_block(
    tmp_path: Path,
) -> None:
    case = _case_with_tri_governance_drop()
    engine = ComprehensiveOnlineMemoryEngine(
        case,
        profile_name="chain_tri_governed_answer_contract",
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

    assert "Answer Contract: chain_tri_governed_answer_contract" in result.text_block
    assert "allowed_evidence:" in result.text_block
    assert "forbidden_memory_ids:" in result.text_block
    assert "governance_dropped_memory_ids:" in result.text_block
    assert result.raw["governance_dropped_ids"]
    assert result.raw["evidence_source"] == (
        "tri_governed_answer_contract.governed_allowed_evidence_ids"
    )
    assert result.raw["answer_contract"]["diagnostic_eval_only"] is True
    assert result.raw["answer_contract"]["combines_candidate_governance"] is True
```

- [ ] **Step 2: Run integration tests to verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py::test_tri_governed_answer_contract_profile_is_optional_eval_only tests/test_memory_comprehensive_online_eval.py::test_tri_governed_answer_contract_profile_injects_governed_contract_block -q -p no:cacheprovider
```

Expected: fail with unknown profile or missing raw metadata.

- [ ] **Step 3: Register constants, imports, and metadata**

Modify imports in `memory2/eval_comprehensive_online.py`:

```python
from memory2.eval_answer_contract import (
    build_governed_tri_answer_contract,
    build_tri_answer_contract,
    render_answer_contract_block,
    tri_answer_contract_evidence_ids,
)
```

Add constants and optional profile:

```python
TRI_GOVERNED_ANSWER_CONTRACT_PROFILE = "chain_tri_governed_answer_contract"
OPTIONAL_ANSWER_QUALITY_PROFILES: tuple[str, ...] = (
    TRI_CANDIDATE_GOVERNANCE_PROFILE,
    TRI_ANSWER_CONTRACT_PROFILE,
    TRI_GOVERNED_ANSWER_CONTRACT_PROFILE,
)
```

Add metadata:

```python
TRI_GOVERNED_ANSWER_CONTRACT_PROFILE: {
    "eval_only": True,
    "oracle_protected": True,
    "uses_fixture_expected_ids": True,
    "diagnostic_answer_contract": True,
    "uses_fixture_answer_expectations": True,
    "combines_candidate_governance": True,
    "description": (
        "Combines candidate-governed tri ids with the diagnostic answer "
        "contract to test whether input filtering plus answer constraints "
        "can preserve answer quality while reducing forbidden risk."
    ),
},
```

- [ ] **Step 4: Route evidence ids and source labels**

In `evidence_ids_for_profile()` add this before the unknown-profile check:

```python
if profile_name == TRI_GOVERNED_ANSWER_CONTRACT_PROFILE:
    return governed_tri_evidence_ids_for_case(case)
```

In `profile_evidence_source()` add:

```python
TRI_GOVERNED_ANSWER_CONTRACT_PROFILE: (
    "tri_governed_answer_contract.governed_allowed_evidence_ids"
),
```

- [ ] **Step 5: Render the governed answer contract block**

In `ComprehensiveOnlineMemoryEngine.retrieve()`, update the answer-contract branch:

```python
if self.profile_name in {
    TRI_ANSWER_CONTRACT_PROFILE,
    TRI_GOVERNED_ANSWER_CONTRACT_PROFILE,
}:
    if self.profile_name == TRI_GOVERNED_ANSWER_CONTRACT_PROFILE:
        governed_ids = governed_tri_evidence_ids_for_case(self.case)
        contract = build_governed_tri_answer_contract(self.case, governed_ids)
        combines_candidate_governance = True
    else:
        contract = build_tri_answer_contract(self.case)
        combines_candidate_governance = False
    self.used_memory_ids = list(contract.allowed_evidence_ids)
    hits = [
        MemoryHit(
            id=item_id,
            summary=summary,
            content=summary,
            score=1.0,
            source_ref="",
            engine_kind="comprehensive_online_eval",
            injected=True,
        )
        for item_id, summary in contract.evidence_summaries
    ]
    self.last_text_block = render_answer_contract_block(contract)
    return MemoryEngineRetrieveResult(
        text_block=self.last_text_block,
        hits=hits,
        raw={
            "ids": list(contract.allowed_evidence_ids),
            "must_use_ids": list(contract.must_use_ids),
            "forbidden_ids": list(contract.forbidden_ids),
            "governance_dropped_ids": list(contract.governance_dropped_ids),
            "evidence_source": profile_evidence_source(self.profile_name),
            "answer_contract": {
                "diagnostic_eval_only": contract.diagnostic_eval_only,
                "combines_candidate_governance": combines_candidate_governance,
                "required_terms": list(contract.required_terms),
                "required_term_groups": [
                    list(group) for group in contract.required_term_groups
                ],
                "forbidden_terms": list(contract.forbidden_terms),
            },
        },
    )
```

- [ ] **Step 6: Run focused integration tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_answer_contract.py tests/test_memory_comprehensive_online_eval.py::test_tri_governed_answer_contract_profile_is_optional_eval_only tests/test_memory_comprehensive_online_eval.py::test_tri_governed_answer_contract_profile_injects_governed_contract_block -q -p no:cacheprovider
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit Task 2**

Run:

```bash
git add memory2/eval_comprehensive_online.py tests/test_memory_comprehensive_online_eval.py
git commit -m "feat: add governed tri answer contract eval profile"
```

Expected: commit succeeds locally.

---

### Task 3: Fake-Provider Smoke And Report Metadata

**Files:**
- Modify: `tests/test_memory_comprehensive_online_eval.py`
- Modify: `scripts/run_memory_comprehensive_online_eval.py`
- Modify: `memory2/eval_comprehensive_online.py`

**Interfaces:**
- Consumes: `chain_tri_governed_answer_contract` profile from Task 2.
- Produces:
  - Fake provider handles the governed answer contract block.
  - Markdown metadata exposes `combines_candidate_governance`.
  - Fake-provider smoke can run a 40-case / 5-profile / 200-call matrix without real LLM.

- [ ] **Step 1: Add report metadata regression test**

Append to `tests/test_memory_comprehensive_online_eval.py`:

```python
def test_tri_governed_answer_contract_report_records_combined_eval_metadata(
    tmp_path: Path,
) -> None:
    case = build_quantitative_eval_cases(
        case_set="common",
        limit=1,
        case_pack="standard",
    )[0]
    specs = build_comprehensive_run_specs(
        [case],
        profiles=("chain_tri_governed_answer_contract",),
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
        "chain_tri_governed_answer_contract"
    ]
    assert metadata["eval_only"] is True
    assert metadata["oracle_protected"] is True
    assert metadata["uses_fixture_expected_ids"] is True
    assert metadata["diagnostic_answer_contract"] is True
    assert metadata["uses_fixture_answer_expectations"] is True
    assert metadata["combines_candidate_governance"] is True

    md_path = tmp_path / "report.md"
    write_comprehensive_online_markdown(report, md_path)
    markdown = md_path.read_text(encoding="utf-8")
    assert "chain_tri_governed_answer_contract" in markdown
    assert "combines_candidate_governance" in markdown
```

- [ ] **Step 2: Run metadata test to verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py::test_tri_governed_answer_contract_report_records_combined_eval_metadata -q -p no:cacheprovider
```

Expected: fail because Markdown does not expose `combines_candidate_governance`.

- [ ] **Step 3: Update fake-provider answer selection**

In both `tests/test_memory_comprehensive_online_eval.py::ComprehensiveScriptedProvider.chat()` and `scripts/run_memory_comprehensive_online_eval.py::ScriptedComprehensiveOnlineProvider.chat()`, add the governed branch before the generic answer-contract branch:

```python
elif "Answer Contract: chain_tri_governed_answer_contract" in text:
    answer = "根据 governed Answer Contract，应使用治理后的 allowed_evidence，并避免 forbidden_terms。"
```

Keep the existing branch for `"Answer Contract: chain_tri_answer_contract"` unchanged.

- [ ] **Step 4: Extend metadata Markdown columns**

Modify `_profile_metadata_markdown_section()` in `memory2/eval_comprehensive_online.py` so the table header includes:

```python
(
    "| profile | eval_only | oracle_protected | uses_fixture_expected_ids | "
    "diagnostic_answer_contract | uses_fixture_answer_expectations | "
    "combines_candidate_governance |"
),
"| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
```

Add the row value:

```python
_fmt(row.get("combines_candidate_governance")),
```

- [ ] **Step 5: Run fake-provider smoke**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-p6o1-governed-answer-contract-fake/workspace \
  --out-dir /tmp/akashic-memory-p6o1-governed-answer-contract-fake/reports \
  --case-pack standard \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --profiles chain_memory_base,chain_tri_retrieval,chain_tri_candidate_governance,chain_tri_answer_contract,chain_tri_governed_answer_contract \
  --prompt-variants baseline \
  --repeats 1 \
  --fake-provider \
  --timeout-s 60 \
  --concurrency 1
```

Expected report facts:

```text
case_count = 200
unique_case_count = 40
profile_count = 5
real_llm_enabled = False
provider_error_count = 0
timeout_count = 0
chain_tri_governed_answer_contract appears in profile summary
combines_candidate_governance appears in Markdown metadata table
```

- [ ] **Step 6: Run focused regression**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_answer_contract.py tests/test_memory_comprehensive_online_eval.py tests/test_memory_comprehensive_online_cli.py -q -p no:cacheprovider
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit Task 3**

Run:

```bash
git add memory2/eval_comprehensive_online.py scripts/run_memory_comprehensive_online_eval.py tests/test_memory_comprehensive_online_eval.py
git commit -m "test: cover governed answer contract eval metadata"
```

Expected: commit succeeds locally.

---

### Task 4: Documentation And Final Verification

**Files:**
- Modify: `my_md/memory_optimization/README.md`
- Modify: `my_md/memory_optimization/02-memory-quality-metrics.md`
- Modify: `my_md/memory_optimization/03-memory-governance-design.md`
- Modify: `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
- Modify: `progress.md`
- Modify: `task_plan.md`

**Interfaces:**
- Consumes: fake-provider smoke from Task 3.
- Produces: P6o-1 documented boundary and handoff criteria for later P6o real LLM A/B.

- [ ] **Step 1: Update memory optimization docs**

Add to `my_md/memory_optimization/README.md`:

```markdown
- Phase 6o1-governed-answer-contract-profile：新增 eval-only `chain_tri_governed_answer_contract`，组合 candidate-governed tri evidence 和 Answer Contract 渲染。P6o-1 只验证 profile wiring、metadata、fake-provider smoke 和报告链路，不运行真实 LLM，不改变生产 `AgentLoop`、真实召回、真实写入或 prompt。下一轮真实 A/B 才比较 answer_rate、grounding_rate、forbidden_rate 和 token 成本。
```

Add to `my_md/memory_optimization/02-memory-quality-metrics.md` under the P6n/P6o section:

```markdown
### Phase 6o1 Governed Answer Contract Profile

P6o-1 adds only the eval profile and fake-provider smoke for `chain_tri_governed_answer_contract`. It does not produce real LLM quality evidence. The profile uses `chain_tri_candidate_governance` evidence ids as allowed evidence, then renders an Answer Contract over those ids. This isolates wiring and report correctness before spending real LLM calls.

Next real A/B criteria remain: answer_rate close to or above `75.0%`, grounding_rate `100.0%`, forbidden_rate below `12.5%`, and no obvious token blow-up.
```

Add to `my_md/memory_optimization/03-memory-governance-design.md`:

```markdown
P6o-1 implementation boundary: `chain_tri_governed_answer_contract` is still oracle-assisted because candidate governance protects fixture expected ids and the answer contract uses fixture answer expectations. It is useful for testing whether the combined shape can be evaluated, not for production activation.
```

Add to `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`:

```markdown
P6o-1 complete criteria: profile registered, governed ids reused as allowed evidence, contract rendered with governed profile name, eval-only metadata visible in JSON and Markdown, 200-row fake-provider smoke passes. Real LLM A/B is intentionally deferred.
```

- [ ] **Step 2: Update planning records**

Append to `task_plan.md`:

```markdown
## 2026-07-28 Memory P6o1 Governed Answer Contract

Goal: add eval-only `chain_tri_governed_answer_contract` wiring so the next real A/B can test candidate governance plus answer contract.

1. Extend pure answer contract helper for governed allowed ids - pending
2. Register governed answer contract profile in comprehensive online eval - pending
3. Run fake-provider smoke and metadata regression - pending
4. Update docs and commit locally without push - pending
```

Append to `progress.md` with:

```markdown
## 2026-07-28 Memory P6o1 Governed Answer Contract Plan

- Plan path: `docs/superpowers/plans/2026-07-28-memory-p6o1-governed-answer-contract.md`
- Scope: eval-only profile wiring, fake-provider smoke, docs, no real LLM.
- Production boundary: no AgentLoop, Reasoner, ToolExecutor, memory write, production prompt, or old `Retriever.retrieve()` contract changes.
```

- [ ] **Step 3: Run final verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_answer_contract.py tests/test_memory_comprehensive_online_eval.py tests/test_memory_comprehensive_online_cli.py tests/test_memory_tri_candidate_governance.py tests/test_memory_tri_retrieval_failure_attribution.py -q -p no:cacheprovider
```

Expected: all selected tests pass.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m compileall -q memory2 scripts tests
```

Expected: exit `0`.

Run:

```bash
git diff --check
```

Expected: exit `0`.

- [ ] **Step 4: Commit Task 4**

Run:

```bash
git add memory2/eval_answer_contract.py memory2/eval_comprehensive_online.py scripts/run_memory_comprehensive_online_eval.py tests/test_memory_answer_contract.py tests/test_memory_comprehensive_online_eval.py my_md/memory_optimization/README.md my_md/memory_optimization/02-memory-quality-metrics.md my_md/memory_optimization/03-memory-governance-design.md my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md progress.md task_plan.md
git add -f docs/superpowers/plans/2026-07-28-memory-p6o1-governed-answer-contract.md
git commit -m "feat: add governed tri answer contract eval profile"
```

Expected: commit succeeds locally. Do not push unless the user explicitly asks.

---

## Final Acceptance Criteria

- `chain_tri_governed_answer_contract` is available only as an optional eval profile.
- The profile evidence ids equal existing `chain_tri_candidate_governance` ids.
- The profile renders `Answer Contract: chain_tri_governed_answer_contract`.
- JSON and Markdown metadata mark the profile as eval-only, oracle-protected, candidate-governance combined, and diagnostic answer-contract assisted.
- Fake-provider smoke produces a 200-row / 40-unique-case / 5-profile report with no provider errors or timeouts.
- No real LLM run is part of P6o-1.
- Production retrieval, memory writes, tool execution, AgentLoop, Reasoner, and production prompt behavior are unchanged.
- Focused pytest, compileall, and `git diff --check` pass.

## Self-Review Notes

- Spec coverage: this plan covers the P6o-1 scope only: eval-only combined profile, helper extension, report metadata, fake-provider smoke, docs, and verification.
- Scope check: real LLM A/B, production-safe risk scoring, risk-tiered filtering, and answer-after-check retry are intentionally deferred to later P6o steps.
- Placeholder scan: no task uses open-ended markers or generic "add tests" instructions; each task includes file paths, code snippets, commands, and expected results.
- Type consistency: the plan consistently uses `chain_tri_governed_answer_contract`, `TRI_GOVERNED_ANSWER_CONTRACT_PROFILE`, `build_governed_tri_answer_contract()`, and `tri_governed_answer_contract_evidence_ids()`.
