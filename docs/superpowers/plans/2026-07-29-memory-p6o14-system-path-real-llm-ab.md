# Memory P6o14 System Path Real LLM A/B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a bounded real LLM A/B for the P6o-13 system-path safe version-governed integration, comparing current system-path memory injection against safe-version replace mode.

**Architecture:** Extend the P6o-13 system-path eval runner so it can use the real configured `LLMProvider`, feed each fixture's real query through `AgentLoop.process_direct()`, score answers with the existing answer expectation scorer, and write sanitized JSON/Markdown reports. Keep runtime default `off`, keep production behavior unchanged, and use this plan only as an eval gate before any production activation.

**Tech Stack:** Python `>=3.12`, pytest, existing `AgentLoop`, existing `DefaultMemoryRetrievalPipeline`, existing `DefaultMemoryEngine`, existing `MemoryStore2`, existing `memory2.eval_llm_sample.score_answer_text`, existing `agent.config.load_config`, existing `agent.provider.LLMProvider`, JSON/Markdown reports.

## Global Constraints

- Worktree: `/home/jjh/git_work/akashic-agent/.worktrees/memory-next`.
- Branch: `memory-next`.
- Do not sync remote/main in this plan unless the user explicitly redirects.
- Do not push without explicit user instruction.
- Do not modify graph retrieval, graph routing, graph-all-on, `chain_all_on`, production memory writes, post-response memory writes, or production retry/fallback behavior.
- Default runtime behavior must remain unchanged: `MemoryConfig.safe_version_governed_mode = "off"` and existing `retrieved_memory_block` output remains unchanged unless explicit eval/test mode is selected.
- `safe_version_replace` remains allowed only when `safe_version_governed_mode = "replace"` and `safe_version_governed_replace_allowed = True`.
- Session metadata may request `off` or `shadow`, but must not enable `replace` by itself.
- Real LLM mode must require `--enable-real-llm`; fake and real provider flags must be mutually exclusive.
- Reports must not include raw prompt, raw session text, raw user query, raw memory summaries, full answers, API keys, or authorization values.
- Privacy gates must inspect both JSON and Markdown reports, not Markdown alone.
- Do not stage or modify the existing untracked intent directory `my_md/memory_optimization/eval_reports/p6o13_system_path_real_llm_validation_v1/`.
- P6o-14 success is a small controlled system-path A/B conclusion, not a production natural-traffic claim.
- `--real-memory-workspace` is accepted for CLI parity with older eval runners but intentionally unused in P6o-14 because cases are fixture-seeded into temporary system-path stores.

---

## File Structure

- Modify `memory2/eval_system_path_safe_version.py`
  - Use the fixture query instead of a constant synthetic message.
  - Score answers with `answer_expectation_from_case()` and `score_answer_text()`.
  - Wrap providers with the existing recording-provider pattern so real LLM token usage is measurable.
  - Add real/fake LLM metadata and aggregate/per-mode answer, grounding, forbidden, token, latency, contract, and post-check metrics.
- Modify `scripts/run_memory_system_path_safe_version_eval.py`
  - Add real provider construction using `load_config()` and `LLMProvider`.
  - Enforce `--fake-provider` and `--enable-real-llm` mutual exclusion.
  - Pass `real_llm_enabled` into the eval report.
- Modify `tests/test_memory_system_path_safe_version_eval.py`
  - Add RED/GREEN coverage for real-provider flag handling, scored fake rows, sanitized report fields, and mode summary metrics.
- Create during execution:
  - `my_md/memory_optimization/eval_reports/p6o14_system_path_safe_version_real_llm_ab_v1/system_path_safe_version_eval.json`
  - `my_md/memory_optimization/eval_reports/p6o14_system_path_safe_version_real_llm_ab_v1/system_path_safe_version_eval.md`
- Modify docs after execution:
  - `my_md/memory_optimization/README.md`
  - `progress.md`

---

## Task 0: Baseline And Safety Check

**Files:**
- Modify: none

**Interfaces:**
- Consumes: current branch state and existing untracked P6o-13 real LLM intent directory.
- Produces: verified baseline and explicit artifact boundary.

