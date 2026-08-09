## 2026-08-02 普通插件写工具审批恢复 Findings

- `save_content_item` 已注册为 `risk="write"`，阻塞行为来自治理策略，不是插件未加载。
- runtime 日志中的 `risk_strategy_write_requires_approval` 和 `invoker_reached=false` 说明真实工具没有进入 `ContentLibrary.save_content_item()`。
- `ToolApprovalStore` 当前只持久化 `args_summary_json`，不会保存原始 URL/note/tags；这是正确的脱敏边界。
- `ToolExecutor` 已支持带 `TrustedApprovalContext` 的 approved 普通工具消费和执行，但需要调用方提供原始参数、同一个 request id、同一个 session、同一个 tool、同一个 approval scope 和匹配的 args hash。
- `SideEffectPayloadVault` 已有私有目录、0600 文件、hash 校验、非 symlink 读取/写入等安全基础，但当前限制为 `write_file/edit_file/shell`。
- `plugins/status_commands/plugin.py` 的 `/run_approved_tool` 当前只路由受管 file/shell side-effect runtime；普通插件 write 工具返回 `managed_side_effect_tool_unsupported`。
- `PluginContext` 已向插件提供 `tool_registry`，状态命令可以通过真实 registry 执行工具；这能让 content library 继续使用 runtime registry context 绑定 `channel/chat_id`，避免模型传 scope。
- 保守实现应只开放普通非受管 `risk="write"` 工具恢复执行；`external-side-effect`、`destructive`、未注册工具、跨 session、payload 缺失、hash 不匹配继续拒绝。
- 实现后，普通插件 write 工具恢复执行复用 `ToolExecutor`，因此 approval 会经历 `approved -> consumed -> executed/execution_failed`，而不是由 status command 绕过治理状态机直接调用工具。
- 状态命令回复只暴露执行状态、invoker 状态和工具结果中的安全 `status` 标量，不回显工具原始 output，避免 content item 的 URL/note/tag 等内容从审批恢复命令中泄露。

# Document RAG P10a Findings

## 2026-07-28 Tool Governance P4c/P5a Findings

- P4b was merged into `origin/main` through PR #3; latest main is `7794819`.
- Governance roadmap explicitly lists the next follow-up as P5 queryable persistent `ToolAuditLedger`, then external API side-effect replay.
- The term P4c is best treated as a design-first bridge to that P5 ledger work, not as a new execution capability.
- Existing `agent/policies/tool_audit.py` does not persist a ledger; it builds per-result `audit_trace` metadata for turn trace / observe.
- Existing approval and approved side-effect stores should remain source-of-truth. A queryable ledger should be a sidecar audit projection, not a replacement transaction owner.
- Ledger events must be allowlist-based. Raw shell command, raw tool args, raw file content, raw file path, raw output text, payload path, token, cookie and secret values must not enter ledger rows.
- Ledger write failure should not relabel execution outcome, consume/unconsume approval, or change side-effect runtime status.
- The design spec lives under ignored `docs/`, so force staging is required for this project if the spec should travel with the branch.
- The implementation plan should start with the ledger store and only then wire runtimes; this keeps redaction/query/prune behavior testable before touching executor or side-effect execution paths.
- Plan review found allowlisted metadata keys alone are insufficient; implementation must also reject unsafe values under allowed keys.
- Plan review found fail-open must be tested for approval and side-effect runtime ledger writes, not just executor writes.
- Plan review found `/tool_audit` must be tested through the real `StatusCommands.before_turn_modules()` plugin path and must keep request/approval/tool/event queries session-scoped by default.
- P4c implementation confirms the ledger can stay a sidecar audit projection: executor, approval runtime, approved file side-effect runtime, and approved shell side-effect runtime all write bounded events fail-open without taking over source-of-truth state.
- `/tool_audit` should remain current-session scoped in V1. Broad cross-session/admin search, dashboard views, and richer retention operations need separate authorization design instead of being hidden behind command arguments.
- Final P4c verification required temporary test dependencies `pyyaml`, `html2text`, and `lxml` for existing plugin-manager import paths; with those supplied after final-review fixes, focused governance suite passed `151` tests and P1-P4c baseline passed `193` tests.
- P4c does not make external API side-effect replay safe by itself. That remains the next design target, still requiring private payload retrieval, trusted preview/execution/cancel surfaces, and no raw args in approval/audit stores.
- Final review confirmed that top-level ledger fields need structured sanitization too; metadata allowlists alone are insufficient because event/reason/status fields are also persisted and displayed.
- Shell side-effect failure ledger events should describe source-of-truth state only after the source stores have committed that state; persistence failures need their own bounded audit outcome.

