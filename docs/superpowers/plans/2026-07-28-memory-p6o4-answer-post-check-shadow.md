# Memory P6o4 Answer Post-Check Shadow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add eval-only answer post-check shadow for the production-safe governed tri evidence contract.

**Architecture:** Keep production retrieval, production prompts, AgentLoop behavior, memory writes, and real LLM execution unchanged. Add a pure post-check helper that consumes the P6o-3 production-safe evidence contract raw fields, the generated answer text, and the eval harness context memory ids, then records shadow-only diagnostics in comprehensive online eval reports. The context id fields describe injected/retrieved evidence context, not proven answer citations. The check is observational only: it must not fail, retry, alter, or rewrite answers.

**Tech Stack:** Python 3.14, dataclasses, existing `memory2.eval_answer_contract`, existing `memory2.eval_comprehensive_online`, pytest, fake-provider comprehensive eval harness.

## Global Constraints

- Work only in `/home/jjh/git_work/akashic-agent/.worktrees/memory-next`.
- P6o-4 is eval/shadow-only. It must not run real LLM.
- Do not modify production `AgentLoop`, `Reasoner`, `ToolExecutor`, `ToolRegistry`, memory write behavior, production prompt behavior, or the old `Retriever.retrieve()` return contract.
- Do not change `chain_tri_answer_contract`; it remains an oracle diagnostic profile using fixture answer expectations.
- Do not add fixture answer expectations back into `chain_tri_governed_answer_contract`.
- The answer post-check shadow may read the production-safe contract fields from `result.raw["answer_contract"]`, answer text, and harness context ids. In the current eval harness those context ids are carried by `ComprehensiveOnlineMemoryEngine.used_memory_ids`; they mean injected/retrieved context, not proven answer citations. The shadow must not store raw prompt, raw session text, full answer, API keys, or `answer_debug`.
- The shadow result must be report-only. It must not affect `passed`, `answer_rule_passed`, `memory_grounding_passed`, `failures`, retries, or provider calls.
- Do not push without explicit user instruction.

---

## File Structure

- Create `memory2/eval_answer_post_check.py`: pure dataclass and builder for post-answer shadow diagnostics.
- Create `tests/test_memory_answer_post_check.py`: pure tests for allowed evidence inclusion, missing likely relevant context, forbidden boundary inclusion, stale/conflict inclusion, insufficient fallback observation, and privacy.
- Modify `memory2/eval_comprehensive_online.py`: store last retrieve raw data in `ComprehensiveOnlineMemoryEngine`, attach post-check shadow to governed production-safe case records while leaving non-governed rows as `None`, aggregate metrics, and write a Markdown summary.
- Modify `tests/test_memory_comprehensive_online_eval.py`: integration and smoke tests for post-check case records, aggregate metrics, metadata, and Markdown privacy.
- Modify memory optimization docs and planning records: `my_md/memory_optimization/README.md`, `my_md/memory_optimization/02-memory-quality-metrics.md`, `my_md/memory_optimization/03-memory-governance-design.md`, `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`, `progress.md`, and `task_plan.md`.

---

### Task 0: Confirm Clean P6o-4 Baseline

**Files:**
- Modify: none

**Interfaces:**
- Consumes: current `memory-next` worktree after P6o-3.
- Produces: known clean baseline for P6o-4 commits.

- [x] **Step 1: Inspect status**

Run:

```bash
git status --short
```

Expected: no tracked output. Ignored scratch files under `.superpowers/` and ignored plan drafts are acceptable only before they are intentionally force-added.

- [x] **Step 2: Inspect recent commits**

Run:

```bash
git log --oneline -8
```

Expected to include:

```text
16ffaa6 docs: record production safe evidence contract handoff
5b0c63b test: cover p6o3 governed evidence contract smoke
9e84acd feat: use production safe evidence contract for governed tri eval
5638b49 feat: add production safe evidence contract helper
0202665 docs: record tiered candidate governance handoff
```

---

### Task 1: Add Pure Answer Post-Check Shadow Helper

**Files:**
- Create: `memory2/eval_answer_post_check.py`
- Test: `tests/test_memory_answer_post_check.py`

**Interfaces:**
- Consumes:
  - `answer: str`
  - `answer_contract: Mapping[str, object]`
  - `context_memory_ids: Sequence[str]`
- Produces:
  - `AnswerPostCheckShadow`
  - `build_answer_post_check_shadow(answer: str, answer_contract: Mapping[str, object], context_memory_ids: Sequence[str]) -> AnswerPostCheckShadow`
  - `answer_post_check_shadow_to_dict(shadow: AnswerPostCheckShadow) -> dict[str, object]`

- [x] **Step 1: Add failing pure post-check tests**

Create `tests/test_memory_answer_post_check.py`:

