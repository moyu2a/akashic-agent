# Document RAG P10a Intent Preload Plan

## 2026-07-28 Memory Tri Answer Contract Implementation Plan

Goal: create an executable plan for eval-only `chain_tri_answer_contract`, testing whether structured evidence injection and answer constraints can fix tri retrieval's post-grounding answer-quality failures.

1. Inspect current `memory-next` eval/profile/report entry points - complete
2. Write `docs/superpowers/plans/2026-07-28-memory-tri-answer-contract.md` - complete
3. Self-review the plan for scope, placeholders, interfaces, and verification gates - complete
4. Hand off execution choice to user - complete

Boundary:

- Planning only; no implementation code changed.
- Plan keeps production `AgentLoop`, `Reasoner`, `ToolExecutor`, memory writes, production prompt behavior, and old `Retriever.retrieve()` contract unchanged.
- Plan file is under ignored `docs/`; use `git add -f` only if the plan should be committed.

## 2026-07-28 Memory Tri Retrieval Failure Attribution

Goal: explain why `chain_tri_retrieval` in the route-governed small online run has `100%` grounding but only `42.5%` answer pass rate, without rerunning real LLM or changing production behavior.

1. Add tri retrieval failure attribution module and tests - complete
2. Add report writers and CLI wrapper - complete
3. Generate `tri_retrieval_failure_attribution_v1` from `route_governance_small_online_v1` - complete
4. Update memory optimization docs with metrics, result, and next decisions - complete
5. Run focused regression, compile, and diff checks - complete
6. Commit locally without push - complete

Inputs:

- `my_md/memory_optimization/eval_reports/route_governance_small_online_v1/memory_comprehensive_online_eval.json`

Outputs:

- `my_md/memory_optimization/eval_reports/tri_retrieval_failure_attribution_v1/tri_retrieval_failure_attribution.json`
- `my_md/memory_optimization/eval_reports/tri_retrieval_failure_attribution_v1/tri_retrieval_failure_attribution.md`

Boundary:

- No real LLM rerun.
- No production `AgentLoop`, `Reasoner`, `ToolExecutor`, memory write, retrieval, or prompt change.
- Reports omit raw prompt, raw memory summary, session text, and full answers.

Current result:

- `tri_case_count = 40`
- `tri_answer_fail_count = 23`
- `tri_grounding_fail_count = 0`
- `tri_grounded_answer_fail_count_any = 23`
- `tri_grounded_non_forbidden_answer_fail_count = 18`
- `tri_forbidden_fail_count = 5`
- `baseline_passed_but_tri_failed_count = 5`
- `baseline_failed_but_tri_passed_count = 9`
- `tri_failed_but_rerank_passed_count = 7`

Current conclusion:

- Tri retrieval's current small-online bottleneck is not recall coverage. The failures are after grounding: evidence use, noise, answer constraints, and forbidden governance.
- Next decision: if later cumulative profile rescue remains high, validate `route + tri + graph/rerank/injection`; otherwise prioritize candidate denoising, forbidden filtering, and scenario routing.

Verification:

- `tests/test_memory_tri_retrieval_failure_attribution.py tests/test_memory_online_failure_attribution.py tests/test_memory_comprehensive_online_eval.py` -> `24 passed`.
- `compileall -q memory2 scripts tests` -> passed.
- `git diff --check` -> passed.

Commit:

- Local commit created; not pushed.

## 2026-07-27 Memory Tri Retrieval Route Governance

Goal: turn tri retrieval / graph retrieval from global always-on enhancements into scene-routed candidate governance, while preserving the existing AgentLoop, Reasoner, ToolExecutor, production write path, and old `retrieve()` return contract.

1. Add retrieval governance pure functions for scene classification, route policy, lane caps, source/scope/low-confidence filtering, and trace output - complete
2. Reuse the same governance helper in offline eval, quantitative uplift, retriever trace, and default memory engine trace - complete
3. Add route governance CLI/report and focused tests - complete
4. Generate route governance reports and update memory/governance docs - complete
5. Run focused regression, compile, and diff checks - complete
6. Commit when verification is complete - pending

Results so far:

- New route governance module: `memory2/retrieval_governance.py`.
- New report path:
  - `my_md/memory_optimization/eval_reports/memory_route_governance_eval.json`
  - `my_md/memory_optimization/eval_reports/memory_route_governance_eval.md`
- Offline route report:
  - `offline_case_count = 320`
  - `offline_scene_count = 5`
  - all offline scenes currently show `expected_route_hit_rate = 100%`
  - candidate drop rate ranges from `63.3933%` to `77.085%`
- Live engine route smoke:
  - `live_case_count = 9`
  - only validates real `DefaultMemoryEngine.retrieve()` route trace wiring
  - does not prove real LLM answer-quality uplift
- Review follow-up:
  - offline eval now applies route governance once across all lanes, matching real retriever duplicate and lane precedence behavior;
  - reports split `expected_route_hit_rate` from `candidate_accept_rate`;
  - focused verification after fixes: `88 passed`, `compileall` exit `0`, `git diff --check` exit `0`.

Current conclusion:

- Tri retrieval and graph retrieval should not be interpreted as global default-on modules.
- The current implementation improves candidate boundaries and traceability.
- The next trustworthy answer-quality conclusion requires more realistic live fixtures and a fresh bounded LLM rerun for tri/graph/rerank paths.

## 2026-07-26 Memory Online Attribution And Version Grounding Plan

Goal: create a reproducible online answer-quality failure attribution report and fix the `chain_version_provenance` grounding metric before spending more real LLM calls.

1. Write implementation plan for online failure attribution and version grounding repair - complete
2. Review the plan before execution - complete
3. Implement Task 1 online failure attribution report - complete
4. Implement Task 2 profile-aware version/provenance grounding fix - complete
5. Rebuild checkpoint/fake-provider reports and update docs - complete
6. Run final regression and commit - complete

Plan:

- `docs/superpowers/plans/2026-07-26-memory-online-attribution-version-grounding.md`

Current inputs:

- Real LLM full answer-quality report:
  - `/tmp/akashic-memory-answer-quality-real-full-v1/reports/memory_comprehensive_online_eval.json`
  - `/tmp/akashic-memory-answer-quality-real-full-v1/checkpoint-report/memory_comprehensive_online_eval.json`
- Current online result:
  - `chain_memory_base answer_rate = 42.1875%`, grounding `96.25%`, forbidden `12.1875%`;
  - `chain_tri_retrieval answer_rate = 28.4375%`, grounding `100%`, forbidden `30%`;
  - `chain_graph_retrieval answer_rate = 26.25%`, grounding `100%`, forbidden `29.6875%`;
  - `chain_rerank_injection answer_rate = 39.6875%`, grounding `100%`, forbidden `9.6875%`;
  - `chain_version_provenance answer_rate = 40.3125%`, grounding `0%`, forbidden `0.9375%`;
  - `chain_all_on answer_rate = 23.4375%`, grounding `100%`, forbidden `24.6875%`.

Working hypothesis:

- The first issue is not raw recall shortage. Tri/graph retrieve evidence but increase forbidden/noise, hurting final answers.
- The second issue is likely evaluation-side grounding mismatch for `chain_version_provenance`: generic answer expectations include both target and graph ids, while the version/provenance evidence source intentionally uses `version_chain.active_leaf_ids`.

Plan review result:

- Independent review verdict: required revision before execution.
- Critical fix applied: historical checkpoint rows already contain final `memory_grounding_passed` booleans, so checkpoint-only rebuilds cannot prove a scorer fix or change old `chain_version_provenance` grounding values.
- Important fix applied: Task 2 tests now require a fresh fake-provider/evaluation path that exercises scoring, not a hand-written checkpoint row with `memory_grounding_passed=True`.
- Important fix applied: Task 1 CLI now explicitly supports both report JSON and checkpoint JSONL, matching the stated input boundary.
- Minor fix applied: Task 1 attribution now includes paired comparison against matching `chain_memory_base` rows and failure-code distribution / examples should be produced during implementation.

Task 1 result:

- Added `memory2/eval_online_failure_attribution.py`, `scripts/run_memory_online_failure_attribution.py`, and `tests/test_memory_online_failure_attribution.py`.
- Focused test: `tests/test_memory_online_failure_attribution.py` -> `4 passed`.
- Generated report:
  - `my_md/memory_optimization/eval_reports/online_failure_attribution/online_failure_attribution.json`
  - `my_md/memory_optimization/eval_reports/online_failure_attribution/online_failure_attribution.md`
- Historical real LLM attribution summary:
  - `chain_tri_retrieval`: 229 answer failures, 0 grounding failures, 96 forbidden failures, 78 forbidden introduced vs baseline;
  - `chain_graph_retrieval`: 236 answer failures, 0 grounding failures, 95 forbidden failures, 82 forbidden introduced vs baseline;
  - `chain_rerank_injection`: 193 answer failures, 0 grounding failures, 31 forbidden failures, 15 forbidden introduced vs baseline;
  - `chain_version_provenance`: 191 answer failures, 320 grounding failures, 3 forbidden failures, 320 `missing_expected_memory_ids`.

Task 2 result:

- Added profile-aware answer expectations in `memory2/eval_comprehensive_online.py`.
- `chain_version_provenance` now scores grounding against `expected_active_version_ids` when those ids exist.
- This aligns scoring with the profile's evidence source, `version_chain_shadow.active_leaf_ids`.
- Added regression tests in `tests/test_memory_comprehensive_online_eval.py`:
  - `test_version_provenance_grounding_uses_active_version_ids`
  - `test_version_provenance_online_scoring_not_forced_to_graph_ids`
- Focused verification:
  - `tests/test_memory_comprehensive_online_eval.py` -> `16 passed`.
- Report rebuild / validation:
  - historical checkpoint-only report written to `my_md/memory_optimization/eval_reports/answer_quality_real_full_after_version_grounding_fix/`;
  - it still shows historical `chain_version_provenance grounding = 0.0%`, which is expected because checkpoint rows already store old `memory_grounding_passed` values;
  - fresh fake-provider scorer validation written to `my_md/memory_optimization/eval_reports/version_grounding_fake_validation/`;
  - 20-case slice shows `chain_memory_base grounding = 20/20 = 100.0%` and `chain_version_provenance grounding = 20/20 = 100.0%`.
- Small real LLM smoke recorded for later reference:
  - `/tmp/akashic-memory-version-grounding-smoke/reports/memory_comprehensive_online_eval.{json,md}`;
  - `case_count = 10`, `unique_case_count = 5`, `profile_count = 2`;
  - `chain_memory_base answer_rate = 60%`, `chain_version_provenance answer_rate = 80%`;
  - both profiles had `grounding_rate = 100%` and `forbidden_rate = 0%`.

Current conclusion:

- The old real report's version-chain grounding failure is explained by an evaluation-side expected-id mismatch.
- The scorer path for future runs is fixed.
- Old checkpoint-only reports remain historical evidence and must not be used to claim the fix changed old real percentages.
- The next trustworthy real number requires a bounded fresh real LLM rerun for `chain_version_provenance` after this fix.
- The new smoke is only a gate check and should not be promoted to the final online conclusion.

Final verification:

- `PYTHONDONTWRITEBYTECODE=1 /home/jjh/git_work/akashic-agent/.worktrees/memory-experiments-phase0/.venv/bin/python -m pytest tests/test_memory_online_failure_attribution.py tests/test_memory_comprehensive_online_eval.py tests/test_memory_target_metrics.py tests/test_memory_answer_retrieval_counts.py -q -p no:cacheprovider` -> `42 passed in 116.97s`.
- `git diff --check` -> passed.

Constraints:

- Do not change production `AgentLoop`, `Reasoner`, `ToolExecutor`, memory writes, or production prompt behavior.
- Do not run a new full real LLM matrix until checkpoint/fake-provider verification is complete.
- Keep all-on labeled as `combo/check`.
- Do not push without explicit user instruction.

## 2026-07-26 Memory Next Post-Merge Regression Repair

Goal: repair post-merge regressions on `memory-next` so dashboard / memory_rollup tests, Markdown consolidation tests, and memory quantitative expectations run reliably in the current Python 3.14 test environment.

1. Confirm current worktree and preserve existing dirty changes - complete
2. Reproduce and isolate dashboard startup delay - complete
3. Disable implicit `npx` plugin-panel compilation unless explicitly enabled - complete
4. Reproduce and isolate Markdown consolidation hang - complete
5. Replace local Markdown `asyncio.to_thread()` file calls with a synchronous async helper - complete
6. Replace hanging Starlette `TestClient` usages in dashboard tests with a test-only ASGI client - complete
7. Add the `httpx2` dev dependency and update `uv.lock` - complete
8. Synchronize memory quantitative expected totals with current write-governance semantics - complete
9. Run focused and broad regression verification - complete
10. Commit and push - pending user instruction

Results:

- Dashboard / rollup target: `31 passed in 9.21s`.
- Combined dashboard / memory engine / quantitative target: `83 passed in 12.93s`.
- Memory engine / quantitative group: `91 passed in 29.00s`.
- Memory enhancement group: `86 passed in 111.05s`.
- Tool governance group: `293 passed, 2 warnings in 3.27s`.
- `git diff --check`: exit `0`.

Constraints:

- Do not push without explicit user instruction.
- Keep the dashboard ASGI replacement test-only.
- Do not enable network-backed `npx` compilation during ordinary dashboard app startup.
- Do not reinterpret the current `all_on` score as a regression unless write-governance semantics change again.

Errors Encountered:

| Error | Attempt | Resolution |
| --- | --- | --- |
| Dashboard app creation waited on `npx --yes esbuild` for plugins without local esbuild | 1 | Added explicit `AKASHIC_DASHBOARD_COMPILE_PLUGINS` gate for npx fallback and queued pending panels by default. |
| Markdown consolidation test hung around async thread cleanup | 1 | Replaced local Markdown `asyncio.to_thread()` calls with `_run_blocking_io()`. |
| FastAPI `TestClient` hung in anyio blocking portal | 1 | Added `tests/asgi_client.py` using `httpx2.AsyncClient` with `ASGITransport`. |
| Sync dashboard endpoints still entered threadpool under ASGI transport | 1 | Wrapped sync FastAPI route calls as async handlers and updated the route coroutine flag. |
| Background optimizer test lost task state across requests | 1 | Kept a per-client event loop for the test client lifetime and drained pending tasks on close. |
| Parallel dashboard request test hit event-loop reentrancy | 1 | Added a per-client lock to serialize calls through the shared sync test client. |

## Goal

Implement turn-local Document RAG tool intent preload without changing always-on policy or writing intent decisions to `ToolDiscoveryState` / LRU.

## 2026-07-22 Memory Phase 6s Sleep Hygiene Source-Backed Evidence

Goal: add a source-backed sleep hygiene evaluation path that proves cleanup and review candidates can be traced to real `SessionStore` messages, while keeping sleep consolidation shadow-only and non-mutating.

1. Add source evidence aggregate metrics and Markdown source tables - complete
2. Add deterministic `SessionStore` fixture builder - complete
3. Add CLI fixture mode and generate `sleep_hygiene_source_backed_v1` report - complete
4. Tighten dry-run patch source safety gate - complete
5. Update memory optimization docs and final verification - in progress

Constraints:

- Do not change `AgentLoop`, `Reasoner`, `ToolExecutor`, production retrieval, prompt injection, or production memory storage.
- Do not merge, delete, supersede, or write real memory rows.
- Keep formal V3 proxy reports reproducible; source-backed fixture report is separate.
- Use counts and percentages rather than opaque scores.
- Do not stage `.superpowers/sdd/*.diff`.

Results so far:

- Commits:
  - `80ba815 feat: add sleep hygiene source evidence metrics`
  - `5be2f78 feat: add sleep hygiene source-backed fixture`
  - `b57baaa feat: add sleep hygiene source-backed report`
  - `fee1d5a feat: gate sleep hygiene patch by source evidence`
- Source-backed report path: `my_md/memory_optimization/eval_reports/sleep_hygiene_source_backed_v1/`.
- Headline metrics:
  - `case_count = 160`
  - `evaluated_evidence_row_count = 200`
  - `source_fetch_mode = session-store`
  - `source_ref_coverage_rate = 81.5%`
  - `source_ref_parse_success_rate = 82.2086%`
  - `source_fetch_success_rate = 36.1963%`
  - `source_support_rate = 18.4049%`
  - `missing_source_count = 75`
  - `unsupported_source_count = 29`
  - `session_ref_not_fetchable_count = 37`
  - `malformed_source_ref_count = 29`
- Dry-run patch source gate:
  - `patch rows = 200`
  - `source_backed_action_safe = 12`
  - `requires_review = 24`
  - `source_not_fetchable = 73`
  - `source_not_supporting_summary = 11`
  - `not_cleanup_candidate = 80`

Errors Encountered:

| Error | Attempt | Resolution |
| --- | --- | --- |
| Source evidence metrics test failed with missing `source_evidence_metrics` | 1 | Added aggregate source metrics, by-action metrics, and Markdown tables. |
| Source fixture tests failed because `memory2.eval_sleep_hygiene_source_fixture` did not exist | 1 | Added deterministic fixture builder backed by real `SessionStore`. |
| CLI fixture test failed because `--source-fixture-mode` and `--source-fixture-db` did not exist | 1 | Added fixture CLI mode and checkpoint source labels. |
| Patch safety test failed because dry-run patch lacked `source_backed_action_safe` | 1 | Added source-backed safety fields and block reasons. |

## 2026-07-24 Memory Answer Quality Real LLM Full Eval

Goal: run the full real LLM recall/answer uplift matrix for the answer-quality table, using original memory as the baseline and keeping write governance / sleep hygiene out of the main answer table.

1. Review and revise the real LLM full-eval plan - complete
2. Preflight case count, provider config, and matrix size - complete
3. Run 10-case real-provider smoke - complete
4. Run full 320-case / 1920-call real LLM matrix with checkpoint/resume - complete
5. Rebuild checkpoint-only report excluding infrastructure failures - complete
6. Extract single-profile uplift and ordered profile comparison tables - complete
7. Update memory optimization docs and persistent progress - in progress
8. Run verification and commit relevant docs - pending

Constraints:

- Use `chain_memory_base` as the original memory baseline.
- Use exactly `chain_memory_base`, `chain_tri_retrieval`, `chain_graph_retrieval`, `chain_rerank_injection`, `chain_version_provenance`, and `chain_all_on`.
- Do not interpret ordered profile comparisons as true cumulative feature toggles.
- Treat `chain_all_on` as compatibility/check evidence; it currently uses sleep-filtered ids.
- Do not write production memory or observe DB.
- Do not copy or commit `/tmp/.../answer_debug`.
- Do not stage `.superpowers/sdd/*.diff` or unrelated dirty files.

Results so far:

- Plan: `docs/superpowers/plans/2026-07-24-memory-answer-quality-real-llm-full-eval.md`.
- Smoke report: `/tmp/akashic-memory-answer-quality-real-smoke-v1/reports`.
- Full report: `/tmp/akashic-memory-answer-quality-real-full-v1/reports`.
- Checkpoint-only report: `/tmp/akashic-memory-answer-quality-real-full-v1/checkpoint-report`.
- Full matrix:
  - `case_count = 1920`;
  - `unique_case_count = 320`;
  - `completed_call_count = 1920`;
  - `checkpoint_input_count = 1920`;
  - `provider_error_count = 0`;
  - `timeout_count = 0`;
  - `excluded_infra_failure_count = 0`;
  - `total_token_count = 10593288`;
  - `avg_latency_ms = 4350.3875`.
- Single-profile answer rates:
  - original memory baseline `42.1875%`;
  - tri retrieval `28.4375%`;
  - graph retrieval `26.25%`;
  - rerank/injection governance `39.6875%`;
  - version/provenance `40.3125%`;
  - all-on check `23.4375%`.
- Current conclusion:
  - recall expansion can improve grounding but hurt final answer quality when noise/forbidden rises;
  - rerank/injection governance is the best enhanced profile in this real matrix;
  - version/provenance grounding mapping needs repair;
  - full all-on should not be the default active strategy without routing and injection tuning.

Errors Encountered:

| Error | Attempt | Resolution |
| --- | --- | --- |
| Independent review found the plan mislabeled ordered profile comparison as cumulative module gain | 1 | Revised the plan wording and table extraction to say ordered profile comparison only. |
| Independent review found `chain_all_on` was described as sleep-free while current code uses sleep-filtered ids | 1 | Revised plan/docs to label `chain_all_on` as compatibility/check evidence. |

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

Post-check note: the protected Agent PID `372968` was verified alive immediately after isolated cleanup, then disappeared together with parent PID `372933`, port 2236, and `/tmp/akashic.sock` before the 09:02 final check. Its file log contains no graceful shutdown or traceback after the 08:00 optimizer entry. No signal was sent to the protected process; cause is external/undetermined and it was not restarted automatically.

## 2026-07-16 Publication And Documentation

1. Verify task-owned commits and exclude user-owned dirty files - complete
2. Push LA-002 implementation and smoke evidence through `c4d3d4c` - complete
3. Update Local Agent status, roadmap order, and publication evidence - complete
4. Commit and push the documentation update - complete

## 2026-07-20 Memory Target Metric Evaluation

Goal: replace broad memory uplift presentation with three target-metric percentage tables, while preserving existing offline and real-LLM checkpoint flows.

1. Update memory optimization docs with the new three-group metric rationale - complete
2. Write and self-review the implementation plan - complete
3. Implement target-metric report code, CLI, and tests - complete
4. Run the report on the existing 80 deterministic cases - complete
5. Record three main result tables and verification evidence - complete

Constraints:

- Do not write production memory DB or observe DB.
- Reuse existing 80 target-oriented cases for the first deterministic report.
- Keep real LLM behind explicit `--enable-real-llm` / checkpoint flow.
- Report percentages, percentage-point deltas, and relative uplift only when the baseline denominator is valid.
- Do not claim production accuracy from offline proxy metrics.

Results so far:

- Plan written: `docs/superpowers/plans/2026-07-20-memory-target-metric-eval.md`.
- Added target metric code: `memory2/eval_target_metrics.py`.
- Added CLI wrapper: `scripts/run_memory_target_metrics_eval.py`.
- Added tests: `tests/test_memory_target_metrics.py`, `tests/test_memory_target_metrics_cli.py`.
- Generated report: `my_md/memory_optimization/eval_reports/memory_target_metrics_eval.json` and `.md`.
- Focused target metric tests: `10 passed in 2.31s`.
- Related memory eval regression: `27 passed in 7.09s`.
- Compileall target check exited `0`.
- `git diff --check` exited `0`.

Errors Encountered:

| Error | Attempt | Resolution |
| --- | --- | --- |
| Initial target metric report used trace-internal baseline recalled ids, so target recall before was already 100% | 1 | Temporarily changed answer/retrieval before values to disabled-module baseline (`0%`) for presentation; this was later superseded by the realistic target-metric phase, which restored real trace baseline values and marked the fixture as insufficiently discriminative. |
| Initial write table showed candidate/scanned counts as case counts | 1 | Added `unit_count` to target metric rows and aggregate candidate/scanned counts separately. |

## 2026-07-20 Memory Realistic Target Metrics

Goal: make target-metric reports more truthful by replacing fixed `before = 0` with real offline baseline trace values, while adding clearly labeled online checkpoint/evidence inputs for all three groups.

1. Write and review a realistic before/after implementation plan - complete
2. Fix plan issues from independent review: paired online rows, source labels, fake-provider separation, and explicit before sources - complete
3. Add failing tests for trace baseline before values, online pairing, and report source labels - complete
4. Implement real offline baseline metrics, online checkpoint rows, write/hygiene evidence rows, and CLI options - complete
5. Regenerate the formal offline report and run fake-provider smoke into `/tmp` only - complete
6. Update memory optimization docs, findings, progress, and task plan - complete
7. Run focused tests, compileall, diff check, and summarize results - complete

Constraints:

- Do not write production memory DB or observe DB.
- Do not label fake-provider smoke as real LLM.
- Do not copy offline values into online rows.
- Online answer rows must pair before/after by `(case_id, prompt_variant, repeat_index)`.
- Formal `my_md` report should remain offline-real-baseline unless a real checkpoint is explicitly supplied.

Results so far:

- Formal report mode is now `offline_trace_real_baseline_target_metrics`.
- `online_status = gated_no_checkpoint` and `online_row_count = 0` for the committed formal report.
- Phase 6f 80-case fixture had target recall `100% -> 100%` for tri retrieval, graph retrieval, and rerank/injection, so it could not prove recall uplift under the realistic baseline. This was superseded by Phase 6g hard-miss cases.
- Version/provenance in Phase 6f reported `100% -> 50%`, exposing an active-leaf / expected-target calibration issue. This was superseded by Phase 6g version-aware metrics.
- Fake-provider smoke verified all three online input paths into `/tmp`, with `online_row_count = 6`.
- Documentation update recorded the current testing result, known issues, and next plan across `README.md`, `01-memory-optimization-roadmap.md`, `02-memory-quality-metrics.md`, `04-memory-plugin-experiment-roadmap.md`, `05-memory-target-metric-eval-plan.md`, `findings.md`, `progress.md`, and this task plan.
- Next implementation step should be version-chain metric/case repair plus harder retrieval cases before spending more real LLM calls.

Errors Encountered:

| Error | Attempt | Resolution |
| --- | --- | --- |
| Initial plan allowed fake-provider checkpoint to be labeled as real LLM and did not require paired online rows | 1 | Independent review found the issue; plan revised to require source labels, fake-provider separation, and `(case_id, prompt_variant, repeat_index)` inner joins. |
| First implementation patch was too large and failed context matching | 1 | Split changes into smaller apply_patch operations. |

## 2026-07-20 Memory Phase 6g Version Metrics And Hard Cases

Goal: fix the target-metric report problems found by realistic baseline evaluation: version/provenance `100% -> 50%` was a metric semantics issue, and retrieval `100% -> 100%` meant the fixture lacked discriminative baseline misses.

1. Write and review the Phase 6g plan - complete
2. Add failing tests for version-aware metrics, hard tri/graph misses, and Markdown exposure - complete
3. Implement explicit `baseline_miss_recall_ids`, version expectation fields, and baseline lane filtering - complete
4. Regenerate `memory_target_metrics_eval.json` and `.md` - complete
5. Update memory optimization docs, findings, progress, and task plan - complete
6. Run focused and final verification - in progress

