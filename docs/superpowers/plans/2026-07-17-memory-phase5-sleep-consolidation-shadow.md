# Memory Phase5 Sleep Consolidation Shadow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 memory 插件增加 Phase5 “离线睡眠巩固”影子实验：扫描现有长期记忆，发现重复、可合并、过期、冲突和缺失溯源的候选项，并输出可对比 trace，但不修改真实记忆。

**Architecture:** 第一版只做 shadow / dry-run，不做真实后台守护进程、不合并、不删除、不改写数据库。核心算法放在 `memory2/sleep_consolidation_experiments.py`，`plugins/default_memory` 只负责配置、trace 记录和在现有异步 memory event 后触发一次有界扫描。

**Tech Stack:** Python dataclass、现有 `MemoryExperimentRunner`、现有 `MemoryStore2.list_items_for_dashboard()`、pytest、JSONL trace。

## Global Constraints

- 默认关闭：新增开关默认 `False`，不开启时行为和现有代码完全一致。
- 只做影子实验：不得修改 `memory_items`、不得写 `memory_replacements`、不得调用 `forget`、不得调用真实 merge。
- 不改 `AgentLoop`、Reasoner、`ToolExecutor`、真实 `recall_memory` 结果、真实 prompt 注入行为。
- 不新增数据库 schema。
- 不新增 LLM 调用。
- 不新增外部依赖。
- 所有扫描必须有上限，默认最多扫描 500 条 active memory。
- 所有 trace 候选输出必须有上限，避免 JSONL 过大或阻塞异步 memory 事件处理。
- `uv.lock` 当前已有本地脏改，除非用户明确要求，不要 stage 或 commit。

---

## File Structure

- Create: `memory2/sleep_consolidation_experiments.py`
  - 纯函数模块，负责候选发现、指标计算和 `SleepConsolidationShadowResult` 返回。
- Modify: `plugins/default_memory/config.py`
  - 增加 `sleep_consolidation_shadow_enabled` 和 `sleep_consolidation_max_items` 配置。
- Modify: `plugins/default_memory/experiments.py`
  - 增加 `record_sleep_consolidation_shadow()`，统一写入 `feature_name="sleep_consolidation_shadow"`。
- Modify: `plugins/default_memory/engine.py`
  - 读取配置，并在 `ConsolidationCommitted` 事件处理后触发 shadow 扫描。
- Create: `tests/test_memory_sleep_consolidation_experiments.py`
  - 覆盖纯算法：重复组、可合并候选、过期候选、冲突候选、指标。
- Modify: `tests/test_memory_experiments_config.py`
  - 覆盖新增配置解析和默认渲染。
- Modify: `tests/test_memory_experiments_runner.py`
  - 覆盖 runner trace 写入形状。
- Create: `tests/test_memory_sleep_consolidation_engine.py`
  - 覆盖开关关闭不触发、开关打开触发但不修改真实 store。
- Modify: `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
  - 更新 Phase5 状态、实现范围和测试结论。
- Modify: `my_md/memory_optimization/02-memory-quality-metrics.md`
  - 增加睡眠巩固指标解释。

---

### Task 1: 纯算法模块和测试

**Files:**
- Create: `memory2/sleep_consolidation_experiments.py`
- Create: `tests/test_memory_sleep_consolidation_experiments.py`

**Interfaces:**
- Consumes: `list[dict[str, object]]` 形态的 memory item，字段来自 `MemoryStore2.list_items_for_dashboard()`。
- Produces:
  - `SleepConsolidationShadowResult`
  - `build_sleep_consolidation_shadow_result(*, memory_items, now=None, duplicate_threshold=0.88, merge_threshold=0.55, stale_days=180, max_duplicate_groups=100, max_merge_candidates=100, max_conflict_candidates=100) -> SleepConsolidationShadowResult`

- [ ] **Step 1: Write failing tests for duplicate, merge, stale, conflict and metrics**

Add `tests/test_memory_sleep_consolidation_experiments.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone

from memory2.sleep_consolidation_experiments import (
    build_sleep_consolidation_shadow_result,
)


NOW = datetime(2026, 7, 17, tzinfo=timezone.utc)


def _item(
    item_id: str,
    summary: str,
    *,
    memory_type: str = "preference",
    updated_at: str = "2026-07-17T00:00:00+00:00",
    reinforcement: int = 1,
    emotional_weight: int = 0,
    source_ref: str = "cli:local@post_response",
    status: str = "active",
) -> dict[str, object]:
    return {
        "id": item_id,
        "summary": summary,
        "memory_type": memory_type,
        "updated_at": updated_at,
        "reinforcement": reinforcement,
        "emotional_weight": emotional_weight,
        "source_ref": source_ref,
        "status": status,
        "scope_channel": "cli",
        "scope_chat_id": "local",
    }


