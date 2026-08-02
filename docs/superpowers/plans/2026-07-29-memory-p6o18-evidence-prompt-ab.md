# P6o-18 Evidence Prompt A/B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add eval/config-gated system-path memory evidence prompt variants and run a bounded real LLM A/B to test whether better evidence presentation improves answer selection when grounding is already `100.0%`.

**Architecture:** Keep safe-version replacement as the retrieval and evidence safety layer. Add one normalized prompt-variant hint that is only emitted from trusted config/eval mode, render two new model-facing evidence block variants, expose sanitized metadata for reporting, and extend the existing system-path eval runner with new modes. Do not change the global system prompt or production default activation.

**Tech Stack:** Python 3.14 via `.venv/bin/python`, existing `AgentLoop` system path, `DefaultMemoryRetrievalPipeline`, `DefaultMemoryEngine`, `memory2.system_path_safe_version_contract`, `scripts/run_memory_system_path_safe_version_eval.py`, pytest, JSON/Markdown reports.

## Global Constraints

- Branch/worktree: execute only in `/home/jjh/git_work/akashic-agent/.worktrees/memory-next` on branch `memory-next`.
- Preserve all existing uncommitted P6o-16/P6o-17 work.
- Protected untracked path: do not stage, delete, edit, or move `my_md/memory_optimization/eval_reports/p6o13_system_path_real_llm_validation_v1/`.
- Production default remains `MemoryConfig.safe_version_governed_mode = "off"`.
- New prompt variants must be config/eval-gated; `request.extra` and `session_metadata` must not enable replace, guidance, or prompt variants.
- Do not change global system prompt, tool prompts, production write behavior, retry, fallback, graph/all-on, or retrieval lanes.
- `near_query_block` in P6o-18 means a question-proximal evidence block wording inside the existing context-frame order. It does not change `MessageEnvelopeBuilder` message ordering.
- Reports must stay sanitized: no raw prompt, raw query, session text, memory summaries, full answers, API keys, authorization values, or secrets.
- Real LLM config path is `/home/jjh/git_work/akashic-agent/config.toml`; never copy or print config contents.
- P6o-18 prompt variant precedence: a non-`standard` prompt variant is active only when safe-version mode is trusted `replace`, replace is allowed, and `safe_version_answer_guidance_enabled = true` in config/eval mode. If guidance is disabled, the effective variant is `standard`.
- P6o-18 exploratory success gate: complete `160` real rows, zero provider errors, zero timeouts, token metrics available on every row and every mode, all variant metadata correct, rebuilt checkpoint has `160` valid input rows and `0` malformed rows, primary/rebuilt summaries match, grounding no lower than `100.0%`, forbidden equal to `0.0%`, at least one new prompt variant has answer rate greater than `safe_version_replace_guided`, and winning variant avg tokens are no more than `safe_version_replace` + `8%`.

---

## File Structure

- Modify: `agent/looping/ports.py`
  - Add `MemoryConfig.safe_version_answer_prompt_variant: str = "standard"`.
- Modify: `agent/looping/core.py`
  - Pass `safe_version_answer_prompt_variant` to `DefaultMemoryRetrievalPipeline`.
- Modify: `agent/retrieval/default_pipeline.py`
  - Normalize configured prompt variant and pass it only through trusted config-gated hints.
  - Continue stripping caller-provided safe-version hint escalation from `request.extra`.
- Modify: `plugins/default_memory/engine.py`
  - Read `safe_version_answer_prompt_variant` from engine hints.
  - Pass it into `build_system_path_safe_version_contract()`.
  - Include sanitized metadata for `answer_prompt_variant`.
- Modify: `memory2/system_path_safe_version_contract.py`
  - Add prompt variant normalization.
  - Render `standard`, `guided`, `structured_guided`, and `near_query_block`.
  - Store canonical `answer_prompt_variant` on `SystemPathEvidenceContract`.
  - Include `answer_prompt_variant` in contract dict without requiring callers to pass the variant again.
- Create: `scripts/check_memory_p6o18_gate.py`
  - Reproducibly validate primary/rebuilt reports and write `gate_decision.json` plus `evidence_prompt_ab_report.md`.
- Modify: `memory2/eval_system_path_safe_version.py`
  - Add eval modes `safe_version_replace_structured_guided` and `safe_version_replace_near_query_block`.
  - Include new modes in replace/post-check/guidance logic and sanitized metadata.
- Modify: `tests/test_memory_system_path_safe_version_contract.py`
  - Add prompt variant rendering and privacy tests.
