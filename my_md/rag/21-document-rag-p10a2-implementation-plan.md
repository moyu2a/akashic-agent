# P10a.2 Turn Tool Boundary Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a turn-local Tool Boundary Manager that preserves P10a.1 access control while adding tool budget, repeated-call, evidence-completion, ledger, and trace governance for P10a.2.

**Architecture:** Add pure policy modules first, then introduce a `TurnToolBoundaryManager` facade that wraps the existing `ToolAccessGateway`. Integrate the facade into `DefaultReasoner` at the existing narrow tool visibility, `tool_search`, pre-execution, post-result, and next-loop hint points without rewriting `AgentLoop`.

**Tech Stack:** Python 3.11+, dataclasses, existing `agent.policies`, existing `DefaultReasoner`, existing pytest + pytest-asyncio test suite, no new runtime dependency.

## Global Constraints

- All boundary decisions are current-turn only.
- Do not mutate `ToolDiscoveryState` or LRU from P10a.2 policy decisions.
- Do not change tool `always_on` metadata.
- Do not rewrite `AgentLoop`.
- Preserve existing P10a.1 Tool Access Gateway behavior.
- `soft_stop` means: do not execute the requested target tool; return a structured boundary result; enqueue a compact next-call hint.
- `soft_stop` and `block` must not add the target tool to successful `tools_used`.
- Core access block, disabled tools, and no-tool policies cannot be weakened by budget, evidence, or future plugin rules.
- `ToolCallLedger` is the shared current-turn fact source; policies should not rescan raw LLM messages.
- First implementation is core-only; plugins do not contribute rules yet.
- Keep changes scoped to `agent/policies`, `agent/core/passive_turn.py`, focused tests, and P10a.2 docs.

---

## File Structure

Create:

- `agent/policies/tool_ledger.py`
  - Defines `ToolClass`, `ToolCallRecord`, `ToolCallLedger`, `classify_tool_name`, `extract_tool_result_facts`, and stable argument hashing.
  - Owns structured facts used by budget and evidence policies.

- `agent/policies/tool_budget.py`
  - Defines `TaskIntent`, `ToolBoundaryAction`, `ToolBoundaryDecision`, `BudgetProfile`, `ToolBudgetPolicy`, and `infer_task_intent`.
  - Decides `warn`, `soft_stop`, or `allow` for repeated/over-budget tool calls.

- `agent/policies/evidence_completion.py`
  - Defines `EvidenceCompletionPolicy`.
  - Emits a `soft_stop` when Document RAG evidence is sufficient.

- `agent/policies/tool_boundary.py`
  - Defines `TurnToolBoundaryManager`, `ToolBoundaryContext`, and facade APIs.
  - Wraps existing `ToolAccessGateway` and merges access, budget, and evidence decisions.

- `tests/test_tool_ledger.py`
- `tests/test_tool_budget_policy.py`
- `tests/test_evidence_completion_policy.py`
- `tests/test_tool_boundary_manager.py`
- `tests/test_tool_boundary_reasoner.py`

Modify:

- `agent/core/passive_turn.py`
  - Replace direct `_tool_access_gateway` usage with `TurnToolBoundaryManager`.
  - Keep `_tool_access_trace` compatibility or add `_tool_boundary_trace`.
  - Insert pending soft-stop hint before the next LLM call through the existing `loop_state` hint path.

- `my_md/rag/20-document-rag-p10a2-tool-boundary-design.md`
  - Mark implementation status and any final API adjustments.

- `my_md/rag/21-document-rag-p10a2-implementation-plan.md`
  - Track task completion.

---

### Task 1: Tool Ledger

**Files:**
- Create: `agent/policies/tool_ledger.py`
- Test: `tests/test_tool_ledger.py`

**Interfaces:**
- Produces:
  - `ToolClass = Literal["discovery", "retrieval", "evidence_expand", "local_file", "execution", "external_io", "memory_write", "unknown"]`
  - `classify_tool_name(tool_name: str) -> ToolClass`
  - `stable_args_hash(arguments: Mapping[str, Any]) -> str`
  - `extract_tool_result_facts(tool_name: str, result_text: str) -> ToolResultFacts`
  - `ToolCallLedger.add_record(record: ToolCallRecord) -> None`
  - `ToolCallLedger.count_tool(tool_name: str) -> int`
  - `ToolCallLedger.count_class(tool_class: ToolClass) -> int`
  - `ToolCallLedger.same_args_count(tool_name: str, args_hash: str) -> int`
  - `ToolCallLedger.has_successful_retrieval() -> bool`
  - `ToolCallLedger.has_citation_evidence() -> bool`
  - `ToolCallLedger.summary() -> dict[str, object]`
- Consumes: no project-specific imports except stdlib.

- [ ] **Step 1: Write failing ledger tests**

Add `tests/test_tool_ledger.py`:

```python
from __future__ import annotations

import json

from agent.policies.tool_ledger import (
    ToolCallLedger,
    ToolCallRecord,
    classify_tool_name,
    extract_tool_result_facts,
    stable_args_hash,
)


def test_classifies_known_tool_classes() -> None:
    assert classify_tool_name("tool_search") == "discovery"
    assert classify_tool_name("search_docs") == "retrieval"
    assert classify_tool_name("recall_memory") == "retrieval"
    assert classify_tool_name("fetch_doc_chunk") == "evidence_expand"
    assert classify_tool_name("fetch_messages") == "evidence_expand"
    assert classify_tool_name("read_file") == "local_file"
    assert classify_tool_name("list_dir") == "local_file"
    assert classify_tool_name("shell") == "execution"
    assert classify_tool_name("memorize") == "memory_write"
    assert classify_tool_name("custom_tool") == "unknown"


def test_stable_args_hash_is_order_insensitive() -> None:
    left = stable_args_hash({"query": "agent runtime", "top_k": 5})
    right = stable_args_hash({"top_k": 5, "query": "agent runtime"})
    assert left == right
    assert len(left) == 16


def test_extracts_search_docs_facts() -> None:
    result = json.dumps(
        {
            "ok": True,
            "hit_count": 2,
            "hits": [
                {
                    "chunk_id": "c1",
                    "citation": "my_md/doc.md > Agent Runtime",
                }
            ],
        }
    )

    facts = extract_tool_result_facts("search_docs", result)

    assert facts.result_ok is True
    assert facts.hit_count == 2
    assert facts.result_has_evidence is True
    assert facts.result_has_citation is True
    assert facts.citation_refs == ("my_md/doc.md > Agent Runtime",)
    assert facts.chunk_keys == ("c1",)


def test_extracts_fetch_doc_chunk_facts() -> None:
    result = json.dumps(
        {
            "ok": True,
            "chunk": {
                "chunk_id": "c1",
                "citation": "my_md/doc.md > Agent Runtime",
                "text": "Agent runtime 负责管理 agent 的一次运行过程。",
            },
        }
    )

    facts = extract_tool_result_facts("fetch_doc_chunk", result)

    assert facts.result_ok is True
    assert facts.result_has_evidence is True
    assert facts.result_has_citation is True
    assert facts.hit_count is None
    assert facts.citation_refs == ("my_md/doc.md > Agent Runtime",)
    assert facts.chunk_keys == ("c1",)


def test_extracts_terminal_scope() -> None:
    facts = extract_tool_result_facts(
        "search_docs",
        json.dumps({"terminal_scope": "document_rag", "fallback_allowed": False}),
    )
    assert facts.terminal_scope == "document_rag"


def test_ledger_counts_and_summary() -> None:
    ledger = ToolCallLedger()
    args_hash = stable_args_hash({"query": "agent runtime"})
    ledger.add_record(
        ToolCallRecord(
            tool_name="search_docs",
            tool_class="retrieval",
            args_hash=args_hash,
            args_summary='{"query":"agent runtime"}',
            call_index=1,
            visible_before_call=True,
            result_ok=True,
            hit_count=1,
            citation_refs=("my_md/doc.md > Agent Runtime",),
            chunk_keys=("c1",),
            result_has_evidence=True,
            result_has_citation=True,
        )
    )
    ledger.add_record(
        ToolCallRecord(
            tool_name="search_docs",
            tool_class="retrieval",
            args_hash=args_hash,
            args_summary='{"query":"agent runtime"}',
            call_index=2,
            visible_before_call=True,
            decision_action="soft_stop",
            decision_reason="retrieval_budget_exceeded",
        )
    )

    assert ledger.count_tool("search_docs") == 2
    assert ledger.count_class("retrieval") == 2
    assert ledger.same_args_count("search_docs", args_hash) == 2
    assert ledger.has_successful_retrieval() is True
    assert ledger.has_citation_evidence() is True
    assert ledger.summary() == {
        "tool_calls": 2,
        "class_counts": {"retrieval": 2},
        "has_successful_retrieval": True,
        "has_citation_evidence": True,
    }
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_tool_ledger.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agent.policies.tool_ledger'`.

