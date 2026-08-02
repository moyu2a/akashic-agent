# Memory P6o13 System Path Safe Version Governed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the current best eval-only safe version-governed memory answer path into the real system retrieval/prompt path behind explicit test-only flags, then validate it with fixture-driven system-path tests.

**Architecture:** Add a production-path-safe contract builder that consumes real retrieved memory candidates and route traces, not fixture answer expectations. Wire it into `DefaultMemoryEngine.retrieve()` as `off | shadow | replace` modes controlled through `MemoryConfig` and retrieval hints; default stays `off`. Add system-path tests and a system-path eval runner that exercise real `AgentLoop -> DefaultMemoryRetrievalPipeline -> DefaultMemoryEngine.retrieve() -> retrieved_memory_block -> prompt render` while still using controlled fixtures and scripted/fake providers.

**Tech Stack:** Python `>=3.12`, pytest, existing `AgentLoop`, existing `DefaultMemoryRetrievalPipeline`, existing `DefaultMemoryEngine`, existing `MemoryStore2`, existing `memory2.retrieval_governance`, existing `memory2.eval_answer_post_check`, JSON/Markdown reports.

## Global Constraints

- Worktree: `/home/jjh/git_work/akashic-agent/.worktrees/memory-next`.
- Branch: `memory-next`.
- Do not sync remote/main in this plan unless the user explicitly redirects.
- Do not push without explicit user instruction.
- Do not modify graph retrieval, graph routing, graph-all-on, `chain_all_on`, production memory writes, post-response memory writes, or production retry/fallback behavior.
- Do not copy fixture `expected ids`, `should_recall_ids`, `required_terms`, or oracle answer expectations into system-path runtime code.
- Default runtime behavior must remain unchanged: `MemoryConfig.safe_version_governed_mode = "off"` and existing `retrieved_memory_block` output is byte-for-byte unchanged for the same mocked retrieval result.
- Default `off` mode must not add safe-version hints, metadata, trace fields, or `RetrievalResult.metadata`; tests may assert the same observable result shape as before.
- `shadow` mode must record the safe version-governed contract in `MemoryEngineRetrieveResult.raw` and `trace`, but must keep `text_block` equal to the current memory block.
- `replace` mode is allowed only when two independent test/eval gates are true: `safe_version_governed_mode = "replace"` and `safe_version_governed_replace_allowed = True`. Session metadata may request `off` or `shadow`, but must not enable `replace` by itself.
- Replace-mode contract generation failure must be unmistakable: set `contract_generation_success = False`, set `replace_applied = False`, keep baseline `text_block`, and make the eval/report gate fail. Do not silently count this as a successful replace run.
- Model-visible contract must never include raw `forbidden_boundary_ids:` or `deleted_evidence_ids:` labels, nor raw forbidden/deleted ids.
- Model-visible contract may include compact allowed evidence snippets from retrieved memory because this is the prompt payload; committed reports must not include those raw snippets.
- Committed reports must not include raw prompt, raw session text, raw memory summaries, full answers, API keys, or authorization values.
- Existing eval-only P6o profiles remain available but are not the implementation target for this plan.
- Existing untracked file `my_md/memory_optimization/eval_reports/p6o13_system_path_real_llm_validation_v1/system_path_validation_intent.md` must not be overwritten or deleted.

---

## File Structure

- Create `memory2/system_path_safe_version_contract.py`
  - Production-path-safe contract builder and renderer that does not depend on `EvalCase`.
- Modify `agent/looping/ports.py`
  - Add `MemoryConfig.safe_version_governed_mode: str = "off"` and `MemoryConfig.safe_version_governed_replace_allowed: bool = False`.
- Modify `agent/looping/core.py`
  - Pass `config.memory.safe_version_governed_mode` and `config.memory.safe_version_governed_replace_allowed` into `DefaultMemoryRetrievalPipeline`.
- Modify `agent/retrieval/default_pipeline.py`
  - Convert config/session metadata into safe-version hints only when effective mode is `shadow` or allowed `replace`; default `off` must omit these hints.
  - Convert only config/eval-runner construction into `MemoryEngineRetrieveRequest.hints["safe_version_governed_replace_allowed"]`; session metadata must not grant replace permission.
  - Return safe version-governed metadata in `RetrievalResult.metadata` only for `shadow` and allowed `replace`; default `off` returns no safe-version metadata.
- Modify `plugins/default_memory/engine.py`
  - Build and attach safe version-governed shadow contract after current retrieval.
  - Keep default and shadow `text_block` unchanged.
  - Use replace mode only when explicitly requested and separately allowed by eval/test gate.
- Create `memory2/eval_system_path_safe_version.py`
  - Fixture-driven system-path eval helpers using real `AgentLoop` and `DefaultMemoryEngine`.
- Create `scripts/run_memory_system_path_safe_version_eval.py`
  - CLI for fake/scripted system-path smoke and optional real LLM validation.
- Create `tests/test_memory_system_path_safe_version_contract.py`
  - Pure contract builder/rendering tests.
- Modify `tests/test_memory_engine_contract.py`
  - Default/shadow/replace engine retrieve tests.
- Modify `tests/test_turn_pipelines.py`
  - Pipeline hint propagation and default behavior tests.
- Create `tests/test_memory_system_path_safe_version_eval.py`
  - AgentLoop system-path eval/report tests.
- Create reports during execution:
  - `my_md/memory_optimization/eval_reports/p6o13_system_path_safe_version_governed_v1/system_path_safe_version_eval.json`
  - `my_md/memory_optimization/eval_reports/p6o13_system_path_safe_version_governed_v1/system_path_safe_version_eval.md`
- Modify docs after execution:
  - `my_md/memory_optimization/README.md`
  - `progress.md`

---

## Task 0: Baseline And Existing Artifact Protection

**Files:**
- Modify: none

**Interfaces:**
- Consumes: current branch and existing untracked P6o-13 intent file.
- Produces: verified clean baseline and explicit note about untracked artifact.

- [ ] **Step 1: Confirm worktree and branch**

Run:

```bash
ROOT=$(git rev-parse --show-toplevel)
BRANCH=$(git branch --show-current)
printf 'ROOT=%s\nBRANCH=%s\n' "$ROOT" "$BRANCH"
test "$ROOT" = "/home/jjh/git_work/akashic-agent/.worktrees/memory-next"
test "$BRANCH" = "memory-next"
```

Expected:

```text
ROOT=/home/jjh/git_work/akashic-agent/.worktrees/memory-next
BRANCH=memory-next
```

- [ ] **Step 2: Inspect status and protect existing untracked intent**

Run:

```bash
git status --short
find my_md/memory_optimization/eval_reports/p6o13_system_path_real_llm_validation_v1 -maxdepth 2 -type f -print 2>/dev/null | sort
```

Expected: the `find` command prints `my_md/memory_optimization/eval_reports/p6o13_system_path_real_llm_validation_v1/system_path_validation_intent.md`. `git status --short` may print the parent directory as untracked. Do not assert exact status output because unrelated user files may also be present.

Do not edit, stage, delete, or overwrite this existing untracked directory in this plan.

---

## Task 1: Pure System-Path Safe Version Contract Builder

**Files:**
- Create: `memory2/system_path_safe_version_contract.py`
- Create: `tests/test_memory_system_path_safe_version_contract.py`

**Interfaces:**
- Consumes:
  - `memory2.retrieval_governance.CandidateGovernancePolicy`
  - `memory2.retrieval_governance.build_retrieval_routing_decision`
  - `memory2.retrieval_governance.apply_retrieval_route`
  - `memory2.version_chain_experiments.build_version_chain_shadow_result`
  - retrieved memory item dictionaries with fields like `id`, `memory_id`, `summary`, `source_ref`, `status`, `extra_json`, `candidate_risk_tier`, `candidate_risks`.
  - real replacement/provenance records from `MemoryStore2.list_replacements()` with `old_item_id` and `new_item_id`.
- Produces:
  - `SystemPathEvidenceContract`
  - `SystemPathSafeVersionResult`
  - `build_system_path_safe_version_contract(...)`
  - `render_system_path_evidence_contract_block(...)`
  - `system_path_contract_to_dict(...)`

- [ ] **Step 1: Write failing pure contract tests**

Create `tests/test_memory_system_path_safe_version_contract.py`:

