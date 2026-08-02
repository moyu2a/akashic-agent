# Evidence Contract Conflict Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent governed Evidence Contract turns from being answered as "I need to check memory first" when the contract already contains sufficient `allowed_evidence` / `current_truth`, while preserving normal global history-retrieval safety rules.

**Architecture:** Add a narrow contract-completion rule to the safe-version Evidence Contract render path, add a light global evidence-type boundary without weakening ordinary history retrieval, and extend post-check shadow to classify pseudo tool markup and meta-action final answers. Keep production defaults unchanged; validation is prompt/post-check plus targeted and medium real LLM gates.

**Tech Stack:** Python 3, pytest, existing `memory2` eval modules, existing real LLM CLI `scripts/run_memory_system_path_safe_version_eval.py`, Markdown reports under `my_md/memory_optimization/`.

## Global Constraints

- Keep production default behavior unchanged: no real retry, no default-on production switch.
- Do not weaken ordinary global history retrieval: ordinary memory summaries and `RECENT_CONTEXT.md` remain candidate context requiring source verification when exact history/current facts matter.
- Treat only explicit `Evidence Contract` / `allowed_evidence` / `current_truth` / `Answer Candidate Contract` with `insufficient_evidence_fallback=false` and non-empty answer facts as already retrieved and governed answer evidence.
- Preserve privacy posture: reports and post-check dicts must not include raw prompt or raw answer unless explicitly using a local debug-only artifact.
- Do not touch unrelated untracked `my_md/memory_optimization/eval_reports/p6o13_system_path_real_llm_validation_v1/`.
- Record test method, data, and conclusion in `my_md/memory_optimization/16-evidence-contract-conflict-governance.md`.

---

## File Structure

- Modify `memory2/system_path_safe_version_contract.py`
  - Responsibility: render scoped Evidence Contract instructions. Add "retrieval and governance complete" instructions only for answer guidance variants that already guide final answer selection.
- Modify `prompts/agent.py`
  - Responsibility: global behavior rules. Add one concise evidence-type boundary so global history retrieval does not override sufficient Evidence Contracts.
- Modify `memory2/eval_answer_post_check.py`
  - Responsibility: answer post-check shadow. Add private boolean flags and retry reasons for pseudo tool markup, DSML markup, meta-action final answers, and ignored answerable Evidence Contract.
- Modify `tests/test_memory_system_path_safe_version_contract.py`
  - Responsibility: prompt-render regression tests for scoped contract completion text.
- Modify `tests/test_message_lookup_tool.py`
  - Responsibility: global prompt regression tests. Add a narrow assertion that Evidence Contracts are distinct from ordinary summaries.
- Modify `tests/test_memory_answer_post_check.py`
  - Responsibility: post-check regression tests for the three observed failure families.
- Create or modify `my_md/memory_optimization/16-evidence-contract-conflict-governance.md`
  - Responsibility: record plan, review notes, test methods, data, and conclusions.

---

### Task 1: Prompt Contract Completion Rule

**Files:**
- Modify: `memory2/system_path_safe_version_contract.py:324-365`
- Test: `tests/test_memory_system_path_safe_version_contract.py`

**Interfaces:**
- Consumes: `render_system_path_evidence_contract_block(contract, answer_guidance_enabled=True, answer_prompt_variant=...) -> str`
- Produces: prompt text that tells the model governed retrieval is complete for answerable contract turns.

- [ ] **Step 1: Write failing tests for guided retry and schema-first prompt text**

Add these tests to `tests/test_memory_system_path_safe_version_contract.py`:

