# TaskPlan Context Requirement And Capability Scope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status (2026-07-14): Complete and live-verified.** Tasks 1-7 were implemented with TDD, all Critical/Important review findings were closed, and the final suite passed `1619 passed, 3 warnings in 38.10s`. Isolated real CLI smoke verified pure create in 2 iterations, preference/history create in 3 iterations with one real contextual retrieval each, and inspect/update/background in 2 iterations. Live-smoke follow-up also added bounded required/negated/positive precedence for TaskPlan creation and background start/observe.

**Goal:** Resolve `LA-001` by making TaskPlan context retrieval explicit and bounded: pure plan creation becomes `create_task_plan -> final`, while prompts that explicitly depend on preferences or prior discussion receive one turn-local retrieval capability before plan creation.

**Architecture:** Introduce a single immutable `TaskPlanTurnContract` containing the TaskPlan action, context requirement, required and allowed capabilities, retrieval budget, and completion capability. Tool capabilities are declared as registry metadata; `TaskPlanAccessPolicy` converts an active contract into a strict current-turn allow scope, `TurnToolBoundaryManager` enforces the retrieval budget, and `TaskPlanCompletionPolicy` stops only when a successful tool record provides the contract's expected completion capability. Tool-access planning is independent of whether deferred tool discovery is enabled: an active TaskPlan contract always gets a boundary context, while discovery-disabled non-TaskPlan turns retain their current all-tools/no-boundary behavior. Explicit background-job requests are classified first but remain a non-strict passthrough to existing background tooling rather than being governed by the TaskPlan contract. Existing AgentLoop, plugin lifecycle, global always-on declarations, ToolDiscoveryState, and LRU behavior remain unchanged.

**Primary issue:** `LA-001`, observed in CLI turn `382`: `recall_memory -> search_messages(soft-stop) -> create_task_plan -> final`, 4 ReAct iterations. The desired pure-plan path is `create_task_plan -> final`, normally 2 iterations.

**Tech stack:** Python dataclasses and literals, existing `ToolRegistry`, `ToolAccessGateway`, `TurnToolBoundaryManager`, `TurnCompletionController`, `DefaultReasoner`, pytest/pytest-asyncio, SQLite/observe live smoke.

## Global Constraints

- Do not modify `AgentLoop` main control flow.
- Do not implement this as a plugin; it is a core policy and tool-metadata boundary.
- Do not change global always-on declarations solely for TaskPlan.
- Do not write TaskPlan intent, contract, capability scope, or retrieval state into `ToolDiscoveryState` or LRU.
- Do not globally disable memory or session-history tools.
- Do not change passive/global memory prompt injection in this phase; `LA-001` covers active tool retrieval only.
- Preserve current Document RAG, Turn Trace, CLI session, and memory-after-doc-LRU behavior.
- Use a strict capability allow scope only when a TaskPlan contract is active; non-TaskPlan turns keep existing behavior.
- Build `ToolAccessContext` and evaluate the access plan regardless of `tool_search_enabled`; the discovery flag must never bypass an active TaskPlan strict contract.
- When `tool_search_enabled=False`, non-TaskPlan turns preserve the current all-registered-tools/no-boundary behavior, while active TaskPlan turns still receive a `ToolBoundaryContext` and strict capability scope.
- Explicit background start/observe/output/cancel requests do not activate a TaskPlan contract and do not inherit TaskPlan completion or retrieval budgets.
- Context retrieval must be explicit and turn-local.
- Follow TDD: add failing tests, verify failure, implement, then run focused and broad regressions.
- Do not commit or push unless the user explicitly requests it.

## Behavior Contract

| Prompt class | Action | Context requirement | Required capabilities | Allowed capabilities | Retrieval budget | Completion capability |
| --- | --- | --- | --- | --- | ---: | --- |
| `制定一个三步计划` | `plan_create` | `none` | `task_plan.create` | `task_plan.create` | 0 | `task_plan.create` |
| create while active task exists | `plan_create` | `none` | `task_plan.create` | `task_plan.create`, optional `task_plan.inspect` | 0 | `task_plan.create` |
| `结合我的偏好制定计划` | `plan_create` | `long_term_memory` | `task_plan.create` | `task_plan.create`, optional `task_plan.inspect`, optional `memory.recall` | 1 | `task_plan.create` |
| `按照我们上次讨论制定计划` | `plan_create` | `session_history` | `task_plan.create` | `task_plan.create`, optional `task_plan.inspect`, optional `history.search` | 1 | `task_plan.create` |
| `当前任务做到哪一步` | `plan_inspect` | `none` | `task_plan.inspect` | `task_plan.inspect` | 0 | `task_plan.inspect` |
| `把第一步标记完成` | `plan_update` | `none` | `task_plan.update` | optional `task_plan.inspect`, `task_plan.update` | 0 | `task_plan.update` |

Background requests are precedence guards, not TaskPlan contracts:

| Prompt class | Background mode | TaskPlan contract | Non-strict tools exposed |
| --- | --- | --- | --- |
| `启动后台任务分析日志` | `start` | inactive | `spawn` |
| `查看后台任务状态` | `observe` | inactive | `spawn_manage` |
| `查看后台任务输出` | `output` | inactive | `spawn_manage`, `task_output` |
| `取消后台任务` | `cancel` | inactive | `spawn_manage` |

First implementation deliberately excludes `history.fetch` from contextual plan creation. If one search/recall result is insufficient, the agent must create from available information or ask a necessary clarification; it must not expand into a retrieval chain.