```python
from __future__ import annotations

from memory2.system_path_safe_version_contract import (
    build_system_path_safe_version_contract,
    render_system_path_evidence_contract_block,
    system_path_contract_to_dict,
)


def _item(
    item_id: str,
    summary: str,
    *,
    status: str = "active",
    source_ref: str = "telegram:1:1",
    extra_json: dict[str, object] | None = None,
    **extra: object,
) -> dict[str, object]:
    return {
        "id": item_id,
        "summary": summary,
        "memory_type": "preference",
        "status": status,
        "source_ref": source_ref,
        "extra_json": extra_json or {},
        **extra,
    }


def test_system_path_contract_uses_tiered_governance_without_fixture_ids() -> None:
    result = build_system_path_safe_version_contract(
        query="我现在默认用什么测试框架？",
        baseline_items=[
            _item("m-current", "用户偏好使用 pytest。"),
            _item("m-forbidden", "用户禁止使用 nose。", forbidden=True),
        ],
        route_trace={
            "candidates_by_lane": {
                "semantic": [
                    _item("m-current", "用户偏好使用 pytest。"),
                    _item("m-forbidden", "用户禁止使用 nose。", forbidden=True),
                ],
                "keyword": [],
                "provenance": [],
                "graph": [],
            }
        },
        replacements=[],
        top_k=8,
    )

    assert result.contract.production_safe is True
    assert result.contract.uses_fixture_answer_expectations is False
    assert result.contract.allowed_evidence_ids == ("m-current",)
    assert result.contract.forbidden_boundary_ids == ("m-forbidden",)
    assert result.contract.deleted_evidence_ids == ("m-forbidden",)
    assert result.contract.candidate_risk_tier_counts["delete"] == 1
    assert result.contract.accepted_candidate_risk_tier_counts["allow"] == 1


def test_system_path_render_hides_raw_forbidden_and_deleted_ids() -> None:
    result = build_system_path_safe_version_contract(
        query="测试偏好是什么？",
        baseline_items=[_item("m-current", "用户偏好使用 pytest。")],
        route_trace={
            "candidates_by_lane": {
                "semantic": [
                    _item("m-current", "用户偏好使用 pytest。"),
                    _item("blocked-id", "禁止使用 nose。", forbidden=True),
                ],
                "keyword": [],
                "provenance": [],
                "graph": [],
            }
        },
        replacements=[],
        top_k=8,
    )

    text = render_system_path_evidence_contract_block(result.contract)

    assert "Evidence Contract: system_memory_safe_version_governed" in text
    assert "allowed_evidence:" in text
    assert "用户偏好使用 pytest。" in text
    assert "forbidden_boundary_count: 1" in text
    assert "deleted_evidence_count: 1" in text
    assert "forbidden_boundary_ids:" not in text
    assert "deleted_evidence_ids:" not in text
    assert "likely_relevant_evidence_ids:" not in text
    assert "active_version_ids:" not in text
    assert "blocked-id" not in text
    assert "m-current" not in text


def test_system_path_contract_dict_is_private_but_auditable() -> None:
    result = build_system_path_safe_version_contract(
        query="测试偏好是什么？",
        baseline_items=[_item("m-current", "用户偏好使用 pytest。")],
        route_trace={
            "candidates_by_lane": {
                "semantic": [_item("m-current", "用户偏好使用 pytest。")],
                "keyword": [],
                "provenance": [],
                "graph": [],
            }
        },
        replacements=[],
        top_k=8,
    )

    payload = system_path_contract_to_dict(result.contract)

    assert payload["production_safe"] is True
    assert payload["production_safe_evidence_contract"] is True
    assert payload["uses_fixture_answer_expectations"] is False
    assert payload["allowed_evidence_ids"] == ["m-current"]
    assert "raw_prompt" not in payload
    assert "raw_answer" not in payload


def test_system_path_contract_enforces_replacement_version_boundary() -> None:
    old_item = _item(
        "m-old",
        "用户旧偏好使用 nose。",
        status="superseded",
        source_ref="telegram:1:old",
    )
    current_item = _item(
        "m-current",
        "用户当前偏好使用 pytest。",
        status="active",
        source_ref="telegram:1:new",
    )

    result = build_system_path_safe_version_contract(
        query="我现在默认用什么测试框架？",
        baseline_items=[old_item, current_item],
        route_trace={
            "candidates_by_lane": {
                "semantic": [old_item, current_item],
                "keyword": [],
                "provenance": [],
                "graph": [],
            }
        },
        replacements=[
            {
                "old_item_id": "m-old",
                "new_item_id": "m-current",
                "old_memory_type": "preference",
                "new_memory_type": "preference",
                "old_summary": "用户旧偏好使用 nose。",
                "new_summary": "用户当前偏好使用 pytest。",
                "old_source_ref": "telegram:1:old",
                "new_source_ref": "telegram:1:new",
            }
        ],
        top_k=8,
    )

    text = render_system_path_evidence_contract_block(result.contract)

    assert result.contract.allowed_evidence_ids == ("m-current",)
    assert result.contract.active_version_ids == ("m-current",)
    assert result.contract.stale_warning_ids == ("m-old",)
    assert result.contract.deleted_evidence_ids == ("m-old",)
    assert result.contract.version_boundary["replacement_count"] == 1
    assert result.contract.version_boundary["stale_recalled_count"] == 0
    assert "m-old" not in text
    assert "用户旧偏好使用 nose。" not in text


def test_system_path_contract_retains_downgrade_and_requires_review_candidates() -> None:
    downgrade = _item(
        "m-downgrade",
        "用户可能偏好 pytest。",
        source_ref="telegram:1@post_response",
    )
    requires_review = _item(
        "m-review",
        "用户偏好测试工具存在冲突，需要复核。",
        source_ref="telegram:1:2",
        conflict=True,
    )

    result = build_system_path_safe_version_contract(
        query="我默认用什么测试框架？",
        baseline_items=[downgrade, requires_review],
        route_trace={
            "candidates_by_lane": {
                "semantic": [downgrade, requires_review],
                "keyword": [],
                "provenance": [],
                "graph": [],
            }
        },
        replacements=[],
        top_k=8,
    )

    assert result.contract.allowed_evidence_ids == ("m-downgrade", "m-review")
    assert result.contract.downgrade_ids == ("m-downgrade",)
    assert result.contract.requires_review_ids == ("m-review",)
    assert result.contract.candidate_risk_tier_counts["downgrade"] == 1
    assert result.contract.candidate_risk_tier_counts["requires_review"] == 1
    assert result.contract.accepted_candidate_risk_tier_counts["downgrade"] == 1
    assert result.contract.accepted_candidate_risk_tier_counts["requires_review"] == 1
```

- [ ] **Step 2: Run RED tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_system_path_safe_version_contract.py \
  -q -p no:cacheprovider
```

Expected: fails with `ModuleNotFoundError: No module named 'memory2.system_path_safe_version_contract'`.

- [ ] **Step 3: Implement pure contract module**

Create `memory2/system_path_safe_version_contract.py`:

```python
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from memory2.retrieval_governance import (
    CandidateGovernancePolicy,
    apply_retrieval_route,
    build_retrieval_routing_decision,
)
from memory2.version_chain_experiments import build_version_chain_shadow_result

SYSTEM_SAFE_VERSION_PROFILE = "system_memory_safe_version_governed"


@dataclass(frozen=True)
class SystemPathEvidenceContract:
    profile_name: str
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
    candidate_risk_tier_counts: dict[str, int]
    accepted_candidate_risk_tier_counts: dict[str, int]
    tiered_deleted_risks_by_reason: dict[str, int]
    version_boundary: dict[str, object]


@dataclass(frozen=True)
class SystemPathSafeVersionResult:
    contract: SystemPathEvidenceContract
    text_block: str
    accepted_items: tuple[dict[str, object], ...]
    trace: dict[str, object]


