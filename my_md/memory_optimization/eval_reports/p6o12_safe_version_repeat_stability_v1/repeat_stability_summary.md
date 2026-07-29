# P6o-12 Safe Version Repeat Stability Summary

This report is a repeat-stability analysis over an existing real LLM eval output. It does not add profiles, does not enable graph/all-on, and does not change production behavior.

## Matrix

- `case_count`: `240`
- `unique_case_count`: `40`
- `profile_count`: `2`
- `prompt_variant_count`: `1`
- `repeat_count`: `3`
- `provider_error_count`: `0`
- `timeout_count`: `0`

## Profile Totals

| profile | cases | answer | grounding | forbidden | avg tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| chain_tri_governed_answer_contract | 120 | 119/120 = 99.1667% | 100.0% | 0.0% | 6122.6917 |
| chain_tri_version_governed_answer_contract | 120 | 117/120 = 97.5% | 100.0% | 0.0% | 6030.3833 |

## Per-Repeat Answer Counts

| profile | repeat | answer | grounding | forbidden | avg tokens |
| --- | ---: | ---: | ---: | ---: | ---: |
| chain_tri_governed_answer_contract | 0 | 40/40 | 40/40 | 0/40 | 6118.55 |
| chain_tri_governed_answer_contract | 1 | 39/40 | 40/40 | 0/40 | 6161.825 |
| chain_tri_governed_answer_contract | 2 | 40/40 | 40/40 | 0/40 | 6087.7 |
| chain_tri_version_governed_answer_contract | 0 | 39/40 | 40/40 | 0/40 | 5990.875 |
| chain_tri_version_governed_answer_contract | 1 | 39/40 | 40/40 | 0/40 | 6097.675 |
| chain_tri_version_governed_answer_contract | 2 | 39/40 | 40/40 | 0/40 | 6002.6 |

## Post-Check Shadow

| profile | needs_retry | forbidden_boundary_included | missing_likely_relevant_context | stale_evidence_included | conflict_evidence_included |
| --- | ---: | ---: | ---: | ---: | ---: |
| chain_tri_governed_answer_contract | 0 | 0 | 0 | 0 | 0 |
| chain_tri_version_governed_answer_contract | 0 | 0 | 0 | 0 | 0 |

## Conclusion

- Safe version-governed stability gate: `passed`.
- Token delta vs governed baseline: `-92.3084` avg tokens.
- P6o-10 `40/40` should not be treated as a fixed 100% guarantee; this repeat run supports a stable `39/40` to `40/40` band on the current 40-case slice.
- If passed, next step is targeted hard-slice validation before any routed graph design.
- If failed, next step is failure/sensitivity analysis on the unstable repeats before expanding the matrix.