- [ ] **Step 1: Confirm worktree and branch**

Run:

```bash
ROOT=$(git rev-parse --show-toplevel)
BRANCH=$(git branch --show-current)
printf 'ROOT=%s\nBRANCH=%s\n' "$ROOT" "$BRANCH"
test "$ROOT" = "/home/jjh/git_work/akashic-agent/.worktrees/memory-next"
test "$BRANCH" = "memory-next"
```

Expected:

```text
ROOT=/home/jjh/git_work/akashic-agent/.worktrees/memory-next
BRANCH=memory-next
```

- [ ] **Step 2: Inspect status and protect existing untracked intent**

Run:

```bash
git status --short
find my_md/memory_optimization/eval_reports/p6o13_system_path_real_llm_validation_v1 -maxdepth 2 -type f -print 2>/dev/null | sort
```

Expected: `find` prints:

```text
my_md/memory_optimization/eval_reports/p6o13_system_path_real_llm_validation_v1/system_path_validation_intent.md
```

Do not edit, stage, delete, or overwrite this directory in P6o-14.

---

## Task 1: Add Real Provider Gate And Answer Scoring

**Files:**
- Modify: `memory2/eval_system_path_safe_version.py`
- Modify: `scripts/run_memory_system_path_safe_version_eval.py`
- Modify: `tests/test_memory_system_path_safe_version_eval.py`

**Interfaces:**
- Consumes:
  - `memory2.eval_llm_sample.answer_expectation_from_case(case: EvalCase) -> AnswerExpectation`
  - `memory2.eval_llm_sample.score_answer_text(answer: str, expectation: AnswerExpectation, used_memory_ids: Sequence[str]) -> AnswerScoreResult`
  - `memory2.eval_llm_sample._RecordingProvider`
  - `memory2.eval_llm_sample._extract_token_counts(response: LLMResponse | None) -> dict[str, object]`
  - `agent.config.load_config(path: str | Path) -> Config`
  - `agent.provider.LLMProvider`
- Produces:
  - `run_system_path_safe_version_cases(..., real_llm_enabled: bool = False)`
  - JSON metrics `real_llm_enabled`, `fake_provider_enabled`, `answer_rule_pass_rate`, `memory_grounding_pass_rate`, `forbidden_violation_rate`, `token_metrics_available`
  - per-case fields `answer_rule_passed`, `memory_grounding_passed`, `expected_memory_used`, `forbidden_contains_violation_count`, `failures`

- [ ] **Step 1: Write failing tests for scored rows and real-provider flag handling**

Append these tests to `tests/test_memory_system_path_safe_version_eval.py`:

```python
def test_system_path_safe_version_cli_rejects_fake_and_real_flags(
    tmp_path: Path,
) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_memory_system_path_safe_version_eval.py",
            "--workspace",
            str(tmp_path / "workspace"),
            "--out-dir",
            str(tmp_path / "reports"),
            "--fake-provider",
            "--enable-real-llm",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "--fake-provider and --enable-real-llm cannot be used together" in completed.stderr


def test_system_path_safe_version_fake_provider_rows_are_answer_scored(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "reports"
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
            "--balanced-small",
            "--common-limit",
            "2",
            "--hard-limit",
            "2",
            "--modes",
            "current,safe_version_replace",
            "--real-memory-workspace",
            str(tmp_path / "empty-real-workspace"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(
        (out_dir / "system_path_safe_version_eval.json").read_text(encoding="utf-8")
    )
    metrics = payload["metrics"]
    assert metrics["fake_provider_enabled"] is True
    assert metrics["real_llm_enabled"] is False
    assert "answer_rule_pass_rate" in metrics
    assert "memory_grounding_pass_rate" in metrics
    assert "forbidden_violation_rate" in metrics
    assert "token_metrics_available" in metrics
    for row in payload["cases"]:
        assert "answer_rule_passed" in row
        assert "memory_grounding_passed" in row
        assert "expected_memory_used" in row
        assert "forbidden_contains_violation_count" in row
        assert "failures" in row
        assert "answer_passed" not in row
```

