# P6o-16 System Path Answer Guidance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a production-safe, explicitly gated answer guidance variant for system-path safe version replace, then validate whether it improves answer-rule pass rate without increasing forbidden leakage.

**Architecture:** Keep retrieval and candidate governance unchanged. Add an optional guidance rendering layer to `system_path_safe_version_contract`, wire one boolean through `MemoryConfig`, `DefaultMemoryRetrievalPipeline`, `DefaultMemoryEngine`, and the system-path eval harness, and compare `current`, `safe_version_replace`, and `safe_version_replace_guided` on the bounded common 20 + hard 20 case pack.

**Tech Stack:** Python dataclasses, pytest, existing `AgentLoop` system-path eval harness, existing checkpoint JSONL resume/report-only flow, existing markdown/json report writers.

## Global Constraints

- Branch/worktree: execute only in `/home/jjh/git_work/akashic-agent/.worktrees/memory-next` on branch `memory-next`.
- Protected untracked path: do not stage, delete, or modify `my_md/memory_optimization/eval_reports/p6o13_system_path_real_llm_validation_v1/`.
- Production default remains off: no guidance text is rendered unless an explicit config/eval flag enables it.
- Runtime guidance must not use fixture answer expectations, expected answer terms, expected memory ids, case query text, full prompt, full answer, or oracle-derived labels.
- Model-visible contract text must not expose raw forbidden/deleted/superseded ids.
- Reports must remain sanitized: no raw prompt, query, session text, memory summaries, full answers, API keys, or secrets.
- No graph-all-on, no new retrieval lanes, no retry/fallback behavior, no production activation by session metadata.
- P6o-16 success gate: `safe_version_replace_guided` has 0 provider errors, 0 timeouts, grounding rate at least `safe_version_replace`, forbidden violation rate equal to `safe_version_replace` and no higher than `0.0`, answer rate greater than `safe_version_replace`, and average total tokens no more than `safe_version_replace + 5%`.

---

## File Structure

- Modify `memory2/system_path_safe_version_contract.py`: add optional answer guidance rendering and auditable metadata.
- Modify `plugins/default_memory/engine.py`: read a sanitized guidance hint, pass it to contract builder, and expose metadata.
- Modify `agent/looping/ports.py`: add `MemoryConfig.safe_version_answer_guidance_enabled: bool = False`.
- Modify `agent/looping/core.py`: pass the new config into `DefaultMemoryRetrievalPipeline`.
- Modify `agent/retrieval/default_pipeline.py`: gate guidance from config only and pass it to engine hints only when safe version mode is replace with replace allowed.
- Modify `memory2/eval_system_path_safe_version.py`: add `safe_version_replace_guided` mode, include guidance metadata in sanitized reports, and enable post-check shadow for the guided mode.
- Modify `scripts/run_memory_system_path_safe_version_eval.py`: keep CLI unchanged except accepting the new mode through the existing `--modes` string.
- Modify tests:
  - `tests/test_memory_system_path_safe_version_contract.py`
  - `tests/test_memory_engine_contract.py`
  - `tests/test_turn_pipelines.py`
  - `tests/test_memory_system_path_safe_version_eval.py`
- Create report directory `my_md/memory_optimization/eval_reports/p6o16_system_path_answer_guidance_v1/`.
- Update documentation:
  - `my_md/memory_optimization/README.md`
  - `my_md/memory_optimization/progress.md`
  - add `my_md/memory_optimization/eval_reports/p6o16_system_path_answer_guidance_v1/system_path_answer_guidance_report.md`.

---

### Task 1: Contract Guidance Flag

**Files:**
- Modify: `memory2/system_path_safe_version_contract.py`
- Test: `tests/test_memory_system_path_safe_version_contract.py`

**Interfaces:**
- Consumes: `SystemPathEvidenceContract`, `render_system_path_evidence_contract_block(contract)`, `build_system_path_safe_version_contract(...)`.
- Produces:
  - `build_system_path_safe_version_contract(..., answer_guidance_enabled: bool = False) -> SystemPathSafeVersionResult`
  - `render_system_path_evidence_contract_block(contract, *, answer_guidance_enabled: bool = False) -> str`
  - `system_path_contract_to_dict(contract, *, answer_guidance_enabled: bool = False) -> dict[str, object]`
  - Dict key `answer_guidance_enabled: bool`

- [ ] **Step 1: Add failing tests for default-off and guided rendering**

Add these tests to `tests/test_memory_system_path_safe_version_contract.py`:

```python
def test_system_path_answer_guidance_is_default_off() -> None:
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
    )

    assert "Answer Guidance:" not in result.text_block
    assert system_path_contract_to_dict(result.contract)["answer_guidance_enabled"] is False


def test_system_path_answer_guidance_is_production_safe_and_private() -> None:
    result = build_system_path_safe_version_contract(
        query="测试偏好是什么？",
        baseline_items=[_item("m-current", "用户偏好使用 pytest。")],
        route_trace={
            "candidates_by_lane": {
                "semantic": [
                    _item("m-current", "用户偏好使用 pytest。"),
                    _item("blocked-id", "禁止使用 nose。", forbidden=True),
                ],
                "keyword": [],
                "provenance": [],
                "graph": [],
            }
        },
        replacements=[],
        top_k=8,
        answer_guidance_enabled=True,
    )

    text = result.text_block
    payload = system_path_contract_to_dict(
        result.contract,
        answer_guidance_enabled=True,
    )

    assert "Answer Guidance:" in text
    assert "Use allowed_evidence as the only source for the answer." in text
    assert "State concrete facts from allowed_evidence directly." in text
    assert "Answer in the user's language." in text
    assert "blocked-id" not in text
    assert "forbidden_boundary_ids:" not in text
    assert "deleted_evidence_ids:" not in text
    assert payload["answer_guidance_enabled"] is True
    assert payload["uses_fixture_answer_expectations"] is False
```

- [ ] **Step 2: Run the contract tests and verify failure**

Run:

```bash
pytest tests/test_memory_system_path_safe_version_contract.py -q
```

Expected: the two new tests fail because `answer_guidance_enabled` is not implemented yet.

- [ ] **Step 3: Implement minimal contract guidance**

Change `memory2/system_path_safe_version_contract.py` as follows:

```python
def build_system_path_safe_version_contract(
    *,
    query: str,
    baseline_items: Sequence[Mapping[str, Any]],
    route_trace: Mapping[str, Any],
    replacements: Sequence[Mapping[str, Any]] = (),
    top_k: int = 8,
    answer_guidance_enabled: bool = False,
) -> SystemPathSafeVersionResult:
```

Render and trace with the flag:

```python
    guidance_enabled = bool(answer_guidance_enabled)
    return SystemPathSafeVersionResult(
        contract=contract,
        text_block=render_system_path_evidence_contract_block(
            contract,
            answer_guidance_enabled=guidance_enabled,
        ),
        accepted_items=tuple(dict(item) for item in accepted),
        trace={
            "safe_version_governed": system_path_contract_to_dict(
                contract,
                answer_guidance_enabled=guidance_enabled,
            )
        },
    )
```

Change the renderer signature and append guidance only when enabled:

```python
def render_system_path_evidence_contract_block(
    contract: SystemPathEvidenceContract,
    *,
    answer_guidance_enabled: bool = False,
) -> str:
    lines = [
        f"Evidence Contract: {contract.profile_name}",
        "production_safe=true",
        "uses_fixture_answer_expectations=false",
        "candidate_governance_mode: " + contract.candidate_governance_mode,
        "allowed_evidence:",
        *_indent_lines(contract.allowed_evidence),
        "likely_relevant_evidence_count: " + str(len(contract.likely_relevant_evidence_ids)),
        "active_version_count: " + str(len(contract.active_version_ids)),
        "stale_warning_count: " + str(len(contract.stale_warning_ids)),
        "conflict_warning_count: " + str(len(contract.conflict_warning_ids)),
        "forbidden_boundary_count: " + str(len(contract.forbidden_boundary_ids)),
        "deleted_evidence_count: " + str(len(contract.deleted_evidence_ids)),
        "insufficient_evidence_fallback: "
        + ("true" if contract.insufficient_evidence_fallback else "false"),
        (
            "Instruction: answer only from allowed_evidence. If evidence is "
            "insufficient, say that the available memory is insufficient. Do not "
            "use deleted, superseded, cross-scope, or forbidden boundary evidence."
        ),
    ]
    if bool(answer_guidance_enabled):
        lines.extend(
            [
                "Answer Guidance:",
                "  Use allowed_evidence as the only source for the answer.",
                "  State concrete facts from allowed_evidence directly.",
                "  Prefer active versions when active_version_count is greater than 0.",
                "  If the evidence is insufficient, say the available memory is insufficient.",
                "  Do not mention deleted, superseded, or forbidden boundary evidence.",
                "  Answer in the user's language.",
            ]
        )
    return "\n".join(lines)
```

Change the dict helper:

```python
def system_path_contract_to_dict(
    contract: SystemPathEvidenceContract,
    *,
    answer_guidance_enabled: bool = False,
) -> dict[str, object]:
    return {
        "profile_name": contract.profile_name,
        "production_safe": contract.production_safe,
        "production_safe_evidence_contract": contract.production_safe,
        "uses_fixture_answer_expectations": contract.uses_fixture_answer_expectations,
        "answer_guidance_enabled": bool(answer_guidance_enabled),
        ...
    }
```

- [ ] **Step 4: Run the contract tests and verify pass**

Run:

```bash
pytest tests/test_memory_system_path_safe_version_contract.py -q
```

Expected: all tests in the file pass.

---

### Task 2: Engine and Pipeline Gating

**Files:**
- Modify: `plugins/default_memory/engine.py`
- Modify: `agent/looping/ports.py`
- Modify: `agent/looping/core.py`
- Modify: `agent/retrieval/default_pipeline.py`
- Test: `tests/test_memory_engine_contract.py`
- Test: `tests/test_turn_pipelines.py`

**Interfaces:**
- Consumes: Task 1 `answer_guidance_enabled` builder parameter and contract dict key.
- Produces:
  - `MemoryConfig.safe_version_answer_guidance_enabled: bool = False`
  - `DefaultMemoryRetrievalPipeline(..., safe_version_answer_guidance_enabled: bool = False)`
  - Engine hint `safe_version_answer_guidance_enabled: bool`
  - Metadata key `answer_guidance_enabled: bool`

- [ ] **Step 1: Add failing engine tests**

Add to `tests/test_memory_engine_contract.py`:

```python
@pytest.mark.asyncio
async def test_default_memory_engine_safe_version_guidance_requires_replace_mode() -> None:
    items = [
        {
            "id": "m-current",
            "summary": "用户偏好使用 pytest。",
            "score": 0.91,
            "source_ref": "telegram:1:1",
            "memory_type": "preference",
            "status": "active",
            "extra_json": {},
        }
    ]
    route_trace = {
        "candidates_by_lane": {
            "semantic": items,
            "keyword": [],
            "provenance": [],
            "graph": [],
        }
    }
    retriever = SimpleNamespace(
        retrieve_with_lanes=AsyncMock(return_value=(items, items, [])),
        retrieve_with_trace=AsyncMock(return_value=(items, route_trace)),
        build_injection_block=MagicMock(
            return_value=("baseline memory block", ["m-current"])
        ),
    )
    engine = _make_default_engine(retriever=cast(Any, retriever))
    engine._v2_store = SimpleNamespace(list_replacements=MagicMock(return_value=[]))

    result = await engine.retrieve(
        MemoryEngineRetrieveRequest(
            query="我默认用什么测试框架？",
            scope=MemoryScope(session_key="s", channel="telegram", chat_id="1"),
            hints={
                "safe_version_governed_mode": "shadow",
                "safe_version_answer_guidance_enabled": True,
            },
            top_k=8,
        )
    )

    metadata = result.raw["safe_version_governed_metadata"]
    assert metadata["mode"] == "shadow"
    assert metadata["answer_guidance_enabled"] is False
    assert "Answer Guidance:" not in result.text_block


@pytest.mark.asyncio
async def test_default_memory_engine_safe_version_replace_guidance_changes_contract_text() -> None:
    items = [
        {
            "id": "m-current",
            "summary": "用户偏好使用 pytest。",
            "score": 0.91,
            "source_ref": "telegram:1:1",
            "memory_type": "preference",
            "status": "active",
            "extra_json": {},
        }
    ]
    route_trace = {
        "candidates_by_lane": {
            "semantic": items,
            "keyword": [],
            "provenance": [],
            "graph": [],
        }
    }
    retriever = SimpleNamespace(
        retrieve_with_lanes=AsyncMock(return_value=(items, items, [])),
        retrieve_with_trace=AsyncMock(return_value=(items, route_trace)),
        build_injection_block=MagicMock(
            return_value=("baseline memory block", ["m-current"])
        ),
    )
    engine = _make_default_engine(retriever=cast(Any, retriever))
    engine._v2_store = SimpleNamespace(list_replacements=MagicMock(return_value=[]))

    result = await engine.retrieve(
        MemoryEngineRetrieveRequest(
            query="我默认用什么测试框架？",
            scope=MemoryScope(session_key="s", channel="telegram", chat_id="1"),
            hints={
                "safe_version_governed_mode": "replace",
                "safe_version_governed_replace_allowed": True,
                "safe_version_answer_guidance_enabled": True,
            },
            top_k=8,
        )
    )

    metadata = result.raw["safe_version_governed_metadata"]
    contract = result.raw["safe_version_governed_shadow"]
    assert metadata["answer_guidance_enabled"] is True
    assert contract["answer_guidance_enabled"] is True
    assert "Answer Guidance:" in result.text_block
    assert "forbidden_boundary_ids:" not in result.text_block
    assert "deleted_evidence_ids:" not in result.text_block
```