def build_system_path_safe_version_contract(
    *,
    query: str,
    baseline_items: Sequence[Mapping[str, Any]],
    route_trace: Mapping[str, Any],
    replacements: Sequence[Mapping[str, Any]] = (),
    top_k: int = 8,
) -> SystemPathSafeVersionResult:
    candidates_by_lane = _candidate_lanes(route_trace, baseline_items)
    decision = build_retrieval_routing_decision(query).with_candidate_governance(
        CandidateGovernancePolicy(enabled=True, mode="tiered")
    )
    accepted, trace = apply_retrieval_route(decision, candidates_by_lane)
    accepted = accepted[: max(1, int(top_k))]
    allowed_ids = _ids(accepted)
    version_boundary = build_version_chain_shadow_result(
        memory_items=list(_item_by_id(candidates_by_lane).values()),
        replacements=[dict(item) for item in replacements],
        recalled_items=[dict(item) for item in accepted],
    )
    records = _tier_records(trace)
    deleted_ids = tuple(
        item_id
        for item_id, record in records.items()
        if str(record.get("tier") or "") == "delete"
    )
    forbidden_boundary_ids = tuple(
        item_id
        for item_id in deleted_ids
        if "forbidden_candidate" in _string_tuple(records.get(item_id, {}).get("risks", ()))
        or _truthy(_item_by_id(candidates_by_lane).get(item_id, {}), "forbidden")
    )
    downgrade_ids = tuple(
        item_id for item_id in allowed_ids
        if str(records.get(item_id, {}).get("tier") or "") == "downgrade"
    )
    requires_review_ids = tuple(
        item_id for item_id in allowed_ids
        if str(records.get(item_id, {}).get("tier") or "") == "requires_review"
    )
    conflict_warning_ids = tuple(
        item_id for item_id in allowed_ids
        if "conflict_candidate" in _string_tuple(records.get(item_id, {}).get("risks", ()))
    )
    insufficient_ids = tuple(
        item_id for item_id in allowed_ids
        if "insufficient_evidence" in _string_tuple(records.get(item_id, {}).get("risks", ()))
    )
    stale_ids = tuple(
        _dedupe(
            (
                *deleted_ids,
                *version_boundary.experimental_result.get("stale_recalled_ids", []),
                *[
                    item_id
                    for item_id in _item_by_id(candidates_by_lane)
                    if str(
                        _item_by_id(candidates_by_lane)
                        .get(item_id, {})
                        .get("status")
                        or ""
                    ).lower()
                    == "superseded"
                ],
            )
        )
    )
    replacement_active_leaf_ids = set(
        str(item_id)
        for item_id in version_boundary.experimental_result.get("active_leaf_ids", [])
    )
    active_ids = tuple(
        item_id for item_id in allowed_ids
        if str(_item_by_id(candidates_by_lane).get(item_id, {}).get("status") or "active").lower()
        == "active"
        and (not replacement_active_leaf_ids or item_id in replacement_active_leaf_ids or item_id not in _replacement_ids(replacements))
    )
    likely_ids = tuple(item_id for item_id in allowed_ids if item_id not in requires_review_ids)
    contract = SystemPathEvidenceContract(
        profile_name=SYSTEM_SAFE_VERSION_PROFILE,
        production_safe=True,
        uses_fixture_answer_expectations=False,
        candidate_governance_mode="tiered",
        allowed_evidence=_evidence_lines(accepted),
        likely_relevant_evidence=_evidence_lines(
            [item for item in accepted if _item_id(item) in set(likely_ids)]
        ),
        stale_warning=stale_ids,
        conflict_warning=conflict_warning_ids,
        active_version=active_ids,
        forbidden_boundary=forbidden_boundary_ids,
        allowed_evidence_ids=allowed_ids,
        likely_relevant_evidence_ids=likely_ids,
        downgrade_ids=downgrade_ids,
        requires_review_ids=requires_review_ids,
        stale_warning_ids=stale_ids,
        conflict_warning_ids=conflict_warning_ids,
        active_version_ids=active_ids,
        insufficient_evidence_ids=insufficient_ids,
        insufficient_evidence_fallback=not bool(allowed_ids) or bool(insufficient_ids),
        forbidden_boundary_ids=forbidden_boundary_ids,
        deleted_evidence_ids=deleted_ids,
        candidate_risk_tier_counts=_int_dict(trace.get("candidate_risk_tier_counts", {})),
        accepted_candidate_risk_tier_counts=_int_dict(
            trace.get("accepted_candidate_risk_tier_counts", {})
        ),
        tiered_deleted_risks_by_reason=_int_dict(
            trace.get("tiered_deleted_risks_by_reason", {})
        ),
        version_boundary={
            "replacement_count": int(version_boundary.metrics.get("replacement_count", 0) or 0),
            "chain_count": int(version_boundary.metrics.get("chain_count", 0) or 0),
            "active_leaf_count": int(version_boundary.metrics.get("active_leaf_count", 0) or 0),
            "stale_recalled_count": int(version_boundary.metrics.get("stale_recalled_count", 0) or 0),
            "superseded_recalled_count": int(version_boundary.metrics.get("superseded_recalled_count", 0) or 0),
            "rollback_candidate_count": int(version_boundary.metrics.get("rollback_candidate_count", 0) or 0),
            "conflict_chain_count": int(version_boundary.metrics.get("conflict_chain_count", 0) or 0),
        },
    )
    return SystemPathSafeVersionResult(
        contract=contract,
        text_block=render_system_path_evidence_contract_block(contract),
        accepted_items=tuple(dict(item) for item in accepted),
        trace={"safe_version_governed": system_path_contract_to_dict(contract)},
    )
```

The implementation must also include private helpers `_candidate_lanes`, `_ids`, `_item_id`, `_item_by_id`, `_tier_records`, `_string_tuple`, `_truthy`, `_dedupe`, `_int_dict`, and `system_path_contract_to_dict`. These helpers must use only runtime candidate data and must not import `EvalCase`.
The implementation must also include `_evidence_lines(items)` and `_replacement_ids(replacements)`. `_evidence_lines` may include compact summaries because it is model-visible prompt evidence, but it must not include raw memory IDs. `system_path_contract_to_dict` must not include those summaries in committed reports.
`system_path_contract_to_dict` must include both `production_safe` and `production_safe_evidence_contract` so existing `build_answer_post_check_shadow` can consume the same payload without an adapter.

- [ ] **Step 4: Implement renderer**

Add this function to `memory2/system_path_safe_version_contract.py`:

```python
def render_system_path_evidence_contract_block(
    contract: SystemPathEvidenceContract,
) -> str:
    lines = [
        f"Evidence Contract: {contract.profile_name}",
        "production_safe=true",
        "uses_fixture_answer_expectations=false",
        "candidate_governance_mode: " + contract.candidate_governance_mode,
        "allowed_evidence:",
        *_indent_lines(contract.allowed_evidence),
        "likely_relevant_evidence_count: "
        + str(len(contract.likely_relevant_evidence_ids)),
        "active_version_count: " + str(len(contract.active_version_ids)),
        "stale_warning_count: " + str(len(contract.stale_warning_ids)),
        "conflict_warning_count: " + str(len(contract.conflict_warning_ids)),
        "forbidden_boundary_count: " + str(len(contract.forbidden_boundary_ids)),
        "deleted_evidence_count: " + str(len(contract.deleted_evidence_ids)),
        "insufficient_evidence_fallback: "
        + ("true" if contract.insufficient_evidence_fallback else "false"),
        (
            "Instruction: answer only from allowed_evidence. If evidence is "
            "insufficient, say that the available memory is insufficient. Do not "
            "use deleted, superseded, cross-scope, or forbidden boundary evidence."
        ),
    ]
    return "\n".join(lines)
```

The renderer must not render raw memory ID fields such as `forbidden_boundary_ids:`, `deleted_evidence_ids:`, `likely_relevant_evidence_ids:`, or `active_version_ids:`.

- [ ] **Step 5: Run GREEN tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_system_path_safe_version_contract.py \
  -q -p no:cacheprovider
```

Expected:

```text
5 passed
```

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add memory2/system_path_safe_version_contract.py tests/test_memory_system_path_safe_version_contract.py
git commit -m "feat: add system path safe version contract builder"
```

---

## Task 2: Feature Flag And Retrieval Pipeline Hint Propagation

**Files:**
- Modify: `agent/looping/ports.py`
- Modify: `agent/looping/core.py`
- Modify: `agent/retrieval/default_pipeline.py`
- Modify: `tests/test_turn_pipelines.py`

**Interfaces:**
- Consumes:
  - `AgentLoopConfig.memory`
  - `DefaultMemoryRetrievalPipeline.retrieve(...)`
  - `RetrievalRequest.session_metadata`
  - `MemoryEngineRetrieveRequest.hints`
- Produces:
  - `MemoryConfig.safe_version_governed_mode`
  - `MemoryConfig.safe_version_governed_replace_allowed`
  - `DefaultMemoryRetrievalPipeline(memory, safe_version_governed_mode="off", safe_version_governed_replace_allowed=False)`
  - retrieval hints `safe_version_governed_mode` and `safe_version_governed_replace_allowed` only outside default `off`.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_turn_pipelines.py`:

```python
async def test_retrieval_pipeline_defaults_safe_version_mode_off() -> None:
    engine = _RecordingMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(MemoryServices(engine=engine))

    result = await pipeline.retrieve(_retrieval_request("请记得我的测试偏好"))

    assert "safe_version_governed_mode" not in engine.requests[-1].hints
    assert "safe_version_governed_replace_allowed" not in engine.requests[-1].hints
    assert "safe_version_governed_mode" not in result.metadata


async def test_retrieval_pipeline_passes_safe_version_mode_from_config() -> None:
    engine = _RecordingMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(
        MemoryServices(engine=engine),
        safe_version_governed_mode="shadow",
    )

    result = await pipeline.retrieve(_retrieval_request("请记得我的测试偏好"))

    assert engine.requests[-1].hints["safe_version_governed_mode"] == "shadow"
    assert result.metadata.get("safe_version_governed_mode") == "shadow"


async def test_retrieval_pipeline_allows_session_metadata_shadow_override_for_tests() -> None:
    engine = _RecordingMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(
        MemoryServices(engine=engine),
        safe_version_governed_mode="off",
    )
    request = _retrieval_request("请记得我的测试偏好")
    request.session_metadata["safe_version_governed_mode"] = "shadow"

    await pipeline.retrieve(request)

    assert engine.requests[-1].hints["safe_version_governed_mode"] == "shadow"
    assert engine.requests[-1].hints["safe_version_governed_replace_allowed"] is False


async def test_retrieval_pipeline_rejects_session_metadata_replace_without_allow_gate() -> None:
    engine = _RecordingMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(
        MemoryServices(engine=engine),
        safe_version_governed_mode="off",
        safe_version_governed_replace_allowed=False,
    )
    request = _retrieval_request("请记得我的测试偏好")
    request.session_metadata["safe_version_governed_mode"] = "replace"

    await pipeline.retrieve(request)

    assert engine.requests[-1].hints["safe_version_governed_mode"] == "shadow"
    assert engine.requests[-1].hints["safe_version_governed_replace_allowed"] is False


async def test_retrieval_pipeline_rejects_session_metadata_replace_even_when_allow_flag_true() -> None:
    engine = _RecordingMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(
        MemoryServices(engine=engine),
        safe_version_governed_mode="off",
        safe_version_governed_replace_allowed=True,
    )
    request = _retrieval_request("请记得我的测试偏好")
    request.session_metadata["safe_version_governed_mode"] = "replace"

    await pipeline.retrieve(request)

    assert engine.requests[-1].hints["safe_version_governed_mode"] == "shadow"
    assert engine.requests[-1].hints["safe_version_governed_replace_allowed"] is False


async def test_retrieval_pipeline_allows_replace_only_from_config_gate() -> None:
    engine = _RecordingMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(
        MemoryServices(engine=engine),
        safe_version_governed_mode="replace",
        safe_version_governed_replace_allowed=True,
    )

    await pipeline.retrieve(_retrieval_request("请记得我的测试偏好"))

    assert engine.requests[-1].hints["safe_version_governed_mode"] == "replace"
    assert engine.requests[-1].hints["safe_version_governed_replace_allowed"] is True


def test_agent_loop_passes_safe_version_config_to_default_retrieval_pipeline(tmp_path: Path) -> None:
    tools = ToolRegistry()
    tools.register(_NoopTool())

    loop = AgentLoop(
        AgentLoopDeps(
            bus=MagicMock(),
            provider=cast(Any, _Provider()),
            light_provider=cast(Any, _Provider()),
            tools=tools,
            session_manager=MagicMock(),
            workspace=tmp_path,
            memory_services=MemoryServices(engine=cast(Any, _FakeMemoryEngine())),
            retrieval_pipeline=None,
        ),
        AgentLoopConfig(
            memory=MemoryConfig(
                safe_version_governed_mode="replace",
                safe_version_governed_replace_allowed=True,
            )
        ),
    )

    assert isinstance(loop._retrieval_pipeline, DefaultMemoryRetrievalPipeline)
    assert loop._retrieval_pipeline._safe_version_governed_mode == "replace"
    assert loop._retrieval_pipeline._safe_version_governed_replace_allowed is True
```

If `tests/test_turn_pipelines.py` does not already have `_RecordingMemoryEngine` or `_retrieval_request`, add minimal local helpers:

```python
class _RecordingMemoryEngine:
    def __init__(self) -> None:
        self.requests: list[MemoryEngineRetrieveRequest] = []

    async def retrieve(self, request: MemoryEngineRetrieveRequest) -> MemoryEngineRetrieveResult:
        self.requests.append(request)
        mode = str(request.hints.get("safe_version_governed_mode") or "off")
        raw = {}
        if mode in {"shadow", "replace"}:
            raw["safe_version_governed_metadata"] = {
                "mode": mode,
                "contract_generation_success": True,
            }
        return MemoryEngineRetrieveResult(text_block="baseline memory", hits=[], raw=raw)
```

Also update imports in `tests/test_turn_pipelines.py` if missing:

```python
from agent.retrieval.default_pipeline import DefaultMemoryRetrievalPipeline
from agent.looping.ports import MemoryConfig
from core.memory.engine import MemoryEngineRetrieveRequest, MemoryEngineRetrieveResult
```

- [ ] **Step 2: Run RED tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_turn_pipelines.py::test_retrieval_pipeline_defaults_safe_version_mode_off \
  tests/test_turn_pipelines.py::test_retrieval_pipeline_passes_safe_version_mode_from_config \
  tests/test_turn_pipelines.py::test_retrieval_pipeline_allows_session_metadata_shadow_override_for_tests \
  tests/test_turn_pipelines.py::test_retrieval_pipeline_rejects_session_metadata_replace_without_allow_gate \
  tests/test_turn_pipelines.py::test_retrieval_pipeline_rejects_session_metadata_replace_even_when_allow_flag_true \
  tests/test_turn_pipelines.py::test_retrieval_pipeline_allows_replace_only_from_config_gate \
  tests/test_turn_pipelines.py::test_agent_loop_passes_safe_version_config_to_default_retrieval_pipeline \
  -q -p no:cacheprovider
```

Expected: at least one failure because the pipeline does not yet accept/pass the mode.

- [ ] **Step 3: Add memory config flag**

Modify `agent/looping/ports.py`:

```python
@dataclass
class MemoryConfig:
    window: int = 40
    safe_version_governed_mode: str = "off"
    safe_version_governed_replace_allowed: bool = False
```

Keep `keep_count` unchanged.

- [ ] **Step 4: Pass config into pipeline**

Modify `agent/looping/core.py`:

```python
retrieval_pipeline = deps.retrieval_pipeline or DefaultMemoryRetrievalPipeline(
    memory=memory_svc,
    safe_version_governed_mode=config.memory.safe_version_governed_mode,
    safe_version_governed_replace_allowed=config.memory.safe_version_governed_replace_allowed,
)
```

- [ ] **Step 5: Implement hint propagation**

Modify `agent/retrieval/default_pipeline.py`:

```python
class DefaultMemoryRetrievalPipeline(MemoryRetrievalPipeline):
    def __init__(
        self,
        memory: MemoryServices,
        safe_version_governed_mode: str = "off",
        safe_version_governed_replace_allowed: bool = False,
    ) -> None:
        self._memory = memory
        self._safe_version_governed_mode = _safe_version_mode(
            safe_version_governed_mode
        )
        self._safe_version_governed_replace_allowed = bool(
            safe_version_governed_replace_allowed
        )
```

Before creating `MemoryEngineRetrieveRequest`, compute:

```python
configured_mode = _safe_version_mode(
    self._safe_version_governed_mode
)
safe_mode = configured_mode
session_mode_raw = request.session_metadata.get("safe_version_governed_mode")
session_mode = (
    _safe_version_mode(session_mode_raw)
    if session_mode_raw is not None
    else ""
)
if session_mode in {"off", "shadow"}:
    safe_mode = session_mode
elif session_mode == "replace" and safe_mode != "replace":
    safe_mode = "shadow"
replace_allowed = (
    safe_mode == "replace"
    and configured_mode == "replace"
    and self._safe_version_governed_replace_allowed
)
if safe_mode == "replace" and not replace_allowed:
    safe_mode = "shadow"
hints = dict(request.extra or {})
if safe_mode in {"shadow", "replace"}:
    hints["safe_version_governed_mode"] = safe_mode
    hints["safe_version_governed_replace_allowed"] = (
        replace_allowed and safe_mode == "replace"
    )
```

Then pass `hints=hints` into `MemoryEngineRetrieveRequest`.

Return metadata:

```python
safe_metadata = dict(result.raw.get("safe_version_governed_metadata", {}) or {})
metadata = (
    {**safe_metadata, "safe_version_governed_mode": safe_mode}
    if safe_mode in {"shadow", "replace"} and safe_metadata
    else {}
)
return RetrievalResult(
    block=result.text_block,
    trace=_build_retrieval_trace(result),
    metadata=metadata,
)
```

Add helper:

```python
def _safe_version_mode(value: object) -> str:
    mode = str(value or "off")
    if mode not in {"off", "shadow", "replace"}:
        return "off"
    return mode
```

- [ ] **Step 6: Run GREEN tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_turn_pipelines.py::test_retrieval_pipeline_defaults_safe_version_mode_off \
  tests/test_turn_pipelines.py::test_retrieval_pipeline_passes_safe_version_mode_from_config \
  tests/test_turn_pipelines.py::test_retrieval_pipeline_allows_session_metadata_shadow_override_for_tests \
  tests/test_turn_pipelines.py::test_retrieval_pipeline_rejects_session_metadata_replace_without_allow_gate \
  tests/test_turn_pipelines.py::test_retrieval_pipeline_rejects_session_metadata_replace_even_when_allow_flag_true \
  tests/test_turn_pipelines.py::test_retrieval_pipeline_allows_replace_only_from_config_gate \
  tests/test_turn_pipelines.py::test_agent_loop_passes_safe_version_config_to_default_retrieval_pipeline \
  -q -p no:cacheprovider
```

