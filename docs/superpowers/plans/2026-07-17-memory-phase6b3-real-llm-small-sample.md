# Memory Phase6b-3 Real LLM Small-Sample Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicitly gated real-LLM small-sample memory evaluation that measures whether the model uses controlled memory evidence correctly, while recording latency, token metadata, and answer-rule outcomes.

**Architecture:** Reuse the Phase6b-2 real `AgentLoop` dry-run harness shape, but replace the fake provider with a guarded real `LLMProvider` only when `--enable-real-llm` is present. Keep the memory engine controlled by fixture data so the run does not depend on the user's real memory database. Score answers with deterministic string/rule checks first; LLM-as-judge, Dashboard, and active gates stay out of scope.

**Tech Stack:** Python dataclasses, asyncio, existing `AgentLoop`, existing `LLMProvider`, existing `load_config`, existing `EvalCase` fixtures, pytest, JSON/Markdown reports.

## Global Constraints

- Real LLM calls must be disabled by default.
- The CLI must require `--enable-real-llm` before constructing or calling a real `LLMProvider`.
- Default pytest must not call a real LLM, embedding API, network, or paid service.
- This phase must not use or mutate the user's real `workspace/memory/memory2.db`.
- This phase must not write the user's real `workspace/sessions.db` or `workspace/observe/observe.db`.
- All AgentLoop/session writes must go under a caller-provided temporary workspace.
- Reports must not include assembled prompts, raw session messages, full answer text, API keys, or raw config values.
- Reports may include answer length, hashed/truncated-safe answer metadata, booleans, counts, ids, best-effort token metadata, latency, and sanitized failure reasons.
- Token counts are optional because not every `LLMResponse` or provider exposes usage fields; every report must include `token_metrics_available`.
- Provider exceptions must be reported as sanitized categories, not raw exception text.
- Do not add dependencies.
- Do not stage or commit `uv.lock`.
- Preserve Phase6a, Phase6b-1, and Phase6b-2 tests and behavior.

---

## File Structure

- Modify: `tests/fixtures/memory_eval_cases/preference_recall.json`
  - Add answer-level expectations for language preference.
- Modify: `tests/fixtures/memory_eval_cases/cross_scope_isolation.json`
  - Add answer-level expectations for avoiding cross-scope memory.
- Modify: `tests/fixtures/memory_eval_cases/vague_reference_graph.json`
  - Add answer-level expectations for vague-reference graph memory.
- Create: `memory2/eval_llm_sample.py`
  - Answer expectation parser, deterministic answer scorer, real/fake LLM sample harness, report writers.
- Create: `scripts/run_memory_llm_sample_eval.py`
  - Explicitly gated CLI for real LLM sample runs.
- Create: `tests/test_memory_eval_llm_sample.py`
  - Unit/integration tests using fake providers only.
- Create: `tests/test_memory_llm_sample_cli.py`
  - CLI gate/report tests using fake mode only.
- Modify: `my_md/memory_optimization/README.md`
  - Record Phase6b-3 scope and results.
- Modify: `my_md/memory_optimization/02-memory-quality-metrics.md`
  - Add answer-quality and cost/latency metric definitions.
