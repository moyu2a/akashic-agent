# Memory P6o-19 Answer Candidate Retry Shadow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an eval-only P6o-19 system-path mode that tests whether an answer-candidate contract plus post-check retry shadow reduces cases where retrieved memory evidence is correct but the LLM selects or phrases the answer incorrectly.

**Architecture:** Keep production defaults off and build on the existing safe-version governed system-path path. Add a structured answer-candidate layer to `memory2/system_path_safe_version_contract.py`, propagate it through sanitized contract dictionaries, extend `memory2/eval_answer_post_check.py` to classify would-retry reasons from answer scoring signals, and expose a new eval mode in `memory2/eval_system_path_safe_version.py`.

**Tech Stack:** Python dataclasses, existing `AgentLoop.process_direct()` system-path eval harness, pytest/pytest-asyncio, JSON/Markdown report writers, existing fake-provider and real-LLM checkpoint flow.

## Global Constraints

- Worktree: `/home/jjh/git_work/akashic-agent/.worktrees/memory-next`.
- Production default remains `MemoryConfig.safe_version_governed_mode = "off"`.
- No graph-all-on, no recall expansion, no production retry/fallback execution, no production memory write changes, no global system prompt change.
- Reports must not include raw query, raw prompt, session text, memory summary, full answer, API key, Authorization, or secret values.
- P6o-19 real LLM work must run fake smoke first, then checkpointed real run, checkpoint rebuild, privacy scan, and `git diff --check`.
- Protected untracked directory must not be deleted or overwritten: `my_md/memory_optimization/eval_reports/p6o13_system_path_real_llm_validation_v1/`.

---

## Execution Status

- [x] Task 1: Answer Candidate Contract.
- [x] Task 2: Retry Shadow Classification.
- [x] Task 3: P6o-19 Eval Mode and Report Metrics.
- [x] Task 4: P6o-19 Gate Report.
- [x] Task 5: Fake Smoke, Documentation, and Verification.
- [x] Task 6: Code review was requested. The first review inspected the wrong checkout and was invalid; the corrected review attempt failed with provider `403 INSUFFICIENT_BALANCE`, so no external review feedback was available to apply.
- [x] Task 7: No review fixes were applied because no valid review feedback was produced.
- [x] Task 8: Final focused tests, compileall, P6o-19 gate rerun, privacy scan, and `git diff --check` were run.

---

## File Structure

- Modify `memory2/system_path_safe_version_contract.py`
  - Add `AnswerCandidateContract`.
  - Build prompt-only answer candidates from likely relevant active evidence plus active version ids and stale/deleted ids.
  - Render an answer-candidate block only for the new P6o-19 mode.
  - Include only report-safe candidate counts and reason labels in `system_path_contract_to_dict()` report paths; raw candidate text stays prompt-only and raw terms are not serialized into committed reports.
- Modify `memory2/eval_answer_post_check.py`
  - Add scoring-aware retry shadow fields and reason classification.
  - Keep existing evidence-boundary retry reasons unchanged.
  - Use `score_answer_text()` miss counts as authoritative retry signals; do not classify retry from raw substring matching.
- Modify `memory2/eval_system_path_safe_version.py`
  - Add mode `safe_version_replace_guided_with_retry_shadow`.
  - Attach answer score fields to the post-check contract for this mode only.
  - Add mode summary metrics for retry shadow capture.
  - Add a sanitizer for report-safe `answer_candidate_contract` fields.
- Modify `scripts/run_memory_system_path_safe_version_eval.py`
  - No new flags required; the existing `--modes` option will accept the new mode.
- Modify tests:
  - `tests/test_memory_system_path_safe_version_contract.py`
  - `tests/test_memory_system_path_safe_version_eval.py`
  - Add or modify `tests/test_memory_answer_post_check.py` if it exists; otherwise add `tests/test_memory_answer_post_check.py`.
- Modify docs after execution:
  - `my_md/memory_optimization/README.md`
  - `progress.md`
  - Create `my_md/memory_optimization/eval_reports/p6o19_answer_candidate_retry_shadow_v1/p6o19_answer_candidate_retry_shadow_report.md`

---

### Task 1: Answer Candidate Contract

**Files:**
- Modify: `memory2/system_path_safe_version_contract.py`
- Test: `tests/test_memory_system_path_safe_version_contract.py`

**Interfaces:**
- Produces dataclass:
  - `AnswerCandidateContract`
  - fields:
    - `enabled: bool`
    - `current_truth_ids: tuple[str, ...]`
    - `current_truth_lines: tuple[str, ...]`
    - `must_include_term_count: int`
    - `forbidden_old_value_ids: tuple[str, ...]`
    - `language_requirement: str`
    - `candidate_reason: str`
- Extends `SystemPathEvidenceContract` with:
  - `answer_candidate_contract: AnswerCandidateContract`
- Adds prompt variant:
  - `guided_retry_shadow`