```python
def test_guided_retry_shadow_marks_contract_retrieval_complete_when_answerable() -> None:
    result = build_system_path_safe_version_contract(
        query="上次那个回答方式怎么说？",
        baseline_items=[_item("m-current", "用户偏好中文回答。")],
        route_trace={
            "candidates_by_lane": {
                "semantic": [_item("m-current", "用户偏好中文回答。")],
                "keyword": [],
                "provenance": [],
                "graph": [],
            }
        },
        replacements=[],
        top_k=8,
        answer_guidance_enabled=True,
        answer_prompt_variant="guided_retry_shadow",
    )

    text = result.text_block
    assert "retrieval and governance for this turn are already complete" in text
    assert "insufficient_evidence_fallback=false" in text
    assert "Do not restart recall, search, fetch, or read memory files" in text
    assert "Do not output pseudo tool calls, DSML markup" in text
    assert "Do not answer with \"先查\", \"先翻\", or \"核实\"" in text
    assert "用户偏好中文回答。" in text


def test_schema_first_shadow_marks_contract_retrieval_complete_when_answerable() -> None:
    result = build_system_path_safe_version_contract(
        query="那个旧方案怎么回滚？",
        baseline_items=[_item("m-current", "版本链只保留当前叶子并记录回滚候选。")],
        route_trace={
            "candidates_by_lane": {
                "semantic": [_item("m-current", "版本链只保留当前叶子并记录回滚候选。")],
                "keyword": [],
                "provenance": [],
                "graph": [],
            }
        },
        replacements=[],
        top_k=8,
        answer_guidance_enabled=True,
        answer_prompt_variant="schema_first_shadow",
    )

    text = result.text_block
    assert "retrieval and governance for this turn are already complete" in text
    assert "Do not restart recall, search, fetch, or read memory files" in text
    assert "Then write only the final natural-language answer" in text


def test_guided_retry_shadow_does_not_mark_retrieval_complete_when_insufficient() -> None:
    result = build_system_path_safe_version_contract(
        query="这个有没有证据？",
        baseline_items=[],
        route_trace={
            "candidates_by_lane": {
                "semantic": [],
                "keyword": [],
                "provenance": [],
                "graph": [],
            }
        },
        replacements=[],
        top_k=8,
        answer_guidance_enabled=True,
        answer_prompt_variant="guided_retry_shadow",
    )

    assert result.contract.insufficient_evidence_fallback is True
    assert "retrieval and governance for this turn are already complete" not in result.text_block
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest \
  tests/test_memory_system_path_safe_version_contract.py::test_guided_retry_shadow_marks_contract_retrieval_complete_when_answerable \
  tests/test_memory_system_path_safe_version_contract.py::test_schema_first_shadow_marks_contract_retrieval_complete_when_answerable \
  tests/test_memory_system_path_safe_version_contract.py::test_guided_retry_shadow_does_not_mark_retrieval_complete_when_insufficient \
  -q -p no:cacheprovider
```

Expected: both tests fail because the new completion text is absent.

- [ ] **Step 3: Add a shared render helper for answerable Evidence Contract completion text**

In `memory2/system_path_safe_version_contract.py`, add a small helper near `_indent_lines`:

```python
def _answerable_contract_completion_guidance(contract: SystemPathEvidenceContract) -> list[str]:
    if (
        contract.insufficient_evidence_fallback
        or not contract.answer_candidate_contract.current_truth_lines
    ):
        return []
    return [
        "  Because insufficient_evidence_fallback=false and current_truth is present, retrieval and governance for this turn are already complete.",
        "  When insufficient_evidence_fallback=false and current_truth or allowed_evidence answers the user, answer directly from this contract.",
        "  Do not restart recall, search, fetch, or read memory files such as MEMORY.md, HISTORY.md, or RECENT_CONTEXT.md.",
        "  Do not output pseudo tool calls, DSML markup, tool-call placeholders, or internal action plans as the final answer.",
        "  Do not answer with \"先查\", \"先翻\", or \"核实\" when the contract already contains the answer.",
    ]
```

In the `guided_retry_shadow` branch, insert:

```python
                *_answerable_contract_completion_guidance(contract),
```

immediately after:

```python
                "  Use the Answer Candidate Contract to select the final answer.",
```

In the `schema_first_shadow` branch, insert the same helper immediately after:

```python
                "  Use allowed_evidence as the only source for the answer.",
```

using:

```python
                *_answerable_contract_completion_guidance(contract),
```

- [ ] **Step 4: Run prompt contract tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest \
  tests/test_memory_system_path_safe_version_contract.py -q -p no:cacheprovider
