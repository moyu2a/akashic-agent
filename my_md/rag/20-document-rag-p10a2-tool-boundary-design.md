# Turn Tool Boundary Manager Design

## Background

RAG-006 P10a introduced turn-local Document RAG intent preload. P10a.1 then added
the Tool Access Gateway so strong document-evidence turns no longer drift into
`shell`, `read_file`, or `list_dir` unless the user explicitly asks for local
source files.

The latest live smoke for turn `361` proves that access control works:

- no `shell`, `read_file`, or `list_dir` calls;
- `error=NULL`;
- CLI stayed connected;
- actual chain:
  `tool_search -> search_docs -> fetch_doc_chunk -> fetch_doc_chunk -> fetch_doc_chunk -> search_docs -> fetch_doc_chunk`.

The remaining problem is no longer wrong tool access. It is missing tool-use
boundary management after tools are already available:

- redundant `tool_search` for already visible tools;
- repeated retrieval after retrieval has already succeeded;
- repeated evidence expansion after enough citation-bearing evidence exists;
- no clear current-turn completion signal that tells the model to stop using
  tools and answer.

## Design Goal

Add a modular current-turn tool boundary layer that answers five questions:

1. Which tools are visible in this turn?
2. Which tools may `tool_search` unlock in this turn?
3. Which requested tool calls may execute?
4. Has this turn already spent enough tool budget?
5. Is there enough evidence to stop tool use and answer?

The design keeps all decisions turn-local. It does not write policy outcomes to
`ToolDiscoveryState`, does not change always-on metadata, does not replace the
plugin system, and does not rewrite `AgentLoop`.

## Architectural Position

The new boundary manager is a core policy layer called by `DefaultReasoner`.

```text
DefaultReasoner.run_turn()
        |
        v
TurnToolBoundaryManager
        |
        +-- ToolAccessPolicy
        +-- ToolBudgetPolicy
        +-- EvidenceCompletionPolicy
        +-- ToolCallLedger
        +-- ToolBoundaryTrace
```

This is not a normal plugin. It must run before or during surfaces that normal
plugin hooks cannot fully control:

- prompt tool-schema visibility;
- `tool_search` result filtering and unlock merging;
- execution gating before a tool runs;
- current-turn tool result observation;
- lightweight hints before the next LLM call.

Future plugins may contribute bounded policy rules, but the core manager must
validate, merge, and enforce final decisions.

## Module Layout

Create or evolve these modules:

- `agent/policies/tool_boundary.py`
  - Facade used by `DefaultReasoner`.
  - Owns policy ordering and decision merging.
  - Exposes current-turn APIs for visibility, discovery, execution, observation,
    and next-call hints.

- `agent/policies/tool_access.py`
  - Existing Tool Access Gateway.
  - Becomes the access policy implementation under the boundary manager.
  - Keeps current P10a and P10a.1 behavior.

- `agent/policies/tool_budget.py`
  - Generic budget and repetition rules based on tool class and task intent.
  - Produces warn, soft-stop, require-reason, or block decisions.

- `agent/policies/evidence_completion.py`
  - Evidence-state rules.
  - First version focuses on Document RAG citation-bearing evidence.
  - Later versions can cover memory/message evidence and external research.

- `agent/policies/tool_ledger.py`
  - Current-turn ledger for tool calls and result summaries.
  - Shared by access, budget, and evidence policies.

Tests:

- `tests/test_tool_boundary_manager.py`
- `tests/test_tool_budget_policy.py`
- `tests/test_evidence_completion_policy.py`
- `tests/test_tool_boundary_reasoner.py`

Existing access gateway tests should keep passing and may be migrated to assert
through the boundary manager facade once integration is stable.

## Core Concepts

### ToolClass

Budget and completion rules should not be hardcoded only by tool name. Each tool
gets a class:

```text
discovery        tool_search
retrieval        search_docs, recall_memory, search_messages
evidence_expand  fetch_doc_chunk, fetch_messages
local_file       read_file, list_dir
execution        shell
external_io      future network/API/email tools
memory_write     memorize
```

The first implementation may use a small static mapping. Later it can move to
tool registry metadata.

### TaskIntent

The manager chooses budget profiles from the current turn intent:

```text
doc_qa_simple
doc_qa_with_evidence
memory_qa
code_inspection
no_tool
open_exploration
```

