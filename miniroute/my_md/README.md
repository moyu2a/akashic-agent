# MiniRoute 复盘文档

这个目录用于记录 MiniRoute 小模型的训练数据、MiniMind LoRA 训练结果、错误模式、问题清单和后续实验方案。

## 文档索引

- [route_dataset_notes.md](route_dataset_notes.md): 数据集版本、样本规模、标签口径和 V2 数据改动。
- [route_eval_v2.md](route_eval_v2.md): `full_sft + lora_route_v2` 的本轮评测方法、指标和错误模式。
- [route_issue_log.md](route_issue_log.md): 持续维护的问题清单，每次发现新问题都追加到这里。
- [route_experiment_plan.md](route_experiment_plan.md): 后续实验计划、判断标准和推荐执行顺序。
- [minimind_training_handoff.md](minimind_training_handoff.md): 给 MiniMind 云服务器训练侧使用的交接说明和命令。
- [EXPERIMENT_RECORD_TEMPLATE.md](EXPERIMENT_RECORD_TEMPLATE.md): 单次训练/评测实验记录模板，后续每轮实验都按该模板复制填写。
- [route_eval_template_fixed_baseline.md](route_eval_template_fixed_baseline.md): 模板固定版训练结果基线，用于和 V3 对比。
- [route_eval_current_confusion.md](route_eval_current_confusion.md): 当前错误混淆统计和主因判断。
- [route_eval_v3_2_train.md](route_eval_v3_2_train.md): `lora_route_v3_2` 在 V3 train 上的评测记录。
- [route_eval_v3_2_valid.md](route_eval_v3_2_valid.md): `lora_route_v3_2` 在 V3 valid 上的评测记录。
- [route_eval_v3_2_test.md](route_eval_v3_2_test.md): `lora_route_v3_2` 在 V3 test 上的评测记录和错误历程。
- [v3_1_fix_plan.md](v3_1_fix_plan.md): V3.1 小修数据计划、目标和暂不做事项。
- [v4_design_notes.md](v4_design_notes.md): V4 场景识别路线、数据集和当前结论。
- [v4_1_dataset_notes.md](v4_1_dataset_notes.md): V4.1 数据修订、校验结果和下一轮训练命令。
- [v4_2_dataset_notes.md](v4_2_dataset_notes.md): V4.2 数据修订、分布偏移修复、校验结果和训练命令。

## 当前结论快照

