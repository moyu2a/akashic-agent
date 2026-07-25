# Memory Phase6b-2 Agent Dry-Run Design

## Goal

Phase6b-2 adds a real `AgentLoop` dry-run evaluation layer for memory eval cases. It verifies that fixture or sampled memory cases can pass through the real passive turn pipeline with a fake LLM provider and temporary workspace, without starting `main.py`, calling external models, using embeddings, or writing the user's real workspace.

## Scope

This phase is an integration smoke layer between Phase6a/6b-1 offline reports and later real LLM evaluation.

It must verify:

- A real `AgentLoop` can process eval case queries through `process_direct()`.
- A real `SessionManager` writes only to a temporary workspace.
- A real `DefaultMemoryRetrievalPipeline` calls a controlled memory engine with the case query, session key, channel, chat id, and history.
- A fake LLM provider receives the assembled prompt and returns deterministic text.
- `TurnCommitted` can be observed through the real `EventBus`.
- The report records metrics and failure reasons without raw prompt, memory summary, or session text.

It must not do:

- Start `main.py` or a real IPC server.
- Call real LLM, embedding, network, or external services.
- Write `workspace/memory/memory2.db`, `workspace/sessions.db`, or `workspace/observe/observe.db`.
- Claim final answer quality, grounding, source support, or real token cost.

## Recommended Architecture

Create `memory2/eval_agent_dry_run.py` as a focused harness module.

The harness should define:

- `ScriptedDryRunProvider`: fake LLM provider that records calls and returns deterministic `LLMResponse`.
- `CaseMemoryEngine`: controlled memory engine that satisfies the `MemoryEngine` methods needed by `DefaultMemoryRetrievalPipeline`, records retrieval requests, and returns a context block derived from eval case ids.
- `AgentDryRunCaseResult`: per-case dry-run result with case id, session key, reply length, request counts, event counts, and failure reasons.
- `AgentDryRunReport`: aggregate report with metrics.
- `run_agent_dry_run_case()`: builds a temporary `AgentLoop` and runs one case.
- `run_agent_dry_run_cases()`: runs multiple cases.
- `write_agent_dry_run_json()` and `write_agent_dry_run_markdown()`.

Add `scripts/run_memory_agent_dry_run_eval.py` as a CLI over existing fixture cases:

```text
scripts/run_memory_agent_dry_run_eval.py
  --case-root tests/fixtures/memory_eval_cases
  --workspace /tmp/akashic-memory-agent-dry-run
  --out-dir my_md/memory_optimization/eval_reports
  --limit 9
```

The CLI should write:

- `memory_agent_dry_run_eval.json`
- `memory_agent_dry_run_eval.md`

## Report Contract

The report should include summary metrics:

- `phase6b_level = "agent_dry_run"`
- `agent_loop_enabled = true`
- `fake_llm_enabled = true`
- `llm_calls_enabled = false`
- `embedding_calls_enabled = false`
- `answer_quality_available = false`
- `case_count`
- `passed_case_count`
- `failed_case_count`
- `agent_turn_count`
- `turn_committed_count`
- `retrieval_request_count`
- `fake_llm_call_count`
- `session_message_count`

The report should include records:

- `case_records`: case id, category, session key, channel, chat id, counts, pass/fail, failure reasons.
- `failure_records`: case id plus failure reason.

The report must not include:

- raw memory summaries,
- raw query text,
- assembled prompts,
- full session messages,
- LLM response text.

## Testing Strategy

Unit and integration tests should cover:

- One eval case runs through real `AgentLoop.process_direct()` and returns a deterministic fake reply.
- The controlled memory engine records a retrieval request with the expected session key, channel, and chat id.
- `TurnCommitted` is emitted and observed.
- Temporary `sessions.db` is written under the test workspace, not the repository workspace.
- The report contains counts and records, but not raw fixture memory text.
- The CLI writes both JSON and Markdown reports and exits 0 when at least one case passes.
- The CLI exits 1 when there are no cases or all cases fail, while still writing reports.

## Design Review

- No placeholder requirements remain.
- The phase is narrowly scoped to fake-LLM AgentLoop dry-run and does not overlap with Phase6b-3 real LLM evaluation.
- The harness reuses existing `AgentLoop`, `SessionManager`, `ToolRegistry`, `EventBus`, `EvalCase`, and fixture loader patterns.
- The report boundary matches the existing Phase6b-1 privacy posture.