- Modify: `tests/test_memory_engine_contract.py`
  - Add engine-level prompt variant config/hint tests.
- Modify: `tests/test_turn_pipelines.py`
  - Add retrieval pipeline tests proving `request.extra` and `session_metadata` cannot enable prompt variants.
- Modify: `tests/test_memory_system_path_safe_version_eval.py`
  - Add CLI fake-provider mode shape tests for four P6o-18 modes.
- Create report directory: `my_md/memory_optimization/eval_reports/p6o18_evidence_prompt_ab_v1/`.
- Modify docs after execution:
  - `my_md/memory_optimization/README.md`
  - `progress.md`

---

### Task 1: Add Prompt Variant Contract Rendering

**Files:**
- Modify: `memory2/system_path_safe_version_contract.py`
- Modify: `tests/test_memory_system_path_safe_version_contract.py`

**Interfaces:**
- Consumes: existing `build_system_path_safe_version_contract(..., answer_guidance_enabled: bool)`.
- Produces: backward-compatible `build_system_path_safe_version_contract(..., answer_prompt_variant: str = "standard")`.
- Produces normalized variants: `standard`, `guided`, `structured_guided`, `near_query_block`.
- Produces sanitized contract field: `answer_prompt_variant`.
- Rule: `SystemPathEvidenceContract.answer_prompt_variant` is the canonical normalized value.

- [ ] **Step 1: Write failing contract tests**

Add these tests to `tests/test_memory_system_path_safe_version_contract.py`:

```python
def test_system_path_structured_guided_variant_groups_answer_critical_evidence() -> None:
    result = build_system_path_safe_version_contract(
        query="测试偏好是什么？",
        baseline_items=[_item("m-current", "用户偏好使用 pytest。")],
        route_trace={
            "candidates_by_lane": {
                "semantic": [_item("m-current", "用户偏好使用 pytest。")],
                "keyword": [],
                "provenance": [],
                "graph": [],
            }
        },
        replacements=[],
        top_k=8,
        answer_prompt_variant="structured_guided",
    )

    text = result.text_block
    payload = system_path_contract_to_dict(
        result.contract,
    )

    assert "Structured Answer Guidance:" in text
    assert "answer_critical_evidence:" in text
    assert "用户偏好使用 pytest。" in text
    assert "active_allowed_evidence_count: 1" in text
    assert "Use answer_critical_evidence first." in text
    assert payload["answer_guidance_enabled"] is True
    assert payload["answer_prompt_variant"] == "structured_guided"
    assert "m-current" not in text
```

Add:

```python
def test_system_path_near_query_variant_marks_next_user_message_scope() -> None:
    result = build_system_path_safe_version_contract(
        query="测试偏好是什么？",
        baseline_items=[_item("m-current", "用户偏好使用 pytest。")],
        route_trace={
            "candidates_by_lane": {
                "semantic": [_item("m-current", "用户偏好使用 pytest。")],
                "keyword": [],
                "provenance": [],
                "graph": [],
            }
        },
        replacements=[],
        top_k=8,
        answer_prompt_variant="near_query_block",
    )

    text = result.text_block
    assert "Question-Proximal Memory Evidence:" in text
    assert "Use this block for the immediately following user request." in text
    assert "Do not use deleted, superseded, cross-scope, or forbidden boundary evidence." in text
    assert system_path_contract_to_dict(
        result.contract,
    )["answer_prompt_variant"] == "near_query_block"
```

Add:

```python
def test_system_path_standard_variant_keeps_p6o17_baseline_text() -> None:
    result = build_system_path_safe_version_contract(
        query="测试偏好是什么？",
        baseline_items=[_item("m-current", "用户偏好使用 pytest。")],
        route_trace={
            "candidates_by_lane": {
                "semantic": [_item("m-current", "用户偏好使用 pytest。")],
                "keyword": [],
                "provenance": [],
                "graph": [],
            }
        },
        replacements=[],
        top_k=8,
        answer_prompt_variant="standard",
    )

    assert "Answer Guidance:" not in result.text_block
    assert "Structured Answer Guidance:" not in result.text_block
    assert "Question-Proximal Memory Evidence:" not in result.text_block
    assert system_path_contract_to_dict(result.contract)["answer_prompt_variant"] == "standard"
```

- [ ] **Step 2: Verify contract tests fail for missing variant support**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_system_path_safe_version_contract.py::test_system_path_structured_guided_variant_groups_answer_critical_evidence \
  tests/test_memory_system_path_safe_version_contract.py::test_system_path_near_query_variant_marks_next_user_message_scope \
  -q -p no:cacheprovider
