# Document RAG P10a.3 Turn Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a turn-local completion boundary so Document RAG evidence-complete `soft_stop` decisions stop the ReAct tool loop and force the next model call to be final-only.

**Architecture:** Keep P10a.2 `TurnToolBoundaryManager` responsible for tool access and execution decisions. Add `TurnCompletionController` as a separate current-turn policy that reads the same `ToolCallLedger`, boundary decisions, and access-plan context, then decides whether to continue ReAct or switch the next LLM call to final-only. `DefaultReasoner.run()` consumes that decision inside the ReAct loop by omitting tool schemas and requiring a final answer from existing evidence; `DefaultReasoner.run_turn()` only propagates the resulting metadata into `TurnRunResult.context_retry`.

**Tech Stack:** Python 3.12, dataclasses, existing `pytest` / `pytest-asyncio`, existing `DefaultReasoner`, existing `ToolCallLedger`, existing observe metadata.

## Global Constraints

- Keep all completion state turn-local.
- Do not write completion policy state into `ToolDiscoveryState` or LRU.
- Do not change always-on tool metadata.
- Do not replace P10a.2 `soft_stop`; consume it as an input signal.
- Do not generate the final answer in Python; final wording remains an LLM response.
- P10a.1 access blocks still win over all budget/completion decisions.
- Final-only mode must omit tool schemas by passing `tools=[]`. Do not change provider behavior or require `tool_choice="none"` unless a provider-specific test proves it is necessary.
- First implementation is conservative and only enables evidence-complete final-only for `doc_qa_with_evidence`.
- No-hit retrieval, chunk without citation, explicit local-source requests, and broader exploration must not final-only early.
- Ordinary agent logs must expose soft-stop and final-only decisions without requiring observe DB inspection.

---

## File Structure

- Create `agent/policies/turn_completion.py`
  - Owns `TurnCompletionAction`, `TurnCompletionDecision`, and `TurnCompletionController`.
  - Reads `TaskIntent`, `ToolCallLedger`, recent boundary decisions, and whether the access plan explicitly allows local-source tools.
  - Does not know about `DefaultReasoner` internals or tool schemas.

- Create `tests/test_turn_completion_policy.py`
  - Unit tests for conservative final-only rules.
  - Negative tests for no-hit, no citation evidence, non-doc intent, and broader exploration intent.

- Modify `agent/policies/tool_boundary.py`
  - Add a small helper to expose boundary decision metadata cleanly.
  - Add an ordinary logger line when `soft_stop` happens.
  - Do not move completion logic into this file.

- Modify `agent/core/passive_turn.py`
  - Instantiate `TurnCompletionController`.
  - Inside `DefaultReasoner.run()`, after boundary `soft_stop`, ask the completion controller whether the next LLM call should be final-only.
  - When final-only is active, append a compact context hint, call the LLM without tools, and return the response directly if it has content.
  - Add completion metadata to `ReasonerResult.metadata`.
  - In `DefaultReasoner.run_turn()`, copy `ReasonerResult.metadata["turn_completion"]` into `retry_trace["turn_completion"]`, matching the existing `tool_boundary` propagation pattern.

- Create `tests/test_turn_completion_reasoner.py`
  - Integration tests proving evidence-complete soft-stop causes final-only and prevents further tool schema exposure.
  - Regression tests proving ordinary P10a.2 soft-stop still records tool_chain facts.
  - Tests that call `run_turn()` must assert `TurnRunResult.context_retry["turn_completion"]`, not `result.metadata`.

- Modify docs after code:
  - `my_md/governance/02-current-issues.md`
  - `my_md/governance/04-fix-roadmap.md`
  - `my_md/governance/06-star-log.md`
  - `my_md/rag/20-document-rag-p10a2-tool-boundary-design.md`
  - `my_md/rag/22-document-rag-p10a3-turn-completion-plan.md`
  - `progress.md`

---

### Task 1: Add Turn Completion Policy

**Files:**
- Create: `agent/policies/turn_completion.py`
- Test: `tests/test_turn_completion_policy.py`

**Interfaces:**
- Consumes:
  - `TaskIntent` from `agent.policies.tool_budget`
  - `ToolCallLedger` from `agent.policies.tool_ledger`
  - boundary decisions as `Sequence[Mapping[str, object]]`, matching `ToolBoundaryContext.decisions`
  - `local_source_allowed: bool`, derived from `ToolAccessPlan.reason == "doc_rag_allows_explicit_local_files"`
