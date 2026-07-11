# Document RAG P9 Citation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Document RAG answers cite only real document evidence with `[source_path > heading_path]`, remove or replace fabricated document citations, and inject Document RAG citation rules only when Document RAG is enabled.

**Architecture:** Keep retrieval and storage unchanged. Add citation-ready fields to Document RAG tool outputs, expose global app config to plugins, strengthen tool/prompt guidance, and add a Document RAG citation validator in the existing citation plugin. The validator builds an allowlist from current-turn `search_docs` / `fetch_doc_chunk` tool results, removes unknown document citations from the final reply, appends real tool-derived citations when needed, and skips citation insertion for no-evidence answers. Do not modify AgentLoop.

**Tech Stack:** Python 3.12+, existing `Tool` abstraction, existing `plugins/citation` prompt/after-reasoning lifecycle modules, pytest, IPC CLI smoke test.

## Global Constraints

- Do not write document chunks into `memory2.db`.
- Do not change `doc_rag` indexing, chunking, embedding, or retriever ranking in P9.
- Do not modify AgentLoop for P9.
- Do not mix Document RAG citation with memory citation IDs.
- Memory citation protocol remains `§cited:[id1,id2]§` and stays invisible to users.
- Document RAG citation format is visible to users: `[source_path > heading_path]`.
- Document RAG citations must come only from `search_docs` / `fetch_doc_chunk` tool results.
- Unknown document citations in final answers must not be shown to users.
- Document RAG citation prompt must be injected only when `config.doc_rag.enabled = true`.
- Do not cite `chunk_id` in normal user-facing answers unless debug mode or user explicitly asks for evidence IDs.
- No evidence means no fabricated document citation.
- Do not expose API keys in prompts, tool outputs, traces, tests, or docs.

---

## Current Baseline

P7/P8 proved:

```text
Agent -> tool_search -> search_docs -> Document RAG retriever -> answer
```

Actual CLI smoke on 2026-07-10:

- Agent called `tool_search`.
- Agent called `search_docs`.
- `search_docs` returned `trace_id=90eaa095ed4940f3912cc969de9f6e31`.
- Top1 hit: `my_md/doc_rag_corpus/manual_test.md > Agent Runtime`.
- Agent answered correctly.
- Agent then used `read_file` to inspect the source file instead of `fetch_doc_chunk`.

P9 must improve this into:

```text
Agent -> tool_search -> search_docs -> fetch_doc_chunk when needed -> answer with [source_path > heading_path]
```

P9 does not need to improve ranking quality. Ranking, hybrid search, rerank, and query rewrite are later phases.

## Design Decision

### Chosen Approach

Use five layers together:

1. Tool output carries explicit `citation` fields.
2. `PluginContext` exposes global app config as `app_config`, separate from plugin-local config.
3. Document RAG citation prompt is injected only when `app_config.doc_rag.enabled` is true.
4. Tool descriptions and prompt instructions tell the Agent when to cite and when to call `fetch_doc_chunk`.
5. Existing `plugins/citation` adds a Document RAG citation validator after reasoning.

Why choose this:

- Tool output fields make citation deterministic and testable.
- Conditional prompt injection avoids teaching disabled environments to use unavailable Document RAG behavior.
- Prompt/tool guidance improves the model's natural behavior without changing AgentLoop.
- After-reasoning validation catches two common failure modes: `search_docs` was used but final answer forgot citation, or final answer contains a citation that did not come from current-turn tool results.
- Reusing the existing citation plugin keeps citation concerns in one lifecycle area.
- Exposing `app_config` to plugins is a general capability, but it is implemented narrowly and read-only for this use case.

Why not only rely on prompt:

- The P7/P8 smoke test already showed the model may choose `read_file` after `search_docs`.
- LLMs can forget citation rules under context pressure.
- Prompt-only behavior is harder to evaluate deterministically.

Why not force citation inside `search_docs` answer generation:

- Tools should return evidence, not generate final natural language answers.
- Keeping tools JSON-only preserves testability and separation of concerns.

Why not modify AgentLoop:

- AgentLoop is shared runtime infrastructure.
- Citation can be implemented through existing tool output and plugin lifecycle hooks.
- Avoiding AgentLoop changes keeps P9 scoped and lower-risk.

Why modify `PluginContext`:

- Current `PluginContext.config` is plugin-local config, not global app config.
- The citation plugin cannot reliably know `doc_rag.enabled` without app config.
- Adding `app_config` keeps plugin-local config unchanged and avoids overloading the existing `config` field.
- The change is additive and should not break existing plugins.

Why not reuse memory citation format:

- `§cited:[id]§` is internal metadata for memory persistence.
- Document citations are user-facing source references.
- Mixing them would confuse memory accounting, user output, and evaluation.

## Current Problems And One-Step Solutions

### Problem 1: Fake Document Citations Are Not Actually Prevented

Problem:

- A prompt or light guard can add missing citations, but it cannot guarantee that model-generated citations are real.
- Example bad output:

```text
Agent runtime 负责调度工具。[fake.md > Runtime]
```

One-step solution:

- Add a Document RAG citation validator in `plugins/citation`.
- Extract all visible document citations from the final reply.
- Build `allowed_citations` from current-turn `search_docs` and `fetch_doc_chunk` tool results.
- Remove every visible citation that is not in `allowed_citations`.
- If the answer used Document RAG evidence and lacks an allowed citation, append real citations from `allowed_citations`.
- Record removed fake citations in `ctx.outbound_metadata["doc_rag_citation"]` for observe/eval.

Why this solves the problem:

- The user never sees citations that did not come from current-turn tools.
- Evaluation can still inspect removed fake citations through metadata.
- The solution is deterministic and testable without an LLM judge.

### Problem 2: Guard May Add Citations To No-Evidence Answers

Problem:

- A naive guard sees `search_docs` in tool history and appends citations even when the final answer says there is no enough document evidence.

One-step solution:

- Add `is_doc_rag_no_evidence_reply(reply)` with explicit Chinese and English refusal/no-evidence patterns.
- Skip citation insertion when the final reply says the document knowledge base has no evidence.
- Also skip when `search_docs` returned `hit_count=0`.

Why this solves the problem:

- No-evidence answers stay honest.
- The system does not turn low-confidence or refused answers into cited claims.

### Problem 3: Existing No-Fake-Citation Acceptance Is Too Weak

Problem:

- Checking only `hit_count=0` is insufficient.
- The system must also handle replies that already contain fabricated citations.

One-step solution:

- Add tests for:
  - no hits -> no citation insertion.
  - no-evidence reply -> no citation insertion.
  - fake citation in reply -> fake citation removed.
  - fake citation plus allowed citation -> fake removed, allowed kept.
  - no citation plus allowed citation -> allowed citation appended.

Why this solves the problem:

- The test suite covers both missing citation and fabricated citation paths.
- P10 can build metrics on top of deterministic validator outputs.

### Problem 4: Document RAG Prompt Injection Is Unconditional

Problem:

- Injecting Document RAG citation rules while `doc_rag.enabled=false` adds prompt noise.
- It may encourage the model to search disabled tools or cite unavailable document evidence.

One-step solution:

- Add `app_config: Config | None` to `PluginContext`.
- Pass global `Config` into `PluginManager`.
- When loading each plugin, set `PluginContext.app_config = config`.
- `CitationPromptModule` injects Document RAG citation protocol only when `app_config.doc_rag.enabled is True`.
- Keep memory citation protocol always injected as before.

Why this solves the problem:

- Prompt behavior follows runtime capability.
- Plugin-local `config` remains plugin-local and backward compatible.
- The solution is reusable for future plugins that need read-only app config.

## Target Behavior

### Normal Document Answer

User:

```text
请从文档知识库中检索 agent runtime 负责什么？
```

Expected final answer:

```text
Agent runtime 负责管理 agent 的一次运行过程。[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]
```

### Needs More Evidence

Expected tool path:

```text
tool_search -> search_docs -> fetch_doc_chunk -> final answer with citation
```

Use `fetch_doc_chunk` when:

- snippet is too short to answer confidently.
- user asks for details, exact wording, table content, or configuration.
- answer needs more than one sentence of evidence.

### No Evidence

If `search_docs` returns no hits:

```text
当前文档知识库中没有检索到可引用证据。基于一般经验，我建议……
```

No `[source_path > heading_path]` citation should be fabricated.

## File Structure

Modify:

- `agent/plugins/context.py`: add read-only `app_config` field for global `Config`.
- `agent/plugins/manager.py`: accept optional global app config and pass it into `PluginContext`.
- `bootstrap/tools.py`: construct `PluginManager` with global `Config`.
- `agent/tools/doc_rag.py`: add `citation` field to `search_docs` hits and `fetch_doc_chunk` chunk output; strengthen tool descriptions.
- `bootstrap/toolsets/doc_rag.py`: update search hints if needed.
- `plugins/citation/plugin.py`: conditionally inject Document RAG citation protocol and add after-reasoning citation validator.
- `plugins/citation/README.md`: document memory citation vs Document RAG citation boundary.
- `tests/test_plugin_manager.py`: test plugin context receives global app config.
- `tests/test_doc_rag_tools.py`: test `citation` field and no full content in `search_docs`.
- `tests/test_doc_rag_toolset.py`: test hints/descriptions make `fetch_doc_chunk` discoverable for citation expansion.
- `tests/test_citation_plugin.py` or new `tests/test_doc_rag_citation_plugin.py`: test source extraction, fake citation removal, missing-citation append, and no-evidence behavior.
- `my_md/rag/11-document-rag-implementation-plan.md`: record P9 progress.
- `my_md/rag/17-document-rag-p7-tools-plan.md`: link P9 follow-up if needed.
- `my_md/governance/03-domain-evolution.md`: record RAG evolution after implementation.

Do not modify:

- `agent/looping/*`
- `doc_rag/indexer.py`
- `doc_rag/retriever.py`
- `doc_rag/store.py`
- `memory2/*`

## Task 0: Expose Global App Config To Plugins

**Files:**

- Modify: `agent/plugins/context.py`
- Modify: `agent/plugins/manager.py`
- Modify: `bootstrap/tools.py`
- Test: `tests/test_plugin_manager.py`

**Interfaces:**

- Consumes: global `Config` already available in `bootstrap/tools.py`.
- Produces: `PluginContext.app_config: Config | None`.

- [ ] Add failing test that a loaded plugin receives `context.app_config`.

Add import near the existing imports:

```python
from agent.config_models import Config
```

Add this test near the existing context/config tests in `tests/test_plugin_manager.py`:

```python
@pytest.mark.asyncio
async def test_plugin_context_receives_app_config(tmp_path: Path):
    cfg = Config(
        provider="deepseek",
        model="deepseek-chat",
        api_key="key",
        system_prompt="test",
        base_url="https://example.test/v1",
    )
    shutil.copytree(FIXTURES_DIR / "hello", tmp_path / "hello")

    manager = PluginManager(
        plugin_dirs=[tmp_path],
        event_bus=EventBus(),
        app_config=cfg,
    )
    await manager.load_all()

    instance = _get_instance("hello")
    assert instance.context.app_config is cfg
    assert instance.context.config is None
```

Use existing `tests/test_plugin_manager.py` plugin fixture patterns rather than inventing a new plugin loader pattern.

- [ ] Add `app_config` to `PluginContext`.

Expected change:

```python
if TYPE_CHECKING:
    from agent.config_models import Config
    from agent.plugins.config import PluginConfig

@dataclass
class PluginContext:
    event_bus: Any
    tool_registry: Any
    plugin_id: str
    plugin_dir: Path
    kv_store: "PluginKVStore"
    config: "PluginConfig | None" = None
    app_config: "Config | None" = None
    workspace: Path | None = None
    session_manager: Any = None
    memory_engine: Any = None
```

- [ ] Add optional `app_config` constructor argument to `PluginManager`.

Expected behavior:

```python
class PluginManager:
    def __init__(
        self,
        plugin_dirs: list[Path],
        *,
        event_bus: EventBus,
        tool_registry: Any = None,
        workspace: Path | None = None,
        session_manager: Any = None,
        memory_engine: Any = None,
        app_config: Config | None = None,
    ) -> None:
        self._app_config = app_config
```

- [ ] Pass `app_config` when building `PluginContext`.

Expected change:

```python
instance.context = PluginContext(
    event_bus=self._event_bus,
    tool_registry=self._tool_registry,
    plugin_id=plugin_id,
    plugin_dir=plugin_dir,
    kv_store=PluginKVStore(plugin_dir / ".kv.json"),
    config=plugin_config,
    app_config=self._app_config,
    workspace=self._workspace,
    session_manager=self._session_manager,
    memory_engine=self._memory_engine,
)
```

- [ ] Pass global config from `bootstrap/tools.py`.

Expected change where the plugin manager is constructed:

```python
plugin_manager = _PluginManager(
    plugin_dirs=_resolve_plugin_dirs(workspace),
    event_bus=event_bus,
    tool_registry=tools,
    workspace=workspace,
    session_manager=session_manager,
    memory_engine=memory_runtime.engine,
    app_config=config,
)
```

- [ ] Run tests.

```bash
uv run --with pytest pytest tests/test_plugin_manager.py -v
```

Expected: all selected plugin manager tests pass.

Why this task first:

- Conditional prompt injection depends on global `doc_rag.enabled`.
- `PluginContext.config` is plugin-local config and must not be overloaded.

Risk:

- This touches plugin infrastructure, so regression coverage must include existing plugin manager tests and at least one plugin that only uses plugin-local config.

## Task 1: Add Citation Field To Document RAG Tool Outputs

**Files:**

- Modify: `agent/tools/doc_rag.py`
- Test: `tests/test_doc_rag_tools.py`

**Interfaces:**

- Consumes: `RetrievalHit.source_path`, `RetrievalHit.heading_path`, `ChunkRecord.source_path`, `ChunkRecord.heading_path`.
- Produces: JSON field `citation: str` with format `[source_path > heading_path]` or `[source_path]`.

- [ ] Write failing test for `search_docs` hit citation.

Add assertion to `test_search_docs_returns_structured_hits_without_content`:

```python
assert payload["hits"][0]["citation"] == (
    "[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]"
)
```

- [ ] Write failing test for `fetch_doc_chunk` citation.

Add assertion to `test_fetch_doc_chunk_returns_capped_content`:

```python
assert payload["chunk"]["citation"] == (
    "[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]"
)
```

- [ ] Implement helper in `agent/tools/doc_rag.py`.

```python
def _doc_citation(source_path: str, heading_path: str) -> str:
    source = str(source_path or "").strip()
    heading = str(heading_path or "").strip()
    if source and heading:
        return f"[{source} > {heading}]"
    if source:
        return f"[{source}]"
    return ""
```

- [ ] Add `citation` to `search_docs` hit output.

```python
"citation": _doc_citation(hit.source_path, hit.heading_path),
```

- [ ] Add `citation` to `fetch_doc_chunk` chunk output.

```python
"citation": _doc_citation(chunk.source_path, chunk.heading_path),
```

- [ ] Run tests.

```bash
uv run --with pytest pytest tests/test_doc_rag_tools.py -v
```

Expected:

```text
all selected Document RAG tool tests pass
```

Why this task first:

- It makes citation explicit data rather than a string the model must invent.
- It gives the after-reasoning validator a stable field to parse.

## Task 2: Strengthen Tool Descriptions And Search Hints

**Files:**

- Modify: `agent/tools/doc_rag.py`
- Modify: `bootstrap/toolsets/doc_rag.py`
- Test: `tests/test_doc_rag_toolset.py`