Expected:

```text
7 passed
```

- [ ] **Step 7: Commit Task 2**

Run:

```bash
git add agent/looping/ports.py agent/looping/core.py agent/retrieval/default_pipeline.py tests/test_turn_pipelines.py
git commit -m "feat: pass safe version memory mode through retrieval pipeline"
```

---

## Task 3: DefaultMemoryEngine Shadow And Replace Modes

**Files:**
- Modify: `plugins/default_memory/engine.py`
- Modify: `tests/test_memory_engine_contract.py`

**Interfaces:**
- Consumes:
  - `request.hints["safe_version_governed_mode"]`
  - `route_trace["candidates_by_lane"]`
  - current `items`, `text_block`, `injected_ids`, `hits`
  - `memory2.system_path_safe_version_contract`
- Produces:
  - `raw["safe_version_governed_shadow"]`
  - `raw["safe_version_governed_metadata"]`
  - `trace["safe_version_governed_mode"]`
  - `trace["safe_version_governed_replace_applied"]`
  - optional replace-mode `text_block`.

- [ ] **Step 1: Write failing engine tests**

Append to `tests/test_memory_engine_contract.py`:

```python
@pytest.mark.asyncio
async def test_default_memory_engine_safe_version_shadow_keeps_text_block(tmp_path: Path) -> None:
    items = [
        {
            "id": "m-current",
            "summary": "用户偏好使用 pytest。",
            "score": 0.91,
            "source_ref": "telegram:1:1",
            "memory_type": "preference",
            "status": "active",
            "extra_json": {},
        }
    ]
    route_trace = {
        "candidates_by_lane": {
            "semantic": items,
            "keyword": [],
            "provenance": [],
            "graph": [],
        }
    }
    retriever = SimpleNamespace(
        retrieve_with_lanes=AsyncMock(return_value=(items, items, [])),
        retrieve_with_trace=AsyncMock(return_value=(items, route_trace)),
        build_injection_block=MagicMock(return_value=("baseline memory block", ["m-current"])),
    )
    store = SimpleNamespace(list_replacements=MagicMock(return_value=[]))
    engine = _make_default_engine(retriever=cast(Any, retriever))
    engine._v2_store = store

    result = await engine.retrieve(
        MemoryEngineRetrieveRequest(
            query="我默认用什么测试框架？",
            scope=MemoryScope(session_key="s", channel="telegram", chat_id="1"),
            hints={
                "require_scope_match": True,
                "safe_version_governed_mode": "shadow",
            },
            top_k=8,
        )
    )

    assert result.text_block == "baseline memory block"
    assert result.raw["safe_version_governed_metadata"]["mode"] == "shadow"
    assert result.raw["safe_version_governed_metadata"]["replace_applied"] is False
    assert result.raw["safe_version_governed_shadow"]["production_safe"] is True
    assert "Evidence Contract: system_memory_safe_version_governed" not in result.text_block


@pytest.mark.asyncio
async def test_default_memory_engine_safe_version_replace_uses_contract_text(tmp_path: Path) -> None:
    items = [
        {
            "id": "m-current",
            "summary": "用户偏好使用 pytest。",
            "score": 0.91,
            "source_ref": "telegram:1:1",
            "memory_type": "preference",
            "status": "active",
            "extra_json": {},
        }
    ]
    route_trace = {
        "candidates_by_lane": {
            "semantic": items,
            "keyword": [],
            "provenance": [],
            "graph": [],
        }
    }
    retriever = SimpleNamespace(
        retrieve_with_lanes=AsyncMock(return_value=(items, items, [])),
        retrieve_with_trace=AsyncMock(return_value=(items, route_trace)),
        build_injection_block=MagicMock(return_value=("baseline memory block", ["m-current"])),
    )
    store = SimpleNamespace(list_replacements=MagicMock(return_value=[]))
    engine = _make_default_engine(retriever=cast(Any, retriever))
    engine._v2_store = store

    result = await engine.retrieve(
        MemoryEngineRetrieveRequest(
            query="我默认用什么测试框架？",
            scope=MemoryScope(session_key="s", channel="telegram", chat_id="1"),
            hints={
                "require_scope_match": True,
                "safe_version_governed_mode": "replace",
                "safe_version_governed_replace_allowed": True,
            },
            top_k=8,
        )
    )

    assert "Evidence Contract: system_memory_safe_version_governed" in result.text_block
    assert "forbidden_boundary_ids:" not in result.text_block
    assert "deleted_evidence_ids:" not in result.text_block
    assert result.raw["safe_version_governed_metadata"]["mode"] == "replace"
    assert result.raw["safe_version_governed_metadata"]["replacement_requested"] is True
    assert result.raw["safe_version_governed_metadata"]["replace_applied"] is True


@pytest.mark.asyncio
async def test_default_memory_engine_safe_version_replace_requires_allow_gate(tmp_path: Path) -> None:
    items = [
        {
            "id": "m-current",
            "summary": "用户偏好使用 pytest。",
            "score": 0.91,
            "source_ref": "telegram:1:1",
            "memory_type": "preference",
            "status": "active",
            "extra_json": {},
        }
    ]
    route_trace = {
        "candidates_by_lane": {
            "semantic": items,
            "keyword": [],
            "provenance": [],
            "graph": [],
        }
    }
    retriever = SimpleNamespace(
        retrieve_with_lanes=AsyncMock(return_value=(items, items, [])),
        retrieve_with_trace=AsyncMock(return_value=(items, route_trace)),
        build_injection_block=MagicMock(return_value=("baseline memory block", ["m-current"])),
    )
    engine = _make_default_engine(retriever=cast(Any, retriever))
    engine._v2_store = SimpleNamespace(list_replacements=MagicMock(return_value=[]))

    result = await engine.retrieve(
        MemoryEngineRetrieveRequest(
            query="我默认用什么测试框架？",
            scope=MemoryScope(session_key="s", channel="telegram", chat_id="1"),
            hints={
                "require_scope_match": True,
                "safe_version_governed_mode": "replace",
                "safe_version_governed_replace_allowed": False,
            },
            top_k=8,
        )
    )

    assert result.text_block == "baseline memory block"
    assert result.raw["safe_version_governed_metadata"]["mode"] == "shadow"
    assert result.raw["safe_version_governed_metadata"]["replacement_requested"] is False
    assert result.raw["safe_version_governed_metadata"]["replace_applied"] is False


@pytest.mark.asyncio
async def test_default_memory_engine_off_adds_no_safe_version_metadata() -> None:
    items = [
        {
            "id": "m-current",
            "summary": "用户偏好使用 pytest。",
            "score": 0.91,
            "source_ref": "telegram:1:1",
            "memory_type": "preference",
            "status": "active",
            "extra_json": {},
        }
    ]
    retriever = SimpleNamespace(
        retrieve_with_lanes=AsyncMock(return_value=(items, items, [])),
        build_injection_block=MagicMock(return_value=("baseline memory block", ["m-current"])),
    )
    engine = _make_default_engine(retriever=cast(Any, retriever))

    result = await engine.retrieve(
        MemoryEngineRetrieveRequest(
            query="我默认用什么测试框架？",
            scope=MemoryScope(session_key="s", channel="telegram", chat_id="1"),
            hints={"require_scope_match": True},
            top_k=8,
        )
    )

    assert result.text_block == "baseline memory block"
    assert "safe_version_governed_metadata" not in result.raw
    assert "safe_version_governed_shadow" not in result.raw
    assert "safe_version_governed_mode" not in result.trace


@pytest.mark.asyncio
async def test_default_memory_engine_replace_contract_failure_is_not_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    items = [
        {
            "id": "m-current",
            "summary": "用户偏好使用 pytest。",
            "score": 0.91,
            "source_ref": "telegram:1:1",
            "memory_type": "preference",
            "status": "active",
            "extra_json": {},
        }
    ]
    retriever = SimpleNamespace(
        retrieve_with_lanes=AsyncMock(return_value=(items, items, [])),
        build_injection_block=MagicMock(return_value=("baseline memory block", ["m-current"])),
    )
    engine = _make_default_engine(retriever=cast(Any, retriever))

    def _raise_contract_error(**kwargs: object) -> object:
        raise RuntimeError("contract failed")

    monkeypatch.setattr(
        "plugins.default_memory.engine.build_system_path_safe_version_contract",
        _raise_contract_error,
    )

    result = await engine.retrieve(
        MemoryEngineRetrieveRequest(
            query="我默认用什么测试框架？",
            scope=MemoryScope(session_key="s", channel="telegram", chat_id="1"),
            hints={
                "safe_version_governed_mode": "replace",
                "safe_version_governed_replace_allowed": True,
            },
            top_k=8,
        )
    )

    assert result.text_block == "baseline memory block"
    metadata = result.raw["safe_version_governed_metadata"]
    assert metadata["mode"] == "replace"
    assert metadata["contract_generation_success"] is False
    assert metadata["replacement_requested"] is True
    assert metadata["replace_applied"] is False
```