## 2026-07-20 Memory Phase 6k Findings

- The comprehensive fake-provider core matrix can run end to end with the current scripts and produces a 1280-row report for the answer/retrieval slice.
- The real LLM core matrix also works with checkpointing. The run produced `/tmp/akashic-memory-phase6k-real/reports/memory_comprehensive_online_eval.checkpoint.jsonl`, then was manually stopped after 325 real calls to control cost/time.
- The checkpoint report was successfully rebuilt from that file. It records a partial real LLM slice with `case_count = 325`, `unique_case_count = 82`, `profile_count = 4`, `answer_rule_pass_rate = 24.0`, `memory_grounding_pass_rate = 74.7692`, `forbidden_violation_rate = 15.3846`, `avg_latency_ms = 4635.4431`, and `total_token_count = 1754732`.
- The target-metric report conversion initially failed because the writer tried to render version-chain专项 rows for online checkpoint data that only contains answer/retrieval fields. The fix is to keep version-chain专项 rendering offline-only while leaving the online checkpoint rows in the main table.
- After that fix, `/tmp/akashic-memory-phase6k-target/memory_target_metrics_eval.json` and `.md` were generated successfully from the real checkpoint.
- The current real LLM result is intentionally partial. It is useful for validating the checkpoint path and report conversion, but it is not the full 1280-run conclusion.

## 2026-07-20 Memory Phase 6j Findings

- A larger evaluation set can be added without destabilizing previous reports by keeping `standard` as the default case pack and making the larger set explicit through `--case-pack comprehensive`.
- The comprehensive pack now produces 320 deterministic target-oriented cases: common 160 / hard 160, 20 scenario categories, and 8 variants per set.
- This is a target-driven synthetic evaluation set, not natural production traffic. Its purpose is to stress known memory capabilities and boundaries: recall, graph bridge, injection control, version/provenance, write value, session isolation, source_ref, entropy/value, and sleep compaction.
- The existing target metric runner can consume the 320-case pack. The smoke report in `/tmp/akashic-memory-comprehensive-pack` produced 1920 case records, 960 write candidates, and 2400 hygiene scan units.
- The smoke target recall values are high because many comprehensive cases remain easier than the hard-miss fixtures: tri `98.125% -> 100%`, graph `98.75% -> 100%`, rerank/injection `98.125% -> 100%`, version/provenance `97.5% -> 100%`.
- The first comprehensive smoke uncovered one fixture-design issue: the `costly_call_preference` noise text shared strong query keywords and became a ranked-context injection. The root cause was sample content collision with the current deterministic keyword/semantic scoring, not CLI parsing or report generation.
- Write-governance and sleep-consolidation numbers from the comprehensive smoke remain shadow/proxy. They are useful for offline comparison but still do not replace real write evidence or real consolidation evidence.

## Project Overview

- `akashic-agent` is a Python agent with passive reply loops, tools, plugins, long-term/session memory, and proactive/background workflows.
- Document RAG tools are implemented under `agent/tools/doc_rag.py` and currently registered as deferred read-only tools, not always-on.

## 2026-07-20 Memory Phase 6i Findings

- The target-metric report already had online write/hygiene evidence row builders, but the input boundary needed hardening before real evidence could be trusted.
- Evidence inputs now accept JSON arrays, wrapped `{"records": [...]}` JSON, and JSONL.
- Write evidence and hygiene evidence now fail fast on missing fields, unsupported value domains, string booleans, bool token values, negative token values, and nonnumeric token estimates.
- This does not create real write-governance or sleep-consolidation evidence by itself. It makes the evidence ingestion path strict enough for the next phase to collect real records.

## 2026-07-20 Memory Phase 6h Findings

- Phase 6h fixed the remaining graph gap as a denominator issue, not a real graph-lane miss: graph retrieval now uses `expected_graph_recall_ids`, so the report is `97.5% -> 100%` instead of being penalized by tri-retrieval-only misses.
- The forked replacement-chain fixture made `conflict_chain_detection_rate` measurable on hard / overall rows; common stays `unavailable` because it has no forked chain.
- The current formal report is still offline proxy data, not real online LLM evidence. It uses `measurement_mode = offline_trace_real_baseline_target_metrics` and `online_status = gated_no_checkpoint`.
- Write-governance and sleep-consolidation are still shadow / proxy tables. They are useful for structure and comparison, but they do not yet prove real online prompt token reduction or live DB hygiene.
- The next useful step is to add real evidence inputs for write governance and memory hygiene, then rebuild the target-metric report from checkpoint-backed or live rows.

