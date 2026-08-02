# P6o35 Retry-If-Needed Shadow Telemetry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add and validate a narrow eval-only retry-if-needed telemetry surface for the current best answer contract, without changing prompt behavior or enabling real retry.

**Architecture:** Keep `safe_version_replace_guided_with_retry_shadow` prompt, mode, and single LLM call behavior unchanged. Extend post-check shadow output with separate retry-if-needed fields that distinguish actionable answer-shape/answer-selection misses from blocked safety/context failures, so later real retry can be designed from high-precision telemetry instead of the broad `needs_retry` bucket.

**Tech Stack:** Python, pytest, `scripts/run_memory_system_path_safe_version_eval.py`, real LLM eval with checkpoint JSONL, sanitized markdown/JSON reports.

## Global Constraints

- Do not enable real production retry.
- Do not add a second LLM call.
- Do not change current best prompt wording or prompt variant.
- Do not change production default `safe_version_governed_mode=off`.
- Do not change recall, memory write, fallback, graph/all-on, or global system prompt behavior.
- Normal reports must not include raw prompt, raw answer, raw query, memory summary, or conversation log.
- New telemetry fields may contain only booleans, counts, stable reason codes, and sanitized memory ids already allowed in current reports.
- Debug raw answers are allowed only under explicit local `--answer-debug-dir`.
- The current best remains `safe_version_replace_guided_with_retry_shadow` with `persona-mode work`.

---

### Task 1: Add Narrow Retry-If-Needed Shadow Fields

**Files:**
- Modify: `memory2/eval_answer_post_check.py`
- Modify: `memory2/eval_system_path_safe_version.py`
- Test: `tests/test_memory_answer_post_check.py`
- Test: `tests/test_memory_system_path_safe_version_eval.py`

**Interfaces:**
- Consumes: existing `AnswerPostCheckShadow.needs_retry` and `retry_reasons`.
- Produces: `retry_if_needed_shadow_enabled`, `retry_if_needed_eligible`, `retry_if_needed_reasons`, and `retry_if_needed_blocked_reasons`.

- [ ] **Step 1: Add failing post-check test for actionable retry reasons**

In `tests/test_memory_answer_post_check.py`, add:

```python
def test_post_check_retry_if_needed_marks_actionable_answer_misses() -> None:
    shadow = build_answer_post_check_shadow(
        "我先查一下。<｜｜DSML｜｜tool_calls><｜｜DSML｜｜invoke name=\"read_file\">",
        {
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
                "expected_any_miss_count": 1,
                "language_passed": True,
                "forbidden_contains_violation_count": 0,
            },
        },
        ["m-current"],
    )

    payload = answer_post_check_shadow_to_dict(shadow)
    assert payload["retry_if_needed_shadow_enabled"] is True
    assert payload["retry_if_needed_eligible"] is True
    assert payload["retry_if_needed_reasons"] == [
        "required_terms_missing",
        "answer_choice_group_missing",
        "dsml_tool_markup_in_final_answer",
        "tool_markup_in_final_answer",
        "meta_action_final_answer",
        "answerable_evidence_contract_ignored",
    ]
    assert payload["retry_if_needed_blocked_reasons"] == []
```

- [ ] **Step 2: Add failing post-check test for blocked safety reasons**

In `tests/test_memory_answer_post_check.py`, add:

```python
def test_post_check_retry_if_needed_blocks_forbidden_answer_term() -> None:
    shadow = build_answer_post_check_shadow(
        "用户旧偏好 unittest。",
        {
            "production_safe_evidence_contract": True,
            "allowed_evidence_ids": ["m-current"],
            "likely_relevant_evidence_ids": ["m-current"],
            "insufficient_evidence_fallback": False,
            "answer_candidate_contract": {
                "enabled": True,
                "current_truth_count": 1,
                "must_include_term_count": 1,
                "forbidden_old_value_count": 1,
                "language_requirement": "match_user_language",
            },
            "answer_score": {
                "expected_contains_miss_count": 0,
                "expected_any_miss_count": 0,
                "language_passed": True,
                "forbidden_contains_violation_count": 1,
            },
        },
        ["m-current"],
    )

    payload = answer_post_check_shadow_to_dict(shadow)
    assert payload["retry_if_needed_shadow_enabled"] is True
    assert payload["retry_if_needed_eligible"] is False
    assert payload["retry_if_needed_reasons"] == []
    assert payload["retry_if_needed_blocked_reasons"] == [
        "forbidden_answer_term_found"
    ]
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```bash
pytest tests/test_memory_answer_post_check.py -q
```

Expected: failure because the four retry-if-needed fields do not exist yet.

- [ ] **Step 4: Implement telemetry fields**

In `memory2/eval_answer_post_check.py`, extend `AnswerPostCheckShadow` with:

```python
retry_if_needed_shadow_enabled: bool = False
retry_if_needed_eligible: bool = False
retry_if_needed_reasons: tuple[str, ...] = ()
retry_if_needed_blocked_reasons: tuple[str, ...] = ()
```

Compute:

```python
forbidden_answer_term_found = (
    candidate_enabled
    and int(score_map.get("forbidden_contains_violation_count", 0) or 0) > 0
)
```

Add `forbidden_answer_term_found` to broad `retry_reasons`, but classify it as blocked for narrow retry-if-needed.

Use this classification:

```python
actionable_reasons = (
    "required_terms_missing",
    "answer_choice_group_missing",
    "language_requirement_failed",
    "dsml_tool_markup_in_final_answer",
    "tool_markup_in_final_answer",
    "meta_action_final_answer",
    "answerable_evidence_contract_ignored",
)
blocked_reasons = (
    "forbidden_answer_term_found",
    "forbidden_boundary_included",
    "forbidden_boundary_mentioned",
    "missing_likely_relevant_context",
    "stale_evidence_included",
    "conflict_evidence_included",
    "insufficient_evidence_fallback_missing",
)
```

Set:

```python
retry_if_needed_shadow_enabled = candidate_enabled
retry_if_needed_reasons = tuple(reason for reason in retry_reasons if reason in actionable_reasons)
retry_if_needed_blocked_reasons = tuple(reason for reason in retry_reasons if reason in blocked_reasons)
retry_if_needed_eligible = (
    retry_if_needed_shadow_enabled
    and bool(retry_if_needed_reasons)
    and not bool(retry_if_needed_blocked_reasons)
)
```

Add the four fields to `answer_post_check_shadow_to_dict()`.

- [ ] **Step 5: Pass forbidden score into post-check**

In `memory2/eval_system_path_safe_version.py`, when building `answer_contract["answer_score"]` for `safe_version_replace_guided_with_retry_shadow` and `safe_version_replace_schema_first_shadow`, include:

```python
"forbidden_contains_violation_count": score.forbidden_contains_violation_count,
```

Do not add any second provider call.

- [ ] **Step 6: Add runner shape/privacy test**

In `tests/test_memory_system_path_safe_version_eval.py`, extend the existing guided retry shadow fake-provider test or add a new one to assert each retry-shadow row contains:

```python
post = row["post_check_shadow"]
assert "retry_if_needed_shadow_enabled" in post
assert "retry_if_needed_eligible" in post
assert "retry_if_needed_reasons" in post
assert "retry_if_needed_blocked_reasons" in post
assert "raw_answer" not in str(post)
assert "raw_prompt" not in str(post)
```

For fake-provider run shape, assert:

```python
assert payload["metrics"]["mode_summaries"]["safe_version_replace_guided_with_retry_shadow"]["case_count"] == 2
assert payload["metrics"]["mode_summaries"]["safe_version_replace_guided_with_retry_shadow"]["answer_candidate_contract_enabled_rate"] == 100.0
```

- [ ] **Step 7: Run focused tests and verify GREEN**

Run:

```bash
pytest \
  tests/test_memory_answer_post_check.py \
  tests/test_memory_system_path_safe_version_eval.py \
  -q
```

Expected: all selected tests pass.

### Task 2: Run P6o35 Telemetry Validation Gates

**Files:**
- Create: `my_md/memory_optimization/20-p6o35-retry-if-needed-shadow-telemetry.md`
- Modify: `my_md/memory_optimization/README.md`
- Create: `my_md/memory_optimization/eval_reports/p6o35_retry_if_needed_shadow_fake_v1/`
- Create: `my_md/memory_optimization/eval_reports/p6o35_retry_if_needed_shadow_real_r3_v1_<timestamp>/`

**Interfaces:**
- Consumes: new telemetry fields from Task 1.
- Produces: fake smoke report, real LLM R3 telemetry report, documented conclusion and next-step recommendation.

- [ ] **Step 1: Run fake-provider smoke**

Run:

```bash
python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace /tmp/akashic-p6o35-fake-workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o35_retry_if_needed_shadow_fake_v1 \
  --fake-provider \
  --balanced-small \
  --common-limit 2 \
  --hard-limit 2 \
  --modes safe_version_replace_guided_with_retry_shadow \
  --persona-mode work