- [ ] **Step 2: Add failing pipeline tests**

Add to `tests/test_turn_pipelines.py`:

```python
@pytest.mark.asyncio
async def test_retrieval_pipeline_passes_safe_version_guidance_only_from_config() -> None:
    engine = _FakeMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(
        MemoryServices(engine=engine),
        safe_version_governed_mode="replace",
        safe_version_governed_replace_allowed=True,
        safe_version_answer_guidance_enabled=True,
    )
    request = _retrieval_request("我默认用什么测试框架？")
    request.session_metadata["safe_version_answer_guidance_enabled"] = False

    await pipeline.retrieve(request)

    assert engine.requests[-1].hints["safe_version_governed_mode"] == "replace"
    assert engine.requests[-1].hints["safe_version_governed_replace_allowed"] is True
    assert engine.requests[-1].hints["safe_version_answer_guidance_enabled"] is True


@pytest.mark.asyncio
async def test_retrieval_pipeline_ignores_session_guidance_escalation() -> None:
    engine = _FakeMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(
        MemoryServices(engine=engine),
        safe_version_governed_mode="replace",
        safe_version_governed_replace_allowed=True,
        safe_version_answer_guidance_enabled=False,
    )
    request = _retrieval_request("我默认用什么测试框架？")
    request.session_metadata["safe_version_answer_guidance_enabled"] = True

    await pipeline.retrieve(request)

    assert engine.requests[-1].hints["safe_version_governed_mode"] == "replace"
    assert "safe_version_answer_guidance_enabled" not in engine.requests[-1].hints


@pytest.mark.asyncio
async def test_retrieval_pipeline_ignores_extra_guidance_escalation() -> None:
    engine = _RecordingMemoryEngine()
    pipeline = DefaultMemoryRetrievalPipeline(
        MemoryServices(engine=engine),
        safe_version_governed_mode="replace",
        safe_version_governed_replace_allowed=True,
        safe_version_answer_guidance_enabled=False,
    )
    request = _retrieval_request("我默认用什么测试框架？")
    request.extra["safe_version_answer_guidance_enabled"] = True

    await pipeline.retrieve(request)

    assert engine.requests[-1].hints["safe_version_governed_mode"] == "replace"
    assert "safe_version_answer_guidance_enabled" not in engine.requests[-1].hints
```

Add to `test_agent_loop_passes_safe_version_config_to_default_retrieval_pipeline`:

```python
                safe_version_answer_guidance_enabled=True,
```

and assert:

```python
    assert loop._retrieval_pipeline._safe_version_answer_guidance_enabled is True
```

- [ ] **Step 3: Run engine and pipeline tests and verify failure**

Run:

```bash
pytest tests/test_memory_engine_contract.py tests/test_turn_pipelines.py -q
```

Expected: new tests fail because the config and hint do not exist yet.

- [ ] **Step 4: Implement the gating path**

In `agent/looping/ports.py`, change `MemoryConfig`:

```python
class MemoryConfig:
    window: int = 40
    safe_version_governed_mode: str = "off"
    safe_version_governed_replace_allowed: bool = False
    safe_version_answer_guidance_enabled: bool = False
```

In `agent/looping/core.py`, pass the config:

```python
            safe_version_answer_guidance_enabled=(
                config.memory.safe_version_answer_guidance_enabled
            ),
```

In `agent/retrieval/default_pipeline.py`, add the constructor parameter and field:

```python
        safe_version_answer_guidance_enabled: bool = False,
```

```python
        self._safe_version_answer_guidance_enabled = bool(
            safe_version_answer_guidance_enabled
        )
```

When building hints, remove caller-provided safe-version control keys before applying config:

```python
        hints = dict(request.extra or {})
        hints.pop("safe_version_governed_mode", None)
        hints.pop("safe_version_governed_replace_allowed", None)
        hints.pop("safe_version_answer_guidance_enabled", None)
```

Then only add the guidance flag from config:

```python
            if (
                safe_mode == "replace"
                and replace_allowed
                and self._safe_version_answer_guidance_enabled
            ):
                hints["safe_version_answer_guidance_enabled"] = True
```

In `plugins/default_memory/engine.py`, compute guidance as replace-only:

```python
        answer_guidance_enabled = (
            safe_mode == "replace"
            and replace_allowed
            and bool(request.hints.get("safe_version_answer_guidance_enabled", False))
        )
```

Pass it to the builder:

```python
                    answer_guidance_enabled=answer_guidance_enabled,
```

Build the auditable contract dict with the same flag:

```python
                safe_shadow = system_path_contract_to_dict(
                    safe_result.contract,
                    answer_guidance_enabled=answer_guidance_enabled,
                )
```

Add to `safe_metadata`:

```python
                    "answer_guidance_enabled": answer_guidance_enabled,
```

Also add `"answer_guidance_enabled": False` to the exception metadata path.

- [ ] **Step 5: Run engine and pipeline tests and verify pass**

Run:

```bash
pytest tests/test_memory_engine_contract.py tests/test_turn_pipelines.py -q
```

Expected: all tests in both files pass.

---

### Task 3: Eval Harness Guided Mode

**Files:**
- Modify: `memory2/eval_system_path_safe_version.py`
- Modify: `scripts/run_memory_system_path_safe_version_eval.py`
- Test: `tests/test_memory_system_path_safe_version_eval.py`

**Interfaces:**
- Consumes: Task 2 `MemoryConfig.safe_version_answer_guidance_enabled`.
- Produces:
  - Eval mode `safe_version_replace_guided`
  - Sanitized metadata key `answer_guidance_enabled`
  - Guided mode included in post-check shadow

- [ ] **Step 1: Add failing eval CLI test**

Add to `tests/test_memory_system_path_safe_version_eval.py`:

```python
def test_system_path_safe_version_cli_supports_replace_guided_mode(tmp_path: Path) -> None:
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
            "safe_version_replace,safe_version_replace_guided",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        (out_dir / "system_path_safe_version_eval.json").read_text(encoding="utf-8")
    )
    summaries = payload["metrics"]["mode_summaries"]
    assert summaries["safe_version_replace"]["case_count"] == 2
    assert summaries["safe_version_replace_guided"]["case_count"] == 2
    guided_rows = [
        row for row in payload["cases"] if row["mode"] == "safe_version_replace_guided"
    ]
    assert guided_rows
    assert all(
        row["safe_version_metadata"]["answer_guidance_enabled"] is True
        for row in guided_rows
    )
    assert all(
        row["safe_version_contract"]["answer_guidance_enabled"] is True
        for row in guided_rows
    )
    assert all(
        row["post_check_shadow"]["shadow_enabled"] is True
        for row in guided_rows
    )
```

- [ ] **Step 2: Run eval test and verify failure**

Run:

```bash
pytest tests/test_memory_system_path_safe_version_eval.py::test_system_path_safe_version_cli_supports_replace_guided_mode -q
```

Expected: fails with unknown mode or missing metadata.

- [ ] **Step 3: Implement guided eval mode**

In `memory2/eval_system_path_safe_version.py`, update `MODE_TO_SAFE_VERSION`:

```python
MODE_TO_SAFE_VERSION = {
    "current": "off",
    "safe_version_shadow": "shadow",
    "safe_version_replace": "replace",
    "safe_version_replace_guided": "replace",
}
```

When building `MemoryConfig`, set:

```python
                safe_version_governed_replace_allowed=(
                    mode in {"safe_version_replace", "safe_version_replace_guided"}
                ),
                safe_version_answer_guidance_enabled=(
                    mode == "safe_version_replace_guided"
                ),
```

Enable post-check for guided mode:

```python
    if mode in {
        "safe_version_shadow",
        "safe_version_replace",
        "safe_version_replace_guided",
    } and contract:
```

Add `"answer_guidance_enabled"` to `_sanitize_metadata()` and `_sanitize_contract()` allowed keys.

- [ ] **Step 4: Run eval tests and verify pass**

Run:

```bash
pytest tests/test_memory_system_path_safe_version_eval.py -q
```

Expected: all system-path eval tests pass.

---

### Task 4: Verification Matrix and Privacy Gates

**Files:**
- No source files unless a test exposes a defect.
- Create: `my_md/memory_optimization/eval_reports/p6o16_system_path_answer_guidance_v1/`

**Interfaces:**
- Consumes: Tasks 1-3 implementation.
- Produces:
  - fake smoke JSON/MD report
  - real small A/B JSON/MD report
  - checkpoint JSONL for resumability

