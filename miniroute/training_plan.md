# MiniRoute 训练计划

## 训练目标

基于 MiniMind 预训练模型进行 SFT 或 LoRA 微调，使模型能够根据用户输入稳定输出 MiniRoute 路由 JSON。

## 不做从零预训练

本项目不从随机参数开始训练模型，也不重新训练 tokenizer。MiniMind 的基础语言能力来自预训练模型，本项目只做 MnemoAgent 场景下的监督微调。

## 推荐训练方式

第一版优先使用 LoRA 微调。

原因：

- 训练成本低。
- 迭代速度快。
- 方便多轮错误分析和重训。
- 不容易破坏基础语言能力。

## 云服务器准备

推荐配置：

- GPU：RTX 4090 24GB、A10、L20 或同等级显卡。
- Python：按 MiniMind 官方要求配置。
- 框架：PyTorch、CUDA、MiniMind 依赖。

安装顺序：

1. 跑通 GPU 和 PyTorch。
2. 拉取 MiniMind 代码。
3. 跑通官方推理 Demo。
4. 跑通官方 SFT 或 LoRA Demo。
5. 替换为 MiniRoute 数据集。

## 训练输入

训练数据：

- `data/route_train.jsonl`
- `data/route_valid.jsonl`

测试数据不参与训练：

- `data/route_test.jsonl`

## 训练输出

需要保存：

- 模型权重或 LoRA adapter。
- tokenizer 和配置文件。
- 训练命令。
- 训练日志。
- 训练集版本号。
- 验证集指标。

建议输出目录：

```text
training/runs/YYYYMMDD-HHMM-miniroute-sft-v1/
```

## 第一轮训练目标

第一轮不追求极限准确率，重点验证：

- 模型能稳定输出 JSON。
- intent 分类基本可用。
- 高风险请求不被判低。
- 工具范围不会明显过度开放。

## 训练后必须做的事

1. 跑固定测试集。
2. 生成 `evaluation/eval_report.md`。
3. 抽样查看错误案例。
4. 将错误案例记录到 `reports/error_analysis.md`。
5. 按错误类型补数据。
6. 再训练下一轮。