## P10a Requirements

- Strong document intent should make `search_docs` visible for the current turn.
- Strong document intent plus original/evidence expansion intent should make `fetch_doc_chunk` visible for the current turn.
- Strong memory/session intent without strong document intent should suppress current-turn LRU residue for `search_docs` / `fetch_doc_chunk`.
- Intent preload must be turn-local and must not mutate `ToolDiscoveryState`.

## Code Findings

- `DefaultReasoner.run_turn()` reads LRU via `self._discovery.get_preloaded(session.key)` before prompt rendering.
- `DefaultReasoner.run()` computes visible tools from `always_on | preloaded_tools - disabled_tools`.
- `build_turn_injection_prompt()` also receives visible names during prompt rendering, so it must receive the same effective current-turn preload set.

## Live Smoke Failure Investigation

- Current app now also writes workspace logs via `bootstrap.app.configure_workspace_file_logging()`, so IPC/server traces can be reviewed from the workspace log file.
- Recent observe turns for session `cli:cli-140554156611568`:
  - turn 348: first document question, `react_iteration_count=6`, `error=NULL`.
  - turn 349: second "项目文档 + 原文证据" question, `react_iteration_count=10`, `error=NULL`.
- turn 349 persisted successfully to both `observe.turns` and `sessions.messages`; the assistant message length is 1721 chars and `tool_chain` stored in sessions is 86577 chars.
- turn 349 tool path was not the desired `search_docs -> fetch_doc_chunk -> final`; it was `search_docs` followed by `shell` and many `read_file` calls, total 15 tool calls.
- The third prompt did not appear in `observe.turns`, so it likely did not reach the Agent inbound queue. This points to a CLI/IPC connection issue after the second response, not an Agent reasoning crash before commit.
- Historical IPC server behavior assigned CLI session ids from `id(writer)`, so disconnect/reconnect created a new `cli:<id>` session. CLI IPC v2 replaced this with a persistent `client_id` plus `AKASHIC_CLI_SESSION` value.
- User-provided stdout log confirms the sequence:
  - P10a preload worked: `search_docs=yes fetch_doc_chunk=yes`.
  - The model chose `shell` in iteration 2 and then many `read_file` calls.
  - After final reply and observe enqueue, server logged `[cli] client disconnected`.
- User also observed CLI message at 14:27:33: `Separator is found, but chunk is longer than limit`.
- The message comes from Python `asyncio.StreamReader.readline()` / `readuntil()` `LimitOverrunError`, meaning the newline separator was found but the line before it exceeded the reader limit. This makes the CLI disconnect root cause concrete: the IPC newline-delimited JSON response became too large, most likely due to oversized outbound `metadata/tool_chain`.
- Recorded this as:
  - RAG-006 P10a.1 follow-up: strong document turns need non-RAG tool suppression/constraints.
  - CLI-001: CLI/IPC needed stable session ids and outbound metadata trimming; this is now fixed by CLI IPC v2 and user-confirmed default session inheritance on 2026-07-11.

## 2026-07-15 TaskPlan Main-Service Verification

- The current main service runs from `/home/jjh/git_work/akashic-agent`, listens on `/tmp/akashic.sock` and dashboard port `2236`, and remained connected during the smoke.
- Observe turns `389-392` validate pure create, inspect, update, and background observe in exactly two iterations each with no error.
- Pure create exposed only `create_task_plan` and did not execute memory, history, RAG, local-file, or spawn tools.
- TaskPlan completion used `task_plan_completion_capability_satisfied`; all four turns had empty LRU preload.
- SQLite task `task_feebe25a9a8c452cacf652af0c7bd29a` has three steps; Step 1 is completed with the expected result summary.
- The same-day main-service run did not repeat preference, history, or no-create cases. Those remain covered by the 2026-07-14 isolated live smoke and automated regressions.
- The next architectural gap is no longer context authorization. It is recoverable, idempotent single-step execution with explicit side-effect authorization, now registered as open issue `LA-002`.

## LA-002 Design Findings