```python
from __future__ import annotations

from memory2.eval_answer_post_check import (
    answer_post_check_shadow_to_dict,
    build_answer_post_check_shadow,
)


def _contract() -> dict[str, object]:
    return {
        "production_safe_evidence_contract": True,
        "allowed_evidence_ids": ["target", "weak", "conflict"],
        "likely_relevant_evidence_ids": ["target", "weak"],
        "stale_warning_ids": ["old"],
        "conflict_warning_ids": ["conflict"],
        "active_version_ids": ["target", "weak", "conflict"],
        "insufficient_evidence_ids": ["gap"],
        "insufficient_evidence_fallback": True,
        "forbidden_boundary_ids": ["blocked"],
        "deleted_evidence_ids": ["blocked", "old"],
    }


def test_post_check_records_allowed_missing_risky_and_fallback_signals() -> None:
    shadow = build_answer_post_check_shadow(
        "根据证据不足，无法确认。",
        _contract(),
        ["target", "conflict", "blocked"],
    )

    assert shadow.shadow_enabled is True
    assert shadow.production_safe_evidence_contract is True
    assert shadow.allowed_evidence_included is True
    assert shadow.included_allowed_evidence_ids == ("target", "conflict")
    assert shadow.missing_likely_relevant_context_ids == ("weak",)
    assert shadow.forbidden_boundary_included is True
    assert shadow.included_forbidden_boundary_ids == ("blocked",)
    assert shadow.conflict_evidence_included is True
    assert shadow.included_conflict_warning_ids == ("conflict",)
    assert shadow.stale_evidence_included is False
    assert shadow.insufficient_evidence_fallback_expected is True
    assert shadow.insufficient_evidence_fallback_observed is True
    assert shadow.needs_retry is True
    assert shadow.retry_reasons == (
        "forbidden_boundary_included",
        "missing_likely_relevant_context",
        "conflict_evidence_included",
    )
    assert shadow.raw_answer == ""
    assert shadow.raw_prompt == ""


def test_post_check_marks_missing_fallback_when_evidence_is_insufficient() -> None:
    shadow = build_answer_post_check_shadow(
        "可以继续执行。",
        _contract(),
        ["target", "weak"],
    )

    assert shadow.insufficient_evidence_fallback_expected is True
    assert shadow.insufficient_evidence_fallback_observed is False
    assert shadow.needs_retry is True
    assert "insufficient_evidence_fallback_missing" in shadow.retry_reasons


def test_post_check_is_disabled_for_non_production_safe_contract() -> None:
    shadow = build_answer_post_check_shadow(
        "根据 Answer Contract 回答。",
        {"required_terms": ["ORACLE_TERM"]},
        ["target"],
    )

    assert shadow.shadow_enabled is False
    assert shadow.production_safe_evidence_contract is False
    assert shadow.included_allowed_evidence_ids == ()
    assert shadow.retry_reasons == ()


def test_post_check_dict_is_private_and_structured() -> None:
    shadow = build_answer_post_check_shadow(
        "这是一段完整回答，证据不足，无法确认。",
        _contract(),
        ["target", "weak"],
    )

    payload = answer_post_check_shadow_to_dict(shadow)

    assert payload["shadow_enabled"] is True
    assert payload["production_safe_evidence_contract"] is True
    assert payload["allowed_evidence_included"] is True
    assert payload["included_allowed_evidence_ids"] == ["target", "weak"]
    assert "raw_answer" not in payload
    assert "raw_prompt" not in payload
    assert "full_answer" not in payload
    assert "这是一段完整回答" not in str(payload)
```

- [x] **Step 2: Run pure post-check tests to verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_answer_post_check.py -q -p no:cacheprovider
```

Expected: fail because `memory2.eval_answer_post_check` does not exist.

- [x] **Step 3: Implement pure helper**

Create `memory2/eval_answer_post_check.py`:

```python
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class AnswerPostCheckShadow:
    shadow_enabled: bool
    production_safe_evidence_contract: bool
    allowed_evidence_included: bool
    included_allowed_evidence_ids: tuple[str, ...]
    missing_likely_relevant_context_ids: tuple[str, ...]
    forbidden_boundary_included: bool
    included_forbidden_boundary_ids: tuple[str, ...]
    stale_evidence_included: bool
    included_stale_warning_ids: tuple[str, ...]
    conflict_evidence_included: bool
    included_conflict_warning_ids: tuple[str, ...]
    insufficient_evidence_fallback_expected: bool
    insufficient_evidence_fallback_observed: bool
    forbidden_boundary_mentions: tuple[str, ...]
    needs_retry: bool
    retry_reasons: tuple[str, ...]
    raw_prompt: str = ""
    raw_answer: str = ""


