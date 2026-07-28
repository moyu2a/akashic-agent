# Memory P6o2 Risk-Tiered Candidate Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace eval-only strict tri candidate governance with risk-tiered candidate governance so weak but potentially useful evidence is downgraded or marked for review instead of being dropped.

**Architecture:** Keep production retrieval, writing, AgentLoop, ToolExecutor, Reasoner, and prompt behavior unchanged. Extend the existing pure retrieval governance helpers with a `tiered` candidate governance mode while preserving the existing `strict` mode as the default. Then switch the eval-only tri candidate governance and governed answer-contract profiles to use the tiered mode and expose tier counts in reports and docs.

**Tech Stack:** Python 3.14, dataclasses, existing `memory2.retrieval_governance`, existing `memory2.eval_comprehensive_online`, existing `memory2.eval_tri_candidate_governance`, pytest, existing offline/eval CLIs.

## Global Constraints

- Work only in `/home/jjh/git_work/akashic-agent/.worktrees/memory-next`.
- Do not modify production `AgentLoop`, `Reasoner`, `ToolExecutor`, `ToolRegistry`, memory write behavior, production prompt behavior, or the old `Retriever.retrieve()` return contract.
- P6o-2 is eval/shadow-only. It must not run real LLM.
- Preserve `CandidateGovernancePolicy(mode="strict")` behavior for existing route governance callers. Only the eval-only tri candidate governance path and pre-existing eval-only profiles that reuse that path (`chain_tri_candidate_governance` and `chain_tri_governed_answer_contract`) may opt into `mode="tiered"`; answer-contract rendering semantics must not change in P6o-2.
- Risk tier mapping must be exact:
  - `delete`: `forbidden_candidate`, `superseded_candidate`, `scope_mismatch`
  - `downgrade`: `weak_source_ref`, `low_confidence`
  - `requires_review`: `conflict_candidate`, `missing_source_ref`, `insufficient_evidence`
  - `allow`: no risks
- Do not commit raw prompts, raw session text, raw memory summaries, full answers, API keys, or `answer_debug` artifacts.
- Do not push without explicit user instruction.

---

## File Structure

- Modify `memory2/retrieval_governance.py`: add candidate risk tier classification, add `CandidateGovernancePolicy.mode`, and add tiered mode behavior to `apply_retrieval_route()`.
- Modify `tests/test_memory_retrieval_governance.py`: pure tests for exact risk-tier mapping, insufficient-evidence detection, strict-mode compatibility, and tiered-mode annotations.
- Modify `memory2/eval_comprehensive_online.py`: make eval-only `chain_tri_candidate_governance` and `chain_tri_governed_answer_contract` use tiered governed tri ids, update profile metadata, and expose diagnostic tier metadata without changing answer-contract fields.
- Modify `tests/test_memory_comprehensive_online_eval.py`: integration tests for profile evidence source, tiered preservation of downgraded/review candidates, candidate raw tier metadata, and governed answer-contract raw tier metadata.
- Modify `memory2/eval_tri_candidate_governance.py`: add offline tier-count metrics and case-row tier fields with separate classified-vs-accepted counts.
- Modify `tests/test_memory_tri_candidate_governance.py`: report and CLI tests for tiered metrics and private artifacts.
- Modify `my_md/memory_optimization/README.md`, `my_md/memory_optimization/02-memory-quality-metrics.md`, `my_md/memory_optimization/03-memory-governance-design.md`, `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`: record P6o-2 design, the actual offline report count summary, and P6o-3 handoff.
- Modify `progress.md` and `task_plan.md`: record plan execution and verification.

---

### Task 0: Confirm Clean P6o-2 Baseline

**Files:**
- Modify: none

**Interfaces:**
- Consumes: current `memory-next` worktree after P6o-1.
- Produces: known clean baseline for P6o-2 commits.

- [ ] **Step 1: Inspect status**

Run:

```bash
git status --short
```

Expected: no output except possibly ignored plan scratch files under `.superpowers/`. If tracked files are dirty, stop and inspect before continuing.

- [ ] **Step 2: Inspect recent commits**

Run:

```bash
git log --oneline -6
```

Expected to include:

```text
f24ed71 docs: record governed answer contract eval handoff
075d7be test: cover governed answer contract eval metadata
14d36d0 feat: add governed tri answer contract eval profile
ae253f0 feat: add governed tri answer contract helper
```

---

### Task 1: Add Pure Candidate Risk Tier Classification

**Files:**
- Modify: `memory2/retrieval_governance.py`
- Test: `tests/test_memory_retrieval_governance.py`

**Interfaces:**
- Consumes: `classify_candidate_risks(candidate: Mapping[str, Any]) -> tuple[str, ...]`.
- Produces:
  - `classify_candidate_risk_tier(candidate: Mapping[str, Any]) -> dict[str, object]`
  - `classify_candidate_risks()` includes `insufficient_evidence` when fixture or production-safe metadata marks evidence as insufficient.

- [ ] **Step 1: Add failing insufficient-evidence risk test**

Append to `tests/test_memory_retrieval_governance.py`:

```python
def test_candidate_risk_classifier_flags_insufficient_evidence() -> None:
    assert "insufficient_evidence" in classify_candidate_risks(
        {"id": "gap", "source_ref": "telegram:1:1", "insufficient_evidence": True}
    )
    assert "insufficient_evidence" in classify_candidate_risks(
        {"id": "gap-risk", "source_ref": "telegram:1:1", "risk": "evidence_gap"}
    )
    assert "insufficient_evidence" in classify_candidate_risks(
        {"id": "gap-tag", "source_ref": "telegram:1:1", "tags": ["insufficient_evidence"]}
    )
```

