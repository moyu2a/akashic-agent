# Memory Tri Answer Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an eval-only `chain_tri_answer_contract` profile that tests whether clearer evidence injection and answer constraints can improve tri-retrieval answer quality without expanding recall or changing production behavior.

**Architecture:** Keep production memory retrieval unchanged. Add a small pure answer-contract module that turns an `EvalCase` plus existing `tri_retrieval.fused_ids` into a structured diagnostic prompt block, then wire that block into `ComprehensiveOnlineMemoryEngine` only for the new eval-only profile. Reports compare the new profile against `chain_memory_base`, `chain_tri_retrieval`, and `chain_tri_candidate_governance` on the existing balanced-small real LLM matrix.

**Tech Stack:** Python 3.14, dataclasses, existing `memory2.eval_comprehensive_online`, existing `memory2.eval_quantitative_cases`, pytest, existing comprehensive online eval CLI.

## Global Constraints

- Work only in `/home/jjh/git_work/akashic-agent/.worktrees/memory-next`.
- Do not modify production `AgentLoop`, `Reasoner`, `ToolExecutor`, `ToolRegistry`, memory write behavior, production prompt behavior, or the old `Retriever.retrieve()` return contract.
- `chain_tri_answer_contract` is eval-only and must be marked as diagnostic/oracle-assisted. It must not be described as a production-ready default.
- Do not commit raw prompts, raw session text, raw memory summaries, full answers, API keys, or `answer_debug` artifacts.
- Use the same bounded real LLM shape as the last small online run before considering any larger run: common `20` + hard `20`, prompt variant `baseline`, repeat `1`, explicit profile list.
- Keep `chain_all_on` labeled as `combo/check`; do not use it as a pure module uplift row.
- Do not push without explicit user instruction.

---

## File Structure

- Create `memory2/eval_answer_contract.py`: pure eval-only answer contract builder, renderer, and metadata helpers.
- Modify `memory2/eval_comprehensive_online.py`: register the optional profile, route evidence ids through the new contract helper, and render the contract block only for that profile.
- Modify `tests/test_memory_comprehensive_online_eval.py`: verify profile registration, report metadata, and fake-provider behavior through the existing online eval path.
- Create `tests/test_memory_answer_contract.py`: focused pure tests for contract building, allowed evidence ids, forbidden ids, key answer terms, and rendered text boundaries.
- Modify `scripts/run_memory_comprehensive_online_eval.py`: update fake provider only enough to recognize the answer-contract block during smoke; CLI profile plumbing should continue to use `--profiles`.
- Modify `my_md/memory_optimization/README.md`, `my_md/memory_optimization/02-memory-quality-metrics.md`, and `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`: record the P6n design, bounded run command, result boundary, and final measured result after the run.
- Modify `progress.md` and `task_plan.md`: record plan execution, verification commands, and the evidence boundary.

---

### Task 1: Pure Answer Contract Builder

**Files:**
- Create: `memory2/eval_answer_contract.py`
- Test: `tests/test_memory_answer_contract.py`

**Interfaces:**
- Consumes: `memory2.eval_quantitative_uplift._family_trace_for_case(case, "tri_retrieval")`, `EvalCase.setup["memory_items"]`, `EvalCase.expectations["should_recall_ids"]`, `EvalCase.expectations["should_not_recall_ids"]`, and `EvalCase.expectations["answer_expectations"]`.
- Produces:
  - `AnswerContract` dataclass.
  - `build_tri_answer_contract(case: EvalCase) -> AnswerContract`.
  - `render_answer_contract_block(contract: AnswerContract) -> str`.
  - `tri_answer_contract_evidence_ids(case: EvalCase) -> tuple[str, ...]`.

- [ ] **Step 1: Write focused failing tests**

Add `tests/test_memory_answer_contract.py`:

```python
from __future__ import annotations

from memory2.eval_answer_contract import (
    build_tri_answer_contract,
    render_answer_contract_block,
    tri_answer_contract_evidence_ids,
)
from memory2.eval_quantitative_cases import build_quantitative_eval_cases


def _case_with_should_not_in_tri():
    for case in (
        build_quantitative_eval_cases(case_set="common", limit=20, case_pack="standard")
        + build_quantitative_eval_cases(case_set="hard", limit=20, case_pack="standard")
    ):
        tri_ids = set(build_tri_answer_contract(case).tri_ids)
        should_not = set(case.expectations["should_not_recall_ids"])
        if tri_ids & should_not:
            return case
    raise AssertionError("fixture must include at least one tri should-not candidate")


def test_contract_keeps_expected_ids_and_marks_forbidden_candidates() -> None:
    case = _case_with_should_not_in_tri()

    contract = build_tri_answer_contract(case)

    expected_ids = tuple(str(item) for item in case.expectations["should_recall_ids"])
    should_not_ids = set(str(item) for item in case.expectations["should_not_recall_ids"])
    assert set(expected_ids) <= set(contract.must_use_ids)
    assert set(contract.forbidden_ids) == (set(contract.tri_ids) & should_not_ids)
    assert set(contract.forbidden_ids).isdisjoint(contract.allowed_evidence_ids)
    assert contract.diagnostic_eval_only is True


def test_contract_evidence_ids_preserve_tri_order_and_remove_forbidden() -> None:
    case = _case_with_should_not_in_tri()
    tri_ids = build_tri_answer_contract(case).tri_ids
    forbidden = set(str(item) for item in case.expectations["should_not_recall_ids"])

    governed_ids = tri_answer_contract_evidence_ids(case)

    assert governed_ids == tuple(item_id for item_id in tri_ids if item_id not in forbidden)
    assert set(case.expectations["should_recall_ids"]) <= set(governed_ids)


def test_contract_extracts_answer_terms_without_raw_prompt_or_full_answer() -> None:
    case = _case_with_should_not_in_tri()

    contract = build_tri_answer_contract(case)

    answer_expectations = case.expectations["answer_expectations"]
    expected_terms = answer_expectations.get("expected_answer_contains", ())
    expected_term_groups = answer_expectations.get("expected_answer_contains_any", ())
    forbidden_terms = answer_expectations.get("forbidden_answer_contains", ())

    assert set(contract.required_terms) >= {str(term) for term in expected_terms}
    assert contract.required_terms
    assert contract.required_term_groups == tuple(
        tuple(str(term) for term in group) for group in expected_term_groups
    )
    assert contract.forbidden_terms == tuple(str(term) for term in forbidden_terms)
    assert contract.raw_answer == ""
    assert contract.raw_prompt == ""


def test_rendered_contract_is_structured_and_private() -> None:
    case = _case_with_should_not_in_tri()
    contract = build_tri_answer_contract(case)

    text = render_answer_contract_block(contract)

    assert "Answer Contract" in text
    assert "must_use_memory_ids" in text
    assert "forbidden_memory_ids" in text
    assert "required_terms" in text
    assert "不要使用 forbidden_memory_ids" in text
    assert "memory_id=" in text
    assert case.setup["query"] not in text
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_answer_contract.py -q -p no:cacheprovider
```

Expected: fail with `ModuleNotFoundError: No module named 'memory2.eval_answer_contract'`.

- [ ] **Step 3: Implement the pure helper**

Create `memory2/eval_answer_contract.py`:

```python
"""Eval-only answer contract helpers for tri-retrieval diagnostics."""

from __future__ import annotations

from dataclasses import dataclass

from memory2.eval_quantitative_cases import EvalCase
from memory2.eval_quantitative_uplift import _family_trace_for_case


@dataclass(frozen=True)
class AnswerContract:
    profile_name: str
    diagnostic_eval_only: bool
    tri_ids: tuple[str, ...]
    must_use_ids: tuple[str, ...]
    allowed_evidence_ids: tuple[str, ...]
    forbidden_ids: tuple[str, ...]
    required_terms: tuple[str, ...]
    required_term_groups: tuple[tuple[str, ...], ...]
    forbidden_terms: tuple[str, ...]
    evidence_summaries: tuple[tuple[str, str], ...]
    raw_prompt: str = ""
    raw_answer: str = ""


def build_tri_answer_contract(case: EvalCase) -> AnswerContract:
    tri_ids = _ids_from_trace(case, "tri_retrieval", "fused_ids")
    expected_ids = _string_tuple(case.expectations.get("should_recall_ids", ()))
    should_not_ids = set(_string_tuple(case.expectations.get("should_not_recall_ids", ())))
    allowed_ids = tuple(item_id for item_id in tri_ids if item_id not in should_not_ids)
    forbidden_ids = tuple(item_id for item_id in tri_ids if item_id in should_not_ids)
    answer_expectations = case.expectations.get("answer_expectations") or {}
    summaries = _summaries_for_ids(case, allowed_ids)
    return AnswerContract(
        profile_name="chain_tri_answer_contract",
        diagnostic_eval_only=True,
        tri_ids=tri_ids,
        must_use_ids=tuple(item_id for item_id in expected_ids if item_id in allowed_ids),
        allowed_evidence_ids=allowed_ids,
        forbidden_ids=forbidden_ids,
        required_terms=_string_tuple(answer_expectations.get("expected_answer_contains", ())),
        required_term_groups=_term_groups(
            answer_expectations.get("expected_answer_contains_any", ())
        ),
        forbidden_terms=_string_tuple(
            answer_expectations.get("forbidden_answer_contains", ())
        ),
        evidence_summaries=summaries,
    )


def tri_answer_contract_evidence_ids(case: EvalCase) -> tuple[str, ...]:
    return build_tri_answer_contract(case).allowed_evidence_ids


def render_answer_contract_block(contract: AnswerContract) -> str:
    lines = [
        "Answer Contract: chain_tri_answer_contract",
        "diagnostic_eval_only=true",
        "请只根据 allowed_evidence 回答；不要使用 forbidden_memory_ids 中的记忆。",
        "如果 required_terms 或 required_term_groups 与证据一致，请在中文回答中保留这些关键术语。",
        "如果证据不足以支持 required_terms，请说明无法确认，不要补写 forbidden_terms。",
        "must_use_memory_ids: " + ", ".join(contract.must_use_ids),
        "forbidden_memory_ids: " + ", ".join(contract.forbidden_ids),
        "required_terms: " + ", ".join(contract.required_terms),
        "required_term_groups: " + _format_groups(contract.required_term_groups),
        "forbidden_terms: " + ", ".join(contract.forbidden_terms),
        "allowed_evidence:",
    ]
    for item_id, summary in contract.evidence_summaries:
        lines.append(f"- memory_id={item_id}; summary={summary}")
    return "\n".join(lines)


def _summaries_for_ids(case: EvalCase, ids: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    by_id = {
        str(item.get("id") or item.get("memory_id") or ""): item
        for item in case.setup.get("memory_items", ())
        if isinstance(item, dict)
    }
    rows: list[tuple[str, str]] = []
    for item_id in ids:
        item = by_id.get(item_id) or {}
        summary = str(item.get("summary") or item.get("content") or "")
        rows.append((item_id, _compact(summary)))
    return tuple(rows)


def _ids_from_trace(case: EvalCase, family_name: str, key: str) -> tuple[str, ...]:
    trace = _family_trace_for_case(case, family_name)
    if trace is None:
        return ()
    raw_ids = trace.experimental_result.get(key, [])
    return _string_tuple(raw_ids)


def _string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value else ()
    if not isinstance(value, (list, tuple, set)):
        return ()
    return tuple(str(item) for item in value if str(item))


def _term_groups(value: object) -> tuple[tuple[str, ...], ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    groups: list[tuple[str, ...]] = []
    for group in value:
        terms = _string_tuple(group)
        if terms:
            groups.append(terms)
    return tuple(groups)


def _format_groups(groups: tuple[tuple[str, ...], ...]) -> str:
    return " | ".join("(" + ", ".join(group) + ")" for group in groups)


def _compact(text: str, *, limit: int = 180) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_answer_contract.py -q -p no:cacheprovider
```

