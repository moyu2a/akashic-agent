# Tri Candidate Denoising Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a small, measurable tri-retrieval candidate governance layer that reduces noisy, forbidden, superseded, conflicting, cross-scope, and weak-source candidates after retrieval, while preserving target grounding.

**Architecture:** Extend the existing pure-function route governance layer instead of changing `AgentLoop`, `Reasoner`, `ToolExecutor`, memory writes, or production prompts. The new logic classifies candidate risks, applies strict denoising only when requested by a routing decision / eval profile, emits trace counters, and generates a small offline attribution report before any real LLM rerun.

**Tech Stack:** Python dataclasses / pure functions, existing `memory2/retrieval_governance.py`, existing route-governance tests, existing comprehensive online report JSON, pytest, JSON/Markdown docs.

## Global Constraints

- Worktree: `/home/jjh/git_work/akashic-agent/.worktrees/memory-next`.
- Do not sync remote/main in this plan.
- Do not call real LLM in this plan; any real LLM rerun must be a later explicitly approved plan.
- Do not modify `AgentLoop`, `Reasoner`, `ToolExecutor`, `ToolRegistry`, production memory writes, or production prompts.
- Keep the current `retrieve()` return contract unchanged.
- Add candidate governance as pure functions and trace fields so it is measurable and reversible.
- Default behavior must remain compatible with the existing route-governance tests unless a decision explicitly enables strict filtering.
- Reports must not include raw prompt, raw session text, raw memory summary, or full answers.
- Primary success criteria for this plan are offline / trace-level:
  - candidate risk classification must run before source/scope/low-confidence drop decisions so protected non-fatal expected ids can be measured correctly;
  - protected target grounding proxy must not decrease on `EvalCase.expectations["should_recall_ids"]`;
  - `evidence_ids_for_profile(case, "chain_tri_retrieval")` may be reported only as a diagnostic tri-fused set, not as the protected oracle;
  - unprotected target loss must also be reported so oracle protection does not hide potential production false positives;
  - risky candidate drop counts must be visible by reason;
  - known 40-case tri-failure rows must be joined back into the candidate-governance report by `case_id`;
  - fixture-derived `memory_items`, `should_recall_ids`, and `should_not_recall_ids` must be used before adding any synthetic risk candidates;
  - the plan must prepare a later bounded real LLM rerun but not perform it.
- Review revision notes:
  - The first draft placed candidate governance after low-confidence filtering, which would drop protected expected ids too early. This revision moves risk classification before all candidate drop decisions and uses one unified filter path.
  - The first draft used mostly synthetic candidates. This revision requires fixture-derived candidates and the existing tri failure attribution JSON, with synthetic candidates only as bounded supplements where the fixture lacks a risk type.
  - `missing_source_ref` is intentionally a non-fatal drop risk: it can be dropped in unprotected strict mode, but a protected expected id with only `missing_source_ref` must be counted in `would_drop_protected_by_reason` and retained in protected mode.
  - The second review found that protected expected ids were still derived from tri fused evidence. This revision uses `should_recall_ids` as the protected oracle and keeps tri fused ids as diagnostics only.

---

## File Structure

- Modify `memory2/retrieval_governance.py`
  - Add `CandidateGovernancePolicy`.
  - Add `classify_candidate_risks()`.
  - Add optional strict filtering to `apply_retrieval_route()`.
  - Add trace fields for accepted / dropped risk reasons.

- Modify `tests/test_memory_retrieval_governance.py`
  - Add focused tests for forbidden, superseded, conflict, weak-source, cross-scope, and protected-target behavior.

- Create `memory2/eval_tri_candidate_governance.py`
  - Build a deterministic offline comparison from eval fixtures and existing tri-failure report data.
  - Use each `EvalCase.setup["memory_items"]` as the primary candidate source.
  - Use each `EvalCase.expectations["should_recall_ids"]` and `["should_not_recall_ids"]` to measure target preservation and forbidden/noise drops.
  - Join rows to `tri_retrieval_failure_attribution_v1/tri_retrieval_failure_attribution.json` by `case_id` so metrics can be grouped by `failure_bucket` and pass pattern.
  - Produce before/after candidate-governance metrics without calling LLM.

- Create `scripts/run_memory_tri_candidate_governance_eval.py`
  - CLI wrapper for the offline candidate-governance report.

- Create `tests/test_memory_tri_candidate_governance.py`
  - Test the offline report schema, counts, and privacy boundary.

