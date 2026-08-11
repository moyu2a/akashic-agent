# MiniRoute 数据集记录

## 任务定义

MiniRoute 是 MnemoAgent 的前置路由小模型。输入用户请求，输出固定 JSON，用于判断：

```json
{
  "intent": "chat",
  "need_memory": false,
  "need_tools": false,
  "tool_scope": ["none"],
  "risk_level": "none"
}
```

输出只作为粗粒度路由建议，不是最终工具授权。高风险工具仍由 MnemoAgent 原有工具治理链路裁决。

## V1 数据集

文件：

- `miniroute/data/route_train.jsonl`: 875 条。
- `miniroute/data/route_valid.jsonl`: 184 条。
- `miniroute/data/route_test.jsonl`: 191 条。

V1 暴露的问题：

- JSON 格式能学会，但路由语义没有学稳。
- 训练集完全匹配约 `29.83%`，验证集完全匹配约 `29.35%`。
- `memory_query` / `profile_update` 使用 `tool_scope=["memory_tools"]`，但同时标注 `need_tools=false`，字段关系不自洽。
- prompt 没有列出合法枚举，模型会生成 schema 外标签，例如 `trace`。
- `chat` hard negative 不够，容易被误判为记忆、保存或工具执行。
- 文件读取、高风险执行、状态查询之间边界不足。

## V2 数据集

文件：

- `miniroute/data/route_v2_train.jsonl`: 1061 条。
- `miniroute/data/route_v2_valid.jsonl`: 227 条。
- `miniroute/data/route_v2_test.jsonl`: 232 条。
- 总计: 1520 条。
- V2 测试集中高风险样本: 35 条。

V2 改动：

- 记忆查询统一为：

```json
{
  "intent": "memory_query",
  "need_memory": true,
  "need_tools": true,
  "tool_scope": ["memory_tools"],
  "risk_level": "read_only"
}
```

- 画像更新统一为：

```json
{
  "intent": "profile_update",
  "need_memory": true,
  "need_tools": true,
  "tool_scope": ["memory_tools"],
  "risk_level": "write"
}
```

- 增加 `unknown_tools`：
  - `none` 表示明确不需要工具。
  - `unknown_tools` 表示需要工具，但无法归入当前定义的工具域。
- 每条样本的 user prompt 中列出合法 `intent`、`tool_scope` 和 `risk_level`。
- 增加 `chat` hard negative，例如包含“保存”“记忆”“工具”“偏好”等词但不需要工具的普通分析请求。
- 增加记忆查询 vs 画像更新、文件读取 vs 高风险执行、状态查询 vs 工具执行的边界样本。
- V2 train/valid/test 使用确定性随机打乱，seed 为 `20260805`。
- V2 不覆盖 V1 文件，使用 `route_v2_*.jsonl` 独立保存。

## V2 数据校验

命令：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m miniroute.tools.validate_dataset \
  --train miniroute/data/route_v2_train.jsonl \
  --valid miniroute/data/route_v2_valid.jsonl \
  --test miniroute/data/route_v2_test.jsonl
```

结果：

```json
{
  "ok": true,
  "total_records": 1520,
  "high_risk_test_count": 35,
  "issues": []
}
```