- Produces:
  - `TurnCompletionAction = Literal["continue_react", "final_only"]`
  - `TurnCompletionDecision(action: TurnCompletionAction, reason: str, model_hint: str = "", metadata: Mapping[str, object] = field(default_factory=dict))`
  - `TurnCompletionController.evaluate(intent: TaskIntent, ledger: ToolCallLedger, boundary_decisions: Sequence[Mapping[str, object]], local_source_allowed: bool = False) -> TurnCompletionDecision`

- [ ] **Step 1: Write policy tests**

Create `tests/test_turn_completion_policy.py`:

```python
from __future__ import annotations

from agent.policies.tool_budget import TaskIntent
from agent.policies.tool_ledger import ToolCallLedger, ToolCallRecord
from agent.policies.turn_completion import TurnCompletionController


def _record(
    tool_name: str,
    *,
    tool_class: str,
    ok: bool = True,
    hit_count: int | None = None,
    has_citation: bool = False,
) -> ToolCallRecord:
    return ToolCallRecord(
        tool_name=tool_name,
        tool_class=tool_class,  # type: ignore[arg-type]
        args_hash=f"{tool_name}-hash",
        args_summary=f"{tool_name} args",
        call_index=1,
        visible_before_call=True,
        decision_action="allow",
        decision_reason="within_budget",
        result_ok=ok,
        hit_count=hit_count,
        citation_refs=("[doc.md > Heading]",) if has_citation else (),
        chunk_keys=("chunk-1",) if has_citation else (),
        result_has_evidence=ok,
        result_has_citation=has_citation,
    )


def _ledger_with_doc_evidence() -> ToolCallLedger:
    ledger = ToolCallLedger()
    ledger.add_record(
        _record("search_docs", tool_class="retrieval", ok=True, hit_count=3)
    )
    ledger.add_record(
        _record("fetch_doc_chunk", tool_class="evidence_expand", ok=True, has_citation=True)
    )
    return ledger


def test_doc_evidence_complete_soft_stop_switches_to_final_only() -> None:
    decision = TurnCompletionController().evaluate(
        intent="doc_qa_with_evidence",
        ledger=_ledger_with_doc_evidence(),
        local_source_allowed=False,
        boundary_decisions=[
            {
                "tool": "fetch_doc_chunk",
                "action": "soft_stop",
                "reason": "document_rag_evidence_complete",
                "execute": False,
            }
        ],
    )

    assert decision.action == "final_only"
    assert decision.reason == "document_rag_evidence_complete"
    assert "answer from the existing Document RAG evidence" in decision.model_hint
    assert decision.metadata["successful_retrieval"] is True
    assert decision.metadata["citation_evidence"] is True


def test_no_hit_retrieval_does_not_final_only() -> None:
    ledger = ToolCallLedger()
    ledger.add_record(_record("search_docs", tool_class="retrieval", ok=True, hit_count=0))

    decision = TurnCompletionController().evaluate(
        intent="doc_qa_with_evidence",
        ledger=ledger,
        local_source_allowed=False,
        boundary_decisions=[
            {
                "tool": "search_docs",
                "action": "soft_stop",
                "reason": "document_rag_evidence_complete",
                "execute": False,
            }
        ],
    )

    assert decision.action == "continue_react"
    assert decision.reason == "evidence_not_complete"


def test_chunk_without_citation_does_not_final_only() -> None:
    ledger = ToolCallLedger()
    ledger.add_record(
        _record("search_docs", tool_class="retrieval", ok=True, hit_count=2)
    )
    ledger.add_record(
        _record("fetch_doc_chunk", tool_class="evidence_expand", ok=True, has_citation=False)
    )

    decision = TurnCompletionController().evaluate(
        intent="doc_qa_with_evidence",
        ledger=ledger,
        local_source_allowed=False,
        boundary_decisions=[
            {
                "tool": "fetch_doc_chunk",
                "action": "soft_stop",
                "reason": "document_rag_evidence_complete",
                "execute": False,
            }
        ],
    )

    assert decision.action == "continue_react"
    assert decision.reason == "evidence_not_complete"


def test_non_doc_intent_does_not_final_only() -> None:
    decision = TurnCompletionController().evaluate(
        intent="open_exploration",
        ledger=_ledger_with_doc_evidence(),
        local_source_allowed=False,
        boundary_decisions=[
            {
                "tool": "fetch_doc_chunk",
                "action": "soft_stop",
                "reason": "document_rag_evidence_complete",
                "execute": False,
            }
        ],
    )

    assert decision.action == "continue_react"
    assert decision.reason == "non_doc_evidence_intent"


def test_soft_stop_without_evidence_complete_reason_does_not_final_only() -> None:
    decision = TurnCompletionController().evaluate(
        intent="doc_qa_with_evidence",
        ledger=_ledger_with_doc_evidence(),
        local_source_allowed=False,
        boundary_decisions=[
            {
                "tool": "tool_search",
                "action": "soft_stop",
                "reason": "redundant_visible_tool_search",
                "execute": False,
            }
        ],
    )

    assert decision.action == "continue_react"
    assert decision.reason == "completion_signal_absent"


def test_local_source_allowed_does_not_final_only() -> None:
    decision = TurnCompletionController().evaluate(
        intent="doc_qa_with_evidence",
        ledger=_ledger_with_doc_evidence(),
        local_source_allowed=True,
        boundary_decisions=[
            {
                "tool": "fetch_doc_chunk",
                "action": "soft_stop",
                "reason": "document_rag_evidence_complete",
                "execute": False,
            }
        ],
    )

    assert decision.action == "continue_react"
    assert decision.reason == "local_source_allowed"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_turn_completion_policy.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'agent.policies.turn_completion'`.