P10a.2 only needs Document RAG intents, but the abstraction must not be
Document-RAG-specific.

### ToolCallLedger

The ledger is the shared current-turn fact source. Policies should not scan raw
LLM messages independently.

Suggested fields:

```python
@dataclass(frozen=True)
class ToolCallRecord:
    tool_name: str
    tool_class: str
    args_hash: str
    args_summary: str
    call_index: int
    result_summary: str = ""
    result_has_evidence: bool = False
    result_has_citation: bool = False
    result_error_code: str = ""
```

The ledger should provide derived facts:

- calls by tool;
- calls by tool class;
- same-args repeats;
- same-class streak;
- whether retrieval has succeeded;
- whether citation-bearing evidence exists;
- whether a tool was already visible when `tool_search` was called.

### ToolBoundaryDecision

Use one decision shape across policies:

```python
@dataclass(frozen=True)
class ToolBoundaryDecision:
    action: Literal["allow", "warn", "soft_stop", "require_reason", "block"]
    reason: str
    model_hint: str | None = None
    user_visible_message: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
```

Semantics:

- `allow`: proceed normally.
- `warn`: execute, but record a policy warning.
- `soft_stop`: do not make this a fatal tool error; nudge the model to answer
  from existing evidence.
- `require_reason`: reserved for later high-cost or risky tools.
- `block`: do not execute; return a structured tool result.

P10a.2 should mostly use `soft_stop`, while P10a.1 local-file drift remains a
hard access block.

## Policy Responsibilities

### ToolAccessPolicy

Answers: can this tool be used?

Responsibilities:

- compute current-turn visible tools;
- filter `tool_search` results;
- merge allowed `tool_search` unlocks;
- block execution of tools forbidden in this turn;
- observe terminal tool results such as Document RAG disabled fallback.

This is the current Tool Access Gateway responsibility and should remain the
only policy that hard-blocks local-file tools in strong Document RAG turns.

### ToolBudgetPolicy

Answers: should the turn keep spending tools?

Responsibilities:

- count calls by tool class;
- detect same-args repeats;
- detect repeated retrieval after retrieval success;
- detect redundant `tool_search` for tools already visible;
- produce soft-stop hints when a budget boundary is crossed.

First P10a.2 profile:

```text
doc_qa_simple:
  retrieval.max_calls = 1
  evidence_expand.max_calls = 1
  redundant_visible_tool_search = soft_stop

doc_qa_with_evidence:
  retrieval.max_calls = 1
  evidence_expand.max_calls = 2
  redundant_visible_tool_search = soft_stop
  repeated_same_args = soft_stop
```

These numbers are policy defaults, not architectural constants.

### EvidenceCompletionPolicy

Answers: is there enough evidence to stop?

Responsibilities:

- track whether `search_docs` returned hits;
- track whether `fetch_doc_chunk` returned citation-bearing chunk text;
- decide whether the current evidence likely covers the user's core question;
- emit a soft-stop model hint when evidence is sufficient.

First P10a.2 completion rule:

```text
If intent is doc_qa_with_evidence
and at least one citation-bearing chunk exists
and at least one retrieval hit exists,
then prefer final answer over additional retrieval or expansion.
```

The rule should be conservative. It should not claim semantic proof of answer
quality; it only says enough evidence exists to attempt a grounded answer.

## Reasoner Integration

`DefaultReasoner` should integrate through a facade, not call every policy
directly.

Narrow integration points:

1. Before building prompt schemas:
   - ask boundary manager for visible tools.

2. After `tool_search` returns:
   - filter blocked matches;
   - merge only allowed unlocks.

3. Before executing a tool call:
   - ask boundary manager for access and budget decision.
   - hard blocks become structured tool results.
   - soft stops add a corrective tool result or next-call hint, depending on
     which path is least disruptive in the existing reasoner.

4. After a tool returns:
   - append a `ToolCallRecord` to the ledger;
   - update evidence state;
   - update access plan if terminal result semantics require it.

5. Before the next LLM call:
   - if the manager has a pending soft-stop hint, insert a compact model hint:
     existing evidence is enough; answer now unless the user explicitly asked
     for more exploration.

No `AgentLoop` rewrite is needed.

## P10a.2 Behavior

For the regression prompt similar to turn `361`:

```text
请重新从文档知识库检索，不要复用上轮内容：
根据项目文档回答agent runtime负责什么，
并调用原文chunk展开证据，回答必须带引用
```