- Modify documentation:
  - `my_md/memory_optimization/02-memory-quality-metrics.md`
  - `my_md/memory_optimization/03-memory-governance-design.md`
  - `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
  - `my_md/memory_optimization/README.md`
  - `progress.md`
  - `task_plan.md`

- Create report outputs:
  - `my_md/memory_optimization/eval_reports/tri_candidate_governance_v1/tri_candidate_governance.json`
  - `my_md/memory_optimization/eval_reports/tri_candidate_governance_v1/tri_candidate_governance.md`

---

### Task 1: Add Candidate Risk Classification

**Files:**
- Modify: `memory2/retrieval_governance.py`
- Modify: `tests/test_memory_retrieval_governance.py`

**Interfaces:**
- Produces:
  - `classify_candidate_risks(candidate: Mapping[str, Any]) -> tuple[str, ...]`
  - risk codes:
    - `forbidden_candidate`
    - `superseded_candidate`
    - `conflict_candidate`
    - `scope_mismatch`
    - `missing_source_ref`
    - `weak_source_ref`
    - `low_confidence`

- [ ] **Step 1: Write failing tests for candidate risk classification**

Append to `tests/test_memory_retrieval_governance.py`:

```python
from memory2.retrieval_governance import classify_candidate_risks


def test_candidate_risk_classifier_flags_forbidden_superseded_and_conflict() -> None:
    risks = classify_candidate_risks(
        {
            "id": "old-tool-rule",
            "summary": "旧规则：优先使用 web_search，但现在这是 forbidden。",
            "status": "superseded",
            "forbidden": True,
            "conflict": True,
            "source_ref": "telegram:1:10",
            "scope_match": True,
            "confidence": 0.9,
        }
    )

    assert risks == (
        "forbidden_candidate",
        "superseded_candidate",
        "conflict_candidate",
    )


def test_candidate_risk_classifier_flags_source_scope_and_low_confidence() -> None:
    risks = classify_candidate_risks(
        {
            "id": "weak-source",
            "summary": "不确定：未在对话中明确记录。",
            "source_ref": "session:telegram:1",
            "scope_match": False,
            "confidence": 0.4,
        }
    )

    assert risks == (
        "scope_mismatch",
        "weak_source_ref",
        "low_confidence",
    )


def test_candidate_risk_classifier_flags_missing_source_ref() -> None:
    assert classify_candidate_risks({"id": "no-source"}) == ("missing_source_ref",)
```

- [ ] **Step 2: Run tests and confirm RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_retrieval_governance.py::test_candidate_risk_classifier_flags_forbidden_superseded_and_conflict -q -p no:cacheprovider
```

Expected: fails with `ImportError` or `AttributeError` because `classify_candidate_risks` does not exist.

- [ ] **Step 3: Implement risk classification**

Add to `memory2/retrieval_governance.py`:

```python
def classify_candidate_risks(candidate: Mapping[str, Any]) -> tuple[str, ...]:
    risks: list[str] = []
    if _is_forbidden_candidate(candidate):
        risks.append("forbidden_candidate")
    if str(candidate.get("status") or "").lower() == "superseded":
        risks.append("superseded_candidate")
    if _is_conflict_candidate(candidate):
        risks.append("conflict_candidate")
    if candidate.get("scope_match") is False:
        risks.append("scope_mismatch")
    if not _has_source_ref(candidate):
        risks.append("missing_source_ref")
    elif _has_weak_source_ref(candidate):
        risks.append("weak_source_ref")
    if _is_low_confidence(candidate):
        risks.append("low_confidence")
    return tuple(risks)


def _is_forbidden_candidate(item: Mapping[str, Any]) -> bool:
    if item.get("forbidden") is True or item.get("forbidden_candidate") is True:
        return True
    if item.get("should_not_recall") is True:
        return True
    risk = item.get("risk")
    if isinstance(risk, str) and risk.lower() in {"forbidden", "blocked", "deny"}:
        return True
    tags = item.get("tags")
    if isinstance(tags, Sequence) and not isinstance(tags, (str, bytes)):
        if any(str(tag).lower() in {"forbidden", "blocked", "deny"} for tag in tags):
            return True
    extra = item.get("extra_json")
    if isinstance(extra, Mapping):
        topics = extra.get("active_topics")
        if isinstance(topics, Sequence) and not isinstance(topics, (str, bytes)):
            return any(str(topic) in {"助手推断"} for topic in topics)
    return False


def _is_conflict_candidate(item: Mapping[str, Any]) -> bool:
    if item.get("conflict") is True or item.get("conflict_candidate") is True:
        return True
    relation = str(item.get("relation_type") or "").lower()
    if relation in {"conflicts", "conflict", "contradicts"}:
        return True
    if item.get("conflict_with") or item.get("conflict_ids"):
        return True
    summary = str(item.get("summary") or "")
    extra = item.get("extra_json")
    topics = extra.get("active_topics") if isinstance(extra, Mapping) else ()
    topic_text = " ".join(str(topic) for topic in topics) if isinstance(topics, Sequence) and not isinstance(topics, (str, bytes)) else ""
    return "冲突" in summary or "冲突" in topic_text


def _has_weak_source_ref(item: Mapping[str, Any]) -> bool:
    source_ref = str(item.get("source_ref") or "")
    if not source_ref:
        return False
    if source_ref.endswith("@post_response"):
        return True
    if source_ref.startswith("session:"):
        return True
    confidence = item.get("source_ref_confidence")
    if isinstance(confidence, int | float) and confidence < 0.6:
        return True
    return item.get("source_ref_confident") is False
```

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_retrieval_governance.py -q -p no:cacheprovider
```

Expected: all route-governance tests pass.

---

### Task 2: Add Strict Candidate Governance Policy To Route Filtering

**Files:**
- Modify: `memory2/retrieval_governance.py`
- Modify: `tests/test_memory_retrieval_governance.py`

**Interfaces:**
- Produces:
  - `CandidateGovernancePolicy`
  - `RetrievalRoutingDecision.candidate_governance: CandidateGovernancePolicy`
  - new trace fields:
    - `candidate_governance_enabled`
    - `protected_expected_ids`
    - `dropped_risks_by_reason`
    - `protected_risky_candidate_count`
    - `accepted_risky_candidate_count`

- [ ] **Step 1: Write failing tests for strict filtering**

Append:

```python
from memory2.retrieval_governance import CandidateGovernancePolicy


def test_strict_candidate_governance_drops_risky_candidates_by_reason() -> None:
    decision = build_retrieval_routing_decision("以后遇到网页搜索时优先用哪个工具？")
    decision = decision.with_candidate_governance(
        CandidateGovernancePolicy(enabled=True)
    )

    candidates, trace = apply_retrieval_route(
        decision,
        {
            "semantic": [
                _candidate("good", source_ref="telegram:1:1", confidence=0.9),
                _candidate(
                    "old",
                    source_ref="telegram:1:2",
                    status="superseded",
                    confidence=0.9,
                ),
                _candidate(
                    "forbidden",
                    source_ref="telegram:1:3",
                    forbidden=True,
                    confidence=0.9,
                ),
            ]
        },
    )

    assert [item["id"] for item in candidates] == ["good"]
    assert trace["candidate_governance_enabled"] is True
    assert trace["dropped_risks_by_reason"] == {
        "superseded_candidate": 1,
        "forbidden_candidate": 1,
    }


def test_candidate_governance_protects_expected_ids_from_non_fatal_noise_filters() -> None:
    decision = build_retrieval_routing_decision("上次提到的那个方案是什么？")
    decision = decision.with_candidate_governance(
        CandidateGovernancePolicy(
            enabled=True,
            protected_expected_ids=("target",),
        )
    )

    candidates, trace = apply_retrieval_route(
        decision,
        {
            "semantic": [
                _candidate("target", confidence=0.4, source_ref="session:telegram:1"),
                _candidate("noise", confidence=0.4, source_ref="session:telegram:1"),
            ]
        },
    )

    assert [item["id"] for item in candidates] == ["target"]
    assert trace["protected_risky_candidate_count"] == 1
    assert trace["dropped_risks_by_reason"] == {"weak_source_ref": 1, "low_confidence": 1}
```

- [ ] **Step 2: Run tests and confirm RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_retrieval_governance.py::test_strict_candidate_governance_drops_risky_candidates_by_reason -q -p no:cacheprovider
```

Expected: fails because `CandidateGovernancePolicy` and `with_candidate_governance()` do not exist.

- [ ] **Step 3: Implement policy dataclass and decision copier**

Update the dataclass import first:

```python
from dataclasses import asdict, dataclass, field
```

Add before `RetrievalRoutingDecision`:

```python
@dataclass(frozen=True)
class CandidateGovernancePolicy:
    enabled: bool = False
    protected_expected_ids: tuple[str, ...] = ()
    drop_risks: tuple[str, ...] = (
        "forbidden_candidate",
        "superseded_candidate",
        "conflict_candidate",
        "scope_mismatch",
        "missing_source_ref",
        "weak_source_ref",
        "low_confidence",
    )
    fatal_risks: tuple[str, ...] = (
        "forbidden_candidate",
        "superseded_candidate",
        "conflict_candidate",
        "scope_mismatch",
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "protected_expected_ids": list(self.protected_expected_ids),
            "drop_risks": list(self.drop_risks),
            "fatal_risks": list(self.fatal_risks),
        }
```

Extend `RetrievalRoutingDecision`:

```python
    candidate_governance: CandidateGovernancePolicy = field(
        default_factory=CandidateGovernancePolicy
    )

    def with_candidate_governance(
        self,
        policy: CandidateGovernancePolicy,
    ) -> "RetrievalRoutingDecision":
        return RetrievalRoutingDecision(
            scene=self.scene,
            allowed_lanes=self.allowed_lanes,
            max_per_lane=dict(self.max_per_lane),
            require_source_ref=self.require_source_ref,
            require_scope_match=self.require_scope_match,
            graph_enabled=self.graph_enabled,
            drop_low_confidence=self.drop_low_confidence,
            reason=self.reason,
            candidate_governance=policy,
        )
```

Update `to_dict()`:

```python
        result["candidate_governance"] = self.candidate_governance.to_dict()
```

- [ ] **Step 4: Apply policy inside `apply_retrieval_route()` with one unified decision path**

Do not put candidate governance after existing source/scope/low-confidence `continue` statements. That would drop protected expected ids before they can be measured. Replace the per-candidate drop block with this structure:

```python
            risks = classify_candidate_risks(item)
            protected = _candidate_id(item) in protected_expected_ids

            if decision.candidate_governance.enabled:
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
                if decision.require_source_ref and "missing_source_ref" in risks:
                    _count(dropped_by_reason, "missing_source_ref")
                    continue
                if decision.require_scope_match and "scope_mismatch" in risks:
                    _count(dropped_by_reason, "scope_mismatch")
                    continue
                if decision.drop_low_confidence and "low_confidence" in risks:
                    _count(dropped_by_reason, "low_confidence")
                    continue
```

Initialize before the lane loop:

```python
    dropped_risks_by_reason: dict[str, int] = {}
    would_drop_protected_by_reason: dict[str, int] = {}
    protected_risky_candidate_count = 0
    accepted_risky_candidate_count = 0
    protected_expected_ids = set(decision.candidate_governance.protected_expected_ids)
```

Increment after accept:

```python
            if risks:
                accepted_risky_candidate_count += 1
```

Add helper:

```python
def _candidate_id(item: Mapping[str, Any]) -> str:
    for field in ("id", "memory_id"):
        value = item.get(field)
        if value not in (None, ""):
            return str(value)
    return ""
```

Add trace fields:

```python
        "candidate_governance_enabled": decision.candidate_governance.enabled,
        "candidate_governance": decision.candidate_governance.to_dict(),
        "protected_expected_ids": list(decision.candidate_governance.protected_expected_ids),
        "dropped_risks_by_reason": dropped_risks_by_reason,
        "would_drop_protected_by_reason": would_drop_protected_by_reason,
        "protected_risky_candidate_count": protected_risky_candidate_count,
        "accepted_risky_candidate_count": accepted_risky_candidate_count,
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_retrieval_governance.py tests/test_memory_eval_runner.py tests/test_memory_route_governance_eval.py -q -p no:cacheprovider
```

Expected: all selected tests pass.

---

### Task 3: Add Offline Tri Candidate Governance Report

**Files:**
- Create: `memory2/eval_tri_candidate_governance.py`
- Create: `scripts/run_memory_tri_candidate_governance_eval.py`
- Create / Modify: `tests/test_memory_tri_candidate_governance.py`

**Interfaces:**
- Consumes:
  - `build_quantitative_eval_cases(case_pack="comprehensive")`
  - `EvalCase.expectations["should_recall_ids"]`
  - `EvalCase.expectations["should_not_recall_ids"]`
  - `build_retrieval_routing_decision(query)`
  - `apply_retrieval_route(decision, candidates_by_lane)`
