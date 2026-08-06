# MiniRoute 与 Agent Evaluation Harness 集成说明

日期：2026-08-06

## 当前状态

MiniRoute 当前仍在训练和评测调试阶段。本文件只记录未来集成约束，不推动当前 AgentLoop、ToolExecutor 或生产治理代码修改。

## 当前真实输出 schema

MiniRoute 的 `RouteLabel` 当前只有以下五个字段：

```json
{
  "intent": "memory_query",
  "need_memory": true,
  "need_tools": false,
  "tool_scope": ["memory_tools"],
  "risk_level": "read_only"
}
```

- `tool_scope` 是 `list[str]`。
- `json_valid` 不属于模型输出。
- `json_valid` 不属于 `RouteLabel`。
- JSON/schema 合法性由 `ParsedTrainingRecord.ok/errors` 和评测报告中的 `invalid_json_count` 表示。

## Harness 中的保存方式

合法输出：

```python
router_decision = {
    "intent": "...",
    "need_memory": True,
    "need_tools": False,
    "tool_scope": ["memory_tools"],
    "risk_level": "read_only",
}
router_parse_ok = True
router_parse_errors = ()
```

非法输出：

```python
router_decision = None
router_parse_ok = False
router_parse_errors = ("invalid output json: ...",)
```

解析状态属于 Harness envelope，不得写回 MiniRoute 模型输出。

## 未来集成方向

```text
用户请求
 -> MiniRoute Shadow
 -> router_decision
 -> TaskSpec
 -> AgentLoop / Reasoner
 -> Tool Governance
 -> Tool Execution
 -> Outcome / Security / Cost Graders
```

未来需要验证：

- JSON 解析成功率。
- intent accuracy。
- need_memory accuracy。
- need_tools accuracy。
- tool_scope accuracy。
- risk_level accuracy。
- high-risk recall。
- risk underestimate。
- scope overopen。

## 当前不做

- 不修改 MiniRoute schema。
- 不修改 MiniRoute 推理代码。
- 不将 MiniRoute 当前输出作为生产授权。
- 不把 MiniRoute 当前调试数据纳入 Agent Harness 主 gate。
- 不根据当前 MiniRoute 文档直接修改生产工具治理策略。

## 2026-08-06 Harness v2 适配检查点

本轮只新增 Harness 侧 adapter：

- `task_from_miniroute_record()` 调用 `miniroute.v1_schema.parse_training_record()`。
- 解析成功时，`router_decision` 只保存 `RouteLabel.to_dict()` 的五个字段。
- 解析失败时，`router_decision=None`，`router_parse_ok=False`，错误进入 `router_parse_errors`。
- 没有向 MiniRoute schema 添加 `json_valid`。
- 没有修改 MiniRoute Python、测试、训练数据或模型文件。

后续若要把 MiniRoute 纳入 Agent Harness 主 gate，必须先完成真实模型输出采样、invalid JSON 统计、risk underestimate/scope overopen 统计，以及和当前 AgentLoop/Tool Governance 配置的兼容性复核。
