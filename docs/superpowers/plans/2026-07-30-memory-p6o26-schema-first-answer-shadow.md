# Memory P6o26 Schema First Answer Shadow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an eval/config-gated schema-first answer shadow mode to test whether structured fact selection before natural-language answering can lift system-path memory answer accuracy above the current `80%` guided ceiling.

**Architecture:** Keep the change inside the existing system-path safe-version eval harness. Add one new answer prompt variant, `schema_first_shadow`, and one eval mode, `safe_version_replace_schema_first_shadow`, that reuses safe-version replacement, active/current truth extraction, answer scoring, and post-check shadow telemetry without production retry or production default activation.

**Tech Stack:** Python, pytest, existing `memory2` eval harness, existing `scripts/run_memory_system_path_safe_version_eval.py`, Markdown reports under `my_md/memory_optimization`.

## Global Constraints

- Do not change production default: `MemoryConfig.safe_version_governed_mode` remains `off`.
- Do not add real retry/fallback execution.
- Do not expand recall, enable graph-all-on, change memory writes, or change global system prompt.
- Do not write raw prompt, raw answer, raw user query, raw session text, or sensitive config values to committed reports.
- New behavior must be reachable only through config/eval-controlled `safe_version_answer_prompt_variant`.
- Formal quality conclusions require fresh real LLM runs with `provider_error_count = 0`, `timeout_count = 0`, and sanitized reports.

---

### Task 1: Add Schema-First Prompt Variant

**Files:**
- Modify: `memory2/system_path_safe_version_contract.py`
- Test: `tests/test_memory_system_path_safe_version_contract.py`

**Interfaces:**
- Consumes: `build_system_path_safe_version_contract(..., answer_prompt_variant=...)`.
- Produces: normalized variant string `schema_first_shadow` and model-visible schema-first instructions.

- [ ] **Step 1: Write failing prompt-rendering test**

Add a test to `tests/test_memory_system_path_safe_version_contract.py`:

```python
def test_schema_first_shadow_renders_structured_selection_then_natural_answer() -> None:
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
        answer_prompt_variant="schema_first_shadow",
    )

    text = result.text_block
    payload = system_path_contract_to_dict(
        result.contract,
        answer_guidance_enabled=True,
    )

    assert payload["answer_prompt_variant"] == "schema_first_shadow"
    assert payload["answer_candidate_contract"]["enabled"] is True
    assert payload["answer_candidate_contract"]["current_truth_count"] == 1
    assert payload["answer_candidate_contract"]["must_include_term_count"] == 1
    assert "must_include_terms" not in payload["answer_candidate_contract"]
    assert "Schema-First Answer Shadow:" in text
    assert "First select the answer facts internally" in text
    assert "Then write only the final natural-language answer" in text
    assert "selected_facts" in text
    assert "ignored_superseded_or_stale" in text
    assert "Do not expose JSON" in text
    assert "用户当前偏好使用 pytest。" in text
    assert "m-current" not in text
    assert "m-old" not in text
```