```

Expected: all tests in the file pass.

---

### Task 2: Global Evidence-Type Boundary

**Files:**
- Modify: `prompts/agent.py:147-156`
- Test: `tests/test_message_lookup_tool.py`

**Interfaces:**
- Consumes: `build_agent_behavior_rules_prompt(workspace=Path(...)) -> str`
- Produces: global prompt text that distinguishes ordinary memory summaries from governed answer contracts.

- [ ] **Step 1: Write failing global prompt test**

Add this test to `tests/test_message_lookup_tool.py` near the existing prompt assertions:

```python
def test_behavior_prompt_distinguishes_evidence_contract_from_memory_summary() -> None:
    prompt = build_agent_behavior_rules_prompt(workspace=Path("."))

    assert "Evidence Contract / allowed_evidence / current_truth" in prompt
    assert "Answer Candidate Contract" in prompt
    assert "insufficient_evidence_fallback=false" in prompt
    assert "已完成本轮召回和治理" in prompt
    assert "普通记忆摘要" in prompt
    assert "RECENT_CONTEXT.md" in prompt
    assert "禁止只凭 recall 摘要或 search 预览直接作答" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest \
  tests/test_message_lookup_tool.py::test_behavior_prompt_distinguishes_evidence_contract_from_memory_summary \
  -q -p no:cacheprovider
```

Expected: fail because the global evidence-type boundary is absent.

- [ ] **Step 3: Add one scoped boundary bullet to the history retrieval protocol**

In `prompts/agent.py`, under `### 历史检索协议` before the numbered waterfall, add:

```text
例外边界：普通记忆摘要和 `RECENT_CONTEXT.md` 只是候选上下文；但当本轮系统提示中存在明确的 Evidence Contract / allowed_evidence / current_truth / Answer Candidate Contract，且 `insufficient_evidence_fallback=false`、证据直接回答用户问题时，表示已完成本轮召回和治理，应直接基于该 contract 回答，不要重新启动历史检索。
```

- [ ] **Step 4: Run targeted prompt test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest \
  tests/test_message_lookup_tool.py::test_behavior_prompt_distinguishes_evidence_contract_from_memory_summary \
  -q -p no:cacheprovider
```

Expected: pass.

---

### Task 3: Post-Check Shadow Failure Classification

**Files:**
- Modify: `memory2/eval_answer_post_check.py:8-178`
- Test: `tests/test_memory_answer_post_check.py`

**Interfaces:**
- Consumes: `build_answer_post_check_shadow(answer: str, answer_contract: Mapping[str, object], context_memory_ids: Sequence[str]) -> AnswerPostCheckShadow`
- Produces: private structured flags and retry reasons without exposing raw answers.

- [ ] **Step 1: Write failing tests for DSML/tool markup and meta-action final answers**

Add these tests to `tests/test_memory_answer_post_check.py`:

```python
def _answerable_contract() -> dict[str, object]:
    return {
        "production_safe_evidence_contract": True,
        "allowed_evidence_ids": ["m-current"],
        "likely_relevant_evidence_ids": ["m-current"],
        "insufficient_evidence_fallback": False,
        "answer_candidate_contract": {
            "enabled": True,
            "current_truth_count": 1,
            "must_include_term_count": 1,
            "forbidden_old_value_count": 0,
            "language_requirement": "match_user_language",
        },
        "answer_score": {
            "expected_contains_miss_count": 1,
            "expected_any_miss_count": 0,
            "language_passed": True,
        },
    }


def test_post_check_flags_dsml_tool_markup_final_answer() -> None:
    shadow = build_answer_post_check_shadow(
        "我先查一下。<｜｜DSML｜｜tool_calls><｜｜DSML｜｜invoke name=\"read_file\">",
        _answerable_contract(),
        ["m-current"],
    )

    payload = answer_post_check_shadow_to_dict(shadow)
    assert payload["dsml_tool_markup_in_final_answer"] is True
    assert payload["tool_markup_in_final_answer"] is True
    assert payload["meta_action_final_answer"] is True
    assert payload["answerable_evidence_contract_ignored"] is True
    assert "dsml_tool_markup_in_final_answer" in payload["retry_reasons"]
    assert "tool_markup_in_final_answer" in payload["retry_reasons"]
    assert "meta_action_final_answer" in payload["retry_reasons"]
    assert "answerable_evidence_contract_ignored" in payload["retry_reasons"]
    assert "tool_calls><" not in str(payload)