- [ ] **Step 2: Run insufficient-evidence test to verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_retrieval_governance.py::test_candidate_risk_classifier_flags_insufficient_evidence -q -p no:cacheprovider
```

Expected: fail because `insufficient_evidence` is not classified yet.

- [ ] **Step 3: Implement insufficient-evidence risk classification**

Modify `memory2/retrieval_governance.py`.

In `classify_candidate_risks()`, after the low-confidence check, add:

```python
    if _is_insufficient_evidence(candidate):
        risks.append("insufficient_evidence")
```

Add helper near `_is_low_confidence()`:

```python
def _is_insufficient_evidence(item: Mapping[str, Any]) -> bool:
    if item.get("insufficient_evidence") is True:
        return True
    risk = item.get("risk")
    if isinstance(risk, str) and risk.lower() in {
        "insufficient_evidence",
        "evidence_gap",
        "needs_evidence",
    }:
        return True
    tags = item.get("tags")
    return isinstance(tags, Sequence) and not isinstance(tags, (str, bytes)) and any(
        str(tag).lower()
        in {"insufficient_evidence", "evidence_gap", "needs_evidence"}
        for tag in tags
    )
```

- [ ] **Step 4: Run insufficient-evidence test to verify GREEN**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_retrieval_governance.py::test_candidate_risk_classifier_flags_insufficient_evidence -q -p no:cacheprovider
```

Expected: test passes.

- [ ] **Step 5: Add failing risk-tier mapping test**

Append to `tests/test_memory_retrieval_governance.py`:

```python
def test_candidate_risk_tier_mapping_is_exact() -> None:
    assert classify_candidate_risk_tier(
        _candidate("blocked", forbidden=True, source_ref="telegram:1:1")
    )["tier"] == "delete"
    assert classify_candidate_risk_tier(
        _candidate("old", status="superseded", source_ref="telegram:1:1")
    )["tier"] == "delete"
    assert classify_candidate_risk_tier(
        _candidate("wrong-scope", source_ref="telegram:1:1", scope_match=False)
    )["tier"] == "delete"
    assert classify_candidate_risk_tier(
        _candidate("weak", source_ref="session:telegram:1")
    )["tier"] == "downgrade"
    assert classify_candidate_risk_tier(
        _candidate("low", source_ref="telegram:1:1", confidence=0.3)
    )["tier"] == "downgrade"
    assert classify_candidate_risk_tier(
        _candidate("conflict", source_ref="telegram:1:1", conflict=True)
    )["tier"] == "requires_review"
    assert classify_candidate_risk_tier(_candidate("missing-source"))[
        "tier"
    ] == "requires_review"
    assert classify_candidate_risk_tier(
        _candidate("gap", source_ref="telegram:1:1", insufficient_evidence=True)
    )["tier"] == "requires_review"
    assert classify_candidate_risk_tier(
        _candidate("clean", source_ref="telegram:1:1", confidence=0.9)
    )["tier"] == "allow"
```

Add `classify_candidate_risk_tier` to the import list at the top of the same file.

- [ ] **Step 6: Run tier mapping test to verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_retrieval_governance.py::test_candidate_risk_tier_mapping_is_exact -q -p no:cacheprovider
```

Expected: fail because `classify_candidate_risk_tier` is missing.

- [ ] **Step 7: Implement tier classification**

Add constants near `_LOW_CONFIDENCE_PHRASES`:

```python
_DELETE_RISKS = ("forbidden_candidate", "superseded_candidate", "scope_mismatch")
_DOWNGRADE_RISKS = ("weak_source_ref", "low_confidence")
_REQUIRES_REVIEW_RISKS = (
    "conflict_candidate",
    "missing_source_ref",
    "insufficient_evidence",
)
```

Add this public helper after `classify_candidate_risks()`:

```python
def classify_candidate_risk_tier(candidate: Mapping[str, Any]) -> dict[str, object]:
    risks = classify_candidate_risks(candidate)
    if any(risk in _DELETE_RISKS for risk in risks):
        tier = "delete"
    elif any(risk in _REQUIRES_REVIEW_RISKS for risk in risks):
        tier = "requires_review"
    elif any(risk in _DOWNGRADE_RISKS for risk in risks):
        tier = "downgrade"
    else:
        tier = "allow"
    return {
        "candidate_id": _candidate_id(candidate),
        "tier": tier,
        "action": tier,
        "risks": risks,
    }
```

- [ ] **Step 8: Run Task 1 tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_retrieval_governance.py::test_candidate_risk_tier_mapping_is_exact tests/test_memory_retrieval_governance.py::test_candidate_risk_classifier_flags_insufficient_evidence -q -p no:cacheprovider
```

Expected: both tests pass.

- [ ] **Step 9: Commit Task 1**

Run:

```bash
git add memory2/retrieval_governance.py tests/test_memory_retrieval_governance.py
git commit -m "feat: classify candidate governance risk tiers"
```

Expected: commit succeeds locally.

---

### Task 2: Add Tiered Candidate Governance Mode To Route Application

