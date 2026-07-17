# Memory Phase 4 Version Chain And Provenance Shadow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变真实记忆写入、真实召回、真实 prompt 注入和 AgentLoop 的前提下，为 memory 插件增加 Phase 4a 版本链 shadow 和 Phase 4b 层级溯源 shadow，并输出可对比实验数据。

**Architecture:** Phase 4a 只读取现有 `memory_items.status` 和 `memory_replacements`，并把本轮真实召回项也并入只读快照，构建旁路版本链、当前叶子节点、回滚候选和旧版本误召回指标。版本链只统计参与 replacement 图的条目，不把普通单点 active 记忆算成链。Phase 4b 只解析现有 `source_ref`、`extra_json.scope_channel`、`extra_json.scope_chat_id` 和本轮召回项，统计来源覆盖、解析成功率、召回跨 scope 风险和孤儿记忆。两个模块都通过 `MemoryExperimentRunner` 写 JSONL trace，真实 `DefaultMemoryEngine.retrieve()` 返回值保持 baseline。

**Tech Stack:** Python 3.12+, 现有 `memory2.store.MemoryStore2`, `plugins/default_memory.DefaultMemoryEngine`, `MemoryExperimentsConfig`, `MemoryExperimentRunner`, `pytest`。

## Execution Status

Status: complete, shadow-only.

Implemented:

- `MemoryExperimentsConfig.version_chain_shadow_enabled`
- `MemoryExperimentsConfig.provenance_shadow_enabled`
- `MemoryExperimentRunner.record_version_chain_shadow()`
- `MemoryExperimentRunner.record_provenance_shadow()`
- `memory2/version_chain_experiments.py`
- `memory2/provenance_experiments.py`
- `DefaultMemoryEngine.retrieve()` Phase 4 shadow trace wiring after real injection
- bounded `_list_shadow_memory_items()` pagination helper
- Phase 4 docs under `my_md/memory_optimization`

Verification:

- focused Phase 4 suite: `45 passed`
- broader memory suite: `136 passed, 3 skipped, 1 warning`
- full pytest: `1915 passed, 3 skipped, 3 warnings`
- `compileall plugins/default_memory memory2 tests -q`: passed
- `git diff --check`: passed

Boundaries preserved:

- No `AgentLoop`, Reasoner, `ToolExecutor`, real `recall_memory`, prompt injection, or database schema changes.
- No real `fetch_messages` provenance fetch in Phase 4b.
- No active behavior switch; both Phase 4a/4b remain shadow-only.
- `uv.lock` remains excluded from this work.

## Global Constraints

- 不修改 `AgentLoop`、Reasoner、`ToolExecutor`、真实 `recall_memory` 工具执行或 prompt 组织主流程。
- 不改变 `DefaultMemoryEngine.retrieve()` 的返回值语义：真实返回仍基于 baseline `items` 和 `Retriever.build_injection_block(items)`。
- 不改数据库 schema，不新增迁移。
- Phase 4a/4b 默认关闭；开启后也只支持 shadow 记录，不切到 active。
- 不改 `MemoryStore2.upsert_item()`、`record_replacements()`、`save_item_with_supersede()` 的真实写入语义。
- 不执行真实 `fetch_messages` 回源；Phase 4b 第一版只做 `source_ref` 解析和 dry-run 指标。
- 实验失败只能写 debug 日志，不能影响用户回复。
- 不把 `uv.lock` 的本地镜像漂移纳入提交，除非依赖解析确实需要且用户明确同意。

---

## File Structure

- Modify `plugins/default_memory/config.py`
  - 给 `memory_experiments` 增加 `version_chain_shadow_enabled` 和 `provenance_shadow_enabled` 两个开关，并写入 render/load。

- Modify `plugins/default_memory/experiments.py`
  - 增加 `record_version_chain_shadow()` 和 `record_provenance_shadow()`。

- Create `memory2/version_chain_experiments.py`
  - 纯函数构建版本链 shadow 结果，输入 memory item 快照、replacement 记录和本轮召回项。

- Create `memory2/provenance_experiments.py`
  - 纯函数解析现有 `source_ref`，输出 session/message/span 层级和覆盖指标。

- Modify `plugins/default_memory/engine.py`
  - 在真实召回和真实注入完成后记录 Phase 4a/4b shadow trace。
  - 只读分页后的 `MemoryStore2.list_items_for_dashboard(status="", page_size=200)` 和 `MemoryStore2.list_replacements()`；如果总量超过单页，需要分页读取到 shadow 上限，不能只取第一页后宣称全库指标。

- Modify `tests/test_memory_experiments_config.py`
  - 验证 Phase 4 开关默认值、加载和 render。

- Modify `tests/test_memory_experiments_runner.py`
  - 验证两个新 trace feature 能写入 JSONL。

- Create `tests/test_memory_version_chain_experiments.py`
  - 验证版本链构建、链深度、当前叶子、旧版本误召回、回滚候选和冲突链指标。

- Create `tests/test_memory_provenance_experiments.py`
  - 验证 `source_ref` 解析、覆盖率、message/span 统计、孤儿记忆和跨 scope 风险指标。

- Modify `tests/test_memory_engine_contract.py`
  - 验证 Phase 4 trace 不改变真实 hits、真实 `text_block` 和 `raw["items"]`。

