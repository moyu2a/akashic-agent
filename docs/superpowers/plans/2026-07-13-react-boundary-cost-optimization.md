# Bounded ReAct Batch Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce Document RAG ReAct cost for fixed-path document questions by combining proactive final-only completion with same-batch tool-call boundary handling.

**Architecture:** Keep evidence sufficiency in `EvidenceContractManager`, final-only decisions in `TurnCompletionController`, and access control in `ToolAccessGateway`. Add a focused `ReactBoundaryManager` that provides cost/profile decisions only: same-batch skip decisions, next-call final-only recommendation metadata, and traceable suppression recommendations. Integrate only in `DefaultReasoner.run_turn()` / `DefaultReasoner.run()` around the existing tool-call execution loop; do not touch `AgentLoop`.

**Tech Stack:** Python dataclasses, existing `ToolCallLedger`, `EvidenceAssessment`, `TurnCompletionDecision`, `ToolAccessPlan`, pytest fake providers/tools.

## Global Constraints

- Do not modify always-on tool registration.
- Do not write React boundary state into `ToolDiscoveryState` / LRU.
- Do not remove or bypass `ToolAccessGateway`, `TurnToolBoundaryManager`, `TurnCompletionController`, or `EvidenceContractManager`.
- Do not make `ReactBoundaryManager` define evidence sufficiency; `EvidenceContractManager.assess()` is the only source for `tool_stop_allowed` / `answer_ready`.
- Keep `AgentLoop` out of scope; integration belongs in `DefaultReasoner`.
- Preserve current soft-stop behavior as fallback when the batch boundary does not apply.
- For explicit local source/code/file intent, do not force Document RAG final-only.
- Same-batch skipped tool calls must still receive a tool result message, because provider protocols require one tool result per assistant tool call.
- Use TDD: every behavioral change starts with a failing test and a confirmed RED result.
- Avoid unrelated refactors and unrelated documentation changes.
- Current worktree may contain unrelated edits; stage only files touched by each task.

---

## File Structure

- Create `agent/policies/react_boundary.py`
  - Owns Document RAG bounded-ReAct cost profile.
  - Does not execute tools.
  - Does not mutate LRU, `ToolDiscoveryState`, or `ToolAccessPlan`.
  - Produces:
    - `ReactBoundaryDecision` for next-call final-only metadata.
    - `BatchToolDecision` for same-assistant-response tool-call handling.
- Modify `agent/policies/tool_access.py`
  - Add stable `ToolAccessPlan.local_source_allowed: bool = False`.
  - Set it in the explicit local/source/file allowance path.
- Modify `agent/policies/turn_completion.py`
  - Let `TurnCompletionController.evaluate()` optionally consume `EvidenceAssessment`.
  - Preserve the existing soft-stop signal path as fallback.
- Modify `agent/core/passive_turn.py`
  - Instantiate `ReactBoundaryManager`.
  - Evaluate batch skip before full tool-boundary execution for each tool call.
  - Evaluate proactive final-only after successful real tool results are recorded and evidence is assessed.
  - Append legal lightweight tool results for batch-skipped calls.
- Create `tests/test_react_boundary.py`
  - Unit tests for batch and next-call policy decisions.
- Modify `tests/test_turn_completion_reasoner.py`
  - Add failing reasoner tests for same-batch multi fetch, proactive final-only, evidence-contract hint propagation, and local-source exemption.
- Modify governance/RAG docs after implementation:
  - `my_md/governance/02-current-issues.md`
  - `my_md/governance/04-fix-roadmap.md`
  - `my_md/governance/06-star-log.md`
  - `my_md/rag/22-document-rag-p10a3-turn-completion-plan.md`

---

## Target Behavior

### Simple Document Question

Prompt shape:

```text
请从文档知识库中检索agent runtime负责什么？回答必须带文档引用
```

Expected happy path:

```text
LLM -> search_docs -> LLM final-only
```

Acceptance:

- real tools used: `["search_docs"]`
- final provider call uses `tools=[]`
- no `fetch_doc_chunk`
- no `shell/read_file/list_dir`
- no state written to LRU except normal successful tool usage behavior already present before this plan

### Document Question With Original Evidence

Prompt shape:

```text
根据项目文档回答agent runtime负责什么，并展开原文证据
```

Expected happy path:

```text
LLM -> search_docs -> LLM -> fetch_doc_chunk -> LLM final-only
```

Acceptance:

- real tools used: `["search_docs", "fetch_doc_chunk"]`
- final provider call uses `tools=[]`
- final-only call includes `turn_completion` and `evidence_contract` hints
- no `shell/read_file/list_dir`

### Same-Batch Multi Fetch

Problem shape seen in real turns `365/366`:

```text
LLM -> [
  fetch_doc_chunk(c1),
  fetch_doc_chunk(c2),
  fetch_doc_chunk(c3)
]
```

Expected behavior:

- first budget-valid `fetch_doc_chunk` executes normally
- later same-batch Document RAG fetch calls receive lightweight legal tool results
- skipped calls use status `batch_skipped_by_react_boundary`
- skipped calls do not count as successful `tools_used`
- skipped calls do not add success records to `ToolCallLedger`
- skipped calls are visible in `tool_chain` / observe as skipped, not as normal `tool_boundary_soft_stop`
- next provider call is final-only with `tools=[]`

Payload for skipped tool result:

```json
{
  "ok": false,
  "error_code": "react_boundary_batch_skip",
  "terminal_scope": "document_rag",
  "message": "This Document RAG tool call was skipped because enough evidence was already collected in this assistant tool-call batch. Answer from the successful search_docs/fetch_doc_chunk evidence already available.",
  "action": "answer_from_existing_evidence"
}
```

---

## Interfaces

### `ToolAccessPlan.local_source_allowed`

Add a stable boolean to avoid fragile reason-string checks.

```python
@dataclass(frozen=True)
class ToolAccessPlan:
    visible_add: frozenset[str] = frozenset()
    visible_suppress: frozenset[str] = frozenset()
    tool_search_block: frozenset[str] = frozenset()
    execution_block: frozenset[str] = frozenset()
    reason: str = ""
    matched_terms: tuple[str, ...] = ()
    policies: tuple[str, ...] = ()
    filter_error: bool = False
    local_source_allowed: bool = False
```

Set `local_source_allowed=True` only for explicit local/source/file/code intent paths that currently produce `doc_rag_allows_explicit_local_files` or equivalent behavior. Keep `reason` for logs only.

### `TurnCompletionController.evaluate(...)`

Extend signature:

```python
def evaluate(
    self,
    *,
    intent: TaskIntent,
    ledger: ToolCallLedger,
    boundary_decisions: Sequence[Mapping[str, object]],
    evidence_assessment: EvidenceAssessment | None = None,
    local_source_allowed: bool = False,
    proactive_allowed: bool = False,
) -> TurnCompletionDecision:
    ...
```

Rules:

- If `local_source_allowed`, return `continue_react`.
- If `intent == "doc_qa_simple"` and `evidence_assessment.sufficiency.tool_stop_allowed`, return `final_only` with reason `document_rag_retrieval_complete`.
- If `intent == "doc_qa_with_evidence"` and `evidence_assessment.sufficiency.tool_stop_allowed`, return `final_only` with reason `document_rag_evidence_complete`.
- If no `evidence_assessment`, preserve current behavior: require existing soft-stop signal before final-only.
- `proactive_allowed` controls whether evidence sufficiency alone can trigger final-only. Existing soft-stop fallback should still work with `proactive_allowed=False`.

### `ReactBoundaryManager`

Create `agent/policies/react_boundary.py`.

It must not inspect raw tool result JSON to decide evidence sufficiency. It receives `EvidenceAssessment` and uses only `assessment.sufficiency.tool_stop_allowed`.

```python
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from agent.policies.evidence_contract import EvidenceAssessment
from agent.policies.tool_budget import TaskIntent
from agent.policies.tool_ledger import ToolCallLedger

DOC_RAG_RUNTIME_TOOLS = frozenset({"search_docs", "fetch_doc_chunk"})

BatchToolAction = Literal["execute", "skip"]


@dataclass(frozen=True)
class BatchToolDecision:
    action: BatchToolAction
    reason: str
    status: str = ""
    result_payload: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ReactBoundaryDecision:
    recommend_final_only: bool
    reason: str
    model_hint: str = ""
    recommended_suppress: frozenset[str] = frozenset()
    metadata: Mapping[str, object] = field(default_factory=dict)


class ReactBoundaryManager:
    def evaluate_after_tool_result(
        self,
        *,
        intent: TaskIntent,
        ledger: ToolCallLedger,
        evidence_assessment: EvidenceAssessment | None,
        local_source_allowed: bool = False,
    ) -> ReactBoundaryDecision:
        ...

    def evaluate_batch_tool_call(
        self,
        *,
        intent: TaskIntent,
        tool_name: str,
        tool_batch_index: int,
        ledger: ToolCallLedger,
        evidence_assessment: EvidenceAssessment | None,
        local_source_allowed: bool = False,
    ) -> BatchToolDecision:
        ...
```

Batch skip rules:

- If `local_source_allowed`, return `execute`.
- If `tool_name` is not in `DOC_RAG_RUNTIME_TOOLS`, return `execute`.
- If `tool_batch_index == 0`, return `execute`.
- If `evidence_assessment is None`, return `execute`.
- If `evidence_assessment.sufficiency.tool_stop_allowed is False`, return `execute`.
- If `intent == "doc_qa_with_evidence"` and `tool_name == "fetch_doc_chunk"` and at least one successful `fetch_doc_chunk` has already been recorded in the ledger, return `skip`.
- If `intent == "doc_qa_simple"` and `tool_name in DOC_RAG_RUNTIME_TOOLS` and a successful `search_docs` result with citation evidence exists, return `skip`.

Next-call recommendation rules:

- If `local_source_allowed`, return `recommend_final_only=False`.
- If `evidence_assessment is None`, return `recommend_final_only=False`.
- If `evidence_assessment.sufficiency.tool_stop_allowed is False`, return `recommend_final_only=False`.
- If `intent == "doc_qa_simple"`, return `recommend_final_only=True`, reason `document_rag_retrieval_complete`.
- If `intent == "doc_qa_with_evidence"`, return `recommend_final_only=True`, reason `document_rag_evidence_complete`.
- Otherwise return `recommend_final_only=False`.

Only `TurnCompletionController.evaluate()` may produce the final `TurnCompletionDecision`. `ReactBoundaryDecision.recommend_final_only` is a cost/profile recommendation, not a completion decision.

---

### Task 1: Add Stable Local-Source Access Flag

**Files:**
- Modify: `agent/policies/tool_access.py`
- Modify: `tests/test_tool_access_gateway.py`

**Interfaces:**
- Produces: `ToolAccessPlan.local_source_allowed: bool`
- Consumes: existing explicit local/source/file intent detection.

- [ ] **Step 1: Locate current local-source reason path**

Run:

```bash
rg -n "doc_rag_allows_explicit_local_files|ToolAccessPlan|local.*source|read_file|list_dir" agent/policies/tool_access.py tests
```

Expected: shows the existing place where explicit local file/source requests are allowed.

- [ ] **Step 2: Write failing tests for stable flag**

In `tests/test_tool_access_gateway.py`, extend `test_explicit_source_request_allows_local_tools()`:

```python
assert plan.local_source_allowed is True
```

In `test_strong_doc_evidence_prefers_rag_and_blocks_local_tools()`, add:

```python
assert plan.local_source_allowed is False
```

Add a new merge-preservation test:

```python
def test_explicit_source_flag_survives_observe_tool_result_merge() -> None:
    gateway = ToolAccessGateway()
    ctx = _ctx("根据项目文档和源码回答，请读取 agent/core/passive_turn.py")
    plan = gateway.build_plan(ctx)

    updated = gateway.observe_tool_result(
        plan,
        "search_docs",
        json.dumps({"terminal_scope": "document_rag", "fallback_allowed": False}),
    )

    assert plan.local_source_allowed is True
    assert updated.local_source_allowed is True
```

- [ ] **Step 3: Run the focused test to verify RED**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_tool_access_gateway.py::test_explicit_source_request_allows_local_tools \
  tests/test_tool_access_gateway.py::test_strong_doc_evidence_prefers_rag_and_blocks_local_tools \
  tests/test_tool_access_gateway.py::test_explicit_source_flag_survives_observe_tool_result_merge \
  -q
```

Expected: FAIL with `AttributeError` or assertion failure for `local_source_allowed`.

- [ ] **Step 4: Add the field and set it**

In `agent/policies/tool_access.py`, add:

```python
local_source_allowed: bool = False
```

to `ToolAccessPlan`.

In the explicit local/source/file allowance path, set:

```python
local_source_allowed=True
```

In `_merge_plans(...)`, preserve the flag:

```python
local_source_allowed=left.local_source_allowed or right.local_source_allowed,
```

Do not remove or rename the existing `reason`; logs and docs may still use it.

- [ ] **Step 5: Run focused test to verify GREEN**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_tool_access_gateway.py::test_explicit_source_request_allows_local_tools \
  tests/test_tool_access_gateway.py::test_strong_doc_evidence_prefers_rag_and_blocks_local_tools \
  tests/test_tool_access_gateway.py::test_explicit_source_flag_survives_observe_tool_result_merge \
  -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add agent/policies/tool_access.py tests/test_tool_access_gateway.py
git commit -m "feat: expose stable local-source access flag"
```