**Files:**
- Modify: `memory2/retrieval_governance.py`
- Test: `tests/test_memory_retrieval_governance.py`

**Interfaces:**
- Consumes: `CandidateGovernancePolicy`, `classify_candidate_risk_tier()`, `apply_retrieval_route()`.
- Produces:
  - `CandidateGovernancePolicy.mode: str = "strict"`
  - `mode="strict"` keeps existing drop behavior.
  - `mode="tiered"` deletes only `delete` tier candidates and accepts `downgrade`, `requires_review`, and `allow` candidates with diagnostic annotations.
  - Trace fields:
    - `candidate_governance_mode`
    - `candidate_risk_tier_counts`
    - `accepted_candidate_risk_tier_counts`
    - `tiered_deleted_risks_by_reason`
    - `candidate_risk_tiers`

- [ ] **Step 1: Add focused failing mode tests**

Append to `tests/test_memory_retrieval_governance.py`:

```python
def test_tiered_candidate_governance_keeps_review_and_downgrade_candidates() -> None:
    decision = build_retrieval_routing_decision("上次提到的那个方案是什么？")
    decision = decision.with_candidate_governance(
        CandidateGovernancePolicy(enabled=True, mode="tiered")
    )

    candidates, trace = apply_retrieval_route(
        decision,
        {
            "semantic": [
                _candidate("good", source_ref="telegram:1:1", confidence=0.9),
                _candidate("weak", source_ref="session:telegram:1", confidence=0.9),
                _candidate("conflict", source_ref="telegram:1:2", conflict=True),
                _candidate("forbidden", source_ref="telegram:1:3", forbidden=True),
            ]
        },
    )

    assert [item["id"] for item in candidates] == ["good", "weak", "conflict"]
    assert [item["candidate_risk_tier"] for item in candidates] == [
        "allow",
        "downgrade",
        "requires_review",
    ]
    assert trace["candidate_governance_mode"] == "tiered"
    assert trace["candidate_risk_tier_counts"]["delete"] == 1
    assert trace["accepted_candidate_risk_tier_counts"] == {
        "allow": 1,
        "downgrade": 1,
        "requires_review": 1,
    }
    assert trace["tiered_deleted_risks_by_reason"] == {"forbidden_candidate": 1}


def test_strict_candidate_governance_remains_default_mode() -> None:
    policy = CandidateGovernancePolicy(enabled=True)
    assert policy.mode == "strict"

    decision = build_retrieval_routing_decision("上次提到的那个方案是什么？")
    decision = decision.with_candidate_governance(policy)

    candidates, trace = apply_retrieval_route(
        decision,
        {
            "semantic": [
                _candidate("weak", source_ref="session:telegram:1", confidence=0.9),
                _candidate("conflict", source_ref="telegram:1:2", conflict=True),
            ]
        },
    )

    assert candidates == []
    assert trace["candidate_governance_mode"] == "strict"
    assert trace["dropped_risks_by_reason"] == {
        "weak_source_ref": 1,
        "conflict_candidate": 1,
    }


def test_strict_candidate_governance_accepts_insufficient_evidence_by_default() -> None:
    decision = build_retrieval_routing_decision("上次提到的那个方案是什么？")
    decision = decision.with_candidate_governance(
        CandidateGovernancePolicy(enabled=True)
    )

    candidates, trace = apply_retrieval_route(
        decision,
        {
            "semantic": [
                _candidate(
                    "needs-review",
                    source_ref="telegram:1:1",
                    insufficient_evidence=True,
                ),
            ]
        },
    )

    assert [item["id"] for item in candidates] == ["needs-review"]
    assert trace["candidate_governance_mode"] == "strict"
    assert trace["dropped_risks_by_reason"] == {}
    assert trace["accepted_risky_candidate_count"] == 1


def test_candidate_governance_policy_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="unknown candidate governance mode"):
        CandidateGovernancePolicy(enabled=True, mode="mystery")
```

Add `import pytest` near the top of `tests/test_memory_retrieval_governance.py`.

- [ ] **Step 2: Run mode tests to verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_retrieval_governance.py::test_tiered_candidate_governance_keeps_review_and_downgrade_candidates tests/test_memory_retrieval_governance.py::test_strict_candidate_governance_remains_default_mode tests/test_memory_retrieval_governance.py::test_strict_candidate_governance_accepts_insufficient_evidence_by_default tests/test_memory_retrieval_governance.py::test_candidate_governance_policy_rejects_unknown_mode -q -p no:cacheprovider
```

Expected: fail because `CandidateGovernancePolicy.mode`, mode validation, and tiered trace fields do not exist.

- [ ] **Step 3: Implement policy mode and tiered route branch**

Modify `CandidateGovernancePolicy` in `memory2/retrieval_governance.py`:

```python
mode: str = "strict"
```

Add `"mode": self.mode` to `to_dict()`.

Add construction-time validation:

```python
    def __post_init__(self) -> None:
        if self.mode not in {"strict", "tiered"}:
            raise ValueError(f"unknown candidate governance mode: {self.mode}")
