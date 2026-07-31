# Work Persona Side Handoff

## Purpose

This handoff records the side-conversation work so the main thread can continue from the current state without re-discovering context.

## Current Branch / Workspace

- Worktree: `/home/jjh/git_work/akashic-agent/.worktrees/memory-next`
- Topic: work-mode persona for memory answer correctness
- Production default: still `casual`
- Work mode: manually selectable, not automatically enabled

## Implemented In This Side Conversation

### Persona split

Files:

- `agent/persona.py`
- `prompts/agent.py`
- `agent/core/prompt_block.py`
- `agent/context.py`

Changes:

- Added `PersonaMode = Literal["casual", "work"]`.
- Renamed existing casual prompt to `CASUAL_PERSONALITY_RULES`.
- Added `WORK_PERSONALITY_RULES`.
- Added `get_personality_rules(mode="casual")`.
- Kept compatibility alias: `PERSONALITY_RULES = CASUAL_PERSONALITY_RULES`.
- Added manual work-mode entry points:
  - `build_agent_static_identity_prompt(..., persona_mode="work")`
  - `IdentityPromptBlock(persona_mode="work")`
  - `ContextBuilder(..., persona_mode="work")`

Work prompt key rules:

- task correctness beats style;
- answer directly, conclusion first;
- preserve key terms from user/evidence/test expectations;
- when tools are needed, call tools for real;
- final answer must be natural language;
- do not output tool-call placeholders, internal action plans, pseudo XML tags such as `<read_file>`, `<search>`, `<tool>`;
- memory recall / experiment analysis / fact judgment must use current evidence; if insufficient, say insufficient.

### Eval manual mode support

Files:

- `memory2/eval_system_path_safe_version.py`
- `scripts/run_memory_system_path_safe_version_eval.py`
- `tests/test_memory_system_path_safe_version_eval.py`

Changes:

- Added `persona_mode` parameter to `run_system_path_safe_version_cases(...)`.
- Eval runner now creates `ContextBuilder(..., persona_mode=persona_mode)`.
- CLI added:

```bash
--persona-mode casual|work
```

- Default remains `casual`.

## Tests / Verification

Focused verification after implementation:

| command | result |
| --- | --- |
| `uv run python -m compileall agent/persona.py prompts/agent.py agent/core/prompt_block.py agent/context.py memory2/eval_system_path_safe_version.py scripts/run_memory_system_path_safe_version_eval.py tests/test_agent_core_p4_prompt_block.py tests/test_memory_system_path_safe_version_eval.py` | exit code 0 |
| `uv run --with pytest --with pytest-asyncio pytest tests/test_agent_core_p4_prompt_block.py tests/test_memory_system_path_safe_version_eval.py::test_system_path_eval_can_render_work_persona -q -p no:cacheprovider` | `10 passed in 0.58s` |
| `uv run --with pytest --with pytest-asyncio pytest tests/test_support_modules.py -q -p no:cacheprovider` | `12 passed in 3.17s` |

## Validation Data

### Targeted 6-case retry-shadow rerun

Report:

- `my_md/memory_optimization/13-work-persona-six-case-validation.md`
- `my_md/memory_optimization/eval_reports/p6o28_work_persona_six_retry_shadow_v1/system_path_safe_version_eval.json`
- `my_md/memory_optimization/eval_reports/p6o28_work_persona_six_retry_shadow_v1/system_path_safe_version_eval.md`

Configuration:

- mode: `safe_version_replace_guided_with_retry_shadow`
- persona: `work`
- real LLM: true
- cases: the 6 previously failed retry-shadow cases

Result:

| metric | value |
| --- | ---: |
| cases | 6 |
| answer success | 6 / 6 |
| answer rate | 100.0% |
| grounding rate | 100.0% |
| forbidden rate | 0.0% |
| provider errors | 0 |
| timeouts | 0 |
| would retry | 0 |

Conclusion:

- All 6 previously failed retry-shadow cases passed with manual work persona.
- No `<read_file>`, `<search>`, `<tool>`, or ordinary pseudo tool markup appeared.
- Key terms such as `中文`, `条目式`, `NetworkX`, `叶子`, `回滚`, `睡眠巩固`, and cleanup relation were preserved.

### 40-case medium real LLM rerun

Report:

- `my_md/memory_optimization/14-work-persona-medium-real-validation.md`
- `my_md/memory_optimization/eval_reports/p6o29_work_persona_medium_real_v1/system_path_safe_version_eval.json`
- `my_md/memory_optimization/eval_reports/p6o29_work_persona_medium_real_v1/system_path_safe_version_eval.md`

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