- [ ] **Step 3: Implement `agent/policies/turn_completion.py`**

Create `agent/policies/turn_completion.py`:

```python
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from agent.policies.tool_budget import TaskIntent
from agent.policies.tool_ledger import ToolCallLedger

TurnCompletionAction = Literal["continue_react", "final_only"]


@dataclass(frozen=True)
class TurnCompletionDecision:
    action: TurnCompletionAction
    reason: str
    model_hint: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)


class TurnCompletionController:
    def evaluate(
        self,
        *,
        intent: TaskIntent,
        ledger: ToolCallLedger,
        boundary_decisions: Sequence[Mapping[str, object]],
        local_source_allowed: bool = False,
    ) -> TurnCompletionDecision:
        if local_source_allowed:
            return TurnCompletionDecision(
                action="continue_react",
                reason="local_source_allowed",
                metadata=self._metadata(ledger, boundary_decisions),
            )

        if intent != "doc_qa_with_evidence":
            return TurnCompletionDecision(
                action="continue_react",
                reason="non_doc_evidence_intent",
                metadata=self._metadata(ledger, boundary_decisions),
            )

        has_signal = any(
            item.get("action") == "soft_stop"
            and item.get("reason") == "document_rag_evidence_complete"
            and item.get("execute") is False
            for item in boundary_decisions
        )
        if not has_signal:
            return TurnCompletionDecision(
                action="continue_react",
                reason="completion_signal_absent",
                metadata=self._metadata(ledger, boundary_decisions),
            )

        if not ledger.has_successful_retrieval() or not ledger.has_citation_evidence():
            return TurnCompletionDecision(
                action="continue_react",
                reason="evidence_not_complete",
                metadata=self._metadata(ledger, boundary_decisions),
            )

        return TurnCompletionDecision(
            action="final_only",
            reason="document_rag_evidence_complete",
            model_hint=(
                "Document RAG evidence is complete for this turn. Do not request "
                "more tools. Answer from the existing Document RAG evidence and "
                "include the available citations."
            ),
            metadata=self._metadata(ledger, boundary_decisions),
        )

    def _metadata(
        self,
        ledger: ToolCallLedger,
        boundary_decisions: Sequence[Mapping[str, object]],
    ) -> dict[str, object]:
        return {
            "successful_retrieval": ledger.has_successful_retrieval(),
            "citation_evidence": ledger.has_citation_evidence(),
            "soft_stop_count": sum(
                1 for item in boundary_decisions if item.get("action") == "soft_stop"
            ),
        }
```