---

### Task 2: Extend Turn Completion To Consume Evidence Assessment

**Files:**
- Modify: `agent/policies/turn_completion.py`
- Modify: `tests/test_turn_completion_policy.py`

**Interfaces:**
- Consumes: `EvidenceAssessment | None`
- Produces: `TurnCompletionController.evaluate(..., evidence_assessment=..., proactive_allowed=...)`

- [ ] **Step 1: Add failing policy tests**

Append tests to `tests/test_turn_completion_policy.py` using the existing imports/helpers where possible. If the file does not already import evidence classes, add:

```python
from agent.policies.evidence_contract import (
    EvidenceAssessment,
    EvidenceSufficiency,
    TaskEvidenceRequirement,
)
```

Add helper:

```python
def _assessment_ready(task_type: str) -> EvidenceAssessment:
    return EvidenceAssessment(
        requirement=TaskEvidenceRequirement(task_type=task_type),
        items=(),
        sufficiency=EvidenceSufficiency(
            tool_stop_allowed=True,
            answer_ready=True,
            reason="requirements_satisfied",
        ),
        constraints=(),
        model_hint="Evidence contract for this answer:",
    )
```

Add tests:

```python
def test_proactive_simple_doc_completion_uses_evidence_assessment() -> None:
    decision = TurnCompletionController().evaluate(
        intent="doc_qa_simple",
        ledger=ToolCallLedger(),
        boundary_decisions=(),
        evidence_assessment=_assessment_ready("doc_qa_simple"),
        proactive_allowed=True,
    )

    assert decision.action == "final_only"
    assert decision.reason == "document_rag_retrieval_complete"
    assert decision.metadata["proactive"] is True


def test_proactive_doc_evidence_completion_uses_evidence_assessment() -> None:
    decision = TurnCompletionController().evaluate(
        intent="doc_qa_with_evidence",
        ledger=ToolCallLedger(),
        boundary_decisions=(),
        evidence_assessment=_assessment_ready("doc_qa_with_evidence"),
        proactive_allowed=True,
    )

    assert decision.action == "final_only"
    assert decision.reason == "document_rag_evidence_complete"
    assert decision.metadata["proactive"] is True


def test_local_source_allowed_blocks_proactive_completion() -> None:
    decision = TurnCompletionController().evaluate(
        intent="doc_qa_with_evidence",
        ledger=ToolCallLedger(),
        boundary_decisions=(),
        evidence_assessment=_assessment_ready("doc_qa_with_evidence"),
        proactive_allowed=True,
        local_source_allowed=True,
    )

    assert decision.action == "continue_react"
    assert decision.reason == "local_source_allowed"
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_turn_completion_policy.py::test_proactive_simple_doc_completion_uses_evidence_assessment \
  tests/test_turn_completion_policy.py::test_proactive_doc_evidence_completion_uses_evidence_assessment \
  tests/test_turn_completion_policy.py::test_local_source_allowed_blocks_proactive_completion \
  -q
```

Expected: FAIL because `evaluate()` does not accept `evidence_assessment` / `proactive_allowed`.

- [ ] **Step 3: Implement signature and rules**

Modify `TurnCompletionController.evaluate()` in `agent/policies/turn_completion.py`:

```python
    def evaluate(
        self,
        *,
        intent: TaskIntent,
        ledger: ToolCallLedger,
        boundary_decisions: Sequence[Mapping[str, object]],
        evidence_assessment: EvidenceAssessment | None = None,
        local_source_allowed: bool = False,
        proactive_allowed: bool = False,
    ) -> TurnCompletionDecision:
        if local_source_allowed:
            return TurnCompletionDecision(
                action="continue_react",
                reason="local_source_allowed",
                metadata=self._metadata(ledger, boundary_decisions),
            )

        if proactive_allowed and evidence_assessment is not None:
            if evidence_assessment.sufficiency.tool_stop_allowed:
                if intent == "doc_qa_simple":
                    return TurnCompletionDecision(
                        action="final_only",
                        reason="document_rag_retrieval_complete",
                        model_hint=(
                            "Document RAG retrieval is complete for this turn. "
                            "Do not request more tools. Answer from the existing "
                            "search_docs evidence and include available citations."
                        ),
                        metadata={
                            **self._metadata(ledger, boundary_decisions),
                            "proactive": True,
                            "evidence_reason": evidence_assessment.sufficiency.reason,
                        },
                    )
                if intent == "doc_qa_with_evidence":
                    return TurnCompletionDecision(
                        action="final_only",
                        reason="document_rag_evidence_complete",
                        model_hint=(
                            "Document RAG evidence is complete for this turn. "
                            "Do not request more tools. Answer from the existing "
                            "Document RAG evidence and include available citations."
                        ),
                        metadata={
                            **self._metadata(ledger, boundary_decisions),
                            "proactive": True,
                            "evidence_reason": evidence_assessment.sufficiency.reason,
                        },
                    )
```

Keep the existing soft-stop logic below this block. Do not delete it.

- [ ] **Step 4: Run tests to verify GREEN**

Run the same command from Step 2.

Expected: PASS.

- [ ] **Step 5: Run existing turn completion policy tests**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_turn_completion_policy.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add agent/policies/turn_completion.py tests/test_turn_completion_policy.py
git commit -m "feat: allow proactive turn completion from evidence assessment"
```

---

### Task 3: Add React Boundary Policy Unit

**Files:**
- Create: `agent/policies/react_boundary.py`
- Create/Modify: `tests/test_react_boundary.py`

**Interfaces:**
- Consumes:
  - `TaskIntent`
  - `ToolCallLedger`
  - `EvidenceAssessment | None`
- Produces:
  - `ReactBoundaryManager.evaluate_after_tool_result(...) -> ReactBoundaryDecision`
  - `ReactBoundaryManager.evaluate_batch_tool_call(...) -> BatchToolDecision`

- [ ] **Step 1: Write failing unit tests**

Create `tests/test_react_boundary.py`:

```python
from __future__ import annotations

import json

from agent.policies.evidence_contract import (
    EvidenceAssessment,
    EvidenceSufficiency,
    TaskEvidenceRequirement,
)
from agent.policies.react_boundary import ReactBoundaryManager
from agent.policies.tool_ledger import ToolCallLedger, ToolCallRecord