def test_sleep_consolidation_detects_duplicate_groups() -> None:
    result = build_sleep_consolidation_shadow_result(
        memory_items=[
            _item("m1", "用户喜欢中文回答"),
            _item("m2", "用户喜欢中文回答"),
            _item("m3", "用户使用 pytest 测试"),
        ],
        now=NOW,
    )

    assert result.experimental_result["duplicate_groups"] == [
        {"item_ids": ["m1", "m2"], "reason": "near_duplicate", "similarity": 1.0}
    ]
    assert result.metrics["scanned_count"] == 3
    assert result.metrics["duplicate_group_count"] == 1
    assert result.metrics["duplicate_item_count"] == 2
    assert result.metrics["estimated_redundancy_drop"] > 0


def test_sleep_consolidation_detects_merge_candidates() -> None:
    result = build_sleep_consolidation_shadow_result(
        memory_items=[
            _item("m1", "用户以后代码示例优先使用 pytest"),
            _item("m2", "用户代码测试示例喜欢使用 pytest"),
            _item("m3", "用户喜欢中文回答"),
        ],
        now=NOW,
    )

    candidates = result.experimental_result["merge_candidates"]
    assert candidates
    assert candidates[0]["item_ids"] == ["m1", "m2"]
    assert candidates[0]["reason"] == "same_type_related_content"
    assert result.metrics["merge_candidate_count"] == 1


def test_sleep_consolidation_detects_stale_low_value_candidates() -> None:
    result = build_sleep_consolidation_shadow_result(
        memory_items=[
            _item(
                "m1",
                "用户临时测试变量是 abc",
                memory_type="event",
                updated_at="2025-01-01T00:00:00+00:00",
                reinforcement=1,
                emotional_weight=0,
            ),
            _item(
                "m2",
                "用户强偏好中文回答",
                updated_at="2025-01-01T00:00:00+00:00",
                reinforcement=5,
                emotional_weight=4,
            ),
        ],
        now=NOW,
    )

    assert result.experimental_result["stale_candidate_ids"] == ["m1"]
    assert result.experimental_result["low_value_candidate_ids"] == ["m1"]
    assert result.metrics["stale_candidate_count"] == 1
    assert result.metrics["low_value_candidate_count"] == 1


def test_sleep_consolidation_detects_conflicts() -> None:
    result = build_sleep_consolidation_shadow_result(
        memory_items=[
            _item("m1", "用户喜欢使用中文回答"),
            _item("m2", "用户不喜欢使用中文回答"),
        ],
        now=NOW,
    )

    assert result.experimental_result["conflict_candidates"] == [
        {
            "item_ids": ["m1", "m2"],
            "reason": "opposite_preference_signal",
            "similarity": result.experimental_result["conflict_candidates"][0][
                "similarity"
            ],
        }
    ]
    assert result.metrics["conflict_candidate_count"] == 1
    assert result.experimental_result["duplicate_groups"] == []
    assert result.experimental_result["merge_candidates"] == []


def test_sleep_consolidation_limits_candidate_trace_size() -> None:
    result = build_sleep_consolidation_shadow_result(
        memory_items=[
            _item(f"m{idx}", f"用户喜欢中文回答 {idx % 2}")
            for idx in range(12)
        ],
        now=NOW,
        duplicate_threshold=0.1,
        max_duplicate_groups=3,
        max_merge_candidates=3,
        max_conflict_candidates=3,
    )

    assert len(result.experimental_result["duplicate_groups"]) <= 3
    assert result.metrics["duplicate_group_truncated_count"] >= 0
    assert result.metrics["merge_candidate_truncated_count"] >= 0
    assert result.metrics["conflict_candidate_truncated_count"] >= 0


def test_sleep_consolidation_reports_missing_source_and_token_saving() -> None:
    result = build_sleep_consolidation_shadow_result(
        memory_items=[
            _item("m1", "用户喜欢中文回答", source_ref=""),
            _item("m2", "用户喜欢中文回答", source_ref=""),
        ],
        now=NOW,
    )

    assert result.metrics["missing_source_ref_count"] == 2
    assert result.metrics["estimated_token_saving"] > 0
    assert result.baseline_result == {
        "active_memory_count": 2,
        "baseline_item_ids": ["m1", "m2"],
    }
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_sleep_consolidation_experiments.py -q
```

Expected: FAIL because `memory2.sleep_consolidation_experiments` does not exist.

- [ ] **Step 3: Implement the minimal pure module**

Create `memory2/sleep_consolidation_experiments.py` with these public objects and deterministic helpers:

```python
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class SleepConsolidationShadowResult:
    baseline_result: dict[str, Any]
    experimental_result: dict[str, Any]
    metrics: dict[str, Any]