Expected behavior:

- `search_docs` and `fetch_doc_chunk` are visible by current-turn access policy.
- `shell`, `read_file`, and `list_dir` remain suppressed and execution-blocked.
- `tool_search(select:search_docs,fetch_doc_chunk)` when both tools are already
  visible triggers a soft-stop or corrective hint, not a new useful unlock.
- second similar `search_docs` triggers soft-stop.
- third `fetch_doc_chunk` triggers soft-stop.
- the model should converge to final answer after roughly 3-4 ReAct rounds and
  no more than about 4 tool calls.

Target chains:

- simple Document RAG question: `search_docs -> final`;
- evidence Document RAG question: `search_docs -> fetch_doc_chunk -> final`;
- complex evidence question: `search_docs -> fetch_doc_chunk -> fetch_doc_chunk -> final`.

## Observability

Each boundary decision should be logged and added to turn metadata:

```json
{
  "tool_boundary": {
    "intent": "doc_qa_with_evidence",
    "decisions": [
      {
        "tool": "fetch_doc_chunk",
        "action": "soft_stop",
        "reason": "evidence_expand_budget_exceeded",
        "call_index": 4
      }
    ],
    "ledger_summary": {
      "retrieval_calls": 1,
      "evidence_expand_calls": 2,
      "has_citation_evidence": true
    }
  }
}
```

This trace is required because tool governance changes are behavioral and need
live smoke review, not only unit tests.

## Plugin Extension Model

The first implementation is core-only. The design should leave an extension
path:

```text
plugin contributes ToolBoundaryRule
core validates rule
core merges rule into current-turn policy
core enforces final decision
```

Plugins must not:

- bypass disabled tools;
- write directly to LRU or `ToolDiscoveryState`;
- mutate the LLM message list directly;
- replace `ToolRegistry.execute`;
- override hard blocks from core access policy.

This keeps plugins as extension planes while the boundary manager remains the
control plane.

## Non-Goals

This design does not add:

- global RBAC;
- persistent per-user permissions;
- user approval UI for risky tools;
- a full policy DSL;
- model-based semantic evidence grading;
- changes to always-on tool metadata;
- cross-turn budget persistence;
- hard blocking of normal repeated calls as the first implementation.

## Verification Plan

Unit tests:

- tool-class mapping and default budgets;
- ledger same-args and same-class counters;
- redundant visible `tool_search` soft-stop;
- repeated retrieval soft-stop;
- evidence expansion budget soft-stop;
- evidence completion hint when citation-bearing chunk exists;
- explicit local-source requests still allow local file tools through access
  policy.

Reasoner integration tests:

- initial visible tools preserve P10a behavior;
- strong Document RAG turns still suppress local-file tools;
- blocked local-file calls still do not execute;
- redundant `tool_search` produces boundary metadata;
- repeated RAG calls produce soft-stop hints;
- memory-after-doc-LRU still suppresses stale Document RAG visibility.

Live smoke:

- repeat turn `361`-style prompt and confirm no local-file tools;
- confirm tool calls drop from 7 toward 4 or fewer;
- confirm simple Document RAG prompt can answer with `search_docs -> final`;
- confirm evidence prompt can answer with `search_docs -> fetch_doc_chunk -> final`;
- confirm explicit source-code prompt can still use `read_file` or `shell` when
  appropriate.

## Rollout

Phase 1:

- add ledger, budget policy, evidence completion policy, and boundary facade;
- keep existing `ToolAccessGateway` behavior unchanged;
- integrate soft-stop hints only for Document RAG P10a.2;
- add tests and metadata traces.

Phase 2:

- migrate direct access-gateway calls in `DefaultReasoner` behind the boundary
  facade;
- keep compatibility tests for access behavior.

Phase 3:

- expose a controlled plugin rule contribution interface if a later use case
  needs domain-specific budgets.

## Acceptance Criteria

- The access behavior verified by P10a.1 remains intact.
- P10a.2 Document RAG evidence turns no longer repeat retrieval and expansion
  unnecessarily.
- The first implementation is turn-local and does not mutate LRU.
- `DefaultReasoner` has one boundary-manager facade rather than new scattered
  policy branches.
- All new policy decisions are visible in logs or observe metadata.
- Tests cover policy units and reasoner integration.