def build_answer_post_check_shadow(
    answer: str,
    answer_contract: Mapping[str, object],
    context_memory_ids: Sequence[str],
) -> AnswerPostCheckShadow:
    production_safe = bool(answer_contract.get("production_safe_evidence_contract"))
    if not production_safe:
        return AnswerPostCheckShadow(
            shadow_enabled=False,
            production_safe_evidence_contract=False,
            allowed_evidence_included=False,
            included_allowed_evidence_ids=(),
            missing_likely_relevant_context_ids=(),
            forbidden_boundary_included=False,
            included_forbidden_boundary_ids=(),
            stale_evidence_included=False,
            included_stale_warning_ids=(),
            conflict_evidence_included=False,
            included_conflict_warning_ids=(),
            insufficient_evidence_fallback_expected=False,
            insufficient_evidence_fallback_observed=False,
            forbidden_boundary_mentions=(),
            needs_retry=False,
            retry_reasons=(),
        )

    context_ids = _string_tuple(context_memory_ids)
    allowed = _string_tuple(answer_contract.get("allowed_evidence_ids", ()))
    likely = _string_tuple(answer_contract.get("likely_relevant_evidence_ids", ()))
    forbidden = _string_tuple(answer_contract.get("forbidden_boundary_ids", ()))
    stale = _string_tuple(answer_contract.get("stale_warning_ids", ()))
    conflict = _string_tuple(answer_contract.get("conflict_warning_ids", ()))
    expected_fallback = bool(answer_contract.get("insufficient_evidence_fallback"))

    included_allowed = _intersection_in_order(context_ids, allowed)
    missing_likely = tuple(item_id for item_id in likely if item_id not in set(context_ids))
    included_forbidden = _intersection_in_order(context_ids, forbidden)
    included_stale = _intersection_in_order(context_ids, stale)
    included_conflict = _intersection_in_order(context_ids, conflict)
    fallback_observed = _mentions_insufficient_evidence(answer)
    boundary_mentions = tuple(item_id for item_id in forbidden if item_id and item_id in answer)

    retry_reasons: list[str] = []
    if included_forbidden:
        retry_reasons.append("forbidden_boundary_included")
    if boundary_mentions:
        retry_reasons.append("forbidden_boundary_mentioned")
    if missing_likely:
        retry_reasons.append("missing_likely_relevant_context")
    if included_stale:
        retry_reasons.append("stale_evidence_included")
    if included_conflict:
        retry_reasons.append("conflict_evidence_included")
    if expected_fallback and not fallback_observed:
        retry_reasons.append("insufficient_evidence_fallback_missing")

    return AnswerPostCheckShadow(
        shadow_enabled=True,
        production_safe_evidence_contract=True,
        allowed_evidence_included=bool(included_allowed),
        included_allowed_evidence_ids=included_allowed,
        missing_likely_relevant_context_ids=missing_likely,
        forbidden_boundary_included=bool(included_forbidden),
        included_forbidden_boundary_ids=included_forbidden,
        stale_evidence_included=bool(included_stale),
        included_stale_warning_ids=included_stale,
        conflict_evidence_included=bool(included_conflict),
        included_conflict_warning_ids=included_conflict,
        insufficient_evidence_fallback_expected=expected_fallback,
        insufficient_evidence_fallback_observed=fallback_observed,
        forbidden_boundary_mentions=boundary_mentions,
        needs_retry=bool(retry_reasons),
        retry_reasons=tuple(retry_reasons),
    )


def answer_post_check_shadow_to_dict(
    shadow: AnswerPostCheckShadow,
) -> dict[str, object]:
    return {
        "shadow_enabled": shadow.shadow_enabled,
        "production_safe_evidence_contract": shadow.production_safe_evidence_contract,
        "allowed_evidence_included": shadow.allowed_evidence_included,
        "included_allowed_evidence_ids": list(shadow.included_allowed_evidence_ids),
        "missing_likely_relevant_context_ids": list(
            shadow.missing_likely_relevant_context_ids
        ),
        "forbidden_boundary_included": shadow.forbidden_boundary_included,
        "included_forbidden_boundary_ids": list(shadow.included_forbidden_boundary_ids),
        "stale_evidence_included": shadow.stale_evidence_included,
        "included_stale_warning_ids": list(shadow.included_stale_warning_ids),
        "conflict_evidence_included": shadow.conflict_evidence_included,
        "included_conflict_warning_ids": list(shadow.included_conflict_warning_ids),
        "insufficient_evidence_fallback_expected": (
            shadow.insufficient_evidence_fallback_expected
        ),
        "insufficient_evidence_fallback_observed": (
            shadow.insufficient_evidence_fallback_observed
        ),
        "forbidden_boundary_mentions": list(shadow.forbidden_boundary_mentions),
        "needs_retry": shadow.needs_retry,
        "retry_reasons": list(shadow.retry_reasons),
    }


