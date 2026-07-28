# Memory P6o3 Production-Safe Evidence Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the eval-only governed tri answer-contract path from fixture answer expectations to a production-safe evidence contract built from candidate tiers and memory metadata.

**Architecture:** Keep production retrieval, writing, AgentLoop, ToolExecutor, Reasoner, and default prompt behavior unchanged. Add a new pure evidence-contract helper in `memory2/eval_answer_contract.py` that consumes P6o-2 governed tri trace metadata and memory item fields, then switch only the eval-only `chain_tri_governed_answer_contract` profile to render that production-safe contract. The existing `chain_tri_answer_contract` remains an oracle diagnostic control and continues using fixture answer expectations.

**Tech Stack:** Python 3.14, dataclasses, existing `memory2.eval_answer_contract`, existing `memory2.eval_comprehensive_online`, existing P6o-2 `governed_tri_trace_for_case()`, pytest, fake-provider eval harness.

## Global Constraints

- Work only in `/home/jjh/git_work/akashic-agent/.worktrees/memory-next`.
- P6o-3 is eval/shadow-only. It must not run real LLM.
- Do not modify production `AgentLoop`, `Reasoner`, `ToolExecutor`, `ToolRegistry`, memory write behavior, production prompt behavior, or the old `Retriever.retrieve()` return contract.
- Do not change `chain_tri_answer_contract`; it remains a diagnostic/oracle profile that uses fixture answer expectations.
- `chain_tri_governed_answer_contract` must stop using fixture `answer_expectations` fields such as `expected_answer_contains`, `expected_answer_contains_any`, and `forbidden_answer_contains`.
- `chain_tri_governed_answer_contract` may still reuse P6o-2 eval-only governed tri ids and candidate tier trace. P6o-3 removes oracle answer-term dependencies, not the P6o-2 candidate-governance fixture harness.
- The production-safe evidence contract must expose canonical fields with these exact names in raw/rendered output: `allowed_evidence`, `likely_relevant_evidence`, `stale_warning`, `conflict_warning`, `active_version`, `insufficient_evidence_fallback`, and `forbidden_boundary`. The implementation may also expose id-suffixed aliases for compatibility, but tests must cover the canonical names.
- Do not commit raw prompts, raw session text, raw memory summaries beyond existing fixture summaries, full answers, API keys, or `answer_debug` artifacts.
- Do not push without explicit user instruction.

---

## File Structure

- Modify `memory2/eval_answer_contract.py`: add pure `ProductionEvidenceContract` dataclass, `build_production_governed_tri_evidence_contract()`, `render_production_evidence_contract_block()`, and helpers that derive fields from governed trace + memory item metadata without fixture answer expectations.
- Modify `tests/test_memory_answer_contract.py`: pure tests for production-safe field derivation, no fixture answer-term dependency, privacy boundary, and rendered block field names.
- Modify `memory2/eval_comprehensive_online.py`: switch only `TRI_GOVERNED_ANSWER_CONTRACT_PROFILE` to the production-safe evidence contract, update metadata, raw fields, and Markdown metadata visibility while preserving the old diagnostic `TRI_ANSWER_CONTRACT_PROFILE`.
- Modify `tests/test_memory_comprehensive_online_eval.py`: integration tests that governed profile metadata no longer advertises fixture answer expectations, raw output exposes production-safe fields, and rendered text no longer contains required-term / forbidden-term oracle fields.
- Modify `my_md/memory_optimization/README.md`, `my_md/memory_optimization/02-memory-quality-metrics.md`, `my_md/memory_optimization/03-memory-governance-design.md`, `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`: record P6o-3 boundary, tests, and P6o-4 handoff.
- Modify `progress.md` and `task_plan.md`: record plan execution and verification.

---

### Task 0: Confirm Clean P6o-3 Baseline

**Files:**
- Modify: none

**Interfaces:**
- Consumes: current `memory-next` worktree after P6o-2.
- Produces: known clean baseline for P6o-3 commits.

- [x] **Step 1: Inspect status**

Run:

```bash
git status --short
```

Expected: no tracked output. Ignored scratch files under `.superpowers/` are acceptable.

- [x] **Step 2: Inspect recent commits**

Run:

```bash
git log --oneline -8
```

Expected to include:

```text
0202665 docs: record tiered candidate governance handoff
87efed0 test: align governed contract assertion with tiered semantics
5dc8877 test: report tiered tri candidate governance metrics
aef192b feat: use tiered governance for tri eval profiles
f1f7524 feat: add tiered candidate governance mode
3849fe1 feat: classify candidate governance risk tiers
```

---

### Task 1: Add Pure Production-Safe Evidence Contract Helper

**Files:**
- Modify: `memory2/eval_answer_contract.py`
- Test: `tests/test_memory_answer_contract.py`

**Interfaces:**
- Consumes:
  - `build_governed_tri_answer_contract(case, governed_evidence_ids)`
  - governed trace info shaped as `{"ids": tuple[str, ...], "trace": dict[str, object]}`
  - P6o-2 trace fields `candidate_risk_tiers`, `candidate_risk_tier_counts`, `tiered_deleted_risks_by_reason`
- Produces:
  - `ProductionEvidenceContract`
  - `build_production_governed_tri_evidence_contract(case: EvalCase, governed_trace_info: object) -> ProductionEvidenceContract`
  - `render_production_evidence_contract_block(contract: ProductionEvidenceContract) -> str`
  - no dependency on fixture `answer_expectations`
  - canonical fields `allowed_evidence`, `likely_relevant_evidence`, `stale_warning`, `conflict_warning`, `active_version`, `insufficient_evidence_fallback`, and `forbidden_boundary`