- V2 数据修复了 V1 的主要标签矛盾：记忆查询和画像更新统一进入 `memory_tools`，并设置 `need_tools=true`。
- V2 prompt 增加了完整枚举约束，并新增 `unknown_tools`，避免未知工具需求被错误标成 `none`。
- 重要前提：本轮实验是使用 `route_v2_train.jsonl` 训练 LoRA，并直接在同一个训练集上评测，不是验证集或测试集评测。
- 即使在训练集评测条件下，`lora_route_v2` 和 `lora_route_v2_2` 的完全匹配率都只有 `40.34%`，说明问题首先是训练集未拟合，而不是验证集泛化差。
- 本轮 `full_sft + lora_route_v2` 在训练集 `route_v2_train.jsonl` 上有提升，但仍未拟合训练集。
- V1 训练集完全匹配约 `29.83%`，V2 训练集完全匹配提升到 `40.34%`。
- V2 的 `need_tools` 字段提升明显，达到 `85.30%`，说明 memory/tool 口径统一是有效的。
- 主要弱项仍然是 `intent`、`tool_scope`、`risk_level`，当前模型仍会把大量请求误判为 `tool_execution + shell_tools + high_risk`。
- 已完成 `max_seq_len=1024` 对照训练，训练集完全匹配仍为 `40.34%`，错误行集合与上一轮完全一致，说明单纯加长上下文不是主因。
- 模板固定实验已经完成：训练侧和评测侧模板已统一，但最新结果仍大量出现 `tool_execution + shell_tools + high_risk` 过度预测、记忆类边界混淆和 schema 外输出。
- 因此，模板不一致已排除为当前主因，下一步应转向 V3 边界数据设计，或降低第一版输出空间复杂度。
- V3 数据已生成，基于 V2 追加边界 hard negative，总量 `2380` 条，其中 train `1664`、valid `355`、test `361`。
- V3 数据校验通过：`ok=true`，`high_risk_test_count=33`，`issues=[]`。
- 已完成 `lora_route_v3_2` 的 train 评测：完全匹配 `1304/1664 = 78.37%`，相比模板固定版 baseline `40.34%` 提升 `38.03` 个百分点。
- 已完成 `lora_route_v3_2` 的 valid 评测：完全匹配 `290/355 = 81.69%`，相比 baseline 提升 `41.35` 个百分点。
- 已完成 `lora_route_v3_2` 的 test 评测：完全匹配 `284/361 = 78.67%`，相比 baseline 提升 `38.33` 个百分点。
- train、valid、test 均稳定在 `78%-82%` 区间，V3 数据路线成立，`lora_route_v3_2` 可作为当前阶段 baseline 冻结。
- V3.1 小修数据已生成，不覆盖 V3，保留 V3 split 并追加 `74` 条 delta；总量 `2454` 条，其中 train `1713`、valid `361`、test `380`。
- V3.1 数据校验通过：`ok=true`，`high_risk_test_count=34`，`issues=[]`。
- 已完成 `lora_route_v3_1` train 评测：完全匹配 `1357/1713 = 79.22%`，相比 V3_2 train `78.37%` 仅提升 `0.85` 个百分点，暂不能判定 V3.1 成功。
- V3.1 train 的 Schema 合法率达到 `99.94%`，但 `intent/tool_scope/risk_level` 边界仍是主要问题。
- 因此从 V4 开始，MiniRoute 主线改为轻量场景识别器，不再一次性生成五字段工具治理结果。
- V4 输入只保留 `has_active_task` 和 `user_message`，输出 `scene`、`operation`、`request_mode` 三字段。
- V4 数据已生成：train `2400`、valid `300`、test `300`，总量 `3000`，随机种子 `20260806`。
- V4 后续需要在 MiniMind 侧新增 `eval_route_v4.py` 或修改评测字段，不能继续直接使用旧五字段 `eval_route.py`。
- 已完成 V4 train 首轮评测：完全匹配 `1831/2400 = 76.29%`，但 `scene=95.54%`、`operation=96.29%`，说明场景识别方向成立。
- V4 train 的主要问题是 `request_mode`：`569` 个错误中 `462` 个是 request_mode-only，根因是 `compound` 按 `index % 5 == 0` 机械生成。
- V4.1 数据已生成，不覆盖 V4：train `2400`、valid `300`、test `300`，`compound_count=600`，schema 校验和 V4.1 语义校验均通过。
- V4.1 将 `compound` 限定为同一场景、同一操作下多个同类目标，不再生成跨场景 compound。
- V4.1 train 评测几乎满分：`2396/2400 = 99.83%`，`request_mode=100.00%`，说明机械标注问题已经修掉。
- 但 V4.1 valid/test 掉到约 `50%-51%`，scene/operation 仅 `66%-67%`，说明 split-specific 话术差异过大，出现明显分布偏移。
- 当前更像模板迁移问题，不适合继续堆同一版训练；下一步应做 V4.2，收缩 train/valid/test 的话术差异。
- V4.2 数据已生成，不覆盖 V4/V4.1：train `2400`、valid `300`、test `300`，总量 `3000`，`compound_count=600`。
- V4.2 让 train、valid、test 共享同一组 template family，并使用不同 held-out 句式；生成期 exact/normalized 跨 split 泄漏为 `0`，split 内 normalized 重复为 `0`，同模板族跨 split 最高 4-gram Jaccard 相似度为 `0.3871`。
- V4.2 本地单测通过：`7 passed in 1.59s`；schema 校验通过：`ok=true`、`issues=[]`。
- 下一步应训练 `lora_route_v4_2`，验证 valid/test 是否从 V4.1 的 `50%-51%` 回升到 `85%+`。