Expected: `4 passed`.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add memory2/eval_answer_contract.py tests/test_memory_answer_contract.py
git commit -m "feat: add memory tri answer contract helper"
```

Expected: commit succeeds locally.

---

### Task 2: Wire Eval-Only Profile Into Comprehensive Online Eval

**Files:**
- Modify: `memory2/eval_comprehensive_online.py`
- Modify: `tests/test_memory_comprehensive_online_eval.py`

**Interfaces:**
- Consumes: `build_tri_answer_contract(case)`, `render_answer_contract_block(contract)`, and `tri_answer_contract_evidence_ids(case)` from Task 1.
- Produces:
  - Constant `TRI_ANSWER_CONTRACT_PROFILE = "chain_tri_answer_contract"`.
  - Optional profile metadata with `eval_only=True`, `diagnostic_answer_contract=True`, and `uses_fixture_answer_expectations=True`.
  - `profile_evidence_source("chain_tri_answer_contract") == "tri_answer_contract.allowed_evidence_ids"`.
  - `ComprehensiveOnlineMemoryEngine.retrieve()` renders the contract block for this profile.

- [ ] **Step 1: Write failing integration tests**

Append to `tests/test_memory_comprehensive_online_eval.py`:

```python
def test_tri_answer_contract_profile_is_optional_eval_only() -> None:
    case = build_quantitative_eval_cases(case_set="common", limit=1, case_pack="standard")[0]

    specs = build_comprehensive_run_specs(
        [case],
        profiles=("chain_tri_answer_contract",),
        prompt_variants=("baseline",),
        repeats=1,
    )

    assert len(specs) == 1
    assert evidence_ids_for_profile(case, "chain_tri_answer_contract")
    assert (
        profile_evidence_source("chain_tri_answer_contract")
        == "tri_answer_contract.allowed_evidence_ids"
    )


def test_tri_answer_contract_profile_injects_contract_block(tmp_path: Path) -> None:
    case = build_quantitative_eval_cases(case_set="common", limit=1, case_pack="standard")[0]
    engine = ComprehensiveOnlineMemoryEngine(
        case,
        profile_name="chain_tri_answer_contract",
        prompt_variant="baseline",
    )

    result = asyncio.run(
        engine.retrieve(
            MemoryEngineRetrieveRequest(
                query=str(case.setup["query"]),
                mode="explicit",
                top_k=8,
            )
        )
    )

    assert "Answer Contract: chain_tri_answer_contract" in result.text_block
    assert "allowed_evidence:" in result.text_block
    assert "forbidden_memory_ids:" in result.text_block
    assert result.raw["evidence_source"] == "tri_answer_contract.allowed_evidence_ids"
```

If `MemoryEngineRetrieveRequest` is not already imported in the file, add:

```python
from core.memory.engine import MemoryEngineRetrieveRequest
from memory2.eval_comprehensive_online import ComprehensiveOnlineMemoryEngine
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py::test_tri_answer_contract_profile_is_optional_eval_only tests/test_memory_comprehensive_online_eval.py::test_tri_answer_contract_profile_injects_contract_block -q -p no:cacheprovider
```

Expected: fail with unknown profile or missing import/name errors.

- [ ] **Step 3: Modify imports and constants**

In `memory2/eval_comprehensive_online.py`, add imports near existing retrieval governance imports:

```python
from memory2.eval_answer_contract import (
    build_tri_answer_contract,
    render_answer_contract_block,
    tri_answer_contract_evidence_ids,
)
```

Add the profile constant and include it in optional profiles:

```python
TRI_CANDIDATE_GOVERNANCE_PROFILE = "chain_tri_candidate_governance"
TRI_ANSWER_CONTRACT_PROFILE = "chain_tri_answer_contract"
OPTIONAL_ANSWER_QUALITY_PROFILES: tuple[str, ...] = (
    TRI_CANDIDATE_GOVERNANCE_PROFILE,
    TRI_ANSWER_CONTRACT_PROFILE,
)
```

Extend `PROFILE_METADATA`:

```python
TRI_ANSWER_CONTRACT_PROFILE: {
    "eval_only": True,
    "diagnostic_answer_contract": True,
    "uses_fixture_answer_expectations": True,
    "description": (
        "Renders a structured answer contract over existing tri fused ids "
        "to test whether answer constraints improve grounded tri retrieval."
    ),
},
```

- [ ] **Step 4: Route evidence ids and source labels**

In `evidence_ids_for_profile()` before the `profile_name not in COMPREHENSIVE_CHAIN_PROFILES` check:

```python
if profile_name == TRI_ANSWER_CONTRACT_PROFILE:
    return tri_answer_contract_evidence_ids(case)