- [x] **Step 1: Add failing pure production-contract tests**

Append to `tests/test_memory_answer_contract.py`:

```python
def test_production_governed_contract_uses_tiered_metadata_not_answer_expectations() -> None:
    case = _case_with_should_not_in_tri()
    governed_trace_info = {
        "ids": ("target", "weak", "conflict", "gap"),
        "trace": {
            "candidate_governance_mode": "tiered",
            "candidate_risk_tiers": [
                {
                    "candidate_id": "target",
                    "tier": "allow",
                    "risks": (),
                    "lane": "semantic",
                },
                {
                    "candidate_id": "weak",
                    "tier": "downgrade",
                    "risks": ("weak_source_ref",),
                    "lane": "semantic",
                },
                {
                    "candidate_id": "conflict",
                    "tier": "requires_review",
                    "risks": ("conflict_candidate",),
                    "lane": "semantic",
                },
                {
                    "candidate_id": "gap",
                    "tier": "requires_review",
                    "risks": ("insufficient_evidence",),
                    "lane": "semantic",
                },
                {
                    "candidate_id": "blocked",
                    "tier": "delete",
                    "risks": ("forbidden_candidate",),
                    "lane": "semantic",
                },
                {
                    "candidate_id": "old",
                    "tier": "delete",
                    "risks": ("superseded_candidate",),
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
                    "id": "conflict",
                    "summary": "conflicting evidence",
                    "status": "active",
                    "source_ref": "telegram:1:2",
                    "conflict": True,
                },
                {
                    "id": "gap",
                    "summary": "insufficient evidence",
                    "status": "active",
                    "source_ref": "telegram:1:3",
                    "insufficient_evidence": True,
                },
                {
                    "id": "blocked",
                    "summary": "blocked evidence",
                    "status": "active",
                    "source_ref": "telegram:1:4",
                    "forbidden": True,
                },
                {
                    "id": "old",
                    "summary": "old superseded evidence",
                    "status": "superseded",
                    "source_ref": "telegram:1:5",
                },
            ],
        },
        expectations={
            **case.expectations,
            "answer_expectations": {
                "expected_answer_contains": ["ORACLE_TERM"],
                "expected_answer_contains_any": [["ORACLE_GROUP"]],
                "forbidden_answer_contains": ["ORACLE_FORBIDDEN"],
            },
        },
    )

    contract = build_production_governed_tri_evidence_contract(
        case,
        governed_trace_info,
    )

    assert contract.profile_name == "chain_tri_governed_answer_contract"
    assert contract.production_safe is True
    assert contract.uses_fixture_answer_expectations is False
    assert contract.allowed_evidence == ("target", "weak", "conflict", "gap")
    assert contract.likely_relevant_evidence == ("target", "weak")
    assert contract.stale_warning == ("old",)
    assert contract.conflict_warning == ("conflict",)
    assert contract.active_version == ("target", "weak", "conflict", "gap")
    assert contract.forbidden_boundary == ("blocked",)
    assert contract.allowed_evidence_ids == ("target", "weak", "conflict", "gap")
    assert contract.likely_relevant_evidence_ids == ("target", "weak")
    assert contract.downgrade_ids == ("weak",)
    assert contract.requires_review_ids == ("conflict", "gap")
    assert contract.conflict_warning_ids == ("conflict",)
    assert contract.insufficient_evidence_ids == ("gap",)
    assert contract.insufficient_evidence_fallback is True
    assert contract.forbidden_boundary_ids == ("blocked",)
    assert contract.stale_warning_ids == ("old",)
    assert contract.active_version_ids == ("target", "weak", "conflict", "gap")
    assert contract.required_terms == ()
    assert contract.required_term_groups == ()
    assert contract.forbidden_terms == ()
```

Also add imports:

```python
from dataclasses import replace

from memory2.eval_answer_contract import (
    build_production_governed_tri_evidence_contract,
    render_production_evidence_contract_block,
    ...
)
```

- [x] **Step 2: Run pure production-contract test to verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_answer_contract.py::test_production_governed_contract_uses_tiered_metadata_not_answer_expectations -q -p no:cacheprovider
```

Expected: fail because `build_production_governed_tri_evidence_contract` does not exist.

- [x] **Step 3: Add failing render privacy test**

Append to `tests/test_memory_answer_contract.py`:

```python
def test_render_production_evidence_contract_is_structured_and_not_oracle_terms() -> None:
    case = _case_with_should_not_in_tri()
    case = replace(
        case,
        expectations={
            **case.expectations,
            "answer_expectations": {
                "expected_answer_contains": ["ORACLE_TERM"],
                "expected_answer_contains_any": [["ORACLE_GROUP"]],
                "forbidden_answer_contains": ["ORACLE_FORBIDDEN"],
            },
        },
    )
    contract = build_production_governed_tri_evidence_contract(
        case,
        {
            "ids": build_tri_answer_contract(case).allowed_evidence_ids,
            "trace": {"candidate_governance_mode": "tiered", "candidate_risk_tiers": []},
        },
    )

    text = render_production_evidence_contract_block(contract)

    assert "Evidence Contract: chain_tri_governed_answer_contract" in text
    assert "production_safe=true" in text
    assert "allowed_evidence:" in text
    assert "likely_relevant_evidence_ids:" in text
    assert "stale_warning_ids:" in text
    assert "conflict_warning_ids:" in text
    assert "active_version_ids:" in text
    assert "insufficient_evidence_fallback:" in text
    assert "forbidden_boundary_ids:" in text
    assert "required_terms:" not in text
    assert "required_term_groups:" not in text
    assert "forbidden_terms:" not in text
    assert "ORACLE_TERM" not in text
    assert "ORACLE_GROUP" not in text
    assert "ORACLE_FORBIDDEN" not in text
    assert case.setup["query"] not in text