def _intersection_in_order(
    source: tuple[str, ...],
    allowed: tuple[str, ...],
) -> tuple[str, ...]:
    allowed_set = set(allowed)
    return tuple(item_id for item_id in source if item_id in allowed_set)


def _mentions_insufficient_evidence(answer: str) -> bool:
    markers = ("证据不足", "无法确认", "不能确认", "insufficient evidence")
    return any(marker.lower() in answer.lower() for marker in markers)


def _string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value else ()
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item) for item in value if str(item))
```

- [x] **Step 4: Run pure tests to verify GREEN**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_answer_post_check.py -q -p no:cacheprovider
```

Expected: all post-check helper tests pass.

- [x] **Step 5: Commit Task 1**

Run:

```bash
git add memory2/eval_answer_post_check.py tests/test_memory_answer_post_check.py
git commit -m "feat: add answer post-check shadow helper"
```

Expected: commit succeeds locally.

---

### Task 2: Attach Post-Check Shadow To Comprehensive Eval Reports

**Files:**
- Modify: `memory2/eval_comprehensive_online.py`
- Test: `tests/test_memory_comprehensive_online_eval.py`

**Interfaces:**
- Consumes:
  - `build_answer_post_check_shadow(answer, answer_contract, context_memory_ids)`
  - `answer_post_check_shadow_to_dict(shadow)`
  - `ComprehensiveOnlineMemoryEngine.last_raw`
- Produces:
  - `ComprehensiveCaseResult.answer_post_check_shadow: dict[str, object] | None`
  - per-case `answer_post_check_shadow` in JSON case records: dict for production-safe governed profile, `None` for non-governed profiles
  - report metrics under `answer_post_check_shadow`
  - Markdown section `## Answer Post-Check Shadow`

- [x] **Step 1: Add failing integration tests**

Add imports in `tests/test_memory_comprehensive_online_eval.py` if needed.

Append near the P6o-3 tests:

```python
def test_p6o4_governed_contract_records_answer_post_check_shadow(
    tmp_path: Path,
) -> None:
    case = _case_with_tiered_tri_candidate()
    specs = build_comprehensive_run_specs(
        [case],
        profiles=("chain_tri_governed_answer_contract",),
        prompt_variants=("baseline",),
        repeats=1,
    )

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            real_llm_enabled=False,
        )
    )

    assert report.metrics["answer_post_check_shadow"]["case_count"] == 1
    assert report.metrics["answer_post_check_shadow"]["enabled_case_count"] == 1
    assert report.metrics["answer_post_check_shadow"]["needs_retry_count"] == 0
    record = report.case_records[0]
    shadow = record["answer_post_check_shadow"]
    assert shadow["shadow_enabled"] is True
    assert shadow["production_safe_evidence_contract"] is True
    assert shadow["allowed_evidence_included"] is True
    assert shadow["forbidden_boundary_included"] is False
    assert shadow["needs_retry"] is False
    assert "raw_answer" not in shadow
    assert "full_answer" not in shadow
```

Add:

```python
def test_p6o4_answer_post_check_shadow_markdown_is_private(
    tmp_path: Path,
) -> None:
    case = _case_with_tiered_tri_candidate()
    specs = build_comprehensive_run_specs(
        [case],
        profiles=("chain_tri_governed_answer_contract",),
        prompt_variants=("baseline",),
        repeats=1,
    )

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            real_llm_enabled=False,
        )
    )
    md_path = tmp_path / "report.md"
    write_comprehensive_online_markdown(report, md_path)
    markdown = md_path.read_text(encoding="utf-8")

    assert "## Answer Post-Check Shadow" in markdown
    assert "needs_retry_count" in markdown
    assert "raw_prompt" not in markdown
    assert "full_answer" not in markdown
    assert "session_text" not in markdown
    assert "根据 production-safe evidence contract" not in markdown
```

Add:

```python
def test_p6o4_post_check_shadow_does_not_change_scoring_or_provider_calls(
    tmp_path: Path,
) -> None:
    case = _case_with_tiered_tri_candidate()
    governed_ids = evidence_ids_for_profile(
        case,
        "chain_tri_governed_answer_contract",
    )
    target_id = governed_ids[0]
    case = replace(
        case,
        setup={
            **case.setup,
            "memory_items": [
                {
                    **item,
                    "insufficient_evidence": (
                        True
                        if str(item.get("id") or item.get("memory_id") or "")
                        == target_id
                        else item.get("insufficient_evidence", False)
                    ),
                }
                for item in case.setup["memory_items"]
            ],
        },
    )
    specs = build_comprehensive_run_specs(
        [case],
        profiles=("chain_tri_governed_answer_contract",),
        prompt_variants=("baseline",),
        repeats=1,
    )
    provider = CountingProvider()

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            provider,
            model="scripted",
            real_llm_enabled=False,
        )
    )

    record = report.case_records[0]
    shadow = record["answer_post_check_shadow"]
    assert provider.call_count == 1
    assert record["passed"] is True
    assert record["answer_rule_passed"] is True
    assert record["memory_grounding_passed"] is True
    assert record["failures"] == []
    assert shadow["needs_retry"] is True
    assert "insufficient_evidence_fallback_missing" in shadow["retry_reasons"]
    assert report.metrics["answer_post_check_shadow"]["needs_retry_count"] == 1
```