def _record(
    tool_name: str,
    *,
    tool_class: str,
    call_index: int,
    result_ok: bool = True,
    hit_count: int | None = None,
    citation_refs: tuple[str, ...] = (),
    chunk_keys: tuple[str, ...] = (),
) -> ToolCallRecord:
    return ToolCallRecord(
        tool_name=tool_name,
        tool_class=tool_class,  # type: ignore[arg-type]
        args_hash=f"{tool_name}-{call_index}",
        args_summary="{}",
        call_index=call_index,
        visible_before_call=True,
        result_ok=result_ok,
        hit_count=hit_count,
        citation_refs=citation_refs,
        chunk_keys=chunk_keys,
        result_has_evidence=result_ok,
        result_has_citation=bool(citation_refs),
    )


def _assessment_ready(task_type: str = "doc_qa_with_evidence") -> EvidenceAssessment:
    return EvidenceAssessment(
        requirement=TaskEvidenceRequirement(task_type=task_type),
        items=(),
        sufficiency=EvidenceSufficiency(
            tool_stop_allowed=True,
            answer_ready=True,
            reason="requirements_satisfied",
        ),
        constraints=(),
        model_hint="Evidence contract for this answer:",
    )


def _assessment_missing() -> EvidenceAssessment:
    return EvidenceAssessment(
        requirement=TaskEvidenceRequirement(task_type="doc_qa_with_evidence"),
        items=(),
        sufficiency=EvidenceSufficiency(
            tool_stop_allowed=False,
            answer_ready=True,
            reason="missing_evidence",
            missing_requirements=("fetched_text",),
        ),
        constraints=(),
        model_hint="Evidence contract for this answer:",
    )


def test_after_tool_result_recommends_final_only_from_assessment() -> None:
    decision = ReactBoundaryManager().evaluate_after_tool_result(
        intent="doc_qa_with_evidence",
        ledger=ToolCallLedger(),
        evidence_assessment=_assessment_ready(),
        local_source_allowed=False,
    )

    assert decision.recommend_final_only is True
    assert decision.reason == "document_rag_evidence_complete"
    assert decision.recommended_suppress == frozenset({"search_docs", "fetch_doc_chunk"})
    assert decision.metadata["evidence_reason"] == "requirements_satisfied"


def test_after_tool_result_does_not_final_only_for_local_source() -> None:
    decision = ReactBoundaryManager().evaluate_after_tool_result(
        intent="doc_qa_with_evidence",
        ledger=ToolCallLedger(),
        evidence_assessment=_assessment_ready(),
        local_source_allowed=True,
    )

    assert decision.recommend_final_only is False
    assert decision.reason == "local_source_allowed"
    assert decision.recommended_suppress == frozenset()


def test_batch_skip_after_first_successful_fetch_and_ready_evidence() -> None:
    ledger = ToolCallLedger()
    ledger.add_record(
        _record(
            "fetch_doc_chunk",
            tool_class="evidence_expand",
            call_index=1,
            citation_refs=("my_md/doc.md > Agent Runtime",),
            chunk_keys=("c1",),
        )
    )

    decision = ReactBoundaryManager().evaluate_batch_tool_call(
        intent="doc_qa_with_evidence",
        tool_name="fetch_doc_chunk",
        tool_batch_index=1,
        ledger=ledger,
        evidence_assessment=_assessment_ready(),
        local_source_allowed=False,
    )

    assert decision.action == "skip"
    assert decision.reason == "document_rag_batch_evidence_complete"
    assert decision.status == "batch_skipped_by_react_boundary"
    payload = json.loads(decision.result_payload)
    assert payload["error_code"] == "react_boundary_batch_skip"
    assert payload["terminal_scope"] == "document_rag"


def test_batch_does_not_skip_when_evidence_missing() -> None:
    ledger = ToolCallLedger()
    ledger.add_record(
        _record(
            "fetch_doc_chunk",
            tool_class="evidence_expand",
            call_index=1,
            citation_refs=("my_md/doc.md > Agent Runtime",),
            chunk_keys=("c1",),
        )
    )

    decision = ReactBoundaryManager().evaluate_batch_tool_call(
        intent="doc_qa_with_evidence",
        tool_name="fetch_doc_chunk",
        tool_batch_index=1,
        ledger=ledger,
        evidence_assessment=_assessment_missing(),
        local_source_allowed=False,
    )

    assert decision.action == "execute"
    assert decision.reason == "evidence_incomplete"


def test_batch_does_not_skip_for_local_source() -> None:
    ledger = ToolCallLedger()
    ledger.add_record(
        _record("fetch_doc_chunk", tool_class="evidence_expand", call_index=1)
    )

    decision = ReactBoundaryManager().evaluate_batch_tool_call(
        intent="doc_qa_with_evidence",
        tool_name="fetch_doc_chunk",
        tool_batch_index=1,
        ledger=ledger,
        evidence_assessment=_assessment_ready(),
        local_source_allowed=True,
    )

    assert decision.action == "execute"
    assert decision.reason == "local_source_allowed"
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_react_boundary.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent.policies.react_boundary'`.

- [ ] **Step 3: Implement policy**

Create `agent/policies/react_boundary.py` with the interfaces and rules defined in the **Interfaces** section above.

Implementation requirements:

- Use `json.dumps(..., ensure_ascii=False)` for `result_payload`.
- Use `ledger.count_tool("fetch_doc_chunk")` to detect an already successful fetch only if the current ledger records successful tool results. If `count_tool` counts non-success entries, add a local helper:

```python
def _successful_tool_count(ledger: ToolCallLedger, tool_name: str) -> int:
    return sum(
        1
        for record in ledger.records
        if record.tool_name == tool_name and record.result_ok
    )
```