```

Expected:
- exit `0`
- `unique_case_count=4`
- `case_count=4`
- exact mode set is only `safe_version_replace_guided_with_retry_shadow`
- `answer_candidate_contract_enabled_rate=100.0`
- retry-if-needed fields exist on all rows
- `fake_provider_enabled=true`, `real_llm_enabled=false`

- [ ] **Step 2: Run real LLM R3 telemetry validation**

Create a timestamped run id:

```bash
RUN_ID="p6o35_retry_if_needed_shadow_real_r3_v1_$(date +%Y%m%d_%H%M%S)"
```

Run:

```bash
python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace "/tmp/akashic-${RUN_ID}-workspace" \
  --out-dir "my_md/memory_optimization/eval_reports/${RUN_ID}" \
  --enable-real-llm \
  --balanced-small \
  --common-limit 40 \
  --hard-limit 40 \
  --modes safe_version_replace_guided_with_retry_shadow \
  --persona-mode work \
  --repeats 3 \
  --timeout-s 60 \
  --checkpoint-jsonl "/tmp/akashic-${RUN_ID}.jsonl" \
  --early-infra-abort-count 20 \
  --early-infra-abort-rate 0.5 \
  --answer-debug-dir "my_md/memory_optimization/eval_reports/${RUN_ID}/answer_debug"
```

Expected:
- exit `0`
- exact mode set is only `safe_version_replace_guided_with_retry_shadow`
- `unique_case_count=80`
- `case_count=240`
- `repeat_count=3`
- `real_llm_enabled=true`
- `fake_provider_enabled=false`
- `provider_error_count=0`
- `timeout_count=0`
- `malformed_checkpoint_line_count=0`
- no `blocked_status.json`

- [ ] **Step 3: Analyze telemetry and stability**

Print and record:
- aggregate answer, grounding, forbidden, token, latency
- per-repeat answer/grounding/forbidden
- broad `would_retry_count` and reason counts
- narrow `retry_if_needed_eligible` row count
- narrow actionable reason row counts and reason counts
- blocked reason row counts and reason counts
- overlap-deduped rows for `answerable_evidence_contract_ignored`, tool markup, DSML markup, and meta action
- flipped case count across repeats
- case-level interesting rows with debug file path only

Gate interpretation:
- infra gate passes only when provider errors, timeouts, and malformed checkpoint lines are all `0`
- safety gate passes only when forbidden rate is `0.0%`
- telemetry gate passes only when retry-if-needed fields are present on all rows and contain no raw text
- eligibility gate passes only when forbidden-answer-term rows, if any, are blocked and not eligible
- performance is interpreted against P6o34 baseline, but P6o35 is not a prompt-performance experiment
- production readiness remains `false`; real retry remains deferred

- [ ] **Step 4: Document method, data, and conclusion**

Create `my_md/memory_optimization/20-p6o35-retry-if-needed-shadow-telemetry.md` with:
- plan path and review revisions
- code diff summary
- fake smoke command and metrics
- real run command and artifacts
- real run aggregate table
- repeat table
- retry-if-needed telemetry table
- blocked safety/context table
- flipped/interesting-row table using debug file paths but not copying raw answers into the normal report
- gate decision
- conclusion on whether telemetry is clean enough to design a future narrow real retry

Append one README bullet under the memory optimization phase list summarizing P6o35.

- [ ] **Step 5: Final verification**

Run:

```bash
pytest \
  tests/test_memory_answer_post_check.py \
  tests/test_memory_system_path_safe_version_eval.py \
  -q
git status --short
```

Expected:
- tests pass
- only P6o35 code, plan, docs, and report artifacts are modified/untracked, plus the pre-existing unrelated `p6o13_system_path_real_llm_validation_v1/` remains untouched.

## Self-Review

- Spec coverage: The revised plan separates broad `needs_retry` from narrow retry-if-needed eligibility, preserves prompt and single-call behavior, independently blocks forbidden failures, validates privacy, and records data/conclusion.
- Placeholder scan: No `TBD`, `TODO`, or unspecified test steps remain.
- Type consistency: The four new fields are present in dataclass, dict output, runner rows, fake smoke, and real telemetry docs.