- [ ] **Step 4: Run policy tests**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_turn_completion_policy.py -q
```

Expected: `6 passed`.

- [ ] **Step 5: Commit Task 1**

```bash
git add agent/policies/turn_completion.py tests/test_turn_completion_policy.py
git commit -m "Add turn completion policy"
```

---

### Task 2: Add Boundary Decision Observability Helpers

**Files:**
- Modify: `agent/policies/tool_boundary.py`
- Test: `tests/test_tool_boundary_manager.py`

**Interfaces:**
- Consumes:
  - Existing `ToolBoundaryContext.decisions`
- Produces:
  - `TurnToolBoundaryManager.recent_decisions(context: ToolBoundaryContext) -> tuple[Mapping[str, object], ...]`
  - Ordinary log line for each `soft_stop`

- [ ] **Step 1: Add failing manager test**

Append to `tests/test_tool_boundary_manager.py`:

```python
def test_recent_decisions_exposes_soft_stop_for_completion_controller() -> None:
    manager = TurnToolBoundaryManager()
    context = _context("根据项目文档回答 agent runtime，并展开原文证据")
    visible = {"tool_search", "search_docs", "fetch_doc_chunk"}

    search = manager.evaluate_tool_call(
        context,
        tool_name="search_docs",
        arguments={"query": "agent runtime"},
        visible_names=visible,
    )
    assert search.execute is True
    manager.record_tool_result(
        context,
        tool_name="search_docs",
        arguments={"query": "agent runtime"},
        result_text='{"ok": true, "hit_count": 1, "hits": [{"chunk_id": "c1", "citation": "[doc.md > A]"}]}',
        visible_before_call=True,
        decision_action=search.action,
        decision_reason=search.reason,
    )
    fetch = manager.evaluate_tool_call(
        context,
        tool_name="fetch_doc_chunk",
        arguments={"chunk_id": "c1"},
        visible_names=visible,
    )
    assert fetch.execute is True
    manager.record_tool_result(
        context,
        tool_name="fetch_doc_chunk",
        arguments={"chunk_id": "c1"},
        result_text='{"ok": true, "chunk": {"chunk_id": "c1", "citation": "[doc.md > A]"}}',
        visible_before_call=True,
        decision_action=fetch.action,
        decision_reason=fetch.reason,
    )

    stopped = manager.evaluate_tool_call(
        context,
        tool_name="fetch_doc_chunk",
        arguments={"chunk_id": "c2"},
        visible_names=visible,
    )

    assert stopped.execute is False
    decisions = manager.recent_decisions(context)
    assert decisions[-1]["action"] == "soft_stop"
    assert decisions[-1]["reason"] == "document_rag_evidence_complete"
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_tool_boundary_manager.py::test_recent_decisions_exposes_soft_stop_for_completion_controller -q
```

Expected: fail with `AttributeError: 'TurnToolBoundaryManager' object has no attribute 'recent_decisions'`.

- [ ] **Step 3: Implement helper and soft-stop log**

Modify `agent/policies/tool_boundary.py`:

```python
import logging
```

Add near imports:

```python
logger = logging.getLogger(__name__)
```

Add method inside `TurnToolBoundaryManager`:

```python
    def recent_decisions(
        self,
        context: ToolBoundaryContext,
    ) -> tuple[Mapping[str, object], ...]:
        return tuple(context.decisions)
```

Add this immediately before returning a `soft_stop` `BoundaryExecutionDecision` in `evaluate_tool_call()`:

```python
            logger.info(
                "[tool_boundary] soft_stop tool=%s reason=%s",
                tool_name,
                final.reason,
            )
```

- [ ] **Step 4: Run manager tests**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_tool_boundary_manager.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 2**

```bash
git add agent/policies/tool_boundary.py tests/test_tool_boundary_manager.py
git commit -m "Expose tool boundary decisions for turn completion"
```

---

### Task 3: Integrate Final-Only Mode into DefaultReasoner

**Files:**
- Modify: `agent/core/passive_turn.py`
- Test: `tests/test_turn_completion_reasoner.py`

**Interfaces:**
- Consumes:
  - `TurnCompletionController.evaluate(...)`
  - `TurnCompletionDecision.action == "final_only"`
  - `TurnToolBoundaryManager.recent_decisions(...)`
- Produces:
  - `ReasonerResult.metadata["turn_completion"]`
  - `TurnRunResult.context_retry["turn_completion"]` when using `DefaultReasoner.run_turn()`
  - ordinary log line `[turn_completion] final_only reason=...`
  - final-only LLM call with no tool schemas

- [ ] **Step 1: Write the failing final-only integration test**

Create `tests/test_turn_completion_reasoner.py`:

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
    search_docs: _RecordingTool,
    fetch_doc_chunk: _RecordingTool,
) -> DefaultReasoner:
    tools = ToolRegistry()
    tools.register(ToolSearchTool(tools), always_on=True, risk="read-only")
    tools.register(search_docs)
    tools.register(fetch_doc_chunk)
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


def test_doc_rag_evidence_complete_switches_next_call_to_final_only() -> None:
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
    assert len(search_docs.calls) == 1
    assert len(fetch_doc_chunk.calls) == 1
    assert result.tools_used == ["search_docs", "fetch_doc_chunk"]
    assert result.context_retry["turn_completion"]["action"] == "final_only"
    assert result.context_retry["turn_completion"]["reason"] == "document_rag_evidence_complete"
    assert provider.calls[-1]["tools"] == []
```

