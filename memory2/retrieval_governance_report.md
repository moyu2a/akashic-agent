# Task 1 召回治理报告

## 改动文件

- `memory2/retrieval_governance.py`：新增纯函数场景识别、`RetrievalRoutingDecision`、lane 门控、lane cap、去重与 JSON 可序列化 route trace。
- `tests/test_memory_retrieval_governance.py`：覆盖 fuzzy_reference、tool_preference、partial_conflict、graph 门控、lane cap、provenance 优先、去重和 trace 序列化。

## 验证

执行：

```bash
./.worktrees/memory-experiments-phase0/.venv/bin/python -m pytest -q tests/test_memory_retrieval_governance.py
```

结果：`7 passed`。

## 疑点

仓库当前未包含任务说明提及的 `retrieval_experiments.py`、`retrieval_graph_experiments.py`、`rerank_experiments.py`；实现参考了现有 `memory2/retriever.py` 的 lane/RRF 语义。治理层尚未接入 AgentLoop、Reasoner、ToolExecutor 或真实写入路径，符合本任务范围。