```

Expected: fails because `answer_prompt_variant` is not accepted or variant text is missing.

- [ ] **Step 3: Implement normalized prompt variants**

In `memory2/system_path_safe_version_contract.py`:

```python
SAFE_VERSION_ANSWER_PROMPT_VARIANTS = {
    "standard",
    "guided",
    "structured_guided",
    "near_query_block",
}


def normalize_safe_version_answer_prompt_variant(
    value: object,
    *,
    answer_guidance_enabled: bool = False,
) -> str:
    variant = str(value or "").strip()
    if not variant:
        return "guided" if bool(answer_guidance_enabled) else "standard"
    if variant not in SAFE_VERSION_ANSWER_PROMPT_VARIANTS:
        return "guided" if bool(answer_guidance_enabled) else "standard"
    return variant
```

Update `build_system_path_safe_version_contract()` to accept `answer_prompt_variant: str = "standard"`, normalize it, and pass it into `render_system_path_evidence_contract_block()` and `system_path_contract_to_dict()`.

Add `answer_prompt_variant: str` to `SystemPathEvidenceContract`, and set it to the normalized value during contract construction. `system_path_contract_to_dict(result.contract)` must preserve the variant without caller-supplied parameters.

Update `render_system_path_evidence_contract_block()` to accept `answer_prompt_variant: str = "standard"` and render:
- `standard`: current block without `Answer Guidance`.
- `guided`: current `Answer Guidance` block.
- `structured_guided`: current safety counts plus `Structured Answer Guidance`, `answer_critical_evidence`, `active_allowed_evidence_count`, and active/critical usage instructions.
- `near_query_block`: current safety counts plus `Question-Proximal Memory Evidence` and instructions scoped to the immediately following user request.

Update `system_path_contract_to_dict()` to include:

```python
"answer_guidance_enabled": contract.answer_prompt_variant != "standard",
"answer_prompt_variant": contract.answer_prompt_variant,
```

- [ ] **Step 4: Verify contract tests pass**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_system_path_safe_version_contract.py \
  -q -p no:cacheprovider
```

Expected: all contract tests pass.

---

### Task 2: Gate Prompt Variants Through Config And Engine

**Files:**
- Modify: `agent/looping/ports.py`
- Modify: `agent/looping/core.py`
- Modify: `agent/retrieval/default_pipeline.py`
- Modify: `plugins/default_memory/engine.py`
- Modify: `tests/test_turn_pipelines.py`
- Modify: `tests/test_memory_engine_contract.py`

**Interfaces:**
- Consumes: `normalize_safe_version_answer_prompt_variant()`.
- Produces: trusted hint `safe_version_answer_prompt_variant`.
- Security rule: caller-provided `request.extra` and `session_metadata` cannot enable prompt variants.

- [ ] **Step 1: Write failing pipeline and engine tests**

Add to `tests/test_turn_pipelines.py`:

```python
async def test_safe_version_answer_prompt_variant_flows_from_config_only() -> None:
    engine = _RecordingMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(
        MemoryServices(engine=engine),
        safe_version_governed_mode="replace",
        safe_version_governed_replace_allowed=True,
        safe_version_answer_guidance_enabled=True,
        safe_version_answer_prompt_variant="structured_guided",
    )
    request = _retrieval_request("我默认用什么测试框架？")

    await pipeline.retrieve(request)

    assert engine.requests[-1].hints["safe_version_governed_mode"] == "replace"
    assert engine.requests[-1].hints["safe_version_answer_guidance_enabled"] is True
    assert engine.requests[-1].hints["safe_version_answer_prompt_variant"] == "structured_guided"
```

Add to `tests/test_turn_pipelines.py`:

```python
async def test_safe_version_answer_prompt_variant_extra_cannot_escalate() -> None:
    engine = _RecordingMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(
        MemoryServices(engine=engine),
        safe_version_governed_mode="replace",
        safe_version_governed_replace_allowed=True,
        safe_version_answer_guidance_enabled=False,
        safe_version_answer_prompt_variant="standard",
    )
    request = _retrieval_request("我默认用什么测试框架？")
    request.extra["safe_version_answer_prompt_variant"] = "structured_guided"

    await pipeline.retrieve(request)

    assert engine.requests[-1].hints["safe_version_governed_mode"] == "replace"
    assert "safe_version_answer_prompt_variant" not in engine.requests[-1].hints
```

