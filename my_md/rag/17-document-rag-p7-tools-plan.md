# Document RAG P7 Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the existing Document RAG retriever to the Agent as read-only tools: `search_docs` and `fetch_doc_chunk`.

**Architecture:** Keep Document RAG backend logic inside `doc_rag/*`. Add thin Agent tool wrappers under `agent/tools/*`, then register them through a new bootstrap toolset so AgentLoop does not need direct changes. `search_docs` performs retrieval and returns snippets; `fetch_doc_chunk` expands one chunk by `chunk_id`.

**Tech Stack:** Python 3.12+, existing `Tool` / `ToolRegistry` abstraction, existing `bootstrap.toolsets` wiring, `DocRagRetriever`, `DocRagStore`, pytest with fake retriever/store where possible.

## Global Constraints

- Do not write document chunks into `memory2.db`.
- Do not modify AgentLoop for P7.
- Tools must return structured JSON strings, not prose.
- Tools must be read-only.
- `search_docs` must not return full chunk content by default.
- `fetch_doc_chunk` may return full chunk content only with `max_chars` cap.
- Respect `config.doc_rag.enabled`; Agent tools should return `doc_rag_disabled` when disabled.
- P7 registration strategy: register tools by default through the `doc_rag` toolset, but make tool execution return `doc_rag_disabled` when `config.doc_rag.enabled = false`.
- Do not expose API keys in tool output, trace, logs, or tests.
- Keep `recall_memory` and `search_docs` conceptually separate: memory tool searches user memory; document tool searches indexed Markdown corpus.
- P7 does not enforce final-answer citations. It only returns citation-ready metadata; citation policy is P9.

---

## Current Baseline

P4-P6 already proves:

```text
Markdown files -> loader -> chunker -> embedding -> store -> retriever -> trace
```

Manual verification on 2026-07-10:

- `doc_rag_index_check --rebuild` succeeded.
- 2 documents indexed.
- 11 chunks created.
- all chunks are `embedding_status=ready`.
- retrieval query `agent runtime 负责什么` returned 5 hits.
- top1 hit was `my_md/doc_rag_corpus/manual_test.md > Agent Runtime`.
- JSONL trace was written with `retrieval_mode=vector_only`.

P7 must prove:

```text
Agent tool call -> search_docs / fetch_doc_chunk -> Document RAG backend -> structured evidence
```

## Tool Interface Design

### `search_docs`

Purpose:

- Search indexed Markdown documents.
- Return ranked evidence candidates.
- Provide `trace_id` for debugging and later evaluation.

Parameters:

```json
{
  "query": "agent runtime 负责什么",
  "top_k": 5
}
```

Schema rules:

- `query`: required string, min length 1.
- `top_k`: optional integer, minimum 1, maximum 10.

Success output:

```json
{
  "ok": true,
  "error_code": "",
  "query": "agent runtime 负责什么",
  "top_k": 5,
  "trace_id": "1fd2984b7b504ddda6ea4b1f84de4378",
  "hit_count": 1,
  "hits": [
    {
      "rank": 1,
      "chunk_id": "0cf46daf12216544",
      "source_path": "my_md/doc_rag_corpus/manual_test.md",
      "heading_path": "Agent Runtime",
      "score": 0.806164,
      "score_type": "vector",
      "snippet": "# Agent Runtime Agent runtime 负责管理 agent 的一次运行过程。",
      "chunk_content_hash": "...",
      "document_content_hash": "..."
    }
  ]
}
```

Error output examples:

```json
{"ok": false, "error_code": "doc_rag_disabled", "message": "Document RAG is disabled", "hits": []}
{"ok": false, "error_code": "empty_query", "message": "query is empty", "hits": []}
{"ok": false, "error_code": "invalid_top_k", "message": "top_k must be between 1 and 10", "hits": []}
{"ok": false, "error_code": "retrieval_error", "message": "safe error text", "hits": []}
```

No-hit behavior:

```json
{
  "ok": true,
  "error_code": "",
  "query": "unknown topic",
  "top_k": 5,
  "trace_id": "...",
  "hit_count": 0,
  "hits": []
}
```

Use `ok=true` for no hits because retrieval executed successfully. The Agent should treat `hit_count=0` as "no document evidence found" and should not invent document citations.

Why this design:

- It returns enough evidence for the model to answer without stuffing full documents into context.
- `trace_id` links Agent behavior back to retriever trace.
- `chunk_id` lets the Agent call `fetch_doc_chunk` only when it needs more detail.
- Structured error codes make automated evaluation easier.
- `hit_count=0` separates "retrieval ran but found no evidence" from system/runtime errors.

Why not return full content in `search_docs`:

- Full content can quickly expand context.
- It makes tool calls expensive.
- It mixes recall and evidence expansion into one step, which makes failure attribution harder.

### `fetch_doc_chunk`

Purpose:

- Fetch a full indexed chunk by `chunk_id`.
- Let Agent inspect exact evidence after `search_docs`.

Parameters:

```json
{
  "chunk_id": "0cf46daf12216544",
  "max_chars": 2000
}
```

Schema rules:

- `chunk_id`: required string.
- `max_chars`: optional integer, minimum 200, maximum 8000, default 2000.

Success output:

```json
{
  "ok": true,
  "error_code": "",
  "chunk": {
    "chunk_id": "0cf46daf12216544",
    "source_path": "my_md/doc_rag_corpus/manual_test.md",
    "title": "Agent Runtime",
    "heading_path": "Agent Runtime",
    "chunk_index": 0,
    "content": "# Agent Runtime\n\nAgent runtime 负责管理 agent 的一次运行过程。",
    "content_truncated": false,
    "chunk_content_hash": "...",
    "document_content_hash": "..."
  }
}
```

Error output examples:

```json
{"ok": false, "error_code": "doc_rag_disabled", "message": "Document RAG is disabled"}
{"ok": false, "error_code": "invalid_chunk_id", "message": "chunk_id is empty"}
{"ok": false, "error_code": "invalid_max_chars", "message": "max_chars must be between 200 and 8000"}
{"ok": false, "error_code": "chunk_not_found", "message": "chunk not found"}
```

Why this design:

- It keeps `search_docs` lightweight.
- It gives the Agent a second step to fetch exact evidence only when needed.
- It supports citation and evaluation because source metadata stays attached to content.

## File Structure

Create:

- `agent/tools/doc_rag.py`: `SearchDocsTool`, `FetchDocChunkTool`, JSON response helpers.
- `bootstrap/toolsets/doc_rag.py`: `DocRagToolsetProvider` registering the two tools.
- `tests/test_doc_rag_tools.py`: unit tests for tool output, error codes, truncation, disabled behavior.
- `tests/test_doc_rag_toolset.py`: unit tests for ToolRegistry registration and wiring.

No new manual helper script is planned for P7. Manual backend checks should use pytest-level tool execution and the existing index/retrieve scripts; Agent-level checks should use the existing CLI.

Modify:

- `bootstrap/wiring.py`: add `"doc_rag"` to `_TOOLSET_WIRING`.
- `agent/config_models.py`: add `"doc_rag"` to default `WiringConfig.toolsets`.
- `agent/config.py`: add `"doc_rag"` to default loaded toolsets.
- `config.example.toml`: update commented `[agent.wiring] toolsets` example.
- `my_md/rag/11-document-rag-implementation-plan.md`: mark P7/P8 progress after implementation.

Do not modify:

- `agent/looping/*`
- `doc_rag/indexer.py`
- `doc_rag/chunker.py`
- `doc_rag/loader.py`
- `memory2/*`

## Task 1: Tool Classes

**Files:**

- Create: `agent/tools/doc_rag.py`
- Test: `tests/test_doc_rag_tools.py`

**Interfaces:**

- Consumes: `agent.tools.base.Tool`, `DocRagRetriever.search`, `DocRagStore.get_chunk`, `Config.doc_rag`.
- Produces: `SearchDocsTool`, `FetchDocChunkTool`.

Constructor and lifecycle requirements:

- `SearchDocsTool(config: Config, retriever: DocRagRetriever | None = None)`.
- `FetchDocChunkTool(config: Config, store: DocRagStore | None = None)`.
- Tests inject fake retriever/store so unit tests never call real embedding APIs.
- Production path lazily creates `DocRagRetriever(config)` or `DocRagStore(config.doc_rag.store_path, vec_dim=config.doc_rag.embedding.dim)` only when the tool is executed and `doc_rag.enabled` is true.
- Tool wrappers do not own long-running background tasks.
- Tool wrappers should expose `close()` only if a future store/retriever resource requires explicit cleanup; P7 can rely on SQLite connection lifetime matching process lifetime unless tests prove otherwise.
- Tool execution must catch backend exceptions and return `retrieval_error` / `store_error` JSON instead of raising.

Step plan:

- [x] Write failing tests for `search_docs` success output.
- [x] Write failing tests for `search_docs` no-hit output with `ok=true`, `hit_count=0`, `hits=[]`.
- [x] Write failing tests for `search_docs` disabled output.
- [x] Write failing tests for empty query and invalid top_k.
- [x] Write failing tests for `fetch_doc_chunk` success output.
- [x] Write failing tests for chunk truncation and chunk_not_found.
- [x] Write failing tests proving fake retriever/store injection avoids real embedding and real SQLite dependencies.
- [x] Implement minimal tool classes.
- [x] Run `uv run --with pytest pytest tests/test_doc_rag_tools.py -v`.

