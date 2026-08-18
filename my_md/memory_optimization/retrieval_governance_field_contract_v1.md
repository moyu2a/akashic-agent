# Retrieval Governance Field Contract v1

## 1. Goal

This document defines the production-facing field contract for the memory
retrieval governance path:

```text
user question
  -> retrieval_plan
  -> lane retrieval
  -> RRF fusion
  -> candidate_governance
  -> structured_evidence
  -> prompt evidence block
  -> LLM answer
```

The responsibility split is:

| Stage | Responsibility |
| --- | --- |
| `retrieval_plan` | Decide how this query should retrieve memory. |
| `lane retrieval` | Let each lane find candidates with its own method. |
| `RRF fusion` | Merge lane candidates into one ranked list. |
| `candidate_governance` | Decide whether candidates are allowed, uncertain, or dropped. |
| `structured_evidence` | Render allowed candidates into a stable evidence contract. |
| `prompt` | Give the model only the evidence it is allowed to use. |

## 2. Retrieval Plan

`retrieval_plan` is the single plan object for one retrieval request. It combines
request boundaries and routing strategy so downstream stages do not need to
consult two separate objects.

| Field | Required | Purpose |
| --- | --- | --- |
| `query` | Yes | Original user question. |
| `scope_channel` | Yes | Current channel boundary for cross-channel isolation. |
| `scope_chat_id` | Yes | Current chat/session boundary for cross-session isolation. |
| `memory_types` | Recommended | Restricts retrieval to memory types such as `event`, `preference`, `profile`, or `procedure`. |
| `top_k` | Yes | Final fused candidate limit. |
| `aux_queries` | Optional | Auxiliary semantic queries used by semantic retrieval only. |
| `time_window` | Optional | Optional `time_start` and `time_end` filters. |
| `score_threshold` | Recommended | Applies only inside semantic lane to filter low-scoring embedding results. It does not apply to keyword, provenance, or graph lanes, and it is not a global post-RRF threshold. |
| `scene` | Yes | Query scene such as `source_lookup`, `partial_conflict`, `exact_recall`, or `fuzzy_reference`. |
| `allowed_lanes` | Yes | Lanes enabled for this request. |
| `max_per_lane` | Yes | Per-lane candidate cap before RRF. |
| `require_source_ref` | Yes | Whether candidates must have a source reference. |
| `require_scope_match` | Yes | Whether candidates must match current scope. |
| `drop_low_confidence` | Yes | Whether low-confidence candidates should be filtered. |
| `candidate_governance` | Yes | Decision-table policy for candidate governance. |
| `reason` | Recommended | Human-readable reason for the plan. |

## 3. Candidate Governance Policy

`candidate_governance` is a decision-table policy, not an opaque string or loose
boolean. The implementation should execute the table and keep strategy out of
scattered if/else blocks.

| Field | Purpose |
| --- | --- |
| `mode` | Governance mode, currently `strict` or `tiered`. |
| `drop_rules` | Risk labels that must be dropped, such as `superseded_candidate`, `scope_mismatch`, and `forbidden_candidate`. |
| `downgrade_rules` | Risk labels retained as downgraded evidence, such as `low_confidence` and `weak_source_ref`. |
| `review_rules` | Risk labels retained only as uncertain/review evidence, such as `conflict_candidate`, `missing_source_ref`, and `insufficient_evidence`. |
| `allow_threshold` | Optional minimum post-RRF rank boundary. Candidates with worse fused rank can be dropped. |
| `protected_ids` | Eval/debug-only candidate ids protected from non-fatal filters. |
| `eval_mode` | Whether eval-only policy fields may affect routing. |

`protected_ids` only works in evaluation mode, for example under
`--enable-eval-mode`. In production, `protected_ids` must be empty in effect and
every candidate must pass the same governance path as all other candidates.

The production `Retriever` defaults to `enabled=true, mode=tiered`. The
standalone `build_retrieval_routing_decision()` compatibility wrapper keeps
candidate governance disabled because it represents lane routing only; callers
that execute a retrieval request must apply governance after RRF through
`apply_candidate_governance()`.

## 4. Lane Output Contract

Each lane may retrieve differently, but each lane should output a compatible
candidate shape.

| Field | Required | Purpose |
| --- | --- | --- |
| `id` | Yes | Memory item id. |
| `text` or `summary` | Yes | Candidate memory text. |
| `status` | Yes | `active`, `superseded`, or `expired`. |
| `scope` | Yes | Candidate scope, derived from channel/chat/user scope. |
| `source_ref` | Recommended | Source pointer for audit and provenance. |
| `confidence` | Recommended | Confidence used by downgrade governance. |
| `memory_type` | Recommended | Memory type. |
| `lane_name` | Yes | Candidate lane name. |
| `score` | Lane-specific | Lane-local ranking score. |
| `scope_match` | Recommended | Whether the candidate matches current request scope. |

### Semantic lane

Semantic lane uses embedding similarity and may use `aux_queries`. The
`score_threshold` field only applies here.

### Keyword lane

Keyword lane uses literal query terms and should not use semantic expansion.

