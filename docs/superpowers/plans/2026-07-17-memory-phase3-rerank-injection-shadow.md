# Memory Phase 3 Rerank And Injection Governance Shadow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变真实召回、真实注入和 AgentLoop 的前提下，为 memory 插件增加 Phase 3a 质量重排 shadow 和 Phase 3b 注入治理 shadow，并输出可对比实验数据。

**Architecture:** Phase 3a 在现有 baseline hits、三路召回候选和图谱候选之上做纯函数重排，只记录候选名次、分数拆解和 overlap 指标。Phase 3b 消费真实注入结果和 Phase 3a 的实验候选，模拟“哪些记忆应该进入 prompt、哪些应该丢弃以及原因”，但真实 `text_block`、`hits`、`raw["items"]` 全部保持 baseline。实验数据继续通过 `MemoryExperimentRunner` 写入 JSONL trace。

**Tech Stack:** Python 3.12+, 现有 `memory2` 检索实验模块, `pytest`, 现有 JSONL 实验写入器, `DefaultMemoryEngine`, `MemoryExperimentsConfig`。

## Global Constraints

- 不修改 `AgentLoop`、Reasoner、`ToolExecutor`、真实 `recall_memory` 工具执行或 prompt 组织主流程。
- 不改变 `DefaultMemoryEngine.retrieve()` 的返回值语义：真实返回仍基于 baseline `items` 和 `Retriever.build_injection_block(items)`。
- 不改数据库 schema，不新增迁移。
- Phase 3a/3b 默认关闭；开启后也只支持 shadow 记录，不切到 active。
- 真实 `text_block`、`hits[].injected`、`raw["items"]` 不受 Phase 3a/3b 影响。
- 实验失败只能写 debug 日志，不能影响用户回复。
- 不把 `uv.lock` 的本地镜像漂移纳入提交，除非依赖解析确实需要且用户明确同意。

---

## File Structure

- Modify `plugins/default_memory/config.py`
  - 给 `memory_experiments` 增加 `rerank_shadow_enabled` 和 `injection_governance_shadow_enabled` 两个开关，并写入 render/load。

- Create `memory2/rerank_experiments.py`
  - 实现 Phase 3a 的候选池融合、质量重排、分数拆解和指标统计。

- Create `memory2/injection_governance_experiments.py`
  - 实现 Phase 3b 的注入治理模拟、丢弃原因、注入原因和字符预算对比。

- Modify `plugins/default_memory/experiments.py`
  - 增加 `record_rerank_shadow()` 和 `record_injection_governance_shadow()`。

- Modify `plugins/default_memory/engine.py`
  - 在真实检索后、真实注入前构建 Phase 3a shadow；在真实注入后构建 Phase 3b shadow。
  - 任何 shadow 异常只记录 debug，不影响 baseline 返回。

- Modify `tests/test_memory_experiments_config.py`
  - 验证新开关默认值、加载和 render。

- Modify `tests/test_memory_experiments_runner.py`
  - 验证两个新 trace feature 能写入 JSONL。

- Create `tests/test_memory_rerank_experiments.py`
  - 验证重排分数、rank delta、overlap 和 score breakdown。

- Create `tests/test_memory_injection_governance_experiments.py`
  - 验证注入治理的 allow/drop 原因、预算控制和 prompt delta。

- Modify `tests/test_memory_engine_contract.py`
  - 验证 Phase 3a/3b trace 不改变真实 hits 和注入块。

- Modify `my_md/memory_optimization/01-memory-optimization-roadmap.md`
- Modify `my_md/memory_optimization/02-memory-quality-metrics.md`
- Modify `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
- Modify `my_md/memory_optimization/README.md`
  - 记录 Phase 3a/3b 的范围、trace 字段、测试结论和仍未切 active 的边界。

---

### Task 1: 增加 Phase 3 开关和 trace writer

**Files:**
- Modify: `plugins/default_memory/config.py`
- Modify: `plugins/default_memory/experiments.py`
- Modify: `tests/test_memory_experiments_config.py`
- Modify: `tests/test_memory_experiments_runner.py`

**Interfaces:**
- Produces: `MemoryExperimentsConfig.rerank_shadow_enabled: bool`
- Produces: `MemoryExperimentsConfig.injection_governance_shadow_enabled: bool`
- Produces: `MemoryExperimentRunner.record_rerank_shadow(...) -> MemoryExperimentTrace | None`
- Produces: `MemoryExperimentRunner.record_injection_governance_shadow(...) -> MemoryExperimentTrace | None`

- [ ] **Step 1: 写 config failing tests**

Append these tests to `tests/test_memory_experiments_config.py`:

```python
def test_memory_experiments_phase3_flags_load_from_plugin_toml(tmp_path: Path) -> None:
    (tmp_path / "config.local.toml").write_text(
        "\n".join(
            [
                "[memory_experiments]",
                "enabled = true",
                'mode = "shadow"',
                "rerank_shadow_enabled = true",
                "injection_governance_shadow_enabled = true",
            ]
        ),
        encoding="utf-8",
    )

    cfg = load_default_memory_config(plugin_dir=tmp_path)

    assert cfg.memory_experiments.rerank_shadow_enabled is True
    assert cfg.memory_experiments.injection_governance_shadow_enabled is True


def test_render_default_memory_config_includes_phase3_flags() -> None:
    rendered = render_default_memory_config()

    assert "rerank_shadow_enabled = false" in rendered
    assert "injection_governance_shadow_enabled = false" in rendered
```

- [ ] **Step 2: 跑 RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_experiments_config.py -q
```