Add:

```python
def test_p6o4_non_governed_rows_have_no_post_check_shadow(
    tmp_path: Path,
) -> None:
    case = build_quantitative_eval_cases(
        case_set="common",
        limit=1,
        case_pack="standard",
    )[0]
    specs = build_comprehensive_run_specs(
        [case],
        profiles=("chain_tri_retrieval",),
        prompt_variants=("baseline",),
        repeats=1,
    )

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            real_llm_enabled=False,
        )
    )

    assert report.case_records[0]["answer_post_check_shadow"] is None
    assert report.metrics["answer_post_check_shadow"]["case_count"] == 0
```

Add near checkpoint tests:

```python
def test_p6o4_checkpoint_loader_accepts_rows_without_post_check_shadow(
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "checkpoint.jsonl"
    checkpoint.write_text(
        json.dumps(
            {
                "spec_key": "old",
                "result": _checkpoint_result(
                    case_id="case-old",
                    profile_name="chain_tri_governed_answer_contract",
                ),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = build_comprehensive_online_report_from_checkpoint(
        checkpoint,
        real_llm_enabled=False,
    )

    assert report.case_records[0]["answer_post_check_shadow"] is None
    assert report.metrics["answer_post_check_shadow"]["case_count"] == 0
```

Also add this import at the top of `tests/test_memory_comprehensive_online_eval.py`:

```python
from dataclasses import replace
```

- [x] **Step 2: Run integration tests to verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py::test_p6o4_governed_contract_records_answer_post_check_shadow tests/test_memory_comprehensive_online_eval.py::test_p6o4_answer_post_check_shadow_markdown_is_private tests/test_memory_comprehensive_online_eval.py::test_p6o4_post_check_shadow_does_not_change_scoring_or_provider_calls tests/test_memory_comprehensive_online_eval.py::test_p6o4_non_governed_rows_have_no_post_check_shadow tests/test_memory_comprehensive_online_eval.py::test_p6o4_checkpoint_loader_accepts_rows_without_post_check_shadow -q -p no:cacheprovider
```

Expected: fail because case records and metrics do not include `answer_post_check_shadow`.

- [x] **Step 3: Store last raw retrieval output**

In `ComprehensiveOnlineMemoryEngine.__init__()`, add:

```python
self.last_raw: dict[str, object] = {}
```

Before each `return MemoryEngineRetrieveResult(...)`, set:

```python
self.last_raw = dict(raw)
```

For existing non-contract branch, set it immediately before returning the result. For governed production-safe branch, set it before its early return.

- [x] **Step 4: Extend result dataclass and checkpoint compatibility**

In `ComprehensiveCaseResult`, add the defaulted field at the end:

```python
answer_post_check_shadow: dict[str, object] | None = None
```

In `_load_checkpoint_rows()`, preserve compatibility with older checkpoints by constructing:

```python
payload_with_defaults = {
    **result_payload,
    "failures": tuple(result_payload.get("failures", [])),
    "answer_post_check_shadow": result_payload.get("answer_post_check_shadow"),
}
```

and pass `**payload_with_defaults`.

- [x] **Step 5: Build post-check shadow after answer scoring**

Add imports:

```python
from memory2.eval_answer_post_check import (
    answer_post_check_shadow_to_dict,
    build_answer_post_check_shadow,
)
```

In `_run_comprehensive_case()` after `score = score_answer_text(...)`, add:

```python
answer_post_check_shadow: dict[str, object] | None = None
answer_contract = memory.last_raw.get("answer_contract")
if (
    spec.profile_name == TRI_GOVERNED_ANSWER_CONTRACT_PROFILE
    and isinstance(answer_contract, dict)
):
    answer_post_check_shadow = answer_post_check_shadow_to_dict(
        build_answer_post_check_shadow(
            answer,
            answer_contract,
            memory.used_memory_ids,
        )
    )