- [ ] **Step 1: Write failing tests for candidate contract structure**

Add this test to `tests/test_memory_system_path_safe_version_contract.py`:

```python
def test_answer_candidate_contract_extracts_current_truth_and_terms() -> None:
    current = _item("m-current", "用户当前默认测试框架是 pytest。")
    old = _item("m-old", "用户旧测试框架是 nose。", status="superseded")

    result = build_system_path_safe_version_contract(
        query="我现在默认用什么测试框架？",
        baseline_items=[old, current],
        route_trace={
            "candidates_by_lane": {
                "semantic": [old, current],
                "keyword": [],
                "provenance": [],
                "graph": [],
            }
        },
        replacements=[
            {
                "old_item_id": "m-old",
                "new_item_id": "m-current",
                "old_memory_type": "preference",
                "new_memory_type": "preference",
                "old_summary": "用户旧测试框架是 nose。",
                "new_summary": "用户当前默认测试框架是 pytest。",
                "old_source_ref": "telegram:1:old",
                "new_source_ref": "telegram:1:new",
            }
        ],
        top_k=8,
        answer_guidance_enabled=True,
        answer_prompt_variant="guided_retry_shadow",
    )

    candidate = result.contract.answer_candidate_contract
    assert candidate.enabled is True
    assert candidate.current_truth_ids == ("m-current",)
    assert candidate.current_truth_lines == ("用户当前默认测试框架是 pytest。",)
    assert candidate.must_include_term_count == 1
    assert candidate.forbidden_old_value_ids == ("m-old",)
    assert candidate.language_requirement == "match_user_language"
    assert candidate.candidate_reason == "safe_version_guided_retry_shadow"
```

- [ ] **Step 2: Verify the test fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_memory_system_path_safe_version_contract.py::test_answer_candidate_contract_extracts_current_truth_and_terms -q -p no:cacheprovider
```

Expected: FAIL because `guided_retry_shadow` and `answer_candidate_contract` do not exist.

- [ ] **Step 3: Add minimal dataclass and builder logic**

In `memory2/system_path_safe_version_contract.py`:

```python
@dataclass(frozen=True)
class AnswerCandidateContract:
    enabled: bool
    current_truth_ids: tuple[str, ...]
    current_truth_lines: tuple[str, ...]
    must_include_term_count: int
    forbidden_old_value_ids: tuple[str, ...]
    language_requirement: str
    candidate_reason: str
```

Extend `SAFE_VERSION_ANSWER_PROMPT_VARIANTS` with `"guided_retry_shadow"`.

Add `answer_candidate_contract: AnswerCandidateContract` to `SystemPathEvidenceContract`.

Build it inside `build_system_path_safe_version_contract()`:

```python
answer_candidate_contract = _build_answer_candidate_contract(
    enabled=prompt_variant == "guided_retry_shadow",
    active_ids=active_ids,
    likely_ids=likely_ids,
    stale_ids=stale_ids,
    deleted_ids=deleted_ids,
    items_by_id=items_by_id,
)
```

Pass `answer_candidate_contract=answer_candidate_contract` into `SystemPathEvidenceContract`.

Add helper:

```python
def _build_answer_candidate_contract(
    *,
    enabled: bool,
    active_ids: Sequence[str],
    likely_ids: Sequence[str],
    stale_ids: Sequence[str],
    deleted_ids: Sequence[str],
    items_by_id: Mapping[str, Mapping[str, object]],
) -> AnswerCandidateContract:
    if not enabled:
        return AnswerCandidateContract(
            enabled=False,
            current_truth_ids=(),
            current_truth_lines=(),
            must_include_term_count=0,
            forbidden_old_value_ids=(),
            language_requirement="",
            candidate_reason="disabled",
        )
    likely_set = set(likely_ids)
    current_ids = tuple(item_id for item_id in active_ids if item_id in likely_set)
    current_lines = tuple(
        str(items_by_id[item_id].get("summary") or "").strip()
        for item_id in current_ids
        if item_id in items_by_id and str(items_by_id[item_id].get("summary") or "").strip()
    )
    return AnswerCandidateContract(
        enabled=True,
        current_truth_ids=current_ids,
        current_truth_lines=current_lines,
        must_include_term_count=len(current_lines),
        forbidden_old_value_ids=tuple(_dedupe((*stale_ids, *deleted_ids))),
        language_requirement="match_user_language",
        candidate_reason="safe_version_guided_retry_shadow",
    )