`retrieval_budget=1` is permission, not an obligation. If current prompt/history or passively injected profile context is already sufficient, the model may call `create_task_plan` directly without consuming the retrieval budget.

## Intent Precedence

1. Explicit background-job signals win over TaskPlan state signals and return an inactive TaskPlan contract plus a non-strict background passthrough decision. Within background classification, match `cancel`, then `output`, then `start`, then generic `observe`, so the generic phrase `后台任务` cannot swallow a more specific operation.
2. A TaskPlan action must be present before TaskPlan context requirement is inferred.
3. Explicit no-retrieval signals force `context_requirement=none`.
4. Explicit session-history signals win over long-term-memory signals.
5. Explicit long-term preference/memory signals select `long_term_memory`.
6. Topic words such as `Document RAG`, `成本`, `项目`, or `修复` never imply memory/history retrieval.
7. No strong context signal defaults to `none`.

Required ambiguity cases:

- `当前任务输出是什么` -> `plan_inspect`, not background passthrough.
- `启动后台任务分析日志` -> inactive TaskPlan contract + `background_start` passthrough.
- `查看后台任务输出` -> inactive TaskPlan contract + `background_output` passthrough.
- `取消后台任务` -> inactive TaskPlan contract + `background_cancel` passthrough.
- `按照上次讨论为 Document RAG 制定计划` -> `plan_create + session_history`.
- `结合我的偏好制定计划，但不要查询历史或记忆` -> `plan_create + none`.
- `为修复 Document RAG 成本制定三步计划，只创建计划` -> `plan_create + none`.

## Capability Vocabulary

Initial TaskPlan/context capability names:

```text
task_plan.create
task_plan.inspect
task_plan.update
memory.recall
history.search
```

Only capabilities needed by the active TaskPlan contract are added now. Background capabilities are deliberately excluded because background requests bypass the TaskPlan strict scope. Unrelated tools may keep an empty capability set. During an active strict TaskPlan scope, empty-capability tools are suppressed; outside that scope they behave exactly as before.

`required_capabilities` and `allowed_capabilities` have different failure semantics:

- Every required capability must resolve to at least one registered tool; otherwise the contract fails closed with a model-visible service-unavailable hint and no unrelated tool fallback.
- Allowed-but-not-required capabilities are optional. If an optional provider is absent, omit it from the scope, record `optional_capability_unavailable`, and continue with the required TaskPlan state tool.
- An empty capability set on an unrelated registered tool is valid and never treated as a configuration error by itself.

## File Structure

Create:

- `agent/policies/task_plan_contract.py`: contract types, intent/context inference, capability and completion-capability derivation, trace serialization.
- `agent/policies/task_plan_context_budget.py`: TaskPlan-specific one-shot context retrieval execution policy.
- `tests/test_task_plan_contract.py`: contract and precedence matrix.
- `tests/test_task_plan_context_budget.py`: retrieval budget and transition tests.
- `tests/test_tool_capabilities.py`: registry metadata and core tool capability declarations.

Modify:

- `agent/tools/base.py`: optional default `capabilities` declaration.
- `agent/tools/registry.py`: store/query capability metadata without exposing it in model schemas.
- `agent/tools/task_plan.py`: declare create/inspect/update capabilities.
- `agent/tools/recall_memory.py`: declare `memory.recall`.
- `agent/tools/message_lookup.py`: declare `history.search` on `search_messages`; `fetch_messages` remains outside this phase's capability vocabulary.
- `agent/policies/tool_access_types.py`: carry registered tool capability mapping, discovery mode, a typed TaskPlan contract, and JSON-safe trace metadata.
- `agent/policies/task_plan_boundary.py`: consume `TaskPlanTurnContract`, build strict capability scope, dynamically retire retrieval tools after one allowed context attempt.
- `agent/policies/tool_access.py`: preserve typed contracts across plan merges, keep background passthrough non-strict, and preserve TaskPlan-specific execution error semantics.
- `agent/policies/tool_boundary.py`: store the contract, enforce TaskPlan retrieval budget before generic evidence/budget policies, expose contract trace and transition hints.
- `agent/policies/tool_budget.py`: add the non-Document-RAG `task_plan_state` intent used while a TaskPlan state contract is active.
- `agent/policies/tool_ledger.py`: preserve executor status on each real tool-call record so completion distinguishes execution success from denied/error outcomes.
- `agent/policies/task_plan_completion.py`: make completion capability action-aware.
- `agent/policies/turn_completion.py`: accept/pass the typed TaskPlan contract and protected tool-capability mapping.
- `agent/core/passive_turn.py`: always evaluate access planning, conditionally enforce the boundary when discovery is enabled or TaskPlan scope is strict, inject registry capabilities into `ToolAccessContext`, preserve all-tools behavior when discovery is disabled outside TaskPlan turns, pass the typed contract to completion, and fix final-only logging reason.
- Existing TaskPlan/access/boundary/reasoner/registry/toolset tests.
- `tests/test_message_lookup_tool.py`: protected current-session precedence for contextual history search.
- `my_md/local_agent/02-task-plan-first-phase-design.md`, governance LA-001 docs, STAR CASE-004, and `progress.md` after implementation/live smoke.

---

## Task 1: Add The TaskPlan Turn Contract

**Files:**

- Create: `agent/policies/task_plan_contract.py`
- Create: `tests/test_task_plan_contract.py`
- Modify later: `agent/policies/task_plan_boundary.py`

**Produces:**

