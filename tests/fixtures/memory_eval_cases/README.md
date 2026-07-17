# Memory Eval Cases

These fixtures define offline memory experiment eval cases. They do not run the
agent, call an LLM, call embeddings, or mutate a real memory database.

Phase6 runners should use the same case payload under multiple config profiles:

- `off`: experiment framework disabled.
- `phase1`: write-value shadow baseline.
- `phase2`: graph / retrieval shadow profile.
- `phase3`: rerank and injection-governance shadow profile.
- `phase4`: version-chain and provenance shadow profile.
- `phase5`: sleep-consolidation shadow profile.
- `all`: all implemented shadow features enabled together.

`phase_targets` describe what a case is meant to evaluate, such as `phase2a` or
`phase4b`. `config_profiles` describe which runtime profiles a later runner
should compare. Keep those two fields distinct.

The first fixture pack covers:

- `preference_recall`
- `temporary_memory_pollution`
- `duplicate_memory`
- `conflict_memory`
- `vague_reference_graph`
- `injection_governance_budget`
- `cross_scope_isolation`
- `stale_memory_sleep`
- `provenance_trace`

The fixture pack captures what each phase should make observable through
`memory_experiments` traces. It is a schema and data contract for future eval
runners, not the runner itself.