- [ ] **Step 2: Confirm the test sequence**

The test must exercise this exact sequence:

1. LLM call 1 returns `search_docs`.
2. LLM call 2 returns `fetch_doc_chunk`.
3. LLM call 3 returns a redundant `fetch_doc_chunk`.
4. Boundary returns `tool_boundary_soft_stop`.
5. Completion controller activates final-only.
6. LLM call 4 receives `tools=[]` and returns final content.

The expected failing assertions before implementation are:

```python
assert result.context_retry["turn_completion"]["action"] == "final_only"
assert provider.calls[-1]["tools"] == []
```

- [ ] **Step 3: Run test to verify failure**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_turn_completion_reasoner.py -q
```

Expected: fail because `DefaultReasoner.run()` has no turn-completion integration and `run_turn()` does not propagate `turn_completion` into `context_retry`.

- [ ] **Step 4: Import and instantiate the controller**

Modify imports in `agent/core/passive_turn.py`:

```python
from agent.policies.turn_completion import (
    TurnCompletionController,
    TurnCompletionDecision,
)
```

In `DefaultReasoner.__init__`, add:

```python
        self._turn_completion = TurnCompletionController()
```

- [ ] **Step 5: Add final-only state to `run`**

Near the local variables in `DefaultReasoner.run()` where `tools_used`, `tool_chain`, and `visible_names` are initialized, add:

```python
        turn_completion_decision: TurnCompletionDecision | None = None
        final_only_next_call = False
```

- [ ] **Step 6: Consume final-only before LLM call**

Immediately before the LLM call schema selection, after pending boundary hint consumption, add:

```python
            if final_only_next_call and turn_completion_decision is not None:
                messages.append(
                    support.build_context_hint_message(
                        "turn_completion",
                        turn_completion_decision.model_hint,
                    )
                )
                logger.info(
                    "[turn_completion] final_only reason=%s",
                    turn_completion_decision.reason,
                )
```

- [ ] **Step 7: Omit tool schemas during final-only**

Replace schema selection and LLM call with logic equivalent to:

```python
            schema_names = set(visible_names) if visible_names is not None else None
            if schema_names is None and disabled:
                schema_names = self._tools.get_registered_names() - disabled
            elif schema_names is not None:
                schema_names -= disabled
            tools_for_call = [] if final_only_next_call else self._tools.get_schemas(names=schema_names)
            response = await self._llm.provider.chat(
                messages=messages,
                tools=tools_for_call,
                model=self._llm_config.model,
                max_tokens=self._llm_config.max_tokens,
                tool_choice="auto",
                on_content_delta=on_content_delta,
            )
```

Do not change provider behavior in P10a.3. In this project, passing `tools=[]` is the intended final-only signal; provider adapters already omit tool schema payloads when no tools are present.

- [ ] **Step 8: If final-only still returns tool calls, block and summarize**

After the LLM response, before normal tool-call execution:

```python
            if final_only_next_call and response.tool_calls:
                logger.info(
                    "[turn_completion] final_only ignored tool calls: %s",
                    [tc.name for tc in response.tool_calls],
                )
                summary = await self._summarize_incomplete_progress(
                    messages,
                    reason="final_only_tool_call",
                    iteration=iteration + 1,
                    tools_used=tools_used,
                )
                return self._build_result(
                    reply=summary,
                    tools_used=tools_used,
                    tool_chain=tool_chain,
                    visible_names=visible_names,
                    thinking=None,
                    streamed=streamed,
                    react_input_samples=react_input_samples,
                    cache_prompt_tokens=react_cache_prompt_tokens,
                    cache_hit_tokens=react_cache_hit_tokens,
                    cache_seen=react_cache_seen,
                    tool_boundary_trace=(
                        self._tool_boundary.trace(tool_boundary_context)
                        if tool_boundary_context is not None
                        else None
                    ),
                    turn_completion_trace=(
                        _completion_trace(turn_completion_decision)
                        if turn_completion_decision is not None
                        else None
                    ),
                )