Use the existing `_make_default_engine` helper already present in `tests/test_memory_engine_contract.py`; do not introduce `_build_engine` or `_upsert_memory_item`.

- [ ] **Step 2: Run RED tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_engine_contract.py::test_default_memory_engine_safe_version_shadow_keeps_text_block \
  tests/test_memory_engine_contract.py::test_default_memory_engine_safe_version_replace_uses_contract_text \
  tests/test_memory_engine_contract.py::test_default_memory_engine_safe_version_replace_requires_allow_gate \
  tests/test_memory_engine_contract.py::test_default_memory_engine_off_adds_no_safe_version_metadata \
  tests/test_memory_engine_contract.py::test_default_memory_engine_replace_contract_failure_is_not_success \
  -q -p no:cacheprovider
```

Expected: fails because engine has not attached safe version-governed metadata yet.

- [ ] **Step 3: Integrate safe contract in engine retrieve**

Modify `plugins/default_memory/engine.py` in `DefaultMemoryEngine.retrieve()` after `text_block, injected_ids = self._retriever.build_injection_block(items)`:

```python
safe_mode = _safe_version_governed_mode(
    request.hints.get("safe_version_governed_mode")
)
replace_allowed = bool(request.hints.get("safe_version_governed_replace_allowed", False))
if safe_mode == "replace" and not replace_allowed:
    safe_mode = "shadow"
safe_shadow = None
safe_metadata: dict[str, object] | None = None
if safe_mode in {"shadow", "replace"}:
    try:
        safe_result = build_system_path_safe_version_contract(
            query=request.query,
            baseline_items=items,
            route_trace=route_trace,
            replacements=(
                self._v2_store.list_replacements()
                if self._v2_store is not None
                else []
            ),
            top_k=request.top_k or len(items) or 8,
        )
        safe_shadow = system_path_contract_to_dict(safe_result.contract)
        safe_metadata = {
            "mode": safe_mode,
            "contract_generation_success": True,
            "allowed_evidence_count": len(safe_result.contract.allowed_evidence_ids),
            "deleted_evidence_count": len(safe_result.contract.deleted_evidence_ids),
            "downgrade_count": len(safe_result.contract.downgrade_ids),
            "requires_review_count": len(safe_result.contract.requires_review_ids),
            "forbidden_boundary_count": len(safe_result.contract.forbidden_boundary_ids),
            "replacement_requested": safe_mode == "replace",
            "replace_allowed": replace_allowed,
            "replace_applied": safe_mode == "replace",
        }
        if safe_mode == "replace":
            text_block = safe_result.text_block
            injected_ids = list(safe_result.contract.allowed_evidence_ids)
    except Exception as exc:
        logger.debug("safe version governed system-path shadow failed", exc_info=True)
        safe_metadata = {
            "mode": safe_mode,
            "contract_generation_success": False,
            "error_type": type(exc).__name__,
            "replacement_requested": safe_mode == "replace",
            "replace_allowed": replace_allowed,
            "replace_applied": False,
        }
```

Add imports:

```python
from memory2.system_path_safe_version_contract import (
    build_system_path_safe_version_contract,
    system_path_contract_to_dict,
)
```

Add helper near other private helpers:

```python
def _safe_version_governed_mode(value: object) -> str:
    mode = str(value or "off")
    if mode not in {"off", "shadow", "replace"}:
        return "off"
    return mode
```

Attach to result:

```python
raw={
    "items": items,
    "route_trace": route_trace,
    **(
        {
            "safe_version_governed_shadow": safe_shadow,
            "safe_version_governed_metadata": safe_metadata,
        }
        if safe_metadata is not None
        else {}
    ),
}
```

Add trace fields:

```python
**(
    {
        "safe_version_governed_mode": safe_mode,
        "safe_version_governed_contract_generation_success": bool(
            safe_metadata.get("contract_generation_success", False)
        ),
        "safe_version_governed_replace_applied": bool(
            safe_metadata.get("replace_applied", False)
        ),
    }
    if safe_metadata is not None
    else {}
),
```

- [ ] **Step 4: Run GREEN tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_engine_contract.py::test_default_memory_engine_safe_version_shadow_keeps_text_block \
  tests/test_memory_engine_contract.py::test_default_memory_engine_safe_version_replace_uses_contract_text \
  tests/test_memory_engine_contract.py::test_default_memory_engine_safe_version_replace_requires_allow_gate \
  tests/test_memory_engine_contract.py::test_default_memory_engine_off_adds_no_safe_version_metadata \
  tests/test_memory_engine_contract.py::test_default_memory_engine_replace_contract_failure_is_not_success \
  -q -p no:cacheprovider
```

Expected:

```text
5 passed
```

- [ ] **Step 5: Regression check default behavior**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_engine_contract.py::test_default_memory_engine_retrieve_maps_hits_and_text_block \
  tests/test_turn_pipelines.py::test_process_direct_suppresses_stream_and_memory_when_requested \
  -q -p no:cacheprovider
```

Expected: selected default behavior tests pass.

- [ ] **Step 6: Commit Task 3**

Run:

```bash
git add plugins/default_memory/engine.py tests/test_memory_engine_contract.py
git commit -m "feat: attach safe version governed memory shadow to engine"
```

---

## Task 4: System-Path AgentLoop Eval Helpers, Post-Check Shadow, And CLI

**Files:**
- Create: `memory2/eval_system_path_safe_version.py`
- Create: `scripts/run_memory_system_path_safe_version_eval.py`
- Create: `tests/test_memory_system_path_safe_version_eval.py`

**Interfaces:**
- Consumes:
  - `AgentLoop`
  - `DefaultMemoryEngine`
  - `MemoryStore2`
  - `build_quantitative_eval_cases`
  - `safe_version_governed_mode`
- Produces:
  - `SystemPathSafeVersionReport`
  - `run_system_path_safe_version_cases(...)`
  - `build_answer_post_check_shadow(...)` telemetry records for shadow/replace modes
  - JSON/Markdown report writers
  - CLI output files.

- [ ] **Step 1: Write failing eval helper tests**

Create `tests/test_memory_system_path_safe_version_eval.py`:

```python
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from memory2.eval_quantitative_cases import build_quantitative_eval_cases


def _walk_report_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        keys = {str(key) for key in value}
        for child in value.values():
            keys.update(_walk_report_keys(child))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for child in value:
            keys.update(_walk_report_keys(child))
        return keys
    return set()


def _raw_fixture_strings(cases: list[object]) -> list[str]:
    values: list[str] = []
    for case in cases:
        setup = getattr(case, "setup")
        query = str(setup.get("query") or "").strip()
        if query:
            values.append(query)
        for item in setup.get("memory_items", []):
            if isinstance(item, dict):
                summary = str(item.get("summary") or "").strip()
                if summary:
                    values.append(summary)
        for replacement in setup.get("memory_replacements", []):
            if isinstance(replacement, dict):
                for key in ("old_summary", "new_summary"):
                    summary = str(replacement.get(key) or "").strip()
                    if summary:
                        values.append(summary)
    return values


def _assert_report_is_private(payload: dict[str, object], markdown: str) -> None:
    forbidden_keys = {
        "raw_prompt",
        "prompt",
        "full_answer",
        "raw_answer",
        "session_text",
        "memory_summary",
        "raw_memory_summary",
    }
    assert not (forbidden_keys & _walk_report_keys(payload))
    selected_cases = (
        build_quantitative_eval_cases("common", case_pack="standard", limit=2)
        + build_quantitative_eval_cases("hard", case_pack="standard", limit=2)
    )
    report_text = json.dumps(payload, ensure_ascii=False) + "\n" + markdown
    for raw_value in _raw_fixture_strings(selected_cases):
        assert raw_value not in report_text
    assert "根据 system path safe version governed contract，应只使用 allowed_evidence 回答。" not in report_text
    assert "根据系统路径注入记忆回答。" not in report_text
    assert "没有可用记忆，无法确认。" not in report_text