- Do not parse tool result JSON in this module.
- Do not import `TurnCompletionController`.

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_react_boundary.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/policies/react_boundary.py tests/test_react_boundary.py
git commit -m "feat: add document rag react boundary policy"
```

---

### Task 4: Add Reasoner Regression Tests Before Integration

**Files:**
- Modify: `tests/test_turn_completion_reasoner.py`

**Interfaces:**
- Consumes existing `_Provider`, `_RecordingTool`, `_make_reasoner`, `_msg`, `_session`.
- Produces failing regressions for the real P10a.4b bug, provider protocol legality, proactive final-only, and evidence-contract hint propagation.

- [ ] **Step 1: Add failing same-batch test**

Append to `tests/test_turn_completion_reasoner.py`:

```python
def test_same_batch_redundant_fetches_are_batch_skipped_and_final_only() -> None:
    search_docs = _RecordingTool(
        "search_docs",
        json.dumps(
            {
                "ok": True,
                "hit_count": 3,
                "hits": [
                    {
                        "chunk_id": "c1",
                        "citation": "my_md/doc.md > Agent Runtime",
                        "snippet": "Agent runtime 负责管理 agent 的一次运行过程。",
                    },
                    {
                        "chunk_id": "c2",
                        "citation": "my_md/doc.md > Tool Calling",
                        "snippet": "工具调用用于让 agent 访问外部能力。",
                    },
                    {
                        "chunk_id": "c3",
                        "citation": "my_md/doc.md > System Overview",
                        "snippet": "系统全景描述 agent 运行边界。",
                    },
                ],
            }
        ),
    )
    fetch_doc_chunk = _RecordingTool(
        "fetch_doc_chunk",
        json.dumps(
            {
                "ok": True,
                "chunk": {
                    "chunk_id": "c1",
                    "citation": "my_md/doc.md > Agent Runtime",
                    "content": "Agent runtime 负责管理 agent 的一次运行过程。",
                },
            }
        ),
    )
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[ToolCall("q1", "search_docs", {"query": "agent runtime"})],
            ),
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall("f1", "fetch_doc_chunk", {"chunk_id": "c1"}),
                    ToolCall("f2", "fetch_doc_chunk", {"chunk_id": "c2"}),
                    ToolCall("f3", "fetch_doc_chunk", {"chunk_id": "c3"}),
                ],
            ),
            LLMResponse(content="final answer with citation", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(
        provider,
        search_docs=search_docs,
        fetch_doc_chunk=fetch_doc_chunk,
    )

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg("根据项目文档回答agent runtime负责什么，并展开原文证据"),
            session=cast(Any, _session()),
        )
    )

    assert result.reply == "final answer with citation"
    assert result.tools_used == ["search_docs", "fetch_doc_chunk"]
    assert len(fetch_doc_chunk.calls) == 1
    assert provider.calls[-1]["tools"] == []
    assert result.context_retry["turn_completion"]["action"] == "final_only"
    assert result.context_retry["turn_completion"]["metadata"]["react_boundary"] is True
    statuses = [
        call.get("status")
        for group in result.tool_chain
        for call in group.get("calls", [])
        if call.get("name") == "fetch_doc_chunk"
    ]
    assert statuses == [
        "success",
        "batch_skipped_by_react_boundary",
        "batch_skipped_by_react_boundary",
    ]
    assert result.context_retry["turn_completion"]["metadata"]["batch_skip_count"] == 2
    assert result.context_retry["evidence_contract"]["metadata"]["fetched_text_count"] == 1
    assert result.context_retry["evidence_contract"]["metadata"][
        "soft_stopped_candidate_count"
    ] == 0
    assert result.context_retry["tool_boundary"]["ledger_summary"]["class_counts"][
        "evidence_expand"
    ] == 1

    final_messages = provider.calls[-1]["messages"]
    tool_results = {
        message.get("tool_call_id"): message
        for message in final_messages
        if message.get("role") == "tool"
    }
    assert {"f1", "f2", "f3"} <= set(tool_results)
    assert "react_boundary_batch_skip" in str(tool_results["f2"].get("content", ""))
    assert "react_boundary_batch_skip" in str(tool_results["f3"].get("content", ""))
```

- [ ] **Step 2: Add simple same-batch skip test**

Append:

```python
def test_simple_doc_same_batch_fetch_is_skipped_after_search_evidence() -> None:
    search_docs = _RecordingTool(
        "search_docs",
        json.dumps(
            {
                "ok": True,
                "hit_count": 1,
                "hits": [
                    {
                        "chunk_id": "c1",
                        "citation": "my_md/doc.md > Agent Runtime",
                        "snippet": "Agent runtime 负责管理 agent 的一次运行过程。",
                    }
                ],
            }
        ),
    )
    fetch_doc_chunk = _RecordingTool("fetch_doc_chunk")
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall("q1", "search_docs", {"query": "agent runtime"}),
                    ToolCall("f1", "fetch_doc_chunk", {"chunk_id": "c1"}),
                ],
            ),
            LLMResponse(content="simple final with citation", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(
        provider,
        search_docs=search_docs,
        fetch_doc_chunk=fetch_doc_chunk,
    )

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg("请从文档知识库中检索agent runtime负责什么？回答必须带文档引用"),
            session=cast(Any, _session()),
        )
    )

    assert result.reply == "simple final with citation"
    assert result.tools_used == ["search_docs"]
    assert len(fetch_doc_chunk.calls) == 0
    assert provider.calls[-1]["tools"] == []
    statuses = [
        call.get("status")
        for group in result.tool_chain
        for call in group.get("calls", [])
        if call.get("name") == "fetch_doc_chunk"
    ]
    assert statuses == ["batch_skipped_by_react_boundary"]
```

- [ ] **Step 3: Add proactive final-only and evidence hint tests**

Append:

```python
def test_simple_doc_retrieval_enters_final_only_without_fetch() -> None:
    search_docs = _RecordingTool(
        "search_docs",
        json.dumps(
            {
                "ok": True,
                "hit_count": 1,
                "hits": [
                    {
                        "chunk_id": "c1",
                        "citation": "my_md/doc.md > Agent Runtime",
                        "snippet": "Agent runtime 负责管理 agent 的一次运行过程。",
                    }
                ],
            }
        ),
    )
    fetch_doc_chunk = _RecordingTool("fetch_doc_chunk")
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[ToolCall("q1", "search_docs", {"query": "agent runtime"})],
            ),
            LLMResponse(content="simple final with citation", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(
        provider,
        search_docs=search_docs,
        fetch_doc_chunk=fetch_doc_chunk,
    )

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg("请从文档知识库中检索agent runtime负责什么？回答必须带文档引用"),
            session=cast(Any, _session()),
        )
    )

    assert result.reply == "simple final with citation"
    assert result.tools_used == ["search_docs"]
    assert len(fetch_doc_chunk.calls) == 0
    assert provider.calls[-1]["tools"] == []
    assert result.context_retry["turn_completion"]["reason"] == (
        "document_rag_retrieval_complete"
    )


