# LongMemEval Phase B Full 外部 LLM Judge 审查说明

## 审查输入

- PASS 包：`phase_b_full_passed_case_human_review_zh.md`
- FAIL 包：`phase_b_full_failed_case_human_review_zh.md`
- 索引：`phase_b_full_case_review_index.json`
- 原始报告：`public_long_memory_eval.json`

`strict_public_score.passed` 只用于拆包，不代表最终 correctness。

## Judge 口径

- `language_mismatch_only`：英文问题中文或中英混杂回答，但事实内容正确；不计 factual/preference error。
- `gold_questionable`：gold 或 case 本身边界明显；从 adjusted 分母剔除。
- `true_error`：事实答案错误、时间推理错误、证据足够却拒答、最终立场与 gold 相反。
- `partial_preference_miss`：偏好题抓住部分上下文，但遗漏 gold 中关键个性化依据；按保守 adjusted 口径计错。
- `scorer_false_positive`：strict PASS 但 Judge 判错。
- `scorer_false_negative`：strict FAIL 但 Judge 判对。
- `true_correct`：事实/推理/偏好核心正确。

## 输出 JSON Schema

```json
{
  "dataset": "longmemeval_phase_b_full_p5_oracle_v1",
  "case_count": 500,
  "results": [
    {
      "case_id": "string",
      "category": "string",
      "strict_passed": true,
      "judge_label": "true_correct | true_error | partial_preference_miss | gold_questionable | language_mismatch_only | scorer_false_positive | scorer_false_negative",
      "counts_as_adjusted_error": false,
      "excluded_from_adjusted_denominator": false,
      "language_issue_only": false,
      "reason_zh": "一句到三句中文理由",
      "required_evidence_summary_zh": "关键证据摘要",
      "model_answer_summary_zh": "模型答案摘要"
    }
  ],
  "summary": {
    "effective_denominator": 0,
    "adjusted_error_count": 0,
    "adjusted_pass_count": 0,
    "gold_questionable_count": 0,
    "language_mismatch_only_count": 0,
    "scorer_false_positive_count": 0,
    "scorer_false_negative_count": 0
  }
}
```

## adjusted 统计规则

- `excluded_from_adjusted_denominator=true` 的 case 不进入分母。
- `true_error` 和 `partial_preference_miss` 计入 adjusted error。
- `language_mismatch_only` 不计 adjusted error。
- `scorer_false_positive` 如果事实错误，计入 adjusted error。
- `scorer_false_negative` 如果事实正确，不计 adjusted error。