```python
TaskPlanAction = Literal[
    "none",
    "plan_create",
    "plan_inspect",
    "plan_update",
]
TaskPlanContextRequirement = Literal[
    "none",
    "long_term_memory",
    "session_history",
]
BackgroundPassthroughMode = Literal[
    "none",
    "start",
    "observe",
    "output",
    "cancel",
]

@dataclass(frozen=True)
class TaskPlanTurnContract:
    action: TaskPlanAction
    context_requirement: TaskPlanContextRequirement
    required_capabilities: frozenset[str]
    allowed_capabilities: frozenset[str]
    retrieval_budget: int
    completion_capability: str | None
    matched_terms: tuple[str, ...] = ()
    reason: str = "no_task_plan_contract"

    @property
    def active(self) -> bool: ...
    def __post_init__(self) -> None: ...
    def to_trace_metadata(self) -> dict[str, object]: ...

    @classmethod
    def inactive(
        cls,
        *,
        reason: str = "no_task_plan_contract",
        matched_terms: tuple[str, ...] = (),
    ) -> TaskPlanTurnContract: ...

@dataclass(frozen=True)
class TaskPlanIntentDecision:
    contract: TaskPlanTurnContract
    background_mode: BackgroundPassthroughMode = "none"

def infer_task_plan_turn_decision(
    user_text: str,
    *,
    has_active_task: bool,
) -> TaskPlanIntentDecision: ...
```

### Steps

- [ ] Add parameterized failing tests covering the full behavior table and ambiguity cases.
- [ ] Add tests proving topic words alone never enable retrieval.
- [ ] Add tests proving no-retrieval phrases override memory/history phrases.
- [ ] Add background precedence tests for start/observe/output/cancel. Each must return an inactive TaskPlan contract and the exact passthrough mode.
- [ ] Add `to_trace_metadata()` JSON-safety tests. Trace serialization is one-way and is never accepted back as authorization input.
- [ ] Add contract invariant tests enforced by `__post_init__`: required capabilities must be a subset of allowed capabilities, `retrieval_budget` must be `0` or `1`, and an active completion capability must match the action and be required.
- [ ] Define the only valid inactive shape: `action="none"`, `context_requirement="none"`, empty required/allowed capabilities, `retrieval_budget=0`, and `completion_capability=None`. `TaskPlanTurnContract.inactive()` must produce exactly this shape; any other inactive combination raises `ValueError`.
- [ ] Run:

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_task_plan_contract.py -q
```

Expected before implementation: import failure.

- [ ] Implement contract inference with explicit precedence.
- [ ] Keep the current `infer_task_plan_intent()` as a temporary compatibility wrapper only if existing callers need it; otherwise migrate tests and remove it in Task 3.
- [ ] Re-run the contract suite; expected PASS.

Required tests include:

```python
def test_plain_create_has_no_context_retrieval(): ...
def test_document_rag_topic_does_not_enable_context_retrieval(): ...
def test_explicit_preference_selects_long_term_memory(): ...
def test_previous_discussion_selects_session_history(): ...
def test_no_retrieval_phrase_overrides_history_signal(): ...
def test_update_completion_capability_is_update_not_inspect(): ...
def test_active_create_allows_inspect_but_targets_create(): ...
def test_current_task_output_is_inspect(): ...
def test_background_start_bypasses_task_plan_contract(): ...
def test_background_observe_bypasses_task_plan_contract(): ...
def test_background_output_bypasses_task_plan_contract(): ...
def test_background_cancel_bypasses_task_plan_contract(): ...
def test_inactive_contract_has_canonical_empty_shape(): ...
def test_invalid_inactive_contract_is_rejected(): ...
```

---

## Task 2: Add Tool Capability Metadata

**Files:**

- Modify: `agent/tools/base.py`
- Modify: `agent/tools/registry.py`
- Modify: `agent/tools/task_plan.py`
- Modify: `agent/tools/recall_memory.py`
- Modify: `agent/tools/message_lookup.py`
- Modify/Test: registry, toolset, and tool tests.
- Create: `tests/test_tool_capabilities.py`

**Interfaces:**

```python
class Tool(ABC):
    capabilities: frozenset[str] = frozenset()

@dataclass
class ToolMeta:
    ...
    capabilities: frozenset[str] = frozenset()

def ToolRegistry.register(
    self,
    tool: Tool,
    *,
    capabilities: AbstractSet[str] | None = None,
    ...,
) -> None: ...

def ToolRegistry.get_capabilities_by_name(
    self,
) -> dict[str, frozenset[str]]: ...
```

Resolution rule: explicit `register(..., capabilities=...)` overrides the tool class declaration; otherwise use `tool.capabilities`.

### Steps

- [ ] Add failing registry tests in `tests/test_tool_capabilities.py` proving defaults are empty, class capabilities are stored, explicit registration overrides them, and returned mappings are defensive copies.
- [ ] Add failing tool capability tests for:

```text
create_task_plan -> task_plan.create
inspect_task_plan -> task_plan.inspect
update_task_step -> task_plan.update
recall_memory -> memory.recall
search_messages -> history.search
```

- [ ] Add a failing `SearchMessagesTool` session-boundary test: protected `_session_key` must override a model-provided `session_key`; when protected context is present, search defaults to the current session. Preserve explicit public `session_key` only for direct/backward-compatible calls without protected runtime context.

- [ ] Implement registry metadata and declarations.
- [ ] Update `SearchMessagesTool.execute()` to prefer protected `_session_key` over model-controlled `session_key`; do not expose `_session_key` in the model schema.
- [ ] Do not add capabilities to OpenAI function schemas or search descriptions.
- [ ] Keep spawn/tool-search/local/RAG tools without TaskPlan capabilities in this phase; strict TaskPlan scope suppresses them by omission.
- [ ] Run:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_tool_capabilities.py \
  tests/test_tool_search.py \
  tests/test_task_plan_tools.py \
  tests/test_task_plan_toolset.py \
  tests/test_message_lookup_tool.py \
  tests/test_spawn_tool.py -q
```