Also add non-network provider construction tests:

```python
def test_system_path_safe_version_real_provider_builder_requires_api_key(
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    from types import SimpleNamespace
    import scripts.run_memory_system_path_safe_version_eval as cli

    args = SimpleNamespace(
        fake_provider=False,
        enable_real_llm=True,
        config=str(tmp_path / "config.toml"),
        timeout_s=60.0,
    )
    monkeypatch.setattr(
        cli,
        "load_config",
        lambda path: SimpleNamespace(
            api_key="",
            model="real-model",
            base_url="https://example.invalid",
            system_prompt="",
            extra_body={},
            provider="test-provider",
        ),
    )

    provider, model = cli.build_provider_for_system_path_safe_version(args)

    assert provider is None
    assert model == "real-model"


def test_system_path_safe_version_real_provider_builder_uses_config(
    monkeypatch: object,
    tmp_path: Path,
) -> None:
    from types import SimpleNamespace
    import scripts.run_memory_system_path_safe_version_eval as cli

    created: dict[str, object] = {}

    class FakeRealProvider:
        def __init__(self, **kwargs: object) -> None:
            created.update(kwargs)

    args = SimpleNamespace(
        fake_provider=False,
        enable_real_llm=True,
        config=str(tmp_path / "config.toml"),
        timeout_s=12.5,
    )
    monkeypatch.setattr(
        cli,
        "load_config",
        lambda path: SimpleNamespace(
            api_key="secret-key",
            model="real-model",
            base_url="https://example.invalid",
            system_prompt="system",
            extra_body={"x": 1},
            provider="test-provider",
        ),
    )
    monkeypatch.setattr(cli.agent_provider, "LLMProvider", FakeRealProvider)

    provider, model = cli.build_provider_for_system_path_safe_version(args)

    assert isinstance(provider, FakeRealProvider)
    assert model == "real-model"
    assert created["api_key"] == "secret-key"
    assert created["request_timeout_s"] == 12.5
    assert created["provider_name"] == "test-provider"
```

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_system_path_safe_version_eval.py::test_system_path_safe_version_cli_rejects_fake_and_real_flags \
  tests/test_memory_system_path_safe_version_eval.py::test_system_path_safe_version_fake_provider_rows_are_answer_scored \
  -q -p no:cacheprovider
```

Expected: both fail because the CLI does not reject both flags yet and rows still use `answer_passed` instead of scored answer fields.

- [ ] **Step 3: Implement provider selection and answer scoring**

In `scripts/run_memory_system_path_safe_version_eval.py`:

- import `load_config` and `agent.provider as agent_provider`;
- add:

```python
def build_provider_for_system_path_safe_version(
    args: argparse.Namespace,
) -> tuple[object | None, str | None]:
    if bool(args.fake_provider):
        return ScriptedSystemPathProvider(), "fake-model"
    if not bool(args.enable_real_llm):
        return ScriptedSystemPathProvider(), "scripted"
    cfg = load_config(args.config)
    if not cfg.api_key:
        return None, cfg.model
    return (
        agent_provider.LLMProvider(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            system_prompt=cfg.system_prompt,
            extra_body=cfg.extra_body,
            request_timeout_s=float(args.timeout_s),
            provider_name=cfg.provider,
        ),
        cfg.model,
    )
```

- replace the current real-provider rejection with:

```python
if bool(args.fake_provider) and bool(args.enable_real_llm):
    parser.error("--fake-provider and --enable-real-llm cannot be used together")
provider, model = build_provider_for_system_path_safe_version(args)
if provider is None or model is None:
    raise SystemExit("missing API key for --enable-real-llm")