def build_sleep_consolidation_shadow_result(
    *,
    memory_items: list[dict[str, object]],
    now: datetime | None = None,
    duplicate_threshold: float = 0.88,
    merge_threshold: float = 0.55,
    stale_days: int = 180,
    max_duplicate_groups: int = 100,
    max_merge_candidates: int = 100,
    max_conflict_candidates: int = 100,
) -> SleepConsolidationShadowResult:
    started_at = time.perf_counter()
    current_time = now or datetime.now(timezone.utc)
    active_items = [
        dict(item)
        for item in memory_items
        if str(item.get("status") or "active").strip() == "active"
        and str(item.get("id") or "").strip()
    ]
    conflict_pairs = _conflict_pair_ids(active_items)
    all_conflicts = _conflict_candidates(active_items, conflict_pairs)
    all_duplicate_groups = _duplicate_groups(
        active_items,
        duplicate_threshold,
        excluded_pairs=conflict_pairs,
    )
    all_merge_candidates = _merge_candidates(
        active_items,
        all_duplicate_groups,
        merge_threshold,
        duplicate_threshold,
        excluded_pairs=conflict_pairs,
    )
    duplicate_groups = all_duplicate_groups[: max(0, int(max_duplicate_groups))]
    merge_candidates = all_merge_candidates[: max(0, int(max_merge_candidates))]
    conflicts = all_conflicts[: max(0, int(max_conflict_candidates))]
    stale_ids = _stale_candidate_ids(active_items, now=current_time, stale_days=stale_days)
    low_value_ids = _low_value_candidate_ids(active_items, stale_ids)
    missing_source_ref_count = sum(
        1 for item in active_items if not str(item.get("source_ref") or "").strip()
    )
    duplicate_item_ids = sorted(
        {item_id for group in duplicate_groups for item_id in group["item_ids"]}
    )
    estimated_token_saving = _estimated_token_saving(
        active_items,
        duplicate_item_ids=duplicate_item_ids,
        merge_candidates=merge_candidates,
        stale_ids=stale_ids,
    )
    latency_ms = round((time.perf_counter() - started_at) * 1000, 4)

    return SleepConsolidationShadowResult(
        baseline_result={
            "active_memory_count": len(active_items),
            "baseline_item_ids": _ids(active_items),
        },
        experimental_result={
            "duplicate_groups": duplicate_groups,
            "merge_candidates": merge_candidates,
            "stale_candidate_ids": stale_ids,
            "low_value_candidate_ids": low_value_ids,
            "conflict_candidates": conflicts,
        },
        metrics={
            "scanned_count": len(active_items),
            "duplicate_group_count": len(duplicate_groups),
            "duplicate_item_count": len(duplicate_item_ids),
            "merge_candidate_count": len(merge_candidates),
            "stale_candidate_count": len(stale_ids),
            "low_value_candidate_count": len(low_value_ids),
            "conflict_candidate_count": len(conflicts),
            "missing_source_ref_count": missing_source_ref_count,
            "estimated_token_saving": estimated_token_saving,
            "estimated_redundancy_drop": _ratio(len(duplicate_item_ids), len(active_items)),
            "job_latency_ms": latency_ms,
            "applied_change_count": 0,
            "duplicate_group_truncated_count": max(
                0,
                len(all_duplicate_groups) - len(duplicate_groups),
            ),
            "merge_candidate_truncated_count": max(
                0,
                len(all_merge_candidates) - len(merge_candidates),
            ),
            "conflict_candidate_truncated_count": max(
                0,
                len(all_conflicts) - len(conflicts),
            ),
        },
    )
```

Also implement these private helpers in the same file:

```python
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_WORD_RE = re.compile(r"[A-Za-z0-9_]+")


def _ids(items: list[dict[str, object]]) -> list[str]:
    return [str(item.get("id") or "").strip() for item in items if str(item.get("id") or "").strip()]


def _tokens(text: object) -> set[str]:
    raw = str(text or "").lower()
    tokens = set(_WORD_RE.findall(raw))
    tokens.update(ch for ch in raw if _CJK_RE.match(ch))
    return {token for token in tokens if token.strip()}


def _similarity(left: dict[str, object], right: dict[str, object]) -> float:
    left_tokens = _tokens(left.get("summary"))
    right_tokens = _tokens(right.get("summary"))
    if not left_tokens or not right_tokens:
        return 0.0
    return round(len(left_tokens & right_tokens) / len(left_tokens | right_tokens), 4)


