# Akashic Agent Test Docs

这个文件夹专门用于记录 `akashic-agent` 的测试方案、测试步骤、测试记录和问题复盘。

目标不是一次性跑完所有测试，而是按链路逐步验证：

```text
被动对话主链路
-> Memory / RAG
-> 工具调用
-> 插件扩展
-> Proactive 主动链路
-> Background / Subagent
-> Observe / Dashboard
-> 回归测试
```

## 文档列表

- [00-test-strategy.md](./00-test-strategy.md): 总体测试策略和测试顺序。
- [01-passive-agent-loop-test.md](./01-passive-agent-loop-test.md): 被动对话主链路测试。
- [02-memory-rag-test.md](./02-memory-rag-test.md): Memory / RAG 测试。
- [03-tool-plugin-test.md](./03-tool-plugin-test.md): 工具和插件测试。
- [04-proactive-background-test.md](./04-proactive-background-test.md): Proactive、Scheduler、Background Job、Subagent 测试。
- [05-observe-dashboard-test.md](./05-observe-dashboard-test.md): Observe / Dashboard / Trace 测试。
- [06-regression-checklist.md](./06-regression-checklist.md): 回归测试清单。
- [07-test-log.md](./07-test-log.md): 实际测试记录。
- [eval_suite/](./eval_suite/): Agent 能力评估测试集，覆盖任务成功率、工具正确率、安全、记忆、隔离、RAG 质量和成本。

## 测试记录模板

每次测试都按这个格式记录到 `07-test-log.md`：

```text
测试日期：
测试链路：
测试目标：
输入：
预期行为：
实际行为：
涉及文件：
观察到的 trace / 日志：
问题：
结论：
下一步：
```

## 后续更新提示词

```text
请根据本次测试结果，更新 my_md/test_docs 下相关测试文档，补充测试步骤、实际结果、问题、结论和下一步计划。
```

如果涉及测试体系本身的演进，例如新增测试集、修正误判、调整 judge 或指标，请同步更新：

```text
请更新 my_md/governance/03-domain-evolution.md 的 Test 分节，记录本次测试体系发现、处理、结果、证据、影响和下一步。
```