- [ ] **Step 3: Implement `tool_ledger.py`**

Create `agent/policies/tool_ledger.py`:

```python
from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

ToolClass = Literal[
    "discovery",
    "retrieval",
    "evidence_expand",
    "local_file",
    "execution",
    "external_io",
    "memory_write",
    "unknown",
]

_TOOL_CLASS_BY_NAME: dict[str, ToolClass] = {
    "tool_search": "discovery",
    "search_docs": "retrieval",
    "recall_memory": "retrieval",
    "search_messages": "retrieval",
    "fetch_doc_chunk": "evidence_expand",
    "fetch_messages": "evidence_expand",
    "read_file": "local_file",
    "list_dir": "local_file",
    "shell": "execution",
    "memorize": "memory_write",
}


@dataclass(frozen=True)
class ToolResultFacts:
    result_ok: bool = False
    hit_count: int | None = None
    citation_refs: tuple[str, ...] = ()
    chunk_keys: tuple[str, ...] = ()
    terminal_scope: str = ""
    result_has_evidence: bool = False
    result_has_citation: bool = False
    result_error_code: str = ""


@dataclass(frozen=True)
class ToolCallRecord:
    tool_name: str
    tool_class: ToolClass
    args_hash: str
    args_summary: str
    call_index: int
    visible_before_call: bool
    decision_action: str = "allow"
    decision_reason: str = ""
    requested_unlocks: tuple[str, ...] = ()
    unlocked_tools: tuple[str, ...] = ()
    blocked_tools: tuple[str, ...] = ()
    result_ok: bool = False
    hit_count: int | None = None
    citation_refs: tuple[str, ...] = ()
    chunk_keys: tuple[str, ...] = ()
    terminal_scope: str = ""
    result_summary: str = ""
    result_has_evidence: bool = False
    result_has_citation: bool = False
    result_error_code: str = ""


@dataclass
class ToolCallLedger:
    records: list[ToolCallRecord] = field(default_factory=list)

    def add_record(self, record: ToolCallRecord) -> None:
        self.records.append(record)

    def next_call_index(self) -> int:
        return len(self.records) + 1

    def count_tool(self, tool_name: str) -> int:
        return sum(1 for record in self.records if record.tool_name == tool_name)

    def count_class(self, tool_class: ToolClass) -> int:
        return sum(1 for record in self.records if record.tool_class == tool_class)

    def same_args_count(self, tool_name: str, args_hash: str) -> int:
        return sum(
            1
            for record in self.records
            if record.tool_name == tool_name and record.args_hash == args_hash
        )

    def has_successful_retrieval(self) -> bool:
        return any(
            record.tool_class == "retrieval"
            and record.result_ok
            and (record.hit_count or 0) > 0
            for record in self.records
        )

    def has_citation_evidence(self) -> bool:
        return any(record.result_has_citation for record in self.records)

    def summary(self) -> dict[str, object]:
        class_counts = Counter(record.tool_class for record in self.records)
        return {
            "tool_calls": len(self.records),
            "class_counts": dict(sorted(class_counts.items())),
            "has_successful_retrieval": self.has_successful_retrieval(),
            "has_citation_evidence": self.has_citation_evidence(),
        }


def classify_tool_name(tool_name: str) -> ToolClass:
    return _TOOL_CLASS_BY_NAME.get(tool_name, "unknown")


def stable_args_hash(arguments: Mapping[str, Any]) -> str:
    encoded = json.dumps(arguments, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def summarize_args(arguments: Mapping[str, Any], *, max_chars: int = 240) -> str:
    encoded = json.dumps(arguments, ensure_ascii=False, sort_keys=True, default=str)
    if len(encoded) <= max_chars:
        return encoded
    return encoded[: max_chars - 1] + "…"


def extract_tool_result_facts(tool_name: str, result_text: str) -> ToolResultFacts:
    try:
        payload = json.loads(result_text)
    except (TypeError, ValueError):
        return ToolResultFacts(result_ok=False)
    if not isinstance(payload, dict):
        return ToolResultFacts(result_ok=False)

    result_ok = payload.get("ok") is True
    error_code = str(payload.get("error_code") or "")
    terminal_scope = str(payload.get("terminal_scope") or "")
    hit_count = _as_int(payload.get("hit_count"))
    citations: list[str] = []
    chunk_keys: list[str] = []

    if isinstance(payload.get("hits"), list):
        for item in payload["hits"]:
            if not isinstance(item, dict):
                continue
            _append_str(citations, item.get("citation"))
            _append_str(chunk_keys, item.get("chunk_id"))

    chunk = payload.get("chunk")
    if isinstance(chunk, dict):
        _append_str(citations, chunk.get("citation"))
        _append_str(chunk_keys, chunk.get("chunk_id"))

    result_has_citation = bool(citations)
    result_has_evidence = result_ok and (
        result_has_citation or bool(chunk_keys) or (hit_count or 0) > 0
    )

    return ToolResultFacts(
        result_ok=result_ok,
        hit_count=hit_count,
        citation_refs=tuple(citations),
        chunk_keys=tuple(chunk_keys),
        terminal_scope=terminal_scope,
        result_has_evidence=result_has_evidence,
        result_has_citation=result_has_citation,
        result_error_code=error_code,
    )


def _append_str(target: list[str], value: object) -> None:
    if isinstance(value, str) and value:
        target.append(value)


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None
```

- [ ] **Step 4: Run ledger tests**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_tool_ledger.py -q
```

Expected: `6 passed`.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add agent/policies/tool_ledger.py tests/test_tool_ledger.py my_md/rag/21-document-rag-p10a2-implementation-plan.md
git commit -m "Add turn-local tool call ledger"
```

---

### Task 2: Budget And Evidence Policies

**Files:**
- Create: `agent/policies/tool_budget.py`
- Create: `agent/policies/evidence_completion.py`
- Test: `tests/test_tool_budget_policy.py`
- Test: `tests/test_evidence_completion_policy.py`

**Interfaces:**
- Consumes from Task 1:
  - `ToolCallLedger`
  - `ToolCallRecord`
  - `ToolClass`
  - `classify_tool_name`
  - `stable_args_hash`
- Produces:
  - `TaskIntent`
  - `ToolBoundaryAction`
  - `ToolBoundaryDecision`
  - `infer_task_intent(user_text: str) -> TaskIntent`
  - `ToolBudgetPolicy.evaluate_call(...) -> ToolBoundaryDecision`
  - `EvidenceCompletionPolicy.evaluate_call(...) -> ToolBoundaryDecision`

- [ ] **Step 1: Write failing budget policy tests**

Add `tests/test_tool_budget_policy.py`:

```python
from __future__ import annotations

from agent.policies.tool_budget import (
    ToolBudgetPolicy,
    ToolBoundaryDecision,
    infer_task_intent,
)
from agent.policies.tool_ledger import (
    ToolCallLedger,
    ToolCallRecord,
    classify_tool_name,
    stable_args_hash,
)


def _record(tool_name: str, args: dict, *, ok: bool = True, hit_count: int | None = None) -> ToolCallRecord:
    return ToolCallRecord(
        tool_name=tool_name,
        tool_class=classify_tool_name(tool_name),
        args_hash=stable_args_hash(args),
        args_summary=str(args),
        call_index=1,
        visible_before_call=True,
        result_ok=ok,
        hit_count=hit_count,
        result_has_evidence=ok and ((hit_count or 0) > 0),
    )


def test_infers_doc_qa_with_evidence_intent() -> None:
    assert (
        infer_task_intent("根据项目文档回答agent runtime负责什么，并展开原文证据")
        == "doc_qa_with_evidence"
    )


def test_infers_doc_qa_simple_intent() -> None:
    assert infer_task_intent("请从文档知识库中检索agent runtime负责什么") == "doc_qa_simple"


def test_infers_open_exploration_for_non_doc_prompt() -> None:
    assert infer_task_intent("帮我分析这个项目下一步怎么做") == "open_exploration"


def test_redundant_tool_search_for_visible_target_soft_stops() -> None:
    decision = ToolBudgetPolicy().evaluate_call(
        intent="doc_qa_with_evidence",
        ledger=ToolCallLedger(),
        tool_name="tool_search",
        arguments={"query": "select:search_docs,fetch_doc_chunk"},
        visible_names={"tool_search", "search_docs", "fetch_doc_chunk"},
    )

    assert decision.action == "soft_stop"
    assert decision.reason == "redundant_visible_tool_search"
    assert "already visible" in (decision.model_hint or "")


def test_second_similar_search_docs_soft_stops_after_successful_retrieval() -> None:
    ledger = ToolCallLedger()
    ledger.add_record(_record("search_docs", {"query": "agent runtime"}, hit_count=3))

    decision = ToolBudgetPolicy().evaluate_call(
        intent="doc_qa_with_evidence",
        ledger=ledger,
        tool_name="search_docs",
        arguments={"query": "agent runtime"},
        visible_names={"search_docs", "fetch_doc_chunk"},
    )

    assert decision.action == "soft_stop"
    assert decision.reason == "retrieval_budget_exceeded"


def test_third_fetch_doc_chunk_soft_stops() -> None:
    ledger = ToolCallLedger()
    ledger.add_record(_record("fetch_doc_chunk", {"chunk_id": "c1"}))
    ledger.add_record(_record("fetch_doc_chunk", {"chunk_id": "c2"}))

    decision = ToolBudgetPolicy().evaluate_call(
        intent="doc_qa_with_evidence",
        ledger=ledger,
        tool_name="fetch_doc_chunk",
        arguments={"chunk_id": "c3"},
        visible_names={"search_docs", "fetch_doc_chunk"},
    )

    assert decision.action == "soft_stop"
    assert decision.reason == "evidence_expand_budget_exceeded"


def test_budget_allows_first_required_doc_rag_calls() -> None:
    policy = ToolBudgetPolicy()
    ledger = ToolCallLedger()

    first_search = policy.evaluate_call(
        intent="doc_qa_with_evidence",
        ledger=ledger,
        tool_name="search_docs",
        arguments={"query": "agent runtime"},
        visible_names={"search_docs", "fetch_doc_chunk"},
    )
    first_fetch = policy.evaluate_call(
        intent="doc_qa_with_evidence",
        ledger=ledger,
        tool_name="fetch_doc_chunk",
        arguments={"chunk_id": "c1"},
        visible_names={"search_docs", "fetch_doc_chunk"},
    )

    assert first_search == ToolBoundaryDecision(action="allow", reason="within_budget")
    assert first_fetch == ToolBoundaryDecision(action="allow", reason="within_budget")
```

- [ ] **Step 2: Write failing evidence completion tests**

Add `tests/test_evidence_completion_policy.py`:

```python
from __future__ import annotations

from agent.policies.evidence_completion import EvidenceCompletionPolicy
from agent.policies.tool_ledger import ToolCallLedger, ToolCallRecord


def test_evidence_complete_soft_stops_additional_expansion() -> None:
    ledger = ToolCallLedger()
    ledger.add_record(
        ToolCallRecord(
            tool_name="search_docs",
            tool_class="retrieval",
            args_hash="h1",
            args_summary="{}",
            call_index=1,
            visible_before_call=True,
            result_ok=True,
            hit_count=1,
            result_has_evidence=True,
        )
    )
    ledger.add_record(
        ToolCallRecord(
            tool_name="fetch_doc_chunk",
            tool_class="evidence_expand",
            args_hash="h2",
            args_summary="{}",
            call_index=2,
            visible_before_call=True,
            result_ok=True,
            citation_refs=("my_md/doc.md > Agent Runtime",),
            chunk_keys=("c1",),
            result_has_evidence=True,
            result_has_citation=True,
        )
    )

    decision = EvidenceCompletionPolicy().evaluate_call(
        intent="doc_qa_with_evidence",
        ledger=ledger,
        tool_name="fetch_doc_chunk",
        arguments={"chunk_id": "c2"},
    )

    assert decision.action == "soft_stop"
    assert decision.reason == "document_rag_evidence_complete"


def test_no_hit_retrieval_does_not_soft_stop() -> None:
    ledger = ToolCallLedger()
    ledger.add_record(
        ToolCallRecord(
            tool_name="search_docs",
            tool_class="retrieval",
            args_hash="h1",
            args_summary="{}",
            call_index=1,
            visible_before_call=True,
            result_ok=True,
            hit_count=0,
        )
    )

    decision = EvidenceCompletionPolicy().evaluate_call(
        intent="doc_qa_with_evidence",
        ledger=ledger,
        tool_name="fetch_doc_chunk",
        arguments={"chunk_id": "c1"},
    )

    assert decision.action == "allow"
    assert decision.reason == "evidence_not_complete"


def test_chunk_without_citation_does_not_soft_stop() -> None:
    ledger = ToolCallLedger()
    ledger.add_record(
        ToolCallRecord(
            tool_name="search_docs",
            tool_class="retrieval",
            args_hash="h1",
            args_summary="{}",
            call_index=1,
            visible_before_call=True,
            result_ok=True,
            hit_count=1,
            result_has_evidence=True,
        )
    )
    ledger.add_record(
        ToolCallRecord(
            tool_name="fetch_doc_chunk",
            tool_class="evidence_expand",
            args_hash="h2",
            args_summary="{}",
            call_index=2,
            visible_before_call=True,
            result_ok=True,
            result_has_evidence=True,
            result_has_citation=False,
        )
    )

    decision = EvidenceCompletionPolicy().evaluate_call(
        intent="doc_qa_with_evidence",
        ledger=ledger,
        tool_name="fetch_doc_chunk",
        arguments={"chunk_id": "c2"},
    )

    assert decision.action == "allow"
    assert decision.reason == "evidence_not_complete"


def test_broader_exploration_intent_does_not_soft_stop() -> None:
    ledger = ToolCallLedger()
    ledger.add_record(
        ToolCallRecord(
            tool_name="search_docs",
            tool_class="retrieval",
            args_hash="h1",
            args_summary="{}",
            call_index=1,
            visible_before_call=True,
            result_ok=True,
            hit_count=1,
            result_has_evidence=True,
            result_has_citation=True,
        )
    )

    decision = EvidenceCompletionPolicy().evaluate_call(
        intent="open_exploration",
        ledger=ledger,
        tool_name="fetch_doc_chunk",
        arguments={"chunk_id": "c2"},
    )

    assert decision.action == "allow"
    assert decision.reason == "non_doc_evidence_intent"
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_tool_budget_policy.py tests/test_evidence_completion_policy.py -q
```

Expected: FAIL with missing modules.

- [ ] **Step 4: Implement `tool_budget.py`**

Create `agent/policies/tool_budget.py`:

```python
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from agent.policies.doc_rag_intent import decide_doc_rag_preload
from agent.policies.tool_ledger import (
    ToolCallLedger,
    ToolClass,
    classify_tool_name,
    stable_args_hash,
)

TaskIntent = Literal[
    "doc_qa_simple",
    "doc_qa_with_evidence",
    "memory_qa",
    "code_inspection",
    "no_tool",
    "open_exploration",
]
ToolBoundaryAction = Literal["allow", "warn", "soft_stop", "require_reason", "block"]


@dataclass(frozen=True)
class ToolBoundaryDecision:
    action: ToolBoundaryAction
    reason: str
    model_hint: str | None = None
    user_visible_message: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BudgetProfile:
    class_max_calls: Mapping[ToolClass, int]


_DOC_SIMPLE_PROFILE = BudgetProfile(
    class_max_calls={"retrieval": 1, "evidence_expand": 1}
)
_DOC_EVIDENCE_PROFILE = BudgetProfile(
    class_max_calls={"retrieval": 1, "evidence_expand": 2}
)


class ToolBudgetPolicy:
    def evaluate_call(
        self,
        *,
        intent: TaskIntent,
        ledger: ToolCallLedger,
        tool_name: str,
        arguments: Mapping[str, Any],
        visible_names: set[str] | None,
    ) -> ToolBoundaryDecision:
        if (
            tool_name == "tool_search"
            and visible_names is not None
            and _select_targets(arguments) <= visible_names
            and _select_targets(arguments)
        ):
            return ToolBoundaryDecision(
                action="soft_stop",
                reason="redundant_visible_tool_search",
                model_hint=(
                    "The requested tools are already visible in this turn. "
                    "Use the visible tool directly or answer from existing evidence."
                ),
                metadata={"requested_tools": sorted(_select_targets(arguments))},
            )

        profile = _profile_for_intent(intent)
        if profile is None:
            return ToolBoundaryDecision(action="allow", reason="no_budget_profile")

        tool_class = classify_tool_name(tool_name)
        max_calls = profile.class_max_calls.get(tool_class)
        if max_calls is None:
            return ToolBoundaryDecision(action="allow", reason="within_budget")

        if ledger.count_class(tool_class) >= max_calls:
            reason = (
                "retrieval_budget_exceeded"
                if tool_class == "retrieval"
                else "evidence_expand_budget_exceeded"
            )
            return ToolBoundaryDecision(
                action="soft_stop",
                reason=reason,
                model_hint="Current turn tool budget is enough; answer from existing evidence.",
                metadata={
                    "tool_class": tool_class,
                    "max_calls": max_calls,
                    "current_calls": ledger.count_class(tool_class),
                },
            )

        args_hash = stable_args_hash(arguments)
        if ledger.same_args_count(tool_name, args_hash) > 0:
            return ToolBoundaryDecision(
                action="soft_stop",
                reason="repeated_same_args",
                model_hint="This repeats a previous tool call; answer from existing evidence.",
                metadata={"tool_name": tool_name},
            )

        return ToolBoundaryDecision(action="allow", reason="within_budget")


def infer_task_intent(user_text: str) -> TaskIntent:
    text = user_text or ""
    if "不用工具" in text or "不要调用工具" in text:
        return "no_tool"
    doc_decision = decide_doc_rag_preload(text)
    if doc_decision.preload_search_docs and doc_decision.preload_fetch_doc_chunk:
        return "doc_qa_with_evidence"
    if doc_decision.preload_search_docs:
        return "doc_qa_simple"
    if "记忆" in text or "session" in text or "会话" in text:
        return "memory_qa"
    if "源码" in text or "读取" in text or ".py" in text:
        return "code_inspection"
    return "open_exploration"


def _profile_for_intent(intent: TaskIntent) -> BudgetProfile | None:
    if intent == "doc_qa_simple":
        return _DOC_SIMPLE_PROFILE
    if intent == "doc_qa_with_evidence":
        return _DOC_EVIDENCE_PROFILE
    return None


def _select_targets(arguments: Mapping[str, Any]) -> set[str]:
    query = str(arguments.get("query") or "")
    if not query.startswith("select:"):
        return set()
    raw = query.removeprefix("select:")
    return {item.strip() for item in raw.split(",") if item.strip()}
```

- [ ] **Step 5: Implement `evidence_completion.py`**

Create `agent/policies/evidence_completion.py`:

```python
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from agent.policies.tool_budget import TaskIntent, ToolBoundaryDecision
from agent.policies.tool_ledger import ToolCallLedger, classify_tool_name


class EvidenceCompletionPolicy:
    def evaluate_call(
        self,
        *,
        intent: TaskIntent,
        ledger: ToolCallLedger,
        tool_name: str,
        arguments: Mapping[str, Any],
    ) -> ToolBoundaryDecision:
        if intent != "doc_qa_with_evidence":
            return ToolBoundaryDecision(action="allow", reason="non_doc_evidence_intent")

        tool_class = classify_tool_name(tool_name)
        if tool_class not in {"retrieval", "evidence_expand"}:
            return ToolBoundaryDecision(action="allow", reason="not_evidence_tool")

        if ledger.has_successful_retrieval() and ledger.has_citation_evidence():
            return ToolBoundaryDecision(
                action="soft_stop",
                reason="document_rag_evidence_complete",
                model_hint=(
                    "Document RAG already has retrieval hits and citation-bearing "
                    "chunk evidence. Answer now with existing citations."
                ),
            )

        return ToolBoundaryDecision(action="allow", reason="evidence_not_complete")
```

- [ ] **Step 6: Run policy tests**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_tool_budget_policy.py tests/test_evidence_completion_policy.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit Task 2**

Run:

```bash
git add agent/policies/tool_budget.py agent/policies/evidence_completion.py tests/test_tool_budget_policy.py tests/test_evidence_completion_policy.py my_md/rag/21-document-rag-p10a2-implementation-plan.md
git commit -m "Add turn-local tool budget policies"
```

---

### Task 3: Turn Tool Boundary Manager Facade

**Files:**
- Create: `agent/policies/tool_boundary.py`
- Test: `tests/test_tool_boundary_manager.py`

**Interfaces:**
- Consumes:
  - `ToolAccessContext`, `ToolAccessGateway`, `ToolAccessPlan`
  - `ToolBudgetPolicy`, `EvidenceCompletionPolicy`, `ToolBoundaryDecision`
  - `ToolCallLedger`, `ToolCallRecord`, `extract_tool_result_facts`
- Produces:
  - `ToolBoundaryContext`
  - `BoundaryExecutionDecision`
  - `TurnToolBoundaryManager.build_context(...)`
  - `TurnToolBoundaryManager.compute_visible_names(...)`
  - `TurnToolBoundaryManager.filter_tool_search_matches(...)`
  - `TurnToolBoundaryManager.merge_tool_search_unlocks(...)`
  - `TurnToolBoundaryManager.evaluate_tool_call(...)`
  - `TurnToolBoundaryManager.record_tool_result(...)`
  - `TurnToolBoundaryManager.consume_pending_hint(context: ToolBoundaryContext) -> str | None`
  - `TurnToolBoundaryManager.trace() -> dict[str, object]`

- [ ] **Step 1: Write failing manager tests**

Add `tests/test_tool_boundary_manager.py`:

```python
from __future__ import annotations

import json

from agent.policies.tool_access import ToolAccessContext
from agent.policies.tool_boundary import TurnToolBoundaryManager


def _ctx(text: str) -> ToolAccessContext:
    return ToolAccessContext(
        session_key="cli:1",
        user_text=text,
        always_on_tools=frozenset({"tool_search", "read_file", "shell", "list_dir"}),
        lru_preloaded_tools=frozenset(),
        disabled_tools=frozenset(),
    )


def test_manager_preserves_doc_rag_access_behavior() -> None:
    manager = TurnToolBoundaryManager()
    ctx = manager.build_context(_ctx("根据项目文档回答agent runtime负责什么，并展开原文证据"))

    visible = manager.compute_visible_names(ctx)

    assert {"search_docs", "fetch_doc_chunk", "tool_search"} <= visible
    assert visible.isdisjoint({"read_file", "shell", "list_dir"})
    assert ctx.intent == "doc_qa_with_evidence"


def test_core_access_block_wins_before_budget() -> None:
    manager = TurnToolBoundaryManager()
    ctx = manager.build_context(_ctx("根据项目文档回答agent runtime负责什么，并展开原文证据"))

    decision = manager.evaluate_tool_call(
        ctx,
        tool_name="read_file",
        arguments={"path": "README.md"},
        visible_names={"search_docs", "fetch_doc_chunk"},
    )

    assert decision.action == "block"
    assert decision.reason == "tool_blocked_by_doc_rag_policy"
    assert decision.execute is False


def test_redundant_visible_tool_search_soft_stops_without_execution() -> None:
    manager = TurnToolBoundaryManager()
    ctx = manager.build_context(_ctx("根据项目文档回答agent runtime负责什么，并展开原文证据"))

    decision = manager.evaluate_tool_call(
        ctx,
        tool_name="tool_search",
        arguments={"query": "select:search_docs,fetch_doc_chunk"},
        visible_names={"tool_search", "search_docs", "fetch_doc_chunk"},
    )

    assert decision.action == "soft_stop"
    assert decision.execute is False
    assert json.loads(decision.result_payload or "{}")["error_code"] == "tool_boundary_soft_stop"
    assert manager.consume_pending_hint(ctx)
    assert manager.consume_pending_hint(ctx) is None


def test_recorded_evidence_causes_next_fetch_soft_stop() -> None:
    manager = TurnToolBoundaryManager()
    ctx = manager.build_context(_ctx("根据项目文档回答agent runtime负责什么，并展开原文证据"))
    manager.record_tool_result(
        ctx,
        tool_name="search_docs",
        arguments={"query": "agent runtime"},
        result_text=json.dumps(
            {
                "ok": True,
                "hit_count": 1,
                "hits": [{"chunk_id": "c1", "citation": "my_md/doc.md > Agent Runtime"}],
            }
        ),
        visible_before_call=True,
        decision_action="allow",
        decision_reason="within_budget",
    )
    manager.record_tool_result(
        ctx,
        tool_name="fetch_doc_chunk",
        arguments={"chunk_id": "c1"},
        result_text=json.dumps(
            {
                "ok": True,
                "chunk": {
                    "chunk_id": "c1",
                    "citation": "my_md/doc.md > Agent Runtime",
                    "text": "Agent runtime 负责管理 agent 的一次运行过程。",
                },
            }
        ),
        visible_before_call=True,
        decision_action="allow",
        decision_reason="within_budget",
    )

    decision = manager.evaluate_tool_call(
        ctx,
        tool_name="fetch_doc_chunk",
        arguments={"chunk_id": "c2"},
        visible_names={"search_docs", "fetch_doc_chunk"},
    )

    assert decision.action == "soft_stop"
    assert decision.reason == "document_rag_evidence_complete"
    assert decision.execute is False


def test_trace_contains_decisions_and_ledger_summary() -> None:
    manager = TurnToolBoundaryManager()
    ctx = manager.build_context(_ctx("根据项目文档回答agent runtime负责什么，并展开原文证据"))
    manager.evaluate_tool_call(
        ctx,
        tool_name="tool_search",
        arguments={"query": "select:search_docs,fetch_doc_chunk"},
        visible_names={"tool_search", "search_docs", "fetch_doc_chunk"},
    )

    trace = manager.trace(ctx)

    assert trace["intent"] == "doc_qa_with_evidence"
    assert trace["decisions"][0]["action"] == "soft_stop"
    assert trace["ledger_summary"]["tool_calls"] == 0
```

- [ ] **Step 2: Run manager tests to verify failure**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_tool_boundary_manager.py -q
```

Expected: FAIL with missing `agent.policies.tool_boundary`.

- [ ] **Step 3: Implement `tool_boundary.py`**

Create `agent/policies/tool_boundary.py`:

```python
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from agent.policies.evidence_completion import EvidenceCompletionPolicy
from agent.policies.tool_access import (
    ToolAccessContext,
    ToolAccessGateway,
    ToolAccessPlan,
)
from agent.policies.tool_budget import (
    TaskIntent,
    ToolBoundaryDecision,
    ToolBudgetPolicy,
    infer_task_intent,
)
from agent.policies.tool_ledger import (
    ToolCallLedger,
    ToolCallRecord,
    classify_tool_name,
    extract_tool_result_facts,
    stable_args_hash,
    summarize_args,
)


@dataclass
class ToolBoundaryContext:
    access_context: ToolAccessContext
    access_plan: ToolAccessPlan
    intent: TaskIntent
    ledger: ToolCallLedger = field(default_factory=ToolCallLedger)
    pending_hints: list[str] = field(default_factory=list)
    decisions: list[dict[str, object]] = field(default_factory=list)


@dataclass(frozen=True)
class BoundaryExecutionDecision:
    action: str
    reason: str
    execute: bool
    result_payload: str | None = None
    model_hint: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


class TurnToolBoundaryManager:
    def __init__(
        self,
        *,
        access_gateway: ToolAccessGateway | None = None,
        budget_policy: ToolBudgetPolicy | None = None,
        evidence_policy: EvidenceCompletionPolicy | None = None,
    ) -> None:
        self._access = access_gateway or ToolAccessGateway()
        self._budget = budget_policy or ToolBudgetPolicy()
        self._evidence = evidence_policy or EvidenceCompletionPolicy()

    def build_context(self, access_context: ToolAccessContext) -> ToolBoundaryContext:
        access_plan = self._access.build_plan(access_context)
        return ToolBoundaryContext(
            access_context=access_context,
            access_plan=access_plan,
            intent=infer_task_intent(access_context.user_text),
        )

    def compute_visible_names(self, context: ToolBoundaryContext) -> set[str]:
        return self._access.compute_visible_names(
            context.access_context,
            context.access_plan,
        )

    def filter_tool_search_matches(
        self,
        context: ToolBoundaryContext,
        tool_search_payload: str,
    ) -> tuple[str, tuple[str, ...]]:
        return self._access.filter_tool_search_matches(
            context.access_plan,
            tool_search_payload,
        )

    def merge_tool_search_unlocks(
        self,
        *,
        context: ToolBoundaryContext,
        current_visible: set[str],
        unlocked: set[str],
    ) -> set[str]:
        return self._access.merge_tool_search_unlocks(
            current_visible=current_visible,
            unlocked=unlocked,
            context=context.access_context,
            plan=context.access_plan,
        )

    def observe_access_tool_result(
        self,
        context: ToolBoundaryContext,
        tool_name: str,
        result_text: str,
    ) -> None:
        context.access_plan = self._access.observe_tool_result(
            context.access_plan,
            tool_name,
            result_text,
        )

    def evaluate_tool_call(
        self,
        context: ToolBoundaryContext,
        *,
        tool_name: str,
        arguments: Mapping[str, Any],
        visible_names: set[str] | None,
    ) -> BoundaryExecutionDecision:
        gate = self._access.check_tool_call(context.access_plan, tool_name, dict(arguments))
        if not gate.allowed:
            decision = BoundaryExecutionDecision(
                action="block",
                reason=gate.error_code or gate.reason or "tool_access_block",
                execute=False,
                result_payload=json.dumps(
                    {
                        "ok": False,
                        "error_code": gate.error_code,
                        "message": gate.message,
                        "recommended_tools": list(gate.recommended_tools),
                        "fallback_allowed": False,
                    },
                    ensure_ascii=False,
                ),
                metadata={"recommended_tools": list(gate.recommended_tools)},
            )
            self._record_decision(context, tool_name, decision)
            return decision

        evidence_decision = self._evidence.evaluate_call(
            intent=context.intent,
            ledger=context.ledger,
            tool_name=tool_name,
            arguments=arguments,
        )
        budget_decision = self._budget.evaluate_call(
            intent=context.intent,
            ledger=context.ledger,
            tool_name=tool_name,
            arguments=arguments,
            visible_names=visible_names,
        )
        final = _more_restrictive(evidence_decision, budget_decision)
        if final.action == "soft_stop":
            payload = _soft_stop_payload(final)
            if final.model_hint:
                context.pending_hints.append(final.model_hint)
            decision = BoundaryExecutionDecision(
                action="soft_stop",
                reason=final.reason,
                execute=False,
                result_payload=payload,
                model_hint=final.model_hint,
                metadata=dict(final.metadata),
            )
            self._record_decision(context, tool_name, decision)
            return decision

        decision = BoundaryExecutionDecision(
            action=final.action,
            reason=final.reason,
            execute=True,
            model_hint=final.model_hint,
            metadata=dict(final.metadata),
        )
        self._record_decision(context, tool_name, decision)
        return decision

    def record_tool_result(
        self,
        context: ToolBoundaryContext,
        *,
        tool_name: str,
        arguments: Mapping[str, Any],
        result_text: str,
        visible_before_call: bool,
        decision_action: str,
        decision_reason: str,
        requested_unlocks: tuple[str, ...] = (),
        unlocked_tools: tuple[str, ...] = (),
        blocked_tools: tuple[str, ...] = (),
    ) -> None:
        facts = extract_tool_result_facts(tool_name, result_text)
        context.ledger.add_record(
            ToolCallRecord(
                tool_name=tool_name,
                tool_class=classify_tool_name(tool_name),
                args_hash=stable_args_hash(arguments),
                args_summary=summarize_args(arguments),
                call_index=context.ledger.next_call_index(),
                visible_before_call=visible_before_call,
                decision_action=decision_action,
                decision_reason=decision_reason,
                requested_unlocks=requested_unlocks,
                unlocked_tools=unlocked_tools,
                blocked_tools=blocked_tools,
                result_ok=facts.result_ok,
                hit_count=facts.hit_count,
                citation_refs=facts.citation_refs,
                chunk_keys=facts.chunk_keys,
                terminal_scope=facts.terminal_scope,
                result_summary=result_text[:240],
                result_has_evidence=facts.result_has_evidence,
                result_has_citation=facts.result_has_citation,
                result_error_code=facts.result_error_code,
            )
        )

    def consume_pending_hint(self, context: ToolBoundaryContext) -> str | None:
        if not context.pending_hints:
            return None
        return context.pending_hints.pop(0)

    def trace(self, context: ToolBoundaryContext) -> dict[str, object]:
        return {
            "intent": context.intent,
            "tool_access": {
                "reason": context.access_plan.reason,
                "policies": list(context.access_plan.policies),
                "visible_add": sorted(context.access_plan.visible_add),
                "visible_suppress": sorted(context.access_plan.visible_suppress),
                "tool_search_block": sorted(context.access_plan.tool_search_block),
                "execution_block": sorted(context.access_plan.execution_block),
                "matched_terms": list(context.access_plan.matched_terms),
                "filter_error": context.access_plan.filter_error,
            },
            "decisions": list(context.decisions),
            "ledger_summary": context.ledger.summary(),
        }

    def _record_decision(
        self,
        context: ToolBoundaryContext,
        tool_name: str,
        decision: BoundaryExecutionDecision,
    ) -> None:
        context.decisions.append(
            {
                "tool": tool_name,
                "action": decision.action,
                "reason": decision.reason,
                "execute": decision.execute,
                "metadata": dict(decision.metadata),
            }
        )