**Interfaces:**

- Consumes: existing tool descriptions and `search_hint`.
- Produces: clearer tool routing guidance.

- [ ] Update `SearchDocsTool.description`.

The description should include these rules:

```text
用于检索已索引的 Markdown 文档知识库。
如果使用本工具结果回答文档问题，最终回答的关键结论必须带 citation 字段中的 [source_path > heading_path] 引用。
如果 snippet 不足以回答，必须继续调用 fetch_doc_chunk，而不是直接改用 read_file。
不要用于查询用户长期记忆。
```

- [ ] Update `FetchDocChunkTool.description`.

The description should include these rules:

```text
根据 search_docs 返回的 chunk_id 读取更完整的文档 chunk。
用于展开 search_docs 命中的证据，优先于 read_file。
最终回答应使用返回的 citation 字段引用来源。
```

- [ ] Update `bootstrap/toolsets/doc_rag.py` search hints.

Expected hints:

```python
search_hint="文档知识库 document rag markdown 检索 search docs citation"
search_hint="文档片段 chunk 原文 fetch content citation 展开证据"
```

- [ ] Add assertions to `tests/test_doc_rag_toolset.py`.

Example:

```python
search_tool = registry.get_tool("search_docs")
fetch_tool = registry.get_tool("fetch_doc_chunk")
assert "fetch_doc_chunk" in search_tool.description
assert "citation" in search_tool.description
assert "优先于 read_file" in fetch_tool.description
```

- [ ] Run tests.

```bash
uv run --with pytest pytest tests/test_doc_rag_toolset.py -v
```

Expected:

```text
all selected Document RAG toolset tests pass
```

Why this task:

- P7/P8 smoke showed the model chose `read_file` after `search_docs`.
- Tool descriptions are part of the model's action policy.
- This is lower risk than changing tool visibility or AgentLoop routing.

Why not make both tools always-on:

- Current P7 design intentionally keeps them non always-on.
- Tool discovery already works through `tool_search`.
- Always-on tools would increase prompt size and token cost before evaluation proves it is needed.

## Task 3: Add Conditional Document RAG Citation Protocol And Validator

**Files:**

- Modify: `plugins/citation/plugin.py`
- Modify: `plugins/citation/README.md`
- Test: new `tests/test_doc_rag_citation_plugin.py`

**Interfaces:**

- Consumes: `AfterReasoningCtx.tool_chain`, tool results from `search_docs` and `fetch_doc_chunk`.
- Consumes: `PluginContext.app_config.doc_rag.enabled`.
- Produces: visible document citations in final reply only when backed by current-turn Document RAG tool results.
- Produces: `ctx.outbound_metadata["doc_rag_citation"]` with validator summary.

- [ ] Add protocol text to `plugins/citation/plugin.py`.

```python
_DOC_RAG_CITATION_PROTOCOL = """### Document RAG 引用规则 - 对用户可见
当你使用 search_docs / fetch_doc_chunk 的结果回答文档问题时，关键结论后必须使用工具结果里的 citation 字段引用来源，格式为 [source_path > heading_path]。
如果 search_docs 返回 hit_count=0，不要编造文档引用；应说明当前文档知识库中没有检索到可引用证据。
如果 search_docs 的 snippet 不足以支撑回答，应继续调用 fetch_doc_chunk 展开 chunk，而不是直接改用 read_file。
不要把 recall_memory 的记忆引用协议用于 Document RAG。
"""
```

- [ ] Append this protocol in `CitationPromptModule.run` only when Document RAG is enabled.

Expected implementation shape:

```python
def _doc_rag_enabled_from_context(plugin: Plugin | None) -> bool:
    app_config = getattr(getattr(plugin, "context", None), "app_config", None)
    doc_rag = getattr(app_config, "doc_rag", None)
    return bool(getattr(doc_rag, "enabled", False))

ctx.system_sections_bottom.append(
    PromptSectionRender(
        name="doc_rag_citation_protocol",
        content=_DOC_RAG_CITATION_PROTOCOL,
        is_static=True,
    )
)
```

`CitationPromptModule` should receive the plugin instance:

```python
class CitationPromptModule:
    def __init__(self, plugin: "CitationPlugin") -> None:
        self._plugin = plugin

    async def run(self, frame: Any) -> Any:
        ctx = frame.slots.get(_PROMPT_CTX_SLOT)
        if not isinstance(ctx, PromptRenderCtx):
            return frame
        ctx.system_sections_bottom.append(
            PromptSectionRender(
                name="citation_protocol",
                content=_CITATION_PROTOCOL,
                is_static=True,
            )
        )
        if _doc_rag_enabled_from_context(self._plugin):
            ctx.system_sections_bottom.append(
                PromptSectionRender(
                    name="doc_rag_citation_protocol",
                    content=_DOC_RAG_CITATION_PROTOCOL,
                    is_static=True,
                )
            )
        return frame
```

Memory citation protocol remains always injected.

- [ ] Add helper to extract Document RAG citations from tool chain.

Expected behavior:

```python
extract_doc_rag_citations_from_tool_chain(tool_chain) -> list[str]
```

Extraction rules:

- Only inspect calls where `name` is `search_docs` or `fetch_doc_chunk`.
- Parse call `result` as JSON.
- For `search_docs`, read `hits[].citation`.
- For `fetch_doc_chunk`, read `chunk.citation`.
- If `citation` is missing, synthesize from `source_path` and `heading_path`.
- Deduplicate while preserving order.
- Ignore malformed JSON.
- Ignore `hit_count=0`.

- [ ] Add helper to extract visible document citation strings from replies.

Expected behavior:

```python
extract_visible_doc_citations(reply: str) -> list[str]
```

Pattern:

```text
\[[^\[\]\n]+?\.m(?:d|arkdown)\s+>\s+[^\[\]\n]+\]
```

Rules:

- Match user-facing citations such as `[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]`.
- Require the ` > ` separator so ordinary markdown references such as `[README.md]` are not treated as Document RAG citations.
- Do not remove document-looking text unless a Document RAG tool was called in the current turn.
- Do not match memory protocol such as `§cited:[abc123]§`.
- Deduplicate while preserving order.

- [ ] Add helper to check reply citation.

```python
def reply_has_doc_rag_citation(reply: str, citations: list[str]) -> bool:
    return any(citation and citation in reply for citation in citations)
```

- [ ] Add helper to detect no-evidence replies.

Expected behavior:

```python
def is_doc_rag_no_evidence_reply(reply: str) -> bool:
    lowered = reply.lower()
    markers = [
        "当前文档知识库中没有检索到",
        "当前文档知识库中没有",
        "文档知识库中没有找到",
        "没有足够的文档证据",
        "没有足够文档证据",
        "无法从文档知识库",
        "无法根据文档知识库",
        "no document evidence",
        "no evidence in the document knowledge base",
        "not found in the document",
    ]
    return any(marker in lowered for marker in markers)
```

False-positive rule:

- Do not treat replies such as `不是没有证据，而是证据显示 agent runtime 负责调度。` as no-evidence replies.
- Add a unit test for this exact false-positive case.

- [ ] Add helper to remove fake document citations.

Expected behavior:

```python
def remove_unknown_doc_citations(reply: str, allowed: list[str]) -> tuple[str, list[str]]:
    allowed_set = set(allowed)
    removed: list[str] = []
    cleaned = reply
    for citation in extract_visible_doc_citations(reply):
        if citation in allowed_set:
            continue
        removed.append(citation)
        cleaned = cleaned.replace(citation, "")
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([。！？,.!?；;：:])", r"\1", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.rstrip(), removed
```

Rules:

- Extract visible document citations from reply.
- Keep citations that are in `allowed`.
- Remove citations that are not in `allowed`.
- Return cleaned reply and removed fake citations.
- Clean extra whitespace left by removed citations.

- [ ] Add helper to append fallback references.

```python
def append_doc_rag_references(reply: str, citations: list[str], limit: int = 2) -> str:
    selected = [item for item in citations if item][:limit]
    if not selected:
        return reply
    if reply_has_doc_rag_citation(reply, selected):
        return reply
    return f"{reply.rstrip()}\n\n参考来源：{'；'.join(selected)}"
```

- [ ] Add validator function.

Expected behavior:

```python
def validate_doc_rag_citations(reply: str, tool_chain: list[dict[str, object]]) -> tuple[str, dict[str, object]]:
    doc_rag_tool_called = doc_rag_tool_was_called(tool_chain)
    allowed = extract_doc_rag_citations_from_tool_chain(tool_chain)
    cleaned, removed_fake = (
        remove_unknown_doc_citations(reply, allowed)
        if doc_rag_tool_called
        else (reply, [])
    )
    inserted = False
    skipped_no_evidence = bool(allowed and is_doc_rag_no_evidence_reply(cleaned))
    if allowed and not skipped_no_evidence:
        before = cleaned
        cleaned = append_doc_rag_references(cleaned, allowed)
        inserted = cleaned != before
    return cleaned, {
        "allowed_citations": allowed,
        "removed_fake_citations": removed_fake,
        "inserted_fallback": inserted,
        "skipped_no_evidence": skipped_no_evidence,
        "doc_rag_tool_called": doc_rag_tool_called,
    }
```

Important:

- `removed_fake_citations` must be metadata only; do not expose it to the user.
- If `allowed` is empty, remove unknown document-looking citations only when a Document RAG tool was called. This avoids deleting ordinary bracketed text in unrelated answers.
- Add `doc_rag_tool_was_called(tool_chain)` so this condition is explicit and testable.
- Unknown-citation removal should use the strict visible citation extractor above, not a broad `.md` bracket pattern.

- [ ] Add after-reasoning validator module.

Expected module:

```python
class DocRagCitationValidatorModule:
    slot = "citation.doc_rag_validator"
    requires = ("after_reasoning.build_ctx", _REASONING_CTX_SLOT)
    produces = (_REASONING_CTX_SLOT,)

    async def run(self, frame: Any) -> Any:
        ctx = frame.slots.get(_REASONING_CTX_SLOT)
        if ctx is None:
            return frame
        cleaned, summary = validate_doc_rag_citations(
            str(getattr(ctx, "reply", "") or ""),
            list(getattr(ctx, "tool_chain", ()) or ())
        )
        ctx.reply = cleaned
        if summary["allowed_citations"] or summary["removed_fake_citations"]:
            ctx.outbound_metadata["doc_rag_citation"] = summary
        return frame
```