Add to `tests/test_turn_pipelines.py`:

```python
async def test_safe_version_answer_prompt_variant_session_metadata_cannot_escalate() -> None:
    engine = _RecordingMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(
        MemoryServices(engine=engine),
        safe_version_governed_mode="replace",
        safe_version_governed_replace_allowed=True,
        safe_version_answer_guidance_enabled=False,
        safe_version_answer_prompt_variant="standard",
    )
    request = _retrieval_request("我默认用什么测试框架？")
    request.session_metadata["safe_version_answer_prompt_variant"] = "structured_guided"

    await pipeline.retrieve(request)

    assert engine.requests[-1].hints["safe_version_governed_mode"] == "replace"
    assert "safe_version_answer_prompt_variant" not in engine.requests[-1].hints
```

Add to `tests/test_turn_pipelines.py`:

```python
async def test_safe_version_answer_prompt_variant_requires_guidance_gate() -> None:
    engine = _RecordingMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(
        MemoryServices(engine=engine),
        safe_version_governed_mode="replace",
        safe_version_governed_replace_allowed=True,
        safe_version_answer_guidance_enabled=False,
        safe_version_answer_prompt_variant="structured_guided",
    )

    await pipeline.retrieve(_retrieval_request("我默认用什么测试框架？"))

    assert engine.requests[-1].hints["safe_version_governed_mode"] == "replace"
    assert "safe_version_answer_guidance_enabled" not in engine.requests[-1].hints
    assert "safe_version_answer_prompt_variant" not in engine.requests[-1].hints
```

Add an engine-level test to `tests/test_memory_engine_contract.py` that retrieves with hints:

```python
{
    "safe_version_governed_mode": "replace",
    "safe_version_governed_replace_allowed": True,
    "safe_version_answer_guidance_enabled": True,
    "safe_version_answer_prompt_variant": "structured_guided",
}
```

Assert:

```python
metadata["answer_guidance_enabled"] is True
metadata["answer_prompt_variant"] == "structured_guided"
contract["answer_prompt_variant"] == "structured_guided"
"Structured Answer Guidance:" in result.text_block
```

- [ ] **Step 2: Verify new config/engine tests fail**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_turn_pipelines.py::test_safe_version_answer_prompt_variant_flows_from_config_only \
  tests/test_turn_pipelines.py::test_safe_version_answer_prompt_variant_extra_cannot_escalate \
  -q -p no:cacheprovider
```

Expected: fails because `MemoryConfig.safe_version_answer_prompt_variant` and hint propagation do not exist yet.

- [ ] **Step 3: Implement config-gated prompt variant propagation**

In `agent/looping/ports.py`, add:

```python
safe_version_answer_prompt_variant: str = "standard"
```

In `agent/looping/core.py`, pass it into `DefaultMemoryRetrievalPipeline`.

In `agent/retrieval/default_pipeline.py`:
- accept `safe_version_answer_prompt_variant: str = "standard"` in `__init__`;
- normalize with `normalize_safe_version_answer_prompt_variant()`;
- strip `safe_version_answer_prompt_variant` from `request.extra`;
- emit `hints["safe_version_answer_prompt_variant"]` only when safe mode is trusted replace, replace is allowed, and normalized variant is not `standard`.

In `plugins/default_memory/engine.py`:
- read normalized `answer_prompt_variant` from `request.hints`;
- only allow non-standard variant when `safe_mode == "replace"`, `replace_allowed`, and `safe_version_answer_guidance_enabled` is true;
- pass `answer_prompt_variant` into `build_system_path_safe_version_contract()` and `system_path_contract_to_dict()`;
- include `answer_prompt_variant` in `safe_metadata`.

- [ ] **Step 4: Verify config/engine tests pass**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_turn_pipelines.py tests/test_memory_engine_contract.py \
  -q -p no:cacheprovider
```

Expected: all selected tests pass.

---

### Task 3: Add P6o-18 Eval Modes And Smoke Gate

**Files:**
- Modify: `memory2/eval_system_path_safe_version.py`
- Modify: `tests/test_memory_system_path_safe_version_eval.py`

**Interfaces:**
- Produces modes:
  - `safe_version_replace`
  - `safe_version_replace_guided`
  - `safe_version_replace_structured_guided`
  - `safe_version_replace_near_query_block`

- [ ] **Step 1: Write failing CLI mode test**

Add to `tests/test_memory_system_path_safe_version_eval.py`:

```python
def test_system_path_safe_version_cli_supports_p6o18_prompt_variants(
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
            (
                "safe_version_replace,safe_version_replace_guided,"
                "safe_version_replace_structured_guided,"
                "safe_version_replace_near_query_block"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        (out_dir / "system_path_safe_version_eval.json").read_text(encoding="utf-8")
    )
    assert payload["metrics"]["mode_count"] == 4
    assert payload["metrics"]["case_count"] == 8
    expected = {
        "safe_version_replace": "standard",
        "safe_version_replace_guided": "guided",
        "safe_version_replace_structured_guided": "structured_guided",
        "safe_version_replace_near_query_block": "near_query_block",
    }
    for row in payload["cases"]:
        assert row["safe_version_contract"]["answer_prompt_variant"] == expected[row["mode"]]
```

- [ ] **Step 2: Verify CLI mode test fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_system_path_safe_version_eval.py::test_system_path_safe_version_cli_supports_p6o18_prompt_variants \
  -q -p no:cacheprovider
```

Expected: fails because new modes are unknown.

- [ ] **Step 3: Implement eval modes**

In `memory2/eval_system_path_safe_version.py`:
- add new modes to `MODE_TO_SAFE_VERSION`;
- add helper `_mode_answer_prompt_variant(mode: str) -> str`;
- set `safe_version_governed_replace_allowed=True` for all replace-family modes;
- set `safe_version_answer_guidance_enabled=True` for non-standard variants;
- set `safe_version_answer_prompt_variant` to the helper value;
- include the new modes in post-check shadow mode set.
- add `answer_prompt_variant` to `_sanitize_metadata()` and `_sanitize_contract()`.

- [ ] **Step 4: Verify eval tests pass**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_system_path_safe_version_eval.py \
  -q -p no:cacheprovider
```

Expected: all eval tests pass.

---

### Task 4: Add Reproducible Gate Checker

**Files:**
- Create: `scripts/check_memory_p6o18_gate.py`
- Test manually with real/fake reports in Task 5.

**Interfaces:**
- Consumes: primary report path, rebuilt report path, output directory.
- Produces: `gate_decision.json` and `evidence_prompt_ab_report.md`.
- Exits nonzero if report shape is malformed or primary/rebuilt metrics do not match.
- Exits zero when shape is valid, even if exploratory `gate_passed = false`, so docs can record failed A/B data.

- [ ] **Step 1: Create gate checker script**

Create `scripts/check_memory_p6o18_gate.py` with arguments:

```bash
--primary-json PATH
--rebuilt-json PATH
--out-dir PATH
```

The script must check:
- primary `case_count = 160`, `unique_case_count = 40`, `mode_count = 4`, `repeat_count = 1`;
- primary `provider_error_count = 0`, `timeout_count = 0`;
- rebuilt `checkpoint_input_count = 160`, `malformed_checkpoint_line_count = 0`, `case_count = 160`;
- primary/rebuilt `mode_summaries` match exactly;
- every row has `token_metrics_available = true`;
- every mode summary has `token_metrics_available = true`;
- every row's `safe_version_contract.answer_prompt_variant` and `safe_version_metadata.answer_prompt_variant` match its mode;
- every row's `safe_version_contract.answer_guidance_enabled` is false only for `safe_version_replace`;
- grounding is `100.0%` for every mode;
- forbidden is `0.0%` for every mode.

The gate passes when at least one of `safe_version_replace_structured_guided` or `safe_version_replace_near_query_block` has answer rate greater than `safe_version_replace_guided`, and the best new variant avg tokens are no more than `safe_version_replace` + `8%`.

- [ ] **Step 2: Ensure script has no raw text output**

The script output files must contain aggregate metrics only:
- no raw prompt;
- no raw query;
- no session text;
- no memory summaries;
- no full answers;
- no API keys or authorization values.

---

### Task 5: Run P6o-18 Fake Smoke And Real Small A/B

**Files:**
- Create: `my_md/memory_optimization/eval_reports/p6o18_evidence_prompt_ab_v1/fake_smoke/`
- Create: `my_md/memory_optimization/eval_reports/p6o18_evidence_prompt_ab_v1/real_small_ab/`
- Create: `my_md/memory_optimization/eval_reports/p6o18_evidence_prompt_ab_v1/real_small_ab_rebuilt/`
- Create: `my_md/memory_optimization/eval_reports/p6o18_evidence_prompt_ab_v1/gate_decision.json`
- Create: `my_md/memory_optimization/eval_reports/p6o18_evidence_prompt_ab_v1/evidence_prompt_ab_report.md`

