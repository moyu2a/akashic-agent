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

- Quantitative uplift: `baseline_main_score = 94.375`, `all_on_main_score = 69.5543`, `total_uplift_points = -24.8207`.
- Chain uplift: `chain_memory_base = 94.375`, `chain_all_on = 69.5543`, `total_chain_uplift_points = -24.8207`.
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