def _same_scope(left: dict[str, object], right: dict[str, object]) -> bool:
    return (
        str(left.get("scope_channel") or "") == str(right.get("scope_channel") or "")
        and str(left.get("scope_chat_id") or "") == str(right.get("scope_chat_id") or "")
    )
```

Implementation requirements:

- `_conflict_pair_ids()` must run before duplicate / merge detection and return item-id pairs that contain opposite preference markers.
- `_duplicate_groups()` groups same `memory_type` + same scope + similarity >= `duplicate_threshold`, excluding conflict pairs.
- `_merge_candidates()` returns pairs with same `memory_type` + same scope + `merge_threshold <= similarity < duplicate_threshold`, excluding already duplicated ids and conflict pairs.
- `_stale_candidate_ids()` returns active items older than `stale_days` when `reinforcement <= 1` and `emotional_weight <= 1`.
- `_low_value_candidate_ids()` returns stale items whose summary contains temporary markers like `临时`、`测试`、`本次`、`temporary` or whose `memory_type == "event"`.
- `_conflict_candidates()` returns same type/scope pairs with similarity >= 0.35 where one summary contains negative markers like `不喜欢`、`不要`、`避免`、`dislike`、`avoid` and the other contains positive preference markers like `喜欢`、`偏好`、`prefer`、`always`.
- `_estimated_token_saving()` uses `max(1, len(summary) // 4)` as a deterministic token approximation.
- `_ratio()` returns rounded 4-decimal floats and returns `0.0` when denominator is 0.
- All candidate lists must be sorted deterministically: similarity descending, then `item_ids` ascending.
- `duplicate_groups`、`merge_candidates` and `conflict_candidates` must be truncated by their max parameters, with `*_truncated_count` metrics recording dropped candidates.

- [ ] **Step 4: Run focused tests and fix only this module until green**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_sleep_consolidation_experiments.py -q
```

Expected: PASS.

---

### Task 2: 配置开关和 trace runner

**Files:**
- Modify: `plugins/default_memory/config.py`
- Modify: `plugins/default_memory/experiments.py`
- Modify: `tests/test_memory_experiments_config.py`
- Modify: `tests/test_memory_experiments_runner.py`

**Interfaces:**
- Consumes: `MemoryExperimentsConfig`
- Produces:
  - `sleep_consolidation_shadow_enabled: bool = False`
  - `sleep_consolidation_max_items: int = 500`
  - `MemoryExperimentRunner.record_sleep_consolidation_shadow(...)`

- [ ] **Step 1: Write failing config tests**

Append to `tests/test_memory_experiments_config.py`:

```python
def test_memory_experiments_phase5_flags_load_from_plugin_toml(
    tmp_path: Path,
) -> None:
    plugin_dir = tmp_path / "default_memory"
    plugin_dir.mkdir()
    (plugin_dir / "config.local.toml").write_text(
        "\n".join(
            [
                "[memory_experiments]",
                "enabled = true",
                'mode = "shadow"',
                "sleep_consolidation_shadow_enabled = true",
                "sleep_consolidation_max_items = 123",
                "",
            ]
        ),
        encoding="utf-8",
    )

    cfg = load_default_memory_config(plugin_dir=plugin_dir)

    assert cfg.memory_experiments.sleep_consolidation_shadow_enabled is True
    assert cfg.memory_experiments.sleep_consolidation_max_items == 123


def test_render_default_memory_config_includes_phase5_flags() -> None:
    rendered = render_default_memory_config()

    assert "sleep_consolidation_shadow_enabled = false" in rendered
    assert "sleep_consolidation_max_items = 500" in rendered
```

- [ ] **Step 2: Run config tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_experiments_config.py -q
```

Expected: FAIL because the new attributes are missing.

- [ ] **Step 3: Add config fields, rendering and parsing**

In `plugins/default_memory/config.py`, update `MemoryExperimentsConfig`:

```python
sleep_consolidation_shadow_enabled: bool = False
sleep_consolidation_max_items: int = 500
```

In `__post_init__`, clamp:

```python
object.__setattr__(
    self,
    "sleep_consolidation_max_items",
    max(1, min(int(self.sleep_consolidation_max_items), 5000)),
)
```

In `render_default_memory_config()`, add:

```python
f"sleep_consolidation_shadow_enabled = {str(memory_experiments.sleep_consolidation_shadow_enabled).lower()}",
f"sleep_consolidation_max_items = {memory_experiments.sleep_consolidation_max_items}",
```

In `_build_config()`, add:

```python
sleep_consolidation_shadow_enabled=bool(
    experiments.get("sleep_consolidation_shadow_enabled", False)
),
sleep_consolidation_max_items=int(
    experiments.get("sleep_consolidation_max_items", 500)
),
```

- [ ] **Step 4: Write failing runner trace test**

Append to `tests/test_memory_experiments_runner.py`:

```python
def test_record_sleep_consolidation_shadow_writes_trace(tmp_path: Path) -> None:
    runner = MemoryExperimentRunner(
        workspace=tmp_path,
        config=MemoryExperimentsConfig(enabled=True, mode="shadow"),
    )

    runner.record_sleep_consolidation_shadow(
        session_key="cli:local",
        turn_id="cli:local@sleep_consolidation",
        baseline_result={"active_memory_count": 2},
        experimental_result={"duplicate_groups": [{"item_ids": ["m1", "m2"]}]},
        metrics={"duplicate_group_count": 1, "applied_change_count": 0},
    )

    row = _read_jsonl(tmp_path / "observe" / "memory_experiments.jsonl")[0]
    assert row["feature_name"] == "sleep_consolidation_shadow"
    assert row["baseline_result"]["active_memory_count"] == 2
    assert row["metrics_json"]["duplicate_group_count"] == 1
    assert row["metrics_json"]["applied_change_count"] == 0
```

- [ ] **Step 5: Run runner tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_experiments_runner.py::test_record_sleep_consolidation_shadow_writes_trace -q
```

Expected: FAIL because the runner method is missing.

- [ ] **Step 6: Add runner method**

In `plugins/default_memory/experiments.py`, add:

```python
def record_sleep_consolidation_shadow(
    self,
    *,
    session_key: str,
    turn_id: str,
    baseline_result: dict[str, Any],
    experimental_result: dict[str, Any],
    metrics: dict[str, Any],
) -> MemoryExperimentTrace | None:
    return self.record(
        feature_name="sleep_consolidation_shadow",
        session_key=session_key,
        turn_id=turn_id,
        baseline_result=baseline_result,
        experimental_result=experimental_result,
        metrics=metrics,
    )
```

- [ ] **Step 7: Run config and runner tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_experiments_config.py tests/test_memory_experiments_runner.py -q
```

Expected: PASS.

---

### Task 3: 在 memory engine 中接入异步事件后的 shadow 扫描

**Files:**
- Modify: `plugins/default_memory/engine.py`
- Create: `tests/test_memory_sleep_consolidation_engine.py`

**Interfaces:**
- Consumes:
  - `build_sleep_consolidation_shadow_result(memory_items=...)`
  - `MemoryExperimentRunner.record_sleep_consolidation_shadow(...)`
  - `MemoryStore2.list_items_for_dashboard(status="active", page_size=...)`
- Produces:
  - `_sleep_consolidation_shadow_enabled`
  - `_sleep_consolidation_max_items`
  - `_record_sleep_consolidation_shadow_from_event(event: ConsolidationCommitted) -> None`

- [ ] **Step 1: Write engine behavior test at the smallest viable seam**

Create `tests/test_memory_sleep_consolidation_engine.py` with focused unit tests that instantiate a minimal engine-like object. The tests must prove the safety contract:

```python
from __future__ import annotations

from types import SimpleNamespace

from core.memory.events import ConsolidationCommitted
from plugins.default_memory.engine import (
    DefaultMemoryEngine,
    _session_key_from_source_ref,
)


class _Runner:
    enabled = True

    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def record_sleep_consolidation_shadow(self, **kwargs: object) -> None:
        self.records.append(dict(kwargs))


class _Store:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.update_calls = 0
        self.delete_calls = 0

    def list_items_for_dashboard(self, **kwargs: object):
        self.calls.append(dict(kwargs))
        return (
            [
                {
                    "id": "m1",
                    "summary": "用户喜欢中文回答",
                    "memory_type": "preference",
                    "status": "active",
                    "source_ref": "cli:local@post_response",
                    "scope_channel": "cli",
                    "scope_chat_id": "local",
                },
                {
                    "id": "m2",
                    "summary": "用户喜欢中文回答",
                    "memory_type": "preference",
                    "status": "active",
                    "source_ref": "cli:local@post_response",
                    "scope_channel": "cli",
                    "scope_chat_id": "local",
                },
            ],
            2,
        )

    def update_item_for_dashboard(self, *args: object, **kwargs: object) -> None:
        self.update_calls += 1

    def delete_item(self, *args: object, **kwargs: object) -> None:
        self.delete_calls += 1


def _event(source_ref: str = "cli:local@post_response") -> ConsolidationCommitted:
    return ConsolidationCommitted(
        history_entry_payloads=[],
        source_ref=source_ref,
        scope_channel="cli",
        scope_chat_id="local",
        conversation="USER: hello",
    )


def test_sleep_consolidation_shadow_records_after_consolidation_without_writes(
) -> None:
    runner = _Runner()
    store = _Store()
    engine = SimpleNamespace(
        _experiment_runner=runner,
        _sleep_consolidation_shadow_enabled=True,
        _sleep_consolidation_max_items=10,
        _v2_store=store,
    )
    engine._list_shadow_memory_items = DefaultMemoryEngine._list_shadow_memory_items.__get__(
        engine,
        DefaultMemoryEngine,
    )

    DefaultMemoryEngine._record_sleep_consolidation_shadow_from_event(
        engine,
        _event(),
    )

    assert store.calls == [{"status": "active", "page": 1, "page_size": 10}]
    assert store.update_calls == 0
    assert store.delete_calls == 0
    assert len(runner.records) == 1
    record = runner.records[0]
    assert record["session_key"] == "cli:local"
    assert record["turn_id"] == "cli:local@post_response@sleep_consolidation"
    assert record["metrics"]["applied_change_count"] == 0


def test_sleep_consolidation_shadow_disabled_does_not_scan() -> None:
    runner = _Runner()
    store = _Store()
    engine = SimpleNamespace(
        _experiment_runner=runner,
        _sleep_consolidation_shadow_enabled=False,
        _sleep_consolidation_max_items=10,
        _v2_store=store,
    )

    DefaultMemoryEngine._record_sleep_consolidation_shadow_from_event(
        engine,
        _event(),
    )

    assert store.calls == []
    assert runner.records == []


def test_session_key_from_source_ref_is_conservative() -> None:
    assert (
        _session_key_from_source_ref(
            "cli:local@post_response",
            channel="qq",
            chat_id="123",
        )
        == "cli:local"
    )
    assert (
        _session_key_from_source_ref(
            '["telegram:123:abc@message"]',
            channel="telegram",
            chat_id="123",
        )
        == "telegram:123"
    )
    assert (
        _session_key_from_source_ref(
            "cli:local@post_response#h:abc",
            channel="qq",
            chat_id="456",
        )
        == "qq:456"
    )
```

The assertion must check:

- `session_key` is derived from `event.source_ref` only for the explicit `session_key@post_response` form.
- `turn_id == f"{event.source_ref}@sleep_consolidation"`。
- `metrics["applied_change_count"] == 0`.
- `list_items_for_dashboard()` is called with `status="active"` and bounded `page_size`.
- disabled path does not scan and does not write trace.
- JSON/list source refs and `#` provenance refs fall back to `channel:chat_id`.

- [ ] **Step 2: Run the new engine test and verify failure**

Run the exact new test:

```bash
.venv/bin/python -m pytest tests/test_memory_sleep_consolidation_engine.py::test_sleep_consolidation_shadow_records_after_consolidation_without_writes -q
```

Expected: FAIL because engine method, helper and flags do not exist.

- [ ] **Step 3: Import the pure builder**

In `plugins/default_memory/engine.py`, add:

```python
from memory2.sleep_consolidation_experiments import (
    build_sleep_consolidation_shadow_result,
)
```

- [ ] **Step 4: Read config flags in `DefaultMemoryEngine.__init__`**

Near the other experiment flags, add:

```python
self._sleep_consolidation_shadow_enabled = (
    default_config.memory_experiments.sleep_consolidation_shadow_enabled
)
self._sleep_consolidation_max_items = (
    default_config.memory_experiments.sleep_consolidation_max_items
)
```

- [ ] **Step 5: Trigger shadow scan after consolidation processing**

At the end of `_on_consolidation_committed()`, after existing saves and implicit long-term extraction:

```python
self._record_sleep_consolidation_shadow_from_event(event)
```

This call must not change the existing failure behavior of consolidation extraction. The shadow helper catches its own exceptions, so a sleep-consolidation trace failure must not fail the consolidation event after the existing memory writes have completed.

Add helper:

```python
def _record_sleep_consolidation_shadow_from_event(
    self,
    event: ConsolidationCommitted,
) -> None:
    experiment_runner = getattr(self, "_experiment_runner", None)
    if (
        experiment_runner is None
        or not getattr(experiment_runner, "enabled", False)
        or not bool(getattr(self, "_sleep_consolidation_shadow_enabled", False))
        or self._v2_store is None
    ):
        return
    try:
        max_items = max(1, int(getattr(self, "_sleep_consolidation_max_items", 500)))
        memory_items = self._list_shadow_memory_items(
            status="active",
            page_size=min(max_items, 200),
            max_pages=max(1, (max_items + 199) // 200),
        )[:max_items]
        shadow = build_sleep_consolidation_shadow_result(memory_items=memory_items)
        session_key = _session_key_from_source_ref(
            event.source_ref,
            channel=event.scope_channel,
            chat_id=event.scope_chat_id,
        )
        experiment_runner.record_sleep_consolidation_shadow(
            session_key=session_key,
            turn_id=f"{event.source_ref}@sleep_consolidation",
            baseline_result=shadow.baseline_result,
            experimental_result=shadow.experimental_result,
            metrics=shadow.metrics,
        )
    except Exception:
        logger.debug("sleep consolidation shadow trace failed", exc_info=True)
```

Add module helper:

```python
def _session_key_from_source_ref(
    source_ref: str,
    *,
    channel: str,
    chat_id: str,
) -> str:
    raw = str(source_ref or "").strip()
    if raw.endswith("@post_response") and raw.count("@") == 1:
        return raw.split("@", 1)[0]
    fallback = f"{channel}:{chat_id}".strip(":")
    return fallback or "unknown:unknown"
```

Do not split JSON message-id lists, `source_ref` values with `#` suffixes, or arbitrary strings containing `@`; those forms must use the `channel:chat_id` fallback.

- [ ] **Step 6: Run engine test**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_sleep_consolidation_engine.py::test_sleep_consolidation_shadow_records_after_consolidation_without_writes -q
```

Expected: PASS.

- [ ] **Step 7: Add consolidation event call-chain test**

Append to `tests/test_memory_sleep_consolidation_engine.py`:

```python
import pytest
from unittest.mock import AsyncMock, Mock


@pytest.mark.asyncio
async def test_consolidation_event_invokes_sleep_shadow_after_existing_work() -> None:
    engine = SimpleNamespace()
    engine._save_from_consolidation = AsyncMock()
    engine._extract_implicit_long_term = AsyncMock(return_value={})
    engine._save_implicit_long_term = AsyncMock()
    engine._record_sleep_consolidation_shadow_from_event = Mock()

    await DefaultMemoryEngine._on_consolidation_committed(
        engine,
        ConsolidationCommitted(
            history_entry_payloads=[("[2026-07-17 10:00] 用户说喜欢中文", 0)],
            source_ref="cli:local@post_response",
            scope_channel="cli",
            scope_chat_id="local",
            conversation="USER: 我喜欢中文回答",
        ),
    )

    engine._save_from_consolidation.assert_awaited_once()
    engine._extract_implicit_long_term.assert_awaited_once()
    engine._save_implicit_long_term.assert_not_awaited()
    engine._record_sleep_consolidation_shadow_from_event.assert_called_once()
```

This test must use the real `_on_consolidation_committed()` method and fake only its dependencies. It proves the new shadow hook is reached through the real event path without changing the existing save/extract order.

- [ ] **Step 8: Run all engine sleep-consolidation tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_sleep_consolidation_engine.py -q
```

Expected: PASS.

---

### Task 4: 文档更新

**Files:**
- Modify: `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
- Modify: `my_md/memory_optimization/02-memory-quality-metrics.md`
- Modify: `my_md/memory_optimization/README.md`

**Interfaces:**
- Consumes: Phase5 实现结论和测试结果。
- Produces: 可在换 session 后继承的项目文档。

- [ ] **Step 1: Update roadmap Phase5 status**

In `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`, update Phase5 from `待做` to `已完成第一版 shadow dry-run` after implementation passes. The text must state:

```text
Phase 5 已完成第一版：离线睡眠巩固 shadow dry-run

- 在 `ConsolidationCommitted` 事件处理后执行有界 active memory 扫描。
- 输出重复组、可合并候选、过期候选、低价值候选、冲突候选和缺失 source_ref 数量。
- 只写 `sleep_consolidation_shadow` trace，不合并、不删除、不 supersede、不修改真实召回和 prompt 注入。
- 第一版不是常驻后台守护进程；是否做 scheduler / daemon 留到 active 化前评估。
```

- [ ] **Step 2: Update metrics doc**

In `my_md/memory_optimization/02-memory-quality-metrics.md`, add a Phase5 section with these metric definitions:

```text
- `scanned_count`：本次扫描的 active memory 数量。
- `duplicate_group_count`：高度相似的重复组数量。
- `duplicate_item_count`：参与重复组的记忆数量。
- `merge_candidate_count`：同类、同 scope、语义接近但未达到重复阈值的候选数量。
- `stale_candidate_count`：更新时间较久、强化次数低、情绪权重低的候选数量。
- `low_value_candidate_count`：过期且偏临时/事件型的候选数量。
- `conflict_candidate_count`：同一偏好方向存在相反表达的候选数量。
- `missing_source_ref_count`：缺少来源引用的记忆数量。
- `estimated_token_saving`：如果后续合并/清理候选，预计可减少的 token 量。
- `estimated_redundancy_drop`：重复项占扫描集合的比例。
- `job_latency_ms`：本次 shadow job 耗时。
- `applied_change_count`：第一版固定为 0，表示没有真实副作用。
- `duplicate_group_truncated_count`：因 trace 输出上限被截断的重复组数量。
- `merge_candidate_truncated_count`：因 trace 输出上限被截断的可合并候选数量。
- `conflict_candidate_truncated_count`：因 trace 输出上限被截断的冲突候选数量。
- `stale_candidate_truncated_count`：因 trace 输出上限被截断的过期候选数量。
- `low_value_candidate_truncated_count`：因 trace 输出上限被截断的低价值候选数量。
```

- [ ] **Step 3: Update README link**

Ensure `my_md/memory_optimization/README.md` references Phase5 sleep consolidation and points to the roadmap and metrics docs.

- [ ] **Step 4: Check docs for stale “待做” wording**

Run:

```bash
rg -n "Phase 5|睡眠巩固|sleep_consolidation" my_md/memory_optimization
```

Expected: all Phase5 mentions match the implemented shadow-only scope.

---

### Task 5: Verification and commit

**Files:**
- All files touched above.

**Interfaces:**
- Produces: one commit for Phase5 if all verification passes.

- [ ] **Step 1: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_memory_sleep_consolidation_experiments.py \
  tests/test_memory_sleep_consolidation_engine.py \
  tests/test_memory_experiments_config.py \
  tests/test_memory_experiments_runner.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run broader memory tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_*.py tests/test_post_response_memory_experiments.py -q
```

Expected: PASS, with existing skips/warnings allowed only if unrelated and already present.

- [ ] **Step 3: Compile touched Python packages**

Run:

```bash
.venv/bin/python -m compileall plugins/default_memory memory2 tests -q
```

Expected: no output and exit code 0.

- [ ] **Step 4: Check whitespace**

Run:

```bash
git diff --check
```

Expected: no output and exit code 0.

- [ ] **Step 5: Review dirty files**

Run:

```bash
git status --short
```

Expected:

```text
 M plugins/default_memory/config.py
 M plugins/default_memory/engine.py
 M plugins/default_memory/experiments.py
 M tests/test_memory_experiments_config.py
 M tests/test_memory_experiments_runner.py
 M my_md/memory_optimization/README.md
 M my_md/memory_optimization/02-memory-quality-metrics.md
 M my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md
 M uv.lock
?? memory2/sleep_consolidation_experiments.py
?? tests/test_memory_sleep_consolidation_engine.py
?? tests/test_memory_sleep_consolidation_experiments.py
?? docs/superpowers/plans/2026-07-17-memory-phase5-sleep-consolidation-shadow.md  # if not already tracked
```

Do not stage `uv.lock` unless the user explicitly asks.

- [ ] **Step 6: Stage only Phase5 files**

Run:

```bash
git add \
  plugins/default_memory/config.py \
  plugins/default_memory/engine.py \
  plugins/default_memory/experiments.py \
  memory2/sleep_consolidation_experiments.py \
  tests/test_memory_sleep_consolidation_engine.py \
  tests/test_memory_sleep_consolidation_experiments.py \
  tests/test_memory_experiments_config.py \
  tests/test_memory_experiments_runner.py \
  my_md/memory_optimization/README.md \
  my_md/memory_optimization/02-memory-quality-metrics.md \
  my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md
git add -f docs/superpowers/plans/2026-07-17-memory-phase5-sleep-consolidation-shadow.md
```

If the plan file is already tracked, the second command is harmless; it is required only because `docs/` is ignored in this worktree.

- [ ] **Step 7: Commit**

Run:

```bash
git commit -m "feat: add memory sleep consolidation shadow experiment"
```

Expected: commit succeeds; `uv.lock` remains unstaged if it is still dirty.

---

## Self-Review

**Spec coverage:** The plan covers Phase5 sleep consolidation dry-run, duplicate detection, merge candidates, stale / low-value candidates, conflict candidates, token saving estimate, trace output, trace truncation, config switch, bounded scanning, docs, tests and commit.

**Placeholder scan:** No deferred implementation markers remain. Each test and public interface is named explicitly.

**Type consistency:** The public result type is consistently named `SleepConsolidationShadowResult`; the builder is consistently named `build_sleep_consolidation_shadow_result`; the runner method is consistently named `record_sleep_consolidation_shadow`; the config fields are consistently named `sleep_consolidation_shadow_enabled` and `sleep_consolidation_max_items`.

**Boundary check:** The plan does not change `AgentLoop`、Reasoner、`ToolExecutor`、真实 `recall_memory`、真实 prompt 注入或数据库 schema。第一版 `applied_change_count` 固定为 0，保证没有真实副作用；候选输出有上限，避免 shadow trace 放大异步事件成本。