- Modify `my_md/memory_optimization/README.md`
- Modify `my_md/memory_optimization/01-memory-optimization-roadmap.md`
- Modify `my_md/memory_optimization/02-memory-quality-metrics.md`
- Modify `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
  - 记录 Phase 4a/4b 的范围、trace 字段、测试结论和仍未 active 化的边界。

---

### Task 1: 增加 Phase 4 开关和 trace writer

**Files:**
- Modify: `plugins/default_memory/config.py`
- Modify: `plugins/default_memory/experiments.py`
- Modify: `tests/test_memory_experiments_config.py`
- Modify: `tests/test_memory_experiments_runner.py`

**Interfaces:**
- Produces: `MemoryExperimentsConfig.version_chain_shadow_enabled: bool`
- Produces: `MemoryExperimentsConfig.provenance_shadow_enabled: bool`
- Produces: `MemoryExperimentRunner.record_version_chain_shadow(...) -> MemoryExperimentTrace | None`
- Produces: `MemoryExperimentRunner.record_provenance_shadow(...) -> MemoryExperimentTrace | None`

- [ ] **Step 1: 写 config failing tests**

Append to `tests/test_memory_experiments_config.py`:

```python
def test_memory_experiments_phase4_flags_load_from_plugin_toml(
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
                "version_chain_shadow_enabled = true",
                "provenance_shadow_enabled = true",
                "",
            ]
        ),
        encoding="utf-8",
    )

    cfg = load_default_memory_config(plugin_dir=plugin_dir)

    assert cfg.memory_experiments.version_chain_shadow_enabled is True
    assert cfg.memory_experiments.provenance_shadow_enabled is True


def test_render_default_memory_config_includes_phase4_flags() -> None:
    rendered = render_default_memory_config()

    assert "version_chain_shadow_enabled = false" in rendered
    assert "provenance_shadow_enabled = false" in rendered
```

- [ ] **Step 2: 跑 RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_experiments_config.py -q
```

Expected: FAIL because `MemoryExperimentsConfig` does not expose the Phase 4 fields yet.

- [ ] **Step 3: 实现 config 字段**

In `plugins/default_memory/config.py`, update `MemoryExperimentsConfig`:

```python
@dataclass(frozen=True)
class MemoryExperimentsConfig:
    enabled: bool = False
    mode: str = "off"
    trace_enabled: bool = True
    trace_path: str = "observe/memory_experiments.jsonl"
    graph_retrieval_enabled: bool = False
    graph_retrieval_max_nodes: int = 400
    graph_retrieval_max_hops: int = 2
    rerank_shadow_enabled: bool = False
    injection_governance_shadow_enabled: bool = False
    version_chain_shadow_enabled: bool = False
    provenance_shadow_enabled: bool = False
```

In `render_default_memory_config()`, add:

```python
f"version_chain_shadow_enabled = {str(memory_experiments.version_chain_shadow_enabled).lower()}",
f"provenance_shadow_enabled = {str(memory_experiments.provenance_shadow_enabled).lower()}",
```

In `_build_config()`, add:

```python
version_chain_shadow_enabled=bool(
    experiments.get("version_chain_shadow_enabled", False)
),
provenance_shadow_enabled=bool(
    experiments.get("provenance_shadow_enabled", False)
),
```

- [ ] **Step 4: 跑 config tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_experiments_config.py -q
```

Expected: PASS.

- [ ] **Step 5: 写 runner failing tests**

Append to `tests/test_memory_experiments_runner.py`:

```python
def test_record_version_chain_shadow_writes_trace(tmp_path: Path) -> None:
    runner = MemoryExperimentRunner(
        workspace=tmp_path,
        config=MemoryExperimentsConfig(enabled=True, mode="shadow"),
    )

    runner.record_version_chain_shadow(
        session_key="cli:local",
        turn_id="cli:local@retrieve",
        baseline_result={"baseline_recalled_ids": ["old"]},
        experimental_result={"chain_count": 1, "active_leaf_ids": ["new"]},
        metrics={"stale_recalled_count": 1, "max_chain_depth": 2},
    )

    row = _read_jsonl(tmp_path / "observe" / "memory_experiments.jsonl")[0]
    assert row["feature_name"] == "version_chain_shadow"
    assert row["experimental_result"]["active_leaf_ids"] == ["new"]
    assert row["metrics_json"]["stale_recalled_count"] == 1


def test_record_provenance_shadow_writes_trace(tmp_path: Path) -> None:
    runner = MemoryExperimentRunner(
        workspace=tmp_path,
        config=MemoryExperimentsConfig(enabled=True, mode="shadow"),
    )

    runner.record_provenance_shadow(
        session_key="cli:local",
        turn_id="cli:local@retrieve",
        baseline_result={"baseline_recalled_ids": ["m1"]},
        experimental_result={"parsed_source_refs": [{"item_id": "m1"}]},
        metrics={"source_ref_coverage": 1.0, "parse_success_rate": 1.0},
    )

    row = _read_jsonl(tmp_path / "observe" / "memory_experiments.jsonl")[0]
    assert row["feature_name"] == "provenance_shadow"
    assert row["metrics_json"]["source_ref_coverage"] == 1.0
```

- [ ] **Step 6: 跑 RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_experiments_runner.py -q
```

Expected: FAIL because `MemoryExperimentRunner` does not expose the two record methods yet.

- [ ] **Step 7: 实现 runner 方法**

In `plugins/default_memory/experiments.py`, add:

```python
def record_version_chain_shadow(
    self,
    *,
    session_key: str,
    turn_id: str,
    baseline_result: dict[str, Any],
    experimental_result: dict[str, Any],
    metrics: dict[str, Any],
) -> MemoryExperimentTrace | None:
    return self.record(
        feature_name="version_chain_shadow",
        session_key=session_key,
        turn_id=turn_id,
        baseline_result=baseline_result,
        experimental_result=experimental_result,
        metrics=metrics,
    )


def record_provenance_shadow(
    self,
    *,
    session_key: str,
    turn_id: str,
    baseline_result: dict[str, Any],
    experimental_result: dict[str, Any],
    metrics: dict[str, Any],
) -> MemoryExperimentTrace | None:
    return self.record(
        feature_name="provenance_shadow",
        session_key=session_key,
        turn_id=turn_id,
        baseline_result=baseline_result,
        experimental_result=experimental_result,
        metrics=metrics,
    )
```

- [ ] **Step 8: 跑 runner tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_experiments_runner.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add plugins/default_memory/config.py plugins/default_memory/experiments.py tests/test_memory_experiments_config.py tests/test_memory_experiments_runner.py
git commit -m "feat: add memory phase4 shadow trace flags"
```

---

### Task 2: 实现 Phase 4a 版本链 shadow 纯函数

**Files:**
- Create: `memory2/version_chain_experiments.py`
- Create: `tests/test_memory_version_chain_experiments.py`

**Interfaces:**
- Produces: `VersionChainShadowResult`
- Produces: `build_version_chain_shadow_result(memory_items, replacements, recalled_items) -> VersionChainShadowResult`

- [ ] **Step 1: 写 version chain failing tests**

Create `tests/test_memory_version_chain_experiments.py`:

```python
from memory2.version_chain_experiments import build_version_chain_shadow_result


def test_version_chain_detects_active_leaf_and_stale_recall() -> None:
    result = build_version_chain_shadow_result(
        memory_items=[
            {"id": "old", "status": "superseded", "summary": "用户喜欢英文"},
            {"id": "new", "status": "active", "summary": "用户喜欢中文"},
        ],
        replacements=[
            {
                "old_item_id": "old",
                "old_summary": "用户喜欢英文",
                "new_item_id": "new",
                "new_summary": "用户喜欢中文",
                "relation_type": "supersede",
                "source_ref": "cli:local@post_response",
            }
        ],
        recalled_items=[{"id": "old", "status": "superseded"}],
    )

    assert result.experimental_result["chain_count"] == 1
    assert result.experimental_result["active_leaf_ids"] == ["new"]
    assert result.metrics["max_chain_depth"] == 2
    assert result.metrics["stale_recalled_count"] == 1
    assert result.metrics["rollback_candidate_count"] == 1


def test_version_chain_detects_conflict_chain_with_multiple_active_leaves() -> None:
    result = build_version_chain_shadow_result(
        memory_items=[
            {"id": "root", "status": "superseded", "summary": "规则 v1"},
            {"id": "left", "status": "active", "summary": "规则 v2"},
            {"id": "right", "status": "active", "summary": "规则 v2 冲突"},
        ],
        replacements=[
            {"old_item_id": "root", "new_item_id": "left", "relation_type": "supersede"},
            {"old_item_id": "root", "new_item_id": "right", "relation_type": "supersede"},
        ],
        recalled_items=[{"id": "left", "status": "active"}],
    )

    assert result.experimental_result["chain_count"] == 1
    assert set(result.experimental_result["active_leaf_ids"]) == {"left", "right"}
    assert result.metrics["conflict_chain_count"] == 1
    assert result.metrics["active_leaf_count"] == 2


def test_version_chain_ignores_standalone_active_items() -> None:
    result = build_version_chain_shadow_result(
        memory_items=[
            {"id": "standalone", "status": "active", "summary": "普通记忆"},
            {"id": "old", "status": "superseded", "summary": "旧规则"},
            {"id": "new", "status": "active", "summary": "新规则"},
        ],
        replacements=[
            {"old_item_id": "old", "new_item_id": "new", "relation_type": "supersede"}
        ],
        recalled_items=[{"id": "standalone", "status": "active"}],
    )

    assert result.experimental_result["chain_count"] == 1
    assert result.experimental_result["active_leaf_ids"] == ["new"]
    assert result.metrics["stale_recalled_count"] == 0


def test_version_chain_uses_recalled_item_status_when_snapshot_is_incomplete() -> None:
    result = build_version_chain_shadow_result(
        memory_items=[],
        replacements=[],
        recalled_items=[{"id": "active_from_baseline", "status": "active"}],
    )

    assert result.metrics["stale_recalled_count"] == 0
```

- [ ] **Step 2: 跑 RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_version_chain_experiments.py -q
```

Expected: FAIL because `memory2.version_chain_experiments` does not exist.

- [ ] **Step 3: 创建 `memory2/version_chain_experiments.py`**

Create the module with this public shape:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VersionChainShadowResult:
    baseline_result: dict[str, Any]
    experimental_result: dict[str, Any]
    metrics: dict[str, Any]


