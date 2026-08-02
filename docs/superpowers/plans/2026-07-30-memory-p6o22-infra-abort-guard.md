# P6o-22 Infra Abort Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent real-LLM memory eval runs from producing quality-looking reports when early rows are dominated by timeout/provider errors.

**Architecture:** Add an eval-only infra gate to `run_system_path_safe_version_cases`: once a configurable minimum number of fresh rows exists, inspect cumulative fresh rows and raise a typed `SystemPathInfraAbort` if infra failures meet or exceed the configured threshold. The CLI catches that abort, writes the partial sanitized report plus a `blocked_status.json`, can also mark checkpoint-report-only rebuilds as blocked, exits non-zero by default for blocked runs, and never changes production memory behavior.

**Tech Stack:** Python 3.11+, pytest, existing `memory2.eval_system_path_safe_version` report model, existing `scripts/run_memory_system_path_safe_version_eval.py` CLI.

## Global Constraints

- Production defaults remain unchanged: `MemoryConfig.safe_version_governed_mode` stays `off`.
- No graph-all-on, no recall expansion, no real retry/fallback, no memory write change, and no global prompt change.
- Reports remain private: no raw query, prompt, memory summary, full answer, API key, or complete response.
- Existing checkpoint resume semantics stay intact except the new CLI guard can stop unsafe fresh runs early.
- Default CLI behavior for existing callers remains compatible unless the run hits the new infra abort condition.

---

### Task 1: Add Eval Infra Abort Domain Model

**Files:**
- Modify: `memory2/eval_system_path_safe_version.py`
- Test: `tests/test_memory_system_path_safe_version_eval.py`

**Interfaces:**
- Produces: `SystemPathInfraAbort(RuntimeError)` with attributes:
  - `reason: str`
  - `report: SystemPathSafeVersionReport`
  - `fresh_case_count: int`
  - `fresh_timeout_count: int`
  - `fresh_provider_error_count: int`
  - `threshold_count: int`
  - `threshold_rate: float`
- Produces: `build_system_path_blocked_status(report, reason, checkpoint_jsonl=None) -> dict[str, object]`
- Produces: `system_path_report_infra_failure_rate(report) -> float`
- Consumes: existing `SystemPathSafeVersionReport`, `_build_metrics`, `_validate_report_privacy`.

- [ ] **Step 1: Write failing unit test for blocked status payload**

Add this test to `tests/test_memory_system_path_safe_version_eval.py`:

```python
def test_system_path_blocked_status_marks_quality_interpretation_disallowed() -> None:
    from memory2.eval_system_path_safe_version import (
        SystemPathSafeVersionReport,
        build_system_path_blocked_status,
        system_path_report_infra_failure_rate,
    )

    report = SystemPathSafeVersionReport(
        cases=(
            {
                "case_id": "case-a",
                "mode": "safe_version_replace",
                "timeout": True,
                "provider_error": False,
                "answer_rule_passed": False,
                "memory_grounding_passed": True,
                "forbidden_contains_violation_count": 0,
                "latency_ms": 1000,
                "token_count": 0,
                "replacement_seeded_count": 1,
                "safe_version_contract": {},
            },
        ),
        metrics={
            "evaluation_level": "system_path_safe_version_governed",
            "unique_case_count": 1,
            "mode_count": 1,
            "case_count": 1,
            "repeat_count": 1,
            "provider_error_count": 0,
            "timeout_count": 1,
            "malformed_checkpoint_line_count": 0,
            "checkpoint_input_count": 0,
            "real_llm_enabled": True,
            "fake_provider_enabled": False,
            "raw_query_included": False,
            "raw_memory_summary_included": False,
            "prompt_included": False,
            "conversation_log_included": False,
            "complete_response_included": False,
        },
    )

    status = build_system_path_blocked_status(
        report,
        reason="early infra failure rate 100.0% exceeded 50.0%",
        checkpoint_jsonl=Path("checkpoint.jsonl"),
    )

    assert status["status"] == "infra_blocked"
    assert status["quality_interpretation_allowed"] is False
    assert status["reason"] == "early infra failure rate 100.0% exceeded 50.0%"
    assert status["case_count"] == 1
    assert status["timeout_count"] == 1
    assert status["provider_error_count"] == 0
    assert status["checkpoint_jsonl"] == "checkpoint.jsonl"
    assert system_path_report_infra_failure_rate(report) == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_system_path_safe_version_eval.py::test_system_path_blocked_status_marks_quality_interpretation_disallowed -q -p no:cacheprovider
```