- Modify: `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
  - Mark Phase6b-3 implemented after verification.

---

## Answer Expectations

Add an optional `answer_expectations` object under `expectations`. Existing validation accepts extra fields, so this is backward compatible.

Use this shape:

```json
"answer_expectations": {
  "expected_answer_contains": ["中文"],
  "forbidden_answer_contains": ["英文回答"],
  "expected_memory_ids": ["m_pref_cn"],
  "expected_language": "zh",
  "grounding_required": true
}
```

Initial fixture edits:

Use only these three stable first-batch cases:

`preference_recall.json`:

```json
"answer_expectations": {
  "expected_answer_contains": ["中文"],
  "forbidden_answer_contains": ["英文回答", "English"],
  "expected_memory_ids": ["m_pref_cn"],
  "expected_language": "zh",
  "grounding_required": true
}
```

`cross_scope_isolation.json`:

```json
"answer_expectations": {
  "expected_answer_contains": ["Telegram", "中文"],
  "forbidden_answer_contains": ["QQ", "更短"],
  "expected_memory_ids": ["m_tg_pref"],
  "expected_language": "zh",
  "grounding_required": true
}
```

`vague_reference_graph.json`:

```json
"answer_expectations": {
  "expected_answer_contains": ["RRF", "三路召回"],
  "forbidden_answer_contains": [],
  "expected_memory_ids": ["m_graph_1", "m_graph_2"],
  "expected_language": "zh",
  "grounding_required": true
}
```

Do not add answer-quality scoring for `conflict_memory.json` in Phase6b-3 first batch. It contains two active conflicting memories, `m_like_cn` and `m_dislike_cn`, so there is no single deterministic correct answer until a later fixture marks one memory as superseded, lower confidence, or otherwise resolved. `injection_governance_budget.json` can be added in a later batch after this 3-case path is stable.

---

### Task 1: Answer Expectations and Deterministic Scorer

**Files:**
- Modify: `tests/fixtures/memory_eval_cases/preference_recall.json`
- Modify: `tests/fixtures/memory_eval_cases/cross_scope_isolation.json`
- Modify: `tests/fixtures/memory_eval_cases/vague_reference_graph.json`
- Create: `memory2/eval_llm_sample.py`
- Create: `tests/test_memory_eval_llm_sample.py`

**Interfaces:**
- Consumes:
  - `memory2.eval_cases.EvalCase`
- Produces:
  - `AnswerExpectation`
  - `AnswerScoreResult`
  - `answer_expectation_from_case(case: EvalCase) -> AnswerExpectation`
  - `score_answer_text(answer: str, expectation: AnswerExpectation, used_memory_ids: list[str]) -> AnswerScoreResult`

- [ ] **Step 1: Add answer expectations to three stable fixture files**

Edit only the `expectations` object and add `answer_expectations`. Keep existing fields intact.

For `tests/fixtures/memory_eval_cases/preference_recall.json`, add:

```json
"answer_expectations": {
  "expected_answer_contains": ["中文"],
  "forbidden_answer_contains": ["英文回答", "English"],
  "expected_memory_ids": ["m_pref_cn"],
  "expected_language": "zh",
  "grounding_required": true
}
```

For `tests/fixtures/memory_eval_cases/cross_scope_isolation.json`, add:

```json
"answer_expectations": {
  "expected_answer_contains": ["Telegram", "中文"],
  "forbidden_answer_contains": ["QQ", "更短"],
  "expected_memory_ids": ["m_tg_pref"],
  "expected_language": "zh",
  "grounding_required": true
}
```

For `tests/fixtures/memory_eval_cases/vague_reference_graph.json`, add:

```json
"answer_expectations": {
  "expected_answer_contains": ["RRF", "三路召回"],
  "forbidden_answer_contains": [],
  "expected_memory_ids": ["m_graph_1", "m_graph_2"],
  "expected_language": "zh",
  "grounding_required": true
}
```

Leave `tests/fixtures/memory_eval_cases/conflict_memory.json` unchanged in this phase because its active memories disagree with each other.

- [ ] **Step 2: Write failing scorer tests**

Create `tests/test_memory_eval_llm_sample.py` with tests for:

```python
def test_answer_expectation_from_case_reads_optional_fields():
    case = load_eval_case(Path("tests/fixtures/memory_eval_cases/preference_recall.json"))
    expectation = answer_expectation_from_case(case)
    assert "中文" in expectation.expected_answer_contains
    assert "m_pref_cn" in expectation.expected_memory_ids
    assert expectation.expected_language == "zh"