def build_version_chain_shadow_result(
    *,
    memory_items: list[dict[str, object]],
    replacements: list[dict[str, object]],
    recalled_items: list[dict[str, object]],
) -> VersionChainShadowResult:
    items_by_id = _items_by_id(memory_items, replacements, recalled_items)
    children = _children_by_old_item(replacements)
    parents = _parents_by_new_item(replacements)
    replacement_ids = _replacement_item_ids(replacements)
    roots = _root_ids(replacement_ids, parents)
    chains = [_walk_chain(root, children) for root in roots]
    active_leaf_ids = _active_leaf_ids(chains, children, items_by_id)
    recalled_ids = _ids(recalled_items)
    stale_recalled_ids = [
        item_id
        for item_id in recalled_ids
        if _status(items_by_id.get(item_id)) != "active" or (
            item_id in replacement_ids and item_id not in active_leaf_ids
        )
    ]
    rollback_candidates = [
        str(rep.get("old_item_id"))
        for rep in replacements
        if str(rep.get("old_item_id") or "").strip()
        and str(rep.get("new_item_id") or "").strip() in active_leaf_ids
    ]
    conflict_chains = [
        chain
        for chain in chains
        if len([item_id for item_id in chain if item_id in active_leaf_ids]) > 1
    ]

    return VersionChainShadowResult(
        baseline_result={
            "baseline_recalled_ids": recalled_ids,
            "baseline_recalled_count": len(recalled_ids),
        },
        experimental_result={
            "chain_count": len(chains),
            "chains": chains,
            "active_leaf_ids": active_leaf_ids,
            "stale_recalled_ids": stale_recalled_ids,
            "rollback_candidate_ids": sorted(set(rollback_candidates)),
        },
        metrics={
            "replacement_count": len(replacements),
            "chain_count": len(chains),
            "avg_chain_depth": _avg([len(chain) for chain in chains]),
            "max_chain_depth": max([len(chain) for chain in chains], default=0),
            "active_leaf_count": len(active_leaf_ids),
            "stale_recalled_count": len(stale_recalled_ids),
            "superseded_recalled_count": sum(
                1 for item_id in recalled_ids if _status(items_by_id.get(item_id)) == "superseded"
            ),
            "rollback_candidate_count": len(set(rollback_candidates)),
            "conflict_chain_count": len(conflict_chains),
            "orphan_replacement_count": _orphan_replacement_count(replacements, items_by_id),
        },
    )
```

The module must also include `_items_by_id()`, `_replacement_item_ids()`, `_children_by_old_item()`, `_parents_by_new_item()`, `_root_ids()`, `_walk_chain()`, `_active_leaf_ids()`, `_ids()`, `_status()`, `_orphan_replacement_count()`, and `_avg()`.

Implementation notes:

- `_items_by_id(memory_items, replacements, recalled_items)` must merge, in order, persisted memory item rows, old/new replacement snapshots, and recalled items. Recalled items are included so an incomplete dashboard snapshot does not make active recalled items look stale.
- `_replacement_item_ids(replacements)` returns only ids that appear as `old_item_id` or `new_item_id`; `chain_count` and chain depth must be computed only from this graph.
- `_walk_chain(root, children)` must traverse all descendants deterministically and return a flattened stable list for that connected replacement graph. For branching replacements, the chain should include both active leaves.
- `_active_leaf_ids(chains, children, items_by_id)` returns active ids in a chain that have no outgoing replacement edge. If a chain has no active leaf, return an empty list for that chain and let metrics surface it through depth/replacement counts.

- [ ] **Step 4: 跑 version chain tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_version_chain_experiments.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add memory2/version_chain_experiments.py tests/test_memory_version_chain_experiments.py
git commit -m "feat: add memory version chain shadow analysis"
```

---

### Task 3: 实现 Phase 4b 层级溯源 shadow 纯函数

**Files:**
- Create: `memory2/provenance_experiments.py`
- Create: `tests/test_memory_provenance_experiments.py`

**Interfaces:**
- Produces: `ProvenanceShadowResult`
- Produces: `parse_source_ref(source_ref: str) -> dict[str, object]`
- Produces: `build_provenance_shadow_result(memory_items, recalled_items, scope_channel, scope_chat_id) -> ProvenanceShadowResult`

- [ ] **Step 1: 写 provenance failing tests**

Create `tests/test_memory_provenance_experiments.py`:

```python
from memory2.provenance_experiments import (
    build_provenance_shadow_result,
    parse_source_ref,
)


def test_parse_source_ref_supports_message_id_json_and_hash_suffix() -> None:
    parsed = parse_source_ref('["tg:1:2","tg:1:3"]#h:abc123')

    assert parsed["parse_ok"] is True
    assert parsed["level"] == "message"
    assert parsed["message_ids"] == ["tg:1:2", "tg:1:3"]
    assert parsed["span_or_suffix"] == "h:abc123"


def test_parse_source_ref_supports_post_response_session_ref() -> None:
    parsed = parse_source_ref("cli:local@post_response")

    assert parsed["parse_ok"] is True
    assert parsed["level"] == "session"
    assert parsed["session_key"] == "cli:local"


def test_provenance_shadow_counts_coverage_orphans_and_cross_scope_risk() -> None:
    result = build_provenance_shadow_result(
        memory_items=[
            {
                "id": "scoped",
                "source_ref": '["cli:local:1"]#profile',
                "scope_channel": "cli",
                "scope_chat_id": "local",
            },
            {"id": "orphan", "source_ref": "", "scope_channel": "", "scope_chat_id": ""},
            {
                "id": "cross",
                "source_ref": "telegram:1@post_response",
                "scope_channel": "telegram",
                "scope_chat_id": "1",
            },
        ],
        recalled_items=[{"id": "scoped"}, {"id": "cross"}],
        scope_channel="cli",
        scope_chat_id="local",
    )

    assert result.metrics["source_ref_coverage"] == 0.6667
    assert result.metrics["parse_success_rate"] == 1.0
    assert result.metrics["orphan_memory_count"] == 1
    assert result.metrics["cross_scope_risk_count"] == 1
    assert result.metrics["cross_scope_memory_count"] == 1
    assert result.metrics["message_level_source_count"] == 1


def test_provenance_shadow_cross_scope_risk_is_recall_scoped() -> None:
    result = build_provenance_shadow_result(
        memory_items=[
            {
                "id": "cross_not_recalled",
                "source_ref": "telegram:1@post_response",
                "scope_channel": "telegram",
                "scope_chat_id": "1",
            }
        ],
        recalled_items=[],
        scope_channel="cli",
        scope_chat_id="local",
    )

    assert result.metrics["cross_scope_memory_count"] == 1
    assert result.metrics["cross_scope_risk_count"] == 0
```