```

In `memory2/eval_system_path_safe_version.py`:

- import:

```python
from memory2.eval_llm_sample import (
    _RecordingProvider,
    _extract_token_counts,
    answer_expectation_from_case,
    score_answer_text,
)
from typing import Iterable
```

- change `run_system_path_safe_version_cases()` signature to include:

```python
real_llm_enabled: bool = False,
```

- pass `real_llm_enabled` into `_build_metrics(...)`;
- inside `_run_case_mode()`, wrap the supplied provider before constructing `AgentLoop`:

```python
recording_provider = _RecordingProvider(provider)
```

- pass `recording_provider` as both `provider` and `light_provider` in `AgentLoopDeps`;
- in `_run_case_mode()`, replace the constant `loop.process_direct("system path eval user message", ...)` message with:

```python
query = str(case.setup.get("query") or "").strip() or "system path eval user message"
answer = await asyncio.wait_for(
    loop.process_direct(
        query,
        session_key=str(case.setup.get("scope", {}).get("session_key") or "cli:local"),
        channel=str(case.setup.get("scope", {}).get("channel") or "cli"),
        chat_id=str(case.setup.get("scope", {}).get("chat_id") or "local"),
        skip_post_memory=True,
        disabled_tools=["message_push"],
    ),
    timeout=timeout_s,
)
```

- after `context_ids` is known, score:

```python
score = score_answer_text(
    answer,
    answer_expectation_from_case(case),
    context_ids,
)
failures = list(score.failures)
if provider_error:
    failures.append("provider_error")
if timeout:
    failures.append("timeout")
```

- if `recording_provider.errors` is non-empty and `provider_error` is still false, set `provider_error = True` and append `"provider_error"`;
- replace `_provider_usage(provider)` with:

```python
token_counts = _extract_token_counts(
    recording_provider.responses[-1] if recording_provider.responses else None
)
```

- return these fields instead of `answer_passed`, `grounding_passed`, and `forbidden_violation`:

```python
"passed": not failures,
"answer_rule_passed": score.answer_rule_passed,
"memory_grounding_passed": score.memory_grounding_passed,
"expected_memory_used": bool(score.expected_memory_used),
"forbidden_contains_violation_count": score.forbidden_contains_violation_count,
"prompt_token_count": int(token_counts["prompt_token_count"]),
"completion_token_count": int(token_counts["completion_token_count"]),
"token_count": int(token_counts["total_token_count"]),
"token_metrics_available": bool(token_counts["token_metrics_available"]),
"failures": tuple(_sanitize_failure(failure) for failure in failures),
```

- add local `_sanitize_failure()` with the same behavior used in `memory2.eval_comprehensive_online`:

```python
def _sanitize_failure(failure: str) -> str:
    if failure.startswith("missing expected answer term:"):
        return "missing_expected_answer_term"
    if failure.startswith("missing expected answer term group:"):
        return "missing_expected_answer_term_group"
    if failure.startswith("found forbidden answer term:"):
        return "found_forbidden_answer_term"
    if failure.startswith("missing expected memory ids:"):
        return "missing_expected_memory_ids"
    if failure == "answer is not detected as Chinese":
        return "answer_language_not_chinese"
    return failure
```

- update `_build_metrics()` to compute top-level aggregate answer, grounding, forbidden, latency, token, `token_metrics_available`, and mode summaries from the scored fields:

```python
answer_success_count = sum(1 for row in records if row["answer_rule_passed"])
grounding_success_count = sum(1 for row in records if row["memory_grounding_passed"])
forbidden_case_count = sum(
    1
    for row in records
    if int(row.get("forbidden_contains_violation_count", 0) or 0) > 0
)
```

Then include:

```python
"real_llm_enabled": bool(real_llm_enabled),
"fake_provider_enabled": not bool(real_llm_enabled),
"answer_rule_pass_rate": _pct(answer_success_count, len(records)),
"memory_grounding_pass_rate": _pct(grounding_success_count, len(records)),
"forbidden_violation_rate": _pct(forbidden_case_count, len(records)),
"avg_latency_ms": _avg(int(row.get("latency_ms", 0) or 0) for row in records),
"total_token_count": sum(int(row.get("token_count", 0) or 0) for row in records),
"avg_total_token_count": _avg(int(row.get("token_count", 0) or 0) for row in records),
"token_metrics_available": any(bool(row.get("token_metrics_available")) for row in records),
```

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_system_path_safe_version_eval.py \
  -q -p no:cacheprovider
```

