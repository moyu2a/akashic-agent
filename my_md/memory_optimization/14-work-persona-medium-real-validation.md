# Work Persona Medium Real Validation

## Scope

This run validates the current best retry-shadow path with manual work persona on the 40-case medium real LLM set.

Configuration:

- mode: `safe_version_replace_guided_with_retry_shadow`
- persona: `work`
- real LLM: enabled
- case set: balanced medium, `20` common + `20` hard
- repeats: `1`
- timeout: `60s`
- checkpoint: `/tmp/akashic-p6o29-work-persona-medium-real-checkpoint.jsonl`

Paths:

- workspace: `/tmp/akashic-p6o29-work-persona-medium-real-workspace`
- report dir: `my_md/memory_optimization/eval_reports/p6o29_work_persona_medium_real_v1`
- JSON report: `my_md/memory_optimization/eval_reports/p6o29_work_persona_medium_real_v1/system_path_safe_version_eval.json`
- Markdown report: `my_md/memory_optimization/eval_reports/p6o29_work_persona_medium_real_v1/system_path_safe_version_eval.md`

## Method

Command:

```bash
uv run python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace /tmp/akashic-p6o29-work-persona-medium-real-workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o29_work_persona_medium_real_v1 \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --enable-real-llm \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --modes safe_version_replace_guided_with_retry_shadow \
  --persona-mode work \
  --timeout-s 60 \
  --checkpoint-jsonl /tmp/akashic-p6o29-work-persona-medium-real-checkpoint.jsonl \
  --early-infra-abort-count 5 \
  --early-infra-abort-rate 0.5 \
  --allow-infra-blocked-exit-zero
```

Post-run parsing extracted:

- overall metrics from `system_path_safe_version_eval.json`;
- failed case ids and post-check retry reasons;
- raw final answers from local `sessions.db`.

## Data

Overall:

| metric | value |
| --- | ---: |
| unique cases | 40 |
| case rows | 40 |
| real LLM | true |
| provider errors | 0 |
| timeouts | 0 |
| answer success | 37 / 40 |
| answer rate | 92.5% |
| grounding rate | 100.0% |
| forbidden rate | 0.0% |
| would retry | 3 |
| retry reasons | `required_terms_missing: 3`, `answer_choice_group_missing: 1` |
| avg latency | 7314.825 ms |
| avg total tokens | 6012.3 |
| total tokens | 240492 |
| token metrics available | true |

Compared with the prior P6o27 medium real retry-shadow result:

| run | mode | persona | cases | answer success | answer rate |
| --- | --- | --- | ---: | ---: | ---: |
| P6o27 | `safe_version_replace_guided_with_retry_shadow` | casual/default | 40 | 34 / 40 | 85.0% |
| P6o29 | `safe_version_replace_guided_with_retry_shadow` | work | 40 | 37 / 40 | 92.5% |

Delta: `+3` successful cases, `+7.5` percentage points.

## Failed Cases

### `hard_graph_bridge_01`

Input:

```text
那个图谱路由怎么接？
```

Failures:

- `missing_expected_answer_term`
- post-check retry reason: `required_terms_missing`

Raw answer:

```text
我先查一下近期上下文和记忆，看看“图谱路由”具体指什么。

<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="read_file">
<｜｜DSML｜｜parameter name="file" string="true">/tmp/akashic-p6o29-work-persona-medium-real-workspace/repeat-00/case-024-safe_version_replace_guided_with_retry_shadow/memory/RECENT_CONTEXT.md</｜｜DSML｜｜parameter>
</｜｜DSML｜｜invoke>
<｜｜DSML｜｜invoke name="read_file">
<｜｜DSML｜｜parameter name="file" string="true">/tmp/akashic-p6o29-work-persona-medium-real-workspace/repeat-00/case-024-safe_version_replace_guided_with_retry_shadow/memory/HISTORY.md</｜｜DSML｜｜parameter>
</｜｜DSML｜｜invoke>
</｜｜DSML｜｜tool_calls>
```

Judgment:

- Real answer-layer error.
- Work persona blocked the earlier plain `<read_file>` style but did not block provider-specific DSML tool-call markup.
- The final answer became a meta action instead of answering from allowed evidence.

