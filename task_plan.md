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

## LA-002 Task 10 Verification and Documentation

Goal: verify the reviewed LA-002 implementation end to end with an isolated Agent, preserve exact evidence, update facts-only documentation, and commit only Task 10 verification/documentation files.

1. Inspect runtime/configuration/documentation surfaces and protect existing user changes - complete
2. Run focused, compatibility, full pytest, compileall, and diff gates - complete
3. Run isolated live CLI/replay/restart/defer/finalizer smoke and clean up only its process - complete
4. Write `.superpowers/sdd/task-10-report.md` and update LA-002 documentation with measured facts - complete
5. Self-review, independent review, rerun final gates, stage only Task 10 files, and commit - complete

Final post-review gates: focused `195 passed in 9.34s`; compatibility `278 passed in 9.18s`; full pytest `1844 passed, 3 warnings in 48.12s`; prescribed compileall and `git diff --check` exited `0`.

### Task 10 Constraints

- Do not modify or stage `findings.md`, `my_md/interview/08-architecture-diagram.md`, or `my_test_py/`.
- Do not stop, signal, replace, or reuse the existing Agent process, socket, workspace, database, or dashboard port.
- Use a unique isolated config/workspace/SQLite/socket/dashboard port with `task_execution.enabled=true`.
- Do not claim live-provider evidence when credentials are unavailable; preserve real turn/request/attempt identifiers only.
- Side-effect execution remains unimplemented and must not be documented as implemented.

### Task 10 Errors Encountered

| Error | Attempt | Resolution |
| --- | --- | --- |
| Full pytest reported one stale CLI-frame assertion and three stale spawn read-result assertions | 1 | Confirmed against introducing commits `4627658` and `173b904`; updated compatibility tests to assert UUID presence and structured `ToolResult` fields, then reran focused cases/full suite. |
| Temporary isolated launcher could not import `bootstrap` because Python used `/tmp/akashic-task10-20260715` as `sys.path[0]` | 1 | Process exited before binding any resource; relaunched with `PYTHONPATH=/home/jjh/git_work/akashic-agent`. |
| Controlled recovery helper passed a string to `TaskPlanStore`, which requires `Path` | 1 | Helper exited before SQLite mutation; wrapped the database path with `Path(...)` and reran. |
| `codex review --uncommitted <prompt>` rejected the documented option/prompt combination | 1 | No review ran; use an ephemeral `codex exec` reviewer with read-only sandbox and the same constrained file list. |
| `codex exec` rejected subcommand-local `-a never` | 1 | No review ran; place the approval policy before the `exec` subcommand for this CLI build. |
| First read-only reviewer stayed idle without producing a final assessment | 1 | Terminated only owned reviewer PID `447772` after bounded wait; rerun with stdin explicitly closed and a bounded command timeout. |
| Second reviewer inspected the diff but timed out before writing a final verdict | 1 | Preserve its requested-column scope question; run a smaller read-only review over a generated in-scope patch plus brief/report. |

## 2026-07-16 Independent Isolated Live Smoke

Goal: start a fresh isolated Agent and IPC session from the final LA-002 code, verify real-provider execution and replay behavior, then clean up only isolated resources.

1. Create fresh config/workspace/socket/dashboard/client/session identities - complete
2. Start isolated server and verify protected Agent isolation - complete
3. Run create/continue/replay/new-request and restart/retry session flows - complete
4. Validate logs and SQLite attempts/events - complete
5. Stop isolated server, verify cleanup, and record measured evidence - complete

Constraints: do not reuse or signal PID `372968`, `/tmp/akashic.sock`, port `2236`, or the prior Task 10 database/session; do not modify or stage user-owned dirty files.

Result: fresh PIDs `508645/509279`, socket `/tmp/akashic-la002-final-20260716.sock`, dashboard `2248`, and two new sessions produced `3 succeeded / 1 blocked / 0 active` attempts. Duplicate request `222...` executed zero tools and added no row; restart blocked attempt `555...`, ordinary continue added no attempt, and explicit retry `777...` created only attempt 2. Six observe turns had no error. Final-only literal DSML appeared on replay and after successful retry, confirming a provider reply-normalization follow-up beyond replay-only scope.
