# Document RAG P10a Intent Preload Plan

## Goal

Implement turn-local Document RAG tool intent preload without changing always-on policy or writing intent decisions to `ToolDiscoveryState` / LRU.

## Phases

1. Research project context and P10a requirements - complete
2. Add failing tests for pure intent rules and run_turn visibility behavior - complete
3. Implement `agent/policies/doc_rag_intent.py` and integrate in `DefaultReasoner.run_turn()` - complete
4. Run focused pytest and debug failures - complete
5. Update `my_md` governance/RAG docs - complete
6. Final verification and summary - complete

## Constraints

- Do not modify Document RAG always-on strategy.
- Do not write intent preloads into `ToolDiscoveryState` / LRU.
- Suppress `search_docs` / `fetch_doc_chunk` LRU residue only for the current turn when the user asks a strong memory/session question without strong document intent.
- Keep rules conservative and deterministic.

## Errors Encountered

| Error | Attempt | Resolution |
| --- | --- | --- |

## 2026-07-15 Documentation Addendum

Goal: record the restarted main-service TaskPlan smoke, keep LA-001 evidence boundaries accurate, and register the next architectural gap without changing implementation.

1. Verify main-service process, logs, observe turns, and TaskPlan SQLite state - complete
2. Update Local Agent, governance, STAR, interview, findings, and progress documents - complete
3. Register LA-002 recovery/execution orchestration as open planning work - complete
4. Run documentation consistency and diff checks - complete

## LA-002 Design Document

Goal: produce a reviewable design for recoverable, idempotent, single-step TaskPlan execution without implementing runtime behavior.

1. Inspect current TaskPlan, Tool Gateway, Boundary, Completion, channel identity, and runtime wiring - complete
2. Define attempt state machine, transaction invariants, recovery semantics, and authorization boundary - complete
3. Write `my_md/local_agent/03-task-plan-recovery-execution-design.md` and update indexes - complete
4. Self-review placeholders, contradictions, scope, security claims, and acceptance criteria - complete
5. Run documentation checks and commit the design - complete

## LA-002 Implementation Plan

Goal: turn the approved LA-002 design into a complete, TDD-oriented, file-level implementation plan without changing business code.

1. Record approved product decisions in the design/governance docs - complete
2. Map exact files, interfaces, migrations, and tests for LA-002a/LA-002b - complete
3. Write `docs/superpowers/plans/2026-07-15-task-plan-recovery-execution-implementation.md` - complete
4. Self-review spec coverage, placeholders, and type consistency - complete
5. Run plan checks and commit the approved design plus implementation plan - complete