```

- [x] **Step 4: Run render test to verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_answer_contract.py::test_render_production_evidence_contract_is_structured_and_not_oracle_terms -q -p no:cacheprovider
```

Expected: fail because `render_production_evidence_contract_block` does not exist.

- [x] **Step 5: Implement `ProductionEvidenceContract` and builder**

In `memory2/eval_answer_contract.py`, add these imports:

```python
from collections.abc import Mapping
from typing import Any
```

Add dataclass after `AnswerContract`:

```python
@dataclass(frozen=True)
class ProductionEvidenceContract:
    profile_name: str
    diagnostic_eval_only: bool
    production_safe: bool
    uses_fixture_answer_expectations: bool
    candidate_governance_mode: str
    allowed_evidence: tuple[str, ...]
    likely_relevant_evidence: tuple[str, ...]
    stale_warning: tuple[str, ...]
    conflict_warning: tuple[str, ...]
    active_version: tuple[str, ...]
    forbidden_boundary: tuple[str, ...]
    allowed_evidence_ids: tuple[str, ...]
    likely_relevant_evidence_ids: tuple[str, ...]
    downgrade_ids: tuple[str, ...]
    requires_review_ids: tuple[str, ...]
    stale_warning_ids: tuple[str, ...]
    conflict_warning_ids: tuple[str, ...]
    active_version_ids: tuple[str, ...]
    insufficient_evidence_ids: tuple[str, ...]
    insufficient_evidence_fallback: bool
    forbidden_boundary_ids: tuple[str, ...]
    deleted_evidence_ids: tuple[str, ...]
    required_terms: tuple[str, ...] = ()
    required_term_groups: tuple[tuple[str, ...], ...] = ()
    forbidden_terms: tuple[str, ...] = ()
    evidence_summaries: tuple[tuple[str, str], ...] = ()
    raw_prompt: str = ""
    raw_answer: str = ""
```

Add public builder:

```python
def build_production_governed_tri_evidence_contract(
    case: EvalCase,
    governed_trace_info: object,
) -> ProductionEvidenceContract:
    trace_info = dict(governed_trace_info) if isinstance(governed_trace_info, Mapping) else {}
    trace = trace_info.get("trace", {})
    trace = dict(trace) if isinstance(trace, Mapping) else {}
    allowed_ids = _string_tuple(trace_info.get("ids", ()))
    tier_records = _tier_records_by_id(trace.get("candidate_risk_tiers", ()))
    by_id = _memory_items_by_id(case)

    downgrade_ids = _ids_with_tier(allowed_ids, tier_records, "downgrade")
    requires_review_ids = _ids_with_tier(allowed_ids, tier_records, "requires_review")
    conflict_warning_ids = _ids_with_risk(allowed_ids, tier_records, "conflict_candidate")
    insufficient_evidence_ids = tuple(
        item_id
        for item_id in allowed_ids
        if _record_has_risk(tier_records.get(item_id, {}), "insufficient_evidence")
        or _item_truthy(by_id.get(item_id, {}), "insufficient_evidence")
    )
    deleted_ids = tuple(
        item_id
        for item_id, record in tier_records.items()
        if str(record.get("tier") or "") == "delete"
    )
    forbidden_boundary_ids = tuple(
        item_id
        for item_id in deleted_ids
        if _record_has_risk(tier_records.get(item_id, {}), "forbidden_candidate")
        or _item_truthy(by_id.get(item_id, {}), "forbidden")
        or _item_truthy(by_id.get(item_id, {}), "forbidden_candidate")
    )
    stale_warning_ids = tuple(
        item_id
        for item_id in deleted_ids
        if _record_has_risk(tier_records.get(item_id, {}), "superseded_candidate")
        or str(by_id.get(item_id, {}).get("status") or "").lower() == "superseded"
    )
    active_version_ids = tuple(
        item_id
        for item_id in allowed_ids
        if str(by_id.get(item_id, {}).get("status") or "active").lower() == "active"
    )
    likely_relevant_ids = tuple(
        item_id
        for item_id in allowed_ids
        if item_id not in requires_review_ids
    )
    return ProductionEvidenceContract(
        profile_name=GOVERNED_TRI_ANSWER_CONTRACT_PROFILE,
        diagnostic_eval_only=True,
        production_safe=True,
        uses_fixture_answer_expectations=False,
        candidate_governance_mode=str(trace.get("candidate_governance_mode") or "tiered"),
        allowed_evidence=allowed_ids,
        likely_relevant_evidence=likely_relevant_ids,
        stale_warning=stale_warning_ids,
        conflict_warning=conflict_warning_ids,
        active_version=active_version_ids,
        forbidden_boundary=forbidden_boundary_ids,
        allowed_evidence_ids=allowed_ids,
        likely_relevant_evidence_ids=likely_relevant_ids,
        downgrade_ids=downgrade_ids,
        requires_review_ids=requires_review_ids,
        stale_warning_ids=stale_warning_ids,
        conflict_warning_ids=conflict_warning_ids,
        active_version_ids=active_version_ids,
        insufficient_evidence_ids=insufficient_evidence_ids,
        insufficient_evidence_fallback=not allowed_ids or bool(insufficient_evidence_ids),
        forbidden_boundary_ids=forbidden_boundary_ids,
        deleted_evidence_ids=deleted_ids,
        evidence_summaries=_summaries_for_ids(case, allowed_ids),
    )
```