```

Do not add a raw term extractor in this task. The prompt may show `current_truth_lines`, but committed JSON/Markdown reports must contain only counts and ids that are already present in existing sanitized contract reports.

- [ ] **Step 4: Verify the contract test passes**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_memory_system_path_safe_version_contract.py::test_answer_candidate_contract_extracts_current_truth_and_terms -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 5: Write failing tests for rendering and privacy**

Add this test:

```python
def test_guided_retry_shadow_renders_prompt_contract_without_raw_ids() -> None:
    result = build_system_path_safe_version_contract(
        query="测试偏好是什么？",
        baseline_items=[
            _item("m-current", "用户当前偏好使用 pytest。"),
            _item("m-old", "用户旧偏好使用 nose。", status="superseded"),
        ],
        route_trace={
            "candidates_by_lane": {
                "semantic": [
                    _item("m-current", "用户当前偏好使用 pytest。"),
                    _item("m-old", "用户旧偏好使用 nose。", status="superseded"),
                ],
                "keyword": [],
                "provenance": [],
                "graph": [],
            }
        },
        replacements=[
            {
                "old_item_id": "m-old",
                "new_item_id": "m-current",
                "old_memory_type": "preference",
                "new_memory_type": "preference",
                "old_summary": "用户旧偏好使用 nose。",
                "new_summary": "用户当前偏好使用 pytest。",
                "old_source_ref": "telegram:1:old",
                "new_source_ref": "telegram:1:new",
            }
        ],
        answer_guidance_enabled=True,
        answer_prompt_variant="guided_retry_shadow",
    )

    text = result.text_block
    payload = system_path_contract_to_dict(
        result.contract,
        answer_guidance_enabled=True,
    )

    assert "Answer Candidate Contract:" in text
    assert "current_truth:" in text
    assert "must_include_term_count:" in text
    assert "用户当前偏好使用 pytest。" in text
    assert "m-current" not in text
    assert "m-old" not in text
    assert payload["answer_candidate_contract"]["enabled"] is True
    assert payload["answer_candidate_contract"]["current_truth_count"] == 1
    assert payload["answer_candidate_contract"]["must_include_term_count"] == 1
    assert "current_truth_lines" not in payload["answer_candidate_contract"]
    assert "must_include_terms" not in payload["answer_candidate_contract"]
    assert "raw_prompt" not in payload
    assert "raw_answer" not in payload
```

- [ ] **Step 6: Verify the rendering test fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_memory_system_path_safe_version_contract.py::test_guided_retry_shadow_renders_prompt_contract_without_raw_ids -q -p no:cacheprovider
```

Expected: FAIL because rendering and serialization are missing.

- [ ] **Step 7: Implement rendering and serialization**

In `render_system_path_evidence_contract_block()`, add:

```python
    elif variant == "guided_retry_shadow":
        candidate = contract.answer_candidate_contract
        lines.extend(
            [
                "Answer Guidance:",
                "  Use allowed_evidence as the only source for the answer.",
                "  Use the Answer Candidate Contract to select the final answer.",
                "  Include the must_include_terms when they are supported by current_truth.",
                "  Answer in the user's language.",
                "Answer Candidate Contract:",
                "current_truth:",
                *_indent_lines(candidate.current_truth_lines),
                "must_include_term_count: "
                + str(candidate.must_include_term_count),
                "forbidden_old_value_count: "
                + str(len(candidate.forbidden_old_value_ids)),
                "language_requirement: " + candidate.language_requirement,
            ]
        )
```

In `system_path_contract_to_dict()`, add:

```python
        "answer_candidate_contract": {
            "enabled": contract.answer_candidate_contract.enabled,
            "current_truth_count": len(contract.answer_candidate_contract.current_truth_ids),
            "must_include_term_count": contract.answer_candidate_contract.must_include_term_count,
            "forbidden_old_value_count": len(contract.answer_candidate_contract.forbidden_old_value_ids),
            "language_requirement": contract.answer_candidate_contract.language_requirement,
            "candidate_reason": contract.answer_candidate_contract.candidate_reason,
        },
```

- [ ] **Step 8: Run focused contract tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_memory_system_path_safe_version_contract.py -q -p no:cacheprovider
```

Expected: all tests pass.

---

### Task 2: Retry Shadow Classification

**Files:**
- Modify: `memory2/eval_answer_post_check.py`
- Test: `tests/test_memory_answer_post_check.py`

**Interfaces:**
- Extends `AnswerPostCheckShadow` with:
  - `answer_candidate_contract_enabled: bool`
  - `required_terms_missing: bool`
  - `answer_choice_group_missing: bool`
  - `language_requirement_failed: bool`
- Consumes optional contract dict keys:
  - `answer_candidate_contract.enabled`
  - `answer_score.expected_contains_miss_count`
  - `answer_score.expected_any_miss_count`
  - `answer_score.language_passed`

- [ ] **Step 1: Add failing post-check tests**

Add to existing `tests/test_memory_answer_post_check.py`:

```python
from memory2.eval_answer_post_check import (
    answer_post_check_shadow_to_dict,
    build_answer_post_check_shadow,
)


