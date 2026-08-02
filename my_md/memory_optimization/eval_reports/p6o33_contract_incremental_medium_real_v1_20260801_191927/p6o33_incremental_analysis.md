# P6o33 Contract Incremental Medium Real Eval

## Method

- A: `safe_version_replace` = Evidence Contract.
- B: `safe_version_replace_guided` = A + Answer Guidance.
- C: `safe_version_replace_guided_with_retry_shadow` = B + Answer Candidate Contract.
- retry shadow 不是真实 retry；本实验不执行第二次 LLM 调用。

## Results

| mode | cases | answer_success | answer_rate | grounding_rate | forbidden_rate | candidate_contract | would_retry | retry_reasons | avg_tokens | avg_latency_ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| safe_version_replace | 80 | 71 | 88.75 | 100.0 | 0.0 | 0.0 | 4 | `{"dsml_tool_markup_in_final_answer": 3, "meta_action_final_answer": 2, "tool_markup_in_final_answer": 4}` | 5795.475 | 5789.9625 |
| safe_version_replace_guided | 80 | 74 | 92.5 | 100.0 | 0.0 | 0.0 | 3 | `{"dsml_tool_markup_in_final_answer": 3, "tool_markup_in_final_answer": 3}` | 5823.475 | 5352.9625 |
| safe_version_replace_guided_with_retry_shadow | 80 | 80 | 100.0 | 100.0 | 0.0 | 100.0 | 0 | `{}` | 6040.1625 | 4703.575 |

## Incremental Effect

- A -> B answer delta: `3.75` pp.
- B -> C answer delta: `7.5` pp.
- B -> C paired: `{"losses": 0, "paired_cases": 80, "ties": 74, "wins": 6}`.
- target_reached: `true`.
- gate_passed: `true`.

## Failure Reasons

```json
{
  "safe_version_replace": {
    "answer_language_not_chinese": 1,
    "missing_expected_answer_term": 5,
    "missing_expected_answer_term_group": 6
  },
  "safe_version_replace_guided": {
    "missing_expected_answer_term": 3,
    "missing_expected_answer_term_group": 4
  },
  "safe_version_replace_guided_with_retry_shadow": {}
}
```