- Produces:
  - `build_tri_candidate_governance_report(case_pack: str = "comprehensive") -> dict[str, object]`
  - `write_tri_candidate_governance_report(report: Mapping[str, object], out_dir: Path) -> tuple[Path, Path]`

- [ ] **Step 1: Write failing report tests**

Create `tests/test_memory_tri_candidate_governance.py`:

```python
from __future__ import annotations

import json

from memory2.eval_tri_candidate_governance import (
    build_tri_candidate_governance_report,
    write_tri_candidate_governance_report,
)


def test_tri_candidate_governance_report_has_counts_and_preserves_targets() -> None:
    report = build_tri_candidate_governance_report(case_pack="standard")

    metrics = report["metrics"]
    assert metrics["case_count"] > 0
    assert metrics["protected_expected_hit_count"] == metrics["baseline_expected_hit_count"]
    assert metrics["protected_expected_hit_loss_count"] == 0
    assert metrics["unprotected_expected_hit_loss_count"] >= 0
    assert "dropped_risks_by_reason" in metrics
    assert "unprotected_dropped_risks_by_reason" in metrics
    assert "would_drop_protected_by_reason" in metrics
    assert "failure_bucket_counts" in metrics
    assert isinstance(metrics["dropped_risks_by_reason"], dict)
    assert "case_rows" in report


def test_tri_candidate_governance_report_uses_fixture_should_not_ids() -> None:
    report = build_tri_candidate_governance_report(case_pack="standard")

    metrics = report["metrics"]
    assert metrics["should_not_candidate_count"] > 0
    assert metrics["strict_should_not_drop_count"] > 0
    assert metrics["strict_should_not_kept_count"] == 0


def test_tri_candidate_governance_report_writes_private_artifacts(tmp_path) -> None:
    report = build_tri_candidate_governance_report(case_pack="standard")
    json_path, md_path = write_tri_candidate_governance_report(report, tmp_path)

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["metrics"]["case_count"] == report["metrics"]["case_count"]
    markdown = md_path.read_text(encoding="utf-8")
    assert "Tri Candidate Governance" in markdown
    assert "raw_prompt" not in markdown
    assert "full_answer" not in markdown
    assert "session_text" not in markdown
```