def test_post_check_retry_shadow_flags_missing_required_terms() -> None:
    shadow = build_answer_post_check_shadow(
        "我建议继续使用 unittest。",
        {
            "production_safe_evidence_contract": True,
            "allowed_evidence_ids": ["m-current"],
            "likely_relevant_evidence_ids": ["m-current"],
            "answer_candidate_contract": {
                "enabled": True,
                "current_truth_count": 1,
                "must_include_term_count": 1,
                "forbidden_old_value_count": 1,
                "language_requirement": "match_user_language",
            },
            "answer_score": {
                "expected_contains_miss_count": 1,
                "expected_any_miss_count": 0,
                "language_passed": True,
            },
        },
        ["m-current"],
    )

    payload = answer_post_check_shadow_to_dict(shadow)
    assert payload["answer_candidate_contract_enabled"] is True
    assert payload["required_terms_missing"] is True
    assert payload["needs_retry"] is True
    assert "required_terms_missing" in payload["retry_reasons"]
```

Add:

```python
def test_post_check_retry_shadow_flags_language_failure() -> None:
    shadow = build_answer_post_check_shadow(
        "Use pytest.",
        {
            "production_safe_evidence_contract": True,
            "allowed_evidence_ids": ["m-current"],
            "likely_relevant_evidence_ids": ["m-current"],
            "answer_candidate_contract": {
                "enabled": True,
                "current_truth_count": 1,
                "must_include_term_count": 1,
                "forbidden_old_value_count": 0,
                "language_requirement": "match_user_language",
            },
            "answer_score": {
                "expected_contains_miss_count": 0,
                "expected_any_miss_count": 0,
                "language_passed": False,
            },
        },
        ["m-current"],
    )

    payload = answer_post_check_shadow_to_dict(shadow)
    assert payload["language_requirement_failed"] is True
    assert payload["needs_retry"] is True
    assert "language_requirement_failed" in payload["retry_reasons"]
```

- [ ] **Step 2: Verify the tests fail**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_memory_answer_post_check.py -q -p no:cacheprovider
```

Expected: FAIL because fields are missing.

- [ ] **Step 3: Implement scoring-aware retry reasons**

In `AnswerPostCheckShadow`, add:

```python
    answer_candidate_contract_enabled: bool = False
    required_terms_missing: bool = False
    answer_choice_group_missing: bool = False
    language_requirement_failed: bool = False
```

In `build_answer_post_check_shadow()`, after reading `expected_fallback`:

```python
    answer_candidate_contract = answer_contract.get("answer_candidate_contract")
    if isinstance(answer_candidate_contract, Mapping):
        candidate_enabled = bool(answer_candidate_contract.get("enabled"))
    else:
        candidate_enabled = False
    answer_score = answer_contract.get("answer_score")
    score_map = answer_score if isinstance(answer_score, Mapping) else {}
    required_terms_missing = (
        candidate_enabled
        and int(score_map.get("expected_contains_miss_count", 0) or 0) > 0
    )
    answer_choice_group_missing = (
        candidate_enabled
        and int(score_map.get("expected_any_miss_count", 0) or 0) > 0
    )
    language_failed = (
        candidate_enabled
        and "language_passed" in score_map
        and not bool(score_map.get("language_passed"))
    )
```

After existing retry reasons:

```python
    if required_terms_missing:
        retry_reasons.append("required_terms_missing")
    if answer_choice_group_missing:
        retry_reasons.append("answer_choice_group_missing")
    if language_failed:
        retry_reasons.append("language_requirement_failed")
```

Populate the new dataclass fields in both disabled and enabled returns.

In `answer_post_check_shadow_to_dict()`, add:

```python
        "answer_candidate_contract_enabled": shadow.answer_candidate_contract_enabled,
        "required_terms_missing": shadow.required_terms_missing,
        "answer_choice_group_missing": shadow.answer_choice_group_missing,
        "language_requirement_failed": shadow.language_requirement_failed,
```