Expected: all tests in the file pass.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add memory2/eval_system_path_safe_version.py scripts/run_memory_system_path_safe_version_eval.py tests/test_memory_system_path_safe_version_eval.py
git commit -m "feat: score system path safe version ab eval"
```

---

## Task 2: Fake Smoke Report Gate For P6o-14 Shape

**Files:**
- Modify: `memory2/eval_system_path_safe_version.py`
- Modify: `tests/test_memory_system_path_safe_version_eval.py`

**Interfaces:**
- Consumes: Task 1 scored system-path report.
- Produces:
  - Markdown table with answer, grounding, forbidden, contract, post-check, token, and latency per mode.
  - JSON `mode_summaries` with the same fields.

- [ ] **Step 1: Write failing report-shape assertions**

Extend `test_system_path_safe_version_cli_fake_provider_writes_sanitized_report()` in `tests/test_memory_system_path_safe_version_eval.py` with:

```python
current = payload["metrics"]["mode_summaries"]["current"]
replace = payload["metrics"]["mode_summaries"]["safe_version_replace"]
assert "answer_success_count" in current
assert "answer_rule_pass_rate" in current
assert "memory_grounding_pass_rate" in current
assert "forbidden_violation_rate" in current
assert "avg_total_token_count" in current
assert "avg_latency_ms" in current
assert replace["contract_generation_success_rate"] == 100.0
assert replace["post_check_shadow_enabled_rate"] == 100.0
assert "| mode | cases | answer_success | answer_rate | grounding_rate | forbidden_rate | contract_success | post_check_shadow | avg_tokens |" in markdown
```

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_system_path_safe_version_eval.py::test_system_path_safe_version_cli_fake_provider_writes_sanitized_report \
  -q -p no:cacheprovider
```

Expected: fail because current Markdown and mode summaries do not include answer-quality columns.

- [ ] **Step 3: Implement report summary fields**

In `_build_metrics()`, each `mode_summaries[mode]` must include:

```python
answer_success_count = sum(1 for row in rows if row["answer_rule_passed"])
grounding_success_count = sum(1 for row in rows if row["memory_grounding_passed"])
forbidden_case_count = sum(
    1
    for row in rows
    if int(row.get("forbidden_contains_violation_count", 0) or 0) > 0
)
mode_summaries[mode] = {
    "case_count": len(rows),
    "answer_success_count": answer_success_count,
    "grounding_success_count": grounding_success_count,
    "forbidden_case_count": forbidden_case_count,
    "answer_rule_pass_rate": _pct(answer_success_count, len(rows)),
    "memory_grounding_pass_rate": _pct(grounding_success_count, len(rows)),
    "forbidden_violation_rate": _pct(forbidden_case_count, len(rows)),
    "contract_generation_success_rate": _pct(len(contract_rows), len(rows)),
    "post_check_shadow_enabled_rate": _pct(len(post_rows), len(rows)),
    "avg_total_token_count": _avg(int(row.get("token_count", 0) or 0) for row in rows),
    "avg_latency_ms": _avg(int(row.get("latency_ms", 0) or 0) for row in rows),
    "token_metrics_available": any(bool(row.get("token_metrics_available")) for row in rows),
}
```

Add:

```python
def _avg(values: Iterable[object]) -> float:
    items = [float(value) for value in values]
    if not items:
        return 0.0
    return round(sum(items) / len(items), 4)
```

Update `write_system_path_safe_version_markdown()` to render:

```markdown
| mode | cases | answer_success | answer_rate | grounding_rate | forbidden_rate | contract_success | post_check_shadow | avg_tokens |
```

- [ ] **Step 4: Run fake smoke and privacy gate**

Run:

```bash
rm -rf /tmp/akashic-memory-p6o14-system-path-safe-version-fake
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace /tmp/akashic-memory-p6o14-system-path-safe-version-fake/workspace \
  --out-dir /tmp/akashic-memory-p6o14-system-path-safe-version-fake/reports \
  --fake-provider \
  --case-pack standard \
  --balanced-small \
  --common-limit 2 \
  --hard-limit 2 \
  --modes current,safe_version_replace \
  --real-memory-workspace /tmp/akashic-memory-p6o14-system-path-safe-version-fake/empty-real-workspace
if rg -n "raw_prompt|full_answer|session_text|api[_-]?key|Authorization" \
  /tmp/akashic-memory-p6o14-system-path-safe-version-fake/reports/*.md; then
  exit 1
else
  echo "p6o14 fake privacy grep ok"
fi
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path
from memory2.eval_quantitative_cases import build_quantitative_eval_cases

path = Path("/tmp/akashic-memory-p6o14-system-path-safe-version-fake/reports/system_path_safe_version_eval.json")
payload = json.loads(path.read_text(encoding="utf-8"))
text = json.dumps(payload, ensure_ascii=False)
blocked_terms = ("raw_prompt", "full_answer", "session_text", "api_key", "Authorization")
assert not any(term in text for term in blocked_terms)
cases = (
    build_quantitative_eval_cases("common", case_pack="standard", limit=2)
    + build_quantitative_eval_cases("hard", case_pack="standard", limit=2)
)
for case in cases:
    query = str(case.setup.get("query") or "").strip()
    assert not query or query not in text
    for item in case.setup.get("memory_items", []):
        if isinstance(item, dict):
            summary = str(item.get("summary") or "").strip()
            assert not summary or summary not in text
print("p6o14 fake json privacy ok")
PY
```

Expected:

```text
p6o14 fake privacy grep ok
p6o14 fake json privacy ok
```

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add memory2/eval_system_path_safe_version.py tests/test_memory_system_path_safe_version_eval.py
git commit -m "test: gate system path safe version ab report shape"
```

---

## Task 3: Run P6o-14 Small Real LLM A/B

**Files:**
- Create:
  - `my_md/memory_optimization/eval_reports/p6o14_system_path_safe_version_real_llm_ab_v1/system_path_safe_version_eval.json`
  - `my_md/memory_optimization/eval_reports/p6o14_system_path_safe_version_real_llm_ab_v1/system_path_safe_version_eval.md`

**Interfaces:**
- Consumes: Task 1 and Task 2 eval runner.
- Produces: real LLM system-path A/B report.

- [ ] **Step 1: Run real LLM A/B**

Run:

```bash
rm -rf /tmp/akashic-memory-p6o14-system-path-safe-version-real
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_memory_system_path_safe_version_eval.py \
  --workspace /tmp/akashic-memory-p6o14-system-path-safe-version-real/workspace \
  --out-dir my_md/memory_optimization/eval_reports/p6o14_system_path_safe_version_real_llm_ab_v1 \
  --config config.toml \
  --enable-real-llm \
  --case-pack standard \
  --balanced-small \
  --common-limit 20 \
  --hard-limit 20 \
  --modes current,safe_version_replace \
  --timeout-s 60 \
  --real-memory-workspace /tmp/akashic-memory-p6o14-system-path-safe-version-real/empty-real-workspace
```

Expected:

```text
my_md/memory_optimization/eval_reports/p6o14_system_path_safe_version_real_llm_ab_v1/system_path_safe_version_eval.json
my_md/memory_optimization/eval_reports/p6o14_system_path_safe_version_real_llm_ab_v1/system_path_safe_version_eval.md
```

If this exits with `missing API key for --enable-real-llm`, stop and report that P6o-14 is blocked by local config, without changing plan scope.

- [ ] **Step 2: Validate real report gates**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path

path = Path("my_md/memory_optimization/eval_reports/p6o14_system_path_safe_version_real_llm_ab_v1/system_path_safe_version_eval.json")
payload = json.loads(path.read_text(encoding="utf-8"))
m = payload["metrics"]
assert m["evaluation_level"] == "system_path_safe_version_governed"
assert m["real_llm_enabled"] is True
assert m["fake_provider_enabled"] is False
assert m["unique_case_count"] == 40
assert m["mode_count"] == 2
assert m["case_count"] == 80
assert m["provider_error_count"] == 0
assert m["timeout_count"] == 0
assert m["token_metrics_available"] is True
current = m["mode_summaries"]["current"]
replace = m["mode_summaries"]["safe_version_replace"]
assert current["case_count"] == 40
assert replace["case_count"] == 40
assert replace["contract_generation_success_rate"] == 100.0
assert replace["post_check_shadow_enabled_rate"] == 100.0
assert current["token_metrics_available"] is True
assert replace["token_metrics_available"] is True
assert replace["answer_rule_pass_rate"] >= current["answer_rule_pass_rate"]
assert replace["memory_grounding_pass_rate"] >= current["memory_grounding_pass_rate"]
assert replace["forbidden_violation_rate"] <= current["forbidden_violation_rate"]
print("p6o14 real ab gate ok")
print("current", current)
print("safe_version_replace", replace)
PY
```