```

In `apply_retrieval_route()`, initialize these near existing trace counters:

```python
candidate_risk_tier_counts: dict[str, int] = {}
accepted_candidate_risk_tier_counts: dict[str, int] = {}
tiered_deleted_risks_by_reason: dict[str, int] = {}
candidate_risk_tiers: list[dict[str, object]] = []
```

Replace the current `if decision.candidate_governance.enabled:` block with:

```python
            if decision.candidate_governance.enabled:
                mode = decision.candidate_governance.mode
                if mode == "tiered":
                    tier_record = dict(classify_candidate_risk_tier(item))
                    tier_record["lane"] = lane
                    candidate_risk_tiers.append(tier_record)
                    tier = str(tier_record["tier"])
                    _count(candidate_risk_tier_counts, tier)
                    risks = tuple(str(risk) for risk in tier_record["risks"])
                    if tier == "delete":
                        for risk in risks:
                            if risk in _DELETE_RISKS:
                                _count(tiered_deleted_risks_by_reason, risk)
                                _count(dropped_risks_by_reason, risk)
                        continue
                    item["candidate_risk_tier"] = tier
                    item["candidate_governance_action"] = tier
                    item["candidate_risks"] = risks
                elif mode == "strict":
                    drop_risks = [
                        risk
                        for risk in risks
                        if risk in decision.candidate_governance.drop_risks
                    ]
                    fatal = any(
                        risk in decision.candidate_governance.fatal_risks
                        for risk in drop_risks
                    )
                    if drop_risks and (fatal or not protected):
                        for risk in drop_risks:
                            _count(dropped_risks_by_reason, risk)
                        continue
                    if drop_risks and protected:
                        protected_risky_candidate_count += 1
                        for risk in drop_risks:
                            _count(would_drop_protected_by_reason, risk)
                else:
                    raise ValueError(f"unknown candidate governance mode: {mode}")
```

After a candidate is accepted and before `if risks:` existing count, add:

```python
            if decision.candidate_governance.enabled and decision.candidate_governance.mode == "tiered":
                _count(
                    accepted_candidate_risk_tier_counts,
                    str(item.get("candidate_risk_tier") or "allow"),
                )
```

Add the new trace fields:

```python
        "candidate_governance_mode": decision.candidate_governance.mode,
        "candidate_risk_tier_counts": candidate_risk_tier_counts,
        "accepted_candidate_risk_tier_counts": accepted_candidate_risk_tier_counts,
        "tiered_deleted_risks_by_reason": tiered_deleted_risks_by_reason,
        "candidate_risk_tiers": candidate_risk_tiers,
```

- [ ] **Step 4: Run route governance tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_retrieval_governance.py -q -p no:cacheprovider
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add memory2/retrieval_governance.py tests/test_memory_retrieval_governance.py
git commit -m "feat: add tiered candidate governance mode"
```

Expected: commit succeeds locally.

---

### Task 3: Switch Eval-Only Tri Profiles To Tiered Governance

**Files:**
- Modify: `memory2/eval_comprehensive_online.py`
- Test: `tests/test_memory_comprehensive_online_eval.py`

**Interfaces:**
- Consumes: `CandidateGovernancePolicy(mode="tiered")`.
- Produces:
  - `governed_tri_trace_for_case(case: EvalCase) -> dict[str, object]`
  - `governed_tri_evidence_ids_for_case(case)` uses tiered governance.
  - `chain_tri_candidate_governance` and `chain_tri_governed_answer_contract` expose tiered metadata in eval-only raw output.
  - `profile_evidence_source("chain_tri_candidate_governance") == "tri_candidate_governance.risk_tiered_allowed_ids"`
  - `PROFILE_METADATA["chain_tri_candidate_governance"]["candidate_governance_mode"] == "tiered"`.

- [ ] **Step 1: Add failing integration tests**

Append near existing candidate-governance / governed-answer-contract tests in `tests/test_memory_comprehensive_online_eval.py`:

```python
def _case_with_tiered_tri_candidate():
    for case in (
        build_quantitative_eval_cases(case_set="common", limit=20, case_pack="standard")
        + build_quantitative_eval_cases(case_set="hard", limit=20, case_pack="standard")
    ):
        trace_info = governed_tri_trace_for_case(case)
        trace = trace_info["trace"]
        records = trace.get("candidate_risk_tiers", [])
        accepted_ids = set(trace_info["ids"])
        accepted_soft_ids = {
            str(record["candidate_id"])
            for record in records
            if record.get("tier") in {"downgrade", "requires_review"}
            and str(record.get("candidate_id") or "") in accepted_ids
        }
        deleted_ids = {
            str(record["candidate_id"])
            for record in records
            if record.get("tier") == "delete"
        }
        if accepted_soft_ids and deleted_ids.isdisjoint(accepted_ids):
            return case
    raise AssertionError("fixture must include a tiered governed tri case")


def test_tri_candidate_governance_uses_tiered_evidence_source() -> None:
    case = _case_with_tiered_tri_candidate()

    governed_ids = evidence_ids_for_profile(case, "chain_tri_candidate_governance")

    assert governed_ids
    assert (
        profile_evidence_source("chain_tri_candidate_governance")
        == "tri_candidate_governance.risk_tiered_allowed_ids"
    )
    assert set(governed_ids) <= set(evidence_ids_for_profile(case, "chain_tri_retrieval"))
    assert set(governed_ids).isdisjoint(
        set(str(item) for item in case.expectations["should_not_recall_ids"])
    )
    trace_info = governed_tri_trace_for_case(case)
    trace = trace_info["trace"]
    accepted_ids = set(trace_info["ids"])
    assert any(
        record.get("tier") in {"downgrade", "requires_review"}
        and str(record.get("candidate_id") or "") in accepted_ids
        for record in trace["candidate_risk_tiers"]
    )
    assert all(
        record.get("tier") != "delete"
        or str(record.get("candidate_id") or "") not in accepted_ids
        for record in trace["candidate_risk_tiers"]
    )


def test_tri_candidate_governance_raw_exposes_tiered_trace(tmp_path: Path) -> None:
    case = _case_with_tiered_tri_candidate()
    engine = ComprehensiveOnlineMemoryEngine(
        case,
        profile_name="chain_tri_candidate_governance",
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

    assert result.raw["candidate_governance_mode"] == "tiered"
    assert isinstance(result.raw["candidate_risk_tier_counts"], dict)
    assert isinstance(result.raw["accepted_candidate_risk_tier_counts"], dict)
    assert isinstance(result.raw["candidate_risk_tiers"], list)


def test_governed_answer_contract_raw_exposes_tiered_candidate_trace(
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

    assert result.raw["candidate_governance_mode"] == "tiered"
    assert isinstance(result.raw["candidate_risk_tier_counts"], dict)
    assert isinstance(result.raw["candidate_risk_tiers"], list)
    assert result.raw["answer_contract"]["candidate_governance_mode"] == "tiered"
```