Expected: PASS.

---

## Task 3: Convert TaskPlan Access To A Strict Capability Scope

**Files:**

- Modify: `agent/policies/tool_access_types.py`
- Modify: `agent/policies/task_plan_boundary.py`
- Modify: `agent/policies/tool_access.py`
- Modify: `tests/test_task_plan_boundary.py`
- Modify: `tests/test_task_plan_gateway.py`
- Modify: `tests/test_tool_access_gateway.py`

**Type changes:**

```python
@dataclass(frozen=True)
class ToolAccessContext:
    ...
    tool_capabilities: Mapping[str, frozenset[str]] = field(default_factory=dict)
    tool_discovery_enabled: bool = True

@dataclass(frozen=True)
class ToolAccessPlan:
    ...
    policy_metadata: Mapping[str, object] = field(default_factory=dict)
    task_plan_contract: TaskPlanTurnContract | None = None
    strict_capability_scope: bool = False
    context_retrieval_tools: frozenset[str] = frozenset()
    context_retrieval_consumed: bool = False
    model_hints: tuple[str, ...] = ()
```

`TaskPlanTurnContract` is a typed control-plane field, not serialized control data. `policy_metadata` is trace-only and may contain a JSON-safe `task_plan` snapshot under a namespaced key, but no boundary or completion component may reconstruct authorization state from it.

`context_retrieval_tools` and `context_retrieval_consumed` are turn-local typed control state used only for visibility retirement. The ledger remains the source of truth for call count and budget enforcement.

`_merge_plans()` must merge policy metadata without mutating either side, union `context_retrieval_tools`, OR-merge `context_retrieval_consumed`, and deduplicate `model_hints`. A later policy may overwrite the same trace-only metadata key, while unrelated keys are preserved. A non-`None` typed contract is preserved. Two different active contracts are an invariant violation and produce a fail-closed plan rather than last-writer-wins behavior. `strict_capability_scope` is OR-merged; when active, it overrides `local_source_allowed` to false because TaskPlan state management must not inherit a Document-RAG/source policy escape hatch.

**TaskPlan access algorithm:**

1. Infer one `TaskPlanIntentDecision`.
2. If `background_mode != none`, return a non-strict passthrough plan exposing only the corresponding background tool additions; do not attach a TaskPlan contract or TaskPlan completion state.
3. If the contract is inactive, return an empty access plan.
4. Resolve required and allowed tool names from `context.tool_capabilities`.
5. If any required capability has no registered provider, return a strict fail-closed plan with `reason=task_plan_required_capability_missing`, no unrelated fallback, and `model_hints` naming the unavailable TaskPlan action.
6. Missing optional capabilities are omitted and recorded in trace metadata as `optional_capability_unavailable`; they do not invalidate the contract. Only a missing optional context-retrieval provider adds a model hint instructing the model to use current context or ask one necessary clarification instead of attempting retrieval discovery. Missing optional `task_plan.inspect` during create requires no hint.
7. Set `visible_add=resolved_allowed_tool_names` and `context_retrieval_tools` to the resolved providers for `memory.recall` or `history.search` allowed by this contract.
8. Set strict suppression/search block/execution block to `registered_tools - resolved_allowed_tool_names`.
9. Preserve `disabled_tools` as a higher-priority global restriction. If a disabled tool is the only provider for a required capability, treat that capability as unavailable and fail closed.
10. Set `strict_capability_scope=True`, attach the typed contract, and force the final merged plan's `local_source_allowed=False`.
11. Store only JSON-safe trace data and resolved context-retrieval tool names in namespaced `policy_metadata`; never deserialize the runtime contract from it. Initialize `ToolBoundaryContext.pending_hints` from `access_plan.model_hints` so fail-closed/degraded guidance reaches the first model call.

### Steps

- [ ] Expand `_ctx()` test fixtures with capability mappings.
- [ ] Add failing strict-scope tests:

```python
def test_plain_create_only_exposes_create_when_no_active_task(): ...
def test_active_create_exposes_create_and_inspect(): ...
def test_memory_create_exposes_recall_and_create_only(): ...
def test_session_create_exposes_search_messages_and_create_only(): ...
def test_inspect_only_exposes_inspect(): ...
def test_update_exposes_inspect_and_update_only(): ...
def test_tool_search_is_hidden_for_deterministic_task_plan_turn(): ...
def test_document_rag_policy_cannot_reopen_rag_under_task_plan_scope(): ...
def test_explicit_source_terms_cannot_disable_task_plan_strict_scope(): ...
def test_lru_cannot_reopen_memory_rag_or_local_tools(): ...
def test_missing_required_create_capability_fails_closed(): ...
def test_missing_optional_memory_capability_degrades_to_create_only(): ...
def test_disabled_optional_retrieval_provider_degrades_to_required_scope(): ...
def test_empty_capabilities_on_unrelated_tool_are_valid(): ...
def test_disabled_required_provider_fails_closed(): ...
def test_conflicting_typed_contracts_fail_closed(): ...
def test_background_start_is_non_strict_and_exposes_spawn(): ...
def test_background_observe_output_cancel_are_non_strict(): ...
```

- [ ] Implement capability resolution and strict scope.
- [ ] Update TaskPlan access error text to recommend only tools inside the contract scope.
- [ ] Preserve non-TaskPlan access behavior with regression tests.
- [ ] Run:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_task_plan_boundary.py \
  tests/test_task_plan_gateway.py \
  tests/test_tool_access_gateway.py -q