Constraints:

- Do not call a real LLM.
- Do not write production memory DB or observe DB.
- Do not modify AgentLoop, Reasoner, ToolExecutor, ToolRegistry, or production memory retrieval.
- Keep `online_status = gated_no_checkpoint` in the formal report unless a real checkpoint is explicitly supplied.

Results so far:

- Formal report still uses `measurement_mode = offline_trace_real_baseline_target_metrics`.
- `online_status = gated_no_checkpoint`, `online_row_count = 0`, and `real_llm_used = False`.
- Overall target recall: 三路召回 `93.75% -> 100%`, 图谱召回 `93.75% -> 98.75%`, 重排与注入治理 `93.75% -> 100%`, 版本链与溯源 `90% -> 100%`.
- Hard subset target recall: 三路召回 `87.5% -> 100%`, 图谱召回 `87.5% -> 97.5%`, 版本链当前有效版本 `80% -> 100%`.
- Version metrics now include `current_version_recall_rate`, `stale_version_misuse_rate`, and `conflict_chain_detection_rate`. Conflict-chain detection remains `unavailable` because current fixtures have no forked replacement chain.
- Focused target/eval/version suite: `28 passed in 4.96s`.

Errors Encountered:

| Error | Attempt | Resolution |
| --- | --- | --- |
| Initial Phase 6g plan set `expected_conflict_chain_count = 1` even though current fixtures only have `old -> target` single chains | 1 | Plan review revised expected conflict count to `0`; report now uses `unavailable` until forked chains exist. |
| Baseline miss first design skipped only forced recall, allowing ordinary query-term matching to reintroduce missed ids | 1 | Runner now skips explicit `baseline_miss_recall_ids` from the entire baseline recall loop. |
| Graph hard case still showed `100% -> 100%` because graph baseline fused lanes reused semantic/provenance candidates containing the missed graph id | 1 | Graph shadow baseline lanes now filter explicit baseline miss ids while graph lane remains available for experimental recovery. |

## 2026-07-20 Memory Phase 6h Graph Conflict And Evidence Inputs

Goal: continue the memory target-metric repair cycle by locating the remaining graph hard miss, adding a forked version-chain fixture, and turning write/hygiene from shadow estimates into evidence-backed metrics.

1. Update docs with the next-step scope - complete
2. Write and review the Phase 6h implementation plan - complete
3. Implement graph hard-case refinement, forked replacement-chain fixture, and evidence-input hooks - complete
4. Regenerate target metrics and verify the new indicators - complete
5. Update docs with results and remaining gaps - complete

Constraints:

- Do not call a real LLM unless the evidence-input work explicitly requires it later.
- Do not write production memory DB or observe DB.
- Do not change AgentLoop, Reasoner, ToolExecutor, ToolRegistry, or production memory retrieval for this repair pass.

Planned outcomes:

- Graph retrieval now uses a graph-specific denominator, so the remaining `98.75%` gap is no longer a false penalty from tri-retrieval misses.
- `conflict_chain_detection_rate` is measurable on the forked replacement-chain fixture and remains `unavailable` only where no fork exists.
- Write-governance and sleep-consolidation tables still need stronger real evidence inputs before they can be treated as online metrics.

Results:

- Overall target recall: tri `93.75% -> 100%`, graph `97.5% -> 100%`, rerank/injection `93.75% -> 100%`, version/provenance `90% -> 100%`.
- Hard subset: tri `87.5% -> 100%`, graph `95% -> 100%`, current version `80% -> 100%`.
- `conflict_chain_detection_rate`: `100%` on hard / overall, `unavailable` on common.
- Write-governance and sleep-consolidation remain proxy / shadow tables in the formal report; no online row is present yet.

Next open work:

- Collect real evidence inputs for write governance and memory hygiene, then rerun the target-metric report with checkpoint-backed or live evidence rows.

## 2026-07-20 Memory Phase 6i Evidence Input Hardening

Goal: harden write-governance and memory-hygiene evidence inputs so malformed records cannot silently become online target metrics.

1. Write and review the Phase 6i evidence-input plan - complete
2. Add JSONL, wrapped JSON, invalid-domain, invalid-boolean, and invalid-token tests - complete
3. Harden evidence loading and schema validation in `memory2/eval_target_metrics.py` - complete
4. Update memory optimization docs, findings, progress, and task plan - complete
5. Run target metric tests, compileall, and diff checks - complete

Constraints:

- Do not call a real LLM.
- Do not write production memory DB or observe DB.
- Do not modify AgentLoop, Reasoner, ToolExecutor, ToolRegistry, or production memory retrieval.
- Do not change Phase 6h answer-layer metric math.

Results so far:

- Evidence inputs now support JSON arrays, `{"records": [...]}` wrapped JSON, and JSONL.
- Write evidence rows must use supported labels and decisions and must use real boolean `infra_error`.
- Hygiene evidence rows must use supported labels/states, real boolean fields, and nonnegative numeric token estimates.
- Invalid evidence fails fast through the CLI instead of being silently counted.
- Verification: focused evidence-input tests `7 passed`; full target metric tests `25 passed`; compileall and `git diff --check` exited `0`.

## 2026-07-20 Memory Phase 6j Comprehensive Case Pack

Goal: add a larger target-oriented memory evaluation pack that can be consumed by the existing offline and online runners without changing the default 80-case reports.

1. Preserve default `standard` case pack behavior - complete
2. Add explicit `comprehensive` case pack with more scenarios and variants - complete
3. Wire `--case-pack comprehensive` into offline target/uplift/chain/balanced and comprehensive-online CLI entry points - complete
4. Add structure and CLI smoke tests - complete
5. Run the 320-case target metric smoke into `/tmp` only - complete
6. Update memory optimization docs, findings, progress, and task plan - complete

Constraints:

- Do not overwrite the formal `my_md/memory_optimization/eval_reports/memory_target_metrics_eval.*` report in this step.
- Do not call a real LLM.
- Do not write production memory DB or observe DB.
- Keep old 80-case `standard` defaults reproducible.

Results:

- `standard` remains 80 cases: common 40 / hard 40.
- `comprehensive` produces 320 cases: common 160 / hard 160.
- Coverage now includes 20 target-oriented scenario categories and 8 variants per common/hard set.
- Full target-metric smoke command:
  `.venv/bin/python scripts/run_memory_target_metrics_eval.py --out-dir /tmp/akashic-memory-comprehensive-pack --case-pack comprehensive`
- Smoke output:
  - `case_count = 320`
  - `common_case_count = 160`
  - `hard_case_count = 160`
  - `case_record_count = 1920`
  - write candidates = `960`
  - hygiene scanned units = `2400`
  - tri recall `98.125% -> 100%`
  - graph recall `98.75% -> 100%`
  - rerank/injection `98.125% -> 100%`
  - version/provenance `97.5% -> 100%`
  - write pollution block after `100%`
  - sleep token saving after `32.8125%`

Errors Encountered:

| Error | Attempt | Resolution |
| --- | --- | --- |
| First 320-case smoke failed because `costly_call_preference` noise summary shared query keywords and was injected as ranked context | 1 | Changed only that scenario's unrelated noise text so high-risk confirmation remains covered by target/conflict/old items while the noise item no longer becomes a false expected failure. |

## 2026-07-20 Memory Phase 6k Real LLM Core Eval

Goal: run a controlled real-LLM answer/retrieval core matrix over the comprehensive pack, preserve a checkpoint, and convert the checkpoint into target metrics without claiming the run is more complete than it is.

1. Write and review the real-LLM core eval plan - complete
2. Add a CLI regression for comprehensive core matrix acceptance - complete
3. Run the fake-provider core matrix to validate the matrix shape - complete
4. Start the real-LLM core matrix with explicit checkpoint persistence - complete
5. Stop after a bounded partial run and rebuild the checkpoint report - complete
6. Convert the checkpoint into target metrics and fix writer compatibility if needed - complete
7. Update docs, progress, findings, and task plan with the partial real-LLM conclusion - complete

Constraints:

- Do not overwrite formal `my_md` eval reports with this partial result.
- Do not treat checkpoint-report-only output as a full 1280-run conclusion.
- Do not add write-governance or sleep-hygiene real evidence claims from this run.

Results:

- Fake-provider core matrix completed with `case_count = 1280`, `profile_count = 4`, `prompt_variant_count = 1`, `repeat_count = 1`.
- Real LLM core matrix produced checkpoint `/tmp/akashic-memory-phase6k-real/reports/memory_comprehensive_online_eval.checkpoint.jsonl`.
- Real LLM run was manually stopped after `325` calls to control time/cost.
- Checkpoint report rebuilt at `/tmp/akashic-memory-phase6k-real/checkpoint-report/memory_comprehensive_online_eval.{json,md}` with `case_count = 325`, `unique_case_count = 82`, `answer_rule_pass_rate = 24.0`, `memory_grounding_pass_rate = 74.7692`, `forbidden_violation_rate = 15.3846`, `avg_latency_ms = 4635.4431`, `total_token_count = 1754732`.
- Target-metric conversion initially failed because the writer tried to render version-chain专项 rows for online checkpoint data; fixed by keeping the version-chain section offline-only.
- Target-metric report rebuilt successfully at `/tmp/akashic-memory-phase6k-target/memory_target_metrics_eval.{json,md}`.

Errors Encountered:

| Error | Attempt | Resolution |
| --- | --- | --- |
| Real run initially omitted an explicit checkpoint path | 1 | Added `--checkpoint-jsonl /tmp/akashic-memory-phase6k-real/reports/memory_comprehensive_online_eval.checkpoint.jsonl` to the plan and reused it in the resume/report-only paths. |
| Target-metric rebuild failed with `KeyError: 'current_version_recall_rate'` when rendering online checkpoint rows | 1 | Restricted version-chain专项 rendering to `measurement_layer == "offline_trace"` so online checkpoint data remains in the main table only. |

## 2026-07-21 Memory Baseline Plus Enhancements

Goal: change the quantitative memory evaluation framing from disabled-memory baseline to original-memory baseline plus enhancement modules.

1. Treat `memory_base` as the single-module original-memory baseline - complete
2. Treat `chain_memory_base` as the cumulative-chain original-memory baseline - complete
3. Keep `off` / `chain_off` as disabled-enhancement controls, not as the main baseline - complete
4. Add count-oriented summary fields for target/success/miss/recall-rate presentation - complete
5. Regenerate uplift, chain, and layered reports under the new baseline - complete
6. Update memory optimization docs and planning files - complete
7. Run focused tests and diff checks - complete

Results:

- Quantitative uplift: `baseline_main_score = 94.375`, `all_on_main_score = 69.3043`, `total_uplift_points = -25.0707`.
- Chain uplift: `chain_memory_base = 94.375`, `chain_all_on = 69.3043`, `total_chain_uplift_points = -25.0707`.
- Layered scoring: `baseline_total_layered_score = 94.375`, `final_total_layered_score = 54.9521`, `total_layered_uplift_points = -39.4229`.
- Focused verification: `50 passed`; `git diff --check` exited `0`.

Next open work:

- Commit this baseline-framing change.
- Build the 320-case offline count/percentage report with two views:
  - single-module gain relative to original memory;
  - cumulative chain gain relative to original memory.

## 2026-07-21 Memory 320 Case Baseline Plus Count Report

Goal: produce a compact 320-case offline report that presents memory enhancement effects as recalled/missed counts and recall-rate percentage-point changes.

1. Run comprehensive single-module quantitative uplift report into `/tmp` - complete
2. Run comprehensive cumulative-chain quantitative report into `/tmp` - complete
3. Extract single-module count/rate table relative to original memory - complete
4. Extract cumulative-chain count/rate table relative to original memory - complete
5. Write a linked memory optimization document with results and conclusions - complete

Results:

- Original memory baseline: `628/640` recalled, `12/640` missed, `98.12%` recall.
- Tri retrieval: `640/640` recalled, +12 recalled, +1.88 percentage points.
- Graph retrieval: `638/640` recalled, +10 recalled, +1.57 percentage points.
- All-on: `370/640` recalled, -258 recalled, -40.31 percentage points.

Next open work:

- Convert the 320-case count report into the next real-LLM matrix selection:
  - keep `chain_memory_base`;
  - include `chain_tri_retrieval`, `chain_graph_retrieval`, and `chain_rerank_injection`;
  - treat write governance and sleep hygiene as separate evidence-layer evaluations rather than answer-recall profiles.

## 2026-07-21 Memory Answer Comprehensive V2

Goal: expand the answer/retrieval-only count evaluation from 320 cases to a more persuasive 1000-case pack, while keeping original memory as the main baseline.

1. Revise and review the implementation plan - complete
2. Add failing tests for the new case pack and answer-only report tables - complete
3. Implement `answer_comprehensive_v2`, report builder, and CLI - complete
4. Generate formal JSON/Markdown reports under `my_md/memory_optimization/eval_reports` - complete
5. Update memory optimization docs and planning files - complete
6. Run focused verification and commit - complete

Results:

- `answer_comprehensive_v2` produces `1000` cases and `2000` target memories.
- Single-module table:
  - original memory baseline: `1978/2000`, `98.9%`;
  - tri retrieval: `2000/2000`, +22 recalled, +1.1 percentage points;
  - graph retrieval: `1994/2000`, +16 recalled, +0.8 percentage points;
  - rerank/injection: `1584/2000`, -394 recalled, -19.7 percentage points;
  - version/provenance: `1000/2000`, -978 recalled, -48.9 percentage points;
  - answer-only all-on: `1998/2000`, +20 recalled, +1.0 percentage points.
- Chain table:
  - `chain_tri_retrieval`: `2000/2000`, cumulative +22 recalled;
  - `chain_graph_retrieval`: `2000/2000`, cumulative +22 recalled;
  - `chain_rerank_injection`: `2000/2000`, cumulative +22 recalled;
  - `chain_version_provenance`: `1998/2000`, cumulative +20 recalled;
  - `chain_all_on`: `1998/2000`, cumulative +20 recalled.

Next open work:

- Verify and commit this answer/retrieval-only 1000-case report.
- Use these results to select real-LLM answer/retrieval profiles: keep `chain_memory_base`, `chain_tri_retrieval`, `chain_graph_retrieval`, `chain_rerank_injection`, and include answer-only `chain_all_on` as a positive but not strongest recall setting.
- Use the interview-facing explanation in `06-memory-320-baseline-plus-count-eval.md` when explaining why governance modules can drop single-module recall but remain valuable in the full chain.

Verification:

- `.venv/bin/python -m pytest tests/test_memory_quantitative_uplift.py tests/test_memory_answer_retrieval_counts.py tests/test_memory_answer_retrieval_counts_cli.py tests/test_memory_quantitative_chain_cli.py tests/test_memory_quantitative_uplift_cli.py -q -p no:cacheprovider` -> `30 passed in 59.58s`.
- `.venv/bin/python -m compileall memory2/eval_answer_retrieval_counts.py scripts/run_memory_answer_retrieval_counts_eval.py tests/test_memory_answer_retrieval_counts.py tests/test_memory_answer_retrieval_counts_cli.py -q` -> exit `0`.
- `git diff --check` and `git diff --cached --check` -> exit `0`.

## 2026-07-21 Memory Write Governance Offline Count Eval

Goal: produce a standalone write-governance count table that compares original write behavior against additive write-value governance.

1. Revise and review the implementation plan - complete
2. Add diversified 1200-candidate write-governance case pack - complete
3. Add offline count report with category, common/hard, and subtype breakdowns - complete
4. Add CLI and generate JSON/Markdown reports - complete
5. Update linked memory optimization docs - complete
6. Run focused verification and commit - complete

Results:

- Original write baseline: `1200/1200` written.
- Write-value governance: `202/1200` directly written.
- Write reduction: `998/1200`, `83.1667%`.
- Useful candidate retention: `140/400`, `35.0%`.
- Pollution candidate control: `738/800`, `92.25%`.
- False reject: `260/400`, `65.0%`.
- False accept: `62/800`, `7.75%`.
- Review miss: `142/200`, `71.0%`.

Conclusion:

- This table successfully separates write governance from answer/retrieval evaluation.
- The module is effective at controlling temporary state and assistant-inference pollution.
- It is too conservative for useful preferences and stable facts, especially hard cases.
- Conflict routing still needs improvement because most conflict candidates are not sent to review.

Next plan:

1. Split write-governance false-reject reporting into direct reject false reject, review deferral, and not-directly-written conservative rate.
2. Narrow temporary-risk markers so terms like `测试` do not automatically reject long-term test plans or evaluation rules.
3. Add implicit long-term value signals for stable requirements, cross-session preferences, default rules, priorities, and follow-up reusable constraints.
4. Add conflict-to-review routing based on overlap with existing memories and opposite/priority/scope-change wording.
5. Regenerate the 1200-candidate report and compare before/after:
   - useful retention should improve from `35.0%`;
   - pollution control should stay near or above `90%`;
   - direct reject false reject should fall below current `20.0%`;
   - conflict review miss should fall below current `71.0%`.

## 2026-07-21 Memory Write Governance Policy Tuning

Goal: reduce useful-memory false rejects while keeping pollution control high and routing conflicts to review.

1. Plan and review policy tuning - complete
2. Split false-reject metrics into direct reject, review deferral, and conservative not-directly-written useful rate - complete
3. Narrow temporary-risk markers and add implicit long-term value signals - complete
4. Add conflict-to-review routing with unrelated-change guard - complete
5. Regenerate 1200-candidate report and run metric gate - complete
6. Update docs and run verification - complete

Results:

- Original write baseline remains `1200/1200` written.
- Tuned write-value governance directly writes `172/1200`.
- Useful retention improved from `35.0%` to `37.5%`.
- Pollution control improved from `92.25%` to `97.25%`.
- Direct reject false reject improved from `20.0%` to `12.5%`.
- Review deferral moved from `45.0%` to `50.0%`.
- Not-directly-written useful candidate rate improved from `65.0%` to `62.5%`.
- False accept improved from `7.75%` to `2.75%`.
- Conflict review miss improved from `71.0%` to `2.0%`.

Conclusion:

- The tuning meets the automatic metric gates and does not trade away pollution control.
- The largest gain is conflict routing, which now sends `196/200` conflict candidates to review.
- The remaining weakness is hard useful candidates, which still mostly enter review instead of direct write.

Next plan:

1. Add an offline review resolver for write-governance `review` candidates.
2. Resolver inputs: candidate summary, existing memories, source_ref, original write-governance score, and reason list.
3. Resolver outputs: `approve_write`, `keep_review`, or `reject`.
4. Add tests for:
   - safe useful review candidate promoted to final write;
   - hard useful candidate final retention improves;
   - conflict candidate remains in review;
   - temporary / assistant inference / duplicate pollution does not get promoted.
5. Add a second report table for review handling:
   - review candidate count;
   - promoted write count;
   - kept review count;
   - rejected count;
   - useful final retention;
   - hard useful final retention;
   - conflict review preservation;
   - duplicate hard leakage.
6. Run offline metric gate before any online test:
   - useful final retention `> 60%`;
   - hard useful final retention `> 40%`;
   - pollution control `>= 90%`;
   - conflict review preservation `>= 95%`;
   - duplicate hard leakage `< 10%`.

Verification:

- `.venv/bin/python -m pytest tests/test_memory_write_governance_counts.py tests/test_memory_write_governance_counts_cli.py tests/test_post_response_memory_experiments.py -q -p no:cacheprovider` -> `22 passed in 1.01s`.
- `.venv/bin/python -m compileall plugins/default_memory/experiments.py memory2/eval_write_governance_counts.py tests/test_memory_write_governance_counts.py -q` -> exit `0`.
- `git diff --check` -> exit `0`.

## 2026-07-21 Memory Write Governance Review Resolver

Goal: add an offline-first second-stage resolver for write-governance `review` candidates, plus a final safety gate for candidates that would otherwise be written.

1. Commit the pre-existing documentation state - complete
2. Add pure resolver module and resolver-focused tests - complete
3. Integrate resolver and final safety gate into the offline count report - complete
4. Regenerate JSON/Markdown reports and run metric gates - complete
5. Update memory optimization docs and planning files - complete
6. Run final verification and commit - complete

Results:

- First-stage direct write remains `172/1200`; this keeps the previous write-governance table comparable.
- Review candidates: `449`.
- Review promoted writes: `203`.
- Review kept: `196`.
- Review rejected: `50`.
- Final written count after resolver and safety gate: `350/1200`.
- Useful final retention: `87.5%`.
- Hard useful final retention: `75.0%`.
- Final pollution control: `100.0%`.
- Conflict review preservation: `98.0%`.
- Hard duplicate leakage: `0.0%`.

Plan adjustment:

- Resolver-only handling was insufficient because some hard duplicate leakage came from first-stage `allow`, not from `review`.
- The implementation therefore adds a final write safety gate after first-stage allow / resolver promotion. It checks every provisional final write for duplicate, conflict, and pollution signals before final write counting.

Gap to ideal state:

- Useful final retention is `87.5%`; ideal is `100%`, so the gap is `50/400` useful candidates or `12.5` percentage points.
- Hard useful final retention is `75.0%`; ideal is `100%`, so the gap is `50/200` hard useful candidates or `25` percentage points.
- Conflict review preservation is `98.0%`; ideal is `100%`, so the gap is `4/200` conflict candidates or `2` percentage points.
- Final pollution control is `100.0%` and hard duplicate leakage is `0.0%`, so those two are already at the strict ideal target in this offline set.
- Main remaining weakness is useful hard-candidate recovery, not pollution control.

Verification so far:

- `.venv/bin/python -m pytest tests/test_memory_write_governance_counts.py -q -p no:cacheprovider` -> `26 passed in 0.98s`.
- `.venv/bin/python -m pytest tests/test_memory_write_governance_counts_cli.py -q -p no:cacheprovider` -> `1 passed in 0.20s`.
- Resolver metric gate passed:
  - useful final retention `87.5%` > `60.0%`;
  - hard useful final retention `75.0%` > `40.0%`;
  - final pollution control `100.0%` >= `90.0%`;
  - conflict review preservation `98.0%` >= `95.0%`;
  - hard duplicate leakage `0.0%` < `10.0%`.
- Final focused verification:
  - `.venv/bin/python -m pytest tests/test_memory_write_governance_counts.py tests/test_memory_write_governance_counts_cli.py tests/test_post_response_memory_experiments.py -q -p no:cacheprovider` -> `32 passed in 1.52s`.
  - `.venv/bin/python -m compileall memory2/write_governance_review.py memory2/eval_write_governance_counts.py tests/test_memory_write_governance_counts.py tests/test_memory_write_governance_counts_cli.py -q` -> exit `0`.
  - `git diff --check` -> exit `0`.
  - `git diff --cached --check` -> exit `0`.

Constraints:

- Offline-only; no real LLM calls.
- No production memory DB, observe DB, or workspace memory state writes.
- No AgentLoop, live memory write behavior, Reasoner, ToolExecutor, or ToolRegistry changes.
- Resolver and final safety gate do not branch on eval labels such as category, case_set, or subtype.

## 2026-07-21 Memory Hard Useful Recovery Tuning

Goal: recover hard useful write candidates that were falsely rejected by broad temporary-risk markers, while preserving pollution control and duplicate safety.

1. Commit the current ideal-gap documentation baseline - complete
2. Add regression tests for temporary-marker false positives - complete
3. Tighten temporary-risk detection in `score_write_candidate_shadow()` - complete
4. Add strict ideal gap metrics to the offline report - complete
5. Regenerate JSON/Markdown reports and run strict metric gates - complete
6. Update memory optimization docs and planning files - complete
7. Run final verification and commit - complete

Root cause:

- `50/200` hard useful misses were all first-stage `reject` with reason `temporary_state`.
- The stable exception phrase `除非用户临时改口` was matched by broad standalone `临时`.
- `4/200` conflict misses were also first-stage `reject` with reason `temporary_state`, caused by broad `不要记` matching inside `不要记录来源`.

Implementation:

- Removed broad standalone `临时`, `不要记`, and English `temporary` from temporary-risk matching.
- Kept precise temporary markers such as `今天这次`, `本轮调试`, `只用于当前`, `先不用长期保存`, `不要写入长期记忆`, `不要记住`, and `do not remember`.
- Added regression tests for Chinese stable exceptions, English `temporary exception`, `不要记录来源` conflict wording, and precise temporary rejection examples.
- Added JSON/Markdown metrics:
  - `useful_final_gap_count`;
  - `hard_useful_final_gap_count`;
  - `conflict_review_gap_count`;
  - `strict_ideal_gap_count`.

Results:

- Useful final retention: `87.5% -> 100.0%`.
- Hard useful final retention: `75.0% -> 100.0%`.
- Conflict review preservation: `98.0% -> 100.0%`.
- Final pollution control: `100.0% -> 100.0%`.
- Hard duplicate leakage: `0.0% -> 0.0%`.
- Useful final gap: `50/400 -> 0/400`.
- Hard useful final gap: `50/200 -> 0/200`.
- Conflict review gap: `4/200 -> 0/200`.
- Strict ideal gap: `54 -> 0`.

Strict metric gate:

- useful final retention `100.0%` >= `95.0%`;
- hard useful final retention `100.0%` >= `95.0%`;
- final pollution control `100.0%` >= `98.0%`;
- conflict review preservation `100.0%` >= `99.0%`;
- hard duplicate leakage `0.0%` == `0.0%`.

Final verification:

- `.venv/bin/python -m pytest tests/test_memory_write_governance_counts.py tests/test_memory_write_governance_counts_cli.py tests/test_post_response_memory_experiments.py tests/test_memory_experiments_runner.py tests/test_memory_eval_runner.py -q -p no:cacheprovider` -> `70 passed in 1.64s`.
- `.venv/bin/python -m compileall plugins/default_memory/experiments.py memory2/write_governance_review.py memory2/eval_write_governance_counts.py tests/test_memory_write_governance_counts.py tests/test_memory_write_governance_counts_cli.py -q` -> exit `0`.
- `git diff --check` -> exit `0`.
- `git diff --cached --check` -> exit `0`.

Constraints:

- Offline/shadow evaluation only.
- No real LLM calls.
- No production memory DB or observe DB writes.
- No AgentLoop, Reasoner, ToolExecutor, ToolRegistry, or live memory write behavior changes.