Add `governed_tri_trace_for_case` to the import list from `memory2.eval_comprehensive_online`.

- [ ] **Step 2: Run integration tests to verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py::test_tri_candidate_governance_uses_tiered_evidence_source tests/test_memory_comprehensive_online_eval.py::test_tri_candidate_governance_raw_exposes_tiered_trace tests/test_memory_comprehensive_online_eval.py::test_governed_answer_contract_raw_exposes_tiered_candidate_trace -q -p no:cacheprovider
```

Expected: fail because the evidence source is still strict and raw tier fields are missing.

- [ ] **Step 3: Implement tiered governed trace helper**

In `memory2/eval_comprehensive_online.py`, add a helper next to `governed_tri_evidence_ids_for_case()`:

```python
def governed_tri_trace_for_case(case: EvalCase) -> dict[str, object]:
    tri_ids = tuple(_ids_from_trace(case, "tri_retrieval", "fused_ids"))
    if not tri_ids:
        return {"ids": (), "trace": {}}
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
            mode="tiered",
            protected_expected_ids=expected_ids,
        )
    )
    governed, trace = apply_retrieval_route(decision, {"semantic": candidates})
    ids = tuple(
        str(candidate.get("id") or candidate.get("memory_id") or "")
        for candidate in governed
        if candidate.get("id") or candidate.get("memory_id")
    )
    return {"ids": ids, "trace": trace}
```

Change `governed_tri_evidence_ids_for_case()` to:

```python
def governed_tri_evidence_ids_for_case(case: EvalCase) -> tuple[str, ...]:
    return tuple(governed_tri_trace_for_case(case).get("ids", ()))
```

- [ ] **Step 4: Expose tier raw metadata and source labels**

In `PROFILE_METADATA[TRI_CANDIDATE_GOVERNANCE_PROFILE]`, change the description to avoid "strict" and add:

```python
"candidate_governance_mode": "tiered",
```

In `profile_evidence_source()`, change the candidate governance source to:

```python
TRI_CANDIDATE_GOVERNANCE_PROFILE: (
    "tri_candidate_governance.risk_tiered_allowed_ids"
),
```

In `ComprehensiveOnlineMemoryEngine.retrieve()`, replace the initial id lookup with profile-aware trace reuse:

```python
        governed_trace: dict[str, object] | None = None
        if self.profile_name in {
            TRI_CANDIDATE_GOVERNANCE_PROFILE,
            TRI_GOVERNED_ANSWER_CONTRACT_PROFILE,
        }:
            governed_trace = governed_tri_trace_for_case(self.case)
            ids = list(tuple(governed_trace.get("ids", ())))
        else:
            ids = list(evidence_ids_for_profile(self.case, self.profile_name))
```

When `self.profile_name == TRI_GOVERNED_ANSWER_CONTRACT_PROFILE`, reuse the trace:

```python
assert governed_trace is not None
governed_ids = tuple(governed_trace.get("ids", ()))
trace = governed_trace.get("trace", {})
```

Then add these fields to `raw` for the governed answer-contract profile:

```python
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
```

Inside `raw["answer_contract"]`, add:

```python
"candidate_governance_mode": "tiered" if combines_candidate_governance else "none",
```

For the non-answer-contract retrieval result, add tier fields only when `self.profile_name == TRI_CANDIDATE_GOVERNANCE_PROFILE`:

```python
        raw: dict[str, object] = {
            "ids": ids,
            "evidence_source": profile_evidence_source(self.profile_name),
        }
        if self.profile_name == TRI_CANDIDATE_GOVERNANCE_PROFILE:
            assert governed_trace is not None
            trace = governed_trace.get("trace", {})
            raw.update(
                {
                    "candidate_governance_mode": trace.get(
                        "candidate_governance_mode"
                    ),
                    "candidate_risk_tier_counts": trace.get(
                        "candidate_risk_tier_counts",
                        {},
                    ),
                    "accepted_candidate_risk_tier_counts": trace.get(
                        "accepted_candidate_risk_tier_counts",
                        {},
                    ),
                    "tiered_deleted_risks_by_reason": trace.get(
                        "tiered_deleted_risks_by_reason",
                        {},
                    ),
                    "candidate_risk_tiers": trace.get("candidate_risk_tiers", []),
                }
            )