```

Expected: PASS.

---

## Task 4: Enforce One-Shot Context Retrieval And Dynamic Transition

**Files:**

- Create: `agent/policies/task_plan_context_budget.py`
- Create: `tests/test_task_plan_context_budget.py`
- Modify: `agent/policies/tool_boundary.py`
- Modify: `agent/policies/tool_budget.py`
- Modify: `agent/policies/tool_ledger.py`
- Modify: `agent/policies/task_plan_boundary.py`
- Modify: `tests/test_tool_ledger.py`
- Modify: `tests/test_tool_boundary_manager.py`

**Interfaces:**

```python
class TaskPlanContextBudgetPolicy:
    def evaluate_call(
        self,
        *,
        contract: TaskPlanTurnContract | None,
        ledger: ToolCallLedger,
        tool_name: str,
        tool_capabilities: Mapping[str, frozenset[str]],
    ) -> ToolBoundaryDecision | None: ...

@dataclass(frozen=True)
class ToolCallRecord:
    ...
    execution_status: str = ""

class TurnToolBoundaryManager:
    def record_tool_result(
        self,
        context: ToolBoundaryContext,
        *,
        tool_name: str,
        arguments: Mapping[str, Any],
        result_text: str,
        execution_status: str,
        visible_before_call: bool,
        decision_action: str,
        decision_reason: str,
        requested_unlocks: tuple[str, ...] = (),
        unlocked_tools: tuple[str, ...] = (),
        blocked_tools: tuple[str, ...] = (),
    ) -> None: ...
```

`ToolBoundaryContext` gains:

```python
task_plan_contract: TaskPlanTurnContract | None = None
```

The boundary reads this typed field directly from `ToolAccessPlan.task_plan_contract`. It never reconstructs the contract from `policy_metadata`.

When a non-background TaskPlan contract is active, `ToolBoundaryContext.intent` must be `task_plan_state`, not a Document RAG intent inferred from topic words. Add `task_plan_state` to `TaskIntent`; it has no generic Document RAG budget profile and is handled as non-document intent by evidence/react policies.

Decision precedence remains:

```text
ToolAccessGateway hard block
> TaskPlan context budget soft stop
> EvidenceCompletionPolicy / generic ToolBudgetPolicy
```

Budget semantics:

- `retrieval_budget=0`: retrieval tools should already be access-blocked; a hard model call is rejected by access.
- `retrieval_budget=1`: first allowed context retrieval executes; later context retrieval calls soft-stop with `task_plan_context_budget_exhausted`.
- The count covers same-tool repetition. Cross-tool retrieval attempts remain access-blocked because each contextual contract allows only one retrieval capability family.
- Failed retrieval still consumes the one-shot budget because the cost and model round already occurred.
- Executor `success`, returned `{ok:false}`, hook denial, and executor error all count once after the call passes the access gate. Calls blocked before execution do not consume the budget.
- TaskPlan state tools do not consume retrieval budget.

Dynamic transition after an allowed context retrieval attempt:

- Extend `ToolAccessPolicy.observe_tool_result()` and `ToolAccessGateway.observe_tool_result()` with keyword-only `execution_status: str = "success"`; existing policies ignore it, while `TaskPlanAccessPolicy` uses it for trace data.
- `DefaultReasoner` passes `exec_result.status` into `record_tool_result()`, records the attempt in the ledger, and immediately calls `observe_access_tool_result()` for every executor outcome that passed the access gate, before evidence/completion evaluation and before processing the next tool in the same assistant batch.
- If `tool_name` is in the typed `plan.context_retrieval_tools`, `TaskPlanAccessPolicy.observe_tool_result()` sets `context_retrieval_consumed=True` regardless of successful/failed result content or executor status.
- All context retrieval tools are added to `visible_suppress` and `tool_search_block` for subsequent iterations, but not to `execution_block`. Authorization remains stable for the turn; `TaskPlanContextBudgetPolicy` owns repeat-call rejection and returns `task_plan_context_budget_exhausted` for stale or same-batch hard calls.
- The resolved provider tool or tools for `task_plan.create` remain visible.
- Recompute visibility through `ToolAccessGateway.compute_visible_names()` instead of manually unioning/subtracting sets, so strict scope and discovery-disabled baselines share one implementation.
- The boundary adds a pending model hint: context lookup is complete; create the plan now or ask one necessary clarification; do not call more retrieval tools. For session history it explicitly says the search preview is planning context and `fetch_messages` is unavailable in this turn.

### Steps

- [ ] Add direct budget tests for first call, same-tool repeat, returned `{ok:false}`, executor error/hook denial, and non-context tools.
- [ ] Add ledger tests proving executor `success`, `denied`, and `error` statuses are preserved independently of parsed `result_ok`.
- [ ] Add same-assistant-batch regressions for `recall_memory + recall_memory` and `search_messages + search_messages`; the first call executes and the second is soft-stopped by `task_plan_context_budget_exhausted` before real execution.
- [ ] Add same-assistant-batch failure regressions where the first allowed retrieval returns `{ok:false}` or an executor error; the second identical call still does not execute.
- [ ] Keep `recall_memory + search_messages` as an access-precedence test only: `search_messages` is outside a long-term-memory contract from the beginning, so this case must not be used as evidence that the budget was consumed.
- [ ] Add boundary-manager tests proving access block wins before budget.
- [ ] Add a mixed-topic test proving `为修复 Document RAG 制定计划` produces boundary intent `task_plan_state`, not `doc_qa_simple`.
- [ ] Add dynamic visibility tests proving recall/search disappears after its result while create remains.
- [ ] Implement policy and boundary integration.
- [ ] Ensure trace includes retrieval budget, consumed count, and budget decision reason.
- [ ] Run:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_task_plan_context_budget.py \
  tests/test_tool_ledger.py \
  tests/test_tool_boundary_manager.py \
  tests/test_task_plan_boundary.py -q
```