**Interfaces:**
- Consumes: four eval modes from Task 3.
- Produces: fake shape proof, real `160`-call A/B, checkpoint rebuild, gate decision, sanitized summary.

- [ ] **Step 1: Run fake-provider smoke**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace /tmp/akashic-p6o18-fake-workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o18_evidence_prompt_ab_v1/fake_smoke \
  --fake-provider \
  --balanced-small \
  --common-limit 2 \
  --hard-limit 2 \
  --modes safe_version_replace,safe_version_replace_guided,safe_version_replace_structured_guided,safe_version_replace_near_query_block
```

Expected: `case_count = 16`, `mode_count = 4`, zero infra failures, and all variant metadata matches mode names.

- [ ] **Step 2: Run real small A/B**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace /tmp/akashic-p6o18-real-workspace-v1 \
  --out-dir my_md/memory_optimization/eval_reports/p6o18_evidence_prompt_ab_v1/real_small_ab \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --enable-real-llm \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --modes safe_version_replace,safe_version_replace_guided,safe_version_replace_structured_guided,safe_version_replace_near_query_block \
  --timeout-s 30 \
  --checkpoint-jsonl my_md/memory_optimization/eval_reports/p6o18_evidence_prompt_ab_v1/real_small_ab/checkpoint.jsonl \
  --resume
```

Expected: `160` real rows, zero provider errors, zero timeouts.

- [ ] **Step 3: Rebuild from checkpoint**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_system_path_safe_version_eval.py \
  --out-dir my_md/memory_optimization/eval_reports/p6o18_evidence_prompt_ab_v1/real_small_ab_rebuilt \
  --config /home/jjh/git_work/akashic-agent/config.toml \
  --enable-real-llm \
  --checkpoint-jsonl my_md/memory_optimization/eval_reports/p6o18_evidence_prompt_ab_v1/real_small_ab/checkpoint.jsonl \
  --checkpoint-report-only
```

Expected: rebuilt metrics match primary mode summaries and `checkpoint_input_count = 160`.

- [ ] **Step 4: Compute gate and write summary**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_memory_p6o18_gate.py \
  --primary-json my_md/memory_optimization/eval_reports/p6o18_evidence_prompt_ab_v1/real_small_ab/system_path_safe_version_eval.json \
  --rebuilt-json my_md/memory_optimization/eval_reports/p6o18_evidence_prompt_ab_v1/real_small_ab_rebuilt/system_path_safe_version_eval.json \
  --out-dir my_md/memory_optimization/eval_reports/p6o18_evidence_prompt_ab_v1
```

Expected: report is written whether gate passes or fails.

- [ ] **Step 5: Run privacy scans**

Run:

```bash
rg -n '"(raw_prompt|prompt|raw_query|query|full_answer|raw_answer|session_text|memory_summary|raw_memory_summary|api_key|authorization|secret)"' \
  my_md/memory_optimization/eval_reports/p6o18_evidence_prompt_ab_v1
rg -in 'bearer|api[_-]?key|authorization|secret|token[[:space:]]*[:=]' \
  my_md/memory_optimization/eval_reports/p6o18_evidence_prompt_ab_v1
```

Expected: both scans have no matches and exit code `1`.

---

### Task 6: Documentation And Final Verification

**Files:**
- Modify: `my_md/memory_optimization/README.md`
- Modify: `progress.md`

**Interfaces:**
- Consumes: Task 4 reports.
- Produces: durable P6o-18 method/data/conclusion record.

- [ ] **Step 1: Update docs**

Add P6o-18 entries to `my_md/memory_optimization/README.md` and `progress.md` with:
- test method and matrix;
- per-mode answer/grounding/forbidden/token data;
- gate result;
- comparison against P6o-17;
- next-step recommendation.

- [ ] **Step 2: Final verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_system_path_safe_version_contract.py \
  tests/test_memory_engine_contract.py \
  tests/test_turn_pipelines.py \
  tests/test_memory_system_path_safe_version_eval.py \
  -q -p no:cacheprovider
git diff --check
git status --short -- my_md/memory_optimization/eval_reports/p6o13_system_path_real_llm_validation_v1/
```

Expected: pytest exits `0`, `git diff --check` exits `0`.

- [ ] **Step 3: Show final working tree**

Run:

```bash
git status --short --branch
```

Expected:
- P6o-18 code/report/docs changes are present.
- P6o-13 protected untracked path remains untouched.