```

Return `raw=raw` instead of reconstructing the literal raw dict in the non-answer-contract branch.

- [ ] **Step 5: Run focused integration tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_retrieval_governance.py tests/test_memory_comprehensive_online_eval.py::test_tri_candidate_governance_uses_tiered_evidence_source tests/test_memory_comprehensive_online_eval.py::test_tri_candidate_governance_raw_exposes_tiered_trace tests/test_memory_comprehensive_online_eval.py::test_governed_answer_contract_raw_exposes_tiered_candidate_trace -q -p no:cacheprovider
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit Task 3**

Run:

```bash
git add memory2/eval_comprehensive_online.py tests/test_memory_comprehensive_online_eval.py
git commit -m "feat: use tiered governance for tri eval profiles"
```

Expected: commit succeeds locally.

---

### Task 4: Add Offline P6o-2 Tier Metrics And CLI Coverage

**Files:**
- Modify: `memory2/eval_tri_candidate_governance.py`
- Test: `tests/test_memory_tri_candidate_governance.py`

**Interfaces:**
- Consumes: `CandidateGovernancePolicy(mode="tiered")`, `apply_retrieval_route()` tiered trace.
- Produces:
  - Report metrics: `tiered_candidate_risk_tier_counts`, `tiered_accepted_candidate_risk_tier_counts`, `tiered_deleted_risks_by_reason`.
  - Case row fields: `tiered_classified_candidate_count`, `tiered_accepted_candidate_count`, `tiered_delete_count`, `tiered_downgrade_count`, `tiered_requires_review_count`, `tiered_allow_count`.

- [ ] **Step 1: Add failing report tests**

Append to `tests/test_memory_tri_candidate_governance.py`:

```python
def test_tri_candidate_governance_report_records_tiered_metrics() -> None:
    report = build_tri_candidate_governance_report(case_pack="standard")

    metrics = report["metrics"]
    assert metrics["tiered_candidate_risk_tier_counts"]
    assert "delete" in metrics["tiered_candidate_risk_tier_counts"]
    assert "accepted_candidate_risk_tier_counts" not in metrics
    assert metrics["tiered_accepted_candidate_risk_tier_counts"]
    assert metrics["tiered_deleted_risks_by_reason"]
    rows = report["case_rows"]
    assert rows
    assert all("tiered_classified_candidate_count" in row for row in rows)
    assert all("tiered_accepted_candidate_count" in row for row in rows)
    assert any(row["tiered_downgrade_count"] > 0 for row in rows)


def test_tri_candidate_governance_markdown_mentions_risk_tiers(tmp_path) -> None:
    report = build_tri_candidate_governance_report(case_pack="standard")
    _json_path, md_path = write_tri_candidate_governance_report(report, tmp_path)

    markdown = md_path.read_text(encoding="utf-8")
    assert "Risk Tier Metrics" in markdown
    assert "tiered_candidate_risk_tier_counts" in markdown
    assert "tiered_accepted_candidate_count" in markdown
    assert "tiered_downgrade_count" in markdown
```

- [ ] **Step 2: Run report tests to verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_tri_candidate_governance.py::test_tri_candidate_governance_report_records_tiered_metrics tests/test_memory_tri_candidate_governance.py::test_tri_candidate_governance_markdown_mentions_risk_tiers -q -p no:cacheprovider
```

Expected: fail because tiered report metrics and markdown section are missing.

- [ ] **Step 3: Implement tiered offline metrics**

In `memory2/eval_tri_candidate_governance.py`, initialize aggregate dicts:

```python
tiered_candidate_risk_tier_counts: dict[str, int] = {}
tiered_accepted_candidate_risk_tier_counts: dict[str, int] = {}
tiered_deleted_risks_by_reason: dict[str, int] = {}
```

For each case, after the protected/unprotected strict decisions, add:

```python
tiered_decision = baseline_decision.with_candidate_governance(
    CandidateGovernancePolicy(
        enabled=True,
        mode="tiered",
        protected_expected_ids=expected_ids,
    )
)
tiered_candidates, tiered_trace = apply_retrieval_route(
    tiered_decision,
    candidates_by_lane,
)
```

Merge aggregate counts:

```python
_merge_counts(
    tiered_candidate_risk_tier_counts,
    tiered_trace.get("candidate_risk_tier_counts", {}),
)
_merge_counts(
    tiered_accepted_candidate_risk_tier_counts,
    tiered_trace.get("accepted_candidate_risk_tier_counts", {}),
)
_merge_counts(
    tiered_deleted_risks_by_reason,
    tiered_trace.get("tiered_deleted_risks_by_reason", {}),
)
```

Add to each row:

```python
"tiered_classified_candidate_count": sum(
    int(count or 0)
    for count in dict(tiered_trace.get("candidate_risk_tier_counts", {})).values()
),
"tiered_accepted_candidate_count": len(tiered_candidates),
"tiered_candidate_risk_tier_counts": tiered_trace.get(
    "candidate_risk_tier_counts",
    {},
),
"tiered_accepted_candidate_risk_tier_counts": tiered_trace.get(
    "accepted_candidate_risk_tier_counts",
    {},
),
"tiered_deleted_risks_by_reason": tiered_trace.get(
    "tiered_deleted_risks_by_reason",
    {},
),
"tiered_delete_count": int(
    dict(tiered_trace.get("candidate_risk_tier_counts", {})).get("delete", 0)
),
"tiered_downgrade_count": int(
    dict(tiered_trace.get("candidate_risk_tier_counts", {})).get("downgrade", 0)
),
"tiered_requires_review_count": int(
    dict(tiered_trace.get("candidate_risk_tier_counts", {})).get(
        "requires_review",
        0,
    )
),
"tiered_allow_count": int(
    dict(tiered_trace.get("candidate_risk_tier_counts", {})).get("allow", 0)
),
```