### Provenance lane

Provenance lane only performs exact or structured metadata retrieval based on
fields such as `source_ref`, `session_id`, `speaker`, `scope_channel`,
`scope_chat_id`, `turn_index`, `message_id`, and time position. It must not use
embedding similarity or semantic query expansion. If a provenance path requires
embedding retrieval, it should be merged into semantic lane instead of remaining
a separate lane.

### Graph lane

Graph lane is optional and should only represent relation traversal, such as
`supersedes`, `conflicts`, or `duplicates`. Pure semantic similarity does not
belong in graph lane.

## 5. RRF Fusion Contract

RRF merges lane candidates into one ranked candidate list. RRF ranks; it does
not perform candidate governance.

Each fused candidate must retain:

| Field | Required | Purpose |
| --- | --- | --- |
| `id` | Yes | Evidence id. |
| `text` | Yes | Evidence text eventually rendered to the model. |
| `status` | Yes | Active/stale boundary. |
| `scope` | Yes | Cross-scope boundary. |
| `confidence` | Recommended | Downgrade signal. |
| `source_ref` | Recommended | Source and audit signal. |
| `relations` | Recommended | `supersedes`, `conflicts`, or `duplicates` metadata. |
| `retrieval` | Yes | Lane and RRF observability. |

`retrieval` should include:

| Field | Purpose |
| --- | --- |
| `fused_rank` | Final 1-based RRF rank. |
| `rrf_score` | Final RRF score. |
| `lane_hits` | Lanes that retrieved this candidate. |
| `lane_ranks` | Candidate rank inside each lane. |
| `lane_scores` | Candidate score inside each lane. |
| `lane_submitted_counts` | Number of candidates each lane submitted to RRF. |

Future test summaries must record lane submitted counts, target rank in each
lane, and final RRF rank.

## 6. Candidate Governance Contract

Candidate governance classifies fused candidates into three output groups:

| Output | Purpose |
| --- | --- |
| `allowed_candidates` | Candidates allowed to become answer evidence. |
| `uncertain_candidates` | Candidates retained for audit/review context but not strong answer evidence. |
| `dropped_candidates` | Candidates removed from evidence and prompt. |

`requires_review` candidates are not returned in `allowed_candidates`; they are
recorded in the trace and mapped to `uncertain_evidence_ids` for audit only.

Risk labels include:

| Risk | Meaning |
| --- | --- |
| `forbidden_candidate` | Candidate is explicitly forbidden. |
| `superseded_candidate` | Candidate was replaced by a newer version. |
| `expired_candidate` | Candidate is expired. |
| `scope_mismatch` | Candidate crosses the current scope boundary. |
| `conflict_candidate` | Candidate conflicts with other evidence. |
| `duplicate_candidate` | Candidate duplicates another candidate. |
| `missing_source_ref` | Candidate lacks source reference. |
| `weak_source_ref` | Candidate source is weak. |
| `low_confidence` | Candidate confidence is low. |
| `insufficient_evidence` | Candidate says evidence is insufficient or incomplete. |
| `low_rrf_rank` | Candidate is below the configured rank threshold. |

Default action mapping:

| Action | Meaning |
| --- | --- |
| `delete` | Candidate does not enter structured evidence. |
| `requires_review` | Candidate maps to uncertain evidence only. |
| `downgrade` | Candidate can remain allowed but with lower priority. |
| `allow` | Candidate can become allowed evidence. |

## 7. Structured Evidence Contract

Structured evidence maps governance output into the model-facing evidence
contract:

| Field | Purpose |
| --- | --- |
| `allowed_evidence_ids` | IDs allowed in prompt evidence. |
| `allowed_evidence` | Allowed evidence content. |
| `uncertain_evidence_ids` | IDs of `uncertain_candidates`; audit/report only. |
| `stale_warning_ids` | Superseded/expired ids. |
| `conflict_warning_ids` | Conflict ids. |
| `downgrade_ids` | Downgraded ids. |
| `requires_review_ids` | Review-only ids. |
| `forbidden_boundary_ids` | IDs that must not be used. |
| `insufficient_evidence` | Whether allowed evidence is missing or insufficient. |
| `evidence_summaries` | Rendered summaries for allowed evidence only. |
| `evidence_render_metadata` | Rendering, truncation, and length metadata. |

Mapping rule: candidate governance outputs `uncertain_candidates`; structured
evidence maps that list to `uncertain_evidence_ids`. `evidence_summaries` must
contain only `allowed_evidence`, never `uncertain_evidence` content.

## 8. Prompt Contract

The prompt may use allowed evidence as the only answer source.

If `allowed_evidence_ids` is empty and `insufficient_evidence=true`, the model
must answer that the available memory cannot confirm the answer. Any uncertain
content is audit-only and must not be used as an answer source.

If allowed evidence is non-empty, the model must answer from allowed evidence
first. Uncertain evidence may be treated only as background and the answer must
not introduce facts that appear only in uncertain evidence.

Debug-only fields such as `dropped_by_reason`, raw scores, protected ids, and
render metadata should stay in trace/report output rather than direct prompt
text.
