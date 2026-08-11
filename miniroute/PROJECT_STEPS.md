# MiniRoute 项目主要步骤

本文记录 MiniRoute 从项目设计、数据构建、SFT 微调、评测到 MnemoAgent 接入的主要步骤。

## 阶段 1：确定任务边界

目标：把 MiniRoute 固定为轻量场景识别模型，不做最终回答模型，也不做工具审批模型。

需要完成：

1. 明确小模型输入：当前用户消息，必要时可附带少量会话元信息。
2. 明确小模型输出：固定 JSON，不输出解释文本。
3. 明确小模型职责：V4 只判断 `scene`、`operation` 和 `request_mode`。
4. 明确安全边界：小模型只做建议，不能绕过原工具治理和审批机制。

阶段产物：

- `README.md`
- `label_schema.md`

## 阶段 2：设计标签体系

目标：把开放式用户请求转成可监督训练的场景分类任务。

需要完成：

1. 设计 `scene` 标签。
2. 设计 `operation` 标签。
3. 设计 `request_mode` 标签。
4. 补充典型样例和混淆样例。
5. 保留 V1-V3 五字段协议作为历史 baseline，不作为 V4 主线。

阶段产物：

- `label_schema.md`

## 阶段 3：构建数据集

目标：准备 MiniMind SFT 可用的数据。

数据来源：

1. MnemoAgent 现有工具治理测试用例。
2. MnemoAgent 真实对话日志，需脱敏。
3. 人工模板扩写。
4. 高风险和混淆样本专项补充。

推荐规模：

- 训练集：2000 到 3000 条。
- 验证集：200 到 300 条。
- 测试集：200 到 300 条。

阶段产物：

- `data/route_v4_train.jsonl`
- `data/route_v4_valid.jsonl`
- `data/route_v4_test.jsonl`
- `dataset_plan.md`

## 阶段 4：云服务器安装 MiniMind

目标：在云服务器跑通 MiniMind 官方推理和训练流程。

需要完成：

1. 准备 GPU 云服务器。
2. 安装 CUDA、Python、PyTorch 和 MiniMind 依赖。
3. 跑通 MiniMind 官方推理 Demo。
4. 跑通 MiniMind 官方 SFT 或 LoRA Demo。
5. 将 MiniRoute 数据转换为 MiniMind 训练格式。

阶段产物：

- `training/environment.md`
- `training/minimind_setup.md`

## 阶段 5：SFT 或 LoRA 微调

目标：让小模型学会根据用户输入输出固定 JSON 场景结果。

建议优先使用 LoRA 微调，先不要全量微调。

需要完成：

1. 选择 MiniMind 预训练模型。
2. 设置训练数据路径。
3. 设置输出目录。
4. 运行第一轮 SFT 或 LoRA 微调。
5. 保存模型权重、训练日志和训练命令。

阶段产物：

- `training_plan.md`
- `training/train_commands.md`
- `training/run_log.md`

## 阶段 6：离线评测

目标：在固定测试集上验证模型是否可用。

核心指标：

- JSON 合法率。
- scene 准确率。
- operation 准确率。
- request_mode 准确率。
- 完全匹配率。
- `chat -> action` 危险混淆数量。
- `unknown -> action` 危险混淆比例。

建议通过标准：

- JSON 合法率不低于 99%。
- scene 准确率不低于 90%。
- 完全匹配率不低于 88%。
- `chat -> action` 危险混淆等于 0。

阶段产物：

- `evaluation_plan.md`
- `evaluation/eval_report.md`
- `reports/error_analysis.md`

## 阶段 7：错误分析和补数据

目标：针对模型错误补充训练样本，并进行多轮迭代。

重点错误类型：

1. `chat` 和 `profile` 混淆。
2. `memory` 和 `status` 混淆。
3. `file` 和 `action` 混淆。
4. `content` 和 `action` 混淆。
5. `task` 和 `chat` 混淆。
6. 输出 JSON 不合法。

阶段产物：

- `reports/error_analysis.md`
- 新增或修订后的训练数据。

## 阶段 8：部署推理服务

目标：把微调后的模型包装成可被 MnemoAgent 调用的服务。

建议接口：

```text
POST /route
```

请求：

```json
{
  "message": "你还记得我上次说的回答偏好吗？",
  "has_active_task": false
}
```

响应：

```json
{
  "scene": "memory",
  "operation": "query",
  "request_mode": "single"
}
```

阶段产物：

- `integration/api_contract.md`
- `integration_plan.md`

## 阶段 9：Shadow 接入 MnemoAgent

目标：先让 MiniRoute 只做旁路预测，不影响真实对话流程。

每轮记录：

- 用户输入。
- MiniRoute V4 场景识别结果。
- MnemoAgent 原流程使用的上下文策略。
- 是否发生长期记忆召回。
- 最终真实工具调用。
- prompt tokens 和耗时。

阶段产物：

- `integration/shadow_log_schema.md`
- `reports/shadow_eval_report.md`

## 阶段 10：低风险启用

目标：Shadow 稳定后，只让 MiniRoute 辅助低风险决策。

可优先启用：

- 是否跳过长期记忆检索。
- 是否进入工作模式。
- 是否使用任务状态摘要。
- 是否使用短上下文或完整上下文。

继续禁止小模型直接控制：

- shell 工具。
- 写文件工具。
- 删除或覆盖操作。
- 审批结果。
- 外部副作用工具。

阶段产物：

- `integration/rollout_plan.md`
- `reports/final_report.md`
