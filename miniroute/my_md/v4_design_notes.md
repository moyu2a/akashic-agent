# MiniRoute V4 设计与实验记录

## 背景

V1-V3 路线让小模型一次性输出 `intent`、`need_memory`、`need_tools`、`tool_scope` 和 `risk_level`。V3_2 在 train/valid/test 上稳定到 `78%-82%`，但主要错误仍集中在意图、工具域和风险等级的组合混淆。

因此 V4 不再把小模型设计成工具治理器，而是改成轻量场景识别器。

## V4 职责

MiniRoute V4 只判断当前用户请求的处理场景：

```json
{"scene": "task", "operation": "plan", "request_mode": "single"}
```

V4 输入只包含：

- `has_active_task`
- `user_message`

V4 不输入完整记忆、完整历史、完整工具列表、插件信息、文件内容、检索结果或工具结果。

## 为什么这样设计

目标是优化主 Agent 调用前的 token 和时延，而不是让小模型替代主系统决策。

可优化点：

- `chat` 请求跳过长期记忆召回，减少无效上下文。
- `memory` 请求只进入记忆召回链路，不扩大工具范围。
- `profile` 请求进入画像写入候选，避免误当普通问答。
- `status` 请求走观测摘要，不查询长期记忆。
- `unknown` 请求回退原流程，避免过度自信。

## 当前数据

V4 数据已生成：

```text
route_v4_train.jsonl: 2400
route_v4_valid.jsonl: 300
route_v4_test.jsonl: 300
total: 3000
shuffle_seed: 20260806
```

场景分布：

```text
chat: 450
memory: 360
profile: 300
task: 390
file: 360
status: 300
content: 300
action: 360
unknown: 180
```

边界样本：

```text
v4:chat_vs_profile
v4:memory_vs_profile
v4:memory_vs_status
v4:file_vs_action
v4:task_vs_chat
v4:content_vs_action
v4:unknown_vs_action
```

## 本轮修改

- 新增 `miniroute/v4_schema.py`，定义 V4 三字段协议。
- 新增 `miniroute/tools/generate_v4_dataset.py`，生成 V4 训练、验证和测试集。
- 扩展 `miniroute/tools/validate_dataset.py`，支持 `--schema v4` 校验。
- 扩展 `miniroute/evaluation/evaluate.py`，支持 V4 三字段离线评测。
- 新增 `tests/test_miniroute_v4.py`，覆盖 schema、轻量输入、数据生成、数据校验和 V4 评测统计。

## 当前结论

V4 是后续主线。V3_2 继续冻结为旧五字段 baseline，用于说明旧路线的上限和错误原因；V4 则单独训练、单独评测、单独复盘，不再和 V1-V3 的五字段指标直接混算。

下一步是在 MiniMind 云服务器训练 `route_v4_train.jsonl`，并新增或改造评测脚本，只评测 `scene`、`operation` 和 `request_mode`。