- [ ] **Step 2: 跑 RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_provenance_experiments.py -q
```

Expected: FAIL because `memory2.provenance_experiments` does not exist.

- [ ] **Step 3: 创建 `memory2/provenance_experiments.py`**

Create the module with this public shape:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProvenanceShadowResult:
    baseline_result: dict[str, Any]
    experimental_result: dict[str, Any]
    metrics: dict[str, Any]


def parse_source_ref(source_ref: str) -> dict[str, object]:
    raw = str(source_ref or "").strip()
    if not raw:
        return {"parse_ok": False, "level": "missing", "raw": raw}
    base, suffix = _split_suffix(raw)
    if base.startswith("["):
        message_ids = _parse_message_id_list(base)
        return {
            "parse_ok": bool(message_ids),
            "level": "message" if message_ids else "malformed",
            "raw": raw,
            "message_ids": message_ids,
            "span_or_suffix": suffix,
        }
    if "@post_response" in base:
        session_key = base.split("@", 1)[0].strip()
        return {
            "parse_ok": bool(session_key),
            "level": "session",
            "raw": raw,
            "session_key": session_key,
            "span_or_suffix": suffix,
        }
    if base.count(":") >= 2:
        return {
            "parse_ok": True,
            "level": "message",
            "raw": raw,
            "message_ids": [base],
            "span_or_suffix": suffix,
        }
    if base.count(":") == 1:
        return {
            "parse_ok": True,
            "level": "session",
            "raw": raw,
            "session_key": base,
            "span_or_suffix": suffix,
        }
    return {"parse_ok": False, "level": "malformed", "raw": raw}


def build_provenance_shadow_result(
    *,
    memory_items: list[dict[str, object]],
    recalled_items: list[dict[str, object]],
    scope_channel: str,
    scope_chat_id: str,
) -> ProvenanceShadowResult:
    parsed = []
    orphan_ids = []
    cross_scope_memory_ids = []
    recalled_ids = _ids(recalled_items)
    recalled_by_id = {
        str(item.get("id") or ""): item
        for item in recalled_items
        if str(item.get("id") or "").strip()
    }
    for item in memory_items:
        item_id = str(item.get("id") or "")
        source_ref = str(item.get("source_ref") or "")
        parsed_ref = parse_source_ref(source_ref)
        parsed_ref["item_id"] = item_id
        parsed.append(parsed_ref)
        if not source_ref.strip():
            orphan_ids.append(item_id)
        if _is_cross_scope(item, scope_channel=scope_channel, scope_chat_id=scope_chat_id):
            cross_scope_memory_ids.append(item_id)

    with_source = [item for item in memory_items if str(item.get("source_ref") or "").strip()]
    parseable = [item for item in parsed if bool(item.get("parse_ok"))]
    memory_by_id = {
        str(item.get("id") or ""): item
        for item in memory_items
        if str(item.get("id") or "").strip()
    }
    cross_scope_recalled_ids = [
        item_id
        for item_id in recalled_ids
        if _is_cross_scope(
            memory_by_id.get(item_id, recalled_by_id.get(item_id, {})),
            scope_channel=scope_channel,
            scope_chat_id=scope_chat_id,
        )
    ]
    return ProvenanceShadowResult(
        baseline_result={
            "baseline_recalled_ids": recalled_ids,
            "baseline_recalled_count": len(recalled_ids),
        },
        experimental_result={
            "parsed_source_refs": parsed,
            "orphan_memory_ids": orphan_ids,
            "cross_scope_memory_ids": cross_scope_memory_ids,
            "cross_scope_risk_ids": cross_scope_recalled_ids,
        },
        metrics={
            "source_ref_coverage": _ratio(len(with_source), len(memory_items)),
            "parse_success_rate": _ratio(len(parseable), len(with_source)),
            "source_ref_parse_success_rate": _ratio(len(parseable), len(with_source)),
            "session_level_source_count": _count_level(parsed, "session"),
            "message_level_source_count": _count_level(parsed, "message"),
            "span_level_source_count": sum(
                1 for item in parsed if str(item.get("span_or_suffix") or "").strip()
            ),
            "malformed_source_ref_count": _count_level(parsed, "malformed"),
            "orphan_memory_count": len(orphan_ids),
            "cross_scope_memory_count": len(cross_scope_memory_ids),
            "cross_scope_risk_count": len(cross_scope_recalled_ids),
        },
    )
```

The module must also include `_split_suffix()`, `_parse_message_id_list()`, `_ids()`, `_count_level()`, `_is_cross_scope()`, and `_ratio()`.

Implementation notes:

- `source_ref_coverage`, `parse_success_rate`, `orphan_memory_count`, and `cross_scope_memory_count` describe the scanned memory snapshot.
- `cross_scope_risk_count` and `cross_scope_risk_ids` describe only the current baseline recalled items. This keeps the metric aligned with the user-facing risk: whether the current prompt may receive memory from another scope.

- [ ] **Step 4: 跑 provenance tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_provenance_experiments.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add memory2/provenance_experiments.py tests/test_memory_provenance_experiments.py
git commit -m "feat: add memory provenance shadow analysis"
```

---

### Task 4: 接入 DefaultMemoryEngine shadow 记录

**Files:**
- Modify: `plugins/default_memory/engine.py`
- Modify: `tests/test_memory_engine_contract.py`

**Interfaces:**
- Consumes: `build_version_chain_shadow_result(...)`
- Consumes: `build_provenance_shadow_result(...)`
- Produces: `DefaultMemoryEngine._record_version_chain_shadow(...)`
- Produces: `DefaultMemoryEngine._record_provenance_shadow(...)`

- [ ] **Step 1: 写 engine failing tests**

Append to `tests/test_memory_engine_contract.py`:

```python
@pytest.mark.asyncio
async def test_default_memory_engine_records_version_chain_without_changing_hits() -> None:
    records: list[dict[str, object]] = []

    class _Runner:
        enabled = True

        def record_version_chain_shadow(self, **kwargs: object) -> object:
            records.append(kwargs)
            return object()

    retriever = SimpleNamespace(
        retrieve_with_lanes=AsyncMock(return_value=([{"id": "old", "status": "superseded"}], [], [])),
        build_injection_block=MagicMock(return_value=("block", ["old"])),
    )
    store = SimpleNamespace(
        list_items_for_dashboard=MagicMock(
            return_value=(
                [
                    {"id": "old", "status": "superseded", "summary": "旧规则", "source_ref": "cli:local:1"},
                    {"id": "new", "status": "active", "summary": "新规则", "source_ref": "cli:local:2"},
                ],
                2,
            )
        ),
        list_replacements=MagicMock(
            return_value=[{"old_item_id": "old", "new_item_id": "new", "relation_type": "supersede"}]
        ),
    )
    engine = _make_default_engine(retriever=cast(Any, retriever))
    engine._experiment_runner = _Runner()
    engine._v2_store = store
    engine._version_chain_shadow_enabled = True
    engine._provenance_shadow_enabled = False

    result = await engine.retrieve(
        MemoryEngineRetrieveRequest(
            query="旧规则",
            scope=MemoryScope(session_key="cli:local", channel="cli", chat_id="local"),
            top_k=3,
        )
    )

    assert result.text_block == "block"
    assert [hit.id for hit in result.hits] == ["old"]
    assert records
    assert records[0]["experimental_result"]["active_leaf_ids"] == ["new"]
    assert records[0]["metrics"]["stale_recalled_count"] == 1


@pytest.mark.asyncio
async def test_default_memory_engine_records_provenance_without_changing_prompt() -> None:
    records: list[dict[str, object]] = []

    class _Runner:
        enabled = True

        def record_provenance_shadow(self, **kwargs: object) -> object:
            records.append(kwargs)
            return object()

    retriever = SimpleNamespace(
        retrieve_with_lanes=AsyncMock(
            return_value=([{"id": "m1", "source_ref": '["cli:local:1"]#profile'}], [], [])
        ),
        build_injection_block=MagicMock(return_value=("real block", ["m1"])),
    )
    store = SimpleNamespace(
        list_items_for_dashboard=MagicMock(
            return_value=(
                [
                    {
                        "id": "m1",
                        "source_ref": '["cli:local:1"]#profile',
                        "scope_channel": "cli",
                        "scope_chat_id": "local",
                    }
                ],
                1,
            )
        )
    )
    engine = _make_default_engine(retriever=cast(Any, retriever))
    engine._experiment_runner = _Runner()
    engine._v2_store = store
    engine._version_chain_shadow_enabled = False
    engine._provenance_shadow_enabled = True

    result = await engine.retrieve(
        MemoryEngineRetrieveRequest(
            query="profile",
            scope=MemoryScope(session_key="cli:local", channel="cli", chat_id="local"),
            top_k=3,
        )
    )

    assert result.text_block == "real block"
    assert cast(list[object], cast(dict[str, object], result.raw)["items"])[0]["id"] == "m1"
    assert records
    assert records[0]["metrics"]["source_ref_coverage"] == 1.0


def test_default_memory_engine_shadow_item_listing_reads_multiple_pages() -> None:
    calls: list[dict[str, object]] = []

    def _list_items_for_dashboard(**kwargs: object) -> tuple[list[dict[str, object]], int]:
        calls.append(kwargs)
        page = int(kwargs.get("page") or 1)
        if page == 1:
            return ([{"id": "m1"}], 2)
        if page == 2:
            return ([{"id": "m2"}], 2)
        return ([], 2)

    store = SimpleNamespace(list_items_for_dashboard=MagicMock(side_effect=_list_items_for_dashboard))
    engine = _make_default_engine()
    engine._v2_store = store

    items = engine._list_shadow_memory_items(status="", page_size=1, max_pages=5)

    assert [item["id"] for item in items] == ["m1", "m2"]
    assert [call["page"] for call in calls] == [1, 2]