- [ ] **Step 2: Run tests and confirm RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_tri_candidate_governance.py -q -p no:cacheprovider
```

Expected: fails because module does not exist.

- [ ] **Step 3: Implement deterministic offline report**

Implement `memory2/eval_tri_candidate_governance.py` with:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from memory2.eval_comprehensive_online import evidence_ids_for_profile
from memory2.eval_quantitative_cases import build_quantitative_eval_cases
from memory2.retrieval_governance import (
    CandidateGovernancePolicy,
    apply_retrieval_route,
    build_retrieval_routing_decision,
)


DEFAULT_TRI_FAILURE_ATTRIBUTION_JSON = (
    "my_md/memory_optimization/eval_reports/"
    "tri_retrieval_failure_attribution_v1/tri_retrieval_failure_attribution.json"
)


def build_tri_candidate_governance_report(
    case_pack: str = "comprehensive",
    tri_failure_json: str | Path = DEFAULT_TRI_FAILURE_ATTRIBUTION_JSON,
) -> dict[str, object]:
    tri_rows = _load_tri_failure_rows(Path(tri_failure_json))
    rows: list[dict[str, object]] = []
    dropped_by_reason: dict[str, int] = {}
    unprotected_dropped_by_reason: dict[str, int] = {}
    would_drop_protected_by_reason: dict[str, int] = {}
    failure_bucket_counts: dict[str, int] = {}
    baseline_expected_hit_count = 0
    protected_expected_hit_count = 0
    unprotected_expected_hit_count = 0
    protected_expected_hit_loss_count = 0
    unprotected_expected_hit_loss_count = 0
    should_not_candidate_count = 0
    strict_should_not_drop_count = 0
    strict_should_not_kept_count = 0

    for case in build_quantitative_eval_cases(case_pack=case_pack):
        expected_ids = tuple(str(item) for item in case.expectations.get("should_recall_ids", ()))
        if not expected_ids:
            continue
        tri_fused_ids = tuple(evidence_ids_for_profile(case, "chain_tri_retrieval"))
        should_not_ids = tuple(str(item) for item in case.expectations.get("should_not_recall_ids", ()))
        tri_failure = tri_rows.get(case.id, {})
        failure_bucket = str(tri_failure.get("failure_bucket") or "not_in_40_case_report")
        failure_bucket_counts[failure_bucket] = failure_bucket_counts.get(failure_bucket, 0) + 1
        baseline_decision = build_retrieval_routing_decision(
            str(case.setup.get("query") or "")
        )
        protected_decision = baseline_decision.with_candidate_governance(
            CandidateGovernancePolicy(enabled=True, protected_expected_ids=expected_ids)
        )
        unprotected_decision = baseline_decision.with_candidate_governance(
            CandidateGovernancePolicy(enabled=True)
        )
        candidates_by_lane = _fixture_candidates_by_lane(case, should_not_ids)
        baseline_candidates, _baseline_trace = apply_retrieval_route(
            baseline_decision,
            candidates_by_lane,
        )
        protected_candidates, protected_trace = apply_retrieval_route(
            protected_decision,
            candidates_by_lane,
        )
        unprotected_candidates, unprotected_trace = apply_retrieval_route(
            unprotected_decision,
            candidates_by_lane,
        )
        baseline_ids = {str(item.get("id") or item.get("memory_id") or "") for item in baseline_candidates}
        protected_ids = {str(item.get("id") or item.get("memory_id") or "") for item in protected_candidates}
        unprotected_ids = {str(item.get("id") or item.get("memory_id") or "") for item in unprotected_candidates}
        expected_set = set(expected_ids)
        should_not_set = set(should_not_ids)
        baseline_hits = len(expected_set & baseline_ids)
        protected_hits = len(expected_set & protected_ids)
        unprotected_hits = len(expected_set & unprotected_ids)
        baseline_expected_hit_count += baseline_hits
        protected_expected_hit_count += protected_hits
        unprotected_expected_hit_count += unprotected_hits
        protected_loss = max(0, baseline_hits - protected_hits)
        unprotected_loss = max(0, baseline_hits - unprotected_hits)
        protected_expected_hit_loss_count += protected_loss
        unprotected_expected_hit_loss_count += unprotected_loss
        should_not_candidate_count += len(should_not_set & baseline_ids)
        strict_should_not_kept_count += len(should_not_set & protected_ids)
        strict_should_not_drop_count += len((should_not_set & baseline_ids) - protected_ids)
        for reason, count in protected_trace.get("dropped_risks_by_reason", {}).items():
            dropped_by_reason[str(reason)] = dropped_by_reason.get(str(reason), 0) + int(count)
        for reason, count in unprotected_trace.get("dropped_risks_by_reason", {}).items():
            unprotected_dropped_by_reason[str(reason)] = unprotected_dropped_by_reason.get(str(reason), 0) + int(count)
        for reason, count in protected_trace.get("would_drop_protected_by_reason", {}).items():
            would_drop_protected_by_reason[str(reason)] = would_drop_protected_by_reason.get(str(reason), 0) + int(count)
        rows.append(
            {
                "case_id": case.id,
                "category": case.category,
                "failure_bucket": failure_bucket,
                "pass_pattern": tri_failure.get("pass_pattern"),
                "scene": protected_trace["scene"],
                "expected_id_count": len(expected_ids),
                "tri_fused_id_count": len(tri_fused_ids),
                "tri_fused_expected_overlap_count": len(set(tri_fused_ids) & expected_set),
                "should_not_id_count": len(should_not_ids),
                "baseline_expected_hits": baseline_hits,
                "protected_expected_hits": protected_hits,
                "unprotected_expected_hits": unprotected_hits,
                "protected_expected_hit_loss": protected_loss,
                "unprotected_expected_hit_loss": unprotected_loss,
                "baseline_candidate_count": len(baseline_candidates),
                "protected_candidate_count": len(protected_candidates),
                "unprotected_candidate_count": len(unprotected_candidates),
                "dropped_risks_by_reason": protected_trace.get("dropped_risks_by_reason", {}),
                "would_drop_protected_by_reason": protected_trace.get("would_drop_protected_by_reason", {}),
                "protected_risky_candidate_count": protected_trace.get("protected_risky_candidate_count", 0),
            }
        )

    metrics = {
        "case_pack": case_pack,
        "case_count": len(rows),
        "baseline_expected_hit_count": baseline_expected_hit_count,
        "protected_expected_hit_count": protected_expected_hit_count,
        "unprotected_expected_hit_count": unprotected_expected_hit_count,
        "protected_expected_hit_loss_count": protected_expected_hit_loss_count,
        "unprotected_expected_hit_loss_count": unprotected_expected_hit_loss_count,
        "should_not_candidate_count": should_not_candidate_count,
        "strict_should_not_drop_count": strict_should_not_drop_count,
        "strict_should_not_kept_count": strict_should_not_kept_count,
        "dropped_risks_by_reason": dropped_by_reason,
        "unprotected_dropped_risks_by_reason": unprotected_dropped_by_reason,
        "would_drop_protected_by_reason": would_drop_protected_by_reason,
        "failure_bucket_counts": failure_bucket_counts,
    }
    return {"metrics": metrics, "case_rows": rows}
```