Expected: FAIL with import error for `build_system_path_blocked_status`.

- [ ] **Step 3: Implement blocked status helper and abort exception**

Add near the `SystemPathSafeVersionReport` dataclass:

```python
class SystemPathInfraAbort(RuntimeError):
    def __init__(
        self,
        *,
        reason: str,
        report: SystemPathSafeVersionReport,
        fresh_case_count: int,
        fresh_timeout_count: int,
        fresh_provider_error_count: int,
        threshold_count: int,
        threshold_rate: float,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.report = report
        self.fresh_case_count = int(fresh_case_count)
        self.fresh_timeout_count = int(fresh_timeout_count)
        self.fresh_provider_error_count = int(fresh_provider_error_count)
        self.threshold_count = int(threshold_count)
        self.threshold_rate = float(threshold_rate)
```

Add this function after `_build_metrics`:

```python
def system_path_report_infra_failure_rate(
    report: SystemPathSafeVersionReport,
) -> float:
    case_count = int(report.metrics.get("case_count", 0) or 0)
    if case_count <= 0:
        return 0.0
    infra_count = int(report.metrics.get("timeout_count", 0) or 0) + int(
        report.metrics.get("provider_error_count", 0) or 0
    )
    return infra_count / case_count


def build_system_path_blocked_status(
    report: SystemPathSafeVersionReport,
    *,
    reason: str,
    checkpoint_jsonl: Path | None = None,
) -> dict[str, object]:
    _validate_report_privacy(report)
    metrics = report.metrics
    payload: dict[str, object] = {
        "status": "infra_blocked",
        "reason": str(reason),
        "quality_interpretation_allowed": False,
        "case_count": int(metrics.get("case_count", 0) or 0),
        "unique_case_count": int(metrics.get("unique_case_count", 0) or 0),
        "mode_count": int(metrics.get("mode_count", 0) or 0),
        "repeat_count": int(metrics.get("repeat_count", 1) or 1),
        "provider_error_count": int(metrics.get("provider_error_count", 0) or 0),
        "timeout_count": int(metrics.get("timeout_count", 0) or 0),
        "malformed_checkpoint_line_count": int(
            metrics.get("malformed_checkpoint_line_count", 0) or 0
        ),
    }
    if checkpoint_jsonl is not None:
        payload["checkpoint_jsonl"] = str(checkpoint_jsonl)
        payload["checkpoint_line_count"] = _count_checkpoint_lines(checkpoint_jsonl)
    return payload
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_system_path_safe_version_eval.py::test_system_path_blocked_status_marks_quality_interpretation_disallowed -q -p no:cacheprovider
```

Expected: PASS.

---

### Task 2: Add Early Infra Abort Guard To Eval Runner

**Files:**
- Modify: `memory2/eval_system_path_safe_version.py`
- Test: `tests/test_memory_system_path_safe_version_eval.py`

**Interfaces:**
- Modifies `run_system_path_safe_version_cases(..., early_infra_abort_count=0, early_infra_abort_rate=1.0)`.
- Treats `early_infra_abort_count` as minimum fresh rows required before evaluating the cumulative fresh-row infra rate.
- Raises `SystemPathInfraAbort` only after fresh rows, not checkpoint-skipped rows.
- Uses existing record fields `timeout` and `provider_error`.