def test_proactive_final_only_includes_evidence_contract_hint() -> None:
    search_docs = _RecordingTool(
        "search_docs",
        json.dumps(
            {
                "ok": True,
                "hit_count": 1,
                "hits": [
                    {
                        "chunk_id": "c1",
                        "citation": "my_md/doc.md > Agent Runtime",
                        "snippet": "Agent runtime 负责管理 agent 的一次运行过程。",
                    }
                ],
            }
        ),
    )
    fetch_doc_chunk = _RecordingTool(
        "fetch_doc_chunk",
        json.dumps(
            {
                "ok": True,
                "chunk": {
                    "chunk_id": "c1",
                    "citation": "my_md/doc.md > Agent Runtime",
                    "content": "Agent runtime 负责管理 agent 的一次运行过程。",
                },
            }
        ),
    )
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[ToolCall("q1", "search_docs", {"query": "agent runtime"})],
            ),
            LLMResponse(
                content="",
                tool_calls=[ToolCall("f1", "fetch_doc_chunk", {"chunk_id": "c1"})],
            ),
            LLMResponse(content="final answer", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(
        provider,
        search_docs=search_docs,
        fetch_doc_chunk=fetch_doc_chunk,
    )

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg("根据项目文档回答agent runtime负责什么，并展开原文证据"),
            session=cast(Any, _session()),
        )
    )

    final_messages = provider.calls[-1]["messages"]
    hint_text = "\n".join(str(message.get("content", "")) for message in final_messages)

    assert "Evidence contract for this answer" in hint_text
    assert "Only successful fetch_doc_chunk results may be described" in hint_text
    assert result.context_retry["evidence_contract"]["sufficiency"][
        "tool_stop_allowed"
    ] is True
```

- [ ] **Step 4: Run tests to verify RED**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_turn_completion_reasoner.py::test_same_batch_redundant_fetches_are_batch_skipped_and_final_only \
  tests/test_turn_completion_reasoner.py::test_simple_doc_same_batch_fetch_is_skipped_after_search_evidence \
  tests/test_turn_completion_reasoner.py::test_simple_doc_retrieval_enters_final_only_without_fetch \
  tests/test_turn_completion_reasoner.py::test_proactive_final_only_includes_evidence_contract_hint \
  -q
```

Expected: FAIL. Current behavior should either execute/soft-stop through the old boundary path or not set the new metadata.

- [ ] **Step 5: Do not implement in this task**

Stop after confirming RED. Implementation belongs in Task 5.

---

### Task 5: Integrate Batch Boundary And Proactive Completion In Reasoner

**Files:**
- Modify: `agent/core/passive_turn.py`
- Modify: `tests/test_turn_completion_reasoner.py` only if imports need adjustment.

**Interfaces:**
- Consumes:
  - `ReactBoundaryManager`
  - `BatchToolDecision`
  - `ToolAccessPlan.local_source_allowed`
  - `TurnCompletionController.evaluate(..., evidence_assessment=..., proactive_allowed=True)`
- Produces:
  - same-batch skip status `batch_skipped_by_react_boundary`
  - `turn_completion.metadata.react_boundary == True`
  - final `turn_completion.metadata.batch_skip_count`

- [ ] **Step 1: Import and instantiate manager**

In `agent/core/passive_turn.py`, add:

```python
from agent.policies.react_boundary import ReactBoundaryManager
```

In `DefaultReasoner.__init__`, add:

```python
self._react_boundary = ReactBoundaryManager()
```

- [ ] **Step 2: Add helper for local-source flag**

Near other small helpers in `agent/core/passive_turn.py`, add:

```python
def _local_source_allowed(context: ToolBoundaryContext | None) -> bool:
    if context is None:
        return False
    return bool(getattr(context.access_plan, "local_source_allowed", False))
```

Do not use `access_plan.reason` for this decision.

- [ ] **Step 3: Add helper to convert proactive completion trace**

Add:

```python
def _react_completion_metadata(
    *,
    reason: str,
    decision_metadata: Mapping[str, object],
    recommended_suppress: frozenset[str],
    batch_skip_count: int,
) -> dict[str, object]:
    return {
        **dict(decision_metadata),
        "react_boundary": True,
        "react_boundary_reason": reason,
        "recommended_suppress": sorted(recommended_suppress),
        "batch_skip_count": batch_skip_count,
    }
```

If `Mapping` is not already imported in `agent/core/passive_turn.py`, add it from `collections.abc`.

Add a helper to refresh the count after later same-batch skips:

```python
def _with_batch_skip_count(
    decision: TurnCompletionDecision | None,
    batch_skip_count: int,
) -> TurnCompletionDecision | None:
    if decision is None:
        return None
    if not bool(decision.metadata.get("react_boundary")):
        return decision
    return TurnCompletionDecision(
        action=decision.action,
        reason=decision.reason,
        model_hint=decision.model_hint,
        metadata={**dict(decision.metadata), "batch_skip_count": batch_skip_count},
    )
```

- [ ] **Step 4: Track batch skip count**

In `DefaultReasoner.run()`, near existing turn-local variables:

```python
react_boundary_batch_skip_count = 0
```

- [ ] **Step 5: Evaluate batch skip before normal tool boundary execution**

Inside the `for tool_batch_index, tool_call in enumerate(response.tool_calls):` loop, after `visible_before_call` is computed and before `self._tool_boundary.evaluate_tool_call(...)`, add:

```python
                    if tool_boundary_context is not None:
                        batch_decision = self._react_boundary.evaluate_batch_tool_call(
                            intent=tool_boundary_context.intent,
                            tool_name=tool_call.name,
                            tool_batch_index=tool_batch_index,
                            ledger=tool_boundary_context.ledger,
                            evidence_assessment=evidence_assessment,
                            local_source_allowed=_local_source_allowed(
                                tool_boundary_context
                            ),
                        )
                        if batch_decision.action == "skip":
                            react_boundary_batch_skip_count += 1
                            turn_completion_decision = _with_batch_skip_count(
                                turn_completion_decision,
                                react_boundary_batch_skip_count,
                            )
                            result = batch_decision.result_payload
                            await self._observe_tool_call_started(
                                session_key=tool_event_session_key,
                                channel=tool_event_channel,
                                chat_id=tool_event_chat_id,
                                iteration=iteration + 1,
                                call_id=tool_call.id,
                                tool_name=tool_call.name,
                                arguments=tool_call.arguments,
                            )
                            append_tool_result(
                                messages,
                                tool_call_id=tool_call.id,
                                content=result,
                                tool_name=tool_call.name,
                            )
                            await self._observe_tool_call_completed(
                                session_key=tool_event_session_key,
                                channel=tool_event_channel,
                                chat_id=tool_event_chat_id,
                                iteration=iteration + 1,
                                call_id=tool_call.id,
                                tool_name=tool_call.name,
                                arguments=tool_call.arguments,
                                final_arguments=tool_call.arguments,
                                status=batch_decision.status,
                                result_preview=support.log_preview(result),
                            )
                            iter_calls.append(
                                {
                                    "call_id": tool_call.id,
                                    "name": tool_call.name,
                                    "status": batch_decision.status,
                                    "arguments": tool_call.arguments,
                                    "boundary_action": "skip",
                                    "boundary_reason": batch_decision.reason,
                                    "result": result,
                                }
                            )
                            logger.info(
                                "[react_boundary] batch_skip tool=%s reason=%s",
                                tool_call.name,
                                batch_decision.reason,
                            )
                            continue
```