Expected: FAIL because `MemoryExperimentsConfig` does not yet expose the two fields.

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
```

In `render_default_memory_config()`, add these lines after graph fields:

```python
f"rerank_shadow_enabled = {str(memory_experiments.rerank_shadow_enabled).lower()}",
f"injection_governance_shadow_enabled = {str(memory_experiments.injection_governance_shadow_enabled).lower()}",
```

In `_build_config()`, pass:

```python
rerank_shadow_enabled=bool(experiments.get("rerank_shadow_enabled", False)),
injection_governance_shadow_enabled=bool(
    experiments.get("injection_governance_shadow_enabled", False)
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
def test_record_rerank_shadow_writes_trace(tmp_path: Path) -> None:
    trace_path = tmp_path / "memory_experiments.jsonl"
    runner = MemoryExperimentRunner(
        workspace=tmp_path,
        config=MemoryExperimentsConfig(
            enabled=True,
            mode="shadow",
            trace_path=str(trace_path),
        ),
    )

    runner.record_rerank_shadow(
        session_key="cli:local",
        turn_id="cli:local@retrieve",
        baseline_result={"baseline_ids": ["m1"]},
        experimental_result={"reranked_ids": ["m2", "m1"]},
        metrics={"rerank_changed_count": 2},
    )

    row = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])
    assert row["feature_name"] == "rerank_shadow"
    assert row["experimental_result"]["reranked_ids"] == ["m2", "m1"]
    assert row["metrics_json"]["rerank_changed_count"] == 2


def test_record_injection_governance_shadow_writes_trace(tmp_path: Path) -> None:
    trace_path = tmp_path / "memory_experiments.jsonl"
    runner = MemoryExperimentRunner(
        workspace=tmp_path,
        config=MemoryExperimentsConfig(
            enabled=True,
            mode="shadow",
            trace_path=str(trace_path),
        ),
    )

    runner.record_injection_governance_shadow(
        session_key="cli:local",
        turn_id="cli:local@retrieve",
        baseline_result={"baseline_injected_ids": ["m1"]},
        experimental_result={"experimental_injected_ids": ["m2"]},
        metrics={"prompt_token_delta": -12},
    )

    row = json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])
    assert row["feature_name"] == "injection_governance_shadow"
    assert row["experimental_result"]["experimental_injected_ids"] == ["m2"]
    assert row["metrics_json"]["prompt_token_delta"] == -12
```

- [ ] **Step 6: 跑 RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_experiments_runner.py -q
```

Expected: FAIL because runner does not yet expose the two record methods.

- [ ] **Step 7: 实现 runner 方法**

In `plugins/default_memory/experiments.py`, add:

```python
def record_rerank_shadow(
    self,
    *,
    session_key: str,
    turn_id: str,
    baseline_result: dict[str, Any],
    experimental_result: dict[str, Any],
    metrics: dict[str, Any],
) -> MemoryExperimentTrace | None:
    return self.record(
        feature_name="rerank_shadow",
        session_key=session_key,
        turn_id=turn_id,
        baseline_result=baseline_result,
        experimental_result=experimental_result,
        metrics=metrics,
    )


def record_injection_governance_shadow(
    self,
    *,
    session_key: str,
    turn_id: str,
    baseline_result: dict[str, Any],
    experimental_result: dict[str, Any],
    metrics: dict[str, Any],
) -> MemoryExperimentTrace | None:
    return self.record(
        feature_name="injection_governance_shadow",
        session_key=session_key,
        turn_id=turn_id,
        baseline_result=baseline_result,
        experimental_result=experimental_result,
        metrics=metrics,
    )
```

- [ ] **Step 8: 跑 Task 1 tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_experiments_config.py tests/test_memory_experiments_runner.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit Task 1**

Run:

```bash
git add plugins/default_memory/config.py plugins/default_memory/experiments.py tests/test_memory_experiments_config.py tests/test_memory_experiments_runner.py
git commit -m "feat: add memory phase3 experiment trace flags"
```

---

### Task 2: 实现 Phase 3a 质量重排 shadow

**Files:**
- Create: `memory2/rerank_experiments.py`
- Create: `tests/test_memory_rerank_experiments.py`

**Interfaces:**
- Consumes: `RetrievalLaneResult` and `rrf_fuse_lanes()` from `memory2.retrieval_experiments`
- Produces: `RerankShadowResult`
- Produces: `build_rerank_shadow_result(...) -> RerankShadowResult`

- [ ] **Step 1: 写 rerank failing tests**

Create `tests/test_memory_rerank_experiments.py`:

```python
from __future__ import annotations

from memory2.rerank_experiments import build_rerank_shadow_result


def test_build_rerank_shadow_result_prefers_scoped_procedure_with_source() -> None:
    result = build_rerank_shadow_result(
        query="以后查资料怎么处理",
        baseline_items=[
            {
                "id": "m1",
                "memory_type": "event",
                "summary": "用户昨天讨论了资料检索",
                "score": 0.88,
                "scope_channel": "cli",
                "scope_chat_id": "local",
                "source_ref": "cli:local:1",
            },
            {
                "id": "m2",
                "memory_type": "procedure",
                "summary": "查资料时优先交叉验证多个来源",
                "score": 0.72,
                "scope_channel": "cli",
                "scope_chat_id": "local",
                "source_ref": "cli:local:2",
                "extra_json": {"tool_requirement": "web"},
            },
        ],
        semantic_items=[{"id": "m1", "score": 0.88}, {"id": "m2", "score": 0.72}],
        keyword_items=[],
        provenance_items=[{"id": "m2", "provenance_score": 0.85}],
        graph_items=[],
        scope_channel="cli",
        scope_chat_id="local",
        top_n=2,
    )

    assert result.baseline_result["baseline_ids"] == ["m1", "m2"]
    assert result.experimental_result["reranked_ids"][0] == "m2"
    assert result.metrics["rerank_changed_count"] == 2
    first = result.experimental_result["ranked_items"][0]
    assert first["id"] == "m2"
    assert first["score_breakdown"]["type_weight"] > 0
    assert first["score_breakdown"]["source_ref_weight"] > 0
    assert first["rank_delta"] < 0


def test_build_rerank_shadow_result_penalizes_low_confidence_and_long_items() -> None:
    result = build_rerank_shadow_result(
        query="项目偏好",
        baseline_items=[
            {
                "id": "long",
                "memory_type": "profile",
                "summary": "x" * 900,
                "score": 0.51,
                "scope_channel": "cli",
                "scope_chat_id": "local",
            },
            {
                "id": "short",
                "memory_type": "preference",
                "summary": "用户希望回答尽量使用中文",
                "score": 0.7,
                "scope_channel": "cli",
                "scope_chat_id": "local",
                "source_ref": "cli:local:3",
            },
        ],
        semantic_items=[],
        keyword_items=[],
        provenance_items=[],
        graph_items=[],
        scope_channel="cli",
        scope_chat_id="local",
        top_n=2,
    )

    assert result.experimental_result["reranked_ids"] == ["short", "long"]
    long_item = next(
        item for item in result.experimental_result["ranked_items"] if item["id"] == "long"
    )
    assert long_item["score_breakdown"]["low_confidence_penalty"] < 0
    assert long_item["score_breakdown"]["length_penalty"] < 0
    assert result.metrics["baseline_experimental_overlap_rate"] == 1.0
```