```

In `profile_evidence_source()` add:

```python
TRI_ANSWER_CONTRACT_PROFILE: "tri_answer_contract.allowed_evidence_ids",
```

- [ ] **Step 5: Render the answer contract block**

In `ComprehensiveOnlineMemoryEngine.retrieve()`, after computing `ids` and before building `hits`, add:

```python
if self.profile_name == TRI_ANSWER_CONTRACT_PROFILE:
    contract = build_tri_answer_contract(self.case)
    self.used_memory_ids = list(contract.allowed_evidence_ids)
    hits = [
        MemoryHit(
            id=item_id,
            summary=summary,
            content=summary,
            score=1.0,
            source_ref="",
            engine_kind="comprehensive_online_eval",
            injected=True,
        )
        for item_id, summary in contract.evidence_summaries
    ]
    self.last_text_block = render_answer_contract_block(contract)
    return MemoryEngineRetrieveResult(
        text_block=self.last_text_block,
        hits=hits,
        raw={
            "ids": list(contract.allowed_evidence_ids),
            "must_use_ids": list(contract.must_use_ids),
            "forbidden_ids": list(contract.forbidden_ids),
            "evidence_source": profile_evidence_source(self.profile_name),
            "answer_contract": {
                "diagnostic_eval_only": contract.diagnostic_eval_only,
                "required_terms": list(contract.required_terms),
                "required_term_groups": [list(group) for group in contract.required_term_groups],
                "forbidden_terms": list(contract.forbidden_terms),
            },
        },
    )