- Current TaskPlan state is split into `task_plans` and `task_steps`; step status is business progress and should not absorb execution-attempt lifecycle.
- `TaskPlanStore` already uses `BEGIN IMMEDIATE`, foreign keys, and partial uniqueness for active plans. LA-002 should preserve this transaction boundary and add a separate attempt/event schema.
- `TaskPlanService` is the ownership boundary. New recovery and orchestration services must validate the protected session key through it rather than querying rows from tool adapters.
- `TaskPlanTurnContract` is intentionally focused on create/inspect/update plus context retrieval. Execution needs a separate typed contract to avoid coupling planning-context authorization to durable execution state.
- `AgentLoop` currently consumes turns serially, but attempt uniqueness and idempotency must be enforced by SQLite so future concurrency or duplicate transport delivery cannot violate invariants.
- `InboundMessage` has metadata but no universal message ID. IPC v2 currently carries client/session identity but no per-request ID. LA-002 must use a runtime-owned request identity and add a stable transport request ID where available; content hashes are not valid idempotency keys.
- Registry risk metadata already distinguishes `read-only`, `write`, and `external-side-effect`. The first execution scope can automatically allow only exact `read-only` tools and defer all other/unknown risk classes.
- A database transaction cannot provide exactly-once behavior across an external side effect. If the process dies after a tool acts but before finalization, the attempt outcome is unknown and must not be automatically replayed.
- Startup recovery should be complemented by session reconciliation before claim/inspect; waiting authorization can remain waiting, while stale running/pending attempts become blocked with an explicit recovery reason.
- The safe read-only flow needs explicit begin and finish control operations. Arbitrary tool success alone must not mark a TaskPlan step complete.
- Implementation planning confirmed `TaskPlanStore` should remain the single transaction owner; `execution_store.py` will provide connection-scoped SQL helpers rather than opening an independently committed repository.
- `DefaultReasoner.run_turn()` already constructs a typed boundary context before prompt rendering, and `run()` already supports dynamic visibility transitions for LA-001. LA-002 should reuse that mechanism through a separate `TaskExecutionTurnContract`.
- `ToolRegistry.execute()` merges public arguments with protected underscore context last. Runtime-owned `_request_id` and `_attempt_id` can use the same anti-forgery rule as `_session_key`.
- Execution tools should join the existing `task_plan` toolset and return the shared `TaskExecutionService` through toolset extras; a second toolset would make service/store identity easier to miswire.
- `TaskPlanPromptRenderModule` is the correct prompt integration point for a bounded current-attempt summary; full event history should stay in SQLite/observe.
- The config model needs a separate `TaskExecutionConfig` with `enabled=false`; the implementation plan must test that invalid high-risk auto configuration cannot enable write/external/destructive execution.

## 2026-07-20 Memory Target Metric Findings

- Existing layered scoring correctly separates answer, write governance, and memory hygiene, but it still uses score formulas that are hard to explain per module.
- `write_governance` currently depends on `write_value_score` trace, so it should be presented as the effect of enabling write-value governance, not as a number every retrieval module must change.
- `memory_hygiene` currently depends on `sleep_consolidation_shadow` trace, so it should be presented as the effect of enabling sleep consolidation and library-level maintenance.
- Retrieval, graph, rerank, and version/provenance effects are better explained through target recall, answer hit, evidence hit, wrong recall, wrong injection, stale-version misuse, and source support percentages.
- A percentage report should show before percentage, after percentage, percentage-point delta, and relative uplift only when the denominator is valid.
- Real LLM target-metric reporting should reuse comprehensive online checkpoints; changing presentation should not force another expensive provider run.
- The first target-metric report used a presentation baseline (`before = 0`) and therefore overstated retrieval uplift. The realistic report now reads `before` from trace baseline ids or marks unavailable when no baseline event exists.
- With real offline baseline, the Phase 6f 80-case fixture had target recall `100% -> 100%` for tri retrieval, graph retrieval, and rerank/injection. This was more truthful than `0% -> 100%`, but it meant the fixture was not discriminative enough to prove recall uplift. This finding was superseded by Phase 6g hard-miss cases below.
- Version/provenance in Phase 6f reported target recall `100% -> 50%`; this reflected stricter active-leaf selection and showed the case expectations needed to distinguish stale/old targets from active-current targets. This finding was superseded by Phase 6g version-aware metrics below.
- Write governance and hygiene online layers need evidence records; answer-level comprehensive checkpoints alone cannot honestly produce write candidate or scanned-memory health metrics.
- Fake-provider checkpoint smoke must stay separated from formal reports and must be labeled `fake_provider`, not real LLM.
- Rerank/injection governance is the most interpretable governance result in the current target table: target recall stays `100%`, while wrong injection after is `0%`.
- Write governance direction is reasonable but incomplete: pollution block after `100%` and write reduction after `100%` can be inflated by rejecting too much. Future metrics need useful-candidate retention, true false-reject baseline, and future recall usefulness.
- Sleep consolidation direction is reasonable but still shadow-only: token saving after `33.482%` and recall retention after `100%` are estimates from dry-run traces, not proof that the real memory DB was cleaned or real prompt tokens dropped.
- Next work should not start with another costly real LLM run. Fix version-chain target semantics and add harder retrieval cases first, then rerun offline real-baseline target metrics, then rebuild real LLM target tables from checkpoint.