- [ ] **Step 1: Write failing async test for early abort**

Add this test to `tests/test_memory_system_path_safe_version_eval.py`:

```python
def test_system_path_eval_aborts_when_early_fresh_rows_are_all_timeouts(
    tmp_path: Path,
) -> None:
    from agent.provider import LLMResponse
    from memory2.eval_system_path_safe_version import (
        SystemPathInfraAbort,
        run_system_path_safe_version_cases,
    )

    class SlowProvider:
        async def chat(self, **kwargs: object) -> LLMResponse:
            await asyncio.sleep(1)
            return LLMResponse(content="too late", tool_calls=[])

    cases = build_quantitative_eval_cases("all", case_pack="standard", limit=2)
    checkpoint_jsonl = tmp_path / "checkpoint.jsonl"

    try:
        asyncio.run(
            run_system_path_safe_version_cases(
                cases,
                tmp_path / "workspace",
                SlowProvider(),
                modes=("safe_version_replace",),
                model="slow-model",
                timeout_s=0.001,
                real_llm_enabled=True,
                checkpoint_jsonl=checkpoint_jsonl,
                early_infra_abort_count=2,
                early_infra_abort_rate=0.5,
            )
        )
    except SystemPathInfraAbort as exc:
        assert exc.fresh_case_count == 2
        assert exc.fresh_timeout_count == 2
        assert exc.fresh_provider_error_count == 0
        assert exc.report.metrics["case_count"] == 2
        assert exc.report.metrics["timeout_count"] == 2
        assert "early infra failure rate 100.0% met or exceeded 50.0%" in exc.reason
    else:
        raise AssertionError("expected SystemPathInfraAbort")

    assert checkpoint_jsonl.exists()
    assert len(checkpoint_jsonl.read_text(encoding="utf-8").splitlines()) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_system_path_safe_version_eval.py::test_system_path_eval_aborts_when_early_fresh_rows_are_all_timeouts -q -p no:cacheprovider
```

Expected: FAIL because `run_system_path_safe_version_cases` does not accept `early_infra_abort_count`.

- [ ] **Step 3: Implement guard**

Update `run_system_path_safe_version_cases` signature:

```python
async def run_system_path_safe_version_cases(
    cases: Sequence[EvalCase],
    workspace: Path,
    provider: object,
    *,
    modes: Sequence[str],
    model: str = "scripted",
    timeout_s: float = 30.0,
    real_llm_enabled: bool = False,
    repeats: int = 1,
    checkpoint_jsonl: Path | None = None,
    resume: bool = False,
    early_infra_abort_count: int = 0,
    early_infra_abort_rate: float = 1.0,
) -> SystemPathSafeVersionReport:
```

Add before the loop:

```python
    fresh_records: list[dict[str, object]] = []
    abort_count = max(0, int(early_infra_abort_count))
    abort_rate = min(1.0, max(0.0, float(early_infra_abort_rate)))
```

Add immediately after appending a freshly run record and checkpoint append:

```python
                fresh_records.append(record)
                if abort_count and len(fresh_records) >= abort_count:
                    infra_count = sum(
                        1
                        for item in fresh_records
                        if bool(item.get("timeout")) or bool(item.get("provider_error"))
                    )
                    observed_rate = infra_count / len(fresh_records)
                    if observed_rate >= abort_rate:
                        partial_report = SystemPathSafeVersionReport(
                            cases=tuple(records),
                            metrics=_build_metrics(
                                records,
                                unique_case_count=len(cases),
                                modes=modes,
                                real_llm_enabled=real_llm_enabled,
                                repeats=repeat_count,
                                skipped_from_checkpoint_count=skipped,
                                malformed_checkpoint_line_count=malformed_checkpoint_line_count,
                            ),
                        )
                        raise SystemPathInfraAbort(
                            reason=(
                                "early infra failure rate "
                                f"{round(observed_rate * 100.0, 4)}% met or exceeded "
                                f"{round(abort_rate * 100.0, 4)}%"
                            ),
                            report=partial_report,
                            fresh_case_count=len(fresh_records),
                            fresh_timeout_count=sum(
                                1 for item in fresh_records if bool(item.get("timeout"))
                            ),
                            fresh_provider_error_count=sum(
                                1
                                for item in fresh_records
                                if bool(item.get("provider_error"))
                            ),
                            threshold_count=abort_count,
                            threshold_rate=abort_rate,
                        )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_system_path_safe_version_eval.py::test_system_path_eval_aborts_when_early_fresh_rows_are_all_timeouts -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 5: Write and pass regression test for 2-of-3 infra majority**

Add this test to `tests/test_memory_system_path_safe_version_eval.py`:

```python
def test_system_path_eval_aborts_when_two_of_three_early_rows_are_infra_failures(
    tmp_path: Path,
) -> None:
    from agent.provider import LLMResponse
    from memory2.eval_system_path_safe_version import (
        SystemPathInfraAbort,
        run_system_path_safe_version_cases,
    )

    class MostlySlowProvider:
        def __init__(self) -> None:
            self.calls = 0

        async def chat(self, **kwargs: object) -> LLMResponse:
            self.calls += 1
            if self.calls <= 2:
                await asyncio.sleep(1)
            return LLMResponse(content="根据系统路径注入记忆回答。", tool_calls=[])

    cases = build_quantitative_eval_cases("all", case_pack="standard", limit=3)

    try:
        asyncio.run(
            run_system_path_safe_version_cases(
                cases,
                tmp_path / "workspace",
                MostlySlowProvider(),
                modes=("safe_version_replace",),
                model="mostly-slow-model",
                timeout_s=0.001,
                real_llm_enabled=True,
                early_infra_abort_count=3,
                early_infra_abort_rate=0.5,
            )
        )
    except SystemPathInfraAbort as exc:
        assert exc.fresh_case_count == 3
        assert exc.fresh_timeout_count == 2
        assert exc.report.metrics["case_count"] == 3
        assert exc.report.metrics["timeout_count"] == 2
        assert "66.6667% met or exceeded 50.0%" in exc.reason
    else:
        raise AssertionError("expected SystemPathInfraAbort")
```

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_system_path_safe_version_eval.py::test_system_path_eval_aborts_when_two_of_three_early_rows_are_infra_failures -q -p no:cacheprovider
```

Expected: PASS after the guard implementation.

---

### Task 3: Wire CLI Blocked Artifacts

**Files:**
- Modify: `scripts/run_memory_system_path_safe_version_eval.py`
- Test: `tests/test_memory_system_path_safe_version_eval.py`

**Interfaces:**
- Adds CLI args:
  - `--early-infra-abort-count`, default `0`.
  - `--early-infra-abort-rate`, default `1.0`.
  - `--allow-infra-blocked-exit-zero`, default false.
  - `--fake-provider-delay-s`, default `0.0`, only affects `--fake-provider` test runs.
- On `SystemPathInfraAbort`, writes:
  - `system_path_safe_version_eval.json`
  - `system_path_safe_version_eval.md`
  - `blocked_status.json`
- Returns exit code `2` by default, or `0` if `--allow-infra-blocked-exit-zero` is set.
- Rejects invalid guard args: `--early-infra-abort-count < 0`, or `--early-infra-abort-rate <= 0.0`, or `--early-infra-abort-rate > 1.0`.

- [ ] **Step 1: Write failing CLI test**

Add this test to `tests/test_memory_system_path_safe_version_eval.py`:

```python
def test_system_path_safe_version_cli_writes_blocked_status_on_early_abort(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "reports"
    checkpoint_jsonl = tmp_path / "checkpoint.jsonl"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_system_path_safe_version_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(out_dir),
            "--fake-provider",
            "--case-pack",
            "standard",
            "--limit",
            "2",
            "--modes",
            "safe_version_replace",
            "--timeout-s",
            "0.001",
            "--fake-provider-delay-s",
            "0.05",
            "--checkpoint-jsonl",
            str(checkpoint_jsonl),
            "--early-infra-abort-count",
            "1",
            "--early-infra-abort-rate",
            "1.0",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    blocked = json.loads((out_dir / "blocked_status.json").read_text(encoding="utf-8"))
    payload = json.loads(
        (out_dir / "system_path_safe_version_eval.json").read_text(encoding="utf-8")
    )
    markdown = (out_dir / "system_path_safe_version_eval.md").read_text(
        encoding="utf-8"
    )
    assert blocked["status"] == "infra_blocked"
    assert blocked["quality_interpretation_allowed"] is False
    assert blocked["timeout_count"] == 1
    assert blocked["case_count"] == payload["metrics"]["case_count"]
    assert "early infra failure rate" in blocked["reason"]
    assert blocked["fresh_case_count"] == 1
    assert blocked["fresh_timeout_count"] == 1
    assert "raw_prompt" not in markdown
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_system_path_safe_version_eval.py::test_system_path_safe_version_cli_writes_blocked_status_on_early_abort -q -p no:cacheprovider
```

Expected: FAIL because CLI args, fake delay, and blocked writer do not exist.

- [ ] **Step 3: Implement CLI catch and artifact writing**

Update `ScriptedSystemPathProvider`:

```python
class ScriptedSystemPathProvider:
    def __init__(self, *, delay_s: float = 0.0) -> None:
        self.calls: list[dict[str, Any]] = []
        self._delay_s = max(0.0, float(delay_s))

    async def chat(self, **kwargs: Any) -> LLMResponse:
        if self._delay_s:
            await asyncio.sleep(self._delay_s)
        text = "\n".join(
            str(message.get("content") or "")
            for message in kwargs.get("messages", [])
            if isinstance(message, dict)
        )
```

Update imports in `scripts/run_memory_system_path_safe_version_eval.py`:

```python
import json

from memory2.eval_system_path_safe_version import (
    SystemPathInfraAbort,
    build_system_path_blocked_status,
    build_system_path_safe_version_report_from_checkpoint,
    run_system_path_safe_version_cases,
    write_system_path_safe_version_json,
    write_system_path_safe_version_markdown,
)
```

Add parser args:

```python
    parser.add_argument("--fake-provider-delay-s", type=float, default=0.0)
    parser.add_argument("--early-infra-abort-count", type=int, default=0)
    parser.add_argument("--early-infra-abort-rate", type=float, default=1.0)
    parser.add_argument("--allow-infra-blocked-exit-zero", action="store_true")
```

Add validation after existing parser validation:

```python
    if int(args.early_infra_abort_count) < 0:
        parser.error("--early-infra-abort-count must be >= 0")
    if not (0.0 < float(args.early_infra_abort_rate) <= 1.0):
        parser.error("--early-infra-abort-rate must be > 0.0 and <= 1.0")
```

Update `build_provider_for_system_path_safe_version`:

```python
    if bool(args.fake_provider):
        return (
            ScriptedSystemPathProvider(delay_s=float(args.fake_provider_delay_s)),
            "fake-model",
        )
```

Initialize blocked state before the `if bool(args.checkpoint_report_only)` branch:

```python
    blocked_status: dict[str, object] | None = None
    exit_code = 0
```

Wrap the `asyncio.run(...)` call:

```python
        try:
            report = asyncio.run(
                run_system_path_safe_version_cases(
                    cases,
                    Path(args.workspace),
                    provider,
                    modes=modes,
                    model=model,
                    timeout_s=args.timeout_s,
                    real_llm_enabled=bool(args.enable_real_llm),
                    repeats=int(args.repeats),
                    checkpoint_jsonl=Path(args.checkpoint_jsonl)
                    if args.checkpoint_jsonl
                    else None,
                    resume=bool(args.resume),
                    early_infra_abort_count=int(args.early_infra_abort_count),
                    early_infra_abort_rate=float(args.early_infra_abort_rate),
                )
            )
            exit_code = 0
            blocked_status = None
        except SystemPathInfraAbort as exc:
            report = exc.report
            blocked_status = build_system_path_blocked_status(
                report,
                reason=exc.reason,
                checkpoint_jsonl=Path(args.checkpoint_jsonl)
                if args.checkpoint_jsonl
                else None,
            )
            blocked_status.update(
                {
                    "fresh_case_count": exc.fresh_case_count,
                    "fresh_timeout_count": exc.fresh_timeout_count,
                    "fresh_provider_error_count": exc.fresh_provider_error_count,
                    "early_infra_abort_count": exc.threshold_count,
                    "early_infra_abort_rate": exc.threshold_rate,
                }
            )
            exit_code = 0 if bool(args.allow_infra_blocked_exit_zero) else 2
```

After writing JSON and Markdown, add:

```python
    if blocked_status is not None:
        (out_dir / "blocked_status.json").write_text(
            json.dumps(
                blocked_status,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
    return exit_code
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_system_path_safe_version_eval.py::test_system_path_safe_version_cli_writes_blocked_status_on_early_abort -q -p no:cacheprovider
```

Expected: PASS.

- [ ] **Step 5: Write and pass checkpoint-report-only blocked test**

Add this test to `tests/test_memory_system_path_safe_version_eval.py`:

```python
def test_system_path_safe_version_cli_report_only_marks_timeout_checkpoint_blocked(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "reports"
    checkpoint_jsonl = tmp_path / "checkpoint.jsonl"
    record = {
        "case_id": "case-timeout",
        "case_index": 0,
        "repeat_index": 0,
        "category": "common",
        "mode": "safe_version_replace",
        "passed": False,
        "answer_rule_passed": False,
        "memory_grounding_passed": True,
        "expected_memory_used": True,
        "forbidden_contains_violation_count": 0,
        "answer_length": 0,
        "expected_contains_pass_count": 0,
        "expected_contains_miss_count": 1,
        "expected_any_pass_count": 0,
        "expected_any_miss_count": 1,
        "language_passed": False,
        "failures": ["timeout"],
        "provider_error": False,
        "timeout": True,
        "latency_ms": 1000,
        "token_count": 0,
        "prompt_token_count": 0,
        "completion_token_count": 0,
        "token_metrics_available": False,
        "replacement_seeded_count": 1,
        "safe_version_metadata": {},
        "safe_version_contract": {},
        "post_check_shadow": {"shadow_enabled": True},
    }
    checkpoint_jsonl.write_text(
        json.dumps({"spec_key": "case-timeout|safe_version_replace|0", "result": record})
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_system_path_safe_version_eval.py",
            "--out-dir",
            str(out_dir),
            "--enable-real-llm",
            "--checkpoint-jsonl",
            str(checkpoint_jsonl),
            "--checkpoint-report-only",
            "--early-infra-abort-count",
            "1",
            "--early-infra-abort-rate",
            "1.0",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    blocked = json.loads((out_dir / "blocked_status.json").read_text(encoding="utf-8"))
    assert blocked["status"] == "infra_blocked"
    assert blocked["quality_interpretation_allowed"] is False
    assert blocked["case_count"] == 1
    assert blocked["timeout_count"] == 1
    assert "checkpoint infra failure rate 100.0% met or exceeded 100.0%" in blocked["reason"]
```