def test_score_answer_text_passes_expected_and_forbidden_rules():
    expectation = AnswerExpectation(
        expected_answer_contains=("中文",),
        forbidden_answer_contains=("英文回答",),
        expected_memory_ids=("m_pref_cn",),
        expected_language="zh",
        grounding_required=True,
    )
    result = score_answer_text("我应该用中文回答你。", expectation, ["m_pref_cn"])
    assert result.passed is True
    assert result.expected_contains_pass_count == 1
    assert result.forbidden_contains_violation_count == 0
    assert result.expected_memory_used is True


def test_score_answer_text_fails_forbidden_and_missing_memory():
    expectation = AnswerExpectation(
        expected_answer_contains=("中文",),
        forbidden_answer_contains=("英文回答",),
        expected_memory_ids=("m_pref_cn",),
        expected_language="zh",
        grounding_required=True,
    )
    result = score_answer_text("我会用英文回答。", expectation, [])
    assert result.passed is False
    assert result.forbidden_contains_violation_count == 1
    assert result.expected_memory_used is False
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_eval_llm_sample.py -q
```

Expected: fail because `memory2.eval_llm_sample` does not exist.

- [ ] **Step 4: Implement expectation parser and scorer**

Implement in `memory2/eval_llm_sample.py`:

```python
@dataclass(frozen=True)
class AnswerExpectation:
    expected_answer_contains: tuple[str, ...] = ()
    forbidden_answer_contains: tuple[str, ...] = ()
    expected_memory_ids: tuple[str, ...] = ()
    expected_language: str = ""
    grounding_required: bool = False


@dataclass(frozen=True)
class AnswerScoreResult:
    passed: bool
    expected_contains_pass_count: int
    expected_contains_miss_count: int
    forbidden_contains_violation_count: int
    expected_memory_used: bool
    language_passed: bool
    failures: tuple[str, ...]
```

Scoring rules:

- expected terms are case-insensitive substring checks for Latin text and direct substring checks for CJK.
- forbidden terms fail if any term appears.
- `expected_memory_used` passes if every expected memory id is in `used_memory_ids`.
- `expected_language == "zh"` passes when the answer contains at least one CJK character.
- `passed` is true only when all enabled checks pass.

- [ ] **Step 5: Run scorer tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_eval_llm_sample.py -q
```

Expected: scorer tests pass.

---

### Task 2: Real/Fake LLM Sample Harness

**Files:**
- Modify: `memory2/eval_llm_sample.py`
- Modify: `tests/test_memory_eval_llm_sample.py`

**Interfaces:**
- Consumes:
  - `AnswerExpectation`
  - `score_answer_text()`
  - existing `AgentLoop`
  - existing `LLMProvider`
  - fixture `EvalCase`
- Produces:
  - `LLMSampleCaseResult`
  - `LLMSampleReport`
  - `run_llm_sample_case(case: EvalCase, workspace: Path, provider: object, model: str, timeout_s: float = 60.0) -> LLMSampleCaseResult`
  - `run_llm_sample_cases(cases: Sequence[EvalCase], workspace: Path, provider: object, model: str, timeout_s: float = 60.0) -> LLMSampleReport`
  - `write_llm_sample_json(report: LLMSampleReport, path: Path) -> None`
  - `write_llm_sample_markdown(report: LLMSampleReport, path: Path) -> None`

- [ ] **Step 1: Add fake-provider harness tests**

Add tests using a fake provider that returns answer text and records call kwargs:

```python
class _FakeLLMProvider:
    def __init__(self, answer: str = "我应该用中文回答你。") -> None:
        self.answer = answer
        self.calls = []

    async def chat(self, **kwargs):
        self.calls.append(kwargs)
        return LLMResponse(content=self.answer, tool_calls=[], provider_fields={"usage": {"total_tokens": 12}})
```

Add tests:

- one case passes with fake provider answer,
- report includes `real_llm_enabled = false` for fake mode,
- report includes `answer_quality_available = true`,
- report includes `token_metrics_available = true` when fake usage metadata is present,
- report includes `token_metrics_available = false` when provider usage metadata is absent,
- report JSON and Markdown include no raw query, memory summary, fake answer text, prompt text, session text, API key string, or config value string,
- provider exception becomes sanitized `provider_error_count = 1`.

- [ ] **Step 2: Implement controlled memory engine for LLM answer runs**

Implement `LLMSampleMemoryEngine` in `memory2/eval_llm_sample.py`.

Differences from Phase6b-2 `CaseMemoryEngine`:

- It may inject memory summaries into `text_block` so the model has evidence.
- It must record only memory ids in report objects.
- It should set `MemoryHit.injected = True` for expected memory ids.
- It should expose `used_memory_ids` from the retrieved expected ids for deterministic scoring.

- [ ] **Step 3: Implement LLM sample run functions**

`run_llm_sample_case()` should:

1. Build real `AgentLoop`.
2. Use real `SessionManager` under temporary workspace.
3. Use caller-provided provider.
4. Run `loop.process_direct()` with `skip_post_memory=True`.
5. Measure latency with `time.perf_counter()`.
6. Score returned answer with `score_answer_text()`.
7. Record answer length, not answer text.
8. Record token metadata when available from `LLMResponse.cache_prompt_tokens`, `cache_hit_tokens`, or `provider_fields["usage"]`.
9. Catch provider timeout/error and store sanitized failure categories.
10. Set `token_metrics_available = true` only when at least one token count is present; otherwise keep prompt/completion/total token counts as `0` or `null` consistently in JSON and document the missing usage metadata in Markdown.

`run_llm_sample_cases()` should skip cases without `expectations.answer_expectations` before applying `limit`, so Phase6b-3 executes only the three stable answer-quality cases unless later fixtures explicitly add answer expectations.

- [ ] **Step 4: Implement report writers**

Report metrics:

```text
phase6b_level = "real_llm_small_sample"
real_llm_enabled
answer_quality_available
case_count
passed_case_count
failed_case_count
answer_contains_pass_count
answer_contains_miss_count
forbidden_contains_violation_count
expected_memory_used_count
language_pass_count
provider_error_count
timeout_count
total_latency_ms
avg_latency_ms
prompt_token_count
completion_token_count
total_token_count
token_metrics_available
raw_query_included = false
raw_memory_summary_included = false
prompt_included = false
session_text_included = false
full_answer_included = false
```

Case records:

```text
case_id
category
session_key
passed
answer_length
latency_ms
expected_memory_used
expected_contains_pass_count
expected_contains_miss_count
forbidden_contains_violation_count
language_passed
token_counts
token_metrics_available
failures
```