Add private helpers:

```python
def _memory_items_by_id(case: EvalCase) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("id") or item.get("memory_id") or ""): dict(item)
        for item in case.setup.get("memory_items", ())
        if isinstance(item, Mapping)
    }


def _tier_records_by_id(records: object) -> dict[str, dict[str, Any]]:
    if not isinstance(records, (list, tuple)):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, Mapping):
            continue
        candidate_id = str(record.get("candidate_id") or "")
        if candidate_id:
            result[candidate_id] = dict(record)
    return result


def _ids_with_tier(
    ids: tuple[str, ...],
    records: dict[str, dict[str, Any]],
    tier: str,
) -> tuple[str, ...]:
    return tuple(
        item_id
        for item_id in ids
        if str(records.get(item_id, {}).get("tier") or "allow") == tier
    )


def _ids_with_risk(
    ids: tuple[str, ...],
    records: dict[str, dict[str, Any]],
    risk: str,
) -> tuple[str, ...]:
    return tuple(item_id for item_id in ids if _record_has_risk(records.get(item_id, {}), risk))


def _record_has_risk(record: Mapping[str, Any], risk: str) -> bool:
    risks = record.get("risks", ())
    return isinstance(risks, (list, tuple, set)) and risk in {str(item) for item in risks}


def _item_truthy(item: Mapping[str, Any], key: str) -> bool:
    return item.get(key) is True
```

- [x] **Step 6: Implement production evidence contract renderer**

Add to `memory2/eval_answer_contract.py`:

```python
def render_production_evidence_contract_block(
    contract: ProductionEvidenceContract,
) -> str:
    lines = [
        f"Evidence Contract: {contract.profile_name}",
        "diagnostic_eval_only=true",
        "production_safe=true",
        "请只根据 allowed_evidence 回答；如果 insufficient_evidence_fallback=true，请说明证据不足。",
        "不要使用 forbidden_boundary_ids 中的记忆；stale_warning_ids 和 conflict_warning_ids 只能作为风险提示。",
        "allowed_evidence: " + ", ".join(contract.allowed_evidence),
        "likely_relevant_evidence: " + ", ".join(contract.likely_relevant_evidence),
        "stale_warning: " + ", ".join(contract.stale_warning),
        "conflict_warning: " + ", ".join(contract.conflict_warning),
        "active_version: " + ", ".join(contract.active_version),
        "forbidden_boundary: " + ", ".join(contract.forbidden_boundary),
        "allowed_evidence_ids: " + ", ".join(contract.allowed_evidence_ids),
        "likely_relevant_evidence_ids: " + ", ".join(contract.likely_relevant_evidence_ids),
        "downgrade_ids: " + ", ".join(contract.downgrade_ids),
        "requires_review_ids: " + ", ".join(contract.requires_review_ids),
        "stale_warning_ids: " + ", ".join(contract.stale_warning_ids),
        "conflict_warning_ids: " + ", ".join(contract.conflict_warning_ids),
        "active_version_ids: " + ", ".join(contract.active_version_ids),
        "insufficient_evidence_ids: " + ", ".join(contract.insufficient_evidence_ids),
        "insufficient_evidence_fallback: "
        + ("true" if contract.insufficient_evidence_fallback else "false"),
        "forbidden_boundary_ids: " + ", ".join(contract.forbidden_boundary_ids),
        "deleted_evidence_ids: " + ", ".join(contract.deleted_evidence_ids),
        "allowed_evidence:",
    ]
    for item_id, summary in contract.evidence_summaries:
        lines.append(f"- memory_id={item_id}; summary={summary}")
    return "\n".join(lines)
```