Do not call `record_tool_result()` for skipped calls. They are protocol results, not successful evidence.

- [ ] **Step 6: Evaluate proactive final-only after real tool result assessment**

After the existing block that records a successful real tool result and computes:

```python
evidence_assessment = self._evidence_contract.assess(...)
```

add:

```python
                        react_decision = self._react_boundary.evaluate_after_tool_result(
                            intent=tool_boundary_context.intent,
                            ledger=tool_boundary_context.ledger,
                            evidence_assessment=evidence_assessment,
                            local_source_allowed=_local_source_allowed(
                                tool_boundary_context
                            ),
                        )
                        completion_decision = self._turn_completion.evaluate(
                            intent=tool_boundary_context.intent,
                            ledger=tool_boundary_context.ledger,
                            boundary_decisions=self._tool_boundary.recent_decisions(
                                tool_boundary_context
                            ),
                            evidence_assessment=evidence_assessment,
                            local_source_allowed=_local_source_allowed(
                                tool_boundary_context
                            ),
                            proactive_allowed=react_decision.recommend_final_only,
                        )
                        if completion_decision.action == "final_only":
                            metadata = _react_completion_metadata(
                                reason=react_decision.reason,
                                decision_metadata=react_decision.metadata,
                                recommended_suppress=react_decision.recommended_suppress,
                                batch_skip_count=react_boundary_batch_skip_count,
                            )
                            turn_completion_decision = TurnCompletionDecision(
                                action="final_only",
                                reason=completion_decision.reason,
                                model_hint=completion_decision.model_hint,
                                metadata={
                                    **dict(completion_decision.metadata),
                                    **metadata,
                                },
                            )
                            final_only_next_call = True
                            logger.info(
                                "[react_boundary] final_only reason=%s",
                                react_decision.reason,
                            )
```

Keep the existing soft-stop-triggered `TurnCompletionController.evaluate(...)` fallback. Update that fallback call to pass:

```python
evidence_assessment=evidence_assessment,
local_source_allowed=_local_source_allowed(tool_boundary_context),
```

but keep `proactive_allowed=False`.

- [ ] **Step 7: Run Task 4 regressions to verify GREEN**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_turn_completion_reasoner.py::test_same_batch_redundant_fetches_are_batch_skipped_and_final_only \
  tests/test_turn_completion_reasoner.py::test_simple_doc_same_batch_fetch_is_skipped_after_search_evidence \
  tests/test_turn_completion_reasoner.py::test_simple_doc_retrieval_enters_final_only_without_fetch \
  tests/test_turn_completion_reasoner.py::test_proactive_final_only_includes_evidence_contract_hint \
  -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add agent/core/passive_turn.py tests/test_turn_completion_reasoner.py
git commit -m "feat: bound document rag same-batch tool calls"
```

---

### Task 6: Verify Proactive Final-Only Reasoner Tests

**Files:**
- Modify: `tests/test_turn_completion_reasoner.py`

**Interfaces:**
- Consumes Task 4 tests and Task 5 integration.
- Produces GREEN verification for serial happy paths and evidence-contract hint propagation.

- [ ] **Step 1: Run tests added in Task 4**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_turn_completion_reasoner.py::test_simple_doc_retrieval_enters_final_only_without_fetch \
  tests/test_turn_completion_reasoner.py::test_proactive_final_only_includes_evidence_contract_hint \
  -q
```

Expected: PASS.

- [ ] **Step 2: Commit**

```bash
git add tests/test_turn_completion_reasoner.py
git commit -m "test: verify proactive document rag final-only paths"
```

---

### Task 7: Preserve Fallback And Local-Source Behavior

**Files:**
- Modify: `tests/test_turn_completion_reasoner.py`
- Modify: `tests/test_react_boundary.py` if additional policy coverage is needed.

**Interfaces:**
- Consumes Task 1 local-source flag and Task 5 integration.
- Produces regression coverage that bounded ReAct does not over-close open exploration/source tasks.

- [ ] **Step 1: Add no-citation fallback test**

Append:

```python
def test_proactive_boundary_does_not_final_only_without_citation() -> None:
    search_docs = _RecordingTool(
        "search_docs",
        json.dumps(
            {
                "ok": True,
                "hit_count": 1,
                "hits": [{"chunk_id": "c1", "snippet": "Agent runtime text"}],
            }
        ),
    )
    fetch_doc_chunk = _RecordingTool("fetch_doc_chunk")
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[ToolCall("q1", "search_docs", {"query": "agent runtime"})],
            ),
            LLMResponse(
                content="",
                tool_calls=[ToolCall("f1", "fetch_doc_chunk", {"chunk_id": "c1"})],
            ),
            LLMResponse(content="best effort answer", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(
        provider,
        search_docs=search_docs,
        fetch_doc_chunk=fetch_doc_chunk,
    )

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg("根据项目文档回答agent runtime负责什么，并展开原文证据"),
            session=cast(Any, _session()),
        )
    )

    assert result.reply == "best effort answer"
    assert len(provider.calls) == 3
    assert provider.calls[1]["tools"] != []
    assert result.context_retry.get("turn_completion", {}).get("action") != "final_only"
```

- [ ] **Step 2: Preserve explicit local-source reasoner test**

Keep the existing `tests/test_turn_completion_reasoner.py::test_explicit_local_source_request_does_not_switch_to_final_only` and update it only if the implementation changes metadata shape. It must continue to assert:

```python
assert result.context_retry.get("turn_completion", {}).get("action") != "final_only"
assert provider.calls[3]["tools"] != []
assert len(read_file.calls) == 1
```

This proves the reasoner did not use Document RAG sufficiency to close a source investigation turn before the explicit `read_file` call.

- [ ] **Step 3: Run fallback tests**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_turn_completion_reasoner.py::test_proactive_boundary_does_not_final_only_without_citation \
  tests/test_turn_completion_reasoner.py::test_explicit_local_source_request_does_not_switch_to_final_only \
  -q