```

When constructing `ComprehensiveCaseResult`, pass:

```python
answer_post_check_shadow=answer_post_check_shadow,
```

Do not add any post-check retry reason into `failures`; P6o-4 is shadow-only.

- [x] **Step 6: Add case record and aggregate metrics**

In `_case_record()`, add:

```python
"answer_post_check_shadow": result.answer_post_check_shadow,
```

In `_metrics_from_results()`, add:

```python
"answer_post_check_shadow": _answer_post_check_shadow_metrics(results),
```

In `_empty_metrics()`, add:

```python
"answer_post_check_shadow": _answer_post_check_shadow_metrics(()),
```

Add helper near `_profile_summaries()`:

```python
def _answer_post_check_shadow_metrics(
    results: tuple[ComprehensiveCaseResult, ...],
) -> dict[str, object]:
    shadows = [
        result.answer_post_check_shadow
        for result in results
        if isinstance(result.answer_post_check_shadow, dict)
    ]
    enabled = [shadow for shadow in shadows if shadow.get("shadow_enabled") is True]
    return {
        "case_count": len(shadows),
        "enabled_case_count": len(enabled),
        "needs_retry_count": sum(1 for shadow in enabled if shadow.get("needs_retry") is True),
        "forbidden_boundary_included_count": sum(
            1 for shadow in enabled if shadow.get("forbidden_boundary_included") is True
        ),
        "stale_evidence_included_count": sum(
            1 for shadow in enabled if shadow.get("stale_evidence_included") is True
        ),
        "conflict_evidence_included_count": sum(
            1 for shadow in enabled if shadow.get("conflict_evidence_included") is True
        ),
        "missing_likely_relevant_context_count": sum(
            1
            for shadow in enabled
            if shadow.get("missing_likely_relevant_context_ids")
        ),
        "insufficient_fallback_missing_count": sum(
            1
            for shadow in enabled
            if shadow.get("insufficient_evidence_fallback_expected") is True
            and shadow.get("insufficient_evidence_fallback_observed") is False
        ),
    }
```

- [x] **Step 7: Add Markdown post-check section**

In `write_comprehensive_online_markdown()`, add after `_profile_metadata_markdown_section(metrics)`:

```python
lines.extend(_answer_post_check_shadow_markdown_section(metrics))
```

Add helper:

```python
def _answer_post_check_shadow_markdown_section(metrics: dict[str, object]) -> list[str]:
    shadow = metrics.get("answer_post_check_shadow", {})
    if not isinstance(shadow, dict) or not shadow:
        return []
    return [
        "",
        "## Answer Post-Check Shadow",
        "",
        "- `case_count`: `" + _fmt(shadow.get("case_count")) + "`",
        "- `enabled_case_count`: `" + _fmt(shadow.get("enabled_case_count")) + "`",
        "- `needs_retry_count`: `" + _fmt(shadow.get("needs_retry_count")) + "`",
        "- `forbidden_boundary_included_count`: `"
        + _fmt(shadow.get("forbidden_boundary_included_count"))
        + "`",
        "- `stale_evidence_included_count`: `"
        + _fmt(shadow.get("stale_evidence_included_count"))
        + "`",
        "- `conflict_evidence_included_count`: `"
        + _fmt(shadow.get("conflict_evidence_included_count"))
        + "`",
        "- `missing_likely_relevant_context_count`: `"
        + _fmt(shadow.get("missing_likely_relevant_context_count"))
        + "`",
        "- `insufficient_fallback_missing_count`: `"
        + _fmt(shadow.get("insufficient_fallback_missing_count"))
        + "`",
    ]
```

- [x] **Step 8: Run focused integration tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_answer_post_check.py tests/test_memory_comprehensive_online_eval.py::test_p6o4_governed_contract_records_answer_post_check_shadow tests/test_memory_comprehensive_online_eval.py::test_p6o4_answer_post_check_shadow_markdown_is_private tests/test_memory_comprehensive_online_eval.py::test_p6o4_post_check_shadow_does_not_change_scoring_or_provider_calls tests/test_memory_comprehensive_online_eval.py::test_p6o4_non_governed_rows_have_no_post_check_shadow tests/test_memory_comprehensive_online_eval.py::test_p6o4_checkpoint_loader_accepts_rows_without_post_check_shadow -q -p no:cacheprovider
```

Expected: all selected tests pass.

- [x] **Step 9: Commit Task 2**

Run:

```bash
git add memory2/eval_comprehensive_online.py tests/test_memory_comprehensive_online_eval.py
git commit -m "feat: record governed answer post-check shadow"
```

Expected: commit succeeds locally.

---

### Task 3: Add Fake-Provider Smoke Coverage For P6o-4

**Files:**
- Modify: `tests/test_memory_comprehensive_online_eval.py`

**Interfaces:**
- Consumes:
  - `run_comprehensive_online_eval()`
  - `write_comprehensive_online_markdown()`
  - `answer_post_check_shadow` case records and metrics
- Produces:
  - P6o-4 smoke coverage over common/hard mini matrix.

- [x] **Step 1: Add failing fake-provider smoke test**

Append near `test_p6o3_governed_contract_fake_provider_smoke_is_private`:

```python
def test_p6o4_answer_post_check_shadow_fake_provider_smoke(
    tmp_path: Path,
) -> None:
    cases = (
        build_quantitative_eval_cases(case_set="common", limit=2, case_pack="standard")
        + build_quantitative_eval_cases(case_set="hard", limit=2, case_pack="standard")
    )
    specs = build_comprehensive_run_specs(
        cases,
        profiles=(
            "chain_tri_retrieval",
            "chain_tri_candidate_governance",
            "chain_tri_governed_answer_contract",
        ),
        prompt_variants=("baseline",),
        repeats=1,
    )

    report = asyncio.run(
        run_comprehensive_online_eval(
            specs,
            tmp_path / "workspace",
            ComprehensiveScriptedProvider(),
            model="scripted",
            timeout_s=5.0,
            real_llm_enabled=False,
        )
    )
    md_path = tmp_path / "report.md"
    write_comprehensive_online_markdown(report, md_path)
    markdown = md_path.read_text(encoding="utf-8")

    assert report.metrics["case_count"] == 12
    assert report.metrics["real_llm_enabled"] is False
    assert report.metrics["provider_error_count"] == 0
    assert report.metrics["timeout_count"] == 0
    shadow_metrics = report.metrics["answer_post_check_shadow"]
    assert shadow_metrics["case_count"] == 4
    assert shadow_metrics["enabled_case_count"] == 4
    assert shadow_metrics["forbidden_boundary_included_count"] == 0
    assert shadow_metrics["insufficient_fallback_missing_count"] == 0
    governed_rows = [
        row
        for row in report.case_records
        if row["profile_name"] == "chain_tri_governed_answer_contract"
    ]
    assert len(governed_rows) == 4
    assert all(isinstance(row["answer_post_check_shadow"], dict) for row in governed_rows)
    assert all(row["answer_post_check_shadow"]["shadow_enabled"] is True for row in governed_rows)
    assert all(
        row["answer_post_check_shadow"]["forbidden_boundary_included"] is False
        for row in governed_rows
    )
    assert "## Answer Post-Check Shadow" in markdown
    assert "raw_prompt" not in markdown
    assert "full_answer" not in markdown
    assert "session_text" not in markdown
```

- [x] **Step 2: Run smoke test**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py::test_p6o4_answer_post_check_shadow_fake_provider_smoke -q -p no:cacheprovider
```

Expected: test passes after Task 2 implementation.

- [x] **Step 3: Run broader comprehensive eval tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py -q -p no:cacheprovider
```

Expected: all comprehensive online eval tests pass.

- [x] **Step 4: Commit Task 3**

Run:

```bash
git add tests/test_memory_comprehensive_online_eval.py
git commit -m "test: cover p6o4 answer post-check smoke"
```

Expected: commit succeeds locally.

---

### Task 4: Documentation And P6o-5 Handoff

**Files:**
- Modify: `my_md/memory_optimization/README.md`
- Modify: `my_md/memory_optimization/02-memory-quality-metrics.md`
- Modify: `my_md/memory_optimization/03-memory-governance-design.md`
- Modify: `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
- Modify: `progress.md`
- Modify: `task_plan.md`
- Modify: `docs/superpowers/plans/2026-07-28-memory-p6o4-answer-post-check-shadow.md`

**Interfaces:**
- Consumes: Task 1-3 implementation and verification results.
- Produces: P6o-4 documented boundary and P6o-5 small real LLM A/B handoff.

- [x] **Step 1: Update memory optimization docs**

Add this summary to `my_md/memory_optimization/README.md` after the P6o-3 paragraph:

```markdown
- Phase 6o4-answer-post-check-shadow：新增 eval/shadow-only answer post-check，读取 P6o-3 production-safe evidence contract、回答文本和 harness context memory ids，记录 allowed evidence inclusion、missing likely evidence from context、forbidden boundary inclusion、stale/conflict evidence inclusion、insufficient-evidence fallback 和 retry need。P6o-4 不触发 retry，不改变 production answer，不运行真实 LLM；它只让 P6o-5 真实 LLM A/B 前具备回答后校验观测字段。
```

Add to `my_md/memory_optimization/02-memory-quality-metrics.md` below P6o-3:

```markdown
### Phase 6o4 Answer Post-Check Shadow