Expected if the A/B passes:

```text
p6o14 real ab gate ok
```

If any assertion fails, do not massage the report. Record the failure as the P6o-14 result and proceed to docs with a failed-gate conclusion.

- [ ] **Step 3: Run report privacy grep**

Run:

```bash
if rg -n "raw_prompt|full_answer|session_text|api[_-]?key|Authorization" \
  my_md/memory_optimization/eval_reports/p6o14_system_path_safe_version_real_llm_ab_v1/*.md; then
  exit 1
else
  echo "p6o14 real report privacy grep ok"
fi
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path
from memory2.eval_quantitative_cases import build_quantitative_eval_cases

path = Path("my_md/memory_optimization/eval_reports/p6o14_system_path_safe_version_real_llm_ab_v1/system_path_safe_version_eval.json")
payload = json.loads(path.read_text(encoding="utf-8"))
text = json.dumps(payload, ensure_ascii=False)
blocked_terms = ("raw_prompt", "full_answer", "session_text", "api_key", "Authorization")
assert not any(term in text for term in blocked_terms)
cases = (
    build_quantitative_eval_cases("common", case_pack="standard", limit=20)
    + build_quantitative_eval_cases("hard", case_pack="standard", limit=20)
)
for case in cases:
    query = str(case.setup.get("query") or "").strip()
    assert not query or query not in text
    for item in case.setup.get("memory_items", []):
        if isinstance(item, dict):
            summary = str(item.get("summary") or "").strip()
            assert not summary or summary not in text
print("p6o14 real json privacy ok")
PY
```

Expected:

```text
p6o14 real report privacy grep ok
p6o14 real json privacy ok
```

- [ ] **Step 4: Commit Task 3**

Run:

```bash
git add \
  my_md/memory_optimization/eval_reports/p6o14_system_path_safe_version_real_llm_ab_v1/system_path_safe_version_eval.json \
  my_md/memory_optimization/eval_reports/p6o14_system_path_safe_version_real_llm_ab_v1/system_path_safe_version_eval.md
git commit -m "test: record p6o14 system path real llm ab"
```

---

## Task 4: Documentation And Final Verification

**Files:**
- Modify: `my_md/memory_optimization/README.md`
- Modify: `progress.md`

**Interfaces:**
- Consumes: P6o-14 real report.
- Produces: documented P6o-14 data, conclusion, and next gate.

- [ ] **Step 1: Update README**

Add a `Phase 6o14-system-path-real-llm-ab` bullet after P6o-13. Include:

- report paths;
- matrix size `40` unique cases and `80` calls;
- modes `current` and `safe_version_replace`;
- real LLM infra results;
- current vs replace answer, grounding, forbidden, token, latency, contract, and post-check numbers;
- note that `--real-memory-workspace` is intentionally unused because this A/B uses fixture-seeded temporary system-path stores;
- explicit conclusion: pass or fail against the no-worse-than-current gate;
- boundary: no production default activation.

- [ ] **Step 2: Append progress section**

Append:

```markdown
## 2026-07-29 P6o-14 system path real LLM A/B
```

Include:

- plan path;
- code commits;
- report paths;
- real A/B metrics;
- gate result;
- next step.