- [ ] **Step 1: Run focused tests**

Run:

```bash
pytest \
  tests/test_memory_system_path_safe_version_contract.py \
  tests/test_memory_engine_contract.py \
  tests/test_turn_pipelines.py \
  tests/test_memory_system_path_safe_version_eval.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run fake-provider shape smoke**

Run:

```bash
python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace /tmp/akashic-p6o16-fake-workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o16_system_path_answer_guidance_v1/fake_smoke \
  --fake-provider \
  --balanced-small \
  --common-limit 2 \
  --hard-limit 2 \
  --modes current,safe_version_replace,safe_version_replace_guided
```

Expected:
- command exits `0`
- JSON and markdown files are written
- metrics show `unique_case_count = 4`, `mode_count = 3`, `case_count = 12`
- `safe_version_replace_guided` rows have `answer_guidance_enabled = true`

- [ ] **Step 3: Run privacy scan on fake smoke**

Run:

```bash
rg -n "\"(raw_prompt|prompt|full_answer|raw_answer|session_text|memory_summary|raw_memory_summary|api_key|authorization|secret)\"" \
  my_md/memory_optimization/eval_reports/p6o16_system_path_answer_guidance_v1/fake_smoke
```

Expected: no matches.

- [ ] **Step 4: Run real small A/B with checkpoint**

Run:

```bash
python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace /tmp/akashic-p6o16-real-workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o16_system_path_answer_guidance_v1/real_small_ab \
  --enable-real-llm \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --modes current,safe_version_replace,safe_version_replace_guided \
  --timeout-s 30 \
  --repeats 1 \
  --checkpoint-jsonl my_md/memory_optimization/eval_reports/p6o16_system_path_answer_guidance_v1/real_small_ab/checkpoint.jsonl \
  --resume
```

Expected:
- command exits `0`
- metrics show `unique_case_count = 40`, `mode_count = 3`, `case_count = 120`, `repeat_count = 1`
- `provider_error_count = 0`
- `timeout_count = 0`

- [ ] **Step 5: Check the real A/B gate**

Run:

```bash
python - <<'PY'
import json
from pathlib import Path

path = Path("my_md/memory_optimization/eval_reports/p6o16_system_path_answer_guidance_v1/real_small_ab/system_path_safe_version_eval.json")
payload = json.loads(path.read_text(encoding="utf-8"))
metrics = payload["metrics"]
summaries = metrics["mode_summaries"]
replace = summaries["safe_version_replace"]
guided = summaries["safe_version_replace_guided"]
token_limit = round(float(replace["avg_total_token_count"]) * 1.05, 4)
gate_passed = (
    int(metrics["provider_error_count"]) == 0
    and int(metrics["timeout_count"]) == 0
    and float(guided["memory_grounding_pass_rate"]) >= float(replace["memory_grounding_pass_rate"])
    and float(guided["forbidden_violation_rate"]) == float(replace["forbidden_violation_rate"])
    and float(guided["forbidden_violation_rate"]) <= 0.0
    and float(guided["answer_rule_pass_rate"]) > float(replace["answer_rule_pass_rate"])
    and float(guided["avg_total_token_count"]) <= token_limit
)
print(json.dumps({
    "gate_passed": gate_passed,
    "replace_answer_rate": replace["answer_rule_pass_rate"],
    "guided_answer_rate": guided["answer_rule_pass_rate"],
    "replace_forbidden_rate": replace["forbidden_violation_rate"],
    "guided_forbidden_rate": guided["forbidden_violation_rate"],
    "replace_grounding_rate": replace["memory_grounding_pass_rate"],
    "guided_grounding_rate": guided["memory_grounding_pass_rate"],
    "guided_avg_tokens": guided["avg_total_token_count"],
    "token_limit": token_limit,
}, ensure_ascii=False, indent=2, sort_keys=True))
if not gate_passed:
    raise SystemExit(2)
PY
```

Expected:
- if the gate passes, command exits `0` and docs should mark guided as passed
- if the gate fails, command exits `2`; continue to Task 5 documentation, but mark guided as failed and keep production default off

- [ ] **Step 6: Rebuild report from checkpoint**

Run:

```bash
python scripts/run_memory_system_path_safe_version_eval.py \
  --out-dir my_md/memory_optimization/eval_reports/p6o16_system_path_answer_guidance_v1/real_small_ab_rebuilt \
  --enable-real-llm \
  --checkpoint-jsonl my_md/memory_optimization/eval_reports/p6o16_system_path_answer_guidance_v1/real_small_ab/checkpoint.jsonl \
  --checkpoint-report-only