Add aggregate metrics:

```python
"tiered_candidate_risk_tier_counts": tiered_candidate_risk_tier_counts,
"tiered_accepted_candidate_risk_tier_counts": (
    tiered_accepted_candidate_risk_tier_counts
),
"tiered_deleted_risks_by_reason": tiered_deleted_risks_by_reason,
```

- [ ] **Step 4: Add Markdown risk tier section**

In `write_tri_candidate_governance_report()`, after the metrics list, add:

```python
    lines.extend(["", "## Risk Tier Metrics", ""])
    if isinstance(metrics, Mapping):
        for key in (
            "tiered_candidate_risk_tier_counts",
            "tiered_accepted_candidate_risk_tier_counts",
            "tiered_deleted_risks_by_reason",
        ):
            lines.append(f"- `{key}`: `{metrics.get(key)}`")
```

Extend the case table header and rows with:

```markdown
tiered_classified | tiered_accepted | tiered_delete | tiered_downgrade | tiered_requires_review | tiered_allow
```

Use row values:

```python
row["tiered_classified_candidate_count"]
row["tiered_accepted_candidate_count"]
row["tiered_delete_count"]
row["tiered_downgrade_count"]
row["tiered_requires_review_count"]
row["tiered_allow_count"]
```

- [ ] **Step 5: Run report and CLI tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_tri_candidate_governance.py -q -p no:cacheprovider
```

Expected: all tests pass.

- [ ] **Step 6: Run offline P6o-2 report command**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_tri_candidate_governance_eval.py \
  --out-dir /tmp/akashic-memory-p6o2-risk-tiered-candidate-governance/reports \
  --case-pack standard
```

Expected: exit `0`, writes `tri_candidate_governance.json` and `.md`.

- [ ] **Step 7: Verify offline report facts**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path('/tmp/akashic-memory-p6o2-risk-tiered-candidate-governance/reports/tri_candidate_governance.json').read_text(encoding='utf-8'))
metrics = payload['metrics']
checks = {
    'case_count': metrics.get('case_count'),
    'has_tiered_counts': bool(metrics.get('tiered_candidate_risk_tier_counts')),
    'has_accepted_tiered_counts': bool(metrics.get('tiered_accepted_candidate_risk_tier_counts')),
    'has_deleted_risks': bool(metrics.get('tiered_deleted_risks_by_reason')),
    'protected_expected_hit_loss_count': metrics.get('protected_expected_hit_loss_count'),
    'strict_should_not_kept_count': metrics.get('strict_should_not_kept_count'),
}
print(json.dumps(checks, ensure_ascii=False, indent=2, sort_keys=True))
if checks['case_count'] <= 0:
    raise SystemExit('case_count must be positive')
if not checks['has_tiered_counts']:
    raise SystemExit('missing tiered counts')
if checks['protected_expected_hit_loss_count'] != 0:
    raise SystemExit('protected strict target loss changed')
if checks['strict_should_not_kept_count'] != 0:
    raise SystemExit('strict should-not keep count changed')
PY
```

Expected: prints positive `case_count`, tiered counts present, protected target loss remains `0`, strict should-not keep count remains `0`.

- [ ] **Step 8: Commit Task 4**

Run:

```bash
git add memory2/eval_tri_candidate_governance.py tests/test_memory_tri_candidate_governance.py
git commit -m "test: report tiered tri candidate governance metrics"
```

Expected: commit succeeds locally.

---

### Task 5: Documentation And Final Verification

**Files:**
- Modify: `my_md/memory_optimization/README.md`
- Modify: `my_md/memory_optimization/02-memory-quality-metrics.md`
- Modify: `my_md/memory_optimization/03-memory-governance-design.md`
- Modify: `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
- Modify: `progress.md`
- Modify: `task_plan.md`

**Interfaces:**
- Consumes: Task 4 offline report facts.
- Produces: P6o-2 documented boundary and P6o-3 handoff.

- [ ] **Step 1: Update memory optimization docs**

Use the exact values printed by Task 4 Step 7 for `case_count`, `tiered_candidate_risk_tier_counts`, `tiered_accepted_candidate_risk_tier_counts`, `tiered_deleted_risks_by_reason`, `protected_expected_hit_loss_count`, and `strict_should_not_kept_count`. Do not record estimated values.

Add to `my_md/memory_optimization/README.md` after the P6o-1 paragraph:

```markdown
- Phase 6o2-risk-tiered-candidate-governance：新增 eval/shadow-only risk-tiered candidate governance，把候选风险从 strict drop 拆成 `delete`、`downgrade`、`requires_review` 和 `allow`。P6o-2 不运行真实 LLM，不改变生产 `AgentLoop`、真实召回、真实写入或 prompt；它只验证候选分层 trace、eval profile evidence ids 和离线报告指标。离线报告需要记录 `case_count`、tiered classified / accepted counts、tiered deleted risks、`protected_expected_hit_loss_count` 和 `strict_should_not_kept_count`。下一步 P6o-3 才把这些 tier 转成生产安全 evidence contract 字段。
```