```

- [ ] **Step 2: 跑 RED**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_memory_engine_contract.py::test_default_memory_engine_records_version_chain_without_changing_hits \
  tests/test_memory_engine_contract.py::test_default_memory_engine_records_provenance_without_changing_prompt \
  tests/test_memory_engine_contract.py::test_default_memory_engine_shadow_item_listing_reads_multiple_pages \
  -q
```

Expected: FAIL because engine does not import or record Phase 4 shadows yet.

- [ ] **Step 3: 初始化 Phase 4 开关**

In `DefaultMemoryEngine.__init__()`, after Phase 3 flags:

```python
self._version_chain_shadow_enabled = (
    default_config.memory_experiments.version_chain_shadow_enabled
)
self._provenance_shadow_enabled = (
    default_config.memory_experiments.provenance_shadow_enabled
)
```

In `_make_default_engine()` test helper, no default field is required if each Phase 4 test sets both attributes explicitly.

- [ ] **Step 4: 添加 imports**

In `plugins/default_memory/engine.py`:

```python
from memory2.version_chain_experiments import build_version_chain_shadow_result
from memory2.provenance_experiments import build_provenance_shadow_result
```

- [ ] **Step 5: 实现 `_record_version_chain_shadow()`**

Add method near the existing shadow record helpers:

```python
def _record_version_chain_shadow(
    self,
    *,
    scope: MemoryScope,
    baseline_items: list[dict[str, object]],
) -> None:
    runner = self._experiment_runner
    if (
        runner is None
        or not bool(getattr(runner, "enabled", False))
        or not bool(getattr(self, "_version_chain_shadow_enabled", False))
        or self._v2_store is None
    ):
        return
    try:
        memory_items = self._list_shadow_memory_items(status="")
        replacements = self._v2_store.list_replacements()
        shadow = build_version_chain_shadow_result(
            memory_items=memory_items,
            replacements=replacements,
            recalled_items=baseline_items,
        )
        runner.record_version_chain_shadow(
            session_key=scope.session_key,
            turn_id=f"{scope.session_key}@retrieve",
            baseline_result=shadow.baseline_result,
            experimental_result=shadow.experimental_result,
            metrics=shadow.metrics,
        )
    except Exception:
        logger.debug("version chain shadow trace failed", exc_info=True)
```

- [ ] **Step 6: 实现 `_record_provenance_shadow()`**

Add method near `_record_version_chain_shadow()`:

```python
def _record_provenance_shadow(
    self,
    *,
    scope: MemoryScope,
    baseline_items: list[dict[str, object]],
) -> None:
    runner = self._experiment_runner
    if (
        runner is None
        or not bool(getattr(runner, "enabled", False))
        or not bool(getattr(self, "_provenance_shadow_enabled", False))
        or self._v2_store is None
    ):
        return
    try:
        memory_items = self._list_shadow_memory_items(status="")
        shadow = build_provenance_shadow_result(
            memory_items=memory_items,
            recalled_items=baseline_items,
            scope_channel=scope.channel or "",
            scope_chat_id=scope.chat_id or "",
        )
        runner.record_provenance_shadow(
            session_key=scope.session_key,
            turn_id=f"{scope.session_key}@retrieve",
            baseline_result=shadow.baseline_result,
            experimental_result=shadow.experimental_result,
            metrics=shadow.metrics,
        )
    except Exception:
        logger.debug("provenance shadow trace failed", exc_info=True)
```

- [ ] **Step 7: 在 `retrieve()` 中调用 Phase 4 shadow**

After `_record_injection_governance_shadow(...)` and before building `hits`, add:

```python
self._record_version_chain_shadow(scope=scope, baseline_items=items)
self._record_provenance_shadow(scope=scope, baseline_items=items)
```

This order makes Phase 4 observe the same baseline items and injected block that the real engine returned. It must not modify `items`, `text_block`, `injected_ids`, `hits`, or `raw`.

- [ ] **Step 8: 添加分页读取 helper**

Add this helper near other shadow helpers:

```python
def _list_shadow_memory_items(
    self,
    *,
    status: str = "",
    page_size: int = 200,
    max_pages: int = 20,
) -> list[dict[str, object]]:
    if self._v2_store is None:
        return []
    all_items: list[dict[str, object]] = []
    safe_page_size = max(1, min(int(page_size), 200))
    safe_max_pages = max(1, int(max_pages))
    for page in range(1, safe_max_pages + 1):
        rows, total = self._v2_store.list_items_for_dashboard(
            status=status,
            page=page,
            page_size=safe_page_size,
        )
        all_items.extend(rows)
        if len(all_items) >= int(total) or not rows:
            break
    return all_items
```

The helper keeps Phase 4 bounded but prevents the plan from silently reporting first-page-only version/provenance metrics as if they were complete.

- [ ] **Step 9: 跑 engine tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_memory_engine_contract.py::test_default_memory_engine_records_version_chain_without_changing_hits \
  tests/test_memory_engine_contract.py::test_default_memory_engine_records_provenance_without_changing_prompt \
  tests/test_memory_engine_contract.py::test_default_memory_engine_shadow_item_listing_reads_multiple_pages \
  -q