- [ ] **Step 3: Run verification suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_memory_system_path_safe_version_contract.py \
  tests/test_memory_system_path_safe_version_eval.py \
  tests/test_memory_engine_contract.py::test_default_memory_engine_safe_version_shadow_keeps_text_block \
  tests/test_memory_engine_contract.py::test_default_memory_engine_safe_version_replace_uses_contract_text \
  tests/test_memory_engine_contract.py::test_default_memory_engine_safe_version_replace_requires_allow_gate \
  tests/test_memory_engine_contract.py::test_default_memory_engine_off_adds_no_safe_version_metadata \
  tests/test_memory_engine_contract.py::test_default_memory_engine_replace_contract_failure_is_not_success \
  tests/test_turn_pipelines.py::test_retrieval_pipeline_defaults_safe_version_mode_off \
  tests/test_turn_pipelines.py::test_retrieval_pipeline_passes_safe_version_mode_from_config \
  tests/test_turn_pipelines.py::test_retrieval_pipeline_allows_session_metadata_shadow_override_for_tests \
  tests/test_turn_pipelines.py::test_retrieval_pipeline_rejects_session_metadata_replace_without_allow_gate \
  tests/test_turn_pipelines.py::test_retrieval_pipeline_rejects_session_metadata_replace_even_when_allow_flag_true \
  tests/test_turn_pipelines.py::test_retrieval_pipeline_allows_replace_only_from_config_gate \
  tests/test_turn_pipelines.py::test_agent_loop_passes_safe_version_config_to_default_retrieval_pipeline \
  -q -p no:cacheprovider
```

Expected: all selected tests pass.

- [ ] **Step 4: Run default regression slice**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/test_turn_pipelines.py \
  tests/test_memory_comprehensive_online_cli.py::test_comprehensive_online_cli_p6o8_safe_boundary_fake_provider_matrix_shape \
  tests/test_memory_comprehensive_online_cli.py::test_comprehensive_online_cli_p6o7_version_governed_fake_provider_matrix_shape \
  -q -p no:cacheprovider
```

Expected: all selected tests pass.

- [ ] **Step 5: Run diff and privacy hygiene**

Run:

```bash
git diff --check
if rg -n "raw_prompt|full_answer|session_text|api[_-]?key|Authorization" \
  my_md/memory_optimization/eval_reports/p6o14_system_path_safe_version_real_llm_ab_v1/*.md \
  my_md/memory_optimization/README.md; then
  exit 1
else
  echo "p6o14 docs privacy grep ok"
fi
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python - <<'PY'
import json
from pathlib import Path

path = Path("my_md/memory_optimization/eval_reports/p6o14_system_path_safe_version_real_llm_ab_v1/system_path_safe_version_eval.json")
payload = json.loads(path.read_text(encoding="utf-8"))
text = json.dumps(payload, ensure_ascii=False)
blocked_terms = ("raw_prompt", "full_answer", "session_text", "api_key", "Authorization")
assert not any(term in text for term in blocked_terms)
print("p6o14 final json privacy ok")
PY
git status --short
```

Expected:

- `git diff --check` has no output.
- privacy grep prints `p6o14 docs privacy grep ok`.
- JSON privacy check prints `p6o14 final json privacy ok`.
- `git status --short` may still show only the protected untracked P6o-13 real LLM intent directory.

- [ ] **Step 6: Commit Task 4**

Run:

```bash
git add my_md/memory_optimization/README.md progress.md
git commit -m "docs: record p6o14 system path real llm ab"
```

---

## Follow-Up Gate After This Plan

If P6o-14 passes:

- Run P6o-15 repeat stability on the system path, not the eval-only profile path.
- Suggested matrix: `current` vs `safe_version_replace`, common `20` + hard `20`, repeat `3`, baseline prompt, `240` real calls.
- Keep default production `off` until repeat stability passes.

If P6o-14 fails:

- Do not productionize replace mode.
- Compare failure records by case and mode.
- Diagnose whether failures come from answer scoring, missing expected ids, contract rendering, or replace-mode evidence loss.
- Prefer targeted hard-slice debugging over graph/all-on expansion.
