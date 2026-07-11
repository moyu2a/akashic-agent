# Document RAG P10a Findings

## Project Overview

- `akashic-agent` is a Python agent with passive reply loops, tools, plugins, long-term/session memory, and proactive/background workflows.
- Document RAG tools are implemented under `agent/tools/doc_rag.py` and currently registered as deferred read-only tools, not always-on.

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