- [x] **Step 7: Run Task 1 tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_answer_contract.py -q -p no:cacheprovider
```

Expected: all answer contract tests pass.

- [x] **Step 8: Commit Task 1**

Run:

```bash
git add memory2/eval_answer_contract.py tests/test_memory_answer_contract.py
git commit -m "feat: add production safe evidence contract helper"
```

Expected: commit succeeds locally.

---

### Task 2: Switch Governed Eval Profile To Production-Safe Contract

**Files:**
- Modify: `memory2/eval_comprehensive_online.py`
- Test: `tests/test_memory_comprehensive_online_eval.py`

**Interfaces:**
- Consumes:
  - `build_production_governed_tri_evidence_contract(case, governed_trace_info)`
  - `render_production_evidence_contract_block(contract)`
  - `governed_tri_trace_for_case(case)`
- Produces:
  - `chain_tri_governed_answer_contract` raw output with `production_safe_evidence_contract = True`
  - metadata marks `uses_fixture_answer_expectations = False`
  - `answer_expectation_for_profile(case, "chain_tri_governed_answer_contract")` no longer uses fixture answer terms for scoring
  - rendered governed contract no longer includes `required_terms`, `required_term_groups`, or `forbidden_terms`

- [x] **Step 1: Add failing integration tests**

Append near existing governed answer-contract tests in `tests/test_memory_comprehensive_online_eval.py`:

```python
def test_governed_answer_contract_profile_uses_production_safe_contract(
    tmp_path: Path,
) -> None:
    case = _case_with_tiered_tri_candidate()
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

    assert "Evidence Contract: chain_tri_governed_answer_contract" in result.text_block
    assert "production_safe=true" in result.text_block
    assert "allowed_evidence:" in result.text_block
    assert "likely_relevant_evidence_ids:" in result.text_block
    assert "forbidden_boundary_ids:" in result.text_block
    assert "required_terms:" not in result.text_block
    assert "required_term_groups:" not in result.text_block
    assert "forbidden_terms:" not in result.text_block
    assert result.raw["answer_contract"]["production_safe"] is True
    assert result.raw["answer_contract"]["production_safe_evidence_contract"] is True
    assert result.raw["answer_contract"]["uses_fixture_answer_expectations"] is False
    assert "allowed_evidence" in result.raw["answer_contract"]
    assert "likely_relevant_evidence" in result.raw["answer_contract"]
    assert "stale_warning" in result.raw["answer_contract"]
    assert "conflict_warning" in result.raw["answer_contract"]
    assert "active_version" in result.raw["answer_contract"]
    assert "forbidden_boundary" in result.raw["answer_contract"]
    assert "required_terms" not in result.raw["answer_contract"]
    assert "required_term_groups" not in result.raw["answer_contract"]
    assert "forbidden_terms" not in result.raw["answer_contract"]