### `hard_version_chain_01`

Input:

```text
那个旧方案怎么回滚？
```

Failures:

- `missing_expected_answer_term`
- post-check retry reason: `required_terms_missing`

Raw answer:

```text
先查一下记忆文件里的版本链记录，确认回滚候选怎么存的。

<｜｜DSML｜｜tool_calls>
<｜｜DSML｜｜invoke name="read_file">
<｜｜DSML｜｜parameter name="file" string="true">/tmp/akashic-p6o29-work-persona-medium-real-workspace/repeat-00/case-025-safe_version_replace_guided_with_retry_shadow/memory/MEMORY.md</｜｜DSML｜｜parameter>
</｜｜DSML｜｜invoke>
<｜｜DSML｜｜invoke name="read_file">
<｜｜DSML｜｜parameter name="file" string="true">/tmp/akashic-p6o29-work-persona-medium-real-workspace/repeat-00/case-025-safe_version_replace_guided_with_retry_shadow/memory/HISTORY.md</｜｜DSML｜｜parameter>
</｜｜DSML｜｜invoke>
</｜｜DSML｜｜tool_calls>
```

Judgment:

- Real answer-layer error.
- Same failure family as previous `<read_file>` issue, but now surfaced in DSML syntax.
- This is not a recall problem; grounding was 100% and allowed evidence was included.

### `hard_preference_recall_02`

Input:

```text
上次那个回答方式怎么说？
```

Failures:

- `missing_expected_answer_term`
- `missing_expected_answer_term_group`
- `missing_expected_answer_term_group`
- post-check retry reasons: `required_terms_missing`, `answer_choice_group_missing`

Raw answer:

```text
先翻一下记忆文件核实“上次的回答方式”具体指什么。
```

Judgment:

- Real answer-layer error.
- No pseudo XML was output, but the answer is still a meta action / clarification-like action instead of applying the available preference evidence.
- The same case passed in the targeted six-case run, so this may be stochastic, but the failure mode remains: meta action can still override direct memory answer.

## Root Cause Analysis

The 3 failed cases share the same high-level pattern:

- retrieval and grounding were successful;
- allowed evidence was present in the prompt;
- the model did not treat the injected evidence contract as already completed answer evidence;
- the final answer became either a pseudo tool call or a meta action.

This means the remaining issue is not memory recall. The memory system already retrieved and governed the relevant facts. The model sometimes still behaves as if it needs to retrieve the memory again.

### Why "先查/先翻" happened despite complete recall

The global agent rules contain reasonable production rules for ordinary conversations:

- current or external facts should be checked before answering;
- historical questions may require recall/search/fetch;
- macro timeline browsing can use `read_file HISTORY.md`;
- skills should be read with `read_file` before execution.

Those rules are useful for normal agent behavior, but they conflict with system-path eval turns where an `Evidence Contract` has already been injected. In these eval turns, `allowed_evidence` / `current_truth` is not ordinary memory summary; it is the already-filtered answer evidence.

The model failed to reliably distinguish these two situations:

| situation | correct behavior |
| --- | --- |
| Ordinary retrieved memory / recall preview | Treat as candidate context; fetch source if details or exact history matter |
| `Evidence Contract` with `allowed_evidence` / `current_truth` and no insufficient fallback | Treat as already-governed answer evidence; answer directly |

The failed prompts contained vague historical references such as "那个", "上次", and "旧方案". These phrases activated the model's general "go verify history first" habit, even though the answer evidence had already been supplied.

### Why DSML appeared

The literal `DSML` syntax is not generated by this repository's runtime. Repository search only finds it in historical issue notes and the validation report, not in prompt-building or tool-execution code.

The eval path used an empty `ToolRegistry`, so no real tool call was executed. The model/provider returned tool-call-like DSML text in `content`, and the provider adapter correctly treated it as final text because it was not present in the structured `tool_calls` field.

This matches an existing known issue family: provider/model output can emit literal DSML tool syntax in final-only / tools-unavailable contexts.

### Why current work persona was not enough