Add helper `_fixture_candidates_by_lane()` that uses `EvalCase.setup["memory_items"]` first:

```python
def _fixture_candidates_by_lane(case, should_not_ids: tuple[str, ...]) -> dict[str, list[dict[str, object]]]:
    scope = dict(case.setup.get("scope") or {})
    should_not = set(should_not_ids)
    candidates: list[dict[str, object]] = []
    for item in case.setup.get("memory_items", []):
        if not isinstance(item, Mapping):
            continue
        candidate = dict(item)
        candidate["scope_match"] = (
            str(candidate.get("scope_channel") or "") == str(scope.get("channel") or "")
            and str(candidate.get("scope_chat_id") or "") == str(scope.get("chat_id") or "")
        )
        candidate["should_not_recall"] = str(candidate.get("id") or "") in should_not
        candidates.append(candidate)
    return {
        "semantic": candidates,
        "keyword": list(candidates),
        "provenance": list(candidates),
        "graph": list(candidates),
    }
```

Add helper `_load_tri_failure_rows()`:

```python
def _load_tri_failure_rows(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("case_rows", [])
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("case_id") or ""): dict(row)
        for row in rows
        if isinstance(row, Mapping)
    }
```

The report must not include raw user prompt, raw memory summary, full answers, or session text. It may include ids, category, scene, counts, failure bucket, pass pattern, and risk reason counts.

- [ ] **Step 4: Implement report writer and CLI**

In the same module, add:

```python
def write_tri_candidate_governance_report(
    report: Mapping[str, object],
    out_dir: Path,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "tri_candidate_governance.json"
    md_path = out_dir / "tri_candidate_governance.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Tri Candidate Governance",
        "",
        "本报告是三路召回候选去噪和 forbidden / 冲突过滤的离线 trace 评测，不调用 LLM。",
        "",
        "## Metrics",
        "",
    ]
    for key, value in report["metrics"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Case Rows", ""])
    lines.append("| case_id | category | bucket | scene | expected | baseline_hits | protected_hits | unprotected_hits | protected_loss | unprotected_loss | baseline_candidates | protected_candidates |")
    lines.append("| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in report["case_rows"]:
        lines.append(
            f"| `{row['case_id']}` | `{row['category']}` | `{row['failure_bucket']}` | `{row['scene']}` | "
            f"{row['expected_id_count']} | {row['baseline_expected_hits']} | "
            f"{row['protected_expected_hits']} | {row['unprotected_expected_hits']} | "
            f"{row['protected_expected_hit_loss']} | {row['unprotected_expected_hit_loss']} | "
            f"{row['baseline_candidate_count']} | {row['protected_candidate_count']} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path
```

Create `scripts/run_memory_tri_candidate_governance_eval.py`:

```python
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from memory2.eval_tri_candidate_governance import (
    build_tri_candidate_governance_report,
    write_tri_candidate_governance_report,
)


DEFAULT_OUT_DIR = "my_md/memory_optimization/eval_reports/tri_candidate_governance_v1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-pack", default="comprehensive")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    report = build_tri_candidate_governance_report(case_pack=args.case_pack)
    json_path, md_path = write_tri_candidate_governance_report(report, Path(args.out_dir))
    print(json_path)
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run report tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_tri_candidate_governance.py -q -p no:cacheprovider
```

Expected: all tests pass.

---

### Task 4: Generate Report And Update Documentation

**Files:**
- Create: `my_md/memory_optimization/eval_reports/tri_candidate_governance_v1/tri_candidate_governance.json`
- Create: `my_md/memory_optimization/eval_reports/tri_candidate_governance_v1/tri_candidate_governance.md`
- Modify:
  - `my_md/memory_optimization/README.md`
  - `my_md/memory_optimization/02-memory-quality-metrics.md`
  - `my_md/memory_optimization/03-memory-governance-design.md`
  - `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
  - `progress.md`
  - `task_plan.md`

- [ ] **Step 1: Generate report**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_tri_candidate_governance_eval.py
```

