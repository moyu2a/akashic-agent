# System Path Failure Attribution

本报告只包含脱敏 case id、repeat id、pass/fail 和 heuristic failure bucket；不包含原始问题、提示词、记忆正文或完整回答。

## Method

- input report: `system_path_safe_version_eval.json`
- baseline mode: `current`
- candidate mode: `safe_version_replace`
- matrix scope: `40` unique cases x `3` repeats
- paired_run_count: `120`
- unpaired_run_count: `0`
- bucket semantics: sanitized heuristic

Attribution uses already-sanitized scoring fields from the system-path report, including pass/fail booleans, forbidden counts, grounding result, answer length, expected-term miss counts, any-group miss counts, and language pass. It does not inspect raw answers.

## Movement

| movement | count | meaning |
| --- | ---: | --- |
| baseline_failed_candidate_passed | 64 | replace rescued current failure |
| baseline_passed_candidate_failed | 7 | replace regressed current pass |
| baseline_passed_candidate_passed | 24 | both passed |
| baseline_failed_candidate_failed | 25 | both failed |

## Candidate Buckets

- paired_run_count: `120`
- unpaired_run_count: `0`
- failure_bucket_semantics: `sanitized_heuristic`

| bucket | count |
| --- | ---: |
| answer_rule_miss_any_group | 13 |
| answer_rule_miss_required_terms | 16 |
| language_failure | 3 |
| passed | 88 |

## Conclusion

`safe_version_replace` passed `88/120 = 73.3333%` paired runs. The remaining miss surface is concentrated in answer-rule misses:

- `answer_rule_miss_required_terms = 16`
- `answer_rule_miss_any_group = 13`
- `language_failure = 3`

This supports the conclusion that the next bottleneck is evidence-to-answer expression, not recall or forbidden governance. P6o-16 should target model-visible system-path answer guidance while keeping grounding `100.0%`, forbidden `0.0%`, contract success `100.0%`, and bounded tokens.