- [ ] Register the new module in `CitationPlugin.after_reasoning_modules`.

Expected order:

```python
return [
    CitationAfterReasoningModule(),
    DocRagCitationValidatorModule(),
    ProtocolTagCleanupModule(),
]
```

Why this order:

- Memory citation cleanup remains first.
- Document RAG validator runs after memory citation cleanup, so it sees the user-facing reply.
- Document RAG references are visible and should remain in the final reply if valid.
- Protocol tag cleanup still runs last to remove internal memory tags.

- [ ] Update `plugins/citation/README.md`.

Add a section:

```text
Document RAG citation is user-facing and uses [source_path > heading_path].
Memory citation is internal and uses §cited:[id]§.
The plugin must keep these protocols separate.
Document RAG protocol is injected only when app_config.doc_rag.enabled is true.
The validator removes document-looking citations that were not returned by current-turn search_docs/fetch_doc_chunk.
```

Why this task:

- It provides deterministic citation insertion when the model forgets citation.
- It removes fabricated document citations before the user sees them.
- It only cites sources that appeared in current-turn tool results.

Risk:

- The fallback may append a general "参考来源" instead of placing citations after each exact claim.
- This is acceptable for v0, because P10 evaluation can still verify citation existence and source validity.
- Removing fake citations may leave a sentence without sentence-level citation; P10 should measure answer faithfulness separately.

Why not build a complex citation rewriter now:

- Rewriting sentence-level claims requires answer parsing and evidence alignment.
- That belongs after retrieval-only and e2e eval exists.

## Task 4: Unit Tests For Document RAG Citation Validator

**Files:**

- Create: `tests/test_doc_rag_citation_plugin.py`

**Interfaces:**

- Consumes: helpers from `plugins.citation.plugin`.
- Produces: regression tests for extraction, fake citation removal, fallback citation behavior, and no-evidence skip behavior.

- [ ] Test extracting citations from `search_docs`.

```python
def test_extract_doc_rag_citations_from_search_docs_tool_chain():
    tool_chain = [
        {
            "text": "",
            "calls": [
                {
                    "name": "search_docs",
                    "result": json.dumps(
                        {
                            "ok": True,
                            "hit_count": 1,
                            "hits": [
                                {
                                    "citation": "[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]",
                                    "source_path": "my_md/doc_rag_corpus/manual_test.md",
                                    "heading_path": "Agent Runtime",
                                }
                            ],
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
        }
    ]
    assert extract_doc_rag_citations_from_tool_chain(tool_chain) == [
        "[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]"
    ]
```

- [ ] Test extracting citations from `fetch_doc_chunk`.

```python
def test_extract_doc_rag_citations_from_fetch_doc_chunk_tool_chain():
    tool_chain = [
        {
            "text": "",
            "calls": [
                {
                    "name": "fetch_doc_chunk",
                    "result": json.dumps(
                        {
                            "ok": True,
                            "chunk": {
                                "citation": "[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]"
                            },
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
        }
    ]
    assert extract_doc_rag_citations_from_tool_chain(tool_chain) == [
        "[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]"
    ]
```

- [ ] Test no hits does not create citation.

```python
def test_extract_doc_rag_citations_ignores_no_hits():
    tool_chain = [
        {
            "calls": [
                {
                    "name": "search_docs",
                    "result": json.dumps({"ok": True, "hit_count": 0, "hits": []}),
                }
            ]
        }
    ]
    assert extract_doc_rag_citations_from_tool_chain(tool_chain) == []
```

- [ ] Test visible citation extraction ignores memory protocol.

```python
def test_extract_visible_doc_citations_ignores_memory_protocol():
    reply = (
        "答案。[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]\n"
        "§cited:[abc123]§"
    )
    assert extract_visible_doc_citations(reply) == [
        "[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]"
    ]
```

- [ ] Test visible citation extraction ignores ordinary markdown references.

```python
def test_extract_visible_doc_citations_ignores_plain_markdown_reference():
    reply = "请阅读 [README.md] 和 [notes.markdown]，这不是 Document RAG 引用。"
    assert extract_visible_doc_citations(reply) == []
```

- [ ] Test fallback appends source when missing.

```python
def test_append_doc_rag_references_when_reply_missing_citation():
    reply = "Agent runtime 负责管理 agent 的一次运行过程。"
    citations = ["[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]"]
    assert append_doc_rag_references(reply, citations) == (
        "Agent runtime 负责管理 agent 的一次运行过程。\n\n"
        "参考来源：[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]"
    )
```

- [ ] Test existing citation is not duplicated.

```python
def test_append_doc_rag_references_does_not_duplicate_existing_citation():
    reply = (
        "Agent runtime 负责管理 agent 的一次运行过程。"
        "[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]"
    )
    citations = ["[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]"]
    assert append_doc_rag_references(reply, citations) == reply
```

- [ ] Test fake citation is removed and real citation is appended.

```python
def test_validate_doc_rag_citations_removes_fake_and_appends_real():
    tool_chain = [
        {
            "calls": [
                {
                    "name": "search_docs",
                    "result": json.dumps(
                        {
                            "ok": True,
                            "hit_count": 1,
                            "hits": [
                                {
                                    "citation": "[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]"
                                }
                            ],
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        }
    ]
    reply, summary = validate_doc_rag_citations(
        "Agent runtime 负责调度。[fake.md > Fake]",
        tool_chain,
    )
    assert "[fake.md > Fake]" not in reply
    assert "[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]" in reply
    assert summary["removed_fake_citations"] == ["[fake.md > Fake]"]
    assert summary["inserted_fallback"] is True
```

