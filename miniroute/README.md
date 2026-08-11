# MiniRoute

MiniRoute 是面向 MnemoAgent 的轻量路由模型项目。项目目标不是让小模型直接回答用户问题，而是基于 MiniMind 预训练模型做 SFT 微调，让小模型在用户消息进入主 Agent 前识别当前请求的处理场景。

V1-V3 曾尝试让小模型一次性预判意图、记忆需求、工具需求、工具范围和风险等级。该路线在 `lora_route_v3_2` 上稳定到 `78%-82%`，但错误主要集中在多字段组合混淆。V4 起，MiniRoute 收窄为轻量场景识别器，优先验证它能否帮助主 Agent 减少无效记忆召回、无效上下文拼接和不必要的大模型治理轮次。

MiniRoute 只负责粗粒度场景建议。它不选择具体工具、不生成工具参数、不拆分任务，也不替代工具注册表、任务规划器和原有工具治理。

## 项目目标

- 构建个人智能体场景下的请求场景数据集。
- 基于 MiniMind 进行 SFT 或 LoRA 微调。
- 让模型稳定输出结构化 JSON 场景结果。
- 建立离线评测指标，重点验证场景、操作和请求模式。
- 以 Shadow 模式接入 MnemoAgent，不影响原主流程。
- 在验证稳定后，仅用于低风险上下文策略辅助。

## V4 当前任务边界

小模型负责：

- 判断当前用户请求场景。
- 判断请求对应的粗粒度操作。
- 判断请求是单一请求还是复合请求。
- 根据 `has_active_task` 辅助区分任务类请求和普通讨论。

小模型输入只包含：

- `has_active_task`
- `user_message`

小模型不负责：

- 生成最终回答。
- 直接执行工具。
- 直接审批高风险操作。
- 直接写入长期记忆。
- 绕过 MnemoAgent 原有工具治理。
- 选择具体工具或安排多个工具的执行顺序。
- 读取完整记忆、完整历史、工具列表、插件信息、文件内容或检索结果。

## 输出示例

```json
{
  "scene": "memory",
  "operation": "query",
  "request_mode": "single"
}
```

## 目录说明

- `PROJECT_STEPS.md`: 项目主要步骤和阶段目标。
- `label_schema.md`: 标签体系和输出字段定义。
- `v4_design.md`: V4 设计目标、输入输出、边界和接入方式。
- `dataset_plan.md`: 数据来源、样本格式和数据划分方案。
- `training_plan.md`: MiniMind 微调训练流程。
- `evaluation_plan.md`: 离线评测指标和通过标准。
- `integration_plan.md`: 接入 MnemoAgent 的 Shadow 方案。
- `data/`: 训练、验证、测试数据放置目录。
- `training/`: 训练配置、命令和训练日志放置目录。
- `evaluation/`: 评测脚本、评测输入和评测输出放置目录。
- `integration/`: MnemoAgent 接入设计、接口样例和 Shadow 日志说明。
- `reports/`: 实验报告、错误分析和阶段总结。
- `my_md/`: MiniMind 训练、评测、问题复盘和下一轮实验决策记录。

## 复盘记录要求

MiniRoute 的训练和评测很容易出现“训练参数、数据版本、评测模板、错误统计混在一起”的问题。后续每次实验都必须在 `my_md/` 下留下可追溯记录，避免只保留最终结论。

每轮实验至少记录：

1. 实验目标：本轮要验证什么问题，例如 V4 三字段是否可拟合、危险场景混淆是否降低、Shadow 是否减少 token。
2. 修改内容：本轮改了哪些代码、数据、prompt、训练参数或评测脚本。
3. 测试数据：使用哪个 train、valid、test 文件，样本数量是多少，是否和上一轮一致。
4. 训练方案：基座权重、LoRA 名称、epoch、batch size、学习率、`max_seq_len`、是否固定 chat template。
5. 评测方案：评测命令、评测集、是否保留 empty think、是否开启 schema 校验。
6. 测试结果：完全匹配率、字段准确率、严格 JSON 比例、可提取 JSON 比例、schema 外输出数量。
7. 错误分析：V4 记录 Top scene/operation/request_mode 混淆；历史五字段实验再记录 intent/tool_scope/risk_level 混淆。
8. 结论和下一步：明确本轮假设是否成立，下一轮继续调参、改数据、改模板、做 Shadow 还是回退。

建议每次新实验都基于 `my_md/EXPERIMENT_RECORD_TEMPLATE.md` 新建记录文件，并同步更新 `my_md/README.md` 的当前结论快照。