Add to `my_md/memory_optimization/02-memory-quality-metrics.md` under the P6o-1 section:

```markdown
### Phase 6o2 Risk-Tiered Candidate Governance

P6o-2 changes the eval-only candidate-governance semantics from a single strict filter into four diagnostic tiers: `delete`, `downgrade`, `requires_review`, and `allow`. The production path remains unchanged. This directly targets the P6n/P6o observation that strict candidate governance can reduce forbidden risk while hurting answer_rate by pruning too much context.

Current verification is offline/fake only. It proves that tier counts and accepted tier counts are observable, not that answer quality improved. Record the exact offline count summary from the generated `tri_candidate_governance.json` before committing docs. Real LLM A/B remains deferred to P6o-5.
```

Add to `my_md/memory_optimization/03-memory-governance-design.md` after the P6o-1 boundary paragraph:

```markdown
P6o-2 design boundary: tiered governance changes the eval/shadow decision record from binary keep/drop to `delete`, `downgrade`, `requires_review`, and `allow`. `delete` is reserved for forbidden, superseded, and scope mismatch candidates; weak source and low confidence are downgraded; conflicts, missing source, and insufficient evidence require review. This is the bridge to P6o-3 evidence contract generation, not a production activation.
```

Add to `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md` after the P6o-1 complete criteria paragraph:

```markdown
P6o-2 complete criteria: strict mode remains compatible, tiered mode records candidate tier counts, eval-only tri profiles use tiered allowed ids, offline report exposes tiered counts, and focused tests pass. P6o-3 should consume these tiers to render production-safe contract fields without fixture answer expectations.
```

- [ ] **Step 2: Update planning records**

Append to `task_plan.md`:

```markdown
## 2026-07-28 Memory P6o2 Risk-Tiered Candidate Governance

Goal: replace eval-only strict candidate filtering with risk-tiered candidate governance before production-safe evidence contract work.

1. Add pure risk tier classification - complete
2. Add tiered candidate governance mode while preserving strict mode - complete
3. Switch eval-only tri candidate/governed profiles to tiered ids - complete
4. Add offline report tier metrics - complete
5. Update docs and commit locally without push - pending
```

Append to `progress.md`:

```markdown
## 2026-07-28 Memory P6o2 Risk-Tiered Candidate Governance

- Plan path: `docs/superpowers/plans/2026-07-28-memory-p6o2-risk-tiered-candidate-governance.md`
- Scope: eval/shadow-only candidate risk tiers, offline report metrics, docs, no real LLM.
- Production boundary: no AgentLoop, Reasoner, ToolExecutor, memory write, production prompt, or old `Retriever.retrieve()` contract changes.
- Risk tiers: `delete`, `downgrade`, `requires_review`, `allow`.
- Next handoff: P6o-3 production-safe evidence contract should consume tiered candidate metadata and remove fixture answer expectations.
```

- [ ] **Step 3: Run final verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_retrieval_governance.py tests/test_memory_tri_candidate_governance.py tests/test_memory_comprehensive_online_eval.py tests/test_memory_answer_contract.py -q -p no:cacheprovider
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

- [ ] **Step 4: Commit Task 5**

Run:

```bash
git add my_md/memory_optimization/README.md my_md/memory_optimization/02-memory-quality-metrics.md my_md/memory_optimization/03-memory-governance-design.md my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md progress.md task_plan.md
git add -f docs/superpowers/plans/2026-07-28-memory-p6o2-risk-tiered-candidate-governance.md
git commit -m "docs: record tiered candidate governance handoff"
```

Expected: commit succeeds locally. Do not push unless the user explicitly asks.

---

## Final Acceptance Criteria

- `CandidateGovernancePolicy(mode="strict")` remains the default and preserves existing strict behavior.
- `CandidateGovernancePolicy(mode="tiered")` deletes only `delete` tier candidates and keeps `downgrade`, `requires_review`, and `allow` candidates with diagnostic annotations.
- Risk tier mapping exactly matches the Global Constraints.
- `chain_tri_candidate_governance` and the pre-existing eval-only `chain_tri_governed_answer_contract` use tiered governed ids in the eval harness.
- Candidate-governance raw metadata and governed answer-contract raw metadata include tiered governance trace fields.
- Offline tri candidate governance report includes tiered candidate counts and accepted tier counts.
- No real LLM run is part of P6o-2.
- Production retrieval, memory writes, tool execution, AgentLoop, Reasoner, and production prompt behavior are unchanged.
- Focused pytest, compileall, and `git diff --check` pass.

## Self-Review Notes

- Spec coverage: this plan covers P6o-2 only: pure tier classification, route tiered mode, eval profile wiring, offline report metrics, docs, and verification.
- Scope check: P6o-3 production-safe evidence contract, P6o-4 answer post-check shadow, and P6o-5 real LLM A/B are intentionally deferred.
- Placeholder scan: no open-ended TODO placeholders remain; each task has file paths, expected functions, commands, and expected outcomes.
- Type consistency: `mode="tiered"`, `classify_candidate_risk_tier()`, `candidate_risk_tier_counts`, and `accepted_candidate_risk_tier_counts` are used consistently across tasks.