- [ ] **Step 2: 跑 RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_rerank_experiments.py -q
```

Expected: FAIL because `memory2.rerank_experiments` does not exist.

- [ ] **Step 3: 创建 `memory2/rerank_experiments.py`**

Implement the module with this public shape:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from memory2.retrieval_experiments import RetrievalLaneResult, rrf_fuse_lanes


@dataclass(frozen=True)
class RerankShadowResult:
    baseline_result: dict[str, Any]
    experimental_result: dict[str, Any]
    metrics: dict[str, Any]


def build_rerank_shadow_result(
    *,
    query: str,
    baseline_items: list[dict[str, object]],
    semantic_items: list[dict[str, object]],
    keyword_items: list[dict[str, object]],
    provenance_items: list[dict[str, object]],
    graph_items: list[dict[str, object]] | None = None,
    scope_channel: str = "",
    scope_chat_id: str = "",
    top_n: int = 8,
) -> RerankShadowResult:
    safe_top_n = max(1, int(top_n))
    candidate_pool = _candidate_pool(
        baseline_items=baseline_items,
        semantic_items=semantic_items,
        keyword_items=keyword_items,
        provenance_items=provenance_items,
        graph_items=graph_items or [],
        top_n=max(safe_top_n, len(baseline_items), 1),
    )
    baseline_ids = _ids(baseline_items)
    baseline_pos = {item_id: index for index, item_id in enumerate(baseline_ids)}
    ranked = []
    for index, item in enumerate(candidate_pool):
        item_id = _hit_id(item)
        if not item_id:
            continue
        breakdown = _score_breakdown(
            item,
            scope_channel=scope_channel,
            scope_chat_id=scope_chat_id,
        )
        final_score = round(sum(breakdown.values()), 6)
        raw_rank = baseline_pos.get(item_id, index) + 1
        ranked.append((final_score, item_id, raw_rank, dict(item), breakdown))

    ranked.sort(key=lambda entry: (entry[0], _item_score(entry[3]), entry[1]), reverse=True)
    ranked_items: list[dict[str, object]] = []
    for experimental_index, (final_score, item_id, raw_rank, item, breakdown) in enumerate(
        ranked[:safe_top_n], start=1
    ):
        item["experimental_score"] = final_score
        item["raw_rank"] = raw_rank
        item["experimental_rank"] = experimental_index
        item["rank_delta"] = experimental_index - raw_rank
        item["score_breakdown"] = breakdown
        ranked_items.append(item)

    reranked_ids = _ids(ranked_items)
    return RerankShadowResult(
        baseline_result={
            "query": query,
            "baseline_hit_count": len(baseline_items),
            "baseline_ids": baseline_ids,
        },
        experimental_result={
            "candidate_count": len(candidate_pool),
            "reranked_hit_count": len(ranked_items),
            "reranked_ids": reranked_ids,
            "ranked_items": ranked_items,
        },
        metrics={
            "rerank_changed_count": _rerank_changed_count(baseline_ids, reranked_ids),
            "baseline_experimental_overlap_rate": _overlap_rate(baseline_ids, reranked_ids),
            "avg_experimental_score": _avg(
                [float(item.get("experimental_score") or 0.0) for item in ranked_items]
            ),
            "scope_match_count": sum(
                1
                for item in ranked_items
                if item.get("scope_channel") == scope_channel
                and item.get("scope_chat_id") == scope_chat_id
            ),
            "source_ref_count": sum(1 for item in ranked_items if str(item.get("source_ref") or "").strip()),
        },
    )
```

Also implement private helpers in the same file:

```python
def _candidate_pool(
    *,
    baseline_items: list[dict[str, object]],
    semantic_items: list[dict[str, object]],
    keyword_items: list[dict[str, object]],
    provenance_items: list[dict[str, object]],
    graph_items: list[dict[str, object]],
    top_n: int,
) -> list[dict[str, object]]:
    lanes = [
        RetrievalLaneResult("baseline", baseline_items),
        RetrievalLaneResult("semantic", sorted(semantic_items, key=_item_score, reverse=True)),
        RetrievalLaneResult("keyword", keyword_items),
        RetrievalLaneResult("provenance", provenance_items),
    ]
    if graph_items:
        lanes.append(RetrievalLaneResult("graph", graph_items))
    all_items = [
        *baseline_items,
        *semantic_items,
        *keyword_items,
        *provenance_items,
        *graph_items,
    ]
    unique_item_count = len({item_id for item in all_items if (item_id := _hit_id(item))})
    fused = rrf_fuse_lanes(
        lanes,
        top_n=max(1, int(top_n), unique_item_count),
    )
    by_id: dict[str, dict[str, object]] = {}
    for source_item in all_items:
        item_id = _hit_id(source_item)
        if not item_id:
            continue
        merged = dict(by_id.get(item_id, {}))
        merged.update(source_item)
        by_id[item_id] = merged
    for item in fused:
        item_id = _hit_id(item)
        if not item_id:
            continue
        merged = dict(by_id.get(item_id, {}))
        merged.update(item)
        by_id[item_id] = merged
    return [by_id[item_id] for item_id in _ids(fused) if item_id in by_id]


def _score_breakdown(
    item: dict[str, object],
    *,
    scope_channel: str,
    scope_chat_id: str,
) -> dict[str, float]:
    memory_type = str(item.get("memory_type") or "")
    summary = str(item.get("summary") or "")
    score = _item_score(item)
    type_weights = {
        "procedure": 0.18,
        "preference": 0.14,
        "profile": 0.08,
        "event": 0.04,
    }
    scope_match = (
        bool(scope_channel or scope_chat_id)
        and str(item.get("scope_channel") or "") == str(scope_channel or "")
        and str(item.get("scope_chat_id") or "") == str(scope_chat_id or "")
    )
    breakdown = {
        "base_score": round(score, 6),
        "rrf_weight": round(float(item.get("rrf_score") or 0.0), 6),
        "scope_weight": 0.15 if scope_match else 0.0,
        "type_weight": type_weights.get(memory_type, 0.0),
        "source_ref_weight": 0.08 if str(item.get("source_ref") or "").strip() else 0.0,
        "provenance_weight": round(min(0.08, float(item.get("provenance_score") or 0.0) * 0.08), 6),
        "graph_weight": round(min(0.1, float(item.get("graph_score") or 0.0) * 0.1), 6),
        "low_confidence_penalty": -0.08 if score and score < 0.6 else 0.0,
        "length_penalty": -0.06 if len(summary) > 600 else 0.0,
        "missing_source_penalty": -0.04 if not str(item.get("source_ref") or "").strip() else 0.0,
    }
    return breakdown
```

The module must also include `_hit_id()`, `_ids()`, `_item_score()`, `_rerank_changed_count()`, `_overlap_rate()`, and `_avg()` helpers. Use the same semantics as existing retrieval experiment helpers.