Implementation result:

- Added `agent/tools/doc_rag.py`.
- `tests/test_doc_rag_tools.py` passes: `9 passed, 1 warning`.
- Tool backend errors are returned as structured JSON and redact configured API keys.

Expected behavior:

- Tools return JSON strings.
- JSON has stable `ok` and `error_code` fields.
- `search_docs` never returns full content.
- `fetch_doc_chunk` caps content and sets `content_truncated`.
- No-hit retrieval is not an error: `ok=true`, `hit_count=0`, `hits=[]`.
- Backend failures are structured errors, not thrown exceptions.

## Task 2: Toolset Registration

**Files:**

- Create: `bootstrap/toolsets/doc_rag.py`
- Modify: `bootstrap/wiring.py`
- Modify: `agent/config_models.py`
- Modify: `agent/config.py`
- Modify: `config.example.toml`
- Test: `tests/test_doc_rag_toolset.py`

**Interfaces:**

- Consumes: `ToolRegistry.register`, `ToolsetDeps.config`.
- Produces: `DocRagToolsetProvider`.

Step plan:

- [x] Write failing test that `DocRagToolsetProvider` registers `search_docs` and `fetch_doc_chunk`.
- [x] Write failing test that `resolve_toolset_provider("doc_rag")` returns the provider.
- [x] Write failing config test that default wiring includes `"doc_rag"`.
- [x] Implement provider and wiring registration.
- [x] Update `config.example.toml` commented toolset list.
- [x] Run `uv run --with pytest pytest tests/test_doc_rag_toolset.py tests/test_doc_rag_config.py -v`.

Implementation result:

- Added `bootstrap/toolsets/doc_rag.py`.
- Updated `bootstrap/wiring.py`, `agent/config_models.py`, `agent/config.py`, and `config.example.toml`.
- `tests/test_doc_rag_toolset.py tests/test_doc_rag_config.py` passes: `5 passed, 1 warning`.

Expected behavior:

- Both tools are registered as read-only.
- Tools are not always-on unless explicitly chosen later.
- Tool search can discover them through name/description/search_hint.
- Tools are registered even when `doc_rag.enabled = false`; disabled behavior is handled at execution time with `doc_rag_disabled`.

Why register even when disabled:

- It keeps the toolset shape stable across environments.
- The Agent can receive a structured disabled response instead of an unknown-tool failure.
- It avoids rebuilding the tool registry when config changes from disabled to enabled.

Risk:

- The Agent may discover a disabled tool. The tool description and disabled response must make the state explicit.

## Task 3: Manual Backend Tool Test

**Files:**

- Modify: `my_md/rag/11-document-rag-implementation-plan.md`
- Modify: `my_md/rag/17-document-rag-p7-tools-plan.md`

Step plan:

- [ ] Run indexing first:

```bash
uv run python -m scripts.doc_rag_index_check --rebuild
```

- [x] Run indexing first.
- [x] Run pytest-level direct tool execution through `tests/test_doc_rag_tools.py`; do not add a new helper script in P7.
- [x] Verify `search_docs` returns top1 `manual_test.md > Agent Runtime` for `agent runtime 负责什么`.
- [x] Verify `fetch_doc_chunk` can fetch the returned `chunk_id`.
- [x] Record actual result in `my_md/rag/11-document-rag-implementation-plan.md`.

Indexing result:

```text
status: succeeded
run_id: 60ef858e6a604bd6b42f77bc4045889e
docs_scanned: 2
docs_indexed: 2
docs_skipped: 0
docs_deleted: 0
docs_failed: 0
chunks_created: 11
embedding_failed: 0
store_path: ~/.akashic/workspace/doc_rag/doc_rag.db
```

Actual result:

```text
search_ok: True
search_error:
hit_count: 5
top1_source: my_md/doc_rag_corpus/manual_test.md
top1_heading: Agent Runtime
top1_chunk: 0cf46daf12216544
fetch_ok: True
fetch_error:
fetch_source: my_md/doc_rag_corpus/manual_test.md
fetch_heading: Agent Runtime
fetch_chars: 50
```

Expected behavior:

- `search_docs` output includes `trace_id`.
- `fetch_doc_chunk` output includes capped content and citation metadata.
- No additional manual script is required for this phase.

## Task 4: CLI Agent Smoke Test

**Files:**

- No source file changes expected after Task 1/2.
- Update: `my_md/rag/11-document-rag-implementation-plan.md`

Step plan:

- [ ] Start Agent server:
- [x] Start Agent server with a temporary smoke config:

```bash
uv run python main.py --config /tmp/akashic-doc-rag-smoke.toml --port 2237
```

- [x] Send a CLI-equivalent IPC message to the temporary socket:

```bash
socket=/tmp/akashic-doc-rag-smoke.sock
```

- [x] Ask:

```text
请从文档知识库中检索 agent runtime 负责什么？
```

- [ ] Expected tool behavior:

```text
Agent calls search_docs.
If needed, Agent calls fetch_doc_chunk.
Agent answer is based on returned document evidence and may mention source_path/heading_path naturally.
```

- [ ] Check server logs for tool calls.
- [x] Check server logs / response metadata for tool calls.
- [x] Check retrieval trace JSONL for corresponding `trace_id`.
- [x] Record actual behavior and gaps.

Actual behavior on 2026-07-10:

- Used temporary config only; the project `config.toml` was not changed.
- Temporary config set `doc_rag.enabled=true` and socket `/tmp/akashic-doc-rag-smoke.sock`.
- Agent tool chain: `tool_search` -> `search_docs` -> `read_file`.
- `search_docs` returned `ok=true`, `hit_count=5`, `trace_id=90eaa095ed4940f3912cc969de9f6e31`.
- Top1 hit: `my_md/doc_rag_corpus/manual_test.md > Agent Runtime`, `chunk_id=0cf46daf12216544`, score `0.806164`.
- Assistant answer was grounded in the top document evidence: "Agent runtime 负责管理 agent 的一次运行过程。"
- Retrieval trace JSONL contains the same trace id and five hits.
- No `recall_memory` call was used for this document question.

Observed gap:

- Agent chose `read_file` to inspect the source file after `search_docs`, instead of `fetch_doc_chunk`.
- This does not fail P7 because `search_docs` worked and direct `fetch_doc_chunk` was already verified, but it should be addressed in P9/P10 by prompt/tool guidance and eval cases that prefer `fetch_doc_chunk` for chunk expansion.

Expected result:

- Agent can discover and call Document RAG tools.
- Answer is grounded in indexed Markdown docs.
- Tool calls do not use `recall_memory` for document knowledge.
- Do not fail P7 solely because the final answer lacks formal citation syntax; citation enforcement belongs to P9.

## Task 5: Verification

Run:

```bash
uv run --with pytest pytest \
  tests/test_doc_rag_config.py \
  tests/test_doc_rag_models.py \
  tests/test_doc_rag_store.py \
  tests/test_doc_rag_store_search.py \
  tests/test_doc_rag_loader.py \
  tests/test_doc_rag_chunker.py \
  tests/test_doc_rag_embedding.py \
  tests/test_doc_rag_indexer.py \
  tests/test_doc_rag_retriever.py \
  tests/test_doc_rag_scripts.py \
  tests/test_doc_rag_tools.py \
  tests/test_doc_rag_toolset.py \
  -v

uv run --with pytest pytest \
  tests/test_memory2_retrieval_baseline.py \
  tests/test_tool_discovery_routing.py \
  -v

uv run --with black black --check \
  doc_rag \
  agent/tools/doc_rag.py \
  bootstrap/toolsets/doc_rag.py \
  tests/test_doc_rag_*.py \
  scripts/doc_rag_index_check.py \
  scripts/doc_rag_retrieve_check.py

python3 -m compileall -q doc_rag agent/tools bootstrap/toolsets scripts
```

Expected:

- All new and existing Doc RAG tests pass.
- Existing memory/tool routing regression still passes.
- Formatting and syntax checks pass.

Actual result on 2026-07-10:

- Doc RAG test matrix: `58 passed, 1 warning`.
- Existing memory/tool discovery regression: `16 passed, 1 warning`.
- Black check: passed.
- Compile check: `python3 -m compileall -q doc_rag agent/tools bootstrap/toolsets scripts` passed.

## Acceptance Criteria

| Requirement | Acceptance |
| --- | --- |
| `search_docs` works | Returns structured JSON hits with `trace_id` |
| `fetch_doc_chunk` works | Returns exact chunk content capped by `max_chars` |
| Disabled behavior works | Tools return `doc_rag_disabled` when config disables Document RAG |
| Tool registration works | ToolRegistry contains both tools through `doc_rag` toolset |
| No AgentLoop change | No changes under `agent/looping/*` |
| No secret leakage | Outputs do not contain API keys |
| Manual CLI path works | Agent can call document tools from CLI |

## Out of Scope

- Citation enforcement in final answers.
- Retrieval-only evaluation runner.
- Agent e2e evaluation runner.
- Hybrid search.
- Rerank.
- Query rewrite.
- GraphRAG.
- LLM Wiki.

These start after P7-P8 is stable.