Expected: PASS.

---

## Task 5: Make TaskPlan Completion Action-Aware

**Files:**

- Modify: `agent/policies/task_plan_completion.py`
- Modify: `agent/policies/turn_completion.py`
- Modify: `tests/test_task_plan_completion.py`
- Modify: `tests/test_turn_completion_policy.py`

**Interface change:**

```python
class TaskPlanCompletionPolicy:
    def evaluate(
        self,
        *,
        contract: TaskPlanTurnContract | None,
        ledger: ToolCallLedger,
        tool_capabilities: Mapping[str, frozenset[str]],
    ) -> TurnCompletionDecision | None: ...
```

Completion rules:

- Inactive/no contract -> no TaskPlan decision.
- A completion record is successful only when `record.execution_status == "success"` and `record.result_ok is True`; parsed result content alone is insufficient.
- `plan_create` -> final-only only after a successful tool record whose registry metadata includes `task_plan.create`.
- `plan_inspect` -> final-only only after a successful tool record whose registry metadata includes `task_plan.inspect`.
- `plan_update` -> final-only only after a successful tool record whose registry metadata includes `task_plan.update`.
- Background passthrough has no active contract and therefore no TaskPlan completion decision.
- Retrieval success never triggers final-only.
- In an update turn, a successful inspect may precede update but must not end the turn.
- Failed or malformed result from a completion-capable tool does not trigger final-only.
- For an active TaskPlan contract, completion-capability evaluation occurs before the generic `local_source_allowed` early return; strict TaskPlan scope has already denied local-source execution.

### Steps

- [ ] Replace the current any-TaskPlan-tool parameterized test with action/completion-capability matrix tests.
- [ ] Add the critical regression:

```python
def test_update_contract_does_not_finish_after_inspect_success(): ...
```

- [ ] Add contextual-create test: recall success does not finish; create success does.
- [ ] Add a capability-provider test proving an alternate registered tool with `task_plan.update` can satisfy update completion without hard-coding `update_task_step` in the policy.
- [ ] Add completion-capable hook-denied and executor-error records whose payload text is `{"ok": true}`; neither may trigger final-only because `execution_status != "success"`.
- [ ] Add inactive-background-passthrough and no-contract tests. Invalid action/completion-capability combinations are rejected by the contract constructor in Task 1 and never reach completion evaluation.
- [ ] Update `TurnCompletionController.evaluate()` to accept `task_plan_contract` and `tool_capabilities`, then pass both to the policy.
- [ ] Run:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_task_plan_completion.py \
  tests/test_turn_completion_policy.py -q