Result:

| run | mode | persona | cases | answer success | answer rate |
| --- | --- | --- | ---: | ---: | ---: |
| P6o27 prior best | `safe_version_replace_guided_with_retry_shadow` | casual/default | 40 | 34 / 40 | 85.0% |
| P6o29 | `safe_version_replace_guided_with_retry_shadow` | work | 40 | 37 / 40 | 92.5% |

Other metrics:

- grounding rate: `100.0%`
- forbidden rate: `0.0%`
- provider errors: `0`
- timeouts: `0`
- would retry: `3`
- retry reasons: `required_terms_missing: 3`, `answer_choice_group_missing: 1`

Conclusion:

- Manual work persona improved medium real retry-shadow from `85.0%` to `92.5%`.
- Improvement: `+3` successful cases, `+7.5` percentage points.
- Remaining failures are answer-layer failures, not recall failures.

## Remaining 40-Case Failures

### `hard_graph_bridge_01`

Input:

```text
那个图谱路由怎么接？
```

Output shape:

- The answer says it will first check recent context and memory.
- Then it emits literal DSML-style pseudo tool calls for `read_file RECENT_CONTEXT.md` and `read_file HISTORY.md`.

Cause:

- Real answer-layer error.
- The model did not treat `allowed_evidence/current_truth` as already-completed answer evidence.
- It fell back to the ordinary "vague historical reference => verify context first" habit.
- The provider/model emitted DSML-like tool-call syntax in final text.

### `hard_version_chain_01`

Input:

```text
那个旧方案怎么回滚？
```

Output shape:

- The answer says it will first check memory files for version-chain records.
- Then it emits literal DSML-style pseudo tool calls for `read_file MEMORY.md` and `read_file HISTORY.md`.

Cause:

- Real answer-layer error.
- Same family as previous `<read_file>` failure, now in provider-specific DSML syntax.
- Recall/grounding was correct; final answer did not use it directly.

### `hard_preference_recall_02`

Input:

```text
上次那个回答方式怎么说？
```

Output shape:

```text
先翻一下记忆文件核实“上次的回答方式”具体指什么。
```

Cause:

- Real answer-layer error.
- No DSML markup, but still a meta-action final answer.
- The model should have answered from available preference evidence: `中文回答` and `条目式`.

## Root Cause Summary

The system has already recalled and governed the evidence, but the model does not always understand the evidence block's role.

Correct intended flow:

```text
user vague historical query
-> Evidence Contract / allowed_evidence / current_truth already injected
-> treat this as governed answer evidence
-> directly answer
```

Observed residual failure flow:

```text
user vague historical query
-> model recognizes "那个 / 上次 / 旧方案"
-> applies general history-retrieval habit
-> says "先查/先翻/核实"
-> sometimes emits provider-specific DSML pseudo tool calls
```

Important distinction:

- ordinary memory summary should remain candidate context and may require source verification;
- `Evidence Contract / allowed_evidence / current_truth / Answer Candidate Contract` should be treated as governed answer evidence when it directly answers the request and is not marked insufficient.

## Proposed Next Step

Do not add a broad "memory always wins" rule. That risks answering from ordinary summaries instead of original facts.

Instead, add a global evidence-type rule:

```text
When an Answer Evidence Contract is present, and allowed_evidence/current_truth directly answers the user's request, treat it as already-completed retrieval and governed answer evidence.
Do not restart recall, search files, read memory files, or output "先查/先翻/核实" as the final answer.
Answer directly from allowed_evidence/current_truth.
Only say evidence is insufficient when the contract marks insufficient evidence or the allowed evidence does not contain facts that answer the request.
```

Recommended post-check additions:

- `dsml_tool_markup_in_final_answer`
- `tool_markup_in_final_answer`
- `meta_action_final_answer`
- `answerable_evidence_contract_ignored`

These should make residual failures explicit instead of hiding them under generic `missing_expected_answer_term`.

## Files Changed In This Side Work

Code/test files touched by this side conversation:

- `agent/persona.py`
- `prompts/agent.py`
- `agent/core/prompt_block.py`
- `agent/context.py`
- `memory2/eval_system_path_safe_version.py`
- `scripts/run_memory_system_path_safe_version_eval.py`
- `tests/test_agent_core_p4_prompt_block.py`
- `tests/test_memory_system_path_safe_version_eval.py`

Docs/reports added by this side conversation:

- `my_md/memory_optimization/12-work-persona-mode-test-report.md`
- `my_md/memory_optimization/13-work-persona-six-case-validation.md`
- `my_md/memory_optimization/14-work-persona-medium-real-validation.md`
- `my_md/memory_optimization/15-work-persona-side-handoff.md`
- `my_md/memory_optimization/eval_reports/p6o28_work_persona_six_retry_shadow_v1/`
- `my_md/memory_optimization/eval_reports/p6o29_work_persona_medium_real_v1/`

Pre-existing unrelated dirty files were present before this handoff and should not be assumed to belong to this side change unless separately reviewed:

- `memory2/eval_llm_sample.py`
- `memory2/system_path_safe_version_contract.py`
- memory/eval-related tests listed in `git status`
- `my_md/memory_optimization/eval_reports/p6o13_system_path_real_llm_validation_v1/`

## Resume In Main Thread

Use this section when returning from the side conversation to the main thread.

### What is already done

- Manual `work` persona mode has been implemented.
- Default production behavior remains `casual`.
- Eval runner can select persona with `--persona-mode casual|work`.
- Focused 6-case retry-shadow validation passed: `6 / 6 = 100.0%`.
- Medium 40-case real LLM validation improved from `34 / 40 = 85.0%` to `37 / 40 = 92.5%`.
- Test methods, data, and conclusions are recorded in:
  - `my_md/memory_optimization/12-work-persona-mode-test-report.md`
  - `my_md/memory_optimization/13-work-persona-six-case-validation.md`
  - `my_md/memory_optimization/14-work-persona-medium-real-validation.md`

### What remains unresolved

The 40-case run still has 3 failures:

| case | failure shape | likely cause |
| --- | --- | --- |
| `hard_graph_bridge_01` | says "先查" and emits DSML-style pseudo `read_file` calls | answer layer ignores already injected governed evidence |
| `hard_version_chain_01` | says "先查记忆文件" and emits DSML-style pseudo `read_file` calls | same as above, plus tool-markup leakage |
| `hard_preference_recall_02` | final answer is only "先翻一下记忆文件核实..." | meta-action final answer despite sufficient evidence |

These failures are not recall failures. Grounding was `100.0%`; the model had usable evidence but did not treat `Evidence Contract / allowed_evidence / current_truth` as already-completed answer evidence.

### Recommended next implementation

Implement a narrow evidence-contract rule, not a broad "memory always wins" rule:

```text
When an Answer Evidence Contract is present, and allowed_evidence/current_truth directly answers the user's request, treat it as already-completed retrieval and governed answer evidence.
Do not restart recall, search files, read memory files, or output "先查/先翻/核实" as the final answer.
Answer directly from allowed_evidence/current_truth.
Only say evidence is insufficient when the contract marks insufficient evidence or the allowed evidence does not contain facts that answer the request.
```

Reasoning:

- Ordinary memory summaries can still be candidate context and may require source verification.
- Governed evidence blocks such as `Evidence Contract`, `allowed_evidence`, `current_truth`, and `Answer Candidate Contract` are different: they are produced by the current retrieval/eval pipeline for this answer.
- This avoids making stale or weak memory override source truth, while preventing the model from trying to recall memory that has already been recalled.

### Recommended post-check additions

Add deterministic answer-layer diagnostics:

- `dsml_tool_markup_in_final_answer`
- `tool_markup_in_final_answer`
- `meta_action_final_answer`
- `answerable_evidence_contract_ignored`

Expected benefit:

- DSML / pseudo tool-call leakage becomes explicit.
- "先查/先翻/核实" meta-action final answers become explicit.
- Future failed cases are easier to separate into scorer strictness, recall failure, and answer-contract violation.

### Suggested main-thread order

1. Review and commit the side work if acceptable.
2. Implement the narrow evidence-contract rule in the prompt/answer contract layer.
3. Add deterministic post-check reasons for pseudo tool markup and meta-action final answers.
4. Rerun the same 3 failed cases first.
5. Rerun the 6-case targeted set.
6. Rerun the 40-case medium real LLM set.
7. Record method, data, failures, and conclusion in a new numbered report.

### Useful commands

Focused verification already used:

```bash
uv run python -m compileall agent/persona.py prompts/agent.py agent/core/prompt_block.py agent/context.py memory2/eval_system_path_safe_version.py scripts/run_memory_system_path_safe_version_eval.py tests/test_agent_core_p4_prompt_block.py tests/test_memory_system_path_safe_version_eval.py
```

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_agent_core_p4_prompt_block.py tests/test_memory_system_path_safe_version_eval.py::test_system_path_eval_can_render_work_persona -q -p no:cacheprovider
```

```bash
uv run --with pytest --with pytest-asyncio pytest tests/test_support_modules.py -q -p no:cacheprovider
```