def _soft_stop_payload(decision: ToolBoundaryDecision) -> str:
    return json.dumps(
        {
            "ok": False,
            "error_code": "tool_boundary_soft_stop",
            "terminal_scope": "current_turn_tool_budget",
            "fallback_allowed": False,
            "recommended_action": "answer_from_existing_evidence",
            "message": decision.model_hint
            or "Current turn already has enough evidence; answer from existing evidence.",
            "reason": decision.reason,
        },
        ensure_ascii=False,
    )


_ACTION_RANK = {
    "allow": 0,
    "warn": 1,
    "require_reason": 2,
    "soft_stop": 3,
    "block": 4,
}


def _more_restrictive(
    left: ToolBoundaryDecision,
    right: ToolBoundaryDecision,
) -> ToolBoundaryDecision:
    if _ACTION_RANK[right.action] > _ACTION_RANK[left.action]:
        return right
    return left
```

- [ ] **Step 4: Run manager tests**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_tool_boundary_manager.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add agent/policies/tool_boundary.py tests/test_tool_boundary_manager.py my_md/rag/21-document-rag-p10a2-implementation-plan.md
git commit -m "Add turn tool boundary manager"
```

---

### Task 4: Reasoner Integration

**Files:**
- Modify: `agent/core/passive_turn.py`
- Test: `tests/test_tool_boundary_reasoner.py`
- Modify: existing `tests/test_tool_access_gateway_reasoner.py` only if assertions need metadata key updates.

**Interfaces:**
- Consumes:
  - `TurnToolBoundaryManager`
  - `ToolBoundaryContext`
  - `BoundaryExecutionDecision`
- Produces:
  - `result.context_retry["tool_boundary"]`
  - `result.metadata["tool_boundary"]` through `_build_result` if practical; otherwise `context_retry` is required for this iteration.

- [ ] **Step 1: Write failing reasoner tests**

Add `tests/test_tool_boundary_reasoner.py`:

```python
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, cast

from agent.core.passive_turn import DefaultReasoner
from agent.core.runtime_support import LLMServices, ToolDiscoveryState
from agent.core.types import ContextRenderResult, ContextRequest
from agent.looping.ports import LLMConfig
from agent.provider import LLMResponse, ToolCall
from agent.tools.base import Tool
from agent.tools.registry import ToolRegistry
from agent.tools.tool_search import ToolSearchTool


class _RecordingTool(Tool):
    def __init__(self, name: str, result: str | None = None) -> None:
        self._name = name
        self._result = result or json.dumps({"ok": True})
        self.calls: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._name

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return self._result


class _Provider:
    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def chat(self, **kwargs: Any) -> LLMResponse:
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("provider.chat called more than expected")
        return self._responses.pop(0)


def _msg(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=content,
        media=[],
        channel="cli",
        chat_id="1",
        timestamp=datetime.now(timezone.utc),
    )


def _session() -> SimpleNamespace:
    return SimpleNamespace(
        key="cli:1",
        messages=[],
        metadata={},
        get_history=lambda max_messages=40, *, start_index=None: [],
        last_consolidated=0,
    )


def _make_reasoner(
    provider: _Provider,
    *,
    search_docs: _RecordingTool | None = None,
    fetch_doc_chunk: _RecordingTool | None = None,
) -> DefaultReasoner:
    tools = ToolRegistry()
    tools.register(ToolSearchTool(tools), always_on=True, risk="read-only")
    tools.register(search_docs or _RecordingTool("search_docs"))
    tools.register(fetch_doc_chunk or _RecordingTool("fetch_doc_chunk"))
    tools.register(_RecordingTool("read_file"), always_on=True)
    tools.register(_RecordingTool("shell"), always_on=True)
    tools.register(_RecordingTool("list_dir"), always_on=True)

    def _render(request: ContextRequest, **_kwargs: object) -> ContextRenderResult:
        return ContextRenderResult(
            system_prompt="",
            turn_injection_context={"turn_injection": request.turn_injection_prompt or ""},
            messages=[{"role": "user", "content": request.current_message}],
            debug_breakdown=[],
        )

    return DefaultReasoner(
        llm=cast(Any, LLMServices(provider=provider, light_provider=provider)),
        llm_config=LLMConfig(model="m", max_iterations=6, max_tokens=256),
        tools=tools,
        discovery=ToolDiscoveryState(),
        tool_search_enabled=True,
        memory_window=10,
        context=cast(Any, SimpleNamespace(render=_render)),
        session_manager=cast(Any, SimpleNamespace(save_async=lambda *_args, **_kw: None)),
    )


def test_redundant_visible_tool_search_soft_stop_does_not_execute_tool_search() -> None:
    provider = _Provider(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCall(
                        "s1",
                        "tool_search",
                        {"query": "select:search_docs,fetch_doc_chunk"},
                    )
                ],
            ),
            LLMResponse(content="final", tool_calls=[]),
        ]
    )
    reasoner = _make_reasoner(provider)

    result = asyncio.run(
        reasoner.run_turn(
            msg=_msg("根据项目文档回答agent runtime负责什么，并展开原文证据"),
            session=cast(Any, _session()),
        )
    )

    tool_messages = [m for m in provider.calls[1]["messages"] if m.get("role") == "tool"]
    payload = json.loads(tool_messages[-1]["content"])
    assert payload["error_code"] == "tool_boundary_soft_stop"
    assert result.tools_used == []
    assert result.tool_chain[0]["calls"][0]["status"] == "soft_stopped_by_tool_boundary"
    assert result.context_retry["tool_boundary"]["decisions"][0]["reason"] == "redundant_visible_tool_search"


def test_repeated_fetch_soft_stop_after_citation_evidence() -> None:
    search_docs = _RecordingTool(
        "search_docs",
        json.dumps(
            {
                "ok": True,
                "hit_count": 1,
                "hits": [{"chunk_id": "c1", "citation": "my_md/doc.md > Agent Runtime"}],
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
                    "text": "Agent runtime 负责管理 agent 的一次运行过程。",
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
            LLMResponse(
                content="",
                tool_calls=[ToolCall("f2", "fetch_doc_chunk", {"chunk_id": "c2"})],
            ),
            LLMResponse(content="final", tool_calls=[]),
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

    assert len(search_docs.calls) == 1
    assert len(fetch_doc_chunk.calls) == 1
    assert result.tools_used == ["search_docs", "fetch_doc_chunk"]
    assert result.tool_chain[2]["calls"][0]["status"] == "soft_stopped_by_tool_boundary"
    assert result.context_retry["tool_boundary"]["ledger_summary"]["has_citation_evidence"] is True
```