```

Expected:
- command exits `0`
- rebuilt metrics match the primary real small A/B on case count and mode summaries

- [ ] **Step 7: Run privacy scan on real reports**

Run:

```bash
rg -n "\"(raw_prompt|prompt|raw_query|query|full_answer|raw_answer|session_text|memory_summary|raw_memory_summary|api_key|authorization|secret)\"" \
  my_md/memory_optimization/eval_reports/p6o16_system_path_answer_guidance_v1/real_small_ab \
  my_md/memory_optimization/eval_reports/p6o16_system_path_answer_guidance_v1/real_small_ab_rebuilt
```

Expected: no matches.

- [ ] **Step 8: Run value-based privacy scan on real reports**

Run:

```bash
python - <<'PY'
import json
from pathlib import Path
from memory2.eval_quantitative_cases import build_quantitative_eval_cases

base = Path("my_md/memory_optimization/eval_reports/p6o16_system_path_answer_guidance_v1")
report_text = (
    (base / "real_small_ab" / "system_path_safe_version_eval.json").read_text(encoding="utf-8")
    + "\n"
    + (base / "real_small_ab" / "system_path_safe_version_eval.md").read_text(encoding="utf-8")
    + "\n"
    + (base / "real_small_ab_rebuilt" / "system_path_safe_version_eval.json").read_text(encoding="utf-8")
    + "\n"
    + (base / "real_small_ab_rebuilt" / "system_path_safe_version_eval.md").read_text(encoding="utf-8")
)
cases = (
    build_quantitative_eval_cases("common", case_pack="standard", limit=20)
    + build_quantitative_eval_cases("hard", case_pack="standard", limit=20)
)
leaks = []
for case in cases:
    setup = case.setup
    values = [str(setup.get("query") or "").strip()]
    for item in setup.get("memory_items", []):
        if isinstance(item, dict):
            values.append(str(item.get("summary") or "").strip())
    for replacement in setup.get("memory_replacements", []):
        if isinstance(replacement, dict):
            values.append(str(replacement.get("old_summary") or "").strip())
            values.append(str(replacement.get("new_summary") or "").strip())
    leaks.extend(value for value in values if value and value in report_text)
print(json.dumps({"leak_count": len(leaks)}, ensure_ascii=False, sort_keys=True))
if leaks:
    raise SystemExit(1)
PY
```

Expected: `{"leak_count": 0}`.

---

### Task 5: Documentation and Final Verification

**Files:**
- Create: `my_md/memory_optimization/eval_reports/p6o16_system_path_answer_guidance_v1/system_path_answer_guidance_report.md`
- Modify: `my_md/memory_optimization/README.md`
- Modify: `my_md/memory_optimization/progress.md`

**Interfaces:**
- Consumes: Task 4 fake and real report metrics.
- Produces: durable P6o-16 record with method, data, conclusion, and next-step decision.

- [ ] **Step 1: Extract metrics from real report**

Run:

```bash
python - <<'PY'
import json
from pathlib import Path
path = Path("my_md/memory_optimization/eval_reports/p6o16_system_path_answer_guidance_v1/real_small_ab/system_path_safe_version_eval.json")
payload = json.loads(path.read_text(encoding="utf-8"))
print(json.dumps(payload["metrics"], ensure_ascii=False, indent=2, sort_keys=True))
PY
```

Expected: printed metrics include mode summaries for `current`, `safe_version_replace`, and `safe_version_replace_guided`.

- [ ] **Step 2: Write the P6o-16 report from metrics**

Run:

```bash
python - <<'PY'
import json
from pathlib import Path

base = Path("my_md/memory_optimization/eval_reports/p6o16_system_path_answer_guidance_v1")
payload = json.loads(
    (base / "real_small_ab" / "system_path_safe_version_eval.json").read_text(
        encoding="utf-8"
    )
)
metrics = payload["metrics"]
summaries = metrics["mode_summaries"]
replace = summaries["safe_version_replace"]
guided = summaries["safe_version_replace_guided"]