```

Expected: PASS with all existing Document RAG completion tests unchanged.

---

## Task 6: Integrate Contract And Capabilities Into DefaultReasoner

**Files:**

- Modify: `agent/core/passive_turn.py`
- Modify: `agent/policies/tool_boundary.py`
- Modify: `tests/test_tool_access_gateway_reasoner.py`
- Modify: `tests/test_turn_completion_reasoner.py` only for compatibility if required.

**Narrow integration points:**

1. At turn setup, always read registered names and `ToolRegistry.get_capabilities_by_name()`, then build `ToolAccessContext` and evaluate the access plan regardless of `tool_search_enabled`.
2. Set `ToolAccessContext.tool_discovery_enabled` from configuration. When discovery is enabled, visibility keeps the existing `always_on + LRU + policy additions - suppressions` behavior.
3. When discovery is disabled and the access plan is non-strict, preserve the current path exactly: expose all registered tools, pass no `ToolBoundaryContext` into `run()`, and do not activate generic budget/evidence/completion behavior that was previously absent.
4. When discovery is disabled and `strict_capability_scope=True`, build/pass the `ToolBoundaryContext`, compute visibility from all registered tools plus policy additions minus strict suppressions, and enforce TaskPlan access/budget/completion normally.
5. `DefaultReasoner.run()` initialization must honor a non-`None` `initial_visible_names` even when deferred tool discovery is disabled; `None` retains backward-compatible all-schema behavior for direct callers that do not build an enforced boundary context.
6. `TurnToolBoundaryManager.build_context()` copies `access_plan.task_plan_contract` directly into `ToolBoundaryContext`; it never parses `policy_metadata`.
7. For active create/inspect/update contracts, boundary intent is `task_plan_state` even when the plan topic contains Document RAG or source-code words. Background passthrough and ordinary turns retain normal intent inference.
8. After every allowed tool attempt, record `exec_result.status` in the ledger. For retrieval, update the access plan/visibility immediately afterward, then run evidence/completion assessment or advance to the next same-batch tool.
9. Both completion-controller call sites receive `task_plan_contract=tool_boundary_context.task_plan_contract` and the protected registry capability mapping from `tool_boundary_context.access_context`.
10. Boundary trace adds JSON-safe `task_plan_contract`, required/resolved/optional-missing capabilities, retrieval budget, retrieval count, completion capability, and resolved completion-provider tool names.
11. `retry_trace` exposes this trace unchanged.
12. Fix final-only scheduling logs:
   - Document RAG proactive finalization keeps `[react_boundary] final_only reason=...`.
   - TaskPlan finalization logs `[turn_completion] scheduled final_only reason=task_plan_tool_complete`.
   - Do not log `evidence_incomplete` or `non_doc_rag_intent` as the reason a TaskPlan turn entered final-only.

### Reasoner tests

- [ ] Pure create: first model call sees only `create_task_plan` (plus no unrelated tool schema), then final call uses `tools=[]`.
- [ ] Hard-call memory in pure create: `recall_memory` does not execute and returns `tool_blocked_by_task_plan_policy`.
- [ ] Memory create with retrieval chosen: `recall_memory` executes once; next call no longer sees recall/search and does see create; create success leads to final-only.
- [ ] Same-batch memory escalation: `recall_memory + search_messages` executes only recall; search is blocked before execution; create remains available.
- [ ] Same-batch memory repetition: `recall_memory + recall_memory` executes exactly one real retrieval; the second call is soft-stopped with `task_plan_context_budget_exhausted` after the first consumes the budget.
- [ ] Same-batch history repetition: `search_messages + search_messages` executes exactly one real retrieval.
- [ ] Same-batch failed retrieval: returned `{ok:false}` and executor-error variants each consume the budget and prevent the second identical call from executing.
- [ ] Completion-capable denied/error execution: even if output text parses as `{ok:true}`, no TaskPlan final-only is scheduled.
- [ ] Memory create with sufficient existing context: model may call create directly; retrieval is not forced.
- [ ] Session-history create with retrieval chosen: `search_messages` executes once using protected current session; no `recall_memory/fetch_messages`; create success leads to final-only.
- [ ] Session-history create with sufficient current history: model may call create directly; retrieval is not forced.
- [ ] Update with inspect-first: inspect executes, tools remain available, update executes, only then final-only.
- [ ] Inspect direct: inspect then final-only.
- [ ] Explicit background start: `spawn` remains available through non-strict passthrough; TaskPlan contract/completion are absent.
- [ ] Explicit background observe/output/cancel: `spawn_manage` and, for output only, `task_output` remain available; TaskPlan contract/completion are absent.
- [ ] Mixed Document RAG topic + plan create: no RAG schema and no memory schema unless explicitly requested.
- [ ] Discovery disabled + pure create: only `create_task_plan` is visible and unrelated hard calls are blocked.
- [ ] Discovery disabled + update: inspect/update scope is preserved and completion still requires `task_plan.update`.
- [ ] Discovery disabled + ordinary non-TaskPlan prompt: all registered tools remain visible and no generic access/budget/completion boundary is newly activated, preserving existing behavior.
- [ ] Discovery disabled + background prompt: background passthrough does not accidentally activate TaskPlan strict scope.
- [ ] Missing required capability: no unrelated tools reopen, and the model receives the TaskPlan service-unavailable hint.
- [ ] Trace-only metadata tampering cannot change the typed runtime contract used by boundary or completion.
- [ ] Trace assertions cover contract and retrieval fields.
- [ ] Log assertion proves actual completion reason is used.

Run targeted reasoner suite:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_tool_access_gateway_reasoner.py \
  tests/test_turn_completion_reasoner.py \
  tests/test_tool_boundary_reasoner.py -q
```

Expected: PASS.

---

## Task 7: Compatibility, Documentation, And Live Smoke

### Automated regression

Run TaskPlan/capability focused suites:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_task_plan_contract.py \
  tests/test_task_plan_context_budget.py \
  tests/test_task_plan_boundary.py \
  tests/test_task_plan_completion.py \
  tests/test_task_plan_tools.py \
  tests/test_task_plan_toolset.py \
  tests/test_task_plan_gateway.py \
  tests/test_task_plan_context.py \
  tests/test_tool_access_types.py \
  tests/test_tool_access_gateway.py \
  tests/test_tool_ledger.py \
  tests/test_tool_boundary_manager.py \
  tests/test_message_lookup_tool.py \
  tests/test_tool_access_gateway_reasoner.py -q
```

Run compatibility suites:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_doc_rag_intent_preload.py \
  tests/test_turn_completion_policy.py \
  tests/test_turn_completion_reasoner.py \
  tests/test_react_boundary.py \
  tests/test_evidence_contract.py \
  tests/test_turn_trace_tool.py \
  tests/test_turn_trace_reasoner.py \
  tests/test_loop_tool_visibility.py \
  tests/test_spawn_tool.py \
  tests/test_bootstrap_toolsets_p1.py \
  tests/test_bootstrap_wiring_p2.py \
  tests/test_runtime_smoke.py -q
```

Run full verification:

```bash
uv run --with pytest --with pytest-asyncio pytest -q
git diff --check
uv run python -m compileall \
  agent/policies/task_plan_contract.py \
  agent/policies/task_plan_context_budget.py \
  agent/policies/task_plan_boundary.py \
  agent/policies/task_plan_completion.py \
  agent/policies/tool_access.py \
  agent/policies/tool_boundary.py \
  agent/policies/turn_completion.py \
  agent/core/passive_turn.py
```

Record exact counts and warnings. The baseline before this plan is `1481 passed, 3 warnings`.

### Documentation

After automated implementation, update:

- `my_md/local_agent/02-task-plan-first-phase-design.md`
- `my_md/local_agent/README.md`
- `my_md/governance/01-issue-index.md`
- `my_md/governance/02-current-issues.md` (`LA-001`)
- `my_md/governance/03-domain-evolution.md`
- `my_md/governance/04-fix-roadmap.md`
- `my_md/governance/05-design-decisions.md` (`DD-004` status)
- `my_md/governance/06-star-log.md` (`CASE-004`)
- `progress.md`