- [ ] **Step 2: Run reasoner tests to verify failure**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_tool_boundary_reasoner.py -q
```

Expected: FAIL because `DefaultReasoner` still uses `ToolAccessGateway` directly and has no soft-stop handling.

- [ ] **Step 3: Replace direct gateway construction**

In `agent/core/passive_turn.py`, change imports near the top from:

```python
from agent.policies.tool_access import (
    ToolAccessContext,
    ToolAccessGateway,
    ToolAccessPlan,
)
```

to:

```python
from agent.policies.tool_access import ToolAccessContext
from agent.policies.tool_boundary import ToolBoundaryContext, TurnToolBoundaryManager
```

Then change `DefaultReasoner.__init__` from:

```python
self._tool_access_gateway = ToolAccessGateway()
```

to:

```python
self._tool_boundary = TurnToolBoundaryManager()
```

- [ ] **Step 4: Build boundary context in `run_turn`**

In `DefaultReasoner.run_turn`, replace:

```python
tool_access_context: ToolAccessContext | None = None
tool_access_plan: ToolAccessPlan | None = None
visible_names: set[str] | None = None
```

with:

```python
tool_access_context: ToolAccessContext | None = None
tool_boundary_context: ToolBoundaryContext | None = None
visible_names: set[str] | None = None
```

Replace the current `tool_access_plan = ...` block with:

```python
tool_boundary_context = self._tool_boundary.build_context(tool_access_context)
visible_names = self._tool_boundary.compute_visible_names(tool_boundary_context)
retry_trace["tool_boundary"] = self._tool_boundary.trace(tool_boundary_context)
retry_trace["tool_access"] = retry_trace["tool_boundary"]["tool_access"]
logger.info(
    "[tool_boundary] intent=%s access_reason=%s add=%s suppress=%s",
    tool_boundary_context.intent,
    tool_boundary_context.access_plan.reason,
    ",".join(sorted(tool_boundary_context.access_plan.visible_add)) or "-",
    ",".join(sorted(tool_boundary_context.access_plan.visible_suppress)) or "-",
)
```

When calling `self.run(...)`, replace `tool_access_plan=tool_access_plan` with:

```python
tool_boundary_context=tool_boundary_context
```

- [ ] **Step 5: Update `run` signature**

In `DefaultReasoner.run`, replace:

```python
tool_access_context: ToolAccessContext | None = None,
tool_access_plan: ToolAccessPlan | None = None,
```

with:

```python
tool_boundary_context: ToolBoundaryContext | None = None,
```

- [ ] **Step 6: Add pending hint injection before each LLM call**

Inside the ReAct loop, after `step_ctx.early_stop` handling and before `react_input_samples.append(...)`, insert:

```python
if tool_boundary_context is not None:
    boundary_hint = self._tool_boundary.consume_pending_hint(tool_boundary_context)
    if boundary_hint:
        messages.append(
            support.build_context_hint_message(
                "tool_boundary",
                boundary_hint,
            )
        )
```

- [ ] **Step 7: Replace access gate with boundary decision**

Replace the block:

```python
if tool_access_plan is not None:
    gate = self._tool_access_gateway.check_tool_call(...)
    if not gate.allowed:
        ...
        status="blocked_by_tool_access_gateway"
```

with:

```python
boundary_decision = None
if tool_boundary_context is not None:
    boundary_decision = self._tool_boundary.evaluate_tool_call(
        tool_boundary_context,
        tool_name=tool_call.name,
        arguments=tool_call.arguments,
        visible_names=visible_names,
    )
    if not boundary_decision.execute:
        result = boundary_decision.result_payload or ""
        append_tool_result(
            messages,
            tool_call_id=tool_call.id,
            content=result,
            tool_name=tool_call.name,
        )
        status = (
            "blocked_by_tool_boundary"
            if boundary_decision.action == "block"
            else "soft_stopped_by_tool_boundary"
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
            status=status,
            result_preview=support.log_preview(result),
        )
        iter_calls.append(
            {
                "call_id": tool_call.id,
                "name": tool_call.name,
                "status": status,
                "arguments": tool_call.arguments,
                "boundary_action": boundary_decision.action,
                "boundary_reason": boundary_decision.reason,
                "result": result,
            }
        )
        continue
```

This preserves the requirement that `soft_stop` does not execute the target tool and does not append to `tools_used`.

- [ ] **Step 8: Replace tool_search filter and unlock merge calls**

Replace:

```python
if exec_result.status == "success" and tool_call.name == "tool_search" and tool_access_plan is not None:
    result, tool_search_blocked = self._tool_access_gateway.filter_tool_search_matches(...)
```

with:

```python
if exec_result.status == "success" and tool_call.name == "tool_search" and tool_boundary_context is not None:
    result, tool_search_blocked = self._tool_boundary.filter_tool_search_matches(
        tool_boundary_context,
        str(result),
    )
```

Replace unlock merge with:

```python
if tool_boundary_context is not None:
    visible_names = self._tool_boundary.merge_tool_search_unlocks(
        context=tool_boundary_context,
        current_visible=visible_names,
        unlocked=_newly_unlocked,
    )
```

- [ ] **Step 9: Record successful tool results in ledger**

After `append_tool_result(...)` for a real executed tool and before `tool_search` unlock handling, add:

```python
if tool_boundary_context is not None:
    self._tool_boundary.record_tool_result(
        tool_boundary_context,
        tool_name=tool_call.name,
        arguments=exec_result.final_arguments,
        result_text=str(result),
        visible_before_call=(
            initial_visible_names is None
            or tool_call.name in (visible_names or set())
        ),
        decision_action=boundary_decision.action if boundary_decision else "allow",
        decision_reason=boundary_decision.reason if boundary_decision else "within_budget",
        blocked_tools=tuple(tool_search_blocked),
    )
```

If `visible_before_call` is inaccurate because `visible_names` changed after execution, compute it before execution:

```python
visible_before_call = visible_names is None or tool_call.name in visible_names
```

and pass that local variable into `record_tool_result`.

- [ ] **Step 10: Replace observe access result update**

Replace:

```python
updated_plan = self._tool_access_gateway.observe_tool_result(...)
...
visible_names |= set(tool_access_plan.visible_add)
visible_names -= set(tool_access_context.disabled_tools)
visible_names -= set(tool_access_plan.visible_suppress)
```

with:

```python
if tool_boundary_context is not None and exec_result.status == "success":
    old_plan = tool_boundary_context.access_plan
    self._tool_boundary.observe_access_tool_result(
        tool_boundary_context,
        tool_call.name,
        str(result),
    )
    if tool_boundary_context.access_plan != old_plan and visible_names is not None:
        visible_names |= set(tool_boundary_context.access_plan.visible_add)
        visible_names -= set(tool_boundary_context.access_context.disabled_tools)
        visible_names -= set(tool_boundary_context.access_plan.visible_suppress)
```

- [ ] **Step 11: Add boundary trace to result metadata**

In every call to `_build_result(...)` inside `run`, pass:

```python
tool_boundary_trace=(
    self._tool_boundary.trace(tool_boundary_context)
    if tool_boundary_context is not None
    else None
),
```

If `_build_result` does not accept this argument, extend its signature and set:

```python
if tool_boundary_trace is not None:
    metadata["tool_boundary"] = tool_boundary_trace
```

Also in `run_turn`, after `result = await self.run(...)`, set:

```python
if result.metadata.get("tool_boundary"):
    retry_trace["tool_boundary"] = result.metadata["tool_boundary"]