```

Add:

```python
def test_governed_answer_contract_report_metadata_marks_no_fixture_answer_expectations(
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
    assert metadata["production_safe_evidence_contract"] is True
    assert metadata["uses_fixture_answer_expectations"] is False

    md_path = tmp_path / "report.md"
    write_comprehensive_online_markdown(report, md_path)
    markdown = md_path.read_text(encoding="utf-8")
    assert "production_safe_evidence_contract" in markdown
```

Add:

```python
def test_governed_answer_contract_scoring_expectation_is_not_oracle_terms() -> None:
    case = build_quantitative_eval_cases(
        case_set="common",
        limit=1,
        case_pack="standard",
    )[0]
    oracle = answer_expectation_for_profile(case, "chain_tri_answer_contract")

    expectation = answer_expectation_for_profile(
        case,
        "chain_tri_governed_answer_contract",
    )

    assert oracle.expected_answer_contains or oracle.expected_answer_contains_any
    assert expectation.expected_answer_contains == ()
    assert expectation.expected_answer_contains_any == ()
    assert expectation.forbidden_answer_contains == ()
    assert expectation.expected_memory_ids == evidence_ids_for_profile(
        case,
        "chain_tri_governed_answer_contract",
    )
    assert expectation.grounding_required is True
```

- [x] **Step 2: Run integration tests to verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py::test_governed_answer_contract_profile_uses_production_safe_contract tests/test_memory_comprehensive_online_eval.py::test_governed_answer_contract_report_metadata_marks_no_fixture_answer_expectations tests/test_memory_comprehensive_online_eval.py::test_governed_answer_contract_scoring_expectation_is_not_oracle_terms -q -p no:cacheprovider
```

Expected: fail because governed profile still renders old `Answer Contract` with fixture answer terms and scoring still uses oracle answer expectations.

- [x] **Step 3: Switch imports and metadata**

In `memory2/eval_comprehensive_online.py`, change imports from `memory2.eval_answer_contract` to include:

```python
    build_production_governed_tri_evidence_contract,
    render_production_evidence_contract_block,
```

In `PROFILE_METADATA[TRI_GOVERNED_ANSWER_CONTRACT_PROFILE]`, change:

```python
"uses_fixture_answer_expectations": False,
"production_safe_evidence_contract": True,
```

Keep:

```python
"diagnostic_answer_contract": True,
"combines_candidate_governance": True,
"candidate_governance_mode": "tiered",
```

Update the description to say production-safe evidence contract and avoid saying fixture answer expectations.

Also update `_profile_metadata_lines()` in `memory2/eval_comprehensive_online.py` so Markdown can expose the new metadata key. Change the header string from:

```python
"diagnostic_answer_contract | uses_fixture_answer_expectations | "
"combines_candidate_governance |"
```

to:

```python
"diagnostic_answer_contract | uses_fixture_answer_expectations | "
"production_safe_evidence_contract | combines_candidate_governance |"
```

Change the separator from:

```python
"| --- | ---: | ---: | ---: | ---: | ---: | ---: |"
```

to:

```python
"| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
```

Add this row value between `uses_fixture_answer_expectations` and `combines_candidate_governance`:

```python
_fmt(row.get("production_safe_evidence_contract")),
```

- [x] **Step 4: Switch governed profile retrieve branch**

In `ComprehensiveOnlineMemoryEngine.retrieve()`, inside:

```python
if self.profile_name == TRI_GOVERNED_ANSWER_CONTRACT_PROFILE:
```

replace the governed old answer-contract construction with:

```python
assert governed_trace is not None
trace = dict(governed_trace.get("trace", {}))
contract = build_production_governed_tri_evidence_contract(
    self.case,
    governed_trace,
)
combines_candidate_governance = True
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
self.last_text_block = render_production_evidence_contract_block(contract)
raw = {
    "ids": list(contract.allowed_evidence_ids),
    "evidence_source": profile_evidence_source(self.profile_name),
    "candidate_governance_mode": trace.get("candidate_governance_mode"),
    "candidate_risk_tier_counts": trace.get("candidate_risk_tier_counts", {}),
    "accepted_candidate_risk_tier_counts": trace.get(
        "accepted_candidate_risk_tier_counts",
        {},
    ),
    "tiered_deleted_risks_by_reason": trace.get(
        "tiered_deleted_risks_by_reason",
        {},
    ),
    "candidate_risk_tiers": trace.get("candidate_risk_tiers", []),
    "answer_contract": {
        "diagnostic_eval_only": contract.diagnostic_eval_only,
        "production_safe": contract.production_safe,
        "production_safe_evidence_contract": True,
        "uses_fixture_answer_expectations": (
            contract.uses_fixture_answer_expectations
        ),
        "combines_candidate_governance": combines_candidate_governance,
        "candidate_governance_mode": contract.candidate_governance_mode,
        "allowed_evidence": list(contract.allowed_evidence),
        "likely_relevant_evidence": list(
            contract.likely_relevant_evidence
        ),
        "stale_warning": list(contract.stale_warning),
        "conflict_warning": list(contract.conflict_warning),
        "active_version": list(contract.active_version),
        "forbidden_boundary": list(contract.forbidden_boundary),
        "allowed_evidence_ids": list(contract.allowed_evidence_ids),
        "likely_relevant_evidence_ids": list(
            contract.likely_relevant_evidence_ids
        ),
        "downgrade_ids": list(contract.downgrade_ids),
        "requires_review_ids": list(contract.requires_review_ids),
        "stale_warning_ids": list(contract.stale_warning_ids),
        "conflict_warning_ids": list(contract.conflict_warning_ids),
        "active_version_ids": list(contract.active_version_ids),
        "insufficient_evidence_ids": list(contract.insufficient_evidence_ids),
        "insufficient_evidence_fallback": contract.insufficient_evidence_fallback,
        "forbidden_boundary_ids": list(contract.forbidden_boundary_ids),
        "deleted_evidence_ids": list(contract.deleted_evidence_ids),
    },
}
return MemoryEngineRetrieveResult(
    text_block=self.last_text_block,
    hits=hits,
    raw=raw,
)
```

Leave the existing `TRI_ANSWER_CONTRACT_PROFILE` branch using `build_tri_answer_contract()`.

- [x] **Step 5: Make governed scoring expectation non-oracle**

In `memory2/eval_comprehensive_online.py`, update `answer_expectation_for_profile()` so governed production-safe profile scoring no longer uses fixture answer terms. Add before the version-provenance branch:

```python
    if profile_name == TRI_GOVERNED_ANSWER_CONTRACT_PROFILE:
        governed_ids = governed_tri_evidence_ids_for_case(case)
        return AnswerExpectation(
            expected_memory_ids=governed_ids,
            expected_language=expectation.expected_language,
            grounding_required=bool(governed_ids),
        )
```

This keeps grounding/language checks but removes `expected_answer_contains`, `expected_answer_contains_any`, and `forbidden_answer_contains` for the governed profile. Do not change `TRI_ANSWER_CONTRACT_PROFILE`.

- [x] **Step 6: Update fake providers for the new governed contract header**

In `tests/test_memory_comprehensive_online_eval.py`, update `ComprehensiveScriptedProvider.chat()`:

```python
elif "Evidence Contract: chain_tri_governed_answer_contract" in text:
    answer = "根据 production-safe evidence contract，应使用 allowed_evidence，并在证据不足时说明无法确认。"
elif "Answer Contract: chain_tri_governed_answer_contract" in text:
    answer = "根据 governed Answer Contract，应使用治理后的 allowed_evidence，并避免 forbidden_terms。"
```

In `scripts/run_memory_comprehensive_online_eval.py`, update `ScriptedComprehensiveOnlineProvider.chat()` the same way:

```python
elif "Evidence Contract: chain_tri_governed_answer_contract" in text:
    answer = "根据 production-safe evidence contract，应使用 allowed_evidence，并在证据不足时说明无法确认。"
elif "Answer Contract: chain_tri_governed_answer_contract" in text:
    answer = "根据 governed Answer Contract，应使用治理后的 allowed_evidence，并避免 forbidden_terms。"
```

The new fake answer must not mention `forbidden_terms`, because the production-safe governed contract no longer renders that oracle field.

- [x] **Step 7: Update old governed-profile tests**

In `tests/test_memory_comprehensive_online_eval.py`, update old assertions that currently require:

```python
assert "Answer Contract: chain_tri_governed_answer_contract" in result.text_block
assert "forbidden_memory_ids:" in result.text_block
assert "governance_dropped_memory_ids:" in result.text_block
assert result.raw["forbidden_ids"]
assert result.raw["answer_contract"]["diagnostic_eval_only"] is True
assert result.raw["answer_contract"]["combines_candidate_governance"] is True
assert metadata["uses_fixture_answer_expectations"] is True
```

to the P6o-3 semantics:

```python
assert "Evidence Contract: chain_tri_governed_answer_contract" in result.text_block
assert "forbidden_boundary_ids:" in result.text_block
assert "deleted_evidence_ids:" in result.text_block
assert result.raw["answer_contract"]["diagnostic_eval_only"] is True
assert result.raw["answer_contract"]["production_safe"] is True
assert result.raw["answer_contract"]["production_safe_evidence_contract"] is True
assert result.raw["answer_contract"]["uses_fixture_answer_expectations"] is False
assert result.raw["answer_contract"]["combines_candidate_governance"] is True
assert metadata["uses_fixture_answer_expectations"] is False
assert metadata["production_safe_evidence_contract"] is True
```

- [x] **Step 8: Run focused integration tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_answer_contract.py tests/test_memory_comprehensive_online_eval.py::test_governed_answer_contract_profile_uses_production_safe_contract tests/test_memory_comprehensive_online_eval.py::test_governed_answer_contract_report_metadata_marks_no_fixture_answer_expectations tests/test_memory_comprehensive_online_eval.py::test_governed_answer_contract_scoring_expectation_is_not_oracle_terms tests/test_memory_comprehensive_online_eval.py::test_tri_governed_answer_contract_profile_injects_governed_contract_block tests/test_memory_comprehensive_online_eval.py::test_tri_governed_answer_contract_report_records_combined_eval_metadata -q -p no:cacheprovider
```

Expected: all selected tests pass.

- [x] **Step 9: Commit Task 2**

Run:

```bash
git add memory2/eval_comprehensive_online.py tests/test_memory_comprehensive_online_eval.py scripts/run_memory_comprehensive_online_eval.py
git commit -m "feat: use production safe evidence contract for governed tri eval"
```

Expected: commit succeeds locally.

---

### Task 3: Add Fake-Provider Smoke For P6o-3 Metadata And Privacy

**Files:**
- Test: `tests/test_memory_comprehensive_online_eval.py`

**Interfaces:**
- Consumes:
  - `run_comprehensive_online_eval()`
  - `write_comprehensive_online_markdown()`
  - `chain_tri_governed_answer_contract` production-safe metadata
- Produces:
  - smoke coverage proving no raw prompt/full answer/session text and no oracle answer terms are exposed for the governed production-safe profile.

- [x] **Step 1: Add failing fake-provider smoke test**

Append to `tests/test_memory_comprehensive_online_eval.py`:

```python
def test_p6o3_governed_contract_fake_provider_smoke_is_private(
    tmp_path: Path,
) -> None:
    cases = (
        build_quantitative_eval_cases(case_set="common", limit=2, case_pack="standard")
        + build_quantitative_eval_cases(case_set="hard", limit=2, case_pack="standard")
    )
    specs = build_comprehensive_run_specs(
        cases,
        profiles=(
            "chain_tri_retrieval",
            "chain_tri_candidate_governance",
            "chain_tri_governed_answer_contract",
        ),
        prompt_variants=("baseline",),
        repeats=1,
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
    md_path = tmp_path / "report.md"
    write_comprehensive_online_markdown(report, md_path)
    markdown = md_path.read_text(encoding="utf-8")

    assert report.metrics["case_count"] == 12
    assert report.metrics["real_llm_enabled"] is False
    assert report.metrics["provider_error_count"] == 0
    assert report.metrics["timeout_count"] == 0
    metadata = report.metrics["profile_metadata"][
        "chain_tri_governed_answer_contract"
    ]
    assert metadata["production_safe_evidence_contract"] is True
    assert metadata["uses_fixture_answer_expectations"] is False
    governed_rows = [
        row
        for row in report.case_records
        if row["profile_name"] == "chain_tri_governed_answer_contract"
    ]
    assert governed_rows
    assert all(row["passed"] is True for row in governed_rows)
    assert all(row["failures"] == [] for row in governed_rows)
    assert "production_safe_evidence_contract" in markdown
    assert "raw_prompt" not in markdown
    assert "full_answer" not in markdown
    assert "session_text" not in markdown
```

- [x] **Step 2: Run smoke test to verify GREEN**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py::test_p6o3_governed_contract_fake_provider_smoke_is_private -q -p no:cacheprovider
```

Expected: test passes after Task 2 implementation.

- [x] **Step 3: Run broader comprehensive eval tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py -q -p no:cacheprovider
```

Expected: all comprehensive online eval tests pass.

- [x] **Step 4: Commit Task 3**

Run:

```bash
git add tests/test_memory_comprehensive_online_eval.py
git commit -m "test: cover p6o3 governed evidence contract smoke"
```

Expected: commit succeeds locally.

---

### Task 4: Documentation And P6o-4 Handoff

**Files:**
- Modify: `my_md/memory_optimization/README.md`
- Modify: `my_md/memory_optimization/02-memory-quality-metrics.md`
- Modify: `my_md/memory_optimization/03-memory-governance-design.md`
- Modify: `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
- Modify: `progress.md`
- Modify: `task_plan.md`

**Interfaces:**
- Consumes: Task 1-3 implementation and verification results.
- Produces: P6o-3 documented boundary and P6o-4 answer post-check shadow handoff.

- [x] **Step 1: Update memory optimization docs**

Add this summary to `my_md/memory_optimization/README.md` after the P6o-2 paragraph:

```markdown
- Phase 6o3-production-safe-evidence-contract：将 eval-only `chain_tri_governed_answer_contract` 从 fixture answer expectations 迁移到 production-safe evidence contract。P6o-3 仍不运行真实 LLM，不改变生产 `AgentLoop`、真实召回、真实写入或默认 prompt；它只把 P6o-2 的 tiered candidate metadata 和 memory item metadata 渲染成 `allowed_evidence`、`likely_relevant_evidence`、`stale_warning`、`conflict_warning`、`active_version`、`insufficient_evidence_fallback` 和 `forbidden_boundary`。旧 `chain_tri_answer_contract` 保留为 oracle 诊断对照。下一步 P6o-4 做回答后校验 shadow。
```

Add to `my_md/memory_optimization/02-memory-quality-metrics.md` below P6o-2:

```markdown
### Phase 6o3 Production-Safe Evidence Contract

P6o-3 removes fixture answer-term dependencies from the governed tri contract path. The metric meaning is still schema / harness readiness, not answer-quality uplift: it proves that production-safe contract fields can be derived from candidate tiers, source/status/conflict metadata, and allowed evidence ids.

The key boundary is that `chain_tri_answer_contract` remains the oracle diagnostic profile, while `chain_tri_governed_answer_contract` becomes the production-safe eval/shadow profile. Real LLM A/B remains deferred until P6o-5.
```

Add to `my_md/memory_optimization/03-memory-governance-design.md` after the P6o-2 boundary:

```markdown
P6o-3 design boundary: the governed evidence contract no longer says what terms the answer must contain. Instead it exposes evidence state that production code could plausibly know: allowed ids, likely relevant ids, downgraded ids, requires-review ids, stale/superseded warnings, conflict warnings, active version ids, insufficient-evidence fallback, and forbidden boundary ids. This keeps the answer contract useful without depending on fixture answer expectations.
```

Add to `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md` after the P6o-2 complete criteria:

```markdown
P6o-3 complete criteria: governed tri contract uses production-safe evidence fields, JSON / Markdown metadata marks `production_safe_evidence_contract`, fixture answer expectations are absent from the governed contract raw output and rendered block, and fake-provider smoke passes. P6o-4 should add answer post-check shadow over these fields before any real LLM A/B.
```

- [x] **Step 2: Update planning records**

Append to `task_plan.md`:

```markdown
## 2026-07-28 Memory P6o3 Production-Safe Evidence Contract

Goal: replace fixture answer expectations in the governed tri contract path with production-safe evidence contract fields.

1. Add pure production-safe evidence contract helper - complete
2. Switch governed eval profile to production-safe contract - complete
3. Add fake-provider smoke and privacy coverage - complete
4. Update docs and commit locally without push - pending
```

Append to `progress.md`:

```markdown
## 2026-07-28 Memory P6o3 Production-Safe Evidence Contract

- Plan path: `docs/superpowers/plans/2026-07-28-memory-p6o3-production-safe-evidence-contract.md`.
- Scope: eval/shadow-only evidence contract, no real LLM.
- Production boundary: no AgentLoop, Reasoner, ToolExecutor, memory write, production prompt, or old `Retriever.retrieve()` contract changes.
- Contract fields: `allowed_evidence`, `likely_relevant_evidence`, `stale_warning`, `conflict_warning`, `active_version`, `insufficient_evidence_fallback`, `forbidden_boundary`.
- Old `chain_tri_answer_contract` remains oracle diagnostic; governed profile is the production-safe eval/shadow path.
- Next handoff: P6o-4 answer post-check shadow should record allowed evidence usage, missed key evidence, forbidden terms, superseded/conflict evidence usage, and retry need.
```

- [x] **Step 3: Run final verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_answer_contract.py tests/test_memory_comprehensive_online_eval.py tests/test_memory_retrieval_governance.py tests/test_memory_tri_candidate_governance.py -q -p no:cacheprovider
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

- [x] **Step 4: Commit Task 4**

Run:

```bash
git add my_md/memory_optimization/README.md my_md/memory_optimization/02-memory-quality-metrics.md my_md/memory_optimization/03-memory-governance-design.md my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md progress.md task_plan.md
git add -f docs/superpowers/plans/2026-07-28-memory-p6o3-production-safe-evidence-contract.md
git commit -m "docs: record production safe evidence contract handoff"
```

Expected: commit succeeds locally. Do not push unless the user explicitly asks.

---

## Final Acceptance Criteria

- `chain_tri_answer_contract` remains unchanged as an oracle diagnostic control using fixture answer expectations.
- `chain_tri_governed_answer_contract` no longer reads fixture answer expectations for rendered or raw answer-contract fields.
- `answer_expectation_for_profile(case, "chain_tri_governed_answer_contract")` no longer uses fixture answer terms; it keeps governed evidence grounding and language checks only.
- Governed profile rendered text exposes production-safe evidence fields and omits `required_terms`, `required_term_groups`, and `forbidden_terms`.
- Governed profile raw output exposes production-safe fields: allowed evidence, likely relevant evidence, downgrade/requires-review ids, stale warnings, conflict warnings, active version ids, insufficient-evidence fallback, forbidden boundary ids, and deleted ids.
- JSON / Markdown profile metadata includes `production_safe_evidence_contract = True` and `uses_fixture_answer_expectations = False` for `chain_tri_governed_answer_contract`.
- No real LLM run is part of P6o-3.
- Production retrieval, memory writes, tool execution, AgentLoop, Reasoner, and production prompt behavior are unchanged.
- Focused pytest, compileall, and `git diff --check` pass.

## Self-Review Notes

- Spec coverage: this plan covers P6o-3 only: pure evidence-contract helper, governed eval profile wiring, fake-provider smoke/privacy coverage, docs, and verification.
- Scope check: P6o-4 answer post-check shadow and P6o-5 real LLM A/B are intentionally deferred.
- Placeholder scan: no open-ended TODO placeholders remain; each task has file paths, expected functions, commands, and expected outcomes.
- Type consistency: `ProductionEvidenceContract`, `build_production_governed_tri_evidence_contract()`, `render_production_evidence_contract_block()`, and `production_safe_evidence_contract` are used consistently across tasks.