- [ ] **Step 2: Verify the test fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_memory_system_path_safe_version_contract.py::test_schema_first_shadow_renders_structured_selection_then_natural_answer -q -p no:cacheprovider
```

Expected: fails because `schema_first_shadow` normalizes away or instructions are missing.

- [ ] **Step 3: Implement minimal prompt variant**

In `memory2/system_path_safe_version_contract.py`:

- Add `"schema_first_shadow"` to `SAFE_VERSION_ANSWER_PROMPT_VARIANTS`.
- Enable `AnswerCandidateContract` for both `guided_retry_shadow` and `schema_first_shadow`.
- Add a render branch that includes:
  - allowed evidence only.
  - internal structured fields: `selected_facts`, `active_version_used`, `ignored_superseded_or_stale`, `insufficient_evidence`.
  - instruction to output only final natural-language answer, not JSON.
  - current truth lines from `candidate.current_truth_lines`.

- [ ] **Step 4: Verify the test passes**

Run the same pytest command. Expected: pass.

### Task 2: Add Eval Mode And Post-Check Telemetry

**Files:**
- Modify: `memory2/eval_system_path_safe_version.py`
- Test: `tests/test_memory_system_path_safe_version_eval.py`

**Interfaces:**
- Consumes: CLI `--modes safe_version_replace_schema_first_shadow`.
- Produces: report rows with `answer_prompt_variant = schema_first_shadow`, `answer_candidate_contract.enabled = true`, and scorer-driven retry reason counts.

- [ ] **Step 1: Write failing CLI mode test**

Add a test to `tests/test_memory_system_path_safe_version_eval.py`:

```python
def test_system_path_safe_version_cli_supports_schema_first_shadow_mode(
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
            "safe_version_replace,safe_version_replace_guided,safe_version_replace_schema_first_shadow",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        (out_dir / "system_path_safe_version_eval.json").read_text(encoding="utf-8")
    )
    schema = payload["metrics"]["mode_summaries"][
        "safe_version_replace_schema_first_shadow"
    ]
    assert schema["case_count"] == 2
    assert schema["answer_candidate_contract_enabled_rate"] == 100.0
    assert schema["would_retry_count"] == 2
    assert schema["retry_reason_counts"]["required_terms_missing"] == 2
    assert schema["retry_reason_counts"]["answer_choice_group_missing"] == 2
    rows = [
        row
        for row in payload["cases"]
        if row["mode"] == "safe_version_replace_schema_first_shadow"
    ]
    assert rows
    assert all(
        row["safe_version_contract"]["answer_prompt_variant"] == "schema_first_shadow"
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
    assert all(row["post_check_shadow"]["required_terms_missing"] is True for row in rows)
    assert all(row["post_check_shadow"]["answer_choice_group_missing"] is True for row in rows)
    _assert_report_is_private(
        payload,
        (out_dir / "system_path_safe_version_eval.md").read_text(encoding="utf-8"),
    )
```

- [ ] **Step 2: Verify the test fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_memory_system_path_safe_version_eval.py::test_system_path_safe_version_cli_supports_schema_first_shadow_mode -q -p no:cacheprovider
```

Expected: fails because mode is not wired.

- [ ] **Step 3: Implement mode wiring**

In `memory2/eval_system_path_safe_version.py`:

- Add `safe_version_replace_schema_first_shadow` to `MODE_TO_SAFE_VERSION` with value `"replace"`.
- Add it to `REPLACE_FAMILY_MODES`.
- Map it in `_mode_answer_prompt_variant()` to `"schema_first_shadow"`.
- Treat it like retry-shadow for `answer_score` attachment so post-check can count `required_terms_missing`, `answer_choice_group_missing`, and `language_requirement_failed`.

- [ ] **Step 4: Verify the test passes**

Run the same pytest command. Expected: pass.

### Task 3: Focused Regression And Fake Gate

**Files:**
- Existing tests only.
- Generated outside repo: `/tmp/akashic-p6o26-fake-gate-*`.

**Interfaces:**
- Consumes: new schema-first mode in CLI.
- Produces: fake-provider report proving wiring, sanitization, and telemetry.

- [ ] **Step 1: Add production-boundary tests**

Extend existing production-boundary tests so `schema_first_shadow` is covered:

- In `tests/test_turn_pipelines.py`, update the config-only safe-version prompt variant test to use `schema_first_shadow` and assert it flows only from trusted config.
- In the `request.extra` and `session_metadata` escalation tests, attempt to inject `schema_first_shadow` and assert no hint is forwarded when config remains `standard`.
- In `tests/test_default_memory_plugin_config.py` or an existing config-default test, assert default `safe_version_governed_mode == "off"` and default `safe_version_answer_prompt_variant == "standard"`.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_turn_pipelines.py::test_safe_version_answer_prompt_variant_flows_from_config_only tests/test_turn_pipelines.py::test_safe_version_answer_prompt_variant_extra_cannot_escalate tests/test_turn_pipelines.py::test_safe_version_answer_prompt_variant_session_metadata_cannot_escalate tests/test_default_memory_plugin_config.py -q -p no:cacheprovider
```

Expected: pass after implementation.

- [ ] **Step 2: Run focused regression**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_memory_system_path_safe_version_contract.py tests/test_memory_system_path_safe_version_eval.py tests/test_memory_answer_post_check.py tests/test_memory_eval_llm_sample.py tests/test_turn_pipelines.py::test_safe_version_answer_prompt_variant_flows_from_config_only tests/test_turn_pipelines.py::test_safe_version_answer_prompt_variant_extra_cannot_escalate tests/test_turn_pipelines.py::test_safe_version_answer_prompt_variant_session_metadata_cannot_escalate tests/test_default_memory_plugin_config.py -q -p no:cacheprovider
```

Expected: all tests pass.

- [ ] **Step 3: Run fake-provider gate**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python scripts/run_memory_system_path_safe_version_eval.py --workspace /tmp/akashic-p6o26-fake-gate-workspace --out-dir /tmp/akashic-p6o26-fake-gate-report --fake-provider --balanced-small --common-limit 2 --hard-limit 2 --modes safe_version_replace,safe_version_replace_guided,safe_version_replace_guided_with_retry_shadow,safe_version_replace_schema_first_shadow
```

Expected:

- exit `0`;
- report JSON and Markdown created;
- `case_count = 16`;
- `unique_case_count = 4`;
- `provider_error_count = 0`;
- `timeout_count = 0`;
- `safe_version_replace_schema_first_shadow.answer_candidate_contract_enabled_rate = 100.0`.
- `safe_version_replace_schema_first_shadow.would_retry_count > 0`;
- retry reasons include `required_terms_missing` and `answer_choice_group_missing`;
- generated JSON/Markdown pass the same privacy scan as `_assert_report_is_private`.

### Task 4: Real Pregate

**Files:**
- Generated outside repo: `/tmp/akashic-p6o26-real-pregate-*`.

**Interfaces:**
- Consumes: repository config `/home/jjh/git_work/akashic-agent/config.toml`.
- Produces: fresh real LLM pregate data for 10 unique cases and 4 modes.

- [ ] **Step 1: Run real pregate**

Run:

```bash
.venv/bin/python scripts/run_memory_system_path_safe_version_eval.py --workspace /tmp/akashic-p6o26-real-pregate-workspace --out-dir /tmp/akashic-p6o26-real-pregate-report --config /home/jjh/git_work/akashic-agent/config.toml --enable-real-llm --case-pack standard --balanced-small --common-limit 5 --hard-limit 5 --modes safe_version_replace,safe_version_replace_guided,safe_version_replace_guided_with_retry_shadow,safe_version_replace_schema_first_shadow --timeout-s 30 --checkpoint-jsonl /tmp/akashic-p6o26-real-pregate-report/checkpoint.jsonl --early-infra-abort-count 3 --early-infra-abort-rate 0.5
```

Expected:

- exit `0`;
- `case_count = 40`;
- `unique_case_count = 10`;
- `provider_error_count = 0`;
- `timeout_count = 0`;
- no raw prompt or raw answer in committed docs.

- [ ] **Step 2: Extract metrics**

Run:

```bash
.venv/bin/python - <<'PY'
import json
p='/tmp/akashic-p6o26-real-pregate-report/system_path_safe_version_eval.json'
d=json.load(open(p,encoding='utf-8'))
print({k:d['metrics'].get(k) for k in ('case_count','unique_case_count','mode_count','repeat_count','provider_error_count','timeout_count','malformed_checkpoint_line_count','memory_grounding_pass_rate','forbidden_violation_rate','token_metrics_available')})
for mode,row in d['metrics']['mode_summaries'].items():
    print(mode, row['answer_success_count'], row['case_count'], row['answer_rule_pass_rate'], row['memory_grounding_pass_rate'], row['forbidden_violation_rate'], row['avg_total_token_count'], row['avg_latency_ms'], row['would_retry_count'], row['retry_reason_counts'])
PY
```

Expected: output contains all four modes and interpretable answer data.

### Task 5: Documentation And Final Verification

**Files:**
- Modify: `my_md/memory_optimization/10-memory-answer-correctness-uplift-history.md`
- Modify: `my_md/memory_optimization/README.md`

**Interfaces:**
- Consumes: fake gate and real pregate reports.
- Produces: committed-safe, sanitized method/data/conclusion record.

- [ ] **Step 1: Document method, data, and conclusion**

Add a `P6o-26 Schema First Answer Shadow` section to `10-memory-answer-correctness-uplift-history.md` with:

- code changes summary;
- focused regression commands/results;
- fake gate command/path/gate data;
- real pregate command/path/gate data;
- mode table for answer/grounding/forbidden/tokens/latency/would-retry;
- note that `would-retry` and retry reason counts are extracted from JSON metrics, because the generated Markdown summary does not include retry telemetry;
- conclusion comparing schema-first shadow vs guided and retry-shadow.

Append one README bullet summarizing the same result.

- [ ] **Step 2: Run final verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pytest-asyncio pytest tests/test_memory_system_path_safe_version_contract.py tests/test_memory_system_path_safe_version_eval.py tests/test_memory_answer_post_check.py tests/test_memory_eval_llm_sample.py tests/test_turn_pipelines.py::test_safe_version_answer_prompt_variant_flows_from_config_only tests/test_turn_pipelines.py::test_safe_version_answer_prompt_variant_extra_cannot_escalate tests/test_turn_pipelines.py::test_safe_version_answer_prompt_variant_session_metadata_cannot_escalate tests/test_default_memory_plugin_config.py -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 uv run python -m compileall -q memory2/system_path_safe_version_contract.py memory2/eval_system_path_safe_version.py tests/test_memory_system_path_safe_version_contract.py tests/test_memory_system_path_safe_version_eval.py
git diff --check
```

Expected: all pass with exit `0`.

- [ ] **Step 3: Final review**

Use `requesting-code-review` after implementation. The reviewer must check:

- schema-first mode is eval/config gated only;
- production default stays off;
- report sanitization still excludes raw prompt/answer;
- tests cover prompt rendering, CLI wiring, and post-check telemetry;
- docs match actual fake/real metrics.

## Execution Record

- Implemented `schema_first_shadow` and `safe_version_replace_schema_first_shadow` as eval/config-gated shadow paths only.
- Focused regression during original execution: `70 passed`.
- Fake-provider gate: `16` rows, `4` modes, schema-first contract enabled `100.0%`, would-retry `4`, retry reasons `required_terms_missing = 4` and `answer_choice_group_missing = 4`, privacy scan passed.
- Real pregate: `40` rows, `10` unique cases, `4` modes, `provider_error_count = 0`, `timeout_count = 0`, grounding `100.0%`, forbidden `0.0%`.
- Real pregate mode results:
  - `safe_version_replace`: `8/10 = 80.0%`
  - `safe_version_replace_guided`: `9/10 = 90.0%`
  - `safe_version_replace_guided_with_retry_shadow`: `10/10 = 100.0%`
  - `safe_version_replace_schema_first_shadow`: `5/10 = 50.0%`
- Reviewer follow-up:
  - fixed misleading schema-first telemetry label from `safe_version_guided_retry_shadow` to `safe_version_schema_first_shadow`;
  - restored config-only boundary coverage for both `structured_guided` and `schema_first_shadow`;
  - updated the history document intro to cover P6o-26.
- Post-review verification:
  - RED confirmed before fix: schema-first contract test failed because `candidate_reason` was still `safe_version_guided_retry_shadow`;
  - GREEN focused test: `1 passed`;
  - related contract/eval/boundary suite: `39 passed`;
  - fake telemetry gate: `2` schema-first rows, `candidate_reason_counts = safe_version_schema_first_shadow: 2`, no raw case keys, privacy flags false;
  - final related suite: `72 passed`;
  - compileall exit `0`;
  - `git diff --check` exit `0`.

## Final Conclusion

Schema-first is correctly wired and safely gated, but the real pregate showed it regressed to `50.0%` answer accuracy. It should remain shadow-only. The best current small-sample signal is still guided retry-shadow, but that path is also diagnostic/shadow and should not become a production default without a larger guarded real run.