token_limit = round(float(replace["avg_total_token_count"]) * 1.05, 4)
gate_passed = (
    int(metrics["provider_error_count"]) == 0
    and int(metrics["timeout_count"]) == 0
    and float(guided["memory_grounding_pass_rate"]) >= float(replace["memory_grounding_pass_rate"])
    and float(guided["forbidden_violation_rate"]) == float(replace["forbidden_violation_rate"])
    and float(guided["forbidden_violation_rate"]) <= 0.0
    and float(guided["answer_rule_pass_rate"]) > float(replace["answer_rule_pass_rate"])
    and float(guided["avg_total_token_count"]) <= token_limit
)
conclusion = (
    "safe_version_replace_guided passed the P6o-16 gate: answer guidance improved answer rate while preserving grounding, forbidden control, and token budget."
    if gate_passed
    else "safe_version_replace_guided did not pass the P6o-16 gate: keep production default off and treat guidance as an eval-only candidate until failure attribution shows the next bounded fix."
)
next_step = (
    "Prepare a config-gated shadow rollout plan that records guided-vs-unguided answer post-check deltas without changing production replies."
    if gate_passed
    else "Run failure attribution on guided misses against safe_version_replace misses, then revise the answer guidance wording or scoring boundary before another real A/B."
)

def row(mode: str) -> str:
    data = summaries[mode]
    return (
        f"| {mode} | {data['case_count']} | {data['answer_rule_pass_rate']} | "
        f"{data['memory_grounding_pass_rate']} | {data['forbidden_violation_rate']} | "
        f"{data['contract_generation_success_rate']} | {data['post_check_shadow_enabled_rate']} | "
        f"{data['avg_total_token_count']} | {data['avg_latency_ms']} |"
    )

report = "\n".join(
    [
        "# P6o-16 System Path Answer Guidance",
        "",
        "## Purpose",
        "",
        "Validate whether production-safe answer guidance can improve answer-rule pass rate after P6o-15 showed that safe version replace already controls forbidden leakage but still misses some required answer terms.",
        "",
        "## Method",
        "",
        "- Case pack: standard balanced small, common 20 + hard 20.",
        "- Modes: current, safe_version_replace, safe_version_replace_guided.",
        "- Repeats: 1.",
        "- Real calls: 40 unique cases * 3 modes * 1 repeat = 120.",
        "- Checkpoint: real_small_ab/checkpoint.jsonl.",
        "- Reports exclude raw prompt, query, session text, memory summaries, full answers, and secrets.",
        "",
        "## Results",
        "",
        "| mode | cases | answer_rate | grounding_rate | forbidden_rate | contract_success | post_check_shadow | avg_tokens | avg_latency_ms |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        row("current"),
        row("safe_version_replace"),
        row("safe_version_replace_guided"),
        "",
        "## Gate",
        "",
        f"- provider_error_count: {metrics['provider_error_count']}.",
        f"- timeout_count: {metrics['timeout_count']}.",
        "- guided forbidden must stay at 0.0.",
        "- guided grounding must not regress below safe_version_replace.",
        "- guided answer rate must exceed safe_version_replace.",
        f"- guided avg tokens must be no more than safe_version_replace + 5%, threshold {token_limit}.",
        f"- gate_passed: {str(gate_passed).lower()}.",
        "",
        "## Conclusion",
        "",
        conclusion,
        "",
        "## Next Step",
        "",
        next_step,
        "",
    ]
)
(base / "system_path_answer_guidance_report.md").write_text(report, encoding="utf-8")
print(base / "system_path_answer_guidance_report.md")
PY
```

Expected: the report file is written and includes the actual metrics, gate decision, conclusion, and next step derived from the real A/B JSON.

- [ ] **Step 3: Update README and progress**

Add a P6o-16 entry to `my_md/memory_optimization/README.md` and `my_md/memory_optimization/progress.md` that includes:
- tested modes
- 120-call real matrix
- answer/grounding/forbidden/token conclusion
- whether guided replace passed or failed the gate
- next recommended step

- [ ] **Step 4: Run final source verification**

Run:

```bash
pytest \
  tests/test_memory_system_path_safe_version_contract.py \
  tests/test_memory_engine_contract.py \
  tests/test_turn_pipelines.py \
  tests/test_memory_system_path_safe_version_eval.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Run formatting and privacy verification**

Run:

```bash
git diff --check
rg -n "\"(raw_prompt|prompt|full_answer|raw_answer|session_text|memory_summary|raw_memory_summary|api_key|authorization|secret)\"" \
  my_md/memory_optimization/eval_reports/p6o16_system_path_answer_guidance_v1
```

Expected:
- `git diff --check` exits `0`
- `rg` exits `1` with no matches

- [ ] **Step 6: Summarize uncommitted state**

Run:

```bash
git status --short
```

Expected: source, tests, report, and docs changes are visible; protected untracked P6o-13 path remains unmodified and unstaged.
