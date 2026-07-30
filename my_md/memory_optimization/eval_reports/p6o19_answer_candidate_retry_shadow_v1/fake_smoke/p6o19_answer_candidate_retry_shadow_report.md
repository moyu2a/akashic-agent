# P6o-19 Answer Candidate Retry Shadow

## Method

- Modes: `safe_version_replace`, `safe_version_replace_guided`, `safe_version_replace_guided_with_retry_shadow`.
- P6o-19 is eval-only shadow telemetry: it does not execute a real retry and does not change production defaults.
- Reported answer-candidate fields are sanitized counts and reason labels only.

## Infra

- case_count: `12`.
- unique_case_count: `4`.
- mode_count: `3`.
- repeat_count: `1`.
- provider_error_count: `0`.
- timeout_count: `0`.
- checkpoint_input_count: `0`.
- malformed_checkpoint_line_count: `0`.
- real_llm_enabled: `false`.
- fake_provider_enabled: `true`.

## Results

| mode | cases | answer_success | answer_rate | grounding_rate | forbidden_rate | candidate_contract | would_retry | retry_reasons | avg_tokens | avg_latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| `safe_version_replace` | 4 | 0 | 0.0 | 100.0 | 0.0 | 0.0 | 0 | `{}` | 30.0 | 46.25 |
| `safe_version_replace_guided` | 4 | 0 | 0.0 | 100.0 | 0.0 | 0.0 | 0 | `{}` | 30.0 | 43.0 |
| `safe_version_replace_guided_with_retry_shadow` | 4 | 0 | 0.0 | 100.0 | 0.0 | 100.0 | 4 | `{"answer_choice_group_missing": 4, "required_terms_missing": 4}` | 30.0 | 47.5 |

## Gate

- guided_answer_rate: `0.0`.
- retry_shadow_answer_rate: `0.0`.
- answer_delta_vs_guided: `0.0`.
- retry_shadow_would_retry_count: `4`.
- retry_shadow_reason_counts: `{"answer_choice_group_missing": 4, "required_terms_missing": 4}`.
- gate_passed: `false`.

## Conclusion

P6o-19 did not pass the quality gate: retry-shadow did not exceed guided in this report. Fake-provider runs should be interpreted as wiring and privacy checks only.