- [ ] **Step 4: Run post-check tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_memory_answer_post_check.py -q -p no:cacheprovider
```

Expected: PASS.

---

### Task 3: P6o-19 Eval Mode and Report Metrics

**Files:**
- Modify: `memory2/eval_system_path_safe_version.py`
- Modify: `scripts/run_memory_system_path_safe_version_eval.py` only if CLI validation needs explicit help text.
- Test: `tests/test_memory_system_path_safe_version_eval.py`

**Interfaces:**
- Adds mode:
  - `safe_version_replace_guided_with_retry_shadow`
- Maps mode to:
  - `safe_version_governed_mode="replace"`
  - `safe_version_governed_replace_allowed=True`
  - `safe_version_answer_guidance_enabled=True`
  - `safe_version_answer_prompt_variant="guided_retry_shadow"`
- Adds report metrics:
  - per-row `post_check_shadow.retry_reasons`
  - mode summary `would_retry_count`
  - mode summary `retry_reason_counts`
  - mode summary `answer_candidate_contract_enabled_rate`

- [ ] **Step 1: Add failing CLI mode test**

Add this test to `tests/test_memory_system_path_safe_version_eval.py`:

```python
def test_system_path_safe_version_cli_supports_guided_retry_shadow_mode(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "out"
    workspace = tmp_path / "workspace"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_system_path_safe_version_eval.py",
            "--workspace",
            str(workspace),
            "--out-dir",
            str(out_dir),
            "--fake-provider",
            "--balanced-small",
            "--common-limit",
            "1",
            "--hard-limit",
            "1",
            "--modes",
            "safe_version_replace,safe_version_replace_guided,safe_version_replace_guided_with_retry_shadow",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        (out_dir / "system_path_safe_version_eval.json").read_text(encoding="utf-8")
    )
    summaries = payload["metrics"]["mode_summaries"]
    shadow = summaries["safe_version_replace_guided_with_retry_shadow"]
    assert shadow["case_count"] == 2
    assert shadow["answer_candidate_contract_enabled_rate"] == 100.0
    assert "would_retry_count" in shadow
    assert "retry_reason_counts" in shadow
    rows = [
        row
        for row in payload["cases"]
        if row["mode"] == "safe_version_replace_guided_with_retry_shadow"
    ]
    assert rows
    assert all(
        row["safe_version_contract"]["answer_prompt_variant"] == "guided_retry_shadow"
        for row in rows
    )
    assert all(
        row["safe_version_contract"]["answer_candidate_contract"]["enabled"] is True
        for row in rows
    )
    assert all(
        "current_truth_lines"
        not in row["safe_version_contract"]["answer_candidate_contract"]
        for row in rows
    )
    assert all(
        "must_include_terms"
        not in row["safe_version_contract"]["answer_candidate_contract"]
        for row in rows
    )
```

- [ ] **Step 2: Verify the CLI mode test fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_memory_system_path_safe_version_eval.py::test_system_path_safe_version_cli_supports_guided_retry_shadow_mode -q -p no:cacheprovider
```

Expected: FAIL because mode is unknown.

- [ ] **Step 3: Wire the new mode**

In `memory2/eval_system_path_safe_version.py`:

```python
MODE_TO_SAFE_VERSION = {
    ...
    "safe_version_replace_guided_with_retry_shadow": "replace",
}

REPLACE_FAMILY_MODES = {
    ...
    "safe_version_replace_guided_with_retry_shadow",
}
```

Update `_mode_answer_prompt_variant()`:

```python
    if mode == "safe_version_replace_guided_with_retry_shadow":
        return "guided_retry_shadow"
```

- [ ] **Step 4: Attach answer score to post-check only for retry-shadow mode**

In `_run_case_mode()`, move score calculation before post-check construction or build a scoring metadata dict after score and re-run post-check construction. Use this shape:

```python
    score = score_answer_text(
        answer,
        answer_expectation_from_case(case),
        context_ids,
    )
    if mode in POST_CHECK_MODES and contract:
        answer_contract = dict(contract)
        answer_contract["production_safe_evidence_contract"] = True
        if mode == "safe_version_replace_guided_with_retry_shadow":
            answer_contract["answer_score"] = {
                "expected_contains_miss_count": score.expected_contains_miss_count,
                "expected_any_miss_count": score.expected_any_miss_count,
                "language_passed": score.language_passed,
            }
        post_check = answer_post_check_shadow_to_dict(
            build_answer_post_check_shadow(answer, answer_contract, context_ids)
        )
```

Keep existing behavior for all other modes.

- [ ] **Step 5: Add summary metrics**

Before `_mode_summaries()`, update `_sanitize_contract()` to keep only a report-safe answer candidate shape:

```python
    sanitized = {key: value for key, value in contract.items() if key in allowed}
    candidate = contract.get("answer_candidate_contract")
    if isinstance(candidate, dict):
        sanitized["answer_candidate_contract"] = {
            "enabled": bool(candidate.get("enabled")),
            "current_truth_count": int(candidate.get("current_truth_count") or 0),
            "must_include_term_count": int(candidate.get("must_include_term_count") or 0),
            "forbidden_old_value_count": int(candidate.get("forbidden_old_value_count") or 0),
            "language_requirement": str(candidate.get("language_requirement") or ""),
            "candidate_reason": str(candidate.get("candidate_reason") or ""),
        }
    return sanitized
```

Do not add `current_truth_lines`, raw term lists, raw memory summaries, or raw answers to sanitized reports.

In `_mode_summaries()`, include:

```python
        "would_retry_count": sum(
            1
            for row in rows
            if bool(cast(dict[str, object], row.get("post_check_shadow") or {}).get("needs_retry"))
        ),
        "retry_reason_counts": _retry_reason_counts(rows),
        "answer_candidate_contract_enabled_rate": _pct(
            sum(
                1
                for row in rows
                if bool(
                    cast(dict[str, object], cast(dict[str, object], row.get("safe_version_contract") or {}).get("answer_candidate_contract") or {}).get("enabled")
                )
            ),
            len(rows),
        ),
```