- [ ] **Step 5: Run harness tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_eval_llm_sample.py -q
```

Expected: all fake-provider tests pass.

---

### Task 3: Explicitly Gated CLI

**Files:**
- Create: `scripts/run_memory_llm_sample_eval.py`
- Create: `tests/test_memory_llm_sample_cli.py`

**Interfaces:**
- Consumes:
  - `memory2.eval_cases.load_eval_cases`
  - `memory2.eval_llm_sample.run_llm_sample_cases`
  - `agent.config.load_config`
  - `agent.provider.LLMProvider`
- Produces:
  - `memory_llm_sample_eval.json`
  - `memory_llm_sample_eval.md`
  - `build_provider_for_llm_sample(args: argparse.Namespace) -> tuple[object | None, str | None]`

- [ ] **Step 1: Write direct provider-gate tests**

Create `tests/test_memory_llm_sample_cli.py`.

Direct tests must import the CLI module and monkeypatch `agent.provider.LLMProvider` with a sentinel that raises if constructed.

Required direct tests:

- `build_provider_for_llm_sample()` with neither `--enable-real-llm` nor `--fake-provider` returns no provider and does not construct `LLMProvider`.
- `build_provider_for_llm_sample()` with `--fake-provider` returns the deterministic fake provider and does not read API key/config values.
- `build_provider_for_llm_sample()` with `--enable-real-llm` is the only path allowed to load config and construct `LLMProvider`.

- [ ] **Step 2: Write subprocess CLI behavior tests**

Subprocess tests must cover:

- CLI without `--enable-real-llm` exits `1` and writes a report with `real_llm_enabled = false`.
- CLI with `--fake-provider` runs the 3 stable fixture cases and exits `0`.
- CLI reports recursively omit raw query, memory summary, fake answer text, prompt text, session text, API key string, and config value string from both JSON and Markdown outputs.

Do not attempt to prove provider construction behavior through subprocess monkeypatching; that guarantee belongs to the direct function tests. Do not call a real provider in pytest.

- [ ] **Step 3: Implement CLI**

CLI shape:

```bash
.venv/bin/python scripts/run_memory_llm_sample_eval.py \
  --case-root tests/fixtures/memory_eval_cases \
  --workspace /tmp/akashic-memory-llm-eval \
  --out-dir my_md/memory_optimization/eval_reports \
  --config config.toml \
  --limit 3 \
  --enable-real-llm
```

Flags:

- `--enable-real-llm`: required for real provider calls.
- `--fake-provider`: test mode; uses deterministic fake provider and never reads API key.
- `--case-root`: defaults to fixture root.
- `--workspace`: required.
- `--out-dir`: defaults to `my_md/memory_optimization/eval_reports`.
- `--config`: defaults to `config.toml`.
- `--limit`: default `3`.
- `--timeout-s`: default `60`.

Behavior:

- If neither `--enable-real-llm` nor `--fake-provider` is present, write a gated report and exit `1`.
- If `--fake-provider` is present, run without real LLM and set `real_llm_enabled = false`.
- If `--enable-real-llm` is present, load config and instantiate `LLMProvider`.
- If config has no API key, write sanitized failure report and exit `1`.
- Select only fixtures with `expectations.answer_expectations`, then apply `--limit`.
- Exit `0` only if at least one case ran and all executed cases passed.

- [ ] **Step 4: Run CLI tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_llm_sample_cli.py -q
```

Expected: tests pass without network.

- [ ] **Step 5: Run fake-provider CLI locally**

Run:

```bash
.venv/bin/python scripts/run_memory_llm_sample_eval.py \
  --case-root tests/fixtures/memory_eval_cases \
  --workspace /tmp/akashic-memory-llm-eval-fake \
  --out-dir my_md/memory_optimization/eval_reports \
  --limit 3 \
  --fake-provider
```

Expected:

- exit code `0`
- writes `memory_llm_sample_eval.json`
- writes `memory_llm_sample_eval.md`
- report has `real_llm_enabled = false`

---

### Task 4: Manual Real LLM Run

**Files:**
- No code files required.
- Generated: `my_md/memory_optimization/eval_reports/memory_llm_sample_eval.json`
- Generated: `my_md/memory_optimization/eval_reports/memory_llm_sample_eval.md`

**Interfaces:**
- Consumes:
  - `config.toml` with valid provider/API key
  - explicit `--enable-real-llm`
- Produces:
  - first real LLM answer-quality small-sample report

- [ ] **Step 1: Confirm clean gate command**

Run without enabling real LLM:

```bash
.venv/bin/python scripts/run_memory_llm_sample_eval.py \
  --case-root tests/fixtures/memory_eval_cases \
  --workspace /tmp/akashic-memory-llm-eval-real \
  --out-dir my_md/memory_optimization/eval_reports \
  --limit 3
```

Expected:

- exit code `1`
- report says real LLM is disabled
- no provider call occurs

- [ ] **Step 2: Run manual real LLM sample only after user approval**

Run:

```bash
.venv/bin/python scripts/run_memory_llm_sample_eval.py \
  --case-root tests/fixtures/memory_eval_cases \
  --workspace /tmp/akashic-memory-llm-eval-real \
  --out-dir my_md/memory_optimization/eval_reports \
  --config config.toml \
  --limit 3 \
  --timeout-s 60 \
  --enable-real-llm
```

Expected:

- exit code `0` if all 3 cases pass,
- exit code `1` if any case fails or provider fails,
- report records real LLM metrics without full answer text.

Do not run this command inside automated tests.

---

### Task 5: Documentation, Verification, and Commit

**Files:**
- Modify: `my_md/memory_optimization/README.md`
- Modify: `my_md/memory_optimization/02-memory-quality-metrics.md`
- Modify: `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
- Add generated reports if produced:
  - `my_md/memory_optimization/eval_reports/memory_llm_sample_eval.json`
  - `my_md/memory_optimization/eval_reports/memory_llm_sample_eval.md`

**Interfaces:**
- Consumes:
  - Task 3 fake-provider report
  - Task 4 manual real LLM report if executed
- Produces:
  - Updated project memory optimization docs

- [ ] **Step 1: Update docs**

Record:

- Phase6b-3 boundaries.
- Whether the report is fake-provider or real-LLM.
- Number of cases.
- pass/fail counts.
- latency/token/provider error metrics.
- explicit note that this is small-sample and not production traffic.

- [ ] **Step 2: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_memory_eval_cases.py \
  tests/test_memory_eval_runner.py \
  tests/test_memory_eval_real_samples.py \
  tests/test_memory_eval_real_candidates.py \
  tests/test_memory_eval_real_report.py \
  tests/test_memory_real_sample_eval_cli.py \
  tests/test_memory_eval_agent_dry_run.py \
  tests/test_memory_agent_dry_run_cli.py \
  tests/test_memory_eval_llm_sample.py \
  tests/test_memory_llm_sample_cli.py \
  -q
```

Expected: all tests pass without real LLM calls.

- [ ] **Step 3: Run compile and diff checks**

Run:

```bash
.venv/bin/python -m compileall memory2 tests scripts -q
git diff --check
```

Expected: both commands exit `0`.

- [ ] **Step 4: Stage and commit**

Do not stage `uv.lock`.

```bash
git add \
  memory2/eval_llm_sample.py \
  scripts/run_memory_llm_sample_eval.py \
  tests/test_memory_eval_llm_sample.py \
  tests/test_memory_llm_sample_cli.py \
  tests/fixtures/memory_eval_cases/preference_recall.json \
  tests/fixtures/memory_eval_cases/cross_scope_isolation.json \
  tests/fixtures/memory_eval_cases/vague_reference_graph.json \
  my_md/memory_optimization/README.md \
  my_md/memory_optimization/02-memory-quality-metrics.md \
  my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md \
  my_md/memory_optimization/eval_reports/memory_llm_sample_eval.json \
  my_md/memory_optimization/eval_reports/memory_llm_sample_eval.md
git add -f \
  docs/superpowers/plans/2026-07-17-memory-phase6b3-real-llm-small-sample.md
git commit -m "feat: add memory real llm sample evaluation"
```

Expected: commit succeeds; `git status --short` only shows pre-existing `uv.lock` unless new unrelated user changes appear.

---

## Self-Review

- Spec coverage: plan covers answer expectations, deterministic scoring, fake-provider tests, explicit real LLM gate, manual real LLM run, reports, docs, and verification.
- Red-flag scan: no deferred-detail markers or unspecified implementation steps remain.
- Type consistency: exported names are consistent across tasks.
- Safety check: real LLM is opt-in only through `--enable-real-llm`, and automated tests use fake providers only.
- Scope check: LLM-as-judge, Dashboard, production traffic evaluation, active gates, and real user memory DB evaluation are explicitly out of scope.