def test_post_check_flags_plain_meta_action_without_raw_answer_leak() -> None:
    shadow = build_answer_post_check_shadow(
        "先翻一下记忆文件核实“上次的回答方式”具体指什么。",
        _answerable_contract(),
        ["m-current"],
    )

    payload = answer_post_check_shadow_to_dict(shadow)
    assert payload["meta_action_final_answer"] is True
    assert payload["answerable_evidence_contract_ignored"] is True
    assert "meta_action_final_answer" in payload["retry_reasons"]
    assert "answerable_evidence_contract_ignored" in payload["retry_reasons"]
    assert "先翻一下" not in str(payload)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest \
  tests/test_memory_answer_post_check.py::test_post_check_flags_dsml_tool_markup_final_answer \
  tests/test_memory_answer_post_check.py::test_post_check_flags_plain_meta_action_without_raw_answer_leak \
  -q -p no:cacheprovider
```

Expected: fail because the new fields and retry reasons do not exist.

- [ ] **Step 3: Extend `AnswerPostCheckShadow` dataclass**

Add boolean fields with defaults:

```python
    tool_markup_in_final_answer: bool = False
    dsml_tool_markup_in_final_answer: bool = False
    meta_action_final_answer: bool = False
    answerable_evidence_contract_ignored: bool = False
```

- [ ] **Step 4: Add private detectors**

Add helpers near `_mentions_insufficient_evidence`:

```python
def _contains_dsml_tool_markup(answer: str) -> bool:
    lowered = answer.lower()
    return "dsml" in lowered and ("tool_calls" in lowered or "invoke" in lowered)


def _contains_tool_markup(answer: str) -> bool:
    lowered = answer.lower()
    markers = (
        "<read_file",
        "</read_file",
        "<tool",
        "</tool",
        "<search",
        "</search",
        "tool_calls",
        "invoke name=",
        "read_file>",
    )
    return any(marker in lowered for marker in markers) or _contains_dsml_tool_markup(answer)


def _is_meta_action_final_answer(answer: str) -> bool:
    stripped = answer.strip()
    if not stripped:
        return False
    markers = (
        "我先查",
        "先查",
        "我先翻",
        "先翻",
        "我需要先查",
        "需要先查",
        "核实一下",
        "先核实",
        "确认一下",
        "看一下记忆",
        "查一下记忆",
        "翻一下记忆",
    )
    return any(marker in stripped for marker in markers)


def _answerable_contract_ignored(
    *,
    candidate_enabled: bool,
    expected_fallback: bool,
    answer: str,
) -> bool:
    return (
        candidate_enabled
        and not expected_fallback
        and (_contains_tool_markup(answer) or _is_meta_action_final_answer(answer))
    )
```

- [ ] **Step 5: Wire detectors into retry reasons and dict output**

Inside `build_answer_post_check_shadow`, after `boundary_mentions`, compute:

```python
    dsml_tool_markup = _contains_dsml_tool_markup(answer)
    tool_markup = _contains_tool_markup(answer)
    meta_action = _is_meta_action_final_answer(answer)
    contract_ignored = _answerable_contract_ignored(
        candidate_enabled=candidate_enabled,
        expected_fallback=expected_fallback,
        answer=answer,
    )
```

Append retry reasons after existing answer-score reasons:

```python
    if dsml_tool_markup:
        retry_reasons.append("dsml_tool_markup_in_final_answer")
    if tool_markup:
        retry_reasons.append("tool_markup_in_final_answer")
    if meta_action:
        retry_reasons.append("meta_action_final_answer")
    if contract_ignored:
        retry_reasons.append("answerable_evidence_contract_ignored")