```

Implement `_completion_trace()` as a small helper near `_is_tool_loop_guard_denial()`:

```python
def _completion_trace(decision: TurnCompletionDecision | None) -> dict[str, object] | None:
    if decision is None:
        return None
    return {
        "action": decision.action,
        "reason": decision.reason,
        "metadata": dict(decision.metadata),
    }
```

- [ ] **Step 9: Return immediately when final-only produces content**

In the existing final reply branch, make sure `_build_result()` receives `turn_completion_trace=_completion_trace(turn_completion_decision)`.

- [ ] **Step 10: Evaluate completion after a boundary soft-stop**

Inside the `if not boundary_decision.execute:` branch, after `iter_calls.append(...)` and before `continue`, add:

```python
                            if (
                                tool_boundary_context is not None
                                and boundary_decision.action == "soft_stop"
                            ):
                                turn_completion_decision = self._turn_completion.evaluate(
                                    intent=tool_boundary_context.intent,
                                    ledger=tool_boundary_context.ledger,
                                    boundary_decisions=self._tool_boundary.recent_decisions(
                                        tool_boundary_context
                                    ),
                                    local_source_allowed=(
                                        tool_boundary_context.access_plan.reason
                                        == "doc_rag_allows_explicit_local_files"
                                    ),
                                )
                                if turn_completion_decision.action == "final_only":
                                    final_only_next_call = True
```

- [ ] **Step 11: Add metadata support**

Update `_build_result()` signature:

```python
        turn_completion_trace: dict[str, object] | None = None,
```

Add to metadata:

```python
        if turn_completion_trace is not None:
            metadata["turn_completion"] = turn_completion_trace
```

Update every `_build_result()` call inside `DefaultReasoner.run()` to pass `turn_completion_trace=_completion_trace(turn_completion_decision)` where the local variable exists, and omit it in helper methods that do not have that variable.

- [ ] **Step 12: Propagate metadata through `run_turn`**

In `DefaultReasoner.run_turn()`, after the existing `tool_boundary` propagation block, add:

```python
                if result.metadata.get("turn_completion"):
                    retry_trace["turn_completion"] = result.metadata["turn_completion"]
```

This is required because `run_turn()` returns `TurnRunResult`, not `ReasonerResult`, and tests/live observe read `context_retry`.

- [ ] **Step 13: Run reasoner test**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_turn_completion_reasoner.py -q
```

Expected: all tests pass.

- [ ] **Step 14: Commit Task 3**

```bash
git add agent/core/passive_turn.py tests/test_turn_completion_reasoner.py
git commit -m "Add final-only turn completion mode"
```

---

### Task 4: Add Negative Reasoner Regressions

**Files:**
- Modify: `tests/test_turn_completion_reasoner.py`
- Modify: `tests/test_turn_completion_policy.py` if policy gaps are found

**Interfaces:**
- Consumes:
  - Final-only metadata from Task 3
  - Existing fake reasoner harness
- Produces:
  - Regression coverage that final-only does not trigger too early.

- [ ] **Step 1: Add no-hit regression**

Add a reasoner test where `search_docs` returns:

```json
{"ok": true, "hit_count": 0, "hits": []}
```

Then the model requests another retrieval. Assert:

```python
assert result.context_retry.get("turn_completion", {}).get("action") != "final_only"
assert provider.calls[-1]["tools"] != []
```

- [ ] **Step 2: Add no-citation chunk regression**

Add a reasoner test where `fetch_doc_chunk` returns:

```json
{"ok": true, "chunk": {"chunk_id": "c1", "content": "text without citation"}}
```

Then the model requests another `fetch_doc_chunk`. Assert final-only is not triggered.

- [ ] **Step 3: Add explicit local-source regression**

Use prompt:

```text
根据项目文档和源码回答，并展开原文证据，请读取 agent/core/passive_turn.py
```

Assert final-only is not triggered merely because a Document RAG tool produced citation evidence earlier in the turn. This guards the P10a.1 explicit local-file allow path. The prompt intentionally contains both evidence-expansion terms and explicit source/local-file terms so the regression cannot pass merely because the intent was not `doc_qa_with_evidence`.

- [ ] **Step 4: Add final-only tool-call ignore regression**

Add a reasoner test with this sequence:

1. `search_docs` succeeds.
2. `fetch_doc_chunk` succeeds with citation.
3. Redundant `fetch_doc_chunk` soft-stops and activates final-only.
4. The next provider response still returns `ToolCall("bad", "search_docs", {"query": "again"})`.

Assert:

```python
assert len(search_docs.calls) == 1
assert len(fetch_doc_chunk.calls) == 1
assert result.context_retry["turn_completion"]["action"] == "final_only"
assert "final_only_tool_call" in (result.reply or "")
```

This verifies that final-only is a runtime boundary, not just another prompt hint.

- [ ] **Step 5: Run negative regressions**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_turn_completion_policy.py tests/test_turn_completion_reasoner.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 4**

```bash
git add tests/test_turn_completion_policy.py tests/test_turn_completion_reasoner.py
git commit -m "Add turn completion negative regressions"
```

---

### Task 5: Metadata, Logging, and Targeted Suite

**Files:**
- Modify: `agent/core/passive_turn.py`
- Modify: `agent/policies/tool_boundary.py`
- Modify: `tests/test_tool_boundary_reasoner.py`
- Modify: `tests/test_tool_boundary_manager.py`

**Interfaces:**
- Produces:
  - Ordinary log visibility for `soft_stop` and final-only
  - Observe metadata fields:
    - `tool_boundary.decisions`
    - `tool_boundary.ledger_summary`
    - `turn_completion.action`
    - `turn_completion.reason`
    - `turn_completion.metadata.soft_stop_count`

- [ ] **Step 1: Add mandatory log assertions**

Use `caplog` in either `tests/test_tool_boundary_manager.py` or `tests/test_turn_completion_reasoner.py` so ordinary logs are covered by automated tests:

```python
assert "[tool_boundary] soft_stop tool=fetch_doc_chunk reason=document_rag_evidence_complete" in caplog.text
assert "[turn_completion] final_only reason=document_rag_evidence_complete" in caplog.text
```

At least one test must prove each log line. Do not leave log coverage only to manual smoke; ordinary logs are part of the P10a.3 debugging contract.

- [ ] **Step 2: Verify observe metadata shape through reasoner metadata**

Add assertions to the final-only reasoner test:

```python
assert result.context_retry["tool_boundary"]["ledger_summary"]["has_successful_retrieval"] is True
assert result.context_retry["tool_boundary"]["ledger_summary"]["has_citation_evidence"] is True
assert result.context_retry["turn_completion"]["metadata"]["soft_stop_count"] >= 1
```

- [ ] **Step 3: Run targeted P10a.3/P10a.2 tests**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_turn_completion_policy.py \
  tests/test_turn_completion_reasoner.py \
  tests/test_tool_boundary_manager.py \
  tests/test_tool_boundary_reasoner.py \
  tests/test_evidence_completion_policy.py \
  -q
```

Expected: all tests pass.

- [ ] **Step 4: Commit Task 5**

```bash
git add agent/core/passive_turn.py agent/policies/tool_boundary.py tests/test_turn_completion_reasoner.py tests/test_tool_boundary_reasoner.py tests/test_tool_boundary_manager.py
git commit -m "Trace turn completion boundary decisions"
```

---

### Task 6: Full Verification and Documentation

**Files:**
- Modify: `my_md/governance/02-current-issues.md`
- Modify: `my_md/governance/04-fix-roadmap.md`
- Modify: `my_md/governance/06-star-log.md`
- Modify: `my_md/rag/20-document-rag-p10a2-tool-boundary-design.md`
- Modify: `my_md/rag/22-document-rag-p10a3-turn-completion-plan.md`
- Modify: `progress.md`

**Interfaces:**
- Produces:
  - P10a.3 implementation status and verification results
  - Manual smoke instructions

- [ ] **Step 1: Run targeted suite**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_turn_completion_policy.py \
  tests/test_turn_completion_reasoner.py \
  tests/test_tool_boundary_manager.py \
  tests/test_tool_boundary_reasoner.py \
  tests/test_evidence_completion_policy.py \
  -q
```