## 2026-07-21 Memory Write Governance Key Data Documentation

Goal: record the current Phase 6n write-governance key data in memory optimization docs and clarify what is offline evidence versus online evidence.

1. Add explicit dataset configuration and baseline explanation to `07-memory-write-governance-count-eval.md` - complete
2. Sync the memory optimization README Phase 6n summary - complete
3. Replace stale `240`-candidate write-governance wording in target metric and quality metric docs with the current `1200`-candidate offline count result - complete
4. Update the experiment roadmap so future work starts from real online evidence instead of redoing useful-retention fixture work - complete
5. Record the documentation update in `progress.md` and `task_plan.md` - complete

Recorded key data:

- Offline set: `1200` candidates = common `600` + hard `600` = `2 * 6 categories * 5 subtypes * 20 variants`.
- Baseline: original write behavior writes `1200/1200`, including useful `400/400` and pollution/duplicate/conflict `800/800`.
- Enhanced chain: direct write `172/1200`, write reduction `85.6667%`, first-stage pollution control `97.25%`.
- Review/final path: review candidates `503`, promoted writes `253`, final writes `400/1200`.
- Final quality: useful final retention `100.0%`, hard useful final retention `100.0%`, final pollution control `100.0%`, conflict review preservation `100.0%`, hard duplicate leakage `0.0%`, strict ideal gap `0`.

Remaining boundary:

- These are synthetic/template-based offline results.
- They do not prove production AgentLoop write behavior or online memory quality.
- Online evidence still needs real candidate records, decisions, actual write/review/reject outcomes, and future recall usefulness.

## 2026-07-21 Memory Write Governance Online Shadow Eval

Goal: build a test-set-driven online shadow path for write governance, producing `write_evidence.jsonl` that can be consumed by target metrics.

1. Add write evidence domain mapping and final-decision conversion - complete
2. Add test-set-driven AgentLoop runner with fake-provider support - complete
3. Add CLI `scripts/run_memory_write_governance_online_eval.py` - complete
4. Add target-metric integration smoke for `--online-write-evidence-json` - complete
5. Fix small-sample category imbalance by adding balanced candidate selection - complete
6. Run fake-provider smoke and target metric report generation - complete
7. Update memory optimization docs and planning records - complete

Implemented files:

- `memory2/eval_write_governance_online.py`
- `scripts/run_memory_write_governance_online_eval.py`
- `tests/test_memory_write_governance_online_eval.py`
- `tests/test_memory_write_governance_online_cli.py`

Current fake-provider smoke:

- reports: `/tmp/akashic-memory-write-governance-online-fake-v2/reports`
- target metrics: `/tmp/akashic-memory-write-governance-online-fake-v2/target`
- `candidate_count = 24`
- `real_llm_enabled = False`
- `infra_passed = True`
- `provider_error_count = 0`
- `timeout_count = 0`
- `total_token_count = 720`
- `avg_latency_ms = 34.5417`
- evidence distribution:
  - useful `8`, all after `allow`;
  - pollution `8`, all after `reject`;
  - duplicate `4`, all after `reject`;
  - conflict `4`, all after `review`.

Target metric online evidence row:

- `online_write_record_count = 24`
- useful write precision `33.3333% -> 100.0%`
- pollution block rate `0.0% -> 100.0%`
- duplicate control rate `0.0% -> 100.0%`
- conflict review rate `0.0% -> 100.0%`
- write reduction rate `0.0% -> 66.6667%`
- false reject rate `0.0% -> 0.0%`
- false accept rate `100.0% -> 0.0%`

Verification so far:

- `.venv/bin/python -m pytest tests/test_memory_write_governance_online_eval.py tests/test_memory_write_governance_online_cli.py tests/test_memory_target_metrics_cli.py -q -p no:cacheprovider` -> `21 passed in 15.51s`.

Boundaries:

- This is test-set-driven online shadow evaluation, not production traffic.
- Candidate summaries and labels come from the test set, not from LLM extraction.
- The run uses real AgentLoop and can optionally call real LLM, but fake-provider smoke did not call a real LLM.
- `skip_post_memory=True` prevents post-response memory writes.
- No production memory DB, observe DB, live AgentLoop behavior, ToolExecutor, or ToolRegistry changes.

Real LLM pilot:

- reports: `/tmp/akashic-memory-write-governance-online-real-pilot-v2/reports`
- target metrics: `/tmp/akashic-memory-write-governance-online-real-pilot-v2/target`
- `candidate_count = 24`
- `real_llm_enabled = True`
- `infra_passed = True`
- `provider_error_count = 0`
- `timeout_count = 0`
- `total_token_count = 124099`
- `avg_latency_ms = 2790.7917`
- evidence distribution:
  - useful `8`, all after `allow`;
  - pollution `8`, all after `reject`;
  - duplicate `4`, all after `reject`;
  - conflict `4`, all after `review`.

Real target metric online evidence row:

- `online_write_record_count = 24`
- useful write precision `33.3333% -> 100.0%`
- pollution block rate `0.0% -> 100.0%`
- duplicate control rate `0.0% -> 100.0%`
- conflict review rate `0.0% -> 100.0%`
- write reduction rate `0.0% -> 66.6667%`
- false reject rate `0.0% -> 0.0%`
- false accept rate `100.0% -> 0.0%`

Updated boundary after pilot:

- The pilot proves the test-set-driven write-governance online shadow path can run with a real LLM provider and produce target-metric-compatible evidence.
- It still does not prove natural production traffic quality.
- It still does not evaluate LLM-generated memory candidate extraction.

## 2026-07-22 Memory Phase 6o Expanded Write Governance Real LLM Eval

Goal: execute the reviewed plan for a larger write-governance real LLM shadow evaluation, while fixing the limited sampler so the expanded sample is fair across common/hard and category dimensions.

1. Preflight candidate universe and current limited sampler - complete
2. Add failing sampler test and verify RED - complete
3. Implement common/hard + category stratified limited selection - complete
4. Run fake-provider full 1200 shadow and target metrics - complete
5. Run real LLM expanded 240 shadow and target metrics - complete
6. Skip optional real 1200 unless explicitly approved - complete
7. Update memory optimization docs and recovery records - in progress
8. Run focused tests, diff checks, stage intended files, and commit - pending

Preflight:

- `build_write_governance_candidates(case_set="all")` returned `1200`.
- `common = 600`, `hard = 600`.
- Each category had `200` candidates.
- Old `limit=240` returned `common = 240`, `hard = 0`, so the plan correctly required sampler repair before real 240 evaluation.

Sampler repair:

- Added regression test in `tests/test_memory_write_governance_online_eval.py`.
- RED result: `Counter({'common': 24})` failed against expected common `12` / hard `12`.
- Implemented common/hard + category stratified selection in `memory2/eval_write_governance_online.py`.
- Focused sampler tests: `2 passed in 0.21s`.

Fake full 1200:

- reports: `/tmp/akashic-memory-write-governance-expanded-fake/reports`
- target metrics: `/tmp/akashic-memory-write-governance-expanded-fake/target`
- `candidate_count = 1200`
- `checkpoint rows = 1200`
- `evidence rows = 1200`
- `infra_passed = True`
- `provider_error_count = 0`
- `timeout_count = 0`
- `total_token_count = 36000`
- `avg_latency_ms = 31.8925`

Real LLM expanded 240:

- reports: `/tmp/akashic-memory-write-governance-expanded-real-240/reports`
- target metrics: `/tmp/akashic-memory-write-governance-expanded-real-240/target`
- checkpoint: `/tmp/akashic-memory-write-governance-expanded-real-240/reports/checkpoint.jsonl`
- evidence: `/tmp/akashic-memory-write-governance-expanded-real-240/reports/memory_write_governance_online_evidence.jsonl`
- `candidate_count = 240`
- `checkpoint rows = 240`
- `evidence rows = 240`
- `common = 120`
- `hard = 120`
- each category count = `40`
- `real_llm_enabled = True`
- `infra_passed = True`
- `provider_error_count = 0`
- `timeout_count = 0`
- `completed_call_count = 240`
- `skipped_from_checkpoint_count = 0`
- `total_token_count = 1236228`
- `avg_latency_ms = 2366.625`

Real 240 evidence distribution:

- useful `80`: allow `80`, reject `0`, review `0`
- pollution `80`: allow `0`, reject `80`, review `0`
- duplicate `40`: allow `0`, reject `40`, review `0`
- conflict `40`: allow `0`, reject `0`, review `40`

Real 240 target metric online evidence row:

- `online_write_record_count = 240`
- useful write precision `33.3333% -> 100.0%`
- pollution block rate `0.0% -> 100.0%`
- duplicate control rate `0.0% -> 100.0%`
- conflict review rate `0.0% -> 100.0%`
- write reduction rate `0.0% -> 66.6667%`
- false reject rate `0.0% -> 0.0%`
- false accept rate `100.0% -> 0.0%`

Optional real 1200:

- Not executed by default.
- Reason: it is estimated at about `6.2M` tokens and the 240 run already provides common/hard + category balanced evidence.
- It should require explicit user approval before spending that cost.

Boundary:

- This is test-set-driven real LLM shadow evaluation.
- It does not prove production natural traffic quality.
- It does not evaluate LLM-generated memory candidate extraction.
- It does not write production memory DB because the runner uses `skip_post_memory=True`.

Documentation follow-up:

- Added a detailed test scheme to `my_md/memory_optimization/07-memory-write-governance-count-eval.md`.
- The section records:
  - test purpose;
  - fake full / 24 pilot / 240 expanded three-layer design;
  - 1200 candidate universe;
  - 240-case common/hard + category stratified sampling;
  - category-to-label mapping;
  - AgentLoop and write governance runtime chain;
  - metric formulas;
  - baseline definition;
  - acceptance criteria;
  - provider failure and checkpoint handling;
  - production-boundary caveats.

## 2026-07-22 Sleep Hygiene Evidence Eval

Goal: 补齐睡眠巩固在“记忆库卫生表”中的可量化 evidence，回答打开睡眠巩固后重复/过期/低价值候选识别和关键记忆误伤情况。

Implemented:

- Added deterministic sleep hygiene case builder: `memory2/eval_sleep_hygiene_cases.py`.
- Added shadow-to-evidence converter and report writer: `memory2/eval_sleep_hygiene_evidence.py`.
- Added CLI: `scripts/run_memory_sleep_hygiene_evidence_eval.py`.
- Added tests:
  - `tests/test_memory_sleep_hygiene_cases.py`;
  - `tests/test_memory_sleep_hygiene_evidence.py`;
  - `tests/test_memory_sleep_hygiene_evidence_cli.py`.
- Added report output under `my_md/memory_optimization/eval_reports/sleep_hygiene_evidence/`.
- Added dedicated docs: `my_md/memory_optimization/08-memory-sleep-hygiene-eval.md`.

Design boundary:

- Uses current `sleep_consolidation_shadow`.
- Does not change `AgentLoop`, `Reasoner`, `ToolExecutor`, retrieval, prompt injection, or production memory storage.
- Does not merge, delete, supersede, or write real memory rows.
- `source_fetch_success_rate` is proxy-only in this phase.
- `shadow_estimated_token_saving_rate` is an estimate, not real DB or prompt token reduction.

Current 600-case result:

- `case_count = 600`
- `scanned_active_item_count = 750`
- `evaluated_evidence_row_count = 600`
- duplicate candidate identification rate `100.0%`
- stale candidate identification rate `100.0%`
- low-value candidate identification rate `100.0%`
- source_ref coverage `90.0%`
- proxy source fetch success `100.0%`
- shadow estimated token saving `64.0138%`
- retained memory retention `100.0%`
- retained candidate leak count `0`
- unexpected candidate count `0`
- false positive cleanup rate `0.0%`
- applied change count `0`

Next:

- Add real `source_ref` fetch evidence.
- Add harder false-positive cases.
- Consider active dry-run patch generation only after shadow precision remains stable.

## 2026-07-22 Sleep Hygiene Hard Eval V2

Goal: upgrade sleep hygiene evaluation from standard-only correctness to standard/hard/overall boundary evaluation.

Implemented:

- Added per-item `expected_after_state` so false positives inside multi-item hard cases cannot be hidden.
- Added hard scenarios:
  - `near_merge_not_duplicate`;
  - `old_high_value`;
  - `temporary_but_pinned`;
  - `cross_scope_identical`;
  - `opposite_preference_conflict`;
  - `multi_duplicate_pairwise`;
  - `missing_source_but_important`;
  - `mixed_signal_low_value`.
- Added CLI support for `--case-set standard|hard|all` and `--hard-per-scenario`.
- Generated V2 reports under `my_md/memory_optimization/eval_reports/sleep_hygiene_evidence_v2/`.

Current V2 result:

- standard: `600` cases, `600` evaluated items, candidate recall `100.0%`, candidate precision `100.0%`, retained protection `100.0%`, false positive cleanup `0.0%`, safe evidence token saving `64.0138%`.
- hard: `320` cases, `520` evaluated items, candidate recall `100.0%`, candidate precision `75.0%`, retained protection `90.0%`, false positive cleanup `10.0%`, safe evidence token saving `unsafe`.
- overall: `920` cases, `1120` evaluated items, candidate recall `100.0%`, candidate precision `93.4426%`, retained protection `92.7273%`, false positive cleanup `7.2727%`, safe evidence token saving `unsafe`.