```

- [ ] **Step 6: Run focused integration tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_answer_contract.py tests/test_memory_comprehensive_online_eval.py::test_tri_answer_contract_profile_is_optional_eval_only tests/test_memory_comprehensive_online_eval.py::test_tri_answer_contract_profile_injects_contract_block -q -p no:cacheprovider
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit Task 2**

Run:

```bash
git add memory2/eval_comprehensive_online.py tests/test_memory_comprehensive_online_eval.py
git commit -m "feat: add eval-only tri answer contract profile"
```

Expected: commit succeeds locally.

---

### Task 3: Fake-Provider Smoke And Report Metadata

**Files:**
- Modify: `scripts/run_memory_comprehensive_online_eval.py`
- Modify: `tests/test_memory_comprehensive_online_eval.py`
- Test: existing CLI tests in `tests/test_memory_comprehensive_online_cli.py`

**Interfaces:**
- Consumes: optional profile registration from Task 2.
- Produces:
  - Fake provider can demonstrate answer-contract structure without real LLM calls.
  - Markdown/JSON report includes `chain_tri_answer_contract` in profile summary and eval-only metadata.

- [ ] **Step 1: Add report-level regression test**

Append to `tests/test_memory_comprehensive_online_eval.py`:

```python
def test_tri_answer_contract_profile_report_records_eval_only_metadata(tmp_path: Path) -> None:
    case = build_quantitative_eval_cases(case_set="common", limit=1, case_pack="standard")[0]
    specs = build_comprehensive_run_specs(
        [case],
        profiles=("chain_tri_answer_contract",),
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

    metadata = report.metrics["profile_metadata"]["chain_tri_answer_contract"]
    assert metadata["eval_only"] is True
    assert metadata["diagnostic_answer_contract"] is True
    assert metadata["uses_fixture_answer_expectations"] is True
    assert report.metrics["profile_summaries"]["chain_tri_answer_contract"]["case_count"] == 1

    md_path = tmp_path / "report.md"
    write_comprehensive_online_markdown(report, md_path)
    markdown = md_path.read_text(encoding="utf-8")
    assert "diagnostic_answer_contract" in markdown
    assert "uses_fixture_answer_expectations" in markdown
```

- [ ] **Step 2: Run test to verify RED or current gap**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_comprehensive_online_eval.py::test_tri_answer_contract_profile_report_records_eval_only_metadata -q -p no:cacheprovider
```

Expected: fail if `profile_metadata` does not include the new profile, otherwise pass and continue.

- [ ] **Step 3: Update fake provider answer selection**

In both `tests/test_memory_comprehensive_online_eval.py::ComprehensiveScriptedProvider.chat()` and `scripts/run_memory_comprehensive_online_eval.py::ScriptedComprehensiveOnlineProvider.chat()`, add this branch before the generic fallback:

```python
elif "Answer Contract: chain_tri_answer_contract" in text:
    answer = "根据 Answer Contract，应使用 must_use_memory_ids 中的证据回答，并避免 forbidden_terms。"
```

- [ ] **Step 4: Extend metadata Markdown columns**

Existing `profile_metadata` metrics already include optional profiles present in the run. Update `_profile_metadata_markdown_section()` in `memory2/eval_comprehensive_online.py` so the Markdown table exposes answer-contract-specific boundary fields:

```python
def _profile_metadata_markdown_section(metrics: dict[str, object]) -> list[str]:
    metadata = metrics.get("profile_metadata", {})
    if not isinstance(metadata, dict) or not metadata:
        return []
    lines = [
        "",
        "## Eval-Only Profile Metadata",
        "",
        (
            "| profile | eval_only | oracle_protected | uses_fixture_expected_ids | "
            "diagnostic_answer_contract | uses_fixture_answer_expectations |"
        ),
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for profile in sorted(metadata):
        row = metadata.get(profile)
        if not isinstance(row, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    profile,
                    _fmt(row.get("eval_only")),
                    _fmt(row.get("oracle_protected")),
                    _fmt(row.get("uses_fixture_expected_ids")),
                    _fmt(row.get("diagnostic_answer_contract")),
                    _fmt(row.get("uses_fixture_answer_expectations")),
                ]
            )
            + " |"
        )
    return lines
```

This keeps existing candidate-governance metadata visible while making the new answer-contract oracle boundary visible in Markdown.

- [ ] **Step 5: Run fake-provider smoke**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-tri-answer-contract-fake/workspace \
  --out-dir /tmp/akashic-memory-tri-answer-contract-fake/reports \
  --case-pack standard \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --profiles chain_memory_base,chain_tri_retrieval,chain_tri_candidate_governance,chain_tri_answer_contract \
  --prompt-variants baseline \
  --repeats 1 \
  --fake-provider \
  --timeout-s 60 \
  --concurrency 1
```

Expected output files:

```text
/tmp/akashic-memory-tri-answer-contract-fake/reports/memory_comprehensive_online_eval.json
/tmp/akashic-memory-tri-answer-contract-fake/reports/memory_comprehensive_online_eval.md
```

Expected report facts:

```text
case_count = 160
unique_case_count = 40
profile_count = 4
real_llm_enabled = False
provider_error_count = 0
timeout_count = 0
chain_tri_answer_contract appears in profile summary
```

- [ ] **Step 6: Run focused regression**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_answer_contract.py tests/test_memory_comprehensive_online_eval.py tests/test_memory_comprehensive_online_cli.py -q -p no:cacheprovider
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit Task 3**

Run:

```bash
git add scripts/run_memory_comprehensive_online_eval.py tests/test_memory_comprehensive_online_eval.py memory2/eval_comprehensive_online.py
git commit -m "test: cover tri answer contract online eval profile"
```

Expected: commit succeeds locally.

---

### Task 4: Bounded Real LLM Run And Documentation

**Files:**
- Modify: `my_md/memory_optimization/README.md`
- Modify: `my_md/memory_optimization/02-memory-quality-metrics.md`
- Modify: `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
- Modify: `progress.md`
- Modify: `task_plan.md`
- Generated report:
  - `my_md/memory_optimization/eval_reports/tri_answer_contract_small_online_v1/memory_comprehensive_online_eval.json`
  - `my_md/memory_optimization/eval_reports/tri_answer_contract_small_online_v1/memory_comprehensive_online_eval.md`

**Interfaces:**
- Consumes: real LLM CLI path from Task 3.
- Produces: measured comparison of `chain_tri_answer_contract` against `chain_memory_base`, `chain_tri_retrieval`, and `chain_tri_candidate_governance`.

- [ ] **Step 1: Run the bounded real LLM matrix**

Run only after fake-provider smoke and focused tests pass:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_comprehensive_online_eval.py \
  --workspace /tmp/akashic-memory-tri-answer-contract-online/workspace \
  --out-dir my_md/memory_optimization/eval_reports/tri_answer_contract_small_online_v1 \
  --config config.toml \
  --case-pack standard \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --profiles chain_memory_base,chain_tri_retrieval,chain_tri_candidate_governance,chain_tri_answer_contract \
  --prompt-variants baseline \
  --repeats 1 \
  --enable-real-llm \
  --checkpoint-jsonl /tmp/akashic-memory-tri-answer-contract-online/reports/memory_comprehensive_online_eval.checkpoint.jsonl \
  --timeout-s 60 \
  --concurrency 1
```

Expected report facts if provider credentials are available:

```text
real_llm_enabled = True
case_count = 160
unique_case_count = 40
profile_count = 4
provider_error_count = 0
timeout_count = 0
```

If the command gates due to missing API key, do not substitute fake-provider results as real evidence. Record `missing_api_key` in `progress.md` and stop before claiming P6n measured performance.

- [ ] **Step 2: Extract measured comparison**

Read the generated Markdown report and record these exact rows:

```text
chain_memory_base answer_rate / grounding_rate / forbidden_rate / avg_tokens / avg_latency_ms
chain_tri_retrieval answer_rate / grounding_rate / forbidden_rate / avg_tokens / avg_latency_ms
chain_tri_candidate_governance answer_rate / grounding_rate / forbidden_rate / avg_tokens / avg_latency_ms
chain_tri_answer_contract answer_rate / grounding_rate / forbidden_rate / avg_tokens / avg_latency_ms
```

Success gate for P6n:

```text
chain_tri_answer_contract.answer_rate > 55.0
chain_tri_answer_contract.grounding_rate == 100.0
chain_tri_answer_contract.forbidden_rate <= 15.0
```

If answer rate improves but forbidden rises above `15.0`, classify the result as answer-contract partial success with forbidden regression. If forbidden improves but answer rate stays at or below `55.0`, classify the result as answer-contract safety success without answer-quality success.

- [ ] **Step 3: Update memory optimization docs**

Add a short P6n section to `my_md/memory_optimization/README.md`:

```markdown
- Phase 6n-tri-answer-contract：新增 eval-only `chain_tri_answer_contract` profile，不扩大召回、不改生产链路，只把已有 `tri_retrieval.fused_ids` 渲染成 Answer Contract：must-use ids、allowed evidence、forbidden ids、required terms、required term groups 和 forbidden terms。小型真实 LLM 报告路径是 `my_md/memory_optimization/eval_reports/tri_answer_contract_small_online_v1/memory_comprehensive_online_eval.json` 和 `.md`。本 profile 使用 fixture answer expectations，属于诊断/上限验证，不能直接宣称为生产策略。
```

Add a measured table to `my_md/memory_optimization/02-memory-quality-metrics.md` by copying the four profile rows from the generated report's `Profile Summary` table. The table must include only these profiles and columns:

```markdown
### Phase 6n Tri Answer Contract Small Online

Columns: profile, answer_rate, grounding_rate, forbidden_rate, avg_tokens, avg_latency_ms.
Rows: chain_memory_base, chain_tri_retrieval, chain_tri_candidate_governance, chain_tri_answer_contract.
Conclusion: one concrete sentence based only on the measured success gate.
```

Every table cell must be copied from the generated report before committing. Do not commit generic marker text in the table.

Add a roadmap note to `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md` explaining whether the next step is:

```text
answer contract works -> translate diagnostic contract into production-safe evidence injection without fixture expectations
answer contract does not work -> inspect failure buckets before adding new retrieval lanes
answer contract reduces forbidden only -> combine lightweight forbidden filtering with less aggressive evidence pruning
```

- [ ] **Step 4: Update planning records**

Append to `task_plan.md`:

```markdown
## 2026-07-28 Memory Tri Answer Contract

Goal: test whether structured answer-contract evidence injection fixes tri retrieval's post-grounding answer-quality failures without changing production retrieval or prompt behavior.

1. Add pure answer-contract helper and tests - complete
2. Add eval-only `chain_tri_answer_contract` profile - complete
3. Run fake-provider smoke and focused regression - complete
4. Run bounded real LLM comparison and document measured outcome - complete
5. Commit locally without push - pending
```

Append to `progress.md` with the exact commands run, paths written, metrics, and whether the success gate passed.

- [ ] **Step 5: Run final verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_memory_answer_contract.py tests/test_memory_comprehensive_online_eval.py tests/test_memory_comprehensive_online_cli.py tests/test_memory_tri_candidate_governance.py tests/test_memory_tri_retrieval_failure_attribution.py -q -p no:cacheprovider
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

- [ ] **Step 6: Commit Task 4**

Run:

```bash
git add memory2/eval_answer_contract.py memory2/eval_comprehensive_online.py scripts/run_memory_comprehensive_online_eval.py tests/test_memory_answer_contract.py tests/test_memory_comprehensive_online_eval.py my_md/memory_optimization/README.md my_md/memory_optimization/02-memory-quality-metrics.md my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md my_md/memory_optimization/eval_reports/tri_answer_contract_small_online_v1/memory_comprehensive_online_eval.json my_md/memory_optimization/eval_reports/tri_answer_contract_small_online_v1/memory_comprehensive_online_eval.md progress.md task_plan.md
git commit -m "test: add tri answer contract online eval"
```

Expected: commit succeeds locally. Do not push unless the user explicitly asks.

---

## Final Acceptance Criteria

- `chain_tri_answer_contract` is available only as an optional eval profile.
- Production retrieval, memory writes, tool execution, AgentLoop, Reasoner, and production prompt behavior are unchanged.
- Fake-provider smoke produces a 160-row / 40-unique-case / 4-profile report.
- Real LLM run, if credentials are available, produces a complete 160-row report with `provider_error_count = 0` and `timeout_count = 0`.
- The final docs state whether the profile passed the P6n success gate:
  - answer rate above `55.0%`;
  - grounding rate equal to `100.0%`;
  - forbidden rate at or below `15.0%`.
- The docs explicitly label `chain_tri_answer_contract` as diagnostic/oracle-assisted because it uses fixture answer expectations.
- Focused pytest, compileall, and `git diff --check` pass.

## Self-Review Notes

- Spec coverage: this plan covers answer-contract construction, profile wiring, fake-provider smoke, bounded real LLM comparison, documentation, and verification.
- Scope check: this is one subsystem inside the memory eval harness; it intentionally avoids production memory runtime changes.
- Type consistency: the plan consistently uses `AnswerContract`, `build_tri_answer_contract()`, `render_answer_contract_block()`, `tri_answer_contract_evidence_ids()`, and `TRI_ANSWER_CONTRACT_PROFILE`.
- Placeholder scan: implementation steps contain concrete code and commands. The documentation table instructions require concrete measured values before committing.