## 2026-07-20 Memory Phase 6g Findings

- The old version/provenance `100% -> 50%` result was a metric semantics problem: `_version_provenance_metrics()` used generic `should_recall_ids` containing both `_target` and `_graph`, but `version_chain.active_leaf_ids` can only contain replacement-chain leaves such as `_target`.
- Version/provenance now uses `expected_active_version_ids` for current-version recall and `expected_stale_version_ids` for stale misuse. Overall current-version recall is now `90% -> 100%`; hard subset is `80% -> 100%`.
- Current generated version fixtures have only `old -> target` replacement chains. There is no forked replacement chain, so `conflict_chain_detection_rate` must remain `unavailable`; reporting `0%` or `100%` would imply a tested capability that the data does not contain.
- The old retrieval `100% -> 100%` result was too easy to prove uplift. Phase 6g adds explicit `baseline_miss_recall_ids` only for selected hard cases so baseline can miss target ids while experimental lanes can recover them.
- Validation is not globally weakened: normal cases still require every `should_recall_ids` item in baseline recalled ids; only explicitly marked baseline-miss ids are skipped for baseline validation.
- Graph retrieval needed an extra correction: graph baseline fused lanes reuse semantic/keyword/provenance lanes, so explicit graph misses must be filtered from those baseline lanes while leaving the graph lane available for experimental recovery.
- Current overall target recall results are: 三路召回 `93.75% -> 100%`, 图谱召回 `93.75% -> 98.75%`, 重排与注入治理 `93.75% -> 100%`, 版本链与溯源 `90% -> 100%`.
- Current hard target recall results are: 三路召回 `87.5% -> 100%`, 图谱召回 `87.5% -> 97.5%`, 版本链当前有效版本 `80% -> 100%`.
- These are still offline target-oriented fixtures, not real online LLM results. The formal report keeps `online_status = gated_no_checkpoint` and `real_llm_used = False`.
- Next useful work: inspect graph hard misses behind the remaining `98.75%`, add forked replacement-chain fixtures, and add write/hygiene evidence before spending more provider tokens.
## 2026-08-05 MiniRoute V2 Dataset Findings

- MiniMind `lora_route_v1` showed stable JSON formatting but weak routing semantics: train exact `29.83%`, valid exact `29.35%`.
- V1 root causes were data/schema issues rather than only训练参数问题:
  - memory labels used `need_tools=false` with `tool_scope=["memory_tools"]`;
  - prompt did not enumerate allowed `intent` / `tool_scope` / `risk_level` values;
  - no fallback tool domain existed for "needs tool but current scopes do not match";
  - chat hard negatives, memory/profile boundaries, file-read/high-risk boundaries were weak;
  - V1 train/valid/test were grouped by intent.
- V2 treats memory as an ability/tool domain at route layer:
  - `memory_query`: `need_memory=true`, `need_tools=true`, `tool_scope=["memory_tools"]`, `risk_level="read_only"`;
  - `profile_update`: `need_memory=true`, `need_tools=true`, `tool_scope=["memory_tools"]`, `risk_level="write"`.
- V2 adds `unknown_tools` to separate "clearly no tool needed" from "needs some tool but cannot map to existing domains".
- V2 prompt enumerates all legal labels and explicitly says MiniRoute output is coarse routing advice, not final tool authorization.
- V2 validator applies stricter consistency rules only to `route_v2_*.jsonl`, preserving V1 historical dataset validation for comparison.
