# Governance Docs

这个目录统一管理 `akashic-agent` 的问题、演进、修复路线、设计决策和 STAR 复盘。

业务目录只保留领域知识和原始事实：

- `architecture/`：架构与模块理解。
- `test_docs/`：测试方案、测试日志、自动评估报告。
- `rag/`：RAG 设计、实验、评估和面试表达。
- `local_agent/`：本地个人数字员工 / 本地开发工作台 Agent 的产品和架构演进路线。
- `interview/`：通用面试表达。
- `learning/`：学习路线和运行手册。

治理目录负责把这些事实进一步抽象成“问题、路线、决策、复盘”。

## 文档列表

- [01-issue-index.md](./01-issue-index.md): 全局问题总表，记录技术债、风险和待解决问题。
- [02-current-issues.md](./02-current-issues.md): 当前待解决问题，从测试、架构、RAG、系统问题中提炼。
- [03-domain-evolution.md](./03-domain-evolution.md): 领域演进记录，按 Architecture / Test / RAG / System 分节。
- [04-fix-roadmap.md](./04-fix-roadmap.md): 修复优先级、阶段计划和验证方式。
- [05-design-decisions.md](./05-design-decisions.md): 重要设计取舍记录。
- [06-star-log.md](./06-star-log.md): 通用 STAR 复盘案例库。
- [08-tool-invocation-policy-p1-status.md](./08-tool-invocation-policy-p1-status.md): Tool Safety Gateway P1.1 调用级策略接口状态、规则和验证结果。

## 映射规则

| 场景 | 原始事实放哪里 | 治理记录放哪里 |
| --- | --- | --- |
| 测试失败 | `test_docs/07-test-log.md` 或 `test_docs/eval_suite/reports/` | `02-current-issues.md` 或 `03-domain-evolution.md` |
| 测试体系变化 | `test_docs/` | `03-domain-evolution.md` 的 Test 分节 |
| 架构问题 | `architecture/` | `03-domain-evolution.md` 的 Architecture 分节 |
| RAG 实验问题 | `rag/` | `03-domain-evolution.md` 的 RAG 分节 |
| 本地 Agent 产品/架构路线 | `local_agent/` | 如形成问题或取舍，再进入 `03-domain-evolution.md`、`05-design-decisions.md` 或 `06-star-log.md` |
| 跨模块系统问题 | 相关领域目录 | `02-current-issues.md` 和 `03-domain-evolution.md` 的 System 分节 |
| 修复计划 | 相关领域目录和问题文档 | `04-fix-roadmap.md` |
| 设计取舍 | 相关领域目录和问题文档 | `05-design-decisions.md` |
| 完整复盘案例 | 不分散 | `06-star-log.md` |

## 使用规则

- 原始事实先放回产生它的地方。
- 需要跟踪的问题进入 `01-issue-index.md` 和 `02-current-issues.md`。
- 领域过程变化进入 `03-domain-evolution.md`。
- 修复计划进入 `04-fix-roadmap.md`。
- 重要取舍进入 `05-design-decisions.md`。
- 形成完整闭环、可复盘、可面试表达的问题进入 `06-star-log.md`。

## 后续更新提示词

```text
请按 my_md/governance 的映射规则更新文档：原始事实留在对应业务目录；需要治理的问题同步到 my_md/governance/01-issue-index.md 或 02-current-issues.md；领域演进写入 03-domain-evolution.md；修复计划写入 04-fix-roadmap.md；设计取舍写入 05-design-decisions.md；完整 STAR 案例写入 06-star-log.md。
```
