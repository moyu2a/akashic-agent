# MiniRoute

MiniRoute 是面向 MnemoAgent 的轻量意图路由模型项目。项目目标不是让小模型直接回答用户问题，而是基于 MiniMind 预训练模型做 SFT 微调，让小模型在用户消息进入主 Agent 前，预判用户意图、记忆需求、工具需求、工具范围和风险等级。

第一阶段只做旁路预测，不控制真实工具执行。小模型输出结果用于和 MnemoAgent 现有工具治理链路做 Shadow 对照，验证其是否能辅助减少无效记忆召回、无效工具开放和高风险工具误开放。

## 项目目标

- 构建个人智能体场景下的意图路由数据集。
- 基于 MiniMind 进行 SFT 或 LoRA 微调。
- 让模型稳定输出结构化 JSON 路由结果。
- 建立离线评测指标，重点验证高风险召回和禁止工具误开放。
- 以 Shadow 模式接入 MnemoAgent，不影响原主流程。
- 在验证稳定后，仅用于低风险路由辅助。

## 第一阶段任务边界

小模型负责：

- 判断用户请求类型。
- 判断是否需要长期记忆。
- 判断是否需要工具。
- 判断建议开放的工具范围。
- 判断风险等级。

小模型不负责：

- 生成最终回答。
- 直接执行工具。
- 直接审批高风险操作。
- 直接写入长期记忆。
- 绕过 MnemoAgent 原有工具治理。

## 输出示例

```json
{
  "intent": "memory_query",
  "need_memory": true,
  "need_tools": false,
  "tool_scope": ["memory_tools"],
  "risk_level": "read_only"
}
```

## 目录说明

- `PROJECT_STEPS.md`: 项目主要步骤和阶段目标。
- `label_schema.md`: 标签体系和输出字段定义。
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
- `my_md/agent_harness_eval_integration_plan.md`: MiniRoute 与未来 Agent Evaluation Harness 的集成约束；当前只记录设计，不参与生产修改。

## 复盘记录要求

MiniRoute 的训练和评测很容易出现“训练参数、数据版本、评测模板、错误统计混在一起”的问题。后续每次实验都必须在 `my_md/` 下留下可追溯记录，避免只保留最终结论。

每轮实验至少记录：

1. 实验目标：本轮要验证什么问题，例如模板是否一致、V3 数据是否改善边界、是否需要移除 `tool_scope`。
2. 修改内容：本轮改了哪些代码、数据、prompt、训练参数或评测脚本。
3. 测试数据：使用哪个 train、valid、test 文件，样本数量是多少，是否和上一轮一致。
4. 训练方案：基座权重、LoRA 名称、epoch、batch size、学习率、`max_seq_len`、是否固定 chat template。
5. 评测方案：评测命令、评测集、是否保留 empty think、是否开启 schema 校验。
6. 测试结果：完全匹配率、字段准确率、严格 JSON 比例、可提取 JSON 比例、schema 外输出数量。
7. 错误分析：Top intent、tool_scope、risk_level 混淆，以及典型错误样本。
8. 结论和下一步：明确本轮假设是否成立，下一轮继续调参、改数据、改模板还是简化输出空间。

建议每次新实验都基于 `my_md/EXPERIMENT_RECORD_TEMPLATE.md` 新建记录文件，并同步更新 `my_md/README.md` 的当前结论快照。