```

Pass booleans into `AnswerPostCheckShadow(...)`, including the non-production-safe early return with all four fields `False`.

In `answer_post_check_shadow_to_dict`, add:

```python
        "tool_markup_in_final_answer": shadow.tool_markup_in_final_answer,
        "dsml_tool_markup_in_final_answer": shadow.dsml_tool_markup_in_final_answer,
        "meta_action_final_answer": shadow.meta_action_final_answer,
        "answerable_evidence_contract_ignored": shadow.answerable_evidence_contract_ignored,
```

- [ ] **Step 6: Run post-check tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest \
  tests/test_memory_answer_post_check.py -q -p no:cacheprovider
```

Expected: all tests in the file pass.

---

### Task 4: Local Regression Suite

**Files:**
- Modify only if tests expose failures in files touched by Tasks 1-3.

**Interfaces:**
- Consumes: all changed code from Tasks 1-3.
- Produces: verified local regression signal before real LLM spend.

- [ ] **Step 1: Run focused regression suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest \
  tests/test_memory_system_path_safe_version_contract.py \
  tests/test_memory_answer_post_check.py \
  tests/test_message_lookup_tool.py \
  tests/test_memory_system_path_safe_version_eval.py \
  -q -p no:cacheprovider
```

Expected: all selected tests pass.

- [ ] **Step 2: Run compile check**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python -m compileall \
  memory2/system_path_safe_version_contract.py \
  memory2/eval_answer_post_check.py \
  prompts/agent.py \
  tests/test_memory_system_path_safe_version_contract.py \
  tests/test_memory_answer_post_check.py \
  tests/test_message_lookup_tool.py
```

Expected: exit code `0`.

---

### Task 5: Real LLM Gates and Documentation

**Files:**
- Create or modify: `my_md/memory_optimization/16-evidence-contract-conflict-governance.md`
- Read-only input: `my_md/memory_optimization/eval_reports/p6o29_work_persona_medium_real_v1/system_path_safe_version_eval.json`

**Interfaces:**
- Consumes: existing CLI `scripts/run_memory_system_path_safe_version_eval.py`
- Produces: targeted and medium real LLM reports plus Markdown summary.

- [ ] **Step 1: Run targeted hard-slice real LLM gate**

Use the existing system-path CLI with work persona and guided retry shadow. The CLI has no direct case-id filter, so run the smallest deterministic hard slice that includes all three failed case ids and extract only the target rows from the report. For the standard case pack, hard limit `20` covers variant `01` and `02` for all 10 scenarios, including `hard_graph_bridge_01`, `hard_version_chain_01`, and `hard_preference_recall_02`.

Before the real LLM run, verify the target ids are present:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python -c "from memory2.eval_quantitative_cases import build_quantitative_eval_cases; ids=[c.id for c in build_quantitative_eval_cases('hard', limit=20)]; targets={'hard_graph_bridge_01','hard_version_chain_01','hard_preference_recall_02'}; print([i for i in ids if i in targets]); raise SystemExit(0 if targets <= set(ids) else 1)"
```

Expected: prints all three target ids and exits `0`.

Run:

```bash
uv run python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace /tmp/akashic-p6o30-contract-conflict-targeted-workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o30_contract_conflict_targeted_real_v1 \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --enable-real-llm \
  --balanced-small \
  --common-limit 0 \
  --hard-limit 20 \
  --modes safe_version_replace_guided_with_retry_shadow \
  --persona-mode work \
  --timeout-s 60 \
  --checkpoint-jsonl /tmp/akashic-p6o30-contract-conflict-targeted-checkpoint.jsonl \
  --early-infra-abort-count 5 \
  --early-infra-abort-rate 0.5 \
  --allow-infra-blocked-exit-zero
```

Expected hard-slice gate:
- provider errors: `0`
- timeouts: `0`
- target case ids present: `hard_graph_bridge_01`, `hard_version_chain_01`, `hard_preference_recall_02`
- target answer success: target `3/3`.
- If target answer success is below `3/3`, stop for failed-case analysis before medium unless the failure is provider/infra and the report is explicitly marked blocked.

- [ ] **Step 2: Run 40-case medium real LLM regression gate**

Run:

```bash
uv run python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace /tmp/akashic-p6o31-contract-conflict-medium-workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o31_contract_conflict_medium_real_v1 \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --enable-real-llm \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --modes safe_version_replace_guided_with_retry_shadow \
  --persona-mode work \
  --timeout-s 60 \
  --checkpoint-jsonl /tmp/akashic-p6o31-contract-conflict-medium-checkpoint.jsonl \
  --early-infra-abort-count 5 \
  --early-infra-abort-rate 0.5 \
  --allow-infra-blocked-exit-zero
