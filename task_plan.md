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
