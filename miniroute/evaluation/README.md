# Evaluation Directory

MiniRoute 离线评测脚本、输入和输出放在本目录。

建议文件：

- `eval_report.md`: 最新评测报告。
- `confusion_matrix.md`: 混淆矩阵。
- `dangerous_confusions.md`: V4 危险场景混淆明细，例如 `chat -> action`。

## V4 评测重点

V4 只评测三字段：

```text
scene
operation
request_mode
```

本仓库的 `miniroute.evaluation.evaluate.evaluate_v4_predictions()` 用于离线统计已经解析后的标签。MiniMind 云端模型推理仍需要单独的 `eval_route_v4.py`，不能直接复用旧五字段 `eval_route.py`。

重点指标：

- JSON 合法率。
- Schema 合法率。
- scene 准确率。
- operation 准确率。
- request_mode 准确率。
- 完全匹配率。
- `chat -> action`、`unknown -> action` 等危险混淆。