- [ ] Test no-evidence reply does not append citation.

```python
def test_validate_doc_rag_citations_skips_no_evidence_reply():
    tool_chain = [
        {
            "calls": [
                {
                    "name": "search_docs",
                    "result": json.dumps(
                        {
                            "ok": True,
                            "hit_count": 1,
                            "hits": [
                                {
                                    "citation": "[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]"
                                }
                            ],
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        }
    ]
    reply, summary = validate_doc_rag_citations(
        "当前文档知识库中没有足够证据回答这个问题。",
        tool_chain,
    )
    assert "[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]" not in reply
    assert summary["skipped_no_evidence"] is True
```

- [ ] Test no-evidence detection does not skip positive evidence replies.

```python
def test_validate_doc_rag_citations_does_not_skip_positive_evidence_reply():
    tool_chain = [
        {
            "calls": [
                {
                    "name": "search_docs",
                    "result": json.dumps(
                        {
                            "ok": True,
                            "hit_count": 1,
                            "hits": [
                                {
                                    "citation": "[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]"
                                }
                            ],
                        },
                        ensure_ascii=False,
                    ),
                }
            ]
        }
    ]
    reply, summary = validate_doc_rag_citations(
        "不是没有证据，而是证据显示 agent runtime 负责调度。",
        tool_chain,
    )
    assert "[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]" in reply
    assert summary["skipped_no_evidence"] is False
    assert summary["inserted_fallback"] is True
```

- [ ] Test unrelated replies are not modified when no Document RAG tool was called.

```python
def test_validate_doc_rag_citations_ignores_reply_without_doc_rag_tool_call():
    reply = "请阅读 [notes.md > local draft]，这是用户自己写的普通文本。"
    cleaned, summary = validate_doc_rag_citations(reply, tool_chain=[])
    assert cleaned == reply
    assert summary["doc_rag_tool_called"] is False
    assert summary["removed_fake_citations"] == []
```

- [ ] Test ordinary markdown references are not removed even when Document RAG tool was called.

```python
def test_validate_doc_rag_citations_keeps_plain_markdown_reference():
    tool_chain = [
        {
            "calls": [
                {
                    "name": "search_docs",
                    "result": json.dumps({"ok": True, "hit_count": 0, "hits": []}),
                }
            ]
        }
    ]
    reply = "用户提到 [README.md]，这只是普通 markdown 文件名。"
    cleaned, summary = validate_doc_rag_citations(reply, tool_chain=tool_chain)
    assert cleaned == reply
    assert summary["doc_rag_tool_called"] is True
    assert summary["removed_fake_citations"] == []
```

- [ ] Test prompt protocol is injected only when Document RAG is enabled.

Use a minimal frame with `PromptRenderCtx` and a `CitationPlugin` whose `context.app_config.doc_rag.enabled` is true/false.

Expected:

```python
assert "doc_rag_citation_protocol" not in section_names_when_disabled
assert "doc_rag_citation_protocol" in section_names_when_enabled
```

- [ ] Run tests.

```bash
uv run --with pytest pytest tests/test_doc_rag_citation_plugin.py -v
```

Expected:

```text
all selected Document RAG citation plugin tests pass
```

## Task 5: Manual CLI Smoke Test

**Files:**

- No source file changes expected.
- Update: `my_md/rag/11-document-rag-implementation-plan.md`
- Update: `my_md/rag/18-document-rag-p9-citation-plan.md`

**Interfaces:**

- Consumes: running Agent with `doc_rag.enabled=true`.
- Produces: observed CLI behavior and trace id.

- [ ] Rebuild index.

```bash
uv run python -m scripts.doc_rag_index_check --rebuild
```

Expected:

```text
status: succeeded
docs_indexed: 2
chunks_created: 11
embedding_failed: 0
```

- [ ] Start Agent with temporary config.

Use a temporary copy of `config.toml`, append:

```toml
[channels]
socket = "/tmp/akashic-doc-rag-p9-smoke.sock"

[doc_rag]
enabled = true
source_root = "."
store_path = "~/.akashic/workspace/doc_rag/doc_rag.db"
collection_id = "default"
```

Run:

```bash
uv run python main.py --config /tmp/akashic-doc-rag-p9-smoke.toml --port 2237
```

- [ ] Send IPC question.

```text
请从文档知识库中检索 agent runtime 负责什么？如果需要展开证据，请优先使用 fetch_doc_chunk，回答必须带文档引用。
```

- [ ] Expected result.

Tool path should be one of:

```text
tool_search -> search_docs -> answer with citation
tool_search -> search_docs -> fetch_doc_chunk -> answer with citation
```

Final answer must contain:

```text
[my_md/doc_rag_corpus/manual_test.md > Agent Runtime]
```

It should not use `recall_memory`.

- [ ] Check trace.

```bash
tail -n 3 ~/.akashic/workspace/doc_rag/retrieval_traces.jsonl
```

Expected:

```text
query contains "agent runtime"
hit_count: 5
top1 source_path: my_md/doc_rag_corpus/manual_test.md
top1 heading_path: Agent Runtime
```