Implementation: after `build_system_path_safe_version_report_from_checkpoint`, if `args.early_infra_abort_count > 0`, compute `system_path_report_infra_failure_rate(report)`. If `metrics["case_count"] >= early_infra_abort_count` and the rate meets or exceeds `early_infra_abort_rate`, set `blocked_status = build_system_path_blocked_status(...)` with reason `checkpoint infra failure rate ... met or exceeded ...`, and set `exit_code` to `2` unless `--allow-infra-blocked-exit-zero`.

---

### Task 4: Re-test And Document P6o-22 Results

**Files:**
- Modify: `my_md/memory_optimization/eval_reports/p6o21_provider_timeout_diagnosis_v1/provider_timeout_diagnosis.md`
- Create: `my_md/memory_optimization/eval_reports/p6o22_infra_abort_guard_v1/`

**Interfaces:**
- Consumes CLI from Task 3.
- Produces fresh smoke artifacts and a conclusion that differentiates infra-blocked data from quality data.

- [ ] **Step 1: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_system_path_safe_version_eval.py tests/test_memory_answer_post_check.py tests/test_memory_system_path_safe_version_contract.py -q -p no:cacheprovider
```

Expected: all tests pass.

- [ ] **Step 2: Run compile check**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m compileall memory2/eval_system_path_safe_version.py scripts/run_memory_system_path_safe_version_eval.py tests/test_memory_system_path_safe_version_eval.py
```

Expected: exit 0.

- [ ] **Step 3: Run infra-abort fake smoke**

Run:

```bash
.venv/bin/python scripts/run_memory_system_path_safe_version_eval.py --workspace /tmp/akashic-p6o22-infra-abort-fake/workspace --out-dir my_md/memory_optimization/eval_reports/p6o22_infra_abort_guard_v1/fake_abort --fake-provider --fake-provider-delay-s 0.05 --case-pack standard --limit 2 --modes safe_version_replace --timeout-s 0.001 --checkpoint-jsonl my_md/memory_optimization/eval_reports/p6o22_infra_abort_guard_v1/fake_abort/checkpoint.jsonl --early-infra-abort-count 1 --early-infra-abort-rate 1.0
```

Expected: exit 2, `blocked_status.json` exists, `quality_interpretation_allowed=false`.

- [ ] **Step 4: Run fresh real mini matrix**

Run:

```bash
.venv/bin/python scripts/run_memory_system_path_safe_version_eval.py --workspace /tmp/akashic-p6o22-real-mini/workspace --out-dir my_md/memory_optimization/eval_reports/p6o22_infra_abort_guard_v1/real_mini --config /home/jjh/git_work/akashic-agent/config.toml --enable-real-llm --case-pack standard --limit 3 --modes safe_version_replace,safe_version_replace_guided,safe_version_replace_guided_with_retry_shadow --timeout-s 30 --checkpoint-jsonl my_md/memory_optimization/eval_reports/p6o22_infra_abort_guard_v1/real_mini/checkpoint.jsonl --early-infra-abort-count 3 --early-infra-abort-rate 0.5
```

Expected: exit 0, `timeout_count=0`, `provider_error_count=0`, answer rows have non-zero `answer_length`.

- [ ] **Step 5: Append results to diagnosis report**

Append a `## P6o-22 Retest` section to:

`my_md/memory_optimization/eval_reports/p6o21_provider_timeout_diagnosis_v1/provider_timeout_diagnosis.md`

Include:

- fixed behavior
- exact commands
- fake abort status metrics
- real mini matrix metrics
- final conclusion: old all-zero data is invalid for quality; fresh guarded runs can now separate infra-blocked from answer-quality data.

- [ ] **Step 6: Privacy scan docs**

Run:

```bash
rg -n "api_key|sk-|Authorization|Bearer|raw_query|raw_prompt|full_answer|raw_answer|session_text|memory_summary" my_md/memory_optimization/eval_reports/p6o21_provider_timeout_diagnosis_v1 my_md/memory_optimization/eval_reports/p6o22_infra_abort_guard_v1
```

Expected: no matches.
