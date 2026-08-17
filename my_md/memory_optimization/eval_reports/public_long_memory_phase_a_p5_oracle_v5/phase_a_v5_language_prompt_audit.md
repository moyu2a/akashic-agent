# Phase A v5 Language Prompt Audit

## Metrics

- `finding_count`: `129`
- `production_hidden_answer_language_bias_count`: `0`
- `public_p5_hidden_answer_language_bias_count`: `0`
- `legacy_benchmark_answer_language_bias_count`: `3`
- `fixture_answer_language_bias_count`: `81`

## Hidden Bias Gate

- production hidden answer-language bias: `0`
- public P5 hidden answer-language bias: `0`
- legacy LongMemEval English-only prompts remain classified as `legacy_benchmark` and are not on the public P5 runner path.

## Legacy / Fixture Findings

| classification | risk | path | line | text |
| --- | --- | --- | ---: | --- |
| legacy_benchmark | isolated_answer_language_bias | eval/longmemeval/config.example.toml | 45 | system_prompt   = "You are a helpful personal assistant with long-term memory. When the user asks about past conversations or personal details, always use your  |
| legacy_benchmark | isolated_answer_language_bias | eval/longmemeval/qa_runner.py | 118 | content=instance.question + "\n\n[Respond in English only. One sentence or short phrase.]", |
| legacy_benchmark | isolated_answer_language_bias | eval/longmemeval/runtime.py | 24 | Answer in English only. Be concise: one sentence or a short phrase. |
| fixture | isolated_answer_language_bias | scripts/run_memory_comprehensive_online_eval.py | 84 | answer = "三路召回使用 RRF 融合排序，并用中文回答。" |
| fixture | isolated_answer_language_bias | scripts/run_memory_comprehensive_online_eval.py | 86 | answer = "NetworkX 图谱可以辅助第三路召回，并用中文回答。" |
| fixture | isolated_answer_language_bias | scripts/run_memory_comprehensive_online_eval.py | 88 | answer = "Python 测试优先使用 pytest，并用中文回答。" |
| fixture | isolated_answer_language_bias | scripts/run_memory_comprehensive_online_eval.py | 90 | answer = "回答时应保持条目式，并用中文回答。" |
| fixture | isolated_answer_language_bias | scripts/run_memory_llm_sample_eval.py | 33 | answer = "你在 Telegram 会话偏好中文回答。" |
| fixture | isolated_answer_language_bias | scripts/run_memory_llm_sample_eval.py | 35 | answer = "我应该用中文回答你。" |
| fixture | isolated_answer_language_bias | tests/fixtures/memory_eval_cases/conflict_memory.json | 13 | "summary": "用户喜欢使用中文回答", |
| fixture | isolated_answer_language_bias | tests/fixtures/memory_eval_cases/conflict_memory.json | 22 | "summary": "用户不喜欢使用中文回答", |
| fixture | isolated_answer_language_bias | tests/fixtures/memory_eval_cases/conflict_memory.json | 43 | "query": "我喜欢中文回答吗？" |
| fixture | isolated_answer_language_bias | tests/fixtures/memory_eval_cases/cross_scope_isolation.json | 13 | "summary": "用户在 Telegram 会话偏好中文回答", |
| fixture | isolated_answer_language_bias | tests/fixtures/memory_eval_cases/duplicate_memory.json | 13 | "summary": "用户喜欢中文回答", |
| fixture | isolated_answer_language_bias | tests/fixtures/memory_eval_cases/duplicate_memory.json | 22 | "summary": "用户喜欢中文回答", |
| fixture | isolated_answer_language_bias | tests/test_memory_answer_contract.py | 97 | assert "在中文回答" not in text |
| fixture | isolated_answer_language_bias | tests/test_memory_answer_contract.py | 98 | assert "中文回答" not in text |
| fixture | isolated_answer_language_bias | tests/test_memory_answer_contract.py | 335 | assert "中文回答" not in text |
| fixture | isolated_answer_language_bias | tests/test_memory_comprehensive_online_cli.py | 400 | assert "请继续用中文回答，并保持 pytest 风格。" not in report_text |
| fixture | isolated_answer_language_bias | tests/test_memory_comprehensive_online_cli.py | 403 | assert "请继续用中文回答，并保持 pytest 风格。" not in markdown_text |
| fixture | isolated_answer_language_bias | tests/test_memory_comprehensive_online_eval.py | 54 | answer = "三路召回使用 RRF 融合排序，并用中文回答。" |
| fixture | isolated_answer_language_bias | tests/test_memory_comprehensive_online_eval.py | 56 | answer = "NetworkX 图谱可以辅助第三路召回，并用中文回答。" |
| fixture | isolated_answer_language_bias | tests/test_memory_comprehensive_online_eval.py | 58 | answer = "Python 测试优先使用 pytest，并用中文回答。" |
| fixture | isolated_answer_language_bias | tests/test_memory_eval_llm_sample.py | 31 | answer: str = "我应该用中文回答你。", |
| fixture | isolated_answer_language_bias | tests/test_memory_eval_llm_sample.py | 79 | result = score_answer_text("我应该用中文回答你。", expectation, ["m_pref_cn"]) |
| fixture | isolated_answer_language_bias | tests/test_memory_eval_llm_sample.py | 132 | AnswerExpectation(expected_answer_contains=("中文回答",)), |
| fixture | isolated_answer_language_bias | tests/test_memory_eval_llm_sample.py | 226 | result = score_answer_text("我会用中文回答。", expectation, ["m_graph_1"]) |
| fixture | isolated_answer_language_bias | tests/test_memory_eval_llm_sample.py | 238 | provider = _FakeLLMProvider("我应该用中文回答你。") |
| fixture | isolated_answer_language_bias | tests/test_memory_eval_llm_sample.py | 249 | assert result.answer_length == len("我应该用中文回答你。") |
| fixture | isolated_answer_language_bias | tests/test_memory_eval_llm_sample.py | 416 | response=LLMResponse(content="我应该用中文回答你。", tool_calls=[]), |
| fixture | isolated_answer_language_bias | tests/test_memory_eval_llm_sample.py | 438 | content="我应该用中文回答你。", |
| fixture | isolated_answer_language_bias | tests/test_memory_eval_llm_sample.py | 464 | content="我应该用中文回答你。", |
| fixture | isolated_answer_language_bias | tests/test_memory_eval_llm_sample.py | 516 | fake_answer = "我应该用中文回答你。" |
| fixture | isolated_answer_language_bias | tests/test_memory_experiments_live_smoke.py | 155 | "summary": "用户明确要求记住：喜欢中文回答", |
| fixture | isolated_answer_language_bias | tests/test_memory_experiments_live_smoke.py | 506 | text="请记住我喜欢中文回答。", |
| fixture | isolated_answer_language_bias | tests/test_memory_experiments_live_smoke.py | 579 | text="请记住我喜欢中文回答。", |
| fixture | isolated_answer_language_bias | tests/test_memory_experiments_runner.py | 294 | result = score_write_candidate_shadow("用户明确要求记住：喜欢中文回答") |
| fixture | isolated_answer_language_bias | tests/test_memory_experiments_runner.py | 303 | "用户明确要求记住：以后都用中文回答", |
| fixture | isolated_answer_language_bias | tests/test_memory_experiments_runner.py | 347 | "用户明确要求记住：以后都用中文回答", |
| fixture | isolated_answer_language_bias | tests/test_memory_experiments_runner.py | 350 | {"id": "mem_1", "summary": "用户明确要求记住：以后都用中文回答"}, |
| fixture | isolated_answer_language_bias | tests/test_memory_experiments_runner.py | 370 | {"id": "mem_1", "summary": "用户喜欢中文回答"}, |
| fixture | isolated_answer_language_bias | tests/test_memory_experiments_runner.py | 400 | "summary": "用户明确要求记住：喜欢中文回答", |
| fixture | isolated_answer_language_bias | tests/test_memory_experiments_runner.py | 452 | "summary": "用户明确要求记住：以后都用中文回答", |
| fixture | isolated_answer_language_bias | tests/test_memory_experiments_runner.py | 475 | assert candidates[0]["summary"] == "用户明确要求记住：以后都用中文回答" |
| fixture | isolated_answer_language_bias | tests/test_memory_experiments_runner.py | 487 | {"id": "mem_existing", "summary": "用户明确要求记住：以后都用中文回答"}, |
| fixture | isolated_answer_language_bias | tests/test_memory_experiments_runner.py | 496 | "summary": "用户明确要求记住：以后都用中文回答", |
| fixture | isolated_answer_language_bias | tests/test_memory_experiments_runner.py | 528 | {"id": "mem_1", "summary": "用户明确要求记住：以后都用中文回答"}, |
| fixture | isolated_answer_language_bias | tests/test_memory_experiments_runner.py | 537 | "summary": "用户明确要求记住：以后都用中文回答", |
| fixture | isolated_answer_language_bias | tests/test_memory_experiments_runner.py | 557 | {"id": "mem_existing", "summary": "用户明确要求记住：以后都用中文回答"}, |
| fixture | isolated_answer_language_bias | tests/test_memory_experiments_runner.py | 566 | "summary": "用户明确要求记住：以后都用中文回答", |
| fixture | isolated_answer_language_bias | tests/test_memory_governance_dataset.py | 31 | "summary": "用户现在偏好中文回答", |
| fixture | isolated_answer_language_bias | tests/test_memory_governance_dataset.py | 32 | "content": "用户现在偏好中文回答", |
| fixture | isolated_answer_language_bias | tests/test_memory_governance_dataset.py | 42 | "expected_answer_contains_any": [["中文回答", "保持中文"]], |
| fixture | isolated_answer_language_bias | tests/test_memory_governance_dataset.py | 87 | expected_answer_contains_any=(("中文回答", "保持中文"),), |
| fixture | isolated_answer_language_bias | tests/test_memory_injection_governance_experiments.py | 76 | "summary": "用户希望中文回答", |
| fixture | isolated_answer_language_bias | tests/test_memory_llm_sample_cli.py | 249 | "用户在 Telegram 会话偏好中文回答", |
| fixture | isolated_answer_language_bias | tests/test_memory_llm_sample_cli.py | 251 | "我应该用中文回答你。", |
| fixture | isolated_answer_language_bias | tests/test_memory_llm_sample_cli.py | 252 | "你在 Telegram 会话偏好中文回答。", |
| fixture | isolated_answer_language_bias | tests/test_memory_semantic_judge.py | 46 | answer_text="保持中文回答", |
| fixture | isolated_answer_language_bias | tests/test_memory_semantic_judge.py | 54 | answer_text="保持中文回答", |
| fixture | isolated_answer_language_bias | tests/test_memory_semantic_judge.py | 87 | AnswerExpectation(expected_answer_contains=("中文回答",)), |
| fixture | isolated_answer_language_bias | tests/test_memory_semantic_judge.py | 105 | AnswerExpectation(expected_answer_contains=("中文回答",)), |
| fixture | isolated_answer_language_bias | tests/test_memory_sleep_consolidation_engine.py | 37 | "summary": "用户喜欢中文回答", |
| fixture | isolated_answer_language_bias | tests/test_memory_sleep_consolidation_engine.py | 46 | "summary": "用户喜欢中文回答", |
| fixture | isolated_answer_language_bias | tests/test_memory_sleep_consolidation_engine.py | 166 | conversation="USER: 我喜欢中文回答", |
| fixture | isolated_answer_language_bias | tests/test_memory_sleep_consolidation_experiments.py | 41 | _item("m1", "用户喜欢中文回答"), |
| fixture | isolated_answer_language_bias | tests/test_memory_sleep_consolidation_experiments.py | 42 | _item("m2", "用户喜欢中文回答"), |
| fixture | isolated_answer_language_bias | tests/test_memory_sleep_consolidation_experiments.py | 62 | _item("m3", "用户喜欢中文回答"), |
| fixture | isolated_answer_language_bias | tests/test_memory_sleep_consolidation_experiments.py | 87 | "用户强偏好中文回答", |
| fixture | isolated_answer_language_bias | tests/test_memory_sleep_consolidation_experiments.py | 105 | _item("m1", "用户喜欢使用中文回答"), |
| fixture | isolated_answer_language_bias | tests/test_memory_sleep_consolidation_experiments.py | 106 | _item("m2", "用户不喜欢使用中文回答"), |
| fixture | isolated_answer_language_bias | tests/test_memory_sleep_consolidation_experiments.py | 128 | _item(f"m{idx}", f"用户喜欢中文回答 {idx % 2}") for idx in range(12) |
| fixture | isolated_answer_language_bias | tests/test_memory_sleep_consolidation_experiments.py | 183 | _item("m1", "用户喜欢中文回答", source_ref=""), |
| fixture | isolated_answer_language_bias | tests/test_memory_sleep_consolidation_experiments.py | 184 | _item("m2", "用户喜欢中文回答", source_ref=""), |
| fixture | isolated_answer_language_bias | tests/test_memory_sleep_hygiene_provenance.py | 63 | "cli:local:1": "用户说喜欢中文回答", |
| fixture | isolated_answer_language_bias | tests/test_memory_sleep_hygiene_provenance.py | 81 | resolver = MappingSourceRefResolver({"cli:local:1": "用户说喜欢中文回答"}) |
| fixture | isolated_answer_language_bias | tests/test_memory_sleep_hygiene_provenance.py | 96 | content="用户说喜欢中文回答", |
| fixture | isolated_answer_language_bias | tests/test_memory_write_governance_counts.py | 465 | summary="后续同类任务请在中文回答中先给结论", |
| fixture | isolated_answer_language_bias | tests/test_memory_write_governance_counts.py | 473 | {"id": "existing", "summary": "后续同类任务请在中文回答中先给结论"} |
| fixture | isolated_answer_language_bias | tests/test_post_response_memory_experiments.py | 46 | user_msg="请记住我喜欢中文回答", |
| fixture | isolated_answer_language_bias | tests/test_post_response_memory_experiments.py | 53 | "arguments": {"summary": "用户明确要求记住：喜欢中文回答"}, |
| fixture | isolated_answer_language_bias | tests/test_post_response_memory_experiments.py | 97 | user_msg="请记住我喜欢中文回答", |
| fixture | isolated_answer_language_bias | tests/test_post_response_memory_experiments.py | 104 | "arguments": {"summary": "用户明确要求记住：喜欢中文回答"}, |
| fixture | isolated_answer_language_bias | tests/test_post_response_memory_experiments.py | 213 | "arguments": {"summary": "用户明确要求记住：喜欢中文回答"}, |