```

Expected: PASS.

- [ ] **Step 4: Run existing negative completion tests**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_turn_completion_reasoner.py::test_no_hit_retrieval_does_not_switch_to_final_only \
  tests/test_turn_completion_reasoner.py::test_chunk_without_citation_does_not_switch_to_final_only \
  -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_turn_completion_reasoner.py tests/test_react_boundary.py
git commit -m "test: preserve document rag fallback boundaries"
```

---

### Task 8: Documentation Update

**Files:**
- Modify: `my_md/governance/02-current-issues.md`
- Modify: `my_md/governance/04-fix-roadmap.md`
- Modify: `my_md/governance/06-star-log.md`
- Modify: `my_md/rag/22-document-rag-p10a3-turn-completion-plan.md`
- Modify: `progress.md`

**Interfaces:**
- Consumes test results from Tasks 1-7.
- Produces documented implementation status and smoke-test recipe.

- [ ] **Step 1: Update current issues**

Record:

```markdown
P10a.4b Bounded ReAct / Batch Boundary 已实现或正在实现：
- P10a.4a 后的剩余问题不是证据正确性，而是同一 assistant tool-call batch 仍生成多余 `fetch_doc_chunk`。
- 方案分两层：after-result proactive final-only 控制下一轮；same-batch boundary 控制当前 response 中已生成的冗余 tool calls。
- Same-batch skipped calls 仍追加合法 tool result，但标记为 `batch_skipped_by_react_boundary`，不计入成功 `tools_used`，不写入证据 ledger。
```

- [ ] **Step 2: Update roadmap**

Record:

```markdown
P10a.4b 验收指标：
- simple doc: `search_docs -> final`
- evidence doc: `search_docs -> fetch_doc_chunk -> final`
- same-batch multi fetch: only first fetch executes; later fetch calls are `batch_skipped_by_react_boundary`
- no `shell/read_file/list_dir`
- final-only includes Evidence Contract
- explicit local-source intent does not proactive final-only
```

- [ ] **Step 3: Update STAR log**

Add to CASE-003:

```markdown
P10a.4b 把问题从“执行边界”进一步拆成“同批次协议边界”和“下一轮终止边界”。由于 LLM 已经在一个 assistant message 中生成的 tool calls 不能被 after-result final-only 取消，系统必须为每个 generated tool call 追加合法 tool result，同时用 batch boundary 降低噪声并防止这些 skipped calls 污染 evidence ledger。
```

- [ ] **Step 4: Update RAG plan and progress**

Record exact pytest commands and results. If real CLI smoke has not been run yet, state it as pending and include the command/prompt to run.

- [ ] **Step 5: Commit**

```bash
git add \
  my_md/governance/02-current-issues.md \
  my_md/governance/04-fix-roadmap.md \
  my_md/governance/06-star-log.md \
  my_md/rag/22-document-rag-p10a3-turn-completion-plan.md \
  progress.md
git commit -m "docs: record bounded react batch boundary plan"
```

---

### Task 9: Final Verification

**Files:**
- No new source files unless failures require fixes.

**Interfaces:**
- Consumes all previous tasks.
- Produces final readiness evidence.

- [ ] **Step 1: Run targeted P10a suite**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_react_boundary.py \
  tests/test_turn_completion_policy.py \
  tests/test_turn_completion_reasoner.py \
  tests/test_tool_boundary_manager.py \
  tests/test_tool_boundary_reasoner.py \
  tests/test_evidence_completion_policy.py \
  tests/test_evidence_contract.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run full pytest**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest -q
```

Expected: PASS.

- [ ] **Step 3: Run compile check**

Run:

```bash
python3 -m compileall agent/policies agent/core/passive_turn.py tests/test_react_boundary.py tests/test_turn_completion_reasoner.py
```

Expected: exits 0.

- [ ] **Step 4: Run diff check**

Run:

```bash
git diff --check
```

Expected: exits 0.

- [ ] **Step 5: Manual CLI smoke**

Run these prompts in the CLI after restarting the agent if needed:

```text
请从文档知识库中检索agent runtime负责什么？回答必须带文档引用
```

```text
根据项目文档回答agent runtime负责什么，并展开原文证据
```

Expected logs:

```text
[react_boundary] final_only reason=document_rag_retrieval_complete
[react_boundary] final_only reason=document_rag_evidence_complete
```

If the model emits same-batch redundant fetch calls, expected logs:

```text
[react_boundary] batch_skip tool=fetch_doc_chunk reason=document_rag_batch_evidence_complete
```

Expected observe/session facts:

- no `shell/read_file/list_dir`
- successful target tools:
  - simple doc: `search_docs`
  - evidence doc: `search_docs`, `fetch_doc_chunk`
- final answer has citations
- final answer labels only successful `fetch_doc_chunk` result as original/full text

- [ ] **Step 6: Commit final fixes if needed**

If Step 1-5 required fixes:

```bash
git add \
  agent/core/passive_turn.py \
  agent/policies/react_boundary.py \
  agent/policies/tool_access.py \
  agent/policies/turn_completion.py \
  tests/test_react_boundary.py \
  tests/test_tool_access_gateway.py \
  tests/test_turn_completion_policy.py \
  tests/test_turn_completion_reasoner.py \
  my_md/governance/02-current-issues.md \
  my_md/governance/04-fix-roadmap.md \
  my_md/governance/06-star-log.md \
  my_md/rag/22-document-rag-p10a3-turn-completion-plan.md \
  progress.md
git commit -m "fix: stabilize bounded react batch boundary"
```

---

## Self-Review

- Spec coverage:
  - Same-batch multi `fetch_doc_chunk` is covered by Task 4 and Task 5.
  - Proactive next-call final-only is covered by Task 2, Task 5, and Task 6.
  - Evidence sufficiency remains owned by `EvidenceContractManager`; `ReactBoundaryManager` consumes `EvidenceAssessment`.
  - Local-source exemption uses stable `ToolAccessPlan.local_source_allowed`, not `reason` strings.
  - Provider protocol legality is preserved by appending a lightweight tool result for every skipped generated tool call.
  - Fallback soft-stop behavior remains as fallback.
- Placeholder scan:
  - No placeholder implementation steps remain.
  - No angle-bracket placeholders remain in commands or commit steps.
- Type consistency:
  - `ReactBoundaryDecision.recommend_final_only` is used instead of `final_only` so `TurnCompletionController` remains the only owner of final completion decisions.
  - `ReactBoundaryDecision.recommended_suppress` is used consistently instead of the old ambiguous `visible_suppress`.
  - `BatchToolDecision.status` uses `batch_skipped_by_react_boundary`.
  - `TurnCompletionController.evaluate()` receives `evidence_assessment` and `proactive_allowed`.
  - `ToolAccessPlan.local_source_allowed` is the stable local-source capability flag.