```

- [ ] **Step 12: Run reasoner boundary tests**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_tool_boundary_reasoner.py -q
```

Expected: all tests pass.

- [ ] **Step 13: Run existing access and preload regression tests**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_doc_rag_intent.py tests/test_doc_rag_intent_preload.py tests/test_agent_core_p2_reasoner.py tests/test_tool_search.py tests/test_tool_access_gateway.py tests/test_tool_access_gateway_reasoner.py tests/test_tool_boundary_manager.py tests/test_tool_boundary_reasoner.py -q
```

Expected: all tests pass. Existing P10a.1 tests must still pass.

- [ ] **Step 14: Commit Task 4**

Run:

```bash
git add agent/core/passive_turn.py tests/test_tool_boundary_reasoner.py tests/test_tool_access_gateway_reasoner.py my_md/rag/21-document-rag-p10a2-implementation-plan.md
git commit -m "Integrate turn tool boundary manager into reasoner"
```

---

### Task 5: Documentation, Full Verification, And Live-Smoke Instructions

**Files:**
- Modify: `my_md/rag/20-document-rag-p10a2-tool-boundary-design.md`
- Modify: `my_md/rag/21-document-rag-p10a2-implementation-plan.md`
- Modify: `my_md/governance/02-current-issues.md`
- Modify: `my_md/governance/04-fix-roadmap.md`
- Modify: `my_md/governance/06-star-log.md`

**Interfaces:**
- Consumes implementation and test results from Tasks 1-4.
- Produces updated docs that distinguish automated verification from still-pending real CLI/LLM smoke.

- [ ] **Step 1: Run targeted test suite**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_tool_ledger.py \
  tests/test_tool_budget_policy.py \
  tests/test_evidence_completion_policy.py \
  tests/test_tool_boundary_manager.py \
  tests/test_tool_boundary_reasoner.py \
  tests/test_tool_access_gateway.py \
  tests/test_tool_access_gateway_reasoner.py \
  tests/test_doc_rag_intent.py \
  tests/test_doc_rag_intent_preload.py \
  tests/test_tool_search.py \
  -q
```

Expected: all tests pass.

- [ ] **Step 2: Run broader regression suite**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest -q
```

Expected: all tests pass or only known unrelated failures. If failures occur, record exact failing tests and do not claim full-suite pass.

- [ ] **Step 3: Run compile check**

Run:

```bash
python3 -m compileall agent/policies agent/core/passive_turn.py tests/test_tool_ledger.py tests/test_tool_budget_policy.py tests/test_evidence_completion_policy.py tests/test_tool_boundary_manager.py tests/test_tool_boundary_reasoner.py
```

Expected: command exits 0.

- [ ] **Step 4: Update design implementation status**

In `my_md/rag/20-document-rag-p10a2-tool-boundary-design.md`, add a section near the top:

```markdown
## Implementation Status

- Automated implementation: completed on 2026-07-12.
- Implemented modules:
  - `agent/policies/tool_ledger.py`
  - `agent/policies/tool_budget.py`
  - `agent/policies/evidence_completion.py`
  - `agent/policies/tool_boundary.py`
- Reasoner integration: `DefaultReasoner` now routes current-turn tool access, budget, evidence-completion, and trace decisions through `TurnToolBoundaryManager`.
- Verification:
  - targeted pytest: record the exact command from Task 5 Step 1 and its observed pass/fail summary.
  - full pytest: record the exact command from Task 5 Step 2 and its observed pass/fail summary; if it fails, list the exact failing test node ids.
  - compileall: record the exact command from Task 5 Step 3 and whether it exited 0.
- Real CLI/LLM smoke: pending user run.
```

Replace placeholders with real command output summaries from Steps 1-3.

- [ ] **Step 5: Update governance docs**

In `my_md/governance/02-current-issues.md`, under P10a.2, add:

```markdown
- P10a.2 automated implementation completed:
  - added turn-local ledger, budget, evidence completion, and boundary manager modules;
  - integrated `DefaultReasoner` through the boundary facade;
  - `soft_stop` prevents redundant target-tool execution and records boundary metadata;
  - automated verification: record the exact targeted pytest, full pytest, and compileall summaries from Task 5.
- Real CLI/LLM smoke remains pending:
  - repeat turn `361`-style prompt;
  - expected no `shell/read_file/list_dir`;
  - target chain no more than about 4 tool calls.
```

In `my_md/governance/04-fix-roadmap.md`, update 第五阶段 verification with the same automated result and pending live smoke.

In `my_md/governance/06-star-log.md`, add a dated result bullet:

```markdown
- 2026-07-12 P10a.2 automated implementation completed: Turn Tool Boundary Manager now keeps P10a.1 access blocks while adding soft-stop budget/evidence governance. Real CLI/LLM smoke remains pending.
```

- [ ] **Step 6: Add manual live-smoke instructions**

In `my_md/rag/21-document-rag-p10a2-implementation-plan.md`, add:

```markdown
## Manual Live Smoke

Use the real CLI against a Document RAG-enabled agent:

1. Prompt:
   `请重新从文档知识库检索，不要复用上轮内容：根据项目文档回答agent runtime负责什么，并调用原文chunk展开证据，回答必须带引用`
2. Check logs:
   - no `shell/read_file/list_dir`;
   - `tool_boundary` decisions present;
   - redundant `tool_search` or third `fetch_doc_chunk` is `soft_stop` if attempted;
   - target executed tool calls: about 4 or fewer.
3. Check observe:
   - `error=NULL`;
   - CLI remains connected;
   - `tool_boundary.ledger_summary.has_citation_evidence=true` when chunk evidence exists.
```

- [ ] **Step 7: Run docs formatting check**

Run:

```bash
git diff --check
```

Expected: no output, exit 0.

- [ ] **Step 8: Commit Task 5**

Run:

```bash
git add my_md/rag/20-document-rag-p10a2-tool-boundary-design.md my_md/rag/21-document-rag-p10a2-implementation-plan.md my_md/governance/02-current-issues.md my_md/governance/04-fix-roadmap.md my_md/governance/06-star-log.md
git commit -m "Document P10a.2 boundary implementation status"
```

---

## Final Verification Before Push

- [ ] Run:

```bash
git status --short --branch
```

Expected: only intentional tracked changes are present; do not add `my_test_py/`.

- [ ] Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_tool_ledger.py tests/test_tool_budget_policy.py tests/test_evidence_completion_policy.py tests/test_tool_boundary_manager.py tests/test_tool_boundary_reasoner.py -q
```

Expected: all P10a.2 tests pass.

- [ ] Run:

```bash
git log --oneline -5
```

Expected: task commits are visible in order.

- [ ] If the user asks to push, run:

```bash
git push
```

Expected: `main -> main` pushed successfully.

## Implementation Results

- Automated implementation completed on 2026-07-12.
- Implemented modules:
  - `agent/policies/tool_ledger.py`
  - `agent/policies/tool_budget.py`
  - `agent/policies/evidence_completion.py`
  - `agent/policies/tool_boundary.py`
- Reasoner integration:
  - `DefaultReasoner` now uses `TurnToolBoundaryManager` for current-turn access,
    budget, evidence completion, non-executing `soft_stop`, ledger recording,
    tool-search filtering/unlock merging, and `tool_boundary` trace metadata.
- Verification:
  - Targeted suite: `100 passed, 2 warnings in 0.31s`.
  - Full pytest suite: `1361 passed, 3 warnings in 35.12s`.
  - Compile check exited 0.

## Manual Live Smoke

Use the real CLI against a Document RAG-enabled agent:

1. Prompt:
   `请重新从文档知识库检索，不要复用上轮内容：根据项目文档回答agent runtime负责什么，并调用原文chunk展开证据，回答必须带引用`
2. Check logs:
   - no `shell/read_file/list_dir`;
   - `tool_boundary` decisions present;
   - redundant `tool_search` or post-evidence `fetch_doc_chunk` is `soft_stop` if attempted;
   - target executed tool calls: about 4 or fewer.
3. Check observe:
   - `error=NULL`;
   - CLI remains connected;
   - `tool_boundary.ledger_summary.has_citation_evidence=true` when chunk evidence exists.