- [ ] Clean temporary config and socket.

```bash
rm -f /tmp/akashic-doc-rag-p9-smoke.toml /tmp/akashic-doc-rag-p9-smoke.sock
```

## Task 6: Verification Matrix

Run:

```bash
uv run --with pytest pytest \
  tests/test_plugin_manager.py \
  tests/test_doc_rag_tools.py \
  tests/test_doc_rag_toolset.py \
  tests/test_doc_rag_citation_plugin.py \
  -v
```

Run broader Doc RAG regression:

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
  tests/test_doc_rag_citation_plugin.py \
  tests/test_plugin_manager.py \
  -v
```

Run existing regression:

```bash
uv run --with pytest pytest \
  tests/test_memory2_retrieval_baseline.py \
  tests/test_tool_discovery_routing.py \
  -v
```

Run formatting and syntax:

```bash
uv run --with black black --check \
  doc_rag \
  agent/tools/doc_rag.py \
  bootstrap/toolsets/doc_rag.py \
  plugins/citation/plugin.py \
  tests/test_plugin_manager.py \
  tests/test_doc_rag_*.py

python3 -m compileall -q doc_rag agent/tools bootstrap/toolsets plugins/citation
```

Expected:

- All tests pass.
- No new lint or syntax errors.
- Existing memory citation behavior remains unchanged.

## Acceptance Criteria

| Requirement | Acceptance |
| --- | --- |
| `search_docs` citation | Every hit includes `citation` |
| `fetch_doc_chunk` citation | Chunk output includes `citation` |
| Plugin app config | `PluginContext.app_config` receives global `Config` |
| Conditional prompt rule | System prompt includes Document RAG visible citation rule only when `doc_rag.enabled=true` |
| Memory boundary | Memory citation protocol remains internal and unchanged |
| Missing citation validator | If Document RAG evidence was used and reply lacks citation, final reply gets real tool-derived references |
| Fake citation validator | Document-looking citations not returned by current-turn tools are removed before user output |
| No-evidence behavior | No citation is generated when `search_docs` returns no hits or final answer is a no-evidence reply |
| Tool path guidance | Tool descriptions say to use `fetch_doc_chunk` before `read_file` for chunk expansion |
| CLI smoke | Document question answer contains `[source_path > heading_path]` |
| No AgentLoop change | No changes under `agent/looping/*` |

## Out Of Scope

- Sentence-level citation alignment.
- Complex footnote numbering.
- Web UI citation rendering.
- Hybrid search.
- Rerank.
- Query rewrite.
- LLM judge for citation faithfulness.
- GraphRAG or LLM Wiki.

These start after P9 and P10 establish a measurable citation baseline.

## Follow-Up After P9

P10 should build evaluation around these failure reasons:

```text
retrieval_miss
ranking_bad
tool_misuse
fetch_missing
citation_missing
citation_fake
answer_unfaithful
no_evidence_failed
```

P9 is successful when citation existence and citation validity become mechanically checkable. P10 then measures whether the cited answer is actually faithful to the cited evidence.

## Implementation Result 2026-07-10

Status: implemented and automatically verified.

Completed:

- Added `PluginContext.app_config` and passed global `Config` from runtime bootstrap into `PluginManager`.
- Added `citation` to `search_docs` hits and `fetch_doc_chunk` chunk output.
- Strengthened Document RAG tool descriptions and search hints so `fetch_doc_chunk` is discoverable as the preferred evidence expansion tool.
- Added conditional Document RAG citation prompt injection in `plugins/citation`, only when `app_config.doc_rag.enabled=true`.
- Added Document RAG citation validator in `plugins/citation`:
  - extracts allowed citations from current-turn `search_docs` / `fetch_doc_chunk`;
  - removes unknown visible document citations;
  - appends real fallback references when evidence was used but citation is missing;
  - skips citation insertion for no-hit or explicit no-evidence replies;
  - writes summary metadata to `outbound_metadata["doc_rag_citation"]`.
- Preserved memory citation behavior and kept `§cited:[id]§` separate from visible Document RAG citation.

Verification:

```bash
uv run --with pytest --with pytest-asyncio pytest \
  tests/test_plugin_manager.py \
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
  tests/test_doc_rag_citation_plugin.py \
  tests/test_citation_plugin.py \
  tests/test_memory2_retrieval_baseline.py \
  tests/test_tool_discovery_routing.py -q
```

Result:

```text
135 passed
```

Additional checks:

```bash
uv run --with black black --check doc_rag agent/plugins/context.py agent/plugins/manager.py agent/tools/doc_rag.py bootstrap/tools.py bootstrap/toolsets/doc_rag.py plugins/citation/plugin.py tests/test_plugin_manager.py tests/test_doc_rag_*.py
python3 -m compileall -q doc_rag agent/tools agent/plugins bootstrap/toolsets plugins/citation tests/test_doc_rag_citation_plugin.py tests/test_doc_rag_tools.py tests/test_doc_rag_toolset.py tests/test_plugin_manager.py
```

Result:

- Black check passed.
- Compileall passed.

Not yet done:

- Real CLI/LLM smoke test was not run in this implementation pass. It still needs a running Agent with `doc_rag.enabled=true` and an IPC/CLI question to confirm live model behavior.