```

Expected: PASS.

- [ ] **Step 10: 跑 Phase 4 focused suite**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_memory_experiments_config.py \
  tests/test_memory_experiments_runner.py \
  tests/test_memory_version_chain_experiments.py \
  tests/test_memory_provenance_experiments.py \
  tests/test_memory_engine_contract.py::test_default_memory_engine_records_version_chain_without_changing_hits \
  tests/test_memory_engine_contract.py::test_default_memory_engine_records_provenance_without_changing_prompt \
  tests/test_memory_engine_contract.py::test_default_memory_engine_shadow_item_listing_reads_multiple_pages \
  -q
```

Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add plugins/default_memory/engine.py tests/test_memory_engine_contract.py
git commit -m "feat: wire memory phase4 shadow traces"
```

---

### Task 5: 文档、验证和提交边界

**Files:**
- Modify: `my_md/memory_optimization/README.md`
- Modify: `my_md/memory_optimization/01-memory-optimization-roadmap.md`
- Modify: `my_md/memory_optimization/02-memory-quality-metrics.md`
- Modify: `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`

**Interfaces:**
- Consumes: Phase 4 trace fields and verification output.
- Produces: 项目文档中的 Phase 4 实施结论。

- [ ] **Step 1: 更新 roadmap 文档**

Document these facts:

```text
Phase 4a 已完成：因果一致性版本链 shadow。
- 只读取 memory_items.status、memory_replacements 和本轮 baseline recalled items。
- 版本链只统计参与 replacement 图的条目，不把普通 active 单点记忆计入 chain_count。
- 输出 chain_count、avg_chain_depth、max_chain_depth、active_leaf_count、stale_recalled_count、superseded_recalled_count、rollback_candidate_count、conflict_chain_count、orphan_replacement_count。
- 不改变真实写入、真实召回和真实 prompt 注入。

Phase 4b 已完成：层级化溯源 shadow。
- 第一版只解析现有 source_ref，不执行真实 fetch_messages 回源。
- 输出 source_ref_coverage、parse_success_rate、message_level_source_count、session_level_source_count、span_level_source_count、malformed_source_ref_count、orphan_memory_count、cross_scope_memory_count、cross_scope_risk_count。
- cross_scope_memory_count 面向扫描快照，cross_scope_risk_count 面向本轮真实召回项。
- fetch_success_rate、evidence_precision 和 source_support_rate 留到后续带回源评测阶段。
```

- [ ] **Step 2: 更新 quality metrics 文档**

Add a section mapping Phase 4 metrics to interpretation:

```text
stale_recalled_count > 0 表示 baseline 可能召回了已经被替换的旧记忆。
conflict_chain_count > 0 表示同一替换链存在多个 active 叶子，后续 active 化前必须人工审查。
source_ref_coverage 越低，说明记忆可解释性越差。
cross_scope_memory_count > 0 表示扫描快照里存在其他 channel/chat 的来源。
cross_scope_risk_count > 0 表示当前会话真实召回项可能混入其他 channel/chat 的来源。
```

- [ ] **Step 3: 更新 README 索引**

Ensure `my_md/memory_optimization/README.md` links to the Phase 4 status and says Phase 4 is still shadow-only.

- [ ] **Step 4: 跑 broader memory suite**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_*.py tests/test_post_response_memory_experiments.py -q
```

Expected: PASS, with the same known skipped/warning pattern as the current branch unless a real regression appears.

- [ ] **Step 5: 跑 compile and diff gates**

Run:

```bash
.venv/bin/python -m compileall plugins/default_memory memory2 tests -q
git diff --check
```

Expected: both commands exit 0.

- [ ] **Step 6: Commit docs and final verification**

Do not stage `uv.lock` unless the user explicitly asks.

```bash
git add \
  my_md/memory_optimization/README.md \
  my_md/memory_optimization/01-memory-optimization-roadmap.md \
  my_md/memory_optimization/02-memory-quality-metrics.md \
  my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md
git commit -m "docs: record memory phase4 shadow results"
```

If the plan file itself should be committed, force-add it because `/docs/` is ignored:

```bash
git add -f docs/superpowers/plans/2026-07-17-memory-phase4-version-provenance-shadow.md
git commit -m "docs: add memory phase4 implementation plan"
```

---

## Self-Review

### Spec Coverage

- 因果一致性版本链：Task 2 构建 replacement-only 版本链，Task 4 接入 trace，Task 5 记录指标。
- 层级化溯源：Task 3 解析 `source_ref` 并区分扫描级和召回级跨 scope 指标，Task 4 接入 trace，Task 5 记录指标。
- 可输出测试数据：Task 1 增加开关和 trace writer；Task 2/3/4 都有 JSONL 指标；Task 4 还验证 shadow 快照不是第一页误报。
- 不改 AgentLoop 和真实行为：Global Constraints 与 Task 4 明确不修改真实返回。
- off/on 对照基础：两个开关默认 false，开启后仅 shadow。

### Placeholder Scan

No `TBD`, `TODO`, or unspecified implementation step remains. Future work is explicitly out of scope only for real `fetch_messages` 回源评测、active 化和数据库 schema 扩展。

### Type Consistency

- `MemoryExperimentsConfig.version_chain_shadow_enabled` and `provenance_shadow_enabled` are consumed by `DefaultMemoryEngine`.
- `record_version_chain_shadow()` and `record_provenance_shadow()` use the same signature style as existing Phase 2/3 trace methods.
- `build_version_chain_shadow_result()` and `build_provenance_shadow_result()` both return dataclasses with `baseline_result`, `experimental_result`, and `metrics`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-17-memory-phase4-version-provenance-shadow.md`.

Two execution options:

1. Subagent-Driven (recommended): dispatch a fresh subagent per task, review between tasks, fast iteration.
2. Inline Execution: execute tasks in this session using executing-plans, batch execution with checkpoints.