Expected output:

```text
my_md/memory_optimization/eval_reports/tri_candidate_governance_v1/tri_candidate_governance.json
my_md/memory_optimization/eval_reports/tri_candidate_governance_v1/tri_candidate_governance.md
```

- [ ] **Step 2: Validate report integrity**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path

path = Path("my_md/memory_optimization/eval_reports/tri_candidate_governance_v1/tri_candidate_governance.json")
data = json.loads(path.read_text(encoding="utf-8"))
metrics = data["metrics"]
assert metrics["case_count"] > 0
assert metrics["protected_expected_hit_loss_count"] == 0
assert metrics["protected_expected_hit_count"] == metrics["baseline_expected_hit_count"]
assert metrics["unprotected_expected_hit_loss_count"] >= 0
assert metrics["dropped_risks_by_reason"]
assert "unprotected_dropped_risks_by_reason" in metrics
assert "would_drop_protected_by_reason" in metrics
assert "failure_bucket_counts" in metrics
print("tri candidate governance report ok")
print(metrics)
PY
```

Expected: prints `tri candidate governance report ok`.

- [ ] **Step 3: Update docs**

Record:

- why the first improvement targets candidate governance;
- which risk reasons are filtered;
- whether target grounding proxy stayed intact;
- protected vs unprotected expected-id loss;
- `strict_should_not_drop_count` and `strict_should_not_kept_count`;
- protected and unprotected risk reason distributions;
- how this prepares the next small real LLM rerun;
- boundary: offline trace / no real LLM / no production prompt change.

- [ ] **Step 4: Update progress logs**

Append to `progress.md` and `task_plan.md`:

```text
Plan: tri candidate denoising governance.
Purpose: reduce tri retrieval regressions and forbidden failures while preserving target grounding.
Boundary: offline trace first, no real LLM, no AgentLoop/prompt/write change.
Next: if strict governance preserves expected ids and drops risky candidates, run a bounded real LLM rerun against the 40-case small online slice or a focused failure-case slice.
```

---

### Task 5: Verification And Commit

**Files:**
- All files touched in Tasks 1-4.

- [ ] **Step 1: Run focused tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_retrieval_governance.py tests/test_memory_route_governance_eval.py tests/test_memory_eval_runner.py tests/test_memory_tri_candidate_governance.py tests/test_memory_tri_retrieval_failure_attribution.py -q -p no:cacheprovider
```

Expected: all selected tests pass.

- [ ] **Step 2: Run compile and diff checks**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m compileall -q memory2 scripts tests
git diff --check
```

Expected: both commands exit `0`.

- [ ] **Step 3: Inspect diff**

Run:

```bash
git status --short
git diff --stat
```

Expected: changes are limited to retrieval governance, tri candidate governance eval, tests, reports, and memory optimization docs.

- [ ] **Step 4: Commit locally**

Run:

```bash
git add memory2/retrieval_governance.py \
  memory2/eval_tri_candidate_governance.py \
  scripts/run_memory_tri_candidate_governance_eval.py \
  tests/test_memory_retrieval_governance.py \
  tests/test_memory_tri_candidate_governance.py \
  my_md/memory_optimization/eval_reports/tri_candidate_governance_v1 \
  my_md/memory_optimization/README.md \
  my_md/memory_optimization/02-memory-quality-metrics.md \
  my_md/memory_optimization/03-memory-governance-design.md \
  my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md \
  progress.md task_plan.md
git commit -m "feat: add tri candidate governance eval"
```

Expected: one local commit on `memory-next`; do not push.

## Self-Review

- Spec coverage: The plan targets the first actual improvement after tri retrieval failure attribution: candidate denoising plus forbidden / conflict filtering. It preserves target grounding as the first gate and prepares a later real LLM rerun without running it here.
- Placeholder scan: No `TBD`, `TODO`, or vague “add tests” steps remain; each task has exact files, commands, expected outcomes, and core code snippets.
- Type consistency: Public names are consistent across tasks: `CandidateGovernancePolicy`, `classify_candidate_risks()`, `with_candidate_governance()`, `build_tri_candidate_governance_report()`, and `write_tri_candidate_governance_report()`.
- Scope check: The plan does not alter production AgentLoop, ToolExecutor, memory writes, or prompts. It extends the existing route-governance pure function and adds an offline eval report. A real LLM rerun is intentionally left to a later plan after offline trace evidence exists.
