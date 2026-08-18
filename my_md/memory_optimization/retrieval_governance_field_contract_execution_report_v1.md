# Retrieval Governance Field Contract v1 Execution Report

## Summary

This branch implemented the retrieval governance field contract across
retrieval planning, candidate governance, RRF observability, structured
evidence rendering, and prompt contract behavior.

Implemented changes:

- `score_threshold` now remains semantic-lane-only in the documented contract.
- `retrieval_plan` is now a real runtime object and appears in retriever trace.
- The main `Retriever.retrieve_with_trace()` path now performs lane routing,
  RRF fusion, and candidate governance in that order.
- `candidate_governance` now has explicit decision-table fields.
- `protected_ids` are eval-only in effect.
- `uncertain_candidates` are mapped to `uncertain_evidence_ids`.
- RRF fused candidates now retain a `retrieval` metadata block.
- Provenance lane is constrained to structured metadata-based recall.

## Code Changes

- `memory2/retrieval_governance.py`
  - Added decision-table fields to `CandidateGovernancePolicy`.
  - Kept legacy compatibility with `drop_risks` / `protected_expected_ids`.
  - Eval-only protected ids now require `eval_mode=True`.
  - Governance traces now expose allowed, uncertain, and dropped candidate groups.
  - Added post-RRF `apply_candidate_governance()`.

- `memory2/retriever.py`
  - `retrieve_with_trace()` now builds and records `retrieval_plan`.
  - Candidate governance is applied after `fused_items` are produced.
  - RRF fused candidates now carry `retrieval.fused_rank`, `retrieval.rrf_score`,
    `retrieval.lane_hits`, `retrieval.lane_ranks`, `retrieval.lane_scores`, and
    `retrieval.lane_submitted_counts`.
  - Provenance lane was narrowed to structured metadata based routing.

- `memory2/retrieval_experiments.py`
  - RRF experiment helper now emits the same retrieval metadata block.

- `memory2/eval_answer_contract.py`
  - Added `ProductionEvidenceContract.uncertain_evidence_ids`.
  - Prompt contract now forbids using uncertain evidence as an answer source.

- `memory2/eval_comprehensive_online.py`
  - Raw eval payload now records `uncertain_evidence_ids`.
  - Eval-only candidate governance calls now explicitly set `eval_mode=True`.

- `memory2/eval_tri_candidate_governance.py`
  - Eval-only protected governance calls now explicitly set `eval_mode=True`.

## Tests

Passed:

- `tests/test_retrieval_governance_field_contract.py`
- `tests/test_memory_retrieval_governance.py`
- `tests/test_memory_answer_contract.py`

Run commands used:

```bash
/home/jjh/git_work/akashic-agent/.venv/bin/python -m pytest tests/test_retrieval_governance_field_contract.py -q -p no:cacheprovider
/home/jjh/git_work/akashic-agent/.venv/bin/python -m pytest tests/test_memory_retrieval_governance.py -q -p no:cacheprovider
/home/jjh/git_work/akashic-agent/.venv/bin/python -m pytest tests/test_memory_answer_contract.py -q -p no:cacheprovider
```

## Notes

- `uv run` was blocked in this environment by a snap-confine permission issue,
  so verification used the repo virtualenv directly.
- `git diff --check` still reports trailing whitespace in the pre-existing
  uncommitted `my_md/interview/08补充.md` file; this was not modified here.