- [ ] **Step 4: 跑 rerank tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_rerank_experiments.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add memory2/rerank_experiments.py tests/test_memory_rerank_experiments.py
git commit -m "feat: add memory rerank shadow scoring"
```

---

### Task 3: 把 Phase 3a 接入 DefaultMemoryEngine

**Files:**
- Modify: `plugins/default_memory/engine.py`
- Modify: `tests/test_memory_engine_contract.py`

**Interfaces:**
- Consumes: `build_rerank_shadow_result(...)`
- Produces: `DefaultMemoryEngine._build_rerank_shadow(...)`
- Produces: `DefaultMemoryEngine._record_rerank_shadow(...)`

- [ ] **Step 1: 写 engine failing test**

Append to `tests/test_memory_engine_contract.py`:

```python
@pytest.mark.asyncio
async def test_default_memory_engine_records_rerank_shadow_without_changing_hits() -> None:
    records: list[dict[str, object]] = []

    class _Runner:
        enabled = True

        def record_tri_retrieval_shadow(self, **kwargs: object) -> object:
            return object()

        def record_graph_retrieval_shadow(self, **kwargs: object) -> object:
            return object()

        def record_rerank_shadow(self, **kwargs: object) -> object:
            records.append(kwargs)
            return object()

    retriever = SimpleNamespace(
        retrieve_with_lanes=AsyncMock(
            return_value=(
                [
                    {
                        "id": "baseline",
                        "memory_type": "event",
                        "summary": "base",
                        "score": 0.88,
                    }
                ],
                [{"id": "semantic", "summary": "sem", "score": 0.8}],
                [{"id": "keyword", "summary": "key", "keyword_score": 0.7}],
            )
        ),
        build_injection_block=MagicMock(return_value=("block", ["baseline"])),
    )
    store = SimpleNamespace(
        list_items_for_dashboard=MagicMock(
            return_value=(
                [
                    {
                        "id": "prov",
                        "memory_type": "procedure",
                        "summary": "上次方案需要保留来源",
                        "source_ref": "cli:local:1",
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
    engine._rerank_shadow_enabled = True
    engine._graph_retrieval_enabled = False

    result = await engine.retrieve(
        MemoryEngineRetrieveRequest(
            query="上次那个方案",
            scope=MemoryScope(session_key="cli:local", channel="cli", chat_id="local"),
            hints={"memory_types": ["event", "procedure"], "require_scope_match": True},
            top_k=3,
        )
    )

    assert [hit.id for hit in result.hits] == ["baseline"]
    assert result.text_block == "block"
    assert records
    assert records[0]["baseline_result"]["baseline_ids"] == ["baseline"]
    assert "reranked_ids" in records[0]["experimental_result"]
```

- [ ] **Step 2: 跑 RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_engine_contract.py::test_default_memory_engine_records_rerank_shadow_without_changing_hits -q
```

Expected: FAIL because engine does not yet import or record rerank shadow.

- [ ] **Step 3: 在 engine 初始化 Phase 3a 开关**

In `DefaultMemoryEngine.__init__()`, after graph config assignment, add:

```python
self._rerank_shadow_enabled = (
    default_config.memory_experiments.rerank_shadow_enabled
)
self._injection_governance_shadow_enabled = (
    default_config.memory_experiments.injection_governance_shadow_enabled
)
```

Also make `_make_default_engine()` tests set these attributes where needed, or make record methods use `getattr(..., False)`.

- [ ] **Step 4: 实现 `_build_rerank_shadow()` 和 `_record_rerank_shadow()`**

In `plugins/default_memory/engine.py`, import:

```python
from memory2.rerank_experiments import RerankShadowResult, build_rerank_shadow_result
```

Add methods near existing `_record_graph_retrieval_shadow()`:

```python
async def _build_rerank_shadow(
    self,
    *,
    request: MemoryEngineRetrieveRequest,
    baseline_items: list[dict],
    semantic_items: list[dict],
    keyword_items: list[dict],
    memory_types: list[str] | None,
    scope: MemoryScope,
) -> RerankShadowResult | None:
    if self._v2_store is None:
        return None
    top_k = max(1, int(request.top_k or len(baseline_items) or 8))
    active_items, _total = self._v2_store.list_items_for_dashboard(
        status="active",
        page_size=max(200, top_k * 20),
    )
    active_items = self._filter_provenance_candidates(
        active_items,
        memory_types=memory_types,
        scope=scope,
        require_scope_match=bool(request.hints.get("require_scope_match", False)),
    )
    provenance_lane = build_provenance_lane(
        request.query,
        active_items,
        scope_channel=scope.channel,
        scope_chat_id=scope.chat_id,
        limit=max(20, top_k * 2),
    )
    graph_items: list[dict[str, object]] = []
    if bool(getattr(self, "_graph_retrieval_enabled", False)):
        graph_lane = build_graph_lane(
            request.query,
            active_items,
            scope_channel=scope.channel or "",
            scope_chat_id=scope.chat_id or "",
            limit=max(20, top_k * 2),
            max_hops=max(1, int(getattr(self, "_graph_retrieval_max_hops", 2))),
            max_nodes=max(1, int(getattr(self, "_graph_retrieval_max_nodes", 400))),
        )
        graph_items = graph_lane.items
    return build_rerank_shadow_result(
        query=request.query,
        baseline_items=baseline_items,
        semantic_items=semantic_items,
        keyword_items=keyword_items,
        provenance_items=provenance_lane.items,
        graph_items=graph_items,
        scope_channel=scope.channel,
        scope_chat_id=scope.chat_id,
        top_n=top_k,
    )


async def _record_rerank_shadow(
    self,
    *,
    request: MemoryEngineRetrieveRequest,
    baseline_items: list[dict],
    semantic_items: list[dict],
    keyword_items: list[dict],
    memory_types: list[str] | None,
    scope: MemoryScope,
) -> RerankShadowResult | None:
    experiment_runner = getattr(self, "_experiment_runner", None)
    if experiment_runner is None or not getattr(experiment_runner, "enabled", False):
        return None
    if not bool(getattr(self, "_rerank_shadow_enabled", False)):
        return None
    try:
        shadow = await self._build_rerank_shadow(
            request=request,
            baseline_items=baseline_items,
            semantic_items=semantic_items,
            keyword_items=keyword_items,
            memory_types=memory_types,
            scope=scope,
        )
        if shadow is None:
            return None
        experiment_runner.record_rerank_shadow(
            session_key=scope.session_key,
            turn_id=f"{scope.session_key}@retrieve",
            baseline_result=shadow.baseline_result,
            experimental_result=shadow.experimental_result,
            metrics=shadow.metrics,
        )
        return shadow
    except Exception:
        logger.debug("rerank shadow trace failed", exc_info=True)
        return None
```

- [ ] **Step 5: 在 `retrieve()` 中接入，但不改变真实结果**

In `DefaultMemoryEngine.retrieve()`, after `_record_graph_retrieval_shadow(...)` and before `build_injection_block(items)`, add:

```python
rerank_shadow = await self._record_rerank_shadow(
    request=request,
    baseline_items=items,
    semantic_items=semantic_items,
    keyword_items=keyword_items,
    memory_types=memory_types,
    scope=scope,
)
```

Keep this variable for Task 5 injection governance. Do not replace `items`.

- [ ] **Step 6: 跑 engine rerank test**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_engine_contract.py::test_default_memory_engine_records_rerank_shadow_without_changing_hits -q
```

Expected: PASS.

- [ ] **Step 7: 跑 Phase 3a focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_rerank_experiments.py tests/test_memory_engine_contract.py::test_default_memory_engine_records_rerank_shadow_without_changing_hits -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 3**

Run:

```bash
git add plugins/default_memory/engine.py tests/test_memory_engine_contract.py
git commit -m "feat: wire memory rerank shadow trace"
```

---

### Task 4: 实现 Phase 3b 注入治理 shadow

**Files:**
- Create: `memory2/injection_governance_experiments.py`
- Create: `tests/test_memory_injection_governance_experiments.py`

**Interfaces:**
- Consumes: baseline items and baseline injected ids from real retriever.
- Consumes: Phase 3a ranked items when available.
- Produces: `InjectionGovernanceShadowResult`
- Produces: `build_injection_governance_shadow_result(...) -> InjectionGovernanceShadowResult`

- [ ] **Step 1: 写 injection governance failing tests**

Create `tests/test_memory_injection_governance_experiments.py`:

```python
from __future__ import annotations

from memory2.injection_governance_experiments import (
    build_injection_governance_shadow_result,
)


def test_injection_governance_prefers_rules_and_drops_weak_history() -> None:
    result = build_injection_governance_shadow_result(
        baseline_items=[
            {
                "id": "e1",
                "memory_type": "event",
                "summary": "用户很久之前随口提到一个临时安排",
                "score": 0.51,
            },
            {
                "id": "p1",
                "memory_type": "procedure",
                "summary": "回答架构问题时先给技术版再给易懂版",
                "score": 0.8,
                "source_ref": "cli:local:1",
                "extra_json": {"tool_requirement": "none"},
            },
        ],
        baseline_injected_ids=["e1", "p1"],
        baseline_text_block="old block",
        candidate_items=[
            {
                "id": "p1",
                "memory_type": "procedure",
                "summary": "回答架构问题时先给技术版再给易懂版",
                "experimental_score": 1.2,
                "score": 0.8,
                "source_ref": "cli:local:1",
            },
            {
                "id": "e1",
                "memory_type": "event",
                "summary": "用户很久之前随口提到一个临时安排",
                "experimental_score": 0.2,
                "score": 0.51,
            },
        ],
        max_chars=400,
        max_items=4,
    )

    assert result.baseline_result["baseline_injected_ids"] == ["e1", "p1"]
    assert result.experimental_result["experimental_injected_ids"] == ["p1"]
    assert result.experimental_result["drop_reasons"]["e1"] in {
        "low_confidence",
        "weak_relevance",
    }
    assert result.experimental_result["inject_reasons"]["p1"] == "high_value_rule"
    assert result.metrics["low_confidence_injected_count"] == 1


def test_injection_governance_enforces_character_budget() -> None:
    result = build_injection_governance_shadow_result(
        baseline_items=[],
        baseline_injected_ids=[],
        baseline_text_block="",
        candidate_items=[
            {
                "id": "long",
                "memory_type": "preference",
                "summary": "x" * 1000,
                "experimental_score": 1.0,
                "score": 0.9,
                "source_ref": "cli:local:1",
            },
            {
                "id": "short",
                "memory_type": "preference",
                "summary": "用户希望中文回答",
                "experimental_score": 0.9,
                "score": 0.8,
                "source_ref": "cli:local:2",
            },
        ],
        max_chars=120,
        max_items=4,
    )

    assert result.experimental_result["experimental_injected_ids"] == ["short"]
    assert result.experimental_result["drop_reasons"]["long"] == "over_budget"
    assert result.metrics["experimental_injected_count"] == 1
```

- [ ] **Step 2: 跑 RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_injection_governance_experiments.py -q
```

Expected: FAIL because module does not exist.

- [ ] **Step 3: 创建 `memory2/injection_governance_experiments.py`**

Implement the public shape:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InjectionGovernanceShadowResult:
    baseline_result: dict[str, Any]
    experimental_result: dict[str, Any]
    metrics: dict[str, Any]


def build_injection_governance_shadow_result(
    *,
    baseline_items: list[dict[str, object]],
    baseline_injected_ids: list[str],
    baseline_text_block: str,
    candidate_items: list[dict[str, object]],
    max_chars: int,
    max_items: int,
) -> InjectionGovernanceShadowResult:
    safe_max_chars = max(60, int(max_chars))
    safe_max_items = max(1, int(max_items))
    baseline_ids = _ids(baseline_items)
    baseline_injected = [str(item_id) for item_id in baseline_injected_ids if str(item_id).strip()]
    ordered_candidates = sorted(
        [dict(item) for item in candidate_items if _hit_id(item)],
        key=lambda item: (
            float(item.get("experimental_score") or item.get("score") or 0.0),
            _type_priority(str(item.get("memory_type") or "")),
            _hit_id(item),
        ),
        reverse=True,
    )
    experimental_ids: list[str] = []
    inject_reasons: dict[str, str] = {}
    drop_reasons: dict[str, str] = {}
    used_chars = 0
    seen_summaries: set[str] = set()
    for item in ordered_candidates:
        item_id = _hit_id(item)
        summary = str(item.get("summary") or "").strip()
        reason = _drop_reason(item, seen_summaries=seen_summaries)
        if reason:
            drop_reasons[item_id] = reason
            continue
        line_chars = len(summary) + len(item_id) + 8
        if used_chars + line_chars > safe_max_chars:
            drop_reasons[item_id] = "over_budget"
            continue
        if len(experimental_ids) >= safe_max_items:
            drop_reasons[item_id] = "max_items"
            continue
        experimental_ids.append(item_id)
        used_chars += line_chars
        seen_summaries.add(summary)
        inject_reasons[item_id] = _inject_reason(item)

    prompt_delta = used_chars - len(str(baseline_text_block or ""))
    low_confidence_injected_count = sum(
        1
        for item in baseline_items
        if _hit_id(item) in set(baseline_injected)
        and float(item.get("score") or 0.0) < 0.6
    )
    return InjectionGovernanceShadowResult(
        baseline_result={
            "baseline_ids": baseline_ids,
            "baseline_injected_ids": baseline_injected,
            "baseline_injected_count": len(baseline_injected),
            "baseline_text_chars": len(str(baseline_text_block or "")),
        },
        experimental_result={
            "experimental_injected_ids": experimental_ids,
            "experimental_injected_count": len(experimental_ids),
            "drop_reasons": drop_reasons,
            "inject_reasons": inject_reasons,
            "experimental_text_chars": used_chars,
        },
        metrics={
            "baseline_injected_count": len(baseline_injected),
            "experimental_injected_count": len(experimental_ids),
            "prompt_token_delta": prompt_delta,
            "low_confidence_injected_count": low_confidence_injected_count,
            "dropped_count": len(drop_reasons),
            "newly_injected_count": len(set(experimental_ids) - set(baseline_injected)),
            "removed_from_injection_count": len(set(baseline_injected) - set(experimental_ids)),
        },
    )
```

Also implement:

```python
def _drop_reason(item: dict[str, object], *, seen_summaries: set[str]) -> str:
    summary = str(item.get("summary") or "").strip()
    score = float(item.get("score") or item.get("experimental_score") or 0.0)
    experimental_score = float(item.get("experimental_score") or score)
    if not summary:
        return "empty_summary"
    if summary in seen_summaries:
        return "duplicate"
    if len(summary) > 600:
        return "over_budget"
    if score < 0.55:
        return "low_confidence"
    if experimental_score < 0.35:
        return "weak_relevance"
    return ""


def _inject_reason(item: dict[str, object]) -> str:
    memory_type = str(item.get("memory_type") or "")
    if memory_type == "procedure":
        return "high_value_rule"
    if memory_type == "preference":
        return "stable_preference"
    if str(item.get("source_ref") or "").strip():
        return "sourced_context"
    return "ranked_context"
```

The module must include `_hit_id()`, `_ids()`, and `_type_priority()`.

- [ ] **Step 4: 跑 injection governance tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_injection_governance_experiments.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

Run:

```bash
git add memory2/injection_governance_experiments.py tests/test_memory_injection_governance_experiments.py
git commit -m "feat: add memory injection governance shadow"
```

---

### Task 5: 把 Phase 3b 接入 DefaultMemoryEngine

**Files:**
- Modify: `plugins/default_memory/engine.py`
- Modify: `tests/test_memory_engine_contract.py`

**Interfaces:**
- Consumes: `build_injection_governance_shadow_result(...)`
- Consumes: optional `RerankShadowResult`
- Produces: `DefaultMemoryEngine._record_injection_governance_shadow(...)`

- [ ] **Step 1: 写 engine failing test**

Append to `tests/test_memory_engine_contract.py`:

```python
@pytest.mark.asyncio
async def test_default_memory_engine_records_injection_governance_without_changing_prompt() -> None:
    records: list[dict[str, object]] = []

    class _Runner:
        enabled = True

        def record_tri_retrieval_shadow(self, **kwargs: object) -> object:
            return object()

        def record_graph_retrieval_shadow(self, **kwargs: object) -> object:
            return object()

        def record_rerank_shadow(self, **kwargs: object) -> object:
            return object()

        def record_injection_governance_shadow(self, **kwargs: object) -> object:
            records.append(kwargs)
            return object()

    retriever = SimpleNamespace(
        retrieve_with_lanes=AsyncMock(
            return_value=(
                [
                    {
                        "id": "e1",
                        "memory_type": "event",
                        "summary": "低置信历史",
                        "score": 0.51,
                    },
                    {
                        "id": "p1",
                        "memory_type": "procedure",
                        "summary": "回答先给技术版再给易懂版",
                        "score": 0.85,
                        "source_ref": "cli:local:1",
                    },
                ],
                [],
                [],
            )
        ),
        build_injection_block=MagicMock(return_value=("baseline block", ["e1", "p1"])),
    )
    engine = _make_default_engine(retriever=cast(Any, retriever))
    engine._experiment_runner = _Runner()
    engine._v2_store = SimpleNamespace(
        list_items_for_dashboard=MagicMock(return_value=([], 0))
    )
    engine._rerank_shadow_enabled = False
    engine._injection_governance_shadow_enabled = True

    result = await engine.retrieve(
        MemoryEngineRetrieveRequest(
            query="回答要求",
            scope=MemoryScope(session_key="cli:local", channel="cli", chat_id="local"),
            top_k=2,
        )
    )

    assert result.text_block == "baseline block"
    assert [hit.id for hit in result.hits] == ["e1", "p1"]
    assert records
    assert records[0]["baseline_result"]["baseline_injected_ids"] == ["e1", "p1"]
    assert "experimental_injected_ids" in records[0]["experimental_result"]
```

- [ ] **Step 2: 跑 RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_engine_contract.py::test_default_memory_engine_records_injection_governance_without_changing_prompt -q
```

Expected: FAIL because engine does not yet record injection governance.

- [ ] **Step 3: 实现 `_record_injection_governance_shadow()`**

In `plugins/default_memory/engine.py`, import:

```python
from memory2.injection_governance_experiments import (
    build_injection_governance_shadow_result,
)
```

Add method:

```python
def _record_injection_governance_shadow(
    self,
    *,
    scope: MemoryScope,
    baseline_items: list[dict],
    baseline_text_block: str,
    baseline_injected_ids: list[str],
    rerank_shadow: RerankShadowResult | None,
) -> None:
    experiment_runner = getattr(self, "_experiment_runner", None)
    if experiment_runner is None or not getattr(experiment_runner, "enabled", False):
        return
    if not bool(getattr(self, "_injection_governance_shadow_enabled", False)):
        return
    try:
        candidate_items = baseline_items
        if rerank_shadow is not None:
            ranked = rerank_shadow.experimental_result.get("ranked_items")
            if isinstance(ranked, list):
                candidate_items = [item for item in ranked if isinstance(item, dict)]
        shadow = build_injection_governance_shadow_result(
            baseline_items=baseline_items,
            baseline_injected_ids=baseline_injected_ids,
            baseline_text_block=baseline_text_block,
            candidate_items=candidate_items,
            max_chars=getattr(self._retriever, "_inject_max_chars", 1200),
            max_items=getattr(self._retriever, "_inject_max_procedure_preference", 4)
            + getattr(self._retriever, "_inject_max_event_profile", 2)
            + getattr(self._retriever, "_inject_max_forced", 3),
        )
        experiment_runner.record_injection_governance_shadow(
            session_key=scope.session_key,
            turn_id=f"{scope.session_key}@retrieve",
            baseline_result=shadow.baseline_result,
            experimental_result=shadow.experimental_result,
            metrics=shadow.metrics,
        )
    except Exception:
        logger.debug("injection governance shadow trace failed", exc_info=True)
```

- [ ] **Step 4: 在 `retrieve()` 中接入，但不改变真实 prompt**

After:

```python
text_block, injected_ids = self._retriever.build_injection_block(items)
```

add:

```python
self._record_injection_governance_shadow(
    scope=scope,
    baseline_items=items,
    baseline_text_block=text_block,
    baseline_injected_ids=injected_ids,
    rerank_shadow=rerank_shadow,
)
```

Keep the subsequent hit building unchanged.

- [ ] **Step 5: 跑 engine injection governance test**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_engine_contract.py::test_default_memory_engine_records_injection_governance_without_changing_prompt -q
```

Expected: PASS.

- [ ] **Step 6: 跑 Phase 3b focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_memory_injection_governance_experiments.py tests/test_memory_engine_contract.py::test_default_memory_engine_records_injection_governance_without_changing_prompt -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 5**

Run:

```bash
git add plugins/default_memory/engine.py tests/test_memory_engine_contract.py
git commit -m "feat: wire memory injection governance shadow"
```

---

### Task 6: 更新 memory 优化文档和测试结论

**Files:**
- Modify: `my_md/memory_optimization/01-memory-optimization-roadmap.md`
- Modify: `my_md/memory_optimization/02-memory-quality-metrics.md`
- Modify: `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`
- Modify: `my_md/memory_optimization/README.md`

**Interfaces:**
- Produces: 面向面试和项目切换 session 的 Phase 3a/3b 说明。
- Produces: Phase 3 trace 字段说明。
- Produces: 当前测试结论说明。

- [ ] **Step 1: 更新 roadmap**

Add a section to `my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md`:

```markdown
## Phase 3a：质量重排 shadow

Phase 3a 不改变真实召回结果，只把 baseline hits、语义召回、关键词召回、溯源召回和图谱召回候选合成一个实验候选池，然后根据作用域匹配、记忆类型、来源可信度、溯源信号、图谱信号、低置信惩罚和长度惩罚重新排序。

输出 trace：`rerank_shadow`。

关键字段：

- `baseline_ids`：当前真实召回顺序。
- `reranked_ids`：实验重排顺序。
- `ranked_items`：包含 `raw_rank`、`experimental_rank`、`rank_delta`、`experimental_score` 和 `score_breakdown`。
- `rerank_changed_count`：名次变化数量。
- `baseline_experimental_overlap_rate`：baseline 和实验结果重合率。

测试结论：Phase 3a 可以输出候选质量重排数据，但真实 `retrieve()` 返回值、真实 prompt 注入和用户回复不变。

## Phase 3b：注入治理 shadow

Phase 3b 不改变真实 prompt，只模拟“如果采用治理策略，哪些记忆应该注入，哪些应该丢弃”。治理信号包括记忆类型优先级、实验重排分、置信度、来源、重复内容、字符预算和最大条数。

输出 trace：`injection_governance_shadow`。

关键字段：

- `baseline_injected_ids`：当前真实注入的记忆。
- `experimental_injected_ids`：实验治理后建议注入的记忆。
- `drop_reasons`：实验策略丢弃原因。
- `inject_reasons`：实验策略注入原因。
- `prompt_token_delta`：实验注入相对 baseline 的字符变化近似值。
- `low_confidence_injected_count`：baseline 中低置信仍被注入的数量。

测试结论：Phase 3b 可以输出注入治理对比数据，但真实 `text_block` 不变。
```

- [ ] **Step 2: 更新 metrics 文档**

Add Phase 3 metrics to `my_md/memory_optimization/02-memory-quality-metrics.md`:

```markdown
## Phase 3 可输出指标

### 质量重排

- `rerank_changed_count`
- `baseline_experimental_overlap_rate`
- `avg_experimental_score`
- `scope_match_count`
- `source_ref_count`
- `rank_delta`
- `score_breakdown`

### 注入治理

- `baseline_injected_count`
- `experimental_injected_count`
- `prompt_token_delta`
- `low_confidence_injected_count`
- `dropped_count`
- `newly_injected_count`
- `removed_from_injection_count`
- `drop_reasons`
- `inject_reasons`
```

- [ ] **Step 3: 更新 README 和总路线图**

In `my_md/memory_optimization/README.md` and `01-memory-optimization-roadmap.md`, add a short status line:

```markdown
- Phase 3a/3b：计划进入质量重排 shadow 和注入治理 shadow。目标是先得到 off/on 对比数据，不改变真实 AgentLoop、真实召回和真实 prompt。
```

After implementation, change the line to:

```markdown
- Phase 3a/3b 已完成：新增质量重排 shadow 和注入治理 shadow，测试确认真实 hits、真实注入块和 `raw["items"]` 不变。
```

- [ ] **Step 4: Commit docs**

Run:

```bash
git add my_md/memory_optimization/01-memory-optimization-roadmap.md my_md/memory_optimization/02-memory-quality-metrics.md my_md/memory_optimization/04-memory-plugin-experiment-roadmap.md my_md/memory_optimization/README.md
git commit -m "docs: update memory phase3 experiment plan"
```

---

### Task 7: 全量验证和提交前检查

**Files:**
- No direct file edits unless checks expose a defect.

**Interfaces:**
- Produces: verification evidence for the whole Phase 3 change.

- [ ] **Step 1: 跑 focused memory tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_memory_experiments_config.py \
  tests/test_memory_experiments_runner.py \
  tests/test_memory_rerank_experiments.py \
  tests/test_memory_injection_governance_experiments.py \
  tests/test_memory_engine_contract.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: 跑 broader memory suite**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_memory_*.py \
  tests/test_post_response_memory_experiments.py \
  -q
```

Expected: PASS.

- [ ] **Step 3: 跑 compile check**

Run:

```bash
.venv/bin/python -m compileall plugins/default_memory memory2 tests -q
```

Expected: no output and exit code 0.

- [ ] **Step 4: 跑 whitespace check**

Run:

```bash
git diff --check
```

Expected: no output and exit code 0.

- [ ] **Step 5: 检查 git 状态**

Run:

```bash
git status --short
```

Expected: only intended files are modified; do not stage unrelated `uv.lock` mirror drift.

- [ ] **Step 6: Final commit if needed**

If Task 7 required fixes, commit them:

```bash
git add <intended-files-only>
git commit -m "fix: stabilize memory phase3 shadow tests"
```

---

## Self-Review

**Spec coverage:** This plan covers Phase 3a rerank shadow, Phase 3b injection governance shadow, config flags, trace writer methods, engine wiring, tests, docs, and final verification. It explicitly keeps real retrieval, real injection, AgentLoop, ToolExecutor, and database schema unchanged.

**Placeholder scan:** The plan contains no open placeholder requirements. Names, files, commands, feature names, and expected outputs are concrete.

**Type consistency:** `RerankShadowResult` and `InjectionGovernanceShadowResult` follow the existing `baseline_result / experimental_result / metrics` pattern. Runner methods match existing `record_tri_retrieval_shadow()` and `record_graph_retrieval_shadow()` style. Engine wiring passes `rerank_shadow` into injection governance without replacing baseline `items`.

**Execution boundary:** Phase 3 can be stopped safely after Task 3 with only rerank shadow enabled. Task 4/5 add injection governance shadow and can be reviewed independently. No task switches experimental behavior to active.