Boundary:

- Still offline evidence / shadow-only.
- No real DB cleanup happened.
- No real prompt token reduction is claimed.
- The hard result exposes a real boundary issue: merge candidates can hurt retained protection if treated as cleanup.

Next improvement sequence:

1. Scenario split report: add per-scenario hard metrics so `near_merge_not_duplicate`, scope safety, conflict safety, missing-source safety and low-value cleanup are visible independently.
2. Candidate taxonomy: split `merge suggestion` from `cleanup candidate`; near-merge should default to review and should not count as safe cleanup token saving.
3. Real provenance evidence: replace proxy `source_fetch_success` with real `source_ref` lookup and support/mismatch counters.
4. Active dry-run patch: output `would_merge`, `would_mark_stale`, `would_remove_low_value`, `would_keep`, and `requires_review` without writing DB.
5. Activation gate: do not enable real merge / supersede until hard precision, retained protection, real source fetch, and recoverability meet explicit thresholds.

## 2026-07-22 Sleep Hygiene Safety V3

Goal: turn the V2 hard-eval finding into a safer sleep hygiene evaluation and dry-run workflow without changing production memory behavior.

Completed:

- Documentation baseline commit:
  - `2c50d26 docs: record sleep hygiene safety follow-ups`.
- Task 1:
  - added hard `scenario_metrics`;
  - committed as `361d5f4 feat: add sleep hygiene scenario metrics`.
- Task 2:
  - split `cleanup candidate` from `merge suggestion`;
  - near-merge is review-only and no longer counted as safe cleanup;
  - committed as `3281611 feat: split sleep hygiene cleanup and review candidates`.
- Task 3:
  - added source_ref provenance resolver modes;
  - wired CLI `--source-fetch-mode proxy|session-store` and `--session-db`;
  - committed as `d0a2263 feat: add sleep hygiene provenance evidence`.
- Task 4:
  - added non-mutating dry-run patch JSON;
  - committed as `8102cea feat: add sleep hygiene dry-run patch report`.
- Task 5:
  - generated formal V3 reports under `my_md/memory_optimization/eval_reports/sleep_hygiene_evidence_v3/`;
  - updated memory optimization docs with V3 results and boundaries.

Current V3 result:

| case_set | cases | rows | cleanup recall | cleanup precision | retained protection | false positive cleanup | merge suggestions | review required | safe cleanup token saving |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| standard | 600 | 600 | 100.0% | 100.0% | 100.0% | 0.0% | 0 | 0 | 64.0138% |
| hard | 320 | 520 | 100.0% | 100.0% | 100.0% | 0.0% | 40 | 120 | 23.7952% |
| overall | 920 | 1120 | 100.0% | 100.0% | 100.0% | 0.0% | 40 | 120 | 42.5121% |

Next:

1. Keep sleep hygiene active gate closed.
2. If stronger evidence is needed, run `--source-fetch-mode session-store --session-db <path>` against fixture or real sessions DB.
3. Add production-like dry-run evidence before allowing any real merge / stale mark / low-value removal.

## 2026-07-22 Source Ref Quality Shadow

Goal: make the source-backed safety gate measurable from the write side, without changing production writes.

Completed in this phase:

- Added source_ref quality shadow normalizer and evaluator.
- Added guarded fixture DB flow so tests use a marked `sessions.db` and refuse unmarked DBs.
- Added same-session validation for both baseline and normalized message-level refs.
- Added CLI report generation under `my_md/memory_optimization/eval_reports/source_ref_quality_shadow_v1/`.
- Recorded metrics:
  - message-level coverage `33.3333% -> 83.3333%`;
  - parse success `66.6667% -> 100.0%`;
  - real source fetch success `33.3333% -> 83.3333%`;
  - source support `16.6667% -> 66.6667%`;
  - source-backed eligible `1/6 -> 4/6`.

Boundaries:

- This is synthetic fixture / shadow-only.
- It does not rewrite existing memory rows.
- It does not change `DefaultMemoryEngine`, `PostResponseMemoryWorker`, `Memorizer`, `MemoryStore2`, retrieval, prompt injection, `AgentLoop`, `Reasoner`, or `ToolExecutor`.
- It does not prove production online uplift.

Next:

1. Because production real samples are not currently available, keep using target-driven test sets rather than claiming production evidence.
2. Use the expanded source_ref quality case pack as the current offline baseline for write-source quality.
3. If stronger realism is needed without production data, run the expanded test set through a controlled AgentLoop shadow harness, still without production memory writes.

## 2026-07-23 Source Ref Quality Expanded Case Pack

Goal: make the source_ref write-quality result more convincing using a broader target-driven test set.

Completed:

- Added `memory2/eval_source_ref_quality_cases.py`.
- Added `200` deterministic cases:
  - common `100`;
  - hard `100`;
  - 10 scenarios x 20 cases.
- Added grouped metrics by:
  - `case_set`;
  - `scenario`.
- Added CLI support for:
  - `--case-pack smoke|expanded`;
  - `--common-per-scenario`;
  - `--hard-per-scenario`.
- Generated report under `my_md/memory_optimization/eval_reports/source_ref_quality_expanded_v1/`.

Current result:

| metric | before | after | delta |
| --- | ---: | ---: | ---: |
| message-level coverage | 40.0% | 90.0% | +50.0 |
| parse success | 80.0% | 100.0% | +20.0 |
| real source fetch success | 20.0% | 80.0% | +60.0 |
| source support | 10.0% | 70.0% | +60.0 |
| source-backed eligible | 20/200 | 140/200 | +120 items |

Boundaries:

- This is synthetic controlled fixture / shadow-only.
- It does not prove production natural traffic uplift.
- It does not modify real memory writes.
- It does not run real online AgentLoop tests.

Next:

1. Use this expanded report as the source_ref write-quality offline evidence.
2. If needed, design a controlled AgentLoop shadow harness for the same test set.
3. Do not active-write normalized `source_ref` until there is evidence from either real samples or a controlled online shadow run.

Documentation note:

- Current Phase 6u conclusion and metric definitions have been synchronized to the memory optimization docs.
- The main conclusion is `source-backed eligible: 20/200 -> 140/200` on the target-driven fixture.
- The current boundary remains unchanged: synthetic fixture / shadow-only, no production natural traffic, no active write-time source_ref change.

## 2026-07-24 Answer Retrieval Metric Report Update

Goal: update the answer/retrieval deterministic count report to show interview-friendly uplift against the original memory baseline.

Plan after review:

1. Add relative percentage fields to the single-module table:
   - relative recall lift percent;
   - miss reduction rate percent.
2. Add adjacent and cumulative percentage fields to the chain table:
   - adjacent relative recall lift percent;
   - adjacent miss reduction rate percent;
   - cumulative miss reduction count;
   - cumulative relative recall lift percent;
   - cumulative miss reduction rate percent.
3. Update markdown output and docs with formula notes.
4. Keep answer correctness, evidence hit, noise control, and context cost as future online / trace-evidence metrics, not measured offline result tables.

Current status: implementation complete and verified.

Completed result:

- Single-module table now includes:
  - relative recall lift percent;
  - miss reduction rate percent.
- Chain table now includes:
  - adjacent relative recall lift percent;
  - adjacent miss reduction rate percent;
  - cumulative miss reduction count;
  - cumulative relative recall lift percent;
  - cumulative miss reduction rate percent.
- Regenerated report:
  - `my_md/memory_optimization/eval_reports/memory_answer_retrieval_counts_eval.json`;
  - `my_md/memory_optimization/eval_reports/memory_answer_retrieval_counts_eval.md`.
- Key regenerated numbers:
  - tri retrieval: `2000/2000`, relative recall lift `1.1122%`, miss reduction `100.0%`;
  - graph retrieval: `1994/2000`, relative recall lift `0.8089%`, miss reduction `72.7273%`;
  - chain all on: `1998/2000`, cumulative relative recall lift `1.0111%`, cumulative miss reduction `90.9091%`.
- Boundary remains:
  - answer correctness, evidence hit, noise control, and context cost are not measured by this offline deterministic count report;
  - they require online shadow / agent dry-run trace evidence.

Verification:

- `.venv/bin/python -m pytest tests/test_memory_answer_retrieval_counts.py tests/test_memory_answer_retrieval_counts_cli.py -q -p no:cacheprovider` => `9 passed in 103.19s`.
- `git diff --check` => passed.

Documentation sync:

- Updated `02-memory-quality-metrics.md` with Phase 6m Answer Comprehensive V2 data, formulas, and offline-only boundary.
- Updated `05-memory-target-metric-eval-plan.md` with the current recall coverage table and the online evidence required for answer correctness, evidence hit, noise control, and context cost.
- Updated `04-memory-plugin-experiment-roadmap.md` with the current recall coverage results in the Phase 6f/6m roadmap section.

## 2026-07-24 Memory Answer Quality Online Uplift Report

Goal: add an answer-quality uplift layer to the comprehensive online report so answer correctness, grounding, forbidden/noise, token, and latency can be compared against original memory baseline without polluting the offline recall-count report.

1. Write and verify RED tests for profile uplift rows - complete
2. Implement profile uplift fields in `_metrics_from_results()` and `_empty_metrics()` - complete
3. Write and verify RED tests for chain answer-quality rows - complete
4. Implement chain adjacent/cumulative rows - complete
5. Write and verify RED tests for Markdown answer-quality sections - complete
6. Render answer-quality, chain, and cost/latency Markdown tables - complete
7. Add formula / zero denominator / partial-matrix regression test - complete
8. Run fake-provider smoke report - complete
9. Try checkpoint-only real report rebuild - blocked by missing local checkpoint
10. Update memory optimization docs and planning records - complete
11. Final verification and commit - pending

Implemented fields:

- `ANSWER_QUALITY_PROFILES`
- `profile_answer_quality_uplift_vs_memory_base`
- `chain_answer_quality_uplift_rows`
- `answer_quality_required_profiles`
- `answer_quality_missing_profiles`
- `answer_quality_partial_matrix`

Current fake-provider smoke:

- report path: `/tmp/akashic-memory-answer-quality-uplift-fake/reports/memory_comprehensive_online_eval.json`
- markdown path: `/tmp/akashic-memory-answer-quality-uplift-fake/reports/memory_comprehensive_online_eval.md`
- `case_count = 240`
- `profile_count = 6`
- `real_llm_enabled = False`
- `infra_passed = True`
- `answer_quality_partial_matrix = False`
- `answer_quality_missing_profiles = []`

Boundaries:

- This is report/evaluation code only; no production AgentLoop, Reasoner, ToolExecutor, ToolRegistry, memory write, or observe DB behavior changed.
- `chain_write_value` and `chain_sleep_consolidation` are excluded from the answer-quality table.
- `chain_all_on` is marked `combo/check`, not interpreted as a pure single-module answer/retrieval gain.
- Fake-provider smoke validates schema and calculations only; it is not real LLM performance evidence.
- Existing checkpoint `/tmp/akashic-memory-phase6k-real/reports/memory_comprehensive_online_eval.checkpoint.jsonl` is absent in the current environment, so no checkpoint-only real report was rebuilt in this pass.

Verification so far:

- `.venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py -q -p no:cacheprovider` -> `14 passed in 7.74s`.
- `.venv/bin/python -m pytest tests/test_memory_comprehensive_online_cli.py -q -p no:cacheprovider` -> `8 passed in 9.35s`.

## 2026-07-27 Memory Route Governance Small Online Eval

Goal: after adding route governance, run a short real LLM fresh rerun for answer/retrieval profiles and record whether the routed path is worth expanding.

Plan status:

1. Revise plan after independent review - complete.
2. Run fake-provider balanced smoke - complete.
3. Run real LLM common 20 + hard 20 balanced matrix - complete.
4. Rebuild checkpoint-only report and validate data integrity - complete.
5. Update docs and reports - complete.
6. Final verification and commit - pending.

Report:

- `my_md/memory_optimization/eval_reports/route_governance_small_online_v1/memory_comprehensive_online_eval.json`
- `my_md/memory_optimization/eval_reports/route_governance_small_online_v1/memory_comprehensive_online_eval.md`

Run shape:

- `unique_case_count = 40`
- common `20`, hard `20`
- `profile_count = 4`
- profiles: `chain_memory_base`, `chain_tri_retrieval`, `chain_graph_retrieval`, `chain_rerank_injection`
- `completed_call_count = 160`
- `real_llm_enabled = True`
- `provider_error_count = 0`
- `timeout_count = 0`
- `excluded_infra_failure_count = 0`
- `partial_due_to_infra_failure = False`

Key results:

| profile | answer_success | answer_rate | relative answer lift vs base | grounding_rate | forbidden_rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| `chain_memory_base` | `13/40` | `32.5%` | `0%` | `100%` | `15%` |
| `chain_tri_retrieval` | `17/40` | `42.5%` | `+30.7692%` | `100%` | `12.5%` |
| `chain_graph_retrieval` | `13/40` | `32.5%` | `0%` | `100%` | `15%` |
| `chain_rerank_injection` | `18/40` | `45%` | `+38.4615%` | `100%` | `10%` |

Conclusion:

- This is a short controlled online result, not a production/full-matrix claim.
- Tri retrieval is positive after route governance on this slice.
- Graph retrieval is still not better than the original memory baseline on this slice, but current answer-quality fixtures do not isolate graph evidence from tri evidence well enough to treat this as a standalone graph-capability verdict.
- Rerank/injection is the strongest routed answer path and should be prioritized for the next expanded fresh rerun.

## 2026-07-28 Memory Tri Candidate Governance

Goal: execute the reviewed plan for tri retrieval candidate denoising and forbidden / conflict filtering, producing offline trace evidence before spending more real LLM calls.

Plan status:

1. Add candidate risk classification - complete.
2. Add strict candidate governance policy and trace fields - complete.
3. Add offline tri candidate governance report - complete.
4. Add CLI wrapper and privacy tests - complete.
5. Generate comprehensive report - complete.
6. Update memory optimization docs and progress records - complete.
7. Run final regression, compile, diff check, independent review, and commit - pending.

Report:

- `my_md/memory_optimization/eval_reports/tri_candidate_governance_v1/tri_candidate_governance.json`
- `my_md/memory_optimization/eval_reports/tri_candidate_governance_v1/tri_candidate_governance.md`

Key offline result:

| metric | value |
| --- | ---: |
| `case_count` | `320` |
| target evidence | `640` |
| baseline expected hits | `640/640` |
| protected strict expected hits | `640/640` |
| protected target loss | `0` |
| should-not candidates | `368` |
| strict should-not drops | `368/368` |
| strict should-not kept | `0` |
| unprotected strict target loss | `640/640` |

Interpretation:

- This phase proves the candidate governance layer can be measured and can remove known bad candidates without losing protected target evidence.
- It also proves a risky point: strict filtering without target protection is too aggressive on the current fixture because weak source_ref appears on many expected memories.
- The next meaningful answer-quality check should be a small fresh real LLM rerun comparing current route-governed tri retrieval against candidate-governed tri retrieval, focused on forbidden rate and grounded-answer-rule misses.

## 2026-07-28 Tri Candidate Governance Small Online Plan

Goal: run a bounded real LLM small online comparison for the candidate-governed tri retrieval path.

Plan:

- `docs/superpowers/plans/2026-07-28-tri-candidate-governance-small-online.md`

Current status:

1. Record latest offline tri candidate governance data - complete.
2. Create formal implementation plan using writing-plans skill - complete.
3. Review plan with independent reviewer - complete.
4. Revise plan after review - complete.
5. Implement eval-only `chain_tri_candidate_governance` profile - complete.
6. Add balanced common/hard small case selection to CLI - complete.
7. Run fake-provider smoke and integrity check - complete.
8. Run real LLM 40-case / 120-call small matrix - complete.
9. Update docs and commit - in progress.

Planned small test shape:

| item | value |
| --- | --- |
| unique cases | `40` |
| split | common `20` + hard `20` |
| profiles | `chain_memory_base`, `chain_tri_retrieval`, `chain_tri_candidate_governance` |
| prompt variants | `baseline` |
| repeats | `1` |
| expected real LLM calls | `120` |
| output dir | `my_md/memory_optimization/eval_reports/tri_candidate_governance_small_online_v1` |

Main decision criteria:

- If governed tri forbidden rate drops and answer rate does not fall, expand to a larger rerun.
- If forbidden drops but answer does not improve, prioritize evidence injection and answer constraints.
- If grounding drops, tune candidate governance false positives before more online runs.
- Because the governed tri profile is oracle-protected in eval, any positive result must be described as controlled test-set evidence, not production readiness.

Plan review / revision notes:

- Independent review found no Critical issues, but required fixes before execution.
- The plan now requires explicit JSON and Markdown metadata for `chain_tri_candidate_governance`: `eval_only = true`, `oracle_protected = true`, `uses_fixture_expected_ids = true`.
- The governed profile is no longer described as re-running tri lanes. It is now a strict, order-preserving filter over existing `tri_retrieval.fused_ids`.
- Tests now cover the final 40-case selection, should-not removal, target preservation, duplicate prevention, and optional profile Markdown visibility.
- Fake and real commands use a temp empty `--real-memory-workspace` to avoid accidental read-only sampling from the default workspace.

Execution result:

- Fake-provider smoke passed: `case_count = 120`, `unique_case_count = 40`, `profile_count = 3`, `provider_error_count = 0`, `timeout_count = 0`.
- Real LLM small online run passed infrastructure gates: `case_count = 120`, `unique_case_count = 40`, `completed_call_count = 120`, `provider_error_count = 0`, `timeout_count = 0`.
- Real LLM output dir: `my_md/memory_optimization/eval_reports/tri_candidate_governance_small_online_v1`.

| profile | answer_success | answer_rate | grounding_rate | forbidden_rate | avg_tokens | avg_latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `chain_memory_base` | `20/40` | `50.0%` | `100.0%` | `10.0%` | `5486.7` | `4785.5` |
| `chain_tri_retrieval` | `22/40` | `55.0%` | `100.0%` | `15.0%` | `5529.875` | `4922.225` |
| `chain_tri_candidate_governance` | `17/40` | `42.5%` | `100.0%` | `0.0%` | `5383.225` | `3988.775` |

Conclusion:

- The candidate governance layer succeeded on forbidden control: `chain_tri_candidate_governance` reduced forbidden violations from tri retrieval's `15.0%` to `0.0%`.
- It did not satisfy the planned answer-quality success gate: answer rate dropped from tri retrieval's `55.0%` to `42.5%`.
- Grounding stayed at `100.0%`, so the next bottleneck is not target recall but recall-after-answer quality: evidence injection, answer constraints, candidate confidence routing, and fallback behavior.

## 2026-07-28 Memory Tri Answer Contract

Goal: test whether structured answer-contract evidence injection fixes tri retrieval's post-grounding answer-quality failures without changing production retrieval or prompt behavior.

1. Add pure answer-contract helper and tests - complete
2. Add eval-only `chain_tri_answer_contract` profile - complete
3. Run fake-provider smoke and focused regression - complete
4. Run bounded real LLM comparison and document measured outcome - complete
5. Commit locally without push - pending

## 2026-07-28 Memory P6o1 Governed Answer Contract

Goal: add eval-only `chain_tri_governed_answer_contract` wiring so the next real A/B can test candidate governance plus answer contract.

Plan:

- `docs/superpowers/plans/2026-07-28-memory-p6o1-governed-answer-contract.md`

Current status:

1. Extend pure answer contract helper for governed allowed ids - complete.
2. Register governed answer contract profile in comprehensive online eval - complete.
3. Run fake-provider smoke and metadata regression - complete.
4. Update docs and commit locally without push - in progress.

Fake-provider smoke:

- output dir: `/tmp/akashic-memory-p6o1-governed-answer-contract-fake/reports`;
- profiles: `chain_memory_base`, `chain_tri_retrieval`, `chain_tri_candidate_governance`, `chain_tri_answer_contract`, `chain_tri_governed_answer_contract`;
- split: common `20` + hard `20`;
- prompt variant: `baseline`;
- repeats: `1`;
- `case_count = 200`;
- `unique_case_count = 40`;
- `profile_count = 5`;
- `real_llm_enabled = False`;
- `provider_error_count = 0`;
- `timeout_count = 0`.

Boundary:

- eval-only profile wiring, fake-provider smoke, metadata, docs;
- no real LLM in P6o-1;
- no production `AgentLoop`, `Reasoner`, `ToolExecutor`, memory write, production prompt, or old `Retriever.retrieve()` contract changes.

Next real A/B criteria:

- answer_rate close to or above `75.0%`;
- grounding_rate remains `100.0%`;
- forbidden_rate below `12.5%`;
- no obvious token blow-up.

## 2026-07-28 Memory P6o2 Risk-Tiered Candidate Governance

Goal: replace eval-only strict candidate filtering with risk-tiered candidate governance before production-safe evidence contract work.

1. Add pure risk tier classification - complete
2. Add tiered candidate governance mode while preserving strict mode - complete
3. Switch eval-only tri candidate/governed profiles to tiered ids - complete
4. Add offline report tier metrics - complete
5. Update docs and commit locally without push - pending

## 2026-07-28 Memory P6o3 Production-Safe Evidence Contract

Goal: replace fixture answer expectations in the governed tri contract path with production-safe evidence contract fields.

1. Add pure production-safe evidence contract helper - complete
2. Switch governed eval profile to production-safe contract - complete
3. Add fake-provider smoke and privacy coverage - complete
4. Update docs and commit locally without push - complete

## 2026-07-28 Memory P6o4 Answer Post-Check Shadow

Goal: record answer post-check shadow diagnostics for the governed production-safe evidence contract without changing answer behavior.

1. Add pure answer post-check shadow helper - complete
2. Attach post-check shadow to comprehensive eval reports - complete
3. Add fake-provider smoke and privacy coverage - complete
4. Update docs and commit locally without push - complete

## 2026-07-28 Memory P6o5 Small Real LLM AB

Goal: run a bounded real LLM A/B comparing raw tri retrieval, candidate governance, oracle answer contract, and governed production-safe evidence contract.

Plan:

- `docs/superpowers/plans/2026-07-28-memory-p6o5-small-real-llm-ab.md`

Matrix:

- common `20` + hard `20`;
- prompt variant `baseline`;
- repeats `1`;
- profiles: `chain_tri_retrieval`, `chain_tri_candidate_governance`, `chain_tri_answer_contract`, `chain_tri_governed_answer_contract`;
- expected and completed calls: `160`.

Execution status:

1. Add scaled fake-provider CLI matrix-shape regression - complete.
2. Run full fake-provider 160-row smoke - complete.
3. Run real LLM 160-call matrix - complete.
4. Update docs and commit locally without push - in progress.

Real report:

- `my_md/memory_optimization/eval_reports/p6o5_governed_answer_contract_small_online_v1/memory_comprehensive_online_eval.json`
- `my_md/memory_optimization/eval_reports/p6o5_governed_answer_contract_small_online_v1/memory_comprehensive_online_eval.md`

Real report integrity:

- `real_llm_enabled = True`;
- `case_count = 160`;
- `unique_case_count = 40`;
- `completed_call_count = 160`;
- `profile_count = 4`;
- `prompt_variant_count = 1`;
- `repeat_count = 1`;
- `provider_error_count = 0`;
- `timeout_count = 0`;
- `excluded_infra_failure_count = 0`;
- `partial_due_to_infra_failure = False`.

Per-profile result:

- `chain_tri_retrieval`: answer `15/40 = 37.5%`, grounding `100.0%`, forbidden `12.5%`, avg tokens `5518.825`.
- `chain_tri_candidate_governance`: answer `20/40 = 50.0%`, grounding `100.0%`, forbidden `15.0%`, avg tokens `5538.125`.
- `chain_tri_answer_contract`: answer `32/40 = 80.0%`, grounding `100.0%`, forbidden `15.0%`, avg tokens `5688.775`.
- `chain_tri_governed_answer_contract`: answer `39/40 = 97.5%`, grounding `100.0%`, forbidden `0.0%`, avg tokens `6079.675`.

Post-check shadow:

- `case_count = 40`;
- `enabled_case_count = 40`;
- `needs_retry_count = 0`;
- `forbidden_boundary_included_count = 0`;
- `missing_likely_relevant_context_count = 0`;
- `stale_evidence_included_count = 0`;
- `conflict_evidence_included_count = 0`;
- `insufficient_fallback_missing_count = 0`.

Conclusion:

- `chain_tri_governed_answer_contract` is the best P6o-5 profile: it combines candidate governance and production-safe evidence contract, reaching `97.5%` answer rate with `0.0%` forbidden.
- Raw tri retrieval underperforms because it expands context without answer guidance.
- Candidate governance alone underperforms because it filters input but does not tell the model how to use allowed evidence.
- Oracle answer contract performs well but is not production-safe because it uses fixture answer expectations.
- Post-check shadow ids mean injected/included context ids, not proven answer citation use.

Boundary:

- Small controlled eval only, not production natural traffic.
- No production `AgentLoop`, `Reasoner`, `ToolExecutor`, memory write, production prompt, or old `Retriever.retrieve()` contract changes.
- Next step should be robustness / targeted failure expansion before productionization.

## 2026-07-28 Memory P6o6 Governed Rerank Signal

Goal: execute the first P6o-6 signal-expansion slice by testing rerank as a governed evidence-contract input, without graph/version/all-on productionization.

Plan:

- `docs/superpowers/plans/2026-07-28-memory-p6o6-governed-rerank-signal.md`

Execution status:

1. Write, review, and revise P6o-6 plan - complete.
2. Add custom production evidence contract profile name - complete.
3. Add eval-only `chain_tri_rerank_governed_answer_contract` profile - complete.
4. Add Markdown metadata / fake-provider / CLI smoke coverage - complete.
5. Run full fake-provider gate - complete.
6. Run bounded real LLM matrix - complete.
7. Update docs and commit locally without push - in progress.

Real report:

- `my_md/memory_optimization/eval_reports/p6o6_governed_rerank_small_online_v1/memory_comprehensive_online_eval.json`
- `my_md/memory_optimization/eval_reports/p6o6_governed_rerank_small_online_v1/memory_comprehensive_online_eval.md`

Real report integrity:

- `real_llm_enabled = True`;
- `case_count = 80`;
- `unique_case_count = 40`;
- `completed_call_count = 80`;
- `profile_count = 2`;
- `prompt_variant_count = 1`;
- `repeat_count = 1`;
- `provider_error_count = 0`;
- `timeout_count = 0`;
- JSON / Markdown privacy checks passed.

Per-profile result:

- `chain_tri_governed_answer_contract`: answer `39/40 = 97.5%`, grounding `100.0%`, forbidden `0.0%`, avg tokens `6162.05`.
- `chain_tri_rerank_governed_answer_contract`: answer `40/40 = 100.0%`, grounding `100.0%`, forbidden `0.0%`, avg tokens `6209.475`.

Post-check shadow:

- `case_count = 80`;
- `enabled_case_count = 80`;
- `needs_retry_count = 0`;
- `forbidden_boundary_included_count = 0`;
- `missing_likely_relevant_context_count = 0`;
- `stale_evidence_included_count = 0`;
- `conflict_evidence_included_count = 0`;
- `insufficient_fallback_missing_count = 0`.

Conclusion:

- Rerank helped only as governed-contract internal ordering; it did not expand recall beyond candidate-governed tri ids.
- The rerank-governed profile recovered the remaining P6o-5 `1/40` miss while keeping forbidden at `0.0%`.
- Avg-token overhead versus governed baseline is about `47.425` tokens, roughly `0.77%`.
- This remains controlled eval harness evidence, not production natural traffic.

Next step:

- Test version-boundary governed fields separately.
- Do not add graph or all-on until version-boundary has its own controlled result.

## 2026-07-28 P6o-7 Version-Boundary Governed Slice

Goal: test version-boundary evidence-contract fields as a governed tri signal, without expanding recall and without enabling graph/all-on/rerank combinations.

Plan:

- `docs/superpowers/plans/2026-07-28-memory-p6o7-version-boundary-governed.md`

Execution status:

1. Confirm P6o-6 data is recorded in docs - complete.
2. Write, review, and revise P6o-7 plan - complete.
3. Add version-boundary evidence contract fields - complete.
4. Add eval-only `chain_tri_version_governed_answer_contract` profile - complete.
5. Add fake-provider CLI matrix smoke - complete.
6. Run fake-provider 40-case gate - complete.
7. Run bounded real LLM matrix - complete.
8. Update docs and commit locally without push - in progress.

Real report:

- `my_md/memory_optimization/eval_reports/p6o7_version_boundary_governed_small_online_v1/memory_comprehensive_online_eval.json`
- `my_md/memory_optimization/eval_reports/p6o7_version_boundary_governed_small_online_v1/memory_comprehensive_online_eval.md`

Real report integrity:

- `real_llm_enabled = True`;
- `case_count = 80`;
- `unique_case_count = 40`;
- `completed_call_count = 80`;
- `profile_count = 2`;
- `prompt_variant_count = 1`;
- `repeat_count = 1`;
- `provider_error_count = 0`;
- `timeout_count = 0`;
- JSON / Markdown privacy checks passed.

Per-profile real result:

- `chain_tri_governed_answer_contract`: answer `38/40 = 95.0%`, grounding `100.0%`, forbidden `0.0%`, avg tokens `6170.85`.
- `chain_tri_version_governed_answer_contract`: answer `38/40 = 95.0%`, grounding `100.0%`, forbidden `0.0%`, avg tokens `6052.6`.

Post-check shadow:

- `case_count = 80`;
- `enabled_case_count = 80`;
- `needs_retry_count = 2`;
- `forbidden_boundary_included_count = 0`;
- `missing_likely_relevant_context_count = 0`;
- `stale_evidence_included_count = 0`;
- `conflict_evidence_included_count = 0`;
- `insufficient_fallback_missing_count = 0`.

Conclusion:

- Version-boundary metadata did not expand recall and did not hurt answer, grounding, or forbidden main metrics.
- It reduced token cost by `118.25` avg tokens versus the same-run governed baseline.
- It did not pass the post-check no-rise safety gate: version-governed `needs_retry_count = 2` versus governed `0`, both due to `forbidden_boundary_mentioned` on `hard_version_chain_01` and `hard_stale_sleep_02`.
- Keep version-boundary as eval/shadow evidence-contract metadata for now; do not productionize it alone.

Next step:

- Analyze the two forbidden-boundary mention retries and redesign how forbidden boundary ids are presented or hidden from the model before combining rerank + version.
- Continue deferring graph/all-on until combined governed-contract signals have targeted evidence.

## 2026-07-28 P6o-8 Safe Boundary Presentation

Goal: fix the P6o-7 forbidden-boundary expression risk by hiding model-visible raw forbidden/deleted ids while preserving raw metadata for post-check.

Plan:

- `docs/superpowers/plans/2026-07-28-memory-p6o8-p6o10-boundary-rerank-combo.md`

Execution status:

1. Write, review, and revise the gated P6o-8/P6o-9/P6o-10 plan - complete.
2. Hide model-visible `forbidden_boundary_ids:` and `deleted_evidence_ids:` labels/values - complete.
3. Preserve raw ids in `result.raw["answer_contract"]` for post-check - complete.
4. Add focused contract, engine, and CLI coverage - complete.
5. Run P6o-8 fake-provider gate - complete.
6. Run bounded P6o-8 real LLM matrix - complete.
7. Update docs and commit locally without push - in progress.

Real report:

- `my_md/memory_optimization/eval_reports/p6o8_version_boundary_safe_presentation_small_online_v1/memory_comprehensive_online_eval.json`
- `my_md/memory_optimization/eval_reports/p6o8_version_boundary_safe_presentation_small_online_v1/memory_comprehensive_online_eval.md`

Real report integrity:

- `real_llm_enabled = True`;
- `case_count = 80`;
- `unique_case_count = 40`;
- `completed_call_count = 80`;
- `profile_count = 2`;
- `prompt_variant_count = 1`;
- `repeat_count = 1`;
- `provider_error_count = 0`;
- `timeout_count = 0`;
- JSON / Markdown privacy checks passed.

Per-profile real result:

- `chain_tri_governed_answer_contract`: answer `40/40 = 100.0%`, grounding `100.0%`, forbidden `0.0%`, avg tokens `6171.225`.
- `chain_tri_version_governed_answer_contract`: answer `39/40 = 97.5%`, grounding `100.0%`, forbidden `0.0%`, avg tokens `6054.025`.

Post-check shadow:

- `case_count = 80`;
- `enabled_case_count = 80`;
- `needs_retry_count = 0`;
- `forbidden_boundary_included_count = 0`;
- `missing_likely_relevant_context_count = 0`;
- `stale_evidence_included_count = 0`;
- `conflict_evidence_included_count = 0`;
- `insufficient_fallback_missing_count = 0`.

Conclusion:

- The P6o-7 failure was caused by unsafe model-visible boundary expression, not by the version-boundary metadata itself.
- Hiding raw forbidden/deleted ids restored the post-check no-rise gate: aggregate `needs_retry_count` is now `0`.
- Version-governed answer rate is `2.5` points below the same-run governed baseline, within the `5.0` point gate; grounding and forbidden remain clean, and avg tokens decrease by `117.2`.
- This remains eval/shadow evidence, not production natural traffic.

Next step:

- Run P6o-9 same-matrix comparison for `chain_tri_governed_answer_contract`, `chain_tri_rerank_governed_answer_contract`, and revised `chain_tri_version_governed_answer_contract`.
- Only enter P6o-10 combo implementation if P6o-9 passes the same gates.

## 2026-07-28 P6o-9 Governed/Rerank/Version Same Matrix

Goal: compare existing governed, rerank-governed, and safe version-governed profiles in one real LLM run before adding a combined profile.

Plan:

- `docs/superpowers/plans/2026-07-28-memory-p6o8-p6o10-boundary-rerank-combo.md`

Execution status:

1. Run P6o-9 fake-provider gate - complete.
2. Run bounded P6o-9 real LLM matrix - complete.
3. Assert P6o-9 gate - complete.
4. Update docs and commit locally without push - in progress.

Real report:

- `my_md/memory_optimization/eval_reports/p6o9_governed_rerank_version_same_matrix_v1/memory_comprehensive_online_eval.json`
- `my_md/memory_optimization/eval_reports/p6o9_governed_rerank_version_same_matrix_v1/memory_comprehensive_online_eval.md`

Real report integrity:

- `real_llm_enabled = True`;
- `case_count = 120`;
- `unique_case_count = 40`;
- `completed_call_count = 120`;
- `profile_count = 3`;
- `prompt_variant_count = 1`;
- `repeat_count = 1`;
- `provider_error_count = 0`;
- `timeout_count = 0`;
- JSON / Markdown privacy checks passed.

Per-profile real result:

- `chain_tri_governed_answer_contract`: answer `39/40 = 97.5%`, grounding `100.0%`, forbidden `0.0%`, avg tokens `6156.725`.
- `chain_tri_rerank_governed_answer_contract`: answer `38/40 = 95.0%`, grounding `100.0%`, forbidden `0.0%`, avg tokens `6118.475`.
- `chain_tri_version_governed_answer_contract`: answer `38/40 = 95.0%`, grounding `100.0%`, forbidden `0.0%`, avg tokens `6021.55`.

Post-check shadow:

- `case_count = 120`;
- `enabled_case_count = 120`;
- `needs_retry_count = 0`;
- `forbidden_boundary_included_count = 0`;
- `missing_likely_relevant_context_count = 0`;
- `stale_evidence_included_count = 0`;
- `conflict_evidence_included_count = 0`;
- `insufficient_fallback_missing_count = 0`.

Conclusion:

- Same-run governed is still the strongest standalone profile by answer rate.
- Rerank-governed and safe version-governed both trail governed by `2.5` answer-rate points but pass the configured gate.
- All three preserve grounding `100.0%`, forbidden `0.0%`, and zero post-check risk counts.
- P6o-10 can proceed, but must prove the combination preserves governed evidence ids and does not expand recall.

Next step:

- Add eval-only `chain_tri_rerank_version_governed_answer_contract`.
- Validate combo ordering, no recall expansion, metadata, fake gate, real gate, and docs before considering graph/all-on.

## 2026-07-28 P6o-10 Rerank + Version Governed Combo

Goal: test whether rerank ordering and safe version-boundary metadata are complementary when combined inside the governed evidence contract without recall expansion.

Plan:

- `docs/superpowers/plans/2026-07-28-memory-p6o8-p6o10-boundary-rerank-combo.md`

Execution status:

1. Add eval-only `chain_tri_rerank_version_governed_answer_contract` - complete.
2. Prove combo ids equal rerank-governed ids and have the same set as governed ids - complete.
3. Prove combo contract hides raw forbidden/deleted ids and exposes combined metadata - complete.
4. Run P6o-10 fake-provider gate - complete.
5. Run bounded P6o-10 real LLM matrix - complete.
6. Assert P6o-10 gate - complete.
7. Update docs and commit locally without push - in progress.

Real report:

- `my_md/memory_optimization/eval_reports/p6o10_rerank_version_governed_combo_small_online_v1/memory_comprehensive_online_eval.json`
- `my_md/memory_optimization/eval_reports/p6o10_rerank_version_governed_combo_small_online_v1/memory_comprehensive_online_eval.md`

Real report integrity:

- `real_llm_enabled = True`;
- `case_count = 160`;
- `unique_case_count = 40`;
- `completed_call_count = 160`;
- `profile_count = 4`;
- `prompt_variant_count = 1`;
- `repeat_count = 1`;
- `provider_error_count = 0`;
- `timeout_count = 0`;
- JSON / Markdown privacy checks passed.

Per-profile real result:

- `chain_tri_governed_answer_contract`: answer `39/40 = 97.5%`, grounding `100.0%`, forbidden `0.0%`, avg tokens `6130.1`.
- `chain_tri_rerank_governed_answer_contract`: answer `39/40 = 97.5%`, grounding `100.0%`, forbidden `0.0%`, avg tokens `6131.95`.
- `chain_tri_version_governed_answer_contract`: answer `40/40 = 100.0%`, grounding `100.0%`, forbidden `0.0%`, avg tokens `6004.95`.
- `chain_tri_rerank_version_governed_answer_contract`: answer `39/40 = 97.5%`, grounding `100.0%`, forbidden `0.0%`, avg tokens `6036.7`.

Post-check shadow:

- `case_count = 160`;
- `enabled_case_count = 160`;
- `needs_retry_count = 0`;
- `forbidden_boundary_included_count = 0`;
- `missing_likely_relevant_context_count = 0`;
- `stale_evidence_included_count = 0`;
- `conflict_evidence_included_count = 0`;
- `insufficient_fallback_missing_count = 0`.

Conclusion:

- Combo passes the gate and is safe in this matrix.
- Combo ties governed answer rate, keeps grounding and forbidden clean, and reduces avg tokens by `93.4` versus governed.
- Safe version-governed is the strongest profile in this run: `40/40 = 100.0%`, avg tokens `6004.95`.
- The data does not justify jumping to graph/all-on or production activation; it supports a targeted robustness/failure analysis next.

Next step:

- Compare failure cases and rerun sensitivity for safe version-only vs combo.
- Keep all profiles eval/shadow-only until robustness holds beyond this 40-case small matrix.