P6o-4 adds report-only post-answer diagnostics for the production-safe governed contract. These metrics are not pass/fail gates yet: `needs_retry_count`, `forbidden_boundary_included_count`, `missing_likely_relevant_context_count`, `stale_evidence_included_count`, `conflict_evidence_included_count`, and `insufficient_fallback_missing_count` describe what a future production retry/fallback policy would have observed.
```

Add to `my_md/memory_optimization/03-memory-governance-design.md` after the P6o-3 boundary:

```markdown
P6o-4 design boundary: answer post-check is shadow-only. It does not rewrite, retry, or block answers; it records whether the eval context included allowed evidence, missed likely evidence, included forbidden boundaries, included stale/conflict evidence, or whether the answer text failed to acknowledge insufficient evidence. P6o-5 can use these fields to compare real LLM profiles before any active retry policy exists.
```

Add to `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md` after the P6o-3 complete criteria:

```markdown
P6o-4 complete criteria: comprehensive eval case records include private `answer_post_check_shadow`, aggregate metrics expose retry and evidence-risk counts, Markdown shows only aggregate shadow metrics, fake-provider smoke passes, and no production answer behavior changes. P6o-5 should run the small real LLM A/B with these shadow metrics enabled.
```

- [x] **Step 2: Update planning records**

Append to `task_plan.md`:

```markdown
## 2026-07-28 Memory P6o4 Answer Post-Check Shadow

Goal: record answer post-check shadow diagnostics for the governed production-safe evidence contract without changing answer behavior.

1. Add pure answer post-check shadow helper - complete
2. Attach post-check shadow to comprehensive eval reports - complete
3. Add fake-provider smoke and privacy coverage - complete
4. Update docs and commit locally without push - pending
```

Append to `progress.md`:

```markdown
## 2026-07-28 Memory P6o4 Answer Post-Check Shadow

- Plan path: `docs/superpowers/plans/2026-07-28-memory-p6o4-answer-post-check-shadow.md`.
- Scope: eval/shadow-only post-answer diagnostics, no real LLM.
- Production boundary: no retry, no answer rewrite, no production prompt change, no AgentLoop / Reasoner / ToolExecutor / memory write change.
- Shadow fields: allowed evidence inclusion, missing likely relevant evidence from context, forbidden boundary inclusion, stale evidence inclusion, conflict evidence inclusion, insufficient-evidence fallback observation, retry need.
- Markdown boundary: aggregate metrics only; no raw prompt, session text, full answer, or answer_debug.
- Next handoff: P6o-5 small real LLM A/B should compare `chain_tri_retrieval`, `chain_tri_candidate_governance`, `chain_tri_answer_contract`, and `chain_tri_governed_answer_contract` with post-check shadow metrics enabled.
```

- [x] **Step 3: Run final verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_answer_contract.py tests/test_memory_answer_post_check.py tests/test_memory_comprehensive_online_eval.py tests/test_memory_retrieval_governance.py tests/test_memory_tri_candidate_governance.py -q -p no:cacheprovider
```

Expected: all selected tests pass.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m compileall -q memory2 scripts tests
```

Expected: exit `0`.

Run:

```bash
git diff --check
```

Expected: exit `0`.

- [x] **Step 4: Mark plan complete and commit Task 4**

Mark this plan's completed checkboxes with `- [x]`, then run:

```bash
git add my_md/memory_optimization/README.md my_md/memory_optimization/02-memory-quality-metrics.md my_md/memory_optimization/03-memory-governance-design.md my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md progress.md task_plan.md
git add -f docs/superpowers/plans/2026-07-28-memory-p6o4-answer-post-check-shadow.md
git commit -m "docs: record answer post-check shadow handoff"
```

Expected: commit succeeds locally. Do not push unless the user explicitly asks.

---

## Final Acceptance Criteria

- `chain_tri_answer_contract` remains unchanged as an oracle diagnostic control using fixture answer expectations.
- `chain_tri_governed_answer_contract` remains production-safe and does not reintroduce fixture answer terms.
- Answer post-check shadow is populated only for production-safe governed contract case records; non-governed case records keep `answer_post_check_shadow = None`.
- Post-check shadow records allowed evidence inclusion, missing likely relevant evidence, forbidden boundary inclusion, stale/conflict evidence inclusion, insufficient-evidence fallback observation, and retry need.
- Post-check shadow does not change `passed`, `answer_rule_passed`, `memory_grounding_passed`, `failures`, retries, provider calls, prompts, or answers.
- JSON case records include private structured `answer_post_check_shadow`; Markdown includes only aggregate post-check metrics.
- No real LLM run is part of P6o-4.
- Production retrieval, memory writes, tool execution, AgentLoop, Reasoner, and production prompt behavior are unchanged.
- Focused pytest, compileall, and `git diff --check` pass.

## Self-Review Notes

- Spec coverage: this plan covers P6o-4 only: pure post-check helper, comprehensive eval wiring, fake-provider smoke/privacy coverage, docs, and verification.
- Scope check: P6o-5 real LLM A/B and any active retry/fallback policy are intentionally deferred.
- Placeholder scan: no open-ended TODO placeholders remain; each task has file paths, expected functions, commands, and expected outcomes.
- Type consistency: `AnswerPostCheckShadow`, `build_answer_post_check_shadow()`, `answer_post_check_shadow_to_dict()`, and `answer_post_check_shadow` are used consistently across tasks.