def test_system_path_safe_version_cli_fake_provider_writes_sanitized_report(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "reports"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_system_path_safe_version_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(out_dir),
            "--fake-provider",
            "--case-pack",
            "standard",
            "--balanced-small",
            "--common-limit",
            "2",
            "--hard-limit",
            "2",
            "--modes",
            "current,safe_version_shadow,safe_version_replace",
            "--real-memory-workspace",
            str(tmp_path / "empty-real-workspace"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads((out_dir / "system_path_safe_version_eval.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "system_path_safe_version_eval.md").read_text(encoding="utf-8")
    assert payload["metrics"]["evaluation_level"] == "system_path_safe_version_governed"
    assert payload["metrics"]["unique_case_count"] == 4
    assert payload["metrics"]["mode_count"] == 3
    assert payload["metrics"]["case_count"] == 12
    assert payload["metrics"]["fake_provider_enabled"] is True
    assert payload["metrics"]["raw_query_included"] is False
    assert payload["metrics"]["raw_memory_summary_included"] is False
    assert payload["metrics"]["prompt_included"] is False
    assert payload["metrics"]["full_answer_included"] is False
    assert "safe_version_replace" in payload["metrics"]["mode_summaries"]
    assert payload["metrics"]["mode_summaries"]["safe_version_shadow"]["contract_generation_success_rate"] == 100.0
    assert payload["metrics"]["mode_summaries"]["safe_version_shadow"]["post_check_shadow_enabled_rate"] == 100.0
    assert payload["metrics"]["mode_summaries"]["safe_version_replace"]["post_check_shadow_enabled_rate"] == 100.0
    assert payload["metrics"]["mode_summaries"]["current"]["post_check_shadow_enabled_rate"] == 0.0
    assert all("post_check_shadow" in row for row in payload["cases"])
    assert payload["metrics"]["replacement_seeded_count"] > 0
    version_rows = [
        row
        for row in payload["cases"]
        if row["mode"] in {"safe_version_shadow", "safe_version_replace"}
        and row.get("replacement_seeded_count", 0) > 0
    ]
    assert version_rows
    assert all(
        row["safe_version_contract"]["version_boundary"]["replacement_count"] > 0
        for row in version_rows
    )
    _assert_report_is_private(payload, markdown)
```

- [ ] **Step 2: Run RED test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_system_path_safe_version_eval.py \
  -q -p no:cacheprovider
```

Expected: fails because the CLI does not exist yet.

- [ ] **Step 3: Implement eval helper**

Create `memory2/eval_system_path_safe_version.py` with:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence
from unittest.mock import MagicMock

from agent.looping.core import AgentLoop
from agent.looping.ports import AgentLoopConfig, AgentLoopDeps, LLMConfig, MemoryConfig, MemoryServices
from agent.provider import LLMResponse
from agent.tools.registry import ToolRegistry
from bus.event_bus import EventBus
from memory2.eval_answer_post_check import (
    answer_post_check_shadow_to_dict,
    build_answer_post_check_shadow,
)
from memory2.eval_quantitative_cases import EvalCase
from memory2.store import MemoryStore2
from memory2.retriever import Retriever
from plugins.default_memory.engine import DefaultMemoryEngine
from session.manager import SessionManager
```

Required public functions and signatures:

```python
async def run_system_path_safe_version_cases(
    cases: Sequence[EvalCase],
    workspace: Path,
    provider: object,
    *,
    modes: Sequence[str],
    model: str = "scripted",
    timeout_s: float = 30.0,
) -> SystemPathSafeVersionReport

def write_system_path_safe_version_json(
    report: SystemPathSafeVersionReport,
    path: Path,
) -> None

def write_system_path_safe_version_markdown(
    report: SystemPathSafeVersionReport,
    path: Path,
) -> None
```

Mode mapping:

```python
MODE_TO_SAFE_VERSION = {
    "current": "off",
    "safe_version_shadow": "shadow",
    "safe_version_replace": "replace",
}
```

The helper must:

- seed each `EvalCase.setup["memory_items"]` into a temporary `MemoryStore2`, preserving fixture `id`, `status`, `memory_type`, `source_ref`, `scope_channel`, `scope_chat_id`, and `extra_json`;
- seed each `EvalCase.setup["memory_replacements"]` into the same store's real `memory_replacements` table, preserving `old_item_id`, `new_item_id`, memory types, summaries, and source refs so `DefaultMemoryEngine.retrieve()` can read them through `self._v2_store.list_replacements()`;
- construct `DefaultMemoryEngine` with the same dependencies used by existing eval dry-run helpers in `memory2/eval_agent_dry_run.py`; do not use eval-only `ComprehensiveOnlineMemoryEngine`;
- wrap `DefaultMemoryEngine.retrieve()` with a small recording subclass or proxy that stores the latest `MemoryEngineRetrieveResult` per case/mode while still executing the real engine retrieval path;
- run real `AgentLoop.process_direct(...)`;
- set `AgentLoopConfig(memory=MemoryConfig(safe_version_governed_mode=MODE_TO_SAFE_VERSION[mode], safe_version_governed_replace_allowed=(mode == "safe_version_replace")))`;
- call provider through `AgentLoop`, not directly;
- collect answer pass, grounding pass, forbidden violation, token counts, contract generation metadata, replacement seeded counts, and sanitized case records;
- include `safe_version_contract` in each shadow/replace case row as the sanitized `system_path_contract_to_dict(...)` payload; it may include IDs and numeric `version_boundary`, but must not include allowed evidence summaries or raw prompt text;
- include top-level metrics `replacement_seeded_count`, `version_boundary_case_count`, and per-mode `contract_generation_success_rate`;
- assert during report generation that any case with seeded replacements and mode in `safe_version_shadow|safe_version_replace` has `safe_version_contract["version_boundary"]["replacement_count"] > 0`;
- call `build_answer_post_check_shadow(answer, answer_contract, context_memory_ids)` after `AgentLoop.process_direct(...)` for `safe_version_shadow` and `safe_version_replace`, where:
  - `answer` is the returned assistant text;
  - `answer_contract` is `latest_retrieve_result.raw["safe_version_governed_shadow"]` plus `production_safe_evidence_contract=True`;
  - `context_memory_ids` are `hit.id` values from `latest_retrieve_result.hits` in shadow mode, and `allowed_evidence_ids` when replace mode applied;
- include only `answer_post_check_shadow_to_dict(...)` output in reports; do not include `AnswerPostCheckShadow.raw_prompt` or `raw_answer`;
- score answer/grounding/forbidden using fixture expectations only in the evaluator, not in system-path runtime code.

- [ ] **Step 4: Implement CLI**

Create `scripts/run_memory_system_path_safe_version_eval.py`:

```python
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.config import load_config
import agent.provider as agent_provider
from agent.provider import LLMResponse
from memory2.eval_quantitative_cases import build_quantitative_eval_cases
from memory2.eval_system_path_safe_version import (
    run_system_path_safe_version_cases,
    write_system_path_safe_version_json,
    write_system_path_safe_version_markdown,
)


class ScriptedSystemPathProvider:
    async def chat(self, **kwargs: Any) -> LLMResponse:
        text = "\n".join(
            str(message.get("content") or "")
            for message in kwargs.get("messages", [])
            if isinstance(message, dict)
        )
        if "Evidence Contract: system_memory_safe_version_governed" in text:
            answer = "根据 system path safe version governed contract，应只使用 allowed_evidence 回答。"
        elif "memory_id=" in text:
            answer = "根据系统路径注入记忆回答。"
        else:
            answer = "没有可用记忆，无法确认。"
        return LLMResponse(
            content=answer,
            tool_calls=[],
            provider_fields={"usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}},
        )
```

CLI args:

```python
--workspace
--out-dir
--config
--case-pack standard|comprehensive
--balanced-small
--common-limit
--hard-limit
--limit
--modes
--fake-provider
--enable-real-llm
--timeout-s
--real-memory-workspace
```

Output files:

```text
system_path_safe_version_eval.json
system_path_safe_version_eval.md
```

- [ ] **Step 5: Run GREEN CLI test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_system_path_safe_version_eval.py \
  -q -p no:cacheprovider
```

Expected:

```text
1 passed
```

- [ ] **Step 6: Commit Task 4**

Run:

```bash
git add memory2/eval_system_path_safe_version.py scripts/run_memory_system_path_safe_version_eval.py tests/test_memory_system_path_safe_version_eval.py
git commit -m "feat: add system path safe version eval runner"
```

---

## Task 5: Fake System-Path Report And Docs

**Files:**
- Create:
  - `my_md/memory_optimization/eval_reports/p6o13_system_path_safe_version_governed_v1/system_path_safe_version_eval.json`
  - `my_md/memory_optimization/eval_reports/p6o13_system_path_safe_version_governed_v1/system_path_safe_version_eval.md`
- Modify:
  - `my_md/memory_optimization/README.md`
  - `progress.md`

**Interfaces:**
- Consumes:
  - `scripts/run_memory_system_path_safe_version_eval.py`
- Produces:
  - committed fake/system-path smoke report;
  - documented P6o-13 status and next real LLM gate.

- [ ] **Step 1: Run fake-provider system-path smoke**

Run:

```bash
rm -rf /tmp/akashic-memory-p6o13-system-path-safe-version-fake
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace /tmp/akashic-memory-p6o13-system-path-safe-version-fake/workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o13_system_path_safe_version_governed_v1 \
  --fake-provider \
  --case-pack standard \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --modes current,safe_version_shadow,safe_version_replace \
  --real-memory-workspace /tmp/akashic-memory-p6o13-system-path-safe-version-fake/empty-real-workspace
```

Expected:

```text
my_md/memory_optimization/eval_reports/p6o13_system_path_safe_version_governed_v1/system_path_safe_version_eval.json
my_md/memory_optimization/eval_reports/p6o13_system_path_safe_version_governed_v1/system_path_safe_version_eval.md
```

- [ ] **Step 2: Validate fake report gates**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path
from memory2.eval_quantitative_cases import build_quantitative_eval_cases

def walk_keys(value):
    if isinstance(value, dict):
        keys = {str(key) for key in value}
        for child in value.values():
            keys.update(walk_keys(child))
        return keys
    if isinstance(value, list):
        keys = set()
        for child in value:
            keys.update(walk_keys(child))
        return keys
    return set()

def raw_fixture_strings(cases):
    values = []
    for case in cases:
        query = str(case.setup.get("query") or "").strip()
        if query:
            values.append(query)
        for item in case.setup.get("memory_items", []):
            if isinstance(item, dict):
                summary = str(item.get("summary") or "").strip()
                if summary:
                    values.append(summary)
        for replacement in case.setup.get("memory_replacements", []):
            if isinstance(replacement, dict):
                for key in ("old_summary", "new_summary"):
                    summary = str(replacement.get(key) or "").strip()
                    if summary:
                        values.append(summary)
    return values

path = Path("my_md/memory_optimization/eval_reports/p6o13_system_path_safe_version_governed_v1/system_path_safe_version_eval.json")
payload = json.loads(path.read_text(encoding="utf-8"))
markdown = path.with_suffix(".md").read_text(encoding="utf-8")
m = payload["metrics"]
assert m["evaluation_level"] == "system_path_safe_version_governed"
assert m["fake_provider_enabled"] is True
assert m["unique_case_count"] == 40
assert m["mode_count"] == 3
assert m["case_count"] == 120
assert m["provider_error_count"] == 0
assert m["timeout_count"] == 0
assert m["raw_query_included"] is False
assert m["raw_memory_summary_included"] is False
assert m["prompt_included"] is False
assert m["session_text_included"] is False
assert m["full_answer_included"] is False
assert m["mode_summaries"]["safe_version_shadow"]["contract_generation_success_rate"] == 100.0
assert m["mode_summaries"]["safe_version_replace"]["contract_generation_success_rate"] == 100.0
assert m["mode_summaries"]["safe_version_shadow"]["post_check_shadow_enabled_rate"] == 100.0
assert m["mode_summaries"]["safe_version_replace"]["post_check_shadow_enabled_rate"] == 100.0
assert m["replacement_seeded_count"] > 0
version_rows = [
    row for row in payload.get("cases", [])
    if row.get("mode") in {"safe_version_shadow", "safe_version_replace"}
    and row.get("replacement_seeded_count", 0) > 0
]
assert version_rows
for row in version_rows:
    assert row["safe_version_contract"]["version_boundary"]["replacement_count"] > 0
forbidden_keys = {
    "raw_prompt",
    "prompt",
    "full_answer",
    "raw_answer",
    "session_text",
    "memory_summary",
    "raw_memory_summary",
}
blocked = forbidden_keys & walk_keys(payload)
assert not blocked, f"forbidden report keys: {sorted(blocked)}"
selected_cases = (
    build_quantitative_eval_cases("common", case_pack="standard", limit=20)
    + build_quantitative_eval_cases("hard", case_pack="standard", limit=20)
)
report_text = json.dumps(payload, ensure_ascii=False) + "\n" + markdown
for raw_value in raw_fixture_strings(selected_cases):
    assert raw_value not in report_text
for answer in (
    "根据 system path safe version governed contract，应只使用 allowed_evidence 回答。",
    "根据系统路径注入记忆回答。",
    "没有可用记忆，无法确认。",
):
    assert answer not in report_text
print("p6o13 fake gate ok")
PY
```

Expected:

```text
p6o13 fake gate ok
```

- [ ] **Step 3: Update README and progress**

Add README bullet after P6o-12 production candidate handoff:

```text
Phase 6o13-system-path-safe-version-governed
```

Include:

- system path integration status;
- default mode remains `off`;
- modes tested: `current`, `safe_version_shadow`, `safe_version_replace`;
- fake-provider smoke size and gate results;
- post-check shadow telemetry is recorded only for shadow/replace and does not retry or alter production answers;
- no graph/all-on;
- no production write/retry/fallback changes;
- next gate is real LLM system-path A/B only after smoke passes.

Append progress section:

```markdown
## 2026-07-29 P6o-13 system path safe version governed
```

Include changed files, smoke report path, fake gate metrics, and next step.

- [ ] **Step 4: Privacy grep**

Run:

```bash
if rg -n "raw_prompt|full_answer|session_text|api[_-]?key|Authorization" \
  my_md/memory_optimization/eval_reports/p6o13_system_path_safe_version_governed_v1/*.md \
  my_md/memory_optimization/README.md; then
  exit 1
else
  echo "privacy grep ok"
fi
```

Expected:

```text
privacy grep ok
```

- [ ] **Step 5: Commit Task 5**

Run:

```bash
git add \
  my_md/memory_optimization/README.md \
  progress.md \
  my_md/memory_optimization/eval_reports/p6o13_system_path_safe_version_governed_v1/system_path_safe_version_eval.json \
  my_md/memory_optimization/eval_reports/p6o13_system_path_safe_version_governed_v1/system_path_safe_version_eval.md
git commit -m "docs: record p6o13 system path safe version smoke"
```

---

## Task 6: Verification

**Files:**
- Verify all changed files.

**Interfaces:**
- Consumes: all P6o-13 implementation commits.
- Produces: final verification evidence.

- [ ] **Step 1: Run focused test suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_system_path_safe_version_contract.py \
  tests/test_memory_system_path_safe_version_eval.py \
  tests/test_memory_engine_contract.py::test_default_memory_engine_safe_version_shadow_keeps_text_block \
  tests/test_memory_engine_contract.py::test_default_memory_engine_safe_version_replace_uses_contract_text \
  tests/test_memory_engine_contract.py::test_default_memory_engine_safe_version_replace_requires_allow_gate \
  tests/test_memory_engine_contract.py::test_default_memory_engine_off_adds_no_safe_version_metadata \
  tests/test_memory_engine_contract.py::test_default_memory_engine_replace_contract_failure_is_not_success \
  tests/test_turn_pipelines.py::test_retrieval_pipeline_defaults_safe_version_mode_off \
  tests/test_turn_pipelines.py::test_retrieval_pipeline_passes_safe_version_mode_from_config \
  tests/test_turn_pipelines.py::test_retrieval_pipeline_allows_session_metadata_shadow_override_for_tests \
  tests/test_turn_pipelines.py::test_retrieval_pipeline_rejects_session_metadata_replace_without_allow_gate \
  tests/test_turn_pipelines.py::test_retrieval_pipeline_rejects_session_metadata_replace_even_when_allow_flag_true \
  tests/test_turn_pipelines.py::test_retrieval_pipeline_allows_replace_only_from_config_gate \
  tests/test_turn_pipelines.py::test_agent_loop_passes_safe_version_config_to_default_retrieval_pipeline \
  -q -p no:cacheprovider
```

Expected: all selected tests pass.

- [ ] **Step 2: Run default regression slice**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_turn_pipelines.py \
  tests/test_memory_comprehensive_online_cli.py::test_comprehensive_online_cli_p6o8_safe_boundary_fake_provider_matrix_shape \
  tests/test_memory_comprehensive_online_cli.py::test_comprehensive_online_cli_p6o7_version_governed_fake_provider_matrix_shape \
  -q -p no:cacheprovider
```

Expected: all selected tests pass.

- [ ] **Step 3: Check diff hygiene and status**

Run:

```bash
git diff --check
git status --short
```

Expected:

- `git diff --check` has no output.
- `git status --short` may still show the pre-existing untracked intent directory:

```text
?? my_md/memory_optimization/eval_reports/p6o13_system_path_real_llm_validation_v1/
```

Do not stage that pre-existing directory unless the user explicitly asks.

---

## Follow-Up Gate After This Plan

If P6o-13 fake/system-path smoke passes, the next plan should be:

```text
P6o-14 system-path safe version-governed real LLM A/B
```

Suggested real LLM matrix:

- common `20` + hard `20`;
- prompt `baseline`;
- repeat `1`;
- modes:
  - `current`;
  - `safe_version_replace`;
  - optional `safe_version_shadow` for telemetry-only parity;
- success gate:
  - infra clean;
  - answer not below current;
  - grounding not below current;
  - forbidden not above current;
  - contract generation success `100.0%`;
  - reports sanitized.