```

Expected gate:
- provider errors: `0`
- timeouts: `0`
- answer success should be at least prior best `37/40 = 92.5%`; any lower result requires failed-case analysis before commit.
- grounding remains `100%`.
- forbidden remains `0%`.
- retry reasons include new classifications if DSML/meta-action still occurs.

- [ ] **Step 3: Record method, data, and conclusion**

Create or update `my_md/memory_optimization/16-evidence-contract-conflict-governance.md` with:

```markdown
# Evidence Contract Conflict Governance

## Problem

The remaining P6o29 failures were not retrieval failures. They were answer-layer conflicts where global history retrieval rules caused the model to restart memory lookup despite sufficient governed Evidence Contract data.

## Changes

- Contract completion rule in `memory2/system_path_safe_version_contract.py`.
- Global evidence-type boundary in `prompts/agent.py`.
- Post-check retry classifications in `memory2/eval_answer_post_check.py`.

## Test Method

[list exact pytest and real LLM commands]

## Data

| run | scope | cases | answer | grounding | forbidden | provider errors | timeouts | key retry reasons |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| P6o29 baseline | medium real LLM | 40 | 37/40 = 92.5% | 100.0% | 0.0% | 0 | 0 | required_terms_missing: 3, answer_choice_group_missing: 1 |
| P6o30 | targeted real LLM | [fill] | [fill] | [fill] | [fill] | [fill] | [fill] | [fill] |
| P6o31 | medium real LLM | 40 | [fill] | [fill] | [fill] | [fill] | [fill] | [fill] |

## Failed Case Analysis

[record remaining failures and whether they are DSML/tool markup, meta action, answer term miss, provider issue, or unrelated scorer miss]

## Conclusion

[state whether scheme C improved the targeted conflict family and whether medium regression gate passed]
```

- [ ] **Step 4: Final verification before commit**

Run:

```bash
git status --short
git diff -- memory2/system_path_safe_version_contract.py memory2/eval_answer_post_check.py prompts/agent.py tests/test_memory_system_path_safe_version_contract.py tests/test_memory_answer_post_check.py tests/test_message_lookup_tool.py my_md/memory_optimization/16-evidence-contract-conflict-governance.md
```

Expected:
- only intended files changed, plus real LLM report output dirs from this task;
- unrelated `p6o13_system_path_real_llm_validation_v1/` remains untouched.

- [ ] **Step 5: Commit**

Commit generated P6o30/P6o31 JSON and Markdown report directories only when the run completed or was explicitly blocked and the files are needed to audit the result. Do not add unrelated historical report directories.

Run:

```bash
git add memory2/system_path_safe_version_contract.py \
  memory2/eval_answer_post_check.py \
  prompts/agent.py \
  tests/test_memory_system_path_safe_version_contract.py \
  tests/test_memory_answer_post_check.py \
  tests/test_message_lookup_tool.py \
  my_md/memory_optimization/16-evidence-contract-conflict-governance.md \
  my_md/memory_optimization/eval_reports/p6o30_contract_conflict_targeted_real_v1 \
  my_md/memory_optimization/eval_reports/p6o31_contract_conflict_medium_real_v1
git commit -m "fix(memory): govern answerable evidence contract conflicts"
```

Expected: commit succeeds.

---

## Self-Review

- Spec coverage: The plan covers contract-local rule, global evidence boundary, post-check classification, local tests, real LLM targeted and medium gates, and documentation.
- Placeholder scan: No `TBD` / `TODO` placeholders remain. Fill markers in the documentation template are intentionally part of Task 5 execution output and must be replaced before commit.
- Type consistency: New post-check fields are dataclass booleans, constructor values, dict keys, and tests all use identical names.
- Scope check: The plan is focused on one failure family and avoids broad memory retrieval refactors or production retry changes.