## 后续记录约定

每次有新训练或评测结果时，更新本目录对应文档，并至少记录：

1. 实验目标：本轮要验证的假设是什么。
2. 修改内容：本轮改了哪些代码、数据、prompt、训练参数或评测脚本。
3. 测试数据：train、valid、test 文件路径、样本数量、数据版本和随机种子。
4. 训练方案：基座权重、LoRA 名称、epoch、batch size、学习率、`max_seq_len`、chat template 设置。
5. 评测方案：完整评测命令、评测集、empty think 处理方式、schema 校验方式。
6. 测试结果：完全匹配率、字段准确率、严格 JSON 比例、可提取 JSON 比例、schema 外输出数量。
7. 错误分析：V4 记录 Top scene、operation、request_mode 混淆；历史五字段实验再记录 Top intent、tool_scope、risk_level 混淆。
8. 结论：本轮假设是否成立，问题是训练模板、训练参数、数据边界还是模型能力。
9. 下一步：继续调参、进入 V3 数据、简化输出字段或暂停该路线。

## 单次实验记录流程

每次训练或评测结束后，按下面顺序补文档：

1. 复制 `EXPERIMENT_RECORD_TEMPLATE.md`，命名为 `route_eval_版本或日期.md`。
2. 填写本轮实验目标、修改内容、训练命令和评测命令。
3. 粘贴 train、valid、test 的核心指标，不能只写一个最终准确率。
4. 记录 Top 混淆模式，尤其是 `tool_execution + shell_tools + high_risk` 过度预测、记忆类边界混淆和 schema 外输出。
5. 把新发现的问题追加到 `route_issue_log.md`，不要覆盖旧问题。
6. 根据结果更新 `route_experiment_plan.md`，明确下一轮优先级。
7. 更新本 README 的“当前结论快照”，保证打开目录后能直接看到最新状态。

## 指标记录口径

- `train` 结果用于判断模型是否学会训练数据，不能当成泛化能力。
- `valid` 结果用于选择数据版本、训练参数和模板方案。
- `test` 结果只在方案稳定后使用，用于阶段性结论。
- `strict_json` 表示模型是否只输出 JSON。
- `extractable_json` 表示能否从输出中提取 JSON，但不代表格式已经合格。
- V4 的 `exact_match` 表示 `scene`、`operation`、`request_mode` 三个字段全部正确，是后续主指标。
- V4 字段准确率必须拆开看，尤其关注 `scene` 和 `operation`。
- V4 schema 外输出必须单独记录，例如缺字段、枚举错误或输出旧五字段。
- 历史五字段实验仍需记录 `intent`、`tool_scope`、`risk_level`，用于和 V3_2 baseline 对照。

## 当前待验证重点

模板固定已经完成，V3 数据也已生成，并完成 train/valid/test 评测。V3.1 小修数据也已生成，但 train 只从 `78.37%` 提升到 `79.22%`。V4 首轮证明 scene/operation 可学，但 request_mode 标签有问题。V4.1 修掉了 request_mode 机械标注，但 valid/test 掉分严重。V4.2 已生成并通过本地校验，当前重点切换到 MiniMind 训练验证：

- 冻结 `lora_route_v4_1` 作为 request_mode 修复对照。
- 使用 `route_v4_2_train/valid/test.jsonl` 训练 `lora_route_v4_2`。
- 重点看 valid/test 是否从 `50%-51%` 回到 `85%+`。
- 继续观察 `file -> action`、`unknown -> action`、`content -> action` 危险混淆。
- 如果 V4.2 仍无法泛化，再重新审视 schema 或模型容量，而不是继续无目标堆模板。
- Shadow 接入后记录原流程实际 token 和时延，用来判断 V4 是否真的带来上下文优化收益。

`lora_route_v3_2` 继续作为旧五字段 baseline 冻结，后续不再用 V3.1 小修作为主线，除非需要补充历史对照。