The work persona already says the final answer should be natural language and should not contain examples like `<read_file>`, `<search>`, or `<tool>`.

It reduced the earlier failure cluster and improved medium accuracy from `85.0%` to `92.5%`, but it did not explicitly cover:

- provider-specific DSML tags such as `<｜｜DSML｜｜tool_calls>`;
- short meta-action final answers such as "先翻一下记忆文件核实..."。

So the remaining failure mode is narrower: not casual style, not ordinary `<read_file>`, but provider-specific pseudo tool markup and meta-action final answers.

## Solution Reasoning

The next solution should avoid the unsafe shortcut "if memory exists, answer from memory." That would risk answering from ordinary memory summaries instead of original facts.

The safer direction is to define evidence types globally:

1. Ordinary memory summaries are candidate context.
   They may need source verification for exact facts, original wording, timelines, current status, or concrete operational steps.

2. Answer Evidence Contract blocks are governed answer evidence.
   When a block contains `Evidence Contract`, `allowed_evidence`, `current_truth`, or `Answer Candidate Contract`, and it has enough facts to answer the user's question, it should be treated as already retrieved and already filtered evidence.

This suggests a global rule like:

```text
When an Answer Evidence Contract is present, and allowed_evidence/current_truth directly answers the user's request, treat it as already-completed retrieval and governed answer evidence.
Do not restart recall, search files, read memory files, or output "先查/先翻/核实" as the final answer.
Answer directly from allowed_evidence/current_truth.
Only say evidence is insufficient when the contract marks insufficient evidence or the allowed evidence does not contain facts that answer the request.
```

This is better than endlessly adding priority patches because it gives the model a stable ontology:

- ordinary memory summary = candidate evidence;
- answer contract = governed answer evidence;
- insufficient contract = admit insufficiency;
- current external world = still verify with tools.

### "Enough evidence" definition

For this system, evidence should be considered enough when all of these are true:

- the turn contains `Evidence Contract` / `allowed_evidence` / `current_truth` / `Answer Candidate Contract`;
- the contract does not indicate insufficient evidence fallback;
- `allowed_evidence` or `current_truth` contains a concrete fact that directly answers the user's question;
- the answer does not require current external-world state outside the contract.

If those conditions hold, the model should answer from the contract and should not initiate another retrieval step.

### Guardrail still needed

Prompt changes reduce probability; deterministic post-check is still needed for visibility and retry.

Recommended post-check reasons:

- `dsml_tool_markup_in_final_answer`
- `tool_markup_in_final_answer`
- `meta_action_final_answer`
- `answerable_evidence_contract_ignored`

These checks would turn the current residual failures into explicit retry/debug signals instead of generic `missing_expected_answer_term`.

## Verification

Additional verification after adding `persona_mode` eval support:

| command | result |
| --- | --- |
| `uv run python -m compileall agent/persona.py prompts/agent.py agent/core/prompt_block.py agent/context.py memory2/eval_system_path_safe_version.py scripts/run_memory_system_path_safe_version_eval.py tests/test_agent_core_p4_prompt_block.py tests/test_memory_system_path_safe_version_eval.py` | exit code 0 |
| `uv run --with pytest --with pytest-asyncio pytest tests/test_agent_core_p4_prompt_block.py tests/test_memory_system_path_safe_version_eval.py::test_system_path_eval_can_render_work_persona -q -p no:cacheprovider` | `10 passed in 0.58s` |

## Conclusion

The work persona improved the current best retry-shadow medium real score from `85.0%` to `92.5%` on the comparable 40-case set.

What improved:

- The known six-case failure cluster was fixed in targeted validation.
- Medium-scale answer success increased by `+7.5` percentage points.
- Grounding remained `100.0%`.
- Forbidden violation remained `0.0%`.
- Provider errors and timeouts remained `0`.

Remaining bottleneck:

- The main residual issue is still answer layer, not recall.
- Work persona reduces casual-style drift and plain tool-placeholder output, but does not fully prevent provider-specific DSML pseudo tool-call markup.
- The next improvement should extend the final-answer natural-language rule and post-check guard to cover DSML-like tool-call markup and short meta-action answers such as “先翻一下记忆文件核实...”.