Add helper:

```python
def _retry_reason_counts(rows: Sequence[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        post_check = row.get("post_check_shadow")
        if not isinstance(post_check, dict):
            continue
        reasons = post_check.get("retry_reasons", [])
        if not isinstance(reasons, list):
            continue
        for reason in reasons:
            key = str(reason)
            counts[key] = counts.get(key, 0) + 1
    return counts
```

- [ ] **Step 6: Run focused eval tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_memory_system_path_safe_version_eval.py -q -p no:cacheprovider
```

Expected: all tests pass.

---

### Task 4: P6o-19 Gate Report

**Files:**
- Create: `scripts/check_memory_p6o19_gate.py`
- Test: `tests/test_memory_system_path_safe_version_eval.py`
- Docs output: `my_md/memory_optimization/eval_reports/p6o19_answer_candidate_retry_shadow_v1/`

**Interfaces:**
- Consumes `system_path_safe_version_eval.json`.
- Produces:
  - `gate_decision.json`
  - `p6o19_answer_candidate_retry_shadow_report.md`
- Gate fields:
  - `guided_answer_rate`
  - `retry_shadow_answer_rate`
  - `answer_delta_vs_guided`
  - `grounding_rate`
  - `forbidden_rate`
  - `would_retry_count`
  - `retry_reason_counts`
  - `gate_passed`
  - `gate_reasons`

- [ ] **Step 1: Add failing gate script test**

Add to `tests/test_memory_system_path_safe_version_eval.py`:

```python
def test_p6o19_gate_script_writes_retry_shadow_summary(tmp_path: Path) -> None:
    report_path = tmp_path / "system_path_safe_version_eval.json"
    out_dir = tmp_path / "gate"
    report_path.write_text(
        json.dumps(
            {
                "metrics": {
                    "mode_summaries": {
                        "safe_version_replace_guided": {
                            "answer_rule_pass_rate": 75.0,
                            "memory_grounding_pass_rate": 100.0,
                            "forbidden_violation_rate": 0.0,
                            "avg_total_token_count": 100.0,
                            "case_count": 4,
                        },
                        "safe_version_replace_guided_with_retry_shadow": {
                            "answer_rule_pass_rate": 80.0,
                            "memory_grounding_pass_rate": 100.0,
                            "forbidden_violation_rate": 0.0,
                            "avg_total_token_count": 103.0,
                            "case_count": 4,
                            "would_retry_count": 1,
                            "retry_reason_counts": {"required_terms_missing": 1},
                        },
                    },
                    "provider_error_count": 0,
                    "timeout_count": 0,
                    "checkpoint_input_count": 12,
                    "malformed_checkpoint_line_count": 0,
                    "case_count": 12,
                    "mode_count": 3,
                },
                "cases": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/check_memory_p6o19_gate.py",
            "--report-json",
            str(report_path),
            "--out-dir",
            str(out_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    decision = json.loads((out_dir / "gate_decision.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "p6o19_answer_candidate_retry_shadow_report.md").read_text(
        encoding="utf-8"
    )
    assert decision["answer_delta_vs_guided"] == 5.0
    assert decision["would_retry_count"] == 1
    assert decision["retry_reason_counts"] == {"required_terms_missing": 1}
    assert decision["gate_reasons"] == []
    assert "# P6o-19 Answer Candidate Retry Shadow" in markdown
```

- [ ] **Step 2: Verify the gate script test fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_memory_system_path_safe_version_eval.py::test_p6o19_gate_script_writes_retry_shadow_summary -q -p no:cacheprovider
```

Expected: FAIL because `scripts/check_memory_p6o19_gate.py` does not exist.

- [ ] **Step 3: Implement gate script**

Create `scripts/check_memory_p6o19_gate.py` with:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _summary(payload: dict[str, Any], mode: str) -> dict[str, Any]:
    summaries = payload.get("metrics", {}).get("mode_summaries", {})
    if not isinstance(summaries, dict) or mode not in summaries:
        raise SystemExit(f"missing mode summary: {mode}")
    summary = summaries[mode]
    if not isinstance(summary, dict):
        raise SystemExit(f"invalid mode summary: {mode}")
    return summary


def _float(value: object) -> float:
    return round(float(value or 0.0), 4)


def build_gate_decision(payload: dict[str, Any]) -> dict[str, Any]:
    guided = _summary(payload, "safe_version_replace_guided")
    shadow = _summary(payload, "safe_version_replace_guided_with_retry_shadow")
    guided_answer = _float(guided.get("answer_rule_pass_rate"))
    shadow_answer = _float(shadow.get("answer_rule_pass_rate"))
    delta = round(shadow_answer - guided_answer, 4)
    reasons: list[str] = []
    metrics = payload.get("metrics", {})
    if int(metrics.get("provider_error_count") or 0) > 0:
        reasons.append("provider_errors_present")
    if int(metrics.get("timeout_count") or 0) > 0:
        reasons.append("timeouts_present")
    if int(metrics.get("malformed_checkpoint_line_count") or 0) > 0:
        reasons.append("malformed_checkpoint_lines_present")
    if int(metrics.get("case_count") or 0) <= 0:
        reasons.append("missing_case_rows")
    if int(metrics.get("mode_count") or 0) < 3:
        reasons.append("missing_expected_modes")
    if delta <= 0:
        reasons.append("answer_not_above_guided")
    if _float(shadow.get("memory_grounding_pass_rate")) < 100.0:
        reasons.append("grounding_below_100")
    if _float(shadow.get("forbidden_violation_rate")) > 0.0:
        reasons.append("forbidden_above_0")
    retry_counts = shadow.get("retry_reason_counts", {})
    if not isinstance(retry_counts, dict):
        retry_counts = {}
    decision = {
        "guided_answer_rate": guided_answer,
        "retry_shadow_answer_rate": shadow_answer,
        "answer_delta_vs_guided": delta,
        "grounding_rate": _float(shadow.get("memory_grounding_pass_rate")),
        "forbidden_rate": _float(shadow.get("forbidden_violation_rate")),
        "guided_avg_tokens": _float(guided.get("avg_total_token_count")),
        "retry_shadow_avg_tokens": _float(shadow.get("avg_total_token_count")),
        "would_retry_count": int(shadow.get("would_retry_count") or 0),
        "retry_reason_counts": {str(k): int(v or 0) for k, v in retry_counts.items()},
        "provider_error_count": int(metrics.get("provider_error_count") or 0),
        "timeout_count": int(metrics.get("timeout_count") or 0),
        "checkpoint_input_count": int(metrics.get("checkpoint_input_count") or 0),
        "malformed_checkpoint_line_count": int(metrics.get("malformed_checkpoint_line_count") or 0),
        "gate_passed": not reasons,
        "gate_reasons": reasons,
    }
    return decision


def write_markdown(decision: dict[str, Any], path: Path) -> None:
    lines = [
        "# P6o-19 Answer Candidate Retry Shadow",
        "",
        "## Gate",
        "",
        f"- gate_passed: `{decision['gate_passed']}`",
        f"- guided_answer_rate: `{decision['guided_answer_rate']}`",
        f"- retry_shadow_answer_rate: `{decision['retry_shadow_answer_rate']}`",
        f"- answer_delta_vs_guided: `{decision['answer_delta_vs_guided']}`",
        f"- grounding_rate: `{decision['grounding_rate']}`",
        f"- forbidden_rate: `{decision['forbidden_rate']}`",
        f"- would_retry_count: `{decision['would_retry_count']}`",
        f"- retry_reason_counts: `{decision['retry_reason_counts']}`",
        "",
        "## Conclusion",
        "",
        "本报告只记录 P6o-19 gate 数据，不包含原始 query、prompt、memory summary、session text 或完整回答。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-json", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.report_json).read_text(encoding="utf-8"))
    decision = build_gate_decision(payload)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "gate_decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_markdown(decision, out_dir / "p6o19_answer_candidate_retry_shadow_report.md")
    print(out_dir / "gate_decision.json")
    print(out_dir / "p6o19_answer_candidate_retry_shadow_report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run gate script tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_memory_system_path_safe_version_eval.py::test_p6o19_gate_script_writes_retry_shadow_summary -q -p no:cacheprovider
```

Expected: PASS.

---

### Task 5: Fake Smoke, Documentation, and Verification

**Files:**
- Modify: `my_md/memory_optimization/README.md`
- Modify: `progress.md`
- Create: `my_md/memory_optimization/eval_reports/p6o19_answer_candidate_retry_shadow_v1/`

**Interfaces:**
- Uses CLI:
  - `scripts/run_memory_system_path_safe_version_eval.py`
  - `scripts/check_memory_p6o19_gate.py`

- [ ] **Step 1: Run fake-provider P6o-19 smoke**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace /tmp/akashic-p6o19-answer-candidate-fake/workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o19_answer_candidate_retry_shadow_v1/fake_smoke \
  --fake-provider \
  --case-pack standard \
  --balanced-small \
  --common-limit 2 \
  --hard-limit 2 \
  --modes safe_version_replace,safe_version_replace_guided,safe_version_replace_guided_with_retry_shadow
```

Expected: exit `0`, writes `system_path_safe_version_eval.json` and `.md`.

- [ ] **Step 2: Run P6o-19 gate on fake smoke**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python scripts/check_memory_p6o19_gate.py \
  --report-json my_md/memory_optimization/eval_reports/p6o19_answer_candidate_retry_shadow_v1/fake_smoke/system_path_safe_version_eval.json \
  --out-dir my_md/memory_optimization/eval_reports/p6o19_answer_candidate_retry_shadow_v1/fake_smoke
```

Expected: exit `0`, writes `gate_decision.json` and `p6o19_answer_candidate_retry_shadow_report.md`.

- [ ] **Step 3: Run focused regression**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest \
  tests/test_memory_system_path_safe_version_contract.py \
  tests/test_memory_answer_post_check.py \
  tests/test_memory_system_path_safe_version_eval.py \
  tests/test_memory_engine_contract.py \
  tests/test_turn_pipelines.py \
  -q -p no:cacheprovider
```

Expected: all selected tests pass.

- [ ] **Step 4: Run compile and diff checks**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python -m compileall \
  memory2/system_path_safe_version_contract.py \
  memory2/eval_answer_post_check.py \
  memory2/eval_system_path_safe_version.py \
  scripts/run_memory_system_path_safe_version_eval.py \
  scripts/check_memory_p6o19_gate.py \
  tests/test_memory_system_path_safe_version_contract.py \
  tests/test_memory_answer_post_check.py \
  tests/test_memory_system_path_safe_version_eval.py
```

Expected: compileall exits `0`.

Run:

```bash
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 5: Update documentation**

Append to `progress.md`:

```markdown
## 2026-07-30 P6o-19 answer candidate retry shadow

- Goal:
  - test whether answer-candidate contract plus post-check retry shadow reduces answer-layer misses when grounding is already correct.
- Scope:
  - added eval-only `safe_version_replace_guided_with_retry_shadow`;
  - production default remains `MemoryConfig.safe_version_governed_mode = "off"`;
  - no graph-all-on, no recall expansion, no production retry/fallback, no memory write change.
- Fake smoke:
  - report path: `my_md/memory_optimization/eval_reports/p6o19_answer_candidate_retry_shadow_v1/fake_smoke/`;
  - modes: `safe_version_replace`, `safe_version_replace_guided`, `safe_version_replace_guided_with_retry_shadow`;
  - common `2` + hard `2`;
  - record actual case_count, mode_count, provider_error_count, timeout_count, and retry shadow metrics from the generated JSON.
- Test result:
  - record exact focused pytest output.
  - record compileall and `git diff --check` output.
- Conclusion:
  - fake smoke validates wiring and privacy only; it is not a real LLM answer-quality conclusion.
  - next gate is a checkpointed real LLM small matrix if the user approves provider spend.
```

Add a short README bullet under the Phase 6o section with the actual fake smoke data and path.

- [ ] **Step 6: Request code review**

Use `requesting-code-review` with:

- Description: P6o-19 answer-candidate retry shadow eval mode, fake smoke, reports, docs.
- Requirements / Plan: `docs/superpowers/plans/2026-07-30-memory-p6o19-answer-candidate-retry-shadow.md`
- Base: current pre-implementation HEAD.
- Head: current HEAD or working diff if not committed.

- [ ] **Step 7: Apply review feedback**

Use `receiving-code-review`:

- Fix Critical and Important issues after verifying them against the code.
- Re-run focused tests after each fix.
- Do not implement unrelated “nice-to-have” review suggestions unless they directly affect P6o-19 correctness or privacy.

- [ ] **Step 8: Final verification before claiming completion**

Run the focused regression, compileall, and `git diff --check` again.

Expected: all pass before final status is reported.

---

## Real LLM Follow-Up Gate

Do not run real LLM automatically as part of this implementation unless the user explicitly approves provider spend. If approved, run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace /tmp/akashic-p6o19-answer-candidate-real/workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o19_answer_candidate_retry_shadow_v1/real_small_ab \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --enable-real-llm \
  --case-pack standard \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --modes safe_version_replace,safe_version_replace_guided,safe_version_replace_guided_with_retry_shadow \
  --checkpoint-jsonl my_md/memory_optimization/eval_reports/p6o19_answer_candidate_retry_shadow_v1/real_small_ab/checkpoint.jsonl
```

Then rebuild:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python scripts/run_memory_system_path_safe_version_eval.py \
  --out-dir my_md/memory_optimization/eval_reports/p6o19_answer_candidate_retry_shadow_v1/real_small_ab_rebuilt \
  --enable-real-llm \
  --checkpoint-jsonl my_md/memory_optimization/eval_reports/p6o19_answer_candidate_retry_shadow_v1/real_small_ab/checkpoint.jsonl \
  --checkpoint-report-only
```

Then run gate:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python scripts/check_memory_p6o19_gate.py \
  --report-json my_md/memory_optimization/eval_reports/p6o19_answer_candidate_retry_shadow_v1/real_small_ab/system_path_safe_version_eval.json \
  --out-dir my_md/memory_optimization/eval_reports/p6o19_answer_candidate_retry_shadow_v1
```

Record real data, test method, result, and conclusion in:

- `my_md/memory_optimization/eval_reports/p6o19_answer_candidate_retry_shadow_v1/p6o19_answer_candidate_retry_shadow_report.md`
- `my_md/memory_optimization/README.md`
- `progress.md`
