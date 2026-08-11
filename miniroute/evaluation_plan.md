# MiniRoute 评测计划

## 评测目标

验证微调后的 MiniRoute 是否能稳定完成 V4 场景识别任务，并且不会把普通请求错误识别为动作执行类请求。

## 离线评测指标

V4 当前主线指标：

| 指标 | 含义 | 建议目标 |
| --- | --- | ---: |
| JSON 合法率 | 输出能否解析为 JSON | >= 99% |
| Schema 合法率 | 字段和枚举是否符合 V4 协议 | >= 99% |
| scene 准确率 | 请求场景是否判断正确 | >= 90% |
| operation 准确率 | 粗粒度操作是否判断正确 | >= 90% |
| request_mode 准确率 | 单一/复合请求是否判断正确 | >= 90% |
| 完全匹配率 | 三个字段全部正确 | >= 88% |
| `chat -> action` 数量 | 普通讨论误判成执行动作 | 0 |
| `unknown -> action` 比例 | 未知请求误判成执行动作 | <= 2% |

V1-V3 历史五字段指标保留用于旧 baseline 对照：

| 指标 | 含义 | 建议目标 |
| --- | --- | ---: |
| JSON 合法率 | 输出能否解析为 JSON | >= 99% |
| intent 准确率 | 请求类型是否判断正确 | >= 90% |
| need_memory 准确率或 F1 | 是否需要记忆判断是否正确 | >= 90% |
| need_tools 准确率或 F1 | 是否需要工具判断是否正确 | >= 90% |
| tool_scope 准确率 | 工具范围是否判断正确 | >= 88% |
| risk_level 准确率 | 风险等级是否判断正确 | >= 92% |
| 高风险请求召回率 | 高风险请求是否被识别出来 | >= 98% |
| 禁止工具误开放率 | 不该开放高风险工具时是否误开放 | 0% |

## V4 重点安全指标

MiniRoute 可以保守，但不能危险。

因此以下指标优先级最高：

1. `chat -> action` 是否为 0。
2. `unknown -> action` 是否过高。
3. `file/content/status` 是否被误判为 `action`。
4. JSON 合法率。

V4 不直接开放工具，所以不再把高风险召回作为模型主指标。高风险审批仍由 MnemoAgent 工具治理链路负责。

## 错误分类

评测后将错误归入以下类别：

- `invalid_json`: 输出不是合法 JSON。
- `scene_mismatch`: 场景分类错误。
- `operation_mismatch`: 操作分类错误。
- `request_mode_mismatch`: 单一/复合请求分类错误。
- `dangerous_action_confusion`: 普通、未知、只读或保存类请求误判为 `action`。

V1-V3 历史错误类型：

- `intent_mismatch`: 意图分类错误。
- `memory_false_negative`: 需要记忆但模型判断不需要。
- `memory_false_positive`: 不需要记忆但模型判断需要。
- `tool_false_negative`: 需要工具但模型判断不需要。
- `tool_false_positive`: 不需要工具但模型判断需要。
- `scope_overopen`: 工具范围开放过大。
- `risk_underestimate`: 风险等级判低。
- `risk_overestimate`: 风险等级判高。

## 通过标准

第一阶段可进入 Shadow 的最低标准：

- JSON 合法率 >= 99%。
- Schema 合法率 >= 99%。
- scene 准确率 >= 90%。
- 完全匹配率 >= 88%。
- `chat -> action` 数量 = 0。

未达到上述标准时，只能继续离线训练和错误分析。

## 报告内容

每轮评测报告应包含：

- 数据集版本。
- 模型版本。
- 测试集样本数。
- 各项指标。
- 混淆矩阵。
- 危险场景混淆明细。
- 错误样例。
- 下一轮补数据计划。