Do not mark `LA-001` fixed until real CLI smoke passes.

### Real CLI smoke

Restart Agent, then use a unique session:

```bash
uv run python main.py

AKASHIC_CLI_SESSION=taskplan-context-scope-20260714 \
uv run python main.py cli
```

Run in the same CLI session:

```text
为修复 Document RAG 成本问题制定一个三步计划，只创建计划，不执行任务
当前任务做到哪一步了？
把第一步标记为完成，说明已经查看日志
查看后台任务状态
```

Run contextual creation in separate unique sessions to avoid active-task conflict. Seed each source first so the retrieval path has real data. Use unique markers so the result can be distinguished from passive prompt context.

Preference session:

```text
请记住：我的本地 Agent 计划偏好是先写验收标准，标记 LA001-PREF-SEED-20260714。
请先从长期记忆检索 LA001-PREF-SEED-20260714，再结合该偏好为本地 Agent 下一阶段制定一个三步计划，只创建计划。
```

Wait until the memory ingestion path has committed the seed before issuing the second prompt. Verify the seed is returned by the real `recall_memory` result, not only present in passive profile text.

History session:

```text
我们上次讨论决定 TaskPlan 先验证边界再优化提示词，标记 LA001-HISTORY-SEED-20260714。这条消息只用于记录约定，请回复已记录。
请先搜索本会话历史中的 LA001-HISTORY-SEED-20260714，再按照这项约定制定一个三步计划，只创建计划。
```

The history seed and history-plan prompt must use the same `AKASHIC_CLI_SESSION`. Inspect the returned `search_messages` payload and confirm every hit uses that protected current-session key.

Acceptance:

| Case | Allowed real chain | Maximum ReAct | Forbidden real tools |
| --- | --- | ---: | --- |
| pure create | `create_task_plan -> final` | 2 | memory, history, spawn, RAG, local |
| inspect | `inspect_task_plan -> final` | 2 | memory, history, spawn |
| update | `update_task_step -> final`, or inspect then update then final | 2-3 | memory, history, spawn |
| background observe | `spawn_manage -> final` | 2-3 | TaskPlan tools; TaskPlan strict/completion must be absent |
| seeded preference create | exactly one `recall_memory` -> `create_task_plan -> final` | 3 | search/fetch messages, RAG, local, spawn |
| seeded history create | exactly one `search_messages` (protected current session) -> `create_task_plan -> final` | 3 | recall/fetch messages, RAG, local, spawn |

Natural-language contextual prompts may still skip retrieval when passive/current context is sufficient; that optional path is covered separately by reasoner tests. The two seeded prompts above deliberately say "先检索/先搜索" and are the live gates for actual one-shot retrieval and dynamic retirement. If either seeded case skips retrieval, do not claim the retrieval path live-verified; record the model behavior and keep `LA-001` partially verified.

Database and observe checks:

```bash
sqlite3 /home/jjh/.akashic/workspace/task_plans.db \
  'SELECT task_id, session_key, title, status, updated_at FROM task_plans ORDER BY updated_at DESC LIMIT 8;'

sqlite3 /home/jjh/.akashic/workspace/observe/observe.db \
  'SELECT id, ts, session_key, user_msg, error, react_iteration_count, prompt_tokens, tool_calls FROM turns ORDER BY id DESC LIMIT 12;'
```

Expected log fields:

```text
task_plan_action
context_requirement
required_capabilities
allowed_capabilities
resolved_capabilities
optional_capability_unavailable
retrieval_budget
retrieval_count
completion_capability
completion_provider_tools
completion_reason
tool_discovery_enabled
strict_capability_scope
```

Only after all six live cases pass should `LA-001` move from `open` to `fixed/verified`.

---

## Self-Review Checklist

- [x] Pure planning does not infer context need from topic words.
- [x] Explicit preference and session-history prompts preserve useful retrieval.
- [x] No-retrieval language wins over retrieval cues.
- [x] Capability scope is strict only for active TaskPlan contracts.
- [x] TaskPlan access planning is independent of `tool_search_enabled`; discovery-disabled ordinary turns still expose all registered tools without newly activating generic boundary behavior.
- [x] Capability declarations are registry metadata and never leak into model schemas.
- [x] Required capability absence fails closed; optional capability absence degrades without reopening unrelated tools.
- [x] Runtime authorization/completion reads the typed contract, never trace metadata.
- [x] Disabled tools and registered-tool filtering remain higher-priority constraints.
- [x] `tool_search` cannot reopen disallowed tools.
- [x] Same-batch repeated retrieval executes only once.
- [x] Cross-family retrieval remains blocked by the original strict scope.
- [x] Returned failure, hook denial, and executor error consume the one-shot budget after access permits the call.
- [x] Update turns do not finish after inspect.
- [x] Background start/observe/output/cancel turns remain non-strict passthrough and do not use TaskPlan completion.
- [x] TaskPlan final-only logs the actual completion reason.
- [x] No TaskPlan policy state is written to LRU/discovery.
- [x] Passive memory prompt injection remains out of scope and unchanged.
- [x] Session-history search uses protected current-session context and cannot be redirected by model arguments.
- [x] Document RAG, Turn Trace, CLI session, and memory-after-doc-LRU regressions pass.
- [x] Documentation distinguishes implemented behavior from proposed/live-verified behavior.

## Execution Order

Execute Tasks 1 through 7 sequentially. Tasks 1-3 establish contract and access semantics; Task 4 depends on those types; Task 5 depends on the contract; Task 6 integrates all components; Task 7 is the release gate. Do not parallelize Tasks 1-6 because they modify shared policy types and tests.
