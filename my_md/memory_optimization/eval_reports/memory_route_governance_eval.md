# 记忆三路召回路由治理报告

本报告只展示路由和候选治理证据。离线表来自确定性 trace，真实引擎表来自 `DefaultMemoryEngine.retrieve()` 的 route smoke。

## 三路召回路由表

| scene | cases | baseline_success | gated_success | graph_success | candidate_drop_rate | expected_route_hit_rate | candidate_accept_rate | graph_used_rate | note |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| fuzzy_reference | 16 | 30 | 32 | 30 | 68.27% | 100.0% | 31.73% | 0.0% | 模糊指代需要语义扩展，允许少量图谱邻接候选补全上下文。 |
| partial_conflict | 24 | 48 | 48 | 48 | 63.3933% | 100.0% | 36.6067% | 0.0% | 冲突判断优先保留同作用域、可追溯的来源证据。 |
| source_lookup | 16 | 32 | 32 | 32 | 77.085% | 100.0% | 22.915% | 0.0% | 来源查询必须可追溯，先返回同作用域的 provenance 证据。 |
| tool_preference | 16 | 30 | 32 | 30 | 76.73% | 100.0% | 23.27% | 0.0% | 工具偏好以规则语义和字面工具名为主，避免引入图谱或来源噪声。 |
| unknown | 248 | 488 | 496 | 488 | 73.7155% | 100.0% | 26.2845% | 0.0% | 未识别场景采用保守的语义和关键词双 lane。 |

## 真实引擎 route smoke

| scene | case_count | candidate_accept_rate | candidate_drop_rate | graph_used_rate | note |
| --- | ---: | ---: | ---: | ---: | --- |
| fuzzy_reference | 2 | 25.0% | 75.0% | 100.0% | ok hits=1; ok hits=2 |
| unknown | 7 | 34.2843% | 51.43% | 0.0% | ok hits=0; ok hits=1; ok hits=2 |