Expected: all targeted P10a.3/P10a.2 tests pass.

- [ ] **Step 2: Run broader relevant suite**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_doc_rag_intent.py \
  tests/test_doc_rag_intent_preload.py \
  tests/test_tool_access_gateway.py \
  tests/test_tool_access_gateway_reasoner.py \
  tests/test_tool_boundary_manager.py \
  tests/test_tool_boundary_reasoner.py \
  tests/test_turn_completion_policy.py \
  tests/test_turn_completion_reasoner.py \
  tests/test_agent_core_p2_reasoner.py \
  -q
```

Expected: all tests pass.

- [ ] **Step 3: Run full suite**

Run:

```bash
uv run --with pytest --with pytest-asyncio pytest -q
```

Expected: all tests pass. If failures are unrelated to this change, record exact node ids and error summaries before deciding whether to fix or defer.

- [ ] **Step 4: Run compile check**

Run:

```bash
python3 -m compileall agent/policies agent/core/passive_turn.py tests/test_turn_completion_policy.py tests/test_turn_completion_reasoner.py
```

Expected: command exits 0.

- [ ] **Step 5: Update docs**

Update the listed governance/RAG docs with:

```markdown
- P10a.3 automated implementation completed:
  - added `TurnCompletionController`;
  - final-only mode triggers after `document_rag_evidence_complete`;
  - final-only omits tool schemas and requires answer from existing ledger evidence;
  - targeted pytest: record the observed summary from Task 6 Step 1;
  - full pytest: record the observed summary from Task 6 Step 3;
  - compileall: record whether Task 6 Step 4 exited 0.
- Real CLI/LLM smoke remains required:
  - repeat turn `362` prompt;
  - expected successful target-tool executions: `search_docs`, `fetch_doc_chunk`;
  - expected `turn_completion final_only` log after evidence-complete soft stop;
  - expected final LLM call has no tool schema;
  - target ReAct iterations: 3-4 rather than 5+.
```

- [ ] **Step 6: Add manual smoke recipe**

Add this recipe to `my_md/rag/22-document-rag-p10a3-turn-completion-plan.md`:

```markdown
## Manual Live Smoke

Prompt:

`请重新从文档知识库检索，不要复用上轮内容：根据项目文档回答agent runtime负责什么，并调用原文chunk展开证据，回答必须带引用`

Expected logs:

- `[tool_boundary] soft_stop tool=fetch_doc_chunk reason=document_rag_evidence_complete`
- `[turn_completion] final_only reason=document_rag_evidence_complete`
- no `shell/read_file/list_dir`
- no real execution after final-only begins

Expected observe metadata:

- `tool_boundary.ledger_summary.has_successful_retrieval=true`
- `tool_boundary.ledger_summary.has_citation_evidence=true`
- `turn_completion.action=final_only`
- `turn_completion.reason=document_rag_evidence_complete`

Expected cost shape:

- successful target-tool executions: `search_docs`, `fetch_doc_chunk`
- ReAct iterations: target 3-4
- no repeated LLM rounds after final-only
```

- [ ] **Step 7: Commit Task 6**

```bash
git add my_md/governance/02-current-issues.md my_md/governance/04-fix-roadmap.md my_md/governance/06-star-log.md my_md/rag/20-document-rag-p10a2-tool-boundary-design.md my_md/rag/22-document-rag-p10a3-turn-completion-plan.md progress.md
git commit -m "Document P10a.3 turn completion implementation"
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
git log --oneline -8
```

Expected: P10a.3 task commits are visible in order.

- [ ] If the user asks to push, run:

```bash
git push
```

Expected: `main -> main` pushed successfully.

---

## Plan Self-Review

- Spec coverage: covers policy, reasoner integration, logging, metadata, tests, docs, and manual smoke.
- Placeholder scan: no `TBD`, no unspecified "add tests", and every task has explicit files and commands.
- Type consistency: `TurnCompletionDecision`, `TurnCompletionController.evaluate`, and `_completion_trace` names are used consistently across tasks.
- Scope check: focused on P10a.3 completion boundary only; no changes to tool registry, always-on metadata, LRU, or plugin architecture.
