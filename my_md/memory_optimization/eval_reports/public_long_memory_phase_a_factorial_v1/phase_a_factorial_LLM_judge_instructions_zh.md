# Phase A Factorial 外部 LLM Judge 指令

目标：对 `phase_a_factorial_case_reviews.jsonl` 中 400 条调用结果进行语义正确性判定，并按 profile 汇总 adjusted pass rate。

判定口径：
- 输入字段：`question`、`gold_answer`、`model_answer`、`category`、`profile`、`failure_attribution`、`rendered_evidence_snippet`。
- PASS：模型回答与 gold 在语义上等价，或 abstention 类问题表达了“信息不足/没有记录/不能确定”的同等含义。
- FAIL：模型给出与 gold 冲突的事实、选择了错误版本/当前状态、漏掉必要多证据聚合、或回答无关。
- LANGUAGE_ONLY：仅因英文问题使用中文框架但事实语义正确；本轮不计为真实错误，但需要记录。
- GOLD_QUESTIONABLE：gold 本身边界过窄或人工看起来可疑；单独记录，不直接作为模型真实错误。
- PARTIAL：答案覆盖部分必要事实但漏掉关键约束；按错误计入。

输出建议 JSONL，每行：
```json
{"source_id":"...","profile":"...","verdict":"PASS|FAIL|LANGUAGE_ONLY|GOLD_QUESTIONABLE|PARTIAL","reason":"简短原因","corrected_answer":"如需要可填"}
```

最终汇总：
- 每个 profile 的 PASS / FAIL / LANGUAGE_ONLY / GOLD_QUESTIONABLE / PARTIAL 数量。
- adjusted pass rate：`(PASS + LANGUAGE_ONLY) / (总数 - GOLD_QUESTIONABLE)`。
- conservative pass rate：`PASS / 总数`。
- 主要错误类型表：多证据聚合少算、当前状态/版本选择错误、abstention 表达未匹配、偏好判断边界、证据缺失、语言问题等。
